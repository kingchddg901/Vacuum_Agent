"""Phase 4 integration tests — rooms service handlers.

Coverage targets
----------------
[SR-1]  save_managed_rooms service persists room config.
[SR-2]  get_vacuum_maps service returns map list for a vacuum.
[SR-3]  update_room_fields service updates a field and returns ok.
[SR-4]  update_room_fields service returns error for unknown room.

Note: discover_rooms service is excluded — it calls adapter entities and
run_discovery_pass which require a real HA entity setup.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN

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
