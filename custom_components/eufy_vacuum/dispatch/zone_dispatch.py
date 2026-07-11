"""Convert normalized live-map zone rectangles to device (vacuum-mm) coordinates.

Some brands de-normalize zone rects on their side (Eufy's fork ``zone_clean`` takes
0..1 fractions of the live image), so the integration ships them verbatim. Others —
Roborock's ``app_zoned_clean`` — want **world/device millimetres**
(``[[x0,y0,x1,y1,repeat], ...]``), so the integration must convert before dispatch.

This module does that conversion WITHOUT depending on the map-parser internals (or
numpy): the affine that maps the normalized 0..1 image frame to the device mm frame is
recovered by least squares from known ``(normalized, mm)`` correspondences — the live
map's own room-bbox corners, which we already have in BOTH frames — and is then
round-trip VALIDATED against those same points. If the fit can't reproduce them within a
tight tolerance (non-affine geometry, clamped/garbage points, too few rooms), the
converter returns ``None`` and the caller MUST refuse to dispatch rather than risk
cleaning the wrong area. "Refuse rather than mis-dispatch" is the safety contract.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def _det3(m: Sequence[Sequence[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _solve3_two(a: list[list[float]], bx: list[float], by: list[float]):
    """Solve two 3x3 systems sharing matrix ``a`` for right-hand sides ``bx`` and
    ``by`` (Cramer's rule). Returns ``(sol_x, sol_y)`` 3-tuples, or ``None`` if
    ``a`` is singular (degenerate / collinear correspondences)."""
    d = _det3(a)
    if abs(d) < 1e-9:
        return None

    def _col(mat, col, rhs):
        return [[rhs[r] if c == col else mat[r][c] for c in range(3)] for r in range(3)]

    sol_x = tuple(_det3(_col(a, c, bx)) / d for c in range(3))
    sol_y = tuple(_det3(_col(a, c, by)) / d for c in range(3))
    return sol_x, sol_y


def fit_normalized_to_mm(correspondences: Iterable[Sequence[float]]):
    """Least-squares affine ``(nx, ny) -> (mmx, mmy)`` from ``(nx, ny, mmx, mmy)``
    correspondences. Returns ``(ax, bx, cx, ay, by, cy)`` where
    ``mmx = ax*nx + bx*ny + cx`` and ``mmy = ay*nx + by*ny + cy`` — or ``None`` when
    there are fewer than 3 usable points or they are collinear/degenerate."""
    pts = []
    for c in correspondences or []:
        if c is None or len(c) != 4:
            continue
        try:
            pts.append((float(c[0]), float(c[1]), float(c[2]), float(c[3])))
        except (TypeError, ValueError):
            continue
    if len(pts) < 3:
        return None
    # Normal equations (M^T M) k = M^T r, with each row [nx, ny, 1].
    ata = [[0.0] * 3 for _ in range(3)]
    atx = [0.0, 0.0, 0.0]
    aty = [0.0, 0.0, 0.0]
    for nx, ny, mx, my in pts:
        row = (nx, ny, 1.0)
        for i in range(3):
            for j in range(3):
                ata[i][j] += row[i] * row[j]
            atx[i] += row[i] * mx
            aty[i] += row[i] * my
    sol = _solve3_two(ata, atx, aty)
    if sol is None:
        return None
    (ax, bx, cx), (ay, by, cy) = sol
    return (ax, bx, cx, ay, by, cy)


def _apply(coeffs, nx: float, ny: float):
    ax, bx, cx, ay, by, cy = coeffs
    return (ax * nx + bx * ny + cx, ay * nx + by * ny + cy)


def max_residual_mm(coeffs, correspondences: Iterable[Sequence[float]]) -> float:
    """Largest per-point error (mm) of the fitted affine over the correspondences —
    the round-trip check. A clean affine fit yields ~0; a large value means the
    geometry isn't the affine we assumed, so the caller should refuse."""
    worst = 0.0
    for c in correspondences or []:
        if c is None or len(c) != 4:
            continue
        try:
            nx, ny, mx, my = float(c[0]), float(c[1]), float(c[2]), float(c[3])
        except (TypeError, ValueError):
            continue
        px, py = _apply(coeffs, nx, ny)
        worst = max(worst, abs(px - mx), abs(py - my))
    return worst


def normalized_rects_to_mm(
    correspondences: Iterable[Sequence[float]],
    rects: Iterable[Sequence[float]],
    *,
    validate_tol_mm: float = 50.0,
):
    """Convert normalized ``[x0, y0, x1, y1]`` rects (0..1, top-left origin) to device-mm
    ``[x0, y0, x1, y1]`` (min/max-ordered) via the affine fit from ``correspondences``.

    Returns the mm rects, or ``None`` if the affine can't be validated within
    ``validate_tol_mm`` (caller must then REFUSE to dispatch). 50 mm (~2 in) is far under a
    room; an exact affine fits to ~0, so a failure means the geometry isn't what we
    assumed (clamped points / unexpected projection) — exactly when NOT to send coords.
    """
    coeffs = fit_normalized_to_mm(correspondences)
    if coeffs is None:
        return None
    if max_residual_mm(coeffs, correspondences) > validate_tol_mm:
        return None
    out: list[list[float]] = []
    for r in rects or []:
        if not isinstance(r, (list, tuple)) or len(r) != 4:
            return None
        try:
            x0, y0, x1, y1 = (float(v) for v in r)
        except (TypeError, ValueError):
            return None
        mx0, my0 = _apply(coeffs, x0, y0)
        mx1, my1 = _apply(coeffs, x1, y1)
        out.append([min(mx0, mx1), min(my0, my1), max(mx0, mx1), max(my0, my1)])
    return out
