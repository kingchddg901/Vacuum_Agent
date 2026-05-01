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

Stats model (schema_version 3):
- Each room entry stores avg_minutes, minutes_min, minutes_max, and minutes_stddev
  so the estimator can compute confidence scores based on sample variance.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from ..timestamp_utils import parse_timestamp
from .history_store import LearningHistoryStore
from .utils import _iso_now, _room_profile_key, _safe_bool, _safe_float, _safe_int


def _parse_started_at(value: Any):
    """Parse stable timestamp formats."""
    return parse_timestamp(value)


def _room_key(
    map_id: Any,
    slug: Any,
    effective_mode: Any,
    clean_times: Any,
    is_carpet: Any,
    clean_intensity: Any = "",
) -> str:
    """Return exact room learning key."""
    return (
        f"{_safe_int(map_id, 0)}::"
        f"{str(slug or '').strip().lower()}::"
        f"{str(effective_mode or '').strip().lower()}::"
        f"{_safe_int(clean_times, 1)}::"
        f"{'1' if _safe_bool(is_carpet, False) else '0'}::"
        f"{str(clean_intensity or 'standard').strip().lower()}"
    )


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

            ended_at = job_info.get("ended_at")
            if isinstance(ended_at, str) and ended_at.strip():
                if latest_job_at is None or ended_at > latest_job_at:
                    latest_job_at = ended_at

        count = len(jobs)

        return {
            "schema_version": 3,
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
        # exact_key → list of per-room duration samples (used for stddev).
        room_samples: dict[str, list[float]] = {}
        room_stats: dict[str, dict[str, Any]] = {}
        room_baselines: dict[str, dict[str, Any]] = {}

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

            room_water_allocations, _job_water_totals = self._derive_room_water_allocations(
                job=job,
                rooms=rooms,
            )
            per_room_duration = total_duration / room_count
            per_room_battery = total_battery_used / room_count
            per_room_drift = total_job_drift / room_count
            map_id = _safe_int(profile.get("map_id"), 0)

            for room in rooms:
                if not isinstance(room, dict):
                    continue

                slug = str(room.get("slug", "")).strip().lower()
                if not slug:
                    continue

                effective_mode = str(
                    room.get("clean_mode", room.get("effective_mode", "unknown"))
                ).strip().lower() or "unknown"
                clean_times = _safe_int(
                    room.get("clean_passes", room.get("clean_times", 1)),
                    1,
                )
                if clean_times not in (1, 2):
                    clean_times = 1
                is_carpet = _safe_bool(
                    room.get("is_carpet", room.get("carpet", False)),
                    False,
                )
                clean_intensity = str(
                    room.get("clean_intensity", "standard")
                ).strip().lower() or "standard"

                exact_key = _room_key(map_id, slug, effective_mode, clean_times, is_carpet, clean_intensity)

                room_samples.setdefault(exact_key, []).append(per_room_duration)

                if exact_key not in room_stats:
                    room_stats[exact_key] = {
                        "map_id": map_id,
                        "room_slug": slug,
                        "effective_mode": effective_mode,
                        "clean_times": clean_times,
                        "is_carpet": is_carpet,
                        "clean_intensity": clean_intensity,
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
                room_stats[exact_key]["total_estimated_minutes"] += per_room_duration
                room_stats[exact_key]["total_estimated_battery_used"] += per_room_battery
                room_stats[exact_key]["total_robot_water_used_ml"] += _safe_float(room_water.get("robot_water_used_ml"), 0.0)
                room_stats[exact_key]["total_water_overhead_ml"] += _safe_float(room_water.get("water_overhead_ml"), 0.0)
                room_stats[exact_key]["total_water_used_ml"] += _safe_float(room_water.get("total_water_used_ml"), 0.0)
                room_stats[exact_key]["total_drift_minutes"] += per_room_drift
                room_stats[exact_key]["total_abs_drift_minutes"] += abs(per_room_drift)

                baseline_key = _room_baseline_key(map_id, slug)
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
                    }

                room_baselines[baseline_key]["sample_count"] += 1
                room_baselines[baseline_key]["total_estimated_minutes"] += per_room_duration
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

        output_exact: list[dict[str, Any]] = []
        for key in sorted(room_stats.keys()):
            item = room_stats[key]
            sample_count = max(_safe_int(item.get("sample_count"), 0), 1)
            samples = room_samples.get(key, [])
            avg_minutes = round(item["total_estimated_minutes"] / sample_count, 2)

            output_exact.append(
                {
                    "map_id": item["map_id"],
                    "room_slug": item["room_slug"],
                    "effective_mode": item["effective_mode"],
                    "clean_times": item["clean_times"],
                    "is_carpet": item["is_carpet"],
                    "clean_intensity": item["clean_intensity"],
                    "sample_count": item["sample_count"],
                    "avg_minutes": avg_minutes,
                    "avg_battery_used": round(item["total_estimated_battery_used"] / sample_count, 2),
                    "avg_robot_water_used_ml": round(item["total_robot_water_used_ml"] / sample_count, 2),
                    "avg_water_overhead_ml": round(item["total_water_overhead_ml"] / sample_count, 2),
                    "avg_total_water_used_ml": round(item["total_water_used_ml"] / sample_count, 2),
                    "avg_drift_minutes": round(item["total_drift_minutes"] / sample_count, 2),
                    "avg_abs_drift_minutes": round(item["total_abs_drift_minutes"] / sample_count, 2),
                    "minutes_min": round(min(samples), 2) if samples else avg_minutes,
                    "minutes_max": round(max(samples), 2) if samples else avg_minutes,
                    "minutes_stddev": _stddev(samples),
                }
            )

        output_baselines: list[dict[str, Any]] = []
        for key in sorted(room_baselines.keys()):
            item = room_baselines[key]
            sample_count = max(_safe_int(item.get("sample_count"), 0), 1)
            output_baselines.append(
                {
                    "map_id": item["map_id"],
                    "room_slug": item["room_slug"],
                    "sample_count": item["sample_count"],
                    "avg_minutes": round(item["total_estimated_minutes"] / sample_count, 2),
                    "avg_battery_used": round(item["total_estimated_battery_used"] / sample_count, 2),
                    "avg_robot_water_used_ml": round(item["total_robot_water_used_ml"] / sample_count, 2),
                    "avg_water_overhead_ml": round(item["total_water_overhead_ml"] / sample_count, 2),
                    "avg_total_water_used_ml": round(item["total_water_used_ml"] / sample_count, 2),
                    "avg_drift_minutes": round(item["total_drift_minutes"] / sample_count, 2),
                    "avg_abs_drift_minutes": round(item["total_abs_drift_minutes"] / sample_count, 2),
                    "effective_modes": item["effective_modes"],
                    "clean_times": item["clean_times"],
                    "carpet_true_count": item["carpet_true_count"],
                    "carpet_false_count": item["carpet_false_count"],
                }
            )

        return {
            "schema_version": 3,
            "vacuum_entity_id": vacuum_entity_id,
            "rebuilt_at": _iso_now(),
            "room_stats": output_exact,
            "room_baselines": output_baselines,
            "lookup_order": [
                "map_id + room_slug + effective_mode + clean_times + is_carpet + clean_intensity",
                "fallback 1: ignore clean_intensity (with confidence penalty)",
                "fallback 2: ignore is_carpet",
                "fallback 3: ignore clean_passes",
                "final fallback: room_baselines",
            ],
            "drift_note": (
                "avg_drift_minutes is currently allocated equally per room from job-level drift. "
                "minutes_stddev uses population stddev of per-room duration samples."
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

            job_entries.append(
                {
                    "job_id": job_id,
                    "started_at": job_info.get("started_at"),
                    "ended_at": job_info.get("ended_at"),
                    "duration_minutes": duration_minutes,
                    "room_count": room_count,
                    "room_slugs": room_slugs,
                    "status": str(outcome.get("status", "unknown")).strip().lower(),
                    "used_for_learning": bool(outcome.get("used_for_learning", False)),
                    "sanity_passed": bool(outcome.get("sanity_passed", False)),
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
