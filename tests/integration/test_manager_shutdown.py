"""RP-003/INIT-1 — manager shutdown seam + unload ledger.

Before this, EufyVacuumManager exposed no shutdown seam: a reloaded entry's
PREVIOUS manager could keep running spawned tasks/timers and keep writing to
the shared store after a NEW manager had taken over (hardware-proven pattern:
a timer captured during the old manager's life fires after unload and
clobbers the new manager's save). async_shutdown() now cancels the two ledgered
spawn sites (phase_runner's dock pollers, external_run's grace timers) and
async_save() becomes a no-op once shut down.

[MS-1] shutdown cancels a live dock-poller task and a pending grace timer.
[MS-2] async_save is a no-op after shutdown (belt-and-braces).
[MS-3] double-reload: the old manager's late-firing save cannot clobber the
       new manager's data once the store is re-read fresh.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

_VAC = "vacuum.alfred"
_MAP = "6"


async def test_shutdown_cancels_ledgered_dock_poller_and_grace_timer(manager, monkeypatch):
    """[MS-1] async_shutdown cancels every live dock-poller task (phase_runner)
    and every pending external-run grace timer (external_run) -- the two spawn
    sites this packet ledgers."""
    started = asyncio.Event()

    async def _fake_wait_phase(*, vacuum_entity_id, map_id, phase_index):
        started.set()
        await asyncio.sleep(100)

    monkeypatch.setattr(manager.phase_runner, "_run_wait_phase", _fake_wait_phase)
    manager.phase_runner._spawn_dock_poller(
        vacuum_entity_id=_VAC, map_id=_MAP, phase_type="wait", phase_index=0,
    )
    await started.wait()
    assert manager.phase_runner._dock_poller_tasks, "the poller task was not ledgered"

    cancelled = []
    manager.external_run._external_grace_timers()[(_VAC, _MAP)] = (
        lambda: cancelled.append(1)
    )

    result = await manager.async_shutdown()

    assert result["tasks_cancelled"] >= 1
    assert result["timers_cancelled"] >= 1
    assert cancelled == [1], "the grace timer's cancel callable was not invoked"
    assert manager.phase_runner._dock_poller_tasks == {}
    assert manager.phase_runner._dock_poller_active == set()
    assert manager.external_run._external_grace_timers() == {}


async def test_save_after_shutdown_is_a_noop(manager, caplog):
    """[MS-2] async_save is a no-op after async_shutdown -- belt-and-braces
    against a stale, unloaded manager clobbering a store a newer manager (from
    a reload) already owns.

    DRAFT-5: async_shutdown() now does one deliberate final flush of its OWN
    (so a debounced draft save via async_save_delayed is never silently dropped
    by an unload) before it marks itself closed -- that is the CURRENT manager,
    still the authoritative owner, doing its own last write, not a stray late
    write from an already-superseded manager, so it isn't what this test's
    "no-op after shutdown" contract is about. Assert on the call AFTER shutdown
    instead (the one _closed actually gates).
    """
    stub = AsyncMock()
    manager.storage.async_save = stub

    await manager.async_shutdown()
    assert stub.await_count == 1, "shutdown's own final flush"

    await manager.async_save()

    assert stub.await_count == 1, "the post-shutdown call must be suppressed, not a 2nd write"
    assert "save after shutdown suppressed" in caplog.text


async def test_shutdown_is_idempotent(manager):
    """[MS-2b] A second shutdown call (e.g. a duplicate unload callback) is a
    harmless no-op, not a re-cancel of an empty ledger raising."""
    first = await manager.async_shutdown()
    second = await manager.async_shutdown()
    assert second == {"timers_cancelled": 0, "tasks_cancelled": 0}
    assert first is not None


async def test_double_reload_yields_one_live_manager_writing(hass, mock_config_entry, hass_storage):
    """[MS-3] A reload's PREVIOUS manager, shut down, cannot clobber the new
    manager's save even when a late callback captured from before shutdown
    (exactly what an armed asyncio timer/task holds) fires after the new
    manager has already saved. Verified by re-reading the store fresh, not by
    inspecting either manager's in-memory state."""
    from custom_components.eufy_vacuum.adapters.registry import AdapterCoordinator
    from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR, DOMAIN
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    hass.data.setdefault(DOMAIN, {})
    coordinator = AdapterCoordinator(hass, mock_config_entry)
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = coordinator

    a = EufyVacuumManager(hass)
    await a.async_initialize()
    a.data["owner"] = "A"
    late_save = a.async_save  # captured before shutdown, as an armed callback would hold it

    await a.async_shutdown()

    b = EufyVacuumManager(hass)
    await b.async_initialize()
    b.data["owner"] = "B"
    await b.async_save()

    # A's captured save callback fires late (the race this packet closes) --
    # must be suppressed, not overwrite B's save.
    await late_save()

    reloaded = EufyVacuumManager(hass)
    await reloaded.async_initialize()
    assert reloaded.data.get("owner") == "B"


async def test_shutdown_before_load_never_flushes_the_seed_over_the_store(hass, mock_config_entry):
    """[MS-4] R2-BUG-6. __init__.py registers async_shutdown via entry.async_on_unload
    BEFORE awaiting async_initialize -- deliberately, so a mid-setup failure still tears
    down. But __init__ seeds self.data = {} and only async_initialize replaces it with the
    real store, so a failure at (or before) async_load left the EMPTY SEED in place, and an
    unguarded flush wrote {} over the user's entire store: every managed room, map, learned
    profile and theme, wiped by an unrelated setup failure.

    Constructed-but-never-initialized is exactly the state HA unloads from when setup
    fails, so this pins that the flush is skipped there -- and, below, that a real
    initialized manager DOES still flush (the guard must not disable the save seam)."""
    from custom_components.eufy_vacuum.adapters.registry import AdapterCoordinator
    from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR, DOMAIN
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = AdapterCoordinator(hass, mock_config_entry)

    manager = EufyVacuumManager(hass)  # NO async_initialize -- setup "failed"
    assert manager.data == {}, "the seed is what makes this dangerous"
    manager.storage.async_save = AsyncMock()

    result = await manager.async_shutdown()

    manager.storage.async_save.assert_not_awaited()
    assert result == {"timers_cancelled": 0, "tasks_cancelled": 0}
    assert manager._closed is True, "a failed setup must still mark the manager closed"
    assert await manager.async_shutdown() == {"timers_cancelled": 0, "tasks_cancelled": 0}


async def test_shutdown_after_load_still_flushes(hass, mock_config_entry):
    """[MS-5] The other half of R2-BUG-6's guard: once the store HAS been read, unload must
    still flush it. A guard that also suppressed the real save would trade data loss on a
    rare setup failure for data loss on every reload -- strictly worse."""
    from custom_components.eufy_vacuum.adapters.registry import AdapterCoordinator
    from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR, DOMAIN
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = AdapterCoordinator(hass, mock_config_entry)

    manager = EufyVacuumManager(hass)
    await manager.async_initialize()
    manager.data["owner"] = "flush-me"
    manager.storage.async_save = AsyncMock()

    await manager.async_shutdown()

    manager.storage.async_save.assert_awaited_once()
    assert manager.storage.async_save.await_args.args[0].get("owner") == "flush-me"
