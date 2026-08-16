#!/usr/bin/env python3
"""Harvest replica NOTICES already written in source comments.

WHAT THIS IS FOR. `docs/dev/00c-replicas.md` records rules deliberately implemented
in more than one place, so that changing one copy sends you to the others. Populating
it looks like a bootstrap problem — you need the register to know what is a replica,
and you build the register by noticing replicas — but the noticing has ALREADY
HAPPENED. Dozens of times, in prose, in comments, by whoever was standing there when
a fix landed in one copy and not its twin. It was simply never registered.

So the first census needs no new insight. It is a harvest.

WHAT THIS DOES NOT DO. It does not propose unification, and neither should you while
reading its output. Roughly half the divergence in this repo is deliberate: each copy
feeds a different consumer or derives its inputs differently, and forcing agreement
would force it where the copies SHOULD differ. Asking for "places that want a helper"
returns a list of helpers. The output here is evidence for a human to classify, and
the only question that classification has to answer is:

    Does changing one member OBLIGE changing the others?

WHAT IT CANNOT SEE. A replica nobody has ever remarked on. That is the real limit —
this finds recorded knowledge, not unrecorded structure. A family whose copies were
written independently and never noticed is invisible here and stays that way until a
bug proves it. Which is the argument for recording one AT THE FIX, when the evidence
is strongest and the mental model is already built.

Usage:
    python scripts/replica_census.py            # unregistered candidates first
    python scripts/replica_census.py --all      # include files already carrying an RN
    python scripts/replica_census.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Source roots. `custom_components/eufy_vacuum/frontend/` is DELIBERATELY excluded:
#: those .js files are BUILT from src/, so every hit there is a duplicate of a hit we
#: already have, and counting both would inflate the census with its own output.
ROOTS = ("custom_components", "src", "scripts", "harness")
SUFFIXES = {".py", ".js", ".mjs"}
EXCLUDE_PARTS = {"__pycache__", "node_modules", "dist", "frontend"}

#: The vocabulary people actually reach for when they notice a replica. Tuned to what
#: this repo says, not to what a duplicate-detector would look for — two 90%-identical
#: functions are often unrelated, while two that share no syntax at all can be twins
#: because both enforce "change X while preserving Y".
#: STRONG — the writer is asserting a rule lives in more than one place, or that
#: copies came apart. Near-certain replica notices.
STRONG = re.compile(
    r"(its twin|the twin\b"
    r"|both must agree|must stay in sync|keep(ing)? .{0,25}in sync"
    r"|same predicate|identical predicate"
    r"|written twice|second copy|third copy|two copies|three copies|other cop(y|ies)"
    r"|one copy of|copies drift|drifted apart|ONE COPY NOW"
    r"|in two places|in three places|exists twice|bound in TWO)",
    re.IGNORECASE,
)

#: WEAK — the same words people use for "this behaves like that", which in UI code is
#: usually interaction feel, not a shared obligation. KEPT rather than dropped, because
#: the single best find of the first run came through here:
#:   `sanitizeStepsForSave mirrors the backend normalize (profiles/manager...)`
#: a frontend/backend pair normalising the same thing — exactly a replica, and it would
#: have been lost by tightening. Tiered, so precision is reported instead of pretended.
WEAK = re.compile(
    r"(mirrors? (the|its)|mirroring the|same rule|same question|twins?\b"
    r"|duplicated deliberately)",
    re.IGNORECASE,
)

#: A notice that NAMES another location is likelier to be real whatever tier it hit.
#: "mirrors the backend normalize (profiles/manager.normalize_run_profile_steps)" is
#: evidence; "mirrors the room-name label" is prose about a widget.
NAMES_A_SITE = re.compile(r"[\w/]+\.(py|js|mjs)\b|\w+\.\w+\(\)|::\w+")

#: Already-registered: an RN declaration or reference anywhere in the file.
RN_MARK = re.compile(r"\bRN[0-9A-HJKMNP-TV-Z]{6}\b")

#: Comment-ish lines only. A string literal that happens to contain "twins" is not a
#: notice, and neither is a variable named `mirror`.
COMMENTISH = re.compile(r"^\s*(#|//|\*|\"\"\"|''')")


def source_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix not in SUFFIXES:
                continue
            if EXCLUDE_PARTS & set(p.parts):
                continue
            if p.name == pathlib.Path(__file__).name:
                continue  # this file describes the form; it is not a notice
            out.append(p)
    return out


def harvest() -> list[dict]:
    findings: list[dict] = []
    for path in source_files():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        registered = any(RN_MARK.search(l) for l in lines)
        hits = []
        for i, l in enumerate(lines, 1):
            if not COMMENTISH.match(l) or RN_MARK.search(l):
                continue
            strong, weak = bool(STRONG.search(l)), bool(WEAK.search(l))
            if not (strong or weak):
                continue
            hits.append({"line": i, "text": l.strip()[:160],
                         "tier": "strong" if strong else "weak",
                         "names_site": bool(NAMES_A_SITE.search(l))})
        if not hits:
            continue
        # Cluster adjacent hits: one comment block is ONE notice, not five candidates.
        clusters: list[list[dict]] = []
        for h in hits:
            if clusters and h["line"] - clusters[-1][-1]["line"] <= 4:
                clusters[-1].append(h)
            else:
                clusters.append([h])
        findings.append({
            "file": path.relative_to(ROOT).as_posix(),
            "registered": registered,
            "notices": len(hits),
            "strong": sum(1 for h in hits if h["tier"] == "strong"),
            "names_site": sum(1 for h in hits if h["names_site"]),
            "clusters": [
                {"at": c[0]["line"],
                 "tier": "strong" if any(x["tier"] == "strong" for x in c) else "weak",
                 "quote": " ".join(x["text"] for x in c)[:300]}
                for c in clusters
            ],
        })
    # STRONG first, then notices that NAME another site, and only then volume. Ranking
    # by count alone put seven "mirrors the canvas hit-test tap" UI comments above a
    # frontend/backend normaliser pair — loud, and about nothing.
    findings.sort(key=lambda f: (f["registered"], -f["strong"], -f["names_site"],
                                 -f["notices"], f["file"]))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true",
                    help="include files that already carry an RN anchor")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    findings = harvest()
    shown = findings if args.all else [f for f in findings if not f["registered"]]

    if args.json:
        print(json.dumps(shown, indent=2))
        return 0

    unreg = [f for f in findings if not f["registered"]]
    print(f"{sum(f['notices'] for f in findings)} replica notices in "
          f"{len(findings)} files · {len(unreg)} files carry NO RN anchor\n")
    for f in shown:
        flag = "" if f["registered"] else "  <-- UNREGISTERED"
        print(f"{f['file']}  ({f['strong']} strong / {f['notices']} total){flag}")
        for c in f["clusters"]:
            print(f"    [{c['tier'][0].upper()}] :{c['at']}  {c['quote'][:145]}")
        print()
    if not args.all and any(f["registered"] for f in findings):
        print(f"({sum(1 for f in findings if f['registered'])} file(s) with an existing "
              f"RN anchor hidden — pass --all to include them.)")
    print("\nCLASSIFY, do not unify. The question is: does changing one member OBLIGE\n"
          "changing the others? Record candidates in docs/dev/00c-replicas.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
