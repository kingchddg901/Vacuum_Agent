# 31 — MapSourceCoordinator

> **Scope:** Implementation reference for `mapping/map_source_coordinator.py` — the bundled subsystem that owns the **`map_state_source`** backend dispatch (the VA's read of the *provider's own* room segmentation + live pose). It is the runtime brain behind the seam; the pure decode/normalization lives in `mapping/map_source.py` and `mapping/map_source_runtime.py`, and the *design* rationale lives in [map-state-source](map-state-source.md). This doc is the ownership anchor — several older docs still attribute these four `async_*` readers to `core/manager.py`; they are **delegators**, the work is here.

---

## 1. Overview

`map_state_source` is the **VA-owned read of the device/fork's OWN map segmentation** — the provider's authoritative per-room geometry, current room, and live robot/dock pose — normalized into a brand-general payload the card and consumers use. It is **distinct from the CV segmentor** ([26-eufy-segmentor](26-eufy-segmentor.md)): the segmentor *infers* rooms from an uploaded map *image* with computer vision; `map_state_source` *reads* the segmentation the device already computed (room-id raster on Eufy, the parsed `MapData` on Roborock) and never guesses. It is also distinct from the legacy trace-bounds path ([11-mapping-system](11-mapping-system.md) §3), which derived bounds from drifting robot samples; `map_state_source` is immune to the per-session coordinate drift (see `reference_eufy_intersession_coord_drift`) because it consumes the provider's own segmentation, not accumulated poses.

`MapSourceCoordinator` is constructed with the core manager (the bundled-subsystem pattern, the same shape as `ActiveJobTracker`, `PhaseRunner`, `LiveRoomRefreshManager`):

```python
# core/manager.py :: async_initialize
from ..mapping.map_source_coordinator import MapSourceCoordinator
self.map_source = MapSourceCoordinator(manager=self)
```

It uses `manager.hass`, writes its normalized result into `manager._map_state_source_cache`, and shares `manager._resolve_live_map_image_entity`. Everything brand-specific is in the adapter's `map_state_source` / `map_render` blocks; the coordinator only dispatches by the declared backend/format and never makes a brand assumption.

**Module:** `custom_components/eufy_vacuum/mapping/map_source_coordinator.py`
**Class:** `MapSourceCoordinator`

### 1.1 What it owns

- The pre-warm dispatcher (`async_refresh_map_state_source`) that fans out to the three backends and populates the manager cache off-loop.
- The three backend branches: **storage**, **memory-primary** (Eufy fork), and **memory introspect** (Roborock).
- The live-pose overlay path — layering the fork's fresh in-memory robot/dock/trail onto the static segmentation.
- The lightweight live-pose poll (`async_get_map_live_pose`), the verify probe (`async_compare_map_sources`), and the card own-render raster fetch (`async_get_map_render_data`).
- Its two backend-internal caches: `_mem_rooms_cache` (content-versioned static scan) and `_live_pose_geom_cache` (mtime-cached geometry).

### 1.2 What stays on the manager (and why)

Two seams deliberately remain on `core/manager.py` so the on-loop readers (and their tests) don't change:

- **`_map_state_source_cache`** — the pre-warm writes the normalized result here (`self._manager._map_state_source_cache[...]`), and two **synchronous on-loop** readers consume it directly: the dashboard-snapshot composer (`get_dashboard_snapshot`, the `map_state_source` snapshot key) and the map-overlays sensor (`sensor/map_overlays.py`). Keeping the cache on the manager means those readers never reach across into the subsystem. Value shape: `{"mtime": float|None, "present_gate": bool, "map_id": str, "result": <map_source result dict>}`.
- **`_resolve_live_map_image_entity`** — the live-map presence gate, *also* used by the snapshot composer for the live backdrop. Sharing it means the snapshot and the coordinator agree on "is the live map present?". The pre-warm calls it via `self._manager._resolve_live_map_image_entity`.

The coordinator's own caches (`_mem_rooms_cache`, `_live_pose_geom_cache`) live on the coordinator because only its own methods read them.

---

## 2. The three backends + the presence gate

The adapter declares a `map_state_source` block (see [25-eufy-adapter](25-eufy-adapter.md#map_state_source) for the Eufy values and [22-adapter-config-reference](22-adapter-config-reference.md#13a2-map_state_source--read-the-providers-own-map-segmentation) for the full schema). The `backend` key selects the branch; the optional `memory` block upgrades the `storage` backend to memory-primary.

### 2.1 The presence gate

Before any backend runs, `async_refresh_map_state_source` resolves the live-map image entity and computes `present`:

```python
live_img = self._manager._resolve_live_map_image_entity(
    vacuum_entity_id=vacuum_entity_id, map_id=map_id, adapter_cfg=adapter_cfg
)
present = (live_img is not None) if source_cfg.get(
    "present_requires_live_map_image", True
) else True
```

Most backends require the live-map artifact (the same gate as the live backdrop), so plain non-fork eufy-clean — which has no `camera.<device>_map` — resolves to *not present* and segmentation features hide, exactly like the model/CV presence gates. An adapter can opt out with `present_requires_live_map_image: False`. The resolved `live_img` is also handed to the Roborock introspector (the parsed `MapData` likely lives on that image entity object).

### 2.2 `storage` (and memory-primary)

Dispatched when `backend == "storage"`. Two sub-paths:

- **Memory-primary** — when the adapter declares a `memory` block (the Eufy fork holds the same `MapData` in memory, fresher + loop-safe). Runs `_refresh_eufy_map_source`, which **falls back to the `.storage` read** internally when the in-memory `MapData` is absent/malformed.
- **Plain `.storage`** — when there's no `memory` block (legacy / other forks). Runs `_refresh_storage_map_source`.

The `.storage` read (`map_source_runtime.load_store_json`) is blocking — it's a ~200 KB JSON + base64 decode — so it runs through `hass.async_add_executor_job` and is cached by file **mtime** (plus the presence gate): an unchanged map costs one `stat`, not a re-parse, on every snapshot.

### 2.3 `memory` (Roborock introspect)

Dispatched when `backend == "memory"`. Pure in-memory introspection (no IO, loop-safe). It collects candidate roots (`map_source_runtime.roborock_candidates` — config-entry `runtime_data`, `hass.data[domain]`, and the live image entity object) and resolves them via `roborock_result_from_candidates`, which BFS-walks for a `MapData`-like object (`.rooms` + `.image`) and projects each room's bbox through the parser's own `ImageDimensions.to_img(...).rotated(...)` transform. It **always** attaches a `diagnostics` breadcrumb (a bounded structure tree when nothing is found) for deploy-and-discover tuning.

### 2.4 Unknown backend / not configured / failure

Every miss degrades to an **absent marker** written to the cache so the on-loop snapshot never errors:

| Condition | `reason` |
|---|---|
| No `map_state_source` block | `not_configured` |
| `backend` unrecognized | `unknown_backend:<backend>` |
| Any unforeseen exception in dispatch | `refresh_error` |
| Storage: no resolvable device | `no_device` |
| Storage: version guard failed | `store_version_mismatch` (logs a warning) |
| Presence gate false | `live_map_absent` |

The whole dispatch is wrapped in a `try/except` — `async_refresh_map_state_source` **never raises** (it runs on the event loop inside the dashboard-snapshot service).

---

## 3. The four public readers

All four are `async`, keyword-only, adapter-driven, and degrade to an absent marker — never raise. `core/manager.py` keeps a 1-line delegator for each (e.g. `async_refresh_map_state_source` → `self.map_source.async_refresh_map_state_source(...)`), so existing call sites are unchanged.

### 3.1 `async_refresh_map_state_source`

```python
async_refresh_map_state_source(*, vacuum_entity_id: str, map_id: str) -> dict[str, Any]
```

Pre-warm: dispatches to the backend, applies the presence gate, and writes the normalized result into `manager._map_state_source_cache[vacuum_entity_id]`. Called from the dashboard-snapshot service handler **before** the synchronous snapshot, so the on-loop snapshot can include the result without doing the blocking `.storage` read itself. Returns the cached result dict (also handy for tests / a future sensor).

**Result shape (present):** `{present: True, backend, rooms: [{number, name, bbox, area_m2, width_m, height_m, ...}], image_size, current_room?, path?, robot_anchor?, dock_anchor?, robot_heading?, robot_docked?, walls?, no_go?, no_mop?, zones?, obstacles?}` — assembled by `map_source.build_map_source_result` + the live-pose overlay. Bboxes are normalized to 0–1 of the *rendered* image (top-left origin, Y-flip applied). `width_m`/`height_m` are the room's real-world box size in metres (Eufy derived from the map resolution, Roborock from the raw mm coordinates), used for per-room framing. Separately, the dashboard snapshot this pre-warms also carries a `furnished_render` key (resolved by `resolve_furnished_render` in `map_source.py` — the active custom layout's furnished art/transform/mode; see [data model](03-data-model.md)).

### 3.2 `async_get_map_live_pose`

```python
async_get_map_live_pose(*, vacuum_entity_id: str) -> dict[str, Any]
```

Returns **only the moving overlays** (robot/dock anchors + `current_room` + heading + live `path`) from the fork's fresh in-memory pose — the lightweight payload the card polls at the ~2s live cadence, vs the full snapshot. It reads the in-memory pose (`_read_inmem_pose`), loads the mtime-cached static geometry (`_load_live_pose_geom`) the normalization needs, and runs `map_source.live_pose_overlay`. Degrades to `{present: False, reason, diagnostics}`. (Used by the card *and* by the `_handle_get_map_live_pose` service and the server-side pose-sampler probe in `mapping/mapping_services.py`.)

### 3.3 `async_compare_map_sources`

```python
async_compare_map_sources(*, vacuum_entity_id: str) -> dict[str, Any]
```

Diagnostic **verify probe (P1)**: reads the fork's in-memory `_map_data` AND the `.storage` `map_data` and compares them field-by-field via `map_source.compare_map_data`, to confirm the in-memory bytes are byte-identical *before* repointing the source to memory. Returns `{in_memory_present, storage_present, diagnostics, compare?}`, where `compare` carries a per-field comparison (rasters by len+sha1) and a `normalization_safe` verdict over the geometry/raster fields the decoders use. Adapter-driven via `map_state_source.memory`; degrades to a marker on absence.

### 3.4 `async_get_map_render_data`

```python
async_get_map_render_data(*, vacuum_entity_id: str) -> dict[str, Any]
```

Returns the raster + decode params for the card's **own** map render (Wave 1). Adapter-driven: the adapter's `map_render.format` selects the decode (only `eufy_room_pixels_v1` today), and the **source pointer is reused from `map_state_source`** (no duplicate schema). Memory-primary again — when a `memory` block is declared it reads the fork's in-memory raster first (`render_data_from_storage`) and falls back to the off-loop `.storage` read (`eufy_render_data_from_store`). The card calls this on demand (when the VA-rendered backdrop is selected) and caches by the returned `version`; the raster is static (changes only on a re-map), so it's fetch-once, not snapshot bloat. Degrades to `{present: False, reason}`.

---

## 4. Caches: coordinator-internal vs manager-resident

There are **three** caches in play. Two are internal to the coordinator's backends; one stays on the manager for the on-loop readers (§1.2).

| Cache | Lives on | Keying / invalidation | Purpose |
|---|---|---|---|
| `_mem_rooms_cache` | coordinator | **content version** (sha1 of the raw room-pixel bytes, `map_source.eufy_version_of` / `eufy_mapdata_obj_from_candidates`) | Memory-primary static per-room scan + the converted `map_data` dict — re-runs the BFS scan + base64 convert only on a genuine **re-map**, not every refresh. |
| `_live_pose_geom_cache` | coordinator | **file mtime** | The static `map_data` geometry the live-pose normalization needs (loaded by `_load_live_pose_geom`); re-read only when the Store file changes. |
| `_map_state_source_cache` | **manager** | file **mtime** + **presence gate** (storage) / written fresh each refresh (memory) | The normalized backend result; written by the pre-warm, read **synchronously on the loop** by the snapshot composer and the map-overlays sensor. |

The `_mem_rooms_cache` entry holds `{version, result, map_data}`. On a cache hit the coordinator shallow-copies the cached `static` result and layers the **fresh** pose onto the copy — the static rooms scan is reused, only the moving pose changes each refresh, and the cached static stays clean of the moving fields.

---

## 5. The live-pose overlay path

The static segmentation comes from `.storage` (or the in-memory `MapData`), but the robot *position* there (`robot_trail[-1]`) lags the fork's save-throttle and is the stale "robot frozen in the kitchen" ghost. So both the storage and memory backends layer the fork's fresh in-memory pose on top:

1. `_read_inmem_pose` finds the pose **holder** (the object carrying both a robot- and a dock-pixel attr, matched by **presence** because the fork *nulls* `_robot_pixel` while docked) via `map_source_runtime.eufy_live_pose_from_candidates`, and reads robot pixel (None when docked), dock pixel, trail, and heading off it.
2. `_apply_inmem_pose_to_result` builds the overlay (`map_source.live_pose_overlay`) and merges it with `map_source.apply_live_pose_override`, which **clears the live-pose-owned keys** (`current_room`, `path`) before merging so a stale `.storage` value can't survive next to a fresh dock anchor.

Docked semantics: when the robot pixel is absent but a dock pixel resolves, the robot anchor resolves *to the dock* and `robot_docked` is flagged — mirroring the fork's own render and killing the stale-pose ghost. The whole override is defensive (a raising provider-internal property degrades to the base overlays rather than aborting the on-loop snapshot).

> The Eufy fork exposes the pose on `hass.data["robovac_mqtt"][<entry>]["coordinators"][0]` (an `EufyCleanCoordinator`): `_robot_pixel` (nulled while docked), `_dock_pixel`, `_robot_trail`. There is **no** in-memory heading attr (the fork bakes orientation into the rendered bytes); `heading_attrs` is kept future-proof but matches nothing today. See the adapter's `live_pose` block in [25-eufy-adapter](25-eufy-adapter.md#map_state_source).

---

## 6. Call sites + the manager seam

| Caller | Path | Reads/writes |
|---|---|---|
| Dashboard-snapshot service handler | `services/snapshots.py` → `manager.async_refresh_map_state_source` (pre-warm), then `get_dashboard_snapshot` reads the `map_state_source` cache key on-loop | writes + reads `_map_state_source_cache` |
| Map-overlays sensor | `sensor/map_overlays.py` (`_result()` reads `manager._map_state_source_cache`) | reads `_map_state_source_cache` |
| `get_map_render_data` service | `mapping/mapping_services.py::_handle_get_map_render_data` → `manager.async_get_map_render_data` | — |
| `get_map_live_pose` service + pose-sampler probe | `mapping/mapping_services.py::_handle_get_map_live_pose` → `manager.async_get_map_live_pose` | — |
| `compare_map_sources` service | `mapping/mapping_services.py::_handle_compare_map_sources` → `manager.async_compare_map_sources` | — |
| Snapshot `supports_va_render` flag | `core/manager.py::get_dashboard_snapshot` gates on `isinstance(adapter_cfg.get("map_render"), dict)` | — |

The manager's four delegators (`async_refresh_map_state_source`, `async_get_map_live_pose`, `async_compare_map_sources`, `async_get_map_render_data`) are thin 1-line forwards to `self.map_source.*`. The cache and `_resolve_live_map_image_entity` stay on the manager (§1.2) — that is the deliberate boundary of this re-bundle, not an oversight.

---

## 7. Cross-links

- [11-mapping-system](11-mapping-system.md) — the CV segmentor, image variants, trace-bounds path, and the map bucket this subsystem is distinct from.
- [map-state-source](map-state-source.md) — the **design** doc for the seam (goal, brand reality, wave plan, the pure-vs-runtime split). This doc is the implementation reference for the coordinator; that one is the rationale.
- [22-adapter-config-reference](22-adapter-config-reference.md#13a2-map_state_source--read-the-providers-own-map-segmentation) — the `map_state_source` / [`map_render`](22-adapter-config-reference.md#13a3-map_render--va-owned-client-side-map-render) adapter-config schema (backend, identifier_domain, store_key, store_version, presence gate, `live_pose`, `memory`, render `format`).
- [25-eufy-adapter](25-eufy-adapter.md#map_state_source) — the Eufy adapter's concrete `map_state_source` / `map_render` values (storage backend, `live_pose` attr paths, the in-memory `MapData` source).
- [26-eufy-segmentor](26-eufy-segmentor.md) — the CV segmentor (inferred rooms from an uploaded image), the *other* source of room geometry this one is contrasted with.
