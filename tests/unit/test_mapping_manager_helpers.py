"""Unit tests for mapping/manager.py module-level helpers — pure functions,
no HA dependency. (The MappingManager class itself is integration-tested.)

Coverage targets
----------------
[MM-1]  _vacuum_slug: strips domain, lowercases; no-dot passthrough.
[MM-2]  _safe_int / _safe_float: coercion + default fallback.
[MM-3]  _deep_merge_dict: recursive nested merge.
[MM-4]  _display_label: slug → Title Case; empty/separator-only → None.
[MM-5]  _clean_text: stripped string or None.
[MM-6]  _percentile_trim: < min samples unchanged; else trims P10/P90 outliers.
[MM-7]  _clean_string_list: non-list → []; drops empty entries.
[MM-8]  _normalize_point: rounds valid pair; bad length/non-numeric → None.
[MM-9]  _normalize_image_variant: default primary; normalizes separators/case.
[MM-10] _image_variant_role: dark→segmentation, light→boundary, else primary.
[MM-11] _normalize_segment_adjustments: non-dict → {}; no-op payload skipped; valid kept.
[MM-12] _adjust_polygon_pixel: translation, edge nudges, vertex moves; bad input filtered.
[MM-13] _bbox_from_polygon_pixel: empty → None; inclusive width/height.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.mapping.manager import (
    _adjust_polygon_pixel,
    _bbox_from_polygon_pixel,
    _clean_string_list,
    _clean_text,
    _deep_merge_dict,
    _display_label,
    _image_variant_role,
    _normalize_image_variant,
    _normalize_point,
    _normalize_segment_adjustments,
    _percentile_trim,
    _safe_float,
    _safe_int,
    _vacuum_slug,
)


# ---------------------------------------------------------------------------
# Small coercion helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entity,expected", [
    ("vacuum.Alfred", "alfred"), ("alfred", "alfred"), ("vacuum.kitchen_bot", "kitchen_bot"),
])
def test_vacuum_slug(entity, expected):
    """[MM-1]"""
    assert _vacuum_slug(entity) == expected


def test_safe_int_float():
    """[MM-2]"""
    assert _safe_int("3.9") == 3
    assert _safe_int("x", 5) == 5
    assert _safe_float("2.5") == pytest.approx(2.5)
    assert _safe_float("x") is None
    assert _safe_float("x", 1.0) == pytest.approx(1.0)


def test_deep_merge_dict():
    """[MM-3]"""
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    updates = {"nested": {"y": 20, "z": 30}, "b": 2}
    out = _deep_merge_dict(base, updates)
    assert out == {"a": 1, "nested": {"x": 1, "y": 20, "z": 30}, "b": 2}
    assert base["nested"] == {"x": 1, "y": 2}  # base untouched


@pytest.mark.parametrize("value,expected", [
    ("living_room", "Living Room"), ("kitchen-nook", "Kitchen Nook"),
    ("", None), ("   ", None), ("__-_", None),
])
def test_display_label(value, expected):
    """[MM-4]"""
    assert _display_label(value) == expected


def test_clean_text():
    """[MM-5]"""
    assert _clean_text("  hi ") == "hi"
    assert _clean_text("") is None
    assert _clean_text(None) is None


# ---------------------------------------------------------------------------
# _percentile_trim
# ---------------------------------------------------------------------------

def test_percentile_trim_below_min():
    """[MM-6] fewer than the minimum sample count → unchanged."""
    samples = [(float(i), float(i)) for i in range(5)]
    assert _percentile_trim(samples) == samples


def test_percentile_trim_drops_outliers():
    """[MM-6] 10 samples → P10 cut removes the extreme low corner."""
    samples = [(float(i), float(i)) for i in range(10)]
    out = _percentile_trim(samples)
    assert (0.0, 0.0) not in out
    assert len(out) == 9


# ---------------------------------------------------------------------------
# list / point normalization
# ---------------------------------------------------------------------------

def test_clean_string_list():
    """[MM-7]"""
    assert _clean_string_list("nope") == []
    assert _clean_string_list(["a", "", "  ", "b"]) == ["a", "b"]


@pytest.mark.parametrize("value,expected", [
    ([1.234, 5.678], [1.23, 5.68]),
    ((1, 2), [1.0, 2.0]),
    ([1, 2, 3], None),
    ("xy", None),
    (["a", "b"], None),
])
def test_normalize_point(value, expected):
    """[MM-8]"""
    assert _normalize_point(value) == expected


@pytest.mark.parametrize("value,expected", [
    (None, "primary"), ("", "primary"), ("Dark Mode", "dark_mode"), ("light-x", "light_x"),
])
def test_normalize_image_variant(value, expected):
    """[MM-9]"""
    assert _normalize_image_variant(value) == expected


@pytest.mark.parametrize("variant,role", [
    ("dark", "segmentation"), ("light", "boundary"), ("primary", "primary"), ("other", "primary"),
])
def test_image_variant_role(variant, role):
    """[MM-10]"""
    assert _image_variant_role(variant) == role


# ---------------------------------------------------------------------------
# _normalize_segment_adjustments
# ---------------------------------------------------------------------------

def test_segment_adjustments_non_dict():
    """[MM-11]"""
    assert _normalize_segment_adjustments("nope") == {}


def test_segment_adjustments_skips_noop():
    """[MM-11] a payload with no offsets/edges/vertex moves is dropped."""
    assert _normalize_segment_adjustments({"seg": {}}) == {}


def test_segment_adjustments_valid():
    """[MM-11]"""
    out = _normalize_segment_adjustments({
        "seg1": {
            "offset_x": 5, "offset_y": -2,
            "vertex_moves": [
                {"index": 0, "delta_x": 1, "delta_y": 0},
                {"index": -1, "delta_x": 9, "delta_y": 9},   # bad index dropped
                {"index": 2, "delta_x": 0, "delta_y": 0},    # no delta dropped
                "not-a-dict",
            ],
        },
    })
    assert "seg1" in out
    assert out["seg1"]["offset_x"] == 5
    assert out["seg1"]["vertex_moves"] == [{"index": 0, "delta_x": 1, "delta_y": 0}]
    assert "updated_at" in out["seg1"]


# ---------------------------------------------------------------------------
# _adjust_polygon_pixel
# ---------------------------------------------------------------------------

_SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]


def _adjust(**kw):
    base = dict(offset_x=0, offset_y=0, edge_left=0, edge_right=0,
                edge_top=0, edge_bottom=0, vertex_moves=None)
    base.update(kw)
    return _adjust_polygon_pixel(_SQUARE, **base)


def test_adjust_polygon_translation():
    """[MM-12]"""
    out = _adjust(offset_x=5)
    assert out[0] == [5, 0]
    assert out[1] == [15, 0]


def test_adjust_polygon_edge_nudge():
    """[MM-12] edge_right shifts only the points in the right band."""
    out = _adjust(edge_right=3)
    assert out[1] == [13, 0]   # x=10 is in the right band
    assert out[0] == [0, 0]    # x=0 is not


def test_adjust_polygon_vertex_move():
    """[MM-12]"""
    out = _adjust(vertex_moves=[{"index": 0, "delta_x": 1, "delta_y": 2}])
    assert out[0] == [1, 2]


def test_adjust_polygon_bad_input():
    """[MM-12]"""
    assert _adjust_polygon_pixel("nope", offset_x=0, offset_y=0, edge_left=0,
                                 edge_right=0, edge_top=0, edge_bottom=0) == []
    # bad points are filtered out
    out = _adjust_polygon_pixel([[0, 0], "x", [10, 10]], offset_x=0, offset_y=0,
                                edge_left=0, edge_right=0, edge_top=0, edge_bottom=0)
    assert len(out) == 2


# ---------------------------------------------------------------------------
# _bbox_from_polygon_pixel
# ---------------------------------------------------------------------------

def test_bbox_from_polygon_empty():
    """[MM-13]"""
    assert _bbox_from_polygon_pixel([]) is None


def test_bbox_from_polygon():
    """[MM-13] inclusive width/height (+1)."""
    bbox = _bbox_from_polygon_pixel([[0, 0], [10, 0], [10, 5]])
    assert bbox == {"x": 0, "y": 0, "width": 11, "height": 6}
