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


def _room_profile_key(room: dict[str, Any]) -> str:
    """Return a stable per-room settings signature used for stats matching."""
    return "::".join(
        [
            str(room.get("slug", "")).strip().lower(),
            str(room.get("selected_profile_name", room.get("resolved_profile_name", ""))).strip().lower(),
            str(room.get("clean_mode", "")).strip().lower(),
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
        f"{str(effective_mode or '').strip().lower()}::"
        f"{_safe_int(clean_times, 1)}::"
        f"{'1' if _safe_bool(is_carpet, False) else '0'}::"
        f"{str(clean_intensity or 'standard').strip().lower()}::"
        f"{'1' if _safe_bool(edge_mopping, False) else '0'}"
    )
