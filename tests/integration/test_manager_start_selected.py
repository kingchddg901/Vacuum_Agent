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
[SS-7]  failed learning snapshot still starts → degraded learning_snapshot.
[SS-8]  sequenced job advances + re-dispatches next phase; final → False.
[SS-9]  atomic job (no phases) never advances → caller finalizes.
[SS-10] sequenced advance sets the next room's per-room fan (awaited) BEFORE
        re-dispatch — native per-room fan in strict order, no poll lag.
[SS-11] sequenced advance re-dispatches up to _PHASE_MAX_ATTEMPTS when the device
        doesn't start (ignored the post-dock clean), then gives up (watchdog).
[SS-12] phase verify with a native current-room signal: current_room == the phase
        target → confirmed started, no retry.
[SS-13] phase verify false-positive fix: device reports 'cleaning' but current_room
        is the dock (not the target) → not fooled, retries to the cap.
[SS-15] dock-room-as-target: current_room == target but vacuum docked (not cleaning)
        → verify requires actively-cleaning → no false-confirm, retries; pending stays.
[SS-16] initial phase is verify-only: _run_advanced_phase(initial=True) skips the
        settle + first dispatch, confirms room 0, clears the dispatch-pending guard.
[SS-17] verify requires _PHASE_CONFIRM_SECONDS cumulative cleaning-the-target seconds
        (sustained, not a single flicker sample) before releasing the guard.
[SS-18] cumulative tally is not reset by a transient current-room dip (accumulate,
        not strict continuity) — still confirms once enough real cleaning is seen.
[SS-19] non-native fallback confirms immediately on one 'cleaning' sample — the
        cumulative requirement is native-only (a non-native brand can't measure it).
[SS-20] native: a device that never cleans the target (parked/ignored) hits the
        no-progress budget -> verify returns False -> re-dispatch.
[SS-21] _phase_target_is_dock_room reads the map's per-room is_dock_room flag.
[SS-22] advanced phase targeting the dock room waits _PHASE_DOCK_SETTLE_SECONDS.
[SS-23] advanced phase targeting a normal room waits _PHASE_SETTLE_SECONDS.
[SS-24] _phase_timing: adapter dispatch.phase_timing overrides the in-core defaults
        per key; omitted keys + no adapter -> defaults (brand timing in the adapter).
[SS-25] start_selected_rooms(strict_order=True) on a path-optimizing brand builds a
        one-phase-per-room sequenced job + arms the guard/watchdog (the ENTRY path).
[SS-26] _run_advanced_phase: job cancelled during the settle window -> guard aborts
        with NO re-dispatch (a Cancel Run mid-settle can't spuriously re-clean).
[SS-27] _await_phase_started: job moved on (cancelled/advanced) mid-poll -> returns
        True (nothing to retry) instead of re-dispatching against a stopped job.
[SS-28] _vacuum_started_cleaning: vacuum state not yet 'cleaning' but the adapter's
        job_active binary is on -> True (the device's inCleaning flag confirms dispatch).
[SS-29] _await_phase_started: a small room cleaned in under confirm_seconds (cleaned-
        then-docked) confirms via the idle-exit instead of stalling the phase forever.
[SS-30] pause releases the strict-order dispatch guard (and the watchdog bails on
        status!=started) so a pause/resume can't leave it stuck and stall the run.
[SS-31] the watchdog bails (no re-dispatch) when _cancel_in_flight is set — a cancel
        can't be undone by a re-dispatch during the return-to-base window.
[CSS-1] _clear_room_selections_after_start: enabled room flips off, summary rebuilt.
[CSS-2] _clear_room_selections_after_start: skip non-dict/off rooms, early-return, empty map.
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


def _instant_phase_dispatch(monkeypatch):
    """Zero the settle/verify/confirm delays so the spawned re-dispatch task runs to
    completion inside async_block_till_done (no real waiting in tests). With confirm
    at 0 a single cleaning+on-target poll confirms; the sustained-accumulation
    behaviour is exercised separately in test_phase_verify_requires_sustained_cleaning."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    monkeypatch.setattr(_mgr, "_PHASE_SETTLE_SECONDS", 0)
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 0)
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 0)


async def test_maybe_advance_phase_sequenced(manager, hass, monkeypatch):
    """[SS-8] a sequenced job advances + re-dispatches the next phase, then on the
    final phase returns False so the caller finalizes."""
    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")  # verify sees it started -> no retry
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


async def test_maybe_advance_phase_sets_fan_before_dispatch(manager, hass, monkeypatch):
    """[SS-10] strict-order advance applies the next room's per-room fan (awaited)
    BEFORE re-dispatching its segment — so the room starts at its own fan with no
    current_room poll lag (native per-room fan; passes already ride the payload)."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")  # verify sees it started -> no retry

    order: list[str] = []

    async def _send(call: ServiceCall) -> None:
        order.append("dispatch")

    async def _fan(call: ServiceCall) -> None:
        order.append(f"fan:{call.data.get('fan_speed')}")

    hass.services.async_register("vacuum", "send_command", _send)
    hass.services.async_register("vacuum", "set_fan_speed", _fan)

    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "vocabulary": {"fan_speed_options": [{"value": "quiet"}, {"value": "turbo"}]},
        "dispatch": {"per_room_live_settings": [
            {"field": "fan_speed", "options_key": "fan_speed_options",
             "service": {"domain": "vacuum", "service": "set_fan_speed",
                         "value_key": "fan_speed"}},
        ]},
    })
    try:
        phase0 = {"resolved_rooms": [{"room_id": 1, "fan_speed": "quiet"}],
                  "payload": {"segments": [1]}, "room_count": 1}
        phase1 = {"resolved_rooms": [{"room_id": 2, "fan_speed": "turbo"}],
                  "payload": {"segments": [2]}, "room_count": 1}
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
            "phases": [phase0, phase1], "current_phase_index": 0,
            "resolved_rooms": phase0["resolved_rooms"], "payload": phase0["payload"],
            "completed_room_ids": [1], "current_room_id": 1,
            "has_observed_active_lifecycle": True,
            "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        }
        advanced = await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP)
        await hass.async_block_till_done()
        assert advanced is True
        # Room 2's fan (turbo) is set BEFORE the segment dispatch.
        assert order == ["fan:turbo", "dispatch"]
    finally:
        unregister_adapter_config(_VAC)


async def test_maybe_advance_phase_retries_until_max(manager, hass, monkeypatch):
    """[SS-11] when the device never starts after a dispatch (it ignored the clean
    sent the instant it docked), the phase re-dispatches up to _PHASE_MAX_ATTEMPTS,
    then gives up — the per-phase watchdog."""
    import custom_components.eufy_vacuum.core.manager as _mgr

    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked")  # never goes active -> always retries
    calls = _register_dispatch(hass)

    phase0 = {"resolved_rooms": [{"room_id": 1}], "payload": {"segments": [1]}, "room_count": 1}
    phase1 = {"resolved_rooms": [{"room_id": 2}], "payload": {"segments": [2]}, "room_count": 1}
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [phase0, phase1], "current_phase_index": 0,
        "resolved_rooms": phase0["resolved_rooms"], "payload": phase0["payload"],
        "completed_room_ids": [1], "current_room_id": 1,
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }

    assert await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
    await hass.async_block_till_done()
    # one dispatch per attempt, capped at the watchdog limit (never saw cleaning)
    assert len(calls) == _mgr._PHASE_MAX_ATTEMPTS
    # device never started -> dispatch-pending stays set, so the run stalls
    # (recoverable via Cancel Run) instead of finalizing a room that never cleaned
    assert manager.data["active_jobs"][_VAC][_MAP].get("_phase_dispatch_pending") is True


def _native_phase_job(manager):
    """Seed a 2-phase strict-order job whose rooms carry names/slugs so the native
    current-room signal can be matched (phase 0 Kitchen done -> advance to Hallway)."""
    phase0 = {"resolved_rooms": [{"room_id": 1, "name": "Kitchen", "slug": "kitchen"}],
              "payload": {"segments": [1]}, "room_count": 1}
    phase1 = {"resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
              "payload": {"segments": [2]}, "room_count": 1}
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [phase0, phase1], "current_phase_index": 0,
        "resolved_rooms": phase0["resolved_rooms"], "payload": phase0["payload"],
        "completed_room_ids": [1], "current_room_id": 1,
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }


async def test_phase_verify_native_on_target_success(manager, hass, monkeypatch):
    """[SS-12] with a native current-room signal, the watchdog confirms the
    DISPATCHED room actually started (current_room == the phase target) and does
    not retry — reuses the native-rollover slug match."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")  # the OLD check would pass here too
    hass.states.async_set("sensor.test_current_room", "Hallway")  # == phase 1 target
    calls = _register_dispatch(hass)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        _native_phase_job(manager)
        assert await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
        await hass.async_block_till_done()
        assert len(calls) == 1  # on the target room -> verified, no retry
        # watchdog confirmed the target room started -> dispatch-pending cleared,
        # so this phase's real completion can finalize/advance normally
        assert manager.data["active_jobs"][_VAC][_MAP].get("_phase_dispatch_pending") is False
    finally:
        unregister_adapter_config(_VAC)


async def test_phase_verify_native_wrong_room_retries(manager, hass, monkeypatch):
    """[SS-13] false-positive fix: the device reports 'cleaning' (the OLD job-active
    check would pass) but current_room is the DOCK room, not the dispatched target.
    The native verify isn't fooled — it retries to the watchdog cap, so a clean the
    device ignored at the dock is actually re-sent."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")            # the trap: old check passes
    hass.states.async_set("sensor.test_current_room", "Dining Room")  # dock, not a target
    calls = _register_dispatch(hass)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        _native_phase_job(manager)
        assert await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
        await hass.async_block_till_done()
        # never on the target room -> not fooled by "cleaning" -> retried to the cap
        assert len(calls) == _mgr._PHASE_MAX_ATTEMPTS
    finally:
        unregister_adapter_config(_VAC)


async def test_phase_verify_dock_room_as_target_not_confirmed(manager, hass, monkeypatch):
    """[SS-15] dock-room-as-target: the device reports current_room == the dispatched
    target (the dock physically sits in that room) but is DOCKED, not cleaning. Position
    alone would false-confirm; requiring vacuum.state == cleaning isn't fooled, so the
    watchdog retries to the cap and the dispatch-pending guard stays set (the run stalls
    for Cancel Run rather than finalizing a room that never actually cleaned)."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked")              # parked, not cleaning
    hass.states.async_set("sensor.test_current_room", "Hallway")  # == phase 1 target
    calls = _register_dispatch(hass)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        _native_phase_job(manager)
        assert await manager.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
        await hass.async_block_till_done()
        # on the target room but DOCKED -> not confirmed -> retried to the cap
        assert len(calls) == _mgr._PHASE_MAX_ATTEMPTS
        # never confirmed cleaning -> pending stays set so completion can't finalize it
        assert manager.data["active_jobs"][_VAC][_MAP].get("_phase_dispatch_pending") is True
    finally:
        unregister_adapter_config(_VAC)


async def test_initial_phase_is_verify_only(manager, hass, monkeypatch):
    """[SS-16] phase 0 was already dispatched by start_selected_rooms, so the watchdog
    for it runs initial=True: it skips the settle + the first dispatch and just VERIFIES
    the device actually started room 0, then clears the dispatch-pending guard. (A parked
    robot whose dock is in a target room would otherwise let the completion gate finalize
    room 0 the instant it started — Fix A.)"""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.test_current_room", "Kitchen")  # == phase 0 target
    calls = _register_dispatch(hass)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
            "phases": [
                {"resolved_rooms": [{"room_id": 1, "name": "Kitchen", "slug": "kitchen"}],
                 "payload": {"segments": [1]}, "room_count": 1},
                {"resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
                 "payload": {"segments": [2]}, "room_count": 1},
            ],
            "current_phase_index": 0,
            "resolved_rooms": [{"room_id": 1, "name": "Kitchen", "slug": "kitchen"}],
            "queue_room_ids": [1],
            "current_room_id": 1,
            "_phase_dispatch_pending": True,
            "has_observed_active_lifecycle": True,
            "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        }
        await manager._run_advanced_phase(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0, initial=True
        )
        await hass.async_block_till_done()
        # verify-only: the initial phase is NOT re-dispatched (start already sent it)
        assert calls == []
        # confirmed cleaning room 0 -> guard cleared so its real completion can finalize
        assert manager.data["active_jobs"][_VAC][_MAP].get("_phase_dispatch_pending") is False
    finally:
        unregister_adapter_config(_VAC)


async def test_phase_verify_requires_sustained_cleaning(manager, hass, monkeypatch):
    """[SS-17] the native verify requires _PHASE_CONFIRM_SECONDS CUMULATIVE seconds of
    cleaning-the-target before releasing the guard — a single cleaning+on-target sample
    (a flicker, or the dock-in-target room momentarily reading 'current') is not enough.
    With the poll sleep stubbed out, confirmation takes several polls, not one."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    # Spin the poll loop with no real delay; require 15s == 3 polls @ 5s to confirm.
    monkeypatch.setattr(_mgr.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 90)
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 15)
    monkeypatch.setattr(_mgr, "_PHASE_POLL_SECONDS", 5)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.test_current_room", "Hallway")
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
            "phases": [{"resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
                        "payload": {"segments": [2]}, "room_count": 1}],
            "current_phase_index": 0,
            "resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
            "queue_room_ids": [2],
            "current_room_id": 2,
            "has_observed_active_lifecycle": True,
            "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        }
        result = await manager._await_phase_started(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0
        )
        assert result is True                       # sustained cleaning-on-target confirms
        # required more than a single sample: it slept (polled) at least twice before
        # the cumulative tally reached the confirm threshold.
        assert _mgr.asyncio.sleep.await_count >= 2
    finally:
        unregister_adapter_config(_VAC)


async def test_phase_verify_tolerates_current_room_dips(manager, hass, monkeypatch):
    """[SS-18] the cumulative tally is NOT reset by a transient current-room dip: a
    poll where the live signal momentarily leaves the target just doesn't add, and
    accumulation resumes — so a flickering signal still confirms once enough real
    cleaning is observed (accumulate, not strict continuity). With a reset-on-dip bug
    the same sequence would need an extra poll to confirm."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 90)
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 15)   # 3 matching polls @ 5s
    monkeypatch.setattr(_mgr, "_PHASE_POLL_SECONDS", 5)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.test_current_room", "Hallway")  # poll 1 matches
    # Each poll's sleep advances the live current-room: a DIP off-target on poll 2,
    # then back on target. Matches at polls 1, 3, 4 -> 3 matches over 4 polls.
    seq = iter(["Foyer", "Hallway", "Hallway", "Hallway"])

    async def _tick(*_a, **_k):
        try:
            hass.states.async_set("sensor.test_current_room", next(seq))
        except StopIteration:
            pass

    sleep_mock = AsyncMock(side_effect=_tick)
    monkeypatch.setattr(_mgr.asyncio, "sleep", sleep_mock)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
            "phases": [{"resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
                        "payload": {"segments": [2]}, "room_count": 1}],
            "current_phase_index": 0,
            "resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
            "queue_room_ids": [2],
            "current_room_id": 2,
            "has_observed_active_lifecycle": True,
            "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        }
        result = await manager._await_phase_started(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0
        )
        assert result is True
        # 3 matching polls reached over 4 polls (1 dip) -> exactly 3 sleeps. A tally
        # that reset on the dip would need a 5th poll (4 sleeps) to re-accumulate.
        assert sleep_mock.await_count == 3
    finally:
        unregister_adapter_config(_VAC)


async def test_phase_verify_non_native_immediate(manager, hass, monkeypatch):
    """[SS-19] a brand with NO native current-room signal uses the coarse cleaning
    check, which confirms on a single 'cleaning' sample — the cumulative
    _PHASE_CONFIRM_SECONDS requirement is native-only (otherwise a non-native brand
    would never meet a tally it can't measure and would stall every phase)."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    # CONFIRM non-zero: if accumulation were (wrongly) applied to the fallback, this
    # would force multiple polls instead of an immediate confirm.
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 90)
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 45)
    monkeypatch.setattr(_mgr, "_PHASE_POLL_SECONDS", 5)
    sleep_mock = AsyncMock()
    monkeypatch.setattr(_mgr.asyncio, "sleep", sleep_mock)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    # No adapter config registered -> has_native False -> coarse fallback.
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [{"resolved_rooms": [{"room_id": 1}], "payload": {}, "room_count": 1}],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 1}], "queue_room_ids": [1], "current_room_id": 1,
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }
    result = await manager._await_phase_started(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0
    )
    assert result is True
    assert sleep_mock.await_count == 0          # immediate, no accumulation polling


async def test_phase_verify_idle_window_retries(manager, hass, monkeypatch):
    """[SS-20] native path: a device that never cleans the target (parked on the dock /
    ignored the dispatch) accrues the no-progress budget and the attempt gives up
    (returns False -> re-dispatch) after _PHASE_VERIFY_SECONDS with no cleaning of the
    target — even though its current_room reads as the target the whole time."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 20)   # 4 idle polls @ 5s
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 45)
    monkeypatch.setattr(_mgr, "_PHASE_POLL_SECONDS", 5)
    sleep_mock = AsyncMock()
    monkeypatch.setattr(_mgr.asyncio, "sleep", sleep_mock)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked")                    # never cleaning
    hass.states.async_set("sensor.test_current_room", "Hallway")  # on target but docked
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
            "phases": [{"resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
                        "payload": {"segments": [2]}, "room_count": 1}],
            "current_phase_index": 0,
            "resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
            "queue_room_ids": [2],
            "current_room_id": 2,
            "has_observed_active_lifecycle": True,
            "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        }
        result = await manager._await_phase_started(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0
        )
        assert result is False                  # no cleaning-of-target -> idle budget hit
    finally:
        unregister_adapter_config(_VAC)


def test_phase_target_is_dock_room(manager):
    """[SS-21] _phase_target_is_dock_room reads the map's per-room is_dock_room flag
    (int or str room id), and is safe (False) for an unknown room or None."""
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "rooms": {
            "18": {"room_id": 18, "name": "Dining Room", "is_dock_room": True},
            "27": {"room_id": 27, "name": "Kitchen", "is_dock_room": False},
        }
    }
    assert manager._phase_target_is_dock_room(_VAC, _MAP, 18) is True
    assert manager._phase_target_is_dock_room(_VAC, _MAP, "18") is True
    assert manager._phase_target_is_dock_room(_VAC, _MAP, 27) is False
    assert manager._phase_target_is_dock_room(_VAC, _MAP, 99) is False    # unknown room
    assert manager._phase_target_is_dock_room(_VAC, _MAP, None) is False


def _seed_dock_phase(manager, hass, *, room_id, room_name, is_dock):
    """Seed a 1-phase advanced job targeting room_id + the map's is_dock_room flag,
    with the device already cleaning that room so the verify confirms immediately."""
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.test_current_room", room_name)  # == target
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "rooms": {str(room_id): {"room_id": room_id, "name": room_name,
                                 "is_dock_room": is_dock}}
    }
    slug = room_name.strip().lower().replace(" ", "_")
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [{"resolved_rooms": [{"room_id": room_id, "name": room_name, "slug": slug}],
                    "payload": {"segments": [room_id]}, "room_count": 1}],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": room_id, "name": room_name, "slug": slug}],
        "queue_room_ids": [room_id],
        "current_room_id": room_id,
        "_phase_dispatch_pending": True,
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }


async def test_advanced_phase_extends_settle_for_dock_room(manager, hass, monkeypatch):
    """[SS-22] an advanced (non-initial) phase whose target IS the dock room waits
    _PHASE_DOCK_SETTLE_SECONDS before the first dispatch, so the dock's longer
    ignore-transient passes (vs _PHASE_SETTLE_SECONDS for a normal room, SS-23)."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    sleeps: list[float] = []

    async def _rec(d, *a, **k):
        sleeps.append(d)

    monkeypatch.setattr(_mgr.asyncio, "sleep", AsyncMock(side_effect=_rec))
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 0)  # confirm on first sample
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _register_dispatch(hass)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        _seed_dock_phase(manager, hass, room_id=18, room_name="Dining Room", is_dock=True)
        await manager._run_advanced_phase(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0, initial=False
        )
        await hass.async_block_till_done()
        assert sleeps                                       # the settle ran
        assert sleeps[0] == _mgr._PHASE_DOCK_SETTLE_SECONDS  # extended for the dock room
    finally:
        unregister_adapter_config(_VAC)


async def test_advanced_phase_normal_settle_for_non_dock_room(manager, hass, monkeypatch):
    """[SS-23] an advanced phase whose target is NOT the dock room uses the normal
    _PHASE_SETTLE_SECONDS — the extended settle is dock-room only."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    sleeps: list[float] = []

    async def _rec(d, *a, **k):
        sleeps.append(d)

    monkeypatch.setattr(_mgr.asyncio, "sleep", AsyncMock(side_effect=_rec))
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 0)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _register_dispatch(hass)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        _seed_dock_phase(manager, hass, room_id=27, room_name="Kitchen", is_dock=False)
        await manager._run_advanced_phase(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0, initial=False
        )
        await hass.async_block_till_done()
        assert sleeps
        assert sleeps[0] == _mgr._PHASE_SETTLE_SECONDS      # normal settle, not extended
    finally:
        unregister_adapter_config(_VAC)


def test_phase_timing_merges_adapter_over_defaults(manager):
    """[SS-24] _phase_timing keeps strict-order watchdog timing BRAND-OWNED: an
    adapter's dispatch.phase_timing overrides any subset of the in-core _PHASE_*
    defaults; omitted keys (and no adapter at all) fall back to the defaults."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    # No adapter config -> every value is the in-core default.
    pt = manager._phase_timing(_VAC)
    assert pt["settle_seconds"] == _mgr._PHASE_SETTLE_SECONDS
    assert pt["dock_settle_seconds"] == _mgr._PHASE_DOCK_SETTLE_SECONDS
    assert pt["verify_seconds"] == _mgr._PHASE_VERIFY_SECONDS
    assert pt["confirm_seconds"] == _mgr._PHASE_CONFIRM_SECONDS
    assert pt["poll_seconds"] == _mgr._PHASE_POLL_SECONDS
    assert pt["max_attempts"] == _mgr._PHASE_MAX_ATTEMPTS
    # Adapter overrides a SUBSET -> those win, the rest stay default (brand-owned).
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "dispatch": {"phase_timing": {"dock_settle_seconds": 20, "max_attempts": 5}},
    })
    try:
        pt = manager._phase_timing(_VAC)
        assert pt["dock_settle_seconds"] == 20                      # overridden
        assert pt["max_attempts"] == 5                              # overridden
        assert pt["settle_seconds"] == _mgr._PHASE_SETTLE_SECONDS   # default kept
        assert pt["verify_seconds"] == _mgr._PHASE_VERIFY_SECONDS   # default kept
    finally:
        unregister_adapter_config(_VAC)


async def test_start_selected_rooms_strict_order_arms_watchdog(manager, hass, monkeypatch):
    """[SS-25] start_selected_rooms(strict_order=True) on a path-optimizing brand
    (capabilities.honors_clean_order False) builds a SEQUENCED job — one phase per
    enabled room — and arms the strict-order machinery: sets _phase_dispatch_pending
    and spawns the initial phase-0 watchdog (the entry block in start_selected_rooms).
    This is the only end-to-end exercise of that path; the watchdog tests above all
    seed the job by hand. The device stays docked so the watchdog can't confirm room 0,
    so the guard stays pending — proving BOTH the flag was set and the watchdog ran."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    _instant_phase_dispatch(monkeypatch)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _seed_enabled(manager, count=2)
    hass.states.async_set(_VAC, "docked")          # never goes cleaning -> never confirms
    _register_dispatch(hass)
    # honors_clean_order False -> strict_order is honored and the roborock_segment_clean
    # engine emits one single-segment phase per room (effective_strict path).
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "capabilities": {"honors_clean_order": False},
        "dispatch": {"template": "roborock_segment_clean", "passes_max": 3},
    })
    try:
        result = await manager.start_selected_rooms(
            vacuum_entity_id=_VAC, map_id=_MAP, strict_order=True)
        await hass.async_block_till_done()
        assert result["started"] is True
        job = manager.data["active_jobs"][_VAC][_MAP]
        # sequenced job: one phase per enabled room (>1 -> phases attached)
        assert len(job.get("phases") or []) == 2
        # the watchdog was spawned + the guard set; a docked device never confirmed
        # room 0, so it stays pending instead of finalizing on the parked dock state
        assert job.get("_phase_dispatch_pending") is True
    finally:
        unregister_adapter_config(_VAC)


async def test_advanced_phase_aborts_when_cancelled_during_settle(manager, hass, monkeypatch):
    """[SS-26] _run_advanced_phase: if the job is cancelled (or advances/finalizes)
    DURING the post-dock settle window, the retry-loop guard aborts WITHOUT
    re-dispatching — so a user Cancel Run mid-settle can't trigger a spurious clean
    against an already-stopped job. The settle sleep is exactly where that race lands."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 0)
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 0)
    monkeypatch.setattr(_mgr, "_PHASE_SETTLE_SECONDS", 30)   # non-zero settle window
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    calls = _register_dispatch(hass)

    # The settle sleep is where a Cancel Run lands: flip the job out of 'started'
    # during it, so the post-settle guard sees a job no longer on this phase.
    async def _cancel_during_settle(*_a, **_k):
        manager.data["active_jobs"][_VAC][_MAP]["status"] = "cancelled"

    sleep_mock = AsyncMock(side_effect=_cancel_during_settle)
    monkeypatch.setattr(_mgr.asyncio, "sleep", sleep_mock)

    phase0 = {"resolved_rooms": [{"room_id": 1}], "payload": {"segments": [1]}, "room_count": 1}
    phase1 = {"resolved_rooms": [{"room_id": 2}], "payload": {"segments": [2]}, "room_count": 1}
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [phase0, phase1], "current_phase_index": 1,
        "resolved_rooms": phase1["resolved_rooms"], "payload": phase1["payload"],
        "completed_room_ids": [1], "current_room_id": 2,
        "_phase_dispatch_pending": True,
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }
    # Directly awaited (nothing spawned) -> no async_block_till_done, which would add
    # an incidental asyncio.sleep(0) to the globally-patched mock and skew the count.
    await manager._run_advanced_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_index=1, initial=False)
    # the settle ran (one sleep), then the guard aborted before any dispatch
    assert sleep_mock.await_count == 1
    assert calls == []


async def test_await_phase_started_returns_true_when_job_moved_on(manager, hass, monkeypatch):
    """[SS-27] _await_phase_started: if the job is cancelled / finalized / advanced to
    another phase while the verify poll is running, it returns True ('job moved on,
    nothing to retry') rather than forcing a re-dispatch against a stopped job. This is
    the concurrency seam — a Cancel Run or completion listener can fire between polls."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    sleep_mock = AsyncMock()
    monkeypatch.setattr(_mgr.asyncio, "sleep", sleep_mock)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked")
    # job is no longer 'started' (cancelled mid-run) -> the poll-entry guard fires
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "cancelled",
        "phases": [{"resolved_rooms": [{"room_id": 1}], "payload": {}, "room_count": 1}],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 1}], "current_room_id": 1,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }
    result = await manager._await_phase_started(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0)
    assert result is True               # job moved on -> treated as confirmed
    assert sleep_mock.await_count == 0  # returned before polling, no retry pressure


def test_vacuum_started_cleaning_job_active_fallback(manager, hass):
    """[SS-28] _vacuum_started_cleaning: when the HA vacuum state hasn't flipped to
    'cleaning' yet, the adapter's job_active binary (the device's inCleaning flag)
    being 'on' still confirms a dispatch took — the fallback that stops the watchdog
    re-dispatching a clean the device DID accept (Roborock, whose vacuum entity lags
    the firmware flag). Off -> not started (a re-dispatch would be warranted)."""
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked")          # HA state lags -> not 'cleaning'
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"job_active": "binary_sensor.ivy_cleaning"},
    })
    try:
        hass.states.async_set("binary_sensor.ivy_cleaning", "on")
        assert manager._vacuum_started_cleaning(_VAC) is True
        hass.states.async_set("binary_sensor.ivy_cleaning", "off")
        assert manager._vacuum_started_cleaning(_VAC) is False
    finally:
        unregister_adapter_config(_VAC)


async def test_phase_verify_fast_room_confirms_on_idle_exit(manager, hass, monkeypatch):
    """[SS-29] a small room the device cleans in under confirm_seconds (it starts THIS
    room, cleans briefly, then docks) must be treated as CONFIRMED, not a no-show: the
    idle-budget exit returns True when cleaning-of-target was observed (cleaning_in_target
    > 0). Pre-fix it returned False -> the watchdog re-dispatched an already-cleaned room
    (device ignores it) and the phase stalled forever with _phase_dispatch_pending set."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config, unregister_adapter_config,
    )
    monkeypatch.setattr(_mgr, "_PHASE_VERIFY_SECONDS", 20)    # 4 idle polls @ 5s
    monkeypatch.setattr(_mgr, "_PHASE_CONFIRM_SECONDS", 100)  # never reached (small room)
    monkeypatch.setattr(_mgr, "_PHASE_POLL_SECONDS", 5)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.test_current_room", "Hallway")
    # The device cleans the target for two polls, then docks (finished fast).
    seq = iter([("cleaning", "Hallway"), ("docked", "Dining Room"),
                ("docked", "Dining Room"), ("docked", "Dining Room"), ("docked", "Dining Room")])

    async def _tick(*_a, **_k):
        try:
            st, room = next(seq)
            hass.states.async_set(_VAC, st)
            hass.states.async_set("sensor.test_current_room", room)
        except StopIteration:
            pass

    monkeypatch.setattr(_mgr.asyncio, "sleep", AsyncMock(side_effect=_tick))
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.test_current_room"},
    })
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
            "phases": [{"resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
                        "payload": {"segments": [2]}, "room_count": 1}],
            "current_phase_index": 0,
            "resolved_rooms": [{"room_id": 2, "name": "Hallway", "slug": "hallway"}],
            "queue_room_ids": [2], "current_room_id": 2,
            "has_observed_active_lifecycle": True,
            "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        }
        result = await manager._await_phase_started(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0)
        assert result is True   # cleaned the target (briefly) then docked -> confirmed, not retried
    finally:
        unregister_adapter_config(_VAC)


def test_pause_releases_strict_order_guard(manager):
    """[SS-30] pausing a sequenced job releases _phase_dispatch_pending (and the watchdog
    independently bails on status!=started). Pre-fix the guard stayed set, so after resume
    the completion gate suppressed every advance forever — a permanent stall recoverable
    only by Cancel Run. No-op for atomic jobs (flag never set)."""
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [{"resolved_rooms": [{"room_id": 1}], "payload": {"segments": [1]}, "room_count": 1},
                   {"resolved_rooms": [{"room_id": 2}], "payload": {"segments": [2]}, "room_count": 1}],
        "current_phase_index": 0, "resolved_rooms": [{"room_id": 1}],
        "current_room_id": 1, "_phase_dispatch_pending": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }
    result = manager.active_job.pause_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "paused"
    assert result.get("_phase_dispatch_pending") is False


async def test_watchdog_bails_when_cancel_in_flight(manager, hass, monkeypatch):
    """[SS-31] the per-phase watchdog bails (no re-dispatch) when _cancel_in_flight is set
    — the signal async_cancel sets up front (before status flips) so a cancel can't be
    undone by the watchdog re-sending app_segment_clean during the return-to-base window."""
    import custom_components.eufy_vacuum.core.manager as _mgr
    from unittest.mock import AsyncMock
    _instant_phase_dispatch(monkeypatch)
    monkeypatch.setattr(_mgr.asyncio, "sleep", AsyncMock())
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked")
    calls = _register_dispatch(hass)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [{"resolved_rooms": [{"room_id": 1}], "payload": {"segments": [1]}, "room_count": 1},
                   {"resolved_rooms": [{"room_id": 2}], "payload": {"segments": [2]}, "room_count": 1}],
        "current_phase_index": 1, "resolved_rooms": [{"room_id": 2}], "payload": {"segments": [2]},
        "current_room_id": 2, "_phase_dispatch_pending": True,
        "_cancel_in_flight": True,   # async_cancel set this up front
        "has_observed_active_lifecycle": True,
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }
    await manager._run_advanced_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_index=1, initial=False)
    await hass.async_block_till_done()
    assert calls == []   # cancel in flight -> watchdog bailed before dispatching


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
