"""Job control services — start / pause / resume / cancel / clear / inspect.

Twelve services covering the active-job lifecycle:
- get_start_status: pre-start readiness
- start_selected_rooms: start the queued job
- start_run_profile: apply + start a saved profile
- start_zone_clean: ad-hoc free-form zone clean (fire-and-forget, no job tracking)
- pause_active_job / resume_active_job / cancel_active_job: lifecycle controls
- clear_active_job: clear local state without device interaction
- get_active_job / get_job_progress_snapshot / get_job_control_state /
  get_lifecycle_state: read-only inspection

cancel_active_job fires EVENT_JOB_FINISHED when the cancel actually
finalizes a job; the other lifecycle controls don't fire that event
themselves (the lifecycle listener / pause-timeout listener / path-
blocker listener own those firings).
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    EVENT_JOB_FINISHED,
    SERVICE_CANCEL_ACTIVE_JOB,
    SERVICE_CLEAR_ACTIVE_JOB,
    SERVICE_GET_ACTIVE_JOB,
    SERVICE_GET_JOB_CONTROL_STATE,
    SERVICE_GET_JOB_PROGRESS_SNAPSHOT,
    SERVICE_GET_LIFECYCLE_STATE,
    SERVICE_GET_START_STATUS,
    SERVICE_PAUSE_ACTIVE_JOB,
    SERVICE_RESUME_ACTIVE_JOB,
    SERVICE_START_RUN_PROFILE,
    SERVICE_START_SELECTED_ROOMS,
    SERVICE_START_ZONE_CLEAN,
)
from ._common import (
    JOB_CONTROL_SCHEMA,
    VACUUM_MAP_SCHEMA,
    get_manager,
    job_finished_event_payload,
    resolved_call_data,
)

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_START_STATUS,
    SERVICE_START_SELECTED_ROOMS,
    SERVICE_START_ZONE_CLEAN,
    SERVICE_START_RUN_PROFILE,
    SERVICE_PAUSE_ACTIVE_JOB,
    SERVICE_RESUME_ACTIVE_JOB,
    SERVICE_CANCEL_ACTIVE_JOB,
    SERVICE_CLEAR_ACTIVE_JOB,
    SERVICE_GET_ACTIVE_JOB,
    SERVICE_GET_JOB_PROGRESS_SNAPSHOT,
    SERVICE_GET_JOB_CONTROL_STATE,
    SERVICE_GET_LIFECYCLE_STATE,
)


_START_SELECTED_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Optional("confirm_reduced_run"): cv.boolean,
        vol.Optional("confirm_token"): cv.string,
        vol.Optional("path_block_action"): vol.In(
            ["event_only", "pause_and_event", "cancel_and_event"]
        ),
        vol.Optional("pause_timeout_minutes_override"): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
        # Opt-in strict room order (sequenced per-room dispatch) for brands that
        # otherwise path-optimize and ignore the order. No-op for order-honoring
        # brands.
        vol.Optional("strict_order"): cv.boolean,
    }
)

_START_RUN_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
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

# A zone rectangle: exactly four floats [x0, y0, x1, y1], normalized (0-1) to the
# live-map image with a top-left origin. Values aren't hard-range-clamped here —
# a drag to the image edge can land slightly outside, and the provider clamps.
_ZONE_RECT_SCHEMA = vol.All([vol.Coerce(float)], vol.Length(min=4, max=4))

_START_ZONE_CLEAN_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        # Optional + auto-resolved by resolved_call_data, but intentionally not
        # forwarded to the device (the provider uses its current map).
        vol.Optional("map_id"): cv.string,
        vol.Required("zones"): vol.All(
            cv.ensure_list, [_ZONE_RECT_SCHEMA], vol.Length(min=1)
        ),
        vol.Optional("clean_times", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10)
        ),
    }
)


async def _handle_get_start_status(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Check if start is allowed.

    Must NOT use async_add_executor_job — get_start_status calls
    hass.bus.async_fire internally (via _build_effective_start_plan →
    _maybe_roll_current_room_by_timing) and must stay on the event loop.
    """
    payload = get_manager(hass).get_start_status(**resolved_call_data(hass, call))
    _LOGGER.debug("get_start_status complete: %s", payload)
    return payload


async def _handle_start_selected_rooms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Start cleaning selected rooms."""
    try:
        payload = await get_manager(hass).start_selected_rooms(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to start cleaning: {err}") from err
    _LOGGER.debug("start_selected_rooms complete: %s", payload)
    await get_manager(hass).async_save()


async def _handle_start_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply and start one saved run profile."""
    try:
        payload = await get_manager(hass).start_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to start run profile: {err}") from err
    _LOGGER.debug("start_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_start_zone_clean(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Dispatch an ad-hoc free-form zone clean (draw a box on the live map → clean).

    Fire-and-forget: it carries no room ids and does NOT touch the job/queue/
    learning store, so there is no async_save() — nothing was persisted.
    """
    try:
        payload = await get_manager(hass).dispatch_zone_clean(
            **resolved_call_data(hass, call)
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to start zone clean: {err}") from err
    _LOGGER.debug("start_zone_clean complete: %s", payload)
    return payload


async def _handle_pause_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Pause one tracked active job and the underlying vacuum."""
    try:
        payload = await get_manager(hass).async_pause_active_job(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to pause job: {err}") from err
    _LOGGER.debug("pause_active_job complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_resume_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Resume one tracked paused job and the underlying vacuum."""
    try:
        payload = await get_manager(hass).async_resume_active_job(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to resume job: {err}") from err
    _LOGGER.debug("resume_active_job complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_cancel_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Cancel one tracked job, return the vacuum to base, and finalize it."""
    resolved = resolved_call_data(hass, call)
    try:
        payload = await get_manager(hass).async_cancel_active_job(**resolved)
    except Exception as err:
        raise HomeAssistantError(f"Failed to cancel job: {err}") from err
    if payload.get("cancelled"):
        hass.bus.async_fire(
            EVENT_JOB_FINISHED,
            job_finished_event_payload(
                vacuum_entity_id=resolved.get("vacuum_entity_id"),
                map_id=resolved.get("map_id"),
                result=payload.get("finalize_result"),
            ),
        )
    _LOGGER.debug("cancel_active_job complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_clear_active_job(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear active job state."""
    try:
        payload = get_manager(hass).clear_active_job(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to clear active job: {err}") from err
    _LOGGER.debug("clear_active_job complete: %s", payload)
    await get_manager(hass).async_save()


async def _handle_get_active_job(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current active job state."""
    payload = get_manager(hass).get_active_job(**resolved_call_data(hass, call))
    _LOGGER.debug("get_active_job complete: %s", payload)
    return payload


async def _handle_get_job_progress_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return canonical room-job progress state for the card."""
    payload = get_manager(hass).get_job_progress_snapshot(**resolved_call_data(hass, call))
    _LOGGER.debug("get_job_progress_snapshot complete: %s", payload)
    return payload


async def _handle_get_job_control_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return card-facing action state for one vacuum/map."""
    payload = get_manager(hass).get_job_control_state(**resolved_call_data(hass, call))
    _LOGGER.debug("get_job_control_state complete: %s", payload)
    return payload


async def _handle_get_lifecycle_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get lifecycle state for vacuum."""
    payload = get_manager(hass).get_lifecycle_state(**resolved_call_data(hass, call))
    _LOGGER.debug("get_lifecycle_state complete: %s", payload)
    return payload


def register(hass: HomeAssistant) -> None:
    """Register job-control services."""

    async def get_start_status(call: ServiceCall) -> dict:
        return await _handle_get_start_status(hass, call)

    async def start_selected_rooms(call: ServiceCall) -> None:
        await _handle_start_selected_rooms(hass, call)

    async def start_run_profile(call: ServiceCall) -> dict:
        return await _handle_start_run_profile(hass, call)

    async def start_zone_clean(call: ServiceCall) -> dict:
        return await _handle_start_zone_clean(hass, call)

    async def pause_active_job(call: ServiceCall) -> dict:
        return await _handle_pause_active_job(hass, call)

    async def resume_active_job(call: ServiceCall) -> dict:
        return await _handle_resume_active_job(hass, call)

    async def cancel_active_job(call: ServiceCall) -> dict:
        return await _handle_cancel_active_job(hass, call)

    async def clear_active_job(call: ServiceCall) -> None:
        await _handle_clear_active_job(hass, call)

    async def get_active_job(call: ServiceCall) -> dict:
        return await _handle_get_active_job(hass, call)

    async def get_job_progress_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_job_progress_snapshot(hass, call)

    async def get_job_control_state(call: ServiceCall) -> dict:
        return await _handle_get_job_control_state(hass, call)

    async def get_lifecycle_state(call: ServiceCall) -> dict:
        return await _handle_get_lifecycle_state(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_GET_START_STATUS, get_start_status,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_SELECTED_ROOMS, start_selected_rooms,
        schema=_START_SELECTED_ROOMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_RUN_PROFILE, start_run_profile,
        schema=_START_RUN_PROFILE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_ZONE_CLEAN, start_zone_clean,
        schema=_START_ZONE_CLEAN_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE_ACTIVE_JOB, pause_active_job,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESUME_ACTIVE_JOB, resume_active_job,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_ACTIVE_JOB, cancel_active_job,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_ACTIVE_JOB, clear_active_job,
        schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_ACTIVE_JOB, get_active_job,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_JOB_PROGRESS_SNAPSHOT, get_job_progress_snapshot,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_JOB_CONTROL_STATE, get_job_control_state,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_LIFECYCLE_STATE, get_lifecycle_state,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
