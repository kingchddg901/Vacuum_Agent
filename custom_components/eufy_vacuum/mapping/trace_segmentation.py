"""Splits a TraceRun into candidate behavioural segments using multi-signal analysis."""

from __future__ import annotations

import math
from typing import Any

from ..timestamp_utils import parse_timestamp
from .boundary import point_in_polygon

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

# Time gap that constitutes a hard pause between samples.
# 8 seconds: long enough to be unambiguous, short enough to catch
# repositioning pauses that occur between cleaning passes.
PAUSE_THRESHOLD_SECONDS = 8.0

# Number of consecutive samples a signal must be active before
# it counts as "sustained". Prevents single-sample noise from
# triggering a split. At ~2-5s per sample, 4 samples ≈ 8-20 seconds.
SUSTAIN_WINDOW = 4

# Speed drop fraction to trigger SPEED_CHANGE signal.
# Speed must drop to below this fraction of the recent baseline.
# 0.35 = dropped to less than 35% of recent speed → significant.
SPEED_CHANGE_RATIO = 0.35

# Density drop fraction to trigger DENSITY_CHANGE signal.
# Local density must drop to below this fraction of the recent baseline.
DENSITY_CHANGE_RATIO = 0.35

# Radius in vacuum units for local density computation.
# Should be roughly one robot-width of coverage overlap.
DENSITY_RADIUS = 40.0

# Minimum samples a segment must have after merging.
# Segments shorter than this are merged into their neighbor.
MIN_SEGMENT_SAMPLES = 15

# Speed and density similarity threshold for merge.
# Two adjacent segments whose means differ by less than this
# fraction are considered behaviourally the same and merged.
MERGE_SIMILARITY_THRESHOLD = 0.25

# Baseline window: how many recent samples to use for rolling mean.
BASELINE_WINDOW = 12

# Minimum speed in vacuum-units/second to compute meaningful ratios.
# Below this the robot is considered stationary regardless of signal.
MIN_SPEED_FOR_SIGNAL = 1.0

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_ts(value: Any) -> float | None:
    """Return a Unix timestamp float from an ISO string, or None."""
    if not value:
        return None
    dt = parse_timestamp(str(value))
    if dt is None:
        return None
    return dt.timestamp()


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2)


def _rolling_mean(values: list[float], window: int) -> list[float]:
    """Return per-index rolling mean of the last `window` values."""
    result: list[float] = []
    for i, v in enumerate(values):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def _local_density(
    samples: list[dict[str, Any]],
    radius: float,
) -> list[float]:
    """Return per-sample count of nearby samples within radius.

    O(n²) — acceptable for typical trace sizes (~hundreds to low thousands
    of samples). For very long traces this is the bottleneck, but
    segmentation is an offline operation, not a hot path.
    """
    n = len(samples)
    density = []
    xs = [float(s["x"]) for s in samples]
    ys = [float(s["y"]) for s in samples]
    r2 = radius * radius
    for i in range(n):
        count = 0
        xi, yi = xs[i], ys[i]
        for j in range(n):
            if i == j:
                continue
            dx = xs[j] - xi
            dy = ys[j] - yi
            if dx * dx + dy * dy <= r2:
                count += 1
        density.append(float(count))
    return density


def _extract_samples(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only structurally valid samples from a run."""
    raw = run.get("samples", [])
    if not isinstance(raw, list):
        return []
    valid = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        try:
            float(s["x"])
            float(s["y"])
            valid.append(s)
        except (KeyError, TypeError, ValueError):
            continue
    return valid


# ---------------------------------------------------------------------------
# Signal computation
# ---------------------------------------------------------------------------

def _compute_per_sample_signals(
    samples: list[dict[str, Any]],
    polygon_vacuum: list[list[float]] | None,
) -> dict[str, list[Any]]:
    """Compute all per-sample signals from raw samples.

    Returns a dict of parallel lists, each length == len(samples):
      speeds:        float | None    — vacuum-units/second
      time_gaps:     float | None    — seconds since previous sample
      density:       float           — local sample count in radius
      inside_polygon: bool | None    — None if no polygon supplied
    """
    n = len(samples)
    speeds: list[float | None] = [None] * n
    time_gaps: list[float | None] = [None] * n

    for i in range(1, n):
        ts_prev = _parse_ts(samples[i - 1].get("ts"))
        ts_curr = _parse_ts(samples[i].get("ts"))
        if ts_prev is not None and ts_curr is not None:
            dt = ts_curr - ts_prev
            if dt > 0:
                dx = float(samples[i]["x"]) - float(samples[i - 1]["x"])
                dy = float(samples[i]["y"]) - float(samples[i - 1]["y"])
                distance = math.sqrt(dx * dx + dy * dy)
                speeds[i] = distance / dt
                time_gaps[i] = dt

    # Density is computed globally — it depends on the full sample set.
    density = _local_density(samples, DENSITY_RADIUS)

    inside_polygon: list[bool | None] = [None] * n
    if polygon_vacuum and len(polygon_vacuum) >= 3:
        for i, s in enumerate(samples):
            inside_polygon[i] = point_in_polygon(
                (float(s["x"]), float(s["y"])), polygon_vacuum
            )

    return {
        "speeds": speeds,
        "time_gaps": time_gaps,
        "density": density,
        "inside_polygon": inside_polygon,
    }


# ---------------------------------------------------------------------------
# Split point detection
# ---------------------------------------------------------------------------

def _find_split_points(
    samples: list[dict[str, Any]],
    signals: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    """Return a list of split point dicts indicating where to cut.

    Each entry: {index: int, reason: str}
    Index is the first sample of the NEW segment (i.e. the cut is
    between index-1 and index).

    Hard boundaries (pause) are placed immediately.
    Soft boundaries require 2+ sustained signals.
    """
    n = len(samples)
    if n < 2:
        return []

    speeds = signals["speeds"]
    time_gaps = signals["time_gaps"]
    density = signals["density"]
    inside_polygon = signals["inside_polygon"]

    # Rolling baselines for speed and density.
    valid_speeds = [s if s is not None else 0.0 for s in speeds]
    speed_baseline = _rolling_mean(valid_speeds, BASELINE_WINDOW)
    density_baseline = _rolling_mean(density, BASELINE_WINDOW)

    split_points: list[dict[str, Any]] = []
    # Track which indices already have a split to avoid duplicates.
    split_indices: set[int] = set()

    def _add_split(index: int, reason: str) -> None:
        if index not in split_indices and 0 < index < n:
            split_indices.add(index)
            split_points.append({"index": index, "reason": reason})

    # ----------------------------------------------------------------
    # Pass 1: Hard boundaries — pauses
    # A temporal gap between consecutive samples is unambiguous.
    # No sustain window required.
    # ----------------------------------------------------------------
    for i in range(1, n):
        gap = time_gaps[i]
        if gap is not None and gap >= PAUSE_THRESHOLD_SECONDS:
            _add_split(i, f"pause:{round(gap, 1)}s")

    # ----------------------------------------------------------------
    # Pass 2: Soft boundaries — sustained multi-signal agreement
    #
    # For each position i, look at the window [i, i+SUSTAIN_WINDOW).
    # A signal fires if it is active for ALL samples in the window.
    # A split is placed at i if 2+ signals fire simultaneously.
    # ----------------------------------------------------------------
    for i in range(1, n - SUSTAIN_WINDOW):

        # Skip if already a hard boundary here or in recent window.
        if any((i + w) in split_indices for w in range(SUSTAIN_WINDOW)):
            continue

        active_signals: list[str] = []

        # -- SPEED_CHANGE signal --
        # Speed has dropped significantly relative to baseline and
        # stayed low for the full window.
        # We only fire if the baseline was meaningfully fast to begin
        # with — avoids triggering on an already-slow segment.
        baseline_speed = speed_baseline[i]
        if baseline_speed >= MIN_SPEED_FOR_SIGNAL:
            window_speeds = [
                valid_speeds[i + w]
                for w in range(SUSTAIN_WINDOW)
                if valid_speeds[i + w] is not None
            ]
            if len(window_speeds) == SUSTAIN_WINDOW:
                max_window_speed = max(window_speeds)
                if max_window_speed < baseline_speed * SPEED_CHANGE_RATIO:
                    active_signals.append("speed_drop")

        # -- DENSITY_CHANGE signal --
        # Local density has dropped significantly and stayed low.
        baseline_density = density_baseline[i]
        if baseline_density > 0:
            window_density = [density[i + w] for w in range(SUSTAIN_WINDOW)]
            max_window_density = max(window_density)
            if max_window_density < baseline_density * DENSITY_CHANGE_RATIO:
                active_signals.append("density_drop")

        # -- BOUNDARY_CROSSING signal --
        # Polygon membership has changed and stayed changed.
        # Only computed if inside_polygon has values (polygon was supplied).
        if inside_polygon[i] is not None:
            prev_states = [
                inside_polygon[max(0, i - w - 1)]
                for w in range(SUSTAIN_WINDOW)
                if inside_polygon[max(0, i - w - 1)] is not None
            ]
            window_states = [
                inside_polygon[i + w]
                for w in range(SUSTAIN_WINDOW)
                if inside_polygon[i + w] is not None
            ]
            if prev_states and window_states:
                # All previous states one way, all window states the other way.
                prev_all_inside = all(prev_states)
                prev_all_outside = not any(prev_states)
                window_all_inside = all(window_states)
                window_all_outside = not any(window_states)
                if (prev_all_inside and window_all_outside) or \
                   (prev_all_outside and window_all_inside):
                    active_signals.append("boundary_crossing")

        # Require 2+ signals to agree.
        if len(active_signals) >= 2:
            reason = "+".join(sorted(active_signals))
            _add_split(i, reason)

    split_points.sort(key=lambda p: p["index"])
    return split_points


# ---------------------------------------------------------------------------
# Segment construction
# ---------------------------------------------------------------------------

def _build_segments(
    samples: list[dict[str, Any]],
    split_points: list[dict[str, Any]],
    signals: dict[str, list[Any]],
    polygon_vacuum: list[list[float]] | None,
) -> list[dict[str, Any]]:
    """Construct segment dicts from split points and signal data."""
    n = len(samples)
    if n == 0:
        return []

    # Build boundary list: [0] + [each split index] + [n]
    boundaries = [0] + [p["index"] for p in split_points] + [n]
    reasons = [None] + [p["reason"] for p in split_points] + [None]

    segments: list[dict[str, Any]] = []

    for seg_idx in range(len(boundaries) - 1):
        start = boundaries[seg_idx]
        end = boundaries[seg_idx + 1] - 1  # inclusive
        reason = reasons[seg_idx + 1]  # reason for the split that STARTS this segment

        seg_samples = samples[start : end + 1]
        seg_count = len(seg_samples)
        if seg_count == 0:
            continue

        # Timestamps.
        started_at = seg_samples[0].get("ts")
        ended_at = seg_samples[-1].get("ts")
        ts0 = _parse_ts(started_at)
        ts1 = _parse_ts(ended_at)
        duration = round(ts1 - ts0, 2) if ts0 is not None and ts1 is not None else None

        # Speed diagnostics.
        seg_speeds = [
            signals["speeds"][start + i]
            for i in range(seg_count)
            if signals["speeds"][start + i] is not None
        ]
        mean_speed = round(sum(seg_speeds) / len(seg_speeds), 4) if seg_speeds else 0.0

        # Density diagnostics.
        seg_density = [signals["density"][start + i] for i in range(seg_count)]
        mean_density = round(sum(seg_density) / len(seg_density), 4) if seg_density else 0.0

        # Boundary state.
        polygon_states: list[bool] = [
            signals["inside_polygon"][start + i]
            for i in range(seg_count)
            if signals["inside_polygon"][start + i] is not None
        ]
        if not polygon_states:
            boundary_state = "unknown"
            boundary_ratio = None
        else:
            inside_n = sum(1 for s in polygon_states if s)
            boundary_ratio = round(inside_n / len(polygon_states), 4)
            if boundary_ratio >= 0.9:
                boundary_state = "inside"
            elif boundary_ratio <= 0.1:
                boundary_state = "outside"
            else:
                boundary_state = "mixed"

        segments.append({
            "segment_index": seg_idx,
            "start_index": start,
            "end_index": end,
            "sample_count": seg_count,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration,
            "split_reason": reason,
            "diagnostics": {
                "mean_speed": mean_speed,
                "mean_density": mean_density,
                "boundary_state": boundary_state,
                "boundary_ratio": boundary_ratio,
            },
        })

    # Reindex.
    for i, seg in enumerate(segments):
        seg["segment_index"] = i

    return segments


# ---------------------------------------------------------------------------
# Merge passes
# ---------------------------------------------------------------------------

def _merge_short_segments(
    segments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Merge any segment shorter than MIN_SEGMENT_SAMPLES into its neighbor.

    Merges into the smaller neighbor to minimise information loss.
    Returns (updated_segments, merge_count).
    """
    merged_count = 0
    changed = True

    while changed:
        changed = False
        result: list[dict[str, Any]] = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg["sample_count"] < MIN_SEGMENT_SAMPLES and len(segments) > 1:
                # Merge into smaller neighbor.
                if i == 0:
                    # Only right neighbor exists.
                    target = i + 1
                elif i == len(segments) - 1:
                    # Only left neighbor exists.
                    target = i - 1
                elif segments[i - 1]["sample_count"] <= segments[i + 1]["sample_count"]:
                    target = i - 1
                else:
                    target = i + 1

                # Merge by extending the target's index range.
                merged_seg = dict(segments[min(i, target)])
                other_seg = dict(segments[max(i, target)])
                merged_seg["start_index"] = min(
                    segments[i]["start_index"], segments[target]["start_index"]
                )
                merged_seg["end_index"] = max(
                    segments[i]["end_index"], segments[target]["end_index"]
                )
                merged_seg["sample_count"] = (
                    merged_seg["end_index"] - merged_seg["start_index"] + 1
                )
                merged_seg["started_at"] = (
                    segments[min(i, target)]["started_at"]
                    if min(i, target) == segments[min(i, target)]["start_index"]
                    else segments[min(i, target)]["started_at"]
                )
                merged_seg["ended_at"] = segments[max(i, target)]["ended_at"]
                ts0 = _parse_ts(merged_seg["started_at"])
                ts1 = _parse_ts(merged_seg["ended_at"])
                merged_seg["duration_seconds"] = (
                    round(ts1 - ts0, 2)
                    if ts0 is not None and ts1 is not None
                    else None
                )
                merged_seg["split_reason"] = segments[min(i, target)]["split_reason"]

                # Recompute diagnostics as weighted average.
                n_a = segments[i]["sample_count"]
                n_b = segments[target]["sample_count"]
                n_total = n_a + n_b
                diag_a = segments[i]["diagnostics"]
                diag_b = segments[target]["diagnostics"]
                merged_seg["diagnostics"] = {
                    "mean_speed": round(
                        (diag_a["mean_speed"] * n_a + diag_b["mean_speed"] * n_b) / n_total, 4
                    ),
                    "mean_density": round(
                        (diag_a["mean_density"] * n_a + diag_b["mean_density"] * n_b) / n_total, 4
                    ),
                    "boundary_state": "mixed",  # recomputed below
                    "boundary_ratio": None,
                }
                # Boundary ratio.
                br_a = diag_a.get("boundary_ratio")
                br_b = diag_b.get("boundary_ratio")
                if br_a is not None and br_b is not None:
                    br = round((br_a * n_a + br_b * n_b) / n_total, 4)
                    merged_seg["diagnostics"]["boundary_ratio"] = br
                    if br >= 0.9:
                        merged_seg["diagnostics"]["boundary_state"] = "inside"
                    elif br <= 0.1:
                        merged_seg["diagnostics"]["boundary_state"] = "outside"
                    else:
                        merged_seg["diagnostics"]["boundary_state"] = "mixed"
                else:
                    merged_seg["diagnostics"]["boundary_state"] = "unknown"

                segments = [
                    s for idx, s in enumerate(segments)
                    if idx != i and idx != target
                ]
                segments.insert(min(i, target), merged_seg)
                merged_count += 1
                changed = True
                break
            i += 1

    return segments, merged_count


def _merge_similar_segments(
    segments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Merge adjacent segments with similar speed and density profiles.

    Two adjacent segments that look behaviourally identical should be
    one segment — the split point was noise, not a real boundary.
    Returns (updated_segments, merge_count).
    """
    merged_count = 0
    changed = True

    while changed:
        changed = False
        for i in range(len(segments) - 1):
            a = segments[i]
            b = segments[i + 1]
            diag_a = a["diagnostics"]
            diag_b = b["diagnostics"]

            # Skip if either has zero speed (can't compute meaningful ratio).
            speed_a = diag_a["mean_speed"]
            speed_b = diag_b["mean_speed"]
            density_a = diag_a["mean_density"]
            density_b = diag_b["mean_density"]

            speeds_similar = False
            if speed_a > MIN_SPEED_FOR_SIGNAL and speed_b > MIN_SPEED_FOR_SIGNAL:
                ratio = min(speed_a, speed_b) / max(speed_a, speed_b)
                speeds_similar = ratio >= (1.0 - MERGE_SIMILARITY_THRESHOLD)

            densities_similar = False
            if density_a > 0 and density_b > 0:
                ratio = min(density_a, density_b) / max(density_a, density_b)
                densities_similar = ratio >= (1.0 - MERGE_SIMILARITY_THRESHOLD)
            elif density_a == 0 and density_b == 0:
                densities_similar = True

            if speeds_similar and densities_similar:
                # Merge b into a.
                merged = dict(a)
                merged["end_index"] = b["end_index"]
                merged["sample_count"] = merged["end_index"] - merged["start_index"] + 1
                merged["ended_at"] = b["ended_at"]
                ts0 = _parse_ts(merged["started_at"])
                ts1 = _parse_ts(merged["ended_at"])
                merged["duration_seconds"] = (
                    round(ts1 - ts0, 2)
                    if ts0 is not None and ts1 is not None
                    else None
                )
                n_a = a["sample_count"]
                n_b = b["sample_count"]
                n_total = n_a + n_b
                br_a = diag_a.get("boundary_ratio")
                br_b = diag_b.get("boundary_ratio")
                new_br: float | None = None
                if br_a is not None and br_b is not None:
                    new_br = round((br_a * n_a + br_b * n_b) / n_total, 4)
                new_state = "unknown"
                if new_br is not None:
                    if new_br >= 0.9:
                        new_state = "inside"
                    elif new_br <= 0.1:
                        new_state = "outside"
                    else:
                        new_state = "mixed"
                merged["diagnostics"] = {
                    "mean_speed": round(
                        (speed_a * n_a + speed_b * n_b) / n_total, 4
                    ),
                    "mean_density": round(
                        (density_a * n_a + density_b * n_b) / n_total, 4
                    ),
                    "boundary_state": new_state,
                    "boundary_ratio": new_br,
                }
                segments = segments[:i] + [merged] + segments[i + 2:]
                merged_count += 1
                changed = True
                break

    return segments, merged_count


def _reindex(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rewrite segment_index on all segments to reflect their current list position."""
    for i, seg in enumerate(segments):
        seg["segment_index"] = i
    return segments


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def segment_trace_run(
    run: dict[str, Any],
    polygon_vacuum: list[list[float]] | None = None,
) -> dict[str, Any]:
    """Segment a TraceRun into candidate behavioural segments.

    Parameters
    ----------
    run:
        A fully loaded TraceRun dict. Must contain a "samples" list.

    polygon_vacuum:
        Optional vacuum-space room boundary. When supplied, enables
        the BOUNDARY_CROSSING signal. When absent, only PAUSE and
        the speed/density soft signals are available.

    Returns a SegmentationResult dict. Never raises — structural
    problems are returned as error fields.
    """
    run_id = str(run.get("run_id", "unknown"))
    vacuum_entity_id = str(run.get("vacuum_entity_id", ""))
    map_id = str(run.get("map_id", ""))
    room_id = run.get("room_id")

    def _error(reason: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id,
            "room_id": room_id,
            "error": reason,
            "segment_count": 0,
            "segments": [],
            "diagnostics": None,
        }

    samples = _extract_samples(run)
    if len(samples) < 2:
        return _error(f"insufficient_samples:{len(samples)}")

    # Compute all per-sample signals once.
    signals = _compute_per_sample_signals(samples, polygon_vacuum)

    # Find split points.
    split_points = _find_split_points(samples, signals)
    hard_boundaries = sum(1 for p in split_points if p["reason"].startswith("pause:"))
    soft_boundaries = len(split_points) - hard_boundaries

    # Build initial segments.
    segments = _build_segments(samples, split_points, signals, polygon_vacuum)

    # Anti-oversegmentation merge passes.
    merge_passes = 0
    total_short_merges = 0
    total_similarity_merges = 0

    for _ in range(20):  # cap iterations — stable in practice after 2-3 passes
        prev_count = len(segments)
        segments, short_n = _merge_short_segments(segments)
        segments, sim_n = _merge_similar_segments(segments)
        total_short_merges += short_n
        total_similarity_merges += sim_n
        merge_passes += 1
        if len(segments) == prev_count:
            break

    segments = _reindex(segments)

    return {
        "run_id": run_id,
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": map_id,
        "room_id": room_id,
        "error": None,
        "segment_count": len(segments),
        "segments": segments,
        "diagnostics": {
            "total_samples": len(samples),
            "hard_boundaries": hard_boundaries,
            "soft_boundaries": soft_boundaries,
            "merge_passes": merge_passes,
            "short_merges": total_short_merges,
            "similarity_merges": total_similarity_merges,
        },
    }