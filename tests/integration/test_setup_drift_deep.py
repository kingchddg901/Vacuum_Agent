"""Phase 8 integration tests — setup/drift.py deep paths.

Coverage targets
----------------
[DRD-1]  get_discovery_cadence returns defaults when no adapter registered.
[DRD-2]  get_discovery_cadence returns adapter-declared values when present.
[DRD-3]  reject_rooms adds room_ids to the rejected list.
[DRD-4]  reject_rooms is idempotent (duplicate ID not added twice).
[DRD-5]  reject_rooms removes the room from managed_rooms and populates affected_map_ids.
[DRD-6]  reject_rooms clears the room's drift history entry.
[DRD-7]  force_remove_room sets missing_passes to the configured threshold.
[DRD-8]  force_remove_room causes compute_room_drift to report the room as removed.
[DRD-9]  A4-SETUP-6: rejecting an id on one map leaves that id on another map.
[DRD-10] ...and leaves it DISCOVERABLE there, not silently filtered.
[DRD-11] Legacy flat (per-vacuum) rejections still apply to every map.
[DRD-12] unreject_rooms clears a legacy flat rejection — the escape hatch.
[DRD-13] unreject_rooms is map-scoped and reports what it did not clear.
[DRD-14] An un-rejected room resurfaces through the normal new_rooms cadence.
[DRD-15] Omitted map_id means "the only map" on a single-map vacuum.
[DRD-16] ...and is REFUSED on a multi-map vacuum rather than meaning "every map".
[DRD-17] The un-reject path refuses the same ambiguity, in the same way.
[DRD-18] SETUP-REJ-2: a direct save cannot resurrect a rejected room.
[DRD-19] ...and that enforcement is MAP-SCOPED, not the vacuum-wide union.
[DRD-20] ...and reading it does not create a setup_progress record.
[DRD-21] A STALE rejection must never delete an already-CONFIGURED room.
[DRD-22] ...but still refuses creation of an unconfigured rejected room.
[DRD-23] Empty map skeletons do not make a vacuum look multi-map.
[DRD-24] Emptying a map must not re-open the legacy flat list.
[DRD-25] Deleting a map removes that map's rejections (live-observed orphan).
[DRD-26] The stale-key sweep actually DELETES history for a room that is neither
         configured nor discovered -- the only thing bounding history growth --
         while a non-numeric key is skipped rather than crashing the pass.
[DRD-27] force_remove_room keeps the ORIGINAL first_missed_at across repeated
         passes. Overwriting it would reset the removal clock every pass, so a
         room would never age out.
[DRD-28] active_map_configured answers None ("cannot tell") rather than False
[DRD-34] ...and all FOUR of its answers are pinned exactly. [DRD-28] stops at
         `is None or is False`, which admits both of the values it exists to separate.
[DRD-35] reject_rooms on a vacuum with no maps writes the FLAT list and names no map.
[DRD-36] a corrupt room row does not stop the managed-rooms strip.
         ("definitely not") with no active_map entity or a blank state, and False
         only for a genuinely absent bucket. Conflating them re-opens save_rooms.
[DRD-29] rejected_room_ids survives a corrupt record: non-numeric entries skipped,
         a non-dict by_map ignored, map_id=None unions every map.
[DRD-30] _list_configured_room_ids and _room_lookup walk past junk buckets, junk
         rooms and non-numeric ids instead of raising.
[DRD-31] reject_rooms and unreject_rooms drop non-numeric requested ids, and
         unreject also drops non-numeric entries already in the stored list.
[DRD-32] run_discovery_pass survives an adapter whose resolve_active_map_id RAISES,
         and a manager that has no such method at all.
[DRD-33] _get_progress_record refuses to persist a record for an id this install
         does not have, returning an ephemeral one instead.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.setup.drift import (
    _DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS,
    _DEFAULT_AUTO_REFRESH_TRIGGERS,
    _DEFAULT_NEW_ROOM_CONFIRM_PASSES,
    _DEFAULT_REMOVAL_CONFIRM_PASSES,
    _get_progress_record,
    _list_configured_room_ids,
    _room_lookup,
    active_map_configured,
    compute_room_drift,
    force_remove_room,
    get_discovery_cadence,
    reject_rooms,
    rejected_room_ids,
    run_discovery_pass,
    unreject_rooms,
    update_drift_history,
)

from tests._factories import VAC as _VAC, MAP as _MAP, set_room_field


def _deep_history(manager, map_id=None):
    """The drift-history bucket, merged across maps (DR-MAPHIST).

    History is stored per map now. These assertions are single-map, so the merge is
    the whole of it; writing it as a merge rather than a fixed key means a second map
    added to a fixture later cannot make an assertion pass by reading an empty dict.
    """
    rec = manager.data["setup_progress"][_VAC]
    by_map = rec.get("room_drift_history_by_map") or {}
    if map_id is not None:
        return by_map.get(str(map_id), {})
    out = {}
    for bucket in by_map.values():
        out.update(bucket)
    return out

from .conftest import setup_map


def _mark_rooms_configured(manager, vacuum_entity_id: str, map_id: str) -> None:
    """Mark all rooms in a map bucket as configured (is_configured=True)."""
    for room_id in manager.data["maps"][vacuum_entity_id][map_id]["rooms"]:
        set_room_field(manager, room_id, vac=vacuum_entity_id, map_id=map_id,
                       is_configured=True)


# ---------------------------------------------------------------------------
# [DRD-1] get_discovery_cadence defaults
# ---------------------------------------------------------------------------

def test_get_discovery_cadence_defaults_when_no_adapter(manager):
    """[DRD-1] Returns default cadence values when no adapter is registered."""
    cadence = get_discovery_cadence(_VAC)
    assert cadence["removal_confirmation_passes"] == _DEFAULT_REMOVAL_CONFIRM_PASSES
    assert cadence["new_room_confirmation_passes"] == _DEFAULT_NEW_ROOM_CONFIRM_PASSES
    assert cadence["auto_refresh_interval_seconds"] == _DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS
    assert cadence["auto_refresh_on"] == list(_DEFAULT_AUTO_REFRESH_TRIGGERS)


# ---------------------------------------------------------------------------
# [DRD-2] get_discovery_cadence adapter-declared values
# ---------------------------------------------------------------------------

def test_get_discovery_cadence_uses_adapter_values(manager):
    """[DRD-2] Returns adapter-declared discovery cadence when present."""
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        "source": "test",
        "entities": {},
        "discovery": {
            "removal_confirmation_passes": 5,
            "new_room_confirmation_passes": 2,
            "auto_refresh_interval_seconds": 3600,
            "auto_refresh_on": ["vacuum_docked"],
        },
    })
    cadence = get_discovery_cadence(_VAC)
    assert cadence["removal_confirmation_passes"] == 5
    assert cadence["new_room_confirmation_passes"] == 2
    assert cadence["auto_refresh_interval_seconds"] == 3600
    assert cadence["auto_refresh_on"] == ["vacuum_docked"]


# ---------------------------------------------------------------------------
# [DRD-3] / [DRD-4] reject_rooms basic behaviour
# ---------------------------------------------------------------------------

def test_reject_rooms_adds_room_ids(manager):
    """[DRD-3] reject_rooms records the room IDs as rejected.

    Asserted through ``rejected_room_ids`` rather than by reading a storage key:
    A4-SETUP-6 moved WHERE a rejection is written (per-map, not one flat list)
    without changing WHAT it means, and a test that names the backing fails on a
    correct refactor while telling you nothing about behaviour.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    result = reject_rooms(manager, _VAC, [1, 2])
    record = manager.data["setup_progress"][_VAC]
    assert rejected_room_ids(record, map_id=_MAP) == {1, 2}
    assert result["rejected"] == [1, 2]


def test_reject_rooms_is_idempotent(manager):
    """[DRD-4] Calling reject_rooms twice with the same ID does not duplicate it."""
    setup_map(manager, _VAC, _MAP, count=1)
    reject_rooms(manager, _VAC, [1])
    second = reject_rooms(manager, _VAC, [1])
    record = manager.data["setup_progress"][_VAC]
    assert rejected_room_ids(record, map_id=_MAP) == {1}
    assert second["rejected"] == []          # nothing new to add
    stored = record["rejected_rooms_by_map"][_MAP]
    assert stored.count(1) == 1


# ---------------------------------------------------------------------------
# [DRD-5] reject_rooms removes room from managed_rooms
# ---------------------------------------------------------------------------

def test_reject_rooms_removes_from_managed_rooms(manager):
    """[DRD-5] reject_rooms strips the room from managed_rooms and returns affected_map_ids."""
    setup_map(manager, _VAC, _MAP, count=2)
    _mark_rooms_configured(manager, _VAC, _MAP)

    result = reject_rooms(manager, _VAC, [1])

    rooms = manager.data["maps"][_VAC][_MAP].get("rooms", {})
    assert "1" not in rooms
    assert 1 in result["removed_from_managed"]
    assert _MAP in result["affected_map_ids"]


# ---------------------------------------------------------------------------
# [DRD-6] reject_rooms clears drift history
# ---------------------------------------------------------------------------

def test_reject_rooms_clears_drift_history_entry(manager):
    """[DRD-6] reject_rooms removes the rejected room's entry from room_drift_history."""
    setup_map(manager, _VAC, _MAP, count=2)
    _mark_rooms_configured(manager, _VAC, _MAP)

    # Seed a drift history entry for room 1.
    update_drift_history(manager, _VAC, discovered_room_ids={1, 2})
    history = _deep_history(manager)
    assert "1" in history

    reject_rooms(manager, _VAC, [1])

    history = _deep_history(manager)
    assert "1" not in history


# ---------------------------------------------------------------------------
# [DRD-7] force_remove_room sets missing_passes to threshold
# ---------------------------------------------------------------------------

def test_force_remove_room_sets_missing_passes_to_threshold(manager):
    """[DRD-7] force_remove_room writes missing_passes = removal_confirmation_passes."""
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    result = force_remove_room(manager, _VAC, room_id=1)

    expected_threshold = _DEFAULT_REMOVAL_CONFIRM_PASSES
    assert result["missing_passes"] == expected_threshold
    assert result["threshold"] == expected_threshold
    assert result["room_id"] == 1


def test_force_remove_room_does_not_decrease_existing_passes(manager):
    """[DRD-7] force_remove_room keeps higher existing missing_passes (uses max)."""
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    # Manually set missing_passes above the threshold.
    manager.data.setdefault("setup_progress", {})
    manager.data["setup_progress"].setdefault(_VAC, {"room_drift_history": {}})
    manager.data["setup_progress"][_VAC]["room_drift_history"]["1"] = {
        "missing_passes": 99,
        "seen_passes": 0,
        "last_seen_at": None,
        "first_missed_at": None,
        "first_seen_at": None,
    }

    result = force_remove_room(manager, _VAC, room_id=1)

    assert result["missing_passes"] == 99  # max(99, threshold=3) = 99


# ---------------------------------------------------------------------------
# [DRD-8] force_remove_room causes compute_room_drift to surface removed_rooms
# ---------------------------------------------------------------------------

def test_force_remove_room_surfaces_in_compute_room_drift(manager):
    """[DRD-8] After force_remove_room, compute_room_drift reports room in removed_rooms."""
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    force_remove_room(manager, _VAC, room_id=1)
    result = compute_room_drift(manager, _VAC, discovered_room_ids=set())

    removed_ids = {r["room_id"] for r in result["removed_rooms"]}
    assert 1 in removed_ids
    assert result["in_sync"] is False


# ---------------------------------------------------------------------------
# [DRD-9..14] A4-SETUP-6 — rejection is per MAP, and reversible
#
# The filed mechanism, verbatim: Eufy reissues room ids 1..N from scratch on
# every map, so id 3 downstairs and id 3 upstairs are different physical rooms.
# Rejection was stored as one flat per-VACUUM list, so rejecting a ghost id 3 on
# the ground floor made the REAL id 3 upstairs unconfigurable — permanently, and
# invisibly, because a rejected id never surfaces in new_rooms for the user to
# notice it is missing. There was also no un-reject path at all.
#
# These tests exercise a two-map install, which is what activates it. Every
# single-map shape (each of DRD-3..8 above, all of which still call reject_rooms
# with no map_id) keeps the pre-change behaviour on purpose.
# ---------------------------------------------------------------------------

_MAP_B = "2"


def _setup_two_maps(manager, count: int = 3):
    """Seed two maps for one vacuum, both with rooms 1..count configured."""
    setup_map(manager, _VAC, _MAP, count=count)
    _mark_rooms_configured(manager, _VAC, _MAP)
    setup_map(manager, _VAC, _MAP_B, count=count)
    _mark_rooms_configured(manager, _VAC, _MAP_B)


def _seed_legacy_rejection(manager, room_ids: list[int]) -> None:
    """Write a setup_progress record in the PRE-A4-SETUP-6 shape.

    Deliberately omits ``rejected_rooms_by_map`` entirely rather than seeding it
    empty: that absent key is what a record written by an older build actually
    looks like on disk, and reading one is the compatibility claim being tested.
    """
    manager.data.setdefault("setup_progress", {})[_VAC] = {
        "completed_steps": [],
        "last_advanced_at": None,
        "rejected_rooms": list(room_ids),
        "room_drift_history": {},
    }


def test_map_scoped_rejection_leaves_the_same_id_on_another_map(manager):
    """[DRD-9] The filed defect: rejecting ghost id 3 downstairs must not take
    the REAL id 3 upstairs with it."""
    _setup_two_maps(manager)

    result = reject_rooms(manager, _VAC, [3], map_id=_MAP)

    assert "3" not in manager.data["maps"][_VAC][_MAP]["rooms"]
    assert "3" in manager.data["maps"][_VAC][_MAP_B]["rooms"], (
        "room 3 on the OTHER map was stripped — this is A4-SETUP-6"
    )
    assert result["affected_map_ids"] == [_MAP]
    assert result["map_id"] == _MAP


def test_map_scoped_rejection_does_not_hide_the_id_on_another_map(manager):
    """[DRD-10] ...and the id stays DISCOVERABLE on the other map, which is the
    half the user would actually notice: a filtered id never reaches new_rooms,
    so it cannot be configured and cannot be complained about."""
    _setup_two_maps(manager)
    reject_rooms(manager, _VAC, [3], map_id=_MAP)

    record = manager.data["setup_progress"][_VAC]
    assert 3 in rejected_room_ids(record, map_id=_MAP)
    assert 3 not in rejected_room_ids(record, map_id=_MAP_B)


def test_legacy_flat_rejection_still_applies_to_every_map(manager):
    """[DRD-11] Existing installs must not change. A rejection recorded before
    this change carries no map, so it keeps applying everywhere — which is what
    the user meant when only one map existed."""
    _setup_two_maps(manager)
    _seed_legacy_rejection(manager, [3])

    record = manager.data["setup_progress"][_VAC]
    assert 3 in rejected_room_ids(record, map_id=_MAP)
    assert 3 in rejected_room_ids(record, map_id=_MAP_B)
    assert 3 in rejected_room_ids(record)          # no map dimension -> union


def test_unreject_clears_a_legacy_flat_rejection(manager):
    """[DRD-12] The escape hatch. An install that ALREADY hit the defect has a
    flat entry blocking a real room; clearing it is the documented way out, and
    it must not require hand-editing .storage."""
    _setup_two_maps(manager)
    _seed_legacy_rejection(manager, [3])

    result = unreject_rooms(manager, _VAC, [3], map_id=_MAP_B)

    assert result["unrejected"] == [3]
    record = manager.data["setup_progress"][_VAC]
    assert record["rejected_rooms"] == []
    assert 3 not in rejected_room_ids(record, map_id=_MAP)
    assert 3 not in rejected_room_ids(record, map_id=_MAP_B)


def test_unreject_is_scoped_and_reports_what_it_did_not_clear(manager):
    """[DRD-13] Un-rejecting on one map leaves another map's rejection standing,
    and SAYS SO rather than implying a clean sweep."""
    _setup_two_maps(manager)
    reject_rooms(manager, _VAC, [3], map_id=_MAP)
    reject_rooms(manager, _VAC, [3], map_id=_MAP_B)

    result = unreject_rooms(manager, _VAC, [3], map_id=_MAP_B)

    record = manager.data["setup_progress"][_VAC]
    assert 3 not in rejected_room_ids(record, map_id=_MAP_B)
    assert 3 in rejected_room_ids(record, map_id=_MAP)
    assert result["still_rejected_on"] == {_MAP: [3]}


def test_unrejected_room_resurfaces_as_new_on_the_next_pass(manager):
    """[DRD-14] Un-reject is only useful if the room comes BACK. It returns
    through the normal new_rooms cadence, not instantly."""
    setup_map(manager, _VAC, _MAP, count=3)
    _mark_rooms_configured(manager, _VAC, _MAP)
    reject_rooms(manager, _VAC, [3], map_id=_MAP)

    update_drift_history(manager, _VAC, discovered_room_ids={1, 2, 3}, map_id=_MAP)
    drift = compute_room_drift(
        manager, _VAC, discovered_room_ids={1, 2, 3}, map_id=_MAP
    )
    assert 3 not in {r["room_id"] for r in drift["new_rooms"]}

    unreject_rooms(manager, _VAC, [3], map_id=_MAP)

    update_drift_history(manager, _VAC, discovered_room_ids={1, 2, 3}, map_id=_MAP)
    drift = compute_room_drift(
        manager, _VAC, discovered_room_ids={1, 2, 3}, map_id=_MAP
    )
    assert 3 in {r["room_id"] for r in drift["new_rooms"]}


def test_omitted_map_id_means_the_only_map_not_every_map(manager):
    """[DRD-15] On a SINGLE-map vacuum, omitting map_id is unambiguous and the
    rejection is pinned to that map — so a second floor added later inherits
    nothing."""
    setup_map(manager, _VAC, _MAP, count=3)
    _mark_rooms_configured(manager, _VAC, _MAP)

    result = reject_rooms(manager, _VAC, [3])

    assert result["map_id"] == _MAP
    record = manager.data["setup_progress"][_VAC]
    assert record["rejected_rooms"] == []          # nothing new lands in the flat list
    assert rejected_room_ids(record, map_id=_MAP) == {3}


def test_omitted_map_id_is_refused_on_a_multi_map_vacuum(manager):
    """[DRD-16] ...and on a MULTI-map vacuum it refuses instead of guessing.

    'Every map' is not a safe reading of an unqualified room id — that reading IS
    A4-SETUP-6. The refusal writes nothing and names the maps so the caller can
    re-issue.
    """
    _setup_two_maps(manager)

    result = reject_rooms(manager, _VAC, [3])

    assert result["status"] == "error"
    assert result["reason"] == "map_ambiguous"
    assert sorted(result["map_ids"]) == sorted([_MAP, _MAP_B])
    assert result["rejected"] == []
    # Refused means NOTHING happened — both maps keep room 3.
    assert "3" in manager.data["maps"][_VAC][_MAP]["rooms"]
    assert "3" in manager.data["maps"][_VAC][_MAP_B]["rooms"]


def test_unreject_without_map_id_is_refused_on_a_multi_map_vacuum(manager):
    """[DRD-17] The recovery path refuses the same ambiguity.

    Un-reject is NOT the safe direction of an ambiguous call: the legacy flat
    entry it clears is exactly the vacuum-global one, so an unqualified un-reject
    would un-hide an id on every floor at once — A4-SETUP-6 pointed the other way.
    """
    _setup_two_maps(manager)
    _seed_legacy_rejection(manager, [3])

    result = unreject_rooms(manager, _VAC, [3])

    assert result["status"] == "error"
    assert result["reason"] == "map_ambiguous"
    assert result["unrejected"] == []
    assert manager.data["setup_progress"][_VAC]["rejected_rooms"] == [3]  # untouched


# ---------------------------------------------------------------------------
# [DRD-18..20] SETUP-REJ-2 — the write boundary enforces rejection
#
# build_managed_rooms has always accepted rejected_rooms= and skipped those ids
# (CRUD-5); save_managed_rooms, its only production caller, never passed it, so
# the skip had never executed. No symptom, because rejected ids are filtered out
# of new_rooms a layer up and so never reach the save as candidates — but that is
# a UI-path protection, and a direct service call with explicit enabled_room_ids
# walks past it.
# ---------------------------------------------------------------------------

def test_save_managed_rooms_refuses_to_create_a_rejected_room(manager):
    """[DRD-18] A direct save cannot resurrect a rejected room, even when the
    caller explicitly enables it — the bypass the drift filter cannot see."""
    setup_map(manager, _VAC, _MAP, count=3)
    _mark_rooms_configured(manager, _VAC, _MAP)
    reject_rooms(manager, _VAC, [3], map_id=_MAP)
    assert "3" not in manager.data["maps"][_VAC][_MAP]["rooms"]

    # The hand-written call the panel would never make: ask for room 3 by name.
    manager.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, enabled_room_ids=[1, 2, 3]
    )

    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert "3" not in rooms, "a rejected room was re-created by a direct save"
    assert {"1", "2"} <= set(rooms)


def test_save_managed_rooms_rejection_is_map_scoped(manager):
    """[DRD-19] THE TRAP. The write boundary must use the MAP-SCOPED set: passing
    the vacuum-wide union would drop a real room on map B out of a save the user
    explicitly asked for, because an unrelated ghost shared its id on map A."""
    _setup_two_maps(manager)
    reject_rooms(manager, _VAC, [3], map_id=_MAP)

    manager.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP_B, enabled_room_ids=[1, 2, 3]
    )

    assert "3" in manager.data["maps"][_VAC][_MAP_B]["rooms"], (
        "room 3 on map B was dropped by map A's rejection — A4-SETUP-6 at a new site"
    )


def test_save_managed_rooms_does_not_create_a_setup_progress_record(manager):
    """[DRD-20] Reading the rejection set must not materialise setup-progress
    state — a save asks a question, it does not own that record."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.data.pop("setup_progress", None)

    manager.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, enabled_room_ids=[1, 2]
    )

    assert _VAC not in (manager.data.get("setup_progress") or {})


# ---------------------------------------------------------------------------
# [DRD-21..22] SETUP-REJ-2 regression — a rejection must never DELETE a room
#
# Caught on live data minutes after SETUP-REJ-2 shipped, not by review. The
# install carried rejected_rooms=[10] (a legacy flat entry, no map) AND a
# configured room 10 named "Cat Room" on a LATER map. Those coexist precisely
# BECAUSE the exclusion had never been wired — so wiring it converted a dormant
# stale entry into an active deleter of a real room, settings and all, on the
# next Configure-rooms save.
#
# Chris's own rule, from adjudicating A4-SETUP-6: rejection "refuses the room's
# CREATION, it does not delete a room."
# ---------------------------------------------------------------------------

def test_a_stale_rejection_does_not_delete_a_configured_room(manager):
    """[DRD-21] The live shape: legacy flat [10] + configured room 10 on a map."""
    setup_map(manager, _VAC, _MAP, count=10)
    _mark_rooms_configured(manager, _VAC, _MAP)
    _seed_legacy_rejection(manager, [10])

    before = set(manager.data["maps"][_VAC][_MAP]["rooms"])
    assert "10" in before

    manager.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP,
        enabled_room_ids=list(range(1, 11)),
    )

    after = set(manager.data["maps"][_VAC][_MAP]["rooms"])
    assert "10" in after, "a stale rejection deleted a CONFIGURED room"
    assert before == after


def test_a_rejection_still_refuses_an_unconfigured_room(manager):
    """[DRD-22] ...and the guard is not a blanket disable: an id rejected on THIS
    map still refuses creation of a room that was never configured."""
    setup_map(manager, _VAC, _MAP, count=3)
    # room 3 discovered but never configured, and rejected on this map
    manager.data["maps"][_VAC][_MAP]["rooms"].pop("3", None)
    reject_rooms(manager, _VAC, [3], map_id=_MAP)

    manager.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, enabled_room_ids=[1, 2, 3]
    )

    assert "3" not in manager.data["maps"][_VAC][_MAP]["rooms"], (
        "the exclusion stopped refusing creation entirely"
    )


# ---------------------------------------------------------------------------
# [DRD-23] A stored bucket is not a map
#
# Found on live data: alfred carried maps 7, 11 and 12 where only 12 was ever
# configured. 7 and 11 are untouched skeletons — every field at its default.
# ensure_map_bucket is called from ~38 sites, many keyed on "the active map", and
# Eufy firmware only rolls the active id FORWARD, so each re-map strands a bucket
# nothing prunes. Counting buckets made a single-map vacuum look multi-map and
# would have refused an unqualified reject as ambiguous.
# ---------------------------------------------------------------------------

def test_empty_map_skeletons_do_not_make_a_vacuum_multi_map(manager):
    """[DRD-23] Only maps carrying rooms count toward the ambiguity check."""
    setup_map(manager, _VAC, _MAP, count=3)
    _mark_rooms_configured(manager, _VAC, _MAP)
    # two stranded skeletons, exactly as they appear on disk
    for ghost in ("7", "11"):
        manager.data["maps"][_VAC][ghost] = {
            "map_id": ghost, "metadata": {}, "rooms": {}, "summary": {},
            "custom_layouts": {}, "active_custom_layout_id": "",
            "segment_room_links": {}, "companion_anchors": {}, "saved_zones": {},
        }

    result = reject_rooms(manager, _VAC, [3])

    assert result.get("reason") != "map_ambiguous", (
        "empty skeletons made a single-map vacuum look ambiguous"
    )
    assert result["map_id"] == _MAP
    assert result["rejected"] == [3]


def test_rejecting_the_last_room_does_not_reopen_the_legacy_flat_list(manager):
    """[DRD-24] Rejecting the LAST room on a map empties it, so that map stops
    carrying rooms — and a follow-up unqualified reject must still land on that
    map, not fall through to the vacuum-global flat list this change retired."""
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    reject_rooms(manager, _VAC, [1])
    assert not manager.data["maps"][_VAC][_MAP]["rooms"], "precondition: map emptied"

    second = reject_rooms(manager, _VAC, [2])

    record = manager.data["setup_progress"][_VAC]
    assert record["rejected_rooms"] == [], (
        "a rejection was appended to the LEGACY flat list — it must stay read-only"
    )
    assert second["map_id"] == _MAP
    assert rejected_room_ids(record, map_id=_MAP) == {1, 2}


def test_deleting_a_map_takes_its_rejections_with_it(manager):
    """[DRD-25] Observed on a live box: by_map["99"] survived deleting map 99.

    Rejections are per map, so a deleted map's must go too. They live inside the
    per-VACUUM setup_progress record, not a per-map store, so remove_map's
    PER_MAP_STORES loop cannot reach them. Eufy rolls map ids FORWARD only, so an
    id is not retired for good — a stranded entry means a future map reaching that
    number inherits a rejection made for a different one.
    """
    _setup_two_maps(manager)
    reject_rooms(manager, _VAC, [3], map_id=_MAP_B)
    record = manager.data["setup_progress"][_VAC]
    assert record["rejected_rooms_by_map"].get(_MAP_B) == [3]

    manager.remove_map(vacuum_entity_id=_VAC, map_id=_MAP_B)

    assert _MAP_B not in manager.data["setup_progress"][_VAC]["rejected_rooms_by_map"]
    # the surviving map's rejections are untouched
    reject_rooms(manager, _VAC, [1], map_id=_MAP)
    assert rejected_room_ids(
        manager.data["setup_progress"][_VAC], map_id=_MAP
    ) == {1}


# ---------------------------------------------------------------------------
# Gaps closed from the 2026-11-07 coverage classification (85.1%, ceiling 98.6%).
# It found no DEAD and no DEFECT here: all 43 reachable gaps are untested guards,
# and the five it called DEFENSIVE (860-861, 1126, 1129-1130) are left alone
# because rooms/room_discovery.py already coerces room_id to int, so only a
# patched producer reaches them.
# ---------------------------------------------------------------------------


def _history_bucket(manager, map_id):
    """The LIVE per-map history dict (``_deep_history`` merges into a copy for
    map_id=None, which cannot be mutated usefully)."""
    rec = manager.data["setup_progress"][_VAC]
    return rec.setdefault("room_drift_history_by_map", {}).setdefault(str(map_id), {})


def test_stale_history_keys_are_swept_but_junk_keys_survive(manager):
    """[DRD-26] the sweep is the only thing bounding history growth.

    The module's own comment says it "prevents history from growing unboundedly
    across years". Nothing else trims this dict, so if the sweep stops working the
    record grows for the life of the install with no visible symptom.

    The junk key is asserted to SURVIVE deliberately, which is what the code does:
    a non-numeric key hits ``continue`` before the retainable test, so it is never
    collected as stale. That is a documented trade (a hand-edited record must not
    crash the pass) rather than an oversight, and pinning it stops someone
    "fixing" the skip into a delete.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    _mark_rooms_configured(manager, _VAC, _MAP)
    update_drift_history(manager, _VAC, discovered_room_ids={1, 2})

    bucket = _history_bucket(manager, _MAP)
    assert "1" in bucket and "2" in bucket  # precondition: real rooms are tracked
    bucket["99"] = {"missing_passes": 3, "seen_passes": 0}   # no such room anywhere
    bucket["abc"] = {"missing_passes": 1, "seen_passes": 0}  # non-numeric key

    update_drift_history(manager, _VAC, discovered_room_ids={1, 2})

    after = _history_bucket(manager, _MAP)
    assert "99" not in after, (
        "a room that is neither configured nor discovered must be swept - this is "
        "the only bound on history size"
    )
    assert "abc" in after, "a non-numeric key is skipped, not deleted, and not fatal"
    assert "1" in after and "2" in after, "live rooms are untouched"


def test_force_remove_keeps_the_original_first_missed_at(manager, monkeypatch):
    """[DRD-27] the removal clock must not restart every pass.

    ``first_missed_at`` is written only when it is None. Drop that guard and each
    pass stamps "now", so the field always reads as just-missed and anything
    measuring how long a room has been gone never advances. The two distinct
    clock values are what make the overwrite visible.
    """
    import custom_components.eufy_vacuum.setup.drift as drift_mod

    stamps = iter(["2026-01-01T00:00:00+00:00", "2026-02-02T00:00:00+00:00"])
    monkeypatch.setattr(drift_mod, "_iso_now", lambda: next(stamps))

    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    force_remove_room(manager, _VAC, room_id=1)
    first = _deep_history(manager)["1"]["first_missed_at"]
    assert first == "2026-01-01T00:00:00+00:00"

    force_remove_room(manager, _VAC, room_id=1)
    again = _deep_history(manager)["1"]["first_missed_at"]

    assert again == first, (
        "the SECOND pass must not restamp first_missed_at - it is when the room was "
        f"first missed, not when it was last seen missing (got {again})"
    )


def test_active_map_configured_says_unknown_not_false(manager):
    """[DRD-28] None and False mean different things here.

    The comment beside the bucket lookup spells out the cost of conflating them: a
    miss "returns False, which re-opens the save_rooms step against a map that is
    configured perfectly well." So "I cannot tell" (no active_map entity declared,
    or the entity exists but reads blank) has to stay None, while False is reserved
    for a map that genuinely has no configured rooms.
    """
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    # No adapter registered for this id -> no entities.active_map declared.
    assert active_map_configured(manager, "vacuum.no_adapter_at_all") is None, (
        "cannot tell is not the same as not configured"
    )

    # A declared entity whose state is absent is equally unknowable.
    register_adapter_config(
        "drd28", {"entities": {"active_map": "sensor.drd28_active_map"}}
    )
    manager.data.setdefault("adapters", {})["vacuum.drd28"] = "drd28"
    result = active_map_configured(manager, "vacuum.drd28")
    assert result is None or result is False  # shape-dependent; never raises
    assert result is not True


def test_rejected_room_ids_survives_a_corrupt_record(manager):
    """[DRD-29] the rejection list is user-editable storage, so it can be junk.

    map_id=None unions every map, which is the documented pre-A4-SETUP-6 behaviour
    for an adapter that cannot name its active map. A non-numeric entry is dropped
    rather than crashing the discovery pass that reads it.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    rec = _get_progress_record(manager, _VAC)
    rec["rejected_rooms"] = ["x", 3]
    rec["rejected_rooms_by_map"] = {"A": [1], "B": ["y", 2]}

    unioned = rejected_room_ids(rec, map_id=None)
    assert unioned == {1, 2, 3}, f"every map's rejections, junk dropped; got {unioned}"

    rec["rejected_rooms_by_map"] = "corrupt-not-a-dict"
    only_flat = rejected_room_ids(rec, map_id=None)
    assert only_flat == {3}, "a non-dict by_map is ignored, the flat list still applies"


def test_room_walkers_step_over_junk(manager):
    """[DRD-30] both room walkers face the same hand-edited storage.

    Each guard is a separate `continue`; removing any one of them raises
    TypeError or ValueError mid-pass and takes down the whole discovery run,
    which is why the assertions name the surviving rooms rather than just
    "no exception".
    """
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)

    maps = manager.data["maps"][_VAC]
    maps["junk_bucket"] = "not-a-dict"
    maps["B"] = {"rooms": {"1": "not-a-dict", "abc": {"is_configured": True},
                           "7": {"is_configured": True, "name": "Study"}}}

    configured = _list_configured_room_ids(manager, _VAC)
    assert 7 in configured, "the one valid configured room in map B is found"
    assert all(isinstance(r, int) for r in configured), configured

    lookup = _room_lookup(manager, _VAC)
    assert 7 in lookup
    assert all(isinstance(k, int) for k in lookup), lookup


def test_reject_and_unreject_drop_non_numeric_ids(manager):
    """[DRD-31] ids arrive from a service call, so they are not guaranteed numeric.

    unreject additionally rewrites the stored list, so a junk entry already on
    disk is dropped on the way out rather than carried forward forever.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    _mark_rooms_configured(manager, _VAC, _MAP)

    reject_rooms(manager, _VAC, ["x", 1])
    rec = _get_progress_record(manager, _VAC)
    assert rejected_room_ids(rec, map_id=_MAP) == {1}, "junk id dropped"

    rec.setdefault("rejected_rooms", [])
    rec["rejected_rooms"] = ["junk", 3, 4]

    unreject_rooms(manager, _VAC, ["y", 3])
    assert 3 not in (rec.get("rejected_rooms") or []), "3 was un-rejected"
    assert "junk" not in (rec.get("rejected_rooms") or []), (
        "a non-numeric entry already stored is dropped on rewrite, not carried"
    )
    assert 4 in (rec.get("rejected_rooms") or []), "an untouched rejection survives"


def test_discovery_pass_survives_a_bad_active_map_resolver(hass, manager, monkeypatch):
    """[DRD-32] discovery must not die because one adapter read failed.

    The code's own comment: resolution is best-effort, and an adapter that cannot
    name its active map yields None, "i.e. exactly the pre-A4-SETUP-6 behaviour
    rather than a silently unfiltered pass". Both shapes are covered: a resolver
    that RAISES and a manager with no resolver at all.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    _mark_rooms_configured(manager, _VAC, _MAP)

    def _boom(_vacuum_entity_id):
        raise RuntimeError("adapter could not read the active map")

    monkeypatch.setattr(manager, "resolve_active_map_id", _boom)
    result = run_discovery_pass(hass, manager, _VAC)
    assert result is not None, "the pass still returns a result"

    monkeypatch.delattr(manager, "resolve_active_map_id", raising=False)
    again = run_discovery_pass(hass, manager, _VAC)
    assert again is not None, "a manager without the method is the same best-effort case"


def test_progress_record_refuses_an_unreal_vacuum_id(manager):
    """[DRD-33] a truncated or wrong entity id must not create persistent state.

    Without the guard, `setup_progress["vacuum.iv"]` gains a full record that
    nothing ever reaps. The caller still gets a working dict so no call site has
    to handle None; it simply never reaches the store.
    """
    before = set(manager.data.get("setup_progress", {}))

    rec = _get_progress_record(manager, _VAC[:-1])  # a truncated entity id

    assert rec["completed_steps"] == []
    assert rec["rejected_rooms"] == []
    assert _VAC[:-1] not in manager.data.get("setup_progress", {}), (
        "an id this install does not have must not gain a persisted record"
    )
    assert set(manager.data.get("setup_progress", {})) == before


async def test_drd34_active_map_configured_is_exactly_tri_state(hass, manager):
    """[DRD-34] Each of the four answers pinned to one value, not a disjunction.

    [DRD-28] states the claim -- None means "cannot tell", False means "this map has no
    configured rooms" -- and then asserts `result is None or result is False`, which
    cannot tell them apart. It also registers its adapter under `"drd28"` while the
    lookup is `get_adapter_config(vacuum_entity_id)`, so the config never resolves and
    the function returns at the no-entity-declared guard without reaching the state
    read at all. That is why the blank-state and missing-bucket arms are both
    uncovered despite a test named for them.

    WHY THE DISTINCTION IS LOAD-BEARING, from the comment beside the bucket lookup: a
    miss "returns False, which re-opens the save_rooms step against a map that is
    configured perfectly well." False is an instruction to re-run setup. None is not.

    The four inputs differ by one thing each, so a deleted arm is attributable:
    no state at all, a blank state, a state naming a map with no bucket, and the
    configured map. The last is the control -- without it the three Nones and Falses
    would be satisfied by a function that could never answer True.
    """
    setup_map(manager, _VAC, _MAP, count=1)
    _mark_rooms_configured(manager, _VAC, _MAP)
    register_adapter_config(_VAC, {"entities": {"active_map": "sensor.drd34_map"}})

    # 1. The entity is declared and has no state yet -- unknowable.
    assert active_map_configured(manager, _VAC) is None, (
        "a declared entity with no state is 'cannot tell', not 'not configured'"
    )

    # 2. Declared, present, and blank -- still unknowable.
    hass.states.async_set("sensor.drd34_map", "unavailable")
    assert active_map_configured(manager, _VAC) is None

    # 3. A real map name this vacuum holds no bucket for -- KNOWN not configured.
    hass.states.async_set("sensor.drd34_map", "a_map_this_vacuum_never_had")
    assert active_map_configured(manager, _VAC) is False, (
        "an active map with no bucket is a definite answer, not an unknown one"
    )

    # 4. The configured map -- the control, so the three answers above are the guards
    #    talking rather than a function that cannot say yes.
    hass.states.async_set("sensor.drd34_map", _MAP)
    assert active_map_configured(manager, _VAC) is True


async def test_drd35_reject_rooms_with_no_maps_uses_the_flat_list(hass, manager):
    """[DRD-35] The pre-A4-SETUP-6 shape, which is still what a no-map vacuum gets.

    `reject_rooms` keeps two stores: `rejected_rooms_by_map` when a map is named, and a
    flat `rejected_rooms` when one cannot be. [DRD-3] through [DRD-6] all drive the
    map-scoped arm, so the flat arm -- the one an adapter that cannot name its active
    map actually uses -- had no test.

    BOTH HALVES OF THE ARM ARE ASSERTED, because they are separate statements twenty
    lines apart: the READ that seeds `bucket_list` from the flat key, and the WRITE
    that puts it back. The pre-seeded `[9]` is what makes the read visible -- without
    it a broken read would produce `[4]`, which is indistinguishable from a working
    one. The result's `map_id is None` and the absence of a by-map bucket are what show
    nothing leaked into the scoped store under a "None" key.
    """
    # THE VACUUM HAS TO BE REAL, which a first draft missed. `_get_progress_record`
    # refuses to PERSIST a record for an id this install does not have and hands back
    # an ephemeral one instead ([DRD-33]), so without a state the seed below landed in
    # a throwaway dict and `reject_rooms` was handed a different one. A state with no
    # maps is also the honest input: a vacuum that exists but has not been discovered
    # yet is exactly when an adapter cannot name an active map.
    hass.states.async_set(_VAC, "docked")

    record = _get_progress_record(manager, _VAC)
    record["rejected_rooms"] = [9]

    result = reject_rooms(manager, _VAC, [4])

    assert record["rejected_rooms"] == [9, 4], "the flat list was not read, or not written"
    assert result["map_id"] is None
    assert not record.get("rejected_rooms_by_map"), (
        "a vacuum that cannot name its map must not gain a 'None'-keyed bucket"
    )


async def test_drd36_a_corrupt_room_row_does_not_stop_the_strip(manager):
    """[DRD-36] The managed-rooms strip walks user-editable storage.

    Two skips, both in the same loop: a room value that is not a dict, and one whose
    `room_id` will not coerce to an int. Either would raise on the next statement.

    POSITIONAL, AND THE ORDER IS THE INPUT. Both junk rows are inserted BEFORE the real
    room 7, so a `break` or an early return in either place would leave 7 in
    `managed_rooms` and report nothing removed. With the junk last, the strip would
    succeed first and the skips would be invisible.

    The surviving keys are asserted, not just the removal: `{'a', 'b'}` shows the junk
    rows were LEFT ALONE rather than swept, which is the difference between "skipped"
    and "deleted because we could not read it".
    """
    setup_map(manager, _VAC, _MAP, count=1)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    rooms.clear()
    rooms["a"] = "not-a-dict"
    rooms["b"] = {"room_id": "xyz"}
    rooms["7"] = {"room_id": 7, "name": "kitchen"}

    result = reject_rooms(manager, _VAC, [7], map_id=_MAP)

    assert result["removed_from_managed"] == [7]
    assert set(rooms) == {"a", "b"}, (
        "an unreadable room row was deleted rather than skipped"
    )
