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
[QB-15] a break STRANDED at the trailing edge by a later room disable is self-healed on
        READ, and the stored break survives so re-enabling the room restores it.
[QB-16] breaks left with NOTHING to bracket (every room disabled) heal to an empty plan
        -- the all-breaks case, where the two heal arms are not separable.
[ZP-1] add_queue_zone inserts a zone step between rooms.
[ZP-2] a zone-only queue is still "stepped" (has_breaks True).
[ZP-3] add_queue_zone needs >= 2 rooms.
[ZP-4] set_queue_breaks round-trips a zone entry (reorder preserves zone_ids).
[ZP-5] normalize dedupes/validates zone_ids; empty -> dropped.
[SVP-1] save_run_profile from a stepped queue captures the WHOLE plan (rooms + break), not a flattened clean.
[SVP-2] a flat queue (no breaks) saves as a single room_group — no phantom break/zone.
[ZT-1] a zone can TRAIL (after_index == room_count -> cleaned after the last room).
[ZT-2] set_queue_breaks: zone trails, charge/wait clamp to interior.
[ZT-3] a rooms+zone queue (no charge) takes the stepped plan (gate fix; zone not dropped).
[ZT-4] the launch reset drains breaks too (a trailing zone must not survive as an orphan chip).
[ZE-1] a queued zone with no samples estimates off area x per-mode rate (rooms' mop mode -> mop rate).
[ZE-2] a learned zone average wins over the area fallback for the run's mode.
[ZE-3] a rooms-only queue reports no zone contribution (has_zone False).
[ZE-4] _zone_estimate_mode: zone-only prefers the zone's learned mode; rooms present -> rooms' mode.
[ZE-5] a multi-zone step estimates as the SUM of its zones.
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


async def test_get_queue_steps_names_its_rooms(manager):
    """live:QUEUE-READ-1. get_queue_steps could describe the queue's STRUCTURE but its
    rooms were `{"room_id": N}` and nothing else, so rendering the live plan needed a
    second service (get_queue_state) that in turn could not see the breaks at all — two
    services each half-answering "what is queued". build_queue_from_managed_rooms
    already resolves this metadata; it was being discarded."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait", after_index=1, wait_minutes=2
    )
    res = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)
    assert [s["type"] for s in res["steps"]] == ["room_group", "wait", "room_group"]

    rooms = [r for s in res["steps"] if s["type"] == "room_group" for r in s["rooms"]]
    assert len(rooms) == 3
    for room in rooms:
        # room_id stays first and unchanged — existing consumers are unaffected.
        assert isinstance(room["room_id"], int) and room["room_id"] > 0
        assert set(room) == {"room_id", "name", "slug", "order", "profile_name"}
        assert room["name"]
        # slug/profile_name are passed through verbatim from the managed room — a room
        # that has never stored one reads None rather than a fabricated value, so the
        # contract is "the key is always present", not "it is always populated".
    # order is the QUEUE order, so the plan can be rendered without a second lookup
    assert [r["order"] for r in rooms] == sorted(r["order"] for r in rooms)


async def test_queue_step_room_ids_still_match_the_id_only_sibling(manager):
    """The id-only helper is now DERIVED from the metadata one, so the two cannot
    disagree about order — which is the failure mode that made two backings diverge
    in the first place."""
    setup_map(manager, _VAC, _MAP, count=3)
    bucket = manager.data["maps"][_VAC][_MAP]
    assert manager._enabled_room_ids_in_order(bucket, _VAC, _MAP) == [
        r["room_id"] for r in manager._enabled_rooms_in_order(bucket, _VAC, _MAP)
    ]


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
    """[SVP-1] Saving a profile from a stepped queue captures the WHOLE plan (rooms + break),
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
    """[SVP-2] A flat queue (no breaks) saves as a single room_group — no phantom break/zone;
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


async def test_estimate_queued_zone_area_fallback(manager):
    """[ZE-1] a queued zone with no learned samples estimates off area x per-mode rate; the
    run's mop mode (from rooms) picks the mop rate."""
    setup_map(manager, _VAC, _MAP, count=2)
    _seed_saved_zone(manager)
    manager.data["maps"][_VAC][_MAP]["saved_zones"]["z1"]["area_m2"] = 0.5
    manager.add_queue_zone(vacuum_entity_id=_VAC, map_id=_MAP, after_index=2, zone_ids=["z1"])
    est = manager._estimate_queued_zones(
        vacuum_entity_id=_VAC, map_id=_MAP, resolved_rooms=[{"clean_mode": "vacuum_mop"}]
    )
    assert est["has_zone"] is True and len(est["zones"]) == 1
    z = est["zones"][0]
    assert z["clean_mode"] == "mop" and z["source"] == "area_fallback"
    assert z["seconds"] == 120 and est["seconds"] == 120  # 0.5 m² * 240 s/m²


async def test_estimate_queued_zone_prefers_learned(manager):
    """[ZE-2] once a zone has a learned sample for the run's mode, the average wins over area."""
    setup_map(manager, _VAC, _MAP, count=2)
    _seed_saved_zone(manager)
    mb = manager.data["maps"][_VAC][_MAP]
    mb["saved_zones"]["z1"]["area_m2"] = 0.5
    mb["learned_zones"] = {"z1": {"mop": {"avg_wall_seconds": 285, "sample_count": 2}}}
    manager.add_queue_zone(vacuum_entity_id=_VAC, map_id=_MAP, after_index=2, zone_ids=["z1"])
    est = manager._estimate_queued_zones(
        vacuum_entity_id=_VAC, map_id=_MAP, resolved_rooms=[{"clean_mode": "vacuum_mop"}]
    )
    z = est["zones"][0]
    assert z["source"] == "learned" and z["seconds"] == 285 and z["sample_count"] == 2


async def test_estimate_no_zone_has_none(manager):
    """[ZE-3] a rooms-only queue reports no zone contribution."""
    setup_map(manager, _VAC, _MAP, count=2)
    est = manager._estimate_queued_zones(
        vacuum_entity_id=_VAC, map_id=_MAP, resolved_rooms=[{"clean_mode": "vacuum"}]
    )
    assert est == {"has_zone": False, "seconds": 0, "minutes": 0.0, "zones": []}


def test_zone_estimate_mode_selection(manager):
    """[ZE-4] zone-only estimates against the zone's own learned mode; rooms present -> rooms'."""
    learned = {"z1": {"mop": {"avg_wall_seconds": 200, "sample_count": 1}}}
    assert manager._zone_estimate_mode([], learned, "z1", False) == "mop"
    assert manager._zone_estimate_mode([], {}, "z9", False) == "vacuum"            # no data
    assert manager._zone_estimate_mode([{"clean_mode": "x"}], learned, "z1", True) == "mop"
    assert manager._zone_estimate_mode([{"clean_mode": "x"}], learned, "z1", False) == "vacuum"


async def test_estimate_multi_zone_step_sums(manager):
    """[ZE-5] a multi-zone step estimates as the SUM of its zones (learning skips it, but the
    estimate still adds them up)."""
    setup_map(manager, _VAC, _MAP, count=2)
    mb = manager.data["maps"][_VAC][_MAP]
    _seed_saved_zone(manager, "z1")
    _seed_saved_zone(manager, "z2")
    mb["saved_zones"]["z1"]["area_m2"] = 0.5
    mb["saved_zones"]["z2"]["area_m2"] = 1.0
    manager.add_queue_zone(
        vacuum_entity_id=_VAC, map_id=_MAP, after_index=2, zone_ids=["z1", "z2"]
    )
    est = manager._estimate_queued_zones(
        vacuum_entity_id=_VAC, map_id=_MAP, resolved_rooms=[{"clean_mode": "vacuum"}]
    )
    assert len(est["zones"]) == 2 and est["seconds"] == 90  # 0.5*60=30 + 1.0*60=60


# ---------------------------------------------------------------------------
# [QB-15] / [QB-16] — get_queue_steps' self-heal, from the 2026-11-07 coverage triage.
#
# `profiles.normalize_run_profile_steps` is NOT total: its own docstring says so, and
# `_reject_unbracketed_break` raises ServiceValidationError when the first or last of
# 2+ steps is a charge_wait or wait. That raise comes out of a READ path, so without
# the catch in get_queue_steps the symptom is the queue refusing to load at all --
# the same shape the normaliser's docstring describes as "saved run profile will not
# load".
#
# Both WRITE paths clamp after_index to an interior slot ([QB-6], [ZT-2]), so this is
# only reachable for state that became invalid AFTER it was written. The comment on
# the except names the cause: "a room disabled AFTER a break was placed can strand it
# at the edge." Both tests below take that route through the public API rather than
# hand-planting storage.
#
# ⚠ TWO CORRECTIONS, both measured rather than reasoned.
#
# 1. The triage proposed persisting `after_index: 0` to reach the leading arm. That
#    input cannot: `_map_queue_breaks` filters on `after >= 1`, so a 0 is dropped
#    before the steps loop ever sees it.
#
# 2. THE LEADING while-loop IS UNREACHABLE. `steps[0]` can only be a break when there
#    are NO rooms at all -- a break with `after_index >= 1` always emits after at
#    least one room_group -- and in that case EVERY entry is a break, so the trailing
#    loop would drain that same list from the right. So the leading loop IS executed
#    by [QB-16] -- it runs first and does the popping, and coverage records it -- but
#    it cannot be ablation-proven, because deleting it leaves the test green:
#    measured, A3 red set NONE. Deleting the TRAILING loop reddens both tests.
#
#    Whether to delete the leading loop is a behaviour decision, not a test one --
#    the same call [SWT-2] records for the tick's `if not active_job` guard. Left in
#    place and documented. Note it is not pure dead weight even so: it is what makes
#    the dropped breaks log as "leading" rather than "trailing", which is the only
#    observable difference between the two arms on this input.
# ---------------------------------------------------------------------------


def _rooms(manager, map_id=_MAP):
    return manager.data["maps"][_VAC][map_id]["rooms"]


def _stored_breaks(manager, map_id=_MAP):
    return manager.data["maps"][_VAC][map_id].get("queue_breaks") or []


async def test_a_trailing_stranded_break_is_healed_on_read(manager):
    """[QB-15] disabling a room must not make the queue unreadable.

    Two rooms with an interior wait is [room_1] wait [room_2]. Disable room 1 and the
    wait has nothing left in front of it, so the derived steps come out as
    [room_group, wait] -- a trailing break, which the normaliser refuses. Without the
    self-heal the user's queue simply fails to load, and the only way back is to
    guess that a disabled room is the cause.

    The second half is the part the except's comment promises and is worth pinning:
    the heal is NON-DESTRUCTIVE. The stored break is untouched, so re-enabling the
    room brings it back where it was.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    added = manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait",
        after_index=1, wait_minutes=5,
    )
    assert added["added"] is True
    assert [s["type"] for s in added["steps"]] == ["room_group", "wait", "room_group"]

    # The user disables the FIRST room, which is what strands the break.
    _rooms(manager)["1"]["enabled"] = False

    res = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)

    assert [s["type"] for s in res["steps"]] == ["room_group"], (
        f"the stranded trailing break must be dropped from the READ; got {res['steps']!r}"
    )
    assert len(res["steps"][0]["rooms"]) == 1
    # NON-DESTRUCTIVE: storage still holds it...
    assert _stored_breaks(manager), "the heal must not delete the stored break"
    # ...so re-enabling the room restores the plan exactly.
    _rooms(manager)["1"]["enabled"] = True
    back = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)
    assert [s["type"] for s in back["steps"]] == ["room_group", "wait", "room_group"], (
        "re-enabling the room must restore the break the read dropped"
    )


async def test_leading_stranded_breaks_are_healed_on_read(manager):
    """[QB-16] every room disabled leaves the breaks with nothing to bracket.

    With no enabled rooms the room loop never runs and the drain emits the breaks on
    their own, so the derived steps are [wait, wait]. Two breaks, not one: the
    normaliser cannot trip on a single-entry list, as its docstring states.

    A reachable state, not a contrived one -- a user disabling every room on a map
    while a stepped queue is stored gets here -- and without the heal the queue read
    raises instead of reporting an empty plan.

    THE LEADING ARM IS COVERED BUT NOT PROVEN, which the ablation established rather
    than my reading it off the code: the leading loop does run here and does the
    popping, but the trailing loop would drain the identical all-breaks list from the
    right, so deleting the leading loop leaves this test GREEN. No input separates
    them -- see the note above. This test's own bite is the catch itself and the
    trailing drain; both are measured.
    """
    setup_map(manager, _VAC, _MAP, count=3)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait",
        after_index=1, wait_minutes=5,
    )
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="wait",
        after_index=2, wait_minutes=7,
    )
    assert len(_stored_breaks(manager)) == 2

    for rid in ("1", "2", "3"):
        _rooms(manager)[rid]["enabled"] = False

    res = manager.get_queue_steps(vacuum_entity_id=_VAC, map_id=_MAP)

    assert res["steps"] == [], (
        f"breaks with nothing to bracket must heal to an empty plan; got {res['steps']!r}"
    )
    assert _stored_breaks(manager), "again non-destructive -- the breaks are still stored"
