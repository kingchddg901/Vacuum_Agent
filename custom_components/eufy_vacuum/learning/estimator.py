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

  Matched half-open by MIN threshold (RP-036/EST-1): the band with the
  largest min_score <= score wins, so every score in [0.0, 1.0] matches
  exactly one band with no gap at a boundary (e.g. 0.795, strictly between
  medium's labeled 0.79 max and high's 0.80 min, resolves to MEDIUM). The
  labeled max_score values above stay as display-only documentation of each
  band's nominal top.

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
#   IN2QDNB3  `learning/history_store.py#IN2QDNB3`
#       A2-ACC-1 (closed RP-006): A single transient read failure makes record_estimate_accuracy silently overwrite
#              the entire accuracy history with one job's rooms
#   IN40W49E  `profiles/room_profiles.py#IN40W49E`
#       A1-EST-7 (closed RP-025): _load_mop_wash_config hard-codes Eufy's wash-frequency bounds (15/20/25) in the
#              brand-agnostic estimator while the adapter already declares wash_frequency_bounds
#       A1-EST-8 (closed RP-025): is_mop raw-compares clean_mode against a hand-copied literal set while the very same
#              function canonicalizes it for the stats lookup
#   INJW5J2A  `learning/history_store.py#INJW5J2A`
#       A1-EST-9: estimate() runs ensure_dirs (four mkdir syscalls) three times per call on the event
#              loop, even on full cache hits


from __future__ import annotations

import copy
import logging
import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .history_store import LearningHistoryStore
from .brand_facts import brand_facts_for
from ..timestamp_utils import datetime_to_utc_iso, parse_timestamp, utc_now
from .utils import (
    _canonical_clean_intensity,
    _canonical_clean_mode,
    _iso_now,
    _room_key,
    _safe_float,
    _safe_int,
)

_LOGGER = logging.getLogger(__name__)


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

#: Minimum average boundaries-per-job before the global inter-room overhead may be
#: divided down to a per-boundary figure. Guards a degenerate divisor: at
#: avg_room_count 1.001 the divisor is 0.001 and the result is meaningless. 0.25 means
#: "at least a quarter of runs had a second room" — below that the archive is dominated
#: by single-room jobs and there is no boundary population to average over.
_MIN_BOUNDARIES_PER_JOB = 0.25
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


def _nearest_breakpoint(score: float) -> dict[str, Any]:
    """Return the breakpoint whose band is numerically closest to score.

    Defensive fallback only — see _breakpoint_for_score, whose half-open
    min-threshold scan already matches every score in [0.0, 1.0]. Only
    reachable for a score outside that range (neither scoring path should
    ever produce one; both clamp to [0.0, 1.0] before calling this). Picks
    the band minimizing distance to its own [min_score, max_score] interval
    rather than hardcoding LOW, per RP-036/EST-1.
    """
    def _distance(bp: dict[str, Any]) -> float:
        if score < bp["min_score"]:
            return bp["min_score"] - score
        if score > bp["max_score"]:
            return score - bp["max_score"]
        return 0.0

    return dict(min(_BREAKPOINTS, key=_distance))


def _breakpoint_for_score(score: float) -> dict[str, Any]:
    """Return the confidence breakpoint dict for a given score.

    _BREAKPOINTS is ordered HIGH -> MEDIUM -> LOW (descending min_score).
    The band with the largest min_score <= score wins — equivalent to
    half-open [min_score, next_band's min_score) bands, contiguous with no
    gap at any boundary, so every score in [0.0, 1.0] matches exactly one
    band regardless of how max_score is labeled for display (RP-036/EST-1;
    previously a score like 0.795 matched neither the medium [_, 0.79] nor
    the high [0.80, _] closed interval and fell through to a hardcoded LOW).
    """
    for bp in _BREAKPOINTS:
        if score >= bp["min_score"]:
            return dict(bp)
    # Unreachable for any real caller (both clamp to [0.0, 1.0] first) —
    # only a negative score gets here, since low.min_score == 0.0.
    return _nearest_breakpoint(score)


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
    _facts = brand_facts_for(vacuum_entity_id)
    mode_entity_id: str | None = _facts.entity_id("wash_frequency_mode")
    interval_entity_id: str | None = _facts.entity_id("wash_frequency_value_time")

    mode_state = hass.states.get(mode_entity_id) if mode_entity_id else None
    interval_state = hass.states.get(interval_entity_id) if interval_entity_id else None

    _wash_freq_aliases: dict[str, str] = _facts.alias_map("wash_frequency_mode")
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

def _learning_velocity(
    sample_count: int,
    current_score: float,
    ceiling_score: float | None = None,
) -> dict[str, Any]:
    """Return how many more runs are needed to reach MEDIUM and HIGH.

    Uses the analytical sample targets computed from the scoring formula.
    If already at or above a tier, returns 0 for that tier.

    ceiling_score (RP-036/EST-5) — the best score this room could reach with
    an unlimited sample count, HOLDING its current variance/intensity/drift
    penalties fixed (see estimate()'s caller: same _score_room_confidence
    call with sample_count forced to saturation). _SAMPLES_FOR_HIGH assumes
    ZERO variance and zero penalties (its own comment says so) — a room with
    real, nonzero variance can structurally never clear HIGH no matter how
    many more runs it gets, and runs_to_high must not keep promising it will.
    Pass None (the default) when no ceiling is known — e.g. a cold-start
    "default" room, which has no variance data yet to judge reachability by,
    and for which accumulating samples IS the real path to HIGH (unaffected).
    """
    runs_to_medium = max(_SAMPLES_FOR_MEDIUM - sample_count, 0)
    runs_to_high = max(_SAMPLES_FOR_HIGH - sample_count, 0)

    current_bp = _breakpoint_for_score(current_score)

    high_min = _BREAKPOINTS[0]["min_score"]
    high_reachable = ceiling_score is None or ceiling_score >= high_min
    achievable_ceiling_tier = (
        _breakpoint_for_score(ceiling_score)["key"] if ceiling_score is not None else None
    )
    if not high_reachable:
        # Don't promise arrival — report against the achievable ceiling
        # instead of a runs count that can never be satisfied.
        runs_to_high = None

    return {
        "runs_to_medium": runs_to_medium,
        "runs_to_high": runs_to_high,
        "current_tier": current_bp["key"],
        "high_reachable": high_reachable,
        "achievable_ceiling_tier": achievable_ceiling_tier,
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
    learned_transition_minutes: float | None = None,
    transition_source: str = "default",
) -> dict[str, Any]:
    """Compute job overhead breakdown.

    Mop wash cycles are driven by cumulative projected mop minutes against
    the configured dock cadence (select.<vacuum>_wash_frequency_mode /
    number.<vacuum>_wash_frequency_value_time), not by room count.
    """
    startup = _STARTUP_MINUTES
    # transitions: learned per-room transit sum when available (folded into the
    # room timeline upstream), else the flat per-boundary constant (legacy path
    # for cold start / adapters without cleaning_time).
    if learned_transition_minutes is not None:
        transitions = max(learned_transition_minutes, 0.0)
    else:
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
            "transition_source": transition_source,
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


def _lookup_transit_minutes(
    *,
    transit_index: dict[tuple, dict[str, Any]],
    ingress_index: dict[tuple, dict[str, Any]],
    global_inter_room_minutes: float | None,
    map_id: int,
    from_room_id: int,
    to_room_id: int,
    to_slug: str,
) -> tuple[float, str]:
    """Return (transit_minutes, source) for the leg BEFORE entering to_room.

    Fallback chain, most-specific first:
      1. learned_pairs  — the exact from->to edge (access_graph_edges)
      2. learned_room   — average transit INTO to_room (room_baselines ingress)
      3. learned_global — job-level avg per-boundary inter-room overhead
      4. default        — the _TRANSITION_PER_ROOM constant (today's behavior,
                          used at cold start / adapters without cleaning_time)
    Each learned tier requires sample_count >= 1, so a never-observed leg always
    degrades cleanly to the next tier.
    """
    edge = transit_index.get((map_id, from_room_id, to_room_id))
    if isinstance(edge, dict) and _safe_int(edge.get("sample_count"), 0) >= 1:
        return _safe_float(edge.get("transit_minutes_mean"), 0.0), "learned_pairs"
    ing = ingress_index.get((map_id, to_slug))
    if isinstance(ing, dict) and _safe_int(ing.get("sample_count"), 0) >= 1:
        return _safe_float(ing.get("avg_minutes"), 0.0), "learned_room"
    if global_inter_room_minutes is not None and global_inter_room_minutes > 0:
        return round(global_inter_room_minutes, 4), "learned_global"
    return _TRANSITION_PER_ROOM, "default"


# ---------------------------------------------------------------------------
# Room stat lookup
# ---------------------------------------------------------------------------

#: Below this many samples on EITHER side, a measured setting ratio is noise.
_SETTING_RATIO_MIN_SAMPLES = 2

#: A learned ratio outside this band is an artefact (a partial run, a stalled
#: counter), not a setting effect. Clamps both the measured and the prior ratio.
_SETTING_RATIO_MIN = 0.25
_SETTING_RATIO_MAX = 4.0


def _bucket_ratio(buckets: Any, want_key: Any, got_key: Any) -> float | None:
    """``avg_minutes[want] / avg_minutes[got]`` from a room_baselines setting bucket.

    ``None`` when either side is missing, too thinly sampled, or zero — an unmeasured
    ratio must not become a confident 1.0, which is the live:AUDIT2-ZEROCOERCE shape.
    """
    if not isinstance(buckets, dict):
        return None
    want, got = buckets.get(str(want_key)), buckets.get(str(got_key))
    if not isinstance(want, dict) or not isinstance(got, dict):
        return None
    if (
        _safe_int(want.get("sample_count"), 0) < _SETTING_RATIO_MIN_SAMPLES
        or _safe_int(got.get("sample_count"), 0) < _SETTING_RATIO_MIN_SAMPLES
    ):
        return None
    want_minutes = _safe_float(want.get("avg_minutes"), 0.0)
    got_minutes = _safe_float(got.get("avg_minutes"), 0.0)
    if want_minutes <= 0.0 or got_minutes <= 0.0:
        return None
    return min(max(want_minutes / got_minutes, _SETTING_RATIO_MIN), _SETTING_RATIO_MAX)


def _measured_setting_ratio(
    baselines: list[dict[str, Any]] | None,
    field: str,
    want_key: Any,
    got_key: Any,
    map_id: int | None = None,
    slug: str | None = None,
) -> float | None:
    """This room's own measured ratio, else the MEDIAN across every room that has one.

    The room's own history wins because a setting's effect is partly a property of the
    room (a cluttered room loses more to a second pass than an open one). The median
    across rooms is the next best thing — it is a real measurement of this house's
    robot on this profile, which a constant never is. Median, not mean, so one partial
    run cannot drag it.
    """
    ratios: list[float] = []
    for base in baselines or []:
        if not isinstance(base, dict):
            continue
        ratio = _bucket_ratio(base.get(field), want_key, got_key)
        if ratio is None:
            continue
        if (
            map_id is not None
            and _safe_int(base.get("map_id")) == map_id
            and str(base.get("room_slug", "")).strip().lower() == slug
        ):
            return ratio
        ratios.append(ratio)
    if not ratios:
        return None
    ratios.sort()
    return ratios[len(ratios) // 2]


def _relaxed_setting_scale(
    *,
    baselines: list[dict[str, Any]] | None,
    map_id: int | None,
    slug: str,
    want_passes: int,
    got_passes: int,
    want_edge: bool,
    got_edge: bool,
) -> float:
    """Scale a relaxed match's learned minutes onto the settings actually requested.

    CHRIS 2026-08-05: "a number of clean times is a dominant for the time it takes to
    clean a room compared to 1 pass." ``_find_room_match`` already keeps clean_passes
    longest, but when it finally has to relax (pass 5, no history at the requested pass
    count) it returns the other bucket's ``avg_minutes`` VERBATIM and marks a mismatch.
    A 2-pass room matched on 1-pass history therefore estimates at roughly HALF its
    real time, carrying only a confidence penalty to say so.

    That is not a cosmetic error. It is the same number ``_timing_completion_threshold_
    minutes`` rolls the live room on, so it opened about a third of the way through a
    double-pass room and struck it out on the card while the robot was still in it —
    see live:ROOM-FLICKER-1, whose root cause this addresses at source.

    PRECEDENCE: the room's own measured ratio, then the median measured ratio across
    rooms that have both buckets, then a LINEAR-IN-PASSES prior — a pass is another
    full sweep of the same floor, so N passes is about N times the work once approach
    and egress are excluded (which live:PHASE-ATTR-3's switch to cleaning_seconds now
    guarantees). Measurement always beats the prior and replaces it as soon as it
    exists.

    EDGE MOPPING GETS NO PRIOR. A perimeter pass is additive, not proportional, and
    nothing in the model says how long this room's perimeter takes — so an unmeasured
    edge difference leaves the estimate alone rather than guessing at it.
    """
    scale = 1.0
    if want_passes != got_passes and want_passes > 0 and got_passes > 0:
        ratio = _measured_setting_ratio(
            baselines, "by_clean_times", want_passes, got_passes, map_id, slug
        )
        if ratio is None:
            ratio = min(
                max(want_passes / got_passes, _SETTING_RATIO_MIN), _SETTING_RATIO_MAX
            )
        scale *= ratio
    if want_edge != got_edge:
        ratio = _measured_setting_ratio(
            baselines,
            "by_edge_mopping",
            "on" if want_edge else "off",
            "on" if got_edge else "off",
            map_id,
            slug,
        )
        if ratio is not None:
            scale *= ratio
    return scale


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
            and _canonical_clean_mode(item.get("effective_mode")) == _canonical_clean_mode(clean_mode)
        )

    def _passes(item: dict[str, Any]) -> bool:
        return _safe_int(item.get("clean_times")) == clean_passes

    def _carpet(item: dict[str, Any]) -> bool:
        return bool(item.get("is_carpet")) == is_carpet

    def _edge(item: dict[str, Any]) -> bool:
        return bool(item.get("edge_mopping", False)) == edge_mopping

    def _intensity(item: dict[str, Any]) -> bool:
        # RP-036/EST-3: routed through the shared canonical helper so this
        # matcher's normalization can never silently diverge from the
        # query-side projection that computed `clean_intensity` above, or
        # from record_estimate_accuracy's own room-key normalization.
        return _canonical_clean_intensity(item.get("clean_intensity")) == clean_intensity

    def _best_by_sample_count(matches: list[dict[str, Any]]) -> dict[str, Any]:
        """RP-036/EST-6: deterministic tiebreak for a relaxed pass with more
        than one structural match — prefer the one with the highest
        sample_count (more observations = more trustworthy) instead of
        whichever happened to iterate first."""
        return max(matches, key=lambda item: _safe_int(item.get("sample_count"), 0))

    # Pass 1 — exact. Deduped by construction (stats_rebuilder emits at most
    # one room_stats entry per exact key), so no tiebreak is needed here.
    for item in room_stats:
        if _base(item) and _passes(item) and _carpet(item) and _edge(item) and _intensity(item):
            return item, False

    # Pass 2 — ignore intensity (keep passes, carpet, edge)
    matches = [item for item in room_stats if _base(item) and _passes(item) and _carpet(item) and _edge(item)]
    if matches:
        return _best_by_sample_count(matches), True

    # Pass 3 — ignore carpet (keep passes, edge)
    matches = [item for item in room_stats if _base(item) and _passes(item) and _edge(item)]
    if matches:
        return _best_by_sample_count(matches), True

    # Pass 4 — ignore edge_mopping (keep passes)
    matches = [item for item in room_stats if _base(item) and _passes(item)]
    if matches:
        return _best_by_sample_count(matches), True

    # Pass 5 — ignore passes
    matches = [item for item in room_stats if _base(item)]
    if matches:
        return _best_by_sample_count(matches), True

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
        # RP-036/ACC-7: a bare `.get("rooms", {})` only substitutes its default
        # on an ABSENT key — an older/external payload that stored "rooms" as
        # a list (rather than the canonical dict keyed by room_key) would pass
        # that default check and then raise AttributeError on `.get(room_key,
        # {})`. Mirrors manager.py's isinstance-branch tolerance
        # (build_trust_metrics, ~1397-1413): a list carries no room_key to
        # index by, so it normalizes the same as "no accuracy data" rather
        # than crashing.
        rooms_raw = accuracy_stats.get("rooms")
        accuracy_rooms: dict[str, Any] = rooms_raw if isinstance(rooms_raw, dict) else {}
        room_accuracy = accuracy_rooms.get(room_key, {})
        if not isinstance(room_accuracy, dict):
            room_accuracy = {}
        return _safe_float(room_accuracy.get("mean_abs_pct_error"), 0.0)

    def record_estimate_accuracy(
        self,
        *,
        vacuum_entity_id: str,
        room_actuals: list[dict[str, Any]],
        stats_sink: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record estimated vs actual minutes per room after a job completes.

        Called by finalize_completed_job. Each entry in room_actuals must have:
          slug, clean_mode, clean_passes, is_carpet, clean_intensity,
          estimated_minutes, actual_minutes, map_id (and optionally edge_mopping,
          default off — it is part of the room key).

        Updates the running accuracy stats file with the new observations.
        Returns a summary of what was recorded.
        """
        # RP-006 step 7: when a rebuild supplies stats_sink, read from and write
        # into IT — no disk round-trip per replayed record, one save at the end
        # (the rebuild's), and the live store stays intact until that save lands.
        if stats_sink is not None:
            existing = stats_sink
        else:
            # RP-006 (ACC-1): destructive RMW — refuse on a FAILED read. ABSENT
            # starts fresh as before; UNREADABLE would let this fold rewrite the
            # whole accuracy history as just this job's rooms.
            _outcome, _stats = self.store.load_accuracy_stats_outcome(
                vacuum_entity_id=vacuum_entity_id
            )
            if _outcome == self.store.READ_UNREADABLE:
                _LOGGER.warning(
                    "accuracy update skipped: store unreadable for %s (retrying "
                    "after backoff; history preserved on disk)",
                    vacuum_entity_id,
                )
                return {
                    "vacuum_entity_id": vacuum_entity_id,
                    "rooms_recorded": 0,
                    "skipped": "store_unreadable",
                    "detail": [],
                }
            # Deep-copy the loaded stats: load_accuracy_stats may hand back the shared
            # cached object, and we mutate per-room records in place below. Working on a
            # copy keeps the cache immutable until save_accuracy_stats refreshes it by
            # replacement — so a write_json failure (it re-raises, e.g. on an SMB
            # hiccup) can't leave the cache out of sync with disk, and the loop-bound
            # estimate never reads a half-updated record.
            existing = copy.deepcopy(_stats or {})
        # RP-036/ACC-7: tolerate a non-dict "rooms" (see _drift_ratio_for_room
        # above for the read-side twin of this guard). rooms_data is mutated
        # by key below (`rooms_data[room_key] = {...}`), which raises on a
        # list — normalize to a fresh dict rather than crashing; there is no
        # room_key to preserve from a list-shaped legacy/external payload.
        _rooms_raw = existing.get("rooms")
        rooms_data: dict[str, Any] = _rooms_raw if isinstance(_rooms_raw, dict) else {}

        recorded: list[dict[str, Any]] = []

        for entry in room_actuals:
            slug = str(entry.get("slug", "")).strip().lower()
            clean_mode = str(entry.get("clean_mode", "")).strip().lower()
            clean_passes = _safe_int(entry.get("clean_passes", 1), 1)
            is_carpet = bool(entry.get("is_carpet", False))
            clean_intensity = _canonical_clean_intensity(entry.get("clean_intensity"))
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
                    # RP-036/ACC-6: EXACT-only twins of the totals above. A
                    # single-room sample's actual_minutes is the room's real
                    # measured duration; a multi-room sample's is the job
                    # total divided evenly across rooms — an allocation with
                    # no room-specific signal. Tracked separately so the mean
                    # can prefer exact observations once at least one exists.
                    "total_abs_pct_error_exact": 0.0,
                    "total_signed_error_minutes_exact": 0.0,
                    "mean_abs_pct_error": 0.0,
                    "mean_signed_error_minutes": 0.0,
                    "last_updated": _iso_now(),
                }

            rec = rooms_data[room_key]
            rec["sample_count"] += 1
            if is_single_room:
                rec["single_room_sample_count"] = rec.get("single_room_sample_count", 0) + 1
                rec["total_abs_pct_error_exact"] = (
                    rec.get("total_abs_pct_error_exact", 0.0) + pct_error
                )
                rec["total_signed_error_minutes_exact"] = (
                    rec.get("total_signed_error_minutes_exact", 0.0) + (actual - estimated)
                )
            rec["total_abs_pct_error"] += pct_error
            rec["total_signed_error_minutes"] += (actual - estimated)
            n = rec["sample_count"]
            exact_n = rec.get("single_room_sample_count", 0)
            # RP-036/ACC-6: prefer exact (single-room) samples over allocated
            # (multi-room) ones once at least one exact sample exists — an
            # allocated duration must never outweigh a real per-room
            # observation. Falls back to the all-samples mean only while no
            # exact sample has ever been recorded for this room.
            if exact_n > 0:
                rec["mean_abs_pct_error"] = round(rec["total_abs_pct_error_exact"] / exact_n, 4)
                rec["mean_signed_error_minutes"] = round(
                    rec["total_signed_error_minutes_exact"] / exact_n, 2
                )
            else:
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
        if stats_sink is not None:
            # rebuild mode: fold into the caller's sink; the caller does ONE save
            stats_sink.clear()
            stats_sink.update(updated_payload)
        else:
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

    def _build_transit_indices(
        self,
        *,
        vacuum_entity_id: str,
        room_stats_data: dict[str, Any] | None,
    ) -> tuple[dict[tuple, dict[str, Any]], dict[tuple, dict[str, Any]], float | None]:
        """Build the transit lookup indices for an estimate (no extra room_stats read).

        Returns (transit_index, ingress_index, global_inter_room_minutes):
          - transit_index[(map_id, from_id, to_id)] = access_graph edge
          - ingress_index[(map_id, slug)] = {sample_count, avg_minutes} (transit INTO)
          - global_inter_room_minutes = job-level avg per-boundary inter-room
            overhead, or None when no per-room transit has been captured yet.
        """
        transit_index: dict[tuple, dict[str, Any]] = {}
        ingress_index: dict[tuple, dict[str, Any]] = {}
        for edge in (room_stats_data or {}).get("access_graph_edges", []) or []:
            if not isinstance(edge, dict):
                continue
            transit_index[
                (
                    _safe_int(edge.get("map_id"), 0),
                    _safe_int(edge.get("from_room_id"), -1),
                    _safe_int(edge.get("to_room_id"), -1),
                )
            ] = edge
        for base in (room_stats_data or {}).get("room_baselines", []) or []:
            if not isinstance(base, dict):
                continue
            ing_count = _safe_int(base.get("ingress_sample_count"), 0)
            if ing_count <= 0:
                continue
            ingress_index[
                (
                    _safe_int(base.get("map_id"), 0),
                    str(base.get("room_slug") or "").strip().lower(),
                )
            ] = {
                "sample_count": ing_count,
                "avg_minutes": _safe_float(base.get("avg_ingress_transit_seconds"), 0.0) / 60.0,
            }
        global_inter_room: float | None = None
        try:
            job_stats_data = self.store.load_job_stats(vacuum_entity_id=vacuum_entity_id)
            js = (
                (job_stats_data or {}).get("job_stats", {})
                if isinstance(job_stats_data, dict)
                else {}
            )
            gi = _safe_float(js.get("avg_overhead_inter_room_minutes"), 0.0)
            gi_count = _safe_int(js.get("overhead_inter_room_sample_count"), 0)
            avg_rooms = _safe_float(js.get("avg_room_count"), 0.0)
            # `avg_rooms > 1` alone is not a guard, it is a float comparison: at 1.001 the
            # divisor is 0.001 and a modest per-job overhead becomes a per-boundary
            # estimate hundreds of times too large, applied to EVERY atomic run.
            #
            # That is no longer hypothetical. Phased-run children are single- and two-room
            # records, and since 8a3bada they enter job stats, so avg_room_count is being
            # pulled toward 1.0 (live: 1.77 before children were admitted). Require a real
            # margin and refuse otherwise — an absent global fallback is handled downstream,
            # a wildly inflated one is not.
            if gi > 0 and gi_count >= 1 and (avg_rooms - 1.0) >= _MIN_BOUNDARIES_PER_JOB:
                # avg_overhead_inter_room_minutes is a per-JOB total across all
                # gaps; divide by avg boundaries/job for a per-boundary estimate.
                global_inter_room = gi / (avg_rooms - 1.0)
        except Exception:
            global_inter_room = None
        return transit_index, ingress_index, global_inter_room

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

        # Stale detection — reuse the already-loaded room_stats_data (the estimate
        # is computed on the event loop via the dashboard snapshot, so avoid a second read).
        stats_stale = self._is_stats_stale(
            vacuum_entity_id=vacuum_entity_id, room_stats_data=room_stats_data
        )
        rebuilt_at = (room_stats_data or {}).get("rebuilt_at")

        # Transit / travel-time indices (frame-invariant). Built from the already
        # loaded room_stats_data (access_graph_edges + room_baselines ingress) plus
        # a job-level global. Empty -> _lookup_transit_minutes falls back to the
        # _TRANSITION_PER_ROOM constant (today's behavior).
        transit_index, ingress_index, global_inter_room = self._build_transit_indices(
            vacuum_entity_id=vacuum_entity_id,
            room_stats_data=room_stats_data,
        )

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
        room_minutes_sum = 0.0
        total_transit_minutes = 0.0
        total_battery = 0.0
        projected_mop_minutes = 0.0
        room_confidence_scores: list[float] = []
        transit_sources: list[str] = []
        prev_room_id: int | None = None

        for position, room in enumerate(ordered_rooms):
            slug = str(room.get("slug", "")).strip().lower()
            clean_mode = str(room.get("clean_mode", "")).strip().lower()
            clean_passes = _safe_int(room.get("clean_passes", 1), 1)
            is_carpet = bool(room.get("carpet", False))
            # RP-036/EST-3: routed through the shared canonical helper (see
            # utils._canonical_clean_intensity) alongside _find_room_match's
            # matcher and record_estimate_accuracy, so this query-side
            # projection can never silently diverge from either.
            clean_intensity = _canonical_clean_intensity(room.get("clean_intensity"))
            edge_mopping = bool(room.get("edge_mopping", False))
            room_name = str(room.get("name", slug))
            room_id = _safe_int(room.get("room_id", 0))

            # ISSUE #48. Was `clean_mode in {"vacuum_mop", "mop"}` against a value
            # lowercased at the top of this loop but never canonicalized, so an
            # all-mop job whose rooms are stored as "Vacuum and mop" accumulated no
            # projected_mop_minutes and reported a mop-wash overhead of 0.0 — the ETA
            # short by the entire wash allowance.
            #
            # The contradiction was six lines wide: the same variable goes straight
            # into _find_room_match below, whose predicate canonicalizes both sides,
            # so the room matched its learned stats and got correct minutes while
            # this said it was not a mop room at all.
            is_mop = _canonical_clean_mode(clean_mode) in {"vacuum_mop", "mop"}

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

            # A matched entry can have NO timing samples: wave 3 drops allocated timings,
            # and a room that has only ever run inside a group keeps its area/battery/water
            # samples while its minutes list empties. avg_minutes is then 0.0 — and
            # `_safe_float(0.0, default)` returns 0.0, not the default, so the room would
            # estimate as taking NO TIME. That is worse than the arithmetic figure it
            # replaced: 0 is a confident wrong answer where "unknown" is the truth.
            if match:
                _timing_n = _safe_int(
                    match.get("timing_sample_count", match.get("sample_count")), 0
                )
                # Duration only — area/battery/water stay learned below, because those
                # samples are real even when every timing was an allocation.
                minutes = (
                    _safe_float(match.get("avg_minutes"), _DEFAULT_ROOM_MINUTES)
                    if _timing_n > 0 else _DEFAULT_ROOM_MINUTES
                )
                battery = _safe_float(match.get("avg_battery_used"), _DEFAULT_BATTERY_PER_ROOM)
                # avg_minutes is from the area-gated (partial-excluded) samples, so
                # timing confidence reflects timing_sample_count when it is present.
                sample_count = _safe_int(
                    match.get("timing_sample_count", match.get("sample_count")), 0
                )
                minutes_stddev = _safe_float(match.get("minutes_stddev"), 0.0)
                # Chris 2026-08-05: clean_times DOMINATES room time, so a match found
                # at a different pass count cannot be used at face value. Scale it onto
                # the requested settings — measured ratio first, linear-in-passes prior
                # otherwise. Only for a genuinely LEARNED duration: scaling the default
                # would dress a guess up as a measurement.
                if _timing_n > 0:
                    setting_scale = _relaxed_setting_scale(
                        baselines=(room_stats_data or {}).get("room_baselines", []),
                        map_id=map_id_int,
                        slug=slug,
                        want_passes=clean_passes,
                        got_passes=_safe_int(match.get("clean_times"), clean_passes),
                        want_edge=edge_mopping,
                        got_edge=bool(match.get("edge_mopping", False)),
                    )
                    if setting_scale != 1.0:
                        minutes = round(minutes * setting_scale, 2)
                        # Scale the band with the mean so the coefficient of variation
                        # is preserved. Leaving stddev behind would SHRINK the CV and
                        # hand a relaxed match MORE confidence than the exact one it
                        # stood in for — the mismatch penalty already carries that.
                        minutes_stddev = round(minutes_stddev * setting_scale, 4)
                area_m2 = _safe_float(match.get("avg_area_m2"), 0.0)
                # `source` describes where the DURATION came from — it is what the
                # confidence score keys off. A room whose every timing was an allocation
                # has a defaulted duration, so calling it "learned" would earn confidence
                # the number has not got. Its area stays learned above regardless.
                source = "learned" if _timing_n > 0 else "default"
                # Same room key (shared _room_key) for accuracy lookup.
                room_key = _room_key(
                    map_id_int, slug, clean_mode, clean_passes, is_carpet, clean_intensity, edge_mopping
                )
                drift_ratio = self._drift_ratio_for_room(
                    accuracy_stats=accuracy_stats,
                    room_key=room_key,
                )
                # RP-036/EST-4: match.get("minutes_min")/("minutes_max") are
                # written by stats_rebuilder (the room's own historical band)
                # but were never read back here. Only checked with real timing
                # samples (_timing_n > 0) — an all-allocated match's band is a
                # degenerate 0.0/0.0 placeholder (see the comment above this
                # `if match:`), not a real observed range, so it must not
                # clamp the DEFAULT fallback minutes computed below it.
                band_capped = False
                if _timing_n > 0:
                    _band_min_raw = match.get("minutes_min")
                    _band_max_raw = match.get("minutes_max")
                    if _band_min_raw is not None and _band_max_raw is not None:
                        _band_min = _safe_float(_band_min_raw, minutes)
                        _band_max = _safe_float(_band_max_raw, minutes)
                        if minutes < _band_min:
                            minutes = _band_min
                            band_capped = True
                        elif minutes > _band_max:
                            minutes = _band_max
                            band_capped = True
            else:
                minutes = _DEFAULT_ROOM_MINUTES
                battery = _DEFAULT_BATTERY_PER_ROOM
                sample_count = 0
                minutes_stddev = 0.0
                area_m2 = 0.0
                intensity_mismatch = False
                drift_ratio = 0.0
                source = "default"
                band_capped = False

            confidence_score = _score_room_confidence(
                source=source,
                sample_count=sample_count,
                avg_minutes=minutes,
                minutes_stddev=minutes_stddev,
                intensity_mismatch=intensity_mismatch,
                accuracy_drift_ratio=drift_ratio,
            )
            if band_capped:
                # The displayed estimate was clamped to the room's own
                # historical band edge — never show HIGH confidence for a
                # number the room's history didn't actually produce as its
                # mean. Reuses the existing MEDIUM breakpoint's own max_score
                # as the cap (no new constant).
                confidence_score = min(confidence_score, _BREAKPOINTS[1]["max_score"])
            room_confidence_scores.append(confidence_score)
            confidence = _confidence_result(confidence_score)

            # RP-036/EST-5: _SAMPLES_FOR_HIGH assumes zero variance/penalties
            # (see its own comment). A "learned" room's ceiling — the best
            # score it could reach with the sample bonus maxed out, holding
            # its CURRENT variance/intensity/drift penalties fixed — tells
            # _learning_velocity whether HIGH is even structurally reachable.
            # Left None for a "default" (no match) room: it has no variance
            # data yet to judge reachability by, and accumulating samples IS
            # the real path to HIGH for it (unaffected by this).
            velocity_ceiling: float | None = None
            if source == "learned":
                velocity_ceiling = _score_room_confidence(
                    source=source,
                    sample_count=_SAMPLE_BONUS_SATURATE,
                    avg_minutes=minutes,
                    minutes_stddev=minutes_stddev,
                    intensity_mismatch=intensity_mismatch,
                    accuracy_drift_ratio=drift_ratio,
                )
            velocity = _learning_velocity(sample_count, confidence_score, velocity_ceiling)

            # Transit BEFORE this room (inter-room leg); folded into the offsets
            # so the timeline positions travel time between rooms. position 0's
            # entry leg stays in startup overhead.
            if prev_room_id is not None:
                transit_before, transit_source = _lookup_transit_minutes(
                    transit_index=transit_index,
                    ingress_index=ingress_index,
                    global_inter_room_minutes=global_inter_room,
                    map_id=map_id_int,
                    from_room_id=prev_room_id,
                    to_room_id=room_id,
                    to_slug=slug,
                )
            else:
                transit_before, transit_source = 0.0, "none"
            transit_sources.append(transit_source)

            cumulative_minutes += transit_before
            total_transit_minutes += transit_before
            start_offset = cumulative_minutes
            cumulative_minutes += minutes
            end_offset = cumulative_minutes
            room_minutes_sum += minutes
            total_battery += battery
            if is_mop:
                projected_mop_minutes += minutes
            prev_room_id = room_id

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
                    "band_capped": band_capped,
                    "sample_count": sample_count,
                    "accuracy_drift_ratio": round(drift_ratio, 4),
                    "minutes": round(minutes, 2),
                    "battery": round(battery, 2),
                    "estimated_area_m2": round(area_m2, 2),
                    "estimated_transit_minutes_before": round(transit_before, 2),
                    "transit_source": transit_source,
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

        # Pure room cleaning minutes (transit is tracked separately and folded
        # into the per-room offsets above + overhead.transition_minutes below).
        room_minutes_total = room_minutes_sum

        # ----------------------------------------------------------------
        # Overhead
        # ----------------------------------------------------------------
        mop_wash_config = _load_mop_wash_config(
            hass=self.hass,
            vacuum_entity_id=vacuum_entity_id,
        )
        # Job-level transition source from the per-room transit lookups (ignore
        # the position-0 "none" and the constant "default").
        _learned_sources = {s for s in transit_sources if s not in ("none", "default")}
        if not _learned_sources:
            transition_source = "default"
        elif len(_learned_sources) == 1:
            transition_source = next(iter(_learned_sources))
        else:
            transition_source = "learned_mixed"

        overhead_result = _compute_overhead(
            room_count=len(ordered_rooms),
            room_minutes_total=room_minutes_total,
            total_battery_estimate=total_battery,
            projected_mop_minutes=projected_mop_minutes,
            mop_wash_config=mop_wash_config,
            learned_transition_minutes=total_transit_minutes,
            transition_source=transition_source,
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
            # RP-036/ACC-4 (consistency): a skipped room is resolved, not
            # "next" — same guard as reanchor_timeline's own current-room
            # marking, so this card shortcut doesn't announce "cleaning" a
            # room the robot has provably moved past.
            if not room.get("completed", False) and not room.get("skipped", False):
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
        skipped_room_ids: list[int] | None = None,
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
        skipped_room_ids:
            RP-036/ACC-4 — room ids the live run has provably advanced past
            without cleaning (jobs/active_job.py detect_run_anomalies). A
            skipped room is RESOLVED here, not perpetually "remaining" —
            without this, all_completed can never become True on a run with
            a skipped room.
        """
        anchor_dt = _parse_iso(reanchor_at) or utc_now()

        # Build completed actuals lookup.
        completed_by_id: dict[int, float] = {}
        completed_by_slug: dict[str, float] = {}
        for entry in completed_rooms:
            actual = _safe_float(entry.get("actual_duration_minutes"), 0.0)
            room_id = _safe_int(entry.get("room_id", -1), -1)
            # RP-036/ACC-5: `.get(key, default)` only substitutes on an
            # ABSENT key — an explicit {"slug": None} passes str(None) =
            # "none" through unnoticed, colliding two different null-slug
            # rooms on that literal string. Skip slug-matching entirely for
            # a falsy slug rather than let it fall through as "none".
            _slug_raw = entry.get("slug")
            slug = str(_slug_raw).strip().lower() if _slug_raw else ""
            if room_id >= 0:
                completed_by_id[room_id] = actual
            if slug:
                completed_by_slug[slug] = actual

        # RP-036/ACC-4: normalize the skip list once, ignoring negative/unset ids.
        skipped_ids: set[int] = {
            rid for rid in (_safe_int(r, -1) for r in (skipped_room_ids or [])) if rid >= 0
        }

        original_timeline: list[dict[str, Any]] = original_estimate.get("room_timeline", [])

        started_at_str = original_estimate.get("started_at")
        job_start_dt = _parse_iso(started_at_str) or anchor_dt

        # RP-036/ACC-3: every room's transit-before leg was folded into
        # overhead_minutes as ONE upfront lump at estimate() time
        # (learned_transition_minutes = sum of every room's
        # estimated_transit_minutes_before). That lump is now stale in two
        # directions at once: a completed room's leg already happened, so
        # charging it again out of a "time still ahead" total double-counts
        # it; a remaining room's leg hasn't happened yet and needs to be
        # counted against THAT room's own ETA below, not left anonymous in
        # the job-level lump (which would ALSO double-count it once it's
        # re-added per room). Strip the whole transit component out here —
        # the only way to avoid double-counting one direction while dropping
        # the other — and re-home each remaining room's leg explicitly below.
        total_transit_minutes = sum(
            _safe_float(r.get("estimated_transit_minutes_before"), 0.0) for r in original_timeline
        )
        overhead_minutes = max(
            _safe_float(original_estimate.get("overhead_minutes"), 0.0) - total_transit_minutes,
            0.0,
        )

        updated_timeline: list[dict[str, Any]] = []
        actual_elapsed = 0.0
        remaining_cursor = 0.0

        for room in original_timeline:
            room_id = _safe_int(room.get("room_id", -1), -1)
            _slug_raw = room.get("slug")
            slug = str(_slug_raw).strip().lower() if _slug_raw else ""

            actual_duration: float | None = None
            if room_id in completed_by_id:
                actual_duration = completed_by_id[room_id]
            elif slug in completed_by_slug:
                actual_duration = completed_by_slug[slug]

            entry = dict(room)
            is_skipped = actual_duration is None and room_id in skipped_ids

            if actual_duration is not None:
                start_offset = actual_elapsed
                actual_elapsed += actual_duration
                end_offset = actual_elapsed

                entry["actual_duration_minutes"] = round(actual_duration, 2)
                entry["start_offset_minutes"] = round(start_offset, 2)
                entry["end_offset_minutes"] = round(end_offset, 2)
                entry["eta_minutes_from_start"] = round(end_offset, 2)
                # A completed room's eta_at is a historical fact — when it
                # actually finished — derived purely from summed actual
                # durations, so it stays anchored to job start regardless of
                # any later pause (ACC-2 only changes the FORECAST anchor
                # for rooms that haven't happened yet, below).
                entry["eta_at"] = _eta_at(job_start_dt, end_offset)
                entry["reanchored"] = False
                entry["completed"] = True
                entry["current"] = False
                entry["remaining"] = False
                entry["skipped"] = False
                entry["progress_percent"] = 100
                entry["elapsed_minutes"] = round(actual_duration, 2)
                entry["remaining_minutes"] = 0.0
            elif is_skipped:
                # RP-036/ACC-4: resolved, not remaining — it contributes no
                # further transit or cleaning time since it will not be
                # visited. Cursor position is left unchanged (frozen at
                # "wherever we are"), so it doesn't push later rooms' ETAs.
                entry["start_offset_minutes"] = round(actual_elapsed + remaining_cursor, 2)
                entry["end_offset_minutes"] = round(actual_elapsed + remaining_cursor, 2)
                entry["eta_minutes_from_start"] = round(actual_elapsed + remaining_cursor, 2)
                entry["eta_at"] = _eta_at(anchor_dt, remaining_cursor)
                entry["reanchored"] = True
                entry["completed"] = False
                entry["current"] = False
                entry["remaining"] = False
                entry["skipped"] = True
                entry["progress_percent"] = 0
                entry["elapsed_minutes"] = 0.0
                entry["remaining_minutes"] = 0.0
            else:
                # RP-036/ACC-3: re-add this room's OWN transit-before leg —
                # previously dropped entirely, only room.get("minutes") was
                # counted here.
                transit_before = _safe_float(room.get("estimated_transit_minutes_before"), 0.0)
                estimated_minutes = _safe_float(room.get("minutes"), _DEFAULT_ROOM_MINUTES)
                start_offset = actual_elapsed + remaining_cursor
                remaining_cursor += transit_before + estimated_minutes
                end_offset = actual_elapsed + remaining_cursor

                entry["start_offset_minutes"] = round(start_offset, 2)
                entry["end_offset_minutes"] = round(end_offset, 2)
                entry["eta_minutes_from_start"] = round(end_offset, 2)
                # RP-036/ACC-2: a remaining room's forecast is time-from-NOW
                # (reanchor_at / anchor_dt), not job_start_dt + cumulative —
                # job_start_dt ignores any dead wall-clock gap (a pause)
                # between the last real completion and this reanchor call,
                # silently sliding "Done at" into the past.
                entry["eta_at"] = _eta_at(anchor_dt, remaining_cursor)
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
            if entry.get("completed", False) or entry.get("skipped", False):
                continue
            if not first_unresolved_marked:
                entry["current"] = True
                entry["remaining"] = False
                first_unresolved_marked = True
            else:
                entry["current"] = False
                entry["remaining"] = True

        # RP-036/ACC-2: the job-level forecast is also anchored to NOW —
        # "now" plus whatever cleaning/transit/overhead is still ahead —
        # rather than job_start_dt + the naive full-job total, which is what
        # silently slid "Done at" into the past across a pause.
        total_actual_and_estimated = actual_elapsed + remaining_cursor
        total_minutes = total_actual_and_estimated + overhead_minutes
        job_eta_at = _eta_at(anchor_dt, remaining_cursor + overhead_minutes)

        completed_count = sum(1 for r in updated_timeline if r.get("completed"))
        skipped_count = sum(1 for r in updated_timeline if r.get("skipped"))
        remaining_count = len(updated_timeline) - completed_count - skipped_count

        result = {
            **original_estimate,
            "room_timeline": updated_timeline,
            "breakdown": updated_timeline,
            "total_minutes": round(total_minutes, 2),
            "job_eta_minutes": round(total_minutes, 2),
            "job_eta_at": job_eta_at,
            "reanchored_at": datetime_to_utc_iso(anchor_dt),
            "rooms_completed": completed_count,
            "rooms_skipped": skipped_count,
            "rooms_remaining": remaining_count,
            "actual_elapsed_minutes": round(actual_elapsed, 2),
            "all_completed": remaining_count == 0,
        }

        # Battery-aware update if current_battery supplied.
        if current_battery is not None:
            remaining_battery_estimate = sum(
                _safe_float(r.get("battery"), _DEFAULT_BATTERY_PER_ROOM)
                for r in updated_timeline
                # RP-036/ACC-4 (consistency): a skipped room consumes no
                # battery either — same "resolved, not remaining" treatment
                # as the completion check above.
                if not r.get("completed", False) and not r.get("skipped", False)
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
