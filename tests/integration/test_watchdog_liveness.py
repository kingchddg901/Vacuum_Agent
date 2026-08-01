"""RP-011/RF-07 — watchdog wedges resolved; the reaper reaches every dead state.

Covers the pieces the pure-predicate tests in test_jobs_job_monitor.py (JM-42..47)
can't reach on their own: the watchdog actually marking itself dead, the phase
timing clamps, the dock_status mid-run consultation, the WD-3 has_native gate's
coarse-fallback branch, and the reaper's single-flight tick guard.

[WL-1] a crashed watchdog attempt logs ERROR and marks the phase dead+stamped
       (reapable), rather than dying silently and invisibly.
[WL-2] _phase_timing clamps a nonsensical adapter override and warns naming the key.
[WL-3] poll_stranded_started_job does NOT reap a dock service cycle (mop wash) --
       dock_status is consulted, not just fetched and discarded.
[WL-4] poll_stranded_started_job DOES reap a genuinely stranded run whose
       dock_status is not in the adapter's blocked set (control case).
[WL-5] _await_phase_started's has_native gate is False (coarse fallback reachable)
       for an adapter that declares active_cleaning_target but not
       native_transition_source=True (the Eufy shape).
[WL-6] the reaper tick guard: a second tick firing while the first _process is
       still running is skipped, not run concurrently.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    register_adapter_config,
    unregister_adapter_config,
)

_VAC = "vacuum.alfred"
_MAP = "6"


def _room_phase(room_ids: list[int]) -> dict:
    return {
        "phase_type": "room_group",
        "queue_room_ids": list(room_ids),
        "resolved_rooms": [{"room_id": r, "slug": f"room_{r}"} for r in room_ids],
        "payload": {"segments": list(room_ids), "repeat": 1},
    }


def _seed_phased_job(manager, **extra) -> dict:
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        "queue_room_ids": [1],
        "phases": [_room_phase([1])],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 1, "slug": "room_1"}],
        "payload": {"segments": [1], "repeat": 1},
    }
    job.update(extra)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


# ---------------------------------------------------------------------------
# [WL-1] a crashed watchdog is diagnosable and reapable, not silently dead
# ---------------------------------------------------------------------------

async def test_crashed_watchdog_logs_error_and_marks_dead(manager, monkeypatch, caplog):
    _seed_phased_job(manager)

    async def _boom(**kw):
        raise RuntimeError("collaborator exploded")

    monkeypatch.setattr(manager, "_run_global_pre_calls", _boom)

    with caplog.at_level(logging.ERROR):
        await manager.phase_runner._run_advanced_phase(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0, initial=False,
        )

    stored = manager.data["active_jobs"][_VAC][_MAP]
    assert stored.get("_phase_watchdog_dead") is True
    assert stored.get("_phase_dispatch_pending_since")
    assert any("watchdog crashed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# [WL-2] _phase_timing clamps nonsensical adapter overrides
# ---------------------------------------------------------------------------

async def test_phase_timing_clamps_bad_adapter_overrides(manager, caplog):
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "dispatch": {"phase_timing": {
            "poll_seconds": 0, "max_attempts": 0, "verify_seconds": -5,
        }},
    })
    try:
        with caplog.at_level(logging.WARNING):
            pt = manager._phase_timing(_VAC)
        assert pt["poll_seconds"] >= 1
        assert pt["max_attempts"] >= 1
        assert pt["verify_seconds"] >= 0
        warned_keys = {
            r.args[1] for r in caplog.records
            if "_phase_timing" in r.message and len(r.args) >= 2
        }
        assert {"poll_seconds", "max_attempts", "verify_seconds"} <= warned_keys
    finally:
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# [WL-3/4] STR-1: dock_status consulted against blocked_dock_status_states
# ---------------------------------------------------------------------------

_DOCK_ADAPTER = {
    "adapter_id": "t", "source": "t",
    "entities": {
        "task_status": "sensor.alfred_task",
        "dock_status": "sensor.alfred_dock",
        "active_cleaning_target": "sensor.alfred_target",
    },
    "vocabulary": {"blocked_dock_status_states": ["Washing", "Recycling waste water"]},
}


async def test_stranded_poll_skips_mid_service_dock(manager, hass):
    """[WL-3] a mop-wash dock cycle reads docked+ended-looking exactly like a
    genuine strand -- STR-1 must not reap it."""
    register_adapter_config(_VAC, _DOCK_ADAPTER)
    try:
        _seed_phased_job(manager, has_observed_active_lifecycle=True)
        manager.data["active_jobs"][_VAC][_MAP].pop("phases", None)
        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "charging")
        hass.states.async_set("sensor.alfred_dock", "Washing")
        hass.states.async_set("sensor.alfred_target", "")

        report = manager.poll_stranded_started_job(vacuum_entity_id=_VAC, map_id=_MAP)
        assert report is None
    finally:
        unregister_adapter_config(_VAC)


async def test_stranded_poll_reaps_when_dock_not_mid_service(manager, hass):
    """[WL-4] control: the SAME shape but dock_status outside the blocked set is
    a genuine strand -- STR-1 must not become a blanket new exclusion."""
    register_adapter_config(_VAC, _DOCK_ADAPTER)
    try:
        _seed_phased_job(manager, has_observed_active_lifecycle=True)
        manager.data["active_jobs"][_VAC][_MAP].pop("phases", None)
        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "charging")
        hass.states.async_set("sensor.alfred_dock", "idle")
        hass.states.async_set("sensor.alfred_target", "")

        # First tick stamps stranded_since; the report only fires past the grace.
        assert manager.poll_stranded_started_job(vacuum_entity_id=_VAC, map_id=_MAP) is None
        stamped = manager.data["active_jobs"][_VAC][_MAP]["stranded_since"]
        import datetime
        later = (
            datetime.datetime.fromisoformat(stamped.replace("Z", "+00:00"))
            + datetime.timedelta(minutes=20)
        ).isoformat()
        report = manager.poll_stranded_started_job(
            vacuum_entity_id=_VAC, map_id=_MAP, now=later,
        )
        assert isinstance(report, dict)
    finally:
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# [WL-5] WD-3: has_native gate — coarse fallback reachable for a
# declared-but-not-native adapter (the Eufy shape)
# ---------------------------------------------------------------------------

async def test_await_phase_started_coarse_fallback_for_non_native_adapter(manager, hass, monkeypatch):
    """[WL-5] an adapter that DECLARES active_cleaning_target but leaves
    native_transition_source unset/False (Eufy's own declaration) must route
    through the coarse vacuum.state==cleaning fallback, confirming on the FIRST
    poll regardless of room -- not the strong native per-room path."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_cleaning_target": "sensor.alfred_target"},
        # No live_transition block at all -- native_transition_source defaults False.
    })
    try:
        job = _seed_phased_job(manager, current_room_id=1)
        hass.states.async_set(_VAC, "cleaning")

        async def _no_sleep(*a, **kw):
            return None
        monkeypatch.setattr(asyncio, "sleep", _no_sleep)

        confirmed = await manager.phase_runner._await_phase_started(
            vacuum_entity_id=_VAC, map_id=_MAP, phase_index=0,
        )
        assert confirmed is True  # coarse fallback: state==cleaning alone confirms
    finally:
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# [WL-6] GUARD-4: single concurrent reaper tick
# ---------------------------------------------------------------------------

async def test_reaper_tick_does_not_overlap(hass, manager, monkeypatch):
    """[WL-6] a second tick firing while the first _process is still running
    must be skipped, not run concurrently over the same slots."""
    from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
    from custom_components.eufy_vacuum.listeners import pause_timeout

    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    _seed_phased_job(manager)  # so get_known_vacuum_ids/map_ids find one slot

    entered = asyncio.Event()
    release = asyncio.Event()
    call_count = {"n": 0}

    real_get_known_vacuum_ids = manager.get_known_vacuum_ids

    def _tracking_get_known_vacuum_ids():
        call_count["n"] += 1
        return real_get_known_vacuum_ids()

    def _timeout_report(**kw):
        # get_paused_job_timeout_report is SYNC (not awaited) -- returning a real
        # dict here routes the block into async_cancel_active_job below, the
        # actually-awaited call.
        return {
            "forced_lifecycle_state": "x", "forced_lifecycle_message": "x",
            "cancel_reason": "x", "pause_timeout_minutes": 30,
        }

    async def _blocking_cancel(**kw):
        entered.set()
        await release.wait()
        return {"cancelled": False}

    monkeypatch.setattr(manager, "get_known_vacuum_ids", _tracking_get_known_vacuum_ids)
    monkeypatch.setattr(manager, "get_paused_job_timeout_report", _timeout_report)
    monkeypatch.setattr(manager, "async_cancel_active_job", _blocking_cancel)
    monkeypatch.setattr(manager, "poll_stranded_started_job", lambda **kw: None)

    captured: list = []

    def _capture(hass_arg, handler, interval):
        captured.append(handler)
        return lambda: None

    original = pause_timeout.async_track_time_interval
    pause_timeout.async_track_time_interval = _capture
    try:
        pause_timeout.register(hass)
    finally:
        pause_timeout.async_track_time_interval = original

    assert captured

    captured[0](None)   # first tick: enters _process, blocks in async_cancel_active_job
    await asyncio.wait_for(entered.wait(), timeout=5)
    captured[0](None)   # second tick: must be skipped (in_flight)

    await asyncio.sleep(0)
    assert call_count["n"] == 1, "a second tick ran concurrently with the first"

    release.set()
    await asyncio.sleep(0)
    pause_timeout.remove(hass)
