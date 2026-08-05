"""Room and map CRUD operations for the Eufy Vacuum integration.

Owns the high-level operations for discovering, saving, reading, removing,
and rebuilding room configurations and map buckets on behalf of the
EufyVacuumManager orchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..maps.map_manager import (
    PER_MAP_STORES,
    ensure_map_bucket,
    get_map_bucket,
    get_vacuum_maps_summary,
    rebuild_map_bucket,
)
from ..rooms.reconciliation import compute_plan_token, compute_reconciliation, plan_migration
from ..rooms.room_discovery import discover_rooms_payload
from ..rooms.room_defaults import resolve_new_room_defaults_for_vacuum
from ..rooms.room_manager import build_managed_rooms, build_room_selection_summary

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


def _refuse_destructive_replace(
    stored_rooms: Any, new_rooms: Any, source_desc: str
) -> dict[str, Any] | None:
    """Refuse a save/rebuild that would replace a NON-EMPTY stored room map with an
    EMPTY one. Returns a refusal dict, or None when the replace may proceed.

    RP-005/RF-02. Compares against the STORED store, not the discovery input -- a
    shrunk-but-non-empty discovery is reconcile_room's minimum-evidence guard's
    business, not this one's (discovery legitimately returns partial lists; unnamed
    or blank segments are skipped). Two siblings already guarded this shape before
    this packet -- reconcile_room's no_discovery arm and the import workflow's own
    refusal on an empty payload -- while five CRITICAL call sites did not:
    save_managed_rooms, rebuild_map, reconcile_room's migrate arm on a partial
    discovery, discover_rooms' cache overwrite, and enabled_room_ids: null/[]
    reaching the schema as a valid (and destructive) selection.
    """
    if not new_rooms and stored_rooms:
        return {
            "saved": False,
            "reason": "empty_replacement_refused",
            "source": source_desc,
            "stored_room_count": len(stored_rooms),
        }
    return None


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
        self._manager.data["discovery"].setdefault(vacuum_entity_id, {})
        existing_cached = self._manager.data["discovery"][vacuum_entity_id].get(_disc_map_id)
        existing_cached_rooms = (
            existing_cached.get("rooms", []) if isinstance(existing_cached, dict) else []
        )
        if not payload.get("rooms") and existing_cached_rooms:
            # RP-005/RF-02 (FACADE-2): a discovery glitch returning zero rooms must
            # not silently replace a previously-good cache -- save_managed_rooms
            # reads FROM this cache, so an empty cache here would wipe stored rooms
            # too on the next save. A genuinely-empty FIRST discovery (no prior
            # cache) still writes normally (absent != failed).
            payload = dict(existing_cached)
            payload["cache_kept"] = True
            payload["reason"] = "empty_discovery_kept"

        # Identity-shift reconciliation: compare the fresh discovery against the
        # SAVED rooms for this map by slug. A known slug whose segment id changed
        # (re-segment) or a known id whose name changed (rename) surfaces as a
        # review the user confirms — never an auto-migration ("no auto changes").
        # New/removed rooms are owned by drift, not reported here.
        existing_map_bucket = get_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=_disc_map_id,
        )
        existing_rooms = existing_map_bucket.get("rooms", {})
        dismiss_meta = existing_map_bucket.get("metadata", {})
        payload["reconciliation"] = compute_reconciliation(
            discovered_rooms=payload.get("rooms", []),
            existing_rooms=existing_rooms,
            dismissed_at=dismiss_meta.get("reconciliation_dismissed_at"),
            dismissed_plan_token=dismiss_meta.get("reconciliation_dismissed_token"),
        )
        # REC-5 (RP-019): a fingerprint of this exact review, for the card to round-trip
        # back on confirm — see compute_plan_token / reconcile_room.
        payload["reconciliation"]["plan_token"] = compute_plan_token(
            reviews=payload["reconciliation"]["reviews"],
            discovered_rooms=payload.get("rooms", []),
        )
        self._manager.data["discovery"][vacuum_entity_id][_disc_map_id] = payload

        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.active_map_id = payload.get("active_map_id")

        return payload

    def reconcile_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        action: str = "migrate",
        force: bool = False,
        plan_token: str | None = None,
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
            reported. REQUIRES ``plan_token`` (REC-5/RP-019): the fingerprint
            ``discover_rooms`` returned with the reviews the user actually saw.
            Refused if missing, or if it no longer matches what the CURRENT
            discovery/existing rooms fingerprint to — the plan on screen is not
            necessarily the plan that would apply.
          - ``ignore`` — leave stored data untouched and stamp a dismissal so the
            same reviews stop surfacing until the next real change. No token
            needed — dismissing doesn't apply anything.

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
            # REC-7 (RP-019): fingerprint what's being dismissed (same discovery
            # currently cached, if any) so a LATER genuinely-different review can
            # still surface — see compute_reconciliation's dismissed_plan_token.
            discovery = (
                self._manager.data.get("discovery", {})
                .get(vacuum_entity_id, {})
                .get(map_id_str, {})
            )
            dismissed_rooms = [
                room for room in discovery.get("rooms", [])
                if str(room.get("map_id")) == map_id_str
            ]
            dismissed_reviews = compute_reconciliation(
                discovered_rooms=dismissed_rooms,
                existing_rooms=get_map_bucket(
                    data=self._manager.data,
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id_str,
                ).get("rooms", {}),
            )["reviews"]
            metadata = map_bucket.setdefault("metadata", {})
            metadata["reconciliation_dismissed_at"] = _iso_now()
            metadata["reconciliation_dismissed_token"] = compute_plan_token(
                reviews=dismissed_reviews, discovered_rooms=dismissed_rooms,
            )
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

        # REC-5 (RP-019): recomputed fresh, never trusted from a cached field —
        # see compute_plan_token's docstring for why.
        current_reviews = compute_reconciliation(
            discovered_rooms=discovered_rooms, existing_rooms=existing_rooms,
        )["reviews"]
        current_token = compute_plan_token(
            reviews=current_reviews, discovered_rooms=discovered_rooms,
        )
        if plan_token is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id_str,
                "action": "migrate",
                "migrated_room_count": 0,
                "id_remap": {},
                "dropped": [],
                "skipped": "plan_token_required",
            }
        if plan_token != current_token:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id_str,
                "action": "migrate",
                "migrated_room_count": 0,
                "id_remap": {},
                "dropped": [],
                "skipped": "plan_changed",
            }

        plan = plan_migration(
            discovered_rooms=discovered_rooms,
            existing_rooms=existing_rooms,
        )

        new_rooms = plan["rooms"]

        # RP-005/RF-02: minimum-evidence guard. Discovery legitimately returns
        # partial lists (unnamed/blank segments are skipped, REC-4) so this is
        # deliberately looser than the no_discovery guard above -- it only refuses
        # when the discovery is BOTH smaller than what is stored AND the resulting
        # migration would drop more than half of the stored rooms, which is no
        # longer "a few segments were unnamed" but "this discovery looks wrong."
        # Overridable with force=True for a genuine re-map that really did shrink.
        if (
            not force
            and existing_rooms
            and len(discovered_rooms) < len(existing_rooms)
            and len(new_rooms) * 2 < len(existing_rooms)
        ):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id_str,
                "action": "migrate",
                "migrated_room_count": 0,
                "id_remap": {},
                "dropped": [],
                "skipped": "partial_discovery_refused",
                "stored_room_count": len(existing_rooms),
                "discovered_room_count": len(discovered_rooms),
            }

        map_bucket = ensure_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
        )
        map_bucket["rooms"] = new_rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=new_rooms)
        map_bucket.setdefault("metadata", {})["reconciled_at"] = _iso_now()

        # Drop transient id-keyed rule-status snapshots for BOTH the migrated old ids
        # AND the new/target ids: a re-segment that frees an id (room dropped) and moves
        # another room ONTO it would otherwise leave the dropped room's stale snapshot
        # showing on the migrated room's sensor. They rebuild on the next preflight.
        rule_status_map = (
            self._manager.data.get("room_rule_status", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
        )
        for old_id, new_id in plan["id_remap"].items():
            rule_status_map.pop(str(old_id), None)
            rule_status_map.pop(str(new_id), None)

        # Carry floor-type confirmations onto the new ids — otherwise every renumbered
        # room reads as needing floor-type confirmation (its confirmation is keyed to the
        # OLD id) and the start gate blocks cleaning with onboarding_required.
        self._manager.onboarding.remap_confirmed_floor_types(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
            id_remap=plan["id_remap"],
        )

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

        # SETUP-REJ-2: build_managed_rooms has always accepted rejected_rooms= and
        # skipped those ids (CRUD-5), and this — its ONLY production caller — never
        # passed it, so that branch had never executed. No symptom, because the
        # protection that actually worked sits a layer up: rejected ids are filtered
        # out of new_rooms, so the panel never offers them and they never arrive here
        # as candidates. But that is a UI-PATH protection. A hand-written
        # save_managed_rooms call with explicit enabled_room_ids walks straight past
        # it and can create a room the user rejected — the mirror of the "a direct
        # service call can pop a configured room" residual noted on A4-SETUP-6.
        # Enforcing it at the write boundary closes that, and makes the parameter's
        # documented contract true rather than aspirational.
        #
        # MAP-SCOPED, and this is the whole trap: passing the vacuum-wide union would
        # mean a rejection on floor 1 silently drops a REAL room on floor 2 out of a
        # save the user explicitly asked for. That is A4-SETUP-6 reappearing at a new
        # site, and destructive here rather than merely blocking.
        from ..setup.drift import rejected_room_ids_for   # local: import cycle

        managed_rooms = build_managed_rooms(
            discovered_rooms=filtered_rooms,
            # The BRAND's default profile decides what a newly-approved room starts with,
            # rather than the framework's Eufy-shaped literals.
            new_room_defaults=resolve_new_room_defaults_for_vacuum(vacuum_entity_id),
            existing_rooms=existing_rooms,
            enabled_room_ids=enabled_room_ids,
            floor_types=floor_types or {},
            rejected_rooms=rejected_room_ids_for(
                self._manager, vacuum_entity_id, map_id=str(map_id)
            ),
        )

        refusal = _refuse_destructive_replace(
            stored_rooms=existing_rooms,
            new_rooms=managed_rooms,
            source_desc="save_managed_rooms",
        )
        if refusal is not None:
            return refusal

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
        # Named flags for the buckets that predate PER_MAP_STORES -- callers
        # (tests, the delete-map service response) already key off these
        # exact names. New buckets (run_profiles/queue/onboarding) get their
        # own flags in `removed` too, so nothing the registry clears is
        # invisible to a caller inspecting the summary.
        FLAG_NAMES = {
            "maps": None,  # handled separately below (needs rooms_removed count)
            "discovery": "discovery_removed",
            "room_history": "history_removed",
            "room_rule_status": "rule_status_removed",
            "run_profiles": "run_profiles_removed",
            "queue": "queue_removed",
            "onboarding": "onboarding_removed",
            "active_jobs": "active_job_cleared",
        }
        removed: dict[str, Any] = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "rooms_removed": 0,
            **{name: False for name in FLAG_NAMES.values() if name},
        }

        vacuum_maps = self._manager.data.get("maps", {}).get(vacuum_entity_id, {})
        if map_id_str in vacuum_maps:
            rooms = vacuum_maps[map_id_str].get("rooms", {})
            removed["rooms_removed"] = len(rooms)
            del vacuum_maps[map_id_str]

        # RP-016/RF-20: consume the SAME registry RP-017's id-remap walker
        # reads, so a bucket added there is reachable here too without a
        # second hand-maintained list -- the defect this packet closes
        # (run_profiles/queue/onboarding survived remove_map for however
        # long they existed as real per-map stores nobody added here).
        for store_key, mode in PER_MAP_STORES:
            if store_key == "maps":
                continue  # handled above -- needs the room count
            flag = FLAG_NAMES[store_key]
            bucket = self._manager.data.get(store_key, {}).get(vacuum_entity_id, {})
            if map_id_str not in bucket:
                continue
            if mode == "delete":
                del bucket[map_id_str]
            elif store_key == "active_jobs":
                # Reset rather than delete: callers always index a known
                # vacuum/map pair without a presence check.
                bucket[map_id_str] = self._manager._default_active_job_state(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id_str,
                )
            removed[flag] = True

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

        # rebuild_map_bucket deterministically produces an empty room map from an
        # empty discovered_rooms list (nothing to iterate) -- refuse BEFORE calling
        # it rather than after, so a stale/glitched discovery can never wipe the
        # stored map (rebuild_map_bucket itself is out of this packet's scope).
        existing_rooms = get_map_bucket(
            data=self._manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        ).get("rooms", {})
        refusal = _refuse_destructive_replace(
            stored_rooms=existing_rooms,
            new_rooms=filtered_rooms,
            source_desc="rebuild_map",
        )
        if refusal is not None:
            return refusal

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
