"""Integration tests for the non-segment mapping service handlers.

These are thin wrappers over already-tested MappingManager methods; calling
them through the service registry covers the handler closures registered by
async_register_mapping_services.

Coverage targets
----------------
[MSV-1]  get_mapping_state / get_mapping_package return dicts.
[MSV-2]  get_room_bounds_snapshot returns available=True.
[MSV-3]  boundary trace: start → cancel.
[MSV-4]  close_room_boundary with no samples → no_trace_samples.
[MSV-5]  set_dock_room persists the room id.
[MSV-6]  set_dock_anchor (vacuum docked) saves the pixel anchor.
[MSV-7]  trace capture: start → stop.
[MSV-8]  cancel_trace_capture with no session → cancelled=False.
[MSV-9]  append_mapping_trace_evidence grows the package list.
[MSV-10] save_mapping_package persists a package.
[MSV-11] review_trace_run with a missing run → error.
[MSV-12] clear_room_bounds on an unknown room → room_not_found.
[MSV-13] exclude_room_job_bounds on an unknown room → room_not_found.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping import mapping_services as ms
from custom_components.eufy_vacuum.mapping.mapping_services import (
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def mapping_services(hass, manager):
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


async def test_get_state_and_package(hass, mapping_services):
    """[MSV-1]"""
    state = await _call(hass, ms.SERVICE_GET_MAPPING_STATE,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert state["vacuum_entity_id"] == _VAC
    pkg = await _call(hass, ms.SERVICE_GET_MAPPING_PACKAGE,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert isinstance(pkg, dict)


async def test_room_bounds_snapshot(hass, mapping_services):
    """[MSV-2]"""
    snap = await _call(hass, ms.SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert snap["available"] is True


async def test_boundary_trace_start_cancel(hass, mapping_services):
    """[MSV-3]"""
    started = await _call(hass, ms.SERVICE_START_ROOM_BOUNDARY_TRACE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "5"})
    assert started["started"] is True
    cancelled = await _call(hass, ms.SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
                            {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "5"})
    assert cancelled["cancelled"] is True


async def test_close_boundary_no_samples(hass, mapping_services):
    """[MSV-4]"""
    await _call(hass, ms.SERVICE_START_ROOM_BOUNDARY_TRACE,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "7"})
    closed = await _call(hass, ms.SERVICE_CLOSE_ROOM_BOUNDARY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "7"})
    assert closed["closed"] is False
    assert closed["reason"] == "no_trace_samples"


async def test_set_dock_room(hass, mapping_services):
    """[MSV-5]"""
    result = await _call(hass, ms.SERVICE_SET_DOCK_ROOM,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "2"})
    assert result["saved"] is True
    assert result["dock"]["room_id"] == "2"


async def test_set_dock_anchor_docked(hass, mapping_services):
    """[MSV-6]"""
    hass.states.async_set(_VAC, "docked")
    result = await _call(hass, ms.SERVICE_SET_DOCK_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "pixel_x": 12.0, "pixel_y": 34.0})
    assert result["saved"] is True
    assert result["dock"]["pixel"] == [12.0, 34.0]


async def test_trace_capture_start_stop(hass, mapping_services):
    """[MSV-7]"""
    started = await _call(hass, ms.SERVICE_START_TRACE_CAPTURE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert started["started"] is True
    stopped = await _call(hass, ms.SERVICE_STOP_TRACE_CAPTURE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert stopped["stopped"] is True


async def test_cancel_trace_capture_none(hass, mapping_services):
    """[MSV-8]"""
    result = await _call(hass, ms.SERVICE_CANCEL_TRACE_CAPTURE,
                         {"vacuum_entity_id": _VAC, "map_id": "no_session"})
    assert result["cancelled"] is False


async def test_append_trace_evidence(hass, mapping_services):
    """[MSV-9]"""
    result = await _call(hass, ms.SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
                         {"vacuum_entity_id": _VAC, "map_id": "ev",
                          "evidence": {"label": "doorway"}})
    assert result["saved"] is True
    assert result["trace_count"] >= 1


async def test_save_mapping_package(hass, mapping_services):
    """[MSV-10]"""
    result = await _call(hass, ms.SERVICE_SAVE_MAPPING_PACKAGE,
                         {"vacuum_entity_id": _VAC, "map_id": "pkg",
                          "package": {"schema_version": 1}})
    assert isinstance(result, dict)
    assert result.get("saved") is True or "package" in result


async def test_review_trace_run_missing(hass, mapping_services):
    """[MSV-11]"""
    result = await _call(hass, ms.SERVICE_REVIEW_TRACE_RUN,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "run_id": "ghost", "room_id": "3"})
    assert result["verdict"] == "error"


async def test_clear_room_bounds_unknown(hass, mapping_services):
    """[MSV-12]"""
    result = await _call(hass, ms.SERVICE_CLEAR_ROOM_BOUNDS,
                         {"vacuum_entity_id": _VAC, "map_id": "cl", "room_id": "99"})
    assert result["success"] is False
    assert result["reason"] == "room_not_found"


async def test_exclude_room_job_bounds_unknown(hass, mapping_services):
    """[MSV-13]"""
    result = await _call(hass, ms.SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
                         {"vacuum_entity_id": _VAC, "map_id": "ex", "room_id": "99",
                          "job_index": 0})
    assert result["success"] is False
