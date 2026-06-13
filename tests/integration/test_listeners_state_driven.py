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
[LS-10] discovery vacuum_docked callback fires a pass only on transition INTO docked.
[LS-11] discovery active_map_changed callback fires only on a real value change.
[LS-12] lifecycle active job (tracker not yet tracking) kicks off the trace-capture job.
[LS-13] lifecycle skips finalize when maybe_advance_phase advances a sequenced job.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.listeners import (
    discovery,
    dock_events,
    job_metrics,
    lifecycle,
    path_blockers,
)
from .conftest import setup_map


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


_DRY_DURATION_ENTITY = "sensor.alfred_dry_duration"

_ADAPTER_WITH_DRY = {
    "adapter_id": "test_dry",
    "source": "test",
    "entities": {
        "dock_status": _DOCK_STATUS_ENTITY,
        "dry_duration": _DRY_DURATION_ENTITY,
    },
    "dock_events": {
        "triggers": {
            "last_dry_start": ["drying"],
        }
    },
}


async def test_dock_events_captures_dry_duration_from_entity(hass, manager):
    """[LS-2] A last_dry_start trigger reads the adapter's dry_duration entity and
    records it on the dock event; an unknown/unavailable/"" reading is filtered to
    None and does NOT overwrite the previously captured duration."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DRY)
    hass.states.async_set(_DRY_DURATION_ENTITY, "1h45m")
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    # idle -> drying: reads dry_duration entity and records it on the event.
    hass.states.async_set(_DOCK_STATUS_ENTITY, "drying")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert "last_dry_start" in dock_data
    assert dock_data["last_dry_duration"] == "1h45m"

    # Sentinel-filter branch: dry_duration goes unavailable, then a fresh
    # idle -> drying transition fires. The (unknown/unavailable/"") guard passes
    # None through to record_dock_event, which must NOT overwrite the prior value.
    hass.states.async_set(_DRY_DURATION_ENTITY, "unavailable")
    hass.states.async_set(_DOCK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()
    hass.states.async_set(_DOCK_STATUS_ENTITY, "drying")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert dock_data["last_dry_duration"] == "1h45m"  # unchanged, not "unavailable"


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


async def test_lifecycle_active_starts_mapping_trace_job(hass, manager, monkeypatch):
    """[LS-12] a watched state change that finds the job in an ACTIVE lifecycle —
    with the mapping tracker not yet tracking this vacuum — kicks off the tracker's
    trace-capture job for the active rooms (lifecycle.py 186-211). get_lifecycle_state
    is stubbed to report active; its own derivation is covered in the core suite."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    setup_map(manager, _VAC, _MAP, count=1)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started", "vacuum_entity_id": _VAC, "map_id": _MAP,
        "queue_room_ids": [1],
    }
    monkeypatch.setattr(
        manager, "get_lifecycle_state",
        lambda **kwargs: {"lifecycle_state": "active_job_running"},
    )

    started: dict = {}

    class _FakeTracker:
        def __init__(self):
            self._active_job = {}

        def start_job(self, *, vacuum_entity_id, map_id, rooms):
            started["args"] = (vacuum_entity_id, map_id, rooms)

    hass.data[DOMAIN]["mapping_tracker"] = _FakeTracker()

    hass.states.async_set(_TASK_STATUS_ENTITY, "idle")
    await hass.async_block_till_done()
    lifecycle.register(hass)

    hass.states.async_set(_TASK_STATUS_ENTITY, "cleaning")
    await hass.async_block_till_done()

    assert "args" in started  # the tracker's trace-capture job was started
    assert started["args"][0] == _VAC
    assert started["args"][1] == _MAP


async def test_lifecycle_advance_phase_skips_finalize_and_saves(hass, manager, monkeypatch):
    """[LS-13] When a watched state change drives an active job to completion but
    manager.maybe_advance_phase(...) returns True (a sequenced job advancing to a
    next phase), the lifecycle handler must take the re-dispatch branch — set
    any_changes=True and continue — rather than finalizing (lifecycle.py 247-252).

    Drive it: seed a started active job already past has_observed_active_lifecycle,
    declare a task_status entity, fire task_status -> 'completed' so the completion
    check passes, stub maybe_advance_phase True and maybe_handle_external_run False
    (so the ONLY thing that can set any_changes is the advance-phase branch).
    Observable effects: finalize_learning_for_active_job is NEVER awaited, and the
    end-of-pass manager.async_save() runs (proving any_changes became True at 251).
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    setup_map(manager, _VAC, _MAP, count=1)

    # Active, already-moving job: has_observed_active_lifecycle survives
    # _normalize_active_job (setdefault), so the completion guard at 237 passes.
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started",
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "queue_room_ids": [1],
        "has_observed_active_lifecycle": True,
    }

    advance_calls: list[tuple] = []
    finalize_calls: list[tuple] = []
    save_calls: list[int] = []

    async def _advance(*, vacuum_entity_id, map_id):
        advance_calls.append((vacuum_entity_id, map_id))
        return True  # sequenced job advanced -> caller must skip finalization

    async def _no_external(*, vacuum_entity_id):
        return False  # isolate any_changes to the advance-phase branch

    async def _finalize(**kwargs):
        finalize_calls.append(kwargs)
        return None

    async def _save():
        save_calls.append(1)

    monkeypatch.setattr(manager, "maybe_advance_phase", _advance)
    monkeypatch.setattr(manager, "maybe_handle_external_run", _no_external)
    monkeypatch.setattr(manager, "finalize_learning_for_active_job", _finalize)
    monkeypatch.setattr(manager, "async_save", _save)

    hass.states.async_set(_TASK_STATUS_ENTITY, "cleaning")
    await hass.async_block_till_done()
    lifecycle.register(hass)

    # task_status -> completed: completion signals match (active_target is "" since
    # no active_cleaning_target entity is declared, which is in the clear sentinels).
    hass.states.async_set(_TASK_STATUS_ENTITY, "completed")
    await hass.async_block_till_done()

    # The advance-phase branch ran: maybe_advance_phase was consulted with this
    # vacuum/map, finalization was SKIPPED, and the end-of-pass save fired because
    # any_changes was set True at lifecycle.py:251.
    assert (_VAC, _MAP) in advance_calls
    assert finalize_calls == []  # 251 `continue` skipped the finalize path
    assert save_calls == [1]     # any_changes -> manager.async_save() ran


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


# ---------------------------------------------------------------------------
# [LS-10] — [LS-11] discovery state-driven callbacks
# ---------------------------------------------------------------------------

_ACTIVE_MAP_ENTITY = "sensor.alfred_active_map"


def _discovery_spy(monkeypatch):
    """Patch run_discovery_pass with a call-recording spy; return the call list."""
    calls: list[str] = []
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.setup.drift.run_discovery_pass",
        lambda hass, manager, vid: calls.append(vid),
    )
    return calls


async def test_discovery_fires_on_transition_into_docked(hass, manager, monkeypatch):
    """[LS-10] the vacuum_docked callback runs a pass only on a transition INTO
    docked — repeat docked->docked updates are filtered out."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "discovery": {"auto_refresh_on": ["vacuum_docked"],
                      "auto_refresh_interval_seconds": 0},
    })
    calls = _discovery_spy(monkeypatch)
    hass.states.async_set(_VAC, "cleaning")
    await hass.async_block_till_done()

    discovery.register(hass)

    # transition cleaning -> docked fires the pass
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    assert calls == [_VAC]

    # a docked -> docked attribute update does NOT fire again
    hass.states.async_set(_VAC, "docked", {"battery_level": 99})
    await hass.async_block_till_done()
    assert calls == [_VAC]

    discovery.remove(hass)


async def test_discovery_fires_on_active_map_value_change(hass, manager, monkeypatch):
    """[LS-11] the active_map_changed callback runs a pass on a real value change
    but ignores sentinel values and no-change updates."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": _ACTIVE_MAP_ENTITY},
        "discovery": {"auto_refresh_on": ["active_map_changed"],
                      "auto_refresh_interval_seconds": 0},
    })
    calls = _discovery_spy(monkeypatch)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, "6")
    await hass.async_block_till_done()

    discovery.register(hass)

    # real value change 6 -> 7 fires the pass
    hass.states.async_set(_ACTIVE_MAP_ENTITY, "7")
    await hass.async_block_till_done()
    assert calls == [_VAC]

    # a sentinel value does NOT fire
    hass.states.async_set(_ACTIVE_MAP_ENTITY, "unknown")
    await hass.async_block_till_done()
    assert calls == [_VAC]

    discovery.remove(hass)
