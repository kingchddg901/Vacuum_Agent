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

# Illustrative paths used when DOCUMENTING the citation rule itself. They are not
# claims about this repo and must not be reported as broken ones.
PLACEHOLDERS = {"file.py", "path/to/file.py", "module.py"}

# An ID-form anchor: two-character class prefix + six Crockford Base32 characters.
# Owned by scripts/doc_anchor.py — see the note at its use below.
ANCHOR_ID_RE = re.compile(r"^(?:CN|ST)[0-9A-HJKMNP-TV-Z]{6}$")

# Tallied by form, because the ban is on the FORM, not on being currently wrong.
FORMS = {"line": 0, "symbol": 0, "anchor": 0, "strong": 0, "weak": 0}

# `path/to/file.py::symbol` / `file.py:symbol` / `file.py:120` / `:120-140`.
#
# The `::` branch MUST come first and MUST be spelled with two colons. The original
# pattern had one, so it matched `file.py:symbol` and never `file.py::symbol` — the
# very form this script exists to encourage. Every `::` citation in the corpus was
# skipped silently, which meant NO-SYMBOL reported zero findings because it had never
# been shown a single candidate. A detector that cannot see its target reads exactly
# like a clean one.
CITE_RE = re.compile(
    r"`(?P<path>[\w./-]+\.py)"
    r"(?:::(?P<sym>[A-Za-z_][\w.]*)"          # ::symbol — preferred, refactor-proof
    r"|#(?P<anchor>[^\s`]+)"                  # #anchor  — any unique string in the file
    r"|:(?P<sym1>[A-Za-z_][\w.]*)"            # :symbol  — older spelling, still valid
    r"|:~?(?P<line>\d+)(?:-(?P<end>\d+))?)"   # :N / :N-M (a leading ~ means "about")
    r"`"
)

# `file.py#anchor` — for targets that are real and stable but are not Python symbols:
# a config key (`clean_mode_options`), a keyword argument, a rule id in a comment.
# Roughly a fifth of the surviving line citations point at one of these, and forcing
# them into `::symbol` would name the enclosing 700-line registration function, which
# is true and useless.
#
# The repo already invented this. Sixty distinct rule ids (`RP-033/RF-32`,
# `live:ENT-4`) live in source comments, thirty of them are cited in the docs, and
# nothing has ever verified that a cited one still exists. Six do not.
#
# A rename breaks the citation, and that is correct — a renamed key IS a doc change.

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
    """Every citable symbol in a module → its line span.

    Includes module-level ASSIGNMENTS, not just def/class: `ADAPTER_CONFIG_SCHEMA`
    is a 1,900-line dict literal and the single most-cited thing in the adapter
    docs, and a citation landing inside it is pointing at a real, nameable target.
    Restricting this to callables was the reason a third of the corpus looked
    unrecoverable. Methods appear under both their bare name and `Class.method`,
    because the docs cite both forms.
    """
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return {}
    out: dict[str, list[tuple[int, int]]] = defaultdict(list)

    def record(name: str, start: int, end: int, prefix: str = "") -> None:
        out[name].append((start, end))
        if prefix:
            out[f"{prefix}.{name}"].append((start, end))

    def walk(node: ast.AST, prefix: str = "", in_func: bool = False) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                record(child.name, start, getattr(child, "end_lineno", child.lineno), prefix)
                is_cls = isinstance(child, ast.ClassDef)
                walk(child, child.name if is_cls else prefix, in_func or not is_cls)
                continue
            if isinstance(child, (ast.Assign, ast.AnnAssign)):
                # Module- and class-level only. A LOCAL inside a function body is not
                # a citable symbol, and admitting them was actively harmful: the
                # paragraph describing `register_adapter_config`'s issues list matched
                # a local named `issues`, and the citation converted to
                # `registry.py::issues` — a wrong pointer in a form that looks
                # permanently right. Caught by reading the applied diff, not by any
                # count the tool reported about itself.
                if in_func:
                    continue
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                span = (child.lineno, getattr(child, "end_lineno", child.lineno))
                for t in targets:
                    if isinstance(t, ast.Name):
                        record(t.id, *span, prefix)
                continue
            walk(child, prefix, in_func)

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

    # A bare `__init__.py` means the integration's own entry point. That is the
    # docs' established convention — `02-ha-integration.md` writes it that way eight
    # times — and it is unambiguous to a reader even though 35 files share the name.
    # Teaching the resolver the convention beats rewriting the prose to suit the tool.
    PACKAGE_ROOT = "custom_components/eufy_vacuum"

    def resolve(self, cited: str) -> tuple[pathlib.Path | None, str]:
        """Cited path → file on disk. Returns (path, note); note explains a miss."""
        cited = cited.lstrip("./")
        if cited == "__init__.py":
            cited = f"{self.PACKAGE_ROOT}/__init__.py"
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
            if cited in PLACEHOLDERS:
                continue  # illustrative, in the doc that explains this rule
            py, note = idx.resolve(cited)
            if py is None:
                problems.append(Problem(rel, lineno, "UNRESOLVED", f"`{cited}` — {note}"))
                continue

            syms = idx.symbols(py)
            checked += 1

            if (anchor := m.group("anchor")):
                FORMS["anchor"] += 1
                # An ID-form anchor (CN…/ST…) is owned by scripts/doc_anchor.py, which
                # resolves it repo-wide and distinguishes MOVED from DANGLING. Judging
                # it here on "is the string in THIS file" would call a moved-but-valid
                # citation broken, and two tools disagreeing about the same citation is
                # worse than one of them staying quiet.
                if ANCHOR_ID_RE.match(anchor):
                    continue
                body = py.read_text(encoding="utf-8", errors="replace")
                hits = body.count(anchor)
                if hits == 0:
                    problems.append(Problem(
                        rel, lineno, "NO-ANCHOR",
                        f"`{cited}#{anchor}` — that string does not appear in {py.name}"))
                continue

            sym = m.group("sym") or m.group("sym1")
            if sym:
                FORMS["symbol"] += 1
                name = sym.rstrip("()")
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
    print(f"             {FORMS['anchor']:4d} `file.py#anchor`   (refactor-proof)")
    print(f"  of the {FORMS['line']} line citations:")
    print(f"             {FORMS['strong']:4d} strong-checked — a symbol was named beside them")
    print(f"             {FORMS['weak']:4d} weak only — nothing establishes the line is right")
    return 1 if all_problems else 0


if __name__ == "__main__":
    sys.exit(main())
