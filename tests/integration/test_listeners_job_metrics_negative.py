"""Negative-path tests for the job_metrics listener (HA event weirdness).

Target: custom_components/eufy_vacuum/listeners/job_metrics.py

The watched-sensor handler ``_handle_metrics_change`` pushes the last-seen
cleaning_time / cleaning_area / station-water value into the in-flight active
job so finalization reads from there instead of a live state read. It has a
chain of early-return guards before it touches the manager:

    1. entry is None            (state change for an unwatched entity)
    2. new_state_obj is None    (entity removed -> new_state=None event)
    3. raw in (unavailable / unknown / None)
    4. manager_local is None    (DATA_RUNTIME vanished mid-flight)
    5. int()/float() conversion raises (TypeError/ValueError)

Each guard must early-return WITHOUT raising and WITHOUT recording anything
into the active job. These tests drive the handler closure directly with
crafted Event objects so each guard can be hit in isolation, and assert the
real no-op: no key written to the active-job dict, and
record_active_job_sensor_value / record_counter_sample are never called.

Coverage targets
----------------
[JMN-1] unwatched entity_id   -> entry is None        -> no-op
[JMN-2] new_state is None     -> guard 2              -> no-op
[JMN-3] raw == "unavailable"  -> guard 3              -> no-op
[JMN-4] raw == "unknown"      -> guard 3              -> no-op
[JMN-5] raw is None (state)   -> guard 3              -> no-op
[JMN-6] manager (DATA_RUNTIME) gone -> guard 4        -> no-op
[JMN-7] non-numeric raw       -> float() ValueError   -> no-op
[JMN-8] sanity: a real numeric value DOES record      -> positive control
"""

from __future__ import annotations

import pytest

from homeassistant.core import Event, State

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.listeners import job_metrics


_VAC = "vacuum.alfred"
_MAP = "1"

_CLEANING_TIME_ENTITY = "sensor.alfred_cleaning_time"
_CLEANING_AREA_ENTITY = "sensor.alfred_cleaning_area"

_ADAPTER_WITH_METRICS = {
    "adapter_id": "test_metrics",
    "source": "test",
    "entities": {
        "cleaning_time": _CLEANING_TIME_ENTITY,
        "cleaning_area": _CLEANING_AREA_ENTITY,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_active_job(manager) -> dict:
    """Seed one in-flight (started, not ended) active job and return its dict.

    record_active_job_sensor_value only writes into jobs that have a
    started_at and no ended_at, so the positive control needs this to be a
    *recordable* job. The negative paths must leave it untouched.
    """
    job = {
        "status": "started",
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "started_at": "2026-06-21T00:00:00+00:00",
    }
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


def _capture_handler(hass, manager, monkeypatch):
    """Register job_metrics with the subscribe call stubbed, returning the
    handler closure so each guard can be driven directly with a crafted Event.

    Patching async_track_state_change_event (in the listener's namespace)
    grabs the @callback handler register() builds over the watch_map without
    actually wiring it into the state machine, so we control event.data
    byte-for-byte and can synthesize states the real machine won't emit
    (e.g. a None new_state, or a watched entity disappearing).
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_METRICS)

    captured: dict = {}

    def _fake_track(hass_arg, entity_ids, action):
        captured["entities"] = list(entity_ids)
        captured["handler"] = action
        return lambda: None

    monkeypatch.setattr(job_metrics, "async_track_state_change_event", _fake_track)
    job_metrics.register(hass)

    assert "handler" in captured, "register() did not build a watched handler"
    # cleaning_time is actually being watched -> guards are reachable
    assert _CLEANING_TIME_ENTITY in captured["entities"]
    return captured["handler"]


def _spy_recorders(manager, monkeypatch):
    """Replace the two manager record methods with call-recording spies."""
    calls = {"sensor": [], "counter": []}

    def _sensor(**kwargs):
        calls["sensor"].append(kwargs)
        return True

    def _counter(**kwargs):
        calls["counter"].append(kwargs)
        return True

    monkeypatch.setattr(manager, "record_active_job_sensor_value", _sensor)
    monkeypatch.setattr(manager, "record_counter_sample", _counter)
    return calls


def _event(entity_id, new_state):
    """A state_changed-shaped Event carrying entity_id + new_state."""
    return Event("state_changed", {"entity_id": entity_id, "new_state": new_state})


def _state(entity_id, value, attributes=None):
    return State(entity_id, value, attributes or {})


# ---------------------------------------------------------------------------
# [JMN-1] unwatched entity -> entry is None
# ---------------------------------------------------------------------------

async def test_unwatched_entity_id_is_noop(hass, manager, monkeypatch):
    """[JMN-1] A state change for an entity not in the watch_map early-returns
    (entry is None) without recording."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event("sensor.some_unrelated_thing", _state("sensor.some_unrelated_thing", "42")))

    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_time_seconds" not in job


async def test_missing_entity_id_key_is_noop(hass, manager, monkeypatch):
    """[JMN-1] An event with no entity_id at all -> "" -> entry is None -> no-op."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(Event("state_changed", {"new_state": _state(_CLEANING_TIME_ENTITY, "300")}))

    assert calls["sensor"] == []
    assert "last_cleaning_time_seconds" not in job


# ---------------------------------------------------------------------------
# [JMN-2] new_state is None -> guard 2
# ---------------------------------------------------------------------------

async def test_new_state_none_is_noop(hass, manager, monkeypatch):
    """[JMN-2] A watched entity being removed fires an event with new_state=None;
    the handler must early-return before touching new_state.state."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_TIME_ENTITY, None))

    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_time_seconds" not in job


# ---------------------------------------------------------------------------
# [JMN-3..5] raw in (unavailable / unknown / None) -> guard 3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["unavailable", "unknown"])
async def test_sentinel_raw_value_is_noop(hass, manager, monkeypatch, raw):
    """[JMN-3/4] An unavailable / unknown state string value early-returns
    without recording — no sentinel value reaches the job (guard 3)."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_TIME_ENTITY, _state(_CLEANING_TIME_ENTITY, raw)))

    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_time_seconds" not in job


async def test_state_value_literal_none_is_noop(hass, manager, monkeypatch):
    """[JMN-5] new_state present but .state is the literal None object — guard 3's
    ``raw in (..., None)`` must catch it before float() is attempted.

    A real HA State coerces None -> "unknown", so build a minimal stand-in whose
    .state attribute is literally None to exercise this exact branch.
    """
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    class _NoneState:
        state = None

    handler(_event(_CLEANING_TIME_ENTITY, _NoneState()))

    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_time_seconds" not in job


# ---------------------------------------------------------------------------
# [JMN-6] manager (DATA_RUNTIME) vanished mid-flight -> guard 4
# ---------------------------------------------------------------------------

async def test_manager_gone_is_noop(hass, manager, monkeypatch):
    """[JMN-6] If DATA_RUNTIME is cleared between subscription and callback (the
    manager torn down mid-run), the handler re-reads it as None and early-returns
    instead of dereferencing a missing manager."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    # Manager goes away after the listener was registered.
    hass.data[DOMAIN].pop(DATA_RUNTIME, None)

    # Valid numeric value -> only guard 4 (manager_local is None) can stop it.
    handler(_event(_CLEANING_TIME_ENTITY, _state(_CLEANING_TIME_ENTITY, "300")))

    # The spies are on the (now-detached) manager object; with DATA_RUNTIME gone
    # the handler resolves manager_local=None and never calls them.
    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_time_seconds" not in job


# ---------------------------------------------------------------------------
# [JMN-7] non-numeric raw -> float() raises ValueError -> guard 5
# ---------------------------------------------------------------------------

async def test_non_numeric_value_is_noop(hass, manager, monkeypatch):
    """[JMN-7] A non-numeric state value makes float(raw) raise ValueError; the
    handler swallows it and early-returns without recording a garbage value."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_TIME_ENTITY, _state(_CLEANING_TIME_ENTITY, "not-a-number")))

    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_time_seconds" not in job


async def test_non_numeric_area_value_is_noop(hass, manager, monkeypatch):
    """[JMN-7] Same guard on the cleaning_area (float) path: 'NaNish' garbage that
    float() rejects is dropped, not recorded."""
    handler = _capture_handler(hass, manager, monkeypatch)
    job = _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_AREA_ENTITY, _state(_CLEANING_AREA_ENTITY, "twelve")))

    assert calls["sensor"] == []
    assert calls["counter"] == []
    assert "last_cleaning_area_m2" not in job


# ---------------------------------------------------------------------------
# [JMN-8] positive control — a real numeric value DOES record
# ---------------------------------------------------------------------------

async def test_valid_value_records_positive_control(hass, manager, monkeypatch):
    """[JMN-8] Sanity: with all guards satisfied, a real numeric cleaning_time
    value is recorded (sensor value + counter sample). Proves the negative-path
    no-ops above are guard behavior, not a dead/never-firing handler."""
    handler = _capture_handler(hass, manager, monkeypatch)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_TIME_ENTITY, _state(_CLEANING_TIME_ENTITY, "300")))

    assert len(calls["sensor"]) == 1
    assert calls["sensor"][0]["vacuum_entity_id"] == _VAC
    assert calls["sensor"][0]["key"] == "last_cleaning_time_seconds"
    assert calls["sensor"][0]["value"] == 300  # duration defaults to seconds
    # cleaning_time changes also append a counter sample
    assert len(calls["counter"]) == 1
    assert calls["counter"][0]["vacuum_entity_id"] == _VAC


async def test_duration_unit_minutes_records_seconds(hass, manager, monkeypatch):
    """Roborock exposes cleaning_time as a HA duration sensor in minutes; the
    active job stores the canonical seconds value used by learning."""
    handler = _capture_handler(hass, manager, monkeypatch)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(
        _CLEANING_TIME_ENTITY,
        _state(_CLEANING_TIME_ENTITY, "6.15", {"unit_of_measurement": "min"}),
    ))

    assert calls["sensor"][0]["key"] == "last_cleaning_time_seconds"
    assert calls["sensor"][0]["value"] == 369
