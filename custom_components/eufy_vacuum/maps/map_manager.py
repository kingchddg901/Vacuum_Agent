"""Map-scoped storage operations: create, read, rebuild, and summarize per-vacuum map buckets."""

from __future__ import annotations

from typing import Any

from ..models.models import RoomConfig


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

    A room the rebuild has to create fresh (or one whose settings are being dropped
    because ``preserve_existing_settings`` is False) takes the BRAND's default-profile
    settings, through the same seam the wizard path uses — so the two room writers cannot
    answer "what does a fresh room look like?" differently. They already drifted once on
    the field LIST (``is_transition``); this closes the same gap on the VALUES.
    """
    # Local import: maps <- rooms <- rooms.access_graph <- maps is a cycle at module load.
    from ..profiles.room_profiles import DEFAULT_ROOM_PROFILE_NAME
    from ..rooms.room_defaults import resolve_new_room_defaults_for_vacuum

    new_room_defaults = resolve_new_room_defaults_for_vacuum(vacuum_entity_id)

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

        # Built through RoomConfig — the SAME dataclass build_managed_rooms uses — rather
        # than a second hand-maintained field list. The two lists had already drifted once:
        # is_transition was preserved here and absent from RoomConfig, so a re-save silently
        # un-marked transition rooms. A field added to the dataclass now reaches BOTH
        # writers automatically instead of relying on someone remembering this copy.
        #
        # The approval flags stay LOCAL and deliberately differ: build_managed_rooms is an
        # explicit user approval and stamps is_configured=True, while a rebuild must
        # PRESERVE whatever approval already existed — a rebuilt room must not read as
        # unconfigured (filtered out of entity creation and flagged by the drift tracker),
        # and equally must not silently auto-approve. Same fields, genuinely different
        # question, so the divergence is expressed here rather than hidden in a shared default.
        _prev_grants = previous.get("grants_access_to")
        _prev_rules = previous.get("rules")

        def _prev_or_brand(key: str, fallback: Any, _prev=previous) -> Any:
            """An existing value wins; else the brand's default profile; else the field
            default. Mirrors build_managed_rooms._default exactly — same precedence,
            same seam."""
            if key in _prev:
                return _prev[key]
            return new_room_defaults.get(key, fallback)
        rebuilt_rooms[room_id_key] = RoomConfig(
            room_id=room_id,
            map_id=str(map_id),
            name=str(room["name"]),
            slug=room.get("slug"),
            enabled=bool(previous.get("enabled", True)),
            order=int(previous.get("order", index)),
            profile_name=str(_prev_or_brand("profile_name", DEFAULT_ROOM_PROFILE_NAME)),
            floor_type=floor_type,
            clean_mode=str(_prev_or_brand("clean_mode", "vacuum")),
            fan_speed=str(_prev_or_brand("fan_speed", "")),
            water_level=str(_prev_or_brand("water_level", "")),
            clean_intensity=str(_prev_or_brand("clean_intensity", "")),
            clean_passes=int(_prev_or_brand("clean_passes", 1)),
            edge_mopping=bool(_prev_or_brand("edge_mopping", False)),
            path_type=_prev_or_brand("path_type", None),
            is_dock_room=bool(previous.get("is_dock_room", False)),
            is_transition=bool(previous.get("is_transition", False)),
            grants_access_to=list(_prev_grants) if isinstance(_prev_grants, list) else [],
            rules=list(_prev_rules) if isinstance(_prev_rules, list) else [],
            color=previous.get("color"),
            is_configured=bool(previous.get("is_configured", True)),
            configured_at=previous.get("configured_at"),
        ).as_dict()

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
