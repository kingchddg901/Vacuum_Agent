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
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.setup.drift import (
    SETUP_STEP_IDS,
    compute_room_drift,
    get_adapter_setup_steps,
    is_step_completed,
    record_step_completed,
    update_drift_history,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


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

    update_drift_history(manager, _VAC, discovered_room_ids=set())
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert any(entry["missing_passes"] > 0 for entry in history.values())


def test_update_drift_history_resets_on_reappearance(manager):
    """[DR-11] missing_passes resets to 0 when a room reappears in discovery."""
    setup_map(manager, _VAC, _MAP, count=1)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # Miss once
    update_drift_history(manager, _VAC, discovered_room_ids=set())
    history = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert history["1"]["missing_passes"] == 1

    # Reappear
    update_drift_history(manager, _VAC, discovered_room_ids={1})
    assert history["1"]["missing_passes"] == 0


# ---------------------------------------------------------------------------
# [DR-12] compute_room_drift — confirmed removal
# ---------------------------------------------------------------------------

def test_compute_room_drift_surfaces_removed_rooms_after_threshold(manager):
    """[DR-12] removed_rooms is non-empty after removal_confirmation_passes misses."""
    setup_map(manager, _VAC, _MAP, count=1)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["is_configured"] = True

    # Default threshold is 3 consecutive misses.
    for _ in range(3):
        update_drift_history(manager, _VAC, discovered_room_ids=set())

    result = compute_room_drift(manager, _VAC, discovered_room_ids=set())
    assert len(result["removed_rooms"]) > 0


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
