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
from ..rooms.reconciliation import compute_reconciliation, plan_migration
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

        # Identity-shift reconciliation: compare the fresh discovery against the
        # SAVED rooms for this map by slug. A known slug whose segment id changed
        # (re-segment) or a known id whose name changed (rename) surfaces as a
        # review the user confirms — never an auto-migration ("no auto changes").
        # New/removed rooms are owned by drift, not reported here.
        existing_rooms = get_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=_disc_map_id,
        ).get("rooms", {})
        payload["reconciliation"] = compute_reconciliation(
            discovered_rooms=payload.get("rooms", []),
            existing_rooms=existing_rooms,
        )

        self._manager.data.setdefault("discovery", {})
        self._manager.data["discovery"].setdefault(vacuum_entity_id, {})[_disc_map_id] = payload

        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.active_map_id = payload.get("active_map_id")

        return payload

    def reconcile_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        action: str = "migrate",
    ) -> dict[str, Any]:
        """Apply or dismiss the identity-shift reviews for one vacuum/map.

        A re-segment renumbers many rooms at once, so reconciliation is a single
        per-map decision (mirroring "did you re-map? [Yes, migrate] / [No]")
        rather than a per-room prompt:

          - ``migrate`` — atomically rebuild the saved room map from the cached
            discovery, carrying each saved room's durable settings to its new id
            (slug-matched) and rewriting access-graph grants through the same
            old->new id remap. Learning history is slug-tagged in the job files,
            so it follows the room regardless. Saved rooms whose slug vanished
            from discovery are dropped (the user confirmed the re-map) and
            reported.
          - ``ignore`` — leave stored data untouched and stamp a dismissal so the
            same reviews stop surfacing until the next real change.

        Requires a prior ``discover_rooms`` to have cached the discovery payload.
        """
        from ..learning.utils import _iso_now

        action = str(action or "").strip().lower()
        map_id_str = str(map_id)
        self._manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)

        if action == "ignore":
            map_bucket = ensure_map_bucket(
                data=self._manager.data,
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id_str,
            )
            map_bucket.setdefault("metadata", {})["reconciliation_dismissed_at"] = _iso_now()
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id_str,
                "action": "ignore",
                "migrated_room_count": 0,
                "id_remap": {},
                "dropped": [],
            }

        if action != "migrate":
            raise ValueError(f"reconcile_room: unknown action {action!r}")

        discovery = (
            self._manager.data.get("discovery", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
        )
        discovered_rooms = [
            room
            for room in discovery.get("rooms", [])
            if str(room.get("map_id")) == map_id_str
        ]

        # Never migrate against an empty discovery — a stale/offline discovery
        # would otherwise rebuild the map to nothing and wipe saved rooms. The
        # caller should re-run discover_rooms first.
        if not discovered_rooms:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id_str,
                "action": "migrate",
                "migrated_room_count": 0,
                "id_remap": {},
                "dropped": [],
                "skipped": "no_discovery",
            }

        existing_rooms = get_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
        ).get("rooms", {})

        plan = plan_migration(
            discovered_rooms=discovered_rooms,
            existing_rooms=existing_rooms,
        )

        new_rooms = plan["rooms"]
        map_bucket = ensure_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
        )
        map_bucket["rooms"] = new_rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=new_rooms)
        map_bucket.setdefault("metadata", {})["reconciled_at"] = _iso_now()

        # Drop transient id-keyed rule-status snapshots for the migrated old ids;
        # they rebuild on the next preflight under the new ids.
        rule_status_map = (
            self._manager.data.get("room_rule_status", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
        )
        for old_id in plan["id_remap"]:
            rule_status_map.pop(str(old_id), None)

        # Room-history is a rebuildable cache derived from slug-tagged job files;
        # invalidate so it re-ingests under the new ids.
        self._manager._room_history_cache_ready.discard(vacuum_entity_id)

        self._manager._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
        )
        self._manager._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "action": "migrate",
            "migrated_room_count": len(new_rooms),
            "id_remap": {str(old): new for old, new in plan["id_remap"].items()},
            "dropped": plan["dropped"],
        }

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

        No cross-map access-graph cleanup is needed: ``grants_access_to``
        targets are bare room IDs scoped to a single map (room identity is
        vacuum+map+room), and every consumer resolves them only against that
        same map's room set.  A grant on a remaining map can never reference a
        room on the map being removed, so there is nothing to strip.
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
