"""Unit tests for jobs/active_job.py — pure module helpers + ActiveJobTracker
pure methods (constructed with a mock manager, no hass access).

Coverage targets
----------------
[AJ-1]  _safe_int: sentinels/None → default; float-string truncates.
[AJ-2]  _safe_float: sentinels/None → default.
[AJ-3]  _normalize_path_block_action: valid action kept, else event_only.
[AJ-4]  _normalize_pause_timeout_minutes: negative clamped to 0.
[AJ-5]  _default_active_job_state: shape, str map_id, idle status.
[AJ-6]  _derive_active_job_current_room_id: first uncompleted resolved room.
[AJ-7]  _derive_active_job_current_room_id: skips completed, falls to queue ids.
[AJ-8]  _derive_active_job_current_room_id: all completed → None.
[AJ-9]  _normalize_active_job: fills defaults + normalizes policy fields.
[AJ-10] _normalize_active_job: derives current_room_id when absent.
[AJ-11] _normalize_active_job: current_room_started_at defaults to started_at.
[AJ-12] _normalize_active_job: non-dict input → defaulted dict.
[AJ-13] _compute_current_room_elapsed_minutes: plain elapsed.
[AJ-14] _compute_current_room_elapsed_minutes: subtracts live pause when paused.
[AJ-15] _compute_current_room_elapsed_minutes: bad timestamps → 0.0.
[AJ-16] _room_name_from_active_job: resolved-room match.
[AJ-17] _room_name_from_active_job: queue-room fallback.
[AJ-18] _room_name_from_active_job: None/negative/no-match → None.
[AJ-19] _timing_completion_threshold_minutes: high confidence → tight slack.
[AJ-20] _timing_completion_threshold_minutes: low confidence + few samples → wider slack.
[AJ-21] _live_transition_config: no adapter block → distinct copy of defaults.
[AJ-22] _live_transition_config: adapter block overrides every key; rollover_kinds → stripped tuple.
[AJ-23] _live_transition_config: all-empty rollover_kinds → default tuple; unset keys stay default.
[AJ-24] detect_run_anomalies: running_long suppressed for an unlearned room (issue #40).
[AJ-25] detect_run_anomalies: running_long still fires for a learned room (AJ-24 control).
[AJ-26] poll_stranded_started_job: Eufy strand stamps first tick, reaps only past grace.
[AJ-27] poll_stranded_started_job: task_status == completion value → no stamp, None.
[AJ-28] poll_stranded_started_job: a stamped strand that resumes clears the stamp.
[AJ-29] poll_stranded_started_job: Roborock strand (docked, not 'charging', job_active off) reaps.
[AJ-30] poll_stranded_started_job: Roborock recharge (job_active ON) → no stamp, None.
[AJ-31] poll_stranded_started_job: a paused job is left to the pause-timeout reaper.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.adapters.registry import clear_registry, register_adapter_config
from custom_components.eufy_vacuum.jobs.active_job import (
    ActiveJobTracker,
    _normalize_path_block_action,
    _normalize_pause_timeout_minutes,
    _safe_float,
    _safe_int,
)


@pytest.fixture
def tracker() -> ActiveJobTracker:
    """An ActiveJobTracker whose manager is a mock — pure methods never touch it."""
    return ActiveJobTracker(MagicMock())


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (5, 5), ("3.9", 3), (None, 0), ("", 0), ("unknown", 0), ("unavailable", 0), ("x", 0),
])
def test_safe_int(value, expected):
    """[AJ-1]"""
    assert _safe_int(value) == expected


def test_safe_int_default():
    """[AJ-1]"""
    assert _safe_int(None, 7) == 7


@pytest.mark.parametrize("value,expected", [
    (3.5, 3.5), (4, 4.0), (None, 0.0), ("", 0.0), ("unavailable", 0.0),
])
def test_safe_float(value, expected):
    """[AJ-2]"""
    assert _safe_float(value) == pytest.approx(expected)


@pytest.mark.parametrize("value,expected", [
    ("pause_and_event", "pause_and_event"),
    ("cancel_and_event", "cancel_and_event"),
    ("event_only", "event_only"),
    ("garbage", "event_only"),
    (None, "event_only"),
])
def test_normalize_path_block_action(value, expected):
    """[AJ-3]"""
    assert _normalize_path_block_action(value) == expected


@pytest.mark.parametrize("value,expected", [(5, 5), (-3, 0), ("10", 10), (None, 0)])
def test_normalize_pause_timeout(value, expected):
    """[AJ-4]"""
    assert _normalize_pause_timeout_minutes(value) == expected


# ---------------------------------------------------------------------------
# _default_active_job_state
# ---------------------------------------------------------------------------

def test_default_active_job_state(tracker):
    """[AJ-5]"""
    state = tracker._default_active_job_state(vacuum_entity_id="vacuum.alfred", map_id=6)
    assert state["vacuum_entity_id"] == "vacuum.alfred"
    assert state["map_id"] == "6"  # coerced to str
    assert state["status"] == "idle"
    assert state["payload"] == {"map_id": "6", "rooms": []}
    assert state["completed_room_ids"] == []
    assert state["path_block_action"] == "event_only"


# ---------------------------------------------------------------------------
# _derive_active_job_current_room_id
# ---------------------------------------------------------------------------

def test_derive_current_room_first_uncompleted(tracker):
    """[AJ-6]"""
    job = {
        "completed_room_ids": [1],
        "resolved_rooms": [{"room_id": 1}, {"room_id": 2}, {"room_id": 3}],
    }
    assert tracker._derive_active_job_current_room_id(job) == 2


def test_derive_current_room_queue_fallback(tracker):
    """[AJ-7] no resolved rooms → uses queue_room_ids, skipping completed."""
    job = {"completed_room_ids": [4], "resolved_rooms": [], "queue_room_ids": [4, 5]}
    assert tracker._derive_active_job_current_room_id(job) == 5


def test_derive_current_room_all_done(tracker):
    """[AJ-8]"""
    job = {"completed_room_ids": [1, 2], "resolved_rooms": [{"room_id": 1}, {"room_id": 2}]}
    assert tracker._derive_active_job_current_room_id(job) is None


# ---------------------------------------------------------------------------
# _normalize_active_job
# ---------------------------------------------------------------------------

def test_normalize_fills_defaults(tracker):
    """[AJ-9]"""
    out = tracker._normalize_active_job({"path_block_action": "bogus", "pause_timeout_minutes": -5})
    assert out["queue_room_ids"] == []
    assert out["status"] == "idle"
    assert out["path_block_action"] == "event_only"
    assert out["pause_timeout_minutes"] == 0


def test_normalize_derives_current_room(tracker):
    """[AJ-10]"""
    out = tracker._normalize_active_job({
        "completed_room_ids": [1],
        "resolved_rooms": [{"room_id": 1}, {"room_id": 2}],
    })
    assert out["current_room_id"] == 2


def test_normalize_current_started_defaults_to_started(tracker):
    """[AJ-11]"""
    out = tracker._normalize_active_job({"started_at": "2026-01-01T09:00:00+00:00"})
    assert out["current_room_started_at"] == "2026-01-01T09:00:00+00:00"


def test_normalize_non_dict_input(tracker):
    """[AJ-12]"""
    out = tracker._normalize_active_job("not-a-dict")  # type: ignore[arg-type]
    assert out["status"] == "idle"
    assert out["resolved_rooms"] == []


# ---------------------------------------------------------------------------
# _compute_current_room_elapsed_minutes
# ---------------------------------------------------------------------------

def test_compute_elapsed_plain(tracker):
    """[AJ-13] 10 minutes elapsed, no pauses."""
    job = {"current_room_started_at": "2026-01-01T10:00:00+00:00", "status": "cleaning"}
    result = tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00")
    assert result == pytest.approx(10.0)


def test_compute_elapsed_subtracts_live_pause(tracker):
    """[AJ-14] paused 5 min ago while status==paused → 10 - 5 = 5."""
    job = {
        "current_room_started_at": "2026-01-01T10:00:00+00:00",
        "status": "paused",
        "paused_at": "2026-01-01T10:05:00+00:00",
    }
    result = tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="2026-01-01T10:10:00+00:00")
    assert result == pytest.approx(5.0)


def test_compute_elapsed_bad_timestamps(tracker):
    """[AJ-15]"""
    job = {"current_room_started_at": "", "status": "cleaning"}
    assert tracker._compute_current_room_elapsed_minutes(
        active_job=job, now="not-a-date") == 0.0


# ---------------------------------------------------------------------------
# _room_name_from_active_job
# ---------------------------------------------------------------------------

def test_room_name_resolved_match(tracker):
    """[AJ-16]"""
    job = {"resolved_rooms": [{"room_id": 2, "name": "Kitchen"}]}
    assert tracker._room_name_from_active_job(job, 2) == "Kitchen"


def test_room_name_queue_fallback(tracker):
    """[AJ-17]"""
    job = {"resolved_rooms": [], "queue_rooms": [{"room_id": 3, "slug": "bath"}]}
    assert tracker._room_name_from_active_job(job, 3) == "bath"


@pytest.mark.parametrize("room_id", [None, -1, 99])
def test_room_name_no_match(tracker, room_id):
    """[AJ-18]"""
    job = {"resolved_rooms": [{"room_id": 2, "name": "Kitchen"}]}
    assert tracker._room_name_from_active_job(job, room_id) is None


# ---------------------------------------------------------------------------
# _timing_completion_threshold_minutes
# ---------------------------------------------------------------------------

def test_timing_threshold_high_confidence(tracker):
    """[AJ-19] high confidence + many samples → minimal slack (0.75)."""
    room = {"minutes": 10.0, "confidence_score": 0.9, "sample_count": 5}
    assert tracker._timing_completion_threshold_minutes(room) == pytest.approx(10.75)


def test_timing_threshold_low_confidence_few_samples(tracker):
    """[AJ-20] low confidence + single sample → wider slack."""
    room = {"minutes": 10.0, "confidence_score": 0.3, "sample_count": 1}
    # overrun 0.22 → slack max(0.75, 2.2)=2.2; sample<=1 +1.0 → 3.2; cap 4.0
    assert tracker._timing_completion_threshold_minutes(room) == pytest.approx(13.2)


# ---------------------------------------------------------------------------
# detect_run_anomalies
# ---------------------------------------------------------------------------

def test_detect_run_anomalies_disabled_for_path_optimized_order():
    """A path-optimizing adapter can jump ahead of queue order without implying
    skipped rooms or a stall in the current room."""
    clear_registry()
    register_adapter_config("vacuum.alfred", {
        "adapter_id": "roborock",
        "source": "test",
        "capabilities": {"honors_clean_order": False},
    })
    manager = MagicMock()
    manager.data = {"active_jobs": {}}
    tracker = ActiveJobTracker(manager)
    active_job = {
        "status": "started",
        "queue_room_ids": [1, 2],
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Hall"}],
    }

    result = tracker.detect_run_anomalies(
        vacuum_entity_id="vacuum.alfred",
        map_id="6",
        active_job=active_job,
        raw_timeline=[
            {"room_id": 1, "minutes": 1.0, "confidence_score": 0.9, "sample_count": 3},
            {"room_id": 2, "minutes": 1.0, "confidence_score": 0.9, "sample_count": 3},
        ],
        current_room_id=2,
        current_room_elapsed_minutes=10.0,
        completed_room_ids=[],
        awaiting_bounds_exit=True,
    )

    assert result["stall_detected"] is False
    assert result["running_long"] is False
    assert result["skipped_room_ids"] == []
    manager.hass.bus.async_fire.assert_not_called()


def _order_honoring_tracker() -> ActiveJobTracker:
    """A tracker whose adapter honors clean order (so the running_long tier runs)."""
    clear_registry()
    register_adapter_config("vacuum.alfred", {
        "adapter_id": "eufy", "source": "test",
        "capabilities": {"honors_clean_order": True},
    })
    manager = MagicMock()
    manager.data = {"active_jobs": {}}
    return ActiveJobTracker(manager)


def test_running_long_suppressed_for_unlearned_room():
    """[AJ-24] An unlearned room (source='default', sample_count=0) uses the ~6-min
    default estimate, so running_long must NOT fire on it — otherwise every normal
    new-setup room reads 'may be stuck' (issue #40). elapsed 13 min would land in the
    ~1.5x band of the ~8-min unlearned threshold; the gate suppresses it."""
    tracker = _order_honoring_tracker()
    active_job = {"status": "started", "queue_room_ids": [1],
                  "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}], "counter_samples": []}
    result = tracker.detect_run_anomalies(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=active_job,
        raw_timeline=[{"room_id": 1, "minutes": 6.0, "confidence_score": 0.2,
                       "sample_count": 0, "source": "default"}],
        current_room_id=1,
        current_room_elapsed_minutes=13.0,
        completed_room_ids=[],
        awaiting_bounds_exit=False,  # isolate running_long from the bounds-gated stall
    )
    assert result["running_long"] is False
    assert result["stall_detected"] is False


def test_running_long_fires_for_learned_room():
    """[AJ-25] Control for AJ-24: a LEARNED room with the same overrun still fires
    running_long — the #40 gate only silences the unlearned case. Threshold 10.75;
    elapsed 17 sits in the 1.5x..2x band."""
    tracker = _order_honoring_tracker()
    active_job = {"status": "started", "queue_room_ids": [1],
                  "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}], "counter_samples": []}
    result = tracker.detect_run_anomalies(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=active_job,
        raw_timeline=[{"room_id": 1, "minutes": 10.0, "confidence_score": 0.9,
                       "sample_count": 5, "source": "learned"}],
        current_room_id=1,
        current_room_elapsed_minutes=17.0,
        completed_room_ids=[],
        awaiting_bounds_exit=False,
    )
    assert result["running_long"] is True


# ---------------------------------------------------------------------------
# record_counter_sample (counter-plateau capture buffer)
# ---------------------------------------------------------------------------

def _tracker_with_job(job: dict) -> ActiveJobTracker:
    mgr = MagicMock()
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": job}}}
    return ActiveJobTracker(mgr)


def test_record_counter_sample_buffers_last_seen():
    """record_counter_sample snapshots the last-seen cleaning_time / area / battery
    into the in-flight job's counter_samples (the input to segment_counters)."""
    job = {
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
        "last_battery_percent": 99,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    samples = job["counter_samples"]
    assert len(samples) == 1
    assert samples[0]["cleaning_time"] == 30
    assert samples[0]["cleaning_area"] == 1.0
    assert samples[0]["battery"] == 99


def test_record_counter_sample_skips_finalized_job():
    """A job with ended_at is no longer in-flight -> no sample appended."""
    job = {
        "started_at": "2026-01-01T09:00:00+00:00",
        "ended_at": "2026-01-01T09:30:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is False
    assert job.get("counter_samples", []) == []


# ---------------------------------------------------------------------------
# record_pose_sample (W5b external pose buffer for room attribution)
# ---------------------------------------------------------------------------

def _external_job() -> dict:
    return {"status": "external", "started_at": "2026-01-01T09:00:00+00:00"}


def test_record_pose_sample_buffers_external():
    job = _external_job()
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=[0.1, 0.2], cleaning_area=2.0,
    ) is True
    s = job["pose_samples"]
    assert len(s) == 1
    assert s[0]["current_room"] == 5 and s[0]["anchor"] == [0.1, 0.2] and s[0]["cleaning_area"] == 2.0


def test_record_pose_sample_records_none_current_room():
    """None current_room (docked / off-raster) is recorded, not dropped — the parked-dock
    exclusion depends on None runs existing."""
    job = _external_job()
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=None, anchor=None, cleaning_area=2.0,
    ) is True
    assert job["pose_samples"][0]["current_room"] is None


def test_record_pose_sample_skips_dispatched_run():
    """A dispatched run already knows its rooms -> external-only, no pose sample."""
    job = {"status": "started", "started_at": "2026-01-01T09:00:00+00:00"}
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=[0.1, 0.2], cleaning_area=2.0,
    ) is False
    assert job.get("pose_samples", []) == []


def test_record_pose_sample_skips_finalized():
    job = {"status": "external", "started_at": "2026-01-01T09:00:00+00:00",
           "ended_at": "2026-01-01T09:30:00+00:00"}
    tracker = _tracker_with_job(job)
    assert tracker.record_pose_sample(
        vacuum_entity_id="vacuum.alfred", map_id="6",
        current_room=5, anchor=None, cleaning_area=None,
    ) is False


def test_record_pose_sample_caps_buffer():
    from custom_components.eufy_vacuum.jobs.active_job import _MAX_POSE_SAMPLES
    job = _external_job()
    tracker = _tracker_with_job(job)
    for i in range(_MAX_POSE_SAMPLES + 25):
        tracker.record_pose_sample(
            vacuum_entity_id="vacuum.alfred", map_id="6",
            current_room=i, anchor=None, cleaning_area=None,
        )
    s = job["pose_samples"]
    assert len(s) == _MAX_POSE_SAMPLES
    assert s[-1]["current_room"] == _MAX_POSE_SAMPLES + 24  # del-oldest: newest survive


# ---------------------------------------------------------------------------
# External-run capture (W6.2): status="external" slot + setting-select snapshot
# ---------------------------------------------------------------------------

def test_start_external_capture_opens_external_slot():
    """start_external_capture seeds an in-flight slot with status='external'."""
    mgr = MagicMock()
    mgr.data = {}
    tracker = ActiveJobTracker(mgr)
    slot = tracker.start_external_capture(vacuum_entity_id="vacuum.alfred", map_id="6")
    assert slot["status"] == "external"
    assert slot["started_at"]
    assert mgr.data["active_jobs"]["vacuum.alfred"]["6"]["status"] == "external"


def test_snapshot_settings_selects_maps_and_skips(monkeypatch):
    """value_map normalizes the raw clean_mode string; unmapped selects keep their
    raw value; entries with no entity_id or an unavailable state are skipped."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "settings_selects": {
            "clean_mode": {
                "entity_id": "select.alfred_cleaning_mode",
                "value_map": {"vacuum and mop": "vacuum_mop"},
            },
            "fan_speed": {"entity_id": "select.alfred_suction_level", "value_map": None},
            "absent": {"entity_id": None, "value_map": None},
        }
    })
    states = {
        "select.alfred_cleaning_mode": MagicMock(state="Vacuum and mop"),
        "select.alfred_suction_level": MagicMock(state="Turbo"),
    }
    mgr = MagicMock()
    mgr.hass.states.get = lambda eid: states.get(eid)
    out = ActiveJobTracker(mgr)._snapshot_settings_selects("vacuum.alfred")
    assert out == {"clean_mode": "vacuum_mop", "fan_speed": "Turbo"}


def test_record_counter_sample_captures_settings_for_external(monkeypatch):
    """An external slot also buffers a deduped settings timeline; a repeat with the
    same settings does not append a second entry (one per flip)."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "settings_selects": {
            "clean_mode": {"entity_id": "select.alfred_cleaning_mode", "value_map": None},
        }
    })
    job = {
        "status": "external",
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
        "last_battery_percent": 99,
    }
    mgr = MagicMock()
    mgr.data = {"active_jobs": {"vacuum.alfred": {"6": job}}}
    mgr.hass.states.get = lambda eid: MagicMock(state="Vacuum")
    tracker = ActiveJobTracker(mgr)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    assert job["counter_samples"][0]["cleaning_time"] == 30
    assert job["settings_samples"] == [
        {"t": job["settings_samples"][0]["t"], "settings": {"clean_mode": "Vacuum"}}
    ]
    tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred")
    assert len(job["counter_samples"]) == 2        # counters always append
    assert len(job["settings_samples"]) == 1       # settings deduped (no flip)


def test_record_counter_sample_no_settings_for_internal():
    """Internal (status='started') jobs never buffer settings_samples."""
    job = {
        "status": "started",
        "started_at": "2026-01-01T09:00:00+00:00",
        "last_cleaning_time_seconds": 30,
        "last_cleaning_area_m2": 1.0,
    }
    tracker = _tracker_with_job(job)
    assert tracker.record_counter_sample(vacuum_entity_id="vacuum.alfred") is True
    assert job.get("settings_samples", []) == []


# ---------------------------------------------------------------------------
# _position_lock_reliable (capability-gated geometry — the adapter's call)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Live room rollover by counter-plateau (W5b)
# ---------------------------------------------------------------------------

def _csample(sec: int, ct: float, ca: float) -> dict:
    from datetime import datetime, timedelta
    t = datetime(2026, 1, 1, 9, 0, 0) + timedelta(seconds=sec)
    return {"t": t.isoformat(), "cleaning_time": ct, "cleaning_area": ca}


def _rollover_job(counter_samples: list[dict]) -> dict:
    return {
        "status": "started",
        "started_at": "2026-01-01T09:00:00",
        "current_room_id": 1,
        "current_room_started_at": "2026-01-01T09:00:00",
        "completed_room_ids": [],
        "completed_rooms": [],
        "queue_room_ids": [1, 2],
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Bath"}],
        "counter_samples": counter_samples,
    }


def test_live_rollover_by_counter_plateau():
    """A completed counter segment beyond recorded completions rolls the room live
    via the plateau path (ahead of the timing threshold), source=counter_plateau."""
    samples = [
        _csample(0, 0, 0), _csample(30, 30, 1), _csample(60, 60, 2),   # room 1
        _csample(400, 90, 4),                                          # room 2 started (gap > 90)
    ]
    job = _rollover_job(samples)
    tracker = _tracker_with_job(job)
    raw_timeline = [{"room_id": 1, "confidence_score": 0.5}, {"room_id": 2}]
    updated = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=job,
        raw_timeline=raw_timeline, current_room_id=1,
        current_room_elapsed_minutes=4.0, completed_room_ids=[],
    )
    assert updated["completed_room_ids"] == [1]
    assert updated["current_room_id"] == 2
    sources = [
        c.args[1].get("source")
        for c in tracker._manager.hass.bus.async_fire.call_args_list
        if len(c.args) >= 2 and isinstance(c.args[1], dict)
    ]
    assert "counter_plateau" in sources


def test_live_no_rollover_when_room_in_progress():
    """A single in-progress segment (no completed boundary) + sub-threshold elapsed
    → no rollover."""
    samples = [_csample(0, 0, 0), _csample(30, 30, 1), _csample(60, 60, 2)]  # room 1 only
    job = _rollover_job(samples)
    tracker = _tracker_with_job(job)
    raw_timeline = [
        {"room_id": 1, "minutes": 10.0, "confidence_score": 0.9, "sample_count": 5},
        {"room_id": 2},
    ]
    updated = tracker._maybe_roll_current_room_by_timing(
        vacuum_entity_id="vacuum.alfred", map_id="6", active_job=job,
        raw_timeline=raw_timeline, current_room_id=1,
        current_room_elapsed_minutes=1.0, completed_room_ids=[],
    )
    assert updated["completed_room_ids"] == []
    assert updated["current_room_id"] == 1


# ---------------------------------------------------------------------------
# _live_transition_config (live-rollover orchestration — adapter-override merge)
# ---------------------------------------------------------------------------

def test_live_transition_config_defaults_passthrough(tracker, monkeypatch):
    """[AJ-21] No adapter `live_transition` block → a *copy* of the defaults.

    The returned dict equals _LIVE_TRANSITION_DEFAULTS but must be a distinct
    object: mutating the return must not corrupt the shared module constant.
    """
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    from custom_components.eufy_vacuum.jobs.active_job import _LIVE_TRANSITION_DEFAULTS

    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {})
    cfg = tracker._live_transition_config("vacuum.alfred")
    assert cfg == _LIVE_TRANSITION_DEFAULTS
    assert cfg is not _LIVE_TRANSITION_DEFAULTS  # distinct object
    cfg["enabled"] = "tampered"
    assert _LIVE_TRANSITION_DEFAULTS["enabled"] is True  # constant untouched


def test_live_transition_config_full_override(tracker, monkeypatch):
    """[AJ-22] Adapter block overrides every key: bool-coerces enabled /
    native_transition_source and converts a list of rollover_kinds into a
    whitespace-stripped tuple."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj

    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "live_transition": {
            "enabled": False,
            "native_transition_source": True,
            "rollover_kinds": ["transit", " wash_plateau "],
        }
    })
    cfg = tracker._live_transition_config("vacuum.alfred")
    assert cfg == {
        "enabled": False,
        "native_transition_source": True,
        "rollover_kinds": ("transit", "wash_plateau"),
    }


def test_live_transition_config_blank_rollover_kinds_falls_back(tracker, monkeypatch):
    """[AJ-23] rollover_kinds that strip to all-empty → the after-clean empty
    guard keeps the default tuple; enabled / native_transition_source unspecified
    stay at their defaults."""
    from custom_components.eufy_vacuum.jobs import active_job as _aj
    from custom_components.eufy_vacuum.jobs.active_job import _LIVE_TRANSITION_DEFAULTS

    monkeypatch.setattr(_aj, "_get_adapter_config", lambda v: {
        "live_transition": {"rollover_kinds": ["", "   "]}
    })
    cfg = tracker._live_transition_config("vacuum.alfred")
    assert cfg["rollover_kinds"] == _LIVE_TRANSITION_DEFAULTS["rollover_kinds"]
    assert cfg["enabled"] == _LIVE_TRANSITION_DEFAULTS["enabled"]
    assert cfg["native_transition_source"] == _LIVE_TRANSITION_DEFAULTS["native_transition_source"]


# ---------------------------------------------------------------------------
# poll_stranded_started_job (the FN-1 reaper detection + grace)
# ---------------------------------------------------------------------------

_EUFY_CFG = {
    "adapter_id": "eufy", "source": "test", "brand": "eufy",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_cleaning_target": "sensor.alfred_active_cleaning_target",
    },
    "completion": {
        "task_status_value": "completed",
        "secondary_clear_sentinels": ["", "unknown", "unavailable", "none", "null"],
    },
    "external_mid_run_statuses": ["Returning to Charge", "Washing Mop"],
}

_ROBO_CFG = {
    "adapter_id": "roborock", "source": "test", "brand": "roborock",
    "entities": {
        "task_status": "sensor.ivy_status",
        "dock_status": "sensor.ivy_dock_status",
        "active_cleaning_target": "sensor.ivy_current_room",
        "job_active": "binary_sensor.ivy_job_active",
    },
    "completion": {"task_status_value": "charging", "require_job_active_clear": True},
}


def _poll_tracker(cfg, vac, states, active_job) -> ActiveJobTracker:
    clear_registry()
    register_adapter_config(vac, cfg)
    manager = MagicMock()
    manager.data = {"active_jobs": {vac: {"main": active_job}}}
    manager.hass.states.get.side_effect = (
        lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    )
    return ActiveJobTracker(manager)


def _stamp(tracker, vac):
    return tracker._manager.data["active_jobs"][vac]["main"].get("stranded_since")


def test_poll_stranded_eufy_stamps_then_reaps():
    """[AJ-26] Eufy: docked, target cleared, task_status never 'completed', armed —
    the first tick stamps stranded_since; a report comes only once past the grace."""
    vac = "vacuum.alfred"
    tracker = _poll_tracker(_EUFY_CFG, vac, {
        vac: "docked",
        "sensor.alfred_task_status": "charging",          # NOT 'completed'
        "sensor.alfred_active_cleaning_target": "none",   # cleared sentinel
    }, {"status": "started", "has_observed_active_lifecycle": True, "job_id": "j1"})

    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) == "2026-07-11T10:00:00Z"
    # within the 5-min grace → still no report
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:04:00Z") is None
    report = tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                               now="2026-07-11T10:06:00Z")
    assert report is not None
    assert report["cancel_reason"] == "stranded_no_completion"
    assert report["stranded_since"] == "2026-07-11T10:00:00Z"
    assert report["job_id"] == "j1"


def test_poll_not_stranded_when_completed():
    """[AJ-27] task_status == the brand's completion value → normal gate owns it."""
    vac = "vacuum.alfred"
    tracker = _poll_tracker(_EUFY_CFG, vac, {
        vac: "docked",
        "sensor.alfred_task_status": "completed",
        "sensor.alfred_active_cleaning_target": "none",
    }, {"status": "started", "has_observed_active_lifecycle": True})
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) is None


def test_poll_clears_stamp_on_resume():
    """[AJ-28] a stamped strand that then resumes (vacuum cleaning) drops the stamp."""
    vac = "vacuum.alfred"
    states = {
        vac: "docked",
        "sensor.alfred_task_status": "charging",
        "sensor.alfred_active_cleaning_target": "none",
    }
    tracker = _poll_tracker(_EUFY_CFG, vac, states,
                            {"status": "started", "has_observed_active_lifecycle": True})
    tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                      now="2026-07-11T10:00:00Z")
    assert _stamp(tracker, vac) == "2026-07-11T10:00:00Z"
    # robot resumes cleaning → no longer docked → strand clears
    states[vac] = "cleaning"
    states["sensor.alfred_task_status"] = "cleaning"
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:01:00Z") is None
    assert _stamp(tracker, vac) is None


def test_poll_stranded_roborock_reaps():
    """[AJ-29] Roborock: docked, status 'idle' (not the 'charging' completion value),
    job_active off, require_job_active_clear makes the secondary True → reaps."""
    vac = "vacuum.ivy"
    tracker = _poll_tracker(_ROBO_CFG, vac, {
        vac: "docked",
        "sensor.ivy_status": "idle",
        "sensor.ivy_current_room": "Kitchen",   # reverts to a room name, never a sentinel
        "binary_sensor.ivy_job_active": "off",
    }, {"status": "started", "has_observed_active_lifecycle": True, "job_id": "r1"})

    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    report = tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                               now="2026-07-11T10:06:00Z")
    assert report is not None and report["cancel_reason"] == "stranded_no_completion"


def test_poll_not_stranded_roborock_recharge():
    """[AJ-30] Roborock mid-job recharge keeps job_active ON → not stranded."""
    vac = "vacuum.ivy"
    tracker = _poll_tracker(_ROBO_CFG, vac, {
        vac: "docked",
        "sensor.ivy_status": "idle",
        "sensor.ivy_current_room": "Kitchen",
        "binary_sensor.ivy_job_active": "on",    # still cleaning (recharge)
    }, {"status": "started", "has_observed_active_lifecycle": True})
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) is None


def test_poll_ignores_paused_job():
    """[AJ-31] a paused job is the pause-timeout reaper's; this never stamps it."""
    vac = "vacuum.alfred"
    tracker = _poll_tracker(_EUFY_CFG, vac, {
        vac: "docked",
        "sensor.alfred_task_status": "charging",
        "sensor.alfred_active_cleaning_target": "none",
    }, {"status": "paused", "has_observed_active_lifecycle": True})
    assert tracker.poll_stranded_started_job(vacuum_entity_id=vac, map_id="main",
                                             now="2026-07-11T10:00:00Z") is None
    assert _stamp(tracker, vac) is None
