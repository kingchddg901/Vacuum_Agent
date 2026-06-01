"""Integration tests for services/errors.py + services/setup.py handlers.

Registered via the domain async_register_services (manager_with_services).

Coverage targets
----------------
[SVE-1] acknowledge_error: no tracker → tracker_not_loaded; with tracker → acked.
[SVE-2] get_recent_errors: no tracker → []; with tracker → errors list.
[SVS-1] setup_get_status returns a status dict.
[SVS-2] setup_get_map_rooms returns the managed room list.
[SVS-3] setup_save_rooms saves discovered rooms.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.const import (
    DATA_ERROR_TRACKER,
    DOMAIN,
    SERVICE_ACKNOWLEDGE_ERROR,
    SERVICE_GET_RECENT_ERRORS,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_GET_STATUS,
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
