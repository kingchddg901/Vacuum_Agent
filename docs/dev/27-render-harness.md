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

Two facts about the card (see [19-card-architecture](19-card-architecture.md))
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
| `render(view, opts)` | Render one tab. `opts`: `bundle`, `overrides`, `controller`, `width`, `freeze`. Returns `{ok, error?, misses}` — never throws to the page. |
| `renderGallery(id, opts)` | Render an all-states gallery entry (§3). |
| `ingestTheme(envelope)` | The intake gate (§6). |
| `semanticTokens` | The registry-derived semantic-color token set (§3). |
| `badgeMarks`, `markViewBox` | The shape-mark SVGs (§5). |
| `tokenMap`, `VIEWS`, `VIEW_ORDER` | Registry + view constants for tests. |

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

---

## 3. Fixtures and all-states galleries

`harness/fixtures/gallery.js` holds fixtures that force a tab to show **every
colored state at once** — the honest instrument for colorblind validation.
Distinguishability is relative: whether error-red is confusable with success-
green can only be judged with the two co-present and adjacent at real size. A
gallery of all states in real layout is that instrument; isolated swatches are
not. Current galleries: rooms (queue + confidence tiers), learning review (job
badges), mapping review (the six bounds badges), and a status-dot strip.

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
would mismatch); smoke, completeness, CVD, shape, and intake gates run
everywhere. See [testing/07-render-harness](../testing/07-render-harness.md) for
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
[20-theme-system](20-theme-system.md).

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
[20-theme-system](20-theme-system.md)) and renders a preview of the real card
recolored by it — the config is the seed, the render is the deliverable.

- **Ingest gate** (`window.__evcc.ingestTheme`, `harness/tests/intake.spec.mjs`)
  — the load-bearing safety. It reuses the same validate + clamp path as
  `import_theme` (`clampThemeScalars` + the token registry): keep only known
  registry `--evcc-*` keys (drops unknown keys and unknown floor-type
  namespaces), clamp bounded scalars to range, drop non-primitive values, never
  eval. Values reach the card via `setProperty` (CSS-validated), never HTML. This
  is the entire reason running a stranger's export in CI is safe — the export is
  data, not code.
- **Preview** (`harness/preview.mjs`) — scope drives output: a full theme → a
  contact sheet of the all-states galleries; a texture-scoped export → the rooms
  gallery.
- **Trigger** (`.github/workflows/theme-intake.yml`) — `workflow_dispatch` for a
  one-off, or `push`/`pull_request` on `gallery/themes/*.json` for a versioned
  gallery. PRs and manual dispatches come back as workflow artifacts; on **push
  to master** the rendered gallery — a static `index.html` (built by
  `preview.mjs`) plus the per-theme images — is **published to GitHub Pages**
  (`actions/deploy-pages`). One-time setup: enable Pages with the *GitHub
  Actions* source in repo settings.

---

## 8. File map

| Path | What |
|---|---|
| `harness/mount-entry.js` | Browser entry; `window.__evcc`. Bundled by `build.mjs`. |
| `harness/fixtures/stub-state.js` | Recording null-object stub. |
| `harness/fixtures/gallery.js` | All-states gallery fixtures. |
| `harness/semantic-tokens.js` | Registry-derived semantic-color enum. |
| `harness/cvd/` | `simulate.mjs` (Machado+Brettel), `color.mjs` (CIEDE2000), `report.mjs` (matrix), `tune.mjs` (palette scratchpad). |
| `harness/bundles/` | Flat `--evcc-*` maps: `default`, `cvd-safe`. |
| `harness/lib/mount-page.mjs` | Node helpers: load bundle into a page, render. |
| `harness/build.mjs` · `shoot.mjs` · `shoot-gallery.mjs` · `preview.mjs` · `census.mjs` | esbuild + capture/preview CLIs. |
| `harness/tests/*.spec.mjs` | smoke · gallery-completeness · visual · cvd · shape-marks · intake. |
| `src/renderers/badge-marks.js` | The six per-state shape marks (ships). |
| `gallery/themes/*.json` | Watched theme-export gallery for intake previews. |
| `.github/workflows/card-visual.yml` · `theme-intake.yml` | CI: visual regression · theme preview. |

---

## 9. Judgment inputs (tunable, by design)

Three knobs are spec, not boilerplate — they live in code with comments, not
hidden defaults:

| Input | Where | Current |
|---|---|---|
| Fixture content per tab | `harness/fixtures/gallery.js` | all colored branches forced on one screen |
| Diff threshold + masking | `harness/playwright.config.mjs` | `threshold 0.1`, `maxDiffPixels 60` (absolute), animations frozen |
| CVD pass criterion | `harness/cvd/report.mjs` | 10 pairs × 3 sims, ΔE2000 ≥ 15 |

How to run, regenerate baselines, and read the gates:
[testing/07-render-harness](../testing/07-render-harness.md).
