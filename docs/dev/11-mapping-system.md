# 11 — Mapping System

This document covers the mapping subsystem: image segment analysis, room-bounds learning, segment adjustments, custom layouts, the provider map source, and all on-disk storage. It is intended to expose the full algorithms and mathematics so a developer can understand, modify, or port the system.

> **Status (mapping split).** The run-derived *inference* lineage — trace capture / segmentation / review, room-boundary derivation (vacuum-space polygons), the affine transform-fitting pipeline, image-segment *suggestion*, **and the learned per-room bounding-box store (`room_bounds.py` / `RoomBoundsStore`) itself** — was retired. Room tracking now runs off the device's **native current-room** signal: the tracker resolves it and fires `eufy_vacuum_room_completed` (with each room's dwell duration) via a confidence/dwell debounce, and the map card's companion homes off the live map source's `current_room` — nothing runs in drifting vacuum-coordinates anymore. What survives is the CV segmentation pipeline (§2), segment adjustments (§5), image variants (§6), custom layouts (§10), and the provider map source (§11). The retired designs are preserved in git history and the boundary-derivation design note; **§3 below is kept only as historical reference — its code is deleted.**

---

## 1. Overview

The mapping system has three subsystems that address different aspects of knowing where rooms are. The first two — covered in depth here — are local: they derive room geometry from a map PNG (pixel space) or learn it from cleaning runs (vacuum space). The third reads the room layout the provider's *own* firmware already knows.

**Image segment analysis** answers: *given a map PNG, what regions probably correspond to rooms?* It is a pure computer-vision pipeline that works from pixel data alone. The brand-agnostic geometry/image primitives live in `mapping/segment_primitives.py`; the Eufy HSV pipeline that uses them lives in `adapters/eufy/segmentor.py` and is invoked through the segmenter-engine abstraction in `mapping/segmenter_engines.py`. Its outputs are polygons in pixel space, labelled with quality signals (confidence, structural role, issues). These polygons are used as room shape overlays in the UI map card.

**Room tracking** (`tracker.py`) answers: *which room is the robot in right now?* The tracker reads the device's **native current-room** signal (the adapter's `active_cleaning_target`), resolves it to a managed room, and — through a confidence/dwell debounce — fires `eufy_vacuum_room_completed` with each room's dwell duration as the robot moves between rooms. The earlier learned bounding-box approach (run-derived, in vacuum coordinates) was **removed**: the device re-bases its coordinate origin every session, so cross-session bounds drifted (see §3, kept as historical reference).

**Provider map source** (`map_state_source`) answers: *what room layout does the provider's own firmware already know?* Rather than deriving rooms from pixels (image analysis) or learning them from drifting robot samples (trace bounds), this reader normalises the device's authoritative segmentation — per-room bbox/name plus dock/robot anchors and (later waves) area, current room, and overlay layers — into VA-owned room data in a single rendered-image-normalised (0–1) coordinate space. It is covered in §11 and documented in full in the design reference [`dev/map-state-source.md`](map-state-source.md).

The two subsystems are **independent** and operate in different coordinate spaces — image analysis in pixel space, trace bounds in vacuum space. There is no transform between them: the legacy "System A" affine vacuum↔pixel transform was removed.

- Room-boundary *derivation* (vacuum-space polygons learned from a robot boundary-trace trail) was retired with the mapping split. Room presence is now the accumulated bounding box (§3) alone.
- The room bounds and the image-segment polygon serve complementary but unconnected purposes: the image segment gives shape (pixel space); the bounds give a reliable presence envelope (vacuum space).
- Because no pixel↔vacuum transform exists, an image-space polygon can never be tested against a live (vacuum-space) position — the two spaces are never mixed.

---

## 2. Image Segment Analysis Pipeline

The public entry point is `detect_room_segments(...)` in `adapters/eufy/segmentor.py`, which delegates to `_detect_room_segments_pipeline(...)`. It is built on the brand-agnostic primitives in `mapping/segment_primitives.py` and is reached at runtime via the `EufyCVSegmenter` wrapper in `mapping/segmenter_engines.py` (the segmenter-engine abstraction that lets a non-Eufy brand swap in its own pipeline).

### 2.1 Input

```
detect_room_segments(
    image_path: str,                    # primary map PNG (dark or default variant preferred)
    expected_room_count: int | None,    # hint — enables count-deficit recovery pass
    max_segments: int | None,           # hard cap on output segment count
    min_area_pixels: int = 1200,        # minimum region area to consider
    simplify_epsilon: float | None,     # RDP polygon simplification tolerance
    assist_image_path: str | None,      # secondary image variant (light) for wall cutting
    image_variant: str | None,          # metadata label, e.g. "dark"
    assist_variant: str | None,         # metadata label, e.g. "light"
)
```

The caller (`_handle_analyze_map_image` in `mapping_services.py`) selects the primary image with preference order `dark → default`, and uses `light` as the assist if present.

### 2.2 Room Pixel Mask — HSV Thresholds

The first step converts the RGB image to HSV (Pillow `"HSV"` mode, uint8 [0–255] for all channels) and applies two thresholds to produce a binary room-pixel mask:

```python
room_mask = (value >= 68) & (saturation >= 18)
```

Pixels must be both bright enough (value ≥ 68/255 ≈ 27% brightness) and colourful enough (saturation ≥ 18/255 ≈ 7%) to be treated as room pixels. This excludes near-black walls, near-white backgrounds, and the off-white dock area.

Morphological cleanup is applied after thresholding:

1. `binary_opening` (3×3, 1 iteration) — removes isolated noise specks.
2. `binary_closing` (3×3, 2 iterations) — bridges small gaps within rooms.
3. `binary_fill_holes` — fills enclosed background pockets.

The result is `base_room_mask` (saved for diagnostics).

### 2.3 Assist Image Alignment and Wall Cutting

When an assist image is provided, the pipeline:

1. Builds a room mask from the assist image using the same HSV thresholds.
2. Estimates alignment between the two room masks via `_estimate_alignment`, which is a brute-force IoU grid search over scales `[0.94, 0.97, 1.0, 1.03, 1.06]` and pixel shifts `[-24, -18, ..., +24]` on each axis (step 6), finding the transform that maximises intersection-over-union.
3. Warps the assist image (mask, RGB, H, S, V channels separately) into the primary image's coordinate frame using the found scale/shift.
4. Builds a wall mask from the assist image using the near-white threshold: `value >= 214` and `saturation <= 36`.
5. Restricts wall cuts to a *seam zone*: pixels within a dilated edge band of `base_room_mask`. This prevents broad wall-mask subtraction from erasing valid room pixels — only the seam between regions is cut.
6. Applies: `room_mask = base_room_mask & ~seam_wall_mask`, then re-applies opening/closing/fill.

The result is a room mask with wall-like seam pixels removed where the two images agree.

### 2.4 Hue Clustering

The pipeline works on hue because Eufy map images assign distinct colours to each room. The smoothed hue image is:

```python
hue_smooth = median_filter(hue, size=5)
hue_bin = ((hue_smooth.astype(int16) + 8) // 16).astype(int16)
```

This quantises the 0–255 hue range into 16-unit bins (bins 0–15). The `+8` centres each bin on its midpoint. All distinct bin values present in the room mask become separate clusters. There is no fixed number of clusters — the set is derived entirely from what hue values are present.

For each cluster (hue bin), the pipeline:

1. Extracts the cluster mask: `room_mask & (hue_bin == bin_index)`.
2. Applies `binary_closing` (5×5, 2 iterations) to merge nearby fragments of the same hue, then `binary_opening` (3×3, 1 iteration) and `binary_fill_holes`.
3. Calls `scipy.ndimage.label` with an 8-connected structure to find connected components.

### 2.5 Per-Component Metrics

For each connected component the following are computed:

| Metric | Formula |
|--------|---------|
| `area` | `count_nonzero(component_mask)` |
| `area_percent` | `area / (width × height)` |
| `fill_ratio` | `area / (bbox_width × bbox_height)` |
| `perimeter` | count of exposed 4-connected edges |
| `compactness` | `(4π × area) / perimeter²` (1.0 = circle, lower = irregular) |
| `aspect_ratio` | `max(w,h) / min(w,h)` |
| `agreement_score` | fraction of component pixels confirmed by the aligned assist mask |

Issue flags are set based on these metrics:
- `tiny_region`: `area_percent < 0.015` and `agreement_score < 0.5`
- `touches_border`: component bbox is within 1 pixel of the image edge
- `possible_merge`: `fill_ratio < 0.42` — suggests two rooms merged at a doorway
- `oversized_region`: `area_percent > 0.45`
- `fragmented_candidate`: `compactness < 0.08` and `area_percent < 0.02`

### 2.6 Cascade Splitting Algorithm

A component is flagged as a suspicious merge when:

```python
area >= max(4 × min_area_pixels, 5200) and (fill_ratio < 0.58 or area_percent > 0.18 or "oversized_region" in issues)
```

When flagged, `_split_suspicious_component` attempts these strategies in priority order, stopping at the first success (2+ output masks):

1. **`wall_cuts`** — dilate the seam wall mask into the component; erode by 1–3 iterations; re-label; propagate seeds back into the full component mask.
2. **`localized_bins`** — only for very large components (`area >= max(10 × min_area_pixels, 120_000)`). Quantises normalised chromaticity features into 7-level bins, ranks bins by size (filtering to `[min_area_pixels × 0.9, active_area × 0.24]` range), selects up to 6 colour bins and 4 hue bins as seeds, and grows each seed back into the component.
3. **`color_distance`** — normalised RGB chromaticity features (illumination-invariant). Finds the most distinct bin pair (requiring Euclidean distance ≥ 0.09 in normalised feature space), seeds each, and propagates. Requires `used_area >= 38%` of the active area for acceptance.
4. **`local_support`** — scores pixels by whether they exceed per-channel percentile thresholds (P42 saturation, P38 value from primary; P40 saturation, P36 value from assist). A pixel needs a combined score ≥ 2 (or 3 with both assist channels). Clusters the high-scoring pixels and propagates back.
5. **`assist_hue`** — bins assist-image hue into 12-unit bins (15 bins total over 0–180). Selects bins with size ≥ `max(0.9 × min_area_pixels, 14% of active)`, ensuring angular separation ≥ 2 bins (24°) between selected bins. Propagates each into the component.
6. **`erosion_seeds`** — progressively erodes (1–4 iterations) until the component splits, then propagates each seed back.
7. **`opening_split`** — `binary_opening` at increasing iterations (1–4) to split; propagates back.

Each strategy requires all resulting sub-masks to have area ≥ `max(350, 0.45 × min_area_pixels)`.

After splitting via `localized_bins`, the `_reclaim_localized_child_mask` function attempts to recover vertically truncated children. It trims sparse top rows (rows with fewer pixels than 42% of the dense-row median), then performs a constrained downward propagation (`binary_propagation`) from the lower seed band, limited to pixels that pass saturation and value floor thresholds derived from the child mask's own P20 values.

### 2.7 Polygon Extraction

Each kept component mask is converted to a polygon by `_mask_to_polygon`:

1. Builds an edge graph by scanning each `True` pixel for exposed edges (top/right/bottom/left). Each exposed edge becomes a directed half-edge in a hash map.
2. Traces the outer loop by following the edge graph, preferring angular continuity at junctions.
3. Applies Ramer-Douglas-Peucker simplification (`_rdp`) with epsilon auto-computed as:

   ```python
   epsilon = max(1.0, sqrt(raw_point_count) × 0.42)
   ```

   If the raw trace had ≥ 700 points but simplified to ≤ 6 points (over-simplified), the epsilon is reduced to `max(0.8, epsilon × 0.72)` and simplification is retried.

   The epsilon may also be passed explicitly by the caller.

4. If the simplified polygon has fewer than 4 points, the raw trace is used as-is.

### 2.8 Confidence Scoring

Each candidate segment receives a confidence score [0.05, 0.99]:

```python
confidence = 0.9
confidence -= min(non_split_issue_count × 0.1, 0.45)
if fill_ratio < 0.55:
    confidence -= 0.12
if simplified_point_count > 14:
    confidence -= 0.1
confidence += min(agreement_score × 0.12, 0.12)
confidence = clamp(confidence, 0.05, 0.99)
```

This maps to a quality label:
- `"poor"`: has `tiny_region` or `too_complex` issue
- `"usable"`: has `touches_border` or `possible_merge`, or `confidence < 0.55`
- `"good"`: `confidence < 0.75`
- `"strong"`: otherwise

### 2.9 Post-processing

After all components are evaluated:

1. **Deduplication** — segments sorted by area descending; any candidate whose mask overlaps 80% of an already-kept segment (or 55% when centres are within 28 pixels) is dropped.
2. **Localized-bins deduplication** — localized-bins children are separately ranked by `(confidence, fill_ratio, compactness, area)` and capped at 4 per parent; siblings with > 35% mutual overlap are dropped.
3. **Count-deficit recovery** — if `expected_room_count` is set and the segment count is still below it, previously-deferred candidates are re-evaluated in `recovery_mode=True` (lower thresholds) and admitted if they pass. Recovered candidates receive the `recovered_count_deficit` issue tag.
4. **`max_segments` cap** — after sorting by area descending, any segment beyond `max_segments` is dropped.

### 2.10 `polygon_pct` vs `polygon_pixel`

`polygon_pixel` is the raw polygon in image pixel coordinates: `[[x0, y0], [x1, y1], ...]`.

`polygon_pct` is computed on the fly in `_handle_get_map_segments` each time segments are fetched:

```python
polygon_pct = [
    [round(x / image_width × 100, 4), round(y / image_height × 100, 4)]
    for x, y in polygon_pixel
]
```

This converts each vertex to percentage of image dimensions [0–100]. The card uses `polygon_pct` so overlays scale correctly regardless of the image's display size.

### 2.11 `image_runtime_capabilities`

`image_runtime_capabilities()` (in `mapping/segment_primitives.py`) probes whether each optional library is importable and returns a dict:

```python
{
    "numpy":           {"available": bool, "version": str|None, "error": str|None},
    "pillow":          {...},
    "scipy":           {...},
    "scipy_ndimage":   {...},
    "pipeline_ready":  bool,  # True if pillow + numpy + scipy.ndimage available
}
```

The pipeline depends only on Pillow + NumPy + SciPy; `pipeline_ready` is the single readiness gate. There is no OpenCV or scikit-image dependency.

---

## 3. Room Bounds from Traces

> **Removed (mapping split).** The learned per-room bounding-box store described
> below — `room_bounds.py` / `RoomBoundsStore`, the sample→bounds attribution, and
> the `get_room_bounds_snapshot` service — was **deleted**. It rode the device's
> vacuum-coordinate frame, which re-bases every session, so the cross-session bounds
> were a smear. Room tracking now reads the device's native current-room (§1). This
> section is retained as a historical / disaster-recovery reference; the code is gone.

### 3.1 What a "trace" is

A trace is a time-ordered list of vacuum position samples collected during a single cleaning job. Each sample is `(vx, vy)` in vacuum coordinate units. Samples are collected in `MappingTracker._handle_position_update` by reading the `robot_position_x` and `robot_position_y` HA sensor states.

Deduplication is applied at collection time: if the new `(vx, vy)` is identical to the most recently recorded position, it is discarded. This prevents the X and Y sensors firing separately on the same movement event from creating double entries.

Sampling pauses during mid-job dock returns (`pause_sampling` / `resume_sampling`) to prevent hundreds of identical dock-position samples from corrupting room bounds.

Samples are flushed to a temporary file (`_samples_active.json`) every 25 unique positions so that an HA restart mid-job can recover the partial run.

### 3.2 Attribution Strategy

At the end of a job, `RoomBoundsStore.update_room_bounds` attributes samples to rooms:

**Single-room job** (exactly one non-transition room in the job's room dict): all samples are attributed to that room unconditionally.

**Multi-room job**: for each sample `(vx, vy)`, the first room whose stored bounding box (expanded by `BOUNDS_MARGIN`) contains the point receives credit. Rooms with fewer than `MULTI_ROOM_MIN_RUNS = 4` active history entries are skipped as attribution anchors because their bounds are not yet reliable enough. Unattributed samples are discarded.

### 3.3 `BOUNDS_MARGIN = 50`

After attribution, the bounding box query in `_update_confidence` also uses the same margin:

```python
BOUNDS_MARGIN = 50.0  # vacuum units
```

This adds 50 vacuum units to each side of the stored bounding box when testing whether a position falls within a room. The margin exists to handle two situations:
- The robot may clean right up to the boundary of its known box, or slightly beyond it, as the room boundaries are learned incrementally.
- Coordinate jitter in the vacuum's reported position means exact bounding-box containment would miss valid cleaning positions near edges.

### 3.4 Percentile Trimming

Before samples are committed to history, `_percentile_trim` is applied:

```python
def _percentile_trim(samples, p_lo=0.10, p_hi=0.90):
    # Requires >= 10 samples (_TRIM_MIN_SAMPLES) to apply trimming.
    xs = sorted(vx for vx, _ in samples)
    ys = sorted(vy for _, vy in samples)
    n = len(xs)
    lo_i = int(n * 0.10)
    hi_i = min(int(n * 0.90), n - 1)
    x_lo, x_hi = xs[lo_i], xs[hi_i]
    y_lo, y_hi = ys[lo_i], ys[hi_i]
    return [(vx, vy) for vx, vy in samples if x_lo <= vx <= x_hi and y_lo <= vy <= y_hi]
```

The outermost 10% of both the X and the Y distributions are discarded (independently). A sample survives only if it is within both P10–P90 ranges. This eliminates:
- Dock-adjacent outlier coordinates that slip through the pause gate.
- Large coordinate excursions caused by the robot leaving a room briefly to navigate.
- Sensor glitch spikes that report a physically impossible position for one sample.

Below 10 samples, no trimming is applied because there is insufficient data to compute meaningful percentiles.

### 3.5 History Cap — 20 Entries

Each room's `job_bounds_history` is capped at 20 entries (newest first):

```python
history = [job_entry] + history
history = history[:20]
```

The newest entry becomes index 0. The oldest survives entry becomes index 19. This is the *baseline entry* and is protected from manual exclusion (see Section 7). Capping at 20 prevents unbounded file growth while retaining enough history for meaningful outlier detection.

### 3.6 Bounds Recomputation

After every history update, `_recompute_bounds_from_history` rebuilds the active bounding box:

```python
active = [e for e in history if not e.get("excluded", False)]
min_x = min(e["min_x"] for e in active)
max_x = max(e["max_x"] for e in active)
min_y = min(e["min_y"] for e in active)
max_y = max(e["max_y"] for e in active)
```

The resulting bounds is the *union* of all active (non-excluded) job entries. There is no decay or weighting — every active run contributes equally to the envelope. The centroid `cx, cy` is the midpoint of the union box. `run_count` is the number of active entries. `updated_at` is the `recorded_at` timestamp of the most recently added entry (index 0).

---

## 4. Coordinate System

### 4.1 Vacuum Coordinate Space

The vacuum reports its position as `(vx, vy)` values. These are in proprietary integer units originating from the robot's internal SLAM system. The scale is approximately 1 unit ≈ 1 mm for Eufy devices (not verified across all models). The origin and axis directions are robot-specific. On Eufy map_6 the Y axis increases upward in the robot's reference frame but this is not guaranteed by the protocol.

### 4.2 Pixel Coordinate Space

The map PNG uses the standard image convention: origin at the top-left, X increases rightward, Y increases downward.

### 4.3 No Cross-Space Transform

The two coordinate spaces are **not** related by any runtime transform. The legacy "System A" affine vacuum↔pixel transform (calibration pairs, `compute_affine_transform`, `vacuum_to_pixel`/`pixel_to_vacuum`, machine-corner clustering) has been removed.

Consequences for the rest of the system:

- Image-segment polygons stay in pixel space and are used only as UI map-card overlays; they are never projected into vacuum space.
- Room bounds (§3) operate purely in vacuum space — the accumulated bounding box learned from cleaning-run samples.
- The two are never mixed: without a pixel↔vacuum transform a live (vacuum-space) position cannot be tested against a pixel-space polygon.

---

## 5. Segment Adjustments

### 5.1 The Adjustment Record

Each map stores a `image_segment_adjustments` dict keyed by `segment_id`. Each entry holds:

```json
{
  "offset_x": int,
  "offset_y": int,
  "edge_left": int,
  "edge_right": int,
  "edge_top": int,
  "edge_bottom": int,
  "vertex_moves": [{"index": int, "delta_x": int, "delta_y": int}, ...]
}
```

All values are integers (pixel units). Missing keys are treated as 0.

### 5.2 The Adjustment Application — `_adjust_polygon_pixel`

When `get_map_segments` is called, `_apply_segment_adjustments` applies stored adjustments to each raw segment polygon. The transform proceeds in three layers applied cumulatively:

**Layer 1 — whole-shape translation:** every vertex is shifted by `(offset_x, offset_y)`.

**Layer 2 — edge nudges:** vertices that lie in the outermost 10% of the polygon's bounding box width or height receive an additional per-edge shift:

```python
band_x = max(2, int(round(width × 0.1)))
band_y = max(2, int(round(height × 0.1)))

if x <= (min_x + band_x):  x += edge_left
if x >= (max_x - band_x):  x += edge_right
if y <= (min_y + band_y):  y += edge_top
if y >= (max_y - band_y):  y += edge_bottom
```

This allows the left, right, top, or bottom edges of the polygon to be pushed independently without moving the whole shape.

**Layer 3 — vertex deltas:** each entry in `vertex_moves` moves the specific polygon vertex at `index` by `(delta_x, delta_y)`, applied after the previous two layers.

All three layers are additive and always applied together. There is no matrix composition — the output is a list of `[int, int]` pixel points.

### 5.3 Cumulative Adjustment Accumulation

The `adjust_map_segment` service call *accumulates* adjustments, it does not replace them:

```python
offset_x = current.get("offset_x", 0) + call_delta_x
offset_y = current.get("offset_y", 0) + call_delta_y
edge_left = current.get("edge_left", 0) + call_edge_left
# ... same for all edge fields
```

For `vertex_moves`, each `(index, delta_x, delta_y)` from the call is merged into the existing vertex table by index:

```python
new_delta_x = prev.get("delta_x", 0) + call.get("delta_x", 0)
new_delta_y = prev.get("delta_y", 0) + call.get("delta_y", 0)
```

If both deltas resolve to zero after merging, the vertex entry is removed. If all fields are zero after accumulation, the entire segment adjustment record is deleted. This means calling the service with negative deltas can undo a previous adjustment.

### 5.4 Issue Tags

When adjustments are applied, the following tags are added to the segment's `issues` list:
- `translated_manual` — any adjustment was applied (always set when record is non-zero)
- `edge_adjusted_manual` — at least one edge field is non-zero
- `vertex_adjusted_manual` — at least one `vertex_moves` entry exists

The `translation_offset`, `edge_adjustment`, and `vertex_adjustment` fields are also set on the returned segment for diagnostic display.

---

## 6. Map Image Variants

The `upload_map_image` service validates the `variant` field through the `_image_variant` validator (default `default`): it accepts the four fixed keys `default | dark | light | custom` **plus** any per-layout key matching `custom_*` (one backdrop per named custom layout, see §10). An unrecognised value raises `vol.Invalid`.

| Variant key | Role | Used for |
|------------|------|---------|
| `"default"` | `"primary"` | General display, fallback for analysis |
| `"dark"` | `"segmentation"` | Primary input for image segment analysis; dark theme captures have better colour contrast between rooms |
| `"light"` | `"boundary"` | Assist input for wall cutting; light theme captures have near-white walls that are easy to detect |
| `"custom"` | `"manual"` | Legacy single-custom backdrop and the default backdrop for a migrated `"Custom"` layout (§10). Stored and served like any other variant, but the segmenter **never** reads it — `_handle_analyze_map_image` only probes `dark`/`default` (primary) and `light` (assist), so a custom-only map is never auto-segmented. |
| `"custom_<layout_id>"` | `"manual"` | Per-layout backdrop for a named custom layout (§10). Written when `upload_map_image` is called with a `layout_id` — the server forces the variant key to `custom_<layout_id>` and repoints that layout's `backdrop_variant`. Like `"custom"`, never auto-segmented. Its recorded `image_width`/`image_height` define the pixel space `set_custom_segments` rasterises that layout's authored polygons against. |
| `"custom_<id>_home_art"` / `"custom_<id>_room_<rid>"` | `"manual"` | **Furnished-art** variant for a live-map layout — a to-scale home render composited *over* the live map (whole-home, or per-room). Written when `upload_map_image` is called with `art_scope` (`home`/`room`); points the layout's `home_art.art_variant` / `rooms[<rid>].art_variant`, **not** its `backdrop_variant`. Display-only (never segmented). See the [furnished render reference](../advanced/08-map-configuration.md#furnished-render). |

Variant names are normalised to lowercase, spaces and hyphens replaced by underscores.

**Variant priority depends on the segmentation mode and active layout.** In `cv` mode the active backdrop and analysis inputs prioritise `dark → default` for the primary and `light` for the assist; the custom backdrops are ignored. In `custom` mode (§10), `_handle_get_map_segments` resolves the active layout's `backdrop_variant` (a `custom_<layout_id>` key, or the shared `custom` key for a migrated layout) as the active backdrop, falling back to `dark → default → light` only if no such image is recorded. The segmenter reads `dark`/`default`/`light` exclusively and never reads any `custom*` variant in either mode.

### 6.1 Storage Paths

Images are stored in two locations (written identically):

- **Filesystem (config dir):** `<config_dir>/eufy_vacuum/mapping/<vacuum_slug>/map_<map_id>[_<variant>].png`
- **Browser-served (www root):** `<config_dir>/eufy_vacuum/maps/<vacuum_slug>/map_<map_id>[_<variant>].png`

The `_<variant>` suffix is omitted when `variant == "primary"` or `variant == "default"`. For dark: `map_6_dark.png`. For light: `map_6_light.png`. For default/primary: `map_6.png`.

The browser URL is: `/eufy_vacuum/maps/<vacuum_slug>/map_<map_id>[_<variant>].png`

Additionally, image metadata (width, height, path, browser_url) is recorded in the map's `image_variants` dict inside `map_<map_id>.json`. The `image_segment_adjustments` and `image_segments` results are stored separately in the runtime HA `.storage` Store (the map bucket), not in `map_<map_id>.json` — see §9.1.

---

## 7. Excluded History Entries

Each job entry in a room's `job_bounds_history` carries an `excluded` boolean. `_recompute_bounds_from_history` (§3.6) unions only the **non-excluded** entries, so a flagged run is dropped from the accumulated box while its samples stay in history.

The interactive **bounds-review** surface that set this flag was **retired with the mapping split**: the card's Mapping Bounds Review panel, its `clear_room_bounds` / `exclude_room_job_bounds` / `restore_room_job_bounds` / `rebuild_room_bounds_from_archive` services, and the `boundary.py` transition-candidate scoring that flagged L-shaped / corridor rooms are all gone. The recompute still honors the flag, so entries already excluded on disk stay excluded, but there is no longer a runtime path to toggle it. The retired review design lives in git history.

---

## 8. File Layout

All per-vacuum files live under `<config_dir>/eufy_vacuum/mapping/<vacuum_slug>/`.

### 8.1 Map State File

```
map_<map_id>.json
```

One JSON file per (vacuum, map). Contains:

- `rooms` — per-room dict keyed by `room_id` string. Each room entry holds:
  - `bounds` — the active bounding box: `{min_x, max_x, min_y, max_y, cx, cy, run_count, sample_count, updated_at}`
  - `job_bounds_history` — list of up to 20 job entries, newest first (each carries an `excluded` flag; see §7)
- `image_path`, `image_width`, `image_height` — legacy fields, now duplicated in `image_variants`
- `image_variants` — dict of variant metadata records
- `package` — the richer mapping package (see below)

The same per-map bucket also carries the CV/Custom toggle state, the named custom-layout collection, and its UI overlays (see §10 for the full treatment):

- `segmentation_mode` — `"cv"` or `"custom"`. Defaults to `"cv"` when absent. Selects which segment store `get_map_segments` serves; flipping it never re-runs the segmenter. In `custom` mode it serves the **active** layout.
- `image_segments` — the CV base `SegmentationResult` cache (engine-derived). Special at the map-bucket level — there is exactly one.
- `custom_layouts` — `{layout_id: layout}` dict of named custom layouts. Each layout is `{id, name, backdrop_variant, backdrop_source, custom_segments, segment_room_links, companion_anchors, render_mode, home_art, rooms, created_at, updated_at}` — its own backdrop, authored segments, room links, companion anchors, and (on a live-map layout) the furnished-render state `render_mode`/`home_art`/`rooms` (see §10.1 and the [data model](03-data-model.md)).
- `active_custom_layout_id` — id of the layout served in `custom` mode (or `null`).
- `custom_segments` — **legacy** single user-authored store, in the same `SegmentationResult` shape as `image_segments`. Migrated lazily and non-destructively into a `"Custom"` layout under `custom_layouts` (§10.2); kept, never deleted.
- `segment_room_links` — `{segment_id: room_id}` user-assigned 1:1 segment→room mapping. At the map-bucket level this is **CV's** link store; each custom layout owns its own `segment_room_links`.
- `companion_anchors` — `{room_id | "dock": {pct_x, pct_y}}` anchor positions (0–100% of image, from top-left) for the animated companion sprite, including the reserved `"dock"` mascot spot (not a room). At the map-bucket level this is **CV's** anchor store; each custom layout owns its own `companion_anchors`.

### 8.2 Mapping Package

Embedded in `map_<map_id>.json` under the `"package"` key:

- `room_definitions` — dict keyed by `room_id`. Each definition has labels, slugs, segment link (`suggestion_segment_id`), anchor pixel/vacuum, zone tags, adjacency, etc.
- `segment_adjustments` — per-segment `offset_x`, `offset_y`, edge deltas, vertex moves
- `dock` — pixel/vacuum anchor for the dock, exclusion radius
- `trace_evidence` — up to 100 user-annotated evidence records
- `images` — variant metadata records (merged with `image_variants`)

Note that `segment_room_links` and `companion_anchors` are **not** part of this package JSON. They are runtime-bucket overlays held on the `.storage` map bucket (§8.1, §9.1) and enriched onto each segment at read time by `_build_segments_response` / `_handle_get_map_segments` — the canonical `image_segments` / per-layout `custom_segments` caches are never mutated by them. In `cv` mode the links/anchors come from the **map-bucket** dicts; in `custom` mode they come from the **active layout's** dicts (§10.2). `companion_anchors` may additionally hold the reserved `"dock"` key (the docked-home sprite spot), which is not a room.

### 8.3 Raw Samples Archive (per room)

```
raw_samples_room_<room_id>[_<slug>].jsonl
```

One JSONL file per room. The first line is a metadata header (`"_meta"` key). Each subsequent line is one job entry:

```json
{"job_id": "job_2026-01-15T09-30", "map_id": "6", "room_id": "3",
 "recorded_at": "2026-01-15T09:30:00Z", "room_name": "Kitchen",
 "samples": [[vx, vy], ...], "excluded": false}
```

The file is capped at `RAW_SAMPLES_MAX_LINES = 1000` job lines (excluding the header). Rolling falloff starts from index 2, preserving the header (index 0) and the baseline job entry (index 1, oldest).

File discovery is slug-aware: `_find_raw_samples_path` globs `raw_samples_room_<room_id>*.jsonl` so that renaming a room (changing its slug) does not orphan the archive.

### 8.4 Active Samples Temp File (in-flight)

```
_samples_active.json
```

Written (via atomic rename of `.tmp`) every `SAMPLES_FLUSH_INTERVAL = 25` unique position samples during an active job. Contains `map_id`, `rooms`, and the full `samples` list. Deleted at the start of the next job or after a clean `end_job`. If HA restarts mid-job and a temp file with a matching `map_id` is found on `start_job`, the samples are recovered.

---

## 9. Porting Considerations

### 9.1 Eufy-Specific

The following are specific to Eufy's implementation:

- **Vacuum coordinate units** — Eufy reports `robot_position_x` / `robot_position_y` as integer sensor states in its proprietary unit. The scale (≈ 1 mm/unit) is inferred and not guaranteed.
- **Map image format** — Eufy's map images use a consistent hue-per-room convention. The dark variant provides saturated, high-contrast room colours; the light variant provides near-white walls. Both properties are assumed by the HSV thresholding approach.
- **HA entity model** — `MappingTracker` listens to Home Assistant state change events for position sensors and fires the `eufy_vacuum_room_completed` HA bus event. This is an HA-specific pattern.
- **HA storage** — `RoomBoundsStore._save_map_data` / `_load_map_data` writes directly to JSON files on the config dir filesystem. The `image_segment_adjustments` and `image_segments` results live in the runtime HA storage manager (`.storage` files), not in the mapping JSON files.

### 9.2 Generic / Portable

The following components have no Eufy-specific dependencies and would port directly to another robot or framework:

- **`mapping/segment_primitives.py`** — brand-agnostic geometry/image primitives (polygon math, mask ops, HSV helpers). Pure Python; only dependencies Pillow, NumPy, SciPy.
- **`rasterize_primitives`** (in `mapping/segment_primitives.py`) — the no-CV counterpart to the segmentor. Takes an ordered list of pct-space primitives (`rect`/`circle`/`polygon`, each optionally `op: subtract`; default unions), draws them onto a PIL `"1"` mask, traces the boundary with the *same* `mask_to_polygon` the CV pipeline uses, and scales the result to the map's pixel dimensions. Inputs are plain dicts with 0–100 coordinates; output is a pixel-space polygon. Dependencies: Pillow (`Image`/`ImageDraw`) + NumPy only (no SciPy). This is the portable core of the custom-segment writer (§10).
- **`adapters/eufy/segmentor.py`** — the Eufy HSV segmentation pipeline built on those primitives. Inputs: a PNG file path. Outputs: a pure-Python dict. A new brand provides its own segmentor module and registers it as a segmenter engine (`mapping/segmenter_engines.py`) — see the brand-agnostic adapter docs.
- **`boundary.py`** — `point_in_polygon` (ray casting), the one geometry helper the live map layer still needs (used by `map_source.zone_membership`). The rest of the module — Douglas-Peucker simplification, corner detection, transition-candidate scoring, shoelace area, convex hull — was removed with the mapping split.
- **`_percentile_trim`** in `room_bounds.py` — pure Python outlier trimming.
- **`_recompute_bounds_from_history`** — pure Python union of history entries.

The `BOUNDS_MARGIN` value (50 vacuum units) and percentile parameters (P10/P90) are tuning constants that will need adjustment if the coordinate scale differs from Eufy's.

---

## 10. Custom Segments, Named Layouts & the CV/Custom Toggle

The image segment pipeline (§2) is a CV pipeline: it derives room polygons from pixel data. For maps where that derivation is unreliable — or where the user would rather author rooms from primitive shapes than tune the segmenter — the system offers a parallel **custom** path. CV and custom segments coexist on the same map, both wearing the identical segment shape so room-linking, adjustments, and dispatch treat them uniformly.

The custom side is no longer a single store. A map now holds a **named collection of custom layouts** — e.g. a "solar system" image and a "tree" image, each its own backdrop, authored segments, room links, and mascot anchors. `segmentation_mode` still chooses CV vs custom; in custom mode the **active layout** is served. CV stays special at the map-bucket level (one `image_segments` cache plus the map-bucket `segment_room_links`/`companion_anchors`); custom layouts sit *alongside* CV, never as "layout 0".

### 10.1 CV at the bucket, custom layouts alongside

Each map bucket holds:

- `image_segments` — the **CV base**, produced by whichever `MapSegmenter` engine the adapter selected (§2). Purely engine-derived; exactly one. Re-running CV (`analyze_map_image` with `force_reanalyze`) re-segments and forces a relink.
- `custom_layouts` — `{layout_id: layout}`, a dict of **named custom layouts**. Each layout owns *everything* per-layout:
  - `id`, `name`, `created_at`, `updated_at`
  - `backdrop_variant` — its own backdrop image key (`custom_<layout_id>`, or `custom` for a migrated layout)
  - `custom_segments` — the user-authored set for *this* layout (same `SegmentationResult` shape as `image_segments`)
  - `segment_room_links` — `{segment_id: room_id}` for *this* layout. Because links are per-layout, two layouts can each have a segment id `living` linked to **different** rooms — impossible under the old single-store model.
  - `companion_anchors` — `{room_id | "dock": {pct_x, pct_y}}` for *this* layout, including the reserved `"dock"` mascot spot.
- `active_custom_layout_id` — the layout served in custom mode (or `null`).

`segmentation_mode` (`"cv"` | `"custom"`, default `"cv"`) selects which segment store `get_map_segments` serves; in `custom` mode it serves the **active** layout. **All stores persist independently** — toggling the mode (or switching layouts) is a pointer change, not a regeneration. Flipping `cv → custom → cv` returns each segment set untouched, with zero re-analysis. `_handle_get_map_segments` echoes `segmentation_mode`, `active_custom_layout_id`, the `custom_layouts` summary, and the active `segment_room_links` so the card knows exactly which store it is rendering. Beyond those, the response also carries `saved_zones`, `companion_anchors`, `hidden_regions` (map-level physical masks), `area_label_anchors` (map-level device-room label positions), `image_variants`, and `adjustments`. The per-layout `custom_layouts` summary now includes `backdrop_source` alongside `backdrop_variant`, plus the furnished-render keys `render_mode`, `home_art`, and `rooms` (Wave 0 furnished custom render).

### 10.2 The active-scope seam and legacy migration

Every read/write handler resolves the live stores through a single seam, `_resolve_active_scope(map_bucket)`, which returns `{mode, layout_id, segments_store, links, anchors, backdrop_variant}`:

- **CV branch** (`mode == "cv"`) → the map-bucket keys: `image_segments`, and the map-bucket `segment_room_links` / `companion_anchors` (created via `setdefault`, so the returned dicts are the real mutable stores).
- **Custom branch** (`mode == "custom"`) → the active layout's `custom_segments` / `segment_room_links` / `companion_anchors` and its `backdrop_variant`. When no layout resolves, empty read-only stores are returned.

`get_map_segments` reads through the resolved `segments_store`/`links`/`anchors`/`backdrop_variant`; `set_segment_room_link` and `set_companion_anchor` mutate the resolved `links`/`anchors` (so the existing 1:1-enforcement and 0–100 clamp logic is unchanged, now per-active-store); `set_custom_segments` targets the active layout (auto-creating a default first — §10.5).

Supporting helpers:

- `_migrate_custom_layouts(map_bucket)` — **lazy + non-destructive**. Returns immediately once `custom_layouts` exists. Otherwise it creates an empty `custom_layouts` (and `active_custom_layout_id`); if a legacy single `custom_segments` store with segments is present it folds **a copy** of it into a default layout named `"Custom"` (backdrop `custom`), copying only the `segment_room_links` whose segment ids resolve against the legacy store and the `companion_anchors` for the `"dock"` key plus those linked rooms — leaving CV's map-bucket dicts intact. The legacy `custom_segments` key is **kept, never deleted**, so the migration is idempotent. Every handler calls this before resolving scope.
- `_active_custom_layout(map_bucket)` — the active layout dict, or `None`.
- `_create_layout(map_bucket, name, *, backdrop_variant=None, activate=True)` — mints a layout with empty stores and a `custom_<layout_id>` backdrop variant (unless one is supplied), and activates it by default.
- `_ensure_default_layout(map_bucket, *, backdrop_variant="custom", name="Custom")` — returns the active layout, creating + activating one when none exists (keeps authoring valid with zero layouts; backward-compat with the pre-layout flow, whose backdrop sits at the shared `custom` variant).

### 10.3 Per-layout backdrop variant

Each custom layout needs its own backdrop image because the CV variants may not exist (or may be unsuitable) for a manually-authored map. `upload_map_image` (§6) gains an optional `layout_id`:

- When `layout_id` is supplied, the server **forces** the variant to `custom_<layout_id>` (ignoring any `variant` field), validates that the layout exists (`{"saved": false, "reason": "layout_not_found"}` otherwise), writes the PNG, and repoints that layout's `backdrop_variant` to the new key (touching its `updated_at`).
- The custom backdrops are **never auto-segmented**: `_handle_analyze_map_image` only probes `dark`/`default` (primary) and `light` (assist), so uploading any `custom*` image does not trigger the segmenter.
- The active layout's backdrop `image_width`/`image_height` are the **rasterise canvas** — the pixel space `set_custom_segments` scales that layout's authored polygons into. `set_custom_segments` refuses to run (`{"saved": false, "reason": "no_custom_backdrop"}`) only when the active layout's backdrop variant has no known dimensions **and** the call sent no `backdrop_width`/`backdrop_height` fallback (a live-image-backed layout supplies those dims instead — see §10.4).
- The card renders the custom backdrop with `object-fit: fill` (the `evcc-map-image--fill` modifier) so authored percentage coordinates map 1:1 to the displayed frame, whereas CV-mode backdrops render `object-fit: contain`.

### 10.4 `set_custom_segments` — replace-all authoring (active layout)

`set_custom_segments(vacuum_entity_id, map_id, segments, backdrop_width?, backdrop_height?)` rebuilds the **active layout's** `custom_segments` store from scratch each call (replace-all), after `_ensure_default_layout` guarantees an active layout exists. The `segments` field is a list of segment dicts; extra keys are allowed (`extra=vol.ALLOW_EXTRA`):

```json
{
  "segments": [
    {
      "id": "custom_1",
      "primitives": [
        {"type": "rect",    "x": 10, "y": 20, "w": 30, "h": 25},
        {"type": "circle",  "cx": 60, "cy": 40, "r": 12},
        {"type": "polygon", "points": [[5, 5], [40, 5], [22, 38]]},
        {"type": "rect",    "x": 15, "y": 25, "w": 8, "h": 8, "op": "subtract"}
      ]
    }
  ]
}
```

Each primitive is `{type: rect|circle|polygon, op?: subtract, ...geom}` with all geometry in **0–100% of the map**. `id` is optional; when omitted the server assigns `custom_<N>`. Preserving a stable `id` across re-saves keeps that layout's `segment_room_links` (§5/§10.7) attached.

Server-side, each segment's primitive list is rasterised by `segment_primitives.rasterize_primitives` (run in the executor, since `mask_to_polygon` is blocking):

1. A PIL `"1"` (1-bit) mask is created at a working resolution (512 px square).
2. Primitives are drawn **in order**: `op: subtract` clears (`fill=0`), anything else unions (`fill=1`). Order matters — a later subtract carves out earlier fills.
3. The mask's outer boundary is traced by `mask_to_polygon` — the **same function the CV pipeline uses** (§2.7) — then scaled to the active layout's backdrop pixel dimensions, yielding a `polygon_pixel` list.

A **live-image-backed layout has no uploaded backdrop**, so the card sends the optional `backdrop_width` / `backdrop_height` (coerced to `int` via `SET_CUSTOM_SEGMENTS_SCHEMA`) as the rasterise canvas — the rendered live image's natural pixel size; when they are used the handler sets that layout's image variant to `"live"`. The `no_custom_backdrop` refusal (`{"saved": false, "reason": "no_custom_backdrop"}`) is returned only when **neither** an uploaded backdrop variant with known dimensions **nor** the sent `backdrop_width`/`backdrop_height` are available.

Degenerate results (nothing drawn, or no traceable boundary) are **dropped** and counted in the response's `skipped` field. Each surviving polygon is wrapped by `_build_custom_segment` into the CV segment shape (`source: "custom"`, `quality: "custom"`, `confidence: 1.0`, `structural_role: "room"`, etc.).

Modelling guidance:

- **One segment = one room.** A segment with a single primitive is one simple room.
- **Multiple primitives in one segment = a merged room** — they union into a single polygon (e.g. an L-shaped room built from two rects).
- **`op: subtract` carves.** A subtract along an edge produces a concave-but-simple polygon. An interior hole **cannot** be represented — `mask_to_polygon` traces a single outer loop, so a fully-enclosed cutout is not held by one polygon.

### 10.5 Layout CRUD services

Four services manage the named-layout collection. All are `supports_response=True` and route through `_migrate_custom_layouts` before mutating:

| Service | Effect | Returns |
|---------|--------|---------|
| `create_custom_layout(name?, backdrop_source?)` | Mint + activate a new layout (empty stores, per-layout `custom_<id>` backdrop variant) via `_create_layout`, then flip `segmentation_mode` to `custom`. `name` defaults to `"Custom"`. The optional `backdrop_source` (`CREATE_CUSTOM_LAYOUT_SCHEMA`, `vol.Optional("backdrop_source"): cv.string`) pins the backdrop: `"live"` composes the rooms straight over the brand's live-map image instead of an uploaded `custom_<id>` backdrop variant (surfaced in the `get_map_segments` layout summary). | `{saved, layout_id, layout}` |
| `rename_custom_layout(layout_id, name)` | Rename an existing layout (touches `updated_at`). | `{saved, layout_id, layout}` or `{saved: false, reason: "layout_not_found"\|"missing_name"}` |
| `delete_custom_layout(layout_id)` | Delete a layout and best-effort remove its backdrop image/variant. If the **active** layout is deleted, reassign active to the first remaining layout (ordered by name); if **none** remain, set `active_custom_layout_id = null` and flip `segmentation_mode` back to `cv`. | `{saved, deleted, layout_id, active_custom_layout_id, segmentation_mode}` |
| `set_active_custom_layout(layout_id?)` | Activate a layout and flip to `custom` mode. A **null or unknown** `layout_id` auto-creates + activates a default layout (via `_create_layout`), so custom mode always resolves a live store. | `{saved, active_custom_layout_id, mode}` |

The legacy single-store services keep working through the seam: `set_custom_segments` targets the active layout (auto-creating a default first), and `set_segment_room_link` / `set_companion_anchor` write to whichever `links` / `anchors` store `_resolve_active_scope` selects (CV's map-bucket dicts in `cv` mode, the active layout's in `custom` mode).

### 10.6 `set_segmentation_mode` — the toggle

`set_segmentation_mode(vacuum_entity_id, map_id, mode)` with `mode` ∈ `{cv, custom}` writes the `segmentation_mode` flag.

> **Invariant:** the handler only flips the flag. It **never** re-runs the segmenter, in either direction. `image_segments` and every layout's `custom_segments` are left exactly as they were, so the toggle is reversible with no data loss. (`_handle_set_segmentation_mode` documents this invariant inline.)

When flipping to `custom` with no active layout but layouts present, the handler soft-selects the first layout (sorted by id) so the view always resolves a store; a hard auto-create only happens in the CRUD handlers (§10.5). The response returns the new `mode` and the `segment_count` of whichever store `_resolve_active_scope` now selects.

### 10.7 New per-map bucket keys

The custom path adds these keys to the per-map `.storage` bucket (alongside `image_segments`, `image_segment_adjustments`, `image_variants` — see §8.1):

| Key | Shape | Purpose |
|-----|-------|---------|
| `segmentation_mode` | `"cv"` \| `"custom"` (default `"cv"`) | Selects CV vs custom; in `custom` mode `get_map_segments` serves the active layout |
| `custom_layouts` | `{layout_id: {id, name, backdrop_variant, custom_segments, segment_room_links, companion_anchors, created_at, updated_at}}` | The named custom-layout collection (each layout owns its own backdrop, segments, links, anchors) |
| `active_custom_layout_id` | `str \| null` | Id of the layout served in `custom` mode |
| `custom_segments` | `SegmentationResult` dict (same shape as `image_segments`) | **Legacy** single store; migrated lazily/non-destructively into a `"Custom"` layout, then kept untouched |
| `segment_room_links` | `{segment_id: room_id}` | **CV's** 1:1 segment→room assignment (each layout has its own copy) |
| `companion_anchors` | `{room_id \| "dock": {pct_x, pct_y}}` | **CV's** companion-sprite anchors (0–100% from top-left; reserved `"dock"` mascot spot; each layout has its own copy) |

`polygon_pct`, the enriched `room_id`, and applied adjustments are all derived at read time in `_handle_get_map_segments`, not stored on the cached segments.

### 10.8 Card composer (scope)

In `custom` mode the rooms-panel map toolbar exposes a shape composer (`src/state/map.js`, `src/renderers/map.js`, `src/bindings/map.js`). It edits an in-memory list of authored shapes and serialises them to `set_custom_segments` on save. Each shape is `{id, type, ...geom, group?, op?, room_id?, angle?}`, where `group` defaults to the shape's own `id` (so each shape is its own segment/room by default).

The composer is scoped to the **active layout**: `setMapSegmentsData` resets the draft (`_composeDraft` and friends) whenever the map id **or** `active_custom_layout_id` changes, and the reload guard `_composeLoadedFor` is keyed on `${map_id}:${active_custom_layout_id}` (via `_composeKey`), so switching layouts reloads that layout's saved shapes and mascot anchors.

Composer operations:

| Operation | Effect |
|-----------|--------|
| add rect / circle | Append a new shape (default `angle: 0`) |
| select | Pick a shape (or its merged group) for the next operation |
| move | Translate; *Room* (whole group, the default) or *Piece* (single member) scope when merged |
| tap-to-place | Drop the selected shape at a tapped point |
| scale | Resize about the shape centre |
| resize (W/H) | Adjust width/height — **rect only** |
| rotate (±15°) | Rects carry an `angle` applied at render and baked to a polygon on save; polygons rotate their points directly; circles are a no-op |
| merge | Two-tap two shapes into a shared `group` → ONE segment (group-coloured) |
| cut | Mark a grouped shape `op: subtract` so it carves the room (rendered dashed/red) |
| split | Drop a member out of its group back to its own segment |
| link-to-room | Assign a managed room to a whole merged group (enforced 1:1) |
| save | Replace-all `set_custom_segments`, then reconcile per-**segment** room links |
| re-edit | Reload saved polygons back into the composer once per map |

On save, `composeToSegments` buckets shapes by `group` (default = each shape's own `id`), orders `op: subtract` members **last** within each group (so cuts apply after fills, matching the server's in-order rasterise), and carries the per-segment `room_id` (whichever group-mate holds it, since the link is 1:1 per group).

#### 10.8.1 Layout picker

The old binary CV/Custom toggle is now a **picker** rendered by `_renderSegmentationToggle` (`src/renderers/map.js`):

- An **"Auto (CV)"** chip (`data-action="set-segmentation-mode"`, `data-mode="cv"`), always present.
- One chip **per named layout** (`data-action="set-active-custom-layout"`, `data-layout-id=...`), the active one highlighted; switching a chip swaps the whole layout (backdrop + authored rooms + links + mascot home).
- A **"＋ New"** chip (`data-action="open-new-layout"`) that opens the inline name editor.
- When a layout is active, **Rename** / **Delete layout** buttons plus an inline name-editor `<input>` (a single editor slice shared by create and rename).

The picker reads card state added in `src/state/map.js` — `customLayouts()`, `activeCustomLayoutId()`, `activeCustomLayout()`, and the layout-editor slice (`isLayoutEditorOpen` / `layoutEditorMode` / `layoutDraftName` / `setLayoutDraftName` / `openNewLayoutEditor` / `openRenameLayoutEditor` / `closeLayoutEditor`). The bindings (`src/bindings/map.js`) call the matching actions in `src/actions/map.js` — `createCustomLayout` / `renameCustomLayout` / `deleteCustomLayout` / `setActiveCustomLayout` — and a custom backdrop upload passes `layout_id` (the active layout id) to `uploadMapImage` so the server forces the `custom_<layout_id>` variant.

#### 10.8.2 Companion dock spot and toolbar toggles

Two adjacent toolbar concerns share the same map view:

- **Mascot dock spot.** When the vacuum is `docked` or `idle`, the companion sprite homes to the reserved `"dock"` key in `companion_anchors` — a single map-level spot, *not* a room. Dragging the mascot while docked writes that `"dock"` anchor (the same drag that, mid-clean, writes a per-room anchor). Until the dock spot is set, the mascot falls back to the resolved dock segment's centroid.
- **Mascot on/off.** Card state `mapAnimalEnabled` (localStorage `evcc_animal_on_<vac>`, default on) is **separate** from animal *selection*. A paw button in the rooms-panel map toolbar toggles it; `_renderMapAnimal` returns `''` when off.
- **Floor-texture on/off (split).** Two independent card-state toggles: `mapFloorTextureEnabled` (localStorage `evcc_floor_tex_map_<vac>`) gates the map texture polygons (`_renderFloorTexturePolygon` / `_buildFloorTextureDefs`); `roomFloorTextureEnabled` (`evcc_floor_tex_rooms_<vac>`) gates the room-card texture layers (`_renderFloorTextureLayer`). Both default on and seed from the legacy unified `evcc_floor_tex_<vac>` key on first read. Two hatch buttons toggle them (`map-texture-toggle` / `room-texture-toggle`); the map one is map-view-only, the room-card one stays in the toggle row for list view.

---

## 11. Provider Map Source (`map_state_source`)

The two subsystems above derive room geometry locally — image analysis from pixels (§2), trace bounds from cleaning runs (§3). The **provider map source** is a third reader that instead normalises the room layout the device's *own* firmware already knows. Where image/trace are best-effort inferences, this reads the provider's authoritative segmentation directly, so room tap-regions, current-room, and anchors are *auto-derived* rather than hand-composed or learned from drifting samples.

This section is an orientation only; the full design — wave scope, both brand backends, the normalisation transform, and overlay-layer details — lives in the authoritative design reference [`dev/map-state-source.md`](map-state-source.md).

### 11.1 Modules

| Module | Role |
|--------|------|
| `mapping/map_source.py` | Brand-agnostic, **HA-free pure** core. Turns the device's segmentation (raster + anchors) into normalised room data (per-room bbox + name + dock/robot anchors), in 0–1 of the *rendered* image (top-left origin, Y-flip applied) — the same space the card draws zones/labels in. Unit-testable without Home Assistant. |
| `mapping/map_source_runtime.py` | The HA-aware runtime **locators** that find the provider's data and hand plain dicts to the pure core. Eufy uses the **storage backend** (reads eufy-clean's `.storage/robovac_mqtt.<serial>` Store); Roborock uses the **memory backend** (a defensive introspector over the in-memory parsed `MapData` on the map image entity). Both apply the live-map presence gate and degrade to an absent marker — never raise. |
| `mapping/map_source_coordinator.py` | `MapSourceCoordinator` — the async backend dispatcher (bundled-subsystem pattern, constructed with the core manager; extracted from `core/manager.py`, which keeps one-line delegators). |

### 11.2 Coordinator surface

`MapSourceCoordinator` exposes four public async readers, dispatched by the adapter's declared `map_state_source` backend/format:

- `async_refresh_map_state_source(...)` — pre-warm dispatcher; reads the adapter's `map_state_source` block, applies the presence gate, and writes the normalised result into `manager._map_state_source_cache` so the sync on-loop dashboard snapshot can include it without doing the blocking `.storage` read itself.
- `async_get_map_live_pose(...)` — lightweight live-pose poll.
- `async_compare_map_sources(...)` — in-memory-vs-storage verify probe.
- `async_get_map_render_data(...)` — the card's own-render raster fetch.

Two seams deliberately stay on the manager: `_map_state_source_cache` (the pre-warm writes it; the on-loop snapshot composer and the map-overlays sensor read it directly) and `_resolve_live_map_image_entity` (shared with the dashboard snapshot composer as the live-map presence gate).

### 11.3 Relationship to §2/§3

This reader does **not** replace image analysis or trace bounds — they remain the path for maps where no provider segmentation is available, and the local subsystems own the CV/custom authoring and presence-detection machinery. The provider map source is consumed by the live-map overlay path: because it normalises into the rendered-image (0–1) space the card already draws in, its bboxes/anchors overlay the device-rendered backdrop directly rather than needing the (removed) pixel↔vacuum transform (§4).
