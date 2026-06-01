"""Phase 9 integration tests — services/maintenance.py reset_maintenance
and services/snapshots.py get_dashboard_snapshot.

Coverage targets
----------------
[MR-1]  reset_maintenance raises ServiceValidationError for unknown component (no_source_entity).
[MR-2]  reset_maintenance returns reset=False when source entity state is unavailable.
[MR-3]  reset_maintenance returns reset=True when source entity has usage_hours attribute.
[DS-1]  get_dashboard_snapshot returns a dict with vacuum_entity_id.
[DS-2]  get_dashboard_snapshot includes job_progress, lifecycle, start_status keys.
"""

from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"
_SOURCE_ENTITY = "sensor.alfred_main_brush_remaining"


def _seed_capabilities(manager, vacuum_entity_id: str, source_entity: str) -> None:
    """Seed the capabilities cache so maintenance_sources is populated."""
    manager.data.setdefault("capabilities", {})[vacuum_entity_id] = {
        "maintenance_sources": {"main_brush": source_entity},
        "supports_mop_features": False,
        "supports_water_control": False,
    }


# ---------------------------------------------------------------------------
# [MR-1] reset_maintenance — no source entity
# ---------------------------------------------------------------------------

async def test_reset_maintenance_raises_for_unknown_component(hass, manager_with_services):
    """[MR-1] reset_maintenance raises ServiceValidationError when component has no source entity."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "reset_maintenance",
            {"vacuum_entity_id": _VAC, "component": "nonexistent_component"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [MR-2] reset_maintenance — source entity state unavailable
# ---------------------------------------------------------------------------

async def test_reset_maintenance_returns_false_when_entity_state_absent(hass, manager_with_services):
    """[MR-2] reset_maintenance returns reset=False when source entity has no HA state."""
    # Seed capabilities so the component has a source entity, but don't set the entity state.
    _seed_capabilities(manager_with_services, _VAC, _SOURCE_ENTITY)

    result = await hass.services.async_call(
        DOMAIN,
        "reset_maintenance",
        {"vacuum_entity_id": _VAC, "component": "main_brush"},
        blocking=True,
        return_response=True,
    )
    assert result["reset"] is False
    assert result["reason"] == "source_unavailable"


# ---------------------------------------------------------------------------
# [MR-3] reset_maintenance — success
# ---------------------------------------------------------------------------

async def test_reset_maintenance_success_when_entity_has_usage_hours(hass, manager_with_services):
    """[MR-3] reset_maintenance returns reset=True when source entity has usage_hours."""
    _seed_capabilities(manager_with_services, _VAC, _SOURCE_ENTITY)
    hass.states.async_set(_SOURCE_ENTITY, "ok", {"usage_hours": 150})
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN,
        "reset_maintenance",
        {"vacuum_entity_id": _VAC, "component": "main_brush"},
        blocking=True,
        return_response=True,
    )
    assert result["reset"] is True
    assert result["component"] == "main_brush"


# ---------------------------------------------------------------------------
# [DS-1] / [DS-2] get_dashboard_snapshot
# ---------------------------------------------------------------------------

async def test_get_dashboard_snapshot_returns_dict(hass, manager_with_services):
    """[DS-1] get_dashboard_snapshot returns a dict with vacuum_entity_id."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_dashboard_snapshot",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert result.get("vacuum_entity_id") == _VAC


async def test_get_dashboard_snapshot_includes_required_keys(hass, manager_with_services):
    """[DS-2] get_dashboard_snapshot includes job_progress, lifecycle, start_status."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_dashboard_snapshot",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert "job_progress" in result
    assert "lifecycle" in result
    assert "start_status" in result
    assert "job_control" in result
    assert "upkeep" in result


# ---------------------------------------------------------------------------
# [MR-4/5] handler error-wrapping (HA Silver action-exception contract)
# ---------------------------------------------------------------------------

async def test_reset_maintenance_wraps_manager_error(hass, manager_with_services, monkeypatch):
    """[MR-4] a manager failure in reset surfaces as HomeAssistantError."""
    def _boom(**kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(manager_with_services, "reset_maintenance", _boom)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "reset_maintenance",
            {"vacuum_entity_id": _VAC, "component": "main_brush"},
            blocking=True, return_response=True)


async def test_set_maintenance_interval_wraps_save_error(hass, manager_with_services, monkeypatch):
    """[MR-5] a failed async_save while persisting an interval → HomeAssistantError."""
    async def _boom():
        raise RuntimeError("disk full")
    monkeypatch.setattr(manager_with_services, "async_save", _boom)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "set_maintenance_interval",
            {"vacuum_entity_id": _VAC, "component": "main_brush", "interval_hours": 150},
            blocking=True, return_response=True)
