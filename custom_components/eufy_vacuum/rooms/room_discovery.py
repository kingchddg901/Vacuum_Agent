"""Reads room segment data from the vacuum's HA state and normalizes it for storage.

All brand-specific knowledge (which entity exposes the room list, which
attribute contains it, which keys hold room ID and name) comes from the
adapter registry's discovery config block. This file contains no vacuum
brand assumptions — it reads whatever the adapter declares.

Adapter config shape consumed here (adapters/config_schema.py § discovery):
    room_list_entity:    "vacuum_entity" | <full entity_id>
    room_list_attribute: str — attribute name on the entity
    room_id_key:         str — key in each room dict for the room ID
    room_name_key:       str — key in each room dict for the room name

When the adapter is not registered or discovery config is absent, both
functions degrade gracefully (return None / empty list).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .utils import slugify_room_name
from ..adapters.registry import get_adapter_config

_LOGGER = logging.getLogger(__name__)


def get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None:
    """Return the active map ID for a vacuum, if available.

    Reads the entity declared as entities.active_map in the adapter config.
    Returns None when the adapter is not registered, the entity is missing,
    or its state is an HA sentinel value.
    """
    config = get_adapter_config(vacuum_entity_id)
    active_map_entity = (config or {}).get("entities", {}).get("active_map")
    if not active_map_entity:
        _LOGGER.debug("No active_map entity declared for %s", vacuum_entity_id)
        return None

    state = hass.states.get(active_map_entity)
    if state is None:
        _LOGGER.debug("Active map entity %s missing for %s", active_map_entity, vacuum_entity_id)
        return None

    value = state.state
    if value in {"unknown", "unavailable", "", "none", "None"}:
        _LOGGER.debug("Active map entity invalid value for %s: %s", vacuum_entity_id, value)
        return None

    return str(value)


def discover_rooms_for_vacuum(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return normalized room dicts from the adapter's declared room list entity.

    Reads discovery config from the adapter registry:
      room_list_entity    — "vacuum_entity" or a full entity ID
      room_list_attribute — attribute name that holds the room list
      room_id_key         — key in each room dict for the room ID
      room_name_key       — key in each room dict for the room name

    Returns an empty list when the adapter is not registered, discovery
    config is absent, or the room list attribute is missing/invalid.
    """
    config = get_adapter_config(vacuum_entity_id)
    discovery = (config or {}).get("discovery", {})

    room_list_entity_key = discovery.get("room_list_entity")
    room_list_attribute = discovery.get("room_list_attribute")
    room_id_key = discovery.get("room_id_key")
    room_name_key = discovery.get("room_name_key")

    if not all((room_list_entity_key, room_list_attribute, room_id_key, room_name_key)):
        _LOGGER.debug(
            "Discovery config incomplete for %s — skipping room discovery",
            vacuum_entity_id,
        )
        return []

    # Resolve which entity holds the room list.
    if room_list_entity_key == "vacuum_entity":
        source_entity_id = vacuum_entity_id
    else:
        source_entity_id = room_list_entity_key

    source_state = hass.states.get(source_entity_id)
    if source_state is None:
        _LOGGER.debug(  # pragma: no cover
            "Room list entity %s missing for %s", source_entity_id, vacuum_entity_id
        )
        return []

    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id) or "unknown"

    segments = source_state.attributes.get(room_list_attribute)
    if not isinstance(segments, list):
        _LOGGER.debug(
            "Room list attribute '%s' missing or invalid for %s",
            room_list_attribute,
            vacuum_entity_id,
        )
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


def discover_rooms_payload(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> dict[str, Any]:
    """Return discovery payload shaped for storage, services, and card use."""
    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id)

    rooms = discover_rooms_for_vacuum(
        hass,
        vacuum_entity_id=vacuum_entity_id,
        map_id=resolved_map_id,
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "active_map_id": resolved_map_id,
        "room_count": len(rooms),
        "rooms": rooms,
    }
