# Card Architecture — Overview

This is the **hub** for the frontend documentation set. It covers the two things that stay constant across every panel and card: the **mixin pattern** that four collaborating objects (actions / state / renderers / bindings, plus the controller) are built on, and the **recipe for adding a new panel**. Everything else — the render cycle, state contract, backend contract, styles, bundles, and each feature subsystem — has its own focused doc, indexed below. Start here, then follow the reading map.

---

## The frontend doc set

Each frontend doc lives in `docs/dev/frontend/` and covers one focused area. Links between them are bare sibling filenames; links out to backend subsystems keep their `../NN-` prefix.

- **[architecture-overview.md](architecture-overview.md)** — this hub: the mixin pattern (four layers + the controller), the strict data-flow, and the add-a-panel recipe.
- **[render-cycle.md](render-cycle.md)** — `_scheduleRender` (microtask coalescing), full re-render/re-bind, the `dblclick` disambiguation timer, the `VIEWS`/`VIEW_ORDER` router, and floor-texture rendering.
- **[state-management.md](state-management.md)** — the `state/` module inventory, the init/clear property shape, the `hass` setter + load-once pattern, and how state modules communicate (they don't — everything routes through the card).
- **[event-binding-and-modal-host.md](event-binding-and-modal-host.md)** — the binding layer: `_on`/`_onAll` helpers and idempotency, the `document.body` modal portal, the live-vs-commit (`input`/`change`) convention, and the non-`hass` `_scheduleRender` trigger map.
- **[styles-system.md](styles-system.md)** — where CSS lives, the `styles/` module structure, and the token/CSS-custom-property conventions the renderers emit.
- **[backend-contract-and-data-shapes.md](backend-contract-and-data-shapes.md)** — the backend as a **contract**: every `eufy_vacuum` service, event, and entity a UI reads, the `get_map_segments` read model, plus the minimum polling loop / subscriptions / entity reads / call-safety notes for building any other UI.
- **[card-topology-and-bundles.md](card-topology-and-bundles.md)** — the two standalone Lovelace cards (`vacuum-agent-dashboard`, `eufy-room-card`), the three ESM bundles, the lazy `<eufy-vacuum-map>` host shim, and the reuse boundary vs. the sidebar panel.
- **[module-reference.md](module-reference.md)** — the per-file navigation map of `src/`: every actions / bindings / renderers / styles / theme-token / i18n / `cards/` module and the entry points.
- **[theme-system.md](theme-system.md)** — the theme token model, the editor, per-floor-texture token groups, export/import, presets, and the theme tag/search system.
- **[i18n-system.md](i18n-system.md)** — `this.t` / `this.tVocab`, the locale loader, the de-bundled catalogs, and the trust-model-B "never `esc()` a `t()`" rule.
- **[render-harness.md](render-harness.md)** — the headless Playwright render/visual-regression/CVD/intake harness and the theme gallery.
- **[animal-svg.md](animal-svg.md)** — the companion mascot: the declarative animal descriptor, codegen, and the community submission pipeline.
- **[furnished-render.md](furnished-render.md)** — the furnished digital-twin map: to-scale home art aligned once over the live map.
- **[map-render-layers.md](map-render-layers.md)** — the authoritative layer stack for map rendering (backdrop, polygons, labels, overlays, mascot) and the render-data shape.
- **[themeable-map-palette.md](themeable-map-palette.md)** — the room-fill palette resolver (per-room override > theme palette > default), live-map only.
- **[saved-zones.md](saved-zones.md)** — named reusable clean regions: the multi-select panel, shared settings, draw-to-save, and per-brand caps.
- **[dashboard-card.md](dashboard-card.md)** — the `vacuum-agent-dashboard` drop-in card in depth: arm-then-Start dispatch, embedded map, profiles, and scenes.
- **[custom-segment-composer.md](custom-segment-composer.md)** — the in-map composer: named custom layouts, the shape draft model, the button-driven operations, save/re-edit reconcile, and geometry boundaries.

---

## The Mixin Pattern

### Why prototype mixins rather than a component framework

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

### The four layers

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

**Renderers** (`src/renderers/`) — pure functions that take the render context object and return HTML strings. They read from state but never write to it and never call services. Their UI text is not English literals but localized through the [i18n system](i18n-system.md) (`this.t` / `this.tVocab`), per the user's chosen language.

**Bindings** (`src/bindings/`) — called after every render. They query the shadow DOM for data-attribute selectors and attach event handlers. Event handlers call actions or state mutators, then call `_scheduleRender()`.

**A fifth object — the controller.** Beyond the four render-cycle layers, `LearningController` (`src/controllers/learning-controller.js`, instantiated in `main.js` and driven by `connectedCallback` / `disconnectedCallback`) centralizes the event-driven live-job logic: it owns the HA event subscriptions (room started/finished, job finished), ETA reanchoring, bounds-exit polling, and the live job-progress ticker. The `learning` state module holds the data; the controller drives the updates.

### Strict data flow

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

## Adding a New Panel to the Current Card

Concrete checklist, in order. Each step touches one of the four layers described above; the render-cycle machinery it plugs into (the `VIEWS` enum, `VIEW_ORDER`, `renderHeader()`, `renderView()`) is documented in [render-cycle.md](render-cycle.md).

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

See [render-cycle.md](render-cycle.md) for how `VIEWS` / `VIEW_ORDER` drive the pre-created view-root divs and view routing.

### Step 2: Add a nav tab (`src/render-cycle.js`, `renderHeader()`)

Inside the `<div class="evcc-nav">` section of `renderHeader()`, add:

```js
<button class="evcc-nav-tab ${view === VIEWS.MY_PANEL ? "active" : ""}"
        data-view="${VIEWS.MY_PANEL}">
  My Panel
</button>
```

The nav binding in `src/bindings/nav.js` already handles all `[data-view]` buttons generically — no changes needed there (see [event-binding-and-modal-host.md](event-binding-and-modal-host.md)).

### Step 3: Add a case to the view router (`src/render-cycle.js`, `renderView()`)

```js
case VIEWS.MY_PANEL:
  return renderers.renderMyPanelView?.(ctx)
    ?? `<div class="evcc-empty">My panel unavailable</div>`;
```

`renderView(ctx)` is the `switch(view)` router covered in [render-cycle.md](render-cycle.md).

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

Renderers are pure and read-only; their CSS belongs in `src/styles/` (see [styles-system.md](styles-system.md)) and their text through i18n (see [i18n-system.md](i18n-system.md)).

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

Prefer the `_on`/`_onAll` helpers over raw `addEventListener` for idempotent re-binding — see [event-binding-and-modal-host.md](event-binding-and-modal-host.md).

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

The set/get/clear property convention (lazy init, `?? null` sentinel) is documented in [state-management.md](state-management.md).

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

The service you call must exist in the backend contract — see [backend-contract-and-data-shapes.md](backend-contract-and-data-shapes.md) and the backend [core manager](../05-core-manager.md).

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

Add `clearTimeout(this._myPanelTimer)` to `disconnectedCallback()` to prevent memory leaks. The `hass`-setter debounce/load-once pattern these schedulers follow is covered in [state-management.md](state-management.md).
