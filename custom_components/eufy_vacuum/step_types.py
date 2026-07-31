"""Step- and phase-type vocabulary for stepped runs — the questions, not just the sets.

This module exists because the same-looking tuple was hand-copied across eleven call
sites and drifted. On 2026-07-30 the SAME missing ``"zone"`` was found and fixed twice in
one day, on opposite sides of the stack: ``profiles.manager._enrich_saved_run_profile``'s
``has_stops`` gate (backend) and ``_deriveHasStops`` (card). A rooms->zone profile reported
itself as a flat queue in both.

**There are TWO vocabularies here, and they are NOT the same question.** Collapsing them
into one shared set would be worse than the duplication it replaces — it would break zone
handling outright. Read this before touching either:

``STEPPED_STEP_TYPES`` — "does this step make the run SEQUENCED rather than a flat queue?"
    charge_wait / wait / zone. A zone belongs: it is a distinct phase the run must stop
    and perform, so a rooms->zone plan is multi-phase.

``DOCK_POLLED_PHASE_TYPES`` — "is this phase driven by the DOCK POLLER?"
    charge_wait / wait only. A zone is a CLEAN phase: it dispatches ``dispatch_zone_clean``
    and completes via the room-group watchdog on the clean-complete signal, not by polling
    battery or a timer at the dock. **Adding "zone" here would mean a zone phase waits for
    a dock condition that never arrives, and the run would hang.**

The leading/trailing break-trim in ``planning.run_plan`` is deliberately the second set
too: dropping a leading *zone* would silently skip real cleaning work, whereas dropping a
leading charge/wait is a no-op. That narrowing is correct and intentional.

Prefer the helpers over the bare frozensets. The sets are the substrate; the helpers are
the question, and a caller that reaches for the set is one ``and`` clause away from
re-creating the drift this module removes.
"""

from __future__ import annotations

from typing import Any

#: Step types that make a run STEPPED (sequenced) rather than a flat queue.
#: Used by the "is this plan stepped?" gates and by the add_queue_break service schema.
STEPPED_STEP_TYPES: frozenset[str] = frozenset({"charge_wait", "wait", "zone"})

#: Phase types the DOCK POLLER drives (battery target / timer at the dock).
#: Deliberately EXCLUDES "zone" — see the module docstring.
DOCK_POLLED_PHASE_TYPES: frozenset[str] = frozenset({"charge_wait", "wait"})


def is_stepped_step_type(step_type: Any) -> bool:
    """Return whether a step TYPE makes the run stepped."""
    return str(step_type or "").strip().lower() in STEPPED_STEP_TYPES


def step_requires_stepped_execution(step: Any) -> bool:
    """Return whether a step dict makes the run stepped."""
    return isinstance(step, dict) and is_stepped_step_type(step.get("type"))


def plan_requires_stepped_execution(steps: Any) -> bool:
    """Return whether ANY step in a plan makes the run stepped.

    THE question the ``has_stops`` / stepped-path gates ask. Note the callers that also
    treat "more than one room_group" as stepped keep that clause locally — it is about
    plan SHAPE, not step type, so it does not belong in this vocabulary.
    """
    return isinstance(steps, list) and any(
        step_requires_stepped_execution(s) for s in steps
    )


def is_dock_polled_phase_type(phase_type: Any) -> bool:
    """Return whether a phase TYPE is driven by the dock poller (never "zone")."""
    return str(phase_type or "").strip().lower() in DOCK_POLLED_PHASE_TYPES


def is_dock_polled_phase(phase: Any) -> bool:
    """Return whether a phase dict is driven by the dock poller (never "zone")."""
    return isinstance(phase, dict) and is_dock_polled_phase_type(phase.get("phase_type"))
