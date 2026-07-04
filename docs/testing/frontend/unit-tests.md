# Frontend Unit Tests (card logic)

Pure-JS unit tests for the card's own **computational logic** — coordinate math,
hit-testing, state accessors, validation engines, colour/theme resolution — run
with Node's built-in test runner, no browser and no build.

- **Run them all:** `npm run test:units` (`node --test "src/**/*.test.mjs"`).
- **Run one file:** `node --test src/state/rooms-logic.test.mjs`.
- **505 cases across 36 files**, currently all green. Node ≥ 21 (native glob).

This is one of three separate frontend test tracks — see [the three tracks](#the-three-tracks).

!!! note "How this set got big (2026-07-04)"
    It started as 13 files / 102 cases (mostly map/coordinate helpers). A
    frontend-logic coverage audit then found that most of `src/` is genuinely
    plumbing (renderers, event-binding, hass-orchestration — correctly not
    unit-tested), **but** a dense set of pure-derivation *engines* was untested:
    the room access-graph, the reorder engine, start-block reasons, rule
    validation, `resolvedTheme`, the learning summary/progress, map compose
    geometry, floor-scope, and a few computations that had leaked inline into
    renderers. Those were closed in three waves, taking the suite to 505 cases.

---

## The map

Grouped by `src/` area. Each file's test names carry inline `[XX-N]` ids (the
same convention as the Python suite; the `check_legend_drift.py` legend gate is
Python-only, so these `.mjs` ids are not legend-checked).

### `src/state/` — panel state accessors, coordinate math, and derivation engines

The card's state lives in `applyXState(proto)` mixins. These tests build a stub
proto (`Object.create` over the mixin'd prototype) and assert the pure
derivations — no DOM, no hass.

| File | Cases | What it guards |
|------|------:|----------------|
| `rooms-logic.test.mjs` | 28 | The **room access-graph validator** (`validateRoomAccessUpdate` + DFS cycle / self-reference / duplicate-edge / missing-ref / single-inbound rules → issue codes) and the **start-button readiness** reason-code precedence (`no_rooms_included` > `already_cleaning` > `returning_to_dock` > `vacuum_error`); `orphanedRooms`. |
| `order-engine.test.mjs` | 24 | The **reorder engine** — `_sortOrderedItems` (numeric order + id tiebreak; the `Number(null)===0` sort-to-front footgun is pinned), move-to-position clamp+splice, swap-by-id, 1-based reindex, and the scope-preview wrappers. Drives room drag-and-drop → backend number entities. |
| `room-rules-logic.test.mjs` | 28 | `ruleEntityDescriptor` (domain → category + allowed-operator set), `roomRulesDraftIsValid` (Save-enabled gate incl. the clean_passes 1\|2 rule), scored entity search tiers, operator-group filtering. |
| `theme-resolve.test.mjs` | 26 | `resolvedTheme` — the deterministic **4-layer merge** (12 room-fill palette defaults → active theme → working draft), plus `filteredThemeTokens` / `filteredPresetIds` (facet AND/OR + search filtering). |
| `map-compose-and-viewport.test.mjs` | 25 | `composeToSegments` (custom-segment draft → save payload: subtract-ordering, group/room_id resolution, rotated-rect → polygon trig), `clampMapTransform` (off-screen-recovery clamp), `applyMapZoom` (focal-point), `loadComposeDraftFromSegments` (id-counter advance). |
| `learning-derive.test.mjs` | 33 | `endLearningJob` (actual-vs-predicted summary with the `>0` guards), `_dashboardJobIsActive` (terminal-status gate for the whole live-job UI), room count / timeline / banner fallbacks, estimate keying. |
| `room-editor-matching.test.mjs` | 19 | Preset **snap-back** matcher (`_editorFieldsMatchProfile`), option-list builder (omit → hide picker), clean-mode / intensity canonicalization, carpet gate. |
| `saved-zones-group.test.mjs` | 17 | `savedZonesGrouped` (group under room, live map order, trailing "Unassigned" bucket) and `selectedSavedZoneIds`. |
| `external-jobs-group.test.mjs` | 12 | `externalWizardGroups` (v1/v2 segment grouping) + wizard split-map / default-room seeding. |
| `run-profiles-normalize.test.mjs` | 12 | `_normalizeRunProfilesPayload` (unwrap bare array / `profiles` / `saved_run_profiles` fallback; library guard). |
| `zone-draft.test.mjs` | 11 | `_rectToNormalized` zone coord conversion + multi-zone draft list. |
| `room-profiles-name.test.mjs` | 10 | `makeRoomProfileName` (slug + `custom_` prefix + `_2/_3` collision suffix) + sorted profile lists. |
| `maintenance-logic.test.mjs` | 9 | `findUpkeepItem` (case-insensitive kind+component match) and `canInvokeMaintenanceReset`. |
| `metrics-logic.test.mjs` | 9 | `findMetricsSaveCandidate` (match on profile_key AND room_slug across the selected source). |
| `room-access-logic.test.mjs` | 9 | `accessEditableRooms` (exclude self/dock, hide rooms claimed by another under the single-inbound rule). |
| `live-map-url.test.mjs` | 7 | `_liveMapImageUrl` — backdrop URL + camera cache-bust. |
| `live-pose-overlay.test.mjs` | 7 | Live-pose merge — fresh pose overrides only the moving fields; static segmentation preserved. |
| `room-hit-test.test.mjs` | 6 | `roomIdAtContentPct` — pixel-exact room hit-test (Y-flip + contain letterbox). |
| `area-label-anchor.test.mjs` | 5 | Per-room draggable m² chip anchor. |
| `map-rotation.test.mjs` | 5 | `unrotatePct` — pointer → content frame on a rotated map. |
| `mascot-dwell.test.mjs` | 5 | Dwell-debounced mascot room tracker (state machine). |
| `core-battery.test.mjs` | 5 | `batteryState` — 5-band classifier with charging override + ordered thresholds. |
| `hidden-regions.test.mjs` | 4 | Per-map user-drawn masks — accessor, draw gate, rect conversion. |
| `map-room-labels.test.mjs` | 2 | Per-vacuum map room-label visibility toggle. |

### `src/cards/` — standalone-card logic

| File | Cases | What it guards |
|------|------:|----------------|
| `dashboard-dispatch.test.mjs` | 23 | The dashboard card's pure run-launcher logic. |
| `zone-geometry.test.mjs` | 14 | The card's pure zone-clean geometry (verified vs the real X10 camera). |
| `map-room-color.test.mjs` | 9 | Map room-fill colour resolution (`roomFillTokenName` / palette / override, `normalizeHex`) — the frontend mirror of the backend `_hex_color_or_none`. |

### `src/theme-tokens/` — token-shape + floor-scoping logic

| File | Cases | What it guards |
|------|------:|----------------|
| `helpers.test.mjs` | 22 | `makeTokenLabel` (key → title-case label) + `makeGroupedToken` / `makeTypedGroupToken` (type-validated, finite-range-merge token factories). |
| `floor-scope.test.mjs` | 14 | `detectFloorScope` / `sliceThemeByTypes` / `clampThemeScalars` — targeted theme export/import (longest-name-wins scoping, out-of-range scalar clamp). |
| `animals.test.mjs` | 4 | Per-animal theme-token shape (editor lists only the tokens an animal themes). |

### `src/renderers/` — pure math extracted from render methods

These computations previously lived inline in `renderX(ctx)` methods; they were
extracted into exported pure functions (behaviour-preserving; the render methods
now delegate) so they could be unit-tested off the render path.

| File | Cases | What it guards |
|------|------:|----------------|
| `theme-parsers.test.mjs` | 28 | `_parseColorMix` / `parseScalarThemeValue` / `alphaPercentFromHex` (+ serialize/clamp) — the CSS `color-mix` + scalar + alpha-hex parsers behind the theme editor. |
| `map-geometry.test.mjs` | 20 | `_polygonCentroid` (signed-area + degenerate fallback), `_savedZoneBbox`, `_overlayTransform` (object-fit:contain letterbox). |
| `maintenance-derive.test.mjs` | 18 | `maintenanceDueInBucket(item, now, t)` (due-in projection with 3-day / 0.1-h-per-day guards; `now`/`t` injected), needs-attention verdict, remaining-percent branch. |
| `mapping-review-outlier.test.mjs` | 7 | `computeJobBoundsOutlier` — leave-one-out bounds-outlier detection (union bbox + 10% per-axis tolerance). |

### `src/bindings/` and `src/controllers/`

| File | Cases | What it guards |
|------|------:|----------------|
| `controllers/learning-controller-progress.test.mjs` | 19 | `getRoomProgressSnapshot` (per-room progress flags/percent) and `_computeProgressPercent`. |
| `bindings/room-rules-payload.test.mjs` | 9 | `_buildRulePayload` — rule draft → persisted payload (modifier/blocker action, clean_passes 1\|2 gate, fan-out filter). |

---

## How it's tested

Every file uses Node's built-in runner and assertions — no jsdom, no DOM shim:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
```

Two patterns:

- **Mixin accessors** (`src/state`, controllers) — build a stub proto and set only
  the fields the method reads:
  ```js
  import { applyRoomsState } from "./rooms.js";
  const proto = {}; applyRoomsState(proto);
  const card = Object.create(proto);
  card.getRoomsForActiveMap = () => [/* ... */];   // stub what the derivation reads
  assert.deepEqual(card.validateRoomAccessUpdate(/* ... */).issues, [/* ... */]);
  ```
- **Module functions** (`src/cards`, `src/theme-tokens`, the extracted renderer
  helpers) — import and call directly, like `src/cards/map-room-color.test.mjs`.

Anything that needs a *rendered* card (DOM, computed styles, visual output) is a
render-harness spec instead, not a unit test.

---

## CI

`npm run test:units` runs in
**[node-tests.yml](https://github.com/kingchddg901/Vacuum_Agent/blob/master/.github/workflows/node-tests.yml)**
on any `src/**` change, in the pinned Playwright image. So a `src/state/` or
`src/renderers/` refactor that breaks a derivation fails CI on push. The gate
authority is `npm run test:units` returning non-zero on any failure — mirroring
`pytest tests --no-cov` for the Python suite.

---

## The three tracks

The frontend has three separate test tracks, none of them pytest:

1. **Unit tests** (this doc) — `npm run test:units`, pure logic at the module boundary.
2. **[Render harness](render-harness.md)** — `npm run test:harness`, the *rendered*
   card headless: smoke, visual regression, CVD, shape marks, intake.
3. **i18n / sanitiser node tests** — `npm run check:i18n` (`scripts/check-i18n.mjs`,
   the translate/escape trust-model incl. the double-escape case) and
   `scripts/sanitize-locale.test.mjs` (the locale-sanitiser browser gates). Both
   run in `node-tests.yml`.
