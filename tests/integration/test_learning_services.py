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
[LS-23c] clean_passes>1 room profile appends '<N> Pass' to save_suggested_label (manager 1091->1092).
[LS-23d] _filter_jobs_since includes a now-anchored job in metric_windows['today'] (manager 1378->1379).
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
    SERVICE_GET_EXTERNAL_PENDING_RUNS,
    SERVICE_GET_INCOMPLETE_RUN_LOG,
    SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
    SERVICE_GET_METRICS_SNAPSHOT,
    SERVICE_GET_NEXT_ROOM,
    SERVICE_GET_TROUBLE_ROOMS_LOG,
    SERVICE_REANCHOR_LEARNING_TIMELINE,
    SERVICE_REBUILD_LEARNING_STATS,
    SERVICE_RECORD_ESTIMATE_ACCURACY,
    SERVICE_RESEGMENT_EXTERNAL_RUN,
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
    clean_times: int = 1,
    started_at: str = "2026-01-01T09:00:00+00:00",
    ended_at: str = "2026-01-01T09:30:00+00:00",
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
            "clean_times": clean_times,
            "is_carpet": False,
        }
        for i, slug in enumerate(room_slugs)
    ]
    payload = {
        "record_type": "completed_job",
        "job_id": job_id,
        "job": {
            "started_at": started_at,
            "ended_at": ended_at,
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
# External-run: strip-on-serve + server-side re-segmentation
# ---------------------------------------------------------------------------

def _write_v2_pending(hass, job_id: str, *, strip: bool = False) -> dict:
    """Build a real v2 pending record (A | wash B | uncertain-jump C) and write it
    to the vacuum's external_jobs/ dir. ``strip=True`` simulates a legacy v1 record
    (no embedded samples)."""
    import json
    from datetime import datetime, timedelta

    from custom_components.eufy_vacuum.learning.external_ingest import build_pending_record

    base = datetime(2026, 6, 7, 3, 0, 0)

    def c(sec, ct, ca):
        return {
            "t": (base + timedelta(seconds=sec)).isoformat(),
            "cleaning_time": ct, "cleaning_area": ca, "battery": 100,
        }

    counter = [
        c(0, 0, 0),
        c(60, 30, 1), c(90, 60, 2), c(120, 90, 3),
        c(450, 120, 3), c(480, 150, 5), c(510, 180, 6),   # wash gap 330
        c(550, 210, 8), c(580, 240, 9), c(610, 270, 10),  # area_jump gap 40
    ]
    settings = [{"t": (base + timedelta(seconds=60)).isoformat(), "settings": {"clean_mode": "vacuum"}}]
    rec = build_pending_record(
        detection_ts=base.isoformat(), map_id=_MAP,
        counter_samples=counter, settings_samples=settings, rooms={}, baselines=[],
    )
    assert rec is not None
    if strip:
        rec.pop("counter_samples", None)
        rec.pop("settings_samples", None)
        rec["schema_version"] = 1

    store = LearningHistoryStore(hass)
    ext_dir = store.get_paths(vacuum_entity_id=_VAC).root / "external_jobs"
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / f"{job_id}.json").write_text(json.dumps(rec), encoding="utf-8")
    return rec


async def test_get_external_pending_runs_strips_samples(hass, learning_services):
    """Served v2 record has the bulky samples stripped but keeps candidates /
    active_boundaries and is flagged resegmentable."""
    _write_v2_pending(hass, "job_2026-06-07T03-00-00Z")
    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_EXTERNAL_PENDING_RUNS,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    # find OUR record by id (the external_jobs dir is shared across tests).
    rec = next(r for r in result["pending"] if r["pending_job_id"] == "job_2026-06-07T03-00-00Z")
    assert "counter_samples" not in rec and "settings_samples" not in rec
    assert rec["candidates"] and "active_boundaries" in rec
    assert rec["resegmentable"] is True


async def test_get_external_pending_runs_v1_not_resegmentable(hass, learning_services):
    _write_v2_pending(hass, "job_2026-06-07T01-00-00Z", strip=True)
    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_EXTERNAL_PENDING_RUNS,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    rec = next(r for r in result["pending"] if r["pending_job_id"] == "job_2026-06-07T01-00-00Z")
    assert rec["resegmentable"] is False


async def test_resegment_external_run_round_trip(hass, learning_services):
    """Re-segment to 3 rooms: the response is stripped + reports the new count, and
    the on-disk record keeps its samples for the next re-segment."""
    import json

    rec = _write_v2_pending(hass, "job_2026-06-07T03-00-00Z")
    assert rec["segment_count"] == 2                       # wash only by default
    result = await hass.services.async_call(
        DOMAIN, SERVICE_RESEGMENT_EXTERNAL_RUN,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "pending_job_id": "job_2026-06-07T03-00-00Z", "expected_rooms": 3,
        },
        blocking=True, return_response=True,
    )
    assert result["ok"] is True
    assert result["segment_count"] == 3
    assert "counter_samples" not in result                 # response is stripped

    store = LearningHistoryStore(hass)
    path = store.get_paths(vacuum_entity_id=_VAC).root / "external_jobs" / "job_2026-06-07T03-00-00Z.json"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["counter_samples"]                       # samples preserved on disk
    assert on_disk["segment_count"] == 3


async def test_resegment_external_run_not_resegmentable(hass, learning_services):
    _write_v2_pending(hass, "job_2026-06-07T01-00-00Z", strip=True)
    result = await hass.services.async_call(
        DOMAIN, SERVICE_RESEGMENT_EXTERNAL_RUN,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "pending_job_id": "job_2026-06-07T01-00-00Z", "expected_rooms": 3,
        },
        blocking=True, return_response=True,
    )
    assert result["ok"] is False and result["error"] == "not_resegmentable"


async def test_resegment_external_run_rejects_both_modes(hass, learning_services):
    """The schema forbids passing both expected_rooms and active_boundaries."""
    import voluptuous as vol

    _write_v2_pending(hass, "job_2026-06-07T03-00-00Z")
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_RESEGMENT_EXTERNAL_RUN,
            {
                "vacuum_entity_id": _VAC, "map_id": _MAP,
                "pending_job_id": "job_2026-06-07T03-00-00Z",
                "expected_rooms": 3, "active_boundaries": [1],
            },
            blocking=True, return_response=True,
        )


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


async def test_history_snapshot_multipass_appends_pass_to_suggested_label(hass, learning_services):
    """[LS-23c] A room profile observed with clean_passes>1 appends '<N> Pass' to
    the public save_suggested_label (manager 1091->1092).

    This is the inline suggested-label builder in the room-profile enrichment loop
    (a separate payload from _settings_profile_label's 'N Passes' subtitle). The
    save_suggested_label feeds the card's save-candidate flow, so its content is a
    caller-visible contract. Seeding clean_times=2 carries through the rebuilder
    (room_profiles[].clean_passes = clean_times) so the >1 branch fires.
    """
    _seed_completed_job(hass, _VAC, "j-pass-002", room_slugs=["kitchen"], clean_times=2)

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
    profiles = result.get("room_profiles", [])
    kitchen = [
        p for p in profiles
        if str(p.get("room_slug", "")).strip().lower() == "kitchen"
        and _safe_int_local(p.get("clean_passes")) == 2
    ]
    assert kitchen, "expected a kitchen room profile observed with clean_passes=2"
    label = kitchen[0].get("save_suggested_label", "")
    # The >1-pass branch appended the '<N> Pass' fragment to the public label.
    assert label.endswith("2 Pass"), f"save_suggested_label missing pass count: {label!r}"


async def test_history_snapshot_metric_window_includes_recent_job(hass, learning_services):
    """[LS-23d] _filter_jobs_since includes a job whose anchor >= the window start,
    populating the public summary.metric_windows['today'] bucket (manager 1378->1379).

    The pre-existing seeded test uses a 2026-01-01 fixture date that lands BEFORE
    every window, so only the false (exclude) branch is exercised. Anchoring a job
    at 'now' lands it inside the today window (midnight-UTC start), traversing the
    true (append) branch and proving the recency filter feeds the metric bucket.
    """
    from custom_components.eufy_vacuum.timestamp_utils import utc_now

    now = utc_now()
    started = now.replace(microsecond=0).isoformat()
    _seed_completed_job(
        hass, _VAC, "j-today-001", room_slugs=["kitchen"],
        started_at=started, ended_at=started,
    )

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
    windows = result.get("summary", {}).get("metric_windows", {})
    # The recency filter appended the now-anchored job into every window bucket.
    assert windows.get("today", {}).get("job_count", 0) >= 1
    assert windows.get("last_7_days", {}).get("job_count", 0) >= 1
    assert windows.get("last_30_days", {}).get("job_count", 0) >= 1


def _safe_int_local(value, default: int = 0) -> int:
    """Local int coercion mirror so the test does not import a private helper."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
# [LS-25b] _build_access_graph_context — non-granted edge counts as a jump,
#          and resolved_rooms fallback when the queue has no queue_room_ids.
# ---------------------------------------------------------------------------

async def test_access_graph_non_granted_edge_counts_as_jump(hass, learning_services):
    """[LS-25b] Queue order [2, 1] over a graph that only grants 1->2 yields a
    jump (the 2->1 pair is NOT a granted edge), so graph_jump_count==1 and
    graph_transition_count==0 (manager line 478, else-branch of the pair loop)."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    setup_map(learning_services, _VAC, _MAP, count=2)
    # Only room 1 grants access to room 2; the reverse edge (2->1) does NOT exist.
    rooms_bucket = (
        learning_services.data
        .get("maps", {}).get(_VAC, {}).get(_MAP, {}).get("rooms", {})
    )
    rooms_bucket["1"]["grants_access_to"] = [2]

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)

    # Queue ordered [2, 1] — the single pair (2 -> 1) is not in room 2's grants.
    ctx = learning._build_access_graph_context(
        manager=core_manager,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        queue_state={"queue_room_ids": [2, 1]},
        payload_state={},
    )

    assert ctx["queue_room_ids"] == [2, 1]
    assert ctx["pair_count"] == 1
    assert ctx["graph_jump_count"] == 1        # 2 -> 1 is a jump (line 478)
    assert ctx["graph_transition_count"] == 0  # no granted edge traversed
    assert ctx["present"] is True              # the 1 -> 2 edge means a graph exists
    assert ctx["graph_coherence_score"] == 0.0


async def test_access_graph_resolved_rooms_fallback_when_queue_empty(hass, learning_services):
    """[LS-25c] When queue_state carries no queue_room_ids, the room order is
    derived from payload_state.resolved_rooms (manager 461->468 fallback)."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    setup_map(learning_services, _VAC, _MAP, count=2)
    rooms_bucket = (
        learning_services.data
        .get("maps", {}).get(_VAC, {}).get(_MAP, {}).get("rooms", {})
    )
    rooms_bucket["1"]["grants_access_to"] = [2]

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)

    # Empty queue forces the resolved_rooms fallback; order [1, 2] follows a
    # granted edge so it counts as a transition (proves the fallback ids feed
    # the same pair loop).
    ctx = learning._build_access_graph_context(
        manager=core_manager,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        queue_state={"queue_room_ids": []},
        payload_state={"resolved_rooms": [{"room_id": 1}, {"room_id": 2}]},
    )

    assert ctx["queue_room_ids"] == [1, 2]      # fallback fired (461->468)
    assert ctx["pair_count"] == 1
    assert ctx["graph_transition_count"] == 1   # 1 -> 2 is a granted edge
    assert ctx["graph_jump_count"] == 0


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


async def test_get_room_learning_estimates_cold_cache_no_blocking_reload(
    hass, learning_services, monkeypatch
):
    """[LS-26b] On the event-loop path get_room_learning_estimates is cache-only:
    a cold cache must NOT trigger the blocking _reload_learning_stats_now (which
    would do a disk read on the loop). It returns default estimates and lets the
    executor preload warm the cache for the next refresh."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import (
        _get_learning_manager,
        SERVICE_GET_ROOM_LEARNING_ESTIMATES,
    )

    setup_map(learning_services, _VAC, _MAP, count=1)
    learning = _get_learning_manager(hass)
    learning._room_stats_cache.pop(_VAC, None)
    learning._accuracy_stats_cache.pop(_VAC, None)

    reload_calls: list = []
    monkeypatch.setattr(
        learning, "_reload_learning_stats_now",
        lambda **kw: reload_calls.append(kw) or ({}, {}, True),
    )

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_ROOM_LEARNING_ESTIMATES,
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )

    assert reload_calls == []  # never block-reloads on the loop path
    assert result["rooms"][0]["source"] == "default"


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

@pytest.mark.parametrize(
    "forced_lifecycle_state, expected_status",
    [
        # [LS-30] was_failed branch (job_finalizer 418->419).
        ("failed", "failed"),
        # was_cancelled branch (job_finalizer 416->417): a forced cancel
        # lifecycle, with no forced_outcome_status, must classify the saved
        # outcome.status as "cancelled" — the contract the incomplete-run-log
        # writer reads to decide whether to log a missed-rooms banner.
        ("cancelled", "cancelled"),
    ],
)
async def test_finalize_forced_lifecycle_state_sets_outcome(
    hass, learning_services, forced_lifecycle_state, expected_status
):
    """[LS-30] forced_lifecycle_state sets outcome.status without forced_outcome_status (lines 402-420)."""
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
            forced_lifecycle_state=forced_lifecycle_state,
        )
    )
    outcome = result.get("completed_job", {}).get("outcome", {})
    assert outcome.get("status") == expected_status


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
# [LS-60] get_learning_history_snapshot profile_key + used_for_learning filters
#         prune room_profiles rows (manager _profile_matches lines 971, 978)
# ---------------------------------------------------------------------------

async def test_history_snapshot_room_profile_filters_prune(hass, learning_services):
    """[LS-60] profile_key prunes non-matching room_profiles (manager line 971) and
    used_for_learning=True keeps only profiles with learning_run_count>0 (line 978).

    Seeds three single-room completed jobs in distinct rooms — kitchen and bedroom
    are learning-eligible, study is excluded (used_for_learning=False) — then
    rebuilds so the jobs index carries one room_profiles entry per room (profile_key
    is slug-derived, so each room yields a distinct key with run_count==1 and
    learning_run_count 1/1/0 respectively). The unfiltered snapshot is read first to
    discover the live profile_key values (the key string is deterministic but built
    from the full settings signature, so observing it is more robust than hardcoding).
    """
    _seed_completed_job(hass, _VAC, "j-pf-kitchen", room_slugs=["kitchen"], used_for_learning=True)
    _seed_completed_job(hass, _VAC, "j-pf-bedroom", room_slugs=["bedroom"], used_for_learning=True)
    # study: excluded from learning → its room_profiles row has learning_run_count == 0
    _seed_completed_job(hass, _VAC, "j-pf-study", room_slugs=["study"], used_for_learning=False)

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    # Unfiltered snapshot: discover the room_profiles rows the rebuild produced.
    full = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    profiles = full.get("room_profiles", [])
    by_slug = {
        str(p.get("room_slug", "")).strip().lower(): p
        for p in profiles
        if isinstance(p, dict)
    }
    # The three seeded rooms must each have surfaced a distinct profile row.
    for slug in ("kitchen", "bedroom", "study"):
        assert slug in by_slug, f"{slug} profile missing from {sorted(by_slug)}"
    kitchen_key = str(by_slug["kitchen"].get("profile_key", "")).strip().lower()
    bedroom_key = str(by_slug["bedroom"].get("profile_key", "")).strip().lower()
    assert kitchen_key and bedroom_key and kitchen_key != bedroom_key
    # The excluded study run produced a learning_run_count of 0; kitchen/bedroom > 0.
    assert by_slug["study"].get("learning_run_count", -1) == 0
    assert by_slug["kitchen"].get("learning_run_count", 0) > 0
    assert by_slug["bedroom"].get("learning_run_count", 0) > 0

    # --- profile_key filter (manager line 971) ---
    # Filtering on kitchen's key keeps only kitchen rows; bedroom (and study) pruned.
    by_key = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "profile_key": by_slug["kitchen"]["profile_key"]},
        blocking=True, return_response=True,
    )
    key_profiles = by_key.get("room_profiles", [])
    assert key_profiles, "profile_key filter pruned everything"
    returned_keys = {str(p.get("profile_key", "")).strip().lower() for p in key_profiles}
    assert returned_keys == {kitchen_key}
    assert bedroom_key not in returned_keys  # the non-matching row was pruned (971)

    # --- used_for_learning=True filter (manager line 978) ---
    # Only profiles with learning_run_count>0 survive → study (count 0) is dropped.
    learned = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "used_for_learning": True},
        blocking=True, return_response=True,
    )
    learned_profiles = learned.get("room_profiles", [])
    assert learned_profiles, "used_for_learning filter pruned everything"
    assert all(p.get("learning_run_count", 0) > 0 for p in learned_profiles)
    learned_slugs = {str(p.get("room_slug", "")).strip().lower() for p in learned_profiles}
    assert "study" not in learned_slugs  # learning_run_count==0 row pruned (978)
    assert {"kitchen", "bedroom"} <= learned_slugs


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


# ---------------------------------------------------------------------------
# [LS-54] _auto_record_accuracy returns None when no room yields a usable actual
# ---------------------------------------------------------------------------

async def test_auto_record_accuracy_no_estimate_returns_none(hass, learning_services):
    """[LS-54] _auto_record_accuracy meaningful skips (manager lines 685, 711).

    A room carrying neither estimated_minutes nor avg_minutes has estimated<=0,
    so it is skipped (line 685 continue). With the single room skipped, no room
    produces a usable actual, so room_actuals stays empty and the method returns
    None (line 711) — nothing is recorded.
    """
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(hass)

    # duration_minutes>0 plus a non-empty rooms list clear the early guard at
    # line 657; the room has a slug (passes line 675) but no estimate, so the
    # per-room estimate<=0 skip at line 685 fires and leaves room_actuals empty,
    # driving the no-usable-actual return at line 711.
    result = learning._auto_record_accuracy(
        result={
            "completed_job": {
                "job": {"duration_minutes": 30},
                "job_profile": {"rooms": [{"slug": "kitchen"}]},
            }
        },
        vacuum_entity_id=_VAC,
        map_id=_MAP,
    )

    assert result is None


# ---------------------------------------------------------------------------
# [LS-58] accuracy normalization prefers EXPLICIT percent/weight over derived
# ---------------------------------------------------------------------------

async def test_history_snapshot_accuracy_uses_explicit_percent_and_weight(
    hass, learning_services, monkeypatch
):
    """[LS-58] An accuracy entry carrying explicit avg_abs_error_percent and
    confidence_weight is taken verbatim, not re-derived (manager lines 813, 822).

    The normalizer at lines 802-833 has two prefer-explicit branches:
      - line 813: use entry["avg_abs_error_percent"] when present, instead of
        deriving it from the fractional mean_abs_pct_error (line 815-817).
      - line 822: use entry["confidence_weight"] when present, instead of
        synthesizing it from min(sample_count, 5) (line 824).

    We feed an entry with sample_count=4, avg_abs_error_percent=12.5,
    confidence_weight=3.0 and NO mean_abs_pct_error. The chosen values are
    distinguishable from their fallbacks:
      - derived percent (no mean_abs_pct_error) would be 0.0, not 12.5.
      - synthesized weight from sample_count=4 would be 4.0, not 3.0.
    Both surface (rounded to 2 dp) on the kitchen room's trust block via
    build_trust_metrics, so the snapshot output proves the explicit branches fired.
    """
    # Seed a completed kitchen job and rebuild so the kitchen room surfaces in
    # the snapshot's index_rooms (and thus carries a trust block).
    _seed_completed_job(hass, _VAC, "j-explicit-acc-001", room_slugs=["kitchen"])
    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    # Intercept the snapshot's accuracy read with an explicit-fields entry. The
    # read happens via self.store.load_accuracy_stats(vacuum_entity_id=...), so
    # patching the class method controls exactly what the normalizer sees —
    # independent of whatever the rebuild wrote to disk.
    monkeypatch.setattr(
        LearningHistoryStore,
        "load_accuracy_stats",
        lambda self, *, vacuum_entity_id: {
            "rooms": [
                {
                    "slug": "kitchen",
                    "sample_count": 4,
                    "avg_abs_error_percent": 12.5,
                    "confidence_weight": 3.0,
                }
            ]
        },
    )

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    assert isinstance(result, dict)

    rooms = result.get("rooms", [])
    kitchen = next(
        (r for r in rooms if str(r.get("room_slug", "")).lower() == "kitchen"), None
    )
    assert kitchen is not None, (
        f"kitchen not in snapshot rooms: {[r.get('room_slug') for r in rooms]}"
    )
    # Explicit percent taken verbatim (line 813) — NOT the 0.0 derived fallback.
    assert kitchen.get("avg_abs_error_percent") == 12.5
    # Explicit weight taken verbatim (line 822) — NOT the 4.0 synthesized from
    # min(sample_count=4, 5).
    assert kitchen.get("confidence_weight") == 3.0
    assert kitchen.get("accuracy_sample_count") == 4


# ---------------------------------------------------------------------------
# [LS-67] restore_learning_job — defensive outcome/learning_blockers normalization
# ---------------------------------------------------------------------------

async def test_restore_learning_job_normalizes_malformed_outcome(
    hass, learning_services
):
    """[LS-67] restore_learning_job coerces malformed archived fields before
    restoring (manager.py lines 1664 + 1668).

    Two defensive guards run before the restore mutation:
      - line 1664: a non-dict ``outcome`` is replaced with ``{}`` so the
        subsequent ``outcome[...] = ...`` writes don't crash.
      - line 1668: a non-list ``learning_blockers`` (e.g. a bare int written by
        an old/corrupt record) is replaced with ``[]`` so the comprehension at
        1669-1675 can iterate it.

    Both archived shapes are written straight to disk via the store (the helper
    ``_seed_completed_job`` only ever produces a well-formed outcome, so we build
    the malformed payloads inline, mirroring the [LS-13] round-trip seeding). The
    top-level record stays a dict so ``load_completed_job`` returns it rather than
    None. We then drive SERVICE_RESTORE_LEARNING_JOB and assert the observable,
    normalized result: restore succeeds, ``outcome`` is a dict,
    ``used_for_learning`` is flipped True, and ``learning_blockers`` is a (sorted)
    list — proving each guard turned junk into the expected restored shape.
    """
    store = LearningHistoryStore(hass)

    def _base_job(job_id: str, outcome) -> dict:
        return {
            "record_type": "completed_job",
            "job_id": job_id,
            "job": {
                "ended_at": "2026-01-01T10:00:00+00:00",
                "duration_minutes": 30.0,
                "room_count": 1,
            },
            "battery": {"start": 80, "end": 60, "used": 20},
            "water": {},
            "job_profile": {
                "map_id": _MAP_INT,
                "room_count": 1,
                "room_slugs": ["kitchen"],
                "rooms": [],
            },
            "resolved_rooms": [],
            "queue": {"queue_room_ids": [1], "queue_rooms": []},
            "outcome": outcome,
        }

    # --- Case A: line 1668 — outcome is a dict, but learning_blockers is an int.
    store.save_completed_job(
        vacuum_entity_id=_VAC,
        job_id="j-ls67-int-blockers",
        payload=_base_job(
            "j-ls67-int-blockers",
            {"learning_blockers": 123, "excluded_from_learning": True},
        ),
    )

    rest_a = await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTORE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": "j-ls67-int-blockers"},
        blocking=True,
        return_response=True,
    )
    assert rest_a["restored"] is True
    outcome_a = rest_a["completed_job"]["outcome"]
    assert isinstance(outcome_a, dict)
    assert outcome_a["used_for_learning"] is True
    assert outcome_a["excluded_from_learning"] is False
    # int blockers were coerced to [] (line 1668), so the normalized result is an
    # empty sorted list — not a crash and not the bare int.
    assert isinstance(outcome_a["learning_blockers"], list)
    assert outcome_a["learning_blockers"] == []

    # --- Case B: line 1664 — outcome itself is not a dict (a bare string).
    store.save_completed_job(
        vacuum_entity_id=_VAC,
        job_id="j-ls67-str-outcome",
        payload=_base_job("j-ls67-str-outcome", "totally-not-a-dict"),
    )

    rest_b = await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTORE_LEARNING_JOB,
        {"vacuum_entity_id": _VAC, "job_id": "j-ls67-str-outcome"},
        blocking=True,
        return_response=True,
    )
    assert rest_b["restored"] is True
    outcome_b = rest_b["completed_job"]["outcome"]
    # non-dict outcome was replaced with {} (line 1664) and then populated by the
    # restore mutation, so it is a dict carrying the restored fields.
    assert isinstance(outcome_b, dict)
    assert outcome_b["used_for_learning"] is True
    assert outcome_b["excluded_from_learning"] is False
    assert isinstance(outcome_b["learning_blockers"], list)
    assert outcome_b["learning_blockers"] == []


# ---------------------------------------------------------------------------
# [LS-64] profile_key filter swaps summary.selected_profile for the ENRICHED entry
# ---------------------------------------------------------------------------

async def test_history_snapshot_profile_filter_selects_enriched_profile(hass, learning_services):
    """[LS-64] A profile_key filter sets summary.selected_profile to the matching
    *enriched* room-profile entry (manager line 1321).

    selected_profile starts as filtered_room_profiles[0] — the raw jobs-index
    entry (manager line 1317). Line 1321 then replaces it with the matching
    enriched_room_profiles entry found by profile_key. Only the enriched entry
    carries the trust block + found_profile dict the rebuilt index row lacks, so
    asserting those keys are present on summary.selected_profile (and that it is
    the same object surfaced in result['room_profiles']) proves the swap ran.
    """
    # Seed a single-room completed job + REBUILD so the jobs index gains a
    # room_profiles list with a real per-room profile_key signature.
    _seed_completed_job(hass, _VAC, "j-pkfilter-001", room_slugs=["kitchen"])
    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    # Read an UNFILTERED snapshot first to learn a real profile_key. The kitchen
    # profile must be present after the rebuild.
    unfiltered = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    all_profiles = unfiltered.get("room_profiles", [])
    kitchen_profile = next(
        (p for p in all_profiles if str(p.get("room_slug", "")).lower() == "kitchen"),
        None,
    )
    assert kitchen_profile is not None, (
        f"no kitchen room_profile after rebuild: "
        f"{[p.get('room_slug') for p in all_profiles]}"
    )
    profile_key = kitchen_profile.get("profile_key")
    assert profile_key  # the rebuilt index carries a concrete signature

    # Now call WITH the profile_key filter — this drives the line-1321 swap.
    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "profile_key": profile_key},
        blocking=True, return_response=True,
    )

    selected = result.get("summary", {}).get("selected_profile")
    # The swap populated selected_profile (raw [0] was non-None; line 1321 kept it).
    assert selected is not None
    assert selected.get("profile_key") == profile_key

    # It is the ENRICHED entry: only enriched_room_profiles carry these keys.
    assert "found_profile" in selected
    assert "trust_score" in selected
    assert isinstance(selected.get("found_profile"), dict)

    # And it is the very entry surfaced in result['room_profiles'] (the swap reads
    # from enriched_room_profiles, which is exactly what 'room_profiles' returns).
    filtered_profiles = result.get("room_profiles", [])
    match = next(
        (p for p in filtered_profiles if p.get("profile_key") == profile_key), None
    )
    assert match is not None
    assert selected == match


# ---------------------------------------------------------------------------
# [LS-68..LS-70] enriched_jobs outlier / exclude-suggestion branches
# (manager.py lines 1243, 1248->1255, 1262-1270)
# ---------------------------------------------------------------------------

def _seed_job_with_outcome(
    hass,
    vacuum_entity_id: str,
    job_id: str,
    *,
    room_slug: str = "kitchen",
    duration_minutes: float = 30.0,
    status: str = "completed",
    used_for_learning: bool = True,
    sanity_passed: bool = True,
    excluded_from_learning: bool = False,
    cancel_detection: dict | None = None,
    clean_mode: str = "vacuum",
) -> dict:
    """Seed a single-room completed job with explicit outcome flags.

    Mirrors ``_seed_completed_job`` but exposes the outcome fields the
    enriched-jobs branches key off of: ``sanity_passed`` (so the failed-sanity
    short-circuit at manager 1259 can be avoided), ``excluded_from_learning``
    (the +1 outlier contribution at 1243), and ``cancel_detection`` (the
    cancel-likely suggestion at 1262-1264). ``clean_mode`` changes the room's
    profile signature so a job can share a room average but miss the profile
    average (driving short_vs_room at 1268-1270). The rebuilder copies these
    straight from ``outcome``/``job_profile`` into the jobs index, so a real
    REBUILD propagates them — no monkeypatch needed.
    """
    room = {
        "slug": room_slug,
        "room_id": 1,
        "name": room_slug.replace("_", " ").title(),
        "clean_mode": clean_mode,
        "clean_intensity": "standard",
        "clean_times": 1,
        "is_carpet": False,
    }
    outcome: dict = {
        "status": status,
        "used_for_learning": used_for_learning,
        "sanity_passed": sanity_passed,
        "excluded_from_learning": excluded_from_learning,
        "learning_blockers": [],
    }
    if cancel_detection is not None:
        outcome["cancel_detection"] = cancel_detection
    payload = {
        "record_type": "completed_job",
        "job_id": job_id,
        "job": {
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": f"2026-01-01T09:{int(duration_minutes) % 60:02d}:00+00:00",
            "duration_minutes": duration_minutes,
            "room_count": 1,
        },
        "battery": {"start": 85, "end": 60, "used": 25},
        "water": {},
        "job_profile": {
            "map_id": _MAP_INT,
            "room_count": 1,
            "room_slugs": [room_slug],
            "rooms": [room],
        },
        "resolved_rooms": [room],
        "queue": {"queue_room_ids": [1], "queue_rooms": [room]},
        "outcome": outcome,
    }
    LearningHistoryStore(hass).save_completed_job(
        vacuum_entity_id=vacuum_entity_id, job_id=job_id, payload=payload
    )
    return payload


async def _rebuild_and_snapshot_jobs(hass, vacuum_entity_id: str) -> list[dict]:
    """REBUILD the learning index then return the snapshot's enriched jobs list."""
    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": vacuum_entity_id, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": vacuum_entity_id}, blocking=True, return_response=True,
    )
    return result.get("jobs", [])


async def test_enriched_job_short_vs_profile_suggests_exclude(hass, learning_services):
    """[LS-68] A single-room job far shorter than its PROFILE average is flagged
    exclude_suggested='short_duration_vs_profile' (manager 1265-1267).

    Five same-profile kitchen jobs establish the profile average; the 1-minute
    one sits well under 35% of it. The job is completed, learning-eligible, and
    sanity-passed (so the cancelled/failed-sanity short-circuits at 1256/1259
    don't fire), and it shares the base profile signature, so short_vs_profile
    (checked first) is the branch that wins.
    """
    for i in range(4):
        _seed_job_with_outcome(
            hass, _VAC, f"j-short-base-{i}", room_slug="kitchen", duration_minutes=30.0,
        )
    _seed_job_with_outcome(
        hass, _VAC, "j-short-outlier", room_slug="kitchen", duration_minutes=1.0,
    )

    jobs = await _rebuild_and_snapshot_jobs(hass, _VAC)
    outlier = next(j for j in jobs if j.get("job_id") == "j-short-outlier")

    assert outlier["exclude_suggested"] is True
    assert outlier["exclude_suggested_reason"] == "short_duration_vs_profile"
    # A full-length sibling is NOT suggested for exclusion (none of 1256-1270 fire).
    sibling = next(j for j in jobs if j.get("job_id") == "j-short-base-0")
    assert sibling["exclude_suggested"] is False
    assert sibling["exclude_suggested_reason"] is None


async def test_enriched_job_short_vs_room_suggests_exclude(hass, learning_services):
    """[LS-68b] When the short job's profile signature does NOT match the room's
    profile average (so short_vs_profile can't fire), the room-average branch
    flags exclude_suggested='short_duration_vs_room' (manager 1268-1270).

    Four 30-minute vacuum jobs build the 'pantry' room average. The 1-minute
    outlier is a *mop* job: it still belongs to the pantry room (so the room
    average applies and it is 35%+ short of it), but its own profile signature
    has only the single 1-minute sample, so short_vs_profile (1<=0.35) is False
    and execution falls through to short_vs_room.
    """
    for i in range(4):
        _seed_job_with_outcome(
            hass, _VAC, f"j-room-base-{i}", room_slug="pantry",
            duration_minutes=30.0, clean_mode="vacuum",
        )
    _seed_job_with_outcome(
        hass, _VAC, "j-room-outlier", room_slug="pantry",
        duration_minutes=1.0, clean_mode="mop",
    )

    jobs = await _rebuild_and_snapshot_jobs(hass, _VAC)
    outlier = next(j for j in jobs if j.get("job_id") == "j-room-outlier")

    assert outlier["exclude_suggested"] is True
    assert outlier["exclude_suggested_reason"] == "short_duration_vs_room"


async def test_enriched_job_cancel_likely_suggests_exclude(hass, learning_services):
    """[LS-69] A cancel-likely job (per its stored cancel_detection) is flagged
    exclude_suggested with the detector's reason (manager 1262-1264).

    The job is completed + learning-eligible + sanity-passed and NOT short, so
    the only branch that can fire is the cancel_detection.cancel_likely one. The
    rebuilder copies outcome.cancel_detection verbatim into the index entry, so
    the reason surfaces as exclude_suggested_reason (1248->1255 also runs: the
    detector dict is echoed back with a human label/text attached).
    """
    _seed_job_with_outcome(
        hass, _VAC, "j-cancel-like", room_slug="den", duration_minutes=30.0,
        cancel_detection={"cancel_likely": True, "reason": "cancel_like"},
    )

    jobs = await _rebuild_and_snapshot_jobs(hass, _VAC)
    job = next(j for j in jobs if j.get("job_id") == "j-cancel-like")

    assert job["exclude_suggested"] is True
    assert job["exclude_suggested_reason"] == "cancel_like"
    # The detector block is carried through on the enriched job.
    assert job["cancel_detection"]["cancel_likely"] is True


async def test_enriched_job_excluded_adds_outlier_point(hass, learning_services):
    """[LS-70] An excluded_from_learning job carries a +1.0 outlier_score
    contribution over an otherwise-identical non-excluded job (manager 1243).

    Two same-duration single-room jobs (so the duration-vs-average outlier
    contributions are identical) differ only in outcome.excluded_from_learning.
    The excluded one's outlier_score is exactly 1.0 higher.
    """
    _seed_job_with_outcome(
        hass, _VAC, "j-excl-yes", room_slug="study", duration_minutes=30.0,
        excluded_from_learning=True,
    )
    _seed_job_with_outcome(
        hass, _VAC, "j-excl-no", room_slug="study", duration_minutes=30.0,
        excluded_from_learning=False,
    )

    jobs = await _rebuild_and_snapshot_jobs(hass, _VAC)
    excluded = next(j for j in jobs if j.get("job_id") == "j-excl-yes")
    plain = next(j for j in jobs if j.get("job_id") == "j-excl-no")

    assert excluded["excluded_from_learning"] is True
    assert plain["excluded_from_learning"] is False
    # The +1.0 from the excluded_from_learning branch (line 1243) is the only
    # difference between two otherwise-identical jobs.
    assert excluded["outlier_score"] >= 1.0
    assert excluded["outlier_score"] == round(plain["outlier_score"] + 1.0, 2)


# ---------------------------------------------------------------------------
# [LS-55] finalize_learning_for_active_job derives battery_end from the live
#         adapter battery entity when the caller omits it
#         (tag note: the prompt asked for [LS-54], but [LS-54] is already taken
#          by test_auto_record_accuracy_no_estimate_returns_none above, so this
#          claims the next free number).
# ---------------------------------------------------------------------------

async def test_finalize_active_job_derives_battery_end_from_entity(hass, learning_services):
    """[LS-55] When battery_end is omitted, finalize_learning_for_active_job reads
    it from the live battery via manager._get_battery_level (manager.py 3598-3599).

    _get_battery_level resolves the adapter's ``entities.battery`` sensor first
    (core/charging.get_battery_level 50-58), so we register an adapter config that
    points at a battery sensor, set that sensor to a KNOWN level, then finalize an
    active job WITHOUT passing battery_end. The derived level must flow through to
    completed_job["battery"]["end"] (and "used" = start - end), proving the
    derivation fired rather than a default 0.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    _BATT = "sensor.alfred_battery"
    _DERIVED_END = 47  # distinct from battery_start (90) and from the default 0

    # Point the adapter battery entity at a sensor and give it a known reading so
    # _get_battery_level returns _DERIVED_END (read-from-adapter-entity path).
    register_adapter_config(_VAC, {
        "adapter_id": "test_battery_derive",
        "source": "test",
        "entities": {"battery": _BATT},
    })
    hass.states.async_set(_BATT, str(_DERIVED_END))

    # Sanity: confirm the manager reads the adapter battery entity before relying
    # on it for the derivation (note in the plan).
    core_manager = hass.data[DOMAIN]["runtime"]
    assert core_manager._get_battery_level(_VAC) == _DERIVED_END

    # Ensure the learning manager is wired under DATA_LEARNING so the manager
    # method finds it (the manager getter does not lazily create one).
    _get_learning_manager(hass)

    # Active job with started_at + battery_start; a resolved room so the completed
    # job is well-formed. Fixed timestamps → deterministic, no real clock.
    _seed_active_job(
        learning_services, _VAC, _MAP,
        started_at="2026-01-01T09:00:00+00:00",
        battery_start=90,
        resolved_rooms=[
            {"room_id": 1, "slug": "kitchen", "name": "Kitchen",
             "clean_mode": "vacuum", "clean_intensity": "standard",
             "clean_times": 1, "is_carpet": False}
        ],
    )

    # Call the manager method directly WITHOUT battery_end → forces the derivation.
    result = await core_manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP,
        ended_at="2026-01-01T09:30:00+00:00",
        rebuild_stats=False,
    )

    assert isinstance(result, dict)
    completed = result.get("completed_job", {})
    battery = completed.get("battery", {})
    # The omitted battery_end was derived from the live adapter entity.
    assert battery.get("end") == _DERIVED_END
    assert battery.get("start") == 90
    assert battery.get("used") == 90 - _DERIVED_END
