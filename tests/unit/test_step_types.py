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

Coverage (CV = Capture Validity, RP-013a) — a THIRD question, not the two above:
  [CV-1] a cleaning (room_group) phase with empty room_timing is a capture failure
  [CV-2] a non-cleaning phase (charge_wait/wait/zone) with empty room_timing is VALID-EMPTY
  [CV-3] a cleaning phase WITH room_timing is valid regardless of the emptiness rule
  [CV-4] malformed input is falsy rather than raising
"""

from __future__ import annotations

from custom_components.eufy_vacuum.step_types import (
    CLEANING_PHASE_TYPES,
    DOCK_POLLED_PHASE_TYPES,
    NON_CLEANING_PHASE_TYPES,
    STEPPED_STEP_TYPES,
    is_cleaning_phase_type,
    is_dock_polled_phase,
    is_dock_polled_phase_type,
    is_stepped_step_type,
    phase_capture_is_valid,
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


def test_cleaning_phase_empty_timing_is_capture_failure():
    """[CV-1] The reader's actual bug: room_timing=[] on a CLEANING (room_group)
    phase means the segmenter found nothing for a phase that should have
    cleaned something -- that IS a capture failure."""
    assert is_cleaning_phase_type("room_group") is True
    assert phase_capture_is_valid({"phase_type": "room_group", "room_timing": []}) is False
    assert phase_capture_is_valid({"phase_type": "room_group"}) is False  # missing entirely


def test_non_cleaning_phase_empty_timing_is_valid():
    """[CV-2] charge_wait/wait/zone deliberately write room_timing=[]
    (phase_runner._capture_finishing_phase_timing's own doc). Reading that as
    a failure flagged EVERY stepped run transit_capture_valid=False."""
    for phase_type in ("charge_wait", "wait", "zone"):
        assert is_cleaning_phase_type(phase_type) is False
        assert phase_capture_is_valid({"phase_type": phase_type, "room_timing": []}) is True


def test_cleaning_phase_with_timing_is_valid():
    """[CV-3] The ordinary case, unaffected by the emptiness rule."""
    assert phase_capture_is_valid(
        {"phase_type": "room_group", "room_timing": [{"room_id": 1, "cleaning_seconds": 90}]}
    ) is True


def test_capture_validity_malformed_input_is_falsy():
    """[CV-4]"""
    assert phase_capture_is_valid(None) is False
    assert phase_capture_is_valid("not a dict") is False
    assert is_cleaning_phase_type(None) is False
    assert is_cleaning_phase_type("") is False


def test_cleaning_and_non_cleaning_sets_partition_known_phase_types():
    """CLEANING_PHASE_TYPES and NON_CLEANING_PHASE_TYPES are disjoint and,
    together, cover every phase_type this repo actually emits. If a new phase
    type is ever added, one of these sets must be updated explicitly -- this
    guard fails rather than silently defaulting the new type to either side."""
    assert CLEANING_PHASE_TYPES.isdisjoint(NON_CLEANING_PHASE_TYPES)
    assert CLEANING_PHASE_TYPES | NON_CLEANING_PHASE_TYPES == {
        "room_group", "charge_wait", "wait", "zone",
    }


# ---------------------------------------------------------------------------
# Shared blank-state vocabulary — the OTHER Group F promotion.
#   [BS-1] both leak forms are blank ("None" from Python, "null" from JSON)
#   [BS-2] a real None is blank without the caller stringifying
#   [BS-3] a genuine value is NOT blank — including values that merely contain a sentinel
#   [BS-4] the derived named constants stay in lockstep with the shared set
# ---------------------------------------------------------------------------

from custom_components.eufy_vacuum.entity_helpers import (  # noqa: E402
    BLANK_STATE_VALUES,
    is_blank_state,
)


def test_both_absent_leak_forms_are_blank():
    """[BS-1] The six hand-copied variants each caught only the leak form their own
    producer emitted: "None" (Python str(None)) or "null" (JSON). Both now count."""
    for raw in ("", "unknown", "unavailable", "none", "None", "null", "NULL", "  Unknown  "):
        assert is_blank_state(raw) is True, f"{raw!r} should read as blank"


def test_a_real_none_is_blank():
    """[BS-2]"""
    assert is_blank_state(None) is True


def test_a_genuine_value_is_not_blank():
    """[BS-3] Substring matching is a forbidden pattern in this repo — 'Nonesuch' and
    'Unknown Room' are real values, not sentinels."""
    for raw in ("Kitchen", "1", "Nonesuch", "Unknown Room", "0", 0, 1):
        assert is_blank_state(raw) is False, f"{raw!r} should be a usable value"


def test_derived_constants_stay_in_lockstep():
    """[BS-4] room_discovery and mapping/tracker keep NAMED constants (diagnostics imports
    one), but they are now DERIVED. If someone re-lists members locally, this fails."""
    from custom_components.eufy_vacuum.rooms.room_discovery import _ACTIVE_MAP_SENTINELS
    from custom_components.eufy_vacuum.mapping.tracker import _BLANK_ROOM_SENTINELS

    assert _ACTIVE_MAP_SENTINELS is BLANK_STATE_VALUES
    assert _BLANK_ROOM_SENTINELS is BLANK_STATE_VALUES
