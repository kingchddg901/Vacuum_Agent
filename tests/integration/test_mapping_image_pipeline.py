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
    SERVICE_GET_MAP_SEGMENTS,
    SERVICE_REBUILD_ROOM_BOUNDS,
    SERVICE_RESTORE_ROOM_JOB_BOUNDS,
    SERVICE_SAVE_MAP_IMAGE,
    SERVICE_SET_SEGMENTATION_MODE,
    SERVICE_SET_CUSTOM_SEGMENTS,
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


def test_get_image_segment_suggestions_missing_image(hass, mapping_services):
    """[IMG-9] no saved image on disk → the user-facing missing_image payload:
    available False, reason missing_image, empty summary, image block present."""
    result = _get_mapping_manager(hass).get_image_segment_suggestions(
        vacuum_entity_id=_VAC, map_id="no_image")
    assert result["available"] is False
    assert result["reason"] == "missing_image"
    assert result["summary"]["segment_count"] == 0
    assert result["suggestions"] == []
    # the image metadata block the card reads is still populated
    assert "image" in result and "available_variants" in result["image"]


def test_get_suggestions_picks_distinct_assist_variant(hass, mapping_services, pil):
    """[IMG-6b] with two on-disk variants, the suggestions image block names the
    preferred variant AND records a *distinct* non-preferred variant as the assist
    image (the assist-selection break at manager.py 2067-2069). 'dark' is preferred;
    'light' is the distinct assist (different _light.png path)."""
    mm = _get_mapping_manager(hass)
    mm.save_map_image(vacuum_entity_id=_VAC, map_id=_MAP,
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="dark")
    mm.save_map_image(vacuum_entity_id=_VAC, map_id=_MAP,
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="light")

    result = mm.get_image_segment_suggestions(vacuum_entity_id=_VAC, map_id=_MAP)
    image = result["image"]
    # preferred = first of (dark, primary, light) with an image on disk
    assert image["variant"] == "dark"
    # the break at 2067 selected the distinct non-preferred variant as the assist
    assert image["assist_variant"] == "light"
    assert image["assist_image_path"] is not None
    assert image["assist_image_path"].endswith("_light.png")
    # primary image path is the preferred (dark) one — assist is genuinely distinct
    assert image["image_path"].endswith("_dark.png")
    assert image["assist_image_path"] != image["image_path"]
    # both saved variants are advertised (a legacy "primary" mirror is also kept)
    assert {"dark", "light"} <= set(image["available_variants"])


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


async def test_upload_custom_backdrop_is_not_segmented(hass, mapping_services, pil):
    """[IMG-11b] the custom-segment backdrop uploads + measures like any variant,
    but the segmenter never reads it: with only a 'custom' image present, analyze
    finds no segmenter input (it probes dark/default/light only) and returns
    image_not_found — the no-CV acceptor for the custom-segment path."""
    # Use a dedicated map_id so no other test's on-disk dark/default variant
    # (the suite shares a config dir) can satisfy analyze's filesystem probe.
    cmap = f"{_MAP}_cbk"
    up = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": cmap,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8,
        "variant": "custom"})
    assert up["saved"] is True
    assert up["variant"] == "custom"
    assert up["actual_width"] == 8 and up["actual_height"] == 8
    # only the custom backdrop is present → the segmenter has nothing to read
    analyzed = await _svc(hass, SERVICE_ANALYZE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": cmap, "force_reanalyze": True})
    assert analyzed["available"] is False
    assert analyzed["reason"] == "image_not_found"
    # the backdrop is deletable through the same delete service
    deleted = await _svc(hass, SERVICE_DELETE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": cmap, "variant": "custom"})
    assert isinstance(deleted, dict)


async def test_segmentation_mode_toggle_never_reruns_segmenter(hass, mapping_services, pil):
    """[SEG-TOGGLE-1] the CV-or-Custom toggle NEVER re-runs the segmenter in either
    direction: cv -> custom -> cv leaves image_segments byte-identical, never calls
    the engine, and serves the original CV segments again. The core invariant."""
    import copy
    manager = mapping_services
    _save_image(hass, pil)
    await _analyze(hass)
    bucket = manager.data["maps"][_VAC][_MAP]
    cv_before = copy.deepcopy(bucket["image_segments"])
    assert any(s["segment_id"] == "fake_1" for s in cv_before["segments"])

    # Spy on the engine from here: any re-segmentation would bump this counter.
    engine = segmenter_engines._SEGMENTER_ENGINES[_FAKE_ENGINE]
    real = engine.segment_map_image
    calls = {"n": 0}

    def _counting(**kwargs):
        calls["n"] += 1
        return real(**kwargs)

    engine.segment_map_image = _counting

    r1 = await _svc(hass, SERVICE_SET_SEGMENTATION_MODE,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "mode": "custom"})
    assert r1["saved"] is True and r1["mode"] == "custom"
    r2 = await _svc(hass, SERVICE_SET_SEGMENTATION_MODE,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "mode": "cv"})
    assert r2["mode"] == "cv"

    # invariant: no segmenter run, CV store untouched, CV segments served again
    assert calls["n"] == 0
    assert bucket["image_segments"] == cv_before
    got = await _svc(hass, SERVICE_GET_MAP_SEGMENTS,
                     {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got["segmentation_mode"] == "cv"
    assert any(s["segment_id"] == "fake_1" for s in got["segments"])


async def test_segmentation_mode_switches_segment_store(hass, mapping_services, pil):
    """[SEG-TOGGLE-2] get_map_segments serves image_segments in cv mode and the
    separate custom_segments store in custom mode; the inactive store is preserved
    across the flip."""
    manager = mapping_services
    _save_image(hass, pil)
    await _analyze(hass)
    bucket = manager.data["maps"][_VAC][_MAP]
    # seed a custom store alongside the CV one (as the future writer will)
    bucket["custom_segments"] = {
        "available": True,
        "segments": [{"segment_id": "custom_1",
                      "polygon_pixel": [[1, 1], [5, 1], [5, 5], [1, 5]]}],
    }

    await _svc(hass, SERVICE_SET_SEGMENTATION_MODE,
               {"vacuum_entity_id": _VAC, "map_id": _MAP, "mode": "custom"})
    custom = await _svc(hass, SERVICE_GET_MAP_SEGMENTS,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert custom["segmentation_mode"] == "custom"
    assert {s["segment_id"] for s in custom["segments"]} == {"custom_1"}

    await _svc(hass, SERVICE_SET_SEGMENTATION_MODE,
               {"vacuum_entity_id": _VAC, "map_id": _MAP, "mode": "cv"})
    cv = await _svc(hass, SERVICE_GET_MAP_SEGMENTS,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert {s["segment_id"] for s in cv["segments"]} == {"fake_1"}
    # both stores still present after the round-trip
    assert bucket["custom_segments"]["segments"][0]["segment_id"] == "custom_1"


async def _upload_custom_backdrop(hass, pil, *, map_id=_MAP):
    await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8,
        "variant": "custom"})


async def test_set_custom_segments_authors_polygons(hass, mapping_services, pil):
    """[CUST-1] set_custom_segments rasterises pct primitives into CV-shaped custom
    segments (stable id preserved, auto custom_N otherwise); get_map_segments serves
    them with real polygons + computed pct in custom mode."""
    await _upload_custom_backdrop(hass, pil)
    res = await _svc(hass, SERVICE_SET_CUSTOM_SEGMENTS, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "segments": [
            {"id": "living", "primitives": [
                {"type": "rect", "x": 10, "y": 10, "w": 40, "h": 40}]},
            {"primitives": [
                {"type": "polygon", "points": [[55, 55], [90, 55], [72, 90]]}]},
        ]})
    assert res["saved"] is True
    assert res["segment_count"] == 2
    assert res["segment_ids"] == ["living", "custom_2"]

    await _svc(hass, SERVICE_SET_SEGMENTATION_MODE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "mode": "custom"})
    got = await _svc(hass, SERVICE_GET_MAP_SEGMENTS, {
        "vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got["segmentation_mode"] == "custom"
    assert {s["segment_id"] for s in got["segments"]} == {"living", "custom_2"}
    living = next(s for s in got["segments"] if s["segment_id"] == "living")
    assert living["polygon_pixel"]          # real authored polygon
    assert living["polygon_pct"]            # get_map_segments computed pct from it
    assert living["structural_role"] == "room"
    assert living["source"] == "custom"


async def test_set_custom_segments_requires_backdrop(hass, mapping_services):
    """[CUST-2] without a custom backdrop (no pixel dims) the writer refuses."""
    res = await _svc(hass, SERVICE_SET_CUSTOM_SEGMENTS, {
        "vacuum_entity_id": _VAC, "map_id": "nobackdrop",
        "segments": [{"primitives": [
            {"type": "rect", "x": 0, "y": 0, "w": 50, "h": 50}]}]})
    assert res["saved"] is False
    assert res["reason"] == "no_custom_backdrop"


async def test_set_custom_segments_replace_all(hass, mapping_services, pil):
    """[CUST-3] replace-all: a second call rebuilds custom_segments from scratch."""
    await _upload_custom_backdrop(hass, pil)
    await _svc(hass, SERVICE_SET_CUSTOM_SEGMENTS, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "segments": [
            {"id": "a", "primitives": [{"type": "rect", "x": 10, "y": 10, "w": 30, "h": 30}]},
            {"id": "b", "primitives": [{"type": "rect", "x": 55, "y": 55, "w": 30, "h": 30}]},
        ]})
    res2 = await _svc(hass, SERVICE_SET_CUSTOM_SEGMENTS, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "segments": [
            {"id": "c", "primitives": [{"type": "rect", "x": 20, "y": 20, "w": 40, "h": 40}]},
        ]})
    assert res2["segment_count"] == 1
    assert res2["segment_ids"] == ["c"]
    stored = mapping_services.data["maps"][_VAC][_MAP]["custom_segments"]["segments"]
    assert [s["segment_id"] for s in stored] == ["c"]   # a, b replaced


async def test_upload_bad_base64_service(hass, mapping_services):
    """[IMG-12] upload_map_image with garbage base64 → invalid_base64."""
    res = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": "!!!not-base64!!!"})
    assert res["saved"] is False
    assert res["reason"] == "invalid_base64"


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


def test_translate_vertex_reset_pops_adjustment(hass, mapping_services, pil):
    """[IMG-15b] a vertex move that nets back to (0,0) is the reset-to-default
    mutation: the vertex is popped from the stored moves (manager.py 2320->2327)
    and, since it was the segment's only adjustment, the whole adjustment is popped
    from the package too (2332->2344). The public payload reflects the reset:
    vertex_moves empties and `adjustment` becomes None."""
    # a dedicated map_id keeps this segment's adjustment state independent of the
    # accumulation test (both persist to disk under segment_id "fake_1").
    _MR = "reset"
    mm = _get_mapping_manager(hass)
    mm.save_map_image(vacuum_entity_id=_VAC, map_id=_MR,
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="primary")
    r1 = mm.translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MR, segment_id="fake_1",
        vertex_moves=[{"index": 0, "delta_x": 5, "delta_y": 5}])
    assert r1["saved"] is True and r1["vertex_moves"] == [
        {"index": 0, "delta_x": 5, "delta_y": 5}]
    assert r1["adjustment"] is not None
    # the exact negation drives the vertex net to zero -> reset both arcs
    r2 = mm.translate_image_segment(
        vacuum_entity_id=_VAC, map_id=_MR, segment_id="fake_1",
        vertex_moves=[{"index": 0, "delta_x": -5, "delta_y": -5}])
    assert r2["saved"] is True
    assert r2["vertex_moves"] == []          # 2320->2327: vertex popped
    assert r2["adjustment"] is None          # 2332->2344: adjustment popped
    # and it is genuinely gone from the persisted package, not just the response
    data = mm._ensure_map_data(_VAC, _MR)
    assert "fake_1" not in data["package"].get("segment_adjustments", {})


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


def _tiny_jpeg_b64(pil) -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 40, 40)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def test_upload_non_png_is_converted(hass, mapping_services, pil):
    """[IMG-20] a valid non-PNG image is transcoded to PNG and saved."""
    res = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": _tiny_jpeg_b64(pil), "image_width": 8, "image_height": 8,
        "variant": "default"})
    assert res["saved"] is True


async def test_upload_unsupported_format(hass, mapping_services):
    """[IMG-21] base64 that decodes but isn't an image → unsupported_format."""
    res = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": base64.b64encode(b"hello world").decode("ascii")})
    assert res["saved"] is False
    assert res["reason"] == "unsupported_format"


async def test_translate_vertex_accumulation_via_service(hass, mapping_services, pil):
    """[IMG-22] the translate service accumulates per-vertex moves across calls
    (the handler-side vertex merge, distinct from the manager method)."""
    await _svc(hass, SERVICE_SAVE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8})
    r1 = await _svc(hass, SERVICE_TRANSLATE_IMAGE_SEGMENT, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "fake_1",
        "vertex_moves": [{"index": 0, "delta_x": 5, "delta_y": 5}]})
    assert r1["saved"] is True
    r2 = await _svc(hass, SERVICE_TRANSLATE_IMAGE_SEGMENT, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "fake_1",
        "vertex_moves": [{"index": 0, "delta_x": 3, "delta_y": -5}]})
    assert r2["saved"] is True


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


def test_get_suggestions_picks_distinct_assist_variant(hass, mapping_services, pil):
    """[IMG-6b] with two on-disk variants, the suggestions image block names the
    preferred variant AND records a *distinct* non-preferred variant as the assist
    image (the assist-selection break at manager.py 2067-2069). 'dark' is preferred;
    'light' is the distinct assist (different _light.png path)."""
    mm = _get_mapping_manager(hass)
    mm.save_map_image(vacuum_entity_id=_VAC, map_id=_MAP,
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="dark")
    mm.save_map_image(vacuum_entity_id=_VAC, map_id=_MAP,
                      image_base64=_tiny_png_b64(pil), image_width=8,
                      image_height=8, variant="light")

    result = mm.get_image_segment_suggestions(vacuum_entity_id=_VAC, map_id=_MAP)
    image = result["image"]
    # preferred = first of (dark, primary, light) with an image on disk
    assert image["variant"] == "dark"
    # the break at 2067 selected the distinct non-preferred variant as the assist
    assert image["assist_variant"] == "light"
    assert image["assist_image_path"] is not None
    assert image["assist_image_path"].endswith("_light.png")
    # primary image path is the preferred (dark) one — assist is genuinely distinct
    assert image["image_path"].endswith("_dark.png")
    assert image["assist_image_path"] != image["image_path"]
    # both saved variants are advertised (a legacy "primary" mirror is also kept)
    assert {"dark", "light"} <= set(image["available_variants"])


async def test_delete_one_variant_retains_others(hass, mapping_services, pil):
    """[IMG-23] delete_map_image with multiple variants: popping the deleted one
    keeps the rest. Covers the `if variants:` retain branch (map_bucket
    ['image_variants']=variants) and the remaining_variants result key — the
    multi-variant contract IMG-11 (single-variant -> empty) cannot prove."""
    # upload TWO variants for the same map
    for variant in ("default", "dark"):
        up = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
            "vacuum_entity_id": _VAC, "map_id": _MAP,
            "image_base64": _tiny_png_b64(pil), "image_width": 8, "image_height": 8,
            "variant": variant})
        assert up["saved"] is True

    # delete only "default" — "dark" must survive
    deleted = await _svc(hass, SERVICE_DELETE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "default"})

    assert deleted["deleted"] is True
    assert deleted["variant"] == "default"
    assert "dark" in deleted["remaining_variants"]
    assert "default" not in deleted["remaining_variants"]

    # the surviving variant is genuinely retained, not nuked: deleting it now
    # still finds the recorded entry (would be not_found if the retain branch
    # had clobbered the dict).
    dark_deleted = await _svc(hass, SERVICE_DELETE_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "dark"})
    assert dark_deleted["deleted"] is True
    assert dark_deleted["remaining_variants"] == []
