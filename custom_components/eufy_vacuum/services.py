"""Service handlers for Eufy Vacuum Manager."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_RUNTIME,
    DOMAIN,
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_IMPORT_MAP,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_APPLY_ROOM_PROFILE,
    SERVICE_BUILD_QUEUE,
    SERVICE_BUILD_ROOM_PAYLOAD,
    SERVICE_CANCEL_ACTIVE_JOB,
    SERVICE_CLEAR_ACTIVE_JOB,
    SERVICE_CLEAR_QUEUE,
    SERVICE_DISCOVER_ROOMS,
    SERVICE_DRY_MOP,
    SERVICE_EMPTY_DUST,
    SERVICE_GET_ACTIVE_JOB,
    SERVICE_GET_DASHBOARD_SNAPSHOT,
    SERVICE_GET_DOCK_ACTION_STATUS,
    SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_GET_JOB_PROGRESS_SNAPSHOT,
    SERVICE_GET_JOB_CONTROL_STATE,
    SERVICE_GET_LIFECYCLE_STATE,
    SERVICE_GET_PAYLOAD_STATE,
    SERVICE_GET_QUEUE_STATE,
    SERVICE_GET_ACCESS_GRAPH_HEALTH,
    SERVICE_GET_ROOM_ACCESS_EDITOR,
    SERVICE_GET_ROOM_PROFILES,
    SERVICE_DELETE_ROOM_PROFILE,
    SERVICE_OVERWRITE_ROOM_PROFILE,
    SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
    SERVICE_RENAME_ROOM_PROFILE,
    SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
    SERVICE_SAVE_USER_ROOM_PROFILE,
    SERVICE_GET_SAVED_RUN_PROFILES,
    SERVICE_GET_START_STATUS,
    SERVICE_GET_UPKEEP_SNAPSHOT,
    SERVICE_PAUSE_ACTIVE_JOB,
    SERVICE_RESUME_ACTIVE_JOB,
    SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_STOP_DRY_MOP,
    SERVICE_GET_VACUUM_CAPABILITIES,
    SERVICE_GET_VACUUM_MAPS,
    SERVICE_SAVE_MANAGED_ROOMS,
    SERVICE_SAVE_RUN_PROFILE,
    SERVICE_START_RUN_PROFILE,
    SERVICE_START_SELECTED_ROOMS,
    SERVICE_RENAME_RUN_PROFILE,
    SERVICE_UPDATE_ROOM_FIELDS,
    SERVICE_WASH_MOP,
    SERVICE_RESET_MAINTENANCE,
    SERVICE_SET_DOCK_EVENT_COUNT,
    SERVICE_APPLY_RUN_PROFILE,
    SERVICE_DELETE_RUN_PROFILE,
    SERVICE_OVERWRITE_RUN_PROFILE,
    EVENT_JOB_FINISHED,
)

_LOGGER = logging.getLogger(__name__)


def _job_finished_event_payload(*, vacuum_entity_id: str, map_id: str, result: dict | None) -> dict:
    """Build consistent payload for the job-finished event."""
    result = result if isinstance(result, dict) else {}
    completed_job = result.get("completed_job") or result.get("finalize_result", {}).get("completed_job", {})
    if not isinstance(completed_job, dict):
        completed_job = {}
    outcome = completed_job.get("outcome", {}) if isinstance(completed_job.get("outcome", {}), dict) else {}
    job_info = completed_job.get("job", {}) if isinstance(completed_job.get("job", {}), dict) else {}
    job_path = result.get("job_path")
    if job_path is None and isinstance(result.get("finalize_result"), dict):
        job_path = result["finalize_result"].get("job_path")
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "job_id": result.get("job_id") or result.get("finalize_result", {}).get("job_id"),
        "status": outcome.get("status", "completed"),
        "reason_detail": outcome.get("lifecycle_message") or outcome.get("status"),
        "used_for_learning": outcome.get("used_for_learning"),
        "finalized_at": completed_job.get("finalized_at"),
        "room_count": job_info.get("room_count"),
        "duration_minutes": job_info.get("duration_minutes"),
        "actual_cleaning_minutes": job_info.get("actual_cleaning_minutes"),
        "job_path": job_path,
    }


DISCOVER_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
    }
)

SAVE_MANAGED_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("enabled_room_ids"): vol.All(
            cv.ensure_list,
            [vol.Coerce(int)],
        ),
    }
)

GET_VACUUM_MAPS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)

VACUUM_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
    }
)

JOB_CONTROL_SCHEMA = VACUUM_MAP_SCHEMA
VACUUM_ONLY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)
PAUSE_TIMEOUT_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("pause_timeout_minutes_default"): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }
)

SAVE_USER_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("label"): cv.string,
        vol.Required("clean_mode"): cv.string,
        vol.Required("fan_speed"): cv.string,
        vol.Required("water_level"): cv.string,
        vol.Required("clean_intensity"): cv.string,
        vol.Required("clean_passes"): vol.Coerce(int),
        vol.Required("edge_mopping"): cv.boolean,
        vol.Optional("profile_name"): cv.string,
    }
)

SAVE_ROOM_PROFILE_FROM_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
        vol.Required("label"): cv.string,
        vol.Optional("profile_name"): cv.string,
    }
)

OVERWRITE_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_name"): cv.string,
        vol.Required("label"): cv.string,
        vol.Required("clean_mode"): cv.string,
        vol.Required("fan_speed"): cv.string,
        vol.Required("water_level"): cv.string,
        vol.Required("clean_intensity"): cv.string,
        vol.Required("clean_passes"): vol.Coerce(int),
        vol.Required("edge_mopping"): cv.boolean,
    }
)

OVERWRITE_ROOM_PROFILE_FROM_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
        vol.Required("profile_name"): cv.string,
        vol.Optional("label"): cv.string,
    }
)

RENAME_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_name"): cv.string,
        vol.Optional("new_profile_name"): cv.string,
        vol.Optional("label"): cv.string,
    }
)

DELETE_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_name"): cv.string,
    }
)

APPLY_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_ids"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required("profile_name"): cv.string,
    }
)

RUN_PROFILE_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("expose_as_button"): cv.boolean,
    }
)

RUN_PROFILE_ID_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
    }
)

RUN_PROFILE_OVERWRITE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("expose_as_button"): cv.boolean,
    }
)

RUN_PROFILE_RENAME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)

START_SELECTED_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("confirm_reduced_run"): cv.boolean,
        vol.Optional("confirm_token"): cv.string,
        vol.Optional("path_block_action"): vol.In(
            ["event_only", "pause_and_event", "cancel_and_event"]
        ),
        vol.Optional("pause_timeout_minutes_override"): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }
)

START_RUN_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Optional("confirm_reduced_run"): cv.boolean,
        vol.Optional("confirm_token"): cv.string,
        vol.Optional("path_block_action"): vol.In(
            ["event_only", "pause_and_event", "cancel_and_event"]
        ),
        vol.Optional("pause_timeout_minutes_override"): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }
)

UPDATE_ROOM_FIELDS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
        vol.Optional("enabled"): cv.boolean,
        vol.Optional("clean_mode"): cv.string,
        vol.Optional("fan_speed"): cv.string,
        vol.Optional("water_level"): cv.string,
        vol.Optional("clean_intensity"): cv.string,
        vol.Optional("clean_passes"): vol.Coerce(int),
        vol.Optional("edge_mopping"): cv.boolean,
        vol.Optional("is_dock_room"): cv.boolean,
        vol.Optional("is_transition"): cv.boolean,
        vol.Optional("grants_access_to"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional("rules"): vol.All(cv.ensure_list, [dict]),
    }
)

ROOM_ACCESS_EDITOR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
    }
)

GET_VACUUM_CAPABILITIES_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("detected_model"): vol.Any(None, cv.string),
        vol.Optional("refresh", default=True): cv.boolean,
    }
)

RESET_MAINTENANCE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("component"): cv.string,
    }
)

SET_DOCK_EVENT_COUNT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("event_type"): vol.In(["last_mop_wash", "last_dust_empty", "last_dry_start"]),
        vol.Required("count"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


def _get_manager(hass: HomeAssistant):
    """Return the integration manager."""
    return hass.data[DOMAIN][DATA_RUNTIME]


async def _handle_discover_rooms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Discover rooms from the vacuum integration."""
    payload = _get_manager(hass).discover_rooms(**call.data)
    _LOGGER.debug("discover_rooms complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_save_managed_rooms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Save selected rooms as managed configuration."""
    payload = _get_manager(hass).save_managed_rooms(**call.data)
    _LOGGER.debug("save_managed_rooms complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_get_vacuum_maps(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get all maps for a vacuum."""
    payload = _get_manager(hass).get_vacuum_maps(**call.data)
    _LOGGER.debug("get_vacuum_maps complete: %s", payload)
    return payload


async def _handle_build_queue(hass: HomeAssistant, call: ServiceCall) -> None:
    """Build cleaning queue from enabled rooms."""
    payload = _get_manager(hass).build_queue(**call.data)
    _LOGGER.debug("build_queue complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_build_room_payload(hass: HomeAssistant, call: ServiceCall) -> None:
    """Build payload for room cleaning."""
    payload = _get_manager(hass).build_room_payload(**call.data)
    _LOGGER.debug("build_room_payload complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_get_queue_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current queue state."""
    payload = _get_manager(hass).get_queue_state(**call.data)
    _LOGGER.debug("get_queue_state complete: %s", payload)
    return payload


async def _handle_get_payload_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current payload state."""
    payload = _get_manager(hass).get_payload_state(**call.data)
    _LOGGER.debug("get_payload_state complete: %s", payload)
    return payload


async def _handle_clear_queue(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear queue state."""
    payload = _get_manager(hass).clear_queue(**call.data)
    _LOGGER.debug("clear_queue complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_get_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current active job state."""
    payload = _get_manager(hass).get_active_job(**call.data)
    _LOGGER.debug("get_active_job complete: %s", payload)
    return payload


async def _handle_get_job_progress_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return canonical room-job progress state for the card."""
    payload = _get_manager(hass).get_job_progress_snapshot(**call.data)
    _LOGGER.debug("get_job_progress_snapshot complete: %s", payload)
    return payload


async def _handle_get_job_control_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return card-facing action state for one vacuum/map."""
    payload = _get_manager(hass).get_job_control_state(**call.data)
    _LOGGER.debug("get_job_control_state complete: %s", payload)
    return payload


async def _handle_get_pause_timeout_settings(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return persisted default pause-timeout settings for one vacuum."""
    payload = _get_manager(hass).get_pause_timeout_settings(**call.data)
    _LOGGER.debug("get_pause_timeout_settings complete: %s", payload)
    return payload


async def _handle_set_pause_timeout_settings(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Persist default pause-timeout settings for one vacuum."""
    payload = _get_manager(hass).set_pause_timeout_settings(**call.data)
    _LOGGER.debug("set_pause_timeout_settings complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_get_upkeep_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return upkeep snapshot for one vacuum."""
    payload = _get_manager(hass).get_upkeep_snapshot(**call.data)
    _LOGGER.debug("get_upkeep_snapshot complete: %s", payload)
    return payload


async def _handle_get_dashboard_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return unified dashboard snapshot for one vacuum/map."""
    # Must NOT use async_add_executor_job here — get_dashboard_snapshot calls
    # hass.bus.async_fire internally (via _maybe_roll_current_room_by_timing),
    # which requires the event loop thread.
    payload = _get_manager(hass).get_dashboard_snapshot(**call.data)
    _LOGGER.debug("get_dashboard_snapshot complete: %s", payload)
    return payload


async def _handle_get_dock_action_status(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return gated dock-action availability for one vacuum/map."""
    payload = _get_manager(hass).get_dock_action_status(**call.data)
    _LOGGER.debug("get_dock_action_status complete: %s", payload)
    return payload


async def _handle_clear_active_job(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear active job state."""
    payload = _get_manager(hass).clear_active_job(**call.data)
    _LOGGER.debug("clear_active_job complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_get_lifecycle_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get lifecycle state for vacuum."""
    payload = _get_manager(hass).get_lifecycle_state(**call.data)
    _LOGGER.debug("get_lifecycle_state complete: %s", payload)
    return payload


async def _handle_get_start_status(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Check if start is allowed.

    Must NOT use async_add_executor_job — get_start_status calls
    hass.bus.async_fire internally (via _build_effective_start_plan →
    _maybe_roll_current_room_by_timing) and must stay on the event loop.
    """
    payload = _get_manager(hass).get_start_status(**call.data)
    _LOGGER.debug("get_start_status complete: %s", payload)
    return payload


async def _handle_start_selected_rooms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Start cleaning selected rooms."""
    payload = await _get_manager(hass).start_selected_rooms(**call.data)
    _LOGGER.debug("start_selected_rooms complete: %s", payload)
    await _get_manager(hass).async_save()


async def _handle_start_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply and start one saved run profile."""
    payload = await _get_manager(hass).start_run_profile(**call.data)
    _LOGGER.debug("start_run_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_pause_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Pause one tracked active job and the underlying vacuum."""
    payload = await _get_manager(hass).async_pause_active_job(**call.data)
    _LOGGER.debug("pause_active_job complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_resume_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Resume one tracked paused job and the underlying vacuum."""
    payload = await _get_manager(hass).async_resume_active_job(**call.data)
    _LOGGER.debug("resume_active_job complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_cancel_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Cancel one tracked job, return the vacuum to base, and finalize it."""
    payload = await _get_manager(hass).async_cancel_active_job(**call.data)
    if payload.get("cancelled"):
        hass.bus.async_fire(
            EVENT_JOB_FINISHED,
            _job_finished_event_payload(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                result=payload.get("finalize_result"),
            ),
        )
    _LOGGER.debug("cancel_active_job complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_wash_mop(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated wash-mop dock action."""
    payload = await _get_manager(hass).async_wash_mop(**call.data)
    _LOGGER.debug("wash_mop complete: %s", payload)
    return payload


async def _handle_dry_mop(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated dry-mop dock action."""
    payload = await _get_manager(hass).async_dry_mop(**call.data)
    _LOGGER.debug("dry_mop complete: %s", payload)
    return payload


async def _handle_empty_dust(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated empty-dust dock action."""
    payload = await _get_manager(hass).async_empty_dust(**call.data)
    _LOGGER.debug("empty_dust complete: %s", payload)
    return payload


async def _handle_stop_dry_mop(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated stop-dry-mop dock action."""
    payload = await _get_manager(hass).async_stop_dry_mop(**call.data)
    _LOGGER.debug("stop_dry_mop complete: %s", payload)
    return payload


async def _handle_reset_maintenance(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Reset the maintenance counter for a specific component."""
    payload = _get_manager(hass).reset_maintenance(**call.data)
    _LOGGER.debug("reset_maintenance complete: %s", payload)
    if payload.get("reset"):
        await _get_manager(hass).async_save()
    return payload


async def _handle_set_dock_event_count(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite a dock event counter to a specific value."""
    payload = _get_manager(hass).set_dock_event_count(**call.data)
    _LOGGER.debug("set_dock_event_count complete: %s", payload)
    if payload.get("updated"):
        await _get_manager(hass).async_save()
    return payload


async def _handle_get_room_profiles(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get all available room profiles."""
    payload = _get_manager(hass).get_room_profiles()
    _LOGGER.debug("get_room_profiles complete: %s", payload)
    return payload


async def _handle_save_user_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save a custom room profile."""
    payload = _get_manager(hass).save_user_room_profile(**call.data)
    _LOGGER.debug("save_user_room_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_overwrite_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one existing custom room profile."""
    payload = _get_manager(hass).overwrite_room_profile(**call.data)
    _LOGGER.debug("overwrite_room_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_save_room_profile_from_room(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save a custom room profile from one room's current settings."""
    payload = _get_manager(hass).save_room_profile_from_room(**call.data)
    _LOGGER.debug("save_room_profile_from_room complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_overwrite_room_profile_from_room(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one existing custom room profile from one room's current settings."""
    payload = _get_manager(hass).overwrite_room_profile_from_room(**call.data)
    _LOGGER.debug("overwrite_room_profile_from_room complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_rename_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Rename one custom room profile key and/or label."""
    payload = _get_manager(hass).rename_room_profile(**call.data)
    _LOGGER.debug("rename_room_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_delete_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete one custom room profile."""
    payload = _get_manager(hass).delete_room_profile(**call.data)
    _LOGGER.debug("delete_room_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_apply_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply a profile to one or more rooms."""
    payload = _get_manager(hass).apply_room_profile(**call.data)
    _LOGGER.debug("apply_room_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_get_saved_run_profiles(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return saved run profiles for one vacuum/map."""
    payload = _get_manager(hass).get_saved_run_profiles(**call.data)
    _LOGGER.debug("get_saved_run_profiles complete: %s", payload)
    return payload


async def _handle_get_room_access_editor(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return one room's access-graph editor payload."""
    payload = _get_manager(hass).get_room_access_editor(**call.data)
    _LOGGER.debug("get_room_access_editor complete: %s", payload)
    return payload


async def _handle_get_access_graph_health(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return whole-map access-graph health."""
    payload = _get_manager(hass).get_access_graph_health(**call.data)
    _LOGGER.debug("get_access_graph_health complete: %s", payload)
    return payload


async def _handle_save_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save current enabled-room run as a named reusable profile."""
    payload = _get_manager(hass).save_run_profile(**call.data)
    _LOGGER.debug("save_run_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_apply_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply one saved run profile back onto room selections/settings."""
    payload = _get_manager(hass).apply_run_profile(**call.data)
    _LOGGER.debug("apply_run_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_rename_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Rename one saved run profile."""
    payload = _get_manager(hass).rename_run_profile(**call.data)
    _LOGGER.debug("rename_run_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_overwrite_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one saved run profile from the current enabled-room snapshot."""
    payload = _get_manager(hass).overwrite_run_profile(**call.data)
    _LOGGER.debug("overwrite_run_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_delete_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete one saved run profile."""
    payload = _get_manager(hass).delete_run_profile(**call.data)
    _LOGGER.debug("delete_run_profile complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def _handle_get_vacuum_capabilities(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Detect and return capability information for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]
    detected_model = call.data.get("detected_model")
    refresh = call.data.get("refresh", True)

    payload = _get_manager(hass).get_vacuum_capabilities(
        vacuum_entity_id=vacuum_entity_id,
        detected_model=detected_model,
        refresh=refresh,
    )
    _LOGGER.debug("get_vacuum_capabilities complete: %s", payload)
    await _get_manager(hass).async_save()
    return payload


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def discover_rooms(call: ServiceCall) -> None:
        await _handle_discover_rooms(hass, call)

    async def save_managed_rooms(call: ServiceCall) -> None:
        await _handle_save_managed_rooms(hass, call)

    async def get_vacuum_maps(call: ServiceCall) -> dict:
        return await _handle_get_vacuum_maps(hass, call)

    async def build_queue(call: ServiceCall) -> None:
        await _handle_build_queue(hass, call)

    async def build_room_payload(call: ServiceCall) -> None:
        await _handle_build_room_payload(hass, call)

    async def get_queue_state(call: ServiceCall) -> dict:
        return await _handle_get_queue_state(hass, call)

    async def get_payload_state(call: ServiceCall) -> dict:
        return await _handle_get_payload_state(hass, call)

    async def clear_queue(call: ServiceCall) -> None:
        await _handle_clear_queue(hass, call)

    async def get_active_job(call: ServiceCall) -> dict:
        return await _handle_get_active_job(hass, call)

    async def get_job_progress_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_job_progress_snapshot(hass, call)

    async def get_job_control_state(call: ServiceCall) -> dict:
        return await _handle_get_job_control_state(hass, call)

    async def get_pause_timeout_settings(call: ServiceCall) -> dict:
        return await _handle_get_pause_timeout_settings(hass, call)

    async def set_pause_timeout_settings(call: ServiceCall) -> dict:
        return await _handle_set_pause_timeout_settings(hass, call)

    async def get_upkeep_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_upkeep_snapshot(hass, call)

    async def get_dashboard_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_dashboard_snapshot(hass, call)

    async def get_dock_action_status(call: ServiceCall) -> dict:
        return await _handle_get_dock_action_status(hass, call)

    async def clear_active_job(call: ServiceCall) -> None:
        await _handle_clear_active_job(hass, call)

    async def get_lifecycle_state(call: ServiceCall) -> dict:
        return await _handle_get_lifecycle_state(hass, call)

    async def get_start_status(call: ServiceCall) -> dict:
        return await _handle_get_start_status(hass, call)

    async def start_selected_rooms(call: ServiceCall) -> None:
        await _handle_start_selected_rooms(hass, call)

    async def start_run_profile(call: ServiceCall) -> dict:
        return await _handle_start_run_profile(hass, call)

    async def pause_active_job(call: ServiceCall) -> dict:
        return await _handle_pause_active_job(hass, call)

    async def resume_active_job(call: ServiceCall) -> dict:
        return await _handle_resume_active_job(hass, call)

    async def cancel_active_job(call: ServiceCall) -> dict:
        return await _handle_cancel_active_job(hass, call)

    async def wash_mop(call: ServiceCall) -> dict:
        return await _handle_wash_mop(hass, call)

    async def dry_mop(call: ServiceCall) -> dict:
        return await _handle_dry_mop(hass, call)

    async def empty_dust(call: ServiceCall) -> dict:
        return await _handle_empty_dust(hass, call)

    async def stop_dry_mop(call: ServiceCall) -> dict:
        return await _handle_stop_dry_mop(hass, call)

    async def reset_maintenance(call: ServiceCall) -> dict:
        return await _handle_reset_maintenance(hass, call)

    async def set_dock_event_count(call: ServiceCall) -> dict:
        return await _handle_set_dock_event_count(hass, call)

    async def get_room_profiles(call: ServiceCall) -> dict:
        return await _handle_get_room_profiles(hass, call)

    async def save_user_room_profile(call: ServiceCall) -> dict:
        return await _handle_save_user_room_profile(hass, call)

    async def overwrite_room_profile(call: ServiceCall) -> dict:
        return await _handle_overwrite_room_profile(hass, call)

    async def save_room_profile_from_room(call: ServiceCall) -> dict:
        return await _handle_save_room_profile_from_room(hass, call)

    async def overwrite_room_profile_from_room(call: ServiceCall) -> dict:
        return await _handle_overwrite_room_profile_from_room(hass, call)

    async def rename_room_profile(call: ServiceCall) -> dict:
        return await _handle_rename_room_profile(hass, call)

    async def delete_room_profile(call: ServiceCall) -> dict:
        return await _handle_delete_room_profile(hass, call)

    async def apply_room_profile(call: ServiceCall) -> dict:
        return await _handle_apply_room_profile(hass, call)

    async def get_saved_run_profiles(call: ServiceCall) -> dict:
        return await _handle_get_saved_run_profiles(hass, call)

    async def get_room_access_editor(call: ServiceCall) -> dict:
        return await _handle_get_room_access_editor(hass, call)

    async def get_access_graph_health(call: ServiceCall) -> dict:
        return await _handle_get_access_graph_health(hass, call)

    async def save_run_profile(call: ServiceCall) -> dict:
        return await _handle_save_run_profile(hass, call)

    async def apply_run_profile(call: ServiceCall) -> dict:
        return await _handle_apply_run_profile(hass, call)

    async def rename_run_profile(call: ServiceCall) -> dict:
        return await _handle_rename_run_profile(hass, call)

    async def overwrite_run_profile(call: ServiceCall) -> dict:
        return await _handle_overwrite_run_profile(hass, call)

    async def delete_run_profile(call: ServiceCall) -> dict:
        return await _handle_delete_run_profile(hass, call)

    async def update_room_fields(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.update_room_fields(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            room_id=int(call.data["room_id"]),
            clean_mode=call.data.get("clean_mode"),
            fan_speed=call.data.get("fan_speed"),
            water_level=call.data.get("water_level"),
            clean_intensity=call.data.get("clean_intensity"),
            clean_passes=call.data.get("clean_passes"),
            edge_mopping=call.data.get("edge_mopping"),
            is_dock_room=call.data.get("is_dock_room"),
            is_transition=call.data.get("is_transition"),
            grants_access_to=call.data.get("grants_access_to"),
            rules=call.data.get("rules"),
        )
        if result.get("updated"):
            await manager.async_save()
        _LOGGER.debug("update_room_fields: %s", result)
        return result

    async def get_vacuum_capabilities(call: ServiceCall) -> dict:
        return await _handle_get_vacuum_capabilities(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISCOVER_ROOMS,
        discover_rooms,
        schema=DISCOVER_ROOMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_MANAGED_ROOMS,
        save_managed_rooms,
        schema=SAVE_MANAGED_ROOMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_VACUUM_MAPS,
        get_vacuum_maps,
        schema=GET_VACUUM_MAPS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BUILD_QUEUE,
        build_queue,
        schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BUILD_ROOM_PAYLOAD,
        build_room_payload,
        schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_QUEUE_STATE,
        get_queue_state,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PAYLOAD_STATE,
        get_payload_state,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_QUEUE,
        clear_queue,
        schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ACTIVE_JOB,
        get_active_job,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_JOB_PROGRESS_SNAPSHOT,
        get_job_progress_snapshot,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_JOB_CONTROL_STATE,
        get_job_control_state,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
        get_pause_timeout_settings,
        schema=VACUUM_ONLY_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
        set_pause_timeout_settings,
        schema=PAUSE_TIMEOUT_SETTINGS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_UPKEEP_SNAPSHOT,
        get_upkeep_snapshot,
        schema=VACUUM_ONLY_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DASHBOARD_SNAPSHOT,
        get_dashboard_snapshot,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DOCK_ACTION_STATUS,
        get_dock_action_status,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_ACTIVE_JOB,
        clear_active_job,
        schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LIFECYCLE_STATE,
        get_lifecycle_state,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_START_STATUS,
        get_start_status,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SELECTED_ROOMS,
        start_selected_rooms,
        schema=START_SELECTED_ROOMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_RUN_PROFILE,
        start_run_profile,
        schema=START_RUN_PROFILE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAUSE_ACTIVE_JOB,
        pause_active_job,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_ACTIVE_JOB,
        resume_active_job,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_ACTIVE_JOB,
        cancel_active_job,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WASH_MOP,
        wash_mop,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DRY_MOP,
        dry_mop,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EMPTY_DUST,
        empty_dust,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_DRY_MOP,
        stop_dry_mop,
        schema=JOB_CONTROL_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_MAINTENANCE,
        reset_maintenance,
        schema=RESET_MAINTENANCE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DOCK_EVENT_COUNT,
        set_dock_event_count,
        schema=SET_DOCK_EVENT_COUNT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ROOM_PROFILES,
        get_room_profiles,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_USER_ROOM_PROFILE,
        save_user_room_profile,
        schema=SAVE_USER_ROOM_PROFILE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OVERWRITE_ROOM_PROFILE,
        overwrite_room_profile,
        schema=OVERWRITE_ROOM_PROFILE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
        save_room_profile_from_room,
        schema=SAVE_ROOM_PROFILE_FROM_ROOM_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
        overwrite_room_profile_from_room,
        schema=OVERWRITE_ROOM_PROFILE_FROM_ROOM_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RENAME_ROOM_PROFILE,
        rename_room_profile,
        schema=RENAME_ROOM_PROFILE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_ROOM_PROFILE,
        delete_room_profile,
        schema=DELETE_ROOM_PROFILE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_ROOM_PROFILE,
        apply_room_profile,
        schema=APPLY_ROOM_PROFILE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ROOM_ACCESS_EDITOR,
        get_room_access_editor,
        schema=ROOM_ACCESS_EDITOR_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ACCESS_GRAPH_HEALTH,
        get_access_graph_health,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SAVED_RUN_PROFILES,
        get_saved_run_profiles,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_RUN_PROFILE,
        save_run_profile,
        schema=RUN_PROFILE_NAME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_RUN_PROFILE,
        apply_run_profile,
        schema=RUN_PROFILE_ID_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OVERWRITE_RUN_PROFILE,
        overwrite_run_profile,
        schema=RUN_PROFILE_OVERWRITE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RENAME_RUN_PROFILE,
        rename_run_profile,
        schema=RUN_PROFILE_RENAME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_RUN_PROFILE,
        delete_run_profile,
        schema=RUN_PROFILE_ID_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_ROOM_FIELDS,
        update_room_fields,
        schema=UPDATE_ROOM_FIELDS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_VACUUM_CAPABILITIES,
        get_vacuum_capabilities,
        schema=GET_VACUUM_CAPABILITIES_SCHEMA,
        supports_response=True,
    )

    # ----------------------------------------------------------------------
    # Setup services (panel-driven)
    # ----------------------------------------------------------------------

    from .setup.workflow import add_vacuum as _add_vacuum
    from .setup.workflow import import_active_map as _import_active_map
    from .setup.status import get_setup_status as _get_setup_status
    from .setup.delete import delete_map as _delete_map

    SETUP_ADD_VACUUM_SCHEMA = vol.Schema(
        {vol.Required("vacuum_entity_id"): cv.entity_id}
    )
    SETUP_IMPORT_MAP_SCHEMA = vol.Schema(
        {vol.Required("vacuum_entity_id"): cv.entity_id}
    )
    SETUP_GET_STATUS_SCHEMA = vol.Schema({})
    SETUP_GET_MAP_ROOMS_SCHEMA = vol.Schema(
        {
            vol.Required("vacuum_entity_id"): cv.entity_id,
            vol.Required("map_id"): cv.string,
        }
    )
    SETUP_SAVE_ROOMS_SCHEMA = vol.Schema(
        {
            vol.Required("vacuum_entity_id"): cv.entity_id,
            vol.Required("map_id"): cv.string,
            vol.Optional("enabled_room_ids"): vol.All(
                cv.ensure_list, [vol.Coerce(int)]
            ),
            vol.Optional("floor_types"): vol.Schema({cv.string: cv.string}),
        }
    )
    SETUP_DELETE_MAP_SCHEMA = vol.Schema(
        {
            vol.Required("vacuum_entity_id"): cv.entity_id,
            vol.Required("map_id"): cv.string,
            # confirmation_token: truthy string for elevated; map display name for high
            vol.Optional("confirmation_token"): cv.string,
        }
    )

    async def setup_get_status(call: ServiceCall) -> dict:
        return _get_setup_status(hass)

    async def setup_add_vacuum(call: ServiceCall) -> dict:
        return await _add_vacuum(hass, call.data["vacuum_entity_id"])

    async def setup_import_active_map(call: ServiceCall) -> dict:
        return await _import_active_map(hass, call.data["vacuum_entity_id"])

    async def setup_get_map_rooms(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"rooms": [], "vacuum_entity_id": call.data["vacuum_entity_id"], "map_id": call.data["map_id"]}
        result = manager.get_managed_rooms(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
        )
        rooms_dict = result.get("rooms", {})
        rooms_list = sorted(
            [
                {
                    "room_id": int(room.get("room_id", rid)),
                    "name": str(room.get("name", f"Room {rid}")),
                    "floor_type": str(room.get("floor_type", "hardwood")),
                }
                for rid, room in rooms_dict.items()
                if isinstance(room, dict)
            ],
            key=lambda r: r["room_id"],
        )
        return {
            "vacuum_entity_id": call.data["vacuum_entity_id"],
            "map_id": str(call.data["map_id"]),
            "rooms": rooms_list,
        }

    async def setup_save_rooms(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        result = manager.save_managed_rooms(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            enabled_room_ids=call.data.get("enabled_room_ids"),
            floor_types=call.data.get("floor_types") or {},
        )
        await manager.async_save()
        return {"status": "success", "room_count": result.get("room_count", 0)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_GET_STATUS,
        setup_get_status,
        schema=SETUP_GET_STATUS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_ADD_VACUUM,
        setup_add_vacuum,
        schema=SETUP_ADD_VACUUM_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_IMPORT_MAP,
        setup_import_active_map,
        schema=SETUP_IMPORT_MAP_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_GET_MAP_ROOMS,
        setup_get_map_rooms,
        schema=SETUP_GET_MAP_ROOMS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_SAVE_ROOMS,
        setup_save_rooms,
        schema=SETUP_SAVE_ROOMS_SCHEMA,
        supports_response=True,
    )

    async def setup_delete_map(call: ServiceCall) -> dict:
        return await _delete_map(
            hass,
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            confirmation_token=call.data.get("confirmation_token"),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_DELETE_MAP,
        setup_delete_map,
        schema=SETUP_DELETE_MAP_SCHEMA,
        supports_response=True,
    )



async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    for service_name in (
        SERVICE_SETUP_GET_STATUS,
        SERVICE_SETUP_ADD_VACUUM,
        SERVICE_SETUP_IMPORT_MAP,
        SERVICE_SETUP_GET_MAP_ROOMS,
        SERVICE_SETUP_SAVE_ROOMS,
        SERVICE_SETUP_DELETE_MAP,
        SERVICE_DISCOVER_ROOMS,
        SERVICE_SAVE_MANAGED_ROOMS,
        SERVICE_GET_VACUUM_MAPS,
        SERVICE_BUILD_QUEUE,
        SERVICE_BUILD_ROOM_PAYLOAD,
        SERVICE_GET_QUEUE_STATE,
        SERVICE_GET_PAYLOAD_STATE,
        SERVICE_CLEAR_QUEUE,
        SERVICE_GET_ACTIVE_JOB,
        SERVICE_GET_JOB_PROGRESS_SNAPSHOT,
        SERVICE_GET_JOB_CONTROL_STATE,
        SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
        SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
        SERVICE_GET_UPKEEP_SNAPSHOT,
        SERVICE_GET_DASHBOARD_SNAPSHOT,
        SERVICE_GET_DOCK_ACTION_STATUS,
        SERVICE_CLEAR_ACTIVE_JOB,
        SERVICE_GET_LIFECYCLE_STATE,
        SERVICE_GET_START_STATUS,
        SERVICE_START_SELECTED_ROOMS,
        SERVICE_PAUSE_ACTIVE_JOB,
        SERVICE_RESUME_ACTIVE_JOB,
        SERVICE_CANCEL_ACTIVE_JOB,
        SERVICE_WASH_MOP,
        SERVICE_DRY_MOP,
        SERVICE_EMPTY_DUST,
        SERVICE_STOP_DRY_MOP,
        SERVICE_RESET_MAINTENANCE,
        SERVICE_GET_ROOM_PROFILES,
        SERVICE_SAVE_USER_ROOM_PROFILE,
        SERVICE_OVERWRITE_ROOM_PROFILE,
        SERVICE_APPLY_ROOM_PROFILE,
        SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
        SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
        SERVICE_RENAME_ROOM_PROFILE,
        SERVICE_DELETE_ROOM_PROFILE,
        SERVICE_UPDATE_ROOM_FIELDS,
        SERVICE_GET_ROOM_ACCESS_EDITOR,
        SERVICE_GET_ACCESS_GRAPH_HEALTH,
        SERVICE_GET_SAVED_RUN_PROFILES,
        SERVICE_SAVE_RUN_PROFILE,
        SERVICE_APPLY_RUN_PROFILE,
        SERVICE_OVERWRITE_RUN_PROFILE,
        SERVICE_RENAME_RUN_PROFILE,
        SERVICE_DELETE_RUN_PROFILE,
        SERVICE_START_RUN_PROFILE,
        SERVICE_GET_VACUUM_CAPABILITIES,
    ):
        hass.services.async_remove(DOMAIN, service_name)
