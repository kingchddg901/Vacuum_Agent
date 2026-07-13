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

Stop restores the logger exactly. Dump reads the ring on demand. Off by default →
zero cost when unused. This module is deliberately hass-free (pure ``logging``) so it
unit-tests as plain objects; the service layer owns the file write + hass plumbing.
"""

from __future__ import annotations

import collections
import logging
import time
import traceback
from typing import Any

PACKAGE_LOGGER = "custom_components.eufy_vacuum"
DEFAULT_CAPACITY = 3000
MAX_CAPACITY = 50000

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


class _RingHandler(logging.Handler):
    """Bounded in-memory ring of formatted log entries, optionally area-filtered."""

    def __init__(self, capacity: int, area_subs: tuple[str, ...] | None) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: collections.deque[dict[str, Any]] = collections.deque(maxlen=capacity)
        self._subs = area_subs
        self.seen = 0  # total records that passed the area filter (may exceed capacity)
        self._seq = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self._subs is not None and not any(s in record.name for s in self._subs):
                return
            self.seen += 1
            self._seq += 1
            entry: dict[str, Any] = {
                "seq": self._seq,
                "t": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
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
        self._last: collections.deque[dict[str, Any]] = collections.deque()

    @property
    def active(self) -> bool:
        return self._ring is not None

    def start(self, *, areas: list[str] | None = None, capacity: int | None = None) -> dict[str, Any]:
        """Begin capturing. Restarts cleanly if already active. Returns status."""
        if self.active:
            self.stop()
        cap = DEFAULT_CAPACITY if not capacity else int(capacity)
        cap = max(1, min(cap, MAX_CAPACITY))
        self._areas = [str(a) for a in (areas or [])]
        self._last = collections.deque()
        self._ring = _RingHandler(cap, self._resolve_areas(self._areas))
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
        self._last = collections.deque()

    def status(self) -> dict[str, Any]:
        if self._ring is not None:
            return {
                "active": True,
                "captured": len(self._ring.records),
                "seen": self._ring.seen,
                "capacity": self._ring.records.maxlen,
                "areas": list(self._areas),
                "started_at": self._started_at,
            }
        return {
            "active": False,
            "captured": len(self._last),
            "seen": 0,
            "capacity": None,
            "areas": list(self._areas),
            "started_at": self._started_at,
        }

    @staticmethod
    def _resolve_areas(areas: list[str]) -> tuple[str, ...] | None:
        if not areas:
            return None
        subs: list[str] = []
        for a in areas:
            subs.extend(AREA_MATCHERS.get(str(a).lower(), (f".{a}",)))
        return tuple(subs) or None


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
