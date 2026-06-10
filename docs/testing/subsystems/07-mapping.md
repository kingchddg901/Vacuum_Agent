# Mapping — Subsystem Test Map

The mapping subsystem turns robot-position traces and map images into room
boundaries: a capture/trace pipeline (`trace_capture` → `trace_store` →
`trace_segmentation` → `trace_review`), an image-segmentation stack
(`segment_primitives`, `segmenter_engines`), a coordinate tracker
(`tracker`), and two large orchestrators (`manager`, `mapping_services`).
Covered by **333 tests across 15 files** — the trace/image primitives are
near-fully covered, the tracker + two orchestrators have both their pure helpers
(unit) and hass-bound bodies (integration) covered, and the real
detect_room_segments CV pipeline runs end to end against a synthetic image.

Source: `custom_components/eufy_vacuum/mapping/`
Architecture reference: [docs/dev/11-mapping-system.md](../../dev/11-mapping-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `boundary.py` | 128 | 99% | `tests/integration/test_mapping_boundary.py` | unit (pure geometry) |
| `trace_store.py` | 35 | 100% | `tests/unit/test_mapping_trace_store.py` | unit (`tmp_path`) |
| `trace_capture.py` | 63 | 100% | `tests/unit/test_mapping_trace_capture.py` | unit (`tmp_path`) |
| `trace_review.py` | 162 | 95% | `tests/unit/test_mapping_trace_review.py` | unit (pure) |
| `segment_primitives.py` | 239 | 94% | `tests/unit/test_mapping_segment_primitives.py` | unit (pure + numpy/scipy) |
| `segmenter_engines.py` | 132 | 100% | `tests/unit/test_mapping_segmenter_engines.py` | unit (pure) |
| `trace_segmentation.py` | 314 | 95% | `tests/unit/test_mapping_trace_segmentation.py` | unit (pure) |
| `tracker.py` | 344 | 93% | `test_mapping_tracker.py` + `test_mapping_tracker_events.py` | unit + integration |
| `manager.py` | 904 | 92% | `test_mapping_manager_helpers.py` + `test_mapping_manager.py` + `test_mapping_image_pipeline.py` | unit + integration |
| `mapping_services.py` | 650 | 94% | `test_mapping_services_helpers.py` + `test_mapping_services.py` + `test_mapping_services_handlers.py` + `test_mapping_image_pipeline.py` | unit + integration |

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

Every module sits at 92–100%. The genuinely-untested *behaviours* were closed in
the 2026-06 gap pass (legacy-calibration migration, dock optional-field writes,
`_write_job_bounds` newest-file injection, assist-image selection, delete-variant
retain + already-gone paths, the adjust-segment vertex-merge / reset-to-zero
branches, the room-bounds-snapshot archive enrichment, the raw-sample rolloff +
multi-room orphan drop, the short/similar-segment merge branches, the RDP
fallback / non-unit zoom / alignment-recovery primitives, the degraded `_reshape`
diagnostics, and the sliver area guard). What remains is uncovered **on purpose**,
per the ~90% held-ceiling policy — defensive guards, not coverage debt:

- **`manager.py`** (92%) — non-dict/malformed-input coercion guards across the
  package/dock/roster normalizers, except-on-parse blocks, and not-taken partial
  branches.
- **`mapping_services.py`** (94%) — the `_handle_analyze_map_image` tuning-override /
  light-assist wiring (834-846) is **deferred**: a robust test fights the dual image
  store (`save_map_image` writes the per-map JSON store while the handler probes the
  filesystem) plus phac's shared config dir — not worth a fragile test. The rest is
  defensive (the `OSError` delete branch 693-695, non-dict guards, the tracker-absent
  else, and schema-unreachable coerce guards like 1110-1111).
- **`tracker.py`** (93%) — `# pragma: no cover` I/O / manager except-blocks,
  malformed-line resilience, and trivial early-return guards. The transition-room
  skip at 707 is a redundant defensive short-circuit (its normal path is covered by
  `test_room_completed_event`), deliberately left.
- **`trace_segmentation.py`** (95%) — None-ts / empty-window / zero-baseline guards
  and threshold-duplicate artifacts. The outside/mixed `boundary_state` branches
  (367-370) are covered only on the merge-recompute path, not on the initial build
  with a polygon — thin duplicate-coverage, not dead code (the merge passes read
  `boundary_ratio` and a test asserts the recomputed state).
- **`segment_primitives.py`** (94%), **`trace_review.py`** (95%), **`boundary.py`**
  (99%) — empty-mask divide-by-zero returns, optional-dependency guards, unreachable
  malformed-edge artifacts, and the `<3-unique-point` hull fallback (boundary 269,
  unreachable through its only caller).

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
