"""Unit tests for the map-overlays sensor's state logic (map_state_source mirror).

native_value reads only manager._map_state_source_cache, so it's testable with a fake
manager (no HA). The attribute assembly + visibility lookup need hass and are covered by
the pure resolve_overlay_visibility tests + the live deploy.

[MOS-1] native_value: room-name lookup / availability markers / absent.
"""

from custom_components.eufy_vacuum.sensor.map_overlays import (
    EufyVacuumMapOverlaysSensor,
)


class _FakeManager:
    def __init__(self, result):
        self._map_state_source_cache = (
            {"vacuum.x": {"result": result}} if result is not None else {}
        )


def _sensor(result):
    return EufyVacuumMapOverlaysSensor(
        manager=_FakeManager(result), vacuum_entity_id="vacuum.x"
    )


def test_native_value_room_name():
    """[MOS-1] current_room resolves to the room's name."""
    s = _sensor({
        "present": True, "current_room": 5,
        "rooms": [{"number": 5, "name": "Kitchen"}],
    })
    assert s.native_value == "Kitchen"


def test_native_value_room_number_fallback():
    """[MOS-1b] current_room with no matching room -> 'Room N'."""
    s = _sensor({"present": True, "current_room": 9, "rooms": []})
    assert s.native_value == "Room 9"


def test_native_value_available_when_no_current_room():
    """[MOS-1c] present but no current room -> 'available'."""
    s = _sensor({"present": True, "current_room": None, "rooms": []})
    assert s.native_value == "available"


def test_native_value_unavailable():
    """[MOS-1d] absent map_state_source / empty cache -> 'unavailable'."""
    assert _sensor({"present": False, "reason": "x"}).native_value == "unavailable"
    assert _sensor(None).native_value == "unavailable"
