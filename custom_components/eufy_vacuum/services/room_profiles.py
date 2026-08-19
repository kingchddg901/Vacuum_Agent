"""Room-profile library services — read / save / overwrite / rename / delete / apply.

Eight services for the room-profile library and per-room application.
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INJ7VXE7  `maps/map_manager.py#INJ7VXE7`
#       A3-ROOMS-8 (closed RP-016): delete_room_profile / rename_room_profile leave dangling profile_name references on
#              rooms, which then silently resolve to a built-in preset
#   INJSETB0  `services/queue.py#INJSETB0`
#       A1-WIRE-4 (closed RP-032): get_room_profiles is the only one of the 79 registrations with no schema, so caller-
#              supplied scoping arguments are accepted and silently ignored
#       A3-ROOMS-4 (closed RP-032): services.yaml advertises required fields that the voluptuous schemas reject — three
#              services fail outright when the user fills the form HA renders
#   INT62M7A  `themes/services.py#INT62M7A`
#       A3-ROOMS-11: Error-surfacing is inconsistent across the area: rooms.py wraps 4 of 5 handlers,
#              room_profiles.py wraps 0 of 8, access_graph.py wraps 0 of 2
#       A3-ROOMS-5: apply_room_profile silently no-ops on unknown room ids and returns a success-shaped
#              response with no way to tell
#       A3-ROOMS-7: save_user_room_profile silently overwrites an existing custom profile and reports
#              saved: true, while its sibling rename_room_profile refuses the identical collision


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


_GET_ROOM_PROFILES_SCHEMA = vol.Schema(
    {
        # Optional so the shipped no-argument callers keep working. Supplying it
        # is what makes the BUILT-IN half of the answer brand-correct; without it
        # the response carries the saved library only and says so via
        # ``built_ins_included: false``.
        vol.Optional("vacuum_entity_id"): cv.entity_id,
    }
)


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
        vol.Optional("force", default=False): cv.boolean,
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
    """Get all available room profiles.

    Built-in profiles belong to a brand, so ``vacuum_entity_id`` selects whose are
    included. Omitting it returns the user-saved library alone rather than
    defaulting to a brand — the response flags which it is.
    """
    payload = get_manager(hass).get_room_profiles(
        vacuum_entity_id=call.data.get("vacuum_entity_id")
    )
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
        DOMAIN, SERVICE_GET_ROOM_PROFILES, get_room_profiles,
        schema=_GET_ROOM_PROFILES_SCHEMA, supports_response=True,
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
