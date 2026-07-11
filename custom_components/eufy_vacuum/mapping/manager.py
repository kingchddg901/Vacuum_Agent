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

    def _vacuum_www_dir(self, vacuum_entity_id: str) -> Path:
        """Return the browser-served per-vacuum mapping directory."""
        path = Path(self.hass.config.config_dir) / MAPPING_WWW_ROOT / _vacuum_slug(vacuum_entity_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _map_json_path(self, vacuum_entity_id: str, map_id: str) -> Path:
        return self._vacuum_dir(vacuum_entity_id) / f"map_{map_id}.json"

    def _map_image_path(self, vacuum_entity_id: str, map_id: str, variant: str = "primary") -> Path:
        normalized = _normalize_image_variant(variant)
        suffix = "" if normalized == "primary" else f"_{normalized}"
        return self._vacuum_dir(vacuum_entity_id) / f"map_{map_id}{suffix}.png"

    def _map_image_www_path(self, vacuum_entity_id: str, map_id: str, variant: str = "primary") -> Path:
        normalized = _normalize_image_variant(variant)
        suffix = "" if normalized == "primary" else f"_{normalized}"
        return self._vacuum_www_dir(vacuum_entity_id) / f"map_{map_id}{suffix}.png"

    def _map_image_browser_url(self, vacuum_entity_id: str, map_id: str, variant: str = "primary") -> str:
        normalized = _normalize_image_variant(variant)
        suffix = "" if normalized == "primary" else f"_{normalized}"
        return f"/eufy_vacuum/maps/{_vacuum_slug(vacuum_entity_id)}/map_{map_id}{suffix}.png"

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

    def _normalize_room_definition(
        self,
        *,
        room_id: str,
        payload: Any,
        roster_lookup: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Return one normalized room definition entry."""
        source = dict(payload) if isinstance(payload, dict) else {}
        roster = roster_lookup.get(str(room_id), {})
        known_keys = {
            "room_id",
            "room_id_int",
            "room_label",
            "slug",
            "label",
            "custom_label",
            "display_label",
            "notes",
            "labels",
            "adjacent_room_ids",
            "zone_tags",
            "anchor_pixel",
            "anchor_vacuum",
            "color",
            "source",
            "confidence",
            "suggestion_segment_id",
            "added_at",
            "updated_at",
            "extras",
        }
        custom_label = _clean_text(source.get("custom_label") or source.get("label"))
        room_label = (
            _clean_text(source.get("room_label"))
            or _clean_text(roster.get("label"))
            or _display_label(roster.get("slug"))
            or str(room_id)
        )
        normalized = {
            "room_id": str(room_id),
            "room_id_int": _safe_int(room_id, 0) or None,
            "room_label": room_label,
            "slug": _clean_text(source.get("slug")) or _clean_text(roster.get("slug")),
            "custom_label": custom_label,
            "display_label": custom_label or room_label,
            "notes": _clean_text(source.get("notes")),
            "labels": _clean_string_list(source.get("labels")),
            "adjacent_room_ids": [
                str(item).strip()
                for item in source.get("adjacent_room_ids", [])
                if str(item).strip()
            ] if isinstance(source.get("adjacent_room_ids"), list) else [],
            "zone_tags": _clean_string_list(source.get("zone_tags")),
            "anchor_pixel": _normalize_point(source.get("anchor_pixel"), digits=2),
            "anchor_vacuum": _normalize_point(source.get("anchor_vacuum"), digits=4),
            "color": _clean_text(source.get("color")),
            "source": _clean_text(source.get("source")),
            "confidence": (
                round(_safe_float(source.get("confidence")), 4)
                if _safe_float(source.get("confidence")) is not None
                else None
            ),
            "suggestion_segment_id": _clean_text(
                source.get("suggestion_segment_id")
                or source.get("segment_id")
                or source.get("matched_segment_id")
            ),
            "added_at": _clean_text(source.get("added_at")),
            "updated_at": _clean_text(source.get("updated_at")),
            "extras": {},
        }
        normalized["extras"] = {
            key: value
            for key, value in source.items()
            if key not in known_keys and value is not None
        }
        return normalized

    def _normalize_trace_evidence_entry(
        self,
        *,
        entry: Any,
        roster_lookup: dict[str, dict[str, Any]],
        index: int,
    ) -> dict[str, Any]:
        """Return one normalized trace evidence entry."""
        source = dict(entry) if isinstance(entry, dict) else {}
        room_id = _clean_text(source.get("room_id"))
        roster = roster_lookup.get(str(room_id), {}) if room_id else {}
        kind = _clean_text(source.get("kind") or source.get("type"))
        evidence_id = (
            _clean_text(source.get("evidence_id"))
            or _clean_text(source.get("id"))
            or f"evidence_{index + 1}"
        )
        known_keys = {
            "evidence_id",
            "id",
            "kind",
            "type",
            "kind_label",
            "label",
            "room_id",
            "room_label",
            "source",
            "summary",
            "notes",
            "image_source",
            "confidence",
            "added_at",
            "extras",
        }
        normalized = {
            "evidence_id": evidence_id,
            "kind": kind,
            "kind_label": _display_label(kind),
            "label": _clean_text(source.get("label")),
            "room_id": room_id,
            "room_label": (
                _clean_text(source.get("room_label"))
                or _clean_text(roster.get("label"))
                or _display_label(roster.get("slug"))
                or None
            ),
            "source": _clean_text(source.get("source")),
            "summary": _clean_text(source.get("summary")),
            "notes": _clean_text(source.get("notes")),
            "image_source": _clean_text(source.get("image_source")),
            "confidence": (
                round(_safe_float(source.get("confidence")), 4)
                if _safe_float(source.get("confidence")) is not None
                else None
            ),
            "added_at": _clean_text(source.get("added_at")) or _iso_now(),
            "extras": {},
        }
        normalized["extras"] = {
            key: value
            for key, value in source.items()
            if key not in known_keys and value is not None
        }
        return normalized

    def _normalize_mapping_package(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        package: Any,
        map_data: dict[str, Any] | None = None,
        active_traces: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return one normalized mapping package."""
        source = dict(package) if isinstance(package, dict) else {}
        base = self._default_mapping_package()
        merged = _deep_merge_dict(base, source)

        map_snapshot = map_data if isinstance(map_data, dict) else self._ensure_map_data(vacuum_entity_id, map_id)
        roster = self._mapping_room_roster(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            map_data=map_snapshot,
            active_traces=active_traces or [],
        )
        roster_lookup = {str(item.get("room_id")): item for item in roster if item.get("room_id") is not None}

        room_definitions_source = merged.get("room_definitions", {})
        room_definitions_raw = room_definitions_source if isinstance(room_definitions_source, dict) else {}
        normalized_room_definitions = {
            str(room_id): self._normalize_room_definition(
                room_id=str(room_id),
                payload=value,
                roster_lookup=roster_lookup,
            )
            for room_id, value in room_definitions_raw.items()
        }
        segment_to_room_id: dict[str, str] = {}
        room_sort_keys = sorted(normalized_room_definitions.keys())
        for room_id in room_sort_keys:
            definition = normalized_room_definitions.get(room_id, {})
            if not isinstance(definition, dict):
                continue
            segment_id = str(definition.get("suggestion_segment_id") or "").strip()
            if not segment_id:
                continue
            previous_room_id = segment_to_room_id.get(segment_id)
            if previous_room_id is None:
                segment_to_room_id[segment_id] = room_id
                continue
            normalized_room_definitions[room_id] = {
                **definition,
                "suggestion_segment_id": None,
            }

        trace_source = merged.get("trace_evidence", [])
        trace_raw = trace_source if isinstance(trace_source, list) else []
        normalized_trace = [
            self._normalize_trace_evidence_entry(
                entry=value,
                roster_lookup=roster_lookup,
                index=index,
            )
            for index, value in enumerate(trace_raw)
        ]
        segment_adjustments = _normalize_segment_adjustments(merged.get("segment_adjustments"))

        image = merged.get("image", {})
        if not isinstance(image, dict):
            image = {}
        images_raw = merged.get("images", {})
        if not isinstance(images_raw, dict):
            images_raw = {}
        data_variants = map_snapshot.get("image_variants", {})
        if not isinstance(data_variants, dict):
            data_variants = {}

        merged_variants: dict[str, Any] = {}
        for key, value in data_variants.items():
            merged_variants[_normalize_image_variant(key)] = value
        for key, value in images_raw.items():
            merged_variants[_normalize_image_variant(key)] = value
        if "primary" not in merged_variants:
            legacy_image_path = _clean_text(map_snapshot.get("image_path"))
            legacy_image_source = _clean_text(image.get("source"))
            if legacy_image_path or legacy_image_source:
                merged_variants["primary"] = {
                    "variant": "primary",
                    "role": "primary",
                    "image_path": legacy_image_path,
                    "source": legacy_image_source,
                    "width": map_snapshot.get("image_width"),
                    "height": map_snapshot.get("image_height"),
                    "notes": _clean_text(image.get("notes")),
                }

        normalized_images: dict[str, dict[str, Any]] = {}
        for key, value in merged_variants.items():
            source_variant = dict(value) if isinstance(value, dict) else {}
            normalized_images[key] = {
                "variant": key,
                "role": _clean_text(source_variant.get("role")) or _image_variant_role(key),
                "source": _clean_text(source_variant.get("source")),
                "image_path": _clean_text(source_variant.get("image_path")),
                "width": _safe_int(source_variant.get("width"), 0) or None,
                "height": _safe_int(source_variant.get("height"), 0) or None,
                "notes": _clean_text(source_variant.get("notes")),
            }

        primary_variant = _normalize_image_variant(image.get("variant") or "primary")
        primary_entry = normalized_images.get(primary_variant) or normalized_images.get("primary")
        primary_source = _clean_text(image.get("source")) or (primary_entry.get("source") if isinstance(primary_entry, dict) else None)
        primary_notes = _clean_text(image.get("notes")) or (primary_entry.get("notes") if isinstance(primary_entry, dict) else None)
        dock = merged.get("dock", {})
        if not isinstance(dock, dict):
            dock = {}

        normalized = {
            "schema_version": 2,
            "updated_at": _clean_text(merged.get("updated_at")),
            "image": {
                "source": primary_source,
                "variant": primary_variant,
                "notes": primary_notes,
            },
            "images": normalized_images,
            "dock": {
                "room_id": _clean_text(dock.get("room_id")),
                "pixel": _normalize_point(dock.get("pixel"), digits=2),
                "vacuum": _normalize_point(dock.get("vacuum"), digits=4),
                "exclusion_radius": (
                    round(_safe_float(dock.get("exclusion_radius")), 2)
                    if _safe_float(dock.get("exclusion_radius")) is not None
                    else None
                ),
                "notes": _clean_text(dock.get("notes")),
            },
            "room_definitions": normalized_room_definitions,
            "room_definitions_list": list(normalized_room_definitions.values()),
            "segment_adjustments": segment_adjustments,
            "trace_evidence": normalized_trace[-100:],
            "trace_evidence_count": len(normalized_trace),
            "notes": merged.get("notes", []) if isinstance(merged.get("notes"), list) else [],
        }
        return normalized

    def _managed_map_rooms(
        self,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Return runtime-managed room config for one vacuum/map if available."""
        try:
            runtime = self.hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
            data = getattr(runtime, "data", {}) if runtime is not None else {}
            rooms = (
                data.get("maps", {})
                .get(vacuum_entity_id, {})
                .get(str(map_id), {})
                .get("rooms", {})
            )
            return rooms if isinstance(rooms, dict) else {}
        except Exception:
            return {}

    def _mapping_room_roster(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        map_data: dict[str, Any],
        active_traces: list[str],
    ) -> list[dict[str, Any]]:
        """Return one room roster covering all known map rooms plus mapping status."""
        package = map_data.get("package", self._default_mapping_package())
        if not isinstance(package, dict):
            package = self._default_mapping_package()
        dock = package.get("dock", {})
        dock_room_id = str(dock.get("room_id")) if isinstance(dock, dict) and dock.get("room_id") is not None else None

        mapping_rooms = map_data.get("rooms", {})
        if not isinstance(mapping_rooms, dict):
            mapping_rooms = {}

        managed_rooms = self._managed_map_rooms(vacuum_entity_id, map_id)
        room_ids: set[str] = set(managed_rooms.keys()) | set(mapping_rooms.keys())

        entries: list[dict[str, Any]] = []
        for room_id in room_ids:
            managed = managed_rooms.get(str(room_id), {}) if isinstance(managed_rooms, dict) else {}
            mapped = mapping_rooms.get(str(room_id), {}) if isinstance(mapping_rooms, dict) else {}

            raw_name = managed.get("name")
            raw_slug = managed.get("slug")
            room_label = str(raw_name).strip() if str(raw_name or "").strip() else _display_label(raw_slug) or str(room_id)

            floor_type = str(managed.get("floor_type") or "").strip().lower() or None
            boundary = mapped.get("boundary", [])

            entries.append(
                {
                    "room_id": str(room_id),
                    "room_id_int": _safe_int(room_id, 0) or None,
                    "name": str(raw_name).strip() if str(raw_name or "").strip() else None,
                    "label": room_label,
                    "slug": str(raw_slug).strip() if str(raw_slug or "").strip() else None,
                    "order": _safe_int(managed.get("order"), 0),
                    "enabled": bool(managed.get("enabled", True)),
                    "floor_type": floor_type,
                    "floor_type_label": get_floor_type_label(floor_type) if floor_type else None,
                    "carpet": str(floor_type or "").startswith("carpet"),
                    "has_boundary": bool(boundary),
                    "boundary_point_count": len(boundary),
                    "traced_at": mapped.get("traced_at"),
                    "is_active_trace": str(room_id) in active_traces,
                    "is_dock_room": dock_room_id is not None and str(room_id) == dock_room_id,
                    "transition_candidate": bool(mapped.get("transition_candidate", False)),
                    "transition_score": float(mapped.get("transition_score", 0.0)),
                    "is_transition": bool(managed.get("is_transition", False)),
                    "bounds": mapped.get("bounds"),
                    "has_bounds": bool(mapped.get("bounds")),
                    "bounds_run_count": int((mapped.get("bounds") or {}).get("run_count", 0)),
                }
            )

        return sorted(
            entries,
            key=lambda item: (
                int(item.get("order") or 0),
                str(item.get("label") or ""),
                str(item.get("room_id") or ""),
            ),
        )

    # ------------------------------------------------------------------
    # Map image
    # ------------------------------------------------------------------

    def save_map_image(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        image_base64: str,
        image_width: int | None = None,
        image_height: int | None = None,
        variant: str = "primary",
    ) -> dict[str, Any]:
        """Save a base64-encoded PNG map image to the filesystem.

        Parameters
        ----------
        image_base64: base64-encoded PNG bytes
        image_width/height: pixel dimensions of the image (optional)
        """
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            return {"saved": False, "reason": f"invalid_base64: {exc}"}

        normalized_variant = _normalize_image_variant(variant)
        image_path = self._map_image_path(vacuum_entity_id, map_id, normalized_variant)
        image_www_path = self._map_image_www_path(vacuum_entity_id, map_id, normalized_variant)
        browser_url = self._map_image_browser_url(vacuum_entity_id, map_id, normalized_variant)
        image_path.write_bytes(image_bytes)
        image_www_path.write_bytes(image_bytes)

        data = self._ensure_map_data(vacuum_entity_id, map_id)
        variants = data.get("image_variants", {})
        if not isinstance(variants, dict):
            variants = {}
        variants[normalized_variant] = {
            "variant": normalized_variant,
            "role": _image_variant_role(normalized_variant),
            "image_path": str(image_path),
            "source": browser_url,
            "width": int(image_width) if image_width is not None else None,
            "height": int(image_height) if image_height is not None else None,
            "notes": (
                "Dark theme map capture"
                if normalized_variant == "dark"
                else "Light theme map capture"
                if normalized_variant == "light"
                else None
            ),
        }
        data["image_variants"] = variants

        # WHY: legacy top-level image_path/width/height fields are maintained for
        # callers that haven't migrated to image_variants yet.
        legacy_variant = "primary" if "primary" in variants else normalized_variant
        legacy_image = variants.get(legacy_variant, {})
        data["image_path"] = legacy_image.get("image_path")
        data["image_width"] = legacy_image.get("width")
        data["image_height"] = legacy_image.get("height")
        package = data.get("package", self._default_mapping_package())
        if not isinstance(package, dict):
            package = self._default_mapping_package()
        image_meta = package.get("image", {})
        if not isinstance(image_meta, dict):
            image_meta = {}
        image_meta["source"] = legacy_image.get("source")
        image_meta["variant"] = legacy_variant
        package["image"] = image_meta
        images_meta = package.get("images", {})
        if not isinstance(images_meta, dict):
            images_meta = {}
        images_meta[normalized_variant] = dict(variants[normalized_variant])
        package["images"] = images_meta
        package["updated_at"] = _iso_now()
        data["package"] = self._normalize_mapping_package(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            package=package,
            map_data=data,
        )

        self._save_map_data(vacuum_entity_id, map_id, data)

        return {
            "saved": True,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "variant": normalized_variant,
            "image_path": str(image_path),
            "image_url": browser_url,
            "file_bytes": len(image_bytes),
        }

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

