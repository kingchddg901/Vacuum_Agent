"""Phase 5 integration tests — state-change driven listener callbacks.

Coverage targets
----------------
[LS-1]  dock_events listener registers unsub when dock_status entity is declared.
[LS-2]  dock_events records an event when dock_status transitions to a trigger value.
[LS-3]  dock_events ignores state changes that don't match any trigger.
[LS-4]  dock_events ignores same-value transitions (old == new guard).
[LS-5]  job_metrics listener registers unsub when cleaning_time entity is declared.
[LS-6]  job_metrics fires without error when no active job exists.
[LS-7]  lifecycle listener registers unsub for the vacuum entity.
[LS-8]  lifecycle callback fires without error when no active job exists.
[LS-9]  path_blockers registers the room-update callback on the manager.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.listeners import (
    dock_events,
    job_metrics,
    lifecycle,
    path_blockers,
)


_VAC = "vacuum.alfred"
_MAP = "1"

_DOCK_STATUS_ENTITY = "sensor.alfred_dock_status"
_TASK_STATUS_ENTITY = "sensor.alfred_task_status"
_CLEANING_TIME_ENTITY = "sensor.alfred_cleaning_time"

_ADAPTER_WITH_DOCK = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "dock_status": _DOCK_STATUS_ENTITY,
        "task_status": _TASK_STATUS_ENTITY,
    },
    "dock_events": {
        "triggers": {
            "last_mop_wash": ["washing", "washing mop"],
            "last_dust_empty": ["emptying"],
        }
    },
}

_ADAPTER_WITH_METRICS = {
    "adapter_id": "test_metrics",
    "source": "test",
    "entities": {
        "cleaning_time": _CLEANING_TIME_ENTITY,
    },
}

_ADAPTER_LIFECYCLE = {
    "adapter_id": "test_lifecycle",
    "source": "test",
    "entities": {
        "task_status": _TASK_STATUS_ENTITY,
        "dock_status": _DOCK_STATUS_ENTITY,
    },
    "completion": {
        "task_status_value": "completed",
        "secondary_clear_sentinels": ["", "unknown", "unavailable"],
    },
}


# ---------------------------------------------------------------------------
# [LS-1] — [LS-4] dock_events
# ---------------------------------------------------------------------------

async def test_dock_events_registers_unsub_with_dock_entity(hass, manager):
    """[LS-1] dock_events stores an unsub when dock_status entity is declared."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    unsubs = hass.data[DOMAIN].get("_dock_event_unsubs", [])
    assert len(unsubs) == 1


async def test_dock_events_records_event_on_trigger_transition(hass, manager):
    """[LS-2] Transitioning dock_status to a trigger value records a dock event."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert "last_mop_wash" in dock_data


async def test_dock_events_increments_counter_on_wash(hass, manager):
    """[LS-2] mop_wash_count is incremented after a wash trigger."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert dock_data.get("mop_wash_count", 0) >= 1


async def test_dock_events_ignores_non_trigger_state(hass, manager):
    """[LS-3] State change to a value not in any trigger set records nothing."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "standby")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert "last_mop_wash" not in dock_data
    assert "last_dust_empty" not in dock_data


async def test_dock_events_ignores_same_value_transition(hass, manager):
    """[LS-4] Repeated state set to the same value fires no callback."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_events.register(hass)

    # Set to the same value — old_state == new_state guard should block recording
    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    # Should not have recorded — the guard blocks same-value transitions
    assert "last_mop_wash" not in dock_data


async def test_dock_events_records_emptying_trigger(hass, manager):
    """[LS-2] last_dust_empty is recorded when dock_status transitions to 'emptying'."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "emptying")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert "last_dust_empty" in dock_data


# ---------------------------------------------------------------------------
# [LS-5] — [LS-6] job_metrics
# ---------------------------------------------------------------------------

async def test_job_metrics_registers_unsub_with_cleaning_time_entity(hass, manager):
    """[LS-5] job_metrics stores an unsub when cleaning_time entity is declared."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_METRICS)
    hass.states.async_set(_CLEANING_TIME_ENTITY, "0")
    await hass.async_block_till_done()

    job_metrics.register(hass)

    unsubs = hass.data[DOMAIN].get("_job_metrics_unsubs", [])
    assert len(unsubs) == 1


async def test_job_metrics_no_adapter_no_unsubs(hass, manager):
    """[LS-5] job_metrics does not register unsubs when no adapter is configured."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    job_metrics.register(hass)
    unsubs = hass.data[DOMAIN].get("_job_metrics_unsubs", [])
    assert unsubs == []


async def test_job_metrics_state_change_no_active_job_no_error(hass, manager):
    """[LS-6] Firing a cleaning_time state change does not raise when no active job."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_METRICS)
    hass.states.async_set(_CLEANING_TIME_ENTITY, "0")
    await hass.async_block_till_done()

    job_metrics.register(hass)

    hass.states.async_set(_CLEANING_TIME_ENTITY, "300")
    await hass.async_block_till_done()
    # No active job — record_active_job_sensor_value is a no-op; no assertion needed
    # Just verifying the callback path runs without raising.


# ---------------------------------------------------------------------------
# [LS-7] — [LS-8] lifecycle
# ---------------------------------------------------------------------------

async def test_lifecycle_registers_unsub_for_known_vacuum(hass, manager):
    """[LS-7] lifecycle.register() stores a listener for the vacuum entity."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    lifecycle.register(hass)
    unsubs = hass.data[DOMAIN].get("_job_lifecycle_unsubs", [])
    assert len(unsubs) == 1


async def test_lifecycle_state_change_no_active_job_no_error(hass, manager):
    """[LS-8] Lifecycle entity state change does not raise when no active job."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    hass.states.async_set(_VAC, "cleaning")
    await hass.async_block_till_done()

    lifecycle.register(hass)

    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    # No active job — lifecycle processes and exits early; no assertion needed
    # Verifying the full callback path runs without raising.


async def test_lifecycle_task_status_change_no_active_job_no_error(hass, manager):
    """[LS-8] task_status state change does not raise when no active job."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    hass.states.async_set(_TASK_STATUS_ENTITY, "cleaning")
    await hass.async_block_till_done()

    lifecycle.register(hass)

    hass.states.async_set(_TASK_STATUS_ENTITY, "completed")
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [LS-9] path_blockers
# ---------------------------------------------------------------------------

async def test_path_blockers_registers_room_update_callback(hass, manager):
    """[LS-9] path_blockers.register() registers a room-update callback on manager."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)

    initial_count = len(manager._room_update_callbacks)
    path_blockers.register(hass)
    assert len(manager._room_update_callbacks) == initial_count + 1


async def test_path_blockers_remove_unregisters_callback(hass, manager):
    """[LS-9] path_blockers.remove() unregisters the room-update callback."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    path_blockers.register(hass)
    before = len(manager._room_update_callbacks)
    path_blockers.remove(hass)
    assert len(manager._room_update_callbacks) == before - 1


async def test_path_blockers_no_blocker_rooms_empty_unsubs(hass, manager):
    """[LS-9] path_blockers stores an empty unsub list when no rooms have blocker rules."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    path_blockers.register(hass)
    unsubs = hass.data[DOMAIN].get("_path_blocker_unsubs", None)
    assert unsubs == []
