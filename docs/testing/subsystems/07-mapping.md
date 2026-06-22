# Mapping — Subsystem Test Map

The mapping subsystem turns robot-position traces and map images into room
boundaries: a capture/trace pipeline (`trace_capture` → `trace_store` →
`trace_segmentation` → `trace_review`), an image-segmentation stack
(`segment_primitives`, `segmenter_engines`), a coordinate tracker
(`tracker`), and two large orchestrators (`manager`, `mapping_services`).
A second authoring path lets a human draw rooms directly: `segment_primitives`
rasterises composer shapes into polygons, and `mapping_services` holds many named
**custom layouts** per map alongside the CV store, selected by a `segmentation_mode`
pointer flip.
A third path skips authoring entirely: the **`map_state_source` reader**
(`map_source`, `map_source_runtime`, `map_source_coordinator`) normalizes the
provider's OWN segmentation + live pose into VA-owned room data (bbox/name, dock/robot
anchors, area, current room, overlay layers), so rooms are auto-derived from the device's
authoritative map rather than learned from drifting samples or hand-drawn.
Covered by **479 tests across 20 files** — the trace/image primitives are
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
| `segment_primitives.py` | 280 | 93% | `tests/unit/test_mapping_segment_primitives.py` | unit (pure + numpy/scipy) |
| `segmenter_engines.py` | 132 | 100% | `tests/unit/test_mapping_segmenter_engines.py` | unit (pure) |
| `trace_segmentation.py` | 314 | 95% | `tests/unit/test_mapping_trace_segmentation.py` | unit (pure) |
| `tracker.py` | 403 | 92% | `test_mapping_tracker.py` + `test_mapping_tracker_events.py` | unit + integration |
| `manager.py` | 904 | 92% | `test_mapping_manager_helpers.py` + `test_mapping_manager.py` + `test_mapping_image_pipeline.py` | unit + integration |
| `mapping_services.py` | 1069 | 90% | `test_mapping_services_helpers.py` + `test_mapping_services.py` + `test_mapping_services_handlers.py` + `test_mapping_image_pipeline.py` | unit + integration |
| `map_source.py` | 334 | 95% | `tests/unit/test_map_source.py` | unit (pure) |
| `map_source_runtime.py` | 456 | 90% | `tests/unit/test_map_source_runtime.py` + `tests/unit/test_map_source_collectors.py` | unit (pure) |
| `map_source_coordinator.py` | 189 | 52% | `tests/integration/test_manager_compare_sources.py` + `tests/integration/test_manager_live_pose.py` | integration |

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
  `compactness`, `aspect_ratio`, …), the numpy/scipy mask primitives
  (`mask_to_polygon`, `mask_iou`, transforms, `mask_edge_band`,
  `estimate_alignment`, `normalized_color_features`), and
  `rasterize_primitives` — the composer rasteriser that turns rect/circle/polygon
  shapes into a mask (fill + ordered `subtract` ops) for custom segments.
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

### Custom & multi-layout segmentation
The human-authored alternative to CV, exercised end to end through the services.

- **Authoring** (`test_mapping_image_pipeline.py`) — `set_custom_segments`
  rasterises composer primitives into room polygons (replace-all; refuses with
  `no_custom_backdrop` until a backdrop image exists), and a custom room link
  survives a re-save. `set_segmentation_mode` is a pure pointer flip that **never
  re-runs the segmenter** and losslessly switches the served store (cv ↔ custom).
- **Named layouts** (`LAYOUT-*`, `test_mapping_services.py`) — the `custom_layouts`
  collection lifecycle: a legacy single `custom_segments` store migrates into one
  default layout (custom-resolved links/anchors move onto the layout, CV's stay on
  the map bucket); create / rename / set-active / delete (create flips to custom and
  activates, delete-active reassigns, delete-last flips back to CV); and set-active
  with zero layouts auto-creates one.
- **Per-layout isolation** — the same segment id may link to *different* rooms on
  two layouts (`test_per_layout_segment_isolation`), and companion anchors including
  the reserved `dock` spot are per-layout (`LAYOUT-6`) — neither bleeds across.
- **Furnished render** (`FURN-*`, `test_mapping_furnished_render.py`) — the per-layout
  furnished-art contract end to end: `set_furnished_art_placement` (home/room scope,
  4dp round-trip, scale clamp to `[0.05, 20]`, clear-on-all-null, missing-room-id
  guard), `set_furnished_render_mode` (layout vs per-room, blank room_id → layout
  level), `set_room_viewport`, the `upload_map_image` `art_scope` variant routing
  (`custom_<id>_home_art` / `_room_<rid>` onto `home_art`/`rooms`, never the backdrop),
  the `resolve_furnished_render` projection, the `delete_custom_layout` art sweep, and
  per-layout isolation — all through the real service registry.

### The map_state_source reader
The brand-agnostic read of the **provider's own** segmentation + live pose into
VA-owned room data (architecture: [docs/dev/map-state-source.md](../../dev/map-state-source.md)).
The pure extraction/normalization is unit-tested without Home Assistant; the
manager-facing seams (delegators into `MapSourceCoordinator`) are integration-tested.

- **`map_source`** (`MS-*`, unit, `test_map_source.py`) — the pure core:
  `rooms_from_room_pixels` (per-room bbox+name, Y-flip, catch-all rid 32 filtered,
  malformed/short buffers degrade to `[]`), `normalize_rendered` clamp+flip,
  `anchors_from_storage` (dock/robot normalize, non-numeric coords skipped),
  `rooms_from_parsed_map` (Roborock parser path, flagged approximate), per-room area
  (`pixel_count × (res_cm/100)²`), and `build_map_source_result`'s presence gate
  (absent-with-reason vs populated, with `extra` overlay layers merged in).
- **`map_source_runtime`** (`MSR-*` + `MSC-*`, unit,
  `test_map_source_runtime.py` + `test_map_source_collectors.py`) — the HA-aware
  glue tested with injected plain data: `eufy_result_from_store` (the `#136` version
  guard, presence gate, extraction, degradation), the Roborock `find_mapdata` /
  `find_roomlike_collection` defensive introspector (duck-typing, cycle-safety, attr
  denylist), and the candidate collectors (`eufy_inmem_candidates`,
  `roborock_candidates`, `image_entity_object`) that gather roots from
  `hass.data[domain]` / per-entry `runtime_data` / the image entity, each degrading
  cleanly when a source is absent.
- **`map_source_coordinator`** (`CMP-*` + `LP-*`, integration,
  `test_manager_compare_sources.py` + `test_manager_live_pose.py`) — the manager
  delegators into `MapSourceCoordinator`: `async_compare_map_sources` (the verify
  probe — not_configured / memory_not_configured guards, flags-only when only one
  source is present, `compare_map_data` reached when both are, diagnostics breadcrumb
  passthrough) and the live-pose seam `async_get_map_live_pose` /
  `_apply_inmem_pose_to_result` (robot/dock/heading/trail overlaid on present pose,
  base overlays preserved when pose is absent or its read raises, `no_geom` reason
  when geometry is missing).

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
belongs. Framework-level tests stay engine-agnostic; brand CV tests live with the brand code.

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
  light-assist wiring (the `tuning` dict + `assist_image_path` block inside that handler)
  is **deferred**: a robust test fights the dual image store (`save_map_image` writes the
  per-map JSON store while the handler probes the filesystem) plus phac's shared config dir
  — not worth a fragile test. The rest is defensive (the `OSError` delete branch in
  `_handle_delete_map_image`, non-dict guards, the tracker-absent else, and the
  schema-unreachable coerce guards in `_build_segments_response`).
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
