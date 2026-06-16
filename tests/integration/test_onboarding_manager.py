"""Tests for onboarding/manager.py — OnboardingManager (data dict + hass).

Coverage targets
----------------
[OB-1] get_onboarding_state: rooms_needed / floor_type_needed / complete.
[OB-2] mark_rooms_discovered + confirm_floor_type mutate state.
[OB-3] check_for_new_rooms: grown segment count → True; no state → False.
[OB-4] get_rooms_onboarding_summary aggregates per map.
[OB-5] reset_onboarding clears the map state.
[OB-6] remap_confirmed_floor_types carries confirmations onto re-segmented ids (old->new).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
    hass.states.get.return_value = MagicMock(attributes={"segments": [1, 2, 3]})
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is True
    # no vacuum state → False
    hass.states.get.return_value = None
    assert ob.check_for_new_rooms(vacuum_entity_id=_VAC, map_id=_MAP) is False


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
