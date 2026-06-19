"""Unit tests for mapping/map_source.py — the brand-agnostic map_state_source reader core.

Pure functions (no HA): synthetic room_pixels raster, anchor normalization, the Roborock
parsed-map path, and the presence gate.

[MS-1] rooms_from_room_pixels: per-room bbox+name, Y-flip, catch-all (rid 32) filtered.
[MS-2] normalize_rendered: Y-flip + clamp.
[MS-3] anchors_from_storage: dock/robot normalized; absent when missing.
[MS-4] rooms_from_parsed_map: parser Room bbox -> normalized, flagged approximate.
[MS-5] build_map_source_result: presence gate (absent vs populated).
"""
import base64

from custom_components.eufy_vacuum.mapping.map_source import (
    OVERLAY_VISIBILITY_DEFAULTS,
    anchors_from_storage,
    build_map_source_result,
    current_room_from_storage,
    normalize_rendered,
    overlays_from_storage,
    path_from_storage,
    resolve_overlay_visibility,
    rooms_from_parsed_map,
    rooms_from_room_pixels,
    _decimate_step,
)


def _raster(w, h, blocks):
    """blocks: list of (rid, x0, x1, y0, y1). Returns base64 byte-per-pixel (rid<<2)."""
    buf = bytearray(w * h)
    for rid, x0, x1, y0, y1 in blocks:
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                buf[yy * w + xx] = (rid << 2)
    return base64.b64encode(bytes(buf)).decode()


def test_rooms_from_room_pixels():
    """[MS-1]"""
    md = {
        "width": 10, "height": 10, "resolution": 5,
        "room_outline_width": 10, "room_outline_height": 10,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_names": {"1": "Kitchen", "2": "Office"},
        "room_pixels": _raster(10, 10, [
            (1, 0, 2, 0, 2),     # top-left 3x3
            (2, 5, 7, 5, 7),     # mid 3x3
            (32, 0, 9, 9, 9),    # catch-all row -> must be filtered
        ]),
    }
    rooms = rooms_from_room_pixels(md)
    by_id = {r["number"]: r for r in rooms}
    assert set(by_id) == {1, 2}                      # rid 32 filtered
    assert by_id[1]["name"] == "Kitchen"
    assert by_id[2]["name"] == "Office"
    assert by_id[1]["pixel_count"] == 9
    # rid 1 covers px 0-2, py 0-2; Y-flip -> image y in [0.7, 0.9]
    assert by_id[1]["bbox"] == [0.0, 0.7, 0.2, 0.9]
    assert by_id[2]["bbox"] == [0.5, 0.2, 0.7, 0.4]


def test_rooms_from_room_pixels_empty():
    """[MS-1b] no segmentation -> empty list."""
    assert rooms_from_room_pixels({"width": 10, "height": 10}) == []
    assert rooms_from_room_pixels({"room_pixels": "", "width": 10, "height": 10}) == []


def test_normalize_rendered():
    """[MS-2]"""
    assert normalize_rendered(0, 0, 10, 10) == [0.0, 0.9]      # top-left grid -> bottom image
    assert normalize_rendered(9, 9, 10, 10) == [0.9, 0.0]
    assert normalize_rendered(-5, 99, 10, 10) == [0.0, 0.0]    # clamps
    assert normalize_rendered(5, 5, 0, 0) == [0.0, 0.0]        # degenerate dims


def test_anchors_from_storage():
    """[MS-3]"""
    data = {
        "map_data": {"width": 10, "height": 10},
        "dock_pixel": [5, 5],
        "robot_trail": [[1, 1], [8, 8]],
    }
    a = anchors_from_storage(data)
    assert a["dock_anchor"] == [0.5, 0.4]
    assert a["robot_anchor"] == [0.8, 0.1]
    assert anchors_from_storage({"map_data": {"width": 10, "height": 10}}) == {}


class _Room:
    def __init__(self, x0, y0, x1, y1, number, name):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.number, self.name = number, name


def test_rooms_from_parsed_map():
    """[MS-4]"""
    rooms = rooms_from_parsed_map(
        {3: _Room(10, 20, 30, 40, 3, "Kitchen")}, 100, 100,
    )
    assert len(rooms) == 1
    r = rooms[0]
    assert r["number"] == 3 and r["name"] == "Kitchen"
    assert r["approximate"] is True
    assert r["bbox"] == [0.1, 0.59, 0.3, 0.79]
    assert rooms_from_parsed_map([], 100, 100) == []
    assert rooms_from_parsed_map({3: _Room(0, 0, 1, 1, 3, "x")}, 0, 0) == []


def test_build_map_source_result():
    """[MS-5]"""
    assert build_map_source_result(present=False, backend="storage")["present"] is False
    assert build_map_source_result(present=True, backend="memory", rooms=[])["present"] is False
    out = build_map_source_result(
        present=True, backend="storage",
        rooms=[{"number": 1, "name": "K", "bbox": [0, 0, 1, 1]}],
        anchors={"dock_anchor": [0.5, 0.5]},
    )
    assert out["present"] is True and out["backend"] == "storage"
    assert out["rooms"][0]["number"] == 1
    assert out["dock_anchor"] == [0.5, 0.5]


# --- review-driven gap closes (adversarial review 2026-06-18) -------------------

def test_rooms_from_room_pixels_outline_offset():
    """[MS-1c] non-zero room_outline offset (the proven inverse transform) IS applied —
    pins the single most regression-prone coordinate math (a sign flip mislocates rooms)."""
    md = {
        "width": 10, "height": 10, "resolution": 5,
        "room_outline_width": 10, "room_outline_height": 10,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": -10, "room_outline_origin_y": -10,  # -> ro_dx=ro_dy=2
        "room_names": {"1": "Kitchen"},
        "room_pixels": _raster(10, 10, [(1, 0, 2, 0, 2)]),
    }
    rooms = rooms_from_room_pixels(md)
    assert len(rooms) == 1
    # outline px (0,0)-(2,2) -> main grid (2,2)-(4,4) -> normalized (Y-flip)
    assert rooms[0]["bbox"] == [0.2, 0.5, 0.4, 0.7]


def test_rooms_from_room_pixels_bad_base64():
    """[MS-1d] malformed room_pixels degrades to [] (never crashes) per the contract."""
    md = {"room_pixels": "abc", "width": 10, "height": 10,
          "room_outline_width": 10, "room_outline_height": 10}
    assert rooms_from_room_pixels(md) == []


def test_rooms_from_room_pixels_truncated_buffer():
    """[MS-1e] a room_pixels buffer shorter than ro_w*ro_h returns the rooms that fit,
    no crash."""
    buf = bytearray(50)  # only 5 of 10 rows present
    for yy in range(3):
        for xx in range(3):
            buf[yy * 10 + xx] = (1 << 2)
    md = {"width": 10, "height": 10, "resolution": 5,
          "room_outline_width": 10, "room_outline_height": 10,
          "origin_x": 0, "origin_y": 0,
          "room_outline_origin_x": 0, "room_outline_origin_y": 0,
          "room_names": {"1": "K"},
          "room_pixels": base64.b64encode(bytes(buf)).decode()}
    rooms = rooms_from_room_pixels(md)
    assert [r["number"] for r in rooms] == [1]
    assert rooms[0]["pixel_count"] == 9


def test_rooms_from_room_pixels_name_fallback():
    """[MS-1f] a rid absent from room_names gets the deterministic 'Room N' name."""
    md = {"width": 10, "height": 10, "resolution": 5,
          "room_outline_width": 10, "room_outline_height": 10,
          "origin_x": 0, "origin_y": 0,
          "room_outline_origin_x": 0, "room_outline_origin_y": 0,
          "room_names": {}, "room_pixels": _raster(10, 10, [(7, 0, 1, 0, 1)])}
    assert rooms_from_room_pixels(md)[0]["name"] == "Room 7"


def test_rooms_from_parsed_map_no_flip_and_missing_coord():
    """[MS-4b] flip_y=False uses raw normalization; a Room missing a coord is skipped."""
    rooms = rooms_from_parsed_map({3: _Room(10, 20, 30, 40, 3, "K")}, 100, 100, flip_y=False)
    assert rooms[0]["bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert rooms_from_parsed_map({3: _Room(None, 20, 30, 40, 3, "K")}, 100, 100) == []


def test_anchors_from_storage_non_numeric():
    """[MS-3b] non-numeric dock/robot coords are skipped, not crashed."""
    data = {"map_data": {"width": 10, "height": 10},
            "dock_pixel": ["a", "b"], "robot_trail": [["x", "y"]]}
    assert anchors_from_storage(data) == {}


def test_build_map_source_result_reason_and_anchors():
    """[MS-5b] reason propagates on the absent path; present path omits reason + anchors."""
    assert build_map_source_result(
        present=False, backend="x", reason="ver_mismatch")["reason"] == "ver_mismatch"
    assert build_map_source_result(present=False, backend="x")["reason"] == "no_segmentation"
    out = build_map_source_result(
        present=True, backend="storage",
        rooms=[{"number": 1, "name": "K", "bbox": [0, 0, 1, 1]}])
    assert "reason" not in out
    assert "dock_anchor" not in out and "robot_anchor" not in out


def test_build_map_source_result_extra_merged():
    """[MS-5c] the `extra` overlay layers merge into the present payload."""
    out = build_map_source_result(
        present=True, backend="memory",
        rooms=[{"number": 1, "name": "K", "bbox": [0, 0, 1, 1]}],
        extra={"current_room": 1, "path": [[0.0, 0.0]], "no_go": []},
    )
    assert out["current_room"] == 1 and out["path"] == [[0.0, 0.0]]
    assert out["no_go"] == []


# --- Wave 3a Eufy overlays (area / current-room / path) -------------------------

def _md(blocks, **over):
    """A minimal Eufy map_data block with a room_pixels raster (origin offsets 0)."""
    md = {
        "width": 10, "height": 10, "resolution": 5,
        "room_outline_width": 10, "room_outline_height": 10,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_names": {}, "room_pixels": _raster(10, 10, blocks),
    }
    md.update(over)
    return md


def test_rooms_area_m2():
    """[MS-6] per-room area = pixel_count × (res_cm/100)²; res=5 → 400 px = 1.0 m²."""
    md = {
        "width": 20, "height": 20, "resolution": 5,
        "room_outline_width": 20, "room_outline_height": 20,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_names": {}, "room_pixels": _raster(20, 20, [(1, 0, 19, 0, 19)]),
    }
    room = rooms_from_room_pixels(md)[0]
    assert room["pixel_count"] == 400
    assert room["area_m2"] == 1.0


def test_current_room_from_storage():
    """[MS-7] robot pixel -> exact room id by raster lookup; off-map -> None."""
    data = {"map_data": _md([(5, 2, 2, 2, 2)]), "robot_trail": [[1, 1], [2, 2]]}
    assert current_room_from_storage(data) == 5
    assert current_room_from_storage(
        {"map_data": _md([(5, 2, 2, 2, 2)]), "robot_trail": [[50, 50]]}) is None
    assert current_room_from_storage({"map_data": _md([(5, 2, 2, 2, 2)])}) is None


def test_path_from_storage():
    """[MS-8] robot_trail -> normalized polyline; the latest point is always kept."""
    data = {"map_data": _md([(1, 0, 0, 0, 0)]), "robot_trail": [[0, 0], [5, 5], [9, 9]]}
    assert path_from_storage(data) == [[0.0, 0.9], [0.5, 0.4], [0.9, 0.0]]
    assert path_from_storage({"map_data": _md([(1, 0, 0, 0, 0)])}) == []


def test_path_from_storage_decimates_but_keeps_last():
    """[MS-8b] a long trail is decimated to <= max_points and still ends at the latest."""
    trail = [[i % 10, 0] for i in range(1000)] + [[7, 7]]
    data = {"map_data": _md([(1, 0, 0, 0, 0)]), "robot_trail": trail}
    path = path_from_storage(data, max_points=50)
    assert len(path) <= 52
    assert path[-1] == normalize_rendered(7, 7, 10, 10)


def test_overlays_from_storage_bundle():
    """[MS-9] overlays bundle current_room + path; hazards omitted (empty on device)."""
    data = {"map_data": _md([(5, 2, 2, 2, 2)]), "robot_trail": [[2, 2]]}
    ov = overlays_from_storage(data)
    assert ov["current_room"] == 5
    assert ov["path"] == [normalize_rendered(2, 2, 10, 10)]
    assert ov["image_size"] == [10, 10]   # for the card's letterbox correction
    assert "no_go" not in ov and "walls" not in ov


# --- Wave 3b visibility contract + decimation cap ------------------------------

def test_resolve_overlay_visibility():
    """[MS-10] stored deltas merge over defaults; unknown keys ignored; None -> defaults."""
    base = resolve_overlay_visibility(None)
    assert base == OVERLAY_VISIBILITY_DEFAULTS
    assert base is not OVERLAY_VISIBILITY_DEFAULTS          # a copy, not the shared dict
    merged = resolve_overlay_visibility({"no_go": True, "robot": False, "bogus": True})
    assert merged["no_go"] is True and merged["robot"] is False
    assert merged["room_labels"] is True                   # default preserved
    assert "bogus" not in merged
    # truthy/falsy coerced to real booleans
    assert resolve_overlay_visibility({"path": 1})["path"] is True
    assert resolve_overlay_visibility("nonsense") == OVERLAY_VISIBILITY_DEFAULTS


def test_decimate_step_hard_caps():
    """[MS-11] ceil stride truly caps the sample count (the soft `//` bug fix)."""
    assert _decimate_step(180, 160) == 2        # was 1 (kept all 180) under //
    assert _decimate_step(100, 160) == 1        # below cap -> keep all
    assert _decimate_step(1001, 50) == 21       # ceil(1001/50)
    assert _decimate_step(0, 160) == 1 and _decimate_step(10, 0) == 1  # degenerate
