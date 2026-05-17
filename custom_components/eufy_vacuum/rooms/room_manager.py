"""Builds and summarizes managed room configuration from discovered room data."""

from __future__ import annotations

from typing import Any

from ..models.models import RoomConfig


def _normalize_enabled_room_ids(enabled_room_ids: list[int] | list[str] | None) -> set[int]:
    """Normalize enabled room IDs into a clean integer set."""
    if not enabled_room_ids:
        return set()

    normalized: set[int] = set()

    for raw_room_id in enabled_room_ids:
        try:
            normalized.add(int(raw_room_id))
        except (TypeError, ValueError):
            continue

    return normalized


def build_managed_rooms(
    *,
    discovered_rooms: list[dict[str, Any]],
    existing_rooms: dict[str, Any] | None = None,
    enabled_room_ids: list[int] | list[str] | None = None,
    floor_types: dict[int, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a managed room dict keyed by room_id string from discovered rooms.

    Only rooms in ``enabled_room_ids`` are included when that list is supplied.
    Existing per-room settings are preserved for rooms that are still discovered;
    new rooms receive safe defaults.
    """
    existing_rooms = existing_rooms or {}
    floor_types = floor_types or {}
    explicit_enabled_ids = _normalize_enabled_room_ids(enabled_room_ids)
    has_explicit_enabled_ids = enabled_room_ids is not None

    managed: dict[str, dict[str, Any]] = {}

    for index, room in enumerate(discovered_rooms, start=1):
        room_id = int(room["room_id"])
        room_id_key = str(room_id)

        if has_explicit_enabled_ids and room_id not in explicit_enabled_ids:
            continue

        existing = existing_rooms.get(room_id_key, {})

        # Wizard-supplied floor type takes priority over any stored value;
        # the value encodes carpet pile height (e.g. "carpet_low_pile").
        floor_type = (
            floor_types.get(room_id)
            or floor_types.get(str(room_id))
            or str(existing.get("floor_type", "hardwood"))
        )

        # Calling build_managed_rooms with a room ID in enabled_room_ids
        # is the user's explicit approval — stamp is_configured=True.
        # Preserve a previous configured_at when present; otherwise set
        # now so the response includes a defined timestamp.
        from ..learning.utils import _iso_now
        existing_configured_at = existing.get("configured_at")

        room_config = RoomConfig(
            room_id=room_id,
            map_id=str(room["map_id"]),
            name=str(room["name"]),
            slug=room.get("slug"),
            enabled=bool(existing.get("enabled", True)),
            order=int(existing.get("order", index)),
            profile_name=str(existing.get("profile_name", "vacuum_quick")),
            floor_type=floor_type,
            clean_mode=str(existing.get("clean_mode", "vacuum")),
            fan_speed=str(existing.get("fan_speed", "Max")),
            water_level=str(existing.get("water_level", "Off")),
            clean_intensity=str(existing.get("clean_intensity", "Standard")),
            clean_passes=int(existing.get("clean_passes", 1)),
            edge_mopping=bool(existing.get("edge_mopping", False)),
            path_type=existing.get("path_type"),
            is_dock_room=bool(existing.get("is_dock_room", False)),
            grants_access_to=list(existing.get("grants_access_to", [])),
            rules=list(existing.get("rules", [])),
            is_configured=True,
            configured_at=existing_configured_at or _iso_now(),
        )

        managed[room_id_key] = room_config.as_dict()

    return managed


def build_room_selection_summary(
    *,
    managed_rooms: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact summary for services, entities, and card consumption."""
    enabled_rooms: list[dict[str, Any]] = []
    disabled_rooms: list[dict[str, Any]] = []

    for room_id_key, room in managed_rooms.items():
        target = enabled_rooms if room.get("enabled", False) else disabled_rooms
        target.append(
            {
                "room_id": int(room_id_key),
                "name": room.get("name"),
                "slug": room.get("slug"),
                "order": room.get("order", 0),
                "profile_name": room.get("profile_name", "vacuum_quick"),
                "floor_type": room.get("floor_type", "hardwood"),
                "clean_passes": room.get("clean_passes", 1),
                "edge_mopping": room.get("edge_mopping", False),
                "carpet": str(room.get("floor_type", "")).startswith("carpet"),
            }
        )

    enabled_rooms.sort(key=lambda item: (int(item.get("order", 0)), str(item.get("name", ""))))
    disabled_rooms.sort(key=lambda item: str(item.get("name", "")))

    return {
        "enabled_count": len(enabled_rooms),
        "disabled_count": len(disabled_rooms),
        "enabled_rooms": enabled_rooms,
        "disabled_rooms": disabled_rooms,
    }