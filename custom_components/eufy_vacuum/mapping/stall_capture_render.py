"""Render a stall capture: one room, flat, with the robot's trail and position.

WHAT THIS DRAWS, AND WHY IT IS DELIBERATELY PLAIN. A room silhouette in one neutral fill,
the last stretch of travel as a thin line, and a dot for where the robot stopped. Nothing
else — no floor textures, no per-room palette, no attempt to resemble the card's map.

That is a decision, not a shortcut (Chris, 2026-08-08). This image is read one-handed, at
a glance, from another room, attached to a notification that already says the room's NAME
in text. A flat silhouette answers "where is it and what is around it" faster than a
faithful render would, and — the durable reason — **a deliberately plain image cannot
drift from a design it never imitated.** An earlier draft resolved the card's themeable
room-fill cascade here; that would have made this a THIRD copy of a palette which has
already drifted once (see ``src/cards/map-room-color.js``, which exists because two copies
diverged), and bought a permanent sync obligation for a colour the reader does not need.

PURE. No Home Assistant imports, no I/O, no adapter lookups — bytes in, PNG bytes out.
That is what lets the maintainer dev card exercise it repeatedly and what lets tests cover
it without a hass fixture.

COORDINATE CONTRACT — the one place bugs will live, so it is stated rather than implied:

* ``room_pixels`` is one room-id byte per pixel, row-major, ``width * height`` long. Both
  brands produce this (Eufy ``eufy_room_pixels_v1``; Roborock via
  ``decode_roborock_v1_segments``).
* ``flip_y`` describes the RASTER only — raw row 0 being the image BOTTOM. It is applied
  when building the mask so the mask lands in the rendered frame.
* ``anchor`` and ``trail`` are already normalized 0–1 **in the rendered frame** — which is
  what ``map_source.robot_anchor`` gives you (it comes out of ``normalize_rendered``).
  They are NOT device coordinates and must never be passed through
  ``vacuum_to_normalized``, which is for hazard layers stored in raw vacuum coords.

So: the raster may need flipping, the points never do.
"""

from __future__ import annotations

import io
from typing import Any, Iterable

try:  # Pillow is an OPTIONAL dependency (reqs=[]); the install matrix expects it absent.
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - exercised by the absent-Pillow test via monkeypatch
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]


#: Warm neutral — mid-tone on purpose so the silhouette reads on BOTH a light and a dark
#: notification background without the image carrying its own backdrop.
FILL_RGB: tuple[int, int, int] = (181, 173, 161)

#: The same family, darker. The trail is context, not the subject.
TRAIL_RGB: tuple[int, int, int] = (107, 100, 89)

#: The one saturated thing in the frame — this is the answer to "where is it".
DOT_RGB: tuple[int, int, int] = (232, 115, 74)

#: Ring around the dot so it separates from the fill at any size.
DOT_RING_RGB: tuple[int, int, int] = (255, 255, 255)

#: The room-name pill. Black on white is the one pairing that survives BOTH a light and a
#: dark notification background without knowing which it landed on — the image carries its
#: own contrast instead of assuming a backdrop.
PILL_BG_RGB: tuple[int, int, int] = (0, 0, 0)
PILL_TEXT_RGB: tuple[int, int, int] = (255, 255, 255)

_TRANSPARENT = (0, 0, 0, 0)


def _load_font(size: int):
    """A usable font, or None. Never raises — the pill is optional, the render is not."""
    try:
        from PIL import ImageFont
    except Exception:  # pragma: no cover - Pillow absent is handled earlier
        return None
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        try:
            return ImageFont.load_default()
        except Exception:  # pragma: no cover
            return None
    except Exception:  # pragma: no cover
        return None


def _draw_label_pill(img, draw, text: str, margin: int = 6) -> None:
    """Draw a black pill with white text at the top-left. Best-effort; never raises.

    Drawn at FINAL resolution, after upscaling, so the text stays crisp against a
    deliberately blocky room silhouette.
    """
    font = _load_font(max(11, img.height // 22))
    if font is None:
        return
    try:
        x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    except Exception:  # pragma: no cover - very old Pillow
        return
    tw, th = (x1 - x0), (y1 - y0)
    pad_x, pad_y = max(4, th // 2), max(2, th // 4)
    box = [margin, margin, margin + tw + pad_x * 2, margin + th + pad_y * 2]
    radius = (box[3] - box[1]) // 2
    try:
        draw.rounded_rectangle(box, radius=radius, fill=(*PILL_BG_RGB, 255))
    except Exception:  # pragma: no cover - Pillow < 8.2
        draw.rectangle(box, fill=(*PILL_BG_RGB, 255))
    draw.text(
        (margin + pad_x - x0, margin + pad_y - y0),
        text, font=font, fill=(*PILL_TEXT_RGB, 255),
    )


def room_bbox_from_raster(
    *,
    room_pixels: bytes,
    width: int,
    height: int,
    room_id: int,
    flip_y: bool = False,
) -> tuple[int, int, int, int] | None:
    """Pixel bbox ``(min_x, min_y, max_x, max_y)`` of one room, in the RENDERED frame.

    Returns None when the room has no pixels — ABSENT, not an empty box. A caller must
    treat that as "cannot crop to this room" and fall back to the whole map, never as a
    zero-size crop.

    ``width * height`` scan. The one other caller of an equivalent scan dispatches it via
    executor for exactly this reason; do the same on a job-lifecycle path.
    """
    if not room_pixels or width <= 0 or height <= 0:
        return None
    if len(room_pixels) < width * height:
        return None

    target = room_id & 0xFF
    min_x, min_y, max_x, max_y = width, height, -1, -1

    for row in range(height):
        base = row * width
        # bytes.find is C-level; skip rows that cannot contribute before scanning them.
        chunk = room_pixels[base:base + width]
        if chunk.find(target) == -1:
            continue
        y = (height - 1 - row) if flip_y else row
        col = chunk.find(target)
        while col != -1:
            if col < min_x:
                min_x = col
            if col > max_x:
                max_x = col
            col = chunk.find(target, col + 1)
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y

    if max_x < 0 or max_y < 0:
        return None
    return (min_x, min_y, max_x, max_y)


def _norm_to_px(pt: Any, width: int, height: int) -> tuple[float, float] | None:
    """A normalized 0–1 point to full-image pixels, or None when it is not a real point."""
    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
        return None
    try:
        nx, ny = float(pt[0]), float(pt[1])
    except (TypeError, ValueError):
        return None
    if nx != nx or ny != ny:  # NaN
        return None
    return (nx * width, ny * height)


def render_room_capture(
    *,
    room_pixels: bytes,
    width: int,
    height: int,
    room_id: int,
    anchor: Any = None,
    trail: Iterable[Any] = (),
    label: str | None = None,
    flip_y: bool = False,
    padding_px: int = 10,
    scale: int = 4,
    max_edge_px: int = 1024,
) -> bytes | None:
    """Return PNG bytes for one room, or None when nothing can be drawn.

    None is returned — never a blank image — when Pillow is absent or the room has no
    pixels. Absence must stay distinguishable from "an empty room was rendered".

    ``anchor`` may be None (the robot is docked, or the map source is held/stale): the dot
    is then simply not drawn. It is NOT treated as the origin. Same for any unparseable
    trail point, which is skipped rather than collapsing the line to a corner.

    ``scale`` upsamples with NEAREST, keeping the blocky silhouette crisp rather than
    smearing a 40-pixel room into mush.
    """
    if Image is None or ImageDraw is None:
        return None

    bbox = room_bbox_from_raster(
        room_pixels=room_pixels, width=width, height=height,
        room_id=room_id, flip_y=flip_y,
    )
    if bbox is None:
        return None

    min_x, min_y, max_x, max_y = bbox
    pad = max(0, int(padding_px))
    cx0, cy0 = max(0, min_x - pad), max(0, min_y - pad)
    cx1, cy1 = min(width - 1, max_x + pad), min(height - 1, max_y + pad)
    cw, ch = (cx1 - cx0 + 1), (cy1 - cy0 + 1)
    if cw <= 0 or ch <= 0:
        return None

    # 1) The room silhouette, at RASTER resolution — one byte per pixel, one pixel each.
    img = Image.new("RGBA", (cw, ch), _TRANSPARENT)
    px = img.load()

    target = room_id & 0xFF
    fill = (*FILL_RGB, 255)
    for row in range(height):
        y = (height - 1 - row) if flip_y else row
        if not (cy0 <= y <= cy1):
            continue
        base = row * width
        chunk = room_pixels[base:base + width]
        col = chunk.find(target)
        while col != -1:
            if cx0 <= col <= cx1:
                px[col - cx0, y - cy0] = fill
            col = chunk.find(target, col + 1)

    # 2) Upscale FIRST. NEAREST keeps the silhouette crisp and blocky rather than smearing
    #    a 40-pixel room, and everything drawn after this lands at final resolution.
    factor = max(1, int(scale))
    if max(cw, ch) * factor > max_edge_px:
        factor = max(1, max_edge_px // max(cw, ch))
    if factor > 1:
        img = img.resize((cw * factor, ch * factor), Image.NEAREST)

    # 3) Vector elements, at FINAL resolution — a smooth trail and a round dot over a
    #    blocky room reads as deliberate; upscaling them with the mask would just look
    #    broken, and the label would be illegible.
    draw = ImageDraw.Draw(img)

    def _to_final(p: tuple[float, float]) -> tuple[float, float]:
        return ((p[0] - cx0) * factor + factor / 2.0, (p[1] - cy0) * factor + factor / 2.0)

    pts: list[tuple[float, float]] = []
    for raw in (trail or ()):
        p = _norm_to_px(raw, width, height)
        if p is not None:
            pts.append(_to_final(p))
    if len(pts) >= 2:
        draw.line(pts, fill=(*TRAIL_RGB, 255), width=max(1, factor // 2), joint="curve")

    a = _norm_to_px(anchor, width, height)
    if a is not None:
        ax, ay = _to_final(a)
        r = max(2.5, factor * 1.2)
        ring = max(1.0, r * 0.35)
        draw.ellipse([ax - r - ring, ay - r - ring, ax + r + ring, ay + r + ring],
                     fill=(*DOT_RING_RGB, 255))
        draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(*DOT_RGB, 255))

    if label:
        _draw_label_pill(img, draw, str(label))

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
