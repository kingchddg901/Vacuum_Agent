"""Tests for the map-overlays sensor's user-visible attributes.

Target: custom_components/eufy_vacuum/sensor/map_overlays.py
        EufyVacuumMapOverlaysSensor.extra_state_attributes (+ native_value)

The sensor is a cheap sync reader over two stores:
  * manager._map_state_source_cache[vac]["result"]  -> the normalized map-source
    result (present/backend/current_room/rooms + the verbose geometry layers).
  * manager.data["maps"][vac][str(map_id)]["overlay_visibility"] -> per-map overlay
    toggles, resolved over OVERLAY_VISIBILITY_DEFAULTS. The active map_id is read
    from the adapter config's entities.active_map entity state via get_active_map_id.

Coverage targets
----------------
[MO-1] result PRESENT -> emits rooms (compacted to number/name/bbox/area_m2) + the
       overlay geometry layers + scalar header attrs.
[MO-2] current_room scalar is mirrored and native_value resolves the matching room
       name from the rooms list (the "current-room mark").
[MO-3] map_id truthy (via active_map entity) -> _visibility() reads
       manager.data["maps"][vac][map_id]["overlay_visibility"], merged over defaults.
[MO-4] result ABSENT (not present) -> minimal attrs incl. reason; no rooms layer.
[MO-5] no active_map / no stored bucket -> visibility falls back to all defaults.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.mapping.map_source import (
    OVERLAY_VISIBILITY_DEFAULTS,
)
from custom_components.eufy_vacuum.sensor.map_overlays import (
    EufyVacuumMapOverlaysSensor,
)

_VAC = "vacuum.alfred"
_MAP = "6"
_ACTIVE_MAP_ENTITY = "sensor.alfred_active_map"


def _present_result() -> dict:
    """A realistic 'present' map-source result the sensor normalizes."""
    return {
        "present": True,
        "backend": "eufy_map_state",
        "current_room": 2,
        "rooms": [
            {
                "number": 1,
                "name": "Kitchen",
                "bbox": [0, 0, 100, 100],
                "area_m2": 12.5,
                "pixel_count": 9999,  # internal -> must be dropped
            },
            {
                "number": 2,
                "name": "Living Room",
                "bbox": [100, 0, 200, 120],
                "area_m2": 22.0,
                "pixel_count": 12345,
            },
        ],
        "dock_anchor": [10, 10],
        "robot_anchor": [120, 40],
        "robot_heading": 90,
        "no_go": [[1, 2, 3, 4]],
        "no_mop": [],
        "walls": [[0, 0, 0, 50]],
        "zones": [],
        "obstacles": [{"x": 5, "y": 5}],
        # path is verbose + omitted entirely by the sensor
        "path": [[1, 1], [2, 2], [3, 3]],
    }


def _make_sensor(hass, manager, *, result=None, active_map=True):
    """Build the sensor with caches seeded; optionally register active_map config."""
    cache = {}
    if result is not None:
        cache[_VAC] = {"result": result}
    manager._map_state_source_cache = cache

    entities = {}
    if active_map:
        entities["active_map"] = _ACTIVE_MAP_ENTITY
        hass.states.async_set(_ACTIVE_MAP_ENTITY, _MAP)
    register_adapter_config(
        _VAC,
        {"adapter_id": "eufy", "source": "code", "entities": entities},
    )

    sensor = EufyVacuumMapOverlaysSensor(manager=manager, vacuum_entity_id=_VAC)
    sensor.hass = hass
    return sensor


def _seed_visibility(manager, overlay_visibility: dict) -> None:
    manager.data.setdefault("maps", {})
    manager.data["maps"].setdefault(_VAC, {})[_MAP] = {
        "overlay_visibility": overlay_visibility,
    }


# ---------------------------------------------------------------------------


async def test_present_result_emits_rooms_and_layers(hass, manager):
    """[MO-1] present result -> compacted rooms + geometry layers + scalars."""
    sensor = _make_sensor(hass, manager, result=_present_result())
    attrs = sensor.extra_state_attributes

    # Header scalars.
    assert attrs["vacuum_entity_id"] == _VAC
    assert attrs["present"] is True
    assert attrs["backend"] == "eufy_map_state"
    assert attrs["current_room"] == 2

    # Rooms are compacted to exactly number/name/bbox/area_m2 (pixel_count dropped).
    assert attrs["rooms"] == [
        {"number": 1, "name": "Kitchen", "bbox": [0, 0, 100, 100], "area_m2": 12.5},
        {"number": 2, "name": "Living Room", "bbox": [100, 0, 200, 120], "area_m2": 22.0},
    ]
    for room in attrs["rooms"]:
        assert "pixel_count" not in room

    # Verbose geometry layers are passed through verbatim.
    assert attrs["dock_anchor"] == [10, 10]
    assert attrs["robot_anchor"] == [120, 40]
    assert attrs["robot_heading"] == 90
    assert attrs["no_go"] == [[1, 2, 3, 4]]
    assert attrs["no_mop"] == []
    assert attrs["walls"] == [[0, 0, 0, 50]]
    assert attrs["zones"] == []
    assert attrs["obstacles"] == [{"x": 5, "y": 5}]

    # The verbose path is omitted entirely.
    assert "path" not in attrs


async def test_current_room_marks_matching_room(hass, manager):
    """[MO-2] current_room scalar mirrored; native_value resolves the room name."""
    sensor = _make_sensor(hass, manager, result=_present_result())

    assert sensor.extra_state_attributes["current_room"] == 2
    # The current-room mark: native_value picks the name of room number == current_room.
    assert sensor.native_value == "Living Room"


async def test_visibility_reads_stored_overlay_for_active_map(hass, manager):
    """[MO-3] map_id truthy -> reads manager.data['maps'][vac][map_id] overlay_visibility."""
    sensor = _make_sensor(hass, manager, result=_present_result())
    # Override two layers; unknown key must be ignored, missing keys fall to defaults.
    _seed_visibility(manager, {"no_go": True, "path": True, "bogus_key": True})

    vis = sensor.extra_state_attributes["visibility"]

    # Stored overrides win.
    assert vis["no_go"] is True
    assert vis["path"] is True
    # Unknown stored key is not leaked.
    assert "bogus_key" not in vis
    # A non-overridden layer keeps its default.
    assert vis["room_labels"] is OVERLAY_VISIBILITY_DEFAULTS["room_labels"]
    assert vis["walls"] is OVERLAY_VISIBILITY_DEFAULTS["walls"]
    # Complete, valid map (every default key present).
    assert set(vis) == set(OVERLAY_VISIBILITY_DEFAULTS)


async def test_absent_result_minimal_attrs_with_reason(hass, manager):
    """[MO-4] not-present result -> header + reason only, no rooms/layers."""
    result = {"present": False, "reason": "no_map_cached", "backend": "eufy_map_state"}
    sensor = _make_sensor(hass, manager, result=result)

    attrs = sensor.extra_state_attributes
    assert attrs["present"] is False
    assert attrs["reason"] == "no_map_cached"
    assert attrs["current_room"] is None
    # The verbose layers are NOT emitted when not present.
    assert "rooms" not in attrs
    assert "no_go" not in attrs
    # Visibility is still computed (a complete defaults map).
    assert set(attrs["visibility"]) == set(OVERLAY_VISIBILITY_DEFAULTS)

    # native_value reports the coarse availability marker.
    assert sensor.native_value == "unavailable"


async def test_visibility_defaults_when_no_active_map(hass, manager):
    """[MO-5] no active_map entity declared -> visibility = full defaults."""
    sensor = _make_sensor(hass, manager, result=_present_result(), active_map=False)
    # No maps bucket seeded at all.
    vis = sensor.extra_state_attributes["visibility"]
    assert vis == OVERLAY_VISIBILITY_DEFAULTS
