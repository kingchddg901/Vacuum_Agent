"""Job finalization for the optional learning system.

Responsibilities:
1. save a live snapshot at job start
2. finalize a completed job from current integration state
3. persist completed-job JSON
4. rebuild learned stats
5. optionally rebuild CSV exports

Learning rule:
- all finalized jobs are archived to history
- only eligible completed jobs are used for learning
- cancelled / failed / interrupted / test jobs are excluded from learning
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..battery.job_metrics import compute_job_battery_metrics
from ..const import DATA_BATTERY, DOMAIN
from .utils import _iso_now, _safe_float, _safe_int
from .history_store import LearningHistoryStore
from .stats_rebuilder import LearningStatsRebuilder

_LOGGER = logging.getLogger(__name__)


def _parse_iso_to_utc(value: Any) -> datetime | None:
    """Tolerant ISO-8601 parser used for error-window arithmetic.

    Returns None on any parse failure so the caller can skip a malformed
    entry without affecting the rest of the calculation.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _compute_total_error_seconds(
    error_latch: dict[str, Any] | None,
    *,
    job_ended_at: str | None,
) -> int:
    """Sum the time the run spent inside an error state.

    Walks ``error_latch.errors[]`` chronologically and treats each entry as
    a half-open ``[captured_at, recovered_at)`` interval. Entries that
    never received a recovered_at (because the firmware re-fired before
    the previous error cleared, or because the job ended while still in
    error) are bounded by:

    1. The next entry's ``captured_at``, if there is one — the model only
       carries one "current" error at a time, so the next rising edge
       implicitly closes the previous window.
    2. Otherwise the job's ``ended_at``.

    Overlapping intervals are merged to keep us honest if a misbehaving
    firmware ever produces them despite the alternating-edge model.

    Returns int seconds, clamped to ≥ 0. The caller subtracts this from
    ``cleaning_time_seconds`` so a recoverable run isn't penalised for
    transient faults that the vacuum worked through — the run stays in
    the learning corpus rather than being marked excluded.
    """
    if not isinstance(error_latch, dict):
        return 0
    raw_entries = error_latch.get("errors") or []
    if not raw_entries:
        return 0

    fallback_end = _parse_iso_to_utc(job_ended_at) or datetime.now(timezone.utc)

    intervals: list[tuple[datetime, datetime]] = []
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            continue
        start = _parse_iso_to_utc(entry.get("captured_at"))
        if start is None:
            continue
        end = _parse_iso_to_utc(entry.get("recovered_at"))
        if end is None:
            # Implicit boundary: next entry's captured_at, else job end.
            for follow in raw_entries[index + 1:]:
                if isinstance(follow, dict):
                    end = _parse_iso_to_utc(follow.get("captured_at"))
                    if end is not None:
                        break
            if end is None:
                end = fallback_end
        if end <= start:
            continue
        intervals.append((start, end))

    if not intervals:
        return 0

    # Merge overlaps. Latch model alternates rising/falling so this should
    # be a no-op in normal operation, but defend against firmware quirks.
    intervals.sort(key=lambda iv: iv[0])
    merged: list[tuple[datetime, datetime]] = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    total = sum((end - start).total_seconds() for start, end in merged)
    return max(0, int(total))


def _apply_water_actuals(
    *,
    completed_job: dict[str, Any],
    end_percent: float | None,
    observed_mop_wash_count: int,
) -> None:
    """Enrich the water section of a completed job with end-of-run actuals.

    Splits total dock water used into mop-wash overhead vs floor mopping so
    the floor-only figure is clean for per-room analysis.
    """
    water = completed_job.get("water")
    if not isinstance(water, dict):
        return

    water["actual_end_station_clean_water_percent"] = end_percent
    water["actual_mop_wash_count"] = observed_mop_wash_count

    expected_wash_cycles = int(water.get("wash_cycle_count") or 0)
    water["unexpected_wash_cycles"] = observed_mop_wash_count > expected_wash_cycles

    start_percent = water.get("station_clean_water_percent")
    capacity_ml = water.get("dock_clean_tank_capacity_ml")
    overhead_per_cycle = water.get("dock_wash_overhead_ml_per_cycle") or 0.0

    if (
        end_percent is not None
        and isinstance(start_percent, (int, float))
        and isinstance(capacity_ml, (int, float))
        and capacity_ml > 0
        and start_percent >= end_percent
    ):
        actual_total_ml = round((start_percent - end_percent) / 100.0 * capacity_ml, 1)
        actual_mop_wash_ml = round(observed_mop_wash_count * overhead_per_cycle, 1)
        actual_floor_ml = round(max(actual_total_ml - actual_mop_wash_ml, 0.0), 1)
        estimated = water.get("estimated_total_dock_clean_water_used_ml") or 0

        water["actual_dock_water_used_ml"] = actual_total_ml
        water["actual_mop_wash_water_ml"] = actual_mop_wash_ml
        water["actual_floor_water_ml"] = actual_floor_ml
        water["actual_vs_estimated_delta_ml"] = round(actual_total_ml - estimated, 1)
    else:
        water["actual_dock_water_used_ml"] = None
        water["actual_mop_wash_water_ml"] = None
        water["actual_floor_water_ml"] = None
        water["actual_vs_estimated_delta_ml"] = None


class LearningJobFinalizer:
    """Finalize learning jobs from integration state."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = LearningHistoryStore(hass)
        self.rebuilder = LearningStatsRebuilder(hass)
        self._live_snapshot_cache: dict[str, dict[str, Any]] = {}

    def build_live_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        queue_state: dict[str, Any],
        payload_state: dict[str, Any],
        active_job_state: dict[str, Any],
        capabilities: dict[str, Any] | None = None,
        planned_job_estimate: dict[str, Any] | None = None,
        access_graph_context: dict[str, Any] | None = None,
        started_at: str | None = None,
        battery_start: int | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the live job snapshot payload.

        The active job state is the frozen source of truth captured at start.
        Queue and payload getters may already have drifted by the time the
        snapshot is written, so top-level snapshot mirrors must prefer the
        active job branch and only fall back to queue/payload state when needed.
        """
        active_job = active_job_state if isinstance(active_job_state, dict) else {}
        queue_live = queue_state if isinstance(queue_state, dict) else {}
        payload_live = payload_state if isinstance(payload_state, dict) else {}

        queue_room_ids = active_job.get("queue_room_ids", [])
        if not isinstance(queue_room_ids, list):
            queue_room_ids = []

        queue_rooms = active_job.get("queue_rooms", [])
        if not isinstance(queue_rooms, list) or not queue_rooms:
            queue_rooms = queue_live.get("queue_rooms", []) if isinstance(queue_live.get("queue_rooms", []), list) else []

        payload = active_job.get("payload", {})
        if not isinstance(payload, dict) or not payload:
            payload = payload_live.get("payload", {}) if isinstance(payload_live.get("payload", {}), dict) else {}

        resolved_rooms = active_job.get("resolved_rooms", [])
        if not isinstance(resolved_rooms, list) or not resolved_rooms:
            resolved_rooms = payload_live.get("resolved_rooms", []) if isinstance(payload_live.get("resolved_rooms", []), list) else []

        room_count = _safe_int(active_job.get("room_count"), len(resolved_rooms) or len(queue_rooms))
        if room_count <= 0:
            room_count = len(resolved_rooms) or len(queue_rooms)

        job_metadata = active_job.get("job_metadata", {}) if isinstance(active_job.get("job_metadata"), dict) else {}
        room_slugs = job_metadata.get("room_slugs", []) if isinstance(job_metadata.get("room_slugs", []), list) else []
        if not room_slugs:
            source_rooms = resolved_rooms if resolved_rooms else queue_rooms
            room_slugs = [
                str(room.get("slug", "")).strip().lower()
                for room in source_rooms
                if isinstance(room, dict) and str(room.get("slug", "")).strip()
            ]

        queue_snapshot = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(active_job.get("map_id") or map_id),
            "room_count": room_count,
            "queue_room_ids": queue_room_ids,
            "queue_rooms": queue_rooms,
        }

        if not queue_room_ids and isinstance(queue_live.get("queue_room_ids"), list):
            queue_snapshot["queue_room_ids"] = list(queue_live.get("queue_room_ids", []))
        if (not queue_snapshot["queue_rooms"]) and isinstance(queue_live.get("queue_rooms"), list):
            queue_snapshot["queue_rooms"] = list(queue_live.get("queue_rooms", []))
        if queue_snapshot["room_count"] <= 0:
            queue_snapshot["room_count"] = _safe_int(queue_live.get("room_count"), 0)

        return {
            "schema_version": 1,
            "snapshot_type": "job_start",
            "job_id": job_id or str(active_job.get("job_id") or f"job_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"),
            "vacuum": {
                "entity_id": vacuum_entity_id,
                "name": vacuum_entity_id.split(".", 1)[1],
            },
            "timestamps": {
                "started_at": started_at or str(active_job.get("started_at") or _iso_now()),
            },
            "battery": {
                "start_percent": _safe_int(
                    active_job.get("battery_start", battery_start),
                    _safe_int(battery_start, 0),
                ),
            },
            "queue": queue_snapshot,
            "payload": payload,
            "resolved_rooms": resolved_rooms,
            "active_job": active_job,
            "capabilities": capabilities if isinstance(capabilities, dict) else {},
            "planned_job_estimate": (
                planned_job_estimate if isinstance(planned_job_estimate, dict) else {}
            ),
            "access_graph_context": (
                access_graph_context if isinstance(access_graph_context, dict) else {}
            ),
            "job_profile": {
                "map_id": _safe_int(job_metadata.get("map_id"), _safe_int(map_id, 0)),
                "room_count": _safe_int(job_metadata.get("room_count"), room_count),
                "room_slugs": room_slugs,
                "rooms": resolved_rooms,
            },
        }

    def save_live_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        queue_state: dict[str, Any],
        payload_state: dict[str, Any],
        active_job_state: dict[str, Any],
        capabilities: dict[str, Any] | None = None,
        planned_job_estimate: dict[str, Any] | None = None,
        access_graph_context: dict[str, Any] | None = None,
        started_at: str | None = None,
        battery_start: int | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Save the live learning snapshot for a running job.

        This method is intentionally non-blocking from the event loop. It updates
        the in-memory snapshot cache immediately, then schedules the filesystem
        write in Home Assistant's executor.
        """
        snapshot = self.build_live_snapshot(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            queue_state=queue_state,
            payload_state=payload_state,
            active_job_state=active_job_state,
            capabilities=capabilities,
            planned_job_estimate=planned_job_estimate,
            access_graph_context=access_graph_context,
            started_at=started_at,
            battery_start=battery_start,
            job_id=job_id,
        )
        self._live_snapshot_cache[vacuum_entity_id] = snapshot
        path = self.store.get_live_snapshot_path(vacuum_entity_id=vacuum_entity_id)

        async def _write_snapshot() -> None:
            try:
                await self.hass.async_add_executor_job(
                    lambda: self.store.save_live_snapshot(
                        vacuum_entity_id=vacuum_entity_id,
                        snapshot=snapshot,
                    )
                )
            except Exception:  # pragma: no cover - best-effort snapshot persist
                _LOGGER.exception(
                    "Failed to persist live learning snapshot for %s",
                    vacuum_entity_id,
                )

        self.hass.loop.call_soon_threadsafe(self.hass.async_create_task, _write_snapshot())

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "job_id": snapshot["job_id"],
            "path": str(path),
            "snapshot": snapshot,
        }

    def _collect_finalization_inputs(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        battery_start: int,
        started_at: str,
        ended_at: str,
        forced_outcome_status: str | None,
        forced_lifecycle_state: str | None,
        forced_lifecycle_message: str | None,
    ) -> dict[str, Any]:
        """Collect all event-loop-dependent state needed for finalization.

        Returns a frozen inputs dict that can be passed to finalize_from_inputs().
        Must run on the event loop (calls manager methods that read HA states).
        Does not perform heavy file I/O — only loads the tiny live snapshot from
        cache or disk (cold path only).
        """
        snapshot = self._live_snapshot_cache.get(vacuum_entity_id)
        if not isinstance(snapshot, dict):
            snapshot = self.store.load_live_snapshot(vacuum_entity_id=vacuum_entity_id)
            if isinstance(snapshot, dict):
                self._live_snapshot_cache[vacuum_entity_id] = snapshot

        queue_state = manager.get_queue_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        payload_state = manager.get_payload_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        active_job_state = manager.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        job_id = None
        if isinstance(snapshot, dict):
            job_id = str(snapshot.get("job_id", "")).strip() or None
        if not job_id:
            job_id = f"job_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"

        # Lifecycle name and message are derived from the caller-supplied
        # forced values for non-completed outcomes (cancellation, failure,
        # interruption). For normal completions forced_lifecycle_state is
        # None, and we set "completed" directly.
        #
        # Previously this called get_lifecycle_state() which reads 5 live
        # HA entities (vacuum.state, task_status, dock_status, etc.) and
        # returns the vacuum's *current* readiness — "ready", "mid_job_service",
        # etc. None of those values map to cancelled/failed/interrupted, so
        # they all fell through to outcome_status="completed" anyway. The call
        # added no classification value for normal completions, introduced a
        # live read at finalization time, and produced a stale or misleading
        # lifecycle_message (already suppressed by a separate guard). Removed.
        if forced_lifecycle_state is not None:
            lifecycle_name = str(forced_lifecycle_state).strip().lower()
            lifecycle_message = str(forced_lifecycle_message or "").strip()
        else:
            lifecycle_name = "completed"
            lifecycle_message = str(forced_lifecycle_message or "").strip()

        was_cancelled = lifecycle_name in {"cancelled", "canceled", "user_cancelled", "job_cancelled"}
        was_failed = lifecycle_name in {"failed", "error", "job_failed"}
        was_interrupted = lifecycle_name in {"interrupted", "stopped", "aborted"}

        outcome_status = str(forced_outcome_status or "completed").strip().lower() or "completed"
        if forced_outcome_status is None:
            if was_cancelled:
                outcome_status = "cancelled"
            elif was_failed:
                outcome_status = "failed"
            elif was_interrupted:
                outcome_status = "interrupted"

        cancel_detection: dict[str, Any] | None = None
        if forced_outcome_status is None and outcome_status == "completed":
            cancel_detection = self._detect_cancel_likely_run(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                battery_start=battery_start,
                started_at=started_at,
                ended_at=ended_at,
                active_job_state=active_job_state,
            )
            if cancel_detection.get("cancel_likely"):
                outcome_status = "cancelled"
                was_cancelled = True
                lifecycle_name = "cancel_likely"
                lifecycle_message = str(
                    cancel_detection.get("message")
                    or "Job returned unusually early and looks like a manual cancellation."
                )

        # Prefer values pushed into active_job_state by the job-metrics
        # listener during the run. These are written on every DPS update so
        # they reflect the last value seen before finalization fired, with no
        # race against the task_status "Completed" packet ordering.
        # Fall back to a live sensor read for the first run after a cold
        # start (listener not yet fired), then to wall-clock derivation.
        _job_state_for_metrics = active_job_state if isinstance(active_job_state, dict) else {}
        cleaning_time_seconds: int | None = _safe_int(
            _job_state_for_metrics.get("last_cleaning_time_seconds"), None
        )
        cleaning_area_m2: float | None = _safe_float(
            _job_state_for_metrics.get("last_cleaning_area_m2"), None
        )
        water_end_station_percent: float | None = _safe_float(
            _job_state_for_metrics.get("last_station_water_percent"), None
        )

        if cleaning_time_seconds is None or cleaning_area_m2 is None or water_end_station_percent is None:
            # Sensor fallback — covers the first run on a fresh install
            # before the metrics listener has had a chance to push values.
            try:
                _adapter_entities = (
                    _get_adapter_config(vacuum_entity_id) or {}
                ).get("entities", {})
                if cleaning_time_seconds is None:
                    _ct_entity = _adapter_entities.get("cleaning_time")
                    if _ct_entity:
                        ct_state = manager.hass.states.get(_ct_entity)
                        if ct_state and ct_state.state not in ("unavailable", "unknown"):
                            cleaning_time_seconds = _safe_int(ct_state.state, None)
                if cleaning_area_m2 is None:
                    _ca_entity = _adapter_entities.get("cleaning_area")
                    if _ca_entity:
                        ca_state = manager.hass.states.get(_ca_entity)
                        if ca_state and ca_state.state not in ("unavailable", "unknown"):
                            cleaning_area_m2 = _safe_float(ca_state.state, None)
                if water_end_station_percent is None:
                    water_end_station_percent = manager._get_station_clean_water_percent(
                        vacuum_entity_id=vacuum_entity_id,
                    )
            except Exception:  # pragma: no cover - best-effort station-water read
                pass

        if cleaning_time_seconds is None:
            # Sensor was unavailable or unknown at finalization time. This is
            # common on normal completions — the cleaning_time DPS update from
            # the firmware often arrives in a packet after the task_status
            # "Completed" packet that triggers finalization, so the HA state
            # is still showing the previous (stale or unavailable) value.
            #
            # Fall back to a wall-clock derivation: job wall time minus the
            # paused and mid-job recharge seconds tracked in the active job.
            # Not as precise as the upstream sensor (which also excludes small
            # dock manoeuvring delays), but far better than None, which would
            # cause the error-time subtraction to be silently skipped.
            try:
                _job_state = active_job_state if isinstance(active_job_state, dict) else {}
                _started_str = str(_job_state.get("started_at", "")).strip()
                _paused_secs = _safe_int(_job_state.get("paused_duration_seconds"), 0) or 0
                _recharge_secs = _safe_int(_job_state.get("recharge_seconds_accumulated"), 0) or 0
                if _started_str and ended_at:
                    _s_dt = datetime.fromisoformat(_started_str.replace("Z", "+00:00"))
                    _e_dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                    _wall = int((_e_dt - _s_dt).total_seconds())
                    _derived = max(0, _wall - _paused_secs - _recharge_secs)
                    if _derived > 0:
                        cleaning_time_seconds = _derived
                        _LOGGER.debug(
                            "job_finalizer: cleaning_time sensor unavailable for %s — "
                            "derived %ds from wall-clock (wall=%ds paused=%ds recharge=%ds)",
                            vacuum_entity_id,
                            _derived,
                            _wall,
                            _paused_secs,
                            _recharge_secs,
                        )
            except Exception:
                _LOGGER.debug(
                    "job_finalizer: wall-clock cleaning_time derivation failed for %s",
                    vacuum_entity_id,
                    exc_info=True,
                )

        return {
            "snapshot": snapshot,
            "queue_state": queue_state,
            "payload_state": payload_state,
            "active_job_state": active_job_state,
            "job_id": job_id,
            "lifecycle_name": lifecycle_name,
            "lifecycle_message": lifecycle_message,
            "outcome_status": outcome_status,
            "was_cancelled": was_cancelled,
            "was_failed": was_failed,
            "was_interrupted": was_interrupted,
            "cancel_detection": cancel_detection,
            "water_end_station_percent": water_end_station_percent,
            "cleaning_time_seconds": cleaning_time_seconds,
            "cleaning_area_m2": cleaning_area_m2,
        }

    def finalize_from_inputs(
        self,
        *,
        inputs: dict[str, Any],
        vacuum_entity_id: str,
        map_id: str,
        battery_start: int,
        battery_end: int,
        started_at: str,
        ended_at: str,
        used_for_learning: bool = True,
        rebuild_stats: bool = True,
        rebuild_csv: bool = False,
    ) -> dict[str, Any]:
        """Pure computation + file I/O from pre-collected inputs.

        Safe to run in a thread executor — no event loop access.
        Pre-collected inputs come from _collect_finalization_inputs().
        """
        snapshot = inputs["snapshot"]
        queue_state = inputs["queue_state"]
        payload_state = inputs["payload_state"]
        active_job_state = inputs["active_job_state"]
        job_id = inputs["job_id"]
        lifecycle_name = inputs["lifecycle_name"]
        lifecycle_message = inputs["lifecycle_message"]
        outcome_status = inputs["outcome_status"]
        was_cancelled = inputs["was_cancelled"]
        was_failed = inputs["was_failed"]
        was_interrupted = inputs["was_interrupted"]
        cancel_detection = inputs["cancel_detection"]

        # For completed jobs the timing-based room rollover may not have fired
        # for the last room before finalization ran — there is no "next room"
        # event to trigger it. A successful completion means all queued rooms
        # were cleaned by definition, so synthesize the full list from the
        # queue rather than relying on the accumulation state.
        # For non-completed jobs (cancelled/failed/interrupted) we use the
        # tracked state as-is — it reflects what was actually observed.
        if outcome_status == "completed" and isinstance(active_job_state, dict):
            _queued_ids = [
                _safe_int(r, -1)
                for r in (queue_state or {}).get("queue_room_ids", [])
                if _safe_int(r, -1) > 0
            ]
            if _queued_ids:
                # Shallow copy so we don't mutate the stored active_job_state.
                active_job_state = dict(active_job_state)
                active_job_state["completed_room_ids"] = _queued_ids

        # Harvest the active-run error latch from ErrorTracker. This pulls
        # the latch dict and nulls it on the tracker side, so the latch
        # state is owned by exactly one record after this call (the
        # completed-job outcome). If no errors fired during the run, the
        # harvest returns None and the outcome reflects had_errors=False.
        # Defensive: if the tracker isn't loaded for any reason, fall back
        # to no-error.
        from ..const import DATA_ERROR_TRACKER as _DATA_ERROR_TRACKER

        error_latch: dict[str, Any] | None = None
        try:
            error_tracker = (
                self.hass.data.get(DOMAIN, {}).get(_DATA_ERROR_TRACKER)
                if hasattr(self, "hass") and self.hass is not None
                else None
            )
            if error_tracker is not None:
                error_latch = error_tracker.harvest_active_run(
                    vacuum_entity_id, job_id
                )
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception(
                "job_finalizer: error_tracker harvest failed for %s",
                vacuum_entity_id,
            )

        had_errors = bool(
            isinstance(error_latch, dict)
            and (error_latch.get("error_count") or 0) > 0
        )
        error_count = (
            int(error_latch.get("error_count") or 0)
            if isinstance(error_latch, dict)
            else 0
        )

        # Total seconds the run spent in error state. Subtracted from the
        # upstream-reported cleaning_time_seconds below so a recoverable
        # run isn't penalised for transient faults — the job stays in the
        # learning corpus, just with a more accurate "active cleaning"
        # duration. raw and adjusted values are both stored on the job
        # record so downstream tooling can show "X minutes deducted".
        total_error_seconds = _compute_total_error_seconds(
            error_latch, job_ended_at=ended_at,
        )

        raw_cleaning_seconds = inputs.get("cleaning_time_seconds")
        adjusted_cleaning_seconds = raw_cleaning_seconds
        if (
            raw_cleaning_seconds is not None
            and total_error_seconds > 0
        ):
            adjusted_cleaning_seconds = max(
                0, int(raw_cleaning_seconds) - total_error_seconds
            )
            if total_error_seconds > int(raw_cleaning_seconds):
                # Defensive log: error window exceeded the upstream cleaning
                # time. Probably overlapping rising edges or clock skew.
                # Clamped to 0; record both values so the discrepancy is
                # visible in audit.
                _LOGGER.debug(
                    "job_finalizer: total_error_seconds (%d) > "
                    "cleaning_time_seconds (%d) for %s/%s; clamping to 0",
                    total_error_seconds,
                    int(raw_cleaning_seconds),
                    vacuum_entity_id,
                    job_id,
                )

        completed_job = self.store.build_completed_job_payload(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
            started_at=started_at,
            ended_at=ended_at,
            battery_start=battery_start,
            battery_end=battery_end,
            queue_state=queue_state,
            payload_state=payload_state,
            active_job_state=active_job_state,
            used_for_learning=used_for_learning,
            outcome_status=outcome_status,
            was_cancelled=was_cancelled,
            was_failed=was_failed,
            was_interrupted=was_interrupted,
            is_test_job=False,
            extra_outcome={
                "lifecycle_state": lifecycle_name,
                "lifecycle_message": lifecycle_message,
                "cancel_detection": cancel_detection or {"cancel_likely": False},
                # Error tracking — had_errors is the quick filter; errors
                # carries the full latch (errors[], current_*, recovered,
                # first_seen_*) for review-tab analysis.
                # total_error_seconds: how much wall-clock the run spent in
                # error state; cleaning_time_seconds on the job dict has
                # already been adjusted (see below).
                "had_errors": had_errors,
                "error_count": error_count,
                "errors": error_latch,
                "total_error_seconds": total_error_seconds,
            },
        )
        self._apply_snapshot_estimates_to_completed_job(
            completed_job=completed_job,
            snapshot=snapshot,
        )
        _apply_water_actuals(
            completed_job=completed_job,
            end_percent=inputs.get("water_end_station_percent"),
            observed_mop_wash_count=_safe_int(
                active_job_state.get("observed_mop_wash_count") if isinstance(active_job_state, dict) else None,
                0,
            ),
        )
        _job = completed_job.get("job")
        if isinstance(_job, dict):
            # Apply error-time-adjusted cleaning_time_seconds when an error
            # window was observed. cleaning_time_seconds_raw preserves the
            # upstream value so analysis can recompute or verify.
            if adjusted_cleaning_seconds is not None:
                _job["cleaning_time_seconds"] = adjusted_cleaning_seconds
                if (
                    raw_cleaning_seconds is not None
                    and total_error_seconds > 0
                ):
                    _job["cleaning_time_seconds_raw"] = int(raw_cleaning_seconds)
                    _job["total_error_seconds"] = total_error_seconds
            if inputs.get("cleaning_area_m2") is not None:
                _job["cleaning_area_m2"] = inputs["cleaning_area_m2"]

            # Battery metrics — drain rates + per-mode/suction/water rollup.
            # Only single-bucket jobs (every room same setting) feed per-bucket
            # aggregates downstream; mixed runs still get full job-level stats.
            try:
                # `resolved_rooms` lives at the TOP LEVEL of completed_job
                # (build_completed_job_payload promotes it there), not inside
                # the inner "job" dict. Earlier versions of this hook looked
                # inside _job and got an empty list, which forced
                # weighted_by="none" and empty per-bucket maps even on
                # genuinely single-room runs.
                resolved_rooms = completed_job.get("resolved_rooms")
                if not isinstance(resolved_rooms, list) or not resolved_rooms:
                    resolved_rooms = _job.get("resolved_rooms")
                if not isinstance(resolved_rooms, list) or not resolved_rooms:
                    resolved_rooms = (
                        payload_state.get("resolved_rooms")
                        if isinstance(payload_state, dict)
                        else []
                    )
                battery_metrics = compute_job_battery_metrics(
                    battery_start=battery_start,
                    battery_end=battery_end,
                    duration_minutes=_job.get("duration_minutes"),
                    cleaning_area_m2=inputs.get("cleaning_area_m2"),
                    resolved_rooms=resolved_rooms or [],
                )
                _job["battery_metrics"] = battery_metrics

                # Push to BatteryHealthManager so sensors and aggregates update.
                # Skipped on cancelled/failed/test runs — those drains are not
                # representative of normal cleaning.
                outcome = completed_job.get("outcome", {}) or {}
                outcome_status = str(outcome.get("status", "")).lower()
                if outcome_status in {"completed", "interrupted"} and outcome.get("used_for_learning", True):
                    battery_manager = self.hass.data.get(DOMAIN, {}).get(DATA_BATTERY)
                    if battery_manager is not None:
                        battery_manager.record_job_metrics(
                            vacuum_entity_id=vacuum_entity_id,
                            metrics=battery_metrics,
                            job_id=job_id,
                        )
            except Exception:  # pragma: no cover - best-effort metrics record
                _LOGGER.exception("battery: failed to compute job metrics")

        completed_job["learning_context"] = self._build_learning_context(
            completed_job=completed_job,
            snapshot=snapshot,
        )

        trace_run_id = None
        if isinstance(active_job_state, dict):
            trace_run_id = active_job_state.get("trace_run_id") or None
        if trace_run_id:
            completed_job["trace_run_id"] = str(trace_run_id)

        job_path = self.store.save_completed_job(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
            payload=completed_job,
        )

        incomplete_run_log = self._write_incomplete_run_log(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            completed_job=completed_job,
            active_job_state=active_job_state,
            ended_at=ended_at,
        )

        self._update_trouble_rooms_log(
            vacuum_entity_id=vacuum_entity_id,
            completed_job=completed_job,
            active_job_state=active_job_state,
            ended_at=ended_at,
        )

        stats_result: dict[str, Any] | None = None
        csv_result: dict[str, Any] | None = None

        if rebuild_stats:
            stats_result = self.rebuilder.rebuild_all(
                vacuum_entity_id=vacuum_entity_id,
                rebuild_csv=rebuild_csv,
            )
            if rebuild_csv:
                csv_result = stats_result.get("csv")

        boundary_result = self._auto_derive_room_boundary(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            completed_job=completed_job,
            was_cancelled=was_cancelled,
            trace_run_id=trace_run_id,
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "job_id": job_id,
            "job_path": str(job_path),
            "completed_job": completed_job,
            "incomplete_run_log": incomplete_run_log,
            "stats": stats_result,
            "csv": csv_result,
            "boundary_derivation": boundary_result,
        }

    def finalize_from_manager_state(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        battery_start: int,
        battery_end: int,
        started_at: str,
        ended_at: str | None = None,
        used_for_learning: bool = True,
        rebuild_stats: bool = True,
        rebuild_csv: bool = False,
        forced_outcome_status: str | None = None,
        forced_lifecycle_state: str | None = None,
        forced_lifecycle_message: str | None = None,
    ) -> dict[str, Any]:
        """Finalize a completed job using the integration manager as source of truth.

        Synchronous entry point that combines input collection and I/O.
        For async callers use finalize_learning_for_active_job() on the manager,
        which offloads file I/O to an executor.
        """
        ended_at = ended_at or _iso_now()
        inputs = self._collect_finalization_inputs(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            battery_start=battery_start,
            started_at=started_at,
            ended_at=ended_at,
            forced_outcome_status=forced_outcome_status,
            forced_lifecycle_state=forced_lifecycle_state,
            forced_lifecycle_message=forced_lifecycle_message,
        )
        return self.finalize_from_inputs(
            inputs=inputs,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            battery_start=battery_start,
            battery_end=battery_end,
            started_at=started_at,
            ended_at=ended_at,
            used_for_learning=used_for_learning,
            rebuild_stats=rebuild_stats,
            rebuild_csv=rebuild_csv,
        )

    def _apply_snapshot_estimates_to_completed_job(
        self,
        *,
        completed_job: dict[str, Any],
        snapshot: dict[str, Any] | None,
    ) -> None:
        """Attach start-of-run estimate data onto finalized rooms when available."""
        if not isinstance(snapshot, dict) or not isinstance(completed_job, dict):
            return

        planned = snapshot.get("planned_job_estimate", {})
        if not isinstance(planned, dict):
            return

        timeline = planned.get("room_timeline", [])
        if not isinstance(timeline, list) or not timeline:
            return

        timeline_by_room_id: dict[int, dict[str, Any]] = {}
        timeline_by_slug: dict[str, dict[str, Any]] = {}
        for entry in timeline:
            if not isinstance(entry, dict):
                continue
            room_id = _safe_int(entry.get("room_id", -1), -1)
            slug = str(entry.get("slug", "")).strip().lower()
            if room_id >= 0:
                timeline_by_room_id[room_id] = entry
            if slug:
                timeline_by_slug[slug] = entry

        resolved_rooms = completed_job.get("resolved_rooms", [])
        if not isinstance(resolved_rooms, list):
            return

        enriched_rooms: list[dict[str, Any]] = []
        for room in resolved_rooms:
            if not isinstance(room, dict):
                enriched_rooms.append(room)
                continue
            room_id = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            slug = str(room.get("slug", "")).strip().lower()
            timeline_entry = timeline_by_room_id.get(room_id) if room_id >= 0 else None
            if timeline_entry is None and slug:
                timeline_entry = timeline_by_slug.get(slug)

            if not isinstance(timeline_entry, dict):
                enriched_rooms.append(room)
                continue

            enriched_rooms.append(
                {
                    **room,
                    "estimated_minutes": round(
                        _safe_float(timeline_entry.get("minutes"), 0.0),
                        2,
                    ),
                    "estimated_battery": round(
                        _safe_float(timeline_entry.get("battery"), 0.0),
                        2,
                    ),
                    "estimate_confidence_score": round(
                        _safe_float(timeline_entry.get("confidence_score"), 0.0),
                        4,
                    ),
                    "estimate_confidence_label": str(
                        timeline_entry.get("confidence_label", "")
                    ).strip()
                    or None,
                    "estimate_source": str(
                        timeline_entry.get("source", "")
                    ).strip()
                    or None,
                }
            )

        completed_job["resolved_rooms"] = enriched_rooms
        job_profile = completed_job.get("job_profile", {})
        if isinstance(job_profile, dict):
            job_profile["rooms"] = enriched_rooms

    def _build_learning_context(
        self,
        *,
        completed_job: dict[str, Any],
        snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build queue-shape and estimate-delta metadata for the completed job record."""
        job_info = completed_job.get("job", {}) if isinstance(completed_job, dict) else {}
        actual_job_minutes = _safe_float(
            job_info.get("duration_minutes") if isinstance(job_info, dict) else None,
            0.0,
        )
        battery_info = completed_job.get("battery", {}) if isinstance(completed_job, dict) else {}
        actual_battery_used = _safe_float(
            battery_info.get("used") if isinstance(battery_info, dict) else None,
            0.0,
        )

        planned = snapshot.get("planned_job_estimate", {}) if isinstance(snapshot, dict) else {}
        if not isinstance(planned, dict):
            planned = {}

        room_ids = list(completed_job.get("queue", {}).get("queue_room_ids", []))
        room_slugs = list(completed_job.get("job_profile", {}).get("room_slugs", []))
        resolved_rooms = completed_job.get("resolved_rooms", [])
        room_modes: list[str] = []
        if isinstance(resolved_rooms, list):
            for room in resolved_rooms:
                if isinstance(room, dict):
                    room_modes.append(str(room.get("clean_mode", "")).strip().lower() or "unknown")

        queue_shape_key = (
            f"map:{completed_job.get('job_profile', {}).get('map_id', 0)}"
            f"|count:{len(room_ids)}"
            f"|rooms:{','.join(str(room_id) for room_id in room_ids)}"
            f"|modes:{','.join(room_modes)}"
        )

        estimated_room_minutes_total = _safe_float(planned.get("room_minutes_total"), 0.0)
        estimated_overhead_minutes = _safe_float(planned.get("overhead_minutes"), 0.0)
        estimated_total_minutes = _safe_float(planned.get("total_minutes"), 0.0)
        total_delta = (
            round(actual_job_minutes - estimated_total_minutes, 2)
            if estimated_total_minutes > 0
            else None
        )
        total_delta_ratio = (
            round((actual_job_minutes - estimated_total_minutes) / estimated_total_minutes, 4)
            if estimated_total_minutes > 0
            else None
        )

        access_graph_context = (
            snapshot.get("access_graph_context", {}) if isinstance(snapshot, dict) else {}
        )
        if not isinstance(access_graph_context, dict):
            access_graph_context = {}

        return {
            "schema_version": 1,
            "queue_shape": {
                "key": queue_shape_key,
                "room_ids": room_ids,
                "room_slugs": room_slugs,
                "room_modes": room_modes,
                "room_count": len(room_ids),
            },
            "estimate_snapshot": {
                "available": bool(planned),
                "estimated_room_minutes_total": round(estimated_room_minutes_total, 2),
                "estimated_overhead_minutes": round(estimated_overhead_minutes, 2),
                "estimated_total_minutes": round(estimated_total_minutes, 2),
                "estimated_total_battery_used": round(
                    _safe_float(planned.get("total_battery_used"), 0.0), 2
                ),
                "job_confidence_score": round(
                    _safe_float(planned.get("confidence_score"), 0.0), 4
                ),
                "job_confidence_label": str(
                    planned.get("confidence_label", "")
                ).strip()
                or None,
            },
            "actuals": {
                "actual_job_minutes": round(actual_job_minutes, 2),
                "actual_battery_used": round(actual_battery_used, 2),
            },
            "estimate_delta": {
                "total_minutes_delta": total_delta,
                "total_minutes_delta_ratio": total_delta_ratio,
            },
            "access_graph": {
                "present": bool(access_graph_context.get("present", False)),
                "edge_count": _safe_int(access_graph_context.get("edge_count"), 0),
                "pair_count": _safe_int(access_graph_context.get("pair_count"), 0),
                "graph_transition_count": _safe_int(
                    access_graph_context.get("graph_transition_count"), 0
                ),
                "graph_jump_count": _safe_int(
                    access_graph_context.get("graph_jump_count"), 0
                ),
                "graph_coherence_score": (
                    round(
                        _safe_float(access_graph_context.get("graph_coherence_score"), 0.0),
                        4,
                    )
                    if access_graph_context.get("graph_coherence_score") is not None
                    else None
                ),
            },
        }

    def _detect_cancel_likely_run(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        battery_start: int,
        started_at: str,
        ended_at: str,
        active_job_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Return whether a very short return path looks like a manual cancel."""
        started_dt = self.store._parse_timestamp(started_at)
        ended_dt = self.store._parse_timestamp(ended_at)
        if started_dt is None or ended_dt is None:
            return {"cancel_likely": False, "reason": "missing_timestamps"}

        duration_minutes = max((ended_dt - started_dt).total_seconds() / 60.0, 0.0)
        resolved_rooms = active_job_state.get("resolved_rooms", [])
        if not isinstance(resolved_rooms, list) or len(resolved_rooms) != 1:
            return {"cancel_likely": False, "reason": "not_single_room"}

        transitions = [
            dict(entry)
            for entry in active_job_state.get("state_transitions", [])
            if isinstance(entry, dict)
        ]
        if not transitions:
            return {"cancel_likely": False, "reason": "no_transition_history"}

        transition_pairs = [
            (
                str(entry.get("entity_id", "")).strip(),
                str(entry.get("from_state", "")).strip().lower(),
                str(entry.get("to_state", "")).strip().lower(),
            )
            for entry in transitions
        ]

        # Resolve the task_status entity ID from the adapter registry so we
        # match by full entity ID, not by brand-specific suffix.
        _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        _task_status_entity = _adapter_cfg.get("entities", {}).get("task_status", "")
        if not _task_status_entity:
            return {"cancel_likely": False, "reason": "no_task_status_entity"}

        # Read cancel service exclusion states from adapter vocabulary.
        # These are normalized task_status strings that explain an early return
        # as a service event (low-battery, mop wash, dust empty) rather than
        # a manual cancel. Fall back to an empty set — no false negatives are
        # worse than no exclusion; callers should register vocab if they want it.
        _exclusion_vocab = _adapter_cfg.get("vocabulary", {}).get(
            "cancel_service_exclusion_states", []
        )
        service_exclusion_states: frozenset[str] = frozenset(
            str(s).strip().lower() for s in _exclusion_vocab if s
        )

        if any(to_state in service_exclusion_states for _, _, to_state in transition_pairs):
            return {"cancel_likely": False, "reason": "service_state_explains_return"}

        direct_returning = any(
            entity_id == _task_status_entity and from_state == "cleaning" and to_state == "returning"
            for entity_id, from_state, to_state in transition_pairs
        )
        paused_then_returning = False
        recent_task_states = [
            to_state
            for entity_id, _, to_state in transition_pairs
            if entity_id == _task_status_entity
        ]
        for idx in range(len(recent_task_states) - 1):
            if recent_task_states[idx] == "paused" and recent_task_states[idx + 1] == "returning":
                paused_then_returning = True
                break

        if not direct_returning and not paused_then_returning:
            return {"cancel_likely": False, "reason": "no_cancel_like_transition"}

        # Derive actual_cleaning_minutes from the returning transition so we can
        # apply an absolute floor that doesn't need a prior estimate.
        _MIN_FLOOR_MINUTES = 1.5
        actual_cleaning_minutes: float | None = None
        for t in reversed(transitions):
            if str(t.get("to_state", "")).strip().lower() == "returning":
                returning_ts = str(t.get("changed_at", "")).strip() or None
                if returning_ts:
                    ret_dt = self.store._parse_timestamp(returning_ts)
                    if ret_dt is not None and ret_dt > started_dt:
                        paused_secs = _safe_float(
                            active_job_state.get("paused_duration_seconds"), 0.0
                        )
                        raw = (ret_dt - started_dt).total_seconds() - paused_secs
                        actual_cleaning_minutes = max(raw / 60.0, 0.0)
                break

        if actual_cleaning_minutes is not None and actual_cleaning_minutes < _MIN_FLOOR_MINUTES:
            source = "physical_vacuum" if paused_then_returning else "app_or_manual_return"
            return {
                "cancel_likely": True,
                "reason": "floor_time_too_short",
                "source": source,
                "duration_minutes": round(duration_minutes, 2),
                "actual_cleaning_minutes": round(actual_cleaning_minutes, 2),
                "floor_threshold_minutes": _MIN_FLOOR_MINUTES,
                "message": (
                    f"Actual floor time ({actual_cleaning_minutes:.2f} min) is below the "
                    f"minimum credible clean ({_MIN_FLOOR_MINUTES} min) — likely a false start."
                ),
            }

        learning = manager._get_learning_manager()
        expected_room_minutes = 0.0
        if learning is not None:
            try:
                estimate = learning.estimate_from_manager(
                    manager,
                    vacuum_entity_id,
                    str(map_id),
                    float(_safe_int(battery_start, 0)),
                    1.0,
                    5.0,
                    started_at,
                )
                timeline = list(estimate.get("room_timeline", []))
                if timeline:
                    expected_room_minutes = _safe_float(timeline[0].get("minutes"), 0.0)
            except Exception:
                _LOGGER.exception(
                    "Failed to get learning estimate for %s map %s",
                    vacuum_entity_id,
                    str(map_id),
                )
                expected_room_minutes = 0.0

        short_threshold = max(min(expected_room_minutes * 0.4, expected_room_minutes), 0.75)
        if expected_room_minutes <= 0:
            short_threshold = 1.0

        if duration_minutes >= short_threshold:
            return {
                "cancel_likely": False,
                "reason": "duration_not_short",
                "duration_minutes": round(duration_minutes, 2),
                "expected_room_minutes": round(expected_room_minutes, 2),
                "short_threshold_minutes": round(short_threshold, 2),
            }

        source = "physical_vacuum" if paused_then_returning else "app_or_manual_return"
        return {
            "cancel_likely": True,
            "reason": "early_return_likely_cancelled",
            "source": source,
            "duration_minutes": round(duration_minutes, 2),
            "expected_room_minutes": round(expected_room_minutes, 2),
            "short_threshold_minutes": round(short_threshold, 2),
            "message": (
                "Job returned unusually early after a cancel-like transition pattern."
            ),
        }

    def _write_incomplete_run_log(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        completed_job: dict[str, Any],
        active_job_state: dict[str, Any],
        ended_at: str,
    ) -> dict[str, Any] | None:
        """Write the incomplete run log when a job ends without completing all rooms.

        Only fires for cancelled / failed / interrupted outcomes. Overwrites any
        previous log — only the most recent incomplete job is kept.
        Returns the written payload, or None if not written.
        """
        try:
            outcome = completed_job.get("outcome", {})
            outcome_status = str(outcome.get("status", "")).lower()
            if outcome_status not in {"cancelled", "failed", "interrupted"}:
                # Job completed normally — clear any stale incomplete run log so
                # the card banner doesn't persist after a successful full clean.
                self.store.clear_incomplete_run(vacuum_entity_id=vacuum_entity_id)
                return None

            queue = completed_job.get("queue", {})
            queued_room_ids: list[int] = [
                _safe_int(r, -1)
                for r in (queue.get("queue_room_ids") or [])
                if _safe_int(r, -1) > 0
            ]

            active_completed: list[int] = []
            if isinstance(active_job_state, dict):
                raw = active_job_state.get("completed_room_ids") or []
                if isinstance(raw, list):
                    active_completed = [
                        _safe_int(r, -1)
                        for r in raw
                        if _safe_int(r, -1) > 0
                    ]

            missed_room_ids = sorted(set(queued_room_ids) - set(active_completed))

            # Build name lookup from resolved_rooms
            resolved_rooms = completed_job.get("resolved_rooms", [])
            name_by_id: dict[int, str] = {}
            for room in (resolved_rooms if isinstance(resolved_rooms, list) else []):
                if not isinstance(room, dict):
                    continue
                rid = _safe_int(room.get("room_id", room.get("id", -1)), -1)
                if rid > 0:
                    name_by_id[rid] = (
                        str(room.get("name", "")).strip() or f"Room {rid}"
                    )

            missed_rooms = [
                {"room_id": rid, "name": name_by_id.get(rid, f"Room {rid}")}
                for rid in missed_room_ids
            ]

            payload: dict[str, Any] = {
                "schema_version": 1,
                "record_type": "incomplete_run_log",
                "vacuum_entity_id": vacuum_entity_id,
                "job_id": str(completed_job.get("job_id", "")).strip(),
                "map_id": str(map_id),
                "outcome_status": outcome_status,
                "ended_at": ended_at,
                "queued_room_ids": queued_room_ids,
                "completed_room_ids": active_completed,
                "missed_room_ids": missed_room_ids,
                "missed_rooms": missed_rooms,
                "logged_at": _iso_now(),
            }

            self.store.save_incomplete_run(
                vacuum_entity_id=vacuum_entity_id,
                payload=payload,
            )
            _LOGGER.debug(
                "Incomplete run log written for %s job %s: %d missed room(s)",
                vacuum_entity_id,
                payload["job_id"],
                len(missed_room_ids),
            )
            return payload
        except Exception:
            _LOGGER.exception(
                "Failed to write incomplete run log for %s",
                vacuum_entity_id,
            )
            return None

    def _update_trouble_rooms_log(
        self,
        *,
        vacuum_entity_id: str,
        completed_job: dict[str, Any],
        active_job_state: dict[str, Any],
        ended_at: str,
    ) -> None:
        """Update the chronic trouble rooms counter after every job finalization.

        Tracks how often each room is missed across runs. Rooms missed in 2+
        runs with a miss rate >= 33% are flagged as trouble rooms for the card
        to surface on the room tile.
        """
        try:
            outcome = completed_job.get("outcome", {})
            outcome_status = str(outcome.get("status", "")).lower()

            resolved_rooms = completed_job.get("resolved_rooms", [])
            name_by_id: dict[int, str] = {}
            for room in (resolved_rooms if isinstance(resolved_rooms, list) else []):
                if not isinstance(room, dict):
                    continue
                rid = _safe_int(room.get("room_id", room.get("id", -1)), -1)
                if rid > 0:
                    name_by_id[rid] = (
                        str(room.get("name", "")).strip() or f"Room {rid}"
                    )

            queue = completed_job.get("queue", {})
            queued_room_ids: list[int] = [
                _safe_int(r, -1)
                for r in (queue.get("queue_room_ids") or [])
                if _safe_int(r, -1) > 0
            ]

            if outcome_status == "completed":
                active_completed = queued_room_ids[:]
            else:
                raw = (
                    active_job_state.get("completed_room_ids")
                    if isinstance(active_job_state, dict)
                    else []
                ) or []
                active_completed = [
                    _safe_int(r, -1) for r in raw if _safe_int(r, -1) > 0
                ]

            missed_ids = set(queued_room_ids) - set(active_completed)

            existing = self.store.load_trouble_rooms(vacuum_entity_id=vacuum_entity_id) or {}
            rooms_data: dict[str, dict] = existing.get("rooms", {})
            if not isinstance(rooms_data, dict):
                rooms_data = {}

            for room_id in queued_room_ids:
                key = str(room_id)
                entry = dict(rooms_data.get(key) or {})
                entry.setdefault("room_id", room_id)
                entry["name"] = name_by_id.get(room_id, entry.get("name", f"Room {room_id}"))
                entry["run_count"] = _safe_int(entry.get("run_count"), 0) + 1
                entry.setdefault("miss_count", 0)

                if room_id in missed_ids:
                    entry["miss_count"] = _safe_int(entry["miss_count"], 0) + 1
                    entry["last_missed_at"] = ended_at
                else:
                    entry["last_cleaned_at"] = ended_at

                run_count = max(entry["run_count"], 1)
                entry["miss_rate"] = round(entry["miss_count"] / run_count, 3)
                entry["is_trouble"] = (
                    entry["miss_count"] >= 2 and entry["miss_rate"] >= 0.33
                )
                rooms_data[key] = entry

            payload: dict[str, Any] = {
                "schema_version": 1,
                "record_type": "trouble_rooms_log",
                "vacuum_entity_id": vacuum_entity_id,
                "updated_at": _iso_now(),
                "rooms": rooms_data,
            }
            self.store.save_trouble_rooms(
                vacuum_entity_id=vacuum_entity_id,
                payload=payload,
            )
            _LOGGER.debug("Trouble rooms log updated for %s", vacuum_entity_id)
        except Exception:  # pragma: no cover - best-effort diagnostic log write
            _LOGGER.exception(
                "Failed to update trouble rooms log for %s",
                vacuum_entity_id,
            )

    def _auto_derive_room_boundary(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        completed_job: dict[str, Any],
        was_cancelled: bool,
        trace_run_id: str | None,
    ) -> dict[str, Any] | None:
        """Attempt to derive a room boundary after a completed single-room job.

        Eligibility gates (all must pass):
          - outcome_status == "completed" (not cancelled/failed/interrupted)
          - was_cancelled == False
          - exactly 1 resolved room with a valid room_id
          - trace_run_id present

        Returns the derivation result dict, or None if skipped/not eligible.
        """
        outcome = completed_job.get("outcome", {})
        outcome_status = str(outcome.get("status", "")).lower()

        if was_cancelled or outcome_status != "completed":
            return None

        if not trace_run_id:
            return None

        resolved_rooms = completed_job.get("resolved_rooms", [])
        if not isinstance(resolved_rooms, list) or len(resolved_rooms) != 1:
            return None

        room = resolved_rooms[0]
        if not isinstance(room, dict):
            return None

        room_id = str(room.get("room_id", "")).strip()
        if not room_id or room_id == "None":
            return None

        edge_mopping = bool(room.get("edge_mopping", False))

        _LOGGER.debug(
            "auto_derive_boundary skipped: boundary derivation is inactive for vacuum=%s room=%s run=%s",
            vacuum_entity_id,
            room_id,
            trace_run_id,
        )
        return None
