"""The stall capture renderer — one room, flat, trail and dot.

The interesting cases here are all ABSENCE cases. This renderer sits on a job-lifecycle
path and consumes values that are legitimately missing: a docked robot has no anchor, a
held map source nulls it, an unsegmented room has no pixels, and Pillow is an optional
dependency the install matrix expects to be missing. Each of those must degrade to a
smaller picture or to None — never to an exception, and never to a fabricated coordinate.

Coverage targets
----------------
[SC-1] the room's own pixels become the crop; other rooms are excluded.
[SC-2] the raster is OFFSET into the main grid and the render flips; points are neither.
[SC-3] a room with no pixels yields None — absent, not a blank image.
[SC-4] no anchor draws no dot; it is never treated as (0, 0).
[SC-5] unparseable trail points are skipped, not collapsed to a corner.
[SC-6] absent Pillow yields None rather than raising on a lifecycle path.
[SC-7] the output is a real PNG and honours the max-edge cap.
[SC-8] the room-name pill draws, is optional, and never costs the render.
[SC-9] rid_shift is honoured — a raw-byte compare matches nothing on Eufy.
[SC-10] too few DISTINCT points draw no trail — a slow brand must not get a fabricated path.
[SC-11] the capture is rotated to the user's map orientation; the label stays level.
[SC-12] the ±window is DERIVED from a brand's declared pose cadence, floored at the
        historical 30 s so a fast brand's picture does not change.
[SC-13] sparse samples render as breadcrumbs, never a line — what lets the window widen
[SC-14] C16: a NON-FINITE pose point is rejected by `_norm_to_px`, and an infinite
[SC-20] a trail point whose ELEMENTS are not numbers is skipped -- the shoulder
        just past [SC-5]'s shape guard, which answers None/str before the float().
[SC-21] room_id <= 0 yields no cells. The raster background IS 0, so the ablated
        guard selects the whole floor.
[SC-22] a buffer shorter than its declared size is refused whole, not salvaged.
[SC-23] a room entirely off the canvas returns None, never a blank image.
[SC-24] cells outside the clamped crop are clipped, pinned by a width PAIR (4 on a
        6-wide canvas, 8 on a 12-wide one).
[SC-25] Pillow < 10.1 has no `size=` on load_default; the no-arg form answers.
        segment cannot reach the chevron loop. `while d < seg` with seg=inf never
        terminates — a HANG on an executor thread, on the job-lifecycle path, not a
        wrong picture. `Infinity` is reachable because the pose ring is parsed with a
        bare `json.loads`, which accepts that non-standard literal.
        for a coarse brand without the extra samples becoming extra invented route.
"""

from __future__ import annotations

import struct

import pytest

from custom_components.eufy_vacuum.mapping import stall_capture_render as scr

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _raster(
    width: int,
    height: int,
    blocks: dict[int, tuple[int, int, int, int]],
    rid_shift: int = 0,
) -> bytes:
    """A room-id raster: ``{room_id: (x0, y0, x1, y1)}`` inclusive, 0 elsewhere.

    ``rid_shift`` packs the id the way Eufy does (``id << 2``), so a test can build a
    real Eufy-shaped raster rather than assuming the byte is the id.
    """
    buf = bytearray(width * height)
    for rid, (x0, y0, x1, y1) in blocks.items():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                buf[y * width + x] = rid << rid_shift
    return bytes(buf)


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(_PNG_MAGIC)
    return struct.unpack(">II", data[16:24])


# ---------------------------------------------------------------------------
# bbox / crop
# ---------------------------------------------------------------------------

def _bbox(cells):
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return (min(xs), min(ys), max(xs), max(ys))


def test_cells_are_the_rooms_own_only():
    """[SC-1] A neighbouring room must not widen the crop."""
    rast = _raster(20, 20, {5: (4, 4, 7, 9), 6: (12, 1, 18, 18)})

    cells = scr.room_cells(room_pixels=rast, ro_width=20, ro_height=20, room_id=5)

    assert _bbox(cells) == (4, 4, 7, 9)


def test_rid_shift_is_honoured_not_a_raw_byte_compare():
    """[SC-9] Eufy packs the id (``byte >> 2``); Roborock's decoder resolves it (shift 0).

    A raw-byte compare works on one brand and silently matches NOTHING on the other —
    which renders as "this room has no pixels" rather than as an error.
    """
    packed = _raster(20, 20, {5: (4, 4, 7, 9)}, rid_shift=2)

    assert scr.room_cells(
        room_pixels=packed, ro_width=20, ro_height=20, room_id=5, rid_shift=2
    ), "shift-aware lookup must find the room"
    assert scr.room_cells(
        room_pixels=packed, ro_width=20, ro_height=20, room_id=5, rid_shift=0
    ) == [], "a raw-byte compare must NOT accidentally match"


def test_raster_offset_and_flip_place_the_room_in_rendered_space():
    """[SC-2] The raster is OFFSET into the main grid, and the render flips top-bottom.

    Eufy's raster is ro_w x ro_h at (ro_dx, ro_dy) inside a larger canvas, and the render
    mirrors. An earlier draft treated the raster AS the canvas and skipped the offset,
    which produces a perfectly plausible image of the wrong region — the failure most
    likely to survive a glance, and the reason this is pinned.
    """
    rast = _raster(10, 10, {5: (2, 1, 4, 3)})
    cells = scr.room_cells(room_pixels=rast, ro_width=10, ro_height=10, room_id=5)

    # No offset, no flip: rendered == raster.
    plain = [scr._to_rendered(x, y, ro_dx=0, ro_dy=0, canvas_height=10, flip_y=False)
             for x, y in cells]
    assert _bbox(plain) == (2, 1, 4, 3)

    # Offset only: shifted into the main grid.
    off = [scr._to_rendered(x, y, ro_dx=30, ro_dy=40, canvas_height=100, flip_y=False)
           for x, y in cells]
    assert _bbox(off) == (32, 41, 34, 43)

    # Offset + flip: y mirrors about the CANVAS height, x untouched.
    both = [scr._to_rendered(x, y, ro_dx=30, ro_dy=40, canvas_height=100, flip_y=True)
            for x, y in cells]
    assert _bbox(both) == (32, 100 - 1 - 43, 34, 100 - 1 - 41)


def test_a_room_with_no_pixels_is_absent_not_empty():
    """[SC-3] None, never a zero-size box — the caller must fall back to the whole map."""
    rast = _raster(20, 20, {5: (4, 4, 7, 9)})

    assert scr.room_cells(
        room_pixels=rast, ro_width=20, ro_height=20, room_id=9
    ) == []
    assert scr.render_room_capture(
        room_pixels=rast, ro_width=20, ro_height=20, room_id=9
    ) is None


# ---------------------------------------------------------------------------
# absence handling in the render
# ---------------------------------------------------------------------------

def test_no_anchor_draws_no_dot_and_is_not_the_origin():
    """[SC-4] A docked robot / held source nulls the anchor. That is not position (0,0).

    Compared by BYTES against the same render with the anchor omitted: if None were being
    coerced to a coordinate, a dot would appear and the images would differ.
    """
    pytest.importorskip("PIL")
    rast = _raster(24, 24, {5: (2, 2, 20, 20)})
    kw = dict(room_pixels=rast, ro_width=24, ro_height=24, room_id=5, scale=1)

    explicit_none = scr.render_room_capture(anchor=None, **kw)
    omitted = scr.render_room_capture(**kw)

    assert explicit_none is not None
    assert explicit_none == omitted, "a null anchor must draw nothing at all"

    with_dot = scr.render_room_capture(anchor=(0.5, 0.5), **kw)
    assert with_dot != explicit_none, "the comparison is only meaningful if a dot shows"


def test_garbage_trail_points_are_skipped_not_collapsed():
    """[SC-5] A bad sample must not drag the line to a corner.

    The pose ring can hand back nulls (docked ticks are recorded as None-runs), so the
    renderer sees them. Dropping one point is correct; mapping it to 0,0 draws a line
    across the room that never happened.
    """
    pytest.importorskip("PIL")
    rast = _raster(24, 24, {5: (2, 2, 20, 20)})
    kw = dict(room_pixels=rast, ro_width=24, ro_height=24, room_id=5, scale=1)

    clean = [(0.30, 0.30), (0.40, 0.40), (0.50, 0.50)]
    dirty = [(0.30, 0.30), None, "nope", (0.40, 0.40), (float("nan"), 0.1), (0.50, 0.50)]

    assert scr.render_room_capture(trail=dirty, **kw) == scr.render_room_capture(
        trail=clean, **kw
    )


def test_absent_pillow_returns_none_rather_than_raising(monkeypatch):
    """[SC-6] Pillow is optional (reqs=[]) and this runs on a JOB LIFECYCLE path.

    A missing optional dependency must cost the picture, never the run.
    """
    monkeypatch.setattr(scr, "Image", None)
    monkeypatch.setattr(scr, "ImageDraw", None)
    rast = _raster(20, 20, {5: (4, 4, 7, 9)})

    assert scr.render_room_capture(
        room_pixels=rast, ro_width=20, ro_height=20, room_id=5
    ) is None


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def test_output_is_a_png_cropped_to_the_room_with_padding():
    """[SC-7] Real PNG, sized from the room's bbox + padding, upscaled by `scale`."""
    pytest.importorskip("PIL")
    rast = _raster(40, 40, {5: (10, 10, 19, 14)})  # 10 x 5 room

    data = scr.render_room_capture(
        room_pixels=rast, ro_width=40, ro_height=40, room_id=5,
        padding_px=2, scale=3,
    )

    assert data is not None and data.startswith(_PNG_MAGIC)
    # (10 + 2*2) x (5 + 2*2) = 14 x 9, tripled
    assert _png_size(data) == (14 * 3, 9 * 3)


def test_scale_is_capped_so_a_big_room_cannot_explode():
    """[SC-7] max_edge_px bounds the output; a notification image is not a poster."""
    pytest.importorskip("PIL")
    rast = _raster(300, 300, {5: (0, 0, 299, 299)})

    data = scr.render_room_capture(
        room_pixels=rast, ro_width=300, ro_height=300, room_id=5,
        padding_px=0, scale=8, max_edge_px=600,
    )

    assert data is not None
    w, h = _png_size(data)
    assert max(w, h) <= 600, f"got {w}x{h}"


def test_label_pill_is_drawn_and_is_optional():
    """[SC-8] The room-name pill: black on white, so the image carries its own contrast.

    A notification lands on a light OR dark background and the renderer never learns which.
    Every other element is mid-tone by design; the pill is the one thing that must read
    either way, which is why it is black-on-white rather than themed.
    """
    pytest.importorskip("PIL")
    rast = _raster(60, 60, {5: (5, 5, 54, 54)})
    kw = dict(room_pixels=rast, ro_width=60, ro_height=60, room_id=5, scale=2)

    plain = scr.render_room_capture(**kw)
    pilled = scr.render_room_capture(label="Kitchen", **kw)

    assert plain is not None and pilled is not None
    assert pilled != plain, "the label must actually draw"
    # Same canvas — the pill overlays, it does not resize the crop.
    assert _png_size(pilled) == _png_size(plain)


def test_a_pill_failure_never_costs_the_render(monkeypatch):
    """[SC-8] The label is decoration on a job-lifecycle path; the picture outranks it."""
    pytest.importorskip("PIL")
    monkeypatch.setattr(scr, "_load_font", lambda size: None)
    rast = _raster(40, 40, {5: (5, 5, 34, 34)})

    data = scr.render_room_capture(
        room_pixels=rast, ro_width=40, ro_height=40, room_id=5, label="Kitchen", scale=2
    )

    assert data is not None and data.startswith(_PNG_MAGIC)


def test_too_few_points_draw_no_trail_at_all():
    """[SC-10] A line between two samples asserts a straight path that never happened.

    Eufy's fork pose refreshes ~2s and its sampler ticks at 2.0s, so a ±30s window is ~30
    genuinely distinct positions and a real trace. Joining two far-apart samples would
    fabricate a route across the room in the one artifact whose job is to show what
    actually happened.

    (The claim that used to sit here — that Roborock's window "yields two or three points"
    — was wrong in a way that mattered: it yielded ZERO, because no anchor was ever
    recorded for it. Density, not the shortfall, is what this threshold guards; the
    line-vs-breadcrumb tests below cover the coarse-brand case that the count alone
    cannot. The dedup is this module's own, at render time — not the sampler's.)
    """
    pytest.importorskip("PIL")
    rast = _raster(40, 40, {5: (2, 2, 37, 37)})
    kw = dict(room_pixels=rast, ro_width=40, ro_height=40, room_id=5, scale=1)

    none_at_all = scr.render_room_capture(trail=[], **kw)
    two_points = scr.render_room_capture(trail=[(0.2, 0.2), (0.8, 0.8)], **kw)

    assert two_points == none_at_all, "two samples must not become a line"

    enough = scr.render_room_capture(
        trail=[(0.2, 0.2), (0.4, 0.3), (0.6, 0.5), (0.8, 0.8)], **kw
    )
    assert enough != none_at_all, "a real trace must still draw"


# ---------------------------------------------------------------------------
# [SC-12] the window is derived from a declared cadence, not assumed
# ---------------------------------------------------------------------------

def test_a_fast_pose_keeps_the_historical_thirty_second_window():
    """[SC-12] Eufy's ~2s pose needs only ~5s to bank 4 points, so the FLOOR decides.

    Pinned because the floor is what makes this change a no-op for Eufy: the window it
    already had is the window it keeps, and any regression shows up here rather than as a
    quietly different picture on the brand that was working.
    """
    assert scr.trail_window_seconds(2.0) == 30


def test_a_coarse_pose_widens_the_window_to_hold_the_same_evidence():
    """[SC-12] Roborock's ~30s map refresh needs ±75s to bank 5 positions.

    Measured, not chosen: 17 distinct anchors over ~8 minutes on Ivy (2026-08-09) is one
    new position per ~28s, so a ±30s window holds about two — below the line threshold and
    the reason the capture had no trail even once anchors were recorded.
    """
    assert scr.trail_window_seconds(30.0) == 75


# inf and -inf added 2026-08-24: they were the only bad inputs this list did not
# carry, and they were the only ones that did not fall back — `trail_window_seconds`
# RAISED ValueError on inf, because the ceil trick evaluates `-(-inf // 1)` to NaN.
# Every other value here already returned 30, which is what made the gap invisible.
@pytest.mark.parametrize(
    "bad", [None, 0, -5, "fast", float("nan"), float("inf"), float("-inf")]
)
def test_an_undeclared_or_nonsense_cadence_falls_back_to_the_floor(bad):
    """[SC-12] A capture with a plain-but-correct window beats no capture at all."""
    assert scr.trail_window_seconds(bad) == 30


def test_the_window_scales_with_the_declared_cadence():
    """[SC-12] The relationship is the contract — a slower brand banks strictly more."""
    assert scr.trail_window_seconds(60.0) > scr.trail_window_seconds(30.0)
    assert scr.trail_window_seconds(30.0) > scr.trail_window_seconds(2.0)


# ---------------------------------------------------------------------------
# [SC-13] sparse samples are breadcrumbs, never a line
# ---------------------------------------------------------------------------

def _trail_kw():
    return dict(
        room_pixels=_raster(40, 40, {5: (2, 2, 37, 37)}),
        ro_width=40, ro_height=40, room_id=5, scale=1,
    )


_FOUR_POINTS = [(0.2, 0.2), (0.4, 0.3), (0.6, 0.5), (0.8, 0.8)]


def test_sparse_samples_draw_breadcrumbs_not_a_line():
    """[SC-13] The same points must still render DIFFERENTLY by cadence.

    REVISED 2026-08-09. This originally read "dense ones connect, sparse ones stay separate
    observations" — sparse points are now connected too, so that rationale is retired. The
    reason it changed: refusing to connect them also threw away the ORDER, and inside a
    single-room crop a segment cannot cross a wall, so the most it can overstate is a corner
    the robot drove around rather than through. Losing which way it was travelling costs
    more than that.

    What the cadence still decides is whether the individual OBSERVATIONS are drawn: a
    coarse brand gets its samples marked as dots on the line, because at 30s apart each one
    is a fact worth showing; a 2s brand does not, because thirty of them would be noise.
    Remove the gap check and the two renders become identical.
    """
    pytest.importorskip("PIL")
    kw = _trail_kw()

    dense = scr.render_room_capture(trail=_FOUR_POINTS, trail_gap_s=2.0, **kw)
    sparse = scr.render_room_capture(trail=_FOUR_POINTS, trail_gap_s=30.0, **kw)
    nothing = scr.render_room_capture(trail=[], **kw)

    assert dense != sparse, "a coarse cadence must not render as a connected line"
    assert sparse != nothing, "breadcrumbs must actually be drawn"


def test_the_oldest_breadcrumb_is_paler_than_the_newest():
    """[SC-17] Direction of travel must be IN THE PIXELS, encoded as lightness.

    The ring hands anchors over oldest-first, so which way the robot was going is a fact we
    hold — and "was it heading INTO that corner or backing out of it" is the first thing
    anyone asks of a stall picture. Lightness rather than hue because a colour ramp is
    invisible to ~8% of men and this image carries no legend to fall back on; it cannot,
    since a worded key would be the first English baked into a PNG shipped to an
    18-language audience.

    ASSERTS THE PIXELS, not "the bytes changed". The first draft of this test rendered the
    trail forwards and reversed and asserted the PNGs differed — it passed with the fade AND
    the chevrons both ablated, because reversing a polyline perturbs the encoded bytes for
    reasons that have nothing to do with direction. A gate that is green for an unrelated
    reason is worse than no gate. An intermediate crumb colour cannot exist unless the
    gradient actually ran.
    """
    pytest.importorskip("PIL")
    import io

    from PIL import Image

    kw = _trail_kw()
    png = scr.render_room_capture(trail=_FOUR_POINTS, trail_gap_s=30.0, **kw)

    # getcolors, not getdata: getdata is deprecated and disappears in Pillow 14.
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    colours = {colour for _count, colour in (img.getcolors(1 << 24) or [])}
    between = [
        c for c in colours
        if all(min(f, t) < c[i] < max(f, t)
               for i, (f, t) in enumerate(zip(scr.FILL_RGB, scr.TRAIL_RGB)))
    ]

    assert between, "no crumb colour between the room fill and the trail colour — no fade ran"


@pytest.mark.parametrize("gap_s", [2.0, 30.0])
def test_chevrons_are_drawn_on_both_cadences(monkeypatch, gap_s):
    """[SC-18] The arc-length spacing exists so ONE implementation serves both brands.

    Eufy's ~2s pose puts ~30 points in the window and Roborock's ~30s puts a handful, so a
    chevron per SEGMENT would be a sawtooth on one brand and adequate on the other. Walking
    the distance instead of the point list is what makes both readable — and a chevron pass
    that silently no-ops on one cadence would leave that brand direction-blind while the
    other looked fine, which is the shape of every brand bug in this codebase.
    """
    pytest.importorskip("PIL")
    kw = _trail_kw()

    drawn = scr.render_room_capture(trail=_FOUR_POINTS, trail_gap_s=gap_s, **kw)
    monkeypatch.setattr(scr, "_draw_direction_chevrons", lambda *a, **k: None)
    without = scr.render_room_capture(trail=_FOUR_POINTS, trail_gap_s=gap_s, **kw)

    assert drawn != without, f"no chevrons were drawn at trail_gap_s={gap_s}"


def test_breadcrumbs_need_only_two_observations():
    """[SC-13] The count rule protects a POLYLINE; breadcrumbs connect nothing.

    Two dots are two places the robot was — two facts, not an assertion about travel. The
    line threshold refuses this same input, and that difference is deliberate.
    """
    pytest.importorskip("PIL")
    kw = _trail_kw()
    two = [(0.2, 0.2), (0.8, 0.8)]

    nothing = scr.render_room_capture(trail=[], **kw)
    as_line = scr.render_room_capture(trail=two, trail_gap_s=2.0, **kw)
    as_crumbs = scr.render_room_capture(trail=two, trail_gap_s=30.0, **kw)

    assert as_line == nothing, "two dense samples are still not a line"
    assert as_crumbs != nothing, "two sparse samples are two honest observations"


@pytest.mark.parametrize("unreadable", [None, "soon", float("nan"), object()])
def test_an_unknown_cadence_keeps_the_historical_line(unreadable):
    """[SC-13] An unreadable cadence is the caller failing to say, not a claim of coarseness.

    So it degrades to what was drawn before rather than raising — this runs on a job
    lifecycle path, and the maintainer dev card drives the same function directly.
    """
    pytest.importorskip("PIL")
    kw = _trail_kw()

    assert scr.render_room_capture(trail=_FOUR_POINTS, trail_gap_s=unreadable, **kw) == (
        scr.render_room_capture(trail=_FOUR_POINTS, **kw)
    )


def test_a_stationary_robot_is_not_breadcrumbs_either():
    """[SC-13] Dedup runs before the draw-style choice, so a wedged robot on a coarse
    brand collapses to ONE point and draws nothing — the case this feature photographs
    must not become a scatter of dots implying movement."""
    pytest.importorskip("PIL")
    kw = _trail_kw()

    assert scr.render_room_capture(
        trail=[(0.5, 0.5)] * 12, trail_gap_s=30.0, **kw
    ) == scr.render_room_capture(trail=[], **kw)


def test_a_stationary_robot_is_not_a_trail():
    """[SC-10] Identical consecutive anchors are ONE point, not evidence of movement.

    The pose sampler repeats an identical pose while parked, and a wedged robot repeats
    one too. Counting repeats toward the trail would draw a path for the exact case this
    feature exists to photograph — a vacuum that has stopped moving.
    """
    pytest.importorskip("PIL")
    rast = _raster(40, 40, {5: (2, 2, 37, 37)})
    kw = dict(room_pixels=rast, ro_width=40, ro_height=40, room_id=5, scale=1)

    stationary = [(0.5, 0.5)] * 12

    assert scr.render_room_capture(trail=stationary, **kw) == scr.render_room_capture(
        trail=[], **kw
    )


def test_rotation_matches_the_users_map_orientation():
    """[SC-11] The capture is rotated to the orientation the user actually sees.

    The card rotates its content block with CSS transform:rotate(Ndeg) — CLOCKWISE — while
    PIL rotates counter-clockwise, so the angle is negated. Without it the image is correct
    and unrecognisable: a shape the user has never seen at that angle, which for a glanced
    notification is worse than no picture.
    """
    pytest.importorskip("PIL")
    # A deliberately non-square room, so a wrong angle cannot pass by symmetry.
    rast = _raster(60, 60, {5: (10, 20, 49, 29)})   # 40 wide x 10 tall
    kw = dict(room_pixels=rast, ro_width=60, ro_height=60, room_id=5, padding_px=0, scale=1)

    flat = scr.render_room_capture(rotation_deg=0, **kw)
    turned = scr.render_room_capture(rotation_deg=90, **kw)

    assert flat is not None and turned is not None
    fw, fh = _png_size(flat)
    tw, th = _png_size(turned)
    assert (fw, fh) == (40, 10)
    assert (tw, th) == (10, 40), "a quarter turn must swap the axes"


def test_a_full_turn_is_a_no_op_and_the_angle_is_normalised():
    """[SC-11] 360 and 0 are the same picture; the angle is taken modulo 360."""
    pytest.importorskip("PIL")
    rast = _raster(40, 40, {5: (5, 5, 30, 20)})
    kw = dict(room_pixels=rast, ro_width=40, ro_height=40, room_id=5, scale=1)

    assert scr.render_room_capture(rotation_deg=360, **kw) == scr.render_room_capture(
        rotation_deg=0, **kw
    )


# ---------------------------------------------------------------------------
# [SC-14] C16 - non-finite pose points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
@pytest.mark.parametrize("axis", [0, 1])
def test_sc14_a_non_finite_point_is_not_a_point(bad, axis):
    """[SC-14] RED BEFORE THE FIX for inf (NaN already passed).

    The guard was `nx != nx`, which is a NaN test and lets both infinities through. Both
    axes are exercised because the guard is written per-axis and half of it going missing
    would look identical for whichever axis the test happened to pick.
    """
    pt = [0.5, 0.5]
    pt[axis] = bad
    assert scr._norm_to_px(pt, 100, 100) is None


def test_sc14_a_finite_point_still_resolves():
    """[SC-14] RED IF THE GUARD IS INVERTED OR TOO WIDE. Rejecting everything would also
    make the hang impossible, and would also make every capture blank."""
    assert scr._norm_to_px([0.5, 0.5], 100, 100) == (50.0, 50.0)
    assert scr._norm_to_px([0.0, 1.0], 200, 80) == (0.0, 80.0)


def test_sc14_the_chevron_loop_cannot_be_made_to_hang(monkeypatch):
    """[SC-14] The failure this exists to prevent, driven through the REAL function.

    `Infinity` is reachable: `pose_store.read_range` parses the ring with a bare
    `json.loads`, which accepts the non-standard literal. One such point makes
    `seg = (dx*dx + dy*dy) ** 0.5` infinite, and `while d < seg: ... d += spacing` never
    terminates — on an executor thread, on the job-lifecycle path.

    RED BEFORE THE FIX BY TIMING OUT, not by asserting: a hang has no return value to
    check. Reproduced against the pre-fix code at 15 s. The call is made directly with a
    raw infinite point so this covers the LOOP guard specifically, not the `_norm_to_px`
    gate upstream of it — the two are independent and either alone would close the real
    path.
    """
    class _Draw:
        def line(self, *a, **k):
            pass

        def polygon(self, *a, **k):
            pass

    pts = [(0.0, 0.0), (float("inf"), 50.0), (10.0, 10.0)]
    scr._draw_direction_chevrons(_Draw(), pts, (255, 0, 0), 2, 20.0, 6.0)


def test_sc14_json_loads_really_does_accept_infinity():
    """[SC-14] The reachability premise, pinned. If a future change routes the pose ring
    through a parser that rejects `Infinity`, the guards above stop being load-bearing and
    this test says so by going red — which is the moment to re-read C16, not delete it."""
    import json

    assert json.loads('{"p": [Infinity, 0.5]}')["p"][0] == float("inf")


# ---------------------------------------------------------------------------
# [SC-20]..[SC-25] -- the guards no test reached. Every expected value below was
# derived by RUNNING the real function, not reasoned out; the clipped widths and the
# byte-identity in [SC-20] in particular are measurements, not predictions.
# ---------------------------------------------------------------------------

def test_sc20_a_point_whose_ELEMENTS_are_not_numbers_is_skipped():
    """[SC-20] The shoulder just past [SC-5]'s guard.

    [SC-5] already pins "a bad sample must not drag the line to a corner" and feeds
    `None`, `"nope"` and a NaN. NONE OF THEM REACHES THE `float()` CALL: `_norm_to_px`
    opens with `if not isinstance(pt, (list, tuple)) or len(pt) < 2: return None`, so a
    None and a bare string are answered by the SHAPE guard two lines earlier, and the
    NaN tuple converts fine and is caught by the non-finite check afterwards.

    The `except (TypeError, ValueError)` around the conversion therefore had no test at
    all, and reaching it needs what this uses: a well-shaped tuple of length 2 whose
    ELEMENTS cannot be floated. `("abc", 0.5)` raises ValueError and `(None, 0.2)`
    raises TypeError, which is both arms of the one `except`.

    THE ASSERTION IS BYTE-IDENTITY WITH THE JUNK-FREE RENDER, which is stronger than
    "it returned a PNG": an all-junk trail ALSO returns a PNG, just without a trail
    drawn. Measured -- junk-free and junk-interleaved both come back at 178 bytes and
    compare equal, while the all-junk render is 97 bytes. The third assertion is what
    makes the second one mean something.
    """
    pytest.importorskip("PIL")
    rast = _raster(20, 20, {5: (4, 4, 7, 9)})
    kw = dict(room_pixels=rast, ro_width=20, ro_height=20, room_id=5,
              canvas_width=20, canvas_height=20, scale=2, padding_px=1)

    clean = [(0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.4, 0.4)]
    # The junk rows are INTERLEAVED, not trailing, so a `break` in place of the skip
    # would lose the points after them and change the drawing.
    dirty = [(0.1, 0.1), ("abc", 0.5), (None, 0.2), (0.2, 0.2), (0.3, 0.3), (0.4, 0.4)]

    assert scr.render_room_capture(trail=dirty, **kw) == scr.render_room_capture(
        trail=clean, **kw
    ), "an unfloatable element changed the drawing instead of being dropped"

    # ...and the comparison above is not vacuous: losing the whole trail DOES differ.
    assert scr.render_room_capture(trail=[("abc", 0.5), (None, 0.2)], **kw) != (
        scr.render_room_capture(trail=clean, **kw)
    )


def test_sc21_a_non_positive_room_id_yields_no_cells():
    """[SC-21] `room_id <= 0` is refused, and 0 is a REAL input, not a paranoid one.

    The raster's background is 0, so a room id of 0 would select every unassigned
    pixel in the image -- measured: ablating the guard turns this from an empty list
    into the whole background. That is the difference between "no room" and "the entire
    floor is one room".

    THE `-1` CASE NEEDS A 255 BYTE IN THE RASTER, which a first draft of this test did
    not have -- found by an adversarial audit and confirmed by ablation. The fast path
    masks `target = room_id & 0xFF`, so `-1` becomes 255; with no 255 byte present the
    lookup finds nothing and returns [] whether the guard exists or not. Narrowing the
    guard to `== 0` left the test GREEN, so the assertion was an identity and the
    claim that "both halves are driven" was false. The raster now carries a 255 block,
    so a guard that admitted negative ids would select it.
    """
    rast = _raster(20, 20, {5: (4, 4, 7, 9), 255: (12, 12, 14, 14)})
    kw = dict(room_pixels=rast, ro_width=20, ro_height=20)

    # The control: the real room is found, so the empties below are the guard talking.
    assert len(scr.room_cells(room_id=5, **kw)) == 24

    assert scr.room_cells(room_id=0, **kw) == []
    assert scr.room_cells(room_id=-1, **kw) == [], (
        "a negative id was masked to 255 and selected the 255 block"
    )


def test_sc22_a_buffer_shorter_than_its_declared_size_yields_no_cells():
    """[SC-22] A raster shorter than `ro_width * ro_height` is refused whole.

    The guard protects an index walk that would otherwise read off the end of the
    buffer. The truncation here KEEPS THE ROOM'S OWN ROWS: the room occupies rows 4-9
    and the buffer is cut at row 10, so a partial walk would still find all 24 of its
    cells and the test would pass for the wrong reason. The claim is that a short
    buffer is refused on its DECLARED size rather than salvaged, so the input has to
    be one where salvaging would have succeeded.
    """
    rast = _raster(20, 20, {5: (4, 4, 7, 9)})
    assert len(scr.room_cells(room_pixels=rast, ro_width=20, ro_height=20,
                              room_id=5)) == 24

    short = rast[:200]          # rows 0-9 only; the room's rows 4-9 are all present
    assert scr.room_cells(room_pixels=short, ro_width=20, ro_height=20, room_id=5) == []


def test_sc23_a_room_entirely_off_the_canvas_returns_none():
    """[SC-23] An empty crop returns None, and None must stay distinguishable.

    `ro_dx` offsets the room into canvas space, so a large enough offset puts every
    cell past the right edge. `cx1` is clamped to `cvw - 1` while `cx0` is clamped at
    0, so the width goes non-positive and there is nothing to draw.

    The module's contract is that None means "nothing could be drawn" and is never a
    blank image -- absence has to stay distinguishable from "an empty room was
    rendered". A test that accepted either would not notice the day this started
    returning a transparent PNG. `padding_px=0` so the pad cannot drag the crop back
    inside the canvas and hide the case.
    """
    pytest.importorskip("PIL")
    rast = _raster(10, 10, {5: (2, 2, 5, 5)})
    assert scr.render_room_capture(
        room_pixels=rast, ro_width=10, ro_height=10, room_id=5,
        ro_dx=100, ro_dy=0, canvas_width=50, canvas_height=50, padding_px=0,
    ) is None


def test_sc24_cells_outside_the_crop_are_clipped_not_drawn():
    """[SC-24] The per-cell bounds test inside the paint loop.

    The crop is clamped to the canvas, but `rendered` still holds every cell of the
    room -- including the ones the clamp cut off. Without the bounds test those cells
    index outside the new image.

    WHAT EACH ASSERTION ACTUALLY PINS, corrected after an audit pointed out the
    mis-attribution. The width PAIR pins the crop CLAMP at `cx1 = min(cvw - 1, ...)`,
    which runs before the paint loop: the same room (x 2..9) renders 4 pixels across on
    a 6-wide canvas and 8 on a 12-wide one, both measured. One figure alone would be a
    magic number; the pair shows the width tracking the CANVAS rather than the room.

    The per-cell bounds test inside the loop is pinned by this test too, but through
    the EXCEPTION its absence raises rather than through the size: `rendered` still
    holds every cell of the room including the ones the clamp cut off, so without the
    test `px[x - cx0, y - cy0]` indexes outside the new image and Pillow raises. That
    is what the ablation reddens. Both claims are real; only the labels were wrong.

    `scale=1` so the PNG dimensions are the crop dimensions, with no upscale between.
    """
    pytest.importorskip("PIL")
    rast = _raster(12, 12, {5: (2, 2, 9, 9)})
    kw = dict(room_pixels=rast, ro_width=12, ro_height=12, room_id=5,
              canvas_height=12, scale=1, padding_px=0)

    clipped = scr.render_room_capture(canvas_width=6, **kw)
    assert _png_size(clipped) == (4, 8), "the clip did not follow the narrow canvas"

    whole = scr.render_room_capture(canvas_width=12, **kw)
    assert _png_size(whole) == (8, 8), "the wide canvas should fit the whole room"


def test_sc25_an_old_pillow_without_the_size_argument_still_gets_a_font(monkeypatch):
    """[SC-25] `ImageFont.load_default(size=...)` is Pillow >= 10.1 only.

    The floor in `hacs.json` is older than that, so the keyword call raises TypeError
    on a supported install and the no-argument form is what has to answer. This is the
    same shape as the HA-API floor problem: the test image runs ONE Pillow version and
    cannot see the other, so the fallback is reachable in the field and unreachable
    here unless it is forced.

    The sentinel is a bare `object()` on purpose. A real font would compare equal to
    what the modern path returns, and `None` is what the next fallback yields -- so
    neither would show WHICH branch answered.
    """
    pytest.importorskip("PIL")
    import PIL.ImageFont as image_font

    sentinel = object()

    def old_pillow(*args, **kwargs):
        if kwargs:
            raise TypeError("load_default() takes no keyword arguments")
        return sentinel

    monkeypatch.setattr(image_font, "load_default", old_pillow)
    assert scr._load_font(14) is sentinel
