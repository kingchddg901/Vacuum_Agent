"""The documentation ratchet — a new test file must be documented in the same commit.

PLAN-mock-integrity §7, the sibling of the mock ratchet. Chris asked "did we document
every test?" during planning. The answer was no: 36 of 183 test files appear nowhere
in docs/testing/, almost entirely the audit-campaign fix wave plus recent work.

WHY THIS IS THE SAME BUG CLASS AS THE MOCKS
-------------------------------------------
The truth pass verified every claim the docs already made. It could not verify the
ones they never made — an undocumented subsystem produces zero findings and reads
exactly like a clean one. Same shape as a bare mock agreeing with its caller: the
absence of a complaint gets mistaken for a pass.

That is also why this is a RATCHET and not a demand. Documenting 36 files is a doc
sprint; blocking on it would just get the gate deleted. Holding the number steady
costs one line per new test file and makes the backlog drain-only.

TO ADD A TEST FILE
------------------
Mention it in its subsystem page under docs/testing/. That is all — the check is a
basename match anywhere in docs/testing, deliberately generous, so a coverage-table
row or a sentence of prose both satisfy it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO / "tests" / "undocumented_tests.json"

sys.path.insert(0, str(REPO / "scripts"))
from mock_docs import undocumented_testfiles  # noqa: E402


def _known() -> set[str]:
    return set(json.loads(ALLOWLIST.read_text(encoding="utf-8"))["undocumented"])


def test_new_test_files_are_documented():
    """[DR-1] A test file created after this gate landed must be documented.

    The failure names the file, because the fix is one line in one page and the
    hardest part is knowing which page.
    """
    new = sorted(set(undocumented_testfiles()) - _known())
    assert not new, (
        "New test files that appear nowhere in docs/testing/:\n  "
        + "\n  ".join(new)
        + "\n\nAdd each to its subsystem page under docs/testing/ (a coverage-table "
          "row or a sentence both count). An undocumented test file yields no "
          "findings and reads exactly like a well-covered one — which is the blind "
          "spot this campaign exists to close, not widen."
    )


def test_documented_files_are_removed_from_the_backlog():
    """[DR-2] Hygiene: a file that HAS been documented must leave the allowlist.

    Without this the list only ever grows stale, and a documented file that later
    loses its mention silently passes DR-1 again.
    """
    known = _known()
    still_undocumented = set(undocumented_testfiles())
    paid = sorted(known - still_undocumented)
    assert not paid, (
        "These are now documented but still listed as undocumented:\n  "
        + "\n  ".join(paid)
        + "\n\nRemove them from tests/undocumented_tests.json to bank the progress."
    )


def test_allowlist_entries_still_exist():
    """[DR-3] A deleted test file must not linger in the backlog."""
    known = _known()
    gone = sorted(p for p in known if not (REPO / p).is_file())
    assert not gone, (
        "Allowlist references test files that no longer exist:\n  "
        + "\n  ".join(gone)
        + "\n\nRemove them from tests/undocumented_tests.json."
    )
