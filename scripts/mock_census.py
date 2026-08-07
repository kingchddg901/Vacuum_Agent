#!/usr/bin/env python3
"""Derive each test file's MOCK PROFILE from source. One derivation, two consumers.

PLAN-mock-integrity W0 (§4) + its §8 amendment. The census that feeds the ratchet
and the census that feeds the docs are the SAME computation, deliberately:

  * ``tests/test_mock_ratchet.py`` reads it to fail CI when bare-mock debt grows.
  * ``scripts/update_test_docs.py`` reads it to emit a generated "Mocking" column
    in the subsystem coverage tables.

Generated means it cannot drift. Chris's question behind §8 was "do the docs SAY
which tests are magic-mocked?" — they did not, and the unit/integration Layer
column does not distinguish bare-MagicMock from spec'd from real-fixture, which is
the axis that actually bites.

WHY ANY OF THIS EXISTS
----------------------
Audit 1's lesson, in Chris's words: "the MagicMock is killing us." A bare
``MagicMock()`` agrees with the CALLER, not the callee — every attribute exists,
every method returns a mock, every assertion about shape passes. Four separate
live failures reached hardware green because a mock cheerfully answered a question
production code would have refused. ``spec_manager()`` and ``create_autospec``
already fix that where they are used; this measures where they are not.

WHAT IS NOT A DEFECT
--------------------
Entity-driving partial stubs are CORRECT and stay (docs/testing/04-patterns). The
line the doctrine draws is not "no mocks" — it is: **a mock handed INTO production
code must be spec'd**. A stub that merely drives an entity's own render is fine.
This script therefore reports a profile, never a verdict; classification per site
is W2's job and needs judgement.

Run:  python scripts/mock_census.py            # human table
      python scripts/mock_census.py --json     # machine-readable
      python scripts/mock_census.py --write-allowlist   # regenerate the ratchet
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"
ALLOWLIST = TESTS / "mock_allowlist.json"

# The mock constructors that agree with their caller. Anything spec'd is the cure.
BARE_NAMES = {"MagicMock", "AsyncMock", "Mock", "NonCallableMock"}
SPEC_KWARGS = {"spec", "spec_set", "autospec"}
CURE_NAMES = {"create_autospec", "spec_manager"}

# Only these two remain textual, because neither can be misread as prose: an
# import statement and a function SIGNATURE.
FACTORY_RE = re.compile(r"^\s*from\s+\S*_factories\s+import", re.MULTILINE)
REAL_HASS_RE = re.compile(r"^\s*(?:async\s+)?def\s+test_\w*\([^)]*\bhass\b", re.MULTILINE)


def _fname(node: ast.AST) -> str:
    """The called name, whether `MagicMock(...)` or `mock.MagicMock(...)`."""
    f = getattr(node, "func", None)
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def profile(path: Path) -> dict:
    """The mock profile of one test file, counted from the AST.

    AST, not regex, and the reason is worth keeping: the first cut matched
    ``MagicMock(`` textually and promptly flagged tests/test_mock_ratchet.py — whose
    only mention of the word is the ERROR MESSAGE explaining the rule. A gate that
    punishes files for documenting the doctrine is a gate people route around. The
    same flaw would have counted every mention in a docstring, a comment, or a
    skip-reason string.

    Parsing also gets ``spec=`` right for free: ``MagicMock(spec=Foo)`` is the cure,
    and no lookahead hack is needed to exclude it.

    Falls back to a zero profile on a syntax error rather than raising — a test file
    that does not parse is a different problem, and this census should not be the
    thing that reports it.
    """
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {k: 0 if k.startswith("bare") else False for k in
                ("bare_mock", "bare_async", "spec_manager", "autospec",
                 "factories", "mock_hass", "real_hass")}

    bare_mock = bare_async = 0
    spec_manager = autospec = mock_hass = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _fname(node)
        if name in CURE_NAMES:
            if name == "spec_manager":
                spec_manager = True
            else:
                autospec = True
            continue
        if name not in BARE_NAMES:
            continue
        if any(kw.arg in SPEC_KWARGS for kw in node.keywords if kw.arg):
            continue                      # spec'd: the cure, not the disease
        if name == "AsyncMock":
            bare_async += 1
        else:
            bare_mock += 1

    # A hass STAND-IN specifically: `hass = MagicMock()` / `self.hass = AsyncMock()`.
    # Tracked separately because its lie class differs — hass.states.get returns a
    # mock STATE OBJECT, which is the family audit 1 chased through the listeners.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = {t.id for t in targets if isinstance(t, ast.Name)}
        names |= {t.attr for t in targets if isinstance(t, ast.Attribute)}
        if "hass" in names and isinstance(node.value, ast.Call) and _fname(node.value) in BARE_NAMES:
            mock_hass = True

    return {
        "bare_mock": bare_mock,
        "bare_async": bare_async,
        "spec_manager": spec_manager,
        "autospec": autospec,
        "factories": bool(FACTORY_RE.search(src)),
        "mock_hass": mock_hass,
        "real_hass": bool(REAL_HASS_RE.search(src)),
    }


def census() -> dict[str, dict]:
    """Every test file under tests/, keyed by repo-relative POSIX path."""
    out: dict[str, dict] = {}
    for p in sorted(TESTS.rglob("test_*.py")):
        if "__pycache__" in p.parts:
            continue
        out[p.relative_to(REPO).as_posix()] = profile(p)
    return out


def mocking_label(prof: dict) -> str:
    """The one-cell summary the docs table shows.

    Ordered most-to-least reassuring, so a reader scanning the column sees the
    RISK, not the pedigree: a file that uses spec_manager AND has 9 bare mocks is
    reported by its bare mocks.
    """
    if prof["bare_mock"] or prof["bare_async"]:
        n = prof["bare_mock"] + prof["bare_async"]
        extra = " +hass" if prof["mock_hass"] else ""
        return f"bare x{n}{extra}"
    if prof["spec_manager"] or prof["autospec"]:
        return "spec'd"
    if prof["mock_hass"]:
        return "mock-hass"
    if prof["real_hass"]:
        return "real hass"
    return "no mocks"


def totals(c: dict[str, dict]) -> dict:
    return {
        "files": len(c),
        "files_with_bare": sum(1 for p in c.values() if p["bare_mock"] or p["bare_async"]),
        "bare_mock": sum(p["bare_mock"] for p in c.values()),
        "bare_async": sum(p["bare_async"] for p in c.values()),
        "spec_adopters": sum(1 for p in c.values() if p["spec_manager"] or p["autospec"]),
        "mock_hass_files": sum(1 for p in c.values() if p["mock_hass"]),
    }


def write_allowlist(c: dict[str, dict]) -> dict:
    """The SHRINK-ONLY ratchet input: per-file bare-mock ceilings, current counts.

    Only files that currently HAVE bare mocks are listed. A file absent from this
    map is not permitted any — which is what stops the debt reappearing somewhere
    new while the listed files drain.
    """
    allow = {k: v["bare_mock"] + v["bare_async"]
             for k, v in sorted(c.items()) if v["bare_mock"] or v["bare_async"]}
    payload = {
        "_doc": (
            "PLAN-mock-integrity W0 ratchet. Per-file CEILING on bare MagicMock()/"
            "AsyncMock() constructions. SHRINK ONLY: lowering a number is the point, "
            "raising one or adding a key fails tests/test_mock_ratchet.py. A file not "
            "listed here may have ZERO. Regenerate with "
            "`python scripts/mock_census.py --write-allowlist` ONLY when the numbers "
            "went down."
        ),
        "ceilings": allow,
    }
    ALLOWLIST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-allowlist", action="store_true")
    args = ap.parse_args()

    c = census()
    if args.write_allowlist:
        payload = write_allowlist(c)
        print(f"wrote {ALLOWLIST.relative_to(REPO)} — {len(payload['ceilings'])} files")
        return 0
    if args.json:
        print(json.dumps({"totals": totals(c), "files": c}, indent=2))
        return 0

    t = totals(c)
    print(f"{t['files']} test files | {t['bare_mock']} bare MagicMock + "
          f"{t['bare_async']} bare AsyncMock across {t['files_with_bare']} files")
    print(f"{t['spec_adopters']} files use spec_manager/create_autospec | "
          f"{t['mock_hass_files']} mock the hass object\n")
    worst = sorted(c.items(), key=lambda kv: -(kv[1]["bare_mock"] + kv[1]["bare_async"]))
    for path, prof in worst[:15]:
        n = prof["bare_mock"] + prof["bare_async"]
        if not n:
            break
        print(f"  {n:3}  {mocking_label(prof):14}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
