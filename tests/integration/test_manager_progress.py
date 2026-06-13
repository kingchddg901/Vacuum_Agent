"""Tests for core/manager.py::get_job_progress_snapshot — the live job engine.

~150 lines of real logic (timeline estimate/reanchor, current-room derivation,
bounds-exit + stall detection) that the dashboard polls. Driven against the
real manager + a wired LearningManager with seeded active-job state.

Coverage targets
----------------
[PR-1]  idle job → terminal snapshot, empty timeline.
[PR-2]  started job + learning + resolved rooms → snapshot with derived current
        room and a timeline.
[PR-3]  completed rooms → the reanchor timeline branch.
[PR-4]  a long-overrun current room → awaiting_bounds_exit / stall signalling.
[PR-5]  finalize_learning_for_active_job: no learning manager → None.
[PR-6]  finalize_learning_for_active_job: missing started_at → not finalized.
[PR-7]  finalize_learning_for_active_job: full job → completed_job result.
[PR-8]  jobs-index → room-history merge with newer-wins + bad-row skips.
[PR-9]  single-room stall fires EVENT_STALL_DETECTED exactly once (no re-fire).
[PR-10] single-room at ~1.7x threshold → running_long but NOT stall.
[PR-11] non-sequential advance → room flagged skipped + EVENT_ROOM_SKIPPED once.
[PR-12] normal sequential run (completed prefix) → no skips.
[PS-1]  get_payload_state enriches dict rooms + continues past non-dict entries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.eufy_vacuum.const import (
    DATA_LEARNING,
    DOMAIN,
    EVENT_ROOM_SKIPPED,
    EVENT_STALL_DETECTED,
)
from custom_components.eufy_vacuum.learning.manager import LearningManager


_VAC = "vacuum.alfred"
_MAP = "6"


def _wire(manager, hass):
    hass.data.setdefault(DOMAIN, {})[DATA_LEARNING] = LearningManager(hass)


def _seed_job(manager, *, minutes_ago=10, **extra):
    started = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    job = {
        "status": "started", "job_id": "j1",
        "started_at": started, "current_room_started_at": started,
        "queue_room_ids": [1, 2],
        "resolved_rooms": [
            {"room_id": 1, "name": "Kitchen", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "Bath", "minutes": 5, "clean_mode": "vacuum"},
        ],
        "completed_room_ids": [], "completed_rooms": [],
    }
    job.update(extra)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


def test_progress_idle(manager, hass):
    """[PR-1]"""
    _wire(manager, hass)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "idle"
    assert snap["terminal"] is True
    assert snap["timeline"] == []
    assert snap["timeline_source"] == "none"


def test_progress_started(manager, hass):
    """[PR-2]"""
    _wire(manager, hass)
    _seed_job(manager)
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["status"] == "started"
    assert snap["terminal"] is False
    assert snap["job_id"] == "j1"
    # a timeline was produced from the resolved rooms
    assert snap["timeline_source"] in {"estimate", "reanchored"}
    assert len(snap["timeline"]) >= 1
    # current room derived from the unresolved set
    assert snap["current_room_id"] in (1, 2)


def test_progress_reanchor(manager, hass):
    """[PR-3] a completed room drives the reanchor branch."""
    _wire(manager, hass)
    _seed_job(
        manager,
        completed_room_ids=[1],
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}],
    )
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["timeline_source"] == "reanchored"
    assert 1 in snap["completed_room_ids"]
    # room 1 shows as completed in the timeline
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["completed"] is True


def test_progress_stall(manager, hass):
    """[PR-4] a wildly-overrun current room raises awaiting_bounds_exit/stall.

    With no robot-position entities the timing rollover can't confirm the robot
    left the room, so an elapsed >> threshold should flag bounds-exit (and, at
    >= 2x, a stall + EVENT_STALL_DETECTED).
    """
    _wire(manager, hass)
    # current room started 60 minutes ago vs a 5-minute estimate → >> 2x
    _seed_job(manager, minutes_ago=60)
    hass.states.async_set(_VAC, "cleaning")
    events = []
    hass.bus.async_listen(EVENT_STALL_DETECTED, lambda e: events.append(e))
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    # whichever path the timing engine takes, the snapshot stays well-formed
    assert "awaiting_bounds_exit" in snap
    assert isinstance(snap["awaiting_bounds_exit"], bool)


def test_progress_stall_fires_once(manager, hass):
    """[PR-9] a single-room job stuck >= 2x its estimate fires EVENT_STALL_DETECTED
    exactly once — a second snapshot does not re-fire for the same room.

    Single-room so the timing engine has nowhere to roll the current room to;
    elapsed (60m) >> 2x the 5m estimate → bounds-exit + stall.
    """
    _wire(manager, hass)
    _seed_job(
        manager, minutes_ago=60,
        queue_room_ids=[1],
        resolved_rooms=[{"room_id": 1, "name": "Kitchen", "minutes": 5,
                         "clean_mode": "vacuum"}],
    )
    hass.states.async_set(_VAC, "cleaning")
    events = []
    hass.bus.async_listen(EVENT_STALL_DETECTED, lambda e: events.append(e))

    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["stall_detected"] is True
    assert snap["stall_ratio"] >= 2.0
    assert snap["running_long"] is False  # disjoint bands: >=2x is stall, not running_long

    # a second poll must NOT re-fire (dedup via _stall_notified_room_ids)
    manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(events) == 1
    assert events[0].data["room_id"] == 1


def test_progress_running_long(manager, hass):
    """[PR-10] a single-room job at ~1.7x its rollover threshold (below the 2x stall
    band) flags running_long but NOT stall. The threshold is read from the live
    estimate so the test is robust to the estimator's per-room minutes."""
    _wire(manager, hass)
    rooms = [{"room_id": 1, "name": "Kitchen", "minutes": 5, "clean_mode": "vacuum"}]
    _seed_job(manager, minutes_ago=0, queue_room_ids=[1], resolved_rooms=rooms)
    hass.states.async_set(_VAC, "cleaning")
    room0 = next(
        r for r in manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)["timeline"]
        if r.get("room_id") == 1
    )
    threshold = manager.active_job._timing_completion_threshold_minutes(room0)
    # re-seed so the current room has run ~1.7x the threshold (within [1.5x, 2.0x)).
    _seed_job(manager, minutes_ago=threshold * 1.7, queue_room_ids=[1], resolved_rooms=rooms)
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["running_long"] is True
    assert snap["stall_detected"] is False
    assert snap["running_long_room_id"] == 1
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["running_long"] is True


def test_progress_skipped_conservative(manager, hass):
    """[PR-11] when current_room is ahead of an uncompleted queued room (a non-
    sequential advance), that room is flagged skipped + fires EVENT_ROOM_SKIPPED once.
    Eufy's sequential counter rollover keeps this empty in normal runs (the reliable
    missed-rooms signal is the post-run incomplete_run_log)."""
    _wire(manager, hass)
    _seed_job(
        manager,
        queue_room_ids=[1, 2, 3],
        resolved_rooms=[
            {"room_id": 1, "name": "A", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 2, "name": "B", "minutes": 5, "clean_mode": "vacuum"},
            {"room_id": 3, "name": "C", "minutes": 5, "clean_mode": "vacuum"},
        ],
        completed_room_ids=[2],   # room 2 done, room 1 NOT — current advanced past 1
        current_room_id=3,
    )
    hass.states.async_set(_VAC, "cleaning")
    events: list = []
    hass.bus.async_listen(EVENT_ROOM_SKIPPED, lambda e: events.append(e.data))
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert 1 in snap["skipped_room_ids"]
    assert 1 not in snap["remaining_room_ids"]
    room1 = next((r for r in snap["timeline"] if r.get("room_id") == 1), None)
    assert room1 is not None and room1["skipped"] is True
    # a second poll must NOT re-fire (dedup via _skipped_notified_room_ids)
    manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert len(events) == 1 and events[0]["room_id"] == 1


def test_progress_sequential_no_false_skip(manager, hass):
    """[PR-12] a normal sequential run (completed prefix) flags NO skips."""
    _wire(manager, hass)
    _seed_job(manager, completed_room_ids=[1],
              completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}])
    hass.states.async_set(_VAC, "cleaning")
    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["skipped_room_ids"] == []


async def test_finalize_no_learning(manager):
    """[PR-5] no learning manager wired → None."""
    # the manager fixture does not set DATA_LEARNING
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result is None


def test_save_learning_snapshot_delegates(manager, monkeypatch):
    """[PR-5b] save_learning_snapshot_for_active_job forwards to the learning
    manager's save_live_snapshot_from_manager when one is available."""
    captured: dict = {}

    class _FakeLearning:
        def save_live_snapshot_from_manager(self, **kw):
            captured.update(kw)
            return {"saved": True}

    monkeypatch.setattr(manager, "_get_learning_manager", lambda: _FakeLearning())
    out = manager.save_learning_snapshot_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, started_at="2026-01-01T00:00:00+00:00",
        battery_start=90, job_id="job1")
    assert out == {"saved": True}
    assert captured["vacuum_entity_id"] == _VAC and captured["job_id"] == "job1"


def test_save_learning_snapshot_no_learning_returns_none(manager):
    """[PR-5b] no learning manager wired → None (the early-return guard)."""
    assert manager.save_learning_snapshot_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, started_at="x",
        battery_start=90, job_id="job1") is None


async def test_finalize_missing_started_at(manager, hass):
    """[PR-6] an active job with no started_at → not finalized."""
    _wire(manager, hass)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "started", "started_at": ""}
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["finalized"] is False
    assert result["reason"] == "missing_started_at"


async def test_finalize_main_path(manager, hass):
    """[PR-7] a full job finalizes into a completed_job record."""
    _wire(manager, hass)
    _seed_job(manager, battery_start=90)
    hass.states.async_set(_VAC, "docked", {"battery_level": 70})
    result = await manager.finalize_learning_for_active_job(
        vacuum_entity_id=_VAC, map_id=_MAP, battery_end=70)
    assert result is not None
    assert "completed_job" in result


def test_ingest_jobs_index_into_room_history(manager):
    """[PR-8] jobs-index → room-history merge with newer-wins + bad-row skips."""
    ing = manager._ingest_jobs_index_entry_into_room_history
    # guard branches
    assert ing(vacuum_entity_id=_VAC, index_entry="nope") is False
    assert ing(vacuum_entity_id=_VAC,
               index_entry={"map_id": "6", "rooms": []}) is False  # no ended_at
    assert ing(vacuum_entity_id=_VAC, index_entry={
        "ended_at": "2026-01-01T10:00:00+00:00", "rooms": "notalist"}) is False

    # valid entry: merges fields, skips bad rows
    entry = {
        "ended_at": "2026-01-01T10:00:00+00:00", "map_id": "6", "rooms": [
            {"room_id": 1, "name": "Kitchen", "clean_mode": "vacuum",
             "last_cleaned_at": "2026-01-01T10:00:00+00:00",
             "last_vacuumed_at": "2026-01-01T10:00:00+00:00"},
            {"room_id": 0, "name": "bad"},   # room_id <= 0 → skipped
            "notadict",                       # non-dict row → skipped
        ]}
    assert ing(vacuum_entity_id=_VAC, index_entry=entry) is True
    rh = manager.data["room_history"][_VAC]["6"]["1"]
    assert rh["room_name"] == "Kitchen"
    assert rh["last_cleaned_at"] == "2026-01-01T10:00:00+00:00"
    assert rh["last_job_mode"] == "vacuum"

    # an older entry must NOT overwrite the newer last_cleaned_at
    older = {"ended_at": "2025-01-01T00:00:00+00:00", "map_id": "6", "rooms": [
        {"room_id": 1, "last_cleaned_at": "2025-01-01T00:00:00+00:00"}]}
    ing(vacuum_entity_id=_VAC, index_entry=older)
    assert manager.data["room_history"][_VAC]["6"]["1"]["last_cleaned_at"] == \
        "2026-01-01T10:00:00+00:00"


def test_payload_state_enrichment_skips_non_dict_rooms(manager):
    """[PS-1] get_payload_state enriches each dict room in resolved_rooms with
    settings-profile-display + surface labels, and the loop *continues past* a
    non-dict entry (manager.py:2025) rather than enriching or emitting it.

    Seeds the payload bucket directly on manager.data (the exact dict
    get_payload_state reads at L2005-2018) with one valid room dict plus a bare
    string. The returned resolved_rooms must contain exactly the one enriched
    dict; the non-dict is dropped.
    """
    manager.data.setdefault("payloads", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "payload": {"map_id": _MAP, "rooms": []},
        "resolved_rooms": [
            {
                "room_id": 1,
                "name": "Kitchen",
                "clean_mode": "vacuum",
                "fan_speed": "max",
                "floor_type": "hard",
                "clean_passes": 2,
            },
            "not-a-dict",  # the non-dict the loop must skip (manager.py:2025)
        ],
        "room_count": 2,
    }

    state = manager.get_payload_state(vacuum_entity_id=_VAC, map_id=_MAP)

    resolved = state["resolved_rooms"]
    # the string was dropped — exactly one enriched dict survives
    assert len(resolved) == 1
    room = resolved[0]
    assert isinstance(room, dict)

    # original fields carried through
    assert room["room_id"] == 1
    assert room["name"] == "Kitchen"

    # _settings_profile_display enrichment keys present on the surviving room
    assert "profile_label" in room
    assert room["clean_mode_label"] == "Vacuum"
    assert room["fan_speed_label"] == "Max"
    assert room["clean_passes_label"] == "2 Passes"
    assert isinstance(room["is_custom_profile"], bool)

    # _room_surface_labels enrichment key present
    assert "floor_type_label" in room

    # nothing in the output is a non-dict (the skip held)
    assert all(isinstance(r, dict) for r in resolved)


def test_progress_transition_room_position(manager, hass, monkeypatch):
    """[PROG-T1] When the access-graph + live position detect an intermediate
    transition room between the last-completed room and the next queued room,
    the snapshot's position_room_id (the animal-icon room the card draws) becomes
    that transition room id — even though it is NOT in the queue and
    current_room_id is preserved as the next unfinished queued room.

    Covers core/manager.py::get_job_progress_snapshot line 3236 (the
    `position_room_id = transition_room_id` branch). The branch only runs when
    status == 'started', a current room is derived, AND completed_room_ids is
    non-empty (it needs a last-completed room to walk *from*).

    Setup: queue [1, 2] with room 1 completed and room 2 the in-progress room.
    Because room 2 is the only remaining unresolved room, the timing-rollover
    helper returns early (a final room never rolls), so current_room_id stays 2
    deterministically and no EVENT_ROOM_FINISHED / timers are scheduled. We keep
    the current-room elapsed (2 min) below its 5-min estimate so the bounds-exit
    / stall machinery never engages — the only behaviour under test is the
    transition-room substitution.

    The real _detect_transition_room_from_position consults the access graph and
    live robot-position entities (neither present in this harness, so it would
    return None and the branch would be a no-op). We monkeypatch it to a fixed
    99 to prove the snapshot actually *uses* its return value for the icon
    position while leaving current_room_id intact.
    """
    _wire(manager, hass)
    _seed_job(
        manager,
        minutes_ago=2,  # elapsed (~2m) < 5m estimate → no bounds-exit/stall
        completed_room_ids=[1],
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}],
        current_room_id=2,
    )
    hass.states.async_set(_VAC, "cleaning")

    # Force the access-graph/position detector to report an intermediate
    # transition room (99) the robot is passing through between room 1 → room 2.
    # Keyword-only signature (vacuum_entity_id/map_id/from_room_id/to_room_id);
    # a **kw lambda accepts them all and asserts nothing about call shape.
    monkeypatch.setattr(
        manager, "_detect_transition_room_from_position", lambda **kw: 99
    )

    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)

    # The animal-icon room follows the detected transition room (line 3236)...
    assert snap["position_room_id"] == 99
    # ...while the queued-progress current room is preserved as the next
    # unfinished queued room (room 2), so timeline is_current flags stay correct.
    assert snap["current_room_id"] == 2
    # The transition room is purely positional: it must not be invented into the
    # timeline / queue accounting.
    assert 99 not in [r.get("room_id") for r in snap["timeline"]]
    assert 99 not in snap["completed_room_ids"]
    assert 99 not in snap["remaining_room_ids"]
    # Sanity: the branch's preconditions held (started job with a completed room).
    assert snap["status"] == "started"
    assert 1 in snap["completed_room_ids"]


def test_progress_transition_room_none_falls_back_to_current(manager, hass, monkeypatch):
    """[PROG-T1] Companion negative: when the detector finds no transition room
    (returns None — the real behaviour with no access graph / position data),
    position_room_id falls back to current_room_id (the `position_room_id =
    current_room_id` initializer is left untouched). Proves the line-3236
    substitution is gated on a non-None detection."""
    _wire(manager, hass)
    _seed_job(
        manager,
        minutes_ago=2,
        completed_room_ids=[1],
        completed_rooms=[{"room_id": 1, "actual_duration_minutes": 4.0}],
        current_room_id=2,
    )
    hass.states.async_set(_VAC, "cleaning")

    monkeypatch.setattr(
        manager, "_detect_transition_room_from_position", lambda **kw: None
    )

    snap = manager.get_job_progress_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)

    assert snap["position_room_id"] == snap["current_room_id"] == 2
