"""Backend map_switcher resolution for the dashboard snapshot (Part A).

The fork's per-vacuum "Switch Map" select (`select.<device>_switch_map`, unique_id
`<device>_map_select`, novel-only) is resolved as a device-sibling of the configured
live-map camera. The control is GATED on that entity existing — the select ships with
the eufy-clean map_load feature, so an older fork build won't have it and the snapshot
must degrade to no switcher.

Coverage
--------
[MSW-1] camera's device-sibling *_map_select is surfaced with state/options/available.
[MSW-2] no camera configured -> None.
[MSW-3] camera exists but no *_map_select on the device (older fork) -> None.
[MSW-4] the select present but unavailable -> available False, current None.
"""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr, entity_registry as er


def _wire_fork_entities(
    hass, mock_config_entry, *, ident="device123", select_state="My home (ID: 6)", select_options=None
):
    """Create a robovac_mqtt-style device with a live-map camera + a Switch Map select."""
    if mock_config_entry.entry_id not in hass.config_entries.async_entry_ids():
        mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("robovac_mqtt", ident)},
    )
    cam = ent_reg.async_get_or_create("camera", "robovac_mqtt", f"{ident}_map", device_id=device.id)
    sel = ent_reg.async_get_or_create(
        "select", "robovac_mqtt", f"{ident}_map_select", device_id=device.id
    )
    hass.states.async_set(
        sel.entity_id,
        select_state,
        {"options": select_options or ["My home (ID: 6)", "Testing map (ID: 7)"]},
    )
    return cam.entity_id, sel.entity_id


async def test_map_switcher_resolves_sibling_select(hass, manager, mock_config_entry):
    """[MSW-1]"""
    cam_id, sel_id = _wire_fork_entities(hass, mock_config_entry)
    out = manager._resolve_map_switcher(live_map_image_entity=cam_id)
    assert out == {
        "entity_id": sel_id,
        "current": "My home (ID: 6)",
        "options": ["My home (ID: 6)", "Testing map (ID: 7)"],
        "available": True,
    }


async def test_map_switcher_none_when_no_camera(manager):
    """[MSW-2]"""
    assert manager._resolve_map_switcher(live_map_image_entity=None) is None


async def test_map_switcher_none_when_no_sibling(hass, manager, mock_config_entry):
    """[MSW-3]"""
    if mock_config_entry.entry_id not in hass.config_entries.async_entry_ids():
        mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("robovac_mqtt", "dev_nosel")},
    )
    cam = ent_reg.async_get_or_create("camera", "robovac_mqtt", "dev_nosel_map", device_id=device.id)
    assert manager._resolve_map_switcher(live_map_image_entity=cam.entity_id) is None


async def test_map_switcher_unavailable_select(hass, manager, mock_config_entry):
    """[MSW-4]"""
    cam_id, sel_id = _wire_fork_entities(hass, mock_config_entry, ident="dev_unavail", select_state="unavailable")
    out = manager._resolve_map_switcher(live_map_image_entity=cam_id)
    assert out["entity_id"] == sel_id
    assert out["available"] is False
    assert out["current"] is None
