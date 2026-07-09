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
[PM-11] overwrite_room_profile_from_room: protected / not-found / success / missing-label.
[PM-12] overwrite_run_profile: not-found / no-rooms / success.
[PM-13] overwrite_room_profile error returns: protected name + unknown profile.
[PM-14] save_room_profile_from_room: missing-label / unknown-room / protected-target / details-unavailable.
[PM-15] rename_room_profile more rejections: target protected / exists / empty label.
[PM-16] apply_room_profile: unknown profile name → profile_not_found, no rooms updated.
[PM-17] _protected_room_config downgrades a carpet mop room to vacuum, water + edge off.
[PM-18] run_profile_steps: a legacy rooms-only profile back-fills to one room_group step.
[PM-19] run_profile_steps: an explicit steps list is normalized + returned.
[PM-20] normalize_run_profile_steps: drops junk/empty/bad-target; clamps target 1..100.
[PM-21] set_run_profile_steps: a room→charge→room sequence stores + flags has_charge_steps.
[PM-22] set_run_profile_steps: steps with no room_group are rejected.
[PM-23] set_run_profile_steps: unknown profile → profile_not_found.
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


# ---------------------------------------------------------------------------
# run-profile steps (charge-step Wave 3a)
# ---------------------------------------------------------------------------

def test_run_profile_steps_backfills_legacy_rooms(pm):
    """[PM-18]"""
    steps = ProfileManager.run_profile_steps({"rooms": [{"room_id": 1}, {"room_id": 2}]})
    assert steps == [{"type": "room_group", "rooms": [{"room_id": 1}, {"room_id": 2}]}]


def test_run_profile_steps_uses_explicit_steps(pm):
    """[PM-19]"""
    prof = {"rooms": [{"room_id": 9}], "steps": [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 95},
        {"type": "room_group", "rooms": [{"room_id": 2}]},
    ]}
    steps = ProfileManager.run_profile_steps(prof)
    assert [s["type"] for s in steps] == ["room_group", "charge_wait", "room_group"]
    assert steps[1]["target_battery_percent"] == 95


def test_normalize_steps_drops_invalid_and_clamps(pm):
    """[PM-20]"""
    out = ProfileManager.normalize_run_profile_steps([
        "junk",
        {"type": "room_group", "rooms": []},                     # empty -> dropped
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 250},   # clamp -> 100
        {"type": "charge_wait", "target_battery_percent": "x"},    # bad -> dropped
        {"type": "mystery"},                                       # unknown -> dropped
    ])
    assert out == [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 100},
    ]


def _seed_run_profile(pm, profile_id="p1"):
    lib = pm._get_saved_run_profile_store(vacuum_entity_id=_VAC, map_id=_MAP)
    lib[profile_id] = {"id": profile_id, "name": "Test", "vacuum_entity_id": _VAC,
                       "map_id": _MAP, "rooms": [{"room_id": 1}]}
    return lib


def test_set_run_profile_steps_success(pm):
    """[PM-21]"""
    _seed_run_profile(pm)
    out = pm.set_run_profile_steps(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1", steps=[
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 95},
        {"type": "room_group", "rooms": [{"room_id": 2}]},
    ])
    assert out["saved"] is True
    assert out["profile"]["has_charge_steps"] is True
    assert [s["type"] for s in out["profile"]["steps"]] == ["room_group", "charge_wait", "room_group"]


def test_set_run_profile_steps_requires_a_room_group(pm):
    """[PM-22]"""
    _seed_run_profile(pm)
    out = pm.set_run_profile_steps(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1",
                                   steps=[{"type": "charge_wait", "target_battery_percent": 95}])
    assert out["saved"] is False and out["reason"] == "no_room_group"


def test_set_run_profile_steps_unknown_profile(pm):
    """[PM-23]"""
    out = pm.set_run_profile_steps(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="nope", steps=[])
    assert out["saved"] is False and out["reason"] == "profile_not_found"


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


def test_overwrite_room_profile_rejections(pm):
    """[PM-13] overwrite_room_profile error returns: protected name + unknown profile."""
    fields = dict(label="X", clean_mode="vacuum", fan_speed="Max", water_level="Off",
                  clean_intensity="Standard", clean_passes=1, edge_mopping=False)
    assert pm.overwrite_room_profile(
        profile_name="vacuum_quick", **fields)["reason"] == "protected_profile"
    assert pm.overwrite_room_profile(
        profile_name="ghost", **fields)["reason"] == "profile_not_found"


def test_save_room_profile_from_room_rejections(pm):
    """[PM-14] save_room_profile_from_room error returns: missing label, unknown
    room, protected target name."""
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {"1": {
        "room_id": 1, "name": "Kitchen", "clean_mode": "vacuum", "fan_speed": "Max"}}}}}
    assert pm.save_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, label="  ")["reason"] == "missing_label"
    assert pm.save_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=99, label="X")["reason"] == "room_not_found"
    assert pm.save_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, label="X",
        profile_name="vacuum_quick")["reason"] == "protected_profile"


def test_save_room_profile_from_room_details_unavailable(pm, monkeypatch):
    """[PM-14] save_room_profile_from_room → room_details_unavailable when the room
    exists with a label but the effective details can't be resolved (the 403 arm —
    e.g. the room was deleted between the existence check and the resolve)."""
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {"1": {
        "room_id": 1, "name": "Kitchen", "clean_mode": "vacuum", "fan_speed": "Max"}}}}}
    monkeypatch.setattr(pm, "get_effective_room_details", lambda **kw: None)
    result = pm.save_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, label="My Room",
        profile_name="user_custom")
    assert result["saved"] is False
    assert result["reason"] == "room_details_unavailable"


def test_rename_room_profile_more_rejections(pm):
    """[PM-15] rename_room_profile error returns: target name protected, target
    name already exists, empty new label."""
    _save(pm, name="user_a")
    _save(pm, name="user_b")
    assert pm.rename_room_profile(
        profile_name="user_a", new_profile_name="vacuum_quick")["reason"] == "protected_profile"
    assert pm.rename_room_profile(
        profile_name="user_a", new_profile_name="user_b")["reason"] == "profile_name_exists"
    assert pm.rename_room_profile(
        profile_name="user_a", label="  ")["reason"] == "missing_label"


def test_apply_room_profile_unknown(pm):
    """[PM-16] apply_room_profile: unknown profile name → profile_not_found error
    payload with no rooms updated."""
    result = pm.apply_room_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[1], profile_name="ghost")
    assert result["error"] == "profile_not_found"
    assert result["updated_room_ids"] == []


def test_protected_room_config_carpet_downgrades_mop(pm):
    """[PM-17] a carpet room set to a mop mode is downgraded to vacuum, with water
    level and edge mopping forced off (the carpet-protection invariant)."""
    out = pm._protected_room_config({
        "floor_type": "carpet", "clean_mode": "vacuum_mop",
        "water_level": "High", "edge_mopping": True})
    assert out["clean_mode"] == "vacuum"
    assert out["water_level"] == "Off"
    assert out["edge_mopping"] is False


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


def test_overwrite_room_profile_from_room_missing_label(pm, monkeypatch):
    """[PM-11] overwrite_room_profile_from_room → missing_label when neither the call
    nor the existing profile supplies a label (the 474 arm). Stub the lookup to an
    editable profile with a blank label so the guard is what's exercised."""
    monkeypatch.setattr(
        pm, "_get_editable_room_profile",
        lambda name: ("user_brushes", {"label": ""}))
    result = pm.overwrite_room_profile_from_room(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1,
        profile_name="user_brushes", label="")
    assert result["overwritten"] is False
    assert result["reason"] == "missing_label"


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
