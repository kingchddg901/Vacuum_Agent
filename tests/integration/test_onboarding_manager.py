"""Tests for onboarding/manager.py — OnboardingManager (data dict + hass).

Coverage targets
----------------
[OB-1] get_onboarding_state: rooms_needed / floor_type_needed / complete.
[OB-2] mark_rooms_discovered + confirm_floor_type mutate state.
[OB-3] check_for_new_rooms: grown segment count → True; no state → False.
[OB-3b] DR-ONB-2: a map that is not the ACTIVE one cannot be answered — the live
        room-list attribute has no map dimension, so it describes a different
        room set entirely.
[OB-4] get_rooms_onboarding_summary aggregates per map.
[OB-5] reset_onboarding clears the map state.
[OB-6] remap_confirmed_floor_types carries confirmations onto re-segmented ids (old->new).
[OB-6b] DR-ONB-1: a CHAINED remap ({1:2,2:3,3:4}) must not eat its own output.
[OB-6c] DR-ONB-1: a SWAP ({1:2,2:1}) must not land a confirmation on the wrong room.
[OB-6d] an unremapped confirmation survives verbatim; the dict keeps its identity.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.core import State

from custom_components.eufy_vacuum.onboarding.manager import OnboardingManager


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def hass():
    return MagicMock()


def _seed_rooms(data, rooms):
    data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {"rooms": rooms}


def test_state_progression(hass):
    """[OB-1]"""
    data: dict = {}
    ob = OnboardingManager(data, hass)
    # no rooms yet
    assert ob.get_onboarding_state(vacuum_entity_id=_VAC, map_id=_MAP)["status"] == "rooms_needed"

    _seed_rooms(data, {"1": {"enabled": True}})
    ob.mark_rooms_discovered(vacuum_entity_id=_VAC, map_id=_MAP)
    # discovered but floor type not confirmed
    assert ob.get_onboarding_state(
        vacuum_entity_id=_VAC, map_id=_MAP)["status"] == "floor_type_needed"

    ob.confirm_floor_type(vacuum_entity_id=_VAC, map_id=_MAP, room_id="1")
    state = ob.get_onboarding_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state["status"] == "complete" and state["onboarding_complete"] is True


def test_mark_and_confirm(hass):
    """[OB-2]"""
    data: dict = {}
    _seed_rooms(data, {"1": {"enabled": True}})
    ob = OnboardingManager(data, hass)
    ob.mark_rooms_discovered(vacuum_entity_id=_VAC, map_id=_MAP)
    ob.confirm_floor_type(vacuum_entity_id=_VAC, map_id=_MAP, room_id="1")
    map_ob = data["onboarding"][_VAC][_MAP]
    assert map_ob["rooms_discovered"] is True
    assert map_ob["floor_types_confirmed"]["1"] is True
    assert map_ob["room_count_at_last_check"] == 1


def test_remap_confirmed_floor_types(hass):
    """[OB-6] remap_confirmed_floor_types carries a confirmation onto a re-segmented id
    (old->new) and drops the old key — so a renumbered, already-confirmed room isn't
    re-prompted (which would block cleaning with onboarding_required after a migrate)."""
    data: dict = {}
    _seed_rooms(data, {"27": {"enabled": True}})
    ob = OnboardingManager(data, hass)
    ob.confirm_floor_type(vacuum_entity_id=_VAC, map_id=_MAP, room_id="16")
    ob.remap_confirmed_floor_types(vacuum_entity_id=_VAC, map_id=_MAP, id_remap={16: 27})
    confirmed = data["onboarding"][_VAC][_MAP]["floor_types_confirmed"]
    assert confirmed.get("27") is True   # carried to the new id
    assert "16" not in confirmed         # old id dropped


def test_check_for_new_rooms(hass):
    """[OB-3]"""
    data: dict = {}
    ob = OnboardingManager(data, hass)
    # 3 segments now, 0 at last check → grown
    # W3(a): a REAL State, not a mock one. Production reads
    # source_state.attributes.get("segments") — but a MagicMock state also
    # answers .state, .entity_id, .last_changed and anything else asked of it,
    # so a production change that began reading a different field would keep
    # this test green. State raises instead.
    hass.states.get.return_value = State(_VAC, "docked", {"segments": [1, 2, 3]})
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is True
    # no vacuum state → False
    hass.states.get.return_value = None
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is False


def test_check_for_new_rooms_refuses_a_non_active_map(hass, monkeypatch):
    """[OB-3b] DR-ONB-2: the two sides of the comparison were scoped differently.

    The stored side is per map; the live side is the vacuum entity's room-list
    attribute, which describes whichever map is LOADED. Asking about map A while
    map B is active compared A's stored count against B's rooms — a smaller
    second floor reads as "no new rooms" forever, and a larger one reports new
    rooms belonging to another map.

    The live source cannot be map-scoped, so the honest answer is "I cannot
    tell". Single-map installs — every reachable shape today — are unchanged,
    because there the active map IS the map being asked about.
    """
    from custom_components.eufy_vacuum.onboarding import manager as _ob_mod

    data: dict = {}
    ob = OnboardingManager(data, hass)
    hass.states.get.return_value = State(_VAC, "docked", {"segments": [1, 2, 3]})

    monkeypatch.setattr(
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda _hass, _vac: "OTHER_MAP",
    )
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is False

    # The SAME map still answers normally.
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda _hass, _vac: _MAP,
    )
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is True

    # Unknown active map (boot window / attribute-mode) must not start refusing
    # what it answered before.
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda _hass, _vac: None,
    )
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is True


def test_summary(hass):
    """[OB-4]"""
    data: dict = {}
    _seed_rooms(data, {"1": {"enabled": True}})
    ob = OnboardingManager(data, hass)
    summary = ob.get_rooms_onboarding_summary(vacuum_entity_id=_VAC)
    assert summary["all_complete"] is False
    assert len(summary["maps"]) == 1


def test_reset(hass):
    """[OB-5]"""
    data: dict = {}
    _seed_rooms(data, {"1": {"enabled": True}})
    ob = OnboardingManager(data, hass)
    ob.mark_rooms_discovered(vacuum_entity_id=_VAC, map_id=_MAP)
    result = ob.reset_onboarding(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["reset"] is True
    assert data["onboarding"][_VAC][_MAP]["rooms_discovered"] is False


def test_disabled_room_does_not_block_completion(hass):
    """[OB-1] A disabled+unconfirmed room is excluded from
    enabled_rooms_needing_floor_type, so onboarding reaches 'complete' once the
    only enabled room is confirmed — the disabled room never gates completion.
    """
    data: dict = {}
    ob = OnboardingManager(data, hass)
    # Map with one enabled and one disabled room, both unconfirmed.
    _seed_rooms(data, {"1": {"enabled": True}, "2": {"enabled": False}})
    ob.mark_rooms_discovered(vacuum_entity_id=_VAC, map_id=_MAP)

    # Disabled room "2" is excluded despite being unconfirmed; only "1" is needed.
    state1 = ob.get_onboarding_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state1["enabled_rooms_needing_floor_type"] == ["1"]
    assert state1["status"] == "floor_type_needed"

    # Confirming only the enabled room completes onboarding — "2" is never confirmed.
    ob.confirm_floor_type(vacuum_entity_id=_VAC, map_id=_MAP, room_id="1")
    state2 = ob.get_onboarding_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state2["status"] == "complete"
    assert state2["onboarding_complete"] is True
    assert state2["enabled_rooms_needing_floor_type"] == []


def _confirmed(data):
    return data["onboarding"][_VAC][_MAP]["floor_types_confirmed"]


def _remap_case(hass, confirm_ids, id_remap):
    data: dict = {}
    _seed_rooms(data, {str(i): {"enabled": True} for i in set(id_remap.values())})
    ob = OnboardingManager(data, hass)
    for rid in confirm_ids:
        ob.confirm_floor_type(vacuum_entity_id=_VAC, map_id=_MAP, room_id=str(rid))
    ob.remap_confirmed_floor_types(
        vacuum_entity_id=_VAC, map_id=_MAP, id_remap=id_remap
    )
    return _confirmed(data)


def test_remap_confirmed_floor_types_chain(hass):
    """[OB-6b] DR-ONB-1: a CHAINED remap must not eat its own output.

    The old loop popped from the confirmations dict and wrote back into it in the
    same pass, so a new_id that is also a later old_id consumed the entry just
    written. {1:2, 2:3, 3:4} with rooms 1-3 confirmed collapsed to {'4': True} —
    two of three confirmations destroyed. Each lost one makes the start gate
    refuse with onboarding_required until the user re-confirms a room they
    already did.

    [OB-6] never caught it because its remap ({16: 27}) is disjoint, which is the
    one shape that happens to be correct either way.
    """
    confirmed = _remap_case(hass, [1, 2, 3], {1: 2, 2: 3, 3: 4})
    assert confirmed.get("2") is True
    assert confirmed.get("3") is True
    assert confirmed.get("4") is True
    assert "1" not in confirmed


def test_remap_confirmed_floor_types_swap(hass):
    """[OB-6c] DR-ONB-1: a SWAP must not land a confirmation on the wrong room.

    {1:2, 2:1} with only room 1 confirmed used to produce {'1': True} — the
    confirmation survived in name but moved to a room the user never confirmed,
    which is worse than losing it: the gate opens on unverified floor type.
    """
    only_first = _remap_case(hass, [1], {1: 2, 2: 1})
    assert only_first.get("2") is True
    assert "1" not in only_first

    both = _remap_case(hass, [1, 2], {1: 2, 2: 1})
    assert both.get("1") is True and both.get("2") is True


def test_remap_confirmed_floor_types_leaves_unremapped_keys(hass):
    """[OB-6d] a confirmation whose id is not named in the remap survives verbatim."""
    data: dict = {}
    _seed_rooms(data, {"9": {"enabled": True}})
    ob = OnboardingManager(data, hass)
    for rid in ("5", "9"):
        ob.confirm_floor_type(vacuum_entity_id=_VAC, map_id=_MAP, room_id=rid)
    before = _confirmed(data)
    ob.remap_confirmed_floor_types(vacuum_entity_id=_VAC, map_id=_MAP, id_remap={5: 6})

    confirmed = _confirmed(data)
    assert confirmed is before, "object identity must survive (callers hold refs)"
    assert confirmed.get("6") is True     # remapped
    assert confirmed.get("9") is True     # untouched
    assert "5" not in confirmed
