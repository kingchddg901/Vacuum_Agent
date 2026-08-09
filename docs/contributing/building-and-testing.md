# Building and testing a change

Whatever you touched — a card view, an adapter, a locale — this page is the set of
commands that gate it, and the four ways a change can look finished when it isn't.

| You changed | Run |
|---|---|
| anything under `src/` (the card) | `npm run build:deploy`, then `npm run test:harness` |
| anything under `src/styles/` | `npm run check:styles` (also runs first in every build) |
| Python under `custom_components/eufy_vacuum/` | `scripts\test.bat tests --no-cov` (Windows) · `python -m pytest tests --no-cov` (Linux/macOS) |
| a locale JSON | `npm run check:i18n` |
| anything under `docs/` | `mkdocs build --strict` |

## `npm run build` is not the build that ships

The card under `custom_components/eufy_vacuum/frontend/` is a **build artifact**. Edit
`src/`; never hand-edit the bundle.

- `npm run build` writes to **`dist/`** — a local check, served to nobody.
- `npm run build:deploy` writes to **`custom_components/eufy_vacuum/frontend/`** — the
  bundle Home Assistant actually serves.

Both run `scripts/check-styles.mjs` and the locale-reference generator first and then
`scripts/build-card.mjs`; the only difference is the `--deploy` flag, which switches the
output directory.

**The trap:** nothing catches the wrong one for you. The render harness bundles its own
copy straight from `src/` (`harness/build.mjs`), and the Python suite never touches the
bundle at all — so after `npm run build` every gate stays green while your change is
absent from the integration you're testing against. A card change that appears to do
nothing is usually this.

The deploy build emits three bundles — the panel, the standalone cards, and the lazily
loaded map host — described in
[Card topology and bundles](../dev/frontend/card-topology-and-bundles.md).

## CSS lives inside JS template literals

Every style module in `src/styles/` exports its CSS as a **template string**. A backtick
inside that CSS — including inside a `/* comment */` — closes the literal early, and
everything after it is parsed as JavaScript.

`scripts/check-styles.mjs` catches it: it imports every style module and checks each
exported string for brace balance, so the failure names the file and says *"a stray
backtick or broken template literal"*. But it appends the underlying JS error, so what
you actually read is a parser complaint like `Unexpected identifier` pointing at a line
of ordinary-looking CSS. The fix is the backtick, not the JavaScript.

That same script is the theme lint — a hardcoded color in a rule body fails the build,
because colors have to resolve through `var(--evcc-*, fallback)`. See
[Styles system](../dev/frontend/styles-system.md).

## The Python suite needs Linux

`pytest-homeassistant-custom-component` imports `fcntl`, which does not exist on Windows,
so `python -m pytest` on a Windows host dies at import before a single test runs. The repo
ships a container runner:

```bat
scripts\test.bat tests --no-cov              REM everything — the CI gate
scripts\test.bat tests/adapters              REM one directory
scripts\test.bat --no-cov -k test_setup_flow
```

It builds the pre-baked `eufy-vacuum-test` image on first use and passes every argument
through to pytest. Rebuild the image with `scripts\build-test-image.bat` when
`requirements_test.txt` changes.

On Linux or macOS, run it directly:

```bash
pip install -r requirements_test.txt
python -m pytest tests --no-cov
```

Name `tests` explicitly either way: `tests/adapters` and `tests/replay` sit outside the
`testpaths` in `pytest.ini`, so a bare `pytest` collects neither. CI runs
`python -m pytest tests --no-cov -p no:cacheprovider --tb=short`.

Flag recipes, and the by-hand Docker invocation with its two Windows traps, are in
[Running tests](../testing/02-running-tests.md).

## Visual baselines are Linux, and a green repin can still be wrong

`npm run test:harness` builds the harness bundle and runs every frontend spec (first time:
`npm install`, then `npx playwright install chromium`). The visual-regression specs skip
unless `CI` or `VISUAL=1` is set, because their baselines are generated in one pinned
image — `mcr.microsoft.com/playwright:v1.60.0-noble` — and any other OS renders different
fonts and antialiasing.

Before regenerating a baseline, read the header comment of `harness/tests/visual.spec.mjs`.
It documents the two ways to get a repin that passes and is wrong:

1. **Dropping the build step.** Running only the Playwright half repins against whatever
   `harness/dist/mount.js` was built *last*, so the change you just made is absent: every
   test passes, zero baselines change, and the baseline now disagrees with the code while
   looking freshly pinned. If a card change produced no diffs, suspect this first.
2. **`npm ci` inside the container on a Windows host.** It rewrites the *mounted*
   `node_modules` with Linux binaries, and the host's own build then fails esbuild's
   platform check. The header gives the safer split for that case — build with the host
   toolchain, render in the image, since only the render has to be Linux.

The Docker command for regenerating, and what each spec asserts, are in
[Render harness tests](../testing/frontend/render-harness.md).
