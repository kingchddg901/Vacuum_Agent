"""Procedure shape = the ACTION SEQUENCE. Language-independent, step-granularity-proof.

⚠ THIS REPLACES procedure_shape.py, WHICH MEASURED THE WRONG THING. That module read
the maintenance FREQUENCY table - how often a part is serviced. Chris: "I don't care
about the interval. I care about the steps." Intervals are also industry conventions,
so unrelated manuals scored a median 0.667 Jaccard on them; the signal was weak AND
about the wrong property.

WHY ACTIONS AND NOT STEP COUNTS. The same procedure is chunked differently by
different writers. The dust-bag replacement is FOUR numbered steps in the M40 and
TWO in the X20+, describing identical work:

    M40  1. pull cover, remove bag, discard   2. wipe filter    3. install new bag   4. refit cover
    X20+ 1. pull cover, remove bag, discard, wipe filter        2. install new bag, refit cover

Counting steps says 4 vs 2 and calls them different. Counting ACTIONS says
pull/remove/discard/wipe/install/refit both times and calls them the same.

THE LEXICON IS THE WHOLE METHOD, AND IT IS DELIBERATELY SMALL. Only actions that are
physical, unambiguous, and appear in maintenance instructions. Adding "check" or
"ensure" would fire on every safety note and flatten the signal. Chinese terms are
paired to the same canonical action, which is what carries the comparison across the
translation wall.
"""
import re

#: canonical action -> (english patterns, chinese patterns)
ACTIONS = {
    'open':      (r'\bopen\b',                        r'打开|掀开'),
    'remove':    (r'\bremove|take out|detach|lift out\b', r'取出|取下|拆下|移除'),
    'press':     (r'\bpress|push\b',                  r'按住|按压|按下'),
    'pull':      (r'\bpull\b',                        r'拉开|拉出|拉住'),
    'discard':   (r'\bdiscard|throw away|dispose\b',  r'丢弃|扔掉'),
    'empty':     (r'\bempty|pour out\b',              r'倒出|清空'),
    'rinse':     (r'\brinse|wash\b',                  r'冲洗|清洗'),
    'wipe':      (r'\bwipe\b',                        r'擦拭|擦干'),
    'tap':       (r'\btap\b',                         r'拍打|轻敲'),
    'dry':       (r'\bdry\b',                         r'晾干|烘干|风干'),
    'install':   (r'\binstall|put back|reinstall|refit|insert\b', r'装回|装入|安装|插入'),
    'unscrew':   (r'\bunscrew|screw\b',               r'拧下|拧松|旋下'),
    'cut':       (r'\bcut\b',                         r'剪断|割'),
    'soak':      (r'\bsoak\b',                        r'浸泡'),
    'replace':   (r'\breplace\b',                     r'更换'),
}

_COMPILED = [(name, re.compile(en, re.I), re.compile(cn))
             for name, (en, cn) in ACTIONS.items()]


def action_sequence(text: str):
    """Canonical actions in the order they appear in the text.

    Order matters: 'remove then rinse then dry then install' is a different procedure
    from 'rinse then remove'. Position is recorded so the sequence, not just the set,
    can be compared.
    """
    hits = []
    for name, en, cn in _COMPILED:
        for m in en.finditer(text):
            hits.append((m.start(), name))
        for m in cn.finditer(text):
            hits.append((m.start(), name))
    hits.sort()
    # collapse immediate repeats: "rinse ... rinse" in one sentence is one action
    out = []
    for _, name in hits:
        if not out or out[-1] != name:
            out.append(name)
    return out


def bigrams(seq):
    """Adjacent action pairs - the unit that survives re-chunking into more or fewer
    numbered steps, because the ORDER of work is preserved even when the step
    boundaries move."""
    return {(seq[i], seq[i + 1]) for i in range(len(seq) - 1)}


def compare(a_text: str, b_text: str):
    sa, sb = action_sequence(a_text), action_sequence(b_text)
    if len(sa) < 3 or len(sb) < 3:
        return None
    from collections import Counter
    ca, cb = Counter(sa), Counter(sb)
    multi_inter = sum((ca & cb).values())
    ba, bb = bigrams(sa), bigrams(sb)
    bi = len(ba & bb)
    return {
        'seq_a': sa, 'seq_b': sb,
        'set_jaccard': len(set(sa) & set(sb)) / len(set(sa) | set(sb)),
        'multiset_pct': multi_inter / min(len(sa), len(sb)),
        'bigram_jaccard': bi / len(ba | bb) if (ba | bb) else 0.0,
        'bigram_pct': bi / min(len(ba), len(bb)) if (ba and bb) else 0.0,
    }
