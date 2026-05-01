"""Evaluates whether a stored TraceRun is clean enough for transform fitting."""

from __future__ import annotations

import math
from typing import Any

from ..timestamp_utils import utc_now_iso
from .boundary import point_in_polygon

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# in_room_ratio >= this → candidate for acceptance (before other checks)
ACCEPT_IN_ROOM_RATIO = 0.70

# in_room_ratio <= this → outright rejection
# Below this the robot was mostly elsewhere regardless of other signals.
REJECT_IN_ROOM_RATIO = 0.30

# transit_ratio > this → cannot be accepted even with good in_room_ratio.
# A high transit fraction means the robot was passing through.
# Set loose — some transit is normal at room entry/exit.
TRANSIT_RATIO_CEILING = 0.20

# entry_exit_ratio > this → needs_refine (dirty ends, but core may be clean)
ENTRY_EXIT_CEILING = 0.35

# Fraction of samples at each end considered "entry/exit zone".
# 0.12 = first 12% and last 12% of samples are the entry/exit windows.
ENTRY_EXIT_WINDOW_FRACTION = 0.12

# spatial_spread >= this → spread is acceptable for transform fitting
ACCEPT_SPREAD_RATIO = 0.25

# spatial_spread < this → spread is too poor even if in_room_ratio is good.
# A run that only covers one corner cannot fit a transform for the whole room.
REJECT_SPREAD_RATIO = 0.08

# Radius for local density computation, in vacuum units.
DENSITY_RADIUS = 40.0

# Minimum samples required to produce a verdict.
MIN_SAMPLES_FOR_REVIEW = 10

# Threshold adjustments from segment metadata.
STRONG_GEOMETRY_BONUS = 0.08
SUSPICIOUS_GEOMETRY_PENALTY = 0.10
MIN_CONFIDENCE_FOR_BONUS = 0.75


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _polygon_bbox(polygon: list[list[float]]) -> tuple[float, float, float, float] | None:
    """Return (min_x, min_y, max_x, max_y) or None if polygon is empty."""
    if not polygon:
        return None
    xs = [float(p[0]) for p in polygon]
    ys = [float(p[1]) for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    """Return the area of an axis-aligned bounding box."""
    min_x, min_y, max_x, max_y = bbox
    w = max(0.0, max_x - min_x)
    h = max(0.0, max_y - min_y)
    return w * h


def _compute_spatial_spread(
    inside_points: list[tuple[float, float]],
    polygon: list[list[float]],
) -> float:
    """Return the fraction of the polygon's bounding box spanned by inside-sample positions.

    Returns 0.0 if no inside points or the polygon bbox has zero area;
    1.0 if inside samples span the full polygon bbox.

    # WHY bounding-box ratio: O(n), shape-agnostic, directly answers "did the robot
    # move around the whole room or stay in one corner?" — sufficient for transform quality.
    """
    if not inside_points:
        return 0.0

    poly_bbox = _polygon_bbox(polygon)
    if poly_bbox is None:
        return 0.0
    poly_area = _bbox_area(poly_bbox)
    if poly_area <= 0:
        return 0.0

    xs = [p[0] for p in inside_points]
    ys = [p[1] for p in inside_points]
    sample_bbox = (min(xs), min(ys), max(xs), max(ys))
    sample_area = _bbox_area(sample_bbox)

    return round(min(1.0, sample_area / poly_area), 4)


def _compute_path_density_inside(
    inside_points: list[tuple[float, float]],
    radius: float,
) -> float:
    """Mean local density of inside samples within radius.

    Returns 0.0 if fewer than 2 inside points.
    O(n²) over inside points only — acceptable for review sizes.
    """
    n = len(inside_points)
    if n < 2:
        return 0.0

    r2 = radius * radius
    total = 0
    for i in range(n):
        xi, yi = inside_points[i]
        count = 0
        for j in range(n):
            if i == j:
                continue
            dx = inside_points[j][0] - xi
            dy = inside_points[j][1] - yi
            if dx * dx + dy * dy <= r2:
                count += 1
        total += count

    return round(total / n, 4)


def _compute_entry_exit_ratio(
    membership: list[bool],
    window_fraction: float,
) -> float:
    """Return the fraction of samples in the leading and trailing windows that are outside the polygon.

    # WHY ends-only: run starts/ends with a short outside segment (dock approach) that is
    # salvageable by Phase 3 trimming; separating this from mid-run transit prevents
    # incorrectly rejecting clean runs that just have dirty entry/exit.
    """
    n = len(membership)
    if n < 2:
        return 0.0

    window = max(1, int(n * window_fraction))
    end_samples = membership[:window] + membership[n - window:]
    if not end_samples:
        return 0.0

    outside_in_ends = sum(1 for m in end_samples if not m)
    return round(outside_in_ends / len(end_samples), 4)


def _compute_transit_ratio(
    membership: list[bool],
    window_fraction: float,
) -> float:
    """Fraction of middle-zone samples that are outside the polygon.

    Middle zone excludes the entry/exit windows at each end.
    Outside samples in the middle are transit — robot left the room
    and came back, or passed through a connected area.

    A high transit ratio with a decent in_room_ratio means the run
    contains real room data but is contaminated mid-run.
    """
    n = len(membership)
    if n < 2:
        return 0.0

    window = max(1, int(n * window_fraction))
    middle = membership[window: n - window]
    if not middle:
        return 0.0

    outside_in_middle = sum(1 for m in middle if not m)
    return round(outside_in_middle / len(middle), 4)


def _count_boundary_crossings(membership: list[bool]) -> int:
    """Count the number of inside↔outside state transitions."""
    crossings = 0
    for i in range(1, len(membership)):
        if membership[i] != membership[i - 1]:
            crossings += 1
    return crossings


# ---------------------------------------------------------------------------
# Segment metadata interpretation
# ---------------------------------------------------------------------------

def _evaluate_segment_metadata(
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Derive accept threshold adjustments from optional segment metadata.

    Metadata reflects polygon trustworthiness, not trace quality.
    Strong reliable polygons allow easier acceptance. Suspicious
    polygons require stronger trace evidence.

    Returns:
      accept_delta:       float   — add to ACCEPT_IN_ROOM_RATIO
                                    (negative = easier to accept)
      force_needs_refine: bool    — True → ambiguous run must be needs_refine
      adjustments:        list[str]
      fields:             dict    — raw values, for diagnostics
    """
    result: dict[str, Any] = {
        "accept_delta": 0.0,
        "force_needs_refine": False,
        "adjustments": [],
        "fields": {
            "segment_quality": None,
            "segment_confidence": None,
            "segment_structural_role": None,
            "segment_state": None,
            "local_split_suspicion": None,
            "edit_readiness": None,
        },
    }

    if not isinstance(metadata, dict):
        return result

    quality = str(metadata.get("quality") or "").strip().lower()
    structural_role = str(metadata.get("structural_role") or "").strip().lower()
    segmentation_state = str(metadata.get("segmentation_state") or "").strip().lower()
    local_split_suspicion = metadata.get("local_split_suspicion")
    edit_readiness = str(metadata.get("edit_readiness") or "").strip().lower()

    try:
        confidence = float(metadata["confidence"]) if metadata.get("confidence") is not None else None
    except (TypeError, ValueError):
        confidence = None

    result["fields"].update({
        "segment_quality": quality or None,
        "segment_confidence": confidence,
        "segment_structural_role": structural_role or None,
        "segment_state": segmentation_state or None,
        "local_split_suspicion": bool(local_split_suspicion) if local_split_suspicion is not None else None,
        "edit_readiness": edit_readiness or None,
    })

    # Strong polygon bonus — lowers the accept threshold.
    # Requires quality label, sufficient confidence, and edit_readiness.
    if (
        quality in {"strong", "good"}
        and confidence is not None
        and confidence >= MIN_CONFIDENCE_FOR_BONUS
        and edit_readiness != "review"
    ):
        result["accept_delta"] -= STRONG_GEOMETRY_BONUS
        result["adjustments"].append(
            f"strong_geometry_bonus:-{STRONG_GEOMETRY_BONUS}"
            f"(quality={quality},confidence={confidence:.2f})"
        )

    # Suspicious polygon penalty — raises accept threshold.
    # Hub/spine/connector roles and merged/fragmented states indicate
    # the polygon may over-extend or represent multiple rooms.
    if structural_role in {"hub", "spine", "connector"}:
        result["accept_delta"] += SUSPICIOUS_GEOMETRY_PENALTY
        result["force_needs_refine"] = True
        result["adjustments"].append(
            f"suspicious_role:+{SUSPICIOUS_GEOMETRY_PENALTY}(role={structural_role})"
        )

    if segmentation_state in {"merged_candidate", "fragmented_candidate"}:
        result["accept_delta"] += SUSPICIOUS_GEOMETRY_PENALTY
        result["force_needs_refine"] = True
        result["adjustments"].append(
            f"suspicious_state:+{SUSPICIOUS_GEOMETRY_PENALTY}(state={segmentation_state})"
        )

    # local_split_suspicion alone → force needs_refine, no threshold change.
    if (
        bool(local_split_suspicion)
        and structural_role not in {"hub", "spine", "connector"}
        and segmentation_state not in {"merged_candidate", "fragmented_candidate"}
    ):
        result["force_needs_refine"] = True
        result["adjustments"].append("local_split_suspicion:force_needs_refine")

    return result


# ---------------------------------------------------------------------------
# Core review function
# ---------------------------------------------------------------------------

def review_trace_run(
    run: dict[str, Any],
    polygon_vacuum: list[list[float]],
    segment_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate whether a TraceRun is clean enough for transform fitting.

    Room linkage is assumed correct. This function does not question
    which room the run belongs to — it only measures trace quality.

    Parameters
    ----------
    run:
        Fully loaded TraceRun dict from trace_store.
        Must contain "samples": list of {x, y, ts} dicts.

    polygon_vacuum:
        Vacuum-space room boundary [[vx,vy],...] with >= 3 points.
        From data["rooms"][room_id]["boundary"].

    segment_metadata:
        Optional. Segment dict from get_image_segment_suggestions
        for the segment assigned to this room. Adjusts polygon
        trustworthiness. Caller-supplied — never fetched internally.

    Returns a RunReviewResult dict. Never raises.
    """
    run_id = str(run.get("run_id", "unknown"))
    vacuum_entity_id = str(run.get("vacuum_entity_id", ""))
    map_id = str(run.get("map_id", ""))
    room_id = str(run.get("room_id") or "")

    def _error(reason: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id,
            "room_id": room_id,
            "verdict": "error",
            "error": reason,
            "reviewed_at": utc_now_iso(),
            "diagnostics": None,
        }

    if not isinstance(polygon_vacuum, list) or len(polygon_vacuum) < 3:
        return _error("no_polygon")

    samples = run.get("samples")
    if not isinstance(samples, list):
        return _error("missing_samples")

    points: list[tuple[float, float]] = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        try:
            points.append((float(s["x"]), float(s["y"])))
        except (KeyError, TypeError, ValueError):
            continue

    if len(points) < MIN_SAMPLES_FOR_REVIEW:
        return _error(
            f"insufficient_samples:{len(points)}(minimum {MIN_SAMPLES_FOR_REVIEW})"
        )

    # ----------------------------------------------------------------
    # Compute per-sample polygon membership — basis for all signals.
    # ----------------------------------------------------------------
    membership: list[bool] = [
        point_in_polygon(pt, polygon_vacuum) for pt in points
    ]

    in_room_count = sum(membership)
    in_room_ratio = round(in_room_count / len(points), 4)

    inside_points: list[tuple[float, float]] = [
        pt for pt, m in zip(points, membership) if m
    ]

    # ----------------------------------------------------------------
    # Compute trace quality diagnostics.
    # ----------------------------------------------------------------
    transit_ratio = _compute_transit_ratio(membership, ENTRY_EXIT_WINDOW_FRACTION)
    entry_exit_ratio = _compute_entry_exit_ratio(membership, ENTRY_EXIT_WINDOW_FRACTION)
    path_density_inside = _compute_path_density_inside(inside_points, DENSITY_RADIUS)
    spatial_spread = _compute_spatial_spread(inside_points, polygon_vacuum)
    boundary_crossing_count = _count_boundary_crossings(membership)

    # ----------------------------------------------------------------
    # Segment metadata adjustments (polygon trustworthiness only).
    # ----------------------------------------------------------------
    meta_eval = _evaluate_segment_metadata(segment_metadata)
    accept_delta = meta_eval["accept_delta"]
    force_needs_refine = meta_eval["force_needs_refine"]

    effective_accept = round(
        max(REJECT_IN_ROOM_RATIO + 0.05, ACCEPT_IN_ROOM_RATIO + accept_delta),
        4,
    )
    effective_reject = REJECT_IN_ROOM_RATIO  # never adjusted

    # ----------------------------------------------------------------
    # Verdict — composite of multiple quality signals.
    # ----------------------------------------------------------------
    reject_reasons: list[str] = []

    # Hard rejection: mostly outside the room.
    if in_room_ratio <= effective_reject:
        reject_reasons.append(f"in_room_ratio:{in_room_ratio}<=reject:{effective_reject}")

    # Hard rejection: negligible spatial spread even if in_room_ratio passes.
    # A transform cannot be fit from a run that only covers one corner.
    if spatial_spread < REJECT_SPREAD_RATIO and in_room_ratio < effective_accept:
        reject_reasons.append(f"spatial_spread:{spatial_spread}<reject:{REJECT_SPREAD_RATIO}")

    if reject_reasons:
        verdict = "rejected"
    elif (
        in_room_ratio >= effective_accept
        and transit_ratio <= TRANSIT_RATIO_CEILING
        and spatial_spread >= ACCEPT_SPREAD_RATIO
        and entry_exit_ratio <= ENTRY_EXIT_CEILING
        and not force_needs_refine
    ):
        verdict = "accepted"
    else:
        # Everything that is not clearly rejected or cleanly accepted
        # is needs_refine. This includes:
        # - Good in_room_ratio but high transit contamination mid-run
        # - Good in_room_ratio but dirty entry/exit ends (trimmable)
        # - Good in_room_ratio but poor spatial spread
        # - Suspicious polygon metadata forcing conservatism
        verdict = "needs_refine"

    return {
        "run_id": run_id,
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": map_id,
        "room_id": room_id,
        "verdict": verdict,
        "error": None,
        "reviewed_at": utc_now_iso(),
        "diagnostics": {
            "sample_count": len(points),
            "in_room_count": in_room_count,
            "in_room_ratio": in_room_ratio,
            "transit_ratio": transit_ratio,
            "entry_exit_ratio": entry_exit_ratio,
            "path_density_inside": path_density_inside,
            "spatial_spread": spatial_spread,
            "boundary_crossing_count": boundary_crossing_count,
            "polygon_point_count": len(polygon_vacuum),
            "effective_accept_threshold": effective_accept,
            "effective_reject_threshold": effective_reject,
            "metadata_adjustments": meta_eval["adjustments"],
            "reject_reasons": reject_reasons,
            "thresholds": {
                "base_accept_in_room": ACCEPT_IN_ROOM_RATIO,
                "base_reject_in_room": REJECT_IN_ROOM_RATIO,
                "transit_ceiling": TRANSIT_RATIO_CEILING,
                "entry_exit_ceiling": ENTRY_EXIT_CEILING,
                "spread_accept": ACCEPT_SPREAD_RATIO,
                "spread_reject": REJECT_SPREAD_RATIO,
                **meta_eval["fields"],
            },
        },
    }
