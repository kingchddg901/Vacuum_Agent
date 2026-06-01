"""Integration tests for mapping/mapping_services.py — async service handlers.

Mapping services register through their own async_register_mapping_services
(not the domain async_register_services), and read/write the per-map bucket on
the core manager (DATA_RUNTIME). All target services support_response=True.

Coverage targets
----------------
[MSH-1]  get_map_segments returns adjusted segments + polygon_pct + summary.
[MSH-2]  adjust_map_segment: unknown segment → segment_not_found.
[MSH-3]  adjust_map_segment: a delta is stored and reflected on next read.
[MSH-4]  set_segment_room_link: set injects room_id; the link dict updates.
[MSH-5]  set_segment_room_link: null room_id clears the link.
[MSH-6]  set_segment_room_link: 1:1 enforcement drops the older segment's link.
[MSH-7]  set_companion_anchor: set then clear.
[MSH-8]  delete_map_image: returns a well-formed dict when no image exists.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import (
    DOMAIN,
    SERVICE_ADJUST_MAP_SEGMENT,
    SERVICE_DELETE_MAP_IMAGE,
    SERVICE_GET_MAP_SEGMENTS,
    SERVICE_SET_COMPANION_ANCHOR,
    SERVICE_SET_SEGMENT_ROOM_LINK,
)
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
from custom_components.eufy_vacuum.mapping.mapping_services import (
    SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
    SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
    SERVICE_CANCEL_TRACE_CAPTURE,
    SERVICE_CLEAR_ROOM_BOUNDS,
    SERVICE_CLOSE_ROOM_BOUNDARY,
    SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
    SERVICE_GET_MAPPING_PACKAGE,
    SERVICE_GET_MAPPING_STATE,
    SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
    SERVICE_REVIEW_TRACE_RUN,
    SERVICE_SAVE_MAPPING_PACKAGE,
    SERVICE_SET_DOCK_ANCHOR,
    SERVICE_SET_DOCK_ROOM,
    SERVICE_START_ROOM_BOUNDARY_TRACE,
    SERVICE_START_TRACE_CAPTURE,
    SERVICE_STOP_TRACE_CAPTURE,
    async_register_mapping_services,
    async_unregister_mapping_services,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def mapping_services(hass, manager):
    from custom_components.eufy_vacuum.mapping.manager import MappingManager
    # the mapping-specific handlers resolve a dedicated MappingManager from
    # hass.data; async_setup_entry wires this in production.
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)
    hass.data[DOMAIN].pop("mapping_manager", None)


def _seed_segments(manager, *, segment_ids=("s1", "s2")) -> None:
    bucket = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket["image_segments"] = {
        "available": True,
        "analyzed_at": "2026-01-01T00:00:00+00:00",
        "image": {"width": 100, "height": 100},
        "segments": [
            {"segment_id": sid,
             "polygon_pixel": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "issues": []}
            for sid in segment_ids
        ],
        "summary": {"segment_count": len(segment_ids)},
    }
    bucket["image_variants"] = {"default": {"width": 100, "height": 100}}


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# get_map_segments
# ---------------------------------------------------------------------------

async def test_get_map_segments(hass, mapping_services):
    """[MSH-1]"""
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert result["available"] is True
    assert result["summary"]["segment_count"] == 2
    seg = result["segments"][0]
    assert "polygon_pct" in seg


# ---------------------------------------------------------------------------
# adjust_map_segment
# ---------------------------------------------------------------------------

async def test_adjust_segment_not_found(hass, mapping_services):
    """[MSH-2]"""
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "ghost"})
    assert result["saved"] is False
    assert result["reason"] == "segment_not_found"


async def test_adjust_segment_stores_delta(hass, mapping_services):
    """[MSH-3]"""
    _seed_segments(mapping_services)
    saved = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "segment_id": "s1", "delta_x": 5})
    assert saved["saved"] is True
    # reflected on the next read: the segment polygon is translated +5 in x
    segments = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP})
    s1 = next(s for s in segments["segments"] if s["segment_id"] == "s1")
    assert s1["polygon_pixel"][0][0] == 5
    assert "translated_manual" in s1["issues"]


# ---------------------------------------------------------------------------
# set_segment_room_link
# ---------------------------------------------------------------------------

async def test_link_set_injects_room(hass, mapping_services):
    """[MSH-4]"""
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "segment_id": "s1", "room_id": "3"})
    assert result["saved"] is True and result["action"] == "set"
    assert result["segment_room_links"]["s1"] == "3"
    segments = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP})
    s1 = next(s for s in segments["segments"] if s["segment_id"] == "s1")
    assert s1["room_id"] == "3"


async def test_link_clear(hass, mapping_services):
    """[MSH-5]"""
    _seed_segments(mapping_services)
    await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s1", "room_id": "3"})
    cleared = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP,
                           "segment_id": "s1", "room_id": None})
    assert cleared["action"] == "cleared"
    assert "s1" not in cleared["segment_room_links"]


async def test_link_one_to_one(hass, mapping_services):
    """[MSH-6] linking room 3 to s2 drops the existing s1→3 link."""
    _seed_segments(mapping_services)
    await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s1", "room_id": "3"})
    result = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s2", "room_id": "3"})
    links = result["segment_room_links"]
    assert links.get("s2") == "3"
    assert "s1" not in links


# ---------------------------------------------------------------------------
# set_companion_anchor
# ---------------------------------------------------------------------------

async def test_companion_anchor_set_and_clear(hass, mapping_services):
    """[MSH-7]"""
    _seed_segments(mapping_services)
    setres = await _call(hass, SERVICE_SET_COMPANION_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "room_id": "3", "pct_x": 25.0, "pct_y": 75.0})
    assert setres["action"] == "set"
    assert setres["companion_anchors"]["3"] == {"pct_x": 25.0, "pct_y": 75.0}
    clearres = await _call(hass, SERVICE_SET_COMPANION_ANCHOR,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "3"})
    assert clearres["action"] == "cleared"
    assert "3" not in clearres["companion_anchors"]


# ---------------------------------------------------------------------------
# delete_map_image
# ---------------------------------------------------------------------------

async def test_delete_map_image_no_image(hass, mapping_services):
    """[MSH-8]"""
    result = await _call(hass, SERVICE_DELETE_MAP_IMAGE,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "default"})
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [MSH-9+] non-CV data handlers (dock / bounds / trace capture / package)
# ---------------------------------------------------------------------------

async def test_mapping_state_and_package(hass, mapping_services):
    """[MSH-9] get_mapping_state / save+get package / append trace evidence."""
    state = await _call(hass, SERVICE_GET_MAPPING_STATE,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert state["vacuum_entity_id"] == _VAC
    saved = await _call(hass, SERVICE_SAVE_MAPPING_PACKAGE,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "package": {"rooms": {}}})
    assert saved["saved"] is True
    pkg = await _call(hass, SERVICE_GET_MAPPING_PACKAGE,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert isinstance(pkg, dict)
    ev = await _call(hass, SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
                     {"vacuum_entity_id": _VAC, "map_id": _MAP,
                      "evidence": {"label": "doorway"}})
    assert ev["saved"] is True


async def test_dock_anchor_and_room(hass, mapping_services):
    """[MSH-10] set_dock_anchor + set_dock_room."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    hass.states.async_set(_VAC, "docked")  # dock anchor requires docked state
    anchor = await _call(hass, SERVICE_SET_DOCK_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "pixel_x": 50, "pixel_y": 50})
    assert anchor["saved"] is True
    room = await _call(hass, SERVICE_SET_DOCK_ROOM,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert room["saved"] is True


async def test_trace_capture_cycle(hass, mapping_services):
    """[MSH-11] start → stop → cancel trace capture."""
    started = await _call(hass, SERVICE_START_TRACE_CAPTURE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert started["started"] is True
    stopped = await _call(hass, SERVICE_STOP_TRACE_CAPTURE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert isinstance(stopped, dict)
    # no active session now → cancel returns cancelled False
    cancelled = await _call(hass, SERVICE_CANCEL_TRACE_CAPTURE,
                            {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert cancelled["cancelled"] is False


async def test_room_boundary_trace(hass, mapping_services):
    """[MSH-12] start a room boundary trace, then cancel it; close with no trace."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    started = await _call(hass, SERVICE_START_ROOM_BOUNDARY_TRACE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert isinstance(started, dict)
    cancelled = await _call(hass, SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
                            {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert isinstance(cancelled, dict)
    closed = await _call(hass, SERVICE_CLOSE_ROOM_BOUNDARY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 2})
    assert closed.get("closed") is not True


async def test_bounds_snapshot_and_clear(hass, mapping_services):
    """[MSH-13] room bounds snapshot + clear + exclude/restore (no bounds → no-op)."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    snap = await _call(hass, SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert "rooms" in snap
    cleared = await _call(hass, SERVICE_CLEAR_ROOM_BOUNDS,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert isinstance(cleared, dict)
    excl = await _call(hass, SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP,
                        "room_id": 1, "job_index": 0})
    assert isinstance(excl, dict)


async def test_review_trace_run_missing(hass, mapping_services):
    """[MSH-14] review a non-existent run → error verdict (handler runs)."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    result = await _call(hass, SERVICE_REVIEW_TRACE_RUN,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "run_id": "ghost", "room_id": 1})
    assert isinstance(result, dict)
    assert "verdict" in result
