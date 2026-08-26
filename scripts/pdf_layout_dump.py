"""Dump a PDF page in VISUAL reading order.

Why this exists: ``pypdf.extract_text()`` emits content-stream order, which on the
Dreame manuals interleaves adjacent columns. A collapsed extract of the L10s Gen 2
"Main Brush" block arrives with used-water-tank sentences inside it, and that produced
a false "the dust bag differs" finding once, in a task whose whole output was
⚠ SUPERSEDED 2026-08-25: `pip install pypdfium2` puts a real rasteriser here, so a page
can simply be RENDERED and read. This module exists only because that was believed
impossible. Prefer rendering; keep this for text-layer PDFs where it is cheaper.

transcribed prose. There WAS no rasteriser in this environment — no poppler, no
PyMuPDF — so page images are not an option and this is how the manuals get read.

It reconstructs reading order from the text matrices: compose each run's text matrix
with the CTM to get device coordinates, cluster by *y* into rows, sort each row by *x*,
and mark wide horizontal gaps with ``|`` so column boundaries stay visible. The leading
number on each line is the *y* coordinate, which is what lets a three-column care page
be untangled by eye.

    python scripts/pdf_layout_dump.py MANUAL.pdf 22-30

Used for authoring adapters/dreame/dreame_upkeep_guides.py. Not imported by the
integration and not part of any gate.
"""
import sys
from collections import defaultdict
from pypdf import PdfReader

def dump(path, pageno, y_tol=3.0, col_gap=None):
    page = PdfReader(path).pages[pageno - 1]
    items = []

    def visit(text, cm, tm, font_dict, font_size):
        if not text or not text.strip():
            return
        # tm is the text matrix; cm the CTM. Compose to get device coords.
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        items.append((round(y, 1), round(x, 1), text, font_size))

    page.extract_text(visitor_text=visit)
    if not items:
        return "(no positioned text)"

    rows = defaultdict(list)
    for y, x, t, fs in items:
        key = next((k for k in rows if abs(k - y) <= y_tol), y)
        rows[key].append((x, t, fs))

    out = []
    width = float(page.mediabox.width)
    for y in sorted(rows, reverse=True):
        cells = sorted(rows[y])
        line, prev_x, prev_len = [], None, 0
        for x, t, fs in cells:
            if prev_x is not None and x - prev_x > (col_gap or width * 0.06):
                line.append("   |   ")
            line.append(t)
            prev_x = x
        s = "".join(line)
        s = " ".join(s.split())
        if s:
            out.append(f"{y:7.1f}  {s}")
    return "\n".join(out)

if __name__ == "__main__":
    path = sys.argv[1]
    for spec in sys.argv[2:]:
        if "-" in spec:
            a, b = spec.split("-"); rng = range(int(a), int(b) + 1)
        else:
            rng = [int(spec)]
        for p in rng:
            print(f"\n{'='*74}\n=== PAGE {p} ===\n{'='*74}")
            print(dump(path, p))
