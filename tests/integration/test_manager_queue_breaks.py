"""P1 integration tests — live-queue break steps (ad-hoc stepped composition).

[QB-1] get_queue_steps on a flat queue = one room_group, no breaks.
[QB-2] add_queue_break(charge_wait) splits the queue into two groups around it.
[QB-3] remove_queue_break drops back to flat.
[QB-4] clear_queue_breaks drops back to flat.
[QB-5] add_queue_break needs >= 2 rooms.
[QB-6] add_queue_break clamps after_index to an interior slot.
[QB-7] wait_minutes is clamped via the shared step normalizer.
"""

from __future__ import annotations

from tests._factories import VAC as _VAC, MAP as _MAP
from .conftest import setup_map


async def test_flat_queue_one_group(manager):
    """[QB-1] No breaks -> a single room_group, has_breaks False."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)
    assert res["has_breaks"] is False
    assert [s["type"] for s in res["steps"]] == ["room_group"]
    assert len(res["steps"][0]["rooms"]) == 3


async def test_add_charge_break_splits(manager):
    """[QB-2] A charge break after room #2 -> group(2) + charge_wait + group(1)."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.add_queue_break(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        break_type="charge_wait",
        after_index=2,
        target_battery_percent=90,
    )
    assert res["added"] is True
    assert res["has_breaks"] is True
    assert [s["type"] for s in res["steps"]] == ["room_group", "charge_wait", "room_group"]
    assert len(res["steps"][0]["rooms"]) == 2
    assert len(res["steps"][2]["rooms"]) == 1
    assert res["steps"][1]["target_battery_percent"] == 90


async def test_remove_break_back_to_flat(manager):
    """[QB-3] Removing the only break returns a flat queue."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=1, wait_minutes=20
    )
    res = manager.remove_queue_break(vacuum_entity_id=_VAC, map_id=_MAP, index=0)
    assert res["removed"] is True
    assert res["has_breaks"] is False
    assert [s["type"] for s in res["steps"]] == ["room_group"]


async def test_clear_breaks_back_to_flat(manager):
    """[QB-4] clear_queue_breaks empties all breaks."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=1, wait_minutes=20
    )
    manager.add_queue_break(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        break_type="charge_wait",
        after_index=2,
        target_battery_percent=80,
    )
    res = manager.clear_queue_breaks(vacuum_entity_id=_VAC, map_id=_MAP)
    assert res["has_breaks"] is False
    assert [s["type"] for s in res["steps"]] == ["room_group"]


async def test_add_break_needs_two_rooms(manager):
    """[QB-5] A break needs a room on each side."""
    setup_map(manager, _VAC, _MAP, count=1)
    res = manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=1, wait_minutes=10
    )
    assert res["added"] is False
    assert res["reason"] == "needs_two_rooms"


async def test_add_break_clamps_after_index(manager):
    """[QB-6] after_index is clamped to an interior slot [1, room_count-1]."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=99, wait_minutes=10
    )
    assert res["added"] is True
    assert [s["type"] for s in res["steps"]] == ["room_group", "wait", "room_group"]
    assert len(res["steps"][0]["rooms"]) == 2  # clamped to after the 2nd (last interior) room


async def test_wait_minutes_clamped(manager):
    """[QB-7] wait_minutes is clamped to 1..1440 via the shared step normalizer."""
    setup_map(manager, _VAC, _MAP, count=2)
    res = manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=1, wait_minutes=99999
    )
    assert res["added"] is True
    wait_step = next(s for s in res["steps"] if s["type"] == "wait")
    assert wait_step["wait_minutes"] == 1440


async def test_queue_break_makes_start_plan_stepped(manager):
    """[QB-8] P2: a queue break drives the STEPPED dispatch path — the effective
    start plan gains a charge_wait phase (flat before, stepped after)."""
    setup_map(manager, _VAC, _MAP, count=3)

    plan_flat = manager._build_effective_start_plan(vacuum_entity_id=_VAC, map_id=_MAP)
    types_flat = [p.get("phase_type") for p in plan_flat["phases"]]
    assert not any(t in ("charge_wait", "wait") for t in types_flat)

    manager.add_queue_break(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        break_type="charge_wait",
        after_index=2,
        target_battery_percent=90,
    )
    plan_stepped = manager._build_effective_start_plan(vacuum_entity_id=_VAC, map_id=_MAP)
    types = [p.get("phase_type") for p in plan_stepped["phases"]]
    assert "charge_wait" in types
    assert len(plan_stepped["phases"]) >= 3  # clean -> charge -> clean
