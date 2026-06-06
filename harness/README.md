# Render Harness

Headless render-and-capture for the EVCC Lovelace card. One real render,
several consumers: theme iteration, visual-regression, colorblind
validation, and artifact preview/sharing — differing only in the token
bundle fed in and what's done with the output.

## Why it works

Renderers are pure: `render(ctx) -> HTML string`, reading state only
through the narrow `ctx.state` accessor, emitting structure + `--evcc-*`
references (color lives in tokens). So the harness recreates the **exact
ship path** — `renderHeader(ctx) + renderView(ctx)` composed into the
same shadow-DOM frame as `src/main.js`, with the same `STYLES` injected —
and feeds it a stub `state` plus a flat `--evcc-*` bundle. Identical path,
recolored only by the bundle ⇒ **zero test/prod skew**.

Structure and color are orthogonal inputs: the **fixture** (stub state)
decides which states are present; the **bundle** decides their color.
One fixture × N bundles = the whole matrix, free.

## Layout

| Path | What |
|---|---|
| `mount-entry.js` | Browser entry; exposes `window.__evcc.render(view, opts)`. Bundled by `build.mjs`. |
| `fixtures/stub-state.js` | Recording null-object stub (drives the smoke test). |
| `fixtures/gallery.js` | All-states galleries: real fixtures that force every colored branch onto one screen. |
| `semantic-tokens.js` | The registry-derived semantic-color token set — the one enum the gallery and CVD share. |
| `lib/mount-page.mjs` | Node helpers: load bundle into a Playwright page, render a tab. |
| `bundles/<name>.mjs` | A flat `--evcc-*` map. `default` = baked defaults. |
| `build.mjs` | esbuild → `dist/mount.js` (IIFE). |
| `shoot.mjs` | CLI: per-tab PNGs + contact sheet under `out/<bundle>/`. |
| `shoot-gallery.mjs` | CLI: all-states gallery PNGs + contact sheet under `out/gallery/`. |
| `tests/smoke.spec.mjs` · `tests/gallery-completeness.spec.mjs` | Run everywhere. |
| `tests/visual.spec.mjs` | Visual-regression: render + diff vs committed baselines (CI / `VISUAL=1` only). |
| `tests/__screenshots__/` | Committed **Linux** baselines (generated in the pinned image). |
| `playwright.config.mjs` | Runner config + `toHaveScreenshot` tuning. |

## All-states galleries

`fixtures/gallery.js` holds real fixtures that drive a tab to show **every
colored state at once** — the honest instrument for colorblind validation
(distinguishability is relative; states must be co-present at real size, not
a swatch strip). Current galleries: rooms (queue + confidence tiers), learning
review (job badges), mapping review (the six bounds badges), and a status-dot
strip (one real header per state).

`semantic-tokens.js` derives the semantic-color token set from the registry.
The `gallery-completeness` test asserts every such token is claimed by a
gallery entry (or allowlisted with a reason) — so a new colored state-token
fails the gate until it has a fixture row.

> Note: the mapping-review badge colors come from **non-registry** vars
> (`--evcc-success/--evcc-warning/--evcc-error/--evcc-accent/--evcc-text-muted`),
> so they sit outside the token registry and the CVD enum. Tracked as a
> single-source-of-truth gap to fold into `--evcc-sem-*`.

## Visual regression

`tests/visual.spec.mjs` renders every tab + gallery and diffs against committed
baselines in `tests/__screenshots__/` — the gate for frontend host-boundary
regressions (z-index, shadow DOM, layout) the backend tests can't reach.

Baselines are **Linux**, generated in the pinned Playwright image so they match
CI byte-for-byte; the env is pixel-deterministic. They're gated to CI /
`VISUAL=1` because other platforms render differently (fonts / AA). Tuning lives
in `playwright.config.mjs` → `toHaveScreenshot`: an **absolute** `maxDiffPixels`
budget, not a ratio — a ratio lets a small colored-region change hide inside a
tall image (a recolored confidence chip is ~1% of the rooms gallery, so a 1%
ratio would miss it).

Regenerate baselines after an intended visual change, from the repo root:

```powershell
docker run --rm -v "${PWD}:/work" -v evcc_harness_nm:/work/node_modules -w /work `
  mcr.microsoft.com/playwright:v1.60.0-noble `
  bash -lc "npm ci && node harness/build.mjs && VISUAL=1 npx playwright test -c harness/playwright.config.mjs visual --update-snapshots"
```

CI runs the identical image — `.github/workflows/card-visual.yml`.

## Theme intake & preview

Drop a theme **export** (the export/import schema) into `gallery/themes/*.json`
and CI renders the real card recolored by it (`.github/workflows/theme-intake.yml`,
same pinned image; previews come back as artifacts). Locally:

```bash
npm run harness:preview                              # all exports in gallery/themes/
node harness/preview.mjs gallery/themes/<file>.json  # one export
```

Every upload passes through the **ingest gate** (`window.__evcc.ingestTheme`) —
the same validate + clamp path as `import_theme`: only known registry
`--evcc-*` keys are kept, bounded scalars are clamped to range, malformed /
unknown-namespace exports are skipped, non-primitive values dropped, nothing
eval'd. Values reach the card via `setProperty` (CSS-validated), never HTML. So
previewing a stranger's export is safe. **Scope drives output**: a full theme →
a contact sheet of the all-states galleries; a texture-scoped export → the rooms
gallery. Gate tested in `tests/intake.spec.mjs`.

## Use

```bash
npm install                 # first time
npx playwright install chromium

npm run test:harness        # build + smoke + gallery-completeness
npm run harness:shoot        # build + screenshot all tabs (default bundle)
npm run harness:gallery      # build + screenshot the all-states galleries
node harness/shoot.mjs --bundle default --width 500
```

`dist/` and `out/` are build artifacts (gitignored). Committed baselines
for visual-regression land under `tests/` in Wave 3.
