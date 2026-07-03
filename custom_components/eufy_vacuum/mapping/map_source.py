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
import hashlib
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
    # User-drawn masks that hide map noise (a porch off a room). ON by default = the masking
    # is active; toggling off reveals what's under them without deleting them.
    "hidden_regions": True,
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


def _furnished_art_url(map_bucket: Any, variant: Any) -> str | None:
    """Resolve a furnished-art image variant to its browser_url, or None.

    Tolerates a missing image_variants store / unknown variant / malformed entry —
    this is a never-raise resolver on the on-loop snapshot path."""
    if not variant:
        return None
    variants = map_bucket.get("image_variants") if isinstance(map_bucket, dict) else None
    if not isinstance(variants, dict):
        return None
    entry = variants.get(variant)
    if not isinstance(entry, dict):
        return None
    url = entry.get("browser_url")
    return url if isinstance(url, str) and url else None


def resolve_furnished_render(map_bucket: Any) -> dict | None:
    """PURE: project the ACTIVE custom layout's furnished-art data into the resolved
    shape the card's furnished render consumes (Wave 0).

    Returns None when the map isn't in custom mode, has no active custom layout, or the
    active layout carries no furnished data (no whole-home art AND no per-room furnished
    field). Otherwise returns the layout-level render_mode + the whole-home art (its
    image variant resolved to a browser_url) + per-room entries for any room that has at
    least one furnished field (art_variant / art_placement_transform / viewport /
    render_mode). Transforms/viewports are stored resolution-independent (pct floats) and
    passed through untouched. Never raises; tolerates every missing/malformed key.

    Read locally (no import from mapping_services) to keep this a pure, cycle-free fn:
    the active layout is map_bucket['custom_layouts'][map_bucket['active_custom_layout_id']],
    exactly as ``_active_custom_layout`` resolves it."""
    if not isinstance(map_bucket, dict):
        return None
    if (map_bucket.get("segmentation_mode") or "cv") != "custom":
        return None
    layouts = map_bucket.get("custom_layouts")
    layout_id = map_bucket.get("active_custom_layout_id")
    layout = layouts.get(layout_id) if isinstance(layouts, dict) and layout_id else None
    if not isinstance(layout, dict):
        return None

    home_art_raw = layout.get("home_art") if isinstance(layout.get("home_art"), dict) else None
    rooms_raw = layout.get("rooms") if isinstance(layout.get("rooms"), dict) else {}

    # Per-room: include any room with at least one furnished field present.
    _FURNISHED_FIELDS = ("art_variant", "art_placement_transform", "viewport", "render_mode")
    rooms_out: dict[str, Any] = {}
    for rid, entry in rooms_raw.items():
        if not isinstance(entry, dict):
            continue
        if not any(entry.get(f) is not None for f in _FURNISHED_FIELDS):
            continue
        rooms_out[str(rid)] = {
            "art_url": _furnished_art_url(map_bucket, entry.get("art_variant")),
            "transform": entry.get("art_placement_transform"),
            "viewport": entry.get("viewport"),
            "render_mode": entry.get("render_mode"),
        }

    if home_art_raw is None and not rooms_out:
        return None

    home_out = None
    if home_art_raw is not None:
        home_out = {
            "art_url": _furnished_art_url(map_bucket, home_art_raw.get("art_variant")),
            "transform": home_art_raw.get("art_placement_transform"),
        }

    return {
        "active_layout_id": layout_id,
        "render_mode": layout.get("render_mode") or "live",
        "home_art": home_out,
        "rooms": rooms_out,
    }


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


def vacuum_to_normalized(vx: Any, vy: Any, map_data: dict[str, Any]) -> list[float] | None:
    """Map a DEVICE/VACUUM-frame point (the frame the hazard layers are stored in) to
    normalized 0–1 of the rendered image.

    Hazards (virtual_walls/forbidden_zones/ban_mop_zones) are stored in raw vacuum coords
    (same frame as origin_x/origin_y), NOT pixels — so we first project to the main grid
    (px = (vx - origin_x) / res) and then apply the rendered-image normalization (incl. the
    Y-flip). None on non-numeric input / missing dims. Verified live (the hazard placement is
    eyeballed after deploy — the Y orientation is the one assumption)."""
    if not (
        isinstance(vx, (int, float)) and not isinstance(vx, bool)
        and isinstance(vy, (int, float)) and not isinstance(vy, bool)
    ):
        return None
    width = _as_int(map_data.get("width"))
    height = _as_int(map_data.get("height"))
    res = _as_int(map_data.get("resolution"), 5) or 5
    if not (width and height):
        return None
    px = (vx - _as_int(map_data.get("origin_x"))) / res
    py = (vy - _as_int(map_data.get("origin_y"))) / res
    return normalize_rendered(px, py, width, height)


def _outline_geometry(map_data: dict[str, Any]):
    """Shared Eufy room_pixels geometry: (ro_w, ro_h, ro_dx, ro_dy, res, width, height).

    The room_pixels raster is in the room_outline frame; (ro_dx, ro_dy) is the integer
    offset that maps an outline cell to the MAIN render grid. Both grids use the
    ``origin + index*res`` convention (the fork's own ``_pose_to_pixel``), so outline cell
    ``rx`` lands at main-grid pixel ``rx + (room_outline_origin - origin)/res``.

    The sign is VERIFIED against the fork's rendered map: on a stored X10 map whose outline
    origin sits +105 cells from the map origin, this sign overlays the segmentation floor
    onto the rendered floor at ~93%; the inverted sign gives <1% (rooms slide off-grid).
    Returns None when the required dims are missing. Single source for the per-room
    extraction, the current-room lookup, and saved-zone filing, so the transform can't drift.
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
    ro_dx = round((_as_int(map_data.get("room_outline_origin_x"), ox) - ox) / res)
    ro_dy = round((_as_int(map_data.get("room_outline_origin_y"), oy) - oy) / res)
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
            # Real-world bbox dimensions (metres) = pixel extent × resolution (res is
            # cm/cell) — a to-scale guide for the furnished render. The bbox over-estimates
            # non-rectangular rooms; area_m2 (pixel count) is the true floor area.
            "width_m": round((max_px - min_px + 1) * res / 100.0, 2),
            "height_m": round((max_py - min_py + 1) * res / 100.0, 2),
        })
    return rooms


def zone_membership(map_data: dict[str, Any], geometry: list[list[float]]) -> dict[str, Any]:
    """Filing + size for a saved zone against the Eufy map (Wave 2).

    Returns ``{"area_m2": float | None, "room_number": int | None}``:

    - ``area_m2`` — the zone bbox's real-world FOOTPRINT, computed EXACTLY as the fork
      de-normalizes a zone clean (``coordinator.normalized_rects_to_quads_cm``): the world
      span of the bbox is ``(Δnx*width*res, Δny*height*res)`` cm, so the footprint is
      ``Δnx*Δny*width*height*res^2``. This is what ``clean_saved_zone`` actually dispatches
      (the bbox), so "size shown == size cleaned", and — crucially — it depends ONLY on
      ``width``/``height``/``resolution``, never on the room_outline offset, so it is immune
      to any raster-alignment issue.
    - ``room_number`` — the room holding **>= 90% of the SEGMENTED FLOOR cells** whose
      centre falls inside the zone polygon. Furniture-footprint / background cells are
      excluded from the denominator (the same ``0 < rid < _CATCH_ALL_RID`` filter
      ``rooms_from_room_pixels`` applies), so a big-furniture zone isn't wrongly split.
      ``None`` when no room dominates or the zone covers no floor (Unassigned). FILING
      ONLY — never affects dispatch.

    Pure + defensive: fields are ``None`` when the map/geometry is missing or malformed;
    never raises. Roborock has no per-pixel raster, so ``room_number`` stays ``None`` there
    (and ``area_m2`` needs the Eufy ``width``/``height``/``resolution`` dims).
    """
    from .boundary import point_in_polygon  # local import: no import cycle at module load

    empty = {"area_m2": None, "room_number": None}
    if not (isinstance(geometry, list) and len(geometry) >= 3):
        return empty
    try:
        xs = [float(p[0]) for p in geometry]
        ys = [float(p[1]) for p in geometry]
    except (TypeError, ValueError, IndexError):
        return empty
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)

    # AREA — mirror the fork's de-normalization exactly; OFFSET-INDEPENDENT of the raster.
    width = _as_int(map_data.get("width"))
    height = _as_int(map_data.get("height"))
    res = _as_int(map_data.get("resolution"), 5) or 5
    area_m2: float | None = None
    if width and height:
        dx_cm = (bx1 - bx0) * width * res
        dy_cm = (by1 - by0) * height * res
        area_m2 = round(abs(dx_cm) * abs(dy_cm) / 10_000.0, 1)

    # ROOM FILING — floor-dominance from the room_pixels raster (the offset now overlays the
    # rendered floor; see _outline_geometry). A cheap bbox reject precedes the per-cell
    # ray-cast. Best-effort: any missing/bad piece leaves room_number None (Unassigned)
    # without disturbing area.
    room_number: int | None = None
    geom = _outline_geometry(map_data)
    rp_b64 = map_data.get("room_pixels")
    if geom is not None and rp_b64:
        try:
            room_px = base64.b64decode(rp_b64)
        except (ValueError, TypeError):
            room_px = b""
        if room_px:
            ro_w, ro_h, ro_dx, ro_dy, _res, _w, _h = geom
            floor_total = 0              # in-zone SEGMENTED-floor cells -> filing denominator
            per_rid: dict[int, int] = {}
            for ry in range(ro_h):
                row = ry * ro_w
                for rx in range(ro_w):
                    idx = row + rx
                    if idx >= len(room_px):
                        break
                    nx, ny = normalize_rendered(rx + ro_dx, ry + ro_dy, _w, _h)
                    if nx < bx0 or nx > bx1 or ny < by0 or ny > by1:
                        continue
                    if not point_in_polygon((nx, ny), geometry):
                        continue
                    rid = room_px[idx] >> 2
                    if 0 < rid < _CATCH_ALL_RID:
                        floor_total += 1
                        per_rid[rid] = per_rid.get(rid, 0) + 1
            if floor_total:
                best_rid, best_cnt = max(per_rid.items(), key=lambda kv: kv[1])
                if best_cnt / floor_total >= 0.90:
                    room_number = best_rid
    return {"area_m2": area_m2, "room_number": room_number}


def current_room_for_pixel(map_data: dict[str, Any], px: Any, py: Any) -> int | None:
    """Eufy: the room id at a MAIN-grid pixel, by exact raster lookup.

    Converts (px, py) into the room_outline raster and reads the room id there —
    pixel-exact membership (no bbox / margin). None when off-map / a catch-all cell /
    no raster. Shared by the storage current-room and the live in-memory pose override.
    """
    rp_b64 = map_data.get("room_pixels")
    if not rp_b64:
        return None
    geom = _outline_geometry(map_data)
    if geom is None:
        return None
    ro_w, ro_h, ro_dx, ro_dy, _res, _w, _h = geom
    try:
        rx = int(px) - ro_dx
        ry = int(py) - ro_dy
    except (TypeError, ValueError):
        return None
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


def current_room_from_storage(data: dict[str, Any]) -> int | None:
    """Eufy: the room id the robot is currently in, from `robot_trail[-1]` (lagged
    storage). The live in-memory pose path uses `current_room_for_pixel` directly.
    """
    md = data.get("map_data") or {}
    trail = data.get("robot_trail") or []
    if not trail or not _numeric_pair(trail[-1]):
        return None
    return current_room_for_pixel(md, trail[-1][0], trail[-1][1])


def normalize_trail(
    trail: Any, width: int, height: int, *, max_points: int = 160
) -> list[list[float]]:
    """A MAIN-grid pixel trail → normalized rendered-image polyline (decimated).

    Decimated to ~``max_points`` so a long trail stays a small overlay (and out of the
    recorder-bound sensor attrs); the final (latest) point is always kept. [] on bad
    input. Shared by the lagged `.storage` path and the fresh in-memory live trail so
    both land in the identical rendered space.
    """
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


def path_from_storage(data: dict[str, Any], *, max_points: int = 160) -> list[list[float]]:
    """Eufy: the lagged `.storage` `robot_trail` as a normalized polyline."""
    md = data.get("map_data") or {}
    return normalize_trail(
        data.get("robot_trail") or [],
        _as_int(md.get("width")), _as_int(md.get("height")), max_points=max_points,
    )


def _normalize_vacuum_point(p: Any, map_data: dict[str, Any]) -> list[float] | None:
    """A single [vx, vy] vacuum point -> normalized rendered point (or None)."""
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return vacuum_to_normalized(p[0], p[1], map_data)
    return None


def _as_seq(v: Any) -> list[Any] | tuple[Any, ...]:
    """A hazard layer as an iterable, or [] for anything else. Guards against a truthy NON-list
    scalar (e.g. a fork-schema drift delivering a bare int) which `(v or [])` would NOT catch —
    iterating it would raise on the on-loop snapshot path."""
    return v if isinstance(v, (list, tuple)) else []


def hazards_from_mapdata(map_data: dict[str, Any]) -> dict[str, Any]:
    """Eufy: the device HAZARD layers, vacuum-frame -> normalized rendered space.

    virtual_walls -> `walls` (line segments [[x1,y1],[x2,y2]]); forbidden_zones (no-go) ->
    `no_go` (polygons); ban_mop_zones (vacuum-only/no-mop) -> `no_mop` (polygons) — the SAME
    shapes the card's Wave-3c overlay renderers already draw. Empty/absent layers are omitted.
    These default OFF in the Map Layers panel. Pure; degrades a malformed entry to skipped.
    """
    out: dict[str, Any] = {}

    walls: list[Any] = []
    for seg in _as_seq(map_data.get("virtual_walls")):
        if isinstance(seg, (list, tuple)) and len(seg) == 2:
            p0 = _normalize_vacuum_point(seg[0], map_data)
            p1 = _normalize_vacuum_point(seg[1], map_data)
            if p0 and p1:
                walls.append([p0, p1])
    if walls:
        out["walls"] = walls

    for key, layer in (("no_go", "forbidden_zones"), ("no_mop", "ban_mop_zones")):
        polys: list[Any] = []
        for poly in _as_seq(map_data.get(layer)):
            if isinstance(poly, (list, tuple)) and len(poly) >= 3:
                pts = [pt for pt in (_normalize_vacuum_point(p, map_data) for p in poly) if pt]
                if len(pts) >= 3:
                    polys.append(pts)
        if polys:
            out[key] = polys

    return out


def overlays_from_storage(data: dict[str, Any]) -> dict[str, Any]:
    """Eufy: the non-room overlay layers (current room, path, hazards), normalized.

    Hazards (`virtual_walls`/`forbidden_zones`/`ban_mop_zones`) are stored in vacuum coords;
    a live map carrying them confirmed the frame (2026-06-19), so they're now extracted via
    hazards_from_mapdata. Eufy has no robot heading and no saved-zone/obstacle concept.
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
    out.update(hazards_from_mapdata(md))
    return out


def live_pose_overlay(
    map_data: dict[str, Any],
    robot_pixel: Any,
    dock_pixel: Any,
    heading: Any,
    trail: Any = None,
) -> dict[str, Any]:
    """PURE: normalize the fork's live in-memory PIXEL pose into the moving overlay
    fields (robot/dock anchors + current-room + live path), in the SAME rendered space as
    the static layers (so they override the lagged .storage values without drifting).

    DOCKED SEMANTICS: the fork sets `_robot_pixel` only while the robot is away from the
    dock; when docked it's None and the robot physically sits at `_dock_pixel` (mirrors the
    fork's own render). So a non-pair `robot_pixel` with a valid dock resolves the robot
    anchor TO the dock and flags `robot_docked` — this is what kills the "stale in the
    kitchen" ghost (the lagged .storage `robot_trail[-1]` frozen mid-clean).

    Empty when dims are missing; only the fields that resolve are included. Shared by the
    snapshot override and the get_map_live_pose service.
    """
    out: dict[str, Any] = {}
    width = _as_int(map_data.get("width"))
    height = _as_int(map_data.get("height"))
    if not (width and height):
        return out
    robot_active = _numeric_pair(robot_pixel)
    anchor = robot_pixel if robot_active else (dock_pixel if _numeric_pair(dock_pixel) else None)
    if anchor is not None:
        out["robot_anchor"] = normalize_rendered(anchor[0], anchor[1], width, height)
        cr = current_room_for_pixel(map_data, anchor[0], anchor[1])
        if cr is not None:
            out["current_room"] = cr
        if not robot_active:
            out["robot_docked"] = True
    if _numeric_pair(dock_pixel):
        out["dock_anchor"] = normalize_rendered(dock_pixel[0], dock_pixel[1], width, height)
    if isinstance(heading, (int, float)) and not isinstance(heading, bool):
        out["robot_heading"] = heading
    if trail is not None:
        path = normalize_trail(trail, width, height)
        if path:
            out["path"] = path
    return out


# The moving overlay keys the live pose OWNS when present. robot_anchor / dock_anchor /
# robot_heading / robot_docked are always re-supplied by a present overlay (or are static
# and harmless to keep), but current_room and path are only CONDITIONALLY emitted (room
# resolves / trail non-empty) — so they must be cleared before a partial overlay is merged,
# else a stale .storage value (a mid-clean robot_trail[-1] room / lagged trail) survives
# next to a fresh dock anchor: the exact "stale in the kitchen" ghost this feature kills.
_LIVE_POSE_OWNED_KEYS = ("current_room", "path")


def apply_live_pose_override(result: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Make the fresh live pose AUTHORITATIVE over the lagged .storage overlays: drop the
    owned moving keys, then merge the (possibly partial) overlay. No-op when the overlay is
    empty (dims missing) — we then have no live replacement, so the .storage values stand.
    Mutates + returns `result`. Mirrored on the card in state.mapOverlayData()."""
    if not overlay:
        return result
    for key in _LIVE_POSE_OWNED_KEYS:
        result.pop(key, None)
    result.update(overlay)
    return result


def eufy_version_of(map_data: dict[str, Any]) -> str:
    """A short content hash of the room raster — changes only on a re-map. Used to cache the
    per-room scan (so the memory backend re-scans on a re-map, not every refresh) and for the
    card's render-data fetch caching. "" when there's no raster."""
    rp = map_data.get("room_pixels")
    if not rp:
        return ""
    return hashlib.sha1(str(rp).encode("utf-8", "ignore")).hexdigest()[:12]


def render_data_from_storage(map_data: dict[str, Any]) -> dict[str, Any] | None:
    """Eufy storage backend: the raw RASTER + DECODE PARAMS the card renders from.

    Returns the room-id raster (`room_pixels` b64) plus EXPLICIT decode params — render
    canvas dims, the room_outline raster dims + offset to the main grid, the Y-flip, the
    rid bit-shift, the catch-all id, and `room_names` — so the card can rebuild the
    floor plan generically WITHOUT any brand assumptions (it just applies these params).
    `version` is a content hash for client-side caching (re-fetch only when the map
    changes). None when no segmentation. Pure; coupling to the Eufy shape lives behind
    the adapter's `map_render.format` that selects this reader. Wave 1 = rooms only;
    walls/obstacles (`raw_pixels`) are Wave 2 once that encoding is decoded.
    """
    rp_b64 = map_data.get("room_pixels")
    if not rp_b64:
        return None
    geom = _outline_geometry(map_data)
    if geom is None:
        return None
    ro_w, ro_h, ro_dx, ro_dy, res, width, height = geom
    names = map_data.get("room_names")
    if not isinstance(names, dict):
        names = {}
    rp_str = str(rp_b64)
    version = eufy_version_of(map_data)
    return {
        "present": True,
        "format": "eufy_room_pixels_v1",
        "width": width,            # render-canvas dims (main grid)
        "height": height,
        "ro_width": ro_w,          # room_pixels raster dims (room_outline frame)
        "ro_height": ro_h,
        "ro_dx": ro_dx,            # raster -> main-grid integer offset
        "ro_dy": ro_dy,
        "res": res,
        "flip_y": True,            # render flips top-bottom
        "rid_shift": 2,            # room id = byte >> rid_shift
        "catch_all_rid": _CATCH_ALL_RID,
        "room_pixels": rp_str,
        "room_names": {str(k): str(v) for k, v in names.items()},
        "version": version,
    }


# Fields lifted from the fork's in-memory MapData OBJECT into the .storage-shaped map_data
# DICT. The byte rasters are base64-encoded so the storage-oriented decoders (rooms /
# render / current-room) consume them UNCHANGED; the rest copy straight across.
_MAPDATA_BYTE_FIELDS = ("room_pixels", "raw_pixels")
_MAPDATA_PLAIN_FIELDS = (
    "width", "height", "origin_x", "origin_y", "resolution",
    "room_outline_width", "room_outline_height",
    "room_outline_origin_x", "room_outline_origin_y",
    "room_names", "virtual_walls", "forbidden_zones", "ban_mop_zones",
)


def mapdata_dict_from_obj(obj: Any, *, field_attrs: Any = None) -> dict[str, Any] | None:
    """Convert the fork's in-memory ``MapData`` OBJECT into the same map_data DICT the
    storage decoders consume (base64 for the byte rasters), so a repointed in-memory source
    reuses every existing decoder unchanged. ``field_attrs`` optionally remaps a logical
    field to a different object attr (drift insurance). Returns None when there's no
    ``room_pixels`` raster (not a usable MapData) — the caller then falls back to .storage.
    Pure + never raises."""
    fa = field_attrs if isinstance(field_attrs, dict) else {}

    def _attr(name: str) -> Any:
        return getattr(obj, fa.get(name, name), None)

    try:
        rp = _attr("room_pixels")
        if not isinstance(rp, (bytes, bytearray)):
            return None
        out: dict[str, Any] = {}
        for name in _MAPDATA_BYTE_FIELDS:
            v = _attr(name)
            if isinstance(v, (bytes, bytearray)):
                out[name] = base64.b64encode(bytes(v)).decode("ascii")
        for name in _MAPDATA_PLAIN_FIELDS:
            v = _attr(name)
            if v is not None:
                out[name] = v
        return out
    except Exception:  # noqa: BLE001 - a provider object must never crash the reader
        return None


def _raster_digest(b64: Any) -> dict[str, Any] | None:
    """len + short sha1 of a base64 raster — enough to prove equality without dumping 200 KB."""
    if not isinstance(b64, str) or not b64:
        return None
    return {"len": len(b64), "sha1": hashlib.sha1(b64.encode("ascii")).hexdigest()[:12]}


def _layer_count(v: Any) -> int | None:
    return len(v) if isinstance(v, (list, tuple)) else None


def _key_types(d: Any) -> str | None:
    """The set of key python-types in a dict (e.g. "int" vs "str"), so a room_names
    inequality that's purely native-int-keys vs JSON-str-keys is visible as such."""
    if not isinstance(d, dict):
        return None
    if not d:
        return "empty"
    return "+".join(sorted({type(k).__name__ for k in d}))


def compare_map_data(memory: dict[str, Any], storage: dict[str, Any]) -> dict[str, Any]:
    """VERIFY PROBE (P1): field-by-field compare of the in-memory vs .storage map_data dicts
    to confirm the in-memory bytes are byte-identical BEFORE repointing the source. Rasters are
    compared by len+sha1 (not dumped); geometry by value. ``normalization_safe`` is True iff
    every field the decoders actually use (the raster + the outline/grid geometry) matches — so
    the validated dead-on overlay alignment is provably preserved. Hazards/room_names are
    reported informationally. Pure."""
    geom_fields = (
        "width", "height", "origin_x", "origin_y", "resolution",
        "room_outline_width", "room_outline_height",
        "room_outline_origin_x", "room_outline_origin_y",
    )
    fields: dict[str, Any] = {}
    normalization_safe = True

    for f in _MAPDATA_BYTE_FIELDS:
        mv, sv = memory.get(f), storage.get(f)
        equal = mv == sv
        fields[f] = {"equal": equal, "memory": _raster_digest(mv), "storage": _raster_digest(sv)}
        if f == "room_pixels" and not equal:
            normalization_safe = False

    for f in geom_fields:
        mv, sv = memory.get(f), storage.get(f)
        equal = mv == sv
        fields[f] = {"equal": equal, "memory": mv, "storage": sv}
        if not equal:
            normalization_safe = False

    # room_names is labels-only (never affects normalization). Dump both + their key TYPES so
    # an inequality is explained (native int keys in memory vs JSON str keys in storage is the
    # benign + expected case the decoders already handle).
    mem_names, store_names = memory.get("room_names"), storage.get("room_names")
    fields["room_names"] = {
        "equal": mem_names == store_names,
        "memory_key_types": _key_types(mem_names),
        "storage_key_types": _key_types(store_names),
        "memory": mem_names,
        "storage": store_names,
    }
    # Hazard layers: counts + the FIRST entry of each (shape sample) so the coordinate frame
    # can be designed before rendering them (P3). Eufy: virtual_walls / forbidden_zones (no-go)
    # / ban_mop_zones (vacuum-only).
    for hz in ("virtual_walls", "forbidden_zones", "ban_mop_zones"):
        mv, sv = memory.get(hz), storage.get(hz)
        fields[hz] = {
            "memory": _layer_count(mv),
            "storage": _layer_count(sv),
            "sample": (mv[0] if isinstance(mv, (list, tuple)) and mv else None),
        }

    return {"normalization_safe": normalization_safe, "fields": fields}


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
