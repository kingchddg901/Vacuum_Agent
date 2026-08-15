#!/usr/bin/env python3
"""Mint and verify documentation anchors — a stable name for a place in the code.

    # anchor: clean-mode-options-3W18QZ6B                    <- in source
    `adapters/eufy/adapter.py#clean-mode-options-3W18QZ6B`   <- in a doc

WHY NOT JUST A LINE NUMBER. Measured on this repo, 2026-08-15: 88% of the line
citations that could be verified were wrong, and three broke the same morning from
commits to the code they described. A line number rots without anyone touching the
document, and a rotted one still RESOLVES — it lands on plausible code and reads as
correct.

WHY NOT JUST THE SEMANTIC NAME. `file.py#clean_mode_options` was the first fix and
it has two flaws. Renaming the concept breaks every citation, so the docs punish a
rename. And a semantic name can become MISLEADING while still resolving — a key
called `clean_mode_options` that no longer holds options points somewhere real and
says something false. That is the line-number failure again, one level up.

SO THE ANCHOR IS BOTH. The human half (`clean-mode-options`) is a hint and may be
re-worded freely. The machine half (`7Q9K2M4X`, 8 characters of Crockford Base32) is
identity and never changes. 32^8 ≈ 1.1e12, so with a few thousand anchors a
collision is not a practical concern — and the minter checks anyway, because it is
free.

THE ID IS UNIQUE REPO-WIDE, WHICH MAKES THE PATH ADVISORY. `::symbol` and a bare
semantic anchor both break when code moves between files. An anchor does not: the
checker finds the ID wherever it now lives and reports the stale path as a fixable
finding rather than a broken citation.

THIS IS NOT A NEW CONVENTION HERE, only a checked one. Sixty distinct rule ids
(`RP-033/RF-32`, `live:ENT-4`, `SETUP-6`) already live in source comments and thirty
are cited in the docs. Nothing ever verified them; six are dangling. Those keep
working — any string in the file is a valid anchor — and new ones get an ID.

Run:
  python scripts/doc_anchor.py --mint clean-mode-options   # a fresh anchor token
      -> paste into source as:   # anchor: clean-mode-options-3W18QZ6B
  python scripts/doc_anchor.py --check                     # unique, cited, resolving
  python scripts/doc_anchor.py --orphans                   # anchors no doc cites

Exit code: 0 = every anchor unique and every citation resolves, 1 = otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Crockford Base32: no I, L, O or U — the four that get misread or mistyped when a
# human copies an id out of a comment and into a document.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ID_LEN = 8

SOURCE_ROOTS = ("custom_components", "scripts", "src", "harness")
DOC_ROOTS = ("docs",)

# An anchor must be DECLARED, never pattern-matched. Eight-letter uppercase English
# words are valid Crockford Base32 — the first run of this script reported
# `auto-DETECTED` and `runtime-DETECTED` as one colliding id, and RESOLVED, DISABLED
# and RECORDED would all have done the same. The `anchor:` marker is what makes a
# token an anchor. It also makes every anchor greppable in one pattern.
MARKER = "anchor:"
ANCHOR_RE = re.compile(
    MARKER + r"\s*([a-z][a-z0-9-]*[a-z0-9])-([" + ALPHABET + r"]{%d})\b" % ID_LEN
)
# A citation carries only the token, so validating one needs the bare shape too.
TOKEN_RE = re.compile(r"^([a-z][a-z0-9-]*[a-z0-9])-([" + ALPHABET + r"]{%d})$" % ID_LEN)
CITE_ANCHOR_RE = re.compile(r"`[\w./-]+\.py#([\w-]+)`")


def source_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in SOURCE_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix not in {".py", ".js", ".mjs"} or "__pycache__" in p.parts:
                continue
            if "node_modules" in p.parts:
                continue
            if p.name == "doc_anchor.py":
                continue  # its docstring shows the FORM; those are not anchors

            out.append(p)
    return out


def scan_anchors() -> dict[str, list[tuple[pathlib.Path, str]]]:
    """id -> [(file, full token)]. Keyed on the ID, because that is the identity."""
    found: dict[str, list[tuple[pathlib.Path, str]]] = defaultdict(list)
    for p in source_files():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for slug, ident in ANCHOR_RE.findall(text):
            found[ident].append((p, f"{slug}-{ident}"))
    return found


def mint(slug: str, taken: set[str]) -> str:
    """A deterministic-but-unpredictable id for `slug`, salted until it is free.

    Derived from the slug rather than from randomness so that a re-run for the same
    name is reproducible in a test, and salted on collision so it is still unique.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    if not slug:
        raise SystemExit("a slug needs at least one alphanumeric character")
    for salt in range(10_000):
        digest = hashlib.blake2b(f"{slug}:{salt}".encode(), digest_size=8).digest()
        n = int.from_bytes(digest, "big")
        ident = "".join(ALPHABET[(n >> (5 * i)) & 31] for i in range(ID_LEN))
        if ident not in taken:
            return f"{slug}-{ident}"
    raise SystemExit("could not find a free id — that should be impossible")


def cited_anchors() -> dict[str, list[tuple[str, int, str]]]:
    """anchor token -> [(doc, line, cited path)] for every `file.py#anchor` in docs."""
    out: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for root in DOC_ROOTS:
        for doc in sorted((ROOT / root).rglob("*.md")):
            rel = doc.relative_to(ROOT).as_posix()
            for i, line in enumerate(
                doc.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                for m in CITE_ANCHOR_RE.finditer(line):
                    path = re.match(r"`([\w./-]+\.py)#", m.group(0)).group(1)
                    out[m.group(1)].append((rel, i, path))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mint", metavar="SLUG", help="print a fresh anchor token")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--orphans", action="store_true")
    args = ap.parse_args()

    anchors = scan_anchors()

    if args.mint:
        print(mint(args.mint, set(anchors)))
        return 0

    problems: list[str] = []

    # 1 — an id used twice is not an identity. The whole design rests on this.
    for ident, places in sorted(anchors.items()):
        distinct = {tok for _, tok in places}
        files = {p for p, _ in places}
        if len(distinct) > 1:
            problems.append(
                f"COLLIDING  id {ident} carries {len(distinct)} different names: "
                + ", ".join(sorted(distinct))
            )
        elif len(files) > 1:
            problems.append(
                f"DUPLICATED {ident} appears in {len(files)} files: "
                + ", ".join(sorted(f.relative_to(ROOT).as_posix() for f in files))
            )

    cites = cited_anchors()
    by_token = {tok: p for places in anchors.values() for p, tok in places}

    for token, uses in sorted(cites.items()):
        m = TOKEN_RE.match(token)
        if not m:
            continue  # a legacy semantic anchor; checked by check_doc_citations.py
        ident = m.group(2)
        if ident not in anchors:
            for doc, line, _ in uses:
                problems.append(
                    f"DANGLING   {doc}:{line} cites {token}, which is in no source file")
            continue
        home = by_token.get(token)
        if home is None:
            continue
        home_rel = home.relative_to(ROOT).as_posix()
        for doc, line, path in uses:
            # The PATH IS ADVISORY. The id resolved, so the citation is not broken —
            # the code moved and the human-readable half is now stale.
            if not home_rel.endswith("/" + path.lstrip("./")) and not home_rel.endswith(path):
                problems.append(
                    f"MOVED      {doc}:{line} cites {path}#…, but {token} now lives in "
                    f"{home_rel}")

    if args.orphans:
        uncited = {tok for places in anchors.values() for _, tok in places} - set(cites)
        print(f"{len(uncited)} anchors in source that no document cites")
        for tok in sorted(uncited):
            print(f"  {tok}  ({by_token[tok].relative_to(ROOT).as_posix()})")
        return 0

    for p in problems:
        print(p)
    print()
    print(f"{len(anchors)} anchor ids in source · {len(cites)} cited in docs · "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
