"""Phase 7 integration tests — setup/drift.py.

Coverage targets
----------------
[DR-1]  is_step_completed returns False for empty progress.
[DR-2]  is_step_completed returns True after step recorded.
[DR-3]  record_step_completed adds step to completed_steps.
[DR-4]  record_step_completed is idempotent (no duplicates).
[DR-5]  record_step_completed ignores unknown step IDs.
[DR-6]  get_adapter_setup_steps returns default when no adapter.
[DR-7]  get_adapter_setup_steps returns declared steps from adapter.
[DR-8]  compute_room_drift returns in_sync=True with no configured rooms.
[DR-9]  compute_room_drift with discovered_room_ids=None and no history → in_sync.
[DR-10] update_drift_history increments missing_passes for absent rooms.
[DR-11] update_drift_history resets missing_passes when room reappears.
[DR-12] compute_room_drift surfaces removed_rooms after threshold misses.
[DR-13] compute_room_drift surfaces new_rooms immediately (n_new=1 default).
[DR-14] _list_configured_room_ids excludes is_configured=False rooms from drift tracking.
[DR-15] get_discovery_cadence honors an explicit low pass count + floors a literal 0 to 1 (CS-2).
[DR-16] An EMPTY discovery pass leaves every stored drift counter untouched and warns (C58).
[DR-17] An EMPTY discovery pass does not create a setup_progress record (C58).
"""

from __future__ import annotations

import copy

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.setup.drift import (
    SETUP_STEP_IDS,
    compute_room_drift,
    get_adapter_setup_steps,
    get_discovery_cadence,
    is_step_completed,
    record_step_completed,
    update_drift_history,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


@pytest.fixture(autouse=True)
def _vacuum_is_added(manager):
    """Setup progress only exists for a vacuum that has been ADDED.

    Production reaches every one of these paths through
    ``workflow.add_vacuum_to_manager``, which calls ``ensure_vacuum_record`` BEFORE
    anything records a step — so ``data["vacuums"]`` always has the vacuum by then.
    These tests skipped that, recording setup progress for a vacuum the install had
    never added and Home Assistant did not have.

    That is not a state production can reach, and it is the state that let
    setup_progress["vacuum.iv"] — a truncated entity id — become a permanent record on
    a live install. The guard in ``drift._get_progress_record`` now refuses it, so the
    fixture supplies the step production would already have taken.
    """
    manager.data.setdefault("vacuums", {}).setdefault(_VAC, {"vacuum_entity_id": _VAC})
    return manager


# ---------------------------------------------------------------------------
# [DR-1] — [DR-2] is_step_completed
# ---------------------------------------------------------------------------

def test_is_step_completed_false_for_empty_progress(manager):
    """[DR-1] is_step_completed returns False when completed_steps is empty."""
    assert is_step_completed({}, "save_rooms") is False
    assert is_step_completed({"completed_steps": []}, "save_rooms") is False


def test_is_step_completed_true_after_recording(manager):
    """[DR-2] is_step_completed returns True after record_step_completed."""
    record_step_completed(manager, _VAC, "save_rooms")
    progress = manager.data["setup_progress"][_VAC]
    assert is_step_completed(progress, "save_rooms") is True


# ---------------------------------------------------------------------------
# [DR-3] — [DR-5] record_step_completed
# ---------------------------------------------------------------------------

def test_record_step_completed_adds_to_list(manager):
    """[DR-3] record_step_completed appends the step to completed_steps."""
    record_step_completed(manager, _VAC, "add_vacuum")
    completed = manager.data["setup_progress"][_VAC]["completed_steps"]
    assert "add_vacuum" in completed


def test_record_step_completed_is_idempotent(manager):
    """[DR-4] Calling record_step_completed twice does not duplicate the entry."""
    record_step_completed(manager, _VAC, "save_rooms")
    record_step_completed(manager, _VAC, "save_rooms")
    completed = manager.data["setup_progress"][_VAC]["completed_steps"]
    assert completed.count("save_rooms") == 1


def test_record_step_completed_ignores_unknown_step(manager):
    """[DR-5] record_step_completed silently ignores unrecognised step IDs."""
    record_step_completed(manager, _VAC, "nonexistent_step")
    completed = manager.data.get("setup_progress", {}).get(_VAC, {}).get("completed_steps", [])
    assert "nonexistent_step" not in completed


def test_record_step_completed_sets_last_advanced_at(manager):
    """[DR-3] record_step_completed stamps last_advanced_at."""
    record_step_completed(manager, _VAC, "import_active_map")
    assert manager.data["setup_progress"][_VAC]["last_advanced_at"] is not None


# ---------------------------------------------------------------------------
# [DR-6] — [DR-7] get_adapter_setup_steps
# ---------------------------------------------------------------------------

def test_get_adapter_setup_steps_returns_default_when_no_adapter(manager):
    """[DR-6] Returns default steps when no adapter config is registered."""
    steps = get_adapter_setup_steps(_VAC)
    assert isinstance(steps, list)
    assert len(steps) > 0
    assert all(s in SETUP_STEP_IDS for s in steps)


def test_get_adapter_setup_steps_returns_declared_steps(manager):
    """[DR-7] Returns adapter-declared steps when present."""
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        "source": "test",
        "entities": {},
        "setup": {"steps": ["add_vacuum", "import_active_map", "save_rooms"]},
    })
    steps = get_adapter_setup_steps(_VAC)
    assert steps == ["add_vacuum", "import_active_map", "save_rooms"]


def test_get_adapter_setup_steps_filters_unknown_ids(manager):
    """[DR-7] Unknown step IDs in the adapter declaration are filtered out."""
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        "source": "test",
        "entities": {},
        "setup": {"steps": ["add_vacuum", "foobar_step"]},
    })
    steps = get_adapter_setup_steps(_VAC)
    assert "foobar_step" not in steps
    assert "add_vacuum" in steps


def test_get_discovery_cadence_honors_low_values_and_floors_zero(manager):
    """[DR-15] CS-2: an explicit low confirmation-pass count is honored (not silently
    reverted to the default via `or`), and a literal 0 is clamped to the meaningful
    floor of 1 — never 0, which would make `missing_passes >= n_remove` a tautology
    (every configured room flagged removed). Absent → the documented defaults."""
    # explicit low value honored
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test", "entities": {},
        "discovery": {"removal_confirmation_passes": 2, "new_room_confirmation_passes": 2},
    })
    cad = get_discovery_cadence(_VAC)
    assert cad["removal_confirmation_passes"] == 2
    assert cad["new_room_confirmation_passes"] == 2

    # explicit 0 clamps to 1 (was silently 3 / 1 default before the fix)
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test", "entities": {},
        "discovery": {"removal_confirmation_passes": 0, "new_room_confirmation_passes": 0},
    })
    cad = get_discovery_cadence(_VAC)
    assert cad["removal_confirmation_passes"] == 1
    assert cad["new_room_confirmation_passes"] == 1

    # absent → documented defaults
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test", "entities": {}, "discovery": {},
    })
    cad = get_discovery_cadence(_VAC)
    assert cad["removal_confirmation_passes"] == 3
    assert cad["new_room_confirmation_passes"] == 1


# ---------------------------------------------------------------------------
# [DR-8] — [DR-9] compute_room_drift — in_sync baseline
# ---------------------------------------------------------------------------

def test_compute_room_drift_in_sync_no_configured_rooms(manager):
    """[DR-8] in_sync=True when no rooms are configured and no history exists."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = compute_room_drift(manager, _VAC)
    assert result["in_sync"] is True
    assert result["new_rooms"] == []
    assert result["removed_rooms"] == []


def test_compute_room_drift_no_discovered_ids_no_history_in_sync(manager):
    """[DR-9] Passing discovered_room_ids=None with no history → in_sync."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = compute_room_drift(manager, _VAC, discovered_room_ids=None)
    assert result["in_sync"] is True


# ---------------------------------------------------------------------------
# [DR-10] — [DR-11] update_drift_history
# ---------------------------------------------------------------------------

def test_update_drift_history_increments_missing_passes(manager):
    """[DR-10] update_drift_history increments missing_passes for absent configured rooms."""
    setup_map(manager, _VAC, _MAP, count=2)
    # Mark rooms as configured
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # C58: the miss is expressed as a READABLE pass that lists room 2 and not
    # room 1. This used to pass `set()`, which since the C58 guard means
    # "unreadable pass" and scores nothing — the assertion would then have been
    # measuring the guard, not the increment it claims to cover.
    update_drift_history(manager, _VAC, discovered_room_ids={2})
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert history["1"]["missing_passes"] == 1


def test_update_drift_history_resets_on_reappearance(manager):
    """[DR-11] missing_passes resets to 0 when a room reappears in discovery."""
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # Miss once — a readable pass that lists room 2 but not room 1 (C58: an
    # empty set is a read failure, not a sighting of nothing).
    update_drift_history(manager, _VAC, discovered_room_ids={2})
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert history["1"]["missing_passes"] == 1

    # Reappear
    update_drift_history(manager, _VAC, discovered_room_ids={1, 2})
    assert history["1"]["missing_passes"] == 0


# ---------------------------------------------------------------------------
# [DR-12] compute_room_drift — confirmed removal
# ---------------------------------------------------------------------------

def test_compute_room_drift_surfaces_removed_rooms_after_threshold(manager):
    """[DR-12] removed_rooms is non-empty after removal_confirmation_passes misses."""
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # Default threshold is 3 consecutive misses. Each pass is READABLE and lists
    # room 2 — C58: three empty sets would now be three unreadable passes and
    # would confirm nothing, which is the whole point of the guard.
    for _ in range(3):
        update_drift_history(manager, _VAC, discovered_room_ids={2})

    result = compute_room_drift(manager, _VAC, discovered_room_ids={2})
    removed_ids = {r["room_id"] for r in result["removed_rooms"]}
    assert removed_ids == {1}


# ---------------------------------------------------------------------------
# [DR-13] compute_room_drift — new room surfaces immediately
# ---------------------------------------------------------------------------

def test_compute_room_drift_surfaces_new_room_immediately(manager):
    """[DR-13] New discovered room surfaces in new_rooms on first sighting (n_new=1)."""
    setup_map(manager, _VAC, _MAP, count=1)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # Room 99 not in configured set
    update_drift_history(manager, _VAC, discovered_room_ids={1, 99})
    result = compute_room_drift(manager, _VAC, discovered_room_ids={1, 99})
    new_ids = {r["room_id"] for r in result["new_rooms"]}
    assert 99 in new_ids


# ---------------------------------------------------------------------------
# [DR-14] _list_configured_room_ids — the is_configured gate
# ---------------------------------------------------------------------------

def test_unconfigured_room_excluded_from_drift_tracking(manager):
    """[DR-14] A room sitting in a map bucket with is_configured=False is
    excluded from the configured set, so it is never drift-tracked.

    Guards the load-bearing configured-vs-discovered distinction in
    _list_configured_room_ids: with neither room in the pass, only the
    configured room accrues a missing pass; the unconfigured one (a freshly
    discovered room not yet through the save_rooms step) is not tracked at all.
    Every other drift test marks all rooms configured, so the exclusion branch
    is otherwise unexercised.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    # room_id 1 configured; room_id 2 left unconfigured.
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = room.get("room_id") == 1

    # A READABLE pass that lists neither room — id 99 is a room this map has
    # never had. C58: `set()` would be an unreadable pass and would score
    # nothing, so it can no longer express "both rooms missing".
    update_drift_history(manager, _VAC, discovered_room_ids={99})
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]

    assert history.get("1", {}).get("missing_passes") == 1
    assert "2" not in history


# ---------------------------------------------------------------------------
# [DR-16] — [DR-17] C58: an EMPTY discovery pass is a read failure
# ---------------------------------------------------------------------------

def test_empty_discovery_pass_leaves_drift_history_untouched(manager, caplog):
    """[DR-16] An empty discovered set changes NO stored counter, in either
    direction, and says so in the log (C58, ruling 2026-08-24).

    The failure this bites: `update_drift_history` had no empty-read guard, so a
    pass that read nothing — cold service-response cache after a restart, vacuum
    offline, cloud unreachable — struck EVERY configured room. Three of those and
    `compute_room_drift` reports the user's whole room list removed, from reads
    that never happened.

    The setup is the sequence that does the damage: two genuine misses on
    readable passes (so the counter is NON-ZERO), then the source goes dark.
    A non-zero starting counter is what makes this test bite in both directions —
    incrementing (3 == threshold, room confirmed removed) and resetting (0,
    discarding two real observations) are both wrong, and against a fresh
    zeroed counter a reset would be indistinguishable from correct behaviour.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # Two REAL misses: readable passes that list room 2 and not room 1.
    update_drift_history(manager, _VAC, discovered_room_ids={2})
    update_drift_history(manager, _VAC, discovered_room_ids={2})
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert history["1"]["missing_passes"] == 2

    before = copy.deepcopy(history)

    # Now the source goes unreadable. Five passes' worth — well past the
    # 3-pass removal threshold.
    with caplog.at_level("WARNING"):
        for _ in range(5):
            update_drift_history(manager, _VAC, discovered_room_ids=set())

    # Not just missing_passes: NOTHING in the stored history moved. last_seen_at
    # and first_missed_at are timestamps a later diagnosis reads, and an
    # unreadable pass is not an observation of any of them.
    assert history == before
    assert history["1"]["missing_passes"] == 2

    # And the room is not confirmed removed on the strength of those passes.
    result = compute_room_drift(manager, _VAC)
    assert result["removed_rooms"] == []

    # NOT A SILENT SKIP — the ruling's other half. The ledger's complaint was
    # that a day of failed reads left nothing suspicious in the log.
    warnings = [
        r for r in caplog.records
        if r.levelname == "WARNING" and "discovered NO rooms" in r.getMessage()
    ]
    assert len(warnings) == 5
    assert "UNREADABLE" in warnings[0].getMessage()
    # It names the vacuum and how many rooms were at stake, and does NOT assert
    # a cause — a cleared map and an unreachable cloud look identical here.
    assert _VAC in warnings[0].getMessage()
    assert "2 configured room(s)" in warnings[0].getMessage()


def test_empty_discovery_pass_does_not_create_a_setup_progress_record(manager):
    """[DR-17] An unreadable pass does not materialise setup-progress state.

    The guard returns before `_get_progress_record`, which `setdefault`s the
    record into existence. A pass that learned nothing should not leave a
    persisted record behind as its only trace — same principle as
    `save_managed_rooms` (asked-a-question, not made-a-change).
    """
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True
    assert _VAC not in manager.data.get("setup_progress", {})

    update_drift_history(manager, _VAC, discovered_room_ids=set())

    assert _VAC not in manager.data.get("setup_progress", {})
