"""Service handlers for the Eufy Vacuum mapping module."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import time
from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DATA_RUNTIME,
    DOMAIN,
    SERVICE_ADJUST_MAP_SEGMENT,
    SERVICE_ANALYZE_MAP_IMAGE,
    SERVICE_GET_MAP_SEGMENTS,
    SERVICE_GET_MAP_RENDER_DATA,
    SERVICE_GET_MAP_LIVE_POSE,
    SERVICE_COMPARE_MAP_SOURCES,
    SERVICE_SET_COMPANION_ANCHOR,
    SERVICE_SET_HIDDEN_REGIONS,
    SERVICE_SET_AREA_LABEL_ANCHOR,
    SERVICE_SET_LIVE_MAP_ROTATION,
    SERVICE_SET_MAP_OVERLAY_VISIBILITY,
    SERVICE_SET_SEGMENT_ROOM_LINK,
    SERVICE_SET_SEGMENTATION_MODE,
    SERVICE_SET_CUSTOM_SEGMENTS,
    SERVICE_CREATE_CUSTOM_LAYOUT,
    SERVICE_RENAME_CUSTOM_LAYOUT,
    SERVICE_DELETE_CUSTOM_LAYOUT,
    SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
    SERVICE_SET_FURNISHED_ART_PLACEMENT,
    SERVICE_SET_FURNISHED_RENDER_MODE,
    SERVICE_SET_ROOM_VIEWPORT,
    SERVICE_UPLOAD_MAP_IMAGE,
    SERVICE_DELETE_MAP_IMAGE,
)
from ..maps.map_manager import ensure_map_bucket
from ..timestamp_utils import utc_now_iso
from .manager import MappingManager
from .map_source import (
    OVERLAY_VISIBILITY_DEFAULTS,
    resolve_furnished_render,
    resolve_overlay_visibility,
)
from .segment_primitives import polygon_area, rasterize_primitives
from .tracker import EVENT_BOUNDARY_SAVED

_LOGGER = logging.getLogger(__name__)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# ---------------------------------------------------------------------------
# Service names
# ---------------------------------------------------------------------------

SERVICE_SAVE_MAP_IMAGE             = "save_map_image"
SERVICE_START_ROOM_BOUNDARY_TRACE  = "start_room_boundary_trace"
SERVICE_CLOSE_ROOM_BOUNDARY        = "close_room_boundary"
SERVICE_CANCEL_ROOM_BOUNDARY_TRACE = "cancel_room_boundary_trace"
SERVICE_GET_MAPPING_STATE          = "get_mapping_state"
SERVICE_SAVE_MAPPING_PACKAGE       = "save_mapping_package"
SERVICE_APPEND_MAPPING_TRACE_EVIDENCE = "append_mapping_trace_evidence"
SERVICE_GET_MAPPING_PACKAGE        = "get_mapping_package"
SERVICE_GET_IMAGE_SEGMENT_SUGGESTIONS = "get_image_segment_suggestions"
SERVICE_TRANSLATE_IMAGE_SEGMENT    = "translate_image_segment"
SERVICE_SET_DOCK_ANCHOR            = "set_dock_anchor"
SERVICE_SET_DOCK_ROOM              = "set_dock_room"
SERVICE_GET_ROOM_BOUNDS_SNAPSHOT      = "get_room_bounds_snapshot"
SERVICE_CLEAR_ROOM_BOUNDS             = "clear_room_bounds"
SERVICE_EXCLUDE_ROOM_JOB_BOUNDS       = "exclude_room_job_bounds"
SERVICE_RESTORE_ROOM_JOB_BOUNDS       = "restore_room_job_bounds"
SERVICE_REBUILD_ROOM_BOUNDS           = "rebuild_room_bounds_from_archive"

# Trace capture (Phase 1)
SERVICE_START_TRACE_CAPTURE  = "start_trace_capture"
SERVICE_STOP_TRACE_CAPTURE   = "stop_trace_capture"
SERVICE_CANCEL_TRACE_CAPTURE = "cancel_trace_capture"

# Trace run review (Phase 2)
SERVICE_REVIEW_TRACE_RUN = "review_trace_run"

ALL_MAPPING_SERVICES = (
    SERVICE_SAVE_MAP_IMAGE,
    SERVICE_START_ROOM_BOUNDARY_TRACE,
    SERVICE_CLOSE_ROOM_BOUNDARY,
    SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
    SERVICE_GET_MAPPING_STATE,
    SERVICE_SAVE_MAPPING_PACKAGE,
    SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
    SERVICE_GET_MAPPING_PACKAGE,
    SERVICE_GET_IMAGE_SEGMENT_SUGGESTIONS,
    SERVICE_TRANSLATE_IMAGE_SEGMENT,
    SERVICE_SET_DOCK_ANCHOR,
    SERVICE_SET_DOCK_ROOM,
    SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
    SERVICE_CLEAR_ROOM_BOUNDS,
    SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
    SERVICE_RESTORE_ROOM_JOB_BOUNDS,
    SERVICE_REBUILD_ROOM_BOUNDS,
    # Trace capture
    SERVICE_START_TRACE_CAPTURE,
    SERVICE_STOP_TRACE_CAPTURE,
    SERVICE_CANCEL_TRACE_CAPTURE,
    # Trace run review
    SERVICE_REVIEW_TRACE_RUN,
    # Image analysis
    SERVICE_UPLOAD_MAP_IMAGE,
    SERVICE_DELETE_MAP_IMAGE,
    SERVICE_ANALYZE_MAP_IMAGE,
    SERVICE_GET_MAP_SEGMENTS,
    SERVICE_ADJUST_MAP_SEGMENT,
    # Map UI overlay state (segment→room links, companion anchors, hidden regions)
    SERVICE_SET_SEGMENT_ROOM_LINK,
    SERVICE_SET_COMPANION_ANCHOR,
    SERVICE_SET_HIDDEN_REGIONS,
    SERVICE_SET_AREA_LABEL_ANCHOR,
    SERVICE_SET_LIVE_MAP_ROTATION,
    SERVICE_SET_MAP_OVERLAY_VISIBILITY,
    SERVICE_GET_MAP_RENDER_DATA,
    SERVICE_GET_MAP_LIVE_POSE,
    SERVICE_COMPARE_MAP_SOURCES,
    # CV/Custom toggle + custom-segment authoring + named custom layouts
    SERVICE_SET_SEGMENTATION_MODE,
    SERVICE_SET_CUSTOM_SEGMENTS,
    SERVICE_CREATE_CUSTOM_LAYOUT,
    SERVICE_RENAME_CUSTOM_LAYOUT,
    SERVICE_DELETE_CUSTOM_LAYOUT,
    SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
    # Furnished custom render
    SERVICE_SET_FURNISHED_ART_PLACEMENT,
    SERVICE_SET_FURNISHED_RENDER_MODE,
    SERVICE_SET_ROOM_VIEWPORT,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

SAVE_MAP_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("image_base64"): cv.string,
        vol.Optional("image_width"): vol.Coerce(int),
        vol.Optional("image_height"): vol.Coerce(int),
        vol.Optional("variant", default="primary"): cv.string,
    }
)

START_ROOM_BOUNDARY_TRACE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
    }
)

CLOSE_ROOM_BOUNDARY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
        vol.Optional("epsilon", default=5.0): vol.Coerce(float),
    }
)

CANCEL_ROOM_BOUNDARY_TRACE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
    }
)

GET_MAPPING_STATE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
    }
)

GET_ROOM_BOUNDS_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
    }
)

CLEAR_ROOM_BOUNDS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
    }
)

EXCLUDE_ROOM_JOB_BOUNDS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
        vol.Required("job_index"): vol.Coerce(int),
    }
)

RESTORE_ROOM_JOB_BOUNDS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
        vol.Required("job_index"): vol.Coerce(int),
    }
)

REBUILD_ROOM_BOUNDS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
    }
)

SAVE_MAPPING_PACKAGE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("package"): dict,
    }
)

APPEND_MAPPING_TRACE_EVIDENCE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("evidence"): dict,
    }
)

GET_IMAGE_SEGMENT_SUGGESTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("min_area_pixels", default=1200): vol.Coerce(int),
        vol.Optional("simplify_epsilon"): vol.Coerce(float),
        vol.Optional("max_segments"): vol.Coerce(int),
    }
)

TRANSLATE_IMAGE_SEGMENT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("segment_id"): cv.string,
        vol.Optional("delta_x", default=0): vol.Coerce(int),
        vol.Optional("delta_y", default=0): vol.Coerce(int),
        vol.Optional("edge_left", default=0): vol.Coerce(int),
        vol.Optional("edge_right", default=0): vol.Coerce(int),
        vol.Optional("edge_top", default=0): vol.Coerce(int),
        vol.Optional("edge_bottom", default=0): vol.Coerce(int),
        vol.Optional(
            "vertex_moves",
            default=[],
        ): [
            {
                vol.Required("index"): vol.Coerce(int),
                vol.Optional("delta_x", default=0): vol.Coerce(int),
                vol.Optional("delta_y", default=0): vol.Coerce(int),
            }
        ],
    }
)

SET_DOCK_ANCHOR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("pixel_x"): vol.Coerce(float),
        vol.Required("pixel_y"): vol.Coerce(float),
        vol.Optional("vacuum_x"): vol.Coerce(float),
        vol.Optional("vacuum_y"): vol.Coerce(float),
        vol.Optional("exclusion_radius"): vol.Coerce(float),
        vol.Optional("notes"): cv.string,
    }
)

SET_DOCK_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): cv.string,
        vol.Optional("notes"): cv.string,
    }
)


# Trace capture schemas (Phase 1)
START_TRACE_CAPTURE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        # room_id is optional; room association is resolved in a later phase
        vol.Optional("room_id"): vol.Any(None, cv.string),
    }
)

STOP_TRACE_CAPTURE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
    }
)

CANCEL_TRACE_CAPTURE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
    }
)


# Trace run review schema (Phase 2)
REVIEW_TRACE_RUN_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("run_id"): cv.string,
        vol.Required("room_id"): cv.string,
        # Optional; adjusts accept thresholds based on polygon trustworthiness.
        # When absent, geometry-only thresholds apply.
        vol.Optional("segment_metadata"): vol.Any(None, dict),
    }
)


# Image analysis service schemas
#
# Image variants: "default"/"dark"/"light" are segmenter inputs (dark = primary,
# clearest room colours; light = assist, wall detection). "custom" is the
# manual-authoring backdrop for the no-CV custom-segment path — it is stored and
# served exactly like any other variant, but the segmenter never reads it
# (_handle_analyze_map_image only probes dark/default/light), so a custom-only
# map is never auto-segmented. Its recorded width/height are the pixel space the
# custom segment writer rasterises against.
def _image_variant(value):
    """Accept the four fixed variants plus per-layout ``custom_<id>`` backdrops."""
    value = cv.string(value)
    if value in ("default", "dark", "light", "custom") or value.startswith("custom_"):
        return value
    raise vol.Invalid(f"unknown image variant: {value}")


UPLOAD_MAP_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("image_base64"): cv.string,
        vol.Optional("variant", default="default"): _image_variant,
        vol.Optional("layout_id"): cv.string,
        vol.Optional("image_width"): vol.Coerce(int),
        vol.Optional("image_height"): vol.Coerce(int),
        # Furnished custom render (Wave 0): when set, the upload is furnished ART (not a
        # backdrop). The variant key is DERIVED from layout_id + scope (custom_<id>_home_art
        # or custom_<id>_room_<room_id>) and written onto the layout's home_art / rooms[*],
        # never onto backdrop_variant. Requires layout_id; "room" requires room_id.
        vol.Optional("art_scope"): vol.In(["home", "room"]),
        vol.Optional("room_id"): vol.Any(cv.string, vol.Coerce(int)),
    }
)

DELETE_MAP_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("variant", default="default"): _image_variant,
    }
)

ANALYZE_MAP_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("expected_room_count"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("max_segments"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("min_area_pixels"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("simplify_epsilon"): vol.Coerce(float),
        vol.Optional("force_reanalyze", default=False): cv.boolean,
    }
)

GET_MAP_SEGMENTS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
    }
)

# CV-or-Custom segmentation toggle. The handler only flips the flag — see the
# invariant in _handle_set_segmentation_mode (never re-runs the segmenter).
SET_SEGMENTATION_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("mode"): vol.In(["cv", "custom"]),
    }
)

# Author no-CV custom segments from a primitive list (replace-all). The handler
# rasterises each segment server-side (segment_primitives.rasterize_primitives).
SET_CUSTOM_SEGMENTS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("segments"): [
            vol.Schema(
                {
                    vol.Optional("id"): cv.string,
                    vol.Required("primitives"): list,
                },
                extra=vol.ALLOW_EXTRA,
            )
        ],
        # A live-image-backed layout has no uploaded backdrop, so the card sends the
        # rendered live image's natural pixel size for rasterisation (shapes +
        # stored polygons are pct; these dims only set the raster resolution/aspect).
        vol.Optional("backdrop_width"): vol.Coerce(int),
        vol.Optional("backdrop_height"): vol.Coerce(int),
    }
)

# Named custom layouts (a map can hold many — solar-system image, tree image, ...).
CREATE_CUSTOM_LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("name"): cv.string,
        # "live" pins the layout to the brand's live-map image as its backdrop.
        vol.Optional("backdrop_source"): cv.string,
    }
)

RENAME_CUSTOM_LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("layout_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)

DELETE_CUSTOM_LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("layout_id"): cv.string,
    }
)

SET_ACTIVE_CUSTOM_LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        # null / omitted -> auto-create + activate a default layout.
        vol.Optional("layout_id"): vol.Any(None, cv.string),
    }
)

ADJUST_MAP_SEGMENT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("segment_id"): cv.string,
        vol.Optional("delta_x", default=0): vol.Coerce(int),
        vol.Optional("delta_y", default=0): vol.Coerce(int),
        vol.Optional("edge_left", default=0): vol.Coerce(int),
        vol.Optional("edge_right", default=0): vol.Coerce(int),
        vol.Optional("edge_top", default=0): vol.Coerce(int),
        vol.Optional("edge_bottom", default=0): vol.Coerce(int),
        vol.Optional("vertex_moves", default=[]): [
            {
                vol.Required("index"): vol.Coerce(int),
                vol.Optional("delta_x", default=0): vol.Coerce(int),
                vol.Optional("delta_y", default=0): vol.Coerce(int),
            }
        ],
    }
)

SET_SEGMENT_ROOM_LINK_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("segment_id"): cv.string,
        # Pass null / omit to clear the link.
        vol.Optional("room_id"): vol.Any(None, cv.string, vol.Coerce(int)),
    }
)

SET_COMPANION_ANCHOR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Any(cv.string, vol.Coerce(int)),
        # Pass null / omit pct_x AND pct_y to clear the anchor.
        vol.Optional("pct_x"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("pct_y"): vol.Any(None, vol.Coerce(float)),
    }
)

# Replace-all the per-map HIDDEN REGIONS (drawn rects that mask map noise). The handler
# sanitizes each entry, so the schema only needs the list shape; an empty/omitted list clears.
SET_HIDDEN_REGIONS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Optional("regions", default=list): list,
    }
)

# Per-room AREA-LABEL position (the m² chip), so the user can drag it off the room-name label.
# Same shape as the companion anchor; null pct_x AND pct_y resets to the default (room centre).
SET_AREA_LABEL_ANCHOR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional("pct_x"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("pct_y"): vol.Any(None, vol.Coerce(float)),
    }
)

# Furnished custom render (Wave 0). All three write onto the ACTIVE custom layout.
#
# Furnished-art placement transform — the rotated-rect placement {tx,ty,scale,rotation}
# (pct floats, resolution-independent) applied to the art element only. scope "home" =
# the layout's whole-home art; "room" = a per-room override (room_id required). Pass all
# of tx/ty/scale/rotation null (or omit them) to CLEAR the placement.
SET_FURNISHED_ART_PLACEMENT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("scope"): vol.In(["home", "room"]),
        vol.Optional("room_id"): vol.Any(None, cv.string, vol.Coerce(int)),
        vol.Optional("tx"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("ty"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("scale"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("rotation"): vol.Any(None, vol.Coerce(float)),
    }
)

# Furnished render mode — live | art | blend. room_id null/omitted = the layout-level
# default; otherwise the per-room override.
SET_FURNISHED_RENDER_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("mode"): vol.In(["live", "art", "blend"]),
        vol.Optional("room_id"): vol.Any(None, cv.string, vol.Coerce(int)),
    }
)

# Saved per-room viewport (framing) — {cx,cy,zoom} (pct floats). Pass all of cx/cy/zoom
# null (or omit them) to CLEAR the saved viewport.
SET_ROOM_VIEWPORT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("room_id"): vol.Any(cv.string, vol.Coerce(int)),
        vol.Optional("cx"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("cy"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("zoom"): vol.Any(None, vol.Coerce(float)),
    }
)


SET_LIVE_MAP_ROTATION_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("map_id"): cv.string,
        vol.Required("rotation"): vol.All(vol.Coerce(int), vol.In([0, 90, 180, 270])),
    }
)

SET_MAP_OVERLAY_VISIBILITY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        # Optional — blank/absent auto-resolves to the active map (then the first
        # stored map), like the dashboard-snapshot service.
        vol.Optional("map_id"): cv.string,
        # Partial map of overlay-layer -> bool, merged over the stored deltas. Keys
        # are validated against the known layers so a typo is rejected, not silently
        # stored. Omitted entirely on a reset.
        vol.Optional("visibility"): vol.Schema(
            {vol.In(tuple(OVERLAY_VISIBILITY_DEFAULTS)): cv.boolean}
        ),
        # Clear all stored deltas -> fall back to the defaults.
        vol.Optional("reset", default=False): cv.boolean,
    }
)

GET_MAP_RENDER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_mapping_manager(hass: HomeAssistant) -> MappingManager:
    manager = hass.data.get(DOMAIN, {}).get("mapping_manager")
    if manager is None:
        raise HomeAssistantError("Mapping manager not available")
    return manager


def _get_room_name(hass: HomeAssistant, vacuum_entity_id: str, map_id: str, room_id: str) -> str:
    """Return room name from integration storage if available."""
    try:
        core = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if core is None:
            return str(room_id)
        result = core.get_managed_rooms(vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))
        return str(result.get("rooms", {}).get(str(room_id), {}).get("name", room_id))
    except Exception:
        return str(room_id)


# ---------------------------------------------------------------------------
# Polygon math helpers
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bbox_from_polygon_pixel(polygon: list[list[int]]) -> dict[str, int] | None:
    if not polygon:
        return None
    xs = [int(p[0]) for p in polygon]
    ys = [int(p[1]) for p in polygon]
    if not xs or not ys:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "x": min_x,
        "y": min_y,
        "width": max(1, max_x - min_x),
        "height": max(1, max_y - min_y),
    }


def _adjust_polygon_pixel(
    polygon: Any,
    *,
    offset_x: int,
    offset_y: int,
    edge_left: int,
    edge_right: int,
    edge_top: int,
    edge_bottom: int,
    vertex_moves: list[dict[str, int]] | None = None,
) -> list[list[int]]:
    """Return polygon adjusted by whole-shape translation, edge nudges, and vertex deltas."""
    if not isinstance(polygon, list):
        return []
    parsed: list[list[int]] = []
    for point in polygon:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        try:
            parsed.append([int(round(float(point[0]))), int(round(float(point[1])))])
        except Exception:
            continue
    if not parsed:
        return []

    xs = [p[0] for p in parsed]
    ys = [p[1] for p in parsed]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(1, max_x - min_x)
    height = max(1, max_y - min_y)
    band_x = max(2, int(round(width * 0.1)))
    band_y = max(2, int(round(height * 0.1)))

    translated: list[list[int]] = []
    for point in parsed:
        x = point[0] + offset_x
        y = point[1] + offset_y
        if point[0] <= (min_x + band_x):
            x += edge_left
        if point[0] >= (max_x - band_x):
            x += edge_right
        if point[1] <= (min_y + band_y):
            y += edge_top
        if point[1] >= (max_y - band_y):
            y += edge_bottom
        translated.append([int(round(x)), int(round(y))])

    if translated and isinstance(vertex_moves, list):
        for move in vertex_moves:
            if not isinstance(move, dict):
                continue
            idx = _safe_int(move.get("index"), -1)
            if idx < 0 or idx >= len(translated):
                continue
            translated[idx][0] += _safe_int(move.get("delta_x"))
            translated[idx][1] += _safe_int(move.get("delta_y"))

    return translated


def _apply_segment_adjustments(
    segments: list[dict[str, Any]],
    adjustments: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply stored per-segment adjustments to a list of raw segments."""
    if not adjustments:
        return segments
    result: list[dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            result.append(seg)
            continue
        seg_id = str(seg.get("segment_id") or "").strip()
        adj = adjustments.get(seg_id)
        if not seg_id or not isinstance(adj, dict):
            result.append(seg)
            continue

        offset_x = _safe_int(adj.get("offset_x"))
        offset_y = _safe_int(adj.get("offset_y"))
        edge_left = _safe_int(adj.get("edge_left"))
        edge_right = _safe_int(adj.get("edge_right"))
        edge_top = _safe_int(adj.get("edge_top"))
        edge_bottom = _safe_int(adj.get("edge_bottom"))
        vertex_moves = adj.get("vertex_moves") if isinstance(adj.get("vertex_moves"), list) else []

        if not any((offset_x, offset_y, edge_left, edge_right, edge_top, edge_bottom)) and not vertex_moves:
            result.append(seg)
            continue

        updated = dict(seg)
        polygon = _adjust_polygon_pixel(
            updated.get("polygon_pixel"),
            offset_x=offset_x,
            offset_y=offset_y,
            edge_left=edge_left,
            edge_right=edge_right,
            edge_top=edge_top,
            edge_bottom=edge_bottom,
            vertex_moves=vertex_moves,
        )
        if polygon:
            updated["polygon_pixel"] = polygon
            bbox = _bbox_from_polygon_pixel(polygon)
            if bbox:
                updated["bbox"] = bbox

        center = updated.get("center_pixel")
        if isinstance(center, (list, tuple)) and len(center) == 2:
            try:
                updated["center_pixel"] = [
                    round(float(center[0]) + offset_x, 2),
                    round(float(center[1]) + offset_y, 2),
                ]
            except Exception:
                _LOGGER.exception("Failed to translate polygon center for %s", updated.get("id", "unknown"))

        issues = list(updated.get("issues") or [])
        if "translated_manual" not in issues:
            issues.append("translated_manual")
        if any((edge_left, edge_right, edge_top, edge_bottom)) and "edge_adjusted_manual" not in issues:
            issues.append("edge_adjusted_manual")
        if vertex_moves and "vertex_adjusted_manual" not in issues:
            issues.append("vertex_adjusted_manual")
        updated["issues"] = issues
        updated["translation_offset"] = [offset_x, offset_y]
        updated["edge_adjustment"] = {"left": edge_left, "right": edge_right, "top": edge_top, "bottom": edge_bottom}
        updated["vertex_adjustment"] = vertex_moves
        result.append(updated)
    return result


# ---------------------------------------------------------------------------
# Image analysis handlers
# ---------------------------------------------------------------------------

async def _handle_upload_map_image(hass: HomeAssistant, call: ServiceCall) -> dict:
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    variant: str = call.data.get("variant", "default")
    layout_id: str | None = call.data.get("layout_id")
    image_b64: str = call.data["image_base64"]
    declared_width: int | None = call.data.get("image_width")
    declared_height: int | None = call.data.get("image_height")
    # Furnished custom render (Wave 0): art_scope ("home"/"room") routes the upload as
    # furnished ART for the active-or-targeted layout (NOT a backdrop). room_id is the
    # per-room target (str) when scope is "room".
    art_scope: str | None = call.data.get("art_scope")
    art_room_id = call.data.get("room_id")

    if art_scope is not None:
        # Furnished art is layout-scoped: the variant key + the layout field it writes
        # are both DERIVED from layout_id, so it's required. The layout must already exist.
        if layout_id is None:
            return {"saved": False, "reason": "layout_id_required"}
        if art_scope == "room":
            art_room_id = str(art_room_id).strip() if art_room_id is not None else ""
            if not art_room_id:
                return {"saved": False, "reason": "missing_room_id"}
            variant = f"custom_{layout_id}_room_{art_room_id}"
        else:
            variant = f"custom_{layout_id}_home_art"
        _mgr = hass.data[DOMAIN][DATA_RUNTIME]
        _bucket = ensure_map_bucket(
            data=_mgr.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
        )
        _migrate_custom_layouts(_bucket)
        if not isinstance((_bucket.get("custom_layouts") or {}).get(layout_id), dict):
            return {"saved": False, "reason": "layout_not_found"}
    # Per-layout backdrop: the layout_id forces the variant key (custom_<id>) and
    # the layout must already exist (validate before writing any file).
    elif layout_id is not None:
        variant = f"custom_{layout_id}"
        _mgr = hass.data[DOMAIN][DATA_RUNTIME]
        _bucket = ensure_map_bucket(
            data=_mgr.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
        )
        _migrate_custom_layouts(_bucket)
        if not isinstance((_bucket.get("custom_layouts") or {}).get(layout_id), dict):
            return {"saved": False, "reason": "layout_not_found"}

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return {"saved": False, "reason": "invalid_base64"}

    if not image_bytes.startswith(_PNG_MAGIC):
        try:
            import io
            from PIL import Image as _PILImageConv
            with _PILImageConv.open(io.BytesIO(image_bytes)) as _img:
                _buf = io.BytesIO()
                _img.save(_buf, format="PNG")
                image_bytes = _buf.getvalue()
        except Exception:
            return {"saved": False, "reason": "unsupported_format"}

    object_id = vacuum_entity_id.split(".", 1)[1]
    base_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "maps", object_id)
    suffix = "" if variant == "default" else f"_{variant}"
    file_path = os.path.join(base_dir, f"map_{map_id}{suffix}.png")
    browser_url = f"/eufy_vacuum/maps/{object_id}/map_{map_id}{suffix}.png"

    def _write_and_measure() -> dict:
        os.makedirs(base_dir, exist_ok=True)
        with open(file_path, "wb") as fh:
            fh.write(image_bytes)
        actual_width: int | None = None
        actual_height: int | None = None
        try:
            from PIL import Image as _PILImage
            with _PILImage.open(file_path) as img:
                actual_width, actual_height = img.size
        except Exception:
            actual_width = declared_width
            actual_height = declared_height
        return {
            "saved": True,
            "path": file_path,
            "browser_url": browser_url,
            "variant": variant,
            "size_bytes": len(image_bytes),
            "declared_width": declared_width,
            "declared_height": declared_height,
            "actual_width": actual_width,
            "actual_height": actual_height,
        }

    result = await hass.async_add_executor_job(_write_and_measure)

    if result["saved"]:
        manager = hass.data[DOMAIN][DATA_RUNTIME]
        map_bucket = ensure_map_bucket(
            data=manager.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        variants: dict = map_bucket.setdefault("image_variants", {})
        variants[variant] = {
            "variant": variant,
            "path": file_path,
            "browser_url": browser_url,
            "width": result["actual_width"],
            "height": result["actual_height"],
        }
        if art_scope is not None:
            # Furnished ART: write the derived variant onto the layout's home_art /
            # rooms[*] (lazily created), NOT backdrop_variant (that stays the layout's
            # whole-map backdrop). Bumps updated_at like the backdrop branch.
            layout = (map_bucket.get("custom_layouts") or {}).get(layout_id)
            if isinstance(layout, dict):
                if art_scope == "room":
                    rooms = layout.setdefault("rooms", {})
                    rooms.setdefault(str(art_room_id), {})["art_variant"] = variant
                else:
                    layout.setdefault("home_art", {})["art_variant"] = variant
                layout["updated_at"] = utc_now_iso()
        elif layout_id is not None:
            layout = (map_bucket.get("custom_layouts") or {}).get(layout_id)
            if isinstance(layout, dict):
                layout["backdrop_variant"] = variant
                layout["updated_at"] = utc_now_iso()
        await manager.async_save()

    _LOGGER.debug("upload_map_image: %s", result)
    return result


async def _handle_delete_map_image(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete one image variant for a map.

    Mirror of _handle_upload_map_image: removes the PNG from
    eufy_vacuum/maps/{object_id}/map_{map_id}{suffix}.png and drops the
    variant from data["maps"][vacuum][map_id]["image_variants"]. Used
    by the card's per-variant trash button on the Map Configuration
    panel so users can drop a bad upload without nuking the whole map.

    Returns {"deleted": False, "reason": "not_found"} when the variant
    isn't recorded; safe to call multiple times.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    variant: str = call.data.get("variant", "default")

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    variants: dict = map_bucket.get("image_variants", {}) or {}
    entry = variants.get(variant)
    if not isinstance(entry, dict):
        return {
            "deleted": False,
            "reason": "not_found",
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id,
            "variant": variant,
        }

    object_id = vacuum_entity_id.split(".", 1)[1]
    base_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "maps", object_id)
    suffix = "" if variant == "default" else f"_{variant}"
    file_path = entry.get("path") or os.path.join(base_dir, f"map_{map_id}{suffix}.png")

    def _remove_file() -> bool:
        try:
            os.remove(file_path)
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            _LOGGER.warning("delete_map_image: failed to remove %s: %s", file_path, exc)
            return False

    file_removed = await hass.async_add_executor_job(_remove_file)

    variants.pop(variant, None)
    if variants:
        map_bucket["image_variants"] = variants
    else:
        # Empty dict is fine; consumers check `not variants` and the
        # next variants payload will surface an empty IMAGE VARIANTS row.
        map_bucket["image_variants"] = {}

    await manager.async_save()

    result = {
        "deleted": True,
        "file_removed": file_removed,
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": map_id,
        "variant": variant,
        "remaining_variants": list(map_bucket["image_variants"].keys()),
    }
    _LOGGER.debug("delete_map_image: %s", result)
    return result


def _build_segments_response(map_bucket: dict) -> dict:
    """Return the segments payload enriched with backend-stored overlays.

    The base ``image_segments`` cache is the canonical ``SegmentationResult``
    produced by whichever ``MapSegmenter`` engine the adapter selected —
    purely engine-derived, no UI-side state. Two overlays live alongside
    the cache and ride along on every read so the card never has to make
    a second round-trip:

    - ``segment_room_links`` — ``{segment_id: room_id}`` user-assigned
      mapping. Each segment gets a ``room_id`` field populated when a
      link exists.
    - ``companion_anchors`` — ``{room_id: {pct_x, pct_y}}`` — per-room
      anchor positions for the animated companion sprite.

    The original ``image_segments`` cache is NOT mutated; this builds a
    shallow-copied response. Keeps the cache pristine so re-analysis
    starts from clean data.
    """
    base = map_bucket.get("image_segments") or {}
    if not isinstance(base, dict):
        return base
    links = map_bucket.get("segment_room_links") or {}
    anchors = map_bucket.get("companion_anchors") or {}
    if not isinstance(links, dict):
        links = {}
    if not isinstance(anchors, dict):
        anchors = {}

    response = dict(base)
    raw_segments = base.get("segments") or []
    if isinstance(raw_segments, list) and links:
        enriched: list[dict] = []
        for seg in raw_segments:
            if not isinstance(seg, dict):
                enriched.append(seg)
                continue
            seg_id = str(seg.get("segment_id"))
            linked_room = links.get(seg_id)
            if linked_room is not None:
                # Shallow copy + room_id injection. Original cache untouched.
                seg = {**seg, "room_id": str(linked_room)}
            enriched.append(seg)
        response["segments"] = enriched
    response["companion_anchors"] = dict(anchors)
    return response


async def _handle_analyze_map_image(hass: HomeAssistant, call: ServiceCall) -> dict:
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    expected_room_count = call.data.get("expected_room_count")
    max_segments = call.data.get("max_segments")
    min_area_pixels: int = call.data.get("min_area_pixels", 1200)
    simplify_epsilon = call.data.get("simplify_epsilon")
    force_reanalyze: bool = call.data.get("force_reanalyze", False)

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )

    if not force_reanalyze and map_bucket.get("image_segments"):
        _LOGGER.debug("analyze_map_image: returning cached for %s map %s", vacuum_entity_id, map_id)
        return _build_segments_response(map_bucket)

    # Prefer the variant recorded on upload; fall back to filesystem probe.
    variants: dict = map_bucket.get("image_variants") or {}
    object_id = vacuum_entity_id.split(".", 1)[1]
    base_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "maps", object_id)

    def _variant_path(v: str) -> str:
        if v in variants and variants[v].get("path"):
            return str(variants[v]["path"])
        suffix = "" if v == "default" else f"_{v}"
        return os.path.join(base_dir, f"map_{map_id}{suffix}.png")

    # Dark as primary, light as assist; fall back to default if dark missing.
    image_path: str | None = None
    image_variant: str | None = None
    for candidate in ("dark", "default"):
        p = _variant_path(candidate)
        if os.path.isfile(p):
            image_path = p
            image_variant = candidate
            break

    if not image_path:
        return {
            "available": False,
            "reason": "image_not_found",
            "message": f"No map image found in {base_dir}",
            "segments": [],
        }

    light_p = _variant_path("light")
    assist_path = light_p if os.path.isfile(light_p) else None

    # Select the engine declared by the adapter. Tuning starts from the
    # adapter's persisted defaults; call.data fields override them so a
    # service caller can still parameterize a one-off run.
    from ..adapters.registry import get_adapter_config
    from .segmenter_engines import get_segmenter_engine

    adapter = get_adapter_config(vacuum_entity_id) or {}
    mapping_block = adapter.get("mapping", {}) if isinstance(adapter, dict) else {}
    engine_name = mapping_block.get("segmenter_engine") if isinstance(mapping_block, dict) else None
    adapter_tuning = mapping_block.get("segmenter_tuning", {}) if isinstance(mapping_block, dict) else {}

    tuning: dict = dict(adapter_tuning) if isinstance(adapter_tuning, dict) else {}
    if expected_room_count is not None:
        tuning["expected_room_count"] = expected_room_count
    if max_segments is not None:
        tuning["max_segments"] = max_segments
    if min_area_pixels is not None:
        tuning["min_area_pixels"] = min_area_pixels
    if simplify_epsilon is not None:
        tuning["simplify_epsilon"] = simplify_epsilon
    if assist_path:
        tuning["assist_image_path"] = assist_path
    if image_variant is not None:
        tuning["image_variant"] = image_variant
    if assist_path:
        tuning["assist_variant"] = "light"

    engine = get_segmenter_engine(engine_name)

    def _run() -> dict:
        return engine.segment_map_image(
            image_path=image_path,
            tuning=tuning,
            context=None,
        )

    result = await hass.async_add_executor_job(_run)
    result["analyzed_at"] = utc_now_iso()
    map_bucket["image_segments"] = result
    await manager.async_save()

    _LOGGER.debug(
        "analyze_map_image: %s segments for %s map %s",
        len(result.get("segments", [])), vacuum_entity_id, map_id,
    )
    # Enrich with stored overlays before returning. Re-analysis preserves
    # the user's segment_room_links and companion_anchors — they're
    # independent of the image-derived segments.
    return _build_segments_response(map_bucket)


async def _handle_get_map_segments(hass: HomeAssistant, call: ServiceCall) -> dict:
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )

    # CV-or-Custom: serve whichever segment store the toggle selects. Reading is
    # pure — it never invokes the segmenter — so a custom <-> cv flip is a cheap
    # pointer change and both stores survive a round-trip untouched.
    _migrate_custom_layouts(map_bucket)
    scope = _resolve_active_scope(map_bucket)
    mode: str = scope["mode"]
    raw = scope["segments_store"] or {}
    adjustments: dict = map_bucket.get("image_segment_adjustments") or {}
    raw_segments: list = raw.get("segments") or []

    adjusted_segments = _apply_segment_adjustments(raw_segments, adjustments)

    img_variants = map_bucket.get("image_variants") or {}
    img_meta = (
        (img_variants.get(scope["backdrop_variant"]) if scope["backdrop_variant"] else None)
        or img_variants.get("dark")
        or img_variants.get("default")
        or img_variants.get("light")
        or {}
    )
    # The pixel->pct scale MUST be the pixel dims the polygons were rasterised
    # against, which the segment store records under "image". Prefer those over the
    # backdrop variant's dims: a LIVE-image-backed custom layout has NO uploaded
    # image_variant, so relying on img_variants would leave img_w/h at 1 and inflate
    # polygon_pct by a factor of the real width (polygons land far off-screen). For
    # CV + uploaded-custom the store dims equal the variant dims, so this is a no-op.
    store_img = raw.get("image") if isinstance(raw.get("image"), dict) else {}
    img_w = store_img.get("width") or img_meta.get("width") or 1
    img_h = store_img.get("height") or img_meta.get("height") or 1
    for seg in adjusted_segments:
        px = seg.get("polygon_pixel")
        if px and isinstance(px, list):
            seg["polygon_pct"] = [
                [round(x / img_w * 100, 4), round(y / img_h * 100, 4)]
                for x, y in px
            ]

    # Enrich with backend-stored overlays (segment_room_links,
    # companion_anchors) so this endpoint serves the same union of
    # image-derived + UI-state data that analyze_map_image does. Card
    # never has to make a second round-trip.
    links = scope["links"]
    if isinstance(links, dict) and links:
        for seg in adjusted_segments:
            if not isinstance(seg, dict):
                continue
            seg_id = str(seg.get("segment_id"))
            linked_room = links.get(seg_id)
            if linked_room is not None:
                seg["room_id"] = str(linked_room)

    anchors = scope["anchors"]

    layouts = map_bucket.get("custom_layouts") or {}
    layouts_summary = [
        {
            "id": lay.get("id"),
            "name": lay.get("name"),
            "backdrop_variant": lay.get("backdrop_variant"),
            "backdrop_source": lay.get("backdrop_source"),
            "segment_count": len((lay.get("custom_segments") or {}).get("segments") or []),
            "created_at": lay.get("created_at"),
            "updated_at": lay.get("updated_at"),
            # Furnished custom render (Wave 0) — this fixed whitelist is the ONLY way the
            # per-layout furnished keys reach the editor, so surface them here.
            "render_mode": lay.get("render_mode"),
            "home_art": lay.get("home_art"),
            "rooms": lay.get("rooms") or {},
        }
        for lay in layouts.values()
        if isinstance(lay, dict)
    ]

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": map_id,
        "segmentation_mode": mode,
        "active_custom_layout_id": map_bucket.get("active_custom_layout_id"),
        "custom_layouts": layouts_summary,
        "segment_room_links": dict(links) if isinstance(links, dict) else {},
        "available": bool(raw.get("available", False)),
        "analyzed_at": raw.get("analyzed_at"),
        "image": raw.get("image"),
        "image_variants": map_bucket.get("image_variants") or {},
        "summary": {
            **(raw.get("summary") or {}),
            "segment_count": len(adjusted_segments),
            "adjusted_count": sum(
                1 for s in adjusted_segments
                if "translated_manual" in (s.get("issues") or [])
                or "edge_adjusted_manual" in (s.get("issues") or [])
                or "vertex_adjusted_manual" in (s.get("issues") or [])
            ),
        },
        "segments": adjusted_segments,
        "adjustments": adjustments,
        "companion_anchors": dict(anchors) if isinstance(anchors, dict) else {},
        # Hidden regions are MAP-LEVEL (mode-independent physical masks), not scope-resolved.
        "hidden_regions": list(map_bucket.get("hidden_regions") or [])
        if isinstance(map_bucket.get("hidden_regions"), list) else [],
        # Area-label positions are MAP-LEVEL too (the device rooms are mode-independent).
        "area_label_anchors": dict(map_bucket.get("area_label_anchors") or {})
        if isinstance(map_bucket.get("area_label_anchors"), dict) else {},
    }


async def _handle_set_segmentation_mode(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Flip a map between CV and Custom segmentation.

    INVARIANT: this NEVER runs the segmenter, in either direction. It only writes
    the ``segmentation_mode`` flag; ``_handle_get_map_segments`` then reads whichever
    store the flag selects (``image_segments`` for cv, ``custom_segments`` for
    custom). Both stores are left untouched, so toggling cv -> custom -> cv preserves
    each segment set with zero re-analysis.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    mode: str = call.data["mode"]

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    map_bucket["segmentation_mode"] = mode
    # Flipping to custom with no active layout but layouts present: soft-select the
    # first so the view always resolves a store (hard auto-create is in the CRUD).
    if mode == "custom" and not _active_custom_layout(map_bucket):
        layouts = map_bucket.get("custom_layouts") or {}
        if layouts:
            map_bucket["active_custom_layout_id"] = sorted(layouts)[0]
    await manager.async_save()

    active = (_resolve_active_scope(map_bucket)["segments_store"] or {}).get("segments") or []
    _LOGGER.debug("set_segmentation_mode: %s/%s -> %s", vacuum_entity_id, map_id, mode)
    return {"saved": True, "mode": mode, "segment_count": len(active)}


# ---------------------------------------------------------------------------
# Custom layouts — named collection of no-CV segmentations per map
# ---------------------------------------------------------------------------
#
# A map can hold MANY named custom layouts (e.g. a "solar system" image and a
# "tree" image), each owning its own backdrop, authored segments, room links and
# mascot anchors. CV stays special at the map-bucket level (image_segments + the
# shared segment_room_links/companion_anchors). The active view is resolved once,
# through _resolve_active_scope, so CV and custom can never drift.


def _generate_custom_layout_id(existing) -> str:
    """Stable unique id for a new custom layout (mirrors run-profile ids), with a
    same-second collision guard so rapid creates (and tests) never clash."""
    base = f"cl_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def _active_custom_layout(map_bucket: dict) -> dict | None:
    """The active custom layout dict (the one being authored / shown in custom
    mode), or None when there is no resolvable active layout."""
    layouts = map_bucket.get("custom_layouts") or {}
    layout_id = map_bucket.get("active_custom_layout_id")
    layout = layouts.get(layout_id) if layout_id else None
    return layout if isinstance(layout, dict) else None


def _migrate_custom_layouts(map_bucket: dict) -> None:
    """Lazily fold a legacy single ``custom_segments`` store into the named
    ``custom_layouts`` collection. Idempotent + non-destructive: returns at once
    once ``custom_layouts`` exists, and never deletes the legacy key.

    Today's ``segment_room_links`` / ``companion_anchors`` are SHARED between CV
    and the single custom store. On migration we COPY into the default layout only
    the entries that resolve against its custom segments (a link whose seg id is a
    custom segment; the ``dock`` anchor + anchors for rooms those links point at),
    leaving CV's map-bucket dicts intact.
    """
    if isinstance(map_bucket.get("custom_layouts"), dict):
        return
    map_bucket["custom_layouts"] = {}
    map_bucket.setdefault("active_custom_layout_id", None)

    legacy = map_bucket.get("custom_segments")
    if not isinstance(legacy, dict) or not legacy.get("segments"):
        return

    seg_ids = {str(s.get("segment_id")) for s in legacy.get("segments") or []}
    all_links = map_bucket.get("segment_room_links") or {}
    links = {sid: rid for sid, rid in all_links.items() if str(sid) in seg_ids}
    linked_rooms = {str(rid) for rid in links.values()}
    all_anchors = map_bucket.get("companion_anchors") or {}
    anchors = {
        key: val for key, val in all_anchors.items()
        if key == "dock" or str(key) in linked_rooms
    }

    layout_id = _generate_custom_layout_id(set())
    now = utc_now_iso()
    map_bucket["custom_layouts"][layout_id] = {
        "id": layout_id,
        "name": "Custom",
        "backdrop_variant": "custom",
        "custom_segments": legacy,
        "segment_room_links": dict(links),
        "companion_anchors": dict(anchors),
        # Furnished custom render (Wave 0): per-room furnished-art + viewport overrides.
        # Empty at mint; home_art / render_mode stay absent until set (parity w/ _create_layout).
        "rooms": {},
        "created_at": now,
        "updated_at": now,
    }
    map_bucket["active_custom_layout_id"] = layout_id


def _resolve_active_scope(map_bucket: dict) -> dict:
    """Resolve the live segment store / link store / anchor store / backdrop
    variant from (segmentation_mode, active layout). CV → the map-bucket-level
    keys; custom → the active layout's keys. ``links``/``anchors`` are the real
    mutable dicts, so the existing 1:1-enforcement and clamp logic is unchanged.
    Call after ``_migrate_custom_layouts``.
    """
    mode = map_bucket.get("segmentation_mode") or "cv"
    if mode == "custom":
        layout = _active_custom_layout(map_bucket)
        if layout is not None:
            return {
                "mode": "custom",
                "layout_id": map_bucket.get("active_custom_layout_id"),
                "segments_store": layout.setdefault("custom_segments", {}),
                "links": layout.setdefault("segment_room_links", {}),
                "anchors": layout.setdefault("companion_anchors", {}),
                "backdrop_variant": layout.get("backdrop_variant"),
            }
        return {
            "mode": "custom", "layout_id": None,
            "segments_store": {}, "links": {}, "anchors": {},
            "backdrop_variant": None,
        }
    return {
        "mode": "cv", "layout_id": None,
        "segments_store": map_bucket.get("image_segments") or {},
        "links": map_bucket.setdefault("segment_room_links", {}),
        "anchors": map_bucket.setdefault("companion_anchors", {}),
        "backdrop_variant": None,
    }


def _create_layout(
    map_bucket: dict, name: str, *, backdrop_variant: str | None = None,
    backdrop_source: str | None = None, activate: bool = True
) -> dict:
    """Mint + (optionally) activate a new custom layout with empty stores. New
    layouts get a per-layout ``custom_<id>`` backdrop variant unless one is given.
    ``backdrop_source="live"`` pins the layout to the brand's live-map image (the
    card composes rooms straight over the live camera/image, never an upload)."""
    layouts = map_bucket.setdefault("custom_layouts", {})
    layout_id = _generate_custom_layout_id(set(layouts))
    now = utc_now_iso()
    layout = {
        "id": layout_id,
        "name": (name or "").strip() or "Custom",
        "backdrop_variant": backdrop_variant or f"custom_{layout_id}",
        "custom_segments": {},
        "segment_room_links": {},
        "companion_anchors": {},
        # Furnished custom render (Wave 0): per-room furnished-art + viewport overrides.
        # Empty at mint; home_art / render_mode stay absent until set.
        "rooms": {},
        "created_at": now,
        "updated_at": now,
    }
    if backdrop_source:
        layout["backdrop_source"] = backdrop_source
    layouts[layout_id] = layout
    if activate:
        map_bucket["active_custom_layout_id"] = layout_id
    return layout


def _ensure_default_layout(
    map_bucket: dict, *, backdrop_variant: str = "custom", name: str = "Custom"
) -> dict:
    """Return the active custom layout, creating + activating a default one when
    none exists. Keeps authoring valid with zero layouts — backward-compat with the
    pre-layout flow (whose backdrop sits at the shared ``custom`` variant)."""
    layout = _active_custom_layout(map_bucket)
    if layout is not None:
        return layout
    return _create_layout(map_bucket, name, backdrop_variant=backdrop_variant)


def _build_custom_segment(
    segment_id: str, polygon_pixel: list[list[int]], *, map_w: int, map_h: int
) -> dict:
    """Wrap an authored polygon in the same segment shape CV produces, so
    get_map_segments / room-linking / dispatch treat custom and CV segments
    identically."""
    xs = [p[0] for p in polygon_pixel]
    ys = [p[1] for p in polygon_pixel]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    area = abs(polygon_area([(float(x), float(y)) for x, y in polygon_pixel]))
    total = max(1, int(map_w) * int(map_h))
    return {
        "segment_id": segment_id,
        "source": "custom",
        "polygon_pixel": polygon_pixel,
        "bbox": {
            "x": min_x, "y": min_y,
            "width": max(1, max_x - min_x), "height": max(1, max_y - min_y),
        },
        "area_pixels": int(round(area)),
        "area_percent": round(area / total * 100, 2),
        "center_pixel": [round((min_x + max_x) / 2, 1), round((min_y + max_y) / 2, 1)],
        "point_count_raw": len(polygon_pixel),
        "point_count_simplified": len(polygon_pixel),
        "confidence": 1.0,
        "quality": "custom",
        "structural_role": "room",
        "segmentation_state": "custom",
        "edit_readiness": "ready",
        "matched_room_id": None,
        "matched_room_label": None,
        "issues": [],
    }


async def _handle_set_custom_segments(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Author custom (no-CV) segments from primitives — REPLACE-ALL into the map's
    custom_segments store.

    Each segment's pct-space primitives are rasterised + traced into a polygon
    (segment_primitives.rasterize_primitives -> mask_to_polygon), scaled to the
    'custom' backdrop's pixel dims, and wrapped as a CV-shaped segment. Requires
    the custom backdrop (for the dims). Never invokes the segmenter. Stable ``id``
    fields are preserved (auto ``custom_N`` otherwise) so segment_room_links survive
    re-saves. The rasterisation runs in the executor (mask_to_polygon is blocking).
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    seg_inputs: list = call.data["segments"]

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )

    _migrate_custom_layouts(map_bucket)
    layout = _ensure_default_layout(map_bucket)

    variant = layout.get("backdrop_variant") or "custom"
    backdrop = (map_bucket.get("image_variants") or {}).get(variant) or {}
    map_w = backdrop.get("width")
    map_h = backdrop.get("height")
    if not map_w or not map_h:
        # Live-image-backed layout: no uploaded backdrop, so the card captured the
        # rendered live image's natural pixel size. Shapes + the stored polygons are
        # pct, so these dims only set the rasterisation resolution/aspect — using the
        # live image's real dims keeps the polygon aspect true over the live picture.
        cw = call.data.get("backdrop_width")
        ch = call.data.get("backdrop_height")
        if cw and ch:
            map_w, map_h = int(cw), int(ch)
            variant = "live"
    if not map_w or not map_h:
        return {"saved": False, "reason": "no_custom_backdrop"}

    def _rasterise_all() -> tuple[list[dict], int]:
        built: list[dict] = []
        skipped = 0
        used_ids: set[str] = set()
        for i, seg in enumerate(seg_inputs):
            sid = str(seg.get("id") or "").strip() or f"custom_{i + 1}"
            base, n = sid, 1
            while sid in used_ids:  # de-dup defensively
                n += 1
                sid = f"{base}_{n}"
            used_ids.add(sid)
            poly = rasterize_primitives(
                seg.get("primitives") or [], width=int(map_w), height=int(map_h)
            )
            if not poly:
                skipped += 1
                continue
            built.append(
                _build_custom_segment(sid, poly, map_w=int(map_w), map_h=int(map_h))
            )
        return built, skipped

    built, skipped = await hass.async_add_executor_job(_rasterise_all)

    layout["custom_segments"] = {
        "available": bool(built),
        "engine": "custom",
        "analyzed_at": utc_now_iso(),
        "image": {"width": int(map_w), "height": int(map_h), "variant": variant},
        "segments": built,
        "summary": {"segment_count": len(built)},
    }
    layout["updated_at"] = utc_now_iso()
    await manager.async_save()

    _LOGGER.debug(
        "set_custom_segments: %s/%s -> %d segments (%d skipped)",
        vacuum_entity_id, map_id, len(built), skipped,
    )
    return {
        "saved": True,
        "segment_count": len(built),
        "skipped": skipped,
        "segment_ids": [s["segment_id"] for s in built],
    }


async def _handle_adjust_map_segment(hass: HomeAssistant, call: ServiceCall) -> dict:
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    segment_id: str = str(call.data["segment_id"]).strip()

    if not segment_id:
        return {"saved": False, "reason": "missing_segment_id"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )

    segments = (map_bucket.get("image_segments") or {}).get("segments") or []
    if not any(str(seg.get("segment_id") or "") == segment_id for seg in segments):
        return {"saved": False, "reason": "segment_not_found", "segment_id": segment_id}

    adjustments: dict = map_bucket.setdefault("image_segment_adjustments", {})
    current = adjustments.get(segment_id, {})

    offset_x = _safe_int(current.get("offset_x")) + _safe_int(call.data.get("delta_x"))
    offset_y = _safe_int(current.get("offset_y")) + _safe_int(call.data.get("delta_y"))
    edge_left = _safe_int(current.get("edge_left")) + _safe_int(call.data.get("edge_left"))
    edge_right = _safe_int(current.get("edge_right")) + _safe_int(call.data.get("edge_right"))
    edge_top = _safe_int(current.get("edge_top")) + _safe_int(call.data.get("edge_top"))
    edge_bottom = _safe_int(current.get("edge_bottom")) + _safe_int(call.data.get("edge_bottom"))

    existing_vertices: dict[int, dict] = {
        _safe_int(v.get("index"), -1): v
        for v in (current.get("vertex_moves") or [])
        if isinstance(v, dict) and _safe_int(v.get("index"), -1) >= 0
    }
    for move in (call.data.get("vertex_moves") or []):
        if not isinstance(move, dict):
            continue
        idx = _safe_int(move.get("index"), -1)
        if idx < 0:
            continue
        prev = existing_vertices.get(idx, {"index": idx, "delta_x": 0, "delta_y": 0})
        nx = _safe_int(prev.get("delta_x")) + _safe_int(move.get("delta_x"))
        ny = _safe_int(prev.get("delta_y")) + _safe_int(move.get("delta_y"))
        if nx or ny:
            existing_vertices[idx] = {"index": idx, "delta_x": nx, "delta_y": ny}
        else:
            existing_vertices.pop(idx, None)

    vertex_moves = [existing_vertices[i] for i in sorted(existing_vertices)]

    if any((offset_x, offset_y, edge_left, edge_right, edge_top, edge_bottom)) or vertex_moves:
        adjustments[segment_id] = {
            "offset_x": offset_x,
            "offset_y": offset_y,
            "edge_left": edge_left,
            "edge_right": edge_right,
            "edge_top": edge_top,
            "edge_bottom": edge_bottom,
            "vertex_moves": vertex_moves,
        }
    else:
        adjustments.pop(segment_id, None)

    await manager.async_save()

    _LOGGER.debug("adjust_map_segment: %s → %s", segment_id, adjustments.get(segment_id))
    return {
        "saved": True,
        "segment_id": segment_id,
        "adjustment": adjustments.get(segment_id),
    }


async def _handle_set_segment_room_link(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist or clear a segment→room linkage on the per-map bucket.

    Pass ``room_id`` (string or int) to set; pass ``null`` or omit to
    clear. The mapping is enforced 1:1 — assigning a room that's already
    linked to another segment removes the older link, mirroring the
    card's existing assignSegmentRoom behaviour.

    Returns the updated full ``segment_room_links`` dict so the card
    can refresh its in-memory state without a separate fetch.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    segment_id: str = str(call.data["segment_id"]).strip()
    room_id_raw = call.data.get("room_id")

    if not segment_id:
        return {"saved": False, "reason": "missing_segment_id"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    links: dict = _resolve_active_scope(map_bucket)["links"]

    if room_id_raw is None or str(room_id_raw).strip() == "":
        # Clear path.
        links.pop(segment_id, None)
        action = "cleared"
    else:
        room_id = str(room_id_raw).strip()
        # Enforce 1:1 — drop any other segment currently pointing at this room.
        for existing_seg, existing_room in list(links.items()):
            if str(existing_room) == room_id and existing_seg != segment_id:
                links.pop(existing_seg, None)
        links[segment_id] = room_id
        action = "set"

    await manager.async_save()
    _LOGGER.debug(
        "set_segment_room_link: %s on %s/%s -> %s",
        action, vacuum_entity_id, map_id, segment_id,
    )
    return {
        "saved": True,
        "segment_id": segment_id,
        "action": action,
        "segment_room_links": dict(links),
    }


async def _handle_set_companion_anchor(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist or clear the per-room companion-sprite anchor position.

    Anchor is stored as ``{room_id: {pct_x, pct_y}}`` where pct_x/pct_y
    are 0-100 percentage offsets from the map image's top-left. Pass
    null for both pct_x and pct_y (or omit them) to clear the anchor.

    Returns the updated full ``companion_anchors`` dict so the card
    refreshes in-memory state without a second fetch.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    room_id: str = str(call.data["room_id"]).strip()
    pct_x = call.data.get("pct_x")
    pct_y = call.data.get("pct_y")

    if not room_id:
        return {"saved": False, "reason": "missing_room_id"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    anchors: dict = _resolve_active_scope(map_bucket)["anchors"]

    if pct_x is None and pct_y is None:
        anchors.pop(room_id, None)
        action = "cleared"
    else:
        # Clamp 0-100 defensively. The card sends fractional pixel%; the service
        # schema (SET_COMPANION_ANCHOR_SCHEMA) already coerced pct_x/pct_y to
        # float-or-None, so float() here cannot raise — there is no reachable
        # error path, hence no error arm.
        x = max(0.0, min(100.0, float(pct_x))) if pct_x is not None else 50.0
        y = max(0.0, min(100.0, float(pct_y))) if pct_y is not None else 50.0
        anchors[room_id] = {"pct_x": round(x, 4), "pct_y": round(y, 4)}
        action = "set"

    await manager.async_save()
    _LOGGER.debug(
        "set_companion_anchor: %s on %s/%s room %s",
        action, vacuum_entity_id, map_id, room_id,
    )
    return {
        "saved": True,
        "room_id": room_id,
        "action": action,
        "companion_anchors": dict(anchors),
    }


# ---------------------------------------------------------------------------
# Furnished custom render (Wave 0) — per-layout furnished-art overlay state
# ---------------------------------------------------------------------------
#
# All three write onto the ACTIVE custom layout (resolved via _active_custom_layout):
# never the map bucket, so furnished data can't leak across CV / other layouts. The
# whole-home art lives at layout["home_art"]; per-room overrides at
# layout["rooms"][room_id]. Each bumps updated_at + async_saves + returns the resolved
# furnished_render projection so the card refreshes without a second fetch. Transforms
# and viewports are stored resolution-independent (pct floats).


def _round4(value: Any, default: float) -> float:
    """Coerce to float (schema already did) rounded to 4dp; ``default`` for None."""
    return round(float(value), 4) if value is not None else default


async def _handle_set_furnished_art_placement(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist or clear the furnished-art placement transform {tx,ty,scale,rotation}
    on the active custom layout. scope "home" = the whole-home art; "room" = a per-room
    override (room_id required). Pass all of tx/ty/scale/rotation null (or omit them) to
    clear the placement. Returns the resolved furnished_render so the card refreshes."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    scope: str = call.data["scope"]
    room_id = call.data.get("room_id")
    tx = call.data.get("tx")
    ty = call.data.get("ty")
    scale = call.data.get("scale")
    rotation = call.data.get("rotation")

    if scope == "room":
        room_id = str(room_id).strip() if room_id is not None else ""
        if not room_id:
            return {"saved": False, "reason": "missing_room_id"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layout = _active_custom_layout(map_bucket)
    if layout is None:
        return {"saved": False, "reason": "no_active_layout"}

    # The target dict the transform lives on: the home art, or the per-room override.
    if scope == "room":
        target = layout.setdefault("rooms", {}).setdefault(room_id, {})
    else:
        target = layout.setdefault("home_art", {})

    if tx is None and ty is None and scale is None and rotation is None:
        target.pop("art_placement_transform", None)
        action = "cleared"
    else:
        target["art_placement_transform"] = {
            "tx": _round4(tx, 0.0),
            "ty": _round4(ty, 0.0),
            # Clamp scale to the same [0.05, 20] floor/ceiling the card enforces. A raw 0
            # (or negative) would persist as 0.0 but the renderer coerces it back to 1x
            # (`Number(scale) || 1`), so state and render would silently disagree; clamp here
            # so the stored value is always renderable and matches what the UI allows.
            "scale": _round4(
                None if scale is None else min(max(float(scale), 0.05), 20.0), 1.0,
            ),
            "rotation": _round4(rotation, 0.0),
        }
        action = "set"

    layout["updated_at"] = utc_now_iso()
    await manager.async_save()
    _LOGGER.debug(
        "set_furnished_art_placement: %s scope=%s on %s/%s room=%s",
        action, scope, vacuum_entity_id, map_id, room_id,
    )
    return {
        "saved": True,
        "scope": scope,
        "room_id": room_id if scope == "room" else None,
        "action": action,
        "furnished_render": resolve_furnished_render(map_bucket),
    }


async def _handle_set_furnished_render_mode(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Set the furnished render mode (live | art | blend) at the layout level (room_id
    omitted) or as a per-room override (room_id set) on the active custom layout."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    mode: str = call.data["mode"]
    room_id = call.data.get("room_id")

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layout = _active_custom_layout(map_bucket)
    if layout is None:
        return {"saved": False, "reason": "no_active_layout"}

    # A blank/whitespace room_id means "layout-level default", same as None — never mint a
    # junk rooms[""] entry. (The placement/viewport handlers REJECT blank with missing_room_id
    # because a transform/viewport with no room is meaningless; a render_mode legitimately
    # defaults to the layout level, so route blank there instead of rejecting.)
    room_id = str(room_id).strip() if room_id is not None else ""
    if not room_id:
        layout["render_mode"] = mode
    else:
        layout.setdefault("rooms", {}).setdefault(room_id, {})["render_mode"] = mode

    layout["updated_at"] = utc_now_iso()
    await manager.async_save()
    _LOGGER.debug(
        "set_furnished_render_mode: %s on %s/%s room=%s",
        mode, vacuum_entity_id, map_id, room_id or None,
    )
    return {
        "saved": True,
        "mode": mode,
        "room_id": room_id or None,
        "furnished_render": resolve_furnished_render(map_bucket),
    }


async def _handle_set_room_viewport(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist or clear a saved per-room viewport {cx,cy,zoom} (pct floats) on the
    active custom layout. Pass all of cx/cy/zoom null (or omit them) to clear it."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    room_id = str(call.data["room_id"]).strip()
    cx = call.data.get("cx")
    cy = call.data.get("cy")
    zoom = call.data.get("zoom")

    if not room_id:
        return {"saved": False, "reason": "missing_room_id"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layout = _active_custom_layout(map_bucket)
    if layout is None:
        return {"saved": False, "reason": "no_active_layout"}

    target = layout.setdefault("rooms", {}).setdefault(room_id, {})
    if cx is None and cy is None and zoom is None:
        target.pop("viewport", None)
        action = "cleared"
    else:
        target["viewport"] = {
            "cx": _round4(cx, 0.0),
            "cy": _round4(cy, 0.0),
            "zoom": _round4(zoom, 1.0),
        }
        action = "set"

    layout["updated_at"] = utc_now_iso()
    await manager.async_save()
    _LOGGER.debug(
        "set_room_viewport: %s on %s/%s room %s",
        action, vacuum_entity_id, map_id, room_id,
    )
    return {
        "saved": True,
        "room_id": room_id,
        "action": action,
        "furnished_render": resolve_furnished_render(map_bucket),
    }


async def _handle_set_hidden_regions(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Replace-all the per-map HIDDEN REGIONS — normalized ``[x0, y0, x1, y1]`` rects (0-1 of
    the rendered image, top-left origin) the card draws to MASK map noise (e.g. porch noise off
    a room). Stored at the MAP-BUCKET level (NOT per segmentation scope): a hidden area is a
    physical region, mode-independent, and only drawable over the device-frame backdrop — so it
    follows the map regardless of CV/custom layout. An empty/omitted ``regions`` clears them.
    Each entry is sanitized (4 FINITE numbers, clamped 0-1, ordered min<max, degenerate dropped).
    Returns the updated list."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    raw = call.data.get("regions") or []

    cleaned: list[list[float]] = []
    for rect in raw:
        if not (isinstance(rect, (list, tuple)) and len(rect) == 4):
            continue
        if not all(
            isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c)
            for c in rect
        ):
            continue  # reject non-numeric / bool / NaN / inf (NaN would clamp to an edge, not drop)
        x0, y0, x1, y1 = (max(0.0, min(1.0, float(c))) for c in rect)
        lo_x, hi_x = sorted((x0, x1))
        lo_y, hi_y = sorted((y0, y1))
        if hi_x - lo_x > 0.001 and hi_y - lo_y > 0.001:  # drop degenerate / stray taps
            cleaned.append([round(lo_x, 5), round(lo_y, 5), round(hi_x, 5), round(hi_y, 5)])

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    regions: list = map_bucket.setdefault("hidden_regions", [])
    regions.clear()
    regions.extend(cleaned)

    await manager.async_save()
    _LOGGER.debug(
        "set_hidden_regions: %d region(s) on %s/%s", len(cleaned), vacuum_entity_id, map_id,
    )
    return {"saved": True, "hidden_regions": list(regions)}


async def _handle_set_area_label_anchor(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist or clear the per-room AREA-LABEL position (the m² chip), so it can be dragged off
    the room-name label. Stored MAP-LEVEL (the device rooms are segmentation-mode-independent),
    keyed by room id, as ``{pct_x, pct_y}`` (0-100 of the map content box — the same frame the
    mascot anchor uses). Null both pct_x and pct_y to reset to the default (room centre).
    Returns the updated map."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    room_id: str = str(call.data["room_id"]).strip()
    pct_x = call.data.get("pct_x")
    pct_y = call.data.get("pct_y")

    if not room_id:
        return {"saved": False, "reason": "missing_room_id"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    anchors: dict = map_bucket.setdefault("area_label_anchors", {})

    if pct_x is None and pct_y is None:
        anchors.pop(room_id, None)
        action = "cleared"
    else:
        x = max(0.0, min(100.0, float(pct_x))) if pct_x is not None else 50.0
        y = max(0.0, min(100.0, float(pct_y))) if pct_y is not None else 50.0
        anchors[room_id] = {"pct_x": round(x, 4), "pct_y": round(y, 4)}
        action = "set"

    await manager.async_save()
    _LOGGER.debug(
        "set_area_label_anchor: %s on %s/%s room %s",
        action, vacuum_entity_id, map_id, room_id,
    )
    return {
        "saved": True, "room_id": room_id, "action": action,
        "area_label_anchors": dict(anchors),
    }


async def _handle_set_live_map_rotation(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist the live-map DISPLAY rotation (0/90/180/270) on the map bucket.

    Display only — the card rotates the live map image to match how the user
    pictures their home; cleaning/dispatch is by room id and is never affected.
    Stored per map so the orientation follows the user across devices; surfaced in
    the dashboard snapshot as ``live_map_rotation``.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    rotation = int(call.data["rotation"]) % 360

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    map_bucket["live_map_rotation"] = rotation
    await manager.async_save()
    _LOGGER.debug(
        "set_live_map_rotation: %s deg on %s/%s",
        rotation, vacuum_entity_id, map_id,
    )
    return {"saved": True, "live_map_rotation": rotation}


async def _handle_set_map_overlay_visibility(
    hass: HomeAssistant, call: ServiceCall,
) -> dict:
    """Persist per-map overlay-layer visibility (Wave 3b). Display only.

    Stores only the user's DELTAS as ``overlay_visibility`` on the map bucket (a partial
    dict merged over the defaults at read time via ``resolve_overlay_visibility``), so the
    defaults can evolve without rewriting stored prefs. ``reset:true`` clears the deltas.
    Returns the fully-resolved visibility for the card. Like rotation, this never touches
    cleaning/dispatch — the card reads it to show/hide overlay layers on the backdrop.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    manager = hass.data[DOMAIN][DATA_RUNTIME]
    # Resolve map_id when omitted: active map, then the first stored map.
    map_id = call.data.get("map_id")
    if not map_id:
        from ..rooms.room_discovery import get_active_map_id
        try:
            map_id = get_active_map_id(hass, vacuum_entity_id)
        except Exception:  # noqa: BLE001
            map_id = None
    if not map_id:
        vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {})
        map_id = next(iter(vac_maps), None)
    if not map_id:
        return {
            "saved": False,
            "error": "no_map",
            "message": f"No map found for '{vacuum_entity_id}'; pass map_id explicitly.",
        }
    map_bucket = ensure_map_bucket(
        data=manager.data,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    if call.data.get("reset"):
        map_bucket.pop("overlay_visibility", None)
    else:
        stored = map_bucket.get("overlay_visibility")
        if not isinstance(stored, dict):
            stored = {}
        stored.update({k: bool(v) for k, v in (call.data.get("visibility") or {}).items()})
        map_bucket["overlay_visibility"] = stored
    await manager.async_save()
    resolved = resolve_overlay_visibility(map_bucket.get("overlay_visibility"))
    _LOGGER.debug(
        "set_map_overlay_visibility: %s/%s -> %s",
        vacuum_entity_id, map_id, resolved,
    )
    return {"saved": True, "map_id": map_id, "overlay_visibility": resolved}


async def _handle_get_map_render_data(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the raster + decode params for the card's OWN map render (Wave 1).

    Adapter-driven, off-loop .storage read — delegates to
    manager.async_get_map_render_data. The card calls this on demand (VA-rendered
    backdrop selected) and caches by the returned `version`.
    """
    manager = hass.data[DOMAIN][DATA_RUNTIME]
    return await manager.async_get_map_render_data(
        vacuum_entity_id=call.data["vacuum_entity_id"]
    )


async def _handle_get_map_live_pose(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the live moving-overlay pose (robot/dock/current-room) from the fork's
    in-memory coordinator — the lightweight payload the card polls at the ~2s cadence."""
    manager = hass.data[DOMAIN][DATA_RUNTIME]
    return await manager.async_get_map_live_pose(
        vacuum_entity_id=call.data["vacuum_entity_id"]
    )


async def _handle_compare_map_sources(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Verify probe: compare the fork's in-memory _map_data against the .storage map_data
    (byte-identical check) before repointing the map source to memory."""
    manager = hass.data[DOMAIN][DATA_RUNTIME]
    return await manager.async_compare_map_sources(
        vacuum_entity_id=call.data["vacuum_entity_id"]
    )


# ===========================================================================
# THROWAWAY DIAGNOSTIC — Wave 0 of the native-transition design
# (docs/dev/eufy-native-transition.md). REMOVE after the validation recording.
#
# Question it answers: is the inferred live `current_room` fresh + non-flickering
# during a real run WITH NO CARD OPEN? It runs server-side (so the card's ~2s UI
# poll is NOT keeping the signal warm) and logs the SAME `async_get_map_live_pose`
# payload the card reads, one line per tick, to a JSONL file in the config dir.
# Read three numbers off it: (1) refresh actually happening server-side,
# (2) doorway/transit flicker rate, (3) None-while-cleaning frequency.
# ===========================================================================

# Active probe tasks, keyed by vacuum entity id (so a second call can stop/restart).
_LIVE_ROOM_PROBE_TASKS: dict[str, asyncio.Task] = {}

DEBUG_LOG_LIVE_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("interval_seconds", default=2.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.5, max=60.0)
        ),
        vol.Optional("duration_minutes", default=30): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=180)
        ),
        vol.Optional("stop", default=False): cv.boolean,
    }
)


def _append_jsonl(path: str, obj: dict) -> None:
    """Append one JSON line (sync — runs in the executor, never on the loop)."""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj) + "\n")


async def _handle_debug_log_live_room(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Start (or stop) a server-side per-tick logger of the live current_room signal.

    THROWAWAY — see the banner above. Call with stop: true to cancel early; otherwise it
    auto-stops after duration_minutes. Restarting cancels any prior probe for the vacuum.
    """
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    stop: bool = call.data["stop"]

    # Cancel any in-flight probe for this vacuum first (restart or stop both want this).
    existing = _LIVE_ROOM_PROBE_TASKS.pop(vacuum_entity_id, None)
    if existing is not None and not existing.done():
        existing.cancel()
    if stop:
        return {"stopped": True, "vacuum_entity_id": vacuum_entity_id}

    interval: float = float(call.data["interval_seconds"])
    duration_minutes: int = int(call.data["duration_minutes"])
    duration_s = duration_minutes * 60
    manager = hass.data[DOMAIN][DATA_RUNTIME]
    path = hass.config.path(
        f"eufy_current_room_probe_{vacuum_entity_id.replace('.', '_')}.jsonl"
    )
    oid = vacuum_entity_id.split(".", 1)[-1]   # for the device sensors below

    def _sensor_num(suffix):
        s = hass.states.get(f"sensor.{oid}_{suffix}")
        try:
            return float(s.state) if s is not None else None
        except (TypeError, ValueError):
            return None

    def _sensor_str(suffix):
        s = hass.states.get(f"sensor.{oid}_{suffix}")
        return s.state if s is not None else None

    await hass.async_add_executor_job(
        _append_jsonl, path,
        {
            "kind": "meta", "vacuum": vacuum_entity_id, "started": utc_now_iso(),
            "interval_seconds": interval, "duration_minutes": duration_minutes,
            "note": "tab-CLOSED validation; read freshness/flicker/None-rate",
        },
    )

    async def _loop() -> None:
        start = time.monotonic()
        n = 0
        try:
            while time.monotonic() - start < duration_s:
                tick = utc_now_iso()
                try:
                    pose = await manager.async_get_map_live_pose(
                        vacuum_entity_id=vacuum_entity_id
                    )
                except Exception as err:  # a probe must never crash a real run
                    pose = {"present": False, "reason": f"probe_error:{err!r}"}
                # Log only the small fields (skip the verbose `path` trail).
                await hass.async_add_executor_job(
                    _append_jsonl, path,
                    {
                        "kind": "sample", "t": tick, "i": n,
                        "present": bool(pose.get("present")),
                        "reason": pose.get("reason"),
                        "current_room": pose.get("current_room"),
                        "robot_docked": pose.get("robot_docked", False),
                        "robot_anchor": pose.get("robot_anchor"),
                        "robot_heading": pose.get("robot_heading"),
                        # Device signals for the room-attribution classifier: swept-area is the
                        # REQUIRED clean-vs-parked separator (a wash/park sweeps ~0 m^2); the
                        # status fields timestamp the washes. See room_attribution.py.
                        "cleaning_area": _sensor_num("cleaning_area"),
                        "cleaning_time": _sensor_num("cleaning_time"),
                        "task_status": _sensor_str("task_status"),
                        "dock_status": _sensor_str("dock_status"),
                        "diagnostics": pose.get("diagnostics"),
                    },
                )
                n += 1
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        finally:
            _LIVE_ROOM_PROBE_TASKS.pop(vacuum_entity_id, None)
            try:
                await hass.async_add_executor_job(
                    _append_jsonl, path,
                    {"kind": "end", "ended": utc_now_iso(), "samples": n},
                )
            except Exception:  # executor may be gone on shutdown — best-effort
                pass

    task = hass.async_create_background_task(
        _loop(), name=f"eufy_live_room_probe:{vacuum_entity_id}"
    )
    _LIVE_ROOM_PROBE_TASKS[vacuum_entity_id] = task
    return {
        "started": True, "vacuum_entity_id": vacuum_entity_id, "path": path,
        "interval_seconds": interval, "duration_minutes": duration_minutes,
    }


# ---------------------------------------------------------------------------
# Custom layout CRUD
# ---------------------------------------------------------------------------


async def _handle_create_custom_layout(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Create + activate a new named custom layout (empty stores, per-layout
    backdrop variant) and flip the map into custom mode so it goes live."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    name: str = str(call.data.get("name") or "").strip() or "Custom"
    backdrop_source: str | None = str(call.data.get("backdrop_source") or "").strip() or None

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layout = _create_layout(map_bucket, name, backdrop_source=backdrop_source)
    map_bucket["segmentation_mode"] = "custom"
    await manager.async_save()
    _LOGGER.debug("create_custom_layout: %s/%s -> %s", vacuum_entity_id, map_id, layout["id"])
    return {"saved": True, "layout_id": layout["id"], "layout": dict(layout)}


async def _handle_rename_custom_layout(hass: HomeAssistant, call: ServiceCall) -> dict:
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    layout_id: str = call.data["layout_id"]
    name: str = str(call.data["name"]).strip()
    if not name:
        return {"saved": False, "reason": "missing_name"}

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layout = (map_bucket.get("custom_layouts") or {}).get(layout_id)
    if not isinstance(layout, dict):
        return {"saved": False, "reason": "layout_not_found"}
    layout["name"] = name
    layout["updated_at"] = utc_now_iso()
    await manager.async_save()
    return {"saved": True, "layout_id": layout_id, "layout": dict(layout)}


async def _handle_delete_custom_layout(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete a custom layout. Best-effort removes its backdrop file/variant; when
    the active layout is deleted, reassigns to the first remaining (by name) — or
    flips back to CV when none remain (so custom mode never has no store)."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    layout_id: str = call.data["layout_id"]

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layouts = map_bucket.get("custom_layouts") or {}
    layout = layouts.get(layout_id)
    if not isinstance(layout, dict):
        return {"saved": False, "reason": "layout_not_found"}

    variant = layout.get("backdrop_variant")
    meta = (map_bucket.get("image_variants") or {}).pop(variant, None) if variant else None
    if isinstance(meta, dict) and meta.get("path"):
        try:
            await hass.async_add_executor_job(os.remove, meta["path"])
        except OSError:
            pass

    # Furnished custom render (Wave 0): also sweep the layout's furnished-art files (the
    # whole-home art + each per-room art) so they don't orphan on disk. Best-effort, same
    # try/except as the backdrop removal above.
    art_variants: list[str] = []
    home_art = layout.get("home_art")
    if isinstance(home_art, dict) and home_art.get("art_variant"):
        art_variants.append(home_art["art_variant"])
    rooms = layout.get("rooms")
    if isinstance(rooms, dict):
        for room in rooms.values():
            if isinstance(room, dict) and room.get("art_variant"):
                art_variants.append(room["art_variant"])
    for art_variant in art_variants:
        art_meta = (map_bucket.get("image_variants") or {}).pop(art_variant, None)
        if isinstance(art_meta, dict) and art_meta.get("path"):
            try:
                await hass.async_add_executor_job(os.remove, art_meta["path"])
            except OSError:
                pass

    layouts.pop(layout_id, None)

    if map_bucket.get("active_custom_layout_id") == layout_id:
        remaining = sorted(
            (lay for lay in layouts.values() if isinstance(lay, dict)),
            key=lambda lay: str(lay.get("name") or ""),
        )
        if remaining:
            map_bucket["active_custom_layout_id"] = remaining[0].get("id")
        else:
            map_bucket["active_custom_layout_id"] = None
            if map_bucket.get("segmentation_mode") == "custom":
                map_bucket["segmentation_mode"] = "cv"

    await manager.async_save()
    return {
        "saved": True,
        "deleted": True,
        "layout_id": layout_id,
        "active_custom_layout_id": map_bucket.get("active_custom_layout_id"),
        "segmentation_mode": map_bucket.get("segmentation_mode") or "cv",
    }


async def _handle_set_active_custom_layout(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Activate a custom layout (+ flip to custom mode). A null/unknown target
    auto-creates a default layout, so custom mode always resolves a live store."""
    vacuum_entity_id: str = call.data["vacuum_entity_id"]
    map_id: str = call.data["map_id"]
    layout_id = call.data.get("layout_id")

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=vacuum_entity_id, map_id=map_id,
    )
    _migrate_custom_layouts(map_bucket)
    layouts = map_bucket.get("custom_layouts") or {}
    if layout_id and isinstance(layouts.get(layout_id), dict):
        map_bucket["active_custom_layout_id"] = layout_id
    else:
        _create_layout(map_bucket, "Custom")
    map_bucket["segmentation_mode"] = "custom"
    await manager.async_save()
    return {
        "saved": True,
        "active_custom_layout_id": map_bucket.get("active_custom_layout_id"),
        "mode": map_bucket.get("segmentation_mode"),
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def async_register_mapping_services(hass: HomeAssistant) -> None:
    """Register all mapping services."""

    async def handle_save_map_image(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.save_map_image(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                image_base64=call.data["image_base64"],
                image_width=call.data.get("image_width"),
                image_height=call.data.get("image_height"),
                variant=call.data.get("variant", "primary"),
            )
        )
        _LOGGER.info("save_map_image: %s", result)
        return result

    async def handle_start_room_boundary_trace(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = mgr.start_room_boundary_trace(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            room_id=call.data["room_id"],
        )
        _LOGGER.info("start_room_boundary_trace: %s", result)
        return result

    async def handle_close_room_boundary(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        map_id = call.data["map_id"]
        room_id = call.data["room_id"]

        result = await hass.async_add_executor_job(
            lambda: mgr.close_room_boundary(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                room_id=room_id,
                epsilon=call.data.get("epsilon", 5.0),
            )
        )
        _LOGGER.info("close_room_boundary: %s", result)

        if result.get("closed"):
            room_name = _get_room_name(hass, vacuum_entity_id, map_id, room_id)
            hass.bus.async_fire(
                EVENT_BOUNDARY_SAVED,
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "room_id": str(room_id),
                    "room_name": room_name,
                    "point_count": result["point_count_simplified"],
                },
            )

        return result

    async def handle_cancel_room_boundary_trace(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = mgr.cancel_room_boundary_trace(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            room_id=call.data["room_id"],
        )
        _LOGGER.info("cancel_room_boundary_trace: %s", result)
        return result

    async def handle_get_mapping_state(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = mgr.get_mapping_state(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
        )
        return result

    async def handle_save_mapping_package(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.save_mapping_package(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                package=call.data["package"],
            )
        )
        _LOGGER.info("save_mapping_package: %s", result)
        return result

    async def handle_append_mapping_trace_evidence(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.append_mapping_trace_evidence(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                evidence=call.data["evidence"],
            )
        )
        _LOGGER.info("append_mapping_trace_evidence: %s", result)
        return result

    async def handle_get_mapping_package(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        return mgr.get_mapping_package(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
        )

    async def handle_get_image_segment_suggestions(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        return await hass.async_add_executor_job(
            lambda: mgr.get_image_segment_suggestions(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                min_area_pixels=call.data.get("min_area_pixels", 1200),
                simplify_epsilon=call.data.get("simplify_epsilon"),
                max_segments=call.data.get("max_segments"),
            )
        )

    async def handle_translate_image_segment(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.translate_image_segment(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                segment_id=call.data["segment_id"],
                delta_x=call.data.get("delta_x", 0),
                delta_y=call.data.get("delta_y", 0),
                edge_left=call.data.get("edge_left", 0),
                edge_right=call.data.get("edge_right", 0),
                edge_top=call.data.get("edge_top", 0),
                edge_bottom=call.data.get("edge_bottom", 0),
                vertex_moves=call.data.get("vertex_moves", []),
            )
        )
        _LOGGER.info("translate_image_segment: %s", result)
        return result

    async def handle_set_dock_anchor(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.set_dock_anchor(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                pixel_x=call.data["pixel_x"],
                pixel_y=call.data["pixel_y"],
                vacuum_x=call.data.get("vacuum_x"),
                vacuum_y=call.data.get("vacuum_y"),
                exclusion_radius=call.data.get("exclusion_radius"),
                notes=call.data.get("notes"),
            )
        )
        _LOGGER.info("set_dock_anchor: %s", result)
        return result

    async def handle_set_dock_room(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.set_dock_room(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                room_id=call.data["room_id"],
                notes=call.data.get("notes"),
            )
        )
        _LOGGER.info("set_dock_room: %s", result)
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_MAP_IMAGE,
        handle_save_map_image,
        schema=SAVE_MAP_IMAGE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_ROOM_BOUNDARY_TRACE,
        handle_start_room_boundary_trace,
        schema=START_ROOM_BOUNDARY_TRACE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLOSE_ROOM_BOUNDARY,
        handle_close_room_boundary,
        schema=CLOSE_ROOM_BOUNDARY_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
        handle_cancel_room_boundary_trace,
        schema=CANCEL_ROOM_BOUNDARY_TRACE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_MAPPING_STATE,
        handle_get_mapping_state,
        schema=GET_MAPPING_STATE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_MAPPING_PACKAGE,
        handle_save_mapping_package,
        schema=SAVE_MAPPING_PACKAGE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
        handle_append_mapping_trace_evidence,
        schema=APPEND_MAPPING_TRACE_EVIDENCE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_MAPPING_PACKAGE,
        handle_get_mapping_package,
        schema=GET_MAPPING_STATE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_IMAGE_SEGMENT_SUGGESTIONS,
        handle_get_image_segment_suggestions,
        schema=GET_IMAGE_SEGMENT_SUGGESTIONS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TRANSLATE_IMAGE_SEGMENT,
        handle_translate_image_segment,
        schema=TRANSLATE_IMAGE_SEGMENT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_DOCK_ANCHOR,
        handle_set_dock_anchor,
        schema=SET_DOCK_ANCHOR_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_DOCK_ROOM,
        handle_set_dock_room,
        schema=SET_DOCK_ROOM_SCHEMA,
        supports_response=True,
    )


    # ------------------------------------------------------------------
    # Phase 1 — raw trace capture
    # ------------------------------------------------------------------

    async def handle_start_trace_capture(call: ServiceCall) -> dict[str, Any]:
        """Start a raw trace capture session for the given vacuum/map pair.

        room_id is optional — room association is resolved in a later phase.
        A pre-existing session for this pair is discarded; the caller is
        informed via previous_cancelled in the return payload.
        """
        mgr = _get_mapping_manager(hass)
        result = mgr.start_trace_capture(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
            room_id=call.data.get("room_id"),
        )
        _LOGGER.info("start_trace_capture: %s", result)
        return result

    async def handle_stop_trace_capture(call: ServiceCall) -> dict[str, Any]:
        """Finalise and persist the active TraceRun. Returns stopped=False if no session is active."""
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.stop_trace_capture(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
            )
        )
        _LOGGER.info("stop_trace_capture: %s", result)
        return result

    async def handle_cancel_trace_capture(call: ServiceCall) -> dict[str, Any]:
        """Discard the active session without writing. Returns cancelled=False if no session is active."""
        mgr = _get_mapping_manager(hass)
        result = mgr.cancel_trace_capture(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            map_id=call.data["map_id"],
        )
        _LOGGER.info("cancel_trace_capture: %s", result)
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_START_TRACE_CAPTURE,
        handle_start_trace_capture,
        schema=START_TRACE_CAPTURE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_TRACE_CAPTURE,
        handle_stop_trace_capture,
        schema=STOP_TRACE_CAPTURE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_TRACE_CAPTURE,
        handle_cancel_trace_capture,
        schema=CANCEL_TRACE_CAPTURE_SCHEMA,
        supports_response=True,
    )


    # ------------------------------------------------------------------
    # Phase 2 — coarse trace run review
    # ------------------------------------------------------------------

    async def handle_review_trace_run(call: ServiceCall) -> dict[str, Any]:
        """Evaluate a stored TraceRun against a room's vacuum polygon.

        Returns a verdict (accepted / needs_refine / rejected / error) with
        full diagnostics. When segment_metadata is supplied it must be the
        segment dict from get_image_segment_suggestions for the assigned room;
        it adjusts polygon trustworthiness thresholds. Does not persist.
        """
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.review_trace_run_for_room(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                run_id=call.data["run_id"],
                room_id=call.data["room_id"],
                segment_metadata=call.data.get("segment_metadata"),
            )
        )
        diag = result.get("diagnostics") or {}
        _LOGGER.info(
            "review_trace_run: %s verdict=%s inside_ratio=%s effective_accept=%s adjustments=%s",
            call.data["run_id"],
            result.get("verdict"),
            diag.get("inside_ratio"),
            diag.get("effective_accept_threshold"),
            diag.get("metadata_adjustments"),
        )
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_REVIEW_TRACE_RUN,
        handle_review_trace_run,
        schema=REVIEW_TRACE_RUN_SCHEMA,
        supports_response=True,
    )


    # ------------------------------------------------------------------
    # Image analysis services
    # ------------------------------------------------------------------

    async def upload_map_image(call: ServiceCall) -> dict:
        return await _handle_upload_map_image(hass, call)

    async def analyze_map_image(call: ServiceCall) -> dict:
        return await _handle_analyze_map_image(hass, call)

    async def get_map_segments(call: ServiceCall) -> dict:
        return await _handle_get_map_segments(hass, call)

    async def adjust_map_segment(call: ServiceCall) -> dict:
        return await _handle_adjust_map_segment(hass, call)

    async def set_segment_room_link(call: ServiceCall) -> dict:
        return await _handle_set_segment_room_link(hass, call)

    async def set_companion_anchor(call: ServiceCall) -> dict:
        return await _handle_set_companion_anchor(hass, call)

    async def set_hidden_regions(call: ServiceCall) -> dict:
        return await _handle_set_hidden_regions(hass, call)

    async def set_area_label_anchor(call: ServiceCall) -> dict:
        return await _handle_set_area_label_anchor(hass, call)

    async def set_live_map_rotation(call: ServiceCall) -> dict:
        return await _handle_set_live_map_rotation(hass, call)

    async def set_map_overlay_visibility(call: ServiceCall) -> dict:
        return await _handle_set_map_overlay_visibility(hass, call)

    async def get_map_render_data(call: ServiceCall) -> dict:
        return await _handle_get_map_render_data(hass, call)

    async def get_map_live_pose(call: ServiceCall) -> dict:
        return await _handle_get_map_live_pose(hass, call)

    async def compare_map_sources(call: ServiceCall) -> dict:
        return await _handle_compare_map_sources(hass, call)

    async def set_segmentation_mode(call: ServiceCall) -> dict:
        return await _handle_set_segmentation_mode(hass, call)

    async def set_custom_segments(call: ServiceCall) -> dict:
        return await _handle_set_custom_segments(hass, call)

    async def create_custom_layout(call: ServiceCall) -> dict:
        return await _handle_create_custom_layout(hass, call)

    async def rename_custom_layout(call: ServiceCall) -> dict:
        return await _handle_rename_custom_layout(hass, call)

    async def delete_custom_layout(call: ServiceCall) -> dict:
        return await _handle_delete_custom_layout(hass, call)

    async def set_active_custom_layout(call: ServiceCall) -> dict:
        return await _handle_set_active_custom_layout(hass, call)

    async def set_furnished_art_placement(call: ServiceCall) -> dict:
        return await _handle_set_furnished_art_placement(hass, call)

    async def set_furnished_render_mode(call: ServiceCall) -> dict:
        return await _handle_set_furnished_render_mode(hass, call)

    async def set_room_viewport(call: ServiceCall) -> dict:
        return await _handle_set_room_viewport(hass, call)

    async def delete_map_image(call: ServiceCall) -> dict:
        return await _handle_delete_map_image(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_UPLOAD_MAP_IMAGE, upload_map_image,
        schema=UPLOAD_MAP_IMAGE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_MAP_IMAGE, delete_map_image,
        schema=DELETE_MAP_IMAGE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE, analyze_map_image,
        schema=ANALYZE_MAP_IMAGE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_MAP_SEGMENTS, get_map_segments,
        schema=GET_MAP_SEGMENTS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SEGMENTATION_MODE, set_segmentation_mode,
        schema=SET_SEGMENTATION_MODE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CUSTOM_SEGMENTS, set_custom_segments,
        schema=SET_CUSTOM_SEGMENTS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADJUST_MAP_SEGMENT, adjust_map_segment,
        schema=ADJUST_MAP_SEGMENT_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SEGMENT_ROOM_LINK, set_segment_room_link,
        schema=SET_SEGMENT_ROOM_LINK_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_COMPANION_ANCHOR, set_companion_anchor,
        schema=SET_COMPANION_ANCHOR_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_HIDDEN_REGIONS, set_hidden_regions,
        schema=SET_HIDDEN_REGIONS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_AREA_LABEL_ANCHOR, set_area_label_anchor,
        schema=SET_AREA_LABEL_ANCHOR_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_LIVE_MAP_ROTATION, set_live_map_rotation,
        schema=SET_LIVE_MAP_ROTATION_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_MAP_OVERLAY_VISIBILITY, set_map_overlay_visibility,
        schema=SET_MAP_OVERLAY_VISIBILITY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_MAP_RENDER_DATA, get_map_render_data,
        schema=GET_MAP_RENDER_DATA_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_MAP_LIVE_POSE, get_map_live_pose,
        schema=GET_MAP_RENDER_DATA_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COMPARE_MAP_SOURCES, compare_map_sources,
        schema=GET_MAP_RENDER_DATA_SCHEMA, supports_response=True,
    )

    # THROWAWAY DIAGNOSTIC (Wave 0, eufy-native-transition) — remove after validation.
    async def debug_log_live_room(call: ServiceCall) -> dict:
        return await _handle_debug_log_live_room(hass, call)

    hass.services.async_register(
        DOMAIN, "debug_log_live_room", debug_log_live_room,
        schema=DEBUG_LOG_LIVE_ROOM_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_CUSTOM_LAYOUT, create_custom_layout,
        schema=CREATE_CUSTOM_LAYOUT_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RENAME_CUSTOM_LAYOUT, rename_custom_layout,
        schema=RENAME_CUSTOM_LAYOUT_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_CUSTOM_LAYOUT, delete_custom_layout,
        schema=DELETE_CUSTOM_LAYOUT_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT, set_active_custom_layout,
        schema=SET_ACTIVE_CUSTOM_LAYOUT_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FURNISHED_ART_PLACEMENT, set_furnished_art_placement,
        schema=SET_FURNISHED_ART_PLACEMENT_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FURNISHED_RENDER_MODE, set_furnished_render_mode,
        schema=SET_FURNISHED_RENDER_MODE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM_VIEWPORT, set_room_viewport,
        schema=SET_ROOM_VIEWPORT_SCHEMA, supports_response=True,
    )


    # ------------------------------------------------------------------
    # Bounds review
    # ------------------------------------------------------------------

    async def handle_get_room_bounds_snapshot(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        map_id = call.data["map_id"]
        result = mgr.get_room_bounds_snapshot(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        # Attach display name and archive flag from runtime room config.
        tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
        try:
            core = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
            if core is not None:
                managed = core.get_managed_rooms(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                ).get("rooms", {})
                for room_id, room_data in result.get("rooms", {}).items():
                    room_data["name"] = managed.get(str(room_id), {}).get("name") or f"Room {room_id}"
                    if tracker is not None:
                        room_data["has_archive"] = tracker._find_raw_samples_path(vacuum_entity_id, str(room_id)) is not None
                    else:
                        room_data["has_archive"] = False
        except Exception:
            _LOGGER.debug("get_room_bounds_snapshot: could not enrich room names")
        return result

    async def handle_clear_room_bounds(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.clear_room_bounds(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                room_id=call.data["room_id"],
            )
        )
        _LOGGER.info("clear_room_bounds: %s", result)
        return result

    async def handle_exclude_room_job_bounds(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.exclude_room_job_bounds(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                room_id=call.data["room_id"],
                job_index=call.data["job_index"],
            )
        )
        _LOGGER.info("exclude_room_job_bounds: %s", result)
        if result.get("success") and result.get("job_id"):
            tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
            if tracker is not None:
                await hass.async_add_executor_job(
                    tracker.update_raw_samples_exclusion,
                    call.data["vacuum_entity_id"],
                    call.data["room_id"],
                    result["job_id"],
                    True,
                )
        return result

    async def handle_restore_room_job_bounds(call: ServiceCall) -> dict[str, Any]:
        mgr = _get_mapping_manager(hass)
        result = await hass.async_add_executor_job(
            lambda: mgr.restore_room_job_bounds(
                vacuum_entity_id=call.data["vacuum_entity_id"],
                map_id=call.data["map_id"],
                room_id=call.data["room_id"],
                job_index=call.data["job_index"],
            )
        )
        _LOGGER.info("restore_room_job_bounds: %s", result)
        if result.get("success") and result.get("job_id"):
            tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
            if tracker is not None:
                await hass.async_add_executor_job(
                    tracker.update_raw_samples_exclusion,
                    call.data["vacuum_entity_id"],
                    call.data["room_id"],
                    result["job_id"],
                    False,
                )
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
        handle_get_room_bounds_snapshot,
        schema=GET_ROOM_BOUNDS_SNAPSHOT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_ROOM_BOUNDS,
        handle_clear_room_bounds,
        schema=CLEAR_ROOM_BOUNDS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
        handle_exclude_room_job_bounds,
        schema=EXCLUDE_ROOM_JOB_BOUNDS_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE_ROOM_JOB_BOUNDS,
        handle_restore_room_job_bounds,
        schema=RESTORE_ROOM_JOB_BOUNDS_SCHEMA,
        supports_response=True,
    )

    async def handle_rebuild_room_bounds(call: ServiceCall) -> dict[str, Any]:
        tracker = hass.data.get(DOMAIN, {}).get("mapping_tracker")
        if tracker is None:
            return {"success": False, "reason": "tracker_unavailable"}
        vacuum_entity_id = call.data["vacuum_entity_id"]
        map_id = call.data["map_id"]
        room_id = call.data["room_id"]
        result = await hass.async_add_executor_job(
            lambda: tracker.rebuild_room_bounds_from_archive(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                room_id=room_id,
            )
        )
        _LOGGER.info("rebuild_room_bounds_from_archive: %s", result)
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_REBUILD_ROOM_BOUNDS,
        handle_rebuild_room_bounds,
        schema=REBUILD_ROOM_BOUNDS_SCHEMA,
        supports_response=True,
    )


async def async_unregister_mapping_services(hass: HomeAssistant) -> None:
    """Unregister all mapping services."""
    for service in ALL_MAPPING_SERVICES:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
