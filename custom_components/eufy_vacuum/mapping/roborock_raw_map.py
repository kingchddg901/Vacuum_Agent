"""Roborock v1 raw-map segment decoder.

``python-roborock`` + ``vacuum-map-parser-roborock`` parse the raw map blob into a
per-pixel room-id raster to COLOUR the rooms, then DISCARD it — the public
``MapData`` keeps only per-room bounding boxes + a rendered RGB image. But the raw
blob survives on the v1 ``MapContent.raw_api_response`` (cached in HA memory, next
to the ``map_data`` our roborock introspection already reaches). This re-decodes
JUST the segment layer from those bytes into a per-pixel room-id raster equivalent
to Eufy's ``room_pixels``, so Roborock can ride the SAME raster render pipeline
(per-room colour / floor textures / pixel-exact hit-test) instead of overlapping
bounding boxes.

Only the v1 (S6 / Q-series-class) format is handled here; b01 (newer Qrevo-class)
uses a different parser and is out of scope. The structure is mirrored from
``vacuum-map-parser-roborock`` (all LITTLE-endian) so a firmware format change is a
one-file fix:

- map header length = ``int16 @ 0x02``; the first block starts at that offset.
- each block: ``header_len = int16 @ block+0x02``; ``type = int16 @ header[0x00]``;
  ``data_len = int32 @ header[0x04]``; the block DATA starts at ``block+header_len``;
  advance to the next block by ``data_len + int8 @ header[0x02]`` (== header_len for
  the <256-byte headers roborock uses — reproduced verbatim from the reference).
- IMAGE block (``type == 2``): ``top/left/height/width = int32 @ header[header_len-16..-4]``;
  the data is ``width*height`` bytes, one per pixel, row-major, and row 0 is the
  image BOTTOM (the reference flips Y on render), so ``flip_y`` is True.
- pixel byte -> ``(pixel_type = byte & 0x07, room = byte >> 3)``. A pixel is a ROOM
  iff ``(byte & 0x07) == 7`` AND it is not ``0x07`` (MAP_SCAN) or ``0xFF``
  (MAP_INSIDE). ``0xFF`` is the catch-all scanned floor (id 31); ``0x00`` outside,
  ``0x01`` wall, other obstacle bits -> wall variants — all resolve to id 0.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

_BLOCK_TYPE_IMAGE = 2
_MAP_SCAN = 0x07     # transient "being scanned" — not a room
_MAP_INSIDE = 0xFF   # scanned floor, unassigned to a room
CATCH_ALL_RID = 31   # 0xFF >> 3 — the catch-all "inside, no room" floor
MAX_ROOM_RID = 30    # (30 << 3) | 7 == 0xF7; 0xFF (31) is the catch-all, not a room


def _u16(b: bytes, i: int) -> int:
    return b[i] | (b[i + 1] << 8)


def _u32(b: bytes, i: int) -> int:
    return b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24)


def resolve_rid(pixel_type: int) -> int:
    """Resolve a raw pixel byte to a room id: 1..30 room, 31 catch-all inside, 0 background.

    Mirrors ``RoborockImageParser.get_room_at_pixel`` (a pixel is a room only when its
    low 3 bits are 7 and it isn't the SCAN/INSIDE sentinel) plus the INSIDE catch-all.
    """
    if pixel_type == _MAP_INSIDE:
        return CATCH_ALL_RID
    if pixel_type != _MAP_SCAN and (pixel_type & 0x07) == 7:
        return pixel_type >> 3
    return 0


# 256-entry lookup so the per-pixel resolve is a single C-level bytes.translate() over
# the (up to ~1M-pixel) image rather than a Python loop.
_RID_LUT = bytes(resolve_rid(v) for v in range(256))


def decode_roborock_v1_segments(raw: Any) -> dict[str, Any] | None:
    """Decode the IMAGE block of a raw Roborock v1 map blob into a room-id raster.

    Returns ``{width, height, top, left, rid_shift, catch_all_rid, flip_y, room_ids,
    room_pixels}`` where ``room_pixels`` is one resolved room-id byte per pixel
    (``rid_shift == 0`` — already resolved), or ``None`` when there is no IMAGE block
    or the blob is malformed/truncated. Pure; never raises.
    """
    try:
        raw = bytes(raw)
    except (TypeError, ValueError):
        return None
    n = len(raw)
    if n < 4:
        return None
    try:
        pos = _u16(raw, 0x02)  # map header length -> first block offset
        image: tuple[int, int, int, int, int, int] | None = None
        while pos + 8 <= n:
            header_len = _u16(raw, pos + 0x02)
            if header_len < 8 or pos + header_len > n:
                break
            block_type = _u16(raw, pos)
            data_len = _u32(raw, pos + 0x04)
            data_start = pos + header_len
            if block_type == _BLOCK_TYPE_IMAGE and header_len >= 16:
                top = _u32(raw, pos + header_len - 16)
                left = _u32(raw, pos + header_len - 12)
                height = _u32(raw, pos + header_len - 8)
                width = _u32(raw, pos + header_len - 4)
                image = (top, left, height, width, data_start, data_len)
            # Advance exactly as the reference does: data_len + the int8 at header[0x02].
            step = data_len + raw[pos + 0x02]
            if step <= 0:
                break  # malformed: no forward progress -> bail rather than spin
            pos += step
        if image is None:
            return None
        top, left, height, width, data_start, data_len = image
        pixel_count = width * height
        if width <= 0 or height <= 0 or pixel_count > data_len:
            return None
        if data_start + pixel_count > n:
            return None
        room_pixels = raw[data_start:data_start + pixel_count].translate(_RID_LUT)
        room_ids = sorted(
            b for b in set(room_pixels) if 1 <= b <= MAX_ROOM_RID
        )
        return {
            "width": width,
            "height": height,
            "top": top,
            "left": left,
            "rid_shift": 0,          # room_pixels already holds resolved ids
            "catch_all_rid": CATCH_ALL_RID,
            "flip_y": True,          # raw row 0 is the image bottom
            "room_ids": room_ids,
            "room_pixels": room_pixels,
        }
    except (IndexError, ValueError):
        return None


def roborock_render_data(
    decoded: dict[str, Any] | None,
    room_names: Any = None,
    *,
    version: str | None = None,
) -> dict[str, Any] | None:
    """Build the card's render-data (the generic ``eufy_room_pixels_v1`` shape) from a
    decoded Roborock raster, so Roborock rides the SAME frontend decode as Eufy.

    The decoded raster already holds resolved room ids, so ``rid_shift`` is 0; the raster
    IS the render canvas (Roborock has no separate room-outline frame), so ``ro_width/height``
    match the canvas and ``ro_dx/dy`` are 0. ``room_names`` maps room id -> display name
    (from the adapter's discovered rooms). Returns None on empty/malformed input.

    NOTE: ``res`` (device-mm per pixel, from roborock's ``map/50`` image scale) is emitted
    for completeness but only matters for the POSE overlay's coord mapping — the room-raster
    render itself needs none of it. Pose registration (res/origin/flip against the live
    robot position) is the device-calibration step; verify on a real vacuum.
    """
    if not decoded:
        return None
    rp = decoded.get("room_pixels")
    width = decoded.get("width")
    height = decoded.get("height")
    if not rp or not width or not height:
        return None
    names = room_names if isinstance(room_names, dict) else {}
    raw = bytes(rp)
    if version is None:
        version = hashlib.sha1(raw).hexdigest()[:12]
    return {
        "present": True,
        "format": "eufy_room_pixels_v1",     # the card's brand-agnostic raster decode
        "width": int(width),
        "height": int(height),
        "ro_width": int(width),              # the raster IS the canvas (no outline frame)
        "ro_height": int(height),
        "ro_dx": 0,
        "ro_dy": 0,
        "res": int(decoded.get("res", 50)),  # roborock map/50 -> 50 mm/px; pose-only, calibrate on device
        "flip_y": bool(decoded.get("flip_y", True)),
        "rid_shift": int(decoded.get("rid_shift", 0)),
        "catch_all_rid": int(decoded.get("catch_all_rid", CATCH_ALL_RID)),
        "room_pixels": base64.b64encode(raw).decode("ascii"),
        "room_names": {str(k): str(v) for k, v in names.items()},
        "version": version,
    }
