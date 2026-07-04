"""Unit tests for mapping/map_source.py — the brand-agnostic map_state_source reader core.

Pure functions (no HA): synthetic room_pixels raster, anchor normalization, the Roborock
parsed-map path, and the presence gate.

[MS-1] rooms_from_room_pixels: per-room bbox+name, Y-flip, catch-all (rid 32) filtered.
[MS-2] normalize_rendered: Y-flip + clamp.
[MS-3] anchors_from_storage: dock/robot normalized; absent when missing.
[MS-4] rooms_from_parsed_map: parser Room bbox -> normalized, flagged approximate.
[MS-5] build_map_source_result: presence gate (absent vs populated).
[MS-6] rooms_from_room_pixels: per-room area_m2 = pixel_count x (res_cm/100)^2 (400 px @ res=5 -> 1.0 m2).
[MS-7] current_room_from_storage: robot pixel -> exact room id by raster lookup; off-map / no trail -> None.
[MS-8] path_from_storage: robot_trail -> normalized polyline; empty when no trail.
[MS-9] overlays_from_storage: bundles current_room + path + image_size; empty hazard layers omitted.
[MS-10] resolve_overlay_visibility: stored deltas merge over defaults (copy); unknown keys dropped; None -> defaults.
[MS-11] _decimate_step: ceil stride hard-caps the sample count (soft // bug fix); degenerate -> 1.
[MS-12] render_data_from_storage: card-render raster + explicit decode params (dims/offset/flip/rid_shift/version); no seg -> None.
[MS-13] current_room_for_pixel: room id at an arbitrary main-grid pixel; off-map / byte-0 / non-numeric -> None.
[MS-14] live_pose_overlay: in-memory pixel pose -> normalized robot/dock anchors + current-room + heading.
[MS-15] apply_live_pose_override: live pose authoritative for current_room + path; clears stale .storage values; empty overlay = no-op.
[MS-16] mapdata_dict_from_obj: in-memory MapData object -> byte-identical .storage map_data dict; non-MapData -> None.
[MS-17] compare_map_data: normalization_safe iff raster (len+sha1) + geometry match; hazards by count; room_names key-type diff.
[MS-18] eufy_version_of: content version = 12-char sha1 of the raster; stable per map, changes on re-map; no raster -> "".
[MS-19] vacuum_to_normalized: vacuum-frame point -> main grid ((v-origin)/res) then rendered normalization; non-numeric/bool/no-dims -> None.
[MS-20] hazards_from_mapdata: device hazard layers -> normalized overlays (walls/no_go/no_mop); degenerate/scalar-drift degrade, never raise.
"""
import base64
from types import SimpleNamespace

from custom_components.eufy_vacuum.mapping.map_source import (
    OVERLAY_VISIBILITY_DEFAULTS,
    anchors_from_storage,
    apply_live_pose_override,
    build_map_source_result,
    compare_map_data,
    current_room_for_pixel,
    current_room_from_storage,
    eufy_version_of,
    hazards_from_mapdata,
    live_pose_overlay,
    mapdata_dict_from_obj,
    normalize_rendered,
    normalize_trail,
    overlays_from_storage,
    vacuum_to_normalized,
    path_from_storage,
    render_data_from_storage,
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
    # Real-world box dims from the pixel extent x resolution (res=5cm): 3 cells -> 0.15 m.
    assert by_id[1]["width_m"] == 0.15 and by_id[1]["height_m"] == 0.15


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
    """[MS-1c] non-zero room_outline offset IS applied with the VERIFIED sign — pins the
    single most regression-prone coordinate math. ro_dx = (room_outline_origin - origin)/res:
    outline origin -10 is +10 cm right of the map origin -20, so ro_dx=ro_dy=+2. (On a real
    X10 map this sign overlays the segmentation floor on the rendered floor at ~93%; the
    inverted sign gives <1% — rooms slide off-grid.)"""
    md = {
        "width": 10, "height": 10, "resolution": 5,
        "room_outline_width": 10, "room_outline_height": 10,
        "origin_x": -20, "origin_y": -20,
        "room_outline_origin_x": -10, "room_outline_origin_y": -10,  # -> ro_dx=ro_dy=+2
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


def test_current_room_for_pixel():
    """[MS-13] room id at an arbitrary main-grid pixel (shared by storage + live pose)."""
    md = _md([(5, 2, 2, 2, 2)])
    assert current_room_for_pixel(md, 2, 2) == 5
    assert current_room_for_pixel(md, 50, 50) is None   # off-map
    assert current_room_for_pixel(md, 0, 0) is None     # byte 0 -> not a room
    assert current_room_for_pixel(md, "x", 2) is None   # non-numeric


def test_current_room_for_pixel_with_outline_offset():
    """[MS-13b] the inverse lookup applies the VERIFIED offset sign on a realistic map
    (outline origin RIGHT of the map origin, as on a real X10). ro_dx=+2, so a main-grid
    pixel maps to (px - ro_dx) in the raster; the inverted sign would look up the wrong cell."""
    md = _md([(5, 2, 2, 2, 2)], origin_x=-20, origin_y=-20,
             room_outline_origin_x=-10, room_outline_origin_y=-10)   # ro_dx=ro_dy=+2
    assert current_room_for_pixel(md, 4, 4) == 5     # main (4,4) -> outline (2,2) = room 5
    assert current_room_for_pixel(md, 2, 2) is None  # main (2,2) -> outline (0,0) = empty


def test_live_pose_overlay():
    """[MS-14] in-memory pixel pose -> normalized robot/dock anchors + current-room."""
    md = _md([(5, 2, 2, 2, 2)])
    ov = live_pose_overlay(md, [2, 2], [8, 8], 90)
    assert ov["robot_anchor"] == normalize_rendered(2, 2, 10, 10)
    assert ov["current_room"] == 5
    assert ov["dock_anchor"] == normalize_rendered(8, 8, 10, 10)
    assert ov["robot_heading"] == 90
    assert "robot_docked" not in ov                 # active robot is not docked
    # no dims -> empty; bool heading rejected
    assert live_pose_overlay({}, [2, 2], None, None) == {}
    assert "robot_heading" not in live_pose_overlay(md, None, None, True)


def test_apply_live_pose_override_clears_stale_owned_keys():
    """[MS-15] the live pose is AUTHORITATIVE for current_room + path: a partial overlay that
    omits them (e.g. a docked robot whose dock cell has no room) must CLEAR the lagged
    .storage values, not leave them stale (the ghost the feature kills). Empty overlay = no-op."""
    # docked, dock cell off-room: overlay carries robot/dock anchors but NO current_room/path
    overlay = {"robot_anchor": [0.7, 0.34], "dock_anchor": [0.7, 0.34], "robot_docked": True}
    result = {"present": True, "rooms": [{"number": 5}], "current_room": 5,  # STALE mid-clean
              "path": [[0.1, 0.9]], "image_size": [10, 10]}
    apply_live_pose_override(result, overlay)
    assert "current_room" not in result and "path" not in result   # stale values cleared
    assert result["robot_anchor"] == [0.7, 0.34] and result["robot_docked"] is True
    assert result["rooms"] == [{"number": 5}] and result["image_size"] == [10, 10]  # static kept
    # a resolved overlay re-supplies them (and they win over the stale base)
    result2 = {"current_room": 5, "path": [[0.1, 0.9]]}
    apply_live_pose_override(result2, {"current_room": 8, "path": [[0.7, 0.34]]})
    assert result2["current_room"] == 8 and result2["path"] == [[0.7, 0.34]]
    # empty overlay (dims missing) -> no live replacement, keep the .storage values untouched
    result3 = {"current_room": 5, "path": [[0.1, 0.9]]}
    assert apply_live_pose_override(result3, {}) == {"current_room": 5, "path": [[0.1, 0.9]]}


def test_mapdata_dict_from_obj():
    """[MS-16] convert the in-memory MapData OBJECT to the .storage map_data DICT (base64 for
    the byte rasters) so the existing decoders consume it unchanged + byte-identically."""
    rp_b64 = _raster(10, 10, [(5, 2, 2, 2, 2)])
    rp_bytes = base64.b64decode(rp_b64)
    obj = SimpleNamespace(
        room_pixels=rp_bytes, raw_pixels=b"\x01\x02", width=10, height=10, resolution=5,
        origin_x=0, origin_y=0, room_outline_width=10, room_outline_height=10,
        room_outline_origin_x=0, room_outline_origin_y=0, room_names={"5": "Kitchen"},
        virtual_walls=[], forbidden_zones=[], ban_mop_zones=[],
    )
    d = mapdata_dict_from_obj(obj)
    assert d["room_pixels"] == rp_b64                       # byte-identical to the storage form
    assert d["raw_pixels"] == base64.b64encode(b"\x01\x02").decode("ascii")
    assert d["width"] == 10 and d["room_outline_width"] == 10
    assert d["room_names"] == {"5": "Kitchen"}
    # the converted dict drives the EXISTING decoders unchanged
    assert current_room_for_pixel(d, 2, 2) == 5
    assert rooms_from_room_pixels(d)[0]["number"] == 5
    # not a usable MapData (no bytes raster) -> None (caller falls back to .storage)
    assert mapdata_dict_from_obj(SimpleNamespace(width=10)) is None
    assert mapdata_dict_from_obj(SimpleNamespace(room_pixels=rp_b64)) is None  # str, not bytes


def test_compare_map_data():
    """[MS-17] verify probe: normalization_safe iff the raster + geometry match; rasters by
    len+sha1, hazards by count."""
    md = _md([(5, 2, 2, 2, 2)])
    assert compare_map_data(md, dict(md))["normalization_safe"] is True
    # a differing geometry field -> unsafe
    diff_geom = dict(md)
    diff_geom["width"] = 99
    rep = compare_map_data(md, diff_geom)
    assert rep["normalization_safe"] is False
    assert rep["fields"]["width"] == {"equal": False, "memory": 10, "storage": 99}
    # a differing raster -> unsafe (compared by digest, never dumped)
    diff_rp = dict(md)
    diff_rp["room_pixels"] = _raster(10, 10, [(6, 0, 0, 0, 0)])
    rep2 = compare_map_data(md, diff_rp)
    assert rep2["normalization_safe"] is False
    assert rep2["fields"]["room_pixels"]["equal"] is False
    assert (rep2["fields"]["room_pixels"]["memory"]["sha1"]
            != rep2["fields"]["room_pixels"]["storage"]["sha1"])
    # hazards reported as counts + a shape sample (present only in memory here)
    md_hz = dict(md)
    md_hz["virtual_walls"] = [[1, 2], [3, 4]]
    rep3 = compare_map_data(md_hz, md)
    assert rep3["fields"]["virtual_walls"] == {"memory": 2, "storage": None, "sample": [1, 2]}
    # room_names: not equal but key-types explain it (int keys in memory, str in storage)
    rep4 = compare_map_data({"room_names": {1: "K"}}, {"room_names": {"1": "K"}})
    rn = rep4["fields"]["room_names"]
    assert rn["equal"] is False
    assert rn["memory_key_types"] == "int" and rn["storage_key_types"] == "str"
    assert rn["memory"] == {1: "K"} and rn["storage"] == {"1": "K"}


def test_vacuum_to_normalized():
    """[MS-19] hazard points are in vacuum coords: project to the main grid ((v-origin)/res)
    then apply the rendered-image normalization (Y-flip)."""
    md = {"origin_x": 0, "origin_y": 0, "resolution": 5, "width": 10, "height": 10}
    assert vacuum_to_normalized(10, 20, md) == [0.2, 0.5]      # px=2, py=4 -> flip
    # origin offset is applied before the divide
    md2 = {"origin_x": -50, "origin_y": -50, "resolution": 5, "width": 10, "height": 10}
    assert vacuum_to_normalized(0, 0, md2) == normalize_rendered(10, 10, 10, 10)
    # non-numeric / missing dims -> None
    assert vacuum_to_normalized("x", 0, md) is None
    assert vacuum_to_normalized(True, 0, md) is None           # bools rejected
    assert vacuum_to_normalized(0, 0, {}) is None


def test_hazards_from_mapdata():
    """[MS-20] device hazard layers (vacuum-frame) -> normalized card overlays: virtual_walls ->
    walls (segments), forbidden_zones -> no_go (polys), ban_mop_zones -> no_mop (polys)."""
    md = {"origin_x": 0, "origin_y": 0, "resolution": 5, "width": 10, "height": 10,
          "virtual_walls": [[[10, 20], [30, 40]]],
          "forbidden_zones": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
          "ban_mop_zones": [[[5, 5], [15, 5], [15, 15], [5, 15]]]}
    hz = hazards_from_mapdata(md)
    assert hz["walls"] == [[vacuum_to_normalized(10, 20, md), vacuum_to_normalized(30, 40, md)]]
    assert len(hz["no_go"]) == 1 and len(hz["no_go"][0]) == 4
    assert len(hz["no_mop"]) == 1 and len(hz["no_mop"][0]) == 4
    # absent/empty layers omitted; a degenerate poly (<3 pts) skipped; a bad wall (not a pair) skipped
    assert hazards_from_mapdata({"width": 10, "height": 10}) == {}
    assert "no_go" not in hazards_from_mapdata({**md, "forbidden_zones": [[[0, 0], [1, 1]]]})
    assert "walls" not in hazards_from_mapdata({**md, "virtual_walls": [[[1, 2], [3, 4], [5, 6]]]})
    # a truthy NON-list scalar layer (fork-schema drift) must DEGRADE, never raise (runs on loop)
    assert hazards_from_mapdata(
        {**md, "virtual_walls": 123, "forbidden_zones": True, "ban_mop_zones": "x"}) == {}


def test_eufy_version_of():
    """[MS-18] content version = sha1 of the raster; stable per map, changes on re-map."""
    md = _md([(5, 2, 2, 2, 2)])
    v = eufy_version_of(md)
    assert isinstance(v, str) and len(v) == 12
    assert eufy_version_of(dict(md)) == v                          # stable
    remapped = dict(md)
    remapped["room_pixels"] = _raster(10, 10, [(6, 0, 0, 0, 0)])
    assert eufy_version_of(remapped) != v                          # re-map -> new version
    assert eufy_version_of({}) == ""                               # no raster


def test_live_pose_overlay_docked_resolves_to_dock():
    """[MS-14b] robot pixel None (docked) -> robot anchor SNAPS to the dock + robot_docked;
    current-room comes from the dock cell. This is the fix for the stale mid-clean ghost."""
    md = _md([(5, 2, 2, 2, 2), (7, 8, 8, 8, 8)])
    ov = live_pose_overlay(md, None, [8, 8], None)
    assert ov["robot_anchor"] == normalize_rendered(8, 8, 10, 10)   # == dock
    assert ov["dock_anchor"] == normalize_rendered(8, 8, 10, 10)
    assert ov["robot_docked"] is True
    assert ov["current_room"] == 7                  # the dock's room, not a stale one
    # a non-pair robot string is treated the same as docked
    assert live_pose_overlay(md, "x", [8, 8], None)["robot_docked"] is True
    # docked with NO dock either -> no robot anchor at all
    assert "robot_anchor" not in live_pose_overlay(md, None, None, None)


def test_live_pose_overlay_live_trail():
    """[MS-14c] an in-memory robot trail -> normalized live path on the overlay."""
    md = _md([(5, 2, 2, 2, 2)])
    ov = live_pose_overlay(md, [2, 2], [8, 8], None, [(0, 0), (5, 5), (9, 9)])
    assert ov["path"] == [normalize_rendered(0, 0, 10, 10),
                          normalize_rendered(5, 5, 10, 10),
                          normalize_rendered(9, 9, 10, 10)]
    assert "path" not in live_pose_overlay(md, [2, 2], [8, 8], None)           # no trail arg
    assert "path" not in live_pose_overlay(md, [2, 2], [8, 8], None, [])       # empty trail


def test_normalize_trail():
    """[MS-8c] the shared trail normalizer (tuples ok, decimates, always keeps the latest)."""
    assert normalize_trail([(0, 0), (5, 5), (9, 9)], 10, 10) == [
        [0.0, 0.9], [0.5, 0.4], [0.9, 0.0]]
    assert normalize_trail([], 10, 10) == []
    assert normalize_trail([(1, 1)], 0, 0) == []         # no dims
    long = [(i % 10, 0) for i in range(1000)] + [(7, 7)]
    out = normalize_trail(long, 10, 10, max_points=50)
    assert len(out) <= 52 and out[-1] == normalize_rendered(7, 7, 10, 10)


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


# --- Wave-1 self-render: raster + explicit decode params --------------------------

def test_render_data_from_storage():
    """[MS-12] the card-render raster + EXPLICIT decode params (no brand assumptions
    leak to the card — it gets dims/offset/flip/rid_shift verbatim)."""
    md = _md([(5, 2, 2, 2, 2)], room_names={"5": "Kitchen"})
    rd = render_data_from_storage(md)
    assert rd["present"] is True and rd["format"] == "eufy_room_pixels_v1"
    assert rd["width"] == 10 and rd["height"] == 10
    assert rd["ro_width"] == 10 and rd["ro_height"] == 10
    assert rd["ro_dx"] == 0 and rd["ro_dy"] == 0
    assert rd["rid_shift"] == 2 and rd["catch_all_rid"] == 32 and rd["flip_y"] is True
    assert rd["room_pixels"] == md["room_pixels"]
    assert rd["room_names"] == {"5": "Kitchen"}
    assert len(rd["version"]) == 12
    # version is a stable content hash (same raster -> same version)
    assert render_data_from_storage(md)["version"] == rd["version"]
    # no segmentation -> None (caller treats as absent)
    assert render_data_from_storage({"width": 10, "height": 10}) is None
