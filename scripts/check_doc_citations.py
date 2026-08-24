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

# Importable however this script is invoked: `python scripts/check_doc_citations.py`
# already puts `scripts/` on the path, `python -m scripts.check_doc_citations` does not.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# Where a bare basename citation (`manager.py:12`) may be resolved from.
#
# `src` was absent until 2026-08-21, so the ENTIRE frontend tree was outside this
# checker's world — not merely unparsed, unlisted. It could not answer even "does
# this file exist?" about any of the 240 line citations in `docs/dev/frontend/`,
# which is why that corpus accumulated them at 12.0 per doc against the backend's
# 1.4: the backend's were pruned by a gate that could see them.
SOURCE_ROOTS = ("custom_components", "scripts", "tests", "harness", "src")

# Extensions the resolver indexes. A citation into any of these is checkable.
SOURCE_SUFFIXES = (".py", ".mjs", ".js")

DOC_ROOTS = ("docs",)

# Generated/build output. Present only after a build, so a citation into it is not
# a broken reference on a clean checkout — the same asymmetry that makes
# `test_replica_ratchet.py` fail for a developer who has built and pass in CI.
BUILD_DIRS = ("/dist/", "/node_modules/", "/__pycache__/")

# Illustrative paths used when DOCUMENTING the citation rule itself. They are not
# claims about this repo and must not be reported as broken ones. The `my-panel` /
# `myanimal` family are the "how to add a panel" and "how to add an animal"
# tutorials in `architecture-overview.md` and `animal-svg.md`.
PLACEHOLDERS = {
    "file.py", "path/to/file.py", "module.py",
    "src/renderers/my-panel.js", "src/bindings/my-panel.js",
    "src/state/my-panel.js", "src/actions/my-panel.js",
    "animals/myanimal.js", "my-panel.js", "myanimal.js",
}

# An ID-form anchor: two-character class prefix + six Crockford Base32 characters.
# Owned by scripts/doc_anchor.py — see the note at its use below.
#
# IMPORTED, NOT RESTATED. This was a second copy of doc_anchor's class list, and a copy
# of a list that grows is a copy that goes stale: it still read `CN|SN|HN|PN|IN` after
# `RN`, `BN` and `EN` were minted. A citation whose class is missing here does not fail
# loudly — it falls PAST the skip below and gets substring-counted in the single file it
# names, which succeeds by luck whenever the citation and the declaration share a file.
# Cite one across files and this gate reports NO-ANCHOR while `doc_anchor --check`
# correctly calls it MOVED: two gates, opposite verdicts, on the class the section pass
# minted 177 of. Importing makes a newly registered class covered here by construction.
from doc_anchor import TOKEN_RE as ANCHOR_ID_RE  # noqa: E402

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
    r"`(?P<path>[\w./-]+\.(?:py|mjs|js))"
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


# Every way this codebase names a JavaScript symbol. Regex, not a parser, and that is
# deliberate: the questions this gate asks are dumb ones — does the file exist, does
# the named symbol exist, has a cited target disappeared — and none of them need to
# understand JavaScript. Building a semantic JS analyser to delete line numbers would
# be the cure being worse than the disease.
#
# The PROTOTYPE-MIXIN form is the one that matters and the one a naive pattern misses.
# `architecture-overview.md` documents the choice ("Why prototype mixins rather than a
# component framework"), so the bindings and renderers are assembled as
# `proto._bindMap = function () {` rather than declared. A first pass that only matched
# declarations resolved 58% of the corpus; the misses were `_bindMap`, `_on`, `_onAll` —
# all of them assignments.
#
# INDENT IS THE FILTER, and it is load-bearing. Without it the method form matches
# any `foo(...) {` deep inside a body — a call with a trailing brace, an object
# literal, a callback — and every one of those becomes a phantom symbol that CHOPS
# the enclosing range into one-line slivers. Measured on the first pass: `resolvedTheme`
# reported a span of `377-377`, and 116 citations were flagged wrong against ranges
# that were an artifact of the extractor rather than the code. Real declarations,
# exports and prototype assignments all sit at column 0-2 in this codebase.
JS_SYMBOL_RE = re.compile(
    r"""^[ \t]{0,2}(?:
          (?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(?P<fn>[\w$]+)
        | (?:export\s+)?(?:default\s+)?class\s+(?P<cls>[\w$]+)
        | (?:export\s+)?(?:const|let|var)\s+(?P<var>[\w$]+)\s*=
        # proto.x = fn — the mixin form, at column 0-2. NOT `this.x = fn` inside a
        # constructor: that sits at indent 4, and widening the indent cap to reach it
        # re-admits every `foo(...) {` deep in a function body, which is what fragmented
        # every range into one-line slivers. Constructor-assigned handlers
        # (`_boundHandleResize`) are real citable things but get an anchor, not a symbol.
        | [\w$.]+\.(?P<prop>[\w$]+)\s*=\s*(?:async\s+)?(?:function|\()
        | (?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?(?P<meth>[\w$]+)\s*\([^;]*\)\s*\{  # method
    )""",
    re.X,
)
# Words that match the method form but are control flow, not symbols.
JS_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "catch", "function", "return", "else",
    "do", "try", "with", "case", "typeof", "await", "new", "delete", "void",
})


def symbol_ranges_js(path: pathlib.Path) -> dict[str, list[tuple[int, int]]]:
    """Every citable symbol in a JS/MJS module → its line span.

    ⚠ SPANS ARE APPROXIMATE. A symbol runs from its own line to the line before the
    next symbol, because brace-matching JavaScript correctly means handling template
    literals, regex literals and comments — a parser's job. Containment is the only
    thing the spans are used for (does line N sit inside symbol S), and for that an
    approximation is honest. A `::symbol` citation, the form this gate exists to
    encourage, needs only the NAME and is exact.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    found: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        m = JS_SYMBOL_RE.match(line)
        if not m:
            continue
        name = m.group("fn") or m.group("cls") or m.group("var") or m.group("prop") or m.group("meth")
        if not name or name in JS_KEYWORDS:
            continue
        # A `const`/`let`/`var` is a MODULE-LEVEL symbol only at column 0. Indented, it is a
        # LOCAL and indexing it is actively harmful: `animalHslComponents` in
        # `styles/index.js` declares m/int/r/g/b/max/min/l/d/h/s/round at indent 2, and each
        # one truncated the enclosing function's range to a single line. Bad ranges make
        # by-line resolution confidently wrong, which is how a conversion pass produced
        # anchors claiming the modal host is appended in `_confirm`.
        indent = len(line) - len(line.lstrip())
        if m.group("var") and indent > 0:
            continue
        found.append((i, name))
    out: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for idx, (start, name) in enumerate(found):
        end = found[idx + 1][0] - 1 if idx + 1 < len(found) else len(lines)
        out[name].append((start, max(start, end)))
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
            for src in base.rglob("*"):
                if src.suffix not in SOURCE_SUFFIXES or not src.is_file():
                    continue
                rel = src.relative_to(ROOT).as_posix()
                if any(d in f"/{rel}/" for d in BUILD_DIRS):
                    continue
                self._by_rel[rel] = src
                self._by_base[src.name].append(src)
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
            self._syms[py] = (symbol_ranges(py) if py.suffix == ".py"
                              else symbol_ranges_js(py))
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



#: Directories whose citations are AS-OF THEIR DATE and must not be "corrected".
#:
#: `docs/dev/maintenance/` holds completed audit records — dated findings, ticked off,
#: naming the file and line as they were when the audit ran. `docs/dev/history/` holds
#: retired approaches. Both are HISTORY under `docs/dev/00-documentation-standard.md` §1:
#: a record of what was true then, which is never "wrong".
#:
#: Rewriting those citations so they resolve against today's tree would falsify the
#: record. A finding that says `repairs.py:1` is CORRECT — `repairs.py` existed when the
#: finding was filed, and its deletion is part of what the record documents. Pointing it
#: at some surviving file would erase exactly the fact worth keeping.
#:
#: `check_docs_index.py` already excludes `maintenance/` for a related reason (it is not
#: published to the site at all — `exclude_docs` in mkdocs.yml).
HISTORICAL_DIRS: tuple[str, ...] = ("dev/maintenance/", "dev/history/")


def _is_historical_record(path: pathlib.Path) -> bool:
    """True for a doc whose citations are a dated record, not a live claim."""
    rel = path.resolve().as_posix()
    return any(f"docs/{d}" in rel for d in HISTORICAL_DIRS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docs", nargs="*", help="docs to check (default: all under docs/)")
    ap.add_argument("--summary", action="store_true", help="per-doc counts only")
    args = ap.parse_args()

    if args.docs:
        targets = [pathlib.Path(d).resolve() for d in args.docs]
    else:
        targets = sorted(
            p
            for root in DOC_ROOTS
            for p in (ROOT / root).rglob("*.md")
            if not _is_historical_record(p)
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
