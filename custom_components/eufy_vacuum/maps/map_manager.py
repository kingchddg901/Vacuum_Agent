"""Map-scoped storage operations: create, read, rebuild, and summarize per-vacuum map buckets."""

from __future__ import annotations

from typing import Any


def ensure_map_bucket(
    *,
    data: dict[str, Any],
    vacuum_entity_id: str,
    map_id: str,
) -> dict[str, Any]:
    """Ensure a map bucket exists and return it."""
    data.setdefault("maps", {})
    data["maps"].setdefault(vacuum_entity_id, {})
    data["maps"][vacuum_entity_id].setdefault(
        str(map_id),
        {
            "map_id": str(map_id),
            "metadata": {},
            "rooms": {},
            "summary": {},
        },
    )
    return data["maps"][vacuum_entity_id][str(map_id)]


def save_map_discovery_snapshot(
    *,
    data: dict[str, Any],
    vacuum_entity_id: str,
    map_id: str,
    discovery_payload: dict[str, Any],
) -> dict[str, Any]:
    """Save a discovery snapshot into the map bucket."""
    map_bucket = ensure_map_bucket(
        data=data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )

    map_bucket.setdefault("metadata", {})
    map_bucket["metadata"]["last_discovery"] = {
        "active_map_id": discovery_payload.get("active_map_id"),
        "room_count": discovery_payload.get("room_count", 0),
    }
    map_bucket["metadata"]["discovered_rooms"] = discovery_payload.get("rooms", [])

    return map_bucket


def get_map_bucket(
    *,
    data: dict[str, Any],
    vacuum_entity_id: str,
    map_id: str,
) -> dict[str, Any]:
    """Return a map bucket if present, otherwise an empty map-shaped payload."""
    return (
        data.get("maps", {})
        .get(vacuum_entity_id, {})
        .get(
            str(map_id),
            {
                "map_id": str(map_id),
                "metadata": {},
                "rooms": {},
                "summary": {},
            },
        )
    )


def get_vacuum_maps_summary(
    *,
    data: dict[str, Any],
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Return a summary of all known maps for one vacuum."""
    map_buckets = data.get("maps", {}).get(vacuum_entity_id, {})

    maps: list[dict[str, Any]] = []

    for map_id, bucket in sorted(map_buckets.items(), key=lambda item: str(item[0])):
        metadata = bucket.get("metadata", {})
        summary = bucket.get("summary", {})
        rooms = bucket.get("rooms", {})

        maps.append(
            {
                "map_id": str(map_id),
                "room_count": len(rooms),
                "enabled_room_count": int(summary.get("enabled_count", 0)),
                "disabled_room_count": int(summary.get("disabled_count", 0)),
                "last_discovery": metadata.get("last_discovery", {}),
            }
        )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_count": len(maps),
        "maps": maps,
    }


def rebuild_map_bucket(
    *,
    data: dict[str, Any],
    vacuum_entity_id: str,
    map_id: str,
    discovered_rooms: list[dict[str, Any]],
    preserve_existing_settings: bool = True,
) -> dict[str, Any]:
    """Rebuild the room list for one map bucket from freshly discovered rooms.

    Stale room entries (no longer discovered) are removed. Existing per-room
    settings are preserved when ``preserve_existing_settings`` is True.
    Other maps and vacuums are not affected.
    """
    map_bucket = ensure_map_bucket(
        data=data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )

    existing_rooms = map_bucket.get("rooms", {})
    rebuilt_rooms: dict[str, dict[str, Any]] = {}

    for index, room in enumerate(discovered_rooms, start=1):
        room_id = int(room["room_id"])
        room_id_key = str(room_id)

        previous = existing_rooms.get(room_id_key, {}) if preserve_existing_settings else {}

        # floor_type encodes carpet pile height in the value itself
        # (e.g. "carpet_low_pile"); there is no separate carpet_type field.
        floor_type = str(previous.get("floor_type", "hardwood"))

        rebuilt_rooms[room_id_key] = {
            "room_id": room_id,
            "map_id": str(map_id),
            "name": str(room["name"]),
            "slug": room.get("slug"),
            "enabled": bool(previous.get("enabled", True)),
            "order": int(previous.get("order", index)),
            "profile_name": str(previous.get("profile_name", "vacuum_quick")),
            "floor_type": floor_type,
            "clean_mode": str(previous.get("clean_mode", "vacuum")),
            "fan_speed": str(previous.get("fan_speed", "Max")),
            "water_level": str(previous.get("water_level", "Off")),
            "clean_intensity": str(previous.get("clean_intensity", "Standard")),
            "clean_passes": int(previous.get("clean_passes", 1)),
            "edge_mopping": bool(previous.get("edge_mopping", False)),
            "path_type": previous.get("path_type"),
            "is_dock_room": bool(previous.get("is_dock_room", False)),
            "is_transition": bool(previous.get("is_transition", False)),
            "color": previous.get("color"),  # preserve per-room map fill override across a rebuild
            "grants_access_to": list(previous.get("grants_access_to", []))
            if isinstance(previous.get("grants_access_to"), list)
            else [],
            "rules": list(previous.get("rules", []))
            if isinstance(previous.get("rules"), list)
            else [],
        }

    map_bucket["rooms"] = rebuilt_rooms
    map_bucket.setdefault("metadata", {})
    map_bucket["metadata"]["last_rebuild"] = {
        "map_id": str(map_id),
        "room_count": len(rebuilt_rooms),
        "preserve_existing_settings": preserve_existing_settings,
    }

    enabled_count = sum(1 for room in rebuilt_rooms.values() if room.get("enabled", False))
    disabled_count = len(rebuilt_rooms) - enabled_count

    map_bucket["summary"] = {
        "enabled_count": enabled_count,
        "disabled_count": disabled_count,
        "enabled_rooms": sorted(
            [
                {
                    "room_id": int(room_id),
                    "name": room["name"],
                    "slug": room.get("slug"),
                    "order": room.get("order", 0),
                }
                for room_id, room in rebuilt_rooms.items()
                if room.get("enabled", False)
            ],
            key=lambda item: (int(item.get("order", 0)), str(item.get("name", ""))),
        ),
        "disabled_rooms": sorted(
            [
                {
                    "room_id": int(room_id),
                    "name": room["name"],
                    "slug": room.get("slug"),
                    "order": room.get("order", 0),
                }
                for room_id, room in rebuilt_rooms.items()
                if not room.get("enabled", False)
            ],
            key=lambda item: str(item.get("name", "")),
        ),
    }

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "room_count": len(rebuilt_rooms),
        "rooms": rebuilt_rooms,
        "summary": map_bucket["summary"],
        "metadata": map_bucket["metadata"],
    }
