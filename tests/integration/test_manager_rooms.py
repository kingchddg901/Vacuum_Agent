"""Phase 3 integration tests — room lifecycle (save, get, update_fields).

Coverage targets
----------------
[MR-1]  save_managed_rooms creates a map bucket and returns room_count.
[MR-2]  save_managed_rooms stores all discovered rooms by default.
[MR-3]  save_managed_rooms respects enabled_room_ids filter.
[MR-4]  save_managed_rooms returns summary with enabled/disabled counts.
[MR-5]  get_managed_rooms returns rooms for a saved map.
[MR-6]  get_managed_rooms returns empty for an unknown map.
[MR-7]  update_room_fields changes fan_speed.
[MR-8]  update_room_fields toggles enabled flag.
[MR-9]  update_room_fields returns error payload for unknown room.
[MR-10] update_room_fields changes clean_passes.
[MR-11] set_rooms_enabled_subset enables only the specified rooms.
[MR-12] set_rooms_enabled_subset disables all others.
"""

from __future__ import annotations

import pytest

from .conftest import make_rooms, seed_discovery, setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [MR-1] — [MR-4] save_managed_rooms
# ---------------------------------------------------------------------------

async def test_save_managed_rooms_creates_map_bucket(manager):
    """[MR-1] A map bucket exists in data after save."""
    setup_map(manager, _VAC, _MAP, count=2)
    assert _VAC in manager.data.get("maps", {})
    assert _MAP in manager.data["maps"][_VAC]


async def test_save_managed_rooms_room_count(manager):
    """[MR-1] Returned room_count matches the number of seeded rooms."""
    result = setup_map(manager, _VAC, _MAP, count=3)
    assert result["room_count"] == 3


async def test_save_managed_rooms_stores_all_rooms(manager):
    """[MR-2] All seeded rooms land in the map bucket by default."""
    setup_map(manager, _VAC, _MAP, count=3)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert set(rooms.keys()) == {"1", "2", "3"}


async def test_save_managed_rooms_filter_by_enabled_ids(manager):
    """[MR-3] Only rooms in enabled_room_ids are stored."""
    result = setup_map(manager, _VAC, _MAP, count=4, enabled_room_ids=[1, 3])
    assert result["room_count"] == 2
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert set(rooms.keys()) == {"1", "3"}


async def test_save_managed_rooms_summary_counts(manager):
    """[MR-4] Summary counts all rooms as enabled (enabled=True by default)."""
    result = setup_map(manager, _VAC, _MAP, count=3)
    assert result["summary"]["enabled_count"] == 3
    assert result["summary"]["disabled_count"] == 0


async def test_save_managed_rooms_sets_is_configured(manager):
    """[MR-2] All saved rooms have is_configured=True."""
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        assert room["is_configured"] is True


async def test_save_managed_rooms_preserves_existing_settings(manager):
    """[MR-2] Existing room settings survive a re-save."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["fan_speed"] = "quiet"

    # Re-seed and re-save with the same rooms
    seed_discovery(manager, _VAC, _MAP, make_rooms(_MAP, 2))
    manager.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["fan_speed"] == "quiet"


# ---------------------------------------------------------------------------
# [MR-5] — [MR-6] get_managed_rooms
# ---------------------------------------------------------------------------

async def test_get_managed_rooms_returns_rooms(manager):
    """[MR-5] get_managed_rooms returns the saved rooms."""
    setup_map(manager, _VAC, _MAP, count=3)
    result = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["room_count"] == 3
    assert "1" in result["rooms"]
    assert "2" in result["rooms"]
    assert "3" in result["rooms"]


async def test_get_managed_rooms_empty_for_unknown_map(manager):
    """[MR-6] Returns zero rooms for a map that hasn't been saved."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id="99")
    assert result["room_count"] == 0
    assert result["rooms"] == {}


async def test_get_managed_rooms_room_names(manager):
    """[MR-5] Room names from the discovery payload appear in the result."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["rooms"]["1"]["name"] == "Room 1"
    assert result["rooms"]["2"]["name"] == "Room 2"


# ---------------------------------------------------------------------------
# [MR-7] — [MR-10] update_room_fields
# ---------------------------------------------------------------------------

async def test_update_room_fields_fan_speed(manager):
    """[MR-7] fan_speed is updated in the stored room config."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, fan_speed="quiet"
    )
    assert result.get("ok") is not False
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["fan_speed"] == "quiet"


async def test_update_room_fields_toggle_enabled(manager):
    """[MR-8] enabled can be toggled to False."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, enabled=False
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["enabled"] is False


async def test_update_room_fields_unknown_room_returns_error(manager):
    """[MR-9] Returns error payload when the room_id does not exist."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=99, fan_speed="max"
    )
    assert result["ok"] is False
    assert result["error"] == "room_not_found"


async def test_update_room_fields_clean_passes(manager):
    """[MR-10] clean_passes is updated in the stored room config."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=2, clean_passes=2
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["2"]["clean_passes"] == 2


async def test_update_room_fields_clean_mode(manager):
    """[MR-7] clean_mode is updated in the stored room config."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, clean_mode="mop"
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["clean_mode"] == "mop"


async def test_update_room_fields_invalid_access_graph_rejected(manager):
    """[MR-10b] a structurally-illegal access-graph change (a second dock room)
    is rejected with an error payload AND the room is rolled back, not saved."""
    setup_map(manager, _VAC, _MAP, count=2)
    # Room 1 becomes the dock room — a single dock room is valid.
    ok = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, is_dock_room=True
    )
    assert ok.get("ok") is not False

    # Making room 2 a second dock room is structurally illegal.
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=2, is_dock_room=True
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_access_graph"
    assert result["updated"] is False
    assert isinstance(result["issues"], list) and result["issues"]
    # rollback: room 2 was NOT persisted as a dock room
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["2"].get("is_dock_room") is not True
    # room 1 (the legitimate dock room) is untouched
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["is_dock_room"] is True


# ---------------------------------------------------------------------------
# [MR-11] — [MR-12] set_rooms_enabled_subset
# ---------------------------------------------------------------------------

async def test_set_rooms_enabled_subset_enables_specified(manager):
    """[MR-11] Only the specified room IDs are enabled."""
    setup_map(manager, _VAC, _MAP, count=4)
    manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[1, 3]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["1"]["enabled"] is True
    assert rooms["3"]["enabled"] is True


async def test_set_rooms_enabled_subset_disables_others(manager):
    """[MR-12] Rooms not in the subset are disabled."""
    setup_map(manager, _VAC, _MAP, count=4)
    manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[1, 3]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["2"]["enabled"] is False
    assert rooms["4"]["enabled"] is False


async def test_set_rooms_enabled_subset_returns_counts(manager):
    """[MR-11] Return value has correct enabled_count and total_count."""
    setup_map(manager, _VAC, _MAP, count=4)
    result = manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[2, 4]
    )
    assert result["enabled_count"] == 2
    assert result["total_count"] == 4


async def test_set_rooms_enabled_subset_string_ids(manager):
    """[MR-11] String room IDs are accepted and normalized correctly."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=["1", "3"]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["1"]["enabled"] is True
    assert rooms["2"]["enabled"] is False
