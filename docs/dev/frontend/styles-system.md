# Styles System

How CSS actually reaches pixels: the combiner that stitches `styles/*.js` into one shadow-root `<style>`, the separate body-host stylesheet the modal/toast portals need, the runtime `--evcc-*` token bridge, the typeface chain, and the "all CSS in `src/styles/`" rule with its CI gates.

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

- Imports: `src/styles/index.js:22-48`.
- Array + join: `src/styles/index.js:50-82` — `STYLES = [ … ].join("\n")` (`index.js:82`).

**Order matters — three load-bearing positions:**
- **`fontStyles` is FIRST** (`index.js:54`, comment `:51-53`). The `@font-face` declarations must be parsed before anything reads `--evcc-font-family`, and the `[data-evcc-font]` override rule needs to sit ahead of anything it must outrank. See §4 (the typeface chain).
- **`foundationStyles` is second** (`index.js:55`). It owns the canonical `:host` token block (`foundation.js:142`+); every downstream module consumes `var(--evcc-*)`, so foundation must declare those tokens before anything references them. See §3(A).
- **`MOBILE_STYLES` is LAST** (`index.js:81`). Mobile rules reach shared elements via `.evcc-shell[data-viewport="mobile"]` and must win specificity over the desktop defaults declared above — the comment at `index.js:76-79` spells this out. `externalJobsStyles` sits just before it (`index.js:80`).

**Injection (shadow root).** `STYLES` is imported into `main.js:10`, passed into the frame builder in `_render()` as `this._ensureShellFrame(STYLES)` (`main.js:1393`), and written as a single `<style data-evcc-style-root>${styles}</style>` that is a **direct child of the shadow root — the sibling right before `<ha-card>`** (`main.js:1487`), not inside `ha-card`/`.evcc-shell`.

**Injected ONCE, not per render.** `_ensureShellFrame` only rewrites `shadowRoot.innerHTML` when `missingFrame` is true (`main.js:1485-1506`) — first mount or a HACS-update frame reset. On later renders the existing `[data-evcc-style-root]` block is reused as-is unless `styles` itself changed (`styleRoot.textContent !== styles`, `main.js:1514-1516`); only header / bottom-nav / mobile-overlay / active view-root innerHTML get diffed per render (`main.js:1428-1461`). So the shadow `<style>` is stable across the card's life.

**Blast radius.** Adding a module means: create `styles/<feature>.js` exporting `<feature>Styles`, `import` it (`index.js:22-48`), and add it to the array (`index.js:50-82`) at the right specificity position. Forget the array entry and the export exists but never ships. This reaches the **command-center panel only** — see Cliff 2.

**Intentional omissions.** Several imported exports are deliberately NOT in the shadow `STYLES` array — `sharedChipStyles` (`index.js:22`), `maintenanceModalHostStyles` (`index.js:36`), `externalWizardModalStyles` (`index.js:45`), `dialogModalStyles` (`index.js:46`), `jobSummaryStyles` (`index.js:47`). They ride `MODAL_HOST_STYLES` instead (§2). `jobSummaryStyles` is a partial exception worth flagging: alongside its body-host modal rules it also carries three **shadow-root-targeted** selectors (`.evcc-review-job-card[data-job-summary-open]` cursor/hover/focus-visible, `styles/job-summary.js:122-133`) that, riding only `MODAL_HOST_STYLES`, never reach the actual review card in the shadow root — see §2's note.

---

## 2. The body-host style split

The modal host is a `document.body` child, **outside** the card's shadow root (see [event-binding-and-modal-host.md §3](event-binding-and-modal-host.md)). The shadow `<style>` cascade cannot reach it, so it gets its own stylesheet.

**`MODAL_HOST_STYLES`** — defined `styles/index.js:118`. It interpolates the body-host-only exports:
- `sharedChipStyles` — `index.js:540`
- `maintenanceModalHostStyles`, `roomAccessStyles`, `roomEstimateStyles`, `jobSummaryStyles`, `externalWizardModalStyles`, `dialogModalStyles` — the `${…}` block at `index.js:580-585`.

**Injection site — `_updateModalHost()`** (`main.js:1543-1647`):
- Host div created lazily and appended to `document.body` (`main.js:1606-1610`): `div.evcc-modal-host`.
- Before injection the host is stamped with the resolved language direction (`applyDir`, `main.js:1615`) and the typeface attribute (`_applyFontAttributeTo`, `main.js:1621`) — both are things a body-mounted node cannot inherit from the card (§4).
- Styles prepended inline to the modal markup: `` const modalMarkup = `<style>${MODAL_HOST_STYLES}</style>${html}`; `` (`main.js:1623`), written via `innerHTML` (`main.js:1632`).
- Guarded by a `dataset.renderedHtml` diff (`main.js:1624`) — re-injected only when markup changes; each open modal body's `scrollTop` is preserved by index across the swap (`main.js:1628-1637`). Teardown at `main.js:1599-1602` / `1839-1847`.

**Parallel toast host.** `TOAST_HOST_STYLES` (`index.js:911-992`) is injected the same way in `_updateToastHost` (markup construction `main.js:1728`, written `:1730`), z-index `10000` (`index.js:946`) to sit above the modal host's `9999` (`index.js:243`).

**Why the split is load-bearing.** The modal/toast hosts are detached from the card's `:host` cascade, so they neither receive the shadow `<style>` nor inherit the canonical `--evcc-*` seeds. `MODAL_HOST_STYLES` re-derives the whole `--evcc-modal-*` family from canonical tokens on `.evcc-modal-host` (`index.js:180-226`), with a light-scheme companion re-deriving the same family with light floors (`index.js:684-710`, inside the `@media (prefers-color-scheme: light)` block that runs `:674-768`), precisely to compensate. This is the modal token derivation bridge, matching `themes/preloaded.py`'s `_build_release_theme_colors()`.

**Adding a body-host style — you MUST touch two places:**
1. Author the rules as a `*ModalHostStyles` export in the feature module (canonical example `styles/maintenance.js` `maintenanceModalHostStyles`; also `external-jobs.js` `externalWizardModalStyles`, `dialog.js` `dialogModalStyles`, `job-summary.js` `jobSummaryStyles`).
2. Interpolate it into `MODAL_HOST_STYLES` at `styles/index.js:580-585`.

Skip step 2 and the export exists but is never injected → the modal renders unstyled with no error. See Cliff 1 for the dead-`modals.js` trap.

**A variant of the same failure, already shipped: shadow-root rules stranded in a body-host-only module.** `jobSummaryStyles` rides `MODAL_HOST_STYLES` correctly (step 2 above is done), but three of its rules target `.evcc-review-job-card[data-job-summary-open]` (`cursor: pointer`, a `:hover` border, and a `:focus-visible` outline — `styles/job-summary.js:122-133`) — and the review job card that selector matches lives in the **shadow root** (`renderers/review.js`, styled by `styles/review.js` which IS in the `STYLES` array), not inside `document.body`. Because those three rules only ship to the modal host, where no such element ever exists, they are dead: the review card gets no pointer cursor and no hover border. The one that matters for [§4a's](event-binding-and-modal-host.md) keyboard-parity claim is narrower than it sounds — the shadow-root stylesheet never sets `outline` on `.evcc-review-job-card` at all (`styles/review.js:126-134` is the only base rule and has no outline), so a keyboard user tabbing to the card still gets the browser's default `:focus-visible` outline. What's actually lost is the *styled* 2px accent ring (`outline: 2px solid var(--evcc-accent)`) falling back to that UA default. The fix is the mirror of Cliff 1: a rule meant for the shadow root belongs in a module that's actually in the `STYLES` array (e.g. alongside `reviewStyles`), not in a body-host-only module.

---

## 3. The theme-token runtime bridge

Per-render, resolved theme values are written as inline `--evcc-*` custom properties on the live hosts; the stylesheets reference `var(--evcc-*, default)`, so an unset token falls back to its default. Three moving parts: **apply-theme** (writer), the **token registry** (key inventory), and the **default sources** (CSS + JS palette).

### 3.1 The writer — `apply-theme.js`

`applyThemeToCard(card)` (`src/styles/apply-theme.js:32`) is the runtime entry point (the first step of `_render()` — see [render-cycle.md](render-cycle.md)):
- Reads the resolved layer: `state.resolvedTheme()` (`apply-theme.js:36`, guarded at `:34`).
- **Target 1 (card host):** `applyDynamicTheme(card, resolved)` (`apply-theme.js:41`) — vars on the `<eufy-…>` instance that carries `:host`.
- **Target 2 (modal host):** `applyDynamicTheme(card._modalHost, resolved)` (`apply-theme.js:49-51`), only when the modal host is body-attached — because it is detached from `:host` and needs the token layer bridged separately.

**When it runs:** the first effectful call in `_render()` (`main.js:1363`); once post-library-load (`main.js:1256`); plus 14 event-driven callsites in `bindings/theme.js` (e.g. preset `:251/:288`, mode `:305`, token `:633/:676`, color `:654`, alpha `:705/:718`, colormix `:914/:928/:945`, backend refresh `:1543`) for immediate editor feedback without waiting for a full render.

**The actual writer — `applyDynamicTheme(card, resolvedTheme)`** (`styles/index.js:92`):
- Iterates `THEME_TOKEN_REGISTRY` and **removes** any prop absent/null/empty in `tokens` (`index.js:98-102`) — so a cleared draft value falls back to the foundation default instead of leaving a stale inline value.
- Then `host.style.setProperty(property, value)` for every present token (`index.js:104-108`).

**Trust boundary:** apply-theme does NOT resolve the cascade — it just writes an already-merged `tokens` map. The default→theme→override layering resolves upstream in `resolvedTheme()` (§3.3).

### 3.2 The token inventory — `THEME_TOKEN_REGISTRY`

A flat array of descriptor entries `{ key, label, group, type, min?, max?, step? }`, exported as a live `let` binding (`theme-tokens/index.js:127`), reassigned by `rebuild()` (`:150`). `rebuild()` flattens static group token-sets + dynamically-built animal tokens (`:132-161`), asserts unique keys (`:113-125, :145`), and also produces `THEME_TOKEN_MAP`, `THEME_GROUP_MAP`, `THEME_GROUPS`. It rebuilds on the `animal-svg-registered` document event (`:169-177`); the live binding means importers see new values with no subscription.

Token definitions come from group-bound factories in `theme-tokens/helpers.js`: `makeTypedGroupToken(group, defaultType)` (`:173`) wrapping `makeGroupedToken` (`:126`). Examples: `mapToken.color` (`helpers.js:176, :208`), `roomToken.number` (rangeless on purpose, `:180, :207`), `roomToken.size` (`:179`); range sugar `.unit/.blur/.angle/.signed` (`:191-194`) over `SCALAR_RANGES` (`:81-91`). `min/max/step` are **editor-only, never persisted** (`helpers.js:139-143`).

**Trust boundary:** the registry is the **key inventory + type/label/range** — it does NOT carry a `default` field. `applyDynamicTheme` iterates it only for the remove-pass (`THEME_TOKEN_REGISTRY` imported at `styles/index.js:48`, used `:98`). Defaults live in CSS/JS (§3.3). The registry also feeds the editor (`THEME_GROUP_MAP`/`THEME_GROUPS`, out of scope — see [theme-system.md](theme-system.md)).

### 3.3 Where each default actually lives

There is **no single default source.** When `applyDynamicTheme` removes/never-sets a prop, the stylesheet's `var(--evcc-*, fallback)` resolves it. Three distinct sources by token family:

**(A) Canonical foundation tokens → `:host` block in `styles/foundation.js:142`+.** Declares canonical defaults, e.g. `--evcc-surface-base: var(--card-background-color, #1c2127)` (`:153`), `--evcc-accent: var(--accent-color, #3b82f6)` (`:181`), text/border/semantic/radius/chip tokens. Each chains to an HA theme var first, then a literal — this is the **only** place HA fallbacks are mapped. A theme overrides by writing an inline prop on the same host.

**(B) Modal-family tokens → derived in `MODAL_HOST_STYLES`.** The body host is detached from `:host`, so `--evcc-modal-*` defaults are re-derived from canonical tokens in `.evcc-modal-host` (`styles/index.js:180-226`, dark) with a light companion (`:684-710`, under the `@media (prefers-color-scheme: light)` block). See §2.

**(C) Room-fill tokens → NO CSS default anywhere; default lives in JS + inline `var()` fallback.** `--evcc-room-fill-<N>` is declared in no `:host` block. Instead:
- **SVG path:** `roomFillCss(idx, override)` (`cards/map-room-color.js:71`) emits `var(--evcc-room-fill-<N>, <defaultHex>)` (`:74`), the hex inlined from `ROOM_FILL_PALETTE` (`:19-23`) — CSS resolves it live, a theme token overrides via cascade.
- **Raster path:** `roomFillRgb(idx, host)` (`:101`) reads the computed prop off a mounted node, else `roomFillDefault(idx)` — canvas can't take CSS vars.
- **Editor swatch seed:** because the token carries no default anywhere, `resolvedTheme()` seeds the palette so the picker isn't blank — `state/theme.js:385-389` (`colorMap['--evcc-room-fill-<i+1>'] = hex`, `sources=default`). Comment `theme.js:375-384` notes the seed equals the render's own default, so a themeless card is net-zero.
- Full per-room cascade (override > token > default) documented at `map-room-color.js:5-8`.

**The cascade resolver — `resolvedTheme()` (`state/theme.js:360`)** produces the `{tokens, sources}` apply-theme writes:
- **0. default** — room-fill palette seed (`theme.js:385-389`; a sibling floor-texture-material seed follows at `:409-428`, cross-referenced from [floor-texture-map-view.md](floor-texture-map-view.md) rather than restated here).
- **1. theme** — active theme's `colors`/`alpha`/`tokens` (`theme.js:433-448`); `activeTheme = library[effectiveActiveThemeId()]` (`theme.js:373`); `effectiveActiveThemeId()` (`:279`) resolves per-device override → backend active fallback.
- **2. draft** — working-draft overlay, highest precedence (`theme.js:453-466`).
- **3. combine** — `_hexWithAlpha()` folds `colorMap`+`alphaMap` into 8-char hex (`theme.js:475-478`).
- Returns `{tokens, sources}` (`:480`); `sources` (default|theme|draft) drives editor provenance only. The foundation `:host` default (A) is NOT in `tokens` — it is the implicit floor CSS applies whenever `resolvedTheme` omits a key.

**One-line bridge:** `_render()` → `applyThemeToCard(this)` (`main.js:1363`) → `resolvedTheme()` merges default(seed)→theme→draft into `{tokens}` (`theme.js:360`) → `applyDynamicTheme` writes/removes inline `--evcc-*` on card + modal host (`styles/index.js:92`) → CSS resolves anything unset via `:host` (A), modal-derived (B), or `var(…,defaultHex)` (C).

---

## 4. The typeface chain

The accessibility typeface (OpenDyslexic, the theme/paper default is the other option — see
[i18n-system.md](i18n-system.md#the-language-control) for the per-user store) shipped once
already **inert**: every rule involved was individually valid CSS/JS, and nothing caught that the
rules didn't connect. `styles/typeface-wiring.test.mjs` (tests `TF-1`…`TF-6`) now asserts the
*connections*, not just that each piece parses. The chain, in order:

1. **`@font-face` is registered on the DOCUMENT, not the shadow tree.** Chromium does not honour
   `@font-face` rules that live only inside a shadow root — `document.fonts.check()` still returns
   `true` for a family with zero registered faces, so that gap is invisible to the obvious check
   (this is `live:FONT-1`, landed 41a9735). The fix, `ensureFontFacesInDocument()`
   (`styles/fonts.js:91-97`), id-guarded (idempotent, so whichever bundle entry loads first wins)
   and injected into `document.head`, is called from **all three** bundle-entry files —
   `all-cards.js`, `cards-standalone.js`, `cards/vacuum-map-host.js` (`TF-6`) — because any one of
   them can be the only bundle a given surface loads. `FONT_FACE_CSS` (`fonts.js:58-81`) also stays
   part of `fontStyles` for engines that do read `@font-face` from a shadow sheet; the duplicate
   registration is a no-op where it isn't needed.
2. **`:host([data-evcc-font="opendyslexic"])` sets `--evcc-a11y-font-family` — a SEPARATE token
   from the theme's** (`fonts.js`, the `[data-evcc-font]` rule; mirrored on the modal/toast hosts
   in `styles/index.js`). The old claim that being FIRST in the `STYLES` array made a
   `--evcc-font-family` setter beat a theme was wrong: the theme's Font Family token
   (`--evcc-font-family` is in `THEME_TOKEN_REGISTRY`) is written as an **inline style** by
   `applyDynamicTheme`, and inline beats any sheet rule regardless of array position
   (live:FONT-1 remainder #2, found on-device 2026-08-06 against a theme carrying Segoe UI/Inter).
   Precedence therefore lives in the **read's fallback chain**, not the cascade: every
   `font-family` read is `var(--evcc-a11y-font-family, var(--evcc-font-family, …))` — the user's
   accessibility choice first, the theme's aesthetic choice second, the HA default last, with no
   `!important` anywhere. `TF-8` pins both halves: setters write only the a11y token, and no read
   consults the theme token without the a11y token ahead of it.
3. **`.evcc-shell` reads the token** (`styles/shell.js`, the `.evcc-shell` base rule) —
   `font-family: var(--evcc-font-family, var(--paper-font-body1_-_font-family, sans-serif))`.
   This link has now been wrong twice (`TF-1`): first the rule named a font directly instead of
   reading the token; then (the live:FONT-1 remainder, found on-device 2026-08-06) the token-read
   sat on `foundation.js`'s `.evcc-card` block — a selector **no element carries**; the shell frame
   emits `.evcc-shell` (`main.js`). Every source-regex assertion passed while the rule matched
   nothing, and the faces reported `unloaded` forever because no rendered text ever requested the
   family. `TF-7` now asserts the markup side: the shell frame must emit the class the reading rule
   targets. (`foundation.js:276`'s `.evcc-card` block is dead code — cleanup tracked in
   DOC-PASS-TRIAGE.)
4. **The modal and toast hosts re-declare the token**, because a `document.body` child cannot
   inherit a custom property declared on the card's `:host` (`TF-2`): `.evcc-modal-host[data-evcc-font="opendyslexic"]`
   (`styles/index.js:126-128`) and `.evcc-toast-host[data-evcc-font="opendyslexic"]`
   (`:919-921`) restate the same declaration for their branch of the document.
5. **`main.js` stamps the attribute on all three hosts** (`TF-3`): `_applyFontAttributeTo(el)`
   (`main.js:465-470`) is the single stamp/clear helper, called for the card itself
   (`_applyFontAttribute` → `main.js:452-454`), the modal host (`main.js:1621`), and the toast host
   (`main.js:1726`) — a font selected on the card must reach its modals and toasts, which live
   outside the shadow tree where step 2's rule is declared.

**Selection and persistence** are `setUiFont(fontId)` (`main.js:478-484`, optimistic apply +
fire-and-forget persist, same shape as `setLanguageOverride`) and `_maybeLoadFontChoice()`
(`main.js:426-439`, one-shot load on first `hass`, in-session pick always wins over a late server
read) — see [i18n-system.md](i18n-system.md#the-language-control) for the shared user-data object
and the language-gated *offering* of the font (`fontSupportsLang`).

**The picker's own sample bypasses the token deliberately** (`TF-5`): `.evcc-font-sample-opendyslexic`
(`fonts.js:118-124`) hardcodes `font-family: "OpenDyslexic"` so the option shows the typeface
*before* it is selected — routing it through `--evcc-font-family` would only resolve once the
setting is already on, defeating the preview.

**Why served, not embedded as `data:` URIs.** The two woff2 files are ~235KB combined (not the
~100KB the design estimated) and the cards bundle loads on every HA page via `add_extra_js_url`, so
a `data:`-embedded font would cost every user those bytes on every page load whether or not they
use it. Served from `/eufy_vacuum/fonts` (registered with `cache_headers=True`) instead: a browser
only fetches the `@font-face` `src` when something renders in that family, so the cost is zero
until the toggle is on and cached after (`fonts.js:13-29`).

**Licence.** OpenDyslexic ships under the SIL Open Font License 1.1 with a Reserved Font Name; the
full licence text travels beside the woff2 files at `frontend/fonts/OFL.txt` and must not be
removed (`fonts.js:31-41`).

---

## 5. Styles-in-styles-only + the CI gates

**The rule**: all CSS lives in `src/styles/`; renderers emit **no** inline `<style>`. Verified — grep for `<style` across `src/renderers/` returns zero matches.

**The one allowed escape hatch:** dynamic `style="--x:…"` attributes that set only CSS custom properties consumed by rules in `src/styles/` (data → CSS, never literal declarations). Sanctioned examples:
- `renderers/map.js:928` — `--seg-color` (room-fill per segment); `:1484` — `--evcc-grp` (group color)
- `renderers/rooms.js:815` — `--job-progress`; `:1417` — `--room-progress`
- `renderers/maintenance.js:418, :509` — `--maintenance-remaining` (gauge fill)
- `renderers/floor-texture-surface.js:132` — `--floor-opacity-card` / `--floor-position-card`

**Renderer ↔ styles pairing** is by `evcc-<feature>-*` class convention: a renderer emits `class="evcc-<feature>-*"`, matching rules live in `styles/<feature>.js`, and the module is registered in the combiner (§1). Concrete (`saved-zones`): renderer classes in `renderers/saved-zones.js` (`.evcc-saved-zones-panel :44/:121/:130/:166`, `-header :31`, `-item.is-selected :90`, …) pair with rules in `styles/saved-zones.js` (`.evcc-saved-zones-panel :6`, `-header :18`, `-item :119`, `-item.is-selected :131`, …); wired via `import { savedZonesStyles }` (`index.js:35`) + array entry (`index.js:67`). The export is a plain template-string constant (`saved-zones.js:5` → closing backtick `:226`) — exactly the shape the gate checks.

**The gate — `scripts/check-styles.mjs`.** Five checks (its own success line names all five: "import cleanly, CSS exports brace-balanced, no un-tokenized colors, no physical-direction (non-RTL) CSS, and every `--evcc-*` reference resolves", `:240`), all `src/styles/*.js` (skipping `*.test.js`) unless noted:
1. **Import-clean** — `import()`s each module; a stray backtick / broken template literal throws on import → fail. This catches the original prod bug: truncated CSS that was still valid JS.
2. **Brace-balanced** — walks each string export counting `{`/`}`; nonzero depth = truncated literal → fail. (1 and 2 together: `:28-42`.)
3. **THEME-LINT** (`:44-94`) — no hardcoded color literal (`#hex` / `rgb(a)` / `hsl(a)`) assigned to a color-ish CSS property in a rule body; every color must resolve through `var(--evcc-*, fallback)`. Scans `src/styles/*` (minus `foundation.js`, the token-DEFINITION file, whitelisted since its literals ARE the defaults) **plus** `src/room-card.js`, `cards/dashboard-card.js`, `cards/profile-card.js`, `cards/_shared.js` — i.e. beyond `src/styles/` too. An inline `/* theme-lint-ignore */` comment on the line whitelists a deliberately theme-independent color.
4. **RTL-LINT** (`:96-138`) — no *physical*-direction property (`margin-left`/`-right`, `padding-left`/`-right`, `border-left`/`-right`, `text-align: left/right`, bare `left:`/`right:`) outside an `/* rtl-ignore */` line; the card renders RTL (Arabic/Hebrew) and a physical rule won't mirror. Same target list as THEME-LINT plus `cards/vacuum-map-host.js`, minus `styles/map.js` — the map is spatial (coordinate math, canvas, CSS-triangle borders) and is force-`direction: ltr` on `.evcc-map-view`, so its physical properties are correct by construction and would only be false positives here.
5. **TOKEN-LINT** (`:140-237`) — every `var(--evcc-*)` reference must resolve to something real: a CSS declaration anywhere in the card (including the token-definition file), an entry in the theme-token inventory (`src/theme-tokens/*` — tokens a THEME may supply that the card itself never declares), or a runtime-set inline `style="--evcc-x:…"`. A dangling reference still renders (its fallback always applies) and never appears in the theme editor, so it silently advertises a knob that doesn't exist — three shipped that way in one sitting before this check existed. `KNOWN_DANGLING` (`:199-208`) is a **shrink-only** allowlist of pre-existing dangling references recorded 2026-08-06; it currently lists none (all 11 recorded that day were fixed same-day), and the gate itself fails the build if a listed entry stops dangling and the entry isn't deleted — so the list can never silently regrow permission.
- Exits `1` on any failure (`:239`). Header (`:1-17`) documents the original incident all of this guards (dropped nav / header-padding / view-stage `overflow:auto`).

**Runs FIRST in the build** (`package.json:6-7`): both `build` and `build:deploy` are `node scripts/check-styles.mjs && …` — `&&`-chained first, so a new module that fails any of the five checks blocks the entire build before the card is bundled. Also standalone `check:styles` (`package.json:9`).

**Gate blind spot — narrower than it looks.** Checks 1–2 (import-clean, brace-balance) scan **only** `src/styles/`. Checks 3–5 (theme-lint, RTL-lint, token-lint) additionally reach into `room-card.js`, `dashboard-card.js`, `profile-card.js`, `cards/_shared.js`, and (RTL-lint only) `vacuum-map-host.js` — but **none** of the five checks look at the standalone cards' own inline `CARD_CSS` block beyond those specific files (Cliff 2). A backtick-in-a-comment truncation inside `dashboard-card.js`'s `CARD_CSS`, for instance, would still ship silently — it's covered by 3/4 for un-tokenized colors and physical CSS, but not by 1/2 for a truncated template literal.

---

## 6. Cliffs

**Cliff 1 — new modal CSS must go in the BODY host, not the shadow bundle.** Add a modal's CSS to any shadow-bundled module (the `STYLES` array, `index.js:50-82`) and the body-portal modal renders **completely unstyled** — no error, just naked markup on `document.body`. The live modal stylesheet is `MODAL_HOST_STYLES` (`index.js:118`), injected at `main.js:1623`. **Trap:** `styles/modals.js:3` is verbatim `⚠️ DEPRECATED — DO NOT EDIT` ("its rules never match anything… edit `MODAL_HOST_STYLES` in `src/styles/index.js`, not this one"), yet it is still in the array (`index.js:69`) — it looks authoritative but is inert (slated for deletion v0.10.0+). (Its banner's own `_renderModals()` reference is itself stale — the live method is `_updateModalHost()`.) Correct add = both places (§2). **Token gotcha:** miss the light companion (`index.js:684-710`, inside the `:674-768` media block) and a themeless light-OS Follow-HA user gets a dark modal. **A live example of the inverse mistake** — shadow-root CSS stranded in a body-host-only module, so it never reaches the shadow root at all — is `jobSummaryStyles`; see §2's note.

**Cliff 2 — the three-bundle boundary: `styles/` reaches ONLY the command-center.** `scripts/build-card.mjs:74-76` builds three self-contained esbuild bundles, no code-splitting — entry points `src/all-cards.js` → `eufy-vacuum-command-center.js`, `src/cards-standalone.js` → the room/dashboard cards, `src/cards/vacuum-map-host.js` → the map host. `main.js:10` is the **only** importer of `STYLES`/`MODAL_HOST_STYLES`, and it is reachable only from the command-center entry. The standalone cards carry their OWN inline CSS and do NOT import `src/styles/` (though `check-styles.mjs`'s theme-lint/RTL-lint/token-lint checks do reach some of them — see §5's gate blind-spot note):
- `cards/dashboard-card.js:989` `const CARD_CSS` with its own `:host`; header `:986` says verbatim "own shadow root — sibling cards carry their own CSS".
- `src/room-card.js:80-81` / `:368-369` (note: at `src/`, not `src/cards/`) write their own shadow `<style>` (imports only i18n + `cards/_shared.js`, not `styles/`).
- The sole `styles/` import in `cards/` is `mapStyles` in `vacuum-map-host.js:24` (map host pulls just `styles/map.js`).

**This is the #1 "I changed the CSS but the room card didn't update" trap.** Editing `src/styles/` changes the command-center panel only; the room/dashboard cards have hand-duplicated token maps (e.g. `dashboard-card.js:992-997` maps `--evcc-accent`→`--accent`) you must edit too. Duplication is the deliberate price of independently-cacheable lazy bundles (`build-card.mjs:63-73`). The three bundle entries also each independently call `ensureFontFacesInDocument()` (§4) for the same reason — a standalone card can be the only bundle a page loads.

**Cliff 3 — where a token's default lives is per-family; room-fill is seeded elsewhere.** Canonical defaults are in `foundation.js:142`+ (`:host`). Room-fill is the exception with **two** independent default sources — the map renderer's own `var()` fallback (`roomFillCss`/`roomFillRgb` in `cards/map-room-color.js`, keeps a themeless card correct) **and** the `resolvedTheme` seed (`state/theme.js:385-389`, only so the editor swatch opens). `theme.js:375-384` and `theme-tokens/map.js:52-56` both state this verbatim. **Bites:** looking in `foundation.js`/`index.js` `:host` for a room-fill default finds nothing; changing one palette requires syncing both, and count = `ROOM_FILL_N` in `cards/map-room-color.js` (`theme-tokens/map.js:56`: "keep them in sync"). Full trace in §3(C).

**Cliff 4 — build-time style handling.**
- **Texture cache-bust:** `build-card.mjs:27-42` `hashDir()` sha1's each texture's name+bytes → 10-char `assetVer`, injected as the esbuild `define` `__ASSET_VER__` (`:60`) and appended `?v=<hash>` to texture URLs. Same scheme mints `__LOCALE_VER__`. **Bites:** these are compile-time `define` constants — a raw `__ASSET_VER__` is undefined under `build:dev`/`watch` (`package.json:10-11`), which don't set the defines. (Rendering of the texture itself is [render-cycle.md](render-cycle.md).)
- **External dynamic-import boundary:** `build-card.mjs:59` `external: ["/eufy_vacuum/frontend/*"]` leaves the dashboard card's runtime `import()` of the ~1MB map host as a literal URL — loads only when `show_map` is on (same pattern `main.js` uses for animal-svg).
- **CSS-literal guard blind spot:** the `check-styles.mjs` import-clean/brace-balance checks (§5) scan only `src/styles/`, not the standalone cards' inline `CARD_CSS` — a truncating backtick there ships silently even though the lint checks partially cover those same files.
