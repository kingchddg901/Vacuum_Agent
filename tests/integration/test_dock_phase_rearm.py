"""Dock-phase re-arm — a charge_wait / wait poller survives pause+resume and HA restart.

A charge_wait / wait phase's ONLY driver is an in-memory asyncio poller task spawned from
``phase_runner.maybe_advance_phase``. Two events drop that task with no re-arm, wedging the run
in 'started' forever:

  * PAUSE+RESUME — ``async_resume_active_job`` flips status back to 'started' but re-arms nothing.
  * HA RESTART — ``async_initialize`` loses the task AND force-clears ``_phase_dispatch_pending``.

``phase_runner.rearm_dock_phase_if_needed`` re-spawns the matching poller (double-spawn guarded)
and re-asserts the dock guard. This module covers the re-arm helper + both call sites.

[RA-1] re-arm spawns the charge poller when the current phase is charge_wait.
[RA-2] re-arm spawns the wait poller when the current phase is wait.
[RA-3] re-arm is a no-op for a room-group phase (its completion path drives it).
[RA-4] re-arm is a no-op for a paused / finalized job (only 'started').
[RA-5] the double-spawn guard: a second re-arm while a poller is live does NOT spawn again.
[RA-6] re-arm re-asserts _phase_dispatch_pending (a restart cleared it) for a dock phase.
[RA-7] async_resume_active_job re-arms a charge_wait phase.
[RA-8] a wait-phase re-arm mid-wait recomputes the deadline from the persisted wait_started_at
       (a restart does not restart the full timer).
"""

from __future__ import annotations

import custom_components.eufy_vacuum.jobs.phase_runner as phase_runner_mod

_VAC = "vacuum.ivy"
_MAP = "Main floor"


def _room_phase(rid: int, slug: str) -> dict:
    return {"resolved_rooms": [{"room_id": rid, "slug": slug}], "queue_room_ids": [rid],
            "payload": {}, "room_count": 1}


def _charge_phase(target: int = 95) -> dict:
    return {"phase_type": "charge_wait", "target_battery_percent": target,
            "charge_wait_timeout_minutes": 180,
            "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0}


def _wait_phase(mins: int = 5) -> dict:
    return {"phase_type": "wait", "wait_minutes": mins,
            "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0}


def _seed(manager, job: dict) -> None:
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job


def _job(manager) -> dict:
    return manager.data["active_jobs"][_VAC][_MAP]


def _capture_spawns(manager, monkeypatch):
    """Record which poller each _spawn_dock_poller would launch, without running it.

    We intercept at hass.async_create_task so the real _spawn_dock_poller guard logic runs
    (it's the thing under test) but the coroutine never executes — closing it avoids a
    'never awaited' warning.
    """
    spawned: list[str] = []

    async def _inert():
        return None

    def _mark(kind):
        # SYNC replacement: _spawn_dock_poller calls this to BUILD the poller coro (it does
        # not await it), so record the spawn here — at build time — and hand back an inert
        # coroutine the async_create_task stub can close without running anything.
        def _f(**kw):
            spawned.append(kind)
            return _inert()
        return _f

    monkeypatch.setattr(manager.phase_runner, "_run_charge_wait_phase", _mark("charge"))
    monkeypatch.setattr(manager.phase_runner, "_run_wait_phase", _mark("wait"))
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())
    return spawned


async def test_rearm_spawns_charge_poller(hass, manager, monkeypatch):
    """[RA-1]"""
    spawned = _capture_spawns(manager, monkeypatch)
    _seed(manager, {
        "status": "started", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), _charge_phase(), _room_phase(8, "dining")],
        "_phase_dispatch_pending": True,
    })
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert spawned == ["charge"]


async def test_rearm_spawns_wait_poller(hass, manager, monkeypatch):
    """[RA-2]"""
    spawned = _capture_spawns(manager, monkeypatch)
    _seed(manager, {
        "status": "started", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), _wait_phase(), _room_phase(8, "dining")],
        "_phase_dispatch_pending": True,
    })
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert spawned == ["wait"]


async def test_rearm_noop_for_room_phase(hass, manager, monkeypatch):
    """[RA-3] a room-group phase is driven by its completion path — nothing to re-arm."""
    spawned = _capture_spawns(manager, monkeypatch)
    _seed(manager, {
        "status": "started", "current_phase_index": 0,
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
        "_phase_dispatch_pending": True,
    })
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is False
    assert spawned == []


async def test_rearm_noop_for_paused_job(hass, manager, monkeypatch):
    """[RA-4] only a 'started' job re-arms; a paused (or finalized) one is left alone."""
    spawned = _capture_spawns(manager, monkeypatch)
    _seed(manager, {
        "status": "paused", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
    })
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is False
    assert spawned == []


async def test_rearm_double_spawn_guarded(hass, manager, monkeypatch):
    """[RA-5] a live poller holds the guard, so a concurrent re-arm does NOT spawn again."""
    spawned = _capture_spawns(manager, monkeypatch)
    _seed(manager, {
        "status": "started", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
        "_phase_dispatch_pending": True,
    })
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is True
    # The first spawn set the guard and (in the intercept) the coro was closed WITHOUT running
    # its finally, so the guard is still held — a second re-arm must be a no-op.
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is False
    assert spawned == ["charge"]  # only one


async def test_rearm_reasserts_dispatch_guard(hass, manager, monkeypatch):
    """[RA-6] an HA restart cleared _phase_dispatch_pending; re-arm restores it so the
    intentional dock the poller is about to drive isn't finalized by the completion gate."""
    _capture_spawns(manager, monkeypatch)
    _seed(manager, {
        "status": "started", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
        "_phase_dispatch_pending": False,   # restart force-cleared it
    })
    assert manager.phase_runner.rearm_dock_phase_if_needed(
        vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert _job(manager)["_phase_dispatch_pending"] is True


async def test_resume_rearms_charge_phase(hass, manager, monkeypatch):
    """[RA-7] async_resume_active_job re-arms the poller after status flips to 'started'."""
    spawned = _capture_spawns(manager, monkeypatch)
    # A no-op vacuum.start so resume's service call succeeds without a real platform.
    if not manager.hass.services.has_service("vacuum", "start"):
        manager.hass.services.async_register("vacuum", "start", lambda call: None)
    _seed(manager, {
        "status": "paused", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
        # pause cleared the guard; resume re-arm re-asserts it.
        "_phase_dispatch_pending": False,
    })
    out = await manager.active_job.async_resume_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["resumed"] is True
    assert spawned == ["charge"]
    assert _job(manager)["_phase_dispatch_pending"] is True


async def test_wait_rearm_recomputes_deadline_from_started_at(hass, manager, monkeypatch):
    """[RA-8] a wait phase re-armed mid-wait recomputes the remaining window from the
    PERSISTED wait_started_at — a restart 4 min into a 5-min wait leaves ~1 min, it does
    NOT restart the full 5. A single poll that jumps 65s crosses the recomputed ~60s
    remaining and advances; had the timer restarted from a full 300s it would not have."""
    # Frozen now = 240s after the persisted wait_started_at (300s - 240s = 60s remaining).
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:04:00Z")

    clock = {"t": 1000.0}
    monkeypatch.setattr(manager.hass.loop, "time", lambda: clock["t"])

    if not manager.hass.services.has_service("vacuum", "return_to_base"):
        manager.hass.services.async_register("vacuum", "return_to_base", lambda call: None)

    advanced = {"n": 0}

    async def _adv(**k):
        advanced["n"] += 1

    monkeypatch.setattr(manager.phase_runner, "maybe_advance_phase", _adv)

    # A wait phase already 240s in (persisted wait_started_at) with a 5-min window.
    phase = _wait_phase(5)
    phase["wait_started_at"] = "2026-01-01T00:00:00Z"   # 240s before frozen now
    _seed(manager, {
        "status": "started", "current_phase_index": 1,
        "phases": [_room_phase(5, "kitchen"), phase, _room_phase(8, "dining")],
        "_phase_dispatch_pending": True, "counter_samples": [],
        "resolved_rooms": [], "queue_room_ids": [],
    })

    # No real sleeping: each poll jumps the clock 65s and is counted. Remaining is ~60s
    # (300 - 240), so exactly ONE poll crosses the recomputed deadline. Had the timer
    # restarted from a full 300s it would have taken FIVE polls — the poll COUNT is what
    # proves the deadline was recomputed from the persisted start, not reset to full.
    polls = {"n": 0}

    async def _no_sleep(_s):
        polls["n"] += 1
        clock["t"] += 65.0

    monkeypatch.setattr(phase_runner_mod.asyncio, "sleep", _no_sleep)

    await manager.phase_runner._run_wait_phase(vacuum_entity_id=_VAC, map_id=_MAP, phase_index=1)
    assert advanced["n"] == 1
    assert polls["n"] == 1   # 60s remaining / 65s per poll = 1 poll; a full 300s reset = 5
    # wait_started_at was NOT overwritten (kept the original for the deadline recompute).
    assert _job(manager)["phases"][1]["wait_started_at"] == "2026-01-01T00:00:00Z"
