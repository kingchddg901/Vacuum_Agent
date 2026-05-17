"""The Eufy Vacuum Manager integration."""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any
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
    DATA_ERROR_TRACKER,
    DATA_LEARNING,
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_JOB_PROGRESS_TICK,
    EVENT_PATH_BLOCKED,
)
from .adapters.registry import get_adapter_config, unregister_adapter_config
from .adapters.eufy.adapter import register_eufy_adapter_for_vacuum
from .adapters.config_loader import load_stored_adapter_configs
from .core.water_amendment import (
    register_post_job_water_amendment as _register_post_job_water_amendment,
)
from .battery.manager import BatteryHealthManager
from .core.error_tracker import ErrorTracker
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
    "binary_sensor",
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
_JOB_PROGRESS_UNSUBS = "_job_progress_unsubs"
_DISCOVERY_UNSUBS = "_discovery_unsubs"

# Lifecycle states that confirm the job has genuinely started moving.
# A job is not eligible for auto-finalization until at least one of these
# has been observed, preventing stale pre-run dock states (e.g. dock_drying)
# from instantly completing the job. Values must match evaluate_job_lifecycle().
_ACTIVE_LIFECYCLE_STATES: set[str] = {
    "active_job_running",  # vacuum is actively cleaning
    "mid_job_service",     # dock is servicing mid-job (wash/empty/recycle)
}

# Generic completion fallbacks. Used by _get_adapter_value when the adapter
# registry is absent. The task_status value is the normalized "job done"
# string; the clear sentinels are standard HA empty/unavailable states.
_DEFAULT_COMPLETION_TASK_STATUS = "completed"
_DEFAULT_CLEAR_SENTINELS: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "null"}
)


def _get_adapter_vocab(
    vacuum_entity_id: str,
    section: str,
    key: str,
    fallback: frozenset[str],
) -> frozenset[str]:
    """Read a vocabulary set from the adapter registry with fallback.

    Returns the registry value as a frozenset if present, otherwise
    returns the fallback. Never raises.
    """
    try:
        config = get_adapter_config(vacuum_entity_id)
        if config is None:
            return fallback
        value = config.get(section, {}).get(key)
        if isinstance(value, (list, set, frozenset)):
            return frozenset(str(v).strip().lower() for v in value)
        return fallback
    except Exception:
        return fallback


def _get_adapter_value(
    vacuum_entity_id: str,
    *path: str,
    fallback: Any,
) -> Any:
    """Read any scalar value from the adapter registry with fallback.

    ``path`` is a sequence of dict keys to traverse.
    Returns fallback if registry is absent, path is missing, or any
    error occurs.
    """
    try:
        config = get_adapter_config(vacuum_entity_id)
        if config is None:
            return fallback
        value: Any = config
        for key in path:
            if not isinstance(value, dict):
                return fallback
            value = value.get(key)
            if value is None:
                return fallback
        return value
    except Exception:
        return fallback


def _get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]:
    """Return entity IDs to watch for lifecycle state changes.

    Reads from the adapter registry — always includes the vacuum entity
    itself plus all declared entities whose state changes drive lifecycle
    re-evaluation. Returns only the vacuum entity when no adapter is
    registered, which is still safe (lifecycle functions then read empty
    entity states and produce no-op results).

    No brand-specific entity naming — all entity IDs come from the
    adapter's registered config.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entities = config.get("entities", {})
    watch: list[str] = [vacuum_entity_id]
    for key in ("task_status", "dock_status", "active_cleaning_target", "active_map"):
        entity_id = entities.get(key)
        if entity_id:
            watch.append(entity_id)
    return watch


def _completed_finalize_signals(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Return current entity states used for completion detection.

    Reads entity IDs from the adapter registry. Returns empty strings
    for absent or unavailable entities — the caller compares values
    against configured sentinels and task_status values.

    No brand-specific entity naming — all entity IDs come from the
    adapter's registered config.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entities = config.get("entities", {})

    def _state(entity_id: str | None) -> str:
        if not entity_id:
            return ""
        state_obj = hass.states.get(entity_id)
        if state_obj is None or state_obj.state is None:
            return ""
        return str(state_obj.state).strip().lower()

    return {
        "vacuum_state": _state(vacuum_entity_id),
        "task_status": _state(entities.get("task_status")),
        "dock_status": _state(entities.get("dock_status")),
        "active_target": _state(entities.get("active_cleaning_target")),
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



def _remove_lifecycle_listeners(hass: HomeAssistant) -> None:
    """Remove lifecycle listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_LIFECYCLE_UNSUBS, [])

    for unsub in unsubs:
        try:
            unsub()
        except Exception:
            _LOGGER.exception("Failed to remove lifecycle listener")



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
                        # Vocabulary params omitted — manager reads them from the
                        # adapter registry directly, with brand-specific fallbacks.
                    )

                    manager_local.update_active_job_recharge_observation(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id,
                    )

                    _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
                    _dock_status_entity = _adapter_cfg.get("entities", {}).get("dock_status")
                    if _dock_status_entity and entity_id == _dock_status_entity:
                        _new_state_n = str(new_state or "").strip().lower()
                        _wash_triggers = frozenset(
                            str(s).strip().lower()
                            for s in _adapter_cfg.get("dock_events", {})
                                                  .get("triggers", {})
                                                  .get("last_mop_wash", [])
                        ) or frozenset({"washing", "washing mop"})
                        if _new_state_n in _wash_triggers:
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
                            # WHY: start_job is sync and performs disk I/O
                                # (`_load_samples_from_disk` / `_delete_samples_tmp_file`).
                                # Run it on the executor to avoid both the
                                # not-awaitable TypeError and the blocking-I/O warning.
                            await hass.async_add_executor_job(
                                functools.partial(
                                    tracker.start_job,
                                    vacuum_entity_id=vacuum_entity_id,
                                    map_id=str(map_id),
                                    rooms=job_rooms,
                                )
                            )

                    _completion_task_status = _get_adapter_value(
                        vacuum_entity_id,
                        "completion", "task_status_value",
                        fallback=_DEFAULT_COMPLETION_TASK_STATUS,
                    )
                    _clear_sentinels = _get_adapter_vocab(
                        vacuum_entity_id,
                        "completion", "secondary_clear_sentinels",
                        _DEFAULT_CLEAR_SENTINELS,
                    )

                    completion_signals = _completed_finalize_signals(hass, vacuum_entity_id)

                    # Successful completion: task_status==Completed + target cleared.
                    # has_observed_active_lifecycle guards against stale pre-run dock
                    # states (e.g. dock_drying) triggering finalization before the job
                    # actually started moving. vacuum_docked is NOT required here —
                    # the vacuum may still be returning when these two signals fire,
                    # and requiring docked was stranding active_job records.
                    should_finalize_completed = bool(
                        str(completion_signals.get("task_status", "")).strip().lower()
                        == str(_completion_task_status).strip().lower()
                        and str(completion_signals.get("active_target", "")).strip().lower()
                        in _clear_sentinels
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
                            # WHY: end_job is sync and performs disk I/O
                            # (update_room_bounds, _append_raw_samples,
                            # _load_map_data). Run on executor.
                            await hass.async_add_executor_job(
                                functools.partial(
                                    tracker.end_job,
                                    vacuum_entity_id=vacuum_entity_id,
                                )
                            )

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
                        # Some docks wash the mop ~2s after docking, after finalization.
                        _completed = finalize_result.get("completed_job") or {}
                        _job_path = finalize_result.get("job_path")
                        _job_id = finalize_result.get("job_id")
                        _has_mop = any(
                            "mop" in str(r.get("clean_mode", "")).lower()
                            for r in _completed.get("resolved_rooms", [])
                            if isinstance(r, dict)
                        )
                        _amendment_enabled = _get_adapter_value(
                            vacuum_entity_id,
                            "post_job_wash_amendment", "enabled",
                            fallback=True,  # amendment: enabled by default
                        )
                        if _has_mop and _job_path and _job_id and _amendment_enabled:
                            _water = _completed.get("water") or {}
                            _debounce = _get_adapter_value(
                                vacuum_entity_id,
                                "post_job_wash_amendment", "debounce_seconds",
                                fallback=60.0,  # seconds; adapter config is authoritative
                            )
                            _timeout = _get_adapter_value(
                                vacuum_entity_id,
                                "post_job_wash_amendment", "timeout_seconds",
                                fallback=180,  # seconds; adapter config is authoritative
                            )
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
                                debounce_seconds=_debounce,
                                timeout_seconds=_timeout,
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
# Job metrics listeners (cleaning_time, cleaning_area)
# ----------------------------------------------------------------------

_JOB_METRICS_UNSUBS = "_job_metrics_unsubs"


def _remove_job_metrics_listeners(hass: HomeAssistant) -> None:
    """Remove job metrics state listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_METRICS_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:
            _LOGGER.exception("Failed to remove job metrics listener")


def _register_job_metrics_listeners(hass: HomeAssistant) -> None:
    """Register listeners that push job-metric sensor values into active_job_state.

    Tracks cleaning_time, cleaning_area, and station water level. These
    sensors update during the run via DPS packets, but finalization fires on
    a separate DPS packet (task_status → Completed) that may arrive before
    the sensor values have landed in HA's state machine. By pushing the
    last-seen value into active_job_state as each update arrives, finalization
    reads from there instead of issuing a live HA state read at job-end.
    """
    _remove_job_metrics_listeners(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    # Build a map of entity_id → (vacuum_entity_id, active_job_state_key, type)
    # for every vacuum whose adapter config exposes these entities.
    from .adapters.registry import get_adapter_config
    watch_map: dict[str, tuple[str, str, str]] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        config = get_adapter_config(vacuum_entity_id)
        entities = (config or {}).get("entities", {})
        object_id = vacuum_entity_id.split(".", 1)[-1]

        # Only watch entities the adapter explicitly declares. If an entity
        # key is absent the listener simply doesn't subscribe — finalization
        # falls through to its sensor and wall-clock fallbacks. Guessing at
        # a brand-specific name would silently subscribe to a nonexistent
        # entity on any adapter that doesn't expose it.
        ct_entity = entities.get("cleaning_time")
        if ct_entity:
            watch_map[ct_entity] = (vacuum_entity_id, "last_cleaning_time_seconds", "int")

        ca_entity = entities.get("cleaning_area")
        if ca_entity:
            watch_map[ca_entity] = (vacuum_entity_id, "last_cleaning_area_m2", "float")

        # Station water level — lives in capabilities entities, not the main
        # entities dict. Only added when the capability is exposed.
        try:
            caps = manager.get_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id, refresh=False
            )
            water_entity = (
                caps.get("entities", {}).get("water_level")
                or caps.get("entities", {}).get("station_water")
            )
            if water_entity:
                watch_map[water_entity] = (
                    vacuum_entity_id, "last_station_water_percent", "float"
                )
        except Exception:
            pass

    if not watch_map:
        domain_data[_JOB_METRICS_UNSUBS] = []
        return

    @callback
    def _handle_metrics_change(event: Event) -> None:
        entity_id = str(event.data.get("entity_id", ""))
        entry = watch_map.get(entity_id)
        if entry is None:
            return

        new_state_obj = event.data.get("new_state")
        if new_state_obj is None:
            return
        raw = new_state_obj.state
        if raw in ("unavailable", "unknown", None):
            return

        vacuum_entity_id, key, value_type = entry
        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        try:
            value = int(float(raw)) if value_type == "int" else float(raw)
        except (TypeError, ValueError):
            return

        manager_local.record_active_job_sensor_value(
            vacuum_entity_id=vacuum_entity_id,
            key=key,
            value=value,
        )

    unsub = async_track_state_change_event(
        hass,
        list(watch_map.keys()),
        _handle_metrics_change,
    )

    domain_data[_JOB_METRICS_UNSUBS] = [unsub]


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
        dock_entity = (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("dock_status")
        if dock_entity:
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

        _triggers = _get_adapter_value(
            vacuum_entity_id,
            "dock_events", "triggers",
            fallback={},
        )

        for event_type, trigger_states in _triggers.items():
            trigger_set = frozenset(
                str(s).strip().lower() for s in trigger_states
            )
            if new_val not in trigger_set:
                continue

            dry_duration: str | None = None
            if event_type == "last_dry_start":
                _dry_entity = _get_adapter_value(
                    vacuum_entity_id, "entities", "dry_duration", fallback=None
                )
                dry_sel = hass.states.get(_dry_entity) if _dry_entity else None
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


def _remove_job_progress_listener(hass: HomeAssistant) -> None:
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_PROGRESS_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover
            pass


def _register_job_progress_listener(hass: HomeAssistant) -> None:
    """Tick the job-progress snapshot every 5 s while any vacuum has an
    active job. Keeps stall detection and ``awaiting_bounds_exit``
    derivation firing during cleaning periods that have no vacuum-state
    transitions — e.g. a bounds-exit wait, where the vacuum reports
    "cleaning" continuously and the entity-state lifecycle listener
    never fires.

    Without this, ``get_job_progress_snapshot`` would only run when the
    dashboard polled it, which meant ``EVENT_STALL_DETECTED`` (fired as
    a side effect from inside the snapshot) silently failed for users
    who weren't actively looking at the panel. Moving the cadence to
    the backend makes stall-driven automations reliable regardless of
    UI state, and lets the card drop its bounds-exit polling.

    After each tick we fire ``EVENT_JOB_PROGRESS_TICK`` so the dashboard
    can refresh its snapshot if it's open. Cost per tick: one method
    call and one event per active vacuum/map; negligible.
    """
    _remove_job_progress_listener(hass)

    domain_data = hass.data.setdefault(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    @callback
    def _handle_job_progress_tick(_now) -> None:
        for vacuum_entity_id in manager.get_known_vacuum_ids():
            for map_id in manager.get_known_map_ids(vacuum_entity_id):
                map_id_str = str(map_id)
                if map_id_str.strip().lower() == "unknown":
                    continue

                active_job = manager.get_active_job(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id_str,
                )
                if active_job.get("status") not in {"started", "paused"}:
                    continue

                try:
                    manager.get_job_progress_snapshot(
                        vacuum_entity_id=vacuum_entity_id,
                        map_id=map_id_str,
                    )
                except Exception:
                    _LOGGER.exception(
                        "eufy_vacuum: job-progress tick failed for %s/%s",
                        vacuum_entity_id,
                        map_id_str,
                    )
                    continue

                hass.bus.async_fire(
                    EVENT_JOB_PROGRESS_TICK,
                    {
                        "vacuum_entity_id": vacuum_entity_id,
                        "map_id": map_id_str,
                    },
                )

    unsub = async_track_time_interval(
        hass,
        _handle_job_progress_tick,
        timedelta(seconds=5),
    )
    domain_data[_JOB_PROGRESS_UNSUBS] = [unsub]


def _remove_discovery_listeners(hass: HomeAssistant) -> None:
    """Tear down all auto-discovery triggers registered for the entry."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_DISCOVERY_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover
            pass


def _register_discovery_listeners(hass: HomeAssistant) -> None:
    """Wire auto-discovery triggers that keep room-drift history fresh.

    Each managed vacuum's adapter declares which triggers apply (under
    ``discovery.auto_refresh_on``) and an optional periodic interval
    (``discovery.auto_refresh_interval_seconds``). The framework owns
    the trigger semantics; the adapter just opts in.

    Triggers wired here:
      - ``vacuum_docked``        — vacuum entity transitions to "docked"
      - ``active_map_changed``   — active_map sensor value changes
      - ``config_entry_reload``  — one-shot pass right now (setup time)
      - periodic safety net      — every N seconds, adapter-configurable

    Manual rescan via ``setup_discover_rooms`` service also updates
    drift history (wired separately in services.py — the service path
    is always available regardless of which auto triggers are declared).
    """
    _remove_discovery_listeners(hass)

    from .setup.drift import get_discovery_cadence, run_discovery_pass

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    unsubs: list[Callable[[], None]] = []

    for vacuum_entity_id in manager.get_known_vacuum_ids():
        cadence = get_discovery_cadence(vacuum_entity_id)
        triggers = set(cadence.get("auto_refresh_on") or [])
        interval_seconds = int(cadence.get("auto_refresh_interval_seconds") or 0)
        adapter_config = get_adapter_config(vacuum_entity_id) or {}
        active_map_entity = (adapter_config.get("entities") or {}).get("active_map")

        # Bind vacuum_entity_id at closure-creation time so per-vacuum
        # callbacks see their own ID rather than the loop variable.
        def _make_run_pass(vid: str) -> Callable[[], None]:
            def _run() -> None:
                async def _do() -> None:
                    try:
                        run_discovery_pass(hass, manager, vid)
                        await manager.async_save()
                    except Exception:
                        _LOGGER.exception(
                            "discovery: failed for %s", vid
                        )
                hass.async_create_task(_do())
            return _run

        run_pass = _make_run_pass(vacuum_entity_id)

        # --- config_entry_reload: one-shot pass right now ---
        if "config_entry_reload" in triggers:
            run_pass()

        # --- vacuum_docked: state transitions to "docked" ---
        if "vacuum_docked" in triggers:
            @callback
            def _on_vacuum_state(
                event: Event,
                _run_pass: Callable[[], None] = run_pass,
            ) -> None:
                new_state_obj = event.data.get("new_state")
                old_state_obj = event.data.get("old_state")
                new_state = getattr(new_state_obj, "state", None)
                old_state = getattr(old_state_obj, "state", None)
                # Only fire on transition INTO docked — filter out
                # repeat docked-to-docked attribute updates and unknown
                # → docked startup noise.
                if new_state == "docked" and old_state != "docked":
                    _run_pass()

            unsubs.append(
                async_track_state_change_event(
                    hass, [vacuum_entity_id], _on_vacuum_state
                )
            )

        # --- active_map_changed: active_map sensor value changes ---
        if "active_map_changed" in triggers and active_map_entity:
            @callback
            def _on_active_map(
                event: Event,
                _run_pass: Callable[[], None] = run_pass,
            ) -> None:
                new_state_obj = event.data.get("new_state")
                old_state_obj = event.data.get("old_state")
                new_value = getattr(new_state_obj, "state", None)
                old_value = getattr(old_state_obj, "state", None)
                if (
                    new_value not in (None, "unknown", "unavailable")
                    and new_value != old_value
                ):
                    _run_pass()

            unsubs.append(
                async_track_state_change_event(
                    hass, [active_map_entity], _on_active_map
                )
            )

        # --- periodic safety net ---
        if interval_seconds > 0:
            @callback
            def _on_tick(
                _now,
                _run_pass: Callable[[], None] = run_pass,
            ) -> None:
                _run_pass()

            unsubs.append(
                async_track_time_interval(
                    hass, _on_tick, timedelta(seconds=interval_seconds)
                )
            )

    domain_data[_DISCOVERY_UNSUBS] = unsubs
    _LOGGER.debug(
        "discovery: registered %d auto-discovery trigger(s) across %d vacuum(s)",
        len(unsubs),
        len(manager.get_known_vacuum_ids()),
    )


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

    # Load stored adapter configs (UI-configured brands) before code
    # adapter registration. Code adapters registered below will overwrite
    # stored configs for the same vacuum — code adapters always win.
    _stored_count = load_stored_adapter_configs(hass, manager.data)
    if _stored_count > 0:
        _LOGGER.debug(
            "eufy_vacuum: loaded %d stored adapter config(s)",
            _stored_count,
        )

    # Register Eufy code adapter for each managed vacuum.
    # This overwrites any stored config for the same vacuum.
    for _vacuum_entity_id in manager.get_known_vacuum_ids():
        try:
            register_eufy_adapter_for_vacuum(hass, _vacuum_entity_id)
        except Exception:
            _LOGGER.exception(
                "eufy_vacuum: failed to register adapter config for %s",
                _vacuum_entity_id,
            )

    hass.data[DOMAIN][DATA_RUNTIME] = manager
    hass.data[DOMAIN][DATA_LEARNING] = LearningManager(hass)

    battery_manager = BatteryHealthManager(hass, runtime_manager=manager)
    battery_manager.start(manager.get_known_vacuum_ids())
    hass.data[DOMAIN][DATA_BATTERY] = battery_manager

    # Active-run error tracker. Wires state-change listeners on each
    # vacuum's error_message + vacuum entity, latches errors, persists
    # them across restarts. The two error sensors and the
    # active_run_has_error binary sensor read from this tracker.
    error_tracker = ErrorTracker(hass, runtime_manager=manager)
    error_tracker.start(manager.get_known_vacuum_ids())
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = error_tracker

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
    _register_job_metrics_listeners(hass)
    _register_dock_event_listeners(hass)
    _register_path_blocker_listeners(hass)
    _register_pause_timeout_listener(hass)
    _register_job_progress_listener(hass)
    _register_discovery_listeners(hass)

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
        _remove_job_metrics_listeners(hass)
        _remove_dock_event_listeners(hass)
        _remove_path_blocker_listeners(hass)
        _remove_pause_timeout_listener(hass)
        _remove_job_progress_listener(hass)
        _remove_discovery_listeners(hass)

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
        error_tracker = domain_data.pop(DATA_ERROR_TRACKER, None)
        if error_tracker is not None:
            try:
                error_tracker.stop()
            except Exception:  # pragma: no cover
                _LOGGER.exception("Failed to stop error tracker")
        # Unregister adapter configs on unload.
        _runtime_manager = domain_data.get(DATA_RUNTIME)
        if _runtime_manager is not None:
            for _vacuum_entity_id in list(_runtime_manager.get_known_vacuum_ids()):
                unregister_adapter_config(_vacuum_entity_id)

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
