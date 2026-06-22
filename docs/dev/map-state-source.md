# Map State Source — Auto-Derived Room Data

**Status:** design approved 2026-06-18. **Wave 1 COMPLETE + LIVE-VERIFIED on both brands
(2026-06-19).** Eufy (storage backend) returns 10 rooms + dock/robot anchors, presence-gated on
the live-map camera. Roborock (memory backend) returns 10 rooms with normalized bboxes, read from
the parsed `MapData` on the map image entity (`_home_trait._map_content.map_data`) and projected via
the parser's own `ImageDimensions.to_img(...).rotated(...)` transform (the live transform was
verified exact by hand against the raw room coords). No consumer wiring yet (Wave 3). No fork
changes required.

### Roborock specifics (learned at runtime, 2026-06-19)

- Parsed geometry is NOT on the coordinator (`runtime_data` carries only id→name metadata) — it
  lives on the **map image entity**: `image.<id> → _home_trait._map_content.map_data` (the newer
  python-roborock-traits build; older stable HA discards it and would need a
  `cloud_api.get_map_v1()` re-fetch+parse — not required here).
- `map_data.rooms` is `dict[int, Room]`; `Room.x0..y1` are **vacuum coords (~50× the pixel grid)**,
  so they MUST be projected via `image.dimensions.to_img(point).rotated(dims)` and normalized by
  `image.data.size` (the rendered size = `dims.width/height × scale`). Reader **calls** that
  transform (via a lightweight `_XY` point shim) rather than reimplementing it.
- The reader targets an object with BOTH `.rooms` and `.image` (a `MapData`) — never a generic
  x0/y0/x1/y1 collection, because `no_go_areas`/walls/zones are rectangles too.
- `Room.name`/`pos_x`/`pos_y` are `None` for Roborock → names fall back to `Room {number}`; the
  `number` is the segment id, reconciled to real names in Wave 3.

## Implementation map (Wave 1)

| Piece | Where |
|---|---|
| Pure reader core (extraction/normalization, HA-free) | `mapping/map_source.py` (13 tests) |
| Runtime locators (Eufy `.storage` read; Roborock introspector) | `mapping/map_source_runtime.py` (13 tests) |
| Async pre-warm + cache + snapshot field | `mapping/map_source_coordinator.py` `MapSourceCoordinator.async_refresh_map_state_source` / `_refresh_storage_map_source` / `_refresh_eufy_map_source` (constructed as `self.map_source = MapSourceCoordinator(manager=self)` in `core/manager.py` `async_initialize`); `core/manager.py` keeps thin 1-line delegators plus `_map_state_source_cache` and `_resolve_live_map_image_entity`; snapshot key `map_state_source` |
| Pre-warm call site (off-loop IO before the on-loop sync snapshot) | `services/snapshots.py` `_handle_get_dashboard_snapshot` |
| Adapter config blocks | `adapters/eufy/adapter.py` + `adapters/roborock/adapter.py` `map_state_source` |

The Eufy `.storage` read is BLOCKING (200 KB + base64), so it runs in an executor inside the
async pre-warm and is cached by file-mtime — the on-loop sync snapshot only reads the cache. The
Roborock introspect is in-memory (loop-safe). Both degrade to `{present: false, reason}` and never
raise.

## Goal

Read the **provider's own map segmentation** (the device's authoritative room data — not bounds
learned from drifting robot samples) to auto-derive, brand-general:

- room **select-regions** (the tap-targets you currently hand-compose) — the headline win,
- room **bounds** + exact **current-room** membership,
- **dock** + **robot** anchors (for mascots),
- zone **m²**.

This removes the manual room-compose step. All decode/coupling cost lives on the dev side; the
user gets it for free. The drift investigation (see `reference_eufy_intersession_coord_drift`)
established that the stable, authoritative segmentation already exists in the provider — we just
have to read it instead of inferring it.

## The seam

One VA-owned **reader**, driven by a per-adapter **`map_state_source`** pointer, publishes
normalized map data into the dashboard snapshot. Consumers (select-box auto-gen, current-room,
mascot, bounds review, zone m²) read the **VA's** output — never the provider directly. All
provider coupling is isolated to one adapter-configured reader.

## Brand reality (why a pointer, not a hardcode)

| | Eufy (smcneece fork) | Roborock (HA core) |
|---|---|---|
| Source | `.storage/robovac_mqtt.<id>` (**decoded on disk**) | in-memory coordinator `MapData` |
| Per-room bbox | from `room_pixels` extents | parser `Room.x0..y1` (**direct**) |
| Exact outline | `room_pixels` raster (**free, L-exact**) | reconstruct (color-seg render / re-parse segment layer) |
| Offline-readable | yes (proven) | no (geometry is in HA memory) |

The Eufy fork is unusually generous (persists decoded `room_pixels`); Roborock keeps geometry
in-memory. Hence a per-adapter pointer that supports **storage** and **memory** backends.

## Adapter config contract (`map_state_source`)

```yaml
map_state_source:
  backend: storage | memory
  present_when: <gate predicate>          # see Presence gate
  # storage backend (Eufy):
  store_key: "robovac_mqtt.{device_id}"
  store_version: 1                         # guard; mismatch -> unavailable
  fields:
    segmentation: map_data.room_pixels
    origin:       map_data.origin_x/origin_y
    resolution:   map_data.resolution
    dims:         map_data.width/height
    room_names:   map_data.room_names
    robot:        robot_trail[-1]
    dock:         dock_pixel
  # memory backend (Roborock):
  hass_data_domain: roborock
  locate: <how to find the coordinator for this vacuum>
  fields:
    rooms:  "MapData.rooms[] -> x0,y0,x1,y1,number,name"
    image:  "..."
    robot/charger: "..."
```

## Presence gate (the unifier)

Each backend is **active only when its source artifact is present** — the *same* capability-by-
presence mechanism the VA already uses (`cv_available`, `supports_map_bounds`, …):

- **Eufy:** active iff the camera/map artifact exists (`camera.<device>_map` resolved **and**
  `.storage` `map_data` present). Plain non-fork Eufy → inactive → segmentation features hide.
- **Roborock:** active iff `hass.data["roborock"]` coordinator + a parsed `MapData` exist.
- **Future models:** declare their own `present_when`. Core just asks "is the source present?" —
  degrade to `unavailable`/hidden when not, never crash.

## Reader output (VA-owned, normalized)

Per room: `{number, name, bbox (normalized 0–1), polygon (when available), label_pos, width_m,
height_m (real-world box size in metres — Eufy res-derived, Roborock mm-derived)}`; plus
`current_room` (pixel/segment lookup), `dock_anchor`, `robot_anchor` (normalized). Published as
snapshot fields (sensors optional later).

## Wave 3a — full overlay extraction (built 2026-06-19)

The reader now extracts the device's other authoritative map layers, all in the SAME normalized
space, so the card can OVERLAY them on the device-rendered backdrop (never our own render):

- **Both:** per-room `area_m2`, `current_room` (Eufy = exact pixel lookup; Roborock = `vacuum_room`),
  robot `path` (decimated), `dock_anchor`/`robot_anchor`.
- **Roborock also:** `robot_heading`, `no_go`/`no_mop` (4-pt polygons), `walls` (segments), `zones`
  (rects), `obstacles` (`{pos,type,has_photo}`) — all via the shared `_mapdata_projector`.
- **Eufy hazards** (`forbidden_zones`/`ban_mop_zones`/`virtual_walls`) are DEFERRED — empty on the
  live device, so their populated coordinate frame is unverified; wired when a live map carries them.

## Wave 3b — visibility toggles + sensor mirror (built 2026-06-19)

- **Per-layout visibility** — 11 toggleable layers with defaults (Navigation + room labels/area
  ON; hazards/activity OFF). `OVERLAY_VISIBILITY_DEFAULTS` + `resolve_overlay_visibility(stored)`
  in `map_source.py`; only the user's DELTAS are stored (`overlay_visibility` on the map bucket),
  merged over defaults at read time so defaults can evolve.
- **Service** `eufy_vacuum.set_map_overlay_visibility` (vacuum_entity_id, map_id, partial
  `visibility` map, or `reset:true`) — schema rejects unknown layer keys; returns the resolved map.
- **Snapshot** carries `map_overlay_visibility` (resolved), independent of map_state_source presence.
- **Sensor** `sensor.<vac>_map_overlays`: state = current room name (recorded → room timeline);
  attributes mirror the overlay layers + visibility for automations/templates. `path` omitted; the
  verbose layers are recorder-excluded. Refreshed by a 60 s platform timer + every snapshot fetch.
- **Path hard-cap** — `_decimate_step` (ceil stride) truly caps sampled polylines.

## Wave 3c — card rendering + toggle UI (built 2026-06-19)

The card draws the overlay layers over the **live** backdrop and a "Map Layers" panel toggles
them. Additive only — existing room regions / mascots / labels are untouched.

- **Renderer** (`src/renderers/map.js`): `_renderDeviceOverlaySvg` (current-room rect, no-go/no-mop
  polygons, zones, walls, path) + `_renderDeviceOverlayHtml` (robot dot + heading arrow, dock,
  obstacle markers, m² area chips), inside the rotator so they turn with the map.
- **Letterbox correction** (`_overlayTransform`): overlays are normalized to the IMAGE frame, but
  the live `<img>` is `object-fit:contain` in a SQUARE box — so coords are mapped image→container
  using `image_size` (now in `map_state_source`) and the SAME math as the zone path
  (`state._rectToNormalized`, inverted). Without this every layer drifts on a non-square map.
- **Gate**: `state.isLiveImageDisplayed()` — overlays render only when the live device image is the
  displayed backdrop (Roborock always; Eufy when on the live source, not the CV image).
- **Toggle panel** (`_renderMapLayersPanel`, side column) → `set_map_overlay_visibility`, with an
  optimistic flip that rolls back on service failure.
- **Theming**: `--evcc-map-ov-*` tokens (no hardcoded colors).

Reviewed via a multi-agent adversarial pass (13 raised → 4 confirmed → fixed: the letterbox
mismatch, the optimistic-rollback gap, + `image_size` plumbing). Deferred (pre-existing, low):
live-map rotation is gated on `hasLiveImage` not `isLiveImageDisplayed`.

## Self-render (client-side canvas) — Wave 1 (built 2026-06-19)

The card draws its OWN full-grid map backdrop from the device's room raster — no server
dependency (no Pillow). The VA owns the frame, so the overlays align perfectly (no
fork-camera crop). Adapter-driven, brand-agnostic core + card.

- **Adapter:** a `map_render: {format}` block declares the decode format (Eufy
  `eufy_room_pixels_v1`) and **reuses the `map_state_source` store pointer** (no duplicate
  schema). Roborock omits it → `supports_va_render: false` → the card hides the toggle (its
  HA-core render is already frame-matched).
- **Service** `get_map_render_data` → `manager.async_get_map_render_data` (a thin delegator to
  `MapSourceCoordinator.async_get_map_render_data` in `mapping/map_source_coordinator.py`)
  dispatches by `map_render.format`, executor-reads `.storage`, returns the raster (`room_pixels`
  b64) +
  **explicit decode params** (dims, `ro_dx/dy`, `flip_y`, `rid_shift`, `catch_all_rid`,
  `room_names`, `version`) — so the card decodes with **no brand assumptions**.
- **Card:** a `<canvas>` backdrop (same `object-fit:contain` as the live `<img>`, so it
  letterboxes identically and the overlays align via `image_size`); a per-vacuum toolbar
  toggle; fetch-once-cached-by-version; the decode is memoized by version. The overlay +
  panel gate generalizes to `overlaysAligned()` = live image **or** VA render.
- Reviewed (19 raised → 4 confirmed, all low → fixed: ImageData memoization, the
  loading/fallback empty-state, the failed-fetch sentinel).
- **Wave 1 = rooms only** (`room_pixels`). Walls/floor (`raw_pixels` — different encoding),
  themed graph-coloring, and the in-memory live-pose re-render (kills the dynamic lag) are
  later waves.

## Waves (each shippable, gated, additive — not a rewrite)

1. **Reader + both backends + presence gate.** Output: per-room **bbox + names**. **No consumer
   wiring** — expose + verify only.
   - Eufy backend: build now (storage shape proven).
   - Roborock backend: starts as a **defensive runtime introspector** (walks `hass.data["roborock"]`,
     finds the parsed `MapData`, dumps rooms bbox+name to log/snapshot) — because the exact
     `hass.data` structure isn't knowable offline. This *is* the live Roborock test; tune the access
     path from what it finds.
2. **Exact polygons.** Eufy: contour-trace `room_pixels` (L-exact). Roborock: reconstruct (color-seg
   render or re-parse segment layer).
3. **Wire consumers.** Auto-gen select-regions (replace manual compose) → tap → room number/id →
   native clean; current-room (replace bbox/sample membership); mascot follow/dock; bounds-review
   replacement; zone m².

## Defensive contract

Adapter-config paths (re-point, don't rewrite, when the fork schema shifts at #136); Store-`version`
guard; degrade-to-`unavailable` on any mismatch; brand-agnostic core, coupling only in adapter +
reader.

## Risks

- Schema coupling to provider internals (Eufy storage shape — esp. the #136 merge; Roborock
  in-memory attrs). Contained by the adapter pointer + defensive parse + presence gate.
- Roborock exactness needs a reconstruction step (color-seg / re-parse) — dev cost, not user cost.
- Roborock backend can't be verified offline — W1 introspector confirms it at runtime.
