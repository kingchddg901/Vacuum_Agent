# Card Topology & Bundles

This doc maps the frontend's *element topology* — the two standalone Lovelace cards that ship alongside the sidebar panel, the three self-contained ESM bundles the build emits, and the `<eufy-vacuum-map>` host shim that lets the map renderer mixin live inside a standalone card. Start at [architecture-overview.md](architecture-overview.md) for the hub; the three-bundle boundary is also the CSS boundary described in [styles-system.md](styles-system.md), and every file named here has a per-file entry in [module-reference.md](module-reference.md).

Everything in [architecture-overview.md](architecture-overview.md) describes the **sidebar panel** (the monolithic `EufyVacuumCommandCenter`). The integration also ships **two standalone Lovelace cards** a user drops onto their own dashboards. They reuse the panel's *patterns and helpers* but are independent custom elements.

## The two cards

| Element | Display name | Config | File |
|---|---|---|---|
| `vacuum-agent-dashboard` | Vacuum Agent — Dashboard Mode | `vacuum_entity_id` (req), `title`, `show_map`, `show_profiles`, `show_scenes`, `show_dock` | `src/cards/dashboard-card.js` |
| `eufy-room-card` | Eufy Room Card | `vacuum_entity_id` (req), `room_id` (req), `name` | `src/room-card.js` |

Both follow the HA card contract (`setConfig`, `set hass`, `getConfigElement`, `getStubConfig`, `window.customCards.push`) and define themselves via `defineCard(name, cls)` — an **idempotent** `customElements.define` (the same element is defined by more than one bundle; see the bundles section below). The dashboard card is the multi-room control surface (header → map → Rooms accordion → profiles → app scenes → Start/Dock); the room card is single-room. Their shared, DOM-light helpers live in **`src/cards/_shared.js`** (`esc`, `vocab`, `roomSwitchesFor`, `adapterOptions`, `committedRoomFields`, `chipRow`, `callResponse`, `stripNull`, `registerCard`, `defineCard`, and the language control `renderLangControl`/`wireLangControl`).

The dashboard card's **arm-then-Start** dispatch is pure + unit-tested in `src/cards/dashboard-dispatch.js` (`nextArmed` mutual-exclusivity reducer, `planStart`, `armedIsValid`). Nothing reaches the vacuum until **Start** — load-bearing because the Eufy app scene (`select.<obj>_scene`) *fires on `select_option`*, so the card only stores the choice locally and fires on Start ().

## Three self-contained ESM bundles

`scripts/build-card.mjs` (`npm run build:deploy`) emits **three** bundles — no code-splitting; the duplicated common code is the price of independently-cacheable, lazily-loadable modules:

| Bundle | Entry | Loaded |
|---|---|---|
| `eufy-vacuum-command-center.js` | `src/all-cards.js` | the sidebar **panel** (registered as the panel module) |
| `eufy-vacuum-cards.js` | `src/cards-standalone.js` | **every page** — registered globally via `frontend.add_extra_js_url(hass, url)` in `async_setup`, so the cards are defined even on a cold dashboard that never opens the panel |
| `eufy-vacuum-map.js` | `src/cards/vacuum-map-host.js` | **lazily**, on demand — `import("/eufy_vacuum/frontend/eufy-vacuum-map.js")` from the dashboard card when a map is wanted |

The lazy map URL is an absolute *served* URL, marked `external: ["/eufy_vacuum/frontend/*"]` in esbuild so it's left as a runtime `import()` (the same pattern `main.js` uses for the animal-svg manifest). The heavy ~1 MB map graph loads only when `show_map` is on. Because the cards bundle and the panel bundle both define `vacuum-agent-dashboard` / `eufy-room-card`, the `defineCard` guard keeps the second define a no-op.

**Cache-busting.** Two build-injected content hashes (esbuild `define`): `__ASSET_VER__` (textures dir) and `__LOCALE_VER__` (the shipped locales dir). The locale loader appends `?v=__LOCALE_VER__` to the shipped `index.json` + per-locale fetches so an edited catalog can't be served stale (the symptom was newly-added keys falling back to English while older keys rendered translated). See for the *escaping* counterpart — `t()` output is already HTML-escaped (trust model B), so it must never be passed through `esc()`/`escapeHtml()` again.

## The `<eufy-vacuum-map>` host

The map is a renderer **mixin** coupled to the card (`this.card._state` / `_actions` / `_scheduleRender` / `shadowRoot`), not a component — so embedding it meant building a **host shim**, `src/cards/vacuum-map-host.js`. The host:

- instantiates the real `VacuumCard{State,Renderers,Bindings,Actions}` and exposes them as `_state` / `_renderers` / `_actions` / `_bindings`;
- provides the card surface the mixins expect — `applyCardDomHelpers(this)` (`_on`/`_onAll`), `_scheduleRender`, `showToast`, the two frame pollers copied from `main.js`, and an instance override `isMapViewActive → true` (it does **not** write the panel's per-vacuum view localStorage);
- renders `mapStyles + renderMapRoomView(ctx)` then calls `_bindings._bindMap()`;
- imports its own `i18n` instance and calls `ensureLocalesLoaded` (a separate bundle = a separate catalog registry), and is fed `_langOverride` + `hass` by the dashboard card each render.

**Per-context, per-device view state.** Two map prefs are persisted in `localStorage`, both keyed so the panel and an embedded card never fight:

- **Pan/zoom** (`_mapZoom` / `_mapTranslateX` / `_mapTranslateY`, `src/state/map.js`) — lazy-restored on first render, persisted (debounced) on `applyMapZoom`/`applyMapPan`, flushed in `disconnectedCallback`, cleared by the fit button (`resetMapTransform`). Key: `evcc_map_xform_<ctx>_<vac>` where `<ctx>` is `panel` (default) or `card` (the host sets `_state._mapCtx = "card"`). Translate is in container **px**, hence per-context. The reset-on-map-switch is gated to a genuine real→real switch (`_xformMapId`) so it never wipes the just-restored view on first load.
- **Moved room-name labels** — drag a name off its centroid; the position is stored as **% of the content box** (container-independent, so one key works for panel + card), key `evcc_map_room_names_<vac>_<mapId>`. A tap (no drag) still forwards to the polygon's single-click select; dropping a name back near its centroid clears the anchor (auto-placement). Only the *segment* name labels (`.evcc-map-label--draggable`, `pointer-events:auto`) are draggable — the device-room fallback labels stay tap-through.

## Reuse boundary

The cards are a **new sibling** of the panel, not an extension of it. The single-room `EufyRoomCard` stays single-room by design; the dashboard card is the multi-room surface. Both consume the same backend contract (see [backend-contract-and-data-shapes.md](backend-contract-and-data-shapes.md)) — `get_dashboard_snapshot`, `start_selected_rooms`, `start_run_profile`, `update_room_fields`, `switch.turn_on/off`, the `select.<obj>_scene` entity — so a card-started run appears in the panel's history/learning identically. The user-facing guide is [Dashboard & Room cards](../../user-guide/20-dashboard-and-room-cards.md).
