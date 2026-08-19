#!/usr/bin/env python3
"""Harvest invariant NOTICES already written in source comments.

WHAT THIS IS FOR. `docs/dev/00b-invariants.md` records rules the system must
preserve. Every one of its entries arrived the same way: a finding in the
2026-07 audit corpus, grouped into a repair family, promoted to a rule. That is
one route, and it only reaches rules somebody filed a DEFECT against.

The other route was never taken. Dozens of times, in comments, whoever was
standing there when a fix landed wrote down the rule they had just learned --
"must never", "or the store is wiped", "otherwise the card shows a room that is
gone". Those are invariants. They were simply never registered.

So, like `replica_census.py`, the first pass needs no new insight. It is a
harvest.

THE DISCRIMINATOR IS 00b'S OWN, and it is the whole point:

    An invariant states a rule AND its consequence. If you cannot name what goes
    wrong, you have a CONVENTION, not an invariant.

So a notice is ranked by whether it carries both halves. A line that says "always
use the helper" is a convention and should stay one -- promoting it would
manufacture exactly the unfalsifiable claim the registry exists to remove. A line
that says "never write here, HA overwrites it on shutdown and the edit becomes a
.corrupt backup" is an invariant that has been sitting in a comment.

WHY COMMENTS ARE GOOD EVIDENCE, AND WHY THEY ROT ANYWAY. A comment is normally
written LIVE -- at the change, by whoever had just worked out what was true. That
is why this repo trusts prose at the site over a document. But the property that
makes it accurate at birth is the property that lets it drift: a comment is
protected from casual rewriting, and that same inertia means NOTHING FORCES IT TO
CHANGE WHEN THE CODE AROUND IT DOES. Accurate when written, unmaintained after.

It therefore decays while still READING as authoritative, because sitting beside
the code is exactly why you believed it. A stale doc is suspected on sight; a
stale comment is trusted. That makes comment rot the more dangerous of the two.

Measured here, one week: 35 of 60 "(closed RP-x)" claims in source name a packet
whose commits never touched the file; mapping_services.py asserted room links are
"independent of the image-derived segments" when they are keyed BY them; a
docstring claimed write-time normalization in a function that normalizes on read.

WHAT THIS DOES NOT DO. It does not decide anything. Ranking is not a ruling: the
order is human ruling -> mint -> declare -> cite, and this tool sits before the
first step. It cannot tell a rule that is TRUE from one that WAS true. Every
candidate needs the code read, and STALE is an EXPECTED outcome -- a stale find is
worth more than a registerable one, because it was actively misleading.

Run from the repo root:
    python scripts/invariant_census.py                 # ranked candidates
    python scripts/invariant_census.py --seed <file>   # write a harvest table
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ROOTS = ("custom_components", "src", "scripts", "harness")
SUFFIXES = {".py", ".js", ".mjs"}

#: RULE — the writer is stating something the system must or must not do. Modal +
#: obligation. "MUST" shouted is this repo's own convention for a hard rule.
RULE = re.compile(
    r"(must (not|never|always)\b|\bMUST\b|\bNEVER\b(?! mind)"
    r"|is not optional|cannot be (allowed|permitted)"
    r"|always .{0,30}\b(before|first|after)\b"
    r"|\bINVARIANT\b|the rule is|by construction)",
    re.IGNORECASE,
)

#: CONSEQUENCE — what goes wrong. Without one there is no invariant, only a
#: preference, and 00b says so in as many words. This vocabulary is drawn from the
#: repo's own prose: it describes failures as silent, wiping, poisoning, ghosting.
CONSEQUENCE = re.compile(
    r"(silently|silent\b|otherwise\b|or the\b|or a\b"
    r"|corrupt|wipe[sd]?\b|overwrit|clobber|orphan|poison|stale\b|ghost"
    r"|is the bug|reads as|never fires|no test|nothing (says|reports|notices)"
    r"|lost\b|drops?\b|breaks?\b|fails? open)",
    re.IGNORECASE,
)

#: Already registered: an IN declaration or reference anywhere in the file.
IN_MARK = re.compile(r"\bIN[0-9A-HJKMNP-TV-Z]{6}\b")

#: Comment-ish lines only. A string literal containing "must never" is not a notice.
COMMENTISH = re.compile(r"^\s*(#|//|\*|\"\"\"|''')")

#: Noise: the registry, this tool, and the notation spec all quote the vocabulary.
SKIP_NAMES = {"invariant_census.py", "replica_census.py", "doc_anchor.py"}


def source_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix not in SUFFIXES or not p.is_file():
                continue
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            if p.name in SKIP_NAMES:
                continue
            out.append(p)
    return out


def harvest() -> list[dict]:
    rows: list[dict] = []
    for path in source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        registered = bool(IN_MARK.search(text))
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if not COMMENTISH.match(line) or not RULE.search(line):
                continue
            # a consequence may land on the next couple of lines -- the repo's
            # prose habitually states the rule then the cost.
            window = " ".join(lines[i - 1:i + 3])
            rows.append({
                "file": path.relative_to(ROOT).as_posix(),
                "line": i,
                "text": line.strip().lstrip("#/*").strip(),
                "has_consequence": bool(CONSEQUENCE.search(window)),
                "registered": registered,
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", help="write a harvest table to this markdown file")
    args = ap.parse_args()

    rows = harvest()
    fresh = [r for r in rows if not r["registered"]]
    strong = [r for r in fresh if r["has_consequence"]]
    weak = [r for r in fresh if not r["has_consequence"]]

    print(f"rule-shaped comment lines      : {len(rows)}")
    print(f"  in files with no IN anchor   : {len(fresh)}")
    print(f"  ...WITH a named consequence  : {len(strong)}   <- invariant candidates")
    print(f"  ...without one               : {len(weak)}   <- conventions, and should stay so")
    print(f"files holding a candidate      : {len({r['file'] for r in strong})}")

    if args.seed:
        out = ["# 00b-h — Invariant harvest (WORKING LIST, unclassified)", "",
               "> Generated by `python scripts/invariant_census.py --seed <this file>` and then",
               "> **edited by hand**. The STATUS column is the whole point and no regeneration",
               "> can recompute it.", "",
               "Every entry in [00b](00b-invariants.md) arrived from the audit corpus — a filed",
               "defect, grouped into a repair family, promoted. This is the other route: rules",
               "written down in comments by whoever learned them, and never registered.", "",
               "**Classify against 00b's own discriminator:** an invariant states a rule AND its",
               "consequence. No consequence → it is a `CONVENTION` and should stay one; promoting",
               "it manufactures the unfalsifiable claim the registry exists to remove.", "",
               "`STATUS`: ` ` unclassified · `INVARIANT` · `CONVENTION` · `PN` (binding but no",
               "code site) · `STALE` (asserts something no longer true).", "",
               "**Ranking is not a ruling.** A candidate here is a lead. The order stays",
               "human ruling → mint → declare → cite.", "",
               f"**{len(strong)}** lines state a rule AND a consequence in a file with no `IN` anchor.", "",
               "| STATUS | File | Notice |", "|---|---|---|"]
        for r in sorted(strong, key=lambda r: (r["file"], r["line"])):
            out.append(f"|  | `{r['file']}`:{r['line']} | {r['text'][:150]} |")
        pathlib.Path(args.seed).write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
        print(f"\n-> {args.seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
