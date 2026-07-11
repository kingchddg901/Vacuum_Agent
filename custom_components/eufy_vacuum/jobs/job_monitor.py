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
    ``"access_graph"`` for graph-propagated ones.
    """

    room_id: int
    name: Optional[str]
    source: str            # "direct_rule" | "access_graph"
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
) -> dict[str, Any]:
    """Build start protection result from lifecycle state and prepared payload."""
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

    if int(payload_room_count or 0) <= 0:
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
      - a sequenced phase mid-dispatch (``_phase_dispatch_pending``).

    Requires vacuum docked/idle — a still-``returning`` run is not yet over, and an
    error state is left alone (it may recover; reaping a maybe-recovering run is
    worse than a rare lingering record).
    """
    if str(status or "").strip().lower() != "started":
        return False
    if not has_observed_active_lifecycle:
        return False
    if phase_dispatch_pending or job_active_on or is_mid_run_status:
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
