"""Read a provider's OWN map segmentation into normalized, VA-owned room data.

This is the brand-agnostic core of the `map_state_source` seam (see
docs/dev/map-state-source.md). It turns the device's authoritative segmentation —
not bounds learned from drifting robot samples — into normalized room data the card
and consumers use, so room select-regions / current-room / anchors are AUTO-DERIVED
rather than hand-composed.

Wave 1 scope: per-room **bbox + name** + dock/robot anchors, normalized to 0–1 of the
RENDERED image (top-left origin, Y-flip applied) — the same space the card draws
zones/labels in. Exact polygons (contour-trace) are Wave 2.

Wave 3a adds the rest of the device's authoritative map layers — per-room **area (m²)**,
**current room**, the robot **path/trail**, and (Roborock) **no-go / no-mop / virtual-wall /
zone / obstacle** layers — all in the SAME normalized space, so the card can OVERLAY them on
the device-rendered backdrop (we never render the map ourselves).

This module is intentionally **HA-free and pure**: the runtime locators (loading the
provider's `.storage` for the Eufy storage backend, or finding the coordinator's parsed
map in `hass.data` for the Roborock memory backend) live in the caller and inject plain
data here, so the extraction/normalization is unit-testable without Home Assistant.
"""
from __future__ import annotations

import base64
from typing import Any

# Room IDs at-or-above this are catch-all/background (e.g. the full-grid sentinel
# observed as id 32 on Eufy), never a real room.
_CATCH_ALL_RID = 32

# Wave 3b — toggleable overlay layers + their default visibility. The user's chosen
# defaults (2026-06-19): Navigation (robot/dock/current_room) + room labels/area ON;
# hazards (no_go/no_mop/walls/zones) + activity (path/obstacles) OFF. The room
# tap-regions themselves are always shown (the core function) and are not toggleable.
OVERLAY_VISIBILITY_DEFAULTS: dict[str, bool] = {
    "room_labels": True,
    "room_area": True,
    "current_room": True,
    "robot": True,
    "dock": True,
    "no_go": False,
    "no_mop": False,
    "walls": False,
    "zones": False,
    "path": False,
    "obstacles": False,
}


def resolve_overlay_visibility(stored: Any) -> dict[str, bool]:
    """Merge a stored per-layout visibility dict over the defaults (sanitized booleans).

    Unknown keys in `stored` are ignored; missing keys fall back to the default, so a
    partial stored dict (or None) always yields a complete, valid visibility map.
    """
    out = dict(OVERLAY_VISIBILITY_DEFAULTS)
    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in out:
                out[key] = bool(value)
    return out


def _decimate_step(n: int, max_points: int) -> int:
    """Ceil-division stride so a sampled sequence is HARD-capped at ~max_points.

    ``n // max_points`` only thins above 2x the cap (a 180-pt path stayed 180); the
    ceil stride caps it for real, which matters for the recorder-bound sensor attrs.
    """
    if max_points <= 0:
        return 1
    return max(1, -(-n // max_points))


def _clamp01(v: float) -> float:
    return min(max(v, 0.0), 1.0)


def _as_int(value: Any, default: int = 0) -> int:
    """Coerce to int, degrading to ``default`` on missing/non-numeric input.

    The reader sits behind a never-crash / degrade-to-unavailable contract
    (docs/dev/map-state-source.md) — provider-internal fields can drift type across a
    schema change (esp. the pending #136 fork merge), so we coerce rather than raise.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _numeric_pair(p: Any) -> bool:
    """True iff ``p`` is a 2-element list/tuple of numbers (not bools)."""
    return (
        isinstance(p, (list, tuple)) and len(p) == 2
        and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in p)
    )


def normalize_rendered(px: float, py: float, width: int, height: int) -> list[float]:
    """Map a MAIN-grid pixel to normalized 0–1 of the rendered image.

    The render flips top-bottom, so image-Y = (height-1-py)/height. Result is
    [nx, ny] with a top-left origin, matching the card's overlay space.
    """
    if width <= 0 or height <= 0:
        return [0.0, 0.0]
    nx = _clamp01(px / width)
    ny = _clamp01((height - 1 - py) / height)
    return [round(nx, 5), round(ny, 5)]


def _outline_geometry(map_data: dict[str, Any]):
    """Shared Eufy room_pixels geometry: (ro_w, ro_h, ro_dx, ro_dy, res, width, height).

    The room_pixels raster is in the room_outline frame; (ro_dx, ro_dy) is the integer
    offset to the MAIN grid (= round((origin - room_outline_origin)/res)). Returns None
    when the required dims are missing. Single source for both the per-room extraction
    and the robot-pixel current-room lookup, so the inverse transform can't drift.
    """
    width = _as_int(map_data.get("width"))
    height = _as_int(map_data.get("height"))
    res = _as_int(map_data.get("resolution"), 5) or 5
    ro_w = _as_int(map_data.get("room_outline_width"))
    ro_h = _as_int(map_data.get("room_outline_height"))
    if not (width and height and ro_w and ro_h):
        return None
    ox = _as_int(map_data.get("origin_x"))
    oy = _as_int(map_data.get("origin_y"))
    ro_dx = round((ox - _as_int(map_data.get("room_outline_origin_x"), ox)) / res)
    ro_dy = round((oy - _as_int(map_data.get("room_outline_origin_y"), oy)) / res)
    return ro_w, ro_h, ro_dx, ro_dy, res, width, height


def _area_m2(pixel_count: int, res_cm: int) -> float:
    """Floor area of a room_pixels region (each cell is res_cm × res_cm)."""
    return round(pixel_count * (res_cm / 100.0) ** 2, 1)


def rooms_from_room_pixels(map_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Eufy storage backend: per-room bbox + name + area from the `room_pixels` raster.

    `map_data` is the decoded map block (origin/res/dims, room_outline_*, room_names,
    room_pixels b64). Returns rooms with a normalized bbox (rendered-image space) +
    `area_m2`. Empty list when no segmentation is present (caller treats as not-available).
    """
    rp_b64 = map_data.get("room_pixels")
    if not rp_b64:
        return []
    geom = _outline_geometry(map_data)
    if geom is None:
        return []
    ro_w, ro_h, ro_dx, ro_dy, res, width, height = geom
    names = map_data.get("room_names")
    if not isinstance(names, dict):
        names = {}
    try:
        # Untrusted provider-internal field — degrade to "not available" rather than
        # crash on a truncated/re-encoded raster (binascii.Error subclasses ValueError).
        room_px = base64.b64decode(rp_b64)
    except (ValueError, TypeError):
        return []

    # rid -> [min_px, max_px, min_py, max_py, count]  in MAIN-grid pixels
    acc: dict[int, list[int]] = {}
    for ry in range(ro_h):
        row = ry * ro_w
        for rx in range(ro_w):
            idx = row + rx
            if idx >= len(room_px):
                break
            rid = room_px[idx] >> 2
            if not (0 < rid < _CATCH_ALL_RID):
                continue
            px, py = rx + ro_dx, ry + ro_dy
            a = acc.get(rid)
            if a is None:
                acc[rid] = [px, px, py, py, 1]
            else:
                if px < a[0]: a[0] = px
                if px > a[1]: a[1] = px
                if py < a[2]: a[2] = py
                if py > a[3]: a[3] = py
                a[4] += 1

    rooms: list[dict[str, Any]] = []
    for rid in sorted(acc):
        min_px, max_px, min_py, max_py, cnt = acc[rid]
        c0 = normalize_rendered(min_px, min_py, width, height)
        c1 = normalize_rendered(max_px, max_py, width, height)
        bbox = [min(c0[0], c1[0]), min(c0[1], c1[1]), max(c0[0], c1[0]), max(c0[1], c1[1])]
        rooms.append({
            "number": rid,
            "name": str(names.get(str(rid)) or names.get(rid) or f"Room {rid}"),
            "bbox": bbox,           # [x0,y0,x1,y1] normalized, top-left origin
            "pixel_count": cnt,
            "area_m2": _area_m2(cnt, res),
        })
    return rooms


def current_room_from_storage(data: dict[str, Any]) -> int | None:
    """Eufy: the room id the robot is currently in, by exact pixel lookup.

    Converts the latest robot pixel (`robot_trail[-1]`, MAIN-grid space) back into the
    room_outline raster and reads the room id there — pixel-exact membership (no bbox /
    margin), the Roborock-grade native room detection the segmentation unlocks. None when
    unavailable / off-map / a catch-all cell.
    """
    md = data.get("map_data") or {}
    rp_b64 = md.get("room_pixels")
    trail = data.get("robot_trail") or []
    if not rp_b64 or not trail or not _numeric_pair(trail[-1]):
        return None
    geom = _outline_geometry(md)
    if geom is None:
        return None
    ro_w, ro_h, ro_dx, ro_dy, _res, _w, _h = geom
    rx = int(trail[-1][0]) - ro_dx
    ry = int(trail[-1][1]) - ro_dy
    if not (0 <= rx < ro_w and 0 <= ry < ro_h):
        return None
    try:
        raster = base64.b64decode(rp_b64)
    except (ValueError, TypeError):
        return None
    idx = ry * ro_w + rx
    if idx >= len(raster):
        return None
    rid = raster[idx] >> 2
    return rid if 0 < rid < _CATCH_ALL_RID else None


def path_from_storage(data: dict[str, Any], *, max_points: int = 160) -> list[list[float]]:
    """Eufy: the robot trail as a normalized polyline (decimated to `max_points`).

    `robot_trail` is MAIN-grid pixels; we normalize each kept point to the rendered
    image. Decimated so a long trail stays a small overlay (and stays out of the
    recorder-bound sensor attributes). [] when absent.
    """
    md = data.get("map_data") or {}
    width = _as_int(md.get("width"))
    height = _as_int(md.get("height"))
    trail = data.get("robot_trail") or []
    if not (width and height) or not isinstance(trail, (list, tuple)) or not trail:
        return []
    step = _decimate_step(len(trail), max_points)
    out: list[list[float]] = []
    for i in range(0, len(trail), step):
        pt = trail[i]
        if _numeric_pair(pt):
            out.append(normalize_rendered(pt[0], pt[1], width, height))
    # Always keep the final (latest) point even if decimation skipped it.
    last = trail[-1]
    if _numeric_pair(last):
        tail = normalize_rendered(last[0], last[1], width, height)
        if not out or out[-1] != tail:
            out.append(tail)
    return out


def overlays_from_storage(data: dict[str, Any]) -> dict[str, Any]:
    """Eufy: the non-room overlay layers (current room, path), normalized.

    Hazard layers (`forbidden_zones`/`ban_mop_zones`/`virtual_walls`) exist in the
    schema but were EMPTY on the live device, so their populated coordinate frame is
    unverified — deferred (omitted) until a live map carries them, rather than shipping
    a guessed transform. Eufy has no robot heading and no saved-zone/obstacle concept.
    """
    out: dict[str, Any] = {}
    # Rendered-image dims so the card can letterbox-correct (object-fit:contain) when
    # placing the normalized overlays over the live backdrop. Only the ASPECT matters.
    md = data.get("map_data") or {}
    w = _as_int(md.get("width"))
    h = _as_int(md.get("height"))
    if w and h:
        out["image_size"] = [w, h]
    current = current_room_from_storage(data)
    if current is not None:
        out["current_room"] = current
    path = path_from_storage(data)
    if path:
        out["path"] = path
    return out


def anchors_from_storage(data: dict[str, Any]) -> dict[str, list[float]]:
    """Normalized dock + robot anchors from the Eufy storage (`dock_pixel`/`robot_trail`)."""
    md = data.get("map_data") or {}
    width = _as_int(md.get("width"))
    height = _as_int(md.get("height"))
    out: dict[str, list[float]] = {}
    if not (width and height):
        return out
    dock = data.get("dock_pixel")
    if _numeric_pair(dock):
        out["dock_anchor"] = normalize_rendered(dock[0], dock[1], width, height)
    trail = data.get("robot_trail") or []
    if trail and _numeric_pair(trail[-1]):
        out["robot_anchor"] = normalize_rendered(trail[-1][0], trail[-1][1], width, height)
    return out


def rooms_from_parsed_map(
    rooms: Any,
    image_width: int,
    image_height: int,
    *,
    flip_y: bool = True,
) -> list[dict[str, Any]]:
    """Roborock memory backend: per-room bbox + name from the parser's `MapData.rooms`.

    `rooms` is the parser's room collection — each entry exposes `x0,y0,x1,y1` (bbox),
    `number`, `name` (vacuum-map-parser `Room`). Coords are in image pixels; we
    normalize by the image dims. NOTE (Wave 1): the parser only gives bboxes, so
    L-shaped rooms are approximate until Wave 2 reconstructs exact polygons. The exact
    in-memory access path AND the ``flip_y`` orientation are UNVERIFIED against a live
    Roborock map — the Wave 1 introspector (not yet built) confirms both; until then
    ``flip_y`` is a hypothesis. This stays pure.
    """
    if not image_width or not image_height:
        return []
    items = rooms.values() if hasattr(rooms, "values") else rooms
    out: list[dict[str, Any]] = []
    for r in items:
        x0 = getattr(r, "x0", None); y0 = getattr(r, "y0", None)
        x1 = getattr(r, "x1", None); y1 = getattr(r, "y1", None)
        if None in (x0, y0, x1, y1):
            continue
        n0 = normalize_rendered(min(x0, x1), min(y0, y1), image_width, image_height) if flip_y \
            else [_clamp01(min(x0, x1) / image_width), _clamp01(min(y0, y1) / image_height)]
        n1 = normalize_rendered(max(x0, x1), max(y0, y1), image_width, image_height) if flip_y \
            else [_clamp01(max(x0, x1) / image_width), _clamp01(max(y0, y1) / image_height)]
        out.append({
            "number": getattr(r, "number", None),
            "name": str(getattr(r, "name", None) or f"Room {getattr(r, 'number', '?')}"),
            "bbox": [min(n0[0], n1[0]), min(n0[1], n1[1]), max(n0[0], n1[0]), max(n0[1], n1[1])],
            "approximate": True,   # bbox-only from the parser; exact outline is Wave 2
        })
    return out


def build_map_source_result(
    *,
    present: bool,
    backend: str,
    rooms: list[dict[str, Any]] | None = None,
    anchors: dict[str, list[float]] | None = None,
    extra: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Assemble the normalized, VA-owned snapshot payload (or an absent marker).

    `present` is the adapter's presence gate (e.g. Eufy: camera artifact + map_data;
    Roborock: coordinator + parsed map). When false the payload carries `present:false`
    and no rooms, so consumers degrade/hide rather than error. `anchors` carries
    dock/robot anchor points; `extra` carries the Wave-3a overlay layers (current_room,
    path, no_go, walls, …) — both merged in only when present.
    """
    if not present or not rooms:
        return {"present": False, "backend": backend, "reason": reason or "no_segmentation"}
    payload: dict[str, Any] = {"present": True, "backend": backend, "rooms": rooms}
    if anchors:
        payload.update(anchors)
    if extra:
        payload.update(extra)
    return payload
