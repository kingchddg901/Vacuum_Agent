"""Brand-agnostic image and geometry primitives for vacuum map segmentors.

This module is the recommended starting point when writing a new segmentor
adapter (see ``docs/contributing/porting-guide.md``).  Every function here is
pure and has no knowledge of Eufy, Roborock, or any other brand.

What lives here
~~~~~~~~~~~~~~~
- Optional-dependency setup (numpy, Pillow, scipy) — import ``np`` and
  ``_NDIMAGE`` from here rather than repeating the guard pattern.
- ``image_runtime_capabilities`` — check library availability at runtime.
- Polygon geometry: ``rdp``, ``polygon_area``, ``normalize_polygon``,
  ``bbox_from_stats``
- Mask–polygon conversion: ``mask_to_polygon``, ``mask_perimeter``
- Shape metrics: ``compactness``, ``aspect_ratio``
- Mask comparison: ``mask_iou``, ``agreement_score``,
  ``component_overlap_ratio``, ``mask_left_right_counts``, ``mask_edge_band``
- Image transforms: ``transform_mask``, ``transform_scalar_image``,
  ``transform_color_image``
- Multi-image alignment: ``estimate_alignment``
- Color features: ``normalized_color_features``

Typical import pattern for a new segmentor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    from ..mapping.segment_primitives import (
        np, _NDIMAGE, _PIL_SCIPY_READY,
        image_runtime_capabilities,
        mask_to_polygon, mask_iou, estimate_alignment,
        rdp, compactness, aspect_ratio,
    )
"""

from __future__ import annotations

import importlib
import logging
import math
from collections import defaultdict
from typing import Any

_LOGGER = logging.getLogger(__name__)


# -- optional dependency setup ------------------------------------------------

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


# -- runtime capability report ------------------------------------------------

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


# -- polygon geometry ---------------------------------------------------------

def bbox_from_stats(x: int, y: int, w: int, h: int) -> dict[str, int]:
    """Return a bbox dict from top-left corner and dimensions."""
    return {
        "x": int(x),
        "y": int(y),
        "width": int(w),
        "height": int(h),
    }


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker polyline simplification."""
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

    left = rdp(points[: index + 1], epsilon)
    right = rdp(points[index:], epsilon)
    return left[:-1] + right


def polygon_area(points: list[tuple[float, float]]) -> float:
    """Return the signed area of a polygon via the shoelace formula."""
    if len(points) < 3:
        return 0.0
    area = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def normalize_polygon(points: list[tuple[float, float]]) -> list[list[float]]:
    """Round polygon vertices to 2 dp and return as nested lists."""
    polygon: list[list[float]] = []
    for x, y in points:
        polygon.append([round(float(x), 2), round(float(y), 2)])
    return polygon


# -- mask–polygon conversion --------------------------------------------------

def mask_to_polygon(
    mask: Any, simplify_epsilon: float | None = None
) -> tuple[list[list[float]], int]:
    """Trace the outer boundary of a boolean mask and return a simplified polygon.

    Returns ``(polygon_points, raw_point_count)``.  The polygon is simplified
    with RDP; ``raw_point_count`` is the vertex count before simplification.
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
                candidates.sort(
                    key=lambda point: (
                        math.atan2(point[1] - current[1], point[0] - current[0])
                        - math.atan2(prev[1] - current[1], prev[0] - current[0])
                    )
                )
            chosen = candidates[0]
            unused.remove((current, chosen))
            loop.append(chosen)
            current = chosen

        if len(loop) >= 4 and loop[0] == loop[-1]:
            loops.append([(float(x), float(y)) for (x, y) in loop[:-1]])

    if not loops:
        return ([], 0)

    best_loop = max(loops, key=lambda pts: abs(polygon_area(pts)))
    raw_point_count = len(best_loop)
    epsilon = (
        float(simplify_epsilon)
        if simplify_epsilon is not None
        else max(1.0, math.sqrt(max(raw_point_count, 1)) * 0.42)
    )
    simplified = rdp(best_loop + [best_loop[0]], epsilon)
    simplified = simplified[:-1] if simplified and simplified[0] == simplified[-1] else simplified

    if raw_point_count >= 700 and len(simplified) <= 6:
        epsilon = max(0.8, epsilon * 0.72)
        simplified = rdp(best_loop + [best_loop[0]], epsilon)
        simplified = simplified[:-1] if simplified and simplified[0] == simplified[-1] else simplified

    if len(simplified) < 4:
        simplified = best_loop

    return (normalize_polygon(simplified), raw_point_count)


# -- shape metrics ------------------------------------------------------------

def mask_perimeter(mask: Any) -> int:
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


def compactness(area: int, perimeter: int) -> float:
    """Return the isoperimetric quotient (4πA / P²).  Range 0–1; 1 = circle."""
    if area <= 0 or perimeter <= 0:
        return 0.0
    return float((4.0 * math.pi * area) / max(float(perimeter * perimeter), 1.0))


def aspect_ratio(width: int, height: int) -> float:
    """Return max/min dimension ratio.  1.0 = square; higher = more elongated."""
    if width <= 0 or height <= 0:
        return 0.0
    return float(max(width, height)) / float(max(min(width, height), 1))


# -- mask comparison & scoring ------------------------------------------------

def mask_iou(mask_a: Any, mask_b: Any) -> float:
    """Return intersection-over-union of two boolean masks."""
    if getattr(mask_a, "shape", None) != getattr(mask_b, "shape", None):
        return 0.0
    union = np.count_nonzero(mask_a | mask_b)
    if union <= 0:
        return 0.0
    intersection = np.count_nonzero(mask_a & mask_b)
    return float(intersection) / float(union)


def agreement_score(component_global: Any, assist_mask: Any | None) -> float:
    """Return fraction of component pixels confirmed by the assist mask (0–1)."""
    if assist_mask is None or getattr(component_global, "shape", None) != getattr(assist_mask, "shape", None):
        return 0.0
    area = np.count_nonzero(component_global)
    if area <= 0:
        return 0.0
    overlap = np.count_nonzero(component_global & assist_mask)
    return float(overlap) / float(area)


def component_overlap_ratio(mask_a: Any, mask_b: Any) -> tuple[float, float]:
    """Return ``(overlap/area_a, overlap/area_b)`` for two boolean masks."""
    if getattr(mask_a, "shape", None) != getattr(mask_b, "shape", None):
        return (0.0, 0.0)
    area_a = np.count_nonzero(mask_a)
    area_b = np.count_nonzero(mask_b)
    if area_a <= 0 or area_b <= 0:
        return (0.0, 0.0)
    intersection = np.count_nonzero(mask_a & mask_b)
    return (float(intersection) / float(area_a), float(intersection) / float(area_b))


def mask_left_right_counts(mask: Any) -> dict[str, int]:
    """Return pixel counts in the left and right halves of a mask."""
    height, width = mask.shape
    midpoint = width // 2
    return {
        "left": int(np.count_nonzero(mask[:, :midpoint])),
        "right": int(np.count_nonzero(mask[:, midpoint:])),
    }


def mask_edge_band(mask: Any, iterations: int = 2) -> Any:
    """Return the edge band of a mask (dilated XOR eroded) for seam detection."""
    structure = np.ones((3, 3), dtype=bool)
    dilated = _NDIMAGE.binary_dilation(mask, structure=structure, iterations=max(1, int(iterations)))
    eroded = _NDIMAGE.binary_erosion(mask, structure=structure, iterations=max(1, int(iterations)))
    return dilated ^ eroded


# -- image transforms ---------------------------------------------------------

def transform_mask(
    mask: Any, scale: float, shift_x: int, shift_y: int, target_shape: tuple[int, int]
) -> Any:
    """Scale and translate a boolean mask into a canvas of ``target_shape``."""
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


def transform_scalar_image(
    image: Any, scale: float, shift_x: int, shift_y: int, target_shape: tuple[int, int]
) -> Any:
    """Scale and translate a single-channel float image into a canvas of ``target_shape``."""
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


def transform_color_image(
    image: Any, scale: float, shift_x: int, shift_y: int, target_shape: tuple[int, int]
) -> Any:
    """Scale and translate each channel of an RGB image into a canvas of ``target_shape``."""
    channels = [
        transform_scalar_image(image[:, :, index], scale, shift_x, shift_y, target_shape)
        for index in range(image.shape[2])
    ]
    return np.stack(channels, axis=2)


# -- multi-image alignment ----------------------------------------------------

def estimate_alignment(reference_mask: Any, candidate_mask: Any) -> dict[str, Any]:
    """Brute-force search for the best scale/shift alignment of ``candidate_mask``
    onto ``reference_mask``.

    Returns a dict with ``scale``, ``shift_x``, ``shift_y``, and the best IoU
    ``score``.  Search grid: scales ±6 %, shifts ±24 px in 6 px steps.
    """
    target_shape = reference_mask.shape
    baseline = transform_mask(candidate_mask, 1.0, 0, 0, target_shape)
    best = {
        "scale": 1.0,
        "shift_x": 0,
        "shift_y": 0,
        "score": round(mask_iou(reference_mask, baseline), 4),
    }
    scales = [0.94, 0.97, 1.0, 1.03, 1.06]
    shifts = range(-24, 25, 6)

    for scale in scales:
        for shift_y in shifts:
            for shift_x in shifts:
                transformed = transform_mask(candidate_mask, scale, shift_x, shift_y, target_shape)
                score = mask_iou(reference_mask, transformed)
                if score > float(best["score"]):
                    best = {
                        "scale": float(scale),
                        "shift_x": int(shift_x),
                        "shift_y": int(shift_y),
                        "score": round(float(score), 4),
                    }
    return best


# -- color features -----------------------------------------------------------

def normalized_color_features(rgb: Any) -> Any:
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
