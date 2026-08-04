"""Access-graph services — per-room editor, whole-map health, whole-map write.

Three services, all supports_response=True:
- get_room_access_editor: payload for the per-room access editor UI
- get_access_graph_health: whole-map graph validation
- set_room_access_graph: REPLACE the whole map's graph in one atomic write

The write is replace-all because the graph is all-or-nothing by design: N
per-room writes leave the map observably half-built between them. Clearing is
the same call with no dock room and no edges, which is why there is no separate
clear service (live:AGX-CLEAR-1).
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
    SERVICE_SET_ROOM_ACCESS_GRAPH,
)
from ._common import VACUUM_MAP_SCHEMA, get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_ROOM_ACCESS_EDITOR,
    SERVICE_GET_ACCESS_GRAPH_HEALTH,
    SERVICE_SET_ROOM_ACCESS_GRAPH,
)


_ROOM_ACCESS_EDITOR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("room_id"): vol.Coerce(int),
    }
)


# Edges are PAIRS rather than a parent -> children mapping: that is what the
# builder produces (one tap is one edge), and pairs are order-independent, so a
# caller cannot express the same graph two ways.
_ACCESS_EDGE_SCHEMA = vol.Schema(
    {
        vol.Required("from"): vol.Coerce(int),
        vol.Required("to"): vol.Coerce(int),
    }
)


_SET_ROOM_ACCESS_GRAPH_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        # Both optional, and BOTH omitted is the clear operation rather than a
        # no-op — the second exit the start refusal names.
        vol.Optional("dock_room_id"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("edges"): [_ACCESS_EDGE_SCHEMA],
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


async def _handle_set_room_access_graph(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Replace one map's whole access graph (or clear it)."""
    payload = get_manager(hass).set_room_access_graph(**resolved_call_data(hass, call))
    _LOGGER.debug("set_room_access_graph complete: %s", payload)
    return payload


def register(hass: HomeAssistant) -> None:
    """Register access-graph services."""

    async def get_room_access_editor(call: ServiceCall) -> dict:
        return await _handle_get_room_access_editor(hass, call)

    async def get_access_graph_health(call: ServiceCall) -> dict:
        return await _handle_get_access_graph_health(hass, call)

    async def set_room_access_graph(call: ServiceCall) -> dict:
        return await _handle_set_room_access_graph(hass, call)

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ROOM_ACCESS_GRAPH,
        set_room_access_graph,
        schema=_SET_ROOM_ACCESS_GRAPH_SCHEMA,
        supports_response=True,
    )
