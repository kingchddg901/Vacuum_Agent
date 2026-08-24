"""Room-identity reconciliation — pure detection + migration planning.

Some brands renumber their segment ids when the map is re-segmented (Roborock:
naming a new room or merging two renumbers most ids). The framework keys stored
room config + the access graph by the raw segment id, so a renumber would make a
renamed-id room look brand-new and orphan its settings. The user's rule is "no
auto changes": surface an id change as a REVIEW the user confirms, never migrate
silently.

Stable identity is the room SLUG (name-derived, assigned at first discovery).
This module compares a fresh discovery against the stored (saved) rooms by slug
and reports what changed:

  - ``id_changed`` — a known slug now carries a different segment id (the
    re-segment case). Confirming migrates the durable data to the new id.
  - ``renamed``    — a known segment id now carries a different name/slug (the
    same physical room was renamed in the app).

New rooms and removed rooms are intentionally NOT reported here — the existing
drift system (setup/drift.py) owns those signals. This module only owns the
identity-shift cases that drift can't express.

Dispatch correctness does NOT depend on confirming a review: the dispatch path
resolves slug -> live id from a fresh get_maps at send time (Wave 2b). Reviews
are purely about attributing stored data to the right id.

Pure — no hass, no manager. ``compute_reconciliation`` reports; the manager
applies a confirmed migration (it owns the data dict).
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
#       A2-REC-3 (closed RP-019): A room renamed AND renumbered in the same edit is invisible to reconciliation — and
#              migrate then deletes its stored data as if it were a stranger
#   INCFMPP1  `rooms/room_discovery.py#INCFMPP1`
#       A2-REC-2: Two rooms with the same name collapse into one identity: phantom id_changed on an
#              unchanged map, and migrate overwrites one room's settings with the other's


from __future__ import annotations

import hashlib
import json
from typing import Any

from .utils import slugify_room_name


def _coerce_int(value: Any) -> int | None:
    """Return value as an int, or None if it is not integer-coercible."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _room_slug(room: dict[str, Any]) -> str | None:
    """Return a room's slug, deriving it from the name when absent."""
    slug = str(room.get("slug") or "").strip().lower()
    if slug:
        return slug
    name = str(room.get("name") or "").strip()
    return slugify_room_name(name) if name else None


def _existing_unique_by_slug(
    existing_rooms: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Slug -> stored room, for slugs that are UNIQUE among ``existing_rooms``.

    RP-018/D5, applied here as well. A store predating admission-time slug uniqueness
    can still hold two rooms sharing a slug. ``setdefault`` — which both builders below
    used — is first-wins, so slug-led matching would pick one of the two candidates on
    iteration order and collapse two rooms' identities on a guess. An ambiguous slug is
    excluded entirely instead, and that room falls back to id-led matching, which is a
    known answer rather than an arbitrary one.

    ``rooms/room_manager.py::_existing_by_slug`` is the same RULE over a different
    vocabulary and stays separate on purpose: it reads the stored ``slug`` field
    verbatim, while reconciliation compares against a FRESH discovery where a room may
    carry no slug yet, so it lowercases and derives from the name (``_room_slug``).
    Unifying the two would force one module's slug definition onto the other; the shared
    thing is the uniqueness question, not how a slug is spelled.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for room in existing_rooms.values():
        if not isinstance(room, dict):
            continue
        slug = _room_slug(room)
        if slug:
            grouped.setdefault(slug, []).append(room)
    return {slug: rooms[0] for slug, rooms in grouped.items() if len(rooms) == 1}


def compute_reconciliation(
    *,
    discovered_rooms: list[dict[str, Any]],
    existing_rooms: dict[str, Any] | None,
    dismissed_at: str | None = None,
    dismissed_plan_token: str | None = None,
) -> dict[str, Any]:
    """Return identity-shift reviews comparing discovery to stored rooms.

    Args:
        discovered_rooms: normalized discovery dicts (room_id:int, name, slug).
        existing_rooms:   the saved map bucket's ``rooms`` dict, keyed by id-str.
        dismissed_at: when the user last dismissed this map's reviews (reconcile_room
          action=ignore stamps it), or None if never dismissed.
        dismissed_plan_token: the plan_token fingerprint of the reviews that were
          dismissed. REC-7/RP-019: an identical review must not re-fire on every
          discovery pass, but a GENUINELY new shift must still surface — so a
          dismissal only suppresses while the fresh reviews fingerprint the SAME as
          what was dismissed. Once discovery moves on, this token no longer matches
          and the (new) reviews return normally.

    Returns:
        ``{"reviews": [ ... ], "has_changes": bool}`` where each review is one of:
          {"kind": "id_changed", "slug", "name", "old_id", "new_id"}
          {"kind": "renamed", "room_id", "old_slug", "new_slug",
           "old_name", "new_name"}
          {"kind": "renamed_and_renumbered", "old_id", "new_id", "old_slug",
           "new_slug", "old_name", "new_name", "inferred": True,
           "match_basis": "sole_remaining_pair"}
            — C55: this kind is reached by ELIMINATION and carries no similarity
            evidence. The two extra keys say so, so a consumer can present it as a
            question rather than as a determination.
        plus ``"dismissed": True`` when a dismissal suppressed an identical set.
    """
    existing_rooms = existing_rooms or {}

    # Ambiguous slugs are EXCLUDED, not first-wins — see _existing_unique_by_slug.
    existing_by_slug = _existing_unique_by_slug(existing_rooms)
    existing_by_id: dict[int, dict[str, Any]] = {}
    for room in existing_rooms.values():
        if not isinstance(room, dict):
            continue
        room_id = _coerce_int(room.get("room_id"))
        if room_id is not None:
            existing_by_id[room_id] = room

    # Slugs present in the fresh discovery. A 'renamed' review must NOT fire when the
    # old slug is still discovered (the room was renumbered, not renamed — already
    # surfaced as an id_changed review for a different discovered room). Firing both
    # produces a contradictory pair, and confirming the spurious 'renamed' would
    # misattribute the original room's settings to the new room on the freed id.
    discovered_slugs = {
        _room_slug(d)
        for d in discovered_rooms
        if isinstance(d, dict) and _room_slug(d)
    }

    reviews: list[dict[str, Any]] = []
    matched_existing_slugs: set[str] = set()
    unmatched_discovered: list[dict[str, Any]] = []

    for discovered in discovered_rooms:
        if not isinstance(discovered, dict):
            continue
        new_id = _coerce_int(discovered.get("room_id"))
        slug = _room_slug(discovered)
        name = str(discovered.get("name") or "").strip()
        if new_id is None or not slug:
            continue

        slug_match = existing_by_slug.get(slug)
        if slug_match is not None:
            matched_existing_slugs.add(slug)
            old_id = _coerce_int(slug_match.get("room_id"))
            if old_id is not None and old_id != new_id:
                reviews.append(
                    {
                        "kind": "id_changed",
                        "slug": slug,
                        "name": name or str(slug_match.get("name") or ""),
                        "old_id": old_id,
                        "new_id": new_id,
                    }
                )
            # slug matches and id matches → no shift.
            continue

        # No slug match — is this the SAME id under a new name (a rename)?
        id_match = existing_by_id.get(new_id)
        if id_match is not None:
            old_slug = _room_slug(id_match)
            if old_slug:
                matched_existing_slugs.add(old_slug)
                if old_slug != slug and old_slug not in discovered_slugs:
                    reviews.append(
                        {
                            "kind": "renamed",
                            "room_id": new_id,
                            "old_slug": old_slug,
                            "new_slug": slug,
                            "old_name": str(id_match.get("name") or ""),
                            "new_name": name,
                        }
                    )
            continue
        # Neither slug nor id matched — brand-new, UNLESS it turns out to be the
        # other half of a rename+renumber (see the singleton pairing below).
        unmatched_discovered.append(discovered)

    # REC-3 (RP-019): a room renamed AND renumbered in the same re-map matches
    # NEITHER a slug nor an id, so it is invisible to both branches above. When
    # exactly one existing room and exactly one discovered room are left unclaimed,
    # this pairs them.
    #
    # C55 — WHAT THIS PAIRING RESTS ON, STATED HONESTLY. This comment used to say the
    # two rooms "can only be each other". They can not: there is NO similarity test of
    # any kind here — no name or slug comparison, no geometry, no area. A stored room
    # DELETED plus an unrelated room ADDED in the same re-map leaves exactly one on each
    # side and produces this review, having nothing to do with a rename.
    #
    # The pairing stays, because refusing it loses the genuine rename-and-renumber this
    # branch exists to catch, and because the user confirms it before anything is
    # applied. What changes is that the review no longer presents a guess as a finding:
    # it carries `inferred` and `match_basis`, so a consumer can say "these are the only
    # two left — are they the same room?" rather than "this room was renamed and
    # renumbered". Anything more than one on either side is genuinely ambiguous and is
    # still left unpaired.
    # ⚠ ACCEPTED RISK (Chris, 2026-08-24), ledger C55. THIS IS A KNOWN DEFECT THAT
    # SHIPS DELIBERATELY. A stored room DELETED plus an unrelated room ADDED in the
    # same re-map lands in exactly this 1-and-1 shape, so the pairing can be wrong,
    # and `plan_migration` then carries the old room's durable settings AND its
    # access-graph position (`grants_access_to`, and `is_dock_room` via
    # `carried = dict(source)`) onto a room that is not the same room.
    #
    # THE FIX WAS BUILT, MEASURED, AND REJECTED — do not rebuild it without reading
    # this. Dropping the access-graph position turns a COMPLETE graph PARTIAL for the
    # GENUINE rename-and-renumber this branch exists to serve, because the real case
    # and the wrong guess arrive through the same elimination. `access_graph_block_code`
    # maps partial -> `incomplete_access_graph`, and `planning/run_plan.py` refuses
    # EVERY run on that map before the queue is built. Probed against real stored data:
    # Dock(1)->Hall(2)->Study(4) with Study renamed+renumbered to Office(9) went from
    # `valid: True, complete` to `missing_dependency, partial, blocked`. The user would
    # confirm a review saying "Office — formerly Study" and then find nothing runs, with
    # nothing connecting the two. Both of this house's boxes are fully wired graphs.
    #
    # So the accepted trade is: a RARE wrong pairing that the user confirms, against a
    # COMMON hard stop with no explanation. The access-graph position is what makes the
    # graph valid, so removing it necessarily invalidates the graph — that tension is
    # the finding, and it is why no partial version of the fix helps either.
    #
    # WHAT WOULD CHANGE THE RULING: a review row that says outright the room will need
    # re-linking before runs resume (card work, `src/renderers/setup.js` folds this kind
    # into "Renamed" and reads neither `inferred` nor `match_basis`), or a similarity
    # floor with a threshold somebody has actually measured. Neither existed at 2.1.0.
    unmatched_existing = [
        room for slug, room in existing_by_slug.items() if slug not in matched_existing_slugs
    ]
    if len(unmatched_existing) == 1 and len(unmatched_discovered) == 1:
        old_room = unmatched_existing[0]
        new_room = unmatched_discovered[0]
        reviews.append(
            {
                "kind": "renamed_and_renumbered",
                "old_id": _coerce_int(old_room.get("room_id")),
                "new_id": _coerce_int(new_room.get("room_id")),
                "old_slug": _room_slug(old_room),
                "new_slug": _room_slug(new_room),
                "old_name": str(old_room.get("name") or ""),
                "new_name": str(new_room.get("name") or "").strip(),
                # C55: this pair was reached by ELIMINATION, not by matching anything
                # about the two rooms. A consumer that renders every review the same way
                # would state it as a determination; these two fields are what let it
                # not. Structured, not prose — the wording is the card's, so this adds
                # no user-facing string and no key to the eighteen locale files.
                "inferred": True,
                "match_basis": "sole_remaining_pair",
            }
        )

    if dismissed_at is not None and reviews and dismissed_plan_token is not None:
        fresh_token = compute_plan_token(reviews=reviews, discovered_rooms=discovered_rooms)
        if fresh_token == dismissed_plan_token:
            return {"reviews": [], "has_changes": False, "dismissed": True}

    return {"reviews": reviews, "has_changes": bool(reviews)}


def plan_migration(
    *,
    discovered_rooms: list[dict[str, Any]],
    existing_rooms: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the new id-keyed room map after a confirmed re-map.

    Atomic and slug-matched: every saved room whose slug (or, failing that, its
    id) still exists in the fresh discovery is carried to its NEW id, preserving
    all durable settings and updating name/slug; ``grants_access_to`` targets are
    rewritten through the same old->new id remap. Building fresh from the
    discovered set is collision-free by construction (discovered ids are unique),
    which the alternative — incrementally re-keying in place — is not when a
    re-segment REUSES ids across rooms.

    Saved rooms whose slug vanished from discovery (merged/deleted in the re-map)
    are dropped and reported under ``dropped`` — the user confirmed the re-map,
    and drift surfaces genuine removals separately.

    Returns:
        {"rooms": {id_str: cfg}, "id_remap": {old_id: new_id},
         "slug_remap": {old_slug: new_slug}, "dropped": [slug, ...]}
    """
    existing_rooms = existing_rooms or {}

    # Ambiguous slugs are EXCLUDED, not first-wins — see _existing_unique_by_slug.
    existing_by_slug = _existing_unique_by_slug(existing_rooms)
    existing_by_id: dict[int, dict[str, Any]] = {}
    for room in existing_rooms.values():
        if not isinstance(room, dict):
            continue
        room_id = _coerce_int(room.get("room_id"))
        if room_id is not None:
            existing_by_id[room_id] = room

    # Old ids whose slug still exists in the fresh discovery: they'll be carried by the
    # slug match below, so their freed numeric id must NOT be claimed by the id-fallback
    # for a DIFFERENT (brand-new) room that happens to reuse it. Without this, a
    # re-segment that both renumbers room A (16->20) and adds a new room B on A's freed
    # id 16 would stamp A's durable settings + access-graph grants onto B.
    discovered_slugs = {
        _room_slug(d)
        for d in discovered_rooms
        if isinstance(d, dict) and _room_slug(d)
    }
    consumed_old_ids: set[int] = set()
    for _slug, _room in existing_by_slug.items():
        if _slug in discovered_slugs:
            _oid = _coerce_int(_room.get("room_id"))
            if _oid is not None:
                consumed_old_ids.add(_oid)

    new_rooms: dict[str, dict[str, Any]] = {}
    id_remap: dict[int, int] = {}
    # D5: old_slug -> new_slug for rooms carried under a CHANGED name. The learning
    # key is map::slug, so without this the room's past runs stay under a name
    # nothing asks for again. Reported, not applied, here — plan_migration is pure.
    slug_remap: dict[str, str] = {}
    carried_slugs: set[str] = set()
    unmatched_discovered: list[tuple[int, str, dict[str, Any]]] = []

    for discovered in discovered_rooms:
        if not isinstance(discovered, dict):
            continue
        new_id = _coerce_int(discovered.get("room_id"))
        slug = _room_slug(discovered)
        if new_id is None or not slug:
            continue

        source = existing_by_slug.get(slug)
        if source is None and new_id not in consumed_old_ids:
            source = existing_by_id.get(new_id)
        if source is None:
            # No durable data for this discovered room YET — see the REC-3 pairing
            # below before concluding it's genuinely new.
            unmatched_discovered.append((new_id, slug, discovered))
            continue

        old_id = _coerce_int(source.get("room_id"))
        carried = dict(source)
        carried["room_id"] = new_id
        carried["name"] = str(discovered.get("name") or source.get("name") or "")
        carried["slug"] = slug
        new_rooms[str(new_id)] = carried
        if old_id is not None:
            if old_id != new_id:
                id_remap[old_id] = new_id
            source_slug = _room_slug(source)
            if source_slug:
                carried_slugs.add(source_slug)
                if source_slug != slug:
                    slug_remap[source_slug] = slug

    # REC-3 (RP-019): mirrors compute_reconciliation's singleton pairing — a room
    # renamed AND renumbered in the same re-map matches neither by slug nor by id,
    # so without this it is reported dropped (settings lost) and its new id
    # treated as a brand-new room. When exactly one existing room and exactly one
    # discovered room are left unclaimed, carry the old room's durable settings
    # onto the new id rather than losing them; anything more than one on either
    # side is ambiguous and is left as a genuine drop/new-room pair.
    #
    # C55: this side is reached only AFTER the user confirms the review, and the review
    # now declares that its pairing came from elimination rather than a similarity match
    # (`inferred` / `match_basis` — see compute_reconciliation). That is deliberate: the
    # decision to trust the pair belongs to the person who can see both rooms, and this
    # function's job is to execute it faithfully once they have. It carries every durable
    # setting and rewrites the access graph through `id_remap`, so a confirmation given
    # on a mis-stated finding is expensive — which is exactly why the statement was
    # fixed rather than this behaviour.
    leftover_existing_slugs = [s for s in existing_by_slug if s not in carried_slugs]
    if len(leftover_existing_slugs) == 1 and len(unmatched_discovered) == 1:
        source = existing_by_slug[leftover_existing_slugs[0]]
        new_id, slug, discovered = unmatched_discovered[0]
        old_id = _coerce_int(source.get("room_id"))
        carried = dict(source)
        carried["room_id"] = new_id
        carried["name"] = str(discovered.get("name") or source.get("name") or "")
        carried["slug"] = slug
        new_rooms[str(new_id)] = carried
        if old_id is not None and old_id != new_id:
            id_remap[old_id] = new_id
        carried_slugs.add(leftover_existing_slugs[0])

    # Rewrite grants through the old->new id remap; drop targets that no longer
    # resolve to a carried room (their room was dropped in the re-map).
    valid_new_ids = {_coerce_int(key) for key in new_rooms}
    valid_new_ids.discard(None)
    for cfg in new_rooms.values():
        rewritten: list[int] = []
        seen: set[int] = set()
        for target in cfg.get("grants_access_to", []) or []:
            target_id = _coerce_int(target)
            if target_id is None:
                continue
            mapped = id_remap.get(target_id, target_id)
            if mapped in valid_new_ids and mapped not in seen:
                seen.add(mapped)
                rewritten.append(mapped)
        cfg["grants_access_to"] = rewritten

    dropped = sorted(
        slug
        for slug in existing_by_slug
        if slug not in carried_slugs
    )

    return {
        "rooms": new_rooms,
        "id_remap": id_remap,
        "slug_remap": slug_remap,
        "dropped": dropped,
    }


def compute_plan_token(
    *, reviews: list[dict[str, Any]], discovered_rooms: list[dict[str, Any]]
) -> str:
    """Deterministic fingerprint of a reconciliation review + the discovery it was
    computed from (REC-5/RP-019).

    ``reconcile_room`` recomputes this fresh from the CURRENT discovery/existing
    rooms at confirm time and compares it against the token the caller reviewed —
    never trusting a value cached at discover time, so this also catches a
    discovery snapshot changed by any means, not only a repeat ``discover_rooms``
    call. A mismatch means the plan on screen is not the plan that would apply.
    """
    canonical = json.dumps(
        {"reviews": reviews, "rooms": discovered_rooms}, sort_keys=True, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
