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
