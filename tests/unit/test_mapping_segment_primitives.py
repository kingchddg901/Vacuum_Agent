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
[SP-20] transform_mask: unit-scale centering + shift; off-canvas → empty.
[SP-21] transform_scalar_image: unit-scale centering of a float image.
[SP-21b] transform_scalar_image: non-unit-scale bilinear (order=1) resample branch.
[SP-22] transform_color_image: per-channel transform preserves channel count.
[SP-23] mask_edge_band: dilate-XOR-erode produces a non-empty edge ring (scipy).
[SP-24] normalized_color_features: per-pixel chromaticity channels sum to 1.
[SP-10b] compactness ranks blockiness: pi/4 ceiling, disc scores below square.
[SP-24b] normalized_color_features == rgb/sum(rgb); the luminance weights were dead.
[SP-25] mask_to_polygon: RDP-collapse fallback reverts to best_loop for a drawable (>=4 vertex) polygon.
[SP-26] estimate_alignment: a strictly-better shifted candidate takes the best-update branch (recovers the shift).
[SP-RAST-1] rasterize_primitives: a pct rect -> rectangle polygon in map px; empty -> [].
[SP-RAST-2] rasterize_primitives: subtract clears an edge; polygon primitive round-trips.
[SP-RAST-3] rasterize_primitives: the circle branch draws an ELLIPSE -- pi/4 of its own bbox.
[SP-RAST-4] rasterize_primitives: a non-dict primitive and an unknown type each draw nothing.
[SP-RAST-5] rasterize_primitives: a 2-point polygon is not drawable; a junk vertex is dropped.
[SP-RAST-6] rasterize_primitives: A2-POLYGO-8 -- a malformed shape mid-segment is silent.
[SP-RAST-7] rasterize_primitives: A2-POLYGO-2 -- libs-missing and all-subtracted return the
            same [], so the caller cannot tell them apart.
"""

from __future__ import annotations

import math

import pytest

from custom_components.eufy_vacuum.mapping import segment_primitives as sp_module
from custom_components.eufy_vacuum.mapping.segment_primitives import (
    aspect_ratio,
    agreement_score,
    bbox_from_stats,
    compactness,
    component_overlap_ratio,
    estimate_alignment,
    image_runtime_capabilities,
    mask_edge_band,
    mask_iou,
    mask_left_right_counts,
    mask_perimeter,
    mask_to_polygon,
    normalize_polygon,
    normalized_color_features,
    polygon_area,
    rasterize_primitives,
    rdp,
    transform_color_image,
    transform_mask,
    transform_scalar_image,
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


def test_transform_mask_unit_scale(np):
    """[SP-20] a 2x2 mask centered into a 6x6 canvas at unit scale."""
    mask = np.ones((2, 2), dtype=bool)
    out = transform_mask(mask, 1.0, 0, 0, (6, 6))
    assert out.shape == (6, 6)
    assert int(np.count_nonzero(out)) == 4
    assert bool(out[2, 2]) and bool(out[3, 3])
    # shifted entirely off the canvas → empty
    off = transform_mask(mask, 1.0, 100, 100, (6, 6))
    assert int(np.count_nonzero(off)) == 0


def test_transform_scalar_image_unit_scale(np):
    """[SP-21]"""
    img = np.ones((2, 2), dtype=np.float32)
    out = transform_scalar_image(img, 1.0, 0, 0, (6, 6))
    assert out.shape == (6, 6)
    assert out.sum() == pytest.approx(4.0)


def test_transform_scalar_image_non_unit_scale(np):
    """[SP-21b] non-unit-scale (|scale-1|>1e-6) takes the _NDIMAGE.zoom(order=1)
    bilinear branch: enlarged footprint, intermediate values, centered placement.

    Requires scipy.ndimage for the float zoom (the order-1 path that distinguishes
    this from transform_mask's order-0/bool resample).
    """
    pytest.importorskip("scipy.ndimage")
    img = np.zeros((4, 4), dtype=np.float32)
    img[1:3, 1:3] = 1.0  # solid 2x2 interior block of value 1.0

    out = transform_scalar_image(img, 2.0, 0, 0, (16, 16))

    # (a) shape + dtype of the float canvas
    assert out.shape == (16, 16)
    assert out.dtype == np.float32
    # (b) 2x upscale enlarges the nonzero footprint (~4x area growth)
    assert np.count_nonzero(out) > np.count_nonzero(img)
    assert np.count_nonzero(out) >= 12
    # (c) bilinear, not nearest: order=1 produces values strictly between 0 and 1,
    #     which an order=0 (nearest) resample would NOT
    assert bool(((out > 0) & (out < 1.0)).any())
    # (d) centered: the footprint sits in the middle, corners stay empty
    assert np.count_nonzero(out[6:10, 6:10]) > 0
    assert np.count_nonzero(out[:2, :2]) == 0
    assert np.count_nonzero(out[:2, -2:]) == 0
    assert np.count_nonzero(out[-2:, :2]) == 0
    assert np.count_nonzero(out[-2:, -2:]) == 0


def test_transform_color_image(np):
    """[SP-22] each channel is transformed; channel count preserved."""
    img = np.ones((2, 2, 3), dtype=np.float32)
    out = transform_color_image(img, 1.0, 0, 0, (6, 6))
    assert out.shape == (6, 6, 3)
    assert out.sum() == pytest.approx(12.0)  # 4 per channel * 3


def test_mask_edge_band(np):
    """[SP-23] requires scipy.ndimage for binary dilation/erosion."""
    pytest.importorskip("scipy.ndimage")
    mask = np.zeros((12, 12), dtype=bool)
    mask[3:9, 3:9] = True  # solid 6x6
    band = mask_edge_band(mask, iterations=1)
    assert band.shape == mask.shape
    assert band.any()
    # the deep interior is neither newly dilated nor eroded away → not in band
    assert not bool(band[6, 6])


def test_normalized_color_features(np):
    """[SP-24] per-pixel chromaticity: the three channels sum to 1.0."""
    rgb = (np.ones((2, 2, 3), dtype=np.float32) * 100.0)
    feats = normalized_color_features(rgb)
    assert feats.shape == (2, 2, 3)
    assert np.allclose(feats.sum(axis=2), 1.0)


def test_mask_to_polygon_rdp_collapse_fallback(np):
    """[SP-25] RDP fallback: a single-pixel mask whose 4-corner loop RDP-collapses
    below 4 vertices reverts to best_loop, so a drawable (>=4 vertex) polygon is
    always returned (segmentor.py:1198 would otherwise drop this region)."""
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    polygon, raw_count = mask_to_polygon(mask)
    # raw loop is the 4 corners of the unit pixel
    assert raw_count == 4
    # fallback restored best_loop instead of returning the 2-point RDP collapse
    assert len(polygon) == 4
    assert len(polygon) == raw_count  # matches raw, not <4
    # the restored polygon is exactly the unit-pixel corners (order-insensitive)
    assert sorted(map(tuple, polygon)) == [(2.0, 2.0), (2.0, 3.0), (3.0, 2.0), (3.0, 3.0)]


def test_estimate_alignment_recovers_shifted_candidate(np):
    """[SP-26] a strictly-better transformed candidate replaces ``best``.

    Reference and candidate are SAME-shape (60, 60) arrays so transform_mask's
    centering is identical for both; the candidate's True block is shifted +6 px
    in x.  The unit/zero baseline IoU is degraded (0.3333), so the brute-force
    grid must find a better alignment and take the update branch — recovering
    shift_x=-6 at score 1.0.  Drives the best-update inside estimate_alignment.

    Requires scipy.ndimage (transform_mask uses ndimage.zoom for the non-unit
    scales in the search grid).
    """
    pytest.importorskip("scipy.ndimage")
    ref = np.zeros((60, 60), dtype=bool)
    ref[10:22, 10:22] = True
    cand = np.zeros((60, 60), dtype=bool)
    cand[10:22, 16:28] = True  # same array shape; True region shifted +6 px in x

    # Baseline (no transform) is degraded: 12x12 blocks overlap by 6 columns.
    baseline = transform_mask(cand, 1.0, 0, 0, (60, 60))
    assert round(mask_iou(ref, baseline), 4) == pytest.approx(0.3333)

    # The grid finds the -6 px x-shift that perfectly re-aligns the candidate,
    # so the update branch fires and replaces best with that scale/shift/score.
    result = estimate_alignment(ref, cand)
    assert result["score"] == pytest.approx(1.0)
    assert result["shift_x"] == -6
    assert result["shift_y"] == 0
    assert result["scale"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Primitive rasterization (PIL + numpy)
# ---------------------------------------------------------------------------

def test_rasterize_primitives_rect(np):
    """[SP-RAST-1] a single pct rect rasterises to a rectangle polygon in the
    map's pixel space (bbox/area ~ the rect); an empty primitive list yields []."""
    pytest.importorskip("PIL")
    poly = rasterize_primitives(
        [{"type": "rect", "x": 10, "y": 10, "w": 30, "h": 30}],
        width=100, height=100,
    )
    assert poly
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    assert min(xs) == pytest.approx(10, abs=2)
    assert max(xs) == pytest.approx(40, abs=2)
    assert min(ys) == pytest.approx(10, abs=2)
    assert max(ys) == pytest.approx(40, abs=2)
    area = abs(polygon_area([(float(x), float(y)) for x, y in poly]))
    assert area == pytest.approx(900, rel=0.15)
    # nothing drawn -> empty polygon
    assert rasterize_primitives([], width=100, height=100) == []


def test_rasterize_primitives_subtract_and_polygon(np):
    """[SP-RAST-2] subtract clears (an edge cut shrinks the outer outline) and an
    explicit polygon primitive round-trips through the same extraction."""
    pytest.importorskip("PIL")
    full = rasterize_primitives(
        [{"type": "rect", "x": 0, "y": 0, "w": 50, "h": 50}],
        width=100, height=100,
    )
    cut = rasterize_primitives(
        [
            {"type": "rect", "x": 0, "y": 0, "w": 50, "h": 50},
            {"type": "rect", "x": 25, "y": 0, "w": 25, "h": 50, "op": "subtract"},
        ],
        width=100, height=100,
    )
    full_area = abs(polygon_area([(float(x), float(y)) for x, y in full]))
    cut_area = abs(polygon_area([(float(x), float(y)) for x, y in cut]))
    assert cut_area < full_area  # the right half was removed
    # an explicit polygon primitive also produces a polygon
    tri = rasterize_primitives(
        [{"type": "polygon", "points": [[20, 20], [60, 20], [40, 60]]}],
        width=100, height=100,
    )
    assert len(tri) >= 3



def test_compactness_ranks_blockiness_not_roundness():
    """[SP-10b] A2-POLYGO-6: pin the RASTER quotient's real behaviour.

    The docstring used to claim "Range 0-1; 1 = circle". Both halves are wrong,
    and [SP-10] has always asserted ~0.785 for a square, so the test and the
    docstring were contradicting each other. `perimeter` is mask_perimeter's
    exposed-edge count -- a taxicab perimeter -- so the attainable maximum is
    pi/4 and a digital disc scores BELOW a square of the same footprint.

    The ordering assert is the anchor: it encodes the fact the old docstring
    denied, so anyone who "fixes" the arithmetic to make circles score 1.0
    breaks it deliberately rather than silently rescaling the Eufy segmentor's
    tuned 0.08 / 0.22 thresholds.
    """
    square = compactness(100, 40)                       # 10x10, P = 2(w+h) = 40
    assert square <= math.pi / 4 + 1e-9                 # pi/4 is the ceiling, not 1.0
    assert square == pytest.approx(math.pi / 4)         # a square ATTAINS it

    single_pixel = compactness(1, 4)                    # also exactly pi/4
    assert single_pixel == pytest.approx(math.pi / 4)

    # a radius-10 digital disc: 4-connected staircase perimeter is 8r, the same
    # as its bounding square's
    disc = compactness(int(math.pi * 100), 80)
    assert disc < square, "a circle scores WORSE than a box under a raster perimeter"


def test_normalized_color_features_has_no_luminance_weighting(np):
    """[SP-24b] A2-POLYGO-7: the transform is pure chromaticity.

    The removed Rec.709 luminance divide cancelled exactly in the ratio that
    follows -- (rgb/L)/(sum(rgb)/L) == rgb/sum(rgb) -- so the weights could not
    influence the output. This asserts the closed form directly, which is what
    makes the removal provably behaviour-neutral rather than merely untested.
    """
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 256, size=(6, 5, 3), dtype=np.uint8)

    expected_f = rgb.astype(np.float32) + 1.0
    expected = expected_f / expected_f.sum(axis=2, keepdims=True)

    assert np.allclose(normalized_color_features(rgb), expected, atol=1e-6)
    # and the defining property still holds for a non-uint8 caller
    assert np.allclose(normalized_color_features(rgb.astype(np.float32)).sum(axis=2), 1.0)


# ---------------------------------------------------------------------------
# [SP-RAST-3]..[SP-RAST-7]. `rasterize_primitives` is reached from
# mapping_services.py::_handle_set_custom_segments, which feeds it the card's
# authored pct shapes one segment at a time and keeps the polygon it returns.
# ---------------------------------------------------------------------------

def _area(poly):
    return abs(polygon_area([(float(x), float(y)) for x, y in poly]))


def test_rast3_the_circle_branch_draws_an_ellipse_not_its_bounding_box(np):
    """[SP-RAST-3] The circle primitive, which had no test at all.

    THE ASSERTION IS THE AREA RATIO, not that a polygon came back. "A circle
    rasterises to something" is satisfied by `draw.rectangle` just as well, and the
    rect branch two lines above is already proven -- so a shape-blind assertion here
    would pass against the branch drawing the WRONG primitive. A disc fills pi/4 of
    its bounding square, so the ratio is what separates an ellipse from a box.

    It also pins `r` being scaled through `_p` like a coordinate: a radius is a
    LENGTH, and reading it with the position helper is only correct because `_p` is a
    pure pct->px scale. If `r` were left unscaled the disc would be a few px across
    at the 512 working resolution and the area assertion would collapse.

    The square control is authored to the circle's own bbox (30..70 pct), so the two
    numbers are comparable without computing anything from the circle itself.
    """
    pytest.importorskip("PIL")
    circle = rasterize_primitives(
        [{"type": "circle", "cx": 50, "cy": 50, "r": 20}], width=100, height=100
    )
    square = rasterize_primitives(
        [{"type": "rect", "x": 30, "y": 30, "w": 40, "h": 40}], width=100, height=100
    )
    assert circle, "the circle branch produced no polygon at all"

    xs = [p[0] for p in circle]
    ys = [p[1] for p in circle]
    assert min(xs) == pytest.approx(30, abs=2)
    assert max(xs) == pytest.approx(70, abs=2)
    assert min(ys) == pytest.approx(30, abs=2)
    assert max(ys) == pytest.approx(70, abs=2)

    assert _area(circle) == pytest.approx(math.pi * 20 * 20, rel=0.1)
    assert _area(circle) < _area(square) * 0.85, (
        "the circle filled its whole bounding box -- an ellipse was not drawn"
    )


def test_rast4_a_non_dict_primitive_and_an_unknown_type_both_draw_nothing(np):
    """[SP-RAST-4] Two ways a primitive contributes nothing, kept apart.

    `primitives` arrives from the card over a service call, so a row can be a string
    or a None -- and the next statement calls `.get` on it.

    THE JUNK COMES FIRST, which is what makes this more than a no-raise test: with a
    `break` in place of the skip the trailing rect is never drawn and the result is
    []. The rect is the discriminator; the absence of an exception is not.

    THE UNKNOWN TYPE CARRIES A FULL SET OF RECT FIELDS, which is the half of this my
    first draft got wrong. A blob with only `x` and `y` proves nothing: route it into
    the rect branch and it dies on `prim["w"]` regardless, so the ablation came back
    DEAD -- the test passed whether or not the type was checked at all. Given `w` and
    `h` spanning the whole canvas, a chain that fell through to the rect branch would
    paint over everything, and the area assertion sees it.

    It is paired with a small real rect for the same reason: the claim is that the
    blob contributes NOTHING, and only a drawn shape beside it can distinguish that
    from "nothing was drawn at all".
    """
    pytest.importorskip("PIL")
    rect = {"type": "rect", "x": 10, "y": 10, "w": 30, "h": 30}

    survived = rasterize_primitives(["junk", None, 7, rect], width=100, height=100)
    assert survived, "a non-dict row stopped the walk instead of being skipped"
    assert _area(survived) == pytest.approx(900, rel=0.15)

    blob = {"type": "blob", "x": 0, "y": 0, "w": 100, "h": 100}
    assert rasterize_primitives([blob], width=100, height=100) == [], (
        "an unrecognised primitive type drew something"
    )
    with_blob = rasterize_primitives([blob, rect], width=100, height=100)
    assert _area(with_blob) == pytest.approx(900, rel=0.15), (
        "the unknown type painted the canvas, so its `type` was never checked"
    )


def test_rast5_a_two_point_polygon_is_not_drawable_but_a_junk_vertex_is_dropped(np):
    """[SP-RAST-5] The `len(pts) >= 3` gate, asserted as an asymmetric pair.

    A polygon needs three vertices to enclose anything, and `draw.polygon` on two
    would raise. The empty return here DOES equal the fallback, so on its own it
    proves nothing -- the third point is added in the second call and the SAME shape
    then draws. That pair is what the gate's two arms are measured against.

    THE JUNK VERTICES ARE CHOSEN ONE PER HALF of `isinstance(pt, (list, tuple)) and
    len(pt) == 2`, and the first draft's were not: `len("nope")` is 4 and
    `len([1, 2, 3])` is 3, so the LENGTH half rejected both on its own and dropping
    isinstance changed nothing -- that ablation came back DEAD. `"ab"` is the shape
    that separates them: a sequence of length two that is not a list, which slips past
    a length-only filter and then dies in `float("a")`, taking the whole polygon with
    it.

    AND THE BBOX IS WHAT MAKES THE LENGTH HALF BITE in the other direction. `[1, 2, 3]`
    passes isinstance, so a filter missing the length check reads `pt[0], pt[1]` off it
    and adds a vertex at (1, 2) pct -- a spike into the far corner. The triangle still
    has three or more points and still draws, so only its bounding box shows the
    difference.
    """
    pytest.importorskip("PIL")
    two = [[20, 20], [60, 20]]
    assert rasterize_primitives(
        [{"type": "polygon", "points": two}], width=100, height=100
    ) == []
    assert rasterize_primitives(
        [{"type": "polygon", "points": two + [[40, 60]]}], width=100, height=100
    ), "three points did not draw, so the empty result above was not the count gate"

    salvaged = rasterize_primitives(
        [{"type": "polygon",
          "points": [[20, 20], "nope", [60, 20], [1, 2, 3], "ab", [40, 60]]}],
        width=100, height=100,
    )
    assert salvaged, "one malformed vertex discarded the whole polygon"
    assert len(salvaged) >= 3
    assert min(p[0] for p in salvaged) == pytest.approx(20, abs=3)
    assert min(p[1] for p in salvaged) == pytest.approx(20, abs=3), (
        "a 3-element vertex was read as a point, spiking the outline to (1, 2)"
    )
    assert max(p[0] for p in salvaged) == pytest.approx(60, abs=3)


@pytest.mark.parametrize(
    "bad,raises",
    [
        ({"type": "rect", "x": 10, "y": 10, "h": 30}, "KeyError"),
        ({"type": "rect", "x": 10, "y": 10, "w": None, "h": 30}, "TypeError"),
        ({"type": "rect", "x": 10, "y": 10, "w": "wide", "h": 30}, "ValueError"),
    ],
    ids=["missing_key", "none_value", "unparseable_value"],
)
def test_rast6_a_malformed_shape_mid_segment_is_silently_dropped(np, bad, raises):
    """[SP-RAST-6] A2-POLYGO-8, measured down to what is still true of it.

    The finding recorded in this module's invariant block says a malformed primitive
    is silently skipped so "a partially-drawn room saves as a success with no signal
    in the response". The SERVICE-level half of that is no longer true: the caller
    counts whole segments that yielded no polygon and returns `skipped`.

    WHAT SURVIVES IS THE PARTIAL CASE, and it is what this test pins. One bad shape
    among three leaves a polygon that is NOT the one the user authored, and the
    segment still produced a polygon -- so the caller's `skipped` counter stays at
    zero and nothing anywhere reports the missing third of the room.

    THE THREE SHAPES OVERLAP, and that is load-bearing rather than tidy. The first
    draft authored three DISJOINT columns and failed: `mask_to_polygon` returns one
    loop, `max(loops, key=area)`, so disjoint shapes never union into a single
    outline and both rooms came back as the same lone column -- a fixture that could
    not contain the effect it was measuring. Overlapping them makes the middle shape
    the BRIDGE, so losing it is what the assertions can see.

    WHAT THAT MAKES VISIBLE IS WORSE THAN THE DROPPED SHAPE. With the bridge gone the
    mask holds two components, only the larger is kept, and the right-hand third of
    the room disappears as well -- so the saved room is not a damaged version of the
    authored one, it is a DIFFERENT room. The bbox assertion is what pins that: the
    outline stops at 45 rather than reaching 95. The area gap alone would read as
    "slightly smaller".

    THREE CASES FOR THE THREE MEMBERS of the `except (KeyError, TypeError, ValueError)`
    tuple -- a missing key, a None where a number belongs, and an unparseable string.
    Narrowing the tuple to any one member leaves the other two escaping, which is how
    each case is shown to earn its place rather than repeat its neighbours.
    """
    pytest.importorskip("PIL")
    left = {"type": "rect", "x": 5, "y": 40, "w": 40, "h": 20}
    middle = {"type": "rect", "x": 35, "y": 40, "w": 30, "h": 20}
    right = {"type": "rect", "x": 60, "y": 40, "w": 35, "h": 20}

    whole = rasterize_primitives([left, middle, right], width=100, height=100)
    damaged = rasterize_primitives([left, bad, right], width=100, height=100)

    assert max(p[0] for p in whole) == pytest.approx(95, abs=3), (
        "the authored room does not span the full width, so the fixture cannot show "
        "what losing the bridge costs"
    )
    assert damaged, "the %s shape took the whole segment down" % raises
    assert min(p[0] for p in damaged) == pytest.approx(5, abs=3)
    assert max(p[0] for p in damaged) == pytest.approx(45, abs=3), (
        "the right-hand piece survived, so the bridge shape was not dropped"
    )
    assert _area(damaged) < _area(whole) * 0.6


def test_rast7_libs_missing_and_all_subtracted_are_the_same_empty_answer(
    np, monkeypatch
):
    """[SP-RAST-7] A2-POLYGO-2, asserted as the conflation it is.

    numpy and Pillow are OPTIONAL and undeclared, so "not installed" is a real
    shipped configuration and the module-level `np` / `PIL_Image` globals ARE how it
    is represented -- patching them is the only in-process way to reach the install
    this guard exists for.

    THE POINT IS THAT THE THREE ANSWERS ARE IDENTICAL. A user whose host has no
    numpy, a user whose host has no Pillow, and a user who subtracted away everything
    they drew all get exactly `[]`, and the caller treats all three as "degenerate
    shape": it counts the segment as skipped, writes `custom_segments` with an empty
    `segments` list, and returns `saved: True`. The previously saved layout is gone
    and nothing distinguishes a missing library from a bad drawing.

    THIS TEST PINS THE DEFECT RATHER THAN THE FIX, deliberately -- separating the two
    changes a service's response over existing saved layouts, which is not a call to
    make inside a coverage pass. It will redden the moment the conflation is fixed,
    which is the signal wanted.

    THE `if not poly` GUARD IT CROSSES IS UNOBSERVABLE, measured: replacing it with
    `if False` leaves every test in all three files reaching this function green,
    because the scaling comprehension below it maps an empty polygon to the same `[]`.
    The subtracted-away case is here to execute that guard and to be one of the three
    indistinguishable answers -- the bite in this test comes from the two library
    halves, not from it.

    THE TWO LIBRARY HALVES ARE SEPARATE PATCHES because the guard is an `or`: dropping
    either half of `PIL_Image is None or np is None` leaves the other patch sailing
    past it into real work.
    """
    pytest.importorskip("PIL")
    shapes = [{"type": "rect", "x": 10, "y": 10, "w": 30, "h": 30}]
    assert rasterize_primitives(shapes, width=100, height=100), (
        "the control did not draw, so the empty answers below mean nothing"
    )

    all_subtracted = rasterize_primitives(
        shapes + [{"type": "rect", "x": 0, "y": 0, "w": 100, "h": 100,
                   "op": "subtract"}],
        width=100, height=100,
    )
    assert all_subtracted == [], "a fully subtracted drawing left a polygon behind"

    monkeypatch.setattr(sp_module, "PIL_Image", None)
    no_pil = rasterize_primitives(shapes, width=100, height=100)
    monkeypatch.undo()

    monkeypatch.setattr(sp_module, "np", None)
    no_numpy = rasterize_primitives(shapes, width=100, height=100)

    assert no_pil == [] and no_numpy == []
    assert no_pil == all_subtracted == no_numpy, (
        "A2-POLYGO-2: the caller cannot tell a missing library from a bad shape"
    )
