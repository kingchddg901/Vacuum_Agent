"""Phase 9 integration tests — remaining sensor entity submodules.

Coverage targets
----------------
[SR-1]  EufyVacuumDockEventSensor.native_value = None when no events recorded.
[SR-2]  EufyVacuumDockEventSensor.native_value = max timestamp when events exist.
[SR-3]  EufyVacuumDockEventSensor.extra_state_attributes includes vacuum_entity_id.
[SR-4]  EufyVacuumRoomCleaningHistorySensor.native_value = None when no history.
[SR-5]  EufyVacuumRoomCleaningHistorySensor.extra_state_attributes includes history keys.
[SR-6]  EufyVacuumRoomRuleStatusSensor.native_value = 'never' when no rule status stored.
[SR-7]  EufyVacuumRoomRuleStatusSensor.extra_state_attributes includes last_result.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.sensor.dock_event import EufyVacuumDockEventSensor
from custom_components.eufy_vacuum.sensor.room_history import EufyVacuumRoomCleaningHistorySensor
from custom_components.eufy_vacuum.sensor.room_rule_status import EufyVacuumRoomRuleStatusSensor

from tests._factories import VAC as _VAC, MAP as _MAP, ENTRY_ID as _ENTRY_ID, get_room_data
from .conftest import setup_map


def _make_room_sensor(cls, manager, hass, *, room_id: int = 1):
    """Build a room sensor entity and wire hass."""
    entity = cls(
        coordinator_key=_ENTRY_ID,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=room_id,
        room_data=get_room_data(manager, room_id),
    )
    entity.hass = hass
    return entity


# ---------------------------------------------------------------------------
# [SR-1] / [SR-2] / [SR-3] EufyVacuumDockEventSensor
# ---------------------------------------------------------------------------

def test_dock_event_sensor_native_value_none_when_no_events(manager):
    """[SR-1] native_value=None when no dock events have been recorded."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    sensor = EufyVacuumDockEventSensor(manager=manager, vacuum_entity_id=_VAC)
    assert sensor.native_value is None


def test_dock_event_sensor_native_value_max_timestamp(manager):
    """[SR-2] native_value returns the most recent event timestamp."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # Seed dock events directly into manager data.
    manager.data.setdefault("dock_events", {}).setdefault(_VAC, {}).update({
        "last_mop_wash": "2024-01-01T10:00:00",
        "last_dust_empty": "2024-01-02T12:00:00",
    })
    sensor = EufyVacuumDockEventSensor(manager=manager, vacuum_entity_id=_VAC)
    assert sensor.native_value == "2024-01-02T12:00:00"


def test_dock_event_sensor_extra_attributes_includes_vacuum_entity_id(manager):
    """[SR-3] extra_state_attributes includes vacuum_entity_id."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    sensor = EufyVacuumDockEventSensor(manager=manager, vacuum_entity_id=_VAC)
    attrs = sensor.extra_state_attributes
    assert attrs["vacuum_entity_id"] == _VAC
    assert "last_mop_wash" in attrs
    assert "last_dust_empty" in attrs
    assert "last_dry_start" in attrs


# ---------------------------------------------------------------------------
# [SR-4] / [SR-5] EufyVacuumRoomCleaningHistorySensor
# ---------------------------------------------------------------------------

def test_room_history_sensor_native_value_none_when_no_history(hass, manager):
    """[SR-4] native_value=None when no cleaning history exists for the room."""
    setup_map(manager, _VAC, _MAP, count=1)
    sensor = _make_room_sensor(EufyVacuumRoomCleaningHistorySensor, manager, hass)
    assert sensor.native_value is None


def test_room_history_sensor_native_value_returns_last_cleaned_at(hass, manager):
    """[SR-4] native_value returns last_cleaned_at when history is seeded."""
    setup_map(manager, _VAC, _MAP, count=1)
    manager.data.setdefault("room_history", {}).setdefault(_VAC, {}).setdefault(_MAP, {})
    manager.data["room_history"][_VAC][_MAP]["1"] = {
        "last_cleaned_at": "2024-06-01T09:00:00",
    }
    sensor = _make_room_sensor(EufyVacuumRoomCleaningHistorySensor, manager, hass)
    assert sensor.native_value == "2024-06-01T09:00:00"


def test_room_history_sensor_extra_attributes_include_history_fields(hass, manager):
    """[SR-5] extra_state_attributes includes expected cleaning history fields."""
    setup_map(manager, _VAC, _MAP, count=1)
    sensor = _make_room_sensor(EufyVacuumRoomCleaningHistorySensor, manager, hass)
    attrs = sensor.extra_state_attributes
    assert "last_cleaned_at" in attrs
    assert "last_vacuumed_at" in attrs
    assert "last_mopped_at" in attrs
    assert "hours_since_last_vacuum" in attrs


# ---------------------------------------------------------------------------
# [SR-6] / [SR-7] EufyVacuumRoomRuleStatusSensor
# ---------------------------------------------------------------------------

def test_room_rule_status_sensor_native_value_never_when_no_status(hass, manager):
    """[SR-6] native_value='never' when no rule/preflight status has been stored."""
    setup_map(manager, _VAC, _MAP, count=1)
    sensor = _make_room_sensor(EufyVacuumRoomRuleStatusSensor, manager, hass)
    assert sensor.native_value == "never"


def test_room_rule_status_sensor_extra_attributes_include_last_result(hass, manager):
    """[SR-7] extra_state_attributes includes last_result and evaluation fields."""
    setup_map(manager, _VAC, _MAP, count=1)
    sensor = _make_room_sensor(EufyVacuumRoomRuleStatusSensor, manager, hass)
    attrs = sensor.extra_state_attributes
    assert "last_result" in attrs
    assert "last_evaluated_at" in attrs
    assert "last_block_reason" in attrs
