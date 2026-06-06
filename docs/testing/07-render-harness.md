# Render Harness Tests (frontend)

A separate test track from the Python suite: JS/Playwright tests that render the
**real card** headless and gate it for crashes, visual regressions, colorblind
distinguishability, and theme-intake safety. Architecture lives in
[dev/27-render-harness](../dev/27-render-harness.md); this is how to run it.

The harness is the only place the **frontend** is tested — the ~1,900 Python
cases stop at the backend contract; these pick up at the shadow-DOM boundary.

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

`npm run test:harness` runs all of them (visual auto-skips off-CI).

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
| `.github/workflows/card-visual.yml` | push / PR touching `src/**`, `harness/**` | runs `visual` in the pinned image; uploads the diff report on failure |
| `.github/workflows/theme-intake.yml` | `workflow_dispatch`, or push/PR to `gallery/themes/*.json` | renders each theme export through the ingest gate; uploads PNG artifacts (PR/dispatch) and **publishes the gallery to GitHub Pages on push to master** — one-time: enable Pages → *GitHub Actions* source |

Both run in the pinned image, so local-Docker and CI agree byte-for-byte. They're
separate from the Python `tests.yml` job and require `package-lock.json` to be
committed (for `npm ci`).

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
