"""Access-graph services — per-room editor + whole-map health.

Two services, both supports_response=True:
- get_room_access_editor: payload for the per-room access editor UI
- get_access_graph_health: whole-map graph validation
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_GET_ACCESS_GRAPH_HEALTH,
    SERVICE_GET_ROOM_ACCESS_EDITOR,
)
from ._common import VACUUM_MAP_SCHEMA, get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_ROOM_ACCESS_EDITOR,
    SERVICE_GET_ACCESS_GRAPH_HEALTH,
)


_ROOM_ACCESS_EDITOR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
    }
)


async def _handle_get_room_access_editor(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return one room's access-graph editor payload."""
    payload = get_manager(hass).get_room_access_editor(**resolved_call_data(hass, call))
    _LOGGER.debug("get_room_access_editor complete: %s", payload)
    return payload


async def _handle_get_access_graph_health(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return whole-map access-graph health."""
    payload = get_manager(hass).get_access_graph_health(**resolved_call_data(hass, call))
    _LOGGER.debug("get_access_graph_health complete: %s", payload)
    return payload


def register(hass: HomeAssistant) -> None:
    """Register access-graph services."""

    async def get_room_access_editor(call: ServiceCall) -> dict:
        return await _handle_get_room_access_editor(hass, call)

    async def get_access_graph_health(call: ServiceCall) -> dict:
        return await _handle_get_access_graph_health(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ROOM_ACCESS_EDITOR,
        get_room_access_editor,
        schema=_ROOM_ACCESS_EDITOR_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ACCESS_GRAPH_HEALTH,
        get_access_graph_health,
        schema=VACUUM_MAP_SCHEMA,
        supports_response=True,
    )
