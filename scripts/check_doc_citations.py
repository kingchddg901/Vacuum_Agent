#!/usr/bin/env python3
"""Check every `file.py:N` and `file.py::symbol` citation in the docs against source.

A citation is the cheapest possible NOW-doc claim: it says *this behaviour lives
here*. It is also the one claim that rots without anyone touching the document —
inserting a single import at the top of a module invalidates every line citation
below it, silently, in every doc that points at that module.

Measured on 2026-08-15: three of eight spot-checked citations in
`21-adapter-system.md` were wrong the same day, all three broken by commits made
that morning to code the doc describes. Nobody edited the doc. Nothing could have
told them.

WHAT IT CHECKS. Two forms, and the second is the point:

  `capabilities.py:187`                weak  — the line exists in the file
  `_sweep_siblings` (`capabilities.py:187`)
                                       STRONG — the cited line falls inside the
                                       named symbol. This is decidable, and when
                                       it fails the script prints the line the
                                       symbol is actually on.
  `capabilities.py::_sweep_siblings`   STRONG — the symbol exists in that file.

The strong form needs a symbol name near the citation, which the docs supply far
more often than not because a citation without a name is barely readable anyway.

WHY IT IS NOT A CI GATE (yet). Line citations break on ordinary refactors, so
gating on them would fail pushes for work that is not wrong. The standing rule is
that prose cites SYMBOLS, never line numbers — `file.py::symbol` survives any
refactor that does not rename the thing. So this script is a MIGRATION TOOL first:
it finds the broken citations and prints the `::symbol` form to replace them with.
Once a doc set is migrated, the symbol form is stable and gating becomes free.

Run:
  python scripts/check_doc_citations.py                      # every doc
  python scripts/check_doc_citations.py docs/dev/21-adapter-system.md
  python scripts/check_doc_citations.py --summary            # per-doc counts only

Exit code: 0 = every citation resolves, 1 = at least one is wrong.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Where a bare basename citation (`manager.py:12`) may be resolved from.
SOURCE_ROOTS = ("custom_components", "scripts", "tests", "harness")

DOC_ROOTS = ("docs",)

# Tallied by form, because the ban is on the FORM, not on being currently wrong.
FORMS = {"line": 0, "symbol": 0, "strong": 0, "weak": 0}

# `path/to/file.py:120` / `:120-140` / `file.py::symbol`, inside backticks.
CITE_RE = re.compile(
    r"`(?P<path>[\w./-]+\.py)"
    r"(?::(?P<sym>[A-Za-z_][\w.]*)"          # ::symbol
    r"|:~?(?P<line>\d+)(?:-(?P<end>\d+))?)"  # :N or :N-M  (a leading ~ is used
    r"`"                                     # in a few places for "about here")
)

# A symbol named near the citation: the last backticked identifier before it on
# the same line. `_sweep_siblings` (`capabilities.py:187`) is the common shape.
NEAR_SYM_RE = re.compile(r"`(?P<sym>[A-Za-z_][\w.]*(?:\(\))?)`")


@dataclass
class Problem:
    doc: str
    line: int
    kind: str
    detail: str


def symbol_ranges(py: pathlib.Path) -> dict[str, list[tuple[int, int]]]:
    """Every def/class in a module → its line span. Methods appear under both
    their bare name and `Class.method`, because the docs cite both forms."""
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return {}
    out: dict[str, list[tuple[int, int]]] = defaultdict(list)

    def walk(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                end = getattr(child, "end_lineno", child.lineno)
                out[child.name].append((start, end))
                if prefix:
                    out[f"{prefix}.{child.name}"].append((start, end))
                walk(child, child.name if isinstance(child, ast.ClassDef) else prefix)
            else:
                walk(child, prefix)

    walk(tree)
    return out


class Index:
    """Lazily-built map of source files, symbol tables and line counts."""

    def __init__(self) -> None:
        self._by_rel: dict[str, pathlib.Path] = {}
        self._by_base: dict[str, list[pathlib.Path]] = defaultdict(list)
        for root in SOURCE_ROOTS:
            base = ROOT / root
            if not base.is_dir():
                continue
            for py in base.rglob("*.py"):
                if "__pycache__" in py.parts:
                    continue
                rel = py.relative_to(ROOT).as_posix()
                self._by_rel[rel] = py
                self._by_base[py.name].append(py)
        self._syms: dict[pathlib.Path, dict[str, list[tuple[int, int]]]] = {}
        self._lines: dict[pathlib.Path, int] = {}

    def resolve(self, cited: str) -> tuple[pathlib.Path | None, str]:
        """Cited path → file on disk. Returns (path, note); note explains a miss."""
        cited = cited.lstrip("./")
        if cited in self._by_rel:
            return self._by_rel[cited], ""
        # a partial path like `adapters/eufy/adapter.py`
        matches = [p for rel, p in self._by_rel.items() if rel.endswith("/" + cited)]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            return None, f"{len(matches)} files match that path suffix"
        base = cited.rsplit("/", 1)[-1]
        cands = self._by_base.get(base, [])
        if len(cands) == 1:
            return cands[0], ""
        if len(cands) > 1:
            return None, f"ambiguous basename — {len(cands)} files named {base}"
        return None, "no such file"

    def symbols(self, py: pathlib.Path) -> dict[str, list[tuple[int, int]]]:
        if py not in self._syms:
            self._syms[py] = symbol_ranges(py)
        return self._syms[py]

    def length(self, py: pathlib.Path) -> int:
        if py not in self._lines:
            try:
                self._lines[py] = len(py.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                self._lines[py] = 0
        return self._lines[py]


def nearby_symbol(text: str, upto: int, syms: dict[str, list]) -> str | None:
    """The last backticked identifier before the citation that names a real symbol."""
    best: str | None = None
    for m in NEAR_SYM_RE.finditer(text, 0, upto):
        name = m.group("sym").rstrip("()")
        # `Class.method` and bare `method` are both indexed
        if name in syms:
            best = name
        elif "." in name and name.rsplit(".", 1)[-1] in syms:
            best = name.rsplit(".", 1)[-1]
    return best


def check_doc(doc: pathlib.Path, idx: Index) -> tuple[list[Problem], int]:
    problems: list[Problem] = []
    checked = 0
    text = doc.read_text(encoding="utf-8", errors="replace")
    rel = doc.relative_to(ROOT).as_posix()

    for lineno, line in enumerate(text.splitlines(), 1):
        for m in CITE_RE.finditer(line):
            cited = m.group("path")
            py, note = idx.resolve(cited)
            if py is None:
                problems.append(Problem(rel, lineno, "UNRESOLVED", f"`{cited}` — {note}"))
                continue

            syms = idx.symbols(py)
            checked += 1

            if m.group("sym"):
                FORMS["symbol"] += 1
                name = m.group("sym").rstrip("()")
                if name not in syms and name.rsplit(".", 1)[-1] not in syms:
                    problems.append(Problem(
                        rel, lineno, "NO-SYMBOL",
                        f"`{cited}::{name}` — {py.name} declares no such symbol"))
                continue

            FORMS["line"] += 1
            n = int(m.group("line"))
            if n > idx.length(py):
                problems.append(Problem(
                    rel, lineno, "PAST-EOF",
                    f"`{cited}:{n}` — the file is {idx.length(py)} lines"))
                continue

            near = nearby_symbol(line, m.start(), syms)
            if near is None:
                FORMS["weak"] += 1
                continue  # weak check only: the line exists, nothing names it
            FORMS["strong"] += 1
            spans = syms[near]
            if any(start <= n <= end for start, end in spans):
                continue
            where = ", ".join(f"{s}-{e}" for s, e in spans)
            problems.append(Problem(
                rel, lineno, "WRONG-LINE",
                f"`{cited}:{n}` is cited for `{near}`, which is at {where}"
                f"  → use `{cited}::{near}`"))

    return problems, checked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docs", nargs="*", help="docs to check (default: all under docs/)")
    ap.add_argument("--summary", action="store_true", help="per-doc counts only")
    args = ap.parse_args()

    if args.docs:
        targets = [pathlib.Path(d).resolve() for d in args.docs]
    else:
        targets = sorted(
            p for root in DOC_ROOTS for p in (ROOT / root).rglob("*.md")
        )

    idx = Index()
    all_problems: list[Problem] = []
    total_checked = 0
    per_doc: dict[str, tuple[int, int]] = {}

    for doc in targets:
        if not doc.is_file():
            print(f"skip (not a file): {doc}")
            continue
        problems, checked = check_doc(doc, idx)
        total_checked += checked
        all_problems.extend(problems)
        if checked or problems:
            per_doc[doc.relative_to(ROOT).as_posix()] = (checked, len(problems))

    if args.summary:
        for rel, (checked, bad) in sorted(per_doc.items(), key=lambda kv: -kv[1][1]):
            if bad:
                print(f"{bad:4d} wrong / {checked:4d} cited   {rel}")
    else:
        by_kind: dict[str, list[Problem]] = defaultdict(list)
        for p in all_problems:
            by_kind[p.kind].append(p)
        for kind in sorted(by_kind):
            print(f"\n### {kind} — {len(by_kind[kind])}")
            for p in by_kind[kind]:
                print(f"  {p.doc}:{p.line}  {p.detail}")

    print()
    print(f"{len(targets)} docs · {total_checked} citations checked · "
          f"{len(all_problems)} wrong")

    # Coverage, not just findings. A line citation with no symbol named beside it
    # gets the weak check only — the line exists, and nothing establishes it is the
    # RIGHT line. Reporting the wrong-count alone would let an unchecked citation
    # read exactly like a verified one, which is the failure this whole exercise is
    # about. Under the standing rule every `:N` is a defect anyway: a line number
    # that has rotted still resolves, so the reader lands on plausible code and
    # concludes the doc is current.
    print()
    print(f"  by form:   {FORMS['line']:4d} `file.py:N`  (every one a defect by rule)")
    print(f"             {FORMS['symbol']:4d} `file.py::symbol`  (refactor-proof)")
    print(f"  of the {FORMS['line']} line citations:")
    print(f"             {FORMS['strong']:4d} strong-checked — a symbol was named beside them")
    print(f"             {FORMS['weak']:4d} weak only — nothing establishes the line is right")
    return 1 if all_problems else 0


if __name__ == "__main__":
    sys.exit(main())
