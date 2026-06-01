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
[PM-9]  _normalize_profile_match_value coerces bool/number/off/true/false/text.
[PM-10] _match_profile_from_fields matches a preset; mismatched room → None
        (regression guard for the dropped-normalization bug).
[PM-11] overwrite_room_profile_from_room: protected / not-found / success.
[PM-12] overwrite_run_profile: not-found / no-rooms / success.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.profiles.manager import ProfileManager
from custom_components.eufy_vacuum.profiles.room_profiles import (
    resolve_room_profile_for_room,
)


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


# ---------------------------------------------------------------------------
# profile matching (regression: dropped normalization body)
# ---------------------------------------------------------------------------

def test_normalize_profile_match_value(pm):
    """[PM-9]"""
    n = pm._normalize_profile_match_value
    assert n(None) is None
    assert n(True) is True and n(False) is False
    assert n(5) == 5.0
    assert n("Off") == "off"
    assert n("true") is True and n("FALSE") is False
    assert n("3.5") == 3.5
    assert n("Max") == "max"


def test_match_profile_from_fields(pm):
    """[PM-10] a room equal to a preset matches it; a mismatched room → None.

    Before the normalization body was restored, every field compared
    None == None, so this returned the first preset for ANY room. The
    mismatch assertion below is the regression guard.
    """
    # a mop preset: protection preserves water_level for mop modes, so the
    # round-trip can actually match (vacuum presets get water forced to Off).
    name = "vacuum_mop_quick"
    eff = resolve_room_profile_for_room(
        room_config={"profile_name": name}, stored_profiles={})
    room = {
        "clean_mode": eff.get("clean_mode"),
        "fan_speed": eff.get("fan_speed"),
        "water_level": eff.get("water_level"),
        "clean_intensity": eff.get("clean_intensity"),
        "clean_passes": eff.get("clean_passes", 1),
        "edge_mopping": eff.get("edge_mopping", False),
        "floor_type": "hardwood",
    }
    assert pm._match_profile_from_fields(room) == name
    # an impossible pass count matches no preset → None (would be a false
    # match if normalization were still dropped)
    assert pm._match_profile_from_fields({**room, "clean_passes": 99}) is None


# ---------------------------------------------------------------------------
# overwrite-from-room / overwrite-run-profile
# ---------------------------------------------------------------------------

def _seed_room(pm):
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {"1": {
        "room_id": 1, "name": "Kitchen", "clean_mode": "vacuum",
        "fan_speed": "Max", "water_level": "Off",
        "clean_intensity": "Standard", "floor_type": "hardwood"}}}}}


def test_overwrite_room_profile_from_room(pm):
    """[PM-11]"""
    _save(pm)            # creates user_brushes
    _seed_room(pm)
    ok = pm.overwrite_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, profile_name="user_brushes")
    assert ok["overwritten"] is True
    # protected built-in cannot be overwritten
    assert pm.overwrite_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1,
        profile_name="vacuum_quick")["reason"] == "protected_profile"
    # unknown custom profile
    assert pm.overwrite_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1,
        profile_name="ghost")["reason"] == "profile_not_found"


def test_overwrite_run_profile(pm):
    """[PM-12]"""
    _seed_enabled_rooms(pm)
    pid = pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Evening")["profile_id"]
    ok = pm.overwrite_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid, name="Evening v2")
    assert ok["overwritten"] is True
    assert ok["profile"]["name"] == "Evening v2"
    # unknown profile id
    assert pm.overwrite_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="ghost")["reason"] == "profile_not_found"
    # no enabled rooms → rejected
    pm._data["maps"][_VAC][_MAP]["rooms"] = {}
    assert pm.overwrite_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)["reason"] == "no_rooms_selected"
