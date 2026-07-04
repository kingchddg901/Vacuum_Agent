# Styles System

How CSS actually reaches pixels: the combiner that stitches `styles/*.js` into one shadow-root `<style>`, the separate body-host stylesheet the modal/toast portals need, the runtime `--evcc-*` token bridge, and the "all CSS in `src/styles/`" rule with its CI gate.

Scope boundaries — this doc is the DELTA. It does **not** re-cover:
- **[Theme System](theme-system.md)** — the theme *editor*: token hierarchy, palette→token derivation, import/export, token groups/facets.
- **[Frontend Module Reference](module-reference.md)** — the per-file "what each `styles/*.js` is" inventory.
- **[Event Binding & Modal Host](event-binding-and-modal-host.md)** — the body-level modal host node itself (why it's outside the shadow root, z-index, teardown).
- **[Card Topology & Bundles](card-topology-and-bundles.md)** — the three self-contained ESM bundles.
- **[Render Cycle](render-cycle.md)** — floor-texture *rendering* (mask-mode:luminance, marble veins, content-hash cache-bust), and the render cycle whose first step calls `applyThemeToCard`.

---

## 1. The combiner

One CSS string, built once at module-eval time, injected into the shadow root.

**Convention.** Each feature owns one module: `src/styles/<feature>.js` exports a `<feature>Styles` CSS template-string constant. The combiner imports each and pushes it into the `STYLES` array.

- Imports: `src/styles/index.js:22-47`.
- Array + join: `src/styles/index.js:49-78` — `STYLES = [ … ].join("\n")` (`index.js:78`).

**Order matters — two load-bearing positions:**
- **`foundationStyles` is FIRST** (`index.js:50`). It owns the canonical `:host` token block (`foundation.js:120`+); every downstream module consumes `var(--evcc-*)`, so foundation must declare those tokens before anything references them. See §3(A).
- **`MOBILE_STYLES` is LAST** (`index.js:77`). Mobile rules reach shared elements via `.evcc-shell[data-viewport="mobile"]` and must win specificity over the desktop defaults declared above — the comment at `index.js:72-75` spells this out. `externalJobsStyles` sits just before it (`index.js:76`).

**Injection (shadow root).** `STYLES` is imported into `main.js:10`, passed into the frame builder in `_render()` as `this._ensureShellFrame(STYLES)` (`main.js:1329`), and written as a single `<style data-evcc-style-root>${styles}</style>` that is a **direct child of the shadow root — the sibling right before `<ha-card>`** (`main.js:1423`), not inside `ha-card`/`.evcc-shell`.

**Injected ONCE, not per render.** `_ensureShellFrame` only rewrites `shadowRoot.innerHTML` when `missingFrame` is true (`main.js:1417-1442`) — first mount or a HACS-update frame reset. On later renders the existing `[data-evcc-style-root]` block is reused; only header / view-root / nav innerHTML get diffed (`main.js:1364-1397`). So the shadow `<style>` is stable across the card's life.

**Blast radius.** Adding a module means: create `styles/<feature>.js` exporting `<feature>Styles`, `import` it (`index.js:22-47`), and add it to the array (`index.js:49-78`) at the right specificity position. Forget the array entry and the export exists but never ships. This reaches the **command-center panel only** — see Cliff 2.

**Intentional omissions.** Several imported exports are deliberately NOT in the shadow `STYLES` array — `sharedChipStyles` (`index.js:22`), `maintenanceModalHostStyles` (`index.js:35`), `externalWizardModalStyles` (`index.js:45`), `dialogModalStyles` (`index.js:46`). They ride `MODAL_HOST_STYLES` instead (§2).

---

## 2. The body-host style split

The modal host is a `document.body` child, **outside** the card's shadow root (see [35](event-binding-and-modal-host.md)). The shadow `<style>` cascade cannot reach it, so it gets its own stylesheet.

**`MODAL_HOST_STYLES`** — defined `styles/index.js:114`. It interpolates the body-host-only exports:
- `sharedChipStyles` — `index.js:518`
- `maintenanceModalHostStyles`, `roomAccessStyles`, `roomEstimateStyles`, `externalWizardModalStyles`, `dialogModalStyles` — the `${…}` block at `index.js:558-562`.

**Injection site — `_updateModalHost()`** (`main.js:1479-1567`):
- Host div created lazily and appended to `document.body` (`main.js:1537-1541`): `div.evcc-modal-host`.
- Styles prepended inline to the modal markup: `` const modalMarkup = `<style>${MODAL_HOST_STYLES}</style>${html}`; `` (`main.js:1543`), written via `innerHTML` (`main.js:1552`).
- Guarded by a `dataset.renderedHtml` diff (`main.js:1544`) — re-injected only when markup changes. Teardown at `main.js:1530-1532` / `1750-1752`.

**Parallel toast host.** `TOAST_HOST_STYLES` (`index.js:888-959`) is injected the same way in `_updateToastHost` (`main.js:1639`), z-index `10000` to sit above the modal host's `9999`.

**Why the split is load-bearing.** The modal/toast hosts are detached from the card's `:host` cascade, so they neither receive the shadow `<style>` nor inherit the canonical `--evcc-*` seeds. `MODAL_HOST_STYLES` re-derives the whole `--evcc-modal-*` family from canonical tokens on `.evcc-modal-host` (`index.js:166-212`), with a light-scheme companion (`index.js:651-745`), precisely to compensate. This is the modal token derivation bridge, matching `themes/preloaded.py`'s `_build_release_theme_colors()`.

**Adding a body-host style — you MUST touch two places:**
1. Author the rules as a `*ModalHostStyles` export in the feature module (canonical example `styles/maintenance.js:13` `maintenanceModalHostStyles`; also `external-jobs.js` `externalWizardModalStyles`, `dialog.js` `dialogModalStyles`).
2. Interpolate it into `MODAL_HOST_STYLES` at `styles/index.js:558-562`.

Skip step 2 and the export exists but is never injected → the modal renders unstyled with no error. See Cliff 1 for the dead-`modals.js` trap.

---

## 3. The theme-token runtime bridge

Per-render, resolved theme values are written as inline `--evcc-*` custom properties on the live hosts; the stylesheets reference `var(--evcc-*, default)`, so an unset token falls back to its default. Three moving parts: **apply-theme** (writer), the **token registry** (key inventory), and the **default sources** (CSS + JS palette).

### 3.1 The writer — `apply-theme.js`

`applyThemeToCard(card)` (`src/styles/apply-theme.js:32`) is the runtime entry point (the first step of `_render()` — see [render-cycle.md](render-cycle.md)):
- Reads the resolved layer: `state.resolvedTheme()` (`apply-theme.js:36`, guarded at `:34`).
- **Target 1 (card host):** `applyDynamicTheme(card, resolved)` (`apply-theme.js:41`) — vars on the `<eufy-…>` instance that carries `:host`.
- **Target 2 (modal host):** `applyDynamicTheme(card._modalHost, resolved)` (`apply-theme.js:49-51`), only when the modal host is body-attached — because it is detached from `:host` and needs the token layer bridged separately.

**When it runs:** the first effectful call in `_render()` (`main.js:1300`); once post-library-load (`main.js:1193`); plus ~15 event-driven callsites in `bindings/theme.js` (e.g. `:202, :225, :1458`) for immediate editor feedback without waiting for a full render.

**The actual writer — `applyDynamicTheme(card, resolvedTheme)`** (`styles/index.js:88`):
- Iterates `THEME_TOKEN_REGISTRY` and **removes** any prop absent/null/empty in `tokens` (`index.js:94-98`) — so a cleared draft value falls back to the foundation default instead of leaving a stale inline value.
- Then `host.style.setProperty(property, value)` for every present token (`index.js:100-104`).

**Trust boundary:** apply-theme does NOT resolve the cascade — it just writes an already-merged `tokens` map. The default→theme→override layering resolves upstream in `resolvedTheme()` (§3.3).

### 3.2 The token inventory — `THEME_TOKEN_REGISTRY`

A flat array of descriptor entries `{ key, label, group, type, min?, max?, step? }`, exported as a live `let` binding (`theme-tokens/index.js:127`), reassigned by `rebuild()` (`:150`). `rebuild()` flattens static group token-sets + dynamically-built animal tokens (`:132-161`), asserts unique keys (`:113-125, :145`), and also produces `THEME_TOKEN_MAP`, `THEME_GROUP_MAP`, `THEME_GROUPS`. It rebuilds on the `animal-svg-registered` document event (`:169-177`); the live binding means importers see new values with no subscription.

Token definitions come from group-bound factories in `theme-tokens/helpers.js`: `makeTypedGroupToken(group, defaultType)` (`:173`) wrapping `makeGroupedToken` (`:126`). Examples: `mapToken.color` (`helpers.js:176, :208`), `roomToken.number` (rangeless on purpose, `:180, :207`), `roomToken.size` (`:179`); range sugar `.unit/.blur/.angle/.signed` (`:191-194`) over `SCALAR_RANGES` (`:81-91`). `min/max/step` are **editor-only, never persisted** (`helpers.js:139-143`).

**Trust boundary:** the registry is the **key inventory + type/label/range** — it does NOT carry a `default` field. `applyDynamicTheme` iterates it only for the remove-pass (`styles/index.js:47` import, used `:94`). Defaults live in CSS/JS (§3.3). The registry also feeds the editor (`THEME_GROUP_MAP`/`THEME_GROUPS`, out of scope — see [20](theme-system.md)).

### 3.3 Where each default actually lives

There is **no single default source.** When `applyDynamicTheme` removes/never-sets a prop, the stylesheet's `var(--evcc-*, fallback)` resolves it. Three distinct sources by token family:

**(A) Canonical foundation tokens → `:host` block in `styles/foundation.js:120`+.** Declares canonical defaults, e.g. `--evcc-surface-base: var(--card-background-color, #1c2127)` (`:131`), `--evcc-accent: var(--accent-color, #3b82f6)` (`:158`), text/border/semantic/radius/chip tokens. Each chains to an HA theme var first, then a literal — this is the **only** place HA fallbacks are mapped (`foundation.js:12`). A theme overrides by writing an inline prop on the same host.

**(B) Modal-family tokens → derived in `MODAL_HOST_STYLES`.** The body host is detached from `:host`, so `--evcc-modal-*` defaults are re-derived from canonical tokens in `.evcc-modal-host` (`styles/index.js:166-212`, dark) with a light companion (`:661-687` region under the light `@media`). See §2.

**(C) Room-fill tokens → NO CSS default anywhere; default lives in JS + inline `var()` fallback.** `--evcc-room-fill-<N>` is declared in no `:host` block. Instead:
- **SVG path:** `roomFillCss(idx, override)` (`cards/map-room-color.js:71`) emits `var(--evcc-room-fill-<N>, <defaultHex>)` (`:74`), the hex inlined from `ROOM_FILL_PALETTE` (`:19-23`) — CSS resolves it live, a theme token overrides via cascade.
- **Raster path:** `roomFillRgb(idx, host)` (`:101`) reads the computed prop off a mounted node, else `roomFillDefault(idx)` — canvas can't take CSS vars.
- **Editor swatch seed:** because the token carries no default anywhere, `resolvedTheme()` seeds the palette so the picker isn't blank — `state/theme.js:384-388` (`colorMap['--evcc-room-fill-<i+1>'] = ROOM_FILL_PALETTE[i]`, `sources=default`). Comment `theme.js:376-383` notes the seed equals the render's own default, so a themeless card is net-zero.
- Full per-room cascade (override > token > default) documented at `map-room-color.js:5-8`.

**The cascade resolver — `resolvedTheme()` (`state/theme.js:359`)** produces the `{tokens, sources}` apply-theme writes:
- **0. default** — room-fill palette seed (`theme.js:384-388`).
- **1. theme** — active theme's `colors`/`alpha`/`tokens`; `activeTheme = library[effectiveActiveThemeId()]` (`theme.js:372, :393-408`); `effectiveActiveThemeId()` (`:278`) resolves per-device override → backend active fallback.
- **2. draft** — working-draft overlay, highest precedence (`theme.js:413-427`).
- **3. combine** — `_hexWithAlpha()` folds `colorMap`+`alphaMap` into 8-char hex (`theme.js:435-438`).
- Returns `{tokens, sources}` (`:440`); `sources` (default|theme|draft|ha) drives editor provenance only. The foundation `:host` default (A) is NOT in `tokens` — it is the implicit floor CSS applies whenever `resolvedTheme` omits a key.

**One-line bridge:** `_render()` → `applyThemeToCard(this)` (`main.js:1300`) → `resolvedTheme()` merges default(seed)→theme→draft into `{tokens}` (`theme.js:359`) → `applyDynamicTheme` writes/removes inline `--evcc-*` on card + modal host (`styles/index.js:88`) → CSS resolves anything unset via `:host` (A), modal-derived (B), or `var(…,defaultHex)` (C).

---

## 4. Styles-in-styles-only + the CI gate

**The rule**: all CSS lives in `src/styles/`; renderers emit **no** inline `<style>`. Verified — grep for `<style` across `src/renderers/` returns zero matches.

**The one allowed escape hatch:** dynamic `style="--x:…"` attributes that set only CSS custom properties consumed by rules in `src/styles/` (data → CSS, never literal declarations). Sanctioned examples:
- `renderers/map.js:817` — `--seg-color` (room-fill per segment); `:1365` — `--evcc-grp` (group color)
- `renderers/rooms.js:936` — `--job-progress`; `:622` — `--room-progress`
- `renderers/maintenance.js:345, :436` — `--maintenance-remaining` (gauge fill)
- `renderers/floor-texture-surface.js:125` — `--floor-opacity-card` / `--floor-position-card`

**Renderer ↔ styles pairing** is by `evcc-<feature>-*` class convention: a renderer emits `class="evcc-<feature>-*"`, matching rules live in `styles/<feature>.js`, and the module is registered in the combiner (§1). Concrete (`saved-zones`): renderer classes in `renderers/saved-zones.js` (`.evcc-saved-zones-panel :31/:44/:121`, `-header :31`, `-item.is-selected :90`, …) pair with rules in `styles/saved-zones.js` (`.evcc-saved-zones-panel :6`, `-header :18`, `-item.is-selected :119/:131`, …); wired via `import { savedZonesStyles }` (`index.js:34`) + array entry (`index.js:62`). The export is a plain template-string constant (`saved-zones.js:5` → closing backtick `:226`) — exactly the shape the gate checks.

**The gate — `scripts/check-styles.mjs`.** Validates every `src/styles/*.js` (skipping `*.test.js`):
1. **Import-clean** (`:30-35`) — `import()`s each module; a stray backtick / broken template literal throws on import → fail. This catches the original prod bug: truncated CSS that was still valid JS.
2. **Brace-balanced** (`:36-41`) — walks each string export counting `{`/`}`; nonzero depth = truncated literal → fail.
- Exits `1` on any failure (`:44`). Header (`:1-17`) documents the exact incident it guards (dropped nav / header-padding / view-stage `overflow:auto`).

**Runs FIRST in the build** (`package.json:6-7`): both `build` and `build:deploy` are `node scripts/check-styles.mjs && …` — `&&`-chained first, so a new module that fails import or brace-balance blocks the entire build before the card is bundled. Also standalone `check:styles` (`package.json:9`).

**Gate blind spot:** `check-styles.mjs` scans **only** `src/styles/` — it does NOT check the inline `CARD_CSS` in the standalone cards (Cliff 2). A backtick-in-a-comment truncation there would ship silently.

---

## 5. Cliffs

**Cliff 1 — new modal CSS must go in the BODY host, not the shadow bundle.** Add a modal's CSS to any shadow-bundled module (the `STYLES` array, `index.js:49-78`) and the body-portal modal renders **completely unstyled** — no error, just naked markup on `document.body`. The live modal stylesheet is `MODAL_HOST_STYLES` (`index.js:114`), injected at `main.js:1543`. **Trap:** `styles/modals.js:3` is verbatim `⚠️ DEPRECATED — DO NOT EDIT` ("its rules never match anything… edit `MODAL_HOST_STYLES` in `src/styles/index.js`, not this one"), yet it is still in the array (`index.js:64`) — it looks authoritative but is inert (slated for deletion v0.10.0+). (Its banner's own `_renderModals()` reference is itself stale — the live method is `_updateModalHost()`.) Correct add = both places (§2). **Token gotcha:** miss the light companion (`index.js:651-745`) and a themeless light-OS Follow-HA user gets a dark modal.

**Cliff 2 — the three-bundle boundary: `styles/` reaches ONLY the command-center.** `scripts/build-card.mjs:74-76` builds three self-contained esbuild bundles, no code-splitting — entry points `src/all-cards.js` → `eufy-vacuum-command-center.js`, `src/cards-standalone.js` → the room/dashboard cards, `src/cards/vacuum-map-host.js` → the map host. `main.js:10` is the **only** importer of `STYLES`/`MODAL_HOST_STYLES`, and it is reachable only from the command-center entry. The standalone cards carry their OWN inline CSS and do NOT import `src/styles/`:
- `cards/dashboard-card.js:961` `const CARD_CSS` with its own `:host`; header `:958` says verbatim "own shadow root — sibling cards carry their own CSS".
- `src/room-card.js:79-81` / `:367-368` (note: at `src/`, not `src/cards/`) write their own shadow `<style>` (imports only i18n + `cards/_shared.js`, not `styles/`).
- The sole `styles/` import in `cards/` is `mapStyles` in `vacuum-map-host.js:24` (map host pulls just `styles/map.js`).

**This is the #1 "I changed the CSS but the room card didn't update" trap.** Editing `src/styles/` changes the command-center panel only; the room/dashboard cards have hand-duplicated token maps (e.g. `dashboard-card.js:962-970` maps `--evcc-accent`→`--accent`) you must edit too. Duplication is the deliberate price of independently-cacheable lazy bundles (`build-card.mjs:63-73`).

**Cliff 3 — where a token's default lives is per-family; room-fill is seeded elsewhere.** Canonical defaults are in `foundation.js:120`+ (`:host`). Room-fill is the exception with **two** independent default sources — the map renderer's own `var()` fallback (`roomFillCss`/`roomFillRgb` in `cards/map-room-color.js`, keeps a themeless card correct) **and** the `resolvedTheme` seed (`state/theme.js:384-388`, only so the editor swatch opens). `theme.js:376-383` and `theme-tokens/map.js:52-56` both state this verbatim. **Bites:** looking in `foundation.js`/`index.js` `:host` for a room-fill default finds nothing; changing one palette requires syncing both, and count = `ROOM_FILL_N` in `cards/map-room-color.js` (`theme-tokens/map.js:56`: "keep them in sync"). Full trace in §3(C).

**Cliff 4 — build-time style handling.**
- **Texture cache-bust:** `build-card.mjs:27-42` `hashDir()` sha1's each texture's name+bytes → 10-char `assetVer`, injected as the esbuild `define` `__ASSET_VER__` (`:60`) and appended `?v=<hash>` to texture URLs. Same scheme mints `__LOCALE_VER__`. **Bites:** these are compile-time `define` constants — a raw `__ASSET_VER__` is undefined under `build:dev`/`watch` (`package.json:10-11`), which don't set the defines. (Rendering of the texture itself is [render-cycle.md](render-cycle.md).)
- **External dynamic-import boundary:** `build-card.mjs:59` `external: ["/eufy_vacuum/frontend/*"]` leaves the dashboard card's runtime `import()` of the ~1MB map host as a literal URL — loads only when `show_map` is on (same pattern `main.js` uses for animal-svg).
- **CSS-literal guard blind spot:** the `check-styles.mjs` brace-check (§4) scans only `src/styles/`, not the standalone cards' inline `CARD_CSS` — a truncating backtick there ships silently.
