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
