"""Integration tests for learning/services.py — service registration + handlers.

Coverage targets
----------------
[LS-1]  Services are registered after async_register_learning_services.
[LS-2]  get_incomplete_run_log returns {} when no log exists.
[LS-3]  get_trouble_rooms_log returns {} when no log exists.
[LS-4]  rebuild_learning_stats with no jobs runs without error.
[LS-4b] RP-031/Q9: rebuild_learning_stats now supports_response.
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
[LS-15b] RP-031/Q9: save_learning_snapshot now supports_response.
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
[LS-54] _auto_record_accuracy returns None when no room yields a usable actual (manager 685, 711).
[LS-55] finalize_learning_for_active_job derives battery_end from the live adapter battery entity when omitted (manager 3598-3599).
[LS-58] accuracy normalization prefers EXPLICIT avg_abs_error_percent/confidence_weight over derived (manager 813, 822).
[LS-60] get_learning_history_snapshot profile_key + used_for_learning filters prune room_profiles rows (manager 971, 978).
[LS-64] profile_key filter swaps summary.selected_profile for the matching ENRICHED entry (manager 1321).
[LS-67] restore_learning_job coerces malformed outcome/learning_blockers before restoring (manager 1664, 1668).
[LS-68] enriched job far shorter than its PROFILE average → exclude_suggested='short_duration_vs_profile' (manager 1265-1267).
[LS-69] cancel-likely job (per stored cancel_detection) → exclude_suggested with the detector's reason (manager 1262-1264).
[LS-70] excluded_from_learning job carries a +1.0 outlier_score contribution (manager 1243).
[LS-71] discard_external_run SERVICE handler resolves the manager + delegates verbatim (services.py 358-364).
[LS-72] RP-039/RF-16: register/unregister walk the SAME SERVICES tuple (all 21) —
        register→unregister leaves none behind (was: 5 of 21 silently leaked).
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
    origin: str | None = None,
    room_timings: list[dict] | None = None,
    outcome_extra: dict | None = None,
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
            **({"room_timings": room_timings} if room_timings is not None else {}),
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
            **(outcome_extra or {}),
        },
    }
    if origin is not None:
        payload["origin"] = origin
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
    # Clean slate: the test config_dir is shared/persistent across pytest runs, so
    # a prior run's finalize (e.g. LS-20) leaves a trouble_rooms.json behind that
    # makes the service return a populated log instead of {}. Remove only THIS
    # vacuum's single-overwrite trouble-rooms file so the "no log exists" path runs.
    trouble_path = LearningHistoryStore(hass).get_trouble_rooms_path(vacuum_entity_id=_VAC)
    trouble_path.unlink(missing_ok=True)

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
    # Caller doesn't request a response here -- just asserting no exception.
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False},
        blocking=True,
    )


async def test_rebuild_learning_stats_returns_response(hass, learning_services):
    """[LS-4b] RP-031/Q9: rebuild_learning_stats now supports_response -- was
    fire-and-forget (-> None) even though the underlying rebuild always
    produces a real result dict a script could branch on."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["job_files_found"] == 0


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
# [LS-72] RP-039/RF-16 — the full SERVICES tuple registers AND unregisters
# ---------------------------------------------------------------------------

async def test_all_21_learning_services_register_and_unregister(hass, manager):
    """[LS-72] RP-039/RF-16: register/unregister walk the SAME SERVICES tuple, so
    they can never silently drift apart again.

    [LS-1]/[LS-14] above hand-list a SUBSET (12 and 3 of 21 respectively) — that
    shallow spot-check is exactly what let 5 services (SET_LEARNING_PROCESSING,
    PROCESS_PENDING_RUNS, CONFIRM_EXTERNAL_RUN, GET_EXTERNAL_PENDING_RUNS,
    DISCARD_EXTERNAL_RUN) drift out of the old hand-maintained unregister list
    without any test catching it. This iterates the module's own SERVICES tuple
    (currently 21 entries) so a future addition is covered automatically.
    """
    from custom_components.eufy_vacuum.learning import services as learning_services_module

    assert len(learning_services_module.SERVICES) == 21
    assert len(set(learning_services_module.SERVICES)) == 21, "duplicate service name in SERVICES"

    await async_register_learning_services(hass)
    missing = [s for s in learning_services_module.SERVICES if not hass.services.has_service(DOMAIN, s)]
    assert missing == [], f"registered but not found: {missing}"

    await async_unregister_learning_services(hass)
    leaked = [s for s in learning_services_module.SERVICES if hass.services.has_service(DOMAIN, s)]
    assert leaked == [], f"leaked on unregister (the RP-039 bug): {leaked}"


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


async def test_save_learning_snapshot_returns_response(hass, learning_services):
    """[LS-15b] RP-031/Q9: save_learning_snapshot now supports_response -- was
    fire-and-forget (-> None) even though it always builds a real snapshot dict."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_LEARNING_SNAPSHOT,
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "started_at": "2026-01-01T09:00:00+00:00",
            "battery_start": 85,
        },
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["snapshot"]["vacuum"]["entity_id"] == _VAC
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [LS-16] finalize_learning_job — runs against empty manager state
# ---------------------------------------------------------------------------

async def test_finalize_learning_job_empty_state(hass, learning_services):
    """[LS-16] RP-001/GATE4 Q1 superseded this test's premise: finalize with NO active
    job record used to save a job file and fire the finished event unconditionally.
    "A job record that does not exist cannot be finalized" -- it must now refuse
    (no_active_job_record) and fire no event."""
    from custom_components.eufy_vacuum.const import EVENT_JOB_FINISHED
    from homeassistant.exceptions import ServiceValidationError
    fired = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: fired.append(e))

    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB
    with pytest.raises(ServiceValidationError, match="no_active_job_record"):
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
    await hass.async_block_till_done()
    assert fired == []


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
    # queue_room_ids = [1, 2]. RP-001/GATE4 Q1: finalize now requires a stored active-job
    # record to finalize against, so seed one matching the call's started_at -- with no
    # completed_room_ids, so both queued rooms are still missed.
    setup_map(learning_services, _VAC, _MAP, count=2)
    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")

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
    """[LS-20] Two INTERRUPTED finalize calls with the same rooms flag them is_trouble=True.

    Was "cancelled" until 2026-08-02. A user cancel is no longer evidence about a room —
    it says nothing about rooms the run had not reached, and counting it flagged healthy
    rooms as chronic (Entryway 5/9 live). An interrupted run is still evidence: there the
    robot genuinely failed to finish, which is what this counter exists to surface.
    """
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
        "forced_outcome_status": "interrupted",
    }
    # Two interrupted jobs — both rooms missed each time → miss_count reaches 2. RP-001/
    # GATE4 Q1: finalize requires a stored active-job record, and a successful finalize
    # marks that slot `finalized`. Re-seed before each call to model two SEPARATE
    # dispatched job runs on the same map (a fresh dispatch overwrites the slot in
    # production, same as here) rather than re-finalizing one already-finalized slot.
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
    await hass.services.async_call(DOMAIN, SERVICE_FINALIZE_LEARNING_JOB, _finalize, blocking=True)
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
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


async def test_cancelled_runs_never_reach_the_trouble_counter(hass, learning_services):
    """[LS-20] The companion to the above: the SAME two runs, cancelled instead of
    interrupted, must leave the counter untouched. A day of cancel-testing flagged two
    healthy rooms as chronic trouble because this was not true."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    setup_map(learning_services, _VAC, _MAP, count=2)
    learning_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    _finalize = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "battery_start": 85, "battery_end": 75,
        "started_at": "2026-01-01T09:00:00+00:00",
        "ended_at": "2026-01-01T09:02:00+00:00",
        "used_for_learning": False, "rebuild_stats": False,
        "forced_outcome_status": "cancelled",
    }
    async def _counter():
        r = await hass.services.async_call(
            DOMAIN, SERVICE_GET_TROUBLE_ROOMS_LOG, {"vacuum_entity_id": _VAC},
            blocking=True, return_response=True,
        )
        return {k: (v or {}).get("miss_count", 0) for k, v in (r.get("rooms") or {}).items()}

    # Asserted as a DELTA, not an absolute: the suite shares a store, so a sibling test's
    # counter is legitimately already there. What must hold is that a cancel moves nothing.
    before = await _counter()
    for _ in range(2):
        _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
        await hass.services.async_call(DOMAIN, SERVICE_FINALIZE_LEARNING_JOB, _finalize, blocking=True)
    assert await _counter() == before, "a cancelled run moved the trouble counter"


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
# [LS-21b] RP-002/RF-01: finalize refusal raises, not a fabricated "completed" event
# ---------------------------------------------------------------------------

async def test_finalize_service_refusal_raises_service_validation_error(hass, learning_services):
    """[LS-21b] A finalize refusal (no active job for this call, per GATE4 Q1) must
    raise ServiceValidationError carrying the reason -- not fire EVENT_JOB_FINISHED
    with a fabricated status="completed" default."""
    from homeassistant.exceptions import ServiceValidationError
    from custom_components.eufy_vacuum.const import EVENT_JOB_FINISHED
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    finished = []
    hass.bus.async_listen(EVENT_JOB_FINISHED, lambda e: finished.append(e))

    with pytest.raises(ServiceValidationError, match="no_active_job_record"):
        await hass.services.async_call(
            DOMAIN, SERVICE_FINALIZE_LEARNING_JOB,
            {
                "vacuum_entity_id": _VAC, "map_id": _MAP,
                "battery_start": 85, "battery_end": 60,
                "started_at": "2026-01-01T09:00:00+00:00",
                "used_for_learning": True, "rebuild_stats": False,
            },
            blocking=True,
        )
    await hass.async_block_till_done()
    assert finished == [], "a refusal fired EVENT_JOB_FINISHED"


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

    # Single-room jobs carry the FLAT setting codes so the card localizes the
    # profile in the user's (globe) language via _localizedProfile — not the
    # backend's English profile_label snapshot. (learning/manager enrichment loop.)
    kitchen_job = next(j for j in jobs if j.get("job_id") == "j-hist-001")
    for code in ("clean_mode", "clean_intensity", "fan_speed", "water_level"):
        assert code in kitchen_job, f"single-room job missing flat setting code {code!r}"
    assert kitchen_job.get("clean_mode")   # seeded 'vacuum', normalized → non-empty
    assert kitchen_job.get("room_label")   # room prefix for the composed localized label


# ---------------------------------------------------------------------------
# [LS-RE] run_errors — CARD-3: the history snapshot NAMES the faults a run hit.
#
# The evidence has been persisted end to end for both origins since the finalizer
# wrote it, and nothing ever read it: had_errors/error_count said a run hit three
# faults and never which three. error_label_key/error_source_for_code existed, were
# tested, and had ZERO production callers.
#
# Brand-agnostic on purpose [[feedback_brand_agnostic_tests]] — a stub adapter owns
# the code space so these assert the SEAM, not Eufy's table.
# ---------------------------------------------------------------------------

def _register_fault_adapter(vac: str) -> None:
    """Stub adapter declaring a tiny fault vocabulary, in BOTH code spaces."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(vac, {
        "adapter_id": "test_faults",
        "source": "test",
        "error_tracking": {
            "error_label_keys": {
                1: "fault.test.bumper_stuck",
                6021: "fault.test.dirty_tank_full",
                "bumper_stuck": "fault.test.bumper_stuck",
            },
            "dock_sourced_error_codes": [6021],
            "robot_sourced_error_codes": [1, "bumper_stuck"],
        },
    })


def _latch(*entries) -> dict:
    """An error latch in the shape BOTH origins persist under outcome['errors']."""
    return {"error_count": len(entries), "errors": list(entries)}


async def _history_snapshot(hass) -> dict:
    """Rebuild the jobs index, then fetch the snapshot.

    Seeding writes the job FILE; the snapshot reads the INDEX, which only picks up
    new records on a rebuild. The store also outlives an individual test, so
    without this a test silently sees whichever jobs a PREVIOUS test indexed —
    which made an earlier draft of the clean-run control pass vacuously, its
    assertion loop never running because none of its jobs were present.
    """
    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()
    return await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )


def _job_from(result: dict, job_id: str) -> dict:
    """Pull one job out of a snapshot, reporting what WAS there when it is absent.
    A bare next() raises StopIteration, which inside a coroutine surfaces as an
    opaque RuntimeError and hides which ids came back."""
    jobs = result.get("jobs", [])
    for job in jobs:
        if job.get("job_id") == job_id:
            return job
    raise AssertionError(
        f"{job_id!r} not in snapshot; got {[j.get('job_id') for j in jobs]!r}"
    )


async def test_run_errors_names_the_faults(hass, learning_services):
    """[LS-RE1] A run's faults arrive named, sourced, and with recovery state."""
    _register_fault_adapter(_VAC)
    _seed_completed_job(
        hass, _VAC, "j-err-1", room_slugs=["kitchen"],
        outcome_extra={
            "had_errors": True,
            "error_count": 2,
            "errors": _latch(
                {"code": 1, "captured_at": "2026-01-01T09:05:00+00:00",
                 "recovered_at": "2026-01-01T09:06:00+00:00", "room_id": 1},
                {"code": 6021, "captured_at": "2026-01-01T09:20:00+00:00",
                 "recovered_at": None, "room_id": 2},
            ),
        },
    )
    result = await _history_snapshot(hass)
    job = _job_from(result, "j-err-1")
    rows = job.get("run_errors")
    assert isinstance(rows, list) and len(rows) == 2, "the faults never reached the card"

    # Robot-side fault, recovered mid-run.
    assert rows[0]["code"] == 1
    assert rows[0]["label_key"] == "fault.test.bumper_stuck"
    assert rows[0]["source"] == "robot"
    assert rows[0]["recovered"] is True

    # DOCK-1: a station fault, still latched at the end. The source is what the
    # user needs — it says which box to go and look at.
    assert rows[1]["source"] == "dock"
    assert rows[1]["recovered"] is False


async def test_run_errors_resolves_enum_string_codes(hass, learning_services):
    """[LS-RE2] Brands whose codes are enum STRINGS resolve too, not just ints.

    Roborock surfaces `bumper_stuck`, not 1. Core normalises through _code_key;
    before that, every seam opened with _exact_int and a string was dead on arrival.
    """
    _register_fault_adapter(_VAC)
    _seed_completed_job(
        hass, _VAC, "j-err-str", room_slugs=["kitchen"],
        outcome_extra={"had_errors": True, "error_count": 1, "errors": _latch(
            {"code": "bumper_stuck", "captured_at": "2026-01-01T09:05:00+00:00",
             "recovered_at": None},
        )},
    )
    result = await _history_snapshot(hass)
    job = _job_from(result, "j-err-str")
    assert job["run_errors"][0]["label_key"] == "fault.test.bumper_stuck"
    assert job["run_errors"][0]["source"] == "robot"


async def test_unlabelled_code_yields_none_not_a_guess(hass, learning_services):
    """[LS-RE3] A code the adapter has no label for gets label_key None and
    source 'unknown' — the card then renders the RAW code, which is honest and
    searchable. Inventing a label would point the user at the wrong hardware."""
    _register_fault_adapter(_VAC)
    _seed_completed_job(
        hass, _VAC, "j-err-unk", room_slugs=["kitchen"],
        outcome_extra={"had_errors": True, "error_count": 1, "errors": _latch(
            {"code": 999999, "captured_at": "2026-01-01T09:05:00+00:00",
             "recovered_at": None},
        )},
    )
    result = await _history_snapshot(hass)
    row = _job_from(result, "j-err-unk")["run_errors"][0]
    assert row["label_key"] is None
    assert row["source"] == "unknown"
    assert row["code"] == 999999, "the raw code must survive — it is the fallback"


async def test_run_errors_is_empty_for_a_clean_run(hass, learning_services):
    """[LS-RE4] Control: no latch, a malformed latch, and a latch with no entries
    all yield [] rather than raising or fabricating a row."""
    _register_fault_adapter(_VAC)
    for job_id, extra in (
        ("j-clean-1", {}),
        ("j-clean-2", {"errors": None}),
        ("j-clean-3", {"errors": "not-a-dict"}),
        ("j-clean-4", {"errors": {"error_count": 0}}),
        ("j-clean-5", {"errors": {"errors": "not-a-list"}}),
        ("j-clean-6", {"errors": {"errors": [None, 7, "junk"]}}),
    ):
        _seed_completed_job(hass, _VAC, job_id, room_slugs=["kitchen"], outcome_extra=extra)
    result = await _history_snapshot(hass)
    seen = 0
    for job in result["jobs"]:
        if str(job.get("job_id", "")).startswith("j-clean-"):
            seen += 1
            assert job.get("run_errors") == [], f"{job['job_id']} fabricated a fault row"
    # Without this the loop passes vacuously when the jobs are absent -- which is
    # exactly what an earlier draft of this test did.
    assert seen == 6, f"control only saw {seen}/6 seeded clean jobs"


async def test_run_errors_caps_rows_but_never_the_count(hass, learning_services):
    """[LS-RE5] A flapping run can latch dozens. The LIST is capped so the card
    shows a summary; error_count is NOT, so a truncated list is still recognisable
    as truncated instead of silently under-reporting."""
    _register_fault_adapter(_VAC)
    _seed_completed_job(
        hass, _VAC, "j-err-many", room_slugs=["kitchen"],
        outcome_extra={
            "had_errors": True,
            "error_count": 40,
            "errors": {"error_count": 40, "errors": [
                {"code": 1, "captured_at": "2026-01-01T09:05:00+00:00",
                 "recovered_at": None} for _ in range(40)
            ]},
        },
    )
    result = await _history_snapshot(hass)
    job = _job_from(result, "j-err-many")
    assert len(job["run_errors"]) == 12
    assert job["error_count"] == 40, "the count must not inherit the list's cap"


async def test_app_started_runs_get_named_faults_too(hass, learning_services):
    """[LS-RE6] The external ingest writes outcome['errors'] under the SAME key and
    shape as the dispatched finalizer, deliberately, so one reader serves both. If
    that ever diverges, app-started runs silently lose their fault names."""
    _register_fault_adapter(_VAC)
    _seed_completed_job(
        hass, _VAC, "j-ext-err", room_slugs=["kitchen"], origin="external",
        outcome_extra={"had_errors": True, "error_count": 1, "errors": _latch(
            {"code": 6021, "captured_at": "2026-01-01T09:05:00+00:00",
             "recovered_at": None},
        )},
    )
    result = await _history_snapshot(hass)
    job = _job_from(result, "j-ext-err")
    assert job.get("origin") == "external"
    assert job["run_errors"][0]["label_key"] == "fault.test.dirty_tank_full"
    assert job["run_errors"][0]["source"] == "dock"


# ---------------------------------------------------------------------------
# [LS-JD] Job-summary detail — the recharge line and per-room rows the modal needs.
#
# Both are DERIVED at read time from the archived record, so a job written before
# the current rules gets the current answer instead of staying frozen.
# ---------------------------------------------------------------------------

def _seed_with_record(hass, job_id: str, *, battery=None, rooms=None, timings=None):
    """Seed a job then overwrite the archived record's battery/room blocks.

    _seed_completed_job's fixed shape cannot express these, and the derivations
    read the ARCHIVED record rather than the index row.
    """
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

    payload = _seed_completed_job(hass, _VAC, job_id, room_slugs=["kitchen"])
    if battery is not None:
        payload["battery"] = battery
    if rooms is not None:
        payload["resolved_rooms"] = rooms
        payload["job_profile"]["rooms"] = rooms
    if timings is not None:
        payload["job"]["room_timings"] = timings
    LearningHistoryStore(hass).save_completed_job(
        vacuum_entity_id=_VAC, job_id=job_id, payload=payload
    )
    return payload


async def test_recharge_is_derived_so_stale_records_heal(hass, learning_services):
    """[LS-JD1] The real defect this exists for: alfred job_2026-08-05T02-52-05
    stored mid_job_recharge_observed=False while carrying count=1 and 6059 s of
    accumulated charge, because the live flag is CLEARED on resume and the record
    froze that. Re-deriving from the accumulators corrects it."""
    _seed_with_record(hass, "j-recharge-stale", battery={
        "start": 39, "end": 28, "used": 11,
        "mid_job_recharge_observed": False,      # the stale, wrong conclusion
        "mid_job_recharge_count": 1,
        "recharge_seconds_accumulated": 6059,
        "mid_job_recharge_started_at": "2026-08-05T03:10:00+00:00",
    })
    job = _job_from(await _history_snapshot(hass), "j-recharge-stale")
    rc = job.get("recharge")
    assert rc, "a run that recharged reported nothing"
    assert rc["observed"] is True, "stored False was trusted over the accumulators"
    assert rc["count"] == 1
    assert rc["seconds"] == 6059
    assert rc["recovered_from_stale_record"] is True


async def test_recharge_absent_on_a_run_that_did_not(hass, learning_services):
    """[LS-JD2] None, not a zeroed block — the card omits the row rather than
    rendering a confident 'recharged 0 times'."""
    for job_id, battery in (
        ("j-nore-1", {"start": 100, "end": 91, "used": 9,
                      "mid_job_recharge_observed": False,
                      "mid_job_recharge_count": 0,
                      "recharge_seconds_accumulated": 0}),
        ("j-nore-2", {"start": 100, "end": 91, "used": 9}),   # older, no fields
        ("j-nore-3", None),                                    # no battery block
    ):
        _seed_with_record(hass, job_id, battery=battery)
    snap = await _history_snapshot(hass)
    for job_id in ("j-nore-1", "j-nore-2", "j-nore-3"):
        assert _job_from(snap, job_id).get("recharge") is None, job_id


async def test_recharge_still_honours_the_live_flag(hass, learning_services):
    """[LS-JD3] Finalizing while still docked and charging is the one case the
    accumulators cannot cover — the resume that would accrue the seconds has not
    happened. history_store.py:1699 keeps the live flag in its OR for exactly this,
    and so must the derivation."""
    _seed_with_record(hass, "j-recharge-live", battery={
        "start": 28, "end": 17, "used": 11,
        "mid_job_recharge_observed": True,
        "mid_job_recharge_count": 0,
        "recharge_seconds_accumulated": 0,
    })
    rc = _job_from(await _history_snapshot(hass), "j-recharge-live")["recharge"]
    assert rc["observed"] is True
    assert rc["recovered_from_stale_record"] is False, "nothing was corrected here"


async def test_room_detail_uses_the_settings_the_run_dispatched(hass, learning_services):
    """[LS-JD4] Settings come from the record, never the room's CURRENT profile —
    which may have been edited since the run. Both cleaning times are carried
    because they disagree on 110 of 113 real entries."""
    rooms = [{"slug": "kitchen", "room_id": 5, "name": "Kitchen",
              "clean_mode": "vacuum", "fan_speed": "max", "clean_intensity": "deep",
              "water_level": "off", "path_type": "wide", "clean_passes": 2,
              "edge_mopping": False},
             {"slug": "hall", "room_id": 8, "name": "Hall",
              "clean_mode": "vacuum", "fan_speed": "quiet", "clean_passes": 1}]
    timings = [{"room_id": 5, "slug": "kitchen", "cleaning_seconds": 1050,
                "cleaning_wall_seconds": 1065, "area_m2": 12.5,
                "battery_delta": 21.0, "boundary": "job_start"}]
    _seed_with_record(hass, "j-rooms", rooms=rooms, timings=timings)

    detail = _job_from(await _history_snapshot(hass), "j-rooms")["room_detail"]
    assert len(detail) == 2

    kitchen = next(r for r in detail if r["room_id"] == 5)
    assert kitchen["settings"]["fan_speed"] == "max"
    assert kitchen["settings"]["clean_passes"] == 2
    # edge_mopping False is a real setting, not a missing one.
    assert kitchen["settings"]["edge_mopping"] is False
    assert kitchen["cleaning_seconds"] == 1050
    assert kitchen["cleaning_wall_seconds"] == 1065, "the two times were collapsed"
    assert kitchen["area_m2"] == 12.5
    assert kitchen["has_result"] is True
    assert "battery_delta" not in kitchen and "battery" not in kitchen, (
        "per-room battery was surfaced -- it does not reconcile with the job total"
    )

    # A queued room the run never reached: settings, no result. Normal, not an error.
    hall = next(r for r in detail if r["room_id"] == 8)
    assert hall["has_result"] is False
    assert hall["cleaning_seconds"] is None
    assert hall["settings"]["fan_speed"] == "quiet"
    assert "clean_intensity" not in hall["settings"], "an absent setting was invented"


async def test_room_detail_joins_on_room_id_not_slug(hass, learning_services):
    """[LS-JD5] Slugs repeat across maps; room ids are the run's own keys. Joining
    on slug would attach one room's result to another's settings."""
    rooms = [{"slug": "kitchen", "room_id": 5, "name": "Kitchen", "fan_speed": "max"},
             {"slug": "kitchen", "room_id": 9, "name": "Kitchen (upstairs)",
              "fan_speed": "quiet"}]
    timings = [{"room_id": 9, "slug": "kitchen", "cleaning_seconds": 600,
                "cleaning_wall_seconds": 610, "area_m2": 3.0}]
    _seed_with_record(hass, "j-dupslug", rooms=rooms, timings=timings)

    detail = _job_from(await _history_snapshot(hass), "j-dupslug")["room_detail"]
    by_id = {r["room_id"]: r for r in detail}
    assert by_id[9]["cleaning_seconds"] == 600
    assert by_id[5]["cleaning_seconds"] is None, "the result landed on the wrong room"


async def test_room_detail_survives_malformed_records(hass, learning_services):
    """[LS-JD6] Control: junk in the record yields [] rather than raising inside a
    service call the whole history view depends on."""
    for job_id, rooms, timings in (
        ("j-bad-1", [], None),
        ("j-bad-2", "not-a-list", None),
        ("j-bad-3", [None, 7, "junk"], None),
        ("j-bad-4", [{"slug": "kitchen", "room_id": 5}], "not-a-list"),
        ("j-bad-5", [{"slug": "kitchen", "room_id": 5}], [None, "junk"]),
    ):
        _seed_with_record(hass, job_id, rooms=rooms, timings=timings)
    snap = await _history_snapshot(hass)
    for job_id in ("j-bad-1", "j-bad-2", "j-bad-3"):
        assert _job_from(snap, job_id)["room_detail"] == [], job_id
    for job_id in ("j-bad-4", "j-bad-5"):
        rows = _job_from(snap, job_id)["room_detail"]
        assert len(rows) == 1 and rows[0]["has_result"] is False, job_id


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


async def test_get_room_learning_estimates_forwards_edge_mopping(
    hass, learning_services, monkeypatch
):
    """[LS-26a] REGRESSION: the manager entry point must FORWARD edge_mopping to
    _find_room_match. It is part of the learned room key (schema 6), but the parameter
    carries `edge_mopping: bool = False`, so an omitted argument silently returns the
    edge-OFF bucket at full confidence instead of raising. The unit test
    test_find_room_match_edge_split proves the matcher itself is correct; nothing
    previously drove it through this call site."""
    from tests.integration.conftest import setup_map
    from custom_components.eufy_vacuum.learning.services import SERVICE_GET_ROOM_LEARNING_ESTIMATES
    # The manager imports _find_room_match locally at call time, so patch the source
    # module (learning.estimator) — the call-time import picks the patch up.
    from custom_components.eufy_vacuum.learning import estimator as learning_estimator

    setup_map(learning_services, _VAC, _MAP, count=1)
    rooms_bucket = (
        learning_services.data
        .get("maps", {}).get(_VAC, {}).get(_MAP, {}).get("rooms", {})
    )
    assert "1" in rooms_bucket
    rooms_bucket["1"]["slug"] = "room_1"
    rooms_bucket["1"]["edge_mopping"] = True

    seen: list[object] = []
    real = learning_estimator._find_room_match

    def _capture(**kwargs):
        seen.append(kwargs.get("edge_mopping", "MISSING"))
        return real(**kwargs)

    monkeypatch.setattr(learning_estimator, "_find_room_match", _capture)

    await hass.services.async_call(
        DOMAIN, SERVICE_GET_ROOM_LEARNING_ESTIMATES,
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )

    assert seen, "_find_room_match was never called — fixture no longer exercises the lookup"
    # The defect was that the kwarg was NEVER PASSED, so the matcher's `= False` default
    # silently selected the edge-OFF bucket. Assert forwarding, which is the broken
    # contract; the matcher's own edge split is proven by test_find_room_match_edge_split.
    # Before the fix this captured "MISSING".
    assert seen[0] != "MISSING", "edge_mopping was not forwarded to _find_room_match"
    assert isinstance(seen[0], bool)


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

    # RP-001/GATE4 Q1: finalize requires a stored active-job record.
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
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
    """[LS-29] deductible error seconds > cleaning_time_seconds → clamped to 0.

    RF-DOCK amended this test. It used to carry a code-less error entry, because the
    deduction was flat: every error second came off cleaning time regardless of whose
    fault it was. That is the defect RP-046 repairs, so the entry now carries a code
    that genuinely invalidates the run's cleaning evidence (2112 ROLLER BRUSH
    OVERCURRENT) and the adapter declares the table core reads. The CLAMP is still
    real behaviour and still worth pinning; what changed is what reaches it.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
    from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    register_adapter_config(_VAC, {
        "error_tracking": {
            "evidence_invalidating_error_codes": [2112],
            "evidence_safe_error_codes": [6013],
        },
    })
    tracker = ErrorTracker(hass, runtime_manager=learning_services)
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = tracker
    record = tracker._ensure_record(_VAC)
    # 400s of errors vs 300s cleaning → clamped to 0.
    record["active_run_error"] = {
        "error_count": 1,
        "errors": [
            {"code": 2112, "captured_at": "2026-01-01T09:00:00+00:00", "recovered_at": "2026-01-01T09:06:40+00:00"},
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
# [LS-29b] RF-DOCK — a dock fault must NOT be deducted from cleaning time
# ---------------------------------------------------------------------------

async def test_finalize_dock_fault_does_not_reduce_cleaning_time(hass, learning_services):
    """The live incident: alfred job_2026-08-01T23-23-35 cleaned 4 m2 for 360 s and
    recorded ZERO, because five station clean-water-pump faults (6013) were charged
    against it while the robot worked straight through them."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
    from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    register_adapter_config(_VAC, {
        "error_tracking": {
            "evidence_invalidating_error_codes": [2112],
            "evidence_safe_error_codes": [6013],
        },
    })
    tracker = ErrorTracker(hass, runtime_manager=learning_services)
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = tracker
    record = tracker._ensure_record(_VAC)
    record["active_run_error"] = {
        "error_count": 1,
        "errors": [
            {"code": 6013, "captured_at": "2026-01-01T09:00:00+00:00", "recovered_at": "2026-01-01T09:06:40+00:00"},
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
    outcome = result.get("completed_job", {}).get("outcome", {})
    assert job.get("cleaning_time_seconds") == 300, "a dock fault must not deduct"
    # The full window stays visible; only the deducted share changed.
    assert outcome.get("total_error_seconds") == 400
    assert outcome.get("error_seconds_deducted") == 0
    assert (outcome.get("error_seconds_by_evidence") or {}).get("safe") == 400


async def test_finalize_unclassified_fault_is_preserved(hass, learning_services):
    """A brand with no declared table, or a code the vendor shipped after the table was
    written, must PRESERVE the run. Failing toward 'trust the run' is deliberate: wrongly
    crediting adds noise that averages out, wrongly zeroing destroys the observation."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
    from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    register_adapter_config(_VAC, {"error_tracking": {}})   # declares nothing
    tracker = ErrorTracker(hass, runtime_manager=learning_services)
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = tracker
    record = tracker._ensure_record(_VAC)
    record["active_run_error"] = {
        "error_count": 1,
        "errors": [
            {"code": 99999, "captured_at": "2026-01-01T09:00:00+00:00", "recovered_at": "2026-01-01T09:06:40+00:00"},
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
    completed = result.get("completed_job", {})
    assert completed.get("job", {}).get("cleaning_time_seconds") == 300
    outcome = completed.get("outcome", {})
    assert outcome.get("error_seconds_deducted") == 0
    assert (outcome.get("error_seconds_by_evidence") or {}).get("unclassified") == 400


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
    # First: cancelled → writes incomplete run log. RP-001/GATE4 Q1: finalize requires a
    # stored active-job record; re-seed before each call to model two separate dispatched
    # job runs (a fresh dispatch overwrites the slot in production).
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
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
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
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


async def test_get_learning_history_snapshot_origin_filter(hass, learning_services):
    """The origin filter prunes to external (app-started) vs internal (dispatched, origin absent).
    Binary + normalized: a dispatched job with no origin key still matches origin=internal."""
    _seed_completed_job(hass, _VAC, "j-ext", room_slugs=["kitchen"], origin="external")
    _seed_completed_job(hass, _VAC, "j-int", room_slugs=["bedroom"])  # no origin -> internal

    await hass.services.async_call(
        DOMAIN, SERVICE_REBUILD_LEARNING_STATS,
        {"vacuum_entity_id": _VAC, "rebuild_csv": False}, blocking=True,
    )
    await hass.async_block_till_done()

    ext = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "origin": "external"},
        blocking=True, return_response=True,
    )
    ext_ids = {j.get("job_id") for j in ext.get("jobs", [])}
    assert "j-ext" in ext_ids and "j-int" not in ext_ids
    assert ext.get("filters", {}).get("origin") == "external"

    internal = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC, "origin": "internal"},
        blocking=True, return_response=True,
    )
    int_ids = {j.get("job_id") for j in internal.get("jobs", [])}
    assert "j-int" in int_ids and "j-ext" not in int_ids


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


async def test_finalize_overhead_observed_from_transit_capture(hass, learning_services):
    """[LS-35b] when the built job is transit_capture_valid, finalize enriches
    job.overhead_observed: inter_room_minutes is the OBSERVED summed transit
    (not the cleaning-time-derived base). Drives job_finalizer 729-739 — the
    per-room transit enrichment branch, reachable only with captured transitions.
    Reuses the proven two-room counter-sample stream from the history-store suite.
    """
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager
    from tests.unit.test_learning_history_store import _TWO_ROOM_SAMPLES

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)

    # seed an active job carrying the captured counter stream + queue so the
    # build segments it into two rooms (transit_capture_valid=True).
    _seed_active_job(
        learning_services, _VAC, _MAP,
        started_at="2026-01-01T09:00:00+00:00",
        queue_room_ids=[1, 2],
        queue_rooms=[{"room_id": 1, "slug": "kitchen"}, {"room_id": 2, "slug": "bath"}],
        resolved_rooms=[{"room_id": 1, "slug": "kitchen"}, {"room_id": 2, "slug": "bath"}],
        counter_samples=_TWO_ROOM_SAMPLES,
    )

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
    job = result["completed_job"]["job"]
    assert job["transit_capture_valid"] is True
    assert job["transitions"][0]["transit_seconds"] == 300
    # the enrichment overrode inter_room_minutes with the observed transit sum
    # (300s / 60 = 5.0), proving the capture-valid branch ran (not the base).
    #
    # 300, not the raw 330 s gap: the counter advanced 30 s inside that window, so
    # the robot was cleaning for part of it. Counting that as inter-room overhead
    # inflated the estimate - measured 83% over on real runs (history_store
    # ._idle_seconds). The correction propagates here because overhead is the sum
    # of the transits.
    assert job["overhead_observed"]["inter_room_minutes"] == 5.0


# ---------------------------------------------------------------------------
# [LS-36] finalize with rebuild_stats=True, rebuild_csv=True
# ---------------------------------------------------------------------------

async def test_finalize_rebuild_csv(hass, learning_services):
    """[LS-36] rebuild_stats=True, rebuild_csv=True exercises lines 801-807 and manager line 622."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import SERVICE_FINALIZE_LEARNING_JOB

    # RP-001/GATE4 Q1: finalize requires a stored active-job record.
    _seed_active_job(learning_services, _VAC, _MAP, started_at="2026-01-01T09:00:00+00:00")
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
    # Clean slate: the test config_dir is shared/persistent across pytest runs, so
    # completed-job files seeded by OTHER tests (e.g. LS-70 seeds learning-eligible
    # 'study' jobs j-excl-yes/j-excl-no) survive into a repeat run. rebuild_learning_stats
    # below reads EVERY job file in jobs_dir, so those leftovers would push study's
    # learning_run_count above 0 and break the `== 0` assertion. Wipe this vacuum's
    # completed-job files + the derived jobs_index so the rebuild sees only the three
    # jobs this test seeds next.
    _store = LearningHistoryStore(hass)
    for _job_path in _store.list_job_files(vacuum_entity_id=_VAC):
        _job_path.unlink(missing_ok=True)
    _store.get_jobs_index_path(vacuum_entity_id=_VAC).unlink(missing_ok=True)

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


async def test_confirm_external_run_service_refreshes_cache(hass, learning_services, monkeypatch):
    """[LS-40] the confirm-external-run SERVICE handler invalidates + preloads the
    learning-stats cache after a successful confirm with rebuild_stats, so the card
    sees the graduated job (services.py handle_confirm_external_run 283-290).
    confirm_external_run is covered by CXR; it's stubbed here to isolate the
    handler's post-confirm cache refresh."""
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import (
        SERVICE_CONFIRM_EXTERNAL_RUN,
        _get_learning_manager,
    )

    core_manager = hass.data[DOMAIN]["runtime"]
    core_manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    learning = _get_learning_manager(hass)

    monkeypatch.setattr(
        core_manager, "confirm_external_run",
        lambda *a, **k: {"ok": True, "job_id": "ext-x", "rebuilt": True},
    )
    invalidated: list = []
    preloaded: list = []
    monkeypatch.setattr(
        learning, "_invalidate_learning_stats_cache",
        lambda *, vacuum_entity_id: invalidated.append(vacuum_entity_id),
    )
    monkeypatch.setattr(
        learning, "async_preload_learning_stats",
        lambda *, vacuum_entity_id: preloaded.append(vacuum_entity_id),
    )

    result = await hass.services.async_call(
        DOMAIN, SERVICE_CONFIRM_EXTERNAL_RUN,
        {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "pending_job_id": "job_x", "room_assignments": [{"room_id": 1}],
            "rebuild_stats": True,
        },
        blocking=True, return_response=True,
    )

    assert result["ok"] is True
    assert invalidated == [_VAC]  # cache invalidated for the vacuum ...
    assert preloaded == [_VAC]    # ... and preloaded so the card refreshes


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


async def test_history_snapshot_backfills_area_on_stale_index(hass, learning_services):
    """RETROACTIVE fix: an index with status+origin but predating has_attribution_disagreement is
    STALE (the origin-only self-heal wouldn't fire), so the snapshot rebuilds it and back-fills the
    external multi-room Area SUM + the flag on EXISTING runs. Regression for 'was the area fix only
    going forward' — it's retroactive on the next snapshot after a restart, no manual rebuild."""
    _seed_completed_job(
        hass, _VAC, "j-ext-area", room_slugs=["kitchen", "dining_room"], origin="external",
        room_timings=[{"room_id": 1, "slug": "kitchen", "area_m2": 4.0},
                      {"room_id": 2, "slug": "dining_room", "area_m2": 6.0}],
    )
    store = LearningHistoryStore(hass)
    # Stale index: status+origin present (old self-heal would treat it as new format), but no
    # has_attribution_disagreement and a null area — the exact pre-fix external state on disk.
    store.save_jobs_index(vacuum_entity_id=_VAC, payload={"jobs": [
        {"job_id": "j-ext-area", "status": "completed", "origin": "external", "cleaning_area_m2": None},
    ]})

    result = await hass.services.async_call(
        DOMAIN, SERVICE_GET_LEARNING_HISTORY_SNAPSHOT,
        {"vacuum_entity_id": _VAC}, blocking=True, return_response=True,
    )
    entry = next(j for j in result.get("jobs", []) if j.get("job_id") == "j-ext-area")
    assert entry["cleaning_area_m2"] == 10.0            # 4 + 6, summed from room_timings on rebuild
    assert entry["has_attribution_disagreement"] is False


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


# ---------------------------------------------------------------------------
# [LS-71] discard_external_run SERVICE handler resolves the manager + delegates
#         (services.py handle_discard_external_run, lines 358-364)
# ---------------------------------------------------------------------------

async def test_discard_external_run_service_delegates_to_manager(
    hass, learning_services, monkeypatch
):
    """[LS-71] The discard-external-run SERVICE handler resolves the core manager
    and delegates to core_manager.discard_external_run, returning its result
    verbatim (services.py handle_discard_external_run, lines 358-364).

    discard_external_run (the disk-mutating delete of a pending external record)
    is covered by its own unit tests; it is stubbed here to isolate the handler's
    two jobs: (1) resolve the runtime core manager via _get_core_manager and
    (2) hand the schema-validated call fields to the delegate on the executor,
    then surface its return to the caller. We assert the observable result the
    card would see AND spy on the exact positional args the delegate received,
    proving the handler forwarded vacuum_entity_id + pending_job_id in order.
    """
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.learning.services import (
        SERVICE_DISCARD_EXTERNAL_RUN,
    )

    core_manager = hass.data[DOMAIN]["runtime"]
    core_manager.ensure_vacuum_record(vacuum_entity_id=_VAC)

    captured: list = []

    def _fake_discard(vacuum_entity_id, pending_job_id):
        captured.append((vacuum_entity_id, pending_job_id))
        return {"ok": True, "discarded": pending_job_id}

    monkeypatch.setattr(core_manager, "discard_external_run", _fake_discard)

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_DISCARD_EXTERNAL_RUN,
        {"vacuum_entity_id": _VAC, "pending_job_id": "ext-pending-99"},
        blocking=True,
        return_response=True,
    )

    # The handler returned the delegate's result unchanged ...
    assert result == {"ok": True, "discarded": "ext-pending-99"}
    # ... and forwarded exactly the schema fields, in positional order.
    assert captured == [(_VAC, "ext-pending-99")]


# ---------------------------------------------------------------------------
# [LS-54a] a run excluded from learning must not feed accuracy_stats either
# ---------------------------------------------------------------------------

async def _drive_finalize(hass, learning, monkeypatch, *, used_for_learning: bool):
    """Run async_finalize_completed_job with the finalizer stubbed, returning the calls
    made to _auto_record_accuracy."""
    calls: list[int] = []
    monkeypatch.setattr(
        learning, "_auto_record_accuracy",
        lambda **kw: (calls.append(1), {"recorded": True})[1],
    )
    monkeypatch.setattr(
        learning.finalizer, "_collect_finalization_inputs",
        lambda **kw: {"outcome_status": "completed", "active_job_state": {}, "job_id": "j1"},
    )
    monkeypatch.setattr(
        learning.finalizer, "finalize_from_inputs",
        lambda **kw: {
            "completed_job": {
                "outcome": {"status": "completed", "used_for_learning": used_for_learning}
            }
        },
    )
    monkeypatch.setattr(learning, "_record_zone_learning", None, raising=False)

    manager = hass.data[DOMAIN]["runtime"]
    # RP-001/GATE4 Q1: finalize requires a stored active-job record — seed one matching
    # this call, modeling a normal dispatched-and-tracked job being finalized directly at
    # the chokepoint (the finalize_learning_job service's call pattern).
    _seed_active_job(manager, _VAC, _MAP, started_at="2026-01-01T10:00:00+00:00")
    await learning.async_finalize_completed_job(
        manager=manager,
        vacuum_entity_id=_VAC, map_id=_MAP,
        battery_start=90, battery_end=60,
        started_at="2026-01-01T10:00:00+00:00",
        ended_at="2026-01-01T10:30:00+00:00",
    )
    return calls


async def test_accuracy_is_not_recorded_for_a_run_excluded_from_learning(
    hass, learning_services, monkeypatch
):
    """[LS-54a] Accuracy measures ESTIMATE vs ACTUAL. Every reason a run is excluded from
    learning -- cancelled, interrupted, an idle-wall anomaly, a manual exclude -- is a
    reason its ACTUAL duration is unrepresentative, so recording it does not measure
    estimator drift; it measures the anomaly, and then penalises confidence for it.

    This previously fired unconditionally, on the reasoning that accuracy data was "still
    useful" for excluded jobs. A run we do not trust for learning is not trustworthy for
    anything derived from its duration. Gating here also keeps the live path in agreement
    with the archive rebuild -- gating only one would let a rebuild silently change values.
    """
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(hass)
    calls = await _drive_finalize(hass, learning, monkeypatch, used_for_learning=False)
    assert calls == [], "an excluded run fed accuracy_stats"


async def test_accuracy_is_still_recorded_for_an_eligible_run(
    hass, learning_services, monkeypatch
):
    """[LS-54a] The inverse -- the gate must not simply disable accuracy recording. Without
    this, the test above would pass on a change that removed the call entirely."""
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(hass)
    calls = await _drive_finalize(hass, learning, monkeypatch, used_for_learning=True)
    assert calls == [1], "an eligible run stopped feeding accuracy_stats"


# ---------------------------------------------------------------------------
# [LS-56] accuracy_stats becomes repairable from the archive
# ---------------------------------------------------------------------------

async def test_rebuild_accuracy_stats_recomputes_from_the_archive(hass, learning_services):
    """[LS-56] Group B: the last of the three incremental accumulators becomes repairable.

    accuracy_stats is a read-modify-write store outside rebuild_all, so a bad sample was
    permanent — and unlike the other two it feeds the CONFIDENCE penalty, so a poisoned
    entry quietly degrades every estimate for that room.

    The rebuild replays through _auto_record_accuracy, the SAME extractor the live path
    uses, so it cannot drift from what the live fold produced. It rebuilds from EMPTY, and
    an excluded run must stay out — which is what makes exclude_learning_job finally
    effective against accuracy.
    """
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(hass)

    def _rec(minutes, *, used=True, status="completed"):
        return {
            "record_type": "completed_job",
            "map_id": _MAP,
            "outcome": {"status": status, "used_for_learning": used},
            "job": {"duration_minutes": minutes, "map_id": _MAP},
            "job_profile": {"rooms": [{
                "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
                "is_carpet": False, "clean_intensity": "standard",
                "estimated_minutes": 10,
            }]},
            "resolved_rooms": [{
                "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
                "is_carpet": False, "clean_intensity": "standard",
                "estimated_minutes": 10, "map_id": _MAP,
            }],
        }

    archive = [_rec(12), _rec(14), _rec(999, used=False)]  # the last must NOT contribute
    learning.store.load_all_completed_jobs = lambda **kw: archive

    # Poison the store the way a duplicate finalize would.
    learning.store.save_accuracy_stats(
        vacuum_entity_id=_VAC, payload={"rooms": {"poisoned": {"sample_count": 99}}}
    )

    applied = learning.rebuild_accuracy_stats(vacuum_entity_id=_VAC)

    stats = learning.store.load_accuracy_stats(vacuum_entity_id=_VAC) or {}
    assert "poisoned" not in (stats.get("rooms") or {}), "the rebuild folded onto stale data"
    assert applied == 2, f"expected the 2 learning-eligible records, got {applied}"


# ---------------------------------------------------------------------------
# [LS-29c] RF-DOCK clause 4 — the record says WHOSE hardware raised the seconds
# ---------------------------------------------------------------------------

async def test_finalize_reports_error_seconds_by_source(hass, learning_services):
    """[LS-29c] error_seconds_by_source attributes preserved seconds to the dock.

    Drives the live incident's own shape (alfred job_2026-08-01T23-23-35): a
    productive 360 s clean with 455 s of code-6013 STATION CLEAN WATER PUMP SHORT
    raised while the robot worked straight through it.

    The evidence axis alone already stops the deduction — that is RP-046's first
    half and it is asserted here too. What clause 4 adds is that the record can
    now say the 455 s came from the DOCK. Without it the user is told their run
    was fine and never told their station's pump is failing.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
    from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    register_adapter_config(_VAC, {
        "error_tracking": {
            "evidence_invalidating_error_codes": [2112],
            "evidence_safe_error_codes": [6013],
            "dock_sourced_error_codes": [6013],
            "robot_sourced_error_codes": [2112],
        },
    })
    tracker = ErrorTracker(hass, runtime_manager=learning_services)
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = tracker
    record = tracker._ensure_record(_VAC)
    record["active_run_error"] = {
        "error_count": 1,
        "errors": [
            {"code": 6013,
             "captured_at": "2026-01-01T09:00:00+00:00",
             "recovered_at": "2026-01-01T09:07:35+00:00"},   # 455 s
        ],
    }
    _seed_active_job(learning_services, _VAC, _MAP, last_cleaning_time_seconds=360)

    core_manager = hass.data[DOMAIN]["runtime"]
    learning_mgr = _get_learning_manager(hass)
    result = await hass.async_add_executor_job(
        lambda: learning_mgr.finalize_completed_job(
            manager=core_manager, vacuum_entity_id=_VAC, map_id=_MAP,
            battery_start=85, battery_end=82,
            started_at="2026-01-01T09:00:00+00:00",
            ended_at="2026-01-01T09:30:00+00:00",
            used_for_learning=False, rebuild_stats=False,
        )
    )
    job = result.get("completed_job", {}).get("job", {})
    outcome = result.get("completed_job", {}).get("outcome", {})

    # first half (already shipped): a dock fault is NOT charged against the clean
    assert job.get("cleaning_time_seconds") == 360
    assert outcome.get("total_error_seconds") == 455   # full window still visible
    assert outcome.get("error_seconds_deducted") == 0
    assert (outcome.get("error_seconds_by_evidence") or {}).get("safe") == 455

    # clause 4: and the record says the 455 s came from the DOCK
    by_source = outcome.get("error_seconds_by_source") or {}
    assert by_source.get("dock") == 455
    assert by_source.get("robot") == 0
    assert by_source.get("unknown") == 0


def test_review_payload_states_its_own_truncation(manager):
    """[LS-REV5] REV-5: the list is cut to `limit`; the payload must say so.

    filtered_job_count is counted BEFORE `enriched_jobs[:limit_value]`, so the
    headline stat read "127 runs" over a list of 50 with nothing indicating the
    cut. A cap the user cannot see is indistinguishable from there being nothing
    more to see.

    Both numbers are emitted rather than one being "corrected": filtered_job_count
    remains the honest answer to "how many runs match" — which the stat should keep
    showing — and returned_job_count answers "how many are in this payload".
    """
    from custom_components.eufy_vacuum.learning.services import _get_learning_manager

    learning = _get_learning_manager(manager.hass)
    payload = learning.get_learning_history_snapshot(vacuum_entity_id=_VAC, limit=2)
    summary = payload["summary"]

    assert "returned_job_count" in summary, "the payload cannot state its own cut"
    assert "jobs_truncated" in summary
    assert summary["returned_job_count"] == len(payload["jobs"])
    assert summary["returned_job_count"] <= summary["filtered_job_count"]
    if summary["filtered_job_count"] > 2:
        assert summary["jobs_truncated"] is True
        assert summary["returned_job_count"] == 2
    else:
        assert summary["jobs_truncated"] is False
