# Card Architecture — Overview

This is the **hub** for the frontend documentation set. It covers the two things that stay constant across every panel and card: the **mixin pattern** that four collaborating objects (actions / state / renderers / bindings, plus the controller) are built on, and the **recipe for adding a new panel**. Everything else — the render cycle, state contract, backend contract, styles, bundles, and each feature subsystem — has its own focused doc, indexed below. Start here, then follow the reading map.

---

## The frontend doc set

Each frontend doc lives in `docs/dev/frontend/` and covers one focused area. The set is split into **two concerns** — read them for different reasons:

- **Contract** — the exact, client-agnostic interface between the backend and *any* frontend. Its bar: you could throw away this card and build a functionally complete replacement (React, Lit, native mobile, another Lovelace card, voice, or an automation-only client) from the contract alone.
- **Implementation** — how *this* particular card is built: its layers, conventions, and deliberate choices. Its bar: you could reproduce this architecture and preserve its design conventions, not merely build *a* compatible client.

**Authority rule.** The **contract is authoritative** for behavior and data. The implementation docs describe how this card *consumes* the contract, but must **not** redefine payloads, invent backend guarantees, or become the only place a wire shape is documented. Deep subsystem semantics stay in the hardened backend subsystem docs (`../NN-*`); the contract **aggregates** the client-facing surface and **links** to the owning subsystem for the exact shape.

Links between frontend docs are bare sibling filenames; links out to backend subsystems keep their `../NN-` prefix.

### Contract

- **[backend-contract-and-data-shapes.md](backend-contract-and-data-shapes.md)** — the backend as a **contract**: every `eufy_vacuum` service (request + response shape), event payload, entity/attribute used as transport, the snapshot + `get_map_segments` read models, the capability flags and what they gate, the canonical-vs-localized boundary, polling/refresh/cache behavior, mutation/blocked/degraded responses, plus the minimum a non-card client needs. It **aggregates** the client-facing surface and **links** to the DR-grade backend docs ([05](../05-core-manager.md) / [06](../06-job-lifecycle.md) / [03](../03-data-model.md) / [02](../02-ha-integration.md)) for the deep shapes rather than re-owning them.

### Implementation

**Core render cycle & structure**

- **[architecture-overview.md](architecture-overview.md)** — this hub: the mixin pattern (four layers + the controller), the strict data-flow, and the add-a-panel recipe.
- **[render-cycle.md](render-cycle.md)** — `_scheduleRender` (microtask coalescing), the 8-step `_render` with its `dataset.renderedHtml` cache-stamp and full re-bind invariant, the `dblclick` disambiguation timer, the `VIEWS`/`VIEW_ORDER` router, and floor-texture rendering.
- **[state-management.md](state-management.md)** — the `state/` module inventory, the init/clear property shape, the `hass` setter + load-once pattern, and how state modules communicate (they don't — everything routes through the card).
- **[event-binding-and-modal-host.md](event-binding-and-modal-host.md)** — the binding layer: `_on`/`_onAll` helpers and idempotency, the `document.body` modal portal, the live-vs-commit (`input`/`change`) convention, and the non-`hass` `_scheduleRender` trigger map.
- **[card-topology-and-bundles.md](card-topology-and-bundles.md)** — the two standalone Lovelace cards (`vacuum-agent-dashboard`, `eufy-room-card`), the three ESM bundles, the lazy `<eufy-vacuum-map>` host shim, and the reuse boundary vs. the sidebar panel.
- **[module-reference.md](module-reference.md)** — the per-file navigation map of `src/`: every actions / bindings / renderers / styles / theme-token / i18n / `cards/` module and the entry points.

**Cross-cutting systems**

- **[styles-system.md](styles-system.md)** — where CSS lives, the `styles/` module structure, and the token/CSS-custom-property conventions the renderers emit.
- **[theme-system.md](theme-system.md)** — the theme token model, the editor, per-floor-texture token groups, export/import, presets, and the theme tag/search system.
- **[i18n-system.md](i18n-system.md)** — `this.t` / `this.tVocab`, the locale loader, the de-bundled catalogs, and the trust-model-B "never `esc()` a `t()`" rule. Owns localization — the frontend side of the contract's canonical-vs-localized boundary.
- **[render-harness.md](render-harness.md)** — the headless Playwright render/visual-regression/CVD/intake harness and the theme gallery.

**Feature subsystems**

- **[map-render-layers.md](map-render-layers.md)** — the authoritative layer stack for map rendering (backdrop, polygons, labels, overlays, mascot) and the render-data shape (owned by the backend map source; see the contract).
- **[themeable-map-palette.md](themeable-map-palette.md)** — the room-fill palette resolver (per-room override > theme palette > default), live-map only.
- **[floor-texture-map-view.md](floor-texture-map-view.md)** — the per-floor-type material fill for the Map view (hardwood / tile / carpet textures), both brands.
- **[saved-zones.md](saved-zones.md)** — named reusable clean regions: the multi-select panel, shared settings, draw-to-save, and per-brand caps.
- **[custom-segment-composer.md](custom-segment-composer.md)** — the in-map composer: named custom layouts, the shape draft model, the button-driven operations, save/re-edit reconcile, and geometry boundaries.
- **[furnished-render.md](furnished-render.md)** — the furnished digital-twin map: to-scale home art aligned once over the live map.
- **[animal-svg.md](animal-svg.md)** — the companion mascot: the declarative animal descriptor, codegen, and the community submission pipeline.
- **[dashboard-card.md](dashboard-card.md)** — the `vacuum-agent-dashboard` drop-in card in depth: arm-then-Start dispatch, embedded map, profiles, and scenes.

---

## The Mixin Pattern

### Why prototype mixins rather than a component framework

The card is a single Web Component (`<eufy-vacuum-command-center>` — `CARD_NAME` in `src/constants.js`, registered at the bottom of `main.js` with `customElements.define`; a second element, `${CARD_NAME}-editor`, is the visual config editor). There is no virtual DOM, no JSX, no component tree. Everything the card owns renders into its one shadow root — with two deliberate exceptions, the `document.body`-level **modal host** and **toast host**, which exist only because a shadow-root child cannot out-stack a body-level sibling (see [event-binding-and-modal-host.md](event-binding-and-modal-host.md)).

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

**Actions** (`src/actions/`) — every service call the *panel card* makes goes through one place: `proto.callService(domain, service, data = {}, returnResponse = false)` in `src/actions/core.js`, which the domain modules all wrap. (The two standalone Lovelace cards are outside this object and call `hass.callService` directly — see [card-topology-and-bundles.md](card-topology-and-bundles.md).) No action method may touch the DOM or mutate state except by returning data that the caller (main.js or a binding) stores into state.

**State** (`src/state/`) — holds two kinds of data. The first is derived from `hass.states` (vacuum entity, switch entities, number entities, sensor attributes). The second is transient UI state stored as plain properties on the instance (e.g. `_startStatus`, `_dockActionStatus`, editor open/close flags). State modules expose read methods; main.js writes to them by calling named setters or assigning directly to well-known properties.

**Renderers** (`src/renderers/`) — pure functions that take the render context object and return HTML strings. They read from state but never write to it and never call services. Their UI text is not English literals but localized through the [i18n system](i18n-system.md) (`this.t` / `this.tVocab`), per the user's chosen language.

**Bindings** (`src/bindings/`) — called after every render, via `bindEvents()` in `src/bindings/index.js` (one `this._bind*()` call per binding module, in a fixed order). They query the shadow DOM for data-attribute selectors and attach event handlers. Event handlers call actions or state mutators, then call `_scheduleRender()`.

### Who holds what — the four constructors

The four objects do **not** share a receiver shape, and the difference is load-bearing: an action reaching for `this.card` gets `undefined`, which is how a real bug (`clearRoomAccessGraph` calling `this.selectedVacuum()`) shipped.

| Object | Constructed in | Signature | Reaches the rest via |
|---|---|---|---|
| `VacuumCardState` | `setConfig` | `(hass, config)` | `this.hass`, `this.config` — nothing else |
| `VacuumCardActions` | `setConfig` | `(hass, state)` | `this.hass`, `this.state` — **no `this.card`** |
| `VacuumCardRenderers` | `setConfig` | `(card)` | `this.card._state`, `this.card._actions`, … |
| `VacuumCardBindings` | `setConfig` | `(card)` | `this.card._state`, `this.card._actions`, … |

`state` and `actions` are re-pointed on every HA update by `sync()` (`this._state.sync(hass, config)` / `this._actions.sync?.(hass, this._state)` in the `hass` setter); `renderers` and `bindings` hold the card itself, so they need no re-sync in the normal path (each still exposes a `sync(card)` for a re-created card instance). Bindings have no `t` of their own — `t` / `tRaw` / `esc` on `VacuumCardBindings` delegate to `card._renderers`.

**A fifth object — the controller.** Beyond the four render-cycle layers, `LearningController` (`src/controllers/learning-controller.js`, constructed in `setConfig` and driven by `connectedCallback` / `disconnectedCallback` → `connect()` / `disconnect()`) centralizes the event-driven live-job logic. It subscribes to **five** HA events for the configured vacuum — `eufy_vacuum_room_completed`, `eufy_vacuum_room_started`, `eufy_vacuum_room_finished`, `eufy_vacuum_job_finished`, `eufy_vacuum_run_incomplete` — and owns ETA reanchoring, the 5 s bounds-exit poll, the 1 s job-progress ticker, the per-room progress snapshot read by the renderers, and the queue-independent `loadRoomEstimates()` fetch. Every handler drops events whose `data.vacuum_entity_id` isn't this card's. `connect()` is idempotent (early-returns if any subscription is live); `disconnect()` unsubscribes all five and clears all three timers. The `learning` state module holds the data; the controller drives the updates.

### Strict data flow

```
hass setter → state.sync() → _scheduleRender()
                                    ↓
                            _render() builds ctx
                                    ↓
                         renderers read state → HTML string
                                    ↓
                    innerHTML set on view root — only if the
                    string differs from dataset.renderedHtml
                                    ↓
                         bindings.bindEvents() attaches handlers
                                    ↓
user action → binding handler → action.callService() + state mutator → _scheduleRender()
```

The innerHTML step is **diffed, not unconditional**: the header, bottom nav, mobile overlay, active view root, and modal host each cache their last markup in `dataset.renderedHtml` and skip the swap when it is unchanged. `bindEvents()` still runs on every render, which is why the `_on` / `_onAll` helpers are idempotent — a same-markup render keeps its live elements, so a raw `addEventListener` would stack a duplicate listener each time. (The modal host is the exception that proves it: it binds *only* inside the swap branch.)

State modules never call each other. If module A needs data that module B owns, it goes through the card instance, which owns all four layer objects — bindings and renderers reach it as `this.card._state` / `this.card._actions`; actions hold `this.state` directly and have no card reference at all (see the constructor table above).

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

The two lists are not interchangeable and the second edit is not optional. `VIEW_ORDER` is what `_ensureShellFrame()` maps over to pre-create the view-root divs, and it compares `Object.keys(viewRoots).length !== VIEW_ORDER.length` to decide the frame is missing — a view in `VIEWS` but not in `VIEW_ORDER` has no root to render into. (One entry is deliberately in `VIEWS` only: `MAPPING_ARCHIVE`, the retired Mapping view, kept so `setView` and the persisted-view restore can recognise the stored string and reroute it to Rooms.) See [render-cycle.md](render-cycle.md) for how the two drive routing.

### Step 2: Add a nav tab (`src/render-cycle.js`, `renderHeader()`)

Inside the `<div class="evcc-nav">` section of `renderHeader()`, add:

```js
<button class="evcc-nav-tab ${view === VIEWS.MY_PANEL ? "active" : ""}"
        data-view="${VIEWS.MY_PANEL}">
  ${renderers.t("nav.tab_my_panel")}
</button>
```

The label goes through `renderers.t` like every other tab — a literal here is an untranslated string in 18 locales (see [i18n-system.md](i18n-system.md)).

Two things this step does *not* cover:

- **The mobile shell has its own nav.** `renderHeader()` is the desktop path only; `_render()` forks on viewport and calls `renderMobileBottomNav()` instead. A new panel needs an entry in `PRIMARY_MOBILE_TABS` (bottom bar, 4 slots) or `OVERFLOW_MOBILE_TABS` (the "More" sheet) in `src/renderers/mobile-shell.js`, or it is unreachable on mobile — the state `MAP_CONFIG` is in on purpose, reachable from the overflow sheet with no desktop tab at all.
- **Capability gating is a separate switch.** Both nav surfaces filter through `isViewAvailable(view, state)` (`src/render-cycle.js`), the single predicate shared by the desktop header, the mobile shell, the `setView` guard, and the `_render` fallback. Its default is `true`; add a clause only if the panel depends on an adapter capability. Hiding a tab does not remove the view root — `setView` and `_render` independently reroute a hidden view to Rooms.

### Step 3: Add a case to the view router (`src/render-cycle.js`, `renderView()`)

```js
case VIEWS.MY_PANEL:
  return renderers.renderMyPanelView?.(ctx)
    ?? `<div class="evcc-empty">${renderers.t("nav.unavailable_my_panel")}</div>`;
```

`renderView(ctx)` is the `switch(view)` router covered in [render-cycle.md](render-cycle.md). The `?.` / `??` pair is the convention, not defensive noise: every case tolerates a renderer that failed to mix in, and `_render()` wraps the whole call in a try/catch that falls back to `shell.view_error` so one throwing view cannot blank the card.

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
    this.card._onAll("[data-action='my-action']", "click", async () => {
      await this.card._actions.myAction();
      this.card._scheduleRender();
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

Use `card._onAll` (or `card._on` for a single element) rather than raw `addEventListener`: they are idempotent per element+event, which is what makes re-binding safe against the diffed render described above — see [event-binding-and-modal-host.md](event-binding-and-modal-host.md).

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

The convention is a **pair**: a public `async refresh*()` that does the fetch → store → render, and a private `_schedule*Refresh()` that debounces it behind a short timer. Splitting them is what lets an event handler or a binding force a refresh immediately (`card.refreshMyPanel()`) while the `hass` setter — which fires on every HA state update — only ever arms the timer.

```js
async refreshMyPanel() {
  if (!this._state || !this._actions) return null;
  const payload = await this._actions.getMyPanelData();
  if (!payload || !this._state) return null;
  this._state.setMyPanelData(payload);
  this._scheduleRender();
  return payload;
}

_scheduleMyPanelRefresh() {
  if (!this._state || !this._actions) return;
  if (this._view !== VIEWS.MY_PANEL) return;      // view-gated: don't poll a hidden panel

  clearTimeout(this._myPanelTimer);
  this._myPanelTimer = setTimeout(() => {
    this.refreshMyPanel();
  }, 500);
}
```

Then seed `this._myPanelTimer = null` in the constructor, and call `_scheduleMyPanelRefresh()` from the `hass` setter's scheduler block **and** from the matching `if (view === VIEWS.MY_PANEL)` branch in `setView()` — the `hass`-setter call is a no-op while the panel is hidden, so the `setView` call is what fetches on first open. The `hass`-setter debounce/load-once pattern these schedulers follow is covered in [state-management.md](state-management.md).

**Then add `clearTimeout(this._myPanelTimer)` to `disconnectedCallback()`.** This is not optional tidying, and the reason is easy to get wrong: teardown does **not** null `_state` / `_actions` / `_config` / `_hass` / `_renderers`, so the `if (!this._state) return` guard at the top of every refresh helper — which only ever covered the pre-`setConfig` window — passes on a detached card. A surviving timer therefore runs its whole body: a real `hass.callService` for a card that no longer exists, then `_scheduleRender()`, whose `_render()` clears the same guard and re-enters `_updateModalHost` / `_updateToastHost` — both create-if-missing — re-appending to `document.body` the hosts `disconnectedCallback` had just removed. Any timer you add must be cancelled here; `disconnectedCallback`'s list is the invariant, and the check is that every `this._*Timer` assigned anywhere in `main.js` appears in it.
