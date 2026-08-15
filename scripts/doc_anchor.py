#!/usr/bin/env python3
"""Anchor IDs — permanent identity for a place in the code, citable from a document.

    # anchor: CN7K3M9Q  injected stall flag        <- source
    `services/stall_capture.py#CN7K3M9Q`           <- doc
    rg CN7K3M9Q                                    <- the human fallback, always

THE SHAPE. Eight characters. The first two are a TYPE PREFIX, the remaining six are
opaque identity drawn from Crockford Base32.

    CNxxxxxx   code/document notation anchor
    STxxxxxx   semantic trace site

The prefix works like an IIN: it tells tooling what CLASS of identifier this is, not
what the anchored rule means. More prefixes get reserved when a genuinely distinct
class appears, not before.

THE SUFFIX IS RANDOM AND MEANS NOTHING. Not a content hash — deliberately, because a
hash changes when the content does, and the whole point is an identity that survives
the thing being edited, moved, renamed, or substantially rewritten. `ST7K3M9Q` says
"semantic-trace object 7K3M9Q" and nothing else: not the brand, not the subsystem,
not the version, not what it is for.

FIVE LAYERS, DELIBERATELY SEPARATE:

    prefix            identifier class
    opaque suffix     permanent identity
    descriptive name  current taxonomy — `live:ENT-13`, mutable, may be re-cut freely
    prose             the claimed meaning and contract
    code              the current implementation

`live:ENT-13` can evolve into something entirely different, or be retired. `CN7K3M9Q`
does not care. That separation is what makes the anchor a DRIFT-REVIEW SEAM: grep the
key, read the anchored prose beside the anchored code, and judge in one sitting
whether they still describe the same behaviour.

VERDICTS, and the distinctions matter:

    DUPLICATE   the same id in two places — a HARD ERROR. An id used twice is not an
                identity, and every other guarantee here rests on this one.
    DANGLING    cited, and in no source file. A broken citation.
    MOVED       cited against the wrong file, but the id was found elsewhere. NOT a
                break and NOT silently resolved either — the citation still works and
                the path is stale, so it is reported with the new home.

AN ANCHOR MUST BE DECLARED, never pattern-matched. Eight-character words drawn from
this alphabet occur in ordinary English — `STANDARD` and `STRANDED` are both valid
ST-prefixed tokens, and an earlier draft without the marker reported `auto-DETECTED`
and `runtime-DETECTED` as one colliding id. The `anchor:` marker is what makes a
token an anchor in source, and it makes every anchor greppable in one pattern.

Run:
  python scripts/doc_anchor.py --mint CN         # a fresh id to paste into source
  python scripts/doc_anchor.py --check           # unique · cited · resolving
  python scripts/doc_anchor.py --show CN7K3M9Q   # the drift seam: code beside prose
  python scripts/doc_anchor.py --orphans         # anchors no document cites

Exit code: 0 = every anchor unique and every citation resolves, 1 = otherwise.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import secrets
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Crockford Base32 — no I, L, O or U, the four that get misread or mistyped when a
# human copies an id out of a comment and into a document.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
SUFFIX_LEN = 6

# Identifier CLASS, not meaning. Reserve a new one only for a genuinely distinct
# class of thing; "another subsystem" is not a class.
PREFIXES = {
    "CN": "code/document notation anchor",
    "ST": "semantic trace site",
}

SOURCE_ROOTS = ("custom_components", "scripts", "src", "harness")
DOC_ROOTS = ("docs",)

MARKER = "anchor:"
TOKEN = r"(?:" + "|".join(PREFIXES) + r")[" + ALPHABET + r"]{%d}" % SUFFIX_LEN
TOKEN_RE = re.compile(r"^" + TOKEN + r"$")
# In SOURCE an anchor is only an anchor after the marker. A trailing descriptive
# label is encouraged and ignored — it is taxonomy, not identity.
DECL_RE = re.compile(MARKER + r"\s*(" + TOKEN + r")\b")
CITE_RE = re.compile(r"`(?P<path>[\w./-]+\.(?:py|js|mjs))#(?P<token>[\w:-]+)`")


def source_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in SOURCE_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix not in {".py", ".js", ".mjs"}:
                continue
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            if p.name == "doc_anchor.py":
                continue  # its docstring shows the FORM; those are not declarations
            out.append(p)
    return out


def scan() -> dict[str, list[tuple[pathlib.Path, int, str]]]:
    """token -> [(file, line, the whole declaration line)]."""
    found: dict[str, list[tuple[pathlib.Path, int, str]]] = defaultdict(list)
    for p in source_files():
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for tok in DECL_RE.findall(line):
                found[tok].append((p, i, line.strip()))
    return found


def cites() -> dict[str, list[tuple[str, int, str, str]]]:
    """token -> [(doc, line, cited path, the sentence)]."""
    out: dict[str, list[tuple[str, int, str, str]]] = defaultdict(list)
    for root in DOC_ROOTS:
        for doc in sorted((ROOT / root).rglob("*.md")):
            rel = doc.relative_to(ROOT).as_posix()
            for i, line in enumerate(
                doc.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                for m in CITE_RE.finditer(line):
                    out[m.group("token")].append(
                        (rel, i, m.group("path"), line.strip()))
    return out


def mint(prefix: str, taken: set[str]) -> str:
    """A fresh id. RANDOM, never derived — an id derived from content would change
    when the content did, which is the one thing this must never do."""
    prefix = prefix.upper()
    if prefix not in PREFIXES:
        raise SystemExit(
            f"unknown prefix {prefix!r} — reserved classes are: "
            + ", ".join(f"{k} ({v})" for k, v in PREFIXES.items()))
    for _ in range(1000):
        tok = prefix + "".join(secrets.choice(ALPHABET) for _ in range(SUFFIX_LEN))
        if tok not in taken:
            return tok
    raise SystemExit("could not find a free id — that should be impossible")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mint", metavar="PREFIX", help="CN or ST")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--show", metavar="TOKEN", help="code beside the prose citing it")
    ap.add_argument("--orphans", action="store_true")
    args = ap.parse_args()

    anchors = scan()

    if args.mint:
        print(mint(args.mint, set(anchors)))
        return 0

    citations = cites()

    if args.show:
        tok = args.show.upper()
        print(f"=== {tok} — {PREFIXES.get(tok[:2], 'unknown class')} ===\n")
        print("CODE")
        for p, ln, text in anchors.get(tok, []):
            rel = p.relative_to(ROOT).as_posix()
            body = p.read_text(encoding="utf-8", errors="replace").splitlines()
            print(f"  {rel}:{ln}")
            for j in range(ln - 1, min(ln + 6, len(body))):
                print(f"    {j + 1:5d} | {body[j]}")
        if not anchors.get(tok):
            print("  (declared nowhere in source)")
        print("\nPROSE")
        for doc, ln, _path, sentence in citations.get(tok, []):
            print(f"  {doc}:{ln}\n    {sentence[:300]}")
        if not citations.get(tok):
            print("  (cited by no document)")
        return 0

    if args.orphans:
        uncited = set(anchors) - set(citations)
        print(f"{len(uncited)} anchors in source that no document cites")
        for tok in sorted(uncited):
            p, ln, _ = anchors[tok][0]
            print(f"  {tok}  {p.relative_to(ROOT).as_posix()}:{ln}")
        return 0

    problems: list[str] = []

    # DUPLICATE is a hard error: an id used twice is not an identity, and every
    # other guarantee in this scheme rests on this one holding.
    for tok, places in sorted(anchors.items()):
        if len(places) > 1:
            where = ", ".join(f"{p.relative_to(ROOT).as_posix()}:{ln}"
                              for p, ln, _ in places)
            problems.append(f"DUPLICATE  {tok} declared {len(places)} times: {where}")

    for tok, uses in sorted(citations.items()):
        if not TOKEN_RE.match(tok):
            continue  # a legacy descriptive anchor; check_doc_citations.py covers it
        homes = anchors.get(tok)
        if not homes:
            for doc, ln, _p, _s in uses:
                problems.append(
                    f"DANGLING   {doc}:{ln} cites {tok}, declared in no source file")
            continue
        if len(homes) > 1:
            # Already reported as DUPLICATE. Picking one of them as "the" home would
            # then emit a MOVED against the other — a phantom second finding
            # manufactured by the first, and the noisier one would be the lie.
            continue
        home = homes[0][0].relative_to(ROOT).as_posix()
        for doc, ln, path, _s in uses:
            # Found, but not where the citation says. NOT a break — and not silently
            # resolved either. The citation works; the path is stale.
            if not home.endswith("/" + path.lstrip("./")) and home != path:
                problems.append(
                    f"MOVED      {doc}:{ln} cites {path}#{tok}, "
                    f"but {tok} now lives in {home}")

    for p in problems:
        print(p)
    print()
    print(f"{len(anchors)} anchors declared · {len(citations)} cited · "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
