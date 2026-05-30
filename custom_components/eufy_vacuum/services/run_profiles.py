"""Saved run-profile library services — read / save / apply / rename / overwrite / delete.

Six services for the named-runs library. The start_run_profile service
(apply + start in one shot) lives in job_control.py — it's a job
lifecycle operation, not a library mutation.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_APPLY_RUN_PROFILE,
    SERVICE_DELETE_RUN_PROFILE,
    SERVICE_GET_SAVED_RUN_PROFILES,
    SERVICE_OVERWRITE_RUN_PROFILE,
    SERVICE_RENAME_RUN_PROFILE,
    SERVICE_SAVE_RUN_PROFILE,
)
from ._common import VACUUM_MAP_SCHEMA, get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_SAVED_RUN_PROFILES,
    SERVICE_SAVE_RUN_PROFILE,
    SERVICE_APPLY_RUN_PROFILE,
    SERVICE_RENAME_RUN_PROFILE,
    SERVICE_OVERWRITE_RUN_PROFILE,
    SERVICE_DELETE_RUN_PROFILE,
)


_RUN_PROFILE_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("expose_as_button"): cv.boolean,
    }
)

_RUN_PROFILE_ID_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
    }
)

_RUN_PROFILE_OVERWRITE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("expose_as_button"): cv.boolean,
    }
)

_RUN_PROFILE_RENAME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)


async def _handle_get_saved_run_profiles(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return saved run profiles for one vacuum/map."""
    payload = get_manager(hass).get_saved_run_profiles(**resolved_call_data(hass, call))
    _LOGGER.debug("get_saved_run_profiles complete: %s", payload)
    return payload


async def _handle_save_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save current enabled-room run as a named reusable profile."""
    try:
        payload = get_manager(hass).save_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to save run profile: {err}") from err
    _LOGGER.debug("save_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_apply_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply one saved run profile back onto room selections/settings."""
    try:
        payload = get_manager(hass).apply_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to apply run profile: {err}") from err
    if not payload.get("applied") and payload.get("reason") == "profile_not_found":
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("apply_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_rename_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Rename one saved run profile."""
    try:
        payload = get_manager(hass).rename_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to rename run profile: {err}") from err
    if not payload.get("renamed") and payload.get("reason") == "profile_not_found":
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("rename_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_overwrite_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one saved run profile from the current enabled-room snapshot."""
    try:
        payload = get_manager(hass).overwrite_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to overwrite run profile: {err}") from err
    if not payload.get("overwritten") and payload.get("reason") == "profile_not_found":
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("overwrite_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_delete_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete one saved run profile."""
    try:
        payload = get_manager(hass).delete_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to delete run profile: {err}") from err
    if not payload.get("deleted") and payload.get("reason") == "profile_not_found":
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("delete_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register run-profile services."""

    async def get_saved_run_profiles(call: ServiceCall) -> dict:
        return await _handle_get_saved_run_profiles(hass, call)

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

    hass.services.async_register(
        DOMAIN, SERVICE_GET_SAVED_RUN_PROFILES, get_saved_run_profiles,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_RUN_PROFILE, save_run_profile,
        schema=_RUN_PROFILE_NAME_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_RUN_PROFILE, apply_run_profile,
        schema=_RUN_PROFILE_ID_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RENAME_RUN_PROFILE, rename_run_profile,
        schema=_RUN_PROFILE_RENAME_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OVERWRITE_RUN_PROFILE, overwrite_run_profile,
        schema=_RUN_PROFILE_OVERWRITE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_RUN_PROFILE, delete_run_profile,
        schema=_RUN_PROFILE_ID_SCHEMA, supports_response=True,
    )
