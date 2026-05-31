"""Phase 6 integration tests — setup workflow (add_vacuum, import_active_map).

Coverage targets
----------------
[SW-1]  add_vacuum returns blocked when entity is absent from state machine.
[SW-2]  add_vacuum returns success when entity is present.
[SW-3]  add_vacuum success adds vacuum to manager.data.
[SW-4]  add_vacuum returns already_done when vacuum is already managed.
[SW-5]  add_vacuum returns error when manager is absent.
[SW-6]  import_active_map returns blocked when vacuum is not managed.
[SW-7]  import_active_map returns blocked when no active map sensor is present.
[SW-8]  import_active_map returns already_done when map is already imported.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.setup.workflow import add_vacuum, import_active_map

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [SW-1] — [SW-4] add_vacuum
# ---------------------------------------------------------------------------

async def test_add_vacuum_entity_absent_returns_blocked(hass, manager):
    """[SW-1] add_vacuum returns status=blocked when entity not in state machine."""
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "blocked"
    assert _VAC in result["data"].get("vacuum_entity_id", "")


async def test_add_vacuum_entity_present_returns_success(hass, manager):
    """[SW-2] add_vacuum returns status=success when entity exists in HA."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "success"


async def test_add_vacuum_success_writes_vacuum_record(hass, manager):
    """[SW-3] add_vacuum success registers the vacuum in manager.data."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    await add_vacuum(hass, _VAC)
    assert _VAC in manager.data.get("vacuums", {})


async def test_add_vacuum_already_managed_returns_already_done(hass, manager):
    """[SW-4] add_vacuum returns status=already_done when vacuum is already tracked."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "already_done"
    assert "import_active_map" in result.get("next_actions", [])


async def test_add_vacuum_no_manager_returns_error(hass):
    """[SW-5] add_vacuum returns status=error when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    # DATA_RUNTIME deliberately not set
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# [SW-6] — [SW-8] import_active_map
# ---------------------------------------------------------------------------

async def test_import_active_map_unmanaged_returns_blocked(hass, manager):
    """[SW-6] import_active_map returns blocked when vacuum is not yet managed."""
    result = await import_active_map(hass, _VAC)
    assert result["status"] == "blocked"
    assert "next_actions" in result
    assert "add_vacuum" in result["next_actions"]


async def test_import_active_map_no_map_sensor_returns_blocked(hass, manager):
    """[SW-7] import_active_map returns blocked when no active_map entity is declared."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # No adapter with active_map entity → get_active_map_id returns None
    result = await import_active_map(hass, _VAC)
    assert result["status"] == "blocked"


async def test_import_active_map_already_imported_returns_already_done(hass, manager):
    """[SW-8] import_active_map returns already_done when map has rooms."""
    setup_map(manager, _VAC, _MAP, count=3)
    # Simulate active_map entity so get_active_map_id resolves to _MAP
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        "source": "test",
        "entities": {"active_map": "sensor.alfred_active_map"},
    })
    hass.states.async_set("sensor.alfred_active_map", _MAP)
    await hass.async_block_till_done()

    result = await import_active_map(hass, _VAC)
    assert result["status"] == "already_done"
    assert result["data"]["map_id"] == _MAP
    assert result["data"]["room_count"] == 3
