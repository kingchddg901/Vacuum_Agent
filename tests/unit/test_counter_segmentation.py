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


def test_forward_area_attribution_across_dock():
    """cleaning_area lags: a short room's m² can finish posting DURING the dock after
    it. Across a wash_plateau we forward-read to the next room's start, so the lagged
    area lands on the right (short) room instead of inflating the next one. (This is
    the live vac-bathroom case: 1 m² at its last tick -> 3 m² by the next room's start.)"""
    samples = [
        _s(0, 0, 0),
        _s(30, 30, 0), _s(60, 60, 1),        # room A: ct 0->60, only 1 m² posted by its last tick
        _s(280, 90, 3),                       # 220s dock (wash_plateau): A's area finishes 1->3
        _s(310, 120, 4), _s(340, 150, 5),     # room B: area 3->5
    ]
    segs = segment_counters(samples)
    assert len(segs) == 2
    assert segs[1]["boundary"] == "wash_plateau"
    assert segs[0]["area_delta_m2"] == 3.0   # forward-read captured A's dock-lagged m² (not 1.0)
    assert segs[1]["area_delta_m2"] == 2.0   # room B: 5 - 3, not inflated


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


def test_path_varied_boundary_uses_forward_area():
    """The boundary's area is FLAT at the instant (a Narrow room that re-covered);
    the next room's area only climbs a tick later. The FORWARD look still splits it
    — the old same-instant rule returned 1 segment here (the production bug fixed in
    W6.1, reproduced from the multi-setting external run)."""
    samples = [
        _s(0, 0, 0),
        # room 1: area 0->3 then plateaus (Narrow re-covers the rest of the room)
        _s(30, 30, 1), _s(60, 60, 2), _s(90, 90, 3),
        _s(120, 120, 3), _s(150, 150, 3), _s(180, 180, 3),
        # boundary: 43 s delayed step, area STILL 3 at the instant (the area lag)
        _s(223, 210, 3),
        # room 2: area now climbs 3->8
        _s(253, 240, 4), _s(283, 270, 5), _s(313, 300, 6), _s(343, 330, 8),
    ]
    segs = segment_counters(samples)   # blind (external) — no expected_rooms
    assert len(segs) == 2
    assert segs[0]["area_delta_m2"] == 3.0
    assert segs[1]["area_delta_m2"] == 5.0
    assert segs[1]["boundary"] == "area_jump"


def test_expected_rooms_caps_edge_to_fill_oversplit():
    """A single room cleaned edges-then-fill: area crawls to 1 m² on the edge pass,
    a turn, then the fill climbs 1->4. The counters can't tell this from a boundary
    (area rises after the gap either way), so blind it over-splits; the dispatched
    queue count (expected_rooms=1) keeps it one room."""
    samples = [
        _s(0, 0, 0),
        _s(30, 30, 1),                                       # edge pass: area -> 1
        _s(70, 60, 1), _s(100, 90, 2), _s(130, 120, 3), _s(160, 150, 4),  # fill: 1->4
    ]
    assert len(segment_counters(samples)) == 2                     # blind over-splits
    capped = segment_counters(samples, expected_rooms=1)
    assert len(capped) == 1                                        # queue count fixes it
    assert capped[0]["area_delta_m2"] == 4.0


def test_expected_rooms_keeps_strongest_boundary():
    """When more boundaries are found than the queue allows, the strongest (largest
    forward area-rise) wins. Two real split candidates, expected_rooms=2 -> keep the
    one with the bigger forward jump, demote the weaker to in-segment."""
    samples = [
        _s(0, 0, 0),
        _s(30, 30, 1),
        _s(70, 60, 2),                       # gap 40 -> phase B (forward area +2: weak)
        _s(100, 90, 3), _s(130, 120, 4),
        _s(175, 150, 5),                     # gap 45 -> phase C (forward area +4: strong)
        _s(205, 180, 7), _s(235, 210, 9),
    ]
    segs = segment_counters(samples, expected_rooms=2)
    assert len(segs) == 2
    # the split lands at the strong jump (the C boundary), not the weak B turn
    assert segs[0]["area_delta_m2"] == 4.0
    assert segs[1]["area_delta_m2"] == 5.0
