"""Service layer for the optional learning system.

============================================================
LEARNING SERVICES
============================================================

PURPOSE
-------
Thin service registration layer. Each handler validates inputs,
delegates to LearningManager, and returns the full result payload.
No estimation or confidence math lives here.

SERVICES
--------
  save_learning_snapshot        snapshot current job state mid-run
  finalize_learning_job         finalize a completed job, optionally rebuild stats
  rebuild_learning_stats        rebuild all learned stats from completed job history
  run_learning_estimate         full estimate with confidence, ETA, overhead, stale flag
  record_estimate_accuracy      record estimated vs actual per room after a job
  reanchor_learning_timeline    recompute ETAs from actual completed room durations
  get_next_room                 lightweight next-room shortcut for live job display
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import DATA_RUNTIME, DOMAIN, EVENT_JOB_FINISHED, EVENT_RUN_INCOMPLETE
from .external_ingest import strip_samples
from .manager import LearningManager

_LOGGER = logging.getLogger(__name__)

LEARNING_DOMAIN = DOMAIN

SERVICE_SAVE_LEARNING_SNAPSHOT = "save_learning_snapshot"
SERVICE_FINALIZE_LEARNING_JOB = "finalize_learning_job"
SERVICE_REBUILD_LEARNING_STATS = "rebuild_learning_stats"
SERVICE_RUN_LEARNING_ESTIMATE = "run_learning_estimate"
SERVICE_RECORD_ESTIMATE_ACCURACY = "record_estimate_accuracy"
SERVICE_REANCHOR_LEARNING_TIMELINE = "reanchor_learning_timeline"
SERVICE_GET_NEXT_ROOM = "get_next_room"
SERVICE_GET_ROOM_LEARNING_ESTIMATES = "get_room_learning_estimates"
SERVICE_EXCLUDE_LEARNING_JOB = "exclude_learning_job"
SERVICE_RESTORE_LEARNING_JOB = "restore_learning_job"
SERVICE_GET_LEARNING_HISTORY_SNAPSHOT = "get_learning_history_snapshot"
SERVICE_GET_METRICS_SNAPSHOT = "get_metrics_snapshot"
SERVICE_GET_INCOMPLETE_RUN_LOG = "get_incomplete_run_log"
SERVICE_GET_TROUBLE_ROOMS_LOG = "get_trouble_rooms_log"
SERVICE_RETRY_MISSED_ROOMS = "retry_missed_rooms"
SERVICE_SET_LEARNING_PROCESSING = "set_learning_processing"
SERVICE_PROCESS_PENDING_RUNS = "process_pending_runs"

SAVE_LEARNING_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("started_at"): cv.string,
        vol.Required("battery_start"): vol.Coerce(int),
        vol.Optional("job_id"): cv.string,
    }
)

FINALIZE_LEARNING_JOB_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("battery_start"): vol.Coerce(int),
        vol.Required("battery_end"): vol.Coerce(int),
        vol.Required("started_at"): cv.string,
        vol.Optional("ended_at"): cv.string,
        vol.Optional("used_for_learning", default=True): cv.boolean,
        vol.Optional("rebuild_stats", default=True): cv.boolean,
        vol.Optional("rebuild_csv", default=False): cv.boolean,
        vol.Optional("forced_outcome_status"): cv.string,
    }
)

REBUILD_LEARNING_STATS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("rebuild_csv", default=False): cv.boolean,
    }
)

# Box-level learning-processing toggle (flips all vacuums) + on-demand backlog catch-up.
SET_LEARNING_PROCESSING_SCHEMA = vol.Schema({vol.Required("enabled"): cv.boolean})
PROCESS_PENDING_RUNS_SCHEMA = vol.Schema({})

RUN_LEARNING_ESTIMATE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("current_battery", default=0.0): vol.Coerce(float),
        vol.Optional("charge_percent_per_minute", default=1.0): vol.Coerce(float),
        vol.Optional("reserve_battery_percent", default=5.0): vol.Coerce(float),
        vol.Optional("started_at"): cv.string,
    }
)

RECORD_ESTIMATE_ACCURACY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        # List of {slug, clean_mode, clean_passes, is_carpet, clean_intensity,
        #          estimated_minutes, actual_minutes, map_id}
        vol.Required("room_actuals"): [dict],
    }
)

REANCHOR_LEARNING_TIMELINE_SCHEMA = vol.Schema(
    {
        vol.Required("original_estimate"): dict,
        # List of {room_id or slug, actual_duration_minutes}
        vol.Required("completed_rooms"): [dict],
        vol.Optional("reanchor_at"): cv.string,
        vol.Optional("current_battery"): vol.Coerce(float),
        vol.Optional("charge_percent_per_minute", default=1.0): vol.Coerce(float),
        vol.Optional("reserve_battery_percent", default=5.0): vol.Coerce(float),
    }
)

GET_NEXT_ROOM_SCHEMA = vol.Schema(
    {
        # The reanchored estimate payload from reanchor_learning_timeline.
        vol.Required("reanchored_estimate"): dict,
    }
)

GET_ROOM_LEARNING_ESTIMATES_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("current_battery"): vol.Any(None, vol.Coerce(float)),
    }
)

EXCLUDE_LEARNING_JOB_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("job_id"): cv.string,
        vol.Optional("reason", default="manual_exclusion"): cv.string,
        vol.Optional("rebuild_csv", default=False): cv.boolean,
    }
)

RESTORE_LEARNING_JOB_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("job_id"): cv.string,
        vol.Optional("rebuild_csv", default=False): cv.boolean,
    }
)

GET_LEARNING_HISTORY_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("room_slug"): cv.string,
        vol.Optional("profile_key"): cv.string,
        vol.Optional("status"): cv.string,
        vol.Optional("used_for_learning"): cv.boolean,
        vol.Optional("origin"): vol.In(["external", "internal"]),
        vol.Optional("limit", default=50): vol.Coerce(int),
    }
)

GET_METRICS_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("room_slug"): cv.string,
        vol.Optional("profile_key"): cv.string,
        vol.Optional("status"): cv.string,
        vol.Optional("used_for_learning"): cv.boolean,
    }
)

GET_INCOMPLETE_RUN_LOG_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)

GET_TROUBLE_ROOMS_LOG_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)

RETRY_MISSED_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        # map_id is optional — defaults to the map_id stored in the incomplete
        # run log, so automations don't need to track it explicitly.
        vol.Optional("map_id"): cv.string,
        # Set confirm_reduced_run=true to proceed even when blockers or access
        # rules would normally require confirmation (default: true, since
        # automations cannot interactively confirm).
        vol.Optional("confirm_reduced_run", default=True): cv.boolean,
        # Reaction when path-block rules change during the run.
        vol.Optional("path_block_action"): vol.In(
            ["event_only", "pause_and_event", "cancel_and_event"]
        ),
    }
)


SERVICE_CONFIRM_EXTERNAL_RUN = "confirm_external_run"
CONFIRM_EXTERNAL_RUN_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("pending_job_id"): cv.string,
        # [{segment_orders|segment_order, room_id, edge_mopping, override, overrides}]
        vol.Required("room_assignments"): vol.All(cv.ensure_list, [dict]),
        vol.Optional("rebuild_stats", default=True): cv.boolean,
    }
)


SERVICE_GET_EXTERNAL_PENDING_RUNS = "get_external_pending_runs"
GET_EXTERNAL_PENDING_RUNS_SCHEMA = vol.Schema(
    {vol.Required("vacuum_entity_id"): cv.entity_id}
)


SERVICE_DISCARD_EXTERNAL_RUN = "discard_external_run"
DISCARD_EXTERNAL_RUN_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("pending_job_id"): cv.string,
    }
)


SERVICE_RESEGMENT_EXTERNAL_RUN = "resegment_external_run"
RESEGMENT_EXTERNAL_RUN_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("pending_job_id"): cv.string,
        # count XOR explicit boundary set (neither => reset to the confident default).
        vol.Exclusive("expected_rooms", "resegment_mode"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Exclusive("active_boundaries", "resegment_mode"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    }
)


def _get_core_manager(hass: HomeAssistant):
    """Return core integration manager."""
    return hass.data[DOMAIN]["runtime"]


def _get_learning_manager(hass: HomeAssistant) -> LearningManager:
    """Return optional learning manager, creating it if needed."""
    learning = hass.data[DOMAIN].get("learning")
    if learning is None:
        learning = LearningManager(hass)
        hass.data[DOMAIN]["learning"] = learning
    return learning


async def async_register_learning_services(hass: HomeAssistant) -> None:
    """Register optional learning-system services."""

    async def handle_confirm_external_run(call: ServiceCall) -> dict:
        core_manager = _get_core_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        map_id = call.data["map_id"]
        # get_managed_rooms reads manager state — resolve on the loop, then graduate
        # (disk-heavy: load pending + build + write + rebuild) on the executor.
        rooms = (
            core_manager.get_managed_rooms(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id
            )
            or {}
        ).get("rooms", {})
        result = await hass.async_add_executor_job(
            core_manager.confirm_external_run,
            vacuum_entity_id,
            map_id,
            call.data["pending_job_id"],
            call.data["room_assignments"],
            rooms,
            call.data.get("rebuild_stats", True),
        )
        if (
            isinstance(result, dict)
            and result.get("ok")
            and call.data.get("rebuild_stats", True)
        ):
            learning = _get_learning_manager(hass)
            learning._invalidate_learning_stats_cache(vacuum_entity_id=vacuum_entity_id)
            learning.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
        return result if isinstance(result, dict) else {"ok": False}

    async def handle_get_external_pending_runs(call: ServiceCall) -> dict:
        core_manager = _get_core_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = await hass.async_add_executor_job(
            core_manager.get_external_pending_runs,
            vacuum_entity_id,
        )
        # Attach the full per-map room list so the review wizard can offer EVERY
        # room, not just the top-3 shortlist (which can miss the right one).
        # Resolved loop-side, like confirm, because get_managed_rooms reads
        # manager state.
        for rec in (result or {}).get("pending", []) or []:
            rooms_out: list[dict] = []
            try:
                rooms_dict = (
                    core_manager.get_managed_rooms(
                        vacuum_entity_id=vacuum_entity_id, map_id=rec.get("map_id")
                    )
                    or {}
                ).get("rooms", {})
                for rid, room in rooms_dict.items():
                    try:
                        room_id = int(rid)
                    except (TypeError, ValueError):
                        room_id = rid
                    rooms_out.append(
                        {
                            "room_id": room_id,
                            "slug": room.get("slug"),
                            "name": room.get("name") or room.get("slug"),
                        }
                    )
            except Exception:
                _LOGGER.exception(
                    "get_external_pending_runs: failed to attach room list"
                )
            rec["rooms"] = rooms_out
            # The card re-segments server-side; it never needs the raw samples. Flag
            # whether this record CAN be re-segmented (v2 embeds them; v1 cannot),
            # then strip the bulky samples from the served payload.
            rec["resegmentable"] = bool(rec.get("counter_samples"))
            strip_samples(rec)
        return result

    async def handle_resegment_external_run(call: ServiceCall) -> dict:
        core_manager = _get_core_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        map_id = call.data["map_id"]
        # get_managed_rooms reads manager state — resolve on the loop, then
        # re-segment (disk read + segment + write) on the executor.
        rooms = (
            core_manager.get_managed_rooms(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            or {}
        ).get("rooms", {})
        result = await hass.async_add_executor_job(
            core_manager.resegment_external_run,
            vacuum_entity_id,
            map_id,
            call.data["pending_job_id"],
            call.data.get("expected_rooms"),
            call.data.get("active_boundaries"),
            rooms,
        )
        return result if isinstance(result, dict) else {"ok": False}

    async def handle_discard_external_run(call: ServiceCall) -> dict:
        core_manager = _get_core_manager(hass)
        return await hass.async_add_executor_job(
            core_manager.discard_external_run,
            call.data["vacuum_entity_id"],
            call.data["pending_job_id"],
        )

    async def handle_save_learning_snapshot(call: ServiceCall) -> None:
        core_manager = _get_core_manager(hass)
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            learning.save_live_snapshot_from_manager,
            core_manager,
            call.data["vacuum_entity_id"],
            call.data["map_id"],
            call.data["started_at"],
            call.data["battery_start"],
            call.data.get("job_id"),
        )
        _LOGGER.debug("save_learning_snapshot complete: %s", result)

    async def handle_finalize_learning_job(call: ServiceCall) -> None:
        core_manager = _get_core_manager(hass)
        learning = _get_learning_manager(hass)
        result = await learning.async_finalize_completed_job(
            manager=core_manager,
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            battery_start=call.data["battery_start"],
            battery_end=call.data["battery_end"],
            started_at=call.data["started_at"],
            ended_at=call.data.get("ended_at"),
            used_for_learning=call.data["used_for_learning"],
            rebuild_stats=call.data["rebuild_stats"],
            rebuild_csv=call.data["rebuild_csv"],
            forced_outcome_status=call.data.get("forced_outcome_status"),
        )
        hass.bus.async_fire(
            EVENT_JOB_FINISHED,
            {
                "vacuum_entity_id": call.data["vacuum_entity_id"],
                "map_id": str(call.data["map_id"]),
                "job_id": result.get("job_id") if isinstance(result, dict) else None,
                "status": result.get("completed_job", {}).get("outcome", {}).get("status", "completed") if isinstance(result, dict) else "completed",
                "reason_detail": result.get("completed_job", {}).get("outcome", {}).get("lifecycle_message") if isinstance(result, dict) else None,
                "used_for_learning": result.get("completed_job", {}).get("outcome", {}).get("used_for_learning") if isinstance(result, dict) else None,
                "finalized_at": result.get("completed_job", {}).get("finalized_at") if isinstance(result, dict) else None,
                "room_count": result.get("completed_job", {}).get("job", {}).get("room_count") if isinstance(result, dict) else None,
                "job_path": result.get("job_path") if isinstance(result, dict) else None,
            },
        )

        # Fire run-incomplete event when rooms were missed.
        incomplete_log = result.get("incomplete_run_log") if isinstance(result, dict) else None
        if isinstance(incomplete_log, dict) and incomplete_log.get("missed_room_ids"):
            hass.bus.async_fire(
                EVENT_RUN_INCOMPLETE,
                {
                    "vacuum_entity_id": call.data["vacuum_entity_id"],
                    "job_id": incomplete_log.get("job_id"),
                    "outcome_status": incomplete_log.get("outcome_status"),
                    "missed_room_ids": list(incomplete_log.get("missed_room_ids", [])),
                    "missed_rooms": list(incomplete_log.get("missed_rooms", [])),
                },
            )

        _LOGGER.debug("finalize_learning_job complete: %s", result)

    async def handle_rebuild_learning_stats(call: ServiceCall) -> None:
        learning = _get_learning_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = await hass.async_add_executor_job(
            learning.rebuild_learning,
            vacuum_entity_id,
            call.data["rebuild_csv"],
        )
        learning._invalidate_learning_stats_cache(vacuum_entity_id=vacuum_entity_id)
        learning.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
        _LOGGER.debug("rebuild_learning_stats complete: %s", result)

    async def handle_set_learning_processing(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"error": "manager_unavailable"}
        return await manager.async_set_learning_processing(enabled=call.data["enabled"])

    async def handle_process_pending_runs(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"error": "manager_unavailable"}
        return await manager.async_process_pending_learning()

    async def handle_run_learning_estimate(call: ServiceCall) -> dict:
        core_manager = _get_core_manager(hass)
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.estimate_from_manager(
                core_manager,
                call.data["vacuum_entity_id"],
                call.data["map_id"],
                call.data["current_battery"],
                call.data["charge_percent_per_minute"],
                call.data["reserve_battery_percent"],
                call.data.get("started_at"),
            )
        )
        _LOGGER.debug("run_learning_estimate complete: %s", result)
        return result

    async def handle_record_estimate_accuracy(call: ServiceCall) -> dict:
        """Record estimated vs actual minutes per room after a job completes."""
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.record_estimate_accuracy(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                room_actuals=call.data["room_actuals"],
            )
        )
        _LOGGER.debug("record_estimate_accuracy complete: %s", result)
        return result

    async def handle_reanchor_learning_timeline(call: ServiceCall) -> dict:
        """Reanchor room ETAs using actual completed room durations.

        Called mid-job each time eufy_vacuum_room_completed fires.
        Optionally pass current_battery to update battery readiness.
        """
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.reanchor_timeline(
                original_estimate=call.data["original_estimate"],
                completed_rooms=call.data["completed_rooms"],
                reanchor_at=call.data.get("reanchor_at"),
                current_battery=call.data.get("current_battery"),
                charge_percent_per_minute=call.data.get("charge_percent_per_minute", 1.0),
                reserve_battery_percent=call.data.get("reserve_battery_percent", 5.0),
            )
        )
        _LOGGER.debug("reanchor_learning_timeline complete: %s", result)
        return result

    async def handle_get_next_room(call: ServiceCall) -> dict | None:
        """Return the next incomplete room for live job display.

        Lightweight — returns only what the card needs for a
        'cleaning Kitchen, done at 3:47' display.
        """
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.next_room(
                reanchored_estimate=call.data["reanchored_estimate"],
            )
        )
        _LOGGER.debug("get_next_room: %s", result)
        return result or {}

    async def handle_get_room_learning_estimates(call: ServiceCall) -> dict:
        """Return per-room learning estimates for all rooms on a map.

        Queue-independent — every managed room gets an estimate based on
        its current effective persisted settings. Safe for frequent UI refreshes.
        No side effects.
        """
        core_manager = _get_core_manager(hass)
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.get_room_learning_estimates(
                core_manager,
                call.data["vacuum_entity_id"],
                call.data["map_id"],
                call.data.get("current_battery"),
            )
        )
        _LOGGER.debug(
            "get_room_learning_estimates: %d rooms for %s map %s",
            len(result.get("rooms", [])),
            call.data["vacuum_entity_id"],
            call.data["map_id"],
        )
        return result

    async def handle_exclude_learning_job(call: ServiceCall) -> dict:
        """Exclude one archived completed job from learned stats."""
        learning = _get_learning_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = await hass.async_add_executor_job(
            lambda: learning.exclude_learning_job(
                vacuum_entity_id=vacuum_entity_id,
                job_id=call.data["job_id"],
                reason=call.data.get("reason"),
                rebuild_csv=call.data.get("rebuild_csv", False),
            )
        )
        learning._invalidate_learning_stats_cache(vacuum_entity_id=vacuum_entity_id)
        learning.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
        _LOGGER.debug("exclude_learning_job complete: %s", result)
        return result

    async def handle_restore_learning_job(call: ServiceCall) -> dict:
        """Restore one archived completed job back into learned stats."""
        learning = _get_learning_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = await hass.async_add_executor_job(
            lambda: learning.restore_learning_job(
                vacuum_entity_id=vacuum_entity_id,
                job_id=call.data["job_id"],
                rebuild_csv=call.data.get("rebuild_csv", False),
            )
        )
        learning._invalidate_learning_stats_cache(vacuum_entity_id=vacuum_entity_id)
        learning.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
        _LOGGER.debug("restore_learning_job complete: %s", result)
        return result

    async def handle_get_learning_history_snapshot(call: ServiceCall) -> dict:
        """Return a card-friendly learning history snapshot."""
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.get_learning_history_snapshot(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                room_slug=call.data.get("room_slug"),
                profile_key=call.data.get("profile_key"),
                status=call.data.get("status"),
                used_for_learning=call.data.get("used_for_learning"),
                origin=call.data.get("origin"),
                limit=call.data.get("limit", 50),
            )
        )
        _LOGGER.debug("get_learning_history_snapshot complete: %s", result)
        return result

    async def handle_get_metrics_snapshot(call: ServiceCall) -> dict:
        """Return a metrics-focused snapshot for the card."""
        learning = _get_learning_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: learning.get_metrics_snapshot(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                room_slug=call.data.get("room_slug"),
                profile_key=call.data.get("profile_key"),
                status=call.data.get("status"),
                used_for_learning=call.data.get("used_for_learning"),
            )
        )
        _LOGGER.debug("get_metrics_snapshot complete: %s", result)
        return result

    async def handle_get_trouble_rooms_log(call: ServiceCall) -> dict:
        """Return the chronic trouble rooms log for a vacuum.

        Returns per-room miss counts and rates. Rooms with miss_count >= 2
        and miss_rate >= 0.33 are flagged is_trouble=true for the card.
        Returns an empty dict when no log exists.
        """
        learning = _get_learning_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = await hass.async_add_executor_job(
            lambda: learning.get_trouble_rooms_log(
                vacuum_entity_id=vacuum_entity_id,
            )
        )
        _LOGGER.debug("get_trouble_rooms_log for %s: %s", vacuum_entity_id, result)
        return result or {}

    async def handle_get_incomplete_run_log(call: ServiceCall) -> dict:
        """Return the last incomplete run log for a vacuum.

        Returns the log payload when a previous job was cancelled, failed, or
        interrupted before all queued rooms were cleaned. Returns an empty dict
        when no incomplete run log exists.
        """
        learning = _get_learning_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = await hass.async_add_executor_job(
            lambda: learning.get_incomplete_run_log(
                vacuum_entity_id=vacuum_entity_id,
            )
        )
        _LOGGER.debug("get_incomplete_run_log for %s: %s", vacuum_entity_id, result)
        return result or {}

    async def handle_retry_missed_rooms(call: ServiceCall) -> dict:
        """Re-queue only the rooms missed in the last incomplete run and start cleaning.

        Automation pattern
        ------------------
        trigger:
          - platform: event
            event_type: eufy_vacuum_run_incomplete
            event_data:
              vacuum_entity_id: "vacuum.alfred"
        action:
          - service: eufy_vacuum.retry_missed_rooms
            data:
              vacuum_entity_id: "{{ trigger.event.data.vacuum_entity_id }}"

        Returns the same shape as start_selected_rooms with an additional
        ``missed_room_ids`` field listing which rooms were re-queued.
        Returns ``{"started": false, "reason": "no_missed_rooms"}`` when the
        incomplete run log is empty or absent.
        """
        core_manager = _get_core_manager(hass)
        learning = _get_learning_manager(hass)

        vacuum_entity_id: str = call.data["vacuum_entity_id"]
        map_id_override: str | None = call.data.get("map_id")

        # -------------------------------------------------------
        # Load incomplete run log (file I/O → executor).
        # -------------------------------------------------------
        log: dict | None = await hass.async_add_executor_job(
            lambda: learning.get_incomplete_run_log(
                vacuum_entity_id=vacuum_entity_id
            )
        )

        if not log or not log.get("missed_room_ids"):
            _LOGGER.debug(
                "retry_missed_rooms: no missed rooms in log for %s", vacuum_entity_id
            )
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "started": False,
                "reason": "no_missed_rooms",
                "message": "No incomplete run log found or no missed rooms recorded.",
            }

        missed_room_ids: list = list(log["missed_room_ids"])
        map_id: str = str(map_id_override or log.get("map_id") or "")

        if not map_id:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "started": False,
                "reason": "no_map_id",
                "message": "map_id could not be determined from the incomplete run log.",
            }

        # -------------------------------------------------------
        # Enable only missed rooms; rebuild queue.
        # (All in-memory mutations — stays on event loop.)
        # -------------------------------------------------------
        core_manager.set_rooms_enabled_subset(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_ids=missed_room_ids,
        )
        core_manager.build_queue(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        # -------------------------------------------------------
        # Start cleaning.
        # -------------------------------------------------------
        result = await core_manager.start_selected_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            confirm_reduced_run=call.data.get("confirm_reduced_run", True),
            path_block_action=call.data.get("path_block_action"),
        )

        await core_manager.async_save()

        # Clear the incomplete run log once the retry job is successfully
        # dispatched so the card banner doesn't reappear after this run.
        if isinstance(result, dict) and result.get("started"):
            await hass.async_add_executor_job(
                lambda: learning.clear_incomplete_run_log(
                    vacuum_entity_id=vacuum_entity_id
                )
            )

        _LOGGER.debug(
            "retry_missed_rooms for %s map %s: %s", vacuum_entity_id, map_id, result
        )
        return {
            **(result if isinstance(result, dict) else {}),
            "missed_room_ids": missed_room_ids,
            "map_id": map_id,
        }

    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_SAVE_LEARNING_SNAPSHOT,
        handle_save_learning_snapshot,
        schema=SAVE_LEARNING_SNAPSHOT_SCHEMA,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_FINALIZE_LEARNING_JOB,
        handle_finalize_learning_job,
        schema=FINALIZE_LEARNING_JOB_SCHEMA,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_REBUILD_LEARNING_STATS,
        handle_rebuild_learning_stats,
        schema=REBUILD_LEARNING_STATS_SCHEMA,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_SET_LEARNING_PROCESSING,
        handle_set_learning_processing,
        schema=SET_LEARNING_PROCESSING_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_PROCESS_PENDING_RUNS,
        handle_process_pending_runs,
        schema=PROCESS_PENDING_RUNS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_CONFIRM_EXTERNAL_RUN,
        handle_confirm_external_run,
        schema=CONFIRM_EXTERNAL_RUN_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_EXTERNAL_PENDING_RUNS,
        handle_get_external_pending_runs,
        schema=GET_EXTERNAL_PENDING_RUNS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_DISCARD_EXTERNAL_RUN,
        handle_discard_external_run,
        schema=DISCARD_EXTERNAL_RUN_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_RESEGMENT_EXTERNAL_RUN,
        handle_resegment_external_run,
        schema=RESEGMENT_EXTERNAL_RUN_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_RUN_LEARNING_ESTIMATE,
        handle_run_learning_estimate,
        schema=RUN_LEARNING_ESTIMATE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_RECORD_ESTIMATE_ACCURACY,
        handle_record_estimate_accuracy,
        schema=RECORD_ESTIMATE_ACCURACY_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_REANCHOR_LEARNING_TIMELINE,
        handle_reanchor_learning_timeline,
        schema=REANCHOR_LEARNING_TIMELINE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_NEXT_ROOM,
        handle_get_next_room,
        schema=GET_NEXT_ROOM_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_ROOM_LEARNING_ESTIMATES,
        handle_get_room_learning_estimates,
        schema=GET_ROOM_LEARNING_ESTIMATES_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_EXCLUDE_LEARNING_JOB,
        handle_exclude_learning_job,
        schema=EXCLUDE_LEARNING_JOB_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_RESTORE_LEARNING_JOB,
        handle_restore_learning_job,
        schema=RESTORE_LEARNING_JOB_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        handle_get_learning_history_snapshot,
        schema=GET_LEARNING_HISTORY_SNAPSHOT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_METRICS_SNAPSHOT,
        handle_get_metrics_snapshot,
        schema=GET_METRICS_SNAPSHOT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_TROUBLE_ROOMS_LOG,
        handle_get_trouble_rooms_log,
        schema=GET_TROUBLE_ROOMS_LOG_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_GET_INCOMPLETE_RUN_LOG,
        handle_get_incomplete_run_log,
        schema=GET_INCOMPLETE_RUN_LOG_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        LEARNING_DOMAIN,
        SERVICE_RETRY_MISSED_ROOMS,
        handle_retry_missed_rooms,
        schema=RETRY_MISSED_ROOMS_SCHEMA,
        supports_response=True,
    )


async def async_unregister_learning_services(hass: HomeAssistant) -> None:
    """Unregister optional learning-system services."""
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_SAVE_LEARNING_SNAPSHOT)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_FINALIZE_LEARNING_JOB)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_REBUILD_LEARNING_STATS)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_RUN_LEARNING_ESTIMATE)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_RECORD_ESTIMATE_ACCURACY)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_REANCHOR_LEARNING_TIMELINE)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_GET_NEXT_ROOM)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_GET_ROOM_LEARNING_ESTIMATES)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_EXCLUDE_LEARNING_JOB)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_RESTORE_LEARNING_JOB)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_GET_METRICS_SNAPSHOT)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_GET_TROUBLE_ROOMS_LOG)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_GET_INCOMPLETE_RUN_LOG)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_RETRY_MISSED_ROOMS)
    hass.services.async_remove(LEARNING_DOMAIN, SERVICE_RESEGMENT_EXTERNAL_RUN)
