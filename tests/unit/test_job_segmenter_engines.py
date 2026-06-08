"""Unit tests for learning/job_segmenter_engines.py — the pluggable job-segmenter seam.

Coverage targets
----------------
[JE-1]  get_job_segmenter_engine: resolves a registered engine by name.
[JE-2]  get_job_segmenter_engine: absent name (None/"") -> Eufy fallback (legacy default).
[JE-3]  get_job_segmenter_engine: unknown name -> Eufy fallback (NOT noop).
[JE-4]  known_job_engine_names includes the registered engines.
[JE-5]  noop engine resolves and every stage returns [].
[JE-6]  EufyCounterSegmenter.DEFAULT_TUNING == the counter_segmentation module constants.
[JE-7]  Eufy engine fidelity: find_candidates / build_segments / segment_legacy ==
        the counter_segmentation primitives byte-for-byte, across a battery of streams.
[JE-8]  validate_tuning: non-dict, unknown key, bad value, and valid cases.
[JE-9]  partial tuning merges over DEFAULT_TUNING (unspecified keys keep defaults).
[JE-10] noop validate_tuning rejects any tuning keys.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.eufy_vacuum.counter_segmentation import (
    _AREA_JUMP_M2,
    _CADENCE_S,
    _GAP_DELAYED_S,
    _GAP_PLATEAU_S,
    _GAP_TRANSIT_S,
    build_segments,
    find_candidates,
    segment_counters,
    select_active,
)
from custom_components.eufy_vacuum.learning.job_segmenter_engines import (
    EufyCounterSegmenter,
    NoopJobSegmenter,
    get_job_segmenter_engine,
    known_job_engine_names,
)

_BASE = datetime(2026, 6, 6, 21, 54, 0)


def _s(sec: int, ct: float, ca: float, batt=100):
    return {"t": _BASE + timedelta(seconds=sec), "cleaning_time": ct, "cleaning_area": ca, "battery": batt}


# A battery of representative streams (mirrors test_counter_segmentation.py): single
# room, ByRoom plateau, no-mop area-jump, forward-area-across-dock, multi-pass turn,
# edge-to-fill over-split, two-candidate strongest-wins.
_STREAMS: list[list[dict]] = [
    # single room
    [_s(0, 0, 0)] + [_s(30 * i, 30 * i, i, batt=100 - i) for i in range(1, 7)],
    # ByRoom two-room plateau
    [
        _s(0, 0, 0),
        _s(60, 30, 1), _s(90, 60, 2), _s(120, 90, 3),
        _s(150, 120, 4), _s(180, 150, 5), _s(210, 180, 6),
        _s(540, 210, 6), _s(570, 240, 8),
    ],
    # no-mop delayed-step + area-jump transition
    [
        _s(0, 0, 0),
        _s(60, 30, 1), _s(90, 60, 2), _s(120, 90, 3),
        _s(160, 120, 5),
        _s(190, 150, 6), _s(220, 180, 7),
    ],
    # forward-area attribution across a dock
    [
        _s(0, 0, 0),
        _s(30, 30, 0), _s(60, 60, 1),
        _s(280, 90, 3),
        _s(310, 120, 4), _s(340, 150, 5),
    ],
    # multi-pass turn (flat area, one room)
    [
        _s(0, 0, 0),
        _s(60, 30, 1), _s(90, 60, 2), _s(120, 90, 3), _s(150, 120, 4),
        _s(190, 150, 4),
        _s(220, 180, 4), _s(250, 210, 4),
    ],
    # edge-to-fill over-split (needs expected_rooms to collapse)
    [
        _s(0, 0, 0),
        _s(30, 30, 1),
        _s(70, 60, 1), _s(100, 90, 2), _s(130, 120, 3), _s(160, 150, 4),
    ],
    # two candidates, strongest wins under expected_rooms=2
    [
        _s(0, 0, 0),
        _s(30, 30, 1),
        _s(70, 60, 2),
        _s(100, 90, 3), _s(130, 120, 4),
        _s(175, 150, 5),
        _s(205, 180, 7), _s(235, 210, 9),
    ],
]


# --- registry ---------------------------------------------------------------


def test_resolves_registered_engine():
    """[JE-1]"""
    engine = get_job_segmenter_engine("eufy_counter_v1")
    assert isinstance(engine, EufyCounterSegmenter)
    assert engine.engine_name == "eufy_counter_v1"


def test_absent_name_falls_back_to_eufy():
    """[JE-2] None and "" both route to the Eufy engine (legacy default)."""
    assert isinstance(get_job_segmenter_engine(None), EufyCounterSegmenter)
    assert isinstance(get_job_segmenter_engine(""), EufyCounterSegmenter)


def test_unknown_name_falls_back_to_eufy():
    """[JE-3] a genuinely unregistered name falls back to Eufy, NOT noop."""
    engine = get_job_segmenter_engine("totally_made_up")
    assert isinstance(engine, EufyCounterSegmenter)


def test_known_engine_names():
    """[JE-4]"""
    known = known_job_engine_names()
    assert "eufy_counter_v1" in known
    assert "noop_job_fallback" in known


def test_noop_engine_returns_empty():
    """[JE-5] the noop engine resolves and every stage returns []."""
    engine = get_job_segmenter_engine("noop_job_fallback")
    assert isinstance(engine, NoopJobSegmenter)
    stream = _STREAMS[1]
    assert engine.find_candidates(stream) == []
    assert engine.build_segments(stream, []) == []
    assert engine.segment_legacy(stream, expected_rooms=2) == []


# --- byte-identical guarantees ----------------------------------------------


def test_default_tuning_matches_module_constants():
    """[JE-6] the dedup single-source equals the primitives' own kwarg defaults."""
    assert EufyCounterSegmenter.DEFAULT_TUNING == {
        "gap_delayed_s": _GAP_DELAYED_S,
        "gap_transit_s": _GAP_TRANSIT_S,
        "gap_plateau_s": _GAP_PLATEAU_S,
        "area_jump_m2": _AREA_JUMP_M2,
        "cadence_s": _CADENCE_S,
    }


def test_find_candidates_fidelity():
    """[JE-7] engine.find_candidates == module find_candidates, with and without tuning."""
    engine = EufyCounterSegmenter()
    for stream in _STREAMS:
        expected = find_candidates(stream)
        assert engine.find_candidates(stream) == expected
        assert engine.find_candidates(stream, tuning=EufyCounterSegmenter.DEFAULT_TUNING) == expected


def test_build_segments_fidelity():
    """[JE-7] engine.build_segments == module build_segments for a chosen active set."""
    engine = EufyCounterSegmenter()
    for stream in _STREAMS:
        active = select_active(
            find_candidates(stream), default="all", kinds={"wash_plateau", "area_jump"}
        )
        assert engine.build_segments(stream, active) == build_segments(stream, active)


def test_segment_legacy_fidelity():
    """[JE-7] engine.segment_legacy == module segment_counters across expected_rooms."""
    engine = EufyCounterSegmenter()
    for stream in _STREAMS:
        for expected_rooms in (None, 1, 2, 3):
            assert engine.segment_legacy(stream, expected_rooms=expected_rooms) == segment_counters(
                stream, expected_rooms=expected_rooms
            )


# --- tuning validation ------------------------------------------------------


def test_validate_tuning_rejects_non_dict():
    """[JE-8]"""
    assert EufyCounterSegmenter().validate_tuning("nope") == ["job_segmenter.tuning must be a dict"]


def test_validate_tuning_flags_unknown_key():
    """[JE-8]"""
    issues = EufyCounterSegmenter().validate_tuning({"bogus": 1})
    assert any("unknown tuning key" in m and "bogus" in m for m in issues)


def test_validate_tuning_flags_bad_values():
    """[JE-8] non-positive, non-number, and bool values are rejected."""
    engine = EufyCounterSegmenter()
    assert engine.validate_tuning({"gap_plateau_s": -5})
    assert engine.validate_tuning({"gap_plateau_s": "x"})
    assert engine.validate_tuning({"cadence_s": True})  # bool is not a valid number here


def test_validate_tuning_accepts_valid():
    """[JE-8]"""
    assert EufyCounterSegmenter().validate_tuning({}) == []
    assert EufyCounterSegmenter().validate_tuning({"gap_plateau_s": 120, "area_jump_m2": 1.5}) == []


def test_partial_tuning_merges_over_defaults():
    """[JE-9] a single-key override is applied while the rest keep defaults.

    The ByRoom stream's 330 s boundary is a ``wash_plateau`` at default
    ``gap_plateau_s=90``. Raise *only* ``gap_plateau_s`` above the gap: the boundary
    is no longer a wash, but the +2 m² still trips ``area_jump`` because
    ``area_jump_m2`` kept its default — proving the partial dict merged over the
    defaults rather than replacing them."""
    engine = EufyCounterSegmenter()
    stream = _STREAMS[1]

    default_cands = engine.find_candidates(stream)
    assert [c["kind"] for c in default_cands] == ["wash_plateau"]

    overridden = engine.find_candidates(stream, tuning={"gap_plateau_s": 400})
    assert [c["kind"] for c in overridden] == ["area_jump"]


def test_noop_validate_tuning_rejects_keys():
    """[JE-10]"""
    assert NoopJobSegmenter().validate_tuning({}) == []
    assert NoopJobSegmenter().validate_tuning({"gap_plateau_s": 90})
