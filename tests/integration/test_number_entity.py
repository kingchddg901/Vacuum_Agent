"""Phase 9 integration tests — number entity platform.

Coverage targets
----------------
[NE-1]  EufyVacuumRoomOrderNumber.native_value returns float(order) from room data.
[NE-2]  EufyVacuumRoomOrderNumber.native_value defaults to 0.0 when order absent.
[NE-3]  EufyVacuumRoomOrderNumber.unique_id ends with 'order' suffix.
[NE-4]  EufyVacuumRoomOrderNumber.async_set_native_value persists order to manager.data.
[NE-5]  EufyVacuumMaintenanceIntervalNumber.native_value returns default_interval when nothing stored.
[NE-6]  EufyVacuumMaintenanceIntervalNumber.native_value returns stored interval.
[NE-7]  EufyVacuumMaintenanceIntervalNumber.async_set_native_value writes to manager.data.
[NE-8]  EufyVacuumMaintenanceIntervalNumber.unique_id encodes vacuum, component, and suffix.
"""

from __future__ import annotations

from unittest.mock import patch

from custom_components.eufy_vacuum.number import (
    EufyVacuumMaintenanceIntervalNumber,
    EufyVacuumRoomOrderNumber,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"
_ENTRY_ID = "test_entry_id"
_COMPONENT = "main_brush"
_DEFAULT_INTERVAL = 200.0


def _make_order_number(manager, hass, *, room_id: int = 1) -> EufyVacuumRoomOrderNumber:
    """Build an EufyVacuumRoomOrderNumber and wire hass."""
    room_data = (
        manager.data.get("maps", {})
        .get(_VAC, {})
        .get(_MAP, {})
        .get("rooms", {})
        .get(str(room_id), {})
    )
    entity = EufyVacuumRoomOrderNumber(
        coordinator_key=_ENTRY_ID,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=room_id,
        room_data=room_data,
    )
    entity.hass = hass
    return entity


def _make_interval_number(manager) -> EufyVacuumMaintenanceIntervalNumber:
    """Build an EufyVacuumMaintenanceIntervalNumber."""
    return EufyVacuumMaintenanceIntervalNumber(
        manager=manager,
        vacuum_entity_id=_VAC,
        component=_COMPONENT,
        label="Main Brush",
        icon="mdi:brush",
        default_interval=_DEFAULT_INTERVAL,
    )


# ---------------------------------------------------------------------------
# [NE-1] / [NE-2] EufyVacuumRoomOrderNumber.native_value
# ---------------------------------------------------------------------------

def test_room_order_number_native_value_reflects_room_order(hass, manager):
    """[NE-1] native_value returns the room's current order as a float."""
    setup_map(manager, _VAC, _MAP, count=1)
    manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["order"] = 3

    entity = _make_order_number(manager, hass)
    assert entity.native_value == 3.0


def test_room_order_number_native_value_defaults_to_zero(hass, manager):
    """[NE-2] native_value defaults to 0.0 when 'order' is absent from room data."""
    setup_map(manager, _VAC, _MAP, count=1)
    manager.data["maps"][_VAC][_MAP]["rooms"]["1"].pop("order", None)

    entity = _make_order_number(manager, hass)
    assert entity.native_value == 0.0


# ---------------------------------------------------------------------------
# [NE-3] EufyVacuumRoomOrderNumber.unique_id
# ---------------------------------------------------------------------------

def test_room_order_number_unique_id_ends_with_order(hass, manager):
    """[NE-3] unique_id encodes vacuum, map, room_id, and 'order' suffix."""
    setup_map(manager, _VAC, _MAP, count=1)
    entity = _make_order_number(manager, hass)
    assert entity.unique_id.endswith("order")
    assert "alfred" in entity.unique_id
    assert _MAP in entity.unique_id


# ---------------------------------------------------------------------------
# [NE-4] EufyVacuumRoomOrderNumber.async_set_native_value
# ---------------------------------------------------------------------------

async def test_room_order_number_set_native_value_persists_order(hass, manager):
    """[NE-4] async_set_native_value writes the new order to manager.data."""
    setup_map(manager, _VAC, _MAP, count=1)
    entity = _make_order_number(manager, hass)

    with patch.object(entity, "async_write_ha_state"):
        await entity.async_set_native_value(5.0)

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room["order"] == 5


# ---------------------------------------------------------------------------
# [NE-5] / [NE-6] EufyVacuumMaintenanceIntervalNumber.native_value
# ---------------------------------------------------------------------------

def test_maintenance_interval_number_returns_default_when_nothing_stored(manager):
    """[NE-5] native_value returns default_interval when no stored interval exists."""
    entity = _make_interval_number(manager)
    assert entity.native_value == _DEFAULT_INTERVAL


def test_maintenance_interval_number_returns_stored_interval(manager):
    """[NE-6] native_value returns the stored interval when one has been saved."""
    entity = _make_interval_number(manager)
    manager.data.setdefault("maintenance", {})
    manager.data["maintenance"].setdefault(_VAC, {})
    manager.data["maintenance"][_VAC][_COMPONENT] = {"interval_hours": 150.0}

    assert entity.native_value == 150.0


# ---------------------------------------------------------------------------
# [NE-7] EufyVacuumMaintenanceIntervalNumber.async_set_native_value
# ---------------------------------------------------------------------------

async def test_maintenance_interval_number_set_native_value_writes_to_data(manager):
    """[NE-7] async_set_native_value persists the new interval to manager.data."""
    entity = _make_interval_number(manager)
    await entity.async_set_native_value(300.0)

    stored = (
        manager.data.get("maintenance", {})
        .get(_VAC, {})
        .get(_COMPONENT, {})
        .get("interval_hours")
    )
    assert stored == 300.0


# ---------------------------------------------------------------------------
# [NE-8] EufyVacuumMaintenanceIntervalNumber.unique_id
# ---------------------------------------------------------------------------

def test_maintenance_interval_number_unique_id_encodes_vacuum_and_component(manager):
    """[NE-8] unique_id includes vacuum key, component name, and interval suffix."""
    entity = _make_interval_number(manager)
    uid = entity.unique_id
    assert "alfred" in uid
    assert _COMPONENT in uid
    assert "maintenance_interval" in uid
