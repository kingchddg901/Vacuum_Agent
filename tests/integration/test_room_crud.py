"""Tests for rooms/room_crud.py — RoomMapManager (mock manager + .data).

RoomMapManager calls several manager hooks (ensure_vacuum_record,
_refresh_room_derived_state, _notify_rooms_updated, mark_rooms_discovered,
confirm_floor_type, ensure_runtime) — all no-ops on a MagicMock — and the real
build_managed_rooms / rebuild_map_bucket helpers.

Coverage targets
----------------
[RC-1] save_managed_rooms builds managed rooms from discovery.
[RC-2] get_managed_rooms returns the stored rooms + summary.
[RC-3] remove_map deletes the bucket + reports removals.
[RC-4] get_vacuum_maps summarizes known maps.
[RC-5] rebuild_map rebuilds from discovery.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def rmm():
    mgr = MagicMock()
    mgr.data = {}
    mgr.ensure_runtime.return_value = MagicMock()
    return RoomMapManager(mgr), mgr


def _seed_discovery(mgr, rooms):
    mgr.data.setdefault("discovery", {}).setdefault(_VAC, {})[_MAP] = {"rooms": rooms}


_DISCOVERED = [
    {"room_id": 1, "map_id": "6", "name": "Kitchen"},
    {"room_id": 2, "map_id": "6", "name": "Bath"},
]


def test_save_managed_rooms(rmm):
    """[RC-1]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    result = rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["room_count"] == 2
    assert set(result["rooms"]) == {"1", "2"}
    assert mgr.data["maps"][_VAC][_MAP]["rooms"]


def test_get_managed_rooms(rmm):
    """[RC-2]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    got = rm.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert got["room_count"] == 2
    assert "summary" in got


def test_remove_map(rmm):
    """[RC-3]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert removed["rooms_removed"] == 2
    assert removed["discovery_removed"] is True
    assert _MAP not in mgr.data["maps"][_VAC]


def test_get_vacuum_maps(rmm):
    """[RC-4]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    maps = rm.get_vacuum_maps(vacuum_entity_id=_VAC)
    assert maps["map_count"] == 1
    assert maps["maps"][0]["room_count"] == 2


def test_rebuild_map(rmm):
    """[RC-5]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    # discovery now reports only one room → rebuild drops the stale one
    _seed_discovery(mgr, [{"room_id": 1, "map_id": "6", "name": "Kitchen"}])
    rebuilt = rm.rebuild_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert rebuilt["room_count"] == 1
    assert set(rebuilt["rooms"]) == {"1"}
