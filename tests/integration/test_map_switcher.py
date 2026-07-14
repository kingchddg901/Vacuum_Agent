"""Backend map_switcher resolution + post-switch frame gate for the dashboard snapshot.

The fork's per-vacuum "Switch Map" select (`select.<device>_switch_map`, unique_id
`<device>_map_select`, novel-only) is resolved as a device-sibling of the configured
live-map camera. The control is GATED on that entity existing — the select ships with
the eufy-clean map_load feature, so an older fork build won't have it and the snapshot
must degrade to no switcher.

The block also carries ``frame_ungrounded`` — after a map switch the robot's coordinate
frame stays on the old map until it MOVES and re-localizes, so the card pauses zone
drawing in that window (see manager._compute_map_frame_gate / acknowledge_map_frame).

Coverage
--------
[MSW-1] camera's device-sibling *_map_select is surfaced with state/options/available.
[MSW-2] no camera configured -> None.
[MSW-3] camera exists but no *_map_select on the device (older fork) -> None.
[MSW-4] the select present but unavailable -> available False, current None.
[MSW-5] active-map change arms the gate; stays gated while the robot is docked.
[MSW-6] a pose move past the threshold clears the gate.
[MSW-7] acknowledge_map_frame overrides until the NEXT switch re-arms it.
[MSW-8] a cleaning/returning vacuum state clears the gate.
[MSW-9] no usable active-map signal -> never gated.
[MSW-10] the resolved block carries frame_ungrounded/reason after a switch.
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


def _set_active_map(hass, obj, value):
    hass.states.async_set(f"sensor.{obj}_active_map", value)


def _set_pose(hass, obj, x, y):
    hass.states.async_set(f"sensor.{obj}_robot_position_x_raw", str(x))
    hass.states.async_set(f"sensor.{obj}_robot_position_y_raw", str(y))


async def test_map_switcher_resolves_sibling_select(hass, manager, mock_config_entry):
    """[MSW-1]"""
    cam_id, sel_id = _wire_fork_entities(hass, mock_config_entry)
    out = manager._resolve_map_switcher(
        vacuum_entity_id="vacuum.device123", live_map_image_entity=cam_id
    )
    assert out == {
        "entity_id": sel_id,
        "current": "My home (ID: 6)",
        "options": ["My home (ID: 6)", "Testing map (ID: 7)"],
        "available": True,
        "frame_ungrounded": False,
        "frame_ungrounded_reason": None,
    }


async def test_map_switcher_none_when_no_camera(manager):
    """[MSW-2]"""
    assert (
        manager._resolve_map_switcher(
            vacuum_entity_id="vacuum.nope", live_map_image_entity=None
        )
        is None
    )


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
    assert (
        manager._resolve_map_switcher(
            vacuum_entity_id="vacuum.dev_nosel", live_map_image_entity=cam.entity_id
        )
        is None
    )


async def test_map_switcher_unavailable_select(hass, manager, mock_config_entry):
    """[MSW-4]"""
    cam_id, sel_id = _wire_fork_entities(hass, mock_config_entry, ident="dev_unavail", select_state="unavailable")
    out = manager._resolve_map_switcher(
        vacuum_entity_id="vacuum.dev_unavail", live_map_image_entity=cam_id
    )
    assert out["entity_id"] == sel_id
    assert out["available"] is False
    assert out["current"] is None


async def test_frame_gate_arms_on_switch(hass, manager):
    """[MSW-5]"""
    obj, vac = "gate5", "vacuum.gate5"
    _set_active_map(hass, obj, "6")
    _set_pose(hass, obj, 100, 100)
    # First observation: no prior map to compare -> grounded.
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac) == (False, None)
    # Switch to map 7 with the robot still docked -> armed, stays armed.
    _set_active_map(hass, obj, "7")
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac) == (True, "map_switched")
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac) == (True, "map_switched")


async def test_frame_gate_clears_on_move(hass, manager):
    """[MSW-6]"""
    obj, vac = "gate6", "vacuum.gate6"
    _set_active_map(hass, obj, "6")
    _set_pose(hass, obj, 100, 100)
    manager._compute_map_frame_gate(vacuum_entity_id=vac)  # seed
    _set_active_map(hass, obj, "7")
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac)[0] is True
    _set_pose(hass, obj, 200, 100)  # moved well past the threshold
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac) == (False, None)


async def test_frame_gate_user_override(hass, manager):
    """[MSW-7]"""
    obj, vac = "gate7", "vacuum.gate7"
    _set_active_map(hass, obj, "6")
    _set_pose(hass, obj, 100, 100)
    manager._compute_map_frame_gate(vacuum_entity_id=vac)  # seed
    _set_active_map(hass, obj, "7")
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac)[0] is True
    # Override clears it even though the robot never moved.
    assert manager.acknowledge_map_frame(vacuum_entity_id=vac)["acknowledged"] is True
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac) == (False, None)
    # The NEXT switch re-arms the gate.
    _set_active_map(hass, obj, "6")
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac)[0] is True


async def test_frame_gate_clears_when_cleaning(hass, manager):
    """[MSW-8]"""
    obj, vac = "gate8", "vacuum.gate8"
    _set_active_map(hass, obj, "6")
    _set_pose(hass, obj, 100, 100)
    manager._compute_map_frame_gate(vacuum_entity_id=vac)  # seed
    _set_active_map(hass, obj, "7")
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac)[0] is True
    hass.states.async_set(vac, "cleaning")  # moving -> re-localizing
    assert manager._compute_map_frame_gate(vacuum_entity_id=vac) == (False, None)


async def test_frame_gate_no_active_map_signal(manager):
    """[MSW-9]"""
    assert manager._compute_map_frame_gate(vacuum_entity_id="vacuum.nosignal") == (False, None)


async def test_map_switcher_block_reports_frame_ungrounded(hass, manager, mock_config_entry):
    """[MSW-10]"""
    obj, vac = "gate10", "vacuum.gate10"
    cam_id, _sel_id = _wire_fork_entities(hass, mock_config_entry, ident=obj)
    _set_active_map(hass, obj, "6")
    _set_pose(hass, obj, 100, 100)
    manager._resolve_map_switcher(vacuum_entity_id=vac, live_map_image_entity=cam_id)  # seed
    _set_active_map(hass, obj, "7")
    out = manager._resolve_map_switcher(vacuum_entity_id=vac, live_map_image_entity=cam_id)
    assert out["frame_ungrounded"] is True
    assert out["frame_ungrounded_reason"] == "map_switched"
