"""Silent debug "flight recorder" — a drop-in, integration-agnostic helper.

WHY: turning on DEBUG for an integration (via HA's ``logger:`` config or the
per-integration debug toggle) floods the *shared* ``home-assistant.log`` — noisy, not
silent, sometimes huge. This captures ONE integration's DEBUG into a bounded in-memory
ring WITHOUT crushing the main log, and dumps it on demand.

DROP-IN, in three steps — nothing here is specific to any integration:

1. Copy this file into your integration.
2. Register the four services (change one setting — your domain)::

       from .debug_capture import register_debug_services
       register_debug_services(hass, domain=DOMAIN)   # package_logger defaults to
                                                       # custom_components.<domain>

   optionally pass ``areas={...}`` (logger-substring scopes) to enable the ``areas``
   filter. Copy the four ``debug_capture_*`` blocks from ``services.yaml`` too.
3. (optional) Mark noisy handlers ``@debug_traceable("your_service")`` for per-service
   tracing.

HOW it stays silent: while active it sets the configured package logger to ``DEBUG``
with ``propagate = False`` (so DEBUG never reaches HA's root handlers / the main log)
and attaches a :class:`_RingHandler` (DEBUG → ring) plus a :class:`_PassthroughHandler`
(INFO → root, so normal logs still land in ``home-assistant.log``). Stop restores the
logger exactly. Off by default → zero cost when unused.
"""

from __future__ import annotations

import collections
import functools
import logging
import os
import time
import traceback
from typing import Any, Callable

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later

DEFAULT_CAPACITY = 3000
MAX_CAPACITY = 50000
# Cap a single record's message so one giant payload (a base64 map image, a full
# dashboard snapshot) can't bloat the dump.
MAX_MESSAGE_CHARS = 2000

# The four service names this helper registers. Fixed — the caller supplies the domain.
DEBUG_CAPTURE_START = "debug_capture_start"
DEBUG_CAPTURE_STOP = "debug_capture_stop"
DEBUG_CAPTURE_DUMP = "debug_capture_dump"
DEBUG_CAPTURE_STATUS = "debug_capture_status"
SERVICE_NAMES = (
    DEBUG_CAPTURE_START,
    DEBUG_CAPTURE_STOP,
    DEBUG_CAPTURE_DUMP,
    DEBUG_CAPTURE_STATUS,
)

# --- the one setting: which logger tree to capture (+ optional named areas) ----------
# Configured by register_debug_services(); defaults to the whole custom_components tree
# so the module is usable even before configure() runs.
_PACKAGE_LOGGER = "custom_components"
_AREAS: dict[str, tuple[str, ...]] = {}
_DUMP_SUBDIR = "debug"


def configure(package_logger: str, areas: dict[str, tuple[str, ...]] | None = None) -> None:
    """Point the recorder at one integration's logger tree (+ optional area scopes)."""
    global _PACKAGE_LOGGER, _AREAS
    _PACKAGE_LOGGER = package_logger
    _AREAS = dict(areas or {})


# --- per-service trace registry ------------------------------------------------------
_TRACEABLE: set[str] = set()


def register_traceable(name: str) -> None:
    _TRACEABLE.add(str(name))


def traceable_services() -> list[str]:
    return sorted(_TRACEABLE)


class _RingHandler(logging.Handler):
    """Bounded in-memory ring of formatted log entries, optionally gated + filtered."""

    def __init__(
        self,
        capacity: int,
        area_subs: tuple[str, ...] | None,
        gate: Callable[[], bool] | None = None,
        freeze: bool = False,
    ) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: collections.deque[dict[str, Any]] = collections.deque(maxlen=capacity)
        self._subs = area_subs
        self._gate = gate  # when set, only record while it returns True (span-scoped)
        self._freeze = freeze  # stop at capacity instead of evicting oldest
        self.full = False
        self.seen = 0  # total records that passed the filters (may exceed capacity)
        self._seq = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self._gate is not None and not self._gate():
                return
            if self._subs is not None and not any(s in record.name for s in self._subs):
                return
            self.seen += 1
            if self._freeze and len(self.records) >= (self.records.maxlen or 0):
                self.full = True
                return  # keep the first N, drop the rest
            self._seq += 1
            message = record.getMessage()
            if len(message) > MAX_MESSAGE_CHARS:
                message = message[:MAX_MESSAGE_CHARS] + f"…(+{len(message) - MAX_MESSAGE_CHARS} chars elided)"
            entry: dict[str, Any] = {
                "seq": self._seq,
                "t": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
            if record.exc_info:
                entry["exc"] = "".join(traceback.format_exception(*record.exc_info)).rstrip()
            self.records.append(entry)
        except Exception:  # logging must never break the app
            self.handleError(record)


class _PassthroughHandler(logging.Handler):
    """Re-emit INFO+ to the root handlers, so normal logging still reaches
    ``home-assistant.log`` while the package logger is isolated (propagate=False)."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            logging.getLogger().handle(record)
        except Exception:
            self.handleError(record)


class DebugCapture:
    """Start/stop the silent capture and read the ring. One instance per process."""

    def __init__(self) -> None:
        self._ring: _RingHandler | None = None
        self._passthrough: _PassthroughHandler | None = None
        self._prior_level: int | None = None
        self._prior_propagate: bool | None = None
        self._logger_name: str | None = None  # the tree we isolated (frozen at start)
        self._started_at: float | None = None
        self._areas: list[str] = []
        self._targets: set[str] = set()
        self._span_depth = 0
        self._last: collections.deque[dict[str, Any]] = collections.deque()

    @property
    def active(self) -> bool:
        return self._ring is not None

    def start(
        self,
        *,
        areas: list[str] | None = None,
        capacity: int | None = None,
        services: list[str] | None = None,
        freeze: bool = False,
    ) -> dict[str, Any]:
        """Begin capturing. Restarts cleanly if already active. Returns status.

        ``services`` arms per-service tracing: the ring then records ONLY while inside
        a flagged (:func:`debug_traceable`) service's span. ``freeze`` stops at capacity
        instead of evicting oldest.
        """
        if self.active:
            self.stop()
        cap = DEFAULT_CAPACITY if not capacity else int(capacity)
        cap = max(1, min(cap, MAX_CAPACITY))
        self._areas = [str(a) for a in (areas or [])]
        self._targets = {str(s) for s in (services or [])}
        self._span_depth = 0
        self._last = collections.deque()
        gate = self._gate if self._targets else None
        self._ring = _RingHandler(cap, self._resolve_areas(self._areas), gate=gate, freeze=bool(freeze))
        self._passthrough = _PassthroughHandler()
        self._logger_name = _PACKAGE_LOGGER
        logger = logging.getLogger(self._logger_name)
        self._prior_level = logger.level
        self._prior_propagate = logger.propagate
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(self._ring)
        logger.addHandler(self._passthrough)
        self._started_at = time.time()
        return self.status()

    def stop(self) -> dict[str, Any]:
        """Restore the isolated logger and detach handlers. Records survive for a final
        dump. Idempotent — a no-op when not active."""
        if self._logger_name is not None:
            logger = logging.getLogger(self._logger_name)
            if self._ring is not None:
                self._last = self._ring.records
                logger.removeHandler(self._ring)
            if self._passthrough is not None:
                logger.removeHandler(self._passthrough)
            if self._prior_propagate is not None:
                logger.propagate = self._prior_propagate
            if self._prior_level is not None:
                logger.setLevel(self._prior_level)
        status = self.status()  # reads _last (now inactive)
        self._ring = None
        self._passthrough = None
        self._prior_level = None
        self._prior_propagate = None
        self._logger_name = None
        self._span_depth = 0
        return status

    def records(self) -> list[dict[str, Any]]:
        """Snapshot of the captured records (live ring if active, else the last stop)."""
        if self._ring is not None:
            return list(self._ring.records)
        return list(self._last)

    def clear(self) -> None:
        if self._ring is not None:
            self._ring.records.clear()
            self._ring.seen = 0
            self._ring.full = False
        self._last = collections.deque()

    def status(self) -> dict[str, Any]:
        ring = self._ring
        return {
            "active": ring is not None,
            "captured": len(ring.records) if ring is not None else len(self._last),
            "seen": ring.seen if ring is not None else 0,
            "capacity": ring.records.maxlen if ring is not None else None,
            "full": ring.full if ring is not None else False,
            "logger": self._logger_name,
            "areas": list(self._areas),
            "services": sorted(self._targets),
            "started_at": self._started_at,
        }

    # -- per-service tracing ------------------------------------------------

    def _gate(self) -> bool:
        """Ring gate for service-targeted mode: record only inside a flagged span."""
        return self._span_depth > 0

    def is_armed(self, name: str) -> bool:
        """Whether ``name`` should be bracketed: capture active and either global
        (no service targets) or this service is one of the targets."""
        return self.active and (not self._targets or name in self._targets)

    async def run_span(self, name: str, call: Any, fn: Callable) -> Any:
        """Bracket a flagged service call in the ring with start/end markers."""
        span_logger = logging.getLogger(f"{self._logger_name or _PACKAGE_LOGGER}.debug.span")
        self._span_depth += 1
        started = time.time()
        span_logger.debug("▶▶ %s  in=%s", name, _summarize(getattr(call, "data", None)))
        result: Any = None
        try:
            result = await fn(call)
            return result
        finally:
            elapsed_ms = int((time.time() - started) * 1000)
            span_logger.debug("◀◀ %s  done in %dms  out=%s", name, elapsed_ms, _summarize(result))
            self._span_depth = max(0, self._span_depth - 1)

    @staticmethod
    def _resolve_areas(areas: list[str]) -> tuple[str, ...] | None:
        if not areas:
            return None
        subs: list[str] = []
        for a in areas:
            subs.extend(_AREAS.get(str(a).lower(), (f".{a}",)))
        return tuple(subs) or None


def _summarize(value: Any, limit: int = 300) -> str:
    """Compact, truncated repr for span in/out markers (keeps coords/base64 readable)."""
    try:
        text = repr(dict(value)) if isinstance(value, dict) else repr(value)
    except Exception:
        text = "<unreprable>"
    if len(text) > limit:
        text = text[:limit] + f"…(+{len(text) - limit})"
    return text


def render_text(records: list[dict[str, Any]]) -> str:
    """Render captured records to a readable log-style text block for a dump file."""
    lines: list[str] = []
    for r in records:
        t = r.get("t", 0.0)
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) + f".{int((t % 1) * 1000):03d}"
        lines.append(f"{ts} {str(r.get('level', '')):<7} {r.get('logger', '')}: {r.get('message', '')}")
        if r.get("exc"):
            lines.append(str(r["exc"]))
    return "\n".join(lines) + ("\n" if lines else "")


_CAPTURE: DebugCapture | None = None


def get_capture() -> DebugCapture:
    """The process-wide capture singleton (logging is process-global)."""
    global _CAPTURE
    if _CAPTURE is None:
        _CAPTURE = DebugCapture()
    return _CAPTURE


def debug_traceable(name: str) -> Callable:
    """Flag a service handler as per-service traceable AND wrap it.

    Registers ``name`` as a trace target at import time; at call time, when a capture is
    *armed* for ``name`` the call is bracketed in the ring. No-op (zero cost) otherwise."""
    register_traceable(name)

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(call: Any) -> Any:
            capture = get_capture()
            if not capture.is_armed(name):
                return await fn(call)
            return await capture.run_span(name, call, fn)

        return wrapper

    return decorator


# --- HA service layer (drop-in registration) -----------------------------------------

_START_SCHEMA = vol.Schema(
    {
        vol.Optional("areas"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("services"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("size"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_CAPACITY)),
        vol.Optional("max_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("stop_when_full", default=False): cv.boolean,
    }
)
_DUMP_SCHEMA = vol.Schema(
    {
        vol.Optional("write_file", default=True): cv.boolean,
        vol.Optional("clear", default=False): cv.boolean,
    }
)
_EMPTY_SCHEMA = vol.Schema({})


def _write_dump(hass: HomeAssistant, domain: str, records: list[dict[str, Any]]) -> str:
    """Write the rendered ring to ``config/<domain>/debug/debug-<ts>.log``. Blocking —
    call via the executor. Returns the path."""
    dir_path = hass.config.path(domain, _DUMP_SUBDIR)
    os.makedirs(dir_path, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    path = os.path.join(dir_path, f"debug-{ts}.log")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_text(records))
    return path


def register_debug_services(
    hass: HomeAssistant,
    *,
    domain: str,
    package_logger: str | None = None,
    areas: dict[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    """Register the four ``debug_capture_*`` services under ``domain``.

    The only required setting is ``domain``; ``package_logger`` defaults to
    ``custom_components.<domain>``. Returns the registered service names (hand them to
    your unregister path). Drop this whole file into any integration and call this.
    """
    configure(package_logger or f"custom_components.{domain}", areas)
    _LOGGER = logging.getLogger(f"{_PACKAGE_LOGGER}.debug")
    autostop: dict[str, Any] = {"cancel": None}

    def _cancel_autostop() -> None:
        if autostop["cancel"] is not None:
            autostop["cancel"]()
            autostop["cancel"] = None

    async def start(call: ServiceCall) -> dict[str, Any]:
        _cancel_autostop()
        status = get_capture().start(
            areas=call.data.get("areas"),
            capacity=call.data.get("size"),
            services=call.data.get("services"),
            freeze=call.data.get("stop_when_full", False),
        )
        minutes = call.data.get("max_minutes")
        if minutes:
            @callback
            def _auto_stop(_now: Any) -> None:
                autostop["cancel"] = None
                stopped = get_capture().stop()
                _LOGGER.info(
                    "debug capture auto-stopped after %s min (captured=%s)",
                    minutes,
                    stopped.get("captured"),
                )

            autostop["cancel"] = async_call_later(hass, minutes * 60, _auto_stop)
            status["auto_stop_minutes"] = minutes
        # INFO so the breadcrumb reaches home-assistant.log (via the passthrough).
        _LOGGER.info("debug capture STARTED: %s", status)
        return status

    async def stop(call: ServiceCall) -> dict[str, Any]:
        _cancel_autostop()
        status = get_capture().stop()
        _LOGGER.info("debug capture STOPPED (captured=%s)", status.get("captured"))
        return status

    async def dump(call: ServiceCall) -> dict[str, Any]:
        capture = get_capture()
        records = capture.records()
        result: dict[str, Any] = {
            "active": capture.active,
            "count": len(records),
            "records": records,
        }
        if call.data.get("write_file", True):
            result["file"] = await hass.async_add_executor_job(_write_dump, hass, domain, records)
        if call.data.get("clear", False):
            capture.clear()
        return result

    async def status(call: ServiceCall) -> dict[str, Any]:
        payload = get_capture().status()
        payload["traceable"] = traceable_services()
        return payload

    hass.services.async_register(domain, DEBUG_CAPTURE_START, start, schema=_START_SCHEMA, supports_response=True)
    hass.services.async_register(domain, DEBUG_CAPTURE_STOP, stop, schema=_EMPTY_SCHEMA, supports_response=True)
    hass.services.async_register(domain, DEBUG_CAPTURE_DUMP, dump, schema=_DUMP_SCHEMA, supports_response=True)
    hass.services.async_register(domain, DEBUG_CAPTURE_STATUS, status, schema=_EMPTY_SCHEMA, supports_response=True)
    return SERVICE_NAMES
