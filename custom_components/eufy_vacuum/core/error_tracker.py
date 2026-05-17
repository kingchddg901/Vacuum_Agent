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

from ..adapters.registry import get_adapter_config

if TYPE_CHECKING:
    from .manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

# === TUNABLES ================================================================

# Generic not-error sentinel set — standard HA empty/unavailable states.
# Brand-specific sentinels come from adapter_config.vocabulary.not_error_sentinels.
# This is only the last-resort fallback when no adapter is registered.
_NOT_ERROR: frozenset[str] = frozenset({"", "unknown", "unavailable"})

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


def _is_error_value(
    value: Any,
    *,
    not_error: frozenset[str] = _NOT_ERROR,
) -> bool:
    """Return True if ``value`` looks like a real error string."""
    if value is None:
        return False
    text = str(value).strip().lower()
    return bool(text) and text not in not_error


def _get_not_error_set(vacuum_entity_id: str) -> frozenset[str]:
    """Return the not-error sentinel set for this vacuum.

    Reads from the adapter registry. Falls back to the generic HA sentinel
    set (_NOT_ERROR) when the adapter is not registered or has no vocabulary.
    Never raises.
    """
    try:
        config = get_adapter_config(vacuum_entity_id)
        sentinels = (config or {}).get("vocabulary", {}).get("not_error_sentinels")
        if sentinels:
            return frozenset(str(s).strip().lower() for s in sentinels)
    except Exception:
        pass
    return _NOT_ERROR


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
        # Per-vacuum entity ID map: vacuum_entity_id → {entity_key: entity_id}.
        # Populated by _wire_vacuum from the adapter registry. None values mean
        # the adapter did not declare that entity — the corresponding channel
        # is skipped rather than falling back to brand-specific naming conventions.
        self._vacuum_entities: dict[str, dict[str, str | None]] = {}

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
        self._vacuum_entities.clear()

    def _wire_vacuum(self, vacuum_entity_id: str) -> None:
        if vacuum_entity_id in self._vacuum_unsubs:
            return

        config = get_adapter_config(vacuum_entity_id)
        entities = (config or {}).get("entities", {})

        # Resolve entity IDs from the adapter registry only — no brand-specific fallbacks.
        # If the adapter did not declare an entity, that channel is simply absent.
        # Skipping silently is correct: the vacuum entity itself (always present)
        # is still wired, so the secondary-error path continues to function.
        error_message_entity: str | None = entities.get("error_message") or None
        task_status_entity: str | None = entities.get("task_status") or None

        # Store entity IDs so every subsequent method can look them up without
        # reconstructing them from object_id or calling the registry again.
        self._vacuum_entities[vacuum_entity_id] = {
            "error_message": error_message_entity,
            "task_status": task_status_entity,
        }

        self._source_to_vacuum[vacuum_entity_id] = vacuum_entity_id
        if error_message_entity:
            self._source_to_vacuum[error_message_entity] = vacuum_entity_id
        if task_status_entity:
            self._source_to_vacuum[task_status_entity] = vacuum_entity_id

        self._ensure_record(vacuum_entity_id)

        # Build the watch list from the entities that are actually declared.
        # vacuum_entity_id is always included (HA-standard secondary channel).
        watch_entities = [vacuum_entity_id]
        if error_message_entity:
            watch_entities.append(error_message_entity)
        if task_status_entity:
            watch_entities.append(task_status_entity)

        unsubs: list[Callable[[], None]] = []
        # Signal sources, each routed by entity_id in _on_state_event:
        # - error_message: primary; supplies the human-readable string and
        #   numeric code when upstream surfaces them
        # - vacuum.state: HA-derived; flips to "error" when upstream
        #   WorkStatus.state == 2
        # - task_status: parallel string signal that flips to "Error" on
        #   the same upstream condition. Empirical observation (real
        #   recorder trace, 2026-05-10): for stuck/trapped/etc events the
        #   firmware never populates error_message, so this channel +
        #   vacuum.state are the ONLY HA-visible indicators. Adding it
        #   defensively means we don't depend on either alone.
        unsubs.append(
            async_track_state_change_event(
                self._hass,
                watch_entities,
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
            # vacuum.<obj> state transition. HA-derived from the upstream
            # WorkStatus.state — flips to "error" when state == 2.
            self._handle_secondary_error_signal(vacuum_entity_id)
            return

        _ts_entity = self._vacuum_entities.get(vacuum_entity_id, {}).get("task_status")
        if _ts_entity and entity_id == _ts_entity:
            # task_status string transition. Parallel to vacuum.state — same
            # upstream condition (WorkStatus.state == 2 → "Error") routes
            # through this string sensor. Defensive secondary channel:
            # empirically, stuck-type events flip both vacuum.state and
            # task_status simultaneously while error_message stays empty,
            # so subscribing to both protects against edge cases where
            # one fires without the other.
            self._handle_secondary_error_signal(vacuum_entity_id)
            return

        # error_message sensor transition — the primary signal.
        self._handle_error_message_change(
            vacuum_entity_id, old_state, new_state
        )

    # -- secondary error signal handling -------------------------------------

    def _is_in_secondary_error(self, vacuum_entity_id: str) -> bool:
        """True if any secondary channel currently indicates an error state.

        Checks both vacuum.<obj> state and sensor.<obj>_task_status. Either
        one being in "error" / "Error" counts. Used to decide whether to
        schedule a grace window (any channel rising → schedule) and whether
        to cancel one (all channels back to normal → cancel).
        """
        vac = self._hass.states.get(vacuum_entity_id)
        if vac is not None and str(vac.state or "").strip().lower() == "error":
            return True
        _ts_entity = self._vacuum_entities.get(vacuum_entity_id, {}).get("task_status")
        if _ts_entity:
            ts = self._hass.states.get(_ts_entity)
            if ts is not None and str(ts.state or "").strip().lower() == "error":
                return True
        return False

    def _handle_secondary_error_signal(self, vacuum_entity_id: str) -> None:
        """Schedule or cancel the grace window based on combined channel state.

        Called by both the vacuum.state and task_status state-change events.
        Re-evaluates whether ANY secondary channel is currently in error and
        manages the grace timer accordingly:

        - At least one secondary channel in error AND no error_message yet
          → schedule grace timer (idempotent — only schedules once)
        - All secondary channels back to normal → cancel grace; if the
          active-run latch has an unrecovered entry AND error_message is
          still empty, emit a falling edge so recovered/recovered_at are
          set. Firmware that never populates error_message (e.g. brush-stuck
          events on some dock models) has no other clearing signal.
        - error_message already populated → no-op (message handler latches)
        """
        if not self._is_in_secondary_error(vacuum_entity_id):
            self._cancel_grace(vacuum_entity_id)
            # Secondary channels have both cleared. Emit a falling edge if:
            #   1. There is an active-run latch with recovered=False, AND
            #   2. error_message is NOT currently in an error state.
            # Condition 2 prevents double-firing when error_message IS
            # populated — in that case the primary channel (_handle_error_
            # message_change) owns the latch and will emit its own falling
            # edge when the message clears.
            record = self._ensure_record(vacuum_entity_id)
            latch = record.get("active_run_error")
            if isinstance(latch, dict) and not latch.get("recovered"):
                err_msg_entity = self._vacuum_entities.get(vacuum_entity_id, {}).get("error_message")
                msg_state = self._hass.states.get(err_msg_entity) if err_msg_entity else None
                msg_value = msg_state.state if msg_state is not None else None
                if not _is_error_value(
                    msg_value, not_error=_get_not_error_set(vacuum_entity_id)
                ):
                    self._record_falling_edge(vacuum_entity_id)
            return

        # Already in error state on at least one channel — schedule grace if
        # not already pending.
        if vacuum_entity_id in self._grace_cancels:
            return

        # If error_message is already populated, don't bother with the grace
        # window — the message handler will (or already did) latch.
        _err_msg_entity = self._vacuum_entities.get(vacuum_entity_id, {}).get("error_message")
        msg_state = self._hass.states.get(_err_msg_entity) if _err_msg_entity else None
        msg_value = msg_state.state if msg_state is not None else None
        if _is_error_value(msg_value, not_error=_get_not_error_set(vacuum_entity_id)):
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
        """Grace window elapsed — finalise as a generic placeholder latch.

        Re-checks both secondary channels (vacuum.state, task_status) at
        expiry. The vacuum may have left "error" on one channel and not the
        other in the 5 s since the timer was scheduled — if EITHER channel
        is still in error and error_message is still empty, we latch.
        """
        self._grace_cancels.pop(vacuum_entity_id, None)
        if not self._is_in_secondary_error(vacuum_entity_id):
            return
        # Re-check the message in case it arrived after the timer fired but
        # before this callback ran — the message handler would have already
        # latched in that case.
        config = get_adapter_config(vacuum_entity_id)
        error_config = (config or {}).get("error_tracking", {})

        unknown_message = (
            error_config.get("unknown_error_message")
            or "Unknown error during run"
        )

        _err_msg_entity = self._vacuum_entities.get(vacuum_entity_id, {}).get("error_message")
        msg_state = self._hass.states.get(_err_msg_entity) if _err_msg_entity else None
        msg_value = msg_state.state if msg_state is not None else None
        if _is_error_value(msg_value):
            return
        self._record_rising_edge(
            vacuum_entity_id,
            message=unknown_message,
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
        _not_error = _get_not_error_set(vacuum_entity_id)
        was_error = _is_error_value(old_state, not_error=_not_error)
        is_error = _is_error_value(new_state, not_error=_not_error)

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
        """Pull the upstream error_code attribute if the entity exposes one.

        Verified upstream surface (robovac_mqtt as of 2026-05): the code
        lives on the vacuum.<obj> entity's extra_state_attributes alongside
        the message — not on the sensor.<obj>_error_message sensor. We
        check both so a future upstream refactor that adds it to the
        sensor still works.

        Treats 0 as "no code captured" rather than "the upstream's literal
        zero". Reasoning: every per-model error_code proto in the upstream
        starts with E0000_NONE = 0, so upstream uses 0 as the sentinel for
        "no error". If we observe code=0 alongside a real error_message,
        the vacuum entity's attributes lagged the sensor state change —
        better to record None ("we don't know the code") than to claim
        zero, which has a different meaning in the upstream's vocabulary.
        """
        _err_msg_entity = self._vacuum_entities.get(vacuum_entity_id, {}).get("error_message")
        for entity_id in filter(None, (_err_msg_entity, vacuum_entity_id)):
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            attrs = getattr(state, "attributes", None) or {}
            for key in ("error_code", "code", "errorCode"):
                value = _safe_int(attrs.get(key))
                if value is not None and value != 0:
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
