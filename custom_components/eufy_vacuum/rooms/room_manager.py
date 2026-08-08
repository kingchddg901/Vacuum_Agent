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


def _existing_by_slug(existing_rooms: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Slug -> existing room dict, for rooms whose slug is UNIQUE among
    existing_rooms only. RP-018/D5: a store that still holds a pre-RP-015
    duplicate slug (from before admission-time uniqueness existed) must not
    let slug-led carry pick one of two candidates arbitrarily and collapse
    their identities — an ambiguous slug is excluded here entirely, so that
    room falls back to id-led carry (today's behaviour), never a guess.
    """
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for room in existing_rooms.values():
        if not isinstance(room, dict):
            continue
        slug = str(room.get("slug") or "").strip()
        if slug:
            by_slug.setdefault(slug, []).append(room)
    return {slug: rooms[0] for slug, rooms in by_slug.items() if len(rooms) == 1}


def build_managed_rooms(
    *,
    discovered_rooms: list[dict[str, Any]],
    new_room_defaults: dict[str, Any],
    existing_rooms: dict[str, Any] | None = None,
    enabled_room_ids: list[int] | list[str] | None = None,
    floor_types: dict[int, str] | None = None,
    rejected_rooms: set[int] | list[int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a managed room dict keyed by room_id string from discovered rooms.

    Only rooms in ``enabled_room_ids`` are included when that list is supplied.
    Existing per-room settings are preserved for rooms that are still discovered;
    new rooms take their settings from ``new_room_defaults``.

    ``new_room_defaults`` is REQUIRED and has deliberately no default value. It comes from
    ``rooms.room_defaults.resolve_new_room_defaults_for_vacuum`` — the brand's own default
    profile. A permissive default here is exactly the pattern the adapter audit kept
    finding: an omitted argument that quietly resolves to a concrete *Eufy* answer. Making
    it required means a future call site cannot forget and silently get Eufy vocabulary;
    it gets a TypeError instead.

    Can legitimately return ``{}`` (empty ``discovered_rooms``, or ``enabled_room_ids``
    that excludes every room) — this function does not itself refuse a destructive
    replacement of ``existing_rooms``, because it only sees ``existing_rooms`` as
    per-room settings to preserve, not as a wipe-guard baseline (that baseline is the
    CALLER's stored room map, which this function never reads back). RP-005/RF-02:
    callers that write the result into a persisted room store (``save_managed_rooms``,
    ``rebuild_map``) are responsible for guarding an empty result against a non-empty
    stored map via ``room_crud._refuse_destructive_replace`` before assigning it.

    RP-018/RF-25b: carry-over is SLUG-LED with id fallback (REC-8/CRUD-2) — a
    re-segment renumber must not transplant one physical room's settings onto
    whichever room now happens to hold its OLD numeric id. Q5 (verbatim):
    a room with NO existing match — the room this discovery pass has never
    seen before — is enabled on a FIRST import (``existing_rooms`` was empty
    before this call) and DISABLED+unconfirmed on incremental discovery
    (DQ-Q-5/CRUD-6); it never silently joins an already-active queue.
    ``floor_types`` gates ``is_configured`` (CRUD-3): a room reaching this
    function via ``enabled_room_ids`` without a supplied floor_type entry is
    NOT auto-confirmed — a previously-confirmed room stays confirmed across a
    re-save regardless. ``rejected_rooms`` (CRUD-5) excludes ids the user
    explicitly rejected (setup/drift.py) from resurrecting on rediscovery.

    SETUP-REJ-2: that last sentence was true of the CODE and false of the SYSTEM
    until 2026-08-05 — ``save_managed_rooms``, the only production caller, never
    passed the argument, so the skip had never run. It does now, with the
    MAP-SCOPED rejection set (``rejected_room_ids_for``). Any future caller must
    pass the same thing: the vacuum-wide union would drop a real room on one map
    because an unrelated id was rejected on another (A4-SETUP-6).
    """
    from ..profiles.room_profiles import DEFAULT_ROOM_PROFILE_NAME   # local: import cycle

    existing_rooms = existing_rooms or {}
    new_room_defaults = new_room_defaults or {}
    floor_types = floor_types or {}
    rejected_ids = _normalize_enabled_room_ids(rejected_rooms) if rejected_rooms else set()
    explicit_enabled_ids = _normalize_enabled_room_ids(enabled_room_ids)
    has_explicit_enabled_ids = enabled_room_ids is not None
    is_first_import = not existing_rooms
    existing_by_slug = _existing_by_slug(existing_rooms)

    # Old ids "consumed" by a slug match this pass: their freed numeric id must
    # NOT be claimed by id-fallback for a DIFFERENT (brand-new) room that
    # happens to reuse it (mirrors reconciliation.py's plan_migration
    # consumed_old_ids guard — same shape, same reason). Without this, a
    # renumber (Kitchen 16->21, a new Bedroom takes 16) would carry Kitchen via
    # its slug AND transplant Kitchen's old settings onto Bedroom via id 16 —
    # exactly the REC-8/CRUD-2 defect this packet closes.
    consumed_ids: set[int] = set()
    for room in discovered_rooms:
        slug = str(room.get("slug") or "").strip()
        matched = existing_by_slug.get(slug) if slug else None
        if matched is not None:
            try:
                consumed_ids.add(int(matched.get("room_id")))
            except (TypeError, ValueError):
                pass

    managed: dict[str, dict[str, Any]] = {}

    for index, room in enumerate(discovered_rooms, start=1):
        room_id = int(room["room_id"])
        room_id_key = str(room_id)

        slug = str(room.get("slug") or "").strip()
        matched_by_slug = existing_by_slug.get(slug) if slug else None
        if matched_by_slug is not None:
            existing = matched_by_slug
        elif room_id not in consumed_ids:
            existing = existing_rooms.get(room_id_key, {})
        else:
            existing = {}
        is_new_room = not existing

        # A rejection REFUSES A ROOM'S CREATION; it does not delete a room
        # (Chris, adjudicating A4-SETUP-6). So the skip is gated on the room not
        # already being configured — otherwise a stale rejection silently deletes
        # user data on the next re-save, and the room's settings (profile, floor
        # type, order, colour) go with it.
        #
        # SETUP-REJ-2 made this reachable and it is NOT hypothetical: a live
        # install carried rejected_rooms=[10] alongside a configured room 10 on a
        # LATER map, precisely because the exclusion had never been wired. Turning
        # the exclusion on without this gate converted a dormant stale entry into
        # an active room-deleter. Removing a room that is genuinely a phantom is
        # still possible — that is reject_rooms' own explicit, user-initiated
        # strip, which reports what it removed.
        if room_id in rejected_ids and not existing.get("is_configured"):
            continue
        if has_explicit_enabled_ids and room_id not in explicit_enabled_ids:
            continue

        # Wizard-supplied floor type takes priority over any stored value;
        # the value encodes carpet pile height (e.g. "carpet_low_pile").
        floor_type_entry = floor_types.get(room_id)
        if floor_type_entry is None:
            floor_type_entry = floor_types.get(str(room_id))
        floor_type = floor_type_entry or str(existing.get("floor_type", "hardwood"))

        # Calling build_managed_rooms with a room ID in enabled_room_ids is the
        # user's explicit approval — but CRUD-3: is_configured also requires a
        # supplied floor_type entry THIS call, unless the room was already
        # confirmed on a prior save. Scoped to explicit-approval calls only
        # (enabled_room_ids given): the wizard supplies both together from one
        # form submission, so "approved but no floor type" is a real,
        # meaningful gap there. A call with no enabled_room_ids at all is not
        # asking an approval question in the first place (e.g. re-syncing an
        # already-set-up map) — is_configured keeps its unconditional True,
        # as before.
        from ..learning.utils import _iso_now
        existing_configured_at = existing.get("configured_at")
        if has_explicit_enabled_ids:
            is_configured = bool(existing.get("is_configured", False)) or floor_type_entry is not None
        else:
            is_configured = True

        # A field a room already carries wins; otherwise the BRAND's default profile
        # answers, via new_room_defaults. _default() keeps that precedence in one place so
        # the two cannot be wired differently per field, and returns the RoomConfig field
        # default when neither the room nor the brand's profile declares the key — silence
        # from a brand is not a value.
        def _default(key: str, fallback: Any) -> Any:
            if key in existing:
                return existing[key]
            return new_room_defaults.get(key, fallback)

        room_config = RoomConfig(
            room_id=room_id,
            map_id=str(room["map_id"]),
            name=str(room["name"]),
            slug=room.get("slug"),
            enabled=bool(existing.get("enabled", is_first_import if is_new_room else True)),
            order=int(existing.get("order", index)),
            profile_name=str(_default("profile_name", DEFAULT_ROOM_PROFILE_NAME)),
            floor_type=floor_type,
            clean_mode=str(_default("clean_mode", "vacuum")),
            fan_speed=str(_default("fan_speed", "")),
            water_level=str(_default("water_level", "")),
            clean_intensity=str(_default("clean_intensity", "")),
            clean_passes=int(_default("clean_passes", 1)),
            edge_mopping=bool(_default("edge_mopping", False)),
            # ``or ""`` catches a carried-forward None from data written before
            # RoomConfig stopped defaulting this axis to None — str(None) is "None",
            # which is not a value any brand declares but is truthy everywhere.
            path_type=str(_default("path_type", "") or ""),
            is_dock_room=bool(existing.get("is_dock_room", False)),
            is_transition=bool(existing.get("is_transition", False)),  # preserve across a re-save
            grants_access_to=list(existing.get("grants_access_to", [])),
            rules=list(existing.get("rules", [])),
            color=existing.get("color"),  # preserve per-room map fill override across a re-save
            is_configured=is_configured,
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