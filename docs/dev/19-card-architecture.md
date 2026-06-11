# Card Architecture Reference

This document defines the backend as a **contract**, not just a description of the current card. Everything in section 1 — the services, events, and entities — is what any UI must consume to drive a eufy_vacuum installation. Sections 2–6 describe the current card's implementation of that contract, then explain how to extend it.

---

## 1. The Backend Contract

### 1.1 HA Services

All services live in the `eufy_vacuum` domain. Call them via `hass.callService(domain, service, data, target?, notifyOnError?, returnResponse?)`. Services marked **response** must be called with `returnResponse = true`; the result lives at `result.response`.

#### State queries (read-only, response)

| Service | Required fields | What it returns |
|---|---|---|
| `get_start_status` | `vacuum_entity_id`, `map_id` | Pre-flight eligibility, blocking flags, preflight payload |
| `get_dashboard_snapshot` | `vacuum_entity_id`, `map_id` | Full card read model: job control, queue, room list, learning state |
| `get_dock_action_status` | `vacuum_entity_id`, `map_id` | Dock action availability (wash/dry/empty), active action flags |
| `get_pause_timeout_settings` | `vacuum_entity_id` | Configured pause-timeout duration |
| `get_lifecycle_state` | `vacuum_entity_id` | Raw lifecycle state dict |
| `get_job_progress_snapshot` | `vacuum_entity_id` | In-progress job room/timing snapshot |
| `get_job_control_state` | `vacuum_entity_id` | Active job + queue combined state |
| `get_upkeep_snapshot` | `vacuum_entity_id` | Maintenance intervals and remaining hours |
| `get_queue_state` | `vacuum_entity_id`, `map_id` | Raw queue content |
| `get_payload_state` | `vacuum_entity_id`, `map_id` | Raw room payload |
| `get_active_job` | `vacuum_entity_id` | Active job dict |
| `get_vacuum_capabilities` | `vacuum_entity_id` | Hardware capability flags (water level, edge mopping, etc.) |
| `get_vacuum_maps` | `vacuum_entity_id` | Registered maps for the vacuum |

#### Job control (side-effecting)

| Service | Required fields | Notes |
|---|---|---|
| `start_selected_rooms` | `vacuum_entity_id`, `map_id` | Optional: `confirm_reduced_run`, `confirm_token`. Do **not** call with `returnResponse = true` |
| `pause_active_job` | `vacuum_entity_id` | |
| `resume_active_job` | `vacuum_entity_id` | |
| `cancel_active_job` | `vacuum_entity_id` | |
| `vacuum.return_to_base` | `entity_id` (HA vacuum entity) | Standard HA vacuum service — not in eufy_vacuum domain |
| `clear_queue` | `vacuum_entity_id` | Optional: `map_id` (defaults to active map). Clears the pending run queue without stopping a running job |
| `clear_active_job` | `vacuum_entity_id` | |

#### Room management

| Service | Required fields | Notes |
|---|---|---|
| `update_room_fields` | `vacuum_entity_id`, `map_id`, `room_id` | Optional: `enabled`, `clean_mode`, `fan_speed`, `clean_intensity`, `clean_passes`, `water_level`, `edge_mopping`, `is_transition`, `grants_access_to`, `is_dock_room`, `rules`. Omit null optional fields — HA schema rejects them |
| `discover_rooms` | `vacuum_entity_id` | Interrogates the vacuum for the current room list |
| `save_managed_rooms` | `vacuum_entity_id` | Persists discovered rooms into integration storage |
| `get_room_access_editor` | `vacuum_entity_id`, `map_id` | Returns room access graph for editing |
| `get_access_graph_health` | `vacuum_entity_id`, `map_id` | Validates access graph integrity |

Room enabled/disabled state is stored in HA **switch entities** (one per room per map per vacuum). Toggle by calling `homeassistant.turn_on` / `homeassistant.turn_off` with the switch entity ID. Room ordering is stored in HA **number entities** (one per room per map per vacuum). Update by calling `number.set_value`.

#### Queue

| Service | Required fields |
|---|---|
| `build_queue` | `vacuum_entity_id`, `map_id` |
| `build_room_payload` | `vacuum_entity_id`, `map_id` |

#### Learning system

| Service | Required fields | Notes |
|---|---|---|
| `run_learning_estimate` | `vacuum_entity_id`, `map_id`, `current_battery` | Optional: `started_at` (omit for pre-start calls). Returns time estimates per room |
| `reanchor_learning_timeline` | `original_estimate`, `completed_rooms`, `reanchor_at` | Optional: `current_battery`. Recomputes remaining ETAs mid-job |
| `get_next_room` | `reanchored_estimate` | Resolves which room is next from the reanchored estimate |
| `get_room_learning_estimates` | `vacuum_entity_id`, `map_id` | Per-room estimates independent of queue state |
| `get_learning_history_snapshot` | `vacuum_entity_id` | Optional: `room_slug`, `profile_key`, `status`, `used_for_learning`, `limit` |
| `get_metrics_snapshot` | `vacuum_entity_id` | Optional: `room_slug`, `profile_key`, `status`, `used_for_learning` |
| `get_incomplete_run_log` | `vacuum_entity_id` | Last cancelled/failed/interrupted job. Returns null-equivalent `{}` when no log exists |
| `get_trouble_rooms_log` | `vacuum_entity_id` | Chronic trouble rooms. Returns null-equivalent `{}` when no log exists |
| `save_learning_snapshot` | `vacuum_entity_id` | |
| `finalize_learning_job` | `vacuum_entity_id` | Called when a job ends; triggers `eufy_vacuum_run_incomplete` event when rooms were missed |
| `rebuild_learning_stats` | `vacuum_entity_id` | |
| `exclude_learning_job` | `vacuum_entity_id`, `job_id` | Optional: `reason`, `rebuild_csv` |
| `restore_learning_job` | `vacuum_entity_id`, `job_id` | Optional: `rebuild_csv` |

#### Dock (base station)

| Service | Required fields |
|---|---|
| `wash_mop` | `vacuum_entity_id`, `map_id` |
| `dry_mop` | `vacuum_entity_id`, `map_id` |
| `stop_dry_mop` | `vacuum_entity_id`, `map_id` |
| `empty_dust` | `vacuum_entity_id`, `map_id` |
| `reset_maintenance` | `vacuum_entity_id` |
| `set_dock_event_count` | `vacuum_entity_id` |
| `set_pause_timeout_settings` | `vacuum_entity_id`, `pause_timeout_minutes_default` |

#### Profiles (room and run)

| Service | Required fields | Notes |
|---|---|---|
| `get_room_profiles` | _(none)_ | Global profile library |
| `save_user_room_profile` | _(payload)_ | |
| `save_room_profile_from_room` | `vacuum_entity_id`, `map_id`, `room_id`, `label` | Optional: `profile_name` |
| `overwrite_room_profile` | _(payload)_ | |
| `overwrite_room_profile_from_room` | `vacuum_entity_id`, `map_id`, `room_id`, `profile_name` | Optional: `label` |
| `rename_room_profile` | `profile_name` | Optional: `new_profile_name`, `label` |
| `delete_room_profile` | `profile_name` | |
| `apply_room_profile` | `vacuum_entity_id`, `map_id`, `room_ids`, `profile_name` | |
| `get_saved_run_profiles` | `vacuum_entity_id`, `map_id` | |
| `save_run_profile` | `vacuum_entity_id`, `map_id`, `name` | Optional: `expose_as_button` |
| `overwrite_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | Optional: `name`, `expose_as_button` |
| `apply_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | Restores saved room selection and settings |
| `rename_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id`, `name` | |
| `delete_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | |
| `start_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | |

#### Theme

| Service | Notes |
|---|---|
| `get_theme_library` | Returns full library of saved themes and working draft |
| `set_active_theme` | `theme_id`; optional `vacuum_entity_id` |
| `update_working_draft` | `vacuum_entity_id`; optional `tokens`, `colors`, `alpha` |
| `revert_draft` | `vacuum_entity_id` |
| `save_theme_as_new` | `vacuum_entity_id`, `name`; optional `set_as_default` |
| `overwrite_theme` | `vacuum_entity_id`, `theme_id` |
| `rename_theme` | `theme_id`, `name` |
| `delete_theme` | `theme_id` |
| `export_theme` | `theme_id` |
| `import_theme` | `payload` |

#### Setup

| Service | Notes |
|---|---|
| `setup_get_status` | Returns vacuum list and map import state |
| `setup_add_vacuum` | `vacuum_entity_id` |
| `setup_import_active_map` | `vacuum_entity_id` |
| `setup_get_map_rooms` | `vacuum_entity_id`, `map_id` |
| `setup_save_rooms` | `vacuum_entity_id`, `map_id`, `enabled_room_ids`, `floor_types` |
| `setup_delete_map` | `vacuum_entity_id`, `map_id`; optional `confirmation_token` (required for high-protection maps) |

#### Mapping / map image

| Service | Notes |
|---|---|
| `upload_map_image` | `vacuum_entity_id`, `map_id`, `image_base64` |
| `analyze_map_image` | `vacuum_entity_id`, `map_id` |
| `get_map_segments` | `vacuum_entity_id`, `map_id` |
| `adjust_map_segment` | `vacuum_entity_id`, `map_id`, `segment_id`, adjustment fields |
| `get_room_bounds_snapshot` | `vacuum_entity_id`, `map_id` |
| `clear_room_bounds` | `vacuum_entity_id`, `map_id`, `room_id` |
| `exclude_room_job_bounds` | `vacuum_entity_id`, `map_id`, `room_id`, `job_index` |
| `restore_room_job_bounds` | `vacuum_entity_id`, `map_id`, `room_id`, `job_index` |
| `rebuild_room_bounds_from_archive` | `vacuum_entity_id`, `map_id`, `room_id` |

---

### 1.2 HA Events

Subscribe via `hass.connection.subscribeEvents(callback, eventType)`.

| Event type | Payload fields | When it fires |
|---|---|---|
| `eufy_vacuum_job_finished` | `vacuum_entity_id`, job summary fields | Job reaches a terminal state |
| `eufy_vacuum_room_started` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name` | Robot enters a room |
| `eufy_vacuum_room_finished` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, timing fields | Robot finishes a room |
| `eufy_vacuum_path_blocked` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name` | Blockage detected during cleaning |
| `eufy_vacuum_stall_detected` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` | Robot has been in a room >= 2x its learned threshold with `awaiting_bounds_exit = true`. Fires at most once per room per job |
| `eufy_vacuum_run_incomplete` | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids` (list of int), `missed_rooms` (list of `{room_id, name}`) | Fired by `finalize_learning_job` when a cancelled/failed/interrupted job left uncleaned rooms |

---

### 1.3 HA Entities the UI reads

Entity IDs are derived from the vacuum's `object_id` (the part after the dot in `vacuum.alfred` → `alfred`).

#### Vacuum entity

The primary vacuum entity (`vacuum.{object_id}`) is the core state source:

- `state` — `cleaning`, `docked`, `returning`, `paused`, `error`, `idle`
- `attributes.battery_level` — integer 0–100
- `attributes.friendly_name` — display name

#### Switch entities (room enabled/disabled)

The integration creates one switch per room per map: `switch.{object_id}_{map_slug}_{room_slug}`. The switch's `on`/`off` state is the room's enabled flag. Switch `extra_state_attributes` carry all room settings:

```
vacuum_entity_id, map_id, room_id, room_name, slug,
order, profile_name, clean_mode, fan_speed, water_level,
clean_intensity, clean_passes, edge_mopping, floor_type,
carpet, grants_access_to, is_dock_room, rules
```

The card discovers room switches by scanning `hass.states` for entities whose attributes contain `vacuum_entity_id` matching the configured vacuum. It does not rely on a fixed naming pattern.

#### Number entities (room order)

The integration creates one number entity per room per map: `number.{object_id}_{map_slug}_{room_slug}_order`. The integer state is the room's 1-based sort position. Write by calling `number.set_value`.

#### Sensor entities

| Entity ID pattern | `state` | Key `attributes` |
|---|---|---|
| `sensor.{object_id}_theme_state` | Theme ID string | `vacuum_entity_id`, active theme tokens + colors + alpha, working draft overrides, `draft_dirty` flag |
| `sensor.{object_id}_active_map` | Active map ID | Map metadata |
| `sensor.{object_id}_available_profiles` | Profile count | Available profile definitions |
| `sensor.{object_id}_dock_events` | Event count | Dock event history |
| `sensor.{object_id}_robot_position_x_raw` | X coordinate (int) | Raw robot X position |
| `sensor.{object_id}_robot_position_y_raw` | Y coordinate (int) | Raw robot Y position |
| `sensor.{object_id}_{component}_remaining` | Hours remaining | Per-component maintenance sensor (one per maintenance component) |

Per-room sensors are also registered at setup:
- `sensor.{object_id}_{map_slug}_{room_slug}_cleaning_history` — room-level cleaning history
- `sensor.{object_id}_{map_slug}_{room_slug}_rule_status` — room rule evaluation status

#### Theme sensor attributes (detailed)

The `sensor.{object_id}_theme_state` entity is the backend's source of truth for all theme state. On every HA update its attributes should be mirrored into your UI's theme state. Key attribute fields:

- `vacuum_entity_id` — confirms this sensor belongs to a specific vacuum
- `active_theme_id` — the currently applied theme
- `working_draft` — dict of token/color/alpha overrides being edited
- `draft_dirty` — boolean; true when the draft differs from the saved theme
- Token, color, and alpha maps for the active theme

---

## 2. Current Card Implementation — The Mixin Pattern

### 2.1 Why prototype mixins rather than a component framework

The card is a single Web Component (`<eufy-vacuum-command-center>`) registered with `customElements.define`. There is no virtual DOM, no JSX, no component tree. Everything renders into one shadow root.

This creates a constraint: the card has one update entry point (`hass` setter), one render function, one DOM tree. A traditional component-per-view architecture would require either multiple shadow roots (expensive, CSS-isolation-breaking) or complex state passing between component instances. Prototype mixins solve this by adding methods directly onto the class prototypes of four collaborating objects — keeping the namespace flat, avoiding import coupling between domains, and making the call surface trivial to test in isolation.

A mixin is applied with a function that mutates a prototype:

```js
export function applyFooActions(proto) {
  proto.doFoo = async function() { ... };
}
// Called once at module load:
applyFooActions(VacuumCardActions.prototype);
```

This means all domain methods (`dock`, `rooms`, `theme`, `learning`, etc.) appear on a single object but are authored in separate files with no cross-imports between domains.

### 2.2 The four layers

```
actions           state             renderers         bindings
─────────────     ─────────────     ─────────────     ─────────────
VacuumCard        VacuumCard        VacuumCard        VacuumCard
Actions           State             Renderers         Bindings

Service calls     In-memory data    HTML strings      DOM events
to the backend.   derived from      generated from    that call
No DOM.           hass.states and   state. No side    actions or
No state.         service results.  effects.          update state.
                  No DOM.
```

**Actions** (`src/actions/`) — all `hass.callService` calls live here. No method may touch the DOM or mutate state except by returning data that the caller (main.js) stores into state.

**State** (`src/state/`) — holds two kinds of data. The first is derived from `hass.states` (vacuum entity, switch entities, number entities, sensor attributes). The second is transient UI state stored as plain properties on the instance (e.g. `_startStatus`, `_dockActionStatus`, editor open/close flags). State modules expose read methods; main.js writes to them by calling named setters or assigning directly to well-known properties.

**Renderers** (`src/renderers/`) — pure functions that take the render context object and return HTML strings. They read from state but never write to it and never call services.

**Bindings** (`src/bindings/`) — called after every render. They query the shadow DOM for data-attribute selectors and attach event handlers. Event handlers call actions or state mutators, then call `_scheduleRender()`.

**A fifth object — the controller.** Beyond the four render-cycle layers, `LearningController` (`src/controllers/learning-controller.js`, instantiated in `main.js` and driven by `connectedCallback` / `disconnectedCallback`) centralizes the event-driven live-job logic: it owns the HA event subscriptions (room started/finished, job finished), ETA reanchoring, bounds-exit polling, and the live job-progress ticker. The `learning` state module holds the data; the controller drives the updates.

### 2.3 Strict data flow

```
hass setter → state.sync() → _scheduleRender()
                                    ↓
                            _render() builds ctx
                                    ↓
                         renderers read state → HTML string
                                    ↓
                         innerHTML set on view root
                                    ↓
                         bindings.bindEvents() attaches handlers
                                    ↓
user action → binding handler → action.callService() + state mutator → _scheduleRender()
```

State modules never call each other. If module A needs data that module B owns, it goes through the card instance, which owns all four layer objects. This is explicit in every action and binding: they reference `this.card._state`, `this.card._actions`, etc.

---

## 3. Render Cycle

### 3.1 `_scheduleRender`: microtask, not `setTimeout`

```js
_scheduleRender() {
  if (this._renderScheduled) return;
  this._renderScheduled = true;
  Promise.resolve().then(() => {
    this._renderScheduled = false;
    this._render();
  });
}
```

Using `Promise.resolve()` schedules the render as a **microtask** — it runs at the end of the current synchronous turn of the event loop, before the browser paints, and crucially before any `setTimeout(fn, 0)` callbacks. This means multiple synchronous calls to `_scheduleRender()` (e.g. from a state setter and a hass setter both firing in the same turn) coalesce into a single render. The flag `_renderScheduled` is the deduplication guard.

A separate `_scheduleDeferredRender()` method exists for the theme editor, where color pickers and text inputs fire events at high frequency during user gestures. It uses a 600 ms debounce via `setTimeout` so the expensive full re-render only fires after the user pauses.

### 3.2 Full re-render and re-bind on every cycle

Every `_render()` call:
1. Calls `applyThemeToCard(this)` to ensure CSS custom properties are current.
2. Builds a fresh render context object.
3. Snapshots current focus and scroll state within the shadow root.
4. Calls `renderHeader(ctx)` and `renderView(ctx)` to produce HTML strings.
5. Compares each output against a `dataset.renderedHtml` cache stamp on the target container — writes `innerHTML` only if the string changed.
6. Calls `_updateModalHost()` for the document-body-appended modal overlay.
7. Calls `bindings.bindEvents()` to re-attach all event handlers.
8. Restores the captured focus and scroll state.

The HTML comparison (step 5) prevents unnecessary DOM churn on unchanged panels. Without it, every `hass` push would clear and rewrite the full DOM even if nothing visible changed.

Because `innerHTML` is replaced on change, **all previously attached DOM event listeners are discarded**. `bindEvents()` must re-attach everything from scratch on every render. This is intentional — it makes the binding layer stateless.

### 3.3 Why `dblclick` is unreliable: the 220 ms click disambiguation timer

A double-click involves two click events. Between them, `_scheduleRender()` fires (triggered by the first click changing state). The render replaces `innerHTML`, which detaches the element that received the first click. The second click either fires on nothing or on a freshly-attached clone that has no double-click handler.

The solution used in the card is a **220 ms single-click disambiguation timer**: on the first click, start a timer. If a second click arrives within 220 ms, treat the pair as a double-click and cancel the timer. If 220 ms passes with no second click, execute the single-click action. This keeps the DOM stable between the two clicks.

### 3.4 The VIEWS enum and view routing

```js
export const VIEWS = {
  ROOMS:           "rooms",
  MAINTENANCE:     "maintenance",
  BASE_STATION:    "base_station",
  METRICS:         "metrics",
  LEARNING_REVIEW: "learning_review",
  ROOM_RULES:      "room_rules",
  THEME:           "theme",
  MAPPING_ARCHIVE: "mapping",   // not a real view — setView() redirects to ROOMS
  MAP_CONFIG:      "map_config",
  MAPPING_REVIEW:  "mapping_review",
  SETUP:           "setup",
};
```

`VIEW_ORDER` is the array used to pre-create view root divs in the shell frame. Each view gets its own `<div data-evcc-view-root="{viewName}">` inside the view stage. On every render, all roots except the active one are `hidden`. Only the active root's `innerHTML` is updated. This preserves scroll position for inactive views between tab switches.

`renderView(ctx)` dispatches to the appropriate renderer method by `switch(view)`. Adding a new panel requires a new entry in `VIEWS`, a new entry in `VIEW_ORDER`, a nav tab in `renderHeader()`, a case in the `renderView()` switch, a renderer method, and a binding method.

The `MAPPING_ARCHIVE` entry exists for backwards compatibility. Any call to `card.setView(VIEWS.MAPPING_ARCHIVE)` is silently redirected to `VIEWS.ROOMS`.

### 3.5 Floor texture rendering

Room cards render an optional floor-texture layer behind their content. The system is registry-driven and lives in four card files:

- `src/textures/floor-texture-registry.js` — maps each floor type to its layer stack (mask URL, color token, opacity token, optional blur token) plus the SVG-map pattern data.
- `src/textures/floor-texture-resolver.js` — resolves a room's `floor_type` / `carpet_type` to a canonical registry key.
- `src/renderers/floor-texture-surface.js` — generates the card overlay (one `<span>` per layer) and the SVG map polygons/patterns.
- `src/styles/floor-texture-styles.js` — the layer CSS.

**Masking model.** Each layer is a `<span>` filled with its color token and clipped by a grayscale PNG via `mask-image` + **`mask-mode: luminance`** (white reveals the color, black hides it). `mask-mode:luminance` is set explicitly because a raster mask defaults to `mask-mode:alpha` (match-source), and the masks carry no alpha channel — under alpha mode the tint would flood the whole field. A base layer is a mostly-white field (fills the surface with its color); a detail layer (vein / grout / speckle) is a black field with white detail.

**Cache-busting.** Textures are served `cache_headers=True` (7-day browser cache). The build (`scripts/build-card.mjs`) computes a SHA-1 **content hash of the textures directory** and injects it via esbuild `--define __ASSET_VER__`; the registry appends `?v=<hash>` to every texture URL. A regenerated mask changes the hash → browsers fetch it fresh, with zero churn when textures are unchanged.

**Marble two-tier veins.** Marble splits its veins into **major** and **minor** layers. Every vein property is `master + per-layer offset`, clamped, so a master control rides both tiers while the per-tier offsets preserve their delta:
- opacity → `clamp(0, vein-opacity + tier-offset, 1)`
- blur → `max(0, vein-blur + tier-blur-offset)`
- the **minor** color is the master vein color receded in **OKLCH** relative-color syntax (lighter + desaturated + cooler): `oklch(from var(--master) calc(l + Δl) calc(c * Δc) calc(h + Δh) / alpha)`, so the secondary network recedes (atmospheric depth) instead of competing with the major veins.

Blur is an **opt-in per-layer wrapper**: because CSS applies `filter` *before* `mask`, a blurred layer's span is wrapped in a `.evcc-ftx-blur` div so the blur lands on the already-masked result (soft vein edges) rather than the flat fill.

**Legibility over the texture.** The texture is a variable-luminance background, so status/setting chips, the action controls, the room name, and notes get an **opaque surface backing** (or a surface-colored text halo for bare labels) on `.evcc-room-card` — legibility is decoupled from the texture rather than tuned per color, so any chip color stays readable over any floor.

**Stacking.** `.evcc-room-card` sets `isolation: isolate` and the texture layer sits at `z-index: -1`, beneath the queue progress fill (`::before`), the pulse (`::after`), and all content (`z-index: 1`) — so the per-room clean-progress sweep paints *over* the texture, not under it.

The texture layers are themed entirely through the `Floor Textures — *` token groups (see [20-theme-system.md], which also covers the targeted per-floor export/import and presets).

---

## 4. State Management Contract

### 4.1 Module inventory

| Module | File | What it owns |
|---|---|---|
| core | `state/core.js` | `hass.states` access helpers; vacuum entity, state, attributes, battery; vacuumObjectId |
| rooms | `state/rooms.js` | Room list building from switch entities; active map resolution; enabled room counting; access graph logic |
| rooms-order | `state/rooms-order.js` | Order adapter for rooms; drag/selector state for room reordering |
| room-access | `state/room-access.js` | Room access editor open/close state |
| room-editor | `state/room-editor.js` | In-modal field editor state (active room, field values, profile picker) |
| room-estimate | `state/room-estimate.js` | Room-level time estimates storage |
| room-profiles | `state/room-profiles.js` | Room profile library cache |
| room-rules | `state/room-rules.js` | Room rules editor state |
| run-profiles | `state/run-profiles.js` | Saved run profile library cache |
| dock | `state/dock.js` | Dock action status; pause-timeout settings |
| maintenance | `state/maintenance.js` | Maintenance snapshot; dock event data |
| metrics | `state/metrics.js` | Metrics snapshot; filter state |
| review | `state/review.js` | Learning history snapshot; filter state |
| external-jobs | `state/external-jobs.js` | External-run review: subtab selection, pending list, and the confirm wizard (split/merge toggles + per-segment assignments). See [28](28-external-run-ingestion.md) |
| learning | `state/learning.js` | Live-job learning state: estimate, reanchored estimate, next room, completed rooms, job-active flag; incomplete run log; trouble rooms log |
| order | `state/order.js` | Generic order selector (scope, item, position) shared by rooms and run profiles |
| theme | `state/theme.js` | Active theme id, working draft, draft dirty flag, theme library; editor UI state (search query, group filter, open groups) |
| map | `state/map.js` | Map segments data |
| setup | `state/setup.js` | Setup status; setup loading flag |
| mapping-review | `state/mapping-review.js` | Room bounds snapshot |
| confirmations | `state/confirmations.js` | Two-tap confirm state for destructive actions |
| toasts | `state/toasts.js` | Transient toast / notice queue |
| viewport | `state/viewport.js` | Viewport / responsive (mobile vs desktop) state |

### 4.2 Init shape and clear shape

Each state module stores data in plain properties on `this` (the `VacuumCardState` instance). There is no central store object — properties are scattered across the prototype by module. The pattern is consistent:

- A `set*` method assigns the property.
- A getter method reads it with a fallback.
- A `clear*` method (where appropriate) resets to null or `{}`.

Example:
```js
proto.setDockActionStatus = function(payload) { this._dockActionStatus = payload; };
proto.dockActionStatus = function() { return this._dockActionStatus ?? null; };
```

Properties are **not initialized in the constructor** — they are lazily created by the first setter call. This means a getter that fires before the first set returns `undefined ?? null` → `null`, which is the intended "not yet loaded" sentinel.

### 4.3 The hass setter and the load-once pattern

The `hass` setter in `main.js` runs on every HA state push. It:

1. Calls `state.sync(hass, config)` and `actions.sync(hass, state)` to refresh references.
2. Reads the theme sensor attributes and calls `state.setBackendThemeState()`.
3. Calls `_scheduleRender()`.
4. Schedules debounced refreshes for all service-fetched data (dashboard snapshot, start status, dock action status, pause timeout, metrics, learning history, run profiles, incomplete run log, trouble rooms log).

Most of these scheduled refreshes use `clearTimeout` + `setTimeout` with different delays (350 ms to 1400 ms) to avoid hammering the backend on rapid HA state bursts.

**Load-once pattern**: Some fetches should only happen once per session because they are expensive or their data rarely changes. The card implements this with boolean flags (`_themeLoaded`, `_incompleteRunLogLoaded`, `_troubleRoomsLogLoaded`). Once set to `true`, the corresponding scheduler exits early:

```js
_scheduleIncompleteRunLogRefresh() {
  if (this._incompleteRunLogLoaded) return;
  // ...
}
```

The theme library is loaded once via `_loadInitialThemeState()`, which is also guarded by `this._themeLoaded`. Subsequent HA pushes only sync the theme sensor attributes (cheap — already in `hass.states`); they do not re-fetch the library.

### 4.4 How state modules communicate

They don't. Every inter-module interaction routes through the card instance:

- Bindings hold `this.card` and call `this.card._state.someMethod()` and `this.card._actions.someAction()`.
- Actions hold `this.state` and read from it but never write to other action modules.
- Renderers hold `this.card` and read `this.card._state`.

If a binding needs a value from two different state modules, it calls each module's getter separately and combines the results inline.

---

## 5. Building a Different UI — What You Need

This section specifies the minimum required for any UI (React app, Vue SPA, native app, CLI tool, etc.) that wants to drive a eufy_vacuum installation.

### 5.1 Minimum viable polling loop

The backend does not push card-specific state over WebSockets. You must poll:

```
Every time hass.states updates (subscribe via HA WebSocket connection event):
  - Read vacuum entity state + battery from hass.states
  - Read all switch entities whose attributes.vacuum_entity_id == your vacuum
  - Read all number entities whose attributes.vacuum_entity_id == your vacuum
  - Read sensor.{object_id}_theme_state attributes
  - Read sensor.{object_id}_active_map state

Every 500 ms (debounced after HA state push):
  - Call get_dashboard_snapshot(vacuum_entity_id, map_id)

Every 800 ms (debounced after HA state push):
  - Call get_start_status(vacuum_entity_id, map_id)

On Base Station tab activation:
  - Call get_dock_action_status(vacuum_entity_id, map_id)
  - Call get_pause_timeout_settings(vacuum_entity_id)

On Metrics tab activation:
  - Call get_metrics_snapshot(vacuum_entity_id, filters...)

On Learning Review tab activation:
  - Call get_learning_history_snapshot(vacuum_entity_id, filters...)

On Map Bounds Review tab activation:
  - Call get_room_bounds_snapshot(vacuum_entity_id, map_id)

Once per session (load-once):
  - Call get_theme_library()
  - Call get_incomplete_run_log(vacuum_entity_id)
  - Call get_trouble_rooms_log(vacuum_entity_id)

On Rooms tab when map_id or vacuum changes:
  - Call get_saved_run_profiles(vacuum_entity_id, map_id)
  - Call get_room_learning_estimates(vacuum_entity_id, map_id)
```

### 5.2 Event subscriptions needed for real-time updates

Subscribe to all five events for any UI that tracks live jobs:

| Event | Why |
|---|---|
| `eufy_vacuum_room_started` | Update "currently cleaning" indicator |
| `eufy_vacuum_room_finished` | Update completed rooms list; trigger reanchor call |
| `eufy_vacuum_job_finished` | Clear active job UI; show summary |
| `eufy_vacuum_stall_detected` | Show stall warning banner |
| `eufy_vacuum_run_incomplete` | Show missed rooms prompt; offer retry action |

### 5.3 Entity reads needed for room state

For each room in the active map you need:

1. **Switch entity** for enabled/disabled state and all room settings (name, mode, fan speed, etc.). Discover by scanning `hass.states` for entities where `state.attributes.vacuum_entity_id === yourVacuumEntityId` and the entity ID starts with `switch.`.
2. **Number entity** for sort order. Discover by scanning `hass.states` for entities where `state.attributes.vacuum_entity_id === yourVacuumEntityId` and the entity ID starts with `number.` and ends with `_order`.

The active map ID comes from `sensor.{object_id}_active_map` state value.

### 5.4 Service call safety notes

**Safe to call from any UI without side effects:**

- All `get_*` services (read-only query services)
- `get_theme_library` (read-only)
- `run_learning_estimate` (read-only compute, does not mutate stored state)
- `reanchor_learning_timeline`, `get_next_room` (pure compute)

**Has side effects — understand before calling:**

- `start_selected_rooms` — starts the vacuum. Do not call without confirming `get_start_status` returns non-blocked. Do not call with `returnResponse = true` (HA rejects it).
- `clear_queue` — empties the pending run queue only; does **not** disable rooms (the card UI disables rooms as a separate composite action before calling it).
- `finalize_learning_job` — fires `eufy_vacuum_run_incomplete` if rooms were missed. Call only when a job ends.
- `setup_delete_map` — destroys a map and all its room data. Requires a confirmation token for high-protection maps.
- `wash_mop`, `dry_mop`, `empty_dust` — physically operate dock hardware.
- `update_room_fields` — null optional fields (e.g. `water_level`) must be omitted, not sent as null. HA schema validation will reject them.
- `apply_run_profile` — overwrites current room selection and settings with saved profile values.
- `revert_draft` — discards unsaved theme editor changes.

---

## 6. Adding a New Panel to the Current Card

Concrete checklist, in order.

### Step 1: Add to the VIEWS enum (`src/render-cycle.js`)

```js
export const VIEWS = {
  // ... existing entries ...
  MY_PANEL: "my_panel",
};
```

Add `VIEWS.MY_PANEL` to `VIEW_ORDER` as well:

```js
export const VIEW_ORDER = [
  // ... existing entries ...
  VIEWS.MY_PANEL,
];
```

### Step 2: Add a nav tab (`src/render-cycle.js`, `renderHeader()`)

Inside the `<div class="evcc-nav">` section of `renderHeader()`, add:

```js
<button class="evcc-nav-tab ${view === VIEWS.MY_PANEL ? "active" : ""}"
        data-view="${VIEWS.MY_PANEL}">
  My Panel
</button>
```

The nav binding in `src/bindings/nav.js` already handles all `[data-view]` buttons generically — no changes needed there.

### Step 3: Add a case to the view router (`src/render-cycle.js`, `renderView()`)

```js
case VIEWS.MY_PANEL:
  return renderers.renderMyPanelView?.(ctx)
    ?? `<div class="evcc-empty">My panel unavailable</div>`;
```

### Step 4: Create a renderer module (`src/renderers/my-panel.js`)

```js
export function applyMyPanelRenderers(proto) {
  proto.renderMyPanelView = function(ctx) {
    const { state } = ctx;
    // Read from state, return HTML string.
    return `<div class="evcc-my-panel">...</div>`;
  };
}
```

Import and apply in `src/renderers/index.js`:

```js
import { applyMyPanelRenderers } from "./my-panel.js";
// ...
applyMyPanelRenderers(VacuumCardRenderers.prototype);
```

### Step 5: Create a bindings module (`src/bindings/my-panel.js`)

```js
export function applyMyPanelBindings(proto) {
  proto._bindMyPanel = function() {
    const root = this.card.shadowRoot;
    root.querySelectorAll("[data-action='my-action']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await this.card._actions.myAction();
        this.card._scheduleRender();
      });
    });
  };
}
```

Import and apply in `src/bindings/index.js`, and call `this._bindMyPanel()` from `bindEvents()`:

```js
import { applyMyPanelBindings } from "./my-panel.js";
// ...
applyMyPanelBindings(VacuumCardBindings.prototype);
// In bindEvents():
this._bindMyPanel();
```

### Step 6: Add a state module if needed (`src/state/my-panel.js`)

```js
export function applyMyPanelState(proto) {
  proto.setMyPanelData = function(payload) {
    this._myPanelData = payload;
  };
  proto.myPanelData = function() {
    return this._myPanelData ?? null;
  };
}
```

Import and apply in `src/state/index.js`:

```js
import { applyMyPanelState } from "./my-panel.js";
// ...
applyMyPanelState(VacuumCardState.prototype);
```

### Step 7: Add an action module if needed (`src/actions/my-panel.js`)

```js
import { DOMAIN } from "../constants.js";
export function applyMyPanelActions(proto) {
  proto.getMyPanelData = async function() {
    const result = await this.callService(DOMAIN, "my_panel_service", {
      vacuum_entity_id: this.state.vacuumEntityId(),
    }, true);
    return result?.response ?? result;
  };
}
```

Import and apply in `src/actions/index.js`:

```js
import { applyMyPanelActions } from "./my-panel.js";
// ...
applyMyPanelActions(VacuumCardActions.prototype);
```

### Step 8: Wire the data refresh in `main.js` (if the panel needs server data)

Add a scheduler method and call it from `setView()` and from the `hass` setter:

```js
_scheduleMyPanelRefresh() {
  if (!this._state || !this._actions) return;
  if (this._view !== VIEWS.MY_PANEL) return;

  clearTimeout(this._myPanelTimer);
  this._myPanelTimer = setTimeout(async () => {
    const payload = await this._actions.getMyPanelData();
    if (payload && this._state) {
      this._state.setMyPanelData(payload);
      this._scheduleRender();
    }
  }, 500);
}
```

Add `clearTimeout(this._myPanelTimer)` to `disconnectedCallback()` to prevent memory leaks.
