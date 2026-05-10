"""The Eufy Vacuum Manager integration."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import os

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval

from ._frontend_url import panel_js_url
from .const import (
    DATA_BATTERY,
    DATA_LEARNING,
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_PATH_BLOCKED,
)
from .battery.manager import BatteryHealthManager
from .core.manager import EufyVacuumManager
from .learning.manager import LearningManager
from .learning.services import (
    async_register_learning_services,
    async_unregister_learning_services,
)
from .mapping.mapping_services import (
    async_register_mapping_services,
    async_unregister_mapping_services,
)
from .mapping.manager import MappingManager
from .mapping.tracker import MappingTracker
from .services import async_register_services, async_unregister_services
from .theme_services import (
    async_register_theme_services,
    async_unregister_theme_services,
)

_LOGGER = logging.getLogger(__name__)


def _job_finished_event_data(*, vacuum_entity_id: str, map_id: str, finalize_result: dict | None) -> dict:
    """Build a compact job-finished event payload."""
    finalize_result = finalize_result if isinstance(finalize_result, dict) else {}
    completed_job = finalize_result.get("completed_job", {})
    outcome = completed_job.get("outcome", {}) if isinstance(completed_job, dict) else {}
    job_info = completed_job.get("job", {}) if isinstance(completed_job, dict) else {}
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "job_id": finalize_result.get("job_id"),
        "status": outcome.get("status", "completed"),
        "reason_detail": outcome.get("lifecycle_message") or outcome.get("status"),
        "used_for_learning": outcome.get("used_for_learning"),
        "finalized_at": completed_job.get("finalized_at"),
        "room_count": job_info.get("room_count"),
        "duration_minutes": job_info.get("duration_minutes"),
        "actual_cleaning_minutes": job_info.get("actual_cleaning_minutes"),
        "job_path": finalize_result.get("job_path"),
    }


PLATFORMS: list[str] = [
    "button",
    "switch",
    "select",
    "number",
    "sensor",
]

_JOB_LIFECYCLE_UNSUBS = "_job_lifecycle_unsubs"
_DOCK_EVENT_UNSUBS = "_dock_event_unsubs"
_PATH_BLOCKER_UNSUBS = "_path_blocker_unsubs"
_PATH_BLOCKER_ROOM_CALLBACK = "_path_blocker_room_callback"
_PAUSE_TIMEOUT_UNSUBS = "_pause_timeout_unsubs"

# Maps dock event_type keys to the normalised dock_status strings that trigger them.
_DOCK_EVENT_TRIGGERS: dict[str, set[str]] = {
    "last_mop_wash": {"washing", "washing mop"},
    "last_dust_empty": {"emptying dust", "emptying dust bin", "dust emptying"},
    "last_dry_start": {"drying", "drying mop", "drying pads", "mop drying"},
}

# Lifecycle states that confirm the job has genuinely started moving.
# A job is not eligible for auto-finalization until at least one of these
# has been observed, preventing stale pre-run dock states (e.g. dock_drying)
# from instantly completing the job. Values must match evaluate_job_lifecycle().
_ACTIVE_LIFECYCLE_STATES: set[str] = {
    "active_job_running",  # vacuum is actively cleaning
    "mid_job_service",     # dock is servicing mid-job (wash/empty/recycle)
}


# ----------------------------------------------------------------------
# Domain setup
# ----------------------------------------------------------------------


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    hass.data.setdefault(DOMAIN, {})

    maps_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "maps")
    os.makedirs(maps_dir, exist_ok=True)

    # Floor textures ship with the integration so HACS delivers them on
    # every install. Previously this pointed at <config>/eufy_vacuum/textures
    # which only ever existed on the developer's machine — every other
    # install 404'd silently. cache_headers=True because these are
    # versioned, non-changing static assets (~18 MB total).
    textures_dir = os.path.join(os.path.dirname(__file__), "textures")

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    os.makedirs(frontend_dir, exist_ok=True)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/eufy_vacuum/maps", maps_dir, cache_headers=False),
            StaticPathConfig("/eufy_vacuum/textures", textures_dir, cache_headers=True),
            StaticPathConfig("/eufy_vacuum/frontend", frontend_dir, cache_headers=False),
        ]
    )

    return True


# ----------------------------------------------------------------------
# Lifecycle / job auto-finalization
# ----------------------------------------------------------------------


def _get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]:
    """Return entity ids that should trigger lifecycle reevaluation."""
    object_id = vacuum_entity_id.split(".", 1)[1]
    return [
        vacuum_entity_id,
        f"sensor.{object_id}_task_status",
        f"sensor.{object_id}_dock_status",
        f"sensor.{object_id}_active_cleaning_target",
        f"sensor.{object_id}_active_map",
    ]


def _get_entity_state_lower(hass: HomeAssistant, entity_id: str) -> str:
    """Return one entity state as a normalized lowercase string."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None or state_obj.state is None:
        return ""
    return str(state_obj.state).strip().lower()


def _active_cleaning_target_cleared(value: str) -> bool:
    """Return whether the active cleaning target should be treated as cleared."""
    return value in {"", "unknown", "unavailable", "none", "null"}


def _completed_finalize_signals(hass: HomeAssistant, vacuum_entity_id: str) -> dict[str, object]:
    """Return the current strong completion signals for one vacuum."""
    object_id = vacuum_entity_id.split(".", 1)[1]
    vacuum_state = _get_entity_state_lower(hass, vacuum_entity_id)
    task_status = _get_entity_state_lower(hass, f"sensor.{object_id}_task_status")
    dock_status = _get_entity_state_lower(hass, f"sensor.{object_id}_dock_status")
    active_target = _get_entity_state_lower(hass, f"sensor.{object_id}_active_cleaning_target")

    return {
        "vacuum_state": vacuum_state,
        "task_status": task_status,
        "dock_status": dock_status,
        "active_target": active_target,
        "task_completed": task_status == "completed",
        "target_cleared": _active_cleaning_target_cleared(active_target),
        "vacuum_docked": vacuum_state == "docked",
    }


def _remove_lifecycle_listeners(hass: HomeAssistant) -> None:
    """Remove lifecycle listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_LIFECYCLE_UNSUBS, [])

    for unsub in unsubs:
        try:
            unsub()
        except Exception:
            _LOGGER.exception("Failed to remove lifecycle listener")


def _register_post_job_water_amendment(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    job_id: str,
    job_path: str,
    water_start_percent: float,
    mop_wash_count_at_finalization: int,
    timeout_seconds: int = 180,
) -> None:
    """Watch for post-job mop wash and patch completed job water actuals.

    The X10 Pro Omni washes the mop pad after docking from a mop job. This
    starts ~2 seconds after finalization, so the initial water actuals always
    show 0ml. This watcher patches the completed job file once the dock
    finishes its post-job wash cycle (dock_status → Drying).
    """
    object_id = vacuum_entity_id.split(".", 1)[1]
    dock_status_entity = f"sensor.{object_id}_dock_status"
    water_level_entity = f"sensor.{object_id}_water_level"

    amendment_state: dict = {"wash_count": 0, "committed": False, "last_wash_at": 0.0}
    unsub_listener: list[Callable] = []
    unsub_timeout: list[Callable] = []

    def _cancel_all() -> None:
        for fn in unsub_listener:
            try:
                fn()
            except Exception:
                pass
        for fn in unsub_timeout:
            try:
                fn()
            except Exception:
                pass
        unsub_listener.clear()
        unsub_timeout.clear()

    def _write_amendment(end_percent: float | None, wash_count: int) -> None:
        path = Path(job_path)
        if not path.exists():
            return
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _LOGGER.exception("post_job_water_amendment: failed to read %s", job_path)
            return

        water = job.get("water")
        if not isinstance(water, dict):
            return

        total_wash_count = mop_wash_count_at_finalization + wash_count
        water["actual_mop_wash_count"] = total_wash_count
        water["actual_end_station_clean_water_percent"] = end_percent

        start_pct = water.get("station_clean_water_percent")
        capacity_ml = water.get("dock_clean_tank_capacity_ml", 3080.0)
        overhead_per_cycle = water.get("dock_wash_overhead_ml_per_cycle", 120.0)

        tank_emptied = end_percent is not None and end_percent <= 0.0

        if (
            end_percent is not None
            and isinstance(start_pct, (int, float))
            and isinstance(capacity_ml, (int, float))
            and capacity_ml > 0
            and start_pct >= end_percent
        ):
            actual_total_ml = round((start_pct - end_percent) / 100.0 * capacity_ml, 1)
            actual_wash_ml = round(total_wash_count * overhead_per_cycle, 1)
            actual_floor_ml = round(max(actual_total_ml - actual_wash_ml, 0.0), 1) if not tank_emptied else None
            estimated = water.get("estimated_total_dock_clean_water_used_ml") or 0.0
            water["actual_dock_water_used_ml"] = actual_total_ml
            water["actual_mop_wash_water_ml"] = actual_wash_ml
            water["actual_floor_water_ml"] = actual_floor_ml
            water["actual_vs_estimated_delta_ml"] = round(actual_total_ml - float(estimated), 1) if not tank_emptied else None
        else:
            water["actual_dock_water_used_ml"] = None
            water["actual_mop_wash_water_ml"] = None
            water["actual_floor_water_ml"] = None
            water["actual_vs_estimated_delta_ml"] = None

        water["actual_tank_emptied"] = tank_emptied

        from .learning.utils import _iso_now
        water["water_amended_at"] = _iso_now()
        water["water_amendment_reason"] = "post_job_wash"
        job["water"] = water

        try:
            path.write_text(json.dumps(job, indent=2), encoding="utf-8")
            _LOGGER.debug(
                "post_job_water_amendment: patched %s wash_count=%d end_pct=%s",
                job_id, total_wash_count, end_percent,
            )
        except Exception:
            _LOGGER.exception("post_job_water_amendment: failed to write %s", job_path)

    @callback
    def _commit(reason: str) -> None:
        if amendment_state["committed"]:
            return
        amendment_state["committed"] = True
        _cancel_all()

        # Only write if something actually happened during the window.
        if amendment_state["wash_count"] == 0 and reason == "timeout":
            return

        water_state = hass.states.get(water_level_entity)
        end_pct: float | None = None
        if water_state and water_state.state not in ("unavailable", "unknown"):
            try:
                end_pct = float(water_state.state)
            except (ValueError, TypeError):
                pass

        wash_count = amendment_state["wash_count"]
        hass.async_create_task(
            hass.async_add_executor_job(_write_amendment, end_pct, wash_count)
        )

    _MIN_WASH_INTERVAL_SECONDS = 60.0

    @callback
    def _on_dock_change(event: Event) -> None:
        import time as _time
        new_state_obj = event.data.get("new_state")
        new_state = str(getattr(new_state_obj, "state", "") or "").strip().lower()
        if new_state in {"washing", "washing mop"}:
            now = _time.monotonic()
            if now - amendment_state["last_wash_at"] >= _MIN_WASH_INTERVAL_SECONDS:
                amendment_state["wash_count"] += 1
                amendment_state["last_wash_at"] = now
        elif new_state == "drying":
            _commit("drying")

    @callback
    def _on_timeout(_now) -> None:
        _commit("timeout")

    unsub_listener.append(
        async_track_state_change_event(hass, [dock_status_entity], _on_dock_change)
    )
    unsub_timeout.append(async_call_later(hass, timeout_seconds, _on_timeout))


def _register_lifecycle_listeners(hass: HomeAssistant) -> None:
    """Register listeners that auto-finalize completed jobs."""
    _remove_lifecycle_listeners(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    watched_entities: set[str] = set()
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        watched_entities.update(_get_lifecycle_watch_entities(vacuum_entity_id))

    if not watched_entities:
        domain_data[_JOB_LIFECYCLE_UNSUBS] = []
        return

    @callback
    def _handle_lifecycle_change(event: Event) -> None:
        """Process lifecycle-triggering entity change."""
        entity_id = str(event.data.get("entity_id", ""))
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")
        old_state = getattr(old_state_obj, "state", None)
        new_state = getattr(new_state_obj, "state", None)

        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        matched_vacuum_ids: list[str] = []
        for vacuum_entity_id in manager_local.get_known_vacuum_ids():
            if entity_id in _get_lifecycle_watch_entities(vacuum_entity_id):
                matched_vacuum_ids.append(vacuum_entity_id)

        if not matched_vacuum_ids:
            return

        async def _process() -> None:
            """Evaluate and auto-finalize any jobs whose lifecycle has ended."""
            any_changes = False

            for vacuum_entity_id in matched_vacuum_ids:
                for map_id in manager_local.get_known_map_ids(vacuum_entity_id):
                    active_job = manager_local.get_active_job(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    if active_job.get("status") not in {"started", "paused"}:
                        continue

                    manager_local.record_active_job_transition(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                        entity_id=entity_id,
                        from_state=old_state,
                        to_state=new_state,
                    )

                    lifecycle = manager_local.get_lifecycle_state(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    manager_local.update_active_job_recharge_observation(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    _object_id = vacuum_entity_id.split(".", 1)[1]
                    if entity_id == f"sensor.{_object_id}_dock_status":
                        _new_state_n = str(new_state or "").strip().lower()
                        if _new_state_n in {"washing", "washing mop"}:
                            manager_local.update_active_job_mop_wash_observation(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=map_id,
                            )

                    lifecycle_state = str(lifecycle.get("lifecycle_state", "")).strip().lower()

                    if lifecycle_state in _ACTIVE_LIFECYCLE_STATES:
                        # Delegate the flag + write-back to the manager so it owns the mutation.
                        # Also update the local copy so the completion check below sees it.
                        manager_local.record_active_lifecycle_observed(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                        )
                        active_job["has_observed_active_lifecycle"] = True
                        any_changes = True
                        tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
                        if tracker is not None and vacuum_entity_id not in tracker._active_job:
                            all_rooms = manager_local.get_managed_rooms(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=str(map_id),
                            ).get("rooms", {})
                            # Only include rooms active in this job so single-room
                            # jobs always use the unconditional single-room path.
                            active_ids = {
                                str(r) for r in active_job.get("queue_room_ids", [])
                            }
                            job_rooms = (
                                {k: v for k, v in all_rooms.items() if k in active_ids}
                                if active_ids else all_rooms
                            )
                            await tracker.start_job(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=str(map_id),
                                rooms=job_rooms,
                            )

                    completion_signals = _completed_finalize_signals(hass, vacuum_entity_id)

                    # Successful completion: task_status==Completed + target cleared.
                    # has_observed_active_lifecycle guards against stale pre-run dock
                    # states (e.g. dock_drying) triggering finalization before the job
                    # actually started moving. vacuum_docked is NOT required here —
                    # the vacuum may still be returning when these two signals fire,
                    # and requiring docked was stranding active_job records.
                    should_finalize_completed = bool(
                        completion_signals["task_completed"]
                        and completion_signals["target_cleared"]
                        and active_job.get("has_observed_active_lifecycle", False)
                    )

                    if not should_finalize_completed:
                        continue

                    finalize_result = None
                    try:
                        finalize_result = await manager_local.finalize_learning_for_active_job(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                            rebuild_stats=True,
                            rebuild_csv=False,
                        )
                        _LOGGER.debug(
                            "Auto-finalized job for %s map %s: %s",
                            vacuum_entity_id,
                            map_id,
                            finalize_result,
                        )
                    except Exception:
                        _LOGGER.exception(
                            "Failed to auto-finalize job for %s map %s",
                            vacuum_entity_id,
                            map_id,
                        )
                    finally:
                        tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
                        if tracker is not None:
                            await tracker.end_job(vacuum_entity_id=vacuum_entity_id)

                    # Always clear the active_job record so it can never be stranded
                    # as status:started regardless of whether finalization succeeded.
                    # Delegates ownership of finalization write-back to the manager.
                    manager_local.mark_active_job_finalized(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                        finalize_result=finalize_result,
                    )
                    if finalize_result is not None:
                        hass.bus.async_fire(
                            EVENT_JOB_FINISHED,
                            _job_finished_event_data(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=map_id,
                                finalize_result=finalize_result,
                            ),
                        )
                        # Register post-job water amendment for mop jobs.
                        # The X10 washes the mop ~2s after docking, after finalization.
                        _completed = finalize_result.get("completed_job") or {}
                        _job_path = finalize_result.get("job_path")
                        _job_id = finalize_result.get("job_id")
                        _has_mop = any(
                            "mop" in str(r.get("clean_mode", "")).lower()
                            for r in _completed.get("resolved_rooms", [])
                            if isinstance(r, dict)
                        )
                        if _has_mop and _job_path and _job_id:
                            _water = _completed.get("water") or {}
                            _register_post_job_water_amendment(
                                hass,
                                vacuum_entity_id=vacuum_entity_id,
                                job_id=_job_id,
                                job_path=_job_path,
                                water_start_percent=float(
                                    _water.get("station_clean_water_percent") or 0
                                ),
                                mop_wash_count_at_finalization=int(
                                    _water.get("actual_mop_wash_count") or 0
                                ),
                            )
                    any_changes = True

            if any_changes:
                await manager_local.async_save()

        hass.async_create_task(_process())

    unsub = async_track_state_change_event(
        hass,
        list(watched_entities),
        _handle_lifecycle_change,
    )

    domain_data[_JOB_LIFECYCLE_UNSUBS] = [unsub]


# ----------------------------------------------------------------------
# Dock event listeners (wash / empty / dry)
# ----------------------------------------------------------------------


def _remove_dock_event_listeners(hass: HomeAssistant) -> None:
    """Remove dock event state listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_DOCK_EVENT_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:
            _LOGGER.exception("Failed to remove dock event listener")


def _register_dock_event_listeners(hass: HomeAssistant) -> None:
    """Register listeners that record dock events (wash, empty, dry) to storage."""
    _remove_dock_event_listeners(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    watched: dict[str, str] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        object_id = vacuum_entity_id.split(".", 1)[1]
        dock_entity = f"sensor.{object_id}_dock_status"
        watched[dock_entity] = vacuum_entity_id

    if not watched:
        domain_data[_DOCK_EVENT_UNSUBS] = []
        return

    @callback
    def _handle_dock_event(event: Event) -> None:
        """Handle a dock_status state change and record the event."""
        entity_id = str(event.data.get("entity_id", ""))
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if new_state is None:
            return

        new_val = str(new_state.state).strip().lower()
        old_val = str(old_state.state).strip().lower() if old_state else ""

        if new_val == old_val:
            return

        vacuum_entity_id = watched.get(entity_id)
        if vacuum_entity_id is None:
            return

        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        for event_type, trigger_states in _DOCK_EVENT_TRIGGERS.items():
            if new_val not in trigger_states:
                continue

            dry_duration: str | None = None
            if event_type == "last_dry_start":
                object_id = vacuum_entity_id.split(".", 1)[1]
                dry_sel = hass.states.get(f"select.{object_id}_dry_duration")
                if dry_sel is not None and dry_sel.state not in ("unknown", "unavailable", ""):
                    dry_duration = dry_sel.state

            manager_local.record_dock_event(
                vacuum_entity_id=vacuum_entity_id,
                event_type=event_type,
                dry_duration=dry_duration,
            )

            hass.async_create_task(manager_local._async_save_logged())

            _LOGGER.debug(
                "Dock event recorded: %s for %s (dock_status=%s)",
                event_type,
                vacuum_entity_id,
                new_val,
            )

    unsub = async_track_state_change_event(
        hass,
        list(watched.keys()),
        _handle_dock_event,
    )
    domain_data[_DOCK_EVENT_UNSUBS] = [unsub]


# ----------------------------------------------------------------------
# Path-blocker listeners
# ----------------------------------------------------------------------



def _remove_path_blocker_listeners(hass: HomeAssistant) -> None:
    """Remove runtime path-block listeners and room-update callback."""
    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)

    room_callback = domain_data.pop(_PATH_BLOCKER_ROOM_CALLBACK, None)
    if manager is not None and room_callback is not None:
        try:
            manager.unregister_room_update_callback(room_callback)
        except Exception:
            _LOGGER.exception("Failed to unregister path blocker room callback")

    unsubs: list[Callable[[], None]] = domain_data.pop(_PATH_BLOCKER_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:
            _LOGGER.exception("Failed to remove path blocker listener")


def _remove_pause_timeout_listener(hass: HomeAssistant) -> None:
    """Remove the paused-job timeout watchdog."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_PAUSE_TIMEOUT_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:
            _LOGGER.exception("Failed to remove pause-timeout listener")


def _register_pause_timeout_listener(hass: HomeAssistant) -> None:
    """Cancel paused jobs that exceed their configured timeout."""
    _remove_pause_timeout_listener(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    @callback
    def _handle_pause_timeout_tick(_now) -> None:
        """Check paused jobs on a lightweight timer."""
        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        async def _process() -> None:
            any_changes = False
            for vacuum_entity_id in manager_local.get_known_vacuum_ids():
                for map_id in manager_local.get_known_map_ids(vacuum_entity_id):
                    if str(map_id).strip().lower() == "unknown":
                        continue
                    timeout_report = manager_local.get_paused_job_timeout_report(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )
                    if not isinstance(timeout_report, dict):
                        continue

                    result = await manager_local.async_cancel_active_job(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                        forced_lifecycle_state=timeout_report["forced_lifecycle_state"],
                        forced_lifecycle_message=timeout_report["forced_lifecycle_message"],
                        cancel_reason=timeout_report["cancel_reason"],
                    )
                    if not bool(result.get("cancelled")):
                        continue

                    hass.bus.async_fire(
                        EVENT_JOB_FINISHED,
                        _job_finished_event_data(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                            finalize_result=result.get("finalize_result"),
                        ),
                    )
                    any_changes = True
                    _LOGGER.debug(
                        "Auto-cancelled paused job for %s map %s after %s minute timeout",
                        vacuum_entity_id,
                        map_id,
                        timeout_report.get("pause_timeout_minutes"),
                    )

            if any_changes:
                await manager_local.async_save()

        hass.async_create_task(_process())

    unsub = async_track_time_interval(
        hass,
        _handle_pause_timeout_tick,
        timedelta(minutes=1),
    )
    domain_data[_PAUSE_TIMEOUT_UNSUBS] = [unsub]


def _register_path_blocker_listeners(hass: HomeAssistant) -> None:
    """Watch blocker entities during active jobs and fire path-blocked events."""
    _remove_path_blocker_listeners(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    watch_map: dict[str, list[tuple[str, str]]] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        for map_id in manager.get_known_map_ids(vacuum_entity_id):
            if str(map_id).strip().lower() == "unknown":
                continue
            managed_rooms = manager._normalized_managed_rooms_with_automation(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            for room in managed_rooms.values():
                if not isinstance(room, dict):
                    continue
                for rule in room.get("rules", []):
                    if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                        continue
                    if str(rule.get("kind", "")).strip().lower() != "blocker":
                        continue
                    entity_id = str(rule.get("entity_id", "")).strip()
                    if not entity_id:
                        continue
                    targets = watch_map.setdefault(entity_id, [])
                    target = (vacuum_entity_id, str(map_id))
                    if target not in targets:
                        targets.append(target)

    @callback
    def _handle_room_update(*, vacuum_entity_id: str, map_id: str) -> None:
        """Rebuild watchers whenever room automation config changes."""
        _register_path_blocker_listeners(hass)

    manager.register_room_update_callback(_handle_room_update)
    domain_data[_PATH_BLOCKER_ROOM_CALLBACK] = _handle_room_update

    if not watch_map:
        domain_data[_PATH_BLOCKER_UNSUBS] = []
        return

    @callback
    def _handle_path_blocker_change(event: Event) -> None:
        """Re-evaluate active path accessibility after blocker state changes."""
        entity_id = str(event.data.get("entity_id", "")).strip()
        old_state_obj = event.data.get("old_state")
        new_state_obj = event.data.get("new_state")
        old_state = getattr(old_state_obj, "state", None)
        new_state = getattr(new_state_obj, "state", None)

        if not entity_id or entity_id not in watch_map:
            return
        if new_state_obj is None or old_state == new_state:
            return

        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        async def _process() -> None:
            any_changes = False
            for vacuum_entity_id, map_id in watch_map.get(entity_id, []):
                active_job = manager_local.get_active_job(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                )
                report = manager_local.get_runtime_path_block_report(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    trigger_entity_id=entity_id,
                    trigger_entity_state=new_state,
                )
                if not isinstance(report, dict):
                    continue

                path_block_action = str(active_job.get("path_block_action", "event_only")).strip().lower() or "event_only"
                action_taken = "event_only"
                action_result: dict | None = None

                if path_block_action == "pause_and_event":
                    if str(active_job.get("status", "")).strip().lower() == "paused":
                        action_taken = "already_paused"
                    else:
                        action_result = await manager_local.async_pause_active_job(
                            vacuum_entity_id=vacuum_entity_id,
                            map_id=map_id,
                        )
                        action_taken = "paused" if bool((action_result or {}).get("paused")) else "pause_failed"
                elif path_block_action == "cancel_and_event":
                    action_result = await manager_local.async_cancel_active_job(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )
                    action_taken = "cancelled" if bool((action_result or {}).get("cancelled")) else "cancel_failed"
                    if bool((action_result or {}).get("cancelled")):
                        hass.bus.async_fire(
                            EVENT_JOB_FINISHED,
                            _job_finished_event_data(
                                vacuum_entity_id=vacuum_entity_id,
                                map_id=map_id,
                                finalize_result=(action_result or {}).get("finalize_result"),
                            ),
                        )

                report["path_block_action"] = path_block_action
                report["action_taken"] = action_taken
                if action_result is not None:
                    report["action_result"] = action_result
                hass.bus.async_fire(EVENT_PATH_BLOCKED, report)
                any_changes = True
                _LOGGER.debug(
                    "Runtime path blocked for %s map %s via %s (%s): %s",
                    vacuum_entity_id,
                    map_id,
                    entity_id,
                    action_taken,
                    report.get("affected_remaining_room_ids"),
                )

            if any_changes:
                await manager_local.async_save()

        hass.async_create_task(_process())

    unsub = async_track_state_change_event(
        hass,
        list(watch_map.keys()),
        _handle_path_blocker_change,
    )
    domain_data[_PATH_BLOCKER_UNSUBS] = [unsub]


# ----------------------------------------------------------------------
# Config entry lifecycle
# ----------------------------------------------------------------------


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eufy Vacuum Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    manager = EufyVacuumManager(hass)
    await manager.async_initialize()

    hass.data[DOMAIN][DATA_RUNTIME] = manager
    hass.data[DOMAIN][DATA_LEARNING] = LearningManager(hass)

    battery_manager = BatteryHealthManager(hass, runtime_manager=manager)
    battery_manager.start(manager.get_known_vacuum_ids())
    hass.data[DOMAIN][DATA_BATTERY] = battery_manager

    async def _handle_rebaseline(call: ServiceCall) -> None:
        vacuum_entity_id = call.data["vacuum_entity_id"]
        bm = hass.data.get(DOMAIN, {}).get(DATA_BATTERY)
        if bm is None:
            _LOGGER.warning(
                "battery: rebaseline service called but battery manager is not loaded"
            )
            return
        ok = bm.rebaseline(vacuum_entity_id)
        if not ok:
            _LOGGER.warning(
                "battery: rebaseline service called for %s but no record was found",
                vacuum_entity_id,
            )

    hass.services.async_register(
        DOMAIN,
        "battery_rebaseline",
        _handle_rebaseline,
        schema=vol.Schema({vol.Required("vacuum_entity_id"): cv.entity_id}),
    )

    mapping_manager = MappingManager(hass)
    mapping_tracker = MappingTracker(hass, mapping_manager)
    hass.data[DOMAIN]["mapping_manager"] = mapping_manager
    hass.data[DOMAIN]["mapping_tracker"] = mapping_tracker
    for _vac in manager.get_known_vacuum_ids():
        try:
            _caps = manager.get_vacuum_capabilities(vacuum_entity_id=_vac, refresh=False)
            _x_entity = _caps.get("entities", {}).get("robot_position_x")
            _y_entity = _caps.get("entities", {}).get("robot_position_y")
            if _x_entity and _y_entity:
                mapping_tracker.register_vacuum(
                    vacuum_entity_id=_vac,
                    position_x_entity_id=_x_entity,
                    position_y_entity_id=_y_entity,
                )
        except Exception:
            pass

    await async_register_services(hass)
    await async_register_learning_services(hass)
    await async_register_theme_services(hass)
    await async_register_mapping_services(hass)

    _register_lifecycle_listeners(hass)
    _register_dock_event_listeners(hass)
    _register_path_blocker_listeners(hass)
    _register_pause_timeout_listener(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register one sidebar panel per managed vacuum.
    registered_panels: list[str] = []
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        object_id = vacuum_entity_id.split(".", 1)[-1]
        panel_url = f"eufy-vacuum-{object_id}"
        try:
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=panel_url,
                webcomponent_name="eufy-vacuum-command-center",
                js_url=panel_js_url(),
                sidebar_title="Eufy Vacuum",
                sidebar_icon="mdi:robot-vacuum",
                config={"vacuum_entity_id": vacuum_entity_id},
                require_admin=False,
                embed_iframe=False,
            )
            registered_panels.append(panel_url)
            _LOGGER.debug("eufy_vacuum: registered panel /%s for %s", panel_url, vacuum_entity_id)
        except ValueError:
            _LOGGER.debug("eufy_vacuum: panel /%s already registered", panel_url)

    hass.data[DOMAIN][f"_panels_{entry.entry_id}"] = registered_panels

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        for panel_url in domain_data.pop(f"_panels_{entry.entry_id}", []):
            # panel_custom doesn't expose an unregister API; the panel is
            # registered into HA's frontend component, which is where the
            # remove helper lives.
            try:
                frontend.async_remove_panel(hass, panel_url)
            except Exception:  # pragma: no cover - defensive
                _LOGGER.debug("eufy_vacuum: failed to remove panel /%s", panel_url, exc_info=True)

        _remove_lifecycle_listeners(hass)
        _remove_dock_event_listeners(hass)
        _remove_path_blocker_listeners(hass)
        _remove_pause_timeout_listener(hass)

        await async_unregister_mapping_services(hass)
        await async_unregister_learning_services(hass)
        await async_unregister_theme_services(hass)
        await async_unregister_services(hass)

        domain_data = hass.data.get(DOMAIN, {})
        mapping_tracker = domain_data.pop("mapping_tracker", None)
        if mapping_tracker is not None:
            mapping_tracker.unregister_all()
        domain_data.pop("mapping_manager", None)
        battery_manager = domain_data.pop(DATA_BATTERY, None)
        if battery_manager is not None:
            try:
                battery_manager.stop()
            except Exception:  # pragma: no cover
                _LOGGER.exception("Failed to stop battery health manager")
        domain_data.pop(DATA_RUNTIME, None)
        domain_data.pop(DATA_LEARNING, None)

        if not domain_data:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear persistent storage when the entry is deleted."""
    from homeassistant.helpers.storage import Store

    from .core.storage import STORAGE_KEY, STORAGE_VERSION

    store = Store[dict](hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_remove()
    _LOGGER.debug("eufy_vacuum: storage cleared on entry removal")
