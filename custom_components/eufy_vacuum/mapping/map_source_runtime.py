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
    domain = source_cfg.get("identifier_domain")
    if not domain:
        return None
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


def _slot_names(obj: Any) -> list[str]:
    """RB-7: instance attribute names for a ``__slots__`` object (no ``__dict__``),
    walking the MRO so inherited slots are included too. [] for anything without
    ``__slots__``. Bounded to the NAMES the class actually declares — not a blanket
    ``dir()``, which would also pull in methods/dunders/class attrs and blow past the
    "attribute data only" contract the ``__dict__`` path already has."""
    names: list[str] = []
    seen_names: set[str] = set()
    for klass in type(obj).__mro__:
        slots = getattr(klass, "__slots__", None)
        if slots is None:
            continue
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name not in seen_names:
                seen_names.add(name)
                names.append(name)
    return names


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
            else:
                # RB-7: a __slots__ object has no __dict__ and used to dead-end here,
                # silently hiding its data from the BFS. Walk its declared slot names
                # instead — bounded to what the class actually declares (same depth/
                # cycle/denylist guards below apply uniformly to whatever `children`
                # ends up holding).
                for name in _slot_names(obj):
                    if name in _WALK_SKIP_ATTRS or name.startswith("__"):
                        continue
                    try:
                        v = getattr(obj, name)
                    except AttributeError:
                        continue  # slot declared but unset
                    children.append((v, f"{path}.{name}"))
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
    # RB-7: a __slots__ object has no __dict__ — fall back to its declared slot names
    # (bounded, not a blanket dir()) so it doesn't dead-end as an opaque leaf.
    items_source: Any = attrs.items() if isinstance(attrs, dict) else None
    if items_source is None:
        slot_names = _slot_names(obj)
        if slot_names:
            def _slot_items():
                for name in slot_names:
                    try:
                        yield name, getattr(obj, name)
                    except AttributeError:
                        continue  # slot declared but unset
            items_source = _slot_items()
    if items_source is not None:
        out: dict[str, Any] = {}
        n = 0
        for k, v in items_source:
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


def _is_map_content(o: Any) -> bool:
    """True iff ``o`` looks like a python-roborock v1 ``MapContent`` — the object that holds
    the RAW map blob next to the parsed map: a bytes ``raw_api_response`` + a ``map_data``."""
    rar = getattr(o, "raw_api_response", None)
    return isinstance(rar, (bytes, bytearray)) and getattr(o, "map_data", None) is not None


def find_map_content(root: Any, *, max_depth: int = 6):
    """BFS for a ``MapContent``-like object (``raw_api_response`` bytes + ``map_data``).
    ``(map_content, path)|(None, None)``. This is the object our v1 segment decoder
    re-parses — it sits right next to the ``map_data`` that ``find_mapdata`` targets."""
    return _walk(root, _is_map_content, max_depth=max_depth)


def roborock_render_data_from_candidates(candidates: Any, room_names: Any = None) -> dict[str, Any]:
    """Roborock render-data (P2 bridge): locate the ``MapContent`` among the candidate roots,
    decode its raw map blob to a per-pixel room-id raster, and shape it as the card's generic
    render-data — the same roots ``roborock_result_from_candidates`` walks, but reading the
    RAW bytes rather than the parsed bboxes. Returns the render-data dict or an absent marker;
    never raises."""
    from .roborock_raw_map import decode_roborock_v1_segments, roborock_render_data

    for cand in candidates or []:
        root = cand[2] if isinstance(cand, (list, tuple)) and len(cand) >= 3 else cand
        mc, _path = find_map_content(root)
        if mc is None:
            continue
        decoded = decode_roborock_v1_segments(getattr(mc, "raw_api_response", None))
        rd = roborock_render_data(decoded, room_names)
        if rd is not None:
            return rd
    return {"present": False, "reason": "no_raw_map"}


def roborock_geometry_drift_from_candidates(candidates: Any) -> dict[str, Any]:
    """On-device decode validator: for the first candidate exposing BOTH a parsed MapData and
    a raw map blob, overlay the parser's per-room bboxes with the raster-decoded bboxes and
    report the drift. Since both derive from the SAME segment layer, aligned boxes confirm the
    decode (rid/orientation/frame) and a systematic delta is the calibration signal. Returns
    the drift report (``present: True`` + the geometry_drift fields) or an absent marker;
    never raises."""
    from .roborock_raw_map import decode_roborock_v1_segments, geometry_drift

    for cand in candidates or []:
        root = cand[2] if isinstance(cand, (list, tuple)) and len(cand) >= 3 else cand
        md, _md_path = find_mapdata(root)
        mc, _mc_path = find_map_content(root)
        if md is None or mc is None:
            continue
        decoded = decode_roborock_v1_segments(getattr(mc, "raw_api_response", None))
        if decoded is None:
            continue
        return {"present": True, **geometry_drift(rooms_from_mapdata(md), decoded)}
    return {"present": False, "reason": "no_geometry"}


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

    def proj(x: Any, y: Any, *, reject_out_of_grid: bool = False):
        """GEO-4/RB-8: ``reject_out_of_grid`` (default False — every existing caller
        keeps today's unconditional clamp) makes a point whose RAW (pre-clamp)
        projected pixel falls outside the image return None instead of a clamped
        edge point, so a caller that wants to DETECT a bad/out-of-frame correspondence
        (rather than draw it) can opt in.

        live:RB-PROJ-1 — the two None returns below mean OPPOSITE things and are
        counted apart. ``out_of_grid`` is a deliberate, healthy rejection. ``errors``
        is the library transform failing, and if it ever hits 100% every Roborock
        overlay vanishes at once. Counters ride on the function object so no call
        site had to change shape.
        """
        proj.calls += 1
        try:
            p = dims.to_img(_XY(x, y))
            if rotation:
                p = p.rotated(dims)
            raw_x, raw_y = p.x / img_w, p.y / img_h
            if reject_out_of_grid and not (0.0 <= raw_x <= 1.0 and 0.0 <= raw_y <= 1.0):
                proj.out_of_grid += 1
                return None
            return [_clamp01(raw_x), _clamp01(raw_y)]
        except Exception:  # pragma: no cover - defensive over library internals
            proj.errors += 1
            return None

    proj.calls = 0
    proj.errors = 0
    proj.out_of_grid = 0
    return proj, img_w, img_h


#: live:RB-PROJ-1. True while the projector is failing EVERY call, so the warning
#: fires on the transition instead of on every map refresh (~30 s on Roborock).
_projector_alarm_active = False


def _note_projector_health(proj) -> dict[str, int]:
    """Count what the projector dropped, and SAY SO when it drops everything.

    THE DEFECT THIS CLOSES. `proj` swallows Exception per point and every caller
    drops silently (`if p0 and p1`, `if not p: continue`, …), and
    ``overlays_from_mapdata`` omits empty layers by contract. So a change inside
    ``vacuum-map-parser-roborock``'s ``ImageDimensions.to_img`` — a dependency HA
    core bumps on its own schedule, outside this repo's control — takes out no-go
    quads, no-mop quads, virtual walls, saved zones, the path, obstacle markers AND
    the room list in one stroke, while the map still reports present:True and
    renders the raster. The user sees a correct-looking map with nothing on it and
    nothing anywhere says why. A layer that had inputs and produced zero output was
    indistinguishable from a legitimately empty layer; these counts are the whole
    difference.

    Warns only on TOTAL failure. Partial drops are normal — `reject_out_of_grid`
    exists precisely to discard off-frame points — so alarming on those would train
    everyone to ignore the line.

    The repairs platform is deliberately NOT the surface: repairs.py was deleted as
    unreachable (#14:INF-6) and purged off the live box (RP-052). The log is, now
    that it is known to live at /api/hassio/core/logs rather than a file nobody
    could find.
    """
    global _projector_alarm_active
    stats = {
        "calls": int(getattr(proj, "calls", 0)),
        "errors": int(getattr(proj, "errors", 0)),
        "out_of_grid": int(getattr(proj, "out_of_grid", 0)),
    }
    total_failure = stats["calls"] > 0 and stats["errors"] == stats["calls"]
    if total_failure and not _projector_alarm_active:
        _LOGGER.warning(
            "Roborock overlay projector failed EVERY point (%d/%d): every overlay "
            "layer — rooms, no-go, no-mop, walls, zones, path, obstacles — will be "
            "empty while the map still renders. Most likely the parser's "
            "ImageDimensions.to_img changed shape. live:RB-PROJ-1",
            stats["errors"], stats["calls"],
        )
        _projector_alarm_active = True
    elif not total_failure and _projector_alarm_active:
        _LOGGER.warning("Roborock overlay projector recovered (%d/%d errors).",
                        stats["errors"], stats["calls"])
        _projector_alarm_active = False
    return stats


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
            # Real-world bbox dimensions (the room's axis-aligned extent in metres) from
            # the raw vacuum-mm corners — a to-scale guide for the furnished render. The
            # bbox over-estimates non-rectangular rooms (matches `approximate`).
            "width_m": round(abs(x1 - x0) / 1000.0, 2),
            "height_m": round(abs(y1 - y0) / 1000.0, 2),
            "approximate": True,
        })
    return out


def correspondences_from_mapdata(map_data: Any) -> list[tuple[float, float, float, float]]:
    """``(nx, ny, mmx, mmy)`` pairs from the live map's room-bbox corners.

    This is the input the zone-dispatch affine fit needs to invert the normalized->mm
    mapping for brands (Roborock) whose zone command wants device millimetres. Each room
    contributes its four axis-aligned corners, projected device-mm -> normalized via the
    shared ``_mapdata_projector`` (the parser's OWN transform — same source of truth as
    ``rooms_from_mapdata``). Returns ``[]`` when geometry is unavailable; bad/clamped
    corners are ACTUALLY skipped (GEO-4/RB-8: ``proj`` is called with
    ``reject_out_of_grid=True`` here, so a corner that projects outside the image is
    dropped rather than silently accepted as a clamped edge point — a clamped-but-wrong
    correspondence would otherwise feed the affine fit a corrupted data point instead of
    being excluded from it).
    """
    rooms_attr = getattr(map_data, "rooms", None)
    if rooms_attr is None:
        return []
    proj_geom = _mapdata_projector(map_data)
    if proj_geom is None:
        return []
    proj = proj_geom[0]
    items = rooms_attr.values() if hasattr(rooms_attr, "values") else rooms_attr
    out: list[tuple[float, float, float, float]] = []
    for r in items:
        x0 = getattr(r, "x0", None); y0 = getattr(r, "y0", None)
        x1 = getattr(r, "x1", None); y1 = getattr(r, "y1", None)
        if None in (x0, y0, x1, y1):
            continue
        for mx, my in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            p = proj(mx, my, reject_out_of_grid=True)
            if p:
                try:
                    out.append((p[0], p[1], float(mx), float(my)))
                except (TypeError, ValueError):
                    continue
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


# vacuum-map-parser-roborock's obstacle-type ints (its KNOWN_OBSTACLE_TYPES),
# normalized to stable slugs the card translates via vocab.obstacle_type.*.
# Unknown ints pass through as the number string — locale-neutral, never an
# English leak into the tooltip sink.
_OBSTACLE_TYPE_SLUGS = {
    0: "cable", 48: "cable",
    1: "pet_waste",
    2: "shoes",
    3: "poop",
    4: "pedestal",
    5: "extension_cord",
    9: "weighing_scale",
    10: "clothes", 34: "clothes",
    25: "dustpan",
    26: "furniture_crossbar", 27: "furniture_crossbar",
    49: "pet", 50: "pet",
    51: "fabric_paper_balls",
}


def _proj_obstacles(obstacles: Any, proj) -> list[dict[str, Any]]:
    """Project Obstacles to {pos, type, has_photo} markers.

    The parser keeps obstacle metadata on ``Obstacle.details`` (ObstacleDetails:
    ``type`` int, ``photo_name``) — there is no flat ``o.type``/``o.photo``;
    the flat reads are kept only as a degrade path for other parser shapes.
    """
    out: list[dict[str, Any]] = []
    for o in obstacles or []:
        q = proj(getattr(o, "x", None), getattr(o, "y", None))
        if not q:
            continue
        details = getattr(o, "details", None)
        t = getattr(details, "type", None)
        if t is None:
            t = getattr(o, "type", None)
        slug: str | None = None
        if t is not None:
            if isinstance(t, int) and not isinstance(t, bool):
                slug = _OBSTACLE_TYPE_SLUGS.get(t) or str(t)
            else:
                slug = str(t)
        photo = (getattr(details, "photo_name", None)
                 or getattr(o, "photo", None)
                 or getattr(o, "photo_status", None))
        out.append({"pos": q, "type": slug, "has_photo": bool(photo)})
    return out


def robot_pose_from_mapdata(map_data: Any, proj: Any = None) -> dict[str, Any]:
    """The MOVING pose from a parser MapData: robot anchor + heading, dock anchor, room.

    THE ONE implementation, shared by the card's overlay payload (``overlays_from_mapdata``)
    and the brand-generic live-pose accessor (``mapdata_live_pose_from_candidates``). It is a
    function BECAUSE this data had two readers and one of them silently got nothing: the
    stall capture asked ``async_get_map_live_pose``, which required a pose declaration only
    the Eufy fork had, while the position it wanted was already on the MapData the card read
    every refresh. Hand-authoring a second extraction for the second reader would have
    re-opened that gap from the other side — so callers share this or they share nothing.

    EVERY VALUE IS NORMALIZED 0..1 against the rendered image, via ``_mapdata_projector`` —
    the parser's own ``to_img(point).rotated(dims)``. ``vacuum_position`` itself is in DEVICE
    coordinates, and handing those raw to a consumer expecting normalized ones puts the robot
    off-map rather than in the wrong place, which is the failure that looks like a bug in the
    consumer. The keys mirror ``live_pose_overlay``'s exactly, so a downstream reader cannot
    tell which brand produced them.

    ``proj`` lets a caller that already built a projector pass it in, so the projector-health
    counters (live:RB-PROJ-1) accumulate over ONE projector per read rather than splitting
    across two and diluting the all-failed signal. Omitted, one is built here. ``{}`` when the
    image geometry is unavailable; never raises.
    """
    out: dict[str, Any] = {}
    if proj is None:
        proj_geom = _mapdata_projector(map_data)
        if proj_geom is None:
            return out
        proj = proj_geom[0]

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
    return out


def mapdata_live_pose_from_candidates(candidates: Any) -> dict[str, Any]:
    """Live pose for ANY brand whose provider keeps a parsed MapData in memory.

    The counterpart to ``eufy_live_pose_from_candidates`` — same contract, different provider
    shape. That one BFS-hunts a fork coordinator's ``_robot_pixel`` and needs a ``.storage``
    read to normalize it; this one finds the parsed map and reads the position the parser has
    already placed in the rendered frame, so there is no file read and nothing to calibrate.

    Walks the SAME candidate roots as ``roborock_result_from_candidates`` /
    ``roborock_render_data_from_candidates`` and returns the shared ``live_pose_overlay``
    shape (``robot_anchor``/``robot_heading``/``dock_anchor``/``current_room``) plus a
    diagnostics breadcrumb. ``present`` is True when a robot or dock anchor resolved — a
    MapData with neither is a real absence, not an error. In-memory only, so it is loop-safe;
    never raises.
    """
    diag: dict[str, Any] = {
        "candidates": [
            (c[0] + ":" + c[1]) if isinstance(c, (list, tuple)) and len(c) >= 2 else str(c)
            for c in (candidates or [])
        ]
    }
    for cand in candidates or []:
        root = cand[2] if isinstance(cand, (list, tuple)) and len(cand) >= 3 else cand
        try:
            map_data, mpath = find_mapdata(root)
            if map_data is None:
                continue
            pose = robot_pose_from_mapdata(map_data)
        except Exception:  # noqa: BLE001 - a raising provider internal degrades to a miss
            continue
        diag["pose_at"] = mpath
        if not pose:
            continue
        return {
            "present": "robot_anchor" in pose or "dock_anchor" in pose,
            **pose,
            "diagnostics": diag,
        }
    return {"present": False, "reason": "no_parsed_map", "diagnostics": diag}


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

    # The moving pose, via the shared extractor — passing THIS projector so its health
    # counters cover the whole read. Not inlined: the live-pose accessor reads the same
    # fields, and two copies is how the card had a robot position the stall capture did not.
    out.update(robot_pose_from_mapdata(map_data, proj))

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

    # live:RB-PROJ-1. ALWAYS emitted, including the all-zero healthy case: the point
    # is that a consumer can tell "this layer is empty because there was nothing"
    # from "this layer is empty because every projection failed". An absent key
    # would just move the ambiguity one level up.
    out["projector"] = _note_projector_health(proj)
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
    domain = source_cfg.get("hass_data_domain")
    out: list[tuple[str, str, Any]] = []
    if not domain:
        return out
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
    device_id: str | None = None,
) -> dict[str, Any]:
    """Find the fork's in-memory ``MapData`` OBJECT + a CHEAP content version, WITHOUT the
    ~180 KB base64 conversion.

    BFS for the holder of one of ``mapdata_attrs`` (e.g. ``_map_data``) whose value carries a
    bytes ``room_pixels`` raster; the version is sha1 of the RAW raster bytes. Lets the hot
    map_state_source path cache-check the version and only do the (expensive) dict conversion +
    per-room scan on a genuine re-map. Returns ``{present, obj, version, diagnostics}``; the
    absent marker on a miss. NEVER RAISES — runs on the event loop.

    RP-026/LC-1/EXT-1: with two-plus coordinators (two vacuums on the fork), the walk
    used to return the FIRST holder with a raster regardless of which vacuum asked —
    the second vacuum silently got the first's floorplan. ``device_id``, when given,
    requires the SAME object that carries the raster to also carry a matching
    ``device_id`` attribute (the fork's coordinator shape — verified live: a
    coordinator carries both ``device_id`` and ``_map_data`` directly). Omitted (the
    single-coordinator/legacy call sites), the walk keeps today's first-hit
    behaviour — the fallback required_behavior(1) calls for when no linkage exists.
    A device_id given with no match is ABSENT (device_not_found), never a fallback
    to another device's map — silently serving the wrong robot's floorplan is
    exactly the defect being closed.
    """
    fa = field_attrs if isinstance(field_attrs, dict) else {}
    rp_name = fa.get("room_pixels", "room_pixels")
    ox_name = fa.get("origin_x", "origin_x")
    oy_name = fa.get("origin_y", "origin_y")
    res_name = fa.get("res", "res")
    names = mapdata_attrs or ["_map_data", "map_data"]
    diag: dict[str, Any] = {"candidates": [c[0] + ":" + c[1] for c in candidates]}

    def _holds_mapdata(o: Any) -> bool:
        # Cheap predicate: an object exposing a MapData with a bytes raster (no convert).
        if device_id is not None and getattr(o, "device_id", None) != device_id:
            return False
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
                    # EXT-2 (RP-026): the raster alone doesn't say where those pixels
                    # SIT — a re-map to the same room shapes at a new origin/resolution
                    # is a real content change the cache must not treat as a hit.
                    geometry = (
                        getattr(v, ox_name, None),
                        getattr(v, oy_name, None),
                        getattr(v, res_name, None),
                    )
                    version = hashlib.sha1(
                        bytes(rp) + repr(geometry).encode("utf-8")
                    ).hexdigest()[:12]
                    diag["mapdata_at"] = f"{origin}:{key}:{path}.{a}"
                    return {"present": True, "obj": v, "version": version, "diagnostics": diag}
        except Exception:  # noqa: BLE001 - a raising provider internal degrades to a miss
            continue

    if device_id is not None:
        return {"present": False, "reason": "device_not_found", "diagnostics": diag}
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
    domain = source_cfg.get("hass_data_domain")
    out: list[tuple[str, str, Any]] = []
    if image_entity_id:
        ent = image_entity_object(hass, image_entity_id)
        if ent is not None:
            out.append(("image_entity", image_entity_id, ent))
    if domain:
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
