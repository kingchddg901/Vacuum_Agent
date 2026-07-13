"""P1 integration tests — live-queue break steps (ad-hoc stepped composition).

[QB-1] get_queue_steps on a flat queue = one room_group, no breaks.
[QB-2] add_queue_break(charge_wait) splits the queue into two groups around it.
[QB-3] remove_queue_break drops back to flat.
[QB-4] clear_queue_breaks drops back to flat.
[QB-5] add_queue_break needs >= 2 rooms.
[QB-6] add_queue_break clamps after_index to an interior slot.
[QB-7] wait_minutes is clamped via the shared step normalizer.
[QB-8] a queue break drives the STEPPED dispatch path.
[QB-9] set_queue_breaks replaces the store wholesale (old breaks gone).
[QB-10] set_queue_breaks reorders — two breaks swap position by after_index.
[QB-11] set_queue_breaks retargets a break's param in place.
[QB-12] set_queue_breaks needs >= 2 rooms (else clears + reports).
[QB-13] set_queue_breaks clamps after_index and drops invalid entries.
[QB-14] get_queue_steps exposes the raw ordered breaks list.
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


async def test_set_queue_breaks_replaces_wholesale(manager):
    """[QB-9] set_queue_breaks replaces the store — a prior break is gone, the new one applies."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=1, wait_minutes=20
    )
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[{"after_index": 2, "break_type": "charge_wait", "target_battery_percent": 75}],
    )
    assert res["set"] is True
    assert [s["type"] for s in res["steps"]] == ["room_group", "charge_wait", "room_group"]
    charge = next(s for s in res["steps"] if s["type"] == "charge_wait")
    assert charge["target_battery_percent"] == 75
    assert len(res["steps"][0]["rooms"]) == 2  # break now after 2 rooms, not 1


async def test_set_queue_breaks_reorders(manager):
    """[QB-10] Two breaks swap sequence position purely by their after_index."""
    setup_map(manager, _VAC, _MAP, count=4)
    # Original: charge after 1 room, wait after 3 rooms.
    manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[
            {"after_index": 1, "break_type": "charge_wait", "target_battery_percent": 90},
            {"after_index": 3, "break_type": "wait", "wait_minutes": 20},
        ],
    )
    before = [s["type"] for s in manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)["steps"]]
    assert before == ["room_group", "charge_wait", "room_group", "wait", "room_group"]

    # Swap: wait now early (after 1), charge late (after 3).
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[
            {"after_index": 3, "break_type": "charge_wait", "target_battery_percent": 90},
            {"after_index": 1, "break_type": "wait", "wait_minutes": 20},
        ],
    )
    after = [s["type"] for s in res["steps"]]
    assert after == ["room_group", "wait", "room_group", "charge_wait", "room_group"]


async def test_set_queue_breaks_retargets(manager):
    """[QB-11] Editing a break's value = resend the list with the new param."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        break_type="charge_wait",
        after_index=1,
        target_battery_percent=90,
    )
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[{"after_index": 1, "break_type": "charge_wait", "target_battery_percent": 50}],
    )
    charge = next(s for s in res["steps"] if s["type"] == "charge_wait")
    assert charge["target_battery_percent"] == 50


async def test_set_queue_breaks_needs_two_rooms(manager):
    """[QB-12] With < 2 rooms breaks are meaningless: cleared + reported, not applied."""
    setup_map(manager, _VAC, _MAP, count=1)
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[{"after_index": 1, "break_type": "wait", "wait_minutes": 10}],
    )
    assert res["set"] is False
    assert res["reason"] == "needs_two_rooms"
    assert res["has_breaks"] is False


async def test_set_queue_breaks_clamps_and_drops(manager):
    """[QB-13] after_index is clamped to an interior slot; junk entries are dropped."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[
            {"after_index": 99, "break_type": "wait", "wait_minutes": 10},
            {"after_index": 1, "break_type": "bogus"},  # unknown type -> dropped
            "not-a-dict",  # non-dict -> skipped
        ],
    )
    assert res["set"] is True
    assert [s["type"] for s in res["steps"]] == ["room_group", "wait", "room_group"]
    assert len(res["steps"][0]["rooms"]) == 2  # 99 clamped to interior (after 2nd room)


async def test_get_queue_steps_exposes_raw_breaks(manager):
    """[QB-14] The snapshot carries the raw ordered breaks so the card can rebuild the row."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        break_type="charge_wait",
        after_index=1,
        target_battery_percent=90,
    )
    res = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(res["breaks"], list) and len(res["breaks"]) == 1
    entry = res["breaks"][0]
    assert entry["after_index"] == 1
    assert entry["step"]["type"] == "charge_wait"
    assert entry["step"]["target_battery_percent"] == 90
