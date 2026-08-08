"""Tests for profiles/manager.py — ProfileManager room/run profile CRUD.

ProfileManager operates on manager.data + the profiles.room_profiles helpers,
so a MagicMock manager with a real .data dict exercises the CRUD paths.

Coverage targets
----------------
[PM-1]  get_room_profiles merges built-ins + exposes protected names.
[PM-2]  save_user_room_profile saves; a protected name is rejected.
[PM-2b] save_user_room_profile derives path_type (Deep→narrow) + mop_required (B2).
[PM-3]  rename_room_profile: rename; protected + not-found rejections.
[PM-4]  delete_room_profile: delete; protected + not-found rejections.
[PM-5]  get_effective_room_details resolves a stored room; None when absent.
[PM-6]  get_saved_run_profiles: empty library → 0.
[PM-7]  save_run_profile from enabled rooms; missing-name / no-rooms rejections.
[PM-8]  rename_run_profile / delete_run_profile incl. not-found.
[PM-9]  _normalize_profile_match_value coerces bool/number/off/true/false/text.
[PM-10] _match_profile_from_fields matches a preset; mismatched room → None
        (regression guard for the dropped-normalization bug).
[PM-10b] _match_profile_from_fields: a plain vacuum room matches its vacuum preset
        (B1 — vacuum water forced Off vs candidate's floor water default).
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
[PM-24] overwrite_run_profile clears the stale steps list so the new rooms win (Defect #3).
[PM-25] has_stops flags a sequenced run (break step OR >1 room_group); charge-only stays
        distinct from has_charge_steps; a plain single-group queue is has_stops=False (Defect #4b).
[PM-26] normalize_run_profile_steps validates room_group entries: wraps a bare int, drops a
        bad room_id, drops an all-malformed group (Defect #6a).
[PM-27] a stepped edit re-derives room_count/ids/names from the effective steps, not the stale
        profile["rooms"]; legacy rooms-only stays correct (Defect #7).
[PM-28] delete_room_profile refuses when a room still references it, unless force=True (RP-016).
[PM-29] rename_room_profile repoints every referring room's profile_name to the new name (RP-016).
[PM-19] ISSUE #48: Edge Mopping survives the save -> read round trip.
[PM-19b] every mop spelling (display label, token, mixed case) keeps it.
[PM-19c] the carpet-downgrade sibling uses the same predicate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from tests._factories import spec_manager

from custom_components.eufy_vacuum.profiles.manager import ProfileManager
from custom_components.eufy_vacuum.profiles.room_profiles import (
    resolve_room_profile_for_room,
    resolve_profile_catalog,
    no_water_value,
)

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

from tests.brand_catalogs import SYNTHETIC_BLOCK, adapter_config


# ProfileManager mechanics, not vocabulary — so the catalog is the synthetic brand's.
# _match_profile_from_fields and get_room_profiles now require a vacuum because core
# holds no catalog of its own; the synthetic_adapter fixture registers one for _VAC.
pytestmark = pytest.mark.usefixtures("synthetic_adapter")

_CATALOG = resolve_profile_catalog(SYNTHETIC_BLOCK)

_VAC = "vacuum.alfred"
_MAP = "6"


def _queue_steps(*, steps=None, breaks=None) -> dict:
    """The real shape of manager.get_queue_steps — a FLAT queue by default.

    Both save_run_profile and (since RP-021b) overwrite_run_profile snapshot the
    current queue through this call. It was never stubbed, so the autospec'd
    manager returned a MagicMock whose `.get("has_breaks")` is truthy, and
    save_run_profile has quietly been writing a MagicMock into `steps` for as long
    as these tests have existed. Nothing asserted on it, so nothing failed.
    `has_breaks` is DERIVED here rather than passed, for the same reason production
    derives it — a stub that lets the flag disagree with the steps can assert a
    combination the real function cannot produce.
    """
    steps = list(steps or [])
    return {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "steps": steps,
        "breaks": list(breaks or []),
        "has_breaks": any(s.get("type") != "room_group" for s in steps),
    }


@pytest.fixture
def pm() -> ProfileManager:
    mgr = spec_manager()
    mgr.data = {}
    mgr.get_queue_steps.return_value = _queue_steps()
    return ProfileManager(mgr)


def _save(pm, name="user_brushes"):
    return pm.save_user_room_profile(
        label="Brushes", clean_mode="vacuum", fan_speed="Max", water_level="Off",
        clean_intensity="Quick", clean_passes=1, edge_mopping=False, profile_name=name)


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


def test_run_profile_steps_strips_a_legacy_leading_break(pm):
    """[PM-19b] Q17/RP-021a: a profile saved before the leading-break rejection existed
    must still render/start — run_profile_steps normalizes it away loudly instead of
    raising (compatibility_constraints: never fail to start on legacy data)."""
    prof = {"rooms": [{"room_id": 9}], "steps": [
        {"type": "charge_wait", "target_battery_percent": 80},
        {"type": "room_group", "rooms": [{"room_id": 1}]},
    ]}
    steps = ProfileManager.run_profile_steps(prof)
    assert [s["type"] for s in steps] == ["room_group"]


def test_normalize_steps_drops_invalid_and_clamps(pm):
    """[PM-20] The charge_wait sits between two room_groups (not trailing) — a trailing
    one is unsupported since Q17/RP-021a and raises instead of clamping-then-keeping
    (see test_normalize_steps_rejects_trailing_break)."""
    out = ProfileManager.normalize_run_profile_steps([
        "junk",
        {"type": "room_group", "rooms": []},                     # empty -> dropped
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 250},   # clamp -> 100
        {"type": "charge_wait", "target_battery_percent": "x"},    # bad -> dropped
        {"type": "mystery"},                                       # unknown -> dropped
        {"type": "room_group", "rooms": [{"room_id": 2}]},
    ])
    assert out == [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 100},
        {"type": "room_group", "rooms": [{"room_id": 2}]},
    ]


def test_normalize_steps_rejects_leading_break(pm):
    """[PM-20b] Q17/RP-021a: a leading charge_wait/wait has nothing to bracket."""
    with pytest.raises(ServiceValidationError) as exc_info:
        ProfileManager.normalize_run_profile_steps([
            {"type": "charge_wait", "target_battery_percent": 80},
            {"type": "room_group", "rooms": [{"room_id": 1}]},
        ])
    assert exc_info.value.translation_key == "leading_break_unsupported"


def test_normalize_steps_rejects_trailing_break(pm):
    """[PM-20c] Q17/RP-021a: same treatment for a trailing wait."""
    with pytest.raises(ServiceValidationError) as exc_info:
        ProfileManager.normalize_run_profile_steps([
            {"type": "room_group", "rooms": [{"room_id": 1}]},
            {"type": "wait", "wait_minutes": 5},
        ])
    assert exc_info.value.translation_key == "trailing_break_unsupported"


def test_normalize_steps_single_break_is_never_leading_or_trailing(pm):
    """[PM-20d] A lone break (the queue_breaks call sites: one already-positioned break
    normalized in isolation) has no sequence to be first/last in — never rejected."""
    out = ProfileManager.normalize_run_profile_steps(
        [{"type": "charge_wait", "target_battery_percent": 80}]
    )
    assert out == [{"type": "charge_wait", "target_battery_percent": 80}]


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


def test_set_run_profile_steps_rejects_leading_break(pm):
    """[PM-24] Q17/RP-021a: the manager-layer save converts normalize's raise into the
    same structured refusal shape every other set_run_profile_steps failure uses,
    rather than letting a raw exception escape the manager boundary."""
    _seed_run_profile(pm)
    out = pm.set_run_profile_steps(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1", steps=[
        {"type": "charge_wait", "target_battery_percent": 95},
        {"type": "room_group", "rooms": [{"room_id": 1}]},
    ])
    assert out["saved"] is False and out["reason"] == "leading_break_unsupported"


def test_get_room_profiles(pm):
    """[PM-1]"""
    result = pm.get_room_profiles(vacuum_entity_id=_VAC)
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


def test_save_user_profile_derives_mop_required_but_never_path_type(pm):
    """[PM-2b] B2: a custom profile derives mop_required from clean_mode — and does
    NOT synthesize path_type.

    The derivation this used to pin (Deep→narrow / else→wide) has been removed. It was
    core computing one brand's axis out of another brand's word, and the fact that it
    could be computed at all was the evidence that path_type and clean_intensity are
    one property under two names. mop_required is a different case and stays: it reads
    the MODE, which every brand declares, and without it a deep-mop custom profile
    stored as not-mop.
    """
    deep_mop = pm.save_user_room_profile(
        label="Deep Mop", clean_mode="vacuum_mop", fan_speed="Max",
        water_level="Medium", clean_intensity="Deep", clean_passes=2,
        edge_mopping=True, profile_name="user_deepmop",
    )["profile"]
    assert deep_mop["mop_required"] is True      # mop mode (was always False)
    assert not deep_mop.get("path_type")         # nothing synthesized it from "Deep"

    quick_vac = pm.save_user_room_profile(
        label="Quick Vac", clean_mode="vacuum", fan_speed="Standard",
        water_level="Off", clean_intensity="Quick", clean_passes=1,
        edge_mopping=False, profile_name="user_quickvac",
    )["profile"]
    assert quick_vac["mop_required"] is False    # vacuum-only
    assert not quick_vac.get("path_type")


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


def test_delete_room_profile_refuses_with_referrers(pm):
    """RP-016/RF-20: a room still referencing this profile refuses the
    delete unless force=True; force deletes anyway. Rename repoints every
    referring room to the new name in the same store write."""
    _save(pm)
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {
        "1": {"room_id": 1, "name": "Kitchen", "profile_name": "user_brushes"},
    }}}}

    refused = pm.delete_room_profile(profile_name="user_brushes")
    assert refused["deleted"] is False
    assert refused["reason"] == "has_referrers"
    assert refused["referring_rooms"] == [
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "1", "name": "Kitchen"}
    ]
    # unforced refusal is non-destructive -- the profile and referrer both survive.
    assert pm.get_room_profiles(vacuum_entity_id=_VAC)["profiles"]["user_brushes"]
    assert pm._data["maps"][_VAC][_MAP]["rooms"]["1"]["profile_name"] == "user_brushes"

    forced = pm.delete_room_profile(profile_name="user_brushes", force=True)
    assert forced["deleted"] is True
    assert len(forced["referring_rooms"]) == 1


def test_rename_room_profile_repoints_referrers(pm):
    """RP-016/RF-20: rename must repoint every referring room's profile_name,
    not just the store key -- the old behaviour orphaned referrers under a
    name that no longer resolves to anything."""
    _save(pm)
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {
        "1": {"room_id": 1, "name": "Kitchen", "profile_name": "user_brushes"},
        "2": {"room_id": 2, "name": "Bath", "profile_name": "other_profile"},
    }}}}

    result = pm.rename_room_profile(profile_name="user_brushes", new_profile_name="user_renamed")
    assert result["renamed"] is True
    assert [r["room_id"] for r in result["repointed_rooms"]] == ["1"]
    rooms = pm._data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["1"]["profile_name"] == "user_renamed"
    assert rooms["2"]["profile_name"] == "other_profile"  # untouched -- different profile


def test_overwrite_room_profile_rejections(pm):
    """[PM-13] overwrite_room_profile error returns: protected name + unknown profile."""
    fields = dict(label="X", clean_mode="vacuum", fan_speed="Max", water_level="Off",
                  clean_intensity="Quick", clean_passes=1, edge_mopping=False)
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
        "water_level": "High", "edge_mopping": True}, vacuum_entity_id=_VAC)
    assert out["clean_mode"] == "vacuum"
    # The brand's own no-water word, not the literal "Off". This assigned Eufy's
    # casing for every brand — the third copy of that same defect.
    assert out["water_level"] == no_water_value(_CATALOG)
    assert out["edge_mopping"] is False


def test_a_save_does_not_re_add_an_axis_the_brand_does_not_have(pm):
    """[PM-30] A room save must not restore a field its brand declares no axis for.

    LIVE REGRESSION, found on hardware 2026-08-08. The one-shot store repair dropped
    `clean_intensity` from all ten Roborock rooms — correctly, that brand omits the axis
    from every profile — and then a plain save of every room put it straight back as `""`.
    `normalize_room_profile` always emits all nine ProfileRecord keys and this pipeline
    writes the result back, so the repair was being undone one room at a time.

    Inert on its own (empty, never dispatched, no control rendered), which is exactly why
    it would have gone unnoticed until the axis quietly existed everywhere again.
    """
    no_intensity = {
        **SYNTHETIC_BLOCK,
        "builtins": {
            name: {k: v for k, v in prof.items() if k != "clean_intensity"}
            for name, prof in SYNTHETIC_BLOCK["builtins"].items()
        },
        "custom_template": {
            k: v for k, v in SYNTHETIC_BLOCK["custom_template"].items()
            if k != "clean_intensity"
        },
    }
    register_adapter_config(_VAC, adapter_config(room_profiles=no_intensity))
    try:
        out = pm._finalize_room_update(
            {"room_id": 1, "floor_type": "hardwood", "clean_mode": "vacuum",
             "fan_speed": "SynthMid", "clean_intensity": "SynthClose"},
            vacuum_entity_id=_VAC,
        )
        assert "clean_intensity" not in out, out
        # ...and the axes the brand DOES declare are untouched.
        assert out["fan_speed"] == "SynthMid"
        assert out["clean_mode"] == "vacuum"
    finally:
        register_adapter_config(_VAC, adapter_config())


def test_a_save_keeps_every_axis_the_brand_does_have(pm):
    """[PM-30b] The other half — stripping must not reach a declared axis.

    Without this, "strip undeclared fields" could pass by stripping everything, and a
    brand that declares an intensity axis would silently lose it on every save.
    """
    out = pm._finalize_room_update(
        {"room_id": 1, "floor_type": "hardwood", "clean_mode": "vacuum",
         "fan_speed": "SynthMid", "clean_intensity": "SynthClose"},
        vacuum_entity_id=_VAC,
    )
    assert out["clean_intensity"] == "SynthClose"
    assert out["fan_speed"] == "SynthMid"


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
        room_config={"profile_name": name}, stored_profiles={},
        catalog=_CATALOG)
    room = {
        "clean_mode": eff.get("clean_mode"),
        "fan_speed": eff.get("fan_speed"),
        "water_level": eff.get("water_level"),
        "clean_intensity": eff.get("clean_intensity"),
        "clean_passes": eff.get("clean_passes", 1),
        "edge_mopping": eff.get("edge_mopping", False),
        "floor_type": "hardwood",
    }
    assert pm._match_profile_from_fields(room, vacuum_entity_id=_VAC) == name
    # an impossible pass count matches no preset → None (would be a false
    # match if normalization were still dropped)
    assert pm._match_profile_from_fields({**room, "clean_passes": 99}, vacuum_entity_id=_VAC) is None


def test_match_profile_from_fields_vacuum_room_matches_preset(pm):
    """[PM-10b] B1 regression: a plain vacuum room at a vacuum preset's exact values
    matches that preset — it must NOT fall through to "custom".

    The bug: protection forces a vacuum room's water to "Off", while the match
    candidate — resolved from a bare {profile_name} with no floor_type — carried
    the hardwood water default "Low", so "off" != "low" and NO vacuum room ever
    matched a vacuum preset. Resolving + protecting the candidate under the room's
    floor_type closes the asymmetry. Before the fix both asserts returned None.
    """
    fields = ("clean_mode", "fan_speed", "water_level", "clean_intensity",
              "clean_passes", "edge_mopping")

    def _room_at(profile_name: str) -> dict:
        """A room set to exactly what the REGISTERED brand declares for that preset.

        Built from the catalog rather than written out, so the test asks "does a room
        matching a preset match it?" instead of "does a room holding Eufy's words match
        an Eufy preset?" — the latter passes for one brand and silently stops testing
        anything the moment the registered adapter is not that brand.
        """
        declared = _CATALOG["builtins"][profile_name]
        return {"floor_type": "hardwood",
                **{k: declared[k] for k in fields if k in declared}}

    assert pm._match_profile_from_fields(
        _room_at("vacuum_quick"), vacuum_entity_id=_VAC) == "vacuum_quick"
    # vacuum_deep differs on fan/intensity/passes → matches deep, not quick.
    assert pm._match_profile_from_fields(
        _room_at("vacuum_deep"), vacuum_entity_id=_VAC) == "vacuum_deep"


# ---------------------------------------------------------------------------
# overwrite-from-room / overwrite-run-profile
# ---------------------------------------------------------------------------

def _seed_room(pm):
    pm._data["maps"] = {_VAC: {_MAP: {"rooms": {"1": {
        "room_id": 1, "name": "Kitchen", "clean_mode": "vacuum",
        "fan_speed": "Max", "water_level": "Off",
        "clean_intensity": "Quick", "floor_type": "hardwood"}}}}}


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


# ---------------------------------------------------------------------------
# stepped-run enrichment + overwrite/steps reconciliation (Defects #3/#4b/#6a/#7)
# ---------------------------------------------------------------------------

def test_overwrite_run_profile_clears_stale_steps(pm):
    """[PM-24] Defect #3: a profile that already carries a steps sequence, when
    overwritten from a NEW enabled-room set, must not keep the stale steps — the
    overwrite's rooms are what run/apply should clean. run_profile_steps prefers a
    non-empty steps list, so a carried-forward one would silently clean the OLD rooms.

    Still [] here, but note WHY it is [] since RP-021b: overwrite re-snapshots the
    CURRENT queue, and this test's queue is flat. Blanking and re-snapshotting agree
    on a flat queue and disagree on a stepped one — see
    test_overwrite_run_profile_resnapshots_a_stepped_queue.
    """
    _seed_enabled_rooms(pm)  # rooms 1, 2 enabled
    pid = pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Evening")["profile_id"]
    # give the saved profile an explicit stepped sequence over the OLD rooms
    pm.set_run_profile_steps(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid,
        steps=[{"type": "room_group", "rooms": [{"room_id": 1}]},
               {"type": "charge_wait", "target_battery_percent": 90},
               {"type": "room_group", "rooms": [{"room_id": 2}]}])
    # now the enabled set changes to a different room (7) and we overwrite
    pm._data["maps"][_VAC][_MAP]["rooms"] = {
        "7": {"room_id": 7, "name": "Office", "enabled": True, "order": 1}}
    ok = pm.overwrite_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    assert ok["overwritten"] is True
    # stale steps are gone -> run_profile_steps back-fills a single group of the NEW room
    stored = pm._get_saved_run_profile_store(vacuum_entity_id=_VAC, map_id=_MAP)[pid]
    assert stored["steps"] == []
    effective = ProfileManager.run_profile_steps(stored)
    # Room 7 stores none of the vocabulary fields, so the snapshot records them ABSENT.
    # This asserted "Max"/"Off"/"Quick" — values the room never had, minted by
    # _snapshot_room_for_run_profile's defaults. Those are Eufy's words, so a Roborock
    # room missing a field was snapshotted with a value its device does not accept, and
    # the run profile then replayed it. A snapshot records what was there.
    assert effective == [{"type": "room_group", "rooms": [{"room_id": 7, "name": "Office",
                          "profile_name": "vacuum_quick", "clean_mode": "vacuum",
                          "fan_speed": "", "water_level": "",
                          "clean_intensity": "", "clean_passes": 1,
                          "edge_mopping": False, "order": 1}]}]
    # and the enriched view reports the NEW room, not the old 1/2
    assert ok["profile"]["room_ids"] == [7]
    assert ok["profile"]["has_charge_steps"] is False


def test_overwrite_run_profile_resnapshots_a_stepped_queue(pm):
    """[PM-24b] RP-021b / #8:A4-PP-RP-2 (CRITICAL). Overwrite means "this profile now
    IS the current queue" — so when the CURRENT queue is stepped, its sequence must
    survive the save.

    It used to blank `steps` unconditionally. Overwrite is reachable from the card's
    ONLY Save button, so a save whose whole intent was a rename flattened
    "Downstairs, wait 30 min, then Upstairs" into a single pass: no wait, no charge
    stop, zone steps never cleaned — and async_save committed it. The editor opens
    such a profile COLLAPSED, so the user never saw what they lost.
    """
    _seed_enabled_rooms(pm)
    pid = pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Nightly")["profile_id"]

    stepped = [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 90},
        {"type": "room_group", "rooms": [{"room_id": 2}]},
    ]
    pm._manager.get_queue_steps.return_value = _queue_steps(steps=stepped)

    ok = pm.overwrite_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid,
                                  name="Nightly (renamed)")
    assert ok["overwritten"] is True

    stored = pm._get_saved_run_profile_store(vacuum_entity_id=_VAC, map_id=_MAP)[pid]
    assert stored["steps"] == stepped, "the stepped sequence was flattened by a rename"
    assert stored["name"] == "Nightly (renamed)"
    # The charge stop is what a flattened run silently drops, so assert it survived
    # the full read path, not just the stored blob.
    assert ok["profile"]["has_charge_steps"] is True
    assert any(s["type"] == "charge_wait" for s in ProfileManager.run_profile_steps(stored))


def test_overwrite_run_profile_takes_the_current_queue_not_the_old_steps(pm):
    """[PM-24b] The half the old blanking got RIGHT must not regress: overwrite takes
    the CURRENT queue's sequence, never the profile's previous one. A carried-forward
    stale list would clean the OLD rooms, because run_profile_steps prefers a
    non-empty steps list."""
    _seed_enabled_rooms(pm)
    pid = pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, name="Evening")["profile_id"]
    pm.set_run_profile_steps(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid,
        steps=[{"type": "room_group", "rooms": [{"room_id": 1}]},
               {"type": "charge_wait", "target_battery_percent": 90},
               {"type": "room_group", "rooms": [{"room_id": 2}]}])

    # the CURRENT queue is a different stepped plan over room 7
    pm._data["maps"][_VAC][_MAP]["rooms"] = {
        "7": {"room_id": 7, "name": "Office", "enabled": True, "order": 1}}
    # A break must sit BETWEEN groups — Q17/RP-021a drops a trailing one on read, so a
    # queue ending in `wait` would fail this test for an unrelated, correct reason.
    current = [
        {"type": "room_group", "rooms": [{"room_id": 7}]},
        {"type": "wait", "wait_minutes": 15},
        {"type": "room_group", "rooms": [{"room_id": 7}]},
    ]
    pm._manager.get_queue_steps.return_value = _queue_steps(steps=current)

    pm.overwrite_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    stored = pm._get_saved_run_profile_store(vacuum_entity_id=_VAC, map_id=_MAP)[pid]
    assert stored["steps"] == current
    assert not any(s.get("target_battery_percent") == 90 for s in stored["steps"]), \
        "the profile's OLD charge_wait survived — overwrite carried stale steps forward"


def test_has_stops_flags_sequenced_runs(pm):
    """[PM-25] Defect #4b: has_stops means "sequenced run, not a plain queue" — set by
    any break step (charge_wait/wait/zone) OR more than one room_group. It is DISTINCT from
    the charge-only has_charge_steps, and a single-group queue is NOT a stop."""
    # plain single-group queue -> not a stop, no charge
    plain = pm._enrich_saved_run_profile("a", {"name": "Q", "rooms": [{"room_id": 1}, {"room_id": 2}]})
    assert plain["has_stops"] is False and plain["has_charge_steps"] is False
    # wait-only sequence -> a stop, but NOT a charge step
    wait_only = pm._enrich_saved_run_profile("b", {"name": "W", "steps": [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "wait", "wait_minutes": 30},
        {"type": "room_group", "rooms": [{"room_id": 2}]}]})
    assert wait_only["has_stops"] is True and wait_only["has_charge_steps"] is False
    # two room_groups, no break -> a stop (multi-phase run) even with no charge/wait
    multi = pm._enrich_saved_run_profile("c", {"name": "M", "steps": [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "room_group", "rooms": [{"room_id": 2}]}]})
    assert multi["has_stops"] is True and multi["has_charge_steps"] is False
    # charge sequence -> both flags true
    charge = pm._enrich_saved_run_profile("d", {"name": "C", "steps": [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "charge_wait", "target_battery_percent": 90},
        {"type": "room_group", "rooms": [{"room_id": 2}]}]})
    assert charge["has_stops"] is True and charge["has_charge_steps"] is True
    # [PM-25a] REGRESSION: a trailing zone is the ONLY break — one room_group, so the
    # >1-group clause cannot fire and "zone" must be in the step-type tuple. This gate
    # shipped zone-less while its four siblings (manager.py:1308, run_plan.py:1348/1353,
    # core/manager.py:1647) carried it, so a rooms->zone profile presented as a flat queue.
    trailing_zone = pm._enrich_saved_run_profile("e", {"name": "Z", "steps": [
        {"type": "room_group", "rooms": [{"room_id": 1}]},
        {"type": "zone", "zone_ids": ["stove"]}]})
    assert trailing_zone["has_stops"] is True
    assert trailing_zone["has_charge_steps"] is False


def test_normalize_steps_validates_room_group_room_ids(pm):
    """[PM-26] Defect #6a: room_group entries are coerced — a bare int is wrapped, an
    unparseable room_id is dropped, and an all-malformed group is dropped entirely so
    dispatch never sees a room_id that would crash int()."""
    out = ProfileManager.normalize_run_profile_steps([
        {"type": "room_group", "rooms": [
            5,                              # bare int -> wrapped
            {"room_id": "7"},               # numeric string -> coerced to int
            {"room_id": "kitchen"},         # non-numeric -> dropped
            {"room_id": 0},                 # non-positive -> dropped
            {"name": "no id"},              # missing room_id -> dropped
        ]},
        {"type": "room_group", "rooms": [{"room_id": "bad"}, "junk", {"room_id": -3}]},  # all bad -> whole group dropped
    ])
    assert out == [{"type": "room_group", "rooms": [{"room_id": 5}, {"room_id": 7}]}]


def test_enrichment_derives_rooms_from_effective_steps(pm):
    """[PM-27] Defect #7: after a stepped edit that rewrites steps (and leaves the stale
    top-level rooms untouched), the enriched room_count/ids/names come from the EFFECTIVE
    steps, not profile["rooms"]. Legacy rooms-only profiles stay correct (single group)."""
    # profile still carries the OLD top-level rooms {1, 2}, but steps clean {3}
    profile = {
        "name": "Edited",
        "rooms": [{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Bath"}],
        "steps": [{"type": "room_group", "rooms": [{"room_id": 3, "name": "Office"}]}],
    }
    enriched = pm._enrich_saved_run_profile("p", profile)
    assert enriched["room_ids"] == [3]
    assert enriched["room_names"] == ["Office"]
    assert enriched["room_count"] == 1
    # legacy rooms-only profile: back-filled single group -> still reports its rooms
    legacy = pm._enrich_saved_run_profile("q", {
        "name": "Legacy", "rooms": [{"room_id": 4, "name": "Den"}, {"room_id": 5, "name": "Hall"}]})
    assert legacy["room_ids"] == [4, 5]
    assert legacy["room_names"] == ["Den", "Hall"]
    assert legacy["room_count"] == 2


# ---------------------------------------------------------------------------
# RP-021b #8:A4-PP-RP-1 — a stepped apply restores the profile's SAVED settings
# ---------------------------------------------------------------------------

def _seed_profile_room(pm, rid, **fields):
    room = {"room_id": rid, "name": f"Room {rid}", "enabled": True, "order": rid}
    room.update(fields)
    pm._data.setdefault("maps", {}).setdefault(_VAC, {}).setdefault(_MAP, {}) \
        .setdefault("rooms", {})[str(rid)] = room


def test_stepped_apply_restores_saved_settings_not_live_ones(pm):
    """[PM-30] RP-021b / #8:A4-PP-RP-1 (HIGH).

    A stepped profile's room_group entries are id-only by design — bare
    {"room_id": N} — because apply is supposed to restore the SETTINGS from
    profile["rooms"] and take only the sequence from steps. It didn't: every
    field read fell through to the room's CURRENT live state, so the saved
    settings (on disk the whole time, simply unread) were silently discarded.

    Save "Nightly" with the Kitchen on mop/High. Later switch the Kitchen to
    vacuum for a quick pass. Press Run Nightly: right rooms, right order, right
    charge break — and the Kitchen runs dry.
    """
    _seed_profile_room(pm, 1, clean_mode="mop", water_level="High", fan_speed="Quiet")
    _seed_profile_room(pm, 2)
    pid = pm.save_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, name="Nightly")["profile_id"]
    # a stepped sequence whose group entries are id-only, as the save side writes them
    pm.set_run_profile_steps(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid,
        steps=[{"type": "room_group", "rooms": [{"room_id": 1}]},
               {"type": "charge_wait", "target_battery_percent": 90},
               {"type": "room_group", "rooms": [{"room_id": 2}]}])

    # the user later changes the room to a dry quick pass
    pm._data["maps"][_VAC][_MAP]["rooms"]["1"].update(
        {"clean_mode": "vacuum", "water_level": "Off", "fan_speed": "Max"})

    out = pm.apply_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    assert out["applied"] is True
    room1 = pm._data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room1["clean_mode"] == "mop", "the saved mop setting was replaced by the live one"
    assert room1["water_level"] == "High"
    assert room1["fan_speed"] == "Quiet"
    assert out["unsnapshotted_room_ids"] == []


def test_stepped_apply_lets_a_per_group_override_win(pm):
    """[PM-30] The precedence has three layers and the STEP is the most specific.
    A group that carries its own clean_mode is an explicit per-phase override
    (vacuum this pass, mop the next) and must beat the profile-level snapshot —
    otherwise this fix would quietly disable the per-group settings CW-12 pins."""
    _seed_profile_room(pm, 1, clean_mode="mop", water_level="High")
    pid = pm.save_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, name="Mixed")["profile_id"]
    pm.set_run_profile_steps(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid,
        steps=[{"type": "room_group", "rooms": [{"room_id": 1, "clean_mode": "vacuum"}]},
               {"type": "charge_wait", "target_battery_percent": 90},
               {"type": "room_group", "rooms": [{"room_id": 1}]}])

    pm.apply_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    # the LAST group wins the final write (order matters); it has no override,
    # so it falls to the saved snapshot — mop.
    assert pm._data["maps"][_VAC][_MAP]["rooms"]["1"]["clean_mode"] == "mop"


def test_stepped_apply_reports_rooms_with_no_saved_snapshot(pm):
    """[PM-30] The packet's stop_condition: a profile saved before settings were
    snapshotted has nothing to restore, so those rooms keep their CURRENT
    settings — reported, never invented. 'Right rooms, wrong settings' is
    otherwise indistinguishable from a clean apply."""
    _seed_profile_room(pm, 1, clean_mode="vacuum")
    pid = pm.save_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, name="Legacy")["profile_id"]
    store = pm._get_saved_run_profile_store(vacuum_entity_id=_VAC, map_id=_MAP)
    store[pid]["rooms"] = []                       # legacy: no settings snapshot
    store[pid]["steps"] = [{"type": "room_group", "rooms": [{"room_id": 1}]},
                           {"type": "charge_wait", "target_battery_percent": 90},
                           {"type": "room_group", "rooms": [{"room_id": 1}]}]

    out = pm.apply_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid)
    assert out["applied"] is True
    assert 1 in out["unsnapshotted_room_ids"]
    # and it kept the live setting rather than fabricating one
    assert pm._data["maps"][_VAC][_MAP]["rooms"]["1"]["clean_mode"] == "vacuum"


# ---------------------------------------------------------------------------
# RP-021b #13:A5-RUNPROF-4 — the WRITE path refuses; READS stay tolerant
# ---------------------------------------------------------------------------

def _profile_for_steps(pm):
    _seed_enabled_rooms(pm)
    return pm.save_run_profile(vacuum_entity_id=_VAC, map_id=_MAP,
                               name="Stepped")["profile_id"]


@pytest.mark.parametrize("bad_step,reason_fragment", [
    ({"type": "mystery"},                                    "unknown_step_type"),
    ({"type": "charge_wait", "target_battery_percent": "x"}, "unparseable"),
    ({"type": "charge_wait", "target_battery_percent": 250}, "out_of_range"),
    ({"type": "room_group", "rooms": "not-a-list"},          "rooms_not_a_list"),
    ({"type": "zone", "zone_ids": []},                       "no_valid_zone_ids"),
    ("junk",                                                 "not_an_object"),
])
def test_set_steps_refuses_a_malformed_step(pm, bad_step, reason_fragment):
    """[PM-31] RP-021b / #13:A5-RUNPROF-4.

    The write path used to save whatever survived normalization and report
    saved: True. A YAML author who mistyped a step type or a percent got a
    success back and a profile that had quietly lost its charge stop — the robot
    then runs the whole sequence in one go and can strand mid-run instead of
    docking to charge.

    Note the 250 case: a SILENT CLAMP is a caller error too. The author asked for
    something impossible and would otherwise have been told it worked.
    """
    pid = _profile_for_steps(pm)
    out = pm.set_run_profile_steps(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id=pid,
        steps=[{"type": "room_group", "rooms": [{"room_id": 1}]},
               bad_step,
               {"type": "room_group", "rooms": [{"room_id": 2}]}])

    assert out["saved"] is False
    assert out["reason"] == "invalid_steps"
    # the refusal must NAME the offending step, not just say "something was wrong"
    reasons = " ".join(r["reason"] for r in out["rejected_steps"])
    assert reason_fragment in reasons, f"unhelpful refusal: {out['rejected_steps']}"
    assert out["rejected_steps"][0]["index"] == 1

    # ...and nothing was written
    stored = pm._get_saved_run_profile_store(vacuum_entity_id=_VAC, map_id=_MAP)[pid]
    assert not stored.get("steps")


def test_set_steps_still_saves_a_valid_sequence(pm):
    """[PM-31] The control: strictness must not refuse a legitimate sequence."""
    pid = _profile_for_steps(pm)
    steps = [{"type": "room_group", "rooms": [{"room_id": 1}]},
             {"type": "charge_wait", "target_battery_percent": 90},
             {"type": "room_group", "rooms": [{"room_id": 2}]}]
    out = pm.set_run_profile_steps(vacuum_entity_id=_VAC, map_id=_MAP,
                                   profile_id=pid, steps=steps)
    assert out["saved"] is True
    assert "rejected_steps" not in out
    assert pm._get_saved_run_profile_store(
        vacuum_entity_id=_VAC, map_id=_MAP)[pid]["steps"] == steps


def test_reads_stay_tolerant_of_a_legacy_profile(pm):
    """[PM-31] THE CONSTRAINT THIS FIX HAD TO RESPECT. Reads must never fail to
    start a profile already on disk.

    Strictness belongs only on the write path. A profile saved before validation
    existed may hold a step this build cannot parse, and refusing to READ it would
    turn a cosmetic data problem into "your saved run no longer starts". So
    run_profile_steps still drops silently — same normalizer, opposite policy.
    """
    legacy = {
        "rooms": [{"room_id": 1}],
        "steps": [
            {"type": "room_group", "rooms": [{"room_id": 1}]},
            {"type": "mystery"},                                  # unreadable
            {"type": "charge_wait", "target_battery_percent": "?"},  # unparseable
            {"type": "room_group", "rooms": [{"room_id": 2}]},
        ],
    }
    steps = ProfileManager.run_profile_steps(legacy)
    assert [s["type"] for s in steps] == ["room_group", "room_group"]

    # and the shared normalizer's public arm is unchanged for the same reason
    assert ProfileManager.normalize_run_profile_steps(legacy["steps"]) == steps


# ---------------------------------------------------------------------------
# [PM-19] ISSUE #48 — Edge Mopping must survive the save -> read round trip
# ---------------------------------------------------------------------------

def test_edge_mopping_survives_the_display_spelling_round_trip():
    """[PM-19] ptruman/#48: enable Edge Mopping, save, reopen -> it was off.

    The card writes clean_mode as a DISPLAY label ("Vacuum and mop"), not the
    canonical token. The SAVE path asked `"mop" in clean_mode` (substring — it
    matched, so the value persisted correctly, and his diagnostics confirm
    edge_mopping true on disk). The READ path asked
    `clean_mode in {"mop","vacuum_mop"}` — exact and case-SENSITIVE — decided he
    was not in a mop mode, and zeroed it on every read. Forever, silently.

    Driven with his exact stored room.
    """
    from custom_components.eufy_vacuum.profiles.room_profiles import (
        resolve_room_profile_for_room,
    )

    room = {
        "room_id": 1, "name": "Utility", "profile_name": "custom",
        "clean_mode": "Vacuum and mop", "floor_type": "laminate",
        "water_level": "Medium", "clean_intensity": "Deep",
        "edge_mopping": True, "clean_passes": 1,
    }
    resolved = resolve_room_profile_for_room(room_config=room, stored_profiles={}, catalog=_CATALOG)
    assert resolved["edge_mopping"] is True


@pytest.mark.parametrize("clean_mode,expected", [
    ("Vacuum and mop", True),    # what the card actually stores
    ("vacuum_mop", True),        # the canonical token
    ("Vacuum & mop", True),
    ("mop", True),
    ("Mop", True),               # case-sensitivity was its own half of the bug
    ("VACUUM_MOP", True),
    ("vacuum", False),           # edge mopping is meaningless without mop
    ("Vacuum", False),
])
def test_edge_mopping_predicate_accepts_every_mop_spelling(clean_mode, expected):
    """[PM-19b] the round trip must not depend on which spelling was stored."""
    from custom_components.eufy_vacuum.profiles.room_profiles import (
        resolve_room_profile_for_room,
    )

    resolved = resolve_room_profile_for_room(
        room_config={
            "room_id": 1, "profile_name": "custom", "clean_mode": clean_mode,
            "floor_type": "hardwood", "edge_mopping": True,
        },
        stored_profiles={},
        catalog=_CATALOG,
    )
    assert resolved["edge_mopping"] is expected


def test_carpet_downgrade_uses_the_same_predicate(mnt_profiles_manager=None):
    """[PM-19c] ISSUE #48, the sibling copy: a carpet room stored with the
    DISPLAY spelling must still be downgraded off mop.

    The carpet guard used the same exact/case-sensitive membership test, so it
    UNDER-fired: a carpet room stored as "Vacuum and mop" kept a mop mode with
    water and edge forced off — the invariant half-applied.
    """
    from custom_components.eufy_vacuum.profiles.room_profiles import is_mop_clean_mode

    assert is_mop_clean_mode("Vacuum and mop") is True
    assert is_mop_clean_mode("vacuum_mop") is True
    assert is_mop_clean_mode("Mop") is True
    assert is_mop_clean_mode("vacuum") is False
    assert is_mop_clean_mode("") is False
    assert is_mop_clean_mode(None) is False
