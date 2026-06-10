"""Tests for core/manager.py::start_selected_rooms — the start-cleaning path.

The largest untested manager method (~190 lines): evaluates start readiness,
builds the effective plan, dispatches the brand's clean command to the vacuum
service, seeds the active-job record, and fires EVENT_ROOM_STARTED. Driven
against the real manager with a recording stand-in for the vacuum service.

Coverage targets
----------------
[SS-1]  happy path: dispatch + active-job seeded + EVENT_ROOM_STARTED + started.
[SS-2]  blocked start (partial access graph) → started False, not dispatched.
[SS-3]  vacuum entity missing → started False, reason vacuum_missing.
[SS-4]  reduced run requires confirmation; confirm_reduced_run bypasses it.
[SS-5]  start_run_profile: unknown profile → not applied, no dispatch.
[SS-6]  start_run_profile: apply saved profile then dispatch the start.
"""

from __future__ import annotations

from homeassistant.core import ServiceCall

from custom_components.eufy_vacuum.const import EVENT_ROOM_STARTED

from tests._factories import VAC as _VAC, MAP as _MAP, set_room_field
from .conftest import setup_map


def _register_dispatch(hass) -> list[ServiceCall]:
    """Register a recording vacuum.send_command (the default dispatch target)."""
    calls: list[ServiceCall] = []

    async def _handler(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("vacuum", "send_command", _handler)
    return calls


def _seed_enabled(manager, count=2):
    setup_map(manager, _VAC, _MAP, count=count)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    for i, rid in enumerate(rooms, start=1):
        set_room_field(manager, rid, enabled=True, order=i)
    return rooms


def _blocker(entity):
    return {"kind": "blocker", "id": "b1", "entity_id": entity,
            "operator": "is_on", "effect": {"reason": "window_open"}}


async def test_start_happy(manager, hass):
    """[SS-1]"""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _seed_enabled(manager)
    hass.states.async_set(_VAC, "docked", {"battery_level": 90})
    calls = _register_dispatch(hass)
    events = []
    hass.bus.async_listen(EVENT_ROOM_STARTED, lambda e: events.append(e))

    result = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()

    assert result["started"] is True
    assert result["reason"] == "started"
    # the clean command was dispatched to the vacuum service
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == _VAC
    # active job seeded with a job id + started timestamp
    job = manager.data["active_jobs"][_VAC][_MAP]
    assert job["job_id"] and job["started_at"]
    # a room started → event fired
    assert len(events) == 1
    assert events[0].data["vacuum_entity_id"] == _VAC


async def test_start_blocked_partial_graph(manager, hass):
    """[SS-2] a partial access graph blocks the start before any dispatch."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    rooms = _seed_enabled(manager)
    first = next(iter(rooms.values()))
    first["is_dock_room"] = True
    first["grants_access_to"] = [99]   # missing room → invalid → partial
    hass.states.async_set(_VAC, "docked")
    calls = _register_dispatch(hass)

    result = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["started"] is False
    assert calls == []


async def test_start_vacuum_missing(manager, hass):
    """[SS-3] no vacuum entity in the state machine → started False."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _seed_enabled(manager)
    # deliberately do NOT set the vacuum state
    calls = _register_dispatch(hass)
    result = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["started"] is False
    assert result["reason"] == "vacuum_missing"
    assert calls == []


async def test_start_requires_confirmation(manager, hass):
    """[SS-4] a reduced run needs confirmation; confirm_reduced_run proceeds."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    rooms = _seed_enabled(manager)
    keys = list(rooms.keys())
    rooms[keys[0]].update({"is_dock_room": True, "grants_access_to": [2]})
    rooms[keys[1]]["rules"] = [_blocker("binary_sensor.win")]
    hass.states.async_set("binary_sensor.win", "on")
    hass.states.async_set(_VAC, "docked")
    calls = _register_dispatch(hass)

    # 1 of 2 rooms blocked (50%) → confirmation required, no dispatch
    pending = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert pending["started"] is False
    assert pending["reason"] == "confirmation_required"
    assert calls == []

    # confirm_reduced_run bypasses the gate → dispatched + started
    done = await manager.start_selected_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, confirm_reduced_run=True)
    await hass.async_block_till_done()
    assert done["started"] is True
    assert len(calls) == 1


async def test_start_snapshot_error_degrades(manager, hass, monkeypatch):
    """[SS-7] a failed learning snapshot still starts the job, but the result
    carries a user-visible degraded learning_snapshot (saved False/snapshot_error).

    This is the except at start_selected_rooms — it logs AND returns a degraded
    response field to the caller (a supports_response service), not just metadata.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _seed_enabled(manager)
    hass.states.async_set(_VAC, "docked")
    _register_dispatch(hass)

    def _boom(**kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(manager, "save_learning_snapshot_for_active_job", _boom)

    result = await manager.start_selected_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    # the job still starts despite the snapshot failure
    assert result["started"] is True
    # but the caller sees the degraded snapshot status
    assert result["learning_snapshot"]["saved"] is False
    assert result["learning_snapshot"]["reason"] == "snapshot_error"


async def test_start_run_profile_not_found(manager, hass):
    """[SS-5]"""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _seed_enabled(manager)
    hass.states.async_set(_VAC, "docked")
    calls = _register_dispatch(hass)
    res = await manager.start_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="ghost")
    assert res["started"] is False
    assert res["reason"] == "profile_not_found"
    assert calls == []


async def test_maybe_advance_phase_sequenced(manager, hass):
    """[SS-8] a sequenced job advances + re-dispatches the next phase, then on the
    final phase returns False so the caller finalizes."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    calls = _register_dispatch(hass)

    phase0 = {"resolved_rooms": [{"room_id": 1}], "payload": {"phase": 0}, "room_count": 1}
    phase1 = {"resolved_rooms": [{"room_id": 2}], "payload": {"phase": 1}, "room_count": 1}
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [phase0, phase1], "current_phase_index": 0,
        "resolved_rooms": phase0["resolved_rooms"], "payload": phase0["payload"],
        "completed_room_ids": [1], "current_room_id": None,
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }

    # phase 0 complete -> advance to phase 1 + re-dispatch
    advanced = await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    assert advanced is True
    assert len(calls) == 1                                   # next phase dispatched
    job = manager.data["active_jobs"][_VAC][_MAP]
    assert job["current_phase_index"] == 1
    assert job["current_room_id"] == 2                       # swapped to phase 1's rooms
    assert job["completed_room_ids"] == []                   # per-phase progress reset
    assert job["has_observed_active_lifecycle"] is False     # fresh sub-job

    # final phase -> no advance; caller finalizes, no extra dispatch
    again = await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP)
    assert again is False
    assert len(calls) == 1


async def test_maybe_advance_phase_atomic_is_noop(manager, hass):
    """[SS-9] an atomic job (no phases) never advances -> caller finalizes."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    calls = _register_dispatch(hass)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "resolved_rooms": [{"room_id": 1}], "completed_room_ids": [1],
        "current_room_id": None, "job_id": "j1",
    }
    assert await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is False
    assert calls == []


async def test_start_run_profile_success(manager, hass):
    """[SS-6] save a run profile, then start it through the protected path."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _seed_enabled(manager)
    hass.states.async_set(_VAC, "docked")
    calls = _register_dispatch(hass)
    pid = manager.save_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, name="Evening")["profile_id"]
    res = await manager.start_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    await hass.async_block_till_done()
    assert res["started"] is True
    assert res["profile_id"] == pid
    assert len(calls) == 1


async def test_clear_room_selections_after_start_flips_enabled_room(manager, hass):
    """[CSS-1] _clear_room_selections_after_start changed path: an enabled room
    flips to enabled=False while an already-disabled room is left untouched, and
    because something changed the summary is rebuilt to reflect zero enabled.

    setup_map(count=2) seeds both rooms enabled by default; room "2" is then
    explicitly disabled, so the clear must flip only room "1" (line 626-630),
    skip the already-off room "2" (line 625), and run the changed-tail (line 636).
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    set_room_field(manager, 2, enabled=False)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]

    # Precondition: room "1" enabled (changed path), room "2" already off (line 625).
    assert rooms["1"]["enabled"] is True
    assert rooms["2"]["enabled"] is False

    manager._clear_room_selections_after_start(
        vacuum_entity_id=_VAC, map_id=_MAP)

    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    # Changed path (line 626-630): the enabled room is now off.
    assert rooms["1"]["enabled"] is False
    # Already-off room left exactly as-is (line 625 skip).
    assert rooms["2"]["enabled"] is False
    # Other per-room fields survive the flip (only `enabled` is rewritten).
    assert rooms["1"]["name"] == "Room 1"
    # Something changed → the summary was rebuilt (the changed-tail ran).
    assert manager.data["maps"][_VAC][_MAP]["summary"]["enabled_count"] == 0


async def test_clear_room_selections_after_start_noop_skips_and_returns(
    manager, hass
):
    """[CSS-2] Skip + early-return branches: a non-dict room entry is skipped
    (line 623), an already-disabled room is skipped (line 625), and with nothing
    enabled the method early-returns before rebuilding the summary (line 633),
    leaving every entry — including the non-dict one — untouched. Separately, a
    map id with no rooms returns without raising (line 618).

    The non-dict entry is asserted only on this no-change path on purpose: the
    changed-tail summary builder requires numeric-keyed dict rooms, so a non-dict
    entry can only coexist with a call that takes the line-633 early return.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)
    # Disable the only real room so the flip loop has a disabled dict to skip
    # (line 625) and nothing left enabled → line-633 early return.
    set_room_field(manager, 1, enabled=False)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    rooms["junk"] = "x"   # non-dict entry the flip loop must skip (line 623)

    before = {
        k: (dict(v) if isinstance(v, dict) else v) for k, v in rooms.items()
    }
    # Sanity: no enabled rooms remain, so the flip loop changes nothing.
    assert all(
        not v.get("enabled", False)
        for v in before.values()
        if isinstance(v, dict)
    )

    manager._clear_room_selections_after_start(
        vacuum_entity_id=_VAC, map_id=_MAP)

    after = {
        k: (dict(v) if isinstance(v, dict) else v)
        for k, v in manager.data["maps"][_VAC][_MAP]["rooms"].items()
    }
    # Nothing changed (line 633 early-return): every entry — including the
    # non-dict one (line 623 skip) — is exactly as it was.
    assert after == before
    assert after["junk"] == "x"

    # Empty/no-rooms map id → ensure_map_bucket yields rooms={} → returns (line 618).
    manager._clear_room_selections_after_start(
        vacuum_entity_id=_VAC, map_id="no_such_map")
    assert manager.data["maps"][_VAC]["no_such_map"]["rooms"] == {}
