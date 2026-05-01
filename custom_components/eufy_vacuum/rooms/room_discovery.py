"""Reads room segment data from the vacuum's HA state and normalizes it for storage."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def slugify_room_name(name: str) -> str:
    """Return a stable, URL-safe slug derived from a room name."""
    return (
        str(name)
        .strip()
        .lower()
        .replace("'", "")
        .replace('"', "")
        .replace("&", "and")
        .replace(" ", "_")
    )


def get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None:
    """Return the active map ID for a vacuum, if available."""
    object_id = vacuum_entity_id.split(".", 1)[1]
    state = hass.states.get(f"sensor.{object_id}_active_map")

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

    segments = vacuum_state.attributes.get("segments")
    if not isinstance(segments, list):
        _LOGGER.debug("Segments missing or invalid for %s", vacuum_entity_id)
        return []

    rooms: list[dict[str, Any]] = []
    seen_room_ids: set[int] = set()

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        raw_name = segment.get("name")
        raw_id = segment.get("id")

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