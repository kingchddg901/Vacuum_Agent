"""Affine transform between vacuum coordinate space and map image pixel space."""

from __future__ import annotations

import math
from typing import Any

# numpy is available in HA's Python environment via scipy/sklearn deps.
try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum calibration pairs required to compute a transform.
MIN_PAIRS_FOR_TRANSFORM = 3

# Cluster threshold — vacuum units. Corners within this distance are
# considered the same physical corner and merged via running centroid.
CLUSTER_THRESHOLD_UNITS = 50.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Return Euclidean distance between two points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return float(value), or default when value is None/unavailable/unparseable."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return float(value)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Affine transform computation
# ---------------------------------------------------------------------------

def compute_affine_transform(
    pairs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compute affine transform matrix from calibration pairs.

    Parameters
    ----------
    pairs:
        List of calibration pair dicts. Each must have:
          vacuum: [vx, vy]
          pixel:  [px, py]

    Returns a dict with:
      matrix: [[a,b,tx],[c,d,ty],[0,0,1]]  (3×3 row-major)
      pair_count: int
      residual_pixels: float  (mean reprojection error in pixels)
    Returns None if fewer than MIN_PAIRS_FOR_TRANSFORM valid pairs.
    """
    if not _NUMPY_AVAILABLE:
        return None

    valid = [
        p for p in pairs
        if isinstance(p.get("vacuum"), list) and len(p["vacuum"]) == 2
        and isinstance(p.get("pixel"), list) and len(p["pixel"]) == 2
    ]

    if len(valid) < MIN_PAIRS_FOR_TRANSFORM:
        return None

    # Build matrices for least-squares: A · x = b
    # For each pair (vx,vy) → (px,py):
    #   [vx, vy, 1, 0,  0,  0] · [a,b,tx,c,d,ty]^T = px
    #   [0,  0,  0, vx, vy, 1] · [a,b,tx,c,d,ty]^T = py
    A_rows = []
    b_rows = []

    for pair in valid:
        vx, vy = float(pair["vacuum"][0]), float(pair["vacuum"][1])
        px, py = float(pair["pixel"][0]),  float(pair["pixel"][1])

        A_rows.append([vx, vy, 1, 0,  0,  0])
        b_rows.append(px)
        A_rows.append([0,  0,  0, vx, vy, 1])
        b_rows.append(py)

    A = np.array(A_rows, dtype=float)
    b = np.array(b_rows, dtype=float)

    result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    a, bv, tx, c, d, ty = result.tolist()

    matrix = [
        [a,  bv, tx],
        [c,  d,  ty],
        [0.0, 0.0, 1.0],
    ]

    # Compute mean reprojection error.
    errors = []
    for pair in valid:
        vx, vy = float(pair["vacuum"][0]), float(pair["vacuum"][1])
        px, py = float(pair["pixel"][0]),  float(pair["pixel"][1])
        proj = vacuum_to_pixel([vx, vy], matrix)
        errors.append(_distance((proj[0], proj[1]), (px, py)))

    residual = round(float(np.mean(errors)), 3) if errors else 0.0

    return {
        "matrix": matrix,
        "pair_count": len(valid),
        "residual_pixels": residual,
    }


# ---------------------------------------------------------------------------
# Coordinate application
# ---------------------------------------------------------------------------

def vacuum_to_pixel(
    vacuum_point: list[float] | tuple[float, float],
    matrix: list[list[float]],
) -> tuple[float, float]:
    """Apply affine matrix to convert vacuum coords to pixel coords.

    Parameters
    ----------
    vacuum_point: [vx, vy]
    matrix: 3×3 affine matrix (row-major)

    Returns (px, py) as floats.
    """
    vx = float(vacuum_point[0])
    vy = float(vacuum_point[1])

    a,  bv, tx = matrix[0]
    c,  d,  ty = matrix[1]

    px = a * vx + bv * vy + tx
    py = c * vx + d  * vy + ty

    return (round(px, 2), round(py, 2))


def pixel_to_vacuum(
    pixel_point: list[float] | tuple[float, float],
    matrix: list[list[float]],
) -> tuple[float, float] | None:
    """Apply inverse affine matrix to convert pixel coords to vacuum coords.

    Returns None if the matrix is singular (non-invertible).
    """
    if not _NUMPY_AVAILABLE:
        return None

    M = np.array(matrix, dtype=float)
    try:
        M_inv = np.linalg.inv(M)
    except np.linalg.LinAlgError:
        return None

    px = float(pixel_point[0])
    py = float(pixel_point[1])
    point = np.array([px, py, 1.0])
    result = M_inv @ point

    return (round(float(result[0]), 2), round(float(result[1]), 2))


def reproject_machine_pairs(
    pairs: list[dict[str, Any]],
    matrix: list[list[float]],
) -> list[dict[str, Any]]:
    """Re-derive pixel coordinates for all machine-source pairs.

    Manual pairs (source == "manual") are never touched.
    Machine pairs have their pixel coords recomputed from the
    current transform whenever the transform is updated.
    """
    updated = []
    for pair in pairs:
        p = dict(pair)
        if p.get("source") == "manual":
            updated.append(p)
            continue

        vacuum = p.get("vacuum")
        if isinstance(vacuum, list) and len(vacuum) == 2:
            new_pixel = vacuum_to_pixel(vacuum, matrix)
            p["pixel"] = list(new_pixel)

        updated.append(p)
    return updated


# ---------------------------------------------------------------------------
# Calibration pair clustering
# ---------------------------------------------------------------------------

def merge_or_add_corner(
    pairs: list[dict[str, Any]],
    new_vacuum: tuple[float, float],
    matrix: list[list[float]] | None,
    *,
    threshold: float = CLUSTER_THRESHOLD_UNITS,
) -> tuple[list[dict[str, Any]], bool]:
    """Merge a machine-detected corner into the nearest existing cluster,
    or add as a new machine pair if none is within threshold.

    Only merges into machine-source pairs — manual pairs are ground truth
    and are never modified.

    Parameters
    ----------
    pairs:       current calibration pair list
    new_vacuum:  (vx, vy) of the new corner in vacuum coords
    matrix:      current transform matrix (used to derive pixel coords)
    threshold:   cluster radius in vacuum units

    Returns (updated_pairs, was_merged).
    """
    vx, vy = float(new_vacuum[0]), float(new_vacuum[1])

    best_idx = None
    best_dist = float("inf")

    for i, pair in enumerate(pairs):
        if pair.get("source") != "machine":
            continue
        pv = pair.get("vacuum")
        if not isinstance(pv, list) or len(pv) != 2:
            continue
        dist = _distance((vx, vy), (float(pv[0]), float(pv[1])))
        if dist < threshold and dist < best_dist:
            best_dist = dist
            best_idx = i

    updated = list(pairs)

    if best_idx is not None:
        # Merge into existing cluster via running centroid.
        existing = dict(updated[best_idx])
        n = int(existing.get("cluster_count", 1))
        old_vx = float(existing["vacuum"][0])
        old_vy = float(existing["vacuum"][1])

        new_centroid_vx = (old_vx * n + vx) / (n + 1)
        new_centroid_vy = (old_vy * n + vy) / (n + 1)

        existing["vacuum"] = [round(new_centroid_vx, 4), round(new_centroid_vy, 4)]
        existing["cluster_count"] = n + 1

        if matrix is not None:
            new_pixel = vacuum_to_pixel(existing["vacuum"], matrix)
            existing["pixel"] = list(new_pixel)

        updated[best_idx] = existing
        return updated, True

    # No nearby cluster — add as new machine pair.
    new_pair: dict[str, Any] = {
        "vacuum": [round(vx, 4), round(vy, 4)],
        "pixel": [],
        "label": f"corner_cluster_{len([p for p in pairs if p.get('source') == 'machine']) + 1}",
        "source": "machine",
        "cluster_count": 1,
    }

    if matrix is not None:
        new_pair["pixel"] = list(vacuum_to_pixel([vx, vy], matrix))

    updated.append(new_pair)
    return updated, False


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def transform_is_ready(pairs: list[dict[str, Any]]) -> bool:
    """Return True if enough valid pairs exist to compute a transform."""
    valid = [
        p for p in pairs
        if isinstance(p.get("vacuum"), list) and len(p["vacuum"]) == 2
        and isinstance(p.get("pixel"), list) and len(p["pixel"]) == 2
    ]
    return len(valid) >= MIN_PAIRS_FOR_TRANSFORM


def transform_quality(residual_pixels: float) -> str:
    """Return a human-readable quality label for a transform residual.

    Thresholds tuned for typical map image resolutions (~1000×1000px).
    """
    if residual_pixels <= 5.0:
        return "excellent"
    if residual_pixels <= 15.0:
        return "good"
    if residual_pixels <= 30.0:
        return "fair"
    return "poor"
