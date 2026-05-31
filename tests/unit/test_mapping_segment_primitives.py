"""Unit tests for mapping/segment_primitives.py — pure geometry + numpy-backed
mask primitives (numpy-dependent tests skip if numpy is unavailable).

Coverage targets
----------------
[SP-1]  bbox_from_stats: returns int-coerced bbox dict.
[SP-2]  rdp: <= 2 points returns a copy.
[SP-3]  rdp: collinear polyline simplifies to endpoints.
[SP-4]  rdp: a peak beyond epsilon is preserved.
[SP-5]  rdp: closed polyline (start == end) keeps the far point.
[SP-6]  polygon_area: < 3 points → 0.0.
[SP-7]  polygon_area: shoelace area of a square.
[SP-8]  normalize_polygon: rounds to 2dp, returns nested lists.
[SP-9]  compactness: non-positive area/perimeter → 0.0.
[SP-10] compactness: square isoperimetric quotient ≈ 0.785.
[SP-11] aspect_ratio: square=1, elongated>1, zero dim → 0.
[SP-12] image_runtime_capabilities: reports all libraries + pipeline_ready.
[SP-13] mask_perimeter: solid 3x3 block → 12; empty → 0.
[SP-14] mask_to_polygon: solid block → non-empty polygon; empty mask → ([], 0).
[SP-15] mask_iou: identical=1.0, disjoint=0.0, shape mismatch=0.0.
[SP-16] agreement_score: overlap fraction; None assist → 0.0.
[SP-17] component_overlap_ratio: per-mask overlap fractions.
[SP-18] mask_left_right_counts: left/right pixel split.
[SP-19] estimate_alignment: identical masks → score 1.0 at scale 1.0.
"""

from __future__ import annotations

import math

import pytest

from custom_components.eufy_vacuum.mapping.segment_primitives import (
    aspect_ratio,
    agreement_score,
    bbox_from_stats,
    compactness,
    component_overlap_ratio,
    estimate_alignment,
    image_runtime_capabilities,
    mask_iou,
    mask_left_right_counts,
    mask_perimeter,
    mask_to_polygon,
    normalize_polygon,
    polygon_area,
    rdp,
)


@pytest.fixture
def np():
    """numpy module, or skip the test if it is not installed."""
    return pytest.importorskip("numpy")


# ---------------------------------------------------------------------------
# Pure geometry (no numpy)
# ---------------------------------------------------------------------------

def test_bbox_from_stats():
    """[SP-1]"""
    assert bbox_from_stats(1.0, 2.0, 3.0, 4.0) == {"x": 1, "y": 2, "width": 3, "height": 4}


def test_rdp_short_returns_copy():
    """[SP-2]"""
    pts = [(0.0, 0.0), (1.0, 1.0)]
    out = rdp(pts, 0.1)
    assert out == pts and out is not pts


def test_rdp_collinear():
    """[SP-3]"""
    assert rdp([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)], 0.1) == [(0.0, 0.0), (2.0, 2.0)]


def test_rdp_keeps_peak():
    """[SP-4]"""
    out = rdp([(0.0, 0.0), (1.0, 5.0), (2.0, 0.0)], 0.1)
    assert (1.0, 5.0) in out


def test_rdp_closed_polyline():
    """[SP-5] start == end; the far middle point is retained."""
    out = rdp([(0.0, 0.0), (3.0, 4.0), (0.0, 0.0)], 0.1)
    assert (3.0, 4.0) in out


def test_polygon_area_too_few():
    """[SP-6]"""
    assert polygon_area([(0.0, 0.0), (1.0, 1.0)]) == 0.0


def test_polygon_area_square():
    """[SP-7]"""
    square = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    assert polygon_area(square) == pytest.approx(4.0)


def test_normalize_polygon():
    """[SP-8]"""
    out = normalize_polygon([(1.234, 5.678), (9.0, 0.0)])
    assert out == [[1.23, 5.68], [9.0, 0.0]]
    assert all(isinstance(p, list) for p in out)


def test_compactness_zero():
    """[SP-9]"""
    assert compactness(0, 10) == 0.0
    assert compactness(10, 0) == 0.0


def test_compactness_square():
    """[SP-10] area 100, perimeter 40 → 4πA/P²."""
    assert compactness(100, 40) == pytest.approx(4 * math.pi * 100 / 1600)


@pytest.mark.parametrize("w,h,expected", [(5, 5, 1.0), (10, 5, 2.0), (0, 5, 0.0)])
def test_aspect_ratio(w, h, expected):
    """[SP-11]"""
    assert aspect_ratio(w, h) == pytest.approx(expected)


def test_image_runtime_capabilities_shape():
    """[SP-12]"""
    caps = image_runtime_capabilities()
    for lib in ("numpy", "pillow", "scipy", "scipy_ndimage"):
        assert lib in caps
        assert "available" in caps[lib]
    assert "pipeline_ready" in caps


# ---------------------------------------------------------------------------
# numpy-backed mask primitives
# ---------------------------------------------------------------------------

def test_mask_perimeter(np):
    """[SP-13]"""
    mask = np.zeros((6, 6), dtype=bool)
    mask[1:4, 1:4] = True  # solid 3x3
    assert mask_perimeter(mask) == 12
    assert mask_perimeter(np.zeros((4, 4), dtype=bool)) == 0


def test_mask_to_polygon(np):
    """[SP-14]"""
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 2:6] = True  # solid 4x4
    polygon, raw_count = mask_to_polygon(mask)
    assert raw_count > 0
    assert len(polygon) >= 4
    assert all(len(pt) == 2 for pt in polygon)
    # empty mask
    assert mask_to_polygon(np.zeros((5, 5), dtype=bool)) == ([], 0)


def test_mask_iou(np):
    """[SP-15]"""
    a = np.zeros((4, 4), dtype=bool)
    a[1:3, 1:3] = True
    assert mask_iou(a, a) == pytest.approx(1.0)
    b = np.zeros((4, 4), dtype=bool)
    b[0, 0] = True
    assert mask_iou(a, b) == 0.0
    assert mask_iou(a, np.zeros((5, 5), dtype=bool)) == 0.0  # shape mismatch


def test_agreement_score(np):
    """[SP-16]"""
    comp = np.zeros((4, 4), dtype=bool)
    comp[0:2, 0:2] = True  # area 4
    assist = np.zeros((4, 4), dtype=bool)
    assist[0:2, 0:1] = True  # overlaps 2 of 4
    assert agreement_score(comp, assist) == pytest.approx(0.5)
    assert agreement_score(comp, None) == 0.0


def test_component_overlap_ratio(np):
    """[SP-17]"""
    a = np.zeros((4, 4), dtype=bool)
    a[0:2, 0:2] = True  # area 4
    b = np.zeros((4, 4), dtype=bool)
    b[0:1, 0:2] = True  # area 2, overlap 2
    ra, rb = component_overlap_ratio(a, b)
    assert ra == pytest.approx(0.5)  # 2/4
    assert rb == pytest.approx(1.0)  # 2/2


def test_mask_left_right_counts(np):
    """[SP-18]"""
    mask = np.zeros((2, 4), dtype=bool)
    mask[:, 0] = True   # left half
    mask[:, 3] = True   # right half
    counts = mask_left_right_counts(mask)
    assert counts == {"left": 2, "right": 2}


def test_estimate_alignment_identical(np):
    """[SP-19] requires scipy.ndimage for the zoom in the non-unit-scale search grid."""
    pytest.importorskip("scipy.ndimage")
    ref = np.zeros((20, 20), dtype=bool)
    ref[6:12, 6:12] = True
    result = estimate_alignment(ref, ref.copy())
    assert result["score"] == pytest.approx(1.0)
    assert result["scale"] == pytest.approx(1.0)
