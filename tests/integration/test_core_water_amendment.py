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
"""

from __future__ import annotations

import json
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


def _amendment_adapter(*, dock_status="sensor.alfred_dock", water_level="sensor.alfred_water"):
    entities = {}
    if dock_status:
        entities["dock_status"] = dock_status
    if water_level:
        entities["water_level"] = water_level
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": entities,
        "post_job_wash_amendment": {
            "trigger_states": ["washing"],
            "commit_state": "drying",
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
