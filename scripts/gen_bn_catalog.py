#!/usr/bin/env python3
"""A card catalog of every BN (break-notation) anchor in the tree.

    python scripts/gen_bn_catalog.py              # writes docs/dev/reference/BN-CATALOG.generated.md
    EVCC_GENDOC_OUT=<dir> python scripts/gen_bn_catalog.py   # the gate renders here and diffs

WHY A GENERATED FILE AND NOT A HAND-KEPT ONE. notation-anchors.md used to carry per-class
anchor counts, and every one of them was false by the time anyone read it — nothing
recounted them, so the block reported clean forever while the tree moved underneath it.
A catalog of 177 tokens that drifts with every BN pass would rot the same way, faster.
This one is registered in check_generated_docs.py as a gated generator, so CI diffs it on
every push and a stale catalog is a red build, not a quiet lie.

WHAT A CARD HOLDS. The token, the NAME on the line beneath it (the part people read — the
token is what survives renaming it), and which documents cite it. Grouped by file and
ordered by line, so a reader can see the regions of core/manager.py at a glance without
opening 7,629 lines.

⚠ NO LINE NUMBER, DELIBERATELY — AND THE SORT IS NOT THE COLUMN. This table carried one
until 2026-10-25, which made a CI-gated generated file a function of every anchored file's
LAYOUT: PR #76 inserted 18 lines into dock/manager.py and turned the gate red over
`430 -> 448`, a diff that said nothing about anchors. One in three contributor PRs since
the catalog landed hit it. Ordering by line is the feature and needs the number
INTERNALLY; printing it was a separate decision nobody made on purpose, and it contradicts
the notation itself — `notation-anchors.md` § `BN` cites a region as `path#TOKEN`, with no
line in the form, precisely so prose survives the code moving. The address IS the token:
grep it. This file now changes only when an anchor is added, removed, renamed, re-cited or
moves between files, which is exactly when a reader needs to know.

⚠ THE TOKENS IN THE OUTPUT ARE DATA, NOT REFERENCES. doc_anchor.cites() counts a bare
token anywhere under docs/ as a live citation, so a catalog listing every BN would make
every BN "cited" and turn the liveness check decorative — exactly the trap the design doc
names for worked examples. doc_anchor.ref_files() therefore excludes the output file by
name, the same way it excludes the gate test whose tokens are fixtures. Rename the output
and you must rename the exclusion, or liveness goes blind on the day the rename lands.

Reuses doc_anchor.scan() and doc_anchor.cites(); it does not re-parse anchors or guess.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from doc_anchor import ROOT, cites, scan  # noqa: E402

REL_OUT = "docs/dev/reference/BN-CATALOG.generated.md"
OUT_NAME = "BN-CATALOG.generated.md"

# Comment leaders and rule decorations stripped from the NAME line. A name line reads
# `# Service names` or `// ===== THE READ MODEL =====` or ` * Section`; what is left is
# the name. A line that is ONLY a rule (`# ------`) yields nothing, which the catalog
# reports as "(no name line)" — a BN with no name is an address to nowhere, and this is
# the only place that condition becomes visible without running the pass-time gate.
_LEADER_RE = re.compile(r"^\s*(?:#+|//+|/\*+|\*+/?|<!--|-->)\s*")
_RULE_RE = re.compile(r"^[\s=\-~_*]*$")
_DECOR_RE = re.compile(r"^[\s=\-~_]+|[\s=\-~_]+$")


def _name_beneath(path: pathlib.Path, line_no: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(unreadable)"
    if line_no >= len(lines):
        return "(no name line)"
    raw = lines[line_no]  # 0-based index of the line AFTER `line_no` (1-based)
    if _RULE_RE.match(raw):
        return "(no name line)"
    text = _LEADER_RE.sub("", raw)
    text = _DECOR_RE.sub("", text).strip()
    return text or "(no name line)"


def build() -> tuple[str, dict[str, int]]:
    decls = {tok: sites for tok, sites in scan().items() if tok.startswith("BN")}
    refs = cites(set(decls))

    by_file: dict[str, list[tuple[int, str, str, list[str]]]] = defaultdict(list)
    nameless = 0
    cited = 0
    for tok, sites in decls.items():
        for path, line_no, _decl in sites:
            rel = path.relative_to(ROOT).as_posix()
            name = _name_beneath(path, line_no)
            if name == "(no name line)":
                nameless += 1
            citing = sorted({r[0] for r in refs.get(tok, [])})
            if citing:
                cited += 1
            by_file[rel].append((line_no, tok, name, citing))

    total = sum(len(v) for v in by_file.values())
    out: list[str] = []
    out.append(
        "<!-- GENERATED FILE — DO NOT EDIT BY HAND. "
        "Regenerate: python scripts/gen_bn_catalog.py -->"
    )
    out.append("")
    out.append("# BN catalog — every break-notation anchor, by file")
    out.append("")
    out.append(
        "A `BN` anchors a **place**, not a claim — a region of a file that prose can address "
        "without the file being split. This is the card catalog of them: the name on the line "
        "beneath each one, and which documents cite it. There are deliberately no line "
        "numbers here — the citation form is `path#TOKEN` so that prose survives the code "
        "moving, and a column of line numbers would make this file drift every time any "
        "anchored file gained a line. The rule for when a divider earns one is in "
        "[design/shipped/notation-anchors.md](../design/shipped/notation-anchors.md) § `BN`."
    )
    out.append("")
    out.append(
        f"**{total} anchors in {len(by_file)} files · {cited} cited by at least one "
        f"document · {nameless} with no name line.**"
    )
    out.append("")
    out.append(
        "The tokens below are *data* — this file is excluded from the citation scan so "
        "listing an anchor here does not count as citing it. Cite from prose as "
        "`path#TOKEN` in backticks; the catalog deliberately never uses that form."
    )
    out.append("")

    for rel in sorted(by_file):
        rows = sorted(by_file[rel])
        out.append(f"## `{rel}` · {len(rows)}")
        out.append("")
        out.append("| token | section | cited by |")
        out.append("|---|---|---|")
        for _line_no, tok, name, citing in rows:
            cell = ", ".join(f"`{c}`" for c in citing) if citing else "—"
            safe = name.replace("|", "\\|")
            out.append(f"| {tok} | {safe} | {cell} |")
        out.append("")

    stats = {"anchors": total, "files": len(by_file), "cited": cited, "nameless": nameless}
    return "\n".join(out).rstrip() + "\n", stats


def main() -> int:
    text, stats = build()
    out_dir = os.environ.get("EVCC_GENDOC_OUT")
    dest = (pathlib.Path(out_dir) / OUT_NAME) if out_dir else (ROOT / REL_OUT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(
        f"wrote {dest} — {stats['anchors']} BN anchors in {stats['files']} files, "
        f"{stats['cited']} cited, {stats['nameless']} without a name line"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
