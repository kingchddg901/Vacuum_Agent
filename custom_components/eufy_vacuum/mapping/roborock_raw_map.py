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


def raster_room_bboxes(decoded: dict[str, Any] | None) -> dict[int, list[float]]:
    """Per-room NORMALIZED bbox ``{rid: [min_x, min_y, max_x, max_y]}`` (0..1 of the raster)
    from a decoded raster — the min/max column/row of each room's pixels. The raster
    counterpart to the parser's own per-room bboxes; comparing the two validates the decode.
    """
    if not decoded:
        return {}
    rp = decoded.get("room_pixels")
    width = decoded.get("width")
    height = decoded.get("height")
    if not rp or not width or not height:
        return {}
    w, h = int(width), int(height)
    acc: dict[int, list[int]] = {}  # rid -> [min_x, min_y, max_x, max_y] in pixels
    for i, rid in enumerate(rp):
        if not (1 <= rid <= MAX_ROOM_RID):
            continue
        x, y = i % w, i // w
        b = acc.get(rid)
        if b is None:
            acc[rid] = [x, y, x, y]
        else:
            if x < b[0]:
                b[0] = x
            if y < b[1]:
                b[1] = y
            if x > b[2]:
                b[2] = x
            if y > b[3]:
                b[3] = y
    return {
        rid: [b[0] / w, b[1] / h, (b[2] + 1) / w, (b[3] + 1) / h]
        for rid, b in acc.items()
    }


def _bbox_iou(a: list[float], b: list[float]) -> float:
    """Intersection-over-union of two [min_x, min_y, max_x, max_y] boxes. 0 on no overlap."""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def geometry_drift(parser_rooms: Any, decoded: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay the PARSER's per-room bboxes with the RASTER-derived bboxes to check the decode
    for drift — both come from the SAME segment layer, so aligned boxes validate the decode
    (rid extraction + orientation + frame) and a systematic delta IS the calibration signal
    (a constant offset = the parser's trim; an inverted axis = a flip bug).

    ``parser_rooms`` = the ``rooms_from_mapdata`` output (list of ``{number, bbox}``, bbox
    normalized). Returns the room-id set comparison + per-room IoU / centre delta + a soft
    ``aligned`` verdict (all common rooms overlap well and centres are close). Pure; a
    systematic offset lowers IoU without meaning the decode is wrong — read the deltas.
    """
    parser: dict[int, list[float]] = {}
    for r in parser_rooms or []:
        num = r.get("number") if isinstance(r, dict) else None
        bbox = r.get("bbox") if isinstance(r, dict) else None
        if num is not None and isinstance(bbox, list) and len(bbox) == 4:
            try:
                parser[int(num)] = [float(v) for v in bbox]
            except (TypeError, ValueError):
                continue
    raster = raster_room_bboxes(decoded)
    common = sorted(set(parser) & set(raster))
    per_room: dict[int, dict[str, Any]] = {}
    max_center = 0.0
    min_iou = 1.0
    for rid in common:
        pb, rb = parser[rid], raster[rid]
        pcx, pcy = (pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2
        rcx, rcy = (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2
        dc = ((pcx - rcx) ** 2 + (pcy - rcy) ** 2) ** 0.5
        iou = _bbox_iou(pb, rb)
        max_center = max(max_center, dc)
        min_iou = min(min_iou, iou)
        per_room[rid] = {
            "parser": [round(v, 4) for v in pb],
            "raster": [round(v, 4) for v in rb],
            "center_delta": round(dc, 4),
            "iou": round(iou, 3),
        }
    return {
        "room_ids_parser": sorted(parser),
        "room_ids_raster": sorted(raster),
        "common": common,
        "only_parser": sorted(set(parser) - set(raster)),
        "only_raster": sorted(set(raster) - set(parser)),
        "max_center_delta": round(max_center, 4),
        "min_iou": round(min_iou, 3) if common else 0.0,
        "aligned": bool(common)
        and not (set(parser) ^ set(raster))
        and max_center < 0.1
        and min_iou > 0.5,
        "per_room": per_room,
    }
