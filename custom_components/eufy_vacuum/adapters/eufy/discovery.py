"""
Eufy-specific room discovery functions for the Eufy adapter.

Reads room segment data from the Eufy/robovac_mqtt HA entity surface
and normalizes it into the framework's room shape.

get_active_map_id() — reads sensor.{object_id}_active_map to return
                      the currently active map ID.
discover_rooms_for_vacuum() — reads the `segments` attribute from the
                              vacuum entity and returns normalized room
                              dicts.

The `segments` attribute shape expected by discover_rooms_for_vacuum():
    list of dicts, each containing:
        "id":   int | str   — the room ID
        "name": str         — the room display name

This is the Eufy/robovac_mqtt specific attribute format. A port to a
different brand replaces these two functions with equivalents that read
from that brand's entity surface. The return shapes must be preserved.

Return shape of get_active_map_id():
    str | None — the active map ID string, or None if unavailable

Return shape of discover_rooms_for_vacuum():
    list[dict] where each dict contains:
        room_id: int
        map_id:  str
        name:    str
        slug:    str
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .entities import build_entity_id, SUFFIX_ACTIVE_MAP, DOMAIN_SENSOR
from ..registry import get_adapter_config
from ...rooms.utils import slugify_room_name

_LOGGER = logging.getLogger(__name__)


def get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None:
    """Return the active map ID for a vacuum, if available."""
    state = hass.states.get(build_entity_id(vacuum_entity_id, SUFFIX_ACTIVE_MAP))

    if state is None:
        _LOGGER.debug("Active map sensor missing for %s", vacuum_entity_id)
        return None

    value = state.state
    if value in {"unknown", "unavailable", "", "none", "None"}:
        _LOGGER.debug("Active map sensor invalid value for %s: %s", vacuum_entity_id, value)
        return None

    return str(value)


def discover_rooms_for_vacuum(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return normalized room dicts from the vacuum's segments attribute.

    Does not persist. Returns an empty list if the vacuum state or segments
    are unavailable.
    """
    vacuum_state = hass.states.get(vacuum_entity_id)
    if vacuum_state is None:
        _LOGGER.debug("Vacuum state missing for %s", vacuum_entity_id)
        return []

    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id) or "unknown"

    config = get_adapter_config(vacuum_entity_id)
    discovery = (config or {}).get("discovery", {})

    # Registry-sourced discovery config with Eufy fallbacks
    room_list_attribute = discovery.get("room_list_attribute") or "segments"
    room_id_key = discovery.get("room_id_key") or "id"
    room_name_key = discovery.get("room_name_key") or "name"

    segments = vacuum_state.attributes.get(room_list_attribute)
    if not isinstance(segments, list):
        _LOGGER.debug("Segments missing or invalid for %s", vacuum_entity_id)
        return []

    rooms: list[dict[str, Any]] = []
    seen_room_ids: set[int] = set()

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        raw_name = segment.get(room_name_key)
        raw_id = segment.get(room_id_key)

        if raw_name is None or raw_id is None:
            continue

        try:
            room_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if room_id in seen_room_ids:
            continue

        seen_room_ids.add(room_id)

        name = str(raw_name).strip()
        if not name:
            continue

        rooms.append(
            {
                "room_id": room_id,
                "map_id": str(resolved_map_id),
                "name": name,
                "slug": slugify_room_name(name),
            }
        )

    return rooms
