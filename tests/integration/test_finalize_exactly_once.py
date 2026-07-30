"""Exactly-once finalization — the claim that makes finalize_learning_for_active_job safe.

Background: `mark_active_job_finalized` is the sole writer of status="completed" and it runs
AFTER an await whose real suspension is a disk-I/O executor hop. The only entry gate used to
be `if not started_at`, and `started_at` is never cleared — so it stayed truthy forever after
a run and every later caller passed. Two authorities could both enter, both suspend, and both
finalize the same job. `core/water_amendment.py` already documented the symptom ("can fire
multiple times for the same finalized job"), and NO test covered it, which is why it shipped.

[XO-1] a finalized job refuses re-entry ("already_finalized") and does not re-run the work.
[XO-2] re-entry DURING the await is refused ("finalize_in_flight") — this is the real race:
       the nested call happens while the first is suspended, exactly as two authorities would.
[XO-3] a FAILED finalize releases the claim, so a later legitimate finalize still succeeds.
[XO-4] a normal single finalize is unaffected (the happy path must stay untouched).
[XO-5] a claim orphaned by a crash/restart is cleared at startup — otherwise that job
       could never finalize again, which is worse than the duplicate it prevents.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

_VAC, _MAP = "vacuum.alfred", "6"


def _seed_active_job(manager, **extra):
    job = {"started_at": "2026-01-01T10:00:00+00:00", "battery_start": 90}
    job.update(extra)
    manager.data["active_jobs"] = {_VAC: {_MAP: job}}
    return job


def _install_fake_learning(manager, monkeypatch, finalize):
    """Install a REAL LearningManager with only its finalize BODY stubbed.

    The exactly-once claim lives on LearningManager.async_finalize_completed_job (the
    chokepoint -- it was moved there because the finalize_learning_job service reached that
    method directly and walked past a guard placed on the core-manager wrapper). So these
    tests must exercise the real method and stub only `_finalize_claimed`; replacing the
    whole learning manager would replace the claim itself and prove nothing.
    """
    from custom_components.eufy_vacuum.learning.manager import LearningManager

    lm = LearningManager(manager.hass)
    monkeypatch.setattr(lm, "_finalize_claimed", finalize)
    monkeypatch.setattr(manager, "_get_learning_manager", lambda: lm)
    return lm


async def test_finalized_job_refuses_re_entry(manager, monkeypatch):
    """[XO-1] Once `finalized` is set, a second finalize must not re-run the work."""
    calls: list[int] = []

    async def _fake(**kwargs):
        calls.append(1)
        return {"completed_job": {}}

    _install_fake_learning(manager, monkeypatch, _fake)
    _seed_active_job(manager, finalized=True)

    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
    )

    assert result["finalized"] is False
    assert result["reason"] == "already_finalized"
    assert calls == [], "the finalize body ran for an already-finalized job"


async def test_re_entry_during_the_await_is_refused(manager, monkeypatch):
    """[XO-2] THE RACE. A second authority entering while the first is suspended must be
    refused. Re-entering from inside the awaited call reproduces exactly that interleaving:
    the claim is already set, the first call has not yet reached mark_active_job_finalized."""
    inner: dict = {}
    calls: list[int] = []

    async def _fake(**kwargs):
        calls.append(1)
        # We are now "suspended" inside the first finalize — a second authority fires.
        inner["result"] = await manager.finalize_learning_for_active_job(
            vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
        )
        return {"completed_job": {}}

    _install_fake_learning(manager, monkeypatch, _fake)
    _seed_active_job(manager)

    outer = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
    )

    assert inner["result"]["finalized"] is False
    assert inner["result"]["reason"] == "finalize_in_flight"
    assert calls == [1], "the nested call re-ran the finalize body"
    assert outer == {"completed_job": {}}, "the first finalize must still complete normally"


async def test_failed_finalize_releases_the_claim(manager, monkeypatch):
    """[XO-3] Chris's call: RELEASE on failure so a transient error is retryable. A kept
    claim would strand the job until the reaper cleared it."""
    attempts: list[int] = []

    async def _boom(**kwargs):
        attempts.append(1)
        raise RuntimeError("disk went away")

    _install_fake_learning(manager, monkeypatch, _boom)
    job = _seed_active_job(manager)

    with pytest.raises(RuntimeError):
        await manager.finalize_learning_for_active_job(
            vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
        )

    assert "finalize_claimed_at" not in job, "a failed finalize left the claim behind"

    # The retry must be allowed through.
    async def _ok(**kwargs):
        attempts.append(2)
        return {"completed_job": {}}

    _install_fake_learning(manager, monkeypatch, _ok)
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
    )
    assert result == {"completed_job": {}}
    assert attempts == [1, 2]


async def test_single_finalize_is_unaffected(manager, monkeypatch):
    """[XO-4] The happy path must be untouched — the claim is set and then cleared, leaving
    no residue that a later legitimate finalize would trip over."""
    async def _fake(**kwargs):
        return {"completed_job": {}}

    _install_fake_learning(manager, monkeypatch, _fake)
    job = _seed_active_job(manager)

    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
    )
    assert result == {"completed_job": {}}
    assert "finalize_claimed_at" not in job


async def test_restart_clears_an_orphaned_claim(manager):
    """[XO-5] SHIPPING SAFETY. active_jobs is persisted, so a claim orphaned by a crash or
    a restart mid-finalize would come back on the next boot — and block that job from EVER
    finalizing, which is strictly worse than the duplicate finalize the claim prevents.

    A claim cannot legitimately survive a restart: if the process is starting, no finalize
    is in flight. async_initialize therefore calls this unconditionally at boot.
    """
    manager.data["active_jobs"] = {
        _VAC: {
            _MAP: {
                "started_at": "2026-01-01T10:00:00+00:00",
                "battery_start": 90,
                "finalize_claimed_at": "2026-01-01T10:05:00+00:00",  # orphaned by a crash
            },
            "7": {"started_at": "2026-01-01T09:00:00+00:00"},  # no claim -> untouched
        }
    }

    cleared = manager._clear_orphaned_finalize_claims()

    assert cleared == 1
    job = manager.data["active_jobs"][_VAC][_MAP]
    assert "finalize_claimed_at" not in job, (
        "an orphaned claim survived a restart — this job could never finalize again"
    )
    # The job itself, and its claim-free sibling, must be left otherwise intact.
    assert job["started_at"] == "2026-01-01T10:00:00+00:00"
    assert manager.data["active_jobs"][_VAC]["7"]["started_at"] == "2026-01-01T09:00:00+00:00"


async def test_a_cleared_claim_lets_the_job_finalize_again(manager, monkeypatch):
    """[XO-6] The point of XO-5: after the claim is cleared, finalize must actually work.
    Without the clear this job was permanently unfinalizable."""
    async def _fake(**kwargs):
        return {"completed_job": {}}

    _install_fake_learning(manager, monkeypatch, _fake)
    _seed_active_job(manager, finalize_claimed_at="2026-01-01T10:05:00+00:00")

    blocked = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
    )
    assert blocked["reason"] == "finalize_in_flight"

    manager._clear_orphaned_finalize_claims()

    ok = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=50
    )
    assert ok == {"completed_job": {}}


async def test_the_service_entry_point_also_inherits_the_claim(manager, monkeypatch):
    """[XO-7] ED-1 REGRESSION. The claim must live at the CHOKEPOINT, not on the
    core-manager wrapper.

    `finalize_learning_job` (the documented manual retry) calls
    LearningManager.async_finalize_completed_job DIRECTLY. With the guard on the wrapper it
    walked straight past, re-derived the same job_id, harvested an already-nulled error
    latch and os.replace'd the record with had_errors=False -- destroying the run's error
    history unrepairably, since rebuild_all rebuilds FROM those files.

    This drives the learning manager directly, exactly as the service does.
    """
    from custom_components.eufy_vacuum.learning.manager import LearningManager

    bodies: list[int] = []

    async def _body(**kwargs):
        bodies.append(1)
        return {"completed_job": {}}

    lm = LearningManager(manager.hass)
    monkeypatch.setattr(lm, "_finalize_claimed", _body)
    _seed_active_job(manager, finalized=True)

    # The service path — no core-manager wrapper involved.
    result = await lm.async_finalize_completed_job(
        manager=manager,
        vacuum_entity_id=_VAC, map_id=_MAP,
        battery_start=90, battery_end=50,
        started_at="2026-01-01T10:00:00+00:00",
    )

    assert result["reason"] == "already_finalized"
    assert bodies == [], "the service path re-ran finalize on an already-finalized job"
