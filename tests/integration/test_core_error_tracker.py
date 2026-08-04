"""Tests for core/error_tracker.py — active-run error latch tracker.

Drives ErrorTracker with a MagicMock manager (``.data`` dict + AsyncMock
``async_save``) and the real ``hass`` fixture for the state machine, listeners,
and loop. Edge handling, latch shaping, harvest, acknowledge, and the
secondary-channel grace window are all exercised against crafted records.

Coverage targets
----------------
[ET-1]  module helpers: _is_error_value, _get_not_error_set, _safe_int, _job_elapsed.
[ET-2]  _ensure_record defaults + recent_errors limit slicing.
[ET-3]  rising edge with active job → forms latch + last_device + ring buffer.
[ET-4]  rising edge without active job → last_device only, no active latch.
[ET-5]  second rising edge extends the latch (error_count++, recovered reset).
[ET-6]  falling edge marks recovered + stamps recovered_at.
[ET-7]  harvest_active_run returns + clears latch; None when empty.
[ET-8]  acknowledge scopes (active_run / last_device / both) + missing record.
[ET-9]  _read_error_code_attr reads code attr, treats 0 as None.
[ET-10] _handle_error_message_change rising then falling via the public seam.
[ET-11] start/_wire_vacuum wires listeners; stop tears them down.
[ET-12] secondary-channel grace: schedule on vacuum=error, generic latch on expiry.
[ET-13] _persist_and_notify schedules async_save + fires update listeners.
[ET-14] task_status in 'error' counts as a secondary error channel.
[ET-15] RF-DOCK clause 4: error_source_for_code resolves dock/robot/unknown from the
        adapter tables, independently of the evidence axis.
[ET-15b] a brand declaring no source tables reports every fault unattributed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from tests._factories import spec_manager

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.core import error_tracker as et
from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker


_VAC = "vacuum.alfred"


@pytest.fixture
def tracker(hass):
    """Return (ErrorTracker, mock_manager) with a real hass + AsyncMock save."""
    mgr = spec_manager()
    mgr.data = {}
    mgr.async_save = AsyncMock()
    return ErrorTracker(hass, runtime_manager=mgr), mgr


def _seed_active_job(mgr, *, job_id="j1", room_id=3, started_minutes_ago=2,
                     status="started"):
    """Seed an active job.

    `status` is REQUIRED in production — every real active-job record carries one, and
    "in flight" is decided from it (`dispatched_job_is_in_flight`). This fixture used to
    omit it, which is a shape production never produces; the tracker's in-flight check was
    therefore never exercised against a realistic record. Pass status="completed" to model
    a FINISHED job still sitting in the slot, which is the state that caused error
    misattribution.
    """
    started = (datetime.now(timezone.utc)
               - timedelta(minutes=started_minutes_ago)).isoformat()
    mgr.data["active_jobs"] = {
        _VAC: {"6": {"job_id": job_id, "started_at": started,
                     "status": status, "current_room_id": room_id}}}


# ---------------------------------------------------------------------------
# module helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("unknown", False), ("unavailable", False),
    ("Stuck", True), ("E70", True), ("  ", False),
])
def test_is_error_value(value, expected):
    """[ET-1]"""
    assert et._is_error_value(value) is expected


def test_get_not_error_set_and_safe_int():
    """[ET-1]"""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "vocabulary": {"not_error_sentinels": ["NONE", "Normal", ""]},
    })
    s = et._get_not_error_set(_VAC)
    assert "none" in s and "normal" in s
    # unregistered → generic fallback
    assert et._get_not_error_set("vacuum.unknown") == et._NOT_ERROR
    assert et._safe_int("5") == 5
    assert et._safe_int("x") is None
    assert et._safe_int(None) is None


def test_job_elapsed_seconds():
    """[ET-1]"""
    assert et._job_elapsed_seconds(None) == 0
    assert et._job_elapsed_seconds({"started_at": "not-a-date"}) == 0
    started = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    assert et._job_elapsed_seconds({"started_at": started}) >= 85


def test_job_elapsed_seconds_survives_a_naive_timestamp():
    """[ET-1b] A naive started_at PARSES fine and then raised on the subtraction.

    The function documents itself as clamping to 0 rather than raising, but the
    try/except only wraps fromisoformat — so a tz-naive value sailed through it and
    threw TypeError from inside a state-change callback, killing error recording for
    the whole run. Everything this integration writes is aware (_iso_now), so the
    reachable source is a value restored from an older store or hand-edited; UTC is
    the correct reading of it.
    """
    naive = (datetime.now(timezone.utc) - timedelta(seconds=90)).replace(tzinfo=None)
    assert et._job_elapsed_seconds({"started_at": naive.isoformat()}) >= 85
    # A future timestamp still clamps rather than going negative.
    ahead = (datetime.now(timezone.utc) + timedelta(seconds=90)).replace(tzinfo=None)
    assert et._job_elapsed_seconds({"started_at": ahead.isoformat()}) == 0


# ---------------------------------------------------------------------------
# record access
# ---------------------------------------------------------------------------

def test_ensure_record_and_recent_limit(tracker):
    """[ET-2]"""
    t, mgr = tracker
    rec = t.get_record(_VAC)
    assert rec == {"active_run_error": None, "last_device_error": None,
                   "recent_errors": []}
    rec["recent_errors"] = [{"message": f"e{i}"} for i in range(5)]
    assert len(t.recent_errors(_VAC)) == 5
    assert len(t.recent_errors(_VAC, limit=2)) == 2
    assert t.recent_errors(_VAC, limit=2)[-1]["message"] == "e4"


def test_stop_cancels_grace_timers_and_unsubs(tracker):
    """[ET-2b] stop() fires pending grace-timer cancels and listener unsubs, then
    clears all teardown state."""
    t, _ = tracker
    calls: list = []
    t._grace_cancels["s1"] = lambda: calls.append("grace")
    t._vacuum_unsubs["v1"] = [lambda: calls.append("unsub")]
    t.stop()
    assert "grace" in calls and "unsub" in calls
    assert t._grace_cancels == {} and t._vacuum_unsubs == {}


# ---------------------------------------------------------------------------
# rising / falling edges
# ---------------------------------------------------------------------------

async def test_rising_edge_with_active_job(tracker, hass):
    """[ET-3]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    hass.states.async_set(_VAC, "error")
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    await hass.async_block_till_done()

    rec = t.get_record(_VAC)
    assert rec["last_device_error"]["message"] == "Stuck"
    assert rec["last_device_error"]["was_during_active_run"] is True
    assert len(rec["recent_errors"]) == 1
    latch = rec["active_run_error"]
    assert latch["active_job_id"] == "j1"
    assert latch["error_count"] == 1
    assert latch["errored_room_id"] == "3"
    assert latch["current_message"] == "Stuck"
    mgr.async_save.assert_awaited()


async def test_rising_edge_without_active_job(tracker, hass):
    """[ET-4] no job in flight → last_device + ring, but no active-run latch."""
    t, mgr = tracker
    t._record_rising_edge(_VAC, message="E70", code=70, attribute_code=None)
    await hass.async_block_till_done()
    rec = t.get_record(_VAC)
    assert rec["last_device_error"]["message"] == "E70"
    assert rec["active_run_error"] is None
    assert rec["last_device_error"]["was_during_active_run"] is False


async def test_second_rising_edge_extends_latch(tracker, hass):
    """[ET-5]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    t._record_falling_edge(_VAC)  # recovered=True
    t._record_rising_edge(_VAC, message="Cliff", code=6, attribute_code=None)
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch["error_count"] == 2
    assert latch["current_message"] == "Cliff"
    assert latch["recovered"] is False
    assert len(latch["errors"]) == 2


async def test_falling_edge_marks_recovered(tracker, hass):
    """[ET-6]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    t._record_falling_edge(_VAC)
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch["recovered"] is True
    assert latch["current_message"] == ""
    assert latch["errors"][-1]["recovered_at"] is not None
    # no-op when there's no latch
    t2, _ = tracker
    other = "vacuum.none"
    t._record_falling_edge(other)
    assert t.get_record(other)["active_run_error"] is None


# ---------------------------------------------------------------------------
# harvest + acknowledge
# ---------------------------------------------------------------------------

async def test_harvest_active_run(tracker, hass):
    """[ET-7]"""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    harvested = t.harvest_active_run(_VAC, "j1")
    await hass.async_block_till_done()
    assert harvested["active_job_id"] == "j1"
    assert t.get_record(_VAC)["active_run_error"] is None
    # nothing to harvest now
    assert t.harvest_active_run(_VAC, "j1") is None


async def test_acknowledge_scopes(tracker, hass):
    """[ET-8]"""
    t, mgr = tracker
    # missing record → False
    assert t.acknowledge("vacuum.ghost") is False
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    # scope=last_device clears only last_device
    assert t.acknowledge(_VAC, scope="last_device") is True
    rec = t.get_record(_VAC)
    assert rec["last_device_error"] is None
    assert rec["active_run_error"] is not None
    # scope=both, job STILL IN FLIGHT -> the latch is MARKED, not destroyed. Deleting it
    # here would strip the run's error evidence before the finalizer reads it, and with it
    # the had_errors idle-wall exemption — so a stuck-then-freed run would be held from
    # learning as "unexplained idle" while its own record denied the error happened.
    t.acknowledge(_VAC, scope="both")
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None, "acknowledging mid-run destroyed the finalizer's evidence"
    assert latch["acknowledged"] is True
    assert latch["current_message"] == ""   # nothing left for the entities to show
    assert latch["errors"], "the error history itself must survive"

    # Same call with NO job in flight -> nothing to preserve, so it clears as before.
    mgr.data["active_jobs"][_VAC]["6"]["status"] = "completed"
    t.acknowledge(_VAC, scope="both")
    assert t.get_record(_VAC)["active_run_error"] is None


# ---------------------------------------------------------------------------
# code attribute + message-change seam
# ---------------------------------------------------------------------------

def test_read_error_code_attr(tracker, hass):
    """[ET-9] code from attrs; 0 treated as 'no code'."""
    t, mgr = tracker
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    hass.states.async_set("sensor.alfred_err", "Stuck", {"error_code": 70})
    assert t._read_error_code_attr(_VAC) == 70
    hass.states.async_set("sensor.alfred_err", "Stuck", {"error_code": 0})
    assert t._read_error_code_attr(_VAC) is None
    hass.states.async_set("sensor.alfred_err", "Stuck", {})
    assert t._read_error_code_attr(_VAC) is None


async def test_handle_error_message_change(tracker, hass):
    """[ET-10] rising then falling through the message-change handler."""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    t._handle_error_message_change(_VAC, "unknown", "Stuck")
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["current_message"] == "Stuck"
    t._handle_error_message_change(_VAC, "Stuck", "")
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["recovered"] is True


# ---------------------------------------------------------------------------
# wiring + grace window
# ---------------------------------------------------------------------------

def test_start_wires_and_stop_clears(tracker, hass):
    """[ET-11]"""
    t, mgr = tracker
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err",
                     "task_status": "sensor.alfred_task"},
    })
    t.start([_VAC])
    assert _VAC in t._vacuum_unsubs
    assert t._source_to_vacuum["sensor.alfred_err"] == _VAC
    assert t._source_to_vacuum["sensor.alfred_task"] == _VAC
    # idempotent re-wire
    t.start([_VAC])
    t.stop()
    assert t._vacuum_unsubs == {}
    assert t._source_to_vacuum == {}


async def test_secondary_grace_schedule_and_expiry(tracker, hass):
    """[ET-12] vacuum=error + no message schedules grace; expiry latches generic."""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    hass.states.async_set(_VAC, "error")
    hass.states.async_set("sensor.alfred_err", "unknown")
    t._handle_secondary_error_signal(_VAC)
    assert _VAC in t._grace_cancels
    # let the real 5s grace timer fire → _on_grace_expired latches generic
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None
    assert latch["current_message"] == "Unknown error during run"


# ---------------------------------------------------------------------------
# persist + notify
# ---------------------------------------------------------------------------

async def test_wired_event_routing(tracker, hass):
    """[ET-11] full wired path: a real error_message state change → rising latch."""
    t, mgr = tracker
    _seed_active_job(mgr)
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err",
                     "task_status": "sensor.alfred_task"},
    })
    hass.states.async_set("sensor.alfred_err", "normal")
    hass.states.async_set(_VAC, "cleaning")
    t.start([_VAC])
    # rising edge through the real listener
    hass.states.async_set("sensor.alfred_err", "Stuck")
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["current_message"] == "Stuck"
    t.stop()


def test_secondary_error_via_task_status(tracker, hass):
    """[ET-14] task_status in 'error' counts as a secondary error channel."""
    t, mgr = tracker
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": "sensor.alfred_task"}
    hass.states.async_set(_VAC, "docked")          # vacuum NOT in error
    hass.states.async_set("sensor.alfred_task", "error")  # but task_status is
    assert t._is_in_secondary_error(_VAC) is True
    # both channels clear → no secondary error
    hass.states.async_set("sensor.alfred_task", "cleaning")
    assert t._is_in_secondary_error(_VAC) is False


async def test_secondary_clear_emits_falling_edge(tracker, hass):
    """[ET-12] secondary channels clear with empty message → falling edge fires."""
    t, mgr = tracker
    _seed_active_job(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": None}
    # form an unrecovered latch first
    t._record_rising_edge(_VAC, message="Stuck", code=5, attribute_code=None)
    await hass.async_block_till_done()
    # vacuum no longer in error + message empty → falling edge via secondary path
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_err", "")
    t._handle_secondary_error_signal(_VAC)
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["recovered"] is True


async def test_persist_and_notify(tracker, hass):
    """[ET-13]"""
    t, mgr = tracker
    seen: list[str] = []
    unsub = t.add_update_listener(lambda vid: seen.append(vid))
    t._persist_and_notify(_VAC)
    await hass.async_block_till_done()
    assert seen == [_VAC]
    mgr.async_save.assert_awaited()
    # unsub stops further notifications
    unsub()
    t._persist_and_notify(_VAC)
    await hass.async_block_till_done()
    assert seen == [_VAC]


def test_no_latch_forms_for_a_finalized_job(tracker):
    """[ET-inflight] REGRESSION: an error observed BETWEEN runs must not latch onto the
    finished job.

    The in-flight check was `started_at and not ended_at`, but ended_at is never written to
    an active-job record — mark_active_job_finalized sets status="completed" and leaves
    started_at. So a finished job matched forever: an error after docking formed a latch
    under the dead job's id, turning the problem binary_sensor on with nothing running, and
    the NEXT run then inherited that latch's identity fields at harvest.
    """
    et, mgr = tracker
    _seed_active_job(mgr, job_id="j_done", status="completed")

    assert et._lookup_active_job(_VAC) is None, "a finalized job read as in flight"

    # And the live case still works.
    _seed_active_job(mgr, job_id="j_live", status="started")
    live = et._lookup_active_job(_VAC)
    assert live is not None and live["job_id"] == "j_live"


def test_multi_map_does_not_let_a_stale_bucket_shadow_the_live_one(tracker):
    """[ET-inflight-2] The traversal returns the FIRST matching map. With the old predicate
    a finished map-A bucket permanently shadowed a live map-B run, so every error was
    stamped with map A's job id, elapsed time and room."""
    et, mgr = tracker
    started = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    mgr.data["active_jobs"] = {
        _VAC: {
            "6": {"job_id": "old_mapA", "started_at": started,
                  "status": "completed", "finalized": True, "current_room_id": 1},
            "7": {"job_id": "live_mapB", "started_at": started,
                  "status": "started", "current_room_id": 9},
        }
    }
    found = et._lookup_active_job(_VAC)
    assert found is not None and found["job_id"] == "live_mapB", (
        "a stale finalized map bucket shadowed the live run"
    )


async def test_grace_expiry_latches_when_message_sits_at_the_brand_idle_value(tracker, hass):
    """[ET-12a] ES-1 REGRESSION. The expiry check must use the ADAPTER's not-error set.

    With the generic set, a brand's own IDLE value ("none" for both brands, "normal" for
    Eufy) reads as an ERROR, so _on_grace_expired returned early and latched NOTHING —
    total evidence loss for exactly the fault class the secondary channels exist to catch
    (firmware that never populates error_message on a stuck event).

    The pre-existing grace test uses "unknown", the one value where the generic and adapter
    sets AGREE, so it was structurally incapable of catching this.
    """
    t, mgr = tracker
    _seed_active_job(mgr)
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err", "task_status": None},
        "vocabulary": {"not_error_sentinels": ["none", "normal"]},
    })
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}
    hass.states.async_set(_VAC, "error")
    hass.states.async_set("sensor.alfred_err", "none")   # the BRAND's idle value

    t._handle_secondary_error_signal(_VAC)
    assert _VAC in t._grace_cancels

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()

    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None, "the fault produced NO durable evidence at all"
    assert latch["current_message"] == "Unknown error during run"


async def test_grace_does_not_rearm_while_a_placeholder_latch_stands(tracker, hass):
    """[ET-12b] FIND-2 REGRESSION. One sustained fault must not manufacture N edges.

    _on_grace_expired pops its own _grace_cancels entry before doing anything, so the
    "already pending" guard is false again the instant it fires, and the rising edge it
    records carries no dedup key. Every further upstream state write re-armed and produced
    another identical placeholder — inflating error_count into the tens for ONE physical
    fault and flushing the 50-entry recent_errors ring, the only shadow copy that survives
    a harvest.

    This was dormant only because ES-1 returned early; fixing that alone unmasks it.
    """
    t, mgr = tracker
    _seed_active_job(mgr)
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err", "task_status": None},
        "vocabulary": {"not_error_sentinels": ["none", "normal"]},
    })
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}
    hass.states.async_set(_VAC, "error")
    hass.states.async_set("sensor.alfred_err", "none")

    # First arm -> expiry -> one placeholder edge.
    t._handle_secondary_error_signal(_VAC)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert t.get_record(_VAC)["active_run_error"]["error_count"] == 1

    # The fault persists; upstream writes state again. Must NOT re-arm or re-latch.
    t._handle_secondary_error_signal(_VAC)
    assert _VAC not in t._grace_cancels, "re-armed while a placeholder latch was standing"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=12))
    await hass.async_block_till_done()

    latch = t.get_record(_VAC)["active_run_error"]
    assert latch["error_count"] == 1, (
        f"one physical fault produced {latch['error_count']} edges"
    )
    assert len(latch.get("errors") or []) == 1


async def test_job_finished_without_a_record_does_not_clear_the_latch(hass, tracker):
    """[ET-ED3] EVENT_JOB_FINISHED also fires on paths where the finalize RAISED — a cancel
    still marks the job finalized and fires the event with finalize_result=None.

    On those paths the latch was never harvested, so it is the run's ONLY surviving error
    evidence. Clearing it here discarded exactly what the peek/commit split exists to
    preserve: the commit deliberately keeps the latch when the record write fails, and this
    door then threw it away anyway.

    job_path is present on every real payload and non-empty only when a record landed.
    """
    et, mgr = tracker
    _seed_active_job(mgr, status="started")

    # A recovered latch — the shape the auto-clear targets.
    et._ensure_record(_VAC)["active_run_error"] = {
        "current_message": "", "recovered": True, "errors": [{"captured_at": "t0"}],
    }

    # Finalize raised -> job_path absent/empty.
    from custom_components.eufy_vacuum.const import EVENT_JOB_FINISHED
    hass.bus.async_fire(EVENT_JOB_FINISHED, {"vacuum_entity_id": _VAC, "map_id": "6"})
    await hass.async_block_till_done()

    assert et.get_active_run_latch(_VAC) is not None, (
        "the run's only error evidence was cleared after a failed finalize"
    )


# --- ET-VOC-3: the three advertised-but-unread error_tracking knobs -----------
# Every assertion below uses a value DIFFERENT from the hardcoded default, so each
# test fails against the pre-fix tracker. Both shipped brands declare exactly the
# defaults, so wiring these up is behaviour-neutral for Eufy and Roborock — it makes
# the contract doc 22 §9 advertises actually true for the next brand.

def test_task_status_error_value_is_brand_vocabulary(tracker, hass):
    """[ET-VOC-3a] A brand whose task_status says something other than "error".

    The value was hardcoded to == "error", so this entire secondary channel was
    silently dead for any such brand: no grace window, no placeholder latch, and a
    hardware fault that never populates error_message produced no evidence at all.
    """
    t, mgr = tracker
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err",
                     "task_status": "sensor.alfred_task"},
        "error_tracking": {"task_status_error_value": "fault"},
    })
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err",
                                "task_status": "sensor.alfred_task"}
    hass.states.async_set(_VAC, "docked")           # vacuum channel NOT in error

    hass.states.async_set("sensor.alfred_task", "Fault")   # capitalized, as firmware sends
    assert t._is_in_secondary_error(_VAC) is True, "declared error value was ignored"

    # The DEFAULT vocabulary must not leak in beside the declared one.
    hass.states.async_set("sensor.alfred_task", "error")
    assert t._is_in_secondary_error(_VAC) is False, (
        "hardcoded 'error' still matched for a brand that declared 'fault'"
    )


async def test_grace_window_seconds_is_honoured(tracker, hass):
    """[ET-VOC-3b] Firmware that emits the state DPS well before the message DPS.

    5s was a module constant, so a slower brand could not ask for a longer window and
    every real message arriving at, say, 20s was thrown away — the latch had already
    been finalized as the generic placeholder with code None.
    """
    t, mgr = tracker
    _seed_active_job(mgr)
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err", "task_status": None},
        "vocabulary": {"not_error_sentinels": ["none", "normal"]},
        "error_tracking": {"grace_window_seconds": 30},
    })
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}
    hass.states.async_set(_VAC, "error")
    hass.states.async_set("sensor.alfred_err", "none")

    t._handle_secondary_error_signal(_VAC)

    # Past the OLD default, well short of the declared window: nothing may latch yet.
    # This is the half that matters — before the fix the placeholder was already written
    # here, and a real message arriving at 20s had nothing left to upgrade.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert t.get_record(_VAC).get("active_run_error") is None, (
        "latched at the hardcoded 5s instead of the declared 30s"
    )

    # Past the declared window: the timer really is armed, just later.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None, "the declared window never fired at all"
    assert latch["current_message"] == "Unknown error during run"


def test_error_code_attribute_names_is_an_ordered_brand_list(tracker, hass):
    """[ET-VOC-3c] A brand exposing its code under a name outside the default tuple.

    doc 22 §9 documents this as an ordered list, first non-zero int wins. It was a
    hardcoded tuple, so such a brand got code=None on every error — losing exactly the
    field the error-mining work exists to capture.
    """
    t, mgr = tracker
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"error_message": "sensor.alfred_err", "task_status": None},
        "error_tracking": {"error_code_attribute_names": ["fault_id", "legacy_code"]},
    })
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}

    hass.states.async_set("sensor.alfred_err", "Stuck", {"fault_id": 70})
    assert t._read_error_code_attr(_VAC) == 70, "declared attribute name was not read"

    # Ordered: the first declared name that yields a non-zero int wins...
    hass.states.async_set("sensor.alfred_err", "Stuck",
                          {"fault_id": 0, "legacy_code": 12})
    assert t._read_error_code_attr(_VAC) == 12, "list is not tried in order"

    # ...and the declared list REPLACES the default rather than extending it, so a
    # stale upstream error_code attribute cannot shadow the brand's real one.
    hass.states.async_set("sensor.alfred_err", "Stuck", {"error_code": 99})
    assert t._read_error_code_attr(_VAC) is None, (
        "default attribute names still consulted for a brand that declared its own"
    )


def test_error_tracking_cfg_degrades_to_each_callers_default(tracker, hass):
    """[ET-VOC-3d] No adapter, no error_tracking block, junk values → documented defaults.

    _error_tracking_cfg never raises; each caller then applies its own default. This is
    the path every currently-shipped install takes when adapter registration has not
    completed yet.
    """
    register_adapter_config(_VAC, {"adapter_id": "t", "source": "t", "entities": {}})
    assert et._error_tracking_cfg(_VAC) == {}
    assert et._error_tracking_cfg("vacuum.never_registered") == {}

    # A block of the wrong type must not propagate to callers as a mapping.
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t", "entities": {}, "error_tracking": "nonsense",
    })
    assert et._error_tracking_cfg(_VAC) == {}

    t, _mgr = tracker
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}
    hass.states.async_set("sensor.alfred_err", "Stuck", {"errorCode": 70})
    assert t._read_error_code_attr(_VAC) == 70, "fell off the default attribute tuple"


# --- FIND-6: app-started (external) runs must latch too -----------------------

def _seed_external_capture(mgr, *, room_id=3, started_minutes_ago=2):
    """Seed a real external capture slot.

    Deliberately shaped like ``start_external_capture`` writes it: status="external",
    a started_at, and **no job_id** — the id is assigned at graduate time from the
    pending record. Seeding a job_id here would hide the second half of the defect.
    """
    started = (datetime.now(timezone.utc)
               - timedelta(minutes=started_minutes_ago)).isoformat()
    mgr.data["active_jobs"] = {
        _VAC: {"6": {"started_at": started, "status": "external",
                     "current_room_id": room_id}}}


async def test_external_run_forms_an_active_run_latch(tracker, hass):
    """[FIND-6] An app-started run is a real run on real hardware.

    The tracker asked `dispatched_job_is_in_flight`, which is DISPATCH-only by design, so
    an external capture never counted as in flight. Even past that, the latch was gated on
    `active_job_id is not None` and an external slot carries no job_id — two independent
    reasons the latch could not form.

    The user-visible result: every fault during an app-started run landed in
    last_device_error and recent_errors, then was omitted from the run's own record — the
    one place the review wizard looks when it asks "does this look right?".
    """
    t, mgr = tracker
    _seed_external_capture(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}

    t._record_rising_edge(_VAC, message="Brush stuck", code=70, attribute_code=None)
    await hass.async_block_till_done()

    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None, "an app-started run formed no error latch at all"
    assert latch["error_count"] == 1
    assert latch["errors"][0]["message"] == "Brush stuck"
    assert latch["errors"][0]["room_id"] == "3", "external attribution was dropped"
    # Honest about identity: there IS no job id yet, and claiming one would be worse.
    assert latch["active_job_id"] is None
    # The elapsed clock still works — started_at is present on an external slot.
    assert latch["first_seen_job_elapsed_seconds"] >= 100


async def test_a_finished_external_slot_does_not_latch(tracker, hass):
    """[FIND-6] The widened predicate must not re-open the hole it replaced.

    `run_is_in_flight` adds "external" to the dispatched set and nothing else. A slot the
    external finalizer has already cleared is status="idle", so errors seen between runs
    still form no latch — the misattribution bug that the in-flight predicate was
    introduced to fix stays fixed.
    """
    t, mgr = tracker
    _seed_external_capture(mgr)
    mgr.data["active_jobs"][_VAC]["6"]["status"] = "idle"   # clear_active_job's shape
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}

    t._record_rising_edge(_VAC, message="Brush stuck", code=70, attribute_code=None)
    await hass.async_block_till_done()

    assert t.get_record(_VAC)["active_run_error"] is None
    # ...but the device-level buffers still record it, as they always did.
    assert t.get_record(_VAC)["last_device_error"]["message"] == "Brush stuck"
    assert len(t.get_record(_VAC)["recent_errors"]) == 1


async def test_acknowledging_mid_external_run_marks_rather_than_deletes(tracker, hass):
    """[FIND-6 + FIND-3] The mid-run preservation applies to external runs too.

    Same story as the dispatched case: the user frees the stuck robot and clears the
    alert — which is why they went. The run must not then graduate claiming nothing
    happened. Both sites now ask `run_is_in_flight`, so they cannot drift apart.
    """
    t, mgr = tracker
    _seed_external_capture(mgr)
    t._vacuum_entities[_VAC] = {"error_message": "sensor.alfred_err", "task_status": None}
    t._record_rising_edge(_VAC, message="Brush stuck", code=70, attribute_code=None)
    await hass.async_block_till_done()

    assert t.acknowledge(_VAC, scope="active_run") is True

    latch = t.get_record(_VAC)["active_run_error"]
    assert latch is not None, "acknowledging destroyed an external run's only evidence"
    assert latch["acknowledged"] is True
    assert latch["current_message"] == ""      # nothing left for the entities to show
    assert latch["errors"][0]["message"] == "Brush stuck"   # ...but the history survives


# --- FIND-7: nothing hands out the live latch ---------------------------------

async def test_the_latch_handed_to_entities_does_not_change_underneath_them(tracker, hass):
    """[FIND-7] A recorded State must not be rewritten by a later edge.

    `get_active_run_latch` returned the LIVE latch. Home Assistant wraps a State's
    attributes in a ReadOnlyDict but does not copy the nested values, so the `errors`
    entries inside an already-written State were the same dicts the tracker went on to
    mutate. `_record_falling_edge` stamps `recovered_at` IN PLACE on the newest unstamped
    entry — reaching back into a State written minutes earlier and making history claim the
    fault was already recovered at a time when it demonstrably was not.

    A shallow `dict(latch)` at the call site does not help; the nesting is where the
    sharing lives. This is the same hazard `peek_active_run` already deep-copies against.
    """
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Brush stuck", code=70, attribute_code=None)
    await hass.async_block_till_done()

    # What a presentation surface was handed, and would hold onto.
    handed_out = t.get_active_run_latch(_VAC)
    assert handed_out["errors"][0]["recovered_at"] is None

    # Time passes; the robot recovers.
    t._record_falling_edge(_VAC)
    await hass.async_block_till_done()

    assert handed_out["errors"][0]["recovered_at"] is None, (
        "a later falling edge rewrote an already-recorded snapshot"
    )
    assert handed_out["recovered"] is False, "the top-level flag was rewritten too"
    # The live latch did of course advance — the snapshot just isn't it.
    assert t.get_active_run_latch(_VAC)["errors"][0]["recovered_at"] is not None


async def test_a_handed_out_latch_cannot_corrupt_the_tracker(tracker, hass):
    """[FIND-7] The isolation holds in the other direction too.

    A consumer that mutates what it was given — a card payload builder normalizing a
    field, a test, anything — must not be able to reach into the tracker's own state.
    """
    t, mgr = tracker
    _seed_active_job(mgr)
    t._record_rising_edge(_VAC, message="Brush stuck", code=70, attribute_code=None)
    await hass.async_block_till_done()

    handed_out = t.get_active_run_latch(_VAC)
    handed_out["error_count"] = 999
    handed_out["errors"][0]["message"] = "tampered"
    handed_out["errors"].append({"message": "injected"})

    live = t.get_active_run_latch(_VAC)
    assert live["error_count"] == 1
    assert live["errors"][0]["message"] == "Brush stuck"
    assert len(live["errors"]) == 1

    # last_device_error is flat today, but the same guarantee applies.
    device = t.get_last_device_latch(_VAC)
    device["message"] = "tampered"
    assert t.get_last_device_latch(_VAC)["message"] == "Brush stuck"


# ---------------------------------------------------------------------------
# [ET-15] RF-DOCK clause 4 — error_source_for_code: WHOSE hardware raised it
# ---------------------------------------------------------------------------

def test_error_source_for_code_reads_the_adapter_tables():
    """[ET-15] dock / robot / unknown, sourced from the adapter's declared sets.

    A SECOND axis from classify_error_code, not a finer grain of it. The live
    incident's 6013 faults are evidence-SAFE (correctly not deducted) and
    dock-SOURCED (the user's station pump is failing) — reporting only the
    evidence axis tells them the run was fine and never tells them that.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.core.error_tracker import (
        classify_error_code, error_source_for_code,
    )

    register_adapter_config(_VAC, {
        "error_tracking": {
            "dock_sourced_error_codes": [6013],
            "robot_sourced_error_codes": [2112],
            "evidence_invalidating_error_codes": [2112],
            "evidence_safe_error_codes": [6013],
        },
    })

    assert error_source_for_code(_VAC, 6013) == "dock"
    assert error_source_for_code(_VAC, 2112) == "robot"
    # a code in neither table is UNATTRIBUTED, never guessed into a majority class
    assert error_source_for_code(_VAC, 9999) == "unknown"
    assert error_source_for_code(_VAC, None) == "unknown"

    # the two axes are independent: dock-sourced is evidence-SAFE here, and the
    # pair (dock, safe) is exactly the combination a single collapsed axis loses
    assert (error_source_for_code(_VAC, 6013), classify_error_code(_VAC, 6013)) == ("dock", "safe")
    assert (error_source_for_code(_VAC, 2112), classify_error_code(_VAC, 2112)) == ("robot", "invalidating")


def test_error_source_for_code_undeclared_brand_reports_unknown():
    """[ET-15b] a brand declaring no source tables attributes NOTHING.

    Roborock is deliberately in this state — its codes arrive as enum strings,
    so an int-keyed table would be a table of guesses. Reporting every fault as
    unattributed is the honest degradation; defaulting to "robot" would start
    blaming hardware that is fine.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.core.error_tracker import error_source_for_code

    register_adapter_config(_VAC, {"error_tracking": {"grace_window_seconds": 5}})
    for code in (6013, 2112, 1, 0, "bumper_stuck"):
        assert error_source_for_code(_VAC, code) == "unknown"
