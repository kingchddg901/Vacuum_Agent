"""Language-independent procedure fingerprint: the SHAPE of a maintenance table.

Chris's insight, and it is the way past the translation wall: "procedure is procedure.
It'll have a shape." A maintenance table's intervals are Arabic numerals plus a unit,
in every language the corpus carries. The M40 manual is Chinese and cannot be compared
to the X20+ by bigram overlap - but its table reads:

    污水箱   建议每次使用后清洁      =  after each use
    清水箱   每2周清洁1次           =  every 2 weeks
    边刷     每2周 / 3-6个月        =  every 2 weeks / 3-6 months
    滤网     每2周 / 3-6个月        =  every 2 weeks / 3-6 months
    拖布     /     1-3个月          =  1-3 months
    尘袋     /     约2.5个月        =  ~2.5 months

Same components, same intervals, different script. So the fingerprint is the MULTISET
OF INTERVALS the table declares, normalised to weeks.

WHAT THIS DELIBERATELY DOES NOT DO. It does not translate, and it does not try to
align component names across languages - that would need a lexicon per language and
would fail on the first term Dreame words differently. The interval multiset needs
neither. It is a weaker signal than a text diff, and it is available where a text diff
is not.

⚠ AND IT IS A SHAPE, NOT A PROOF. Two unrelated robots with conventional service
intervals will share "every 2 weeks" and "3-6 months" because those are the industry's
numbers, not this machine's. Judge it against the base rate of interval overlap across
UNRELATED pairs, never in isolation.
"""
import re
from fractions import Fraction

# "every 2 weeks", "3 to 6 months", "1-2 months", "every month"
EN = re.compile(
    r'(?:every|once every|approx\.?|about)?\s*'
    r'(\d+(?:\.\d+)?)\s*(?:to|-|~|–)?\s*(\d+(?:\.\d+)?)?\s*'
    r'(week|month|year)s?', re.I)
# "每2周", "3-6个月", "约2.5个月", "每个月"
CN = re.compile(r'(\d+(?:\.\d+)?)\s*(?:[-~到至])?\s*(\d+(?:\.\d+)?)?\s*(周|个月|年)')
CN_EVERY_MONTH = re.compile(r'每个月')
EN_EVERY_MONTH = re.compile(r'once every month|every month', re.I)

UNIT_WEEKS = {'week': 1, 'month': 4.345, 'year': 52.18,
              '周': 1, '个月': 4.345, '年': 52.18}


def intervals(text: str):
    """Every declared interval in the text, normalised to weeks.

    A range ("3 to 6 months") is kept as its MIDPOINT rather than split: the two
    endpoints are one editorial decision, and counting them separately would let a
    table with many ranges dominate the multiset.
    """
    out = []
    for rx in (EN, CN):
        for m in rx.finditer(text):
            lo, hi, unit = m.group(1), m.group(2), m.group(3)
            mult = UNIT_WEEKS.get(unit.lower() if unit.isascii() else unit)
            if mult is None:
                continue
            try:
                a = float(lo)
                b = float(hi) if hi else a
            except ValueError:
                continue
            if a <= 0 or b > 60:      # "60 months" is a warranty, not a service interval
                continue
            out.append(round(((a + b) / 2.0) * mult, 2))
    # bare "every month" / 每个月 carries no digit
    out += [4.35] * len(EN_EVERY_MONTH.findall(text))
    out += [4.35] * len(CN_EVERY_MONTH.findall(text))
    return out


def shape(text: str):
    """The interval multiset as a comparable signature."""
    vals = intervals(text)
    # bucket to tolerate 4.345 vs 4.35 and 8.69 vs 8.7
    return sorted(round(v, 1) for v in vals)


def compare(a: str, b: str):
    sa, sb = shape(a), shape(b)
    if not sa or not sb:
        return None
    from collections import Counter
    ca, cb = Counter(sa), Counter(sb)
    inter = sum((ca & cb).values())
    return {'a': sa, 'b': sb,
            'shared': inter,
            'pct_of_smaller': inter / min(len(sa), len(sb)),
            'jaccard': inter / (len(sa) + len(sb) - inter)}
