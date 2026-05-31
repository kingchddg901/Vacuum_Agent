"""Integration tests for the brand-agnostic image-segmentation wiring.

These cover the framework's segment plumbing (save_map_image,
analyze_map_image, get_image_segment_suggestions, translate_image_segment)
**without** coupling to any brand's CV implementation: a fake segmenter engine
is registered like any adapter's engine and returns a canned SegmentationResult.
This proves the framework drives *any* adapter's CV pipeline.

The real Eufy CV segmentor (detect_room_segments / HSV masks) is tested
separately in tests/adapters/eufy/test_segmentor.py.

Coverage targets
----------------
[IMG-1]  save_map_image: valid base64 PNG is written.
[IMG-2]  save_map_image: invalid base64 → invalid_base64 reason.
[IMG-3]  analyze_map_image: no image on disk → image_not_found.
[IMG-4]  analyze_map_image: drives the (fake) engine and returns its segments.
[IMG-5]  analyze_map_image: a second call returns the cached result.
[IMG-6]  get_image_segment_suggestions: returns the fake engine's segments.
[IMG-7]  translate_image_segment: missing segment_id → reason.
[IMG-8]  translate_image_segment: persists offsets for a real (fake) segment.
"""

from __future__ import annotations

import base64
import io

import pytest

from custom_components.eufy_vacuum.const import DOMAIN, SERVICE_ANALYZE_MAP_IMAGE
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.mapping import segmenter_engines
from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping.mapping_services import (
    _get_mapping_manager,
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"
_FAKE_ENGINE = "test_fake"


class _FakeSegmenter:
    """A brand-neutral segmenter engine — returns one canned segment.

    Mirrors the MapSegmenter protocol; ignores the image entirely so the test
    is deterministic and independent of any brand's pixel heuristics.
    """

    engine_name = _FAKE_ENGINE

    def validate_tuning(self, tuning):
        return []

    def segment_map_image(self, *, image_path, tuning, context=None):
        return {
            "available": True,
            "reason": "ready",
            "message": "",
            "engine": self.engine_name,
            "image": {"width": 100, "height": 100},
            "segments": [{
                "segment_id": "fake_1",
                "polygon_pixel": [[10, 10], [40, 10], [40, 40], [10, 40]],
                "bbox": {"x": 10, "y": 10, "width": 30, "height": 30},
                "area_pixels": 900,
                "area_percent": 9.0,
                "center_pixel": [25.0, 25.0],
                "confidence": 0.9,
                "quality": "good",
                "structural_role": "room",
                "segmentation_state": "clean",
                "edit_readiness": "ready",
                "matched_room_id": None,
                "matched_room_label": None,
                "issues": [],
            }],
            "summary": {"segment_count": 1, "quality_counts": {"good": 1},
                        "good_or_better_count": 1},
            "engine_diagnostics": {},
        }


@pytest.fixture
def pil():
    return pytest.importorskip("PIL")


def _tiny_png_b64(pil) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 40, 40)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture
async def mapping_services(hass, manager, monkeypatch):
    # Register the fake engine like any adapter's engine, and point the adapter
    # config at it — exercises the real engine-selection path, brand-neutrally.
    monkeypatch.setitem(segmenter_engines._SEGMENTER_ENGINES, _FAKE_ENGINE, _FakeSegmenter())
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "mapping": {"segmenter_engine": _FAKE_ENGINE, "segmenter_tuning": {}},
    })
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


def _save_image(hass, pil, *, variant="primary"):
    return _get_mapping_manager(hass).save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64=_tiny_png_b64(pil),
        image_width=8, image_height=8, variant=variant)


async def _analyze(hass, **overrides):
    data = {"vacuum_entity_id": _VAC, "map_id": _MAP, "force_reanalyze": True}
    data.update(overrides)
    return await hass.services.async_call(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE, data, blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# save_map_image
# ---------------------------------------------------------------------------

def test_save_map_image(hass, mapping_services, pil):
    """[IMG-1]"""
    assert _save_image(hass, pil)["saved"] is True


def test_save_map_image_bad_base64(hass, mapping_services):
    """[IMG-2]"""
    result = _get_mapping_manager(hass).save_map_image(
        vacuum_entity_id=_VAC, map_id=_MAP, image_base64="!!!not-base64!!!")
    assert result["saved"] is False
    assert "invalid_base64" in result["reason"]


# ---------------------------------------------------------------------------
# analyze_map_image
# ---------------------------------------------------------------------------

async def test_analyze_image_not_found(hass, mapping_services):
    """[IMG-3]"""
    result = await hass.services.async_call(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE,
        {"vacuum_entity_id": _VAC, "map_id": "no_image", "force_reanalyze": True},
        blocking=True, return_response=True)
    assert result["available"] is False
    assert result["reason"] == "image_not_found"


async def test_analyze_runs_engine(hass, mapping_services, pil):
    """[IMG-4] the framework drives the (fake) engine and surfaces its segments."""
    _save_image(hass, pil)
    result = await _analyze(hass)
    assert result["available"] is True
    assert any(s["segment_id"] == "fake_1" for s in result["segments"])


async def test_analyze_caches(hass, mapping_services, pil):
    """[IMG-5]"""
    _save_image(hass, pil)
    await _analyze(hass)
    cached = await hass.services.async_call(
        DOMAIN, SERVICE_ANALYZE_MAP_IMAGE,
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "force_reanalyze": False},
        blocking=True, return_response=True)
    assert any(s["segment_id"] == "fake_1" for s in cached["segments"])


# ---------------------------------------------------------------------------
# manager-level methods
# ---------------------------------------------------------------------------

def test_get_image_segment_suggestions(hass, mapping_services, pil):
    """[IMG-6]"""
    _save_image(hass, pil)
    result = _get_mapping_manager(hass).get_image_segment_suggestions(
        vacuum_entity_id=_VAC, map_id=_MAP)
    seg_ids = {str(s.get("segment_id")) for s in result.get("suggestions", [])}
    assert "fake_1" in seg_ids


def test_translate_missing_id(hass, mapping_services):
    """[IMG-7]"""
    result = _get_mapping_manager(hass).translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MAP, segment_id="   ")
    assert result["saved"] is False
    assert result["reason"] == "missing_segment_id"


def test_translate_real_segment(hass, mapping_services, pil):
    """[IMG-8] translate a segment the engine actually produced (covers 2363-2436)."""
    _save_image(hass, pil)
    result = _get_mapping_manager(hass).translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MAP, segment_id="fake_1", delta_x=5, delta_y=-3)
    assert result["saved"] is True
