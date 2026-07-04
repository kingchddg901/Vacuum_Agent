"""Room discovery + map + per-room field services.

Four services:
- discover_rooms: discover rooms from the vacuum (also updates drift)
- save_managed_rooms: persist the selected-rooms config
- get_vacuum_maps: list maps for a vacuum
- update_room_fields: write per-room field overrides
"""

from __future__ import annotations

import logging
import re

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_DISCOVER_ROOMS,
    SERVICE_GET_VACUUM_MAPS,
    SERVICE_RECONCILE_ROOM,
    SERVICE_SAVE_MANAGED_ROOMS,
    SERVICE_UPDATE_ROOM_FIELDS,
)
from ._common import get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


def _hex_color_or_none(value):
    """Validate a per-room fill color: canonical ``#rrggbb`` (lowercased), or None to clear.

    Accepts ``#rgb`` / ``#rrggbb`` with or without the leading ``#``; None or an empty string
    clears the override. Mirrors the frontend ``normalizeHex`` so storage stays canonical and the
    render paths never see a value they'd silently drop. Anything else is rejected at the boundary.
    """
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    if not s.startswith("#"):
        s = f"#{s}"
    if re.fullmatch(r"#[0-9a-f]{6}", s):
        return s
    if re.fullmatch(r"#[0-9a-f]{3}", s):
        return "#" + "".join(c * 2 for c in s[1:])
    raise vol.Invalid("color must be a '#rrggbb' / '#rgb' hex string or null")


SERVICES = (
    SERVICE_DISCOVER_ROOMS,
    SERVICE_SAVE_MANAGED_ROOMS,
    SERVICE_GET_VACUUM_MAPS,
    SERVICE_UPDATE_ROOM_FIELDS,
    SERVICE_RECONCILE_ROOM,
)


_DISCOVER_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
    }
)

_RECONCILE_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("action", default="migrate"): vol.In(["migrate", "ignore"]),
    }
)

_SAVE_MANAGED_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Optional("enabled_room_ids"): vol.All(
            cv.ensure_list,
            [vol.Coerce(int)],
        ),
    }
)

_GET_VACUUM_MAPS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)

_UPDATE_ROOM_FIELDS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
        vol.Optional("enabled"): cv.boolean,
        vol.Optional("clean_mode"): cv.string,
        vol.Optional("fan_speed"): cv.string,
        vol.Optional("water_level"): cv.string,
        vol.Optional("clean_intensity"): cv.string,
        vol.Optional("clean_passes"): vol.Coerce(int),
        vol.Optional("edge_mopping"): cv.boolean,
        vol.Optional("color"): _hex_color_or_none,
        vol.Optional("is_dock_room"): cv.boolean,
        vol.Optional("is_transition"): cv.boolean,
        vol.Optional("grants_access_to"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional("rules"): vol.All(cv.ensure_list, [dict]),
    }
)


async def _handle_discover_rooms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Discover rooms from the vacuum integration.

    Also runs a drift-history update so the setup tab's new-room /
    removed-room signals stay in sync after a manual rescan. The
    automatic discovery triggers (vacuum_docked, active_map_changed,
    periodic safety net) wired in listeners/discovery.py keep drift
    fresh in normal operation; this is the manual-trigger equivalent.
    """
    from ..setup.drift import run_discovery_pass
    from ..rooms.source_refresh import async_refresh_room_source

    manager = get_manager(hass)
    call_data = resolved_call_data(hass, call)
    vacuum_entity_id = call_data.get("vacuum_entity_id")

    # Service-response brands (Roborock: rooms live in the get_maps response,
    # not an attribute) need the source cache refreshed BEFORE the sync
    # discovery reads it. No-op for attribute brands (Eufy).
    if vacuum_entity_id:
        await async_refresh_room_source(hass, vacuum_entity_id)

    try:
        payload = manager.discover_rooms(**call_data)
    except Exception as err:
        raise HomeAssistantError(f"Failed to discover rooms: {err}") from err
    _LOGGER.debug("discover_rooms complete: %s", payload)

    if vacuum_entity_id:
        try:
            run_discovery_pass(hass, manager, vacuum_entity_id)
        except Exception:  # pragma: no cover - best-effort drift update
            _LOGGER.exception(
                "discover_rooms: drift update failed for %s",
                vacuum_entity_id,
            )

    await manager.async_save()


async def _handle_save_managed_rooms(hass: HomeAssistant, call: ServiceCall) -> None:
    """Save selected rooms as managed configuration."""
    try:
        payload = get_manager(hass).save_managed_rooms(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to save managed rooms: {err}") from err
    _LOGGER.debug("save_managed_rooms complete: %s", payload)
    await get_manager(hass).async_save()


async def _handle_get_vacuum_maps(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get all maps for a vacuum."""
    payload = get_manager(hass).get_vacuum_maps(**call.data)
    _LOGGER.debug("get_vacuum_maps complete: %s", payload)
    return payload


async def _handle_reconcile_room(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply or dismiss the identity-shift reviews for one vacuum/map.

    ``action=migrate`` rebuilds the saved rooms onto their new segment ids
    (carrying durable settings + rewriting access-graph grants); ``ignore``
    dismisses the reviews and leaves stored data untouched.
    """
    manager = get_manager(hass)
    data = resolved_call_data(hass, call)
    try:
        result = manager.reconcile_room(
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
            action=data.get("action", "migrate"),
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to reconcile room: {err}") from err
    _LOGGER.debug("reconcile_room: %s", result)
    await manager.async_save()
    return result


async def _handle_update_room_fields(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply per-room field overrides without a named profile."""
    manager = get_manager(hass)
    data = resolved_call_data(hass, call)
    # `color` is passed ONLY when the caller supplied it, so the manager can tell "leave the color
    # untouched" (key absent) from "clear the override" (key present, value None) — an automation
    # touching only fan_speed must not wipe a room's color.
    color_kwargs = {"color": data["color"]} if "color" in data else {}
    try:
        result = manager.update_room_fields(
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
            room_id=int(data["room_id"]),
            enabled=data.get("enabled"),
            clean_mode=data.get("clean_mode"),
            fan_speed=data.get("fan_speed"),
            water_level=data.get("water_level"),
            clean_intensity=data.get("clean_intensity"),
            clean_passes=data.get("clean_passes"),
            edge_mopping=data.get("edge_mopping"),
            is_dock_room=data.get("is_dock_room"),
            is_transition=data.get("is_transition"),
            grants_access_to=data.get("grants_access_to"),
            rules=data.get("rules"),
            **color_kwargs,
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to update room fields: {err}") from err
    if result.get("updated"):
        await manager.async_save()
    _LOGGER.debug("update_room_fields: %s", result)
    return result


def register(hass: HomeAssistant) -> None:
    """Register room services."""

    async def discover_rooms(call: ServiceCall) -> None:
        await _handle_discover_rooms(hass, call)

    async def save_managed_rooms(call: ServiceCall) -> None:
        await _handle_save_managed_rooms(hass, call)

    async def get_vacuum_maps(call: ServiceCall) -> dict:
        return await _handle_get_vacuum_maps(hass, call)

    async def update_room_fields(call: ServiceCall) -> dict:
        return await _handle_update_room_fields(hass, call)

    async def reconcile_room(call: ServiceCall) -> dict:
        return await _handle_reconcile_room(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_DISCOVER_ROOMS, discover_rooms, schema=_DISCOVER_ROOMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_MANAGED_ROOMS, save_managed_rooms,
        schema=_SAVE_MANAGED_ROOMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_VACUUM_MAPS, get_vacuum_maps,
        schema=_GET_VACUUM_MAPS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_ROOM_FIELDS, update_room_fields,
        schema=_UPDATE_ROOM_FIELDS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RECONCILE_ROOM, reconcile_room,
        schema=_RECONCILE_ROOM_SCHEMA, supports_response=True,
    )
