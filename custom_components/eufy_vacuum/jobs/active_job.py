"""ActiveJobTracker — active-job state, timing rollover, and transition-room detection.

Owns:
- _parse_job_timestamp, _default_active_job_state, _derive_active_job_current_room_id
- _normalize_active_job, _compute_current_room_elapsed_minutes
- _is_charging, _is_low_battery_return_state
- update_active_job_recharge_observation
- update_active_job_mop_wash_observation, record_active_job_transition
- _room_name_from_active_job
- _timing_completion_threshold_minutes (_MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER)
- _robot_outside_room_bounds, _maybe_roll_current_room_by_timing
- _access_graph_path, _get_robot_position, _detect_transition_room_from_position
- _job_status_summary

Receives manager (EufyVacuumManager) parent reference.
"""

from __future__ import annotations

import asyncio
from collections import deque
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..core.charging import (
    is_charging as _is_charging_impl,
    is_low_battery_return_state as _is_low_battery_return_state_impl,
)
from ..const import DOMAIN, EVENT_ROOM_FINISHED, EVENT_ROOM_STARTED
# select_active is the brand-agnostic selection stage (stays a direct framework
# import); find_candidates / segment_legacy route through the pluggable job-segmenter
# engine (resolved per-vacuum in _live_boundary_count).
from ..counter_segmentation import select_active
from ..rooms.utils import slugify_room_name
from ..timestamp_utils import parse_timestamp, utc_now_iso

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

_PATH_BLOCK_ACTIONS = frozenset(
    {"event_only", "pause_and_event", "cancel_and_event"}
)


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return float value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso_now() -> str:
    """Return current UTC timestamp in stable format."""
    return utc_now_iso()


def _normalize_path_block_action(value: Any) -> str:
    """Return a supported path-block reaction policy."""
    normalized = str(value or "").strip().lower()
    if normalized in _PATH_BLOCK_ACTIONS:
        return normalized
    return "event_only"


def _normalize_pause_timeout_minutes(value: Any) -> int:
    """Return a safe non-negative paused-job timeout in minutes."""
    return max(_safe_int(value, 0), 0)


# Per-job counter-sample buffer cap — a normal job is well under this; guards a
# stuck/never-finalized job from growing the buffer unbounded.
_MAX_COUNTER_SAMPLES = 2000

# Live current-room rollover ORCHESTRATION knobs only — an adapter WITHOUT a
# "live_transition" block behaves as before EXCEPT it now also rolls on a "transit"
# boundary (a 60-90 s flat-area inter-room hop the legacy live path discarded). The
# gap/area/cadence THRESHOLDS live in the adapter's job_segmenter.tuning (the single
# source, resolved by the job-segmenter engine in _live_boundary_count); this block
# carries only enabled / rollover_kinds / native_transition_source. See
# ActiveJobTracker._live_transition_config.
_LIVE_TRANSITION_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "rollover_kinds": ("wash_plateau", "transit", "area_jump"),
    "native_transition_source": False,
}


class ActiveJobTracker:
    """Owns active-job computation, timing rollover, and transition-room detection."""

    def __init__(self, manager: "EufyVacuumManager") -> None:
        """Initialise with the parent EufyVacuumManager.

        Args:
            manager: Parent manager; used to access data, hass, and peer methods.
        """
        self._manager = manager
        # Sensor update callbacks — same pattern as ErrorTracker.add_update_listener.
        # Fired with (vacuum_entity_id, map_id) on job status transitions.
        self._update_listeners: list[Callable[[str, str], None]] = []

    # -- state defaults & normalization ----------------------------------------

    def _parse_job_timestamp(self, value: str | None) -> datetime | None:
        """Parse persisted job timestamps."""
        return parse_timestamp(value)

    def _default_active_job_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return the default active-job structure."""
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "queue_room_ids": [],
            "queue_stable_keys": [],
            "queue_rooms": [],
            "payload": {"map_id": str(map_id), "rooms": []},
            "resolved_rooms": [],
            "room_count": 0,
            "status": "idle",
            "paused_at": None,
            "paused_duration_seconds": 0,
            "completed_room_ids": [],
            "completed_rooms": [],
            "current_room_id": None,
            "current_room_started_at": None,
            "current_room_paused_seconds": 0,
            "observed_mid_job_recharge": False,
            "observed_mid_job_recharge_started_at": None,
            "observed_mid_job_recharge_count": 0,
            "recharge_seconds_accumulated": 0,
            "pending_mid_job_recharge_return": False,
            "pending_mid_job_recharge_return_at": None,
            "observed_mop_wash_count": 0,
            "observed_mop_wash_last_at": None,
            # Per-cycle observation log. List of {"observed_at": <iso ts>}.
            # Tracks individual wash events (vs. the rollup count above) so
            # post-job analysis can correlate wash cadence with mop minutes.
            "observed_mop_wash_cycles": [],
            "state_transitions": [],
            "counter_samples": [],
            # External-run only: deduped timeline of the per-room setting selects
            # ([{t, settings:{clean_mode,...}}]), snapshotted alongside the counters
            # when status == "external". Empty for internal jobs (we dispatched them).
            "settings_samples": [],
            "water_estimate": None,
            "path_block_action": "event_only",
            "pause_timeout_minutes": 0,
            "has_observed_active_lifecycle": False,
        }

    def _derive_active_job_current_room_id(self, active_job: dict[str, Any]) -> int | None:
        """Return the next unresolved room id for an active job."""
        completed_ids = {
            _safe_int(room_id, -1)
            for room_id in active_job.get("completed_room_ids", [])
            if _safe_int(room_id, -1) >= 0
        }

        for room in active_job.get("resolved_rooms", []):
            room_id = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            if room_id >= 0 and room_id not in completed_ids:
                return room_id

        for room_id in active_job.get("queue_room_ids", []):
            normalized = _safe_int(room_id, -1)
            if normalized >= 0 and normalized not in completed_ids:
                return normalized

        return None

    def _normalize_active_job(self, active_job: dict[str, Any]) -> dict[str, Any]:
        """Ensure an active-job record contains progress fields."""
        normalized = dict(active_job) if isinstance(active_job, dict) else {}
        normalized.setdefault("queue_room_ids", [])
        normalized.setdefault("queue_stable_keys", [])
        normalized.setdefault("queue_rooms", [])
        normalized.setdefault("payload", {})
        normalized.setdefault("resolved_rooms", [])
        normalized.setdefault("room_count", 0)
        normalized.setdefault("status", "idle")
        normalized.setdefault("paused_at", None)
        normalized.setdefault("paused_duration_seconds", 0)
        normalized.setdefault("completed_room_ids", [])
        normalized.setdefault("completed_rooms", [])
        normalized.setdefault("current_room_paused_seconds", 0)
        normalized.setdefault("observed_mid_job_recharge", False)
        normalized.setdefault("observed_mid_job_recharge_started_at", None)
        normalized.setdefault("observed_mid_job_recharge_count", 0)
        normalized.setdefault("recharge_seconds_accumulated", 0)
        normalized.setdefault("pending_mid_job_recharge_return", False)
        normalized.setdefault("pending_mid_job_recharge_return_at", None)
        normalized.setdefault("observed_mop_wash_count", 0)
        normalized.setdefault("observed_mop_wash_last_at", None)
        normalized.setdefault("observed_mop_wash_cycles", [])
        normalized.setdefault("state_transitions", [])
        normalized.setdefault("counter_samples", [])
        normalized.setdefault("settings_samples", [])
        normalized.setdefault("water_estimate", None)
        normalized.setdefault("has_observed_active_lifecycle", False)
        normalized["path_block_action"] = _normalize_path_block_action(
            normalized.get("path_block_action")
        )
        normalized["pause_timeout_minutes"] = _normalize_pause_timeout_minutes(
            normalized.get("pause_timeout_minutes")
        )

        if "current_room_id" not in normalized:
            normalized["current_room_id"] = self._derive_active_job_current_room_id(normalized)

        if "current_room_started_at" not in normalized:
            normalized["current_room_started_at"] = normalized.get("started_at")

        return normalized

    # -- timing helpers --------------------------------------------------------

    def _compute_current_room_elapsed_minutes(
        self,
        *,
        active_job: dict[str, Any],
        now: str | None = None,
    ) -> float:
        """Return elapsed active minutes for the current room, excluding pauses."""
        current_started_at = str(active_job.get("current_room_started_at", "")).strip()
        started_dt = self._parse_job_timestamp(current_started_at)
        now_dt = self._parse_job_timestamp(now or _iso_now())
        if started_dt is None or now_dt is None:
            return 0.0

        elapsed_seconds = max(int((now_dt - started_dt).total_seconds()), 0)
        paused_seconds = max(_safe_int(active_job.get("current_room_paused_seconds"), 0), 0)
        paused_at = str(active_job.get("paused_at", "")).strip()
        paused_dt = self._parse_job_timestamp(paused_at)
        if paused_dt is not None and active_job.get("status") == "paused":
            paused_seconds += max(int((now_dt - paused_dt).total_seconds()), 0)

        return round(max((elapsed_seconds - paused_seconds) / 60.0, 0.0), 2)

    def _is_charging(self, vacuum_entity_id: str) -> bool:
        """Definitive "is the vacuum charging right now" check."""
        return _is_charging_impl(self._manager.hass, vacuum_entity_id)

    def _is_low_battery_return_state(
        self,
        *,
        vacuum_entity_id: str,
        current_battery: int,
        vacuum_state: str | None,
        task_status: str | None,
    ) -> bool:
        """Return whether the robot is returning to dock due to low battery.

        The brand low-battery-return task_status string and threshold come from
        the adapter's ``charging`` config; the detection logic is framework code.
        """
        _charging_cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("charging", {})
        return _is_low_battery_return_state_impl(
            current_battery=current_battery,
            vacuum_state=vacuum_state,
            task_status=task_status,
            low_battery_return_status=_charging_cfg.get("low_battery_return_task_status") or "",
            threshold_percent=int(_charging_cfg.get("low_battery_threshold_percent") or 20),
        )

    # -- observation recording -------------------------------------------------

    def update_active_job_recharge_observation(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Record that the active job has actually entered a recharge-like state."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        vacuum_state = self._manager.hass.states.get(vacuum_entity_id)
        _recharge_entities = (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {})
        _task_status_id = _recharge_entities.get("task_status")
        task_status_state = (
            self._manager.hass.states.get(_task_status_id) if _task_status_id else None
        )
        current_battery = self._manager._get_battery_level(vacuum_entity_id)
        observed_at_value = observed_at or _iso_now()

        if self._is_low_battery_return_state(
            vacuum_entity_id=vacuum_entity_id,
            current_battery=current_battery,
            vacuum_state=vacuum_state.state if vacuum_state is not None else None,
            task_status=task_status_state.state if task_status_state is not None else None,
        ):
            if not bool(active_job.get("pending_mid_job_recharge_return", False)):
                active_job["pending_mid_job_recharge_return"] = True
                active_job["pending_mid_job_recharge_return_at"] = observed_at_value

        if not bool(active_job.get("pending_mid_job_recharge_return", False)):
            self._manager.data.setdefault("active_jobs", {})
            self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
            return active_job

        if not self._is_charging(vacuum_entity_id):
            self._manager.data.setdefault("active_jobs", {})
            self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
            return active_job

        tracker = self._manager.hass.data.get(DOMAIN, {}).get("mapping_tracker")

        if bool(active_job.get("observed_mid_job_recharge", False)):
            # Recharge already in progress — check if it ended (vacuum resumed cleaning).
            if not self._is_charging(vacuum_entity_id):
                started_str = str(active_job.get("observed_mid_job_recharge_started_at") or "").strip()
                if started_str:
                    started_dt = parse_timestamp(started_str)
                    ended_dt = parse_timestamp(observed_at_value)
                    if started_dt and ended_dt and ended_dt > started_dt:
                        elapsed = int((ended_dt - started_dt).total_seconds())
                        current = max(_safe_int(active_job.get("recharge_seconds_accumulated"), 0), 0)
                        active_job["recharge_seconds_accumulated"] = current + elapsed
                active_job["observed_mid_job_recharge"] = False
                active_job["observed_mid_job_recharge_started_at"] = None
                if tracker is not None:
                    tracker.resume_sampling(vacuum_entity_id)
            self._manager.data.setdefault("active_jobs", {})
            self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
            return active_job

        active_job["observed_mid_job_recharge"] = True
        active_job["observed_mid_job_recharge_started_at"] = observed_at_value
        active_job["observed_mid_job_recharge_count"] = max(
            _safe_int(active_job.get("observed_mid_job_recharge_count"), 0),
            0,
        ) + 1
        active_job["pending_mid_job_recharge_return"] = False
        active_job["pending_mid_job_recharge_return_at"] = None

        if tracker is not None:
            tracker.pause_sampling(vacuum_entity_id)

        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def update_active_job_mop_wash_observation(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Record a debounced mop-wash event on the active job.

        A dock's wash state can flip 1-2 times within a short window per
        actual wash cycle. The cooldown (adapter ``dock_events.debounce_seconds``
        keyed by ``last_mop_wash``; 0 = none) collapses those flips into one
        counted event.
        """
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        now_str = observed_at or _iso_now()
        last_at = active_job.get("observed_mop_wash_last_at")

        _debounce_cfg = (
            (_get_adapter_config(vacuum_entity_id) or {})
            .get("dock_events", {})
            .get("debounce_seconds", {})
        )
        debounce_seconds = float(_debounce_cfg.get("last_mop_wash", 0) or 0)

        if last_at:
            try:
                last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
                now_dt = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
                if (now_dt - last_dt).total_seconds() < debounce_seconds:
                    return active_job
            except Exception:
                # Unparseable timestamp → fall through and count the wash. Log
                # so a silent debounce break from a timestamp-format drift is
                # detectable rather than invisible.
                _LOGGER.debug(
                    "mop-wash debounce: could not parse timestamps (last=%r now=%r)",
                    last_at, now_str, exc_info=True,
                )

        active_job["observed_mop_wash_count"] = (
            _safe_int(active_job.get("observed_mop_wash_count"), 0) + 1
        )
        active_job["observed_mop_wash_last_at"] = now_str

        # Append per-cycle timestamp. Capped at 50 to bound storage in case
        # dock_status oscillates beyond what the 60s debounce above catches —
        # a real mop-heavy job has 5-10 wash cycles, so this is wildly more
        # than expected.
        cycles = [
            entry for entry in (active_job.get("observed_mop_wash_cycles") or [])
            if isinstance(entry, dict)
        ]
        cycles.append({"observed_at": now_str})
        active_job["observed_mop_wash_cycles"] = cycles[-50:]

        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def record_active_job_transition(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        entity_id: str,
        from_state: str | None,
        to_state: str | None,
        changed_at: str | None = None,
    ) -> dict[str, Any]:
        """Append one relevant state transition to the tracked active job."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        from_state_n = str(from_state or "").strip()
        to_state_n = str(to_state or "").strip()
        if not to_state_n or from_state_n == to_state_n:
            return active_job

        transitions = [
            dict(entry)
            for entry in active_job.get("state_transitions", [])
            if isinstance(entry, dict)
        ]
        transitions.append(
            {
                "entity_id": entity_id,
                "from_state": from_state_n,
                "to_state": to_state_n,
                "changed_at": changed_at or _iso_now(),
            }
        )
        active_job["state_transitions"] = transitions[-12:]

        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def _room_name_from_active_job(self, active_job: dict[str, Any], room_id: int | None) -> str | None:
        """Return room name for one room id from active-job state."""
        if room_id is None:
            return None
        normalized_room_id = _safe_int(room_id, -1)
        if normalized_room_id < 0:
            return None

        for room in active_job.get("resolved_rooms", []):
            candidate = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            if candidate == normalized_room_id:
                return str(room.get("name", room.get("room_name", room.get("slug", "")))).strip() or None

        for room in active_job.get("queue_rooms", []):
            candidate = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            if candidate == normalized_room_id:
                return str(room.get("name", room.get("room_name", room.get("slug", "")))).strip() or None

        return None

    # -- timing rollover + spatial detection -----------------------------------

    def _timing_completion_threshold_minutes(self, room: dict[str, Any]) -> float:
        """Return a conservative elapsed-minutes threshold for timing rollover."""
        estimated_minutes = max(_safe_float(room.get("minutes"), 0.0), 1.0)
        confidence_score = max(min(_safe_float(room.get("confidence_score"), 0.0), 1.0), 0.0)
        sample_count = max(_safe_int(room.get("sample_count"), 0), 0)
        drift_ratio = max(_safe_float(room.get("accuracy_drift_ratio"), 0.0), 0.0)

        if confidence_score >= 0.85:
            overrun_ratio = 0.06
        elif confidence_score >= 0.65:
            overrun_ratio = 0.10
        elif confidence_score >= 0.45:
            overrun_ratio = 0.15
        else:
            overrun_ratio = 0.22

        slack_minutes = max(0.75, estimated_minutes * overrun_ratio)

        if sample_count <= 1:
            slack_minutes += 1.0
        elif sample_count <= 3:
            slack_minutes += 0.5

        if drift_ratio > 0:
            slack_minutes += min(estimated_minutes * drift_ratio * 0.25, 1.5)

        slack_minutes = min(slack_minutes, max(4.0, estimated_minutes * 0.35))
        return round(estimated_minutes + slack_minutes, 2)

    # Floor on elapsed-cleaning time before the mapping tracker's
    # fast-rollover signal is acted on. Calibrated to the smallest room
    # in a representative install with no floor blockers — anything
    # finished faster than this is much more likely a transit through
    # the room than a genuine clean. The tracker's own time/movement-
    # factor model already filters most noise; this is a final floor.
    _MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER = 1.5  # 90 s

    def _robot_outside_room_bounds(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
    ) -> bool | None:
        """Return True/False if the robot's current position is outside the
        room's learned bounds, or None when either the position or the
        bounds aren't available (caller should treat as "unknown" — neither
        triggers nor blocks rollover).
        """
        pos = self._get_robot_position(vacuum_entity_id)
        if pos is None:
            return None

        mapping_manager = self._manager.hass.data.get(DOMAIN, {}).get("mapping_manager")
        if mapping_manager is None:
            return None

        try:
            bounds_snapshot = mapping_manager.get_room_bounds_snapshot(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        except Exception:
            _LOGGER.debug(  # pragma: no cover
                "EufyManager: bounds snapshot fetch failed (vacuum=%s room=%s)",
                vacuum_entity_id, room_id,
            )
            return None

        room_bounds = (
            bounds_snapshot.get("rooms", {})
            .get(str(room_id), {})
            .get("bounds")
        )
        if room_bounds is None:
            return None

        vx, vy = pos
        inside = (
            room_bounds["min_x"] <= vx <= room_bounds["max_x"]
            and room_bounds["min_y"] <= vy <= room_bounds["max_y"]
        )
        return not inside

    def _position_lock_reliable(self, vacuum_entity_id: str) -> bool:
        """Whether this adapter's localization lock is reliable enough to trust
        position/bounds for room detection.

        The adapter's call — core stays neutral and defaults to False (don't trust
        unverified geometry). Eufy answers False (its firmware re-bases the raw
        coordinate frame every session, so stored bounds drift); a brand with a
        stable lock can answer True to re-enable the bounds gate.
        """
        cfg = _get_adapter_config(vacuum_entity_id) or {}
        caps = cfg.get("capabilities", {})
        if not isinstance(caps, dict):
            return False
        return bool(caps.get("position_lock_reliable", False))

    def _live_transition_config(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Live rollover ORCHESTRATION, adapter-overridable. Merges the adapter's
        ``live_transition`` block over ``_LIVE_TRANSITION_DEFAULTS`` — enabled /
        rollover_kinds / native_transition_source only. The gap/area/cadence thresholds
        are NOT here: they live in ``job_segmenter.tuning`` (the single source), resolved
        by the job-segmenter engine in ``_live_boundary_count``."""
        cfg = dict(_LIVE_TRANSITION_DEFAULTS)
        block = (_get_adapter_config(vacuum_entity_id) or {}).get("live_transition")
        if isinstance(block, dict):
            if "enabled" in block:
                cfg["enabled"] = bool(block["enabled"])
            if "native_transition_source" in block:
                cfg["native_transition_source"] = bool(block["native_transition_source"])
            kinds = block.get("rollover_kinds")
            if isinstance(kinds, (list, tuple)) and kinds:
                cleaned = tuple(str(k).strip() for k in kinds if str(k).strip())
                if cleaned:
                    cfg["rollover_kinds"] = cleaned
        return cfg

    def _live_boundary_count(self, vacuum_entity_id: str, active_job: dict[str, Any], raw_timeline: list[dict[str, Any]]) -> int:
        """Number of completed room transitions the live counter signal currently shows
        (the in-progress room is never counted — expected_rooms caps boundaries at N-1).
        Transit-aware + adapter-tunable; falls back to the legacy wash/area_jump-only
        segmentation when the live_transition hook is disabled.

        Detection routes through the adapter's pluggable job-segmenter engine (absent
        block → the Eufy counter engine, byte-identical); ``select_active`` stays the
        brand-agnostic framework selection."""
        from ..learning.job_segmenter_engines import get_job_segmenter_engine

        samples = active_job.get("counter_samples", []) or []
        cfg = self._live_transition_config(vacuum_entity_id)
        # Engine + thresholds both come from the adapter's job_segmenter block (the
        # single source); absent → the Eufy counter engine + its DEFAULT_TUNING. The
        # engine merges a partial/None tuning over its own defaults.
        _js = (_get_adapter_config(vacuum_entity_id) or {}).get("job_segmenter") or {}
        engine = get_job_segmenter_engine(_js.get("engine") if isinstance(_js, dict) else None)
        tuning = _js.get("tuning") if isinstance(_js, dict) else None

        if not cfg["enabled"]:
            segments = engine.segment_legacy(
                samples, expected_rooms=len(raw_timeline) or None, tuning=tuning
            )
            return max(len(segments) - 1, 0)
        candidates = engine.find_candidates(samples, tuning=tuning)
        active = select_active(
            candidates,
            expected_rooms=len(raw_timeline) or None,
            kinds=set(cfg["rollover_kinds"]),
        )
        return len(active)

    def _maybe_roll_current_room_by_timing(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        raw_timeline: list[dict[str, Any]],
        current_room_id: int | None,
        current_room_elapsed_minutes: float,
        completed_room_ids: list[int],
    ) -> dict[str, Any]:
        """Advance one room when elapsed time + bounds together justify rollover.

        Two paths:
          - **Slow room**: timing has reached or exceeded the per-room
            learned threshold AND the robot has left the room's bounds
            (single-sample bounds check — we already waited for timing).
            Fires ``EVENT_ROOM_FINISHED`` with ``source="timing_rollover"``.
          - **Fast room**: the mapping tracker's confidence model has
            decided the robot finished and exited the room (set via the
            ``_pending_fast_rollover`` flag on active_job — see
            ``MappingTracker._signal_fast_rollover``). The tracker's
            time-in-room - movement-count threshold filters doorway
            transits; we additionally require ``elapsed >=
            _MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER`` as a final floor.
            Fires ``EVENT_ROOM_FINISHED`` with ``source="bounds_exit_early"``.
        """
        if active_job.get("status") != "started":
            return active_job

        # Native current-room signal path (e.g. Roborock current_room): the device
        # reports the live room directly, so rollover FOLLOWS that signal (filtered
        # to job targets, matched by name slug, order-agnostic) instead of the
        # sequential timing/counter heuristic below. Gated by the adapter's
        # live_transition.native_transition_source (Eufy defaults False -> the
        # block below is unchanged). Runs BEFORE the current_room_id None guard +
        # the sequential unresolved-index guards (which don't apply to
        # device-optimized order), and reads current_room_id STRAIGHT from
        # active_job rather than the caller's value — the caller derives it from the
        # learning timeline, which is empty before any learning data exists, but the
        # native signal is independent of the timeline.
        if self._live_transition_config(vacuum_entity_id).get("native_transition_source"):
            return self._maybe_roll_current_room_by_native_signal(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                active_job=active_job,
                current_room_id=active_job.get("current_room_id"),
                current_room_elapsed_minutes=current_room_elapsed_minutes,
            )

        if current_room_id is None:
            return active_job

        unresolved_room_ids = [
            _safe_int(room.get("room_id", -1), -1)
            for room in raw_timeline
            if _safe_int(room.get("room_id", -1), -1) not in completed_room_ids
        ]
        if current_room_id not in unresolved_room_ids:
            return active_job

        current_index = unresolved_room_ids.index(current_room_id)
        if current_index >= len(unresolved_room_ids) - 1:
            return active_job

        current_room = next(
            (
                dict(room)
                for room in raw_timeline
                if _safe_int(room.get("room_id", -1), -1) == current_room_id
            ),
            None,
        )
        if not current_room:
            return active_job

        # Counter-plateau boundary — high-confidence + frame-invariant. When the
        # cleaning counters show more finished-room transitions than we've recorded,
        # roll now, ahead of the timing threshold. The in-progress room is never
        # counted (expected_rooms caps boundaries at N-1), so this never rolls the
        # final room. Transit-aware + adapter-tunable — see _live_boundary_count.
        if self._live_boundary_count(vacuum_entity_id, active_job, raw_timeline) > len(completed_room_ids):
            return self._apply_room_rollover(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                active_job=active_job,
                current_room_id=current_room_id,
                current_room=current_room,
                elapsed_minutes=current_room_elapsed_minutes,
                source="counter_plateau",
            )

        threshold_minutes = self._timing_completion_threshold_minutes(current_room)
        elapsed = current_room_elapsed_minutes

        if elapsed < threshold_minutes:
            # Fast-room path: only the mapping tracker's confidence
            # signal can advance us before the timing threshold. The
            # signal lives on active_job as _pending_fast_rollover and
            # is consumed (popped) when we act on it.
            pending = active_job.get("_pending_fast_rollover")
            if not isinstance(pending, dict):
                return active_job
            try:
                signalled_room_id = int(pending.get("room_id"))
            except (TypeError, ValueError):
                signalled_room_id = None
            if signalled_room_id != current_room_id:
                # Stale signal for a room the queue has already moved
                # past — leave it; the next confident exit overwrites.
                return active_job
            if elapsed < self._MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER:
                return active_job

            # Consume the signal so it can't trigger again on the next tick.
            active_job.pop("_pending_fast_rollover", None)
            rollover_source = "bounds_exit_early"
        else:
            # Slow-room path: timing has reached threshold; require the
            # robot to be outside bounds before allowing rollover. A
            # single sample is sufficient here because the room already
            # ran long — we're confirming completion, not detecting it.
            # When bounds are unavailable, timing alone wins (matches
            # pre-existing behaviour).
            # Bounds confirmation is honoured only when the adapter declares its
            # localization lock reliable (capability-gated). Eufy's frame drifts
            # across sessions, so its stored bounds would wrongly block (or pass)
            # a legitimate rollover — there, timing alone advances.
            outside = self._robot_outside_room_bounds(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=current_room_id,
            )
            if self._position_lock_reliable(vacuum_entity_id) and outside is False:
                return active_job
            rollover_source = "timing_rollover"

        return self._apply_room_rollover(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            active_job=active_job,
            current_room_id=current_room_id,
            current_room=current_room,
            elapsed_minutes=current_room_elapsed_minutes,
            source=rollover_source,
        )

    def _apply_room_rollover(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        current_room_id: int,
        current_room: dict[str, Any],
        elapsed_minutes: float,
        source: str,
    ) -> dict[str, Any]:
        """Record one room completed + fire EVENT_ROOM_FINISHED / EVENT_ROOM_STARTED.

        Shared by every live rollover path — ``source`` distinguishes them on the
        event (``counter_plateau`` / ``timing_rollover`` / ``bounds_exit_early``).
        """
        completed_at = _iso_now()
        room_name = self._room_name_from_active_job(active_job, current_room_id)
        confidence_score = _safe_float(current_room.get("confidence_score"), 0.0)
        updated_active_job = self.record_completed_room(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=current_room_id,
            room_name=room_name,
            actual_duration_minutes=elapsed_minutes,
            completed_at=completed_at,
            source=source,
            confidence=confidence_score if confidence_score > 0 else None,
        )

        self._manager.hass.bus.async_fire(
            EVENT_ROOM_FINISHED,
            {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "job_id": updated_active_job.get("job_id"),
                "room_id": str(current_room_id),
                "room_name": room_name,
                "completed_at": completed_at,
                "source": source,
                "actual_duration_minutes": round(elapsed_minutes, 2),
                "confidence": round(confidence_score, 4) if confidence_score > 0 else None,
                "completed_room_ids": updated_active_job.get("completed_room_ids", []),
            },
        )

        next_room_id = _safe_int(updated_active_job.get("current_room_id"), -1)
        if next_room_id >= 0:
            self._manager.hass.bus.async_fire(
                EVENT_ROOM_STARTED,
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "job_id": updated_active_job.get("job_id"),
                    "room_id": str(next_room_id),
                    "room_name": self._room_name_from_active_job(updated_active_job, next_room_id),
                    "started_at": updated_active_job.get("current_room_started_at"),
                    "source": source,
                    "completed_room_ids": updated_active_job.get("completed_room_ids", []),
                },
            )

        self._manager.hass.async_create_task(self._manager._async_save_logged())
        return updated_active_job

    # -- native current-room signal rollover -----------------------------------

    def _resolve_native_target_room_id(
        self,
        vacuum_entity_id: str,
        active_job: dict[str, Any],
    ) -> int | None:
        """Resolve the brand's native current-room NAME signal to a job-target id.

        Reads entities.active_cleaning_target (Roborock sensor.{id}_current_room, a
        room NAME), slugifies it, and matches it against the job's TARGET rooms
        (queue_room_ids) by slug. Returns the matched target's room_id, or None for
        a transit room / the dock / a sentinel / any name not among the job
        targets — the transit filter that keeps a cross-room hop from advancing.
        """
        cfg = _get_adapter_config(vacuum_entity_id) or {}
        entity_id = cfg.get("entities", {}).get("active_cleaning_target")
        if not entity_id:
            return None
        state = self._manager.hass.states.get(entity_id)
        if state is None:
            return None
        name = str(state.state or "").strip()
        if not name or name.lower() in {"unknown", "unavailable", "none", "null"}:
            return None

        signal_slug = slugify_room_name(name)
        target_ids = {
            _safe_int(rid, -1) for rid in active_job.get("queue_room_ids", [])
        }
        target_ids.discard(-1)

        for source in (
            active_job.get("resolved_rooms", []),
            active_job.get("queue_rooms", []),
        ):
            for room in source:
                room_id = _safe_int(room.get("room_id", room.get("id", -1)), -1)
                if room_id < 0 or room_id not in target_ids:
                    continue
                room_slug = (
                    str(room.get("slug") or "").strip().lower()
                    or slugify_room_name(
                        str(room.get("name") or room.get("room_name") or "")
                    )
                )
                if room_slug and room_slug == signal_slug:
                    return room_id
        return None

    def _maybe_roll_current_room_by_native_signal(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        current_room_id: int | None,
        current_room_elapsed_minutes: float,
    ) -> dict[str, Any]:
        """Advance current_room from the brand's NATIVE live-room signal.

        The device cleans targets in its own optimized order, so this tracks the
        last natively-confirmed target on ``active_job["_native_current_room_id"]``
        and is order-agnostic:

          - first confirmed target -> ADOPT it (the initial current_room_id was a
            queue-order GUESS, never actually cleaned; completing it would be a
            phantom). No duplicate event when the guess was already right.
          - a DIFFERENT target -> the previous confirmed target is DONE: complete
            ONLY it and set current directly to the new target.
          - the same target -> no-op (idempotent, so the 5s tick re-reading the
            ~30s-polled signal never double-advances).

        Transit rooms (names not among the job targets) resolve to None -> ignored.
        Assumes rooms_unique_per_job (no revisits) — true for the brands that opt in.
        """
        signal_room_id = self._resolve_native_target_room_id(vacuum_entity_id, active_job)
        if signal_room_id is None:
            return active_job  # transit / dock / sentinel / unmatched -> ignore

        confirmed = _safe_int(active_job.get("_native_current_room_id", -1), -1)
        if signal_room_id == confirmed:
            return active_job  # still on the same target

        completed_ids = {
            _safe_int(rid, -1) for rid in active_job.get("completed_room_ids", [])
        }
        if signal_room_id in completed_ids:
            return active_job  # already finished (rooms_unique_per_job) -> ignore

        if confirmed < 0:
            if signal_room_id == _safe_int(current_room_id, -1):
                # Device started with the guessed room — confirm without a
                # duplicate EVENT_ROOM_STARTED (job-start already fired one), but
                # still push the room's live settings now that it's confirmed.
                active_job["_native_current_room_id"] = signal_room_id
                self._persist_active_job(vacuum_entity_id, map_id, active_job)
                self.apply_per_room_live_settings(
                    vacuum_entity_id, active_job.get("resolved_rooms", []), signal_room_id
                )
                return active_job
            # Adopted a DIFFERENT first room — complete nothing (the guess was
            # never cleaned), just move the live pointer to the real room.
            return self._set_native_current_room(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                active_job=active_job,
                new_room_id=signal_room_id,
                complete_room_id=None,
                elapsed_minutes=current_room_elapsed_minutes,
            )

        # Moved to a new target -> the previous confirmed target is done.
        return self._set_native_current_room(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            active_job=active_job,
            new_room_id=signal_room_id,
            complete_room_id=confirmed,
            elapsed_minutes=current_room_elapsed_minutes,
        )

    def _set_native_current_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        new_room_id: int,
        complete_room_id: int | None,
        elapsed_minutes: float,
    ) -> dict[str, Any]:
        """Complete the previous target (if any) + set current DIRECTLY to the
        device's actual next target; fire EVENT_ROOM_FINISHED / EVENT_ROOM_STARTED
        with ``source="native_signal"``."""
        completed_at = _iso_now()
        job = active_job

        if complete_room_id is not None and complete_room_id >= 0:
            finished_name = self._room_name_from_active_job(job, complete_room_id)
            # Reuse the completed-room bookkeeping (completed_room_ids + the
            # completed_rooms upsert/cap). record_completed_room also sequentially
            # derives a next current; we override it below with the device's real
            # next target.
            job = self.record_completed_room(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                room_id=complete_room_id,
                room_name=finished_name,
                actual_duration_minutes=elapsed_minutes,
                completed_at=completed_at,
                source="native_signal",
            )
            self._manager.hass.bus.async_fire(
                EVENT_ROOM_FINISHED,
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "job_id": job.get("job_id"),
                    "room_id": str(complete_room_id),
                    "room_name": finished_name,
                    "completed_at": completed_at,
                    "source": "native_signal",
                    "actual_duration_minutes": round(elapsed_minutes, 2),
                    "completed_room_ids": job.get("completed_room_ids", []),
                },
            )

        # Direct-set current to the signalled target (override any sequential
        # derive). This is the device's ACTUAL next room, not the queue's next.
        job["current_room_id"] = new_room_id
        job["current_room_started_at"] = completed_at
        job["current_room_paused_seconds"] = 0
        job["_native_current_room_id"] = new_room_id
        self._persist_active_job(vacuum_entity_id, map_id, job)

        self._manager.hass.bus.async_fire(
            EVENT_ROOM_STARTED,
            {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "job_id": job.get("job_id"),
                "room_id": str(new_room_id),
                "room_name": self._room_name_from_active_job(job, new_room_id),
                "started_at": completed_at,
                "source": "native_signal",
                "completed_room_ids": job.get("completed_room_ids", []),
            },
        )
        # Push the new room's live per-room device settings (e.g. Roborock fan).
        self.apply_per_room_live_settings(
            vacuum_entity_id, job.get("resolved_rooms", []), new_room_id
        )
        self._manager.hass.async_create_task(self._manager._async_save_logged())
        return job

    def _persist_active_job(
        self,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
    ) -> None:
        """Write one active-job dict back into runtime storage."""
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job

    def _per_room_live_setting_calls(
        self,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
        room_id: int | None,
    ) -> list[dict[str, Any]]:
        """Build the per-room live-setting service calls for one room.

        Returns a list of ``{"domain", "service", "data"}`` specs (or ``[]``).
        Each ``dispatch.per_room_live_settings`` entry names a canonical room
        field + a service; the value is that room's resolved per-room value,
        optionally value_map'd. An entry may name an ``options_key`` into the
        adapter ``vocabulary`` — the value is emitted only when it's one the brand
        accepts, so the Eufy-shaped default ("Max") is never sent to a
        lowercase-only Roborock ``set_fan_speed``. Empty for brands that declare
        none (e.g. Eufy, whose per-room settings ride the dispatch payload).
        """
        config = _get_adapter_config(vacuum_entity_id) or {}
        entries = config.get("dispatch", {}).get("per_room_live_settings") or []
        if not entries or room_id is None:
            return []
        vocabulary = config.get("vocabulary", {})

        target_id = _safe_int(room_id, -1)
        room = next(
            (
                r
                for r in (resolved_rooms or [])
                if _safe_int(r.get("room_id", r.get("id", -1)), -1) == target_id
            ),
            None,
        )
        if room is None:
            return []

        calls: list[dict[str, Any]] = []
        for entry in entries:
            field = entry.get("field")
            service = entry.get("service") or {}
            domain = service.get("domain")
            service_name = service.get("service")
            value_key = service.get("value_key")
            if not (field and domain and service_name and value_key):
                continue
            value = room.get(field)
            if value is None:
                continue
            value_map = entry.get("value_map") or {}
            wire_value = value_map.get(str(value), value)

            # Only push a value this brand actually accepts (guards the Eufy
            # default "Max" against a lowercase-only Roborock set_fan_speed).
            options_key = entry.get("options_key")
            if options_key:
                valid = {
                    str(o.get("value"))
                    for o in (vocabulary.get(options_key) or [])
                    if isinstance(o, dict)
                }
                if valid and str(wire_value) not in valid:
                    continue

            target_entity = service.get("target_entity_id") or vacuum_entity_id
            calls.append({
                "domain": domain,
                "service": service_name,
                "data": {"entity_id": target_entity, value_key: wire_value},
            })
        return calls

    def apply_per_room_live_settings(
        self,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
        room_id: int | None,
    ) -> None:
        """Fire-and-forget push of one room's per-room LIVE device settings.

        Used by the native current_room rollover (batch mode): the rollover is
        sync, so the service calls are scheduled and best-effort (a failed one is
        logged, never disrupts the run). For the sequenced (strict-order) path,
        ``apply_per_room_live_settings_awaited`` sets them BEFORE the phase's
        dispatch so each room starts at its own value with no poll lag.
        """
        for spec in self._per_room_live_setting_calls(
            vacuum_entity_id, resolved_rooms, room_id
        ):
            async def _call(_spec=spec) -> None:
                try:
                    await self._manager.hass.services.async_call(
                        _spec["domain"], _spec["service"], _spec["data"], blocking=True
                    )
                except Exception:  # pragma: no cover - best-effort live setting
                    _LOGGER.debug(
                        "per-room live setting %s.%s failed for %s",
                        _spec["domain"], _spec["service"], vacuum_entity_id, exc_info=True,
                    )

            self._manager.hass.async_create_task(_call())

    async def apply_per_room_live_settings_awaited(
        self,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
        room_id: int | None,
    ) -> None:
        """Awaited push — set one room's per-room live settings and WAIT.

        Used by the sequenced (strict-order) dispatch path so a phase's room
        settings (e.g. Roborock fan) are applied to the idle device BEFORE its
        segment is dispatched — each room starts at its own value immediately,
        without the ~30s current_room poll lag the rollover incurs. Per-room
        passes already ride the phase payload (``repeat``); this covers the
        settings that can't (fan, which is a global device setting on Roborock).
        Best-effort per call.
        """
        for spec in self._per_room_live_setting_calls(
            vacuum_entity_id, resolved_rooms, room_id
        ):
            try:
                await self._manager.hass.services.async_call(
                    spec["domain"], spec["service"], spec["data"], blocking=True
                )
            except Exception:  # pragma: no cover - best-effort live setting
                _LOGGER.debug(
                    "per-room live setting %s.%s failed for %s",
                    spec["domain"], spec["service"], vacuum_entity_id, exc_info=True,
                )

    def _access_graph_path(
        self,
        managed_rooms: dict[str, Any],
        from_room_id: int,
        to_room_id: int,
    ) -> list[int]:
        """Return intermediate room IDs on the access-graph path from → to.

        Performs a BFS over ``grants_access_to`` edges.  Returns only the
        rooms that lie *between* from_room_id and to_room_id (neither
        endpoint is included).  Returns [] when the rooms are directly
        adjacent or no path exists.
        """
        rooms = managed_rooms.get("rooms", managed_rooms)

        # Build adjacency map: room_id → [granted_room_id, ...]
        grants_map: dict[int, list[int]] = {}
        for room_id_key, room in rooms.items():
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room_id_key), -1)
            if room_id <= 0:
                continue
            raw_grants = room.get("grants_access_to") or []
            neighbors = [_safe_int(g, -1) for g in raw_grants if _safe_int(g, -1) > 0]
            grants_map[room_id] = neighbors

        if from_room_id not in grants_map:
            return []

        # BFS — track full paths so we can extract intermediate rooms.
        from collections import deque
        queue: deque[list[int]] = deque([[from_room_id]])
        visited: set[int] = {from_room_id}

        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == to_room_id:
                return path[1:-1]   # strip from/to endpoints
            for neighbor in grants_map.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return []   # no path found

    def _get_robot_position(self, vacuum_entity_id: str) -> tuple[float, float] | None:
        """Read the current robot X/Y from HA sensor entities.

        Returns (vx, vy) in the vacuum's native coordinate space, or None
        when the sensors are unavailable or report a non-numeric state.
        """
        caps = self._manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        entities = caps.get("entities", {})
        x_entity_id = entities.get("robot_position_x")
        y_entity_id = entities.get("robot_position_y")
        if not x_entity_id or not y_entity_id:
            return None

        x_state = self._manager.hass.states.get(x_entity_id)
        y_state = self._manager.hass.states.get(y_entity_id)
        if x_state is None or y_state is None:
            return None

        try:
            vx = float(x_state.state)
            vy = float(y_state.state)
        except (ValueError, TypeError):
            return None

        return (vx, vy)

    def _detect_transition_room_from_position(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        from_room_id: int | None,
        to_room_id: int | None,
    ) -> int | None:
        """Return the transition room the robot is currently in, or None.

        Called when the robot has finished a queued room (by timing) but has
        not yet entered the next queued room.  Walks the access-graph path
        between the two rooms and checks the robot's live position against
        each intermediate room's learned bounds.

        Returns None when:
        - robot position is unavailable
        - no transition path exists in the access graph
        - robot is not detected inside any transition room's bounds
        """
        if from_room_id is None or to_room_id is None:
            return None

        pos = self._get_robot_position(vacuum_entity_id)
        if pos is None:
            return None
        vx, vy = pos

        managed_rooms = self._manager.get_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        transition_ids = self._access_graph_path(managed_rooms, from_room_id, to_room_id)
        if not transition_ids:
            return None

        # Fetch room bounds from the mapping manager.
        mapping_manager = self._manager.hass.data.get(DOMAIN, {}).get("mapping_manager")
        if mapping_manager is None:
            return None

        try:
            bounds_snapshot = mapping_manager.get_room_bounds_snapshot(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        except Exception:
            _LOGGER.debug(  # pragma: no cover
                "EufyManager: failed to read room bounds for transition detection "
                "(vacuum=%s map=%s)",
                vacuum_entity_id,
                map_id,
            )
            return None

        map_rooms = bounds_snapshot.get("rooms", {})

        for t_id in transition_ids:
            bounds = map_rooms.get(str(t_id), {}).get("bounds")
            if not bounds:
                continue
            # Inline AABB check — mirrors MappingManager._point_in_bounds()
            if (
                bounds["min_x"] <= vx <= bounds["max_x"]
                and bounds["min_y"] <= vy <= bounds["max_y"]
            ):
                return t_id

        return None

    # -- summaries & display helpers -------------------------------------------

    def _job_status_summary(
        self,
        *,
        active_job: dict[str, Any],
        lifecycle_state: dict[str, Any] | None = None,
        progress_snapshot: dict[str, Any] | None = None,
    ) -> str:
        """Return a concise card-facing job summary."""
        lifecycle_state = lifecycle_state or {}
        progress_snapshot = progress_snapshot or {}
        status = str(active_job.get("status", "idle")).strip().lower()
        room_name = self._room_name_from_active_job(
            active_job,
            _safe_int(progress_snapshot.get("current_room_id", active_job.get("current_room_id")), -1),
        )

        if status == "paused":
            return f"Paused in {room_name}" if room_name else "Job paused"
        if status == "started":
            return f"Cleaning {room_name}" if room_name else "Cleaning in progress"
        if status == "completed":
            outcome_status = (
                str(active_job.get("finalize_summary", {}).get("status", "")).strip().lower()
            )
            if outcome_status == "cancelled":
                return "Job cancelled"
            if outcome_status == "failed":
                return "Job failed"
            if outcome_status == "interrupted":
                return "Job interrupted"
            return "Job completed"

        lifecycle_name = str(lifecycle_state.get("lifecycle_state", "")).strip().lower()
        if lifecycle_name == "ready":
            return "Ready to start"
        if lifecycle_name == "dock_drying":
            return "Dock drying"
        return str(lifecycle_state.get("message", "")).strip() or "Idle"

    def _generate_job_id(self) -> str:
        """Generate stable job id."""
        return f"job_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"

    # -- sensor update listeners -----------------------------------------------

    def add_update_listener(
        self, cb: Callable[[str, str], None]
    ) -> Callable[[], None]:
        """Register a callback fired with (vacuum_entity_id, map_id) on job
        status transitions (pause, resume, finalize, clear).

        Returns an unregister callable — same pattern as ErrorTracker.
        """
        self._update_listeners.append(cb)

        def _unsub() -> None:
            try:
                self._update_listeners.remove(cb)
            except ValueError:
                pass

        return _unsub

    def _notify(self, vacuum_entity_id: str, map_id: str) -> None:
        """Fan out a status-change notification to all registered listeners."""
        for cb in list(self._update_listeners):
            try:
                cb(vacuum_entity_id, str(map_id))
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("active_job: update listener raised")


    # -- job lifecycle CRUD ----------------------------------------------------

    def record_active_lifecycle_observed(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Set ``has_observed_active_lifecycle`` on the stored active-job record.

        This flag is the pre-condition for auto-finalization.  Callers that
        hold a local copy returned by ``get_active_job()`` should set the flag
        on their copy too, since ``get_active_job()`` returns a normalized copy
        rather than a live reference.
        """
        self._manager.data.setdefault("active_jobs", {}).setdefault(vacuum_entity_id, {})
        active_job = self._manager.data["active_jobs"][vacuum_entity_id].get(str(map_id))
        if not isinstance(active_job, dict):
            return
        active_job["has_observed_active_lifecycle"] = True
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job

    def get_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return active job state for one vacuum/map."""
        return self._normalize_active_job((
            self._manager.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(
                str(map_id),
                self._default_active_job_state(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                ),
            )
        ))

    def record_active_job_sensor_value(
        self,
        *,
        vacuum_entity_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Write a sensor-derived value into all in-flight active jobs for a vacuum.

        Writes to every map bucket that has a started_at and no ended_at —
        normally only one bucket is active at a time, but the loop is
        defensive. Returns True if at least one job was updated.

        Called from the job-metrics state listener in __init__.py whenever
        a tracked sensor (cleaning_time, cleaning_area, etc.) changes during
        a run. Finalization then reads from active_job_state instead of
        issuing a live HA state read at job-end, avoiding the DPS timing race.
        """
        per_map = self._manager.data.get("active_jobs", {}).get(vacuum_entity_id, {})
        if not isinstance(per_map, dict):
            return False
        updated = False
        for job in per_map.values():
            if not isinstance(job, dict):
                continue
            if job.get("started_at") and not job.get("ended_at"):
                job[key] = value
                updated = True
        if updated:
            try:
                self._manager.hass.async_create_task(self._manager.async_save())
            except Exception:
                pass
        return updated

    def record_counter_sample(
        self,
        *,
        vacuum_entity_id: str,
        observed_at: str | None = None,
    ) -> bool:
        """Append a counter sample to each in-flight job's counter_samples buffer.

        Called from the job-metrics listener whenever sensor.<vacuum>_cleaning_time
        or _cleaning_area changes. Snapshots the last-seen cleaning_time +
        cleaning_area (+ battery) — already pushed by record_active_job_sensor_value
        — as one time-stamped sample. counter_segmentation.segment_counters() turns
        the stream into per-room segments at finalization (frame-invariant — no
        geometry). Returns True if at least one job was updated.
        """
        observed = observed_at or _iso_now()
        per_map = self._manager.data.get("active_jobs", {}).get(vacuum_entity_id, {})
        if not isinstance(per_map, dict):
            return False
        updated = False
        for job in per_map.values():
            if not isinstance(job, dict):
                continue
            if not (job.get("started_at") and not job.get("ended_at")):
                continue
            ct = job.get("last_cleaning_time_seconds")
            ca = job.get("last_cleaning_area_m2")
            if ct is None and ca is None:
                continue
            samples = job.setdefault("counter_samples", [])
            samples.append(
                {
                    "t": observed,
                    "cleaning_time": ct,
                    "cleaning_area": ca,
                    "battery": job.get("last_battery_percent"),
                }
            )
            if len(samples) > _MAX_COUNTER_SAMPLES:
                del samples[: len(samples) - _MAX_COUNTER_SAMPLES]
            # External runs: also snapshot the per-room setting selects (deduped —
            # one entry per flip), our only window into what the app set per room.
            if job.get("status") == "external":
                settings = self._snapshot_settings_selects(vacuum_entity_id)
                if settings:
                    ss = job.setdefault("settings_samples", [])
                    if not ss or ss[-1].get("settings") != settings:
                        ss.append({"t": observed, "settings": settings})
                        if len(ss) > _MAX_COUNTER_SAMPLES:
                            del ss[: len(ss) - _MAX_COUNTER_SAMPLES]
            updated = True
        if updated:
            try:
                self._manager.hass.async_create_task(self._manager.async_save())
            except Exception:
                pass
        return updated

    def _snapshot_settings_selects(self, vacuum_entity_id: str) -> dict[str, str]:
        """Read the adapter's ``settings_selects`` entities → a settings dict.

        External-run only: these global selects mirror the current room's settings
        while the app runs a job. ``value_map`` normalizes raw firmware strings to
        the canonical vocabulary (clean_mode); other keys keep the raw select state
        (normalized downstream). Absent / unavailable entities are skipped; returns
        ``{}`` when the adapter declares no settings_selects.
        """
        cfg = _get_adapter_config(vacuum_entity_id) or {}
        selects = cfg.get("settings_selects", {})
        if not isinstance(selects, dict):
            return {}
        hass = self._manager.hass
        out: dict[str, str] = {}
        for key, spec in selects.items():
            if not isinstance(spec, dict):
                continue
            entity_id = spec.get("entity_id")
            if not entity_id:
                continue
            state_obj = hass.states.get(entity_id)
            raw = getattr(state_obj, "state", None)
            if raw in (None, "", "unknown", "unavailable"):
                continue
            value_map = spec.get("value_map")
            if isinstance(value_map, dict):
                out[key] = value_map.get(str(raw).strip().lower(), str(raw))
            else:
                out[key] = str(raw)
        return out

    def start_external_capture(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Open a capture-only slot for an app-started (external) run.

        Seeds a default slot with ``status="external"`` + ``started_at`` so the
        metrics listener treats it as in-flight — record_active_job_sensor_value
        and record_counter_sample buffer the counters + setting selects into it.
        There is no queue or payload: we did not dispatch it, so room identity is
        unknown and is resolved by the user in review when the pending record is
        finalized.
        """
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        slot = self._default_active_job_state(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id
        )
        slot["status"] = "external"
        slot["started_at"] = _iso_now()
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = slot
        self._notify(vacuum_entity_id, str(map_id))
        return slot

    def clear_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Clear active job state for one vacuum/map."""
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = self._default_active_job_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.active_job_room_ids = []
        self._notify(vacuum_entity_id, str(map_id))

        return self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

    def pause_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        paused_at: str | None = None,
    ) -> dict[str, Any]:
        """Mark one active job as paused without losing elapsed runtime."""
        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        if active_job.get("status") != "started":
            return active_job

        active_job["status"] = "paused"
        active_job["paused_at"] = paused_at or _iso_now()
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        self._notify(vacuum_entity_id, str(map_id))
        return active_job

    def resume_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        resumed_at: str | None = None,
    ) -> dict[str, Any]:
        """Resume one paused job and accumulate paused wall-clock time."""
        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        if active_job.get("status") != "paused":
            return active_job

        resumed_at_str = resumed_at or _iso_now()
        paused_seconds = _safe_int(active_job.get("paused_duration_seconds"), 0)
        paused_at_str = str(active_job.get("paused_at", "")).strip()
        paused_dt = self._parse_job_timestamp(paused_at_str)
        resumed_dt = self._parse_job_timestamp(resumed_at_str)
        if paused_dt is not None and resumed_dt is not None:
            pause_delta_seconds = max(int((resumed_dt - paused_dt).total_seconds()), 0)
            paused_seconds += pause_delta_seconds
            active_job["current_room_paused_seconds"] = max(
                _safe_int(active_job.get("current_room_paused_seconds"), 0) + pause_delta_seconds,
                0,
            )

        active_job["status"] = "started"
        active_job["paused_at"] = None
        active_job["paused_duration_seconds"] = paused_seconds
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        self._notify(vacuum_entity_id, str(map_id))
        return active_job

    def record_completed_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_name: str | None = None,
        actual_duration_minutes: float | None = None,
        completed_at: str | None = None,
        source: str = "event",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Record one room as completed for the tracked active job."""
        active_job = self._normalize_active_job(
            self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        )
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        normalized_room_id = _safe_int(room_id, -1)
        if normalized_room_id < 0:
            return active_job

        completed_ids = [
            _safe_int(existing_room_id, -1)
            for existing_room_id in active_job.get("completed_room_ids", [])
            if _safe_int(existing_room_id, -1) >= 0
        ]
        if normalized_room_id not in completed_ids:
            completed_ids.append(normalized_room_id)
        active_job["completed_room_ids"] = completed_ids

        # Upsert: strip any existing entry for this room then append the new one.
        # De-duplication bounds the list to at most one entry per unique room ID,
        # so the safety cap below matches the job's own room count.
        _queue_room_count = len(active_job.get("queue_room_ids") or [])
        _completed_rooms_cap = max(_queue_room_count + 1, 20)

        completed_rooms = [
            dict(entry)
            for entry in active_job.get("completed_rooms", [])
            if _safe_int(entry.get("room_id", -1), -1) != normalized_room_id
        ]
        entry = {
            "room_id": normalized_room_id,
            "slug": None,
            "room_name": room_name,
            "completed_at": completed_at or _iso_now(),
            "source": source,
        }
        if actual_duration_minutes is not None:
            entry["actual_duration_minutes"] = round(float(actual_duration_minutes), 2)
        if confidence is not None:
            entry["confidence"] = round(float(confidence), 4)
        completed_rooms.append(entry)
        active_job["completed_rooms"] = completed_rooms[-_completed_rooms_cap:]

        next_room_id = self._derive_active_job_current_room_id(active_job)
        active_job["current_room_id"] = next_room_id
        active_job["current_room_started_at"] = (completed_at or _iso_now()) if next_room_id is not None else None
        active_job["current_room_paused_seconds"] = 0
        active_job["paused_at"] = None if active_job.get("status") != "paused" else active_job.get("paused_at")

        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    # -- finalization & async orchestration ------------------------------------

    def mark_active_job_finalized(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        finalize_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Mark one tracked job finalized in runtime storage."""
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        active_job = self._manager.data["active_jobs"][vacuum_entity_id].get(str(map_id), {})
        if not isinstance(active_job, dict):
            active_job = {}

        active_job["status"] = "completed"
        active_job["finalized"] = True
        active_job["paused_at"] = None
        active_job["has_observed_active_lifecycle"] = False
        active_job["finalized_at"] = (
            finalize_result.get("completed_job", {}).get("finalized_at")
            if isinstance(finalize_result, dict)
            else None
        )
        if isinstance(finalize_result, dict):
            active_job["finalize_summary"] = {
                "job_id": finalize_result.get("job_id"),
                "job_path": finalize_result.get("job_path"),
                "used_for_learning": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("used_for_learning")
                ),
                "sanity_passed": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("sanity_passed")
                ),
                "sanity_flags": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("sanity_flags")
                ),
                "learning_blockers": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("learning_blockers")
                ),
                "status": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("status")
                ),
            }

        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        runtime = self._manager.ensure_runtime(vacuum_entity_id)
        runtime.active_job_room_ids = []
        self._notify(vacuum_entity_id, str(map_id))
        return active_job

    async def async_pause_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Pause the vacuum and mark the tracked job paused."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") != "started":
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "paused": False,
                "reason": "no_started_job",
                "active_job": active_job,
            }

        await self._manager.hass.services.async_call(
            "vacuum",
            "pause",
            {"entity_id": vacuum_entity_id},
            blocking=True,
        )
        paused_job = self.pause_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "paused": True,
            "reason": "paused",
            "active_job": paused_job,
        }

    async def async_resume_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Resume the vacuum and the tracked paused job."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") != "paused":
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "resumed": False,
                "reason": "no_paused_job",
                "active_job": active_job,
            }

        await self._manager.hass.services.async_call(
            "vacuum",
            "start",
            {"entity_id": vacuum_entity_id},
            blocking=True,
        )
        resumed_job = self.resume_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "resumed": True,
            "reason": "resumed",
            "active_job": resumed_job,
        }

    # How long to wait for the device to reach a terminal state after return_to_base.
    _CANCEL_CONFIRM_TIMEOUT_S: int = 30
    _CANCEL_POLL_INTERVAL_S: float = 2.0

    async def async_cancel_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        forced_lifecycle_state: str | None = None,
        forced_lifecycle_message: str | None = None,
        cancel_reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel one tracked job by returning the vacuum to base and finalizing.

        After ``return_to_base``, polls for a terminal device state (docked /
        idle / task_status Completed) before writing the learning finalization
        record.  This prevents recording a "cancelled" outcome against a
        still-running session.  If the device does not confirm within
        ``_CANCEL_CONFIRM_TIMEOUT_S`` seconds, logs a warning and finalizes
        anyway so the active-job snapshot is never stuck in "started".
        """
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "cancelled": False,
                "reason": "no_active_job",
                "active_job": active_job,
            }

        await self._manager.hass.services.async_call(
            "vacuum",
            "return_to_base",
            {"entity_id": vacuum_entity_id},
            blocking=True,
        )

        task_status_entity_id = (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("task_status")
        deadline = self._manager.hass.loop.time() + self._CANCEL_CONFIRM_TIMEOUT_S
        confirmed = False
        last_vac_state: str | None = None
        last_task_status: str | None = None

        while self._manager.hass.loop.time() < deadline:
            await asyncio.sleep(self._CANCEL_POLL_INTERVAL_S)
            vac_state_obj = self._manager.hass.states.get(vacuum_entity_id)
            last_vac_state = vac_state_obj.state if vac_state_obj else None
            task_state_obj = (
                self._manager.hass.states.get(task_status_entity_id)
                if task_status_entity_id
                else None
            )
            last_task_status = task_state_obj.state if task_state_obj else None
            task_lower = str(last_task_status or "").strip().lower()

            if last_vac_state in {"docked", "idle"} or task_lower in {"completed", "complete"}:
                confirmed = True
                break

        if not confirmed:
            _LOGGER.warning(
                "async_cancel_active_job: %s did not reach a terminal state within %ds "
                "— finalizing anyway (task_status=%s, vacuum_state=%s)",
                vacuum_entity_id,
                self._CANCEL_CONFIRM_TIMEOUT_S,
                last_task_status,
                last_vac_state,
            )

        finalize_result = await self._manager.finalize_learning_for_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            rebuild_stats=True,
            rebuild_csv=False,
            forced_outcome_status="cancelled",
            forced_lifecycle_state=forced_lifecycle_state or "job_cancelled",
            forced_lifecycle_message=(
                forced_lifecycle_message or "Job was cancelled by return_to_base."
            ),
        )
        self.mark_active_job_finalized(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            finalize_result=finalize_result,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "cancelled": True,
            "confirmed": confirmed,
            "reason": str(cancel_reason or "cancelled"),
            "finalize_result": finalize_result,
        }

    def get_paused_job_timeout_report(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        now: str | None = None,
    ) -> dict[str, Any] | None:
        """Return a timeout report if a paused job has exceeded its limit."""
        active_job = self._normalize_active_job(
            self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        )
        if active_job.get("status") != "paused":
            return None

        pause_timeout_minutes = _normalize_pause_timeout_minutes(
            active_job.get("pause_timeout_minutes")
        )
        if pause_timeout_minutes <= 0:
            return None

        paused_at = str(active_job.get("paused_at", "")).strip()
        paused_dt = self._parse_job_timestamp(paused_at)
        now_dt = self._parse_job_timestamp(now or _iso_now())
        if paused_dt is None or now_dt is None:
            return None

        paused_elapsed_seconds = max(int((now_dt - paused_dt).total_seconds()), 0)
        pause_timeout_seconds = pause_timeout_minutes * 60
        if paused_elapsed_seconds < pause_timeout_seconds:
            return None

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "job_id": active_job.get("job_id"),
            "pause_timeout_minutes": pause_timeout_minutes,
            "paused_at": paused_at,
            "paused_elapsed_seconds": paused_elapsed_seconds,
            "forced_lifecycle_state": "pause_timeout_cancelled",
            "forced_lifecycle_message": (
                f"Paused for over {pause_timeout_minutes} minutes. Job canceled."
            ),
            "cancel_reason": "pause_timeout",
        }
