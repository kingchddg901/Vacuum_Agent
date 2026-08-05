"""Strict-order per-phase finalization fix.

A sequenced (strict-order) job advances one room per PHASE, docking between rooms. The
whole-run counter stream can't be segmented across those dock trips against the single
last-phase queue, so finalization used to record only the last phase's room with the whole
run's battery/area. The fix snapshots each finishing phase's room_timing from its OWN counter
slice (manager.phase_runner._capture_finishing_phase_timing) before advance resets the queue; finalization
concatenates them.

A room_group STEP phase can carry more than one room (a strict-order engine still emits one
room per DISPATCH phase, but a step-plan's room_group step is captured as a single phase
covering the whole group — RP-013b). _capture_finishing_phase_timing sources ids from the
PHASE's OWN resolved_rooms (not the job's whole-run queue_room_ids, which for phase 0 is the
entire run and need not even belong to the phase — REC-2) and emits ONE timing entry per
member: a single-room phase stays exact (allocated=False); a multi-room group's measured
totals have no per-room boundary inside the batch (fabricating one is forbidden), so they are
split evenly with an exact-sum-preserving distribution, allocated=True, allocation_group_size=N.

[SOPT-1] each phase captures its OWN room from its own slice (not the whole stream).
[SOPT-2] capture is idempotent (a retry/double-completion can't double-record).
[SOPT-3] AREA fallback: a flat cleaning_area through a phase falls back to the learned area.
[SOPT-4] atomic jobs (no phases) are a no-op.
[SOPT-6] _learned_room_area_m2 area source prefers learned_area_m2, then area_m2, and returns None when neither key is present, the room is missing, or the id is bad.
[SOPT-7] _phase_room_timing computes within-slice cleaning_seconds/area deltas, battery_delta as first−last, and wall seconds from parsed ISO timestamps, degrading to 0 wall on unparseable timestamps without crashing.
[SOPT-8] a multi-room group phase splits its measured totals evenly across members (allocated=True, allocation_group_size=N), preserving the exact sum even when it doesn't divide evenly.
[SOPT-9] a single-room phase stays allocated=False (exact, not apportioned).
[SOPT-10] phase-scoped ids: a phase's OWN resolved_rooms are credited even when the job's queue_room_ids (whole-run) disagrees.
[SOPT-11] a group phase whose slice SHOWS the split is segmented per member (allocated=False, distinct walls, totals reconcile).
[SOPT-12] segmented rows are rebased off the slice's own baseline, not the segmenter's count-from-zero.
[SOPT-13] gate 1 — a brand declaring honors_clean_order=False is apportioned, never segmented.
[SOPT-14] gate 2 — an unbroken stream (no observable boundary) falls back to apportioning.
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


def _group_phase(rooms: list[tuple[int, str]]) -> dict:
    return {
        "resolved_rooms": [{"room_id": rid, "slug": slug} for rid, slug in rooms],
        "queue_room_ids": [rid for rid, _ in rooms],
        "payload": {}, "room_count": len(rooms),
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


# ---------------------------------------------------------------------------
# A group phase is SEGMENTED when its own counter slice shows the split
# ---------------------------------------------------------------------------

def _two_room_slice(base_ct: int = 30, base_area: float = 1.5) -> list[dict]:
    """A realistic two-room group slice: room A ticks, a >90 s plateau while the
    robot transits, then room B ticks. The plateau is what the segmenter sees.

    ``base_ct`` / ``base_area`` are the CUMULATIVE readings the slice opens at —
    non-zero on every phase after the first, which is what makes the rebase load-
    bearing.
    """
    return [
        _cs("2026-01-01T00:00:30Z", base_ct, base_area),
        _cs("2026-01-01T00:01:00Z", base_ct + 30, base_area + 1.5),
        _cs("2026-01-01T00:01:30Z", base_ct + 60, base_area + 3.0),
        # --- >90 s gap: the inter-room plateau ---
        _cs("2026-01-01T00:03:30Z", base_ct + 90, base_area + 4.5),
        _cs("2026-01-01T00:04:00Z", base_ct + 120, base_area + 6.0),
        _cs("2026-01-01T00:04:30Z", base_ct + 150, base_area + 7.5),
    ]


def _group_job(samples: list[dict], rooms=((4, "a"), (5, "b"))) -> dict:
    return {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z", "ended_at": None,
        "phases": [_group_phase(list(rooms))],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": r, "slug": s} for r, s in rooms],
        "queue_room_ids": [r for r, _ in rooms],
        "counter_samples": samples,
    }


async def test_group_phase_is_segmented_when_the_slice_shows_the_split(
    hass, manager, monkeypatch
):
    """[SOPT-11] The dispatch batched them; the robot still cleaned them one at a
    time, and the counter stream carries the plateau between. Each member gets its
    OWN measurement — allocated=False, so stats_rebuilder admits it."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")
    job = _group_job(_two_room_slice())
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt = job["phases"][0]["room_timing"]

    assert [t["room_id"] for t in rt] == [4, 5]
    assert all(t["allocated"] is False for t in rt)
    assert all("allocation_group_size" not in t for t in rt)

    # The point of the exercise: the two rooms get DIFFERENT wall times. The even
    # split gives both the whole phase's wall, which is what taught a one-minute
    # room a six-minute baseline. Exact values, so this cannot pass by falling
    # back (which would be 75/75 s and 3.75/3.75 m², both walls identical).
    assert [t["cleaning_seconds"] for t in rt] == [60, 90]
    assert [t["area_m2"] for t in rt] == [4.5, 3.0]
    assert [t["cleaning_wall_seconds"] for t in rt] == [30, 60]
    # Each row names the boundary that actually split it.
    assert [t["boundary"] for t in rt] == ["job_start", "wash_plateau"]
    # battery_delta stays an int here as it is on the other two paths.
    assert all(t["battery_delta"] is None or isinstance(t["battery_delta"], int)
               for t in rt)

    # ...and the measured totals still reconcile to the group's own.
    whole = manager.phase_runner._phase_room_timing(None, None, job["counter_samples"])
    assert sum(t["cleaning_seconds"] for t in rt) == whole["cleaning_seconds"]
    assert round(sum(t["area_m2"] for t in rt), 3) == round(whole["area_m2"], 3)


async def test_segmented_rows_are_rebased_off_the_slice_not_zero(
    hass, manager, monkeypatch
):
    """[SOPT-12] THE trap this had to avoid.

    ``build_segments`` counts from zero while cleaning_time/cleaning_area are
    CUMULATIVE across the run, and the window only re-bases at a counter reset —
    once per run, not once per phase. Unrebased, the first member of a later
    phase's group would be credited with the whole run's totals.

    Same slice shape as [SOPT-11] but opening at a high cumulative reading, as any
    phase after the first does. The numbers must be identical to the low-baseline
    case; if the rebase were missing, room 4 would carry ~600 s instead of 60 s.
    """
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")

    low = _group_job(_two_room_slice(base_ct=30, base_area=1.5))
    _seed_job(manager, low)
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, low)
    low_rt = low["phases"][0]["room_timing"]

    high = _group_job(_two_room_slice(base_ct=600, base_area=42.0))
    _seed_job(manager, high)
    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, high)
    high_rt = high["phases"][0]["room_timing"]

    assert all(t["allocated"] is False for t in high_rt), "fell back — nothing proved"
    assert [t["cleaning_seconds"] for t in high_rt] == [t["cleaning_seconds"] for t in low_rt]
    assert [t["area_m2"] for t in high_rt] == [t["area_m2"] for t in low_rt]

    # Measured (probe: .claude/notes/_probe_phase_slice_seg.py). Unrebased, the raw
    # segment for room 4 reports time_active_s 660.0 and area_delta_m2 46.5 — the
    # whole run's cumulative counters booked as one room's work.
    assert [t["cleaning_seconds"] for t in high_rt] == [60, 90]
    assert [t["area_m2"] for t in high_rt] == [4.5, 3.0]


async def test_a_brand_that_reorders_is_not_segmented(hass, manager, monkeypatch):
    """[SOPT-13] Gate 1. Mapping segment i to group_ids[i] is only sound when the
    brand cleans in the order it was given. Roborock declares
    capabilities.honors_clean_order False — it re-routes — so the same slice that
    segments cleanly above must fall back to apportioning."""
    from custom_components.eufy_vacuum.adapters.registry import (
        clear_registry,
        register_adapter_config,
    )

    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")
    register_adapter_config(_VAC, {
        "adapter_id": "reorders_test", "source": "code",
        "capabilities": {"honors_clean_order": False},
    })
    try:
        job = _group_job(_two_room_slice())
        _seed_job(manager, job)

        manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
        rt = job["phases"][0]["room_timing"]
        # The differential: [SOPT-11] segments this EXACT slice. Only the
        # capability declaration differs, so this asserts the gate and nothing else.
        assert all(t["allocated"] is True and t["allocation_group_size"] == 2 for t in rt)
    finally:
        # No autouse fixture clears the registry — leaving this registered would
        # silently apply "this brand reorders" to every later test in the module.
        clear_registry()


async def test_no_observable_split_falls_back_to_apportioning(hass, manager, monkeypatch):
    """[SOPT-14] Gate 2. An unbroken stream (no plateau) yields one bout, not two —
    we cannot say where one room ended, so we do not guess."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")
    steady = [
        _cs(f"2026-01-01T00:0{m // 2}:{(m % 2) * 30:02d}Z", 30 + m * 30, 1.5 + m * 1.5)
        for m in range(0, 8)
    ]
    job = _group_job(steady)
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt = job["phases"][0]["room_timing"]
    assert all(t["allocated"] is True and t["allocation_group_size"] == 2 for t in rt)


async def test_group_phase_splits_evenly_with_exact_sum_preserved(hass, manager, monkeypatch):
    """[SOPT-8] a 3-room group phase: one entry per room, allocated=True,
    allocation_group_size=3, and the measured totals preserved EXACTLY across the split
    (not merely 'approximately a third each') — RP-013b/REC-1."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")
    samples = [
        _cs(f"2026-01-01T00:0{m}:00Z", m * 60, m * (12.0 / 9))
        for m in range(0, 10)
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z", "ended_at": None,
        "phases": [_group_phase([(4, "a"), (5, "b"), (6, "c")])],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": r, "slug": s} for r, s in [(4, "a"), (5, "b"), (6, "c")]],
        "queue_room_ids": [4, 5, 6],
        "counter_samples": samples,
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt = job["phases"][0]["room_timing"]

    assert sorted(t["room_id"] for t in rt) == [4, 5, 6]
    assert all(t["allocated"] is True and t["allocation_group_size"] == 3 for t in rt)
    assert sum(t["cleaning_seconds"] for t in rt) == 540
    assert round(sum(t["area_m2"] for t in rt), 3) == 12.0


async def test_group_phase_uneven_split_still_preserves_exact_sum(hass, manager, monkeypatch):
    """[SOPT-8] a total that does NOT divide evenly by the group size must still sum back
    exactly — the largest-remainder distribution, not naive division + rounding drift."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")
    # 100 seconds / 3 rooms = 33.33... ; 1.0 m2 / 3 rooms = 0.333...
    samples = [
        {"t": "2026-01-01T00:00:00Z", "cleaning_time": 0, "cleaning_area": 0.0, "battery": 90},
        {"t": "2026-01-01T00:01:00Z", "cleaning_time": 100, "cleaning_area": 1.0, "battery": 88},
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z", "ended_at": None,
        "phases": [_group_phase([(1, "a"), (2, "b"), (3, "c")])],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": r, "slug": s} for r, s in [(1, "a"), (2, "b"), (3, "c")]],
        "queue_room_ids": [1, 2, 3],
        "counter_samples": samples,
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt = job["phases"][0]["room_timing"]

    assert sum(t["cleaning_seconds"] for t in rt) == 100
    assert round(sum(t["area_m2"] for t in rt), 3) == 1.0
    # battery_delta (int, first-last) must also sum exactly
    assert sum(t["battery_delta"] for t in rt) == 2


async def test_single_room_phase_stays_exact_not_allocated(hass, manager, monkeypatch):
    """[SOPT-9] a single-room phase is the exact case: allocated=False, no
    allocation_group_size — unchanged by RP-013b's group-split logic."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:09:00Z")
    samples = [
        {"t": "2026-01-01T00:00:00Z", "cleaning_time": 0, "cleaning_area": 0.0, "battery": 90},
        {"t": "2026-01-01T00:01:00Z", "cleaning_time": 60, "cleaning_area": 3.0, "battery": 88},
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z", "ended_at": None,
        "phases": [_phase(5, "kitchen")],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}],
        "queue_room_ids": [5],
        "counter_samples": samples,
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt = job["phases"][0]["room_timing"]

    assert len(rt) == 1
    assert rt[0]["allocated"] is False
    assert "allocation_group_size" not in rt[0]
    assert rt[0]["cleaning_seconds"] == 60 and rt[0]["area_m2"] == 3.0


async def test_phase_scoped_ids_win_over_job_whole_run_queue(hass, manager, monkeypatch):
    """[SOPT-10] REC-2: phase 1's OWN resolved_rooms (room 9) is credited even though the
    job's whole-run queue_room_ids still begins with room 4 (phase 0's room)."""
    clock = iter(["2026-01-01T00:03:00Z", "2026-01-01T00:05:00Z"])
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: next(clock))
    samples = [
        {"t": "2026-01-01T00:03:10Z", "cleaning_time": 10, "cleaning_area": 0.5, "battery": 89},
        {"t": "2026-01-01T00:04:00Z", "cleaning_time": 40, "cleaning_area": 2.0, "battery": 86},
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "started_at": "2026-01-01T00:00:00Z", "ended_at": None,
        "phases": [
            {**_phase(4, "hall"), "_timing_end_t": "2026-01-01T00:03:00Z", "room_timing": [{"room_id": 4}]},
            _phase(9, "office"),
        ],
        "current_phase_index": 1,
        "resolved_rooms": [{"room_id": r, "slug": s} for r, s in [(4, "hall"), (5, "mid"), (9, "office")]],
        "queue_room_ids": [4, 5, 9],  # whole-run queue still starts with room 4
        "counter_samples": samples,
    }
    _seed_job(manager, job)

    manager.phase_runner._capture_finishing_phase_timing(_VAC, _MAP, job)
    rt1 = job["phases"][1]["room_timing"]

    assert [t["room_id"] for t in rt1] == [9]
    assert rt1[0]["allocated"] is False


# ---------------------------------------------------------------------------
# live:PHASE-ATTR-1 — a phase's counters are progress since THAT phase started
# ---------------------------------------------------------------------------

def test_phase_progress_rebases_on_a_reset_that_lags_into_the_slice():
    """[SOPT-15] The counters reset per PHASE, and the two do not reset together.

    MEASURED on hardware (job_2026-08-04T19-37-52, recorder series frozen at
    tests/fixtures/replays/alfred_phase_attr_1.json). Phase 2 dispatched at
    02:43:27Z and cleaning_time reset 2.0 -> 0.0 that same second — but a counter
    sample is appended whenever EITHER sensor changes and carries the other one
    forward, so the slice's opening samples still quoted kitchen's stale 2 m2 for
    two more polls before cleaning_area caught up and dropped to 1 m2.

    A baseline read at the slice EDGE cannot see a reset that lands inside the
    slice. The room that owned the reset — Entryway — was recorded as
    0 s / 0.0 m2 across a 90 s window it demonstrably cleaned, and that zero went
    into learning with allocated=False, i.e. as a genuine observation.

    Real numbers, so this cannot pass on a shape alone: phase 2 swept 0 -> 6 m2
    in 390 s. cleaning_area is quantised to a hard 1 m2, so the m2 figures below
    are the device's own integers, not a scale I chose.
    """
    prior = [
        _cs("2026-08-05T02:39:18Z", 60, 1.0),
        _cs("2026-08-05T02:40:18Z", 120, 2.0),   # kitchen's last reading
    ]
    # cleaning_time resets at the boundary; cleaning_area lags two polls behind it.
    slice_samples = [
        _cs("2026-08-05T02:43:28Z", 0, 2.0),     # ct reset, area still kitchen's
        _cs("2026-08-05T02:44:33Z", 30, 2.0),
        _cs("2026-08-05T02:45:03Z", 60, 1.0),    # area finally resets, INSIDE the slice
        _cs("2026-08-05T02:46:03Z", 120, 2.0),
        _cs("2026-08-05T02:50:50Z", 390, 6.0),
    ]
    out = phase_runner_mod._phase_progress_samples(prior, slice_samples)

    # Every reading is now progress since the phase began, so the phase total is
    # simply the last one — 390 s and 6 m2, exactly what the device swept.
    assert [s["cleaning_time"] for s in out] == [0.0, 30.0, 60.0, 120.0, 390.0]
    assert [s["cleaning_area"] for s in out] == [0.0, 0.0, 1.0, 2.0, 6.0]

    # The lagging reset is the whole point: the pre-reset stale 2.0 contributes
    # nothing, and the 1 m2 that posts at 02:45:03 is counted as this phase's
    # first square metre rather than being cancelled against kitchen's leftover.
    assert out[2]["cleaning_area"] == 1.0


def test_phase_progress_will_not_invent_a_floor_it_was_never_given():
    """[SOPT-16] An unknown floor is NOT zero, and the difference is a whole run.

    With no pre-phase sample there is no evidence of where the counter stood.
    Assuming zero would re-credit a later phase's opening cumulative reading as
    its first member's work — the exact trap [SOPT-12] pins, where a slice
    opening at 600 s would book 600 s against one room. So the slice's own first
    reading stays the floor, and this phase measures forward from it.
    """
    slice_samples = [
        _cs("2026-01-01T00:00:30Z", 600, 42.0),
        _cs("2026-01-01T00:01:00Z", 630, 43.5),
        _cs("2026-01-01T00:01:30Z", 660, 45.0),
    ]
    out = phase_runner_mod._phase_progress_samples([], slice_samples)
    assert [s["cleaning_time"] for s in out] == [0.0, 30.0, 60.0]
    assert [s["cleaning_area"] for s in out] == [0.0, 1.5, 3.0]


def test_phase_progress_does_not_mutate_the_shared_counter_buffer():
    """[SOPT-17] ``counter_samples`` is the run's ONE buffer and every later phase
    slices it again. Re-basing in place would make each phase's floor depend on
    which phases had already been captured."""
    prior = [_cs("2026-01-01T00:00:30Z", 120, 2.0)]
    original = [_cs("2026-01-01T00:01:00Z", 0, 2.0),
                _cs("2026-01-01T00:01:30Z", 30, 1.0)]
    before = [dict(s) for s in original]
    phase_runner_mod._phase_progress_samples(prior, original)
    assert original == before


def test_rounding_jitter_is_not_a_counter_reset():
    """[SOPT-18] A counter that dips by a hundredth did not reset.

    A bare ``value < prev`` cannot tell a reset from noise, and the two cost very
    different things: a jitter misread as a reset RE-ADDS the whole reading as
    fresh progress, inflating the phase by up to a full quantum.

    This is not hypothetical, and counter_segmentation._AREA_EPS already exists
    for it - its comment records 4 of 7 real boundaries lost to the same effect.
    cleaning_area arrives in whole ~1 m2 device steps, but an imperial HA reports
    them in ft2 (10.76 per step, itself a 2-dp rounding of 10.7639), so a
    nominally exact N m2 comes back as N-0.0007 or N+0.0002 depending on which
    way each step rounded. Plain float arithmetic does it too: 3.0 through a ft2
    round-trip returns 2.9999999999999942, which IS a decrease.

    The value below is that exact round-trip, not a number I chose to be small.
    Without the tolerance this phase measures ~7 m2 of sweeping instead of 4.
    """
    jittered = 3.0 * 10.7639104167097 * 0.09290304   # == 2.9999999999999942
    assert jittered < 3.0, "the premise: this round-trip really does go backwards"

    prior = [_cs("2026-01-01T00:00:00Z", 0, 0.0)]
    slice_samples = [
        _cs("2026-01-01T00:00:30Z", 30, 1.0),
        _cs("2026-01-01T00:01:00Z", 60, 2.0),
        _cs("2026-01-01T00:01:30Z", 90, 3.0),
        _cs("2026-01-01T00:02:00Z", 120, jittered),   # the dip
        _cs("2026-01-01T00:02:30Z", 150, 4.0),
    ]
    out = phase_runner_mod._phase_progress_samples(prior, slice_samples)
    assert round(out[-1]["cleaning_area"], 6) == 4.0
    # The dip itself contributes nothing: the counter did not move, so neither
    # does the total. It must not go DOWN either.
    assert round(out[3]["cleaning_area"], 6) == 3.0
    assert [round(s["cleaning_area"], 6) for s in out] == [1.0, 2.0, 3.0, 3.0, 4.0]
