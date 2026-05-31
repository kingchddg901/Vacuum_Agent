# Mapping — Subsystem Test Map

The mapping subsystem turns robot-position traces and map images into room
boundaries: a capture/trace pipeline (`trace_capture` → `trace_store` →
`trace_segmentation` → `trace_review`), an image-segmentation stack
(`segment_primitives`, `segmenter_engines`), a coordinate tracker
(`tracker`), and two large orchestrators (`manager`, `mapping_services`).
Covered by **207 tests across 11 files** (the trace/image primitives are
near-fully covered; the two orchestrators have their pure helpers covered with
the hass-bound bodies deferred).

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
| `segment_primitives.py` | 239 | 91% | `tests/unit/test_mapping_segment_primitives.py` | unit (pure + numpy/scipy) |
| `segmenter_engines.py` | 134 | 87% | `tests/unit/test_mapping_segmenter_engines.py` | unit (pure) |
| `trace_segmentation.py` | 314 | 84% | `tests/unit/test_mapping_trace_segmentation.py` | unit (pure) |
| `tracker.py` | 353 | 45% | `tests/unit/test_mapping_tracker.py` | unit (pure state + `tmp_path` files) |
| `manager.py` | 963 | 24% | `tests/unit/test_mapping_manager_helpers.py` | unit (module helpers only) |
| `mapping_services.py` | 650 | 29% | `tests/unit/test_mapping_services_helpers.py` | unit (pure helpers only) |

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

### The tracker (partial)
- **`tracker`** (`MT`) — pure `_RoomConfidenceState` (movement/time confidence,
  resets) and the file-backed helpers (active-samples flush/load/delete, the
  raw-samples JSONL archive, exclusion flagging, archive-rebuild delegation).

### The orchestrators (helpers only)
- **`manager`** (`MM`) — the module-level pure helpers: slug/coercion,
  `_deep_merge_dict`, `_percentile_trim`, point/variant normalization,
  `_normalize_segment_adjustments`, `_adjust_polygon_pixel`,
  `_bbox_from_polygon_pixel`.
- **`mapping_services`** (`MS`) — `_apply_segment_adjustments`,
  `_build_segments_response`, and the module-local geometry helpers (which
  differ subtly from the manager copies — strict `int()`, no `+1` on bbox).

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

## Known gaps (deferred to a later integration pass)

The two orchestrators and the tracker's event pipeline are the bulk of the
remaining lines, all hass-bound:
- **`manager.py`** (24%) — the `MappingManager` class methods: bounds learning,
  room-bounds CRUD, image-segment caching, snapshot building. Needs a real hass
  + `tmp_path` config dir and seeded map data.
- **`mapping_services.py`** (29%) — the async service handlers
  (`_handle_upload_map_image`, `_handle_analyze_map_image`, segment link/anchor
  handlers) and `async_register_mapping_services`. Needs `hass` + the mapping
  manager wired; note these register via their **own**
  `async_register_mapping_services`, not the domain `async_register_services`.
- **`tracker.py`** (45%) — `register_vacuum` and the position-sensor state-change
  callbacks that drive room-confidence firing. Needs real robot-position
  entities and `async_track_state_change_event`.
- **`trace_segmentation`** soft-signal branches (speed/density/boundary-crossing
  detection) — reachable only with elaborate synthetic multi-signal traces.

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
