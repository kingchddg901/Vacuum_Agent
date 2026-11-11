"""The annotation ratchet — a declared tuple return must match what the function returns.

WHY THIS EXISTS, AND WHY IT IS A GATE RATHER THAN A ONE-OFF SWEEP. Nothing in this repo
type-checks: there is no mypy/pyright step in `.github/workflows/` and no
`.pre-commit-config.yaml`. A return annotation is therefore prose that happens to be
parsed — it can drift arbitrarily far from the code and no gate, test or runtime ever
notices. Found 2026-11-11 while an agent was reading `_split_suspicious_component` for an
unrelated reason: it declared a 2-tuple, every one of its eight `return` statements
returned a 3-tuple, and its DOCSTRING already said three.

That shape is the tell. The docstring was updated when the third element was added and the
annotation was not, so the two sat contradicting each other in the same function header
while a type checker reading the annotation would reject the sole, correct call site.

A sweep of the package then found a SECOND, in an unrelated subsystem:
`__init__.py::_prepare_static_dirs` declared `tuple[str, str, str, str]` and returned five
directories, its call site correctly unpacking all five. Two independent occurrences is
what turned "fix it" into "ratchet it" — one is a slip, two is a class of defect with
nothing watching for it.

WHAT IT CHECKS, AND WHAT IT DELIBERATELY DOES NOT. Only the ARITY of a fixed-length tuple
annotation against the arity of each returned tuple literal. That is the half establishable
from the source alone, with no inference and so no false positives. It does NOT check
element types: `list[Any]` against `list[dict[str, Any]]` needs real inference, and a
ratchet that guesses is worse than none.

It is therefore blind to several real defects, which is said here rather than implied away:
  - a wrong ELEMENT type at the right arity;
  - a function returning a tuple-valued NAME (`return result`) instead of a literal, which
    carries no arity at the return site;
  - `tuple[X, ...]`, a variadic, excluded by construction.

NAMING THE INPUT THAT MAKES IT RED, because a claim with no failure mode is worse than
silence: revert either fix — restore `-> tuple[list[Any], str | None]` on
`_split_suspicious_component`, or `-> tuple[str, str, str, str]` on `_prepare_static_dirs`
— and [AR-1] fails naming that function, the arity it declares and the arity it returns.
Measured both ways.

ON ADDING A TYPE CHECKER. This gate is NOT a step towards one. The repo has deliberately
not got one, and that is the owner's decision rather than a side effect of a bug fix.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "custom_components" / "eufy_vacuum"


def _declared_tuple_arity(node: ast.expr) -> int | None:
    """The arity of a FIXED-length `tuple[...]` annotation, else None.

    `tuple[X, ...]` is variadic and carries no arity, so it is excluded rather than
    counted as 2 — which is what a naive `len(elts)` would do, and it would make every
    variadic in the package a false positive.
    """
    if not isinstance(node, ast.Subscript):
        return None
    base = node.value
    if not (isinstance(base, ast.Name) and base.id == "tuple"):
        return None
    sl = node.slice
    if not isinstance(sl, ast.Tuple):
        return 1
    if any(isinstance(e, ast.Constant) and e.value is Ellipsis for e in sl.elts):
        return None
    return len(sl.elts)


def _package_sources() -> list[Path]:
    """Every .py under the package, read from the DIRECTORY rather than a manifest.

    Walking the tree agrees with the shipped package by construction and sees a file added
    since the last restart; a checked-in module list would not. Nothing here shells out to
    git — the pinned test container refuses that with `dubious ownership`.
    """
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)


def _arity_mismatches() -> list[tuple[str, str, int, int, list[int]]]:
    rows: list[tuple[str, str, int, int, list[int]]] = []
    for path in _package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if fn.returns is None:
                continue
            declared = _declared_tuple_arity(fn.returns)
            if declared is None:
                continue
            returned = {
                len(r.value.elts)
                for r in ast.walk(fn)
                if isinstance(r, ast.Return) and isinstance(r.value, ast.Tuple)
            }
            if returned and returned != {declared}:
                rows.append((
                    path.relative_to(REPO).as_posix(), fn.name, fn.lineno,
                    declared, sorted(returned),
                ))
    return rows


def test_ar1_a_declared_tuple_return_matches_the_arity_returned():
    """[AR-1] No function declares one tuple arity and returns another.

    RED when either 2026-11-11 fix is reverted, and the message names the function, the
    arity it claims and the arity it actually returns — so what gets fixed is the
    annotation, never the assertion.
    """
    rows = _arity_mismatches()
    assert not rows, "\n".join(
        [
            "a declared tuple return disagrees with what the function returns "
            "(nothing in this repo type-checks, so no other gate can see this):"
        ]
        + [
            "  %s::%s (line %d) declares arity %d, returns %s"
            % (path, name, line, declared, returned)
            for path, name, line, declared, returned in rows
        ]
    )


def test_ar2_the_check_can_actually_see_a_mismatch():
    """[AR-2] The detector fires on a KNOWN-BAD input, so [AR-1] passing means something.

    [AR-1] asserts an empty list. An empty list is also what a broken walker returns — a
    bad glob, a renamed package, an exception swallowed somewhere — and it reads
    identically to a clean tree. This injects the exact defect that was found and confirms
    the analysis reports it, which is the only thing separating "nothing is wrong" from
    "nothing was looked at".

    It analyses a source STRING, so it never writes to the tree.
    """
    source = (
        "from typing import Any\n"
        "def f() -> tuple[list[Any], str | None]:\n"
        "    return [], 'a', [{}]\n"
    )
    fn = ast.parse(source).body[1]
    assert isinstance(fn, ast.FunctionDef)
    assert _declared_tuple_arity(fn.returns) == 2
    returned = {
        len(r.value.elts)
        for r in ast.walk(fn)
        if isinstance(r, ast.Return) and isinstance(r.value, ast.Tuple)
    }
    assert returned == {3}, returned


@pytest.mark.parametrize(
    "annotation, expected",
    [
        ("tuple[int, str]", 2),
        ("tuple[list[Any], str | None, list[dict[str, Any]]]", 3),
        ("tuple[str, str, str, str, str]", 5),
        ("tuple[int]", 1),
        ("tuple[int, ...]", None),          # variadic: no arity to check
        ("list[int]", None),                # not a tuple at all
        ("int | None", None),
        ("dict[str, Any]", None),
    ],
)
def test_ar3_only_fixed_arity_tuples_are_counted(annotation, expected):
    """[AR-3] The variadic and non-tuple cases are EXCLUDED, not miscounted.

    `tuple[int, ...]` is the one that matters: read naively it has two subscript elements,
    so a `len(elts)` implementation would call every variadic in the package an arity-2
    annotation and this gate would be a wall of false positives — the failure mode that
    gets a gate deleted rather than obeyed.
    """
    node = ast.parse(annotation, mode="eval").body
    assert _declared_tuple_arity(node) == expected


def test_ar4_the_walk_reaches_the_package():
    """[AR-4] The source walk is non-empty and includes the two files the fixes touched.

    Without this, a package that moved or a glob that stopped matching would leave [AR-1]
    passing over nothing at all. The denominator is the claim.
    """
    found = {p.relative_to(REPO).as_posix() for p in _package_sources()}
    assert len(found) > 100, "only %d source files found under %s" % (len(found), PACKAGE)
    for expected in (
        "custom_components/eufy_vacuum/__init__.py",
        "custom_components/eufy_vacuum/adapters/eufy/segmentor.py",
    ):
        assert expected in found, "%s is not in the walked set" % expected
