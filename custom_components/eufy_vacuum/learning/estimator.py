"""Learning-based estimator for Vacuum Agent.

============================================================
ESTIMATION ENGINE
============================================================

PURPOSE
-------
Single source of truth for all estimation logic:
- per-room timing, battery, confidence, and ETA
- job-level overhead modeling
- confidence breakpoints for UI rendering
- cumulative room timeline
- timeline reanchoring from actual completed room durations
- stale estimate detection
- per-room learning velocity

ARCHITECTURE
------------
This module is pure computation — it takes normalized inputs and returns
structured estimate payloads. It has no HA dependencies beyond the
history store reads. All orchestration lives in manager.py.

CONFIDENCE MODEL
----------------
Per-room confidence is scored on a 0.0–1.0 scale:

  base score:
    learned match  → 0.55
    default        → 0.20

  sample bonus:          up to +0.25 (saturates at 10 samples)
  variance penalty:      up to -0.25 (based on coefficient of variation)
  intensity mismatch:         -0.15  (match found at different clean_intensity)
  accuracy penalty:      up to -0.20 (based on historical estimate drift)

  final score = clamp(base + bonuses - penalties, 0.0, 1.0)

Job confidence = min(room_confidence_scores) — the weakest room drives
the job estimate. This is a hard architectural rule.

OVERHEAD MODEL
--------------
Overhead scales with room count and total workload:
  startup:     fixed 1.0 min
  transitions: 0.75 min per room boundary (room_count - 1)
  recharge:    scales with total battery estimate
  mop wash:    scales with projected mop runtime when wash mode is "By Time"
  dust empty:  scales with total duration
  return:      fixed 1.0 min

BREAKPOINTS
-----------
  HIGH:   0.80–1.00  ui_rank=3  ui_variant="success"
  MEDIUM: 0.50–0.79  ui_rank=2  ui_variant="warning"
  LOW:    0.00–0.49  ui_rank=1  ui_variant="error"

LEARNING VELOCITY
-----------------
Exposes how many more runs are needed per room to reach MEDIUM and HIGH
confidence thresholds, giving the card a "3 more runs to reliable estimate"
signal.

STALE DETECTION
---------------
If the last stats rebuild is older than STALE_THRESHOLD_DAYS, the estimate
payload includes stats_stale=True so the card can warn the user.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .history_store import LearningHistoryStore
from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..timestamp_utils import datetime_to_utc_iso, parse_timestamp, utc_now
from .utils import _iso_now, _room_key, _safe_float, _safe_int


# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Confidence scoring
_LEARNED_BASE = 0.55
_DEFAULT_BASE = 0.20
_SAMPLE_BONUS_MAX = 0.25
_SAMPLE_BONUS_SATURATE = 10          # samples needed to reach full bonus
_VARIANCE_PENALTY_MAX = 0.25
_VARIANCE_PENALTY_CV_THRESHOLD = 0.5 # CV above which full penalty applies
_INTENSITY_MISMATCH_PENALTY = 0.15   # match found at different clean_intensity
_ACCURACY_PENALTY_MAX = 0.20         # max penalty from historical drift
_ACCURACY_PENALTY_THRESHOLD = 0.20   # drift ratio above which full penalty applies

# Overhead modeling
_STARTUP_MINUTES = 1.0
_TRANSITION_PER_ROOM = 0.75          # per room boundary
_RECHARGE_PER_BATTERY_PCT = 0.05     # minutes per 1% battery used
_DEFAULT_MOP_WASH_CYCLE_MINUTES = 1.5  # minutes per configured mop wash cycle
_DEFAULT_WASH_INTERVAL_MINUTES = 20.0     # fallback if by-time mode has no readable number state
_DUST_EMPTY_PER_10_MIN = 0.3         # minutes per 10 job minutes
_RETURN_MINUTES = 1.0

# Fallback defaults
_DEFAULT_ROOM_MINUTES = 6.0
_DEFAULT_BATTERY_PER_ROOM = 0.8

# Stale detection
_STALE_THRESHOLD_DAYS = 30

# Confidence breakpoints
_BREAKPOINTS: list[dict[str, Any]] = [
    {
        "key": "high",
        "min_score": 0.80,
        "max_score": 1.00,
        "ui_rank": 3,
        "ui_variant": "success",
    },
    {
        "key": "medium",
        "min_score": 0.50,
        "max_score": 0.79,
        "ui_rank": 2,
        "ui_variant": "warning",
    },
    {
        "key": "low",
        "min_score": 0.00,
        "max_score": 0.49,
        "ui_rank": 1,
        "ui_variant": "error",
    },
]

# Samples needed to reach each confidence tier (used for learning velocity).
# Derived by solving: base + (n/SATURATE)*BONUS_MAX >= threshold
# These are approximate — computed analytically from the scoring formula
# assuming zero variance and no penalties.
_SAMPLES_FOR_MEDIUM = math.ceil(
    (_BREAKPOINTS[1]["min_score"] - _LEARNED_BASE) / _SAMPLE_BONUS_MAX * _SAMPLE_BONUS_SATURATE
)
_SAMPLES_FOR_HIGH = math.ceil(
    (_BREAKPOINTS[0]["min_score"] - _LEARNED_BASE) / _SAMPLE_BONUS_MAX * _SAMPLE_BONUS_SATURATE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _eta_at(base_dt: datetime, offset_minutes: float) -> str:
    """Return ISO timestamp for base_dt + offset_minutes."""
    return datetime_to_utc_iso(base_dt + timedelta(minutes=offset_minutes))


def _breakpoint_for_score(score: float) -> dict[str, Any]:
    """Return the confidence breakpoint dict for a given score."""
    for bp in _BREAKPOINTS:
        if bp["min_score"] <= score <= bp["max_score"]:
            return dict(bp)
    return dict(_BREAKPOINTS[-1])


def _confidence_result(score: float) -> dict[str, Any]:
    """Return a complete confidence result dict for a given score."""
    clamped = round(max(0.0, min(1.0, score)), 4)
    bp = _breakpoint_for_score(clamped)
    return {
        "confidence_score": clamped,
        "confidence_label": bp["key"],
        "confidence_breakpoint": bp,
    }




def _normalize_wash_frequency_mode(
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
) -> str:
    """Normalize wash frequency mode strings into stable estimator keys.

    aliases — brand-specific display string → canonical key map, sourced
    from adapter_config.vocabulary.wash_frequency_mode_aliases. Pass None
    when aliases are unavailable; canonical keys pass through unchanged.
    """
    raw = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    compact = " ".join(raw.split())

    if not compact:
        return "unknown"
    # Adapter alias lookup.
    if aliases:
        mapped = aliases.get(compact)
        if mapped is not None:
            return mapped
    # Unknown values pass through with spaces replaced by underscores.
    return compact.replace(" ", "_")


def _load_mop_wash_config(*, hass: HomeAssistant, vacuum_entity_id: str) -> dict[str, Any]:
    """Read mop wash cadence configuration from Home Assistant state.

    Entity IDs are resolved from the adapter registry — adapters that don't
    expose wash-frequency helpers simply yield ``None`` here and the
    estimator falls back to a safe default interval so ETA math remains
    stable. The current implementation only models the "By Time" mode.
    """
    _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
    _entities = _adapter_cfg.get("entities", {})
    mode_entity_id: str | None = _entities.get("wash_frequency_mode")
    interval_entity_id: str | None = _entities.get("wash_frequency_value_time")

    mode_state = hass.states.get(mode_entity_id) if mode_entity_id else None
    interval_state = hass.states.get(interval_entity_id) if interval_entity_id else None

    _vocab = _adapter_cfg.get("vocabulary", {})
    _wash_freq_aliases: dict[str, str] = _vocab.get("wash_frequency_mode_aliases") or {}
    mode_key = _normalize_wash_frequency_mode(
        mode_state.state if mode_state else None,
        aliases=_wash_freq_aliases,
    )
    interval_minutes = _safe_float(
        interval_state.state if interval_state else None,
        _DEFAULT_WASH_INTERVAL_MINUTES,
    )

    if interval_minutes <= 0:
        interval_minutes = _DEFAULT_WASH_INTERVAL_MINUTES

    # Respect the configured helper bounds when possible so bad state does
    # not explode ETA calculations.
    interval_minutes = max(15.0, min(25.0, interval_minutes))

    return {
        "mode_entity_id": mode_entity_id,
        "interval_entity_id": interval_entity_id,
        "mode": mode_key,
        "interval_minutes": round(interval_minutes, 2),
        "mode_available": mode_state is not None,
        "interval_available": interval_state is not None,
    }

def _parse_iso(value: str | None) -> datetime | None:
    """Parse ISO timestamp string to datetime, returning None on failure."""
    return parse_timestamp(value)


# ---------------------------------------------------------------------------
# Learning velocity
# ---------------------------------------------------------------------------

def _learning_velocity(sample_count: int, current_score: float) -> dict[str, Any]:
    """Return how many more runs are needed to reach MEDIUM and HIGH.

    Uses the analytical sample targets computed from the scoring formula.
    If already at or above a tier, returns 0 for that tier.
    """
    runs_to_medium = max(_SAMPLES_FOR_MEDIUM - sample_count, 0)
    runs_to_high = max(_SAMPLES_FOR_HIGH - sample_count, 0)

    current_bp = _breakpoint_for_score(current_score)

    return {
        "runs_to_medium": runs_to_medium,
        "runs_to_high": runs_to_high,
        "current_tier": current_bp["key"],
    }


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _score_room_confidence(
    *,
    source: str,
    sample_count: int,
    avg_minutes: float,
    minutes_stddev: float,
    intensity_mismatch: bool = False,
    accuracy_drift_ratio: float = 0.0,
) -> float:
    """Compute per-room confidence score (0.0–1.0).

    Model:
      base             = 0.55 (learned) or 0.20 (default)
      sample_bonus     = min(sample_count / SATURATE, 1.0) * BONUS_MAX
      variance_penalty = clamp(cv / CV_THRESHOLD, 0.0, 1.0) * PENALTY_MAX
      intensity_penalty = 0.15 if match was on different intensity
      accuracy_penalty = clamp(drift_ratio / THRESHOLD, 0.0, 1.0) * PENALTY_MAX

    accuracy_drift_ratio is the mean absolute percentage error of past
    estimates for this room — 0.0 means perfect, 0.20 means 20% off on
    average. Above ACCURACY_PENALTY_THRESHOLD the full penalty applies.
    """
    base = _LEARNED_BASE if source == "learned" else _DEFAULT_BASE

    sample_bonus = min(sample_count / _SAMPLE_BONUS_SATURATE, 1.0) * _SAMPLE_BONUS_MAX

    if source == "learned" and avg_minutes > 0 and minutes_stddev > 0:
        cv = minutes_stddev / avg_minutes
        variance_penalty = min(cv / _VARIANCE_PENALTY_CV_THRESHOLD, 1.0) * _VARIANCE_PENALTY_MAX
    else:
        variance_penalty = 0.0

    intensity_penalty = _INTENSITY_MISMATCH_PENALTY if intensity_mismatch else 0.0

    accuracy_penalty = (
        min(accuracy_drift_ratio / _ACCURACY_PENALTY_THRESHOLD, 1.0) * _ACCURACY_PENALTY_MAX
        if accuracy_drift_ratio > 0
        else 0.0
    )

    return max(0.0, min(1.0,
        base + sample_bonus - variance_penalty - intensity_penalty - accuracy_penalty
    ))


# ---------------------------------------------------------------------------
# Overhead modeling
# ---------------------------------------------------------------------------

def _compute_overhead(
    *,
    room_count: int,
    room_minutes_total: float,
    total_battery_estimate: float,
    projected_mop_minutes: float,
    mop_wash_config: dict[str, Any],
) -> dict[str, Any]:
    """Compute job overhead breakdown.

    Mop wash cycles are driven by cumulative projected mop minutes against
    the configured dock cadence (select.<vacuum>_wash_frequency_mode /
    number.<vacuum>_wash_frequency_value_time), not by room count.
    """
    startup = _STARTUP_MINUTES
    transitions = max(room_count - 1, 0) * _TRANSITION_PER_ROOM
    recharge = total_battery_estimate * _RECHARGE_PER_BATTERY_PCT
    dust_empty = (room_minutes_total / 10.0) * _DUST_EMPTY_PER_10_MIN
    return_to_dock = _RETURN_MINUTES

    wash_mode = str(mop_wash_config.get("mode", "unknown"))
    wash_interval_minutes = _safe_float(
        mop_wash_config.get("interval_minutes"),
        _DEFAULT_WASH_INTERVAL_MINUTES,
    )
    wash_cycle_minutes = _DEFAULT_MOP_WASH_CYCLE_MINUTES

    if wash_mode == "by_time" and projected_mop_minutes > 0 and wash_interval_minutes > 0:
        wash_cycle_count = int(projected_mop_minutes // wash_interval_minutes)
    else:
        wash_cycle_count = 0

    mop_wash = wash_cycle_count * wash_cycle_minutes

    total = startup + transitions + recharge + mop_wash + dust_empty + return_to_dock

    return {
        "overhead_minutes": round(total, 2),
        "overhead": {
            "startup_minutes": round(startup, 2),
            "transition_minutes": round(transitions, 2),
            "recharge_minutes": round(recharge, 2),
            "mop_wash_minutes": round(mop_wash, 2),
            "dust_empty_minutes": round(dust_empty, 2),
            "return_minutes": round(return_to_dock, 2),
            "mop_wash": {
                "mode": wash_mode,
                "mode_entity_id": mop_wash_config.get("mode_entity_id"),
                "interval_entity_id": mop_wash_config.get("interval_entity_id"),
                "interval_minutes": round(wash_interval_minutes, 2),
                "projected_mop_minutes": round(projected_mop_minutes, 2),
                "cycle_count": wash_cycle_count,
                "minutes_per_cycle": round(wash_cycle_minutes, 2),
                "mode_available": bool(mop_wash_config.get("mode_available")),
                "interval_available": bool(mop_wash_config.get("interval_available")),
            },
        },
    }


# ---------------------------------------------------------------------------
# Room stat lookup
# ---------------------------------------------------------------------------

def _find_room_match(
    *,
    room_stats: list[dict[str, Any]],
    map_id: int,
    slug: str,
    clean_mode: str,
    clean_passes: int,
    is_carpet: bool,
    clean_intensity: str,
    edge_mopping: bool = False,
) -> tuple[dict[str, Any] | None, bool]:
    """Find best matching learned room stat.

    Returns (match, mismatch) where mismatch=True signals the match was found at
    a relaxed setting — the estimator applies a confidence penalty in that case.

    Lookup priority (most specific first; clean_passes and edge_mopping are kept
    longest because they move cleaning time the most, while is_carpet is ~constant
    per room and clean_intensity is the smallest effect):
    1. exact: all dimensions incl. clean_intensity and edge_mopping
    2. ignore clean_intensity
    3. ignore is_carpet
    4. ignore edge_mopping
    5. ignore clean_passes
    """
    def _base(item: dict[str, Any]) -> bool:
        return (
            _safe_int(item.get("map_id")) == map_id
            and item.get("room_slug") == slug
            and item.get("effective_mode") == clean_mode
        )

    def _passes(item: dict[str, Any]) -> bool:
        return _safe_int(item.get("clean_times")) == clean_passes

    def _carpet(item: dict[str, Any]) -> bool:
        return bool(item.get("is_carpet")) == is_carpet

    def _edge(item: dict[str, Any]) -> bool:
        return bool(item.get("edge_mopping", False)) == edge_mopping

    def _intensity(item: dict[str, Any]) -> bool:
        return str(item.get("clean_intensity", "standard")).strip().lower() == clean_intensity

    # Pass 1 — exact
    for item in room_stats:
        if _base(item) and _passes(item) and _carpet(item) and _edge(item) and _intensity(item):
            return item, False

    # Pass 2 — ignore intensity (keep passes, carpet, edge)
    for item in room_stats:
        if _base(item) and _passes(item) and _carpet(item) and _edge(item):
            return item, True

    # Pass 3 — ignore carpet (keep passes, edge)
    for item in room_stats:
        if _base(item) and _passes(item) and _edge(item):
            return item, True

    # Pass 4 — ignore edge_mopping (keep passes)
    for item in room_stats:
        if _base(item) and _passes(item):
            return item, True

    # Pass 5 — ignore passes
    for item in room_stats:
        if _base(item):
            return item, True

    return None, False


# ---------------------------------------------------------------------------
# Main estimator class
# ---------------------------------------------------------------------------

class LearningEstimator:
    """Estimate job runtime, confidence, and ETA using learned room data.

    Single source of truth for all estimation math. Always called through
    LearningManager — not directly.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = LearningHistoryStore(hass)

    # ------------------------------------------------------------------
    # Stale detection
    # ------------------------------------------------------------------

    def _is_stats_stale(
        self,
        *,
        vacuum_entity_id: str,
        room_stats_data: dict | None = None,
    ) -> bool:
        """Return True if the last stats rebuild is older than STALE_THRESHOLD_DAYS.

        Pass room_stats_data when it is already loaded to avoid a redundant
        disk read on the event loop.
        """
        if room_stats_data is None:
            room_stats_data = self.store.load_room_stats(vacuum_entity_id=vacuum_entity_id)
        if not room_stats_data:
            return True
        rebuilt_at = _parse_iso(room_stats_data.get("rebuilt_at"))
        if rebuilt_at is None:
            return True
        return (utc_now() - rebuilt_at).days > _STALE_THRESHOLD_DAYS

    # ------------------------------------------------------------------
    # Accuracy stats
    # ------------------------------------------------------------------

    def _load_accuracy_stats(self, *, vacuum_entity_id: str) -> dict[str, Any]:
        """Load per-room accuracy stats from the accuracy file."""
        data = self.store.load_accuracy_stats(vacuum_entity_id=vacuum_entity_id)
        return data if isinstance(data, dict) else {}

    def _drift_ratio_for_room(
        self,
        *,
        accuracy_stats: dict[str, Any],
        room_key: str,
    ) -> float:
        """Return mean absolute percentage error for a room key (0.0–1.0+).

        Returns 0.0 if no accuracy data exists for this room.
        """
        room_accuracy = accuracy_stats.get("rooms", {}).get(room_key, {})
        return _safe_float(room_accuracy.get("mean_abs_pct_error"), 0.0)

    def record_estimate_accuracy(
        self,
        *,
        vacuum_entity_id: str,
        room_actuals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Record estimated vs actual minutes per room after a job completes.

        Called by finalize_completed_job. Each entry in room_actuals must have:
          slug, clean_mode, clean_passes, is_carpet, clean_intensity,
          estimated_minutes, actual_minutes, map_id (and optionally edge_mopping,
          default off — it is part of the room key).

        Updates the running accuracy stats file with the new observations.
        Returns a summary of what was recorded.
        """
        existing = self.store.load_accuracy_stats(vacuum_entity_id=vacuum_entity_id) or {}
        rooms_data: dict[str, Any] = existing.get("rooms", {})

        recorded: list[dict[str, Any]] = []

        for entry in room_actuals:
            slug = str(entry.get("slug", "")).strip().lower()
            clean_mode = str(entry.get("clean_mode", "")).strip().lower()
            clean_passes = _safe_int(entry.get("clean_passes", 1), 1)
            is_carpet = bool(entry.get("is_carpet", False))
            clean_intensity = str(entry.get("clean_intensity", "standard")).strip().lower()
            edge_mopping = bool(entry.get("edge_mopping", False))
            map_id = _safe_int(entry.get("map_id", 0))
            estimated = _safe_float(entry.get("estimated_minutes"), 0.0)
            actual = _safe_float(entry.get("actual_minutes"), 0.0)

            if estimated <= 0 or actual <= 0:
                continue

            # Same key as the room stats (shared _room_key) so lookups align.
            room_key = _room_key(
                map_id, slug, clean_mode, clean_passes, is_carpet, clean_intensity, edge_mopping
            )

            pct_error = abs(actual - estimated) / estimated  # 0.0 = perfect
            is_single_room = bool(entry.get("single_room", False))

            if room_key not in rooms_data:
                rooms_data[room_key] = {
                    "slug": slug,
                    "clean_mode": clean_mode,
                    "clean_passes": clean_passes,
                    "is_carpet": is_carpet,
                    "clean_intensity": clean_intensity,
                    "map_id": map_id,
                    "sample_count": 0,
                    "single_room_sample_count": 0,
                    "total_abs_pct_error": 0.0,
                    "total_signed_error_minutes": 0.0,
                    "mean_abs_pct_error": 0.0,
                    "mean_signed_error_minutes": 0.0,
                    "last_updated": _iso_now(),
                }

            rec = rooms_data[room_key]
            rec["sample_count"] += 1
            if is_single_room:
                rec["single_room_sample_count"] = rec.get("single_room_sample_count", 0) + 1
            rec["total_abs_pct_error"] += pct_error
            rec["total_signed_error_minutes"] += (actual - estimated)
            n = rec["sample_count"]
            rec["mean_abs_pct_error"] = round(rec["total_abs_pct_error"] / n, 4)
            rec["mean_signed_error_minutes"] = round(rec["total_signed_error_minutes"] / n, 2)
            rec["last_updated"] = _iso_now()

            recorded.append({
                "room_key": room_key,
                "estimated_minutes": round(estimated, 2),
                "actual_minutes": round(actual, 2),
                "pct_error": round(pct_error, 4),
                "single_room": is_single_room,
                "mean_abs_pct_error_after": rec["mean_abs_pct_error"],
            })

        updated_payload = {
            "schema_version": 1,
            "vacuum_entity_id": vacuum_entity_id,
            "updated_at": _iso_now(),
            "rooms": rooms_data,
        }
        self.store.save_accuracy_stats(
            vacuum_entity_id=vacuum_entity_id,
            payload=updated_payload,
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "rooms_recorded": len(recorded),
            "detail": recorded,
        }

    # ------------------------------------------------------------------
    # Core estimate
    # ------------------------------------------------------------------

    def estimate(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        ordered_rooms: list[dict[str, Any]],
        started_at: str | None = None,
        current_battery: float = 0.0,
        charge_percent_per_minute: float = 1.0,
        reserve_battery_percent: float = 5.0,
    ) -> dict[str, Any]:
        """Compute a full job estimate from an ordered room list.

        Parameters
        ----------
        ordered_rooms:
            Rooms in execution order from the payload. Each must have:
            slug, clean_mode, clean_passes, clean_intensity, carpet, name, room_id.
        started_at:
            ISO timestamp of when the job started (or now if pre-start).
            Used as the ETA anchor.
        current_battery:
            Battery percentage at estimate time.
        """
        map_id_int = _safe_int(map_id)

        # Anchor time for ETA computation.
        anchor_dt = _parse_iso(started_at) or utc_now()

        # Load learned room stats and accuracy stats.
        room_stats_data = self.store.load_room_stats(vacuum_entity_id=vacuum_entity_id)
        room_stats: list[dict[str, Any]] = (
            room_stats_data.get("room_stats", []) if room_stats_data else []
        )
        accuracy_stats = self._load_accuracy_stats(vacuum_entity_id=vacuum_entity_id)

        # Stale detection.
        stats_stale = self._is_stats_stale(vacuum_entity_id=vacuum_entity_id)
        rebuilt_at = (room_stats_data or {}).get("rebuilt_at")

        # Guard: no rooms in payload — return a clear error rather than silent zeroes.
        if not ordered_rooms:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id_int,
                "room_count": 0,
                "estimated_at": _iso_now(),
                "started_at": started_at,
                "error": "no_payload",
                "error_detail": (
                    "No resolved rooms found. Run build_queue and build_room_payload "
                    "before requesting an estimate."
                ),
                "stats_stale": stats_stale,
                "stats_rebuilt_at": rebuilt_at,
                "can_run_now": False,
            }

        # ----------------------------------------------------------------
        # Per-room estimation
        # ----------------------------------------------------------------
        room_timeline: list[dict[str, Any]] = []
        cumulative_minutes = 0.0
        total_battery = 0.0
        projected_mop_minutes = 0.0
        room_confidence_scores: list[float] = []

        for position, room in enumerate(ordered_rooms):
            slug = str(room.get("slug", "")).strip().lower()
            clean_mode = str(room.get("clean_mode", "")).strip().lower()
            clean_passes = _safe_int(room.get("clean_passes", 1), 1)
            is_carpet = bool(room.get("carpet", False))
            clean_intensity = str(room.get("clean_intensity", "standard")).strip().lower()
            edge_mopping = bool(room.get("edge_mopping", False))
            room_name = str(room.get("name", slug))
            room_id = _safe_int(room.get("room_id", 0))

            is_mop = clean_mode in {"vacuum_mop", "mop"}

            match, intensity_mismatch = _find_room_match(
                room_stats=room_stats,
                map_id=map_id_int,
                slug=slug,
                clean_mode=clean_mode,
                clean_passes=clean_passes,
                is_carpet=is_carpet,
                clean_intensity=clean_intensity,
                edge_mopping=edge_mopping,
            )

            if match:
                minutes = _safe_float(match.get("avg_minutes"), _DEFAULT_ROOM_MINUTES)
                battery = _safe_float(match.get("avg_battery_used"), _DEFAULT_BATTERY_PER_ROOM)
                sample_count = _safe_int(match.get("sample_count"), 0)
                minutes_stddev = _safe_float(match.get("minutes_stddev"), 0.0)
                source = "learned"
                # Same room key (shared _room_key) for accuracy lookup.
                room_key = _room_key(
                    map_id_int, slug, clean_mode, clean_passes, is_carpet, clean_intensity, edge_mopping
                )
                drift_ratio = self._drift_ratio_for_room(
                    accuracy_stats=accuracy_stats,
                    room_key=room_key,
                )
            else:
                minutes = _DEFAULT_ROOM_MINUTES
                battery = _DEFAULT_BATTERY_PER_ROOM
                sample_count = 0
                minutes_stddev = 0.0
                intensity_mismatch = False
                drift_ratio = 0.0
                source = "default"

            confidence_score = _score_room_confidence(
                source=source,
                sample_count=sample_count,
                avg_minutes=minutes,
                minutes_stddev=minutes_stddev,
                intensity_mismatch=intensity_mismatch,
                accuracy_drift_ratio=drift_ratio,
            )
            room_confidence_scores.append(confidence_score)
            confidence = _confidence_result(confidence_score)
            velocity = _learning_velocity(sample_count, confidence_score)

            start_offset = cumulative_minutes
            cumulative_minutes += minutes
            end_offset = cumulative_minutes
            total_battery += battery
            if is_mop:
                projected_mop_minutes += minutes

            room_timeline.append(
                {
                    "position": position + 1,
                    "room_id": room_id,
                    "room_name": room_name,
                    "slug": slug,
                    "clean_mode": clean_mode,
                    "clean_passes": clean_passes,
                    "clean_intensity": clean_intensity,
                    "is_carpet": is_carpet,
                    "source": source,
                    "intensity_mismatch": intensity_mismatch,
                    "sample_count": sample_count,
                    "accuracy_drift_ratio": round(drift_ratio, 4),
                    "minutes": round(minutes, 2),
                    "battery": round(battery, 2),
                    "start_offset_minutes": round(start_offset, 2),
                    "end_offset_minutes": round(end_offset, 2),
                    "eta_minutes_from_start": round(end_offset, 2),
                    "eta_at": _eta_at(anchor_dt, end_offset),
                    "completed": False,
                    "current": False,
                    "remaining": True,
                    "skipped": False,
                    "progress_percent": 0,
                    "elapsed_minutes": 0.0,
                    "remaining_minutes": round(minutes, 2),
                    "learning_velocity": velocity,
                    **confidence,
                }
            )

        room_minutes_total = cumulative_minutes

        # ----------------------------------------------------------------
        # Overhead
        # ----------------------------------------------------------------
        mop_wash_config = _load_mop_wash_config(
            hass=self.hass,
            vacuum_entity_id=vacuum_entity_id,
        )
        overhead_result = _compute_overhead(
            room_count=len(ordered_rooms),
            room_minutes_total=room_minutes_total,
            total_battery_estimate=total_battery,
            projected_mop_minutes=projected_mop_minutes,
            mop_wash_config=mop_wash_config,
        )
        overhead_minutes = overhead_result["overhead_minutes"]
        total_minutes = room_minutes_total + overhead_minutes

        # ----------------------------------------------------------------
        # Job-level confidence — min of all room scores (hard rule)
        # ----------------------------------------------------------------
        if room_confidence_scores:
            job_confidence_score = min(room_confidence_scores)
            weighted_avg_score = round(
                sum(room_confidence_scores) / len(room_confidence_scores), 4
            )
        else:
            job_confidence_score = 0.0
            weighted_avg_score = 0.0

        job_confidence = _confidence_result(job_confidence_score)

        # ----------------------------------------------------------------
        # Job ETA
        # ----------------------------------------------------------------
        job_eta_at = _eta_at(anchor_dt, total_minutes)

        # ----------------------------------------------------------------
        # Battery readiness
        # ----------------------------------------------------------------
        required_start_battery = total_battery + reserve_battery_percent
        battery_shortfall = max(required_start_battery - current_battery, 0.0)
        estimated_charge_minutes = (
            battery_shortfall / charge_percent_per_minute
            if charge_percent_per_minute > 0
            else 0.0
        )
        mid_job_recharge_needed_battery = max(total_battery - current_battery, 0.0)
        mid_job_recharge_estimated_charge_minutes = (
            mid_job_recharge_needed_battery / charge_percent_per_minute
            if charge_percent_per_minute > 0
            else 0.0
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_int,
            "room_count": len(ordered_rooms),
            "estimated_at": _iso_now(),
            "started_at": started_at,
            "stats_stale": stats_stale,
            "stats_rebuilt_at": rebuilt_at,
            # Timing
            "room_minutes_total": round(room_minutes_total, 2),
            "overhead_minutes": overhead_result["overhead_minutes"],
            "overhead": overhead_result["overhead"],
            "total_minutes": round(total_minutes, 2),
            "job_eta_minutes": round(total_minutes, 2),
            "job_eta_at": job_eta_at,
            # Battery
            "total_battery_used": round(total_battery, 2),
            "required_start_battery": round(required_start_battery, 2),
            "battery_shortfall": round(battery_shortfall, 2),
            "estimated_charge_minutes": round(estimated_charge_minutes, 2),
            "remaining_battery_after_job": round(current_battery - total_battery, 2),
            "mid_job_recharge_risk": mid_job_recharge_needed_battery > 0,
            "mid_job_recharge_needed_battery": round(mid_job_recharge_needed_battery, 2),
            "mid_job_recharge_estimated_charge_minutes": round(mid_job_recharge_estimated_charge_minutes, 2),
            "projected_recharge_overhead_minutes": round(overhead_result["overhead"].get("recharge_minutes", 0.0), 2),
            # Battery is workflow-only: recharge/resume is allowed, so
            # low starting charge is a warning condition rather than a
            # start blocker. can_run_now is reserved for true hard-failure
            # estimate states such as missing payload / invalid requests.
            "can_run_now": True,
            "battery_warning": battery_shortfall > 0,
            # Job-level confidence
            **job_confidence,
            # Per-room breakdown
            "breakdown": room_timeline,
            "room_timeline": room_timeline,
            # Debug only — not for user-facing UI
            "_debug": {
                "weighted_avg_confidence_score": weighted_avg_score,
            },
        }

    # ------------------------------------------------------------------
    # Next room shortcut
    # ------------------------------------------------------------------

    def next_room(
        self,
        *,
        reanchored_estimate: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return the next incomplete room from a reanchored timeline.

        Returns a lightweight dict with just what the card needs for a
        "cleaning Kitchen, done at 3:47" display. Returns None if all
        rooms are complete.
        """
        timeline: list[dict[str, Any]] = reanchored_estimate.get("room_timeline", [])

        for room in timeline:
            if not room.get("completed", False):
                return {
                    "room_id": room.get("room_id"),
                    "room_name": room.get("room_name"),
                    "slug": room.get("slug"),
                    "position": room.get("position"),
                    "minutes": room.get("minutes"),
                    "eta_at": room.get("eta_at"),
                    "eta_minutes_from_start": room.get("eta_minutes_from_start"),
                    "confidence_score": room.get("confidence_score"),
                    "confidence_label": room.get("confidence_label"),
                    "confidence_breakpoint": room.get("confidence_breakpoint"),
                    "reanchored": room.get("reanchored", False),
                }

        return None

    # ------------------------------------------------------------------
    # Timeline reanchoring
    # ------------------------------------------------------------------

    def reanchor_timeline(
        self,
        *,
        original_estimate: dict[str, Any],
        completed_rooms: list[dict[str, Any]],
        reanchor_at: str | None = None,
        current_battery: float | None = None,
        charge_percent_per_minute: float = 1.0,
        reserve_battery_percent: float = 5.0,
    ) -> dict[str, Any]:
        """Recompute ETAs for remaining rooms using actual completed durations.

        Call each time eufy_vacuum_room_completed fires. Completed room
        actual durations replace estimates; remaining room ETAs are
        recomputed from the new elapsed total.

        Parameters
        ----------
        completed_rooms:
            List of finished rooms. Each entry must have:
            room_id OR slug, actual_duration_minutes.
        reanchor_at:
            ISO timestamp to anchor remaining ETAs from. Defaults to now.
        current_battery:
            If supplied, updates battery readiness for remaining rooms.
        """
        anchor_dt = _parse_iso(reanchor_at) or utc_now()

        # Build completed actuals lookup.
        completed_by_id: dict[int, float] = {}
        completed_by_slug: dict[str, float] = {}
        for entry in completed_rooms:
            actual = _safe_float(entry.get("actual_duration_minutes"), 0.0)
            room_id = _safe_int(entry.get("room_id", -1), -1)
            slug = str(entry.get("slug", "")).strip().lower()
            if room_id >= 0:
                completed_by_id[room_id] = actual
            if slug:
                completed_by_slug[slug] = actual

        original_timeline: list[dict[str, Any]] = original_estimate.get("room_timeline", [])

        started_at_str = original_estimate.get("started_at")
        job_start_dt = _parse_iso(started_at_str) or anchor_dt

        updated_timeline: list[dict[str, Any]] = []
        actual_elapsed = 0.0
        remaining_cursor = 0.0

        for room in original_timeline:
            room_id = _safe_int(room.get("room_id", -1), -1)
            slug = str(room.get("slug", "")).strip().lower()

            actual_duration: float | None = None
            if room_id in completed_by_id:
                actual_duration = completed_by_id[room_id]
            elif slug in completed_by_slug:
                actual_duration = completed_by_slug[slug]

            entry = dict(room)

            if actual_duration is not None:
                start_offset = actual_elapsed
                actual_elapsed += actual_duration
                end_offset = actual_elapsed

                entry["actual_duration_minutes"] = round(actual_duration, 2)
                entry["start_offset_minutes"] = round(start_offset, 2)
                entry["end_offset_minutes"] = round(end_offset, 2)
                entry["eta_minutes_from_start"] = round(end_offset, 2)
                entry["eta_at"] = _eta_at(job_start_dt, end_offset)
                entry["reanchored"] = False
                entry["completed"] = True
                entry["current"] = False
                entry["remaining"] = False
                entry["skipped"] = False
                entry["progress_percent"] = 100
                entry["elapsed_minutes"] = round(actual_duration, 2)
                entry["remaining_minutes"] = 0.0
            else:
                estimated_minutes = _safe_float(room.get("minutes"), _DEFAULT_ROOM_MINUTES)
                start_offset = actual_elapsed + remaining_cursor
                remaining_cursor += estimated_minutes
                end_offset = actual_elapsed + remaining_cursor

                entry["start_offset_minutes"] = round(start_offset, 2)
                entry["end_offset_minutes"] = round(end_offset, 2)
                entry["eta_minutes_from_start"] = round(end_offset, 2)
                entry["eta_at"] = _eta_at(job_start_dt, end_offset)
                entry["reanchored"] = True
                entry["completed"] = False
                entry["current"] = False
                entry["remaining"] = True
                entry["skipped"] = False
                entry["progress_percent"] = 0
                entry["elapsed_minutes"] = 0.0
                entry["remaining_minutes"] = round(estimated_minutes, 2)

            updated_timeline.append(entry)

        first_unresolved_marked = False
        for entry in updated_timeline:
            if entry.get("completed", False):
                continue
            if not first_unresolved_marked:
                entry["current"] = True
                entry["remaining"] = False
                first_unresolved_marked = True
            else:
                entry["current"] = False
                entry["remaining"] = True

        overhead_minutes = _safe_float(original_estimate.get("overhead_minutes"), 0.0)
        total_actual_and_estimated = actual_elapsed + remaining_cursor
        total_minutes = total_actual_and_estimated + overhead_minutes
        job_eta_at = _eta_at(job_start_dt, total_minutes)

        completed_count = sum(1 for r in updated_timeline if r.get("completed"))
        remaining_count = len(updated_timeline) - completed_count

        result = {
            **original_estimate,
            "room_timeline": updated_timeline,
            "breakdown": updated_timeline,
            "total_minutes": round(total_minutes, 2),
            "job_eta_minutes": round(total_minutes, 2),
            "job_eta_at": job_eta_at,
            "reanchored_at": datetime_to_utc_iso(anchor_dt),
            "rooms_completed": completed_count,
            "rooms_remaining": remaining_count,
            "actual_elapsed_minutes": round(actual_elapsed, 2),
            "all_completed": remaining_count == 0,
        }

        # Battery-aware update if current_battery supplied.
        if current_battery is not None:
            remaining_battery_estimate = sum(
                _safe_float(r.get("battery"), _DEFAULT_BATTERY_PER_ROOM)
                for r in updated_timeline
                if not r.get("completed", False)
            )
            required = remaining_battery_estimate + reserve_battery_percent
            shortfall = max(required - current_battery, 0.0)
            charge_minutes = (
                shortfall / charge_percent_per_minute
                if charge_percent_per_minute > 0
                else 0.0
            )
            mid_job_recharge_needed_battery = max(remaining_battery_estimate - current_battery, 0.0)
            mid_job_recharge_estimated_charge_minutes = (
                mid_job_recharge_needed_battery / charge_percent_per_minute
                if charge_percent_per_minute > 0
                else 0.0
            )
            result["current_battery"] = current_battery
            result["remaining_battery_estimate"] = round(remaining_battery_estimate, 2)
            result["battery_shortfall"] = round(shortfall, 2)
            # Reanchor keeps the same semantic contract as estimate():
            # battery never blocks the job because the robot may recharge
            # and continue. Preserve can_run_now for true hard blockers only.
            result["can_run_now"] = True
            result["estimated_charge_minutes"] = round(charge_minutes, 2)
            result["battery_warning"] = shortfall > 0
            result["mid_job_recharge_risk"] = mid_job_recharge_needed_battery > 0
            result["mid_job_recharge_needed_battery"] = round(mid_job_recharge_needed_battery, 2)
            result["mid_job_recharge_estimated_charge_minutes"] = round(
                mid_job_recharge_estimated_charge_minutes,
                2,
            )

        return result
