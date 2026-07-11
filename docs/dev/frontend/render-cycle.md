# Render Cycle

How the card turns a state change into DOM: the microtask-batched `_scheduleRender`, the 8-step `_render` with its innerHTML cache-stamp and full re-bind invariant, click/double-click disambiguation, the view enum and routing, and floor-texture rendering. This doc is one spoke of the card architecture — start at [architecture-overview.md](architecture-overview.md) for the hub. The binding layer and the body-level modal host referenced in step 6/7 below are documented in depth in [event-binding-and-modal-host.md](event-binding-and-modal-host.md); the CSS-token side of floor textures lives in [styles-system.md](styles-system.md) and [theme-system.md](theme-system.md).

---

## `_scheduleRender`: microtask, not `setTimeout`

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

## Full re-render and re-bind on every cycle

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

> The binding layer and the body-level modal host (`_updateModalHost` in step 6) are documented in depth in **[event-binding-and-modal-host.md](event-binding-and-modal-host.md)**: the `_on`/`_onAll` helpers and their idempotency, why the `document.body` modal portal needs a bind path `_onAll` can't provide, the live-vs-commit (`input` vs `change`) convention, and the non-`hass` `_scheduleRender` trigger map.

## Why `dblclick` is unreliable: the 220 ms click disambiguation timer

A double-click involves two click events. Between them, `_scheduleRender()` fires (triggered by the first click changing state). The render replaces `innerHTML`, which detaches the element that received the first click. The second click either fires on nothing or on a freshly-attached clone that has no double-click handler.

The solution used in the card is a **220 ms single-click disambiguation timer**: on the first click, start a timer. If a second click arrives within 220 ms, treat the pair as a double-click and cancel the timer. If 220 ms passes with no second click, execute the single-click action. This keeps the DOM stable between the two clicks.

## The VIEWS enum and view routing

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
  SETUP:           "setup",
};
```

`VIEW_ORDER` is the array used to pre-create view root divs in the shell frame. Each view gets its own `<div data-evcc-view-root="{viewName}">` inside the view stage. On every render, all roots except the active one are `hidden`. Only the active root's `innerHTML` is updated. This preserves scroll position for inactive views between tab switches.

`renderView(ctx)` dispatches to the appropriate renderer method by `switch(view)`. Adding a new panel requires a new entry in `VIEWS`, a new entry in `VIEW_ORDER`, a nav tab in `renderHeader()`, a case in the `renderView()` switch, a renderer method, and a binding method.

The `MAPPING_ARCHIVE` entry exists for backwards compatibility. Any call to `card.setView(VIEWS.MAPPING_ARCHIVE)` is silently redirected to `VIEWS.ROOMS`.

## Floor texture rendering

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

The texture layers are themed entirely through the `Floor Textures — *` token groups (see [theme-system.md](theme-system.md), which also covers the targeted per-floor export/import and presets).
