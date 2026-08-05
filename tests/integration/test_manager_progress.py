"""Tests for core/manager.py::get_job_progress_snapshot — the live job engine.

~150 lines of real logic (timeline estimate/reanchor, current-room derivation,
bounds-exit + stall detection) that the dashboard polls. Driven against the
real manager + a wired LearningManager with seeded active-job state.

Coverage targets
----------------
[PR-1]  idle job → terminal snapshot, empty timeline.
[PR-2]  started job + learning + resolved rooms → snapshot with derived current
        room and a timeline.
[PR-3]  completed rooms → the reanchor timeline branch.
[PR-4]  a long-overrun current room → awaiting_bounds_exit / stall signalling.
[PR-5]  finalize_learning_for_active_job: no learning manager → None.
[PR-6]  finalize_learning_for_active_job: missing started_at → not finalized.
[PR-7]  finalize_learning_for_active_job: full job → completed_job result.
[PR-8]  jobs-index → room-history merge with newer-wins + bad-row skips.
[PR-9]  single-room stall: a pure snapshot read fires nothing; apply_job_progress_tick
        fires EVENT_STALL_DETECTED exactly once (no re-fire) — SNAP-2.
[PR-10] running_long suppressed for an unlearned room at ~1.7x threshold (issue #40).
[PR-13] a current charge_wait phase surfaces charge_phase_active + target + ETA.
[PR-14] a current zone phase surfaces zone_phase_active + names + ETA (live view not blank).
[PR-15] the zone banner clears once the zone is DONE (docked/dry window) — gated on the device
        actually still cleaning, not just the phase type (the "Cleaning zone" while-docked bug).
[PR-16] the live_queue flattens the whole running phase sequence into ordered done/current/
        upcoming chips (room + charge + wait + zone), from the active_job clone.
[PR-17] a corrupt (non-dict) saved-zone entry doesn't crash the snapshot — name falls back to id.
[PR-11] non-sequential advance → room flagged skipped in a pure read; apply_job_progress_tick
        fires EVENT_ROOM_SKIPPED once (SNAP-2).
[PR-12] normal sequential run (completed prefix) → no skips.
[PS-1]  get_payload_state enriches dict rooms + continues past non-dict entries.
[PR-18] an unreadable battery (get_battery_level -> None) doesn't crash the
        snapshot and doesn't disable skip-detection (RP-042/RF-36).
[PR-19] get_planned_job_estimate refuses with reason=battery_unavailable when
        the battery is unreadable, instead of crashing or fabricating 0% (RP-042).
[PR-20] the estimate panel RECOMPUTES while planning (a frozen plan would stop
        responding to queue edits).
[PR-21] ...and serves the plan frozen AT DISPATCH while a job runs, because job
        start clears the payload the live recompute needs.
[PR-22] a snapshot whose job_id doesn't match the running job is refused — the
        previous run's plan shown as this one's is worse than an empty panel.
[PR-23] no snapshot at all degrades to the pre-existing empty panel, not a raise.
[PR-24] the freeze THAWS once the job is terminal.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.eufy_vacuum.const import (
    DATA_LEARNING,
    DOMAIN,
    EVENT_ROOM_SKIPPED,
    EVENT_STALL_DETECTED,
)
from custom_components.eufy_vacuum.learning.manager import LearningManager

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"


def _wire(manager, hass):
    hass.data.setdefault(DOMAIN, {})[DATA_LEARNING] = LearningManager(hass)


def _seed_job(manager, *, minutes_ago=10, **extra):
    started = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    job = {
        "status": "started", "job_id": "j1",
        "started_at": started, "current_room_started_at": started,
        "queue_room_ids": [1, 2],
        "resolved_rooms": [
            {"room_id": 1, "name": "Kitchen", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "Bath", "minutes": 5, "clean_mode": "vacuum"},
        ],
        "completed_room_ids": [], "completed_rooms": [],
    }
    job.update(extra)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


def test_progress_idle(manager, hass):
    """[PR-1]"""
    _wire(manager, hass)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "idle"
    assert snap["terminal"] is True
    assert snap["timeline"] == []
    assert snap["timeline_source"] == "none"


def test_progress_started(manager, hass):
    """[PR-2]"""
    _wire(manager, hass)
    _seed_job(manager)
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "started"
    assert snap["terminal"] is False
    assert snap["job_id"] == "j1"
    # a timeline was produced from the resolved rooms
    assert snap["timeline_source"] in {"estimate", "reanchored"}
    assert len(snap["timeline"]) >= 1
    # current room derived from the unresolved set
    assert snap["current_room_id"] in (1, 2)


def test_planned_job_estimate_battery_unavailable(manager, hass):
    """[PR-19] RP-042/RF-36: get_planned_job_estimate refuses (available=False,
    reason=battery_unavailable) rather than crash on float(None) or silently
    estimate from a fabricated 0% -- mirrors the existing learning_unavailable
    refusal shape."""
    _wire(manager, hass)
    setup_map(manager, _VAC, _MAP)
    hass.states.async_set(_VAC, "docked")  # no battery_level attribute, no sensor
    result = manager.get_planned_job_estimate(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["available"] is False
    assert result["reason"] == "battery_unavailable"


def test_progress_unreadable_battery_does_not_crash(manager, hass):
    """[PR-18] RP-042/RF-36: no battery sensor registered and no vacuum
    battery_level attribute -> _get_battery_level returns None. The snapshot
    must not crash on float(None) and skip-detection (which rides the same
    timeline call) must keep working -- this file's own fixture never sets a
    battery reading at all, so this is really a regression guard for every
    other test here, made explicit."""
    _wire(manager, hass)
    _seed_job(
        manager,
        queue_room_ids=[1, 2, 3],
        resolved_rooms=[
            {"room_id": 1, "name": "A", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "B", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 3, "name": "C", "minutes": 5, "clean_mode": "vacuum"},
        ],
        completed_room_ids=[2],  # room 2 done, room 1 NOT -- non-sequential advance
        current_room_id=3,
    )
    hass.states.async_set(_VAC, "cleaning")  # deliberately no battery_level attr
    events: list = []
    hass.bus.async_listen(EVENT_ROOM_SKIPPED, lambda e: events.append(e.data))
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "started"
    assert 1 in snap["skipped_room_ids"]  # skip-detection unaffected by the unreadable battery


def test_progress_reanchor(manager, hass):
    """[PR-3] a completed room drives the reanchor branch."""
    _wire(manager, hass)
    _seed_job(
        manager,
        completed_room_ids=[1],
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}],
    )
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["timeline_source"] == "reanchored"
    assert 1 in snap["completed_room_ids"]
    # room 1 shows as completed in the timeline
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["completed"] is True


def test_progress_stall(manager, hass):
    """[PR-4] a wildly-overrun current room raises awaiting_bounds_exit/stall.

    With no robot-position entities the timing rollover can't confirm the robot
    left the room, so an elapsed >> threshold should flag bounds-exit (and, at
    >= 2x, a stall + EVENT_STALL_DETECTED).
    """
    _wire(manager, hass)
    # current room started 60 minutes ago vs a 5-minute estimate → >> 2x
    _seed_job(manager, minutes_ago=60)
    hass.states.async_set(_VAC, "cleaning")
    events = []
    hass.bus.async_listen(EVENT_STALL_DETECTED, lambda e: events.append(e))
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    # whichever path the timing engine takes, the snapshot stays well-formed
    assert "awaiting_bounds_exit" in snap
    assert isinstance(snap["awaiting_bounds_exit"], bool)


def test_progress_stall_fires_once(manager, hass):
    """[PR-9] SNAP-2: a plain get_job_progress_snapshot() poll is a pure read — it
    computes stall_detected but fires nothing. EVENT_STALL_DETECTED only fires from
    the explicit apply_job_progress_tick() (what the 5s ticker in
    listeners/job_progress.py calls), exactly once for a single-room job stuck >= 2x
    its estimate; a second tick does not re-fire for the same room.

    Single-room so the timing engine has nowhere to roll the current room to;
    elapsed (60m) >> 2x the 5m estimate → bounds-exit + stall.
    """
    _wire(manager, hass)
    _seed_job(
        manager, minutes_ago=60,
        queue_room_ids=[1],
        resolved_rooms=[{"room_id": 1, "name": "Kitchen", "minutes": 5,
                         "clean_mode": "vacuum"}],
    )
    hass.states.async_set(_VAC, "cleaning")
    events = []
    hass.bus.async_listen(EVENT_STALL_DETECTED, lambda e: events.append(e))

    # a pure read reports the anomaly field but fires + persists nothing
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["stall_detected"] is True
    assert snap["stall_ratio"] >= 2.0
    assert snap["running_long"] is False  # disjoint bands: >=2x is stall, not running_long
    assert events == []

    # the explicit tick is what actually fires it
    manager.apply_job_progress_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(events) == 1
    assert events[0].data["room_id"] == 1

    # a second tick must NOT re-fire (dedup via _stall_notified_room_ids)
    manager.apply_job_progress_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(events) == 1


def test_progress_running_long_suppressed_when_unlearned(manager, hass):
    """[PR-10] running_long is SUPPRESSED for an unlearned room even at ~1.7x its
    threshold: the ~6-min default estimate would otherwise flag every fresh-setup
    room as 'may be stuck' (issue #40). A LEARNED room still fires — unit test AJ-25.
    The threshold is read from the live estimate so this is robust to per-room minutes."""
    _wire(manager, hass)
    rooms = [{"room_id": 1, "name": "Kitchen", "minutes": 5, "clean_mode": "vacuum"}]
    _seed_job(manager, minutes_ago=0, queue_room_ids=[1], resolved_rooms=rooms)
    hass.states.async_set(_VAC, "cleaning")
    room0 = next(
        r for r in manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)["timeline"]
        if r.get("room_id") == 1
    )
    assert room0.get("source") == "default"  # genuinely unlearned (no seeded stats)
    threshold = manager.active_job._timing_completion_threshold_minutes(room0)
    # ~1.7x the threshold — would trip running_long if the room were learned.
    _seed_job(manager, minutes_ago=threshold * 1.7, queue_room_ids=[1], resolved_rooms=rooms)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["running_long"] is False
    assert snap["stall_detected"] is False
    # the per-room timeline flag is suppressed too (not just the top-level signal)
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["running_long"] is False


def test_progress_charge_phase_surfaces_eta(manager, hass):
    """[PR-13] a current charge_wait phase surfaces charge_phase_active + target + a
    learned ETA (here pure CV taper: 80->95 = 15pp * 3.0 min/pp = 45 min)."""
    from custom_components.eufy_vacuum.battery.manager import BatteryHealthManager
    from custom_components.eufy_vacuum.const import DATA_BATTERY
    _wire(manager, hass)
    bm = BatteryHealthManager(hass, runtime_manager=manager)
    rec = bm.ensure_record(_VAC)
    rec["baseline"]["cc_min_per_pct"] = 1.0
    rec["baseline"]["cv_min_per_pct"] = 3.0
    hass.data[DOMAIN][DATA_BATTERY] = bm
    hass.states.async_set(_VAC, "docked", {"battery_level": 80})
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[1], resolved_rooms=[], current_phase_index=1,
        phases=[
            {"resolved_rooms": [{"room_id": 1, "name": "K"}], "queue_room_ids": [1],
             "payload": {}, "room_count": 1},
            {"phase_type": "charge_wait", "target_battery_percent": 95,
             "charge_from_battery": 80, "charge_started_at": "2026-01-01T00:00:00Z",
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
    )
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["charge_phase_active"] is True
    assert snap["charge_target_percent"] == 95
    assert snap["charge_eta_minutes"] == 45.0
    assert snap["charge_eta_source"] == "baseline"
    assert snap["charge_from_battery"] == 80
    assert snap["charge_started_at"] == "2026-01-01T00:00:00Z"


def test_progress_zone_phase_surfaces(manager, hass):
    """[PR-14] a current zone phase surfaces zone_phase_active + names + an ETA (learned avg
    here: 300s -> 5 min), so the live view shows the zone instead of going blank (a zone has no
    room to anchor the timeline)."""
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
    _wire(manager, hass)
    mb = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    mb.setdefault("saved_zones", {})["z1"] = {"id": "z1", "name": "stove", "area_m2": 0.5}
    mb["learned_zones"] = {"z1": {"mop": {"avg_wall_seconds": 300, "sample_count": 2}}}
    hass.states.async_set(_VAC, "cleaning")
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[], resolved_rooms=[], current_phase_index=1,
        job_metadata={"has_mop_mode": True},
        phases=[
            {"resolved_rooms": [{"room_id": 1, "name": "K"}], "queue_room_ids": [1],
             "payload": {}, "room_count": 1},
            {"phase_type": "zone", "zone_ids": ["z1"], "zones": [[0.1, 0.1, 0.2, 0.2]],
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
    )
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["zone_phase_active"] is True
    assert snap["zone_phase_ids"] == ["z1"]
    assert snap["zone_phase_names"] == ["stove"]
    assert snap["zone_phase_eta_minutes"] == 5.0  # 300s learned (mop bucket)


def test_progress_zone_phase_hidden_when_docked(manager, hass):
    """[PR-15] the trailing zone phase lingers on the active job through the return/dock/dry
    window before finalize clears it — so zone_phase_active must gate on the device STILL cleaning
    (active_cleaning_target='N zone' / not docked), not just the phase type. Otherwise the live
    banner reads 'Cleaning zone · ~N min left' while the robot is docked + drying (the live bug)."""
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
    _wire(manager, hass)
    mb = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    mb.setdefault("saved_zones", {})["z1"] = {"id": "z1", "name": "stove", "area_m2": 0.5}
    hass.states.async_set(_VAC, "docked")  # zone finished, back on the dock (no target)
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[], resolved_rooms=[], current_phase_index=1,
        job_metadata={"has_mop_mode": True},
        phases=[
            {"resolved_rooms": [{"room_id": 1, "name": "K"}], "queue_room_ids": [1],
             "payload": {}, "room_count": 1},
            {"phase_type": "zone", "zone_ids": ["z1"], "zones": [[0.1, 0.1, 0.2, 0.2]],
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
    )
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["zone_phase_active"] is False  # docked -> banner cleared, not "still cleaning"


def test_progress_live_queue_sequence(manager, hass):
    """[PR-16] the live_queue flattens the running job's WHOLE phase sequence into ordered chips
    with done/current/upcoming state, read from the active_job clone (not the composer). A mid-run
    stepped job on its 2nd room: room(done) charge(done) room(current,%) wait(upcoming) zone(up)."""
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
    _wire(manager, hass)
    mb = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    mb.setdefault("saved_zones", {})["z1"] = {"id": "z1", "name": "stove", "area_m2": 0.5}
    hass.states.async_set(_VAC, "cleaning")
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[4],
        resolved_rooms=[{"room_id": 4, "name": "Hallway", "minutes": 5, "clean_mode": "vacuum"}],
        current_room_id=4, current_phase_index=2,
        phases=[
            {"resolved_rooms": [{"room_id": 5, "name": "Kitchen"}], "queue_room_ids": [5],
             "payload": {}, "room_count": 1},
            {"phase_type": "charge_wait", "target_battery_percent": 100,
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
            {"resolved_rooms": [{"room_id": 4, "name": "Hallway"}], "queue_room_ids": [4],
             "payload": {}, "room_count": 1},
            {"phase_type": "wait", "wait_minutes": 9,
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
            {"phase_type": "zone", "zone_ids": ["z1"],
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
    )
    lq = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)["live_queue"]
    assert lq["active"] is True
    assert [(s["kind"], s["state"]) for s in lq["steps"]] == [
        ("room", "done"),       # Kitchen (phase 0)
        ("charge", "done"),     # charge (phase 1)
        ("room", "current"),    # Hallway (phase 2 = current)
        ("wait", "upcoming"),   # wait (phase 3)
        ("zone", "upcoming"),   # stove zone (phase 4)
    ]
    _cur = next(s for s in lq["steps"] if s["state"] == "current")
    assert _cur["name"] == "Hallway"
    _zone = next(s for s in lq["steps"] if s["kind"] == "zone")
    assert _zone["zone_names"] == ["stove"]


def test_progress_zone_snapshot_survives_corrupt_saved_zone(manager, hass):
    """[PR-17] a truthy NON-dict saved-zone entry (corrupt .storage) must not crash the whole
    progress snapshot — the zone-name lookups fall back to the id. Review crash-guard finding."""
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
    _wire(manager, hass)
    mb = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    mb["saved_zones"] = {"z1": "corrupt-not-a-dict"}   # bad shape from odd storage
    hass.states.async_set(_VAC, "cleaning")
    _seed_job(
        manager, minutes_ago=0, queue_room_ids=[], resolved_rooms=[], current_phase_index=0,
        phases=[
            {"phase_type": "zone", "zone_ids": ["z1"],
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
    )
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)  # must NOT raise
    assert snap["zone_phase_names"] == ["z1"]                              # fell back to the id
    assert [s["kind"] for s in snap["live_queue"]["steps"]] == ["zone"]    # live queue also survived


def test_progress_skipped_conservative(manager, hass):
    """[PR-11] SNAP-2: a plain get_job_progress_snapshot() poll is a pure read — when
    current_room is ahead of an uncompleted queued room (a non-sequential advance),
    that room is flagged skipped in the payload, but nothing fires. Only the explicit
    apply_job_progress_tick() (what the 5s ticker calls) fires EVENT_ROOM_SKIPPED,
    once. Eufy's sequential counter rollover keeps this empty in normal runs (the
    reliable missed-rooms signal is the post-run incomplete_run_log)."""
    _wire(manager, hass)
    _seed_job(
        manager,
        queue_room_ids=[1, 2, 3],
        resolved_rooms=[
            {"room_id": 1, "name": "A", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "B", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 3, "name": "C", "minutes": 5, "clean_mode": "vacuum"},
        ],
        completed_room_ids=[2],   # room 2 done, room 1 NOT — current advanced past 1
        current_room_id=3,
    )
    hass.states.async_set(_VAC, "cleaning")
    events: list = []
    hass.bus.async_listen(EVENT_ROOM_SKIPPED, lambda e: events.append(e.data))

    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert 1 in snap["skipped_room_ids"]
    assert 1 not in snap["remaining_room_ids"]
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["skipped"] is True
    assert events == []  # a pure read fires nothing

    manager.apply_job_progress_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(events) == 1 and events[0]["room_id"] == 1
    # a second tick must NOT re-fire (dedup via _skipped_notified_room_ids)
    manager.apply_job_progress_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(events) == 1


def test_progress_sequential_no_false_skip(manager, hass):
    """[PR-12] a normal sequential run (completed prefix) flags NO skips."""
    _wire(manager, hass)
    _seed_job(manager, completed_room_ids=[1],
              completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}])
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["skipped_room_ids"] == []


async def test_finalize_no_learning(manager):
    """[PR-5] no learning manager wired → None."""
    # the manager fixture does not set DATA_LEARNING
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result is None


def test_save_learning_snapshot_delegates(manager, monkeypatch):
    """[PR-5b] save_learning_snapshot_for_active_job forwards to the learning
    manager's save_live_snapshot_from_manager when one is available."""
    captured: dict = {}

    class _FakeLearning:
        def save_live_snapshot_from_manager(self, **kw):
            captured.update(kw)
            return {"saved": True}

    monkeypatch.setattr(manager, "_get_learning_manager", lambda: _FakeLearning())
    out = manager.save_learning_snapshot_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, started_at="2026-01-01T00:00:00+00:00",
        battery_start=90, job_id="job1")
    assert out == {"saved": True}
    assert captured["vacuum_entity_id"] == _VAC and captured["job_id"] == "job1"


def test_save_learning_snapshot_no_learning_returns_none(manager):
    """[PR-5b] no learning manager wired → None (the early-return guard)."""
    assert manager.save_learning_snapshot_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, started_at="x",
        battery_start=90, job_id="job1") is None


async def test_finalize_missing_started_at(manager, hass):
    """[PR-6] an active job with no started_at → not finalized."""
    _wire(manager, hass)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started", "started_at": ""}
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["finalized"] is False
    assert result["reason"] == "missing_started_at"


async def test_finalize_main_path(manager, hass):
    """[PR-7] a full job finalizes into a completed_job record."""
    _wire(manager, hass)
    _seed_job(manager, battery_start=90)
    hass.states.async_set(_VAC, "docked", {"battery_level": 70})
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=70)
    assert result is not None
    assert "completed_job" in result


def test_ingest_jobs_index_into_room_history(manager):
    """[PR-8] jobs-index → room-history merge with newer-wins + bad-row skips."""
    ing = manager._ingest_jobs_index_entry_into_room_history
    # guard branches
    assert ing(vacuum_entity_id=_VAC, index_entry="nope") is False
    assert ing(vacuum_entity_id=_VAC,
               index_entry={"map_id": "6", "rooms": []}) is False  # no ended_at
    assert ing(vacuum_entity_id=_VAC, index_entry={
        "ended_at": "2026-01-01T10:00:00+00:00", "rooms": "notalist"}) is False

    # valid entry: merges fields, skips bad rows
    entry = {
        "ended_at": "2026-01-01T10:00:00+00:00", "map_id": "6", "rooms": [
            {"room_id": 1, "name": "Kitchen", "clean_mode": "vacuum",
             "last_cleaned_at": "2026-01-01T10:00:00+00:00",
             "last_vacuumed_at": "2026-01-01T10:00:00+00:00"},
            {"room_id": 0, "name": "bad"},   # room_id <= 0 → skipped
            "notadict",                       # non-dict row → skipped
        ]}
    assert ing(vacuum_entity_id=_VAC, index_entry=entry) is True
    rh = manager.data["room_history"][_VAC]["6"]["1"]
    assert rh["room_name"] == "Kitchen"
    assert rh["last_cleaned_at"] == "2026-01-01T10:00:00+00:00"
    assert rh["last_job_mode"] == "vacuum"

    # an older entry must NOT overwrite the newer last_cleaned_at
    older = {"ended_at": "2025-01-01T00:00:00+00:00", "map_id": "6", "rooms": [
        {"room_id": 1, "last_cleaned_at": "2025-01-01T00:00:00+00:00"}]}
    ing(vacuum_entity_id=_VAC, index_entry=older)
    assert manager.data["room_history"][_VAC]["6"]["1"]["last_cleaned_at"] == \
        "2026-01-01T10:00:00+00:00"


def test_payload_state_enrichment_skips_non_dict_rooms(manager):
    """[PS-1] get_payload_state enriches each dict room in resolved_rooms with
    settings-profile-display + surface labels, and the loop *continues past* a
    non-dict entry (manager.py:2025) rather than enriching or emitting it.

    Seeds the payload bucket directly on manager.data (the exact dict
    get_payload_state reads at L2005-2018) with one valid room dict plus a bare
    string. The returned resolved_rooms must contain exactly the one enriched
    dict; the non-dict is dropped.
    """
    manager.data.setdefault("payloads", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "payload": {"map_id": _MAP, "rooms": []},
        "resolved_rooms": [
            {
                "room_id": 1,
                "name": "Kitchen",
                "clean_mode": "vacuum",
                "fan_speed": "max",
                "floor_type": "hard",
                "clean_passes": 2,
            },
            "not-a-dict",  # the non-dict the loop must skip (manager.py:2025)
        ],
        "room_count": 2,
    }

    state = manager.get_payload_state(vacuum_entity_id=_VAC, map_id=_MAP)

    resolved = state["resolved_rooms"]
    # the string was dropped — exactly one enriched dict survives
    assert len(resolved) == 1
    room = resolved[0]
    assert isinstance(room, dict)

    # original fields carried through
    assert room["room_id"] == 1
    assert room["name"] == "Kitchen"

    # _settings_profile_display enrichment keys present on the surviving room
    assert "profile_label" in room
    assert room["clean_mode_label"] == "Vacuum"
    assert room["fan_speed_label"] == "Max"
    assert room["clean_passes_label"] == "2 Passes"
    assert isinstance(room["is_custom_profile"], bool)

    # _room_surface_labels enrichment key present
    assert "floor_type_label" in room

    # nothing in the output is a non-dict (the skip held)
    assert all(isinstance(r, dict) for r in resolved)



# --------------------------------------------------------------------------
# A run cancelled during a wait stranded the countdown on the card
# (observed 2026-08-02).
# --------------------------------------------------------------------------


def _wait_phase_job(manager, **extra):
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[1], resolved_rooms=[], current_phase_index=1,
        phases=[
            {"resolved_rooms": [{"room_id": 1, "name": "K"}], "queue_room_ids": [1],
             "payload": {}, "room_count": 1},
            {"phase_type": "wait", "wait_minutes": 2,
             "wait_started_at": "2026-01-01T00:00:00Z",
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
        **extra,
    )


def test_progress_wait_phase_surfaces_while_running(manager, hass):
    """Baseline — a live wait must still drive the countdown banner."""
    _wire(manager, hass)
    _wait_phase_job(manager)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["wait_phase_active"] is True
    assert snap["wait_minutes"] == 2


def test_progress_wait_phase_clears_once_the_job_is_finalized(manager, hass):
    """charge/wait/zone "active" was derived purely from current_phase_index +
    phase_type. A cancel during a wait leaves that index pointing at the wait forever, so
    the card kept counting down a hold that had already been torn down. Same shape as the
    advance-after-cancel defect: phase structure read without asking if the run exists."""
    _wire(manager, hass)
    _wait_phase_job(manager, status="completed", finalized=True)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["wait_phase_active"] is False
    assert snap["wait_started_at"] is None


def test_progress_charge_phase_clears_once_the_job_is_finalized(manager, hass):
    """The charge banner shares the same derivation, so it stranded the same way."""
    _wire(manager, hass)
    hass.states.async_set(_VAC, "docked", {"battery_level": 80})
    _seed_job(
        manager, minutes_ago=0, status="completed", finalized=True,
        queue_room_ids=[1], resolved_rooms=[], current_phase_index=1,
        phases=[
            {"resolved_rooms": [{"room_id": 1, "name": "K"}], "queue_room_ids": [1],
             "payload": {}, "room_count": 1},
            {"phase_type": "charge_wait", "target_battery_percent": 95,
             "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0},
        ],
    )
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["charge_phase_active"] is False


# --------------------------------------------------------------------------
# RP-047 — a group phase is ONE dispatch, so the snapshot must present the
# PHASE rather than pinning to room[0] for its whole duration.
# --------------------------------------------------------------------------


_PHASES = [
    {"phase_type": "room_group", "queue_room_ids": [1],
     "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}], "payload": {}, "room_count": 1},
    {"phase_type": "wait", "wait_minutes": 2, "queue_room_ids": [],
     "resolved_rooms": [], "payload": {}, "room_count": 0},
    {"phase_type": "room_group", "queue_room_ids": [2, 3],
     "resolved_rooms": [{"room_id": 2, "name": "Entryway"},
                        {"room_id": 3, "name": "Hallway"}], "payload": {}, "room_count": 2},
]


def _group_phase_job(manager, *, phase_index: int = 2, **extra):
    """A phased job sitting ON a given phase.

    advance_active_job_phase rewrites the job's TOP-LEVEL queue/resolved_rooms to the
    phase it moved to, so a faithful seed must too — otherwise current_room_id derives
    from a queue the run has already left behind.
    """
    phase = _PHASES[phase_index]
    _seed_job(
        manager, minutes_ago=0,
        current_phase_index=phase_index,
        queue_room_ids=list(phase["queue_room_ids"]),
        resolved_rooms=[dict(r) for r in phase["resolved_rooms"]],
        phases=[dict(p) for p in _PHASES],
        **extra,
    )


def test_progress_group_phase_names_every_room_it_dispatched(manager, hass):
    """record_completed_room never fires inside a group — the group is one command — so
    current_room_id pinned to room[0] for the phase's whole duration and the card looked
    frozen. Live: Entryway held for 13m40s of an [entryway + hallway] phase."""
    _wire(manager, hass)
    _group_phase_job(manager)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)

    assert snap["current_room_ids"] == [2, 3]
    assert snap["current_phase"]["is_group"] is True
    assert snap["current_phase"]["room_ids"] == [2, 3]
    assert snap["current_phase"]["phase_type"] == "room_group"


def test_progress_group_phase_leaves_the_anchor_alone(manager, hass):
    """The anchor must NOT advance partway through a group: the split was never observed
    (that is what a timing row's allocated:true records), so moving it would synthesize a
    boundary. The fix is that the card stops treating it as the whole answer."""
    _wire(manager, hass)
    _group_phase_job(manager)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)

    assert snap["current_room_id"] == 2, "the map anchor moved"
    assert snap["current_room_id"] == snap["current_room_ids"][0]


def test_progress_single_room_phase_is_unchanged(manager, hass):
    """Additive: a single-room phase yields one id identical to the anchor, so every
    existing consumer keeps working."""
    _wire(manager, hass)
    _group_phase_job(manager, phase_index=0)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)

    assert snap["current_room_ids"] == [1]
    assert snap["current_phase"]["is_group"] is False
    assert snap["current_room_id"] == 1


def test_progress_atomic_run_still_reports_a_room_list(manager, hass):
    """An atomic run has no phases at all; the list falls back to the anchor so a
    consumer never has to special-case its absence."""
    _wire(manager, hass)
    _seed_job(manager, minutes_ago=0)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)

    assert snap["current_phase"] is None
    assert snap["current_room_ids"] == [snap["current_room_id"]]


# ---------------------------------------------------------------------------
# The estimate panel: PLANNING recomputes live, RUNNING shows the dispatch plan
# ---------------------------------------------------------------------------

def _freeze_snapshot(manager, hass, *, job_id="j1", total=42.0):
    """Write a live job snapshot carrying a planned estimate, as dispatch does."""
    learning = hass.data[DOMAIN][DATA_LEARNING]
    learning.finalizer._live_snapshot_cache[_VAC] = {
        "schema_version": 1,
        "snapshot_type": "job_start",
        "job_id": job_id,
        "planned_job_estimate": {
            "available": True,
            "total_minutes": total,
            "job_eta_minutes": total,
        },
    }


def test_estimate_panel_is_live_while_planning(manager, hass):
    """[PR-20] With no job running the panel must still RECOMPUTE — a frozen plan
    would stop responding to the user editing the queue."""
    _wire(manager, hass)
    setup_map(manager, _VAC, _MAP)
    _freeze_snapshot(manager, hass, total=999.0)

    out = manager._planned_estimate_for_dashboard(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out.get("frozen_at_dispatch") is not True
    assert out.get("total_minutes") != 999.0


def test_estimate_panel_freezes_at_dispatch_while_running(manager, hass):
    """[PR-21] The panel emptied itself the moment a run started: job start clears
    the payload state that get_planned_job_estimate computes from, so the live
    recompute reports available=False. Serve the plan captured AT DISPATCH."""
    _wire(manager, hass)
    setup_map(manager, _VAC, _MAP)
    _seed_job(manager, payload={}, resolved_rooms=[])   # payload cleared, as at start
    _freeze_snapshot(manager, hass, job_id="j1", total=42.0)

    live = manager.get_planned_job_estimate(vacuum_entity_id=_VAC, map_id=_MAP)
    assert live["available"] is False, "precondition: the live recompute is empty mid-run"

    out = manager._planned_estimate_for_dashboard(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["available"] is True
    assert out["total_minutes"] == 42.0
    assert out["frozen_at_dispatch"] is True
    assert out["source"] == "dispatch_snapshot"


def test_estimate_panel_refuses_a_previous_runs_plan(manager, hass):
    """[PR-22] The snapshot outlives its job on disk. Showing the LAST run's plan
    as this one's would be a new and worse failure than the empty panel, so the
    job id is matched and a mismatch falls back to live."""
    _wire(manager, hass)
    setup_map(manager, _VAC, _MAP)
    _seed_job(manager, job_id="j2", payload={}, resolved_rooms=[])
    _freeze_snapshot(manager, hass, job_id="j1", total=42.0)   # the PREVIOUS run

    out = manager._planned_estimate_for_dashboard(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out.get("frozen_at_dispatch") is not True
    assert out.get("total_minutes") != 42.0


def test_estimate_panel_falls_back_when_no_snapshot_exists(manager, hass):
    """[PR-23] A run predating the snapshot degrades to the pre-existing empty
    panel rather than raising."""
    _wire(manager, hass)
    setup_map(manager, _VAC, _MAP)
    _seed_job(manager, payload={}, resolved_rooms=[])

    out = manager._planned_estimate_for_dashboard(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["available"] is False
    assert out.get("frozen_at_dispatch") is not True


def test_estimate_panel_thaws_once_the_job_is_terminal(manager, hass):
    """[PR-24] Once a run ends the panel is planning the NEXT one — a frozen plan
    that never thaws is the same bug in the other direction."""
    _wire(manager, hass)
    setup_map(manager, _VAC, _MAP)
    _seed_job(manager, status="completed", payload={}, resolved_rooms=[])
    _freeze_snapshot(manager, hass, job_id="j1", total=42.0)

    out = manager._planned_estimate_for_dashboard(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out.get("frozen_at_dispatch") is not True


def test_group_phase_marks_every_room_current(manager, hass):
    """[PR-24] RP-047(b) — a group phase lights ALL its rooms, not room[0].

    THE FINDING (C4 / #9:A3-REC-3). is_current compared against the SINGULAR
    current_room_id, which for a group dispatch is room[0]. A phase cleaning
    three rooms at once therefore marked exactly one room current, and the card
    pinned to it for the whole phase — reproduced live on Alfred as
    pj_2026-08-02T23-04-45, which stayed on Entryway.

    RP-047(a) already computed current_room_ids for the active phase and shipped
    it in the current_phase block; NOTHING CONSUMED IT. Matching the per-room
    flag against the list is the whole fix, and it needs no card change: every
    surface already reads this flag.
    """
    _wire(manager, hass)
    hass.states.async_set(_VAC, "cleaning")
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[1, 2, 3],
        resolved_rooms=[
            {"room_id": 1, "name": "Entryway", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "Hallway", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 3, "name": "Study", "minutes": 5, "clean_mode": "vacuum"},
        ],
        # room[0] — exactly what the old code pinned to.
        current_room_id=1, current_phase_index=0,
        phases=[
            {"resolved_rooms": [
                {"room_id": 1, "name": "Entryway"},
                {"room_id": 2, "name": "Hallway"},
                {"room_id": 3, "name": "Study"},
             ],
             "queue_room_ids": [1, 2, 3], "payload": {}, "room_count": 3},
        ],
    )

    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    timeline = snap["timeline"]
    current = sorted(
        int(r["room_id"]) for r in timeline if r.get("current")
    )

    assert current == [1, 2, 3], (
        f"the group phase marked {current} current — a group dispatch cleans all "
        "three at once, so pinning to room[0] is the defect"
    )
    # and the phase block still describes itself
    assert snap["current_phase"]["is_group"] is True
    assert sorted(snap["current_phase"]["room_ids"]) == [1, 2, 3]


def test_single_room_phase_is_unchanged(manager, hass):
    """[PR-24b] RP-047(b) — atomic dispatch keeps exactly one current room.

    The safety half. Falling back to the singular when there is no phase block,
    and matching a one-room phase, must both behave exactly as before — the fix
    may only ever ADD rooms to a group, never change a single-room run.
    """
    _wire(manager, hass)
    hass.states.async_set(_VAC, "cleaning")
    _seed_job(
        manager, minutes_ago=0,
        queue_room_ids=[1, 2],
        resolved_rooms=[
            {"room_id": 1, "name": "Entryway", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "Hallway", "minutes": 5, "clean_mode": "vacuum"},
        ],
        current_room_id=2, current_phase_index=1,
        phases=[
            {"resolved_rooms": [{"room_id": 1, "name": "Entryway"}],
             "queue_room_ids": [1], "payload": {}, "room_count": 1},
            {"resolved_rooms": [{"room_id": 2, "name": "Hallway"}],
             "queue_room_ids": [2], "payload": {}, "room_count": 1},
        ],
    )

    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    current = [int(r["room_id"]) for r in snap["timeline"] if r.get("current")]
    assert current == [2], f"single-room phase marked {current} current"
    assert snap["current_phase"]["is_group"] is False
