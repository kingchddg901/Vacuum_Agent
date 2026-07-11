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
