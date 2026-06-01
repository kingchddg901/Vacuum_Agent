"""Tests for sensor/error.py, sensor/lifecycle.py, sensor/maintenance.py —
entity property getters over mock tracker/manager sources.

Coverage targets
----------------
[ER-1]  ActiveRunError native: none / active / recovered enum.
[ER-2]  ActiveRunError attributes surface the error message.
[ER-3]  LastDeviceError native + attributes.
[ER-4]  error sensor add/remove listener + vacuum-filtered update callback.
[LC-1]  ActiveJob native: started / paused / finalized / cancelled / none.
[LC-2]  ActiveJob attributes carry the job snapshot.
[LC-3]  ActiveJob update callbacks write on a matching vacuum/map, skip otherwise.
[MN-1]  MaintenanceRemaining native: remaining hours, None when unavailable.
[MN-2]  MaintenanceRemaining interval from storage, else default.
[MN-3]  MaintenanceRemaining attributes from the cached result.
[MN-4]  _refresh_cache flips availability from source_available.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.sensor.error import (
    EufyVacuumActiveRunErrorSensor,
    EufyVacuumLastDeviceErrorSensor,
)
from custom_components.eufy_vacuum.sensor.lifecycle import EufyVacuumActiveJobSensor
from custom_components.eufy_vacuum.sensor.maintenance import (
    EufyVacuumMaintenanceRemainingSensor,
)


_VAC = "vacuum.alfred"
_MAP = "6"


# ---------------------------------------------------------------------------
# error sensors
# ---------------------------------------------------------------------------

def _active_err(latch):
    t = MagicMock()
    t.get_active_run_latch.return_value = latch
    t.add_update_listener.return_value = lambda: None
    return EufyVacuumActiveRunErrorSensor(tracker=t, vacuum_entity_id=_VAC)


@pytest.mark.parametrize("latch,expected", [
    (None, "none"),
    ({}, "none"),
    ({"current_message": "Stuck"}, "active"),
    ({"errors": [{"message": "Cliff"}]}, "recovered"),
    ({"errors": []}, "none"),
])
def test_active_run_error_native(latch, expected):
    """[ER-1]"""
    assert _active_err(latch).native_value == expected


def test_active_run_error_attrs():
    """[ER-2]"""
    s = _active_err({"current_message": "Stuck", "code": 5})
    assert s.extra_state_attributes["message"] == "Stuck"
    # recovered: message pulled from the last error entry
    s2 = _active_err({"errors": [{"message": "A"}, {"message": "B"}]})
    assert s2.extra_state_attributes["message"] == "B"
    assert _active_err(None).extra_state_attributes == {}


def test_last_device_error():
    """[ER-3]"""
    t = MagicMock()
    t.get_last_device_latch.return_value = {"message": "E70", "code": 70}
    t.add_update_listener.return_value = lambda: None
    s = EufyVacuumLastDeviceErrorSensor(tracker=t, vacuum_entity_id=_VAC)
    assert s.native_value == "E70"
    assert s.extra_state_attributes["code"] == 70
    t.get_last_device_latch.return_value = None
    assert s.native_value == "none"
    assert s.extra_state_attributes == {}


async def test_error_sensor_listener_and_callback():
    """[ER-4] add/remove listener + the vacuum-filtered threadsafe write."""
    unsub = MagicMock()
    t = MagicMock()
    t.get_active_run_latch.return_value = {}
    t.add_update_listener.return_value = unsub
    s = EufyVacuumActiveRunErrorSensor(tracker=t, vacuum_entity_id=_VAC)

    await s.async_added_to_hass()
    t.add_update_listener.assert_called_once()

    s.hass = MagicMock()
    s._on_tracker_update(_VAC)                 # matching vacuum → schedules write
    assert s.hass.loop.call_soon_threadsafe.called
    s.hass.loop.call_soon_threadsafe.reset_mock()
    s._on_tracker_update("vacuum.other")        # wrong vacuum → skipped
    assert not s.hass.loop.call_soon_threadsafe.called

    await s.async_will_remove_from_hass()
    unsub.assert_called_once()


# ---------------------------------------------------------------------------
# lifecycle sensor
# ---------------------------------------------------------------------------

def _job_sensor(job):
    m = MagicMock()
    m.get_active_job.return_value = job
    return EufyVacuumActiveJobSensor(manager=m, vacuum_entity_id=_VAC, map_id=_MAP)


@pytest.mark.parametrize("job,expected", [
    ({"status": "started"}, "started"),
    ({"status": "paused"}, "paused"),
    ({"status": "completed"}, "finalized"),
    ({"status": "completed", "finalize_summary": {"status": "cancelled"}}, "cancelled"),
    ({"status": "idle"}, "none"),
])
def test_active_job_native(job, expected):
    """[LC-1]"""
    assert _job_sensor(job).native_value == expected


def test_active_job_attrs():
    """[LC-2]"""
    s = _job_sensor({
        "status": "started", "job_id": "j1", "map_id": _MAP, "room_count": 3,
        "finalize_summary": {"status": "completed", "used_for_learning": True},
    })
    attrs = s.extra_state_attributes
    assert attrs["job_id"] == "j1"
    assert attrs["room_count"] == 3
    assert attrs["finalize_status"] == "completed"
    assert attrs["used_for_learning"] is True


def test_active_job_callbacks():
    """[LC-3]"""
    s = _job_sensor({"status": "started"})
    s.async_write_ha_state = MagicMock()
    s.hass = MagicMock()

    ev_match = MagicMock(data={"vacuum_entity_id": _VAC, "map_id": _MAP})
    ev_other = MagicMock(data={"vacuum_entity_id": "vacuum.other", "map_id": _MAP})

    s._on_room_started(ev_match)
    s._on_job_finished(ev_match)
    s._on_safety_net_tick(None)
    assert s.async_write_ha_state.call_count == 3

    s.async_write_ha_state.reset_mock()
    s._on_room_started(ev_other)      # wrong vacuum → skipped
    assert s.async_write_ha_state.call_count == 0

    # the threadsafe update routes through hass.loop.call_soon_threadsafe
    s._on_active_job_update(_VAC, _MAP)
    assert s.hass.loop.call_soon_threadsafe.called
    s.hass.loop.call_soon_threadsafe.reset_mock()
    s._on_active_job_update("vacuum.other", _MAP)  # wrong vacuum → skipped
    assert not s.hass.loop.call_soon_threadsafe.called


# ---------------------------------------------------------------------------
# maintenance sensor
# ---------------------------------------------------------------------------

def _maint(*, remaining=42.0, source_available=True, interval=None):
    m = MagicMock()
    if interval is not None:
        m.data = {"maintenance": {_VAC: {"main_brush": {"interval_hours": interval}}}}
    else:
        m.data = {"maintenance": {}}
    m.get_maintenance_remaining.return_value = {
        "remaining_hours": remaining, "source_available": source_available,
        "used_since_reset_hours": 10, "interval_hours": interval or 150,
        "current_usage_hours": 110, "reset_at_usage_hours": 100,
        "reset_at": "2026-01-01", "source_entity": "sensor.x",
    }
    return EufyVacuumMaintenanceRemainingSensor(
        manager=m, vacuum_entity_id=_VAC, component="main_brush",
        label="Main Brush", icon="mdi:brush", default_interval=150.0)


def test_maintenance_native():
    """[MN-1]"""
    s = _maint(remaining=42.0, source_available=True)
    s._refresh_cache()
    assert s.native_value == pytest.approx(42.0)
    s2 = _maint(source_available=False)
    s2._refresh_cache()
    assert s2.native_value is None


def test_maintenance_interval():
    """[MN-2]"""
    assert _maint(interval=300)._get_interval() == pytest.approx(300.0)
    assert _maint()._get_interval() == pytest.approx(150.0)  # default


def test_maintenance_attrs():
    """[MN-3]"""
    s = _maint()
    s._refresh_cache()
    attrs = s.extra_state_attributes
    assert attrs["component"] == "main_brush"
    assert attrs["interval_hours"] == 150
    assert attrs["source_entity"] == "sensor.x"


def test_maintenance_availability_flip():
    """[MN-4]"""
    s = _maint(source_available=True)
    s._refresh_cache()
    assert s._attr_available is True
    s._manager.get_maintenance_remaining.return_value = {
        "remaining_hours": None, "source_available": False}
    s._refresh_cache()
    assert s._attr_available is False
