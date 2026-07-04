# 08 — Frontend Unit Tests (card logic)

A third test track, distinct from both the Python suite and the [render
harness](07-render-harness.md): **pure-JS unit tests for the card's own
computational logic** — coordinate math, hit-testing, state accessors, colour
resolution — run with Node's built-in test runner, no browser and no build.

Where they sit in the three-track picture:

- The **~1,900 Python cases** stop at the backend contract (the data the card
  reads).
- These **frontend units** pick up the card's *pure functions and state
  accessors* — the geometry/label/pose/colour logic that has a right answer
  independent of pixels.
- The **[render harness](07-render-harness.md)** (Playwright) picks up at the
  shadow-DOM boundary — the *rendered* card, visual regressions, CVD, intake.

So a bug in `roomIdAtContentPct` or `_rectToNormalized` is caught here in
milliseconds, long before it would surface as a mis-placed click target or a
wrong zone rectangle in a screenshot diff.

Architecture reference: [frontend/state-management](../dev/frontend/state-management.md),
[frontend/module-reference](../dev/frontend/module-reference.md).

---

## TL;DR

- **Run them all:** `npm run test:units` (`node --test "src/**/*.test.mjs"`).
- **Run one file:** `node --test src/state/room-hit-test.test.mjs` (each file's
  header names its own command).
- **No build, no browser, no `npm install` beyond the repo deps** — they import
  the real `src/` modules directly and exercise pure functions against small
  stub state objects. They run anywhere Node ≥ 21 does (the glob is native).
- **102 cases across 13 files**, currently all green.

---

## The map

Grouped by `src/` area. Each file carries inline `[XX-N]` ids in its test names
(e.g. `[MRC-1]`, `[AN-3]`), the same convention as the Python suite — though the
`check_legend_drift.py` legend gate is Python-only, so these are not legend-checked.

### `src/cards/` — standalone-card logic

| File | Cases | What it covers |
|------|------:|----------------|
| `dashboard-dispatch.test.mjs` | 23 | The dashboard card's pure run-launcher logic — which run / service a dashboard action resolves to. |
| `map-room-color.test.mjs` | 9 | Map room-fill colour resolution: `roomFillTokenName` (1-based, palette-wrapping `--evcc-room-fill-N`), palette defaults, the override → palette → default precedence, and `hexToRgb` / `normalizeHex`. The frontend mirror of the backend `_hex_color_or_none` validator. |
| `zone-geometry.test.mjs` | 14 | The card's pure zone-clean geometry (lifted verbatim from `state/zone-draft` so the card's reuse is proven independently; verified against the real X10 camera, 360×301). |

### `src/state/` — panel state accessors & coordinate math

| File | Cases | What it covers |
|------|------:|----------------|
| `room-hit-test.test.mjs` | 6 | `roomIdAtContentPct` — the pixel-exact room hit-test: a content-box % point → the device room id under it, via the render raster (Y-flip + `object-fit: contain` letterbox + catch-all filtering). |
| `zone-draft.test.mjs` | 11 | `_rectToNormalized` (a pct rect → normalized image rect through the letterbox) + the multi-zone draft list. |
| `live-pose-overlay.test.mjs` | 7 | The Phase-B live-pose merge: the fork's fresh in-memory pose overrides only the *moving* overlay fields (robot / dock / current-room / heading / path) while the static segmentation is preserved. |
| `live-map-url.test.mjs` | 7 | `_liveMapImageUrl` — the live-map backdrop URL + camera cache-bust (append `last_updated` to force `<img>` refetch at frame cadence; an image entity's URL already rotates). |
| `map-rotation.test.mjs` | 5 | `unrotatePct` — maps a pointer position into the content frame inside the rotated map rotator, so a mascot drag lands and stores correctly on a rotated map. |
| `mascot-dwell.test.mjs` | 5 | The dwell-debounced mascot room tracker (Wave 3) — a pure state machine over the raw current-room name. |
| `area-label-anchor.test.mjs` | 5 | The per-room draggable m² chip anchor (optimistic overlay vs segments data, keyed by room number). |
| `hidden-regions.test.mjs` | 4 | The per-map user-drawn masks that hide map noise — accessor, draw mode, the draw gate, and the draw → store rect conversion. |
| `map-room-labels.test.mjs` | 2 | The per-vacuum map room-label visibility toggle (default on) — hides VA's own labels over a backdrop that already bakes in its own. |

### `src/theme-tokens/` — token-shape logic

| File | Cases | What it covers |
|------|------:|----------------|
| `animals.test.mjs` | 4 | The per-animal theme-token shape — the editor lists only the tokens an animal *actually* themes (derived from its live `colors` block), so a memorial like Mittens (baked-literal fur, only `--animal-eye` dynamic) doesn't surface inert palette no-ops. |

---

## How it's tested

Each file uses Node's built-in runner and assertions:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMapState } from "./map.js";
```

There is no jsdom and no DOM shim. The tests exercise **pure functions**
directly, and for accessor logic they build a tiny stub state object (the mixin
proto plus `Object.create`) so the accessor sees only the data it reads. This is
deliberate: everything here is logic with a right answer that does not need a
rendered card — anything that *does* is a render-harness spec instead.

---

## CI

`npm run test:units` runs in **[node-tests.yml](https://github.com/kingchddg901/Vacuum_Agent/blob/master/.github/workflows/node-tests.yml)**,
the same workflow that gates the theme/animal submission cores and the
`harness/lib` builders. It triggers on any `src/**` change (and on
`package.json` / the workflow file), in the pinned Playwright image. So a
`src/state/` or `src/cards/` refactor that breaks the geometry or colour logic
fails CI on push — these units are a real gate, not a manual-only convenience.

The gate authority for the frontend units is `npm run test:units` returning
non-zero on any failure, mirroring how `pytest tests --no-cov` gates the Python
suite.
