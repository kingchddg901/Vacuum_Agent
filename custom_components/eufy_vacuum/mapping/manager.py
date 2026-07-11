"""Orchestrates all mapping operations: boundary tracing, bounds learning, and the trace-based transform pipeline."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import DATA_RUNTIME, DOMAIN
from ..entity_helpers import get_floor_type_label
from ..timestamp_utils import utc_now_iso
from ..adapters.registry import get_adapter_config
from .boundary import point_in_polygon
from .segmenter_engines import get_segmenter_engine


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAPPING_ROOT = "eufy_vacuum/mapping"
MAPPING_WWW_ROOT = "eufy_vacuum/maps"
_ISO_FMT = "%Y-%m-%dT%H:%M:%S"
TRACE_ARM_INSIDE_HITS = 3
TRACE_PREARM_BUFFER_LIMIT = 12

# Bounding box margin (vacuum units) added on all sides for presence detection.
BOUNDS_MARGIN = 50.0

# Minimum active runs before a room's attributed samples are saved in a
# multi-room job. Below this the room traps samples to prevent bleed into
# neighbours but nothing is written back. Must match tracker.MULTI_ROOM_MIN_RUNS.
MULTI_ROOM_MIN_RUNS = 4

# Minimum sample count before applying percentile trimming.
# Below this threshold all samples are kept as-is.
_TRIM_MIN_SAMPLES = 10

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return utc_now_iso()


def _vacuum_slug(vacuum_entity_id: str) -> str:
    if "." in vacuum_entity_id:
        return vacuum_entity_id.split(".", 1)[1].strip().lower()
    return str(vacuum_entity_id).strip().lower()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except Exception:
        return default


def _deep_merge_dict(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mapping package updates into a base dict."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _display_label(value: Any) -> str | None:
    """Return a basic human-readable label for slug-like values."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("_", " ").replace("-", " ")
    collapsed = " ".join(part for part in normalized.split() if part)
    if not collapsed:
        return None
    return " ".join(part.capitalize() for part in collapsed.split())


def _clean_text(value: Any) -> str | None:
    """Return a stripped string or None."""
    text = str(value or "").strip()
    return text or None


def _percentile_trim(
    samples: list[tuple[float, float]],
    p_lo: float = 0.10,
    p_hi: float = 0.90,
) -> list[tuple[float, float]]:
    """Return samples trimmed to the P10–P90 range on each axis independently.

    Trims the outermost 10 % of the X distribution and the outermost 10 % of
    the Y distribution. A point is kept only if it survives both cuts.

    Below _TRIM_MIN_SAMPLES the raw list is returned unchanged — there is not
    enough data to compute meaningful percentiles.
    """
    if len(samples) < _TRIM_MIN_SAMPLES:
        return samples

    xs = sorted(vx for vx, _ in samples)
    ys = sorted(vy for _, vy in samples)
    n = len(xs)

    lo_i = int(n * p_lo)
    hi_i = min(int(n * p_hi), n - 1)

    x_lo, x_hi = xs[lo_i], xs[hi_i]
    y_lo, y_hi = ys[lo_i], ys[hi_i]

    return [
        (vx, vy)
        for vx, vy in samples
        if x_lo <= vx <= x_hi and y_lo <= vy <= y_hi
    ]


def _clean_string_list(value: Any) -> list[str]:
    """Return a compact list of non-empty strings."""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text:
            items.append(text)
    return items


def _normalize_point(value: Any, digits: int = 2) -> list[float] | None:
    """Return a rounded 2D point list or None."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return [round(float(value[0]), digits), round(float(value[1]), digits)]
    except Exception:
        return None


def _normalize_image_variant(value: Any) -> str:
    text = str(value or "primary").strip().lower().replace(" ", "_").replace("-", "_")
    return text or "primary"


def _image_variant_role(variant: str) -> str:
    normalized = _normalize_image_variant(variant)
    if normalized == "dark":
        return "segmentation"
    if normalized == "light":
        return "boundary"
    return "primary"


def _normalize_segment_adjustments(value: Any) -> dict[str, dict[str, Any]]:
    """Return persisted per-segment translation, edge, and vertex adjustments."""
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_segment_id, raw_payload in value.items():
        segment_id = str(raw_segment_id or "").strip()
        if not segment_id:
            continue
        payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
        offset_x = _safe_int(payload.get("offset_x"), 0)
        offset_y = _safe_int(payload.get("offset_y"), 0)
        edge_left = _safe_int(payload.get("edge_left"), 0)
        edge_right = _safe_int(payload.get("edge_right"), 0)
        edge_top = _safe_int(payload.get("edge_top"), 0)
        edge_bottom = _safe_int(payload.get("edge_bottom"), 0)
        vertex_moves_raw = payload.get("vertex_moves")
        vertex_moves: list[dict[str, int]] = []
        if isinstance(vertex_moves_raw, list):
            for item in vertex_moves_raw:
                if not isinstance(item, dict):
                    continue
                index = _safe_int(item.get("index"), -1)
                delta_x = _safe_int(item.get("delta_x"), 0)
                delta_y = _safe_int(item.get("delta_y"), 0)
                if index < 0 or not any((delta_x, delta_y)):
                    continue
                vertex_moves.append({
                    "index": index,
                    "delta_x": delta_x,
                    "delta_y": delta_y,
                })
        if not any((offset_x, offset_y, edge_left, edge_right, edge_top, edge_bottom)) and not vertex_moves:
            continue
        normalized[segment_id] = {
            "offset_x": offset_x,
            "offset_y": offset_y,
            "edge_left": edge_left,
            "edge_right": edge_right,
            "edge_top": edge_top,
            "edge_bottom": edge_bottom,
            "vertex_moves": vertex_moves,
            "updated_at": _clean_text(payload.get("updated_at")) or _iso_now(),
        }
    return normalized


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class MappingManager:
    """Manages boundary tracing, trace capture, and image storage per vacuum/map.

    Active boundary traces are stored in memory only — they are not persisted
    until close_room_boundary is called.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager, setting up filesystem paths and in-memory session state."""
        self.hass = hass
        self._base_dir = Path(hass.config.config_dir) / MAPPING_ROOT

    def _vacuum_dir(self, vacuum_entity_id: str) -> Path:
        """Return (and create) the per-vacuum mapping directory."""
        path = self._base_dir / _vacuum_slug(vacuum_entity_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _map_json_path(self, vacuum_entity_id: str, map_id: str) -> Path:
        return self._vacuum_dir(vacuum_entity_id) / f"map_{map_id}.json"

    def _load_map_data(self, vacuum_entity_id: str, map_id: str) -> dict[str, Any]:
        """Load map JSON from filesystem, returning empty dict if absent.

        Strips the legacy ``calibration`` block (System A — affine-transform
        calibration) if encountered, resaving the file once so the legacy
        data is purged on first read.

        This is a one-way migration: System A was removed, so the block is
        pure dead weight in any map file written before then. Safe to retire
        a few releases out, once installs in the wild have all been re-saved
        at least once and no longer carry a ``calibration`` key.
        """
        path = self._map_json_path(vacuum_entity_id, map_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if isinstance(data, dict) and "calibration" in data:
            _LOGGER.info(  # pragma: no cover
                "Stripping legacy calibration block from map_data for %s/%s",
                vacuum_entity_id,
                map_id,
            )
            data.pop("calibration", None)
            try:
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:  # pragma: no cover - best-effort one-shot migration resave
                _LOGGER.exception(
                    "Failed to resave map_data after stripping calibration block: %s",
                    path,
                )

        return data

    def _save_map_data(
        self, vacuum_entity_id: str, map_id: str, data: dict[str, Any]
    ) -> None:
        """Save map JSON to filesystem."""
        path = self._map_json_path(vacuum_entity_id, map_id)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _ensure_map_data(
        self, vacuum_entity_id: str, map_id: str
    ) -> dict[str, Any]:
        """Return map data, initializing defaults if absent."""
        data = self._load_map_data(vacuum_entity_id, map_id)
        data.setdefault("rooms", {})
        data.setdefault("image_path", None)
        data.setdefault("image_width", None)
        data.setdefault("image_height", None)
        data.setdefault("image_variants", {})
        data.setdefault("package", self._default_mapping_package())
        return data

    def _default_mapping_package(self) -> dict[str, Any]:
        """Return the richer mapping package container."""
        return {
            "schema_version": 3,
            "updated_at": None,
            "image": {
                "source": None,
                "variant": "primary",
                "notes": None,
            },
            "images": {},
            "dock": {
                "room_id": None,
                "pixel": None,
                "vacuum": None,
                "exclusion_radius": None,
                "notes": None,
            },
            "room_definitions": {},
            "segment_adjustments": {},
            "trace_evidence": [],
            "notes": [],
        }

    # ------------------------------------------------------------------
    # Map image
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Bounding box room presence
    # ------------------------------------------------------------------

    def update_room_bounds(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        samples: list[tuple[float, float]],
        rooms: dict[str, Any],
        dock_anchor_start: list[float] | None = None,
        dock_anchor_end: list[float] | None = None,
    ) -> None:
        """Attribute position samples from a completed job to room bounding boxes.

        Attribution strategy
        --------------------
        Single-room job (exactly one non-transition room in `rooms`):
          All samples belong to that room unconditionally.

        Multi-room job:
          Samples that fall within an existing room's bounding box (plus margin)
          are attributed to that room. Unattributed samples are discarded.

        Each room's stored bounds are updated with the new samples so that
        repeated runs progressively tighten and expand the box as needed.
        """
        if not samples:
            return

        non_transition = [
            rid for rid, rdata in rooms.items()
            if not rdata.get("is_transition", False)
        ]

        data = self._ensure_map_data(vacuum_entity_id, map_id)

        job_bounds: dict[str, Any] = {}

        if len(non_transition) == 1:
            room_id = str(non_transition[0])
            job_bounds[room_id] = self._update_bounds_for_room(
                data, room_id, _percentile_trim(samples),
                dock_anchor_start=dock_anchor_start,
                dock_anchor_end=dock_anchor_end,
            )
        else:
            map_rooms = data.get("rooms", {})
            attributed: dict[str, list[tuple[float, float]]] = {}
            for vx, vy in samples:
                for rid in non_transition:
                    existing_bounds = map_rooms.get(str(rid), {}).get("bounds")
                    if existing_bounds and self._point_in_bounds(
                        vx, vy, existing_bounds, BOUNDS_MARGIN
                    ):
                        attributed.setdefault(str(rid), []).append((vx, vy))
                        break

            for rid, room_samples in attributed.items():
                # WHY: rooms with fewer than MULTI_ROOM_MIN_RUNS active entries
                # are not yet trustworthy as attribution anchors.
                room_history = map_rooms.get(str(rid), {}).get("job_bounds_history", [])
                active_runs  = sum(1 for e in room_history if not e.get("excluded", False))
                if active_runs < MULTI_ROOM_MIN_RUNS:
                    _LOGGER.debug(
                        "update_room_bounds: skipping low-confidence room %s "
                        "(%d active runs, need %d) in multi-room job on map %s",
                        rid, active_runs, MULTI_ROOM_MIN_RUNS, map_id,
                    )
                    continue
                job_bounds[rid] = self._update_bounds_for_room(
                    data, rid, _percentile_trim(room_samples),
                    dock_anchor_start=dock_anchor_start,
                    dock_anchor_end=dock_anchor_end,
                )

        self._save_map_data(vacuum_entity_id, map_id, data)
        self._write_job_bounds(vacuum_entity_id, job_bounds)

    def _update_bounds_for_room(
        self,
        data: dict[str, Any],
        room_id: str,
        samples: list[tuple[float, float]],
        dock_anchor_start: list[float] | None = None,
        dock_anchor_end: list[float] | None = None,
    ) -> dict[str, Any]:
        """Add a job entry to the room's history and recompute bounds."""
        room_key = str(room_id)
        room_entry = data["rooms"].setdefault(room_key, {})
        history: list[dict[str, Any]] = room_entry.get("job_bounds_history", [])

        xs = [vx for vx, _ in samples]
        ys = [vy for _, vy in samples]
        job_min_x, job_max_x = min(xs), max(xs)
        job_min_y, job_max_y = min(ys), max(ys)
        now = _iso_now()

        # WHY: migrate legacy accumulated bounds into history on first use so
        # existing data isn't silently discarded when the room gets its first new job.
        if not history:
            existing = room_entry.get("bounds")
            if existing:
                history = [{
                    "min_x": existing["min_x"],
                    "max_x": existing["max_x"],
                    "min_y": existing["min_y"],
                    "max_y": existing["max_y"],
                    "cx": existing.get("cx", (existing["min_x"] + existing["max_x"]) / 2.0),
                    "cy": existing.get("cy", (existing["min_y"] + existing["max_y"]) / 2.0),
                    "sample_count": int(existing.get("sample_count", 0)),
                    "recorded_at": existing.get("updated_at", now),
                    "job_id": "pre_migration",
                    "excluded": False,
                }]

        job_id = "job_" + now[:16].replace(":", "-")  # job_YYYY-MM-DDTHH-MM

        job_entry: dict[str, Any] = {
            "min_x": job_min_x,
            "max_x": job_max_x,
            "min_y": job_min_y,
            "max_y": job_max_y,
            "cx": (job_min_x + job_max_x) / 2.0,
            "cy": (job_min_y + job_max_y) / 2.0,
            "sample_count": len(samples),
            "recorded_at": now,
            "job_id": job_id,
            "excluded": False,
            # Per-session dock anchors (Wave 1, capture-only) — the run's coordinate
            # frame origin (start) + re-dock position (end). Consumed by the Wave 2
            # cross-session re-anchor; harmless metadata until then.
            "dock_anchor_start": dock_anchor_start,
            "dock_anchor_end": dock_anchor_end,
        }

        history = [job_entry] + history
        history = history[:20]  # keep last 20
        room_entry["job_bounds_history"] = history
        room_entry["bounds"] = self._recompute_bounds_from_history(history)

        return job_entry

    @staticmethod
    def _recompute_bounds_from_history(
        history: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Union of all non-excluded job history entries."""
        active = [e for e in history if not e.get("excluded", False)]
        if not active:
            return None
        min_x = min(e["min_x"] for e in active)
        max_x = max(e["max_x"] for e in active)
        min_y = min(e["min_y"] for e in active)
        max_y = max(e["max_y"] for e in active)
        return {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "cx": (min_x + max_x) / 2.0,
            "cy": (min_y + max_y) / 2.0,
            "run_count": len(active),
            "sample_count": sum(e.get("sample_count", 0) for e in active),
            "updated_at": active[0].get("recorded_at", ""),
        }

    def get_room_bounds_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return accumulated room bounds and per-job history for every room."""
        data = self._ensure_map_data(vacuum_entity_id, map_id)
        rooms_raw = data.get("rooms", {})

        rooms: dict[str, Any] = {}
        for room_id, room_entry in rooms_raw.items():
            rooms[room_id] = {
                "bounds": room_entry.get("bounds"),
                "job_bounds_history": room_entry.get("job_bounds_history", []),
            }

        return {
            "available": True,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "rooms": rooms,
            "updated_at": _iso_now(),
        }

    def _write_job_bounds(
        self,
        vacuum_entity_id: str,
        job_bounds: dict[str, Any],
    ) -> None:
        """Write per-job bounds into the most recent learning job file."""
        if not job_bounds:
            return
        try:
            import re as _re
            slug = _re.sub(r"[^a-z0-9_]", "_", vacuum_entity_id.lower())
            jobs_dir = (
                Path(self.hass.config.config_dir)
                / "eufy_vacuum"
                / "learning"
                / slug
                / "jobs"
            )
            if not jobs_dir.is_dir():
                return
            job_files = sorted(jobs_dir.glob("job_*.json"), key=lambda p: p.stat().st_mtime)
            if not job_files:
                return
            job_path = job_files[-1]
            payload = json.loads(job_path.read_text(encoding="utf-8"))
            payload.setdefault("mapping", {})["room_bounds"] = job_bounds
            job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:  # pragma: no cover - best-effort I/O, logs and swallows
            _LOGGER.exception("MappingManager: failed to write job bounds to job file")

    @staticmethod
    def _point_in_bounds(
        vx: float,
        vy: float,
        bounds: dict[str, Any],
        margin: float = 0.0,
    ) -> bool:
        """Return True if (vx, vy) is inside bounds expanded by margin."""
        return (
            bounds["min_x"] - margin <= vx <= bounds["max_x"] + margin
            and bounds["min_y"] - margin <= vy <= bounds["max_y"] + margin
        )

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

