"""Count LEDGER-defects-code-vs-doc.md by ENTRY, not by string match.

WHY THIS EXISTS. The ledger's header used to carry hand-maintained counts. They
were wrong every time anyone checked, in the same direction, for months — and the
2026-08-24 truth pass rewrote them and then made them stale again within the hour
by ruling on one entry. A number a human has to remember to update is a number
that lies; this file replaces remembering with running.

WHY A NAIVE GREP IS NOT ENOUGH. `grep -c '\\[OPEN\\]'` over this file overcounts,
because the token names also appear in the header legend, in prose ("came back
NEEDS-RULING"), and inside `⤷` evidence lines. This counts only lines that are
actually an ENTRY, in one of the five shapes the file really uses:

    bullet        - [OPEN] **C13 `core/error_tracker.py` ...
    table row     | C2 [OPEN] | `room_entities.py:103` | ...
    token heading ### C55 [OPEN] — ...
    audit heading ### R1 · HIGH · over-scoped — ...        (stamped with ✅ APPLIED)
    dash heading  ## D39 — ...                             (stamped with ✅ APPLIED)

The two heading shapes carry no [TOKEN] slot, so a closed one is recognised by its
`✅ APPLIED` marker instead — which is why "audit rows" are reported separately
rather than folded into the token totals. They measure different sets and both
numbers are true; see the header note in the ledger itself.

Usage:  python .claude/notes/_ledger_census.py
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

LEDGER = Path(__file__).with_name("LEDGER-defects-code-vs-doc.md")

TOKENS = (
    "OPEN", "OPEN-DRIFTED", "NEEDS-RULING", "FIXED", "FIXED-UNPROVEN",
    "ACCEPTED", "NOT-A-DEFECT", "SUPERSEDED", "UNVERIFIABLE",
)
_TOK = "|".join(re.escape(t) for t in TOKENS)

# An entry line, in the three shapes that carry a token slot.
ENTRY = re.compile(
    rf"^(?:"
    rf"- \[(?P<t1>{_TOK})\]\s+\*{{0,2}}(?P<id1>[A-Z]+[0-9]+[a-z]?)\b"
    rf"|\|\s*(?P<id2>[A-Z]+[0-9]+[a-z]?)\s+\[(?P<t2>{_TOK})\]"
    rf"|#+\s*(?P<id3>[A-Z]+[0-9]+[a-z]?)\s+\[(?P<t3>{_TOK})\]"
    rf")"
)

# The two heading shapes with no token slot; closed ones wear ✅ APPLIED.
AUDIT_HEAD = re.compile(r"^#+\s*(?P<id>[A-Z]+[0-9]+[a-z]?)\s+(?P<applied>✅ APPLIED)?")

# The canonical "how much is left" grep the ledger header quotes.
CANONICAL_OPEN = re.compile(
    r"^(?:- \[OPEN\]|\| [A-Z]+[0-9]+ \[OPEN\]|#+ [A-Z]+[0-9]+ \[OPEN\])"
)


def main() -> int:
    if not LEDGER.exists():
        print(f"missing: {LEDGER}", file=sys.stderr)
        return 1
    lines = LEDGER.read_text(encoding="utf-8").split("\n")

    counts: collections.Counter[str] = collections.Counter()
    ids_by_token: dict[str, list[str]] = collections.defaultdict(list)
    seen_ids: collections.Counter[str] = collections.Counter()
    canonical = 0
    audit_total = audit_applied = 0

    for ln in lines:
        if CANONICAL_OPEN.match(ln):
            canonical += 1
        m = ENTRY.match(ln)
        if m:
            tok = m.group("t1") or m.group("t2") or m.group("t3")
            eid = m.group("id1") or m.group("id2") or m.group("id3")
            counts[tok] += 1
            ids_by_token[tok].append(eid)
            seen_ids[eid] += 1
            continue
        a = AUDIT_HEAD.match(ln)
        if a and "·" in ln:              # audit headings use · as their separator
            audit_total += 1
            if a.group("applied"):
                audit_applied += 1

    open_like = sum(counts[t] for t in ("OPEN", "OPEN-DRIFTED", "NEEDS-RULING"))

    print("TOKENISED ENTRIES (bullet / table row / token-heading)")
    for t in TOKENS:
        if counts[t]:
            print(f"  {t:<16} {counts[t]:>4}")
    print(f"  {'-' * 16} {'-' * 4}")
    print(f"  {'total':<16} {sum(counts.values()):>4}")
    print()
    print(f"still live (OPEN + OPEN-DRIFTED + NEEDS-RULING) : {open_like}")
    print(f"canonical [OPEN] grep                           : {canonical}")
    print()
    print("AUDIT-SECTION HEADINGS (no token slot; closed ones wear ✅ APPLIED)")
    print(f"  applied  {audit_applied:>4}")
    print(f"  open     {audit_total - audit_applied:>4}")
    print(f"  total    {audit_total:>4}")

    if counts["NEEDS-RULING"]:
        print()
        print("BLOCKED ON A DECISION, not on work:")
        for eid in ids_by_token["NEEDS-RULING"]:
            print(f"  {eid}")

    dupes = {i: n for i, n in seen_ids.items() if n > 1}
    if dupes:
        print()
        print("⚠ ID COLLISIONS — the same id names more than one entry.")
        print("  A stamper that locates rows by id can hit the wrong one.")
        for i, n in sorted(dupes.items()):
            print(f"  {i} appears {n}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
