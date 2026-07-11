"""Wave A of the learning-processing toggle — box-level gate on the stats rebuild.

[LP-1] learning_processing_enabled property: default True, reflects the data flag.
[LP-2] pending-run counter: bump / reset / get.
[LP-3] finalize gating: toggle ON -> rebuild_stats True passed to learning + pending
       stays 0; toggle OFF -> rebuild_stats False (collect-only) + pending increments.
"""

from __future__ import annotations

from types import SimpleNamespace


async def test_learning_processing_enabled_default_and_toggle(manager):
    """[LP-1]"""
    assert manager.learning_processing_enabled is True
    manager.data["learning_processing_enabled"] = False
    assert manager.learning_processing_enabled is False
    manager.data["learning_processing_enabled"] = True
    assert manager.learning_processing_enabled is True


async def test_learning_pending_counter(manager):
    """[LP-2]"""
    vac = "vacuum.alfred"
    assert manager.get_learning_pending_runs(vac) == 0
    manager._bump_learning_pending(vac)
    manager._bump_learning_pending(vac)
    assert manager.get_learning_pending_runs(vac) == 2
    manager._reset_learning_pending(vac)
    assert manager.get_learning_pending_runs(vac) == 0


async def test_finalize_gates_rebuild_on_toggle(manager, monkeypatch):
    """[LP-3] the run is always collected; only the rebuild is gated by the toggle."""
    vac, mp = "vacuum.alfred", "6"
    recorded: dict = {}

    async def _fake_finalize(**kwargs):
        recorded["rebuild_stats"] = kwargs.get("rebuild_stats")
        return {"completed_job": {}}

    monkeypatch.setattr(
        manager,
        "_get_learning_manager",
        lambda: SimpleNamespace(async_finalize_completed_job=_fake_finalize),
    )
    manager.data["active_jobs"] = {
        vac: {mp: {"started_at": "2026-01-01T10:00:00+00:00", "battery_start": 90}}
    }

    # Toggle ON (default): rebuild requested, nothing pending.
    await manager.finalize_learning_for_active_job(vacuum_entity_id=vac, map_id=mp, battery_end=50)
    assert recorded["rebuild_stats"] is True
    assert manager.get_learning_pending_runs(vac) == 0

    # Toggle OFF: still collected, rebuild skipped, pending increments per run.
    manager.data["learning_processing_enabled"] = False
    await manager.finalize_learning_for_active_job(vacuum_entity_id=vac, map_id=mp, battery_end=50)
    assert recorded["rebuild_stats"] is False
    assert manager.get_learning_pending_runs(vac) == 1
    await manager.finalize_learning_for_active_job(vacuum_entity_id=vac, map_id=mp, battery_end=50)
    assert manager.get_learning_pending_runs(vac) == 2
