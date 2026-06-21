"""Strict-order per-phase finalization fix.

A sequenced (strict-order) job advances one room per PHASE, docking between rooms. The
whole-run counter stream can't be segmented across those dock trips against the single
last-phase queue, so finalization used to record only the last phase's room with the whole
run's battery/area. The fix snapshots each finishing phase's room_timing from its OWN counter
slice (manager.phase_runner._capture_finishing_phase_timing) before advance resets the queue; finalization
concatenates them.

[SOPT-1] each phase captures its OWN room from its own slice (not the whole stream).
[SOPT-2] capture is idempotent (a retry/double-completion can't double-record).
[SOPT-3] AREA fallback: a flat cleaning_area through a phase falls back to the learned area.
[SOPT-4] atomic jobs (no phases) are a no-op.
"""

from __future__ import annotations

import custom_components.eufy_vacuum.jobs.phase_runner as phase_runner_mod

_VAC = "vacuum.ivy"
_MAP = "Main floor"


def _cs(t: str, ct: int, ca: float) -> dict:
    return {"t": t, "cleaning_time": ct, "cleaning_area": ca, "battery": 90}


def _phase(rid: int, slug: str) -> dict:
    return {
        "resolved_rooms": [{"room_id": rid, "slug": slug}],
        "queue_room_ids": [rid],
        "payload": {}, "room_count": 1,
    }


def _seed_job(manager, job: dict) -> None:
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job


async def test_capture_per_phase_room_timing(hass, manager, monkeypatch):
    """[SOPT-1] + [SOPT-2]"""
    # Deterministic clock so each phase's _timing_end_t lands between the two phases' samples.
    clock = iter(["2026-01-01T00:01:00Z", "2026-01-01T00:03:00Z", "2026-01-01T00:03:00Z"])
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: next(clock))

    phase_a = [
        _cs(f"2026-01-01T00:00:{s:02d}Z", ct, ca)
        for s, ct, ca in [(10, 30, 1.5), (20, 60, 3.0), (40, 90, 4.5), (50, 120, 6.0)]
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z", "ended_at": None,
        "phases": [_phase(5, "kitchen"), _phase(8, "dining_room")],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}],
        "queue_room_ids": [5],
        "counter_samples": list(phase_a),
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt0 = job["phases"][0].get("room_timing")
    assert rt0 and rt0[0]["room_id"] == 5

    # [SOPT-2] idempotent — second call leaves it untouched
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    assert job["phases"][0]["room_timing"] is rt0

    # advance to phase 1: more samples arrive, index bumps (as advance_active_job_phase does)
    phase_b = [
        _cs(f"2026-01-01T00:02:{s:02d}Z", ct, ca)
        for s, ct, ca in [(10, 150, 7.5), (20, 180, 9.0), (40, 210, 10.5), (50, 240, 12.0)]
    ]
    job["counter_samples"].extend(phase_b)
    job["current_phase_index"] = 1
    job["resolved_rooms"] = [{"room_id": 8, "slug": "dining_room"}]
    job["queue_room_ids"] = [8]

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt1 = job["phases"][1].get("room_timing")
    assert rt1 and rt1[0]["room_id"] == 8

    # [SOPT-1] each phase named its OWN room — NOT the whole stream / last room twice
    assert [rt[0]["room_id"] for rt in (rt0, rt1)] == [5, 8]
    # phase 0's slice excluded phase B's area: its area ~ 6 m², not the whole-run ~12
    assert 0 < rt0[0]["area_m2"] <= 8.0


async def test_area_fallback_to_learned(hass, manager, monkeypatch):
    """[SOPT-3] a phase whose cleaning_area is flat (stale sensor) falls back to learned area."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    # learned area for room 5 in the map registry
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "rooms": {"5": {"slug": "kitchen", "learned_area_m2": 9.3}}
    }
    flat = [
        _cs(f"2026-01-01T00:04:{s:02d}Z", ct, 4.0)  # cleaning_area FLAT at 4.0
        for s, ct in [(10, 30), (20, 60), (40, 90), (50, 120)]
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:04:00Z", "ended_at": None,
        "phases": [_phase(5, "kitchen")],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}],
        "queue_room_ids": [5],
        "counter_samples": flat,
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt = job["phases"][0].get("room_timing")
    assert rt and rt[0]["room_id"] == 5
    assert rt[0]["area_m2"] == 9.3 and rt[0].get("area_source") == "learned_fallback"


async def test_never_cleaned_phase_records_empty_not_phantom(hass, manager, monkeypatch):
    """A phase whose slice has no usable counter samples (never cleaned — the watchdog gave up,
    or a stale completion signal) records an EMPTY timing, marked attempted — NOT a phantom room
    with a fabricated learned area (which would poison learning)."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:06:00Z")
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "rooms": {"5": {"slug": "kitchen", "learned_area_m2": 9.3}}
    }
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:06:00Z", "ended_at": None,
        "phases": [_phase(5, "kitchen")],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}],
        "queue_room_ids": [5],
        "counter_samples": [],  # never cleaned -> no samples in the slice
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    assert job["phases"][0]["room_timing"] == []        # no phantom room, no learned-area fabrication
    assert job["phases"][0].get("_timing_end_t")         # but marked attempted (idempotent)

    # re-running is a no-op — guarded on _timing_end_t, NOT room_timing truthiness
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    assert job["phases"][0]["room_timing"] == []


async def test_atomic_job_is_noop(hass, manager):
    """[SOPT-4] a job with no phases is untouched."""
    job = {"vacuum_entity_id": _VAC, "map_id": _MAP, "queue_room_ids": [5], "counter_samples": []}
    _seed_job(manager, job)
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    assert "phases" not in job and "room_timing" not in job


async def test_learned_room_area_prefers_learned_then_area_then_none(hass, manager):
    """[SOPT-6] the AREA fallback source: learned_area_m2 preferred, area_m2 next, None when
    neither / no room / bad id."""
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {"rooms": {
        "5": {"learned_area_m2": 9.3, "area_m2": 1.0},  # learned wins
        "6": {"area_m2": 4.0},                            # only area_m2 -> fallback key
        "7": {"slug": "x"},                               # neither -> None
    }}
    assert manager.phase_runner._learned_room_area_m2(_VAC, _MAP, 5) == 9.3
    assert manager.phase_runner._learned_room_area_m2(_VAC, _MAP, 6) == 4.0
    assert manager.phase_runner._learned_room_area_m2(_VAC, _MAP, 7) is None
    assert manager.phase_runner._learned_room_area_m2(_VAC, _MAP, 99) is None   # no such room
    assert manager.phase_runner._learned_room_area_m2(_VAC, _MAP, 0) is None    # bad id


async def test_phase_room_timing_battery_delta_and_wall_parse(hass, manager):
    """[SOPT-7] per-phase deltas: cleaning_seconds/area = within-slice delta, battery_delta =
    first−last, wall = parsed ISO span; bad timestamps degrade to 0 wall without crashing."""
    good = [
        {"t": "2026-01-01T00:00:00Z", "cleaning_time": 10, "cleaning_area": 1.0, "battery": 80},
        {"t": "2026-01-01T00:02:00Z", "cleaning_time": 130, "cleaning_area": 7.0, "battery": 74},
    ]
    rt = manager.phase_runner._phase_room_timing(5, "kitchen", good)
    assert rt["cleaning_seconds"] == 120 and rt["area_m2"] == 6.0
    assert rt["battery_delta"] == 6 and rt["cleaning_wall_seconds"] == 120

    bad_ts = [
        {"t": "nope", "cleaning_time": 0, "cleaning_area": 0.0, "battery": 50},
        {"t": "also-bad", "cleaning_time": 30, "cleaning_area": 2.0, "battery": 48},
    ]
    rt2 = manager.phase_runner._phase_room_timing(5, "kitchen", bad_ts)
    assert rt2["cleaning_seconds"] == 30 and rt2["battery_delta"] == 2
    assert rt2["cleaning_wall_seconds"] == 0  # _wall_seconds swallows the parse error
