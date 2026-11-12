"""Eufy-specific room-segment extraction via HSV color clustering and morphological analysis.

This module implements the Eufy HSV segmentation pipeline. Brand-agnostic
geometry and image-processing primitives (polygon math, mask ops, transforms,
alignment, color features) live in ``mapping/segment_primitives.py`` and are
imported below; no brand-specific logic belongs there.

Public entry point
~~~~~~~~~~~~~~~~~~
``detect_room_segments`` — accepts a clean unlabeled Eufy map image path and
returns a structured dict of room segments with geometry, quality labels, and
pipeline diagnostics.

Eufy-specific internals
~~~~~~~~~~~~~~~~~~~~~~~
- ``_build_room_mask_from_hsv`` / ``_build_light_wall_mask`` — HSV thresholds
  tuned for Eufy map colour palettes.
- ``_issue_quality``, ``_structural_role``, ``_segmentation_state`` — scoring
  heuristics whose numeric thresholds were calibrated on Eufy map images.
- ``_reclaim_localized_child_mask`` — downward reclaim for vertically truncated
  localized children; relies on Eufy-style saturation/value support masks.
- Split-strategy cascade in ``_split_suspicious_component``, listed here IN THE
  ORDER IT RUNS, which is ordered by evidence quality and returns the first
  strategy that succeeds: wall cuts, localized bins, color distance, local
  support, assist hue, erosion seeds, opening split. Strongest evidence first,
  falling back toward pure morphology — a wall cut is a real observation about
  the map, an erosion seed is a guess about shape. (This list read "erosion,
  opening, wall cuts, ..." until 2026-08-23: source-DEFINITION order, close to
  the reverse of the real cascade, in the one place a reader looks to find out
  what is tried first.) All
  tuned to Eufy map characteristics.

Porting a new brand
~~~~~~~~~~~~~~~~~~~
Start from ``mapping/segment_primitives.py``, which documents the full primitive
surface area.  Copy ``_build_room_mask_from_hsv`` and the scoring heuristics
as a template and tune their thresholds for the new brand's map imagery.

Why this is CV and not a vision model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A vision-model approach was considered and rejected: the pipeline available to it
delivered a DOWNGRADED image rather than the full-quality PNG, so the comparison was
never against the real input. The blocker is what the model can be SHOWN, not what a
model can do — if the full-quality PNG becomes deliverable, this is worth re-running.

Recorded here 2026-08-24 because the tuning below reads as evidence to the contrary.
A reader meeting a thousand-odd lines of hand-tuned HSV clustering reasonably infers
that someone judged CV the better technique; that is a NOT-YET wearing the clothes of
a NEVER. The thresholds are not proof the problem needs hand tuning — they are what
you build when the alternative was evaluated on bad input. The note
``project_eufy_origin_lineage`` already records the engine as deliberately no-LLM;
what it does not record anywhere is WHY, which is the paragraph above.

WHERE the degradation happened, WHEN this was decided, and whether the full-quality
PNG is reachable today are all UNKNOWN. Do not guess them here — stating the reason
and stopping is what keeps this a true fact.
"""

from __future__ import annotations

import logging
from typing import Any

from ...mapping.segment_primitives import (
    np,
    PIL_Image,
    _PIL_SCIPY_READY,
    _NDIMAGE,
    image_runtime_capabilities,
    bbox_from_stats as _bbox_from_stats,
    mask_to_polygon as _mask_to_polygon,
    mask_perimeter as _mask_perimeter,
    compactness as _compactness,
    aspect_ratio as _aspect_ratio,
    agreement_score as _agreement_score,
    component_overlap_ratio as _component_overlap_ratio,
    mask_left_right_counts as _mask_left_right_counts,
    mask_edge_band as _mask_edge_band,
    transform_mask as _transform_mask,
    transform_scalar_image as _transform_scalar_image,
    transform_color_image as _transform_color_image,
    estimate_alignment as _estimate_alignment,
    normalized_color_features as _normalized_color_features,
)

_LOGGER = logging.getLogger(__name__)


# -- Eufy HSV segment quality / role classifiers ------------------------------

def _issue_quality(issues: list[str], confidence: float) -> str:
    """Map a segment's issue flags and confidence score to a quality label."""
    if "tiny_region" in issues or "too_complex" in issues:
        return "poor"
    if "touches_border" in issues or "possible_merge" in issues or confidence < 0.55:
        return "usable"
    if confidence < 0.75:
        return "good"
    return "strong"


def _structural_role(*, area_percent: float, aspect_ratio: float, fill_ratio: float) -> str:
    """Classify a segment's structural role (hub, connector, spine, room, uncertain)."""
    if area_percent >= 0.09 and fill_ratio >= 0.62:
        return "hub"
    if aspect_ratio >= 2.4 and fill_ratio >= 0.34:
        return "connector"
    if aspect_ratio >= 1.7 and fill_ratio >= 0.3:
        return "spine"
    if fill_ratio >= 0.58:
        return "room"
    return "uncertain"


def _segmentation_state(*, issues: list[str], fill_ratio: float, compactness: float) -> str:
    """Classify a segment's segmentation state (clean, merged_candidate, fragmented_candidate, review)."""
    if "possible_merge" in issues:
        return "merged_candidate"
    if "fragmented_candidate" in issues or compactness < 0.08:
        return "fragmented_candidate"
    if fill_ratio >= 0.58 and "tiny_region" not in issues:
        return "clean"
    return "review"


# -- Eufy HSV room / wall masks -----------------------------------------------

def _build_room_mask_from_hsv(hsv: Any) -> Any:
    """Return a binary room-pixel mask derived from HSV saturation and value thresholds.

    WHAT THE THRESHOLDS ARE REJECTING — the imagery observation that calibrated them,
    which cannot be recovered from the numbers. A pixel must be BOTH bright enough
    (``value >= 68`` of 255, ≈ 27% brightness) AND colourful enough
    (``saturation >= 18`` of 255, ≈ 7%) to count as a room pixel. Together that excludes
    near-black walls, near-white backgrounds, and the off-white dock area.

    Salvaged 2026-08-24 from the retired ``11-mapping-system.md``. The threshold VALUES
    were always in code; what was nowhere was the statement of what the mask is MEANT
    to exclude — so a porting brand, or anyone re-tuning, had no way to tell a mis-tune
    from a change in how the vendor renders its maps.
    """
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    room_mask = (value >= 68) & (saturation >= 18)
    structure = np.ones((3, 3), dtype=bool)
    room_mask = _NDIMAGE.binary_opening(room_mask, structure=structure, iterations=1)
    room_mask = _NDIMAGE.binary_closing(room_mask, structure=structure, iterations=2)
    room_mask = _NDIMAGE.binary_fill_holes(room_mask)
    return room_mask


def _build_light_wall_mask(hsv: Any) -> Any:
    """Return a binary mask of near-white wall pixels from a light-theme HSV image."""
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    wall_mask = (value >= 214) & (saturation <= 36)
    structure = np.ones((3, 3), dtype=bool)
    wall_mask = _NDIMAGE.binary_opening(wall_mask, structure=structure, iterations=1)
    wall_mask = _NDIMAGE.binary_dilation(wall_mask, structure=structure, iterations=1)
    return wall_mask


# -- Localized child mask reclaim ---------------------------------------------

def _reclaim_localized_child_mask(
    local_mask: Any,
    parent_mask: Any,
    *,
    primary_sat: Any,
    primary_value: Any,
    assist_sat: Any | None = None,
    assist_value: Any | None = None,
) -> Any:
    """Conservatively reclaim vertically truncated localized child masks.

    This is intentionally biased toward completing room-like regions that got
    clipped upward during localization. It only grows downward a small amount
    inside the already-detected parent component and only through pixels that
    still look room-like in saturation/value space.
    """
    # LOAD-BEARING. This line is the net for `if ys.size == 0: return local_mask`, which was
    # deleted from straight after the `np.nonzero` below on 2026-11-11, so what this line is
    # at risk of is REMOVAL, not a retune. That guard was identity-dead behind this one: it
    # read the very same parameter this line has just proved non-empty. Deleting it left
    # `tests/adapters/eufy` at 336 passed, the same argument that deleted
    # `_try_add_candidate`'s `count <= 0`.
    #
    # THE TWO HALVES OF THIS LINE HAVE DIFFERENT REACH, and conflating them is a mistake this
    # comment has already made once.
    #   * `not bool(np.any(local_mask))` stops being SUFFICIENT at the
    #     `_trim_sparse_top_rows` call below, which REASSIGNS `local_mask`: with the
    #     occupied-row floor ablated the trim returns an EMPTY mask for an input this half had
    #     already passed. It is still NECESSARY past that point — the trim's pass-through arm
    #     hands back the parameter untouched, so the `ys.size == 0` guard after it is dead only
    #     because this half proved the parameter non-empty, which is what that guard's own
    #     comment has always said. What the reassignment ends is sufficiency, not relevance.
    #     The other guard deleted the same day, `if sat_values.size == 0 or
    #     value_values.size == 0`, sits further down and is NOT held by this line directly:
    #     what holds it is the `ys.size == 0` guard earlier in the same function, which tests
    #     an identical predicate on the same mask.
    #   * `_NDIMAGE is None` reaches the WHOLE function. It is the only such check here, and
    #     `_NDIMAGE.binary_propagation` and `_NDIMAGE.binary_closing` below the trim both rest
    #     on it — remove that clause alone and they raise AttributeError on NoneType. THE
    #     SUITE DOES NOT CATCH THAT: `tests/adapters/eufy` stays at 336 passed, because the
    #     test module calls `pytest.importorskip("scipy.ndimage")` and nothing sets `_NDIMAGE`
    #     to None for this function. A real gap, named rather than implied.
    #
    # (The SECOND `ys.size == 0` in this function, the one returning `parent_mask & False`
    # after the trim, is a different guard and still stands: its killers are the 0.68
    # retention clamp and the occupied-row floor, held by `[RCL-1]` and `[RCL-4]`.)
    #
    # WHAT HOLDS IT, measured on these bytes three ways that DISAGREE — which is the point:
    # one number repeated across different ablations would be a constant of the harness, not
    # a property of the code.
    #   * delete the `or not bool(np.any(...))` clause → 2 red,
    #     `test_reclaim_empty_mask_returns_input` and `[RCL-2]`. THIS IS THE ONE THAT MATTERS,
    #     and it was INVISIBLE until the two guards above went: they absorbed the empty mask
    #     and returned the very same object, so removing the net changed nothing a test could
    #     see. Deleting a dominated guard is what made its killer's removal catchable.
    #   * invert it to `bool(np.any(...))` → 10 red, spanning both adapter test files.
    #   * swap `np.any` for `np.all` → 8 red. Fewer on purpose: `np.all` of an all-False
    #     mask is still False, so the empty-mask path alone keeps behaving correctly.
    if _NDIMAGE is None or not bool(np.any(local_mask)):
        return local_mask

    ys, _ = np.nonzero(local_mask)
    height, width = local_mask.shape
    bottom = int(ys.max())
    if bottom >= height - 2:
        return local_mask

    def _trim_sparse_top_rows(mask: Any, *, pass_strength: float) -> Any:
        row_counts = np.count_nonzero(mask, axis=1)
        occupied_rows = np.flatnonzero(row_counts > 0)
        if occupied_rows.size < 6:
            return mask
        local_top = int(occupied_rows.min())
        local_bottom = int(occupied_rows.max())
        lower_start_index = min(len(occupied_rows) // 3, max(len(occupied_rows) - 3, 0))
        lower_start = int(occupied_rows[lower_start_index])
        baseline_rows = row_counts[lower_start : local_bottom + 1]
        baseline_rows = baseline_rows[baseline_rows > 0]
        # Dead: `lower_start` is itself an entry of `occupied_rows` and the window above starts
        # on it, so the `> 0` filter always keeps at least row_counts[lower_start] (0 fires over
        # 341k masks). Provable, not merely sampled: lower_start_index = min(n//3, max(n-3, 0))
        # lands in [0, n-3] for every n >= 6, so lower_start is an occupied row with at least two
        # more occupied rows after it -- the window in fact retains >= 4 of them, never just one.
        #
        # NO EDIT TO THE WINDOW'S START CAN WAKE THIS. The window ends at local_bottom + 1 and
        # row_counts[local_bottom] > 0, so every start a <= local_bottom keeps that entry. Swept
        # every legal start over 60k masks: 0 empty windows. Eight named start edits (local_top,
        # lower_start_index as a row, len//3, lower_start +/- 1, occupied_rows[-3], no anchor at
        # all, and the window above) each fire 0. The wake is the window's END, or the `> 0`
        # filter: `[lower_start : trim_limit]` fires 67%, `[lower_start : local_top + 10]` 69%,
        # `[ls : ls]` 100%, and `> 0` -> `> 1` fires on masks whose rows all hold one pixel.
        #
        # Thin net if dropped -- the np.median of an empty slice is NaN and max(6.0, NaN) returns
        # 6.0, so the trim would fall back to the hard floor instead of the measured baseline.
        # Silent in control flow only: numpy raises two RuntimeWarnings there, which pytest.ini
        # does not turn into errors.
        if baseline_rows.size == 0:
            return mask
        dense_row_baseline = float(np.median(baseline_rows))
        trim_limit = min(local_bottom, local_top + max(10, int(mask.shape[0] * 0.22)))
        trim_rows: list[int] = []
        for row in range(local_top, trim_limit + 1):
            count = int(row_counts[row])
            if count <= 0:
                continue
            if count < max(6.0, dense_row_baseline * pass_strength):
                trim_rows.append(row)
                continue
            break
        if not trim_rows:
            return mask
        trimmed_mask = mask.copy()
        trimmed_mask[trim_rows, :] = False
        if int(np.count_nonzero(trimmed_mask)) < int(np.count_nonzero(mask) * 0.68):
            return mask
        return trimmed_mask

    # Trim sparse top rows before attempting downward reclaim.
    local_mask = _trim_sparse_top_rows(local_mask, pass_strength=0.42)
    ys, _ = np.nonzero(local_mask)
    # Dead: _trim_sparse_top_rows returns either `mask` untouched — non-empty per the np.any()
    # gate at the top of this function — or a trim that cleared its own 0.68 retention clamp.
    # TWO EDITS WAKE IT, and the one that went unguarded longest is not the obvious one:
    #   * relax the 0.68 clamp (to 0.0, 518 fires) — ALREADY GUARDED, behaviourally, by
    #     `test_rcl1_the_trim_refuses_when_it_would_take_too_much`, which goes red on it.
    #   * lower `occupied_rows.size < 6` to `< 1` (3 fires) — GUARDED, since 2026-11-11, by
    #     `test_rcl4_the_occupied_row_floor_is_what_keeps_a_trim_from_emptying_a_child`, which
    #     reddens on that edit and on deleting the floor outright. Until it existed the whole
    #     adapters suite passed with the edit in place, 335 passed / 0 failed. At one occupied
    #     row `int(np.count_nonzero(mask) * 0.68) == 0`, so the clamp cannot refuse anything and
    #     a single sparse row trims to empty. The clamp is BYPASSED rather than loosened, which
    #     is why [RCL-1]'s 16-row fixtures cannot see it.
    # Per the project's own rule, a guard with two killers needs both tested; both now are.
    # WHAT IT COSTS EITHER WAY. Firing returns `parent_mask & False` — the deliberate
    # empty-mask-of-the-right-shape idiom, not a bug — to the sole caller, which drops it at
    # `if local_area <= 0: continue`: ONE ROOM, silently. Deleting the guard instead lets
    # `int(ys.min())` raise ValueError, which escapes `detect_room_segments` and is caught in
    # mapping/segmenter_engines.py as `reason: "engine_exception"` — the WHOLE run, every
    # segment, measured end-to-end on a real pipeline input. One room against all of them is
    # the trade, and it is why the idiom is kept.
    if ys.size == 0:
        return parent_mask & False
    top = int(ys.min())
    bottom = int(ys.max())

    # Neither slice can be empty, and what guarantees it is the `if ys.size == 0: return
    # parent_mask & False` guard earlier in this function. THE SAME PREDICATE, not a related
    # one: indexing a 2-D array with a boolean mask yields one element per True, so
    # `sat_values.size == 0` holds exactly when `ys.size == 0` does, `ys` being `np.nonzero`
    # of this same post-trim `local_mask` with nothing reassigning it in between. That guard
    # returns first, so it STRICTLY DOMINATES this site and suffices alone. Two more stand
    # behind it: `int(ys.min())` and `int(ys.max())` above would both raise on an empty array.
    #
    # THE IDENTITY IS CONDITIONAL ON THE CHANNELS BEING 2-D, and that is the attack worth
    # naming rather than leaving to a reader: `np.zeros((5, 5, 0))[mask]` has shape `(2, 0)`
    # and size 0 while `ys.size` is 2, so a channel array with a degenerate trailing axis
    # would break it. The sole caller passes `component_hsv_full[:, :, 1]` and `[:, :, 2]`,
    # always 2-D, which is why the identity holds here — not because the shape cannot be
    # built. NOTHING PINS THE `.size` FORM against that axis. The nearest test,
    # `[SP-oversize-identity]`, is the CONTRAST rather than the precedent: it pins a `len`-based
    # identity in `_localize_oversized_component` and says in as many words that a zero-width
    # feature axis leaves `len` counting rows and not columns, so `len` SURVIVES the attack that
    # breaks `.size`. That is the discriminator between the two sites, and the reason this one
    # leans on the caller's shape instead of on numpy.
    #
    # TWO EARLIER DRAFTS OF THIS COMMENT NAMED SOMETHING FURTHER AWAY, and both were wrong in
    # the same direction. First the `np.any(local_mask)` gate at the top of the function —
    # but `local_mask` is reassigned by `_trim_sparse_top_rows` between them. Then the trim's
    # own 0.68 clamp and occupied-row floor — but those are the killers of the guard above,
    # one step further out again: ablate the floor and `[RCL-4]` reddens AT THAT GUARD, with
    # these slices never taken. So if this is re-audited, the guard that must REMAIN for the
    # deletion below to stay safe is the `ys.size == 0` one above. Not the trim refusals, and
    # not the gate.
    #
    # The `if sat_values.size == 0 or value_values.size == 0` that restated the predicate here
    # was dead in BOTH arms, not just the `or`, and was deleted on 2026-11-11. If it is ever
    # argued back in, price it against what it stood in front of: `np.percentile` of an empty
    # slice raises IndexError, not a quiet wrong answer.
    sat_values = primary_sat[local_mask]
    value_values = primary_value[local_mask]

    sat_floor = max(18.0, float(np.percentile(sat_values, 20)) - 18.0)
    value_floor = max(68.0, float(np.percentile(value_values, 20)) - 26.0)

    support_mask = parent_mask & (primary_sat >= sat_floor) & (primary_value >= value_floor)
    if assist_sat is not None and assist_value is not None:
        assist_support = (assist_sat >= max(16.0, sat_floor - 4.0)) & (assist_value >= max(64.0, value_floor - 8.0))
        support_mask &= assist_support

    row_index = np.indices(local_mask.shape)[0]
    col_index = np.indices(local_mask.shape)[1]
    xs = np.nonzero(local_mask)[1]
    left = int(xs.min())
    right = int(xs.max())
    horizontal_margin = max(8, int((right - left + 1) * 0.12))
    support_mask &= row_index >= max(0, bottom - 2)
    support_mask &= row_index <= min(height - 1, bottom + max(16, int(height * 0.08)))
    support_mask &= col_index >= max(0, left - horizontal_margin)
    support_mask &= col_index <= min(width - 1, right + horizontal_margin)
    if not bool(np.any(support_mask)):
        return local_mask

    # WHY: binary_propagation from the lower seed band — constrained to connected
    # room-like support rather than blindly dilating the whole child mask.
    lower_seed_band = max(top, bottom - max(10, int((bottom - top + 1) * 0.35)))
    seed_mask = local_mask & (row_index >= lower_seed_band)
    reclaimed = _NDIMAGE.binary_propagation(
        seed_mask,
        structure=np.ones((3, 3), dtype=bool),
        mask=support_mask,
    ) & ~local_mask
    if not bool(np.any(reclaimed)):
        return local_mask

    expanded = local_mask | reclaimed
    expanded = _NDIMAGE.binary_closing(expanded, structure=np.ones((3, 3), dtype=bool), iterations=1)
    expanded &= parent_mask

    added_area = int(np.count_nonzero(expanded)) - int(np.count_nonzero(local_mask))
    if added_area <= 0:
        return _trim_sparse_top_rows(local_mask, pass_strength=0.5)
    if added_area > max(3200, int(np.count_nonzero(local_mask) * 0.55)):
        return _trim_sparse_top_rows(local_mask, pass_strength=0.5)

    # Final cleanup pass to suppress any lingering upper bleed after reclaim.
    return _trim_sparse_top_rows(expanded, pass_strength=0.5)


# -- Split strategies ---------------------------------------------------------

def _split_component_via_erosion(component_mask: Any, min_area_pixels: int) -> list[Any]:
    """Try to split a merged component by progressively eroding and regrowth from seeds."""
    structure = np.ones((3, 3), dtype=bool)
    for iterations in (1, 2, 3, 4):
        eroded = _NDIMAGE.binary_erosion(component_mask, structure=structure, iterations=iterations)
        if not bool(np.any(eroded)):
            continue
        seeds, seed_count = _NDIMAGE.label(eroded, structure=structure)
        if seed_count < 2:
            continue

        grown_masks: list[Any] = []
        for label_index in range(1, seed_count + 1):
            seed_mask = seeds == label_index
            grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
            grown_area = int(np.count_nonzero(grown))
            if grown_area < max(350, int(min_area_pixels * 0.45)):
                continue
            grown_masks.append(grown)

        if len(grown_masks) >= 2:
            return grown_masks
    return []


def _split_component_via_opening(component_mask: Any, min_area_pixels: int) -> list[Any]:
    """Try to split a merged component via binary opening followed by propagation from seeds."""
    structure = np.ones((3, 3), dtype=bool)
    for iterations in (1, 2, 3, 4):
        opened = _NDIMAGE.binary_opening(component_mask, structure=structure, iterations=iterations)
        if not bool(np.any(opened)):
            continue
        seeds, seed_count = _NDIMAGE.label(opened, structure=structure)
        if seed_count < 2:
            continue

        grown_masks: list[Any] = []
        for label_index in range(1, seed_count + 1):
            seed_mask = seeds == label_index
            grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
            grown_area = int(np.count_nonzero(grown))
            if grown_area < max(350, int(min_area_pixels * 0.45)):
                continue
            grown_masks.append(grown)
        if len(grown_masks) >= 2:
            return grown_masks
    return []


def _split_component_via_wall_cuts(
    component_mask: Any,
    wall_hint_mask: Any | None,
    min_area_pixels: int,
    debug_out: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """Try to split a merged component by cutting along nearby wall-hint pixels.

    ``debug_out``, when supplied, receives ONE entry describing the outcome — including
    the declines. This strategy is tried FIRST and used to append a debug row only on
    success, so a failed wall cut left no row at all: the strategy with the strongest
    evidence was invisible in diagnostics exactly when it did not fire, and a reader
    inspecting the per-method list would reasonably conclude it was never attempted.

    The reason is produced HERE rather than inferred by the caller, because the caller
    would have to re-test this function's own preconditions to guess it — a second copy
    of a predicate, which is how the copies drift apart. The parameter is optional so the
    eight existing call sites that only want the masks are unaffected.

    The three declines are genuinely different problems, so they stay three reasons:
    ``no_wall_hint`` means the second image variant was never available (a user/upload
    question), ``wall_hint_shape_mismatch`` means two images arrived at different sizes
    (a pipeline bug), and ``no_split`` means walls were found and no clean cut separated
    the component (a tuning question).
    """
    def _decline(reason: str) -> list[Any]:
        if debug_out is not None:
            debug_out.append({"method": "wall_cuts", "accepted": False, "reason": reason})
        return []

    if wall_hint_mask is None:
        return _decline("no_wall_hint")
    if getattr(component_mask, "shape", None) != getattr(wall_hint_mask, "shape", None):
        return _decline("wall_hint_shape_mismatch")
    structure = np.ones((3, 3), dtype=bool)
    local_wall = wall_hint_mask & _NDIMAGE.binary_dilation(component_mask, structure=structure, iterations=1)
    if not bool(np.any(local_wall)):
        return _decline("no_local_wall")

    for iterations in (1, 2, 3):
        cut_mask = component_mask & ~_NDIMAGE.binary_dilation(local_wall, structure=structure, iterations=iterations)
        if not bool(np.any(cut_mask)):
            continue
        labeled, component_count = _NDIMAGE.label(cut_mask, structure=structure)
        if component_count < 2:
            continue
        grown_masks: list[Any] = []
        for label_index in range(1, component_count + 1):
            seed_mask = labeled == label_index
            grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
            grown_area = int(np.count_nonzero(grown))
            if grown_area < max(350, int(min_area_pixels * 0.45)):
                continue
            grown_masks.append(grown)
        if len(grown_masks) >= 2:
            return grown_masks
    return _decline("no_split")


def _split_component_via_local_support(
    component_mask: Any,
    primary_sat: Any | None,
    primary_value: Any | None,
    assist_sat: Any | None,
    assist_value: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    """Try to split a merged component by scoring pixels against per-channel support thresholds.

    RETURNS ``(masks, debug)`` LIKE EVERY SIBLING, and the shape is the point rather than a
    convenience. This was the only splitter returning a bare list, so all six of its
    refusals were indistinguishable from each other AND from the full-body reject — the
    cascade logged ``local_support:no_split`` for every one, a reason it had to INVENT
    because the callee supplied none. This repo already ruled on that shape once: D20 /
    ``[SP-wall-dbg]``, where the first-tried strategy appended a debug row only on success,
    "so its failure left no row and read as never-attempted".

    The practical cost was a whole arm nobody could test. ``no_supported_body`` — the 3x3
    opening erasing a support mask that is real but too thin to hold together — is reachable
    from the pipeline and was measured firing, but a test over it stayed green with the
    opening deleted, because both inputs produced an identical reason set and an identical
    segment. ``[ECV-30]`` records that history; this is what makes it assertable.

    BEHAVIOUR IS UNCHANGED. Every threshold, every ``continue`` and the masks returned are
    byte-for-byte what they were; only the second element of the tuple is new.
    """
    debug: dict[str, Any] = {
        "method": "local_support",
        "accepted": False,
    }
    if (
        primary_sat is None
        or primary_value is None
        or getattr(component_mask, "shape", None) != getattr(primary_sat, "shape", None)
        or getattr(component_mask, "shape", None) != getattr(primary_value, "shape", None)
    ):
        debug["reason"] = "missing_support_channels"
        return [], debug

    # anchor: RN6M6W3H  the splitters' active-area floor — the replica set
    # `max(int(min_area_pixels * 2.0), 3200)` is written TWICE, here and in
    # `_split_component_via_color_distance`, as BYTE-IDENTICAL four-line blocks down to the
    # `below_active_area_floor` reason. Unlike the oversized gate/floor pair that
    # `[SP-oversize-xsite]` anchors, these are not complementary halves of one decision —
    # they are two INDEPENDENT floors that happen to agree, so retuning one is silent in
    # both directions: no caller compares them and no test reads both.
    # `python scripts/doc_anchor.py --show RN6M6W3H` lists every site.
    active = component_mask.astype(bool)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    if active_area < max(int(min_area_pixels * 2.0), 3200):
        debug["reason"] = "below_active_area_floor"
        return [], debug

    primary_sat_values = primary_sat[active]
    primary_value_values = primary_value[active]
    # UNREACHABLE. Kept as the SHAPE of the contract, not as a live net: the active-area
    # floor above returns `below_active_area_floor` unless
    # `active_area >= max(int(min_area_pixels * 2.0), 3200)`, and `primary_sat[active]`
    # holds exactly `active_area` elements -- so this length is at least 3200 for any
    # `min_area_pixels` whatsoever, because the constant arm of that `max` floors it.
    #
    # THE FLOOR IS THE NET, which makes the floor load-bearing. `[SP-local-5]` tests it
    # behaviourally, bisecting the boundary out of this function's own verdicts, and goes
    # red when the floor is DELETED, neutralised, loses its constant arm, or has that arm
    # lowered under the proportional one -- all four measured. It deliberately does NOT
    # pin the magnitudes: `3200 -> 5000` and `2.0 -> 2.5` both leave it green, because
    # what makes this length non-zero is the floor's SHAPE, not its value.
    #
    # Keeping the SATURATION clause rather than the value one is what makes one check
    # sufficient: the two lengths are equal, so a non-empty saturation slice means a
    # non-empty value slice, and both `np.percentile` calls below are covered. On numpy
    # 2.3.2 an empty slice makes `np.percentile` raise IndexError, so what this clause
    # stands in front of is a crash, not a soft refusal.
    #
    # A second clause `or len(primary_value_values) == 0` stood here once; `git log -S`
    # on that string finds its removal. Both slices index the SAME `active`, over
    # channels the `missing_support_channels` guard above has already required to share
    # `component_mask`'s shape, so the two lengths are equal by construction -- measured
    # over 37 real pipeline calls, never once apart. The `or` implied they could diverge
    # and sent the next reader hunting for a saturation-empty-but-value-not case that
    # cannot be built. `[SP-local-6]` holds the two slices to one mask through the
    # percentile floor they feed.
    #
    # The same identity-dead `or` stood in `_reclaim_localized_child_mask`
    # (`if sat_values.size == 0 or value_values.size == 0`); it was DELETED on 2026-11-11,
    # whole `if` and both arms, because the `ys.size == 0` guard earlier in that function
    # tests the identical predicate and returns first. This one is kept because its killer is
    # a different shape — an area floor, not an emptiness gate — and `[SP-local-6]` pins
    # the two slices together.
    if len(primary_sat_values) == 0:
        debug["reason"] = "empty_support_values"
        return [], debug

    sat_floor = float(np.percentile(primary_sat_values, 42))
    value_floor = float(np.percentile(primary_value_values, 38))
    score = np.zeros(component_mask.shape, dtype=np.uint8)
    score += (primary_sat >= sat_floor).astype(np.uint8)
    score += (primary_value >= value_floor).astype(np.uint8)

    # The two `if len(...)` guards below cannot take their FALSE edge: the enclosing shape
    # check makes each slice exactly `active_area` long (measured: that identity held over
    # 400 random masks), and THREE things in this function keep that above zero. Two are
    # refusals, and EITHER ALONE suffices - ablate the active-area floor and an all-False
    # `component_mask` comes back `empty_support_values`; ablate `empty_support_values` and
    # it comes back `below_active_area_floor`. The third is a CRASH, and it is why those two
    # are not the whole answer: with BOTH of them ablated the call still never reaches these
    # arcs, it dies at `np.percentile(primary_sat_values, 42)` above with IndexError
    # (measured, numpy 2.3.2). ALL THREE have to go - both refusals plus an empty-safe
    # percentile - before either arc takes its false edge; measured at that rung, each one
    # does. With detectors on both arcs the whole adapters suite passes, so nothing in the
    # tests takes either edge today either.
    if assist_sat is not None and getattr(component_mask, "shape", None) == getattr(assist_sat, "shape", None):
        assist_sat_values = assist_sat[active]
        if len(assist_sat_values):
            assist_sat_floor = float(np.percentile(assist_sat_values, 40))
            score += (assist_sat >= assist_sat_floor).astype(np.uint8)

    if assist_value is not None and getattr(component_mask, "shape", None) == getattr(assist_value, "shape", None):
        assist_value_values = assist_value[active]

        # Unreachable false edge, same reason and the same THREE nets as the assist_sat
        # guard above; measured waking with a detector on this arc alone.
        if len(assist_value_values):
            assist_value_floor = float(np.percentile(assist_value_values, 36))
            score += (assist_value >= assist_value_floor).astype(np.uint8)

    required_score = 3 if (assist_sat is not None and assist_value is not None) else 2
    debug["required_score"] = int(required_score)
    supported = active & (score >= required_score)
    debug["scored_support_area"] = int(np.count_nonzero(supported))
    structure = np.ones((3, 3), dtype=bool)
    supported = _NDIMAGE.binary_opening(supported, structure=structure, iterations=1)
    supported = _NDIMAGE.binary_closing(supported, structure=structure, iterations=1)
    debug["opened_support_area"] = int(np.count_nonzero(supported))
    # REACHABLE, and covered - not a dead guard, do not delete it as one. The floors are
    # percentiles of `active`, so the scored mask always has area (swept: never below 20% of
    # it); only the 3x3 opening above can empty it, which is what `[ECV-30]` in
    # tests/adapters/eufy/test_segmentor.py builds. Delete this and `label` on an empty mask
    # returns 0 components, so the decline below still fires - as
    # `insufficient_support_components`. The net holds, the diagnosis does not.
    if not bool(np.any(supported)):
        # The support mask had area but no BODY: nothing in it survived a 3x3 opening, so
        # `scored_support_area` above is non-zero while this is 0. That pair is the only
        # way to tell this refusal from the two below it.
        debug["reason"] = "no_supported_body"
        return [], debug

    labeled, component_count = _NDIMAGE.label(supported, structure=structure)
    debug["support_component_count"] = int(component_count)
    if component_count < 2:
        debug["reason"] = "insufficient_support_components"
        return [], debug

    grown_masks: list[Any] = []
    seed_areas: list[int] = []
    grown_areas: list[int] = []
    for label_index in range(1, component_count + 1):
        seed_mask = labeled == label_index
        seed_area = int(np.count_nonzero(seed_mask))
        seed_areas.append(seed_area)
        if seed_area < max(int(min_area_pixels * 0.35), 180):
            continue
        grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
        grown_area = int(np.count_nonzero(grown))
        grown_areas.append(grown_area)
        if grown_area < max(int(min_area_pixels * 0.8), 1000):
            continue
        if grown_area > int(active_area * 0.8):
            continue
        # REACHABLE FROM A DIRECT CALLER, NOT FROM THIS MODULE'S PIPELINE, and fixtured since
        # 2026-11-11 by `[SP-local-4]` in tests/adapters/eufy/test_segmentor_splitters.py,
        # which goes red (`grown_mask_count` 3, not 2) when this clause is removed.
        # `binary_propagation` is bounded by `component_mask`, so two supported seeds inside
        # ONE connected sub-blob both reflood it and come back IDENTICAL, overlap 1.0 against
        # the 0.74 here. Measured with this removed: a dim-banded sub-blob at 80% of active
        # turns the `insufficient_grown_masks` decline below into an accept of two identical
        # masks - and 75% does it too, 80% is only the ceiling the area guard above imposes.
        #
        # WHAT IT PROTECTS IS THE CASCADE, NOT THE DUPLICATE MASK. An accept returns from
        # `_split_suspicious_component`, so `assist_hue`, `erosion_seeds` and `opening_split`
        # never run and each child carries a `split_local_support` label that changes its
        # keep/drop path. The duplicate itself does NOT reach the user: the segment dedup at
        # the end of `_detect_room_segments_pipeline` drops a candidate at `overlap >= 0.8`
        # and two identical masks sit at 1.0 - measured by ablating this clause together with
        # the area guard above, which accepted 36 identical masks (`split_generated_regions`
        # 36) and emitted ONE segment, `deduped_regions` 35.
        #
        # The pipeline cannot reach this line at all: it hands the cascade ONE 8-connected
        # component, because the 3x3 opening at the cluster stage erases any neck thin enough
        # for the bbox-crop closing to cut (1 px and 2 px necks arrive as two separate
        # components instead; 3 px and thicker survive the crop). Every reflood therefore
        # equals the whole component and the `> int(active_area * 0.8)` guard above
        # `continue`s on every candidate first - measured, the pipeline's own rows read
        # `grown` = 36 x `active_area`, `grown_mask_count` 0, `insufficient_grown_masks`, and
        # a detector raising unless that piece count is 1 passed all 335 adapter tests. Keep
        # this as the CONTRACT for a caller that hands over a multi-piece mask, which is the
        # only way the duplicate can arise.
        if any(_component_overlap_ratio(grown, existing)[0] >= 0.74 for existing in grown_masks):
            continue
        grown_masks.append(grown)

    debug["seed_areas"] = seed_areas
    debug["grown_areas"] = grown_areas
    debug["grown_mask_count"] = int(len(grown_masks))
    if len(grown_masks) < 2:
        debug["reason"] = "insufficient_grown_masks"
        return [], debug
    debug["accepted"] = True
    debug["reason"] = "accepted"
    return grown_masks, debug


def _split_component_via_color_distance(
    component_mask: Any,
    primary_rgb: Any | None,
    assist_rgb: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    debug: dict[str, Any] = {
        "method": "color_distance",
        "accepted": False,
    }
    if (
        primary_rgb is None
        or getattr(component_mask, "shape", None) != getattr(primary_rgb, "shape", None)[:2]
    ):
        debug["reason"] = "missing_primary_rgb"
        return [], debug

    # REPLICA RN6M6W3H — the splitters' active-area floor, 2 copies, must agree
    # Byte-identical to the block in `_split_component_via_local_support`, which holds the
    # primary anchor. Retune one and this splitter admits a band of components the other
    # refuses, which changes which strategy wins the cascade and nothing reports it.
    # `python scripts/doc_anchor.py --show RN6M6W3H` lists every site.
    active = component_mask.astype(bool)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    if active_area < max(int(min_area_pixels * 2.0), 3200):
        debug["reason"] = "below_active_area_floor"
        return [], debug

    primary_features = _normalized_color_features(primary_rgb)
    features = primary_features
    if assist_rgb is not None and getattr(assist_rgb, "shape", None) == getattr(primary_rgb, "shape", None):
        assist_features = _normalized_color_features(assist_rgb)
        features = (primary_features + assist_features) / 2.0

    feature_values = features[active]
    debug["feature_value_count"] = int(len(feature_values))
    # TWO INDEPENDENT FLOORS - sample size here, component size at this function's
    # `below_active_area_floor` gate - and the second dominates today by accident of the
    # constants, not by identity: `len(feature_values) == active_area`, and
    # `max(int(m*1.2), 1800) < max(int(m*2.0), 3200)` STRICTLY for every `min_area_pixels`
    # (swept 0..1e6 plus negatives and up to 2**53: no violations and no ties; 80 calls aimed
    # straight at the empty window [component floor, feature floor) never reached this
    # reason). That gate is therefore the only net, and the bin floor below is no substitute -
    # at `min_area_pixels` 200 two bins of 100 px clear it out of 1000 samples. TWO edits wake
    # this, not one: lower the `* 2.0` / 3200 expression (measured at `min_area_pixels` 1:
    # fires at areas 400, 500, 1000 and 1799, stops at 1800), or raise THIS floor's own 1800
    # (measured: 1800 -> 4000 fires at 3200 and 3999, not at 4000). Merge the two questions
    # and 8-cubed colour binning runs silently over whatever the surviving floor admits - 400
    # samples at `min_area_pixels` 200, so 1000 is the worked example above, not a bound. The
    # cost is NOISE, not a bad split: with the component floor lowered and this guard removed,
    # areas 400, 500, 1000, 1072 and 2000 all still decline `insufficient_grown_masks`,
    # because a centre's `grown_area` has to clear 900 and stay under `active_area * 0.84` at
    # the same time. Standing cost of keeping it: `insufficient_feature_values` can never be
    # emitted, so it never enters the per-method debug list at all - what reads as a live
    # decline is the string HERE and its census row in docs/testing/subsystems/15-adapters.md.
    if len(feature_values) < max(int(min_area_pixels * 1.2), 1800):
        debug["reason"] = "insufficient_feature_values"
        return [], debug

    quantized = np.clip(np.rint(feature_values * 7.0), 0, 7).astype(np.int16)
    unique_bins, counts = np.unique(quantized, axis=0, return_counts=True)
    ranked = sorted(
        (
            (unique_bins[index], int(counts[index]))
            for index in range(len(unique_bins))
            if int(counts[index]) >= max(int(min_area_pixels * 0.45), int(active_area * 0.1))
        ),
        key=lambda item: -item[1],
    )
    debug["ranked_bin_count"] = int(len(ranked))
    if len(ranked) < 2:
        debug["reason"] = "insufficient_color_bins"
        return [], debug

    centers: list[Any] = []
    first_center = ranked[0][0].astype(np.float32) / 7.0
    centers.append(first_center)
    best_second: Any | None = None
    best_distance = 0.0
    for candidate, _count in ranked[1:]:
        candidate_center = candidate.astype(np.float32) / 7.0
        distance = float(np.linalg.norm(candidate_center - first_center))
        if distance > best_distance:
            best_distance = distance
            best_second = candidate_center
    debug["best_center_distance"] = round(float(best_distance), 4)
    # BOTH halves are dead at HEAD, for DIFFERENT reasons — do not collapse this to one note.
    # `best_second is None`: ranked[1:] is non-empty (the `len(ranked) < 2` refusal above) and
    # np.unique(axis=0) rows are distinct, so the first candidate always beats best_distance 0.0.
    # Weakening `distance > best_distance` wakes this half cleanly (measured: 158 of 400
    # palettes, no raises). Dropping the `len(ranked) < 2` refusal wakes it too, but it does
    # something else first: with `ranked` EMPTY it crashes two lines up at `ranked[0][0]` with
    # "IndexError: list index out of range" — of the same 400 palettes, 162 woke this half and
    # 80 crashed. `best_distance < 0.09`: 0.09 sits BELOW the quantizer's own granularity —
    # exhaustively over all 512 `* 7.0` bins the closest distinct pair is 1/7 = 0.142857, and
    # best_distance is only ever 0.0 or >= 1/7, so today this clause is subsumed by the one to
    # its left. Re-quantizing to 16 LEVELS (`* 15.0`, clip 0..15) drops the floor to 1/15 =
    # 0.0667 and 0.09 does start to bite (measured: 8 of 400); 1/16 = 0.0625 is the 17-level
    # `* 16.0` figure, not this one. THERE IS A NET BELOW, so this clause is not what stands
    # between a close pair and a split on noise: woken at 16 levels with only this clause
    # removed, all 8 close pairs came back seed_areas [0, 0] — the 3x3 opening empties both
    # seeds, the per-centre `seed_area` floor refuses them, and the function declines
    # `insufficient_grown_masks` with zero masks. Note the dead reason is also in the accepted
    # set of test_color_distance_uniform_color_rejects, where it cannot be the value.
    if best_second is None or best_distance < 0.09:
        debug["reason"] = "center_distance_too_small"
        return [], debug
    centers.append(best_second)

    structure = np.ones((3, 3), dtype=bool)
    grown_masks: list[Any] = []
    used_area = 0
    seed_areas: list[int] = []
    grown_areas: list[int] = []
    for center in centers:
        distance_map = np.sqrt(np.sum((features - center[None, None, :]) ** 2, axis=2))
        active_distances = distance_map[active]
        # KEEP — the precondition for the percentile below, not an early-out: np.percentile
        # RAISES on an empty slice ("IndexError: index -1 is out of bounds for axis 0 with
        # size 0" — verbatim, re-measured in the pinned test image at numpy 2.3.2 for (0,),
        # float32 and (0, 2)). Dead because `active` is loop-invariant (assigned once, above
        # the loop) and floored at 3200 by below_active_area_floor. NOT every narrowing of the
        # `active_distances` slice wakes it — only one tight enough to exclude every active
        # pixel from some centre: `distance_map[active & (distance_map <= 0.05)]` skipped a
        # centre in 152 of the 158 runs that reached this loop over 400 generated palettes,
        # and with the guard also removed those same 152 raised that IndexError. A `<= 0.35`
        # cut, a `[::2]` subsample and a nearest-1% cut each left it dead, all three with the
        # guard removed and still no crash. Waking it is CORRECT: skipping a centre with no
        # pixels is what the loop wants. Six further percentile calls carry the same
        # precondition - two in _reclaim_localized_child_mask and four in
        # _split_component_via_local_support, which together are every percentile-family call
        # in this file besides this one (counted from the AST, not by eye). The two in
        # _reclaim_localized_child_mask no longer have a guard ADJACENT to them: the `if`
        # that sat there was dead in both arms and was deleted on 2026-11-11. Their
        # precondition is upheld earlier in that function instead, by its own
        # `ys.size == 0` guard, which tests the identical predicate on the same mask.
        if len(active_distances) == 0:
            continue
        threshold = float(np.percentile(active_distances, 46)) + 0.018
        threshold = max(0.04, min(0.14, threshold))
        seed_threshold = max(0.022, threshold * 0.55)
        allowed = active & (distance_map <= threshold)
        seed_mask = active & (distance_map <= seed_threshold)
        seed_mask = _NDIMAGE.binary_opening(seed_mask, structure=structure, iterations=1)
        seed_area = int(np.count_nonzero(seed_mask))
        seed_areas.append(seed_area)
        if seed_area < max(int(min_area_pixels * 0.18), 90):
            continue
        grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=allowed)
        grown_area = int(np.count_nonzero(grown))
        grown_areas.append(grown_area)
        if grown_area < max(int(min_area_pixels * 0.7), 900):
            continue
        if grown_area > int(active_area * 0.84):
            continue
        if any(_component_overlap_ratio(grown, existing)[0] >= 0.72 for existing in grown_masks):
            continue
        grown_masks.append(grown)
        used_area += grown_area

    debug["seed_areas"] = seed_areas
    debug["grown_areas"] = grown_areas
    debug["grown_mask_count"] = int(len(grown_masks))
    debug["used_area"] = int(used_area)
    if len(grown_masks) < 2:
        debug["reason"] = "insufficient_grown_masks"
        return [], debug
    if used_area < int(active_area * 0.38):
        debug["reason"] = "insufficient_coverage"
        return [], debug
    debug["accepted"] = True
    debug["reason"] = "accepted"
    return grown_masks, debug


def _localize_oversized_component(
    component_mask: Any,
    primary_rgb: Any | None,
    assist_rgb: Any | None,
    assist_hue: Any | None,
    assist_sat: Any | None,
    assist_value: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    debug: dict[str, Any] = {
        "method": "localized_bins",
        "accepted": False,
    }
    if (
        primary_rgb is None
        or getattr(component_mask, "shape", None) != getattr(primary_rgb, "shape", None)[:2]
    ):
        debug["reason"] = "missing_primary_rgb"
        return [], debug

    active = component_mask.astype(bool)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    # LOAD-BEARING, AND ABSOLUTE. The `max(..., 120000)` makes this an absolute
    # floor, not a proportional one: the service admits any `min_area_pixels >= 1`
    # and the 10x term only overtakes 120000 above 12000, so NOTHING smaller than
    # 120000 active pixels enters this body at any admissible tuning. That is what
    # retired the `len(feature_values) == 0` re-check below the quantize step --
    # an empty `active` cannot get past here -- so this floor now carries that net
    # alone. [SP-oversize-floor] / [SP-oversize-dominance] measure it by bisecting
    # this function's own behaviour; soften it to a purely proportional bound and
    # both go red -- so does the older `test_localize_oversized_below_floor`.
    #
    # AND IT IS ITSELF UNREACHABLE FROM ITS ONE CALL SITE. The gate in
    # `_split_suspicious_component` applies the SAME threshold expression to the
    # SAME mask before calling, and `active_area` is that mask's non-zero count, so
    # by the time control arrives here the test has already passed. `[SP-oversize-xsite]`
    # pins that the gate and this floor are one threshold, so a one-sided retune of the
    # pair reddens. This floor therefore fires only for a DIRECT caller, and it stays
    # for two reasons: it is the same-function invariant holder for the empty-`active`
    # case, and it is the net if that gate is ever loosened. Retune one of the pair
    # without the other and components between the two floors change behaviour.
    if active_area < max(int(min_area_pixels * 10), 120000):
        debug["reason"] = "below_oversized_floor"
        return [], debug

    features = _normalized_color_features(primary_rgb)
    if assist_rgb is not None and getattr(assist_rgb, "shape", None) == getattr(primary_rgb, "shape", None):
        features = (features + _normalized_color_features(assist_rgb)) / 2.0

    quantized = np.clip(np.rint(features * 7.0), 0, 7).astype(np.int16)
    feature_values = quantized[active]
    # There is deliberately no `len(feature_values) == 0` check here. ONE reason
    # it could not fire, with a second condition closing the only other
    # mechanism: the absolute floor in this same function refuses an empty
    # `active` -- measured, ablating that floor alone makes this check FIRE --
    # and a boolean index over the leading
    # axes yields one ROW per live pixel, so `len` is `count_nonzero(active)`
    # whatever the feature axis holds -- including a zero-width one.
    unique_bins, counts = np.unique(feature_values, axis=0, return_counts=True)
    min_bucket = max(int(min_area_pixels * 0.9), int(active_area * 0.025))
    max_bucket = int(active_area * 0.24)
    ranked_colors = sorted(
        (
            (unique_bins[index], int(counts[index]))
            for index in range(len(unique_bins))
            if min_bucket <= int(counts[index]) <= max_bucket
        ),
        key=lambda item: -item[1],
    )

    ranked_hues: list[tuple[int, int]] = []
    if (
        assist_hue is not None
        and assist_sat is not None
        and assist_value is not None
        and getattr(assist_hue, "shape", None) == getattr(component_mask, "shape", None)
    ):
        assist_active = active & (assist_sat >= 16) & (assist_value >= 70)
        hue_values = assist_hue[assist_active]
        if len(hue_values):
            hue_bins = ((hue_values.astype(np.int16) + 6) // 12).astype(np.int16)
            unique_hues, hue_counts = np.unique(hue_bins, return_counts=True)
            ranked_hues = sorted(
                (
                    (int(unique_hues[index]), int(hue_counts[index]))
                    for index in range(len(unique_hues))
                    if min_bucket <= int(hue_counts[index]) <= max_bucket
                ),
                key=lambda item: -item[1],
            )

    debug["ranked_color_bins"] = int(len(ranked_colors))
    debug["ranked_hue_bins"] = int(len(ranked_hues))
    structure = np.ones((3, 3), dtype=bool)
    candidate_masks: list[Any] = []
    candidate_areas: list[int] = []

    def _try_add_candidate(seed_mask: Any) -> None:
        opened = _NDIMAGE.binary_opening(seed_mask, structure=structure, iterations=1)
        # KEEP. This early-out is what made a `count <= 0` guard below it
        # unreachable: `label()` reports at least one feature for any mask holding a
        # True pixel, so past this line `count >= 1`. That guard is deleted:
        # measured over 847 arrivals at the `label()` below -- the committed fixture
        # maps through `detect_room_segments`, plus a direct `min_area_pixels` sweep
        # of 1..1000000 -- it never fired once, and the lowest count seen past this
        # line was 1, exactly the bound it was testing. 847 counts arrivals PAST
        # this line; arrivals AT it are strictly more whenever this early-out fires,
        # which on dithered colour seeds is every time.
        #
        # Be clear about what this line is, though, because it is NOT the net.
        # Deleting it would not change which candidates this closure appends, only
        # how much work it does: `find_objects` of an all-zero label array is `[]`
        # and `range(1, 0 + 1)` is empty, so the loop below is already a no-op at
        # count 0. The sibling `label()` call in `_detect_room_segments_pipeline`
        # leans on exactly that and carries no count guard at all -- it took
        # count == 0 154 times in those same runs. So the real net under
        # `_try_add_candidate` is the empty range; this line is an early-out that
        # saves the label and find_objects work and kills the guard as a
        # side-effect. Inverting its sense DOES change behaviour, and that is the
        # edit [SP-D3-4] catches. See [SP-D3-1..4] in test_segmentor_splitters.py.
        if not bool(np.any(opened)):
            return
        labeled, count = _NDIMAGE.label(opened, structure=structure)
        slices = _NDIMAGE.find_objects(labeled)
        for label_index in range(1, count + 1):
            label_slice = slices[label_index - 1] if label_index - 1 < len(slices) else None
            # Dead for `_NDIMAGE.label` output: label() relabels to a consecutive 1..n set, so
            # find_objects returns exactly `count` slices, no None entry (400 random runs on
            # scipy 1.18.1: 0 None entries, 0 `len(slices) != count`, nonzero labels exactly
            # 1..count in 200/200). Both arms document the contract for any OTHER producer --
            # find_objects on a GAPPED label array does return None (labels {1,3} give
            # [slice, None, slice]).
            #
            # The net below is the AREA FLOOR, not a crash. A None entry means that label has no
            # pixels, so `labeled[None] == label_index` -- numpy adds an axis rather than raising
            # -- counts 0, and :860 continues on the hard 1400 arm of
            # `max(int(min_area_pixels * 0.9), 1400)` for every min_area_pixels. MEASURED: gap this
            # label() output and delete this guard and the full pipeline is byte-identical (11
            # candidates, same areas, no exception). The `y_slice, x_slice` unpack is NOT reachable
            # from a gapped producer. It raises TypeError only for a SHORT-LIST producer
            # (`len(slices) < count` with the labels present), which this guard also covers -- that
            # ablation does raise, at :864. So this line buys clarity and a little work, not a crash.
            #
            # The twin in _detect_room_segments_pipeline is equally unreachable but its net is the
            # OPPOSITE: it unpacks at :1397 with no area floor in between, so deleting it there
            # kills the whole run with TypeError (measured, same gapped producer). DO NOT make the
            # pair read the same -- that site is the one that needs the crash warning.
            if label_slice is None:
                continue
            local_mask = labeled[label_slice] == label_index
            local_area = int(np.count_nonzero(local_mask))
            if local_area < max(int(min_area_pixels * 0.9), 1400):
                continue
            if local_area > int(active_area * 0.22):
                continue
            y_slice, x_slice = label_slice
            global_mask = np.zeros_like(component_mask, dtype=bool)
            global_mask[y_slice, x_slice] = local_mask
            h = int((y_slice.stop or 0) - (y_slice.start or 0))
            w = int((x_slice.stop or 0) - (x_slice.start or 0))
            fill_ratio = local_area / max(float(w * h), 1.0)
            if fill_ratio < 0.16:
                continue
            if any(max(_component_overlap_ratio(global_mask, existing)) >= 0.68 for existing in candidate_masks):
                continue
            candidate_masks.append(global_mask)
            candidate_areas.append(local_area)

    for color_bin, _count in ranked_colors[:6]:
        seed_mask = active & np.all(quantized == color_bin[None, None, :], axis=2)
        _try_add_candidate(seed_mask)

    if ranked_hues:
        assist_hue_bins = ((assist_hue.astype(np.int16) + 6) // 12).astype(np.int16)
        assist_active = active & (assist_sat >= 16) & (assist_value >= 70)
        for hue_bin, _count in ranked_hues[:4]:
            seed_mask = assist_active & (assist_hue_bins == hue_bin)
            _try_add_candidate(seed_mask)

    debug["candidate_count"] = int(len(candidate_masks))
    debug["candidate_areas"] = candidate_areas
    if len(candidate_masks) < 2:
        debug["reason"] = "insufficient_localized_candidates"
        return [], debug

    debug["accepted"] = True
    debug["reason"] = "accepted"
    return candidate_masks, debug


def _split_component_via_assist_hue(
    component_mask: Any,
    assist_hue: Any | None,
    assist_sat: Any | None,
    assist_value: Any | None,
    min_area_pixels: int,
) -> tuple[list[Any], dict[str, Any]]:
    debug: dict[str, Any] = {
        "method": "assist_hue",
        "accepted": False,
    }
    if (
        assist_hue is None
        or assist_sat is None
        or assist_value is None
        or getattr(component_mask, "shape", None) != getattr(assist_hue, "shape", None)
    ):
        debug["reason"] = "missing_assist_inputs"
        return [], debug

    active = component_mask & (assist_sat >= 16) & (assist_value >= 70)
    active_area = int(np.count_nonzero(active))
    debug["active_area"] = active_area
    # LOAD-BEARING FLOOR -- it is the only thing keeping the hue sample below non-empty,
    # and that sample carries no emptiness check of its own. Two facts do the work:
    #   1. `max(int(min_area_pixels * 1.8), 3500)` sits at or above 3500 for every value
    #      the `min_area_pixels` service field admits
    #      (`vol.All(vol.Coerce(int), vol.Range(min=1))`, no upper bound), and for 0 or a
    #      negative too -- so passing here means `active_area >= 3500`. The deletion
    #      needs only `>= 1`, and that margin is what a retune has to spend.
    #   2. `active` is a BOOLEAN ndarray of `assist_hue`'s shape, so
    #      `len(assist_hue[active]) == active_area`.
    # An `if len(hue_values) == 0` guard sat just below until 2026-11-11 and was deleted
    # as unreachable; that transferred the whole net to this line.
    # WHAT BREAKS (1) IS A FLOOR THAT CAN EVALUATE TO 0 -- retuning 3500 to 0, or dropping
    # the `max` wrapper so `int(min_area_pixels * 1.8)` stands alone -- and NOT a downward
    # retune as such: measured, 3500 -> 1000 leaves this guard exactly as unreachable.
    # Even a 0 floor then needs a caller passing `min_area_pixels <= 0`, which the service
    # schema refuses and `detect_room_segments` clamps away with `int(max(..., 1))`.
    # Breaking (2) is subtler: `active` here is boolean only because it is built by
    # comparison, where two sibling splitters and `_localize_oversized_component` write
    # `component_mask.astype(bool)` -- and with an INTEGER `active` that sample silently
    # becomes FANCY INDEXING of length `shape[0]` instead of a masked selection
    # (measured on one 200x200 mask: bool -> 26, uint8 -> 200). [SP-hue-floor] and
    # [SP-hue-sample] pin both facts.
    if active_area < max(int(min_area_pixels * 1.8), 3500):
        debug["reason"] = "below_active_area_floor"
        return [], debug

    hue_values = assist_hue[active]
    hue_bins = ((hue_values.astype(np.int16) + 6) // 12).astype(np.int16)
    unique_bins, counts = np.unique(hue_bins, return_counts=True)
    ranked_bins = sorted(
        (
            (int(bin_index), int(count))
            for bin_index, count in zip(unique_bins.tolist(), counts.tolist(), strict=False)
            if int(count) >= max(int(min_area_pixels * 0.9), int(active_area * 0.14))
        ),
        key=lambda item: -item[1],
    )
    debug["ranked_bin_count"] = int(len(ranked_bins))
    if len(ranked_bins) < 2:
        debug["reason"] = "insufficient_ranked_bins"
        return [], debug

    selected_bins: list[int] = []
    for bin_index, _count in ranked_bins:
        if not selected_bins:
            selected_bins.append(bin_index)
            continue
        if all(min(abs(bin_index - prev), 15 - abs(bin_index - prev)) >= 2 for prev in selected_bins):
            selected_bins.append(bin_index)
        if len(selected_bins) >= 3:
            break

    if len(selected_bins) < 2:
        debug["reason"] = "insufficient_selected_bins"
        return [], debug

    structure = np.ones((3, 3), dtype=bool)
    grown_masks: list[Any] = []
    used_seed_area = 0
    debug["selected_bins"] = [int(item) for item in selected_bins]
    seed_areas: list[int] = []
    grown_areas: list[int] = []
    for bin_index in selected_bins:
        seed_mask = active & (((assist_hue.astype(np.int16) + 6) // 12) == bin_index)
        seed_mask = _NDIMAGE.binary_opening(seed_mask, structure=structure, iterations=1)
        if not bool(np.any(seed_mask)):
            seed_areas.append(0)
            continue
        seed_areas.append(int(np.count_nonzero(seed_mask)))
        grown = _NDIMAGE.binary_propagation(seed_mask, structure=structure, mask=component_mask)
        grown_area = int(np.count_nonzero(grown))
        grown_areas.append(grown_area)
        if grown_area < max(int(min_area_pixels * 0.8), 1200):
            continue
        if grown_area > int(active_area * 0.82):
            continue
        if any(_component_overlap_ratio(grown, existing)[0] >= 0.72 for existing in grown_masks):
            continue
        grown_masks.append(grown)
        used_seed_area += grown_area

    debug["seed_areas"] = seed_areas
    debug["grown_areas"] = grown_areas
    debug["grown_mask_count"] = int(len(grown_masks))
    debug["used_area"] = int(used_seed_area)
    if len(grown_masks) < 2:
        debug["reason"] = "insufficient_grown_masks"
        return [], debug
    if used_seed_area < int(active_area * 0.45):
        debug["reason"] = "insufficient_coverage"
        return [], debug
    debug["accepted"] = True
    debug["reason"] = "accepted"
    return grown_masks, debug


def _split_suspicious_component(
    component_mask: Any,
    min_area_pixels: int,
    wall_hint_mask: Any | None = None,
    primary_rgb: Any | None = None,
    assist_rgb: Any | None = None,
    primary_sat: Any | None = None,
    primary_value: Any | None = None,
    assist_hue: Any | None = None,
    assist_sat: Any | None = None,
    assist_value: Any | None = None,
) -> tuple[list[Any], str | None, list[dict[str, Any]]]:
    """Try each available split strategy in priority order and return the first that succeeds.

    Returns (split_masks, method_name, debug_entries). method_name is None if no split was found.
    """
    debug_entries: list[dict[str, Any]] = []
    # `debug_entries` is passed so a DECLINE is recorded too. Every other strategy below
    # appends whether it succeeds or fails; this one appended only on success, which made
    # the first-tried strategy the one whose failure could not be seen.
    split_masks = _split_component_via_wall_cuts(
        component_mask, wall_hint_mask, min_area_pixels, debug_entries
    )
    if len(split_masks) >= 2:
        return split_masks, "wall_cuts", [{"method": "wall_cuts", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)}]
    if int(np.count_nonzero(component_mask)) >= max(int(min_area_pixels * 10), 120000):
        split_masks, debug = _localize_oversized_component(
            component_mask,
            primary_rgb,
            assist_rgb,
            assist_hue,
            assist_sat,
            assist_value,
            min_area_pixels,
        )
        debug_entries.append(debug)
        if len(split_masks) >= 2:
            return split_masks, "localized_bins", debug_entries
    split_masks, debug = _split_component_via_color_distance(
        component_mask,
        primary_rgb,
        assist_rgb,
        min_area_pixels,
    )
    debug_entries.append(debug)
    if len(split_masks) >= 2:
        return split_masks, "color_distance", debug_entries
    split_masks, debug = _split_component_via_local_support(
        component_mask,
        primary_sat,
        primary_value,
        assist_sat,
        assist_value,
        min_area_pixels,
    )
    # Take the callee's OWN debug row, as every other strategy here does. This block
    # used to synthesise one -- "accepted" on success, a bare "no_split" otherwise --
    # because the function returned no reason to append, which is what made all six of
    # its refusals read identically (D20 / [SP-wall-dbg] is the same shape).
    debug_entries.append(debug)
    if len(split_masks) >= 2:
        return split_masks, "local_support", debug_entries
    split_masks, debug = _split_component_via_assist_hue(
        component_mask,
        assist_hue,
        assist_sat,
        assist_value,
        min_area_pixels,
    )
    debug_entries.append(debug)
    if len(split_masks) >= 2:
        return split_masks, "assist_hue", debug_entries
    split_masks = _split_component_via_erosion(component_mask, min_area_pixels)
    if len(split_masks) >= 2:
        debug_entries.append({"method": "erosion_seeds", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)})
        return split_masks, "erosion_seeds", debug_entries
    debug_entries.append({"method": "erosion_seeds", "accepted": False, "reason": "no_split"})
    split_masks = _split_component_via_opening(component_mask, min_area_pixels)
    if len(split_masks) >= 2:
        debug_entries.append({"method": "opening_split", "accepted": True, "reason": "accepted", "grown_mask_count": len(split_masks)})
        return split_masks, "opening_split", debug_entries
    debug_entries.append({"method": "opening_split", "accepted": False, "reason": "no_split"})
    return [], None, debug_entries


def _prune_localized_siblings(
    localized_segments: list[dict[str, Any]],
    deduped_count: int,
) -> tuple[list[dict[str, Any]], int]:
    """Rank localized-bins child segments and drop overlapping siblings.

    A localized-bins split can emit several overlapping children for one oversized
    parent component. Rank them strongest-first (confidence -> fill_ratio ->
    compactness -> area_pixels) and keep a child only if its mask does not overlap
    an already-kept sibling by >= 0.35 (each drop bumps ``deduped_count``), capping
    at the top 4. Returns the pruned list and the updated dedupe counter; an empty
    input is a no-op (sorted([]) -> []).
    """
    ranked = sorted(
        localized_segments,
        key=lambda item: (
            -float(item.get("confidence", 0.0)),
            -float(item.get("fill_ratio", 0.0)),
            -float(item.get("compactness", 0.0)),
            -float(item.get("area_pixels", 0)),
        ),
    )
    pruned_localized: list[dict[str, Any]] = []
    for candidate in ranked:
        candidate_mask = candidate.get("_global_mask")
        sibling_overlap = False
        for kept in pruned_localized:
            kept_mask = kept.get("_global_mask")
            overlap_a, overlap_b = _component_overlap_ratio(candidate_mask, kept_mask)
            if max(overlap_a, overlap_b) >= 0.35:
                sibling_overlap = True
                deduped_count = int(deduped_count) + 1
                break
        if sibling_overlap:
            continue
        pruned_localized.append(candidate)
    return pruned_localized[:4], deduped_count


# -- Component keep/drop decision ---------------------------------------------

def _component_should_keep(
    *,
    area: int,
    area_percent: float,
    fill_ratio: float,
    compactness: float,
    aspect_ratio: float,
    agreement_score: float,
    touches_border: bool,
    min_area_pixels: int,
    recovery_mode: bool = False,
) -> tuple[bool, list[str]]:
    """Decide whether a small component is worth keeping.

    Returns (keep, reasons). Small components below min_area_pixels may still
    be kept if geometric signals (compactness, aspect ratio, agreement) are strong.
    """
    reasons: list[str] = []
    if area < 220 and not recovery_mode:
        reasons.append("below_tiny_floor")
        return False, reasons
    small_cutoff = max(180, int(min_area_pixels * (0.65 if recovery_mode else 0.85)))
    if area >= min_area_pixels:
        return True, reasons

    if area < small_cutoff:
        reasons.append("below_small_cutoff")

    if compactness >= 0.22 and fill_ratio >= 0.5:
        reasons.append("compact_small_region")
    if aspect_ratio >= 2.2 and fill_ratio >= 0.42 and not touches_border:
        reasons.append("elongated_enclosed_region")
    if agreement_score >= 0.55:
        reasons.append("confirmed_by_variants")
    if recovery_mode and area_percent >= 0.002 and fill_ratio >= 0.42:
        reasons.append("recovery_candidate")

    keep = any(
        reason in reasons
        for reason in (
            "compact_small_region",
            "elongated_enclosed_region",
            "confirmed_by_variants",
            "recovery_candidate",
        )
    )
    return keep, reasons


# -- Main segmentation pipeline -----------------------------------------------

def _detect_room_segments_pipeline(
    *,
    image_path: str,
    expected_room_count: int | None = None,
    max_segments: int | None = None,
    min_area_pixels: int = 1200,
    simplify_epsilon: float | None = None,
    assist_image_path: str | None = None,
    image_variant: str | None = None,
    assist_variant: str | None = None,
) -> dict[str, Any]:
    """Run the Pillow/NumPy/SciPy segmentation pipeline.

    Segments the primary map image by HSV hue clustering, optionally guided
    by a second image variant for wall-cut refinement. Returns the full
    segmentation result dict including segments, summary, and pipeline diagnostics.
    """
    if not (_PIL_SCIPY_READY and _NDIMAGE is not None):
        return {
            "available": False,
            "reason": "pipeline_unavailable",
            "message": "Pillow/scipy-based segmentation pipeline is not available in this environment.",
            "runtime": image_runtime_capabilities(),
            "segments": [],
        }

    try:
        image = PIL_Image.open(str(image_path)).convert("RGB")
    except Exception:
        _LOGGER.exception("Failed to read map image at %s", image_path)
        return {
            "available": False,
            "reason": "image_unreadable",
            "message": "Could not read the saved map image.",
            "runtime": image_runtime_capabilities(),
            "segments": [],
        }

    rgb = np.asarray(image, dtype=np.uint8)
    hsv = np.asarray(image.convert("HSV"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    image_area = float(width * height)
    hue = hsv[:, :, 0]

    structure = np.ones((3, 3), dtype=bool)
    merge_structure = np.ones((5, 5), dtype=bool)
    room_mask = _build_room_mask_from_hsv(hsv)
    base_room_mask = room_mask.copy()
    assist_registration: dict[str, Any] | None = None
    aligned_assist_room_mask: Any | None = None
    aligned_wall_mask: Any | None = None
    seam_wall_mask: Any | None = None
    removed_by_walls_mask: Any | None = None
    aligned_assist_rgb: Any | None = None
    aligned_assist_hue: Any | None = None
    aligned_assist_sat: Any | None = None
    aligned_assist_value: Any | None = None

    if assist_image_path:
        try:
            assist_image = PIL_Image.open(str(assist_image_path)).convert("RGB")
            assist_rgb = np.asarray(assist_image, dtype=np.uint8)
            assist_hsv = np.asarray(assist_image.convert("HSV"), dtype=np.uint8)
            assist_room_mask = _build_room_mask_from_hsv(assist_hsv)
            registration = _estimate_alignment(room_mask, assist_room_mask)
            aligned_assist_room_mask = _transform_mask(
                assist_room_mask,
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_room_mask = _NDIMAGE.binary_dilation(aligned_assist_room_mask, structure=structure, iterations=2)
            aligned_assist_rgb = _transform_color_image(
                assist_rgb,
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_hue = _transform_scalar_image(
                assist_hsv[:, :, 0],
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_sat = _transform_scalar_image(
                assist_hsv[:, :, 1],
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_assist_value = _transform_scalar_image(
                assist_hsv[:, :, 2],
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )

            assist_wall_mask = _build_light_wall_mask(assist_hsv)
            aligned_wall_mask = _transform_mask(
                assist_wall_mask,
                float(registration["scale"]),
                int(registration["shift_x"]),
                int(registration["shift_y"]),
                room_mask.shape,
            )
            aligned_wall_mask = _NDIMAGE.binary_dilation(aligned_wall_mask, structure=structure, iterations=1)
            edge_hint = _mask_edge_band(base_room_mask, iterations=2)
            seam_zone = _NDIMAGE.binary_dilation(edge_hint, structure=merge_structure, iterations=1)
            seam_wall_mask = aligned_wall_mask & seam_zone
            # WHY: narrow seam cutting only — broad subtraction erased valid room
            # pixels because the light-image wall mask also captures background gradients.
            room_mask = base_room_mask & ~seam_wall_mask
            room_mask = _NDIMAGE.binary_opening(room_mask, structure=structure, iterations=1)
            room_mask = _NDIMAGE.binary_closing(room_mask, structure=structure, iterations=2)
            room_mask = _NDIMAGE.binary_fill_holes(room_mask)
            removed_by_walls_mask = base_room_mask & ~room_mask

            assist_registration = {
                "enabled": True,
                "assist_variant": assist_variant,
                "assist_image_path": assist_image_path,
                "scale": registration["scale"],
                "shift_x": registration["shift_x"],
                "shift_y": registration["shift_y"],
                "score": registration["score"],
            }
        except Exception as err:
            assist_registration = {
                "enabled": False,
                "assist_variant": assist_variant,
                "assist_image_path": assist_image_path,
                "error": f"{type(err).__name__}: {err}",
            }

    if not bool(np.any(room_mask)):
        return {
            "available": False,
            "reason": "no_room_pixels_detected",
            "message": "No room-like regions were detected in the image.",
            "runtime": image_runtime_capabilities(),
            "segments": [],
            "image": {"width": int(width), "height": int(height)},
            "segmentation": {
                "pipeline": "pillow_numpy_scipy",
                "registration": assist_registration,
                "image_variant": image_variant,
                "assist_variant": assist_variant,
            },
        }

    # HUE CLUSTERING, and the world fact the whole pipeline rests on: THE EUFY RENDERER
    # PAINTS EACH ROOM A DISTINCT HUE. Median-filter the hue plane, bin it into 16-wide
    # buckets, then iterate the active bins below — a hue bin corresponds to a room
    # because of that RENDERING property, not because of anything true about rooms.
    #
    # Salvaged 2026-08-24 from the retired `26-eufy-segmentor.md`. Nothing in source said
    # why hue was the clustering space, which leaves the choice reading as a generic
    # computer-vision decision. It is not: the algorithm is keyed to a property of the
    # VENDOR'S map image, so a port to another brand, or a Eufy palette change,
    # invalidates the premise directly rather than merely needing the constants re-tuned.
    hue_smooth = _NDIMAGE.median_filter(hue, size=5)
    hue_bin = ((hue_smooth.astype(np.int16) + 8) // 16).astype(np.int16)
    active_bins = sorted({int(value) for value in hue_bin[room_mask]})

    segments: list[dict[str, Any]] = []
    segment_id = 1
    stage_counts: dict[str, Any] = {
        "clusters_seen": len(active_bins),
        "components_seen": 0,
        "split_candidates": 0,
        "split_generated_regions": 0,
        "kept_regions": 0,
        "recovered_regions": 0,
        "dropped_regions": 0,
    }
    deferred_small_regions: list[dict[str, Any]] = []

    for bin_index in active_bins:
        cluster_mask = room_mask & (hue_bin == bin_index)
        if not bool(np.any(cluster_mask)):
            continue

        # Merge same-hue fragments before labelling to reduce over-segmentation.
        cluster_mask = _NDIMAGE.binary_closing(cluster_mask, structure=merge_structure, iterations=2)
        cluster_mask = _NDIMAGE.binary_opening(cluster_mask, structure=structure, iterations=1)
        cluster_mask = _NDIMAGE.binary_fill_holes(cluster_mask)

        labeled, component_count = _NDIMAGE.label(cluster_mask, structure=structure)
        slices = _NDIMAGE.find_objects(labeled)
        for label_index in range(1, component_count + 1):
            label_slice = slices[label_index - 1] if label_index - 1 < len(slices) else None
            # Dead here for the same scipy contract as the twin in `_try_add_candidate`:
            # `label()` relabels to a consecutive 1..n set, so `find_objects` returns exactly
            # `component_count` slices and never a None entry. DELIBERATELY NOT WORDED THE SAME
            # AS THAT TWIN, because the two do not net the same thing — measured through
            # `EufyCVSegmenter.segment_map_image` on the committed fixture pair, with a
            # short-list producer applied at each site's own `find_objects`:
            #     _try_add_candidate   guard present -> 8 of 10 segments; deleted -> TypeError
            #     HERE                 guard present -> 0 segments, `reason: "ready"`
            #                          deleted       -> available False, "engine_exception"
            # Firing here swallows EVERY component in the hue bin and the run still reports
            # success with zero segments — indistinguishable from "this map has no rooms", which
            # is the absence trap rather than a visible failure. That makes this the worse of
            # the two to wake and the more important of the two to keep.
            # The None has TWO producers, not one: a foreign producer whose `find_objects` is
            # gapped, and the ternary on the line directly above, whose `else None` arm is dead
            # by the same contract. Four dead arms across the two sites.
            if label_slice is None:
                continue
            stage_counts["components_seen"] += 1

            component_mask = labeled[label_slice] == label_index

            y_slice, x_slice = label_slice
            x = int(x_slice.start or 0)
            y = int(y_slice.start or 0)
            w = int((x_slice.stop or 0) - x)
            h = int((y_slice.stop or 0) - y)

            component_mask = _NDIMAGE.binary_closing(component_mask, structure=merge_structure, iterations=1)
            component_mask = _NDIMAGE.binary_fill_holes(component_mask)
            area = int(np.count_nonzero(component_mask))

            touches_border = x <= 1 or y <= 1 or (x + w) >= (width - 1) or (y + h) >= (height - 1)
            fill_ratio = area / max(float(w * h), 1.0)
            area_percent = area / image_area
            perimeter = _mask_perimeter(component_mask)
            compactness = _compactness(area, perimeter)
            aspect_ratio = _aspect_ratio(w, h)

            component_rgb_full = rgb[y : y + h, x : x + w]
            component_hsv_full = hsv[y : y + h, x : x + w]
            component_rgb = component_rgb_full[component_mask]
            component_hsv = component_hsv_full[component_mask]
            mean_rgb = component_rgb.mean(axis=0) if len(component_rgb) else np.array([0.0, 0.0, 0.0])
            mean_saturation = float(component_hsv[:, 1].mean()) if len(component_hsv) else 0.0
            color_bgr = [int(round(float(mean_rgb[2]))), int(round(float(mean_rgb[1]))), int(round(float(mean_rgb[0])))]
            component_global = np.zeros_like(room_mask, dtype=bool)
            component_global[y : y + h, x : x + w] = component_mask
            agreement_score = _agreement_score(component_global, aligned_assist_room_mask)

            issues: list[str] = []
            if area_percent < 0.015 and agreement_score < 0.5:
                issues.append("tiny_region")
            if touches_border:
                issues.append("touches_border")
            if fill_ratio < 0.42:
                issues.append("possible_merge")
            if area_percent > 0.45:
                issues.append("oversized_region")
            if compactness < 0.08 and area_percent < 0.02:
                issues.append("fragmented_candidate")

            suspicious_merge = (
                area >= max(int(min_area_pixels * 4), 5200)
                and (fill_ratio < 0.58 or area_percent > 0.18 or "oversized_region" in issues)
            )
            split_masks: list[Any] = []
            split_method: str | None = None
            split_debug: list[dict[str, Any]] = []
            if suspicious_merge:
                stage_counts["split_candidates"] += 1
                split_masks, split_method, split_debug = _split_suspicious_component(
                    component_mask,
                    int(max(min_area_pixels, 1)),
                    wall_hint_mask=seam_wall_mask[y : y + h, x : x + w] if seam_wall_mask is not None else None,
                    primary_rgb=rgb[y : y + h, x : x + w],
                    assist_rgb=aligned_assist_rgb[y : y + h, x : x + w] if aligned_assist_rgb is not None else None,
                    primary_sat=component_hsv_full[:, :, 1],
                    primary_value=component_hsv_full[:, :, 2],
                    assist_hue=aligned_assist_hue[y : y + h, x : x + w] if aligned_assist_hue is not None else None,
                    assist_sat=aligned_assist_sat[y : y + h, x : x + w] if aligned_assist_sat is not None else None,
                    assist_value=aligned_assist_value[y : y + h, x : x + w] if aligned_assist_value is not None else None,
                )
                if split_debug:
                    stage_counts.setdefault("split_debug", []).append(
                        {
                            "cluster_index": int(bin_index),
                            "bbox": _bbox_from_stats(int(x), int(y), int(w), int(h)),
                            "area_pixels": int(area),
                            "fill_ratio": round(fill_ratio, 4),
                            "area_percent": round(area_percent, 4),
                            "methods": split_debug,
                        }
                    )

            masks_to_emit: list[tuple[Any, str | None]] = []
            if len(split_masks) >= 2:
                stage_counts["split_generated_regions"] += len(split_masks)
                masks_to_emit = [(mask, split_method) for mask in split_masks]
            else:
                masks_to_emit = [(component_mask, None)]

            for local_mask, local_split_method in masks_to_emit:
                if local_split_method == "localized_bins":
                    local_mask = _reclaim_localized_child_mask(
                        local_mask,
                        component_mask,
                        primary_sat=component_hsv_full[:, :, 1],
                        primary_value=component_hsv_full[:, :, 2],
                        assist_sat=aligned_assist_sat[y : y + h, x : x + w] if aligned_assist_sat is not None else None,
                        assist_value=aligned_assist_value[y : y + h, x : x + w] if aligned_assist_value is not None else None,
                    )
                local_area = int(np.count_nonzero(local_mask))
                if local_area <= 0:
                    continue
                local_indices = np.argwhere(local_mask)
                local_y0 = int(local_indices[:, 0].min())
                local_y1 = int(local_indices[:, 0].max()) + 1
                local_x0 = int(local_indices[:, 1].min())
                local_x1 = int(local_indices[:, 1].max()) + 1
                cropped_mask = local_mask[local_y0:local_y1, local_x0:local_x1]
                global_x = x + local_x0
                global_y = y + local_y0
                global_w = local_x1 - local_x0
                global_h = local_y1 - local_y0

                polygon_local, raw_point_count = _mask_to_polygon(cropped_mask, simplify_epsilon=simplify_epsilon)
                polygon = [[pt[0] + global_x, pt[1] + global_y] for pt in polygon_local]
                simplified_point_count = len(polygon)
                if simplified_point_count < 4:
                    stage_counts["dropped_regions"] += 1
                    continue

                local_touches_border = global_x <= 1 or global_y <= 1 or (global_x + global_w) >= (width - 1) or (global_y + global_h) >= (height - 1)
                local_fill_ratio = local_area / max(float(global_w * global_h), 1.0)
                local_area_percent = local_area / image_area
                local_perimeter = _mask_perimeter(cropped_mask)
                local_compactness = _compactness(local_area, local_perimeter)
                local_aspect_ratio = _aspect_ratio(global_w, global_h)

                local_component_global = np.zeros_like(room_mask, dtype=bool)
                local_component_global[global_y : global_y + global_h, global_x : global_x + global_w] = cropped_mask
                local_agreement_score = _agreement_score(local_component_global, aligned_assist_room_mask)
                local_mean_value = float(
                    hsv[global_y : global_y + global_h, global_x : global_x + global_w][cropped_mask][:, 2].mean()
                ) if np.count_nonzero(cropped_mask) else 0.0

                local_issues = list(issues)
                if simplified_point_count > 18:
                    local_issues.append("too_complex")
                if local_split_method:
                    local_issues.append(f"split_{local_split_method}")
                if local_fill_ratio < 0.42 and "possible_merge" not in local_issues:
                    local_issues.append("possible_merge")
                if local_mean_value < 118 and local_area < max(1800, int(min_area_pixels * 1.4)):
                    local_issues.append("dock_dark_artifact")
                if (global_w <= 4 or global_h <= 4 or local_aspect_ratio >= 10.0) and local_area < max(1600, int(min_area_pixels * 1.3)):
                    local_issues.append("thin_artifact")

                keep_now, local_keep_reasons = _component_should_keep(
                    area=local_area,
                    area_percent=local_area_percent,
                    fill_ratio=local_fill_ratio,
                    compactness=local_compactness,
                    aspect_ratio=local_aspect_ratio,
                    agreement_score=local_agreement_score,
                    touches_border=local_touches_border,
                    min_area_pixels=int(max(min_area_pixels, 1)),
                    recovery_mode=False,
                )

                confidence = 0.9
                confidence -= min(len([item for item in local_issues if not str(item).startswith("split_")]) * 0.1, 0.45)
                if local_fill_ratio < 0.55:
                    confidence -= 0.12
                if simplified_point_count > 14:
                    confidence -= 0.1
                confidence += min(local_agreement_score * 0.12, 0.12)
                confidence = max(0.05, min(0.99, round(confidence, 4)))

                candidate = {
                    "segment_id": f"segment_{segment_id}",
                    "cluster_index": int(bin_index),
                    "bbox": _bbox_from_stats(global_x, global_y, global_w, global_h),
                    "area_pixels": local_area,
                    "area_percent": round(local_area_percent, 4),
                    "polygon_pixel": polygon,
                    "point_count_raw": raw_point_count,
                    "point_count_simplified": simplified_point_count,
                    "center_pixel": [round(global_x + (global_w / 2.0), 2), round(global_y + (global_h / 2.0), 2)],
                    "fill_ratio": round(local_fill_ratio, 4),
                    "quality": _issue_quality(local_issues, confidence),
                    "confidence": confidence,
                    "issues": local_issues,
                    "suggested_color_bgr": color_bgr,
                    "mean_saturation": round(mean_saturation, 2),
                    "mean_value": round(local_mean_value, 2),
                    "compactness": round(local_compactness, 4),
                    "aspect_ratio": round(local_aspect_ratio, 4),
                    "variant_agreement": round(local_agreement_score, 4),
                    "variant_support": (
                        "both" if local_agreement_score >= 0.55
                        else "primary_only"
                    ),
                    "structural_role": _structural_role(
                        area_percent=local_area_percent,
                        aspect_ratio=local_aspect_ratio,
                        fill_ratio=local_fill_ratio,
                    ),
                    "segmentation_state": _segmentation_state(
                        issues=local_issues,
                        fill_ratio=local_fill_ratio,
                        compactness=local_compactness,
                    ),
                    "local_split_suspicion": suspicious_merge,
                    "edit_readiness": (
                        "ready" if confidence >= 0.78 and simplified_point_count <= 18
                        else "review"
                    ),
                    "matched_room_id": None,
                    "matched_room_label": None,
                    "_split_method": local_split_method,
                    "_keep_reasons": local_keep_reasons,
                    "_global_mask": local_component_global,
                }

                drop_reasons: list[str] = []
                if local_area_percent > 0.45:
                    keep_now = False
                    drop_reasons.append("area_percent_too_large")
                if "dock_dark_artifact" in local_issues:
                    keep_now = False
                    drop_reasons.append("dock_dark_artifact")
                if "thin_artifact" in local_issues:
                    keep_now = False
                    drop_reasons.append("thin_artifact")
                if "oversized_region" in local_issues:
                    if local_split_method != "localized_bins":
                        keep_now = False
                        drop_reasons.append("oversized_region")
                if local_split_method == "assist_hue" and (
                    local_area_percent > 0.24 or local_fill_ratio < 0.26 or local_compactness < 0.08
                ):
                    keep_now = False
                    drop_reasons.append("assist_hue_child_rejected")
                if area_percent > 0.3 and mean_saturation < 30 and not local_split_method:
                    keep_now = False
                    drop_reasons.append("low_saturation_large_parent")
                if local_split_method == "localized_bins":
                    hard_reject_localized = False
                    if local_area_percent < 0.0025 and local_area < max(1100, int(min_area_pixels * 0.9)):
                        keep_now = False
                        hard_reject_localized = True
                        drop_reasons.append("localized_child_too_small")
                    elif local_fill_ratio < 0.12:
                        keep_now = False
                        hard_reject_localized = True
                        drop_reasons.append("localized_child_sparse")
                    else:
                        # WHY: localized children are partial color pockets, so lower
                        # compactness/fill thresholds apply than for generic split paths.
                        if "possible_merge" in local_issues and local_fill_ratio >= 0.18:
                            local_issues = [issue for issue in local_issues if issue != "possible_merge"]
                            candidate["issues"] = local_issues
                        if confidence < 0.7:
                            confidence = max(confidence, 0.72)
                            candidate["confidence"] = confidence
                            candidate["quality"] = _issue_quality(local_issues, confidence)
                        if local_aspect_ratio >= 4.5 and local_area < max(4200, int(min_area_pixels * 2.8)):
                            keep_now = False
                            hard_reject_localized = True
                            drop_reasons.append("localized_child_connector")
                        if local_compactness < 0.03 and local_fill_ratio < 0.28:
                            keep_now = False
                            hard_reject_localized = True
                            drop_reasons.append("localized_child_fragment")
                        if not hard_reject_localized:
                            keep_now = keep_now or (
                                local_area >= max(1100, int(min_area_pixels * 0.9))
                                and local_fill_ratio >= 0.18
                                and local_compactness >= 0.04
                            )

                if keep_now and not (local_touches_border and local_fill_ratio < 0.18 and local_area_percent > 0.03):
                    segments.append(candidate)
                    stage_counts["kept_regions"] += 1
                    segment_id += 1
                else:
                    candidate["_drop_reasons"] = drop_reasons
                    deferred_small_regions.append(candidate)
                    stage_counts["dropped_regions"] += 1

    deduped_count = 0
    localized_segments = [
        item for item in segments
        if str(item.get("_split_method") or "") == "localized_bins"
    ]
    other_segments = [
        item for item in segments
        if str(item.get("_split_method") or "") != "localized_bins"
    ]
    localized_segments, deduped_count = _prune_localized_siblings(
        localized_segments, deduped_count
    )

    segments = other_segments + localized_segments
    segments.sort(key=lambda item: (-float(item.get("area_pixels", 0)), str(item.get("segment_id", ""))))
    deduped_segments: list[dict[str, Any]] = []
    for candidate in segments:
        candidate_mask = candidate.get("_global_mask")
        drop_candidate = False
        for kept in deduped_segments:
            kept_mask = kept.get("_global_mask")
            overlap_a, overlap_b = _component_overlap_ratio(candidate_mask, kept_mask)
            same_center = (
                abs(float(candidate.get("center_pixel", [0, 0])[0]) - float(kept.get("center_pixel", [0, 0])[0])) <= 28
                and abs(float(candidate.get("center_pixel", [0, 0])[1]) - float(kept.get("center_pixel", [0, 0])[1])) <= 28
            )
            if overlap_a >= 0.8 or overlap_b >= 0.8 or (same_center and max(overlap_a, overlap_b) >= 0.55):
                drop_candidate = True
                deduped_count += 1
                break
        if not drop_candidate:
            deduped_segments.append(candidate)
    segments = deduped_segments

    if expected_room_count and len(segments) < int(expected_room_count):
        deficit = int(expected_room_count) - len(segments)
        deferred_small_regions.sort(
            key=lambda item: (
                -float(item.get("variant_agreement", 0)),
                -float(item.get("compactness", 0)),
                -float(item.get("fill_ratio", 0)),
                -float(item.get("area_pixels", 0)),
            )
        )
        for candidate in deferred_small_regions:
            if deficit <= 0:
                break
            candidate_issues = list(candidate.get("issues") or [])
            if any(
                issue in candidate_issues
                for issue in ("dock_dark_artifact", "thin_artifact", "oversized_region", "fragmented_candidate")
            ):
                continue
            if float(candidate.get("area_percent", 0.0)) > 0.2:
                continue
            if int(candidate.get("area_pixels", 0)) < max(220, int(min_area_pixels * 0.4)):
                continue
            keep_now, local_keep_reasons = _component_should_keep(
                area=int(candidate.get("area_pixels", 0)),
                area_percent=float(candidate.get("area_percent", 0.0)),
                fill_ratio=float(candidate.get("fill_ratio", 0.0)),
                compactness=float(candidate.get("compactness", 0.0)),
                aspect_ratio=float(candidate.get("aspect_ratio", 0.0)),
                agreement_score=float(candidate.get("variant_agreement", 0.0)),
                touches_border=("touches_border" in (candidate.get("issues") or [])),
                min_area_pixels=int(max(min_area_pixels, 1)),
                recovery_mode=True,
            )
            if not keep_now:
                continue
            candidate["issues"] = [issue for issue in (candidate.get("issues") or []) if issue != "tiny_region"]
            candidate["issues"].append("recovered_count_deficit")
            candidate["confidence"] = max(float(candidate.get("confidence", 0.0)), 0.62)
            candidate["quality"] = _issue_quality(list(candidate["issues"]), float(candidate["confidence"]))
            candidate["segment_id"] = f"segment_{segment_id}"
            candidate["variant_support"] = (
                "both" if float(candidate.get("variant_agreement", 0.0)) >= 0.55
                else str(candidate.get("variant_support") or "primary_only")
            )
            candidate["_keep_reasons"] = list(local_keep_reasons)
            segments.append(candidate)
            stage_counts["recovered_regions"] += 1
            segment_id += 1
            deficit -= 1

    segments.sort(key=lambda item: (-float(item.get("area_pixels", 0)), str(item.get("segment_id", ""))))
    if max_segments is not None and max_segments > 0:
        segments = segments[: int(max_segments)]

    quality_counts: dict[str, int] = {}
    for segment in segments:
        segment.pop("_keep_reasons", None)
        segment.pop("_global_mask", None)
        segment.pop("_split_method", None)
        segment.pop("_drop_reasons", None)
        quality = str(segment.get("quality") or "unknown")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1

    assist_enabled = bool(
        isinstance(assist_registration, dict)
        and assist_registration.get("enabled")
    )
    message = "Image-assisted room segments generated via the Pillow/NumPy/SciPy pipeline."
    if assist_enabled:
        message = "Image-assisted room segments generated via the Pillow/NumPy/SciPy pipeline using primary and assist image variants."

    return {
        "available": True,
        "reason": "ready",
        "message": message,
        "runtime": image_runtime_capabilities(),
        "image": {
            "width": int(width),
            "height": int(height),
        },
        "segmentation": {
            "expected_room_count": int(expected_room_count or 0),
            "cluster_count": len(active_bins),
            "room_pixel_count": int(np.count_nonzero(room_mask)),
            "min_area_pixels": int(max(min_area_pixels, 1)),
            "simplify_epsilon": None if simplify_epsilon is None else float(simplify_epsilon),
            "pipeline": "pillow_numpy_scipy",
            "image_variant": image_variant,
            "assist_variant": assist_variant,
            "registration": assist_registration,
            "stages": {
                "base_mask_generation": {
                    "room_pixel_count": int(np.count_nonzero(base_room_mask)),
                    "left_right": _mask_left_right_counts(base_room_mask),
                },
                "variant_reconciliation": {
                    "assist_enabled": assist_enabled,
                    "agreement_pixel_count": int(np.count_nonzero(base_room_mask & aligned_assist_room_mask)) if aligned_assist_room_mask is not None else 0,
                    "wall_pixel_count": int(np.count_nonzero(aligned_wall_mask)) if aligned_wall_mask is not None else 0,
                    "seam_wall_pixel_count": int(np.count_nonzero(seam_wall_mask)) if seam_wall_mask is not None else 0,
                    "removed_by_wall_cut_pixel_count": int(np.count_nonzero(removed_by_walls_mask)) if removed_by_walls_mask is not None else 0,
                    "removed_by_wall_cut_left_right": _mask_left_right_counts(removed_by_walls_mask) if removed_by_walls_mask is not None else {"left": 0, "right": 0},
                    "reconciled_room_pixel_count": int(np.count_nonzero(room_mask)),
                    "reconciled_left_right": _mask_left_right_counts(room_mask),
                },
                "connected_components": {
                    "clusters_seen": int(stage_counts["clusters_seen"]),
                    "components_seen": int(stage_counts["components_seen"]),
                },
                "candidate_scoring": {
                    "kept_regions": int(stage_counts["kept_regions"]),
                    "dropped_regions": int(stage_counts["dropped_regions"]),
                    "deduped_regions": int(deduped_count),
                },
                "suspicious_region_split_pass": {
                    "split_candidates": int(stage_counts["split_candidates"]),
                    "split_generated_regions": int(stage_counts["split_generated_regions"]),
                    "debug": stage_counts.get("split_debug", []),
                    "localized_drop_debug": [
                        {
                            "segment_id": str(item.get("segment_id")),
                            "area_pixels": int(item.get("area_pixels", 0)),
                            "area_percent": float(item.get("area_percent", 0.0)),
                            "fill_ratio": float(item.get("fill_ratio", 0.0)),
                            "compactness": float(item.get("compactness", 0.0)),
                            "issues": list(item.get("issues") or []),
                            "drop_reasons": list(item.get("_drop_reasons") or []),
                        }
                        for item in deferred_small_regions
                        if str(item.get("_split_method") or "") == "localized_bins"
                    ],
                },
                "recovery_pass": {
                    "recovered_regions": int(stage_counts["recovered_regions"]),
                    "count_deficit_after_recovery": max(0, int(expected_room_count or 0) - len(segments)),
                },
            },
        },
        "summary": {
            "segment_count": len(segments),
            "quality_counts": quality_counts,
            "good_or_better_count": sum(
                1 for segment in segments
                if str(segment.get("quality")) in {"good", "strong"}
            ),
        },
        "segments": segments,
    }


def detect_room_segments(
    *,
    image_path: str,
    expected_room_count: int | None = None,
    max_segments: int | None = None,
    min_area_pixels: int = 1200,
    simplify_epsilon: float | None = None,
    assist_image_path: str | None = None,
    image_variant: str | None = None,
    assist_variant: str | None = None,
) -> dict[str, Any]:
    """Return suggested room-like segments from a clean unlabeled map image."""
    return _detect_room_segments_pipeline(
        image_path=image_path,
        expected_room_count=expected_room_count,
        max_segments=max_segments,
        min_area_pixels=min_area_pixels,
        simplify_epsilon=simplify_epsilon,
        assist_image_path=assist_image_path,
        image_variant=image_variant,
        assist_variant=assist_variant,
    )
