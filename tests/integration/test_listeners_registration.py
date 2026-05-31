"""Phase 5 integration tests — listener register/remove guards.

Coverage targets
----------------
[LR-1]  register() returns safely when DATA_RUNTIME is absent.
[LR-2]  remove() returns safely when no unsubs are stored.
[LR-3]  register() with a manager that has no vacuums stores an unsub key.
[LR-4]  remove() after register() clears the unsub key from domain_data.

Tests cover all seven listener modules:
  lifecycle, pause_timeout, discovery, dock_events, job_metrics,
  job_progress, path_blockers
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.listeners import (
    discovery,
    dock_events,
    job_metrics,
    job_progress,
    lifecycle,
    path_blockers,
    pause_timeout,
)


_ALL_MODULES = [
    lifecycle,
    pause_timeout,
    discovery,
    dock_events,
    job_metrics,
    job_progress,
    path_blockers,
]


# ---------------------------------------------------------------------------
# [LR-1] register() guard — no manager
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", _ALL_MODULES, ids=lambda m: m.__name__.split(".")[-1])
async def test_register_no_manager_does_not_raise(hass, module):
    """[LR-1] register() returns without error when DATA_RUNTIME is absent."""
    hass.data.setdefault(DOMAIN, {})
    # DATA_RUNTIME deliberately not set
    module.register(hass)  # must not raise


# ---------------------------------------------------------------------------
# [LR-2] remove() guard — nothing registered
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", _ALL_MODULES, ids=lambda m: m.__name__.split(".")[-1])
async def test_remove_nothing_registered_does_not_raise(hass, module):
    """[LR-2] remove() returns without error when no unsubs are stored."""
    hass.data.setdefault(DOMAIN, {})
    module.remove(hass)  # must not raise


# ---------------------------------------------------------------------------
# [LR-3] register() with manager, no vacuums — stores unsub key
# ---------------------------------------------------------------------------

async def test_register_lifecycle_with_manager_no_vacuums(hass, manager):
    """[LR-3] lifecycle.register() stores its unsub key even with no vacuums."""
    lifecycle.register(hass)
    assert "_job_lifecycle_unsubs" in hass.data[DOMAIN]


async def test_register_pause_timeout_with_manager_no_vacuums(hass, manager):
    """[LR-3] pause_timeout.register() stores its unsub key even with no vacuums."""
    pause_timeout.register(hass)
    assert "_pause_timeout_unsubs" in hass.data[DOMAIN]
    pause_timeout.remove(hass)  # cancel timer so phac teardown doesn't flag it


async def test_register_job_progress_with_manager_no_vacuums(hass, manager):
    """[LR-3] job_progress.register() stores its unsub key even with no vacuums."""
    job_progress.register(hass)
    assert "_job_progress_unsubs" in hass.data[DOMAIN]
    job_progress.remove(hass)  # cancel timer so phac teardown doesn't flag it


async def test_register_dock_events_with_manager_no_vacuums(hass, manager):
    """[LR-3] dock_events.register() stores its unsub key (empty) when no vacuums."""
    dock_events.register(hass)
    assert "_dock_event_unsubs" in hass.data[DOMAIN]


async def test_register_job_metrics_with_manager_no_vacuums(hass, manager):
    """[LR-3] job_metrics.register() stores its unsub key (empty) when no vacuums."""
    job_metrics.register(hass)
    assert "_job_metrics_unsubs" in hass.data[DOMAIN]


async def test_register_discovery_with_manager_no_vacuums(hass, manager):
    """[LR-3] discovery.register() stores its unsub key (empty) when no vacuums."""
    discovery.register(hass)
    assert "_discovery_unsubs" in hass.data[DOMAIN]


async def test_register_path_blockers_with_manager_no_vacuums(hass, manager):
    """[LR-3] path_blockers.register() stores its unsub key even with no vacuums."""
    path_blockers.register(hass)
    assert "_path_blocker_unsubs" in hass.data[DOMAIN]


# ---------------------------------------------------------------------------
# [LR-4] remove() after register() clears unsub key
# ---------------------------------------------------------------------------

async def test_remove_lifecycle_clears_unsub_key(hass, manager):
    """[LR-4] lifecycle.remove() removes the unsub key from domain_data."""
    lifecycle.register(hass)
    lifecycle.remove(hass)
    assert "_job_lifecycle_unsubs" not in hass.data[DOMAIN]


async def test_remove_pause_timeout_clears_unsub_key(hass, manager):
    """[LR-4] pause_timeout.remove() removes the unsub key from domain_data."""
    pause_timeout.register(hass)
    pause_timeout.remove(hass)
    assert "_pause_timeout_unsubs" not in hass.data[DOMAIN]


async def test_remove_job_progress_clears_unsub_key(hass, manager):
    """[LR-4] job_progress.remove() removes the unsub key from domain_data."""
    job_progress.register(hass)
    job_progress.remove(hass)
    assert "_job_progress_unsubs" not in hass.data[DOMAIN]


async def test_remove_dock_events_clears_unsub_key(hass, manager):
    """[LR-4] dock_events.remove() removes the unsub key from domain_data."""
    dock_events.register(hass)
    dock_events.remove(hass)
    assert "_dock_event_unsubs" not in hass.data[DOMAIN]


async def test_remove_job_metrics_clears_unsub_key(hass, manager):
    """[LR-4] job_metrics.remove() removes the unsub key from domain_data."""
    job_metrics.register(hass)
    job_metrics.remove(hass)
    assert "_job_metrics_unsubs" not in hass.data[DOMAIN]


async def test_remove_discovery_clears_unsub_key(hass, manager):
    """[LR-4] discovery.remove() removes the unsub key from domain_data."""
    discovery.register(hass)
    discovery.remove(hass)
    assert "_discovery_unsubs" not in hass.data[DOMAIN]


async def test_remove_path_blockers_clears_unsub_key(hass, manager):
    """[LR-4] path_blockers.remove() removes the unsub key from domain_data."""
    path_blockers.register(hass)
    path_blockers.remove(hass)
    assert "_path_blocker_unsubs" not in hass.data[DOMAIN]


# ---------------------------------------------------------------------------
# Double-remove is idempotent
# ---------------------------------------------------------------------------

async def test_double_remove_does_not_raise(hass, manager):
    """remove() called twice in a row must not raise."""
    lifecycle.register(hass)
    lifecycle.remove(hass)
    lifecycle.remove(hass)  # second call — must not raise


async def test_register_is_idempotent(hass, manager):
    """Calling register() twice re-registers cleanly (remove + re-register)."""
    lifecycle.register(hass)
    lifecycle.register(hass)  # must not raise or leave orphaned unsubs
    assert "_job_lifecycle_unsubs" in hass.data[DOMAIN]
