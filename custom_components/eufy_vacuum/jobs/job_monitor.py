"""Evaluates vacuum job lifecycle state and builds start-blocker results."""

from __future__ import annotations

from typing import Any, Optional

# HA vacuum platform standard states. These are part of the HA vacuum
# state machine spec — not brand-specific firmware strings. All HA vacuum
# integrations use these state names regardless of brand.
_HA_ACTIVE_VACUUM_STATES: frozenset[str] = frozenset({
    "cleaning",   # vacuum platform standard
    "returning",  # vacuum platform standard
    "paused",     # vacuum platform standard
    "error",      # vacuum platform standard
})

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]


class BlockedRoomEntry(TypedDict, total=False):
    """One entry in ``PreflightResult["blocked_rooms"]``.

    ``source`` is ``"direct_rule"`` for rule-triggered blocks and
    ``"access_dependency"`` for access-graph-propagated ones (PRE-4: this
    comment used to name the never-actually-written literal
    ``"access_graph"`` — the real value planning/run_plan.py writes is
    ``"access_dependency"``; documentation-truth fix only, the code's
    literal is unchanged).
    """

    room_id: int
    name: Optional[str]
    source: str            # "direct_rule" | "access_dependency"
    reason: str
    triggered_rule_id: Optional[str]
    trigger_entity_id: Optional[str]
    blocked_by_room_id: Optional[int]
    blocked_by_room_name: Optional[str]


class ModifiedRoomEntry(TypedDict, total=False):
    """One entry in ``PreflightResult["modified_rooms"]`` for rooms changed by a modifier rule."""

    room_id: int
    name: Optional[str]
    changes: dict          # partial RoomRecord fields overridden by the rule
    triggered_rule_ids: list   # list[str]


class PreflightResult(TypedDict, total=False):
    """Output shape of the preflight sub-dict from ``_build_effective_start_plan()``.

    Produced at job-start time; consumed by the start-status endpoint and card.
    Never persisted — re-derived on each call.
    ``available`` is ``True`` when at least one room can run.
    ``confirm_token`` is an opaque token the UI must echo back to confirm.
    """

    available: bool
    blocked: bool
    requires_confirmation: bool
    confirm_token: Optional[str]
    reason: str
    message: str

    selected_room_ids: list     # list[int]
    included_room_ids: list     # list[int] — selected minus blocked
    blocked_room_ids: list      # list[int]

    selected_room_count: int
    included_room_count: int
    blocked_room_count: int

    selected_expected_minutes: float
    included_expected_minutes: float
    blocked_expected_minutes: float

    blocked_ratio_rooms: float  # 0.0–1.0
    blocked_ratio_time: float   # 0.0–1.0

    blocked_rooms: list         # list[BlockedRoomEntry]
    modified_rooms: list        # list[ModifiedRoomEntry]
    warnings: list              # list[str]
    graph: dict                 # access-graph validation summary


def _norm(value: Any) -> str:
    """Return a lowercase stripped string; maps sentinel values (unknown/unavailable/none) to empty string."""
    normalized = str(value or "").strip().lower()
    if normalized in {"unknown", "unavailable", "none"}:
        return ""
    return normalized


def build_job_metadata_from_payload(payload_state: dict[str, Any] | None) -> dict[str, Any]:
    """Extract lightweight job metadata (room IDs, slugs, clean modes) from a payload state dict."""
    payload_state = payload_state or {}

    resolved_rooms = payload_state.get("resolved_rooms", [])
    if not isinstance(resolved_rooms, list):
        resolved_rooms = []

    payload = payload_state.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    room_ids: list[int] = []
    room_slugs: list[str] = []
    clean_modes: list[str] = []

    for room in resolved_rooms:
        if not isinstance(room, dict):
            continue

        try:
            room_ids.append(int(room.get("room_id")))
        except (TypeError, ValueError):
            pass

        slug = str(room.get("slug", "")).strip().lower()
        if slug:
            room_slugs.append(slug)

        clean_mode = str(room.get("clean_mode", "")).strip().lower()
        if clean_mode:
            clean_modes.append(clean_mode)

    return {
        "map_id": payload.get("map_id"),
        "room_count": len(resolved_rooms),
        "room_ids": room_ids,
        "room_slugs": room_slugs,
        "clean_modes": clean_modes,
        "has_mop_mode": any("mop" in mode for mode in clean_modes),
        "has_vacuum_only_mode": any(mode in {"vacuum", "vacuum only"} for mode in clean_modes),
    }


def evaluate_job_lifecycle(
    *,
    active_job_exists: bool,
    active_cleaning_target: str | None,
    vacuum_state: str | None,
    task_status: str | None,
    dock_status: str | None,
    active_map_id: str | None,
    selected_map_id: str | None,
    job_metadata: dict[str, Any] | None = None,
    # Adapter-supplied vocabulary. Brand-specific sets (hard_service_states,
    # drying_states, active_run_task_states) default to empty — callers must
    # pass values from the adapter registry for correct blocking behaviour.
    # active_vacuum_states defaults to the HA platform standard set, which
    # applies universally across all vacuum integrations.
    hard_service_states: frozenset[str] = frozenset(),
    drying_states: frozenset[str] = frozenset(),
    active_run_task_states: frozenset[str] = frozenset(),
    active_vacuum_states: frozenset[str] = _HA_ACTIVE_VACUUM_STATES,
) -> dict[str, Any]:
    """Return a lifecycle state dict describing the vacuum's current readiness.

    Drying is a warning-only state (``blocking=False``). Washing, recycling,
    and dust-emptying are hard blockers.
    """
    job_metadata = job_metadata or {}

    vacuum_state_n = _norm(vacuum_state)
    task_status_n = _norm(task_status)
    dock_status_n = _norm(dock_status)
    active_cleaning_target_n = _norm(active_cleaning_target)
    active_map_id_n = str(active_map_id or "").strip()
    selected_map_id_n = str(selected_map_id or "").strip()

    if selected_map_id_n and active_map_id_n and selected_map_id_n != active_map_id_n:
        return {
            "lifecycle_state": "map_mismatch",
            "message": "The selected map does not match the vacuum's active map.",
            "blocking": True,
            "job_metadata": job_metadata,
        }

    if dock_status_n in hard_service_states or task_status_n in hard_service_states:
        return {
            "lifecycle_state": "mid_job_service",
            "message": "System is servicing the active job before cleaning continues.",
            "blocking": True,
            "job_metadata": job_metadata,
        }

    if dock_status_n in drying_states or task_status_n in drying_states:
        return {
            "lifecycle_state": "dock_drying",
            "message": "Dock is currently drying pads, but start is allowed.",
            "blocking": False,
            "warning": True,
            "job_metadata": job_metadata,
        }

    if active_job_exists and (
        active_cleaning_target_n
        or task_status_n in active_run_task_states
        or vacuum_state_n in active_vacuum_states
    ):
        return {
            "lifecycle_state": "active_job_running",
            "message": "A room-clean job is currently active.",
            "blocking": True,
            "job_metadata": job_metadata,
        }

    if task_status_n in active_run_task_states:
        return {
            "lifecycle_state": "vacuum_busy",
            "message": "Vacuum is busy and cannot start a new room job.",
            "blocking": True,
            "job_metadata": job_metadata,
        }

    if vacuum_state_n not in {"", "docked", "idle", "paused"} and vacuum_state_n not in active_vacuum_states:
        return {
            "lifecycle_state": "vacuum_busy",
            "message": "Vacuum is busy and cannot start a new room job.",
            "blocking": True,
            "job_metadata": job_metadata,
        }

    return {
        "lifecycle_state": "ready",
        "message": "Ready to start cleaning.",
        "blocking": False,
        "job_metadata": job_metadata,
    }


def build_start_blocker_from_lifecycle(
    *,
    lifecycle_state: str,
    lifecycle_message: str,
    selected_map_id: str | None,
    active_map_id: str | None,
    queue_room_ids: list[int] | list[str],
    payload_room_count: int,
    clean_phase_count: int | None = None,
) -> dict[str, Any]:
    """Build start protection result from lifecycle state and prepared payload.

    ``payload_room_count`` is the room count of the FIRST phase, which is what
    ``payload_state`` has always been. ``clean_phase_count`` is how many phases
    in the whole plan actually clean something — rooms OR zones. Pass it and the
    invalid-payload refusal asks the right question; omit it and the old
    first-phase-only behaviour is preserved for callers that have no plan to
    count (A5-PP-RP-2).
    """
    selected_map_id_n = str(selected_map_id or "").strip()
    active_map_id_n = str(active_map_id or "").strip()
    queue_count = len(queue_room_ids or [])

    if not selected_map_id_n:
        return {
            "reason": "no_target_map",
            "message": "Select a target map first.",
            "blocked": True,
        }

    if selected_map_id_n and active_map_id_n and selected_map_id_n != active_map_id_n:
        return {
            "reason": "map_mismatch",
            "message": "The selected map does not match the vacuum's active map.",
            "blocked": True,
        }

    if queue_count <= 0:
        return {
            "reason": "no_rooms_selected",
            "message": "Select at least one room first.",
            "blocked": True,
        }

    # A5-PP-RP-2. This used to read `payload_room_count <= 0` alone, and
    # payload_room_count is phases[0]["room_count"] — the FIRST phase only. A zone
    # phase carries room_count 0 by construction, so any plan whose first
    # surviving phase is a zone was refused as a corrupt payload while being
    # perfectly runnable.
    #
    # It is reachable WITHOUT the user changing anything. _build_steps_phases
    # skips a room_group whose rooms are all blocked ("whole group blocked / not
    # enabled -> skip"), so a saved rooms-then-zone run becomes unstartable the
    # moment a door or occupancy sensor blocks the rooms in its first group — and
    # the message blames a broken payload rather than naming the blocked room.
    #
    # The real question is "is there anything to clean?", not "does phase 0 have
    # rooms?". When the caller can answer it, that answer wins.
    _nothing_to_clean = (
        int(clean_phase_count) <= 0
        if clean_phase_count is not None
        else int(payload_room_count or 0) <= 0
    )
    if _nothing_to_clean:
        return {
            "reason": "invalid_payload",
            "message": "Room-clean payload is missing or invalid.",
            "blocked": True,
        }

    if lifecycle_state == "mid_job_service":
        return {
            "reason": "mid_job_service",
            "message": lifecycle_message or "System is servicing the active job before cleaning continues.",
            "blocked": True,
        }

    if lifecycle_state == "active_job_running":
        return {
            "reason": "active_job_running",
            "message": lifecycle_message or "A room-clean job is currently active.",
            "blocked": True,
        }

    if lifecycle_state == "vacuum_busy":
        return {
            "reason": "vacuum_busy",
            "message": lifecycle_message or "Vacuum is busy and cannot start a new room job.",
            "blocked": True,
        }

    if lifecycle_state == "dock_drying":
        return {
            "reason": "dock_drying",
            "message": lifecycle_message or "Dock is currently drying pads, but start is allowed.",
            "blocked": False,
            "warning": True,
        }

    return {
        "reason": "ready",
        "message": lifecycle_message or "Ready to start cleaning.",
        "blocked": False,
    }


# How long a dispatched `started` run may sit ENDED-but-unfinalized before the
# reaper finalizes it as `interrupted`. The run is already over by the time this
# grace starts (docked + its brand's completion secondary satisfied), so this is
# a safety margin against a late completion packet / a resume — comfortably longer
# than any real signal lag, while the mid-run / recharge / phase exclusions in
# is_stranded_started() already cover the legitimate long docks. Tunable.
STRANDED_REAP_GRACE_MINUTES: float = 5.0


#: RP-011/RF-07 (STR-4): a status="started" job that never observed an active
#: lifecycle (never even started moving) is reapable once dispatched this long
#: ago -- "still settling" stops being credible. Operational constant, not
#: empirically tuned.
NEVER_STARTED_SECONDS: int = 600

#: RP-011/RF-07 (WD-2/STR-3): a pending dock-phase guard past this age with no
#: liveness signal is treated as dead. Fallback only -- the real caller always
#: computes and passes a margin derived from the resolved phase timing; this
#: is what a caller that omits the margin gets.
_DEFAULT_PHASE_WATCHDOG_LIVENESS_MARGIN_SECONDS: float = 600.0


def _phase_pending_still_live(
    *,
    phase_watchdog_dead: bool,
    phase_dispatch_pending_since: str | None,
    liveness_margin_seconds: float,
) -> bool:
    """True while a pending dock-phase guard should still exclude the reaper --
    i.e. the watchdog is presumed alive. False (reapable) once the dead flag is
    explicitly set, or the guard has aged past its liveness margin. No age
    information at all (a caller that has not been updated to supply it) keeps
    the pre-repair conservative behaviour: presumed live."""
    if phase_watchdog_dead:
        return False
    if not phase_dispatch_pending_since:
        return True
    from ..timestamp_utils import parse_timestamp, utc_now

    since_dt = parse_timestamp(phase_dispatch_pending_since)
    if since_dt is None:
        return True
    age_seconds = (utc_now() - since_dt).total_seconds()
    return age_seconds <= liveness_margin_seconds


def is_stranded_started(
    *,
    status: str,
    has_observed_active_lifecycle: bool,
    vacuum_state: str,
    task_status: str,
    completion_task_status_value: str,
    secondary_satisfied: bool,
    job_active_on: bool,
    is_mid_run_status: bool,
    phase_dispatch_pending: bool,
    phase_watchdog_dead: bool = False,
    phase_dispatch_pending_since: str | None = None,
    phase_watchdog_liveness_margin_seconds: float = _DEFAULT_PHASE_WATCHDOG_LIVENESS_MARGIN_SECONDS,
    dispatched_seconds_ago: float | None = None,
    vacuum_errored: bool = False,
) -> bool:
    """True when a dispatched ``started`` run looks ENDED but never hit its brand's
    completion terminal — the FN-1 strand (the run leaves no record and can mask a
    later external run / be mis-attributed by a later terminal signal).

    Brand-agnostic by construction: the caller resolves the brand-specific inputs —
    ``completion_task_status_value`` (Eufy ``"completed"`` / Roborock ``"charging"``),
    ``secondary_satisfied`` (Eufy target-cleared / Roborock job_active-clear, via
    ``completion_secondary_satisfied``), and ``is_mid_run_status`` (the adapter's
    mop-wash/empty/recharge dock set). A run is stranded when it GENUINELY RAN
    (armed) and now reads docked/idle with its completion secondary satisfied, yet
    ``task_status`` has NOT reached the completion value — AND none of the
    "will-resume / mid-flight" exclusions hold:

      - paused runs are excluded (the pause-timeout reaper owns those; only
        ``status=="started"`` reaches here),
      - a mid-run dock (mop-wash / dust-empty / recharge-resume — Eufy),
      - the recharge job-active binary still ON (Roborock mid-job recharge),
      - a sequenced phase mid-dispatch whose watchdog is still LIVE
        (``_phase_dispatch_pending`` alone is no longer an unconditional
        exclusion — RP-011/RF-07 WD-2/STR-3: a DEAD watchdog's phase is reapable
        via ``phase_watchdog_dead`` / ``phase_dispatch_pending_since``).

    STR-4: a run that never observed an active lifecycle at all cannot be
    evaluated by the ended-looking checks below (they all assume a real run
    happened) — it is reapable once ``dispatched_seconds_ago`` clears
    ``NEVER_STARTED_SECONDS``, independent of vacuum_state/docked signals.

    Requires vacuum docked/idle — a still-``returning`` run is not yet over.

    An ERRORED robot is reapable (``vacuum_errored``), which reverses this function's
    original rule. That rule read "an error state is left alone (it may recover;
    reaping a maybe-recovering run is worse than a rare lingering record)" and was
    disproved on hardware: neither shipped brand resumes itself after a trap, so the
    lingering record is every trap rather than a rare one. The recovery allowance now
    lives in the caller's grace window instead, which is where it can actually
    observe a recovery. See the clause below.
    """
    if str(status or "").strip().lower() != "started":
        return False
    if not has_observed_active_lifecycle:
        return (
            dispatched_seconds_ago is not None
            and dispatched_seconds_ago >= NEVER_STARTED_SECONDS
        )
    if phase_dispatch_pending and _phase_pending_still_live(
        phase_watchdog_dead=phase_watchdog_dead,
        phase_dispatch_pending_since=phase_dispatch_pending_since,
        liveness_margin_seconds=phase_watchdog_liveness_margin_seconds,
    ):
        return False
    # A run whose robot is ERRORED is over, and neither check below can see that.
    #
    # HARDWARE, 2026-08-09. A Roborock wedged on a box threw `bumper_stuck` and sat
    # there. Both gates below refused to reap it: upstream keeps
    # `binary_sensor.<vac>_cleaning` ON for an errored robot, so `job_active_on`
    # stayed True; and `error` is neither "docked" nor "idle". The run was still
    # `started` eight minutes past a five-minute grace with `stranded_since` never
    # even stamped, and would have stayed that way indefinitely.
    #
    # This clause replaces the old "an error state is left alone (it MAY RECOVER)"
    # reasoning, which the same test disproved: neither shipped brand resumes itself
    # after a trap — a human has to intervene, and for `bumper_stuck` the firmware
    # will not release until the bumper is physically actuated. So the lingering
    # record is not the rare case that reasoning traded for, it is EVERY trap.
    #
    # The transient error it was protecting against is still protected, by the
    # caller rather than here: poll_stranded_started_job stamps `stranded_since` on
    # the first tick and only reports a reap once the grace has elapsed, clearing the
    # stamp if the condition stops holding. An error that clears inside the window
    # costs nothing. THAT grace is the "may recover" allowance — this predicate just
    # stops pretending an errored robot is still cleaning.
    if vacuum_errored:
        return True
    if job_active_on or is_mid_run_status:
        return False
    if str(vacuum_state or "").strip().lower() not in ("docked", "idle"):
        return False
    if not secondary_satisfied:
        return False
    # If task_status HAS reached the brand's completion value, the normal
    # completion gate owns this — not a strand.
    if str(task_status or "").strip().lower() == str(completion_task_status_value or "").strip().lower():
        return False
    return True
