"""Per-job battery metrics — pure compute, no HA / I/O.

Inputs come from the completed-job dict produced by
``learning/history_store.build_completed_job_payload`` (plus the
``cleaning_area_m2`` that the finalizer attaches afterwards).

Outputs a ``battery_metrics`` block ready to be written back onto the job:

```python
{
    "battery_used_pct": 12,
    "duration_min": 30.2,
    "area_m2": 65.5,
    "drain_per_min": 0.397,
    "drain_per_hour": 23.84,
    "drain_per_m2": 0.183,                       # job-wide
    "is_single_clean_mode": True,                # eligible for per-mode aggregate
    "is_single_fan_speed": True,
    "is_single_water_level": True,
    "single_clean_mode": "vacuum_mop",           # set when is_single_clean_mode
    "by_clean_mode":   {"vacuum_mop": {"area_m2": 65.5, "share": 1.0, "rooms": 4}, ...},
    "by_fan_speed":    {...},
    "by_water_level":  {...},
    "passes_share":    {"1": 0.65, "2": 0.35},
    "edge_mopping":    {"on_share": 0.32, "off_share": 0.68},
    "weighted_by":     "estimated_minutes" | "room_count" | "none",
}
```

WEIGHTING
---------
Per-room m² is not reported by the device. We prorate the total m² across
rooms by ``estimated_minutes`` (from the learning enrichment). When estimates
aren't available we fall back to equal-weight per room. Either way the
per-bucket area shares sum to the job total.

PER-BUCKET DRAIN — NOT ATTRIBUTED HERE
--------------------------------------
We don't have per-room battery telemetry, so a single mixed-mode job cannot
honestly attribute drain to individual buckets. To avoid biasing aggregates,
the per-bucket dicts contain only AREA + share, never drain.

The cross-job aggregator (BatteryHealthManager) feeds per-bucket drain stats
only from jobs that were **single-bucket** for that key — i.e. every room used
the same clean_mode (resp. fan_speed, water_level). The ``is_single_*`` flags
flip those gates. Over many runs the per-bucket means are unbiased; mixed
runs still get full job-level stats.
"""

from __future__ import annotations

from typing import Any

from ..profiles.room_profiles import canonical_clean_mode


def compute_job_battery_metrics(
    *,
    battery_start: int | None,
    battery_end: int | None,
    duration_minutes: float | None,
    cleaning_area_m2: float | None,
    resolved_rooms: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compute the battery_metrics block for a completed job.

    Returns a dict even when inputs are partial — fields that can't be
    computed are set to None so downstream consumers don't have to guard
    every key.
    """
    drain = _safe_drain(battery_start, battery_end)
    duration = _positive_float(duration_minutes)
    area = _positive_float(cleaning_area_m2)

    drain_per_min = round(drain / duration, 4) if drain is not None and duration else None
    drain_per_hour = round(drain_per_min * 60.0, 4) if drain_per_min is not None else None
    drain_per_m2 = round(drain / area, 4) if drain is not None and area else None

    rooms = [r for r in (resolved_rooms or []) if isinstance(r, dict)]
    weights, weighted_by = _prorate_weights(rooms)

    by_mode = _bucketed_share(rooms, weights, area, key="clean_mode")
    by_fan = _bucketed_share(rooms, weights, area, key="fan_speed")
    by_water = _bucketed_share(rooms, weights, area, key="water_level")
    by_passes = _bucketed_share(rooms, weights, area, key="clean_passes")
    edge_share = _binary_share(rooms, weights, key="edge_mopping")

    # "Single bucket" = every room in the job had the same value for this key.
    # Only single-bucket jobs feed per-bucket drain aggregates downstream.
    is_single_mode = len(by_mode) == 1
    is_single_fan = len(by_fan) == 1
    is_single_water = len(by_water) == 1
    single_mode = next(iter(by_mode)) if is_single_mode else None
    single_fan = next(iter(by_fan)) if is_single_fan else None
    single_water = next(iter(by_water)) if is_single_water else None

    return {
        "battery_used_pct": drain,
        "duration_min": duration,
        "area_m2": area,
        "drain_per_min": drain_per_min,
        "drain_per_hour": drain_per_hour,
        "drain_per_m2": drain_per_m2,
        "is_single_clean_mode": is_single_mode,
        "is_single_fan_speed": is_single_fan,
        "is_single_water_level": is_single_water,
        "single_clean_mode": single_mode,
        "single_fan_speed": single_fan,
        "single_water_level": single_water,
        "by_clean_mode": by_mode,
        "by_fan_speed": by_fan,
        "by_water_level": by_water,
        "passes_share": {k: v["share"] for k, v in by_passes.items()},
        "edge_mopping": edge_share,
        "weighted_by": weighted_by,
    }


# ============================================================================
# Helpers
# ============================================================================

def _safe_drain(start: Any, end: Any) -> int | None:
    try:
        s = int(start)
        e = int(end)
    except (TypeError, ValueError):
        return None
    drain = s - e
    return drain if drain >= 0 else None


def _positive_float(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _prorate_weights(
    rooms: list[dict[str, Any]],
) -> tuple[list[float], str]:
    """Return per-room weights (summing to 1.0) and a label describing how
    they were derived.

    Preference order:
    1. ``estimated_minutes`` from the learning enrichment.
    2. Equal weight per room.
    """
    if not rooms:
        return [], "none"

    estimates = []
    for room in rooms:
        try:
            est = float(room.get("estimated_minutes") or 0.0)
        except (TypeError, ValueError):
            est = 0.0
        estimates.append(est)

    total_est = sum(estimates)
    if total_est > 0:
        return [e / total_est for e in estimates], "estimated_minutes"

    equal = 1.0 / len(rooms)
    return [equal for _ in rooms], "room_count"


def _bucketed_share(
    rooms: list[dict[str, Any]],
    weights: list[float],
    area_m2: float | None,
    *,
    key: str,
) -> dict[str, dict[str, Any]]:
    """Sum weights and prorated area into buckets keyed by the given field.

    Missing/empty values are normalized to the literal string ``"unknown"``.
    """
    buckets: dict[str, dict[str, Any]] = {}
    if not rooms:
        return buckets

    for room, weight in zip(rooms, weights):
        raw_value = room.get(key)
        if key == "clean_mode":
            # ISSUE #48, and this one is already on disk. _bucket_key folds case and
            # nothing else, so "Vacuum and mop" and "vacuum_mop" bucket separately —
            # a survey of the live learning store found by_clean_mode keys
            # {'vacuum': 97, 'vacuum and mop': 5} across 103 job records. Two
            # spellings of ONE mode make len(buckets) == 2, which flips
            # is_single_clean_mode False and drops a genuinely single-mode run out of
            # per-mode battery-drain learning entirely.
            #
            # Canonicalized at the CALL SITE, not inside _bucket_key: that helper also
            # buckets fan_speed and water_level, which are brand vocabulary with no
            # canonical form core is entitled to impose.
            #
            # Records already written keep their old keys, so the card's fold in
            # renderers/metrics.js stays — it is reading history this cannot reach.
            raw_value = canonical_clean_mode(raw_value)
        bucket_key = _bucket_key(raw_value)
        bucket = buckets.setdefault(bucket_key, {"share": 0.0, "rooms": 0})
        bucket["share"] = round(bucket["share"] + weight, 6)
        bucket["rooms"] = int(bucket["rooms"]) + 1
        if area_m2:
            bucket["area_m2"] = round(bucket.get("area_m2", 0.0) + (weight * area_m2), 4)

    return buckets


def _binary_share(
    rooms: list[dict[str, Any]],
    weights: list[float],
    *,
    key: str,
) -> dict[str, float]:
    """Return on/off share for a boolean field. Sums to 1.0 unless rooms is empty."""
    on = 0.0
    off = 0.0
    for room, weight in zip(rooms, weights):
        if bool(room.get(key)):
            on += weight
        else:
            off += weight
    return {
        "on_share": round(on, 6),
        "off_share": round(off, 6),
    }


def _bucket_key(value: Any) -> str:
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    return text or "unknown"
