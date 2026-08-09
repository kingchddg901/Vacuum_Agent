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

COORDINATE CONTRACT — the one place bugs will live, so it is stated rather than implied.
A first draft of this module assumed the raster IS the canvas and that a raster byte IS a
room id. Both are false on Eufy, and the result renders a perfectly plausible image of the
wrong region — the failure most likely to survive a glance. The authority is
``map_source.current_room_for_pixel``; these parameters mirror it exactly.

Three distinct spaces:

1. **Raster space** — ``room_pixels`` is ``ro_width * ro_height`` bytes, row-major. A cell
   holds ``room_id << rid_shift`` (Eufy ``rid_shift=2``; Roborock's decoder resolves ids
   itself and reports ``rid_shift=0``). So membership is
   ``(byte >> rid_shift) == room_id`` — never a raw byte compare.
2. **Main-grid space** — the raster is OFFSET into it: ``main = raster + (ro_dx, ro_dy)``.
   For Roborock these are 0 and the two spaces coincide; for Eufy they do not.
3. **Rendered space** — ``canvas_width x canvas_height``, and what ``flip_y`` describes:
   the render mirrors top-bottom. ``anchor`` and ``trail`` arrive already normalized 0–1
   **against this space**, because they come from ``normalize_rendered``.

So a raster cell reaches the picture as
``main = raster + offset`` then ``rendered = flip(main)``, while the points are already
there and must never be flipped or offset. They are also NOT device coordinates: never
pass them through ``vacuum_to_normalized``, which serves hazard layers stored in raw
vacuum coords.
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


def room_cells(
    *,
    room_pixels: bytes,
    ro_width: int,
    ro_height: int,
    room_id: int,
    rid_shift: int = 0,
) -> list[tuple[int, int]]:
    """Raster cells belonging to ``room_id``, as ``(rx, ry)`` in RASTER space.

    Membership is ``(byte >> rid_shift) == room_id``. Eufy packs the id (shift 2);
    Roborock's decoder resolves ids itself and reports shift 0. Comparing raw bytes works
    on one brand and silently matches nothing on the other.

    ``ro_width * ro_height`` scan. The equivalent scan elsewhere in this package is
    dispatched via executor for exactly that reason — do the same on a lifecycle path.
    """
    if not room_pixels or ro_width <= 0 or ro_height <= 0:
        return []
    if len(room_pixels) < ro_width * ro_height:
        return []
    if room_id <= 0:
        return []

    shift = max(0, int(rid_shift))
    out: list[tuple[int, int]] = []

    if shift == 0:
        # Fast path: the id IS the byte, so bytes.find scans at C level.
        target = room_id & 0xFF
        for ry in range(ro_height):
            base = ry * ro_width
            chunk = room_pixels[base:base + ro_width]
            rx = chunk.find(target)
            while rx != -1:
                out.append((rx, ry))
                rx = chunk.find(target, rx + 1)
        return out

    for ry in range(ro_height):
        base = ry * ro_width
        chunk = room_pixels[base:base + ro_width]
        for rx, byte in enumerate(chunk):
            if (byte >> shift) == room_id:
                out.append((rx, ry))
    return out


def _to_rendered(
    rx: int, ry: int, *, ro_dx: int, ro_dy: int, canvas_height: int, flip_y: bool
) -> tuple[int, int]:
    """Raster cell → rendered-space pixel: offset into the main grid, then flip."""
    px, py = rx + ro_dx, ry + ro_dy
    return (px, (canvas_height - 1 - py) if flip_y else py)


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
    ro_width: int,
    ro_height: int,
    room_id: int,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    ro_dx: int = 0,
    ro_dy: int = 0,
    rid_shift: int = 0,
    anchor: Any = None,
    trail: Iterable[Any] = (),
    label: str | None = None,
    flip_y: bool = False,
    padding_px: int = 10,
    scale: int = 4,
    max_edge_px: int = 1024,
) -> bytes | None:
    """Return PNG bytes for one room, or None when nothing can be drawn.

    Parameters mirror the adapter's render-data block, so a caller passes it through
    rather than re-deriving geometry (see the module docstring's three spaces). Roborock's
    raster IS its canvas, so ``ro_dx/ro_dy`` default to 0 and ``canvas_*`` fall back to
    ``ro_*``; Eufy supplies all of them plus ``rid_shift=2``.

    None is returned — never a blank image — when Pillow is absent or the room has no
    cells. Absence must stay distinguishable from "an empty room was rendered".

    ``anchor`` may be None (the robot is docked, or the map source is held/stale): the dot
    is then simply not drawn. It is NOT treated as the origin. Same for any unparseable
    trail point, which is skipped rather than collapsing the line to a corner.

    ``scale`` upsamples with NEAREST, keeping the blocky silhouette crisp rather than
    smearing a 40-pixel room into mush.
    """
    if Image is None or ImageDraw is None:
        return None

    cvw = int(canvas_width or ro_width)
    cvh = int(canvas_height or ro_height)
    if cvw <= 0 or cvh <= 0:
        return None

    cells = room_cells(
        room_pixels=room_pixels, ro_width=ro_width, ro_height=ro_height,
        room_id=room_id, rid_shift=rid_shift,
    )
    if not cells:
        return None

    rendered = [
        _to_rendered(rx, ry, ro_dx=ro_dx, ro_dy=ro_dy, canvas_height=cvh, flip_y=flip_y)
        for rx, ry in cells
    ]
    xs = [p[0] for p in rendered]
    ys = [p[1] for p in rendered]

    pad = max(0, int(padding_px))
    cx0, cy0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
    cx1, cy1 = min(cvw - 1, max(xs) + pad), min(cvh - 1, max(ys) + pad)
    cw, ch = (cx1 - cx0 + 1), (cy1 - cy0 + 1)
    if cw <= 0 or ch <= 0:
        return None

    # 1) The room silhouette, one raster cell per pixel, in RENDERED space.
    img = Image.new("RGBA", (cw, ch), _TRANSPARENT)
    px = img.load()
    fill = (*FILL_RGB, 255)
    for x, y in rendered:
        if cx0 <= x <= cx1 and cy0 <= y <= cy1:
            px[x - cx0, y - cy0] = fill

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

    # anchor/trail are ALREADY in rendered space — normalized against the canvas by
    # normalize_rendered. They are never offset by (ro_dx, ro_dy) and never flipped;
    # doing either here is the bug this module's docstring exists to prevent.
    pts: list[tuple[float, float]] = []
    for raw in (trail or ()):
        p = _norm_to_px(raw, cvw, cvh)
        if p is not None:
            pts.append(_to_final(p))
    if len(pts) >= 2:
        draw.line(pts, fill=(*TRAIL_RGB, 255), width=max(1, factor // 2), joint="curve")

    a = _norm_to_px(anchor, cvw, cvh)
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
