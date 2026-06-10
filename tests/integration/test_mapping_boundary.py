"""Phase 10 integration tests — mapping/boundary.py geometry utilities.

Coverage targets
----------------
[MB-1]  douglas_peucker preserves endpoints for any polyline.
[MB-2]  douglas_peucker returns original points when fewer than 3.
[MB-3]  douglas_peucker simplifies a collinear line to two endpoints.
[MB-4]  douglas_peucker preserves peaks that exceed epsilon.
[MB-5]  detect_corners returns empty for fewer than 3 points.
[MB-6]  detect_corners detects right-angle corners in a square.
[MB-7]  detect_corners returns no corners for a straight polyline.
[MB-8]  process_boundary_trail.valid=False when trail is shorter than MIN_TRAIL_POINTS.
[MB-9]  process_boundary_trail returns valid result for a sufficient trail.
[MB-10] process_boundary_trail result has all required keys.
[MB-11] point_in_polygon returns True for interior point.
[MB-12] point_in_polygon returns False for exterior point.
[MB-13] point_in_polygon returns False for degenerate polygon (fewer than 3 points).
[MB-14] score_transition_candidate returns (0.0, False) for tiny/degenerate polygon.
[MB-15] score_transition_candidate corridor aspect ratio triggers is_candidate=True.
[MB-16] score_transition_candidate normal square room → is_candidate=False.
[MB-17] _distance_point_to_segment returns 0 for point on segment.
[MB-18] _angle_between_segments returns ~90° for perpendicular segments.
"""

from __future__ import annotations

import math

import pytest

from custom_components.eufy_vacuum.mapping.boundary import (
    _angle_between_segments,
    _distance_point_to_segment,
    detect_corners,
    douglas_peucker,
    point_in_polygon,
    process_boundary_trail,
    score_transition_candidate,
)


# ---------------------------------------------------------------------------
# [MB-1] / [MB-2] / [MB-3] / [MB-4] douglas_peucker
# ---------------------------------------------------------------------------

def test_dp_preserves_endpoints():
    """[MB-1] The first and last point are always in the result."""
    points = [(0, 0), (5, 2), (10, 0), (15, 3), (20, 0)]
    result = douglas_peucker(points, epsilon=1.0)
    assert result[0] == points[0]
    assert result[-1] == points[-1]


def test_dp_returns_original_when_fewer_than_3():
    """[MB-2] Fewer than 3 points → original list returned unchanged."""
    assert douglas_peucker([], epsilon=5.0) == []
    assert douglas_peucker([(0, 0)], epsilon=5.0) == [(0, 0)]
    assert douglas_peucker([(0, 0), (10, 0)], epsilon=5.0) == [(0, 0), (10, 0)]


def test_dp_collinear_reduces_to_endpoints():
    """[MB-3] All collinear points collapse to just the two endpoints."""
    points = [(float(x), 0.0) for x in range(11)]
    result = douglas_peucker(points, epsilon=0.01)
    assert len(result) == 2
    assert result[0] == (0.0, 0.0)
    assert result[-1] == (10.0, 0.0)


def test_dp_preserves_peak_exceeding_epsilon():
    """[MB-4] A spike clearly above epsilon is kept in the result."""
    # Flat line with a spike at x=5
    points = [(0.0, 0.0), (3.0, 0.0), (5.0, 20.0), (7.0, 0.0), (10.0, 0.0)]
    result = douglas_peucker(points, epsilon=1.0)
    assert (5.0, 20.0) in result


def test_dp_drops_peak_below_epsilon():
    """[MB-4] A tiny perturbation below epsilon is removed."""
    points = [(0.0, 0.0), (5.0, 0.1), (10.0, 0.0)]
    result = douglas_peucker(points, epsilon=1.0)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# [MB-5] / [MB-6] / [MB-7] detect_corners
# ---------------------------------------------------------------------------

def test_detect_corners_empty_for_fewer_than_3_points():
    """[MB-5] detect_corners returns [] when fewer than 3 points."""
    assert detect_corners([]) == []
    assert detect_corners([(0, 0), (1, 1)]) == []


def test_detect_corners_finds_square_corners():
    """[MB-6] A square's 4 vertices all qualify as corners at 90°."""
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    corners = detect_corners(square, angle_threshold=45.0)
    assert len(corners) == 4


def test_detect_corners_suppressed_by_high_threshold():
    """[MB-7] A threshold above 180° suppresses all corner detection."""
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    corners = detect_corners(square, angle_threshold=181.0)
    assert len(corners) == 0


# ---------------------------------------------------------------------------
# [MB-8] / [MB-9] / [MB-10] process_boundary_trail
# ---------------------------------------------------------------------------

def test_process_trail_invalid_for_short_trail():
    """[MB-8] valid=False and error key present when trail is shorter than MIN_TRAIL_POINTS."""
    result = process_boundary_trail([(0.0, 0.0), (1.0, 1.0)])
    assert result["valid"] is False
    assert "error" in result
    assert result["simplified_boundary"] == []


def test_process_trail_valid_for_sufficient_trail():
    """[MB-9] valid=True for a trail with enough points."""
    trail = [(float(x), 0.0) for x in range(10)]
    result = process_boundary_trail(trail)
    assert result["valid"] is True


def test_process_trail_has_required_keys():
    """[MB-10] Result always contains all required output keys."""
    trail = [(float(x), float(x % 3)) for x in range(10)]
    result = process_boundary_trail(trail)
    required = {
        "simplified_boundary", "corners", "point_count_raw",
        "point_count_simplified", "corner_count", "epsilon", "valid",
    }
    assert required.issubset(result.keys())


def test_process_trail_raw_count_matches_input():
    """[MB-10] point_count_raw equals the original trail length."""
    trail = [(float(i), float(i)) for i in range(8)]
    result = process_boundary_trail(trail)
    assert result["point_count_raw"] == 8


def test_process_trail_simplified_boundary_is_list_of_pairs():
    """[MB-10] simplified_boundary is a list of [x, y] pairs."""
    trail = [(float(i), 0.0) for i in range(10)]
    result = process_boundary_trail(trail)
    for pt in result["simplified_boundary"]:
        assert len(pt) == 2


# ---------------------------------------------------------------------------
# [MB-11] / [MB-12] / [MB-13] point_in_polygon
# ---------------------------------------------------------------------------

_SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]


def test_point_in_polygon_interior():
    """[MB-11] A point clearly inside the square returns True."""
    assert point_in_polygon((5.0, 5.0), _SQUARE) is True


def test_point_in_polygon_exterior():
    """[MB-12] A point clearly outside the square returns False."""
    assert point_in_polygon((20.0, 20.0), _SQUARE) is False


def test_point_in_polygon_degenerate():
    """[MB-13] Polygon with fewer than 3 points → False."""
    assert point_in_polygon((5.0, 5.0), [[0.0, 0.0], [10.0, 10.0]]) is False
    assert point_in_polygon((5.0, 5.0), []) is False


# ---------------------------------------------------------------------------
# [MB-14] / [MB-15] / [MB-16] score_transition_candidate
# ---------------------------------------------------------------------------

def test_score_degenerate_polygon_returns_zero_false():
    """[MB-14] Small/degenerate polygon → score=0.0, is_candidate=False."""
    score, is_candidate = score_transition_candidate([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
    assert score == 0.0
    assert is_candidate is False


def test_score_corridor_triggers_candidate():
    """[MB-15] A very elongated bounding box (corridor) → is_candidate=True."""
    # 1 unit wide, 20 units long → aspect ratio = 20
    corridor = [[0.0, 0.0], [1.0, 0.0], [1.0, 20.0], [0.0, 20.0]]
    score, is_candidate = score_transition_candidate(corridor)
    assert is_candidate is True
    assert score > 0.0


def test_score_normal_room_not_candidate():
    """[MB-16] A roughly square room → is_candidate=False."""
    # 10×10 square
    room = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    score, is_candidate = score_transition_candidate(room)
    assert is_candidate is False


def test_score_returns_tuple_of_float_and_bool():
    """[MB-16] Return type is always (float, bool)."""
    result = score_transition_candidate(_SQUARE)
    assert isinstance(result[0], float)
    assert isinstance(result[1], bool)


# ---------------------------------------------------------------------------
# [MB-17] _distance_point_to_segment
# ---------------------------------------------------------------------------

def test_distance_point_on_segment_is_zero():
    """[MB-17] Distance is 0 when point lies exactly on the segment."""
    dist = _distance_point_to_segment((5.0, 0.0), (0.0, 0.0), (10.0, 0.0))
    assert dist == pytest.approx(0.0, abs=1e-9)


def test_distance_point_perpendicular_to_segment():
    """[MB-17] Perpendicular distance is computed correctly."""
    dist = _distance_point_to_segment((5.0, 3.0), (0.0, 0.0), (10.0, 0.0))
    assert dist == pytest.approx(3.0, abs=1e-9)


def test_distance_degenerate_segment():
    """[MB-17] Degenerate segment (zero length) returns point distance."""
    dist = _distance_point_to_segment((3.0, 4.0), (0.0, 0.0), (0.0, 0.0))
    assert dist == pytest.approx(5.0, abs=1e-9)


# ---------------------------------------------------------------------------
# [MB-18] _angle_between_segments
# ---------------------------------------------------------------------------

def test_angle_90_degrees():
    """[MB-18] Right-angle bend between two perpendicular segments → ~90°."""
    # p1→vertex is horizontal, vertex→p2 is vertical
    angle = _angle_between_segments((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
    assert angle == pytest.approx(90.0, abs=0.5)


def test_angle_collinear_same_direction_is_180():
    """[MB-18] Collinear same-direction vectors → 180° (no bend = maximum direction-change value)."""
    angle = _angle_between_segments((0.0, 0.0), (5.0, 0.0), (10.0, 0.0))
    assert angle == pytest.approx(180.0, abs=1.0)


def test_angle_zero_for_degenerate_segments():
    """[MB-18] Degenerate zero-length segment → returns 0.0."""
    angle = _angle_between_segments((5.0, 5.0), (5.0, 5.0), (10.0, 5.0))
    assert angle == 0.0


def test_score_sliver_area_guard_blocks_corridor_false_positive():
    """[MB-14b] A 4+ vertex near-zero-area sliver → score=0.0, is_candidate=False.

    This clears the line-314 vertex-count guard (4 vertices) but is rejected by
    the poly_area < 1.0 degenerate-area guard. The sliver's bounding box has
    aspect_ratio = 5.0 (0.5 wide / 0.1 tall), which alone would set
    is_candidate=True via the >=3.5 corridor signal — so this asserts the area
    guard actively suppresses a false-positive corridor classification, not
    merely that a degenerate shape returns zero.
    """
    # 4 vertices clears the count guard; shoelace area = 0.05 < 1.0;
    # aspect_ratio = 0.5 / 0.1 = 5.0 would otherwise trip the corridor signal.
    sliver = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.1], [0.0, 0.1]]
    score, is_candidate = score_transition_candidate(sliver)
    assert score == 0.0
    assert is_candidate is False

