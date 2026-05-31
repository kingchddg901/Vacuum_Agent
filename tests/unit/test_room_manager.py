"""Unit tests for rooms/room_manager — pure Python, no HA dependency."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.rooms.room_manager import (
    _normalize_enabled_room_ids,
    build_managed_rooms,
    build_room_selection_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disc(room_id: int, map_id: str = "1", name: str = "Room") -> dict:
    """Minimal discovered-room dict."""
    return {"room_id": room_id, "map_id": map_id, "name": name, "slug": None}


def _managed_room(
    name: str = "Room",
    enabled: bool = True,
    order: int = 1,
    floor_type: str = "hardwood",
) -> dict:
    """Minimal managed-room dict for summary tests."""
    return {
        "name": name,
        "enabled": enabled,
        "order": order,
        "floor_type": floor_type,
        "profile_name": "vacuum_quick",
        "clean_passes": 1,
        "edge_mopping": False,
        "slug": None,
    }


# ---------------------------------------------------------------------------
# _normalize_enabled_room_ids
# ---------------------------------------------------------------------------

def test_normalize_none_returns_empty_set():
    assert _normalize_enabled_room_ids(None) == set()


def test_normalize_empty_list_returns_empty_set():
    assert _normalize_enabled_room_ids([]) == set()


def test_normalize_integer_list():
    assert _normalize_enabled_room_ids([1, 2, 3]) == {1, 2, 3}


def test_normalize_string_list():
    assert _normalize_enabled_room_ids(["1", "2"]) == {1, 2}


def test_normalize_mixed_types():
    assert _normalize_enabled_room_ids([1, "2"]) == {1, 2}


def test_normalize_skips_non_numeric_values():
    assert _normalize_enabled_room_ids(["a", 1, None]) == {1}


def test_normalize_deduplicates():
    assert _normalize_enabled_room_ids([1, 1, "1"]) == {1}


# ---------------------------------------------------------------------------
# build_managed_rooms
# ---------------------------------------------------------------------------

def test_build_all_discovered_rooms_included_when_no_filter():
    result = build_managed_rooms(discovered_rooms=[_disc(1), _disc(2), _disc(3)])
    assert set(result.keys()) == {"1", "2", "3"}


def test_build_filtered_by_enabled_room_ids():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1), _disc(2), _disc(3)],
        enabled_room_ids=[1, 3],
    )
    assert set(result.keys()) == {"1", "3"}
    assert "2" not in result


def test_build_empty_enabled_ids_excludes_all():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1), _disc(2)],
        enabled_room_ids=[],
    )
    assert result == {}


def test_build_string_enabled_room_ids_filter():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1), _disc(2)],
        enabled_room_ids=["1"],
    )
    assert set(result.keys()) == {"1"}


def test_build_defaults_for_new_room():
    result = build_managed_rooms(discovered_rooms=[_disc(5, name="Hallway")])
    room = result["5"]
    assert room["fan_speed"] == "Max"
    assert room["clean_passes"] == 1
    assert room["enabled"] is True
    assert room["clean_mode"] == "vacuum"
    assert room["is_configured"] is True
    assert room["floor_type"] == "hardwood"


def test_build_preserves_existing_fan_speed():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"fan_speed": "quiet"}},
    )
    assert result["1"]["fan_speed"] == "quiet"


def test_build_preserves_existing_clean_passes():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"clean_passes": 2}},
    )
    assert result["1"]["clean_passes"] == 2


def test_build_preserves_existing_enabled_false():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"enabled": False}},
    )
    assert result["1"]["enabled"] is False


def test_build_floor_type_from_floor_types_arg():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1)],
        floor_types={1: "carpet_low_pile"},
    )
    assert result["1"]["floor_type"] == "carpet_low_pile"


def test_build_floor_type_string_key_lookup():
    """floor_types keyed by string room_id should also resolve."""
    result = build_managed_rooms(
        discovered_rooms=[_disc(2)],
        floor_types={"2": "tile"},
    )
    assert result["2"]["floor_type"] == "tile"


def test_build_floor_types_arg_overrides_existing():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"floor_type": "marble"}},
        floor_types={1: "carpet_high_pile"},
    )
    assert result["1"]["floor_type"] == "carpet_high_pile"


def test_build_configured_at_preserved_from_existing():
    result = build_managed_rooms(
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"configured_at": "2024-01-01T00:00:00Z"}},
    )
    assert result["1"]["configured_at"] == "2024-01-01T00:00:00Z"


def test_build_configured_at_set_for_new_room():
    result = build_managed_rooms(discovered_rooms=[_disc(1)])
    assert result["1"]["configured_at"] is not None
    assert isinstance(result["1"]["configured_at"], str)


def test_build_room_name_from_discovered():
    result = build_managed_rooms(discovered_rooms=[_disc(7, name="Living Room")])
    assert result["7"]["name"] == "Living Room"


def test_build_map_id_from_discovered():
    result = build_managed_rooms(discovered_rooms=[_disc(1, map_id="42")])
    assert result["1"]["map_id"] == "42"


def test_build_no_discovered_rooms():
    result = build_managed_rooms(discovered_rooms=[])
    assert result == {}


# ---------------------------------------------------------------------------
# build_room_selection_summary
# ---------------------------------------------------------------------------

def test_summary_empty_managed_rooms():
    summary = build_room_selection_summary(managed_rooms={})
    assert summary["enabled_count"] == 0
    assert summary["disabled_count"] == 0
    assert summary["enabled_rooms"] == []
    assert summary["disabled_rooms"] == []


def test_summary_splits_enabled_and_disabled():
    managed = {
        "1": _managed_room(name="Kitchen", enabled=True),
        "2": _managed_room(name="Bedroom", enabled=False),
    }
    summary = build_room_selection_summary(managed_rooms=managed)
    assert summary["enabled_count"] == 1
    assert summary["disabled_count"] == 1
    assert summary["enabled_rooms"][0]["name"] == "Kitchen"
    assert summary["disabled_rooms"][0]["name"] == "Bedroom"


def test_summary_carpet_flag_true_for_carpet_floor_type():
    managed = {"1": _managed_room(floor_type="carpet_high_pile")}
    summary = build_room_selection_summary(managed_rooms=managed)
    assert summary["enabled_rooms"][0]["carpet"] is True


def test_summary_carpet_flag_true_for_carpet_low_pile():
    managed = {"1": _managed_room(floor_type="carpet_low_pile")}
    summary = build_room_selection_summary(managed_rooms=managed)
    assert summary["enabled_rooms"][0]["carpet"] is True


def test_summary_carpet_flag_false_for_hardwood():
    managed = {"1": _managed_room(floor_type="hardwood")}
    summary = build_room_selection_summary(managed_rooms=managed)
    assert summary["enabled_rooms"][0]["carpet"] is False


def test_summary_enabled_rooms_sorted_by_order():
    managed = {
        "1": _managed_room(name="C", order=3),
        "2": _managed_room(name="A", order=1),
        "3": _managed_room(name="B", order=2),
    }
    summary = build_room_selection_summary(managed_rooms=managed)
    names = [r["name"] for r in summary["enabled_rooms"]]
    assert names == ["A", "B", "C"]


def test_summary_disabled_rooms_sorted_by_name():
    managed = {
        "1": _managed_room(name="Zebra", enabled=False),
        "2": _managed_room(name="Apple", enabled=False),
        "3": _managed_room(name="Mango", enabled=False),
    }
    summary = build_room_selection_summary(managed_rooms=managed)
    names = [r["name"] for r in summary["disabled_rooms"]]
    assert names == ["Apple", "Mango", "Zebra"]


def test_summary_room_id_is_int():
    managed = {"3": _managed_room(name="Room")}
    summary = build_room_selection_summary(managed_rooms=managed)
    assert summary["enabled_rooms"][0]["room_id"] == 3
    assert isinstance(summary["enabled_rooms"][0]["room_id"], int)
