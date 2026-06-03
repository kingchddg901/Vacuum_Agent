#!/usr/bin/env python3
"""Refresh the numbers in docs/testing/ from a real coverage run.

This owns only the *numeric* fields in the testing docs — per-module Stmts/Cov
cells, the per-subsystem Cov column, and the headline coverage/test-count
figures. All prose, module lists, test-file columns, and gap notes are left
untouched.

How to run (inside the test container, so pytest + the package import cleanly):

    docker run --rm -v "C:\\Users\\CKing\\Documents\\GITHUB\\Vacuum_Agent:/workspace" \\
        -w /workspace eufy-vacuum-test python scripts/update_test_docs.py

That regenerates coverage.json, then rewrites the docs in place. Add --dry-run
to preview the changes without writing. Add --no-run to reuse an existing
coverage.json (skips the ~95s pytest run).

The grand-total figures come from coverage's own totals (whole package). The
per-subsystem figures partition the package by top-level directory, so every
source file lands in exactly one subsystem (anything not in a named subsystem
dir is counted under 18-platforms).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "testing"
PKG_PREFIX = "custom_components/eufy_vacuum/"
COV_JSON = REPO / "coverage.json"

TEST_PATHS = ["tests/unit", "tests/integration", "tests/adapters"]

# Top-level source directory -> subsystem doc stem. Anything not listed here
# (root-level modules, models/, maps/, sensor/, brand/, ...) is 18-platforms.
DIR2DOC = {
    "core": "01-core",
    "jobs": "02-jobs",
    "queue": "03-queue",
    "rooms": "04-rooms",
    "planning": "05-planning",
    "learning": "06-learning",
    "mapping": "07-mapping",
    "battery": "08-battery",
    "maintenance": "09-maintenance",
    "dock": "10-dock",
    "setup": "11-setup",
    "profiles": "12-profiles",
    "onboarding": "13-onboarding",
    "themes": "14-themes",
    "adapters": "15-adapters",
    "listeners": "16-listeners",
    "services": "17-services",
}
PLATFORMS_DOC = "18-platforms"

# A per-module table row: | `module.py` | <stmts> | <cov> | rest... |
ROW_RE = re.compile(
    r"^(?P<head>\|\s*`(?P<mod>[^`]+\.py)`\s*\|)"
    r"(?P<stmts>[^|]*)\|(?P<cov>[^|]*)\|(?P<rest>.*)$"
)


def run_coverage() -> None:
    cmd = [
        "python", "-m", "pytest", *TEST_PATHS,
        "--cov=custom_components/eufy_vacuum", "--cov-branch",
        f"--cov-report=json:{COV_JSON}", "-p", "no:cacheprovider", "-q",
    ]
    print("running coverage:", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO, check=True)


def collect_case_count() -> int | None:
    """Number of test items after parametrization (pytest --collect-only)."""
    try:
        out = subprocess.run(
            ["python", "-m", "pytest", *TEST_PATHS, "-p", "no:cacheprovider",
             "--co", "-q"],
            cwd=REPO, check=True, capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        print("  warn: could not collect case count:", exc)
        return None
    return sum(1 for line in out.splitlines() if "::" in line)


def load_coverage() -> dict:
    if not COV_JSON.exists():
        sys.exit(f"coverage.json not found at {COV_JSON} (run without --no-run)")
    return json.loads(COV_JSON.read_text())


def build_index(cov: dict) -> dict[str, dict]:
    """relpath-under-package -> file summary, e.g. 'core/manager.py' -> {...}."""
    index = {}
    for path, entry in cov["files"].items():
        path = path.replace("\\", "/")
        if not path.startswith(PKG_PREFIX):
            continue
        index[path[len(PKG_PREFIX):]] = entry["summary"]
    return index


def doc_of(rel: str) -> str:
    return DIR2DOC.get(rel.split("/")[0], PLATFORMS_DOC)


def resolve(cell: str, target_doc: str, index: dict[str, dict]) -> str | None:
    """Map a table module cell (e.g. 'manager.py') to a coverage relpath,
    disambiguating by the subsystem the doc belongs to."""
    cands = [
        rel for rel in index
        if (rel == cell or rel.endswith("/" + cell)) and doc_of(rel) == target_doc
    ]
    return cands[0] if len(cands) == 1 else None


def count_tests() -> tuple[dict[str, int], dict[str, int]]:
    func_re = re.compile(r"^\s*(?:async\s+)?def test_", re.MULTILINE)
    files: dict[str, int] = {}
    funcs: dict[str, int] = {}
    for rel in TEST_PATHS:
        key = rel.split("/")[-1]  # unit / integration / adapters
        base = REPO / rel
        paths = list(base.rglob("test_*.py"))
        files[key] = len(paths)
        funcs[key] = sum(len(func_re.findall(p.read_text(encoding="utf-8"))) for p in paths)
    return files, funcs


# --------------------------------------------------------------------------- #
# Doc editing
# --------------------------------------------------------------------------- #

class Editor:
    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.changes = 0

    def sub(self, path: Path, pattern: str, repl, *, label: str, expect: int = 1) -> None:
        text = path.read_text(encoding="utf-8")
        new, n = re.subn(pattern, repl, text)
        if n != expect:
            print(f"  WARN [{path.name}] {label}: matched {n}, expected {expect}")
        if new != text:
            self.changes += n
            if not self.dry_run:
                path.write_text(new, encoding="utf-8")
            print(f"  upd  [{path.name}] {label} ({n})")


def fmt_stmt(totals: dict) -> str:
    return f"{totals['percent_statements_covered']:.1f}"


def update_per_module_tables(
    index: dict[str, dict], editor: Editor
) -> dict[str, set[str]]:
    """Rewrite the Stmts/Cov cells in every subsystem map. Returns, per doc
    stem, the set of coverage relpaths its table claims."""
    claimed: dict[str, set[str]] = {}
    for doc in DOCS.glob("subsystems/*.md"):
        stem = doc.stem
        if stem == "README":
            continue
        lines = doc.read_text(encoding="utf-8").splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            m = ROW_RE.match(line.rstrip("\n"))
            if not m:
                continue
            rel = resolve(m.group("mod"), stem, index)
            if rel is None:
                continue
            claimed.setdefault(stem, set()).add(rel)
            s = index[rel]
            new_line = (
                f"{m.group('head')} {s['num_statements']} "
                f"| {s['percent_covered_display']}% |{m.group('rest')}"
            )
            nl = "\n" if line.endswith("\n") else ""
            if new_line + nl != line:
                lines[i] = new_line + nl
                changed = True
        if changed:
            editor.changes += 1
            if not editor.dry_run:
                doc.write_text("".join(lines), encoding="utf-8")
            print(f"  upd  [{doc.name}] per-module rows")
    return claimed


def subsystem_totals(
    claimed: dict[str, set[str]], index: dict[str, dict]
) -> dict[str, str]:
    """Combined statement+branch coverage per subsystem, over exactly the
    modules each subsystem's table lists."""
    out: dict[str, str] = {}
    for stem, rels in claimed.items():
        cl = tot = 0
        for rel in rels:
            s = index[rel]
            cl += s["covered_lines"] + s["covered_branches"]
            tot += s["num_statements"] + s["num_branches"]
        out[stem] = str(round(100 * cl / tot)) if tot else "0"
    return out


def report_unclaimed(claimed: dict[str, set[str]], index: dict[str, dict]) -> None:
    """Source modules counted in the grand total but absent from every
    subsystem table — a doc-drift signal."""
    everywhere = set().union(*claimed.values()) if claimed else set()
    missing = sorted(rel for rel in index if rel not in everywhere)
    if missing:
        print(f"\n  note: {len(missing)} source module(s) not listed in any "
              f"subsystem table (counted in the grand total only):")
        for rel in missing:
            print(f"        {rel}  ({index[rel]['percent_covered_display']}%)")


def update_subsystem_index(per_sub: dict[str, str], totals: dict, editor: Editor) -> None:
    readme = DOCS / "subsystems" / "README.md"
    for stem, pct in per_sub.items():
        # Row form: | 01 | Core ... | [01-core](01-core.md) | 92% |
        # The trailing group tolerates a footnote mark (e.g. "81%¹ |").
        pat = rf"(\]\({re.escape(stem)}\.md\)\s*\|[^|]*?)\d+%([^|]*\|)"
        editor.sub(readme, pat, rf"\g<1>{pct}%\g<2>", label=f"cov col {stem}", expect=1)
    # Footnote-adjacent total line.
    editor.sub(
        readme, r"(\*\*Total:\s*)[\d.]+(% statement coverage\*\*)",
        rf"\g<1>{fmt_stmt(totals)}\g<2>", label="total stmt")
    editor.sub(
        readme, r"(coverage\*\* \()\d+(% combined)",
        rf"\g<1>{totals['percent_covered_display']}\g<2>", label="total combined")


def update_overview(totals: dict, editor: Editor) -> None:
    f = DOCS / "01-overview.md"
    editor.sub(f, r"(\*\*Coverage:\s*)[\d.]+(% statement\*\*)",
               rf"\g<1>{fmt_stmt(totals)}\g<2>", label="stmt")
    editor.sub(f, r"(statement\*\* \()\d+(% combined)",
               rf"\g<1>{totals['percent_covered_display']}\g<2>", label="combined")


def update_readme(totals: dict, files: dict, funcs: dict, cases: int | None,
                  editor: Editor) -> None:
    f = DOCS / "README.md"
    tf = sum(funcs.values())
    nf = sum(files.values())
    editor.sub(f, r"(\*\*)[\d,]+( test functions\*\*)",
               rf"\g<1>{tf:,}\g<2>", label="funcs")
    editor.sub(f, r"(across \*\*)\d+( test files\*\*)",
               rf"\g<1>{nf}\g<2>", label="files")
    editor.sub(
        f, r"\(\d+ unit, \d+ integration, \d+ adapter\)",
        f"({files['unit']} unit, {files['integration']} integration, "
        f"{files['adapters']} adapter)", label="per-dir files")
    if cases is not None:
        editor.sub(f, r"[\d,]+( cases after parametrization)",
                   rf"{cases:,}\g<1>", label="cases")
    editor.sub(f, r"(\*\*)[\d.]+(% coverage\*\*)",
               rf"\g<1>{fmt_stmt(totals)}\g<2>", label="stmt")
    editor.sub(f, r"(coverage\*\* \()\d+(% combined)",
               rf"\g<1>{totals['percent_covered_display']}\g<2>", label="combined")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="preview, do not write")
    ap.add_argument("--no-run", action="store_true",
                    help="reuse existing coverage.json instead of running pytest")
    ap.add_argument("--no-collect", action="store_true",
                    help="skip the --collect-only run (leaves the case count alone)")
    args = ap.parse_args()

    if not args.no_run:
        run_coverage()
    cov = load_coverage()
    index = build_index(cov)
    totals = cov["totals"]
    cases = None if args.no_collect else collect_case_count()
    files, funcs = count_tests()

    print(f"\ntotals: {fmt_stmt(totals)}% statement / "
          f"{totals['percent_covered_display']}% combined")
    print(f"tests : {sum(funcs.values())} functions / {sum(files.values())} files"
          + (f" / {cases} cases" if cases else ""))

    editor = Editor(args.dry_run)
    claimed = update_per_module_tables(index, editor)
    update_subsystem_index(subsystem_totals(claimed, index), totals, editor)
    update_overview(totals, editor)
    update_readme(totals, files, funcs, cases, editor)
    report_unclaimed(claimed, index)

    print(f"\n{'(dry-run) ' if args.dry_run else ''}done — "
          f"{editor.changes} edit groups applied")


if __name__ == "__main__":
    main()
