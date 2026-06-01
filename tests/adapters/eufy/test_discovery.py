"""Brand-specific tests for the Eufy room-discovery functions.

Covers ``adapters/eufy/discovery.py`` — the two functions that read the
Eufy/robovac_mqtt entity surface and normalize it into the framework's room
shape:

  - ``get_active_map_id`` — reads ``sensor.{object_id}_active_map``.
  - ``discover_rooms_for_vacuum`` — reads the ``segments`` attribute off the
    vacuum entity and returns normalized room dicts.

These are Eufy-specific (the ``segments`` attribute format, the sensor naming),
so they live solo in the adapter suite rather than the brand-agnostic contract
suite. Each test drives real HA state via the ``hass`` fixture and isolates the
adapter registry.

Coverage targets
----------------
[DISC-1]  active map: sensor missing -> None.
[DISC-2]  active map: sentinel values -> None.
[DISC-3]  active map: real value -> str.
[DISC-4]  discover: vacuum state missing -> [].
[DISC-5]  discover: segments attr missing / not a list -> [].
[DISC-6]  discover: well-formed segments -> normalized room dicts.
[DISC-7]  discover: explicit map_id overrides the active-map lookup.
[DISC-8]  discover: map_id falls back to "unknown" when no active map.
[DISC-9]  discover: skips non-dict, missing-key, blank-name segments.
[DISC-10] discover: skips non-int-coercible ids and dedupes repeats.
[DISC-11] discover: registry discovery-config keys override Eufy defaults.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.adapters.eufy import discovery


_VAC = "vacuum.alfred"
_ACTIVE_MAP = "sensor.alfred_active_map"


@pytest.fixture(autouse=True)
def _isolate_registry():
    clear_registry()
    yield
    clear_registry()


# --- get_active_map_id ------------------------------------------------------


def test_active_map_missing_returns_none(hass):
    """[DISC-1]"""
    assert discovery.get_active_map_id(hass, _VAC) is None


@pytest.mark.parametrize("sentinel", ["unknown", "unavailable", "", "none", "None"])
def test_active_map_sentinels_return_none(hass, sentinel):
    """[DISC-2]"""
    hass.states.async_set(_ACTIVE_MAP, sentinel)
    assert discovery.get_active_map_id(hass, _VAC) is None


def test_active_map_real_value(hass):
    """[DISC-3]"""
    hass.states.async_set(_ACTIVE_MAP, "6")
    assert discovery.get_active_map_id(hass, _VAC) == "6"


# --- discover_rooms_for_vacuum ----------------------------------------------


def test_discover_no_vacuum_state(hass):
    """[DISC-4]"""
    assert discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []


def test_discover_segments_not_a_list(hass):
    """[DISC-5] segments attr present but not a list."""
    hass.states.async_set(_VAC, "docked", {"segments": "nope"})
    assert discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []


def test_discover_normalizes_segments(hass):
    """[DISC-6]"""
    hass.states.async_set(_ACTIVE_MAP, "6")
    hass.states.async_set(
        _VAC,
        "docked",
        {"segments": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Den"}]},
    )
    rooms = discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert rooms == [
        {"room_id": 1, "map_id": "6", "name": "Kitchen", "slug": "kitchen"},
        {"room_id": 2, "map_id": "6", "name": "Den", "slug": "den"},
    ]


def test_discover_explicit_map_id_wins(hass):
    """[DISC-7] explicit map_id beats the active-map sensor."""
    hass.states.async_set(_ACTIVE_MAP, "6")
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    rooms = discovery.discover_rooms_for_vacuum(
        hass, vacuum_entity_id=_VAC, map_id="99"
    )
    assert rooms[0]["map_id"] == "99"


def test_discover_map_id_falls_back_to_unknown(hass):
    """[DISC-8] no explicit map_id and no active-map sensor -> 'unknown'."""
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    rooms = discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert rooms[0]["map_id"] == "unknown"


def test_discover_skips_malformed_segments(hass):
    """[DISC-9] non-dict, missing id/name, and blank-name entries are dropped."""
    hass.states.async_set(
        _VAC,
        "docked",
        {
            "segments": [
                "not-a-dict",
                {"id": 1},  # missing name
                {"name": "NoId"},  # missing id
                {"id": 3, "name": "   "},  # blank after strip
                {"id": 4, "name": "Bedroom"},  # the only good one
            ]
        },
    )
    rooms = discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert [r["room_id"] for r in rooms] == [4]
    assert rooms[0]["name"] == "Bedroom"


def test_discover_skips_bad_ids_and_dedupes(hass):
    """[DISC-10] non-int-coercible ids skipped; duplicate ids kept once."""
    hass.states.async_set(
        _VAC,
        "docked",
        {
            "segments": [
                {"id": "abc", "name": "Bad"},  # not int-coercible
                {"id": 5, "name": "First"},
                {"id": 5, "name": "Duplicate"},  # same id -> dropped
                {"id": "7", "name": "StringId"},  # int-coercible string ok
            ]
        },
    )
    rooms = discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert [r["room_id"] for r in rooms] == [5, 7]
    assert rooms[0]["name"] == "First"


def test_discover_uses_registry_config_keys(hass):
    """[DISC-11] adapter discovery config overrides the Eufy default keys."""
    register_adapter_config(
        _VAC,
        {
            "adapter_id": "test",
            "source": "code",
            "entities": {},
            "dispatch": {
                "template": "generic_room_ids",
                "service_domain": "vacuum",
                "service_name": "send_command",
            },
            "discovery": {
                "room_list_attribute": "rooms",
                "room_id_key": "segment_id",
                "room_name_key": "label",
            },
        },
    )
    hass.states.async_set(
        _VAC,
        "docked",
        {"rooms": [{"segment_id": 2, "label": "Office"}]},
    )
    rooms = discovery.discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert rooms == [
        {"room_id": 2, "map_id": "unknown", "name": "Office", "slug": "office"}
    ]
