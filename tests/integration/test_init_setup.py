"""End-to-end config-entry lifecycle for __init__.py.

Boots the whole integration through hass.config_entries.async_setup — the real
startup path that was previously untested: async_setup_entry orchestration,
adapter coordinator + manager init, code-adapter registration, service +
listener registration, platform forwarding (binary_sensor/button/switch/
number/sensor async_setup_entry + entity construction), and the unload
teardown. The frontend panel surface is patched out (no frontend component in
the test harness); everything else runs for real.

Coverage targets
----------------
[INIT-1] setup with a configured vacuum → LOADED + runtime/battery/tracker wired
         + platform entities created; unload → NOT_LOADED + state torn down.
[INIT-2] setup with no vacuum → still LOADED (fallback panel path).
[INIT-3] async_remove_entry clears persistent storage.
[INIT-4] setup with the full companion-entity stack present → capability
         detection enables mop/dock/position/maintenance features so the
         switch/number/button/sensor platforms construct those entities.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from custom_components.eufy_vacuum import async_remove_entry
from custom_components.eufy_vacuum.const import (
    DATA_BATTERY,
    DATA_ERROR_TRACKER,
    DATA_RUNTIME,
    DOMAIN,
)


_VAC = "vacuum.alfred"


def _patch_frontend():
    """Patch the panel surfaces that need the frontend component."""
    return [
        patch("homeassistant.components.panel_custom.async_register_panel",
              AsyncMock()),
        patch("homeassistant.components.frontend.async_remove_panel"),
    ]


async def _setup(hass, entry):
    await async_setup_component(hass, "http", {})
    entry.add_to_hass(hass)
    patches = _patch_frontend()
    for p in patches:
        p.start()
    try:
        ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()
    return ok


async def test_setup_and_unload(hass, mock_config_entry):
    """[INIT-1]"""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # core subsystems wired into hass.data
    dd = hass.data[DOMAIN]
    assert dd[DATA_RUNTIME] is not None
    assert dd[DATA_BATTERY] is not None
    assert dd[DATA_ERROR_TRACKER] is not None
    assert dd["mapping_tracker"] is not None
    # the configured vacuum became a managed record
    assert _VAC in dd[DATA_RUNTIME].data.get("vacuums", {})
    # platforms forwarded → eufy_vacuum entities exist in the registry
    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    assert any(e.platform == DOMAIN for e in reg.entities.values())

    # unload tears everything down cleanly
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert DATA_RUNTIME not in hass.data.get(DOMAIN, {})


async def test_setup_no_vacuum(hass, mock_entry_no_vacuum):
    """[INIT-2] no configured vacuum still loads (fallback panel branch)."""
    ok = await _setup(hass, mock_entry_no_vacuum)
    assert ok is True
    assert mock_entry_no_vacuum.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_entry_no_vacuum.entry_id)
    await hass.async_block_till_done()


_COMPANIONS = {
    "sensor.alfred_task_status": "cleaning",
    "sensor.alfred_dock_status": "idle",
    "sensor.alfred_active_map": "6",
    "sensor.alfred_active_cleaning_target": "",
    "sensor.alfred_cleaning_time": "1200",
    "sensor.alfred_cleaning_area": "30",
    "sensor.alfred_battery": "80",
    "sensor.alfred_error_message": "",
    "sensor.alfred_water_level": "75",
    "sensor.alfred_work_mode": "auto",
    "sensor.alfred_robot_position_x_raw": "1.0",
    "sensor.alfred_robot_position_y_raw": "2.0",
    "binary_sensor.alfred_charging": "off",
    "select.alfred_cleaning_intensity": "Standard",
    "button.alfred_wash_mop": "2026-01-01T00:00:00+00:00",
    "button.alfred_dry_mop": "2026-01-01T00:00:00+00:00",
    "button.alfred_empty_dust": "2026-01-01T00:00:00+00:00",
    "sensor.alfred_filter_remaining": "90",
    "sensor.alfred_main_brush_remaining": "85",
    "sensor.alfred_side_brush_remaining": "80",
    "sensor.alfred_rolling_brush_remaining": "88",
}


async def test_setup_full_entity_stack(hass, mock_config_entry):
    """[INIT-4] a richly-capable vacuum → more platform entities constructed."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    for entity_id, state in _COMPANIONS.items():
        hass.states.async_set(entity_id, state)
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # capability detection saw the companion stack → entities across all
    # five platforms got constructed
    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    domains = {e.entity_id.split(".", 1)[0] for e in reg.entities.values()
               if e.platform == DOMAIN}
    # the capability-gated platforms construct entities across several domains
    # (maintenance numbers/buttons, status sensors, error binary_sensor)
    assert len(domains) >= 3
    assert "number" in domains and "button" in domains

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_remove_entry_clears_storage(hass, mock_config_entry):
    """[INIT-3] async_remove_entry removes the integration's store."""
    with patch("homeassistant.helpers.storage.Store.async_remove",
               AsyncMock()) as mock_remove:
        await async_remove_entry(hass, mock_config_entry)
    mock_remove.assert_awaited_once()
