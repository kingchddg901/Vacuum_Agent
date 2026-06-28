"""Integration tests for mapping/tracker.py — the job-lifecycle + position
event pipeline. Uses a real hass + real MappingManager; the raw-position read
(which needs the full capability stack) is patched so the accumulation and
confidence logic can be driven deterministically.

Coverage targets
----------------
[MTE-1]  register_vacuum populates listeners + confidence; idempotent; unregister clears.
[MTE-2]  unregister_all clears every vacuum.
[MTE-3]  start_job seeds active-job state and resets confidence/samples.
[MTE-4]  pause_sampling / resume_sampling toggle the paused set.
[MTE-5]  _handle_position_update accumulates, dedups, and respects pause.
[MTE-6]  end_job writes accumulated samples into room bounds via the manager.
[MTE-7]  end_job archives raw samples for a single-room job.
[MTE-8]  confidence threshold + room exit fires eufy_vacuum_room_completed.
[MTE-9]  _get_raw_position reads capability/state; all None branches + numeric success.
[MTE-10] Wave 1 dock anchors: captured at start + end, stamped on history + archive.
[MTE-10b] dock anchor left None on a mid-job restart (recovered samples).
[MTE-11] dock-drift log: docked+no-job readings logged with deltas; dup/non-docked skipped.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping.tracker import (
    EVENT_ROOM_COMPLETED,
    MappingTracker,
)
from custom_components.eufy_vacuum.timestamp_utils import utc_now


_VAC = "vacuum.alfred"
_MAP = "6"
_ROOMS = {"3": {"is_transition": False, "slug": "kitchen", "name": "Kitchen"}}


@pytest.fixture
def tracker(hass) -> MappingTracker:
    return MappingTracker(hass, MappingManager(hass))


def _register(tracker) -> None:
    tracker.register_vacuum(
        vacuum_entity_id=_VAC,
        position_x_entity_id="sensor.alfred_x",
        position_y_entity_id="sensor.alfred_y",
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_unregister(tracker):
    """[MTE-1]"""
    _register(tracker)
    _register(tracker)  # idempotent
    assert _VAC in tracker._unsubs
    assert _VAC in tracker._confidence
    tracker.unregister_vacuum(_VAC)
    assert _VAC not in tracker._unsubs
    assert _VAC not in tracker._confidence


def test_unregister_all(tracker):
    """[MTE-2]"""
    _register(tracker)
    tracker.unregister_all()
    assert tracker._unsubs == {}


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

def test_start_job(tracker):
    """[MTE-3]"""
    _register(tracker)
    tracker._confidence[_VAC].current_room_id = "9"  # stale state
    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MAP, rooms=_ROOMS)
    assert tracker._active_job[_VAC]["map_id"] == _MAP
    assert tracker._confidence[_VAC].current_room_id is None
    assert tracker._samples_since_flush[_VAC] == 0


def test_pause_resume_sampling(tracker):
    """[MTE-4]"""
    tracker.pause_sampling(_VAC)
    assert _VAC in tracker._sampling_paused
    tracker.resume_sampling(_VAC)
    assert _VAC not in tracker._sampling_paused


def test_handle_position_update_accumulates(tracker):
    """[MTE-5]"""
    _register(tracker)
    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MAP, rooms=_ROOMS)

    tracker._get_raw_position = lambda vacuum_entity_id: (10.0, 10.0)
    tracker._handle_position_update(_VAC)
    tracker._handle_position_update(_VAC)  # identical → deduped
    assert tracker._job_samples[_VAC] == [(10.0, 10.0)]

    tracker._get_raw_position = lambda vacuum_entity_id: (20.0, 20.0)
    tracker._handle_position_update(_VAC)
    assert tracker._job_samples[_VAC] == [(10.0, 10.0), (20.0, 20.0)]

    # paused → no accumulation
    tracker.pause_sampling(_VAC)
    tracker._get_raw_position = lambda vacuum_entity_id: (30.0, 30.0)
    tracker._handle_position_update(_VAC)
    assert (30.0, 30.0) not in tracker._job_samples[_VAC]


async def test_handle_position_update_flushes_periodically(tracker, hass, monkeypatch):
    """[MTE-5b] every SAMPLES_FLUSH_INTERVAL samples the tracker flushes to disk so
    an HA restart mid-job can recover them (the periodic-flush branch)."""
    from custom_components.eufy_vacuum.mapping.tracker import SAMPLES_FLUSH_INTERVAL

    _register(tracker)
    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MAP, rooms=_ROOMS)
    flushed: list = []
    monkeypatch.setattr(tracker, "_flush_samples_to_disk",
                        lambda *a, **k: flushed.append(a))
    # distinct positions so none are deduped; the Nth append trips the flush
    for i in range(SAMPLES_FLUSH_INTERVAL):
        tracker._get_raw_position = lambda vacuum_entity_id, i=i: (float(i), float(i))
        tracker._handle_position_update(_VAC)
    await hass.async_block_till_done()
    assert flushed, "expected a periodic flush after SAMPLES_FLUSH_INTERVAL samples"


def test_end_job_writes_bounds(tracker):
    """[MTE-6] dedicated map id to keep the exact-bounds union isolated."""
    _register(tracker)
    tracker.start_job(vacuum_entity_id=_VAC, map_id="mte6bounds", rooms=_ROOMS)
    tracker._job_samples[_VAC] = [(0.0, 0.0), (10.0, 10.0), (20.0, 20.0)]
    tracker.end_job(vacuum_entity_id=_VAC)

    snap = tracker._manager.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id="mte6bounds")
    bounds = snap["rooms"]["3"]["bounds"]
    assert bounds["min_x"] == 0.0 and bounds["max_x"] == 20.0


def test_end_job_recovers_samples_from_disk(tracker, monkeypatch):
    """[MTE-6b] end_job with no in-memory samples (HA restarted mid-job) recovers
    the last disk-flushed samples and still writes room bounds from them."""
    _register(tracker)
    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MAP, rooms=_ROOMS)
    # simulate a restart: in-memory samples gone, but a flush file is on disk
    tracker._job_samples[_VAC] = []
    tracker._flush_samples_to_disk(_VAC, _MAP, _ROOMS, [(1.0, 1.0), (2.0, 2.0)])
    captured: dict = {}
    monkeypatch.setattr(tracker._manager, "update_room_bounds",
                        lambda **kw: captured.update(kw))
    tracker.end_job(vacuum_entity_id=_VAC)
    assert captured.get("samples") == [(1.0, 1.0), (2.0, 2.0)]


def test_end_job_archives_samples(tracker):
    """[MTE-7]"""
    _register(tracker)
    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MAP, rooms=_ROOMS)
    tracker._job_samples[_VAC] = [(0.0, 0.0), (10.0, 10.0)]
    tracker.end_job(vacuum_entity_id=_VAC)
    assert tracker._find_raw_samples_path(_VAC, "3") is not None


def test_dock_anchor_capture_start_and_end(tracker):
    """[MTE-10] Wave 1: a fresh start captures the dock anchor; end captures the
    re-dock position; both are stamped on the room's history entry AND the raw
    archive line (so cross-session re-anchoring has them later)."""
    import json

    _register(tracker)
    tracker._get_raw_position = lambda vacuum_entity_id: (15000.0, 4000.0)
    tracker.start_job(vacuum_entity_id=_VAC, map_id="mte10dock", rooms=_ROOMS)
    assert tracker._active_job[_VAC]["dock_anchor_start"] == [15000.0, 4000.0]

    tracker._job_samples[_VAC] = [(0.0, 0.0), (10.0, 10.0), (20.0, 20.0)]
    # re-dock at a drifted position
    tracker._get_raw_position = lambda vacuum_entity_id: (15050.0, 4250.0)
    tracker.end_job(vacuum_entity_id=_VAC)

    entry = (
        tracker._manager._load_map_data(_VAC, "mte10dock")
        ["rooms"]["3"]["job_bounds_history"][0]
    )
    assert entry["dock_anchor_start"] == [15000.0, 4000.0]
    assert entry["dock_anchor_end"] == [15050.0, 4250.0]

    path = tracker._find_raw_samples_path(_VAC, "3")
    last = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()][-1]
    rec = json.loads(last)
    assert rec["dock_anchor_start"] == [15000.0, 4000.0]
    assert rec["dock_anchor_end"] == [15050.0, 4250.0]


def test_dock_anchor_absent_on_restart_recovery(tracker):
    """[MTE-10b] On a mid-job HA restart, start_job recovers samples from disk and
    the live position is mid-run (not the dock) — so the start anchor is left None
    rather than recording a bogus anchor."""
    _register(tracker)
    tracker._flush_samples_to_disk(_VAC, "mte10b", _ROOMS, [(1.0, 1.0), (2.0, 2.0)])
    # would-be mid-run read; must be ignored because samples were recovered
    tracker._get_raw_position = lambda vacuum_entity_id: (999.0, 999.0)
    tracker.start_job(vacuum_entity_id=_VAC, map_id="mte10b", rooms=_ROOMS)
    assert tracker._active_job[_VAC]["dock_anchor_start"] is None


async def test_dock_drift_log(tracker, hass):
    """[MTE-11] With NO active job and the vacuum docked, each distinct position
    reading is logged to the dock-drift JSONL (with a delta); an unchanged reading
    and a non-docked state are both skipped."""
    import asyncio
    import json

    _register(tracker)
    hass.states.async_set(_VAC, "docked")  # docked, and start_job NOT called -> no job

    # The HA test config_dir is shared/persistent across runs, so start from a clean
    # slate — otherwise a leftover drift log makes the count assertion non-deterministic.
    # Drain first: a dock-drift append still in flight from a PRIOR test runs on the
    # executor, and if it lands AFTER our unlink it inflates the count (this test
    # passes in isolation but flaked in-suite without this barrier).
    await hass.async_block_till_done()
    drift_path = tracker._dock_drift_path(_VAC)
    if drift_path.exists():
        drift_path.unlink()

    tracker._get_raw_position = lambda vacuum_entity_id: (15000.0, 4000.0)
    tracker._handle_position_update(_VAC)            # first reading -> logged
    await hass.async_block_till_done()               # finish this append before the next
    tracker._handle_position_update(_VAC)            # unchanged -> skipped
    tracker._get_raw_position = lambda vacuum_entity_id: (15000.0, 4237.0)
    tracker._handle_position_update(_VAC)            # drift -> logged with dy=+237
    await hass.async_block_till_done()               # ordered after the first append

    # not docked: a change here must NOT be logged
    hass.states.async_set(_VAC, "cleaning")
    tracker._get_raw_position = lambda vacuum_entity_id: (15010.0, 4250.0)
    tracker._handle_position_update(_VAC)

    # The dock-drift appends run FIRE-AND-FORGET on the executor
    # (async_add_executor_job, deliberately not awaited — file I/O must not block
    # position updates), so async_block_till_done() does not reliably drain them.
    # Reading the file once was the historical flake (the 2nd append sometimes
    # hadn't flushed -> len 1). Poll until both expected records land, then settle.
    path = tracker._dock_drift_path(_VAC)

    def _drift_recs():
        if not path.exists():
            return []
        return [
            json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and '"_meta"' not in ln
        ]

    recs = _drift_recs()
    for _ in range(50):  # up to ~5s
        await hass.async_block_till_done()
        recs = _drift_recs()
        if len(recs) >= 2:
            break
        await asyncio.sleep(0.1)
    # Settle: give any (incorrectly logged) non-docked append a chance to surface,
    # so the len==2 "skipped" assertion below keeps its teeth.
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    recs = _drift_recs()

    assert len(recs) == 2  # first + the drift; dup and the cleaning-state read skipped
    assert (recs[0]["vx"], recs[0]["vy"]) == (15000.0, 4000.0)
    assert "dx" not in recs[0]                 # no delta on the first reading
    assert recs[1]["dy"] == 237.0              # drift delta captured


# ---------------------------------------------------------------------------
# Confidence + room_completed event
# ---------------------------------------------------------------------------

async def test_room_completed_event(hass, tracker):
    """[MTE-8]"""
    _register(tracker)
    # Give room 3 learned bounds so position (10,10) is detected inside it.
    tracker._manager.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(0.0, 0.0), (20.0, 20.0)], rooms={"3": {"is_transition": False}})

    events: list = []
    hass.bus.async_listen(EVENT_ROOM_COMPLETED, lambda e: events.append(e.data))

    job = {"map_id": _MAP, "rooms": _ROOMS}
    # Enter room 3.
    tracker._update_confidence(_VAC, 10.0, 10.0, job)
    # Force high confidence + a real entry time so the exit fires the event.
    conf = tracker._confidence[_VAC]
    conf.confidence = 0.95
    conf.entered_at = utc_now() - timedelta(seconds=45)
    # Leave the room (far outside bounds).
    tracker._update_confidence(_VAC, 5000.0, 5000.0, job)
    await hass.async_block_till_done()

    assert any(d["room_id"] == "3" and d["room_name"] == "Kitchen" for d in events)


# ---------------------------------------------------------------------------
# [MTE-9] _get_raw_position — capability/state read with all None branches
# ---------------------------------------------------------------------------

def _set_runtime(hass, caps, *, raises=False):
    rt = MagicMock()
    if raises:
        rt.get_vacuum_capabilities.side_effect = RuntimeError("boom")
    else:
        rt.get_vacuum_capabilities.return_value = caps
    hass.data.setdefault("eufy_vacuum", {})["runtime"] = rt
    return rt


_POS_CAPS = {"entities": {"robot_position_x": "sensor.alfred_x",
                          "robot_position_y": "sensor.alfred_y"}}


def test_get_raw_position_success(tracker, hass):
    """[MTE-9] numeric x/y states → (vx, vy)."""
    _set_runtime(hass, _POS_CAPS)
    hass.states.async_set("sensor.alfred_x", "1.5")
    hass.states.async_set("sensor.alfred_y", "2.5")
    assert tracker._get_raw_position(_VAC) == (1.5, 2.5)


def test_get_raw_position_no_runtime(tracker, hass):
    """[MTE-9] no runtime manager → None."""
    hass.data.setdefault("eufy_vacuum", {}).pop("runtime", None)
    assert tracker._get_raw_position(_VAC) is None


def test_get_raw_position_caps_raise(tracker, hass):
    """[MTE-9] get_vacuum_capabilities raising → None."""
    _set_runtime(hass, None, raises=True)
    assert tracker._get_raw_position(_VAC) is None


def test_get_raw_position_missing_entities(tracker, hass):
    """[MTE-9] caps without position entities → None."""
    _set_runtime(hass, {"entities": {}})
    assert tracker._get_raw_position(_VAC) is None


def test_get_raw_position_no_state(tracker, hass):
    """[MTE-9] declared entities but no states yet → None."""
    _set_runtime(hass, _POS_CAPS)
    assert tracker._get_raw_position(_VAC) is None


def test_get_raw_position_non_numeric(tracker, hass):
    """[MTE-9] non-numeric state → None."""
    _set_runtime(hass, _POS_CAPS)
    hass.states.async_set("sensor.alfred_x", "unknown")
    hass.states.async_set("sensor.alfred_y", "2.5")
    assert tracker._get_raw_position(_VAC) is None
