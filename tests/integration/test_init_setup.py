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
[INIT-5] boot with stored maps+rooms exercises the sensor orchestrator (room
         history + rule-status sensors built); room-update + job-finished
         callbacks fire the sync/refresh paths + auto-clear the recovered latch.
[INIT-6] adding a room then firing the room-update callback adds NEW history +
         rule-status sensors to the registry (dynamic-entity sync).
[INIT-7] the rule-status + theme refresh callbacks push observable state writes;
         saving a new theme makes the theme sensor report the new theme name.
[INIT-8] the hourly safety-net tick refreshes room-history sensors without crash.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum import async_remove_entry
from custom_components.eufy_vacuum.const import (
    DATA_BATTERY,
    DATA_ERROR_TRACKER,
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
)


_VAC = "vacuum.alfred"
_STORAGE_KEY = "eufy_vacuum.storage"


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


async def test_setup_with_maps_and_rooms(hass, hass_storage, mock_config_entry):
    """[INIT-5] boot with stored maps+rooms exercises the sensor orchestrator.

    Pre-seeding storage means the per-map/room loop in sensor.async_setup_entry
    runs (room history + rule-status sensors get built), and the registered
    room-update / job-finished callbacks fire the sync + refresh paths.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {
                "1": {"room_id": 1, "name": "Kitchen", "enabled": True},
                "2": {"room_id": 2, "name": "Bath", "enabled": True},
            }}}},
        "error_tracker": {_VAC: {
            # a recovered latch (blank current_message) → job-finished auto-clears it
            "active_run_error": {"current_message": "", "recovered": True,
                                 "errors": []},
            "last_device_error": None, "recent_errors": []}},
    }}
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    # room-scoped sensors got built from the stored rooms
    assert any(
        e.platform == DOMAIN and "_6_" in (e.unique_id or "")
        for e in reg.entities.values()
    )

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # room-update notify → _sync_room_history/_rule_status callbacks
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()
    # drop a room then notify again → stale-removal branch
    rt.data["maps"][_VAC]["6"]["rooms"].pop("2", None)
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    # job-finished → refresh history sensors + auto-clear the recovered latch
    hass.bus.async_fire(EVENT_JOB_FINISHED,
                        {"vacuum_entity_id": _VAC, "map_id": "6"})
    await hass.async_block_till_done()
    tracker = hass.data[DOMAIN][DATA_ERROR_TRACKER]
    assert tracker.get_active_run_latch(_VAC) is None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _boot_storage_one_room():
    """Storage payload with one stored vacuum + map "6" holding a single room.

    Mirrors the [INIT-5] seed but with only room "1" so the dynamic-sync tests
    can observe the *new*-room branch when a second room is introduced.
    """
    return {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {
                "1": {"room_id": 1, "name": "Kitchen", "enabled": True},
            }}}},
    }}


async def test_room_update_callback_adds_new_entities(
    hass, hass_storage, mock_config_entry
):
    """[INIT-6] adding a room + notifying builds & registers new room sensors.

    Boots with a single stored room, then introduces room "3" into the
    manager's live map data and fires _notify_rooms_updated. The registered
    sync callbacks must construct a *new* history sensor AND a *new*
    rule-status sensor and push them through async_add_entities, so both land
    in the entity registry. We observe the registry growing with unique_ids
    that carry the "_6_3" room coordinate.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)

    def _room_3_unique_ids():
        return {
            e.unique_id
            for e in reg.entities.values()
            if e.platform == DOMAIN and "_6_3_" in (e.unique_id or "")
        }

    # Room "3" does not exist yet → no sensors for it.
    assert _room_3_unique_ids() == set()

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # A newly-introduced, user-configured room. ``is_configured`` is the
    # entity-creation gate sort_room_items enforces, so without it the room
    # would be treated as discovered-but-unapproved and never materialize.
    rt.data["maps"][_VAC]["6"]["rooms"]["3"] = {
        "room_id": 3, "name": "Office", "enabled": True, "is_configured": True,
    }
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    new_ids = _room_3_unique_ids()
    # Both the history and rule-status sync callbacks fired → two new entities.
    assert any(uid.endswith("_cleaning_history") for uid in new_ids), new_ids
    assert any(uid.endswith("_rule_status") for uid in new_ids), new_ids

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_refresh_callbacks_push_state(hass, hass_storage, mock_config_entry):
    """[INIT-7] rule-status + theme refresh callbacks write observable state.

    _notify_room_rule_status_updated drives the rule-status refresh callback
    (a no-crash state-write fan-out). save_theme_as_new fires the theme update
    callback through the targeted-vacuum branch; afterwards the theme sensor's
    HA state reflects the new theme name, proving the scheduled state write
    actually reached hass.states.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    theme_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_theme_state"
    )
    assert theme_entity_id is not None
    # No theme selected yet.
    assert hass.states.get(theme_entity_id).state == "none"

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # Rule-status refresh fan-out — must not raise and must flush cleanly.
    rt._notify_room_rule_status_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    # Saving a new theme activates it and fires the theme callback for this
    # vacuum (targeted-vacuum branch). The sensor state must update to "X".
    rt.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="X")
    await hass.async_block_till_done()
    assert hass.states.get(theme_entity_id).state == "X"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_hourly_refresh_tick(hass, hass_storage, mock_config_entry):
    """[INIT-8] the hourly safety-net interval refreshes history sensors.

    Advancing the clock past the registered 1-hour interval fires
    _handle_hourly_refresh, which schedules a state write on every room-history
    sensor. The tick must complete without crashing and the history sensor must
    still hold a live state afterwards.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    history_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_6_1_cleaning_history"
    )
    assert history_entity_id is not None

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(hours=1, seconds=5)
    )
    await hass.async_block_till_done()

    # Sensor survived the tick and still reports a state (no exception thrown).
    assert hass.states.get(history_entity_id) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_remove_entry_clears_storage(hass, mock_config_entry):
    """[INIT-3] async_remove_entry removes the integration's store."""
    with patch("homeassistant.helpers.storage.Store.async_remove",
               AsyncMock()) as mock_remove:
        await async_remove_entry(hass, mock_config_entry)
    mock_remove.assert_awaited_once()
