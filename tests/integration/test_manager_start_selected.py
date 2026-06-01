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
"""

from __future__ import annotations

import pytest

from homeassistant.core import ServiceCall

from custom_components.eufy_vacuum.const import EVENT_ROOM_STARTED

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"


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
    for i, room in enumerate(rooms.values(), start=1):
        room["enabled"] = True
        room["order"] = i
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
