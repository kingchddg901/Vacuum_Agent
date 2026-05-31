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
"""

from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy.ndimage")
pytest.importorskip("PIL")

from custom_components.eufy_vacuum.adapters.eufy.segmentor import detect_room_segments
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
