"""Unit tests for rooms/reconciliation.py — pure identity-shift detection +
migration planning.

The reconciliation layer exists because some brands (Roborock) RENUMBER segment
ids on re-segment, while the framework keys stored config + the access graph by
id. Identity is the name slug; these functions detect when a known slug's id
changed (or a known id's name changed) and plan the data migration the user
confirms.

Coverage targets
----------------
[REC-1]  no existing rooms -> no reviews (first discovery).
[REC-2]  slug matches + id unchanged -> no review.
[REC-3]  slug matches + id changed -> id_changed review.
[REC-4]  same id + new slug -> renamed review.
[REC-5]  brand-new discovered room -> no review (drift owns it).
[MIG-1]  migrate re-keys by slug, preserves durable settings, updates name/slug.
[MIG-2]  migrate rewrites grants through the old->new id remap.
[MIG-3]  a saved slug absent from discovery is dropped + reported.
[MIG-4]  id REUSE across rooms migrates without collision.
[MIG-5]  a discovered room with no saved data is not carried (it's new).
[MIG-6]  grant targets that no longer resolve are dropped.
[NL-1]   non-Latin (Cyrillic) rooms survive a full re-segment, distinct ids.
[NL-2]   migration carries every Cyrillic room; none dropped or merged.
[NL-3]   two near non-Latin names are not merged into one identity.
[NL-4]   NFC/NFD forms of one name reconcile as the SAME room (no orphan).
"""

from __future__ import annotations

import unicodedata

from custom_components.eufy_vacuum.rooms.reconciliation import (
    compute_reconciliation,
    plan_migration,
)
from custom_components.eufy_vacuum.rooms.utils import slugify_room_name


def _existing(*rooms) -> dict[str, dict]:
    """Build a saved-rooms dict from (id, name, slug[, grants][, extra]) tuples."""
    out: dict[str, dict] = {}
    for room in rooms:
        rid, name, slug = room[0], room[1], room[2]
        grants = list(room[3]) if len(room) > 3 else []
        extra = room[4] if len(room) > 4 else {}
        out[str(rid)] = {
            "room_id": rid,
            "name": name,
            "slug": slug,
            "grants_access_to": grants,
            **extra,
        }
    return out


def _discovered(*rooms) -> list[dict]:
    """Build discovery dicts from (id, name, slug) tuples."""
    return [
        {"room_id": rid, "map_id": "Main floor", "name": name, "slug": slug}
        for rid, name, slug in rooms
    ]


# --- compute_reconciliation -------------------------------------------------


def test_no_existing_no_reviews():
    """[REC-1]"""
    result = compute_reconciliation(
        discovered_rooms=_discovered((16, "KITCHEN", "kitchen")),
        existing_rooms={},
    )
    assert result["reviews"] == []
    assert result["has_changes"] is False


def test_slug_match_same_id_no_review():
    """[REC-2]"""
    result = compute_reconciliation(
        discovered_rooms=_discovered((16, "KITCHEN", "kitchen")),
        existing_rooms=_existing((16, "KITCHEN", "kitchen")),
    )
    assert result["reviews"] == []


def test_id_changed_review():
    """[REC-3] same slug, new segment id (the re-segment case)."""
    result = compute_reconciliation(
        discovered_rooms=_discovered((27, "KITCHEN", "kitchen")),
        existing_rooms=_existing((16, "KITCHEN", "kitchen")),
    )
    assert result["has_changes"] is True
    assert result["reviews"] == [
        {"kind": "id_changed", "slug": "kitchen", "name": "KITCHEN", "old_id": 16, "new_id": 27}
    ]


def test_renamed_review():
    """[REC-4] same id, new name/slug."""
    result = compute_reconciliation(
        discovered_rooms=_discovered((21, "Foyer", "foyer")),
        existing_rooms=_existing((21, "Entryway", "entryway")),
    )
    assert result["reviews"] == [
        {
            "kind": "renamed",
            "room_id": 21,
            "old_slug": "entryway",
            "new_slug": "foyer",
            "old_name": "Entryway",
            "new_name": "Foyer",
        }
    ]


def test_new_room_no_review():
    """[REC-5] a brand-new discovered room is drift's job, not a review."""
    result = compute_reconciliation(
        discovered_rooms=_discovered(
            (16, "KITCHEN", "kitchen"),
            (99, "Den", "den"),
        ),
        existing_rooms=_existing((16, "KITCHEN", "kitchen")),
    )
    assert result["reviews"] == []


def test_multiple_id_changes():
    """[REC-3] a full re-segment renumbers many rooms -> many reviews."""
    result = compute_reconciliation(
        discovered_rooms=_discovered(
            (27, "KITCHEN", "kitchen"),
            (18, "Dining Room", "dining_room"),
        ),
        existing_rooms=_existing(
            (16, "KITCHEN", "kitchen"),
            (17, "Dining Room", "dining_room"),
        ),
    )
    kinds = {(r["slug"], r["old_id"], r["new_id"]) for r in result["reviews"]}
    assert kinds == {("kitchen", 16, 27), ("dining_room", 17, 18)}


def test_slug_derived_when_absent():
    """A stored room without a slug still matches via name-derived slug."""
    existing = {"16": {"room_id": 16, "name": "KITCHEN"}}  # no slug field
    result = compute_reconciliation(
        discovered_rooms=_discovered((27, "KITCHEN", "kitchen")),
        existing_rooms=existing,
    )
    assert result["reviews"][0]["kind"] == "id_changed"


# --- plan_migration ---------------------------------------------------------


def test_migrate_rekeys_and_preserves_settings():
    """[MIG-1] durable settings carry to the new id; name/slug updated."""
    existing = _existing(
        (16, "KITCHEN", "kitchen", [], {"profile_name": "deep_clean", "floor_type": "tile"}),
    )
    plan = plan_migration(
        discovered_rooms=_discovered((27, "Kitchen", "kitchen")),
        existing_rooms=existing,
    )
    assert set(plan["rooms"]) == {"27"}
    carried = plan["rooms"]["27"]
    assert carried["room_id"] == 27
    assert carried["slug"] == "kitchen"
    assert carried["name"] == "Kitchen"
    assert carried["profile_name"] == "deep_clean"
    assert carried["floor_type"] == "tile"
    assert plan["id_remap"] == {16: 27}


def test_migrate_rewrites_grants():
    """[MIG-2] grants_access_to targets follow the old->new id remap."""
    existing = _existing(
        (16, "KITCHEN", "kitchen", [17]),
        (17, "Dining Room", "dining_room", []),
    )
    plan = plan_migration(
        discovered_rooms=_discovered(
            (27, "KITCHEN", "kitchen"),
            (18, "Dining Room", "dining_room"),
        ),
        existing_rooms=existing,
    )
    assert plan["id_remap"] == {16: 27, 17: 18}
    assert plan["rooms"]["27"]["grants_access_to"] == [18]


def test_migrate_drops_vanished_slug():
    """[MIG-3] a saved room whose slug is gone from discovery is dropped."""
    existing = _existing(
        (16, "KITCHEN", "kitchen"),
        (19, "Office", "office"),
    )
    plan = plan_migration(
        discovered_rooms=_discovered((27, "KITCHEN", "kitchen")),
        existing_rooms=existing,
    )
    assert set(plan["rooms"]) == {"27"}
    assert plan["dropped"] == ["office"]


def test_migrate_id_reuse_no_collision():
    """[MIG-4] kitchen takes office's old id (19); migration stays collision-free."""
    existing = _existing(
        (16, "KITCHEN", "kitchen"),
        (19, "Office", "office"),
    )
    # Re-segment: KITCHEN is now id 19 (office's old id); office is gone.
    plan = plan_migration(
        discovered_rooms=_discovered((19, "KITCHEN", "kitchen")),
        existing_rooms=existing,
    )
    assert set(plan["rooms"]) == {"19"}
    assert plan["rooms"]["19"]["slug"] == "kitchen"
    assert plan["id_remap"] == {16: 19}
    assert plan["dropped"] == ["office"]


def test_migrate_does_not_add_new_rooms():
    """[MIG-5] a discovered room with no saved data is not carried by migration."""
    existing = _existing((16, "KITCHEN", "kitchen"))
    plan = plan_migration(
        discovered_rooms=_discovered(
            (27, "KITCHEN", "kitchen"),
            (30, "Den", "den"),
        ),
        existing_rooms=existing,
    )
    assert set(plan["rooms"]) == {"27"}


def test_migrate_drops_unresolvable_grant():
    """[MIG-6] a grant target that no longer resolves to a carried room drops."""
    existing = _existing(
        (16, "KITCHEN", "kitchen", [99]),  # 99 was never a real room
    )
    plan = plan_migration(
        discovered_rooms=_discovered((27, "KITCHEN", "kitchen")),
        existing_rooms=existing,
    )
    assert plan["rooms"]["27"]["grants_access_to"] == []


# --- non-Latin room names ---------------------------------------------------
# Identity is the name slug, so a non-ASCII script must survive a re-segment the
# same way English does, and Unicode normalization drift must not orphan a room.
# Slugs are derived through the real ``slugify_room_name`` so these stay honest
# as the derivation evolves. An input axis the X10/S6 hardware never produced.

_CYRILLIC = {
    16: "Спальня", 17: "Кабинет", 18: "Зал", 19: "Коридор",
    20: "Ванная", 21: "Гостевой туалет", 22: "Детская",
}


def _cyrillic_existing():
    return _existing(
        *((rid, name, slugify_room_name(name)) for rid, name in _CYRILLIC.items())
    )


def _cyrillic_discovered(id_shift):
    return _discovered(
        *(
            (rid + id_shift, name, slugify_room_name(name))
            for rid, name in _CYRILLIC.items()
        )
    )


def test_cyrillic_rooms_survive_resegment():
    """[NL-1] all seven Cyrillic rooms keep distinct identities when a re-segment
    renumbers every id — the real S7 input class."""
    result = compute_reconciliation(
        discovered_rooms=_cyrillic_discovered(7),
        existing_rooms=_cyrillic_existing(),
    )
    assert len(result["reviews"]) == len(_CYRILLIC)
    assert all(r["kind"] == "id_changed" for r in result["reviews"])
    pairs = {(r["old_id"], r["new_id"]) for r in result["reviews"]}
    assert pairs == {(rid, rid + 7) for rid in _CYRILLIC}


def test_migrate_carries_all_cyrillic_rooms():
    """[NL-2] migration carries every Cyrillic room to its new id, keeps all
    seven distinct, and drops none."""
    plan = plan_migration(
        discovered_rooms=_cyrillic_discovered(7),
        existing_rooms=_cyrillic_existing(),
    )
    assert len(plan["rooms"]) == len(_CYRILLIC)
    assert plan["dropped"] == []
    assert {r["name"] for r in plan["rooms"].values()} == set(_CYRILLIC.values())
    assert plan["id_remap"] == {rid: rid + 7 for rid in _CYRILLIC}


def test_nonlatin_near_names_stay_distinct():
    """[NL-3] two near non-Latin names ("Зал"/"Зала") are NOT merged into one
    identity on re-segment."""
    plan = plan_migration(
        discovered_rooms=_discovered(
            (26, "Зал", slugify_room_name("Зал")),
            (27, "Зала", slugify_room_name("Зала")),
        ),
        existing_rooms=_existing(
            (16, "Зал", slugify_room_name("Зал")),
            (17, "Зала", slugify_room_name("Зала")),
        ),
    )
    assert plan["id_remap"] == {16: 26, 17: 27}
    assert plan["dropped"] == []


def test_migrate_reconciles_nfc_nfd_same_room():
    """[NL-4] a room stored under an NFC name, rediscovered in NFD form (same
    visual name, new id), is recognized as the SAME room and carried — not
    dropped.

    Red-green of the NFC-normalization fix: pre-fix the two forms derive
    different slugs, so the stored room's slug vanishes from discovery and the
    room (with all its durable settings) is dropped on re-map.
    """
    nfc = unicodedata.normalize("NFC", "Йога")
    nfd = unicodedata.normalize("NFD", "Йога")
    plan = plan_migration(
        discovered_rooms=_discovered((20, nfd, slugify_room_name(nfd))),
        existing_rooms=_existing((16, nfc, slugify_room_name(nfc))),
    )
    assert set(plan["rooms"]) == {"20"}
    assert plan["dropped"] == []
    assert plan["id_remap"] == {16: 20}
