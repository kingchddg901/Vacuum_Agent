"""Step- and phase-type vocabulary for stepped runs — the questions, not just the sets.

This module exists because the same-looking tuple was hand-copied across eleven call
sites and drifted. On 2026-07-30 the SAME missing ``"zone"`` was found and fixed twice in
one day, on opposite sides of the stack: ``profiles.manager._enrich_saved_run_profile``'s
``has_stops`` gate (backend) and ``_deriveHasStops`` (card). A rooms->zone profile reported
itself as a flat queue in both.

# REPLICA RN9N6NVB -- the sequenced-vs-flat QUESTION is answered by the backend's
# has_stops gate and the card's _deriveHasStops. The two vocabularies BELOW are a
# different matter and must NOT be merged; read the block.
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


#: RP-013a — a THIRD vocabulary, and again not the same question as the two
#: above. STEPPED_STEP_TYPES asks "does this step make the plan sequenced?"
#: (build time); DOCK_POLLED_PHASE_TYPES asks "who drives this phase's
#: completion?" (dispatch time). This asks a CAPTURE-READ-time question: "does
#: this phase type produce per-room room_timing when properly captured?" Only
#: room_group does — charge_wait/wait (dock-polled) and zone (captured into
#: zone_timing instead) all deliberately write room_timing=[] on purpose
#: (phase_runner._capture_finishing_phase_timing). The membership happens to
#: match DOCK_POLLED_PHASE_TYPES + {"zone"} today; that is a coincidence of
#: what exists, not a reason to derive one set from another — a future phase
#: type could answer these two questions differently.
#: The phase type a plain dispatch phase is stamped with. Named so the stamp in
#: run_plan._build_dispatch_phases and the membership set below cannot drift apart —
#: they were silently inconsistent until 2026-08-02, when no dispatch phase carried a
#: type at all.
CLEANING_PHASE_TYPE = "room_group"

CLEANING_PHASE_TYPES: frozenset[str] = frozenset({CLEANING_PHASE_TYPE})

#: Phase types where an EMPTY room_timing is VALID-EMPTY, not a capture
#: failure — the deliberate complement of CLEANING_PHASE_TYPES over today's
#: known phase types.
NON_CLEANING_PHASE_TYPES: frozenset[str] = frozenset({"charge_wait", "wait", "zone"})


def is_cleaning_phase_type(phase_type: Any) -> bool:
    """Return whether a phase TYPE is expected to produce per-room room_timing."""
    return str(phase_type or "").strip().lower() in CLEANING_PHASE_TYPES


def phase_capture_is_valid(phase: Any) -> bool:
    """Return whether a phase's room_timing correctly reflects its capture,
    whether empty or not.

    A non-cleaning phase (charge_wait/wait/zone) intentionally writes
    room_timing=[] — that is VALID-EMPTY, not a capture failure (RP-013a).
    A CLEANING phase (room_group) with empty/missing room_timing IS the
    capture failure: the segmenter found nothing for a phase that should
    have cleaned something.
    """
    if not isinstance(phase, dict):
        return False
    raw = phase.get("phase_type")
    if raw in (None, ""):
        # ABSENT means "a plain dispatch phase" — only breaks and zones declare a type.
        # Treating absent as non-cleaning made this gate FAIL OPEN: a cleaning phase whose
        # segmenter found nothing was judged valid-empty and transit_capture_valid stayed
        # True, so a total capture failure taught as a clean run. Absent now falls to the
        # cleaning branch, which is also the safe direction for a future phase type that
        # forgets to stamp one: it gets scrutinised rather than waved through.
        return bool(phase.get("room_timing"))
    if not is_cleaning_phase_type(raw):
        return True
    return bool(phase.get("room_timing"))
