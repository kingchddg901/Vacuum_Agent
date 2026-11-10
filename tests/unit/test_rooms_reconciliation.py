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
[REC-23] a saved store holding non-dict rows is walked past, in BOTH entry points.
         The same guard is written three times; one corrupt store reaches all of
         them, and the junk rows come FIRST so `continue` is not a `break`.
[REC-24] an id match whose saved room has NO name must not produce a rename review
         'from nothing' -- the arm skips to the next discovered room instead.
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
[REC-15a] D15: a DUPLICATE slug among the stored rooms is excluded from slug-led
          matching entirely, in compute_reconciliation. `setdefault` was first-wins, so
          which of the two candidates won came down to dict iteration order.
[REC-15b] D15: the same exclusion in plan_migration. It was the third and fourth copies
          of one rule that two other functions already implemented.
[REC-16]  D16/C55: the 1-and-1 leftover pairing declares that it came from ELIMINATION,
          not from matching anything about the two rooms. A deleted room plus an
          unrelated added room produces this review having nothing to do with a rename.
[REC-17]  REC-7/RP-019: a dismissal suppresses only the IDENTICAL plan. The same token
          against a moved-on discovery must let the new reviews through.
[REC-18]  a discovered entry with a non-coercible room_id, or with neither slug nor
          name, is skipped rather than reviewed under a None id.
[REC-19]  REC-3: the sole leftover stored room is carried onto the sole unmatched
          discovered id (renamed AND renumbered), and `dropped` comes back EMPTY -
          the third carry path this module's own docstring calls a false negative.
[REC-20]  D5: a room carried under a CHANGED slug records old->new in slug_remap, which
          is what re-keys its learning history.
[REC-21]  a grants_access_to target that is not int-coercible is skipped, not mapped.
[REC-22]  plan_migration skips the same unusable discovered entries as REC-18, so no
          room is written under a 'None' key.
"""

from __future__ import annotations

import unicodedata

from custom_components.eufy_vacuum.rooms.reconciliation import (
    compute_plan_token,
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


# ---------------------------------------------------------------------------
# D15 - a duplicate stored slug must not be matched on a guess
# ---------------------------------------------------------------------------


def test_rec15a_a_duplicate_stored_slug_is_excluded_from_slug_matching():
    """[REC-15a] RED BEFORE THE FIX.

    A store predating admission-time slug uniqueness can hold two rooms sharing a slug.
    `setdefault` kept whichever came first in iteration order and matched the discovery
    against it, collapsing two rooms' identities on nothing. Excluding the ambiguous slug
    sends that room to id-led matching instead, which is a known answer rather than an
    arbitrary one.

    Both stored rooms keep their ids here, so with the ambiguity excluded there is
    nothing to report at all.
    """
    existing = _existing((16, "Kitchen", "kitchen"), (17, "Kitchen", "kitchen"))
    result = compute_reconciliation(
        discovered_rooms=_discovered((16, "Kitchen", "kitchen"), (17, "Kitchen", "kitchen")),
        existing_rooms=existing,
    )
    kinds = [r["kind"] for r in result["reviews"]]
    assert "id_changed" not in kinds, (
        "an ambiguous slug was matched against one of two candidates: " + repr(result["reviews"])
    )


def test_rec15b_plan_migration_excludes_a_duplicate_slug_too():
    """[REC-15b] The sibling copy. A rule fixed in one builder and not the other leaves
    detection and migration disagreeing about which room is which — which is worse than
    both being wrong, because the review the user confirms is not the plan that applies.

    Asserted through a property the guess cannot satisfy: whichever room the first-wins
    map picked, the OTHER one lost its settings. With the ambiguity excluded, id-led
    carry keeps both.
    """
    existing = _existing(
        (16, "Kitchen", "kitchen", [], {"fan_speed": "max"}),
        (17, "Kitchen", "kitchen", [], {"fan_speed": "quiet"}),
    )
    plan = plan_migration(
        discovered_rooms=_discovered((16, "Kitchen", "kitchen"), (17, "Kitchen", "kitchen")),
        existing_rooms=existing,
    )
    rooms = plan["rooms"]
    assert set(rooms) == {"16", "17"}
    assert rooms["16"]["fan_speed"] == "max"
    assert rooms["17"]["fan_speed"] == "quiet", (
        "the duplicate slug collapsed two rooms onto one stored config"
    )


# ---------------------------------------------------------------------------
# D16 / C55 - the 1-and-1 pairing is an inference, and now says so
# ---------------------------------------------------------------------------


def test_rec16_the_leftover_pairing_declares_it_is_inferred():
    """[REC-16] RED BEFORE THE FIX — the review carried no marker at all.

    The inputs here are deliberately the FALSE case, not the true one: Study is deleted
    and an unrelated Porch is added in the same re-map. Nothing about these two rooms
    matches — not name, not slug, not id — and the branch pairs them anyway, because
    there is no similarity test of any kind.

    The pairing is kept on purpose: refusing it would lose the genuine
    rename-and-renumber this branch exists to catch, and the user confirms before
    anything applies. What must not happen is presenting the guess as a determination,
    so the review states the basis it actually rests on.
    """
    result = compute_reconciliation(
        discovered_rooms=_discovered((1, "Kitchen", "kitchen"), (9, "Porch", "porch")),
        existing_rooms=_existing((1, "Kitchen", "kitchen"), (4, "Study", "study")),
    )
    pairing = [r for r in result["reviews"] if r["kind"] == "renamed_and_renumbered"]
    assert len(pairing) == 1
    review = pairing[0]

    # it still pairs -- the genuine case depends on it
    assert review["old_slug"] == "study" and review["new_slug"] == "porch"
    # ...and it no longer claims to have matched anything
    assert review["inferred"] is True
    assert review["match_basis"] == "sole_remaining_pair"


def test_rec16_a_confident_review_is_not_marked_inferred():
    """[REC-16] RED IF THE MARKER IS SET UNCONDITIONALLY.

    An id_changed review IS an identity match — the slug is the same room by definition.
    Marking every review inferred would make the flag meaningless, which is the same
    failure as not having it.
    """
    result = compute_reconciliation(
        discovered_rooms=_discovered((21, "Kitchen", "kitchen")),
        existing_rooms=_existing((16, "Kitchen", "kitchen")),
    )
    assert [r["kind"] for r in result["reviews"]] == ["id_changed"]
    assert "inferred" not in result["reviews"][0]


# ---------------------------------------------------------------------------
# Gaps closed from the 2026-11-07 coverage classification. This module sat at
# 79.7% with a 100% reachable ceiling -- every missed statement was in a pure
# function, nothing needed hass or hardware.
# ---------------------------------------------------------------------------


def test_dismissal_suppresses_only_the_identical_plan():
    """[REC-17] a dismissal must not become a permanent mute.

    REC-7/RP-019: an identical review re-firing on every discovery pass is noise,
    but a GENUINELY new shift still has to surface. The suppression is therefore
    gated on the plan TOKEN, not on the dismissal existing. Both halves are
    asserted here because the first alone passes if the token compare is deleted.
    """
    existing = {"16": {"room_id": 16, "slug": "kitchen", "name": "Kitchen"}}
    discovered = [{"room_id": 20, "name": "Kitchen"}]

    first = compute_reconciliation(discovered_rooms=discovered, existing_rooms=existing)
    assert first["has_changes"] is True
    assert [r["kind"] for r in first["reviews"]] == ["id_changed"]
    token = compute_plan_token(reviews=first["reviews"], discovered_rooms=discovered)

    # Same plan, already dismissed -> suppressed.
    again = compute_reconciliation(
        discovered_rooms=discovered, existing_rooms=existing,
        dismissed_at="2026-01-01T00:00:00Z", dismissed_plan_token=token,
    )
    assert again == {"reviews": [], "has_changes": False, "dismissed": True}

    # Discovery MOVED ON (20 -> 21). The stale token must not suppress the new plan.
    moved = [{"room_id": 21, "name": "Kitchen"}]
    after = compute_reconciliation(
        discovered_rooms=moved, existing_rooms=existing,
        dismissed_at="2026-01-01T00:00:00Z", dismissed_plan_token=token,
    )
    assert after["has_changes"] is True, "a new shift must surface despite the dismissal"
    assert after.get("dismissed") is not True
    assert after["reviews"][0]["new_id"] == 21


def test_unusable_discovered_entries_are_skipped_not_reviewed():
    """[REC-18] a non-coercible id, or neither slug nor name, is skipped.

    Without the guard the first entry slug-matches `kitchen` and produces an
    id_changed review whose new_id is None -- a review the user cannot act on, and
    one that would carry settings onto a null id if confirmed. This is also the
    only route that exercises `_coerce_int`'s except arm, reached the way the
    module's own docstring describes (a stored/discovered room with a bad room_id)
    rather than by calling the private helper.
    """
    existing = {"5": {"room_id": 5, "slug": "kitchen", "name": "Kitchen"}}
    discovered = [
        {"room_id": "x", "name": "Kitchen"},   # id not int-coercible
        {"room_id": 9},                         # no name AND no slug
        {"room_id": 5, "name": "Kitchen"},      # the real, unchanged one
    ]

    out = compute_reconciliation(discovered_rooms=discovered, existing_rooms=existing)
    assert out["reviews"] == [], f"nothing to review here; got {out['reviews']}"
    assert out["has_changes"] is False


def test_sole_leftover_is_paired_with_sole_unmatched_and_not_dropped():
    """[REC-19] REC-3: renamed AND renumbered in one re-map.

    Such a room matches neither by slug nor by id, so without the pairing it is
    reported dropped and its durable settings are lost. The fixture is the module
    docstring's own worked example (stored {16: kitchen, 17: den}, discovered
    [{16: kitchen}, {20: study}]), which it cites as the FALSE NEGATIVE in
    `dropped`: den vanished from discovery, is carried onto 20, and `dropped`
    comes back empty.

    The grant assertion is the consequence that matters: the remap has to reach
    the access graph, or kitchen keeps pointing at an id nothing holds.

    ⚠ `slug_remap` IS THE ASSERTION THIS TEST WAS MISSING, and its absence hid a real
    defect until 2026-11-08. Every other line here passed while the paired room
    silently lost its learning history: the carry stamped the NEW slug, remapped the
    id and kept the durable settings, so floor type, passes and grants all followed —
    and `room_crud.reconcile_room` gates BOTH history remedies on a non-empty
    `slug_remap`, so an empty one means neither `record_slug_alias` nor
    `rekey_accuracy_slugs` runs. The room reads as never cleaned.

    This is the shorter-copy shape: the pairing below the main loop did three of the
    four things the loop does. [REC-20] directly beneath this test covers a room whose
    NAME alone changed and does assert the remap, so the two neighbours differed by
    exactly the case where both halves of the identity move at once.
    """
    existing = {
        "16": {"room_id": 16, "slug": "kitchen", "name": "Kitchen",
               "grants_access_to": [17]},
        "17": {"room_id": 17, "slug": "den", "name": "Den", "clean_passes": 3},
    }
    discovered = [{"room_id": 16, "name": "Kitchen"}, {"room_id": 20, "name": "Study"}]

    plan = plan_migration(discovered_rooms=discovered, existing_rooms=existing)

    assert set(plan["rooms"]) == {"16", "20"}
    carried = plan["rooms"]["20"]
    assert carried["room_id"] == 20
    assert carried["slug"] == "study"
    assert carried["name"] == "Study"
    assert carried["clean_passes"] == 3, "the durable setting is the point of the pairing"
    assert plan["id_remap"] == {17: 20}
    assert plan["dropped"] == [], "den was carried, not dropped"
    assert plan["rooms"]["16"]["grants_access_to"] == [20], (
        "the grant must follow the room to its new id"
    )
    assert plan["slug_remap"] == {"den": "study"}, (
        "the LEARNING HISTORY must follow too -- carrying the settings without the "
        "alias leaves the room reading as never cleaned"
    )


def test_a_changed_slug_is_recorded_in_slug_remap():
    """[REC-20] D5: the learning history is keyed map::slug.

    A room matched by ID after a rename is carried under the NEW slug, so without
    this entry its past runs stay filed under a name nothing asks for again.
    """
    existing = {"5": {"room_id": 5, "slug": "den", "name": "Den"}}
    discovered = [{"room_id": 5, "name": "Study"}]

    plan = plan_migration(discovered_rooms=discovered, existing_rooms=existing)

    assert plan["slug_remap"] == {"den": "study"}
    assert plan["rooms"]["5"]["slug"] == "study"
    assert plan["id_remap"] == {}, "the id did not move; only the name did"
    assert plan["dropped"] == []


def test_uncoercible_grant_targets_are_skipped():
    """[REC-21] junk in a stored grant list must not reach the access graph.

    This pins the OUTPUT CONTRACT and deliberately not the line it was aimed at.
    The coverage classification flagged `if target_id is None: continue`
    (reconciliation.py:486) as a gap worth a test. It is coverable but REDUNDANT:
    `valid_new_ids` is built from `new_rooms` keys, which are always `str(int)`, so
    None can never be a member — the `mapped in valid_new_ids` test two lines down
    already rejects it. Measured: ablating that guard leaves this test GREEN, and so
    does ablating line 480's `discard(None)`. So unlike its five siblings here this
    one is NOT ablation-proven against a single-line change, and saying otherwise
    would make it read as a guarantee it does not provide.

    What it does defend is the contract against a REWRITE of the loop — an
    unconditional append, or a `mapped is not None` short-circuit — and that contract
    is user-visible: a None in `grants_access_to` is a dangling access-graph edge.
    """
    existing = {
        "5": {"room_id": 5, "slug": "kitchen", "name": "Kitchen",
              "grants_access_to": ["abc", None, 17, 17]},
        "17": {"room_id": 17, "slug": "den", "name": "Den"},
    }
    discovered = [{"room_id": 5, "name": "Kitchen"}, {"room_id": 17, "name": "Den"}]

    plan = plan_migration(discovered_rooms=discovered, existing_rooms=existing)

    assert plan["rooms"]["5"]["grants_access_to"] == [17], (
        "'abc' and None drop out; 17 survives once, de-duplicated"
    )


def test_migration_skips_the_same_unusable_entries():
    """[REC-22] the sibling of REC-18, in the function that WRITES.

    Detection skipping a bad entry while planning carried it would be the worse
    failure: `new_rooms[str(None)]` creates a room under the literal key 'None',
    and a slug of None is written into the stored bucket.
    """
    existing = {"5": {"room_id": 5, "slug": "kitchen", "name": "Kitchen"}}
    discovered = [
        {"room_id": "x", "name": "Kitchen"},
        {"room_id": 9},
        {"room_id": 5, "name": "Kitchen"},
    ]

    plan = plan_migration(discovered_rooms=discovered, existing_rooms=existing)

    assert set(plan["rooms"]) == {"5"}, f"only the usable entry is written; got {sorted(plan['rooms'])}"
    assert "None" not in plan["rooms"]
    assert plan["dropped"] == []


def test_rec23_a_saved_store_with_non_dict_rows_is_walked_past():
    """[REC-23] Three copies of one guard, reached by one corrupt store.

    `data["maps"][vac][map]["rooms"]` is persisted and user-editable, so a row can be a
    string, a None or a number. The non-dict guard is written three times -- once in
    `_existing_unique_by_slug` and once in each of the two `existing_by_id` walks, which
    are byte-identical blocks in `compute_reconciliation` and `plan_migration`. Driving
    ONE store through BOTH public entry points reaches all three.

    THE JUNK ROWS COME FIRST. Python preserves dict insertion order, so a `break` in
    place of any of the three `continue`s would never reach the real rows. With the junk
    last, all three guards would be invisible.

    IT TAKES TWO REAL ROOMS TO MAKE ALL THREE GUARDS BITE, which a first draft missed.
    With only a slug-matching room, the slug path resolves it and `existing_by_id` is
    never consulted -- so breaking BOTH of those walks changed nothing observable and
    the ablation came back DEAD. Executing a line is not depending on it. Room 7 is
    therefore an ID match with a CHANGED name, which is the one path that must read
    `existing_by_id`: with a `break` there the dict is empty, room 7 looks brand-new,
    and the rename review disappears.

    THE EXPECTATIONS ARE NOT THE FALLBACK. An empty review list and empty plan are what
    these functions return for a store they could not read at all, so the assertions
    name content: an id_changed review for kitchen 5 -> 9, a renamed review for room 7,
    and a plan carrying each room's saved settings onto its new key.
    """
    corrupt_store = {
        "1": "junk",
        "2": None,
        "3": 7,
        # slug match, id changed -> resolved by the SLUG path
        "5": {"room_id": 5, "name": "Kitchen", "slug": "kitchen", "clean_passes": 3},
        # id match, name changed -> resolved by the existing_by_id path
        "7": {"room_id": 7, "name": "Den", "slug": "den", "clean_passes": 4},
    }
    discovered = _discovered((9, "Kitchen", "kitchen"), (7, "Lounge", "lounge"))

    result = compute_reconciliation(
        discovered_rooms=discovered, existing_rooms=corrupt_store
    )
    kinds = {r["kind"] for r in result["reviews"]}
    assert kinds == {"id_changed", "renamed"}, (
        f"both paths must report; got {sorted(kinds)}"
    )
    id_changed = next(r for r in result["reviews"] if r["kind"] == "id_changed")
    assert (id_changed.get("slug"), id_changed.get("old_id"), id_changed.get("new_id"))         == ("kitchen", 5, 9)
    renamed = next(r for r in result["reviews"] if r["kind"] == "renamed")
    assert (renamed.get("room_id"), renamed.get("old_slug"), renamed.get("new_slug"))         == (7, "den", "lounge")
    assert result["has_changes"] is True

    plan = plan_migration(discovered_rooms=discovered, existing_rooms=corrupt_store)
    assert set(plan["rooms"]) == {"9", "7"}
    assert plan["rooms"]["9"]["clean_passes"] == 3, (
        "the saved settings did not survive the walk past the junk rows"
    )
    assert plan["rooms"]["7"]["clean_passes"] == 4
    assert plan["id_remap"] == {5: 9}
    assert plan["dropped"] == []


def test_rec24_an_id_match_with_no_saved_name_is_not_a_rename():
    """[REC-24] A rename review needs an old slug to rename FROM.

    The rename branch fires when a discovered id matches a saved id but the slugs
    differ. A saved row carrying neither name nor slug has no slug to derive, so there
    is nothing to report a rename from -- and the arm skips to the next discovered room.

    WITHOUT THE GUARD THE USER SEES A REVIEW 'FROM NOTHING': the branch would append a
    `renamed` entry whose `old_slug` and `old_name` are empty strings, asking them to
    confirm a rename out of a blank. That is worse than silence, because a review is a
    prompt for a decision.

    THE EMPTY LIST HERE DOES EQUAL THE FALLBACK, so it only means something because the
    mutant produces a NON-empty one -- which the ablation confirms. `has_changes` is
    asserted too, since that is the flag the caller actually gates the prompt on.
    """
    result = compute_reconciliation(
        discovered_rooms=_discovered((5, "Study", "study")),
        existing_rooms={"5": {"room_id": 5}},
    )

    assert result["reviews"] == []
    assert result["has_changes"] is False
