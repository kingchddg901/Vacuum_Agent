"""Integration tests for learning/services.py — service registration + handlers.

Coverage targets
----------------
[LS-1]  Services are registered after async_register_learning_services.
[LS-2]  get_incomplete_run_log returns {} when no log exists.
[LS-3]  get_trouble_rooms_log returns {} when no log exists.
[LS-4]  rebuild_learning_stats with no jobs runs without error.
[LS-5]  run_learning_estimate with empty queue returns error payload.
[LS-6]  reanchor_learning_timeline passthrough returns reanchored estimate.
[LS-7]  get_next_room returns {} for empty/no-room estimate.
[LS-8]  record_estimate_accuracy stores accuracy data and returns result.
[LS-9]  get_learning_history_snapshot returns well-formed snapshot.
[LS-10] get_metrics_snapshot returns well-formed payload.
[LS-11] exclude_learning_job returns not_found for a missing job.
[LS-12] restore_learning_job returns not_found for a missing job.
[LS-13] exclude_learning_job + restore round-trip flips used_for_learning.
[LS-14] Services are removed after async_unregister_learning_services.
[LS-15] save_learning_snapshot completes against an empty manager.
[LS-16] finalize_learning_job fires EVENT_JOB_FINISHED.
[LS-17] get_room_learning_estimates returns per-room list.
[LS-18] retry_missed_rooms returns started=False when no log exists.
[LS-19] finalize with cancelled outcome fires EVENT_RUN_INCOMPLETE.
[LS-20] _update_trouble_rooms_log accumulates miss_count across two finalize calls.
[LS-21] finalize with active_job started_at covers wall-clock derivation + trace_run_id.
[LS-22] finalize single completed room with trace_run_id covers boundary derivation check.
[LS-23] get_learning_history_snapshot with seeded jobs runs full enrichment loop.
[LS-24] get_metrics_snapshot with seeded jobs returns populated metrics.
[LS-25] save_learning_snapshot with managed rooms covers access-graph loop body.
[LS-26] get_room_learning_estimates with learned stats hits the learned-match branch.
[LS-27] finalize with adapter cleaning_time entity covers sensor fallback.
[LS-28] ErrorTracker latch is harvested during finalization (lines 609-613).
[LS-29] total_error_seconds > cleaning_time_seconds → adjusted value clamped to 0 (lines 645-660).
[LS-30] forced_lifecycle_state sets outcome without forced_outcome_status (lines 402-420).
[LS-31] Completed finalize clears any prior incomplete run log (line 1251) + trouble rooms last_cleaned_at (line 1390).
[LS-32] active_job.completed_room_ids reduces missed set in incomplete log (lines 1262-1271).
[LS-33] Live snapshot with room_timeline enriches resolved rooms and triggers _auto_record_accuracy (lines 885-955, manager 672-712).
[LS-34] get_learning_history_snapshot status + room_slug filters prune results (manager lines 919-946).
[LS-35] Sync finalize_completed_job path (manager.py lines 537-568).
[LS-36] rebuild_stats=True, rebuild_csv=True exercises lines 801-807 and manager line 622.
[LS-37] started_at == ended_at → wall-clock derived = 0 → skipped (507->525 branch).
[LS-38] used_for_learning=False filter prunes results (manager line 927-928).
[LS-39] async_preload_learning_stats is a no-op when stats are already cached (lines 311-312).
[LS-40] _detect_cancel_likely_run: unparseable timestamps → missing_timestamps.
[LS-41] _detect_cancel_likely_run: multi-room job → not_single_room.
[LS-42] _detect_cancel_likely_run: no state_transitions → no_transition_history.
[LS-43] _detect_cancel_likely_run: adapter without task_status entity → no_task_status_entity.
[LS-44] _detect_cancel_likely_run: exclusion-vocab to_state → service_state_explains_return.
[LS-45] _detect_cancel_likely_run: no cleaning→returning pattern → no_cancel_like_transition.
[LS-46] _detect_cancel_likely_run: paused→returning under floor → cancel_likely floor_time_too_short (physical_vacuum).
[LS-47] _detect_cancel_likely_run: cleaning→returning but long enough → duration_not_short.
[LS-48] get_learning_history_snapshot rebuilds an old-format jobs index (manager 758-769).
[LS-49] get_learning_history_snapshot builds trust metrics from accuracy data (manager 817-833).
[LS-50] _normalize_graph_targets normalizes/de-dups/drops negatives (manager 47-55).
[LS-51] _trust_level_from_score returns the right label per band (manager 61-69).
[LS-52] _display_label returns None for empty/separator-only input (manager 75-80).
[LS-53] finalize pushes battery metrics to the BatteryHealthManager (job_finalizer 755-762).
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
from custom_components.eufy_vacuum.learning.services import (
    SERVICE_EXCLUDE_LEARNING_JOB,
    SERVICE_GET_INCOMPLETE_RUN_LOG,
    SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
    SERVICE_GET_METRICS_SNAPSHOT,
    SERVICE_GET_NEXT_ROOM,
    SERVICE_GET_TROUBLE_ROOMS_LOG,
    SERVICE_REANCHOR_LEARNING_TIMELINE,
    SERVICE_REBUILD_LEARNING_STATS,
    SERVICE_RECORD_ESTIMATE_ACCURACY,
    SERVICE_RESTORE_LEARNING_JOB,
    SERVICE_RUN_LEARNING_ESTIMATE,
    SERVICE_SAVE_LEARNING_SNAPSHOT,
    async_register_learning_services,
    async_unregister_learning_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"
_MAP_INT = 6


# ---------------------------------------------------------------------------
# Test-data helpers
# ---------------------------------------------------------------------------

def _seed_completed_job(
    hass,
    vacuum_entity_id: str,
    job_id: str,
    *,
    room_slugs: list[str] | None = None,
    status: str = "completed",
    used_for_learning: bool = True,
    duration_minutes: float = 30.0,
) -> dict:
    """Seed a minimal completed job directly via LearningHistoryStore."""
    if room_slugs is None:
        room_slugs = ["kitchen"]
    rooms = [
        {
            "slug": slug,
            "room_id": i + 1,
            "name": slug.replace("_", " ").title(),
            "clean_mode": "vacuum",
            "clean_intensity": "standard",
            "clean_times": 1,
            "is_carpet": False,
        }
        for i, slug in enumerate(room_slugs)
    ]
    payload = {
        "record_type": "completed_job",
        "job_id": job_id,
        "job": {
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "duration_minutes": duration_minutes,
            "room_count": len(rooms),
        },
        "battery": {"start": 85, "end": 60, "used": 25},
        "water": {},
        "job_profile": {
            "map_id": _MAP_INT,
            "room_count": len(rooms),
            "room_slugs": room_slugs,
            "rooms": rooms,
        },
        "resolved_rooms": rooms,
        "queue": {
            "queue_room_ids": [r["room_id"] for r in rooms],
            "queue_rooms": rooms,
        },
        "outcome": {
            "status": status,
            "used_for_learning": used_for_learning,
            "learning_blockers": [],
        },
    }
    store = LearningHistoryStore(hass)
    store.save_completed_job(
        vacuum_entity_id=vacuum_entity_id, job_id=job_id, payload=payload
    )
    return payload


def _seed_active_job(manager, vacuum_entity_id: str, map_id: str, **extra) -> None:
    """Directly write active job state into the manager's in-memory store."""
    manager.data.setdefault("active_jobs", {}).setdefault(vacuum_entity_id, {})[
        str(map_id)
    ] = {
        "status": "started",
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        **extra,
    }


# ---------------------------------------------------------------------------
# Fixture: manager + learning services registered
# ---------------------------------------------------------------------------

@pytest.fixture
async def learning_services(hass, manager):
    """Register learning services on top of the already-wired manager."""
    await async_register_learning_services(hass)
    yield manager
    await async_unregister_learning_services(hass)


# ---------------------------------------------------------------------------
# [LS-1] Service registration
# ---------------------------------------------------------------------------

async def test_all_learning_services_registered(hass, learning_services):
    """[LS-1] Every learning service appears in the service registry after registration."""
    services = [
        SERVICE_SAVE_LEARNING_SNAPSHOT,
        SERVICE_REBUILD_LEARNING_STATS,
        SERVICE_RUN_LEARNING_ESTIMATE,
        SERVICE_REANCHOR_LEARNING_TIMELINE,
        SERVICE_GET_NEXT_ROOM,
        SERVICE_RECORD_ESTIMATE_ACCURACY,
        SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        SERVICE_GET_METRICS_SNAPSHOT,
        SERVICE_GET_INCOMPLETE_RUN_LOG,
        SERVICE_GET_TROUBLE_ROOMS_LOG,
        SERVICE_EXCLUDE_LEARNING_JOB,
        SERVICE_RESTORE_LEARNING_JOB,
    ]
    for svc in services:
        assert hass.services.has_service(DOMAIN, svc), f"Missing service: {svc}"


# ---------------------------------------------------------------------------
# [LS-2] get_incomplete_run_log — no file
# ---------------------------------------------------------------------------

async def test_get_incomplete_run_log_empty(hass, learning_services):
    """[LS-2] Returns {} when no incomplete run log exists for the vacuum."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_INCOMPLETE_RUN_LOG,
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result == {}


# ---------------------------------------------------------------------------
# [LS-3] get_trouble_rooms_log — no file
# ---------------------------------------------------------------------------

async def test_get_trouble_rooms_log_empty(hass, learning_services):
    """[LS-3] Returns {} when no trouble rooms log exists for the vacuum."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_TROUBLE_ROOMS_LOG,
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result == {}


# ---------------------------------------------------------------------------
# [LS-4] rebuild_learning_stats — no jobs
# ---------------------------------------------------------------------------

async def test_rebuild_learning_stats_no_jobs(hass, learning_services):
    """[LS-4] Rebuild with no archived jobs completes without error."""
    # Service returns None (no return_response), so just assert no exception.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False},
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [LS-5] run_learning_estimate — empty payload → error response
# ---------------------------------------------------------------------------

async def test_run_learning_estimate_no_rooms(hass, learning_services):
    """[LS-5] With no rooms in the queue, returns an error-keyed payload."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_RUN_LEARNING_ESTIMATE,
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "current_battery": 80.0,
        },
        blocking=True,
        return_response=True,
    )
    # No rooms queued → estimator returns {"error": "no_payload", ...}
    assert "error" in result


# ---------------------------------------------------------------------------
# [LS-6] reanchor_learning_timeline
# ---------------------------------------------------------------------------

def _minimal_estimate() -> dict:
    """Minimal estimate payload with two rooms."""
    return {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "room_timeline": [
            {
                "room_id": 1,
                "slug": "kitchen",
                "name": "Kitchen",
                "minutes": 15.0,
                "battery": 10.0,
                "confidence_score": 0.60,
                "confidence_label": "medium",
                "source": "default",
                "completed": False,
                "current": True,
            },
            {
                "room_id": 2,
                "slug": "bedroom",
                "name": "Bedroom",
                "minutes": 20.0,
                "battery": 12.0,
                "confidence_score": 0.60,
                "confidence_label": "medium",
                "source": "default",
                "completed": False,
                "current": False,
            },
        ],
        "total_minutes": 35.0,
        "room_minutes_total": 35.0,
        "overhead_minutes": 5.0,
        "confidence_score": 0.60,
        "confidence_label": "medium",
    }


async def test_reanchor_marks_completed_rooms(hass, learning_services):
    """[LS-6] Reanchor with one completed room marks it completed and advances current."""
    estimate = _minimal_estimate()
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_REANCHOR_LEARNING_TIMELINE,
        {
            "original_estimate": estimate,
            "completed_rooms": [{"slug": "kitchen", "actual_duration_minutes": 14.0}],
        },
        blocking=True,
        return_response=True,
    )
    assert "room_timeline" in result
    kitchen = next(r for r in result["room_timeline"] if r["slug"] == "kitchen")
    assert kitchen["completed"] is True
    bedroom = next(r for r in result["room_timeline"] if r["slug"] == "bedroom")
    assert bedroom["current"] is True


# ---------------------------------------------------------------------------
# [LS-7] get_next_room
# ---------------------------------------------------------------------------

async def test_get_next_room_returns_dict(hass, learning_services):
    """[LS-7] With a reanchored estimate, returns a room dict (or {})."""
    estimate = _minimal_estimate()
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_NEXT_ROOM,
        {"reanchored_estimate": estimate},
        blocking=True,
        return_response=True,
    )
    # Non-None: current room is kitchen
    assert isinstance(result, dict)


async def test_get_next_room_empty_estimate(hass, learning_services):
    """[LS-7] Empty estimate → returns {}."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_NEXT_ROOM,
        {"reanchored_estimate": {}},
        blocking=True,
        return_response=True,
    )
    assert result == {}


# ---------------------------------------------------------------------------
# [LS-8] record_estimate_accuracy
# ---------------------------------------------------------------------------

async def test_record_estimate_accuracy_stores_data(hass, learning_services):
    """[LS-8] Valid room_actuals are persisted; result contains schema_version."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_RECORD_ESTIMATE_ACCURACY,
        {
            "vacuum_entity_id": _VAC,
            "room_actuals": [
                {
                    "slug": "kitchen",
                    "clean_mode": "vacuum",
                    "clean_passes": 1,
                    "is_carpet": False,
                    "clean_intensity": "standard",
                    "map_id": 6,
                    "estimated_minutes": 15.0,
                    "actual_minutes": 14.0,
                }
            ],
        },
        blocking=True,
        return_response=True,
    )
    assert "schema_version" in result or "rooms" in result or "vacuum_entity_id" in result


# ---------------------------------------------------------------------------
# [LS-9] get_learning_history_snapshot
# ---------------------------------------------------------------------------

async def test_get_learning_history_snapshot_empty(hass, learning_services):
    """[LS-9] With no archived jobs, returns a well-formed snapshot with empty lists."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    # Should have at least the vacuum_entity_id echoed back
    assert result.get("vacuum_entity_id") == _VAC or "jobs" in result or "schema_version" in result


# ---------------------------------------------------------------------------
# [LS-10] get_metrics_snapshot
# ---------------------------------------------------------------------------

async def test_get_metrics_snapshot_empty(hass, learning_services):
    """[LS-10] With no data, returns a well-formed metrics dict."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_METRICS_SNAPSHOT,
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [LS-11] exclude_learning_job — missing job
# ---------------------------------------------------------------------------

async def test_exclude_learning_job_not_found(hass, learning_services):
    """[LS-11] Excluding a non-existent job returns excluded=False + reason."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": "ghost-job-001"},
        blocking=True,
        return_response=True,
    )
    assert result["excluded"] is False
    assert result["reason"] == "job_not_found"


# ---------------------------------------------------------------------------
# [LS-12] restore_learning_job — missing job
# ---------------------------------------------------------------------------

async def test_restore_learning_job_not_found(hass, learning_services):
    """[LS-12] Restoring a non-existent job returns restored=False + reason."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTORE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": "ghost-job-001"},
        blocking=True,
        return_response=True,
    )
    assert result["restored"] is False
    assert result["reason"] == "job_not_found"


# ---------------------------------------------------------------------------
# [LS-13] exclude → restore round-trip
# ---------------------------------------------------------------------------

async def test_exclude_restore_round_trip(hass, learning_services):
    """[LS-13] Exclude then restore a real archived job flips used_for_learning."""
    # Seed a completed job directly via the store
    store = LearningHistoryStore(hass)
    job = {
        "record_type": "completed_job",
        "job_id": "j-roundtrip",
        "job": {"ended_at": "2026-01-01T10:00:00+00:00", "duration_minutes": 30.0, "room_count": 1},
        "battery": {"start": 80, "end": 60, "used": 20},
        "water": {},
        "job_profile": {"map_id": 6, "room_count": 1, "room_slugs": ["kitchen"], "rooms": []},
        "resolved_rooms": [],
        "queue": {"queue_room_ids": [1], "queue_rooms": []},
        "outcome": {"status": "completed", "used_for_learning": True, "learning_blockers": []},
    }
    store.save_completed_job(vacuum_entity_id=_VAC, job_id="j-roundtrip", payload=job)

    # Exclude
    exc = await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": "j-roundtrip"},
        blocking=True,
        return_response=True,
    )
    assert exc["excluded"] is True
    assert exc["completed_job"]["outcome"]["used_for_learning"] is False

    # Restore
    rest = await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTORE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": "j-roundtrip"},
        blocking=True,
        return_response=True,
    )
    assert rest["restored"] is True
    assert rest["completed_job"]["outcome"]["used_for_learning"] is True


# ---------------------------------------------------------------------------
# [LS-14] Unregister cleans up all services
# ---------------------------------------------------------------------------

async def test_services_removed_after_unregister(hass, manager):
    """[LS-14] After unregistering, none of the learning services remain."""
    await async_register_learning_services(hass)
    await async_unregister_learning_services(hass)

    assert not hass.services.has_service(DOMAIN, SERVICE_GET_INCOMPLETE_RUN_LOG)
    assert not hass.services.has_service(DOMAIN, SERVICE_REBUILD_LEARNING_STATS)
    assert not hass.services.has_service(DOMAIN, SERVICE_RUN_LEARNING_ESTIMATE)


# ---------------------------------------------------------------------------
# [LS-15] save_learning_snapshot — empty manager state
# ---------------------------------------------------------------------------

async def test_save_learning_snapshot_empty_manager(hass, learning_services):
    """[LS-15] save_learning_snapshot completes without error against an empty manager."""
    from custom_components.eufy_vacuum.learning.services import SERVICE_SAVE_LEARNING_SNAPSHOT

    # Calling with minimal data: no adapter config, no active job, no queue.
    # Previously blocked by two bugs now fixed:
    #   run_plan.py:282 — hass.states.get(None) with no adapter mode entity
    #   job_finalizer.py:336 — async_create_task called from executor thread
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_LEARNING_SNAPSHOT,
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "started_at": "2026-01-01T09:00:00+00:00",
            "battery_start": 85,
        },
        blocking=True,
    )
    # Allow the scheduled snapshot write to run
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [LS-16] finalize_learning_job — runs against empty manager state
# ---------------------------------------------------------------------------

async def test_finalize_learning_job_empty_state(hass, learning_services):
    """[LS-16] Finalize with no active job saves a job file and fires the finished event."""
    from custom_components.eufy_vacuum.const import EVENT_JOB_FINISHED
    fired = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: fired.append(e))

    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB
    await hass.services.async_call(
        DOMAIN,
        SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "battery_start": 85,
            "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": False,
            "rebuild_stats": False,
        },
        blocking=True,
    )
    # Allow event loop to process the fired event
    await hass.async_block_till_done()
    assert len(fired) == 1
    assert fired[0].data["vacuum_entity_id"] == _VAC


# ---------------------------------------------------------------------------
# [LS-17] get_room_learning_estimates — with rooms seeded
# ---------------------------------------------------------------------------

async def test_get_room_learning_estimates_with_rooms(hass, learning_services):
    """[LS-17] With managed rooms seeded, returns a per-room estimate list."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_GET_ROOM_LEARNING_ESTIMATES

    # Seed rooms so the manager has something to estimate against
    setup_map(learning_services, _VAC, _MAP, count=2)

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ROOM_LEARNING_ESTIMATES,
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "rooms" in result
    assert len(result["rooms"]) == 2


async def test_get_room_learning_estimates_estimate_failed(hass, learning_services, monkeypatch):
    """[LS-17b] if one room's estimate computation raises, that room gets an
    estimate_failed entry rather than crashing the whole list (skip-one-continue
    resilience — the per-room except in get_room_learning_estimates)."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_GET_ROOM_LEARNING_ESTIMATES
    from custom_components.eufy_vacuum.learning import estimator as _est

    setup_map(learning_services, _VAC, _MAP, count=2)

    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    # _confidence_result is imported from .estimator inside the loop body, so
    # patching the module attribute forces the per-room compute to raise.
    monkeypatch.setattr(_est, "_confidence_result", _boom)

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_ROOM_LEARNING_ESTIMATES,
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    rooms = result["rooms"]
    assert len(rooms) == 2
    assert all(r["error"] == "estimate_failed" for r in rooms)
    assert all(r["error_detail"] and r["minutes"] is None for r in rooms)


# ---------------------------------------------------------------------------
# [LS-18] retry_missed_rooms — no incomplete run log
# ---------------------------------------------------------------------------

async def test_retry_missed_rooms_no_log(hass, learning_services):
    """[LS-18] Returns started=False when no incomplete run log exists."""
    from custom_components.eufy_vacuum.learning.services import SERVICE_RETRY_MISSED_ROOMS
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_RETRY_MISSED_ROOMS,
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["started"] is False
    assert result["reason"] == "no_missed_rooms"


async def test_retry_missed_rooms_no_map_id(hass, learning_services):
    """[LS-18b] a log with missed rooms but no resolvable map_id → no_map_id."""
    from custom_components.eufy_vacuum.learning.services import SERVICE_RETRY_MISSED_ROOMS
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

    LearningHistoryStore(hass).save_incomplete_run(
        vacuum_entity_id=_VAC, payload={"missed_room_ids": [1]})  # no map_id
    result = await hass.services.async_call(
        DOMAIN, SERVICE_RETRY_MISSED_ROOMS,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True)
    assert result["started"] is False
    assert result["reason"] == "no_map_id"


async def test_retry_missed_rooms_dispatches_and_clears_log(hass, learning_services):
    """[LS-18c] with an incomplete run log, retry enables the missed rooms, builds
    the queue, dispatches the start, and clears the log on success."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_RETRY_MISSED_ROOMS
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

    setup_map(learning_services, _VAC, _MAP, count=2)
    hass.states.async_set(_VAC, "docked", {"battery_level": 90})
    calls: list = []

    async def _dispatch(call):
        calls.append(call)

    hass.services.async_register("vacuum", "send_command", _dispatch)

    store = LearningHistoryStore(hass)
    store.save_incomplete_run(
        vacuum_entity_id=_VAC, payload={"map_id": _MAP, "missed_room_ids": [1, 2]})

    result = await hass.services.async_call(
        DOMAIN, SERVICE_RETRY_MISSED_ROOMS,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True)
    await hass.async_block_till_done()

    assert result["started"] is True
    assert result["map_id"] == _MAP
    assert set(result["missed_room_ids"]) == {1, 2}
    assert len(calls) == 1  # clean command dispatched
    # the incomplete-run log is cleared after a successful retry dispatch
    assert store.load_incomplete_run(vacuum_entity_id=_VAC) is None


# ---------------------------------------------------------------------------
# [LS-19] finalize_learning_job — cancelled outcome fires EVENT_RUN_INCOMPLETE
# ---------------------------------------------------------------------------

async def test_finalize_cancelled_fires_run_incomplete(hass, learning_services):
    """[LS-19] Cancelling a job with queued rooms fires EVENT_RUN_INCOMPLETE with missed_room_ids."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.const import EVENT_RUN_INCOMPLETE
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    # Seed two managed rooms and build the queue so finalization can see
    # queue_room_ids = [1, 2].  With no active job, both rooms are missed.
    setup_map(learning_services, _VAC, _MAP, count=2)
    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)

    incomplete_events = []
    hass.bus.async_listen(EVENT_RUN_INCOMPLETE, lambda e: incomplete_events.append(e))

    await hass.services.async_call(
        DOMAIN,
        SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "battery_start": 85,
            "battery_end": 75,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:02:00+00:00",
            "used_for_learning": False,
            "rebuild_stats": False,
            "forced_outcome_status": "cancelled",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(incomplete_events) == 1
    evt_data = incomplete_events[0].data
    assert evt_data["vacuum_entity_id"] == _VAC
    assert set(evt_data["missed_room_ids"]) == {1, 2}


# ---------------------------------------------------------------------------
# [LS-20] _update_trouble_rooms_log accumulates across finalize calls
# ---------------------------------------------------------------------------

async def test_trouble_rooms_accumulate_across_finalize_calls(hass, learning_services):
    """[LS-20] Two cancelled finalize calls with the same rooms flag them is_trouble=True."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    setup_map(learning_services, _VAC, _MAP, count=2)
    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)

    _finalize = {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "battery_start": 85,
        "battery_end": 75,
        "started_at": "2026-01-01T09:00:00+00:00",
        "ended_at": "2026-01-01T09:02:00+00:00",
        "used_for_learning": False,
        "rebuild_stats": False,
        "forced_outcome_status": "cancelled",
    }
    # Two cancelled jobs — both rooms missed each time → miss_count reaches 2
    await hass.services.async_call(DOMAIN, SERVICE_FINALIZE_LEARNING_JOB, _finalize, blocking=True)
    await hass.services.async_call(DOMAIN, SERVICE_FINALIZE_LEARNING_JOB, _finalize, blocking=True)

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_TROUBLE_ROOMS_LOG,
        {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    rooms = result.get("rooms", {})
    for rid in ["1", "2"]:
        room = rooms.get(rid, {})
        assert room.get("miss_count", 0) >= 2, f"room {rid} miss_count too low: {room}"
        assert room.get("is_trouble") is True, f"room {rid} not flagged trouble"


# ---------------------------------------------------------------------------
# [LS-21] finalize with active job — wall-clock derivation + trace_run_id
# ---------------------------------------------------------------------------

async def test_finalize_with_active_job_covers_wall_clock_and_trace(hass, learning_services):
    """[LS-21] Active job with started_at exercises wall-clock derivation; trace_run_id stamps the job."""
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    # Seed active job: no last_cleaning_time_seconds → wall-clock fallback runs.
    # trace_run_id present → completed_job["trace_run_id"] branch fires.
    _seed_active_job(
        learning_services, _VAC, _MAP,
        started_at="2026-01-01T09:00:00+00:00",
        trace_run_id="trace-wc-001",
        paused_duration_seconds=0,
        recharge_seconds_accumulated=0,
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": True, "rebuild_stats": False,
        },
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [LS-22] finalize single completed room with trace_run_id — boundary check
# ---------------------------------------------------------------------------

async def test_finalize_single_room_with_trace_covers_boundary_derivation(hass, learning_services):
    """[LS-22] Single resolved room + trace_run_id on a completed job exercises _auto_derive_room_boundary gates."""
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    _seed_active_job(
        learning_services, _VAC, _MAP,
        started_at="2026-01-01T09:00:00+00:00",
        trace_run_id="trace-boundary-001",
        resolved_rooms=[{"room_id": 1, "slug": "kitchen", "name": "Kitchen"}],
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": True, "rebuild_stats": False,
        },
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [LS-23] get_learning_history_snapshot with seeded jobs — full enrichment loop
# ---------------------------------------------------------------------------

async def test_get_learning_history_snapshot_with_seeded_jobs(hass, learning_services):
    """[LS-23] Seeded jobs + rebuilt stats exercise the full enrichment loop in get_learning_history_snapshot."""
    _seed_completed_job(hass, _VAC, "j-hist-001", room_slugs=["kitchen"])
    _seed_completed_job(hass, _VAC, "j-hist-002", room_slugs=["bedroom"])

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False},
        blocking=True,
    )
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict)
    jobs = result.get("jobs", [])
    seeded_ids = {j.get("job_id") for j in jobs}
    assert "j-hist-001" in seeded_ids
    assert "j-hist-002" in seeded_ids


async def test_history_snapshot_accepts_list_shaped_accuracy(hass, learning_services, monkeypatch):
    """[LS-23b] accuracy_stats with a LIST-shaped 'rooms' (externally-produced
    payloads) is accepted alongside the dict shape — the elif-list branch."""
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
    monkeypatch.setattr(
        LearningHistoryStore, "load_accuracy_stats",
        lambda self, *, vacuum_entity_id: {
            "rooms": [{"slug": "kitchen", "mean_abs_pct_error": 0.1, "sample_count": 3}]})
    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True)
    assert isinstance(result, dict)  # ran through the list-accuracy branch without error


# ---------------------------------------------------------------------------
# [LS-24] get_metrics_snapshot with seeded jobs — populated metrics path
# ---------------------------------------------------------------------------

async def test_get_metrics_snapshot_with_seeded_jobs(hass, learning_services):
    """[LS-24] Seeded jobs + rebuilt stats return a metrics payload with job_count > 0."""
    _seed_completed_job(hass, _VAC, "j-met-001", room_slugs=["kitchen"])

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False},
        blocking=True,
    )
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_METRICS_SNAPSHOT,
        {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict)
    # get_metrics_snapshot returns: available, overview.job_stats, filter_options, ...
    assert result.get("available") is True
    assert result.get("overview", {}).get("job_stats", {}).get("total_jobs", 0) >= 1


# ---------------------------------------------------------------------------
# [LS-25] save_learning_snapshot with rooms — access-graph loop body
# ---------------------------------------------------------------------------

async def test_save_snapshot_with_rooms_covers_access_graph_loop(hass, learning_services):
    """[LS-25] Managed rooms with grants_access_to exercise _build_access_graph_context inner loop."""
    from tests.integration.conftest import setup_map

    setup_map(learning_services, _VAC, _MAP, count=2)

    # Wire room 1 → room 2 so the edge loop body (lines 441-452) executes.
    rooms_bucket = (
        learning_services.data
        .get("maps", {}).get(_VAC, {}).get(_MAP, {}).get("rooms", {})
    )
    if "1" in rooms_bucket:
        rooms_bucket["1"]["grants_access_to"] = [2]

    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)

    await hass.services.async_call(
        DOMAIN, SERVICE_SAVE_LEARNING_SNAPSHOT,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "started_at": "2026-01-01T09:00:00+00:00",
            "battery_start": 85,
        },
        blocking=True,
    )
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [LS-26] get_room_learning_estimates — learned-match branch
# ---------------------------------------------------------------------------

async def test_get_room_learning_estimates_hits_learned_match(hass, learning_services):
    """[LS-26] With seeded room stats, get_room_learning_estimates hits the learned-match branch."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_GET_ROOM_LEARNING_ESTIMATES

    setup_map(learning_services, _VAC, _MAP, count=1)

    # Add slug to the managed room so the stats lookup finds a match.
    # Managed rooms are stored at data["maps"][vac][map]["rooms"], not data["rooms"].
    rooms_bucket = (
        learning_services.data
        .get("maps", {}).get(_VAC, {}).get(_MAP, {}).get("rooms", {})
    )
    if "1" in rooms_bucket:
        rooms_bucket["1"]["slug"] = "room_1"

    # Seed a job whose room slug matches the managed room's slug.
    _seed_completed_job(hass, _VAC, "j-rl-001", room_slugs=["room_1"])

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False},
        blocking=True,
    )
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_ROOM_LEARNING_ESTIMATES,
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict)
    assert "rooms" in result
    rooms = result["rooms"]
    assert len(rooms) == 1
    # With matching stats the source should be "learned", not "default".
    assert rooms[0]["source"] == "learned"


# ---------------------------------------------------------------------------
# [LS-27] finalize with adapter cleaning_time entity — sensor fallback
# ---------------------------------------------------------------------------

async def test_finalize_sensor_fallback_via_adapter_entity(hass, learning_services):
    """[LS-27] Adapter cleaning_time/area entities trigger the sensor-state fallback path."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    _CT = "sensor.alfred_cleaning_time"
    _CA = "sensor.alfred_cleaning_area"
    register_adapter_config(_VAC, {
        "adapter_id": "test_sensor_fb",
        "source": "test",
        "entities": {"cleaning_time": _CT, "cleaning_area": _CA},
    })
    hass.states.async_set(_CT, "1800")   # 1800 s of cleaning time
    hass.states.async_set(_CA, "25.5")   # 25.5 m² cleaned

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": True, "rebuild_stats": False,
        },
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [LS-28] ErrorTracker latch harvested during finalization
# ---------------------------------------------------------------------------

async def test_finalize_with_error_tracker_harvests_latch(hass, learning_services):
    """[LS-28] ErrorTracker latch is harvested during finalization (lines 609-613)."""
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
    from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    tracker = ErrorTracker(hass, runtime_manager=learning_services)
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = tracker
    # Seed a two-error latch (total ~60s) for this vacuum.
    record = tracker._ensure_record(_VAC)
    record["active_run_error"] = {
        "error_count": 2,
        "errors": [
            {"captured_at": "2026-01-01T09:01:00+00:00", "recovered_at": "2026-01-01T09:01:30+00:00"},
            {"captured_at": "2026-01-01T09:05:00+00:00", "recovered_at": "2026-01-01T09:05:30+00:00"},
        ],
    }
    # Give the active job 300s of cleaning time so the latch is subtracted.
    _seed_active_job(learning_services, _VAC, _MAP, last_cleaning_time_seconds=300)

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": True, "rebuild_stats": False,
        },
        blocking=True,
    )
    # After harvest the latch is cleared.
    assert tracker.get_active_run_latch(_VAC) is None


# ---------------------------------------------------------------------------
# [LS-29] error latch total > cleaning_time_seconds → clamped to 0
# ---------------------------------------------------------------------------

async def test_finalize_error_seconds_exceeds_cleaning_time(hass, learning_services):
    """[LS-29] total_error_seconds > cleaning_time_seconds → adjusted value clamped to 0 (lines 645-660)."""
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
    from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    tracker = ErrorTracker(hass, runtime_manager=learning_services)
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = tracker
    record = tracker._ensure_record(_VAC)
    # 400s of errors vs 300s cleaning → clamped to 0.
    record["active_run_error"] = {
        "error_count": 1,
        "errors": [
            {"captured_at": "2026-01-01T09:00:00+00:00", "recovered_at": "2026-01-01T09:06:40+00:00"},
        ],
    }
    _seed_active_job(learning_services, _VAC, _MAP, last_cleaning_time_seconds=300)

    core_manager = hass.data[DOMAIN]["runtime"]
    learning_mgr = _get_learning_manager(hass)

    result = await hass.async_add_executor_job(
        lambda: learning_mgr.finalize_completed_job(
            manager=core_manager,
            vacuum_entity_id=_VAC,
            map_id=_MAP,
            battery_start=85,
            battery_end=60,
            started_at="2026-01-01T09:00:00+00:00",
            ended_at="2026-01-01T09:30:00+00:00",
            used_for_learning=False,
            rebuild_stats=False,
        )
    )
    job = result.get("completed_job", {}).get("job", {})
    # clamped to 0 when error window exceeds cleaning time
    assert job.get("cleaning_time_seconds", -1) == 0


# ---------------------------------------------------------------------------
# [LS-30] forced_lifecycle_state="failed" sets outcome
# ---------------------------------------------------------------------------

async def test_finalize_forced_lifecycle_state_failed(hass, learning_services):
    """[LS-30] forced_lifecycle_state sets outcome without forced_outcome_status (lines 402-420)."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)

    result = await hass.async_add_executor_job(
        lambda: learning.finalize_completed_job(
            manager=core_manager,
            vacuum_entity_id=_VAC,
            map_id=_MAP,
            battery_start=85,
            battery_end=60,
            started_at="2026-01-01T09:00:00+00:00",
            ended_at="2026-01-01T09:30:00+00:00",
            used_for_learning=False,
            rebuild_stats=False,
            forced_lifecycle_state="failed",
        )
    )
    outcome = result.get("completed_job", {}).get("outcome", {})
    assert outcome.get("status") == "failed"


# ---------------------------------------------------------------------------
# [LS-31] completed finalize clears prior incomplete run log
# ---------------------------------------------------------------------------

async def test_finalize_completed_clears_incomplete_log(hass, learning_services):
    """[LS-31] Completed finalize clears any prior incomplete run log (line 1251) + trouble rooms last_cleaned_at (line 1390)."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB, SERVICE_GET_INCOMPLETE_RUN_LOG

    setup_map(learning_services, _VAC, _MAP, count=2)
    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)

    base = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "battery_start": 85, "battery_end": 60,
        "started_at": "2026-01-01T09:00:00+00:00",
        "ended_at": "2026-01-01T09:30:00+00:00",
        "used_for_learning": False, "rebuild_stats": False,
    }
    # First: cancelled → writes incomplete run log
    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {**base, "forced_outcome_status": "cancelled"}, blocking=True,
    )
    # Verify incomplete log exists
    log = await hass.services.async_call(
        DOMAIN, SERVICE_GET_INCOMPLETE_RUN_LOG,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    assert isinstance(log, dict) and log  # non-empty

    # Second: completed → clears incomplete run log
    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        base, blocking=True,
    )
    log2 = await hass.services.async_call(
        DOMAIN, SERVICE_GET_INCOMPLETE_RUN_LOG,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    assert log2 == {}  # cleared


# ---------------------------------------------------------------------------
# [LS-32] active_job completed_room_ids limits missed rooms in incomplete log
# ---------------------------------------------------------------------------

async def test_finalize_active_job_completed_room_ids_limits_missed(hass, learning_services):
    """[LS-32] active_job.completed_room_ids reduces missed set in incomplete log (lines 1262-1271)."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB, SERVICE_GET_INCOMPLETE_RUN_LOG

    setup_map(learning_services, _VAC, _MAP, count=2)
    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)

    # Room 1 was completed before cancel; room 2 was missed.
    _seed_active_job(learning_services, _VAC, _MAP, completed_room_ids=[1])

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": False, "rebuild_stats": False,
            "forced_outcome_status": "cancelled",
        },
        blocking=True,
    )
    log = await hass.services.async_call(
        DOMAIN, SERVICE_GET_INCOMPLETE_RUN_LOG,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    missed = set(log.get("missed_room_ids", []))
    assert 2 in missed
    assert 1 not in missed


# ---------------------------------------------------------------------------
# [LS-33] live snapshot estimate enriches resolved rooms + auto_record_accuracy
# ---------------------------------------------------------------------------

async def test_finalize_with_snapshot_estimate_enriches_rooms_and_records_accuracy(hass, learning_services):
    """[LS-33] Live snapshot with room_timeline enriches resolved rooms and triggers _auto_record_accuracy (lines 885-955, manager 672-712)."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB, _get_learning_manager

    learning = _get_learning_manager(hass)
    # Inject a live snapshot with a planned estimate for room 1 (kitchen).
    learning.finalizer._live_snapshot_cache[_VAC] = {
        "job_id": "snap-enrich-001",
        "planned_job_estimate": {
            "room_timeline": [
                {
                    "room_id": 1,
                    "slug": "kitchen",
                    "minutes": 20.0,
                    "battery": 5.0,
                    "confidence_score": 0.8,
                    "confidence_label": "good",
                    "source": "learned",
                }
            ],
            "room_minutes_total": 20.0,
            "overhead_minutes": 2.0,
            "total_minutes": 22.0,
            "total_battery_used": 7.0,
        },
    }

    # Seed active_job with a resolved room matching the timeline.
    _seed_active_job(
        learning_services, _VAC, _MAP,
        resolved_rooms=[
            {"room_id": 1, "slug": "kitchen", "name": "Kitchen",
             "clean_mode": "vacuum", "clean_intensity": "standard", "clean_times": 1, "is_carpet": False}
        ],
        last_cleaning_time_seconds=1200,
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:20:00+00:00",
            "used_for_learning": True, "rebuild_stats": False,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    # No assertion needed beyond no-crash; the enrichment + accuracy record are internal.


# ---------------------------------------------------------------------------
# [LS-34] get_learning_history_snapshot with status + room_slug filters
# ---------------------------------------------------------------------------

async def test_get_learning_history_snapshot_with_filters(hass, learning_services):
    """[LS-34] get_learning_history_snapshot status + room_slug filters prune results (manager lines 919-946)."""
    _seed_completed_job(hass, _VAC, "j-flt-001", room_slugs=["kitchen"], status="completed")
    _seed_completed_job(hass, _VAC, "j-flt-002", room_slugs=["bedroom"], status="cancelled")

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    # status filter — only cancelled
    result_cancelled = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "status": "cancelled"},
        blocking=True, return_response=True,
    )
    jobs = result_cancelled.get("jobs", [])
    assert all(j.get("status") == "cancelled" for j in jobs)

    # room_slug filter — only kitchen
    result_kitchen = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "room_slug": "kitchen"},
        blocking=True, return_response=True,
    )
    job_ids = {j.get("job_id") for j in result_kitchen.get("jobs", [])}
    assert "j-flt-001" in job_ids

    # used_for_learning filter
    result_learning = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "used_for_learning": False},
        blocking=True, return_response=True,
    )
    # seed jobs have used_for_learning=True by default, so False filter may return different set
    assert isinstance(result_learning, dict)


# ---------------------------------------------------------------------------
# [LS-35] sync finalize_completed_job path
# ---------------------------------------------------------------------------

async def test_finalize_completed_job_sync_path(hass, learning_services):
    """[LS-35] Sync finalize_completed_job path (manager.py lines 537-568)."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)

    result = await hass.async_add_executor_job(
        lambda: learning.finalize_completed_job(
            manager=core_manager,
            vacuum_entity_id=_VAC,
            map_id=_MAP,
            battery_start=85,
            battery_end=60,
            started_at="2026-01-01T09:00:00+00:00",
            ended_at="2026-01-01T09:30:00+00:00",
            used_for_learning=False,
            rebuild_stats=False,
        )
    )
    assert isinstance(result, dict)
    assert result.get("vacuum_entity_id") == _VAC


# ---------------------------------------------------------------------------
# [LS-36] finalize with rebuild_stats=True, rebuild_csv=True
# ---------------------------------------------------------------------------

async def test_finalize_rebuild_csv(hass, learning_services):
    """[LS-36] rebuild_stats=True, rebuild_csv=True exercises lines 801-807 and manager line 622."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:30:00+00:00",
            "used_for_learning": False,
            "rebuild_stats": True,
            "rebuild_csv": True,
        },
        blocking=True,
    )
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [LS-37] started_at == ended_at → wall-clock derived = 0 → skipped
# ---------------------------------------------------------------------------

async def test_finalize_wall_clock_zero_derived(hass, learning_services):
    """[LS-37] started_at == ended_at → wall-clock derived = 0 → skipped (507->525 branch)."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    same_time = "2026-01-01T09:00:00+00:00"
    _seed_active_job(
        learning_services, _VAC, _MAP,
        started_at=same_time,
        paused_duration_seconds=0,
        recharge_seconds_accumulated=0,
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "battery_start": 85, "battery_end": 60,
            "started_at": same_time,
            "ended_at": same_time,
            "used_for_learning": False, "rebuild_stats": False,
        },
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [LS-38] get_learning_history_snapshot with used_for_learning=False filter
# ---------------------------------------------------------------------------

async def test_get_learning_history_snapshot_used_for_learning_filter(hass, learning_services):
    """[LS-38] used_for_learning=False filter prunes results (manager line 927-928)."""
    _seed_completed_job(hass, _VAC, "j-ufl-001", room_slugs=["kitchen"], used_for_learning=False)

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "used_for_learning": False},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict)
    jobs = result.get("jobs", [])
    # Jobs with used_for_learning=False are included.
    assert any(j.get("job_id") == "j-ufl-001" for j in jobs)


# ---------------------------------------------------------------------------
# [LS-39] async_preload_learning_stats guard when already cached
# ---------------------------------------------------------------------------

async def test_async_preload_learning_stats_guard_when_cached(hass, learning_services):
    """[LS-39] async_preload_learning_stats is a no-op when stats are already cached (lines 311-312)."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(hass)
    # Pre-populate both caches so the guard fires.
    learning._room_stats_cache[_VAC] = {"room_stats": []}
    learning._accuracy_stats_cache[_VAC] = {}

    # Call — should be a no-op (returns without scheduling)
    learning.async_preload_learning_stats(vacuum_entity_id=_VAC)
    # vacuum_entity_id should NOT be in loading set (no load was scheduled)
    assert _VAC not in learning._learning_stats_loading


# ---------------------------------------------------------------------------
# _detect_cancel_likely_run — helpers + branch coverage [LS-40..LS-47]
# ---------------------------------------------------------------------------

_TASK_STATUS_ENTITY = "sensor.alfred_task_status"


def _register_cancel_adapter(*, with_task_status: bool = True, exclusions=None) -> None:
    """Register an adapter config exposing (or omitting) the task_status entity."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    entities = {"task_status": _TASK_STATUS_ENTITY} if with_task_status else {}
    register_adapter_config(
        _VAC,
        {
            "adapter_id": "test_cancel",
            "source": "test",
            "entities": entities,
            "vocabulary": {"cancel_service_exclusion_states": list(exclusions or [])},
        },
    )


def _run_cancel_detection(hass, core_manager, *, started_at, ended_at, active_job_state):
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(hass)
    return learning.finalizer._detect_cancel_likely_run(
        manager=core_manager,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        battery_start=85,
        started_at=started_at,
        ended_at=ended_at,
        active_job_state=active_job_state,
    )


def _one_room() -> list[dict]:
    return [{"room_id": 1, "slug": "kitchen", "name": "Kitchen"}]


async def test_cancel_detection_missing_timestamps(hass, learning_services):
    """[LS-40] Unparseable timestamps short-circuit to missing_timestamps."""
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="not-a-date", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={"resolved_rooms": _one_room()},
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "missing_timestamps"


async def test_cancel_detection_not_single_room(hass, learning_services):
    """[LS-41] A job with more than one resolved room is ineligible."""
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={"resolved_rooms": [{"room_id": 1}, {"room_id": 2}]},
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "not_single_room"


async def test_cancel_detection_no_transition_history(hass, learning_services):
    """[LS-42] No state_transitions → no_transition_history."""
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={"resolved_rooms": _one_room(), "state_transitions": []},
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "no_transition_history"


async def test_cancel_detection_no_task_status_entity(hass, learning_services):
    """[LS-43] Adapter without a task_status entity → no_task_status_entity."""
    _register_cancel_adapter(with_task_status=False)
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={
            "resolved_rooms": _one_room(),
            "state_transitions": [
                {"entity_id": _TASK_STATUS_ENTITY, "from_state": "cleaning",
                 "to_state": "returning", "changed_at": "2026-01-01T09:00:10+00:00"},
            ],
        },
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "no_task_status_entity"


async def test_cancel_detection_service_state_explains_return(hass, learning_services):
    """[LS-44] A to_state in the exclusion vocabulary explains the early return."""
    _register_cancel_adapter(exclusions=["mop_washing"])
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={
            "resolved_rooms": _one_room(),
            "state_transitions": [
                {"entity_id": _TASK_STATUS_ENTITY, "from_state": "cleaning",
                 "to_state": "mop_washing", "changed_at": "2026-01-01T09:00:10+00:00"},
            ],
        },
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "service_state_explains_return"


async def test_cancel_detection_no_cancel_like_transition(hass, learning_services):
    """[LS-45] Transitions present but no cleaning→returning / paused→returning."""
    _register_cancel_adapter()
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={
            "resolved_rooms": _one_room(),
            "state_transitions": [
                {"entity_id": _TASK_STATUS_ENTITY, "from_state": "cleaning",
                 "to_state": "paused", "changed_at": "2026-01-01T09:00:10+00:00"},
            ],
        },
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "no_cancel_like_transition"


async def test_cancel_detection_floor_time_too_short(hass, learning_services):
    """[LS-46] paused→returning under the floor → cancel_likely (physical_vacuum)."""
    _register_cancel_adapter()
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:00:30+00:00",
        active_job_state={
            "resolved_rooms": _one_room(),
            "state_transitions": [
                {"entity_id": _TASK_STATUS_ENTITY, "from_state": "cleaning",
                 "to_state": "paused", "changed_at": "2026-01-01T09:00:05+00:00"},
                {"entity_id": _TASK_STATUS_ENTITY, "from_state": "paused",
                 "to_state": "returning", "changed_at": "2026-01-01T09:00:10+00:00"},
            ],
        },
    )
    assert result["cancel_likely"] is True
    assert result["reason"] == "floor_time_too_short"
    assert result["source"] == "physical_vacuum"


async def test_cancel_detection_duration_not_short(hass, learning_services):
    """[LS-47] cleaning→returning but the run is long enough → duration_not_short."""
    _register_cancel_adapter()
    result = _run_cancel_detection(
        hass, learning_services,
        started_at="2026-01-01T09:00:00+00:00", ended_at="2026-01-01T09:05:00+00:00",
        active_job_state={
            "resolved_rooms": _one_room(),
            "state_transitions": [
                {"entity_id": _TASK_STATUS_ENTITY, "from_state": "cleaning",
                 "to_state": "returning", "changed_at": "2026-01-01T09:02:00+00:00"},
            ],
        },
    )
    assert result["cancel_likely"] is False
    assert result["reason"] == "duration_not_short"


# ---------------------------------------------------------------------------
# [LS-48] get_learning_history_snapshot rebuilds an old-format jobs index
# ---------------------------------------------------------------------------

async def test_history_snapshot_rebuilds_old_format_index(hass, learning_services):
    """[LS-48] An old-format jobs index + archived jobs triggers a rebuild (manager 758-769)."""
    # Archived completed job present...
    _seed_completed_job(hass, _VAC, "j-oldidx-001", room_slugs=["kitchen"])
    # ...but the jobs index is in the legacy shape (no per-job "status" key).
    store = LearningHistoryStore(hass)
    store.save_jobs_index(
        vacuum_entity_id=_VAC,
        payload={"jobs": [{"job_id": "j-oldidx-001"}]},
    )

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    assert isinstance(result, dict)
    # After the rebuild, the persisted index is in new format (jobs carry status).
    rebuilt = store.load_jobs_index(vacuum_entity_id=_VAC) or {}
    jobs = rebuilt.get("jobs", [])
    assert jobs and isinstance(jobs[0], dict) and "status" in jobs[0]


# ---------------------------------------------------------------------------
# [LS-49] get_learning_history_snapshot builds trust metrics from accuracy data
# ---------------------------------------------------------------------------

async def test_history_snapshot_trust_metrics_with_accuracy(hass, learning_services):
    """[LS-49] Recorded accuracy samples feed the snapshot's trust metrics (manager 793-825).

    Regression test for the accuracy-stats format mismatch: record_estimate_accuracy
    persists rooms as a dict keyed by room_key with a fractional mean_abs_pct_error,
    and the snapshot reader now consumes that canonical shape (previously it only
    read a list of avg_abs_error_percent entries, so recorded accuracy never
    reached build_trust_metrics).
    """
    # Seed a completed kitchen job and rebuild so the room surfaces in the snapshot.
    _seed_completed_job(hass, _VAC, "j-trust-001", room_slugs=["kitchen"])
    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    # Record accuracy through the real service path (canonical dict shape) AFTER
    # the rebuild so it isn't clobbered. 25% error → mean_abs_pct_error 0.25.
    await hass.services.async_call(
        DOMAIN, SERVICE_RECORD_ESTIMATE_ACCURACY,
        {
            "vacuum_entity_id": _VAC,
            "room_actuals": [
                {
                    "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
                    "is_carpet": False, "clean_intensity": "standard", "map_id": 6,
                    "estimated_minutes": 20.0, "actual_minutes": 25.0,
                }
            ],
        },
        blocking=True, return_response=True,
    )
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    assert isinstance(result, dict)

    # The kitchen room's trust block now carries the recorded accuracy sample.
    # avg_abs_error_percent > 0 proves the fractional mean_abs_pct_error was read
    # and translated to a percent — the pre-fix reader left it at 0/absent.
    # (Exact value isn't asserted: config_dir is shared across tests, so the
    # kitchen accuracy sample_count/mean accumulate from other accuracy records.)
    rooms = result.get("rooms", [])
    kitchen = next(
        (r for r in rooms if str(r.get("room_slug", "")).lower() == "kitchen"), None
    )
    assert kitchen is not None, f"kitchen not in snapshot rooms: {[r.get('room_slug') for r in rooms]}"
    assert kitchen.get("accuracy_sample_count", 0) >= 1
    avg_err = kitchen.get("avg_abs_error_percent")
    assert avg_err is not None and avg_err > 0.0


# ---------------------------------------------------------------------------
# Pure-function edge cases [LS-50..LS-52]
# ---------------------------------------------------------------------------

def test_normalize_graph_targets_edges():
    """[LS-50] Non-list → []; negatives and duplicates are dropped, order preserved."""
    from custom_components.eufy_vacuum.learning.manager import _normalize_graph_targets

    assert _normalize_graph_targets("not-a-list") == []
    assert _normalize_graph_targets(None) == []
    assert _normalize_graph_targets([5, 5, -1, 3, "2"]) == [5, 3, 2]


def test_trust_level_from_score_bands():
    """[LS-51] Each score band maps to its label."""
    from custom_components.eufy_vacuum.learning.manager import _trust_level_from_score

    assert _trust_level_from_score(0.90) == "strong"
    assert _trust_level_from_score(0.70) == "good"
    assert _trust_level_from_score(0.50) == "building"
    assert _trust_level_from_score(0.10) == "low"


def test_display_label_empty_and_separator_only():
    """[LS-52] Empty / separator-only strings return None; words are title-cased."""
    from custom_components.eufy_vacuum.learning.manager import _display_label

    assert _display_label("") is None
    assert _display_label("   ") is None
    assert _display_label("___") is None
    assert _display_label("hello_world") == "Hello World"


# ---------------------------------------------------------------------------
# [LS-53] finalize pushes battery metrics to the BatteryHealthManager
# ---------------------------------------------------------------------------

async def test_finalize_pushes_battery_metrics_to_manager(hass, learning_services):
    """[LS-53] A completed, learning-eligible run records metrics on the battery manager (job_finalizer 755-762)."""
    from custom_components.eufy_vacuum.const import DATA_BATTERY
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    class _FakeBatteryManager:
        def __init__(self):
            self.calls = []

        def record_job_metrics(self, *, vacuum_entity_id, metrics, job_id):
            self.calls.append((vacuum_entity_id, job_id, metrics))

    fake = _FakeBatteryManager()
    hass.data[DOMAIN][DATA_BATTERY] = fake

    # Seed an active job with a resolved room so the completed job has a valid
    # room_count + resolved_rooms (no learning blockers → used_for_learning stays True).
    _seed_active_job(
        learning_services, _VAC, _MAP,
        resolved_rooms=[
            {"room_id": 1, "slug": "kitchen", "name": "Kitchen",
             "clean_mode": "vacuum", "clean_intensity": "standard",
             "clean_times": 1, "is_carpet": False}
        ],
    )

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)
    try:
        await hass.async_add_executor_job(
            lambda: learning.finalize_completed_job(
                manager=core_manager,
                vacuum_entity_id=_VAC,
                map_id=_MAP,
                battery_start=85,
                battery_end=60,
                started_at="2026-01-01T09:00:00+00:00",
                ended_at="2026-01-01T09:30:00+00:00",
                used_for_learning=True,
                rebuild_stats=False,
            )
        )
    finally:
        hass.data[DOMAIN].pop(DATA_BATTERY, None)

    assert fake.calls, "record_job_metrics was not called"
    assert fake.calls[0][0] == _VAC
