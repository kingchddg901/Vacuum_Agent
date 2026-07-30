"""Wave A of the learning-processing toggle — box-level gate on the stats rebuild.

[LP-1] learning_processing_enabled property: default True, reflects the data flag.
[LP-2] pending-run counter: bump / reset / get.
[LP-3] finalize gating: toggle ON -> rebuild_stats True passed to learning + pending
       stays 0; toggle OFF -> rebuild_stats False (collect-only) + pending increments.
[LP-4] toggle OFF just stops rebuilds — no catch-up, pending stays.
[LP-5] toggle ON from OFF runs the catch-up (pending cleared) + resumes on.
[LP-6] the button-triggered catch-up clears pending but leaves the toggle off.
[LP-7] the dashboard snapshot carries the toggle state + pending count for the card.
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


async def test_set_processing_off_does_not_catch_up(manager):
    """[LP-4] Turning it OFF just stops rebuilds — no catch-up, pending stays."""
    vac = "vacuum.alfred"
    manager.data.setdefault("vacuums", {})[vac] = {"is_managed": True}
    manager._bump_learning_pending(vac)
    res = await manager.async_set_learning_processing(enabled=False)
    assert res["enabled"] is False
    assert manager.learning_processing_enabled is False
    assert manager.get_learning_pending_runs(vac) == 1  # not caught up


class _StubLearning:
    """Records rebuild_learning calls; the manager fixture has no real LearningManager."""

    def __init__(self) -> None:
        self.rebuilt: list[str] = []

    def rebuild_learning(self, vacuum_entity_id, rebuild_csv=False):
        self.rebuilt.append(vacuum_entity_id)
        return {"rebuilt": True}

    def _invalidate_learning_stats_cache(self, *, vacuum_entity_id):
        pass

    def async_preload_learning_stats(self, *, vacuum_entity_id):
        pass


async def test_set_processing_on_catches_up(manager, monkeypatch):
    """[LP-5] Turning it ON from OFF runs the catch-up (pending cleared) + resumes on."""
    vac = "vacuum.alfred"
    stub = _StubLearning()
    monkeypatch.setattr(manager, "_get_learning_manager", lambda: stub)
    manager.data.setdefault("vacuums", {})[vac] = {"is_managed": True}
    manager.data["learning_processing_enabled"] = False
    manager._bump_learning_pending(vac)
    res = await manager.async_set_learning_processing(enabled=True)
    assert res["enabled"] is True
    assert res["caught_up"] is not None
    assert stub.rebuilt == [vac]  # catch-up reprocessed the vacuum
    assert manager.learning_processing_enabled is True
    assert manager.get_learning_pending_runs(vac) == 0  # backlog processed


async def test_process_pending_runs_stays_off(manager, monkeypatch):
    """[LP-6] The button-triggered catch-up clears pending but leaves the toggle off."""
    vac = "vacuum.alfred"
    stub = _StubLearning()
    monkeypatch.setattr(manager, "_get_learning_manager", lambda: stub)
    manager.data.setdefault("vacuums", {})[vac] = {"is_managed": True}
    manager.data["learning_processing_enabled"] = False
    manager._bump_learning_pending(vac)
    res = await manager.async_process_pending_learning()
    assert res["count"] == 1
    assert stub.rebuilt == [vac]
    assert manager.get_learning_pending_runs(vac) == 0
    assert manager.learning_processing_enabled is False  # still off


async def test_dashboard_snapshot_exposes_learning_processing(manager):
    """[LP-7] The snapshot carries the toggle state + pending count for the card."""
    vac, mp = "vacuum.alfred", "6"
    manager.data["learning_processing_enabled"] = False
    manager._bump_learning_pending(vac)
    manager._bump_learning_pending(vac)
    snap = manager.get_dashboard_snapshot(vacuum_entity_id=vac, map_id=mp)
    lp = snap["learning_processing"]
    assert lp["enabled"] is False
    assert lp["pending_runs"] == 2
    assert lp["has_last_estimate"] is False  # no learning manager in the fixture


async def test_catch_up_also_rebuilds_the_incremental_accumulators(manager, monkeypatch):
    """[LP-8] WIRING: the catch-up must recompute the accumulators rebuild_all does NOT
    write (learned_zones, battery drain aggregates).

    Without this the repair mechanisms exist but nothing invokes them, so a user running a
    rebuild would silently keep whatever bad samples those stores accumulated — which is
    the state that made them 'unrepairable' in the first place.
    """
    called: list[str] = []

    monkeypatch.setattr(
        manager,
        "_get_learning_manager",
        lambda: SimpleNamespace(
            rebuild_learning=lambda *a, **k: {"ok": True},
            _invalidate_learning_stats_cache=lambda **k: None,
            async_preload_learning_stats=lambda **k: None,
        ),
    )

    async def _spy(*, vacuum_entity_id):
        called.append(vacuum_entity_id)
        return {"vacuum_entity_id": vacuum_entity_id}

    monkeypatch.setattr(manager, "async_rebuild_learning_accumulators", _spy)
    manager.data["vacuums"] = {"vacuum.alfred": {}}

    await manager.async_process_pending_learning()

    assert called == ["vacuum.alfred"], "the catch-up did not rebuild the accumulators"


async def test_accumulator_rebuild_survives_one_sink_failing(manager, monkeypatch):
    """[LP-9] One accumulator blowing up must not abort the others or the rebuild — these
    are best-effort repairs layered on top of a stats rebuild that already succeeded."""
    def _boom(self_, **kwargs):
        raise RuntimeError("zone store unreadable")

    monkeypatch.setattr(
        manager,
        "_get_learning_manager",
        lambda: SimpleNamespace(
            rebuild_learned_zones=_boom,
            collect_archived_battery_metrics=lambda **k: [],
        ),
    )

    # Must not raise.
    out = await manager.async_rebuild_learning_accumulators(vacuum_entity_id="vacuum.alfred")
    assert out["vacuum_entity_id"] == "vacuum.alfred"
    assert "learned_zones" not in out, "a failing sink reported a result"
