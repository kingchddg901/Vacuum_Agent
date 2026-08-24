"""Phase 5 integration tests — listener register/remove guards.

Coverage targets
----------------
[LR-1]  register() returns safely when DATA_RUNTIME is absent.
[LR-2]  remove() returns safely when no unsubs are stored.
[LR-3]  register() with a manager that has no vacuums stores an unsub key.
[LR-4]  remove() after register() clears the unsub key from domain_data.
[REG-4] dock_events.register() honors dock_events.enabled=False -- a vacuum
        whose adapter declares dock_status but explicitly opts out gets no
        dock-status watcher at all.

[LR-5]  _ALL_MODULES covers every module in listeners/ — the scope list is
        checked against the tree rather than trusted (it was four short).

Tests cover EVERY listener module; [LR-5] is what keeps that sentence true.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.eufy_vacuum import listeners as listeners_pkg

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from unittest.mock import create_autospec

from custom_components.eufy_vacuum.listeners import (
    clean_order_refresh,
    discovery,
    dock_events,
    entity_rename,
    job_metrics,
    job_progress,
    lifecycle,
    path_blockers,
    pause_timeout,
    pose_sampler,
    stall_capture,
)


_ALL_MODULES = [
    lifecycle,
    pause_timeout,
    discovery,
    dock_events,
    job_metrics,
    job_progress,
    path_blockers,
    stall_capture,
    pose_sampler,
    entity_rename,
    clean_order_refresh,
]


# ---------------------------------------------------------------------------
# [LR-5] the scope list is DERIVED-CHECKED, not trusted
# ---------------------------------------------------------------------------

def test_all_modules_covers_every_listener():
    """[LR-5] Every listener module appears in _ALL_MODULES.

    ⚠ THIS TEST EXISTS BECAUSE THE LIST SILENTLY ROTTED. It was written for seven
    modules and the docstring said 'all seven listener modules'; by 2026-08-24 the
    package held eleven and `__init__.py` registered all eleven, so four listeners
    — stall_capture, pose_sampler, entity_rename and clean_order_refresh — were
    outside every guard above. A hand-maintained scope list reports the same clean
    result whether it is complete or four short, which is why coverage has to come
    from the TREE and not from the list.

    It bit immediately: clean_order_refresh shipped with no `remove()` at all and
    no unwind entry, leaking a state-change subscription on every config-entry
    reload. Nothing here could go red, because the module was not in the list.
    """
    package = Path(listeners_pkg.__file__).parent
    on_disk = {
        f.stem for f in package.glob("*.py")
        if not f.stem.startswith("_")
    }
    covered = {m.__name__.rsplit(".", 1)[-1] for m in _ALL_MODULES}
    assert on_disk == covered, (
        "listeners/ and _ALL_MODULES disagree — "
        f"untested: {sorted(on_disk - covered)}, stale: {sorted(covered - on_disk)}"
    )


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
# [REG-4] register() honors dock_events.enabled=False
# ---------------------------------------------------------------------------

async def test_register_dock_events_disabled_adapter_not_watched(hass, manager):
    """[REG-4] register() honors dock_events.enabled=False -- a vacuum whose
    adapter explicitly opts out gets no dock-status watcher wired at all,
    even though it declares entities.dock_status."""
    vacuum_entity_id = "vacuum.reg4_disabled"
    manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)
    register_adapter_config(vacuum_entity_id, {
        "adapter_id": "test_reg4",
        "source": "test",
        "entities": {"dock_status": "sensor.reg4_dock_status"},
        "dock_events": {
            "enabled": False,
            "triggers": {"last_mop_wash": ["washing"]},
        },
    })
    hass.states.async_set("sensor.reg4_dock_status", "idle")
    await hass.async_block_till_done()

    dock_events.register(hass)

    unsubs = hass.data[DOMAIN].get("_dock_event_unsubs", [])
    assert unsubs == []

    # No listener means the entity is genuinely not watched — a subsequent
    # trigger-value transition records nothing.
    hass.states.async_set("sensor.reg4_dock_status", "washing")
    await hass.async_block_till_done()
    dock_data = manager.data.get("dock_events", {}).get(vacuum_entity_id, {})
    assert "last_mop_wash" not in dock_data


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


# ---------------------------------------------------------------------------
# [LR-6] clean_order_refresh actually SUBSCRIBES, and remove() actually STOPS it
# ---------------------------------------------------------------------------

_LR6_ADAPTER = {
    "adapter_id": "test_lr6",
    "source": "test",
    "device_clean_order": {
        "enabled": True,
        "read": {
            "via": "v1_debug_log",
            "command": "get_clean_sequence",
            "service": {"domain": "vacuum", "service": "send_command"},
            "source_logger": "test.lr6.protocol",
            "decoded_prefix": "Decoded V1 message result: ",
        },
    },
}


async def _lr6_setup(hass, manager):
    """A capable vacuum, parked OFF the dock, with async_read stubbed.

    The stub is autospec'd off the REAL bound method so it cannot drift from the
    signature the listener actually calls.
    """
    vacuum_entity_id = "vacuum.lr6"
    manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)
    register_adapter_config(vacuum_entity_id, dict(_LR6_ADAPTER))
    stub = create_autospec(
        manager.clean_order.async_read,
        return_value={"order": [], "read_at": None, "status": "ok"},
    )
    manager.clean_order.async_read = stub
    hass.states.async_set(vacuum_entity_id, "cleaning")
    await hass.async_block_till_done()
    return vacuum_entity_id, stub


async def test_clean_order_refresh_reads_on_dock_arrival(hass, manager):
    """[LR-6a] POSITIVE CONTROL — a dock arrival triggers a read.

    Without this half, [LR-6b] would pass just as happily against a listener that
    never subscribes to anything at all: 'no read after remove()' is only evidence
    of teardown if a read was reachable in the first place.
    """
    vacuum_entity_id, stub = await _lr6_setup(hass, manager)
    clean_order_refresh.register(hass)
    await hass.async_block_till_done()
    stub.reset_mock()  # discard the startup read; this test is about the edge

    hass.states.async_set(vacuum_entity_id, "docked")
    await hass.async_block_till_done()

    stub.assert_awaited_once_with(vacuum_entity_id)


async def test_clean_order_refresh_remove_stops_dock_reads(hass, manager):
    """[LR-6b] remove() genuinely unsubscribes — the dock arrival reads nothing.

    ⚠ THE CLAIM IS THE SUBSCRIPTION, NOT THE BOOKKEEPING. The first cut of
    clean_order_refresh had no remove() and discarded both unsubs; when remove()
    was added, an ablation that threw the unsubs away again left the whole file
    GREEN, because every existing guard only checked that remove() does not raise
    and that a dict key disappears. A listener that leaks its subscription
    satisfies both. So this asserts the only thing that actually matters: after
    teardown, the event does not reach the handler.

    The leak is not theoretical — `register` runs on every config-entry reload, so
    a discarded unsub makes one dock arrival fire N reads after N reloads, each a
    real send_command to the robot.
    """
    vacuum_entity_id, stub = await _lr6_setup(hass, manager)
    clean_order_refresh.register(hass)
    await hass.async_block_till_done()
    stub.reset_mock()

    clean_order_refresh.remove(hass)
    hass.states.async_set(vacuum_entity_id, "docked")
    await hass.async_block_till_done()

    assert stub.await_count == 0, (
        "remove() left the dock-arrival subscription live — the listener leaks "
        "on every reload"
    )
