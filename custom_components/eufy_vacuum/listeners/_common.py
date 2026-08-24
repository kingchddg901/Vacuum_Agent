"""Shared helpers used across listener modules.

These helpers were previously module-level functions in __init__.py.
They are pure adapter-registry lookups and small data shapes — no
HA wiring of their own — so they live in a private _common module
that every listener can import from.

Public surface:

- get_adapter_vocab(vacuum_entity_id, section, key, fallback) -> frozenset[str]
- get_adapter_value(vacuum_entity_id, *path, fallback) -> Any
- is_dock_trigger_edge(old_state_value, new_state_value, trigger_vocabulary) -> bool
- get_lifecycle_watch_entities(vacuum_entity_id) -> list[str]
- is_job_active(hass, vacuum_entity_id, *, unavailable_is_active=False) -> bool
- completed_finalize_signals(hass, vacuum_entity_id) -> dict[str, Any]
    ⚠ NOT dict[str, str], which this list claimed until 2026-08-24 (L22).
    The returned mapping is NOT homogeneous: four keys hold the lowercased
    state string, but ``job_active_present`` holds a bool (a PRESENCE test,
    added with the issue #51 fix). A caller trusting the old signature would
    treat it as a string — and ``"False"`` is truthy, so a str()-shaped guard
    written against it inverts the very presence check it guards. The other
    eight entries in this list do match their functions.
- completion_secondary_satisfied(vacuum_entity_id, completion_signals, clear_sentinels) -> bool
- job_finished_event_data(*, vacuum_entity_id, map_id, finalize_result) -> dict
- run_incomplete_event_data(*, vacuum_entity_id, finalize_result) -> dict | None
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INYA5T84  `adapters/config_schema.py#INYA5T84`
#       A3-COMMON-2 (closed RP-033): completion_secondary_satisfied() returns True from a config FLAG without verifying
#              the entity it delegates to exists; the "Invariant" asserted in the caller is never
#   IN6VSBJ1  `jobs/active_job.py#IN6VSBJ1`
#       A3-COMMON-4: _common owns the completion QUESTION but not its vocabulary defaults — the clear-
#              sentinel and completion-status fallbacks exist as two hand-copied literals in
#              different modules
#       A3-COMMON-6: The listener layer never uses either canonical in-flight predicate — it hand-inlines
#              the status set that dispatched_job_is_in_flight declares itself "THE single answer"
#              to


from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config
from ..adapters.registry import get_adapter_value as _registry_get_adapter_value


def get_adapter_vocab(
    vacuum_entity_id: str,
    section: str,
    key: str,
    fallback: frozenset[str],
) -> frozenset[str]:
    """Read a vocabulary set from the adapter registry with fallback.

    Returns the registry value as a frozenset if present, otherwise
    returns the fallback. Never raises.
    """
    try:
        config = get_adapter_config(vacuum_entity_id)
        if config is None:
            return fallback
        value = config.get(section, {}).get(key)
        if isinstance(value, (list, set, frozenset)):
            return frozenset(str(v).strip().lower() for v in value)
        return fallback
    except Exception:
        return fallback


def get_adapter_value(
    vacuum_entity_id: str,
    *path: str,
    fallback: Any,
) -> Any:
    """Read any scalar value from the adapter registry with fallback.

    ``path`` is a sequence of dict keys to traverse.
    Returns fallback if registry is absent, path is missing, or any
    error occurs.

    COMMON-5: delegates to adapters/registry.py's own get_adapter_value
    instead of a second, independent implementation of the identical
    lookup -- a fix or semantic change there (e.g. distinguishing a
    declared null from an absent key) now reaches every listener that
    routes through this module.
    """
    try:
        return _registry_get_adapter_value(vacuum_entity_id, *path, fallback=fallback)
    except Exception:
        return fallback


def is_dock_trigger_edge(
    old_state_value: str | None,
    new_state_value: str | None,
    trigger_vocabulary: frozenset[str] | set[str],
) -> bool:
    # anchor: IN96V4SA  an edge needs a KNOWN prior; arrival is not a transition
    """Whether a dock_status transition is a genuine edge INTO a trigger state.

    RP-038 (RF-30) / LIFE-3: the shared edge test both dock_events.py's
    _handle_dock_event and lifecycle.py's inline mop-wash detector delegate
    to, so there is exactly one definition of "is this actually a dock event"
    instead of two independently-drifting ones.

    Three refusals, checked in order — any one of them means "not an edge":

      1. ``new_state_value`` is ``None`` (no current reading at all).
      2. ``old_state_value`` is not a real, previously-known value: missing
         entirely (``None`` — e.g. HA restart, or genuinely the first-ever
         sighting) or currently ``unavailable``/``unknown``. We don't know
         what the device was actually doing before, so a fresh sighting
         after a restart or a reconnect must not be recorded as a brand-new
         dock cycle (REG-1/GUARD-3).
      3. ``old_state_value`` normalizes to the same value as
         ``new_state_value`` (plain dedup) — not a transition at all.

    Otherwise: an edge if and only if the normalized ``new_state_value`` is
    in ``trigger_vocabulary``. Values are compared case-insensitively after
    stripping, matching both callers' existing normalization.
    """
    if new_state_value is None:
        return False
    new_val = str(new_state_value).strip().lower()
    old_val = (
        str(old_state_value).strip().lower() if old_state_value is not None else ""
    )
    if old_val in ("", "unavailable", "unknown"):
        return False
    if new_val == old_val:
        return False
    return new_val in trigger_vocabulary


def get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]:
    """Return entity IDs to watch for lifecycle state changes.

    Reads from the adapter registry — always includes the vacuum entity
    itself plus all declared entities whose state changes drive lifecycle
    re-evaluation. Returns only the vacuum entity when no adapter is
    registered, which is still safe (lifecycle functions then read empty
    entity states and produce no-op results).

    No brand-specific entity naming — all entity IDs come from the
    adapter's registered config.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entities = config.get("entities", {})
    watch: list[str] = [vacuum_entity_id]
    # job_active is the recharge-resume signal (a binary sensor that stays on
    # through a mid-job recharge dock); watching it ensures its clear at the true
    # finish re-triggers finalization. Absent for brands that don't declare it.
    for key in (
        "task_status",
        "dock_status",
        "active_cleaning_target",
        "active_map",
        "job_active",
    ):
        entity_id = entities.get(key)
        if entity_id:
            watch.append(entity_id)
    return watch


# INFJXSM4 enforced at `listeners/path_blockers.py#INFJXSM4` — the keyword below IS the
# rule: an unreadable signal is indeterminate, so the CALLER declares what that means here
# (detection and finalization want opposite answers) rather than this helper collapsing it.
def is_job_active(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    *,
    unavailable_is_active: bool = False,
) -> bool:
    """True if the adapter declares a job-active signal and it is currently on.

    ``entities.job_active`` is a binary sensor that stays ON for the whole
    logical job — INCLUDING a mid-job recharge dock where the device reports
    ``task_status=charging`` and will resume. The completion gate uses this to
    avoid finalizing during a recharge. Brands that don't declare
    ``entities.job_active`` always return False, so the guard is a no-op for them
    (e.g. Eufy).

    ``unavailable_is_active`` (the recharge-guard caller passes True): when the
    binary EXISTS but momentarily reads ``unavailable``/``unknown`` — a transient
    cloud/connection blip — treat it as still ACTIVE. Otherwise a blip during a
    mid-recharge dock lets the completion gate finalize the job early and record a
    truncated learning sample; the true finish still drives it cleanly to ``off``.
    The has_observed arming gate leaves this False (strict ``on``) so an
    indeterminate binary at start can't arm the flag.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entity_id = config.get("entities", {}).get("job_active")
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    if state is None:
        return False
    raw = str(state.state).strip().lower()
    if unavailable_is_active and raw in ("unavailable", "unknown"):
        return True
    return raw == "on"


def completed_finalize_signals(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Return current entity states used for completion detection.

    Reads entity IDs from the adapter registry. Returns the lowercased, stripped
    state of each entity, and ``""`` ONLY when there is no state object to read:
    an undeclared entity key, an entity id that resolves to nothing, or a state
    of ``None``.

    ⚠ AN ENTITY THAT EXISTS AND READS ``unavailable`` RETURNS ``"unavailable"``,
    NOT ``""`` — and this docstring claimed the opposite until 2026-08-24 (L10).
    It said "returns empty strings for absent OR UNAVAILABLE entities", which is
    true of the absent half only. The distinction matters because the sentence
    right after it names the caller's contract: callers compare these values
    against configured sentinels, and a caller that believed the collapse had
    already happened would not think to put ``"unavailable"`` in its sentinel set.

    Both shipped completion paths happen to be safe, and it is worth knowing WHY
    rather than assuming the shape is fine:

      * Eufy declares ``secondary_clear_sentinels`` as
        ``["", "unknown", "unavailable", "none", "null"]`` — it lists the
        indeterminate values explicitly, so ``active_target`` reading
        ``unavailable`` is treated as cleared BY DECLARATION, not by this helper.
      * ``job_active_present`` is the one place the collapse was actually being
        relied on, and it was not happening. See its comment below.

    A new caller does not inherit that luck. Compare against a sentinel set that
    names the indeterminate values, or test them yourself.

    No brand-specific entity naming — all entity IDs come from the
    adapter's registered config.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entities = config.get("entities", {})

    def _state(entity_id: str | None) -> str:
        if not entity_id:
            return ""
        state_obj = hass.states.get(entity_id)
        if state_obj is None or state_obj.state is None:
            return ""
        return str(state_obj.state).strip().lower()

    return {
        "vacuum_state": _state(vacuum_entity_id),
        "task_status": _state(entities.get("task_status")),
        "dock_status": _state(entities.get("dock_status")),
        "active_target": _state(entities.get("active_cleaning_target")),
        # PRESENCE, not value. `completion_secondary_satisfied` used to accept a
        # DECLARED job_active key as proof the signal existed; on a localized install
        # the declared id resolves to nothing and the gate reported "satisfied" about
        # an entity that was not there (issue #51).
        #
        # ⚠ THIRD TIME THIS GATE STOPPED ONE STEP SHORT (L9). RP-033/COMMON-2
        # tightened "flag set" to "entity declared"; issue #51 tightened that to
        # "entity resolves"; and this line then claimed "an entity that is absent or
        # UNAVAILABLE reads '' above, so this is False exactly when there is no signal
        # to trust". The unavailable half was never true — `_state` returns the
        # literal string "unavailable" for an entity that exists and is unreachable,
        # and `bool("unavailable")` is True. So a job-active binary that blipped
        # unavailable mid-run reported the completion secondary SATISFIED on the
        # strength of a signal that could not be read: confident and empty, the exact
        # shape issue #51 was fixed to remove.
        #
        # Fixed HERE rather than in `_state`, deliberately. Collapsing indeterminates
        # inside `_state` would change all five keys at once, and the other four feed
        # sentinel comparisons whose adapters already name the indeterminate values
        # themselves (Eufy lists "unavailable" among `secondary_clear_sentinels`).
        # This key is the only one asking "is there a signal to TRUST", so this is the
        # only one that needs the stronger test.
        #
        # WHICH WAY IT FAILS: an unreadable binary now falls through to the sentinel
        # check instead of short-circuiting True. For Roborock that check does not
        # pass (current_room reverts to the dock room's NAME, never a sentinel), so
        # the job simply does not finalize on THAT evaluation and finalizes on a later
        # one once the binary reads again. A late finalize is recoverable; a premature
        # one ends a job that is still running and writes a wrong run record and wrong
        # learned times. The costs are not symmetric.
        #
        # ⚠ NOT THE SAME QUESTION AS `diagnostics.py`'s KEY OF THE SAME NAME. That one
        # is `SignalPresence.has_state`, a pure "does a state object exist" probe, and
        # `job_active_signal.py` states outright that the callers of that distinction
        # "use different predicates and must keep doing so" — it is deliberately
        # non-lossy so a dump can tell never-created from momentarily-stateless. Do not
        # unify them. They share a name and ask different things.
        "job_active_present": _state(entities.get("job_active")) not in (
            "", "unavailable", "unknown",
        ),
    }


def completion_secondary_satisfied(
    vacuum_entity_id: str,
    completion_signals: dict[str, Any],
    clear_sentinels: frozenset[str],
) -> bool:
    """Whether the completion gate's secondary requirement is met.

    The gate is ``task_status == done`` AND this secondary AND
    has_observed_active_lifecycle. Two modes:

      - ``completion.require_job_active_clear`` (Roborock): the job-active
        (cleaning) binary clearing IS the completion signal — enforced by the
        separate ``is_job_active`` guard in the lifecycle handler — so the
        current-room sentinel check is bypassed here (returns True). Needed
        because Roborock's active_cleaning_target (``current_room``) reverts to
        the DOCK room's name at the end of a run, never a sentinel, so the
        default check below would never pass and the job would never finalize.
        Declaration is NECESSARY BUT NO LONGER SUFFICIENT. The body requires
        BOTH ``entities.job_active`` declared AND
        ``completion_signals["job_active_present"]`` — the entity must also
        RESOLVE to a readable, determinate state — before returning True.
        ⚠ was: "RP-033/COMMON-2: only honored when ``entities.job_active`` is
        actually declared", which documents the tightening this has since been
        superseded by (issue #51), and the correction lived only in the body
        comment a reader of the contract never reaches. Someone asking why a
        Roborock run failed to finalize would check that ``entities.job_active``
        is declared, find that it is, and rule this branch out — when the actual
        refusal came from the second condition. The motive is unchanged: the
        flag names the entity that supplies the real signal, so a config that
        sets the flag with nothing readable behind it must not short-circuit to
        True. Registration warns on the un-declared combination
        (adapters/registry.py._warn_completion_gate_orphan); at runtime EITHER
        failure falls through to the default sentinel check below, i.e. behaves
        as if the flag were never set.

      - default (Eufy): the active_cleaning_target must read a clear sentinel.
    """
    if bool(get_adapter_value(
        vacuum_entity_id, "completion", "require_job_active_clear", fallback=False
    )):
        # DECLARED IS NOT PRESENT (issue #51). RP-033/COMMON-2 tightened this from
        # "flag set" to "entity declared", which is one step short: a declared id that
        # resolves to no entity — the normal state of a localized install before the
        # translation_key rescue reaches it — still short-circuited to True. The gate
        # then reported the secondary satisfied on the strength of an entity that does
        # not exist, which is the worst shape a gate can have: confident and empty.
        #
        # Falling through to the sentinel check is the honest degradation and matches
        # what the docstring already promised for the un-declared case.
        if (
            get_adapter_value(vacuum_entity_id, "entities", "job_active", fallback=None)
            and completion_signals.get("job_active_present")
        ):
            return True
    return (
        str(completion_signals.get("active_target", "")).strip().lower()
        in clear_sentinels
    )


def job_finished_event_data(
    *,
    vacuum_entity_id: str,
    map_id: str,
    finalize_result: dict | None,
) -> dict:
    """Build a compact job-finished event payload.

    Used by every listener path that fires EVENT_JOB_FINISHED — lifecycle
    auto-finalization, pause-timeout cancellation, path-blocker forced
    cancellation. Keeps the payload shape consistent across all firing
    sites.
    """
    finalize_result = finalize_result if isinstance(finalize_result, dict) else {}
    completed_job = finalize_result.get("completed_job", {})
    outcome = completed_job.get("outcome", {}) if isinstance(completed_job, dict) else {}
    job_info = completed_job.get("job", {}) if isinstance(completed_job, dict) else {}
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "job_id": finalize_result.get("job_id"),
        "status": outcome.get("status", "completed"),
        "reason_detail": outcome.get("lifecycle_message") or outcome.get("status"),
        "used_for_learning": outcome.get("used_for_learning"),
        "finalized_at": completed_job.get("finalized_at"),
        "room_count": job_info.get("room_count"),
        "duration_minutes": job_info.get("duration_minutes"),
        "actual_cleaning_minutes": job_info.get("actual_cleaning_minutes"),
        "job_path": finalize_result.get("job_path"),
    }


def run_incomplete_event_data(
    *,
    vacuum_entity_id: str,
    finalize_result: dict | None,
) -> dict | None:
    """Build the run-incomplete event payload, or None when nothing was missed.

    A finalize writes an ``incomplete_run_log`` only for a cancelled / failed /
    interrupted outcome, and only that log lists the rooms that were queued but
    never cleaned. When it names at least one missed room this returns the
    ``EVENT_RUN_INCOMPLETE`` payload; otherwise it returns ``None`` so the caller
    simply skips the fire.

    Used by every listener path whose finalize can strand rooms — the
    pause-timeout auto-cancel, the stranded-run reaper, and the path-block cancel.
    The shape mirrors the ``finalize_learning_job`` service handler
    (``learning/services.py``) so an automation's ``retry_missed_rooms`` trigger
    fires identically whether the run was reaped internally or finalized via the
    service. Keeps the payload consistent across firing sites, exactly like
    ``job_finished_event_data`` does for EVENT_JOB_FINISHED.

    ``finalize_result`` is the raw finalize result (the dict carrying
    ``incomplete_run_log``) — listener callers unwrap ``result["finalize_result"]``
    before passing it here.
    """
    finalize_result = finalize_result if isinstance(finalize_result, dict) else {}
    incomplete_log = finalize_result.get("incomplete_run_log")
    if not isinstance(incomplete_log, dict) or not incomplete_log.get("missed_room_ids"):
        return None
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "job_id": incomplete_log.get("job_id"),
        "outcome_status": incomplete_log.get("outcome_status"),
        "missed_room_ids": list(incomplete_log.get("missed_room_ids", [])),
        "missed_rooms": list(incomplete_log.get("missed_rooms", [])),
    }
