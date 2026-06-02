"""Brand-agnostic tests for the framework battery/charging functions.

Covers ``core/charging.py``:
  - ``_safe_int``  — sentinel-tolerant int coercion.
  - ``get_battery_level`` — sensor first, vacuum battery_level attr fallback.
  - ``is_charging`` — dedicated binary sensor only, no substring fallback.
  - ``is_low_battery_return_state`` — two-signal low-battery-return classifier.

``get_battery_level`` / ``is_charging`` read entity ids from the adapter
registry, so each test registers a minimal config. ``is_low_battery_return_state``
is pure and brand-free; the brand low-battery-return string and threshold are
passed explicitly (the caller resolves them from the adapter's ``charging``
config block).

Coverage targets
----------------
[CHG-1]  _safe_int: sentinels and bad input -> default; floats truncated.
[CHG-2]  battery: dedicated sensor wins.
[CHG-3]  battery: sensor missing/invalid -> vacuum battery_level attr.
[CHG-4]  battery: no sensor entity declared -> vacuum attr.
[CHG-5]  battery: nothing available -> 0.
[CHG-6]  charging: binary sensor "on" -> True, "off" -> False.
[CHG-7]  charging: no entity declared -> False (no fallback).
[CHG-8]  charging: entity unavailable/unknown -> False.
[CHG-9]  low-battery-return: configured task status -> True.
[CHG-10] low-battery-return: returning + battery at/under threshold -> True.
[CHG-11] low-battery-return: returning + healthy battery -> False.
[CHG-12] low-battery-return: not returning -> False.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.core import charging
from custom_components.eufy_vacuum.adapters.eufy.constants import (
    LOW_BATTERY_THRESHOLD_PERCENT,
)

_LOW_BATTERY_RETURN_STATUS = "returning to charge"


_VAC = "vacuum.alfred"
_BATTERY = "sensor.alfred_battery"
_CHARGING = "binary_sensor.alfred_charging"


@pytest.fixture(autouse=True)
def _isolate_registry():
    clear_registry()
    yield
    clear_registry()


def _register(entities: dict) -> None:
    register_adapter_config(
        _VAC,
        {
            "adapter_id": "eufy_test",
            "source": "code",
            "entities": entities,
            "dispatch": {
                "template": "eufy_room_clean",
                "service_domain": "vacuum",
                "service_name": "send_command",
            },
        },
    )


# --- _safe_int --------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0),
        ("", 0),
        ("unknown", 0),
        ("unavailable", 0),
        ("not-a-number", 0),
        ("55", 55),
        ("55.9", 55),  # float string truncated
        (42, 42),
        (42.7, 42),
    ],
)
def test_safe_int(value, expected):
    """[CHG-1]"""
    assert charging._safe_int(value) == expected


def test_safe_int_custom_default():
    """[CHG-1] custom default returned for sentinel."""
    assert charging._safe_int("unknown", -1) == -1


# --- get_battery_level ------------------------------------------------------


def test_battery_dedicated_sensor_wins(hass):
    """[CHG-2]"""
    _register({"battery": _BATTERY})
    hass.states.async_set(_BATTERY, "73")
    hass.states.async_set(_VAC, "cleaning", {"battery_level": 10})
    assert charging.get_battery_level(hass, _VAC) == 73


def test_battery_falls_back_to_vacuum_attr(hass):
    """[CHG-3] sensor present but invalid -> vacuum battery_level attr."""
    _register({"battery": _BATTERY})
    hass.states.async_set(_BATTERY, "unknown")
    hass.states.async_set(_VAC, "cleaning", {"battery_level": 64})
    assert charging.get_battery_level(hass, _VAC) == 64


def test_battery_declared_sensor_absent_uses_attr(hass):
    """[CHG-3] battery entity declared but its state object missing -> attr."""
    _register({"battery": _BATTERY})  # declared, but never set in hass
    hass.states.async_set(_VAC, "cleaning", {"battery_level": 51})
    assert charging.get_battery_level(hass, _VAC) == 51


def test_battery_no_sensor_declared_uses_attr(hass):
    """[CHG-4]"""
    _register({})  # no battery entity declared
    hass.states.async_set(_VAC, "cleaning", {"battery_level": 88})
    assert charging.get_battery_level(hass, _VAC) == 88


def test_battery_nothing_available_is_zero(hass):
    """[CHG-5] no sensor, no vacuum state -> 0."""
    _register({})
    assert charging.get_battery_level(hass, _VAC) == 0


# --- is_charging ------------------------------------------------------------


def test_charging_on(hass):
    """[CHG-6]"""
    _register({"charging": _CHARGING})
    hass.states.async_set(_CHARGING, "on")
    assert charging.is_charging(hass, _VAC) is True


def test_charging_off(hass):
    """[CHG-6]"""
    _register({"charging": _CHARGING})
    hass.states.async_set(_CHARGING, "off")
    assert charging.is_charging(hass, _VAC) is False


def test_charging_no_entity_declared(hass):
    """[CHG-7] no substring fallback — absent entity means False."""
    _register({})
    hass.states.async_set(_VAC, "docked", {"status": "charging"})
    assert charging.is_charging(hass, _VAC) is False


@pytest.mark.parametrize("bad", ["unavailable", "unknown"])
def test_charging_entity_not_binary(hass, bad):
    """[CHG-8]"""
    _register({"charging": _CHARGING})
    hass.states.async_set(_CHARGING, bad)
    assert charging.is_charging(hass, _VAC) is False


# --- is_low_battery_return_state --------------------------------------------


def test_low_battery_return_task_status():
    """[CHG-9] authoritative task status, no battery gate needed."""
    assert charging.is_low_battery_return_state(
        current_battery=95,
        vacuum_state="returning",
        task_status="Returning To Charge",
        low_battery_return_status=_LOW_BATTERY_RETURN_STATUS,
    ) is True


def test_low_battery_return_returning_under_threshold():
    """[CHG-10] generic returning + battery at the threshold."""
    assert charging.is_low_battery_return_state(
        current_battery=LOW_BATTERY_THRESHOLD_PERCENT,
        vacuum_state="returning",
        task_status="cleaning",
        low_battery_return_status=_LOW_BATTERY_RETURN_STATUS,
        threshold_percent=LOW_BATTERY_THRESHOLD_PERCENT,
    ) is True


def test_low_battery_return_returning_healthy_battery():
    """[CHG-11] user-initiated return on a full battery -> not low-battery."""
    assert charging.is_low_battery_return_state(
        current_battery=90,
        vacuum_state="returning",
        task_status=None,
        low_battery_return_status=_LOW_BATTERY_RETURN_STATUS,
    ) is False


def test_low_battery_return_not_returning():
    """[CHG-12]"""
    assert charging.is_low_battery_return_state(
        current_battery=5,
        vacuum_state="cleaning",
        task_status=None,
        low_battery_return_status=_LOW_BATTERY_RETURN_STATUS,
    ) is False


def test_low_battery_return_zero_battery_returning():
    """[CHG-12] battery 0 fails the 0 < battery gate (no reading)."""
    assert charging.is_low_battery_return_state(
        current_battery=0,
        vacuum_state="returning",
        task_status=None,
        low_battery_return_status=_LOW_BATTERY_RETURN_STATUS,
    ) is False


def test_low_battery_return_no_configured_status_uses_generic_path():
    """[CHG-9] empty low_battery_return_status disables the task-status check;
    only the generic returning+threshold path applies."""
    # task_status matches a brand string but no status configured -> ignored,
    # full battery on the generic path -> not low-battery.
    assert charging.is_low_battery_return_state(
        current_battery=95,
        vacuum_state="returning",
        task_status="returning to charge",
    ) is False
