"""End-to-end Roborock harness: dispatch -> live current_room rollover -> completion.

Exercises the Wave 1-3 pieces TOGETHER through the real adapter + manager +
lifecycle listener against stubbed device services — the integration proof the
per-piece unit tests can't give. It pins, among other things, the on-the-wire
app_segment_clean params shape (list-wrapped), which no unit test asserted and
which was wrong until this harness caught it.

Flow:
  1. dispatch (start_selected_rooms) -> app_segment_clean params=[{segments,repeat}]
     with live-resolved ids; the queue-first room's fan is pushed live (per-room
     fan via vacuum.set_fan_speed — passes is global, mop is unsettable).
  2. run starts -> lifecycle marks has_observed_active_lifecycle.
  3. native rollover follows current_room through the device's optimized order
     as a live pointer, pushing each room's fan without treating pointer changes
     as completion proof; transit rooms ignored.
  4. completion (dock: cleaning binary off + charging) -> finalization fires via
     the require_job_active_clear gate.
"""

from __future__ import annotations

import pytest

from homeassistant.core import ServiceCall, SupportsResponse

from custom_components.eufy_vacuum.adapters.registry import clear_registry
from custom_components.eufy_vacuum.adapters.roborock import adapter as rb
from custom_components.eufy_vacuum.listeners import lifecycle


_VAC = "vacuum.ivy"
_MAP = "Main floor"
# Two TARGETS (Kitchen, Office); Dining Room is the dock room and NOT a target.
_KITCHEN, _OFFICE, _DINING = 16, 19, 17


class _FakeDevice:
    manufacturer = "Roborock"
    model = "roborock.vacuum.s6"


def _setup(hass, manager, monkeypatch):
    clear_registry()
    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _FakeDevice())

    # Entity surface (docked at the dock room before the run).
    hass.states.async_set(_VAC, "docked", {"supported_features": 30524, "fan_speed": "max"})
    hass.states.async_set("select.ivy_selected_map", _MAP)
    hass.states.async_set("sensor.ivy_status", "charging")
    hass.states.async_set("binary_sensor.ivy_cleaning", "off")
    hass.states.async_set("binary_sensor.ivy_charging", "on")
    hass.states.async_set("sensor.ivy_battery", "100")
    hass.states.async_set("sensor.ivy_current_room", "Dining Room")
    rb.register_roborock_adapter_for_vacuum(hass, _VAC)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)

    # Managed rooms via the real onboarding path (seed discovery -> save), which
    # confirms floor types so the run isn't blocked as onboarding_required. Only
    # Kitchen + Office are enabled targets; Dining Room is the dock room.
    discovered = [
        {"room_id": _KITCHEN, "map_id": _MAP, "name": "KITCHEN", "slug": "kitchen"},
        {"room_id": _OFFICE, "map_id": _MAP, "name": "Office", "slug": "office"},
    ]
    manager.data.setdefault("discovery", {}).setdefault(_VAC, {})[_MAP] = {
        "active_map_id": _MAP, "rooms": discovered,
    }
    manager.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, enabled_room_ids=[_KITCHEN, _OFFICE]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    rooms[str(_KITCHEN)]["order"] = 1   # queue order; device will path-optimize
    rooms[str(_OFFICE)]["order"] = 2
    # Per-room fan (valid Roborock vocab values) -> pushed live on room entry.
    rooms[str(_KITCHEN)]["fan_speed"] = "turbo"
    rooms[str(_OFFICE)]["fan_speed"] = "quiet"


def _stub_services(hass) -> dict[str, list]:
    calls: dict[str, list] = {"send": [], "fan": [], "mop": []}

    async def _send(call: ServiceCall):
        calls["send"].append(dict(call.data))

    async def _fan(call: ServiceCall):
        calls["fan"].append(dict(call.data))

    async def _mop(call: ServiceCall):
        calls["mop"].append(dict(call.data))

    async def _get_maps(call: ServiceCall):
        return {"maps": [{"flag": 0, "name": _MAP, "rooms": {
            "16": "KITCHEN", "17": "Dining Room", "19": "Office",
        }}]}

    hass.services.async_register("vacuum", "send_command", _send)
    hass.services.async_register("vacuum", "set_fan_speed", _fan)
    hass.services.async_register("select", "select_option", _mop)
    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    return calls


def _job(manager):
    return manager.data["active_jobs"][_VAC][_MAP]


async def _tick_rollover(manager, hass, current_room_name):
    """Simulate the device reporting a room + the 5s progress tick driving rollover."""
    hass.states.async_set("sensor.ivy_current_room", current_room_name)
    await hass.async_block_till_done()
    manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()


async def test_roborock_dispatch_rollover_completion(hass, manager, monkeypatch):
    _setup(hass, manager, monkeypatch)
    calls = _stub_services(hass)

    finalize_calls: list[dict] = []

    async def _finalize(**kwargs):
        finalize_calls.append(kwargs)
        return {"job_id": "j1", "completed_job": {}}

    async def _no_external(*, vacuum_entity_id):
        return False

    monkeypatch.setattr(manager, "finalize_learning_for_active_job", _finalize)
    monkeypatch.setattr(manager, "maybe_handle_external_run", _no_external)

    lifecycle.register(hass)

    # --- 1. DISPATCH -------------------------------------------------------
    result = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    assert result["started"] is True, (result.get("reason"), result.get("message"))

    assert len(calls["send"]) == 1
    send = calls["send"][0]
    assert send["entity_id"] == _VAC
    assert send["command"] == "app_segment_clean"
    # THE wire-shape assertion: params LIST-wrapped, live-resolved segments, queue order.
    assert send["params"] == [{"segments": [_KITCHEN, _OFFICE], "repeat": 1}]
    # Per-room fan: dispatch seeds the queue-first room's fan (Kitchen -> turbo).
    # No mop pre-call (the S6 mop is unsettable).
    assert [c["fan_speed"] for c in calls["fan"]] == ["turbo"]
    assert calls["mop"] == []

    assert _job(manager)["status"] == "started"

    # --- 2. RUN STARTS -> lifecycle marks active ---------------------------
    hass.states.async_set("binary_sensor.ivy_cleaning", "on")
    hass.states.async_set("sensor.ivy_status", "segment_cleaning")
    await hass.async_block_till_done()
    assert _job(manager).get("has_observed_active_lifecycle") is True
    assert finalize_calls == []  # mid-run, no completion

    # --- 3. NATIVE ROLLOVER (device order: Office first, then Kitchen) -----
    await _tick_rollover(manager, hass, "Office")
    assert _job(manager)["current_room_id"] == _OFFICE          # adopted, no phantom-complete
    assert _job(manager)["completed_room_ids"] == []
    assert calls["fan"][-1]["fan_speed"] == "quiet"             # Office fan pushed live

    await _tick_rollover(manager, hass, "KITCHEN")
    assert _job(manager)["completed_room_ids"] == []             # pointer move != completion
    assert _job(manager)["current_room_id"] == _KITCHEN
    assert calls["fan"][-1]["fan_speed"] == "turbo"             # Kitchen fan pushed live

    # transit room (a non-target the robot crosses) is ignored
    await _tick_rollover(manager, hass, "LIVINGROOM")
    assert _job(manager)["current_room_id"] == _KITCHEN          # unchanged
    assert calls["fan"][-1]["fan_speed"] == "turbo"             # no new fan call
    assert finalize_calls == []                                  # still running

    # --- 4. COMPLETION (dock: current_room reverts, cleaning off + charging) ---
    hass.states.async_set("sensor.ivy_current_room", "Dining Room")  # dock room, not a target
    hass.states.async_set("sensor.ivy_status", "charging")
    hass.states.async_set("binary_sensor.ivy_cleaning", "off")
    await hass.async_block_till_done()

    # The require_job_active_clear gate finalized once (charging + cleaning off
    # + has_observed). current_room reverting to the non-target dock room did NOT
    # trigger a spurious rollover.
    assert len(finalize_calls) == 1
