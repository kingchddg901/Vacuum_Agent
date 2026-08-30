"""[DMD] Dreame MapData raster decoder — pure transform (map_source_runtime.dreame_render_from_mapdata).

Shapes derived from the live ground-truth probe on vacuum.robin (frame_type 73):
pixel_type value N == segment N floor, 100+N its border; area = pixel count × grid_size².
The fake MapData mirrors those real attributes (SimpleNamespace, per f/test_discipline: the
fake is shaped from the real closed set — .pixel_type / .dimensions / .segments / .furnitures
/ .robot_position / .charger_position).
"""

from __future__ import annotations

import types

import pytest

import base64

from custom_components.eufy_vacuum.mapping.map_source_runtime import (
    dreame_render_data_from_mapdata,
    dreame_render_from_mapdata,
)

np = pytest.importorskip("numpy")


def _dims(grid_size=50, top=0, left=0, width=4, height=3):
    return types.SimpleNamespace(grid_size=grid_size, top=top, left=left, width=width, height=height)


def _seg(sid, x0, y0, x1, y1, name, cx, cy):
    return types.SimpleNamespace(id=sid, x0=x0, y0=y0, x1=x1, y1=y1, name=name, x=cx, y=cy)


def _make_md():
    # NON-square (width=4, height=3) so [x][y] vs [y][x] is unambiguous. pixel_type is
    # (width, height) = pt[x][y], matching np.full((width, height)) on the real device.
    # seg 1 = four `1` cells + one `101` border cell (5 px); seg 2 = three `2` cells (3 px).
    pt = np.array(
        [[1, 1, 101],   # x=0 (y = 0,1,2)
         [1, 1, 2],     # x=1
         [0, 2, 2],     # x=2
         [0, 0, 0]],    # x=3
        dtype=np.uint8,
    )  # shape (4, 3) = (width, height)
    return types.SimpleNamespace(
        pixel_type=pt,
        dimensions=_dims(),
        segments={
            1: _seg(1, 0, 0, 100, 100, "Kitchen", 50, 50),
            2: _seg(2, 100, 100, 200, 200, "Dining Room", 150, 150),
        },
        robot_position=types.SimpleNamespace(x=0, y=0, a=0),
        charger_position=types.SimpleNamespace(x=100, y=100, a=0),
        furnitures={
            1: types.SimpleNamespace(
                x=50, y=50, x0=0, y0=0, width=1800, height=2100,
                type=types.SimpleNamespace(name="DOUBLE_BED"), angle=90.0, segment_id=1,
            )
        },
        saved_furnitures={},
    )


def test_present_and_backend():
    """[DMD-1] a decoded MapData yields a present dreame_mapdata result."""
    out = dreame_render_from_mapdata(_make_md())
    assert out["present"] is True
    assert out["backend"] == "dreame_mapdata"


def test_true_per_room_area_counts_interior_and_border():
    """[DMD-2] area_m2 = (interior + border) pixel count × grid_size². BITES: seg 1 is
    5 px (4 floor cells value 1 + 1 border cell value 101), seg 2 is 4 px — drop the
    100+id term and Kitchen collapses to 0.16, equal to Dining. (grid_size 200 mm =
    0.04 m²/px, chosen so 5 vs 4 px stay distinct after 2-decimal rounding.)"""
    md = _make_md()
    md.dimensions = _dims(grid_size=200)
    rooms = {r["name"]: r for r in dreame_render_from_mapdata(md)["rooms"]}
    assert rooms["Kitchen"]["area_m2"] == 0.2       # 5 px × 0.04
    assert rooms["Dining Room"]["area_m2"] == 0.12  # 3 px × 0.04
    assert rooms["Kitchen"]["area_m2"] > rooms["Dining Room"]["area_m2"]


def test_area_scales_with_grid_size():
    """[DMD-3] BITES the grid_size term: doubling grid_size (100->200) quadruples area."""
    md100 = _make_md(); md100.dimensions = _dims(grid_size=100)
    md200 = _make_md(); md200.dimensions = _dims(grid_size=200)
    k100 = {r["name"]: r for r in dreame_render_from_mapdata(md100)["rooms"]}["Kitchen"]
    k200 = {r["name"]: r for r in dreame_render_from_mapdata(md200)["rooms"]}["Kitchen"]
    assert k100["area_m2"] == 0.05   # 5 px × 0.01
    assert k200["area_m2"] == 0.2    # 5 px × 0.04 (= 4×, grid doubled)


def test_rooms_bbox_normalized_0_1():
    out = dreame_render_from_mapdata(_make_md())
    for r in out["rooms"]:
        x0, y0, x1, y1 = r["bbox"]
        assert 0.0 <= x0 <= x1 <= 1.0
        assert 0.0 <= y0 <= y1 <= 1.0


def test_anchors_and_furniture_ride_along():
    """[DMD-4] pose + user-placed furniture come from the same read; type is a neutral slug."""
    out = dreame_render_from_mapdata(_make_md())
    assert "dock_anchor" in out          # anchors spread to the top level
    fur = out["furniture"]               # extra ("furniture") spread to the top level
    assert len(fur) == 1
    assert fur[0]["type"] == "double_bed"     # slug from FurnitureType.name
    assert fur[0]["room"] == 1
    assert fur[0]["width_m"] == 1.8 and fur[0]["height_m"] == 2.1


def test_no_dimensions_is_absent_not_raise():
    """[DMD-5] a MapData without usable dimensions degrades to an absent marker."""
    md = _make_md()
    md.dimensions = types.SimpleNamespace(grid_size=0, top=0, left=0, width=0, height=0)
    out = dreame_render_from_mapdata(md)
    assert out["present"] is False
    assert out["reason"] == "no_dimensions"


# --- render-data (room_pixels_v1 raster) ------------------------------------


def _ridmap(v: int) -> int:
    """Expected rid for a pixel_type value given rooms {1, 2}."""
    for s in (1, 2):
        if v in (s, 100 + s, 200 + s):
            return s
    return 0


def test_render_data_shape_and_format():
    """[DMD-6] the render-data carries the shared room_pixels_v1 contract."""
    rd = dreame_render_data_from_mapdata(_make_md())
    assert rd is not None
    assert rd["format"] == "room_pixels_v1"
    assert rd["present"] is True
    assert rd["width"] == 4 and rd["height"] == 3
    assert rd["ro_width"] == rd["width"] and rd["ro_height"] == rd["height"]
    assert rd["rid_shift"] == 0 and rd["catch_all_rid"] == 255
    assert rd["res"] == 50
    assert rd["room_names"]["1"] == "Kitchen" and rd["room_names"]["2"] == "Dining Room"


def test_render_data_raster_is_rowmajor_resolved_rids():
    """[DMD-7] room_pixels decodes to a row-major (ry*width+rx) rid raster. BITES the whole
    encoding: a segment's pixels are value ∈ {id, 100+id, 200+id} → id (border folds into the
    room), everything else → 0. Drop the 100+id fold and pt[0][2]==101 reads 0 not 1."""
    md = _make_md()
    rd = dreame_render_data_from_mapdata(md)
    w, h = rd["width"], rd["height"]
    raw = base64.b64decode(rd["room_pixels"])
    assert len(raw) == w * h
    arr = md.pixel_type  # (width, height) = [x][y]
    for ry in range(h):
        for rx in range(w):
            assert raw[ry * w + rx] == _ridmap(int(arr[rx][ry])), f"mismatch at ry={ry} rx={rx}"
    # the border cell (value 101 at x=0,y=2) folded into room 1
    assert raw[2 * w + 0] == 1


def test_render_data_no_rooms_is_none():
    """[DMD-8] a MapData with no segments yields no render-data (card hides VA render)."""
    md = _make_md()
    md.segments = {}
    assert dreame_render_data_from_mapdata(md) is None
