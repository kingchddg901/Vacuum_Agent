"""Rebuilds learned job and room stats from completed-job history for the optional learning system.

Responsibilities:
- rebuild learned job stats from completed-job JSON
- rebuild learned room stats and room baselines
- optionally rebuild flat CSV exports

Learning rules:
- all finalized jobs may exist in history
- only eligible completed jobs are used for learned stats
- cancelled / failed / interrupted / test jobs remain visible in exports/history
  but are excluded from learning

Stats model (room stats schema_version 6):
- The exact room_stats key is
  map_id::slug::effective_mode::clean_times::is_carpet::clean_intensity::edge_mopping
  — edge-mopping is in the key because it materially changes cleaning time, so
  edge-on and edge-off runs are learned as separate entries.
- Each room entry stores avg_minutes, minutes_min, minutes_max, and minutes_stddev
  so the estimator can compute confidence scores based on sample variance.
- Each room entry also stores avg_area_m2 (+ area_m2_min/max/stddev and
  area_sample_count), per room from counter-plateau capture (room_timings[].area_m2,
  single AND multi-room) or a single-room job's cleaning_area_m2 total. A partial-
  clean gate (area > 1.5 m2 off the room median) drops that clean's TIME from the
  timing stats (partial_excluded_count); area/battery/water keep all samples.
- Each room_baselines entry breaks its averages out by setting — by_clean_times
  (1 vs 2 passes) and by_edge_mopping (on vs off), each with sample_count,
  avg_minutes, minutes_min/max/stddev (a variance band), and avg_battery_used —
  alongside the full per-room average. All stats are learning-jobs-only (bad runs
  are excluded by the caller before aggregation). Area is not bucketed (it is
  settings-invariant).
- Transit/travel time (schema 5): transit_stats + access_graph_edges hold per
  room-pair travel time (avg/min/max/stddev seconds; minutes_mean/stddev),
  aggregated from each job's transitions only when transit_capture_valid;
  room_baselines also carry avg_ingress/egress_transit_seconds (+band). Transit
  is time-based / frame-invariant (raw coordinates drift across sessions).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from ..timestamp_utils import parse_timestamp
from .history_store import LearningHistoryStore
from .utils import (
    _canonical_clean_mode,
    _iso_now,
    _room_key,
    _room_profile_key,
    _safe_bool,
    _safe_float,
    _safe_int,
    compute_overhead_observed,
)


def _parse_started_at(value: Any):
    """Parse stable timestamp formats."""
    return parse_timestamp(value)


def _room_baseline_key(map_id: Any, slug: Any) -> str:
    """Return room baseline key."""
    return f"{_safe_int(map_id, 0)}::{str(slug or '').strip().lower()}"


def _stddev(values: list[float]) -> float:
    """Return population standard deviation of a list of floats."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return round(math.sqrt(variance), 4)


def _median(values: list[float]) -> float:
    """Return the median of a list of floats (0.0 if empty)."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


# Area-quality gate: a per-room clean whose covered area falls more than
# _AREA_GATE_TOL_M2 off the room's median area is a partial/interrupted clean whose
# TIME would poison the room's timing baseline — its minutes sample is excluded
# from the timing stats. Area is settings-invariant, so the band is per-room
# (baseline), not per-settings. Gated only once a room has >= _AREA_GATE_MIN_SAMPLES
# area samples to define a band. (~12% flagged on the archive; tightened Kitchen
# time stddev 101 -> 80 s — see scratch-external-estimator/gate.py.)
_AREA_GATE_TOL_M2 = 1.5
_AREA_GATE_MIN_SAMPLES = 4


def _gate_minutes_by_area(
    minutes: list[float],
    areas: list[float | None],
    median_area: float | None,
) -> tuple[list[float], int]:
    """Return (kept_minutes, excluded_count).

    A minutes sample is excluded when its paired area is more than _AREA_GATE_TOL_M2
    off median_area (a partial clean). Samples with no paired area, or when
    median_area is None (too few area samples to define a band), are kept. Never
    returns empty when given inputs — falls back to all minutes.
    """
    if median_area is None:
        return list(minutes), 0
    kept = [m for m, a in zip(minutes, areas) if a is None or abs(a - median_area) <= _AREA_GATE_TOL_M2]
    excluded = len(minutes) - len(kept)
    if not kept:
        return list(minutes), 0
    return kept, excluded


def _finalize_setting_buckets(buckets: dict[str, dict[str, list[float]]]) -> dict[str, dict[str, Any]]:
    """Reduce a {bucket: {minutes: [...], battery: [...]}} accumulator to an average
    plus a minutes_min/max/stddev band, so a consumer can match within variance
    rather than against a brittle point mean. Samples are learning-jobs-only."""
    out: dict[str, dict[str, Any]] = {}
    for bucket_key, acc in buckets.items():
        mins = acc.get("minutes", [])
        bat = acc.get("battery", [])
        n = len(mins)
        avg = round(sum(mins) / n, 2) if n else 0.0
        out[bucket_key] = {
            "sample_count": n,
            "avg_minutes": avg,
            "minutes_min": round(min(mins), 2) if mins else avg,
            "minutes_max": round(max(mins), 2) if mins else avg,
            "minutes_stddev": _stddev(mins),
            "avg_battery_used": round(sum(bat) / len(bat), 2) if bat else 0.0,
        }
    return out


def _seconds_band(
    samples: list[float],
    *,
    value_label: str = "seconds",
    count_key: str = "sample_count",
) -> dict[str, Any]:
    """Reduce a list of transit-second samples to an avg + min/max/stddev band.

    value_label/count_key let one reducer serve both the per-pair transit_stats
    (avg_seconds, seconds_min/max/stddev) and the per-room ingress/egress bands
    (avg_ingress_transit_seconds, ingress_transit_seconds_min/max/stddev, ...).
    Samples are learning-jobs-only and only from runs with transit_capture_valid.
    """
    n = len(samples)
    avg = round(sum(samples) / n, 2) if n else 0.0
    return {
        count_key: n,
        f"avg_{value_label}": avg,
        f"{value_label}_min": round(min(samples), 2) if samples else avg,
        f"{value_label}_max": round(max(samples), 2) if samples else avg,
        f"{value_label}_stddev": _stddev(samples),
    }


class LearningStatsRebuilder:
    """Rebuild learned stats and optional CSV exports."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = LearningHistoryStore(hass)

    def _job_drift_minutes(self, job: dict[str, Any]) -> float:
        """Return actual minus predicted duration drift in minutes."""
        job_info = job.get("job", {}) if isinstance(job.get("job"), dict) else {}

        started = _parse_started_at(job_info.get("started_at"))
        ended = _parse_started_at(job_info.get("ended_at"))
        predicted = _safe_float(job_info.get("duration_minutes"), 0.0)

        if started is None or ended is None or predicted <= 0:
            return 0.0

        actual = max((ended - started).total_seconds() / 60.0, 0.0)
        return round(actual - predicted, 2)

    def _derive_room_water_allocations(
        self,
        *,
        job: dict[str, Any],
        rooms: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
        """Return per-room and per-job water allocations from stored estimates."""
        water = job.get("water", {}) if isinstance(job.get("water"), dict) else {}
        total_robot_water = _safe_float(water.get("estimated_robot_water_used_ml"), 0.0)
        total_dock_overhead = _safe_float(water.get("estimated_dock_wash_water_used_ml"), 0.0) + _safe_float(
            water.get("estimated_dock_refill_water_used_ml"),
            0.0,
        )
        room_water_entries = water.get("rooms", []) if isinstance(water.get("rooms"), list) else []

        per_room_by_slug: dict[str, dict[str, float]] = {}
        robot_by_slug: dict[str, float] = {}
        mop_slugs: list[str] = []

        for entry in room_water_entries:
            if not isinstance(entry, dict):
                continue
            slug = str(entry.get("slug", "")).strip().lower()
            if not slug:
                continue
            robot_amount = _safe_float(entry.get("estimated_robot_water_used_ml"), 0.0)
            robot_by_slug[slug] = robot_amount
            if _safe_bool(entry.get("mop_active"), False):
                mop_slugs.append(slug)

        if not mop_slugs:
            for room in rooms:
                if not isinstance(room, dict):
                    continue
                slug = str(room.get("slug", "")).strip().lower()
                clean_mode = str(room.get("clean_mode", room.get("effective_mode", ""))).strip().lower()
                water_level = str(room.get("water_level", "")).strip().lower()
                if slug and "mop" in clean_mode and water_level not in {"", "off", "none"}:
                    mop_slugs.append(slug)

        if not robot_by_slug and mop_slugs and total_robot_water > 0:
            fallback_robot = total_robot_water / len(mop_slugs)
            for slug in mop_slugs:
                robot_by_slug[slug] = fallback_robot

        dock_overhead_per_mop_room = (total_dock_overhead / len(mop_slugs)) if mop_slugs else 0.0

        for room in rooms:
            if not isinstance(room, dict):
                continue
            slug = str(room.get("slug", "")).strip().lower()
            if not slug:
                continue
            robot_amount = robot_by_slug.get(slug, 0.0)
            overhead_amount = dock_overhead_per_mop_room if slug in mop_slugs else 0.0
            per_room_by_slug[slug] = {
                "robot_water_used_ml": round(robot_amount, 2),
                "water_overhead_ml": round(overhead_amount, 2),
                "total_water_used_ml": round(robot_amount + overhead_amount, 2),
            }

        return per_room_by_slug, {
            "robot_water_used_ml": round(total_robot_water, 2),
            "water_overhead_ml": round(total_dock_overhead, 2),
            "total_water_used_ml": round(total_robot_water + total_dock_overhead, 2),
        }

    def build_job_stats_payload(
        self,
        *,
        vacuum_entity_id: str,
        jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build learned job-level stats payload."""
        durations: list[float] = []
        battery_used_values: list[float] = []
        robot_water_values: list[float] = []
        water_overhead_values: list[float] = []
        total_water_values: list[float] = []
        room_counts: list[int] = []
        drift_values: list[float] = []
        abs_drift_values: list[float] = []
        overhead_values: list[float] = []
        overhead_entry_values: list[float] = []
        overhead_inter_room_values: list[float] = []
        overhead_return_values: list[float] = []
        overhead_recharge_values: list[float] = []
        latest_job_at = None

        for job in jobs:
            job_info = job.get("job", {}) if isinstance(job.get("job"), dict) else {}
            battery = job.get("battery", {}) if isinstance(job.get("battery"), dict) else {}
            water = job.get("water", {}) if isinstance(job.get("water"), dict) else {}

            room_count = _safe_int(job_info.get("room_count"), 0)
            _room_cleaning = job_info.get("room_cleaning_minutes")
            _actual_cleaning = job_info.get("actual_cleaning_minutes")
            duration = _safe_float(
                _room_cleaning if room_count == 1 and _room_cleaning is not None
                else _actual_cleaning if room_count == 1 and _actual_cleaning is not None
                else job_info.get("duration_minutes"),
                0.0,
            )
            battery_used = _safe_float(battery.get("used"), 0.0)
            robot_water = _safe_float(water.get("estimated_robot_water_used_ml"), 0.0)
            water_overhead = _safe_float(water.get("estimated_dock_wash_water_used_ml"), 0.0) + _safe_float(
                water.get("estimated_dock_refill_water_used_ml"),
                0.0,
            )
            drift = self._job_drift_minutes(job)

            durations.append(duration)
            battery_used_values.append(battery_used)
            robot_water_values.append(robot_water)
            water_overhead_values.append(water_overhead)
            total_water_values.append(robot_water + water_overhead)
            room_counts.append(room_count)
            drift_values.append(drift)
            abs_drift_values.append(abs(drift))

            # Observed overhead — use the job's stored block when present, else
            # derive it from job-level fields so historical jobs (pre-capture)
            # still contribute the retroactive job-level overhead.
            overhead = job_info.get("overhead_observed")
            if not isinstance(overhead, dict):
                overhead = compute_overhead_observed(job_info)
            overhead_values.append(_safe_float(overhead.get("total_overhead_minutes"), 0.0))
            if overhead.get("entry_minutes") is not None:
                overhead_entry_values.append(_safe_float(overhead.get("entry_minutes"), 0.0))
            if overhead.get("inter_room_minutes") is not None:
                overhead_inter_room_values.append(_safe_float(overhead.get("inter_room_minutes"), 0.0))
            if overhead.get("return_minutes") is not None:
                overhead_return_values.append(_safe_float(overhead.get("return_minutes"), 0.0))
            overhead_recharge_values.append(_safe_float(overhead.get("recharge_minutes"), 0.0))

            ended_at = job_info.get("ended_at")
            if isinstance(ended_at, str) and ended_at.strip():
                if latest_job_at is None or ended_at > latest_job_at:
                    latest_job_at = ended_at

        count = len(jobs)

        return {
            "schema_version": 4,
            "vacuum_entity_id": vacuum_entity_id,
            "rebuilt_at": _iso_now(),
            "job_stats": {
                "total_jobs": count,
                "avg_duration_minutes": round(sum(durations) / count, 2) if count else 0.0,
                "avg_battery_used": round(sum(battery_used_values) / count, 2) if count else 0.0,
                "avg_robot_water_used_ml": round(sum(robot_water_values) / count, 2) if count else 0.0,
                "avg_water_overhead_ml": round(sum(water_overhead_values) / count, 2) if count else 0.0,
                "avg_total_water_used_ml": round(sum(total_water_values) / count, 2) if count else 0.0,
                "avg_room_count": round(sum(room_counts) / count, 2) if count else 0.0,
                "avg_drift_minutes": round(sum(drift_values) / count, 2) if count else 0.0,
                "avg_abs_drift_minutes": round(sum(abs_drift_values) / count, 2) if count else 0.0,
                "min_duration_minutes": round(min(durations), 2) if count else 0.0,
                "max_duration_minutes": round(max(durations), 2) if count else 0.0,
                "min_battery_used": round(min(battery_used_values), 2) if count else 0.0,
                "max_battery_used": round(max(battery_used_values), 2) if count else 0.0,
                "min_total_water_used_ml": round(min(total_water_values), 2) if count else 0.0,
                "max_total_water_used_ml": round(max(total_water_values), 2) if count else 0.0,
                "avg_overhead_minutes": round(sum(overhead_values) / count, 2) if count else 0.0,
                "min_overhead_minutes": round(min(overhead_values), 2) if overhead_values else 0.0,
                "max_overhead_minutes": round(max(overhead_values), 2) if overhead_values else 0.0,
                "overhead_minutes_stddev": _stddev(overhead_values),
                "avg_overhead_entry_minutes": (
                    round(sum(overhead_entry_values) / len(overhead_entry_values), 2)
                    if overhead_entry_values else 0.0
                ),
                "avg_overhead_inter_room_minutes": (
                    round(sum(overhead_inter_room_values) / len(overhead_inter_room_values), 2)
                    if overhead_inter_room_values else 0.0
                ),
                "avg_overhead_return_minutes": (
                    round(sum(overhead_return_values) / len(overhead_return_values), 2)
                    if overhead_return_values else 0.0
                ),
                "avg_overhead_recharge_minutes": (
                    round(sum(overhead_recharge_values) / count, 2) if count else 0.0
                ),
                "overhead_sample_count": len(overhead_values),
                "overhead_entry_sample_count": len(overhead_entry_values),
                "overhead_inter_room_sample_count": len(overhead_inter_room_values),
                "latest_job_ended_at": latest_job_at,
            },
        }

    def build_room_stats_payload(
        self,
        *,
        vacuum_entity_id: str,
        jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build learned room stats and room baselines from a list of learning jobs."""
        # exact_key → per-room minutes samples + the area paired with each (for the
        # area-quality gate). The paired area is None when the job had no per-room
        # area capture (so that sample is never gated out).
        room_samples: dict[str, list[float]] = {}
        room_sample_areas: dict[str, list[float | None]] = {}
        # exact_key / baseline_key → cleaned-area samples. Per-room area now comes
        # from transit_capture_valid jobs (room_timings[].area_m2 — single AND
        # multi-room) or a single-room job's cleaning_area_m2 total.
        room_area_samples: dict[str, list[float]] = {}
        baseline_area_samples: dict[str, list[float]] = {}
        # baseline-level minutes samples + paired area (baseline area gate).
        baseline_samples: dict[str, list[float]] = {}
        baseline_sample_areas: dict[str, list[float | None]] = {}
        room_stats: dict[str, dict[str, Any]] = {}
        room_baselines: dict[str, dict[str, Any]] = {}
        # Transit (travel-time) accumulators: per-pair second-samples + identity
        # meta, plus per-room ingress/egress samples folded into room_baselines.
        # Only runs with transit_capture_valid contribute (see the job loop).
        transit_samples: dict[str, list[float]] = {}
        transit_meta: dict[str, dict[str, Any]] = {}
        ingress_samples: dict[str, list[float]] = {}
        egress_samples: dict[str, list[float]] = {}

        for job in jobs:
            job_info = job.get("job", {}) if isinstance(job.get("job"), dict) else {}
            profile = job.get("job_profile", {}) if isinstance(job.get("job_profile"), dict) else {}
            rooms = profile.get("rooms", []) if isinstance(profile.get("rooms"), list) else []

            total_duration = _safe_float(job_info.get("duration_minutes"), 0.0)
            total_battery_used = _safe_float(job.get("battery", {}).get("used"), 0.0)
            total_job_drift = self._job_drift_minutes(job)
            room_count = len(rooms)

            if room_count <= 0:
                continue

            # cleaning_area_m2 is a job total with no per-room split, so it is an
            # exact room area only for single-room jobs; multi-room jobs are
            # skipped for area aggregation.
            cleaning_area_m2 = _safe_float(job_info.get("cleaning_area_m2"), 0.0)
            is_single_room_job = room_count == 1

            room_water_allocations, _job_water_totals = self._derive_room_water_allocations(
                job=job,
                rooms=rooms,
            )
            per_room_duration = total_duration / room_count
            per_room_battery = total_battery_used / room_count
            per_room_drift = total_job_drift / room_count
            map_id = _safe_int(profile.get("map_id"), 0)

            # Per-room (area, wall-minutes) from counter-plateau capture — exact for
            # single AND multi-room jobs; room_minutes/room_area fall back to the
            # job level when a room has no captured segment.
            captured: dict[int, tuple[float, float]] = {}
            if _safe_bool(job_info.get("transit_capture_valid"), False):
                for _rt in (job_info.get("room_timings") or []):
                    if not isinstance(_rt, dict):
                        continue
                    _rid = _safe_int(_rt.get("room_id"), -1)
                    if _rid > 0:
                        captured[_rid] = (
                            _safe_float(_rt.get("area_m2"), 0.0),
                            _safe_float(_rt.get("cleaning_wall_seconds"), 0.0) / 60.0,
                        )

            for room in rooms:
                if not isinstance(room, dict):
                    continue

                slug = str(room.get("slug", "")).strip().lower()
                if not slug:
                    continue

                effective_mode = _canonical_clean_mode(
                    room.get("clean_mode", room.get("effective_mode", "unknown"))
                ) or "unknown"
                clean_times = _safe_int(
                    room.get("clean_passes", room.get("clean_times", 1)),
                    1,
                )
                # Preserve the reported pass count (Eufy caps at 1-2, Roborock
                # allows 1-3) — only reject sub-1 garbage. The old `not in (1, 2)`
                # clamp was Eufy-centric: it collapsed a Roborock 3-pass run into
                # clean_times=1, mis-bucketing it AND desyncing from utils._room_key
                # (the estimator's lookup key), which is lower-bound-only.
                if clean_times < 1:
                    clean_times = 1
                is_carpet = _safe_bool(
                    room.get("is_carpet", room.get("carpet", False)),
                    False,
                )
                clean_intensity = str(
                    room.get("clean_intensity", "standard")
                ).strip().lower() or "standard"
                edge_mopping = _safe_bool(room.get("edge_mopping", False), False)

                rid = _safe_int(room.get("room_id", room.get("id")), -1)
                _cap = captured.get(rid)
                if _cap is not None:
                    room_area = _cap[0] if _cap[0] > 0 else None
                    room_minutes = _cap[1] if _cap[1] > 0 else per_room_duration
                else:
                    room_area = cleaning_area_m2 if (is_single_room_job and cleaning_area_m2 > 0) else None
                    room_minutes = per_room_duration

                exact_key = _room_key(map_id, slug, effective_mode, clean_times, is_carpet, clean_intensity, edge_mopping)

                room_samples.setdefault(exact_key, []).append(room_minutes)
                room_sample_areas.setdefault(exact_key, []).append(room_area)
                if room_area is not None:
                    room_area_samples.setdefault(exact_key, []).append(room_area)

                if exact_key not in room_stats:
                    room_stats[exact_key] = {
                        "map_id": map_id,
                        "room_slug": slug,
                        "effective_mode": effective_mode,
                        "clean_times": clean_times,
                        "is_carpet": is_carpet,
                        "clean_intensity": clean_intensity,
                        "edge_mopping": edge_mopping,
                        "sample_count": 0,
                        "total_estimated_minutes": 0.0,
                        "total_estimated_battery_used": 0.0,
                        "total_robot_water_used_ml": 0.0,
                        "total_water_overhead_ml": 0.0,
                        "total_water_used_ml": 0.0,
                        "total_drift_minutes": 0.0,
                        "total_abs_drift_minutes": 0.0,
                    }

                room_water = room_water_allocations.get(slug, {})
                room_stats[exact_key]["sample_count"] += 1
                room_stats[exact_key]["total_estimated_minutes"] += room_minutes
                room_stats[exact_key]["total_estimated_battery_used"] += per_room_battery
                room_stats[exact_key]["total_robot_water_used_ml"] += _safe_float(room_water.get("robot_water_used_ml"), 0.0)
                room_stats[exact_key]["total_water_overhead_ml"] += _safe_float(room_water.get("water_overhead_ml"), 0.0)
                room_stats[exact_key]["total_water_used_ml"] += _safe_float(room_water.get("total_water_used_ml"), 0.0)
                room_stats[exact_key]["total_drift_minutes"] += per_room_drift
                room_stats[exact_key]["total_abs_drift_minutes"] += abs(per_room_drift)

                baseline_key = _room_baseline_key(map_id, slug)
                if room_area is not None:
                    baseline_area_samples.setdefault(baseline_key, []).append(room_area)
                baseline_samples.setdefault(baseline_key, []).append(room_minutes)
                baseline_sample_areas.setdefault(baseline_key, []).append(room_area)
                if baseline_key not in room_baselines:
                    room_baselines[baseline_key] = {
                        "map_id": map_id,
                        "room_slug": slug,
                        "sample_count": 0,
                        "total_estimated_minutes": 0.0,
                        "total_estimated_battery_used": 0.0,
                        "total_robot_water_used_ml": 0.0,
                        "total_water_overhead_ml": 0.0,
                        "total_water_used_ml": 0.0,
                        "total_drift_minutes": 0.0,
                        "total_abs_drift_minutes": 0.0,
                        "effective_modes": {},
                        "clean_times": {"1": 0, "2": 0},
                        "carpet_true_count": 0,
                        "carpet_false_count": 0,
                        "pass_buckets": {},
                        "edge_buckets": {},
                    }

                room_baselines[baseline_key]["sample_count"] += 1
                room_baselines[baseline_key]["total_estimated_minutes"] += room_minutes
                room_baselines[baseline_key]["total_estimated_battery_used"] += per_room_battery
                room_baselines[baseline_key]["total_robot_water_used_ml"] += _safe_float(room_water.get("robot_water_used_ml"), 0.0)
                room_baselines[baseline_key]["total_water_overhead_ml"] += _safe_float(room_water.get("water_overhead_ml"), 0.0)
                room_baselines[baseline_key]["total_water_used_ml"] += _safe_float(room_water.get("total_water_used_ml"), 0.0)
                room_baselines[baseline_key]["total_drift_minutes"] += per_room_drift
                room_baselines[baseline_key]["total_abs_drift_minutes"] += abs(per_room_drift)
                room_baselines[baseline_key]["effective_modes"][effective_mode] = (
                    room_baselines[baseline_key]["effective_modes"].get(effective_mode, 0) + 1
                )
                room_baselines[baseline_key]["clean_times"][str(clean_times)] = (
                    room_baselines[baseline_key]["clean_times"].get(str(clean_times), 0) + 1
                )

                if is_carpet:
                    room_baselines[baseline_key]["carpet_true_count"] += 1
                else:
                    room_baselines[baseline_key]["carpet_false_count"] += 1

                pass_bucket = room_baselines[baseline_key]["pass_buckets"].setdefault(
                    str(clean_times), {"minutes": [], "battery": []},
                )
                pass_bucket["minutes"].append(room_minutes)
                pass_bucket["battery"].append(per_room_battery)

                edge_bucket = room_baselines[baseline_key]["edge_buckets"].setdefault(
                    "on" if edge_mopping else "off", {"minutes": [], "battery": []},
                )
                edge_bucket["minutes"].append(room_minutes)
                edge_bucket["battery"].append(per_room_battery)

            # --- transit accumulation (job level, after the per-room loop) -----
            # Only valid captures contribute; per-pair seconds + per-room
            # ingress (transit INTO a room) / egress (transit OUT of a room).
            if _safe_bool(job_info.get("transit_capture_valid"), False):
                for tr in (job_info.get("transitions") or []):
                    if not isinstance(tr, dict):
                        continue
                    raw_secs = tr.get("transit_seconds")
                    if raw_secs is None:
                        continue
                    secs = _safe_float(raw_secs, 0.0)
                    from_id = _safe_int(tr.get("from_room_id"), -1)
                    to_id = _safe_int(tr.get("to_room_id"), -1)
                    if from_id <= 0 or to_id <= 0:
                        continue
                    from_slug = str(tr.get("from_slug") or "").strip().lower()
                    to_slug = str(tr.get("to_slug") or "").strip().lower()
                    pairkey = f"{map_id}::{from_id}->{to_id}"
                    transit_samples.setdefault(pairkey, []).append(secs)
                    transit_meta.setdefault(
                        pairkey,
                        {
                            "map_id": map_id,
                            "from_room_id": from_id,
                            "to_room_id": to_id,
                            "from_slug": tr.get("from_slug"),
                            "to_slug": tr.get("to_slug"),
                        },
                    )
                    if to_slug:
                        ingress_samples.setdefault(
                            _room_baseline_key(map_id, to_slug), []
                        ).append(secs)
                    if from_slug:
                        egress_samples.setdefault(
                            _room_baseline_key(map_id, from_slug), []
                        ).append(secs)

        output_exact: list[dict[str, Any]] = []
        for key in sorted(room_stats.keys()):
            item = room_stats[key]
            sample_count = max(_safe_int(item.get("sample_count"), 0), 1)
            samples = room_samples.get(key, [])
            area_samples = room_area_samples.get(key, [])
            area_count = len(area_samples)
            # Area-quality gate: drop partial cleans (area off the room's median)
            # from the TIMING stats. The band is per-room (baseline), area-invariant.
            _b_areas = baseline_area_samples.get(
                _room_baseline_key(item["map_id"], item["room_slug"]), []
            )
            _median_area = _median(_b_areas) if len(_b_areas) >= _AREA_GATE_MIN_SAMPLES else None
            gated, partial_excluded = _gate_minutes_by_area(
                samples, room_sample_areas.get(key, []), _median_area
            )
            avg_minutes = round(sum(gated) / len(gated), 2) if gated else 0.0

            output_exact.append(
                {
                    "map_id": item["map_id"],
                    "room_slug": item["room_slug"],
                    "effective_mode": item["effective_mode"],
                    "clean_times": item["clean_times"],
                    "is_carpet": item["is_carpet"],
                    "clean_intensity": item["clean_intensity"],
                    "edge_mopping": item["edge_mopping"],
                    "sample_count": item["sample_count"],
                    "avg_minutes": avg_minutes,
                    "avg_battery_used": round(item["total_estimated_battery_used"] / sample_count, 2),
                    "avg_robot_water_used_ml": round(item["total_robot_water_used_ml"] / sample_count, 2),
                    "avg_water_overhead_ml": round(item["total_water_overhead_ml"] / sample_count, 2),
                    "avg_total_water_used_ml": round(item["total_water_used_ml"] / sample_count, 2),
                    "avg_drift_minutes": round(item["total_drift_minutes"] / sample_count, 2),
                    "avg_abs_drift_minutes": round(item["total_abs_drift_minutes"] / sample_count, 2),
                    "minutes_min": round(min(gated), 2) if gated else avg_minutes,
                    "minutes_max": round(max(gated), 2) if gated else avg_minutes,
                    "minutes_stddev": _stddev(gated),
                    "timing_sample_count": len(gated),
                    "partial_excluded_count": partial_excluded,
                    "area_sample_count": area_count,
                    "avg_area_m2": round(sum(area_samples) / area_count, 2) if area_count else 0.0,
                    "area_m2_min": round(min(area_samples), 2) if area_count else 0.0,
                    "area_m2_max": round(max(area_samples), 2) if area_count else 0.0,
                    "area_m2_stddev": _stddev(area_samples),
                }
            )

        output_baselines: list[dict[str, Any]] = []
        for key in sorted(room_baselines.keys()):
            item = room_baselines[key]
            sample_count = max(_safe_int(item.get("sample_count"), 0), 1)
            area_samples = baseline_area_samples.get(key, [])
            area_count = len(area_samples)
            _b_median = _median(area_samples) if area_count >= _AREA_GATE_MIN_SAMPLES else None
            b_gated, b_partial = _gate_minutes_by_area(
                baseline_samples.get(key, []), baseline_sample_areas.get(key, []), _b_median
            )
            b_avg_minutes = round(sum(b_gated) / len(b_gated), 2) if b_gated else 0.0
            output_baselines.append(
                {
                    "map_id": item["map_id"],
                    "room_slug": item["room_slug"],
                    "sample_count": item["sample_count"],
                    "avg_minutes": b_avg_minutes,
                    "minutes_min": round(min(b_gated), 2) if b_gated else b_avg_minutes,
                    "minutes_max": round(max(b_gated), 2) if b_gated else b_avg_minutes,
                    "minutes_stddev": _stddev(b_gated),
                    "timing_sample_count": len(b_gated),
                    "partial_excluded_count": b_partial,
                    "avg_battery_used": round(item["total_estimated_battery_used"] / sample_count, 2),
                    "avg_robot_water_used_ml": round(item["total_robot_water_used_ml"] / sample_count, 2),
                    "avg_water_overhead_ml": round(item["total_water_overhead_ml"] / sample_count, 2),
                    "avg_total_water_used_ml": round(item["total_water_used_ml"] / sample_count, 2),
                    "avg_drift_minutes": round(item["total_drift_minutes"] / sample_count, 2),
                    "avg_abs_drift_minutes": round(item["total_abs_drift_minutes"] / sample_count, 2),
                    "area_sample_count": area_count,
                    "avg_area_m2": round(sum(area_samples) / area_count, 2) if area_count else 0.0,
                    "area_m2_min": round(min(area_samples), 2) if area_count else 0.0,
                    "area_m2_max": round(max(area_samples), 2) if area_count else 0.0,
                    "area_m2_stddev": _stddev(area_samples),
                    "effective_modes": item["effective_modes"],
                    "clean_times": item["clean_times"],
                    "carpet_true_count": item["carpet_true_count"],
                    "carpet_false_count": item["carpet_false_count"],
                    "by_clean_times": _finalize_setting_buckets(item["pass_buckets"]),
                    "by_edge_mopping": _finalize_setting_buckets(item["edge_buckets"]),
                    **_seconds_band(
                        ingress_samples.get(key, []),
                        value_label="ingress_transit_seconds",
                        count_key="ingress_sample_count",
                    ),
                    **_seconds_band(
                        egress_samples.get(key, []),
                        value_label="egress_transit_seconds",
                        count_key="egress_sample_count",
                    ),
                }
            )

        transit_stats: list[dict[str, Any]] = []
        access_graph_edges: list[dict[str, Any]] = []
        for pairkey in sorted(transit_samples.keys()):
            secs = transit_samples[pairkey]
            if not secs:
                continue
            meta = transit_meta.get(pairkey, {})
            identity = {
                "map_id": meta.get("map_id", 0),
                "from_room_id": meta.get("from_room_id"),
                "to_room_id": meta.get("to_room_id"),
                "from_slug": meta.get("from_slug"),
                "to_slug": meta.get("to_slug"),
            }
            transit_stats.append({**identity, **_seconds_band(secs)})
            n = len(secs)
            mins = [s / 60.0 for s in secs]
            access_graph_edges.append(
                {
                    **identity,
                    "sample_count": n,
                    "transit_minutes_mean": round(sum(mins) / n, 4),
                    "transit_minutes_stddev": _stddev(mins),
                }
            )

        return {
            "schema_version": 6,
            "vacuum_entity_id": vacuum_entity_id,
            "rebuilt_at": _iso_now(),
            "schema_version_note": "6: per-room area (multi-room) + area-quality gate",
            "room_stats": output_exact,
            "room_baselines": output_baselines,
            "transit_stats": transit_stats,
            "access_graph_edges": access_graph_edges,
            "lookup_order": [
                "map_id + room_slug + effective_mode + clean_times + is_carpet + clean_intensity + edge_mopping",
                "fallback 1: ignore clean_intensity (with confidence penalty)",
                "fallback 2: ignore is_carpet",
                "fallback 3: ignore edge_mopping",
                "fallback 4: ignore clean_passes",
                "final fallback: room_baselines",
            ],
            "drift_note": (
                "avg_drift_minutes is currently allocated equally per room from job-level drift. "
                "minutes_stddev uses population stddev of per-room duration samples."
            ),
            "area_note": (
                "avg_area_m2 is per-room: from counter-plateau capture (room_timings[].area_m2, "
                "single AND multi-room) on transit_capture_valid jobs, or a single-room job's "
                "cleaning_area_m2 total. area_sample_count is the number of area samples."
            ),
            "gate_note": (
                "Area-quality gate: a per-room clean whose area is > 1.5 m2 off the room's median "
                "(needs >= 4 area samples) is treated as partial/interrupted and excluded from the "
                "TIMING stats (avg_minutes + band). partial_excluded_count reports how many were "
                "dropped; timing_sample_count is the kept count. Area / battery / water keep all "
                "samples."
            ),
            "buckets_note": (
                "room_baselines.by_clean_times / by_edge_mopping break the per-room average out "
                "by setting (1 vs 2 passes; edge mop on vs off), each carrying a minutes_min/max/"
                "stddev band so a consumer can match within variance, not against a point mean. "
                "All stats are learning-jobs-only (bad runs excluded). Area is not bucketed."
            ),
            "transit_note": (
                "transit_stats / access_graph_edges hold per room-pair travel time aggregated "
                "from each job's transitions, only when transit_capture_valid. transit_stats is "
                "in seconds (avg/min/max/stddev); access_graph_edges mirrors it in minutes "
                "(transit_minutes_mean/stddev) for the estimator + access graph. room_baselines "
                "carry avg_ingress/egress_transit_seconds (+band). Transit is time-based / "
                "frame-invariant — raw coordinates drift across sessions, so geometry is unused."
            ),
        }

    def build_jobs_index_payload(
        self,
        *,
        vacuum_entity_id: str,
        jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build filter-friendly job, room, and room-profile indexes."""
        job_entries: list[dict[str, Any]] = []
        room_index: dict[str, dict[str, Any]] = {}
        room_profile_index: dict[str, dict[str, Any]] = {}

        for job in jobs:
            if not isinstance(job, dict) or job.get("record_type") != "completed_job":
                continue

            job_id = str(job.get("job_id", "")).strip()
            job_info = job.get("job", {}) if isinstance(job.get("job"), dict) else {}
            battery = job.get("battery", {}) if isinstance(job.get("battery"), dict) else {}
            water = job.get("water", {}) if isinstance(job.get("water"), dict) else {}
            outcome = job.get("outcome", {}) if isinstance(job.get("outcome"), dict) else {}
            profile = job.get("job_profile", {}) if isinstance(job.get("job_profile"), dict) else {}
            rooms = profile.get("rooms", []) if isinstance(profile.get("rooms"), list) else []
            room_slugs = [
                str(room.get("slug", "")).strip().lower()
                for room in rooms
                if isinstance(room, dict) and str(room.get("slug", "")).strip()
            ]
            room_count = _safe_int(job_info.get("room_count"), len(room_slugs))
            _room_cleaning = job_info.get("room_cleaning_minutes")
            _actual_cleaning = job_info.get("actual_cleaning_minutes")
            duration_minutes = round(_safe_float(
                _room_cleaning if room_count == 1 and _room_cleaning is not None
                else _actual_cleaning if room_count == 1 and _actual_cleaning is not None
                else job_info.get("duration_minutes"),
                0.0,
            ), 2)
            battery_used = round(_safe_float(battery.get("used"), 0.0), 2)
            robot_water_used = round(_safe_float(water.get("estimated_robot_water_used_ml"), 0.0), 2)
            water_overhead_used = round(
                _safe_float(water.get("estimated_dock_wash_water_used_ml"), 0.0)
                + _safe_float(water.get("estimated_dock_refill_water_used_ml"), 0.0),
                2,
            )
            total_water_used = round(robot_water_used + water_overhead_used, 2)

            # Origin flows to the review card so an EXTERNAL run reads as "External"
            # (its own flag), not a borrowed sanity/learning verdict. External runs
            # graduate only past the tier-1 identity gate with a valid duration + room
            # set, so they are sane BY CONSTRUCTION (see external_ingest) — force
            # sanity_passed True so an OLD graduated record that predates that explicit
            # flag (missing key -> coerced False here) is never mislabeled "Sanity
            # Failed". cleaning_area_m2 surfaces on the review row so the human
            # include/exclude call sees how much floor the run covered.
            origin = str(job.get("origin") or outcome.get("origin") or "").strip().lower() or None
            is_external = origin == "external"
            # The finalizer stamps a job-level cleaning_area_m2 (sensor read, any room
            # count). EXTERNAL records are built by external_ingest — no finalizer, no
            # sensor — so they carry only per-room room_timings[].area_m2. Fall back to
            # summing those so external runs (single AND multi-room) also show an area.
            cleaning_area_m2 = _safe_float(job_info.get("cleaning_area_m2"), None)
            if cleaning_area_m2 is None:
                _timings = job_info.get("room_timings")
                if isinstance(_timings, list) and _timings:
                    _area_sum = sum(
                        _safe_float(t.get("area_m2"), 0.0)
                        for t in _timings
                        if isinstance(t, dict)
                    )
                    cleaning_area_m2 = _area_sum if _area_sum > 0 else None

            job_entries.append(
                {
                    "job_id": job_id,
                    "started_at": job_info.get("started_at"),
                    "ended_at": job_info.get("ended_at"),
                    "duration_minutes": duration_minutes,
                    "room_count": room_count,
                    "room_slugs": room_slugs,
                    "status": str(outcome.get("status", "unknown")).strip().lower(),
                    "origin": origin,
                    "cleaning_area_m2": round(cleaning_area_m2, 2) if cleaning_area_m2 is not None else None,
                    "used_for_learning": bool(outcome.get("used_for_learning", False)),
                    "sanity_passed": True if is_external else bool(outcome.get("sanity_passed", False)),
                    "battery_used": battery_used,
                    "robot_water_used_ml": robot_water_used,
                    "water_overhead_ml": water_overhead_used,
                    "total_water_used_ml": total_water_used,
                    "cancel_detection": outcome.get("cancel_detection", {}),
                    "mid_job_recharge_observed": bool(battery.get("mid_job_recharge_observed", False)),
                }
            )

            allocated_duration = round(duration_minutes / max(len(rooms), 1), 2)
            allocated_battery = round(battery_used / max(len(rooms), 1), 2)
            room_water_allocations, _job_water_totals = self._derive_room_water_allocations(
                job=job,
                rooms=rooms,
            )

            for room in rooms:
                if not isinstance(room, dict):
                    continue
                slug = str(room.get("slug", "")).strip().lower()
                if not slug:
                    continue

                room_item = room_index.setdefault(
                    slug,
                    {
                        "room_slug": slug,
                        "run_count": 0,
                        "learning_run_count": 0,
                        "total_duration_minutes": 0.0,
                        "total_battery_used": 0.0,
                        "total_robot_water_used_ml": 0.0,
                        "total_water_overhead_ml": 0.0,
                        "total_water_used_ml": 0.0,
                        "last_job_id": None,
                        "last_ended_at": None,
                        "status_counts": {},
                        "profile_keys": {},
                    },
                )
                room_water = room_water_allocations.get(slug, {})
                room_item["run_count"] += 1
                room_item["learning_run_count"] += 1 if outcome.get("used_for_learning", False) else 0
                room_item["total_duration_minutes"] += allocated_duration
                room_item["total_battery_used"] += allocated_battery
                room_item["total_robot_water_used_ml"] += _safe_float(room_water.get("robot_water_used_ml"), 0.0)
                room_item["total_water_overhead_ml"] += _safe_float(room_water.get("water_overhead_ml"), 0.0)
                room_item["total_water_used_ml"] += _safe_float(room_water.get("total_water_used_ml"), 0.0)
                room_item["status_counts"][str(outcome.get("status", "unknown")).strip().lower()] = (
                    room_item["status_counts"].get(str(outcome.get("status", "unknown")).strip().lower(), 0) + 1
                )
                room_item["profile_keys"][_room_profile_key(room)] = (
                    room_item["profile_keys"].get(_room_profile_key(room), 0) + 1
                )
                ended_at = job_info.get("ended_at")
                if isinstance(ended_at, str) and ended_at.strip():
                    if room_item["last_ended_at"] is None or ended_at > room_item["last_ended_at"]:
                        room_item["last_ended_at"] = ended_at
                        room_item["last_job_id"] = job_id

                profile_key = _room_profile_key(room)
                profile_item = room_profile_index.setdefault(
                    profile_key,
                    {
                        "profile_key": profile_key,
                        "room_slug": slug,
                        "selected_profile_name": str(
                            room.get("selected_profile_name", room.get("resolved_profile_name", ""))
                        ).strip().lower(),
                        "resolved_profile_name": str(room.get("resolved_profile_name", "")).strip().lower(),
                        "clean_mode": str(room.get("clean_mode", "")).strip().lower(),
                        "clean_intensity": str(room.get("clean_intensity", "")).strip().lower(),
                        "fan_speed": str(room.get("fan_speed", "")).strip().lower(),
                        "water_level": str(room.get("water_level", "")).strip().lower(),
                        "clean_passes": _safe_int(room.get("clean_passes", room.get("clean_times", 1)), 1),
                        "carpet": _safe_bool(room.get("is_carpet", room.get("carpet", False)), False),
                        "edge_mopping": _safe_bool(room.get("edge_mopping", False), False),
                        "run_count": 0,
                        "learning_run_count": 0,
                        "total_duration_minutes": 0.0,
                        "total_battery_used": 0.0,
                        "total_robot_water_used_ml": 0.0,
                        "total_water_overhead_ml": 0.0,
                        "total_water_used_ml": 0.0,
                        "last_job_id": None,
                        "last_ended_at": None,
                        "status_counts": {},
                    },
                )
                profile_item["run_count"] += 1
                profile_item["learning_run_count"] += 1 if outcome.get("used_for_learning", False) else 0
                profile_item["total_duration_minutes"] += allocated_duration
                profile_item["total_battery_used"] += allocated_battery
                profile_item["total_robot_water_used_ml"] += _safe_float(room_water.get("robot_water_used_ml"), 0.0)
                profile_item["total_water_overhead_ml"] += _safe_float(room_water.get("water_overhead_ml"), 0.0)
                profile_item["total_water_used_ml"] += _safe_float(room_water.get("total_water_used_ml"), 0.0)
                profile_item["status_counts"][str(outcome.get("status", "unknown")).strip().lower()] = (
                    profile_item["status_counts"].get(str(outcome.get("status", "unknown")).strip().lower(), 0) + 1
                )
                if isinstance(ended_at, str) and ended_at.strip():
                    if profile_item["last_ended_at"] is None or ended_at > profile_item["last_ended_at"]:
                        profile_item["last_ended_at"] = ended_at
                        profile_item["last_job_id"] = job_id

        job_entries.sort(key=lambda item: str(item.get("ended_at") or ""), reverse=True)

        room_entries: list[dict[str, Any]] = []
        for slug in sorted(room_index.keys()):
            item = room_index[slug]
            run_count = max(_safe_int(item.get("run_count"), 0), 1)
            room_entries.append(
                {
                    "room_slug": slug,
                    "run_count": item["run_count"],
                    "learning_run_count": item["learning_run_count"],
                    "avg_duration_minutes": round(item["total_duration_minutes"] / run_count, 2),
                    "avg_battery_used": round(item["total_battery_used"] / run_count, 2),
                    "avg_robot_water_used_ml": round(item["total_robot_water_used_ml"] / run_count, 2),
                    "avg_water_overhead_ml": round(item["total_water_overhead_ml"] / run_count, 2),
                    "avg_total_water_used_ml": round(item["total_water_used_ml"] / run_count, 2),
                    "last_job_id": item["last_job_id"],
                    "last_ended_at": item["last_ended_at"],
                    "status_counts": item["status_counts"],
                    "profile_keys": item["profile_keys"],
                }
            )

        room_profile_entries: list[dict[str, Any]] = []
        for key in sorted(room_profile_index.keys()):
            item = room_profile_index[key]
            run_count = max(_safe_int(item.get("run_count"), 0), 1)
            room_profile_entries.append(
                {
                    **{
                        k: v
                        for k, v in item.items()
                        if k
                        not in {
                            "total_duration_minutes",
                            "total_battery_used",
                            "total_robot_water_used_ml",
                            "total_water_overhead_ml",
                            "total_water_used_ml",
                        }
                    },
                    "avg_duration_minutes": round(item["total_duration_minutes"] / run_count, 2),
                    "avg_battery_used": round(item["total_battery_used"] / run_count, 2),
                    "avg_robot_water_used_ml": round(item["total_robot_water_used_ml"] / run_count, 2),
                    "avg_water_overhead_ml": round(item["total_water_overhead_ml"] / run_count, 2),
                    "avg_total_water_used_ml": round(item["total_water_used_ml"] / run_count, 2),
                }
            )

        return {
            "schema_version": 1,
            "vacuum_entity_id": vacuum_entity_id,
            "rebuilt_at": _iso_now(),
            "job_count": len(job_entries),
            "jobs": job_entries,
            "rooms": room_entries,
            "room_profiles": room_profile_entries,
        }

    def _job_export_row(self, job: dict[str, Any]) -> list[Any]:
        """Build one flat jobs CSV row."""
        job_id = job.get("job_id", "")
        job_info = job.get("job", {}) if isinstance(job.get("job"), dict) else {}
        battery = job.get("battery", {}) if isinstance(job.get("battery"), dict) else {}
        profile = job.get("job_profile", {}) if isinstance(job.get("job_profile"), dict) else {}
        outcome = job.get("outcome", {}) if isinstance(job.get("outcome"), dict) else {}
        water = job.get("water", {}) if isinstance(job.get("water"), dict) else {}

        sanity_flags = outcome.get("sanity_flags", [])
        if isinstance(sanity_flags, list):
            sanity_flags = "|".join(str(x) for x in sanity_flags)

        learning_blockers = outcome.get("learning_blockers", [])
        if isinstance(learning_blockers, list):
            learning_blockers = "|".join(str(x) for x in learning_blockers)

        job_drift_minutes = self._job_drift_minutes(job)
        job_abs_drift_minutes = abs(job_drift_minutes)

        water_estimated = water.get("estimated_total_dock_clean_water_used_ml")
        water_end_pct = water.get("actual_end_station_clean_water_percent")
        water_actual_ml = water.get("actual_dock_water_used_ml")

        return [
            job_id,
            job_info.get("started_at", ""),
            job_info.get("ended_at", ""),
            _safe_int(profile.get("map_id"), 0),
            _safe_int(job_info.get("room_count"), 0),
            round(_safe_float(job_info.get("duration_minutes"), 0.0), 2),
            _safe_int(battery.get("start"), 0),
            _safe_int(battery.get("end"), 0),
            round(_safe_float(battery.get("used"), 0.0), 2),
            str(outcome.get("status", "unknown")),
            bool(outcome.get("used_for_learning", False)),
            bool(outcome.get("sanity_passed", False)),
            sanity_flags,
            learning_blockers,
            round(job_drift_minutes, 2),
            round(job_abs_drift_minutes, 2),
            round(_safe_float(water_estimated, 0.0), 1) if water_estimated is not None else "",
            round(_safe_float(water_end_pct, 0.0), 1) if water_end_pct is not None else "",
            round(_safe_float(water_actual_ml, 0.0), 1) if water_actual_ml is not None else "",
        ]

    def _room_export_rows(self, job: dict[str, Any]) -> list[list[Any]]:
        """Build flat rooms CSV rows for one completed job."""
        rows: list[list[Any]] = []

        job_id = job.get("job_id", "")
        job_info = job.get("job", {}) if isinstance(job.get("job"), dict) else {}
        battery = job.get("battery", {}) if isinstance(job.get("battery"), dict) else {}
        profile = job.get("job_profile", {}) if isinstance(job.get("job_profile"), dict) else {}
        outcome = job.get("outcome", {}) if isinstance(job.get("outcome"), dict) else {}

        rooms = profile.get("rooms", []) if isinstance(profile.get("rooms"), list) else []
        room_count = max(len(rooms), 1)

        job_duration = round(_safe_float(job_info.get("duration_minutes"), 0.0), 2)
        job_battery_used = round(_safe_float(battery.get("used"), 0.0), 2)
        job_drift_minutes = round(self._job_drift_minutes(job), 2)
        job_abs_drift_minutes = round(abs(job_drift_minutes), 2)

        allocated_room_minutes = round(job_duration / room_count, 2)
        allocated_room_battery = round(job_battery_used / room_count, 2)
        allocated_room_drift = round(job_drift_minutes / room_count, 2)
        allocated_room_abs_drift = round(job_abs_drift_minutes / room_count, 2)

        sanity_flags = outcome.get("sanity_flags", [])
        if isinstance(sanity_flags, list):
            sanity_flags = "|".join(str(x) for x in sanity_flags)

        learning_blockers = outcome.get("learning_blockers", [])
        if isinstance(learning_blockers, list):
            learning_blockers = "|".join(str(x) for x in learning_blockers)

        for room in rooms:
            if not isinstance(room, dict):
                continue

            rows.append(
                [
                    job_id,
                    job_info.get("started_at", ""),
                    job_info.get("ended_at", ""),
                    _safe_int(profile.get("map_id"), 0),
                    room.get("slug", ""),
                    _safe_int(room.get("room_id", room.get("id", 0)), 0),
                    _safe_int(room.get("room_order", 0), 0),
                    room.get("requested_mode", room.get("selected_profile_name", "")),
                    room.get("effective_mode", room.get("clean_mode", "")),
                    _safe_int(room.get("clean_times", room.get("clean_passes", 1)), 1),
                    room.get("fan_speed", ""),
                    room.get("water_level", ""),
                    room.get("clean_intensity", ""),
                    bool(room.get("edge_mopping", False)),
                    bool(room.get("is_carpet", room.get("carpet", False))),
                    _safe_int(job_info.get("room_count"), 0),
                    job_duration,
                    job_battery_used,
                    str(outcome.get("status", "unknown")),
                    bool(outcome.get("used_for_learning", False)),
                    bool(outcome.get("sanity_passed", False)),
                    sanity_flags,
                    learning_blockers,
                    allocated_room_minutes,
                    allocated_room_battery,
                    allocated_room_drift,
                    allocated_room_abs_drift,
                ]
            )

        return rows

    def rebuild_csv_exports(
        self,
        *,
        vacuum_entity_id: str,
        jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Rebuild flat CSV exports from completed jobs."""
        job_rows: list[list[Any]] = []
        room_rows: list[list[Any]] = []

        for job in jobs:
            if not isinstance(job, dict):
                continue
            if job.get("record_type") != "completed_job":
                continue

            job_rows.append(self._job_export_row(job))
            room_rows.extend(self._room_export_rows(job))

        jobs_csv_path = self.store.rebuild_jobs_csv(
            vacuum_entity_id=vacuum_entity_id,
            rows=job_rows,
        )
        rooms_csv_path = self.store.rebuild_rooms_csv(
            vacuum_entity_id=vacuum_entity_id,
            rows=room_rows,
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "jobs_csv": str(jobs_csv_path),
            "rooms_csv": str(rooms_csv_path),
            "job_rows_written": len(job_rows),
            "room_rows_written": len(room_rows),
        }

    def rebuild_all(
        self,
        *,
        vacuum_entity_id: str,
        rebuild_csv: bool = False,
    ) -> dict[str, Any]:
        """Rebuild learned stats and optional CSV exports from completed jobs."""
        all_jobs = self.store.load_all_completed_jobs(vacuum_entity_id=vacuum_entity_id)
        learning_jobs = [job for job in all_jobs if self.store.is_learning_job(job)]

        job_stats_payload = self.build_job_stats_payload(
            vacuum_entity_id=vacuum_entity_id,
            jobs=learning_jobs,
        )
        room_stats_payload = self.build_room_stats_payload(
            vacuum_entity_id=vacuum_entity_id,
            jobs=learning_jobs,
        )

        job_stats_path = self.store.save_job_stats(
            vacuum_entity_id=vacuum_entity_id,
            payload=job_stats_payload,
        )
        room_stats_path = self.store.save_room_stats(
            vacuum_entity_id=vacuum_entity_id,
            payload=room_stats_payload,
        )
        jobs_index_payload = self.build_jobs_index_payload(
            vacuum_entity_id=vacuum_entity_id,
            jobs=all_jobs,
        )
        jobs_index_path = self.store.save_jobs_index(
            vacuum_entity_id=vacuum_entity_id,
            payload=jobs_index_payload,
        )

        csv_result = None
        if rebuild_csv:
            csv_result = self.rebuild_csv_exports(
                vacuum_entity_id=vacuum_entity_id,
                jobs=all_jobs,
            )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "job_files_found": len(all_jobs),
            "learning_jobs_used": len(learning_jobs),
            "job_stats_path": str(job_stats_path),
            "room_stats_path": str(room_stats_path),
            "jobs_index_path": str(jobs_index_path),
            "csv": csv_result,
        }
