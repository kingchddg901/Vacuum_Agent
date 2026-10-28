# Frontend Unit Tests (card logic)

Pure-JS unit tests for the card's own **computational logic** — coordinate math,
hit-testing, state accessors, validation engines, colour/theme resolution — run
with Node's built-in test runner, no browser and no build.

- **Run them all:** `npm run test:units` (`node --test "src/**/*.test.mjs"`).
- **Run one file:** `node --test src/state/rooms-logic.test.mjs`.
- **1047 cases across 103 files**, currently all green. Node ≥ 21 (native glob).
  (The `node --test` summary line is the authority for these numbers — rerun
  `npm run test:units` rather than trusting this doc's total.)

This is one of three separate frontend test tracks — see [the three tracks](#the-three-tracks).

!!! note "How this set got big (2026-07-04, then the 2026-08 audit campaign)"
    It started as 13 files / 102 cases (mostly map/coordinate helpers). A
    frontend-logic coverage audit then found that most of `src/` is genuinely
    plumbing (renderers, event-binding, hass-orchestration — correctly not
    unit-tested), **but** a dense set of pure-derivation *engines* was untested:
    the room access-graph, the reorder engine, start-block reasons, rule
    validation, `resolvedTheme`, the learning summary/progress, map compose
    geometry, floor-scope, and a few computations that had leaked inline into
    renderers. Those were closed in three waves; the later floor-texture map view
    then added the compositor + material-resolver engines (`src/textures/`),
    taking the suite to 524 cases. The 2026-08 audit campaign added the next
    tier: per-defect **regression files** across `src/actions/` (service-failure
    and refusal surfacing), `src/bindings/` (confirm dialogs, rejected-import
    surfacing), `src/renderers/` (the review modal, job summary, live
    charge/zone banners), the steps editors under `src/state/`, and the
    i18n/font wiring — taking it to 904 cases across 91 files at the campaign's close.

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
| `rooms-logic.test.mjs` | 29 | The **room access-graph validator** (`validateRoomAccessUpdate` + DFS cycle / self-reference / duplicate-edge / missing-ref / single-inbound rules → issue codes) and the **start-button readiness** reason-code precedence (`no_rooms_included` > `already_cleaning` > `returning_to_dock` > `vacuum_error`); `orphanedRooms`. |
| `order-engine.test.mjs` | 24 | The **reorder engine** — `_sortOrderedItems` (numeric order + id tiebreak; the `Number(null)===0` sort-to-front footgun is pinned), move-to-position clamp+splice, swap-by-id, 1-based reindex, and the scope-preview wrappers. Drives room drag-and-drop → backend number entities. |
| `room-rules-logic.test.mjs` | 28 | `ruleEntityDescriptor` (domain → category + allowed-operator set), `roomRulesDraftIsValid` (Save-enabled gate incl. the clean_passes 1\|2 rule), scored entity search tiers, operator-group filtering. |
| `theme-resolve.test.mjs` | 27 | `resolvedTheme` — the deterministic **4-layer merge** (room-fill palette defaults **+ floor-texture material defaults seeded from `FLOOR_TEXTURE_REGISTRY`, incl. the map-rotate token; computed `-eff` layers excluded** → active theme → working draft), plus `filteredThemeTokens` / `filteredPresetIds` (facet AND/OR + search filtering). |
| `map-compose-and-viewport.test.mjs` | 25 | `composeToSegments` (custom-segment draft → save payload: subtract-ordering, group/room_id resolution, rotated-rect → polygon trig), `clampMapTransform` (off-screen-recovery clamp), `applyMapZoom` (focal-point), `loadComposeDraftFromSegments` (id-counter advance). |
| `learning-derive.test.mjs` | 37 | `endLearningJob` (actual-vs-predicted summary with the `>0` guards), `_dashboardJobIsActive` (terminal-status gate for the whole live-job UI), room count / timeline / banner fallbacks, estimate keying. |
| `room-editor-matching.test.mjs` | 22 | Preset **snap-back** matcher (`_editorFieldsMatchProfile`), option-list builder (omit → hide picker), clean-mode / intensity canonicalization, carpet gate. |
| `run-profiles-steps.test.mjs` | 20 | The run-profile **STEPS editor** draft state (charge-step / room-group authoring buffer): draft wiring, the "capture current room setup" snapshot, and editing an existing profile **clones** (never mutates) the stored steps. |
| `steps-order.test.mjs` | 20 | The pure step-mutation helpers in `steps-order.js` — immutable derive-next-array primitives the steps editor rides on; mirrors the backend normalize for save. |
| `state/resolved-entity.test.mjs` | 5 | live:ENT-10 — the card must use the entity the BACKEND resolved, not one it derives itself. `batteryLevel()` / `isCharging()` built `sensor.${objectId}_battery` and `binary_sensor.${objectId}_charging` from the vacuum's object_id, the same naming assumption ENT-1/ENT-5 fixed in Python — a fifth copy, in a language those fixes cannot reach. Issue #49: the backend resolves the battery sensor and it reads 100 while the card derives an id that does not exist. Pins the precedence, the unchanged derivation fallback, and [RE-4] pins the shipped SOURCE so a green mirror over un-rewired code cannot pass. |
| `saved-zones-group.test.mjs` | 17 | `savedZonesGrouped` (group under room, live map order, trailing "Unassigned" bucket) and `selectedSavedZoneIds`. |
| `access-graph-model.test.mjs` | 16 | `access-graph-model.js` — `normalizeRefs` (scalar / null / mixed / blanks) + the graph-model derivations. |
| `steps-manifest.test.mjs` | 15 | `renderStepsManifest` — the pure "Runs As" step→HTML helper **shared** by the run-profiles panel and the standalone profile card (per-step-type rendering, room-name lookup + fallback, single-vs-mixed clean-mode hint). |
| `room-access-logic.test.mjs` | 15 | `accessEditableRooms` (exclude self/dock, hide rooms claimed by another under the single-inbound rule). |
| `zone-draft.test.mjs` | 15 | `_rectToNormalized` zone coord conversion + multi-zone draft list, and `canDrawZone` — draw-gate lights up over the live backdrop **or** an active VA raster (Roborock cv-mode path), still gated by `supportsZoneClean`. |
| `external-jobs-group.test.mjs` | 13 | `externalWizardGroups` (v1/v2 segment grouping) + wizard split-map / default-room seeding. |
| `run-profiles-normalize.test.mjs` | 12 | `_normalizeRunProfilesPayload` (unwrap bare array / `profiles` / `saved_run_profiles` fallback; library guard). |
| `coded-label.test.mjs` | 12 | The shared code→translated-label resolver (namespace lookup with params, fallback rules). `[CL-11/12]` cover the twelve codes the BACKEND's start protection emits, none of which had a key before 2.5.3 — the resolver ran, missed, and fell through to the backend's English `message` every time, which is a fallback that is deliberate, correct and therefore silent. `[CL-11]` passes **no** `message`, because four of the twelve carry the backend's own wording on purpose (it was already good user-facing English and the key's job there is translation); without a message a fall-through returns the code, so "not the code" means the key resolved. `[CL-12]` then requires a shipped non-English pack to differ from English, since a key present only in `en.js` passes `[CL-11]`. The other half of the gate is `tests/unit/test_block_reason_keys.py`, which derives the code set by CALLING the producer. |
| `mascot-facing.test.mjs` | 10 | `mascotFacingSign` — screen-space facing from content motion under map rotation, with a sub-threshold deadband (hold last facing). |
| `room-profiles-name.test.mjs` | 10 | `makeRoomProfileName` (slug + `custom_` prefix + `_2/_3` collision suffix) + sorted profile lists. |
| `core-battery.test.mjs` | 9 | `batteryState` — 5-band classifier with charging override + ordered thresholds, incl. the absent-vs-zero guard. |
| `maintenance-logic.test.mjs` | 9 | `findUpkeepItem` (case-insensitive kind+component match) and `canInvokeMaintenanceReset`. |
| `metrics-logic.test.mjs` | 9 | `findMetricsSaveCandidate` (match on profile_key AND room_slug across the selected source). |
| `steps-queue-order.test.mjs` | 9 | The steps-queue order adapter — reordering the live ad-hoc queue (rooms + charge/wait breaks) as ONE list → room-order writes + recomputed `after_index` per break. |
| `affordance-and-warning.test.mjs` | 8 | Regression (`CENSUS-2`): `canPauseRun` / `canResumeRun` must not trust a prepended data source that doesn't carry the field. |
| `clean-mode-options.test.mjs` | 8 | Issue #48 card half: the stored DISPLAY label and the adapter TOKEN resolve to one clean-mode option. |
| `fault-label.test.mjs` | 7 | Fault-label resolution (`CARD-3`): backend sends a KEY, never text; an unrecognised fault falls back to the **raw vendor code** (honest) rather than blank. |
| `live-map-url.test.mjs` | 7 | `_liveMapImageUrl` — backdrop URL + camera cache-bust. |
| `live-pose-overlay.test.mjs` | 7 | Live-pose merge — fresh pose overrides only the moving fields; static segmentation preserved. |
| `access-issue-label.test.mjs` | 6 | Backend access-issue codes resolve to translated sentences with params; unknown codes degrade safely. |
| `live-trail.test.mjs` | 6 | The live pose trail — accumulates anchors while cleaning, de-dups stationary repeats, freezes docked then continues the SAME trace on resume (recharge case), bounded length. |
| `mascot-dwell.test.mjs` | 6 | Dwell-debounced mascot room tracker (state machine). |
| `room-hit-test.test.mjs` | 6 | `roomIdAtContentPct` — pixel-exact room hit-test (Y-flip + contain letterbox). |
| `area-label-anchor.test.mjs` | 5 | Per-room draggable m² chip anchor. |
| `map-rotation.test.mjs` | 5 | `unrotatePct` — pointer → content frame on a rotated map. |
| `review-exclude-reason.test.mjs` | 5 | The review exclude-reason resolver — preset chip passes its value, "custom" passes the user's trimmed text (falls back to the literal `custom`). |
| `hidden-regions.test.mjs` | 4 | Per-map user-drawn masks — accessor, draw gate, rect conversion. |
| `map-stale.test.mjs` | 4 | `CARD-2` clause 1: the map-stale selectors driving the dim treatment + "last seen" badge (no snapshot → not stale; fresh source → not stale). |
| `steps-order-leading-break.test.mjs` | 3 | Regression (`CARD-6` clause 1): `insertChargeStep` / `insertWaitStep` refuse a leading/trailing break (unsupported positions). |
| `map-room-labels.test.mjs` | 2 | Per-vacuum map room-label visibility toggle. |

### `src/cards/` — standalone-card logic

| File | Cases | What it guards |
|------|------:|----------------|
| `dashboard-dispatch.test.mjs` | 23 | The dashboard card's pure run-launcher logic. |
| `zone-geometry.test.mjs` | 14 | The card's pure zone-clean geometry (verified vs the real X10 camera). |
| `map-room-color.test.mjs` | 9 | Map room-fill colour resolution (`roomFillTokenName` / palette / override, `normalizeHex`) — the frontend mirror of the backend `_hex_color_or_none`. |
| `shared-slider.test.mjs` | 6 | `SLD-*` — the Dreame wetness slider's BAND WORD, which the adapter ships as three English labels and `sliderRow` printed with no lookup. It is **four sinks, not one**: the rendered word plus the three `data-word-*` attributes the drag bindings copy from, so `[SLD-2]` is what stops a fix that reads correctly until the user moves the thumb. `[SLD-3]` holds the fallback for a custom-declared range (any three words an adapter config names), `[SLD-4]` is the argument-order bite — `tVocabFn` was inserted *before* `idPrefix` to mirror `chipRow`, so a stale caller silently loses `data-scope` and every slider commits to the wrong room — and `[SLD-6]` pins that both real callers actually pass a translator, because a correct helper with zero callers passes every test about the helper. `[SLD-5]` is the ablation. |
| `shared-chips.test.mjs` | 4 | `CHIP-*` — WHICH chip renders as selected in the shared `chipRow` (issue #48: the comparison was identity, so a room storing the display label `"Vacuum and mop"` against the token option `vacuum_mop` lit no chip at all). `[CHIP-2]` is the guard against fixing that with a fold that matches everything, `[CHIP-3]` keeps the fold scoped to `clean_mode` because a brand's suction word is not core's to canonicalize, and `[CHIP-4]` pins `canonicalCleanMode` to the backend owner's alias table across the language boundary. |
| `card-suggestions.test.mjs` | 5 | Managed-vacuum detection for the card-config suggestions (companion entities carrying a `vacuum_entity_id` attribute pointing back at the vacuum). |
| `zone-repeat.test.mjs` | 5 | `canZoneRepeat` (`CARD-6` clause 2) — the zone-repeat capability gate. |

### `src/theme-tokens/` — token-shape + floor-scoping logic

| File | Cases | What it guards |
|------|------:|----------------|
| `helpers.test.mjs` | 22 | `makeTokenLabel` (key → title-case label) + `makeGroupedToken` / `makeTypedGroupToken` (type-validated, finite-range-merge token factories). |
| `floor-scope.test.mjs` | 14 | `detectFloorScope` / `sliceThemeByTypes` / `clampThemeScalars` — targeted theme export/import (longest-name-wins scoping, out-of-range scalar clamp). |
| `animals.test.mjs` | 4 | Per-animal theme-token shape (editor lists only the tokens an animal themes). |
| `registry-display-names.test.mjs` | 10 | `FTL-*` / `ANM-*` — the two FRONTEND registries whose names reached the user untranslated. Everything else in the i18n census arrives from the backend; the floor textures and animal companions are declared in the card's own code and served assets, so no `*_label` field was ever involved and the surfaces printed the registry id — the theme editor's floor select showed `carpet-high`, and the preview's animal column showed `cat` while the map picker beside it showed `Cat`. **The two completeness gates are why this file exists:** both display helpers FALL BACK to a prettified id, so a registry entry with no key renders something plausible, and only a gate can tell "English by design" from "nobody added the key". `[FTL-2]` reads the preview's curated order back out of the source, because that order is a look decision and so cannot be derived from the registry. `[FTL-5]` and `[ANM-4]` are CALL-SITE gates, and `[FTL-5]` exists because it was missing: ablating the floor select back to `${name}` left `[FTL-1..4]` green, since they test the helper and the helper was still right. `[ANM-1/2]` pin the one deliberate omission — Mittens is a memorial pet, a proper noun, so she has no key and resolves through the registry label in every language. `[ANM-5]` pins that a user-dropped animal's label cannot break out of the option it sits in, which the raw interpolation it replaced allowed. |
| `flatten.test.mjs` | 12 | `flattenThemeBuckets` / `hexWithAlpha` / `alphaApplies` — the ONE rule for turning `{tokens, colors, alpha}` into a CSS-ready map. Guards the compose-not-concatenate invariant (a key in both `colors` and `alpha` must bake to 8-char hex, never resolve to the bare alpha number) and the `composed` / `unappliedAlpha` accounting that keeps a clean report honest. Eight of the twelve go red against the concatenation this replaced. |

### `src/textures/` — floor-material render math

Pure math + config resolution behind the map's floor-texture view (mask ×
colour × opacity compositing and the room→material mapping). No canvas, no DOM.

| File | Cases | What it guards |
|------|------:|----------------|
| `floor-texture-compositor.test.mjs` | 7 | `compositeFloorTexture(w, h, baseColor, layers)` — the mask×colour×opacity blend the floor view samples: white mask reveals the layer colour over the opaque base, opacity scales the reveal, mid-grey blends halfway, layers stack bottom→top, and degenerate inputs (short luma / opacity ≤ 0 / missing) are skipped safely. Output stays fully opaque (a floor is a solid surface). |
| `floor-texture-resolver.test.mjs` | 10 | `resolveFloorType(room)` (spec `{floor_type, carpet_type}` → `carpet_low`/`carpet_high`; legacy combined forms; `hardwood`/`laminate`→`wood`, `granite`→`granite_light` aliases; direct registry keys; case/whitespace-insensitive; unknown→`default`) and `normalizeFloorRotationDeg(deg)` (non-finite→0, quantise to 0.1° so getComputedStyle noise can't churn the cache, wrap to `[-180, 180)`). |

### `src/renderers/` — pure math extracted from render methods

These computations previously lived inline in `renderX(ctx)` methods; they were
extracted into exported pure functions (behaviour-preserving; the render methods
now delegate) so they could be unit-tested off the render path.

| File | Cases | What it guards |
|------|------:|----------------|
| `theme-parsers.test.mjs` | 28 | `_parseColorMix` / `parseScalarThemeValue` / `alphaPercentFromHex` (+ serialize/clamp) — the CSS `color-mix` + scalar + alpha-hex parsers behind the theme editor. |
| `map-geometry.test.mjs` | 20 | `_polygonCentroid` (signed-area + degenerate fallback), `_savedZoneBbox`, `_overlayTransform` (object-fit:contain letterbox). |
| `maintenance-derive.test.mjs` | 40 | `maintenanceDueInBucket(item, now, t)` (due-in projection with 3-day / 0.1-h-per-day guards; `now`/`t` injected), needs-attention verdict, remaining-percent branch. Plus `[FREQ-1..6]` on `_formatMaintenanceFrequency` (added 2026-08-07, when it was found to be dead code its one call site could never reach): sentence case not title case (`Раз в неделю` and `Einmal pro Woche` must survive unchanged), hyphens preserved while underscores collapse (`every 3-6 months` is a real bundled value the old `[_-]+` class would have mangled), Turkish dotless i (`İki`, not `Iki`), and `[FREQ-5]` — a language value that is TRUTHY but stringifies to `""` must not throw, which is the shape that made `String(x \|\| "en")` crash the whole view via `toLocaleUpperCase("")`. These drive the REAL function through `applyMaintenanceRenderers`, not a transcription of it. Also `[LG-*]`/`[LGK-*]` on `_localizedGuide` (prose and key routing, the latter against the REAL served key packs) and **`[MIN-*]` on `_maintenanceItemName`** — a translated component key beats the backend label, a MISSING one falls through rather than leaking a bare i18n key into the modal title, and `[MIN-5]` pins the ORDER of the two key families. That order is the one property the real catalogue cannot test: five components have a sensible entry in both, so a real-pack assertion passes whichever answers. `vocab.maintenance_component.*` must lead, because it is the family the two modal titles already resolve through and it is brand-scoped. |
| `job-summary.test.mjs` | 15 | The **Job Summary modal** — the surface that closes the gap between the job JSON and what the user is told about a run. |
| `review-error-badge.test.mjs` | 14 | The review list's captured-run-errors (`run_errors`) badge — surfacing the backend's harvested error rows. |
| `setup-reconciliation.test.mjs` | 12 | `CARD-7`/RP-019 — the reconciliation review banner (`renderReconciliationPanel`, driven through the whole `renderSetupView()` since it's a closure, not a proto method). |
| `progress-and-format.test.mjs` | 6 | Regression (`FE-LRN-1` +1): two renderers that showed a plainly wrong thing — the live-progress list's completed/current dispatch fall-through. |
| `maintenance-census6.test.mjs` | 6 | `CENSUS-6` — server-baked English reached the user in all 18 locales; the maintenance renderer must translate, not pass through. |
| `language-control-font.test.mjs` | 5 | The typeface picker inside the language control (P3 of the OpenDyslexic accessibility feature). |
| `review-matcher-clean-mode.test.mjs` | 5 | `CC-5` — the review profile-matcher's clean-mode chip row comparison. |
| `review-absent-battery.test.mjs` | 4 | `REV-6` — an externally-captured run with **absent** battery must not render "Battery 0". |
| `review-truncation-note.test.mjs` | 4 | `REV-5` — the run list is cut to `limit` (50) while the headline stat counts all runs; the truncation must be said. |
| `theme-preview-room-card-state.test.mjs` | 7 | `TPS-*` — **the theme preview renders REAL room cards with NO state**, and `renderRoomCard` must tolerate that. `[TPS-1..3]` inject the three distinct shapes of absence (`null` — the grid default at 8 of 9 call sites; `{}` — present but no such method; the real `_themePreviewState()`), because a test for one does not carry the others. `[TPS-4/5]` keep the predicate load-bearing in both directions, after the first draft asserted the lowercase token and so "passed" against a chip that was there — the chips render title-cased. `[TPS-6]` is the replica gate `RNJE1GDZ`: it diffs the `state` accessors `renderRoomCard` reads against the set `_themePreviewState` declares, and fails on drift. That drift took the whole Theme view down for 2.4.0 — `d32aa092` added a seventh accessor to the reader and not to the stub, and wrote the reads bare where every sibling read is `state?.x?.()`. All 7 ablated; the comment-stripping in `[TPS-6]` is itself ablated, because the gate first matched `state?.x?.()` out of a comment documenting the convention it enforces. |
| `stored-setting-vocab.test.mjs` | 16 | `SSV-*` — the panel sinks that printed a room or dock SETTING as the backend's English, in two shapes. **Precedence:** Station Water, the room-estimate rows and the planned-water tooltip each already had a correct `tVocabRaw` arm and tested the backend's `*_label` first, so the localizing arm was only reachable when the label was absent — which the backend never does. **Missing call:** the map selection bar's per-room summary, the rule editor's setting chips and the native zone-setting selects had no lookup at all. Renders the real renderers against a real shipped pack and reads every expected word *out of* that pack, so a retranslation does not turn it red. `[SSV-4]` is the second half of the Station Water bug — the status bucket was matched against the string about to be displayed, so translating the display would have broken the bucket. `[SSV-7]` keeps Dreame's numeric fine-wetness (`"16"`) passing through untouched, `[SSV-9]` keeps an axis core has never seen on the adapter's own words, and `[SSV-12]` covers a double-escape measured live in `fr`/`he`. `[SSV-13..15]` extend it to the enum tank cards and to the maintenance item NAME, which resolved through a different key family than the modal title for the same item on the same screen. `[SSV-16]` is the one test here that SUPPLIES its own input rather than reading one: the item-name helper's escaped-twin bug is latent only because the ten Latin packs still hold raw English for most of `component_label`, so it registers a locale carrying French's "Réservoir d'eau propre" instead of waiting for the first translation. All twelve fixes ablated. |
| `maintenance-water-card.test.mjs` | 7 | `WTR-*` / `TNK-*` — a device with NO water-level sensor rendered a confident "Empty · ~0 ml remaining", from JS coercion rather than missing data (`Number(null)` is 0, so `Number.isFinite` was true for a null reading → status `replace_now`). `[WTR-1/1b]` are that input; `[WTR-3]` is the same coercion on tank capacity. The file deliberately **echoes i18n keys** so it asserts the BRANCH rather than any wording — which means every `vocab.*` lookup misses by construction, so `[TNK-1]` pins the FALLBACK leg: the tank-state set is the *device's*, so a state we have never keyed must still reach the user as its own label. The keyed leg needs a catalogue and lives in `stored-setting-vocab.test.mjs` `[SSV-13]`. |
| `rule-editor-vocab.test.mjs` | 8 | `RUL-*` — the rule editor's 22 CARD-LOCAL words. Every other i18n-census sink had a backend `*_label` beside it, which is what made it findable; these had nothing. `ruleOperatorGroups` and `ruleEntityDescriptor` composed their own English in the STATE layer (`{label: "State"}`, `{label: "Is ON"}`, `category: "boolean"`) and the renderer printed it — no field to notice, no vocabulary to miss, no key to be absent from. The fix follows `state/rooms.js`'s block reasons: the state returns a CODE, the renderer localizes, the state's English rides along as `resolveCodedLabel`'s message so an operator added without a key reads rather than showing a dotted key (`[RUL-4]`). `[RUL-5]` and `[RUL-8]` read the state layer's **whole** tables from source instead of walking one entity's chips, because `ruleOperatorGroups` filters by what the descriptor allows — a `binary_sensor` never offers the numeric group, so an earlier version could not see `code: "numeric"` being deleted at all. `[RUL-6]` is why the four comparison operators are keyed rather than left hardcoded: a bare `>` is ambiguous in a right-to-left layout, so `ar`/`he` carry words while the fifteen LTR packs keep the symbol. |
| `profile-name-vocab.test.mjs` | 13 | `PRF-*` / `EST-*` / `CHG-*` — the saved-profile NAMES, and two derived codes printed bare. **A zero-caller story:** `_builtInProfileI18nKey` maps the seven saved-profile keys onto the seven translated `rooms.profile_*` values and `_roomProfileLabel` wraps it, but the map was reached from one place (the room editor's chip loop) and the wrapper from **nowhere** — while three surfaces printed the backend's English profile names beside it. Same shape as the `device_id` filter behind [#77](https://github.com/kingchddg901/Vacuum_Agent/issues/77), in a different subsystem. `[PRF-1]` and `[PRF-2]` are the two directions of the precedence decision, and it is *not* "localized first, always": a built-in's backend label is English so the key must beat it, while a user-saved profile's label is the name somebody typed so it must beat a prettified slug. `[PRF-8]` covers the fallback arm of `_localizedProfile`, which is **every multi-room job** — the backend attaches flat setting codes only for a single-room job with an archived room. `[PRF-6b]`, `[CHG-2]` and `[PRF-9]` are call-site gates, two of them added because the ablation refused to go red without them; `[PRF-6b]`'s first draft anchored on the field name and landed on the comment above the call. |
| `base-station-stat-vocab.test.mjs` | 6 | `BSV-*` — the two Station Status rows `CENSUS-6` stopped short of. It fixed the "Dock status" row to resolve the CODE and left "Lifecycle" and "Task" immediately below it reading `label ?? code`, so both were English in all 17 locales while the row above them was translated — the shoulder just after a guard's window closed. Renders the real card through the real `translate()` over a shipped pack rather than transcribing the resolution, which is the `RNNPSKT7` shape its `maintenance-census6` sibling fell into. `[BSV-5]` records why one fix missed two rows: the three adjacent rows resolve through three *different* fields from three different producers. `[BSV-2]` is the ablation; `[BSV-6]` pins the raw/escaped twin choice to the sink. |
| `rooms.test.mjs` | 4 | `confidenceTooltip` (`CARD-2` clause 3) — finite sample counts fold into the tooltip; a count of 0 still renders; numeric strings coerce. |
| `i18n-escaping-contract.test.mjs` | 4 | `live:I18N-1` — the `tRaw` escaping contract in `renderers/shared.js` (what escapes, what must not double-escape). |
| `learning-charge-status.test.mjs` | 3 | The live charge banner gates ONLY on `liveChargeStatus()` — a `charge_wait` phase has an empty room timeline, so the old queue-gated placement never rendered it. |
| `learning-zone-status.test.mjs` | 3 | The live zone banner — same shape as the charge banner: gated on `liveZoneStatus()`, never on the room queue. |
| `run-profiles-unsupported-position.test.mjs` | 3 | `CARD-6` clause 1 display half — an EXISTING saved profile with a leading/trailing break renders the unsupported-position notice. |
| `maintenance-clock-modal-host-css.test.mjs` | 3 | `MHC-*` — every `evcc-*` class the counter picker emits is DEFINED in `MODAL_HOST_STYLES`, the body-portal cascade that actually renders it (the shadow cascade interpolates that export, so the flow is one-way). Caught `.evcc-clock-candidate-main`, emitted with no rule in either cascade, on its first run. |
| `maintenance-clock-candidate-value.test.mjs` | 3 | `MCV-*` — a candidate's reading is rounded to one decimal. The same picker read "414 min" on a Dreame and "206.618888888889 h" on a Roborock; non-numeric states pass through untouched. |
| `room-estimate-allocated.test.mjs` | 2 | `CARD-2` clause 2 — the room-estimate modal's ALLOCATED-source labeling (not just `default`). |
| `metrics-edge-mopping-capability.test.mjs` | 2 | `CARD-8` — the "Edge Mopping" subtitle chip must be capability-gated, not shown whenever `edge_mopping` is truthy. |

### `src/actions/` — service-call wrappers (failure/refusal surfacing)

The audit campaign's `CARD-1` family: a failed or refused service call must
reach the **user**, not just the console. `callService` passes
`notifyOnError: false` (suppressing HA's own error toast), so these wrappers
are responsible for telling the user — and the two shapes (a **throwing** call
vs a normal response carrying `{success: false, reason}`, the operational-
refusal contract) are pinned separately.

**Every fake at the `hass` seam must return the ENVELOPE.** `hass.callService(...,
returnResponse)` resolves to `{context, response}`, never the bare payload. Until
2026-09-13 all four fixtures below returned it bare — a fixture agreeing with the CALLER,
not the callee — so `callService`'s refusal check, which read `result.success` off the
ENVELOPE and could therefore never fire, sat under six green cases for months. Wrap fakes
with `envelope()` from `_test-host.mjs`. Ablating the unwrap in `core.js` now turns **8**
of these cases red while every no-toast control stays green.

| File | Cases | What it guards |
|------|------:|----------------|
| `rooms-clear-applied.test.mjs` | 8 | Defect #8 — post-apply room mutations (`updateRoomFields`, `persistRoomOrdering`) drop the pending applied stepped run profile so Start runs the just-edited FLAT selection, not the saved step sequence. |
| `core-envelope-shape.test.mjs` | 7 | `CES-*` — the `{context, response}` ENVELOPE contract: `callService` returns the UNWRAPPED payload; a null `response` falls back to the envelope (**not** `null`, which would report a save that took as a failure); **REPLICA `RNGP3ZBE` parity** with `cards/_shared.js::callResponse`; the second funnel (`_callThemeService`) revives; and the predicate stays NARROW — `{ok:false}`/`{updated:false}`/`{status:"error"}` remain their own funnels' business, or one refusal toasts twice. |
| `core-refusal-shape.test.mjs` | 6 | `CRS-*` — the generic `callService` wrapper toasts a non-throwing `{success: false, reason}` response. Fixture returns the real envelope. |
| `core-service-failure.test.mjs` | 6 | A **throwing** service call surfaces as a toast (was: console.error + resolve `null`). |
| `rooms-cancel-through-seam.test.mjs` | 6 | The card-cancel bypass — Cancel must call the integration's `cancel_active_job`, never stock `vacuum.return_to_base` (which left the tracker believing the job was live). |
| `fetch-failure-tristate.test.mjs` | 5 | A FAILED fetch is not rendered as a confident empty result — "never loaded" / "failed" / "genuinely empty" stay distinct. |
| `theme-refusal-toast.test.mjs` | 5 | `CARD-9` — `_callThemeService`, the single funnel of all ~11 theme actions, toasts the theme services' own refusal shape. |
| `map-zone-clean-refusal-toast.test.mjs` | 4 | `MZ-2` — the zone-clean call site routes through the refusal-toasting wrapper (e.g. `job_in_progress`). |
| `rooms-start-refusal-toast.test.mjs` | 4 | `FE-ERR-1` — `startCleaning` itself routes through the refusal-surfacing wrapper. |
| `review-snapshot-origin.test.mjs` | 3 | `getLearningHistorySnapshot` forwards EVERY filter param (the `origin` chip was a silent no-op — destructured away). |
| `rooms-retry-missed-map-scope.test.mjs` | 3 | `CARD-5` — `retryMissedRooms` refuses (`map_mismatch`) when the incomplete-run log's map disagrees with the active map. |

### `src/i18n/` and `src/styles/`

| File | Cases | What it guards |
|------|------:|----------------|
| `i18n/rtl.test.mjs` | 10 | `isRTL` (ar/he/fa/ur/iw/ps) + `applyDir` + the bidi-isolate (`FSI`/`PDI`) behavior of `translate` — the logic half of the RTL gates. |
| `i18n/font-store.test.mjs` | 8 | `FS-*` — the per-user typeface store: the coverage gate reads `FONT_SUPPORT` (never a hardcoded `"en"`), region tags resolve to their base, unverified locales are refused even when Latin-script, scalar clamps. |
| `i18n/card4-untranslated-strings.test.mjs` | 1 | `CARD-4` — the three base-catalog strings that were missing from every shipped locale pack stay present everywhere. |
| `i18n/locale-key-coverage.test.mjs` | 2 | `LOCCOV-*` — the GENERALISATION of `CARD-4`: **every** English key is translated in all 17 packs, not three named ones. `check:i18n`'s default mode reports the fallback count and passes, and nothing in CI runs `--strict-coverage`, so a key added to `en.js` and translated nowhere reached users with nothing red. `LOCCOV-2` is an **ablation**: it runs the same check against two injected defects — a new English key in no pack (must add one pair per pack) and an existing key pruned from one pack (must add exactly that pair) — so `LOCCOV-1` passing means something. Both deltas are measured against the tree's own baseline, so the ablation still holds mid-wave. |
| `styles/typeface-wiring.test.mjs` | 6 | `live:FONT-1` — the `--evcc-font-family` token is SET by a rule the shadow tree reads and READ where it resolves (the token was set by a rule nothing read, for two days). |

### `src/bindings/` and `src/controllers/`

| File | Cases | What it guards |
|------|------:|----------------|
| `controllers/learning-controller-progress.test.mjs` | 19 | `getRoomProgressSnapshot` (per-room progress flags/percent) and `_computeProgressPercent`. |
| `bindings/room-rules-save-reaches-service.test.mjs` | 6 | `RRS-*` — **reachability**: the rule save/delete bindings actually reach `saveRoomRules`, which did not exist (call-only since `eae291fa`), so both sites evaluated to `undefined` and the drawer closed with no error while the rule vanished. Also pins that an EMPTY list is sent (deleting the last rule is a clear, not a no-op) and that a refusal keeps the drawer open. `room-rules-payload.test.mjs` could not catch this — it proves the payload is built, never that it reaches a sink. |
| `bindings/maintenance-clock-response-unwrap.test.mjs` | 6 | `MCU-*` — the maintenance-COUNTER picker's two service calls unwrap `.response`. The picker rendered "no suitable counter found" over a list of six because it read `result.candidates` off the envelope; the save path additionally treats `{status:"error"}` as a refusal rather than a save that took. |
| `bindings/room-rules-payload.test.mjs` | 9 | `_buildRulePayload` — rule draft → persisted payload (modifier/blocker action, clean_passes 1\|2 gate, fan-out filter). |
| `bindings/setup-reconciliation.test.mjs` | 9 | `CARD-7`/RP-019 — the reconcile-room Update/Dismiss bindings (bare-proto mixin + recorded `_onAll` handlers). |
| `bindings/theme-import-rejected.test.mjs` | 8 | `CARD-9(3)` — rejected-keys surfacing at BOTH theme-import entry points. |
| `bindings/theme-overwrite-confirm.test.mjs` | 7 | `CARD-9(2)` — the Save button's overwrite-confirm dialog (no silent overwrite). |
| `bindings/map-segments-staleness.test.mjs` | 5 | The map-segments slice follows the ACTIVE MAP — not fetched once for the life of the element. |
| `bindings/room-editor-save-rejection.test.mjs` | 4 | `_roomEditorSaveWasRejected` — a rejected room-editor save is detected and surfaced. |
| `bindings/rooms-queue-missed-map-scope.test.mjs` | 4 | `CARD-5` binding side — the missed-rooms retry binding passes the recorded map id into the map-scoped action. |
| `bindings/theme-preset-confirm.test.mjs` | 3 | `CARD-9` — preset-chip clicks confirm before discarding a dirty working draft, and re-clicking the already-active theme is a no-op. |

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
3. **i18n / sanitiser / build-script node tests** — `npm run check:i18n`
   (`scripts/check-i18n.mjs`, the translate/escape trust-model incl. the
   double-escape case), `scripts/sanitize-locale.test.mjs` (the locale-sanitiser
   browser gates) and `scripts/hash-dir.test.mjs` (the cache-bust token: HD-1 line
   endings must not move it, HD-2/HD-6 a binary file's `0D 0A` must not be folded —
   every shipped texture PNG contains that byte pair). All run in `node-tests.yml`.
