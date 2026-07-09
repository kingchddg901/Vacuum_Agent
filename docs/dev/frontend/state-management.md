# State Management

This doc covers the card's state layer: the `state/` module inventory, how each module stores and clears its data, the `hass` setter and its load-once pattern, and the rule that state modules never talk to each other directly — everything routes through the card instance. It is one spoke of the frontend doc set; start at [architecture-overview.md](architecture-overview.md) for the hub, and see [module-reference.md](module-reference.md) for the per-file navigation map of every *other* frontend directory (actions, bindings, renderers, styles, theme-tokens, i18n, `cards/`, and the entry points).

---

## Module inventory

The table below covers the **`state/`** modules. For every *other* frontend module — actions,
bindings, renderers, styles, theme-tokens, i18n, the `cards/` elements, and the entry points —
see the per-file navigation map in [module-reference.md](module-reference.md).

| Module | File | What it owns |
|---|---|---|
| core | `state/core.js` | `hass.states` access helpers; vacuum entity, state, attributes, battery; vacuumObjectId |
| rooms | `state/rooms.js` | Room list building from switch entities; active map resolution; enabled room counting; access graph logic |
| rooms-order | `state/rooms-order.js` | Order adapter for rooms; drag/selector state for room reordering |
| room-access | `state/room-access.js` | Room access editor open/close state |
| room-editor | `state/room-editor.js` | In-modal field editor state (active room, field values, profile picker); the derived `supportsSettableMop()` getter (reads `dashboardSnapshot().supports_water_control`) that gates whether the editor shows the `clean_mode` picker or a read-only observe-only tank indicator — true for Eufy and settable-mop Roborock (S7+), false for observe-only tanks (Roborock S6) |
| room-estimate | `state/room-estimate.js` | Room-level time estimates storage |
| room-profiles | `state/room-profiles.js` | Room profile library cache |
| room-rules | `state/room-rules.js` | Room rules editor state |
| run-profiles | `state/run-profiles.js` | Saved run profile library cache (`setRunProfilesLibrary` / `savedRunProfiles`), selected profile, and the **profile editor draft**. The draft carries an ordered **`steps`** list — room GROUPS interleaved with `charge_wait` / `wait` STOP steps (`runProfileDraftSteps` / `addDraftChargeStep` / `addDraftWaitStep` / `setDraftChargeTarget` / `setDraftWaitMinutes` / `removeDraftStep` / `moveDraftStep` / `captureCurrentRoomsAsDraftGroup`, all delegating the immutable array math to `state/steps-order.js`); `_normalizeRunProfile` surfaces the backend `has_charge_steps` flag that drives the stepped card UI. Also tracks the **applied-profile** slice — `setAppliedRunProfile` / `pendingStepRunProfileId` (the applied stepped profile's id, the signal that Start should dispatch `start_run_profile` instead of a flat `start_selected_rooms`; cleared when the user hand-edits rooms) — and the collapsible "This run" preview state (`isSteppedPreviewCollapsed` / `toggleSteppedPreviewCollapsed`). Registered in `state/index.js` via `applyRunProfilesState` |
| steps-order | `state/steps-order.js` | **Pure step-mutation helpers** for the run-profile steps editor (no card state, not registered on the prototype — imported by `state/run-profiles.js`). Immutably insert/remove/move/retarget STEP-level entries (`insertChargeStep` / `insertWaitStep` / `removeStep` / `moveStep` / `setChargeTarget` / `setWaitMinutes`), classify steps (`isRoomGroupStep` / `isChargeStep` / `isWaitStep`), clamp targets to the `CHARGE_TARGET_MIN`/`CHARGE_TARGET_MAX` (1–100, default 95) and `WAIT_MIN_MINUTES`/`WAIT_MAX_MINUTES` (1–1440, default 30) ranges, snapshot the enabled Rooms view into a `room_group` step (`roomsToGroupStep`, omitting unset per-room fields so they fall through to the global room settings at dispatch), and `sanitizeStepsForSave` mirroring the backend `normalize_run_profile_steps`. Has its own `steps-order.test.mjs` |
| dock | `state/dock.js` | Dock action status; pause-timeout settings |
| maintenance | `state/maintenance.js` | Maintenance snapshot; dock event data |
| metrics | `state/metrics.js` | Metrics snapshot; filter state |
| review | `state/review.js` | Learning history snapshot; filter state |
| external-jobs | `state/external-jobs.js` | External-run review: subtab selection, pending list, and the confirm wizard (split/merge toggles + per-segment assignments). See [external-run ingestion](../28-external-run-ingestion.md) |
| learning | `state/learning.js` | Live-job learning state: estimate, reanchored estimate, next room, completed rooms, job-active flag; incomplete run log; trouble rooms log |
| order | `state/order.js` | Generic order selector (scope, item, position) shared by rooms and run profiles |
| theme | `state/theme.js` | Active theme id, working draft, draft dirty flag, theme library; editor UI state (search query, group filter, open groups) |
| map | `state/map.js` | Map segments data; zoom/pan transform; segment selection + segment↔room overlay; dot-anchor overlay; active `segmentation_mode`; the **named custom layouts** — `customLayouts()` / `activeCustomLayoutId()` / `activeCustomLayout()` plus the layout-editor slice (`openNewLayoutEditor` / `openRenameLayoutEditor` / `closeLayoutEditor` / `isLayoutEditorOpen` / `layoutEditorMode` / `layoutDraftName` / `setLayoutDraftName`); the **custom-segment composer draft** (shapes, grouping/merge/cut, move-scope, rotate, nudge step) via `proto.compose*` — the draft load and mascot anchors are keyed on `${map_id}:${active_custom_layout_id}` (`setMapSegmentsData` resets the draft when **either** changes; `_composeKey`/`maybeLoadComposeDraft` reload on a layout switch); animal selection/scale; `mapAnimalEnabled` plus the split `mapFloorTextureEnabled` / `roomFloorTextureEnabled` toggles (localStorage `evcc_animal_on_<vac>` / `evcc_floor_tex_map_<vac>` / `evcc_floor_tex_rooms_<vac>`, default on); the **live-map display-rotation** slice (`mapRotation` / `setMapRotationOptimistic` / the `_mapRotationOverlay` optimistic value — applied only to the live image, never to CV/custom maps); the **dwell-debounced mascot follow** (`mascotDwelledRoomId`, committing a room only after sustained dwell); the **live-backdrop URL** slice — `mapImageUrl` (the active backdrop URL, short-circuiting to the live image via `isLiveBackdropActive` when the active scope is a `backdrop_source: "live"` layout) and `_liveMapImageUrl` (appends the live entity's `last_updated` as a query param to cache-bust a stable-token `camera.` entity each frame); and the **per-vacuum room-label visibility** toggle `mapRoomLabelsEnabled` (localStorage `evcc_map_labels_<vac>`, default on) gating the `.evcc-map-label` render so VA's labels don't stack on a label-baked live backdrop. It also owns the **zone-clean draft** (`zoneDrafts` / `zoneDrawMode` / `canDrawZone` / `zoneMax` / `addZoneDraft` — the rectangles fed to `start_zone_clean`), the **hidden-regions draw** slice (`hiddenRegions` / `hideDrawMode` / `canDrawHideArea` → `set_hidden_regions`), the **area-label anchor** slice (`areaLabelAnchor` → `set_area_label_anchor`), the **overlay-visibility** slice (`overlaysAligned` → `set_map_overlay_visibility`), and the **live-pose** slice (`livePose`, fed by `get_map_live_pose`) — each with its own `*.test.mjs` under `src/state/` (`zone-draft`, `hidden-regions`, `area-label-anchor`, `live-pose-overlay`). Note: `liveMapImageEntity` is owned by `state/learning.js` (reads `dashboardSnapshot().live_map_image_entity`), **not** this module — but `mapRotation`, `mascotDwelledRoomId`, the live-URL slice, and `mapRoomLabelsEnabled` live here |
| setup | `state/setup.js` | Setup status; setup loading flag |
| mapping-review | `state/mapping-review.js` | Room bounds snapshot |
| confirmations | `state/confirmations.js` | Two-tap confirm state for destructive actions |
| toasts | `state/toasts.js` | Transient toast / notice queue |
| viewport | `state/viewport.js` | Viewport / responsive (mobile vs desktop) state |
| saved-zones | `state/saved-zones.js` | Saved-zone library (`savedZones` / `setSavedZonesLibrary`, backed by `_savedZonesLibrary` with a map-segments fallback); panel multi-select "will be cleaned" set (`toggleSavedZoneSelection` / `selectedSavedZoneIds` / `selectedSavedZoneCount` / `clearSavedZoneSelection`); collapsible-section state (`savedZonesCollapsed`); grouping-by-room for the panel (`savedZonesGrouped` — one group per room in map order, Unassigned bucket last). Registered in `state/index.js` via `applySavedZonesState` |
| dialog | `state/dialog.js` | Card-native confirm/alert/prompt dialog spec (`openDialog` / `pendingDialog` / `resolveDialog` / `cancelDialog`), replacing browser-native `window.confirm/alert/prompt` (which use the browser locale and are suppressed in the HA webview). One dialog open at a time; the spec carries a `resolve` promise fn and a kind-appropriate cancel value (confirm → false, prompt → null, alert → undefined). Registered in `state/index.js` via `applyDialogState` |

## Init shape and clear shape

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

## The hass setter and the load-once pattern

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

## How state modules communicate

They don't. Every inter-module interaction routes through the card instance:

- Bindings hold `this.card` and call `this.card._state.someMethod()` and `this.card._actions.someAction()`.
- Actions hold `this.state` and read from it but never write to other action modules.
- Renderers hold `this.card` and read `this.card._state`.

If a binding needs a value from two different state modules, it calls each module's getter separately and combines the results inline.
