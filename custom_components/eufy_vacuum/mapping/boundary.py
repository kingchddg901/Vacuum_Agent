"""Point-in-polygon test — the one geometry helper the live map layer needs.

The rest of this module (Douglas-Peucker simplification, corner detection,
polygon-area / convex-hull utilities, and transition scoring — the dead
room-boundary derivation) was removed with the mapping split. Only
``point_in_polygon`` survives; it is used live by ``map_source.zone_membership``.
"""

from __future__ import annotations


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
