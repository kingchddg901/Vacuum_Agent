"""Unit tests for counter_segmentation.segment_counters — pure, HA-free.

Synthetic streams mirror the real runs validated in scratch-external-estimator/:
ByRoom plateau boundary, no-mop delayed-step+area-jump transition, multi-pass
turn (flat area, NOT a boundary), single room, reset trim, entry gap.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.eufy_vacuum.counter_segmentation import segment_counters

_BASE = datetime(2026, 6, 6, 21, 54, 0)


def _s(sec: int, ct: float, ca: float, batt=100):
    return {"t": _BASE + timedelta(seconds=sec), "cleaning_time": ct, "cleaning_area": ca, "battery": batt}


def test_empty_stream():
    assert segment_counters([]) == []


def test_no_increments_after_reset():
    # only a reset, never rises -> no segments
    assert segment_counters([_s(0, 0, 0)]) == []


def test_single_room_one_segment():
    samples = [_s(0, 0, 0)] + [_s(30 * i, 30 * i, i, batt=100 - i) for i in range(1, 7)]
    segs = segment_counters(samples)
    assert len(segs) == 1
    seg = segs[0]
    assert seg["index"] == 0
    assert seg["boundary"] == "job_start"
    assert seg["area_delta_m2"] == 6.0
    assert seg["time_active_s"] == 180.0
    # in-room drain = first rise (99) -> last rise (94); the dock->room approach
    # (100 -> 99) is the entry leg, excluded from the room's battery.
    assert seg["battery_delta"] == 5.0


def test_byroom_two_rooms_plateau_boundary():
    """ByRoom wash: a minutes-long plateau splits the job; area lag is tolerated."""
    samples = [
        _s(0, 0, 0),
        _s(60, 30, 1), _s(90, 60, 2), _s(120, 90, 3),
        _s(150, 120, 4), _s(180, 150, 5), _s(210, 180, 6),   # room A: area 0->6
        # 330 s plateau (the inter-room mop wash)
        _s(540, 210, 6),   # room B first rise — area still 6 (lag), boundary is the gap
        _s(570, 240, 8),   # area catches up to 8
    ]
    segs = segment_counters(samples)
    assert len(segs) == 2
    assert segs[0]["area_delta_m2"] == 6.0
    assert segs[1]["area_delta_m2"] == 2.0           # 8 - 6
    assert segs[1]["boundary"] == "wash_plateau"
    assert segs[1]["gap_before_s"] == 330.0          # 540 - 210
    # area + active-time deltas sum back to the job totals
    assert sum(s["area_delta_m2"] for s in segs) == 8.0
    assert sum(s["time_active_s"] for s in segs) == 240.0


def test_nomop_transition_delayed_step_area_jump():
    """No wash: a ~40 s delayed step WITH an area jump is a room transition."""
    samples = [
        _s(0, 0, 0),
        _s(60, 30, 1), _s(90, 60, 2), _s(120, 90, 3),   # room A: area 0->3
        _s(160, 120, 5),                                 # gap 40s + area 3->5 (+2) => transition
        _s(190, 150, 6), _s(220, 180, 7),                # room B
    ]
    segs = segment_counters(samples)
    assert len(segs) == 2
    assert segs[1]["boundary"] == "area_jump"
    assert segs[0]["area_delta_m2"] == 3.0


def test_multipass_turn_is_not_a_boundary():
    """A ~40 s delayed step with FLAT area is a pass-turn, not a room boundary."""
    samples = [
        _s(0, 0, 0),
        _s(60, 30, 1), _s(90, 60, 2), _s(120, 90, 3), _s(150, 120, 4),  # pass 1: area 0->4
        _s(190, 150, 4),                                                  # gap 40s, area flat => turn
        _s(220, 180, 4), _s(250, 210, 4),                                # pass 2: re-covering, area flat
    ]
    segs = segment_counters(samples)
    assert len(segs) == 1                       # one room, two passes
    assert segs[0]["area_delta_m2"] == 4.0      # true area, not doubled
    assert segs[0]["time_active_s"] == 210.0    # full active clean across both passes


def test_drops_stale_pre_reset_value():
    """A stale (270, 6) carried from the prior job is ignored; segmenting starts
    at the reset to 0."""
    samples = [
        _s(0, 270, 6),    # stale pre-reset
        _s(30, 0, 0),     # job-start reset
        _s(90, 30, 1), _s(120, 60, 2),
    ]
    segs = segment_counters(samples)
    assert len(segs) == 1
    assert segs[0]["area_start_m2"] == 0.0
    assert segs[0]["area_delta_m2"] == 2.0
    # gap_before of the first segment = reset (30s) -> first rise (90s) = entry leg
    assert segs[0]["gap_before_s"] == 60.0


def test_area_lag_same_timestamp_not_undercounted():
    """cleaning_area packets that land at the same timestamp as (but after) the
    cleaning_time tick must still count toward the room. Reproduces the run5
    porting bug: carry-forward gave room 1 = 2 m²; area_at(t) gives the true 3."""
    samples = [
        _s(0, 0, 0),
        _s(30, 30, 1), _s(60, 60, 2),
        _s(120, 90, 2),   # ct ticks to 90 still carrying the old area (lag)
        _s(120, 90, 3),   # area packet for 3 lands at the same timestamp
        # >90 s plateau -> room 2
        _s(450, 120, 3), _s(480, 150, 5),
    ]
    segs = segment_counters(samples)
    assert len(segs) == 2
    assert segs[0]["area_delta_m2"] == 3.0          # includes the lagging tick
    assert sum(s["area_delta_m2"] for s in segs) == 5.0


def test_accepts_iso_string_timestamps():
    samples = [
        {"t": "2026-06-06T21:54:00", "cleaning_time": 0, "cleaning_area": 0},
        {"t": "2026-06-06T21:54:30Z", "cleaning_time": 30, "cleaning_area": 1},
        {"t": "2026-06-06T21:55:00+00:00", "cleaning_time": 60, "cleaning_area": 2},
    ]
    segs = segment_counters(samples)
    assert len(segs) == 1
    assert segs[0]["area_delta_m2"] == 2.0
