#!/usr/bin/env python3
"""Rank modules by the THREE signals that a coverage percentage alone cannot show.

    python scripts/coverage_triage.py            # after any run that wrote coverage.json
    python scripts/coverage_triage.py --all      # every module, not just flagged ones

⚠ WHY A PERCENTAGE IS THE WRONG INSTRUMENT ON ITS OWN. A line covered by an isolated
test with a mocked collaborator reads as SAFE while proving nothing — the mock agrees
with the CALLER, not the callee. The mock ratchet's own docs record Audit 1 tracing four
live failures to exactly that, green all the way to hardware. So the dangerous modules
are not only the low-percentage ones; they include high-percentage ones whose coverage
came from isolation, and the percentage actively hides those.

THE THREE SIGNALS (Chris's rubric, 2026-08-25):

  1. LOW COVERAGE      — a visible hole. Honest: you can see it.
  2. HIGH PARTIAL      — branches where only ONE side ever ran. The logic exists and one
     BRANCH RATE        path is exercised; the other is asserted by absence. This is the
                        "covered in isolation" shape, and line coverage cannot show it.
  3. BARE MOCKS        — the module's tests construct unspec'd MagicMock/AsyncMock.

  one signal = a signal · two = a loud signal · three = a heavy warning

THRESHOLDS ARE THE REPO'S OWN WORST QUARTILE, not magic numbers, so this keeps working
as the codebase moves and cannot be quietly satisfied by the tree drifting past a
hard-coded constant. `--all` prints them.

⚠ THIS IS A READING ORDER, NOT A DEFECT LIST. Some partial branches are defensive
guards that legitimately never fire, and some bare mocks are correct entity-driving
stubs. The output says WHERE TO LOOK; only reading the code says whether anything is
wrong. Treating a flag as a defect would be the same error as treating 100% as proof.

⚠⚠ ITS DISCRIMINATING POWER IS UNVALIDATED — AND ONE ATTEMPT WENT AGAINST IT.

Tested 2026-08-25 by mutation, flagged arm against a zero-signal control, prediction
written down before running (flagged survives, control dies):

  * BOUNDARY mutations (`>=`->`>`, `==`->`>=`) — BOTH SURVIVED. No discrimination.
    That round says more about the probe than the tool: branch coverage promises both
    SIDES of a conditional were taken, never that the boundary VALUE was used, so
    neither arm should have been expected to catch it. It did surface a real gap in
    both modules, `core/charging.py` included at 100%: boundary values go untested.
  * CONDITION INVERSION (`if X:` -> `if not X:`), which full branch coverage should
    catch — BOTH CAUGHT, and the HEAVY-flagged module failed 20 tests against the
    clean control's 2. The flagged module's tests were MORE sensitive, not less.

n=1 module per arm, and the mutated line in the flagged module was a COVERED one while
the signal actually points at its partial branches and its uncovered fifth — so this is
a weak disconfirmation, not a refutation. But it is the opposite of support, and no
run has yet supported it.

USE THIS AS A READING ORDER ONLY. Do NOT cite a tier as evidence that a module is
riskier, and do not scope an audit on it alone. Validating it properly means mutation
testing at scale — many sites across many modules in each arm, comparing SURVIVAL
RATES — which is a real instrument (mutmut, cosmic-ray) and a real investment. Until
that runs, the tiers are a hypothesis about where to look first.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import statistics
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
COV_JSON = REPO / "coverage.json"
SUBSYSTEMS = REPO / "docs" / "testing" / "subsystems"

MIN_STATEMENTS = 40  # below this, one branch swings the percentage wildly

_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*(\d+)%\s*\|(.*?)\|\s*(.*?)\s*\|\s*$")


def bare_mock_counts() -> dict[str, int]:
    """Bare-mock count per module, read from the generated `Mocking` column.

    That column is derived from the same census that feeds the mock ratchet, so this
    cannot disagree with the gate. Re-deriving it here would be a second answer to the
    question and would drift.
    """
    out: dict[str, int] = {}
    for page in sorted(SUBSYSTEMS.glob("*.md")):
        for line in page.read_text(encoding="utf-8").splitlines():
            m = _ROW.match(line)
            if not m:
                continue
            hit = re.search(r"bare x(\d+)", m.group(5))
            out[m.group(1)] = int(hit.group(1)) if hit else 0
    return out


def longest_missing_run(summary_file: dict) -> tuple[int, int]:
    """(longest run, total lines in runs >= 8) of CONSECUTIVE MISSING STATEMENTS.

    Chris's walking heuristic, made measurable: a scattered missing line is usually a
    `continue`, a guard, a log — safe to skip. A long uncovered RUN is a whole path
    nobody exercises, and that is worth reading whatever the percentage says.

    ⚠ ADJACENCY IS IN STATEMENTS, NOT LINE NUMBERS, and the difference is not academic.
    The first cut of this merged missing LINES within 3 of each other, so a 16-line
    comment block sitting mid-function split one real block into fragments — and the
    worst case in the repo, `services/stall_capture.py`, dropped off the list entirely
    while a module I had read by eye and knew was one solid block scored as noise.
    Non-statement lines are not uncovered code; they are not code. Walk the union of
    executed+missing (every statement, in order) and count runs that are all missing.

    Unlike the three-signal TIER, this number is a FACT about the tree rather than a
    prediction about risk, so it needs no validation to be worth acting on.
    """
    miss = set(summary_file["missing_lines"])
    if not miss:
        return 0, 0
    statements = sorted(miss | set(summary_file["executed_lines"]))
    runs, cur = [], 0
    for s in statements:
        if s in miss:
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return (max(runs) if runs else 0), sum(r for r in runs if r >= 8)


def load() -> list[dict]:
    if not COV_JSON.exists():
        sys.exit(
            "coverage.json not found. Produce it with:\n"
            "  docker run --rm -v \"<repo>:/workspace\" -w /workspace eufy-vacuum-test \\\n"
            "    python -m pytest tests --cov-report=json:coverage.json -q"
        )
    cov = json.loads(COV_JSON.read_text(encoding="utf-8"))
    mocks = bare_mock_counts()
    rows = []
    for path, f in cov["files"].items():
        s = f["summary"]
        if s["num_statements"] < MIN_STATEMENTS or not s["num_branches"]:
            continue
        short = path.replace("custom_components/eufy_vacuum/", "")
        longest, blocked = longest_missing_run(f)
        rows.append({
            "longest": longest, "blocked": blocked,
            "mod": short,
            "cov": s["percent_covered"],
            "stmts": s["num_statements"],
            "partial": s["num_partial_branches"],
            "prate": 100.0 * s["num_partial_branches"] / s["num_branches"],
            "bare": mocks.get(short) or mocks.get(short.rsplit("/", 1)[-1]) or 0,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="print every module and the thresholds")
    args = ap.parse_args()

    rows = load()
    if not rows:
        sys.exit("no modules met the statement floor — is coverage.json from a full run?")

    # Worst quartile on each axis, computed from this tree.
    cov_cut = statistics.quantiles([r["cov"] for r in rows], n=4)[0]        # bottom 25%
    prate_cut = statistics.quantiles([r["prate"] for r in rows], n=4)[2]    # top 25%

    for r in rows:
        r["sig"] = [
            "low-cov" if r["cov"] <= cov_cut else None,
            "partial" if r["prate"] >= prate_cut else None,
            "mocks" if r["bare"] >= 1 else None,
        ]
        r["sig"] = [s for s in r["sig"] if s]
        r["n"] = len(r["sig"])

    # PROVENANCE, PRINTED EVERY RUN. A stale or partial coverage.json produces a
    # confident, wrong ranking and looks identical to a good one. On 2026-08-25 a
    # leftover .coverage holding import-only data rendered an HTML report claiming 13%
    # against a real 92%; nothing about the output said so. The totals and the file's
    # own date are the cheapest way to catch that before acting on the list.
    total = json.loads(COV_JSON.read_text(encoding="utf-8"))["totals"]
    stamp = _dt.datetime.fromtimestamp(COV_JSON.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    print(f"  source: coverage.json written {stamp} — {total['percent_covered']:.1f}% overall, "
          f"{total['num_statements']} statements")
    if total["percent_covered"] < 50:
        print("  ⚠ that overall figure is implausibly low for this repo — the data is very "
              "likely import-only residue, NOT a full run. Re-run before trusting the list.")
    print(f"  {len(rows)} modules (>= {MIN_STATEMENTS} statements, with branches)")
    print(f"  thresholds from THIS tree — low-cov <= {cov_cut:.1f}% · partial-rate >= {prate_cut:.1f}% · mocks >= 1\n")

    tiers = [
        (3, "HEAVY WARNING  — all three"),
        (2, "LOUD           — two signals"),
        (1, "SIGNAL         — one"),
    ]
    for n, label in tiers:
        band = sorted((r for r in rows if r["n"] == n),
                      key=lambda r: (-r["partial"], r["cov"]))
        if not band and not args.all:
            continue
        print(f"  === {label}  ({len(band)}) ===")
        print("    cov    partial        bare  block  stmts  module")
        for r in band if (args.all or n >= 2) else band[:12]:
            blk = f"{r['longest']:>3}" if r['longest'] >= 8 else "  ·"
            print(f"    {r['cov']:5.1f}%  {r['partial']:>3} ({r['prate']:4.1f}%)  x{r['bare']:<4} "
                  f"{blk}    {r['stmts']:<5} {r['mod']}")
        if not args.all and n == 1 and len(band) > 12:
            print(f"    … {len(band) - 12} more (use --all)")
        print()

    blocks = sorted((r for r in rows if r["longest"] >= 8),
                    key=lambda r: -r["longest"])
    if blocks:
        print(f"  === LARGE UNCOVERED BLOCKS  ({len(blocks)}) — a FACT, not a prediction ===")
        print("    longest  in-blocks  cov     module")
        for r in blocks:
            print(f"      {r['longest']:>3}       {r['blocked']:>4}    {r['cov']:5.1f}%  {r['mod']}")
        print("    A scattered missing line is usually a guard or a log. A long run is a")
        print("    whole path nobody exercises — read these regardless of the percentage.")
        print()

    heavy = sum(1 for r in rows if r["n"] == 3)
    print(f"  {heavy} heavy · {sum(1 for r in rows if r['n'] == 2)} loud · "
          f"{sum(1 for r in rows if r['n'] == 1)} single")
    print("  Reading order, not a defect list — see this file's docstring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
