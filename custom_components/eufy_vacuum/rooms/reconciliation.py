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
           "new_slug", "old_name", "new_name"}
        plus ``"dismissed": True`` when a dismissal suppressed an identical set.
    """
    existing_rooms = existing_rooms or {}

    existing_by_slug: dict[str, dict[str, Any]] = {}
    existing_by_id: dict[int, dict[str, Any]] = {}
    for room in existing_rooms.values():
        if not isinstance(room, dict):
            continue
        room_id = _coerce_int(room.get("room_id"))
        slug = _room_slug(room)
        if room_id is not None:
            existing_by_id[room_id] = room
        if slug:
            existing_by_slug.setdefault(slug, room)

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
    # exactly one existing room and exactly one discovered room are left
    # unclaimed, they can only be each other — anything more than one on either
    # side is genuinely ambiguous and is deliberately left unpaired (no auto
    # changes without a confident match; drift/new-room handling takes it from
    # there, same as any other unmatched room).
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
         "dropped": [slug, ...]}
    """
    existing_rooms = existing_rooms or {}

    existing_by_slug: dict[str, dict[str, Any]] = {}
    existing_by_id: dict[int, dict[str, Any]] = {}
    for room in existing_rooms.values():
        if not isinstance(room, dict):
            continue
        room_id = _coerce_int(room.get("room_id"))
        slug = _room_slug(room)
        if room_id is not None:
            existing_by_id[room_id] = room
        if slug:
            existing_by_slug.setdefault(slug, room)

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

    # REC-3 (RP-019): mirrors compute_reconciliation's singleton pairing — a room
    # renamed AND renumbered in the same re-map matches neither by slug nor by id,
    # so without this it is reported dropped (settings lost) and its new id
    # treated as a brand-new room. When exactly one existing room and exactly one
    # discovered room are left unclaimed, carry the old room's durable settings
    # onto the new id rather than losing them; anything more than one on either
    # side is ambiguous and is left as a genuine drop/new-room pair.
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

    return {"rooms": new_rooms, "id_remap": id_remap, "dropped": dropped}


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
