"""
Battery and charging state functions for the eufy_vacuum framework.

Reads entity IDs from the adapter registry — no Eufy-specific naming.
A port to a different brand registers its own entity IDs under the same
adapter config keys and these functions work unchanged.

get_battery_level()           — returns current battery percent.
is_charging()                 — returns True if the vacuum is charging.
is_low_battery_return_state() — returns True if returning due to low battery.

Return shapes:
    get_battery_level()           -> int   (0-100)
    is_charging()                 -> bool
    is_low_battery_return_state() -> bool
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..registry import get_adapter_config
from .constants import LOW_BATTERY_THRESHOLD_PERCENT


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely, treating sentinel strings as default."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_battery_level(hass: HomeAssistant, vacuum_entity_id: str) -> int:
    """Return current battery level from sensor first, then vacuum entity.

    Reads the battery entity declared in adapter_config.entities.battery.
    Falls back to the standard HA battery_level attribute on the vacuum
    entity when the dedicated sensor is absent.
    """
    battery_entity = (
        (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("battery")
    )
    if battery_entity:
        battery_sensor = hass.states.get(battery_entity)
        if battery_sensor is not None:
            battery_level = _safe_int(battery_sensor.state, -1)
            if battery_level >= 0:
                return battery_level

    vacuum_state = hass.states.get(vacuum_entity_id)
    if vacuum_state is None:
        return 0

    return _safe_int(vacuum_state.attributes.get("battery_level"), 0)


def is_charging(hass: HomeAssistant, vacuum_entity_id: str) -> bool:
    """Return True if the vacuum is currently charging.

    Reads the charging binary sensor declared in adapter_config.entities.charging.
    Returns False when the entity is absent, unavailable, or unknown — no
    substring fallback. Substring-based fallbacks have known false negatives
    (post-job recharges in particular) and violate the principle of using
    dedicated upstream signals over inferred state.
    """
    charging_entity = (
        (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("charging")
    )
    if not charging_entity:
        return False

    bs = hass.states.get(charging_entity)
    if bs is None or bs.state not in ("on", "off"):
        return False

    return bs.state == "on"


def is_low_battery_return_state(
    *,
    current_battery: int,
    vacuum_state: str | None,
    task_status: str | None,
) -> bool:
    """Return whether the robot is returning to dock due to low battery.

    Two signals, simplest first:

    - ``task_status == "returning to charge"`` — upstream-authoritative;
      the string is specific to low-battery return, no battery threshold
      needed.
    - ``vacuum_state == "returning"`` (HA standard) **and**
      ``0 < battery <= LOW_BATTERY_THRESHOLD_PERCENT`` — the generic
      returning state plus a battery gate so user-initiated return_to_base
      with a full battery isn't mis-classified.
    """
    if str(task_status or "").strip().lower() == "returning to charge":
        return True
    if str(vacuum_state or "").strip().lower() != "returning":
        return False
    return 0 < current_battery <= LOW_BATTERY_THRESHOLD_PERCENT
