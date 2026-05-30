"""Room and map CRUD operations for the Eufy Vacuum integration.

Owns the high-level operations for discovering, saving, reading, removing,
and rebuilding room configurations and map buckets on behalf of the
EufyVacuumManager orchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..maps.map_manager import (
    ensure_map_bucket,
    get_map_bucket,
    get_vacuum_maps_summary,
    rebuild_map_bucket,
)
from ..rooms.room_discovery import discover_rooms_payload
from ..rooms.room_manager import build_managed_rooms, build_room_selection_summary

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


class RoomMapManager:
    """Owns room discovery, save, read, remove, and rebuild operations."""

    def __init__(self, manager: EufyVacuumManager) -> None:
        """Initialise with a back-reference to the owning manager."""
        self._manager = manager

    def discover_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str | None = None,
    ) -> dict[str, Any]:
        """Discover rooms for one vacuum and cache them in ``data["discovery"]``.

        Does not create a map bucket.  Map buckets are created only when
        ``save_managed_rooms`` is called after the user confirms the room list.
        """
        self._manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)

        payload = discover_rooms_payload(
            self._manager.hass,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        _disc_map_id = str(payload.get("active_map_id") or map_id or "")
        self._manager.data.setdefault("discovery", {})
        self._manager.data["discovery"].setdefault(vacuum_entity_id, {})[_disc_map_id] = payload

        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.active_map_id = payload.get("active_map_id")

        return payload

    def save_managed_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        enabled_room_ids: list[int] | list[str] | None = None,
        floor_types: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        """Convert discovered rooms into managed room configuration and save it."""
        self._manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)

        discovery = (
            self._manager.data.get("discovery", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        discovered_rooms = discovery.get("rooms", [])

        filtered_rooms = [
            room for room in discovered_rooms if str(room.get("map_id")) == str(map_id)
        ]

        map_bucket = ensure_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        existing_rooms = map_bucket.get("rooms", {})

        managed_rooms = build_managed_rooms(
            discovered_rooms=filtered_rooms,
            existing_rooms=existing_rooms,
            enabled_room_ids=enabled_room_ids,
            floor_types=floor_types or {},
        )

        map_bucket["rooms"] = managed_rooms
        summary = build_room_selection_summary(managed_rooms=managed_rooms)
        map_bucket["summary"] = summary
        self._manager._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._manager._room_history_cache_ready.discard(vacuum_entity_id)

        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.selected_map_id = str(map_id)

        if managed_rooms:
            self._manager.mark_rooms_discovered(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            for room_id_key in managed_rooms:
                self._manager.confirm_floor_type(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    room_id=room_id_key,
                )

        self._manager._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": len(managed_rooms),
            "rooms": managed_rooms,
            "summary": summary,
        }

    def get_managed_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return managed room config for one vacuum/map."""
        map_bucket = get_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        rooms = map_bucket.get("rooms", {})
        summary = map_bucket.get("summary", build_room_selection_summary(managed_rooms=rooms))

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": len(rooms),
            "rooms": {
                key: {
                    k: list(v) if isinstance(v, list) else v
                    for k, v in value.items()
                }
                for key, value in rooms.items()
                if isinstance(value, dict)
            },
            "summary": summary,
            "metadata": {k: dict(v) if isinstance(v, dict) else v for k, v in map_bucket.get("metadata", {}).items()},
        }

    def remove_map(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Remove one imported map and all associated integration data.

        Does not affect the upstream Eufy map.  Callers must fire
        ``_notify_rooms_updated`` afterward so platform callbacks remove
        stale entities.  Returns a summary of what was removed.
        """
        map_id_str = str(map_id)
        removed: dict[str, Any] = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "rooms_removed": 0,
            "history_removed": False,
            "rule_status_removed": False,
            "discovery_removed": False,
            "active_job_cleared": False,
        }

        vacuum_maps = self._manager.data.get("maps", {}).get(vacuum_entity_id, {})
        if map_id_str in vacuum_maps:
            rooms = vacuum_maps[map_id_str].get("rooms", {})
            removed["rooms_removed"] = len(rooms)
            del vacuum_maps[map_id_str]

        disc = self._manager.data.get("discovery", {}).get(vacuum_entity_id, {})
        if map_id_str in disc:
            del disc[map_id_str]
            removed["discovery_removed"] = True

        hist = self._manager.data.get("room_history", {}).get(vacuum_entity_id, {})
        if map_id_str in hist:
            del hist[map_id_str]
            removed["history_removed"] = True

        rule_st = self._manager.data.get("room_rule_status", {}).get(vacuum_entity_id, {})
        if map_id_str in rule_st:
            del rule_st[map_id_str]
            removed["rule_status_removed"] = True

        # Reset the active-job slot to a blank state rather than deleting it,
        # so callers can always find a key for any known vacuum/map pair.
        vac_jobs = self._manager.data.get("active_jobs", {}).get(vacuum_entity_id, {})
        if map_id_str in vac_jobs:
            vac_jobs[map_id_str] = self._manager._default_active_job_state(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id_str,
            )
            removed["active_job_cleared"] = True

        # Drop stale room-id references from any remaining map's access graph.
        remaining_maps = self._manager.data.get("maps", {}).get(vacuum_entity_id, {})
        for other_bucket in remaining_maps.values():
            for room in other_bucket.get("rooms", {}).values():
                gat = room.get("grants_access_to")
                if isinstance(gat, list) and gat:
                    room["grants_access_to"] = [
                        rid for rid in gat
                        if rid not in removed.get("_deleted_room_ids", set())
                    ]

        return removed

    def get_vacuum_maps(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return summary of known maps for one vacuum."""
        return get_vacuum_maps_summary(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
        )

    def rebuild_map(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        preserve_existing_settings: bool = True,
    ) -> dict[str, Any]:
        """Rebuild one map from the latest discovered rooms."""
        discovery = (
            self._manager.data.get("discovery", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        discovered_rooms = discovery.get("rooms", [])

        filtered_rooms = [
            room for room in discovered_rooms if str(room.get("map_id")) == str(map_id)
        ]

        rebuilt = rebuild_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            discovered_rooms=filtered_rooms,
            preserve_existing_settings=preserve_existing_settings,
        )

        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.selected_map_id = str(map_id)

        self._manager._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._manager._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        return rebuilt
