"""Unit tests for learning/job_finalizer.py — pure-function helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.learning.job_finalizer import (
    LearningJobFinalizer,
    _apply_water_actuals,
    _commanded_break_phase_seconds,
    _compute_total_error_seconds,
    _duration_state_to_seconds,
    _parse_iso_to_utc,
)


@pytest.fixture
def finalizer(tmp_path):
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return LearningJobFinalizer(hass)


# ---------------------------------------------------------------------------
# _parse_iso_to_utc
# ---------------------------------------------------------------------------

def test_parse_iso_utc_zulu():
    dt = _parse_iso_to_utc("2026-01-01T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.tzinfo is not None


def test_parse_iso_utc_offset():
    dt = _parse_iso_to_utc("2026-01-01T10:00:00+00:00")
    assert dt is not None
    assert dt.minute == 0


def test_parse_iso_utc_none_returns_none():
    assert _parse_iso_to_utc(None) is None


def test_parse_iso_utc_empty_string_returns_none():
    assert _parse_iso_to_utc("") is None


def test_parse_iso_utc_non_string_returns_none():
    assert _parse_iso_to_utc(12345) is None


def test_parse_iso_utc_garbage_returns_none():
    assert _parse_iso_to_utc("not-a-date") is None


# ---------------------------------------------------------------------------
# _duration_state_to_seconds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,unit,expected", [
    ("300", "s", 300),
    ("6.15", "min", 369),
    ("0.1", "h", 360),
    ("1500", "ms", 2),
])
def test_duration_state_to_seconds(raw, unit, expected):
    assert _duration_state_to_seconds(raw, unit) == expected


def test_duration_state_to_seconds_bad_value_default():
    assert _duration_state_to_seconds("unavailable", "min", None) is None


# ---------------------------------------------------------------------------
# _compute_total_error_seconds
# ---------------------------------------------------------------------------

def test_error_seconds_no_latch():
    assert _compute_total_error_seconds(None, job_ended_at=None) == 0


def test_error_seconds_empty_errors():
    latch = {"errors": []}
    assert _compute_total_error_seconds(latch, job_ended_at=None) == 0


def test_error_seconds_single_resolved_interval():
    latch = {
        "errors": [
            {
                "captured_at": "2026-01-01T10:00:00Z",
                "recovered_at": "2026-01-01T10:00:30Z",
            }
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 30


def test_error_seconds_unresolved_bounded_by_job_end():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z"}  # no recovered_at
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:01:00Z")
    assert result == 60


def test_error_seconds_unresolved_bounded_by_next_entry():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z"},             # no recovered_at
            {"captured_at": "2026-01-01T10:00:20Z", "recovered_at": "2026-01-01T10:00:40Z"},
        ]
    }
    # First entry ends at second entry's captured_at (T+20s), second entry is 20s
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 40  # 20 + 20


def test_error_seconds_two_separate_intervals():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:10Z"},
            {"captured_at": "2026-01-01T10:01:00Z", "recovered_at": "2026-01-01T10:01:20Z"},
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 30  # 10 + 20


def test_error_seconds_merges_overlapping_intervals():
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:30Z"},
            {"captured_at": "2026-01-01T10:00:20Z", "recovered_at": "2026-01-01T10:00:40Z"},
        ]
    }
    # Merged: 00:00 → 00:40 = 40s
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 40


def test_error_seconds_zero_duration_interval_skipped():
    """end <= start intervals are dropped."""
    latch = {
        "errors": [
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:00Z"},
        ]
    }
    assert _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z") == 0


def test_error_seconds_non_dict_latch():
    assert _compute_total_error_seconds("not_a_dict", job_ended_at=None) == 0


def test_error_seconds_malformed_entry_skipped():
    latch = {
        "errors": [
            "not a dict",
            {"captured_at": "2026-01-01T10:00:00Z", "recovered_at": "2026-01-01T10:00:05Z"},
        ]
    }
    result = _compute_total_error_seconds(latch, job_ended_at="2026-01-01T10:05:00Z")
    assert result == 5


# ---------------------------------------------------------------------------
# _apply_water_actuals
# ---------------------------------------------------------------------------

def _job_with_water(**overrides) -> dict:
    water = {
        "station_clean_water_percent": 80.0,
        "actual_end_station_clean_water_percent": None,
        "dock_clean_tank_capacity_ml": 3000,
        "dock_wash_overhead_ml_per_cycle": 50.0,
        "wash_cycle_count": 2,
        "estimated_total_dock_clean_water_used_ml": 450.0,
    }
    water.update(overrides)
    return {"water": water}


def test_apply_water_actuals_computes_total():
    job = _job_with_water()
    # start=80%, end=65%, capacity=3000ml → used = (80-65)/100 * 3000 = 450ml
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    water = job["water"]
    assert water["actual_dock_water_used_ml"] == pytest.approx(450.0)
    assert water["actual_end_station_clean_water_percent"] == 65.0
    assert water["actual_mop_wash_count"] == 2


def test_apply_water_actuals_splits_wash_overhead():
    job = _job_with_water()
    # 2 washes * 50ml/wash = 100ml overhead → floor = 450 - 100 = 350ml
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    water = job["water"]
    assert water["actual_mop_wash_water_ml"] == pytest.approx(100.0)
    assert water["actual_floor_water_ml"] == pytest.approx(350.0)


def test_apply_water_actuals_none_end_percent_nulls_fields():
    job = _job_with_water()
    _apply_water_actuals(completed_job=job, end_percent=None, observed_mop_wash_count=0)
    water = job["water"]
    assert water["actual_dock_water_used_ml"] is None
    assert water["actual_floor_water_ml"] is None


def test_apply_water_actuals_unexpected_wash_cycles():
    job = _job_with_water()
    # wash_cycle_count=2 in water, but observed=3 → unexpected
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=3)
    assert job["water"]["unexpected_wash_cycles"] is True


def test_apply_water_actuals_expected_wash_cycles():
    job = _job_with_water()
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    assert job["water"]["unexpected_wash_cycles"] is False


def test_apply_water_actuals_no_water_section_noop():
    """No water key → function returns without error."""
    job = {"outcome": {"status": "completed"}}
    _apply_water_actuals(completed_job=job, end_percent=60.0, observed_mop_wash_count=0)
    # No water key added
    assert "water" not in job


def test_apply_water_actuals_delta_computed():
    """actual_vs_estimated_delta_ml = actual_total - estimated."""
    job = _job_with_water()  # estimated = 450ml
    _apply_water_actuals(completed_job=job, end_percent=65.0, observed_mop_wash_count=2)
    # actual=450ml, estimated=450ml → delta=0
    assert job["water"]["actual_vs_estimated_delta_ml"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _apply_snapshot_estimates_to_completed_job — start-of-run estimate enrichment
# ---------------------------------------------------------------------------

def test_apply_snapshot_estimates_matches_by_id_and_slug(finalizer):
    """[JF-1] resolved rooms gain estimate fields from the snapshot timeline,
    matched first by room_id then by slug; unmatched rooms pass through."""
    snapshot = {"planned_job_estimate": {"room_timeline": [
        {"room_id": 1, "minutes": 5.0, "battery": 8.0,
         "confidence_score": 0.9, "confidence_label": "high", "source": "learned"},
        {"slug": "bath", "minutes": 3.0, "battery": 4.0},
    ]}}
    completed_job = {"resolved_rooms": [
        {"room_id": 1, "name": "Kitchen"},          # matches by id
        {"room_id": 7, "slug": "bath"},             # id miss → slug match
        {"room_id": 9, "name": "Hall"},             # no match → passthrough
    ]}
    finalizer._apply_snapshot_estimates_to_completed_job(
        completed_job=completed_job, snapshot=snapshot)
    rooms = {r.get("room_id"): r for r in completed_job["resolved_rooms"]}
    assert rooms[1]["estimated_minutes"] == 5.0
    assert rooms[1]["estimate_confidence_label"] == "high"
    assert rooms[7]["estimated_minutes"] == 3.0
    assert "estimated_minutes" not in rooms[9]


def test_apply_snapshot_estimates_guards(finalizer):
    """[JF-2] missing/empty snapshot or timeline → completed_job untouched."""
    job = {"resolved_rooms": [{"room_id": 1}]}
    finalizer._apply_snapshot_estimates_to_completed_job(completed_job=job, snapshot=None)
    finalizer._apply_snapshot_estimates_to_completed_job(
        completed_job=job, snapshot={"planned_job_estimate": {"room_timeline": []}})
    assert "estimated_minutes" not in job["resolved_rooms"][0]


# ---------------------------------------------------------------------------
# _detect_cancel_likely_run — learning-estimate path (1195-1218)
# ---------------------------------------------------------------------------

_VAC = "vacuum.alfred"


def _cancel_state(returning_offset_min, paused_secs=0.0):
    start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ret = start + timedelta(minutes=returning_offset_min)
    return {
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}],
        "paused_duration_seconds": paused_secs,
        "state_transitions": [
            {"entity_id": "sensor.alfred_task_status",
             "from_state": "cleaning", "to_state": "returning",
             "changed_at": ret.isoformat()},
        ],
    }, start.isoformat(), ret.isoformat()


def test_detect_cancel_short_run_is_likely(finalizer):
    """[JF-3] past the floor (2 min cleaned), a run far under the learned estimate
    is flagged early_return_likely_cancelled."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"task_status": "sensor.alfred_task_status"},
    })
    state, started, ended = _cancel_state(returning_offset_min=2)
    learning = MagicMock()
    learning.estimate_from_manager.return_value = {"room_timeline": [{"minutes": 10.0}]}
    manager = MagicMock()
    finalizer._estimate_fn = learning.estimate_from_manager

    out = finalizer._detect_cancel_likely_run(
        manager=manager, vacuum_entity_id=_VAC, map_id="6",
        battery_start=90, started_at=started, ended_at=ended,
        active_job_state=state)
    # 2 min actual >= 1.5 floor, but << 10 min estimate (short_threshold 4.0)
    assert out["cancel_likely"] is True
    assert out["reason"] == "early_return_likely_cancelled"


def _run_cancel(finalizer, vocab, from_state, to_state):
    """Run _detect_cancel_likely_run for one task_status transition under the
    given adapter vocabulary. Returns the verdict dict."""
    start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ret = start + timedelta(minutes=2)
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"task_status": "sensor.alfred_task_status"},
        "vocabulary": vocab,
    })
    state = {
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}],
        "paused_duration_seconds": 0.0,
        "state_transitions": [
            {"entity_id": "sensor.alfred_task_status",
             "from_state": from_state, "to_state": to_state,
             "changed_at": ret.isoformat()},
        ],
    }
    learning = MagicMock()
    learning.estimate_from_manager.return_value = {"room_timeline": [{"minutes": 10.0}]}
    manager = MagicMock()
    finalizer._estimate_fn = learning.estimate_from_manager
    return finalizer._detect_cancel_likely_run(
        manager=manager, vacuum_entity_id=_VAC, map_id="6",
        battery_start=90, started_at=start.isoformat(), ended_at=ret.isoformat(),
        active_job_state=state)


def test_detect_cancel_active_list_and_returning_home(finalizer):
    """[JF-Roborock] `active` as a LIST + return state `returning_home`: a
    segment_cleaning -> returning_home short run is flagged (the per-room cancel
    case the single-string `active` would have missed)."""
    out = _run_cancel(
        finalizer,
        {"cancel_detection_states": {
            "active": ["cleaning", "segment_cleaning"],
            "returning": "returning_home", "paused": "paused"}},
        from_state="segment_cleaning", to_state="returning_home")
    assert out["cancel_likely"] is True
    assert out["reason"] == "early_return_likely_cancelled"


def test_detect_cancel_defaults_miss_returning_home(finalizer):
    """Regression guard: with the framework DEFAULTS (active='cleaning',
    returning='returning'), a Roborock-style segment_cleaning -> returning_home
    transition is NOT matched — which is exactly why the adapter must declare
    cancel_detection_states. Without it, a cancelled Roborock run silently
    pollutes learning estimates."""
    out = _run_cancel(
        finalizer, {},  # no cancel_detection_states -> framework defaults
        from_state="segment_cleaning", to_state="returning_home")
    assert out["cancel_likely"] is False
    assert out["reason"] == "no_cancel_like_transition"


def test_detect_cancel_estimate_error_then_long_enough(finalizer):
    """[JF-4] when the learning estimate raises, expected falls to 0 → a 1.0 min
    floor; a 2-min run clears it → duration_not_short (not a cancel)."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"task_status": "sensor.alfred_task_status"},
    })
    state, started, ended = _cancel_state(returning_offset_min=2)
    learning = MagicMock()
    learning.estimate_from_manager.side_effect = RuntimeError("boom")
    manager = MagicMock()
    finalizer._estimate_fn = learning.estimate_from_manager

    out = finalizer._detect_cancel_likely_run(
        manager=manager, vacuum_entity_id=_VAC, map_id="6",
        battery_start=90, started_at=started, ended_at=ended,
        active_job_state=state)
    assert out["cancel_likely"] is False
    assert out["reason"] == "duration_not_short"


# ---------------------------------------------------------------------------
# _collect_finalization_inputs — outcome_status classification
# A mislabeled outcome silently poisons the learned ETA priors (a cancelled or
# interrupted run graduating into the baselines as a real, complete clean).
# ---------------------------------------------------------------------------

def _inputs_manager():
    """Minimal manager mock: the queue/payload/active-job reads return empty, so
    only the outcome classification path of _collect_finalization_inputs runs."""
    m = MagicMock()
    m.get_queue_state.return_value = {}
    m.get_payload_state.return_value = {}
    m.get_active_job.return_value = {}
    return m


def test_collect_inputs_interrupted_outcome(finalizer):
    """A forced 'interrupted' lifecycle classifies the run as outcome_status
    'interrupted' (the `elif was_interrupted` arm), not the default 'completed' —
    and skips the cancel-likely probe. Misclassifying it as completed would feed a
    truncated runtime into the timing learner."""
    inputs = finalizer._collect_finalization_inputs(
        manager=_inputs_manager(),
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=80,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state="interrupted",
        forced_lifecycle_message="stopped mid-run",
    )
    assert inputs["outcome_status"] == "interrupted"
    assert inputs["was_interrupted"] is True
    assert inputs["was_cancelled"] is False


def test_collect_inputs_job_id_falls_back_to_active_job_not_a_timestamp(finalizer):
    """[Wave 0] The record's job_id must come from the ACTIVE JOB when the live snapshot
    carries none — not from a synthesised timestamp.

    The fallback is f"job_{now():%Y-%m-%dT%H-%M-%S}", whose 1-second resolution can COLLIDE:
    two jobs finalized in the same second would share a record id. The record id is the only
    handle anything downstream has on a job, and exactly-once finalization will key on it,
    so a synthesised id must be a last resort rather than a second choice.
    """
    m = _inputs_manager()
    m.get_active_job.return_value = {"job_id": "job_from_active"}
    inputs = finalizer._collect_finalization_inputs(
        manager=m,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=80,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert inputs["job_id"] == "job_from_active"


def test_collect_inputs_job_id_synthesised_only_as_last_resort(finalizer):
    """[Wave 0] With neither a snapshot nor an active-job id, the timestamp fallback still
    applies (and logs a warning) — the behaviour is preserved, just demoted."""
    inputs = finalizer._collect_finalization_inputs(
        manager=_inputs_manager(),
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=80,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert str(inputs["job_id"]).startswith("job_")


def test_collect_inputs_cancel_likely_marks_cancelled(finalizer, monkeypatch):
    """When the lifecycle says nothing special (would default to 'completed') but the
    cancel-likely detector fires, the run is reclassified 'cancelled' + lifecycle_name
    'cancel_likely' (the consumption arm). The detector itself is tested separately
    (the _detect_cancel_likely_run tests above); here it is stubbed so the test locks
    that its verdict actually FLIPS the outcome — otherwise a manually-cancelled early
    return would graduate into the learned baselines as a real, complete clean."""
    monkeypatch.setattr(
        finalizer, "_detect_cancel_likely_run",
        lambda **kw: {"cancel_likely": True, "message": "early return looks manual"},
    )
    inputs = finalizer._collect_finalization_inputs(
        manager=_inputs_manager(),
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=80,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:02:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert inputs["outcome_status"] == "cancelled"
    assert inputs["was_cancelled"] is True
    assert inputs["lifecycle_name"] == "cancel_likely"
    assert inputs["cancel_detection"]["cancel_likely"] is True


# ---------------------------------------------------------------------------
# Commit-point ordering — cumulative side effects must not run before the
# durable record exists. Wave 2 of the exactly-once finalization work.
# ---------------------------------------------------------------------------

def _finalizer_with_sink(tmp_path, pushes, *, save_raises=False):
    """A finalizer wired to a recording battery sink, optionally with a failing store."""
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)

    def _sink(*, vacuum_entity_id, metrics, job_id):
        pushes.append(job_id)

    fin = LearningJobFinalizer(hass, battery_sink=_sink)

    # The store is stubbed either way: this pair tests ORDERING around the commit point,
    # not serialization. (The hass MagicMock leaks into the payload, so a real save would
    # fail on JSON encoding for reasons unrelated to what is under test.)
    if save_raises:
        def _save(**kwargs):
            raise OSError("disk full")
    else:
        def _save(**kwargs):
            return "/tmp/job.json"
    fin.store.save_completed_job = _save
    return fin


def _finalize(fin, manager):
    inputs = fin._collect_finalization_inputs(
        manager=manager,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    return fin.finalize_from_inputs(
        inputs=inputs,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90, battery_end=60,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        rebuild_stats=False,
    )


def test_battery_push_does_not_happen_when_the_record_fails_to_save(tmp_path):
    """[JF-commit] A failed save must leave NO cumulative side effect behind.

    Battery aggregates are an incremental store outside rebuild_all, so an aggregate
    counting a run whose record never landed is unrepairable — it cannot be reconciled
    against jobs/ because there is nothing there to reconcile against. The push therefore
    waits for save_completed_job to succeed.
    """
    pushes: list[str] = []
    fin = _finalizer_with_sink(tmp_path, pushes, save_raises=True)

    with pytest.raises(OSError):
        _finalize(fin, _inputs_manager())

    assert pushes == [], "a battery aggregate was recorded for a run with no record"


# KNOWN GAP (pre-existing, not introduced by the commit-point change): the SUCCESSFUL
# battery push is not covered. `battery_sink` appears in no test in this repo, and driving
# it here needs realistic battery inputs — with the MagicMock manager used above,
# compute_job_battery_metrics raises and its `except` swallows the failure, so the push is
# skipped for a reason unrelated to ordering.
#
# Consequence to be honest about: the test above would still pass if someone DELETED the
# push entirely rather than deferring it. Closing this needs a fixture with real
# battery_start/battery_end/duration/resolved_rooms — worth doing when the battery
# subsystem is next touched, and tracked as a coverage gap rather than silently ignored.


def test_error_latch_is_not_cleared_when_the_record_fails_to_save(tmp_path):
    """[JF-commit-2] Wave 2b. A failed save must leave the error latch INTACT.

    The old harvest read-and-cleared in one call, before the record was built. A save that
    raised afterwards destroyed the run's error history permanently — and the retry then
    recorded had_errors=False, because the latch was already gone. Peek/commit defers the
    clear past save_completed_job.
    """
    commits: list[str] = []
    peeked = {"first_seen_at": "t0", "error_count": 1, "errors": [{"captured_at": "t0"}]}

    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    fin = LearningJobFinalizer(
        hass,
        error_source=lambda vac, jid: dict(peeked),
        error_commit=lambda vac, p: commits.append(vac) or True,
    )

    def _boom(**kwargs):
        raise OSError("disk full")
    fin.store.save_completed_job = _boom

    with pytest.raises(OSError):
        _finalize(fin, _inputs_manager())

    assert commits == [], "the error latch was cleared for a run with no record"


def test_error_latch_is_cleared_after_a_successful_save(tmp_path):
    """[JF-commit-2] The inverse: the commit must still happen on the happy path, or the
    latch would leak into the next run. Without this the test above would pass on a change
    that simply never committed."""
    commits: list[str] = []
    peeked = {"first_seen_at": "t0", "error_count": 1, "errors": [{"captured_at": "t0"}]}

    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    fin = LearningJobFinalizer(
        hass,
        error_source=lambda vac, jid: dict(peeked),
        error_commit=lambda vac, p: commits.append(vac) or True,
    )
    fin.store.save_completed_job = lambda **kwargs: "/tmp/job.json"

    _finalize(fin, _inputs_manager())

    assert commits == ["vacuum.fin_test"], "the latch was never cleared after a good save"


# ---------------------------------------------------------------------------
# RP-013f — a stepped run's cleaning_time_seconds is the WHOLE run, not just
# its last dispatched phase (REC-A), and the wall-clock fallback subtracts
# commanded break-phase durations the same way it already subtracts paused
# and mid-job recharge seconds (REC-B).
# ---------------------------------------------------------------------------

def _room_timing(room_id: int, seconds: int) -> dict:
    return {"room_id": room_id, "cleaning_seconds": seconds, "area_m2": 1.0}


def test_commanded_break_phase_seconds_sums_only_break_phases():
    """_commanded_break_phase_seconds: a room phase contributes nothing even
    though it also carries _timing_end_t; only charge_wait/wait phases count,
    each phase's span bounded by the PREVIOUS phase's own end."""
    phases = [
        {"phase_type": "room_group", "_timing_end_t": "2026-01-01T00:05:00+00:00"},
        {"phase_type": "charge_wait", "_timing_end_t": "2026-01-01T00:15:00+00:00"},
        {"phase_type": "room_group", "_timing_end_t": "2026-01-01T00:20:00+00:00"},
    ]
    # break phase spans 00:05:00 -> 00:15:00 = 600s; the room phases contribute 0.
    assert _commanded_break_phase_seconds(phases, "2026-01-01T00:00:00+00:00") == 600


def test_commanded_break_phase_seconds_leading_break_uses_run_start():
    """A break phase with nothing before it spans from the run's own started_at,
    not from an absent previous phase."""
    phases = [{"phase_type": "wait", "_timing_end_t": "2026-01-01T00:10:00+00:00"}]
    assert _commanded_break_phase_seconds(phases, "2026-01-01T00:00:00+00:00") == 600


def test_commanded_break_phase_seconds_no_phases_is_zero():
    assert _commanded_break_phase_seconds(None, "2026-01-01T00:00:00+00:00") == 0
    assert _commanded_break_phase_seconds([], "2026-01-01T00:00:00+00:00") == 0


def test_collect_inputs_stepped_job_sums_room_and_zone_phases_not_break(finalizer):
    """REC-A: a stepped run's cleaning_time_seconds is the SUM of its phases'
    own captured contributions (room_timing cleaning_seconds + zone_timing
    wall_seconds) — never the device's last-seen counter, which only ever
    reflects the FINAL dispatched phase. Break phases contribute zero."""
    m = _inputs_manager()
    m.get_active_job.return_value = {
        "last_cleaning_time_seconds": 302,  # the clobbered device counter — must be ignored
        "phases": [
            {"phase_type": "room_group", "room_timing": [_room_timing(4, 255)]},
            {"phase_type": "charge_wait", "room_timing": []},
            {"phase_type": "room_group", "room_timing": [_room_timing(5, 302)]},
            {"phase_type": "zone", "room_timing": [], "zone_timing": {"wall_seconds": 90}},
        ],
    }
    inputs = finalizer._collect_finalization_inputs(
        manager=m,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert inputs["cleaning_time_seconds"] == 255 + 302 + 90


def test_collect_inputs_stepped_group_phase_multi_room_sums_all_entries(finalizer):
    """Compose-safe with RP-013b: a group phase's room_timing can carry more
    than one entry (one per member, after RP-013b's allocated split) — all of
    them must be summed, not just the first."""
    m = _inputs_manager()
    m.get_active_job.return_value = {
        "phases": [
            {"phase_type": "room_group", "room_timing": [
                _room_timing(4, 100), _room_timing(5, 100), _room_timing(6, 100),
            ]},
        ],
    }
    inputs = finalizer._collect_finalization_inputs(
        manager=m,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert inputs["cleaning_time_seconds"] == 300


def test_collect_inputs_atomic_job_keeps_device_counter_unchanged(finalizer):
    """An atomic job (no 'phases' key at all) is untouched by RP-013f — one
    phase, one counter read, nothing to sum."""
    m = _inputs_manager()
    m.get_active_job.return_value = {"last_cleaning_time_seconds": 480}
    inputs = finalizer._collect_finalization_inputs(
        manager=m,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert inputs["cleaning_time_seconds"] == 480


def test_wall_clock_fallback_subtracts_commanded_break_phases(finalizer):
    """REC-B: with the device sensor unavailable AND the phases carrying no
    captured room_timing/zone_timing at all (a stepped run that captured
    NOTHING — REC-A's phase-sum correctly declines to trust a fabricated 0
    here and falls through), the wall-clock fallback must exclude the
    commanded break phase's span the same way it already excludes
    paused_duration_seconds and recharge_seconds_accumulated — otherwise the
    hold counts as cleaning time and inflates the derived total."""
    finalizer.hass.states.get.return_value = None  # sensor unavailable -> forces the fallback
    m = _inputs_manager()
    m.get_active_job.return_value = {
        # no last_cleaning_time_seconds -> None -> sensor path -> still None
        # (mocked unavailable) -> wall-clock fallback.
        "started_at": "2026-01-01T00:00:00+00:00",
        "paused_duration_seconds": 0,
        "recharge_seconds_accumulated": 0,
        # phases present but none captured anything -> REC-A's phase-sum
        # yields None (not a fabricated 0), so this correctly falls through
        # to the cascade below rather than short-circuiting it.
        "phases": [
            {"phase_type": "room_group", "_timing_end_t": "2026-01-01T00:05:00+00:00"},
            {"phase_type": "charge_wait", "_timing_end_t": "2026-01-01T00:15:00+00:00"},
            {"phase_type": "room_group", "_timing_end_t": "2026-01-01T00:20:00+00:00"},
        ],
    }
    inputs = finalizer._collect_finalization_inputs(
        manager=m,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    # wall = 1200s (20 min); commanded break = 600s (00:05 -> 00:15) subtracted
    # the same way paused/recharge already are -> 600s left, not 1200.
    assert inputs["cleaning_time_seconds"] == 600


def test_wall_clock_fallback_atomic_job_subtracts_commanded_breaks(finalizer):
    """REC-B's real reachable case: an ATOMIC job (no phases) whose sensor is
    unavailable still falls back to wall-clock, and the fallback itself must
    never fabricate a break-phase subtraction it has no phases to compute —
    confirms the zero-phases path is a true no-op, matching the paused/
    recharge-only arithmetic it always had."""
    finalizer.hass.states.get.return_value = None
    m = _inputs_manager()
    m.get_active_job.return_value = {
        "started_at": "2026-01-01T00:00:00+00:00",
        "paused_duration_seconds": 60,
        "recharge_seconds_accumulated": 30,
        # no "phases" key -> atomic job
    }
    inputs = finalizer._collect_finalization_inputs(
        manager=m,
        vacuum_entity_id="vacuum.fin_test", map_id="1",
        battery_start=90,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:20:00+00:00",
        forced_outcome_status=None,
        forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    # wall = 1200s; paused 60 + recharge 30 = 90; no phases -> no break subtraction.
    assert inputs["cleaning_time_seconds"] == 1200 - 90


# ---------------------------------------------------------------------------
# RP-013c — missed rooms, completed evidence, and the overlap-only clear
# ---------------------------------------------------------------------------

_VAC_13C = "vacuum.alfred"
_MAP_13C = "12"


def _cancelled(queued, timings=None):
    return {
        "job_id": "job_13c",
        "outcome": {"status": "cancelled"},
        "queue": {"queue_room_ids": list(queued)},
        "resolved_rooms": [{"room_id": r, "name": f"Room {r}"} for r in queued],
        "job": {"room_timings": list(timings or [])},
    }


def _write(fin, completed_job, active_job_state):
    return fin._write_incomplete_run_log(
        vacuum_entity_id=_VAC_13C, map_id=_MAP_13C,
        completed_job=completed_job, active_job_state=active_job_state,
        ended_at="2026-08-02T00:30:00Z",
    )


def test_missed_consumes_cumulative_evidence(finalizer):
    """[JF-13c] phase 1's rooms are not missed just because the advance reset the list."""
    written = _write(finalizer, _cancelled([1, 2, 3]),
                     {"completed_room_ids_cumulative": [1], "completed_room_ids": []})
    assert sorted(written["missed_room_ids"]) == [2, 3]
    assert sorted(written["completed_room_ids"]) == [1]


def test_missed_unions_cumulative_and_current_phase(finalizer):
    """[JF-13c] the current phase's own progress still counts."""
    written = _write(finalizer, _cancelled([1, 2, 3]),
                     {"completed_room_ids_cumulative": [1], "completed_room_ids": [2]})
    assert sorted(written["missed_room_ids"]) == [3]


def test_timing_evidence_counts_a_room_as_completed(finalizer):
    """[JF-13c] clause 3 — a finished phase's timing is completion evidence."""
    written = _write(
        finalizer,
        _cancelled([1, 2], timings=[{"room_id": 1, "cleaning_seconds": 120}]),
        {"completed_room_ids": []},
    )
    assert sorted(written["missed_room_ids"]) == [2]


def test_zero_second_timing_is_not_completion_evidence(finalizer):
    """[JF-13c] clause 3, the other direction — NO synthesis of completion."""
    written = _write(
        finalizer,
        _cancelled([1, 2], timings=[{"room_id": 1, "cleaning_seconds": 0}]),
        {"completed_room_ids": []},
    )
    assert sorted(written["missed_room_ids"]) == [1, 2]


def test_normal_completion_does_not_clear_a_nonoverlapping_log(finalizer):
    """[JF-13c] STATE-2 — a Kitchen run must not erase a Bedroom+Den strand."""
    _write(finalizer, _cancelled([5, 6]), {"completed_room_ids": []})
    _write(finalizer,
           {"job_id": "j2", "outcome": {"status": "completed"},
            "queue": {"queue_room_ids": [1]},
            "resolved_rooms": [{"room_id": 1, "name": "Kitchen"}]},
           {"completed_room_ids": [1]})
    log = finalizer.store.load_incomplete_run(vacuum_entity_id=_VAC_13C)
    assert sorted(log["missed_room_ids"]) == [5, 6]


def test_normal_completion_clears_an_overlapping_log(finalizer):
    """[JF-13c] STATE-2 — a run covering a logged room DOES clear it."""
    _write(finalizer, _cancelled([5, 6]), {"completed_room_ids": []})
    _write(finalizer,
           {"job_id": "j2", "outcome": {"status": "completed"},
            "queue": {"queue_room_ids": [5, 6]},
            "resolved_rooms": [{"room_id": 5}, {"room_id": 6}]},
           {"completed_room_ids": [5, 6]})
    assert finalizer.store.load_incomplete_run(vacuum_entity_id=_VAC_13C) is None


def test_overlapping_rooms_on_a_different_map_do_not_clear(finalizer):
    """[JF-13c] STATE-2 — same room id on another floor is a different room."""
    _write(finalizer, _cancelled([5, 6]), {"completed_room_ids": []})
    finalizer._write_incomplete_run_log(
        vacuum_entity_id=_VAC_13C, map_id="99",
        completed_job={"job_id": "j2", "outcome": {"status": "completed"},
                       "queue": {"queue_room_ids": [5]},
                       "resolved_rooms": [{"room_id": 5}]},
        active_job_state={"completed_room_ids": [5]},
        ended_at="2026-08-02T01:00:00Z",
    )
    log = finalizer.store.load_incomplete_run(vacuum_entity_id=_VAC_13C)
    assert sorted(log["missed_room_ids"]) == [5, 6]
