"""Perceptual tier — SHAPE similarity of vector figures, no PDF rasteriser needed.

WHY THIS EXISTS. The exact tier (dreame_diagram_fingerprint) matches byte-identical
path geometry. Measured on mop-maintenance pages it does NOT separate mechanisms:

    spin within      median 0.139
    spin x assembly  median 0.114
    spin x roller    median 0.126

Within-class overlap is indistinguishable from cross-class. Exact shingles find
DOCUMENT-TEMPLATE lineage (Aqua10 vs X40 whole-document was J=0.44 vs 0.003, which
is real) but not PROCEDURE identity. Chris's point stands: the question is whether
two figures are semantically the same drawing, not whether their bytes match.

WHY A RASTERISER IS NOT REQUIRED. An earlier note in this effort concluded the
handoff's Step 2 was impossible because the environment has no poppler/PyMuPDF/
ImageMagick. That was wrong. Those tools rasterise a PDF PAGE. The artwork here is
already vector line segments, so the segments can be drawn directly into a numpy
array. Self-rasterising the paths IS the edge map Step 2 asks for, and it skips the
decode-then-edge-detect stage entirely because line art has no fill to discard.

METHOD
  1. Recover line segments from the content stream (m/l pairs).
  2. Group segments into FIGURES by spatial connectivity (union-find over shared
     endpoints within a tolerance). A page holds several drawings; comparing whole
     pages would mix a mop diagram with a dock diagram and the page furniture.
  3. Normalise each figure to its own bounding box -> unit square. This is what
     makes the comparison semantic: the same drawing matches at any position, any
     page size, and any SCALE, which exact hashing cannot do.
  4. Render into a fixed NxN occupancy grid and compare by Hamming distance.

Aspect ratio is preserved (letterboxed) rather than stretched: stretching would
make a tall brush diagram match a wide dock diagram.
"""
from __future__ import annotations

import re
import numpy as np

NUM = re.compile(rb'^-?\d*\.?\d+$')


def _bezier(p0, p1, p2, p3, n=8):
    """Flatten a cubic Bezier into n line segments."""
    pts = [p0]
    for i in range(1, n + 1):
        t = i / n
        u = 1.0 - t
        x = (u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0])
        y = (u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1])
        pts.append((x, y))
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _mul(m, n):
    """Matrix product for PDF 2x3 affine matrices [a b c d e f]."""
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (a1*a2 + b1*c2, a1*b2 + b1*d2,
            c1*a2 + d1*c2, c1*b2 + d1*d2,
            e1*a2 + f1*c2 + e2, e1*b2 + f1*d2 + f2)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a*x + c*y + e, b*x + d*y + f)


def segments(data: bytes):
    """Line segments from the page content stream, in PAGE coordinates.

    ⚠ TWO OMISSIONS, EACH OF WHICH RENDERS THE PAGE BLANK-BUT-PLAUSIBLE.

    1. CURVES ARE MOST OF THE ARTWORK. Handling only m/l/re/h discards every
       Bezier, and on a figure page that is the drawing:
           l10s-pro-ultra p4:  c = 11,770   l = 2,443
       Rendering the line-only extraction produced a page of EMPTY RECTANGLES -
       illustration frames and rules survived, illustrations did not.

    2. `cm` MUST BE TRACKED. Each figure is drawn in its own local coordinate
       space and positioned by a transformation matrix; that page carries 4,046
       `cm` operators. Ignoring them stacks every figure on the origin, which
       renders as a dense blob in one corner and a page of empty frames
       everywhere else. It also destroys spatial grouping: connectivity merges
       all the overlapping art into one "composite", which is exactly the
       large-figure artefact that polluted the first similarity run.

    Both bugs are silent. They produce confident numbers from page furniture.
    """
    segs = []
    nums: list[float] = []
    cur = None
    start_pt = None
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    stack: list[tuple] = []

    def pt(x, y):
        return _apply(ctm, x, y)

    for tok in data.split():
        if NUM.match(tok):
            try:
                nums.append(float(tok))
            except ValueError:
                nums = []
            continue
        op = tok.decode('latin-1', 'replace')
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            if stack:
                ctm = stack.pop()
        elif op == 'cm' and len(nums) >= 6:
            ctm = _mul(tuple(nums[-6:]), ctm)
        elif op == 'm' and len(nums) >= 2:
            cur = pt(nums[-2], nums[-1])
            start_pt = cur
        elif op == 'l' and len(nums) >= 2 and cur is not None:
            nxt = pt(nums[-2], nums[-1])
            segs.append((cur, nxt))
            cur = nxt
        elif op == 'c' and len(nums) >= 6 and cur is not None:
            c1 = pt(nums[-6], nums[-5]); c2 = pt(nums[-4], nums[-3]); p3 = pt(nums[-2], nums[-1])
            segs.extend(_bezier(cur, c1, c2, p3))
            cur = p3
        elif op == 'v' and len(nums) >= 4 and cur is not None:
            c2 = pt(nums[-4], nums[-3]); p3 = pt(nums[-2], nums[-1])
            segs.extend(_bezier(cur, cur, c2, p3))
            cur = p3
        elif op == 'y' and len(nums) >= 4 and cur is not None:
            c1 = pt(nums[-4], nums[-3]); p3 = pt(nums[-2], nums[-1])
            segs.extend(_bezier(cur, c1, p3, p3))
            cur = p3
        elif op == 'h' and cur is not None and start_pt is not None:
            segs.append((cur, start_pt))
            cur = start_pt
        elif op == 're' and len(nums) >= 4:
            x, y, w, h = nums[-4:]
            corners = [pt(x, y), pt(x + w, y), pt(x + w, y + h), pt(x, y + h)]
            for i in range(4):
                segs.append((corners[i], corners[(i + 1) % 4]))
            cur = corners[0]; start_pt = cur
        nums = []
    return segs


def _find(par, i):
    while par[i] != i:
        par[i] = par[par[i]]
        i = par[i]
    return i


#: Pages in this corpus range from ~180 segments to hundreds of thousands (the X40
#: manual yields 691,771 path points in 40 pages). Connectivity grouping is superlinear
#: on the pathological ones and they are page furniture, not diagrams, so cap them.
MAX_SEGS = 60000


def figures(segs, tol=2.0, min_segs=12):
    """Group segments into connected drawings.

    A page carries several figures plus rules and boxes. Comparing whole pages mixes
    them, which is one reason the exact tier showed no separation.
    """
    n = len(segs)
    if not n or n > MAX_SEGS:
        return []
    par = list(range(n))
    # ONE REPRESENTATIVE PER CELL, not a member list. Scanning every member of nine
    # neighbouring cells is quadratic: 1.73 s on a single 3,000-segment page, which
    # put a three-document probe past two minutes. Union-find is transitive, so
    # linking to a cell's representative connects the whole cell.
    rep: dict[tuple, int] = {}
    q = max(tol, 1e-6)
    for i, (a, b) in enumerate(segs):
        for p_ in (a, b):
            kx, ky = round(p_[0] / q), round(p_[1] / q)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    j = rep.get((kx + dx, ky + dy))
                    if j is None:
                        continue
                    ri, rj = _find(par, i), _find(par, j)
                    if ri != rj:
                        par[ri] = rj
            rep.setdefault((kx, ky), i)

    groups: dict[int, list] = {}
    for i in range(n):
        groups.setdefault(_find(par, i), []).append(segs[i])
    return [g for g in groups.values() if len(g) >= min_segs]


def render(fig, N=48):
    """Normalise one figure to a unit square and draw it into an NxN occupancy grid.

    Aspect ratio is PRESERVED (letterboxed). Stretching to fill would let a tall
    brush drawing match a wide dock drawing, which is exactly the false positive
    Section 6 of the handoff warns about.
    """
    xs = [p[0] for s in fig for p in s]
    ys = [p[1] for s in fig for p in s]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    scale = max(w, h)
    if scale <= 0:
        return None
    ox = (scale - w) / 2.0
    oy = (scale - h) / 2.0
    grid = np.zeros((N, N), dtype=np.uint8)
    for (x0, y0), (x1, y1) in fig:
        ax = (x0 - minx + ox) / scale * (N - 1)
        ay = (y0 - miny + oy) / scale * (N - 1)
        bx = (x1 - minx + ox) / scale * (N - 1)
        by = (y1 - miny + oy) / scale * (N - 1)
        steps = int(max(abs(bx - ax), abs(by - ay))) + 1
        t = np.linspace(0.0, 1.0, max(steps, 2))
        xi = np.clip((ax + (bx - ax) * t).round().astype(int), 0, N - 1)
        yi = np.clip((ay + (by - ay) * t).round().astype(int), 0, N - 1)
        grid[yi, xi] = 1
    return grid


#: Popcount lookup for byte-wise Hamming. The obvious int-shift packing loop runs
#: 2304 shifts per figure and made a five-document probe exceed two minutes.
_POP = np.unpackbits(np.arange(256, dtype=np.uint8)[:, None], axis=1).sum(1).astype(np.uint16)


def bits(grid):
    """Pack the occupancy grid to bytes (np.packbits) for cheap Hamming."""
    return np.packbits(grid.flatten())


def hamming(a, b) -> int:
    return int(_POP[np.bitwise_xor(a, b)].sum())


def page_figures(data: bytes, N=48, min_segs=12):
    """(bitint, segment_count, area_fraction) for every figure on a page."""
    out = []
    for fig in figures(segments(data), min_segs=min_segs):
        g = render(fig, N=N)
        if g is None:
            continue
        out.append((bits(g), len(fig), float(g.mean())))
    return out
