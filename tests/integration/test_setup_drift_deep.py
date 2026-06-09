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
    """[DRD-3] reject_rooms records room IDs in setup_progress.rejected_rooms."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = reject_rooms(manager, _VAC, [1, 2])
    rejected = manager.data["setup_progress"][_VAC]["rejected_rooms"]
    assert 1 in rejected
    assert 2 in rejected
    assert result["rejected"] == [1, 2]


def test_reject_rooms_is_idempotent(manager):
    """[DRD-4] Calling reject_rooms twice with the same ID does not duplicate it."""
    setup_map(manager, _VAC, _MAP, count=1)
    reject_rooms(manager, _VAC, [1])
    reject_rooms(manager, _VAC, [1])
    rejected = manager.data["setup_progress"][_VAC]["rejected_rooms"]
    assert rejected.count(1) == 1


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
