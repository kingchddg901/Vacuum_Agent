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
[JMN-9]  METRICS-3: an unrecognized duration unit still records (falls
         through to seconds) but logs a warning once per distinct unit.
[JMN-10] METRICS-4: an entities.water_level key alone is not enough --
         supports_station_water must also be True, or no watcher is wired.
[JMN-11] METRICS-4: a capability lookup failure during registration is
         logged, not silently swallowed, and does not break the rest of
         registration for that vacuum.
[JMN-12] the `ms` and hour alias families are CONVERTED, not assumed seconds
         (x1000 and x3600 respectively if either branch goes). The unit
         PRECEDENCE that keeps this honest is already pinned, in both
         directions, by `test_entity_unit_wins_over_adapter_fallback` and
         `test_adapter_unit_fallback_converts_bare_minutes` -- see the note
         where a duplicate of it was dropped.
[JMN-14] METRICS-4's other half: `supports_station_water` True with NEITHER
         entity declared must watch nothing, not `watch_map[None]`.
[JMN-15] a valid cleaning_area is normalised to m2 by the entity's unit; the
         ft2 row is what proves the unit was consulted at all.
[JMN-16] station water records through the `float` arm, not the `int` arm
         beside it -- which is why the reading is fractional.

⚠ `_duration_state_to_seconds` IS A THIRD COPY of replica set `RN2ZQ5NG`, which
declared two (`learning/job_finalizer.py` primary, `tests/replay/harvest.py`'s
factor table). Measured: identical alias families by AST and identical answers for
all 25 aliases and fallbacks either side knows -- consistent today, but nothing
pinned it, because `RPL-7` reads the PRIMARY's AST. `RPL-7d` now drives the union of
both functions' aliases through both. Do not retype the vocabulary here: a test that
spells the aliases out is a fourth copy that passes while its transcription matches
its author's belief.
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

# Roborock-shaped: cleaning_time reports bare MINUTES with no unit_of_measurement,
# so the adapter declares the fallback unit.
_ADAPTER_WITH_MIN_UNIT = {
    **_ADAPTER_WITH_METRICS,
    "cleaning_time_unit": "min",
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


def _register_capturing(
    hass, manager, monkeypatch, adapter_config=_ADAPTER_WITH_METRICS, caps=None
):
    """Register job_metrics with the subscribe call stubbed; return what it captured.

    Patching async_track_state_change_event (in the listener's namespace) grabs the
    @callback handler register() builds over the watch_map without actually wiring it
    into the state machine, so we control event.data byte-for-byte and can synthesize
    states the real machine won't emit (e.g. a None new_state, or a watched entity
    disappearing). The returned dict carries both the handler and the ENTITY LIST,
    because some claims are about what register() chose to watch rather than about
    what the handler does with an event.

    ``caps`` seeds the capability snapshot BEFORE register() reads it, which is the
    only way to reach the station-water branch. It is seeded after
    ensure_vacuum_record so that call cannot clobber it.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, adapter_config)
    if caps is not None:
        manager.data.setdefault("capabilities", {})[_VAC] = caps
        # PRECONDITION, not decoration: get_vacuum_capabilities(refresh=False) can
        # still rebuild the snapshot (a stored one with no detected_model while a
        # model resolves), and if it did, every assertion downstream would be
        # measuring the rebuilt dict rather than the seeded one.
        live = manager.get_vacuum_capabilities(vacuum_entity_id=_VAC, refresh=False)
        assert live.get("supports_station_water") == caps.get(
            "supports_station_water"
        ), "the seeded capability snapshot did not survive to register()"

    captured: dict = {}

    def _fake_track(hass_arg, entity_ids, action):
        captured["entities"] = list(entity_ids)
        captured["handler"] = action
        return lambda: None

    monkeypatch.setattr(job_metrics, "async_track_state_change_event", _fake_track)
    job_metrics.register(hass)
    return captured


def _capture_handler(hass, manager, monkeypatch, adapter_config=_ADAPTER_WITH_METRICS,
                     caps=None):
    """`_register_capturing`, narrowed to the handler closure most tests want."""
    captured = _register_capturing(hass, manager, monkeypatch, adapter_config, caps)

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
    """[JMN-3] [JMN-4] An unavailable / unknown state string value early-returns
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


async def test_adapter_unit_fallback_converts_bare_minutes(hass, manager, monkeypatch):
    """The REAL Roborock case: cleaning_time is a BARE number in minutes with NO
    unit_of_measurement. The adapter's cleaning_time_unit='min' is the fallback, so
    6.15 (minutes) is stored as 369 seconds — not mis-stored as ~6 seconds (60x low),
    which would skew learning + false-trip the idle-wall guard."""
    handler = _capture_handler(hass, manager, monkeypatch, _ADAPTER_WITH_MIN_UNIT)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_TIME_ENTITY, _state(_CLEANING_TIME_ENTITY, "6.15")))  # no unit

    assert calls["sensor"][0]["key"] == "last_cleaning_time_seconds"
    assert calls["sensor"][0]["value"] == 369


async def test_no_adapter_unit_keeps_seconds(hass, manager, monkeypatch):
    """Control: with no adapter cleaning_time_unit (e.g. Eufy) a bare number stays
    seconds — the fallback is opt-in, never a behavior change for other brands."""
    handler = _capture_handler(hass, manager, monkeypatch)  # default adapter, no unit hint
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(_CLEANING_TIME_ENTITY, _state(_CLEANING_TIME_ENTITY, "300")))

    assert calls["sensor"][0]["value"] == 300


async def test_entity_unit_wins_over_adapter_fallback(hass, manager, monkeypatch):
    """The entity's own unit_of_measurement still wins over the adapter fallback, so
    a brand that DOES publish a unit is unaffected."""
    handler = _capture_handler(hass, manager, monkeypatch, _ADAPTER_WITH_MIN_UNIT)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(
        _CLEANING_TIME_ENTITY,
        _state(_CLEANING_TIME_ENTITY, "300", {"unit_of_measurement": "s"}),
    ))

    assert calls["sensor"][0]["value"] == 300  # seconds, not 300*60


# ---------------------------------------------------------------------------
# [JMN-9] METRICS-3 — unrecognized duration unit logs a warning (once)
# ---------------------------------------------------------------------------

async def test_unrecognized_duration_unit_logs_warning_once(
    hass, manager, monkeypatch, caplog
):
    """[JMN-9] An unrecognized unit still records (falls through to "assume
    seconds") but must log a warning — once per distinct unit value, not once
    per event."""
    from custom_components.eufy_vacuum.listeners import job_metrics as jm

    monkeypatch.setattr(jm, "_WARNED_UNKNOWN_DURATION_UNITS", set())
    handler = _capture_handler(hass, manager, monkeypatch)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    with caplog.at_level("WARNING"):
        handler(_event(
            _CLEANING_TIME_ENTITY,
            _state(_CLEANING_TIME_ENTITY, "300", {"unit_of_measurement": "fortnight"}),
        ))
        handler(_event(
            _CLEANING_TIME_ENTITY,
            _state(_CLEANING_TIME_ENTITY, "301", {"unit_of_measurement": "fortnight"}),
        ))

    # Still recorded as seconds -- the warning doesn't block the fallback.
    assert calls["sensor"][-1]["value"] == 301
    warnings = [r for r in caplog.records if "fortnight" in r.message]
    assert len(warnings) == 1, "must warn once per distinct unit, not once per event"


async def test_recognized_seconds_alias_does_not_warn(hass, manager, monkeypatch, caplog):
    """[JMN-9] Control: a recognized "seconds" alias unit falls through to the
    same bare-value read WITHOUT logging — the warning is for genuinely
    unrecognized units only."""
    from custom_components.eufy_vacuum.listeners import job_metrics as jm

    monkeypatch.setattr(jm, "_WARNED_UNKNOWN_DURATION_UNITS", set())
    handler = _capture_handler(hass, manager, monkeypatch)
    _seed_active_job(manager)
    _spy_recorders(manager, monkeypatch)

    with caplog.at_level("WARNING"):
        handler(_event(
            _CLEANING_TIME_ENTITY,
            _state(_CLEANING_TIME_ENTITY, "300", {"unit_of_measurement": "seconds"}),
        ))

    # Only asserting on job_metrics's OWN warning -- adapter registration logs
    # its own (unrelated) warnings for undeclared mapping/job_segmenter/
    # room_attribution blocks on this minimal test adapter.
    assert not [r for r in caplog.records if r.name.endswith("listeners.job_metrics")]


# ---------------------------------------------------------------------------
# [JMN-12] / [JMN-13] the ms and hour duration families
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,unit,expected_seconds", [
    ("300000", "ms", 300),
    ("300000", "milliseconds", 300),
    ("1800000", "millisecond", 1800),
    ("0.5", "h", 1800),
    ("2", "hr", 7200),
    ("1", "hours", 3600),
])
async def test_jmn12_the_ms_and_hour_families_are_converted_not_assumed_seconds(
    hass, manager, monkeypatch, caplog, raw, unit, expected_seconds
):
    """[JMN-12] Two families of `_duration_state_to_seconds` had no test at all.

    [JMN-9] covers an UNRECOGNISED unit and the minutes family is covered through
    the adapter hint, but `ms` and the hour aliases were only reachable through
    branches nothing drove. What that costs if either branch goes: the unit falls to
    the "assume seconds" fall-through, so a 300000 ms reading is stored as 300000
    seconds instead of 300 — out by x1000 — and a 0.5 h reading as 0 or 1 second
    instead of 1800, out by x3600. `last_cleaning_time_seconds` is what the learning
    pipeline's per-minute means are built on.

    THE EXPECTED VALUES ARE HAND-WRITTEN (300000/1000, 0.5*3600) rather than taken
    from the function, because computing them with `_duration_state_to_seconds`
    would be a shared oracle whose assertion could never fail.

    Both parametrized rows ALSO assert the absence of a warning, which is what
    separates "converted" from "fell through to seconds": the fall-through logs, and
    these units must not. The warn-once set is module-global, so it is reset —
    otherwise an earlier test's warning for the same unit would hide a new one.

    RED: delete the `ms` family and the first three rows return 300000; delete the
    hour family and the last three return 0, 2 and 1.
    """
    from custom_components.eufy_vacuum.listeners import job_metrics as jm

    monkeypatch.setattr(jm, "_WARNED_UNKNOWN_DURATION_UNITS", set())
    handler = _capture_handler(hass, manager, monkeypatch)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    with caplog.at_level("WARNING"):
        handler(_event(
            _CLEANING_TIME_ENTITY,
            _state(_CLEANING_TIME_ENTITY, raw, {"unit_of_measurement": unit}),
        ))

    assert calls["sensor"], "nothing was recorded at all"
    assert calls["sensor"][-1]["key"] == "last_cleaning_time_seconds"
    assert calls["sensor"][-1]["value"] == expected_seconds
    assert not [
        r for r in caplog.records
        if r.name.endswith("listeners.job_metrics") and "duration unit" in r.message
    ], f"{unit!r} is a recognised unit and must not warn"


# NO [JMN-13]. A draft added a unit-PRECEDENCE test here (entity `h` against an
# adapter declaring `min`) as the decoy for [JMN-12]. It was a duplicate, and the
# ablation is what said so: swapping the `or` operands reddened
# `test_entity_unit_wins_over_adapter_fallback` as well, which is a test that was
# already here. Between it and `test_adapter_unit_fallback_converts_bare_minutes`
# both directions of the precedence are pinned, so the draft was dropped under the
# one-place rule rather than kept as a near-twin. Worth recording because the
# duplicate looked load-bearing right up to the moment something else went red
# beside it.


# ---------------------------------------------------------------------------
# [JMN-14] declared support with no entity to watch
# ---------------------------------------------------------------------------

async def test_jmn14_station_water_support_without_an_entity_watches_nothing(
    hass, manager, monkeypatch
):
    """[JMN-14] METRICS-4's other half: `supports_station_water` and NO entity.

    [JMN-10] covers the reverse (an entity key without the capability flag). This
    is a snapshot that claims support while declaring neither `water_level` nor
    `station_water` — which a partial detection or an older build can write, so the
    shape is an outside input rather than something the type hints constrain.

    Without the `if water_entity:` guard, `watch_map[None]` is created and `None`
    goes into the list handed to `async_track_state_change_event`, where HA's own
    string-lowering helper raises on it — taking down registration for every
    vacuum, not just this one.

    The cleaning_time/area assertion is the positive control: "no None" alone is
    also satisfied by a register() that watched nothing whatsoever.

    RED: delete `if water_entity:` and None appears in the watched list.
    """
    captured = _register_capturing(
        hass, manager, monkeypatch,
        caps={"supports_station_water": True, "entities": {}},
    )

    assert "entities" in captured, "register() never reached the subscribe call"
    assert None not in captured["entities"], (
        "a claimed-but-undeclared water entity must not be watched as None"
    )
    assert _CLEANING_TIME_ENTITY in captured["entities"], "positive control"
    assert _CLEANING_AREA_ENTITY in captured["entities"], "positive control"


# ---------------------------------------------------------------------------
# [JMN-15] / [JMN-16] the value_type arms that record
# ---------------------------------------------------------------------------

async def test_jmn15_a_valid_cleaning_area_is_normalised_to_square_metres(
    hass, manager, monkeypatch
):
    """[JMN-15] Only the area REFUSAL arm was covered; the recording one was not.

    `cleaning_area_to_m2` normalises by the entity's own unit because an imperial HA
    presents Eufy's cleaning_area in ft² while Roborock's stays m², and
    `last_cleaning_area_m2` is the denominator of every per-m² learning mean — so a
    unit ignored here inflates those means by ~10.76x.

    ⚠ THE ft² ROW IS THE DISCRIMINATOR. A test that only sent a unitless value would
    pass against a handler that ignored units entirely, because unitless is the
    identity case. 100 ft² -> 9.290304 m² and 100 unitless -> 100.0 is the contrast.
    The factor is written as a literal rather than taken from `cleaning_area_to_m2`,
    for the shared-oracle reason.

    RED: drop the `value is None` return and a bad unit records None; drop the
    normalisation and the ft² row records 100.0.
    """
    handler = _capture_handler(hass, manager, monkeypatch)
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(
        _CLEANING_AREA_ENTITY,
        _state(_CLEANING_AREA_ENTITY, "100", {"unit_of_measurement": "ft²"}),
    ))
    assert calls["sensor"][-1]["key"] == "last_cleaning_area_m2"
    assert calls["sensor"][-1]["value"] == pytest.approx(100 * 0.09290304)

    handler(_event(
        _CLEANING_AREA_ENTITY,
        _state(_CLEANING_AREA_ENTITY, "100", {}),
    ))
    assert calls["sensor"][-1]["value"] == pytest.approx(100.0), (
        "unitless is already canonical -- and the contrast with ft² is what proves "
        "the unit was consulted"
    )


async def test_jmn16_station_water_records_as_a_float_not_an_int(
    hass, manager, monkeypatch
):
    """[JMN-16] The `float` value_type arm, which only station water uses.

    [JMN-10] asserts the water entity gets WATCHED; nothing drove a state through
    the handler, so the `else: value = float(raw)` arm never ran. The four arms are
    duration / area / int / float, and `int` (battery) is the one next to it — so
    42.5 is the input, because 42 would be recorded identically by both arms and the
    test could not tell which ran.

    RED: fold the `else` into the `int` arm and this records 42 instead of 42.5.
    """
    water_entity = "sensor.alfred_station_water"
    handler = _capture_handler(
        hass, manager, monkeypatch,
        caps={"supports_station_water": True,
              "entities": {"water_level": water_entity}},
    )
    _seed_active_job(manager)
    calls = _spy_recorders(manager, monkeypatch)

    handler(_event(water_entity, _state(water_entity, "42.5")))

    assert calls["sensor"], "the water entity was watched but its state recorded nothing"
    assert calls["sensor"][-1]["key"] == "last_station_water_percent"
    assert calls["sensor"][-1]["value"] == 42.5, (
        "a fractional reading distinguishes the float arm from the int arm beside it"
    )
    assert calls["counter"] == [], "water is not a counter key"


# ---------------------------------------------------------------------------
# [JMN-10] / [JMN-11] METRICS-4 — station-water capability gating
# ---------------------------------------------------------------------------

async def test_station_water_not_watched_without_capability(hass, manager, monkeypatch):
    """[JMN-10] An entities.water_level key present in the capability
    snapshot is not enough on its own — supports_station_water must also be
    True, or no watcher is wired (previously wired on the entity-key guess
    alone, with no capability check at all)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_METRICS)
    manager.data.setdefault("capabilities", {})[_VAC] = {
        "supports_station_water": False,
        "entities": {"water_level": "sensor.alfred_water"},
    }
    hass.states.async_set(_CLEANING_TIME_ENTITY, "0")
    hass.states.async_set("sensor.alfred_water", "50")
    await hass.async_block_till_done()

    captured: dict = {}

    def _fake_track(hass_arg, entity_ids, action):
        captured["entities"] = list(entity_ids)
        return lambda: None

    monkeypatch.setattr(job_metrics, "async_track_state_change_event", _fake_track)
    job_metrics.register(hass)

    assert "sensor.alfred_water" not in captured.get("entities", [])


async def test_station_water_watched_when_capability_declared(hass, manager, monkeypatch):
    """[JMN-10] With supports_station_water explicitly True in the stored
    capability snapshot, the declared water entity IS wired."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_METRICS)
    manager.data.setdefault("capabilities", {})[_VAC] = {
        "supports_station_water": True,
        "entities": {"water_level": "sensor.alfred_water"},
    }
    hass.states.async_set(_CLEANING_TIME_ENTITY, "0")
    hass.states.async_set("sensor.alfred_water", "50")
    await hass.async_block_till_done()

    captured: dict = {}

    def _fake_track(hass_arg, entity_ids, action):
        captured["entities"] = list(entity_ids)
        return lambda: None

    monkeypatch.setattr(job_metrics, "async_track_state_change_event", _fake_track)
    job_metrics.register(hass)

    assert "sensor.alfred_water" in captured.get("entities", [])


async def test_station_water_lookup_failure_logs_warning(
    hass, manager, monkeypatch, caplog
):
    """[JMN-11] A capability lookup failure during registration is logged,
    not silently swallowed — and does not break the rest of registration for
    that vacuum (cleaning_time is still watched)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _ADAPTER_WITH_METRICS)
    hass.states.async_set(_CLEANING_TIME_ENTITY, "0")
    await hass.async_block_till_done()

    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(manager, "get_vacuum_capabilities", _boom)

    captured: dict = {}

    def _fake_track(hass_arg, entity_ids, action):
        captured["entities"] = list(entity_ids)
        return lambda: None

    monkeypatch.setattr(job_metrics, "async_track_state_change_event", _fake_track)

    with caplog.at_level("WARNING"):
        job_metrics.register(hass)

    assert any("station-water" in r.message for r in caplog.records)
    assert _CLEANING_TIME_ENTITY in captured.get("entities", [])
