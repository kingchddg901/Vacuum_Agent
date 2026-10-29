"""Every reason the pre-job estimate panel can show must have a card key.

The panel's resolver path was already right: `renderers/learning.js` keeps the machine code,
`resolveCodedLabel` tries ``learning.estimate_error.<code>``, and the backend's `message` is
the last-resort fallback so a code a card release has never heard of still reads.

WHAT WAS WRONG was which FIELD the renderer read. Its branch is entered by
``estimate.error || estimate.available === false``, and the three codes that arrive on the
second path are carried by ``reason``, not ``error`` — so `code` was undefined for all of
them, and `coded-label.js` ranks `message` above `genericKey`, so the backend's English
sentence rendered in all 17 packs. 2.5.3 added a key to this family for ``estimate_failed``,
which is emitted PER ROOM and cannot reach this panel at all; that key's presence is why the
sink read as covered.

WHY THE SET IS DERIVED FROM THE SOURCE, NOT LISTED HERE. `get_planned_job_estimate` needs a
live hass, so it cannot be executed the way [BRK-1] executes the start-blocker ladder. It is
sliced from its own `def` and walked as an AST rather than grepped, because the third of its
three codes is the literal DEFAULT inside
``str(estimate.get("reason", "estimate_unavailable"))`` — a shape a `"reason": "..."` pattern
does not match. The equivalent miss has already happened once in this repo: the census's list
of the start-blocker codes was missing ``blocked``, the default of
``preflight.get("reason", "blocked")``.

Coverage targets
----------------
[ERK-1] every reason `get_planned_job_estimate` can emit has a key (``ready`` excepted —
        that is the AVAILABLE case and renders a figure, not a sentence).
[ERK-2] the mutation control: a reason with no key is reported.
[ERK-3] the inner estimator declares no `reason` of its own — which is WHAT MAKES the
        default the whole set. If it ever declares one, this fails so someone re-enumerates.
[ERK-4] the estimator's `error` values, and that ``no_payload`` is deliberately NOT in this
        family: it has its own actionable sentence.
[ERK-5] ``estimate_failed`` is kept although this producer cannot emit it, and its presence
        must not be read as covering the panel.
[ERK-6] ``estimate_unavailable`` is PREPARED, not a fixed defect. Its literal is real, which
        is why [ERK-1] requires a key for it — but no path reaches it today, and I described
        it as a third live defect on the strength of the literal alone. Enumerating a
        producer's literals is not the same as establishing reachability; conflating the two
        is exactly what made ``estimate_failed`` look like coverage. This pins each clause of
        the unreachability argument so the key going live is visible rather than silent.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import re
import textwrap

from custom_components.eufy_vacuum.core import manager as core_manager
from custom_components.eufy_vacuum.learning import estimator as learning_estimator

REPO = pathlib.Path(__file__).resolve().parents[2]
EN_JS = REPO / "src" / "i18n" / "en.js"
PREFIX = "learning.estimate_error."

#: `ready` is the available case: the panel renders the estimate, not an explanation.
NOT_AN_EXPLANATION = {"ready"}


def en_keys() -> set[str]:
    """Every key defined in the English source."""
    return set(re.findall(r'^\s*"([A-Za-z0-9_.\-]+)"\s*:', EN_JS.read_text(encoding="utf-8"), re.M))


def _reasons_in(func) -> set[str]:
    """Every string a `reason` can take inside one function, by AST.

    Two shapes, and the second is the one a regex over `"reason": "..."` misses:
      * a dict literal's ``"reason"`` value;
      * the default of a ``.get("reason", <literal>)`` call.
    A conditional expression is descended into, so `"a" if x else "b"` yields both.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    found: set[str] = set()

    def literals(node) -> set[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.IfExp):
            return literals(node.body) | literals(node.orelse)
        if isinstance(node, ast.Call):           # str(...) / .get(...) wrappers
            # A `.get(<key>, <default>)` contributes only its DEFAULT. Collecting every
            # argument also harvested the KEY NAME, so the walk reported "reason" itself as
            # a code and demanded a `learning.estimate_error.reason` key — caught by running
            # it, which is the whole argument for [ERK-2] existing as a control.
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get" \
                    and len(node.args) == 2:
                return literals(node.args[1])
            out: set[str] = set()
            for a in node.args:
                out |= literals(a)
            return out
        return set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "reason":
                    found |= literals(v)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and len(node.args) == 2 \
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "reason":
            found |= literals(node.args[1])
    return found


def _errors_in(func) -> set[str]:
    """Every string an `error` key can take inside one function."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "error" \
                        and isinstance(v, ast.Constant) and isinstance(v.value, str):
                    found.add(v.value)
    return found


def unkeyed(codes: set[str], keys: set[str]) -> list[str]:
    return sorted(c for c in codes if f"{PREFIX}{c}" not in keys)


def test_erk_1_every_panel_reason_has_a_key() -> None:
    """[ERK-1]"""
    reasons = _reasons_in(core_manager.EufyVacuumManager.get_planned_job_estimate)
    explanations = reasons - NOT_AN_EXPLANATION

    # Not vacuous, both ways: the walk found the codes, and it found the one hiding in the
    # `.get` default. Without these a broken slice or a changed shape passes everything.
    assert len(explanations) >= 3, (
        f"only {len(explanations)} explanation reason(s) found in get_planned_job_estimate "
        f"({sorted(reasons)}) — the slice or the AST walk is wrong, and an empty scan "
        "passes everything"
    )
    assert "estimate_unavailable" in explanations, (
        "the literal default of `.get(\"reason\", \"estimate_unavailable\")` was not found — "
        "that is the shape a `\"reason\": \"...\"` pattern misses, and the reason this "
        "walks the AST"
    )
    assert "ready" in reasons, "the available case vanished; NOT_AN_EXPLANATION is now stale"

    missing = unkeyed(explanations, en_keys())
    assert not missing, (
        "the estimate panel can show these with no card key, so they render the backend's "
        "English in every pack:\n  " + "\n  ".join(f"{PREFIX}{c}" for c in missing)
    )


def test_erk_2_an_unkeyed_reason_is_reported() -> None:
    """[ERK-2] the mutation control for [ERK-1]'s detector."""
    keys = en_keys()
    assert unkeyed({"thermal_throttled"}, keys) == ["thermal_throttled"]
    # And a real one is NOT reported, or the check above would flag everything.
    assert unkeyed({"learning_unavailable"}, keys) == []


def test_erk_3_the_inner_estimator_declares_no_reason() -> None:
    """[ERK-3] why the default is the whole set, rather than an open one.

    `get_planned_job_estimate` passes through `str(estimate.get("reason", ...))`, so if the
    estimator ever returns a `reason`, the panel gains codes that are invisible to [ERK-1]
    — it slices the manager, not the estimator. This is the tripwire for that.
    """
    source = inspect.getsource(learning_estimator)
    assert '"reason"' not in source, (
        "learning/estimator.py now mentions a `reason` key. If it RETURNS one, that value "
        "reaches the estimate panel through get_planned_job_estimate's "
        "`estimate.get(\"reason\", ...)` and needs a "
        f"{PREFIX}<code> key — re-enumerate the set and extend [ERK-1] to cover this module."
    )


def test_erk_4_the_estimator_errors_and_the_no_payload_exception() -> None:
    """[ERK-4]"""
    # Found by FUNCTION NAME, whatever owns it — the class name is not the contract, and
    # `estimate_from_manager` is only a one-line wrapper around this.
    tree = ast.parse(inspect.getsource(learning_estimator))
    fns = [n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "estimate"]
    assert len(fns) == 1, (
        f"expected exactly one `def estimate` in learning/estimator.py, found {len(fns)} — "
        "resolve which one the manager calls before trusting this set"
    )
    errors: set[str] = set()
    for sub in ast.walk(fns[0]):
        if isinstance(sub, ast.Dict):
            for k, v in zip(sub.keys, sub.values):
                if isinstance(k, ast.Constant) and k.value == "error" \
                        and isinstance(v, ast.Constant) and isinstance(v.value, str):
                    errors.add(v.value)
    assert errors == {"no_payload"}, (
        f"the estimator's error set changed to {sorted(errors)}. Each of these passes "
        "straight through get_planned_job_estimate's `**estimate` spread and lands on the "
        f"panel as `estimate.error`, so anything new needs a {PREFIX}<code> key."
    )
    # `no_payload` is deliberately NOT in the family: it has its own actionable sentence
    # ("queue rooms first"), which a generic failure cannot offer.
    keys = en_keys()
    assert f"{PREFIX}no_payload" not in keys, (
        "no_payload must keep learning.estimate_queue_first rather than joining this "
        "family — it is the one case with something for the user to DO"
    )
    assert "learning.estimate_queue_first" in keys


def test_erk_5_estimate_failed_is_kept_but_proves_nothing() -> None:
    """[ERK-5] the key whose presence made this sink look covered.

    `estimate_failed` is emitted per ROOM by learning/manager.py's `room_entries` loop, and
    no surface renders those entries yet. It is kept as the seam for when one does — but it
    is NOT evidence that the panel's own codes are keyed, which is exactly how it was read.
    """
    keys = en_keys()
    assert f"{PREFIX}estimate_failed" in keys

    manager_source = (REPO / "custom_components" / "eufy_vacuum" / "learning" / "manager.py").read_text(encoding="utf-8")
    assert '"error": "estimate_failed"' in manager_source, (
        "estimate_failed no longer has a producer anywhere — if the per-room loop is gone, "
        "decide whether the key goes with it rather than leaving a key for nothing"
    )
    # And the panel's own producer cannot emit it, which is the whole point.
    assert "estimate_failed" not in _reasons_in(core_manager.EufyVacuumManager.get_planned_job_estimate)
    assert "estimate_failed" not in _errors_in(core_manager.EufyVacuumManager.get_planned_job_estimate)


def test_erk_6_estimate_unavailable_is_prepared_not_live() -> None:
    """[ERK-6] the reachability half, which enumerating the literals does not give you.

    ``estimate_unavailable`` is a real literal in `get_planned_job_estimate` — [ERK-1]
    requires a key for it and should. But no path reaches it today, and the key was briefly
    described as a third fixed defect on the strength of the literal alone. That is the same
    conflation that made ``estimate_failed`` look like coverage, so it gets a gate rather
    than a comment.

    The argument, which this pins so it cannot rot silently:
      * `available = can_run_now or has_zone_time`, and the manager reads
        ``bool(estimate.get("can_run_now", False))``;
      * EVERY return of `estimator.estimate` sets `can_run_now`, so that default never fires;
      * the only return that sets it False also carries ``error: "no_payload"``;
      * and the panel short-circuits `no_payload` to its own actionable sentence BEFORE the
        resolver, so `reason` is never consulted on that path.

    If any clause stops holding, the key becomes live and this fails — which is the useful
    moment to know, because the sentence is then being shown to someone.
    """
    tree = ast.parse(inspect.getsource(learning_estimator))
    fns = [n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "estimate"]
    assert len(fns) == 1

    returns = [n for n in ast.walk(fns[0]) if isinstance(n, ast.Return)]
    dict_returns = [r for r in returns if isinstance(r.value, ast.Dict)]
    assert len(dict_returns) == len(returns) >= 2, (
        f"`estimator.estimate` has {len(returns)} return(s), {len(dict_returns)} of them dict "
        "literals — a non-literal return cannot be read here, so re-establish by hand whether "
        "`can_run_now` is always set before trusting this gate"
    )

    for r in dict_returns:
        keys = {k.value for k, _ in zip(r.value.keys, r.value.values)
                if isinstance(k, ast.Constant)}
        assert "can_run_now" in keys, (
            f"the return at line {r.lineno} does not set `can_run_now`, so the manager's "
            "`.get(\"can_run_now\", False)` now defaults to False — `available` can be false "
            "with no error, and learning.estimate_error.estimate_unavailable IS NOW LIVE. "
            "Check it reads well and say so in en.js."
        )
        false_can_run = any(
            isinstance(k, ast.Constant) and k.value == "can_run_now"
            and isinstance(v, ast.Constant) and v.value is False
            for k, v in zip(r.value.keys, r.value.values)
        )
        if false_can_run:
            errors = {v.value for k, v in zip(r.value.keys, r.value.values)
                      if isinstance(k, ast.Constant) and k.value == "error"
                      and isinstance(v, ast.Constant)}
            assert errors == {"no_payload"}, (
                f"the return at line {r.lineno} sets can_run_now False with error={errors or 'none'}. "
                "Anything other than exactly no_payload reaches the panel with `available` false "
                "and no short-circuit, so learning.estimate_error.estimate_unavailable IS NOW LIVE."
            )

    # The short-circuit itself, which is the last clause of the argument.
    renderer = (REPO / "src" / "renderers" / "learning.js").read_text(encoding="utf-8")
    assert 'estimate.error === "no_payload"' in renderer, (
        "the renderer no longer short-circuits no_payload before the resolver — that path now "
        "reaches `reason`, so estimate_unavailable is live"
    )
