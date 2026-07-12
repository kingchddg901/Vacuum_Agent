"""Unit tests for mapping/mapping_services.py pure helpers — segment adjustment
application and the segments-response builder. (Service handlers are async +
hass-bound and covered separately.)

Coverage targets
----------------
[MS-1]  _apply_segment_adjustments: empty adjustments → unchanged list.
[MS-2]  _apply_segment_adjustments: matching adjustment translates polygon + tags issues.
[MS-3]  _apply_segment_adjustments: all-zero adjustment leaves the segment unchanged.
[MS-4]  _apply_segment_adjustments: non-dict segment passed through.
[MS-5]  _build_segments_response: non-dict image_segments → returned as-is.
[MS-6]  _build_segments_response: room links inject room_id onto segments.
[MS-7]  _build_segments_response: companion_anchors always present; cache not mutated.
[MS-8]  _safe_int / _bbox_from_polygon_pixel / _adjust_polygon_pixel smoke.
[MS-11] _bbox_from_polygon_pixel: empty polygon → None.
[MS-12] _adjust_polygon_pixel: non-list / malformed-point / unparseable guards.
[MS-13] _adjust_polygon_pixel: valid vertex move applies; bad/out-of-range moves ignored.
[MS-14] _apply_segment_adjustments: edge nudges + vertex moves set their manual-adjustment flags.
[MS-15] _apply_segment_adjustments: non-numeric center logged and left unchanged (no crash).
[MS-16] _build_segments_response: non-dict segment_room_links / companion_anchors coerced to {}.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.mapping.mapping_services import (
    _adjust_polygon_pixel,
    _apply_segment_adjustments,
    _bbox_from_polygon_pixel,
    _build_segments_response,
    _safe_int,
)


# ---------------------------------------------------------------------------
# _apply_segment_adjustments
# ---------------------------------------------------------------------------

def _segment() -> dict:
    return {
        "segment_id": "s1",
        "polygon_pixel": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "center_pixel": [5, 5],
        "issues": [],
    }


def test_apply_empty_adjustments():
    """[MS-1]"""
    segs = [_segment()]
    assert _apply_segment_adjustments(segs, {}) is segs


def test_apply_translation():
    """[MS-2]"""
    out = _apply_segment_adjustments([_segment()], {"s1": {"offset_x": 5, "offset_y": 0}})
    seg = out[0]
    assert seg["polygon_pixel"][0] == [5, 0]
    assert seg["translation_offset"] == [5, 0]
    assert "translated_manual" in seg["issues"]
    assert seg["center_pixel"] == [10.0, 5.0]


def test_apply_zero_adjustment_noop():
    """[MS-3]"""
    seg = _segment()
    out = _apply_segment_adjustments([seg], {"s1": {"offset_x": 0, "offset_y": 0}})
    assert out[0] is seg  # unchanged, same object


def test_apply_non_dict_segment():
    """[MS-4]"""
    out = _apply_segment_adjustments(["not-a-dict"], {"s1": {"offset_x": 5}})
    assert out == ["not-a-dict"]


# ---------------------------------------------------------------------------
# _build_segments_response
# ---------------------------------------------------------------------------

def test_build_response_non_dict_base():
    """[MS-5]"""
    assert _build_segments_response({"image_segments": "nope"}) == "nope"


def test_build_response_injects_room_id():
    """[MS-6]"""
    bucket = {
        "image_segments": {"segments": [{"segment_id": "s1"}, {"segment_id": "s2"}]},
        "segment_room_links": {"s1": "3"},
    }
    resp = _build_segments_response(bucket)
    by_id = {s["segment_id"]: s for s in resp["segments"]}
    assert by_id["s1"]["room_id"] == "3"
    assert "room_id" not in by_id["s2"]
    # original cache untouched
    assert "room_id" not in bucket["image_segments"]["segments"][0]


def test_build_response_companion_anchors():
    """[MS-7]"""
    bucket = {
        "image_segments": {"segments": []},
        "companion_anchors": {"3": {"pct_x": 0.5, "pct_y": 0.5}},
    }
    resp = _build_segments_response(bucket)
    assert resp["companion_anchors"] == {"3": {"pct_x": 0.5, "pct_y": 0.5}}


def test_build_response_non_dict_overlays_default_empty():
    """[MS-16] non-dict segment_room_links / companion_anchors are coerced to {}."""
    bucket = {
        "image_segments": {"segments": [{"segment_id": "s1"}]},
        "segment_room_links": "nope",     # non-dict → {}
        "companion_anchors": ["bad"],      # non-dict → {}
    }
    resp = _build_segments_response(bucket)
    # links coerced empty → no room_id injected; anchors coerced empty
    assert "room_id" not in resp["segments"][0]
    assert resp["companion_anchors"] == {}


# ---------------------------------------------------------------------------
# Duplicated geometry helpers (smoke)
# ---------------------------------------------------------------------------

def test_helpers_smoke():
    """[MS-8]"""
    assert _safe_int("4") == 4
    assert _safe_int(4.8) == 4          # float truncates
    assert _safe_int("4.8", 7) == 7     # non-int string → default (int(str) is strict)
    assert _safe_int("x", 7) == 7
    # services _bbox uses raw max-min (no +1), unlike the manager variant
    assert _bbox_from_polygon_pixel([[0, 0], [4, 6]]) == {"x": 0, "y": 0, "width": 4, "height": 6}
    out = _adjust_polygon_pixel([[0, 0], [2, 2]], offset_x=1, offset_y=1,
                                edge_left=0, edge_right=0, edge_top=0, edge_bottom=0)
    assert out[0] == [1, 1]


# ---------------------------------------------------------------------------
# Uncovered-branch coverage (guards, lookups, edge/vertex flags)
# ---------------------------------------------------------------------------

_Z = dict(offset_x=0, offset_y=0, edge_left=0, edge_right=0, edge_top=0, edge_bottom=0)


def test_bbox_empty_polygon_is_none():
    """[MS-11] an empty polygon has no bounding box."""
    assert _bbox_from_polygon_pixel([]) is None


def test_adjust_polygon_guards():
    """[MS-12] non-list / malformed-point / unparseable guards."""
    assert _adjust_polygon_pixel("nope", **_Z) == []
    assert _adjust_polygon_pixel([[1, 2], "x", [3]], **_Z) == [[1, 2]]
    assert _adjust_polygon_pixel([["a", "b"]], **_Z) == []


def test_adjust_polygon_vertex_moves():
    """[MS-13] valid vertex move applies; bad/out-of-range moves ignored."""
    out = _adjust_polygon_pixel(
        [[0, 0], [10, 0], [10, 10], [0, 10]], **_Z,
        vertex_moves=[{"index": 0, "delta_x": 5, "delta_y": 5},
                      "notadict",
                      {"index": 99, "delta_x": 1}])
    assert out[0] == [5, 5]
    assert out[1] == [10, 0]


def test_apply_segment_adjustments_edge_and_vertex_flags():
    """[MS-14] edge nudges + vertex moves set their manual-adjustment flags."""
    segs = [{"segment_id": "s1", "polygon_pixel": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "center_pixel": [5, 5], "issues": []}]
    adj = {"s1": {"offset_x": 1, "edge_left": 2,
                  "vertex_moves": [{"index": 0, "delta_x": 1, "delta_y": 1}]}}
    out = _apply_segment_adjustments(segs, adj)[0]
    assert "edge_adjusted_manual" in out["issues"]
    assert "vertex_adjusted_manual" in out["issues"]


def test_apply_segment_adjustments_bad_center_swallowed():
    """[MS-15] a non-numeric center is logged and left unchanged (no crash)."""
    segs = [{"segment_id": "s1", "polygon_pixel": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "center_pixel": ["a", "b"], "issues": []}]
    out = _apply_segment_adjustments(segs, {"s1": {"offset_x": 2}})[0]
    assert out["center_pixel"] == ["a", "b"]
