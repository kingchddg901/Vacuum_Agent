"""Unit tests for the decomposed segmenter primitives — pure, HA-free.

find_candidates / select_active / build_segments back the server-side
re-segmentation of external runs (the wizard's user-set room count + per-boundary
toggle). These lock the NEW behavior the legacy segment_counters wrapper hides:
the transit boundary (60-90 s flat-area gap), strength ranking, count selection
from the enlarged pool, explicit boundary sets, and additive area attribution.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.eufy_vacuum.counter_segmentation import (
    build_segments,
    find_candidates,
    segment_counters,
    select_active,
)

_BASE = datetime(2026, 6, 7, 0, 0, 0)


def _c(sec: int, ct: float, ca: float, batt: int = 100) -> dict:
    return {"t": _BASE + timedelta(seconds=sec), "cleaning_time": ct, "cleaning_area": ca, "battery": batt}


def _kinds(cands):
    return [c["kind"] for c in cands]


# --- find_candidates: kinds --------------------------------------------------

def test_find_candidates_wash_plateau():
    # gap 240 s -> wash_plateau (confident), regardless of area.
    cands = find_candidates([_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(300, 90, 2), _c(330, 120, 3)])
    assert len(cands) == 1
    assert cands[0]["kind"] == "wash_plateau"
    assert cands[0]["confident"] is True


def test_find_candidates_transit_60_to_90_flat():
    # gap 70 s with FLAT area to the next blip -> transit (the recovered case).
    cands = find_candidates([
        _c(0, 0, 0),
        _c(30, 30, 1), _c(60, 60, 2),     # room A -> 2 m²
        _c(130, 90, 2),                   # gap 70, area flat
        _c(160, 120, 2), _c(190, 150, 2),  # next room's area still lagging
    ])
    assert len(cands) == 1
    assert cands[0]["kind"] == "transit"
    assert cands[0]["confident"] is False
    assert cands[0]["gap_s"] == 70.0


def test_find_candidates_area_jump():
    # gap 45 s but area rises >= 2 forward -> area_jump.
    cands = find_candidates([
        _c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2),
        _c(105, 90, 2), _c(135, 120, 4), _c(165, 150, 5),  # forward area 2 -> 5 (+3)
    ])
    assert len(cands) == 1
    assert cands[0]["kind"] == "area_jump"


def test_find_candidates_weak_below_transit_gap():
    # gap 45 s with flat area -> weak (NOT transit; transit needs gap > 60).
    cands = find_candidates([
        _c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2),
        _c(105, 90, 2), _c(135, 120, 2),  # gap 45, area flat
    ])
    assert len(cands) == 1
    assert cands[0]["kind"] == "weak"


def test_find_candidates_strength_orders_kinds():
    wash = find_candidates([_c(0, 0, 0), _c(30, 30, 1), _c(300, 60, 1), _c(330, 90, 1)])[0]
    transit = find_candidates([_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(130, 90, 2), _c(160, 120, 2), _c(190, 150, 2)])[0]
    area_jump = find_candidates([_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(105, 90, 2), _c(135, 120, 4), _c(165, 150, 5)])[0]
    weak = find_candidates([_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(105, 90, 2), _c(135, 120, 2)])[0]
    assert wash["strength"] > transit["strength"] > area_jump["strength"] > weak["strength"]


# --- the 4-candidate flat stream: wash + 2 transit + weak --------------------

def _four_candidate_stream():
    return [
        _c(0, 0, 0),
        _c(30, 30, 3), _c(60, 60, 3), _c(90, 90, 3),   # A
        _c(300, 120, 3),                                # wash (gap 210)
        _c(330, 150, 3), _c(360, 180, 3),               # B
        _c(430, 210, 3),                                # transit (gap 70)
        _c(460, 240, 3), _c(490, 270, 3),               # C
        _c(560, 300, 3),                                # transit (gap 70)
        _c(590, 330, 3),
        _c(635, 360, 3),                                # weak (gap 45)
        _c(665, 390, 3),
    ]


def test_select_active_default_confident_only_wash():
    cands = find_candidates(_four_candidate_stream())
    assert _kinds(cands) == ["wash_plateau", "transit", "transit", "weak"]
    active = select_active(cands, default="confident")
    assert _kinds(active) == ["wash_plateau"]
    assert len(build_segments(_four_candidate_stream(), active)) == 2


def test_select_active_count_uses_enlarged_pool():
    # expected_rooms=4 reaches 4 rooms by activating transits the LEGACY filter drops.
    stream = _four_candidate_stream()
    cands = find_candidates(stream)
    active = select_active(cands, expected_rooms=4)
    assert len(active) == 3                                   # 4 rooms -> 3 boundaries
    assert "transit" in _kinds(active)                        # transits recovered
    assert len(build_segments(stream, active)) == 4
    # the legacy wrapper can only see the wash -> 2 rooms (proves the recovery).
    assert len(segment_counters(stream)) == 2


def test_select_active_explicit_ids_and_unknown_ignored():
    stream = _four_candidate_stream()
    cands = find_candidates(stream)
    transit_ids = [c["id"] for c in cands if c["kind"] == "transit"]
    active = select_active(cands, active_ids=transit_ids)
    assert _kinds(active) == ["transit", "transit"]
    assert len(build_segments(stream, active)) == 3
    # empty set -> one room; unknown ids -> ignored (one room).
    assert len(build_segments(stream, select_active(cands, active_ids=[]))) == 1
    assert len(build_segments(stream, select_active(cands, active_ids=[9999]))) == 1


# --- build_segments: additive area attribution across regroup ----------------

def test_build_segments_area_additive_across_regroup():
    stream = [
        _c(0, 0, 0),
        _c(30, 30, 2), _c(60, 60, 4),    # A
        _c(105, 90, 6), _c(135, 120, 8),  # B (area_jump at t105)
        _c(180, 150, 10), _c(210, 180, 12),  # C (area_jump at t180)
    ]
    cands = find_candidates(stream)
    assert _kinds(cands) == ["area_jump", "area_jump"]

    both = build_segments(stream, select_active(cands, active_ids=[c["id"] for c in cands]))
    first_only = build_segments(stream, select_active(cands, active_ids=[cands[0]["id"]]))

    assert [s["area_delta_m2"] for s in both] == [4.0, 4.0, 4.0]
    assert [s["area_delta_m2"] for s in first_only] == [4.0, 8.0]   # B+C merged
    # the active set changes per-room area but never the total.
    assert sum(s["area_delta_m2"] for s in both) == sum(s["area_delta_m2"] for s in first_only) == 12.0


def test_build_segments_boundary_id_round_trips():
    stream = _four_candidate_stream()
    cands = find_candidates(stream)
    active = select_active(cands, expected_rooms=4)
    segs = build_segments(stream, active)
    assert segs[0]["boundary_id"] is None                       # first room has no boundary
    active_ids = [s["boundary_id"] for s in segs if s["boundary_id"] is not None]
    assert active_ids == [c["id"] for c in active]              # recoverable from segments
