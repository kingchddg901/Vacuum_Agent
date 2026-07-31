"""Step/phase vocabulary — the two questions must stay DIFFERENT.

The same-looking tuple was hand-copied to eleven call sites and drifted: on 2026-07-30 the
identical missing "zone" was found and fixed twice in one day, backend and card. Promoting
it to helpers removes the copies — but the real risk now is the opposite mistake:
"tidying" the two sets into one.

They are not the same question. A zone makes a run STEPPED (it is a phase the run must stop
and perform) but is NOT dock-polled (it dispatches a clean and completes on the
clean-complete signal, not by polling battery or a timer at the dock). Adding "zone" to the
dock-polled set would make a zone phase wait for a dock condition that never arrives — the
run would hang mid-clean.

Coverage (ST = Step Types):
  [ST-1] a zone makes a plan stepped
  [ST-2] a zone is NOT dock-polled — the distinction that must never be "tidied" away
  [ST-3] the two sets differ by exactly "zone", deliberately
  [ST-4] plan_requires_stepped_execution ignores plan SHAPE (room_group count)
  [ST-5] malformed input is falsy rather than raising
"""

from __future__ import annotations

from custom_components.eufy_vacuum.step_types import (
    DOCK_POLLED_PHASE_TYPES,
    STEPPED_STEP_TYPES,
    is_dock_polled_phase,
    is_dock_polled_phase_type,
    is_stepped_step_type,
    plan_requires_stepped_execution,
    step_requires_stepped_execution,
)


def test_zone_makes_a_plan_stepped():
    """[ST-1] The omission that shipped twice: a rooms->zone plan is SEQUENCED."""
    assert is_stepped_step_type("zone") is True
    assert step_requires_stepped_execution({"type": "zone", "zone_ids": ["z1"]}) is True
    assert plan_requires_stepped_execution(
        [{"type": "room_group"}, {"type": "zone", "zone_ids": ["z1"]}]
    ) is True


def test_zone_is_not_dock_polled():
    """[ST-2] THE distinction. A zone completes on the clean-complete signal via the room
    watchdog; it does not wait at the dock. Treating it as dock-polled hangs the run."""
    assert is_dock_polled_phase_type("zone") is False
    assert is_dock_polled_phase({"phase_type": "zone"}) is False
    assert is_dock_polled_phase_type("charge_wait") is True
    assert is_dock_polled_phase_type("wait") is True


def test_the_two_sets_differ_by_exactly_zone():
    """[ST-3] Guards against a future 'tidy-up' that unifies them. If this fails, read the
    module docstring before changing the assertion."""
    assert STEPPED_STEP_TYPES - DOCK_POLLED_PHASE_TYPES == {"zone"}
    assert DOCK_POLLED_PHASE_TYPES - STEPPED_STEP_TYPES == set()


def test_plan_gate_ignores_plan_shape():
    """[ST-4] The >1-room_group clause is about plan SHAPE, not step type, so callers keep
    it locally — this vocabulary must not absorb it."""
    assert plan_requires_stepped_execution([{"type": "room_group"}, {"type": "room_group"}]) is False
    assert plan_requires_stepped_execution([{"type": "room_group"}]) is False


def test_malformed_input_is_falsy():
    """[ST-5]"""
    assert is_stepped_step_type(None) is False
    assert is_stepped_step_type("") is False
    assert step_requires_stepped_execution("not a dict") is False
    assert step_requires_stepped_execution({}) is False
    assert plan_requires_stepped_execution(None) is False
    assert is_dock_polled_phase(None) is False
    # case/whitespace tolerance, matching the old str().strip().lower() call sites
    assert is_dock_polled_phase_type(" Charge_Wait ") is True
