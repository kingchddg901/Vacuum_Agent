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
[ECV-8]  detect_room_segments: dense adversarial map exercises the CV long tail.
[ECV-9]  detect_room_segments: real fused-rooms map drives the localized-bins split.
[ECV-10] detect_room_segments: expected_room_count drives the deferred-region recovery loop.
[ECV-11] detect_room_segments: low bbox-fill component → possible_merge issue tag.
[ECV-12] detect_room_segments: sub-1.5%-area room, no assist agreement → tiny_region tag.
[ECV-13] detect_room_segments: small thin cross (low compactness + small area) → fragmented_candidate.
[ECV-14] detect_room_segments: oversized near-full-frame room → suspicious/oversized drop path.
[ECV-15] detect_room_segments: suspicious dumbbell component is split inside the pipeline.
[ECV-16] detect_room_segments: flat dark image with no room pixels → no_room_pixels_detected miss.
[ECV-17] detect_room_segments: expected_room_count recovery rescues a deferred region (deficit marker + confidence floor).
[ECV-18] detect_room_segments: per-region scoring block populates every derived key (role/state/confidence/edit_readiness).
[ECV-19] detect_room_segments: accepted split child masks are APPLIED to the emitted segments, not discarded in favour of the parent.
[ECV-21] colour_distance: a grown mask outside its area window at BOTH ends.
[ECV-22] colour_distance: two centres growing into one region are deduped.
[ECV-23] colour_distance: a split covering under 38% of the component is refused.
[ECV-24] colour_distance: the second centre is the FARTHEST bin, whatever the order.
[ECV-25] localized_bins: a bin with no solid core (checkerboard) is refused.
[ECV-26] localized_bins: a candidate over 22% of the component is refused.
[ECV-27] localized_bins: one candidate (or none) is not a split.
[ECV-28] localized_bins: declining hands the component on to colour_distance.
[ECV-29] assist: a blank assist registers and agrees on nothing (guard is defensive-only).
[ECV-30] local_support: 2-px support is erased by the opening; 3-px is not.
[ECV-31] keep/drop: a large washed-out region (mean sat < 30) is not a room.
[ECV-32] keep/drop: a localized child the RECLAIM shrank below the floor is refused.
[ECV-33] keep/drop: a localized child the reclaim made SPARSE is refused.
[ECV-34] assist registration: an unresolvable assist degrades, named, not fatal.
[ECV-35] recovery: stops once the count deficit is satisfied.
[ECV-36] recovery: refuses a candidate over 20% of the frame.
[ECV-37] recovery: relaxes the keep rules, does not remove them.
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
    assert result["engine"] == "cv_image_v1"
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


def test_detect_room_segments_on_dense_adversarial_map():
    """[ECV-8] a dense SYNTHETIC adversarial map (built by merging then randomly
    re-segmenting a sparse mapping run — no real-world data) drives the CV long tail
    that hand-tuned blobs can't reliably reach: the localized-bins child branches,
    the threshold-tuned artifact heuristics, full per-segment scoring / role / state
    classification, and the overlap-dedup pass (~33 segmentor lines). Structural
    assertions only — count band + the classification surface + the multi-role,
    merge-aware outcome — never exact geometry, since --cov can perturb CV."""
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "adversarial_map.png")
    result = detect_room_segments(image_path=fixture, min_area_pixels=1200)

    assert result["available"] is True
    segments = result["segments"]
    assert isinstance(segments, list) and len(segments) >= 10
    # every segment carries the full public classification surface
    assert all(
        {"structural_role", "segmentation_state", "confidence", "edit_readiness", "issues"}
        <= set(s) for s in segments
    )
    roles = {s["structural_role"] for s in segments}
    states = {s["segmentation_state"] for s in segments}
    # the dense map exercises the multi-role classifier ...
    assert {"room", "connector"} <= roles and len(roles) >= 3
    # ... and the merge-candidate detection (the adversarial 'merged rooms' trait)
    assert "merged_candidate" in states


def test_detect_room_segments_on_real_fused_map():
    """[ECV-9] a real Eufy map run exactly as the integration runs it — DARK primary
    + LIGHT assist — whose adjacent rooms fuse with the blue background into a single
    >120k component. This is the only input that reaches the deepest CV tier: the
    localized-bins SPLIT *accepting* and its child-handling (reclaim / rank / prune of
    the recovered room pockets), ~10 lines no over-segmented synthetic can touch (the
    accept gate is a narrow hue window). Structural assertions only — the fused blob
    must come back as multiple rooms (the split worked) — never exact geometry."""
    here = os.path.dirname(__file__)
    result = detect_room_segments(
        image_path=os.path.join(here, "fixtures", "localized_map_dark.png"),
        assist_image_path=os.path.join(here, "fixtures", "localized_map_light.png"),
        image_variant="dark",
        assist_variant="light",
        min_area_pixels=1200,
    )
    assert result["available"] is True
    segments = result["segments"]
    # the fused blue blob was split back into multiple rooms by localized-bins
    assert isinstance(segments, list) and len(segments) >= 5
    assert all(
        {"structural_role", "segmentation_state", "confidence", "edit_readiness", "issues"}
        <= set(s) for s in segments
    )
    assert len({s["structural_role"] for s in segments}) >= 2


def test_detect_segments_with_assist_image(tmp_path):
    """[ECV-5] supplying an assist variant runs the registration/wall-cut path.

    Asserted against a no-assist baseline on the *same* primary image, so every
    claim below is attributable to the assist branch (segmentor.py 983-1055)
    rather than to the primary pipeline:

    * registration solved (identical geometry => scale 1.0) and reported;
    * the aligned assist room mask overlaps the primary one
      (``agreement_pixel_count`` > 0, zero without assist);
    * the light-theme wall mask produced seam pixels that were actually
      SUBTRACTED from the room mask (``room_mask = base & ~seam_wall_mask``,
      line 1041) — so the reconciled room mask is strictly smaller than the
      base mask and than the no-assist run;
    * the agreement score reaches per-segment scoring: ``variant_agreement`` /
      ``variant_support`` flip from 0.0/"primary_only" to >0/"both".
    """
    primary = _map_png(str(tmp_path), saturated=True)
    assist = _light_map_png(str(tmp_path))
    result = detect_room_segments(
        image_path=primary,
        assist_image_path=assist,
        min_area_pixels=200,
    )
    baseline = detect_room_segments(image_path=primary, min_area_pixels=200)

    # The branch must complete and still produce a valid result envelope.
    assert result["available"] is True
    assert isinstance(result["segments"], list)
    assert "summary" in result
    assert baseline["available"] is True

    # --- registration actually ran (segmentor.py 989, 1047-1055) ------------
    registration = result["segmentation"]["registration"]
    assert isinstance(registration, dict)
    assert registration["enabled"] is True
    # Same 240x240 geometry, rooms at identical coordinates => identity align.
    assert float(registration["scale"]) == pytest.approx(1.0)
    assert int(registration["shift_x"]) == 0
    assert int(registration["shift_y"]) == 0
    # ...and the assist-aware message variant is selected (line 1503-1504).
    assert "primary and assist image variants" in result["message"]
    assert baseline["segmentation"]["registration"] is None
    assert "primary and assist image variants" not in baseline["message"]

    recon = result["segmentation"]["stages"]["variant_reconciliation"]
    base_stage = result["segmentation"]["stages"]["base_mask_generation"]
    base_recon = baseline["segmentation"]["stages"]["variant_reconciliation"]

    assert recon["assist_enabled"] is True
    assert base_recon["assist_enabled"] is False

    # --- the aligned assist ROOM mask exists and overlaps the primary -------
    assert recon["agreement_pixel_count"] > 0
    assert base_recon["agreement_pixel_count"] == 0

    # --- the wall-cut branch removed real pixels (segmentor.py 1027-1045) ---
    assert recon["wall_pixel_count"] > 0, "white background must register as wall"
    assert recon["seam_wall_pixel_count"] > 0, "seam zone must intersect the walls"
    removed = recon["removed_by_wall_cut_pixel_count"]
    assert removed > 0, "the seam cut must actually subtract room pixels"
    # The cut narrows the room mask: reconciled == base - removed, and the
    # no-assist run keeps every base pixel.
    assert recon["reconciled_room_pixel_count"] < base_stage["room_pixel_count"]
    assert (
        recon["reconciled_room_pixel_count"]
        == base_stage["room_pixel_count"] - removed
    )
    assert base_recon["removed_by_wall_cut_pixel_count"] == 0
    assert (
        base_recon["reconciled_room_pixel_count"]
        == baseline["segmentation"]["stages"]["base_mask_generation"]["room_pixel_count"]
    )
    # The cut is symmetric on this symmetric fixture — both rooms were trimmed.
    left_right = recon["removed_by_wall_cut_left_right"]
    assert left_right["left"] > 0 and left_right["right"] > 0

    # --- assist agreement reaches per-segment scoring (segmentor.py 1250) ---
    assert len(result["segments"]) >= 1
    assert all(seg["variant_agreement"] > 0.0 for seg in result["segments"]), [
        seg["variant_agreement"] for seg in result["segments"]
    ]
    assert all(seg["variant_support"] == "both" for seg in result["segments"])
    # Without assist the very same rooms score zero agreement, proving the
    # numbers above come from the assist image and not from the primary.
    assert all(seg["variant_agreement"] == 0.0 for seg in baseline["segments"])
    assert all(seg["variant_support"] == "primary_only" for seg in baseline["segments"])
    # Agreement feeds the confidence bonus (line 1285), so the assisted run
    # scores strictly higher on the identical rooms.
    assert max(seg["confidence"] for seg in result["segments"]) > max(
        seg["confidence"] for seg in baseline["segments"]
    )


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
    """[ECV-14] an oversized single room triggers the suspicious/oversized path.

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
    """[ECV-15] a suspicious dumbbell component runs the full split cascade.

    MEASURED FACT (probed 2026-08-07, not an aspiration): this 16px-neck
    dumbbell is *flagged* suspicious and every strategy in the cascade is
    tried, but none of them accepts — the parent is emitted merged. The
    assertions below therefore pin what the pipeline demonstrably does:

    * the component trips ``suspicious_merge`` (segmentor.py:1170-1173) —
      exactly one split candidate is logged;
    * the cascade runs and records a per-strategy verdict for that candidate
      (``debug[*]['methods']``), each entry naming its method and its
      accept/reject decision;
    * the split-APPLY accounting is self-consistent: emitted ``split_*`` issue
      tags (segmentor.py:1259) appear if and only if >= 2 child masks were
      generated and applied (segmentor.py:1204-1206);
    * everything emitted stays inside the dumbbell's own footprint.

    The positive side of that iff — split children actually reaching the
    emitted segments — is covered by [ECV-19], which uses the real fused map
    (the only fixture in this suite whose split is accepted).
    """
    path = _dumbbell_map_png(str(tmp_path))
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert isinstance(result["segments"], list)
    assert "summary" in result

    split_pass = result["segmentation"]["stages"]["suspicious_region_split_pass"]
    # The dumbbell trips the suspicious-merge predicate: exactly one candidate.
    assert split_pass["split_candidates"] == 1

    # The cascade ran and recorded a verdict for every strategy it tried.
    debug = split_pass["debug"]
    assert len(debug) == 1, debug
    methods = debug[0]["methods"]
    assert methods, "the split cascade must record per-strategy verdicts"
    assert all("method" in entry for entry in methods), methods
    assert all(isinstance(entry.get("accepted"), bool) for entry in methods), methods
    assert int(debug[0]["area_pixels"]) > 0

    # Split-apply accounting: child masks are emitted iff >= 2 were generated.
    generated = split_pass["split_generated_regions"]
    split_tags = {
        tag
        for seg in result["segments"]
        for tag in (seg.get("issues") or [])
        if str(tag).startswith("split_")
    }
    accepted_methods = {
        str(entry["method"]) for entry in methods if entry.get("accepted")
    }
    if generated >= 2:
        assert split_tags, (generated, result["segments"])
        assert split_tags <= {f"split_{name}" for name in accepted_methods}
    else:
        assert not split_tags, (generated, split_tags)
        assert not accepted_methods, accepted_methods

    # Whatever came back is a piece of the dumbbell, not something invented:
    # the shape spans x 30..110, y 40..230 in the source image.
    assert result["segments"]
    for seg in result["segments"]:
        box = seg["bbox"]
        assert box["x"] >= 30 and box["y"] >= 40, box
        assert box["x"] + box["width"] <= 111, box
        assert box["y"] + box["height"] <= 231, box
    assert sum(int(seg["area_pixels"]) for seg in result["segments"]) <= int(
        debug[0]["area_pixels"]
    )


def test_detect_split_children_reach_emitted_segments():
    """[ECV-19] accepted split masks are APPLIED, not discarded.

    The wiring between ``_split_suspicious_component`` and the emit loop
    (segmentor.py 1203-1208) is what turns a merged blob into separate rooms.
    Every synthetic fixture in this file has its split cascade REJECT, so the
    apply path only runs on the real fused map: its single >400k-pixel blob is
    accepted by ``localized_bins`` and the children carry a ``split_<method>``
    issue tag into the emitted segments.

    If the returned masks were dropped on the floor and the parent emitted
    instead, the parent would be rejected as ``oversized_region`` and those
    rooms would silently vanish — with the stage counters still reporting a
    successful split. That is what this test detects.
    """
    here = os.path.dirname(__file__)
    result = detect_room_segments(
        image_path=os.path.join(here, "fixtures", "localized_map_dark.png"),
        assist_image_path=os.path.join(here, "fixtures", "localized_map_light.png"),
        image_variant="dark",
        assist_variant="light",
        min_area_pixels=1200,
    )
    assert result["available"] is True

    split_pass = result["segmentation"]["stages"]["suspicious_region_split_pass"]
    assert split_pass["split_candidates"] >= 1
    # A strategy accepted and produced >= 2 child masks.
    assert split_pass["split_generated_regions"] >= 2
    accepted = [
        entry
        for record in split_pass["debug"]
        for entry in record["methods"]
        if entry.get("accepted")
    ]
    assert accepted, split_pass["debug"]
    accepted_tags = {f"split_{entry['method']}" for entry in accepted}

    # THE SUBJECT: those child masks reached the emitted segments.
    split_children = [
        seg
        for seg in result["segments"]
        if any(str(tag).startswith("split_") for tag in (seg.get("issues") or []))
    ]
    assert split_children, (
        "accepted split masks were generated but no emitted segment carries a "
        "split_* tag — the children were discarded and the parent emitted",
        [seg["issues"] for seg in result["segments"]],
    )
    emitted_tags = {
        tag
        for seg in split_children
        for tag in seg["issues"]
        if str(tag).startswith("split_")
    }
    assert emitted_tags <= accepted_tags, (emitted_tags, accepted_tags)

    # Each emitted child is a strict piece of its parent, not the parent again.
    parent_area = max(int(record["area_pixels"]) for record in split_pass["debug"])
    assert all(int(seg["area_pixels"]) < parent_area for seg in split_children)
    assert sum(int(seg["area_pixels"]) for seg in split_children) < parent_area
    # ...and the merged parent never survives to the caller.
    assert all(float(seg["area_percent"]) <= 0.45 for seg in result["segments"])


def test_detect_segments_no_room_pixels(tmp_path):
    """[ECV-16] a flat dark image has no room-like pixels -> structured miss."""
    from PIL import Image

    img = Image.new("RGB", (120, 120), (10, 10, 10))  # below value/sat floors
    path = os.path.join(str(tmp_path), "dark.png")
    img.save(path)
    result = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is False
    assert result["reason"] == "no_room_pixels_detected"


def test_detect_segments_expected_room_count(tmp_path):
    """[ECV-10] expected_room_count drives the deferred-region recovery loop.

    This fixture has an EMPTY deferred pile (both rooms are kept outright, so
    ``dropped_regions == 0``), which is precisely the case the sibling
    [ECV-17] cannot cover: the recovery loop is entered with nothing to rescue
    and must report the residual shortfall rather than inventing segments.
    Asserted against a no-expectation baseline on the same image so the deficit
    accounting is attributable to the parameter (segmentor.py 1434-1435, 1569).
    """
    path = _map_png(str(tmp_path), saturated=True)
    result = detect_room_segments(
        image_path=path, min_area_pixels=200, expected_room_count=5
    )
    baseline = detect_room_segments(image_path=path, min_area_pixels=200)
    assert result["available"] is True
    assert isinstance(result["segments"], list)
    assert baseline["available"] is True

    # The parameter reaches the pipeline and is echoed on the envelope.
    assert result["segmentation"]["expected_room_count"] == 5
    assert baseline["segmentation"]["expected_room_count"] == 0

    recovery = result["segmentation"]["stages"]["recovery_pass"]
    base_recovery = baseline["segmentation"]["stages"]["recovery_pass"]

    # Nothing was deferred, so the recovery loop had no candidate to promote...
    assert result["segmentation"]["stages"]["candidate_scoring"]["dropped_regions"] == 0
    assert recovery["recovered_regions"] == 0
    assert len(result["segments"]) == len(baseline["segments"])

    # ...and the shortfall is reported as a derived value off the parameter.
    assert recovery["count_deficit_after_recovery"] == 5 - len(result["segments"])
    assert recovery["count_deficit_after_recovery"] > 0
    # Without an expectation there is no deficit to report at all.
    assert base_recovery["count_deficit_after_recovery"] == 0


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
    """[ECV-17] expected_room_count recovery rescues a deferred region.

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
    """[ECV-18] the per-region scoring block populates every derived key.

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


def test_ecv20_expected_room_count_is_a_HINT_and_never_a_QUOTA():
    """[ECV-20] A deficit must not be satisfied by manufacturing rooms.

    `expected_room_count` is the user saying how many rooms their map has. When
    the pipeline finds fewer, it re-walks the regions it deferred and rescues the
    ones that are plausibly rooms -- but the deficit is NOT a licence to promote
    whatever is left. Each candidate still has to pass:

      not already tagged `dock_dark_artifact`, `thin_artifact`, `oversized_region`
      or `fragmented_candidate` -- a region judged not-a-room does not become one
      because a count says so;
      no more than 20% of the frame;
      at least `max(220, min_area_pixels * 0.4)` pixels.

    Without those, a user who says "I have 20 rooms" gets twenty things called
    rooms -- dock shadows, wall slivers, whatever remains -- each with a name and
    a place in the cleaning order.

    MEASURED ACROSS THE WHOLE RANGE, at a FIXED min_area_pixels so only the hint
    varies: asking for 16, 18, 20, 24, 30, 40 or 60 rooms all return the SAME
    count as asking for nothing. The loop runs and refuses everything; the hint
    moves no rooms into existence on this map.

    ⚠ THE FIXED min_area_pixels IS THE POINT. An earlier draft compared
    `min=1200, no hint` (15 segments) against `min=200, hint=20` (17) and credited
    the recovery with the difference -- two variables changed and the wrong one got
    the credit. The area floor moved it; the hint never does.

    ⚠ ONLY THE AREA-FLOOR GUARD CARRIES A RED HERE, measured. Ablating the
    sub-floor skip reddens this test; ablating the artifact-tag skip or the
    20%-of-frame skip changes nothing, because no deferred candidate on THIS map
    is artifact-tagged or oversized -- they execute without being observable.
    They are crossed and said to be crossed. A map whose deferred set contains
    one of those shapes would pin them; this one does not, and the fixture it
    would need no longer exists.

    Structural assertions only, per this module's convention: `--cov` can perturb
    CV, so this asserts EQUALITY ACROSS HINTS rather than any absolute count.
    """
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "adversarial_map.png")

    def _n(**kw):
        result = detect_room_segments(
            image_path=fixture, min_area_pixels=200, **kw
        )
        assert result["available"] is True
        return len(result["segments"])

    unhinted = _n()
    assert unhinted > 0, "the fixture produced no segments at all"

    for asked in (18, 24, 60):
        got = _n(expected_room_count=asked)
        assert got == unhinted, (
            "asking for %d rooms changed the result from %d to %d -- the deficit "
            "is being filled with regions the guards were meant to refuse"
            % (asked, unhinted, got)
        )

    # and the rescued set, had anything been rescued, stays fully classified
    detailed = detect_room_segments(
        image_path=fixture, min_area_pixels=200, expected_room_count=24
    )
    assert all(
        {"structural_role", "segmentation_state", "confidence", "issues"} <= set(seg)
        for seg in detailed["segments"]
    ), "a segment skipped the classification surface"


# ---------------------------------------------------------------------------
# [ECV-21..37] The split cascade's refusal arms, driven through the PUBLIC entry
# point with synthetic PNGs.
#
# WHY THESE EXIST AND WHY THEY LOOK LIKE THIS. Every arm below was previously
# recorded as unreachable or geometry-sensitive. It is neither: each one fires
# from `detect_room_segments()` on a constructed image with nothing patched, and
# the ceiling this module can honestly reach is 95.59% rather than the 92.38% it
# sat at. The recipes are preserved in the docstrings because the GEOMETRY IS THE
# CLAIM — these are not arbitrary pictures, each dimension is solving for one
# threshold, and a reader who changes a number without reading the arithmetic
# will silently stop testing the arm.
#
# TWO MECHANISMS DO MOST OF THE WORK, and neither is obvious from the source:
#
#   ONE HUE BIN, MANY COLOUR BINS. `hue_bin = (hue + 8) // 16` on PIL's 0-255
#   hue, so every RGB (255, x, x) has hue 0 and lands in a single cluster —
#   arriving as ONE connected component — while `normalized_color_features`
#   divides out brightness but NOT saturation, so those same shades quantise to
#   DISTINCT colour bins. That is how a single component can be handed to the
#   colour-distance and localized-bins arms with internal structure to find.
#
#   `binary_fill_holes` RE-ABSORBS AN ENCLOSED ISLAND of a different hue, so one
#   component can carry two far-apart chromaticities despite the 16-wide hue
#   binning. The island must be FULLY enclosed; a notch open to the edge is a
#   separate component and the arm goes untested.
#
# EACH TEST ASSERTS THE DIFFERENCE AGAINST A ONE-VARIABLE CONTROL, not just that
# the refusal happened. A refusal can be reached by more than one route, so
# "the reason string appeared" is satisfiable by the wrong branch; "it appeared
# here and not in the near-identical image" is not.
# ---------------------------------------------------------------------------


def _write(img, tmp_path, name):
    path = os.path.join(tmp_path, name)
    img.save(path)
    return path


def _canvas(size, fill=(255, 255, 255)):
    """A white canvas: saturation 0, so the background is excluded by the room gate."""
    from PIL import Image

    return Image.new("RGB", (size, size), fill)


def _paint(tmp_path, name, size, boxes):
    """Write a PNG from a list of (box, colour); boxes are [x0, y0, x1, y1] inclusive."""
    from PIL import ImageDraw

    img = _canvas(size)
    draw = ImageDraw.Draw(img)
    for box, colour in boxes:
        draw.rectangle(box, fill=colour)
    return _write(img, tmp_path, name)


#: Six shades of one hue. Distinct colour bins, one hue bin, all above the room gate.
_SHADES = [(255, 0, 0), (255, 40, 40), (255, 80, 80),
           (255, 120, 120), (255, 160, 160), (255, 230, 230)]


def _split_debug_reasons(result):
    """Every per-method `reason` the split pass recorded, across all clusters."""
    stage = (result.get("segmentation") or {}).get("stages") or {}
    reasons = set()
    for entry in (stage.get("suspicious_region_split_pass") or {}).get("debug") or []:
        for method in entry.get("methods") or []:
            if method.get("reason"):
                reasons.add("%s:%s" % (method.get("method"), method["reason"]))
    return reasons


def _localized_drop_reasons(result):
    """Every drop reason the localized-child pass recorded."""
    stage = (result.get("segmentation") or {}).get("stages") or {}
    out = set()
    for item in (stage.get("suspicious_region_split_pass") or {}).get("localized_drop_debug") or []:
        out.update(item.get("drop_reasons") or [])
    return out


def _colour_debug(result):
    """The color_distance method record: seed/grown areas and how many survived."""
    stage = (result.get("segmentation") or {}).get("stages") or {}
    for entry in (stage.get("suspicious_region_split_pass") or {}).get("debug") or []:
        for method in entry.get("methods") or []:
            if method.get("method") == "color_distance":
                return method
    return {}


def _localized_debug(result):
    """The localized_bins method record, which names how many bins RANKED versus how
    many became candidates -- the only place a bin's rejection is observable."""
    stage = (result.get("segmentation") or {}).get("stages") or {}
    for entry in (stage.get("suspicious_region_split_pass") or {}).get("debug") or []:
        for method in entry.get("methods") or []:
            if method.get("method") == "localized_bins":
                return method
    return {}


def _registration(result):
    """The assist-registration record. It sits on `segmentation`, NOT under `stages`."""
    return (result.get("segmentation") or {}).get("registration") or {}


def _scoring(result):
    stage = (result.get("segmentation") or {}).get("stages") or {}
    return stage.get("candidate_scoring") or {}


def _recovery(result):
    stage = (result.get("segmentation") or {}).get("stages") or {}
    return stage.get("recovery_pass") or {}


# --- colour-distance refusals ----------------------------------------------


def test_ecv21_colour_distance_refuses_a_grown_mask_outside_its_area_window(tmp_path):
    """[ECV-21] A colour pocket is only a room if its GROWN extent is room-sized.

    `_split_component_via_color_distance` grows a seed per colour centre and then
    applies a window at both ends: below `max(min_area*0.7, 900)` the pocket is
    noise, above `active*0.84` it is the whole component wearing a second colour's
    name. Both refusals are on the same image here, which is the point — the
    carrier grows to 4676 of 5476 px (over the upper bound) while the enclosed
    island grows to 800 (under the lower one), so neither survives and the
    strategy declines rather than inventing two rooms out of one.

    GEOMETRY: a 78x78 block with a 20x40 island of a far-apart chromaticity fully
    ENCLOSED inside it, so `binary_fill_holes` re-absorbs the island and both
    colours arrive in one component.
    """
    path = _paint(str(tmp_path), "pocket.png", 170, [
        ([40, 40, 117, 117], (254, 50, 50)),
        ([60, 60, 99, 79], (50, 50, 254)),      # fully enclosed
    ])
    result = detect_room_segments(image_path=path, min_area_pixels=1200)
    assert result["available"] is True
    debug = _colour_debug(result)
    assert debug.get("grown_mask_count") == 0, debug
    areas = sorted(debug["grown_areas"])
    assert len(areas) == 2, "expected one mask per colour centre, got %s" % areas
    # Asserted against the thresholds themselves, not against measured literals, so each
    # end of the window is pinned independently: deleting either guard admits one mask.
    assert areas[0] < max(int(1200 * 0.7), 900), (
        "the island at %d is not below the lower area floor" % areas[0])
    assert areas[1] > int(debug["active_area"] * 0.84), (
        "the carrier at %d is not above the upper area bound" % areas[1])


def test_ecv22_colour_distance_refuses_two_masks_that_are_the_same_region(tmp_path):
    """[ECV-22] Two colour centres that grow into each other are ONE room.

    A ring whose chromaticity sits inside BOTH centres' `allowed` sets is claimed
    by both, so the two grown masks overlap by 11040 of 14884 px = 0.7417, over
    the 0.72 dedup bar, and the second is dropped. Without this the user gets two
    rooms stacked on the same floor.

    GEOMETRY: concentric squares — carrier (84,254,254), a mid ring (118,220,254)
    equidistant-ish from both centres (0.0808 and 0.1212), and a core
    (169,169,254). mid+core form one enclosed hole, so fill_holes re-absorbs them.
    """
    path = _paint(str(tmp_path), "concentric.png", 330, [
        ([80, 80, 231, 231], (84, 254, 254)),
        ([95, 95, 216, 216], (118, 220, 254)),
        ([125, 125, 186, 186], (169, 169, 254)),
    ])
    result = detect_room_segments(image_path=path, min_area_pixels=1200)
    assert result["available"] is True
    assert "color_distance:insufficient_grown_masks" in _split_debug_reasons(result)


def test_ecv23_colour_distance_refuses_a_split_that_leaves_most_of_the_floor_out(tmp_path):
    """[ECV-23] A split has to ACCOUNT for the component, not nibble at it.

    `used_area < active*0.38` refuses a split whose accepted masks cover only a
    fraction of what they claim to partition — the remainder would belong to no
    room at all. Here only the two 10000-px islands rank (the eight mosaic bands
    are each 8176 px, under the 9000 bin floor), so used_area is 20000 of 90000 =
    0.22 and the strategy declines.
    """
    import numpy as np
    from PIL import Image

    canvas = np.full((600, 600, 3), 255, np.uint8)
    canvas[150:450, 150:450] = (254, 50, 50)
    inner = canvas[154:446, 154:446]                 # 4-px red ring survives outside this
    inner[0:50, 0:200] = (50, 50, 254)               # 10000 px, ranks
    inner[50:100, 0:200] = (50, 254, 50)             # 10000 px, ranks
    bands = [(254, 254, 50), (50, 254, 254), (254, 50, 254), (150, 254, 50),
             (50, 150, 254), (254, 150, 50), (150, 50, 254), (50, 254, 150)]
    for index, colour in enumerate(bands):           # 8176 px each, all sub-floor
        top = 100 + index * 28
        if top + 28 > inner.shape[0]:
            break                                    # a band past the interior would
        inner[top:top + 28, 0:292] = colour          # land on the BACKGROUND instead
    path = _write(Image.fromarray(canvas, mode="RGB"), str(tmp_path), "mosaic.png")
    result = detect_room_segments(image_path=path, min_area_pixels=1200)
    assert result["available"] is True
    assert "color_distance:insufficient_coverage" in _split_debug_reasons(result)


def test_ecv24_the_farthest_colour_bin_wins_regardless_of_arrival_order(tmp_path):
    """[ECV-24] The second colour centre is the FARTHEST bin, not the last one seen.

    `if distance > best_distance` keeps a running maximum over the ranked bins,
    and the arm that was never exercised is the FALSE one — a candidate closer
    than the best so far. Order of arrival is by pixel count, so making the
    farthest bin the SECOND-largest means iteration 2 must be rejected.

    This asserts the invariant rather than the branch: the chosen pair is the same
    whichever order the bins arrive in. Both images hold the same three colours in
    one component; only the stripe widths (hence the ranking) differ.
    """
    def _stripes(name, widths_and_colours):
        from PIL import ImageDraw

        img = _canvas(400)
        draw = ImageDraw.Draw(img)
        left = 30
        for width, colour in widths_and_colours:
            draw.rectangle([left, 30, left + width - 1, 330], fill=colour)
            left += width
        return _write(img, str(tmp_path), name)

    far, near = (255, 230, 230), (255, 40, 40)
    descending = _stripes("desc.png", [(170, (255, 0, 0)), (102, far), (68, near)])
    ascending = _stripes("asc.png", [(170, (255, 0, 0)), (102, near), (68, far)])

    first = detect_room_segments(image_path=descending, min_area_pixels=1200)
    second = detect_room_segments(image_path=ascending, min_area_pixels=1200)
    assert first["available"] is True and second["available"] is True

    # COMPARE ONLY COLOUR-DISTANCE's verdict. This asserted the WHOLE reason set, which
    # was over-broad: the two images are different pictures, so a LATER strategy in the
    # cascade is entitled to refuse them for different reasons. It passed only while
    # local_support reported one generic `no_split` for all six of its refusals; the
    # moment that function started naming them, the two runs legitimately diverged on
    # `insufficient_grown_masks` vs `insufficient_support_components` and this test went
    # red without the claim it tests having changed at all.
    def _colour_only(result):
        return {r for r in _split_debug_reasons(result) if r.startswith("color_distance:")}

    assert _colour_only(first) == _colour_only(second), (
        "the colour-distance verdict changed when the bins were merely reordered, "
        "so the running maximum is picking the last candidate rather than the farthest"
    )


# --- localized-bins refusals ------------------------------------------------


def _chromaticity_png(tmp_path, name, layout):
    """A 500x500 white canvas with a 400x400 block painted from a bin-index layout.

    `layout` is a 400x400 int array of indices into `_SHADES`. Every shade is hue
    0, so the block arrives as ONE component carrying six distinct colour bins.
    """
    import numpy as np
    from PIL import Image

    block = np.zeros((400, 400, 3), np.uint8)
    for index, colour in enumerate(_SHADES):
        block[layout == index] = colour
    canvas = np.full((500, 500, 3), 255, np.uint8)
    canvas[50:450, 50:450] = block
    return _write(Image.fromarray(canvas, mode="RGB"), tmp_path, name)


def test_ecv25_a_colour_bin_with_no_solid_core_is_not_a_room(tmp_path):
    """[ECV-25] A bin that survives only as scattered pixels is refused.

    `_localize_oversized_component` opens each bin's seed with a 3x3 structure
    before trusting it. A checkerboard bin has 10000 px — comfortably inside the
    bucket window — but no pixel has an 8-neighbour, so the opening empties it and
    the candidate is dropped. Area alone does not make a room; it has to hold
    together.

    NOT BITE-PROVEN, and the reason is worth knowing. This assertion
    DISCRIMINATES -- the control image gives equal counts -- but no single source
    edit falsifies it, because the refusal is over-determined three deep: remove
    the `np.any(opened)` check and the empty mask reaches `label()`, whose count of
    0 is caught by the next guard; remove that too and `range(1, 0 + 1)` is empty
    so the loop adds nothing anyway; and neutering the structuring element to 1x1
    still leaves the count short. Three ablations tried, all green. Recorded as
    covering the OUTCOME (a bin with no solid core yields no candidate) rather than
    any one branch -- do not read this arm's coverage as proof it is load-bearing.
    """
    import numpy as np

    layout = np.zeros((400, 400), np.int8)
    for stripe in range(5):
        layout[:, stripe * 80:(stripe + 1) * 80] = stripe
    rows, cols = np.mgrid[0:200, 0:200]
    layout[0:200, 0:200] = np.where((rows + cols) % 2 == 0, 5, 0)
    checker = _chromaticity_png(str(tmp_path), "checker.png", layout)

    even = np.zeros((400, 400), np.int8)              # control: five solid stripes
    for stripe in range(5):
        even[:, stripe * 80:(stripe + 1) * 80] = stripe
    solid = _chromaticity_png(str(tmp_path), "even.png", even)

    result = detect_room_segments(image_path=checker, min_area_pixels=1200)
    control = detect_room_segments(image_path=solid, min_area_pixels=1200)
    assert result["available"] is True and control["available"] is True
    scattered, intact = _localized_debug(result), _localized_debug(control)
    # Six bins RANK and only five become candidates: the checkerboard bin was admitted
    # on area and then produced nothing once opened.
    assert scattered["ranked_color_bins"] > scattered["candidate_count"], (
        "every ranked bin became a candidate (%s ranked, %s candidates), so the opening "
        "did not refuse the scattered one"
        % (scattered["ranked_color_bins"], scattered["candidate_count"])
    )
    assert intact["ranked_color_bins"] == intact["candidate_count"], (
        "the control also lost a bin, so the pair is not one-variable"
    )


def test_ecv26_a_localized_candidate_over_a_fifth_of_the_component_is_refused(tmp_path):
    """[ECV-26] A 'pocket' that is a quarter of the floor is not a pocket.

    There is a 3200-px window between two constants in one function: a bin is
    ADMITTED while its count is at most `active*0.24` (38400) and the grown
    candidate is REFUSED above `active*0.22` (35200). A single connected bin of
    37240 px sits inside it, so it is ranked and then dropped — the arm that
    stops an over-large colour pocket from being promoted to a room.
    """
    import numpy as np

    layout = np.zeros((400, 400), np.int8)
    layout[10:206, 10:200] = 1          # 196 x 190 = 37240 px
    layout[250:330, 10:390] = 2         # 30400
    layout[340:390, 10:390] = 3         # 19000
    path = _chromaticity_png(str(tmp_path), "window.png", layout)
    result = detect_room_segments(image_path=path, min_area_pixels=1200)
    assert result["available"] is True
    debug = _localized_debug(result)
    # Three bins rank; the 37240-px one is admitted and then dropped, so it must not
    # appear among the candidate areas while the two smaller ones do.
    assert debug["ranked_color_bins"] == 3, debug
    assert sorted(debug["candidate_areas"]) == [19000, 30400], (
        "candidate areas were %s -- the 37240-px bin was not refused"
        % debug["candidate_areas"]
    )


def test_ecv27_localized_bins_needs_two_candidates_or_it_declines(tmp_path):
    """[ECV-27] One pocket is not a split.

    `len(candidate_masks) < 2` refuses to "split" a component into itself. Two
    independent routes reach it and both are asserted: one in-range bin (the rest
    of the block is above the bucket ceiling and filtered out), and a plain solid
    block where no bin ranks at all so the candidate loop is never entered.
    """
    import numpy as np

    layout = np.zeros((400, 400), np.int8)
    layout[0:100, 0:320] = 1            # the only in-range bin
    one_bin = _chromaticity_png(str(tmp_path), "onebin.png", layout)
    solid = _paint(str(tmp_path), "solid500.png", 500, [([50, 50, 449, 449], (254, 50, 50))])

    for path in (one_bin, solid):
        result = detect_room_segments(image_path=path, min_area_pixels=1200)
        assert result["available"] is True
        assert "localized_bins:insufficient_localized_candidates" in _split_debug_reasons(result)


def test_ecv28_localized_bins_declining_hands_the_component_to_colour_distance(tmp_path):
    """[ECV-28] The cascade falls THROUGH a strategy that ran and found nothing.

    The oversized gate opens on a 198916-px component, `_localize_oversized_component`
    runs, and on a uniform block its single bin is above the bucket ceiling so
    nothing ranks — it declines, and control must continue to colour-distance
    rather than stopping. The control paints the same block as six stripes, which
    ACCEPTS, so the same gate is reached either way and only the verdict differs.
    """
    import numpy as np

    solid = _paint(str(tmp_path), "solid700.png", 700, [([120, 120, 569, 569], (255, 0, 0))])
    layout = np.zeros((450, 450), np.int8)
    for stripe in range(6):
        layout[:, stripe * 75:(stripe + 1) * 75] = stripe
    from PIL import Image
    canvas = np.full((700, 700, 3), 255, np.uint8)
    block = np.zeros((450, 450, 3), np.uint8)
    for index, colour in enumerate(_SHADES):
        block[layout == index] = colour
    canvas[120:570, 120:570] = block
    striped = _write(Image.fromarray(canvas, mode="RGB"), str(tmp_path), "striped700.png")

    declined = detect_room_segments(image_path=solid, min_area_pixels=1200)
    accepted = detect_room_segments(image_path=striped, min_area_pixels=1200)
    assert declined["available"] is True and accepted["available"] is True
    assert "localized_bins:insufficient_localized_candidates" in _split_debug_reasons(declined)
    # THE CLAIM IS THE FALL-THROUGH, so the observable is that the NEXT strategy ran:
    # colour-distance must have recorded a verdict on the declined image.
    assert _colour_debug(declined), (
        "localized_bins declined and nothing ran after it, so the cascade stopped "
        "instead of falling through to colour-distance"
    )
    # The control reaches the same gate and passes it, so the decline above is a
    # verdict about the image and not about the gate being shut.
    assert "localized_bins:insufficient_localized_candidates" not in _split_debug_reasons(accepted)


def test_ecv29_an_assist_showing_nothing_registers_and_contributes_nothing(tmp_path):
    """[ECV-29] An assist image that shows no rooms must not be believed OR break the run.

    An all-black light variant is a real upload mistake and a VALID image: it decodes, it
    aligns, every assist array is built. What it must not do is contribute agreement it
    does not have. Here it registers successfully and yields zero agreeing pixels, while
    the same image with one saturated patch inside the component agrees on that patch.

    HONEST SCOPE. This exercises the empty-assist-hue guard inside the oversized
    localizer, but it does NOT prove that guard is load-bearing: measured, replacing it
    with an unconditional `if True` changes no observable, because `np.unique` over an
    empty array is harmless and the ranking loop simply does not iterate. It is a
    defensive guard, and this test pins the surrounding CONTRACT (a blank assist costs
    the assist, not the analysis) rather than that branch. Recorded so nobody later reads
    the coverage as evidence the branch was proven.
    """
    primary = _paint(str(tmp_path), "primary700.png", 700,
                     [([120, 120, 569, 569], (255, 0, 0))])
    blank = _paint(str(tmp_path), "assist_black.png", 700, [([0, 0, 699, 699], (0, 0, 0))])
    patched = _paint(str(tmp_path), "assist_patch.png", 700, [
        ([0, 0, 699, 699], (0, 0, 0)),
        ([300, 300, 379, 379], (255, 0, 0)),
    ])

    def _agreement(assist):
        result = detect_room_segments(
            image_path=primary, min_area_pixels=1200, image_variant="dark",
            assist_image_path=assist, assist_variant="light",
        )
        assert result["available"] is True, "a degenerate assist must not fail the run"
        assert _registration(result).get("enabled") is True, (
            "a decodable assist must still register"
        )
        stage = (result.get("segmentation") or {}).get("stages") or {}
        return (stage.get("variant_reconciliation") or {}).get("agreement_pixel_count")

    assert _agreement(blank) == 0, "a blank assist agreed with something"
    assert _agreement(patched) > 0, (
        "the control agreed on nothing either, so the pair is not one-variable"
    )


def _local_support_debug(result):
    """local_support's method record. It only EXISTS as of the (masks, debug) refactor —
    before that the cascade synthesised a bare `no_split` for all six of its refusals."""
    stage = (result.get("segmentation") or {}).get("stages") or {}
    for entry in (stage.get("suspicious_region_split_pass") or {}).get("debug") or []:
        for method in entry.get("methods") or []:
            if method.get("method") == "local_support":
                return method
    return {}


def test_ecv30_support_with_no_body_is_refused_and_says_so(tmp_path):
    """[ECV-30] Support that is one pixel wide is not support.

    `_split_component_via_local_support` scores each pixel on saturation and value
    percentiles, requires two votes, then OPENS the result with a 3x3 structure before
    trusting it. Stripes 2 px wide satisfy both percentiles and are then erased entirely,
    so there is support AREA but no support BODY and the strategy declines.

    THE OBSERVABLE IS THE PAIR, which is the only way to tell this refusal from the two
    below it: `scored_support_area` is non-zero (the pixels did score) while
    `opened_support_area` is 0 (none of them survived). The control thickens the same
    stripes to 3 px on an otherwise identical image, so the difference is attributable to
    the width and nothing else.

    GEOMETRY: three colours all in hue bin 6 so they form one component. A 5-row period of
    2 rows Z / 1 row X / 2 rows Y puts 40% at both-votes, 20% at saturation only and 40% at
    value only, which is what places the score>=2 intersection exactly on the thin stripes.

    ⚠ THIS TEST WAS UNWRITEABLE UNTIL THE FUNCTION STARTED NAMING ITS REFUSALS. It was the
    only splitter returning a bare list, so all six of its refusals were indistinguishable
    from each other AND from the full-body reject — the cascade logged one invented
    `local_support:no_split` for every case. The 2-px and 3-px images produced an identical
    reason set and an identical single segment, so a test over them stayed green with the
    opening deleted: a preference, not a claim. The repo had already ruled on that shape
    once (D20 / `[SP-wall-dbg]`), and this arm is what the ruling was worth.
    """
    from PIL import Image
    import numpy as np

    def _periodic(name, z_rows, x_rows, y_rows):
        period = z_rows + x_rows + y_rows
        hsv = np.zeros((460, 460, 3), np.uint8)          # sat 0 -> excluded by the gate
        blob = np.zeros((300, 300, 3), np.uint8)
        for row in range(300):
            phase = row % period
            blob[row, :] = ((96, 200, 220) if phase < z_rows
                            else (95, 200, 80) if phase < z_rows + x_rows
                            else (96, 30, 220))
        hsv[80:380, 80:380] = blob
        rgb = np.asarray(Image.fromarray(hsv, mode="HSV").convert("RGB"))
        return _write(Image.fromarray(rgb, mode="RGB"), str(tmp_path), name)

    thin = detect_room_segments(image_path=_periodic("thin.png", 2, 1, 2),
                                min_area_pixels=1200)
    thick = detect_room_segments(image_path=_periodic("thick.png", 3, 2, 3),
                                 min_area_pixels=1200)
    assert thin["available"] is True and thick["available"] is True

    thin_debug = _local_support_debug(thin)
    assert thin_debug.get("reason") == "no_supported_body", thin_debug
    assert thin_debug["scored_support_area"] > 0, (
        "nothing scored as supported, so the opening is not what refused this"
    )
    assert thin_debug["opened_support_area"] == 0, thin_debug

    # The control reaches the same function and gets PAST that gate, so the refusal above
    # is about the stripe width rather than the strategy being unreachable.
    thick_debug = _local_support_debug(thick)
    assert thick_debug.get("reason") != "no_supported_body", thick_debug
    assert thick_debug["opened_support_area"] > 0, thick_debug


# --- candidate keep/drop arms -----------------------------------------------


def test_ecv31_a_large_washed_out_region_is_not_a_room(tmp_path):
    """[ECV-31] A third of the frame in a colour barely above the gate is refused.

    `area_percent > 0.3 and mean_saturation < 30 and not split_method` drops a big
    pale component — the shape a map takes when the capture has washed out and the
    floor reads as one faint wash rather than rooms. It clears the room gate
    (saturation >= 18) and is still not a room.

    The saturation boundary is sharp and the control sits one step the other side
    of it: mean saturation 25 drops, 31 keeps, on identical geometry.
    """
    dropped = detect_room_segments(
        image_path=_paint(str(tmp_path), "pale.png", 400,
                          [([80, 80, 319, 319], (255, 230, 230))]),
        min_area_pixels=1200)
    kept = detect_room_segments(
        image_path=_paint(str(tmp_path), "lesspale.png", 400,
                          [([80, 80, 319, 319], (255, 224, 224))]),
        min_area_pixels=1200)
    assert dropped["available"] is True and kept["available"] is True
    # The drop reason is not observable here: `localized_drop_debug` is filtered to
    # candidates whose split method was localized_bins, and this parent has none. The
    # segment itself is the observable, which is the user-visible effect anyway.
    assert not dropped["segments"], "the washed-out region was kept as a room"
    assert len(kept["segments"]) == 1, (
        "the control lost its segment too, so the pair is not one-variable"
    )
    assert _scoring(dropped)["dropped_regions"] == 1
    assert _scoring(kept)["dropped_regions"] == 0


def test_ecv32_a_localized_child_the_reclaim_shrank_below_the_floor_is_refused(tmp_path):
    """[ECV-32] A child admitted at 1408 px can arrive at the keep gate as 1008.

    This arm looks dead from the source: the admission floor
    (`max(min_area*0.9, 1400)`) is never below the reject floor
    (`max(1100, min_area*0.9)`). The step between them is
    `_reclaim_localized_child_mask`, whose sparse-top trim deletes leading rows and
    only guarantees the survivor keeps 68% — so the child SHRINKS after admission
    and the reject arm is what catches it.

    GEOMETRY: a 20-px-wide stem above a 48-px-wide block. The stem's row count
    (20) falls under the trim threshold (20.16) so it is deleted; one pixel wider
    and the trim stops at the first row, which is the control.
    """
    def _child(name, stem_width):
        return _paint(str(tmp_path), name, 700, [
            ([30, 20, 629, 299], (255, 120, 120)),                       # parent
            ([130, 60, 130 + stem_width - 1, 79], (255, 0, 0)),          # stem
            ([116, 80, 163, 100], (255, 0, 0)),                          # block
            ([400, 200, 459, 249], (255, 0, 0)),                         # sibling
        ])

    shrunk = detect_room_segments(image_path=_child("shrunk.png", 20), min_area_pixels=1200)
    intact = detect_room_segments(image_path=_child("intact.png", 21), min_area_pixels=1200)
    assert shrunk["available"] is True and intact["available"] is True
    assert "localized_child_too_small" in _localized_drop_reasons(shrunk)
    assert "localized_child_too_small" not in _localized_drop_reasons(intact)


def test_ecv33_a_localized_child_the_reclaim_made_sparse_is_refused(tmp_path):
    """[ECV-33] Growing a child can make it LESS of a room than it was.

    A child cannot be born sparse — the admission gate refuses fill_ratio < 0.16.
    The sparse arm fires because the reclaim grows the child DOWNWARD through
    room-like support: few pixels are added but the bounding box extends a long
    way, and fill_ratio is recomputed from the grown box. The support stripe must
    be a DIFFERENT colour bin from the child (or it joins the child's own seed and
    the candidate is born sparse, failing admission) while still clearing the
    reclaim's saturation floor of 237.

    The control moves the tendril one unit of green — saturation 235 against that
    floor of 237 — so the reclaim cannot see it, the child is not grown, and the
    arm is not taken. One channel step, opposite verdict.
    """
    def _sparse(name, tendril):
        return _paint(str(tmp_path), name, 700, [
            ([40, 20, 339, 619], (255, 120, 120)),      # parent
            ([60, 60, 309, 65], (255, 0, 0)),           # child bar, 1500 px
            ([180, 66, 185, 99], (255, 0, 0)),          # child tooth, 204 px
            ([180, 100, 185, 147], tendril),            # support tendril, 288 px
            ([100, 400, 159, 459], (255, 0, 0)),        # sibling
        ])

    grown = detect_room_segments(image_path=_sparse("sparse.png", (255, 10, 10)),
                                 min_area_pixels=1200)
    ungrown = detect_room_segments(image_path=_sparse("dense.png", (255, 20, 20)),
                                   min_area_pixels=1200)
    assert grown["available"] is True and ungrown["available"] is True
    assert "localized_child_sparse" in _localized_drop_reasons(grown)
    assert "localized_child_sparse" not in _localized_drop_reasons(ungrown)


# --- assist registration ----------------------------------------------------


def test_ecv34_an_assist_path_that_does_not_resolve_degrades_instead_of_failing(tmp_path):
    """[ECV-34] A bad assist must cost the assist, not the whole analysis.

    The registration block is wrapped so that anything it raises leaves the run
    alive in single-image mode, with the failure NAMED in the registration record
    rather than swallowed. Two inputs are asserted because they fail at different
    depths: a path that does not exist (`FileNotFoundError`) and a truncated PNG
    that begins to decode and then cannot (`OSError`).

    THE FIRST IS A LIVE USER ROUTE, not a contrivance, though not the one first
    recorded here. `analyze_map_image` rebuilds its tuning dict every run, so
    deleting a light variant strands nothing; what persists is a STORED adapter
    config that declares `assist_image_path` itself, which `save_adapter_config`
    accepts and which used to reach the pipeline unchecked. The service now drops
    such a path and says so ([MSV-35]), which closes that route -- and leaves this
    test covering the half the service cannot: a path that is readable when it is
    checked and broken when it is opened, and any caller reaching
    `detect_room_segments` directly. The control is the same primary with a
    readable assist, which registers normally.
    """
    primary = _paint(str(tmp_path), "reg_primary.png", 240, [
        ([28, 28, 110, 211], (200, 60, 60)),
        ([129, 28, 211, 211], (60, 80, 200)),
    ])
    good = _paint(str(tmp_path), "reg_assist.png", 240, [
        ([28, 28, 110, 211], (200, 60, 60)),
        ([129, 28, 211, 211], (60, 80, 200)),
    ])
    missing = os.path.join(str(tmp_path), "no_such_assist.png")
    truncated = os.path.join(str(tmp_path), "truncated_assist.png")
    with open(good, "rb") as handle:
        payload = handle.read()
    with open(truncated, "wb") as handle:
        handle.write(payload[: int(len(payload) * 0.55)])

    for assist in (missing, truncated):
        result = detect_room_segments(
            image_path=primary, min_area_pixels=200, image_variant="dark",
            assist_image_path=assist, assist_variant="light",
        )
        assert result["available"] is True, "a bad assist must not fail the analysis"
        registration = _registration(result)
        assert registration.get("enabled") is False
        assert registration.get("error"), "the failure was swallowed without being named"

    control = detect_room_segments(
        image_path=primary, min_area_pixels=200, image_variant="dark",
        assist_image_path=good, assist_variant="light",
    )
    assert _registration(control).get("enabled") is True
    assert not _registration(control).get("error")


# --- the deferred-recovery loop ---------------------------------------------


def _plus_png(tmp_path, name, canvas, centres, outer, arm, colour=(255, 60, 60)):
    """Plus signs, whose fill_ratio is one knob at constant compactness.

    A plus of outer extent `s` and arm width `t` has the SAME taxicab perimeter as
    an s x s square (4s), so compactness = pi*fill/4 and fill = 2u - u^2 for
    u = t/s. That makes arm width the only thing moving fill_ratio across the 0.42
    recovery boundary while compactness stays far above the 0.08 fragmented floor.
    """
    from PIL import ImageDraw, Image

    img = Image.new("RGB", (canvas, canvas), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for cx, cy in centres:
        draw.rectangle([cx - outer // 2, cy - arm // 2, cx + outer // 2, cy + arm // 2], fill=colour)
        draw.rectangle([cx - arm // 2, cy - outer // 2, cx + arm // 2, cy + outer // 2], fill=colour)
    return _write(img, tmp_path, name)


def test_ecv35_recovery_stops_once_the_count_is_satisfied(tmp_path):
    """[ECV-35] Asking for one room does not recover three.

    The recovery loop walks the deferred regions best-first and must STOP when the
    deficit closes, or a user who says "I have one more room than you found" gets
    every leftover fragment promoted. Three identical candidates with a deficit of
    one: exactly one is recovered.

    The control asks for three, so the deficit never closes and the loop runs to
    the end of the list instead of breaking — same image, same floor, one argument
    different.
    """
    path = _plus_png(str(tmp_path), "pluses.png", 560,
                     [(120, 120), (320, 120), (120, 320)], 160, 42)
    stopped = detect_room_segments(image_path=path, expected_room_count=1,
                                   min_area_pixels=16000)
    exhausted = detect_room_segments(image_path=path, expected_room_count=3,
                                     min_area_pixels=16000)
    assert stopped["available"] is True and exhausted["available"] is True
    assert _recovery(stopped).get("recovered_regions") == 1, (
        "a deficit of one recovered %s regions" % _recovery(stopped).get("recovered_regions")
    )
    assert _recovery(exhausted).get("recovered_regions") == 3


def test_ecv36_recovery_refuses_a_candidate_that_is_most_of_the_map(tmp_path):
    """[ECV-36] A deficit is not a licence to promote a region covering the floor.

    A deferred candidate over 20% of the frame is refused by area before
    `_component_should_keep` is even asked. The discrimination is on the FRAME,
    not the region: the same 103625-px plus at the same fill and compactness is
    0.2005 of a 719-px frame (refused, nothing recovered) and 0.1945 of a 730-px
    frame (recovered). Only the denominator moves.
    """
    def _one_plus(name, canvas):
        return _plus_png(str(tmp_path), name, canvas, [(canvas // 2, canvas // 2)], 480, 124)

    refused = detect_room_segments(image_path=_one_plus("big719.png", 719),
                                   expected_room_count=2, min_area_pixels=200000)
    recovered = detect_room_segments(image_path=_one_plus("big730.png", 730),
                                     expected_room_count=2, min_area_pixels=200000)
    assert refused["available"] is True and recovered["available"] is True
    assert _recovery(refused).get("recovered_regions") == 0
    assert _recovery(recovered).get("recovered_regions") == 1, (
        "the control recovered nothing either, so the 20%% area bar is not what "
        "separated these two runs"
    )


def test_ecv37_recovery_still_applies_the_keep_rules_it_relaxed(tmp_path):
    """[ECV-37] Recovery mode lowers the bar; it does not remove it.

    The only thing `recovery_mode=True` changes is one extra way to qualify
    (`area_percent >= 0.002 and fill_ratio >= 0.42`). A candidate that fails that
    too is still refused, so a deficit cannot drag in a region nothing else wanted.

    Arm width is the single knob: 26 px gives fill 0.3144 and the candidate is
    refused; 42 px gives 0.4728 on otherwise identical pluses and it is recovered.
    Compactness moves only 0.247 -> 0.371 and every other field is unchanged.
    """
    centres = [(120, 120), (320, 120), (120, 320)]
    refused = detect_room_segments(
        image_path=_plus_png(str(tmp_path), "thin_plus.png", 560, centres, 160, 26),
        expected_room_count=3, min_area_pixels=12000)
    recovered = detect_room_segments(
        image_path=_plus_png(str(tmp_path), "thick_plus.png", 560, centres, 160, 42),
        expected_room_count=3, min_area_pixels=12000)
    assert refused["available"] is True and recovered["available"] is True
    assert _recovery(refused).get("recovered_regions") == 0
    assert _recovery(recovered).get("recovered_regions") == 3, (
        "thickening the arms recovered %s, so fill_ratio is not the knob under test"
        % _recovery(recovered).get("recovered_regions")
    )
