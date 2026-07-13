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
[ZP-1] add_queue_zone inserts a zone step between rooms.
[ZP-2] a zone-only queue is still "stepped" (has_breaks True).
[ZP-3] add_queue_zone needs >= 2 rooms.
[ZP-4] set_queue_breaks round-trips a zone entry (reorder preserves zone_ids).
[ZP-5] normalize dedupes/validates zone_ids; empty -> dropped.
[SP-1/2] save_run_profile captures the stepped plan; flat queue -> single group.
[ZT-1] a zone can TRAIL (after_index == room_count -> cleaned after the last room).
[ZT-2] set_queue_breaks: zone trails, charge/wait clamp to interior.
[ZT-3] a rooms+zone queue (no charge) takes the stepped plan (gate fix; zone not dropped).
[ZT-4] the launch reset drains breaks too (a trailing zone must not survive as an orphan chip).
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


async def test_add_queue_zone_inserts_between_rooms(manager):
    """[ZP-1] A zone step slots between rooms like a break, but is a clean action."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.add_queue_zone(
        vacuum_entity_id=_VAC, map_id=_MAP, after_index=2, zone_ids=["z_kennel", "z_entry"]
    )
    assert res["added"] is True
    assert [s["type"] for s in res["steps"]] == ["room_group", "zone", "room_group"]
    zone = next(s for s in res["steps"] if s["type"] == "zone")
    assert zone["zone_ids"] == ["z_kennel", "z_entry"]
    assert len(res["steps"][0]["rooms"]) == 2


async def test_zone_only_queue_is_stepped(manager):
    """[ZP-2] A zone (no charge/wait) still marks the queue non-flat."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.add_queue_zone(
        vacuum_entity_id=_VAC, map_id=_MAP, after_index=1, zone_ids=["z_kennel"]
    )
    assert res["has_breaks"] is True


async def test_add_queue_zone_needs_two_rooms(manager):
    """[ZP-3] The inserted-step slot model needs a room on each side."""
    setup_map(manager, _VAC, _MAP, count=1)
    res = manager.add_queue_zone(
        vacuum_entity_id=_VAC, map_id=_MAP, after_index=1, zone_ids=["z_kennel"]
    )
    assert res["added"] is False
    assert res["reason"] == "needs_two_rooms"


async def test_set_queue_breaks_round_trips_zone(manager):
    """[ZP-4] Reorder (set_queue_breaks) preserves a zone entry's zone_ids + position."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[
            {"after_index": 1, "break_type": "zone", "zone_ids": ["z_kennel", "z_entry"]},
            {"after_index": 2, "break_type": "charge_wait", "target_battery_percent": 80},
        ],
    )
    assert res["set"] is True
    assert [s["type"] for s in res["steps"]] == [
        "room_group", "zone", "room_group", "charge_wait", "room_group",
    ]
    zone = next(s for s in res["steps"] if s["type"] == "zone")
    assert zone["zone_ids"] == ["z_kennel", "z_entry"]


async def test_normalize_zone_dedupes_and_drops_empty(manager):
    """[ZP-5] zone_ids are de-duplicated + coerced to non-empty strings; empty -> dropped."""
    norm = manager.profiles.normalize_run_profile_steps
    assert norm([{"type": "zone", "zone_ids": ["a", "a", " b ", "", "  "]}]) == [
        {"type": "zone", "zone_ids": ["a", "b"]}
    ]
    assert norm([{"type": "zone", "zone_ids": []}]) == []
    assert norm([{"type": "zone", "zone_ids": "not-a-list"}]) == []


async def test_save_run_profile_captures_stepped_plan(manager):
    """[SP-1] Saving a profile from a stepped queue captures the WHOLE plan (rooms + break),
    not a flattened room clean — so the composed one-off run becomes a re-runnable profile."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="charge_wait",
        after_index=2, target_battery_percent=90,
    )
    res = manager.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Nightly")
    assert res["saved"] is True
    steps = res["profile"].get("steps")
    assert [s["type"] for s in steps] == ["room_group", "charge_wait", "room_group"]
    assert next(s for s in steps if s["type"] == "charge_wait")["target_battery_percent"] == 90


async def test_save_run_profile_flat_queue_single_group(manager):
    """[SP-2] A flat queue (no breaks) saves as a single room_group — no phantom break/zone;
    the enriched profile's steps back-fill to exactly one clean group."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Everywhere")
    assert res["saved"] is True
    assert [s["type"] for s in res["profile"]["steps"]] == ["room_group"]


def _seed_saved_zone(manager, zid="z1"):
    mb = manager.data["maps"][_VAC][_MAP]
    mb.setdefault("saved_zones", {})[zid] = {
        "id": zid, "name": "Kennel",
        "geometry": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
    }


async def test_zone_can_trail(manager):
    """[ZT-1] a zone at after_index == room_count cleans AFTER the last room (rooms then zone)."""
    setup_map(manager, _VAC, _MAP, count=3)
    res = manager.add_queue_zone(
        vacuum_entity_id=_VAC, map_id=_MAP, after_index=3, zone_ids=["z1"]
    )
    assert res["added"] is True
    assert [s["type"] for s in res["steps"]] == ["room_group", "zone"]
    assert len(res["steps"][0]["rooms"]) == 3


async def test_set_queue_breaks_zone_trails_charge_interior(manager):
    """[ZT-2] set_queue_breaks: a zone may trail (room_count); a charge clamps to interior."""
    setup_map(manager, _VAC, _MAP, count=2)
    res = manager.set_queue_breaks(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        breaks=[
            {"after_index": 2, "break_type": "zone", "zone_ids": ["z1"]},
            {"after_index": 2, "break_type": "charge_wait", "target_battery_percent": 80},
        ],
    )
    assert res["set"] is True
    assert [s["type"] for s in res["steps"]] == [
        "room_group", "charge_wait", "room_group", "zone",
    ]


async def test_rooms_plus_zone_takes_stepped_plan(manager):
    """[ZT-3] A rooms+zone queue with NO charge/wait still takes the STEPPED plan and produces
    a zone phase — before the gate fix it fell to a flat clean and silently dropped the zone."""
    setup_map(manager, _VAC, _MAP, count=2)
    _seed_saved_zone(manager)
    manager.add_queue_zone(vacuum_entity_id=_VAC, map_id=_MAP, after_index=2, zone_ids=["z1"])
    plan = manager._build_effective_start_plan(vacuum_entity_id=_VAC, map_id=_MAP)
    types = [p.get("phase_type") for p in plan["phases"]]
    assert "zone" in types


async def test_launch_reset_drains_breaks_with_rooms(manager):
    """[ZT-4] The launch reset (_clear_room_selections_after_start) drops the queue breaks
    alongside disabling rooms — otherwise a trailing zone/wait outlives the run's room drain
    and re-renders as an orphan chip in the composer once the run ends."""
    setup_map(manager, _VAC, _MAP, count=2)
    _seed_saved_zone(manager)
    manager.add_queue_zone(vacuum_entity_id=_VAC, map_id=_MAP, after_index=2, zone_ids=["z1"])
    # Pre-condition: rooms enabled + a zone break present.
    mb = manager.data["maps"][_VAC][_MAP]
    assert any(r.get("enabled") for r in mb["rooms"].values())
    assert mb.get("queue_breaks")

    manager._clear_room_selections_after_start(vacuum_entity_id=_VAC, map_id=_MAP)

    mb = manager.data["maps"][_VAC][_MAP]
    assert not any(r.get("enabled") for r in mb["rooms"].values())  # rooms drained
    assert mb.get("queue_breaks") == []                            # AND breaks drained
    res = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)
    assert res["has_breaks"] is False
