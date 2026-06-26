"""Tests for rooms/room_discovery.py — adapter-config-driven room discovery.

Uses the `manager` fixture (active AdapterCoordinator) + real hass states.

Coverage targets
----------------
[RD-1] get_active_map_id reads the adapter active_map entity; sentinels → None.
[RD-2] get_active_map_id: no declared entity → None.
[RD-3] discover_rooms_for_vacuum normalizes + dedups + skips bad rows.
[RD-4] discover_rooms_for_vacuum: incomplete discovery config → [].
[RD-5] discover_rooms_payload wraps the room list with counts.
[RD-6] room_list_entity = concrete entity id sources from that entity, not the vacuum.
[RD-7] attribute mode — active_map DECLARED but the entity never created (scalar)
       + implicit_map_id + segments → implicit id.
[RD-8] scalar shape but no rooms visible → None (no phantom map).
[RD-9] a declared active_map entity that EXISTS (has state) wins; implicit never fires.
[RD-10] a declared active_map entity present with a sentinel value → None (don't fork).
[RD-11] implicit map only applies to the vacuum-attribute source.
[RD-12] end-to-end: scalar/Tuya path imports rooms under the implicit id.
[RD-13] BOOT RACE: active_map declared + REGISTERED but stateless → None (must NOT fork
        a phantom map for a novel device whose sensor hasn't materialised yet).
"""

from __future__ import annotations

import pytest

from homeassistant.helpers import entity_registry as er

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


def _attribute_mode_adapter(*, implicit="main", room_list_entity="vacuum_entity"):
    """Real scalar/Tuya shape: the adapter DECLARES active_map from its naming
    pattern (every Eufy device does, existence-unchecked), but the scalar
    transport never creates that sensor — so the declared entity is absent from
    BOTH the state machine and the entity registry. Tests using this must NOT
    create or register sensor.alfred_map; that absence is what selects the
    attribute-mode path."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        # DECLARED (like the real adapter) but never created on the scalar transport.
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": room_list_entity,
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
            "implicit_map_id": implicit,
        },
    })


def test_active_map_implicit_attribute_mode(hass, manager):
    """[RD-7] active_map declared but the entity is absent from HA (scalar) +
    implicit_map_id + segments → implicit id. (Regression guard: the adapter
    ALWAYS declares active_map, so 'declared' must not block the fallback.)"""
    _attribute_mode_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    # sensor.alfred_map is intentionally never created → attribute-mode.
    assert get_active_map_id(hass, _VAC) == "main"


def test_active_map_implicit_no_segments(hass, manager):
    """[RD-8] scalar shape but no usable rooms → None (no phantom map)."""
    _attribute_mode_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": []})
    assert get_active_map_id(hass, _VAC) is None
    hass.states.async_set(_VAC, "docked", {})  # attribute entirely absent
    assert get_active_map_id(hass, _VAC) is None
    hass.states.async_set(_VAC, "docked", {"segments": ["junk", 5]})  # no dict rows
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_entity_wins_over_implicit(hass, manager):
    """[RD-9] a present active_map entity (real state) wins; implicit never fires."""
    _attribute_mode_adapter()
    hass.states.async_set("sensor.alfred_map", "6")  # entity EXISTS with a value
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) == "6"


def test_active_map_unavailable_not_implicit(hass, manager):
    """[RD-10] a present active_map entity with a sentinel value → None. It must
    NOT fall back to the implicit id — that would fork a second map for a device
    whose real map is merely offline for a moment."""
    _attribute_mode_adapter()
    hass.states.async_set("sensor.alfred_map", "unavailable")  # exists, sentinel
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_registered_but_stateless_boot_race(hass, manager):
    """[RD-13] active_map declared + REGISTERED in the entity registry but with no
    state yet (novel device, restart window) → None. Must NOT fork a phantom
    'main' map even though segments are already populated — registry presence
    distinguishes this from the scalar transport (which never registers it)."""
    _attribute_mode_adapter()
    # Register sensor.alfred_map WITHOUT setting a state (the boot-race window).
    er.async_get(hass).async_get_or_create(
        "sensor", "eufy_vacuum", "alfred_map_unique",
        suggested_object_id="alfred_map",
    )
    assert hass.states.get("sensor.alfred_map") is None  # registered, no state
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_implicit_only_for_vacuum_attribute(hass, manager):
    """[RD-11] implicit map only applies to the vacuum-attribute room source."""
    _attribute_mode_adapter(room_list_entity="sensor.alfred_rooms")
    hass.states.async_set("sensor.alfred_rooms", "ok",
                          {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) is None


def test_discover_attribute_mode_end_to_end(hass, manager):
    """[RD-12] scalar/Tuya path: active_map declared but absent, rooms import
    under the implicit id — the exact scenario behind the 'No active map' block."""
    _attribute_mode_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
    ]})
    map_id = get_active_map_id(hass, _VAC)
    assert map_id == "main"
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id=map_id)
    assert [r["room_id"] for r in rooms] == [1, 2]
    assert rooms[0]["map_id"] == "main"


def test_discover_rooms_from_other_entity(hass, manager):
    """[RD-6] room_list_entity = concrete entity id sources from that entity, not the vacuum."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": "sensor.alfred_rooms",  # concrete id, NOT the "vacuum_entity" sentinel
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })
    # Decoy on the vacuum entity: must NOT be sourced.
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 99, "name": "WrongEntity"}]})
    # Real room list lives on the other entity.
    hass.states.async_set("sensor.alfred_rooms", "ok", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
    ]})

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")

    ids = [r["room_id"] for r in rooms]
    assert ids == [1, 2]                 # sourced from sensor.alfred_rooms
    assert rooms[0]["name"] == "Kitchen"
    assert 99 not in ids                 # vacuum entity's decoy was NOT used
