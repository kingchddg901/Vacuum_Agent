"""Unit tests for mapping/trace_review.py — pure trace-quality evaluation.

Coverage targets
----------------
[TR-1]  _polygon_bbox: empty → None; returns min/max corners.
[TR-2]  _bbox_area: width*height, negative spans clamped to 0.
[TR-3]  _compute_spatial_spread: no inside points → 0.0.
[TR-4]  _compute_spatial_spread: zero-area polygon → 0.0.
[TR-5]  _compute_spatial_spread: sample/poly bbox ratio.
[TR-6]  _compute_path_density_inside: < 2 points → 0.0; else mean neighbor count.
[TR-7]  _compute_entry_exit_ratio: n<2 → 0; fraction of end samples outside.
[TR-8]  _compute_transit_ratio: n<2 → 0; fraction of middle samples outside.
[TR-9]  _count_boundary_crossings: counts inside<->outside flips.
[TR-10] _evaluate_segment_metadata: None/non-dict → neutral defaults.
[TR-11] _evaluate_segment_metadata: strong+confident geometry → negative accept_delta.
[TR-12] _evaluate_segment_metadata: hub/spine/connector role → penalty + force_needs_refine.
[TR-13] _evaluate_segment_metadata: merged/fragmented state → penalty + force_needs_refine.
[TR-14] _evaluate_segment_metadata: lone local_split_suspicion → force_needs_refine, no delta.
[TR-15] review_trace_run: polygon < 3 points → no_polygon error.
[TR-16] review_trace_run: non-list samples → missing_samples error.
[TR-17] review_trace_run: < MIN_SAMPLES_FOR_REVIEW valid points → insufficient_samples.
[TR-18] review_trace_run: clean fully-inside run → accepted.
[TR-19] review_trace_run: mostly-outside run → rejected.
[TR-20] review_trace_run: suspicious metadata forces needs_refine on an otherwise-clean run.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.mapping.trace_review import (
    MIN_SAMPLES_FOR_REVIEW,
    _bbox_area,
    _compute_entry_exit_ratio,
    _compute_path_density_inside,
    _compute_spatial_spread,
    _compute_transit_ratio,
    _count_boundary_crossings,
    _evaluate_segment_metadata,
    _polygon_bbox,
    review_trace_run,
)


_SQUARE = [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def test_polygon_bbox():
    """[TR-1]"""
    assert _polygon_bbox([]) is None
    assert _polygon_bbox(_SQUARE) == (0.0, 0.0, 100.0, 100.0)


def test_bbox_area():
    """[TR-2]"""
    assert _bbox_area((0.0, 0.0, 10.0, 5.0)) == pytest.approx(50.0)
    assert _bbox_area((10.0, 10.0, 0.0, 0.0)) == 0.0  # inverted → clamped


def test_spatial_spread_no_inside():
    """[TR-3]"""
    assert _compute_spatial_spread([], _SQUARE) == 0.0


def test_spatial_spread_zero_area_polygon():
    """[TR-4]"""
    degenerate = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
    assert _compute_spatial_spread([(1.0, 1.0)], degenerate) == 0.0


def test_spatial_spread_ratio():
    """[TR-5] inside bbox 80x80 over poly 100x100 = 0.64."""
    spread = _compute_spatial_spread([(10.0, 10.0), (90.0, 90.0)], _SQUARE)
    assert spread == pytest.approx(0.64)


def test_path_density_inside():
    """[TR-6]"""
    assert _compute_path_density_inside([(0.0, 0.0)], 40.0) == 0.0
    pts = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
    assert _compute_path_density_inside(pts, 7.0) == pytest.approx(1.3333, abs=1e-3)


def test_entry_exit_ratio():
    """[TR-7] 10 samples, window=1 → first+last; both outside → 1.0."""
    membership = [False] + [True] * 8 + [False]
    assert _compute_entry_exit_ratio(membership, 0.12) == pytest.approx(1.0)
    assert _compute_entry_exit_ratio([True], 0.12) == 0.0


def test_transit_ratio():
    """[TR-8] middle (idx1..8) has 2 outside of 8 → 0.25."""
    membership = [True] + [True, True, False, True, False, True, True] + [True, True]
    # n=10, window=1 → middle = membership[1:9] (8 samples), 2 outside
    assert _compute_transit_ratio(membership, 0.12) == pytest.approx(0.25)
    assert _compute_transit_ratio([True], 0.12) == 0.0


def test_boundary_crossings():
    """[TR-9]"""
    assert _count_boundary_crossings([True, True, False, False, True]) == 2
    assert _count_boundary_crossings([True, True, True]) == 0


# ---------------------------------------------------------------------------
# _evaluate_segment_metadata
# ---------------------------------------------------------------------------

def test_metadata_none_neutral():
    """[TR-10]"""
    out = _evaluate_segment_metadata(None)
    assert out["accept_delta"] == 0.0
    assert out["force_needs_refine"] is False
    assert out["adjustments"] == []


def test_metadata_strong_bonus():
    """[TR-11]"""
    out = _evaluate_segment_metadata(
        {"quality": "strong", "confidence": 0.9, "edit_readiness": "ready"})
    assert out["accept_delta"] < 0.0
    assert any("strong_geometry_bonus" in a for a in out["adjustments"])


def test_metadata_suspicious_role():
    """[TR-12]"""
    out = _evaluate_segment_metadata({"structural_role": "hub"})
    assert out["accept_delta"] > 0.0
    assert out["force_needs_refine"] is True


def test_metadata_suspicious_state():
    """[TR-13]"""
    out = _evaluate_segment_metadata({"segmentation_state": "merged_candidate"})
    assert out["accept_delta"] > 0.0
    assert out["force_needs_refine"] is True


def test_metadata_lone_split_suspicion():
    """[TR-14]"""
    out = _evaluate_segment_metadata({"local_split_suspicion": True})
    assert out["force_needs_refine"] is True
    assert out["accept_delta"] == 0.0


# ---------------------------------------------------------------------------
# review_trace_run
# ---------------------------------------------------------------------------

def _run(points: list[tuple[float, float]]) -> dict:
    return {
        "run_id": "r1", "vacuum_entity_id": "vacuum.alfred", "map_id": "6", "room_id": 3,
        "samples": [{"x": x, "y": y, "ts": "2026-01-01T10:00:00+00:00"} for x, y in points],
    }


def _inside_grid() -> list[tuple[float, float]]:
    """12 points spread across the interior of the square."""
    return [
        (10.0, 10.0), (50.0, 10.0), (90.0, 10.0),
        (10.0, 50.0), (50.0, 50.0), (90.0, 50.0),
        (10.0, 90.0), (50.0, 90.0), (90.0, 90.0),
        (30.0, 30.0), (70.0, 70.0), (40.0, 60.0),
    ]


def test_review_no_polygon():
    """[TR-15]"""
    result = review_trace_run(_run(_inside_grid()), [[0.0, 0.0], [1.0, 1.0]])
    assert result["verdict"] == "error"
    assert result["error"] == "no_polygon"


def test_review_missing_samples():
    """[TR-16]"""
    result = review_trace_run({"run_id": "r1", "samples": "nope"}, _SQUARE)
    assert result["error"] == "missing_samples"


def test_review_insufficient_samples():
    """[TR-17]"""
    result = review_trace_run(_run([(10.0, 10.0)] * 3), _SQUARE)
    assert result["error"].startswith("insufficient_samples")
    assert f"minimum {MIN_SAMPLES_FOR_REVIEW}" in result["error"]


def test_review_accepted():
    """[TR-18] a clean, well-spread, fully-inside run is accepted."""
    result = review_trace_run(_run(_inside_grid()), _SQUARE)
    assert result["error"] is None
    assert result["verdict"] == "accepted"
    assert result["diagnostics"]["in_room_ratio"] == pytest.approx(1.0)


def test_review_rejected():
    """[TR-19] a run mostly outside the polygon is rejected."""
    result = review_trace_run(_run([(500.0, 500.0)] * 12), _SQUARE)
    assert result["verdict"] == "rejected"
    assert result["diagnostics"]["reject_reasons"]


def test_review_needs_refine_via_metadata():
    """[TR-20] suspicious polygon metadata forces needs_refine on a clean run."""
    result = review_trace_run(_run(_inside_grid()), _SQUARE,
                              segment_metadata={"structural_role": "hub"})
    assert result["verdict"] == "needs_refine"
