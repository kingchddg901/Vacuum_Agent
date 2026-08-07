"""The W0 ratchet — bare-mock debt may shrink, never grow.

PLAN-mock-integrity W0: "lands before any migration so the debt can't grow while
it drains." That ordering is the point. Converting 40 files takes several waves;
without this, new bare mocks land in new places faster than the old ones leave,
and the campaign never converges.

WHAT A BARE MOCK COSTS
----------------------
A bare ``MagicMock()`` / ``AsyncMock()`` **agrees with the caller, not the
callee**. Every attribute exists, every method returns another mock, every shape
assertion passes. Audit 1 traced four live failures to exactly that: production
code asked a question the real object would have refused, the mock answered
cheerfully, and the test stayed green all the way to hardware. Two are documented
verbatim in docs/testing/04 (``mgr.learning`` as a phantom attribute; the
``_collect_finalization_inputs`` missing-kwargs TypeError that cost two live runs).

WHAT THIS IS NOT
----------------
Not a ban. Entity-driving partial stubs are correct and stay
(docs/testing/04-patterns). The doctrine's line is "a mock handed INTO production
code must be spec'd" — which needs per-site judgement, and that is W2's job, not
a regex's. This gate only holds the TOTAL steady so that judgement has time to
happen.

TO CHANGE THE ALLOWLIST
-----------------------
Lowering a number, or removing a file, needs nothing — that is the direction of
travel and the test simply passes. Raising one requires deleting this test, which
is deliberately harder than converting the mock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO / "tests" / "mock_allowlist.json"

sys.path.insert(0, str(REPO / "scripts"))
from mock_census import census  # noqa: E402  (path shim above)


def _ceilings() -> dict[str, int]:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))["ceilings"]


def test_no_new_file_introduces_bare_mocks():
    """[MR-1] A file NOT on the allowlist may have zero.

    This is the half that actually stops the bleeding: the debt is concentrated in
    40 known files, and the failure mode the campaign has to prevent is it
    reappearing in the 142 that are currently clean.
    """
    ceilings = _ceilings()
    offenders = {
        path: prof["bare_mock"] + prof["bare_async"]
        for path, prof in census().items()
        if path not in ceilings and (prof["bare_mock"] or prof["bare_async"])
    }
    assert not offenders, (
        "New bare MagicMock()/AsyncMock() in files that had none:\n  "
        + "\n  ".join(f"{p}: {n}" for p, n in sorted(offenders.items()))
        + "\n\nA bare mock agrees with its CALLER, so it cannot fail the way the real "
          "object would. If it is handed into production code, use spec_manager() or "
          "create_autospec(). If it only drives an entity's own render, that is "
          "sanctioned (docs/testing/04) — say so in a comment and add the file to "
          "tests/mock_allowlist.json in the SAME commit, so the exemption is a "
          "decision on the record rather than a silent regression."
    )


def test_listed_files_do_not_exceed_their_ceiling():
    """[MR-2] A file ON the allowlist may not grow past its recorded count."""
    ceilings = _ceilings()
    c = census()
    grown = {
        path: (cap, c[path]["bare_mock"] + c[path]["bare_async"])
        for path, cap in ceilings.items()
        if path in c and (c[path]["bare_mock"] + c[path]["bare_async"]) > cap
    }
    assert not grown, (
        "Bare-mock count grew in files already carrying debt:\n  "
        + "\n  ".join(f"{p}: {cap} -> {now}" for p, (cap, now) in sorted(grown.items()))
        + "\n\nThe allowlist is SHRINK-ONLY. Convert the mock, or if the addition is "
          "genuinely sanctioned, lower some other count in the same file first."
    )


def test_allowlist_has_no_stale_entries():
    """[MR-3] Hygiene: an entry for a file that no longer exists, or that no longer
    has bare mocks, is debt that has been PAID and should be banked.

    Without this the ratchet silently loosens: a converted file keeps its old
    ceiling, so a future regression back to that count passes MR-2.
    """
    ceilings = _ceilings()
    c = census()
    gone = sorted(p for p in ceilings if p not in c)
    paid = sorted(
        p for p in ceilings
        if p in c and not (c[p]["bare_mock"] or c[p]["bare_async"])
    )
    assert not gone and not paid, (
        f"Allowlist is stale.\n  deleted files still listed: {gone}\n"
        f"  files now clean but still listed: {paid}\n\n"
        "Run `python scripts/mock_census.py --write-allowlist` to bank the progress. "
        "Leaving a paid-off entry lets the file silently regress to its old count."
    )


@pytest.mark.parametrize("path", sorted(_ceilings()))
def test_allowlist_entry_is_real(path):
    """[MR-4] Every listed path exists and is a test file — guards a typo'd key,
    which would otherwise create a permanently-unreachable exemption."""
    p = REPO / path
    assert p.is_file(), f"{path} is on the allowlist but does not exist"
    assert p.name.startswith("test_"), f"{path} is not a test file"
