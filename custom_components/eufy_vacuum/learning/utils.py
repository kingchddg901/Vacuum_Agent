"""Shared utilities for the Eufy Vacuum learning module."""

from __future__ import annotations

from typing import Any

from ..timestamp_utils import utc_now_iso


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


# Canonical cleaning-area unit is m². HA presents area sensors in the box's unit system, so an
# imperial HA (e.g. country=US) exposes Eufy's cleaning_area in ft² while Roborock's stays m²
# (confirmed live: sensor.alfred_cleaning_area unit ft², sensor.ivy_cleaning_area unit m²). The
# raw STATE value follows the unit, so a bare read silently MIXES units — inflating stored area
# ~10.76x, breaking cross-brand comparison, and mis-firing swept_area_min_m2 on ft² values.
_AREA_TO_M2 = {
    "m²": 1.0, "m2": 1.0,
    "ft²": 0.09290304, "ft2": 0.09290304, "sq ft": 0.09290304,
    "in²": 0.00064516, "in2": 0.00064516,
    "yd²": 0.83612736, "yd2": 0.83612736,
    "cm²": 0.0001, "cm2": 0.0001,
}


def cleaning_area_to_m2(value: Any, unit: Any = None) -> float | None:
    """Normalize a cleaning_area reading to canonical m², honoring the sensor's
    ``unit_of_measurement``. A blank/unavailable value → None. An unknown or absent unit is
    assumed to ALREADY be m² (no scaling — we never guess a factor); ft² (imperial HA) → m²."""
    if value in (None, "", "unknown", "unavailable"):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    factor = _AREA_TO_M2.get(str(unit or "").strip().lower())
    return v * factor if factor is not None else v


# Attributed per-room area can legitimately fall SHORT of the device's cleaning_area sensor total
# (the gap = transit/approach that accrued but belongs to no cleaned room — validated live: Ivy
# 7.0 attributed vs 8.5 sensor). But it must never MEANINGFULLY EXCEED it — attributed > sensor is
# double-counting (e.g. a non-monotonic counter). 10% covers rounding/cadence jitter.
AREA_OVER_ATTRIBUTION_TOLERANCE = 0.10


def area_sanity(attributed_m2: Any, sensor_m2: Any, tolerance: float = AREA_OVER_ATTRIBUTION_TOLERANCE) -> dict | None:
    """Sanity-check the attributed per-room area SUM against the device's own cleaning_area sensor
    total (both m²). Returns ``{attributed_m2, sensor_m2, coverage_ratio, over_attributed}`` or
    ``None`` when there is no usable sensor total to check against. ``over_attributed`` is the
    alarm: attributed exceeds the sensor total by more than ``tolerance`` (the sensor total is an
    upper bound, so this can only mean double-counting)."""
    a = _safe_float(attributed_m2, None) if attributed_m2 is not None else None
    s = _safe_float(sensor_m2, None) if sensor_m2 is not None else None
    if a is None or s is None or s <= 0:
        return None
    return {
        "attributed_m2": round(a, 2),
        "sensor_m2": round(s, 2),
        "coverage_ratio": round(a / s, 3),
        "over_attributed": a > s * (1.0 + tolerance),
    }


def _safe_bool(value: Any, default: bool = False) -> bool:
    """Return bool value safely, handling string representations."""
    if isinstance(value, bool):
        return value
    if value in (None, "", "unknown", "unavailable"):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"true", "on", "yes", "1"}
    try:
        return bool(value)
    except Exception:
        return default


def _iso_now() -> str:
    """Return current UTC timestamp in stable ISO format."""
    return utc_now_iso()


_CLEAN_MODE_CANONICAL: dict[str, str] = {
    "vacuum and mop": "vacuum_mop",
    "vacuum & mop": "vacuum_mop",
    "vacuum+mop": "vacuum_mop",
    "vac & mop": "vacuum_mop",
    "vacmop": "vacuum_mop",
}


def _canonical_clean_mode(value: Any) -> str:
    """Normalize a clean_mode/effective_mode string to the canonical token
    ('vacuum', 'mop', 'vacuum_mop').

    Internal job records historically stored the display string ("Vacuum and
    mop") while the framework + adapter value_maps use the token "vacuum_mop";
    folding them together here keeps internal and app-started (external) runs in
    ONE learning bucket instead of splitting on the vocabulary artifact. Unknown
    values pass through lowercased so brand-specific modes are preserved.
    """
    s = str(value or "").strip().lower()
    if not s:
        return s
    if s in _CLEAN_MODE_CANONICAL:
        return _CLEAN_MODE_CANONICAL[s]
    # Any phrasing carrying both verbs is a combined vacuum+mop run.
    if "vacuum" in s and "mop" in s:
        return "vacuum_mop"
    return s


def _room_profile_key(room: dict[str, Any]) -> str:
    """Return a stable per-room settings signature used for stats matching."""
    return "::".join(
        [
            str(room.get("slug", "")).strip().lower(),
            str(room.get("selected_profile_name", room.get("resolved_profile_name", ""))).strip().lower(),
            _canonical_clean_mode(room.get("clean_mode", "")),
            str(room.get("clean_intensity", "")).strip().lower(),
            str(room.get("fan_speed", "")).strip().lower(),
            str(room.get("water_level", "")).strip().lower(),
            str(_safe_int(room.get("clean_passes", room.get("clean_times", 1)), 1)),
            "1" if _safe_bool(room.get("is_carpet", room.get("carpet", False)), False) else "0",
            "1" if _safe_bool(room.get("edge_mopping", False), False) else "0",
        ]
    )


def _room_key(
    map_id: Any,
    slug: Any,
    effective_mode: Any,
    clean_times: Any,
    is_carpet: Any,
    clean_intensity: Any = "",
    edge_mopping: Any = False,
) -> str:
    """Return the exact room learning key (room identity + settings).

    edge_mopping is part of the key because it materially changes cleaning time,
    so edge-on and edge-off runs are learned/tracked separately. Shared by the
    stats rebuilder (room_stats grouping) and the accuracy store so their keys
    always align.
    """
    return (
        f"{_safe_int(map_id, 0)}::"
        f"{str(slug or '').strip().lower()}::"
        f"{_canonical_clean_mode(effective_mode)}::"
        f"{_safe_int(clean_times, 1)}::"
        f"{'1' if _safe_bool(is_carpet, False) else '0'}::"
        f"{str(clean_intensity or 'standard').strip().lower()}::"
        f"{'1' if _safe_bool(edge_mopping, False) else '0'}"
    )


def compute_overhead_observed(job: dict[str, Any]) -> dict[str, Any]:
    """Derive observed run overhead from a completed-job ``job`` block.

    Overhead is wall-clock time not spent actively cleaning: entry (dock->first
    room), inter-room travel, return-to-dock, mid-job recharge, and mop-wash
    dwell. This base is computed purely from fields present on every finalized
    job, so a plain stats rebuild can populate it for historical jobs that
    predate per-room transit capture (the retroactive job-level overhead piece).

        total_overhead_minutes = duration_minutes - cleaning_minutes  (>= 0)
        return_minutes         = return_to_dock_minutes (when known, else None)
        recharge_minutes       = recharge_seconds_accumulated / 60
        entry_minutes / inter_room_minutes = None here; the finalizer fills them
                                 from per-room transit capture when it is valid
        wash_minutes           = None (not separable from job-level fields)

    cleaning_minutes prefers the device cleaning counter (cleaning_time_seconds);
    it falls back to actual_cleaning_minutes (single-room jobs) when absent.
    """
    duration = _safe_float(job.get("duration_minutes"), 0.0)
    cleaning_seconds = _safe_int(job.get("cleaning_time_seconds"), 0)
    if cleaning_seconds > 0:
        cleaning_minutes = cleaning_seconds / 60.0
    else:
        cleaning_minutes = _safe_float(job.get("actual_cleaning_minutes"), 0.0)
    return_raw = job.get("return_to_dock_minutes")
    return {
        "total_overhead_minutes": round(max(duration - cleaning_minutes, 0.0), 2),
        "entry_minutes": None,
        "inter_room_minutes": None,
        "return_minutes": (
            round(_safe_float(return_raw, 0.0), 2) if return_raw is not None else None
        ),
        "recharge_minutes": round(
            _safe_int(job.get("recharge_seconds_accumulated"), 0) / 60.0, 2
        ),
        "wash_minutes": None,
    }


# Cold-start learning guard: a completed run whose wall time exceeds its active
# cleaning by this many minutes — with NO other explanation (no commanded
# charge-wait/wait phase, no logged error) — is HELD from defining a room
# baseline. One extreme first sample must not poison a cold-start baseline; the
# run stays visible and Restore-able in the review tab. 20 min is data-derived
# from Alfred's archive: the legit learning-eligible runs cluster at a <= 11.7 min
# idle gap with a lone 23 min anomaly, then a wide empty band up to a 96 min
# hand-excluded exemplar — so 20 clears every legit run (incl. a 15.4 min
# interrupted tiny-room the design flagged must-pass) while catching the 96 min
# class and the single 23 min outlier (scratch idle_wall_analysis, 2026-07-11).
IDLE_WALL_HOLD_FLOOR_MINUTES = 20.0

# Learning-blocker code stamped on a held run — surfaced in the review tab and
# read by the learning-inclusion gate (used_for_learning is cleared alongside it).
IDLE_WALL_HOLD_BLOCKER = "extreme_idle_wall"


def evaluate_idle_wall_hold(
    *,
    duration_minutes: float,
    active_cleaning_minutes: float | None,
    had_errors: bool,
    had_break_phase: bool,
    floor_minutes: float = IDLE_WALL_HOLD_FLOOR_MINUTES,
) -> dict[str, Any]:
    """Decide whether an otherwise-eligible completed run is held from learning
    for an extreme, UNEXPLAINED idle stretch off the dock.

    idle_gap = duration_minutes - active_cleaning_minutes, where duration_minutes
    is already paused/recharge-adjusted (build_completed_job_payload) and
    active_cleaning_minutes is the error-adjusted DEVICE cleaning counter — NOT the
    state-transition wall slice (actual_cleaning_minutes), which for a stuck/idling
    run tracks nearly the whole wall and would hide the idle as a ~0 gap.

    A run is EXEMPT — it has "another answer" — when it ran a commanded
    charge-wait/wait phase or logged an error; both legitimately inflate wall time
    and carry their own flags, so the idle guard steps aside. Absent a trustworthy
    active-cleaning figure the run is NOT held (missing data is not evidence of
    idling). ALWAYS-ON by design: the danger case is a NEW room's first sample, so
    the guard cannot wait for a baseline to exist before it protects one.

    Returns {"hold": bool, "idle_gap_minutes": float|None, "reason": str|None}.
    """
    if active_cleaning_minutes is None or active_cleaning_minutes <= 0:
        return {"hold": False, "idle_gap_minutes": None, "reason": None}
    idle_gap = round(duration_minutes - active_cleaning_minutes, 2)
    if had_break_phase or had_errors:
        return {"hold": False, "idle_gap_minutes": idle_gap, "reason": None}
    if idle_gap >= floor_minutes:
        return {"hold": True, "idle_gap_minutes": idle_gap, "reason": IDLE_WALL_HOLD_BLOCKER}
    return {"hold": False, "idle_gap_minutes": idle_gap, "reason": None}
