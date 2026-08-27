"""Diagram fingerprinting for the Dreame manual corpus — Step 1, exact tier.

Chris's premise (via the diagram-comparison handoff): if two manuals with different
names contain the same component drawings, that is evidence they document the same
procedure. This module extracts the drawings so that claim can be tested.

⚠ FOUR THINGS ABOUT THIS CORPUS THAT THE OBVIOUS IMPLEMENTATION GETS WRONG.
Each was established by measurement, and each produced a confident, uniform, WRONG
answer first. A uniform answer here is broken, not informative.

1. THERE ARE NO RASTER IMAGES. The handoff's asset class 1 ("embedded raster
   images ... SHA-256 of the raw stream") yields almost nothing: a 220-page Aqua10
   manual contains exactly ONE /Image in the entire file. Hashing image XObjects
   returns zero across whole documents. That is correct, not a bug.

2. FORM XOBJECTS ARE BACKGROUND BOXES, NOT ARTWORK. The same manual holds 26
   distinct /Form XObjects, and the ones inspected are a single filled rectangle
   (153 bytes, one `re` + `f`). An early probe hashing only Form streams reported
   42% overlap between the Track and Roller manuals. That number was measuring
   background boxes. It is not illustration lineage and must never be reported as
   such.

3. THE ARTWORK IS INLINE VECTOR PATHS, ONE SEGMENT PER q/Q BLOCK. Page 12 of the
   Track manual carries 174 moveto / 173 lineto / 172 stroke operators inside 177
   balanced q/Q pairs — i.e. each graphics-state block is a SINGLE LINE SEGMENT,
   not a figure. Treating q/Q as figure granularity and requiring >=4 points per
   asset rejects every block in the corpus and reports zero assets everywhere.

4. ``page.get_contents()`` RETURNS None ON THIS CORPUS. It reports no content for
   pages that demonstrably carry a 16.8 KB stream; ``page["/Contents"].get_object()
   .get_data()`` returns it correctly. Every zero in the chain above ultimately
   traced back to this one accessor. Always use ``contents()`` below.

WHY SHINGLES. Because the unit of reuse is a figure but the unit of storage is a
2-point segment, the fingerprint is a run of k consecutive path points normalised to
the run's OWN first point. That is translation-invariant, so the same drawing matches
wherever it is placed — essential on a corpus whose whole premise is that art is
re-laid-out across editions and page sizes. Rotation and scale are deliberately NOT
normalised: a scaled re-export is a perceptual-tier concern and this tier stays exact.

MEASURED SEPARATION (first 40 content pages, k=8, quant=1.0):

    track  x roller     J=0.439    track  x x40   J=0.003
    track  x protrack   J=0.551    roller x x40   J=0.003
    roller x protrack   J=0.442    protrack x x40 J=0.003

Two orders of magnitude between same-platform and different-platform. The ~236
shingles that every pair shares regardless are the template mass (safety pictograms,
charging illustration) that document-frequency weighting is there to remove.

⚠ JACCARD IS SIZE-SENSITIVE HERE. The X40 manual yields 691,771 path points in 40
pages against the Aqua10's 4,768 — a 145x asymmetry. Report "% of smaller set"
alongside Jaccard, or a large document will look dissimilar to everything.
"""

from __future__ import annotations

import hashlib
import re

NUM = re.compile(rb'^-?\d*\.?\d+$')
#: Path CONSTRUCTION operators only. Colour, text and graphics-state operators are
#: excluded on purpose: a recolour must not change an exact-tier hash.
PATH_OPS = {'m', 'l', 'c', 'v', 'y', 're', 'h'}


def contents(page) -> bytes:
    """Raw content-stream bytes for a page.

    ⚠ Do NOT substitute ``page.get_contents()``. On this corpus it returns None for
    pages that carry a 16.8 KB stream, which silently zeroes every downstream count.
    """
    try:
        obj = page['/Contents'].get_object()
    except Exception:
        return b''
    if hasattr(obj, 'get_data'):
        try:
            return obj.get_data()
        except Exception:
            return b''
    try:  # an array of streams
        return b' '.join(x.get_object().get_data() for x in obj)
    except Exception:
        return b''


def page_points(data: bytes):
    """Ordered path coordinates on a page, in PAGE coordinates.

    ⚠ DELEGATES to dreame_figure_shape.segments(). The original implementation here
    read m/l/re/h directly and did neither curve flattening nor `cm` tracking, so it
    saw ~17% of the geometry (page furniture) with every figure stacked on the origin.
    Every similarity number produced before 2026-08-27 came from that. Do not
    reintroduce a local path parser; there must be exactly one.
    """
    from dreame_figure_shape import segments
    segs = segments(data)
    pts = []
    last = None
    for a, b in segs:
        if a != last:
            pts.append(a)
        pts.append(b)
        last = b
    return pts


def shingles(pts, k: int = 8, quant: float = 1.0) -> set[str]:
    """Translation-normalised runs of k consecutive points -> truncated sha256."""
    out: set[str] = set()
    for i in range(0, len(pts) - k + 1):
        run = pts[i:i + k]
        ox, oy = run[0]
        ser = ';'.join(f'{round((x - ox) / quant)},{round((y - oy) / quant)}'
                       for x, y in run)
        # a run that never leaves its origin is a degenerate repeat, not a drawing
        if set(ser.split(';')) == {'0,0'}:
            continue
        out.add(hashlib.sha256(ser.encode()).hexdigest()[:20])
    return out


def doc_shingles(path: str, page_limit: int | None = None, k: int = 8,
                 quant: float = 1.0):
    """Distinct shingles for one document, deduped WITHIN the document.

    Within-document dedupe is required by the spec and by the corpus: a 34-language
    manual repeats the same art once per language, and without it a single drawing
    would contribute 34 times to corpus-level document-frequency counts.
    """
    from pypdf import PdfReader
    reader = PdfReader(path)
    found: set[str] = set()
    n_points = 0
    n_pages = 0
    for i in range(len(reader.pages)):
        if page_limit and i >= page_limit:
            break
        data = contents(reader.pages[i])
        if not data:
            continue
        n_pages += 1
        pts = page_points(data)
        n_points += len(pts)
        found |= shingles(pts, k=k, quant=quant)
    return found, n_points, n_pages


def compare(a: set[str], b: set[str]) -> dict:
    """Jaccard AND percent-of-smaller. See the size-sensitivity warning above."""
    inter = len(a & b)
    union = len(a | b) or 1
    smaller = min(len(a), len(b)) or 1
    return {'shared': inter, 'jaccard': inter / union, 'pct_of_smaller': inter / smaller}
