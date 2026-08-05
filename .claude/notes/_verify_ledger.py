"""Cross-check the ledger's OPEN column against the shipped code.

WHY THIS EXISTS. Three entries went stale in a single day (2026-08-05): C17's last
quarter was applied with the box unticked, RF-36 read "1 of 4" when all four had
landed two days earlier, and ROOM-FLICKER-1 described a bounds check that had
already been removed with the mapping split. Each was found by hand, each cost a
full investigation, and the checklist is supposed to be a REPORT you can read in a
minute — not a list of leads.

The 2026-08-04 reconcile already learned the general lesson ("check the code, not
the count") and even recorded that 19 of 27 entries were stale. It learned it
MANUALLY. This is the same check, run by a script, so drift is caught the day it
appears instead of the next time somebody scopes work.

WHAT IT CAN AND CANNOT PROVE — and this is the whole reason it reports SUSPECT
rather than STALE. The 2026-08-04 pass already burned itself on exactly this: it
used "does the code cite the finding id?" as the test, put A2-POLYGO-6/-7 in the
open column, and both were already fixed by changes that never named their finding.
Absence of a marker proves nothing. PRESENCE of one is a real signal though: code
that names a finding id is code written to address it, so an OPEN finding whose id
appears in shipped source is a contradiction worth a human minute.

So this is a TRIAGE tool, not a verdict:
  * OPEN + cited in code   -> SUSPECT STALE. Read it. High hit rate.
  * CLOSED + not cited     -> unremarkable. Most fixes never cite an id.
  * OPEN + not cited       -> unremarkable. Could be genuinely open, could be
                              silently fixed. Only reading the seam settles it.

Run from the repo root:  python .claude/notes/_verify_ledger.py
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

NOTES = pathlib.Path(".claude/notes")
SEARCH_ROOTS = ["custom_components", "src"]


def _load(name: str, default):
    path = NOTES / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default


def _ledger_rows() -> list[dict]:
    """Every finding the checklist knows about, from the SAME inputs it uses."""
    rows: list[dict] = list(_load("_open_findings.json", []))
    rows.extend(_load("_direct_reads.json", []))
    return [r for r in rows if isinstance(r, dict) and r.get("id")]


def _closed_ids() -> set[str]:
    """Ids the checklist RENDERS as closed — struck through, or a ticked single.

    Read off the generated markdown on purpose, and the first version of this got
    it wrong: I reconstructed "applied" from the closure-matrix JSON myself, my
    guess at its shape returned nothing, and the tool reported 75 suspects
    including CRITICALs that RP-007 had closed weeks ago. A staleness checker that
    cries wolf is worse than none — it trains you to skip the report, which is the
    exact failure being fixed.

    OPEN-FIX-CHECKLIST.md is _gen_checklist.py's OUTPUT, so parsing it reads the
    generator's own verdict rather than a second, independently-wrong derivation of
    it. That is the point: one implementation of "is this closed", not two.
    """
    path = NOTES / "OPEN-FIX-CHECKLIST.md"
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    closed = set(re.findall(r"~~([A-Za-z0-9][A-Za-z0-9-]*)~~", text))
    closed |= set(re.findall(r"^- \[x\] \*\*`?([A-Za-z0-9][A-Za-z0-9-]*)`?\*\*",
                             text, re.MULTILINE))
    return closed


def _cited_ids() -> set[str]:
    """Finding ids named anywhere in shipped code."""
    try:
        out = subprocess.run(
            ["git", "grep", "-h", "-o", "-E",
             r"\b(live:)?[A-Z][A-Z0-9]+(-[A-Z0-9]+)+\b", "--", *SEARCH_ROOTS],
            capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return set()
    return {m.split(":", 1)[-1] for m in out.split()}


def main() -> int:
    rows = _ledger_rows()
    if not rows:
        print("no ledger rows found — run from the repo root")
        return 2

    applied = _closed_ids()
    wontfix = {
        str(a.get("finding_id", "")).split(":")[-1]
        for a in _load("_adjudicated_findings.json", [])
        if isinstance(a, dict) and not a.get("severity")
    }
    cited = _cited_ids()

    suspect: list[dict] = []
    for row in rows:
        fid = str(row["id"])
        if fid in applied or fid in wontfix:
            continue                      # already off the open board
        if fid in cited:
            suspect.append(row)

    print(f"ledger rows: {len(rows)}   ids cited in shipped code: {len(cited)}")
    print(f"OPEN findings whose id appears in shipped code: {len(suspect)}\n")
    if not suspect:
        print("  none — no contradiction between the open column and the source.")
        return 0

    print("  SUSPECT STALE — the code names these, so read them before scoping:\n")
    for row in sorted(suspect, key=lambda r: str(r.get("sev", ""))):
        where = subprocess.run(
            ["git", "grep", "-l", row["id"], "--", *SEARCH_ROOTS],
            capture_output=True, text=True, check=False,
        ).stdout.split()
        print(f"    {str(row.get('sev','?')):<9}{row['id']:<22}{row.get('file','')}")
        for path in where[:3]:
            print(f"               cited in {path}")
    print("\n  A marker is a HINT, never the test — 2026-08-04 put two already-fixed")
    print("  findings back on the board using exactly that reasoning. Read the seam.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
