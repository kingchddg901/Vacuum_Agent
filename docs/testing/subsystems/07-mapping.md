# Mapping — Subsystem Test Map

The mapping subsystem turns robot-position traces and map images into room
boundaries: a capture/trace pipeline (`trace_capture` → `trace_store` →
`trace_segmentation` → `trace_review`), an image-segmentation stack
(`segment_primitives`, `segmenter_engines`), a coordinate tracker
(`tracker`), and two large orchestrators (`manager`, `mapping_services`).
Covered by **~265 tests across 15 files** — the trace/image primitives are
near-fully covered, the tracker + two orchestrators have both their pure helpers
(unit) and hass-bound bodies (integration) covered, and the real
detect_room_segments CV pipeline runs end to end against a synthetic image.

Source: `custom_components/eufy_vacuum/mapping/`
Architecture reference: [docs/dev/11-mapping-system.md](../../dev/11-mapping-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `boundary.py` | 128 | 98% | `tests/integration/test_mapping_boundary.py` | unit (pure geometry) |
| `trace_store.py` | 35 | 100% | `tests/unit/test_mapping_trace_store.py` | unit (`tmp_path`) |
| `trace_capture.py` | 63 | 100% | `tests/unit/test_mapping_trace_capture.py` | unit (`tmp_path`) |
| `trace_review.py` | 162 | 95% | `tests/unit/test_mapping_trace_review.py` | unit (pure) |
| `segment_primitives.py` | 239 | 93% | `tests/unit/test_mapping_segment_primitives.py` | unit (pure + numpy/scipy) |
| `segmenter_engines.py` | 132 | 99% | `tests/unit/test_mapping_segmenter_engines.py` | unit (pure) |
| `trace_segmentation.py` | 314 | 92% | `tests/unit/test_mapping_trace_segmentation.py` | unit (pure) |
| `tracker.py` | 344 | 90% | `test_mapping_tracker.py` + `test_mapping_tracker_events.py` | unit + integration |
| `manager.py` | 907 | 89% | `test_mapping_manager_helpers.py` + `test_mapping_manager.py` + `test_mapping_image_pipeline.py` | unit + integration |
| `mapping_services.py` | 650 | 91% | `test_mapping_services_helpers.py` + `test_mapping_services.py` + `test_mapping_services_handlers.py` + `test_mapping_image_pipeline.py` | unit + integration |

---

## What's tested

### The trace pipeline (high coverage)
- **`trace_store`** (`TST`) — `tmp_path` round-trips: write/load, missing +
  corrupt-JSON → None, sorted listing, delete found/missing.
- **`trace_capture`** (`TC`) — in-memory capture sessions: start/append/stop
  (persist verified against `tmp_path`), cancel, replace-previous, summaries.
- **`trace_segmentation`** (`TS`) — the split/merge algorithm: `_parse_ts`,
  `_dist`, `_rolling_mean`, `_local_density`, `_extract_samples`,
  `_compute_per_sample_signals`, pause-split detection, segment construction,
  short + similar merges, and `segment_trace_run` end-to-end.
- **`trace_review`** (`TR`) — trace-quality metrics (spatial spread, path
  density, entry-exit/transit ratios, boundary crossings), segment-metadata
  threshold adjustments, and the accepted/rejected/needs_refine verdict.

### The image stack
- **`segment_primitives`** (`SP`) — pure geometry (`rdp`, `polygon_area`,
  `compactness`, `aspect_ratio`, …) plus the numpy/scipy mask primitives
  (`mask_to_polygon`, `mask_iou`, transforms, `mask_edge_band`,
  `estimate_alignment`, `normalized_color_features`).
- **`segmenter_engines`** (`SE`) — the engine registry, tuning validation, and
  the no-image/noop unavailable paths. The CV pipeline body (`detect_room_segments`)
  is exercised only through its failure paths.

### The tracker
- **`tracker`** (`MT`, unit) — pure `_RoomConfidenceState` and the file-backed
  helpers (active-samples flush/load/delete, the raw-samples JSONL archive,
  exclusion flagging).
- **`tracker`** (`MTE`, integration) — the job lifecycle: register/unregister,
  `start_job`/`end_job` (room-bounds write + raw-sample archive),
  pause/resume sampling, `_handle_position_update` (accumulate/dedup/pause), and
  the confidence-threshold room-exit firing `eufy_vacuum_room_completed`.

### The orchestrators
- **`manager`** (`MM`, unit) — the module-level pure helpers. **`MGR`,
  integration** — the `MappingManager` class against a real hass: room-bounds
  attribution/snapshot/clear, exclude/restore job bounds, the trace-capture and
  boundary-trace lifecycles, dock anchor/room, and `get_mapping_state`.
- **`mapping_services`** (`MS`, unit) — `_apply_segment_adjustments`,
  `_build_segments_response`, and the module-local geometry helpers (which
  differ subtly from the manager copies — strict `int()`, no `+1` on bbox).
  **`MSH`, integration** — the service handlers via
  `async_register_mapping_services`: `get_map_segments`, `adjust_map_segment`,
  `set_segment_room_link` (set/clear/1:1), `set_companion_anchor`,
  `delete_map_image`.

---

## How it's tested

Four patterns, same as elsewhere in the suite:

1. **Pure import** (Recipe C) — the trace algorithms, geometry, engine registry,
   and both orchestrators' helpers. No fixtures.
2. **`tmp_path` filesystem** — `trace_store`, `trace_capture`, and the
   `tracker` file helpers get an isolated config dir. For `tracker`, the hass is
   a `MagicMock` with `config.config_dir = str(tmp_path)` and the manager is a
   `MagicMock`:
   ```python
   hass = MagicMock(); hass.config.config_dir = str(tmp_path)
   tracker = MappingTracker(hass, MagicMock())
   ```
3. **numpy/scipy arrays** — the `segment_primitives` mask tests build real
   arrays. numpy ships transitively via HA core; **scipy and Pillow are explicit
   test deps** (see `requirements_test.txt`). Scipy-only paths still guard with
   `pytest.importorskip("scipy.ndimage")` so the file degrades gracefully if the
   stack is ever absent.
4. **Cross-module reference checks** — where `mapping_services` duplicates a
   `manager` helper, the test pins the *actual* behavior of each copy rather than
   assuming they match (they don't — see the bbox `+1` difference).

---

### Image/CV pipeline (`IMG`, integration — brand-agnostic)
The framework's segment plumbing (`save_map_image`, `analyze_map_image`,
`get_image_segment_suggestions`, `translate_image_segment`) is tested against a
**registered fake segmenter engine** that returns a canned `SegmentationResult`
— *not* a concrete brand engine. This proves the framework drives any adapter's
CV pipeline without coupling to Eufy's. The real Eufy CV segmentor
(`detect_room_segments`, HSV masks, `EufyCVSegmenter`) is tested **solo in
`tests/adapters/eufy/test_segmentor.py`** (prefix `ECV`), where brand code
belongs. See [feedback_brand_agnostic_tests](../../../) in memory for the rule.

### Non-segment service handlers (`MSV`, integration)
The boundary-trace, dock, trace-capture, mapping-state/package, room-bounds,
save-package, trace-evidence, and review-trace-run service handlers, exercised
through `async_register_mapping_services`.

## Known gaps

What remains is mostly defensive `except` paths and a few image-specific edges:
- **`manager.py`** (70%) — `_handle`-style boundary normalization edge branches,
  the `save_map_image` www-path writes, and the vertex-move sub-branch of the
  segment-adjust body (2387-2408).
- **`mapping_services.py`** (72%) — `_handle_upload_map_image` (base64 image
  upload) and `save_map_image` service body; both need real image bytes.
- **`tracker.py`** (73%) — the multi-room `end_job` archive attribution, the
  periodic flush-to-disk task, and `_get_raw_position` (full capability stack).
- **`trace_segmentation`** (89%) — a few merge-pass tie-break branches.

---

## Extending

1. **A new trace/geometry/engine behavior?** Pure unit test — add a target to
   the matching file. Use `tmp_path` if it touches disk.
2. **A scipy/numpy image path?** Build real arrays; gate scipy-only code with
   `pytest.importorskip`.
3. **An orchestrator method or service handler?** That's the integration pass —
   stand up the `MappingManager` with a real hass + `tmp_path` config dir (and
   register via `async_register_mapping_services` for the service layer).
4. Re-measure across **all** mapping test files together for the true per-module
   number.
