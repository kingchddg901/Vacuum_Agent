"""Silent debug "flight recorder" for the integration.

The problem this solves: turning on DEBUG for ``custom_components.eufy_vacuum`` (via
HA's ``logger:`` config or the per-integration debug toggle) floods the *shared*
``home-assistant.log`` — noisy, not silent, sometimes huge (map / snapshot spam).

This captures the integration's own DEBUG into a bounded in-memory ring WITHOUT
crushing the main log. While active it:

- sets the ``custom_components.eufy_vacuum`` logger to ``DEBUG`` with
  ``propagate = False`` — so DEBUG records never reach HA's root handlers (the main
  log stays clean at whatever level it's on), and
- attaches two handlers: a :class:`_RingHandler` (DEBUG) that snapshots every record
  into a ``deque``, and a :class:`_PassthroughHandler` (INFO) that re-emits INFO+ to
  the root handlers so normal logs *still* land in ``home-assistant.log``.

Per-service tracing: mark a service handler with :func:`debug_traceable`. When a
capture is *armed* for that service (``services=[...]`` on start), the ring records
ONLY while inside that service's span — so firing one service captures just that
operation, bracketed with ``▶▶``/``◀◀`` markers. Individual records are truncated
so one giant payload (a base64 map image) can't bloat the dump.

Stop restores the logger exactly. Off by default → zero cost when unused. This module
is hass-free (pure ``logging``) so it unit-tests as plain objects; the service layer
owns the file write, the auto-stop timer, and the hass plumbing.
"""

from __future__ import annotations

import collections
import functools
import logging
import time
import traceback
from typing import Any, Callable

PACKAGE_LOGGER = "custom_components.eufy_vacuum"
DEFAULT_CAPACITY = 3000
MAX_CAPACITY = 50000
# Cap a single record's message so one giant payload (a base64 map image, a full
# dashboard snapshot) can't bloat the dump — a real 10 MB capture was mostly these.
MAX_MESSAGE_CHARS = 2000

# area name -> substrings matched against a record's logger name (which is
# ``custom_components.eufy_vacuum.<module path>``). Passing no areas captures
# everything; an unknown area falls back to a literal ``.<area>`` substring.
AREA_MATCHERS: dict[str, tuple[str, ...]] = {
    "map": (".mapping", ".map_source", ".rooms.source_refresh"),
    "rooms": (".rooms", ".room_entities"),
    "dispatch": (".services.job_control", ".jobs", ".queue", ".planning", ".dispatch", ".core.manager"),
    "learning": (".learning", ".battery"),
    "setup": (".setup", ".onboarding", ".panels"),
    "themes": (".themes",),
}

# Services flagged (via @debug_traceable) as worth per-service tracing — the source
# of truth for the debug-target select's options.
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
        a flagged (:func:`debug_traceable`) service's span — so firing one service
        captures just that operation. ``freeze`` stops at capacity instead of evicting.
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
        logger = logging.getLogger(PACKAGE_LOGGER)
        self._prior_level = logger.level
        self._prior_propagate = logger.propagate
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(self._ring)
        logger.addHandler(self._passthrough)
        self._started_at = time.time()
        return self.status()

    def stop(self) -> dict[str, Any]:
        """Restore the logger and detach handlers. Records survive for a final dump.
        Idempotent — a no-op when not active."""
        logger = logging.getLogger(PACKAGE_LOGGER)
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
        """Bracket a flagged service call in the ring with start/end markers.

        The span logger sits under the package, so the markers land in the ring; the
        depth counter opens the gate (targeted mode) so downstream logs during the
        call are captured, then closes it again."""
        span_logger = logging.getLogger(f"{PACKAGE_LOGGER}.debug.span")
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
            subs.extend(AREA_MATCHERS.get(str(a).lower(), (f".{a}",)))
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

    Registers ``name`` as a trace target at import time (→ the debug-target select's
    options). At call time, when a capture is *armed* for ``name`` the call is bracketed
    in the ring (see :meth:`DebugCapture.run_span`); otherwise the wrap is a no-op, so
    it costs nothing when capture is off."""
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
