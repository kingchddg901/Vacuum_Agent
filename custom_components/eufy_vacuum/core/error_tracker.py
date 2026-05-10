"""Active-run error tracking for Eufy Vacuum Manager.

Latches transient upstream errors with active-run context, persists across
restarts, and surfaces them through dedicated entities — without coupling to
``robovac_mqtt`` internals. Reads ``sensor.<obj>_error_message`` and
``vacuum.<obj>`` state via HA's state engine; never imports or invokes
upstream coordinator/parser code.

Three buffers per device, all stored under
``manager.data["error_tracker"][<vacuum_entity_id>]``:

- ``active_run_error`` — sticky during a job. Set on first rising edge while
  a job is active; appended-to on subsequent rising edges; recovered=True
  flag flips when the upstream message clears mid-run; nulled out on harvest
  (called by the JobFinalizer).
- ``last_device_error`` — persistent until acknowledged. Overwritten on
  every rising edge regardless of run context. Cleared only by the
  ``eufy_vacuum.acknowledge_error`` service.
- ``recent_errors`` — append-only ring buffer of the last 50 rising edges,
  for the ``eufy_vacuum.get_recent_errors`` service and debugging.

Edge detection:
- ``not_error`` set: ``{"", "unknown", "unavailable", "NONE", "Normal"}``.
  Anything else is treated as an error string.
- A *rising edge* is a transition from a not_error value (or no prior
  value) to an error value. A *falling edge* is the reverse.

Late-arrival grace window:
- When ``vacuum.<obj>`` transitions to ``"error"`` but
  ``sensor.<obj>_error_message`` is still empty/unknown, a 5-second one-shot
  callback is scheduled. If the message arrives within that window, the
  placeholder latch is upgraded with the actual message + code. If the
  window elapses, the latch is finalized as
  ``"Unknown error during run"`` with ``code: None``.

The tracker is instantiated by ``__init__.async_setup_entry`` after the
runtime ``EufyVacuumManager`` is loaded. ``start(known_vacuum_ids)`` wires
state-change listeners per device and restores latches from storage.
``stop()`` unsubs and is called from ``async_unload_entry``.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)

if TYPE_CHECKING:
    from .manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

# === TUNABLES ================================================================

#: Strings the upstream may emit that mean "no error". Anything else is
#: treated as an error message. The dead ``error_code=0 → "NONE"`` branch in
#: the upstream constants makes ``"NONE"`` important to include alongside
#: the obvious empty / unknown / unavailable values.
_NOT_ERROR: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "normal"}
)

#: How long to wait after ``vacuum.<obj>`` flips to ``"error"`` for a real
#: ``error_message`` to arrive before finalising the latch with a generic
#: placeholder. Some firmware emits the state DPS before the message DPS.
_ERROR_MESSAGE_GRACE_SECONDS = 5

#: Cap on per-device recent_errors ring buffer.
_RECENT_ERRORS_LIMIT = 50

#: Cap on per-latch errors[] list (unbounded would let a misbehaving vacuum
#: balloon storage with thousands of identical messages over a long run).
_LATCH_ERRORS_LIMIT = 50


# === HELPERS =================================================================

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_error_value(value: Any) -> bool:
    """Return True if ``value`` looks like a real error string."""
    if value is None:
        return False
    text = str(value).strip().lower()
    return bool(text) and text not in _NOT_ERROR


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _job_elapsed_seconds(active_job: dict[str, Any] | None) -> int:
    """Compute seconds since active_job.started_at, clamped to 0.

    Returns 0 when no active job is in flight or when started_at can't be
    parsed (rare race during the start sequence).
    """
    if not isinstance(active_job, dict):
        return 0
    started = active_job.get("started_at")
    if not isinstance(started, str):
        return 0
    try:
        started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0
    now = datetime.now(timezone.utc)
    elapsed = int((now - started_dt).total_seconds())
    return max(0, elapsed)


# === TRACKER =================================================================

class ErrorTracker:
    """Single-instance, multi-device error latch tracker.

    Owns the listeners, the in-memory caches, and the storage round-trips.
    Reads from / writes to ``manager.data["error_tracker"]``; calls
    ``manager.async_save()`` to flush. Independent of the battery / mapping
    subsystems but follows the same per-device wire-and-unsub pattern.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        runtime_manager: "EufyVacuumManager",
    ) -> None:
        self._hass = hass
        self._manager = runtime_manager
        # entity_id (state-change source) -> vacuum_entity_id
        self._source_to_vacuum: dict[str, str] = {}
        # vacuum_entity_id -> list of unsub callables
        self._vacuum_unsubs: dict[str, list[Callable[[], None]]] = {}
        # Pending grace-window cancels per vacuum (when vacuum.state == "error"
        # but error_message hasn't arrived yet). Keyed by vacuum_entity_id.
        self._grace_cancels: dict[str, Callable[[], None]] = {}
        # Update notifications for sensors / binary_sensors. Same shape as
        # BatteryHealthManager.add_update_listener.
        self._update_listeners: list[Callable[[str], None]] = []

    # -- listener registration ----------------------------------------------

    def add_update_listener(
        self, cb: Callable[[str], None]
    ) -> Callable[[], None]:
        """Register a callback fired with ``vacuum_entity_id`` whenever its
        latch state changes (rising edge, falling edge, harvest, ack).
        Returns an unregister callable."""
        self._update_listeners.append(cb)

        def _unsub() -> None:
            try:
                self._update_listeners.remove(cb)
            except ValueError:
                pass

        return _unsub

    def _notify(self, vacuum_entity_id: str) -> None:
        for cb in list(self._update_listeners):
            try:
                cb(vacuum_entity_id)
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("error_tracker: update listener raised")

    # -- record access -------------------------------------------------------

    def _root(self) -> dict[str, dict[str, Any]]:
        """Return the per-vacuum error_tracker root dict, creating if absent."""
        return self._manager.data.setdefault("error_tracker", {})

    def _ensure_record(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Return the per-vacuum record, initialising defaults if missing."""
        root = self._root()
        record = root.get(vacuum_entity_id)
        if record is None:
            record = {
                "active_run_error": None,
                "last_device_error": None,
                "recent_errors": [],
            }
            root[vacuum_entity_id] = record
        else:
            record.setdefault("active_run_error", None)
            record.setdefault("last_device_error", None)
            record.setdefault("recent_errors", [])
        return record

    def get_record(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Public read accessor (creates if absent)."""
        return self._ensure_record(vacuum_entity_id)

    def get_active_run_latch(
        self, vacuum_entity_id: str
    ) -> dict[str, Any] | None:
        return self._ensure_record(vacuum_entity_id).get("active_run_error")

    def get_last_device_latch(
        self, vacuum_entity_id: str
    ) -> dict[str, Any] | None:
        return self._ensure_record(vacuum_entity_id).get("last_device_error")

    def recent_errors(
        self, vacuum_entity_id: str, *, limit: int | None = None
    ) -> list[dict[str, Any]]:
        items = list(self._ensure_record(vacuum_entity_id).get("recent_errors") or [])
        if limit is not None and limit >= 0:
            items = items[-limit:]
        return items

    # -- HA wiring -----------------------------------------------------------

    def start(self, vacuum_entity_ids: Iterable[str]) -> None:
        """Begin listening for error_message + vacuum state changes per vacuum.

        Idempotent — re-calling for an already-wired vacuum is a no-op.
        Existing latches in storage are not touched (they survive restart).
        """
        for vacuum_entity_id in vacuum_entity_ids:
            self._wire_vacuum(vacuum_entity_id)

    def stop(self) -> None:
        """Tear down all per-vacuum listeners + pending grace-window timers."""
        for unsubs in self._vacuum_unsubs.values():
            for unsub in unsubs:
                try:
                    unsub()
                except Exception:  # pragma: no cover
                    pass
        self._vacuum_unsubs.clear()
        for cancel in self._grace_cancels.values():
            try:
                cancel()
            except Exception:  # pragma: no cover
                pass
        self._grace_cancels.clear()
        self._source_to_vacuum.clear()

    def _wire_vacuum(self, vacuum_entity_id: str) -> None:
        if vacuum_entity_id in self._vacuum_unsubs:
            return

        # Derive upstream entity ids by object_id, matching the rest of the
        # integration's convention. If the user renames the upstream sensor,
        # this lookup breaks — same constraint as task_status / dock_status /
        # cleaning_area lookups elsewhere. The plan explicitly accepts this
        # parity over a registry-based lookup.
        object_id = vacuum_entity_id.split(".", 1)[-1]
        error_message_entity = f"sensor.{object_id}_error_message"

        self._source_to_vacuum[error_message_entity] = vacuum_entity_id
        self._source_to_vacuum[vacuum_entity_id] = vacuum_entity_id

        self._ensure_record(vacuum_entity_id)

        unsubs: list[Callable[[], None]] = []
        unsubs.append(
            async_track_state_change_event(
                self._hass,
                [error_message_entity, vacuum_entity_id],
                self._on_state_event,
            )
        )
        self._vacuum_unsubs[vacuum_entity_id] = unsubs

    @callback
    def _on_state_event(self, event) -> None:
        entity_id = event.data.get("entity_id")
        vacuum_entity_id = self._source_to_vacuum.get(entity_id)
        if vacuum_entity_id is None:
            return
        new_state_obj = event.data.get("new_state")
        new_state = new_state_obj.state if new_state_obj is not None else None
        old_state_obj = event.data.get("old_state")
        old_state = old_state_obj.state if old_state_obj is not None else None

        if entity_id == vacuum_entity_id:
            # vacuum.<obj> transition. Only relevant when transitioning INTO
            # an error state — that may indicate the firmware fired the state
            # DPS before the message DPS arrived. Schedule a grace window.
            self._handle_vacuum_state_change(
                vacuum_entity_id, old_state, new_state
            )
            return

        # error_message sensor transition — the primary signal.
        self._handle_error_message_change(
            vacuum_entity_id, old_state, new_state
        )

    # -- vacuum.state handling -----------------------------------------------

    def _handle_vacuum_state_change(
        self,
        vacuum_entity_id: str,
        old_state: str | None,
        new_state: str | None,
    ) -> None:
        """Schedule grace-window placeholder if state → 'error' with no msg yet."""
        if str(new_state or "").strip().lower() != "error":
            # Cancel any pending grace timer when leaving error state.
            self._cancel_grace(vacuum_entity_id)
            return

        # Already in error state: only schedule once.
        if vacuum_entity_id in self._grace_cancels:
            return

        # If error_message is already populated, don't bother with the grace
        # window — the message handler will (or already did) latch.
        object_id = vacuum_entity_id.split(".", 1)[-1]
        msg_state = self._hass.states.get(f"sensor.{object_id}_error_message")
        msg_value = msg_state.state if msg_state is not None else None
        if _is_error_value(msg_value):
            return

        self._grace_cancels[vacuum_entity_id] = async_call_later(
            self._hass,
            _ERROR_MESSAGE_GRACE_SECONDS,
            lambda _now, vid=vacuum_entity_id: self._on_grace_expired(vid),
        )

    def _cancel_grace(self, vacuum_entity_id: str) -> None:
        cancel = self._grace_cancels.pop(vacuum_entity_id, None)
        if cancel is not None:
            try:
                cancel()
            except Exception:  # pragma: no cover
                pass

    @callback
    def _on_grace_expired(self, vacuum_entity_id: str) -> None:
        """Grace window elapsed — finalise as a generic placeholder latch."""
        self._grace_cancels.pop(vacuum_entity_id, None)
        # Re-check state at expiry — vacuum may have already left "error".
        vacuum_state = self._hass.states.get(vacuum_entity_id)
        if vacuum_state is None or str(vacuum_state.state or "").strip().lower() != "error":
            return
        # And re-check the message in case it arrived after the timer fired
        # but before this callback ran.
        object_id = vacuum_entity_id.split(".", 1)[-1]
        msg_state = self._hass.states.get(f"sensor.{object_id}_error_message")
        msg_value = msg_state.state if msg_state is not None else None
        if _is_error_value(msg_value):
            return
        self._record_rising_edge(
            vacuum_entity_id,
            message="Unknown error during run",
            code=None,
            attribute_code=None,
        )

    # -- error_message handling ----------------------------------------------

    def _handle_error_message_change(
        self,
        vacuum_entity_id: str,
        old_state: str | None,
        new_state: str | None,
    ) -> None:
        was_error = _is_error_value(old_state)
        is_error = _is_error_value(new_state)

        if is_error:
            # Cancel any pending grace timer — we have a real message now.
            self._cancel_grace(vacuum_entity_id)
            self._record_rising_edge(
                vacuum_entity_id,
                message=str(new_state),
                code=self._read_error_code_attr(vacuum_entity_id),
                attribute_code=None,
            )
            return

        if was_error and not is_error:
            self._record_falling_edge(vacuum_entity_id)

    def _read_error_code_attr(self, vacuum_entity_id: str) -> int | None:
        """Pull the upstream error_code attribute if the sensor exposes one.

        Some upstream releases attach ``error_code`` as a state attribute on
        the error_message sensor; others bury it in the vacuum entity. Try
        both, return the first integer-coercible value.
        """
        object_id = vacuum_entity_id.split(".", 1)[-1]
        for entity_id in (
            f"sensor.{object_id}_error_message",
            vacuum_entity_id,
        ):
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            attrs = getattr(state, "attributes", None) or {}
            for key in ("error_code", "code", "errorCode"):
                value = _safe_int(attrs.get(key))
                if value is not None:
                    return value
        return None

    # -- rising / falling edges ----------------------------------------------

    def _record_rising_edge(
        self,
        vacuum_entity_id: str,
        *,
        message: str,
        code: int | None,
        attribute_code: int | None,
    ) -> None:
        """Form or extend the active-run latch + bump last_device + ring buffer."""
        record = self._ensure_record(vacuum_entity_id)
        now = _iso_now()

        active_job = self._lookup_active_job(vacuum_entity_id)
        active_job_id = self._extract_job_id(active_job)
        elapsed = _job_elapsed_seconds(active_job)
        room_id = self._extract_current_room_id(active_job)

        vacuum_state = self._hass.states.get(vacuum_entity_id)
        vacuum_state_text = (
            vacuum_state.state if vacuum_state is not None else None
        )

        # last_device_error — overwritten regardless of run context.
        record["last_device_error"] = {
            "message": message,
            "code": code,
            "captured_at": now,
            "vacuum_state_at_capture": vacuum_state_text,
            "was_during_active_run": active_job_id is not None,
            "active_job_id_at_capture": active_job_id,
        }

        # recent_errors ring buffer.
        ring = list(record.get("recent_errors") or [])
        ring.append(
            {
                "message": message,
                "code": code,
                "captured_at": now,
                "active_job_id": active_job_id,
                "vacuum_state": vacuum_state_text,
            }
        )
        if len(ring) > _RECENT_ERRORS_LIMIT:
            ring = ring[-_RECENT_ERRORS_LIMIT:]
        record["recent_errors"] = ring

        # active_run_error — only forms when there is an active job.
        if active_job_id is not None:
            latch = record.get("active_run_error")
            if latch is None:
                # First rising edge of this run.
                latch = {
                    "active_job_id": active_job_id,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "first_seen_job_elapsed_seconds": elapsed,
                    "error_count": 0,
                    "current_message": message,
                    "current_code": code,
                    "errored_room_id": room_id,
                    "recovered": False,
                    "errors": [],
                }
            else:
                # Existing latch — fall-through to append. recovered flips
                # back to False because we have a fresh error.
                latch["last_seen_at"] = now
                latch["current_message"] = message
                latch["current_code"] = code
                latch["recovered"] = False

            # Append per-error entry.
            entries = list(latch.get("errors") or [])
            entries.append(
                {
                    "message": message,
                    "code": code,
                    "captured_at": now,
                    "job_elapsed_seconds": elapsed,
                    "room_id": room_id,
                    "recovered_at": None,
                }
            )
            if len(entries) > _LATCH_ERRORS_LIMIT:
                entries = entries[-_LATCH_ERRORS_LIMIT:]
            latch["errors"] = entries
            latch["error_count"] = int(latch.get("error_count") or 0) + 1
            record["active_run_error"] = latch

        self._persist_and_notify(vacuum_entity_id)

    def _record_falling_edge(self, vacuum_entity_id: str) -> None:
        """Mark the most recent active_run_error entry as recovered.

        If there's no active-run latch (error_message cleared while no job is
        in flight, or after a harvest), this is a no-op for the active-run
        side. last_device_error stays as-is until acknowledged.
        """
        record = self._ensure_record(vacuum_entity_id)
        latch = record.get("active_run_error")
        if not isinstance(latch, dict):
            return

        now = _iso_now()
        latch["current_message"] = ""
        latch["current_code"] = None
        latch["recovered"] = True
        latch["last_seen_at"] = now

        # Stamp recovered_at on the most recent entry that doesn't have one.
        entries = list(latch.get("errors") or [])
        for entry in reversed(entries):
            if isinstance(entry, dict) and entry.get("recovered_at") is None:
                entry["recovered_at"] = now
                break
        latch["errors"] = entries

        record["active_run_error"] = latch
        self._persist_and_notify(vacuum_entity_id)

    # -- job-end harvest -----------------------------------------------------

    def harvest_active_run(
        self,
        vacuum_entity_id: str,
        job_id: str | None,
    ) -> dict[str, Any] | None:
        """Pull and clear the active-run latch when a job ends.

        Called by ``learning/job_finalizer.py`` right before ``outcome`` is
        constructed. The returned dict gets folded into ``extra_outcome``
        so the completed job carries the error history. After this returns,
        the active-run latch is null and the next rising edge while a fresh
        active job is in flight starts a new latch.

        Mismatched ``job_id`` (latch belongs to a previous job that wasn't
        harvested) returns the latch anyway — losing history is worse than
        attaching it to the wrong job.
        """
        record = self._ensure_record(vacuum_entity_id)
        latch = record.get("active_run_error")
        if latch is None:
            return None
        if (
            job_id is not None
            and latch.get("active_job_id") not in (None, job_id)
        ):
            _LOGGER.debug(
                "error_tracker: harvest job_id mismatch for %s "
                "(latch=%s, harvest=%s) — attaching anyway",
                vacuum_entity_id,
                latch.get("active_job_id"),
                job_id,
            )
        record["active_run_error"] = None
        self._persist_and_notify(vacuum_entity_id)
        return latch

    # -- service hooks -------------------------------------------------------

    def acknowledge(
        self,
        vacuum_entity_id: str,
        *,
        scope: str = "both",
    ) -> bool:
        """Clear the active-run / last-device latch(es). Returns True if a
        record existed for the vacuum, False otherwise."""
        root = self._root()
        if vacuum_entity_id not in root:
            return False
        record = self._ensure_record(vacuum_entity_id)
        scope_n = (scope or "both").strip().lower()
        if scope_n in ("active_run", "both"):
            record["active_run_error"] = None
        if scope_n in ("last_device", "both"):
            record["last_device_error"] = None
        self._persist_and_notify(vacuum_entity_id)
        return True

    # -- helpers -------------------------------------------------------------

    def _lookup_active_job(self, vacuum_entity_id: str) -> dict[str, Any] | None:
        """Return the in-flight active_job dict for this vacuum, if any.

        Mirrors BatteryHealthManager._has_active_job's traversal: walk the
        per-map active_jobs dict and return the first entry that has
        ``started_at`` and no ``ended_at``.
        """
        active_jobs = self._manager.data.get("active_jobs", {})
        per_map = active_jobs.get(vacuum_entity_id, {})
        if not isinstance(per_map, dict):
            return None
        for map_state in per_map.values():
            if not isinstance(map_state, dict):
                continue
            if map_state.get("started_at") and not map_state.get("ended_at"):
                return map_state
        return None

    @staticmethod
    def _extract_job_id(active_job: dict[str, Any] | None) -> str | None:
        if not isinstance(active_job, dict):
            return None
        job_id = active_job.get("job_id")
        return str(job_id) if job_id else None

    @staticmethod
    def _extract_current_room_id(
        active_job: dict[str, Any] | None,
    ) -> str | None:
        if not isinstance(active_job, dict):
            return None
        room_id = active_job.get("current_room_id")
        if room_id is None:
            return None
        return str(room_id)

    def _persist_and_notify(self, vacuum_entity_id: str) -> None:
        """Schedule a save and fan out the in-memory update notification."""
        # Storage save — fire-and-forget. async_save is an async def, so the
        # canonical pattern is async_create_task(coro). On a worker thread
        # we'd need run_coroutine_threadsafe, but state-change callbacks
        # always arrive on the loop, so async_create_task is correct here.
        try:
            self._hass.async_create_task(self._manager.async_save())
        except Exception:  # pragma: no cover - defensive
            _LOGGER.debug("error_tracker: storage save scheduling failed", exc_info=True)
        self._notify(vacuum_entity_id)
