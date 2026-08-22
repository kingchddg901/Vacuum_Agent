"""Wave A of the learning-processing toggle — box-level gate on the stats rebuild.

[LP-1] learning_processing_enabled property: default True, reflects the data flag.
[LP-2] pending-run counter: bump / reset / get.
[LP-3] finalize gating: toggle ON -> rebuild_stats True passed to learning + pending
       stays 0; toggle OFF -> rebuild_stats False (collect-only) + pending increments.
[LP-4] toggle OFF just stops rebuilds — no catch-up, pending stays.
[LP-5] toggle ON from OFF runs the catch-up (pending cleared) + resumes on.
[LP-6] the button-triggered catch-up clears pending but leaves the toggle off.
[LP-7] the dashboard snapshot carries the toggle state + pending count for the card.
[LP-8] the catch-up ALSO rebuilds the incremental accumulators rebuild_all does not write.
[LP-9] one accumulator failing must not abort the others.
[LP-10] IN5ATBW9: every service that CLAIMS a rebuild runs the whole post-write
       sequence -- accumulators, cache invalidate, cache preload -- against the
       archive as it stands AFTER the write.
[LP-11] ...and the cache half is not optional just because the runtime is.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
from custom_components.eufy_vacuum.learning.services import (
    SERVICE_EXCLUDE_LEARNING_JOB,
    SERVICE_REBUILD_LEARNING_STATS,
    SERVICE_RESTORE_LEARNING_JOB,
    _get_learning_manager,
    async_register_learning_services,
    async_unregister_learning_services,
)


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


# ---------------------------------------------------------------------------
# [LP-10] / [LP-11] IN5ATBW9 — the SERVICE copies of the same post-write sequence
# ---------------------------------------------------------------------------

_VAC = "vacuum.alfred"          # the vacuum the `manager` fixture registers an adapter for
_JOB_ID = "j-in5atbw9"


@pytest.fixture
async def learning_services(hass, manager):
    """Learning services registered on top of the wired manager.

    The handlers are closures inside `async_register_learning_services`, so the service
    registry is the only way to reach them — calling the LearningManager directly walks
    straight past the wiring these tests are about.
    """
    await async_register_learning_services(hass)
    yield manager
    await async_unregister_learning_services(hass)


@pytest.fixture
def archived_job(hass):
    """One learning-eligible completed job in the archive, and the archive left as found.

    The learning archive lives on disk and is SHARED by the whole session, not rebuilt
    per test — so a seeded record that outlives its test becomes a job file other tests
    find. Measured: leaving this one behind turned [LS-4b] red four files later, because
    it asserts `job_files_found == 0` and read this job. The rebuild these services run
    also rewrites `learned/`, so the fixture restores contents as well as removing files.

    Minimal payload on purpose: `is_learning_job` asks for record_type `completed_job`,
    an outcome status of `completed`, and used_for_learning — nothing else gates it.
    """
    store = LearningHistoryStore(hass)
    root = store.get_paths(vacuum_entity_id=_VAC).root
    before = (
        {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        if root.exists()
        else {}
    )
    store.save_completed_job(
        vacuum_entity_id=_VAC,
        job_id=_JOB_ID,
        payload={
            "record_type": "completed_job",
            "job_id": _JOB_ID,
            "job": {
                "ended_at": "2026-01-01T10:00:00+00:00",
                "duration_minutes": 30.0,
                "room_count": 1,
            },
            "battery": {"start": 80, "end": 60, "used": 20},
            "water": {},
            "job_profile": {
                "map_id": 6,
                "room_count": 1,
                "room_slugs": ["kitchen"],
                "rooms": [],
            },
            "resolved_rooms": [],
            "queue": {"queue_room_ids": [1], "queue_rooms": []},
            "outcome": {
                "status": "completed",
                "used_for_learning": True,
                "learning_blockers": [],
            },
        },
    )

    yield _JOB_ID

    for path in {p for p in root.rglob("*") if p.is_file()} - set(before):
        path.unlink()
    for path, blob in before.items():
        if path.read_bytes() != blob:
            path.write_bytes(blob)


#: Every service whose response tells the user the stats were REBUILT. [LP-8] pins the
#: manager-side copy of this sequence (the catch-up); these are the other three, and
#: they are parametrised rather than written out three times on purpose. RP-020/RF-22
#: (SVC-1): the sequence landed in `rebuild_learning_stats` and NOT in exclude/restore,
#: so two of the three claimed "stats rebuilt" while the incremental accumulators
#: OUTSIDE `rebuild_all` (learned_zones, accuracy_stats, battery drain aggregates) kept
#: whatever the excluded job had already contributed. A test per copy proves only that
#: each copy agrees with itself; this one bites the SET.
_REBUILD_CLAIMING_SERVICES = (
    # service, extra call data, response key that means the write happened, and what
    # the archived record must say at the moment the accumulator rebuild reads it back
    (SERVICE_REBUILD_LEARNING_STATS, {}, None, True),
    (SERVICE_EXCLUDE_LEARNING_JOB, {"job_id": _JOB_ID}, "excluded", False),
    (SERVICE_RESTORE_LEARNING_JOB, {"job_id": _JOB_ID}, "restored", True),
)


@pytest.mark.parametrize(
    ("service", "extra_data", "wrote_key", "eligible_when_read_back"),
    _REBUILD_CLAIMING_SERVICES,
    ids=[row[0] for row in _REBUILD_CLAIMING_SERVICES],
)
async def test_every_rebuild_claiming_service_reaches_every_derived_artifact(
    hass,
    learning_services,
    archived_job,
    monkeypatch,
    service,
    extra_data,
    wrote_key,
    eligible_when_read_back,
):
    """[LP-10] IN5ATBW9: a write that changes a source must reach EVERY artifact
    derived from it, and "rebuild" must not name a partial operation.

    Rebuild the derived files, rebuild the incremental accumulators that live outside
    them, invalidate the in-memory cache, repopulate it — all four, or the operation is
    lying about what it did. The user's one tool for removing a known-bad run was
    partial, reported success, and left the bad data influencing estimates.

    RED when any handler drops any one of the three post-write calls, when a handler
    names a vacuum other than the one it just wrote for, or when the accumulator rebuild
    runs BEFORE that write — which would re-fold the very sample being removed.
    """
    core_manager = hass.data[DOMAIN][DATA_RUNTIME]
    learning = _get_learning_manager(hass)

    order: list[str] = []
    # A sentinel, not None/{}: "the rebuild never ran" and "the rebuild saw a record
    # with no outcome" must not both read as the same falsy answer.
    never_read = "<the accumulator rebuild never read the archive>"
    read_back: list = [never_read]

    real_rebuild_all = learning.rebuilder.rebuild_all
    real_accumulators = core_manager.async_rebuild_learning_accumulators
    real_invalidate = learning._invalidate_learning_stats_cache
    real_preload = learning.async_preload_learning_stats

    def _rebuild_all(**kwargs):
        # The FIRST step, and the one the rule names first: it writes the four derived
        # files (room_stats, job_stats, jobs_index, CSV). It runs INSIDE the manager
        # method the service calls, one line after the archive write — so observing it
        # here is also what proves the sequence runs AFTER the write, not merely that
        # it runs. Without this spy, deleting the call leaves `order` unchanged and both
        # tests stay green while all four files go stale (refuted 2026-08-21).
        order.append("rebuild_all")
        return real_rebuild_all(**kwargs)

    async def _accumulators(*, vacuum_entity_id):
        order.append("accumulators")
        record = LearningHistoryStore(hass).load_completed_job(
            vacuum_entity_id=vacuum_entity_id, job_id=archived_job
        )
        read_back[0] = (record or {}).get("outcome", {}).get("used_for_learning")
        return await real_accumulators(vacuum_entity_id=vacuum_entity_id)

    def _invalidate(*, vacuum_entity_id):
        order.append("invalidate")
        return real_invalidate(vacuum_entity_id=vacuum_entity_id)

    def _preload(*, vacuum_entity_id):
        order.append("preload")
        return real_preload(vacuum_entity_id=vacuum_entity_id)

    # create_autospec of the REAL bound methods, and each spy delegates to the real one:
    # the production effects still happen, and a handler that called these positionally
    # or under a different kwarg name is a TypeError here rather than a cheerful pass.
    # A bare mock would agree with the caller about all three.
    spy_rebuild_all = create_autospec(real_rebuild_all, side_effect=_rebuild_all)
    spy_accumulators = create_autospec(real_accumulators, side_effect=_accumulators)
    spy_invalidate = create_autospec(real_invalidate, side_effect=_invalidate)
    spy_preload = create_autospec(real_preload, side_effect=_preload)
    monkeypatch.setattr(learning.rebuilder, "rebuild_all", spy_rebuild_all)
    monkeypatch.setattr(
        core_manager, "async_rebuild_learning_accumulators", spy_accumulators
    )
    monkeypatch.setattr(learning, "_invalidate_learning_stats_cache", spy_invalidate)
    monkeypatch.setattr(learning, "async_preload_learning_stats", spy_preload)

    result = await hass.services.async_call(
        DOMAIN,
        service,
        {"vacuum_entity_id": _VAC, **extra_data},
        blocking=True,
        return_response=True,
    )

    if wrote_key is not None:
        assert result[wrote_key] is True, (
            f"{service} did not perform the write whose reach is under test: {result}"
        )

    # The FOUR post-write calls, in the order that makes each of them mean something.
    # Four, not three: the rule enumerates rebuild_all first, and a ledger that starts at
    # "accumulators" cannot see it go missing.
    assert order == ["rebuild_all", "accumulators", "invalidate", "preload"], (
        f"{service} ran {order or 'NONE'} of the post-write sequence. Its response says "
        "the stats were rebuilt; a missing step means that claim is false for every "
        "artifact that step owns."
    )
    # kwargs vary by call site (rebuild_csv is passed on some paths), so pin the one
    # argument every path must agree on rather than the whole signature.
    spy_rebuild_all.assert_called_once()
    assert spy_rebuild_all.call_args.kwargs.get("vacuum_entity_id") == _VAC, (
        f"{service} rebuilt the derived files for "
        f"{spy_rebuild_all.call_args.kwargs.get('vacuum_entity_id')!r}, not the vacuum "
        "it just wrote for."
    )
    spy_accumulators.assert_called_once_with(vacuum_entity_id=_VAC)
    spy_invalidate.assert_called_once_with(vacuum_entity_id=_VAC)
    spy_preload.assert_called_once_with(vacuum_entity_id=_VAC)

    # ...and it recomputed from the archive AS IT NOW STANDS. Rebuilding first and
    # writing second would re-fold exactly the sample the user asked to remove.
    assert read_back[0] is eligible_when_read_back, (
        f"{service}: the accumulator rebuild read used_for_learning={read_back[0]!r} "
        f"back off disk, expected {eligible_when_read_back!r} — it ran against the "
        "PRE-write archive"
    )


async def test_a_rebuild_claiming_service_without_a_runtime_still_refreshes_the_cache(
    hass, learning_services, archived_job, monkeypatch
):
    """[LP-11] The accumulator rebuild hangs off the runtime, which is optional — but
    the cache half of the sequence is not, and must not be skipped with it.

    `if runtime is not None` is a shoulder: everything after it is unconditional, and a
    change that moved a line inside the guard would take the cache refresh down with the
    accumulators for anyone whose runtime is absent.
    """
    learning = _get_learning_manager(hass)
    order: list[str] = []

    real_invalidate = learning._invalidate_learning_stats_cache
    real_preload = learning.async_preload_learning_stats

    def _invalidate(*, vacuum_entity_id):
        order.append("invalidate")
        return real_invalidate(vacuum_entity_id=vacuum_entity_id)

    def _preload(*, vacuum_entity_id):
        order.append("preload")
        return real_preload(vacuum_entity_id=vacuum_entity_id)

    spy_invalidate = create_autospec(real_invalidate, side_effect=_invalidate)
    spy_preload = create_autospec(real_preload, side_effect=_preload)
    monkeypatch.setattr(learning, "_invalidate_learning_stats_cache", spy_invalidate)
    monkeypatch.setattr(learning, "async_preload_learning_stats", spy_preload)
    monkeypatch.delitem(hass.data[DOMAIN], DATA_RUNTIME)

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": archived_job},
        blocking=True,
        return_response=True,
    )

    assert result["excluded"] is True
    assert order == ["invalidate", "preload"], (
        f"with no runtime the handler ran {order or 'NONE'} — the card keeps serving "
        "the cached pre-exclusion stats while the response says they were rebuilt"
    )
    spy_invalidate.assert_called_once_with(vacuum_entity_id=_VAC)
    spy_preload.assert_called_once_with(vacuum_entity_id=_VAC)
