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
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.setup.drift import (
    _DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS,
    _DEFAULT_AUTO_REFRESH_TRIGGERS,
    _DEFAULT_NEW_ROOM_CONFIRM_PASSES,
    _DEFAULT_REMOVAL_CONFIRM_PASSES,
    compute_room_drift,
    force_remove_room,
    get_discovery_cadence,
    reject_rooms,
    rejected_room_ids,
    unreject_rooms,
    update_drift_history,
)

from tests._factories import VAC as _VAC, MAP as _MAP, set_room_field
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
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert "1" in history

    reject_rooms(manager, _VAC, [1])

    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
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
