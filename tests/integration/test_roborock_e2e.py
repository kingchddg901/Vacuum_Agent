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

    def __init__(self, model="roborock.vacuum.s6"):
        self.model = model


def _setup(hass, manager, monkeypatch, model="roborock.vacuum.s6"):
    clear_registry()
    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _FakeDevice(model))

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


# ===========================================================================
# Stepped run (native in-queue charge): Kitchen -> charge_wait -> Office.
#
# The phase-interleave + charge-poller logic is covered generically in
# test_charge_wait_phase; THESE prove the pieces ride the REAL Roborock adapter
# end to end — a stepped run dispatches app_segment_clean ONCE PER GROUP with the
# charge break between (vac -> charge -> vac), which the flat harness above can't
# show. Roborock is the whole point of the charge step: an S6 re-docks + charges
# after each group anyway, so "charge to X% before the next group" is near-free.
# ===========================================================================

# [{room_group Kitchen}, {charge to 90%}, {room_group Office}] — the stash shape
# start_run_profile builds from a saved profile's steps (profiles.run_profile_steps).
_STEPPED = [
    {"type": "room_group", "rooms": [{"room_id": _KITCHEN}]},
    {"type": "charge_wait", "target_battery_percent": 90},
    {"type": "room_group", "rooms": [{"room_id": _OFFICE}]},
]


async def _start_stepped(hass, manager, monkeypatch, *, steps=None, model="roborock.vacuum.s6"):
    """Setup + kick a stepped run by seeding ``_pending_run_steps`` — exactly what
    ``start_run_profile`` stashes after applying a profile — then dispatching through
    the real adapter. Returns (calls, result).

    The charge poller + phase watchdog run as background tasks; we close them so the
    test drives dispatch synchronously (both are covered in test_charge_wait_phase /
    test_strict_order_phase_timing). Without this the initial watchdog would hit real
    ``asyncio.sleep`` verify windows and hang.
    """
    _setup(hass, manager, monkeypatch, model=model)
    calls = _stub_services(hass)

    async def _finalize(**kwargs):
        return {"job_id": "j1", "completed_job": {}}

    async def _no_external(*, vacuum_entity_id):
        return False

    monkeypatch.setattr(manager, "finalize_learning_for_active_job", _finalize)
    monkeypatch.setattr(manager, "maybe_handle_external_run", _no_external)
    if not hass.services.has_service("vacuum", "return_to_base"):
        hass.services.async_register("vacuum", "return_to_base", lambda call: None)
    monkeypatch.setattr(hass, "async_create_task", lambda coro, *a, **k: coro.close())

    manager.data.setdefault("_pending_run_steps", {}).setdefault(_VAC, {})[_MAP] = list(steps or _STEPPED)
    result = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    return calls, result


async def test_roborock_stepped_dispatch_builds_charge_phase(hass, manager, monkeypatch):
    """[RB-STEP-1] A stepped profile (Kitchen -> charge_wait -> Office) builds a 3-phase
    [room, charge_wait, room] job and dispatches app_segment_clean for GROUP 0 (Kitchen)
    ONLY — Office waits behind the charge, and the charge break is never a phantom clean."""
    calls, result = await _start_stepped(hass, manager, monkeypatch)
    assert result["started"] is True, (result.get("reason"), result.get("message"))

    job = _job(manager)
    assert [p.get("phase_type", "room") for p in job["phases"]] == ["room", "charge_wait", "room"]
    assert job["phases"][1]["target_battery_percent"] == 90
    assert job["current_phase_index"] == 0

    # Phase 0 dispatched Kitchen ONLY, params list-wrapped, live-resolved id.
    assert len(calls["send"]) == 1
    assert calls["send"][0]["command"] == "app_segment_clean"
    assert calls["send"][0]["params"] == [{"segments": [_KITCHEN], "repeat": 1}]
    # No mop pre-call on the S6 (mop unsettable) even in a stepped run.
    assert calls["mop"] == []


async def test_roborock_stepped_resumes_next_group_after_charge(hass, manager, monkeypatch):
    """[RB-STEP-2] After the charge_wait phase, advancing re-dispatches app_segment_clean
    for the NEXT group (Office) through the real adapter — the vac->charge->vac RESUME.
    Proves per-group re-dispatch, not just the first group."""
    from custom_components.eufy_vacuum.queue.queue_engine import advance_active_job_phase

    calls, _ = await _start_stepped(hass, manager, monkeypatch)

    # Walk the job to the Office phase (index 2) as the completion hook + charge poller
    # would (phase 0 clean done -> charge_wait -> target reached -> Office).
    job = _job(manager)
    for _ in range(2):
        job = advance_active_job_phase(job)
        assert job is not None
        manager.data["active_jobs"][_VAC][_MAP] = job
    assert job["current_phase_index"] == 2

    calls["send"].clear()
    calls["fan"].clear()
    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=job, attempt=1,
    )

    assert len(calls["send"]) == 1
    assert calls["send"][0]["command"] == "app_segment_clean"
    assert calls["send"][0]["params"] == [{"segments": [_OFFICE], "repeat": 1}]
    # Office's per-room fan (quiet) is pushed before its segment on the resume.
    assert calls["fan"][-1]["fan_speed"] == "quiet"


async def test_roborock_settable_mop_per_group_water(hass, manager, monkeypatch):
    """[RB-STEP-3] On a SETTABLE-mop model (S7), a per-group vac->mop run pushes the mop
    intensity select PER PHASE from each group's own water_level: Kitchen dry (off) then
    Kitchen mopped (high). Proves the global_pre_calls dispatch (Wave 2) + per-phase
    re-derivation (Wave 1) together. The S6 gets none of this (mop unsettable)."""
    from custom_components.eufy_vacuum.queue.queue_engine import advance_active_job_phase

    # Same room twice — a vacuum pass, a dry-hold wait, then a mop pass at high water.
    # clean_mode is the logical mop switch (vacuum forces water off; vacuum_mop keeps it).
    mop_steps = [
        {"type": "room_group", "rooms": [{"room_id": _KITCHEN, "clean_mode": "vacuum"}]},
        {"type": "wait", "wait_minutes": 1},
        {"type": "room_group",
         "rooms": [{"room_id": _KITCHEN, "clean_mode": "vacuum_mop", "water_level": "high"}]},
    ]
    calls, result = await _start_stepped(
        hass, manager, monkeypatch, steps=mop_steps, model="roborock.vacuum.a15"
    )
    assert result["started"] is True, (result.get("reason"), result.get("message"))

    # Phase 0 (vacuum): mop intensity set OFF before the Kitchen segment.
    assert calls["mop"], "settable model should push a mop pre-call"
    assert calls["mop"][-1]["entity_id"] == "select.ivy_mop_intensity"
    assert calls["mop"][-1]["option"] == "off"

    # Walk to the mop phase (index 2) and re-dispatch through the real adapter.
    job = _job(manager)
    for _ in range(2):
        job = advance_active_job_phase(job)
        assert job is not None
        manager.data["active_jobs"][_VAC][_MAP] = job
    assert job["current_phase_index"] == 2

    calls["mop"].clear()
    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=job, attempt=1,
    )
    # Phase 2 (mop): intensity re-derived from THIS group -> HIGH (per-phase, not the
    # whole-run max that would have mopped the vacuum pass too).
    assert calls["mop"][-1]["option"] == "high"
