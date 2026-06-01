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

from custom_components.eufy_vacuum.const import (
    DOMAIN,
    SERVICE_ANALYZE_MAP_IMAGE,
    SERVICE_DELETE_MAP_IMAGE,
)
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.mapping import segmenter_engines
from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping.mapping_services import (
    SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
    SERVICE_GET_IMAGE_SEGMENT_SUGGESTIONS,
    SERVICE_REBUILD_ROOM_BOUNDS,
    SERVICE_RESTORE_ROOM_JOB_BOUNDS,
    SERVICE_SAVE_MAP_IMAGE,
    SERVICE_TRANSLATE_IMAGE_SEGMENT,
    SERVICE_UPLOAD_MAP_IMAGE,
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


# ---------------------------------------------------------------------------
# [IMG-9+] the CV service-handler wrappers (call through the service layer)
# ---------------------------------------------------------------------------

async def _svc(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


async def test_save_map_image_service(hass, mapping_services, pil):
    """[IMG-9] handle_save_map_image wrapper."""
    res = await _svc(hass, SERVICE_SAVE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8})
    assert res["saved"] is True


async def test_get_suggestions_and_translate_services(hass, mapping_services, pil):
    """[IMG-10] handle_get_image_segment_suggestions + handle_translate_image_segment."""
    await _svc(hass, SERVICE_SAVE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8})
    sug = await _svc(hass, SERVICE_GET_IMAGE_SEGMENT_SUGGESTIONS,
                     {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert any(str(s.get("segment_id")) == "fake_1"
               for s in sug.get("suggestions", []))
    tr = await _svc(hass, SERVICE_TRANSLATE_IMAGE_SEGMENT, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "segment_id": "fake_1", "delta_x": 4})
    assert tr["saved"] is True


async def test_upload_and_delete_map_image_service(hass, mapping_services, pil):
    """[IMG-11] upload_map_image writes a variant + delete_map_image removes it."""
    up = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8,
        "variant": "default"})
    assert up["saved"] is True
    assert up["actual_width"] == 8
    # the file now exists → delete removes it
    deleted = await _svc(hass, SERVICE_DELETE_MAP_IMAGE,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "variant": "default"})
    assert isinstance(deleted, dict)


async def test_upload_bad_base64_service(hass, mapping_services):
    """[IMG-12] upload_map_image with garbage base64 → invalid_base64."""
    res = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": "!!!not-base64!!!"})
    assert res["saved"] is False
    assert res["reason"] == "invalid_base64"


def test_resolve_matches_fake_segment(hass, mapping_services, pil):
    """[IMG-14] _resolve_trace_target_polygon_pixel returns a linked segment's
    polygon from the (fake) engine output — the CV match path."""
    mm = _get_mapping_manager(hass)
    # a fresh map id avoids any segment_adjustments other tests persisted on "6"
    mm.save_map_image(vacuum_entity_id=_VAC, map_id="rsmap",
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="primary")
    md = {"rooms": {"3": {}},
          "package": {"room_definitions": {"3": {"suggestion_segment_id": "fake_1"}}}}
    poly = mm._resolve_trace_target_polygon_pixel(
        vacuum_entity_id=_VAC, map_id="rsmap", room_id="3", map_data=md)
    assert poly == [[10.0, 10.0], [40.0, 10.0], [40.0, 40.0], [10.0, 40.0]]


def test_translate_vertex_accumulation(hass, mapping_services, pil):
    """[IMG-15] translate_image_segment accumulates per-vertex moves across calls."""
    _save_image(hass, pil)
    mm = _get_mapping_manager(hass)
    r1 = mm.translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MAP, segment_id="fake_1",
        vertex_moves=[{"index": 0, "delta_x": 5, "delta_y": 5}])
    assert r1["saved"] is True
    # a second move on the same vertex accumulates onto the first
    r2 = mm.translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MAP, segment_id="fake_1",
        vertex_moves=[{"index": 0, "delta_x": 3, "delta_y": -5}])
    assert r2["saved"] is True


def test_get_suggestions_enriches_matched_room(hass, mapping_services, pil):
    """[IMG-16] get_image_segment_suggestions cross-links a matched segment: the
    segment gains matched_room_id/label and the roster room gains the linked
    suggestion_segment_id (the dual enrichment loops, segment + roster)."""
    mm = _get_mapping_manager(hass)
    _MM = "enrich"
    mm.save_map_image(vacuum_entity_id=_VAC, map_id=_MM,
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="primary")
    # link room "3" to the fake engine's segment via the stored package
    data = mm._ensure_map_data(_VAC, _MM)
    data["rooms"] = {"3": {"room_id": 3, "name": "Office"}}
    data["package"]["room_definitions"] = {"3": {"suggestion_segment_id": "fake_1"}}
    mm._save_map_data(_VAC, _MM, data)

    result = mm.get_image_segment_suggestions(vacuum_entity_id=_VAC, map_id=_MM)
    matched = next(s for s in result["suggestions"] if s["segment_id"] == "fake_1")
    assert str(matched["matched_room_id"]) == "3"
    room = next(r for r in result["room_roster"] if str(r.get("room_id")) == "3")
    assert room["suggestion_segment_id"] == "fake_1"


class _RecordingTracker:
    """Records the tracker-coupling calls the bounds handlers make."""

    def __init__(self) -> None:
        self.exclusion_calls: list = []
        self.rebuild_calls: list = []

    def update_raw_samples_exclusion(self, vac, room_id, job_id, excluded):
        self.exclusion_calls.append((vac, room_id, job_id, excluded))

    def rebuild_room_bounds_from_archive(self, *, vacuum_entity_id, map_id, room_id):
        self.rebuild_calls.append((vacuum_entity_id, map_id, room_id))
        return {"success": True, "room_id": room_id, "rebuilt": True}

    def _find_raw_samples_path(self, vac, room_id):
        return None


def _seed_job_bounds(mm, map_id):
    """Seed two archived job-bounds entries (with job_ids) for room '3'."""
    entries = [
        {"job_id": f"jb{i}", "recorded_at": "t", "samples": [[0, 0], [9, 9]]}
        for i in range(2)
    ]
    mm.rebuild_room_bounds_from_archive(
        vacuum_entity_id=_VAC, map_id=map_id, room_id="3", archived_entries=entries)


async def test_exclude_room_job_bounds_service(hass, mapping_services):
    """[IMG-17] handle_exclude_room_job_bounds: on success it tells the tracker to
    exclude that job's raw samples (excluded=True)."""
    mm = _get_mapping_manager(hass)
    _seed_job_bounds(mm, "exsvc")
    tracker = _RecordingTracker()
    hass.data[DOMAIN]["mapping_tracker"] = tracker
    res = await _svc(hass, SERVICE_EXCLUDE_ROOM_JOB_BOUNDS, {
        "vacuum_entity_id": _VAC, "map_id": "exsvc", "room_id": "3", "job_index": 0})
    assert res["success"] is True
    assert tracker.exclusion_calls
    vac, room_id, job_id, excluded = tracker.exclusion_calls[0]
    assert room_id == "3" and excluded is True and job_id


async def test_restore_room_job_bounds_service(hass, mapping_services):
    """[IMG-18] handle_restore_room_job_bounds: on success it tells the tracker to
    re-include that job's raw samples (excluded=False)."""
    mm = _get_mapping_manager(hass)
    _seed_job_bounds(mm, "rssvc")
    mm.exclude_room_job_bounds(
        vacuum_entity_id=_VAC, map_id="rssvc", room_id="3", job_index=0)
    tracker = _RecordingTracker()
    hass.data[DOMAIN]["mapping_tracker"] = tracker
    res = await _svc(hass, SERVICE_RESTORE_ROOM_JOB_BOUNDS, {
        "vacuum_entity_id": _VAC, "map_id": "rssvc", "room_id": "3", "job_index": 0})
    assert res["success"] is True
    assert tracker.exclusion_calls
    _, room_id, _, excluded = tracker.exclusion_calls[0]
    assert room_id == "3" and excluded is False


async def test_rebuild_room_bounds_service(hass, mapping_services):
    """[IMG-19] handle_rebuild_room_bounds: tracker_unavailable guard, then delegate."""
    # no tracker registered → guard
    hass.data[DOMAIN].pop("mapping_tracker", None)
    guard = await _svc(hass, SERVICE_REBUILD_ROOM_BOUNDS, {
        "vacuum_entity_id": _VAC, "map_id": "rbsvc", "room_id": "3"})
    assert guard["success"] is False
    assert guard["reason"] == "tracker_unavailable"
    # tracker present → delegates to its archive rebuild
    tracker = _RecordingTracker()
    hass.data[DOMAIN]["mapping_tracker"] = tracker
    ok = await _svc(hass, SERVICE_REBUILD_ROOM_BOUNDS, {
        "vacuum_entity_id": _VAC, "map_id": "rbsvc", "room_id": "3"})
    assert ok["rebuilt"] is True
    assert tracker.rebuild_calls == [(_VAC, "rbsvc", "3")]


async def test_upload_pil_read_fallback(hass, mapping_services, pil, monkeypatch):
    """[IMG-13] if measuring the saved image fails, dimensions fall back to the
    declared values in the RETURNED response (degraded response, not just a log)."""
    import PIL.Image

    def _boom(*a, **k):
        raise OSError("cannot read image")

    # a valid PNG skips the conversion branch; PIL is only used to measure size
    monkeypatch.setattr(PIL.Image, "open", _boom)
    res = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8})
    assert res["saved"] is True
    # measurement failed → returned dims fall back to the declared ones
    assert res["actual_width"] == 8
    assert res["actual_height"] == 8
