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
[SP-local-4]   RT-5: the duplicate-grown-mask skip. Two supported seeds inside ONE
               connected sub-blob both reflood it, so the second mask is a duplicate
               and is dropped rather than returned as a second room.
[SP-color]     color_distance: guards + reason branches + full-body reject.
[SP-hue]       assist_hue: guards + full-body reject.
[SP-oversize]  localize_oversized: guards (None rgb, below floor).
[SP-keep]      _component_should_keep: every keep/drop branch.
[SP-cascade]   _split_suspicious_component: wall-cut win + total miss.
[SP-prune]     _prune_localized_siblings: rank + sibling-overlap dedup + top-4 cap.
[SP-wall-dbg]  D20: a wall-cut DECLINE is recorded, and says which decline it was. The
               first-tried strategy appended a debug row only on success, so its failure
               left no row and read as never-attempted.
[SP-oversize-xsite] the cascade's oversized GATE and localize's own oversized FLOOR
               are one threshold, complementary at every area across the whole
               admissible min_area_pixels range -- so a one-sided retune of either
               copy reddens. Behavioural, and it names neither constant.
[SP-hue-floor]  D1: the assist-hue area floor refuses an EMPTY `active` across the
                whole admissible min_area_pixels range, and its BISECTED value never
                admits an empty sample. This is the guard that killed the deleted
                `len(hue_values) == 0` check, so it is now load-bearing.
[SP-hue-sample] D1: the hue sample is `assist_hue` AT the active pixels only -- the
                other half of that invariant, which dies if `active` stops being a
                boolean mask.
[SP-oversize-floor]     D2: the ABSOLUTE active-area floor in
               ``_localize_oversized_component`` absorbs every undersized component,
               swept across ``min_area_pixels``. The floor itself is bisected out of the
               function's own behaviour, never restated, so retuning the source moves
               what the test measures.
[SP-oversize-dominance] D2: that floor is strictly positive for every swept tuning and
               does not scale down with ``min_area_pixels`` -- the arithmetic that made
               the deleted ``no_feature_values`` check unreachable.
[SP-oversize-identity]  D2: ``len(quantized[active]) == count_nonzero(active)``, pinned
               across channel counts including the ``(N, 0)`` feature axis; the second
               CONDITION behind the deletion -- not a second independent reason.
[SP-D3-1..3]   D3: the `count <= 0` refusal in `_localize_oversized_component.
               _try_add_candidate` is deleted. A scipy dependency RATCHET pins
               `label`'s count contract and `find_objects`' gapless indexing, and
               the empty `range` that actually makes the deletion safe.
[SP-D3-4]      D3: the surviving `np.any(opened)` guard still admits real seeds.
               Catches its INVERSION; its deletion has no behaviour to catch, which
               the docstring states rather than implies.
[SP-local-5]   local_support: the active-area floor is the net under the now-dead
               `empty_support_values` slice guard, bisected out of the function's
               own verdicts -- reddens if the floor is deleted, neutralised or
               loses its constant arm, not on a shape-preserving retune.
[SP-local-6]   local_support: both support slices index ONE `active` mask, pinned
               through the percentile floor they feed -- filtering or re-masking
               either slice changes the split.
[RCL-4]        the sparse-top trim's occupied-row FLOOR is the SECOND killer of
               `_reclaim_localized_child_mask`'s `ys.size == 0` fallback, and the
               one nothing covered. At a one-pixel child the retention clamp that
               `[RCL-1]` tests is BYPASSED, not loosened, so no retune of that
               test's fixtures reaches this state. The floor is swept out of the
               function's own answers and never named, so a retune moves what is
               measured; dropping it, or lowering it onto a one-row child, reddens.
"""

from __future__ import annotations

import functools

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
    masks, debug = S._split_component_via_local_support(
        _two_region_mask(), None, None, None, None, _MIN)
    assert masks == [] and debug["reason"] == "missing_support_channels"


def test_local_support_shape_mismatch():
    """[SP-local] channel shape mismatch -> []."""
    comp = _two_region_mask()
    bad = np.zeros((10, 10), dtype=np.uint8)
    masks, debug = S._split_component_via_local_support(comp, bad, bad, None, None, _MIN)
    assert masks == [] and debug["reason"] == "missing_support_channels"


def test_local_support_below_area_floor():
    """[SP-local] active area under the 2x/3200 floor -> []."""
    small = np.zeros((200, 200), dtype=bool)
    small[0:20, 0:20] = True  # 400 px, below 3200
    sat = np.full((200, 200), 200, dtype=np.uint8)
    val = np.full((200, 200), 200, dtype=np.uint8)
    masks, debug = S._split_component_via_local_support(small, sat, val, None, None, _MIN)
    assert masks == [] and debug["reason"] == "below_active_area_floor"


def test_local_support_full_body_runs():
    """[SP-local] body executes over a real component; rejects via area guard."""
    comp = _two_region_mask()
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[40:160, 40:100] = 220  # left half high
    val[40:160, 40:100] = 220
    sat[40:160, 100:160] = 40   # right half low
    val[40:160, 100:160] = 40
    result, debug = S._split_component_via_local_support(comp, sat, val, None, None, _MIN)
    # connected re-flood -> [] but the body is covered; the reason now says WHICH
    # refusal that was rather than leaving all six looking alike.
    assert isinstance(result, list)
    assert debug["reason"] in {"insufficient_grown_masks", "no_supported_body",
                               "insufficient_support_components"}


def _support_scored_blobs():
    """Three disjoint blobs: two room-like (sat/val 220), one dim (sat/val 40).

    Disjoint on purpose -- ``binary_propagation`` is bounded by the input mask, so
    each seed regrows only inside its own blob and stays under the
    ``grown_area > active_area*0.8`` upper guard. That is the only geometry in
    which ``_split_component_via_local_support`` can actually ACCEPT, so it is the
    only geometry in which its percentile scoring is observable.
    """
    bright_a = np.zeros((200, 200), dtype=bool)
    bright_a[20:70, 20:80] = True        # 3000 px
    bright_b = np.zeros((200, 200), dtype=bool)
    bright_b[120:170, 20:80] = True      # 3000 px
    dim_c = np.zeros((200, 200), dtype=bool)
    dim_c[120:170, 120:180] = True       # 3000 px, unsupported
    comp = bright_a | bright_b | dim_c   # active_area 9000, above the 3200 floor
    sat = np.zeros((200, 200), dtype=np.uint8)
    val = np.zeros((200, 200), dtype=np.uint8)
    sat[bright_a | bright_b] = 220
    val[bright_a | bright_b] = 220
    sat[dim_c] = 40                      # below the 42nd/38th percentile floors
    val[dim_c] = 40
    return comp, bright_a, bright_b, dim_c, sat, val


def test_local_support_splits_supported_blobs():
    """[SP-local] the ACCEPT path: percentile scoring keeps the two room-like blobs
    and rejects the dim one, and the label+grow loop returns one mask per survivor."""
    comp, bright_a, bright_b, dim_c, sat, val = _support_scored_blobs()

    result, debug = S._split_component_via_local_support(comp, sat, val, None, None, _MIN)

    assert len(result) == 2                                   # a real split, not []
    assert debug["accepted"] is True and debug["reason"] == "accepted"
    # each returned mask is exactly one of the two supported blobs ...
    recovered = sorted(result, key=lambda m: int(np.flatnonzero(np.any(m, axis=1))[0]))
    assert np.array_equal(recovered[0], bright_a)
    assert np.array_equal(recovered[1], bright_b)
    # ... and the dim blob, which failed the sat/value score, is in neither.
    assert not any(bool(np.any(mask & dim_c)) for mask in result)
    # nothing leaks outside the component the caller handed in.
    assert not any(bool(np.any(mask & ~comp)) for mask in result)


def test_local_support_assist_channels_raise_required_score():
    """[SP-local] the required_score 2-vs-3 rule: with both assist channels present a
    blob must be supported by the ASSIST image too, so assist that disagrees on one
    blob demotes it below the score and collapses the split."""
    comp, bright_a, bright_b, dim_c, sat, val = _support_scored_blobs()

    # Control: assist channels that agree with the primary keep the same 2-way split
    # (so the demotion below is attributable to disagreement, not to assist per se).
    agreeing, agree_debug = S._split_component_via_local_support(
        comp, sat, val, sat.copy(), val.copy(), _MIN
    )
    assert len(agreeing) == 2
    assert agree_debug["required_score"] == 3  # both assist channels present

    # Assist reads blob B as dim: B now scores 2 (primary only) against a
    # required_score of 3, leaving a single supported component -> no split.
    assist_sat = np.zeros((200, 200), dtype=np.uint8)
    assist_value = np.zeros((200, 200), dtype=np.uint8)
    assist_sat[bright_a | dim_c] = 220
    assist_value[bright_a | dim_c] = 220
    assist_sat[bright_b] = 20
    assist_value[bright_b] = 20

    disagreeing, disagree_debug = S._split_component_via_local_support(
        comp, sat, val, assist_sat, assist_value, _MIN
    )
    assert disagreeing == []
    assert disagree_debug["reason"] != "accepted"


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
    # "returns input" means EXACTLY the input: this fixture reaches the
    # `if not np.any(reclaimed): return local_mask` branch (the support band below
    # the child is non-empty but propagation adds nothing), so the child must come
    # back untouched -- an emptied / eroded mask is a regression, not a pass.
    assert np.array_equal(out, local)
    assert int(np.count_nonzero(out)) == int(np.count_nonzero(local)) > 0


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
    """[SP-reclaim] the assist-channel support branch NARROWS where reclaim may grow.

    ``support_mask &= assist_support`` is an intersection, so it can only ever
    remove support. Asserted as a three-way contrast over one geometry:

      * no assist              -> the child grows down into the room-like support;
      * assist == primary      -> identical result (the intersection is a no-op);
      * assist dark below      -> growth is blocked entirely, child returned as-is.

    The third case is the one with teeth: it fails if the assist block is deleted
    (growth returns) or if its comparisons are inverted (dark assist would then
    read as support).
    """
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

    # Baseline: with no assist channels the child grows down past its own bottom.
    no_assist = S._reclaim_localized_child_mask(
        local, parent, primary_sat=sat, primary_value=val
    )
    assert int(np.count_nonzero(no_assist)) > int(np.count_nonzero(local))
    assert int(np.count_nonzero(no_assist[80:])) > 0  # reclaimed below the child

    # Agreeing assist channels intersect to nothing new -> identical to baseline.
    assert np.array_equal(out, no_assist)

    # Disagreeing assist channels (dark from row 77 down, i.e. across the whole
    # support band) remove that support, so reclaim finds nothing to grow into.
    dark_sat = sat.copy()
    dark_value = val.copy()
    dark_sat[77:, :] = 0
    dark_value[77:, :] = 0
    narrowed = S._reclaim_localized_child_mask(
        local, parent,
        primary_sat=sat, primary_value=val,
        assist_sat=dark_sat, assist_value=dark_value,
    )
    assert int(np.count_nonzero(narrowed[80:])) == 0        # nothing reclaimed below
    assert int(np.count_nonzero(narrowed)) < int(np.count_nonzero(no_assist))
    assert np.array_equal(narrowed, local)                  # child returned unchanged


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
    result, _debug = S._split_component_via_local_support(
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



# ---------------------------------------------------------------------------
# D20 - the first-tried strategy records its declines
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case,expected",
    [
        ("no_hint", "no_wall_hint"),
        ("shape_mismatch", "wall_hint_shape_mismatch"),
        ("no_local_wall", "no_local_wall"),
        ("no_split", "no_split"),
    ],
)
def test_sp_wall_dbg_a_decline_is_recorded_with_its_reason(case, expected):
    """[SP-wall-dbg] RED BEFORE THE FIX — the list stayed empty on every failure.

    The four declines are kept distinct because they send a reader somewhere different:
    `no_wall_hint` is a missing second image (the user never uploaded the other theme),
    `wall_hint_shape_mismatch` is two images at different sizes (a pipeline bug),
    `no_local_wall` is a hint that does not touch this component, and `no_split` is walls
    found with no clean cut (a tuning question). Collapsing them to "it failed" would
    close the "never attempted" reading and open a "which of four problems is this" one.
    """
    debug: list[dict] = []
    if case == "no_hint":
        S._split_component_via_wall_cuts(_dumbbell(), None, _MIN, debug)
    elif case == "shape_mismatch":
        S._split_component_via_wall_cuts(_dumbbell(), np.zeros((50, 50), dtype=bool), _MIN, debug)
    elif case == "no_local_wall":
        wall = np.zeros((200, 200), dtype=bool)
        wall[0:5, 0:5] = True
        S._split_component_via_wall_cuts(_dumbbell(), wall, _MIN, debug)
    else:
        # A hint that DOES touch the component but frees no second region: a single
        # pixel-thin nick at the edge. Anything that actually severs the neck would
        # return masks and land in the success path instead.
        comp = _dumbbell()
        wall = np.zeros((200, 200), dtype=bool)
        wall[comp] = False
        ys, xs = np.nonzero(comp)
        wall[ys[0], xs[0]] = True
        S._split_component_via_wall_cuts(comp, wall, _MIN, debug)

    assert len(debug) == 1, "a decline left no debug row at all"
    assert debug[0]["method"] == "wall_cuts"
    assert debug[0]["accepted"] is False
    assert debug[0]["reason"] == expected


def test_sp_wall_dbg_a_success_does_not_append_a_decline():
    """[SP-wall-dbg] RED IF THE SINK IS APPENDED TO UNCONDITIONALLY. The success row is
    written by the caller with its own mask count; a decline row beside it would make the
    per-method list say the strategy both failed and succeeded."""
    comp = _dumbbell(neck_width=8)
    wall = np.zeros((200, 200), dtype=bool)
    wall[96:104, 40:100] = True
    debug: list[dict] = []
    masks = S._split_component_via_wall_cuts(comp, wall, _MIN, debug)

    assert len(masks) >= 2
    assert debug == []


def test_sp_wall_dbg_the_cascade_surfaces_the_decline():
    """[SP-wall-dbg] The end-to-end point: the row has to reach the per-method debug list
    the cascade returns, not just the helper's own sink.

    RED IF THE CALLER STOPS PASSING THE SINK — which is exactly the state this repaired,
    and which no other assertion in this file can see.
    """
    comp = _dumbbell()
    _masks, _method, entries = S._split_suspicious_component(comp, _MIN)
    methods = [e.get("method") for e in entries]
    assert "wall_cuts" in methods, (
        "the first-tried strategy is missing from the per-method debug list, so a reader "
        "would conclude it was never attempted: " + repr(methods)
    )


# ---------------------------------------------------------------------------
# [SP-local-2..4] local_support: the three ways a candidate is discarded
#
# The accept path is exercised elsewhere. These are the discards, and each one
# is asserted by a COUNT rather than by emptiness, because "no split" is also
# what a strategy that silently did nothing returns.
# ---------------------------------------------------------------------------

def _blobs(*rects):
    """A mask holding one rectangle per (top, bottom, left, right)."""
    m = np.zeros((300, 300), dtype=bool)
    for top, bottom, left, right in rects:
        m[top:bottom, left:right] = True
    return m


def test_sp_local3_a_region_below_the_grown_floor_is_dropped_not_returned():
    """[SP-local-3] A third region too small to be a room is discarded, not kept.

    Three disjoint blobs, all fully supported: two large enough to be rooms and
    one of ~400 px. Propagation is masked by the component, so each blob grows to
    itself and no two merge.

    THE ASSERTION IS len == 2, NOT "no crash". Without the grown-area floor the
    small blob is appended too and the caller receives THREE room candidates from
    a component that holds two rooms and a fleck -- and the fleck becomes a room
    on the user's map with a name and a cleaning order.
    """
    mask = _blobs(
        (20, 80, 20, 80),      # 60x60 = 3600
        (120, 180, 20, 80),    # 60x60 = 3600
        (220, 240, 20, 40),    # 20x20 =  400  <- below the 1000 floor
    )
    sat = np.full((300, 300), 200, dtype=np.uint8)
    value = np.full((300, 300), 200, dtype=np.uint8)

    out, _debug = S._split_component_via_local_support(mask, sat, value, None, None, _MIN)

    assert len(out) == 2, (
        "expected the two room-sized regions and not the 400px fleck, got %d"
        % len(out)
    )


def _support_split_by_a_dim_band():
    """One connected sub-blob whose SUPPORT is cut in two, plus a second sub-blob.

    THIS IS THE SIBLING THAT BREAKS ``_support_scored_blobs``'S STATED ASSUMPTION.
    That fixture's docstring calls its disjoint layout "the only geometry in which
    ``_split_component_via_local_support`` can actually ACCEPT" -- true, and it is
    also what hid a whole clause, because one seed per blob leaves the
    duplicate-grown-mask skip nothing to skip.

    Here sub-blob A carries TWO supported seeds separated by a 6 px dim band. The
    band is dim, so it scores below the percentile floors and the labelling sees two
    seeds; but it is part of ``component_mask``, so ``binary_propagation`` floods
    straight across it and BOTH seeds regrow the whole of A. Identical masks,
    overlap 1.0.

    Geometry (300x300 so it matches the neighbouring fixtures):
      A  rows  20:80, cols  20:120 = 6000 px, ONE connected rectangle
           left seed  cols 20:67   = 2820 px, sat/value 220
           dim band   cols 67:73   =  360 px, sat/value  40  (4.5% of active)
           right seed cols 73:120  = 2820 px, sat/value 220
      B  rows 150:190, cols 20:70  = 2000 px, sat/value 220, disjoint from A

    The band's width and its dimness both carry margin. A single 3x3
    ``binary_closing`` bridges a gap of at most 2 px, so 6 px leaves 4 px spare
    before the two seeds would merge back into one. And the band is 4.5% of active
    against a ``value_floor`` at the 38th percentile, so it could grow to 38% of the
    component before the floor dropped onto the dim value and swallowed it.
    """
    comp = np.zeros((300, 300), dtype=bool)
    comp[20:80, 20:120] = True        # sub-blob A, one connected 60x100 = 6000 px
    comp[150:190, 20:70] = True       # sub-blob B, 40x50 = 2000 px, disjoint

    blob_a = np.zeros((300, 300), dtype=bool)
    blob_a[20:80, 20:120] = True
    blob_b = np.zeros((300, 300), dtype=bool)
    blob_b[150:190, 20:70] = True

    a_left = np.zeros((300, 300), dtype=bool)
    a_left[20:80, 20:67] = True       # 60 x 47 = 2820 px
    a_right = np.zeros((300, 300), dtype=bool)
    a_right[20:80, 73:120] = True     # 60 x 47 = 2820 px
    dim_band = np.zeros((300, 300), dtype=bool)
    dim_band[20:80, 67:73] = True     # 60 x  6 =  360 px, inside A, unsupported

    sat = np.zeros((300, 300), dtype=np.uint8)
    value = np.zeros((300, 300), dtype=np.uint8)
    sat[a_left | a_right | blob_b] = 220
    value[a_left | a_right | blob_b] = 220
    sat[dim_band] = 40
    value[dim_band] = 40
    return comp, blob_a, blob_b, dim_band, sat, value


def test_sp_local4_two_seeds_in_one_sub_blob_return_one_mask_not_two():
    """[SP-local-4] RT-5: a sub-blob reached by two seeds is returned ONCE.

    ``binary_propagation`` is bounded by ``component_mask``, not by the seed, so two
    supported seeds inside one connected sub-blob both reflood the WHOLE sub-blob and
    produce identical masks. ``_split_component_via_local_support`` drops the second
    by overlap ratio.

    WHAT THE SKIP IS ACTUALLY WORTH, corrected 2026-11-11 after the claim that stood here
    was refuted. This docstring used to say the duplicate reaches the caller and becomes
    "two rooms occupying one space -- two names, two cleaning orders, one floor". It does
    not: measured, 36 identical accepted masks left the pipeline as ONE segment, 35 of them
    dropped by ``_detect_room_segments_pipeline``'s own ``overlap >= 0.8`` dedup. The
    duplicate never becomes a second room.

    The skip earns its keep somewhere the downstream dedup cannot reach: an ACCEPT STOPS
    THE CASCADE, so ``assist_hue``, ``erosion_seeds`` and ``opening_split`` never run on a
    component that a later strategy might have split correctly, and the ``split_local_support``
    labelling moves each child onto a different keep/drop path downstream. That is the
    consequence worth asserting, and it is why this test pins ``grown_mask_count`` rather
    than the segment count -- the segment count is the half the dedup repairs.

    THE ASSERTION IS NOT ``len(result) == 2``. That is equally true of a run in which
    only two seeds ever existed, which is precisely the fixture gap that kept this
    clause unexecuted for as long as it has existed. What pins it is the debug dict:
    THREE seeds cleared the seed floor and grew, all three grown areas sit inside both
    area guards, and ``grown_mask_count`` is 2 -- leaving the overlap skip as the only
    clause that can account for the missing one.
    """
    comp, blob_a, blob_b, dim_band, sat, value = _support_split_by_a_dim_band()

    result, debug = S._split_component_via_local_support(comp, sat, value, None, None, _MIN)

    # --- the run positively took the duplicate branch ------------------------
    # Three supported seeds over a component holding TWO sub-blobs.
    assert debug["support_component_count"] == 3, debug
    assert len(debug["seed_areas"]) == 3, debug
    assert len(debug["grown_areas"]) == 3, debug

    seed_floor = max(int(_MIN * 0.35), 180)
    grown_floor = max(int(_MIN * 0.8), 1000)
    upper_guard = int(debug["active_area"] * 0.8)

    # Every seed cleared the seed floor, so every seed was grown ...
    assert all(area >= seed_floor for area in debug["seed_areas"]), (seed_floor, debug)
    # ... and every grown area sits inside BOTH area guards, so neither of them
    # discarded a candidate.
    assert all(grown_floor <= area <= upper_guard for area in debug["grown_areas"]), (
        grown_floor, upper_guard, debug)
    # Three candidates, every other clause satisfied, two masks kept.
    assert debug["grown_mask_count"] == 2, debug

    a_area = int(np.count_nonzero(blob_a))
    b_area = int(np.count_nonzero(blob_b))
    # A propagation bounded by `component_mask` and seeded inside A cannot leave A, so
    # a grown area equal to |A| IS A. Two of the three therefore ARE the same mask,
    # overlap ratio 1.0 against the skip's 0.74.
    assert sorted(debug["grown_areas"]) == sorted([a_area, a_area, b_area]), debug

    # --- and the duplicate is not in the output ------------------------------
    assert len(result) == 2, "expected A once and B once, got %d masks" % len(result)
    assert sum(bool(np.array_equal(mask, blob_a)) for mask in result) == 1, (
        "sub-blob A came back %d times: the duplicate reflood was returned as a second "
        "room, so one patch of floor would become two rooms"
        % sum(bool(np.array_equal(mask, blob_a)) for mask in result)
    )
    assert sum(bool(np.array_equal(mask, blob_b)) for mask in result) == 1, result
    assert debug["accepted"] is True and debug["reason"] == "accepted"
    # The skip is discriminating, not blanket: B shares no pixel with A and survived it.
    assert S._component_overlap_ratio(result[0], result[1]) == (0.0, 0.0)

    kept_a = next(mask for mask in result if np.array_equal(mask, blob_a))
    assert bool(np.all(kept_a[dim_band])), (
        "the dim band is not inside the regrown A mask, so the propagation did not "
        "cross it -- the two seeds would have stayed distinct and there would have "
        "been no duplicate to skip"
    )

    # --- margins, stated so a retune is visible instead of silently re-rejecting
    assert debug["active_area"] == 8000, debug      # active floor 3200, margin +4800
    assert min(debug["seed_areas"]) == 2000, debug  # seed   floor  180, margin +1820
    assert min(debug["grown_areas"]) == 2000, debug # grown  floor 1000, margin +1000
    # A's reflood is 75% of active against an upper guard at 80%.
    assert max(debug["grown_areas"]) * 4 == debug["active_area"] * 3, debug
    assert upper_guard - max(debug["grown_areas"]) >= 400, (
        "A's reflood (%d px) is within 400 px of the upper area guard (%d px of %d "
        "active): tighten that 0.8 any further and this test stops reaching the "
        "overlap skip at all -- the guard would reject the duplicate first and the "
        "result would still be two masks, silently"
        % (max(debug["grown_areas"]), upper_guard, debug["active_area"])
    )


# TWO TESTS WERE WRITTEN HERE AND REMOVED, 2026-11-10, and the arithmetic is the
# reason. They aimed at local_support's `no_supported_body` refusal and its
# duplicate-grown-mask skip; both asserted `== []` and both actually got it from
# `component_count < 2`, a path already covered. Measured: neither moved either line.
#
# `sat_floor` is `percentile(active_sat, 42)` and the test is `>= floor`, so AT LEAST
# 58% of active pixels always satisfy it; `value_floor` is percentile 38, so at least
# 62% satisfy that. At least 20% of any component therefore satisfies BOTH, whatever
# the channels hold -- `supported` cannot be empty before morphology. And a half-zero
# channel puts the percentile AT zero, making `>= 0` true everywhere, which is what
# those fixtures did.
#
# So `no_supported_body` is reachable only if the agreeing pixels are scattered finely
# enough for the 3x3 `binary_opening` to erase them, and the duplicate-grown-mask skip
# only with two support regions that survive labelling separately and then grow into
# the same component.
#
# THE SECOND OF THOSE IS NOW CONSTRUCTED -- `[SP-local-4]` immediately above, added
# 2026-11-11. A dim band splits one sub-blob's SUPPORT in two while leaving the sub-blob
# connected in `component_mask`, so both seeds reflood it and the second mask is a
# duplicate. `no_supported_body` is still constructible and not constructed, and stays
# uncovered rather than covered by a test that asserts a different path -- which is the
# shape `[CAP-6]` in test_core_capabilities.py records.

# ---------------------------------------------------------------------------
# [RCL-1..2] _reclaim_localized_child_mask -- the sparse-top trim
#
# The reclaim grows a clipped child downward. Before it does, it trims sparse
# rows off the TOP -- bleed from whatever clipped it. The trim has a refusal of
# its own, and that refusal is the interesting half.
# ---------------------------------------------------------------------------

def _sparse_topped(top_rows: int, top_width: int, dense_rows: int, dense_width: int):
    """A child mask with `top_rows` thin rows above `dense_rows` full ones."""
    m = np.zeros((120, 120), dtype=bool)
    row = 2
    for _ in range(top_rows):
        m[row, 10:10 + top_width] = True
        row += 1
    for _ in range(dense_rows):
        m[row, 10:10 + dense_width] = True
        row += 1
    return m


def _no_support(shape=(120, 120)):
    """Channels that cannot support any reclaim, so the result is the trim alone."""
    return np.zeros(shape, dtype=np.uint8), np.zeros(shape, dtype=np.uint8)


def test_rcl1_the_trim_refuses_when_it_would_take_too_much():
    """[RCL-1] Trimming is capped: a trim that would cost a third of the mask is refused.

    The sparse top rows are usually bleed. But a child that is MOSTLY sparse rows
    is not a clipped room with bleed on top -- it is a thin region, and trimming
    it would delete the thing itself. So the trim keeps its result only if at
    least 68% of the pixels survive.

    BOTH SIDES IN ONE TEST, because the threshold is the claim and either side
    alone is satisfied by a trim that always refuses (or always accepts):

      sparse top = 30 of 90 px  -> trimming leaves 66%  -> REFUSED, rows survive
      sparse top = 10 of 70 px  -> trimming leaves 86%  -> accepted, rows gone

    The channels are zeroed so no reclaim can happen: the returned mask is the
    trim's answer and nothing else.
    """
    sat, value = _no_support()
    parent = np.ones((120, 120), dtype=bool)

    refused = S._reclaim_localized_child_mask(
        _sparse_topped(top_rows=10, top_width=3, dense_rows=6, dense_width=10),
        parent, primary_sat=sat, primary_value=value,
    )
    assert bool(np.any(refused[2:12, :])), (
        "the trim removed the sparse top of a mostly-sparse child -- that child "
        "is a thin region, not a clipped room with bleed above it"
    )

    accepted = S._reclaim_localized_child_mask(
        _sparse_topped(top_rows=10, top_width=1, dense_rows=6, dense_width=10),
        parent, primary_sat=sat, primary_value=value,
    )
    assert not bool(np.any(accepted[2:12, :])), (
        "a child with a genuinely thin bleed on top kept it"
    )


def test_rcl2_an_empty_child_and_a_bottom_edge_child_are_returned_untouched():
    """[RCL-2] Two early exits, and neither is an error.

    An empty child has nothing to reclaim. A child already sitting at the bottom
    edge has nowhere DOWNWARD to grow -- this reclaim only ever grows down, by
    design, because the failure it repairs is upward clipping during localization.

    ⚠ THE BOTTOM-EDGE GUARD IS SUBSUMED, and the probe says by what. Deleting it
    changes NO answer even with support to grow into. Measured on this fixture
    with the guard skipped:

        support pixels: 174   seed pixels: 500   RECLAIMED pixels: 24
        added_area: -34

    The reclaim finds its 24 pixels, and then `binary_closing` -- a dilation
    followed by an erosion -- loses more than that at the ARRAY BORDER, where the
    erosion has no neighbours to keep. `added_area <= 0` then returns the original
    mask, which is exactly what the guard would have returned. Two refusals, one
    answer.

    The guard is therefore an early-out that saves the work, not a behaviour this
    test can see. It is crossed here and said to be crossed. [RCL-3] reaches the
    fallback it hides behind.

    Returning the input unchanged is what lets the caller treat the reclaim as
    always-safe to apply.
    """
    parent = np.ones((120, 120), dtype=bool)
    sat = np.zeros((120, 120), dtype=np.uint8)
    value = np.zeros((120, 120), dtype=np.uint8)
    sat[:, 10:90] = 200
    value[:, 10:90] = 200

    empty = np.zeros((120, 120), dtype=bool)
    assert not bool(np.any(
        S._reclaim_localized_child_mask(
            empty, parent, primary_sat=sat, primary_value=value
        )
    )), "an empty child came back non-empty"

    at_bottom = np.zeros((120, 120), dtype=bool)
    at_bottom[110:120, 10:60] = True
    out = S._reclaim_localized_child_mask(
        at_bottom, parent, primary_sat=sat, primary_value=value
    )
    assert np.array_equal(out, at_bottom), (
        "a child already at the bottom edge was altered; there is nowhere "
        "downward for it to grow, so any change is sideways bleed"
    )


# [RCL-3] WAS WRITTEN HERE AND REMOVED, 2026-11-10, after a THIRD attempt at
# `added_area <= 0` (:276). It asserted that the reclaim never shrinks the child it
# was asked to complete -- a true property -- but measured, it never reached that
# line: the left-edge fixture found no reclaim at all and returned at the
# `not np.any(reclaimed)` guard above, so the assertion held for a reason it did not
# name. Same failure as the two local_support tests removed above.
#
# WHAT THE PROBE DID ESTABLISH, and it is the useful part: `binary_closing` is a
# dilation then an erosion, so AT THE ARRAY BORDER it takes more than it gives. On a
# bottom-edge child the reclaim found 24 pixels and netted -34, which is why that
# fallback exists and why the bottom-edge guard above it is subsumed. Reaching the
# fallback deliberately needs a fixture where a reclaim IS found and the closing
# still loses more -- constructible, not constructed.


# ---------------------------------------------------------------------------
# [SP-oversize-xsite] The oversized GATE and the oversized FLOOR are ONE threshold
#
# ``max(int(min_area_pixels * 10), 120000)`` is written TWICE. Once in
# ``_split_suspicious_component``, as the ``>=`` gate deciding whether to call
# ``_localize_oversized_component`` at all; and once inside
# ``_localize_oversized_component``, as the ``<`` floor on which it refuses. Both
# read ``np.count_nonzero`` of the SAME mask object (the second via
# ``.astype(bool)``, which preserves the count for every dtype) and the SAME
# ``min_area_pixels``, forwarded unchanged. So they are not two validations of one
# value -- they are COMPLEMENTARY halves of one decision: when the gate admits the
# floor cannot fire, and when the floor would fire the gate cannot admit.
#
# WHAT DRIFT COSTS IS SILENCE, which is the whole reason this is anchored. Retune
# one copy and a band of component areas either (a) reaches localize and is turned
# away on its floor, or (b) never reaches localize although its floor would have
# let it through. Either way the localized-bins strategy quietly stops running for
# that band, the cascade falls through to the next strategy, and nothing fails.
# The hazard is a RETUNE, not a typo, so the instrument has to be behavioural.
#
# WHY NOT A SOURCE-TEXT OR AST ANCHOR. Matching the expression's text, or its
# parsed form, reddens when a comment is added beside either line or when a dead
# branch below one of them is removed -- documentation and tidying edits that
# change no behaviour. These tests read only what the two functions DO.
#
# NEITHER CONSTANT IS NAMED BELOW. The boundary is bisected out of the floor's own
# answers and the gate is then measured against it, so the anchor stays correct
# across a DELIBERATE, matched retune of both copies and reddens only on a
# one-sided one.
# ---------------------------------------------------------------------------

_XSITE_H = _XSITE_W = 400
_XSITE_CAP = _XSITE_H * _XSITE_W  # the largest area these fixtures can build


def _xsite_mask_of_exact_area(area: int):
    """One connected component holding EXACTLY ``area`` pixels.

    Whole rows plus a ragged final row. It stays a single connected component, so
    the erosion / opening strategies downstream of the gate behave as they do for
    any solid room blob and cannot win the cascade before the gate is reached.
    """
    flat = np.zeros(_XSITE_CAP, dtype=bool)
    flat[:area] = True
    return flat.reshape(_XSITE_H, _XSITE_W)


def _xsite_uniform_rgb():
    """One flat colour over the whole canvas.

    Deliberate: a uniform colour quantises to a SINGLE feature bin, and one bin
    holding every active pixel sits above ``_localize_oversized_component``'s
    per-bin ``max_bucket``, so no bin is ranked and its candidate loop never runs.
    The function therefore always reaches its floor, and when the floor does not
    fire it declines for a reason that is unambiguously NOT the floor -- which is
    what makes the floor's verdict readable either way.

    It must be a real, shape-matching array and not ``None``: localize's
    primary-rgb guard sits ABOVE the floor, so a ``None`` here would mask the
    floor entirely and every assertion below would pass without ever reaching the
    predicate under test.
    """
    rgb = np.zeros((_XSITE_H, _XSITE_W, 3), dtype=np.uint8)
    rgb[:, :] = (120, 120, 120)
    return rgb


def _xsite_floor_fired(area: int, min_area_pixels: int):
    """Call ``_localize_oversized_component`` directly; report ITS OWN verdict."""
    _masks, debug = S._localize_oversized_component(
        _xsite_mask_of_exact_area(area),
        _xsite_uniform_rgb(),
        None,
        None,
        None,
        None,
        min_area_pixels,
    )
    assert debug.get("reason") != "missing_primary_rgb", (
        "this fixture no longer reaches the oversized floor: localize declined on "
        "its primary-rgb guard, which sits above the floor, so the sample cannot "
        "contain the effect being measured -- " + repr(debug)
    )
    return debug.get("reason") == "below_oversized_floor", debug


def _xsite_gate_admitted(area: int, min_area_pixels: int):
    """Run the cascade; report whether it CALLED localize, and with what result.

    ``_split_suspicious_component`` appends the callee's own debug row, so a
    ``localized_bins`` row in the returned per-method list IS the gate's decision,
    observed without patching or injecting anything. No wall hint is passed, so
    the wall-cut strategy -- the only one tried before the gate -- declines, and
    the gate is therefore always evaluated.
    """
    _masks, _method, entries = S._split_suspicious_component(
        _xsite_mask_of_exact_area(area),
        min_area_pixels,
        primary_rgb=_xsite_uniform_rgb(),
    )
    rows = [entry for entry in entries if entry.get("method") == "localized_bins"]
    return bool(rows), (rows[0] if rows else None), [e.get("method") for e in entries]


_XSITE_BOUNDARY_MEMO: dict[int, int | None] = {}


def _xsite_bisect_floor_boundary(min_area_pixels: int):
    """The smallest area at which the floor does NOT fire, read out of the floor.

    Returns ``None`` when that boundary sits above ``_XSITE_CAP``: for a large
    ``min_area_pixels`` the 10x arm puts the threshold beyond any mask these
    fixtures can build. That is a genuine part of the admissible range (the
    service schema sets ``min=1`` and no upper bound) and the caller asserts it
    differently -- there, both sides must refuse everywhere.
    """
    if min_area_pixels in _XSITE_BOUNDARY_MEMO:
        return _XSITE_BOUNDARY_MEMO[min_area_pixels]
    boundary: int | None
    if not _xsite_floor_fired(1, min_area_pixels)[0]:
        boundary = 1
    elif _xsite_floor_fired(_XSITE_CAP, min_area_pixels)[0]:
        boundary = None
    else:
        low, high = 1, _XSITE_CAP  # fires at low, does not fire at high
        while high - low > 1:
            middle = (low + high) // 2
            if _xsite_floor_fired(middle, min_area_pixels)[0]:
                low = middle
            else:
                high = middle
        boundary = high
    _XSITE_BOUNDARY_MEMO[min_area_pixels] = boundary
    return boundary


@pytest.mark.parametrize(
    "min_area_pixels",
    [
        -1,       # the service schema rejects it; nothing inside the segmentor does
        0,
        1,        # the schema's minimum
        _MIN,     # 200, this file's shared value
        12000,    # hinge: both arms of the max() land on the same number
        12001,    # the 10x arm has just taken over, so the boundary is no longer
                  # the constant -- a retune of either arm shows up here
        15000,    # 10x arm, clear of the constant
        10 ** 6,  # threshold above any constructible mask
        10 ** 9,  # the schema sets no upper bound
    ],
)
def test_sp_oversize_xsite_gate_and_floor_never_disagree(min_area_pixels):
    """[SP-oversize-xsite] The cascade's oversized gate and localize's own floor
    are complementary at every area, over the whole admissible ``min_area_pixels``
    range.

    RED IF EITHER COPY OF THE THRESHOLD IS RETUNED WITHOUT THE OTHER, in either
    direction:
      - lower the gate alone -> it admits a band the floor still refuses, so
        localize is called and turns straight round (``below_oversized_floor``
        arrives in the cascade's diagnostics, which it can never do today);
      - raise the gate alone, or lower the floor alone -> a band where the floor
        would have passed is never offered to localize at all, and gate and floor
        are then both False for the same area.
    Nothing else in this file can see either state: the cascade's RETURN VALUE is
    identical, because it just falls through to the next strategy.
    """
    boundary = _xsite_bisect_floor_boundary(min_area_pixels)
    if boundary is None:
        areas = [1, _MIN, 3200, _XSITE_CAP]
    else:
        areas = sorted(
            {
                1,
                boundary // 2,
                boundary - 1,
                boundary,
                _XSITE_CAP,
            }
        )
        areas = [area for area in areas if 1 <= area <= _XSITE_CAP]

    transcript = []
    disagreements = []
    dead_band = []
    admitted_flags = []
    fired_flags = []
    for area in areas:
        admitted, localize_row, methods = _xsite_gate_admitted(area, min_area_pixels)
        if admitted:
            # The cascade handed back localize's OWN debug row, so the floor's
            # verdict for this very call is already in hand -- an end-to-end
            # reading, and better evidence than a second, separate call.
            floor_reason = localize_row.get("reason")
            floor_area = localize_row.get("active_area")
            floor_source = "cascade row"
        else:
            # The gate refused, so localize was never run: ask it directly what
            # it WOULD have said. This is the counterfactual that catches a gate
            # raised above a floor that would have let the area through.
            _fired, floor_debug = _xsite_floor_fired(area, min_area_pixels)
            floor_reason = floor_debug.get("reason")
            floor_area = floor_debug.get("active_area")
            floor_source = "direct call"
        floor_fired = floor_reason == "below_oversized_floor"
        admitted_flags.append(admitted)
        fired_flags.append(floor_fired)
        transcript.append(
            f"    area={area} gate_admitted={admitted} floor_fired={floor_fired}"
            f" floor.active_area={floor_area}"
            f" floor.reason={floor_reason!r} (via {floor_source})"
            f" cascade.methods={methods}"
        )
        if admitted == floor_fired:
            disagreements.append(area)
        if admitted and floor_fired:
            dead_band.append(area)

    detail = f"\n  min_area_pixels={min_area_pixels} floor_boundary={boundary}\n" + "\n".join(transcript)

    assert not dead_band, (
        "the cascade called localize with an area localize refused on its own "
        f"oversized floor (areas {dead_band}); the gate is now below the floor, so "
        "the localized-bins strategy silently does not run for that whole band"
        + detail
    )
    assert not disagreements, (
        "the cascade's oversized gate and localize's oversized floor disagree at "
        f"areas {disagreements}: both said the same thing about one area, where one "
        "is a `>=` and the other a `<` on the same count of the same mask. One copy "
        "of the threshold has been retuned without the other" + detail
    )

    # A pass has to be attributable, so say which regime this case actually
    # exercised rather than trusting that it exercised one.
    if boundary is None:
        assert not any(admitted_flags) and all(fired_flags), (
            "this case is meant to be the above-the-ceiling regime, where the 10x "
            "arm puts the threshold beyond any constructible mask and BOTH sides "
            "refuse at every area; it is no longer that" + detail
        )
    else:
        assert any(admitted_flags) and not all(admitted_flags), (
            "this case saw only one side of the boundary, so it could not have "
            "detected a disagreement; the sweep must straddle it" + detail
        )


def test_sp_oversize_xsite_floor_early_return_is_unreachable_from_the_cascade():
    """[SP-oversize-xsite] ``below_oversized_floor`` is reachable ONLY by a direct
    call, never through ``_split_suspicious_component``.

    This is the companion that stops the assertion above from being vacuous. The
    claim is that a reason string never arrives by one route; on its own that is
    also what a reason string nobody can produce at all would look like. So the
    same fixture is driven BOTH ways across the boundary: directly, where the
    floor's early return must fire and name itself, and through the cascade, where
    it must never appear.
    """
    boundary = _xsite_bisect_floor_boundary(_MIN)
    assert boundary is not None and boundary > 1, (
        f"the floor's boundary is not constructible here ({boundary}), so neither "
        "half of this contrast can be built"
    )

    direct_reasons = []
    cascade_reasons = []
    for area in (1, boundary // 2, boundary - 1, boundary, _XSITE_CAP):
        _fired, floor_debug = _xsite_floor_fired(area, _MIN)
        direct_reasons.append((area, floor_debug.get("reason")))
        _admitted, localize_row, _methods = _xsite_gate_admitted(area, _MIN)
        cascade_reasons.append((area, None if localize_row is None else localize_row.get("reason")))

    assert any(reason == "below_oversized_floor" for _area, reason in direct_reasons), (
        "the direct half of the contrast produced no floor refusal, so the "
        f"cascade half proves nothing: {direct_reasons}"
    )
    assert all(reason != "below_oversized_floor" for _area, reason in cascade_reasons), (
        "localize's below-the-floor early return was reached THROUGH the cascade. "
        "It is unreachable that way while the gate and the floor share a threshold, "
        f"so the two copies have drifted apart: cascade={cascade_reasons} "
        f"direct={direct_reasons}"
    )


# --- [SP-hue-floor] / [SP-hue-sample]: the net the deleted emptiness guard left behind -
#
# D1, 2026-11-11: `_split_component_via_assist_hue` lost an `if len(hue_values) == 0`
# check that sat on `assist_hue[active]`. It was unreachable, so its deletion removes no
# safety net -- it TRANSFERS the net to the two facts the comment on that splitter's
# area floor now names, and these tests are what make those facts assertable. The floor
# is the guard that killed it, so the floor is the thing tested.


def _hue_floor_refusal(min_area_pixels: int, pixels: int, side: int) -> bool:
    """True when the assist-hue splitter refuses an ``active`` of exactly ``pixels``
    AT ITS AREA FLOOR (as opposed to any refusal further down the body)."""
    shape = (side, side)
    mask = np.zeros(side * side, dtype=bool)
    mask[:pixels] = True
    _masks, debug = S._split_component_via_assist_hue(
        mask.reshape(shape),
        np.zeros(shape, np.uint8),
        np.full(shape, 200, np.uint8),
        np.full(shape, 200, np.uint8),
        min_area_pixels,
    )
    assert debug["active_area"] == pixels, (
        f"active_area {debug['active_area']} != the {pixels} pixels the fixture set, "
        "so the sat/value gates no longer admit them -- re-tune the fixture, not the "
        "assertion. This cannot see a DTYPE change: active_area is "
        "np.count_nonzero(active), identical for a bool and an integer `active`; "
        "[SP-hue-sample] is what catches that."
    )
    return debug["reason"] == "below_active_area_floor"


def _measure_active_area_floor(min_area_pixels: int, *, side: int = 200,
                               max_side: int = 1600) -> int:
    """Bisect the active-area floor out of ``_split_component_via_assist_hue`` itself.

    Returns the smallest ``active_area`` that gets PAST that floor -- read from the
    function's own refusal reason, never restated from the ``3500`` literal in
    segmentor.py, so retuning the source constant moves this number and every
    assertion built on it. ``0`` means an EMPTY ``active`` already passes, i.e. there
    is no floor left at all.
    """
    while _hue_floor_refusal(min_area_pixels, side * side, side):
        if side >= max_side:
            pytest.fail(
                f"the floor for min_area_pixels={min_area_pixels} sits above this "
                f"probe's {side * side}-pixel ceiling; raise `max_side` rather than "
                "weakening the assertion"
            )
        side *= 2
    if not _hue_floor_refusal(min_area_pixels, 0, side):
        return 0
    low, high = 0, side * side
    while high - low > 1:
        mid = (low + high) // 2
        if _hue_floor_refusal(min_area_pixels, mid, side):
            low = mid
        else:
            high = mid
    return high


@pytest.mark.parametrize(
    "min_area_pixels",
    [-(10**9), -1000, -1, 0, 1, 2, 3, 10, 100, 1000, 1944, 1945, 2000,
     10_000, 100_000, 10**6, 10**9],
)
def test_sp_hue_floor_an_empty_active_always_stops_at_the_floor(min_area_pixels):
    """[SP-hue-floor] the assist-hue splitter refuses an EMPTY ``active`` AT ITS AREA
    FLOOR, for every ``min_area_pixels`` the service can deliver.

    This is the guard that KILLED the ``len(hue_values) == 0`` check deleted from that
    splitter: the floor cannot evaluate below 3500 anywhere in the admissible range, so
    reaching ``assist_hue[active]`` implies ``active_area >= 3500``, and that sample's
    length IS ``active_area`` ([SP-hue-sample] pins the other half). Deleting the dead
    check transferred the whole net to this floor, which is why the floor -- and not the
    deleted line -- is what is tested here.

    RANGE: the ``min_area_pixels`` service field is
    ``vol.All(vol.Coerce(int), vol.Range(min=1))`` with NO upper bound
    (``mapping/mapping_services.py``), hence 1 -> 10**9. 0 and negatives are robustness
    rows: a direct caller can pass them, ``detect_room_segments`` cannot, because it
    clamps with ``int(max(min_area_pixels, 1))``. 1944/1945 straddle the point where
    ``int(min_area_pixels * 1.8)`` overtakes the 3500 constant.

    BITES ON deleting the ``if active_area < max(...)`` guard: the refusal then slides
    down to ``insufficient_ranked_bins``, which is where an empty sample actually lands
    (``np.unique`` of an empty array yields no bins, so ``ranked_bins == []``) -- no
    crash, which is precisely why the deleted check was never load-bearing.
    ALSO BITES ON ``3500`` -> ``0``, via the 0/negative rows. A retune to any value
    >= 1 does NOT redden it, and should not: the deleted check stays unreachable for
    any floor of at least one pixel.
    """
    shape = (200, 200)
    component = np.ones(shape, dtype=bool)
    hue = np.zeros(shape, np.uint8)
    sat = np.zeros(shape, np.uint8)        # sat >= 16 false everywhere -> active empty
    value = np.full(shape, 200, np.uint8)

    masks, debug = S._split_component_via_assist_hue(
        component, hue, sat, value, min_area_pixels
    )

    assert debug["active_area"] == 0, (
        f"the fixture failed to empty `active` (active_area={debug['active_area']}), "
        "so the state under test was never presented"
    )
    assert debug["reason"] == "below_active_area_floor", (
        "an empty `active` got past the area floor and reached the hue sample "
        f"(reason={debug['reason']!r}) -- that is the state the deleted "
        "`len(hue_values) == 0` guard used to absorb, and the floor is now the only "
        "thing standing in front of it"
    )
    assert masks == []


@pytest.mark.parametrize(
    "min_area_pixels",
    [-(10**9), -1, 0, 1, 2, 10, 100, 1000, 1944, 1945, 2000, 10_000, 100_000],
)
def test_sp_hue_floor_the_measured_floor_never_admits_an_empty_sample(min_area_pixels):
    """[SP-hue-floor] the area floor, BISECTED out of the splitter instead of read off
    the source literal, is always at least one pixel.

    The complement of the test above: that one is behavioural and catches the guard
    being deleted or weakened, this one is the dominance arithmetic and catches a
    RETUNE -- and it names no threshold, so it moves with segmentor.py rather than
    against it. 10**6 and 10**9 are left to the empty-active test instead, which is O(1)
    in the floor: 10**9's floor is past this probe's 1600x1600 ceiling, and 10**6's fits
    but costs ~20 bisection steps over 2.56e6-pixel arrays for nothing the other rows do
    not already establish.

    BITES ON ``3500`` -> ``0`` (the 0 and negative rows then measure a floor of 0) and
    on deleting the guard outright (every row measures 0).
    """
    floor = _measure_active_area_floor(min_area_pixels)
    assert floor >= 1, (
        f"the active-area floor measured {floor} for min_area_pixels="
        f"{min_area_pixels}: an EMPTY `active` now reaches `assist_hue[active]`, and "
        "the emptiness check that used to sit there was deleted as unreachable"
    )


def test_sp_hue_sample_is_exactly_the_active_pixels():
    """[SP-hue-sample] the sample the assist-hue splitter bins is ``assist_hue`` AT the
    active pixels and nothing else -- the second half of the invariant that kept the
    deleted ``len(hue_values) == 0`` check unreachable.

    ``len(assist_hue[active]) == active_area`` holds only while ``active`` is a BOOLEAN
    mask of ``assist_hue``'s shape. As an integer array the same expression is silently
    FANCY INDEXING: it selects ROWS, so its length becomes ``shape[0]`` and it pulls in
    hue from outside the component (measured on one 200x200 mask, bool -> 26 values,
    uint8 -> 200). Three sibling splitters in this module build ``active`` with
    ``component_mask.astype(bool)`` while this one builds it by comparison, so an edit
    harmonising that line is the realistic way the invariant dies.

    Asserted as a DIFFERENTIAL, because the sample's length is not published in
    ``debug``: hue outside ``active`` must not move the answer. The POSITIVE CONTROL
    runs first -- hue inside ``active`` does move it -- so the null below has a
    demonstrated detection floor rather than being a clean result from a probe that
    could not see a difference either way. Both runs also assert WHICH branch they
    reached, and the fixture is sized from the MEASURED floor, so a retune cannot park
    this test below the floor where it would pass vacuously.

    BITES ON ``active = component_mask & ...`` becoming
    ``active = component_mask.astype(np.uint8) & ...``: the control and the null both
    fail, because every run's sample then collapses to rows 0-1 of ``assist_hue``.
    """
    shape = (200, 200)
    sat = np.full(shape, 200, np.uint8)
    value = np.full(shape, 200, np.uint8)

    floor = _measure_active_area_floor(_MIN)
    assert floor >= 1
    rows = floor // 80 + 10                      # a block comfortably past the floor
    component = np.zeros(shape, dtype=bool)
    component[20:20 + rows, 40:120] = True
    assert int(np.count_nonzero(component)) > floor
    assert not bool(component[:2].any()), (
        "rows 0-1 must sit OUTSIDE the component: a uint8 `active` holds only 0s and "
        "1s, so the fancy-indexing failure this test exists to catch resamples exactly "
        "those two rows, and it would hide if they were inside"
    )

    flat_hue = np.zeros(shape, np.uint8)         # a single bin, inside and outside alike
    _masks, base = S._split_component_via_assist_hue(
        component, flat_hue, sat, value, _MIN
    )
    assert base["reason"] == "insufficient_ranked_bins", (
        f"the fixture stopped at {base['reason']!r} instead of reaching the hue "
        "sample; resize it against the measured floor"
    )

    # POSITIVE CONTROL -- hue INSIDE `active` moves the answer, so this probe can see
    # a change in the sample at all.
    inside_hue = flat_hue.copy()
    inside_hue[20:20 + rows // 2, 40:120] = 12   # one bin over: ranked 2, selected 1
    _masks, moved = S._split_component_via_assist_hue(
        component, inside_hue, sat, value, _MIN
    )
    assert moved != base, (
        "changing hue inside `active` changed nothing in the debug, so this probe "
        "cannot detect a change in the sample and the null below proves nothing"
    )
    assert moved["reason"] == "insufficient_selected_bins", (
        f"the control reached {moved['reason']!r}; it is meant to add a second ranked "
        "bin one step away, which ranks but cannot be selected"
    )

    # THE NULL, with that detection floor established -- hue OUTSIDE `active` cannot.
    outside_hue = flat_hue.copy()
    spread = ((np.arange(shape[0] * shape[1]).reshape(shape) % 15) * 12).astype(np.uint8)
    outside_hue[~component] = spread[~component]
    masks, null = S._split_component_via_assist_hue(
        component, outside_hue, sat, value, _MIN
    )

    assert null == base, (
        "hue from OUTSIDE the active mask reached the splitter's sample: "
        f"{null!r} != {base!r}. `assist_hue[active]` is a masked selection only while "
        "`active` is boolean; as an integer array it indexes rows instead"
    )
    assert masks == []

# --- D2: the floor that retired `no_feature_values` -------------------------
#
# `_localize_oversized_component` used to re-check `len(feature_values) == 0`
# right after quantizing the colour features. It is DELETED, which transfers its
# net to the active-area floor earlier in the same function -- so that floor is
# now load-bearing and gets a behavioural test of its own.
#
# WHY IT COULD NOT FIRE -- one reason, with a second condition that closes the
# only other mechanism. MEASURED: with the floor ablated and the check still in
# place, `no_feature_values` fires (33 of 156 probe cells). So the floor is the
# SOLE reason the check was dead; it is not independently dead. The length
# identity below closes the other way it could have been live -- `len` differing
# from `count_nonzero(active)` -- and is pinned separately.
#
# WHICH LITERALS ARE LOAD-BEARING HERE, stated rather than claimed away: the
# floor itself is never restated -- it is bisected out of the function's own
# verdicts. `_OVERSIZE_SWEEP`'s crossover partition IS fixed externally, and
# deliberately: it is the only thing that can notice the absolute term being
# retuned DOWNWARDS, because every property derived purely from the measurements
# stays self-consistent under a uniform shift. See the dominance test.

#: `min_area_pixels` across the service's admissible range -- `mapping_services`
#: admits any int >= 1 and `segmenter_engines` re-checks it is positive -- plus 0
#: and negatives, which no service call can produce but an internal caller could.
#: One value per distinct regime: non-admissible, the service minimum, the
#: default, either side of today's crossover where the proportional term
#: overtakes the absolute one, and one tuning well inside that regime.
_OVERSIZE_SWEEP = (-5000, 0, 1, 1200, 11999, 12000, 12001, 20000)

#: Where the bisection STARTS looking -- NOT a bound on the floor. The search
#: doubles from here until it finds an area that clears the floor, so retuning
#: the source UPWARDS moves the search instead of reddening the test. The limit
#: only stops a runaway from allocating an absurd canvas.
_OVERSIZE_SEARCH_START = 220000
_OVERSIZE_SEARCH_LIMIT = 4_000_000


def _oversize_canvas(active_area):
    """A component mask with exactly `active_area` live pixels, uniformly coloured.

    ONE colour on purpose. A single colour bin then holds the whole component, so
    it sits above the function's own bucket ceiling (`active_area * 0.24`) and
    nothing ranks -- the body runs all the way to its
    `insufficient_localized_candidates` exit without entering the candidate loop,
    which is the only part that touches scipy. These tests therefore exercise no
    scipy at all, even though the module gate at the top of this file skips the
    whole file on a host without it.
    """
    side = max(8, int(np.ceil(np.sqrt(active_area + 1))) + 1)
    comp = np.zeros((side, side), dtype=bool)
    comp.reshape(-1)[:active_area] = True
    rgb = np.zeros((side, side, 3), dtype=np.uint8)
    rgb[comp] = (210, 70, 70)
    return comp, rgb


def _oversize_reason(min_area_pixels, active_area):
    """The `debug["reason"]` the localizer records for that (tuning, area) pair."""
    comp, rgb = _oversize_canvas(active_area)
    masks, debug = S._localize_oversized_component(
        comp, rgb, None, None, None, None, min_area_pixels
    )
    # The fixture must be the thing the function measured, or the sweep below is
    # measuring a canvas-building bug instead of the floor.
    assert debug["active_area"] == active_area, (
        "fixture built %d live pixels but the function counted %d"
        % (active_area, debug["active_area"])
    )
    assert masks == [], "a uniformly coloured component split; fixture is wrong"
    return debug["reason"]


@functools.lru_cache(maxsize=None)
def _measured_oversize_floor(min_area_pixels):
    """The smallest active area that gets PAST the floor, bisected from behaviour."""
    below = "below_oversized_floor"
    assert _oversize_reason(min_area_pixels, 0) == below, (
        "an EMPTY active mask reached the body at min_area_pixels=%d, so the floor "
        "no longer stops it and `quantized[active]` can be empty in there again"
        % min_area_pixels
    )
    hi = _OVERSIZE_SEARCH_START
    while _oversize_reason(min_area_pixels, hi) == below:
        assert hi < _OVERSIZE_SEARCH_LIMIT, (
            "no active area up to %d clears the floor at min_area_pixels=%d -- the "
            "floor could not be measured" % (hi, min_area_pixels)
        )
        hi = min(hi * 2, _OVERSIZE_SEARCH_LIMIT)
    lo = 0
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _oversize_reason(min_area_pixels, mid) == below:
            lo = mid
        else:
            hi = mid
    return hi


@pytest.mark.parametrize("min_area_pixels", _OVERSIZE_SWEEP)
def test_sp_oversize_floor_absorbs_every_undersized_component(min_area_pixels):
    """[SP-oversize-floor] The floor is load-bearing: nothing undersized gets in.

    This is the behavioural test the deleted `no_feature_values` check handed its
    net to. Delete the `if active_area < max(...)` guard from
    `_localize_oversized_component` and every parametrisation here fails on the
    empty-mask assertion inside `_measured_oversize_floor` -- measured, along with
    the older `test_localize_oversized_below_floor` above, which reddens too. That
    older test pins ONE area at one tuning; this one pins the whole admissible
    range and, unlike it, names no constant.

    TIER, STATED PLAINLY: this calls the localizer DIRECTLY, with real arrays and
    nothing patched, because the floor cannot be reached through the pipeline at
    all -- the gate in `_split_suspicious_component` applies the same threshold to
    the same mask first (which is what `[SP-oversize-xsite]` pins). So the unit
    tier is the only tier at which this floor is observable.
    """
    floor = _measured_oversize_floor(min_area_pixels)
    assert floor > 0, (
        "the measured floor admits an empty active mask at min_area_pixels=%d"
        % min_area_pixels
    )
    for area in sorted({0, 1, floor // 2, floor - 1}):
        assert _oversize_reason(min_area_pixels, area) == "below_oversized_floor", (
            "active_area=%d reached the body (floor measured at %d, "
            "min_area_pixels=%d)" % (area, floor, min_area_pixels)
        )
    # POSITIVE CONTROL. Without it every assertion above would also hold on a
    # function that refused everything, and the sweep would be measuring nothing.
    # One pixel more than the measured floor and the body runs to its own exit.
    assert _oversize_reason(min_area_pixels, floor) == (
        "insufficient_localized_candidates"
    ), "the measured floor is a closed door, not a floor"


def test_sp_oversize_floor_is_absolute_not_proportional():
    """[SP-oversize-dominance] The arithmetic that made `no_feature_values` dead.

    Three properties:

    1. For every swept tuning the floor is strictly positive, so `active` is never
       empty by the time the body indexes with it. This is the property the
       deletion actually rests on.
    2. Across the low end the floor is one CONSTANT and is not bought down by a
       small `min_area_pixels` -- which is what the `max(proportional, absolute)`
       shape means. Collapse the `max` to the bare proportional term and this
       fails.
    3. The proportional term still takes over once `min_area_pixels` is large
       enough, so the `max` is live in both directions. The tuning used here is
       DERIVED from the measured absolute term, not restated, so this stays green
       when the source is retuned.

    SCOPE, HONESTLY. Property 2 partitions the sweep at a crossover fixed in
    `_OVERSIZE_SWEEP`, and that partition is the one externally-fixed number in
    this block. It is deliberate: a retune of the absolute term DOWNWARDS leaves
    every self-derived property self-consistent, so nothing derived from the
    measurements alone could notice it. Consequence, both ways: retuning the
    absolute term down reddens this (measured), retuning it up does not (also
    measured). A one-sided retune of the :656/:888 replica pair is a different
    hazard and is `[SP-oversize-xsite]`'s job, not this test's.
    """
    floors = {m: _measured_oversize_floor(m) for m in _OVERSIZE_SWEEP}
    assert all(f > 0 for f in floors.values()), floors

    low = [m for m in _OVERSIZE_SWEEP if m <= 11999]
    plateau = {floors[m] for m in low}
    assert len(plateau) == 1, (
        "the floor varies across the low end of the range (%s), so it is no longer "
        "absolute there" % {m: floors[m] for m in low}
    )
    absolute = plateau.pop()
    assert all(absolute >= int(m * 10) for m in low), (
        "the absolute term no longer dominates the proportional one at the low end "
        "(absolute=%d, tunings=%s)" % (absolute, low)
    )
    assert any(absolute > int(m * 10) for m in low), (
        "the absolute term never strictly exceeds the proportional one, so the "
        "`max` is indistinguishable from the bare proportional term (absolute=%d)"
        % absolute
    )
    # The crossover tuning is DERIVED from what was just measured: the smallest
    # integer whose proportional term exceeds the absolute one.
    crossover = absolute // 10 + 1
    assert _measured_oversize_floor(crossover) > absolute, (
        "the proportional term never overtakes the absolute one (floor at "
        "min_area_pixels=%d is %d, absolute is %d)"
        % (crossover, _measured_oversize_floor(crossover), absolute)
    )


def test_sp_oversize_boolean_index_length_is_the_active_count():
    """[SP-oversize-identity] `len(quantized[active])` IS `count_nonzero(active)`.

    The second CONDITION behind the deletion -- not a second independent reason.
    It closes the other way `len(feature_values) == 0` could have been live: `len`
    differing from the active count. A boolean index over the leading axes returns
    one ROW per live pixel, so the length is zero exactly when the mask is empty,
    which the floor already refuses.

    Pinned across channel counts including `(N, 0)`, the strongest attack on the
    identity: a zero-width feature axis makes every row empty, and `len` still
    counts the rows and not the columns.

    SCOPE, stated plainly: the identity itself is a property of numpy, so no edit
    to `segmentor.py` can redden the loop -- it is documentation, and said so.
    The final assertion is the part with a failure mode: change
    `normalized_color_features` to return anything but one channel per input
    channel and it goes red, which is also what would break the `axis=2` bin
    comparison in the localizer's candidate loop.
    """
    for chans in (0, 1, 3, 4):
        for area in (0, 1, 7, 4096):
            comp = np.zeros((96, 96), dtype=bool)
            comp.reshape(-1)[:area] = True
            quantized = np.zeros((96, 96, chans), dtype=np.int16)
            rows = quantized[comp]
            assert rows.shape == (area, chans)
            assert len(rows) == int(np.count_nonzero(comp)) == area, (
                "chans=%d area=%d gave len=%d" % (chans, area, len(rows))
            )

    rgb = np.zeros((40, 40, 3), dtype=np.uint8)
    assert S._normalized_color_features(rgb).shape == (40, 40, 3), (
        "the feature array is no longer one channel per input channel, so the "
        "localizer's `axis=2` bin comparison and the identity above both move"
    )

# ---------------------------------------------------------------------------
# [SP-D3-1..4] the net under `_localize_oversized_component._try_add_candidate`
# now that its `count <= 0` refusal is gone (deleted 2026-11-11).
#
# The closure opened a seed mask, returned early if nothing survived the opening
# (`np.any(opened)` -- Guard A), labelled what did, and then refused a second
# time on `count <= 0`. That second refusal was the only `<= 0` of the six
# `_NDIMAGE.label()` call sites in the module: four guard with `< 2`, which has
# real bite because `count == 1` is routine, and one carries no count guard at
# all. It was NOT a mistyped `< 2` -- this closure accumulates candidates across
# up to ten separate calls, so a single-component seed is genuinely useful here,
# unlike the splitters that need >= 2 components to BE a split. The bound was
# correct for this call site and simply vacuous.
#
# Measured before deleting it: 847 arrivals at that `label()` -- the committed
# fixture maps through `detect_room_segments`, plus a direct sweep of
# `min_area_pixels` over 1..1000000 against five band counts with assist
# channels on and off -- every one with `np.any(opened)` true, the lowest count
# seen 1, and the guard firing 0 times.
#
# BE HONEST ABOUT THE INSTRUMENT. [SP-D3-1] and [SP-D3-3] pin SCIPY, not our
# code: they are a dependency ratchet. They go red if scipy changes what
# `label()` counts or how `find_objects` indexes it, and they do not move when
# anyone edits segmentor.py. [SP-D3-2] is the one that holds without scipy's
# cooperation -- the empty `range` that makes the deletion safe whatever a count
# of 0 is taken to mean. [SP-D3-4] is the behavioural test on Guard A, and its
# docstring states what it can and cannot catch.
# ---------------------------------------------------------------------------

# A COPY of the 3x3 structure `_localize_oversized_component` builds for
# `_try_add_candidate`. That is a function-local, so no test can read it: if it is
# ever retuned (to 4-connectivity, say) this copy desynchronises silently and
# nothing in [SP-D3-1..4] notices. Measured -- the pre-existing localized-candidate
# tests (test_ecv26, test_ecv32) are what catch such a retune.
_D3_STRUCTURE = np.ones((3, 3), dtype=bool)


def _d3_label_masks():
    """(name, mask) pairs for the library-contract sweep.

    Deliberately includes shapes a 3x3 opening would destroy (single pixels,
    checkerboards): `label()`'s count contract is worth asserting for its own
    sake, not only over the masks `_try_add_candidate` can actually produce.
    """
    masks = []
    masks.append(("all_true", np.ones((40, 40), dtype=bool)))
    m = np.zeros((40, 40), dtype=bool)
    m[20, 20] = True
    masks.append(("single_pixel_centre", m))
    m = np.zeros((40, 40), dtype=bool)
    m[0, 0] = True
    masks.append(("single_pixel_corner", m))
    m = np.zeros((40, 40), dtype=bool)
    m[-1, -1] = True
    masks.append(("single_pixel_far_corner", m))
    m = np.zeros((40, 40), dtype=bool)
    m[5, :] = True
    masks.append(("one_full_row", m))
    m = np.zeros((40, 40), dtype=bool)
    m[:, 5] = True
    masks.append(("one_full_column", m))
    m = np.zeros((40, 40), dtype=bool)
    for top in (2, 20):
        for left in (2, 20):
            m[top:top + 6, left:left + 6] = True
    masks.append(("four_disconnected_blocks", m))
    rows, cols = np.indices((40, 40))
    masks.append(("checkerboard", ((rows + cols) % 2 == 0)))
    masks.append(("checkerboard_inverse", ((rows + cols) % 2 == 1)))
    masks.append(("one_by_one", np.ones((1, 1), dtype=bool)))
    m = np.zeros((1, 400), dtype=bool)
    m[0, ::3] = True
    masks.append(("single_row_every_third", m))
    m = np.zeros((400, 1), dtype=bool)
    m[::3, 0] = True
    masks.append(("single_column_every_third", m))
    rng = np.random.default_rng(20261111)
    for density in (0.001, 0.01, 0.1, 0.5, 0.9, 0.999):
        masks.append(("random_p%s" % density, rng.random((60, 60)) < density))
    # Shapes THICK enough to survive a 3x3 opening. The thin shapes above are
    # erased by it, so without these [SP-D3-3] would cross Guard A only a handful
    # of times and would be proving far less than it looks like it is.
    m = np.zeros((60, 60), dtype=bool)
    for top in (2, 22, 42):
        for left in (2, 22, 42):
            m[top:top + 8, left:left + 8] = True
    masks.append(("nine_thick_blocks", m))
    m = np.zeros((40, 40), dtype=bool)
    m[4:14, :] = True
    m[24:34, :] = True
    masks.append(("two_thick_bands", m))
    m = np.zeros((40, 40), dtype=bool)
    m[4:36, 4:36] = True
    m[12:28, 12:28] = False
    masks.append(("thick_ring", m))
    m = np.zeros((40, 40), dtype=bool)
    m[4:36, 4:12] = True
    m[28:36, 4:36] = True
    masks.append(("thick_l_shape", m))
    return masks


_D3_LABEL_MASKS = _d3_label_masks()


@pytest.mark.parametrize(
    "mask",
    [mask for _name, mask in _D3_LABEL_MASKS],
    ids=[name for name, _mask in _D3_LABEL_MASKS],
)
def test_sp_d3_1_label_count_contract_over_mask_shapes(mask):
    """[SP-D3-1] A scipy DEPENDENCY RATCHET, not a behavioural test.

    `_try_add_candidate` now goes straight from `label()` to `find_objects()` and
    indexes the result by `label_index - 1` over `range(1, count + 1)`. Four
    properties of scipy carry that, and this pins all four so a scipy change
    announces itself here rather than as a mis-shaped room on someone's map.

    It cannot see a single edit to segmentor.py. That is the point of saying so.
    """
    assert np.any(mask), (
        "fixture bug: this sweep is for NON-empty masks; [SP-D3-2] takes the "
        "empty one, and an empty mask here would make every assertion vacuous"
    )
    labeled, count = S._NDIMAGE.label(mask, structure=_D3_STRUCTURE)

    assert count >= 1, (
        "a mask with a True pixel labelled to count=%d. The deleted `count <= 0` "
        "refusal in `_try_add_candidate` was unreachable precisely BECAUSE this "
        "cannot happen past its `np.any(opened)` guard" % count
    )
    assert int(labeled.max()) == count, (
        "label ids are not 1..count with no gaps (max=%d, count=%d). "
        "`_try_add_candidate` walks `range(1, count + 1)` and indexes "
        "`find_objects` output by `label_index - 1`; a gap desynchronises the two"
        % (int(labeled.max()), count)
    )
    slices = S._NDIMAGE.find_objects(labeled)
    assert len(slices) == count, (
        "find_objects returned %d slices for %d features; the "
        "`label_index - 1 < len(slices)` bound would start silently skipping "
        "real components" % (len(slices), count)
    )
    assert all(entry is not None for entry in slices), (
        "find_objects returned a None entry. Gapless ids are what guarantee it "
        "never does, and the `label_slice is None` skip just below is the only "
        "thing between a None and `labeled[None]`"
    )


def test_sp_d3_2_an_empty_mask_makes_the_candidate_loop_a_no_op():
    """[SP-D3-2] The structural fact that makes the D3 deletion safe WITHOUT scipy.

    This is the one of the four that does not lean on what scipy chooses to
    report as a count. Whatever a count of 0 means, `range(1, count + 1)` is
    empty, so `_try_add_candidate`'s loop body cannot execute and nothing is
    appended -- which is exactly what the deleted `count <= 0` refusal achieved,
    one statement later and at the cost of two lines.

    This is not a theoretical reliance. The sibling `label()` call in
    `_detect_room_segments_pipeline` carries no count guard at all and leans on
    precisely this; measured over the committed fixture maps it was handed
    `count == 0` 154 times and the empty range absorbed every one.
    """
    empty = np.zeros((40, 40), dtype=bool)
    labeled, count = S._NDIMAGE.label(empty, structure=_D3_STRUCTURE)

    assert count == 0, "an empty mask labelled to count=%d" % count
    assert int(labeled.max()) == 0
    assert S._NDIMAGE.find_objects(labeled) == [], (
        "find_objects over an all-zero label array was expected to be empty"
    )
    assert list(range(1, count + 1)) == [], (
        "the empty range is the whole net under `_try_add_candidate`. If this is "
        "ever non-empty then the deleted `count <= 0` refusal was load-bearing "
        "after all and the deletion must be reverted"
    )


def test_sp_d3_3_guard_a_dominates_the_deleted_refusal():
    """[SP-D3-3] RATCHET: past `np.any(opened)`, `count <= 0` is unsatisfiable.

    Runs the two steps `_try_add_candidate` runs -- the module's own
    `binary_opening` and `label`, with a COPY of its 3x3 structure -- over seed
    masks, and asserts the deleted predicate is never satisfiable once Guard A
    has let the call through. This is the dominance arithmetic, and it is a
    RATCHET ON SCIPY ONLY: it catches a scipy whose count semantics move, and
    nothing else. It cannot see ANY edit to segmentor.py -- not Guard A being
    deleted, and not Guard A being retuned, because the predicate below is a
    COPY of Guard A's rather than a read of it. Measured: changing Guard A to
    `if opened.size == 0:`, which no longer implies `count >= 1`, leaves this
    test and the whole adapters/eufy suite green. As a detector of OUR
    regressions it is a preference, not a test, and is named one here.

    The sweep asserts its own floor. `crossed` counts the seeds whose opening
    left anything at all, and the test fails if too few did, because a sweep in
    which the opening erased every seed would pass this vacuously -- Guard A
    would have refused every time and the deleted guard would never have been
    reached at all.
    """
    crossed = 0
    for name, seed in _D3_LABEL_MASKS:
        opened = S._NDIMAGE.binary_opening(seed, structure=_D3_STRUCTURE, iterations=1)
        if not bool(np.any(opened)):
            continue  # Guard A refuses here; the deleted guard is never reached
        crossed += 1
        _labeled, count = S._NDIMAGE.label(opened, structure=_D3_STRUCTURE)
        assert count > 0, (
            "%s: crossed Guard A and then labelled to count=%d. The deleted "
            "`count <= 0` refusal WAS reachable and the D3 deletion is wrong"
            % (name, count)
        )

    # Measured 9 of 22 at the time of writing; the four `thick_*` seeds were added
    # for exactly this reason, because the thin ones are erased by the opening and
    # never cross the guard at all.
    assert crossed >= 8, (
        "only %d of %d seeds survived the 3x3 opening, so Guard A was barely "
        "crossed and this sweep proves little. Widen the fixtures rather than "
        "lowering this floor" % (crossed, len(_D3_LABEL_MASKS))
    )


def test_sp_d3_4_guard_a_still_admits_the_candidates_it_should():
    """[SP-D3-4] BEHAVIOURAL, on the surviving `np.any(opened)` guard (Guard A).

    Deleting the `count <= 0` refusal transfers the net to Guard A, so this
    records what Guard A must keep doing: let real seeds through. A colour-banded
    component above the oversized floor must still yield >= 2 localized
    candidates and report `accepted`.

    WHAT IT CATCHES, measured: inverting Guard A to `if bool(np.any(opened))`
    turns every seed away, and this goes red on `reason` being
    'insufficient_localized_candidates' with candidate_count 0.

    WHAT IT CANNOT CATCH, also measured, and the honest limit of "if Guard A
    kills Guard Z, test Guard A" at this call site: DELETING Guard A outright
    leaves this green, and leaves the whole adapters/eufy suite green. Guard A is
    an early-out over the empty mask and so was the refusal it killed -- two
    refusals, one answer, the shape `[RCL-2]` records above. The real net is the
    empty `range` pinned by [SP-D3-2]. Nothing behavioural can catch Guard A's
    deletion because its deletion has no behaviour; what it costs is a `label`
    and a `find_objects` per dead seed, which is a comment's job, not a test's,
    and the comment on it in `_try_add_candidate` says so.

    The sample is shown to be in the right place rather than assumed: the
    bisection below finds where the function's OWN oversized floor starts
    refusing this fixture and asserts `_MIN` sits below it, so the accept
    assertions above are known to be exercising the admit path rather than
    passing for some other reason. It deliberately does NOT re-derive the
    floor's shape. `[SP-oversize-xsite]` already pins that against the
    cascade's copy of the same threshold while naming neither constant, and
    restating it here as `active_area // 10 + 1` would name the multiplier and
    force a test edit on every legitimate retune.
    """
    comp = np.ones((400, 400), dtype=bool)
    rgb = np.zeros((400, 400, 3), dtype=np.uint8)
    bands = [
        (200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0),
        (200, 0, 200), (0, 200, 200), (150, 75, 0), (75, 0, 150),
    ]
    for index, colour in enumerate(bands):
        rgb[index * 50:(index + 1) * 50, :] = colour

    masks, debug = S._localize_oversized_component(
        comp, rgb, None, None, None, None, _MIN
    )

    # Name the branch and show the run took it, rather than inferring it from a
    # non-empty return.
    assert debug["reason"] == "accepted", debug
    assert debug["accepted"] is True, debug
    assert int(debug["candidate_count"]) >= 2, debug
    assert len(masks) >= 2, debug
    assert all(bool(np.any(mask)) for mask in masks), (
        "a candidate mask came back empty, which is the one thing Guard A is "
        "there to prevent reaching the caller"
    )

    # Where does the function's own oversized floor start refusing this fixture?
    # Bisect it out of the behaviour instead of restating the threshold.
    active_area = int(debug["active_area"])
    admits, refuses = _MIN, active_area
    assert S._localize_oversized_component(
        comp, rgb, None, None, None, None, refuses
    )[1]["reason"] == "below_oversized_floor", (
        "min_area_pixels == active_area was expected to sit below the oversized "
        "floor; the bisection needs a refusing upper bound to start from"
    )
    while refuses - admits > 1:
        middle = (admits + refuses) // 2
        reason = S._localize_oversized_component(
            comp, rgb, None, None, None, None, middle
        )[1]["reason"]
        if reason == "below_oversized_floor":
            refuses = middle
        else:
            admits = middle

    assert _MIN < refuses, (
        "min_area_pixels=%d is not below the oversized floor's first refusing "
        "value (%d) for a component of active_area %d, so the accept assertions "
        "above stopped exercising Guard A at all" % (_MIN, refuses, active_area)
    )

# ---------------------------------------------------------------------------
# [SP-local-5..6] local_support: what holds the two support slices up
#
# 2026-11-11 the second clause of the `empty_support_values` guard was deleted
# (`or len(primary_value_values) == 0`). Both slices index the SAME `active`, so
# their lengths are equal by construction, and the `or` described a divergence
# that cannot be built -- it sent readers hunting for a saturation-empty-but-
# value-not case instead. Deleting it TRANSFERS the net to two other things, and
# these are tests of those two things rather than of the clause that went:
#   [SP-local-5] the active-area floor, which is why neither length can be 0;
#   [SP-local-6] the single `active` mask, which is why they cannot differ.
# ---------------------------------------------------------------------------

_LS_SHAPE = (512, 512)  # 262,144 px -- room for every floor in the sweep below


def _ls_component(area):
    """A component mask holding exactly `area` active pixels."""
    mask = np.zeros(_LS_SHAPE, dtype=bool)
    if area:
        mask.reshape(-1)[:area] = True
    assert int(np.count_nonzero(mask)) == area
    return mask


def _ls_verdict(area, min_area_pixels):
    """local_support's own (masks, debug) for a component of exactly `area` pixels."""
    flat = np.full(_LS_SHAPE, 200, dtype=np.uint8)
    return S._split_component_via_local_support(
        _ls_component(area), flat, flat.copy(), None, None, min_area_pixels
    )


def _ls_floor_boundary(min_area_pixels):
    """The smallest active area that gets PAST the area floor, bisected out of the
    function's own verdicts.

    READ, not restated. The floor is `max(int(min_area_pixels * 2.0), 3200)` inside
    `_split_component_via_local_support` and nothing exports it, so a test that spelled
    `3200` would stay green for ever after someone edited `3200`. Bisecting means a
    retune MOVES this number, and the relations asserted on it below go red when the
    floor's SHAPE changes: deleted, neutralised, constant arm dropped, or that arm
    lowered under the proportional one. A shape-preserving retune (`3200 -> 5000`,
    `2.0 -> 2.5`) stays green by design -- measured both ways.
    """
    lo, hi = 0, _LS_SHAPE[0] * _LS_SHAPE[1]
    assert _ls_verdict(lo, min_area_pixels)[1]["reason"] == "below_active_area_floor", (
        "min_area_pixels=%d: a zero-area component is no longer below the area floor, "
        "so there is no floor to bisect" % min_area_pixels
    )
    assert _ls_verdict(hi, min_area_pixels)[1]["reason"] != "below_active_area_floor", (
        "min_area_pixels=%d: the area floor now sits above %d px, the whole fixture "
        "array -- either it was retuned upward or _LS_SHAPE needs to grow with it"
        % (min_area_pixels, hi)
    )
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _ls_verdict(mid, min_area_pixels)[1]["reason"] == "below_active_area_floor":
            lo = mid
        else:
            hi = mid
    return hi


def test_sp_local5_the_area_floor_is_the_net_under_the_empty_support_slice():
    """[SP-local-5] The active-area floor is what makes an empty support slice impossible.

    `empty_support_values` cannot fire, and THIS is the guard that kills it: the floor
    returns first unless `active_area >= max(int(min_area_pixels * 2.0), 3200)`, and
    `primary_sat[active]` holds exactly `active_area` elements. Deleting the second
    clause of that dead guard therefore rests on this one, which makes this one
    load-bearing -- and the big risk to a load-bearing guard is that somebody deletes
    it, which a behavioural test sees and dominance arithmetic does not.

    Both halves are here. The single edit that reddens it: neutralise the floor
    (`if active_area < max(int(min_area_pixels * 2.0), 3200):` -> `if active_area < 0:`)
    and the zero-area component below stops answering `below_active_area_floor` and
    starts answering `empty_support_values` -- the dead clause comes alive, which is
    the whole reason the floor has to stay. Deleting the floor's three lines outright
    reddens it identically, measured, and that is the edit that actually matters: what
    a load-bearing guard is at risk of is removal, not retuning.
    """
    # 1. THE STATE THE DELETED CLAUSE CLAIMED TO CATCH: a component with no active
    #    pixels at all. The floor answers first, across the whole admissible range of
    #    min_area_pixels (`vol.Range(min=1)` in mapping_services, and the CV engine's
    #    validate_tuning rejects anything that is not a positive int).
    for min_area_pixels in (1, 2, 50, 200, 1200, 1599, 1600, 1601, 5000, 20000, 100000):
        masks, debug = _ls_verdict(0, min_area_pixels)
        assert masks == []
        assert debug["active_area"] == 0, "the fixture did not build a zero-area component"
        assert debug["reason"] == "below_active_area_floor", (
            "min_area_pixels=%d: a zero-area component got PAST the area floor and "
            "reached the support slices, where the emptiness check now covers only one "
            "of the two -- reason was %r" % (min_area_pixels, debug["reason"])
        )

    # 2. The floor is strictly positive for every admissible min_area_pixels: the
    #    arithmetic half. A slice that reaches `empty_support_values` holds at least
    #    `boundary` elements, so it is never empty.
    boundaries = {mp: _ls_floor_boundary(mp) for mp in (1, 1200, 5000, 100000)}
    for min_area_pixels, boundary in sorted(boundaries.items()):
        assert boundary > 0, (
            "min_area_pixels=%d: the area floor admits a zero-area component"
            % min_area_pixels
        )
        # one pixel below the boundary is refused BY THE FLOOR and names it -- a
        # non-degenerate component, not the zero case above.
        under_masks, under = _ls_verdict(boundary - 1, min_area_pixels)
        assert under_masks == []
        assert under["active_area"] == boundary - 1
        assert under["reason"] == "below_active_area_floor"
        # and the boundary itself gets through into the percentile body: naming the
        # branch and showing the run took it is what stops a clean sweep reading clean
        # for the wrong reason.
        _at_masks, at = _ls_verdict(boundary, min_area_pixels)
        assert at["active_area"] == boundary
        assert at["reason"] != "below_active_area_floor"
        assert "required_score" in at, (
            "the above-floor call never reached the scoring body, so this sweep cannot "
            "have measured the area floor: debug=%r" % (at,)
        )

    # 3. The floor's SHAPE, read off the bisected numbers rather than copied out of the
    #    source: it has a min_area_pixels arm, so it tracks the tuning, and a constant
    #    arm, so a small tuning cannot lower it. Flattening it to one constant breaks
    #    the first line; dropping the constant breaks the second.
    assert boundaries[100000] > boundaries[5000] > boundaries[1200], (
        "the area floor stopped tracking min_area_pixels: %r" % (boundaries,)
    )
    assert boundaries[1] == boundaries[1200], (
        "the area floor lost its constant arm, so a small min_area_pixels can now "
        "drive it toward zero: %r" % (boundaries,)
    )


def _ls_one_mask_fixture():
    """Three disjoint blobs; the third is bright in saturation but ZERO in value.

    The third blob is 6400 of 13600 active pixels (47%), and `value_floor` is the 38th
    percentile of the value slice -- so taking that percentile over ALL of `active`,
    zeros included, puts the floor AT 0, where `>= 0` holds for those zeros too. That
    is the only thing keeping the third blob in `supported`, and it is exactly what
    stops being true if the value slice is taken over a different set of pixels from
    the saturation slice.
    """
    mask = np.zeros((300, 300), dtype=bool)
    sat = np.zeros((300, 300), dtype=np.uint8)
    value = np.zeros((300, 300), dtype=np.uint8)
    bright = [(20, 80, 20, 80), (120, 180, 20, 80)]   # 3600 px each, sat AND value high
    dark_value = [(200, 280, 120, 200)]               # 6400 px, sat high, value 0
    for top, bottom, left, right in bright + dark_value:
        mask[top:bottom, left:right] = True
        sat[top:bottom, left:right] = 220
    for top, bottom, left, right in bright:
        value[top:bottom, left:right] = 220
    return mask, sat, value


def test_sp_local6_both_support_slices_index_one_active_mask():
    """[SP-local-6] The two support slices are taken over ONE mask, and the split shows it.

    This is the property the deleted `or len(primary_value_values) == 0` pretended to
    defend and could not: comparing two LENGTHS is a weaker claim than the two slices
    covering the same PIXELS, and the lengths are equal whatever the pixels are.

    So the fixture makes the set matter. A third blob is bright in saturation and zero
    in value, and it is 47% of the active area -- so the 38th percentile of the value
    slice sits at 0, `>= 0` holds for its zeros, and the blob stays supported. Take the
    value slice over anything narrower than `active` (the obvious edit being
    `primary_value[active & (primary_value > 0)]`) and the floor jumps to 220, the blob
    drops out of `supported`, and the split returns two masks instead of three.
    MEASURED on this fixture: `value_floor` 0.0 -> 220.0, `scored_support_area`
    13600 -> 7200.

    The assertions are a COUNT and an AREA rather than emptiness, because "no split" is
    also what a strategy that silently did nothing returns.
    """
    mask, sat, value = _ls_one_mask_fixture()

    masks, debug = S._split_component_via_local_support(
        mask, sat, value, None, None, _MIN
    )

    # the branch was taken: the body scored, labelled and grew.
    assert debug["accepted"] is True and debug["reason"] == "accepted"
    assert debug["active_area"] == 13600            # 3600 + 3600 + 6400
    assert debug["required_score"] == 2             # no assist channels

    # EVERY active pixel is supported, the 6400 whose value channel is zero included.
    # That is the value floor sitting at 0, and it only sits there because the value
    # slice spans the same `active` as the saturation slice.
    assert debug["scored_support_area"] == debug["active_area"], (
        "the value floor rose off zero, so the value slice no longer covers the same "
        "pixels as the saturation slice: %r" % (debug,)
    )
    assert debug["support_component_count"] == 3, (
        "one supported component per blob is what the shared `active` buys; a narrower "
        "value slice drops the zero-value blob entirely: %r" % (debug,)
    )
    assert len(masks) == 3, (
        "expected one mask per blob, the zero-value one included, got %d. NOTE this "
        "assertion also moves when the seed-area, grown-area or upper-area floors below "
        "are retuned, which is not this test's subject: %r" % (len(masks), debug)
    )

    # And the length identity itself, recorded for what it is: this line cannot go red
    # without numpy changing, so it documents WHY the second clause of
    # `empty_support_values` was deleted rather than defending anything. The assertions
    # above are the ones that bite.
    active = mask.astype(bool)
    assert len(sat[active]) == len(value[active]) == debug["active_area"]


# ---------------------------------------------------------------------------
# [RCL-4] The occupied-row FLOOR is the OTHER killer of the empty-mask fallback
#
# `_reclaim_localized_child_mask` keeps an `if ys.size == 0: return parent_mask
# & False` after its first trim, and that line cannot fire. TWO refusals inside
# `_trim_sparse_top_rows` keep it dead, and they are not alternatives -- they own
# different regions of the input space:
#
#   * the RETENTION CLAMP, which throws a trim away unless enough of the mask
#     survives it. `[RCL-1]` above is the test of that one: relax the clamp and
#     the fallback wakes, and `[RCL-1]` goes red on the same edit.
#   * the OCCUPIED-ROW FLOOR at the top of the trim, which refuses outright when
#     a child has too few occupied rows to be read as a room with bleed above it.
#     Lower that floor and the fallback wakes TOO -- and before this test the
#     whole `tests/adapters/eufy` suite stayed green while it did.
#
# WHY `[RCL-1]` CANNOT SEE IT, which is why this is a second test and not a
# second assertion in the first. At the state the floor owns, the clamp is not
# LOOSENED, it is BYPASSED. The clamp asks that the survivors outnumber a
# truncated fraction of the original pixel count, and at a child of exactly ONE
# pixel that fraction truncates to zero -- so a trim that takes everything
# leaves zero survivors against a requirement of zero, and the clamp ACCEPTS it.
# `[RCL-1]`'s fixtures are 70-90 px over 16 rows, where the same requirement is
# tens of pixels and the clamp does all the work; no retune of its fixtures
# reaches the one-pixel state, because the floor turns that state away first.
#
# MEASURED, floor lowered to one occupied row and nothing else touched: a 1-px
# child trims to empty, reaches the fallback and comes back as `parent_mask &
# False`; every child of 2 px or more is still refused, by the clamp. One pixel
# is the whole region the floor owns, and nothing was covering it.
#
# WHAT THAT REGION IS WORTH, said rather than implied, because a reader will
# otherwise take it for a live state. One pixel cannot ARRIVE: the sole caller
# only runs this reclaim on `localized_bins` children, and
# `_localize_oversized_component` floors every candidate it emits at
# `max(int(min_area_pixels * 0.9), 1400)` pixels -- a mask that reaches the
# reclaim unaltered, since `_split_suspicious_component` returns the list as-is
# and `_prune_localized_siblings` runs long afterwards on segment dicts. So what
# is pinned below is the DOMINANCE relation inside the function, which is what
# the rule asks of a killer, and not a reachable input. That is the same footing
# as `[RCL-1]` and `[RCL-2]`, which drive this function directly too.
#
# NEITHER THRESHOLD IS NAMED BELOW. The floor is read off the function's own
# answers by sweeping the occupied-row count on a family the clamp demonstrably
# permits, so a deliberate retune (up or down, as long as it stays above one
# row) MOVES what this test measures instead of needing a test edit; dropping
# the floor, neutralising it, or lowering it onto the one-row child reddens it.
# ---------------------------------------------------------------------------

_RCL4_DENSE_WIDTH = 10   # as the `[RCL-1]` fixtures above
_RCL4_ROW_SWEEP = tuple(range(1, 25))


def _rcl4_child(occupied_rows, *, top_width=1):
    """One thin top row over `occupied_rows - 1` dense ones.

    The trim, when it runs at all, takes the thin row and keeps every dense one,
    so over 90% of the pixels survive at every row count in the sweep -- far
    above anything the retention clamp asks for. That is what makes this family
    a probe of the ROW FLOOR rather than of the clamp: the occupied-row count is
    the only thing moving across the sweep.
    """
    return _sparse_topped(
        top_rows=1,
        top_width=top_width,
        dense_rows=max(occupied_rows - 1, 0),
        dense_width=_RCL4_DENSE_WIDTH,
    )


def _rcl4_reclaim(child):
    """The reclaim with channels that cannot support any growth: the trim alone."""
    sat, value = _no_support(child.shape)
    return S._reclaim_localized_child_mask(
        child, np.ones(child.shape, dtype=bool), primary_sat=sat, primary_value=value
    )


def _rcl4_trim_map():
    """{occupied-row count: did the trim actually act?}, from the reclaim's answers."""
    acted = {}
    for rows in _RCL4_ROW_SWEEP:
        child = _rcl4_child(rows)
        built = int(np.flatnonzero(np.count_nonzero(child, axis=1) > 0).size)
        assert built == rows, (
            "fixture built %d occupied rows, not %d" % (built, rows)
        )
        acted[rows] = not np.array_equal(_rcl4_reclaim(child), child)
    return acted


def _rcl4_floor_boundary(trim_map):
    """The smallest occupied-row count the trim will act on at all. READ, not restated.

    The floor lives inside a nested helper that nothing exports, so a test that
    spelled its value would stay green for ever after someone edited that value.
    Sweeping for the transition means a retune moves this number and the relations
    asserted on it still hold.
    """
    acting = [rows for rows, did in sorted(trim_map.items()) if did]
    assert acting, (
        "the trim never acted at ANY occupied-row count up to %d, so there is no "
        "floor to find and the family below is not trimmable any more -- either the "
        "trim's own row threshold was retuned past this sweep or `_sparse_topped` "
        "changed shape: %r" % (_RCL4_ROW_SWEEP[-1], trim_map)
    )
    boundary = acting[0]
    assert all(trim_map[rows] is (rows >= boundary) for rows in _RCL4_ROW_SWEEP), (
        "the trim's answer flips more than once across the occupied-row sweep, so "
        "'the smallest count it acts on' is not a floor and the reading below is "
        "meaningless: %r" % (trim_map,)
    )
    return boundary


def test_rcl4_the_occupied_row_floor_is_what_keeps_a_trim_from_emptying_a_child():
    """[RCL-4] BEHAVIOURAL, on the occupied-row floor in `_trim_sparse_top_rows`.

    The floor is load-bearing because the `ys.size == 0` fallback above rests on
    it, and what a load-bearing guard is at risk of is REMOVAL, not retuning --
    which a behavioural test sees and dominance arithmetic does not. Both halves
    are here.

    THE SINGLE EDIT THAT REDDENS IT, measured: lower the floor until a single
    occupied row passes it. Part 1's swept boundary collapses to one row and
    part 2's one-pixel child comes back EMPTY, as `parent_mask & False`. Neutralising
    the floor, or deleting its two lines outright, reddens it identically -- and
    deletion is the edit that actually matters. A retune that still refuses a
    one-row child leaves it green, measured, because the fallback stays dead there.

    WHICH REFUSAL THIS REACHES, because "a sparse child came back untouched" is
    also what the retention clamp returns and would pass for the wrong reason.
    The floor is identified by the row count at which the answer FLIPS on a
    family the clamp demonstrably permits: part 1 finds a boundary, so trims ARE
    being accepted in this family, so the clamp's requirement is below the whole
    mask -- and a requirement below the whole mask truncates to zero at a child
    of one pixel, where it cannot refuse anything. The clamp is bypassed there,
    not satisfied, and the floor is the only refusal left standing.

    PART 3 IS DOMINANCE ARITHMETIC and it is deliberately not exclusive to the
    floor: it pins the fallback's unreachability over the whole all-sparse
    family, so a deep retune of the retention clamp reddens it as well. That is
    correct -- what is being pinned there is that the fallback stays dead, not
    which guard keeps it that way.
    """
    # 1. WHERE THE FLOOR SITS, read off the reclaim's own answers.
    trim_map = _rcl4_trim_map()
    boundary = _rcl4_floor_boundary(trim_map)
    assert boundary > 1, (
        "the trim now acts on a child with a single occupied row. That child can "
        "be a single PIXEL, the retention clamp's requirement truncates to zero "
        "there, and the trim returns an empty mask -- which wakes the "
        "`ys.size == 0` fallback in `_reclaim_localized_child_mask` that this "
        "floor is what keeps dead. Swept answers: %r" % (trim_map,)
    )

    # 2. THE PROTECTED STATE ITSELF: one occupied row holding one pixel. The
    #    channels are zeroed so no reclaim can run -- what comes back is the
    #    trim's answer and nothing else. This re-runs the `rows == 1` entry of
    #    part 1's sweep rather than adding a measurement, and the refusal path
    #    returns the input ARRAY ITSELF, so the comparisons below are against
    #    that same object: they are a statement of the state being protected,
    #    and they carry their weight on the RED side, where the fallback
    #    substitutes a different array.
    one_pixel = _rcl4_child(1)
    assert int(np.count_nonzero(one_pixel)) == 1, "the fixture is not a one-pixel child"
    assert 1 < boundary, (
        "the one-pixel child's single occupied row is no longer below the floor "
        "found at %d rows, so the assertions below have stopped exercising the "
        "floor at all" % boundary
    )
    out = _rcl4_reclaim(one_pixel)
    assert int(np.count_nonzero(out)) == 1, (
        "a one-pixel child came back with %d pixels instead of 1. An EMPTY return "
        "is the reclaim's `parent_mask & False` fallback firing, which is the state "
        "the occupied-row floor exists to make impossible"
        % int(np.count_nonzero(out))
    )
    assert np.array_equal(out, one_pixel), (
        "a one-pixel child was moved rather than returned untouched"
    )

    # 3. DOMINANCE: across the all-sparse family -- every row thin enough to be
    #    trim-eligible, so a completed trim would empty the mask -- the reclaim
    #    never returns empty. Below the boundary the floor refuses; at and above
    #    it the clamp does, because those masks hold more than one pixel and its
    #    requirement no longer truncates away.
    emptied = []
    acted = []
    for rows in range(1, 13):
        for width in range(1, 6):
            child = _sparse_topped(
                top_rows=rows, top_width=width, dense_rows=0, dense_width=0
            )
            result = _rcl4_reclaim(child)
            if not bool(np.any(result)):
                emptied.append((rows, width, int(np.count_nonzero(child))))
            elif not np.array_equal(result, child):
                acted.append((rows, width, int(np.count_nonzero(result))))
    assert not emptied, (
        "the trim emptied an all-sparse child at (rows, width, pixels) %r, so the "
        "`ys.size == 0` fallback in `_reclaim_localized_child_mask` is reachable "
        "again" % (emptied,)
    )
    assert not acted, (
        "an all-sparse child was partially trimmed at (rows, width, survivors) %r. "
        "Every row in this family is trim-eligible, so a partial trim means the "
        "row-walk stopped early -- the sweep is no longer measuring what it says"
        % (acted,)
    )
