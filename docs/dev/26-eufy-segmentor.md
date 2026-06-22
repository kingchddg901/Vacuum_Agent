# 26 — The Eufy CV Segmentor — Implementation & Segmenter-Engine Pattern

> **Scope:** The concrete computer-vision room segmenter
> (`adapters/eufy/segmentor.py`, ~1600 lines) and the engine contract it
> implements (`mapping/segmenter_engines.py`). **Dual-purpose**: it documents how
> `eufy_cv_v1` actually turns a map image into rooms, and it is the **pattern
> guide** for a second brand writing its own segmenter.
>
> The generic mapping subsystem (coordinate tracking, bounds learning, the
> segmenter *seam*) is [11-mapping-system](11-mapping-system.md); the adapter that
> *selects* this engine is [25-eufy-adapter](25-eufy-adapter.md). This doc is the
> engine internals.

---

## 1. Where this fits

The framework never calls `segmentor.py` directly. The adapter declares
`mapping.segmenter_engine: "eufy_cv_v1"`; the framework looks that name up in
`mapping/segmenter_engines.py` and calls the engine through a small protocol. A
brand with no map image declares `"noop_fallback"` instead — the card stops
drawing polygon overlays, but trace-based tracking (vacuum-space coordinates)
keeps working. So the segmenter is **optional and swappable**; this is the seam
that keeps CV out of the brand-agnostic core.

The Eufy pipeline is **pure NumPy + Pillow + SciPy** — there is **no `cv2`**
(OpenCV is absent on the HA host). All morphology is `scipy.ndimage`; contour
tracing + simplification is hand-rolled (RDP) in `mapping/segment_primitives.py`.

---

## 2. The segmenter-engine contract (the pattern)

Defined in `mapping/segmenter_engines.py`. Any brand engine implements this — it
is the entire surface area:

```python
class MapSegmenter(Protocol):           # segmenter_engines.py
    engine_name: str
    def validate_tuning(self, tuning: dict) -> list[str]: ...
    def segment_map_image(self, *, image_path, tuning, context=None) -> SegmentationResult: ...
```

- **Registration:** no decorator. A module-level dict `_SEGMENTER_ENGINES` maps
  name → singleton instance. `get_segmenter_engine(name)` returns the instance,
  or `noop_fallback` with a warning on an unknown name. `known_engine_names()`
  feeds the adapter validator, so a config naming a missing engine is flagged at
  registration (see [21 §2.2](21-adapter-system.md)).
- **`validate_tuning`** returns a list of issue strings (empty = valid). The Eufy
  engine rejects keys outside its known set and type-checks each.
- **`segment_map_image`** is the framework entry point. The Eufy wrapper
  (`EufyCVSegmenter`, `engine_name = "eufy_cv_v1"`) guards a null `image_path`,
  maps tuning → `detect_room_segments(...)` kwargs, runs the pipeline inside a
  `try`, and reshapes the result (hoisting CV-only diagnostic blocks into
  `engine_diagnostics`).
- **Statelessness:** singletons hold no per-call state; the same input must
  produce the same output.

> **Pattern for a new brand:** add a `{Brand}Segmenter` class with these three
> members, register it in `_SEGMENTER_ENGINES`, and you're done — the rest of the
> framework already knows how to call it.

---

## 3. `eufy_cv_v1` — what it wraps

`EufyCVSegmenter.segment_map_image` calls **`detect_room_segments()`** (the public
function in `segmentor.py`), which delegates to the private
**`_detect_room_segments_pipeline()`**. The pipeline is built on the
brand-agnostic primitives in `mapping/segment_primitives.py` (polygon math, mask
ops, HSV helpers, RDP). Input is a **filesystem path** to a clean, *unlabeled*
Eufy map PNG; output is a pure-Python `SegmentationResult` dict.

Coordinate space is **canvas pixel space** — origin top-left, y-down. Segment IDs
are **positional** (`segment_1`, `segment_2`, …, 1-based), *not* vendor room IDs; matching
canvas segments to vendor room IDs happens downstream (`matched_room_id` is always
`None` here).

---

## 4. The pipeline, end to end

All logic lives in `_detect_room_segments_pipeline()`. Stages in order:

1. **Load & readiness.** If Pillow/SciPy aren't importable → degraded return.
   Open the PNG, convert to RGB; derive HSV and a hue plane.
2. **Room mask** (`_build_room_mask_from_hsv`). Threshold on value + saturation,
   then `binary_opening` → `binary_closing` (×2) → `binary_fill_holes` to get a
   clean "floor" mask.
3. **Assist-variant reconciliation (optional).** If an `assist_image_path` is
   given, build its room mask, estimate scale/shift alignment, reproject the
   assist masks/RGB/HSV into the primary frame, and cut **only seam-zone walls**
   (`room_mask & ~seam_wall_mask`) so valid pixels aren't erased.
4. **No-room guard.** Empty mask → degraded `no_room_pixels_detected`.
5. **Hue clustering.** Median-filter the hue plane, bin into 16-wide buckets;
   iterate the active bins (Eufy renders each room in a distinct hue).
6. **Connected components per hue bin.** Merge same-hue fragments (closing /
   opening / fill), `ndimage.label`, `find_objects`, per-component cleanup.
7. **Per-component metrics + issue flags.** fill ratio, area %, compactness,
   aspect ratio, mean color, agreement vs the assist mask; flags like
   `tiny_region`, `touches_border`, `possible_merge`, `oversized_region`,
   `fragmented_candidate`.
8. **Suspicious-merge split.** Large, low-fill / oversized components run the
   splitter cascade (§5).
9. **Emit candidates.** For each (possibly split) mask: crop, trace the outer
   boundary via the hand-rolled edge-follower in
   `segment_primitives.mask_to_polygon` (per-cell boundary edges → closed-loop
   walk with angle-sorted junctions → largest-area loop), then RDP-simplify it
   (`simplify_epsilon`, auto-derived when `None`), offset to global coords,
   recompute metrics, compute `confidence`, assign `quality` / `structural_role`
   / `segmentation_state` / `edit_readiness`, then keep/drop rules. Kept →
   `segments`; dropped → `deferred_small_regions`.
10. **Localized-bins dedup.** Localized child rooms sorted by confidence, pruned
    at overlap ≥ 0.35, capped at 4.
11. **Global dedup.** Drop near-duplicates (high overlap or near-identical center).
12. **Recovery pass.** If fewer segments than `expected_room_count`, re-admit the
    best deferred regions (`recovery_mode=True`). *(This is the count-deficit
    backfill — distinct from the failure path in §7.)*
13. **Finalize.** Sort, apply `max_segments`, strip private `_*` keys, build the
    `summary` and nested `segmentation.stages` diagnostics.

---

## 5. The splitter cascade

When stage 8 flags a component as a probable merge of multiple rooms,
`_split_suspicious_component()` tries strategies in priority order and returns the
first that yields ≥ 2 masks:

| # | Strategy | How |
|---|---|---|
| 1 | `_split_component_via_wall_cuts` | subtract dilated wall-hint pixels, re-label, regrow seeds |
| 2 | `_localize_oversized_component` | very large blobs: quantize color into 8³ **"localized bins"**, seed/grow distinct color pockets |
| 3 | `_split_component_via_color_distance` | two farthest color-bin centers, distance-threshold + propagate |
| 4 | `_split_component_via_local_support` | per-channel sat/value percentile scoring, require score ≥ 2 (3 with assist), label + grow |
| 5 | `_split_component_via_assist_hue` | bin the assist image's hue, pick ≥ 2 separated bins, seed/grow |
| 6 | `_split_component_via_erosion` | progressive `binary_erosion` (1–4 iters) until ≥ 2 seeds, regrow |
| 7 | `_split_component_via_opening` | same idea via `binary_opening` |

`_reclaim_localized_child_mask` repairs vertically-clipped localized children;
`_component_should_keep` arbitrates small-region keep/drop. This cascade plus the
recovery loop is why the module is a deliberate coverage thin spot (~91%) — most
strategies only fire on specific multi-room imagery (§9).

---

## 6. Tuning parameters

The `segmenter_tuning` dict (validated against the engine's known-key set):

| Key | Default | Controls |
|---|---|---|
| `min_area_pixels` | 1200 | minimum component area to keep; scales most split/keep thresholds |
| `simplify_epsilon` | `None` | RDP polygon simplification tolerance. `None` = **auto-derive** the epsilon (`max(1.0, sqrt(raw_point_count) * 0.42)`); a positive float overrides it. Simplification **always** runs — `None` is not "off". |
| `expected_room_count` | `None` | triggers the recovery backfill when fewer rooms are found |
| `max_segments` | `None` | hard cap on emitted segments |
| `assist_image_path` | `None` | second image variant enabling wall-cut / color refinement |
| `image_variant` / `assist_variant` | `None` | provenance labels (diagnostics only) |

Eufy ships `min_area_pixels: 1200`, `simplify_epsilon: None`,
`expected_room_count: None` (see [25 §4 `mapping`](25-eufy-adapter.md)).

---

## 7. Degraded & recovery paths

Distinguish two unrelated concepts that both contain the word "recovery":

- **Hard failure (the wrapper).** Any exception inside `detect_room_segments`
  is caught by `segment_map_image`, which returns the canonical empty result via
  `_engine_unavailable(reason="engine_exception")` — `available: False`,
  `segments: []`, empty summary, plus `engine_diagnostics["runtime"]`. The card
  falls back to no overlay; nothing crashes upstream.
- **Pipeline-internal degraded returns** (also `available: False`):
  `pipeline_unavailable` (no SciPy/Pillow), `image_unreadable`,
  `no_room_pixels_detected`. These carry partial diagnostics.
- **Recovery *pass*** (stage 12) is **not** a failure path — it's the count-deficit
  backfill that re-admits deferred regions when `expected_room_count` wasn't met.

> **Pattern:** never raise out of a segmenter. Return the empty
> `SegmentationResult` with a `reason`; the framework treats "no segments" as a
> normal, recoverable state.

---

## 8. Output data shapes

`SegmentationResult` (defined in `segmenter_engines.py`):

```
{
  "available": bool,
  "reason": str, "message": str, "engine": str,
  "image": {"width": int, "height": int},
  "segments": [ <segment>, … ],
  "summary": {"segment_count": int, "quality_counts": {...}, "good_or_better_count": int},
  "engine_diagnostics": {...}      # CV-only blocks hoisted here by the wrapper
}
```

Each **segment** (canonical fields):

```
segment_id        str           # "segment_1", positional (1-based) — NOT a vendor room id
polygon_pixel     [[x, y], …]   # canvas pixel space
bbox              {x, y, width, height}
area_pixels       int
area_percent      float
center_pixel      [x, y]
confidence        float 0–1
quality           "strong" | "good" | "usable" | "poor"
structural_role   str           # engine-defined; eufy_cv_v1 emits "hub" | "connector" | "spine" | "room" | "uncertain"
segmentation_state str
edit_readiness    str
matched_room_id   None          # filled downstream, not here
matched_room_label None
```

Enriched diagnostics also include `cluster_index`, `fill_ratio`, `compactness`,
`aspect_ratio`, `issues[]`, `suggested_color_bgr`, mean saturation/value, and
variant-agreement scores.

---

## 9. Gotchas (and why coverage is ~91%)

- **No cv2.** Everything is `scipy.ndimage` + hand-rolled geometry in
  `segment_primitives.py`. A second-brand author copies
  `_build_room_mask_from_hsv` + the scoring heuristics and **re-tunes the
  thresholds** for their palette.
- **Magic-number heaviness.** Dozens of empirically calibrated thresholds (HSV
  cutoffs, percentiles, area floors, overlap ratios) tuned to Eufy's map palette —
  brittle to theme/palette changes.
- **Real coordinate transforms.** Assist-variant alignment estimates scale + shift
  and reprojects four image planes; it's a genuine registration step.
- **Performance.** O(active hue bins × components), each running repeated
  `binary_*` morphology and propagation over full-image arrays — the splitter is
  the hot path on complex maps.
- **Coverage.** The 7-strategy splitter cascade and the localized-bins +
  recovery branches have many data-dependent paths that only fire on specific
  multi-room imagery; on simple maps most are untaken. This is the deliberate thin
  spot called out in [testing/subsystems/15-adapters](../testing/subsystems/15-adapters.md).

---

## 10. Writing a segmenter for a new brand

1. Add `{Brand}Segmenter` (a class with `engine_name`, `validate_tuning`,
   `segment_map_image`) — typically wrapping your own `detect_room_segments`-style
   function. Build on `mapping/segment_primitives.py` for geometry so you don't
   re-implement polygon math.
2. Register the instance in `_SEGMENTER_ENGINES` under a versioned name
   (`{brand}_cv_v1`).
3. Return a `SegmentationResult` with positional `segment_id`s and
   `matched_room_id: None`; never raise — degrade with a `reason`.
4. Declare `mapping.segmenter_engine: "{brand}_cv_v1"` in the adapter config, with
   a `segmenter_tuning` your `validate_tuning` accepts.
5. If you have no map asset, declare `"noop_fallback"` and skip all of the above —
   trace tracking still works off coordinates.
