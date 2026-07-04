# Event Binding & the Modal Host

This is the deep dive on the card's **binding layer** and its **body-portal modal host** — the one
runtime seam that [Card Architecture](architecture-overview.md) gestures at but never details.

Read first, then come back:
- **[19 §3.1–3.2](architecture-overview.md)** owns the render cycle (`_scheduleRender` microtask
  dedup, the 8-step `_render()` sequence, the "innerHTML replaced → listeners discarded →
  `bindEvents()` re-attaches from scratch" invariant). This doc does **not** re-teach that.
- **[19 §2.2](architecture-overview.md)** owns the four-layer prototype-mixin pattern
  (actions / state / renderers / bindings).
- **[Frontend Module Reference](module-reference.md)** owns the full `src/bindings/*.js`
  file map. Section 1 below is a wiring index, not a replacement for it.

Everything here is the **delta**: the `_on`/`_onAll` binding helpers, the `document.body` modal
portal, and the trigger surface that drives re-renders outside the `hass` setter.

---

## 1. The binding layer at a glance

`this._bindings.bindEvents()` runs at the **end of every `_render()`** (`main.js:1400`), after the
shadow-root HTML has been (conditionally) swapped and after `_updateModalHost()`. Why re-binding
from scratch is safe is [19 §3.2](architecture-overview.md)'s invariant — not repeated here.

`bindEvents()` is a flat fan-out: 21 `_bind*` calls in a fixed order (`bindings/index.js:105-127`).
Each `_bind*` lives in its own module, mixed onto `VacuumCardBindings.prototype` by the
`apply*Bindings(...)` calls at `bindings/index.js:384-403` — with **one exception**: `_bindToasts` is
defined **inline** in `index.js:149` (there is no `toasts.js` module and no `applyToastsBindings`
import). Modules that own a large region sub-bind
further (e.g. `_bindMap` → 16 sub-binders at `bindings/map.js:52-77`; `_bindRoomEditor` → 5 at
`bindings/room-editor.js:21-27`).

| Module (`src/bindings/`) | `_bind*` entry | Region / view it wires |
|---|---|---|
| `nav.js` | `_bindNav` | Header nav tabs, bottom-nav, view switching |
| `language.js` | `_bindLanguage` | Language control menu + per-user override |
| `base-station.js` | `_bindBaseStation` | Base Station view controls |
| `maintenance.js` | `_bindMaintenance` | Maintenance view + **maintenance-item modal (host)** |
| `metrics.js` | `_bindMetrics` | Metrics view |
| `order.js` | `_bindOrder` | Clean-order controls + **order-selector modal (host)** |
| `run-profiles.js` | `_bindRunProfiles` | Run-profiles view |
| `saved-zones.js` | `_bindSavedZones` | Saved-zones view |
| `review.js` | `_bindReview` | External-run review |
| `external-jobs.js` | `_bindExternalJobs` | External-jobs list + **wizard modal (host)** |
| `rooms.js` | `_bindRooms` | Rooms view (the default view) |
| `room-access.js` | `_bindRoomAccess` | Room include/exclude + **room-access modal (host)** |
| `room-estimate.js` | `_bindRoomEstimate` | Room-estimate + **estimate modal (host)** |
| `room-editor.js` | `_bindRoomEditor` | Room-editor **modal (host)** — see §4 |
| `room-rules.js` | `_bindRoomRules` | Per-room rules |
| `theme.js` | `_bindThemeEditor` | Theme editor + **theme-JSON modal (host)** |
| `map.js` | `_bindMap` | Live map, zones, furnished art (16 sub-binders) |
| `setup.js` | `_bindSetup` | Setup / onboarding view |
| `mapping-review.js` | `_bindMappingReview` | Mapping-review view |
| `mobile-shell.js` | `_bindMobileShell` | Mobile overlay + bottom sheet |
| _(inline in `index.js:149`)_ | `_bindToasts` | Toast host (body-level — see §3) |

**Where does the module list live?** `bindEvents()` at `bindings/index.js:105-127` is the single
source of truth for *order*; `bindings/index.js:384-403` is the source of truth for *which modules
exist*. Add a bindings module → register it in both. (The lone inline `_bindToasts` at `index.js:149`
is the exception — it appears in the order list but has no module file or import.)

---

## 2. The `_on` / `_onAll` helpers

Installed **onto the card instance** (not the bindings object) by `applyCardDomHelpers(this)`, called
once in the constructor at `main.js:124` — before any binding module runs, because every module
calls `this.card._on(...)`.

**Signatures** (`bindings/core.js:54-122`):

```js
card.$(selector)                              // shadowRoot.querySelector  → Element | null
card.$all(selector)                           // shadowRoot.querySelectorAll → Element[]
card._on(el, event, handler, options)         // single element; no-ops on null el
card._onAll(selector, event, handler, options)// $all(selector).forEach(el => _on(el, ...))
```

**The root is always the shadow root.** `$`/`$all` query `this.shadowRoot` (`core.js:55,62`), so
`_onAll` can only ever reach nodes **inside the shadow root**. This is the whole reason the modal
host needs a separate path (§3).

**Direct listeners, not delegation.** `_on` calls `addEventListener` on the element itself
(`core.js:113`) — one real listener per element/event, no event delegation. A `data-*` selector maps
to a handler by matching elements in the shadow root and attaching to each:
`card._onAll("[data-action='toggle-overlay']", "change", handler)`.

**Idempotency is what makes "re-bind every render" work — with no manual `removeEventListener`.**
`bindEvents()` re-runs every render, so a naïve `addEventListener` would stack N listeners on any
element the render *didn't* replace. `_on` prevents that two ways (`core.js:96-114`):

- **Elements with `dataset`** get a per-event marker attribute, e.g. `el.dataset.evccBoundClick = "1"`;
  a second `_on` for the same element+event bails (`core.js:98-101`). An `innerHTML` wipe produces a
  **fresh element with no marker**, so the next bind attaches correctly. This is exactly why the
  DOM-wiped-every-render model is safe.
- **Hosts without `dataset`** (ShadowRoot / Document / Window) fall back to a module-level
  `WeakMap` `_boundEventsMap` keyed by host → `Set` of event names (`core.js:40,103-112`). These
  hosts survive render cycles, so the entry persists for their lifetime — intended.

**What breaks if you bypass these helpers:**
- **Raw `el.addEventListener(...)` in a per-render bind path** → duplicate listeners stack every
  render (double-firing saves, N file pickers per click). The `core.js:70-77` comment names this
  exact failure. The only places raw `addEventListener` is legitimate are the **body-level hosts**
  (§3), which live outside the shadow root and carry their own guards.
- **Caching a DOM node across renders** → you're holding a *detached* node. On a content render its
  `innerHTML` was replaced; your reference points at an orphan with dead listeners that isn't in the
  tree. **Re-query inside handlers, never stash.** See `bindings/map.js:2178` ("Re-query each paint so
  a mid-drag re-render doesn't strand a detached node") for the canonical fix.
- **Adding a second `_on` for the same element+event** → silently dropped (it's idempotent). The
  map container multiplexes zone-draw / hide-draw / pan through **one** `pointerdown` handler
  precisely because a second `pointerdown` bind is a no-op (`bindings/map.js:2161-2166` — the
  "drag does nothing" bug).

---

## 3. The body-portal modal host

`card._modalHost` is a `<div class="evcc-modal-host">` created with `document.createElement` and
appended to **`document.body`** (`main.js:1537-1540`) — a portal node **outside the shadow root**.

**Why it exists.** A modal must escape the card's stacking and overflow context to sit above HA
chrome and not be clipped by the card's own `overflow`. A node inside the shadow root can't reliably
out-stack the dashboard; a body-level node with `z-index: 9999` (`styles/index.js:229`, in `MODAL_HOST_STYLES`) can.

**Why it needs its own bind path.** `_onAll` queries `this.shadowRoot` (`core.js:62`), so it can
**never match a body-portal node**. The modal binder therefore queries the host directly —
`host.querySelector(...)` / `host.querySelectorAll(...)` — and attaches **raw `addEventListener`**
(`bindings/index.js:152-323`), bypassing `_on`'s idempotency entirely.

**How idempotency is recovered — at the swap boundary, not per-listener.** `_updateModalHost()`
(`main.js:1479-1567`) rebuilds the host markup each render, then calls `bindModalHostEvents(host)`
**only inside the `if (this._modalHost.dataset.renderedHtml !== modalMarkup)` branch**
(`main.js:1544-1565`). So bindings run only after an actual `innerHTML` swap that recreates every
modal element (dropping old listeners). A same-markup re-render — e.g. a background battery/status
push while a modal sits open — skips the swap **and** the re-bind, so raw `addEventListener` never
stacks duplicates. The `main.js:1559-1564` comment spells this out.

**Lifecycle:**
- **Created** lazily the first render any modal markup is non-empty (`main.js:1537-1540`).
- **Torn down mid-session** the moment *all* modal markup is empty: `_updateModalHost` does
  `this._modalHost.remove(); this._modalHost = null;` (`main.js:1529-1535`) — the whole portal is
  discarded, taking its raw listeners with it. There is **no per-listener teardown**; listeners die
  with their nodes.
- **Torn down on unmount** in `disconnectedCallback` (`main.js:1750-1758`), which removes and nulls
  both `_modalHost` and the parallel `_toastHost`.

**Leak consideration.** Because the host lives on `document.body`, it survives the card being pulled
from the DOM unless explicitly removed. Any *new* body-level host you add **must** be torn down in
`disconnectedCallback` or it orphans on `<body>` after card removal / dashboard nav. The ESC keydown
follows the same discipline: a single `document`-level listener (handler defined in the constructor,
`main.js:89`) anchored once in `connectedCallback` (`main.js:1682`) and removed symmetrically in
disconnect (`main.js:1743`) — deliberately **not** re-attached per modal render.

**Dialog-within-modal stacking.** Confirm/alert/prompt markup is concatenated **last** so it stacks
above the modal that spawned it (`main.js:1520-1527`), and it carries its **own**
`[data-evcc-dialog]` stop-propagation because the generic backdrop stop-propagation only catches the
*first* modal (`bindings/index.js:331-343`). Miss this and a dialog click leaks to the backdrop and
closes the modal beneath it.

**Toast host** is the parallel body-level host (`main.js:1622-1657`), `z-index: 10000`
(`styles/index.js:913`) to sit above the modal host's `9999`. Since it's outside the shadow root, `_on`/`_onAll` can't see it either, so
its dismiss button wires with a **manual `dataset.evccBoundClick` guard** (`main.js:1648-1650`). Any
code touching the toast or modal hosts must replicate that manual idempotency — the shadow-root
helpers won't cover them.

---

## 4. The per-room-color trap (worked example)

This is the canonical "which bind path?" decision, and it shipped as a real bug.

The room editor's field handlers exist on the **shadow-root path**: `_bindRoomEditorFields` at
`bindings/room-editor.js:354-377` binds `[data-field]` via `this.card._onAll(...)`. But the room
editor **renders into the body-level `_modalHost`**, not the shadow root
(`renderRoomEditorModal`, wired from `main.js:1485-1488`). Because `_onAll` queries only the shadow
root (`core.js:62`), those `_onAll` handlers matched **nothing** — the room-color `<input>` (and its
Reset button) had no listener, so edits silently vanished.

The file itself flags the trap, verbatim at `bindings/room-editor.js:374-377`:

> NB: the room editor is a BODY-LEVEL modal, so its fields are actually bound in
> `bindModalHostEvents()` (bindings/index.js) via `host.querySelectorAll` — the room-color input +
> reset live there too. Shadow-root `_onAll` here would never match the modal.

The fix binds them in the **host path**: the color `<input>` and Reset live in
`bindModalHostEvents` at `bindings/index.js:255-272`, using `host.querySelectorAll(...)` +
`addEventListener`.

**Decision rule.** Rendered into the shadow root → bind with `card._on`/`_onAll`. Rendered into
`_modalHost` (any `renderXModal`) → bind in `bindModalHostEvents(host)` with `host.querySelectorAll`.
Pick the wrong path and the handler is a **silent no-op** — no error, just dead controls.

---

## 5. Live-vs-commit (`input` vs `change`)

Convention on any native picker or slider: **`input` = live, no render; `change` = commit + render.**
Rendering on `input` swaps the `<input>` DOM node while the OS picker is still open over it,
orphaning it and losing the value.

The per-room color picker is the canonical case (`bindings/index.js:252-263`):

```js
input.addEventListener("input",  () => this.card._state.updateEditorField("color", input.value));            // live, NO render
input.addEventListener("change", () => { this.card._state.updateEditorField("color", input.value);
                                         this.card._scheduleRender(); });                                     // commit + render
```

- **`input`** captures the pick live with **no `_scheduleRender()`** — the card also re-renders on HA
  state pushes, and swapping the `<input>` while its native picker is open drops the pick.
- **`change`** (picker closed) commits **and** re-renders, so the hex swatch + Reset button appear.

Same split elsewhere:
- Layout-name draft input is `"input"` with no render (`bindings/map.js:816-818`).
- Map-overlay checkbox commits on `"change"` + optimistic render (`bindings/map.js:84-101`).
- **Theme editor** (`bindings/theme.js`): `[data-theme-token]` binds both — `"input"` for live apply
  (`theme.js:538` — range sliders flood `input` every drag pixel; skip the backend call here) and
  `"change"` for persistence (`theme.js:595`). The **color** inputs (`[data-theme-color-input]`)
  persist on `"change"` (`theme.js:573`) then call **`_scheduleDeferredRender()`** (`theme.js:592`),
  the 600 ms debounce owned by [19 §3.1](architecture-overview.md), so the modified-badge update
  doesn't fire mid-gesture.

**Inverting the split loses edits:** render on `input` → the field's node is replaced mid-gesture →
focus lost and the in-flight value discarded.

---

## 6. The `_scheduleRender` trigger map (non-`hass`-setter)

Every re-render funnels through `card._scheduleRender()` (microtask dedup — [19 §3.1](architecture-overview.md)).
The `hass` setter's own refresh cascade (debounced service refreshes + load-once flags) is owned by
[19 §4.3](architecture-overview.md) — **not restated here**. Below are the triggers that fire a render
*outside* the `hass` setter.

| Trigger | Fired by | file:line |
|---|---|---|
| ResizeObserver crosses mobile/desktop boundary | `_boundHandleResize` cb | `main.js:120` |
| `animal-svg-registered` document event | `_boundHandleAnimalRegistered` | `main.js:96` |
| End of `setConfig` | `setConfig` | `main.js:206` |
| External locale (`config.i18n`) loaded | `_maybeLoadExternalLocales` | `main.js:380` |
| Per-user lang override loaded | `_maybeLoadLangOverride` | `main.js:409` |
| Runtime locale catalogs loaded | `_maybeLoadLocale` | `main.js:428` |
| Language menu toggle / close | language control | `main.js:436` / `443` |
| User picks a language | `setLanguageOverride` | `main.js:457` |
| Confirmations auto-clear (registered once, fired by state) | `setConfirmationsRenderTrigger` | `main.js:506` |
| Last-view restored on first sync | `_restoreLastView` | `main.js:615` |
| View switch | `setView` | `main.js:665` |
| Live-map camera poll tick (2000 ms `setInterval`) | `_scheduleLiveMapRefresh` | `main.js:766` |
| Live-pose poll tick (2000 ms `setInterval`) | `_scheduleLivePosePoll` | `main.js:818` / `822` |
| Deferred theme-picker settle (600 ms debounce) | `_scheduleDeferredRender` | `main.js:1290` |
| Toast shown / cleared post-TTL | `showToast` | `main.js:1229` / `1234` |
| Card-native confirm / alert / prompt opened | `_confirm` / `_alert` / `_prompt` | `main.js:1254` / `1263` / `1272` |
| ESC closes dialog / modal | `_handleGlobalKeydown` | `main.js:1597` / `1616` |
| Toast dismiss click (body-level host) | toast host handler | `main.js:1655` |
| Re-mount / panel nav before first hass | `connectedCallback` | `main.js:1706` |
| Animal-svg manifest import resolved | `_loadAnimalSvg` | `main.js:1732` |
| Panel resume (visibility / focus / pageshow / location-changed) | `_handlePanelResume` | `main.js:1791` |

Plus the many refresh-timer resolutions the `hass` cascade *arms* but which fire on their own timers
(start-status `main.js:691`, dashboard-snapshot `721`, dock-action `847`, pause-timeout `862`,
metrics `904`, learning-history `939`, run-profiles `988`, saved-zones `1029`, incomplete-run-log
`1058`, trouble-rooms-log `1087`, theme `1194`). External call sites live throughout
`src/bindings/*` and `src/controllers/learning-controller.js`, all invoking `card._scheduleRender()`
on the same batched path (e.g. `bindings/external-jobs.js:24,34,47,63,74`).

---

## 7. Cliffs — what breaks if you touch it

Binding / modal-host specific. Anything about the render cycle itself is [19 §3.1–3.3](architecture-overview.md).

- **Bind on the wrong path (shadow vs body) → silent no-op.** `_onAll` only sees the shadow root
  (`core.js:62`); anything rendered into `_modalHost` must be bound in `bindModalHostEvents`
  (`bindings/index.js:152`). No error — just dead controls. This *is* the §4 room-color trap.
- **A single feature can bind in *both* paths.** `_bindOrder` is the clearest case: the clean-order
  controls bind shadow-side in `order.js`, but the order-selector **modal** actions bind separately in
  `bindModalHostEvents` (`bindings/index.js:178-214`). Editing order bindings means touching **both**
  files — the same shadow-vs-host split as §4, hidden inside one feature.
- **Stash a DOM ref across renders → detached node.** Content renders replace `innerHTML`; a cached
  reference is an orphan with dead listeners. Re-query inside handlers (`bindings/map.js:2178`).
- **Raw `addEventListener` in a per-render bind path → duplicate handlers each render.** Only the
  body-level hosts may use raw `addEventListener`, and only because they carry their own guards
  (host swap-gate `main.js:1544`; toast `dataset.evccBoundClick` `main.js:1648-1650`). Everything in
  the shadow root goes through `card._on`/`_onAll`.
- **A second `_on` for the same element+event → dropped.** `_on` is idempotent (`core.js:98-112`).
  Multiplex through one handler (`bindings/map.js:2161-2166`); don't expect a second bind to land.
- **Body-level host not torn down → leak.** `_modalHost` / `_toastHost` live on `document.body` and
  survive card removal. `disconnectedCallback` (`main.js:1750-1758`) must remove+null every one. Same
  for any document-level listener (ESC anchored `main.js:1682`, removed `main.js:1743`).
- **`input`-vs-`change` inverted → lost edits / stolen focus.** Render on `input` and you swap the
  `<input>` mid-gesture (`bindings/index.js:252-263`). `input` = live/no-render, `change` =
  commit/render.
- **Dialog stop-propagation missing → modal closes underneath.** A dialog stacked in the host needs
  its own `[data-evcc-dialog]` stop-propagation; the generic one catches only the first modal
  (`bindings/index.js:331-343`).
- **Double-click disambiguation** (the 220 ms timer) is a render-cycle cliff, not a binding one —
  see [19 §3.3](architecture-overview.md).
