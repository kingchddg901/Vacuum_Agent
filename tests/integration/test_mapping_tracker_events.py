"""Integration tests for mapping/tracker.py — the job-lifecycle + position
event pipeline. Uses a real hass; the raw-position read
(which needs the full capability stack) is patched so the confidence and
room logic can be driven deterministically.

Coverage targets
----------------
[MTE-1]  register_vacuum populates listeners + confidence; idempotent; unregister clears.
[MTE-2]  unregister_all clears every vacuum.
[MTE-3]  start_job seeds active-job state and resets confidence.
[MTE-4]  pause_sampling / resume_sampling toggle the paused set.
[MTE-8]  a native-target room change past the confidence threshold fires eufy_vacuum_room_completed.
[MTE-9]  _get_raw_position reads capability/state; all None branches + numeric success.
[MTE-11] dock-drift log: docked+no-job readings logged with deltas; dup/non-docked skipped.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

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
    return MappingTracker(hass)


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


def test_pause_resume_sampling(tracker):
    """[MTE-4]"""
    tracker.pause_sampling(_VAC)
    assert _VAC in tracker._sampling_paused
    tracker.resume_sampling(_VAC)
    assert _VAC not in tracker._sampling_paused


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

async def test_room_completed_event(hass, tracker, monkeypatch):
    """[MTE-8] room_completed fires when the device's native current-room target
    moves from one job room to another (bounds-free — driven by the target signal
    + the confidence/dwell debounce)."""
    _register(tracker)

    events: list = []
    hass.bus.async_listen(EVENT_ROOM_COMPLETED, lambda e: events.append(e.data))

    # The device's native current-room signal, controllable per tick.
    target = {"name": "Kitchen"}
    monkeypatch.setattr(tracker, "_read_active_cleaning_target", lambda vac: target["name"])

    rooms = {
        "3": {"is_transition": False, "slug": "kitchen", "name": "Kitchen"},
        "4": {"is_transition": False, "slug": "hallway", "name": "Hallway"},
    }
    job = {"map_id": _MAP, "rooms": rooms}
    # Enter room 3 (Kitchen).
    tracker._update_confidence(_VAC, 10.0, 10.0, job)
    # Force high confidence + a real entry time so the room change fires the event.
    conf = tracker._confidence[_VAC]
    conf.confidence = 0.95
    conf.entered_at = utc_now() - timedelta(seconds=45)
    # Target moves to room 4 (Hallway) → fires room_completed for room 3.
    target["name"] = "Hallway"
    tracker._update_confidence(_VAC, 12.0, 12.0, job)
    await hass.async_block_till_done()

    assert any(d["room_id"] == "3" and d["room_name"] == "Kitchen" for d in events)


def test_detect_current_room_resolution(tracker, monkeypatch):
    """[MTE-8b] _detect_current_room resolves the native target NAME to a
    non-transition job room by slug/name, and HOLDS (None) on blank / sentinel /
    unmatched / transition-only."""
    rooms = {
        "3": {"is_transition": False, "slug": "kitchen", "name": "Kitchen"},
        "4": {"is_transition": False, "slug": "living_room", "name": "Living Room"},
        "9": {"is_transition": True, "slug": "hall", "name": "Hall"},
    }

    def _detect(name):
        monkeypatch.setattr(tracker, "_read_active_cleaning_target", lambda vac: name)
        return tracker._detect_current_room(_VAC, rooms)

    assert _detect("Kitchen") == "3"           # name match
    assert _detect("living_room") == "4"       # slug match
    assert _detect("Living Room") == "4"       # name match, case/space-insensitive
    assert _detect("Hall") is None             # transition-only room -> HOLD
    assert _detect("Garage") is None           # unmatched -> HOLD
    for blank in ("", "unknown", "unavailable", None):
        assert _detect(blank) is None          # blank / sentinel -> HOLD


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
