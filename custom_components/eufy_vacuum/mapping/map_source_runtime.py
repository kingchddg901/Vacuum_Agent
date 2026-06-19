"""Runtime locators for the `map_state_source` seam — the HA-aware glue.

The pure extraction/normalization lives in ``map_source.py``; THIS module FINDS the
provider's data at runtime and hands plain data to it:

  - **Eufy (storage backend):** read the eufy-clean fork's HA Store file
    (``.storage/robovac_mqtt.<serial>``), version-guard it, and pull the decoded
    ``map_data`` the fork already persists (room_pixels raster + dock/robot anchors).
  - **Roborock (memory backend):** walk the in-memory parsed map the HA-core Roborock
    integration keeps (config-entry ``runtime_data`` / ``hass.data[domain]``). The exact
    attribute path is NOT knowable offline, so this is a DEFENSIVE introspector that
    duck-types for a Room-like collection and ALWAYS attaches a ``diagnostics`` breadcrumb
    — the live deploy is what confirms/tunes the path (docs/dev/map-state-source.md, Wave 1).

Both apply the adapter's presence gate (live-map artifact present) and degrade to an
absent marker — never raise — on any missing/typed-wrong input, per the seam's
never-crash contract. The blocking ``.storage`` read (``load_store_json``) MUST be
called via an executor; everything else is in-memory.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .map_source import (
    _as_int,
    _clamp01,
    _decimate_step,
    anchors_from_storage,
    build_map_source_result,
    hazards_from_mapdata,
    overlays_from_storage,
    render_data_from_storage,
    rooms_from_room_pixels,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared: device identity from the public registry.
# ---------------------------------------------------------------------------

def device_identifier_value(
    hass: HomeAssistant, vacuum_entity_id: str, identifier_domain: str
) -> str | None:
    """Return the device-registry identifier value for a domain, or None.

    The eufy-clean fork keys its Store by the device SERIAL (== the
    ``(robovac_mqtt, <serial>)`` registry identifier); Roborock by its duid. Pulled
    from the PUBLIC device registry only — no provider-private state. Falls back to
    ``device.serial_number`` (which equals the fork serial on Eufy).
    """
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(vacuum_entity_id)
    if entry is None or entry.device_id is None:
        return None
    device = dr.async_get(hass).async_get(entry.device_id)
    if device is None:
        return None
    for domain, ident in device.identifiers:
        if domain == identifier_domain:
            return ident
    return device.serial_number


# ---------------------------------------------------------------------------
# Eufy storage backend.
# ---------------------------------------------------------------------------

def eufy_store_path(
    hass: HomeAssistant, vacuum_entity_id: str, source_cfg: dict[str, Any]
) -> str | None:
    """Resolve the ``.storage`` path for the Eufy fork's map Store, or None.

    Registry lookup only (in-memory, loop-safe). The actual file read is
    ``load_store_json`` and MUST go through an executor.
    """
    domain = source_cfg.get("identifier_domain", "robovac_mqtt")
    device_id = device_identifier_value(hass, vacuum_entity_id, domain)
    if not device_id:
        return None
    key_tmpl = source_cfg.get("store_key") or f"{domain}.{{device_id}}"
    try:
        store_key = str(key_tmpl).format(device_id=device_id)
    except (KeyError, IndexError, ValueError):
        return None
    return hass.config.path(".storage", store_key)


def load_store_json(path: str) -> dict[str, Any] | None:
    """Blocking read+parse of an HA Store JSON file; None on any failure.

    Call via ``hass.async_add_executor_job`` — this does disk IO + a JSON parse of a
    file that embeds the map raster (~200 KB), so it MUST stay off the event loop.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def eufy_result_from_store(
    store_json: Any,
    *,
    expected_version: int | None = None,
    present: bool = True,
) -> dict[str, Any]:
    """PURE: normalized ``map_state_source`` result from a loaded Eufy Store dict.

    Applies the optional store-version guard, then extracts per-room bbox+name from
    ``data.map_data.room_pixels`` and dock/robot anchors from ``data``. ``present`` is
    the caller's presence gate (the live-map artifact); when False the result is the
    absent marker regardless of contents. Degrades to absent on any mismatch — never
    raises. Unit-tested without HA.
    """
    if not isinstance(store_json, dict):
        return build_map_source_result(present=False, backend="storage", reason="no_store")
    if expected_version is not None and store_json.get("version") != expected_version:
        return build_map_source_result(
            present=False, backend="storage", reason="store_version_mismatch"
        )
    if not present:
        return build_map_source_result(
            present=False, backend="storage", reason="live_map_absent"
        )
    data = store_json.get("data")
    if not isinstance(data, dict):
        return build_map_source_result(present=False, backend="storage", reason="no_store_data")
    map_data = data.get("map_data")
    if not isinstance(map_data, dict):
        map_data = {}
    rooms = rooms_from_room_pixels(map_data)
    anchors = anchors_from_storage(data)
    extra = overlays_from_storage(data)
    return build_map_source_result(
        present=True, backend="storage", rooms=rooms, anchors=anchors, extra=extra
    )


def eufy_result_from_mapdata(
    map_data: Any, *, present: bool = True,
) -> dict[str, Any]:
    """PURE: normalized ``map_state_source`` result from an already-converted IN-MEMORY
    map_data dict (the memory backend — the SAME normalized shape as the storage backend).

    Carries only the STATIC segmentation (per-room bbox+name+area + image_size). The MOVING
    overlays (robot/dock/current-room/path) come from the live pose the caller layers on top
    via apply_live_pose_override — so NO .storage anchors here, BY DESIGN. When the live pose
    is momentarily absent the memory result carries no robot/dock anchor (vs the storage path's
    .storage anchors). That is intentional and MORE correct, not a regression: the .storage
    robot position is the lagged "stale in the kitchen" ghost this feature exists to suppress,
    and the .storage dock pixel can be CROSS-SESSION-DRIFTED (Eufy re-localizes its coordinate
    origin every session — reference_eufy_intersession_coord_drift), so showing it when there's
    no live dock would place the dock at a wrong spot. A transient missing marker (early
    session, before the fork populates the pose) self-heals on the next poll; consumers treat
    anchors as optional and hide them.

    ``present`` is the caller's gate. Degrades to absent on a missing/empty raster (the caller
    then falls back to the .storage read). Never raises. Unit-tested without HA.
    """
    if not present:
        return build_map_source_result(present=False, backend="memory", reason="live_map_absent")
    if not isinstance(map_data, dict):
        return build_map_source_result(present=False, backend="memory", reason="no_mapdata")
    rooms = rooms_from_room_pixels(map_data)
    extra: dict[str, Any] = {}
    w = _as_int(map_data.get("width"))
    h = _as_int(map_data.get("height"))
    if w and h:
        extra["image_size"] = [w, h]
    # Device hazard layers (no-go / vacuum-only / virtual walls) — static, so they ride the
    # version-cached static result alongside the rooms (default OFF in the Map Layers panel).
    extra.update(hazards_from_mapdata(map_data))
    return build_map_source_result(present=True, backend="memory", rooms=rooms, extra=extra)


def eufy_render_data_from_store(
    store_json: Any, *, expected_version: int | None = None
) -> dict[str, Any]:
    """PURE: the card-render raster + decode params from a loaded Eufy Store dict.

    Version-guards the wrapper (the `eufy_room_pixels_v1` format), then extracts the
    raster + explicit decode params via ``render_data_from_storage``. Degrades to
    ``{present: false, reason}`` on any mismatch — never raises. Unit-tested without HA.
    """
    if not isinstance(store_json, dict):
        return {"present": False, "reason": "no_store"}
    if expected_version is not None and store_json.get("version") != expected_version:
        return {"present": False, "reason": "store_version_mismatch"}
    data = store_json.get("data")
    if not isinstance(data, dict):
        return {"present": False, "reason": "no_store_data"}
    map_data = data.get("map_data")
    if not isinstance(map_data, dict):
        return {"present": False, "reason": "no_map_data"}
    result = render_data_from_storage(map_data)
    return result if result is not None else {"present": False, "reason": "no_segmentation"}


# ---------------------------------------------------------------------------
# Roborock memory backend (defensive runtime introspector).
#
# The HA-core Roborock integration keeps the parsed map (vacuum-map-parser
# `MapData`) in memory. The exact attribute path varies across HA versions and
# is not knowable offline, so we duck-type for a Room-like collection and a
# width/height-bearing image, and ALWAYS return a diagnostics breadcrumb. The
# first live deploy's log is what confirms/tunes the path.
# ---------------------------------------------------------------------------

_ROOM_ATTRS = ("x0", "y0", "x1", "y1")

# Attribute names that lead into giant/cyclic graphs (the whole hass tree, the
# cloud API client, listener lists). Never descend through these.
_WALK_SKIP_ATTRS = frozenset({
    "hass", "config_entry", "config_entries", "platform", "platforms",
    "api", "cloud_api", "client", "_listeners", "_unsub", "_unsub_refresh",
    "bus", "states", "services", "loop", "_job", "parent",
})


def _is_roomlike(obj: Any) -> bool:
    """True iff ``obj`` exposes x0/y0/x1/y1 (a vacuum-map-parser ``Room``)."""
    return all(hasattr(obj, a) for a in _ROOM_ATTRS)


def _walk(root: Any, predicate, *, max_depth: int = 5, max_nodes: int = 4000):
    """Bounded BFS over dicts/lists/objects; return (hit, breadcrumb) or (None, None).

    ``predicate(obj)`` decides a hit. Visited-set + node/depth caps + an attr
    denylist keep it crash/cycle/cost-safe over arbitrary provider internals.
    PURE — unit-tested with fake objects.
    """
    seen: set[int] = set()
    q: deque[tuple[Any, str, int]] = deque([(root, "root", 0)])
    nodes = 0
    while q and nodes < max_nodes:
        obj, path, depth = q.popleft()
        if id(obj) in seen or depth > max_depth:
            continue
        seen.add(id(obj))
        nodes += 1
        if predicate(obj):
            return obj, path
        children: list[tuple[Any, str]] = []
        if isinstance(obj, dict):
            children = [(v, f"{path}[{k!r}]") for k, v in obj.items()]
        elif isinstance(obj, (list, tuple)):
            children = [(v, f"{path}[{i}]") for i, v in enumerate(obj)]
        else:
            attrs = getattr(obj, "__dict__", None)
            if isinstance(attrs, dict):
                children = [
                    (v, f"{path}.{k}")
                    for k, v in attrs.items()
                    if k not in _WALK_SKIP_ATTRS and not k.startswith("__")
                ]
        for child, cpath in children:
            if child is None or isinstance(child, (str, bytes, int, float, bool)):
                continue
            q.append((child, cpath, depth + 1))
    return None, None


def find_roomlike_collection(root: Any, *, max_depth: int = 5):
    """BFS for the first dict/list whose members are Room-like. (collection, path)|(None, None)."""
    def _is_room_collection(obj: Any) -> bool:
        members: list[Any] | None = None
        if isinstance(obj, dict):
            members = list(obj.values())
        elif isinstance(obj, (list, tuple)):
            members = list(obj)
        return bool(members) and all(_is_roomlike(m) for m in members)

    return _walk(root, _is_room_collection, max_depth=max_depth)


def _structure_tree(obj: Any, *, depth: int = 0, max_depth: int = 3,
                    max_children: int = 24, show_skipped: bool = False) -> Any:
    """A bounded, JSON-safe shape summary of an object graph for diagnostics.

    Returns nested ``{"<type>": {child: subtree}}`` for objects/dicts and
    ``"<type>[n]"`` leaves for lists/scalars — enough to SEE where a parsed map /
    rooms / Room geometry lives when the duck-typed search misses, without dumping
    values. Honors the same attr denylist + depth cap as the walk.

    ``show_skipped`` surfaces denylisted attrs as ``"<type> (skipped)"`` leaves
    (without descending) so a diagnostic dump reveals that e.g. an ``api`` attr
    exists even though the walk won't traverse it — needed when the sought data
    might sit behind a normally-skipped attr.
    """
    tname = type(obj).__name__
    if depth >= max_depth:
        return tname
    if isinstance(obj, dict):
        items = list(obj.items())[:max_children]
        return {f"dict[{len(obj)}]": {
            str(k): _structure_tree(v, depth=depth + 1, max_depth=max_depth,
                                    max_children=max_children, show_skipped=show_skipped)
            for k, v in items
        }}
    if isinstance(obj, (list, tuple)):
        if not obj:
            return f"{tname}[0]"
        return {f"{tname}[{len(obj)}]": _structure_tree(
            obj[0], depth=depth + 1, max_depth=max_depth,
            max_children=max_children, show_skipped=show_skipped)}
    attrs = getattr(obj, "__dict__", None)
    if isinstance(attrs, dict):
        out: dict[str, Any] = {}
        n = 0
        for k, v in attrs.items():
            if k.startswith("__"):
                continue
            if n >= max_children:
                break
            if k in _WALK_SKIP_ATTRS:
                if show_skipped:
                    out[k] = f"{type(v).__name__} (skipped)"
                continue
            out[k] = _structure_tree(v, depth=depth + 1, max_depth=max_depth,
                                     max_children=max_children, show_skipped=show_skipped)
            n += 1
        return {tname: out} if out else tname
    return tname


def _room_diagnostics(collection: Any, sample: int = 3) -> list[dict[str, Any]]:
    """First few rooms' raw coords/number/name — fuels access-path tuning on first deploy."""
    items = list(collection.values()) if hasattr(collection, "values") else list(collection)
    out: list[dict[str, Any]] = []
    for r in items[:sample]:
        out.append({
            "number": getattr(r, "number", None),
            "name": getattr(r, "name", None),
            "x0": getattr(r, "x0", None), "y0": getattr(r, "y0", None),
            "x1": getattr(r, "x1", None), "y1": getattr(r, "y1", None),
        })
    return out


class _XY:
    """Minimal point shim (x/y/a) passed INTO the parser's ImageDimensions.to_img.

    Lets us drive the library's authoritative vacuum->pixel transform without
    importing its Point class (only present where roborock is installed). to_img reads
    ``.x``/``.y`` and returns a real library Point we then read back.
    """
    __slots__ = ("x", "y", "a")

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y, self.a = x, y, None


def _is_mapdata(o: Any) -> bool:
    """True iff ``o`` looks like a vacuum-map-parser MapData (has .rooms AND .image)."""
    return (
        getattr(o, "image", None) is not None
        and getattr(o, "rooms", None) is not None
        and hasattr(o, "rooms") and hasattr(o, "image")
    )


def find_mapdata(root: Any, *, max_depth: int = 6):
    """BFS for a MapData-like object (.rooms + .image). (mapdata, path)|(None, None).

    Targets MapData specifically so we read ``map_data.rooms`` — NOT a generic
    x0/y0/x1/y1 collection, which also matches ``map_data.no_go_areas``/walls/zones.
    """
    return _walk(root, _is_mapdata, max_depth=max_depth)


def _mapdata_projector(map_data: Any):
    """Build the vacuum->normalized-pixel projector for a MapData. (proj, img_w, img_h)|None.

    ``proj(x, y)`` returns ``[nx, ny]`` in 0..1 of the RENDERED image, via the parser's
    OWN ``ImageDimensions.to_img(point).rotated(dims)`` transform (the /50, trim offset,
    Y-flip, scale, rotation) normalized by ``image.data.size``. Calling the library
    transform (vs reimplementing) is the "use the device's computed value" rule. ``proj``
    returns None on any per-point failure (incl. None coords) so callers can drop bad
    points. None when the image geometry is unavailable.
    """
    image = getattr(map_data, "image", None)
    dims = getattr(image, "dimensions", None)
    data = getattr(image, "data", None)
    if dims is None or data is None or not hasattr(dims, "to_img"):
        return None
    try:
        img_w, img_h = int(data.size[0]), int(data.size[1])
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    if img_w <= 0 or img_h <= 0:
        return None
    rotation = getattr(dims, "rotation", 0)

    def proj(x: Any, y: Any):
        try:
            p = dims.to_img(_XY(x, y))
            if rotation:
                p = p.rotated(dims)
            return [_clamp01(p.x / img_w), _clamp01(p.y / img_h)]
        except Exception:  # pragma: no cover - defensive over library internals
            return None

    return proj, img_w, img_h


def _rb_area_m2(x0: float, y0: float, x1: float, y1: float) -> float:
    """Bbox area for a Roborock room — coords are vacuum units (1 unit = 1 mm)."""
    return round(abs(x1 - x0) * abs(y1 - y0) / 1_000_000.0, 1)


def rooms_from_mapdata(map_data: Any) -> list[dict[str, Any]]:
    """Roborock MEMORY backend: per-room normalized bbox + name + area from a MapData.

    ``map_data.rooms`` is ``dict[int, Room]`` with x0..y1 in VACUUM coords; each corner
    is projected via the shared ``_mapdata_projector`` (the parser's authoritative
    transform). The parser leaves ``Room.name`` None, so names fall back to
    ``Room {number}`` (Wave 3 reconciles numbers->discovery names). ``area_m2`` is
    bbox-based (overestimates L-rooms — matches ``approximate``). [] on any missing
    piece; never raises.
    """
    rooms_attr = getattr(map_data, "rooms", None)
    if rooms_attr is None:
        return []
    proj_geom = _mapdata_projector(map_data)
    if proj_geom is None:
        return []
    proj = proj_geom[0]
    items = rooms_attr.values() if hasattr(rooms_attr, "values") else rooms_attr
    out: list[dict[str, Any]] = []
    for r in items:
        x0 = getattr(r, "x0", None); y0 = getattr(r, "y0", None)
        x1 = getattr(r, "x1", None); y1 = getattr(r, "y1", None)
        if None in (x0, y0, x1, y1):
            continue
        c0 = proj(x0, y0)
        c1 = proj(x1, y1)
        if not c0 or not c1:
            continue
        # to_img flips Y, so the corners' pixel-y can invert -> re-min/max.
        ax0, ax1 = sorted((c0[0], c1[0]))
        ay0, ay1 = sorted((c0[1], c1[1]))
        num = getattr(r, "number", None)
        name = getattr(r, "name", None)
        out.append({
            "number": num,
            "name": str(name) if name else (
                f"Room {num}" if num is not None else "Room ?"),
            "bbox": [ax0, ay0, ax1, ay1],
            "area_m2": _rb_area_m2(x0, y0, x1, y1),
            "approximate": True,
        })
    return out


def _proj_areas(areas: Any, proj) -> list[list[list[float]]]:
    """Project quadrilateral Areas (x0,y0..x3,y3 — no-go/no-mop) to 4-point polygons."""
    out: list[list[list[float]]] = []
    for a in areas or []:
        pts: list[list[float]] = []
        for i in range(4):
            p = proj(getattr(a, f"x{i}", None), getattr(a, f"y{i}", None))
            if not p:
                pts = []
                break
            pts.append(p)
        if len(pts) == 4:
            out.append(pts)
    return out


def _proj_walls(walls: Any, proj) -> list[list[list[float]]]:
    """Project Wall segments (x0,y0,x1,y1) to [[nx,ny],[nx,ny]] line segments."""
    out: list[list[list[float]]] = []
    for w in walls or []:
        p0 = proj(getattr(w, "x0", None), getattr(w, "y0", None))
        p1 = proj(getattr(w, "x1", None), getattr(w, "y1", None))
        if p0 and p1:
            out.append([p0, p1])
    return out


def _proj_rects(zones: Any, proj) -> list[list[float]]:
    """Project Zone rects (x0,y0,x1,y1) to normalized [x0,y0,x1,y1] bboxes."""
    out: list[list[float]] = []
    for z in zones or []:
        p0 = proj(getattr(z, "x0", None), getattr(z, "y0", None))
        p1 = proj(getattr(z, "x1", None), getattr(z, "y1", None))
        if p0 and p1:
            out.append([min(p0[0], p1[0]), min(p0[1], p1[1]),
                        max(p0[0], p1[0]), max(p0[1], p1[1])])
    return out


def _proj_path(path_obj: Any, proj, *, max_points: int = 160) -> list[list[float]]:
    """Flatten the Path (list of point segments) to a decimated normalized polyline."""
    segs = getattr(path_obj, "path", None)
    if not isinstance(segs, (list, tuple)):
        return []
    pts = [p for seg in segs if isinstance(seg, (list, tuple)) for p in seg]
    if not pts:
        return []
    step = _decimate_step(len(pts), max_points)
    out: list[list[float]] = []
    for i in range(0, len(pts), step):
        q = proj(getattr(pts[i], "x", None), getattr(pts[i], "y", None))
        if q:
            out.append(q)
    return out


def _proj_obstacles(obstacles: Any, proj) -> list[dict[str, Any]]:
    """Project Obstacles (Point + type) to {pos, type, has_photo} markers."""
    out: list[dict[str, Any]] = []
    for o in obstacles or []:
        q = proj(getattr(o, "x", None), getattr(o, "y", None))
        if not q:
            continue
        t = getattr(o, "type", None)
        out.append({
            "pos": q,
            "type": str(t) if t is not None else None,
            "has_photo": bool(getattr(o, "photo", None)
                              or getattr(o, "photo_status", None)),
        })
    return out


def overlays_from_mapdata(map_data: Any) -> dict[str, Any]:
    """Roborock: the non-room overlay layers from a parser MapData, normalized.

    robot anchor + heading, dock anchor, current room, no-go / no-mop polygons, virtual
    walls, saved zones, the cleaning path, and obstacles — all via the shared projector.
    Only non-empty layers are included; [] / missing degrade silently (never raises).
    """
    out: dict[str, Any] = {}
    proj_geom = _mapdata_projector(map_data)
    if proj_geom is None:
        return out
    proj = proj_geom[0]
    # Rendered-image dims so the card can letterbox-correct (object-fit:contain) when
    # placing the normalized overlays over the live backdrop. Only the ASPECT matters.
    out["image_size"] = [proj_geom[1], proj_geom[2]]

    vp = getattr(map_data, "vacuum_position", None)
    if vp is not None:
        q = proj(getattr(vp, "x", None), getattr(vp, "y", None))
        if q:
            out["robot_anchor"] = q
            heading = getattr(vp, "a", None)
            if heading is not None:
                out["robot_heading"] = heading

    ch = getattr(map_data, "charger", None)
    if ch is not None:
        cq = proj(getattr(ch, "x", None), getattr(ch, "y", None))
        if cq:
            out["dock_anchor"] = cq

    vr = getattr(map_data, "vacuum_room", None)
    if isinstance(vr, int) and not isinstance(vr, bool):
        out["current_room"] = vr

    for key, src in (
        ("no_go", "no_go_areas"),
        ("no_mop", "no_mopping_areas"),
    ):
        polys = _proj_areas(getattr(map_data, src, None), proj)
        if polys:
            out[key] = polys
    walls = _proj_walls(getattr(map_data, "walls", None), proj)
    if walls:
        out["walls"] = walls
    zones = _proj_rects(getattr(map_data, "zones", None), proj)
    if zones:
        out["zones"] = zones
    path = _proj_path(getattr(map_data, "path", None), proj)
    if path:
        out["path"] = path
    obstacles = _proj_obstacles(getattr(map_data, "obstacles", None), proj)
    if obstacles:
        out["obstacles"] = obstacles
    return out


def _mapdata_diag(map_data: Any) -> dict[str, Any]:
    """Diagnostics for a found MapData: image dims/size + a raw rooms sample.

    Lets a live read confirm the vacuum->pixel transform from real numbers without
    a service-call deep-dive (raw room coords vs the dims that map them).
    """
    image = getattr(map_data, "image", None)
    dims = getattr(image, "dimensions", None)
    data = getattr(image, "data", None)
    rooms_attr = getattr(map_data, "rooms", None) or {}
    try:
        data_size = list(data.size) if data is not None else None
    except Exception:  # pragma: no cover
        data_size = None
    return {
        "room_count": len(rooms_attr) if hasattr(rooms_attr, "__len__") else None,
        "image_dims": {
            f: getattr(dims, f, None)
            for f in ("top", "left", "width", "height", "scale", "rotation")
        } if dims is not None else None,
        "image_data_size": data_size,
        "rooms_raw_sample": _room_diagnostics(rooms_attr),
    }


def roborock_result_from_candidates(
    candidates: list[tuple[str, str, Any]],
    *,
    present: bool,
) -> dict[str, Any]:
    """PURE: introspect candidate roots for a parsed Roborock MapData.

    ``candidates`` = ``[(origin_label, key, root_obj), ...]``. Finds the first
    MapData-like object (.rooms + .image), projects each Room bbox to normalized
    rendered-image space via the parser's own transform (``rooms_from_mapdata``), and
    ALWAYS attaches a ``diagnostics`` breadcrumb (incl. a structure tree when nothing
    is found). Returns the absent marker on any miss. Never raises.
    """
    diag: dict[str, Any] = {"candidates": [c[0] + ":" + c[1] for c in candidates]}
    if not present:
        return {**build_map_source_result(present=False, backend="memory",
                                          reason="live_map_absent"), "diagnostics": diag}

    for origin, key, root in candidates:
        map_data, mpath = find_mapdata(root)
        if map_data is None:
            continue
        diag.update({"mapdata_at": f"{origin}:{key}:{mpath}", **_mapdata_diag(map_data)})
        rooms = rooms_from_mapdata(map_data)
        if not rooms:
            # MapData located but no usable room geometry (rooms None/empty, missing
            # image dims, or the transform was unavailable) — the diag above shows why.
            return {**build_map_source_result(present=False, backend="memory",
                                              reason="no_room_geometry"), "diagnostics": diag}
        extra = overlays_from_mapdata(map_data)
        return {**build_map_source_result(present=True, backend="memory",
                                          rooms=rooms, extra=extra), "diagnostics": diag}

    # No MapData in any candidate — attach a bounded structure tree of each
    # so the next live read SHOWS where the parsed map / rooms actually live (the
    # duck-typed search only finds x0/y0/x1/y1 objects; geometry may sit behind a
    # denylisted attr, be on a separate entity, or need re-parsing).
    diag["structure"] = {
        f"{origin}:{key}": _structure_tree(root) for origin, key, root in candidates
    }
    return {**build_map_source_result(present=False, backend="memory",
                                      reason="no_parsed_map"), "diagnostics": diag}


def image_entity_object(hass: HomeAssistant, entity_id: str) -> Any:
    """Return the live image ENTITY OBJECT for an entity_id, or None.

    The parsed Roborock ``MapData`` (with Room geometry) is most likely held on the
    map IMAGE entity rather than the coordinator, so we add that object as an
    introspection candidate. Uses the entity-component registry
    (``hass.data["entity_components"]["image"].get_entity``) — there is no public
    by-id entity-object API, so this is best-effort + defensive.
    """
    try:
        comp = (hass.data.get("entity_components") or {}).get("image")
        if comp is not None and hasattr(comp, "get_entity"):
            return comp.get_entity(entity_id)
    except Exception:  # pragma: no cover - defensive over HA internals
        return None
    return None


# ---------------------------------------------------------------------------
# Eufy IN-MEMORY live pose (the moving overlays — robot/dock/heading — fresh ~2s).
#
# The static segmentation comes from .storage (lagged by the fork's save-throttle); the
# robot POSITION there (robot_trail[-1]) is stale. The fork's in-memory coordinator
# holds a live-updating robot pixel (_robot_pixel) used for its own render. We read THAT
# for the moving layers. Exact attr path isn't knowable offline -> defensive introspector
# + structure-dump (deploy-and-discover, like the Roborock backend).
# ---------------------------------------------------------------------------

def _xy_pair(v: Any) -> bool:
    """True iff ``v`` is a 2-element list/tuple of numbers (a [px, py] pixel)."""
    return (
        isinstance(v, (list, tuple)) and len(v) == 2
        and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)
    )


def _first_attr_pair(obj: Any, attrs: Any) -> list[float] | None:
    """First attr in ``attrs`` present on ``obj`` that is a numeric [px, py] pair."""
    for a in (attrs or []):
        v = getattr(obj, a, None)
        if _xy_pair(v):
            return [v[0], v[1]]
    return None


def _first_attr_trail(obj: Any, attrs: Any) -> list[Any] | None:
    """First attr in ``attrs`` that is a non-empty sequence of [px, py] pairs (the robot
    trail). Validated by its LAST point (cheap) and returned as a detached copy so a live
    mutation mid-read can't corrupt it. None when absent."""
    for a in (attrs or []):
        v = getattr(obj, a, None)
        if isinstance(v, (list, tuple)) and v and _xy_pair(v[-1]):
            return list(v)
    return None


def _has_named_attr(obj: Any, attrs: Any) -> bool:
    """True iff any name in ``attrs`` is an instance attribute of ``obj`` — by PRESENCE,
    regardless of value. The fork nulls `_robot_pixel` while the robot is docked, so the
    pose holder must be matched on the attr existing, not on it currently being a pair.
    Prefers the side-effect-free ``__dict__`` check before falling back to hasattr.
    hasattr only swallows AttributeError, but this predicate runs against ARBITRARY provider
    internals during the BFS — a class-level property whose getter raises KeyError/TypeError
    (a plausible shape mid fork-schema-merge) would otherwise escape and break the on-loop
    snapshot. So the fallback is wrapped: any raise => treat the name as not present."""
    d = getattr(obj, "__dict__", None)
    if isinstance(d, dict):
        for a in (attrs or []):
            if a in d:
                return True
    for a in (attrs or []):
        try:
            if hasattr(obj, a):
                return True
        except Exception:  # noqa: BLE001 - a raising descriptor must not escape the walk
            continue
    return False


def eufy_inmem_candidates(
    hass: HomeAssistant, source_cfg: dict[str, Any]
) -> list[tuple[str, str, Any]]:
    """Candidate roots holding the fork's in-memory coordinator (hass.data + runtime_data)."""
    domain = source_cfg.get("hass_data_domain", "robovac_mqtt")
    out: list[tuple[str, str, Any]] = []
    bucket = (hass.data or {}).get(domain)
    if bucket is not None:
        out.append(("hass_data", domain, bucket))
    try:
        entries = hass.config_entries.async_entries(domain)
    except Exception:  # pragma: no cover - defensive over HA internals
        entries = []
    for entry in entries:
        rd = getattr(entry, "runtime_data", None)
        if rd is not None:
            out.append(("runtime_data", entry.entry_id, rd))
    return out


def eufy_live_pose_from_candidates(
    candidates: list[tuple[str, str, Any]],
    *,
    robot_attrs: Any,
    dock_attrs: Any,
    heading_attrs: Any = None,
    trail_attrs: Any = None,
) -> dict[str, Any]:
    """PURE: find the fork's live robot/dock PIXEL (+ trail) in the in-memory candidates.

    BFS for the pose HOLDER — the object carrying BOTH a robot- and a dock-pixel attr (by
    PRESENCE: the fork nulls the robot pixel while docked, so value-matching would miss a
    docked robot — exactly the case the live read exists to fix). Reads robot (None when
    docked), dock, trail, and heading off that holder. ALWAYS attaches a ``diagnostics``
    breadcrumb (a structure tree when nothing is found) so the first live deploy reveals the
    real attr path. ``present`` is True when EITHER a robot or a dock pixel resolves (a
    docked robot has only a dock). Returns the absent marker on any miss.

    NEVER RAISES (the dashboard-snapshot service calls this ON THE EVENT LOOP): the walk +
    attribute reads run against arbitrary provider internals whose property getters can raise
    a non-AttributeError, so the per-candidate body is wrapped — a raise degrades that
    candidate to a miss rather than aborting the snapshot. Mirrors the Roborock side's guard.
    """
    diag: dict[str, Any] = {"candidates": [c[0] + ":" + c[1] for c in candidates]}

    def _is_pose_holder(o: Any) -> bool:
        return _has_named_attr(o, robot_attrs) and _has_named_attr(o, dock_attrs)

    for origin, key, root in candidates:
        try:
            holder, path = _walk(root, _is_pose_holder)
            if holder is None:
                continue
            robot = _first_attr_pair(holder, robot_attrs)  # None while docked
            dock = _first_attr_pair(holder, dock_attrs)
            trail = _first_attr_trail(holder, trail_attrs)
            heading = None
            for a in (heading_attrs or []):
                hv = getattr(holder, a, None)
                if isinstance(hv, (int, float)) and not isinstance(hv, bool):
                    heading = hv
                    break
        except Exception:  # noqa: BLE001 - a raising provider internal degrades to a miss
            continue
        diag.update({
            "pose_at": f"{origin}:{key}:{path}",
            "holder_type": type(holder).__name__,
            "robot_docked": robot is None and dock is not None,
        })
        return {
            "present": robot is not None or dock is not None,
            "robot_pixel": robot,
            "dock_pixel": dock,
            "robot_heading": heading,
            "trail_pixels": trail,
            "diagnostics": diag,
        }

    try:
        diag["structure"] = {
            f"{o}:{k}": _structure_tree(r, max_depth=6, max_children=40, show_skipped=True)
            for o, k, r in candidates
        }
    except Exception:  # noqa: BLE001 - the diagnostic dump must not raise either
        diag["structure"] = {"error": "structure dump failed"}
    return {"present": False, "reason": "no_pose", "diagnostics": diag}


def eufy_mapdata_obj_from_candidates(
    candidates: list[tuple[str, str, Any]],
    *,
    mapdata_attrs: Any,
    field_attrs: Any = None,
) -> dict[str, Any]:
    """Find the fork's in-memory ``MapData`` OBJECT + a CHEAP content version, WITHOUT the
    ~180 KB base64 conversion.

    BFS for the holder of one of ``mapdata_attrs`` (e.g. ``_map_data``) whose value carries a
    bytes ``room_pixels`` raster; the version is sha1 of the RAW raster bytes. Lets the hot
    map_state_source path cache-check the version and only do the (expensive) dict conversion +
    per-room scan on a genuine re-map. Returns ``{present, obj, version, diagnostics}``; the
    absent marker on a miss. NEVER RAISES — runs on the event loop.
    """
    fa = field_attrs if isinstance(field_attrs, dict) else {}
    rp_name = fa.get("room_pixels", "room_pixels")
    names = mapdata_attrs or ["_map_data", "map_data"]
    diag: dict[str, Any] = {"candidates": [c[0] + ":" + c[1] for c in candidates]}

    def _holds_mapdata(o: Any) -> bool:
        # Cheap predicate: an object exposing a MapData with a bytes raster (no convert).
        for a in names:
            v = getattr(o, a, None)
            if v is not None and isinstance(getattr(v, rp_name, None), (bytes, bytearray)):
                return True
        return False

    for origin, key, root in candidates:
        try:
            holder, path = _walk(root, _holds_mapdata)
            if holder is None:
                continue
            for a in names:
                v = getattr(holder, a, None)
                rp = getattr(v, rp_name, None) if v is not None else None
                if isinstance(rp, (bytes, bytearray)):
                    version = hashlib.sha1(bytes(rp)).hexdigest()[:12]
                    diag["mapdata_at"] = f"{origin}:{key}:{path}.{a}"
                    return {"present": True, "obj": v, "version": version, "diagnostics": diag}
        except Exception:  # noqa: BLE001 - a raising provider internal degrades to a miss
            continue

    return {"present": False, "reason": "no_mapdata", "diagnostics": diag}


def eufy_mapdata_from_candidates(
    candidates: list[tuple[str, str, Any]],
    *,
    mapdata_attrs: Any,
    field_attrs: Any = None,
) -> dict[str, Any]:
    """Find the fork's in-memory ``MapData`` and CONVERT it to the .storage map_data DICT shape
    (so the existing decoders consume it unchanged). Thin wrapper over
    ``eufy_mapdata_obj_from_candidates`` + ``mapdata_dict_from_obj`` — for the non-hot callers
    (the render-data fetch + the compare probe); the hot map_state_source path uses the obj
    locator + its own version cache to avoid re-converting an unchanged map. Returns
    ``{present, map_data, version, diagnostics}``; absent on a miss. Never raises.
    """
    from .map_source import mapdata_dict_from_obj

    fa = field_attrs if isinstance(field_attrs, dict) else {}
    found = eufy_mapdata_obj_from_candidates(
        candidates, mapdata_attrs=mapdata_attrs, field_attrs=fa
    )
    if not found.get("present"):
        return found
    md = mapdata_dict_from_obj(found["obj"], field_attrs=fa)
    if md is None:
        return {"present": False, "reason": "no_mapdata", "diagnostics": found.get("diagnostics")}
    return {
        "present": True, "map_data": md,
        "version": found.get("version"), "diagnostics": found.get("diagnostics"),
    }


def roborock_candidates(
    hass: HomeAssistant,
    source_cfg: dict[str, Any],
    *,
    image_entity_id: str | None = None,
) -> list[tuple[str, str, Any]]:
    """Collect candidate Roborock map roots to introspect.

    Sources: each config-entry ``runtime_data``, ``hass.data[domain]``, and — when
    known — the live map IMAGE entity object (the likely home of the parsed MapData).
    In-memory only (loop-safe). The duck-typed search + structure dump pick the rooms
    out of whatever shape these expose, so we don't over-filter here.
    """
    domain = source_cfg.get("hass_data_domain", "roborock")
    out: list[tuple[str, str, Any]] = []
    if image_entity_id:
        ent = image_entity_object(hass, image_entity_id)
        if ent is not None:
            out.append(("image_entity", image_entity_id, ent))
    try:
        entries = hass.config_entries.async_entries(domain)
    except Exception:  # pragma: no cover - defensive over HA internals
        entries = []
    for entry in entries:
        rd = getattr(entry, "runtime_data", None)
        if rd is not None:
            out.append(("runtime_data", entry.entry_id, rd))
    bucket = (hass.data or {}).get(domain)
    if bucket is not None:
        out.append(("hass_data", domain, bucket))
    return out
