#!/usr/bin/env python3
"""A test that NAMES what it covers must actually cover it.

    @pytest.mark.covers("custom_components/eufy_vacuum/mapping/tracker.py::_compact_dock_drift")
    def test_mt6_compaction_keeps_the_meta_header(...):

    python scripts/check_covers.py          # every marker in tests/
    python scripts/check_covers.py --list   # just show what is declared

WHY THIS EXISTS, and it is the only gate here built from a counted failure rather
than a single incident. On 2026-11-07 six tests in this repo passed without
exercising what they named. Four were written that same day, by the same author, in
the course of closing coverage gaps:

  * `LID-11` / `LID-12` asserted that a duplicate live slug keeps the first id and
    that an unusable live id is skipped. Both green on the first run. Both
    worthless: `rooms/room_discovery.py` had already renamed the duplicate slug and
    already dropped the bad id, so each assertion held for a reason other than the
    one it named -- and the lines they claimed stayed MISSED.
  * a staleness boundary pair built its fixtures FROM the constant under test, so
    moving that constant moved the fixture with it (30 -> 31 and 30 -> 29 both left
    the suite green).
  * `test_harvest_units.py` imported the unit table it was meant to be checking.
  * a rect-shape guard was subsumed by the `except` below it, so ablating the guard
    changed nothing.
  * `MTE-15` asserted on a counter that only moves once a room is current, so it
    measured 0 == 0.

WHAT CAUGHT EACH ONE WAS A SECOND INSTRUMENT -- coverage disagreeing with a green
test, a declared-empty red set, or a control assertion. THE SUITE ALONE NEVER CAUGHT
ONE. That is the gap this closes for exactly one of those shapes, the commonest:
the test passes, and the line it claims is still uncovered.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not catch the other shapes. A fixture derived from its own constant, a
self-referential import, a subsumed guard and a vacuous assertion all COVER their
target lines perfectly well -- coverage cannot see any of them, and ablation is
still the only instrument that can. This gate is not a substitute for declaring a
red set; it is the cheap half that can run unattended.

NO LINE NUMBERS, ON PURPOSE. Targets are `file.py::symbol`, never `file.py:120`.
Line citations rot: inserting 21 lines of comment into `dispatch/manager.py` on the
day this was written moved its guards from 669/706 to 727/730, and every line
citation written that morning was wrong by the afternoon.
`scripts/check_doc_citations.py` reached the same conclusion for docs and calls a
line citation "a defect by rule"; this follows it.

ITS OWN COVERAGE RUN. The CI behaviour gate runs `--no-cov` deliberately (coverage
is inspection-only there), so this cannot read a shared report. It runs the
DECLARING TESTS ONLY, scoped to the target's package directory. That is the
stronger claim and the one worth making: not "something in the suite covers this
symbol" but "THIS test does".

TWO CHECKS, AND THE SECOND ONE WAS MISSING UNTIL AN ABLATION FOUND IT. v1 ran all
the tests naming a symbol in ONE coverage run and asked whether the span came out
covered. Pointing an honest marker at a symbol its test never calls -- MTE-18 at
`_compact_dock_drift` -- left this gate GREEN, because the four genuine compaction
tests were in the same run and their coverage answered for the liar. The hole is
one level below the one the grouping comment in `main()` already warned about, and
the warning was written by the same hand that then shipped it.

So the claim is now evaluated per declaring test, using coverage's own per-test
CONTEXTS (`--cov-context=test`):

  * REACH, per test: every test naming a symbol must itself execute at least one
    line inside it. This is what a sibling's coverage used to hide.
  * SPAN, per symbol: the declaring tests TOGETHER must leave no line of it
    uncovered. Several tests legitimately share one symbol, one per branch, so
    this half stays collective -- and it is the half that catches LID-11's shape,
    where the test does enter but its named lines stay missed.

CONTEXTS NEED A NON-DEFAULT MEASUREMENT CORE. On python 3.14 coverage defaults to
`core=sysmon`, which warns "Dynamic contexts aren't supported ... context data may
be INCOMPLETE" -- and it is: under sysmon one of the two probe tests lost its
`setup` phase entirely. Incomplete attribution makes the REACH check fail tests
that do reach, so this forces `COVERAGE_CORE=ctrace` and then FAILS LOUDLY if the
warning shows up anyway, rather than reading a half-populated report as a verdict.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

# Overridable so this gate can be tested against a synthetic tree. A gate with no
# demonstrated failure is a preference, and the only way to demonstrate this one is
# to point it at a test that deliberately lies about what it covers -- which cannot
# live in the real suite. See tests/test_covers_gate.py.
ROOT = os.environ.get("COVERS_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
TESTS = os.path.join(ROOT, "tests")
MARKER = "covers"


def _decorator_targets(node: ast.AST) -> list[str]:
    """Every string passed to `@pytest.mark.covers(...)` on this function."""
    out: list[str] = []
    for dec in getattr(node, "decorator_list", []) or []:
        if not isinstance(dec, ast.Call):
            continue
        fn = dec.func
        # pytest.mark.covers / mark.covers -- match on the attribute chain's tail.
        if not (isinstance(fn, ast.Attribute) and fn.attr == MARKER):
            continue
        for arg in dec.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.append(arg.value)
    return out


def collect() -> list[tuple[str, str, str]]:
    """(test node id, target file, target symbol) for every declared marker.

    v1 reads MODULE-LEVEL test functions only. A marker inside a test class is
    reported as malformed rather than skipped -- an unreadable claim must be loud,
    which is the lesson `doc_anchor.py`'s MALFORMED check was written from: a
    declaration nothing can parse is invisible, and invisible reads as clean.
    """
    found: list[tuple[str, str, str]] = []
    problems: list[str] = []
    for dirpath, dirnames, names in os.walk(TESTS):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in sorted(names):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError as exc:  # pragma: no cover - a broken test fails louder elsewhere
                problems.append(f"{rel}: unparseable ({exc})")
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for target in _decorator_targets(node):
                        if "::" not in target:
                            problems.append(
                                f"{rel}::{node.name} declares {target!r} with no "
                                f"'::symbol' -- targets are file.py::symbol, never a line"
                            )
                            continue
                        tf, _, sym = target.partition("::")
                        found.append((f"{rel}::{node.name}", tf, sym))
                elif isinstance(node, ast.ClassDef):
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if _decorator_targets(sub):
                                problems.append(
                                    f"{rel}::{node.name}::{sub.name} -- markers inside a "
                                    f"test CLASS are not read yet; move the test to module "
                                    f"level or extend this collector"
                                )
    if problems:
        print("MALFORMED declarations (these are failures, not skips):")
        for p in problems:
            print(f"  {p}")
        print()
    return found, problems


def symbol_span(target_file: str, symbol: str) -> tuple[int, int] | None:
    """(first, last) line of `symbol` in `target_file`. Supports `Class.method`."""
    path = os.path.join(ROOT, target_file.replace("/", os.sep))
    if not os.path.isfile(path):
        return None
    tree = ast.parse(open(path, encoding="utf-8").read())
    want_cls, _, want_fn = symbol.rpartition(".")

    def _scan(body, cls=None):
        for node in body:
            if isinstance(node, ast.ClassDef):
                hit = _scan(node.body, node.name)
                if hit:
                    return hit
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == want_fn and (not want_cls or cls == want_cls):
                    return (node.lineno, node.end_lineno or node.lineno)
        return None

    return _scan(tree.body)


def run_coverage(node_ids: list[str], target_file: str) -> dict:
    """Run ONLY these tests, measuring the target's package directory, per test.

    A DIRECTORY source, never a dotted module: a separator-free `--cov` source makes
    coverage resolve it with `importlib.util.find_spec`, which imports the package
    tree mid-session, reloads NumPy and reddens 46 unrelated tests. The guard in
    `tests/conftest.py` (CNP337CY) refuses that form outright; this stays on the
    right side of it. A FRESH config file escapes the package-wide source in
    `.coveragerc` the way `--cov-config=/dev/null` used to, and `-o addopts=""`
    drops pytest.ini's own --cov flags.
    """
    pkg_dir = os.path.dirname(target_file)
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="covers_")
    os.close(fd)
    # A CONFIG FILE, not /dev/null any more: `show_contexts` has no command-line
    # flag, so per-test attribution cannot be switched on without one. It is written
    # fresh here rather than read from the repo, which keeps the escape from
    # `.coveragerc`'s package-wide source that /dev/null used to provide.
    cfd, cfg = tempfile.mkstemp(suffix=".ini", prefix="covers_cfg_")
    with os.fdopen(cfd, "w", encoding="utf-8") as fh:
        fh.write("\n".join([
            "[run]",
            "branch = True",
            "relative_files = True",
            "",
            "[json]",
            "show_contexts = True",
            "",
        ]))
    env = dict(os.environ)
    # NOT the default core on python 3.14. See the module docstring: sysmon cannot
    # carry dynamic contexts and says so, and the data it returned was genuinely
    # short by one test phase. ctrace is slower and correct.
    env["COVERAGE_CORE"] = "ctrace"
    # ITS OWN DATA FILE, OUTSIDE THE REPO, and this gate was SELF-POISONING without
    # it. coverage writes parallel data as `.coverage.<host>.pid<n>.<rand>` beside
    # COVERAGE_FILE, which defaulted to the repo root, and then combines every such
    # sibling it finds on the next run. An interrupted run leaves a ZERO-BYTE stub,
    # so the following run died with
    #     DataError: Couldn't use data file '.../.coverage...': no such table: context
    # -- and the same collision happens against the plain `--cov` sweeps used to read
    # per-file percentages, whose data has no context table at all. CI never saw it
    # because the behaviour gate there runs --no-cov, so nothing else writes one.
    # Pointing COVERAGE_FILE at the temp dir means the gate neither reads nor leaves
    # anything in the working tree. [CG-8] fences it.
    data_dir = tempfile.mkdtemp(prefix="covers_data_")
    env["COVERAGE_FILE"] = os.path.join(data_dir, ".coverage")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *node_ids,
             "-o", "addopts=", f"--cov-config={cfg}", "--cov-branch",
             "--cov-context=test",
             f"--cov={pkg_dir}", f"--cov-report=json:{tmp}",
             "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )
        # AN INCOMPLETE REPORT IS NOT A VERDICT. If the core fell back anyway, the
        # contexts are partial, the REACH check starts failing tests that do reach,
        # and the gate becomes the thing it was built to catch. Fail on the warning.
        if "no-sysmon-context" in (proc.stdout + proc.stderr):
            return {"_error": (
                "coverage warned that context data may be INCOMPLETE "
                "(no-sysmon-context) despite COVERAGE_CORE=ctrace, so per-test "
                "attribution cannot be trusted. INCONCLUSIVE, not a failed claim."
            ), "_out": proc.stdout[-3000:]}
        # INCONCLUSIVE IS NOT THE SAME AS UNMET, and conflating them is how this
        # gate lies. `--cov=<dir>` reports every .py under the source as FULLY
        # MISSING when it was never imported, so a run that collected zero tests --
        # a bad node id, an import error in the test module -- produces a report in
        # which every claim reads UNCOVERED. That fails, which is safe, but it names
        # the wrong culprit and would send someone to rewrite a correct test. Caught
        # by this gate's own control case ([CG-2]) reporting both symbols uncovered
        # in a tree where both were genuinely called.
        if proc.returncode != 0:
            return {"_error": (
                f"the declaring test(s) did not pass (pytest rc={proc.returncode}), so "
                f"the claim could not be evaluated. Fix the test first; this is "
                f"INCONCLUSIVE, not a failed claim."
            ), "_out": proc.stdout[-3000:]}
        # EXISTENCE BEFORE SIZE. `getsize` on a report coverage never wrote raises
        # FileNotFoundError, and this used to crash the whole gate with a traceback
        # instead of naming the run that produced nothing -- the self-poisoning case
        # above surfaced exactly that way, as an unhandled errno 2 on a path the
        # reader had no reason to care about. A missing report is INCONCLUSIVE, so say
        # so and carry the pytest output that explains it.
        if not os.path.exists(tmp) or not os.path.getsize(tmp):
            return {"_error": (
                "pytest exited 0 but wrote no coverage report, so the claim could "
                "not be evaluated. INCONCLUSIVE, not a failed claim -- the output "
                "below says why (a coverage DataError over a stale data file is the "
                "one seen in practice)."
            ), "_out": (proc.stdout + proc.stderr)[-3000:]}
        with open(tmp, encoding="utf-8") as fh:
            data = json.load(fh)
        data["_rc"] = proc.returncode
        data["_out"] = proc.stdout[-3000:]
        return data
    finally:
        for path in (tmp, cfg):
            try:
                os.unlink(path)
            except OSError:
                pass
        shutil.rmtree(data_dir, ignore_errors=True)


def per_test_reach(
    entry: dict, node_ids: list[str], first: int, last: int
) -> dict[str, list[int]]:
    """{node id: the lines of [first, last] THAT test executed}.

    pytest-cov names a context `<nodeid>|<phase>` -- run, setup or teardown. All
    three count: a fixture that drives the symbol is still that test exercising it.
    The phase suffix is split off, and a parametrized test is matched by prefix
    because the collector reads the function name while the context carries `[id]`.
    """
    ctx = entry.get("contexts") or {}
    out: dict[str, list[int]] = {n: [] for n in node_ids}
    for raw_line, names in ctx.items():
        try:
            line = int(raw_line)
        except (TypeError, ValueError):  # pragma: no cover - coverage keys are ints
            continue
        if not (first <= line <= last):
            continue
        for name in names:
            node = name.split("|", 1)[0]
            for want in node_ids:
                if node == want or node.startswith(want + "["):
                    out[want].append(line)
    return {k: sorted(set(v)) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true", help="show declarations and exit")
    args = ap.parse_args()

    markers, problems = collect()
    print(f"{len(markers)} `covers` declaration(s) across "
          f"{len({m[1] for m in markers})} target file(s)")
    if args.list:
        for node_id, tf, sym in sorted(markers):
            print(f"  {node_id}\n      -> {tf}::{sym}")
        return 1 if problems else 0

    # THE DENOMINATOR, always printed. A gate over zero declarations is a pass over
    # an empty set, and that renders identically to a real pass unless it says so.
    if not markers:
        print(
            "NOTHING DECLARED. Failing rather than passing: this gate is wired into CI\n"
            "because markers exist, so zero of them means they were removed, and a pass\n"
            "over an empty set is indistinguishable from a real pass. If the convention\n"
            "is genuinely being retired, remove the CI step in the same commit."
        )
        return 1

    failures: list[str] = list(problems)
    # GROUPED PER (file, symbol) for the RUN, then judged PER TEST.
    #
    # The grouping is an efficiency: one coverage run per symbol rather than one per
    # marker. It is NOT the unit of judgement, and v1's getting that wrong is the
    # defect an ablation found. The comment that stood here warned that grouping by
    # FILE would let a sibling answer for a false claim -- and then grouping by
    # symbol did exactly that, one level down: four honest compaction tests covered
    # `_compact_dock_drift` for a fifth test that never called it, and the gate said
    # ok. Contexts are what let the run stay grouped while the claim is checked
    # against the test that made it.
    by_symbol: dict[tuple[str, str], list[str]] = defaultdict(list)
    for node_id, tf, sym in markers:
        by_symbol[(tf, sym)].append(node_id)

    for (target_file, sym), group in sorted(by_symbol.items()):
        node_ids = sorted(set(group))
        print(f"\n{target_file}::{sym}  <- {len(node_ids)} test(s)")
        data = run_coverage(node_ids, target_file)
        if "_error" in data:
            failures.append(f"{target_file}: {data['_error']}\n{data.get('_out', '')}")
            continue
        entry = (data.get("files") or {}).get(target_file)
        if entry is None:
            failures.append(
                f"{target_file}: produced no coverage entry -- the declaring tests "
                f"never imported it. Measured files: "
                f"{sorted((data.get('files') or {}))[:6]}"
            )
            continue
        missing = set(entry.get("missing_lines") or [])
        span = symbol_span(target_file, sym)
        if span is None:
            failures.append(
                f"{target_file}::{sym} does not exist there.\n"
                f"    declared by: {', '.join(node_ids)}\n"
                f"    A claim nothing can resolve is worse than no claim: it reads as\n"
                f"    coverage and asserts nothing. Same reasoning as doc_anchor.py's\n"
                f"    MALFORMED check."
            )
            continue
        first, last = span
        uncovered = sorted(l for l in missing if first <= l <= last)
        print(f"    lines {first}-{last}  "
              f"{'ok' if not uncovered else f'UNCOVERED {uncovered}'}")

        # REACH, per test. Lines executed at IMPORT time carry the empty context, so
        # a `def` inside the span is attributed to no test and cannot stand in for
        # one -- which is what makes this check able to bite at all.
        reach = per_test_reach(entry, node_ids, first, last)
        for n in node_ids:
            hit = reach.get(n, [])
            print(f"      declared by {n}  "
                  f"{f'reaches {len(hit)} line(s)' if hit else 'NEVER REACHES IT'}")
            if not hit:
                failures.append(
                    f"{target_file}::{sym}\n"
                    f"    declared by: {n}\n"
                    f"    that test NEVER EXECUTES A LINE of the symbol it names. The\n"
                    f"    span is covered only because OTHER tests in this group cover\n"
                    f"    it, so the declaration asserts nothing. Either point the\n"
                    f"    marker at what the test really exercises, or delete it."
                )

        # SPAN, collective. LID-11's shape: the test runs, passes, and the lines it
        # named are still missing.
        if uncovered:
            failures.append(
                f"{target_file}::{sym} (lines {first}-{last})\n"
                f"    declared by: {', '.join(node_ids)}\n"
                f"    these lines stayed UNCOVERED when those tests ran: {uncovered}\n"
                f"    The test(s) PASS and do not exercise what they name. That is the\n"
                f"    shape this gate exists for -- see the module docstring."
            )

    print()
    if failures:
        print("=" * 78)
        print(f"{len(failures)} FAILURE(S)")
        print("=" * 78)
        for f in failures:
            print(f"\n{f}")
        return 1
    print(f"all {len(markers)} declaration(s) hold: each declaring test REACHES the "
          f"symbol it names, and together they leave no line of it uncovered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
