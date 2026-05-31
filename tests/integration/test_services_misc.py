"""Phase 4 integration tests — miscellaneous service handlers.

Coverage targets
----------------
[SM-1]  acknowledge_error returns graceful payload when no error tracker is loaded.
[SM-2]  get_recent_errors returns graceful payload when no error tracker is loaded.
[SM-3]  set_maintenance_interval persists the interval and returns saved=True.
[SM-4]  get_vacuum_capabilities returns a response dict.
[SM-5]  get_adapter_config returns config=None for a vacuum with no adapter registered.
[SM-6]  observe_entity_states returns observations for each requested entity_id.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


# ---------------------------------------------------------------------------
# [SM-1] acknowledge_error — no tracker
# ---------------------------------------------------------------------------

async def test_acknowledge_error_no_tracker_graceful(hass, manager_with_services):
    """[SM-1] Returns acknowledged=False with reason='tracker_not_loaded' when no tracker."""
    result = await hass.services.async_call(
        DOMAIN,
        "acknowledge_error",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["acknowledged"] is False
    assert result["reason"] == "tracker_not_loaded"


async def test_acknowledge_error_no_tracker_scope_variant(hass, manager_with_services):
    """[SM-1] Explicit scope is accepted; graceful response still returned without tracker."""
    result = await hass.services.async_call(
        DOMAIN,
        "acknowledge_error",
        {"vacuum_entity_id": _VAC, "scope": "active_run"},
        blocking=True,
        return_response=True,
    )
    assert result["acknowledged"] is False
    assert result["reason"] == "tracker_not_loaded"


# ---------------------------------------------------------------------------
# [SM-2] get_recent_errors — no tracker
# ---------------------------------------------------------------------------

async def test_get_recent_errors_no_tracker_graceful(hass, manager_with_services):
    """[SM-2] Returns empty errors list with reason='tracker_not_loaded' when no tracker."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_recent_errors",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["errors"] == []
    assert result["reason"] == "tracker_not_loaded"


async def test_get_recent_errors_no_tracker_with_limit(hass, manager_with_services):
    """[SM-2] limit parameter is accepted; graceful response returned without tracker."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_recent_errors",
        {"vacuum_entity_id": _VAC, "limit": 5},
        blocking=True,
        return_response=True,
    )
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# [SM-3] set_maintenance_interval
# ---------------------------------------------------------------------------

async def test_set_maintenance_interval_service_persists(hass, manager_with_services):
    """[SM-3] set_maintenance_interval writes interval into manager data."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_maintenance_interval",
        {
            "vacuum_entity_id": _VAC,
            "component": "filter",
            "interval_hours": 100.0,
        },
        blocking=True,
        return_response=True,
    )
    assert result["saved"] is True
    assert result["component"] == "filter"
    assert result["interval_hours"] == 100.0

    stored = (
        manager_with_services.data
        .get("maintenance", {})
        .get(_VAC, {})
        .get("filter", {})
        .get("interval_hours")
    )
    assert stored == 100.0


async def test_set_maintenance_interval_service_decimal_rounded(hass, manager_with_services):
    """[SM-3] interval_hours is rounded to one decimal place."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_maintenance_interval",
        {
            "vacuum_entity_id": _VAC,
            "component": "brush",
            "interval_hours": 99.567,
        },
        blocking=True,
        return_response=True,
    )
    assert result["interval_hours"] == 99.6


# ---------------------------------------------------------------------------
# [SM-4] get_vacuum_capabilities
# ---------------------------------------------------------------------------

async def test_get_vacuum_capabilities_service_returns_dict(hass, manager_with_services):
    """[SM-4] get_vacuum_capabilities returns a response dict."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_vacuum_capabilities",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result


async def test_get_vacuum_capabilities_service_with_model_hint(hass, manager_with_services):
    """[SM-4] detected_model hint is accepted without error."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_vacuum_capabilities",
        {"vacuum_entity_id": _VAC, "detected_model": "T2351"},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [SM-5] get_adapter_config
# ---------------------------------------------------------------------------

async def test_get_adapter_config_service_no_adapter_registered(hass, manager_with_services):
    """[SM-5] Returns config=None when no adapter is registered for the vacuum."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["config"] is None


# ---------------------------------------------------------------------------
# [SM-6] observe_entity_states
# ---------------------------------------------------------------------------

async def test_observe_entity_states_service_unknown_entities(hass, manager_with_services):
    """[SM-6] Unknown entity_ids return state=None observations without raising."""
    result = await hass.services.async_call(
        DOMAIN,
        "observe_entity_states",
        {"entity_ids": ["sensor.nonexistent_1", "sensor.nonexistent_2"]},
        blocking=True,
        return_response=True,
    )
    assert result["entity_count"] == 2
    for obs in result["observations"]:
        assert obs["state"] is None
        assert obs["attributes"] == {}


async def test_observe_entity_states_service_empty_list(hass, manager_with_services):
    """[SM-6] Empty entity_ids list returns zero observations."""
    result = await hass.services.async_call(
        DOMAIN,
        "observe_entity_states",
        {"entity_ids": []},
        blocking=True,
        return_response=True,
    )
    assert result["entity_count"] == 0
    assert result["observations"] == []
