"""The stall capture renderer — one room, flat, trail and dot.

The interesting cases here are all ABSENCE cases. This renderer sits on a job-lifecycle
path and consumes values that are legitimately missing: a docked robot has no anchor, a
held map source nulls it, an unsegmented room has no pixels, and Pillow is an optional
dependency the install matrix expects to be missing. Each of those must degrade to a
smaller picture or to None — never to an exception, and never to a fabricated coordinate.

Coverage targets
----------------
[SC-1] the room's own pixels become the crop; other rooms are excluded.
[SC-2] flip_y flips the RASTER (raw row 0 = image bottom) and nothing else.
[SC-3] a room with no pixels yields None — absent, not a blank image.
[SC-4] no anchor draws no dot; it is never treated as (0, 0).
[SC-5] unparseable trail points are skipped, not collapsed to a corner.
[SC-6] absent Pillow yields None rather than raising on a lifecycle path.
[SC-7] the output is a real PNG and honours the max-edge cap.
[SC-8] the room-name pill draws, is optional, and never costs the render.
"""

from __future__ import annotations

import struct

import pytest

from custom_components.eufy_vacuum.mapping import stall_capture_render as scr

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _raster(width: int, height: int, blocks: dict[int, tuple[int, int, int, int]]) -> bytes:
    """A room-id raster: ``{room_id: (x0, y0, x1, y1)}`` inclusive, 0 elsewhere."""
    buf = bytearray(width * height)
    for rid, (x0, y0, x1, y1) in blocks.items():
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                buf[y * width + x] = rid
    return bytes(buf)


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(_PNG_MAGIC)
    return struct.unpack(">II", data[16:24])


# ---------------------------------------------------------------------------
# bbox / crop
# ---------------------------------------------------------------------------

def test_bbox_is_the_rooms_own_pixels_only():
    """[SC-1] A neighbouring room must not widen the crop."""
    rast = _raster(20, 20, {5: (4, 4, 7, 9), 6: (12, 1, 18, 18)})

    assert scr.room_bbox_from_raster(
        room_pixels=rast, width=20, height=20, room_id=5
    ) == (4, 4, 7, 9)


def test_flip_y_flips_the_raster_rows():
    """[SC-2] flip_y describes the RASTER (raw row 0 is the image bottom).

    The x range is unchanged; only the y range mirrors. Getting this wrong puts the crop
    and the (already-rendered-frame) anchor a whole flip apart, which renders a plausible
    image of the WRONG room.
    """
    rast = _raster(20, 20, {5: (4, 2, 7, 5)})

    assert scr.room_bbox_from_raster(
        room_pixels=rast, width=20, height=20, room_id=5, flip_y=False
    ) == (4, 2, 7, 5)
    assert scr.room_bbox_from_raster(
        room_pixels=rast, width=20, height=20, room_id=5, flip_y=True
    ) == (4, 14, 7, 17)


def test_a_room_with_no_pixels_is_absent_not_empty():
    """[SC-3] None, never a zero-size box — the caller must fall back to the whole map."""
    rast = _raster(20, 20, {5: (4, 4, 7, 9)})

    assert scr.room_bbox_from_raster(
        room_pixels=rast, width=20, height=20, room_id=9
    ) is None
    assert scr.render_room_capture(
        room_pixels=rast, width=20, height=20, room_id=9
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
    kw = dict(room_pixels=rast, width=24, height=24, room_id=5, scale=1)

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
    kw = dict(room_pixels=rast, width=24, height=24, room_id=5, scale=1)

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
        room_pixels=rast, width=20, height=20, room_id=5
    ) is None


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def test_output_is_a_png_cropped_to_the_room_with_padding():
    """[SC-7] Real PNG, sized from the room's bbox + padding, upscaled by `scale`."""
    pytest.importorskip("PIL")
    rast = _raster(40, 40, {5: (10, 10, 19, 14)})  # 10 x 5 room

    data = scr.render_room_capture(
        room_pixels=rast, width=40, height=40, room_id=5,
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
        room_pixels=rast, width=300, height=300, room_id=5,
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
    kw = dict(room_pixels=rast, width=60, height=60, room_id=5, scale=2)

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
        room_pixels=rast, width=40, height=40, room_id=5, label="Kitchen", scale=2
    )

    assert data is not None and data.startswith(_PNG_MAGIC)
