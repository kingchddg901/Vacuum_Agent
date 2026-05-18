"""Room boundary geometry: Douglas-Peucker simplification, corner detection, polygon utilities, and transition scoring."""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Douglas-Peucker simplification epsilon (vacuum units).
# Lower = more detail preserved. Higher = more aggressive simplification.
DEFAULT_DP_EPSILON = 5.0

# Minimum angle change (degrees) to classify a point as a corner.
DEFAULT_CORNER_ANGLE_THRESHOLD = 45.0

# Minimum number of points in a trail to attempt simplification.
MIN_TRAIL_POINTS = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _distance_point_to_segment(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    """Return perpendicular distance from point to line segment."""
    px, py = point
    ax, ay = seg_start
    bx, by = seg_end

    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        # Degenerate segment — return distance to the point itself.
        return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    nearest_x = ax + t * dx
    nearest_y = ay + t * dy

    return math.sqrt((px - nearest_x) ** 2 + (py - nearest_y) ** 2)


def _angle_between_segments(
    p1: tuple[float, float],
    vertex: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Return the angle in degrees at vertex between segments p1→vertex and vertex→p2."""
    ax = vertex[0] - p1[0]
    ay = vertex[1] - p1[1]
    bx = p2[0] - vertex[0]
    by = p2[1] - vertex[1]

    dot = ax * bx + ay * by
    mag_a = math.sqrt(ax * ax + ay * ay)
    mag_b = math.sqrt(bx * bx + by * by)

    if mag_a < 1e-9 or mag_b < 1e-9:
        return 0.0

    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
    angle_rad = math.acos(cos_angle)
    direction_change = 180.0 - math.degrees(angle_rad)
    return abs(direction_change)


# ---------------------------------------------------------------------------
# Douglas-Peucker simplification
# ---------------------------------------------------------------------------

def douglas_peucker(
    points: list[tuple[float, float]],
    epsilon: float = DEFAULT_DP_EPSILON,
) -> list[tuple[float, float]]:
    """Simplify a polyline using the Douglas-Peucker algorithm.

    Parameters
    ----------
    points:  list of (x, y) tuples
    epsilon: maximum allowed perpendicular deviation in vacuum units

    Returns a simplified list of (x, y) tuples.
    """
    if len(points) < 3:
        return list(points)

    # Find the point furthest from the line start→end.
    max_dist = 0.0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = _distance_point_to_segment(points[i], points[0], points[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        # Recursively simplify both halves.
        left  = douglas_peucker(points[:max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        # Merge — drop the duplicate at the junction.
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


# ---------------------------------------------------------------------------
# Corner detection
# ---------------------------------------------------------------------------

def detect_corners(
    simplified_boundary: list[tuple[float, float]],
    angle_threshold: float = DEFAULT_CORNER_ANGLE_THRESHOLD,
) -> list[tuple[float, float]]:
    """Detect corners in a simplified boundary polygon.

    A corner is a vertex where the direction change between
    consecutive segments exceeds angle_threshold degrees.

    Parameters
    ----------
    simplified_boundary: list of (x, y) points forming the polygon
    angle_threshold:     minimum direction change to count as a corner

    Returns list of corner (x, y) points.
    """
    n = len(simplified_boundary)
    if n < 3:
        return []

    corners = []

    for i in range(n):
        prev_pt = simplified_boundary[(i - 1) % n]
        curr_pt = simplified_boundary[i]
        next_pt = simplified_boundary[(i + 1) % n]

        angle_change = _angle_between_segments(prev_pt, curr_pt, next_pt)
        if angle_change >= angle_threshold:
            corners.append(curr_pt)

    return corners


# ---------------------------------------------------------------------------
# Trail processing pipeline
# ---------------------------------------------------------------------------

def process_boundary_trail(
    trail: list[tuple[float, float]],
    *,
    epsilon: float = DEFAULT_DP_EPSILON,
    corner_angle_threshold: float = DEFAULT_CORNER_ANGLE_THRESHOLD,
) -> dict[str, Any]:
    """Process a raw position trail into a boundary polygon and corners.

    Parameters
    ----------
    trail:                list of (vx, vy) vacuum coordinate points
    epsilon:              Douglas-Peucker simplification threshold
    corner_angle_threshold: minimum angle change for corner detection

    Returns a dict with:
      simplified_boundary:  list of [vx, vy] points (simplified polygon)
      corners:              list of [vx, vy] corner points
      point_count_raw:      int — original trail length
      point_count_simplified: int — simplified polygon length
      corner_count:         int
      epsilon:              float — epsilon used
      valid:                bool — False if trail was too short
    """
    raw_count = len(trail)

    if raw_count < MIN_TRAIL_POINTS:
        return {
            "simplified_boundary": [],
            "corners": [],
            "point_count_raw": raw_count,
            "point_count_simplified": 0,
            "corner_count": 0,
            "epsilon": epsilon,
            "valid": False,
            "error": f"Trail too short: {raw_count} points (minimum {MIN_TRAIL_POINTS})",
        }

    simplified = douglas_peucker(trail, epsilon)
    corners = detect_corners(simplified, corner_angle_threshold)

    return {
        "simplified_boundary": [[round(p[0], 4), round(p[1], 4)] for p in simplified],
        "corners": [[round(c[0], 4), round(c[1], 4)] for c in corners],
        "point_count_raw": raw_count,
        "point_count_simplified": len(simplified),
        "corner_count": len(corners),
        "epsilon": epsilon,
        "valid": True,
    }


# ---------------------------------------------------------------------------
# Point-in-polygon test
# ---------------------------------------------------------------------------

def point_in_polygon(
    point: tuple[float, float],
    polygon: list[list[float]],
) -> bool:
    """Return True if point is inside the polygon (ray-casting algorithm).

    Parameters
    ----------
    point:   (x, y) in vacuum coordinates
    polygon: list of [x, y] points (does not need to be closed)
    """
    px, py = point
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1

    for i in range(n):
        xi, yi = float(polygon[i][0]), float(polygon[i][1])
        xj, yj = float(polygon[j][0]), float(polygon[j][1])

        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


# ---------------------------------------------------------------------------
# Transition candidate scoring
# ---------------------------------------------------------------------------

def _polygon_area(polygon: list) -> float:
    """Return the signed area of a polygon via the shoelace formula."""
    n = len(polygon)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += float(polygon[i][0]) * float(polygon[j][1])
        area -= float(polygon[j][0]) * float(polygon[i][1])
    return abs(area) / 2.0


def _convex_hull_area(polygon: list) -> float:
    """Return the area of the convex hull of the polygon points.

    Uses Andrew's monotone chain (pure Python). Falls back to polygon area
    if fewer than 3 unique points survive deduplication.
    """
    pts = sorted(set((round(float(p[0]), 6), round(float(p[1]), 6)) for p in polygon))
    if len(pts) < 3:
        return _polygon_area(polygon)

    def _cross(o: tuple, a: tuple, b: tuple) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    return _polygon_area(hull) if len(hull) >= 3 else _polygon_area(polygon)


def score_transition_candidate(
    boundary: list[list[float]],
) -> tuple[float, bool]:
    """Score a room boundary polygon for likelihood of being a transition space.

    Combines three independent signals:

    convexity_ratio  — hull_area / polygon_area.  A perfect rectangle = 1.0.
                       An L-shape is typically 1.4–2.5+.  Catches concave rooms.

    aspect_ratio     — max(w, h) / min(w, h) of the bounding box.
                       Normal rooms < 3.  Corridors are typically 3.5–8+.

    vertex_count     — simplified polygon vertex count.  Normal rooms settle
                       at 4–6.  Complex or non-convex shapes push higher.

    Returns (score, is_candidate).

    score        — 0.0–1.0 continuous confidence (for display / ordering).
    is_candidate — True if ANY single signal clears its own threshold.
                   Intentionally uses OR so that a very strong single signal
                   (e.g. a clearly concave L-shape) surfaces without needing
                   corroboration from weaker signals.
    """
    if not boundary or len(boundary) < 4:
        return 0.0, False

    poly_area = _polygon_area(boundary)
    if poly_area < 1.0:
        return 0.0, False

    hull_area = _convex_hull_area(boundary)
    convexity_ratio = hull_area / poly_area if poly_area > 0 else 1.0

    xs = [float(p[0]) for p in boundary]
    ys = [float(p[1]) for p in boundary]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    aspect_ratio = max(w, h) / max(min(w, h), 0.001)

    vertex_count = len(boundary)

    # Per-signal normalised scores (0.0–1.0).
    convexity_score = min(max(convexity_ratio - 1.0, 0.0) / 1.0, 1.0)
    aspect_score    = min(max(aspect_ratio    - 1.5, 0.0) / 3.5, 1.0)
    vertex_score    = min(max(vertex_count    - 4,   0  ) / 8.0, 1.0)

    score = round(
        convexity_score * 0.50 +
        aspect_score    * 0.35 +
        vertex_score    * 0.15,
        3,
    )

    # Candidate if any single signal is unambiguously above its own threshold.
    is_candidate = (
        convexity_ratio >= 1.4 or   # clearly non-convex (L-shape, T-shape, etc.)
        aspect_ratio    >= 3.5 or   # corridor-shaped bounding box
        vertex_count    >= 8        # high polygon complexity
    )

    return score, is_candidate
