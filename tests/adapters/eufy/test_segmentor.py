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
[ECV-7]  detect_room_segments: Pillow/scipy stack unavailable -> pipeline_unavailable.
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


def test_detect_segments_pipeline_unavailable_without_cv_stack(tmp_path, monkeypatch):
    """[ECV-7] when the Pillow/scipy stack is unavailable (_PIL_SCIPY_READY False),
    the pipeline degrades gracefully — available=False / reason=pipeline_unavailable
    / segments=[] — instead of crashing. The test image HAS scipy, so the env flag
    is patched off to drive the guard at segmentor.py 942-949."""
    path = _map_png(str(tmp_path), saturated=True)  # valid image: no image_unreadable
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.adapters.eufy.segmentor._PIL_SCIPY_READY",
        False,
    )
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is False
    assert result["reason"] == "pipeline_unavailable"
    assert result["segments"] == []
    assert "runtime" in result


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
    """[ECV-7] an oversized single room triggers the suspicious/oversized path.

    A near-full-frame single room (area% ~0.81) is flagged as a suspicious
    split candidate; when the erosion splitter cannot break it, the parent
    itself reaches the emit loop and is dropped via the generic drop-reason
    branches: ``area_percent > 0.45`` (segmentor.py 1296-1298) and the
    non-localized ``oversized_region`` reject (1305-1308). The observable
    consequences are: the oversized parent never survives as a kept clean
    segment, the suspicious-split pass logged >=1 candidate, and >=1 region
    was dropped during candidate scoring.
    """
    path = _oversized_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    # Pipeline completes with a valid envelope.
    assert result["available"] is True
    assert isinstance(result["segments"], list)

    # The oversized parent must NOT survive as a kept clean segment: nothing
    # with area_percent past the >0.45 drop threshold may remain. (1296-1298)
    assert all(
        float(seg.get("area_percent", 0.0)) <= 0.45 for seg in result["segments"]
    ), [seg.get("area_percent") for seg in result["segments"]]

    stages = result["segmentation"]["stages"]
    # The suspicious-region split pass flagged the oversized component.
    assert stages["suspicious_region_split_pass"]["split_candidates"] >= 1
    # ...and at least one region was dropped during candidate scoring, which is
    # where the generic area_percent/oversized_region drop branches fire.
    assert stages["candidate_scoring"]["dropped_regions"] >= 1


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


def _l_shaped_map_png(tmp_path) -> str:
    """Write a map with one L-shaped single-hue room + one normal room.

    The L-shaped green room (two thin arms sharing a corner) has a large bbox
    relative to its filled area, so at a high ``min_area_pixels`` it falls below
    the keep cutoff and is deferred rather than emitted. The magenta room is a
    compact square that survives on its own. With ``expected_room_count`` set,
    the recovery pass must reach back into the deferred pile and rescue the L.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 240), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    green = (60, 160, 90)
    draw.rectangle([30, 30, 120, 60], fill=green)    # horizontal arm
    draw.rectangle([30, 30, 60, 150], fill=green)     # vertical arm
    draw.rectangle([160, 160, 210, 210], fill=(160, 80, 160))  # normal room
    path = os.path.join(tmp_path, "l_shaped.png")
    img.save(path)
    return path


def test_detect_recovery_pass_rescues_deferred(tmp_path):
    """[ECV-11] expected_room_count recovery rescues a deferred region.

    Exercises the deficit loop, the issue/area filters, the recovery-mode
    ``_component_should_keep`` call, and the recovered-candidate mutation +
    append: a rescued region picks up the ``recovered_count_deficit`` issue, a
    confidence floor of 0.62, a reassigned segment id, and is counted in
    ``recovery_pass.recovered_regions``.
    """
    path = _l_shaped_map_png(str(tmp_path))
    # High min_area_pixels so the low-bbox-fill L room is deferred in the base
    # run but recoverable when a higher room count is expected.
    base = detect_room_segments(image_path=path, min_area_pixels=9000)
    rec = detect_room_segments(
        image_path=path, min_area_pixels=9000, expected_room_count=4
    )

    assert base["available"] is True
    assert rec["available"] is True
    # The recovery pass must add at least the deferred L room back.
    assert len(rec["segments"]) > len(base["segments"])
    assert (
        rec["segmentation"]["stages"]["recovery_pass"]["recovered_regions"] >= 1
    )
    # A rescued segment carries the deficit marker and the confidence floor.
    recovered = [
        seg for seg in rec["segments"]
        if "recovered_count_deficit" in seg.get("issues", [])
    ]
    assert recovered, "expected at least one recovered_count_deficit segment"
    assert any(seg["confidence"] >= 0.62 for seg in recovered)
    # tiny_region is stripped when a region is promoted out of the deferred pile.
    assert all("tiny_region" not in seg["issues"] for seg in recovered)


# --- in-pipeline per-component issue tagging ([ECV-11..13]) -----------------
#
# These exercise the issue-tag branches in the connected-component loop of
# detect_room_segments (segmentor.py ~1108-1117). Each synthetic room is shaped
# so exactly one geometric signal trips, and we assert the tag string appears on
# an emitted segment's `issues` list — observable behavior, not geometry.
#
# NOTE on `touches_border` (segmentor.py:1111): not covered here on purpose.
# The pipeline runs binary_closing(5x5, iters=2) + binary_opening(3x3) on every
# component BEFORE computing its bbox, which insets a flush-to-edge room ~6px off
# the array boundary (empirically min x/y == 6). The border check is `x<=1 or
# y<=1 or x+w>=width-1 or ...`, so a clean synthetic room can never satisfy it on
# the kept-segment path, and non-localized deferred regions are not surfaced in
# the result. Forcing it would require an unstable localized_bins split child and
# is not a deterministic real-behavior assertion.


def _all_segment_issues(result) -> set:
    """Union of `issues` across every emitted segment."""
    tags: set = set()
    for segment in result.get("segments", []):
        tags.update(segment.get("issues") or [])
    return tags


def _l_shape_map_png(tmp_path) -> str:
    """A thin single-hue L-shaped room: low bbox fill_ratio (< 0.42).

    The L is two narrow arms inside a large bounding box, so the component's
    area / (bbox w*h) falls well under 0.42, tripping the 'possible_merge' tag
    (segmentor.py:1113) without being large enough to trigger the suspicious-
    merge split (area stays under the 5200-px split floor).
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 240), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    color = (60, 160, 90)
    draw.rectangle([40, 40, 60, 160], fill=color)    # thin vertical arm
    draw.rectangle([40, 140, 160, 160], fill=color)  # thin horizontal arm
    path = os.path.join(tmp_path, "l_shape.png")
    img.save(path)
    return path


def _tiny_room_map_png(tmp_path) -> str:
    """A small saturated room: area_percent < 0.015 with no assist agreement.

    ~28x28 on a 240x240 frame => area_percent ~0.01, below the 0.015 floor;
    with no assist image the variant agreement is 0 (< 0.5), so the
    'tiny_region' tag fires (segmentor.py:1109). The room is still above the
    min-area keep floor, so it survives into the emitted segments.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 240), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 127, 127], fill=(160, 80, 160))
    path = os.path.join(tmp_path, "tiny_room.png")
    img.save(path)
    return path


def _thin_cross_map_png(tmp_path) -> str:
    """A small thin single-hue cross: low compactness AND small area.

    Two ~4px arms give compactness < 0.08 and area_percent < 0.02 (both
    conditions of segmentor.py:1117), tagging 'fragmented_candidate'. The arm
    span keeps the component well clear of the frame edge so the border-inset
    morphology does not delete it.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 240), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    color = (60, 90, 200)
    draw.rectangle([100, 60, 104, 170], fill=color)  # thin vertical arm
    draw.rectangle([60, 113, 170, 117], fill=color)  # thin horizontal arm
    path = os.path.join(tmp_path, "thin_cross.png")
    img.save(path)
    return path


def test_detect_low_fill_possible_merge(tmp_path):
    """[ECV-11] a low bbox-fill L-shaped room is tagged 'possible_merge'."""
    path = _l_shape_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert "possible_merge" in _all_segment_issues(result)


def test_detect_tiny_region_issue(tmp_path):
    """[ECV-12] a sub-1.5%-area room with no assist agreement -> 'tiny_region'."""
    path = _tiny_room_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert "tiny_region" in _all_segment_issues(result)


def test_detect_fragmented_candidate(tmp_path):
    """[ECV-13] a small thin cross (low compactness + small area) is tagged
    'fragmented_candidate'."""
    path = _thin_cross_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert "fragmented_candidate" in _all_segment_issues(result)


def test_detect_segment_scoring_fields(tmp_path):
    """[ECV-11] the per-region scoring block populates every derived key.

    Two saturated rectangular rooms run the full local issue-tagging +
    _component_should_keep + confidence-computation + candidate-assembly block
    (segmentor.py ~1216-1293). This asserts the *observable* scoring contract on
    a kept segment rather than any one branch: each derived field exists and
    holds a value from its allowed range. It also confirms the split-emit
    accounting counter survives into the result envelope as an int (line 1533;
    the split count itself is exercised by the dumbbell test).
    """
    path = _map_png(str(tmp_path), saturated=True)
    result = detect_room_segments(image_path=path, min_area_pixels=200)

    assert result["available"] is True
    assert len(result["segments"]) >= 1
    seg = result["segments"][0]

    # Structural role / segmentation state / edit readiness are enum-valued.
    assert seg["structural_role"] in {
        "hub",
        "connector",
        "spine",
        "room",
        "uncertain",
    }
    assert seg["segmentation_state"] in {
        "clean",
        "merged_candidate",
        "fragmented_candidate",
        "review",
    }
    assert seg["edit_readiness"] in {"ready", "review"}

    # Confidence is clamped into [0.05, 0.99] (segmentor.py line 1247).
    assert 0.05 <= seg["confidence"] <= 0.99

    # A kept segment cleared the <4-point drop (lines 1198-1200).
    assert isinstance(seg["point_count_simplified"], int)
    assert seg["point_count_simplified"] >= 4

    # center_pixel is a 2-element [x, y] list.
    assert isinstance(seg["center_pixel"], list)
    assert len(seg["center_pixel"]) == 2

    # issues is a list (the local issue-tagging block always seeds it).
    assert isinstance(seg["issues"], list)

    # The split-emit accounting counter is wrapped as an int in the envelope.
    split_pass = result["segmentation"]["stages"]["suspicious_region_split_pass"]
    assert isinstance(split_pass["split_generated_regions"], int)


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
