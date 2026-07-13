"""Zone phase — clean a saved zone (or several) as a step in a phased run (Wave: zone step).

A zone is a CLEAN action, not a pause: it dispatches saved-zone rects via
``dispatch_zone_clean`` and completes like a room group (the external completion hook
advances it — completion is dock/clean-complete-signal driven, not room-counter gated),
unlike a charge_wait/wait which a dock poller drives.

[ZN-1] _build_steps_phases: a zone step -> a zone phase interleaved between room groups.
[ZN-2] a rooms+zone run with NO charge/wait stays MULTI-phase (never collapses to one atomic clean).
[ZN-3] a zone whose ids resolve to no geometry is dropped (like an empty room_group).
[ZN-4] advancing INTO a zone phase routes to the room watchdog, NOT the dock poller.
[ZN-5] _dispatch_active_phase on a zone phase fires dispatch_zone_clean with the rects (no segment payload).
[ZN-6] a completed zone phase advances to the next phase (participates in the normal cycle).
[ZN-7] a zone phase confirms via state==cleaning (no target room) -> guard clears -> can finalize.
[ZN-8] a zone that never starts (no-show) returns False so the watchdog re-dispatches.
[ZN-11] _capture_finishing_phase_timing on a zone phase records zone_timing (wall from the phase
        boundary, mode from has_mop_mode, area from the saved zone) + EMPTY room_timing.
[ZN-12] the completed-job recorder folds a single-zone observation into map_bucket['learned_zones'];
        a cancelled outcome records nothing (a partial zone must not under-count the average).
"""

from __future__ import annotations

import custom_components.eufy_vacuum.jobs.phase_runner as phase_runner_mod
import custom_components.eufy_vacuum.jobs.active_job as active_job_mod
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
from custom_components.eufy_vacuum.learning.manager import LearningManager

_VAC = "vacuum.ivy"
_MAP = "Main floor"


def _room_phase(rid: int, slug: str) -> dict:
    return {"resolved_rooms": [{"room_id": rid, "slug": slug}], "queue_room_ids": [rid],
            "payload": {}, "room_count": 1}


def _zone_phase(zone_ids=("z_a",), zones=None) -> dict:
    return {"phase_type": "zone", "zone_ids": list(zone_ids),
            "zones": zones if zones is not None else [[0.1, 0.1, 0.2, 0.2]],
            "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0}


def _rg(*ids):
    return {"type": "room_group", "rooms": [{"room_id": i} for i in ids]}


def _zn(*zone_ids):
    return {"type": "zone", "zone_ids": list(zone_ids)}


def _seed(manager, job: dict) -> None:
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job


async def _noop_coro():
    return None


def _spy(name: str, calls: dict):
    def _f(**kw):
        calls[name] += 1
        return _noop_coro()
    return _f


def _steps_phases(manager, monkeypatch, run_steps, included, *, resolves=True):
    """Materialize steps -> phases with the brand engine + zone resolver faked, so we test
    the interleave/collapse logic. resolves=False -> the zone resolver finds no geometry."""
    monkeypatch.setattr(
        manager.run_plan, "_build_dispatch_phases",
        lambda **kw: [{"ids": list(kw["queue_room_ids"]), "queue_room_ids": list(kw["queue_room_ids"])}],
    )

    def _resolve(**kw):
        return [] if not resolves else [[0.1, 0.1, 0.2, 0.2] for _ in kw["zone_ids"]]

    monkeypatch.setattr(manager, "_resolve_saved_zone_rects", _resolve)
    return manager.run_plan._build_steps_phases(
        vacuum_entity_id=_VAC, map_id=_MAP, effective_rooms={}, included_room_ids=set(included),
        run_steps=run_steps, strict_order=False,
    )


async def test_zone_step_interleaves(hass, manager, monkeypatch):
    """[ZN-1] a zone step becomes a zone phase between the room groups, one rect per id."""
    phases = _steps_phases(manager, monkeypatch, [_rg(1, 2), _zn("z_a", "z_b"), _rg(3)], included={1, 2, 3})
    assert phases[0]["ids"] == [1, 2]
    assert phases[1]["phase_type"] == "zone"
    assert phases[1]["zone_ids"] == ["z_a", "z_b"]
    assert len(phases[1]["zones"]) == 2
    assert phases[2]["ids"] == [3]


async def test_rooms_plus_zone_stays_multiphase(hass, manager, monkeypatch):
    """[ZN-2] no charge/wait, but a zone still forces multi-phase (else the zone would be lost)."""
    phases = _steps_phases(manager, monkeypatch, [_rg(1), _zn("z_a"), _rg(2)], included={1, 2})
    assert [p.get("phase_type", "room") for p in phases] == ["room", "zone", "room"]


async def test_zone_no_geometry_dropped(hass, manager, monkeypatch):
    """[ZN-3] a zone that resolves to nothing is skipped; with no zone/break left, collapses to atomic."""
    phases = _steps_phases(manager, monkeypatch, [_rg(1), _zn("z_missing"), _rg(2)],
                           included={1, 2}, resolves=False)
    assert all(p.get("phase_type") != "zone" for p in phases)
    assert phases[0]["ids"] == [1, 2]  # rooms folded into one atomic clean


async def test_advance_into_zone_spawns_room_watchdog(hass, manager, monkeypatch):
    """[ZN-4] a zone is a clean phase -> the room watchdog, not the charge/wait dock poller."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    calls = {"charge": 0, "room": 0}
    monkeypatch.setattr(manager.phase_runner, "_run_charge_wait_phase", _spy("charge", calls))
    monkeypatch.setattr(manager.phase_runner, "_run_advanced_phase", _spy("room", calls))
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase()],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}], "queue_room_ids": [5],
        "counter_samples": [],
    }
    _seed(manager, job)
    assert await manager.phase_runner.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert calls == {"charge": 0, "room": 1}


async def test_zone_phase_dispatches_via_zone_clean(hass, manager, monkeypatch):
    """[ZN-5] dispatching a zone phase fires dispatch_zone_clean with the phase's rects and
    sends NO room/segment payload."""
    calls = {"zone": None, "room": 0}

    async def _zone_clean(**kw):
        calls["zone"] = kw.get("zones")
        return {"ok": True}

    async def _room_dispatch(**kw):
        calls["room"] += 1

    monkeypatch.setattr(manager, "dispatch_zone_clean", _zone_clean)
    monkeypatch.setattr(manager, "_dispatch_clean_payload", _room_dispatch)
    rects = [[0.1, 0.1, 0.3, 0.3], [0.5, 0.5, 0.7, 0.7]]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase(("z_a", "z_b"), rects)],
        "current_phase_index": 1, "phase_count": 2,
        "resolved_rooms": [], "queue_room_ids": [],
    }
    _seed(manager, job)
    await manager.phase_runner._dispatch_active_phase(vacuum_entity_id=_VAC, map_id=_MAP, job=job)
    assert calls["zone"] == rects
    assert calls["room"] == 0


async def test_zone_phase_completes_and_advances(hass, manager, monkeypatch):
    """[ZN-6] a completed zone advances to the next phase (the external completion hook drives
    it exactly like a room group), re-dispatching the following room via the watchdog."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    calls = {"charge": 0, "room": 0}
    monkeypatch.setattr(manager.phase_runner, "_run_charge_wait_phase", _spy("charge", calls))
    monkeypatch.setattr(manager.phase_runner, "_run_advanced_phase", _spy("room", calls))
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase(), _room_phase(8, "dining")],
        "current_phase_index": 1,
        "resolved_rooms": [], "queue_room_ids": [], "counter_samples": [],
    }
    _seed(manager, job)
    assert await manager.phase_runner.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert manager.data["active_jobs"][_VAC][_MAP]["current_phase_index"] == 2
    assert calls == {"charge": 0, "room": 1}  # advanced into the next ROOM phase via the watchdog


_FAST_TIMING = {
    "settle_seconds": 0, "dock_settle_seconds": 0, "verify_seconds": 3,
    "confirm_seconds": 0.1, "poll_seconds": 1, "max_attempts": 3,
}


async def _drive_zone_await(manager, monkeypatch, *, cleaning: bool) -> bool:
    """Run _await_phase_started for a zone phase (phase 1) with the vacuum cleaning or not."""
    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(phase_runner_mod.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(manager, "_phase_timing", lambda _v: dict(_FAST_TIMING))
    manager.hass.states.async_set(_VAC, "cleaning" if cleaning else "docked", {})
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase()],
        "current_phase_index": 1,
    }
    _seed(manager, job)
    return await manager.phase_runner._await_phase_started(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_index=1
    )


async def test_zone_await_confirms_on_cleaning(hass, manager, monkeypatch):
    """[ZN-7] a zone (no target room) confirms via sustained state==cleaning, so the
    dispatch-pending guard clears and the completed job can finalize (not lock active)."""
    assert await _drive_zone_await(manager, monkeypatch, cleaning=True) is True


async def test_zone_await_no_show_retries(hass, manager, monkeypatch):
    """[ZN-8] a zone that never starts cleaning returns False -> the watchdog re-dispatches."""
    assert await _drive_zone_await(manager, monkeypatch, cleaning=False) is False


async def test_zone_ending_job_clears_via_mark_finalized(hass, manager, monkeypatch):
    """[ZN-9] a run ENDING on a zone clears via the listener's UNCONDITIONAL
    mark_active_job_finalized (the finalizer is learning-only + doesn't touch active_jobs; the
    listener owns the clear). Once the guard clears (ZN-7), the completion reaches this and the
    job ends -- it is NOT room-specific, so a zone-ending job clears exactly like a room one."""
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "started_at": "2026-01-01T00:00:00Z", "battery_start": 90,
        "phases": [_room_phase(5, "kitchen"), _zone_phase()],
        "current_phase_index": 1,  # sitting on the ZONE (last) phase
        "resolved_rooms": [], "queue_room_ids": [], "counter_samples": [],
    }
    _seed(manager, job)
    manager.mark_active_job_finalized(
        vacuum_entity_id=_VAC, map_id=_MAP, finalize_result=None,
    )
    remaining = manager.data.get("active_jobs", {}).get(_VAC, {}).get(_MAP)
    assert not remaining or str(remaining.get("status")) != "started", (
        f"zone-ending job did not clear: {remaining}"
    )


async def test_cancel_clears_even_if_finalize_raises(hass, manager, monkeypatch):
    """[ZN-10] Cancel Run must ALWAYS clear the active job -- even if the learning-only
    finalizer raises on a zone-ending run. Before the guard, an unguarded finalize killed the
    cancel before the clear, stranding the job 'started' (Dev Tools only, exactly the hardware
    failure)."""
    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(active_job_mod.asyncio, "sleep", _no_sleep)

    async def _boom(**kw):
        raise RuntimeError("finalizer can't attribute a zone")

    monkeypatch.setattr(manager, "finalize_learning_for_active_job", _boom)
    hass.states.async_set(_VAC, "docked", {})
    if not manager.hass.services.has_service("vacuum", "return_to_base"):
        manager.hass.services.async_register("vacuum", "return_to_base", lambda call: None)
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "started_at": "2026-01-01T00:00:00Z", "battery_start": 90,
        "phases": [_room_phase(5, "kitchen"), _zone_phase()],
        "current_phase_index": 1,
        "resolved_rooms": [], "queue_room_ids": [],
    }
    _seed(manager, job)
    res = await manager.active_job.async_cancel_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP,
    )
    assert res["cancelled"] is True
    remaining = manager.data.get("active_jobs", {}).get(_VAC, {}).get(_MAP)
    assert not remaining or str(remaining.get("status")) != "started", (
        f"cancel left the job stranded: {remaining}"
    )


def _seed_saved_zone_area(manager, zid="z_a", area=0.5):
    mb = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    mb.setdefault("saved_zones", {})[zid] = {"id": zid, "name": "stove", "area_m2": area}
    return mb


async def test_capture_zone_phase_timing(hass, manager, monkeypatch):
    """[ZN-11] a finishing zone phase gets a zone_timing snapshot: wall = the previous phase's
    end -> now (mop-prep included), mode from the job's has_mop_mode, area from the saved zone;
    room_timing is empty so the finalizer's room path never misfiles it as a phantom room."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:06:30Z")
    _seed_saved_zone_area(manager, "z_a", area=0.5)
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z",
        "job_metadata": {"has_mop_mode": True},
        "phases": [
            {**_room_phase(5, "kitchen"), "_timing_end_t": "2026-01-01T00:02:00Z"},
            _zone_phase(zone_ids=("z_a",)),
        ],
        "current_phase_index": 1,
    }
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    zt = job["phases"][1]["zone_timing"]
    assert zt["zone_ids"] == ["z_a"]
    assert zt["clean_mode"] == "mop"
    assert zt["wall_seconds"] == 270          # 00:02:00 -> 00:06:30
    assert zt["area_m2"] == 0.5
    assert job["phases"][1]["room_timing"] == []


async def test_zone_recorder_learns_only_on_completed(hass, manager):
    """[ZN-12] the completed-job recorder folds a single-zone observation into learned_zones;
    a cancelled outcome records nothing (a mid-zone Cancel is a likely partial)."""
    lm = LearningManager(hass)
    _seed_saved_zone_area(manager, "z_a", area=0.5)
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "phases": [
            _room_phase(5, "kitchen"),
            {**_zone_phase(zone_ids=("z_a",)),
             "zone_timing": {"zone_ids": ["z_a"], "clean_mode": "mop",
                             "wall_seconds": 270, "area_m2": 0.5}},
        ],
    }

    # Cancelled -> no learning.
    await lm._record_zone_learning(
        manager, vacuum_entity_id=_VAC, map_id=_MAP,
        active_job_state=job, outcome_status="cancelled",
    )
    mb = manager.data["maps"][_VAC][_MAP]
    assert not mb.get("learned_zones")

    # Completed -> the observation lands.
    await lm._record_zone_learning(
        manager, vacuum_entity_id=_VAC, map_id=_MAP,
        active_job_state=job, outcome_status="completed",
    )
    bucket = manager.data["maps"][_VAC][_MAP]["learned_zones"]["z_a"]["mop"]
    assert bucket["sample_count"] == 1 and bucket["avg_wall_seconds"] == 270
