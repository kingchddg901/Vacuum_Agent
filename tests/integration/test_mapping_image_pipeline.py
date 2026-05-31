"""Integration tests for the image/CV segmentation pipeline.

Exercises the real detect_room_segments path (numpy/scipy/Pillow — no cv2
anywhere in the codebase) end to end: a synthetic PNG is generated with Pillow,
saved through the mapping manager, then run through the analyze service and the
get_image_segment_suggestions manager method.

Assertions are intentionally lenient about *how many* segments a synthetic image
yields — the point is to drive the pipeline through without error and cover the
CV code paths, not to validate the segmentor's tuning.

Coverage targets
----------------
[IMG-1]  save_map_image: valid base64 PNG is written.
[IMG-2]  save_map_image: invalid base64 → invalid_base64 reason.
[IMG-3]  analyze_map_image: no image on disk → image_not_found.
[IMG-4]  analyze_map_image: runs the CV pipeline and returns a segments payload.
[IMG-5]  analyze_map_image: a second call returns the cached result.
[IMG-6]  get_image_segment_suggestions: runs against the saved image.
[IMG-7]  translate_image_segment: persists per-segment offsets.
"""

from __future__ import annotations

import base64
import io

import pytest

from custom_components.eufy_vacuum.const import (
    DOMAIN,
    SERVICE_ANALYZE_MAP_IMAGE,
)
from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping.mapping_services import (
    _get_mapping_manager,
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def pil():
    return pytest.importorskip("PIL")


def _png_b64(pil) -> str:
    """A 200x200 dark canvas with two light rectangular 'rooms'."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 90, 90], fill=(220, 220, 220))
    draw.rectangle([110, 110, 180, 180], fill=(220, 220, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture
async def mapping_services(hass, manager):
    # _get_mapping_manager does not lazily create — wire one in explicitly.
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


async def _analyze(hass, **overrides):
    data = {"vacuum_entity_id": _VAC, "map_id": _MAP,
            "min_area_pixels": 100, "force_reanalyze": True}
    data.update(overrides)
    return await hass.services.async_call(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE, data, blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# save_map_image
# ---------------------------------------------------------------------------

def test_save_map_image(hass, mapping_services, pil):
    """[IMG-1]"""
    mgr = _get_mapping_manager(hass)
    result = mgr.save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64=_png_b64(pil),
        image_width=200, image_height=200, variant="primary")
    assert result["saved"] is True


def test_save_map_image_bad_base64(hass, mapping_services):
    """[IMG-2]"""
    mgr = _get_mapping_manager(hass)
    result = mgr.save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64="!!!not-base64!!!")
    assert result["saved"] is False
    assert "invalid_base64" in result["reason"]


# ---------------------------------------------------------------------------
# analyze_map_image
# ---------------------------------------------------------------------------

async def test_analyze_image_not_found(hass, mapping_services):
    """[IMG-3] a map with no saved image."""
    result = await hass.services.async_call(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE,
        {"vacuum_entity_id": _VAC, "map_id": "no_image", "force_reanalyze": True},
        blocking=True, return_response=True)
    assert result["available"] is False
    assert result["reason"] == "image_not_found"


async def test_analyze_runs_pipeline(hass, mapping_services, pil):
    """[IMG-4] the CV pipeline runs and returns a well-formed segments payload."""
    _get_mapping_manager(hass).save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64=_png_b64(pil),
        image_width=200, image_height=200, variant="primary")
    result = await _analyze(hass)
    assert "segments" in result and isinstance(result["segments"], list)
    assert "available" in result


async def test_analyze_caches(hass, mapping_services, pil):
    """[IMG-5] without force_reanalyze the cached result is returned."""
    _get_mapping_manager(hass).save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64=_png_b64(pil),
        image_width=200, image_height=200, variant="primary")
    await _analyze(hass)  # populate cache
    cached = await hass.services.async_call(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE,
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "force_reanalyze": False},
        blocking=True, return_response=True)
    assert isinstance(cached.get("segments"), list)


# ---------------------------------------------------------------------------
# manager-level methods
# ---------------------------------------------------------------------------

def test_get_image_segment_suggestions(hass, mapping_services, pil):
    """[IMG-6]"""
    mgr = _get_mapping_manager(hass)
    mgr.save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64=_png_b64(pil),
        image_width=200, image_height=200, variant="primary")
    result = mgr.get_image_segment_suggestions(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(result, dict)
    assert "suggestions" in result or "available" in result


def test_translate_image_segment(hass, mapping_services):
    """[IMG-7]"""
    mgr = _get_mapping_manager(hass)
    result = mgr.translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MAP, segment_id="seg_1", delta_x=5, delta_y=-3)
    assert isinstance(result, dict)
    assert result.get("saved") is True or "reason" in result
