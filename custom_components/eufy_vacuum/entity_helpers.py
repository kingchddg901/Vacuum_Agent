"""Entity helper utilities for Eufy Vacuum Manager."""

from __future__ import annotations

from typing import Any


def _friendly_vacuum_name(vacuum_entity_id: str) -> str:
    """Return a title-cased display name derived from the vacuum entity_id's object_id."""
    object_id = vacuum_entity_id.split(".", 1)[1]
    return object_id.replace("_", " ").strip().title()


def build_entity_name(vacuum_entity_id: str, suffix: str) -> str:
    """Return a human-readable entity name derived from the vacuum entity_id and a suffix."""
    return f"{_friendly_vacuum_name(vacuum_entity_id)} {suffix}"


def make_room_unique_id(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_id: int,
    suffix: str,
) -> str:
    """Build a stable unique ID for a room entity."""
    vacuum_key = vacuum_entity_id.replace(".", "_")
    return f"{vacuum_key}_{map_id}_{room_id}_{suffix}"


def make_room_entity_name(
    *,
    vacuum_entity_id: str,
    room_name: str,
    label: str,
) -> str:
    """Build a friendly room entity name that stays clear in multi-vacuum homes."""
    return f"{_friendly_vacuum_name(vacuum_entity_id)} {room_name} {label}"


def sort_room_items(rooms: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Return rooms sorted by order then name."""
    items = list(rooms.items())
    items.sort(
        key=lambda item: (
            int(item[1].get("order", 999)),
            str(item[1].get("name", "")),
        )
    )
    return items


def get_floor_type_label(floor_type: str) -> str:
    """Return user-friendly floor type label.

    ``floor_type`` encodes carpet pile in the value itself (e.g.
    ``"carpet_low_pile"``) — there is no separate carpet_type field.
    """
    mapping = {
        "hardwood": "Hardwood / Engineered Wood",
        "laminate": "Laminate / Vinyl",
        "tile": "Tile / Stone",
        "marble": "Marble / Natural Stone",
        "granite": "Granite / Natural Stone",
        "concrete": "Concrete",
        "carpet_low_pile": "Carpet — Low-Pile / Thin",
        "carpet_high_pile": "Carpet — Medium/High-Pile/Shag",
        # Legacy value — kept for display of old stored data
        "carpet": "Carpet",
    }
    return mapping.get(str(floor_type), str(floor_type).replace("_", " ").title())


def get_floor_water_guidance(floor_type: str) -> str:
    """Return recommended water guidance for a floor type."""
    mapping = {
        "hardwood": "Low",
        "laminate": "Low",
        "tile": "Medium",
        "marble": "Low",
        "granite": "Low",
        "concrete": "Medium",
        "carpet_low_pile": "Vacuum only",
        "carpet_high_pile": "Vacuum only",
        "carpet": "Vacuum only",
    }
    return mapping.get(str(floor_type), "Unknown")