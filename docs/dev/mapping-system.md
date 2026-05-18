# Mapping System — Developer Reference

This document covers the complete mapping subsystem: image segment analysis, trace capture, room bounds learning, the affine coordinate transform, segment adjustments, and all on-disk storage. It is intended to expose the full algorithms and mathematics so a developer can understand, modify, or port the system.

---

## 1. Overview

The mapping system has two independent subsystems that address different aspects of knowing where rooms are.

**Image segment analysis** answers: *given map data, what regions probably correspond to rooms?* The answer mechanism varies by vendor — Eufy ships flat PNGs that need computer-vision analysis, Roborock streams structured polygons over the wire, and some brands provide no map data at all. To stay brand-agnostic the framework routes this through a **pluggable segmenter engine** (`mapping/segmenter_engines.py`). Each adapter selects an engine by name; the engine's `segment_map_image(...)` method produces a canonical `SegmentationResult` regardless of how it was derived. Polygons in pixel space, labelled with quality signals, get used as room shape overlays in the card and can feed the coordinate transform pipeline.

**Trace-based room bounds** (`manager.py`, `tracker.py`) answers: *given that the robot just cleaned, what bounding box best describes each room in vacuum coordinate space?* This subsystem learns incrementally from actual cleaning runs. Each run appends a new job entry to the room's history; bounds are always the union of all non-excluded history entries. The result is an axis-aligned bounding box in vacuum units, used for real-time room presence detection. This subsystem is **brand-agnostic by construction** — it reads vacuum-space position samples that exist in the same coordinate frame regardless of vendor.

The bridge between the two subsystems is the **room ID**. The trace tracker knows which room it's in by point-in-bounds checks; the image segmenter produces polygons that get linked to room IDs via the `segment_room_links` overlay. The two never share a coordinate space — they share an identifier. If the image segmenter fails, breaks, or doesn't exist for a particular adapter, the trace tracker keeps working off vacuum-space coordinates and the core integration (queue, job lifecycle, room presence) is unaffected. See §2.0 for the engine seam contract.

The two subsystems are related in two ways:
- An image segment's pixel polygon can be mapped to vacuum space via the affine transform, giving a rough vacuum polygon. That polygon drives the `BOUNDARY_CROSSING` signal in trace segmentation and the room-entry gating on boundary traces.
- The trace-based bounds and the image-segment polygon serve complementary purposes: the image segment gives shape; the trace bounds give a reliable presence envelope.

---

## 2. Image Segment Analysis Pipeline

### 2.0 The segmenter engine seam

`mapping/segmenter_engines.py` defines the pluggable interface. Three pieces:

**`MapSegmenter` Protocol** — what every engine implements:

```python
class MapSegmenter(Protocol):
    engine_name: str                                          # registry key

    def validate_tuning(self, tuning: dict) -> list[str]:     # validation hook
        ...

    def segment_map_image(
        self, *,
        image_path: str | None,                               # optional — None for engines that read wire data
        tuning: dict[str, Any],                               # from adapter_config.mapping.segmenter_tuning
        context: dict[str, Any] | None = None,                # optional engine-specific input
    ) -> SegmentationResult:
        ...
```

**`SegmentationResult`** TypedDict — the canonical output every engine produces:

```python
{
    "available":   bool,                  # False = engine couldn't run
    "reason":      str,                   # "ready" | "pipeline_unavailable" | "noop" | ...
    "message":     str,
    "engine":      str,                   # engine_name that produced this result
    "image":       {"width", "height"} | None,
    "segments":    [EnrichedSegment, ...],
    "summary":     {"segment_count", "quality_counts", "good_or_better_count"},
    "engine_diagnostics": dict,           # free-form, engine-specific (optional)
}
```

Renderers and room-link UIs must restrict themselves to `CanonicalSegment` fields (`segment_id`, `polygon_pixel`, `bbox`, `area_pixels`, `area_percent`, `center_pixel`, `confidence`, `quality`, `structural_role`, `segmentation_state`, `edit_readiness`, `matched_room_id`, `matched_room_label`). `EnrichedSegment` extras (`mean_saturation`, `cluster_index`, `fill_ratio`, etc.) are engine-specific and may be absent depending on the engine — use them for debug overlays only, never for production rendering.

**Registry + lookup** — engines are registered in `_SEGMENTER_ENGINES`:

```python
_SEGMENTER_ENGINES = {
    "eufy_cv_v1":    EufyCVSegmenter(),
    "noop_fallback": NoopSegmenter(),
    # "roborock_deterministic": RoborockDeterministicSegmenter(),   # when ready
}

def get_segmenter_engine(name: str | None) -> MapSegmenter:
    """Returns the engine registered under `name`. Falls back to noop_fallback
    on unknown names with a logged warning."""
```

The two consumer call sites (`mapping/manager.py:get_image_segment_suggestions` and `mapping_services.py:_handle_analyze_map_image`) both:

1. Read `adapter_config["mapping"]["segmenter_engine"]` to pick the engine name.
2. Layer caller-supplied kwargs over the adapter's persisted `segmenter_tuning` (for one-off overrides via service calls).
3. Dispatch via `engine.segment_map_image(image_path=..., tuning=..., context=None)`.
4. Cache the resulting `SegmentationResult` under `map_bucket["image_segments"]` in `.storage`.

### 2.0a The three engines

**`eufy_cv_v1` — Pillow + NumPy + SciPy CV pipeline (default).** Wraps the `detect_room_segments` function described below (§2.1–§2.10). Used by adapters that ship flat map PNGs (Eufy, Dreame). The engine's `_reshape` method moves CV-specific diagnostics (`runtime` capability flags, `segmentation.stages.*` pipeline diagnostics) under `engine_diagnostics` so consumers of the canonical contract aren't polluted with engine internals.

**`noop_fallback` — empty result.** Used by adapters that yield no usable map data. Returns `{"available": False, "reason": "noop", "segments": [], ...}`. The card stops rendering polygonal overlays; the trace tracker keeps working off vacuum-space coordinates. This is the safe-default when an adapter doesn't declare a `mapping` block at all.

**`roborock_deterministic` — reserved.** Roborock provides the full map as structured wire data (vector polygons + affine transform) rather than an image. The engine will read `context["wire_payload"]` and translate it into the canonical `SegmentationResult` shape directly, populating `matched_room_id` from the wire room IDs (no fuzzy matching needed). Not yet implemented — slot reserved for when there's a Roborock adapter to drive it.

### 2.0b Adding a new engine

To support a new vendor's segmentation strategy:

1. Implement a class that satisfies `MapSegmenter` — `engine_name`, `validate_tuning`, `segment_map_image`. Translate the vendor's data into the canonical `SegmentationResult` shape.
2. Register it in `_SEGMENTER_ENGINES` under a new string name.
3. The adapter selects it via `adapter_config["mapping"]["segmenter_engine"] = "your_engine_name"` with any vendor-specific knobs under `segmenter_tuning`.

Framework code consuming the result is unchanged — it reads canonical fields off the result without knowing which engine produced it.

### 2.1 Eufy CV engine internals

The sections below describe the internals of `EufyCVSegmenter` — the engine that wraps the Pillow + NumPy + SciPy pipeline. All code lives in `mapping/image_segments.py`. The public function `detect_room_segments(...)` is called by `EufyCVSegmenter.segment_map_image()`, which then reshapes the output into the canonical `SegmentationResult` (hoisting `runtime` and `segmentation` blocks under `engine_diagnostics`).

> **Tuning caveat for porters.** Every threshold and parameter in
> this pipeline — flood-fill thresholds, RDP simplification epsilon,
> `min_area_pixels`, dock-anchor exclusion radius, the count-deficit
> recovery heuristics — was tuned against Eufy floor-plan PNGs
> (X10-style line weight, two-tone room fill, light wall outlines).
> Brands whose app exports look meaningfully different (heavier
> walls, different colour palette, photo-style floorplans, very
> high or low resolution) **will probably not segment well with the
> stock parameters**. The pluggable engine seam in §2.0 is the
> framework's answer to this: a port targeting one of those brands
> should write a new engine class rather than try to retune
> `eufy_cv_v1`. Three strategies are commonly viable — fork
> `EufyCVSegmenter` and adjust constants for the new image style;
> use `noop_fallback` and rely on the interactive boundary-trace
> flow (§3) for shape data; or implement a deterministic engine
> if the vendor exposes structured polygons over the wire (see
> the reserved `roborock_deterministic` slot).

### 2.1.1 Input

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

`image_runtime_capabilities()` probes whether each optional library is importable and returns a dict:

```python
{
    "numpy":           {"available": bool, "version": str|None, "error": str|None},
    "pillow":          {...},
    "scipy":           {...},
    "scipy_ndimage":   {...},
    "pipeline_ready":  bool,  # True if pillow + numpy + scipy.ndimage available
}
```

The pipeline uses Pillow + NumPy + SciPy. There is no OpenCV path — earlier drafts spec'd one but it was never implemented and the field carried no value.

---

## 3. Room Bounds from Traces

### 3.1 What a "trace" is

A trace is a time-ordered list of vacuum position samples collected during a single cleaning job. Each sample is `(vx, vy)` in vacuum coordinate units. Samples are collected in `MappingTracker._handle_position_update` by reading the `robot_position_x` and `robot_position_y` HA sensor states.

Deduplication is applied at collection time: if the new `(vx, vy)` is identical to the most recently recorded position, it is discarded. This prevents the X and Y sensors firing separately on the same movement event from creating double entries.

Sampling pauses during mid-job dock returns (`pause_sampling` / `resume_sampling`) to prevent hundreds of identical dock-position samples from corrupting room bounds.

Samples are flushed to a temporary file (`_samples_active.json`) every 25 unique positions so that an HA restart mid-job can recover the partial run.

### 3.2 Attribution Strategy

At the end of a job, `MappingManager.update_room_bounds` attributes samples to rooms:

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

> Map images are served to the card through the static-path registration documented in [ha-integration.md](ha-integration.md); the coordinate math below maps the vacuum's raw position sensors into pixel space for trace rendering.

### 4.1 Vacuum Coordinate Space

The vacuum reports its position as `(vx, vy)` values. These are in proprietary integer units originating from the robot's internal SLAM system. The scale is approximately 1 unit ≈ 1 mm for Eufy devices (not verified across all models). The origin and axis directions are robot-specific. On Eufy map_6 the Y axis increases upward in the robot's reference frame but this is not guaranteed by the protocol.

### 4.2 Pixel Coordinate Space

The map PNG uses the standard image convention: origin at the top-left, X increases rightward, Y increases downward.

### 4.3 Legacy: affine-transform calibration (System A)

> **Not the active pipeline.** Earlier versions of this integration produced room bounds by fitting a 2D affine transform from manually-anchored vacuum↔pixel pairs (`compute_affine_transform`, `add_calibration_point`, `merge_or_add_corner`, `reproject_machine_pairs` in [`transform.py`](../../custom_components/eufy_vacuum/mapping/transform.py)). That code is preserved for installations that set up calibration before the trace-based pipeline existed, but **the live system does not depend on it**.
>
> The active bounds system is the trace-based pipeline documented in [§3 Room Bounds from Traces](#3-room-bounds-from-traces). It fits envelopes directly from robot movement geometry recorded during a job — no manual anchoring, no least-squares matrix, no calibration pairs. New installs never use the affine transform.
>
> `vacuum_to_pixel` (the conversion formula itself) is still imported by [`boundary.py`](../../custom_components/eufy_vacuum/mapping/boundary.py) to render trace overlays when a legacy calibration matrix happens to exist, but for the bounds pipeline it is a no-op path. Porting a new brand does **not** require implementing any of this.
>
> If you need the historical details (3×3 row-major matrix, `numpy.linalg.lstsq` of `2N` equations in 6 unknowns, `CLUSTER_THRESHOLD_UNITS = 50`, residual quality bands), read the function docstrings in `transform.py` directly — they are the source of truth for the legacy code.

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

Three variants are recognised:

| Variant key | Role | Used for |
|------------|------|---------|
| `"default"` | `"primary"` | General display, fallback for analysis |
| `"dark"` | `"segmentation"` | Primary input for image segment analysis; dark theme captures have better colour contrast between rooms |
| `"light"` | `"boundary"` | Assist input for wall cutting; light theme captures have near-white walls that are easy to detect |

Variant names are normalised to lowercase, spaces and hyphens replaced by underscores.

### 6.1 Storage Paths

Images are stored in two locations (written identically):

- **Filesystem (config dir):** `<config_dir>/eufy_vacuum/mapping/<vacuum_slug>/map_<map_id>[_<variant>].png`
- **Browser-served (www root):** `<config_dir>/eufy_vacuum/maps/<vacuum_slug>/map_<map_id>[_<variant>].png`

The `_<variant>` suffix is omitted when `variant == "primary"` or `variant == "default"`. For dark: `map_6_dark.png`. For light: `map_6_light.png`. For default/primary: `map_6.png`.

The browser URL is: `/eufy_vacuum/maps/<vacuum_slug>/map_<map_id>[_<variant>].png`

Additionally, image metadata (width, height, path, browser_url) is recorded in the map's `image_variants` dict inside `map_<map_id>.json` and kept in sync with the `image_segment_adjustments` and `image_segments` results stored in the same JSON via the runtime's HA storage manager.

---

## 7. Outlier Detection

### 7.1 How the Mapping Review Panel Identifies Outliers

The mapping review panel calls `get_room_bounds_snapshot` to retrieve each room's `job_bounds_history`. The per-job history entries each contain `min_x`, `max_x`, `min_y`, `max_y`, `cx` (centre x), `cy` (centre y), `sample_count`, `recorded_at`, `job_id`, and `excluded`.

The UI derives its own outlier scoring from this data. The integration itself does not compute an outlier score server-side; however, the `score_transition_candidate` function in `boundary.py` demonstrates the scoring approach used for room polygon assessment:

```python
# Three signals, each normalised to [0.0, 1.0]:
convexity_score = clamp((hull_area / poly_area - 1.0) / 1.0, 0.0, 1.0)
aspect_score    = clamp((max(w,h)/min(w,h) - 1.5) / 3.5, 0.0, 1.0)
vertex_score    = clamp((vertex_count - 4) / 8.0, 0.0, 1.0)

score = convexity_score × 0.50 + aspect_score × 0.35 + vertex_score × 0.15
```

A polygon is flagged as a transition candidate (is_candidate = True) if *any single signal* clears its threshold:
- `convexity_ratio >= 1.4` — non-convex shape (L-shaped, T-shaped rooms)
- `aspect_ratio >= 3.5` — corridor-shaped bounding box
- `vertex_count >= 8` — high polygon complexity

This uses OR rather than AND so that a single strong signal (e.g. a clearly concave L-shape) surfaces without needing corroboration.

### 7.2 Manual Exclusion

The user can exclude any job history entry via `exclude_room_job_bounds(room_id, job_index)`. Exclusion sets `history[job_index]["excluded"] = True` and immediately calls `_recompute_bounds_from_history` to recompute the union from the remaining active entries. The corresponding archive JSONL line is also updated (via `tracker.update_raw_samples_exclusion`) so the exclusion flag persists through a rebuild.

### 7.3 Baseline Protection

The oldest entry in the history (index `len(history) - 1` in the newest-first list) is the *baseline entry*. It is protected from exclusion:

```python
if job_index == len(history) - 1:
    return {"success": False, "reason": "baseline_protected"}
```

The rationale: the baseline is the first clean run that established the room's identity. Without it, the system has no reference to judge whether later runs are within a plausible range. Allowing it to be excluded could collapse the bounds to zero or to a degenerate range.

---

## 8. File Layout

All per-vacuum files live under `<config_dir>/eufy_vacuum/mapping/<vacuum_slug>/`.

### 8.1 Map State File

```
map_<map_id>.json
```

One JSON file per (vacuum, map). Contains:

- `calibration` — calibration pairs, transform matrix, residual, `calibration_room_id`
- `rooms` — per-room dict keyed by `room_id` string. Each room entry holds:
  - `boundary` — vacuum-space polygon from a boundary trace (list of `[vx, vy]`)
  - `boundary_pixel` — same polygon in pixel space
  - `bounds` — the active bounding box: `{min_x, max_x, min_y, max_y, cx, cy, run_count, sample_count, updated_at}`
  - `job_bounds_history` — list of up to 20 job entries, newest first
  - `traced_at` — ISO timestamp of last boundary trace close
  - `transition_candidate` / `transition_score` — derived from `score_transition_candidate`
- `image_path`, `image_width`, `image_height` — legacy fields, now duplicated in `image_variants`
- `image_variants` — dict of variant metadata records
- `package` — the richer mapping package (see below)

### 8.2 Mapping Package

Embedded in `map_<map_id>.json` under the `"package"` key:

- `room_definitions` — dict keyed by `room_id`. Each definition has labels, slugs, segment link (`suggestion_segment_id`), anchor pixel/vacuum, zone tags, adjacency, etc.
- `segment_adjustments` — per-segment `offset_x`, `offset_y`, edge deltas, vertex moves
- `dock` — pixel/vacuum anchor for the dock, exclusion radius
- `trace_evidence` — up to 100 user-annotated evidence records
- `images` — variant metadata records (merged with `image_variants`)

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

### 8.5 Trace Run Files

```
traces/<vacuum_slug>/trace_<timestamp>_<map_id>_<room_id>.json
```

Written by `TraceCapture.stop()` via `write_trace_run`. Each file is a full `TraceRun` dict: `run_id`, `schema_version`, `vacuum_entity_id`, `map_id`, `room_id` (may be `null`), `started_at`, `ended_at`, `sample_count`, and `samples` (list of `{"x": float, "y": float, "ts": ISO}`).

These files are the input to the trace segmentation pipeline and the trace review pipeline. They are not automatically cleaned up; `delete_trace_run_by_id` removes one file.

---

## 9. Porting Considerations

### 9.1 Eufy-Specific

The following are specific to Eufy's implementation:

- **Vacuum coordinate units** — Eufy reports `robot_position_x` / `robot_position_y` as integer sensor states in its proprietary unit. The scale (≈ 1 mm/unit) is inferred and not guaranteed.
- **Map image format** — Eufy's map images use a consistent hue-per-room convention. The dark variant provides saturated, high-contrast room colours; the light variant provides near-white walls. Both properties are assumed by the HSV thresholding approach.
- **HA entity model** — `MappingTracker` listens to Home Assistant state change events for position sensors and fires HA bus events (`eufy_vacuum_room_completed`, `eufy_vacuum_calibration_updated`, `eufy_vacuum_boundary_saved`). These are HA-specific patterns.
- **HA storage** — `MappingManager._save_map_data` / `_load_map_data` writes directly to JSON files on the config dir filesystem. The `image_segment_adjustments` and `image_segments` results live in the runtime HA storage manager (`.storage` files), not in the mapping JSON files.

### 9.2 Generic / Portable

The following components have no Eufy-specific dependencies and would port directly to another robot or framework:

- **`image_segments.py`** — entire pipeline. Inputs: a PNG file path. Outputs: a pure-Python dict. Only dependencies: Pillow, NumPy, SciPy.
- **`boundary.py`** — Douglas-Peucker simplification, corner detection, point-in-polygon (ray casting), transition candidate scoring, shoelace polygon area, convex hull (Andrew's monotone chain). All pure Python.
- **`transform.py`** — affine transform computation (requires NumPy), `vacuum_to_pixel`, `pixel_to_vacuum`, calibration pair clustering. The coordinate system is abstract — substitute any two corresponding point sets.
- **`trace_capture.py`** — in-memory session manager. No HA dependency. Requires a `write_trace_run` backend (currently `trace_store.py`).
- **`trace_segmentation.py`** — `segment_trace_run`. Input: a TraceRun dict with `samples` having `x`, `y`, `ts` keys. Output: a SegmentationResult dict. No HA dependency.
- **`_percentile_trim`** in `manager.py` — pure Python outlier trimming.
- **`_recompute_bounds_from_history`** — pure Python union of history entries.

The `BOUNDS_MARGIN` value (50 vacuum units) and percentile parameters (P10/P90) are tuning constants that will need adjustment if the coordinate scale differs from Eufy's.

---

## 10. Services

All mapping services are registered in `mapping/mapping_services.py`
under the `eufy_vacuum.*` namespace. The central index of every
integration service lives in
[advanced/03-services.md](../advanced/03-services.md).

The services fall into five functional groups: map image management,
calibration, room boundaries (interactive draw + trace-driven), dock
anchoring, and image-segment analysis.

> **`map_id` is optional on every service** listed below. The
> integration auto-resolves it from the adapter's `entities.active_map`
> entity when the caller omits it. The tables show `map_id` in the
> Required column because the card always passes it (it knows which
> map it's on), but the service surface itself accepts an omitted
> `map_id` and falls back to the active map. See
> [advanced/03-services.md](../advanced/03-services.md) for the
> user-facing details.

### Map image management

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `save_map_image` | Store a base64-encoded PNG as the map image for one vacuum/map. | `vacuum_entity_id`, `map_id`, `image_base64: str` | `image_width: int`, `image_height: int`, `variant: str` | no |
| `upload_map_image` | Accept a user-uploaded floor plan image for analysis (alternative entry point). | `vacuum_entity_id`, `map_id`, `image_base64: str` | (none) | no |
| `analyze_map_image` | Dispatch to the adapter-declared segmenter engine (see §2.0). | `vacuum_entity_id` | `map_id` (auto), `force_reanalyze: bool`, plus tuning overrides that layer on top of `adapter_config.mapping.segmenter_tuning` (`expected_room_count`, `max_segments`, `min_area_pixels`, `simplify_epsilon`) | yes — canonical `SegmentationResult` with engine-specific diagnostics under `engine_diagnostics` |

### Calibration

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `add_calibration_point` | Record one pixel↔world coordinate pair for georeferencing the map. | `vacuum_entity_id`, `map_id`, `pixel_x: float`, `pixel_y: float`, `vacuum_x: float`, `vacuum_y: float` | `label: str`, `is_calibration_room: bool`, `calibration_room_id: str` | no |
| `compute_transform` | Calculate the affine transform from accumulated calibration points. See §4. | `vacuum_entity_id`, `map_id` | (none) | no |
| `clear_calibration` | Remove all calibration points and the computed transform for one map. | `vacuum_entity_id`, `map_id` | (none) | no |
| `set_companion_anchor` | Position a secondary anchor point for offset correction. | `vacuum_entity_id`, `map_id`, `pixel_x: float`, `pixel_y: float` | `vacuum_x: float`, `vacuum_y: float`, `notes: str` | no |

### Interactive room boundaries

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `start_room_boundary_trace` | Begin an interactive boundary-drawing session for one room. The card streams pointer positions until `close` or `cancel`. | `vacuum_entity_id`, `map_id`, `room_id: str` | (none) | no |
| `close_room_boundary` | Finalize the drawing as a closed polygon with epsilon smoothing applied. | `vacuum_entity_id`, `map_id`, `room_id: str` | `epsilon: float` (default 5.0) | no |
| `cancel_room_boundary_trace` | Abort the current drawing session without saving. | `vacuum_entity_id`, `map_id`, `room_id: str` | (none) | no |
| `get_room_bounds_snapshot` | Return all currently recorded room-boundary polygons for one map. | `vacuum_entity_id`, `map_id` | (none) | yes — `{room_id: polygon, ...}` |
| `clear_room_bounds` | Discard the boundary for one room. | `vacuum_entity_id`, `map_id`, `room_id: str` | (none) | no |

### Trace-driven boundaries (job-based learning)

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `start_trace_capture` | Begin recording the robot's position trace during a clean job. Phase-1 of trace-driven bounds. | `vacuum_entity_id`, `map_id` | `room_id: str` | no |
| `stop_trace_capture` | End recording (the trace is saved and available for review). | `vacuum_entity_id`, `map_id` | (none) | no |
| `cancel_trace_capture` | Discard the in-progress trace. | `vacuum_entity_id`, `map_id` | (none) | no |
| `review_trace_run` | Review and finalize a captured trace run. Phase-2 of trace-driven bounds. | (payload TBD) | (none) | no |
| `append_mapping_trace_evidence` | Add a positional sample to an in-progress trace. Called by the live-position listener. | `vacuum_entity_id`, `map_id`, `evidence: dict` | (none) | no |
| `exclude_room_job_bounds` | Mark one job's trace-derived bounds for a room as unreliable. Excluded from union averaging. | `vacuum_entity_id`, `map_id`, `room_id: str`, `job_index: int` | (none) | no |
| `restore_room_job_bounds` | Re-include previously excluded bounds for one job. | `vacuum_entity_id`, `map_id`, `room_id: str`, `job_index: int` | (none) | no |
| `rebuild_room_bounds_from_archive` | Recompute one room's bounds from all archived trace runs after exclusions/restorations. | `vacuum_entity_id`, `map_id`, `room_id: str` | (none) | no |

### Dock and segment positioning

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `set_dock_anchor` | Place the dock at a pixel + world coordinate. Drives dock-relative trace start-points. | `vacuum_entity_id`, `map_id`, `pixel_x: float`, `pixel_y: float` | `vacuum_x: float`, `vacuum_y: float`, `exclusion_radius: float`, `notes: str` | no |
| `set_dock_room` | Mark a room as the dock-containing room. | `vacuum_entity_id`, `map_id`, `room_id: str` | `notes: str` | no |

### Image segment analysis

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `get_image_segment_suggestions` | Detect contiguous regions in the map image as candidate room polygons. | `vacuum_entity_id`, `map_id` | `min_area_pixels: int` (default 1200), `simplify_epsilon: float`, `max_segments: int` | yes — `{segments: [...]}` |
| `translate_image_segment` | Move/edit a polygon segment via delta translation, edge nudge, or per-vertex moves. | `vacuum_entity_id`, `map_id`, `segment_id: str` | `delta_x: int`, `delta_y: int`, `edge_*`, `vertex_moves: list` | no |
| `adjust_map_segment` | Batch segment edits in one call. See §5. | `vacuum_entity_id`, `map_id`, `updates: list[dict]` | (none) | no |
| `set_segment_room_link` | Link or unlink a detected segment to/from a room. | `vacuum_entity_id`, `map_id`, `segment_id: str` | `room_id: str` (omit to unlink) | no |
| `get_map_segments` | Return detected segments plus their room links and companion anchors. | `vacuum_entity_id`, `map_id` | (none) | yes — `{segments, segment_room_links, companion_anchors}` |

### State and packaging

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `get_mapping_state` | Fetch calibration points, boundaries, and current transform for one map. | `vacuum_entity_id`, `map_id` | (none) | yes — full mapping state dict |
| `get_mapping_package` | Retrieve the full calibration/boundary/transform package for export or sync. | `vacuum_entity_id`, `map_id` | (none) | yes — package dict |
| `save_mapping_package` | Persist a calibration/boundary/transform package (used by import flows). | `vacuum_entity_id`, `map_id`, `package: dict` | (none) | no |
