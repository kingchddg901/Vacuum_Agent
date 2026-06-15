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

from __future__ import annotations

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
) -> dict[str, Any]:
    """Return identity-shift reviews comparing discovery to stored rooms.

    Args:
        discovered_rooms: normalized discovery dicts (room_id:int, name, slug).
        existing_rooms:   the saved map bucket's ``rooms`` dict, keyed by id-str.

    Returns:
        ``{"reviews": [ ... ], "has_changes": bool}`` where each review is one of:
          {"kind": "id_changed", "slug", "name", "old_id", "new_id"}
          {"kind": "renamed", "room_id", "old_slug", "new_slug",
           "old_name", "new_name"}
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

    reviews: list[dict[str, Any]] = []

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
            if old_slug and old_slug != slug:
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
        # Otherwise it's a brand-new room → drift owns it, no review here.

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

    new_rooms: dict[str, dict[str, Any]] = {}
    id_remap: dict[int, int] = {}
    carried_slugs: set[str] = set()

    for discovered in discovered_rooms:
        if not isinstance(discovered, dict):
            continue
        new_id = _coerce_int(discovered.get("room_id"))
        slug = _room_slug(discovered)
        if new_id is None or not slug:
            continue

        source = existing_by_slug.get(slug)
        if source is None:
            source = existing_by_id.get(new_id)
        if source is None:
            # No durable data for this discovered room — it's new; not migrated.
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
