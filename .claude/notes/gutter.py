"""Generic N-column reading order by whitespace gutters. No hard-coded midline."""
import re


def gutters(words, width, min_gap_frac=0.012, bin_pt=2.0):
    if not words:
        return []
    nb = max(1, int(width / bin_pt))
    occ = [0] * nb
    for w in words:
        a = max(0, int(w[0] / bin_pt))
        b = min(nb - 1, int(w[2] / bin_pt))
        for i in range(a, b + 1):
            occ[i] = 1
    runs, i = [], 0
    while i < nb:
        if occ[i]:
            i += 1
            continue
        j = i
        while j < nb and not occ[j]:
            j += 1
        runs.append((i * bin_pt, j * bin_pt))
        i = j
    lo = min(w[0] for w in words)
    hi = max(w[2] for w in words)
    need = width * min_gap_frac
    return [(a, b) for a, b in runs
            if b - a >= need and a > lo + 1 and b < hi - 1]


def columns(words, width):
    g = gutters(words, width)
    if not g:
        return [words]
    cuts = [(a + b) / 2.0 for a, b in g]
    cols = [[] for _ in range(len(cuts) + 1)]
    for w in words:
        c = (w[0] + w[2]) / 2.0
        k = 0
        while k < len(cuts) and c > cuts[k]:
            k += 1
        cols[k].append(w)
    return [c for c in cols if c]


def col_text(page, row=3.0):
    words = page.get_text("words")
    cols = columns(words, page.rect.width)
    out = []
    for c in cols:
        ws = sorted(c, key=lambda w: (round(w[1] / row), w[0]))
        out.append(" ".join(w[4] for w in ws))
    return "\n".join(out), len(cols)


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"\s+", " ", s or "").lower()).strip()
