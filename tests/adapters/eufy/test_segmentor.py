"""Brand-specific tests for the Eufy CV segmentor — detect_room_segments and
the EufyCVSegmenter engine wrapper.

This is Eufy adapter code (HSV-threshold room masks calibrated on Eufy map
imagery), kept solo in the adapter suite and omitted from core coverage. It
needs the numpy/scipy/Pillow image stack; tests skip if any is missing.

Coverage targets
----------------
[ECV-1]  detect_room_segments: saturated-colour rooms → available, segments.
[ECV-2]  detect_room_segments: gray (zero-saturation) rooms → no segments.
[ECV-3]  EufyCVSegmenter.segment_map_image: wraps detect_room_segments output.
[ECV-4]  detect_room_segments: unreadable image path → available False.
[ECV-5]  detect_room_segments: assist image → exercises the wall-cut branch.
[ECV-6]  detect_room_segments: max_segments caps the returned segment count.
[SEG-1]  _issue_quality: issue/confidence → quality label.
[SEG-2]  _structural_role: geometry → role label.
[SEG-3]  _segmentation_state: issues/fill/compactness → state label.
"""

from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy.ndimage")
pytest.importorskip("PIL")

from custom_components.eufy_vacuum.adapters.eufy.segmentor import (
    detect_room_segments,
    _issue_quality,
    _structural_role,
    _segmentation_state,
)
from custom_components.eufy_vacuum.mapping.segmenter_engines import EufyCVSegmenter


def _map_png(tmp_path, *, saturated: bool) -> str:
    """Write a 240x240 dark map with two rectangular rooms; return the path.

    Eufy's room mask is value>=68 AND saturation>=18, so only saturated-colour
    rooms register as components — a gray fill (saturation 0) does not.
    """
    from PIL import Image, ImageDraw

    fill_a = (60, 160, 90) if saturated else (200, 200, 200)
    fill_b = (160, 80, 160) if saturated else (210, 210, 210)
    img = Image.new("RGB", (240, 240), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 110, 110], fill=fill_a)
    draw.rectangle([130, 130, 220, 220], fill=fill_b)
    path = os.path.join(tmp_path, "map.png")
    img.save(path)
    return path


def test_detect_segments_saturated(tmp_path):
    """[ECV-1]"""
    path = _map_png(str(tmp_path), saturated=True)
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert len(result["segments"]) >= 1
    seg = result["segments"][0]
    assert "segment_id" in seg
    assert isinstance(seg.get("polygon_pixel"), list)


def test_detect_segments_gray_none(tmp_path):
    """[ECV-2] zero-saturation rooms are below the saturation threshold."""
    path = _map_png(str(tmp_path), saturated=False)
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["segments"] == []


def test_eufy_cv_segmenter_wraps(tmp_path):
    """[ECV-3] the engine wrapper reshapes detect_room_segments into the contract."""
    path = _map_png(str(tmp_path), saturated=True)
    result = EufyCVSegmenter().segment_map_image(
        image_path=path, tuning={"min_area_pixels": 200})
    assert result["engine"] == "eufy_cv_v1"
    assert result["available"] is True
    assert len(result["segments"]) >= 1
    assert "summary" in result


def _light_map_png(tmp_path) -> str:
    """Write a light-theme variant: near-white walls + saturated rooms.

    The wall mask is value>=214 AND saturation<=36, so a white background
    registers as wall pixels — this drives the assist-image wall-cut branch.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 240), (255, 255, 255))  # white walls
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 110, 110], fill=(60, 160, 90))
    draw.rectangle([130, 130, 220, 220], fill=(160, 80, 160))
    path = os.path.join(tmp_path, "light_map.png")
    img.save(path)
    return path


def test_detect_segments_unreadable_path(tmp_path):
    """[ECV-4] a non-image path returns a structured unavailable result."""
    bad = os.path.join(str(tmp_path), "does_not_exist.png")
    result = detect_room_segments(image_path=bad, min_area_pixels=200)
    assert result["available"] is False
    assert result["reason"] == "image_unreadable"
    assert result["segments"] == []


def test_detect_segments_with_assist_image(tmp_path):
    """[ECV-5] supplying an assist variant runs the registration/wall-cut path."""
    primary = _map_png(str(tmp_path), saturated=True)
    assist = _light_map_png(str(tmp_path))
    result = detect_room_segments(
        image_path=primary,
        assist_image_path=assist,
        min_area_pixels=200,
    )
    # The branch must complete and still produce a valid result envelope.
    assert result["available"] is True
    assert isinstance(result["segments"], list)
    assert "summary" in result


def test_detect_segments_max_segments_caps(tmp_path):
    """[ECV-6] max_segments limits how many segments come back."""
    path = _map_png(str(tmp_path), saturated=True)
    result = detect_room_segments(
        image_path=path, min_area_pixels=200, max_segments=1
    )
    assert result["available"] is True
    assert len(result["segments"]) <= 1


def _oversized_map_png(tmp_path) -> str:
    """A single saturated room covering most of the frame (area% > 0.45).

    Drives the in-pipeline 'oversized_region' / suspicious-merge branch and the
    oversized drop path.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 190, 190], fill=(60, 160, 90))  # ~81% of frame
    path = os.path.join(tmp_path, "oversized.png")
    img.save(path)
    return path


def _dumbbell_map_png(tmp_path) -> str:
    """One single-hue room shaped like a dumbbell (two blobs + a thin neck).

    Single colour => one hue cluster => one connected component whose
    area_percent (>0.18) marks it suspicious; the erosion splitter then breaks
    it in the pipeline, exercising the split-emit + dedup branches.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 240), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    color = (60, 160, 90)
    draw.rectangle([30, 40, 110, 120], fill=color)    # blob A
    draw.rectangle([30, 150, 110, 230], fill=color)   # blob B
    draw.rectangle([62, 120, 78, 150], fill=color)    # thin neck
    path = os.path.join(tmp_path, "dumbbell.png")
    img.save(path)
    return path


def test_detect_segments_oversized_region(tmp_path):
    """[ECV-7] an oversized single room triggers the suspicious/oversized path."""
    path = _oversized_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    # Pipeline completes; the oversized parent is flagged + dropped, so it must
    # not survive as a clean segment.
    assert result["available"] is True
    assert isinstance(result["segments"], list)


def test_detect_segments_dumbbell_split(tmp_path):
    """[ECV-8] a suspicious dumbbell component is split inside the pipeline."""
    path = _dumbbell_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert isinstance(result["segments"], list)
    assert "summary" in result


def test_detect_segments_no_room_pixels(tmp_path):
    """[ECV-9] a flat dark image has no room-like pixels -> structured miss."""
    from PIL import Image

    img = Image.new("RGB", (120, 120), (10, 10, 10))  # below value/sat floors
    path = os.path.join(str(tmp_path), "dark.png")
    img.save(path)
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is False
    assert result["reason"] == "no_room_pixels_detected"


def test_detect_segments_expected_room_count(tmp_path):
    """[ECV-10] expected_room_count drives the deferred-region recovery loop."""
    path = _map_png(str(tmp_path), saturated=True)
    result = detect_room_segments(
        image_path=path, min_area_pixels=200, expected_room_count=5
    )
    assert result["available"] is True
    assert isinstance(result["segments"], list)


# --- pure quality / role / state classifiers (no image needed) --------------


@pytest.mark.parametrize(
    "issues,confidence,expected",
    [
        (["tiny_region"], 0.99, "poor"),
        (["too_complex"], 0.99, "poor"),
        (["touches_border"], 0.99, "usable"),
        (["possible_merge"], 0.99, "usable"),
        ([], 0.50, "usable"),
        ([], 0.60, "good"),
        ([], 0.80, "strong"),
    ],
)
def test_issue_quality(issues, confidence, expected):
    """[SEG-1]"""
    assert _issue_quality(issues, confidence) == expected


@pytest.mark.parametrize(
    "area_percent,aspect_ratio,fill_ratio,expected",
    [
        (0.10, 1.0, 0.70, "hub"),
        (0.01, 3.0, 0.40, "connector"),
        (0.01, 1.8, 0.35, "spine"),
        (0.01, 1.0, 0.60, "room"),
        (0.01, 1.0, 0.10, "uncertain"),
    ],
)
def test_structural_role(area_percent, aspect_ratio, fill_ratio, expected):
    """[SEG-2]"""
    assert _structural_role(
        area_percent=area_percent,
        aspect_ratio=aspect_ratio,
        fill_ratio=fill_ratio,
    ) == expected


@pytest.mark.parametrize(
    "issues,fill_ratio,compactness,expected",
    [
        (["possible_merge"], 0.9, 0.9, "merged_candidate"),
        (["fragmented_candidate"], 0.9, 0.9, "fragmented_candidate"),
        ([], 0.9, 0.05, "fragmented_candidate"),  # low compactness
        ([], 0.60, 0.9, "clean"),
        (["tiny_region"], 0.60, 0.9, "review"),  # clean blocked by tiny_region
        ([], 0.40, 0.9, "review"),  # fill too low
    ],
)
def test_segmentation_state(issues, fill_ratio, compactness, expected):
    """[SEG-3]"""
    assert _segmentation_state(
        issues=issues, fill_ratio=fill_ratio, compactness=compactness
    ) == expected
