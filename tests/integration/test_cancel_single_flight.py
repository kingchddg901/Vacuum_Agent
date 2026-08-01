"""RP-010/RF-06 — cancel single-flight latch (active_job.py half).

async_cancel_active_job had no single-flight latch: a second cancel arriving
inside the 30s terminal-confirm window ran the whole body again and
re-finalized with the exactly-once claim's REFUSAL dict, nulling
finalize_summary (mark_active_job_finalized only rewrites it when given a
real dict). See test_cancel_chokepoint.py for the phase_runner.py half
(dispatch chokepoint + maybe_advance_phase suppression).

[CC-4] a second call while _cancel_in_flight is already set refuses with
       cancel_in_progress.
[CC-5] a cancel failure (return_to_base raises) clears the latch so a retry
       is not permanently blocked.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker

_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def tracker(manager) -> ActiveJobTracker:
    return manager.active_job


async def test_second_cancel_refused_while_first_in_flight(tracker, manager, hass):
    """[CC-4] a second cancel call while _cancel_in_flight is already set (the
    first cancel's own latch, set before return_to_base) is refused rather than
    re-running the whole body."""
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        "_cancel_in_flight": True,
    }
    out = await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["cancelled"] is False
    assert out["reason"] == "cancel_in_progress"


async def test_cancel_failure_clears_latch_for_retry(tracker, manager, hass, monkeypatch):
    """[CC-5] a transient failure (return_to_base raising) must not turn into a
    PERMANENT single-flight lock -- the latch clears so a retry can proceed."""
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
    }

    async def _boom(call):
        raise RuntimeError("device offline")

    hass.services.async_register("vacuum", "return_to_base", _boom)

    with pytest.raises(RuntimeError):
        await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    assert manager.data["active_jobs"][_VAC][_MAP]["_cancel_in_flight"] is False

    # the retry must not be refused as cancel_in_progress
    hass.services.async_register("vacuum", "return_to_base", _boom)
    with pytest.raises(RuntimeError):
        await tracker.async_cancel_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
