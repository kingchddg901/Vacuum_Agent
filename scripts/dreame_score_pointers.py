"""Second opinion on every artwork pointer: does the PROCEDURE agree?

232 document pairs were flagged by shared declared artwork. Artwork finds production
lineage; it does not find procedure identity. Both prior checks showed the two coming
apart in opposite directions:

    S70 Pro Roller x S70 Ultra Roller   artwork 4  (weakest)  text  100%
    M40 x X20+                          artwork 35 (strongest) shape 21st pctile

So each pointer gets scored on two further axes and nothing is collapsed into one
number.

  TEXT SHAPE   bigram overlap of the English maintenance block. Unavailable when
               either document is non-English, which is why the M40 needed the next
               axis.
  PROC SHAPE   the multiset of declared service intervals normalised to weeks.
               Language-independent - the numerals survive translation.

⚠ PROC SHAPE MUST BE READ AS A PERCENTILE, NEVER AS A RAW SCORE. Service intervals
are industry conventions, so unrelated manuals already agree heavily: measured over
4,584 unrelated pairs the median Jaccard is 0.667 and the p90 is 0.875. A raw 0.8
looks strong and is below average. Calibration used here, from that run:

    SAME machine  median 1.000
    DIFF machine  median 0.667   p90 0.875   p99 1.000
"""
import json, os, re, sys, statistics, itertools, random

sys.path.insert(0, os.path.dirname(__file__))
from procedure_shape import shape, compare as shape_compare      # noqa: E402
from compare_maint_text import COMP, VERB, TROUBLE, similarity   # noqa: E402

D = 'C:/Users/CKing/Documents/durable/dreame-port-fixture/derived'
FF = chr(12)
man = {x['name']: x for x in json.load(open(D + '/corpus-manifest.json', encoding='utf-8'))}
ct = {d['file']: d for d in json.load(open(D + '/doc_model_crosstable.json', encoding='utf-8'))}
rows = json.load(open(D + '/clone_pointers.json', encoding='utf-8'))

MAINT = re.compile(r'维护与保养|部件保养|清洁频率|更换频率|Routine Maintenance|'
                   r'Replacement\s+Period|Maintenance\s+Frequency', re.I)

_cache = {}


def pages_of(nm):
    if nm in _cache:
        return _cache[nm]
    x = man.get(nm) or {}
    sha = (x.get('sha256') or '')[:12]
    p = os.path.join(D, 'text', sha + '.txt')
    v = open(p, encoding='utf-8', errors='replace').read().split(FF) if os.path.exists(p) else None
    _cache[nm] = v
    return v


def table_text(nm):
    pg = pages_of(nm)
    if not pg:
        return None
    hits = [s for s in pg if MAINT.search(s)]
    return ' '.join(hits[:3]) if hits else None


def best_block(nm, k=3):
    """Top-k pages by maintenance density - NOT the first k that qualify.

    Picking the first qualifying pages returned 284-709 char fragments on one manual
    and skipped its real 2,952 char maintenance page, which depressed a comparison to
    0.208 that is really 0.317.
    """
    pg = pages_of(nm)
    if not pg:
        return None
    sc = []
    for i, s in enumerate(pg):
        if TROUBLE.search(s):
            continue
        comps = len(set(m.lower() for m in COMP.findall(s)))
        verbs = len(VERB.findall(s))
        if comps >= 2 and verbs >= 3:
            sc.append((comps * 3 + verbs, i, s))
    if not sc:
        return None
    sc.sort(reverse=True)
    return ' '.join(s for _, _, s in sorted(sc[:k], key=lambda t: t[1]))


# --- rebuild the unrelated-pair distribution so percentiles are honest ------------
random.seed(7)
pool = [f for f in ct if ct[f].get('base_codes')]
random.shuffle(pool)
tabs = {}
for f in pool[:140]:
    t = table_text(f)
    if t and len(shape(t)) >= 4:
        tabs[f] = t
base = []
for a, b in itertools.combinations(list(tabs), 2):
    if set(ct[a]['base_codes']) & set(ct[b]['base_codes']):
        continue
    c = shape_compare(tabs[a], tabs[b])
    if c:
        base.append(c['jaccard'])
base.sort()
print(f'calibration: {len(base)} unrelated pairs, median={statistics.median(base):.3f}, '
      f'p90={base[int(.9*len(base))]:.3f}', flush=True)


def pctile(v):
    lo = sum(1 for x in base if x < v)
    return 100.0 * lo / len(base)


out = []
for n, r in enumerate(rows, 1):
    a, b = r['a'], r['b']
    ta, tb = table_text(a), table_text(b)
    sc = shape_compare(ta, tb) if (ta and tb) else None
    ba, bb = best_block(a), best_block(b)
    tx = similarity(ba, bb) if (ba and bb) else None
    out.append({**r,
                'shape_j': round(sc['jaccard'], 3) if sc else None,
                'shape_pctile': round(pctile(sc['jaccard']), 1) if sc else None,
                'text_pct_smaller': round(tx['pct_of_smaller'], 3) if tx else None,
                'text_j': round(tx['jaccard'], 3) if tx else None})
    if n % 50 == 0:
        print(f'  {n}/{len(rows)}', flush=True)

json.dump(out, open(D + '/clone_pointers_scored.json', 'w', encoding='utf-8'),
          indent=1, ensure_ascii=False)

have_shape = [r for r in out if r['shape_pctile'] is not None]
have_text = [r for r in out if r['text_pct_smaller'] is not None]
print(f'\nscored {len(out)} pointers: shape on {len(have_shape)}, text on {len(have_text)}')
strong = [r for r in have_shape if r['shape_pctile'] >= 90]
weak = [r for r in have_shape if r['shape_pctile'] < 50]
print(f'  procedure CORROBORATES (>=p90) : {len(strong)}')
print(f'  procedure CONTRADICTS  (<p50)  : {len(weak)}')
print(f'\nTOP CORROBORATED (artwork + procedure both agree):')
for r in sorted(strong, key=lambda r: -r['n'])[:18]:
    na = str(r['names_a'] or ct.get(r['a'], {}).get('names_resolved') or '')[:26]
    nb = str(r['names_b'] or ct.get(r['b'], {}).get('names_resolved') or '')[:26]
    print(f"  art={r['n']:3d} shape_p={r['shape_pctile']:5.1f} text={r['text_pct_smaller']}  "
          f"{na:28s} <-> {nb}")
    print(f"        {r['a'][:44]:46s} {r['b'][:44]}")
