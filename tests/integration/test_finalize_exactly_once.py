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
    monkeypatch.setattr(
        manager,
        "_get_learning_manager",
        lambda: SimpleNamespace(async_finalize_completed_job=finalize),
    )


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
