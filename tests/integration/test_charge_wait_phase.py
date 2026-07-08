"""Charge-wait phase — native in-queue "charge to X%" (Wave 1).

A charge_wait phase docks the robot and waits until battery >= target before
advancing to the next clean phase. It has NO rooms, so the completion listener
can't advance it — ``phase_runner._run_charge_wait_phase`` owns its lifecycle,
holding ``_phase_dispatch_pending`` (the same guard that stops a between-phase
dock from finalizing) so the intentional charge-dock is never read as a cancel.

[CW-1] a charge_wait phase captures an EMPTY timing (never a phantom room).
[CW-2] advancing INTO a charge_wait phase routes to the charge poller, not the room watchdog.
[CW-3] battery already >= target on entry -> advance immediately (no charge).
[CW-4] below target then reaches it while polling -> advance to the next phase.
[CW-5] never reaches target within the timeout -> finalize like a CANCEL (missed-rooms), not advance.
[CW-6] the unplanned-recharge observer must NOT claim a commanded charge_wait dock.
"""

from __future__ import annotations

import custom_components.eufy_vacuum.jobs.phase_runner as phase_runner_mod

_VAC = "vacuum.ivy"
_MAP = "Main floor"


def _cs(t: str, ct: int, ca: float) -> dict:
    return {"t": t, "cleaning_time": ct, "cleaning_area": ca, "battery": 90}


def _room_phase(rid: int, slug: str) -> dict:
    return {"resolved_rooms": [{"room_id": rid, "slug": slug}], "queue_room_ids": [rid],
            "payload": {}, "room_count": 1}


def _charge_phase(target: int = 95, timeout_min: int = 180) -> dict:
    return {"phase_type": "charge_wait", "target_battery_percent": target,
            "charge_wait_timeout_minutes": timeout_min,
            "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0}


def _seed(manager, job: dict) -> None:
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job


async def _noop_coro():
    return None


async def test_charge_phase_capture_is_empty(hass, manager, monkeypatch):
    """[CW-1] a flat charging slice must NOT segment into a zero-metric phantom room."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
        "current_phase_index": 1,
        "counter_samples": [_cs("2026-01-01T00:04:10Z", 120, 6.0),
                            _cs("2026-01-01T00:04:50Z", 120, 6.0)],  # flat = charging, no cleaning
    }
    _seed(manager, job)
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    assert job["phases"][1]["room_timing"] == []
    assert job["phases"][1].get("_timing_end_t")


def _spy(name: str, calls: dict):
    def _f(**kw):
        calls[name] += 1
        return _noop_coro()
    return _f


async def test_advance_into_charge_phase_spawns_charge_poller(hass, manager, monkeypatch):
    """[CW-2]"""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    calls = {"charge": 0, "room": 0}
    monkeypatch.setattr(manager.phase_runner, "_run_charge_wait_phase", _spy("charge", calls))
    monkeypatch.setattr(manager.phase_runner, "_run_advanced_phase", _spy("room", calls))
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _charge_phase()],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}], "queue_room_ids": [5],
        "counter_samples": [],
    }
    _seed(manager, job)
    assert await manager.phase_runner.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert calls == {"charge": 1, "room": 0}


async def _drive_charge(manager, monkeypatch, *, batteries, target=95, timeout_min=180):
    """Run _run_charge_wait_phase with a scripted battery sequence + no real sleeps."""
    seq = iter(batteries)
    hold = {"b": batteries[-1]}

    def _batt(_hass, _vac):
        try:
            hold["b"] = next(seq)
        except StopIteration:
            pass
        return hold["b"]

    monkeypatch.setattr("custom_components.eufy_vacuum.core.charging.get_battery_level", _batt)

    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(phase_runner_mod.asyncio, "sleep", _no_sleep)

    # Register a no-op return_to_base so the phase's dock command succeeds without a
    # real vacuum platform (ServiceRegistry.async_call is read-only — can't be patched).
    if not manager.hass.services.has_service("vacuum", "return_to_base"):
        manager.hass.services.async_register("vacuum", "return_to_base", lambda call: None)

    counts = {"advance": 0, "cancel": 0}

    async def _adv(**k):
        counts["advance"] += 1

    async def _cancel(**k):
        counts["cancel"] += 1
        return {}

    monkeypatch.setattr(manager.phase_runner, "maybe_advance_phase", _adv)
    monkeypatch.setattr(manager.active_job, "async_cancel_active_job", _cancel)

    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _charge_phase(target, timeout_min),
                   _room_phase(8, "dining")],
        "current_phase_index": 1,
        "resolved_rooms": [], "queue_room_ids": [], "counter_samples": [],
    }
    _seed(manager, job)
    await manager.phase_runner._run_charge_wait_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_index=1
    )
    return counts


async def test_charge_already_at_target_skips(hass, manager, monkeypatch):
    """[CW-3]"""
    assert await _drive_charge(manager, monkeypatch, batteries=[95], target=95) \
        == {"advance": 1, "cancel": 0}


async def test_charge_completes_advances(hass, manager, monkeypatch):
    """[CW-4]"""
    assert await _drive_charge(manager, monkeypatch, batteries=[50, 60, 95], target=95) \
        == {"advance": 1, "cancel": 0}


async def test_charge_timeout_finalizes_like_cancel(hass, manager, monkeypatch):
    """[CW-5]"""
    assert await _drive_charge(manager, monkeypatch, batteries=[50, 50, 50], target=95,
                               timeout_min=0) == {"advance": 0, "cancel": 1}


async def test_recharge_observer_ignores_charge_phase_dock(hass, manager, monkeypatch):
    """[CW-6]"""
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _charge_phase(), _room_phase(8, "dining")],
        "current_phase_index": 1,
    }
    _seed(manager, job)
    out = manager.active_job.update_active_job_recharge_observation(
        vacuum_entity_id=_VAC, map_id=_MAP,
    )
    assert not out.get("observed_mid_job_recharge")
    assert not out.get("pending_mid_job_recharge_return")
