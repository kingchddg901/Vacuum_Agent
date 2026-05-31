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
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def mapping_services(hass, manager):
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


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
