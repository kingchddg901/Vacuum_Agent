"""Phase 8 integration tests — switch entity (EufyVacuumRoomEnabledSwitch).

Coverage targets
----------------
[SW-1]  is_on=False when room data has enabled=False.
[SW-2]  is_on=True when room data has enabled=True.
[SW-3]  available=True when room exists in manager.data; False when absent.
[SW-4]  unique_id encodes vacuum, map, room_id, and 'enabled' suffix.
[SW-5]  async_turn_on writes enabled=True to manager.data.
[SW-6]  async_turn_off writes enabled=False to manager.data.
"""

from __future__ import annotations

from unittest.mock import patch

from custom_components.eufy_vacuum.switch import EufyVacuumRoomEnabledSwitch

from tests._factories import VAC as _VAC, MAP as _MAP, ENTRY_ID as _ENTRY_ID
from tests._factories import get_room_data, set_room_field
from .conftest import setup_map


def _make_switch(manager, room_id: int = 1) -> EufyVacuumRoomEnabledSwitch:
    """Build a switch entity for the given room and wire hass."""
    return EufyVacuumRoomEnabledSwitch(
        coordinator_key=_ENTRY_ID,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=room_id,
        room_data=get_room_data(manager, room_id),
    )


# ---------------------------------------------------------------------------
# [SW-1] / [SW-2] is_on reflects room enabled field
# ---------------------------------------------------------------------------

def test_switch_is_on_false_when_room_disabled(hass, manager):
    """[SW-1] is_on=False when room enabled=False."""
    setup_map(manager, _VAC, _MAP, count=2)
    set_room_field(manager, 1, enabled=False)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    assert sw.is_on is False


def test_switch_is_on_true_when_room_enabled(hass, manager):
    """[SW-2] is_on=True when room enabled=True."""
    setup_map(manager, _VAC, _MAP, count=2)
    set_room_field(manager, 1, enabled=True)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    assert sw.is_on is True


# ---------------------------------------------------------------------------
# [SW-3] available reflects room existence
# ---------------------------------------------------------------------------

def test_switch_available_true_when_room_exists(hass, manager):
    """[SW-3] available=True when room data is present in manager.data."""
    setup_map(manager, _VAC, _MAP, count=1)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    assert sw.available is True


def test_switch_available_false_when_room_absent(hass, manager):
    """[SW-3] available=False when room_id is missing from manager.data."""
    setup_map(manager, _VAC, _MAP, count=1)

    sw = _make_switch(manager, room_id=99)  # room 99 not in data
    sw.hass = hass

    assert sw.available is False


# ---------------------------------------------------------------------------
# [SW-4] unique_id format
# ---------------------------------------------------------------------------

def test_switch_unique_id_encodes_vacuum_map_room_suffix(hass, manager):
    """[SW-4] unique_id includes vacuum key, map_id, room_id, and 'enabled' suffix."""
    setup_map(manager, _VAC, _MAP, count=1)

    sw = _make_switch(manager, room_id=1)
    uid = sw.unique_id

    # Expected: vacuum_alfred_1_1_enabled
    assert "alfred" in uid
    assert _MAP in uid
    assert "1" in uid
    assert uid.endswith("enabled")


# ---------------------------------------------------------------------------
# [SW-5] / [SW-6] async_turn_on / async_turn_off write to manager.data
# ---------------------------------------------------------------------------

async def test_async_turn_on_writes_enabled_true(hass, manager):
    """[SW-5] async_turn_on sets enabled=True in manager.data for the room."""
    setup_map(manager, _VAC, _MAP, count=1)
    set_room_field(manager, 1, enabled=False)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    with patch.object(sw, "async_write_ha_state"):
        await sw.async_turn_on()

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room["enabled"] is True


async def test_async_turn_off_writes_enabled_false(hass, manager):
    """[SW-6] async_turn_off sets enabled=False in manager.data for the room."""
    setup_map(manager, _VAC, _MAP, count=1)
    set_room_field(manager, 1, enabled=True)

    sw = _make_switch(manager, room_id=1)
    sw.hass = hass

    with patch.object(sw, "async_write_ha_state"):
        await sw.async_turn_off()

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room["enabled"] is False
