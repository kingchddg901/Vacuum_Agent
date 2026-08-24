"""Phase 5 integration tests — state-change driven listener callbacks.

Coverage targets
----------------
[LS-1]  dock_events listener registers unsub when dock_status entity is declared.
[LS-2]  dock_events records an event when dock_status transitions to a trigger value.
[LS-3]  dock_events ignores state changes that don't match any trigger.
[LS-4]  dock_events ignores same-value transitions (old == new guard).
[REG-1/GUARD-3] dock_events ignores old_state=None (restart/first sighting)
        and old_state unavailable/unknown -- not a known prior state, so no
        edge is recorded even when new_state is a trigger value.
[LS-5]  job_metrics listener registers unsub when cleaning_time entity is declared.
[LS-6]  job_metrics fires without error when no active job exists.
[LS-7]  lifecycle listener registers unsub for the vacuum entity.
[LS-8]  lifecycle callback fires without error when no active job exists.
[LS-9]  path_blockers registers the room-update callback on the manager.
[LS-10] discovery vacuum_docked callback fires a pass only on transition INTO docked.
[LS-11] discovery active_map_changed callback fires only on a real value change.
[LS-12] lifecycle active job (tracker not yet tracking) kicks off the trace-capture job.
[LS-13] lifecycle skips finalize when maybe_advance_phase advances a sequenced job.
[LS-14] a just-advanced sequenced phase (_phase_dispatch_pending=True) suppresses
        finalize until the watchdog confirms the device started THIS room.
[LS-15] RP-039/RF-16: the spawned _process() task is tracked and CANCELLED by
        remove(hass), not just the state-change-event unsub.
[LS-16] the issue #46 job-active observation trace is reached from the live
        lifecycle path, including for a job that never arms.
[LS-17] L11: the vacuum_docked trigger fires only on an edge from a KNOWN prior
        state. unknown/unavailable/no-prior -> docked is an ARRIVAL, not a
        transition, and firing a discovery pass there runs it at raw startup --
        the exact timing config_entry_reload is deferred through
        async_at_started to avoid.
[LS-18] L11-SIBLING: active_map_changed needs the same guard on the OLD value.
        [LS-11] already pins the NEW value against the sentinels; a restart
        supplies the sentinel on the OTHER end.
[LS-19] L11: both triggers must still fire on the genuine edges they exist for.
        A guard that fixes the startup case by never firing is the same bug
        wearing the opposite sign.
"""

from __future__ import annotations

import asyncio

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
        # REG-4: register() now gates on this per-adapter flag (default
        # False) -- explicit True here so LS-1..LS-4 keep exercising a
        # wired listener. See test_listeners_registration.py for the
        # enabled=False -> not-watched case.
        "enabled": True,
        "triggers": {
            "last_mop_wash": ["washing", "washing mop"],
            "last_dust_empty": ["emptying"],
        },
    },
}

_ADAPTER_WITH_METRICS = {
    "adapter_id": "test_metrics",
    "source": "test",
    "entities": {
        "cleaning_time": _CLEANING_TIME_ENTITY,
    },
}

_BATTERY_ENTITY = "sensor.alfred_battery"

_ADAPTER_WITH_BATTERY = {
    "adapter_id": "test_metrics_battery",
    "source": "test",
    "entities": {
        "cleaning_time": _CLEANING_TIME_ENTITY,
        "battery": _BATTERY_ENTITY,
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


async def test_dock_events_first_sighting_after_restart_not_recorded(hass, manager):
    """[REG-1/GUARD-3] old_state=None (HA restart while the dock is already
    mid-cycle, or genuinely the first-ever reading) must not be treated as a
    transition INTO the trigger state -- we don't know what the device was
    actually doing before, so recording it would fabricate a brand-new dock
    cycle on every restart/reconnect."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    # Deliberately no initial state — the dock entity does not exist yet, so
    # its very first async_set below fires with old_state=None.
    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert "last_mop_wash" not in dock_data


async def test_dock_events_unavailable_prior_state_not_recorded(hass, manager):
    """[GUARD-3] a currently-unavailable prior dock_status reading is
    likewise not a known real state — recovery from an unavailable blip must
    not be recorded as a fresh dock cycle either."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "unavailable")
    await hass.async_block_till_done()

    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
    assert "last_mop_wash" not in dock_data


async def test_dock_events_unknown_prior_state_not_recorded(hass, manager):
    """[GUARD-3] same as above for the 'unknown' HA sentinel state."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_DOCK)
    hass.states.async_set(_DOCK_STATUS_ENTITY, "unknown")
    await hass.async_block_till_done()

    dock_events.register(hass)

    hass.states.async_set(_DOCK_STATUS_ENTITY, "washing")
    await hass.async_block_till_done()

    dock_data = manager.data.get("dock_events", {}).get(_VAC, {})
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
        "enabled": True,
        "triggers": {
            "last_dry_start": ["drying"],
        },
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


async def test_job_metrics_battery_entity_watched_and_plumbed_to_sample(hass, manager):
    """RP-013e/METRICS-2/REC-5: the adapter-declared battery entity is watched
    (previously it was not — no writer for last_battery_percent existed
    anywhere), and a battery reading pushed mid-run reaches the NEXT counter
    sample (OBS-B-3's null per-room battery_delta had this as its root cause)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_BATTERY)
    setup_map(manager, _VAC, _MAP, count=1)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started", "vacuum_entity_id": _VAC, "map_id": _MAP,
        "queue_room_ids": [1],
    }
    hass.states.async_set(_BATTERY_ENTITY, "0")
    hass.states.async_set(_CLEANING_TIME_ENTITY, "0")
    await hass.async_block_till_done()

    job_metrics.register(hass)

    hass.states.async_set(_BATTERY_ENTITY, "57")
    await hass.async_block_till_done()

    job = manager.data["active_jobs"][_VAC][_MAP]
    assert job.get("last_battery_percent") == 57

    hass.states.async_set(_CLEANING_TIME_ENTITY, "300")
    await hass.async_block_till_done()

    samples = job.get("counter_samples") or []
    assert samples and samples[-1].get("battery") == 57


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


async def test_lifecycle_process_task_tracked_and_cancelled_on_remove(
    hass, manager, monkeypatch
):
    """[LS-15] The async_create_task(_process()) spawned per lifecycle state change
    is tracked in hass.data[DOMAIN]["_job_lifecycle_tasks"] and CANCELLED by
    remove(hass) -- previously remove(hass) only cancelled the state-change-event
    unsub, never the in-flight task itself, so a slow/hung _process() (mid
    maybe_handle_external_run, mid finalize, ...) kept running -- and could still
    write manager state -- after the listener was torn down."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    hass.states.async_set(_VAC, "cleaning")
    await hass.async_block_till_done()

    started = asyncio.Event()

    async def _hang(*, vacuum_entity_id):
        started.set()
        await asyncio.sleep(100)

    monkeypatch.setattr(manager, "maybe_handle_external_run", _hang)

    lifecycle.register(hass)

    hass.states.async_set(_VAC, "docked")
    await started.wait()

    tasks = hass.data[DOMAIN].get("_job_lifecycle_tasks", set())
    assert len(tasks) == 1, "the spawned _process() task was not ledgered"
    task = next(iter(tasks))
    assert not task.done()

    lifecycle.remove(hass)
    await hass.async_block_till_done()

    assert task.cancelled()
    assert hass.data[DOMAIN].get("_job_lifecycle_tasks", set()) == set()


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


async def test_lifecycle_phase_dispatch_pending_blocks_premature_finalize(hass, manager, monkeypatch):
    """[LS-14] A just-advanced sequenced phase carries _phase_dispatch_pending=True
    until the watchdog confirms the device started THIS room. While pending, the
    PREVIOUS room's lingering completion signals (a Roborock sits docked+charging
    between phases = its completion signal) must NOT finalize OR advance the new
    phase — the guard short-circuits before either branch. Regression for the live
    bug where Kitchen's dock finalized Hallway before it was ever dispatched."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    setup_map(manager, _VAC, _MAP, count=1)

    # Sequenced phase mid-advance: has_observed_active_lifecycle got re-set True by a
    # transient docked read during the settle window (the exact race), but the phase
    # is still dispatch-pending — the watchdog hasn't confirmed it actually started.
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started",
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "queue_room_ids": [1],
        "has_observed_active_lifecycle": True,
        "_phase_dispatch_pending": True,
    }

    advance_calls: list[tuple] = []
    finalize_calls: list[dict] = []

    async def _advance(*, vacuum_entity_id, map_id):
        advance_calls.append((vacuum_entity_id, map_id))
        return True

    async def _no_external(*, vacuum_entity_id):
        return False

    async def _finalize(**kwargs):
        finalize_calls.append(kwargs)
        return None

    async def _save():
        return None

    monkeypatch.setattr(manager, "maybe_advance_phase", _advance)
    monkeypatch.setattr(manager, "maybe_handle_external_run", _no_external)
    monkeypatch.setattr(manager, "finalize_learning_for_active_job", _finalize)
    monkeypatch.setattr(manager, "async_save", _save)

    hass.states.async_set(_TASK_STATUS_ENTITY, "cleaning")
    await hass.async_block_till_done()
    lifecycle.register(hass)

    # Prior room's lingering completion signal fires while the phase is pending.
    hass.states.async_set(_TASK_STATUS_ENTITY, "completed")
    await hass.async_block_till_done()

    # Suppressed BEFORE the advance/finalize branch: neither fired.
    assert advance_calls == []   # guard short-circuited at `if not should_finalize: continue`
    assert finalize_calls == []  # the prior room's dock did NOT finalize this phase


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


async def test_lifecycle_emits_job_active_observation(hass, manager, monkeypatch, caplog):
    """[LS-16] the issue #46 observation trace is actually REACHED from the live
    lifecycle path — not merely importable.

    A correct function with no reachable caller passes every unit test and every
    audit while producing nothing at runtime. job_active_signal is only worth
    anything if a real job actually writes records, so this asserts the call site,
    not the module: drive a watched state change with an active job present and
    require the record to appear.

    Deliberately placed ABOVE the arming gate in lifecycle.py, so it must fire even
    for a job that never arms — which is the #46 failure itself and precisely the
    run we most need traced.
    """
    import logging

    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_LIFECYCLE)
    setup_map(manager, _VAC, _MAP, count=1)

    # NOT armed: has_observed_active_lifecycle is absent, mirroring a #46 run.
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started",
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "queue_room_ids": [1],
    }

    async def _no_external(*, vacuum_entity_id):
        return False

    monkeypatch.setattr(manager, "maybe_handle_external_run", _no_external)

    hass.states.async_set(_TASK_STATUS_ENTITY, "cleaning")
    await hass.async_block_till_done()
    lifecycle.register(hass)

    with caplog.at_level(logging.DEBUG,
                         logger="custom_components.eufy_vacuum.decision_log"):
        hass.states.async_set(_TASK_STATUS_ENTITY, "segment_cleaning")
        await hass.async_block_till_done()

    records = [r for r in caplog.records if "job_active.observe" in r.getMessage()]
    assert records, (
        "no [job_active.observe] record reached the log from the lifecycle path — "
        "the trace would be empty on real hardware"
    )
    assert '"native"' in records[0].getMessage()


# ---------------------------------------------------------------------------
# [LS-17] - [LS-19] L11: an ARRIVAL is not a transition
# ---------------------------------------------------------------------------


def _docked_trigger_adapter():
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "discovery": {"auto_refresh_on": ["vacuum_docked"],
                      "auto_refresh_interval_seconds": 0},
    })


def _active_map_trigger_adapter():
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": _ACTIVE_MAP_ENTITY},
        "discovery": {"auto_refresh_on": ["active_map_changed"],
                      "auto_refresh_interval_seconds": 0},
    })


@pytest.mark.parametrize("prior", ["unknown", "unavailable"])
async def test_ls17_a_docked_arrival_after_restart_is_not_an_edge(
    hass, manager, monkeypatch, prior
):
    """[LS-17] RED BEFORE THE FIX.

    The predicate was `new_state == "docked" and old_state != "docked"`, under a
    comment claiming it filtered "unknown -> docked startup noise". It did not:
    "unknown" != "docked", so every one of these passed.

    This is what an HA restart looks like for a vacuum that is sitting on its dock,
    which is where most vacuums are most of the time. The pass it fired ran at RAW
    startup - before `async_at_started` - so for a service_response brand the room
    cache (hass.data, empty on restart) yielded NO rooms, and `update_drift_history`
    credited every configured room with a missing pass.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _docked_trigger_adapter()
    calls = _discovery_spy(monkeypatch)
    hass.states.async_set(_VAC, prior)
    await hass.async_block_till_done()

    discovery.register(hass)

    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()

    assert calls == [], (
        f"{prior!r} -> 'docked' is an arrival, not an edge, but it fired: {calls}"
    )
    discovery.remove(hass)


async def test_ls17_a_first_sighting_with_no_prior_state_is_not_an_edge(
    hass, manager, monkeypatch
):
    """[LS-17] RED BEFORE THE FIX, and this is the case with NO state at all.

    Distinct from the parametrised rows above: there the entity existed and read a
    sentinel; here `old_state` is None because the entity is being created for the
    first time. `None != "docked"` was equally true, so this fired too.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _docked_trigger_adapter()
    calls = _discovery_spy(monkeypatch)

    discovery.register(hass)

    # no prior async_set for _VAC at all -> old_state is None
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()

    assert calls == [], f"a first sighting fired a discovery pass: {calls}"
    discovery.remove(hass)


@pytest.mark.parametrize("prior", [None, "unknown", "unavailable"])
async def test_ls18_an_active_map_arrival_is_not_a_change(
    hass, manager, monkeypatch, prior
):
    """[LS-18] RED BEFORE THE FIX - the SAME defect one trigger over.

    `[LS-11]` pins the new value against the sentinels and reads as covering this.
    It never supplied a sentinel OLD value, which is the end a restart supplies:
    the entity is created fresh, so its first real reading is an edge from nothing.

    Found only by checking the sibling after L11 - the shape this project keeps
    hitting, where a guard that EXISTS reads as complete.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _active_map_trigger_adapter()
    calls = _discovery_spy(monkeypatch)
    if prior is not None:
        hass.states.async_set(_ACTIVE_MAP_ENTITY, prior)
        await hass.async_block_till_done()

    discovery.register(hass)

    hass.states.async_set(_ACTIVE_MAP_ENTITY, "6")
    await hass.async_block_till_done()

    assert calls == [], (
        f"{prior!r} -> '6' is an arrival, not a map change, but it fired: {calls}"
    )
    discovery.remove(hass)


async def test_ls19_the_genuine_edges_both_still_fire(hass, manager, monkeypatch):
    """[LS-19] RED IF EITHER GUARD IS WIDENED INTO A MUTE.

    The whole point of both triggers is to run a discovery pass when something real
    happens. Fixing the startup case by refusing everything would pass every test
    above and silently disable auto-discovery, which is a worse defect than the one
    being fixed and would look identical from the outside.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _docked_trigger_adapter()
    calls = _discovery_spy(monkeypatch)
    hass.states.async_set(_VAC, "cleaning")
    await hass.async_block_till_done()

    discovery.register(hass)
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()

    assert calls == [_VAC], f"a real cleaning -> docked edge did not fire: {calls}"
    discovery.remove(hass)

    # ... and the same for the map trigger, from one real value to another
    _active_map_trigger_adapter()
    map_calls = _discovery_spy(monkeypatch)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, "6")
    await hass.async_block_till_done()

    discovery.register(hass)
    hass.states.async_set(_ACTIVE_MAP_ENTITY, "7")
    await hass.async_block_till_done()

    assert map_calls == [_VAC], f"a real 6 -> 7 map change did not fire: {map_calls}"
    discovery.remove(hass)
