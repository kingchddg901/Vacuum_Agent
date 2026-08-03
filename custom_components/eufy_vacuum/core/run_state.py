"""Brand-agnostic "is the robot cleaning right now?" reads.

Framework-level predicate over the vacuum entity's own state. Sibling of
``core/charging.py`` and written for the same reason: the question is generic
(HA's vacuum platform defines the state machine), only the *extra* strings a
brand may add are brand-specific, so the predicate belongs at framework level
with an adapter-declared extension point rather than in an adapter.

WHAT THIS IS FOR. ``_compute_current_room_elapsed_minutes`` measures a room's
elapsed time as wall time since ``current_room_started_at``. That stamp is made
at DISPATCH, and the robot is not cleaning for all of it — it undocks, it may
return mid-room for a mop wash or a recharge, and it drives back. Every one of
those seconds is currently charged to the room, inflating elapsed against the
timing-rollover threshold and, past enough of them, completing a room that was
never finished. This predicate marks the spans to subtract.

WHY NOT REUSE ``external_run._extract_return_overhead``'s set. That one asks a
deliberately WIDER question — post-hoc, over a whole finished external run, from
the recorder — and so it counts ``paused`` and ``idle`` as overhead too. Here
both are wrong: ``paused`` is already subtracted by
``current_room_paused_seconds`` (double-subtracting it would stall the room
forever), and a mid-run ``idle`` is a stall we must NOT hide from the rollover.
Same words, different question; the divergence is deliberate.
"""

from __future__ import annotations

from typing import Any

from ..adapters.registry import get_adapter_config

# HA-standard vacuum states in which the robot is demonstrably NOT cleaning the
# room it is currently assigned to. All three are part of the HA vacuum platform
# state machine, so they apply to every brand.
#
# Deliberately ABSENT, each for its own reason:
#   "paused"  -- already accounted by current_room_paused_seconds.
#   "idle"    -- a mid-run idle is a stall; subtracting it would hide the stall
#                from timing rollover instead of surfacing it.
#   "error"   -- ambiguous. A dock fault can fire while the robot is out on the
#                floor still cleaning (see vocabulary.py's fault-policy note),
#                so "error" is not evidence that cleaning stopped.
_NON_CLEANING_VACUUM_STATES: frozenset[str] = frozenset(
    {
        "docked",
        "returning",
        "returning_to_dock",
    }
)


def non_cleaning_vacuum_states(vacuum_entity_id: str | None = None) -> frozenset[str]:
    """Return the non-cleaning vacuum-state vocabulary for one vacuum.

    The HA-standard set above, plus anything the adapter declares in
    ``vocabulary.non_cleaning_vacuum_states``. The declaration is additive: a
    brand extends the standard states, it does not replace them, because the
    standard ones are part of the platform contract it already implements.

    No adapter declares this today — the seam exists so a brand with, say, a
    distinct "going to wash" vacuum state can subtract it without touching this
    module.
    """
    declared = (
        (get_adapter_config(vacuum_entity_id) or {})
        .get("vocabulary", {})
        .get("non_cleaning_vacuum_states")
        if vacuum_entity_id
        else None
    )
    if not isinstance(declared, (list, tuple, set, frozenset)):
        return _NON_CLEANING_VACUUM_STATES

    extra = {str(value).strip().lower() for value in declared if str(value).strip()}
    return _NON_CLEANING_VACUUM_STATES | extra


def is_non_cleaning_vacuum_state(
    state: Any,
    *,
    vacuum_entity_id: str | None = None,
) -> bool:
    """Return True only when the state DEFINITELY says the robot is not cleaning.

    FAILS OPEN, and the direction matters. ``unknown`` / ``unavailable`` / ``""``
    / any unrecognised string all return False — "not definitely non-cleaning" —
    which subtracts nothing and leaves the room clock running exactly as it did
    before this accumulator existed.

    That asymmetry is deliberate. This predicate only ever REMOVES time from a
    room's elapsed measurement, so a false True is unbounded (a dropout that
    never resolves subtracts forever, the threshold is never reached, and the
    room never advances — the stall 40cbaac was landed to fix), whereas a false
    False is bounded (one span of transit time stays charged to the room, which
    is exactly today's behaviour). Bounded over-measurement beats an unbounded
    stall, so an unreadable state must never open a subtraction window.
    """
    normalized = str(state or "").strip().lower()
    if not normalized:
        return False
    return normalized in non_cleaning_vacuum_states(vacuum_entity_id)
