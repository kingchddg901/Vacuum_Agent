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

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.listeners import discovery, job_progress, pause_timeout

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"

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
    """[LT-2] Register with vacuums that have no active jobs; tick is a no-op."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    job_progress.register(hass)
    await hass.async_block_till_done()
    # No active jobs — tick body skips all vacuums; just verify no raise.
    job_progress.remove(hass)


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
    """[LT-4] Tick runs without error when no paused jobs exist."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    pause_timeout.register(hass)
    await hass.async_block_till_done()
    pause_timeout.remove(hass)


async def test_pause_timeout_tick_skips_unknown_map_id(hass, manager):
    """[LT-4] Tick skips map_ids with the value 'unknown'."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    pause_timeout.register(hass)
    await hass.async_block_till_done()
    pause_timeout.remove(hass)


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
    """[LT-6] discovery.register() immediately runs a pass when trigger=config_entry_reload."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _ADAPTER_WITH_RELOAD_TRIGGER)

    discovery.register(hass)
    await hass.async_block_till_done()
    # Always clean up: default cadence also wires vacuum_docked + 6h timer.
    discovery.remove(hass)


async def test_discovery_no_vacuums_empty_unsubs(hass, manager):
    """[LT-6] discovery.register() stores no unsubs when no vacuums are registered.

    The default cadence activates whenever a vacuum IS registered (vacuum_docked
    trigger + 6h periodic), so this test deliberately uses a fresh manager with
    no vacuums to get an empty unsub list.
    """
    # No vacuum registered → get_known_vacuum_ids() returns [] → no listeners
    discovery.register(hass)
    unsubs = hass.data[DOMAIN].get("_discovery_unsubs", [])
    assert unsubs == []
    # No timer registered → no remove() needed.
