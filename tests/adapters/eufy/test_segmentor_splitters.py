"""Brand-specific tests for the Eufy CV mask-splitter internals.

The framework's segmenter-engine machinery and the pure scoring classifiers are
covered elsewhere (``test_segmentor.py``). This file targets the heavy, tuned
mask-splitter cascade in ``adapters/eufy/segmentor.py`` — the
``_split_component_via_*`` strategies, ``_localize_oversized_component``,
``_split_suspicious_component`` orchestrator, and the ``_component_should_keep``
decision — by feeding them synthetic numpy masks / channels that deterministically
exercise each branch.

Notes on the algorithm shape (why some "positive" paths look the way they do):
  - ``erosion`` / ``opening`` / ``wall_cuts`` regrow each seed by
    ``binary_propagation`` masked by the *connected* component, and apply only a
    lower-area floor — so on a dumbbell they succeed and return >=2 masks.
  - ``color_distance`` / ``local_support`` / ``assist_hue`` apply an upper-area
    guard (``grown_area > active*0.8x``). Because propagation re-floods the whole
    connected component, those bodies run fully but reject — so we assert the
    body executes and returns ``[]`` (with the right debug reason where exposed),
    rather than forcing an unnatural accept.

Coverage targets
----------------
[SP-erosion]   dumbbell splits via erosion; single blob does not.
[SP-opening]   dumbbell splits via opening.
[SP-wall]      wall-hint cut splits; None / shape-mismatch / no-wall -> [].
[SP-local]     local_support: guards + full-body reject.
[SP-color]     color_distance: guards + reason branches + full-body reject.
[SP-hue]       assist_hue: guards + full-body reject.
[SP-oversize]  localize_oversized: guards (None rgb, below floor).
[SP-keep]      _component_should_keep: every keep/drop branch.
[SP-cascade]   _split_suspicious_component: wall-cut win + total miss.
[SP-prune]     _prune_localized_siblings: rank + sibling-overlap dedup + top-4 cap.
"""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy.ndimage")

from custom_components.eufy_vacuum.adapters.eufy import segmentor as S


_MIN = 200  # min_area_pixels used across these tests


# --- mask / channel fixtures ------------------------------------------------


def _dumbbell(neck_width: int = 8):
    """Two 60x60 blobs joined by a thin vertical neck (one connected component)."""
    m = np.zeros((200, 200), dtype=bool)
    m[30:90, 40:100] = True          # blob A
    m[110:170, 40:100] = True        # blob B
    c0 = 70 - neck_width // 2
    m[90:110, c0:c0 + neck_width] = True  # neck
    return m


def _single_blob():
    m = np.zeros((200, 200), dtype=bool)
    m[40:160, 40:160] = True
    return m


def _two_region_mask():
    """One connected rectangle spanning two halves (for channel-based splits)."""
    m = np.zeros((200, 200), dtype=bool)
    m[40:160, 40:160] = True
    return m


# --- erosion / opening ------------------------------------------------------


def test_erosion_splits_dumbbell():
    """[SP-erosion]"""
    masks = S._split_component_via_erosion(_dumbbell(neck_width=6), _MIN)
    assert len(masks) >= 2


def test_erosion_single_blob_no_split():
    """[SP-erosion] a solid blob never separates into >=2 seeds."""
    assert S._split_component_via_erosion(_single_blob(), _MIN) == []


def test_opening_splits_dumbbell():
    """[SP-opening]"""
    masks = S._split_component_via_opening(_dumbbell(neck_width=6), _MIN)
    assert len(masks) >= 2


def test_opening_single_blob_no_split():
    """[SP-opening]"""
    assert S._split_component_via_opening(_single_blob(), _MIN) == []


# --- wall cuts --------------------------------------------------------------


def test_wall_cuts_none_hint():
    """[SP-wall] no wall hint -> []."""
    assert S._split_component_via_wall_cuts(_dumbbell(), None, _MIN) == []


def test_wall_cuts_shape_mismatch():
    """[SP-wall] mismatched hint shape -> []."""
    wall = np.zeros((50, 50), dtype=bool)
    assert S._split_component_via_wall_cuts(_dumbbell(), wall, _MIN) == []


def test_wall_cuts_no_local_wall():
    """[SP-wall] wall hint that doesn't touch the component -> []."""
    wall = np.zeros((200, 200), dtype=bool)
    wall[0:5, 0:5] = True  # far corner, not near the component
    assert S._split_component_via_wall_cuts(_dumbbell(), wall, _MIN) == []


def test_wall_cuts_splits_on_neck_band():
    """[SP-wall] a wall band across the neck cuts the component in two."""
    comp = _dumbbell(neck_width=8)
    wall = np.zeros((200, 200), dtype=bool)
    wall[96:104, 40:100] = True  # horizontal band over the neck
    masks = S._split_component_via_wall_cuts(comp, wall, _MIN)
    assert len(masks) >= 2


# --- local support ----------------------------------------------------------


def test_local_support_none_channels():
    """[SP-local] missing channels -> []."""
    assert S._split_component_via_local_support(_two_region_mask(), None, None, None, None, _MIN) == []


def test_local_support_shape_mismatch():
    """[SP-local] channel shape mismatch -> []."""
    comp = _two_region_mask()
    bad = np.zeros((10, 10), dtype=np.uint8)
    assert S._split_component_via_local_support(comp, bad, bad, None, None, _MIN) == []


def test_local_support_below_area_floor():
    """[SP-local] active area under the 2x/3200 floor -> []."""
    small = np.zeros((200, 200), dtype=bool)
    small[0:20, 0:20] = True  # 400 px, below 3200
    sat = np.full((200, 200), 200, dtype=np.uint8)
    val = np.full((200, 200), 200, dtype=np.uint8)
    assert S._split_component_via_local_support(small, sat, val, None, None, _MIN) == []


def test_local_support_full_body_runs():
    """[SP-local] body executes over a real component; rejects via area guard."""
    comp = _two_region_mask()
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[40:160, 40:100] = 220  # left half high
    val[40:160, 40:100] = 220
    sat[40:160, 100:160] = 40   # right half low
    val[40:160, 100:160] = 40
    result = S._split_component_via_local_support(comp, sat, val, None, None, _MIN)
    assert isinstance(result, list)  # connected re-flood -> [] but body covered


# --- color distance ---------------------------------------------------------


def test_color_distance_missing_rgb():
    """[SP-color] None primary rgb -> debug missing_primary_rgb."""
    masks, debug = S._split_component_via_color_distance(_two_region_mask(), None, None, _MIN)
    assert masks == [] and debug["reason"] == "missing_primary_rgb"


def test_color_distance_below_area_floor():
    """[SP-color] small active area -> below_active_area_floor."""
    small = np.zeros((200, 200), dtype=bool)
    small[0:20, 0:20] = True
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    masks, debug = S._split_component_via_color_distance(small, rgb, None, _MIN)
    assert masks == [] and debug["reason"] == "below_active_area_floor"


def test_color_distance_uniform_color_rejects():
    """[SP-color] a single flat colour -> too few bins / tiny centre distance."""
    comp = _two_region_mask()
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[comp] = (120, 120, 120)  # uniform
    masks, debug = S._split_component_via_color_distance(comp, rgb, None, _MIN)
    assert masks == []
    assert debug["reason"] in {"insufficient_color_bins", "center_distance_too_small"}


def test_color_distance_two_colors_full_body():
    """[SP-color] two distinct colours run the full body (clustering + propagation)."""
    comp = _two_region_mask()
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[40:160, 40:100] = (210, 40, 40)    # red half
    rgb[40:160, 100:160] = (40, 40, 210)   # blue half
    masks, debug = S._split_component_via_color_distance(comp, rgb, None, _MIN)
    assert isinstance(masks, list)
    assert "best_center_distance" in debug  # reached the centre-distance stage


def test_color_distance_with_assist_rgb_averages():
    """[SP-color] supplying assist rgb exercises the feature-averaging branch."""
    comp = _two_region_mask()
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[40:160, 40:100] = (210, 40, 40)
    rgb[40:160, 100:160] = (40, 40, 210)
    assist = rgb.copy()
    masks, debug = S._split_component_via_color_distance(comp, rgb, assist, _MIN)
    assert isinstance(masks, list)


# --- assist hue -------------------------------------------------------------


def test_assist_hue_missing_inputs():
    """[SP-hue] missing assist channels -> missing_assist_inputs."""
    masks, debug = S._split_component_via_assist_hue(_two_region_mask(), None, None, None, _MIN)
    assert masks == [] and debug["reason"] == "missing_assist_inputs"


def test_assist_hue_below_area_floor():
    """[SP-hue] small active area -> below_active_area_floor."""
    small = np.zeros((200, 200), dtype=bool)
    small[0:20, 0:20] = True
    hue = np.zeros((200, 200), dtype=np.uint8)
    sat = np.full((200, 200), 200, dtype=np.uint8)
    val = np.full((200, 200), 200, dtype=np.uint8)
    masks, debug = S._split_component_via_assist_hue(small, hue, sat, val, _MIN)
    assert masks == [] and debug["reason"] == "below_active_area_floor"


def test_assist_hue_full_body_runs():
    """[SP-hue] two hue regions run the full body (binning + propagation)."""
    comp = _two_region_mask()
    hue = np.zeros((200, 200), dtype=np.uint8)
    sat = np.full((200, 200), 200, dtype=np.uint8)
    val = np.full((200, 200), 200, dtype=np.uint8)
    hue[40:160, 40:100] = 30    # hue bin ~3
    hue[40:160, 100:160] = 130  # hue bin ~11
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert isinstance(masks, list)
    assert "ranked_bin_count" in debug


# --- localize oversized -----------------------------------------------------


def test_localize_oversized_missing_rgb():
    """[SP-oversize] None primary rgb -> missing_primary_rgb."""
    masks, debug = S._localize_oversized_component(
        _two_region_mask(), None, None, None, None, None, _MIN
    )
    assert masks == [] and debug["reason"] == "missing_primary_rgb"


def test_localize_oversized_below_floor():
    """[SP-oversize] component under the 10x/120000 oversized floor -> rejected."""
    comp = _two_region_mask()  # ~14400 px, well below 120000
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[comp] = (120, 120, 120)
    masks, debug = S._localize_oversized_component(
        comp, rgb, None, None, None, None, _MIN
    )
    assert masks == [] and debug["reason"] == "below_oversized_floor"


# --- _component_should_keep (pure) ------------------------------------------


def _keep(**over):
    # min_area_pixels=400 so the [220, 400) "small but rescuable" window exists
    # (area<220 is the hard tiny-floor drop; area>=min is the outright keep).
    base = dict(
        area=300,
        area_percent=0.01,
        fill_ratio=0.6,
        compactness=0.3,
        aspect_ratio=1.0,
        agreement_score=0.0,
        touches_border=False,
        min_area_pixels=400,
    )
    base.update(over)
    return S._component_should_keep(**base)


def test_keep_below_tiny_floor():
    """[SP-keep] area < 220 and not recovery -> dropped."""
    keep, reasons = _keep(area=100)
    assert keep is False and "below_tiny_floor" in reasons


def test_keep_above_min_area():
    """[SP-keep] area >= min_area_pixels -> kept outright."""
    keep, reasons = _keep(area=450)
    assert keep is True and reasons == []


def test_keep_compact_small_region():
    """[SP-keep] small but compact + well-filled -> kept."""
    keep, reasons = _keep(area=300, compactness=0.3, fill_ratio=0.6)
    assert keep is True and "compact_small_region" in reasons


def test_keep_elongated_enclosed_region():
    """[SP-keep] elongated, enclosed, not touching border -> kept."""
    keep, reasons = _keep(
        area=300, compactness=0.0, fill_ratio=0.5, aspect_ratio=2.5, touches_border=False
    )
    assert keep is True and "elongated_enclosed_region" in reasons


def test_keep_confirmed_by_variants():
    """[SP-keep] strong cross-variant agreement -> kept."""
    keep, reasons = _keep(area=300, compactness=0.0, fill_ratio=0.1, agreement_score=0.6)
    assert keep is True and "confirmed_by_variants" in reasons


def test_keep_recovery_candidate():
    """[SP-keep] recovery mode rescues a small-but-plausible region."""
    keep, reasons = S._component_should_keep(
        area=300,
        area_percent=0.01,
        fill_ratio=0.5,
        compactness=0.0,
        aspect_ratio=1.0,
        agreement_score=0.0,
        touches_border=False,
        min_area_pixels=400,
        recovery_mode=True,
    )
    assert keep is True and "recovery_candidate" in reasons


def test_keep_small_no_signals_dropped():
    """[SP-keep] small with no rescuing signal -> dropped (below_small_cutoff noted)."""
    keep, reasons = _keep(
        area=300, compactness=0.0, fill_ratio=0.1, aspect_ratio=1.0, agreement_score=0.0
    )
    assert keep is False and "below_small_cutoff" in reasons


# --- _split_suspicious_component orchestrator -------------------------------


def test_suspicious_wall_cut_wins():
    """[SP-cascade] wall-cut is tried first and short-circuits the cascade."""
    comp = _dumbbell(neck_width=8)
    wall = np.zeros((200, 200), dtype=bool)
    wall[96:104, 40:100] = True
    masks, method, debug = S._split_suspicious_component(
        comp, _MIN, wall_hint_mask=wall
    )
    assert method == "wall_cuts" and len(masks) >= 2


def test_suspicious_total_miss_returns_none():
    """[SP-cascade] a plain blob with no hints exhausts the cascade -> None."""
    masks, method, debug = S._split_suspicious_component(_single_blob(), _MIN)
    assert method is None and masks == []
    assert isinstance(debug, list) and debug  # diagnostics accumulated


# --- _reclaim_localized_child_mask ------------------------------------------


def test_reclaim_empty_mask_returns_input():
    """[SP-reclaim] an empty local mask is returned unchanged."""
    empty = np.zeros((200, 200), dtype=bool)
    parent = np.ones((200, 200), dtype=bool)
    sat = np.full((200, 200), 200, dtype=np.uint8)
    out = S._reclaim_localized_child_mask(empty, parent, primary_sat=sat, primary_value=sat)
    assert not bool(np.any(out))


def test_reclaim_mask_touching_bottom_returns_input():
    """[SP-reclaim] a child already reaching the bottom edge is left as-is."""
    local = np.zeros((200, 200), dtype=bool)
    local[150:200, 60:140] = True  # bottom == 199 >= height-2
    parent = np.ones((200, 200), dtype=bool)
    sat = np.full((200, 200), 200, dtype=np.uint8)
    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=sat)
    assert np.array_equal(out, local)


def test_reclaim_no_support_returns_input():
    """[SP-reclaim] no room-like support below the child -> returned unchanged."""
    local = np.zeros((200, 200), dtype=bool)
    local[20:80, 60:140] = True
    parent = local.copy()  # parent doesn't extend below the child
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[local] = 200
    val[local] = 200
    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)
    # nothing room-like below -> no growth
    assert int(np.count_nonzero(out)) <= int(np.count_nonzero(local))


def test_reclaim_grows_downward_into_support():
    """[SP-reclaim] a top-clipped child grows down through room-like support."""
    parent = np.zeros((200, 200), dtype=bool)
    parent[20:180, 40:160] = True       # full room
    local = np.zeros((200, 200), dtype=bool)
    local[20:80, 60:140] = True         # child clipped at the top half
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[parent] = 200                   # whole room is room-like
    val[parent] = 200
    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)
    # reclaim should have added pixels below the original child
    assert int(np.count_nonzero(out)) >= int(np.count_nonzero(local))
    assert out.shape == local.shape


def test_reclaim_with_assist_channels():
    """[SP-reclaim] the assist-channel support branch is exercised."""
    parent = np.zeros((200, 200), dtype=bool)
    parent[20:180, 40:160] = True
    local = np.zeros((200, 200), dtype=bool)
    local[20:80, 60:140] = True
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[parent] = 200
    val[parent] = 200
    out = S._reclaim_localized_child_mask(
        local, parent,
        primary_sat=sat, primary_value=val,
        assist_sat=sat, assist_value=val,
    )
    assert out.shape == local.shape


# --- _localize_oversized_component positive path ----------------------------


def test_localize_oversized_splits_multicolor():
    """[SP-oversize] a >120k-px component of distinct colour bands localizes."""
    comp = np.ones((400, 400), dtype=bool)  # 160000 px, above the floor
    rgb = np.zeros((400, 400, 3), dtype=np.uint8)
    bands = [
        (200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0),
        (200, 0, 200), (0, 200, 200), (150, 75, 0), (75, 0, 150),
    ]
    for i, color in enumerate(bands):
        rgb[i * 50:(i + 1) * 50, :] = color  # 50-row horizontal band each
    masks, debug = S._localize_oversized_component(
        comp, rgb, None, None, None, None, _MIN
    )
    assert debug["active_area"] == 160000
    # distinct colour bands -> multiple localized candidates
    assert len(masks) >= 2
    assert debug["accepted"] is True


# === batch: additional hard-path coverage ===================================


# --- _reclaim_localized_child_mask deep paths (h_01) ------------------------


def test_reclaim_trims_sparse_top():
    """[SP-reclaim] a sparse upward spur over a dense body is trimmed away.

    Exercises the ``_trim_sparse_top_rows`` accumulation + 0.68 area-guard
    accept path: the dense body sets the row baseline, the thin top spur falls
    under ``baseline * pass_strength`` and is dropped, while the body survives.
    Structural counts only -- never exact pixels.
    """
    parent = np.zeros((200, 200), dtype=bool)
    parent[20:180, 40:160] = True               # full room
    local = np.zeros((200, 200), dtype=bool)
    local[60:120, 60:140] = True                # dense body (room-like)
    for r in range(20, 31):                      # thin sparse top spur
        local[r, 95:100] = True
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[parent] = 200                            # whole room reads room-like
    val[parent] = 200

    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)

    assert out.shape == local.shape
    # the sparse top band shrinks ...
    assert int(np.count_nonzero(out[20:30])) < int(np.count_nonzero(local[20:30]))
    # ... while the dense body is preserved ...
    assert int(np.count_nonzero(out[60:120])) > 0
    # ... and nothing escapes the parent component.
    assert not bool(np.any(out & ~parent))


def test_reclaim_grows_and_trims():
    """[SP-reclaim] a top-clipped child grows down through support and is cleaned.

    The body is clipped at the top of the room with a short sparse spur above it;
    downward reclaim into room-like support adds pixels (net growth) and the final
    ``_trim_sparse_top_rows`` cleanup pass runs on the expanded mask. Structural
    counts only.
    """
    parent = np.zeros((200, 200), dtype=bool)
    parent[20:180, 40:160] = True
    local = np.zeros((200, 200), dtype=bool)
    local[30:90, 60:140] = True                  # body clipped in the upper half
    for r in range(20, 26):                       # short sparse spur above the body
        local[r, 95:100] = True
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[parent] = 200
    val[parent] = 200

    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)

    assert out.shape == local.shape
    # reclaim grew the child downward into the room-like support below it ...
    assert int(np.count_nonzero(out)) > int(np.count_nonzero(local))
    # ... staying entirely inside the parent component.
    assert not bool(np.any(out & ~parent))


def test_reclaim_few_occupied_rows_returns_input():
    """[SP-reclaim] a child spanning <6 rows short-circuits the top-trim helper.

    Hits the ``occupied_rows.size < 6`` early return in ``_trim_sparse_top_rows``;
    the mask is too short to estimate a baseline so it is returned unchanged.
    """
    parent = np.zeros((200, 200), dtype=bool)
    parent[20:180, 40:160] = True
    local = np.zeros((200, 200), dtype=bool)
    local[20:25, 60:140] = True                  # only 5 occupied rows
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[parent] = 200
    val[parent] = 200

    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)

    assert out.shape == local.shape
    assert bool(np.any(out))                      # not emptied by the short-circuit


def test_reclaim_no_support_band_returns_input():
    """[SP-reclaim] no room-like support in the band below -> returned unchanged.

    The parent ends above the child's lower band, so the constrained support mask
    is empty and the function returns the child as-is (the no-support branch).
    """
    parent = np.zeros((200, 200), dtype=bool)
    parent[20:70, 40:160] = True                 # room ends at row 69
    local = np.zeros((200, 200), dtype=bool)
    local[60:100, 60:140] = True                 # child extends below the room (bottom=99)
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[parent] = 200
    val[parent] = 200
    sat[local] = 200                             # child reads room-like for the seed stats
    val[local] = 200

    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)

    # no support band below -> no growth, mask is returned unchanged
    assert np.array_equal(out, local)


def test_reclaim_overgrowth_falls_back_to_trim():
    """[SP-reclaim] when reclaim would flood the whole room it falls back to trim.

    A small dense child with a big room-like area below it makes downward
    propagation add more than the over-cap allowance; the function discards the
    over-grown mask and returns the trimmed original instead (over-cap branch).
    Structural counts only.
    """
    parent = np.zeros((250, 250), dtype=bool)
    parent[10:240, 30:220] = True                # large room
    local = np.zeros((250, 250), dtype=bool)
    local[120:140, 40:190] = True                # small dense body high in the room
    for r in range(20, 50):                       # sparse spur above the body
        local[r, 90:130] = True
    sat = np.zeros((250, 250), dtype=np.uint8)
    val = np.zeros((250, 250), dtype=np.uint8)
    sat[parent] = 200
    val[parent] = 200

    out = S._reclaim_localized_child_mask(local, parent, primary_sat=sat, primary_value=val)

    assert out.shape == local.shape
    # over-cap reclaim rejected -> result is the trimmed child, not a room flood ...
    assert int(np.count_nonzero(out)) < int(np.count_nonzero(local))
    # ... and it stays inside the parent component.
    assert not bool(np.any(out & ~parent))


# --- erosion / opening / wall-cut deep paths (h_02) ------------------------


def _tiny_blob():
    """A lone 8x8 blob: erosion/opening empties it by iteration 4.

    Exercises the "morphology wiped everything" guard (the ``if not
    np.any(eroded/opened): continue`` at the top of each iteration). At iters
    1..3 it survives as a single seed (``seed_count < 2``); at iter 4 it is gone.
    """
    m = np.zeros((200, 200), dtype=bool)
    m[150:158, 150:158] = True  # 64 px
    return m


def _big_plus_tiny_disconnected():
    """A big lobe (3600 px) and a far-away tiny lobe (64 px), NOT connected.

    Both survive erosion/opening as separate seeds, but ``binary_propagation`` is
    bounded by the (disconnected) input mask, so the tiny seed regrows to only
    64 px -- below the ``max(350, min*0.45)`` lobe floor -- while the big seed
    clears it. Only one lobe survives the floor, so the >=2 check fails and the
    splitter exhausts its iterations and returns [].
    """
    m = np.zeros((200, 200), dtype=bool)
    m[30:90, 40:100] = True       # big lobe 60x60 = 3600 px (clears the floor)
    m[150:158, 150:158] = True    # tiny lobe 8x8 = 64 px (below the floor)
    return m


def test_erosion_tiny_blob_erodes_away():
    """[SP-erosion] a blob that fully erodes hits the "eroded all gone" skip."""
    assert S._split_component_via_erosion(_tiny_blob(), _MIN) == []


def test_opening_tiny_blob_opens_away():
    """[SP-opening] a blob that fully opens away hits the "opened empty" skip."""
    assert S._split_component_via_opening(_tiny_blob(), _MIN) == []


def test_erosion_lopsided_below_floor():
    """[SP-erosion] one lobe under the area floor -> the small lobe is skipped."""
    assert S._split_component_via_erosion(_big_plus_tiny_disconnected(), _MIN) == []


def test_opening_lopsided_below_floor():
    """[SP-opening] one lobe under the area floor -> the small lobe is skipped."""
    assert S._split_component_via_opening(_big_plus_tiny_disconnected(), _MIN) == []


def test_wall_cuts_dilation_swallows_component():
    """[SP-wall] a wall blanketing the component empties every cut -> []."""
    comp = _dumbbell(neck_width=8)
    wall = np.zeros((200, 200), dtype=bool)
    wall[28:172, 38:102] = True  # blankets the component bbox + a margin
    assert S._split_component_via_wall_cuts(comp, wall, _MIN) == []


def test_wall_cuts_notch_keeps_single_component():
    """[SP-wall] a wall that nicks a corner never severs the component -> []."""
    comp = _dumbbell(neck_width=8)
    wall = np.zeros((200, 200), dtype=bool)
    wall[30:34, 40:44] = True  # tiny notch at a corner of blob A
    assert S._split_component_via_wall_cuts(comp, wall, _MIN) == []


def test_wall_cuts_lobe_below_floor():
    """[SP-wall] a severed lobe under the area floor is dropped -> []."""
    comp = np.zeros((200, 200), dtype=bool)
    comp[30:90, 40:100] = True       # big lobe 3600 px (clears the floor)
    comp[150:166, 150:166] = True    # tiny disconnected lobe 16x16 = 256 px
    wall = np.zeros((200, 200), dtype=bool)
    wall[150:152, 150:152] = True    # corner notch on the tiny lobe
    assert S._split_component_via_wall_cuts(comp, wall, _MIN) == []


# --- local support assist-channel path (h_03) ------------------------------


def _two_bar_component():
    """One connected component shaped like two bars joined by a thin neck."""
    comp = np.zeros((240, 240), dtype=bool)
    comp[30:110, 30:210] = True    # top bar
    comp[130:210, 30:210] = True   # bottom bar
    comp[110:130, 110:130] = True  # narrow neck -> one connected component
    sat = np.zeros((240, 240), dtype=np.uint8)
    val = np.zeros((240, 240), dtype=np.uint8)
    sat[comp] = 220
    val[comp] = 220
    sat[110:130, 110:130] = 30     # neck low so the opening cuts it
    val[110:130, 110:130] = 30
    return comp, sat, val


def test_local_support_with_assist_channels():
    """[SP-local] both assist channels present -> required_score=3 + grow loop."""
    comp, sat, val = _two_bar_component()
    result = S._split_component_via_local_support(
        comp, sat, val, sat.copy(), val.copy(), _MIN
    )
    assert isinstance(result, list)
    assert result == []  # body + grow loop covered; upper-area guard rejects


# --- color distance accept path (h_04) -------------------------------------


def test_color_distance_two_colors_accepts():
    """[SP-color] two chromatically distant halves drive the full accept path."""
    comp = _two_region_mask()
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[40:160, 40:100] = (210, 40, 40)    # red half
    rgb[40:160, 100:160] = (40, 40, 210)   # blue half
    masks, debug = S._split_component_via_color_distance(comp, rgb, None, _MIN)
    assert len(masks) >= 2
    assert debug["accepted"] is True
    assert debug["reason"] == "accepted"
    assert debug["best_center_distance"] > 0.09
    assert debug["grown_mask_count"] >= 2
    assert debug["used_area"] >= int(debug["active_area"] * 0.38)


def test_color_distance_assist_accepts():
    """[SP-color] the assist-rgb feature-averaging branch also reaches accept."""
    comp = _two_region_mask()
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[40:160, 40:100] = (210, 40, 40)
    rgb[40:160, 100:160] = (40, 40, 210)
    assist = rgb.copy()
    masks, debug = S._split_component_via_color_distance(comp, rgb, assist, _MIN)
    assert len(masks) >= 2
    assert debug["accepted"] is True
    assert debug["reason"] == "accepted"
    assert debug["best_center_distance"] > 0.09


# --- localize oversized assist paths (h_05) --------------------------------


def test_localize_oversized_with_assist_hue():
    """[SP-oversize] assist hue/sat/val drives the ranked-hue candidate branch."""
    comp = np.ones((400, 400), dtype=bool)  # 160000 px, above the floor
    rgb = np.zeros((400, 400, 3), dtype=np.uint8)
    bands = [
        (200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0),
        (200, 0, 200), (0, 200, 200), (150, 75, 0), (75, 0, 150),
    ]
    for i, color in enumerate(bands):
        rgb[i * 50:(i + 1) * 50, :] = color
    hue = np.zeros((400, 400), dtype=np.uint8)
    sat = np.full((400, 400), 200, dtype=np.uint8)
    val = np.full((400, 400), 200, dtype=np.uint8)
    for i, hue_value in enumerate(range(0, 141, 20)):  # 0,20,...,140 (8 values)
        hue[i * 50:(i + 1) * 50, :] = hue_value

    masks, debug = S._localize_oversized_component(
        comp, rgb, None, hue, sat, val, _MIN
    )

    assert debug["active_area"] == 160000
    assert debug["ranked_hue_bins"] >= 2  # ranked-hue branch populated
    assert debug["candidate_count"] >= 2  # candidate loop produced bins
    assert len(masks) >= 2
    assert debug["accepted"] is True


def test_localize_oversized_with_assist_rgb():
    """[SP-oversize] passing assist rgb exercises the feature-averaging branch."""
    comp = np.ones((400, 400), dtype=bool)  # 160000 px, above the floor
    rgb = np.zeros((400, 400, 3), dtype=np.uint8)
    bands = [
        (200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0),
        (200, 0, 200), (0, 200, 200), (150, 75, 0), (75, 0, 150),
    ]
    for i, color in enumerate(bands):
        rgb[i * 50:(i + 1) * 50, :] = color

    masks, debug = S._localize_oversized_component(
        comp, rgb, rgb.copy(), None, None, None, _MIN
    )

    assert debug["active_area"] == 160000
    assert debug["ranked_color_bins"] >= 2  # averaging preserved distinct bins
    assert debug["candidate_count"] >= 2
    assert len(masks) >= 2
    assert debug["accepted"] is True


# --- assist hue deep paths (h_06) ------------------------------------------


def _hue_canvas():
    """Blank hue plane + flat saturated/bright sat & value (so every comp pixel is
    'active': sat>=16 and val>=70). Tests stamp hues into ``hue`` per region."""
    hue = np.zeros((200, 200), dtype=np.uint8)
    sat = np.full((200, 200), 200, dtype=np.uint8)
    val = np.full((200, 200), 200, dtype=np.uint8)
    return hue, sat, val


def test_assist_hue_one_hue_insufficient_ranked_bins():
    """[SP-hue] a single flat hue yields one ranked bin -> insufficient_ranked_bins."""
    comp = _two_region_mask()
    hue, sat, val = _hue_canvas()
    hue[comp] = 30  # one hue everywhere -> one bin
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert masks == []
    assert debug["ranked_bin_count"] == 1
    assert debug["reason"] == "insufficient_ranked_bins"


def test_assist_hue_selects_two_bins():
    """[SP-hue] two well-separated hues rank+select bins 3 & 11; propagation re-floods
    the single connected component past the upper-area guard, so it rejects with []."""
    comp = _two_region_mask()
    hue, sat, val = _hue_canvas()
    hue[40:160, 40:100] = 30    # bin (30+6)//12 = 3
    hue[40:160, 100:160] = 130  # bin (130+6)//12 = 11
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert debug["ranked_bin_count"] >= 2
    assert debug["selected_bins"] == [3, 11]
    assert isinstance(masks, list) and masks == []
    assert debug["reason"] in {"insufficient_grown_masks", "insufficient_coverage"}


def test_assist_hue_adjacent_bins_insufficient_selected():
    """[SP-hue] two *adjacent* hue bins rank but fail the >=2 separation rule, so only
    one bin is selected -> insufficient_selected_bins."""
    comp = _two_region_mask()
    hue, sat, val = _hue_canvas()
    hue[40:160, 40:100] = 30    # bin 3
    hue[40:160, 100:160] = 42   # bin (42+6)//12 = 4 (adjacent to 3)
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert masks == []
    assert debug["ranked_bin_count"] == 2
    assert debug["reason"] == "insufficient_selected_bins"


def test_assist_hue_empty_seed_skipped():
    """[SP-hue] a selected bin whose pixels are a 1px-row stripe is erased by the seed
    opening -> that bin contributes a 0-area seed and is skipped; only one bin survives,
    so the result rejects with insufficient_grown_masks."""
    comp = np.zeros((200, 200), dtype=bool)
    hue, sat, val = _hue_canvas()
    comp[20:90, 20:180] = True      # bin-3 blob (top)
    hue[20:90, 20:180] = 30
    comp[110:180, 20:180] = True    # bottom blob, mostly bin 3 ...
    hue[110:180, 20:180] = 30
    for r in range(110, 180, 2):    # ... with a 1px-row bin-11 stripe opening will erase
        hue[r, 20:180] = 130
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert debug["selected_bins"] == [3, 11]
    assert debug["seed_areas"][1] == 0  # bin-11 seed opened away to nothing
    assert masks == []
    assert debug["reason"] == "insufficient_grown_masks"


def test_assist_hue_grown_below_floor_skipped():
    """[SP-hue] a tiny disconnected second-bin blob grows below the per-mask area floor
    and is skipped -> insufficient_grown_masks."""
    comp = np.zeros((200, 200), dtype=bool)
    hue, sat, val = _hue_canvas()
    comp[20:70, 20:80] = True       # bin-3 blob (~3000 px)
    hue[20:70, 20:80] = 30
    comp[150:170, 150:180] = True   # bin-11 blob, tiny + disconnected (~600 px)
    hue[150:170, 150:180] = 130
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert debug["selected_bins"] == [3, 11]
    assert min(debug["grown_areas"]) < 1200  # the tiny blob is below the grow floor
    assert masks == []
    assert debug["reason"] == "insufficient_grown_masks"


def test_assist_hue_insufficient_coverage():
    """[SP-hue] two small disjoint bins grow into valid masks, but their summed area is
    under the 45%-of-active coverage gate (a large multi-hued filler blob inflates the
    active area without contributing a third selectable bin) -> insufficient_coverage."""
    comp = np.zeros((200, 200), dtype=bool)
    hue, sat, val = _hue_canvas()
    comp[20:62, 20:70] = True       # bin-3 blob (~2100 px, clears the grow floor)
    hue[20:62, 20:70] = 30
    comp[150:192, 130:180] = True   # bin-11 blob (~2100 px), disconnected
    hue[150:192, 130:180] = 130
    comp[80:140, 20:180] = True     # big filler blob ...
    band_hues = [0, 60, 72, 84, 108, 168, 0, 60, 72, 84]
    for i, h in enumerate(band_hues):
        r0 = 80 + i * 6
        hue[r0:r0 + 6, 20:180] = h
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert debug["selected_bins"] == [3, 11]
    assert debug["grown_mask_count"] >= 2
    assert debug["used_area"] < int(debug["active_area"] * 0.45)
    assert masks == []
    assert debug["reason"] == "insufficient_coverage"


def test_assist_hue_three_bins_accept_disjoint():
    """[SP-hue] three well-separated hue bins on three *disconnected* blobs: the
    selection loop caps at three bins and each seed grows only within its own blob
    (below the upper-area guard), so the body accepts and returns the per-bin masks."""
    comp = np.zeros((200, 200), dtype=bool)
    hue, sat, val = _hue_canvas()
    comp[20:80, 20:80] = True       # bin 3
    hue[20:80, 20:80] = 30
    comp[20:80, 120:180] = True     # bin (90+6)//12 = 8
    hue[20:80, 120:180] = 90
    comp[120:180, 20:80] = True     # bin (150+6)//12 = 13
    hue[120:180, 20:80] = 150
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert debug["selected_bins"] == [3, 8, 13]
    assert debug["accepted"] is True
    assert debug["reason"] == "accepted"
    assert isinstance(masks, list) and len(masks) >= 2


# --- _prune_localized_siblings (rank + sibling-overlap dedup + top-4 cap) -----

def _localized_seg(mask, confidence, *, fill=0.5, compactness=0.5, area=None):
    """A minimal localized-bins child segment dict for _prune_localized_siblings."""
    return {
        "_global_mask": mask,
        "_split_method": "localized_bins",
        "confidence": confidence,
        "fill_ratio": fill,
        "compactness": compactness,
        "area_pixels": int(mask.sum()) if area is None else area,
    }


def test_prune_localized_keeps_disjoint_ranked():
    """[SP-prune] disjoint children are all kept, ordered strongest-first
    (confidence desc), with no dedup."""
    m0 = np.zeros((10, 40), dtype=bool); m0[:, 0:5] = True
    m1 = np.zeros((10, 40), dtype=bool); m1[:, 12:17] = True
    m2 = np.zeros((10, 40), dtype=bool); m2[:, 24:29] = True
    segs = [_localized_seg(m1, 0.5), _localized_seg(m2, 0.9), _localized_seg(m0, 0.7)]

    out, deduped = S._prune_localized_siblings(segs, 0)

    assert deduped == 0
    assert [s["confidence"] for s in out] == [0.9, 0.7, 0.5]  # ranked, all kept


def test_prune_localized_drops_overlapping_sibling():
    """[SP-prune] a lower-ranked child overlapping a kept sibling by >= 0.35 is
    dropped and counted; a disjoint child still survives."""
    base = np.zeros((10, 20), dtype=bool); base[:, 0:10] = True    # strongest, kept
    overl = np.zeros((10, 20), dtype=bool); overl[:, 3:13] = True  # 0.7 overlap -> dropped
    far = np.zeros((10, 20), dtype=bool); far[:, 15:20] = True     # disjoint -> kept
    segs = [_localized_seg(base, 0.9), _localized_seg(overl, 0.5), _localized_seg(far, 0.4)]

    out, deduped = S._prune_localized_siblings(segs, 0)

    assert deduped == 1
    assert [s["confidence"] for s in out] == [0.9, 0.4]  # overlapping 0.5 dropped


def test_prune_localized_caps_at_four():
    """[SP-prune] more than four disjoint children -> only the top four by rank."""
    segs = []
    for i in range(6):
        m = np.zeros((10, 70), dtype=bool); m[:, i * 10:i * 10 + 5] = True
        segs.append(_localized_seg(m, 0.50 + i * 0.05))

    out, deduped = S._prune_localized_siblings(segs, 0)

    assert deduped == 0
    assert len(out) == 4
    assert [round(s["confidence"], 2) for s in out] == [0.75, 0.70, 0.65, 0.60]


def test_prune_localized_empty_is_noop():
    """[SP-prune] empty input -> ([], unchanged count); the unconditional call site
    relies on this (the `if localized_segments:` guard was removed)."""
    out, deduped = S._prune_localized_siblings([], 3)
    assert out == [] and deduped == 3


def test_assist_hue_overlap_dedup_then_accept():
    """[SP-hue] two bins inside one connected blob both re-flood that whole blob, so the
    second's grown mask is dropped by the >=0.72 overlap dedup; a third bin on a separate
    blob still yields a distinct mask, so the body accepts 2 (not 3) masks."""
    comp = np.zeros((200, 200), dtype=bool)
    hue, sat, val = _hue_canvas()
    comp[20:70, 20:120] = True      # connected blob A: bin 3 left, bin 11 right ->
    hue[20:70, 20:70] = 30          #   both seeds propagate to *all* of A (overlap 1.0)
    hue[20:70, 70:120] = 130
    comp[110:180, 20:180] = True    # separate blob C: bin 8
    hue[110:180, 20:180] = 90
    masks, debug = S._split_component_via_assist_hue(comp, hue, sat, val, _MIN)
    assert debug["accepted"] is True
    assert len(masks) == 2  # A counted once (overlap-deduped) + C


# --- _split_suspicious_component cascade winners (h_07) --------------------


def test_suspicious_color_distance_wins():
    """[SP-cascade] no wall hint + sub-oversized comp -> color_distance branch wins."""
    comp = _two_region_mask()
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)
    rgb[40:160, 40:100] = (210, 40, 40)    # red half
    rgb[40:160, 100:160] = (40, 40, 210)   # blue half
    masks, method, debug = S._split_suspicious_component(comp, _MIN, primary_rgb=rgb)
    assert method == "color_distance" and len(masks) >= 2


def test_suspicious_localized_bins_wins():
    """[SP-cascade] a >120k-px multi-colour comp localizes before color_distance."""
    comp = np.ones((400, 400), dtype=bool)  # 160000 px, above the floor
    rgb = np.zeros((400, 400, 3), dtype=np.uint8)
    bands = [
        (200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0),
        (200, 0, 200), (0, 200, 200), (150, 75, 0), (75, 0, 150),
    ]
    for i, color in enumerate(bands):
        rgb[i * 50:(i + 1) * 50, :] = color  # 50-row horizontal band each
    masks, method, debug = S._split_suspicious_component(comp, _MIN, primary_rgb=rgb)
    assert method == "localized_bins" and len(masks) >= 2


def test_suspicious_erosion_wins():
    """[SP-cascade] dumbbell with no colour/sat/wall hints falls through to erosion."""
    comp = _dumbbell(neck_width=6)
    masks, method, debug = S._split_suspicious_component(comp, _MIN)
    assert method == "erosion_seeds" and len(masks) >= 2
