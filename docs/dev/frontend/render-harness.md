# Render Harness

The render harness is a headless tool that renders the **real card** outside
Home Assistant — for visual-regression, colorblind validation, and theme
previews. It lives in `harness/` (plus `src/renderers/badge-marks.js`, which
ships) and is wired to CI. This document explains how it works and the one
architectural property the whole thing rides on.

It is one tool with several consumers, not several tools. Each consumer
(iteration, regression, colorblind, sharing) is fed the **same real render** and
differs only in the token bundle supplied and what's done with the output.

---

## 1. The load-bearing property

Two facts about the card (see [card-architecture](architecture-overview.md))
make a headless harness cheap:

1. **Renderers are pure.** Every renderer is `render(ctx) → HTML string`,
   reading state through one narrow accessor (`state.foo?.() ?? fallback`), with
   no reach into HA, the backend, or globals. A stubbed `state` drives any tab.
2. **Color lives in tokens.** Renderers emit structure + `--evcc-*` custom-
   property references; the actual colors live in the tokens. Structure and color
   are therefore **orthogonal inputs** to one render path.

Two consequences the design rides on:

- **One fixture × N bundles = the whole matrix, free.** Author a tab's fixture
  once; feed it default / protanopia / deuteranopia / colorblind-safe bundles and
  the same render re-colors itself. Nothing is ever hand-colored.
- **No test/prod skew.** The harness renders the identical path that ships,
  differing only in the token values fed in. A green check is a guarantee about
  the card that ships, not a proxy for it.

The one place the card breaks purity is `src/renderers/rooms.js`, which reads
`window.AnimalSVG` directly at render time. The harness stubs that global;
routing it through `ctx` is a tracked follow-up.

---

## 2. Headless mount

`harness/mount-entry.js` is bundled by esbuild (`harness/build.mjs`) into
`harness/dist/mount.js` (IIFE) and loaded into a Playwright Chromium page. It
exposes `window.__evcc`.

It recreates the **exact ship path**, not an approximation:

- Composes `renderHeader(ctx) + renderView(ctx)` (`src/render-cycle.js`) into the
  same shadow-DOM frame as `src/main.js` `_ensureShellFrame()` —
  `<ha-card><div class="evcc-shell">…</div></ha-card>` with the real `STYLES`
  (`src/styles/index.js`) injected.
- Applies a flat `--evcc-*` bundle as inline custom properties on the host,
  mirroring `applyDynamicTheme` (`src/styles/apply-theme.js`).
- Supplies a stub `state` and a stub `card` (the renderers read
  `_config/_state/_renderers/_view/_mobileMoreOpen` and, for rooms,
  `_learningController`).

Two harness-only shims stand in for the HA host: an `<ha-card>` chrome style
(HA provides the card background/border at runtime) and an optional animation
freeze for deterministic capture. Both are clearly marked and never shipped.

`window.__evcc` surface:

| Member | Purpose |
|---|---|
| `render(view, opts)` | Render one tab. `opts`: `bundle`, `overrides`, `controller`, `width`, `freeze`, `modal` (a renderer name to mount as a body-level modal — §3). Returns `{ok, error?, misses}` — never throws to the page. |
| `renderGallery(id, opts)` | Render an all-states gallery entry (§3). |
| `renderThemePresets(themes, opts)` | Render the Themes-tab presets grid driven by **real** state — a `VacuumCardState` seeded with the theme library, the facet filter / search / Browse-gallery UI, so the picker is captured on genuine state (the null-object stub can't exercise the filter). Backs `shoot-theme-picker.mjs`. |
| `ingestTheme(envelope)` | The intake gate (§6). |
| `registerLocale(lang, catalog)` | Inject a foreign/pseudo locale catalog into the in-page i18n registry (`src/i18n/index.js`) before rendering with `opts.lang`; used by the i18n-locale / i18n-layout / i18n-rtl gates. |
| `makePseudoLong(base)` | Build the layout-stress (pseudo-long) catalog in-page (`harness/lib/pseudo-locale.mjs`), avoiding a Node-side `en.js` import. |
| `en`, `flattenLocale` | The English manifest + the flatten function, exposed so a Node-side spec can flatten a shipped locale JSON in-page — Playwright's Node-side loader treats a typeless `.js` as CJS and can't reparse `en.js`/`flatten.js`'s ESM exports directly, so specs read the locale file in Node and hand the raw object to the page instead. **`flattenLocale` returns `{ flat, coverage }` — seed with `.flat`.** Any other property yields `undefined`, and `registerLocale(code, undefined)` does not throw: it registers an empty catalog, the render silently falls back to English, and a gate named "survives real German" passes green while rendering English. That shipped on 2026-08-07 (`.clean`, which never existed) and went unnoticed for exactly that reason. A seeding helper should assert the returned key count, not trust the render to notice. |
| `semanticTokens` | The registry-derived semantic-color token set (§3). |
| `badgeMarks`, `markViewBox` | The shape-mark SVGs (§5). |
| `tokenMap`, `VIEWS`, `VIEW_ORDER` | Registry + view constants for tests. |
| `VacuumCardState` | The real `src/state/index.js` state class, exposed so tooling can drive genuine state (e.g. per-device theme, driven by `device-theme.spec.mjs`). |
| `gallery` | The gallery-entry metadata list (`id`, `view`, `label`, `tokens`, `clip`, `modal`, `font`) for tests. |
| `mountCard(id, opts)` | **Opt-in.** Mounts one **standalone Lovelace card** (`cards.js` fixtures: `room` / `dashboard` / `profile`) as its real custom element into a width-pinned holder, with a stubbed `callService` served from `CARD_SERVICE_RESPONSES` and a settle pass for the card's one-shot `_ensureData()`. `opts`: `bundle` (flat `--evcc-*` map, applied to the host exactly as `apply-theme.js` does — an EMPTY bundle is the real cold-dashboard look, since the cards read the tokens with literal fallbacks), `freeze`. Returns a serialisable **render report** counted off the LIVE shadow tree (`chips` / `rooms` / `steps` / `text` / heights) — that report is the point, because a card that fails to mount is a small empty box that passes any check asserting only that a file exists. Backs `shoot-cards.mjs`. |
| `cards` | Standalone-card fixture metadata (`id`, `element`, `file`, `label`, `width`). |
| `mountRealCard(opts)` | **Opt-in.** Builds the panel card's own frame rather than the harness's recreation of it. |
| `renderReadmeShot(id, opts)` · `readmeShots` | The committed README panel shots and their metadata (`id`, `file`, `view`, `label`, `clip`, `needsThemes`); gate-measured against the live tree before anything is written. Backs `shoot-readme.mjs`. |
| `version` | Surface version (`1`). |

### The stub state

`harness/fixtures/stub-state.js` is a **recording null-object**: any accessor the
fixture doesn't define returns a callable, indexable, iterable, coercible value
that absorbs `.map()`, `.length`, property chains, and interpolation without
throwing. The header essentials (name, status, battery) are made real so the
chrome renders honestly.

This is deliberate. The renderers touch ~184 distinct accessors; hand-typing
empties for all of them would be throwaway work. The null-object lets the smoke
test prove the **pure-renderer contract** (a throw means a renderer reached
outside `state`/`ctx`) without realistic data, and records the accessor surface
each tab touches (`harness/census.mjs`) as the seed for real fixtures.

#### The stub renders EMPTY STATES — do not gate content on it

The same property that makes the null-object safe makes it **contentless**: an
absorbed accessor yields nothing to iterate, so a view driven by a collection
renders its empty state. Measured 2026-08-07 at width 500, five of the nine
views in `VIEW_ORDER` render a placeholder rather than content:

| view | under the stub | populated fixture that exists |
|---|---|---|
| `rooms` | empty state, 269 chars | `rooms-active` |
| `maintenance` | "No upkeep items need attention", **0 cards** | `maintenance` |
| `metrics` | partial (stat tiles, empty panel) | `metrics-overview` |
| `learning_review` | 2 empty states, 0 cards | `review-badges` |
| `room_rules` | empty state, 277 chars | `room-rules` |

`base_station`, `theme`, `map_config` and `setup` render real content because
they are driven by config and capability rather than by collections.

**Consequence for gates.** A spec that loops `VIEW_ORDER` through `renderTab`
and asserts a layout property is, for those five, asserting it about a
placeholder — and reports zero findings, which is indistinguishable from a
clean pass. This is how a card-header clipping bug reached a user's phone with
a fully green i18n suite: the densest text component in the panel had never
been rendered under any gate. Coverage must be derived from the SCOPES actually
exercised, never from the finding count.

So: gate *chrome* properties (tab strip, header, nav) through `renderTab`, and
gate *content* properties through `renderGallery` with the fixture named above.
The Cyrillic and maintenance-cards passes in `i18n-layout.spec.mjs` are the
worked examples. When you do, assert the fixture produced rows
(`expect(cards).toBeGreaterThan(n)`) — otherwise an emptied fixture silently
restores the very hole you closed.

---

## 3. Fixtures and all-states galleries

`harness/fixtures/gallery.js` holds fixtures that force a tab to show **every
colored state at once** — the honest instrument for colorblind validation.
Distinguishability is relative: whether error-red is confusable with success-
green can only be judged with the two co-present and adjacent at real size. A
gallery of all states in real layout is that instrument; isolated swatches are
not. Current galleries: rooms (queue + confidence tiers), learning review (job
badges), the **External Jobs** subtab (app-started runs awaiting review), the
two-step **review wizard** (modal), and a
status-dot strip — plus **populated single-tab fixtures** (metrics, maintenance,
room rules) that stub a tab's data accessors with realistic content. Those last
serve a purpose beyond colorblind validation: the theme-preview gallery (§7)
renders them so a shared theme shows on real content, not empty stub tabs. (They
are deliberately date-math-free so the baselines stay deterministic.)

**Subtab and modal capture.** The per-tab shooter renders each tab at its default
subtab, so non-default surfaces are captured as gallery fixtures instead. A fixture
flips a subtab by overriding its state accessor (e.g. `reviewSubtab: () =>
"external"`). A **body-level modal** — the review wizard mounts to `document.body`
via `main.js` `_renderModals()`, not `renderView` — is captured by naming its
renderer in the fixture's `modal:` field; `render()` then mounts that one modal
into a shadow-root host with `MODAL_HOST_STYLES` (faithful to the ship path), and
the entry's `clip` crops the shot to the modal shell. Modal entries render under
emulated `prefers-color-scheme: dark` so the modal matches the (dark) card — the
default bundle doesn't theme the modal host, which would otherwise trip the modal's
light-hardening.

The gallery is **enumerated from the token registry**, not hand-listed.
`harness/semantic-tokens.js` derives the semantic-color set from the *Status,
Confidence & Alerts* and *Learning & Metrics* groups of `THEME_TOKEN_REGISTRY`.
The completeness gate asserts every such token is claimed by a gallery entry (or
allowlisted with a reason) — so a new colored state-token fails the gate until it
has a fixture row.

---

## 4. Visual regression

`harness/tests/visual.spec.mjs` renders each tab + gallery and diffs against
committed baselines (`harness/tests/__screenshots__/`) via Playwright's
`toHaveScreenshot`. This closes the frontend host-boundary gap the backend tests
can't reach (z-index, shadow DOM, layout, flood).

**Determinism is the whole game.** Chromium font/anti-alias rendering differs
across OSes, so baselines are generated *and* gated in one pinned image —
`mcr.microsoft.com/playwright:v1.60.0-noble` — making the comparison byte-for-
byte stable. The visual specs are gated to CI / `VISUAL=1` (other platforms
would mismatch); smoke, completeness, CVD, shape, intake, tab-gating, and
device-theme gates run everywhere. See [testing/frontend/render-harness](../../testing/frontend/render-harness.md) for
the regenerate-baselines workflow.

**Structural, not color.** The diff budget is an **absolute** `maxDiffPixels`,
not a ratio — a ratio lets a small colored-region change hide inside a tall image
(a recolored confidence chip is ~1% of the rooms gallery, so a 1% ratio misses
it). The whole-image gate is for **structural** regressions (layout / z-index /
missing elements, which move many pixels); small-region **color** correctness is
the CVD gate's job (§5).

---

## 5. Colorblind (CVD) validation

`harness/cvd/` simulates color-vision deficiency and measures whether the
semantic palette stays distinguishable.

- **Simulation** (`simulate.mjs`): Machado et al. 2009 matrices at severity 1.0
  for protanopia + deuteranopia; Brettel 1997 two-half-plane projection for
  tritanopia (Viénot is inaccurate for tritan). All applied to **linear RGB**.
  Full dichromat severity — a pass covers milder anomalous trichromats.
  Constants verified against DaltonLens / libDaltonLens.
- **Difference** (`color.mjs`): CIEDE2000.
- **The gate**: the 10 pairs among the five color **groups** {success, warning,
  error, info, muted}, under each of the three sims = 30 ΔE values, floor
  **ΔE2000 ≥ 15** (defensible at dot size given the area effect). `warn`/`likely`
  are excluded — they share the warning hue by design; the shape cue (§6) carries
  them. Watch the muted ↔ status "sleeper": a status loses chroma under
  protan/deutan and drifts toward grey.

When a pair misses, **fix the palette, not the floor.** `harness/bundles/cvd-safe.mjs`
is the validated result (all 30 ≥ 15, worst 18.1):

| group | hex | note |
|---|---|---|
| success | `#0C8F86` | dark cyan-teal |
| warning | `#E9A100` | amber |
| error | `#D6403A` | **warm red** (magenta's blue collides with info-blue under protan) |
| info | `#0F4C86` | deep blue (reference / baseline) |
| muted | `#BCC2C7` | light neutral grey |

The trick: success and error sit at **similar lightness but opposite blue-yellow**
(the one axis protan/deutan preserve), and the five hues are luminance-spread so
none desaturates into grey.

**The bundle is five overrides.** `conf-*`, `color-*`, `confidence-*`,
`status-dot-*`, and `learning-confidence-*` all cascade from `--evcc-sem-*` via
`var()` chains (see `themes/preloaded.py` `_build_release_theme_colors`), so
overriding the five anchors recolors the whole semantic palette. That palette
ships as the selectable **"Colorblind Safe"** preloaded theme
(`custom_components/eufy_vacuum/themes/preloaded.py`); see
[theme-system](theme-system.md).

> The five hexes live in both `harness/bundles/cvd-safe.mjs` (JS, harness-
> validated) and `themes/preloaded.py` (Python). Cross-language, comment-linked —
> keep them in sync.

---

## 6. Shape marks — the redundant cue

Color resolves only five groups; the six mapping-bounds badge states need a
sixth distinguisher, and colorblind users shouldn't rely on hue at all. So every
badge carries a per-state SVG **mark** (`src/renderers/badge-marks.js`, always
on, every theme):

| state | mark | state | mark |
|---|:--:|---|:--:|
| ok | ✓ | outlier | ✕ |
| likely | ◐ | excluded | – |
| warn | ! | baseline | ◆ |

All six are authored from one source (shared viewBox + stroke weight,
`currentColor`) — no ASCII/symbol-font mixing, which would land glyphs at
inconsistent weights and break the grayscale comparison.

`harness/tests/shape-marks.spec.mjs` rasterises each mark grey-on-white at dot
size and asserts every pair differs in **flat grayscale** — one property that
covers monochromacy and every CVD type at once. `likely (◐)` ≠ `warn (!)` carries
the shared-color pair; `ok (✓)` ↔ `outlier (✕)` is the safety-critical good-vs-bad
pair and is held to a higher bar.

---

## 7. Theme-export intake

The harness accepts any theme **export** (the export/import schema, see
[theme-system](theme-system.md)) and renders a preview of the real card
recolored by it — the config is the seed, the render is the deliverable.

- **Ingest gate** (`window.__evcc.ingestTheme`, `harness/tests/intake.spec.mjs`)
  — the load-bearing safety. It reuses the same validate + clamp path as
  `import_theme` (`clampThemeScalars` + the token registry): keep only known
  registry `--evcc-*` keys (drops unknown keys and unknown floor-type
  namespaces), clamp bounded scalars to range, drop non-primitive values, never
  eval. Values reach the card via `setProperty` (CSS-validated), never HTML. This
  is the entire reason running a stranger's export in CI is safe — the export is
  data, not code.
- **Preview** (`harness/preview.mjs`) — builds the gallery from
  `gallery/themes/*.json`. Per theme, scope drives the detail render: a full
  theme → the all-states galleries, the populated single-tab fixtures (so the
  theme shows on real content, not empty stubs), and a tour of the remaining tabs;
  a texture-scoped export → the rooms gallery. It also writes a single-room-card **thumbnail** per
  theme and a themes index (`harness/out/preview/themes/index.html`) that grids those thumbnails
  (each linking its detail page) under a **"+ Submit a theme"** button (§8). A per-theme
  `_contact-sheet.png` is produced too — the submission bot embeds it inline in
  the PR (§8). The published Pages site fronts the galleries with a landing hub
  (`harness/build-landing.mjs` + `lib/landing-html.mjs`/`lib/site-nav.mjs`, live theme/animal
  counts read from the committed `gallery/*` sources) linking `/themes/`, `/animals/` (the
  animal-gallery counterpart, `harness/preview-animals.mjs`, driven by `gallery/animals/*.json`),
  and the docs.
- **Trigger** (`.github/workflows/theme-intake.yml`) — `workflow_dispatch` for a
  one-off theme render, or `push`/`pull_request` on `gallery/themes/*.json`,
  `gallery/animals/*.json`, the animal-svg source tree, `docs/**`, or
  `mkdocs.yml` (`:31-33`/`:40-42`, `:35-36`/`:43-44`). `push` additionally
  watches `harness/**` and the workflow file itself (`:34`/`:37`) — `pull_request`
  does not (`:39-44`), so a harness-only PR does not trigger this workflow at
  all; only a push (e.g. a merge to master) picks up a harness-only change. A
  `gallery` job renders the theme preview(s) + the `/animals`
  gallery + the landing page; a separate `docs` job builds the MkDocs site
  (`--strict`, so a broken link/anchor fails CI) — they run in parallel and both
  upload their output as workflow artifacts. **This one Pages site serves both**
  the gallery (theme render *or* docs change) and the docs (gallery change), so a
  docs-only push still rebuilds the (unchanged) gallery and vice versa, keeping
  the combined deploy internally consistent. PRs and manual dispatches build +
  validate only; only on **push to master** does a `publish` job assemble both
  artifacts into one tree (gallery at `/`, docs at `/docs/`) and a `deploy` job
  ships it to **GitHub Pages** (`actions/deploy-pages`) at the repo's Pages URL.
  One-time setup: enable Pages with the *GitHub Actions* source in repo settings.

---

## 8. Theme submission (issue → PR)

Sections 1–7 are the engine; this is the **front door** that lets anyone add a
theme to the gallery without touching the repo. It turns a pasted export into a
reviewable pull request with a rendered preview, and never auto-merges.

**Entry point.** The gallery lobby's **"+ Submit a theme"** button links to a
GitHub **issue form** (`.github/ISSUE_TEMPLATE/theme-submission.yml`): a
`render: json` textarea for the export, optional **vibe tags / author / author
URL / submitted-by** credit fields, a **colorblind-safe claim** checkbox, and an
acknowledgement. The form auto-applies the `theme-submission` label — the only
signal the bot keys on.

**The bot** (`.github/workflows/theme-submission.yml`, on
`issues: [opened, reopened, edited]`, gated `if` the `theme-submission` label is
present). Its core is a **pure transform** — `scripts/process-submission.mjs`,
issue-body → `{envelope, report}`, unit-tested by `process-submission.test.mjs`
and sharing the **same theme-tags core** the card and gallery use, so a
submission is tagged and verified identically to an in-card theme:

1. **Extract + validate.** The form's `render: json` field wraps the export in a
   fenced JSON block; the bot regex-extracts it, `JSON.parse`s it, and
   sanity-checks it's a theme export (`theme.tokens` / `colors` / `alpha`). On
   any failure it comments on the issue with the fix and stops — malformed input
   never becomes a file. The deeper safety is the **ingest gate** (§7): the
   render step runs the export through the same validate + clamp path as
   `import_theme`, so a hostile export is data, not code.
2. **Tag + verify + stamp.** The accepted theme is stamped `source:"community"`,
   keeps the submitter's vibe tags (system words stripped, so a submission can't
   spoof a derived facet), and carries author / author_url / submitted_by. Facet
   tags are **derived** from the palette and colorblind-safety is **verified** by
   simulation — never author-asserted; a failed colorblind claim is
   **non-blocking** (badge left off, report says which status pair collapsed).
   The **author URL** is policy-checked (`isAcceptableAuthorUrl`): only a direct
   `http(s)` link to a non-shortener host is kept — dangerous schemes
   (`javascript:` / `data:` / …) and URL shorteners are dropped, non-blocking,
   with the reason in the report (this is also the stored-XSS defense, since the
   credit becomes a gallery `<a href>`). The bot then writes
   `gallery/themes/{slug}.json` (`slug` = sanitized theme name + `-{issue#}`).
3. **Render** (`harness/build.mjs` + `harness/preview.mjs`) the preview for that
   one theme — its detail page and a `_contact-sheet.png`.
4. **Open (or update) a PR** carrying just `gallery/themes/{slug}.json` on a
   `theme-submission/{slug}` branch, body `Closes #{issue}`. A reopen/edit reuses
   the same branch + PR rather than piling up new ones. Merging it lands the
   theme on master and triggers the §7 publish.
5. **Comment** the full report (tags, credit, colorblind verdict) back on the
   issue with the PR link.

**Why the preview is rendered here, not on the PR.** A PR opened with the
built-in `GITHUB_TOKEN` does **not** trigger other workflows (GitHub's
anti-recursion rule), so `theme-intake.yml` won't run on the bot's PR. Instead
the bot pushes the contact sheet to an off-master **`gallery-previews`** branch
and embeds it in the PR body via a `raw.githubusercontent.com` URL — so the
reviewer sees the render **inline**, with no artifact download. That branch is
never merged; it only holds preview images and is safe to reset or delete (the
bot recreates it on the next submission).

**Reviewing a submission** (maintainer): open the PR, look at the inline preview
(and the full per-tab artifact on the run if you want it), then **merge** to
publish or **close** to reject. The human is the only gate.

**One-time setup.** Both are required, or the bot silently skips / can't open the
PR (also documented in the workflow header):

1. A **`theme-submission` label** must exist — issue forms only apply labels that
   already exist, so without it the gating `if` never matches and the bot no-ops.
2. **Settings → Actions → General → "Allow GitHub Actions to create and approve
   pull requests"** must be on, or `pulls.create` is rejected.

(Plus the §7 Pages enablement, for the publish that runs after a merge.)

---

## 9. File map

| Path | What |
|---|---|
| `harness/mount-entry.js` | Browser entry; `window.__evcc`. Bundled by `build.mjs`. |
| `harness/fixtures/stub-state.js` | Recording null-object stub. |
| `harness/fixtures/gallery.js` | All-states gallery fixtures. |
| `harness/fixtures/cards.js` | The three standalone-card fixtures (`CARD_FIXTURES`), their seeded state (`CARD_STATES`), and the stubbed service responses (`CARD_SERVICE_RESPONSES`) their `callService` is served from. |
| `harness/fixtures/readme-shots.js` | Per-shot definitions for the committed README panel captures — view, file, clip, seeded state, and the **floor** each shot must clear against the live tree before its PNG is written. |
| `harness/semantic-tokens.js` | Registry-derived semantic-color enum. |
| `harness/cvd/` | `simulate.mjs` (Machado+Brettel), `color.mjs` (CIEDE2000), `report.mjs` (matrix), `tune.mjs` (palette scratchpad). |
| `harness/bundles/` | Flat `--evcc-*` maps: `default`, `cvd-safe`. |
| `harness/lib/mount-page.mjs` | Node helpers: load bundle into a page, render. |
| `harness/lib/pseudo-locale.mjs` | Builds the layout-stress (pseudo-long) catalog (backs `makePseudoLong`). |
| `harness/lib/gallery-html.mjs` | Playwright-free gallery HTML generator (index filter bar + per-theme pages) shared by `preview.mjs` and the dry-run; owns the author-URL XSS-escaping contract. |
| `harness/lib/gallery-html.test.mjs` | `node --test` unit tests for the gallery HTML escaping / author-URL contract. |
| `harness/lib/animal-gallery-html.mjs` (+`.test.mjs`) | The animal-gallery counterpart of `gallery-html.mjs` (per-animal pages + faceted index). |
| `harness/lib/landing-html.mjs` (+`.test.mjs`) · `harness/lib/site-nav.mjs` | Pages-site landing hub (live gallery counts) + the shared depth-aware nav bar linking landing / themes / animals / docs. |
| `harness/build.mjs` · `shoot.mjs` · `shoot-gallery.mjs` · `shoot-theme-picker.mjs` · `census.mjs` | esbuild + capture CLIs (`shoot-theme-picker.mjs` shoots the Themes picker with a real-state fixture). |
| `harness/shoot-locales.mjs` | Renders every tab in each real bundled locale (de/fr/es/nl/it/pt/ru) next to English, plus a per-language contact sheet and an overflow probe, via `opts.lang` pinned as the explicit `config.i18n.locale` override — which bypasses the draft-gate, i.e. it shows what a user sees after picking that language from the editor. |
| `harness/shoot-pseudo.mjs` | English-vs-pseudo-long side-by-side per tab + horizontal-overflow probe. |
| `harness/shoot-cards.mjs` (`npm run harness:cards`) | Mounts and shoots the **three standalone Lovelace cards** via `mountCard` / `cardFixtures` (`lib/mount-page.mjs`). Writes `docs/screenshots/card-<id>.png` (committed) + `harness/out/cards/`. `--freeze` is the **default** here, unlike the tab shooters, so a re-run with nothing changed reproduces the same bytes. **Gated**: a card that fails to mount renders as a small empty box, which passes any check that only asserts a file exists — so each shot is gated on what the live shadow tree actually contains (chips / rooms / manifest steps / height) **before** anything is written, and the run exits non-zero on a miss. |
| `harness/shoot-readme.mjs` (`npm run harness:readme`) | Shoots the committed **README panel screenshots**, one full-tab capture per view, into `docs/screenshots/` + `harness/out/readme/`. Per-shot floors live in `harness/fixtures/readme-shots.js`. **Gated on the same failure it exists to prevent**: a tab that renders its EMPTY state screenshots perfectly — right chrome, right active tab, right theme, nothing in it. Nothing is written until the live shadow tree meets the shot's declared floor (element counts for the selectors that ARE the view, required substrings, a height floor, zero `.evcc-empty` nodes, the expected tab actually marked active, and no `undefined` / `NaN` / `[object Object]` in the rendered text); a miss is reported and skipped with its previous PNG left untouched, and the run exits non-zero. |
| `harness/build-landing.mjs` | Writes the Pages landing page after the galleries render. |
| `harness/preview-animals.mjs` | Renders the `/animals` gallery from `gallery/animals/*.json` (real animal-svg framework, all six poses, detail page + faceted index). |
| `harness/preview-index-dryrun.mjs` | Fast no-Chromium gallery-index dry-run: runs committed themes through `lib/gallery-html.mjs` with cheap swatch thumbnails to eyeball the filter bar. |
| `harness/preview.mjs` | Builds the theme gallery: per-theme detail pages, thumbnails, contact sheets, and the themes index. |
| `harness/tests/*.spec.mjs` | smoke · gallery-completeness · visual · cvd · shape-marks · intake · tab-gating · device-theme · i18n-layout · i18n-locale · i18n-rtl (the i18n gates render pseudo/foreign catalogs: i18n-layout asserts no layout overflow under a pseudo-long locale @500px/@390px **plus a real-German pass @390px and a maintenance-CARDS pass in en/de/nl/ru**, i18n-locale asserts the `renderers.t` wiring actually switches the UI, i18n-rtl asserts a real Arabic/Hebrew catalog under `dir="rtl"` also survives the layout probe and that the host actually carries `dir="rtl"`). |
| `src/renderers/badge-marks.js` | The six per-state shape marks (ships). |
| `gallery/themes/*.json` | Theme exports published to the gallery (one JSON per theme). |
| `.github/ISSUE_TEMPLATE/theme-submission.yml` | Submission issue form (the "Submit a theme" target). |
| `.github/workflows/card-visual.yml` · `theme-intake.yml` · `theme-submission.yml` | CI: visual regression · gallery+animals+landing+docs Pages publish · submission bot. |

> **Every shooter renders FROM `src/`, through `harness/build.mjs`** — never from
> `custom_components/eufy_vacuum/frontend/`. That bundle only changes on
> `npm run build:deploy`, so pointing a shooter at it would picture the last deploy
> while every check stayed green.

---

## 10. Judgment inputs (tunable, by design)

Three knobs are spec, not boilerplate — they live in code with comments, not
hidden defaults:

| Input | Where | Current |
|---|---|---|
| Fixture content per tab | `harness/fixtures/gallery.js` | all colored branches forced on one screen |
| Diff threshold + masking | `harness/playwright.config.mjs` | `threshold 0.1`, `maxDiffPixels 60` (absolute), animations frozen |
| CVD pass criterion | `harness/cvd/report.mjs` | 10 pairs × 3 sims, ΔE2000 ≥ 15 |

How to run, regenerate baselines, and read the gates:
[testing/frontend/render-harness](../../testing/frontend/render-harness.md).
