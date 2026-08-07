# Event Binding & the Modal Host

This is the deep dive on the card's **binding layer** and its **body-portal modal host** — the one
runtime seam that [Card Architecture](architecture-overview.md) gestures at but never details.

Read first, then come back:
- **[render-cycle.md](render-cycle.md)** owns the render cycle (`_scheduleRender` microtask
  dedup, the 8-step `_render()` sequence, the "innerHTML replaced → listeners discarded →
  `bindEvents()` re-attaches from scratch" invariant). This doc does **not** re-teach that.
- **[architecture-overview.md](architecture-overview.md)** owns the four-layer prototype-mixin pattern
  (actions / state / renderers / bindings).
- **[Frontend Module Reference](module-reference.md)** owns the full `src/bindings/*.js`
  file map. Section 1 below is a wiring index, not a replacement for it.

Everything here is the **delta**: the `_on`/`_onAll` binding helpers, the `document.body` modal
portal, and the trigger surface that drives re-renders outside the `hass` setter.

---

## 1. The binding layer at a glance

`this._bindings.bindEvents()` runs at the **end of every `_render()`** (`main.js:1464`), after the
shadow-root HTML has been (conditionally) swapped and after `_updateModalHost()`. Why re-binding
from scratch is safe is [render-cycle.md](render-cycle.md)'s invariant — not repeated here.

`bindEvents()` is a flat fan-out: 21 `_bind*` calls in a fixed order (`bindings/index.js:121-141`).
Each `_bind*` lives in its own module, mixed onto `VacuumCardBindings.prototype` by the
`apply*Bindings(...)` calls at `bindings/index.js:407-426` — with **one exception**: `_bindToasts` is
defined **inline** in `index.js:149` (there is no `toasts.js` module and no `applyToastsBindings`
import). Modules that own a large region sub-bind
further (e.g. `_bindMap` → 17 sub-binders at `bindings/map.js:81-97`; `_bindRoomEditor` → 5 at
`bindings/room-editor.js:22-26`).

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
| `job-summary.js` | `_bindJobSummary` | Learning Review job-card launch surface + **job-summary modal (host)** — see §4a |
| `room-editor.js` | `_bindRoomEditor` | Room-editor **modal (host)** — see §4 |
| `room-rules.js` | `_bindRoomRules` | Per-room rules |
| `theme.js` | `_bindThemeEditor` | Theme editor + **theme-JSON modal (host)** |
| `map.js` | `_bindMap` | Live map, zones, furnished art (17 sub-binders) |
| `setup.js` | `_bindSetup` | Setup / onboarding view |
| `mobile-shell.js` | `_bindMobileShell` | Mobile overlay + bottom sheet |
| _(inline in `index.js:149`)_ | `_bindToasts` | Binds `[data-action='dismiss-toast']` via shadow-root `_onAll` — but toasts render only into the body-level toast host (`renderers/toasts.js`, called solely from `_updateToastHost`), so this shadow-root query never matches a live element; the dismiss button that actually works is wired manually in `_updateToastHost` (see §3) |

**Where does the module list live?** `bindEvents()` at `bindings/index.js:121-141` is the single
source of truth for *order*; `bindings/index.js:407-426` is the source of truth for *which modules
exist*. Add a bindings module → register it in both. (The lone inline `_bindToasts` at `index.js:149`
is the exception — it appears in the order list but has no module file or import.)

---

## 2. The `_on` / `_onAll` helpers

Installed **onto the card instance** (not the bindings object) by `applyCardDomHelpers(this)`, called
once in the constructor at `main.js:127` — before any binding module runs, because every module
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
  tree. **Re-query inside handlers, never stash.** See `bindings/map.js:2735` ("Re-query each paint so
  a mid-drag re-render doesn't strand a detached node") for the canonical fix.
- **Adding a second `_on` for the same element+event** → silently dropped (it's idempotent). The
  map container multiplexes zone-draw / hide-area-draw / pan through **one** `pointerdown` handler
  precisely because a second `pointerdown` bind is a no-op — the handler's own comment names it
  the "drag does nothing" bug (`bindings/map.js:2718-2723`, restated at `:2770` for the hide-area
  branch).

---

## 3. The body-portal modal host

`card._modalHost` is a `<div class="evcc-modal-host">` created with `document.createElement` and
appended to **`document.body`** (`main.js:1606-1609`) — a portal node **outside the shadow root**.

**Why it exists.** A modal must escape the card's stacking and overflow context to sit above HA
chrome and not be clipped by the card's own `overflow`. A node inside the shadow root can't reliably
out-stack the dashboard; a body-level node with `z-index: 9999` (`styles/index.js:243`, in `MODAL_HOST_STYLES`) can.

**Why it needs its own bind path.** `_onAll` queries `this.shadowRoot` (`core.js:62`), so it can
**never match a body-portal node**. The modal binder therefore queries the host directly —
`host.querySelector(...)` / `host.querySelectorAll(...)` — and attaches **raw `addEventListener`**
(`bindModalHostEvents`, `bindings/index.js:167-347`), bypassing `_on`'s idempotency entirely. (One
module quietly breaks this generalization: `_bindJobSummaryHost` queries the host directly like
everyone else, but then calls `this.card._on(el, ...)` on the result instead of raw
`addEventListener` — `_on` itself is generic over any element, not shadow-root-bound, so this
still works; see §4a.)

**How idempotency is recovered — at the swap boundary, not per-listener.** `_updateModalHost()`
(`main.js:1543-1647`) rebuilds the host markup each render, then calls `bindModalHostEvents(host)`
**only inside the `if (this._modalHost.dataset.renderedHtml !== modalMarkup)` branch**
(`main.js:1624-1646`). So bindings run only after an actual `innerHTML` swap that recreates every
modal element (dropping old listeners). A same-markup re-render — e.g. a background battery/status
push while a modal sits open — skips the swap **and** the re-bind, so raw `addEventListener` never
stacks duplicates. The `main.js:1639-1644` comment spells this out. (The swap also preserves each
open modal body's `scrollTop` by index, `main.js:1628-1637`, so an in-modal interaction — a room
pick, a setting tap — doesn't jump the modal back to the top.)

**Host stamps.** Because a body-mounted node inherits neither the card's text direction nor its
typeface token, `_updateModalHost` stamps both on the host before injecting markup: `applyDir(...)`
with the resolved language (`main.js:1615`) and the `data-evcc-font` attribute
(`_applyFontAttributeTo`, `main.js:1621` — see [styles-system §4](styles-system.md)). The toast
host gets the same two stamps (`main.js:1720`, `:1726`).

**Lifecycle:**
- **Created** lazily the first render any modal markup is non-empty (`main.js:1606-1609`).
- **Torn down mid-session** the moment *all* modal markup is empty: `_updateModalHost` does
  `this._modalHost.remove(); this._modalHost = null;` (`main.js:1599-1602`) — the whole portal is
  discarded, taking its raw listeners with it. There is **no per-listener teardown**; listeners die
  with their nodes.
- **Torn down on unmount** in `disconnectedCallback` (`main.js:1839-1847`), which removes and nulls
  both `_modalHost` and the parallel `_toastHost`.

**Leak consideration.** Because the host lives on `document.body`, it survives the card being pulled
from the DOM unless explicitly removed. Any *new* body-level host you add **must** be torn down in
`disconnectedCallback` or it orphans on `<body>` after card removal / dashboard nav. The ESC keydown
follows the same discipline: a single `document`-level listener (handler defined in the constructor,
`main.js:92`) anchored once in `connectedCallback` (`main.js:1771`) and removed symmetrically in
disconnect (`main.js:1832`) — deliberately **not** re-attached per modal render.

**Dialog-within-modal stacking.** Confirm/alert/prompt markup is concatenated **last** in the modal
markup string (`main.js:1596`; the ordering rationale is commented at `:1584-1585`), so it stacks
above the modal that spawned it, and it carries its **own** `[data-evcc-dialog]` stop-propagation
because the generic backdrop stop-propagation (`bindings/index.js:171-174`) only catches the
*first* modal (`_bindDialogHost`, `bindings/index.js:363-366`). Miss this and a dialog click leaks to
the backdrop and closes the modal beneath it.

**Toast host** is the parallel body-level host (`_updateToastHost`, `main.js:1702-1747`), `z-index: 10000`
(`styles/index.js:946`) to sit above the modal host's `9999`. Since it's outside the shadow root, `_on`/`_onAll` can't see it either, so
its dismiss button wires with a **manual `dataset.evccBoundClick` guard** (`main.js:1737-1739`). Any
code touching the toast or modal hosts must replicate that manual idempotency — the shadow-root
helpers won't cover them.

---

## 4. The per-room-color trap (worked example)

This is the canonical "which bind path?" decision, and it shipped as a real bug.

The room editor's field handlers exist on the **shadow-root path**: `_bindRoomEditorFields` at
`bindings/room-editor.js:356` binds `[data-field]` via `this.card._onAll(...)`. But the room
editor **renders into the body-level `_modalHost`**, not the shadow root
(`renderRoomEditorModal`, wired from `main.js:1549-1552`). Because `_onAll` queries only the shadow
root (`core.js:62`), those `_onAll` handlers matched **nothing** — the room-color `<input>` (and its
Reset button) had no listener, so edits silently vanished.

The file itself flags the trap, verbatim at `bindings/room-editor.js:376-378`:

> NB: the room editor is a BODY-LEVEL modal, so its fields are actually bound in
> `bindModalHostEvents()` (bindings/index.js) via `host.querySelectorAll` — the room-color input +
> reset live there too. Shadow-root `_onAll` here would never match the modal.

The fix binds them in the **host path**: the color `<input>` lives in `bindModalHostEvents` at
`bindings/index.js:271-279` (`input` for live preview, `change` to commit — see §5), and its Reset
button at `:282-288`, both using `host.querySelectorAll(...)` + `addEventListener`.

**Decision rule.** Rendered into the shadow root → bind with `card._on`/`_onAll`. Rendered into
`_modalHost` (any `renderXModal`) → bind in `bindModalHostEvents(host)` with `host.querySelectorAll`.
Pick the wrong path and the handler is a **silent no-op** — no error, just dead controls.

---

## 4a. The job-card launch surface (guarded in-card controls)

The Learning Review **job card is itself a button**: the whole `<article
class="evcc-review-job-card">` carries `data-job-summary-open="<jobId>"` plus `role="button"`,
`tabindex="0"`, and an `aria-label` (`renderers/review.js:635-639`) — a div that behaves like a
button must be reachable and announced as one. The **error badge is a plain `<span>` nested inside
that card** (`renderers/review.js:545-556`, emitted at `:645-654`) — it carries no attribute of its
own; a click on it bubbles to the card's own click listener, so the badge and the row both land on
the same Job Summary modal rather than a separate error dialog.

The binding (`bindings/job-summary.js`, shadow path) wires `click` (`:38-44`) and `keydown`
(Enter/Space — keyboard parity for the focusable row, `:49-57`) on `[data-job-summary-open]`,
calling `state.openJobSummary(jobId)`.

**The guard.** The card *contains* live controls — the Exclude/restore buttons and the reason
chips — that do **not** stop propagation (checked, not assumed: an earlier draft claimed they did).
Making the card clickable therefore made every one of them open the modal as a side effect (their
click bubbles to the card's listener the same way the badge's does). The fix is a launch-side guard,
not edits to their handlers: `fromInnerControl(event)` (`job-summary.js:26-33`, matching
`INTERACTIVE_INSIDE_CARD` at `:22-23`) walks
`event.target.closest(...)` against
`"[data-review-action],[data-review-reason-chip],button,a,input,select,textarea,label"` and bails
when the click (or Enter on a focused inner button) came from a control that owns its own
behaviour. The `<article>` itself never matches the selector, so the guard cannot swallow the
card's own clicks — and neither can the badge `<span>`, which also never matches it. Guarding at the
launch site keeps the change inside the feature that introduced the problem.

Closing is host-path: `_bindJobSummaryHost(host)` (`job-summary.js:60-80`, called from
`bindModalHostEvents` at `bindings/index.js:234`) binds `[data-action='close-job-summary']` and an
Escape handler **on the modal element itself** (dies with the node, no document listener). The
modal renders body-level like every other (`renderJobSummaryModal`, `main.js:1586-1589`); its CSS
mostly rides `MODAL_HOST_STYLES` — except the card's own pointer-cursor/hover/styled-focus-ring
rules, which are a body-host casualty (the card falls back to the UA default outline, not to no
outline at all); see [styles-system §2](styles-system.md). This is another §7 "one feature, both
bind paths" case.

---

## 5. Live-vs-commit (`input` vs `change`)

Convention on any native picker or slider: **`input` = live, no render; `change` = commit + render.**
Rendering on `input` swaps the `<input>` DOM node while the OS picker is still open over it,
orphaning it and losing the value.

The per-room color picker is the canonical case (`bindings/index.js:271-279`):

```js
input.addEventListener("input",  () => this.card._state.updateEditorField("color", input.value));            // live, NO render
input.addEventListener("change", () => { this.card._state.updateEditorField("color", input.value);
                                         this.card._scheduleRender(); });                                     // commit + render
```

- **`input`** captures the pick live with **no `_scheduleRender()`** — the card also re-renders on HA
  state pushes, and swapping the `<input>` while its native picker is open drops the pick.
- **`change`** (picker closed) commits **and** re-renders, so the hex swatch + Reset button appear.

Same split elsewhere:
- Layout-name draft input is `"input"` with no render (`bindings/map.js:1287`).
- Map-overlay checkbox commits on `"change"` + optimistic render (`bindings/map.js:111`).
- **Theme editor** (`bindings/theme.js`): `[data-theme-token]` binds both — `"input"` for live apply
  (`theme.js:601` — range sliders flood `input` every drag pixel; skip the backend call here) and
  `"change"` for persistence (`theme.js:658`). The **color** inputs (`[data-theme-color-input]`)
  persist on `"change"` (`theme.js:636`) then call **`_scheduleDeferredRender()`** (`theme.js:655`),
  the 600 ms debounce owned by [render-cycle.md](render-cycle.md), so the modified-badge update
  doesn't fire mid-gesture.

**Inverting the split loses edits:** render on `input` → the field's node is replaced mid-gesture →
focus lost and the in-flight value discarded.

---

## 6. The `_scheduleRender` trigger map (non-`hass`-setter)

Every re-render funnels through `card._scheduleRender()` (microtask dedup — [render-cycle.md](render-cycle.md)).
The `hass` setter's own refresh cascade (debounced service refreshes + load-once flags) is owned by
[state-management.md](state-management.md) — **not restated here**. Below are the triggers that fire a render
*outside* the `hass` setter. The `file:line` column always points at the actual `_scheduleRender()`
(or debounced-render) call site, not the enclosing function's declaration.

| Trigger | Fired by | file:line |
|---|---|---|
| ResizeObserver crosses mobile/desktop boundary | `_boundHandleResize` cb | `main.js:123` |
| `animal-svg-registered` document event | `_boundHandleAnimalRegistered` | `main.js:99` |
| End of `setConfig` | `setConfig` | `main.js:209` |
| Config-pinned external locale (`config.i18n`) loaded | `_maybeLoadLocale` | `main.js:383` |
| Per-user lang override loaded | `_maybeLoadLangOverride` | `main.js:413` |
| Per-user font choice loaded | `_maybeLoadFontChoice` | `main.js:436` |
| Runtime locale catalogs (shipped + drop-in) loaded | `_maybeLoadExternalLocales` | `main.js:500` |
| Language menu toggle / close | language control | `main.js:508` / `515` |
| User picks a language | `setLanguageOverride` | `main.js:529` |
| User picks a typeface | `setUiFont` | `main.js:482` |
| Confirmations auto-clear (registered once, fired by state) | `setConfirmationsRenderTrigger` | `main.js:578` |
| Last-view restored on first sync | `_restoreLastView` | `main.js:687` |
| View switch | `setView` | `main.js:734` |
| Live-map camera poll tick (2000 ms `setInterval`) | `_scheduleLiveMapRefresh` | `main.js:835` |
| Live-pose poll tick (2000 ms `setInterval`) | `_scheduleLivePosePoll` | `main.js:887` / `891` |
| Deferred theme-picker settle (600 ms debounce) | `_scheduleDeferredRender` | `main.js:1353` |
| Toast shown / cleared post-TTL | `showToast` | `main.js:1292` / `1297` |
| Card-native confirm / alert / prompt opened | `_confirm` / `_alert` / `_prompt` | `main.js:1317` / `1326` / `1335` |
| ESC closes dialog / modal | `_handleGlobalKeydown` | `main.js:1677` / `1696` |
| Toast dismiss click (body-level host) | toast host handler | `main.js:1744` |
| Re-mount / panel nav before first hass | `connectedCallback` | `main.js:1795` |
| Animal-svg manifest import resolved | `_loadAnimalSvg` | `main.js:1821` |
| Panel resume (visibility / focus / pageshow / location-changed) | `_handlePanelResume` | `main.js:1880` |

Plus the many refresh-timer resolutions the `hass` cascade *arms* but which fire on their own timers
(start-status `main.js:760`, dashboard-snapshot `790`, dock-action `916`, pause-timeout `931`,
metrics `973`, learning-history `1009`, run-profiles `1042`, saved-zones `1088`, incomplete-run-log
`1117`, trouble-rooms-log `1150`, theme `_loadInitialThemeState` `1257`). External call sites live
throughout `src/bindings/*` and `src/controllers/learning-controller.js`, all invoking `card._scheduleRender()`
on the same batched path (e.g. `bindings/external-jobs.js:24,34,47,63,74`).

---

## 7. Cliffs — what breaks if you touch it

Binding / modal-host specific. Anything about the render cycle itself is [render-cycle.md](render-cycle.md).

- **Bind on the wrong path (shadow vs body) → silent no-op.** `_onAll` only sees the shadow root
  (`core.js:62`); anything rendered into `_modalHost` must be bound in `bindModalHostEvents`
  (`bindings/index.js:167`). No error — just dead controls. This *is* the §4 room-color trap.
- **A single feature can bind in *both* paths.** `_bindOrder` is the clearest case: the clean-order
  controls bind shadow-side in `order.js`, but the order-selector **modal** actions bind separately in
  `bindModalHostEvents` (`bindings/index.js:193-229`). Editing order bindings means touching **both**
  files — the same shadow-vs-host split as §4, hidden inside one feature. The job-summary feature
  splits the same way (§4a: launch shadow-side, close host-side).
- **Stash a DOM ref across renders → detached node.** Content renders replace `innerHTML`; a cached
  reference is an orphan with dead listeners. Re-query inside handlers (`bindings/map.js:2735`).
- **Raw `addEventListener` in a per-render bind path → duplicate handlers each render.** Only the
  body-level hosts may use raw `addEventListener`, and only because they carry their own guards
  (host swap-gate `main.js:1624`; toast `dataset.evccBoundClick` `main.js:1737-1739`). Everything in
  the shadow root goes through `card._on`/`_onAll`.
- **A second `_on` for the same element+event → dropped.** `_on` is idempotent (`core.js:98-112`).
  Multiplex through one handler (`bindings/map.js:2718-2723` — zone-draw / hide-area-draw / pan share
  ONE `pointerdown`); don't expect a second bind to land.
- **Body-level host not torn down → leak.** `_modalHost` / `_toastHost` live on `document.body` and
  survive card removal. `disconnectedCallback` (`main.js:1839-1847`) must remove+null every one. Same
  for any document-level listener (ESC anchored `main.js:1771`, removed `main.js:1832`).
- **`input`-vs-`change` inverted → lost edits / stolen focus.** Render on `input` and you swap the
  `<input>` mid-gesture (`bindings/index.js:271-279`). `input` = live/no-render, `change` =
  commit/render.
- **Dialog stop-propagation missing → modal closes underneath.** A dialog stacked in the host needs
  its own `[data-evcc-dialog]` stop-propagation; the generic one catches only the first modal
  (`_bindDialogHost`, `bindings/index.js:363-366`).
- **Double-click disambiguation** (the 220 ms timer) is a render-cycle cliff, not a binding one —
  see [render-cycle.md](render-cycle.md).
