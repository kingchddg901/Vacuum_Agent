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
[DISP-1]  _dispatch_clean_payload merges directly {entity_id, **payload} when no command declared.
[DISP-2]  _dispatch_clean_payload wraps {entity_id, command, params} when a command is declared.
[MQ-10] clear_queue drops the interleaved breaks, not just the rooms.
[MQ-11] applying a STEPPED run profile records its breaks (a plain Start no longer runs it flat).
[MQ-12] applying a FLAT run profile WIPES breaks left over from an earlier composition.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
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


# ---------------------------------------------------------------------------
# [DISP-1] — [DISP-2] _dispatch_clean_payload envelope shapes
#
# The method under test is core/manager.py::_dispatch_clean_payload (~3732-3753;
# the conceptual "room clean dispatch"). It reads the adapter's dispatch config
# and emits one of two service-call envelopes:
#   - direct-merge {entity_id, **payload}      when NO 'command' is declared
#     (Dreame-style vacuum_clean_segment) — manager.py line 3752
#   - wrapped {entity_id, command, params}     when a 'command' IS declared
#     (Eufy/Roborock/Ecovacs send_command) — manager.py line 3750
# A recording service captures call.data so we assert the exact emitted shape.
#
# Cleanup: register_adapter_config routes to the per-test AdapterCoordinator
# (wired by the `manager` fixture), whose registry is torn down with the
# fixture; the recording services live on the function-scoped `hass`. No manual
# teardown / no scheduled timers — the call is synchronous-await with no later().
# ---------------------------------------------------------------------------

async def test_dispatch_clean_payload_direct_merge_no_command(manager, hass):
    """[DISP-1] With no declared 'command' (Dreame vacuum_clean_segment), the
    payload is merged directly into the service data — {entity_id, **payload},
    with NO 'command'/'params' wrapper (manager.py line 3752)."""
    register_adapter_config(
        _VAC,
        {
            "adapter_id": "dreame_direct_merge",
            "dispatch": {
                "service_domain": "vacuum",
                "service_name": "clean_segment",
                "command": "",
            },
            "entities": {"task_status": "sensor.alfred_task_status"},
        },
    )
    recorded: list[dict] = []

    async def _recorder(call):
        recorded.append(dict(call.data))

    hass.services.async_register("vacuum", "clean_segment", _recorder)

    await manager._dispatch_clean_payload(
        vacuum_entity_id=_VAC,
        payload={"segments": [1, 2], "fan": "Quiet"},
    )
    await hass.async_block_till_done()

    assert recorded == [{"entity_id": _VAC, "segments": [1, 2], "fan": "Quiet"}]
    # Direct-merge envelope must NOT wrap into command/params.
    assert "command" not in recorded[0]
    assert "params" not in recorded[0]


async def test_dispatch_clean_payload_wrapped_with_command(manager, hass):
    """[DISP-2] With a declared 'command' (Eufy room_clean send_command), the
    payload is wrapped into {entity_id, command, params} (manager.py line 3750).
    Contrast branch proving both sides of the same dispatch seam."""
    register_adapter_config(
        _VAC,
        {
            "adapter_id": "eufy_wrapped",
            "dispatch": {
                "service_domain": "vacuum",
                "service_name": "send_command",
                "command": "room_clean",
            },
            "entities": {"task_status": "sensor.alfred_task_status"},
        },
    )
    recorded: list[dict] = []

    async def _recorder(call):
        recorded.append(dict(call.data))

    hass.services.async_register("vacuum", "send_command", _recorder)

    await manager._dispatch_clean_payload(
        vacuum_entity_id=_VAC,
        payload={"segments": [1, 2], "fan": "Quiet"},
    )
    await hass.async_block_till_done()

    assert recorded == [
        {
            "entity_id": _VAC,
            "command": "room_clean",
            "params": {"segments": [1, 2], "fan": "Quiet"},
        }
    ]


# ---------------------------------------------------------------------------
# [MQ-10..12] RP-021c / #8:A4-PP-RP-4 — the queue's TWO backings move together
#
# Deliberately here, against the REAL manager fixture, rather than in
# test_profiles_manager.py which drives ProfileManager with a MagicMock manager.
# The fix calls self._manager.set_queue_breaks(...); against a mock that call
# does nothing and returns a mock, so every assertion below would pass while the
# breaks were never written. A mock agrees with the caller, not the callee.
# ---------------------------------------------------------------------------

def _bucket(manager):
    return manager.data["maps"][_VAC][str(_MAP)]


def _save_profile(manager, profile_id, profile):
    store = manager.profiles._get_saved_run_profile_store(
        vacuum_entity_id=_VAC, map_id=str(_MAP)
    )
    store[profile_id] = profile


async def test_clear_queue_also_clears_breaks(manager):
    """[MQ-10] "Clear queue" drops the interleaved breaks too.

    The live queue has TWO backings — enabled rooms, and the charge/wait/zone
    breaks between them. clear_queue emptied only the first, so the breaks
    survived with no rooms to sit between and the NEXT composition inherited
    them: a charge break landing after an arbitrary room of a run that never
    asked for one.
    """
    setup_map(manager, _VAC, _MAP, count=3)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="charge_wait",
        after_index=1, target_battery_percent=90,
    )
    assert _bucket(manager)["queue_breaks"], "precondition: a break was added"

    manager.clear_queue(vacuum_entity_id=_VAC, map_id=_MAP)

    assert _bucket(manager)["queue_breaks"] == []
    assert "queue_source" not in _bucket(manager)


async def test_apply_stepped_profile_writes_its_breaks(manager):
    """[MQ-11] Applying a STEPPED profile records its structure, not just rooms.

    Without this, apply enabled the right rooms in the right ORDER and stopped —
    so a plain Start (reloaded dashboard, second tab, phone, or an automation
    doing apply_run_profile then start_cleaning) ran the profile FLAT: the
    charge break never happened and the robot died mid-run.
    """
    setup_map(manager, _VAC, _MAP, count=3)
    _save_profile(manager, "nightly", {
        "name": "Nightly",
        "rooms": [{"room_id": 1}, {"room_id": 2}],
        "steps": [
            {"type": "room_group", "rooms": [{"room_id": 1}]},
            {"type": "charge_wait", "target_battery_percent": 90},
            {"type": "room_group", "rooms": [{"room_id": 2}]},
        ],
    })

    out = manager.profiles.apply_run_profile(
        vacuum_entity_id=_VAC, map_id=str(_MAP), profile_id="nightly"
    )
    assert out["applied"] is True

    breaks = _bucket(manager)["queue_breaks"]
    assert len(breaks) == 1, f"expected the charge break to be recorded, got {breaks}"
    assert breaks[0]["after_index"] == 1          # after the FIRST room, not room id 1
    assert breaks[0]["step"]["type"] == "charge_wait"

    source = _bucket(manager)["queue_source"]
    assert source["stepped"] is True
    assert source["profile_id"] == "nightly"


async def test_apply_flat_profile_wipes_leftover_breaks(manager):
    """[MQ-12] Applying a FLAT profile clears breaks the map was still carrying.

    The finding's other half. set_queue_breaks is replace-ALL, so a flat profile
    deriving an empty list is what evicts a stale charge break from an earlier
    composition — rather than letting it attach itself to a run that never asked
    for one. This is why the two halves are one fix.
    """
    setup_map(manager, _VAC, _MAP, count=3)
    manager.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    manager.add_queue_break(
        vacuum_entity_id=_VAC, map_id=_MAP, break_type="charge_wait",
        after_index=1, target_battery_percent=90,
    )
    assert _bucket(manager)["queue_breaks"], "precondition: a stale break exists"

    _save_profile(manager, "flat", {
        "name": "Flat", "rooms": [{"room_id": 1}, {"room_id": 2}],
    })
    out = manager.profiles.apply_run_profile(
        vacuum_entity_id=_VAC, map_id=str(_MAP), profile_id="flat"
    )
    assert out["applied"] is True

    assert _bucket(manager)["queue_breaks"] == []
    assert _bucket(manager)["queue_source"]["stepped"] is False
