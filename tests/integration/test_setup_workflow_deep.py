"""Phase 8 integration tests — setup/workflow.py deep paths.

Coverage targets
----------------
[WFD-1]  import_active_map blocked when vacuum not yet managed.
[WFD-2]  import_active_map blocked when no active map detected.
[WFD-3]  import_active_map already_done when map has rooms.
[WFD-4]  import_active_map blocked when discover_rooms_for_vacuum returns empty.
[WFD-5]  import_active_map success — rooms saved into manager.data.
[WFD-6]  add_vacuum panel ValueError is silently caught (already-registered path).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.setup.workflow import add_vacuum, import_active_map

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"

_ACTIVE_MAP_ENTITY = "sensor.alfred_active_map"

_ADAPTER_WITH_MAP = {
    "adapter_id": "test",
    "source": "test",
    "entities": {"active_map": _ACTIVE_MAP_ENTITY},
}


# ---------------------------------------------------------------------------
# [WFD-1] import_active_map — vacuum not managed
# ---------------------------------------------------------------------------

async def test_import_active_map_not_managed_returns_blocked(hass, manager):
    """[WFD-1] import_active_map returns blocked when vacuum has not been added yet."""
    result = await import_active_map(hass, vacuum_entity_id=_VAC)
    assert result["status"] == "blocked"
    assert "add_vacuum" in result["next_actions"]


# ---------------------------------------------------------------------------
# [WFD-2] import_active_map — no active map
# ---------------------------------------------------------------------------

async def test_import_active_map_no_map_entity_returns_blocked(hass, manager):
    """[WFD-2] import_active_map returns blocked when no active map is detected."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # No adapter registered and no active_map entity — get_active_map_id returns None.
    result = await import_active_map(hass, vacuum_entity_id=_VAC)
    assert result["status"] == "blocked"
    assert result["data"]["vacuum_entity_id"] == _VAC


# ---------------------------------------------------------------------------
# [WFD-3] import_active_map — already imported (rooms exist)
# ---------------------------------------------------------------------------

async def test_import_active_map_already_done_when_rooms_exist(hass, manager):
    """[WFD-3] import_active_map returns already_done when the map already has rooms."""
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _ADAPTER_WITH_MAP)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, _MAP)
    await hass.async_block_till_done()

    result = await import_active_map(hass, vacuum_entity_id=_VAC)
    assert result["status"] == "already_done"
    assert result["data"]["map_id"] == _MAP


# ---------------------------------------------------------------------------
# [WFD-4] import_active_map — empty room discovery
# ---------------------------------------------------------------------------

async def test_import_active_map_blocked_when_no_rooms_discovered(hass, manager):
    """[WFD-4] import_active_map returns blocked when discover_rooms_for_vacuum returns []."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_MAP)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, _MAP)
    await hass.async_block_till_done()

    with patch(
        "custom_components.eufy_vacuum.setup.workflow.discover_rooms_for_vacuum",
        return_value=[],
    ):
        result = await import_active_map(hass, vacuum_entity_id=_VAC)

    assert result["status"] == "blocked"
    assert result["data"]["map_id"] == _MAP


# ---------------------------------------------------------------------------
# [WFD-5] import_active_map success
# ---------------------------------------------------------------------------

async def test_import_active_map_success_saves_rooms(hass, manager):
    """[WFD-5] import_active_map seeds discovery cache and saves rooms into manager.data."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_MAP)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, _MAP)
    await hass.async_block_till_done()

    _rooms = [
        {"room_id": 1, "map_id": _MAP, "name": "Living Room"},
        {"room_id": 2, "map_id": _MAP, "name": "Bedroom"},
    ]

    with patch(
        "custom_components.eufy_vacuum.setup.workflow.discover_rooms_for_vacuum",
        return_value=_rooms,
    ):
        result = await import_active_map(hass, vacuum_entity_id=_VAC)

    assert result["status"] == "success"
    assert result["data"]["room_count"] == 2
    assert result["data"]["map_id"] == _MAP
    # Verify rooms were saved into manager.data
    rooms = manager.data.get("maps", {}).get(_VAC, {}).get(_MAP, {}).get("rooms", {})
    assert len(rooms) == 2


async def test_import_active_map_success_populates_discovery_cache(hass, manager):
    """[WFD-5] import_active_map writes to manager.data['discovery'] for downstream use."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_MAP)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, _MAP)
    await hass.async_block_till_done()

    _rooms = [{"room_id": 1, "map_id": _MAP, "name": "Kitchen"}]

    with patch(
        "custom_components.eufy_vacuum.setup.workflow.discover_rooms_for_vacuum",
        return_value=_rooms,
    ):
        await import_active_map(hass, vacuum_entity_id=_VAC)

    discovery = manager.data.get("discovery", {}).get(_VAC, {}).get(_MAP)
    assert discovery is not None
    assert discovery["room_count"] == 1


# ---------------------------------------------------------------------------
# [WFD-6] add_vacuum — panel already-registered ValueError silently caught
# ---------------------------------------------------------------------------

async def test_add_vacuum_panel_already_registered_does_not_raise(hass, manager):
    """[WFD-6] ValueError from async_register_panel (duplicate panel) is swallowed."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.panel_custom.async_register_panel",
        new_callable=AsyncMock,
        side_effect=ValueError("already registered"),
    ):
        result = await add_vacuum(hass, vacuum_entity_id=_VAC)

    assert result["status"] == "success"
    assert _VAC in manager.data.get("vacuums", {})
