"""Saved-zone learning — a deliberately tiny parallel to room learning.

A saved zone is far simpler to learn than a room: it has a stable ``zone_id`` (no
slug-matching), a deterministic area from its coords (never learned), and it cleans in one
uninterrupted pass (no counter-stream segmentation, no transit, no drift). So the only thing
learned is TIME, and it is learned as a WALL-CLOCK total (phase dispatch -> completion, so a
mop zone's prep + post-wash count as the wait the user actually experiences), keyed by
``(zone_id, clean_mode)`` where clean_mode is the coarse ``"mop"`` / ``"vacuum"`` bucket (the
one dimension that materially changes a zone's time).

This module is PURE (no hass, no I/O) so it unit-tests as plain functions. The store it
maintains lives on the map bucket (``map_bucket["learned_zones"]``), persisted with the map:

    {
      "<zone_id>": {
        "mop":    {"avg_wall_seconds": float, "sample_count": int,
                   "last_wall_seconds": int, "last_area_m2": float | None, "updated_at": iso},
        "vacuum": { ... },
      },
    }

Only COMPLETED runs feed the average (a cancelled/partial zone would under-count) — the caller
gates on outcome; only SINGLE-zone steps are attributable, so a multi-zone step is recorded on
the job but skipped here. Estimation reads the same store, falling back to area x a per-mode
rate before any sample exists.
"""

from __future__ import annotations

from typing import Any

# Cold-start fallback: seconds per m² of zone footprint, before any sample exists. A mop pass
# (with its prep + wash) is much slower per m² than a vacuum pass. These are only used until the
# first real observation for a (zone_id, mode) replaces them; the learned average takes over
# immediately at sample_count >= 1.
_FALLBACK_SECONDS_PER_M2 = {"mop": 240.0, "vacuum": 60.0}
# Floor/ceiling so a degenerate area or a wild single sample can't produce an absurd ETA.
_MIN_ESTIMATE_SECONDS = 30
_MAX_ESTIMATE_SECONDS = 3600


def normalize_clean_mode(has_mop_mode: Any) -> str:
    """Coarsen a job's mode to the learning bucket. Mop and vacuum passes differ enough in
    time (a mop zone docks to wet the pad and washes after) that they must not share samples."""
    return "mop" if bool(has_mop_mode) else "vacuum"


def collect_zone_observations(active_job: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Pull learnable zone observations from a finalized job's phases.

    Each ``zone`` phase carries a ``zone_timing`` snapshot (written by the phase-runner at
    completion). Only SINGLE-zone observations are returned — a multi-zone step's wall time
    can't be attributed to one ``zone_id``, so it is skipped for learning (still estimated, as
    the sum of its zones). An observation needs a positive wall time to be worth learning."""
    if not isinstance(active_job, dict):
        return []
    phases = active_job.get("phases")
    if not isinstance(phases, list):
        return []
    out: list[dict[str, Any]] = []
    for phase in phases:
        if not isinstance(phase, dict) or phase.get("phase_type") != "zone":
            continue
        timing = phase.get("zone_timing")
        if not isinstance(timing, dict):
            continue
        zone_ids = timing.get("zone_ids") or []
        if len(zone_ids) != 1:
            continue  # multi-zone step: time isn't attributable to one zone_id
        try:
            wall = int(timing.get("wall_seconds"))
        except (TypeError, ValueError):
            continue
        if wall <= 0:
            continue
        area = timing.get("area_m2")
        try:
            area = float(area) if area is not None else None
        except (TypeError, ValueError):
            area = None
        out.append({
            "zone_id": str(zone_ids[0]),
            "clean_mode": str(timing.get("clean_mode") or "vacuum"),
            "wall_seconds": wall,
            "area_m2": area,
        })
    return out


def update_learned_zone(
    store: dict[str, Any],
    *,
    zone_id: str,
    clean_mode: str,
    wall_seconds: int,
    area_m2: float | None,
    now_iso: str,
) -> dict[str, Any]:
    """Fold one observation into the learned-zones ``store`` (mutated + returned).

    Incremental running mean, so history isn't re-scanned. Keyed ``store[zone_id][mode]``; a
    fresh key starts at the single sample. Defensive: a non-dict store/bucket is re-seeded."""
    if not isinstance(store, dict):
        store = {}
    mode = "mop" if str(clean_mode).strip().lower() == "mop" else "vacuum"
    by_mode = store.setdefault(str(zone_id), {})
    if not isinstance(by_mode, dict):
        by_mode = {}
        store[str(zone_id)] = by_mode
    prev = by_mode.get(mode)
    if isinstance(prev, dict):
        try:
            n = int(prev.get("sample_count") or 0)
            avg = float(prev.get("avg_wall_seconds") or 0.0)
        except (TypeError, ValueError):
            n, avg = 0, 0.0
    else:
        n, avg = 0, 0.0
    new_n = n + 1
    new_avg = (avg * n + float(wall_seconds)) / new_n
    by_mode[mode] = {
        "avg_wall_seconds": round(new_avg, 1),
        "sample_count": new_n,
        "last_wall_seconds": int(wall_seconds),
        "last_area_m2": round(area_m2, 2) if area_m2 is not None else None,
        "updated_at": now_iso,
    }
    return store


def record_observations(
    store: dict[str, Any] | None,
    observations: list[dict[str, Any]],
    *,
    now_iso: str,
) -> tuple[dict[str, Any], int]:
    """Fold every observation into ``store``; return ``(store, applied_count)``. A no-op (0)
    when there is nothing to learn, so the caller can skip persistence."""
    store = store if isinstance(store, dict) else {}
    applied = 0
    for obs in observations or []:
        try:
            update_learned_zone(
                store,
                zone_id=obs["zone_id"],
                clean_mode=obs.get("clean_mode", "vacuum"),
                wall_seconds=obs["wall_seconds"],
                area_m2=obs.get("area_m2"),
                now_iso=now_iso,
            )
            applied += 1
        except (KeyError, TypeError, ValueError):
            continue
    return store, applied


def estimate_zone_seconds(
    store: dict[str, Any] | None,
    *,
    zone_id: str,
    clean_mode: str,
    area_m2: float | None = None,
) -> dict[str, Any]:
    """Estimate one zone's wall-clock seconds for a mode.

    Returns ``{"seconds": int, "source": "learned"|"area_fallback"|"none", "sample_count": int}``.
    Learned average wins the moment a sample exists; before that, area x a per-mode rate; with
    neither, ``source == "none"`` and ``seconds == 0`` (the caller renders "learning…")."""
    mode = "mop" if str(clean_mode).strip().lower() == "mop" else "vacuum"
    bucket = None
    if isinstance(store, dict):
        by_mode = store.get(str(zone_id))
        if isinstance(by_mode, dict):
            bucket = by_mode.get(mode)
    if isinstance(bucket, dict):
        try:
            n = int(bucket.get("sample_count") or 0)
            avg = float(bucket.get("avg_wall_seconds") or 0.0)
        except (TypeError, ValueError):
            n, avg = 0, 0.0
        if n >= 1 and avg > 0:
            return {
                "seconds": _clamp_estimate(avg),
                "source": "learned",
                "sample_count": n,
            }
    try:
        a = float(area_m2) if area_m2 is not None else None
    except (TypeError, ValueError):
        a = None
    if a is not None and a > 0:
        rate = _FALLBACK_SECONDS_PER_M2.get(mode, _FALLBACK_SECONDS_PER_M2["vacuum"])
        return {
            "seconds": _clamp_estimate(a * rate),
            "source": "area_fallback",
            "sample_count": 0,
        }
    return {"seconds": 0, "source": "none", "sample_count": 0}


def _clamp_estimate(seconds: float) -> int:
    """Keep an estimate in a sane band — a bad area or one wild sample can't run away."""
    return int(max(_MIN_ESTIMATE_SECONDS, min(_MAX_ESTIMATE_SECONDS, round(seconds))))
