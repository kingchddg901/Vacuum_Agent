"""Unit tests for the normalized->device-mm zone converter (Roborock app_zoned_clean).

Pure math, no HA. The forward fixture is a known affine with a Y-flip (image y grows
DOWN, vacuum y grows UP) mimicking a Roborock map crop, so the inverse must un-flip.

[ZDM-1] round-trip: a normalized box converts to the expected mm box.
[ZDM-2] an exact affine fits with ~0 residual.
[ZDM-3] fewer than 3 points -> None (under-determined).
[ZDM-4] collinear points -> None (degenerate).
[ZDM-5] a corrupted (non-affine) correspondence -> refuse (None), not a bad dispatch.
[ZDM-6] reversed-corner rects are min/max-ordered in mm.
"""

import pytest

from custom_components.eufy_vacuum.dispatch import zone_dispatch as zd


# Known forward affine: device-mm -> normalized 0..1, Y-flipped.
#   mm x in [20000, 50000] -> nx in [0, 1]
#   mm y in [15000, 45000] -> ny in [0, 1]  (flipped: ny=0 at the TOP = max mm y)
def _fwd(mmx: float, mmy: float):
    return (mmx - 20000) / 30000.0, (45000 - mmy) / 30000.0


def _corr(points):
    return [(*_fwd(mx, my), mx, my) for (mx, my) in points]


# Non-collinear, spread across the map (4 corners + 2 interior).
_GRID = [(20000, 15000), (50000, 15000), (50000, 45000),
         (20000, 45000), (35000, 30000), (26000, 21000)]


def test_zdm1_roundtrip_box_to_mm():
    """[ZDM-1] round-trip: a normalized box converts to the expected mm box."""
    out = zd.normalized_rects_to_mm(_corr(_GRID), [[0.25, 0.25, 0.75, 0.75]])
    assert out is not None
    x0, y0, x1, y1 = out[0]
    # nx 0.25/0.75 -> mmx 27500/42500 ; ny 0.25/0.75 -> mmy 37500/22500 (flip),
    # min/max-ordered -> y0=22500, y1=37500.
    assert x0 == pytest.approx(27500, abs=1.0)
    assert x1 == pytest.approx(42500, abs=1.0)
    assert y0 == pytest.approx(22500, abs=1.0)
    assert y1 == pytest.approx(37500, abs=1.0)


def test_zdm2_exact_affine_zero_residual():
    """[ZDM-2] an exact affine fits with ~0 residual."""
    coeffs = zd.fit_normalized_to_mm(_corr(_GRID))
    assert coeffs is not None
    assert zd.max_residual_mm(coeffs, _corr(_GRID)) < 1.0


def test_zdm3_too_few_points():
    """[ZDM-3] fewer than 3 points -> None (under-determined)."""
    assert zd.fit_normalized_to_mm(_corr(_GRID[:2])) is None
    assert zd.normalized_rects_to_mm(_corr(_GRID[:2]), [[0.1, 0.1, 0.2, 0.2]]) is None


def test_zdm4_collinear_degenerate():
    """[ZDM-4] collinear points -> None (degenerate)."""
    line = [(20000, 15000), (30000, 15000), (40000, 15000), (50000, 15000)]
    assert zd.fit_normalized_to_mm(_corr(line)) is None
    assert zd.normalized_rects_to_mm(_corr(line), [[0.1, 0.1, 0.2, 0.2]]) is None


def test_zdm5_non_affine_refuses():
    """[ZDM-5] a corrupted (non-affine) correspondence -> refuse (None), not a bad dispatch."""
    corr = _corr(_GRID)
    nx, ny, mx, my = corr[0]
    corr[0] = (nx, ny, mx + 5000.0, my - 5000.0)  # 5 m off -> not a clean affine
    assert zd.normalized_rects_to_mm(corr, [[0.25, 0.25, 0.75, 0.75]]) is None


def test_zdm6_reversed_corners_ordered():
    """[ZDM-6] reversed-corner rects are min/max-ordered in mm."""
    # x0>x1 and y0>y1 on input must still come out min/max-ordered.
    out = zd.normalized_rects_to_mm(_corr(_GRID), [[0.75, 0.75, 0.25, 0.25]])
    assert out is not None
    x0, y0, x1, y1 = out[0]
    assert x0 < x1 and y0 < y1
    assert x0 == pytest.approx(27500, abs=1.0)
    assert y1 == pytest.approx(37500, abs=1.0)


# --- bridge: correspondences_from_mapdata + converter, end to end -------------
# A fake parser MapData whose to_img reproduces the same Y-flipped affine as _fwd
# above, so correspondences extracted from its rooms must invert back to mm.
from custom_components.eufy_vacuum.mapping import map_source_runtime as msr  # noqa: E402


class _FP:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _FakeDims:
    rotation = 0

    def to_img(self, pt):  # mm -> image px, matching _fwd (Y-flipped), img 1000x1000
        return _FP((pt.x - 20000) * 1000 / 30000.0, (45000 - pt.y) * 1000 / 30000.0)


class _FakeData:
    size = (1000, 1000)


class _FakeImage:
    dimensions = _FakeDims()
    data = _FakeData()


class _FakeRoom:
    def __init__(self, n, x0, y0, x1, y1):
        self.number, self.name = n, None
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _FakeMapData:
    image = _FakeImage()
    rooms = {
        1: _FakeRoom(1, 20000, 15000, 35000, 30000),
        2: _FakeRoom(2, 35000, 30000, 50000, 45000),
    }


def test_zdm7_correspondences_bridge_roundtrip():
    corr = msr.correspondences_from_mapdata(_FakeMapData())
    assert len(corr) == 8  # two rooms x four corners
    out = zd.normalized_rects_to_mm(corr, [[0.25, 0.25, 0.75, 0.75]])
    assert out is not None
    x0, y0, x1, y1 = out[0]
    assert x0 == pytest.approx(27500, abs=1.0)
    assert x1 == pytest.approx(42500, abs=1.0)
    assert y0 == pytest.approx(22500, abs=1.0)
    assert y1 == pytest.approx(37500, abs=1.0)


def test_zdm8_correspondences_empty_when_no_rooms():
    class _NoRooms:
        image = _FakeImage()
        rooms = None
    assert msr.correspondences_from_mapdata(_NoRooms()) == []


def test_zdm9_correspondences_skip_out_of_grid_corner():
    """[ZDM-9] GEO-4/RB-8: a room corner that projects OUTSIDE the image is skipped
    (not accepted as a clamped edge point) — correspondences_from_mapdata's own
    docstring claims clamped corners are simply skipped; prove it's actually true."""
    class _FarRoom:
        number, name = 3, None
        # x1=200000 is WAY outside the fixture's forward-affine domain (mmx in
        # [20000,50000] maps to nx in [0,1]) -- both x1 corners project past nx=1.0.
        x0, y0, x1, y1 = 20000, 15000, 200000, 30000

    class _WithFarRoom:
        image = _FakeImage()
        rooms = {1: _FakeRoom(1, 20000, 15000, 35000, 30000), 3: _FarRoom()}

    corr = msr.correspondences_from_mapdata(_WithFarRoom())
    # room 1 still contributes its 4 (in-grid) corners; room 3's two OUT-OF-GRID
    # corners (x1=200000) are skipped, its two in-grid corners (x0=20000) survive.
    assert len(corr) == 4 + 2
    assert not any(mmx == 200000.0 for _, _, mmx, _ in corr)


# ---------------------------------------------------------------------------
# go-to: the SINGLE-POINT converter (same affine + refuse contract as zones)
# ---------------------------------------------------------------------------

_ROOM_CORNERS = [
    (25000, 20000), (40000, 20000), (40000, 38000), (25000, 38000),
    (30000, 25000), (35000, 25000),  # >= 3 non-collinear
]


def _corr_from_fwd(mm_corners):
    return [(_fwd(mmx, mmy)[0], _fwd(mmx, mmy)[1], float(mmx), float(mmy))
            for mmx, mmy in mm_corners]


def test_normalized_point_to_mm_round_trips():
    """[ZPT-1] the go-to converter recovers device-mm for a normalized point, inverting the
    SAME Y-flipped affine as the zone converter: forward a target mm to normalized, convert
    back, get the mm. BITE: swap _apply's x/y coeffs and this misses."""
    corr = _corr_from_fwd(_ROOM_CORNERS)
    target = (33000.0, 31000.0)
    nx, ny = _fwd(*target)
    got = zd.normalized_point_to_mm(corr, [nx, ny])
    assert got is not None
    assert round(got[0]) == round(target[0])
    assert round(got[1]) == round(target[1])


def test_normalized_point_to_mm_refuses_bad_geometry():
    """[ZPT-2] the safety contract: too few / collinear correspondences, or a malformed
    point -> None, so dispatch_goto REFUSES rather than send the robot to a guess."""
    corr = _corr_from_fwd(_ROOM_CORNERS)
    assert zd.normalized_point_to_mm([], [0.5, 0.5]) is None
    assert zd.normalized_point_to_mm(corr[:2], [0.5, 0.5]) is None            # < 3
    collinear = [(0.0, 0.0, 0.0, 0.0), (0.5, 0.5, 500.0, 500.0), (1.0, 1.0, 1000.0, 1000.0)]
    assert zd.normalized_point_to_mm(collinear, [0.3, 0.3]) is None           # degenerate
    assert zd.normalized_point_to_mm(corr, [0.5]) is None                     # bad point shape


def test_correspondences_carry_the_render_frame_offset():
    """[ZPT-3] the render's map_frame_offset_mm must ALSO shift the correspondences'
    NORMALIZED side — the card renders (and the user taps) WITH the offset, so the affine
    fit must too, or a go-to lands ~offset away. Identity 1000px projector: a +50mm x offset
    moves a corner's nx by 0.05 while the mm side stays the TRUE corner. BITE: drop the
    offset from correspondences_from_mapdata and nx stays 0.0 (unshifted)."""
    from custom_components.eufy_vacuum.mapping.map_source_runtime import (
        correspondences_from_mapdata,
    )

    class _P:
        def __init__(self, x, y):
            self.x, self.y = x, y

    class _Dims:
        rotation = 0

        def to_img(self, xy):
            return _P(xy.x, xy.y)  # identity mm -> pixel

    class _Data:
        size = (1000, 1000)

    class _Img:
        dimensions = _Dims()
        data = _Data()

    class _Room:
        x0, y0, x1, y1 = 0.0, 0.0, 100.0, 100.0

    class _MD:
        image = _Img()
        rooms = [_Room()]

    md = _MD()
    base = correspondences_from_mapdata(md)
    shifted = correspondences_from_mapdata(md, offset=(50.0, 0.0))
    b00 = next(c for c in base if c[2] == 0.0 and c[3] == 0.0)
    s00 = next(c for c in shifted if c[2] == 0.0 and c[3] == 0.0)
    assert round(b00[0], 4) == 0.0
    assert round(s00[0], 4) == 0.05
    assert (s00[2], s00[3]) == (0.0, 0.0)  # mm side stays the TRUE corner


# ---------------------------------------------------------------------------
# go-to on a DREAME MapData — the shape that shipped broken (RN0Y49XS): the
# decoded Dreame MapData has `.dimensions` (grid) + `.segments`, NOT the parser's
# `.image.dimensions.to_img` + `.rooms`. The old correspondences read `.rooms`
# (absent) and returned [], so every real tap refused with "no live map /
# projection failed". These drive the ACTUAL Dreame shape through the real
# `_dreame_projector` — no mocked projector — so they bite that bug.
# ---------------------------------------------------------------------------

class _DreameDims:
    grid_size = 50.0
    top = 0.0
    left = 0.0
    width = 100
    height = 100


class _DreameSeg:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _DreameMD:
    # No `.image`, no `.rooms` — exactly the shape that made the parser path return [].
    dimensions = _DreameDims()
    segments = {
        1: _DreameSeg(200, 200, 2400, 1200),
        2: _DreameSeg(2600, 1400, 4600, 3800),
    }


def test_dgt1_dreame_shape_round_trips_through_correspondences():
    """[DGT-1] correspondences_from_mapdata dispatches a Dreame MapData to the Dreame
    builder (parser path returns [] on this shape), and an INDEPENDENT interior point —
    projected the SAME way the render's _n does — inverts back to its true vacuum-mm.
    BITE: before the shape dispatch, corr is [] and normalized_point_to_mm returns None."""
    corr = msr.correspondences_from_mapdata(_DreameMD())
    assert len(corr) == 8  # two segments x four corners, all in-grid
    proj, w, h, _gs = msr._dreame_projector(_DreameDims())
    vx, vy = 1500.0, 900.0                       # not one of the bbox corners
    px, py = proj(vx, vy)
    got = zd.normalized_point_to_mm(corr, [px / w, py / h])
    assert got is not None
    assert round(got[0]) == round(vx)
    assert round(got[1]) == round(vy)


def test_dgt2_dreame_correspondences_carry_the_offset():
    """[DGT-2] map_frame_offset_mm shifts the NORMALIZED side (render frame), mm side stays
    TRUE — the Dreame analog of ZPT-3. +500mm x over a grid_size 50 / width 100 projector =
    +0.10 nx. BITE: drop the offset and the shift is 0, so a tap lands ~offset away."""
    base = msr.dreame_correspondences_from_mapdata(_DreameMD(), offset=(0.0, 0.0))
    shifted = msr.dreame_correspondences_from_mapdata(_DreameMD(), offset=(500.0, 0.0))
    b = next(c for c in base if (c[2], c[3]) == (200.0, 200.0))
    s = next(c for c in shifted if (c[2], c[3]) == (200.0, 200.0))
    assert round(s[0] - b[0], 4) == 0.10
    assert (s[2], s[3]) == (200.0, 200.0)        # mm side stays the true corner


def test_dgt3_dreame_correspondences_empty_without_geometry():
    """[DGT-3] refuse-safe inputs: no dimensions or no segments -> [] (dispatch then refuses
    rather than sending the robot to a guess)."""
    class _NoDims:
        segments = {1: _DreameSeg(0, 0, 100, 100)}

    class _NoSegs:
        dimensions = _DreameDims()

    assert msr.dreame_correspondences_from_mapdata(_NoDims()) == []
    assert msr.dreame_correspondences_from_mapdata(_NoSegs()) == []
