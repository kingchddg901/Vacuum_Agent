#!/usr/bin/env python3
"""Check every test file's top-of-file coverage-target ID legend against the
[ID] labels used inline, and fail if they have drifted apart.

Most test files open with a module docstring "Coverage targets" legend that
lists ids like ``[XX-N]`` plus a one-line description each, and every test's own
docstring repeats its ``[id]`` inline. The legend LAGS as new tests land — that
rot is what this script catches.

Convention (enforced here):
  * Legends list WHOLE-NUMBER ids only. Letter-suffixed sub-variants
    (``[MSH-6b]``, ``[XX-3c]`` — a number followed by a letter) are inline-only
    and are NEVER expected in the legend, so a missing sub-variant is not drift.
  * A few ids appear inline purely as CROSS-REFERENCES — to a sibling file's
    test, or embedded inside another entry's prose ("mirrors ``[SD-5]``"). Those
    are not labels of a test defined in this file, so a naive diff false-positives
    on them. They live in CROSSREF_ALLOWLIST below and are ignored.

What counts as drift, per file with a legend:
  * MISSING  — a whole-number id is the primary label of a test in this file but
               is absent from the legend (legend lags new tests).
  * ORPHAN   — the legend lists an id with no matching inline label (a removed or
               renamed test).

Run it (Docker test image, like the rest of the test tooling — but it is pure
stdlib, so any Python 3 works):
  docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test \
      python scripts/check_legend_drift.py

Exit code: 0 = clean, 1 = drift found (suitable as a CI gate).

Sibling: update_test_docs.py owns the NUMERIC fields in docs/testing/; this owns
the per-file ID legends. Neither edits the other's surface.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

# Repo root = parent of this scripts/ dir.
ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# [XX-N] / [XX-Nb] coverage-target id; prefix 2-7 uppercase letters.
ID = re.compile(r"\[([A-Z]{2,7}-\d+[a-z]?)\]")
# A sub-variant id ends in a letter (e.g. MSH-6b) — inline-only by convention.
SUBVARIANT = re.compile(r"-\d+[a-z]$")

# Ids that legitimately appear inline but are NOT a test defined in that file
# (cross-references to a sibling file, or embedded in another entry's prose).
# Verified by hand during the 2026-06-12 legend sweep. Keep keys repo-relative
# with forward slashes.
CROSSREF_ALLOWLIST: dict[str, set[str]] = {
    # "the same one [WA-2] asserts" — WA-2's test lives in the water-amendment file.
    "tests/integration/test_listeners_active.py": {"WA-2"},
    # "...equals the module constants via [JE-6]..." inside the JSC-2 description;
    # JE-6 itself is defined in test_job_segmenter_engines.py.
    "tests/adapters/eufy/test_job_segmenter_config.py": {"JE-6"},
}


def _legend_and_body_ids(src: str) -> tuple[set[str], set[str]]:
    """Return (ids in the module docstring, ids everywhere else)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set(), set()
    node = tree.body[0] if tree.body else None
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)):
        return set(), set(ID.findall(src))  # no legend
    legend = set(ID.findall(node.value.value))
    lines = src.splitlines()
    for i in range(node.lineno - 1, node.end_lineno):
        if 0 <= i < len(lines):
            lines[i] = ""
    body = set(ID.findall("\n".join(lines)))
    return legend, body


def audit() -> list[dict]:
    drift = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        legend, body = _legend_and_body_ids(path.read_text(encoding="utf-8"))
        if not legend:
            continue  # no legend -> nothing to keep in sync
        allow = CROSSREF_ALLOWLIST.get(rel, set())
        missing = sorted(i for i in (body - legend - allow)
                         if not SUBVARIANT.search(i))
        orphan = sorted(legend - body - allow)
        if missing or orphan:
            drift.append({"file": rel, "missing": missing, "orphan": orphan})
    return drift


def main() -> int:
    drift = audit()
    if not drift:
        print("OK: every test-file coverage-target legend is in sync with its "
              "inline [ID] labels.")
        return 0
    print(f"LEGEND DRIFT in {len(drift)} file(s):\n")
    for d in drift:
        print(d["file"])
        if d["missing"]:
            print(f"  MISSING from legend (add these): {d['missing']}")
        if d["orphan"]:
            print(f"  ORPHAN in legend (no inline test): {d['orphan']}")
    print("\nFix: add each MISSING id to the file's top-of-file legend with a "
          "one-line description (whole-number ids only); remove or rename each "
          "ORPHAN. If an id is a legit cross-reference, add it to "
          "CROSSREF_ALLOWLIST in this script.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
