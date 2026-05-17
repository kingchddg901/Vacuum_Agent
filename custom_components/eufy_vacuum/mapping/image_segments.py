"""Deterministic room-segment extraction from clean map images using HSV color clustering and morphological analysis."""

from __future__ import annotations

import importlib
import logging
import math
from collections import defaultdict
from typing import Any

_LOGGER = logging.getLogger(__name__)


def _optional_import(name: str) -> tuple[Any | None, str | None]:
    try:
        return importlib.import_module(name), None
    except Exception as err:  # pragma: no cover - runtime capability guard
        return None, f"{type(err).__name__}: {err}"


np, _NUMPY_IMPORT_ERROR = _optional_import("numpy")
PIL_Image, _PIL_IMPORT_ERROR = _optional_import("PIL.Image")
scipy, _SCIPY_IMPORT_ERROR = _optional_import("scipy")
scipy_ndimage, _SCIPY_NDIMAGE_IMPORT_ERROR = _optional_import("scipy.ndimage")

_PIL_SCIPY_READY = PIL_Image is not None and np is not None and scipy_ndimage is not None
_NDIMAGE = scipy_ndimage


def image_runtime_capabilities() -> dict[str, Any]:
    """Return availability and version info for each optional image-processing library."""
    def _version(module: Any) -> str | None:
        if module is None:
            return None
        return getattr(module, "__version__", None)

    return {
        "numpy": {
            "available": np is not None,
            "version": _version(np),
            "error": _NUMPY_IMPORT_ERROR,
        },
        "pillow": {
            "available": PIL_Image is not None,
            "version": _version(PIL_Image),
            "error": _PIL_IMPORT_ERROR,
        },
        "scipy": {
            "available": scipy is not None,
            "version": _version(scipy),
            "error": _SCIPY_IMPORT_ERROR,
        },
        "scipy_ndimage": {
            "available": scipy_ndimage is not None,
            "version": _version(scipy_ndimage),
            "error": _SCIPY_NDIMAGE_IMPORT_ERROR,
        },
        "pipeline_ready": _PIL_SCIPY_READY and _NDIMAGE is not None,
    }


def _issue_quality(issues: list[str], confidence: float) -> str:
    """Map a segment's issue flags and confidence score to a quality label."""
    if "tiny_region" in issues or "too_complex" in issues:
        return "poor"
    if "touches_border" in issues or "possible_merge" in issues or confidence < 0.55:
        return "usable"
    if confidence < 0.75:
        return "good"
    return "strong"


def _structural_role(*, area_percent: float, aspect_ratio: float, fill_ratio: float) -> str:
    """Classify a segment's structural role (hub, connector, spine, room, uncertain)."""
    if area_percent >= 0.09 and fill_ratio >= 0.62:
        return "hub"
    if aspect_ratio >= 2.4 and fill_ratio >= 0.34:
        return "connector"
    if aspect_ratio >= 1.7 and fill_ratio >= 0.3:
        return "spine"
    if fill_ratio >= 0.58:
        return "room"
    return "uncertain"


def _segmentation_state(*, issues: list[str], fill_ratio: float, compactness: float) -> str:
    """Classify a segment's segmentation state (clean, merged_candidate, fragmented_candidate, review)."""
    if "possible_merge" in issues:
        return "merged_candidate"
    if "fragmented_candidate" in issues or compactness < 0.08:
        return "fragmented_candidate"
    if fill_ratio >= 0.58 and "tiny_region" not in issues:
        return "clean"
    return "review"


def _bbox_from_stats(x: int, y: int, w: int, h: int) -> dict[str, int]:
    return {
        "x": int(x),
        "y": int(y),
        "width": int(w),
        "height": int(h),
    }


def _rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points[:]

    start = points[0]
    end = points[-1]
    sx, sy = start
    ex, ey = end

    max_distance = -1.0
    index = -1
    for idx in range(1, len(points) - 1):
        px, py = points[idx]
        if start == end:
            distance = math.hypot(px - sx, py - sy)
        else:
            numerator = abs((ey - sy) * px - (ex - sx) * py + ex * sy - ey * sx)
            denominator = math.hypot(ex - sx, ey - sy)
            distance = numerator / max(denominator, 1e-6)
        if distance > max_distance:
            max_distance = distance
            index = idx

    if max_distance <= epsilon or index < 0:
        return [start, end]

    left = _rdp(points[: index + 1], epsilon)
    right = _rdp(points[index:], epsilon)
    return left[:-1] + right


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _normalize_polygon(points: list[tuple[float, float]]) -> list[list[float]]:
    polygon: list[list[float]] = []
    for x, y in points:
        polygon.append([round(float(x), 2), round(float(y), 2)])
    return polygon


def _mask_to_polygon(mask: Any, simplify_epsilon: float | None = None) -> tuple[list[list[float]], int]:
    """Trace the outer boundary of a boolean mask and return a simplified polygon.

    Returns (polygon_points, raw_point_count). The polygon is simplified with
    RDP; raw_point_count is the vertex count before simplification.
    """
    height, width = mask.shape
    edges: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

    for y in range(height):
        for x in range(width):
            if not bool(mask[y, x]):
                continue
            if y == 0 or not bool(mask[y - 1, x]):
                edges[(x, y)].append((x + 1, y))
            if x == width - 1 or not bool(mask[y, x + 1]):
                edges[(x + 1, y)].append((x + 1, y + 1))
            if y == height - 1 or not bool(mask[y + 1, x]):
                edges[(x + 1, y + 1)].append((x, y + 1))
            if x == 0 or not bool(mask[y, x - 1]):
                edges[(x, y + 1)].append((x, y))

    if not edges:
        return ([], 0)

    unused = {(start, end) for start, ends in edges.items() for end in ends}
    loops: list[list[tuple[float, float]]] = []

    while unused:
        start_edge = next(iter(unused))
        start_point, next_point = start_edge
        loop = [start_point, next_point]
        unused.remove(start_edge)
        current = next_point

        while current != start_point:
            candidates = [end for end in edges.get(current, []) if (current, end) in unused]
            if not candidates:
                break
            prev = loop[-2]
            if len(candidates) > 1:
                candidates.sort(key=lambda point: math.atan2(point[1] - current[1], point[0] - current[0]) - math.atan2(prev[1] - current[1], prev[0] - current[0]))
            chosen = candidates[0]
            unused.remove((current, chosen))
            loop.append(chosen)
            current = chosen

        if len(loop) >= 4 and loop[0] == loop[-1]:
            loops.append([(float(x), float(y)) for (x, y) in loop[:-1]])

    if not loops:
        return ([], 0)

    best_loop = max(loops, key=lambda pts: abs(_polygon_area(pts)))
    raw_point_count = len(best_loop)
    epsilon = float(simplify_epsilon) if simplify_epsilon is not None else max(1.0, math.sqrt(max(raw_point_count, 1)) * 0.42)
    simplified = _rdp(best_loop + [best_loop[0]], epsilon)
    simplified = simplified[:-1] if simplified and simplified[0] == simplified[-1] else simplified

    if raw_point_count >= 700 and len(simplified) <= 6:
        epsilon = max(0.8, epsilon * 0.72)
        simplified = _rdp(best_loop + [best_loop[0]], epsilon)
        simplified = simplified[:-1] if simplified and simplified[0] == simplified[-1] else simplified

    if len(simplified) < 4:
        simplified = best_loop

    return (_normalize_polygon(simplified), raw_point_count)


def _build_room_mask_from_hsv(hsv: Any) -> Any:
    """Return a binary room-pixel mask derived from HSV saturation and value thresholds."""
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    room_mask = (value >= 68) & (saturation >= 18)
    structure = np.ones((3, 3), dtype=bool)
    room_mask = _NDIMAGE.binary_opening(room_mask, structure=structure, iterations=1)
    room_mask = _NDIMAGE.binary_closing(room_mask, structure=structure, iterations=2)
    room_mask = _NDIMAGE.binary_fill_holes(room_mask)
    return room_mask


def _build_light_wall_mask(hsv: Any) -> Any:
    """Return a binary mask of near-white wall pixels from a light-theme HSV image."""
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    wall_mask = (value >= 214) & (saturation <= 36)
    structure = np.ones((3, 3), dtype=bool)
    wall_mask = _NDIMAGE.binary_opening(wall_mask, structure=structure, iterations=1)
    wall_mask = _NDIMAGE.binary_dilation(wall_mask, structure=structure, iterations=1)
    return wall_mask


def _mask_edge_band(mask: Any, iterations: int = 2) -> Any:
    """Return the edge band of a mask (dilated XOR eroded) for seam detection."""
    structure = np.ones((3, 3), dtype=bool)
    dilated = _NDIMAGE.binary_dilation(mask, structure=structure, iterations=max(1, int(iterations)))
    eroded = _NDIMAGE.binary_erosion(mask, structure=structure, iterations=max(1, int(iterations)))
    return dilated ^ eroded


def _mask_left_right_counts(mask: Any) -> dict[str, int]:
    """Return pixel counts in the left and right halves of a mask."""
    height, width = mask.shape
    midpoint = width // 2
    return {
        "left": int(np.count_nonzero(mask[:, :midpoint])),
        "right": int(np.count_nonzero(mask[:, midpoint:])),
    }


def _transform_mask(mask: Any, scale: float, shift_x: int, shift_y: int, target_shape: tuple[int, int]) -> Any:
    """Scale and translate a boolean mask into a canvas of target_shape."""
    src_h, src_w = mask.shape
    target_h, target_w = target_shape
    if abs(scale - 1.0) > 1e-6:
        scaled = _NDIMAGE.zoom(mask.astype(np.uint8), zoom=scale, order=0) > 0
    else:
        scaled = mask.astype(bool)

    scaled_h, scaled_w = scaled.shape
    canvas = np.zeros((target_h, target_w), dtype=bool)

    base_y = ((target_h - scaled_h) // 2) + int(shift_y)
    base_x = ((target_w - scaled_w) // 2) + int(shift_x)
    dst_y0 = max(base_y, 0)
    dst_x0 = max(base_x, 0)
    dst_y1 = min(base_y + scaled_h, target_h)
    dst_x1 = min(base_x + scaled_w, target_w)

    if dst_y0 >= dst_y1 or dst_x0 >= dst_x1:
        return canvas

    src_y0 = dst_y0 - base_y
    src_x0 = dst_x0 - base_x
    src_y1 = src_y0 + (dst_y1 - dst_y0)
    src_x1 = src_x0 + (dst_x1 - dst_x0)
    canvas[dst_y0:dst_y1, dst_x0:dst_x1] = scaled[src_y0:src_y1, src_x0:src_x1]
    return canvas


def _transform_scalar_image(image: Any, scale: float, shift_x: int, shift_y: int, target_shape: tuple[int, int]) -> Any:
    """Scale and translate a single-channel float image into a canvas of target_shape."""
    src_h, src_w = image.shape
    target_h, target_w = target_shape
    if abs(scale - 1.0) > 1e-6:
        scaled = _NDIMAGE.zoom(image.astype(np.float32), zoom=scale, order=1)
    else:
        scaled = image.astype(np.float32)

    scaled_h, scaled_w = scaled.shape
    canvas = np.zeros((target_h, target_w), dtype=np.float32)

    base_y = ((target_h - scaled_h) // 2) + int(shift_y)
    base_x = ((target_w - scaled_w) // 2) + int(shift_x)
    dst_y0 = max(base_y, 0)
    dst_x0 = max(base_x, 0)
    dst_y1 = min(base_y + scaled_h, target_h)
    dst_x1 = min(base_x + scaled_w, target_w)

    if dst_y0 >= dst_y1 or dst_x0 >= dst_x1:
        return canvas

    src_y0 = dst_y0 - base_y
    src_x0 = dst_x0 - base_x
    src_y1 = src_y0 + (dst_y1 - dst_y0)
    src_x1 = src_x0 + (dst_x1 - dst_x0)
    canvas[dst_y0:dst_y1, dst_x0:dst_x1] = scaled[src_y0:src_y1, src_x0:src_x1]
    return canvas


def _transform_color_image(image: Any, scale: float, shift_x: int, shift_y: int, target_shape: tuple[int, int]) -> Any:
    """Scale and translate each channel of an RGB image into a canvas of target_shape."""
    channels = [
        _transform_scalar_image(image[:, :, index], scale, shift_x, shift_y, target_shape)
        for index in range(image.shape[2])
    ]
    return np.stack(channels, axis=2)


def _mask_iou(mask_a: Any, mask_b: Any) -> float:
    """Return intersection-over-union of two boolean masks."""
    if getattr(mask_a, "shape", None) != getattr(mask_b, "shape", None):
        return 0.0
    union = np.count_nonzero(mask_a | mask_b)
    if union <= 0:
        return 0.0
    intersection = np.count_nonzero(mask_a & mask_b)
    return float(intersection) / float(union)


def _estimate_alignment(reference_mask: Any, candidate_mask: Any) -> dict[str, Any]:
    """Brute-force search for the best scale/shift alignment of candidate_mask onto reference_mask.

    Returns a dict with scale, shift_x, shift_y, and the best IoU score.
    """
    target_shape = reference_mask.shape
    baseline = _transform_mask(candidate_mask, 1.0, 0, 0, target_shape)
    best = {
        "scale": 1.0,
        "shift_x": 0,
        "shift_y": 0,
        "score": round(_mask_iou(reference_mask, baseline), 4),
    }
    scales = [0.94, 0.97, 1.0, 1.03, 1.06]
    shifts = range(-24, 25, 6)

    for scale in scales:
        for shift_y in shifts:
            for shift_x in shifts:
                transformed = _transform_mask(candidate_mask, scale, shift_x, shift_y, target_shape)
                score = _mask_iou(reference_mask, transformed)
                if score > float(best["score"]):
                    best = {
                        "scale": float(scale),
                        "shift_x": int(shift_x),
                        "shift_y": int(shift_y),
                        "score": round(float(score), 4),
                    }
    return best


def _mask_perimeter(mask: Any) -> int:
    """Count exposed edges of True pixels to approximate the mask perimeter."""
    height, width = mask.shape
    perimeter = 0
    for y in range(height):
        for x in range(width):
            if not bool(mask[y, x]):
                continue
            if y == 0 or not bool(mask[y - 1, x]):
                perimeter += 1
            if x == width - 1 or not bool(mask[y, x + 1]):
                perimeter += 1
            if y == height - 1 or not bool(mask[y + 1, x]):
                perimeter += 1
            if x == 0 or not bool(mask[y, x - 1]):
                perimeter += 1
    return perimeter


def _compactness(area: int, perimeter: int) -> float:
    if area <= 0 or perimeter <= 0:
        return 0.0
    return float((4.0 * math.pi * area) / max(float(perimeter * perimeter), 1.0))


def _aspect_ratio(width: int, height: int) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    return float(max(width, height)) / float(max(min(width, height), 1))


def _agreement_score(component_global: Any, assist_mask: Any | None) -> float:
    """Return fraction of component pixels confirmed by the assist mask (0–1)."""
    if assist_mask is None or getattr(component_global, "shape", None) != getattr(assist_mask, "shape", None):
        return 0.0
    area = np.count_nonzero(component_global)
    if area <= 0:
        return 0.0
    overlap = np.count_nonzero(component_global & assist_mask)
    return float(overlap) / float(area)


def _component_overlap_ratio(mask_a: Any, mask_b: Any) -> tuple[float, float]:
    """Return (overlap/area_a, overlap/area_b) for two boolean masks."""
    if getattr(mask_a, "shape", None) != getattr(mask_b, "shape", None):
        return (0.0, 0.0)
    area_a = np.count_nonzero(mask_a)
    area_b = np.count_nonzero(mask_b)
    if area_a <= 0 or area_b <= 0:
        return (0.0, 0.0)
    intersection = np.count_nonzero(mask_a & mask_b)
    return (float(intersection) / float(area_a), float(intersection) / float(area_b))


def _reclaim_localized_child_mask(
    local_mask: Any,
    parent_mask: Any,
    *,
    primary_sat: Any,
    primary_value: Any,
    assist_sat: Any | None = None,
    assist_value: Any | None = None,
) -> Any:
    """Conservatively reclaim vertically truncated localized child masks.

    This is intentionally biased toward completing room-like regions that got
    clipped upward during localization. It only grows downward a small amount
    inside the already-detected parent component and only through pixels that
    still look room-like in saturation/value space.
    """
    if _NDIMAGE is None or not bool(np.any(local_mask)):
        return local_mask

    ys, _ = np.nonzero(local_mask)
    if ys.size == 0:
        return local_mask

    height, width = local_mask.shape
    top = int(ys.min())
    bottom = int(ys.max())
    if bottom >= height - 2:
        return local_mask

    def _trim_sparse_top_rows(mask: Any, *, pass_strength: float) -> Any:
        row_counts = np.count_nonzero(mask, axis=1)
        occupied_rows = np.flatnonzero(row_counts > 0)
        if occupied_rows.size < 6:
            return mask
        local_top = int(occupied_rows.min())
        local_bottom = int(occupied_rows.max())
        lower_start_index = min(len(occupied_rows) // 3, max(len(occupied_rows) - 3, 0))
        lower_start = int(occupied_rows[lower_start_index])
        baseline_rows = row_counts[lower_start : local_bottom + 1]
        baseline_rows = baseline_rows[baseline_rows > 0]
        if baseline_rows.size == 0:
            return mask
        dense_row_baseline = float(np.median(baseline_rows))
        trim_limit = min(local_bottom, local_top + max(10, int(mask.shape[0] * 0.22)))
        trim_rows: list[int] = []
        for row in range(local_top, trim_limit + 1):
            count = int(row_counts[row])
            if count <= 0:
                continue
            if count < max(6.0, dense_row_baseline * pass_strength):
                trim_rows.append(row)
                continue
            break
        if not trim_rows:
            return mask
        trimmed_mask = mask.copy()
        trimmed_mask[trim_rows, :] = False
        if int(np.count_nonzero(trimmed_mask)) < int(np.count_nonzero(mask) * 0.68):
            return mask
        return trimmed_mask

    # Trim sparse top rows before attempting downward reclaim.
    local_mask = _trim_sparse_top_rows(local_mask, pass_strength=0.42)
    ys, _ = np.nonzero(local_mask)
    if ys.size == 0:
        return parent_mask & False
    top = int(ys.min())
    bottom = int(ys.max())

    sat_values = primary_sat[local_mask]
    value_values = primary_value[local_mask]
    if sat_values.size == 0 or value_values.size == 0:
        return local_mask

    sat_floor = max(18.0, float(np.percentile(sat_values, 20)) - 18.0)
    value_floor = max(68.0, float(np.percentile(value_values, 20)) - 26.0)

    support_mask = parent_mask & (primary_sat >= sat_floor) & (primary_value >= value_floor)
    if assist_sat is not None and assist_value is not None:
        assist_support = (assist_sat >= max(16.0, sat_floor - 4.0)) & (assist_value >= max(64.0, value_floor - 8.0))
        support_mask &= assist_support

    row_index = np.indices(local_mask.shape)[0]
    col_index = np.indices(local_mask.shape)[1]
    xs = np.nonzero(local_mask)[1]
    left = int(xs.min())
    right = int(xs.max())
    horizontal_margin = max(8, int((right - left + 1) * 0.12))
    support_mask &= row_index >= max(0, bottom - 2)
    support_mask &= row_index <= min(height - 1, bottom + max(16, int(height * 0.08)))
    support_mask &= col_index >= max(0, left - horizontal_margin)
    support_mask &= col_index <= min(width - 1, right + horizontal_margin)
    if not bool(np.any(support_mask)):
        return local_mask

    # WHY: binary_propagation from the lower seed band — constrained to connected
    # room-like support rather than blindly dilating the whole child mask.
    lower_seed_band = max(top, bottom - max(10, int((bottom - top + 1) * 0.35)))
    seed_mask = local_mask & (row_index >= lower_seed_band)
    reclaimed = _NDIMAGE.binary_propagation(
        seed_mask,
        structure=np.ones((3, 3), dtype=bool),
        mask=support_mask,
    ) & ~local_mask
    if not bool(np.any(reclaimed)):
        return local_mask

    expanded = local_mask | reclaimed
    expanded = _NDIMAGE.binary_closing(expanded, structure=np.ones((3, 3), dtype=bool), iterations=1)
    expanded &= parent_mask

    added_area = int(np.count_nonzero(expanded)) - int(np.count_nonzero(local_mask))
    if added_area <= 0:
        return _trim_sparse_top_rows(local_mask, pass_strength=0.5)
    if added_area > max(3200, int(np.count_nonzero(local_mask) * 0.55)):
        return _trim_sparse_top_rows(local_mask, pass_strength=0.5)

    # Final cleanup pass to suppress any lingering upper bleed after reclaim.
    return _trim_sparse_top_rows(expanded, pass_strength=0.5)


def _split_component_via_erosion(component_mask: Any, min_area_pixels: int) -> list[Any]:
    """Try to split a merged component by progressively eroding and regrowth from seeds."""
    structure = np.ones((3, 3), dtype=bool)
    for iterations in (1, 2, 3, 4):
        eroded = _NDIMAGE.binary_erosion(component_mask, structure=structure, iterations=iterations)
        if not bool(np.any(eroded)):
            continue
        seeds, seed_count = _NDIMAGE.label(eroded, structure=structure)
        if seed_count < 2:
            continue

        slices = _NDIMAGE.find_objects(seeds)
        grown_masks: list[Any] = []
        for label_index in range(1, seed_count + 1):
            seed_mask = seeds == label_index
            grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
            grown_area = int(np.count_nonzero(grown))
            if grown_area < max(350, int(min_area_pixels * 0.45)):
                continue
            grown_masks.append(grown)

        if len(grown_masks) >= 2:
            return grown_masks
    return []


def _split_component_via_opening(component_mask: Any, min_area_pixels: int) -> list[Any]:
    """Try to split a merged component via binary opening followed by propagation from seeds."""
    structure = np.ones((3, 3), dtype=bool)
    for iterations in (1, 2, 3, 4):
        opened = _NDIMAGE.binary_opening(component_mask, structure=structure, iterations=iterations)
        if not bool(np.any(opened)):
            continue
        seeds, seed_count = _NDIMAGE.label(opened, structure=structure)
        if seed_count < 2:
            continue

        grown_masks: list[Any] = []
        for label_index in range(1, seed_count + 1):
            seed_mask = seeds == label_index
            grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
            grown_area = int(np.count_nonzero(grown))
            if grown_area < max(350, int(min_area_pixels * 0.45)):
                continue
            grown_masks.append(grown)
        if len(grown_masks) >= 2:
            return grown_masks
    return []


def _split_component_via_wall_cuts(component_mask: Any, wall_hint_mask: Any | None, min_area_pixels: int) -> list[Any]:
    """Try to split a merged component by cutting along nearby wall-hint pixels."""
    if wall_hint_mask is None or getattr(component_mask, "shape", None) != getattr(wall_hint_mask, "shape", None):
        return []
    structure = np.ones((3, 3), dtype=bool)
    local_wall = wall_hint_mask & _NDIMAGE.binary_dilation(component_mask, structure=structure, iterations=1)
    if not bool(np.any(local_wall)):
        return []

    for iterations in (1, 2, 3):
        cut_mask = component_mask & ~_NDIMAGE.binary_dilation(local_wall, structure=structure, iterations=iterations)
        if not bool(np.any(cut_mask)):
            continue
        labeled, component_count = _NDIMAGE.label(cut_mask, structure=structure)
        if component_count < 2:
            continue
        grown_masks: list[Any] = []
        for label_index in range(1, component_count + 1):
            seed_mask = labeled == label_index
            grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
            grown_area = int(np.count_nonzero(grown))
            if grown_area < max(350, int(min_area_pixels * 0.45)):
                continue
            grown_masks.append(grown)
        if len(grown_masks) >= 2:
            return grown_masks
    return []


def _split_component_via_local_support(
    component_mask: Any,
    primary_sat: Any | None,
    primary_value: Any | None,
    assist_sat: Any | None,
    assist_value: Any | None,
    min_area_pixels: int,
) -> list[Any]:
    """Try to split a merged component by scoring pixels against per-channel support thresholds."""
    if (
        primary_sat is None
        or primary_value is None
        or getattr(component_mask, "shape", None) != getattr(primary_sat, "shape", None)
        or getattr(component_mask, "shape", None) != getattr(primary_value, "shape", None)
    ):
        return []

    active = component_mask.astype(bool)
    active_area = int(np.count_nonzero(active))
    if active_area < max(int(min_area_pixels * 2.0), 3200):
        return []

    primary_sat_values = primary_sat[active]
    primary_value_values = primary_value[active]
    if len(primary_sat_values) == 0 or len(primary_value_values) == 0:
        return []

    sat_floor = float(np.percentile(primary_sat_values, 42))
    value_floor = float(np.percentile(primary_value_values, 38))
    score = np.zeros(component_mask.shape, dtype=np.uint8)
    score += (primary_sat >= sat_floor).astype(np.uint8)
    score += (primary_value >= value_floor).astype(np.uint8)

    if assist_sat is not None and getattr(component_mask, "shape", None) == getattr(assist_sat, "shape", None):
        assist_sat_values = assist_sat[active]
        if len(assist_sat_values):
            assist_sat_floor = float(np.percentile(assist_sat_values, 40))
            score += (assist_sat >= assist_sat_floor).astype(np.uint8)

    if assist_value is not None and getattr(component_mask, "shape", None) == getattr(assist_value, "shape", None):
        assist_value_values = assist_value[active]
        if len(assist_value_values):
            assist_value_floor = float(np.percentile(assist_value_values, 36))
            score += (assist_value >= assist_value_floor).astype(np.uint8)

    required_score = 3 if (assist_sat is not None and assist_value is not None) else 2
    supported = active & (score >= required_score)
    structure = np.ones((3, 3), dtype=bool)
    supported = _NDIMAGE.binary_opening(supported, structure=structure, iterations=1)
    supported = _NDIMAGE.binary_closing(supported, structure=structure, iterations=1)
    if not bool(np.any(supported)):
        return []

    labeled, component_count = _NDIMAGE.label(supported, structure=structure)
    if component_count < 2:
        return []

    grown_masks: list[Any] = []
    for label_index in range(1, component_count + 1):
        seed_mask = labeled == label_index
        seed_area = int(np.count_nonzero(seed_mask))
        if seed_area < max(int(min_area_pixels * 0.35), 180):
            continue
        grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
        grown_area = int(np.count_nonzero(grown))
        if grown_area < max(int(min_area_pixels * 0.8), 1000):
            continue
        if grown_area > int(active_area * 0.8):
            continue
        if any(_component_overlap_ratio(grown, existing)[0] >= 0.74 for existing in grown_masks):
            continue
        grown_masks.append(grown)

    if len(grown_masks) < 2:
        return []
    return grown_masks


def _normalized_color_features(rgb: Any) -> Any:
    """Return illumination-normalized chromaticity features for an RGB image array."""
    rgb_float = rgb.astype(np.float32) + 1.0
    luminance = (
        (0.2126 * rgb_float[:, :, 0])
        + (0.7152 * rgb_float[:, :, 1])
        + (0.0722 * rgb_float[:, :, 2])
    )
    luminance = np.maximum(luminance, 1.0)
    normalized = rgb_float / luminance[:, :, None]
    channel_sum = np.maximum(normalized.sum(axis=2, keepdims=True), 1e-6)
    return normalized / channel_sum


def _split_component_via_color_distance(
    component_mask: Any,
    primary_rgb: Any | None,
    assist_rgb: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    debug: dict[str, Any] = {
        "method": "color_distance",
        "accepted": False,
    }
    if (
        primary_rgb is None
        or getattr(component_mask, "shape", None) != getattr(primary_rgb, "shape", None)[:2]
    ):
        debug["reason"] = "missing_primary_rgb"
        return [], debug

    active = component_mask.astype(bool)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    if active_area < max(int(min_area_pixels * 2.0), 3200):
        debug["reason"] = "below_active_area_floor"
        return [], debug

    primary_features = _normalized_color_features(primary_rgb)
    features = primary_features
    if assist_rgb is not None and getattr(assist_rgb, "shape", None) == getattr(primary_rgb, "shape", None):
        assist_features = _normalized_color_features(assist_rgb)
        features = (primary_features + assist_features) / 2.0

    feature_values = features[active]
    debug["feature_value_count"] = int(len(feature_values))
    if len(feature_values) < max(int(min_area_pixels * 1.2), 1800):
        debug["reason"] = "insufficient_feature_values"
        return [], debug

    quantized = np.clip(np.rint(feature_values * 7.0), 0, 7).astype(np.int16)
    unique_bins, counts = np.unique(quantized, axis=0, return_counts=True)
    ranked = sorted(
        (
            (unique_bins[index], int(counts[index]))
            for index in range(len(unique_bins))
            if int(counts[index]) >= max(int(min_area_pixels * 0.45), int(active_area * 0.1))
        ),
        key=lambda item: -item[1],
    )
    debug["ranked_bin_count"] = int(len(ranked))
    if len(ranked) < 2:
        debug["reason"] = "insufficient_color_bins"
        return [], debug

    centers: list[Any] = []
    first_center = ranked[0][0].astype(np.float32) / 7.0
    centers.append(first_center)
    best_second: Any | None = None
    best_distance = 0.0
    for candidate, _count in ranked[1:]:
        candidate_center = candidate.astype(np.float32) / 7.0
        distance = float(np.linalg.norm(candidate_center - first_center))
        if distance > best_distance:
            best_distance = distance
            best_second = candidate_center
    debug["best_center_distance"] = round(float(best_distance), 4)
    if best_second is None or best_distance < 0.09:
        debug["reason"] = "center_distance_too_small"
        return [], debug
    centers.append(best_second)

    structure = np.ones((3, 3), dtype=bool)
    grown_masks: list[Any] = []
    used_area = 0
    seed_areas: list[int] = []
    grown_areas: list[int] = []
    for center in centers:
        distance_map = np.sqrt(np.sum((features - center[None, None, :]) ** 2, axis=2))
        active_distances = distance_map[active]
        if len(active_distances) == 0:
            continue
        threshold = float(np.percentile(active_distances, 46)) + 0.018
        threshold = max(0.04, min(0.14, threshold))
        seed_threshold = max(0.022, threshold * 0.55)
        allowed = active & (distance_map <= threshold)
        seed_mask = active & (distance_map <= seed_threshold)
        seed_mask = _NDIMAGE.binary_opening(seed_mask, structure=structure, iterations=1)
        seed_area = int(np.count_nonzero(seed_mask))
        seed_areas.append(seed_area)
        if seed_area < max(int(min_area_pixels * 0.18), 90):
            continue
        grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=allowed)
        grown_area = int(np.count_nonzero(grown))
        grown_areas.append(grown_area)
        if grown_area < max(int(min_area_pixels * 0.7), 900):
            continue
        if grown_area > int(active_area * 0.84):
            continue
        if any(_component_overlap_ratio(grown, existing)[0] >= 0.72 for existing in grown_masks):
            continue
        grown_masks.append(grown)
        used_area += grown_area

    debug["seed_areas"] = seed_areas
    debug["grown_areas"] = grown_areas
    debug["grown_mask_count"] = int(len(grown_masks))
    debug["used_area"] = int(used_area)
    if len(grown_masks) < 2:
        debug["reason"] = "insufficient_grown_masks"
        return [], debug
    if used_area < int(active_area * 0.38):
        debug["reason"] = "insufficient_coverage"
        return [], debug
    debug["accepted"] = True
    debug["reason"] = "accepted"
    return grown_masks, debug


def _localize_oversized_component(
    component_mask: Any,
    primary_rgb: Any | None,
    assist_rgb: Any | None,
    assist_hue: Any | None,
    assist_sat: Any | None,
    assist_value: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    debug: dict[str, Any] = {
        "method": "localized_bins",
        "accepted": False,
    }
    if (
        primary_rgb is None
        or getattr(component_mask, "shape", None) != getattr(primary_rgb, "shape", None)[:2]
    ):
        debug["reason"] = "missing_primary_rgb"
        return [], debug

    active = component_mask.astype(bool)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    if active_area < max(int(min_area_pixels * 10), 120000):
        debug["reason"] = "below_oversized_floor"
        return [], debug

    features = _normalized_color_features(primary_rgb)
    if assist_rgb is not None and getattr(assist_rgb, "shape", None) == getattr(primary_rgb, "shape", None):
        features = (features + _normalized_color_features(assist_rgb)) / 2.0

    quantized = np.clip(np.rint(features * 7.0), 0, 7).astype(np.int16)
    feature_values = quantized[active]
    if len(feature_values) == 0:
        debug["reason"] = "no_feature_values"
        return [], debug

    unique_bins, counts = np.unique(feature_values, axis=0, return_counts=True)
    min_bucket = max(int(min_area_pixels * 0.9), int(active_area * 0.025))
    max_bucket = int(active_area * 0.24)
    ranked_colors = sorted(
        (
            (unique_bins[index], int(counts[index]))
            for index in range(len(unique_bins))
            if min_bucket <= int(counts[index]) <= max_bucket
        ),
        key=lambda item: -item[1],
    )

    ranked_hues: list[tuple[int, int]] = []
    if (
        assist_hue is not None
        and assist_sat is not None
        and assist_value is not None
        and getattr(assist_hue, "shape", None) == getattr(component_mask, "shape", None)
    ):
        assist_active = active & (assist_sat >= 16) & (assist_value >= 70)
        hue_values = assist_hue[assist_active]
        if len(hue_values):
            hue_bins = ((hue_values.astype(np.int16) + 6) // 12).astype(np.int16)
            unique_hues, hue_counts = np.unique(hue_bins, return_counts=True)
            ranked_hues = sorted(
                (
                    (int(unique_hues[index]), int(hue_counts[index]))
                    for index in range(len(unique_hues))
                    if min_bucket <= int(hue_counts[index]) <= max_bucket
                ),
                key=lambda item: -item[1],
            )

    debug["ranked_color_bins"] = int(len(ranked_colors))
    debug["ranked_hue_bins"] = int(len(ranked_hues))
    structure = np.ones((3, 3), dtype=bool)
    candidate_masks: list[Any] = []
    candidate_areas: list[int] = []

    def _try_add_candidate(seed_mask: Any) -> None:
        opened = _NDIMAGE.binary_opening(seed_mask, structure=structure, iterations=1)
        if not bool(np.any(opened)):
            return
        labeled, count = _NDIMAGE.label(opened, structure=structure)
        if count <= 0:
            return
        slices = _NDIMAGE.find_objects(labeled)
        for label_index in range(1, count + 1):
            label_slice = slices[label_index - 1] if label_index - 1 < len(slices) else None
            if label_slice is None:
                continue
            local_mask = labeled[label_slice] == label_index
            local_area = int(np.count_nonzero(local_mask))
            if local_area < max(int(min_area_pixels * 0.9), 1400):
                continue
            if local_area > int(active_area * 0.22):
                continue
            y_slice, x_slice = label_slice
            global_mask = np.zeros_like(component_mask, dtype=bool)
            global_mask[y_slice, x_slice] = local_mask
            h = int((y_slice.stop or 0) - (y_slice.start or 0))
            w = int((x_slice.stop or 0) - (x_slice.start or 0))
            fill_ratio = local_area / max(float(w * h), 1.0)
            if fill_ratio < 0.16:
                continue
            if any(max(_component_overlap_ratio(global_mask, existing)) >= 0.68 for existing in candidate_masks):
                continue
            candidate_masks.append(global_mask)
            candidate_areas.append(local_area)

    for color_bin, _count in ranked_colors[:6]:
        seed_mask = active & np.all(quantized == color_bin[None, None, :], axis=2)
        _try_add_candidate(seed_mask)

    if ranked_hues:
        assist_hue_bins = ((assist_hue.astype(np.int16) + 6) // 12).astype(np.int16)
        assist_active = active & (assist_sat >= 16) & (assist_value >= 70)
        for hue_bin, _count in ranked_hues[:4]:
            seed_mask = assist_active & (assist_hue_bins == hue_bin)
            _try_add_candidate(seed_mask)

    debug["candidate_count"] = int(len(candidate_masks))
    debug["candidate_areas"] = candidate_areas
    if len(candidate_masks) < 2:
        debug["reason"] = "insufficient_localized_candidates"
        return [], debug

    debug["accepted"] = True
    debug["reason"] = "accepted"
    return candidate_masks, debug


def _split_component_via_assist_hue(
    component_mask: Any,
    assist_hue: Any | None,
    assist_sat: Any | None,
    assist_value: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    debug: dict[str, Any] = {
        "method": "assist_hue",
        "accepted": False,
    }
    if (
        assist_hue is None
        or assist_sat is None
        or assist_value is None
        or getattr(component_mask, "shape", None) != getattr(assist_hue, "shape", None)
    ):
        debug["reason"] = "missing_assist_inputs"
        return [], debug

    active = component_mask & (assist_sat >= 16) & (assist_value >= 70)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    if active_area < max(int(min_area_pixels * 1.8), 3500):
        debug["reason"] = "below_active_area_floor"
        return [], debug

    hue_values = assist_hue[active]
    if len(hue_values) == 0:
        debug["reason"] = "no_active_hue_values"
        return [], debug

    hue_bins = ((hue_values.astype(np.int16) + 6) // 12).astype(np.int16)
    unique_bins, counts = np.unique(hue_bins, return_counts=True)
    ranked_bins = sorted(
        (
            (int(bin_index), int(count))
            for bin_index, count in zip(unique_bins.tolist(), counts.tolist(), strict=False)
            if int(count) >= max(int(min_area_pixels * 0.9), int(active_area * 0.14))
        ),
        key=lambda item: -item[1],
    )
    debug["ranked_bin_count"] = int(len(ranked_bins))
    if len(ranked_bins) < 2:
        debug["reason"] = "insufficient_ranked_bins"
        return [], debug

    selected_bins: list[int] = []
    for bin_index, _count in ranked_bins:
        if not selected_bins:
            selected_bins.append(bin_index)
            continue
        if all(min(abs(bin_index - prev), 15 - abs(bin_index - prev)) >= 2 for prev in selected_bins):
            selected_bins.append(bin_index)
        if len(selected_bins) >= 3:
            break

    if len(selected_bins) < 2:
        debug["reason"] = "insufficient_selected_bins"
        return [], debug

    structure = np.ones((3, 3), dtype=bool)
    grown_masks: list[Any] = []
    used_seed_area = 0
    debug["selected_bins"] = [int(item) for item in selected_bins]
    seed_areas: list[int] = []
    grown_areas: list[int] = []
    for bin_index in selected_bins:
        seed_mask = active & (((assist_hue.astype(np.int16) + 6) // 12) == bin_index)
        seed_mask = _NDIMAGE.binary_opening(seed_mask, structure=structure, iterations=1)
        if not bool(np.any(seed_mask)):
            seed_areas.append(0)
            continue
        seed_areas.append(int(np.count_nonzero(seed_mask)))
        grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
        grown_area = int(np.count_nonzero(grown))
        grown_areas.append(grown_area)
        if grown_area < max(int(min_area_pixels * 0.8), 1200):
            continue
        if grown_area > int(active_area * 0.82):
            continue
        if any(_component_overlap_ratio(grown, existing)[0] >= 0.72 for existing in grown_masks):
            continue
        grown_masks.append(grown)
        used_seed_area += grown_area

    debug["seed_areas"] = seed_areas
    debug["grown_areas"] = grown_areas
    debug["grown_mask_count"] = int(len(grown_masks))
    debug["used_area"] = int(used_seed_area)
    if len(grown_masks) < 2:
        debug["reason"] = "insufficient_grown_masks"
        return [], debug
    if used_seed_area < int(active_area * 0.45):
        debug["reason"] = "insufficient_coverage"
        return [], debug
    debug["accepted"] = True
    debug["reason"] = "accepted"
    return grown_masks, debug


def _split_suspicious_component(
    component_mask: Any,
    min_area_pixels: int,
    wall_hint_mask: Any | None = None,
    primary_rgb: Any | None = None,
    assist_rgb: Any | None = None,
    primary_sat: Any | None = None,
    primary_value: Any | None = None,
    assist_hue: Any | None = None,
    assist_sat: Any | None = None,
    assist_value: Any | None = None,
) -> tuple[list[Any], str | None]:
    """Try each available split strategy in priority order and return the first that succeeds.

    Returns (split_masks, method_name, debug_entries). method_name is None if no split was found.
    """
    debug_entries: list[dict[str, Any]] = []
    split_masks = _split_component_via_wall_cuts(component_mask, wall_hint_mask, min_area_pixels)
    if len(split_masks) >= 2:
        return split_masks, "wall_cuts", [{"method": "wall_cuts", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)}]
    if int(np.count_nonzero(component_mask)) >= max(int(min_area_pixels * 10), 120000):
        split_masks, debug = _localize_oversized_component(
            component_mask,
            primary_rgb,
            assist_rgb,
            assist_hue,
            assist_sat,
            assist_value,
            min_area_pixels,
        )
        debug_entries.append(debug)
        if len(split_masks) >= 2:
            return split_masks, "localized_bins", debug_entries
    split_masks, debug = _split_component_via_color_distance(
        component_mask,
        primary_rgb,
        assist_rgb,
        min_area_pixels,
    )
    debug_entries.append(debug)
    if len(split_masks) >= 2:
        return split_masks, "color_distance", debug_entries
    split_masks = _split_component_via_local_support(
        component_mask,
        primary_sat,
        primary_value,
        assist_sat,
        assist_value,
        min_area_pixels,
    )
    if len(split_masks) >= 2:
        debug_entries.append({"method": "local_support", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)})
        return split_masks, "local_support", debug_entries
    debug_entries.append({"method": "local_support", "accepted": False, "reason": "no_split"})
    split_masks, debug = _split_component_via_assist_hue(
        component_mask,
        assist_hue,
        assist_sat,
        assist_value,
        min_area_pixels,
    )
    debug_entries.append(debug)
    if len(split_masks) >= 2:
        return split_masks, "assist_hue", debug_entries
    split_masks = _split_component_via_erosion(component_mask, min_area_pixels)
    if len(split_masks) >= 2:
        debug_entries.append({"method": "erosion_seeds", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)})
        return split_masks, "erosion_seeds", debug_entries
    debug_entries.append({"method": "erosion_seeds", "accepted": False, "reason": "no_split"})
    split_masks = _split_component_via_opening(component_mask, min_area_pixels)
    if len(split_masks) >= 2:
        debug_entries.append({"method": "opening_split", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)})
        return split_masks, "opening_split", debug_entries
    debug_entries.append({"method": "opening_split", "accepted": False, "reason": "no_split"})
    return [], None, debug_entries


def _component_should_keep(
    *,
    area: int,
    area_percent: float,
    fill_ratio: float,
    compactness: float,
    aspect_ratio: float,
    agreement_score: float,
    touches_border: bool,
    min_area_pixels: int,
    recovery_mode: bool = False,
) -> tuple[bool, list[str]]:
    """Decide whether a small component is worth keeping.

    Returns (keep, reasons). Small components below min_area_pixels may still
    be kept if geometric signals (compactness, aspect ratio, agreement) are strong.
    """
    reasons: list[str] = []
    if area < 220 and not recovery_mode:
        reasons.append("below_tiny_floor")
        return False, reasons
    small_cutoff = max(180, int(min_area_pixels * (0.65 if recovery_mode else 0.85)))
    if area >= min_area_pixels:
        return True, reasons

    if area < small_cutoff:
        reasons.append("below_small_cutoff")

    if compactness >= 0.22 and fill_ratio >= 0.5:
        reasons.append("compact_small_region")
    if aspect_ratio >= 2.2 and fill_ratio >= 0.42 and not touches_border:
        reasons.append("elongated_enclosed_region")
    if agreement_score >= 0.55:
        reasons.append("confirmed_by_variants")
    if recovery_mode and area_percent >= 0.002 and fill_ratio >= 0.42:
        reasons.append("recovery_candidate")

    keep = any(
        reason in reasons
        for reason in (
            "compact_small_region",
            "elongated_enclosed_region",
            "confirmed_by_variants",
            "recovery_candidate",
        )
    )
    return keep, reasons


def _detect_room_segments_pipeline(
    *,
    image_path: str,
    expected_room_count: int | None = None,
    max_segments: int | None = None,
    min_area_pixels: int = 1200,
    simplify_epsilon: float | None = None,
    assist_image_path: str | None = None,
    image_variant: str | None = None,
    assist_variant: str | None = None,
) -> dict[str, Any]:
    """Run the Pillow/NumPy/SciPy segmentation pipeline.

    Segments the primary map image by HSV hue clustering, optionally guided
    by a second image variant for wall-cut refinement. Returns the full
    segmentation result dict including segments, summary, and pipeline diagnostics.
    """
    if not (_PIL_SCIPY_READY and _NDIMAGE is not None):
        return {
            "available": False,
            "reason": "pipeline_unavailable",
            "message": "Pillow/scipy-based segmentation pipeline is not available in this environment.",
            "runtime": image_runtime_capabilities(),
            "segments": [],
        }

    try:
        image = PIL_Image.open(str(image_path)).convert("RGB")
    except Exception:
        _LOGGER.exception("Failed to read map image at %s", image_path)
        return {
            "available": False,
            "reason": "image_unreadable",
            "message": "Could not read the saved map image.",
            "runtime": image_runtime_capabilities(),
            "segments": [],
        }

    rgb = np.asarray(image, dtype=np.uint8)
    hsv = np.asarray(image.convert("HSV"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    image_area = float(width * height)
    hue = hsv[:, :, 0]

    structure = np.ones((3, 3), dtype=bool)
    merge_structure = np.ones((5, 5), dtype=bool)
    room_mask = _build_room_mask_from_hsv(hsv)
    base_room_mask = room_mask.copy()
    assist_registration: dict[str, Any] | None = None
    aligned_assist_room_mask: Any | None = None
    aligned_wall_mask: Any | None = None
    seam_wall_mask: Any | None = None
    removed_by_walls_mask: Any | None = None
    aligned_assist_rgb: Any | None = None
    aligned_assist_hue: Any | None = None
    aligned_assist_sat: Any | None = None
    aligned_assist_value: Any | None = None

    if assist_image_path:
        try:
            assist_image = PIL_Image.open(str(assist_image_path)).convert("RGB")
            assist_rgb = np.asarray(assist_image, dtype=np.uint8)
            assist_hsv = np.asarray(assist_image.convert("HSV"), dtype=np.uint8)
            assist_room_mask = _build_room_mask_from_hsv(assist_hsv)
            registration = _estimate_alignment(room_mask, assist_room_mask)
            aligned_assist_room_mask = _transform_mask(
                assist_room_mask,
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_room_mask = _NDIMAGE.binary_dilation(aligned_assist_room_mask, structure=structure, iterations=2)
            aligned_assist_rgb = _transform_color_image(
                assist_rgb,
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_hue = _transform_scalar_image(
                assist_hsv[:, :, 0],
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_sat = _transform_scalar_image(
                assist_hsv[:, :, 1],
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_value = _transform_scalar_image(
                assist_hsv[:, :, 2],
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )

            assist_wall_mask = _build_light_wall_mask(assist_hsv)
            aligned_wall_mask = _transform_mask(
                assist_wall_mask,
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_wall_mask = _NDIMAGE.binary_dilation(aligned_wall_mask, structure=structure, iterations=1)
            edge_hint = _mask_edge_band(base_room_mask, iterations=2)
            seam_zone = _NDIMAGE.binary_dilation(edge_hint, structure=merge_structure, iterations=1)
            seam_wall_mask = aligned_wall_mask & seam_zone
            # WHY: narrow seam cutting only — broad subtraction erased valid room
            # pixels because the light-image wall mask also captures background gradients.
            room_mask = base_room_mask & ~seam_wall_mask
            room_mask = _NDIMAGE.binary_opening(room_mask, structure=structure, iterations=1)
            room_mask = _NDIMAGE.binary_closing(room_mask, structure=structure, iterations=2)
            room_mask = _NDIMAGE.binary_fill_holes(room_mask)
            removed_by_walls_mask = base_room_mask & ~room_mask

            assist_registration = {
                "enabled": True,
                "assist_variant": assist_variant,
                "assist_image_path": assist_image_path,
                "scale": registration["scale"],
                "shift_x": registration["shift_x"],
                "shift_y": registration["shift_y"],
                "score": registration["score"],
            }
        except Exception as err:
            assist_registration = {
                "enabled": False,
                "assist_variant": assist_variant,
                "assist_image_path": assist_image_path,
                "error": f"{type(err).__name__}: {err}",
            }

    if not bool(np.any(room_mask)):
        return {
            "available": False,
            "reason": "no_room_pixels_detected",
            "message": "No room-like regions were detected in the image.",
            "runtime": image_runtime_capabilities(),
            "segments": [],
            "image": {"width": int(width), "height": int(height)},
            "segmentation": {
                "pipeline": "pillow_numpy_scipy",
                "registration": assist_registration,
                "image_variant": image_variant,
                "assist_variant": assist_variant,
            },
        }

    hue_smooth = _NDIMAGE.median_filter(hue, size=5)
    hue_bin = ((hue_smooth.astype(np.int16) + 8) // 16).astype(np.int16)
    active_bins = sorted({int(value) for value in hue_bin[room_mask]})

    segments: list[dict[str, Any]] = []
    segment_id = 1
    stage_counts: dict[str, Any] = {
        "clusters_seen": len(active_bins),
        "components_seen": 0,
        "split_candidates": 0,
        "split_generated_regions": 0,
        "kept_regions": 0,
        "recovered_regions": 0,
        "dropped_regions": 0,
    }
    deferred_small_regions: list[dict[str, Any]] = []

    for bin_index in active_bins:
        cluster_mask = room_mask & (hue_bin == bin_index)
        if not bool(np.any(cluster_mask)):
            continue

        # Merge same-hue fragments before labelling to reduce over-segmentation.
        cluster_mask = _NDIMAGE.binary_closing(cluster_mask, structure=merge_structure, iterations=2)
        cluster_mask = _NDIMAGE.binary_opening(cluster_mask, structure=structure, iterations=1)
        cluster_mask = _NDIMAGE.binary_fill_holes(cluster_mask)

        labeled, component_count = _NDIMAGE.label(cluster_mask, structure=structure)
        slices = _NDIMAGE.find_objects(labeled)
        for label_index in range(1, component_count + 1):
            label_slice = slices[label_index - 1] if label_index - 1 < len(slices) else None
            if label_slice is None:
                continue
            stage_counts["components_seen"] += 1

            component_mask = labeled[label_slice] == label_index

            y_slice, x_slice = label_slice
            x = int(x_slice.start or 0)
            y = int(y_slice.start or 0)
            w = int((x_slice.stop or 0) - x)
            h = int((y_slice.stop or 0) - y)

            component_mask = _NDIMAGE.binary_closing(component_mask, structure=merge_structure, iterations=1)
            component_mask = _NDIMAGE.binary_fill_holes(component_mask)
            area = int(np.count_nonzero(component_mask))

            touches_border = x <= 1 or y <= 1 or (x + w) >= (width - 1) or (y + h) >= (height - 1)
            fill_ratio = area / max(float(w * h), 1.0)
            area_percent = area / image_area
            perimeter = _mask_perimeter(component_mask)
            compactness = _compactness(area, perimeter)
            aspect_ratio = _aspect_ratio(w, h)

            component_rgb_full = rgb[y : y + h, x : x + w]
            component_hsv_full = hsv[y : y + h, x : x + w]
            component_rgb = component_rgb_full[component_mask]
            component_hsv = component_hsv_full[component_mask]
            mean_rgb = component_rgb.mean(axis=0) if len(component_rgb) else np.array([0.0, 0.0, 0.0])
            mean_saturation = float(component_hsv[:, 1].mean()) if len(component_hsv) else 0.0
            mean_value = float(component_hsv[:, 2].mean()) if len(component_hsv) else 0.0
            color_bgr = [int(round(float(mean_rgb[2]))), int(round(float(mean_rgb[1]))), int(round(float(mean_rgb[0])))]
            component_global = np.zeros_like(room_mask, dtype=bool)
            component_global[y : y + h, x : x + w] = component_mask
            agreement_score = _agreement_score(component_global, aligned_assist_room_mask)

            issues: list[str] = []
            if area_percent < 0.015 and agreement_score < 0.5:
                issues.append("tiny_region")
            if touches_border:
                issues.append("touches_border")
            if fill_ratio < 0.42:
                issues.append("possible_merge")
            if area_percent > 0.45:
                issues.append("oversized_region")
            if compactness < 0.08 and area_percent < 0.02:
                issues.append("fragmented_candidate")

            keep_small, keep_reasons = _component_should_keep(
                area=area,
                area_percent=area_percent,
                fill_ratio=fill_ratio,
                compactness=compactness,
                aspect_ratio=aspect_ratio,
                agreement_score=agreement_score,
                touches_border=touches_border,
                min_area_pixels=int(max(min_area_pixels, 1)),
                recovery_mode=False,
            )

            suspicious_merge = (
                area >= max(int(min_area_pixels * 4), 5200)
                and (fill_ratio < 0.58 or area_percent > 0.18 or "oversized_region" in issues)
            )
            split_masks: list[Any] = []
            split_method: str | None = None
            split_debug: list[dict[str, Any]] = []
            if suspicious_merge:
                stage_counts["split_candidates"] += 1
                split_masks, split_method, split_debug = _split_suspicious_component(
                    component_mask,
                    int(max(min_area_pixels, 1)),
                    wall_hint_mask=seam_wall_mask[y : y + h, x : x + w] if seam_wall_mask is not None else None,
                    primary_rgb=rgb[y : y + h, x : x + w],
                    assist_rgb=aligned_assist_rgb[y : y + h, x : x + w] if aligned_assist_rgb is not None else None,
                    primary_sat=component_hsv_full[:, :, 1],
                    primary_value=component_hsv_full[:, :, 2],
                    assist_hue=aligned_assist_hue[y : y + h, x : x + w] if aligned_assist_hue is not None else None,
                    assist_sat=aligned_assist_sat[y : y + h, x : x + w] if aligned_assist_sat is not None else None,
                    assist_value=aligned_assist_value[y : y + h, x : x + w] if aligned_assist_value is not None else None,
                )
                if split_debug:
                    stage_counts.setdefault("split_debug", []).append(
                        {
                            "cluster_index": int(bin_index),
                            "bbox": _bbox_from_stats(int(x), int(y), int(w), int(h)),
                            "area_pixels": int(area),
                            "fill_ratio": round(fill_ratio, 4),
                            "area_percent": round(area_percent, 4),
                            "methods": split_debug,
                        }
                    )

            masks_to_emit: list[tuple[Any, str | None]] = []
            if len(split_masks) >= 2:
                stage_counts["split_generated_regions"] += len(split_masks)
                masks_to_emit = [(mask, split_method) for mask in split_masks]
            else:
                masks_to_emit = [(component_mask, None)]

            for local_mask, local_split_method in masks_to_emit:
                if local_split_method == "localized_bins":
                    local_mask = _reclaim_localized_child_mask(
                        local_mask,
                        component_mask,
                        primary_sat=component_hsv_full[:, :, 1],
                        primary_value=component_hsv_full[:, :, 2],
                        assist_sat=aligned_assist_sat[y : y + h, x : x + w] if aligned_assist_sat is not None else None,
                        assist_value=aligned_assist_value[y : y + h, x : x + w] if aligned_assist_value is not None else None,
                    )
                local_area = int(np.count_nonzero(local_mask))
                if local_area <= 0:
                    continue
                local_indices = np.argwhere(local_mask)
                local_y0 = int(local_indices[:, 0].min())
                local_y1 = int(local_indices[:, 0].max()) + 1
                local_x0 = int(local_indices[:, 1].min())
                local_x1 = int(local_indices[:, 1].max()) + 1
                cropped_mask = local_mask[local_y0:local_y1, local_x0:local_x1]
                global_x = x + local_x0
                global_y = y + local_y0
                global_w = local_x1 - local_x0
                global_h = local_y1 - local_y0

                polygon_local, raw_point_count = _mask_to_polygon(cropped_mask, simplify_epsilon=simplify_epsilon)
                polygon = [[pt[0] + global_x, pt[1] + global_y] for pt in polygon_local]
                simplified_point_count = len(polygon)
                if simplified_point_count < 4:
                    stage_counts["dropped_regions"] += 1
                    continue

                local_touches_border = global_x <= 1 or global_y <= 1 or (global_x + global_w) >= (width - 1) or (global_y + global_h) >= (height - 1)
                local_fill_ratio = local_area / max(float(global_w * global_h), 1.0)
                local_area_percent = local_area / image_area
                local_perimeter = _mask_perimeter(cropped_mask)
                local_compactness = _compactness(local_area, local_perimeter)
                local_aspect_ratio = _aspect_ratio(global_w, global_h)

                local_component_global = np.zeros_like(room_mask, dtype=bool)
                local_component_global[global_y : global_y + global_h, global_x : global_x + global_w] = cropped_mask
                local_agreement_score = _agreement_score(local_component_global, aligned_assist_room_mask)
                local_mean_value = float(
                    hsv[global_y : global_y + global_h, global_x : global_x + global_w][cropped_mask][:, 2].mean()
                ) if np.count_nonzero(cropped_mask) else 0.0

                local_issues = list(issues)
                if simplified_point_count > 18:
                    local_issues.append("too_complex")
                if local_split_method:
                    local_issues.append(f"split_{local_split_method}")
                if local_fill_ratio < 0.42 and "possible_merge" not in local_issues:
                    local_issues.append("possible_merge")
                if local_mean_value < 118 and local_area < max(1800, int(min_area_pixels * 1.4)):
                    local_issues.append("dock_dark_artifact")
                if (global_w <= 4 or global_h <= 4 or local_aspect_ratio >= 10.0) and local_area < max(1600, int(min_area_pixels * 1.3)):
                    local_issues.append("thin_artifact")

                keep_now, local_keep_reasons = _component_should_keep(
                    area=local_area,
                    area_percent=local_area_percent,
                    fill_ratio=local_fill_ratio,
                    compactness=local_compactness,
                    aspect_ratio=local_aspect_ratio,
                    agreement_score=local_agreement_score,
                    touches_border=local_touches_border,
                    min_area_pixels=int(max(min_area_pixels, 1)),
                    recovery_mode=False,
                )

                confidence = 0.9
                confidence -= min(len([item for item in local_issues if not str(item).startswith("split_")]) * 0.1, 0.45)
                if local_fill_ratio < 0.55:
                    confidence -= 0.12
                if simplified_point_count > 14:
                    confidence -= 0.1
                confidence += min(local_agreement_score * 0.12, 0.12)
                confidence = max(0.05, min(0.99, round(confidence, 4)))

                candidate = {
                    "segment_id": f"segment_{segment_id}",
                    "cluster_index": int(bin_index),
                    "bbox": _bbox_from_stats(global_x, global_y, global_w, global_h),
                    "area_pixels": local_area,
                    "area_percent": round(local_area_percent, 4),
                    "polygon_pixel": polygon,
                    "point_count_raw": raw_point_count,
                    "point_count_simplified": simplified_point_count,
                    "center_pixel": [round(global_x + (global_w / 2.0), 2), round(global_y + (global_h / 2.0), 2)],
                    "fill_ratio": round(local_fill_ratio, 4),
                    "quality": _issue_quality(local_issues, confidence),
                    "confidence": confidence,
                    "issues": local_issues,
                    "suggested_color_bgr": color_bgr,
                    "mean_saturation": round(mean_saturation, 2),
                    "mean_value": round(local_mean_value, 2),
                    "compactness": round(local_compactness, 4),
                    "aspect_ratio": round(local_aspect_ratio, 4),
                    "variant_agreement": round(local_agreement_score, 4),
                    "variant_support": (
                        "both" if local_agreement_score >= 0.55
                        else "primary_only"
                    ),
                    "structural_role": _structural_role(
                        area_percent=local_area_percent,
                        aspect_ratio=local_aspect_ratio,
                        fill_ratio=local_fill_ratio,
                    ),
                    "segmentation_state": _segmentation_state(
                        issues=local_issues,
                        fill_ratio=local_fill_ratio,
                        compactness=local_compactness,
                    ),
                    "local_split_suspicion": suspicious_merge,
                    "edit_readiness": (
                        "ready" if confidence >= 0.78 and simplified_point_count <= 18
                        else "review"
                    ),
                    "matched_room_id": None,
                    "matched_room_label": None,
                    "_split_method": local_split_method,
                    "_keep_reasons": local_keep_reasons,
                    "_global_mask": local_component_global,
                }

                drop_reasons: list[str] = []
                if local_area_percent > 0.45:
                    keep_now = False
                    drop_reasons.append("area_percent_too_large")
                if "dock_dark_artifact" in local_issues:
                    keep_now = False
                    drop_reasons.append("dock_dark_artifact")
                if "thin_artifact" in local_issues:
                    keep_now = False
                    drop_reasons.append("thin_artifact")
                if "oversized_region" in local_issues:
                    if local_split_method != "localized_bins":
                        keep_now = False
                        drop_reasons.append("oversized_region")
                if local_split_method == "assist_hue" and (
                    local_area_percent > 0.24 or local_fill_ratio < 0.26 or local_compactness < 0.08
                ):
                    keep_now = False
                    drop_reasons.append("assist_hue_child_rejected")
                if area_percent > 0.3 and mean_saturation < 30 and not local_split_method:
                    keep_now = False
                    drop_reasons.append("low_saturation_large_parent")
                if local_split_method == "localized_bins":
                    hard_reject_localized = False
                    if local_area_percent < 0.0025 and local_area < max(1100, int(min_area_pixels * 0.9)):
                        keep_now = False
                        hard_reject_localized = True
                        drop_reasons.append("localized_child_too_small")
                    elif local_fill_ratio < 0.12:
                        keep_now = False
                        hard_reject_localized = True
                        drop_reasons.append("localized_child_sparse")
                    else:
                        # WHY: localized children are partial color pockets, so lower
                        # compactness/fill thresholds apply than for generic split paths.
                        if "possible_merge" in local_issues and local_fill_ratio >= 0.18:
                            local_issues = [issue for issue in local_issues if issue != "possible_merge"]
                            candidate["issues"] = local_issues
                        if confidence < 0.7:
                            confidence = max(confidence, 0.72)
                            candidate["confidence"] = confidence
                            candidate["quality"] = _issue_quality(local_issues, confidence)
                        if local_aspect_ratio >= 4.5 and local_area < max(4200, int(min_area_pixels * 2.8)):
                            keep_now = False
                            hard_reject_localized = True
                            drop_reasons.append("localized_child_connector")
                        if local_compactness < 0.03 and local_fill_ratio < 0.28:
                            keep_now = False
                            hard_reject_localized = True
                            drop_reasons.append("localized_child_fragment")
                        if not hard_reject_localized:
                            keep_now = keep_now or (
                                local_area >= max(1100, int(min_area_pixels * 0.9))
                                and local_fill_ratio >= 0.18
                                and local_compactness >= 0.04
                            )

                if keep_now and not (local_touches_border and local_fill_ratio < 0.18 and local_area_percent > 0.03):
                    segments.append(candidate)
                    stage_counts["kept_regions"] += 1
                    segment_id += 1
                else:
                    candidate["_drop_reasons"] = drop_reasons
                    deferred_small_regions.append(candidate)
                    stage_counts["dropped_regions"] += 1

    deduped_count = 0
    localized_segments = [
        item for item in segments
        if str(item.get("_split_method") or "") == "localized_bins"
    ]
    other_segments = [
        item for item in segments
        if str(item.get("_split_method") or "") != "localized_bins"
    ]
    if localized_segments:
        localized_segments.sort(
            key=lambda item: (
                -float(item.get("confidence", 0.0)),
                -float(item.get("fill_ratio", 0.0)),
                -float(item.get("compactness", 0.0)),
                -float(item.get("area_pixels", 0)),
            )
        )
        pruned_localized: list[dict[str, Any]] = []
        for candidate in localized_segments:
            candidate_mask = candidate.get("_global_mask")
            sibling_overlap = False
            for kept in pruned_localized:
                kept_mask = kept.get("_global_mask")
                overlap_a, overlap_b = _component_overlap_ratio(candidate_mask, kept_mask)
                if max(overlap_a, overlap_b) >= 0.35:
                    sibling_overlap = True
                    deduped_count = int(deduped_count) + 1
                    break
            if sibling_overlap:
                continue
            pruned_localized.append(candidate)
        localized_segments = pruned_localized[:4]

    segments = other_segments + localized_segments
    segments.sort(key=lambda item: (-float(item.get("area_pixels", 0)), str(item.get("segment_id", ""))))
    deduped_segments: list[dict[str, Any]] = []
    for candidate in segments:
        candidate_mask = candidate.get("_global_mask")
        drop_candidate = False
        for kept in deduped_segments:
            kept_mask = kept.get("_global_mask")
            overlap_a, overlap_b = _component_overlap_ratio(candidate_mask, kept_mask)
            same_center = (
                abs(float(candidate.get("center_pixel", [0, 0])[0]) - float(kept.get("center_pixel", [0, 0])[0])) <= 28
                and abs(float(candidate.get("center_pixel", [0, 0])[1]) - float(kept.get("center_pixel", [0, 0])[1])) <= 28
            )
            if overlap_a >= 0.8 or overlap_b >= 0.8 or (same_center and max(overlap_a, overlap_b) >= 0.55):
                drop_candidate = True
                deduped_count += 1
                break
        if not drop_candidate:
            deduped_segments.append(candidate)
    segments = deduped_segments

    if expected_room_count and len(segments) < int(expected_room_count):
        deficit = int(expected_room_count) - len(segments)
        deferred_small_regions.sort(
            key=lambda item: (
                -float(item.get("variant_agreement", 0)),
                -float(item.get("compactness", 0)),
                -float(item.get("fill_ratio", 0)),
                -float(item.get("area_pixels", 0)),
            )
        )
        for candidate in deferred_small_regions:
            if deficit <= 0:
                break
            candidate_issues = list(candidate.get("issues") or [])
            if any(
                issue in candidate_issues
                for issue in ("dock_dark_artifact", "thin_artifact", "oversized_region", "fragmented_candidate")
            ):
                continue
            if float(candidate.get("area_percent", 0.0)) > 0.2:
                continue
            if int(candidate.get("area_pixels", 0)) < max(220, int(min_area_pixels * 0.4)):
                continue
            keep_now, local_keep_reasons = _component_should_keep(
                area=int(candidate.get("area_pixels", 0)),
                area_percent=float(candidate.get("area_percent", 0.0)),
                fill_ratio=float(candidate.get("fill_ratio", 0.0)),
                compactness=float(candidate.get("compactness", 0.0)),
                aspect_ratio=float(candidate.get("aspect_ratio", 0.0)),
                agreement_score=float(candidate.get("variant_agreement", 0.0)),
                touches_border=("touches_border" in (candidate.get("issues") or [])),
                min_area_pixels=int(max(min_area_pixels, 1)),
                recovery_mode=True,
            )
            if not keep_now:
                continue
            candidate["issues"] = [issue for issue in (candidate.get("issues") or []) if issue != "tiny_region"]
            candidate["issues"].append("recovered_count_deficit")
            candidate["confidence"] = max(float(candidate.get("confidence", 0.0)), 0.62)
            candidate["quality"] = _issue_quality(list(candidate["issues"]), float(candidate["confidence"]))
            candidate["segment_id"] = f"segment_{segment_id}"
            candidate["variant_support"] = (
                "both" if float(candidate.get("variant_agreement", 0.0)) >= 0.55
                else str(candidate.get("variant_support") or "primary_only")
            )
            candidate["_keep_reasons"] = list(local_keep_reasons)
            segments.append(candidate)
            stage_counts["recovered_regions"] += 1
            segment_id += 1
            deficit -= 1

    segments.sort(key=lambda item: (-float(item.get("area_pixels", 0)), str(item.get("segment_id", ""))))
    if max_segments is not None and max_segments > 0:
        segments = segments[: int(max_segments)]

    quality_counts: dict[str, int] = {}
    for segment in segments:
        segment.pop("_keep_reasons", None)
        segment.pop("_global_mask", None)
        segment.pop("_split_method", None)
        segment.pop("_drop_reasons", None)
        quality = str(segment.get("quality") or "unknown")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1

    assist_enabled = bool(
        isinstance(assist_registration, dict)
        and assist_registration.get("enabled")
    )
    message = "Image-assisted room segments generated via the Pillow/NumPy/SciPy pipeline."
    if assist_enabled:
        message = "Image-assisted room segments generated via the Pillow/NumPy/SciPy pipeline using primary and assist image variants."

    return {
        "available": True,
        "reason": "ready",
        "message": message,
        "runtime": image_runtime_capabilities(),
        "image": {
            "width": int(width),
            "height": int(height),
        },
        "segmentation": {
            "expected_room_count": int(expected_room_count or 0),
            "cluster_count": len(active_bins),
            "room_pixel_count": int(np.count_nonzero(room_mask)),
            "min_area_pixels": int(max(min_area_pixels, 1)),
            "simplify_epsilon": None if simplify_epsilon is None else float(simplify_epsilon),
            "pipeline": "pillow_numpy_scipy",
            "image_variant": image_variant,
            "assist_variant": assist_variant,
            "registration": assist_registration,
            "stages": {
                "base_mask_generation": {
                    "room_pixel_count": int(np.count_nonzero(base_room_mask)),
                    "left_right": _mask_left_right_counts(base_room_mask),
                },
                "variant_reconciliation": {
                    "assist_enabled": assist_enabled,
                    "agreement_pixel_count": int(np.count_nonzero(base_room_mask & aligned_assist_room_mask)) if aligned_assist_room_mask is not None else 0,
                    "wall_pixel_count": int(np.count_nonzero(aligned_wall_mask)) if aligned_wall_mask is not None else 0,
                    "seam_wall_pixel_count": int(np.count_nonzero(seam_wall_mask)) if seam_wall_mask is not None else 0,
                    "removed_by_wall_cut_pixel_count": int(np.count_nonzero(removed_by_walls_mask)) if removed_by_walls_mask is not None else 0,
                    "removed_by_wall_cut_left_right": _mask_left_right_counts(removed_by_walls_mask) if removed_by_walls_mask is not None else {"left": 0, "right": 0},
                    "reconciled_room_pixel_count": int(np.count_nonzero(room_mask)),
                    "reconciled_left_right": _mask_left_right_counts(room_mask),
                },
                "connected_components": {
                    "clusters_seen": int(stage_counts["clusters_seen"]),
                    "components_seen": int(stage_counts["components_seen"]),
                },
                "candidate_scoring": {
                    "kept_regions": int(stage_counts["kept_regions"]),
                    "dropped_regions": int(stage_counts["dropped_regions"]),
                    "deduped_regions": int(deduped_count),
                },
                "suspicious_region_split_pass": {
                    "split_candidates": int(stage_counts["split_candidates"]),
                    "split_generated_regions": int(stage_counts["split_generated_regions"]),
                    "debug": stage_counts.get("split_debug", []),
                    "localized_drop_debug": [
                        {
                            "segment_id": str(item.get("segment_id")),
                            "area_pixels": int(item.get("area_pixels", 0)),
                            "area_percent": float(item.get("area_percent", 0.0)),
                            "fill_ratio": float(item.get("fill_ratio", 0.0)),
                            "compactness": float(item.get("compactness", 0.0)),
                            "issues": list(item.get("issues") or []),
                            "drop_reasons": list(item.get("_drop_reasons") or []),
                        }
                        for item in deferred_small_regions
                        if str(item.get("_split_method") or "") == "localized_bins"
                    ],
                },
                "recovery_pass": {
                    "recovered_regions": int(stage_counts["recovered_regions"]),
                    "count_deficit_after_recovery": max(0, int(expected_room_count or 0) - len(segments)),
                },
            },
        },
        "summary": {
            "segment_count": len(segments),
            "quality_counts": quality_counts,
            "good_or_better_count": sum(
                1 for segment in segments
                if str(segment.get("quality")) in {"good", "strong"}
            ),
        },
        "segments": segments,
    }


def detect_room_segments(
    *,
    image_path: str,
    expected_room_count: int | None = None,
    max_segments: int | None = None,
    min_area_pixels: int = 1200,
    simplify_epsilon: float | None = None,
    assist_image_path: str | None = None,
    image_variant: str | None = None,
    assist_variant: str | None = None,
) -> dict[str, Any]:
    """Return suggested room-like segments from a clean unlabeled map image."""
    return _detect_room_segments_pipeline(
        image_path=image_path,
        expected_room_count=expected_room_count,
        max_segments=max_segments,
        min_area_pixels=min_area_pixels,
        simplify_epsilon=simplify_epsilon,
        assist_image_path=assist_image_path,
        image_variant=image_variant,
        assist_variant=assist_variant,
    )
