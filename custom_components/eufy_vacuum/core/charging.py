"""Brand-agnostic charging / battery-level reads.

Framework-level helpers that read battery level and charging state from the
entities the adapter declares — no brand assumptions. Previously these lived in
``adapters/eufy/charging.py`` and were imported directly by ``core/manager.py``
and ``jobs/active_job.py``; that was the one hard framework→adapter coupling. The
logic is generic (it reads ``entities.battery`` / ``entities.charging`` from the
adapter registry), so it belongs here.

The only brand-specific values are the low-battery-return signal — the
``task_status`` string a brand reports when returning to charge, and the battery
threshold — which ``is_low_battery_return_state`` takes as explicit parameters
(the caller resolves them from the adapter's ``charging`` config block). The
function itself stays pure and brand-free.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config

# Generic sane default low-battery threshold (percent). A brand may override via
# charging.low_battery_threshold_percent. There is deliberately NO default brand
# task_status string — an unconfigured adapter falls back to the HA-standard
# "returning" vacuum-state + threshold path only.
_DEFAULT_LOW_BATTERY_THRESHOLD_PERCENT = 20


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely, treating sentinel strings as default."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_battery_level(hass: HomeAssistant, vacuum_entity_id: str) -> int:
    """Return current battery level from the adapter's battery entity, else the
    vacuum entity's ``battery_level`` attribute.

    Reads the entity declared in ``adapter_config.entities.battery``. Falls back
    to the standard HA ``battery_level`` attribute on the vacuum entity when the
    dedicated sensor is absent.
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

    Reads the charging binary sensor declared in
    ``adapter_config.entities.charging``. Returns False when absent, unavailable,
    or unknown — no substring fallback (substring fallbacks have known false
    negatives, e.g. post-job recharges, and violate the dedicated-upstream-signal
    principle).
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
    low_battery_return_status: str = "",
    threshold_percent: int = _DEFAULT_LOW_BATTERY_THRESHOLD_PERCENT,
) -> bool:
    """Return whether the robot is returning to dock due to low battery.

    Two signals, simplest first:

    - ``task_status`` equals the brand's low-battery-return string
      (``low_battery_return_status``, from the adapter's ``charging`` config) —
      upstream-authoritative, no threshold needed. Empty string disables this
      check (an adapter that doesn't declare it relies on the generic path below).
    - ``vacuum_state == "returning"`` (HA standard) **and**
      ``0 < battery <= threshold_percent`` — the generic returning state plus a
      battery gate so a user-initiated return_to_base with a full battery isn't
      mis-classified.
    """
    want = str(low_battery_return_status or "").strip().lower()
    if want and str(task_status or "").strip().lower() == want:
        return True
    if str(vacuum_state or "").strip().lower() != "returning":
        return False
    return 0 < current_battery <= int(threshold_percent)
