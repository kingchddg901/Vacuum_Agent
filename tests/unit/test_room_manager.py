"""Unit tests for rooms/room_manager — pure Python, no HA dependency."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.rooms.room_defaults import resolve_new_room_defaults
from custom_components.eufy_vacuum.rooms.room_manager import (
    _normalize_enabled_room_ids,
    build_managed_rooms,
    build_room_selection_summary,
)


#: What the Eufy adapter's declared catalog resolves to — the framework in-code catalog,
#: which Eufy declares by reference. Passed explicitly because build_managed_rooms takes
#: new_room_defaults as a REQUIRED argument: a permissive default there is precisely the
#: pattern that let every Roborock room be created with Eufy vocabulary.
_EUFY_DEFAULTS = resolve_new_room_defaults(None)


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
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(1), _disc(2), _disc(3)])
    assert set(result.keys()) == {"1", "2", "3"}


def test_build_filtered_by_enabled_room_ids():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1), _disc(2), _disc(3)],
        enabled_room_ids=[1, 3],
    )
    assert set(result.keys()) == {"1", "3"}
    assert "2" not in result


def test_build_empty_enabled_ids_excludes_all():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1), _disc(2)],
        enabled_room_ids=[],
    )
    assert result == {}


def test_build_string_enabled_room_ids_filter():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1), _disc(2)],
        enabled_room_ids=["1"],
    )
    assert set(result.keys()) == {"1"}


def test_build_defaults_for_new_room(brand):
    """A new room's settings come from the brand's DEFAULT PROFILE.

    BEHAVIOUR CHANGE, deliberate and approved. This asserted fan_speed == "Max", which was
    the hardcoded literal. But the room is simultaneously labelled profile_name
    "vacuum_quick", and that profile declares fan_speed "Standard" — so a new room claimed
    a profile it did not follow, and because resolve_room_profile_for_room lets the stored
    per-room field win, the profile was never consulted. The label had been decorative
    since it was written.

    Sourcing from the profile is what makes the label true, and is the same move that lets
    a non-Eufy brand supply its own defaults at all. Existing rooms are untouched — they
    carry stored values and nothing rewrites them.

    RP-018/CRUD-3 does not change this case: is_configured's floor_types gate
    only applies to an explicit-approval call (enabled_room_ids given) — this
    call passes neither, so it isn't asking an approval question at all and
    is_configured keeps its unconditional True (see test_build_managed_rooms
    _requires_floor_type_when_explicitly_approved for the gated case).
    """
    defaults = resolve_new_room_defaults(brand)
    profile = brand["builtins"][brand["default_profile"]]
    result = build_managed_rooms(
        new_room_defaults=defaults, discovered_rooms=[_disc(5, name="Hallway")])
    room = result["5"]
    assert room["profile_name"] == brand["default_profile"]
    assert room["fan_speed"] == profile["fan_speed"], "must match the profile it claims to be on"
    assert room["water_level"] == profile["water_level"]
    assert room["clean_intensity"] == profile.get("clean_intensity", "")
    assert room["clean_passes"] == profile["clean_passes"]
    assert room["clean_mode"] == profile["clean_mode"]
    # Framework-owned, brand-independent.
    assert room["enabled"] is True
    assert room["is_configured"] is True
    assert room["floor_type"] == "hardwood"


def test_a_new_room_agrees_with_the_profile_it_claims(brand):
    """The invariant behind the change above, stated once so it cannot silently rot.

    Whatever the catalog's default profile declares IS what a new room gets — no literal
    in build_managed_rooms gets to disagree with it.
    """
    profile = brand["builtins"][brand["default_profile"]]

    room = build_managed_rooms(
        new_room_defaults=resolve_new_room_defaults(brand), discovered_rooms=[_disc(9)],
    )["9"]

    assert room["profile_name"] == brand["default_profile"]
    for key in ("clean_mode", "fan_speed", "water_level", "clean_intensity",
                "clean_passes", "edge_mopping"):
        if key not in profile:
            continue  # a brand may decline an axis entirely (Roborock: clean_intensity)
        assert room[key] == profile[key], f"{key} disagrees with the declared profile"


def test_build_preserves_existing_fan_speed():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"fan_speed": "quiet"}},
    )
    assert result["1"]["fan_speed"] == "quiet"


def test_build_preserves_existing_color():
    """A re-save (save_managed_rooms / setup wizard) must not wipe a per-room color override."""
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"color": "#ff0000"}},
    )
    assert result["1"]["color"] == "#ff0000"


def test_build_defaults_color_none_for_new_room():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(2)])
    assert result["2"]["color"] is None


def test_build_preserves_existing_is_transition():
    """REGRESSION: a re-save must not un-mark a transition room. RoomConfig had no
    is_transition field at all, so build_managed_rooms rebuilt every room without it and
    the flag was dropped from storage — while maps/map_manager.py's parallel preserve list
    kept it. mapping/tracker.py reads it when attributing a live room."""
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"is_transition": True}},
    )
    assert result["1"]["is_transition"] is True


def test_build_defaults_is_transition_false_for_new_room():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(2)])
    assert result["2"]["is_transition"] is False


def test_build_preserves_existing_clean_passes():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"clean_passes": 2}},
    )
    assert result["1"]["clean_passes"] == 2


def test_build_preserves_existing_enabled_false():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"enabled": False}},
    )
    assert result["1"]["enabled"] is False


def test_build_floor_type_from_floor_types_arg():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        floor_types={1: "carpet_low_pile"},
    )
    assert result["1"]["floor_type"] == "carpet_low_pile"


def test_build_floor_type_string_key_lookup():
    """floor_types keyed by string room_id should also resolve."""
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(2)],
        floor_types={"2": "tile"},
    )
    assert result["2"]["floor_type"] == "tile"


def test_build_floor_types_arg_overrides_existing():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"floor_type": "marble"}},
        floor_types={1: "carpet_high_pile"},
    )
    assert result["1"]["floor_type"] == "carpet_high_pile"


def test_build_configured_at_preserved_from_existing():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,
        discovered_rooms=[_disc(1)],
        existing_rooms={"1": {"configured_at": "2024-01-01T00:00:00Z"}},
    )
    assert result["1"]["configured_at"] == "2024-01-01T00:00:00Z"


def test_build_configured_at_set_for_new_room():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(1)])
    assert result["1"]["configured_at"] is not None
    assert isinstance(result["1"]["configured_at"], str)


def test_build_room_name_from_discovered():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(7, name="Living Room")])
    assert result["7"]["name"] == "Living Room"


def test_build_map_id_from_discovered():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(1, map_id="42")])
    assert result["1"]["map_id"] == "42"


def test_build_no_discovered_rooms():
    result = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[])
    assert result == {}


# ---------------------------------------------------------------------------
# RP-018/RF-25b: slug-led carry, Q5 enablement, CRUD-3/CRUD-5
# ---------------------------------------------------------------------------

def test_build_managed_rooms_slug_led_carry_on_renumber():
    """Kitchen renumbers 16->21; a brand-new Bedroom takes over the freed id 16.
    Settings follow the SLUG, not the numeric id — Bedroom must not inherit
    Kitchen's dock/grants via id-fallback just because it now sits at 16."""
    existing = {"16": {
        "room_id": 16, "name": "Kitchen", "slug": "kitchen", "enabled": True,
        "is_dock_room": True, "grants_access_to": ["hallway"],
    }}
    discovered = [
        {"room_id": 21, "map_id": "1", "name": "Kitchen", "slug": "kitchen"},
        {"room_id": 16, "map_id": "1", "name": "Bedroom", "slug": "bedroom"},
    ]
    managed = build_managed_rooms(
        discovered_rooms=discovered, new_room_defaults=_EUFY_DEFAULTS, existing_rooms=existing,
    )
    assert managed["21"]["is_dock_room"] is True
    assert managed["21"]["grants_access_to"] == ["hallway"]
    assert managed["16"]["is_dock_room"] is False
    assert managed["16"]["grants_access_to"] == []


def test_build_managed_rooms_duplicate_stored_slug_falls_back_to_id():
    """D5 safety: a store still holding a pre-RP-015 duplicate slug must not
    let slug-led carry pick one of the two candidates arbitrarily — the
    ambiguous slug is excluded, so matching falls back to id-led (unaffected
    by the ambiguity)."""
    existing = {
        "3": {"room_id": 3, "name": "Bathroom A", "slug": "bathroom", "enabled": False},
        "7": {"room_id": 7, "name": "Bathroom B", "slug": "bathroom", "enabled": True},
    }
    discovered = [{"room_id": 3, "map_id": "1", "name": "Bathroom A", "slug": "bathroom"}]
    managed = build_managed_rooms(
        discovered_rooms=discovered, new_room_defaults=_EUFY_DEFAULTS, existing_rooms=existing,
    )
    assert managed["3"]["enabled"] is False   # id-led (its own stored entry), not slug-ambiguous


def test_build_managed_rooms_q5_first_import_enables_new_room():
    """Q5: a genuinely new room reaching build_managed_rooms with NO existing
    rooms at all for this map (first import) is enabled."""
    managed = build_managed_rooms(
        discovered_rooms=[_disc(1)], new_room_defaults=_EUFY_DEFAULTS, existing_rooms={},
    )
    assert managed["1"]["enabled"] is True


def test_build_managed_rooms_q5_incremental_disables_new_room():
    """Q5: a genuinely new room found on a map that ALREADY had rooms saved
    (incremental discovery) is added disabled — never silently into an
    already-active queue."""
    existing = {"1": {"room_id": 1, "name": "Kitchen", "slug": "kitchen", "enabled": True}}
    discovered = [
        {"room_id": 1, "map_id": "1", "name": "Kitchen", "slug": "kitchen"},
        {"room_id": 2, "map_id": "1", "name": "Office", "slug": "office"},
    ]
    managed = build_managed_rooms(
        discovered_rooms=discovered, new_room_defaults=_EUFY_DEFAULTS, existing_rooms=existing,
    )
    assert managed["1"]["enabled"] is True    # unaffected existing room
    assert managed["2"]["enabled"] is False   # genuinely new -> disabled


def test_build_managed_rooms_requires_floor_type_when_explicitly_approved():
    """CRUD-3: a room approved via enabled_room_ids but with no floor_types
    entry supplied THIS call is NOT auto-confirmed."""
    managed = build_managed_rooms(
        discovered_rooms=[_disc(5)], new_room_defaults=_EUFY_DEFAULTS, existing_rooms={},
        enabled_room_ids=[5], floor_types={},
    )
    assert managed["5"]["is_configured"] is False


def test_build_managed_rooms_floor_type_supplied_confirms():
    """CRUD-3 inverse: the same approval call, but floor_types DOES supply an
    entry for this room — is_configured is True."""
    managed = build_managed_rooms(
        discovered_rooms=[_disc(5)], new_room_defaults=_EUFY_DEFAULTS, existing_rooms={},
        enabled_room_ids=[5], floor_types={5: "tile"},
    )
    assert managed["5"]["is_configured"] is True


def test_build_managed_rooms_excludes_rejected_rooms():
    """CRUD-5: a room the user explicitly rejected (setup/drift.py's
    rejected_rooms) does not resurrect on rediscovery."""
    managed = build_managed_rooms(
        discovered_rooms=[_disc(9)], new_room_defaults=_EUFY_DEFAULTS, existing_rooms={},
        rejected_rooms={9},
    )
    assert "9" not in managed


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


# ---------------------------------------------------------------------------
# Group F: the room field list had TWO writers. They are now ONE dataclass.
# ---------------------------------------------------------------------------

def test_map_rebuild_and_room_save_agree_on_every_field():
    """[RM-F] The map rebuild and build_managed_rooms both construct through RoomConfig,
    so a field added to the dataclass reaches BOTH writers automatically.

    They had already drifted once: is_transition was preserved by the map rebuild and
    absent from RoomConfig, so a re-save silently un-marked transition rooms. Asserting
    the KEY SETS match means the next added field cannot reach only one writer.
    """
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket, rebuild_map_bucket

    saved = build_managed_rooms(
        new_room_defaults=_EUFY_DEFAULTS,discovered_rooms=[_disc(1)], existing_rooms={})["1"]

    data: dict = {}
    ensure_map_bucket(data=data, vacuum_entity_id="vacuum.alfred", map_id="1")
    rebuild_map_bucket(
        data=data,
        vacuum_entity_id="vacuum.alfred",
        map_id="1",
        discovered_rooms=[{"room_id": 1, "name": "Kitchen", "slug": "kitchen", "map_id": "1"}],
    )
    rebuilt = data["maps"]["vacuum.alfred"]["1"]["rooms"]["1"]

    assert set(saved) == set(rebuilt), (
        "the two room writers disagree on their field set — one of them will drop a field"
    )


def test_map_rebuild_preserves_approval_rather_than_stamping_it():
    """[RM-F2] The one place the two writers MUST differ: build_managed_rooms is an
    explicit user approval and stamps is_configured=True; a rebuild must PRESERVE the
    prior approval — neither auto-approving nor silently un-approving a saved room."""
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket, rebuild_map_bucket

    data: dict = {}
    bucket = ensure_map_bucket(data=data, vacuum_entity_id="vacuum.alfred", map_id="1")
    bucket["rooms"] = {"1": {"room_id": 1, "is_configured": False, "is_transition": True}}

    rebuild_map_bucket(
        data=data,
        vacuum_entity_id="vacuum.alfred",
        map_id="1",
        discovered_rooms=[{"room_id": 1, "name": "Kitchen", "slug": "kitchen", "map_id": "1"}],
    )
    room = data["maps"]["vacuum.alfred"]["1"]["rooms"]["1"]

    assert room["is_configured"] is False, "a rebuild silently auto-approved a room"
    assert room["is_transition"] is True, "a rebuild dropped the transition marking"
