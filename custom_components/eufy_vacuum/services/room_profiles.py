"""Room-profile library services — read / save / overwrite / rename / delete / apply.

Eight services for the room-profile library and per-room application.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_APPLY_ROOM_PROFILE,
    SERVICE_DELETE_ROOM_PROFILE,
    SERVICE_GET_ROOM_PROFILES,
    SERVICE_OVERWRITE_ROOM_PROFILE,
    SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
    SERVICE_RENAME_ROOM_PROFILE,
    SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
    SERVICE_SAVE_USER_ROOM_PROFILE,
)
from ._common import get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_ROOM_PROFILES,
    SERVICE_SAVE_USER_ROOM_PROFILE,
    SERVICE_OVERWRITE_ROOM_PROFILE,
    SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM,
    SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM,
    SERVICE_RENAME_ROOM_PROFILE,
    SERVICE_DELETE_ROOM_PROFILE,
    SERVICE_APPLY_ROOM_PROFILE,
)


_SAVE_USER_ROOM_PROFILE_SCHEMA = vol.Schema(
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

_SAVE_ROOM_PROFILE_FROM_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
        vol.Required("label"): cv.string,
        vol.Optional("profile_name"): cv.string,
    }
)

_OVERWRITE_ROOM_PROFILE_SCHEMA = vol.Schema(
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

_OVERWRITE_ROOM_PROFILE_FROM_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
        vol.Required("profile_name"): cv.string,
        vol.Optional("label"): cv.string,
    }
)

_RENAME_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_name"): cv.string,
        vol.Optional("new_profile_name"): cv.string,
        vol.Optional("label"): cv.string,
    }
)

_DELETE_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_name"): cv.string,
    }
)

_APPLY_ROOM_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("room_ids"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required("profile_name"): cv.string,
    }
)


async def _handle_get_room_profiles(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get all available room profiles."""
    payload = get_manager(hass).get_room_profiles()
    _LOGGER.debug("get_room_profiles complete: %s", payload)
    return payload


async def _handle_save_user_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save a custom room profile."""
    payload = get_manager(hass).save_user_room_profile(**call.data)
    _LOGGER.debug("save_user_room_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_overwrite_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one existing custom room profile."""
    payload = get_manager(hass).overwrite_room_profile(**call.data)
    _LOGGER.debug("overwrite_room_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_save_room_profile_from_room(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save a custom room profile from one room's current settings."""
    payload = get_manager(hass).save_room_profile_from_room(**resolved_call_data(hass, call))
    _LOGGER.debug("save_room_profile_from_room complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_overwrite_room_profile_from_room(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one existing custom room profile from one room's current settings."""
    payload = get_manager(hass).overwrite_room_profile_from_room(**resolved_call_data(hass, call))
    _LOGGER.debug("overwrite_room_profile_from_room complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_rename_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Rename one custom room profile key and/or label."""
    payload = get_manager(hass).rename_room_profile(**call.data)
    _LOGGER.debug("rename_room_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_delete_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete one custom room profile."""
    payload = get_manager(hass).delete_room_profile(**call.data)
    _LOGGER.debug("delete_room_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_apply_room_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply a profile to one or more rooms."""
    payload = get_manager(hass).apply_room_profile(**resolved_call_data(hass, call))
    _LOGGER.debug("apply_room_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register room-profile services."""

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

    hass.services.async_register(
        DOMAIN, SERVICE_GET_ROOM_PROFILES, get_room_profiles, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_USER_ROOM_PROFILE, save_user_room_profile,
        schema=_SAVE_USER_ROOM_PROFILE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OVERWRITE_ROOM_PROFILE, overwrite_room_profile,
        schema=_OVERWRITE_ROOM_PROFILE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM, save_room_profile_from_room,
        schema=_SAVE_ROOM_PROFILE_FROM_ROOM_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM, overwrite_room_profile_from_room,
        schema=_OVERWRITE_ROOM_PROFILE_FROM_ROOM_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RENAME_ROOM_PROFILE, rename_room_profile,
        schema=_RENAME_ROOM_PROFILE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ROOM_PROFILE, delete_room_profile,
        schema=_DELETE_ROOM_PROFILE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_ROOM_PROFILE, apply_room_profile,
        schema=_APPLY_ROOM_PROFILE_SCHEMA, supports_response=True,
    )
