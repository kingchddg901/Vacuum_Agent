"""Phase 3 integration tests — queue operations.

Coverage targets
----------------
[MQ-1]  get_queue_state returns empty default for an unknown map.
[MQ-2]  build_queue populates the queue from enabled rooms.
[MQ-3]  build_queue includes only enabled rooms in queue_room_ids.
[MQ-4]  build_queue updates runtime.queue_room_ids.
[MQ-5]  build_queue updates runtime.selected_map_id.
[MQ-6]  clear_queue resets to empty state.
[MQ-7]  get_queue_state after clear returns empty queue_room_ids.
[MQ-8]  clear_queue clears runtime.queue_room_ids.
[MQ-9]  build_queue after partial disable excludes disabled rooms.
"""

from __future__ import annotations

from tests._factories import VAC as _VAC, MAP as _MAP, set_room_field
from .conftest import setup_map


# ---------------------------------------------------------------------------
# [MQ-1] Default state
# ---------------------------------------------------------------------------

async def test_get_queue_state_unknown_map_returns_default(manager):
    """[MQ-1] Unknown map returns a default empty queue payload."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    state = manager.get_queue_state(vacuum_entity_id=_VAC, map_id="99")
    assert state["room_count"] == 0
    assert state["queue_room_ids"] == []
    assert state["queue_rooms"] == []


async def test_get_queue_state_vacuum_and_map_in_default(manager):
    """[MQ-1] Default payload echoes the supplied vacuum_entity_id and map_id."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    state = manager.get_queue_state(vacuum_entity_id=_VAC, map_id="5")
    assert state["vacuum_entity_id"] == _VAC
    assert state["map_id"] == "5"


# ---------------------------------------------------------------------------
# [MQ-2] — [MQ-5] build_queue
# ---------------------------------------------------------------------------

async def test_build_queue_populates_queue(manager):
    """[MQ-2] Queue is populated after build_queue."""
    setup_map(manager, _VAC, _MAP, count=3)
    result = manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    assert "queue_room_ids" in result


async def test_build_queue_all_enabled_rooms_included(manager):
    """[MQ-3] All enabled rooms appear in queue_room_ids."""
    setup_map(manager, _VAC, _MAP, count=3)
    result = manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    # All 3 rooms are enabled by default
    assert len(result["queue_room_ids"]) == 3


async def test_build_queue_updates_runtime_queue(manager):
    """[MQ-4] runtime.queue_room_ids is updated after build_queue."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    runtime = manager.ensure_runtime(_VAC)
    assert len(runtime.queue_room_ids) == 3


async def test_build_queue_updates_runtime_selected_map(manager):
    """[MQ-5] runtime.selected_map_id is set to the queued map."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    runtime = manager.ensure_runtime(_VAC)
    assert runtime.selected_map_id == _MAP


async def test_build_queue_persists_to_data(manager):
    """[MQ-2] Queue payload is written into data['queue']."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    assert _VAC in manager.data.get("queue", {})
    assert _MAP in manager.data["queue"][_VAC]


async def test_build_queue_excludes_disabled_rooms(manager):
    """[MQ-9] Disabled rooms are excluded from queue_room_ids."""
    setup_map(manager, _VAC, _MAP, count=3)
    # Disable room 2
    set_room_field(manager, 2, enabled=False)
    result = manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    assert 2 not in result["queue_room_ids"]
    assert len(result["queue_room_ids"]) == 2


async def test_build_queue_single_room(manager):
    """[MQ-3] Single room queue has exactly one ID."""
    setup_map(manager, _VAC, _MAP, count=1)
    result = manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(result["queue_room_ids"]) == 1


# ---------------------------------------------------------------------------
# [MQ-6] — [MQ-8] clear_queue
# ---------------------------------------------------------------------------

async def test_clear_queue_resets_queue_room_ids(manager):
    """[MQ-6] After clear, queue_room_ids is empty."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    manager.clear_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    state = manager.get_queue_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state["queue_room_ids"] == []


async def test_clear_queue_resets_room_count(manager):
    """[MQ-7] After clear, room_count is zero."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    manager.clear_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    state = manager.get_queue_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state["room_count"] == 0


async def test_clear_queue_clears_runtime_queue(manager):
    """[MQ-8] runtime.queue_room_ids is empty after clear_queue."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    manager.clear_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    runtime = manager.ensure_runtime(_VAC)
    assert runtime.queue_room_ids == []


async def test_clear_queue_returns_empty_state(manager):
    """[MQ-6] clear_queue return value has empty queue_room_ids."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    result = manager.clear_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["queue_room_ids"] == []
    assert result["room_count"] == 0
