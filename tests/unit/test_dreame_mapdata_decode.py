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

from custom_components.eufy_vacuum.mapping.map_source_runtime import (
    dreame_render_from_mapdata,
)

np = pytest.importorskip("numpy")


def _dims(grid_size=50, top=0, left=0, width=4, height=4):
    return types.SimpleNamespace(grid_size=grid_size, top=top, left=left, width=width, height=height)


def _seg(sid, x0, y0, x1, y1, name, cx, cy):
    return types.SimpleNamespace(id=sid, x0=x0, y0=y0, x1=x1, y1=y1, name=name, x=cx, y=cy)


def _make_md():
    # 4x4 raster: seg 1 = four `1` cells + one `101` border cell (5 px);
    #             seg 2 = four `2` cells (4 px); 0 = outside.
    pt = np.array(
        [[1, 1, 101, 0],
         [1, 1, 2, 2],
         [0, 2, 2, 0],
         [0, 0, 0, 0]],
        dtype=np.uint8,
    )
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
    assert rooms["Dining Room"]["area_m2"] == 0.16  # 4 px × 0.04
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
