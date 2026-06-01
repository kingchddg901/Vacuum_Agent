"""Phase 4 integration tests — rooms service handlers.

Coverage targets
----------------
[SR-1]  save_managed_rooms service persists room config.
[SR-2]  get_vacuum_maps service returns map list for a vacuum.
[SR-3]  update_room_fields service updates a field and returns ok.
[SR-4]  update_room_fields service returns error for unknown room.
[SR-5]  discover_rooms handler: success → discover + drift pass + save.
[SR-6]  handler exception wrapping: discover / save / update_room_fields.
[SR-7]  update_room_fields handler: not-updated → no save.

The discover_rooms handler + the error-wrapping branches run through the
module-level _handle_* coroutines with a mock manager (the real service path
can't easily force those failures).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.services.rooms import (
    _handle_discover_rooms,
    _handle_save_managed_rooms,
    _handle_update_room_fields,
)

from .conftest import seed_discovery, make_rooms, setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [SR-1] save_managed_rooms
# ---------------------------------------------------------------------------

async def test_save_managed_rooms_service_persists_rooms(hass, manager_with_services):
    """[SR-1] save_managed_rooms service writes rooms into manager data."""
    rooms = make_rooms(_MAP, 3)
    seed_discovery(manager_with_services, _VAC, _MAP, rooms)
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    await hass.services.async_call(
        DOMAIN,
        "save_managed_rooms",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )

    assert _VAC in manager_with_services.data.get("maps", {})
    assert _MAP in manager_with_services.data["maps"][_VAC]
    assert len(manager_with_services.data["maps"][_VAC][_MAP]["rooms"]) == 3


async def test_save_managed_rooms_service_with_filter(hass, manager_with_services):
    """[SR-1] save_managed_rooms service respects enabled_room_ids filter."""
    rooms = make_rooms(_MAP, 4)
    seed_discovery(manager_with_services, _VAC, _MAP, rooms)
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    await hass.services.async_call(
        DOMAIN,
        "save_managed_rooms",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "enabled_room_ids": [1, 3]},
        blocking=True,
    )

    stored = manager_with_services.data["maps"][_VAC][_MAP]["rooms"]
    assert set(stored.keys()) == {"1", "3"}


# ---------------------------------------------------------------------------
# [SR-2] get_vacuum_maps
# ---------------------------------------------------------------------------

async def test_get_vacuum_maps_service_returns_dict(hass, manager_with_services):
    """[SR-2] get_vacuum_maps service returns a response dict."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_vacuum_maps",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result


async def test_get_vacuum_maps_service_includes_saved_map(hass, manager_with_services):
    """[SR-2] get_vacuum_maps lists the map saved via save_managed_rooms."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_vacuum_maps",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    map_ids = [m.get("map_id") for m in result.get("maps", [])]
    assert _MAP in map_ids


# ---------------------------------------------------------------------------
# [SR-3] — [SR-4] update_room_fields
# ---------------------------------------------------------------------------

async def test_update_room_fields_service_updates_fan_speed(hass, manager_with_services):
    """[SR-3] update_room_fields service writes fan_speed to room config."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "update_room_fields",
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "room_id": 1,
            "fan_speed": "quiet",
        },
        blocking=True,
        return_response=True,
    )
    assert result.get("ok") is not False
    assert manager_with_services.data["maps"][_VAC][_MAP]["rooms"]["1"]["fan_speed"] == "quiet"


async def test_update_room_fields_service_updates_clean_passes(hass, manager_with_services):
    """[SR-3] update_room_fields service writes clean_passes to room config."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "update_room_fields",
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "room_id": 2,
            "clean_passes": 2,
        },
        blocking=True,
        return_response=True,
    )
    assert result.get("ok") is not False
    assert manager_with_services.data["maps"][_VAC][_MAP]["rooms"]["2"]["clean_passes"] == 2


async def test_update_room_fields_service_toggles_enabled(hass, manager_with_services):
    """[SR-3] update_room_fields service can toggle enabled to False."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    await hass.services.async_call(
        DOMAIN,
        "update_room_fields",
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "room_id": 2,
            "enabled": False,
        },
        blocking=True,
        return_response=True,
    )
    assert manager_with_services.data["maps"][_VAC][_MAP]["rooms"]["2"]["enabled"] is False


async def test_update_room_fields_service_unknown_room_returns_error(hass, manager_with_services):
    """[SR-4] update_room_fields service returns error payload for unknown room."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "update_room_fields",
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "room_id": 99,
            "fan_speed": "max",
        },
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is False
    assert result["error"] == "room_not_found"


# ---------------------------------------------------------------------------
# [SR-5] — [SR-7] handler-level: discover + error wrapping (mock manager)
# ---------------------------------------------------------------------------

class _Call:
    def __init__(self, data):
        self.data = data


@pytest.fixture
def rmock(hass):
    mgr = MagicMock()
    mgr.data = {}
    mgr.async_save = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr
    return hass, mgr


def _c(**extra):
    return _Call({"vacuum_entity_id": _VAC, "map_id": _MAP, **extra})


async def test_discover_handler_success(rmock):
    """[SR-5] discover delegates, runs the drift pass, and saves."""
    hass, mgr = rmock
    mgr.discover_rooms.return_value = {"room_count": 0}
    await _handle_discover_rooms(hass, _c())
    mgr.discover_rooms.assert_called_once()
    mgr.async_save.assert_awaited_once()


async def test_discover_handler_raises(rmock):
    """[SR-6]"""
    hass, mgr = rmock
    mgr.discover_rooms.side_effect = RuntimeError("boom")
    with pytest.raises(HomeAssistantError, match="Failed to discover rooms"):
        await _handle_discover_rooms(hass, _c())


async def test_save_handler_raises(rmock):
    """[SR-6]"""
    hass, mgr = rmock
    mgr.save_managed_rooms.side_effect = ValueError("bad")
    with pytest.raises(HomeAssistantError, match="Failed to save managed rooms"):
        await _handle_save_managed_rooms(hass, _c())


async def test_update_handler_raises_and_noop(rmock):
    """[SR-6] + [SR-7] error wrap, and no save when nothing updated."""
    hass, mgr = rmock
    mgr.update_room_fields.return_value = {"updated": False}
    await _handle_update_room_fields(hass, _c(room_id=1))
    mgr.async_save.assert_not_awaited()
    mgr.update_room_fields.side_effect = ValueError("bad")
    with pytest.raises(HomeAssistantError, match="Failed to update room fields"):
        await _handle_update_room_fields(hass, _c(room_id=1))
