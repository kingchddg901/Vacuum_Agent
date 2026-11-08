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
    _dreame_raster_flip,
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


def test_anchors_prefer_live_camera_position_over_sentinel():
    """[DMD-9] robot_pos/dock_pos (the camera's live vacuum_position/charger_position)
    OVERRIDE MapData.robot_position — which is the {0,0} origin sentinel when docked, and
    projects to a fixed WRONG pixel. BITES the pose fix: with the override the anchor moves
    off the sentinel; without it, it doesn't."""
    md = _make_md()
    md.robot_position = types.SimpleNamespace(x=0, y=0, a=0)  # docked -> origin sentinel
    sentinel = dreame_render_from_mapdata(md)                 # no override -> uses {0,0}
    live = dreame_render_from_mapdata(
        md, robot_pos={"x": 150, "y": 100, "a": 0}, dock_pos={"x": 150, "y": 100, "a": 0}
    )
    assert live["robot_anchor"] != sentinel["robot_anchor"]
    # the override is honored for the dock too
    assert live["dock_anchor"] == live["robot_anchor"]


def test_robot_heading_from_angle():
    """[DMD-10] robot_heading = (a - 90) mod 360 — calibrated on straight live runs (MAD ~2°):
    Dreame `a` is degrees CCW-from-east; the card arrow is CSS rotate (0=north, CW). a=90 (facing
    +y/north) → 0; a=0 → 270; a=180 → 90; a=270 → 180."""
    md = _make_md()
    for a, expect in [(90, 0.0), (0, 270.0), (180, 90.0), (270, 180.0), (353, 263.0)]:
        out = dreame_render_from_mapdata(md, robot_pos={"x": 150, "y": 100, "a": a})
        assert out["robot_heading"] == expect, f"a={a} -> {out.get('robot_heading')} != {expect}"
    # docked/unknown sentinel a=32767 -> no anchor, no heading
    docked = dreame_render_from_mapdata(md, robot_pos={"x": 150, "y": 100, "a": 32767})
    assert "robot_heading" not in docked


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


# ---------------------------------------------------------------------------
# [DMD-11]..[DMD-18] — the DEGRADATION arms of dreame_render_from_mapdata
#
# DMD-1..DMD-10 above establish the happy path on a real frame. Everything below is
# what the render does when ONE piece of the device's map is unusable, which is the
# half that had no coverage: nine statements and eight partial branches, every one a
# "this piece is broken, carry on without it" arm.
#
# WHY THEY MATTER SEPARATELY FROM "IT DOESN'T CRASH": each arm decides which FIELD
# goes missing, and the card renders what it is given. A room with no `area_m2` still
# draws; a room whose corners would not project must not draw at a garbage bbox; a
# robot anchor that cannot be placed must be ABSENT rather than placed at the frame
# origin. So these assert the surviving shape, not the absence of an exception --
# a test that only caught the raise would pass just as well if the arm silently
# emitted a wrong value.
#
# All of these keep to PRESENCE/ABSENCE of fields and to equality against a
# differently-configured render. None computes an expected pixel from
# `_dreame_projector`, which would be a shared oracle: the expectation and the
# behaviour under test derived from the same transform, so a change to it would move
# both and the assertion could never fail.
#
# ⚠ FOUR OF THIS FUNCTION'S `None` GUARDS ARE SUBSUMED, measured by ablating each one
# and finding that NOTHING below went red:
#
#   `if None in (x0, y0, x1, y1)`          subsumed by `if not c0 or not c1`
#   `if cx is not None and cy is not None` subsumed by `if centre:`
#   `if ra is not None`                    subsumed by the `except (TypeError, ValueError)`
#   `if dx is not None and dy is not None` subsumed by `if p:`
#
# In every case `_n()` reaches `float(None)`, raises, and returns None, so the
# downstream truthiness check or handler already skips the field. The guards are
# belt-and-braces over the implicit ones -- harmless, two wasted `_n` calls apiece,
# and NOT what any test below proves. So [DMD-12], [DMD-15], [DMD-16] and [DMD-17]
# pin the BEHAVIOUR (the field is absent, the sibling survives), which is the part
# that matters to the card, and the guards' own red sets are declared EMPTY. Written
# down because the obvious next move -- "add a test for that guard" -- cannot
# succeed, and a test that appears to cover one would be a preference.
# ---------------------------------------------------------------------------

def _md_with(**overrides):
    """`_make_md()` with attributes replaced -- the real shape, one piece broken."""
    md = _make_md()
    for k, v in overrides.items():
        setattr(md, k, v)
    return md


@pytest.mark.parametrize("bad,why", [
    ([1], "a one-element list -- IndexError on [1]"),
    (["a", "b"], "non-numeric strings -- ValueError on float()"),
    ((None, None), "a pair of Nones -- TypeError on float()"),
])
def test_dmd11_a_malformed_frame_offset_degrades_to_no_shift(bad, why):
    """[DMD-11] A bad `map_frame_offset_mm` declaration must not cost the whole map.

    The offset is a hand-tuned adapter declaration ([x_mm, y_mm]) that nudges the
    WHOLE raster -- rooms and anchors both ride the same `_n` -- onto Dreame's own
    frame. A typo in it is a plausible edit, and the arm under test turns that into
    "no nudge" rather than no map at all.

    The assertion is EQUALITY WITH THE UNSHIFTED RENDER, which is the actual contract
    and is stronger than "present is True": it pins that the fallback is (0, 0) and
    not some other number. The oracle is a render of the same MapData with no offset
    configured at all -- a different INPUT to the same function, not a re-derivation
    of its internals.

    Three rows because the handler catches three exception types and each comes from
    a different plausible edit to that literal. RED: drop the
    `except (TypeError, ValueError, IndexError)` and each row raises instead of
    rendering.

    LIMIT, FOUND BY TRYING A FOURTH ROW: a DICT-shaped declaration is not covered.
    `{"x": 1, "y": 2}[0]` raises KeyError, which is a LookupError but not an
    IndexError, so it escapes the handler and takes the whole render with it. Left
    alone rather than widened, for two measured reasons. `map_frame_offset_mm` appears
    in no schema in `adapters/config_schema.py`, and its only producer is the
    hardcoded list literal at `adapters/dreame/adapter.py` -- so a dict can arrive
    only from an in-repo edit, the same way the three covered shapes can. And the
    second copy of this read, in `dispatch/manager.py` (the replica pair recorded in
    `docs/dev/00c-replicas.md`), carries the IDENTICAL except tuple -- so this is a
    uniform limit of the guard rather than the two copies having drifted apart, which
    is the failure that would have mattered.
    """
    unshifted = dreame_render_from_mapdata(_make_md(), source_cfg={})

    got = dreame_render_from_mapdata(
        _make_md(), source_cfg={"map_frame_offset_mm": bad},
    )

    assert got["present"] is True, why
    # WHOLE-PAYLOAD equality, which is available because anchors and extras are
    # spread to the top level (see [DMD-5]) -- so this pins the rooms, both anchors,
    # the heading and the grid size in one comparison.
    assert got == unshifted, (
        f"a bad offset must behave exactly like NO offset ({why})"
    )


def test_dmd12_a_segment_missing_a_corner_is_skipped_and_its_siblings_survive():
    """[DMD-12] One unusable segment costs that room, not the map.

    A `None` corner is what a partially-decoded segment presents. Without the skip,
    `sorted()` over a None-derived bbox would either raise or emit a garbage
    rectangle, and a garbage bbox DRAWS -- a room-shaped box in the wrong place is
    worse than a missing room, because the user cannot tell it is wrong.

    The surviving sibling is the load-bearing half of the assertion: checking only
    that the broken room is absent would hold just as well if the loop bailed out
    entirely.
    """
    md = _md_with(segments={
        1: _seg(1, 0, 0, 100, 100, "Kitchen", 50, 50),
        2: types.SimpleNamespace(id=2, x0=None, y0=0, x1=200, y1=200,
                                 name="Half-decoded", x=150, y=150),
    })

    out = dreame_render_from_mapdata(md)

    assert out["present"] is True
    assert [r["number"] for r in out["rooms"]] == [1], "the good room, and only it"


def test_dmd13_a_segment_whose_corners_will_not_project_is_skipped():
    """[DMD-13] A corner that is present but unusable -- a different arm from [DMD-12].

    `None in (x0, y0, x1, y1)` catches a MISSING corner; a corner that is present but
    not a number gets past that check and fails inside `_n`, at `float(vx)`. Two
    guards, two inputs, and the second one is reachable only because the first does
    not look at types.
    """
    md = _md_with(segments={
        1: _seg(1, 0, 0, 100, 100, "Kitchen", 50, 50),
        2: _seg(2, "not-a-number", 0, 200, 200, "Bad frame", 150, 150),
    })

    out = dreame_render_from_mapdata(md)

    assert [r["number"] for r in out["rooms"]] == [1]


def test_dmd14_an_unusable_raster_loses_areas_and_says_so_in_diagnostics():
    """[DMD-14] Area is a bonus; the map is not. The failure is RECORDED, not swallowed.

    True per-room area needs numpy over `pixel_type`. When that cannot be computed the
    rooms must still render with their bboxes and names -- and the reason must land in
    `diagnostics["area_error"]`, because a map that silently lost its areas looks
    exactly like a device that never reported them.

    This also exercises the `px is not None` arm: with no counts, no room gets an
    `area_m2` key at all rather than one holding 0, which would read as a measured
    zero-size room.

    RED: drop the `except Exception as exc: diag["area_error"] = repr(exc)` and this
    raises ValueError out of the whole render.
    """
    out = dreame_render_from_mapdata(_md_with(pixel_type="not an array"))

    assert out["present"] is True
    assert len(out["rooms"]) == 2, "both rooms still render"
    assert "area_error" in out["diagnostics"], "the reason must be recorded"
    assert all("area_m2" not in r for r in out["rooms"]), (
        "absent, not a measured-looking 0"
    )


@pytest.mark.parametrize("seg,why", [
    (types.SimpleNamespace(id=1, x0=0, y0=0, x1=100, y1=100, name="No centre",
                           x=None, y=None),
     "the segment reports no centre at all"),
    (types.SimpleNamespace(id=1, x0=0, y0=0, x1=100, y1=100, name="Bad centre",
                           x="nope", y="nope"),
     "a centre that is present but will not project"),
])
def test_dmd15_a_room_without_a_usable_centre_still_renders(seg, why):
    """[DMD-15] Both centre arms, which fail for different reasons.

    The centre is what a room label and a go-to tap hang off, so it is optional by
    design: a room with a drawable bbox and no centre is still a room. Again the key
    must be ABSENT rather than present-and-None, since the consumer tests for the key.
    """
    out = dreame_render_from_mapdata(_md_with(segments={1: seg}))

    assert len(out["rooms"]) == 1, why
    assert "centre" not in out["rooms"][0]
    assert out["rooms"][0]["bbox"], "the bbox is what makes it still a room"


@pytest.mark.parametrize("robot,heading_expected,why", [
    (types.SimpleNamespace(x="nope", y="nope", a=0), False,
     "a position that will not project -> no anchor AND no heading"),
    (types.SimpleNamespace(x=1200, y=900, a=None), False,
     "a usable position with no angle -> anchor, but no heading"),
    (types.SimpleNamespace(x=1200, y=900, a="east"), False,
     "an angle that is not a number -> anchor, but no heading"),
    (types.SimpleNamespace(x=1200, y=900, a=180), True,
     "the control: a usable position AND angle -> both"),
])
def test_dmd16_the_robot_anchor_degrades_one_field_at_a_time(
    robot, heading_expected, why
):
    """[DMD-16] Three robot-anchor arms, plus the control that makes them mean something.

    A heading is a rotation applied to the card's arrow; an anchor is where the arrow
    sits. They fail independently, so each is skipped independently -- and the last
    row exists because the first three assert ABSENCE, which a render that never
    emitted a heading at all would satisfy just as well.
    """
    out = dreame_render_from_mapdata(_make_md(), robot_pos=robot)

    # anchors and extras are spread to the TOP level -- see [DMD-5].
    assert ("robot_heading" in out) is heading_expected, why
    if robot.x == "nope":
        assert "robot_anchor" not in out, why
    else:
        assert "robot_anchor" in out, why


@pytest.mark.parametrize("dock,present,why", [
    (types.SimpleNamespace(x=None, y=None, a=0), False, "no dock coordinates"),
    (types.SimpleNamespace(x="nope", y="nope", a=0), False,
     "dock coordinates that will not project"),
    (types.SimpleNamespace(x=100, y=100, a=0), True, "the control: a usable dock"),
])
def test_dmd17_the_dock_anchor_is_absent_rather_than_misplaced(dock, present, why):
    """[DMD-17] The dock's two skip arms and its control.

    The dock anchor is drawn as a fixed icon, so a misplaced one is a lie the user
    reads as fact. Absent is the honest answer, and the control row proves these
    assertions are about the dock rather than about the renderer never drawing one.
    """
    out = dreame_render_from_mapdata(_make_md(), dock_pos=dock)

    assert ("dock_anchor" in out) is present, why


def test_dmd18_furniture_is_omitted_entirely_rather_than_emitted_empty():
    """[DMD-18] The `if furniture:` arm, and one unplaceable item being dropped.

    `extra["furniture"]` absent means "this device reported none"; an empty list would
    mean "it reported some and they are all gone". The card branches on the key, so
    the distinction is visible.

    The second half drops a single item whose centre will not project while keeping
    the placeable one -- furniture is decoration, and one bad entry must not cost the
    rest of the room's layout.
    """
    none_at_all = dreame_render_from_mapdata(
        _md_with(furnitures={}, saved_furnitures={}),
    )
    # top level, per [DMD-5] -- `extra` is spread, not nested.
    assert "furniture" not in none_at_all, "omitted, not an empty list"

    mixed = dreame_render_from_mapdata(_md_with(furnitures={
        1: types.SimpleNamespace(x=50, y=50, x0=0, y0=0, width=1800, height=2100,
                                 type=types.SimpleNamespace(name="DOUBLE_BED"),
                                 angle=90.0, segment_id=1),
        2: types.SimpleNamespace(x="nope", y="nope", x0=0, y0=0, width=1, height=1,
                                 type=types.SimpleNamespace(name="CHAIR"),
                                 angle=0.0, segment_id=1),
    }))
    assert [f["type"] for f in mixed["furniture"]] == ["double_bed"], (
        "the placeable item survives; the unplaceable one is dropped"
    )


# ---------------------------------------------------------------------------
# [DMD-19]..[DMD-22] — dreame_render_data_from_mapdata's remaining arms
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("supplied,expect,why", [
    ({1: "Lounge", 2: "Snug"}, "Lounge", "a caller-supplied map wins outright"),
    ({}, "Kitchen", "an EMPTY dict falls back to the segment names"),
    (None, "Kitchen", "None falls back to the segment names"),
])
def test_dmd19_caller_supplied_room_names_override_the_segment_names(
    supplied, expect, why
):
    """[DMD-19] Both halves of `isinstance(room_names, dict) and room_names`.

    VA owns room names: a user renames a room in the card, and that name must win over
    whatever the device still calls the segment. The caller passes the VA names in, so
    the override arm is the normal path for any install where a room has been renamed
    — and it had no test, while the derive-from-segments fallback did ([DMD-7]).

    The empty-dict row is the `and room_names` half, and it is not pedantry: `{}` is
    what the caller passes for a map with no renames yet, and treating it as an
    override would blank every label on the card.
    """
    rd = dreame_render_data_from_mapdata(_make_md(), supplied)

    assert rd["room_names"]["1"] == expect, why


def test_dmd20_an_explicit_version_is_honoured_rather_than_rehashed():
    """[DMD-20] The `version is None` arm — the card's cache key.

    `version` is what the frontend caches the decoded raster against. Derived from the
    raster bytes when the caller does not supply one, so an unchanged map reuses the
    cached decode; but a caller that DOES supply one is pinning that identity, and
    overwriting it with a content hash would either serve a stale raster or force a
    re-decode on every poll.

    Both arms, because the default is the one already exercised: with no version the
    result must be a 12-char hex digest of the bytes, and with one it must be returned
    verbatim.
    """
    derived = dreame_render_data_from_mapdata(_make_md())
    assert len(derived["version"]) == 12, "a sha1 prefix"
    int(derived["version"], 16)          # raises if it is not hex

    pinned = dreame_render_data_from_mapdata(_make_md(), None, version="v-fixed-1")

    assert pinned["version"] == "v-fixed-1", "the caller's identity, untouched"
    assert pinned["room_pixels"] == derived["room_pixels"], (
        "and only the version differs -- the raster itself is the same"
    )


def test_dmd21_a_height_by_width_raster_is_transposed_not_rejected():
    """[DMD-21] The `(height, width)` arm, which is the whole [x][y] vs [y][x] question.

    `pixel_type` is `(width, height)` = `pt[x][y]` on the real device, and the card
    wants row-major `ry*width+rx`. A producer that hands over the array the other way
    round must be normalized rather than refused — and the proof is that BOTH
    orientations yield byte-identical `room_pixels`, which is a stronger claim than
    "it returned something".

    RED: drop `arr = arr.T` and the shape check below rejects this as mismatched, so
    the whole render-data comes back None.
    """
    native = dreame_render_data_from_mapdata(_make_md())

    md = _make_md()
    md.pixel_type = np.asarray(md.pixel_type).T          # (height, width)
    transposed = dreame_render_data_from_mapdata(md)

    assert transposed is not None, "a (height, width) raster must be accepted"
    assert transposed["room_pixels"] == native["room_pixels"], (
        "both orientations must decode to the same row-major raster"
    )


@pytest.mark.parametrize("shape,why", [
    ((5, 5), "neither (width, height) nor its transpose"),
    ((4, 4), "right width, wrong height"),
])
def test_dmd22_a_raster_that_matches_neither_orientation_is_refused(shape, why):
    """[DMD-22] A raster whose shape disagrees with `dimensions` yields None.

    The dimensions drive the projection and the card's canvas, so a raster of another
    size cannot be painted against them. Returning None hides the VA render and the
    card falls back to the device image — visibly degraded, but correct. Painting it
    anyway would put rooms at coordinates the bboxes do not agree with.
    """
    md = _make_md()
    md.pixel_type = np.zeros(shape, dtype=np.uint8)

    assert dreame_render_data_from_mapdata(md) is None, why


def test_dmd23_segment_ids_outside_the_byte_range_are_not_painted():
    """[DMD-23] `sid <= 0 or sid >= 200` — the guard that keeps a rid inside a byte.

    The raster is `uint8` and 255 is the catch-all, so a rid must stay below 200 for
    `200 + sid` to remain meaningful. A segment numbered 0 or 250 is skipped rather
    than wrapped, because `rid` is uint8: writing 250 would collide with the card's
    own palette range, and the arithmetic for its border values overflows.

    The control is the point: the same call carries a VALID segment, so this asserts
    the out-of-range ones are dropped WHILE a legitimate one is painted. Asserting
    only an empty raster would hold just as well if the loop painted nothing at all.
    """
    md = _make_md()
    md.segments = {
        0: _seg(0, 0, 0, 100, 100, "Zero", 50, 50),
        1: _seg(1, 0, 0, 100, 100, "Kitchen", 50, 50),
        250: _seg(250, 100, 100, 200, 200, "Out of range", 150, 150),
    }
    md.pixel_type = np.array(
        [[0, 1, 250], [0, 1, 250], [0, 0, 0], [0, 0, 0]], dtype=np.uint8,
    )

    rd = dreame_render_data_from_mapdata(md)

    painted = set(base64.b64decode(rd["room_pixels"]))
    assert painted == {0, 1}, (
        f"only the in-range segment may be painted, got {sorted(painted)}"
    )


# ---------------------------------------------------------------------------
# [DMD-24] _dreame_raster_flip — every way it DECLINES to decide
#
# `flip_y` tells the card whether to mirror the raster on paint. Get it wrong and the
# rooms are drawn upside down relative to the bboxes and anchors, which ride the
# projection rather than the raster. The decided path is covered; the arms that give
# up and fall back to False were not.
#
# `proj` is a PARAMETER here, so these inject a stub and choose the numbers by hand.
# That is deliberate: deriving the expected rows from `_dreame_projector` -- the
# transform these very tests exist to check -- would be a shared oracle, where the
# expectation and the behaviour move together and the assertion can never fail.
# ---------------------------------------------------------------------------

def _grid(height=10, width=4, rows=(8, 9), sid=1):
    """A (height, width) raster with `sid` painted on `rows`."""
    g = np.zeros((height, width), dtype=np.uint8)
    for r in rows:
        g[r, :] = sid
    return g


def test_dmd24_the_flip_is_decided_both_ways_on_a_hand_built_frame():
    """[DMD-24] The control pair, without which every fallback assertion below is empty.

    Hand-computed, with an injected `proj`:
      * rows 8 and 9 of a 10-row raster -> raster_cy = 8.5 / 10 = 0.85
      * a proj returning y = 0 -> proj_cy = 0.0
      * |0.85 - 0.0| = 0.85 > |0.85 - 1.0| = 0.15, so the raster centroid is nearer
        the MIRROR of the projection -> FLIPPED.
    Move the projection to the same end (y = 9 -> proj_cy = 0.9) and 0.05 > 0.95 is
    false, so the orientations agree and it does NOT flip.
    """
    segs = {1: types.SimpleNamespace(x=50, y=50)}
    grid = _grid(rows=(8, 9))

    flipped = _dreame_raster_flip(grid, segs, lambda cx, cy: (0, 0), 10)
    same = _dreame_raster_flip(grid, segs, lambda cx, cy: (0, 9), 10)

    assert flipped is True, "raster at the bottom, projection at the top -> flip"
    assert same is False, "both at the bottom -> no flip"


@pytest.mark.parametrize("grid,segs,proj,why", [
    (_grid(rows=(8, 9)), {1: types.SimpleNamespace(x=None, y=None)},
     lambda cx, cy: (0, 0),
     "the segment reports no centre, so there is nothing to compare"),
    (_grid(rows=(8, 9), sid=7), {1: types.SimpleNamespace(x=50, y=50)},
     lambda cx, cy: (0, 0),
     "the segment has no pixels in the raster (ys.size == 0)"),
    (_grid(rows=(8, 9)), {1: types.SimpleNamespace(x=50, y=50)},
     lambda cx, cy: None,
     "the centre will not project"),
    (None, {1: types.SimpleNamespace(x=50, y=50)}, lambda cx, cy: (0, 0),
     "the raster is not an array at all -- the blanket except"),
])
def test_dmd24b_an_undecidable_frame_falls_back_to_no_flip(grid, segs, proj, why):
    """[DMD-24b] Four ways to be unable to decide, all of which must NOT flip.

    False is the safe default: an unflipped raster that should have been flipped is
    wrong, but a flipped one that should not have been is wrong too, and False is what
    every non-Dreame backend uses. The point of these rows is that each gives up for a
    DIFFERENT reason, and [DMD-24] above proves True is reachable — so `is False` here
    is a real claim rather than a restatement of the default.
    """
    assert _dreame_raster_flip(grid, segs, proj, 10) is False, why
