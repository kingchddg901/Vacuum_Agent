"""Phase 4 integration tests — snapshot service handlers.

Coverage targets
----------------
[SS-1]  get_pause_timeout_settings returns default settings.
[SS-2]  set_pause_timeout_settings persists and returns updated value.
[SS-3]  get_upkeep_snapshot returns a response dict.

Note: get_dashboard_snapshot is excluded — it calls hass.bus.async_fire
internally (via _maybe_roll_current_room_by_timing) and requires live
entity state that is not available in isolated tests.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


# ---------------------------------------------------------------------------
# [SS-1] get_pause_timeout_settings
# ---------------------------------------------------------------------------

async def test_get_pause_timeout_settings_service_returns_default(hass, manager_with_services):
    """[SS-1] Returns vacuum_entity_id and a default timeout value."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_pause_timeout_settings",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert "pause_timeout_minutes_default" in result


async def test_get_pause_timeout_settings_service_creates_vacuum_record(hass, manager_with_services):
    """[SS-1] Calling for an unseen vacuum does not raise."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_pause_timeout_settings",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [SS-2] set_pause_timeout_settings
# ---------------------------------------------------------------------------

async def test_set_pause_timeout_settings_service_persists_value(hass, manager_with_services):
    """[SS-2] Saved timeout is reflected in data after set service call."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 30},
        blocking=True,
        return_response=True,
    )
    stored = manager_with_services.data["vacuums"][_VAC]["pause_timeout_minutes_default"]
    assert stored == 30


async def test_set_pause_timeout_settings_service_returns_updated(hass, manager_with_services):
    """[SS-2] Service returns updated=True with the persisted value."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 15},
        blocking=True,
        return_response=True,
    )
    assert result["updated"] is True
    assert result["pause_timeout_minutes_default"] == 15
    assert result["vacuum_entity_id"] == _VAC


async def test_set_pause_timeout_settings_service_zero_allowed(hass, manager_with_services):
    """[SS-2] Zero is a valid pause_timeout_minutes_default (disables timeout)."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 0},
        blocking=True,
        return_response=True,
    )
    assert result["updated"] is True
    assert result["pause_timeout_minutes_default"] == 0


# ---------------------------------------------------------------------------
# [SS-3] get_upkeep_snapshot
# ---------------------------------------------------------------------------

async def test_get_upkeep_snapshot_service_returns_dict(hass, manager_with_services):
    """[SS-3] get_upkeep_snapshot returns a response dict."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_upkeep_snapshot",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result
