"""Phase 5 integration tests — time-interval listener setup.

Coverage targets
----------------
[LT-1]  job_progress.register() wires a time-interval subscription.
[LT-2]  job_progress ticker runs without error when no active jobs exist.
[LT-3]  pause_timeout.register() wires a time-interval subscription.
[LT-4]  pause_timeout ticker runs without error when no paused jobs exist.
[LT-5]  Removing then re-registering both timers is clean.
[LT-6]  discovery.register() fires a one-shot pass when config_entry_reload is declared.

Note: every test that calls register() on a timer-based listener must also
call remove() before teardown, otherwise phac's verify_cleanup detects the
lingering timer handle and fails the test.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, call, patch

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import (
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_JOB_PROGRESS_TICK,
    EVENT_RUN_INCOMPLETE,
)
from custom_components.eufy_vacuum.listeners import discovery, job_progress, pause_timeout

from .conftest import setup_map


_VAC = "vacuum.alfred"
_VAC_B = "vacuum.bruce"
_MAP = "1"


def _collect(hass, event_type):
    """Capture every event of one type fired for the rest of the test."""
    events = []
    hass.bus.async_listen(event_type, lambda e: events.append(e))
    return events


_ADAPTER_WITH_RELOAD_TRIGGER = {
    "adapter_id": "test_disc",
    "source": "test",
    "entities": {},
    "discovery": {
        "auto_refresh_on": ["config_entry_reload"],
        "auto_refresh_interval_seconds": 0,
    },
}


# ---------------------------------------------------------------------------
# [LT-1] job_progress timer setup
# ---------------------------------------------------------------------------

async def test_job_progress_register_stores_unsub(hass, manager):
    """[LT-1] job_progress.register() stores exactly one timer unsub."""
    job_progress.register(hass)
    unsubs = hass.data[DOMAIN].get("_job_progress_unsubs", [])
    assert len(unsubs) == 1
    job_progress.remove(hass)


async def test_job_progress_register_no_manager_no_unsub(hass):
    """[LT-1] job_progress.register() stores no unsub when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    job_progress.register(hass)
    unsubs = hass.data[DOMAIN].get("_job_progress_unsubs", [])
    assert unsubs == []
    # No timer registered → no remove() needed.


# ---------------------------------------------------------------------------
# [LT-2] job_progress tick — no active jobs
# ---------------------------------------------------------------------------

async def test_job_progress_tick_no_active_jobs_no_error(hass, manager):
    """[LT-2] Register with vacuums that have no active jobs; tick is a no-op.

    register() only wires a 5-second async_track_time_interval — it runs no
    immediate pass — so the interval has to be FIRED for the tick body to
    execute at all. The no-op claim is then measured on both sides: the tick
    really did reach the seeded slot (it asked the real manager for its active
    job), and having found none in flight it did nothing further — no
    apply_job_progress_tick, no EVENT_JOB_PROGRESS_TICK.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    ticks = _collect(hass, EVENT_JOB_PROGRESS_TICK)

    with (
        patch.object(
            manager, "get_active_job", wraps=manager.get_active_job
        ) as spy_active,
        patch.object(
            manager, "apply_job_progress_tick", wraps=manager.apply_job_progress_tick
        ) as spy_apply,
    ):
        job_progress.register(hass)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
        await hass.async_block_till_done()
        job_progress.remove(hass)

    # The tick body ran: it interrogated the real manager about the real slot.
    assert spy_active.call_args_list == [call(vacuum_entity_id=_VAC, map_id=_MAP)]
    # ...and, no run being in flight, stopped there.
    spy_apply.assert_not_called()
    assert ticks == []


async def test_job_progress_tick_with_vacuum_registered(hass, manager):
    """[LT-2] Register with a known vacuum that has no active job."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    job_progress.register(hass)
    assert "_job_progress_unsubs" in hass.data[DOMAIN]
    job_progress.remove(hass)


# ---------------------------------------------------------------------------
# [LT-3] pause_timeout timer setup
# ---------------------------------------------------------------------------

async def test_pause_timeout_register_stores_unsub(hass, manager):
    """[LT-3] pause_timeout.register() stores exactly one timer unsub."""
    pause_timeout.register(hass)
    unsubs = hass.data[DOMAIN].get("_pause_timeout_unsubs", [])
    assert len(unsubs) == 1
    pause_timeout.remove(hass)


async def test_pause_timeout_register_no_manager_no_unsub(hass):
    """[LT-3] pause_timeout.register() stores no unsub when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    pause_timeout.register(hass)
    unsubs = hass.data[DOMAIN].get("_pause_timeout_unsubs", [])
    assert unsubs == []
    # No timer registered → no remove() needed.


# ---------------------------------------------------------------------------
# [LT-4] pause_timeout tick — no paused jobs
# ---------------------------------------------------------------------------

async def test_pause_timeout_tick_no_paused_jobs_no_error(hass, manager):
    """[LT-4] Tick runs without error when no paused jobs exist.

    register() wires a 1-minute interval and nothing else, so the interval is
    fired here — otherwise _handle_pause_timeout_tick / _process /
    _reap_one_slot never execute. Both reaps are then shown to have actually
    asked their question about the real slot, and to have found nothing:
    no EVENT_JOB_FINISHED, no EVENT_RUN_INCOMPLETE, no persist.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    finished = _collect(hass, EVENT_JOB_FINISHED)
    incomplete = _collect(hass, EVENT_RUN_INCOMPLETE)

    with (
        patch.object(
            manager,
            "get_paused_job_timeout_report",
            wraps=manager.get_paused_job_timeout_report,
        ) as spy_paused,
        patch.object(
            manager,
            "poll_stranded_started_job",
            wraps=manager.poll_stranded_started_job,
        ) as spy_stranded,
        # `wraps=` WITHOUT an explicit AsyncMock: patch.object autodetects an async
        # def and supplies the AsyncMock itself, matching the two spies above. The
        # explicit construction was redundant and read to the mock census as new
        # bare-mock debt in a file that had none.
        patch.object(manager, "async_save", wraps=manager.async_save) as spy_save,
    ):
        pause_timeout.register(hass)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5)
        )
        await hass.async_block_till_done()
        pause_timeout.remove(hass)

    # The tick body ran and both reaps were attempted against the real slot.
    spy_paused.assert_called_once_with(vacuum_entity_id=_VAC, map_id=_MAP)
    spy_stranded.assert_called_once_with(vacuum_entity_id=_VAC, map_id=_MAP)
    # Neither reap had anything to do, so nothing was announced or persisted.
    assert finished == []
    assert incomplete == []
    spy_save.assert_not_awaited()


async def test_pause_timeout_tick_skips_unknown_map_id(hass, manager):
    """[LT-4] Tick skips map_ids with the value 'unknown'.

    A vacuum with no maps at all is exactly how the placeholder slot arises:
    get_known_map_ids() synthesises ["unknown"] for it. A second vacuum with a
    REAL map is registered alongside so the assertion proves the guard is
    SELECTIVE — the real slot is reaped, the "unknown" one is skipped — rather
    than proving the tick merely did nothing.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC_B)
    setup_map(manager, _VAC_B, _MAP, count=2)
    # Precondition: the placeholder slot really is on the tick's iteration list.
    assert manager.get_known_map_ids(_VAC) == ["unknown"]
    assert manager.get_known_map_ids(_VAC_B) == [_MAP]

    with patch.object(
        manager,
        "get_paused_job_timeout_report",
        wraps=manager.get_paused_job_timeout_report,
    ) as spy_paused:
        pause_timeout.register(hass)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(minutes=1, seconds=5)
        )
        await hass.async_block_till_done()
        pause_timeout.remove(hass)

    reaped = [(c.kwargs["vacuum_entity_id"], c.kwargs["map_id"])
              for c in spy_paused.call_args_list]
    # The guard fired: the placeholder slot was never reaped...
    assert "unknown" not in [map_id for _vid, map_id in reaped]
    # ...while the real slot on the other vacuum was.
    assert reaped == [(_VAC_B, _MAP)]


# ---------------------------------------------------------------------------
# [LT-5] Remove + re-register is clean
# ---------------------------------------------------------------------------

async def test_job_progress_re_register_is_clean(hass, manager):
    """[LT-5] Re-registering job_progress after remove stores one unsub."""
    job_progress.register(hass)
    job_progress.remove(hass)
    job_progress.register(hass)
    unsubs = hass.data[DOMAIN].get("_job_progress_unsubs", [])
    assert len(unsubs) == 1
    job_progress.remove(hass)


async def test_pause_timeout_re_register_is_clean(hass, manager):
    """[LT-5] Re-registering pause_timeout after remove stores one unsub."""
    pause_timeout.register(hass)
    pause_timeout.remove(hass)
    pause_timeout.register(hass)
    unsubs = hass.data[DOMAIN].get("_pause_timeout_unsubs", [])
    assert len(unsubs) == 1
    pause_timeout.remove(hass)


# ---------------------------------------------------------------------------
# [LT-6] discovery — config_entry_reload one-shot
# ---------------------------------------------------------------------------

async def test_discovery_config_entry_reload_trigger_fires_pass(hass, manager):
    """[LT-6] discovery.register() immediately runs a pass when trigger=config_entry_reload.

    The declared trigger has to be shown to have TAKEN EFFECT, not merely to
    have been declared: the one-shot is wired through async_at_started (which
    fires straight away once HA is running), so the pass itself is spied on —
    the service-response source refresh, the sync pass for this vacuum, and
    the persist that follows it.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _ADAPTER_WITH_RELOAD_TRIGGER)

    with (
        patch(
            "custom_components.eufy_vacuum.setup.drift.run_discovery_pass",
            autospec=True,
        ) as spy_pass,
        patch(
            "custom_components.eufy_vacuum.rooms.source_refresh.async_refresh_room_source",
            autospec=True,
        ) as spy_refresh,
        # `wraps=` WITHOUT an explicit AsyncMock: patch.object autodetects an async
        # def and supplies the AsyncMock itself, matching the two spies above. The
        # explicit construction was redundant and read to the mock census as new
        # bare-mock debt in a file that had none.
        patch.object(manager, "async_save", wraps=manager.async_save) as spy_save,
    ):
        discovery.register(hass)
        # The adapter declares ONLY config_entry_reload (interval 0), so this
        # vacuum's single unsub is the one-shot's.
        assert list(hass.data[DOMAIN]["_discovery_unsubs"]) == [_VAC]
        assert len(hass.data[DOMAIN]["_discovery_unsubs"][_VAC]) == 1
        await hass.async_block_till_done()
        # Always clean up: default cadence also wires vacuum_docked + 6h timer.
        discovery.remove(hass)

    # The one-shot pass really ran, for THIS vacuum.
    spy_refresh.assert_awaited_once_with(hass, _VAC)
    spy_pass.assert_called_once_with(hass, manager, _VAC)
    spy_save.assert_awaited_once()


async def test_discovery_no_vacuums_empty_unsubs(hass, manager):
    """[LT-6] discovery.register() stores no unsubs when no vacuums are registered.

    The default cadence activates whenever a vacuum IS registered (vacuum_docked
    trigger + 6h periodic), so this test deliberately uses a fresh manager with
    no vacuums to get an empty unsub map.

    RP-039/RF-16: the ledger is keyed per vacuum_entity_id (dict), not a flat
    list, so remove_vacuum() can tear down one vacuum without disturbing the
    others — still empty here since no vacuum is registered.
    """
    # No vacuum registered → get_known_vacuum_ids() returns [] → no listeners
    discovery.register(hass)
    unsubs = hass.data[DOMAIN].get("_discovery_unsubs", {})
    assert unsubs == {}
    # No timer registered → no remove() needed.
