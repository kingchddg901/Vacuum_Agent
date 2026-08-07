#!/usr/bin/env python3
"""Emit the generated "Mocking" column into the subsystem coverage tables.

PLAN-mock-integrity §8. Chris's question was "do the docs SAY which tests are
magic-mocked?" — they did not. The tables carry Stmts / Cov / Test files / Layer,
and Layer distinguishes unit from integration, which is NOT the axis that bites.
Bare-MagicMock vs spec'd vs real-fixture is.

ONE DERIVATION, TWO CONSUMERS: this reads the same ``mock_census`` that writes the
W0 ratchet's allowlist, so the documentation and the gate cannot disagree. Generated
means it cannot drift — hand edits to this column are overwritten.

Lives beside update_test_docs.py rather than inside it because that script owns the
NUMERIC cells (Stmts/Cov) from a coverage run; this owns one derived column from
source analysis, needs no pytest run, and is therefore useful on its own:

    python scripts/mock_docs.py            # write the column
    python scripts/mock_docs.py --check    # CI: fail if stale (writes nothing)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_census import census, mocking_label  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "testing" / "subsystems"

HDR = "Mocking"
HEADER_START = "| Source module "
SEP_RE = re.compile(r"^\|[-: ]+\|[-: |]*$")
ROW_RE = re.compile(r"^\|\s*`[^`]+\.py`\s*\|")
# Same shape update_test_docs.py uses to find test-file references in a row.
MENTION_RE = re.compile(
    r"`([\w/]*test_\w+\.py)`(?:\s*\((unit|int|integration|adapter|adapters)[^)]*\))?"
)
LAYER_DIR = {"unit": "unit", "int": "integration", "integration": "integration",
             "adapter": "adapters", "adapters": "adapters"}


def _cells(line: str) -> list[str]:
    """Split a markdown table row into its cells (no leading/trailing empties)."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _resolve(ref: str, hint: str | None, by_base: dict[str, list[str]]) -> str | None:
    ref = ref.replace("\\", "/")
    base = ref.rsplit("/", 1)[-1]
    cands = by_base.get(base, [])
    if "/" in ref:
        return ref if ref in cands else None
    if len(cands) == 1:
        return cands[0]
    if hint:
        want = LAYER_DIR.get(hint)
        for c in cands:
            if "/" + want + "/" in c:
                return c
    return None


def mock_cell(testfiles: set[str], profiles: dict[str, dict]) -> str:
    """Aggregate one module row's test files into a single cell.

    A row can list ten files, so this summarises. It reports the RISK rather than
    the pedigree: any unspec'd mock anywhere in the row shows, because a module
    whose coverage rests partly on bare mocks is exactly what the column exists to
    surface. "clean" therefore means nothing in the row constructs one.
    """
    if not testfiles:
        return "-"
    bare = 0
    bare_files = 0
    specd = False
    for rel in sorted(testfiles):
        prof = profiles.get(rel)
        if not prof:
            continue
        n = prof["bare_mock"] + prof["bare_async"]
        if n:
            bare += n
            bare_files += 1
        if prof["spec_manager"] or prof["autospec"]:
            specd = True
    if bare:
        suffix = " in " + str(bare_files) + " files" if bare_files > 1 else ""
        return "**bare x" + str(bare) + "**" + suffix
    return "spec'd" if specd else "clean"


def render(doc: Path, profiles: dict[str, dict], by_base: dict[str, list[str]]) -> str:
    """Return the doc's text with the Mocking column present and current.

    Idempotent by construction: every table row is rebuilt from its cells, and the
    column is set by NAME (found in the header) rather than by position, so running
    twice cannot append a second one.
    """
    out: list[str] = []
    col_index: int | None = None
    for raw in doc.read_text(encoding="utf-8").splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        nl = raw[len(line):]

        if line.startswith(HEADER_START):
            cells = _cells(line)
            if HDR in cells:
                col_index = cells.index(HDR)
            else:
                cells.append(HDR)
                col_index = len(cells) - 1
            out.append("| " + " | ".join(cells) + " |" + nl)
            continue

        if col_index is not None and SEP_RE.match(line):
            cells = _cells(line)
            while len(cells) <= col_index:
                cells.append("-------")
            out.append("|" + "|".join(cells) + "|" + nl)
            continue

        if col_index is not None and ROW_RE.match(line):
            cells = _cells(line)
            files: set[str] = set()
            for m in MENTION_RE.finditer(line):
                rel = _resolve(m.group(1), m.group(2), by_base)
                if rel:
                    files.add(rel)
            while len(cells) <= col_index:
                cells.append("")
            cells[col_index] = mock_cell(files, profiles)
            out.append("| " + " | ".join(cells) + " |" + nl)
            continue

        # A blank line ends the table, so a later prose table is not treated as one.
        if not line.strip():
            col_index = None
        out.append(raw)
    return "".join(out)


TESTING_DOCS = REPO / "docs" / "testing"
NAME_RE = re.compile(r"test_[a-z0-9_]+\.py")


def undocumented_testfiles() -> list[str]:
    """Test files that appear NOWHERE in docs/testing/.

    PLAN-mock-integrity §7. The truth pass verified the claims the docs already
    made; it could not verify the ones they never made — the coverage-from-scopes
    blind spot, where an undocumented subsystem and a clean one read identically.

    Deliberately generous: a mention ANYWHERE under docs/testing counts, prose
    included, matched by basename. A stricter rule (must appear in its subsystem's
    coverage table) would be more useful and would flag far more; this is the floor,
    chosen so the gate lands green-able today rather than blocking on a doc sprint.
    """
    text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(TESTING_DOCS.rglob("*.md"))
    )
    mentioned = set(NAME_RE.findall(text))
    return sorted(
        rel for rel in census() if rel.rsplit("/", 1)[-1] not in mentioned
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if any doc would change; write nothing")
    ap.add_argument("--undocumented", action="store_true",
                    help="list test files absent from docs/testing and exit")
    args = ap.parse_args()

    if args.undocumented:
        undoc = undocumented_testfiles()
        print(f"{len(undoc)} test files absent from docs/testing:")
        for rel in undoc:
            print("  " + rel)
        return 0

    profiles = census()
    by_base: dict[str, list[str]] = {}
    for rel in profiles:
        by_base.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)

    stale: list[str] = []
    for doc in sorted(DOCS.glob("*.md")):
        if doc.stem == "README":
            continue
        new = render(doc, profiles, by_base)
        if new == doc.read_text(encoding="utf-8"):
            continue
        if args.check:
            stale.append(doc.name)
        else:
            doc.write_text(new, encoding="utf-8")
            print("  upd  " + doc.name)

    if args.check and stale:
        print("STALE Mocking column in: " + ", ".join(stale))
        print("Run `python scripts/mock_docs.py` to regenerate.")
        return 1
    if args.check:
        print("Mocking column is current in every subsystem doc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
