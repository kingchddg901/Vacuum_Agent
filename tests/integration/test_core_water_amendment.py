"""Tests for core/water_amendment.py — post-job mop-wash water amendment.

register_post_job_water_amendment wires a short-lived dock_status watcher that
patches a completed job file once the dock finishes washing the mop pad. Tests
drive the watcher with live hass states + a real job file on disk and assert
the patched water actuals.

Coverage targets
----------------
[WA-1]  no dock_status entity declared → skip + release the job_id.
[WA-2]  idempotent on job_id — second registration is a no-op.
[WA-3]  wash trigger increments + commit-state writes corrected actuals.
[WA-4]  timeout with no observed wash → no write.
[WA-5]  RP-039/RF-16: the watch joins the entry's async_on_unload ledger — firing
        that callback (as HA's own teardown would on a mid-watch unload) cancels
        the listener + timeout, so a later wash+commit sequence writes nothing.
[WA-6]  an adapter that declares a dock entity but NO wash vocabulary releases the
        job_id and never watches. Distinct from [WA-1], which has no dock entity at
        all and is refused one guard earlier.
[WA-7]  an unreadable water reading at commit time still records the wash, with the
        percent-derived figures left None rather than guessed.
[WA-8]  two washes inside the debounce window count as ONE. Also covers the
        neither-trigger-nor-commit arm, via the intermediate state it needs anyway.
[WA-9]  a job file whose `water` block is absent or not an object is left alone, and
        the watch does not raise into its executor job.
"""

from __future__ import annotations

import json
import time
from datetime import timedelta

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.core.water_amendment import (
    register_post_job_water_amendment,
)


_VAC = "vacuum.alfred"


def _write_job(tmp_path, **water):
    """Write a minimal completed-job file with a water block; return its path."""
    job = {"job_id": "j1", "water": {
        "station_clean_water_percent": water.get("start_pct", 80.0),
        "dock_clean_tank_capacity_ml": water.get("capacity", 4000.0),
        "dock_wash_overhead_ml_per_cycle": water.get("overhead", 100.0),
        "estimated_total_dock_clean_water_used_ml": water.get("estimated", 300.0),
    }}
    path = tmp_path / "job_j1.json"
    path.write_text(json.dumps(job), encoding="utf-8")
    return path


def _amendment_adapter(
    *,
    dock_status="sensor.alfred_dock",
    water_level="sensor.alfred_water",
    trigger_states=("washing",),
    commit_state="drying",
):
    """The adapter config the watch reads. The VOCABULARY is parameterised because the
    module's whole point is that it is declared per brand rather than inherited from
    Eufy -- so "declared nothing" is a configuration a real adapter can ship, and
    [WA-6] needs to be able to express it."""
    entities = {}
    if dock_status:
        entities["dock_status"] = dock_status
    if water_level:
        entities["water_level"] = water_level
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": entities,
        "post_job_wash_amendment": {
            "trigger_states": list(trigger_states),
            "commit_state": commit_state,
        },
    })


async def test_no_dock_status_entity_skips(hass, tmp_path):
    """[WA-1]"""
    _amendment_adapter(dock_status=None)
    path = _write_job(tmp_path)
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j1", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
    )
    # job_id released so a later real registration can proceed
    jobs = hass.data.get(DOMAIN, {}).get("_water_amendment_jobs", set())
    assert "j1" not in jobs


async def test_idempotent_on_job_id(hass, tmp_path):
    """[WA-2]"""
    _amendment_adapter()
    path = _write_job(tmp_path)
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j2", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0)
    jobs = hass.data[DOMAIN]["_water_amendment_jobs"]
    assert "j2" in jobs
    # second registration short-circuits — set membership unchanged
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j2", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0)
    assert sum(1 for j in jobs if j == "j2") == 1
    # commit to cancel the pending 180s timeout timer (avoid lingering-timer teardown)
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()


async def test_wash_then_commit_writes_actuals(hass, tmp_path):
    """[WA-3] one wash cycle + drying commit → corrected water actuals on disk."""
    _amendment_adapter()
    path = _write_job(tmp_path, start_pct=80.0, capacity=4000.0,
                      overhead=100.0, estimated=300.0)
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j1", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
        debounce_seconds=0.0,
    )
    # dock washes, then the water tank reads lower, then dock dries (commit)
    hass.states.async_set("sensor.alfred_dock", "washing")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_water", "75")
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()

    job = json.loads(path.read_text(encoding="utf-8"))
    water = job["water"]
    assert water["water_amendment_reason"] == "post_job_wash"
    assert water["actual_mop_wash_count"] == 1
    assert water["actual_end_station_clean_water_percent"] == pytest.approx(75.0)
    # (80 - 75)/100 * 4000 = 200 ml total dock water
    assert water["actual_dock_water_used_ml"] == pytest.approx(200.0)
    # 1 wash cycle * 100 ml overhead
    assert water["actual_mop_wash_water_ml"] == pytest.approx(100.0)
    assert water["actual_floor_water_ml"] == pytest.approx(100.0)
    assert water["actual_tank_emptied"] is False


async def test_timeout_no_wash_no_write(hass, tmp_path):
    """[WA-4] timeout commit with zero observed washes leaves the file unpatched."""
    _amendment_adapter()
    path = _write_job(tmp_path)
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j1", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
        timeout_seconds=180)
    before = path.read_text(encoding="utf-8")
    # advance past the 180s timeout → _on_timeout → _commit("timeout") with
    # wash_count 0 short-circuits before writing
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()
    assert path.read_text(encoding="utf-8") == before


async def test_ledger_join_cancels_watch_on_entry_unload(hass, tmp_path, mock_config_entry):
    """[WA-5] The watch joins onto the entry's async_on_unload ledger (RP-003's
    pattern), so a mid-watch entry unload cancels it cleanly instead of leaving it
    running against a torn-down hass. Simulates HA's own teardown by popping and
    invoking the LIFO tail of the entry's on_unload list, then proves the watch is
    genuinely dead: a wash+commit sequence that would otherwise write actuals
    writes nothing."""
    mock_config_entry.add_to_hass(hass)
    _amendment_adapter()
    path = _write_job(tmp_path)
    before_count = len(mock_config_entry._on_unload or [])
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j5", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
        debounce_seconds=0.0,
    )
    assert len(mock_config_entry._on_unload or []) == before_count + 1, (
        "register_post_job_water_amendment did not join the entry's on_unload ledger"
    )

    # Simulate HA's own ConfigEntry._async_process_on_unload: pop + call LIFO.
    undo = mock_config_entry._on_unload.pop()
    result = undo()
    if result is not None:
        await result

    before_write = path.read_text(encoding="utf-8")
    hass.states.async_set("sensor.alfred_dock", "washing")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_water", "75")
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()
    assert path.read_text(encoding="utf-8") == before_write, (
        "watch fired after its entry-unload cancel — the ledger join is not working"
    )


async def test_wa6_a_dock_entity_without_a_wash_vocabulary_releases_the_job(hass, tmp_path):
    """[WA-6] Declaring the entity but not the states is a skip, one guard later than
    [WA-1]'s.

    The brand vocabulary is deliberately NOT inherited from Eufy, so an adapter that
    names a `dock_status` entity and declares no `trigger_states`/`commit_state` is a
    configuration a real brand can ship -- and the watch has nothing to listen for.

    WHY THE ASSERTION IS NOT THE SAME AS [WA-1]'S. Both end with the job_id released,
    so `"j6" not in jobs` alone cannot tell which guard answered. This adapter HAS the
    dock entity, which is what carries it past [WA-1]'s guard to this one; and the
    second half drives the dock through a full washing/drying sequence afterwards and
    requires the file to be untouched, which is what shows no listener was ever
    registered rather than merely that the id was released.
    """
    _amendment_adapter(trigger_states=[], commit_state="drying")
    path = _write_job(tmp_path)
    before = path.read_bytes()

    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j6", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
    )
    jobs = hass.data.get(DOMAIN, {}).get("_water_amendment_jobs", set())
    assert "j6" not in jobs

    hass.states.async_set("sensor.alfred_dock", "washing")
    hass.states.async_set("sensor.alfred_water", "75")
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()
    assert path.read_bytes() == before, "a watch was registered despite no vocabulary"


async def test_wa7_an_unreadable_water_reading_still_records_the_wash(hass, tmp_path):
    """[WA-7] The water sensor is a separate entity and can be junk at commit time.

    The wash count comes from counting dock transitions; the end percentage comes from
    reading another entity. Those fail independently, so an unparseable reading must
    not cost the observed wash -- the count is the fact we are sure of.

    THE NON-DEFAULT ASSERTIONS ARE THE LOAD-BEARING ONES. An unpatched file has no
    `water_amendment_reason` key and no `actual_mop_wash_count`, so asserting the
    percent-derived fields are None would pass against a file that was never written
    at all. The reason and the count of 1 are what establish the write happened; the
    Nones are the narrow claim.
    """
    _amendment_adapter()
    path = _write_job(tmp_path, start_pct=80.0, capacity=4000.0)
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j7", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
        debounce_seconds=0.0,
    )
    hass.states.async_set("sensor.alfred_dock", "washing")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_water", "n/a")      # neither a number nor unknown
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()

    water = json.loads(path.read_text(encoding="utf-8"))["water"]
    assert water["water_amendment_reason"] == "post_job_wash"
    assert water["actual_mop_wash_count"] == 1
    assert water["actual_end_station_clean_water_percent"] is None
    assert water["actual_dock_water_used_ml"] is None


async def test_wa8_two_washes_inside_the_debounce_window_count_as_one(hass, tmp_path, monkeypatch):
    """[WA-8] The debounce, and the only test that can see it.

    [WA-3] runs with `debounce_seconds=0.0` and one wash, so its count of 1 is 1 with
    or without the interval check -- the debounce is invisible to it. This drives TWO
    washing transitions inside an hour-long window and requires the count to stay 1;
    ablating the interval check gives 2.

    THE INTERMEDIATE `cleaning` STATE IS MACHINERY, NOT A SECOND CLAIM. HA does not
    fire a state_changed event when a state is re-set to the same value, so two
    washing transitions have to be separated by something else. It is also what covers
    the `elif new_state == _commit_state` false arm, which is why there is no separate
    test for that: a dedicated one would drive the same line with the same input.

    THE CLOCK IS OFFSET, AND TWO EARLIER DRAFTS FAILED HERE -- both usefully. The
    comparison is `now - last_wash_at >= interval` with `last_wash_at` initialised to
    0.0, so whether the FIRST wash is counted depends on `time.monotonic()` exceeding
    the interval. Measured: inside this container it does NOT exceed 3600, so the
    hour-long window swallowed the first wash as well and the count came back 0 --
    not the 2 an absent debounce would give.

    The second draft replaced `time.monotonic` with a scripted iterator, which broke
    the EVENT LOOP: asyncio calls the same function, drained the iterator, and reported
    a task that "took 7764 seconds". So the patch is a constant OFFSET over the real
    clock instead. Every delta asyncio cares about is unchanged, while
    `now - 0.0` is unconditionally larger than any window -- which is exactly the
    property the first wash needs and the second wash must not have.

    WORTH RECORDING AS A LIVE EDGE, not merely a test fix: on a host whose monotonic
    clock has not yet passed `debounce_seconds`, the FIRST wash of a job is dropped,
    because 0.0 is used as a sentinel against a clock that does not start high. Narrow
    -- the shipped default debounce is small -- and reported rather than changed here.

    The water figure is asserted too, because 1 wash x 100 ml overhead is what
    distinguishes "counted once" from "counted once and then lost the reading".
    """
    monkeypatch.setattr(
        "time.monotonic", lambda _real=time.monotonic: _real() + 1_000_000.0
    )
    _amendment_adapter()
    path = _write_job(tmp_path, start_pct=80.0, capacity=4000.0, overhead=100.0)
    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j8", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
        debounce_seconds=3600.0,
    )
    hass.states.async_set("sensor.alfred_dock", "washing")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_dock", "cleaning")   # neither trigger nor commit
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_dock", "washing")    # inside the window
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_water", "75")
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()

    water = json.loads(path.read_text(encoding="utf-8"))["water"]
    assert water["actual_mop_wash_count"] == 1, "the debounce did not suppress the second wash"
    assert water["actual_mop_wash_water_ml"] == pytest.approx(100.0)


async def test_wa9_a_job_file_with_no_water_block_is_left_alone(hass, tmp_path):
    """[WA-9] The file on disk is not guaranteed to carry a `water` block.

    `_write_amendment` runs in an executor job created with `hass.async_create_task`,
    and the path is read at COMMIT time -- long after registration -- so the file's
    shape is whatever is actually there, not whatever was there when the job was
    registered.

    THE BYTES-UNCHANGED ASSERTION ALONE IS NOT ENOUGH, and that is the point: without
    the guard the crash happens BEFORE the write, so the file is unchanged either way.

    WHAT ACTUALLY DISCRIMINATES, measured by ablating the guard: the escaped
    AttributeError lands in a fire-and-forget task, HA's runner logs "Task exception was
    never retrieved", and pytest reports it as
    `ERROR ...::test_wa9_a_job_file_with_no_water_block_is_left_alone` at TEARDOWN. So
    this test does go red on the ablation -- as an ERROR rather than a FAILURE, against
    this test by name. `caplog` inside the body cannot see it, because the task is not
    reaped until the loop closes, which is after the test phase ends.

    That is a weaker detector than an assertion and it is worth saying so: it depends on
    HA's teardown verification continuing to surface unretrieved task exceptions. It is
    recorded here rather than papered over with an in-body assertion that would not
    actually fire.

    (The first ablation sweep called this test DEAD. The sweep was wrong: its matcher
    read only `FAILED` lines and this one reports as `ERROR`. Third time today a harness
    of mine answered about its own matcher rather than about the code.)
    """
    _amendment_adapter()
    path = tmp_path / "job_j9.json"
    path.write_text(json.dumps({"job_id": "j9"}), encoding="utf-8")   # no `water` key
    before = path.read_bytes()

    register_post_job_water_amendment(
        hass, vacuum_entity_id=_VAC, job_id="j9", job_path=str(path),
        water_start_percent=80.0, mop_wash_count_at_finalization=0,
        debounce_seconds=0.0,
    )
    hass.states.async_set("sensor.alfred_dock", "washing")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.alfred_water", "75")
    hass.states.async_set("sensor.alfred_dock", "drying")
    await hass.async_block_till_done()

    assert path.read_bytes() == before
