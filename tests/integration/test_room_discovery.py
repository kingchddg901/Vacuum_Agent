"""Tests for rooms/room_discovery.py — adapter-config-driven room discovery.

Uses the `manager` fixture (active AdapterCoordinator) + real hass states.

Coverage targets
----------------
[RD-1] get_active_map_id reads the adapter active_map entity; sentinels → None.
[RD-2] get_active_map_id: no declared entity → None.
[RD-3] discover_rooms_for_vacuum normalizes + dedups + skips bad rows.
[RD-4] discover_rooms_for_vacuum: incomplete discovery config → [].
[RD-5] discover_rooms_payload wraps the room list with counts.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.rooms.room_discovery import (
    discover_rooms_for_vacuum,
    discover_rooms_payload,
    get_active_map_id,
)


_VAC = "vacuum.alfred"


def _discovery_adapter():
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })


def test_active_map_id(hass, manager):
    """[RD-1]"""
    _discovery_adapter()
    hass.states.async_set("sensor.alfred_map", "6")
    assert get_active_map_id(hass, _VAC) == "6"
    hass.states.async_set("sensor.alfred_map", "unavailable")
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_no_entity(hass, manager):
    """[RD-2]"""
    register_adapter_config(_VAC, {"adapter_id": "t", "source": "t", "entities": {}})
    assert get_active_map_id(hass, _VAC) is None


def test_discover_rooms(hass, manager):
    """[RD-3] dedup id 1, skip non-int id, skip name-less."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
        {"id": 1, "name": "Dup"},      # duplicate id → skipped
        {"id": "x", "name": "Bad"},    # non-int id → skipped
        {"id": 3, "name": ""},          # empty name → skipped
    ]})
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    assert [r["room_id"] for r in rooms] == [1, 2]
    assert rooms[0]["slug"] == "kitchen"
    assert rooms[0]["map_id"] == "6"


def test_discover_incomplete_config(hass, manager):
    """[RD-4]"""
    register_adapter_config(_VAC, {"adapter_id": "t", "source": "t",
                                   "discovery": {"room_list_entity": "vacuum_entity"}})
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []


def test_discover_payload(hass, manager):
    """[RD-5]"""
    _discovery_adapter()
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    payload = discover_rooms_payload(hass, vacuum_entity_id=_VAC)
    assert payload["room_count"] == 1
    assert payload["active_map_id"] == "6"
