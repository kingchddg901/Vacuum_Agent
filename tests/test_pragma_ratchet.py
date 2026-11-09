"""The pragma ratchet — coverage waived outside the rule may shrink, never grow.

THE RULE, and why a gate rather than a sweep. The programme allows
`# pragma: no cover` for a LOGGER LINE only. Every other excluded line leaves the
arithmetic as well as the report, so a pragma elsewhere makes a file's percentage
flattering by exactly as much as it hides — and that percentage is what the
95%-per-file campaign is measured on. Audited 2026-11-08: **224 pragma sites, 103
within the rule, 121 outside it across 39 files**, concentrated in `diagnostics.py`
(21) and `core/manager.py` (20).

121 sites is not one commit's work, and it should not be: several are genuinely
unreachable handlers whose right answer is a recorded classification (the shape used
for `room_discovery.py`'s non-convergence arm and `switch.py`'s two) rather than a
pragma, and a few are real gaps. Which is which needs per-site judgement. This gate
exists so the total cannot grow while that judgement happens — the same reasoning,
and deliberately the same shape, as the W0 mock ratchet next door.

WHAT A PRAGMA ON A COMPOUND STATEMENT ACTUALLY DOES, since this is the part that
surprises. It suppresses the whole statement, not the line it sits on. Of the 189
pragmas on an `except` clause, **97 handlers contain no logger call at all** — mostly
`pass`, `continue`, and real returns like `return (entities, report)`. A pragma
written to skip one `_LOGGER.exception(...)` can be excluding control flow nobody
meant to waive. That is why the census classifies the BODY and not the comment.

⚠ THIS IS NOT A BAN, and it does not claim any one site is wrong. An
`except Exception:  # pragma: no cover` whose body is a log line and a `return None`
is the allowance in substance and is NOT counted. The 121 are the ones that carry
something else.

TO CHANGE THE ALLOWLIST
-----------------------
Lowering a number, or removing a file, needs nothing — the test simply passes.
Raising one requires deleting this test, which is deliberately harder than recording
the classification instead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO / "tests" / "pragma_allowlist.json"

sys.path.insert(0, str(REPO / "scripts"))
from pragma_census import census  # noqa: E402  (path shim above)


def _ceilings() -> dict[str, int]:
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))["ceilings"]


def test_pr1_no_new_file_waives_coverage_outside_the_rule():
    """[PR-1] A file NOT on the allowlist may have zero.

    This is the half that stops the bleeding. The debt is concentrated — two files
    hold 41 of the 121 — so a per-file ceiling lets those drain at their own pace
    while every other file in the package is held at zero. Without this half, a new
    pragma lands in a new file for every one that leaves an old one and the count
    never moves.

    THE INPUT THAT MAKES THIS RED: add `# pragma: no cover` to any `except` that
    carries real code, or to any non-logger line, in a file absent from
    `pragma_allowlist.json`.
    """
    counts = census()
    ceilings = _ceilings()
    new = {path: n for path, n in counts.items() if path not in ceilings}
    assert not new, (
        "these files waive coverage outside the logger-line rule and are not on the "
        "allowlist. Either put the reason in a recorded classification instead (see "
        "this module's docstring for the shape), or — if the site is genuinely a "
        "logger line — check why the census disagrees: " + json.dumps(new, indent=2)
    )


def test_pr2_no_listed_file_grows_its_waivers():
    """[PR-2] A file ON the allowlist may not exceed its ceiling.

    The direction of travel is down. A number that is too HIGH is not a failure —
    it just means the file improved and the ceiling can be lowered — so this asserts
    only the upper bound, and [PR-3] reports the slack separately rather than
    failing on it.

    THE INPUT THAT MAKES THIS RED: add one more non-compliant pragma to any listed
    file, e.g. a second `except Exception:  # pragma: no cover` with a `return` in
    its body.
    """
    counts = census()
    over = {
        path: {"ceiling": ceiling, "found": counts.get(path, 0)}
        for path, ceiling in _ceilings().items()
        if counts.get(path, 0) > ceiling
    }
    assert not over, (
        "coverage waivers grew in these files: " + json.dumps(over, indent=2)
    )


def test_pr3_the_allowlist_does_not_list_files_that_no_longer_need_it():
    """[PR-3] A ceiling that has gone slack is reported, not enforced.

    A stale ceiling is the failure mode a shrink-only gate invites: the number stays
    at its 2026-11-08 value, the file improves, and the gate quietly stops holding
    anything. So this names the slack. It does NOT fail — forcing the allowlist to be
    re-tightened in the same commit as an unrelated fix is how a gate becomes
    something people route around.

    It DOES fail on a file listed with a ceiling nothing can justify: a path that no
    longer exists, or one whose count is now zero, is dead weight that should simply
    be deleted from the file.
    """
    counts = census()
    ceilings = _ceilings()

    missing = [p for p in ceilings if not (REPO / p).is_file()]
    assert not missing, (
        "the allowlist names files that no longer exist; delete these rows: %s"
        % missing
    )
    drained = [p for p in ceilings if counts.get(p, 0) == 0]
    assert not drained, (
        "these files have no waivers left outside the rule — delete their rows so "
        "the gate holds them at zero: %s" % drained
    )

    slack = {
        p: {"ceiling": c, "found": counts.get(p, 0)}
        for p, c in ceilings.items()
        if counts.get(p, 0) < c
    }
    if slack:
        pytest.skip(
            "ceilings have slack and can be lowered (not a failure): "
            + json.dumps(slack, indent=2)
        )


def test_pr4_the_census_can_tell_the_two_shapes_apart():
    """[PR-4] The census's own discriminator, because a classifier that answered
    "non-compliant" for everything would make PR-1 and PR-2 pass for the wrong reason.

    Two synthetic handlers, identical but for their body: one logs and returns, one
    returns a real value. The first must NOT be counted and the second must be. This
    is the ablation PR-1/PR-2 cannot perform on themselves.
    """
    import ast

    from pragma_census import _handler_is_log_only

    def _handler(src: str):
        tree = ast.parse(src)
        return next(n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler))

    log_only = _handler(
        "try:\n    x()\nexcept Exception:\n    _LOGGER.exception('boom')\n    return None\n"
    )
    carries_code = _handler(
        "try:\n    x()\nexcept Exception:\n    _LOGGER.exception('boom')\n    return (a, b)\n"
    )
    silent = _handler("try:\n    x()\nexcept Exception:\n    pass\n")

    assert _handler_is_log_only(log_only) is True
    assert _handler_is_log_only(carries_code) is False, (
        "a handler returning a real value reads as log-only, so the census would "
        "excuse every pragma that hides a return"
    )
    assert _handler_is_log_only(silent) is False, (
        "a silent `except: pass` reads as log-only, which would excuse the single "
        "most common shape in the package"
    )

    # And the census finds a real, non-empty set — a classifier returning {} would
    # make PR-1 and PR-2 vacuous.
    counts = census()
    assert sum(counts.values()) > 50, (
        f"the census found only {sum(counts.values())} sites; it was 121 when this "
        f"gate was written, so either the package improved enormously or the "
        f"classifier stopped matching"
    )
