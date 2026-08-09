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

    Eufy samples at 2s so a ±30s window is a real trace. Roborock's pose comes from the
    map backdrop, which updates every ~30s, so the same window yields two or three points
    — and joining them would fabricate a route across the room in the one artifact whose
    job is to show what actually happened. A slow brand gets an honest dot instead.
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
