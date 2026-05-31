"""Unit tests for models/models.py — dataclass config records.

Coverage targets
----------------
[MOD-1] RoomConfig defaults + as_dict round-trip.
[MOD-2] MapConfig.as_dict nests room dicts keyed by str room id.
[MOD-3] VacuumCapabilities.as_dict.
[MOD-4] VacuumRuntimeState.as_dict.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.models.models import (
    MapConfig,
    RoomConfig,
    VacuumCapabilities,
    VacuumRuntimeState,
)


def test_room_config():
    """[MOD-1]"""
    room = RoomConfig(room_id=1, map_id="6", name="Kitchen")
    assert room.enabled is True and room.clean_mode == "vacuum"
    d = room.as_dict()
    assert d["room_id"] == 1 and d["name"] == "Kitchen"
    assert d["grants_access_to"] == [] and d["rules"] == []


def test_map_config():
    """[MOD-2]"""
    mc = MapConfig(map_id="6", name="Downstairs",
                   rooms={1: RoomConfig(room_id=1, map_id="6", name="Kitchen")})
    d = mc.as_dict()
    assert d["map_id"] == "6"
    assert "1" in d["rooms"] and d["rooms"]["1"]["name"] == "Kitchen"


def test_vacuum_capabilities():
    """[MOD-3]"""
    caps = VacuumCapabilities(supports_room_clean=True, detected_model="T2351")
    d = caps.as_dict()
    assert d["supports_room_clean"] is True
    assert d["detected_model"] == "T2351"


def test_runtime_state():
    """[MOD-4]"""
    state = VacuumRuntimeState(vacuum_entity_id="vacuum.alfred", selected_room_ids=[1, 2])
    d = state.as_dict()
    assert d["vacuum_entity_id"] == "vacuum.alfred"
    assert d["selected_room_ids"] == [1, 2]
    assert d["start_block_reason"] == "unknown"
