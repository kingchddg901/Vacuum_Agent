"""Brand-specific tests for the Eufy lifecycle signal functions.

Covers ``adapters/eufy/lifecycle.py`` — the three functions that translate
Eufy/robovac_mqtt entity naming and state vocabulary into the signals the
framework lifecycle listener consumes. The return shapes are a contract the
listener depends on, so these assert them exactly.

Coverage targets
----------------
[LC-1]  _get_lifecycle_watch_entities returns the 5 watched entity ids.
[LC-2]  _get_entity_state_lower: missing entity -> "".
[LC-3]  _get_entity_state_lower: normalizes whitespace + case.
[LC-4]  _active_cleaning_target_cleared: sentinels -> True, real -> False.
[LC-5]  _completed_finalize_signals: full dict shape + derived booleans.
[LC-6]  _completed_finalize_signals: completed/cleared/docked all True.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.eufy import lifecycle


_VAC = "vacuum.alfred"


# --- _get_lifecycle_watch_entities ------------------------------------------


def test_watch_entities_list():
    """[LC-1]"""
    entities = lifecycle._get_lifecycle_watch_entities(_VAC)
    assert entities == [
        "vacuum.alfred",
        "sensor.alfred_task_status",
        "sensor.alfred_dock_status",
        "sensor.alfred_active_cleaning_target",
        "sensor.alfred_active_map",
    ]


# --- _get_entity_state_lower ------------------------------------------------


def test_entity_state_lower_missing(hass):
    """[LC-2]"""
    assert lifecycle._get_entity_state_lower(hass, "sensor.nope") == ""


def test_entity_state_lower_normalizes(hass):
    """[LC-3]"""
    hass.states.async_set("sensor.alfred_task_status", "  Cleaning  ")
    assert (
        lifecycle._get_entity_state_lower(hass, "sensor.alfred_task_status")
        == "cleaning"
    )


# --- _active_cleaning_target_cleared ----------------------------------------


@pytest.mark.parametrize("cleared", ["", "unknown", "unavailable", "none", "null"])
def test_target_cleared_sentinels(cleared):
    """[LC-4] cleared sentinels"""
    assert lifecycle._active_cleaning_target_cleared(cleared) is True


@pytest.mark.parametrize("active", ["kitchen", "room_3", "1"])
def test_target_not_cleared_for_real_values(active):
    """[LC-4] real target values"""
    assert lifecycle._active_cleaning_target_cleared(active) is False


# --- _completed_finalize_signals --------------------------------------------


def test_finalize_signals_mid_job(hass):
    """[LC-5] an in-progress job: nothing completed/cleared/docked."""
    hass.states.async_set(_VAC, "cleaning")
    hass.states.async_set("sensor.alfred_task_status", "cleaning")
    hass.states.async_set("sensor.alfred_dock_status", "idle")
    hass.states.async_set("sensor.alfred_active_cleaning_target", "kitchen")

    signals = lifecycle._completed_finalize_signals(hass, _VAC)
    assert set(signals) == {
        "vacuum_state",
        "task_status",
        "dock_status",
        "active_target",
        "task_completed",
        "target_cleared",
        "vacuum_docked",
    }
    assert signals["vacuum_state"] == "cleaning"
    assert signals["task_completed"] is False
    assert signals["target_cleared"] is False
    assert signals["vacuum_docked"] is False


def test_finalize_signals_completed_docked(hass):
    """[LC-6] a finished job docked with cleared target -> all three True."""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_task_status", "completed")
    hass.states.async_set("sensor.alfred_dock_status", "charging")
    hass.states.async_set("sensor.alfred_active_cleaning_target", "unknown")

    signals = lifecycle._completed_finalize_signals(hass, _VAC)
    assert signals["task_completed"] is True
    assert signals["target_cleared"] is True
    assert signals["vacuum_docked"] is True
