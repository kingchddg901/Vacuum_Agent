# Render Harness Tests (frontend)

A separate test track from the Python suite: JS/Playwright tests that render the
**real card** headless and gate it for crashes, visual regressions, colorblind
distinguishability, and theme-intake safety. Architecture lives in
[frontend/render-harness](../../dev/frontend/render-harness.md); this is how to run it.

The harness is where the **rendered card** is tested — the Python suite stops
at the backend contract; these pick up at the shadow-DOM boundary. (A small
set of pure-JS tooling units — the gallery-submission bot and the gallery-HTML
builder — are tested separately with `node --test`; see [CI](#ci).)

---

## TL;DR

- **Run the gates:** `npm run test:harness` (builds the bundle, runs all specs).
- **Visual baselines are Linux**, generated and checked in one pinned Playwright
  image. On any other OS the render differs, so the visual specs **skip** unless
  `CI` or `VISUAL=1` — everything else runs anywhere.
- **First time:** `npm install` then `npx playwright install chromium`.
- **Regenerate a baseline** after an intended visual change → run the visual gate
  in the pinned Docker image with `--update-snapshots` (below). Never re-bake
  baselines on the host.

---

## The gates

| Spec | Asserts | Runs |
|---|---|---|
| `smoke.spec.mjs` | every tab renders from the stub without throwing (the pure-renderer contract) | everywhere |
| `gallery-completeness.spec.mjs` | every semantic-color token has a gallery entry (or a reasoned allowlist) | everywhere |
| `visual.spec.mjs` | each tab + gallery matches its committed baseline | CI / `VISUAL=1` only |
| `cvd.spec.mjs` | the `cvd-safe` theme separates all 30 group pairs on the real card (ΔE2000 ≥ 15) + the 5-override cascade resolves | everywhere |
| `shape-marks.spec.mjs` | the six badge marks are distinguishable in flat grayscale at dot size | everywhere |
| `i18n-escaping.spec.mjs` | every POPULATED view x all 18 bundled locales: no HTML entity reaches the screen as literal text (a catalog string escaped twice). The populated set includes **`setup-system`** (added 2026-08-14), a fixture carrying one row per branch of `_renderSystemSubtab` — resolved-uncontested, contested-and-won with a rejected alternative, config-entry sweep, user override, and unresolved — so the localized, RTL and escaping gates cannot report coverage of halves that never rendered | everywhere |
| `intake.spec.mjs` | the ingest gate skips malformed / unknown-namespace exports and clamps every value | everywhere |
| `device-theme.spec.mjs` | per-device theme resolution: the real `VacuumCardState.effectiveActiveThemeId()` fallback chain keeps a device pin through a pre-load, resolves it once the library loads, and clears it only when genuinely stale | everywhere (also re-run in `card-visual` CI) |
| `tab-gating.spec.mjs` | capability tab gating: `renderHeader` hides the Base Station nav tab when `supportsBaseStation()` is false (the S6 no-dock case), default-shown otherwise (Eufy-safe) | everywhere |
| `i18n-locale.spec.mjs` | the renderers resolve the *user's* language: a tab rendered under a registered foreign catalog switches its strings (the rest of the harness only ever renders English); no-language still renders English | everywhere |
| `i18n-layout.spec.mjs` | a translated locale must not break the layout — **property**-based, not pixel-pinned: under a pseudo-lengthened catalog assert nothing escapes its box, at desktop @500px and mobile @390px. Plus two data-driven passes added 2026-08-07: a **real-German** sweep @390px (seeded via `flattenLocale(...).flat`, with the seed key-count asserted and one test pinning `Maintenance Overview`→`Wartungsübersicht`, so the describe cannot silently degrade into a second English run), and a **maintenance-CARDS** pass in en/de/nl/ru driven by the gallery fixture — because `renderTab`'s generic stub renders an EMPTY maintenance view, so the card grid had never been measured in any locale. The cards pass also asserts the **title box**, not just overflow: a starved flex item plus `overflow-wrap:anywhere` degrades into a vertical one-character-per-line column that overflows nothing, so `probeLayout` is blind to it by construction. **Form controls are excluded from `probeLayout`** (2026-08-14): a closed `<select>` reports its widest `<option>` as `scrollWidth`, which the UA paints in a popup layer and never inline, so the Setup → System row picker registered 14px of "overflow" while sitting 220px *inside* its cell. `probeBleed` already skipped them for the same reason. This cannot mask a real blowout — a control genuinely too wide makes its ANCESTORS overflow, and those are still measured, with `shellOverflow` as the aggregate backstop | everywhere |
| `incomplete-run-banner.spec.mjs` | the incomplete-run banner under a WIDE FONT and a LONG LOCALE, at 360px and 390px. Added 2026-08-24 from a phone report that arrived as two symptoms of one defect: in EN + OpenDyslexic the title starved into a word-per-line column beside the button; in FR + OpenDyslexic the same banner pushed the page wider than the viewport. `.evcc-incomplete-run-actions` is `flex-shrink:0` while the body was `flex:1; min-width:0`, so the actions took what they needed and the body absorbed the whole shortfall — starving if they fit, overflowing if they did not. Asserts BOTH symptoms, because fixing one is how this survives: line count for the starve (`probeLayout` is blind to it by construction), `probeLayout` for the overflow. **Introduced 360px to this suite** — 22 of the 24 mobile viewports in harness/tests were 390, and the report came from a 360px Android | everywhere |
| `dashboard-sequence-override.spec.mjs` | the STANDALONE dashboard card's sequence-override row: does it render, is it STYLED AT ALL, and does its verification box carry its own status token. Added 2026-08-24 after a pre-release audit found the `.soro-*` rules had lived in `src/styles/rooms.js` since the row shipped and could never apply — `vacuum-agent-dashboard` attaches its own shadow root and injects only `CARD_CSS`, so the panel's stylesheet cannot reach it. The row rendered as bare divs on that surface for its whole life, and TWO commits "fixed" its colours by editing the panel stylesheet, one of them saying so in its message. Nothing went red because `sequence-override.spec.mjs` mounts the PANEL, and `CARD_STATES` carries neither clean-order entity, so even existing card mounts rendered the row as an empty string. The crude assertion is the load-bearing one — an unstyled div computes `rgba(0, 0, 0, 0)`. Mounting this element for the first time also exposed two defects no review had: 21 calls to a non-existent `this.escapeHtml` (which threw and took the WHOLE CARD down for any V1 owner), and `_shouldRender` tracking neither clean-order entity, so the card never repainted after Apply | everywhere |
| `sequence-override.spec.mjs` | the Override Order row in all five states: it RENDERS at all, fits, and resolves the right semantic colour. Added 2026-08-24 after two defects reached a user's phone that no gate could reach, because **the row never rendered in the harness** — it needs a `switch.<vac>_clean_order_override` in `hass.states` or `findOverrideSwitch` returns null and the renderer returns `""`, and no fixture supplied one. So `i18n-layout` swept Rooms at 390/500px under pseudo-long and passed over an empty string. Two lessons are pinned in the spec itself: (1) the **colour** must be asserted as a RESOLVED rgb value against the document's own `--evcc-sem-*`, because the `is-<kind>` class was correct all along — no stylesheet consumed it, so asserting the class passes while a confirmed match paints in the theme accent; (2) the **fit** claim lives in the pseudo-long block, not the English one — with `flex-wrap` ablated, English at 390px overflows by ZERO (the buttons fit), so there the assertion is a declaration with nothing behind it, while pseudo-long measures +90..100px | everywhere |
| `i18n-rtl.spec.mjs` | an RTL locale must flip cleanly: each tab rendered under the **real Arabic and Hebrew catalogs** with the host stamped `dir="rtl"` (via `applyDir`, as `src/main.js` does) — same property-based probe as the pseudo-long gate (nothing escapes its box, no horizontal scroll), plus an assertion the host actually carries `dir="rtl"` so the gate can't pass by rendering LTR | everywhere |

`npm run test:harness` runs all of them (visual auto-skips off-CI). The i18n
strings + intake security gate are covered separately — see [i18n system](../../dev/frontend/i18n-system.md)
(`check:i18n` + the real-Chromium `scripts/sanitize-locale.test.mjs`).

---

## Running

```bash
# one-time setup
npm install
npx playwright install chromium

# all gates (visual skips locally)
npm run test:harness

# capture PNGs for eyeballing
npm run harness:shoot       # every tab, default bundle  -> harness/out/<bundle>/
npm run harness:gallery     # all-states galleries        -> harness/out/gallery/
npm run harness:preview     # theme exports in gallery/themes/ -> harness/out/preview/
npm run harness:cards       # the three standalone cards  -> docs/screenshots/card-*.png
npm run harness:readme      # the README panel shots      -> docs/screenshots/*.png

# the CVD separation matrix for any bundle
node harness/cvd/report.mjs            # default palette (fails — shows the problem)
node harness/cvd/report.mjs cvd-safe   # the shipped colorblind palette (passes)
```

`harness/out/` and `harness/dist/` are build artifacts (gitignored). Baselines
under `harness/tests/__screenshots__/` are committed.

---

## Hero shots — the standalone cards

```bash
npm run harness:cards
```

Renders the three standalone Lovelace cards and writes the committed hero shots.
Deterministic: the clock is frozen and animations zeroed by default (unlike the tab
shooters, where `--freeze` is opt-in), so re-running with nothing changed reproduces
the same bytes.

| Output | Shows |
|---|---|
| `docs/screenshots/card-room.png` | `eufy-room-card` — one room's cleaning-mode / suction / water / path / passes / edge-mopping chips with the saved values selected, plus Start |
| `docs/screenshots/card-dashboard.png` | `vacuum-agent-dashboard` — the vacuum header, all six rooms with two selected and one expanded to its settings, the saved-profile + app-scene launchers, Dock / Start |
| `docs/screenshots/card-profile.png` | `vacuum-agent-profile-card` — one saved routine's "Runs in this order" step manifest across two room groups, a charge-to-80% stop and a wait, plus Run |
| `harness/out/cards/` | the same three frames plus `_contact-sheet.png`, for reviewing them together |

Flags: `--bundle <name>` themes the cards from `harness/bundles/` exactly as it themes
the panel (they read the same `--evcc-*` tokens); `--scale` sets the device pixel ratio
(default 2); `--out <dir>` redirects the hero shots.

**This is a different mount path from everything above.** The tab shooters drive the
panel's *pure renderers* with a stub `state` accessor. The standalone cards can't be
driven that way — they are plain custom elements with `setConfig` + a `hass` setter,
and every value they show is read back out of `hass`. So `window.__evcc.mountCard()`
mounts the real element in the real document, against the stub hass in
`harness/fixtures/cards.js`, exactly as Lovelace does. What that fixture must supply
is the whole contract in `src/cards/_shared.js`:

- **room switches** — a `switch.*` entity is only a room if its attributes carry a
  matching `vacuum_entity_id` *and* a non-null `room_id`. Miss either and the card
  renders zero rooms.
- **the adapter option lists** — `clean_mode_options` / `fan_speed_options` /
  `water_level_options` / `clean_intensity_options`, carried on each switch. These
  are the chips. Omit them and the card still mounts, still looks structurally
  plausible, and every chip row is empty.
- **the two response-capable reads** — `get_dashboard_snapshot` and
  `get_saved_run_profiles`, answered by the fixture's canned payloads through a
  `callService(..., returnResponse=true)` stub.

Because a card that fails to mount looks like a small empty box — and passes any check
that only asserts a file exists — every shot is gated on what the live shadow tree
actually contains (chip count, active-chip count, room rows, manifest steps, rendered
height) **before** anything is written. A card that misses its floor is reported and
skipped, its previous PNG left untouched, and the run exits non-zero.

Two things the fixture does deliberately, worth knowing before editing it:

- **`clean_mode` appears in both spellings.** The room editor persists the display
  label `Vacuum and mop`; the adapter option value, the profile catalog and the
  framework use the token `vacuum_mop`. Kitchen holds the label and Office holds the
  token, so the shot exercises `canonicalCleanMode()` instead of the trivially-equal
  path — a token-only fixture would light the chip either way and prove nothing.
- **The dashboard card's map section is off**, via the card's own `show_map: false`
  config toggle (a real setting in its visual editor), not by understating the
  device's capability. The map body is a separately-served bundle
  (`/eufy_vacuum/frontend/eufy-vacuum-map.js`) that the harness has no route for.

---

## Panel shots — the README screenshots

```bash
npm run harness:readme
```

Renders the fifteen committed panel screenshots the README embeds — one full-tab
capture per view, at 920 CSS px and `deviceScaleFactor` 2, so each PNG lands ~1840px
wide. Deterministic on the same terms as the card shooter: the clock is frozen,
animations are zeroed, and no fixture derives from wall-clock or randomness, so
re-running with nothing changed reproduces the same bytes.

| Output | Shows |
|---|---|
| `rooms-cards.png` / `rooms-map.png` | the Rooms tab in both view modes — six room cards with learned ETAs and confidence, and the same six as selectable polygons on a floor plan |
| `maintenance.png` · `base-station.png` · `metrics.png` · `metrics-battery.png` · `learning-review.png` · `external-jobs.png` · `external-wizard-step[12].png` · `room-rules.png` · `setup.png` | one tab (or sub-tab, or modal step) each |
| `themes-presets.png` / `themes-palette.png` / `themes-tokens.png` | one view in three sub-states — the preset grid, the palette editor, the token editor |
| `harness/out/readme/` | the same frames plus `_contact-sheet.png`, for reviewing them together |

Flags: `--bundle <name>` themes the shots from `harness/bundles/`; `--width` / `--scale`
set the CSS width and device pixel ratio; `--only <id,id>` shoots a subset; `--dry-run`
writes only the review copies, leaving `docs/screenshots/` alone.

**Every shot is gated on its content, because the failure mode here is a screenshot
that looks fine.** `renderTab` with the default stub state renders the *empty* state:
`renderRoomsView` returns `.evcc-empty` the moment `getRoomsForActiveMap()` is falsy,
and the metrics, maintenance and review tabs each have their own "no data yet" branch.
Every one of those produces a PNG with the right chrome, the right active tab, the
right theme and nothing in it — and passes any check that asserts the file exists. So
each entry in `harness/fixtures/readme-shots.js` declares a floor, measured against the
live shadow tree **before** anything is written:

- **`selectors`** — minimum element counts for the things that *are* the view (six
  `.evcc-room-card`, four `.evcc-base-station-action-card`, three `.evcc-metrics-table`).
- **`text`** / **`notText`** — substrings that must, and must not, appear. `notText`
  exists because not every empty branch renders `.evcc-empty`: the battery tab prints
  "… — no single-bucket jobs yet" as ordinary table rows, so a fixture that named an
  attribute wrong produced a table that looked populated and said nothing.
- **`minHeight`**, zero `.evcc-empty` nodes, the claimed tab actually marked active,
  and no `undefined` / `NaN` / `[object Object]` in the rendered text.
- **overflow**, both axes. `<ha-card>` is `overflow: hidden`, so content the shell
  cannot fit is cropped out of the capture with no other symptom. Shots that declare a
  `height` are bounded panels whose view owns a scroll container, so for those only the
  horizontal axis is checked.

A shot that misses its floor is reported and skipped, its previous PNG left untouched,
and the run exits non-zero.

Three things about the fixtures, worth knowing before editing them:

- **Room names are synthetic, and that is the point.** These are published on a public
  repo, so every shot draws from one neutral list — Kitchen / Living Room / Bedroom /
  Office / Bathroom / Hallway — and the gate asserts those names are present, so a
  fixture that drifted to some other source of room names fails rather than ships. Same
  for entity ids, map names and file paths. The single real-home shot in
  `docs/screenshots` is `floor-texture-map.png`, kept deliberately because it shows no
  names.
- **The map backdrop is drawn, not photographed.** A real install serves the plan from
  Home Assistant; headless there is no such route. `readme-shots.js` emits an inline SVG
  data URI whose rooms are the same percent-coordinate polygons the segment overlay
  uses, square because `.evcc-map-container` is `aspect-ratio: 1` and
  `.evcc-map-image` is `object-fit: contain` — any other ratio letterboxes and the
  polygons drift off the walls.
- **Seven shots reuse the all-states gallery fixtures** rather than carrying a second
  copy that could drift from them. Where such a shot needs one accessor changed, it
  declares an `overlay` instead of editing the gallery entry, whose render is a
  committed visual baseline.

Two of the fifteen are driven by a **real `VacuumCardState`**, via the `real` layer in
`makeStubState` (resolution order: overrides → header essentials → real state →
recording null-object). The Themes tab reads `_ensureThemeState()` and
`resolvedTheme()`, which are an implementation — a mutable sub-tab/draft/facet object,
and several hundred resolved token values seeded from the room-fill palette and the
floor-texture registry. A hand-written stand-in for either would be a transcript that
drifts from the thing it transcribes, so the fixture builds the real object and seeds it
with the shipped library from `gallery/themes/`.

---

## Visual baselines — the Docker workflow

Visual regression only works if baselines are generated in the **same**
environment that gates them. That environment is the pinned image
`mcr.microsoft.com/playwright:v1.60.0-noble` — the same one CI uses. Run it via
PowerShell (the Bash tool mangles `--workdir`):

```powershell
# regenerate baselines after an INTENDED visual change
docker run --rm `
  -v "${PWD}:/work" -v evcc_harness_nm:/work/node_modules -w /work `
  mcr.microsoft.com/playwright:v1.60.0-noble `
  bash -lc "npm ci && node harness/build.mjs && VISUAL=1 npx playwright test -c harness/playwright.config.mjs visual --update-snapshots"
```

Drop `--update-snapshots` to **verify** against the committed baselines instead
(this is exactly what CI does). The `-v evcc_harness_nm:/work/node_modules`
anonymous-ish named volume keeps the container's Linux dependency binaries (esbuild,
Chromium) from clobbering the host's, and is reused across runs so only the first
pays `npm ci`.

To see what an edit changed: run **without** `--update-snapshots` first — the
failing screenshots are the blast radius — then re-run with it to accept.

---

## CI

| Workflow | Trigger | Does |
|---|---|---|
| `.github/workflows/card-visual.yml` | PR (any branch) or push **to `master`** touching `src/**`, `harness/**`, `package.json`, `package-lock.json`, or the workflow file | runs `visual` + `device-theme` in the pinned image; uploads the diff report on failure |
| `.github/workflows/node-tests.yml` | PR or push **to `master`** touching `scripts/**`, `src/theme-tags/**`, `harness/lib/**`, the animal-svg frontend, gallery animals, or `package.json` | `node --test scripts/*.test.mjs harness/lib/*.test.mjs` in the **pinned Playwright image** — covers the Chromium-driven sanitiser gates (animal SVG **and** the locale intake `sanitize-locale.test.mjs`), the submission/PR-gate cores, and the gallery-HTML builder |
| `.github/workflows/theme-intake.yml` | `workflow_dispatch`, or push/PR to `gallery/themes/*.json`, `docs/**`, `mkdocs.yml`, or `harness/**` (push also on the workflow file) | four jobs (gallery / docs / publish / deploy): renders each theme export through the ingest gate **and** builds the MkDocs docs site (`mkdocs build --strict`); uploads PNG + docs artifacts (PR/dispatch) and **on push to master publishes both to the one GitHub Pages site — gallery at `/`, docs at `/docs`** — one-time: enable Pages → *GitHub Actions* source |
| `.github/workflows/theme-submission.yml` | a `theme-submission`-labelled issue is opened | validates a pasted export, renders its preview, and opens a reviewable PR with the preview inline ([frontend/render-harness §8](../../dev/frontend/render-harness.md#8-theme-submission-issue--pr)) — not a gate, no spec; one-time: a `theme-submission` label + "Allow Actions to create PRs" |

Both run in the pinned image, so local-Docker and CI agree byte-for-byte. They
require `package-lock.json` to be committed (for `npm ci`).

`tests.yml` is the separate Python (pytest) gate. The Node test suites have their
own workflow, `node-tests.yml` (above): it runs **every** `scripts/*.test.mjs`
plus `harness/lib/*.test.mjs` in the pinned Playwright image — the
security-critical intake **sanitiser gates** (animal SVG via DOMPurify, and the
locale intake `sanitize-locale.test.mjs`) drive real Chromium, alongside the
gallery-submission bot core (`scripts/process-submission.mjs`) and the
gallery-HTML builder.

---

## Calibration knobs

Three values are spec, not defaults — tune them deliberately:

| Knob | Where | Current | Notes |
|---|---|---|---|
| diff threshold + budget | `harness/playwright.config.mjs` | `threshold 0.1`, `maxDiffPixels 60` | **absolute** pixel budget, not a ratio — a ratio hides small colored-region changes in a tall image |
| CVD pass criterion | `harness/cvd/report.mjs` (`FLOOR`) | ΔE2000 ≥ 15, 10 pairs × 3 sims | fix the palette, not the floor |
| fixture content | `harness/fixtures/gallery.js` | all colored branches per tab | a new state-token must get a gallery row or the completeness gate fails |
| card content floors | `harness/shoot-cards.mjs` (`GATES`) | per-card chip / room / step / height minima | raise them when a card gains a section; a floor low enough to cover all three cards catches none of them |
| panel-shot content floors | `harness/fixtures/readme-shots.js` (`gate`) | per-shot selector counts / required + forbidden text / height | each shot's floor lives next to its fixture; raise it when the tab gains a section, and check it still *fails* on an emptied fixture |

---

## Gotchas

- **Node can't import `src/*.js` directly.** Those are ESM-syntax `.js` files in a
  package with no `"type": "module"`, so Node reads them as CommonJS. They're only
  ever consumed by esbuild. Test code reaches src **through the bundle**
  (`window.__evcc.*`), never by importing it. The `harness/cvd/*.mjs` and
  `harness/bundles/*.mjs` files *are* `.mjs`, so those import fine Node-side.
- **Animations are frozen** in the harness (`freeze` flag + Playwright
  `animations: 'disabled'`) so the pulse/progress animations don't make diffs
  flaky.
- **The visual gate is structural.** It catches layout / z-index / missing-element
  regressions. Subtle small-region color changes are the **CVD gate's** job — a
  whole-image pixel budget intentionally won't flag them.
- **Everything renders from `src/`, never from the shipped bundle.**
  `harness/build.mjs` bundles the mount entry — panel *and* standalone cards — out of
  `src/`. Pointing any of it at `custom_components/eufy_vacuum/frontend/*.js` would
  render whatever was last deployed (that bundle only changes on
  `npm run build:deploy`) while every check stayed green.
- **Don't sweep the harness into an `eufy_vacuum` release.** `harness/`,
  `.github/workflows/*`, `gallery/`, and the `package.json` devDeps are tooling;
  only `src/`, `custom_components/`, and `tests/` ship.

### Escaping state is invisible in the source, and that is the real hazard

`translate()` returns text that is ALREADY HTML-escaped (Trust Model B). Backend
strings and user-controlled names are RAW. Both flow through variables with
names like `attentionSummary`, and nothing at the sink can tell them apart:

```js
// SAFE — the trust decision is made where the value ORIGINATES
const summary = haveCount
  ? this.t("maintenance.attention_summary", { count })   // already escaped
  : this.escapeHtml(upkeep.attention_summary ?? "");      // untrusted -> escape here

// UNSAFE — one escape at the sink cannot serve both branches
const summary = haveCount ? this.t(...) : upkeep.attention_summary;
html += `<div>${this.escapeHtml(summary)}</div>`;         // double-escapes branch 1
```

Escaping at the sink double-escapes the translated branch (the user reads
`d&#39;entretien`) and removing it un-escapes the untrusted branch (an XSS
regression). Both were live in this file simultaneously, and the second was
introduced WHILE fixing the first — the entity gate went green on a change that
had quietly removed the protection.

So: **decide trust at the branch, never at the sink.** Where a variable can hold
either kind, say so in its name.

Neither direction is fully gated. `i18n-escaping.spec.mjs` catches
double-escaping; nothing yet asserts that a backend-sourced string reaching an
innerHTML sink was escaped. That gap is known, not covered.
