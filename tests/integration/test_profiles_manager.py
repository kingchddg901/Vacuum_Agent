"""Tests for profiles/manager.py — ProfileManager room/run profile CRUD.

ProfileManager operates on manager.data + the profiles.room_profiles helpers,
so a MagicMock manager with a real .data dict exercises the CRUD paths.

Coverage targets
----------------
[PM-1]  get_room_profiles merges built-ins + exposes protected names.
[PM-2]  save_user_room_profile saves; a protected name is rejected.
[PM-3]  rename_room_profile: rename; protected + not-found rejections.
[PM-4]  delete_room_profile: delete; protected + not-found rejections.
[PM-5]  get_effective_room_details resolves a stored room; None when absent.
[PM-6]  get_saved_run_profiles: empty library → 0.
[PM-7]  save_run_profile from enabled rooms; missing-name / no-rooms rejections.
[PM-8]  rename_run_profile / delete_run_profile incl. not-found.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.profiles.manager import ProfileManager


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def pm() -> ProfileManager:
    mgr = MagicMock()
    mgr.data = {}
    return ProfileManager(mgr)


def _save(pm, name="user_brushes"):
    return pm.save_user_room_profile(
        label="Brushes", clean_mode="vacuum", fan_speed="Max", water_level="Off",
        clean_intensity="Standard", clean_passes=1, edge_mopping=False, profile_name=name)


def test_get_room_profiles(pm):
    """[PM-1]"""
    result = pm.get_room_profiles()
    assert result["profile_count"] >= 1
    assert "vacuum_quick" in result["profiles"]
    assert "vacuum_quick" in result["protected_profile_names"]


def test_save_user_profile(pm):
    """[PM-2]"""
    assert _save(pm)["saved"] is True
    assert pm._data["profiles"]["room_profiles"]["user_brushes"]["label"] == "Brushes"
    # protected name rejected
    blocked = _save(pm, name="vacuum_quick")
    assert blocked["saved"] is False and blocked["reason"] == "protected_profile"


def test_rename_profile(pm):
    """[PM-3]"""
    _save(pm)
    ok = pm.rename_room_profile(profile_name="user_brushes", new_profile_name="user_renamed")
    assert ok["renamed"] is True and ok["profile_name"] == "user_renamed"
    assert pm.rename_room_profile(
        profile_name="vacuum_quick", new_profile_name="x")["reason"] == "protected_profile"
    assert pm.rename_room_profile(
        profile_name="ghost", new_profile_name="y")["reason"] == "profile_not_found"


def test_delete_profile(pm):
    """[PM-4]"""
    _save(pm)
    assert pm.delete_room_profile(profile_name="user_brushes")["deleted"] is True
    assert pm.delete_room_profile(profile_name="vacuum_quick")["reason"] == "protected_profile"
    assert pm.delete_room_profile(profile_name="ghost")["reason"] == "profile_not_found"


def test_effective_room_details(pm):
    """[PM-5]"""
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {"1": {
        "room_id": 1, "name": "Kitchen", "clean_mode": "vacuum",
        "fan_speed": "Max", "floor_type": "hardwood"}}}}}
    details = pm.get_effective_room_details(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    assert details is not None
    assert details["clean_mode"] is not None
    assert pm.get_effective_room_details(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=99) is None


def test_get_saved_run_profiles_empty(pm):
    """[PM-6]"""
    result = pm.get_saved_run_profiles(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["profile_count"] == 0
    assert result["profiles"] == []


def _seed_enabled_rooms(pm):
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {
        "1": {"room_id": 1, "name": "Kitchen", "enabled": True, "order": 1},
        "2": {"room_id": 2, "name": "Bath", "enabled": True, "order": 2},
    }}}}


def test_save_run_profile(pm):
    """[PM-7]"""
    _seed_enabled_rooms(pm)
    saved = pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Evening")
    assert saved["saved"] is True
    listing = pm.get_saved_run_profiles(vacuum_entity_id=_VAC, map_id=_MAP)
    assert listing["profile_count"] == 1 and listing["profiles"][0]["name"] == "Evening"
    # rejections
    assert pm.save_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, name="  ")["reason"] == "missing_name"
    pm._data["maps"][_VAC][_MAP]["rooms"] = {}  # nothing enabled
    assert pm.save_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, name="X")["reason"] == "no_rooms_selected"


def test_rename_delete_run_profile(pm):
    """[PM-8]"""
    _seed_enabled_rooms(pm)
    pid = pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Evening")["profile_id"]
    renamed = pm.rename_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid, name="Night")
    assert renamed["renamed"] is True
    assert pm.rename_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="ghost", name="x")["reason"] == "profile_not_found"
    deleted = pm.delete_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    assert deleted["deleted"] is True
    assert pm.get_saved_run_profiles(vacuum_entity_id=_VAC, map_id=_MAP)["profile_count"] == 0
