"""Integration tests for services/errors.py + services/setup.py handlers.

Registered via the domain async_register_services (manager_with_services).

Coverage targets
----------------
[SVE-1] acknowledge_error: no tracker → tracker_not_loaded; with tracker → acked.
[SVE-2] get_recent_errors: no tracker → []; with tracker → errors list.
[SVS-1] setup_get_status returns a status dict.
[SVS-2] setup_get_map_rooms returns the managed room list.
[SVS-3] setup_save_rooms saves discovered rooms.
[SVS-4] setup_add_vacuum records the vacuum + stamps the setup step.
[SVS-5] setup_delete_map removes a map given a confirmation token.
[SVS-6] setup_reject_rooms strips rooms + reports the result.
[SVS-7] setup_force_remove_room bumps the missing-pass counter.
[SVS-8] setup_import_active_map discovers + saves the active map.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import (
    DATA_ERROR_TRACKER,
    DOMAIN,
    SERVICE_ACKNOWLEDGE_ERROR,
    SERVICE_GET_RECENT_ERRORS,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_SETUP_FORCE_REMOVE_ROOM,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_REJECT_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
)
from .conftest import seed_discovery, make_rooms, setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

async def test_acknowledge_error(hass, manager_with_services):
    """[SVE-1]"""
    # no tracker loaded
    result = await _call(hass, SERVICE_ACKNOWLEDGE_ERROR, {"vacuum_entity_id": _VAC})
    assert result["acknowledged"] is False and result["reason"] == "tracker_not_loaded"
    # tracker present
    tracker = MagicMock()
    tracker.acknowledge.return_value = True
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = tracker
    result = await _call(hass, SERVICE_ACKNOWLEDGE_ERROR,
                         {"vacuum_entity_id": _VAC, "scope": "both"})
    assert result["acknowledged"] is True
    tracker.acknowledge.assert_called_once_with(_VAC, scope="both")


async def test_get_recent_errors(hass, manager_with_services):
    """[SVE-2]"""
    result = await _call(hass, SERVICE_GET_RECENT_ERRORS, {"vacuum_entity_id": _VAC})
    assert result["errors"] == [] and result["reason"] == "tracker_not_loaded"

    tracker = MagicMock()
    tracker.recent_errors.return_value = [{"message": "E1"}, {"message": "E2"}]
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = tracker
    result = await _call(hass, SERVICE_GET_RECENT_ERRORS,
                         {"vacuum_entity_id": _VAC, "limit": 5})
    assert result["count"] == 2
    tracker.recent_errors.assert_called_once_with(_VAC, limit=5)


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

async def test_setup_get_status(hass, manager_with_services):
    """[SVS-1]"""
    result = await _call(hass, SERVICE_SETUP_GET_STATUS, {})
    assert isinstance(result, dict)


async def test_setup_get_map_rooms(hass, manager_with_services):
    """[SVS-2]"""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await _call(hass, SERVICE_SETUP_GET_MAP_ROOMS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert len(result["rooms"]) == 2
    assert result["rooms"][0]["room_id"] == 1


async def test_setup_save_rooms(hass, manager_with_services):
    """[SVS-3]"""
    seed_discovery(manager_with_services, _VAC, _MAP, make_rooms(_MAP, 3))
    result = await _call(hass, SERVICE_SETUP_SAVE_ROOMS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert result["status"] == "success"
    assert result["room_count"] == 3


# ---------------------------------------------------------------------------
# setup write-path service handlers (add / delete / reject / force-remove)
# ---------------------------------------------------------------------------

@pytest.fixture
def _no_panel(monkeypatch):
    async def _fake(*a, **k):
        return None
    import homeassistant.components.panel_custom as panel_custom
    monkeypatch.setattr(panel_custom, "async_register_panel", _fake)


async def test_setup_add_vacuum(hass, manager_with_services, _no_panel):
    """[SVS-4] add_vacuum service records the vacuum + stamps the setup step."""
    hass.states.async_set(_VAC, "docked")
    result = await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    assert result["status"] == "success"
    assert _VAC in manager_with_services.data.get("vacuums", {})
    steps = manager_with_services.data["setup_progress"][_VAC]["completed_steps"]
    assert "add_vacuum" in steps


async def test_setup_import_active_map(hass, manager_with_services, _no_panel):
    """[SVS-8] import_active_map service discovers + saves the active map."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_active_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity", "room_list_attribute": "segments",
            "room_id_key": "id", "room_name_key": "name"},
    })
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Bath"}]})
    await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    hass.states.async_set("sensor.alfred_active_map", "svsimp")
    result = await _call(hass, "setup_import_active_map", {"vacuum_entity_id": _VAC})
    assert result["status"] == "success"
    assert result["data"]["room_count"] == 2


async def test_setup_delete_map(hass, manager_with_services):
    """[SVS-5] delete_map service removes a map given a confirmation token."""
    setup_map(manager_with_services, _VAC, "svsdel", count=2)
    result = await _call(hass, SERVICE_SETUP_DELETE_MAP,
                         {"vacuum_entity_id": _VAC, "map_id": "svsdel",
                          "confirmation_token": "yes"})
    assert result["status"] == "success"
    assert "svsdel" not in manager_with_services.data.get("maps", {}).get(_VAC, {})


async def test_setup_reject_rooms(hass, manager_with_services):
    """[SVS-6] reject_rooms service strips rooms + reports the result."""
    setup_map(manager_with_services, _VAC, "svsrej", count=3)
    result = await _call(hass, SERVICE_SETUP_REJECT_ROOMS,
                         {"vacuum_entity_id": _VAC, "room_ids": [1, 2]})
    assert result["status"] == "success"
    assert set(result["rejected"]) == {1, 2}


async def test_setup_force_remove_room(hass, manager_with_services):
    """[SVS-7] force_remove_room service bumps the missing-pass counter."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await _call(hass, SERVICE_SETUP_FORCE_REMOVE_ROOM,
                         {"vacuum_entity_id": _VAC, "room_id": 7})
    assert result["status"] == "success"
    assert result["room_id"] == 7
