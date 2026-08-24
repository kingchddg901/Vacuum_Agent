"""Room and map CRUD operations for the Eufy Vacuum integration.

Owns the high-level operations for discovering, saving, reading, removing,
and rebuilding room configurations and map buckets on behalf of the
EufyVacuumManager orchestrator.
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INMKEHPQ  `rooms/room_manager.py#INMKEHPQ`
#       A2-REC-1 (closed RP-019): Reconciliation never runs in production: no trigger, no schedule, no UI — the
#              reviews are computed into a payload nothing reads
#       A2-REC-5 (RP-019, HALF closed — re-read 2026-08-24, RM4): migrate applies a plan the user never saw: it
#              never re-checks the reviews, and rebuilds the map even when there are none
#              CLOSED half: the reviews ARE re-checked. reconcile_room recomputes them fresh and
#              refuses on a missing token (`skipped="plan_token_required"`) or a mismatch
#              (`skipped="plan_changed"`).
#              OPEN half: there is no `if not current_reviews: return` anywhere in the migrate arm.
#              A confirm with ZERO reviews fingerprints to a token that MATCHES, so it proceeds and
#              replaces `map_bucket["rooms"]` wholesale from `plan_migration` — which is not a
#              no-op: every stored room whose slug is absent from the fresh discovery is DROPPED
#              (only the no_discovery and >50% partial-discovery guards stand in the way), grants
#              are rewritten through `id_remap`, and a leftover 1-and-1 pair is carried (C55).
#              This is the preamble above landing on itself: "(closed RP-x)" named a packet that
#              closed one of the two clauses filed under it.


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


# anchor: INC63FDF  a stored room map is replaced only by evidence, never by absence
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

        Does not create a map bucket. This method uses the non-mutating
        ``get_map_bucket`` read path, so it never persists a skeleton.

        ⚠ Map buckets are NOT ONLY created by ``save_managed_rooms``. This
        docstring said they were until 2026-08-24 (R12); it was one of the
        checkable premises behind "where do these phantom map buckets come
        from" and the answer was more paths than the wording admitted. The full
        set: ``save_managed_rooms`` (this file, user-confirmed), ``rebuild_map``
        (this file, via ``rebuild_map_bucket``), and ``reconcile_room`` in
        BOTH the ``action="ignore"`` and ``action="migrate"`` arms (this file,
        via ``ensure_map_bucket``). The ``ignore`` arm in particular creates a
        bucket for a map the user has never confirmed, just to stamp a
        dismissal token — see the reconcile_room docstring for its own note on
        that. ``maps/map_manager.py::map_ids_with_rooms``'s docstring names
        ~38 total ``ensure_map_bucket`` sites across the tree, so a full audit
        starts from that helper, not from this one.
        """
        self._manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)

        payload = discover_rooms_payload(
            self._manager.hass,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        # ⚠ This key and the rooms' OWN ``map_id`` field disagree when the active
        # map cannot be resolved (2026-08-24, RM22). ``discover_rooms_payload`` has
        # no "unknown" fallback, so ``active_map_id`` comes back None and this key
        # is the EMPTY STRING — while ``discover_rooms_for_vacuum`` stamps every
        # room it returns ``map_id="unknown"``. ``save_managed_rooms`` and
        # ``reconcile_room`` look this payload up by their own ``str(map_id)`` and
        # then filter its rooms with ``str(room.get("map_id")) == str(map_id)``, so
        # whichever of the two values the caller passes, one of the two steps
        # misses: "" finds the payload and filters every room out of it; "unknown"
        # finds no payload at all. Either way the save writes an empty room map (or
        # is refused ``empty_replacement_refused`` when something is already stored)
        # and the migrate reports ``skipped="no_discovery"`` — never "no map id",
        # which is the thing that actually went wrong.
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
        # REC-5 (RP-019): a fingerprint of the reviews IN THIS PAYLOAD, for the card to
        # round-trip back on confirm — see compute_plan_token / reconcile_room.
        # ⚠ was "a fingerprint of this exact review" until 2026-08-24 (RM11), which is
        # false in the DISMISSED case — and that is the case that bites. When a dismissal
        # suppresses an identical set, ``compute_reconciliation`` returns
        # ``{"reviews": [], "has_changes": False, "dismissed": True}``, so the token below
        # is computed over an EMPTY review list. ``reconcile_room`` recomputes it WITHOUT
        # the dismissal arguments, i.e. over the real (non-empty) reviews, so the two can
        # never match: a migrate confirmed against this payload comes back
        # ``skipped="plan_changed"`` — a report that the plan changed, for a plan that did
        # not change. The token is round-trippable only while ``dismissed`` is absent.
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
            old->new id remap. Learning is keyed ``map::slug``, so a RENUMBER
            carries it untouched — the slug did not move. A RENAME does move it,
            and this used to lose the room's whole history to a name nothing
            asked for again; the old identity is now recorded as an alias so the
            past runs stay reachable, and the accuracy store — which nothing ever
            rebuilds — is rekeyed in the same pass. Saved rooms whose slug vanished
            from discovery are dropped (the user confirmed the re-map) and
            reported. REQUIRES ``plan_token`` (REC-5/RP-019): the fingerprint
            ``discover_rooms`` returned with the reviews the user actually saw.
            Refused if missing, or if it no longer matches what the CURRENT
            discovery/existing rooms fingerprint to — the plan on screen is not
            necessarily the plan that would apply.
          - ``ignore`` — leave stored data untouched and stamp a dismissal so the
            same reviews stop surfacing until the next real change. No token
            needed — dismissing doesn't apply anything.

        ⚠ Only ``action="migrate"`` requires a prior ``discover_rooms``. This
        docstring said BOTH did until 2026-08-24 (R23); it was true of migrate
        (it returns ``skipped="no_discovery"`` without one) and false of ignore.
        The ignore arm reads ``discovery.get("rooms", [])`` off an empty dict,
        computes its plan token over an EMPTY discovered set, and stamps
        ``reconciliation_dismissed_at`` + ``reconciliation_dismissed_token``
        into a bucket it creates via ``ensure_map_bucket``. Because
        ``compute_reconciliation``'s dismissed-token contract only suppresses
        an IDENTICAL review set, the dismissal that lands is effectively inert
        (it fingerprints nothing) — but the phantom map bucket does persist,
        contributing to the R12 problem. Refusing the ignore arm without prior
        discovery would be more honest, but is not being changed here because
        the shipped card and services flow always discover first; this note
        exists so a future refactor can act on the real contract rather than
        the aspirational one.
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

        # D5: a room carried under a CHANGED name keeps its learned statistics only if
        # the old identity is recorded. The learning key is map::slug and a job record
        # carries the slug it had at run time, so without this the room's whole history
        # stays under a name nothing asks for again and it reads as never cleaned.
        #
        # TWO STORES, TWO REMEDIES, because they are maintained differently:
        #   room_stats  — REBUILT from the job records, so recording the alias is enough;
        #                 the rebuilder resolves every historical slug forward.
        #   accuracy_stats — APPEND-ONLY and never rebuilt, so no later pass would repair
        #                 it. Its existing entries are rekeyed here, once.
        # Recording the alias is what makes the first work; the rekey is what makes the
        # second. Doing only one is the partial fix.
        _slug_remap = plan.get("slug_remap") or {}
        if _slug_remap:
            from ..learning.history_store import LearningHistoryStore

            _store = LearningHistoryStore(self._manager.hass)
            for _old_slug, _new_slug in _slug_remap.items():
                _store.record_slug_alias(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id_str,
                    old_slug=_old_slug,
                    new_slug=_new_slug,
                )
            _store.rekey_accuracy_slugs(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id_str,
                slug_remap=_slug_remap,
            )

        # Room-history is a rebuildable cache derived from the stored job files;
        # invalidate so it reloads.
        # ⚠ was: "derived from slug-tagged job files; invalidate so it re-ingests under
        # the new ids", until 2026-08-24 (RM15). The operative half is false, and it is
        # the half a reader relies on.
        # ``core/manager.py::_ingest_completed_job_into_room_history`` keys every entry
        # on ``room.get("room_id", room.get("id"))`` — the RAW numeric id recorded in
        # the job file — and never reads a slug, even though ``resolved_rooms`` carries
        # one.
        # Historical job files still hold the OLD ids, so the rebuild re-ingests under
        # the OLD ids, not the new ones. And ``async_preload_room_history_cache`` MERGES
        # the rebuild into the live dict (newer-wins per field) instead of replacing it,
        # so the stale old-id entries are not cleared either: after a renumber the
        # migrated room reads as NEVER CLEANED while its history sits under an id nothing
        # asks for again. Carrying room-history across ``id_remap`` — rekeying
        # ``data["room_history"][vacuum][map]``, the same remedy ``accuracy_stats`` gets
        # above — is a code change and is NOT landed.
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
            # include_unscoped=False: only rejections that KNOW their map reach a
            # write boundary. The legacy flat list still suppresses new_rooms (safe,
            # reversible), but must never refuse a creation here — a live install
            # carried rejected_rooms=[10] beside a configured room 10 on a later
            # map, and honouring it here deleted that room.
            rejected_rooms=rejected_room_ids_for(
                self._manager,
                vacuum_entity_id,
                map_id=str(map_id),
                include_unscoped=False,
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
        # ⚠ The ``build_room_selection_summary(...)`` default below NEVER supplies the
        # value (2026-08-24, RM26). It is dead in two independent senses. (1) Python
        # evaluates the default EAGERLY, so it runs on every call and the result is
        # discarded whenever the key is present — including the ``int(room_id_key)`` it
        # does per room, which would raise out of this read path for a non-numeric room
        # key whose summary was going to be thrown away. (2) The key is present on
        # every bucket the current code can produce: ``ensure_map_bucket`` seeds
        # ``"summary": {}`` alongside ``rooms`` (and it is the only bucket creator —
        # ``rebuild_map_bucket`` goes through it too), while ``get_map_bucket``'s
        # miss-path literal carries the key as well. So a bucket whose
        # summary was seeded and never written returns ``{}`` here — this does NOT
        # recompute a missing one. The one-token repair is ``map_bucket.get("summary") or
        # build_room_selection_summary(...)``; it is a behaviour change (a bucket that
        # legitimately holds an empty summary would start reporting a computed one), and
        # it is unlanded.
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
        # R16: flag names come from PER_MAP_STORES itself so a new store cannot be
        # added there without also declaring the response-flag it will report against.
        # Was TWO hand-maintained lists; the sibling dict raised KeyError on
        # divergence and took remove_map down entirely. Now one source of truth.
        removed: dict[str, Any] = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "rooms_removed": 0,
            **{
                flag: False
                for (_key, _mode, flag) in PER_MAP_STORES
                if flag
            },
        }

        vacuum_maps = self._manager.data.get("maps", {}).get(vacuum_entity_id, {})
        if map_id_str in vacuum_maps:
            rooms = vacuum_maps[map_id_str].get("rooms", {})
            removed["rooms_removed"] = len(rooms)
            del vacuum_maps[map_id_str]

        # A4-SETUP-6 follow-up: rejections are per MAP, so the deleted map's take
        # its rejections with it. They live inside the per-VACUUM setup_progress
        # record rather than a per-map store, so PER_MAP_STORES below cannot reach
        # them and this needs its own line. Observed surviving a real delete on a
        # live box. Eufy only ever rolls map ids FORWARD, so an id is not gone for
        # good — leaving the entry means a future map that eventually reaches this
        # number silently inherits a rejection made for a different map, which is
        # A4-SETUP-6 again with time rather than floors as the axis.
        _progress = (
            (self._manager.data.get("setup_progress") or {}).get(vacuum_entity_id) or {}
        )
        _by_map = _progress.get("rejected_rooms_by_map")
        if isinstance(_by_map, dict) and map_id_str in _by_map:
            removed["rejected_rooms_removed"] = sorted(
                int(r) for r in (_by_map.pop(map_id_str) or [])
                if str(r).lstrip("-").isdigit()
            )

        # RP-016/RF-20 (INJ7VXE7): consume the SAME registry an id-remap walker or any
        # future map-scoped operation reads, so a bucket added there is reachable here
        # too from ONE list -- the defect this packet closed (run_profiles/queue/
        # onboarding survived remove_map for however long they existed as real per-map
        # stores nobody added here). R16 (2026-08-24) completed the promise: the flag
        # name lives on each row too, so a new store cannot be added without declaring
        # its response flag, and the loop can never KeyError on divergence.
        for store_key, mode, flag in PER_MAP_STORES:
            if store_key == "maps":
                continue  # handled above -- needs the room count
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
            if flag:
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
