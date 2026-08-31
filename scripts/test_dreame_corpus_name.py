"""Bite test for the manual->model name matcher.

Every case here is a matcher that ALREADY SHIPPED and was wrong. The corpus notes
record four dead matchers plus the two this file caught being written; none of them
looked broken, because a name matcher that over-matches reports excellent coverage and
a name matcher that under-matches reports honest-looking gaps.

⚠ THE LAST TWO CASES ARE THE ABLATION. A matcher that answers uniformly -- credits
everything, or credits nothing -- passes any test suite made only of positive examples.
`test_matcher_answers_vary` fails if the matcher stops discriminating at all.

Run: python -m pytest scripts/test_dreame_corpus_name.py --no-cov
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dreame_corpus_name import build_matcher  # noqa: E402

NAMES = {
    "L40 Ultra", "L40 Ultra Gen 2", "E10", "E30 Pro", "E30 Pro Plus",
    "GoVac 205 Plus", "GoVac 200", "S30 Pro", "S30 Pro Ultra", "X50 Ultra",
    "X40 Ultra", "X40 Ultra Complete", "免洗10", "澄净 Pro", "S10", "S10+",
    "X60 Ultra", "X50",
}

CASES = [
    # (label, text, expected names)
    ("longest declared name wins over its own prefix",
     "the L40 Ultra Gen 2 robot", ["L40 Ultra Gen 2"]),
    ("bare-substring trap: E10 must not match inside shin-e10",
     "model shin-e10 hair styler", []),
    ("token-run trap: hyphens inside a name are separators",
     "e30-pro-PLUS user manual", ["E30 Pro Plus"]),
    ("multiword name containing digits",
     "GoVac 205 Plus User Manual", ["GoVac 205 Plus"]),
    ("S30 Pro is a prefix of nine other names",
     "S30 Pro Ultra specifications", ["S30 Pro Ultra"]),
    # `Complete` was measured as packaging-only: 5 of 5 pairs share a regulatory code,
    # so the Complete manual documents the base machine's maintenance.
    ("Complete inherits the base name (undeclared longer retail name)",
     "X60 Ultra Complete Robot Vacuum", ["X60 Ultra"]),
    ("a declared longer name still wins outright",
     "Applicable to X40 Ultra Complete.", ["X40 Ultra Complete"]),
    # `Master` is a real hardware tier (mains-plumbed): different machine.
    ("hardware-tier suffix rejects the base match",
     "the X50 Master robot", []),
    ("the base name alone still matches",
     "the X50 Ultra robot", ["X50 Ultra"]),
    ("a model glued to an r-code by a tight join is not a prose mention",
     "R2416F-X40_Ultra", []),
    # An ASCII-only normaliser reduced these to `10` and `pro`, matching 1396 and 433
    # of 1998 manuals -- 79% of the corpus read as robot vacuums.
    ("CJK name matches its own Chinese page",
     "本产品 免洗10 使用说明", ["免洗10"]),
    ("CJK name must not decay into an ASCII fragment",
     "Pro model, 10 minutes", []),
    ("`+` is part of the name, not punctuation",
     "S10+ specifications", ["S10+"]),
]


@pytest.mark.parametrize("label,text,expected", CASES, ids=[c[0] for c in CASES])
def test_matcher(label: str, text: str, expected: list[str]) -> None:
    find = build_matcher(NAMES)
    assert sorted(find(text)) == sorted(expected), label


def test_no_model_named_yields_nothing() -> None:
    assert build_matcher(NAMES)("hair dryer user manual") == []


def test_empty_input_yields_nothing() -> None:
    assert build_matcher(NAMES)("") == []


def test_matcher_answers_vary() -> None:
    """ABLATION. A probe that returns the same answer for every input is broken.

    This is the check that would have caught the CJK normalisation bug on the day it
    was written: it credited nearly every document, and every positive case above
    still passed.
    """
    find = build_matcher(NAMES)
    answers = {tuple(sorted(find(text))) for _, text, _ in CASES}
    assert len(answers) > 1, "matcher does not discriminate between inputs"
    # and it must not simply credit everything it sees
    assert find("hair dryer user manual") == []
