# Render Harness Tests (frontend)

A separate test track from the Python suite: JS/Playwright tests that render the
**real card** headless and gate it for crashes, visual regressions, colorblind
distinguishability, and theme-intake safety. Architecture lives in
[frontend/render-harness](../../dev/frontend/render-harness.md); this is how to run it.

The harness is where the **rendered card** is tested — the ~1,900 Python cases
stop at the backend contract; these pick up at the shadow-DOM boundary. (A small
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
| `intake.spec.mjs` | the ingest gate skips malformed / unknown-namespace exports and clamps every value | everywhere |
| `device-theme.spec.mjs` | per-device theme resolution: the real `VacuumCardState.effectiveActiveThemeId()` fallback chain keeps a device pin through a pre-load, resolves it once the library loads, and clears it only when genuinely stale | everywhere (also re-run in `card-visual` CI) |
| `tab-gating.spec.mjs` | capability tab gating: `renderHeader` hides the Base Station nav tab when `supportsBaseStation()` is false (the S6 no-dock case), default-shown otherwise (Eufy-safe) | everywhere |
| `i18n-locale.spec.mjs` | the renderers resolve the *user's* language: a tab rendered under a registered foreign catalog switches its strings (the rest of the harness only ever renders English); no-language still renders English | everywhere |
| `i18n-layout.spec.mjs` | a translated locale must not break the layout — **property**-based, not pixel-pinned: under a pseudo-lengthened catalog assert nothing escapes its box, at desktop @500px and mobile @390px | everywhere |

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

# the CVD separation matrix for any bundle
node harness/cvd/report.mjs            # default palette (fails — shows the problem)
node harness/cvd/report.mjs cvd-safe   # the shipped colorblind palette (passes)
```

`harness/out/` and `harness/dist/` are build artifacts (gitignored). Baselines
under `harness/tests/__screenshots__/` are committed.

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
- **Don't sweep the harness into an `eufy_vacuum` release.** `harness/`,
  `.github/workflows/*`, `gallery/`, and the `package.json` devDeps are tooling;
  only `src/`, `custom_components/`, and `tests/` ship.
