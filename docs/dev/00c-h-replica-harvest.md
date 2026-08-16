# 00c-h — Replica harvest (WORKING LIST, unclassified)

> Generated once by `python scripts/replica_census.py --seed <this file>` and then
> **edited by hand**. The STATUS column is the whole point and no regeneration can
> recompute it — do not add this to the generated-doc gate.

This is the pile. [00c](00c-replicas.md) is the register it gets reduced into.
A suspicion listed here is not a ruling; mixing the two would make it look like one.

**Classify against one question:** *does changing one member OBLIGE changing the
others?* Yes → it earns an `RN` anchor in source and a row in 00c. No → mark
`COUSIN` and it stops costing attention. Do **not** propose helpers while
classifying; roughly half the divergence in this repo is deliberate.

`STATUS`: ` ` unclassified · `OBLIGED` · `COUSIN` · `VIOLATED` (obliged and
currently diverged — a defect with an owner, not a category) · `PHANTOM`.

**`PHANTOM` and `STALE` were added by the walk itself.** A notice can name a twin
that does not exist (`PHANTOM` — a false claim about the system, worth more attention
than a `COUSIN`, since a cousin is merely not a family), or name a REAL thing at a
path it no longer occupies (`STALE`).

> ⚠ **The first PHANTOM call was WRONG, and the mistake is the useful part.** I searched
> for the file NAME (`cvd`) across the repo, found nothing, checked git history for a
> deletion, found nothing, and concluded the gate had never existed. It exists — as
> `src/theme-tags/colorblind.mjs`, under the *mechanism's* name rather than the
> feature's. **Absence of a NAME is not absence of a THING.** Search for the mechanism
> (`Machado`, `protan`, `deutan`) before ruling something fictional; the same shape as
> a curated diagnostics view, where what is missing from the dump is present in the
> system.

**71 files** carry a replica notice and no `RN` anchor; **14** hold a STRONG one.

## Strong notices first

| STATUS | File | S/total | Notice |
|---|---|---|---|
| **OBLIGED** -> `RNWQ82XZ` | `src/bindings/room-editor.js`:405 | 4/4 | * The room editor's Save button is bound in TWO places, on two different |
| **STALE** | `custom_components/eufy_vacuum/themes/preloaded.py`:470 | 1/1 | Cites `harness/bundles/cvd-safe.mjs` + `harness/tests/cvd.spec.mjs`, neither of which exists -- but the CVD gate is REAL and lives at `src/theme-tags/colorblind.mjs` (Machado 2009 matrices) with `derive.mjs` computing `cvdMin` into `themeMetrics`. Right mechanism, wrong path. One nuance the comment still gets wrong: it reads as though a gate re-validates automatically, whereas `colorblind-safe` is a DELIBERATELY manual verified tag -- derive.mjs:175, "a crude palette metric over-claims ... a false safety claim is worse than none." So nothing auto-re-checks the palette, BY DESIGN. |
| **OBLIGED** -> `RNWQ82XZ` | `src/bindings/index.js`:323 | 1/1 | // the SHARED helper in bindings/room-editor.js — not a second copy. |
| **OBLIGED** -> `RNXX8X11` | `src/theme-tokens/map.js`:56 | 1/1 | // lands in Phase 2. Count = ROOM_FILL_N in cards/map-room-color.js — keep them in sync. |
|  | `src/bindings/map.js`:1803 | 1/7 | // than adding a second copy of the panel's guard for the next host to forget. |
|  | `custom_components/eufy_vacuum/core/manager.py`:1604 | 1/3 | # deriving either in core would be a second copy of a brand's or a flow's |
|  | `custom_components/eufy_vacuum/jobs/active_job.py`:2286 | 1/2 | # imports in turn. Reusing their conversions rather than writing a third copy |
|  | `harness/mount-entry.js`:404 | 1/2 | * rather than a second copy that could drift from it. |
|  | `custom_components/eufy_vacuum/adapters/roborock/entities.py`:68 | 1/1 | #: where the same predicate on Eufy correctly returns ``_total_cleaning_area``. |
|  | `custom_components/eufy_vacuum/mapping/map_source_runtime.py`:901 | 1/1 | # fields, and two copies is how the card had a robot position the stall capture did not. |
|  | `src/bindings/map-segments-staleness.test.mjs`:12 | 1/1 | //   — and any future one — are covered, rather than adding a second copy of the guard. |
|  | `src/state/access-graph-model.js`:29 | 1/1 | * two copies. |
|  | `src/state/coded-label.js`:10 | 1/1 | * the code, never showing a bare key, never showing blank." Two copies of that |
|  | `src/styles/fonts.js`:56 | 1/1 | * forget (live:FONT-1 was three copies of exactly that class of miss). |

## Weak notices only — likely prose, review cheaply

| STATUS | File | Notices | Notice |
|---|---|---|---|
|  | `custom_components/eufy_vacuum/learning/services.py`:262 | 1 | # leaked on every unload/reload). Mirrors the pattern services/__init__.py and |
|  | `harness/cvd/report.mjs`:81 | 1 | // panel surface). These mirror the foundation.js defaults. |
|  | `src/bindings/setup-reconciliation.test.mjs`:2 | 1 | // Scaffold mirrors theme-overwrite-confirm.test.mjs's pattern: a bare proto |
|  | `src/bindings/theme-overwrite-confirm.test.mjs`:12 | 1 | // Scaffold mirrors theme-preset-confirm.test.mjs (CARD-9(1)'s own tests): |
|  | `src/renderers/run-profiles.js`:303 | 1 | // ISSUE #48, twin of the same line in state/steps-manifest.js: fold the |
|  | `src/renderers/map.js`:530 | 4 | // mirroring the room-name label. Always the default, never the dragged position. |
|  | `src/state/steps-order.js`:9 | 4 | // sanitizeStepsForSave mirrors the backend normalize (profiles/manager.normalize_run_profile_steps) |
|  | `custom_components/eufy_vacuum/battery/manager.py`:249 | 3 | # mirroring the learning manager's trust_reason/trust_reason_text |
|  | `custom_components/eufy_vacuum/adapters/eufy/adapter.py`:789 | 2 | # a docked robot resolves its anchor to the dock (mirrors the fork's render). |
|  | `custom_components/eufy_vacuum/adapters/registry.py`:399 | 2 | # Job-segmenter engine check — mirrors the mapping check (deferred import). A |
|  | `custom_components/eufy_vacuum/learning/estimator.py`:849 | 2 | # above for the read-side twin of this guard). rooms_data is mutated |
|  | `custom_components/eufy_vacuum/learning/history_store.py`:1560 | 2 | # rung 2 (atomic) and rung 3 (live) mirror the ladder's own precedence: |
|  | `custom_components/eufy_vacuum/profiles/manager.py`:398 | 2 | # _protected_room_config expresses it — same file, same question, and the |
|  | `custom_components/eufy_vacuum/step_types.py`:9 | 2 | **There are TWO vocabularies here, and they are NOT the same question.** Collapsing them |
|  | `src/renderers/shared.js`:127 | 2 | * render its entities literally. The CALLER must escape (these do). Mirrors the |
|  | `custom_components/eufy_vacuum/adapters/brands.py`:247 | 1 | # words" is the same rule stated from the other side. The brand receives |
|  | `custom_components/eufy_vacuum/adapters/eufy/room_profiles.py`:80 | 1 | # "Quick" — by the same rule it applies to every out-of-vocabulary setting on every |
|  | `custom_components/eufy_vacuum/adapters/roborock/adapter.py`:835 | 1 | # frequencies, mirroring the Eufy adapter's upkeep_catalog. The manager |
|  | `custom_components/eufy_vacuum/adapters/roborock/roborock_upkeep_guides.py`:167 | 1 | # twin mounts) with the same remove-wash-airdry care — the true ROTATING roller mop |
|  | `custom_components/eufy_vacuum/adapters/roborock/upkeep_catalog.py`:73 | 1 | # These carry TWO flat mop cloths on twin mounts — same remove-wash-airdry care |
|  | `custom_components/eufy_vacuum/dispatch/manager.py`:514 | 1 | # (mirrors the max-wins "nothing rankable -> leave untouched" contract); a |
|  | `custom_components/eufy_vacuum/jobs/phase_runner.py`:415 | 1 | # Mirrors the pollers' `_still_ours` predicate — a job is advanceable only while it |
|  | `custom_components/eufy_vacuum/learning/job_finalizer.py`:724 | 1 | # mirrors the cleaning_time unit handling right above. |
|  | `custom_components/eufy_vacuum/learning/manager.py`:2257 | 1 | # mirrors the profile_filter_options passthrough. |
|  | `custom_components/eufy_vacuum/learning/stats_rebuilder.py`:347 | 1 | # contributes a sample — mirrors the area_sample_count pattern |
|  | `custom_components/eufy_vacuum/mapping/map_source.py`:388 | 1 | # AREA — mirror the fork's de-normalization exactly; OFFSET-INDEPENDENT of the raster. |
|  | `custom_components/eufy_vacuum/mapping/mapping_services.py`:2709 | 1 | # (mirrors the dispatch-path map_mismatch guard). Indeterminate active map -> compute. |
|  | `custom_components/eufy_vacuum/planning/run_plan.py`:1073 | 1 | # get_access_graph_health diagnostic can answer the same question this |
|  | `custom_components/eufy_vacuum/receipts/__init__.py`:99 | 1 | #: So a station MIRRORS ITS MODULE PATH, and the gate checks that — a copy-pasted receipt |
|  | `harness/fixtures/cards.js`:24 | 1 | * The option lists mirror the Eufy adapter's `vocabulary` block verbatim |
|  | `harness/fixtures/theme-library.mjs`:67 | 1 | // Mirror the export envelope's split: colours also land in colors/alpha so |
|  | `harness/tests/gallery-completeness.spec.mjs`:78 | 1 | // a gate that mirrors the mirror would drift in exactly the same way. |
|  | `harness/tests/i18n-rtl.spec.mjs`:31 | 1 | // typeless .js as CJS and rejects their ESM `export const`). Mirrors the runtime |
|  | `harness/tests/real-frame.spec.mjs`:7 | 1 | * that blind spot: a gallery case byte-identical to its plain twin, a semantic-token |
|  | `src/actions/core-refusal-shape.test.mjs`:1 | 1 | // Regression test — CARD-1 (CF-5 root, RF-14's card-side twin), the structured- |
|  | `src/actions/index.js`:52 | 1 | * Translate a UI string for an action (toast text). Mirrors the identical |
|  | `src/cards/_shared.js`:118 | 1 | * Response-capable service call (snapshot / saved-profile reads). Mirrors the |
|  | `src/cards/card-suggestions.js`:33 | 1 | * The first per-room switch's room_id for a vacuum, or null. Mirrors the filter in |
|  | `src/cards/dashboard-card.js`:879 | 1 | // Wrapped in a collapsible group (mirrors the Rooms group) so the card stays compact; |
|  | `src/clean-mode.js`:12 | 1 | // This mirrors the BACKEND owner, `canonical_clean_mode` in |
|  | `src/i18n/flatten.js`:7 | 1 | * per-subtab sections with staged fallback, mirroring the theme-token chain). |
|  | `src/i18n/index.js`:248 | 1 | * Trust model: locales may be community-contributed (mirroring the theme/animal |
|  | `src/renderers/language-control.js`:18 | 1 | * closes the menu on outside click, mirroring the card's modal pattern. |
|  | `src/renderers/metrics.js`:521 | 1 | * clean_intensity, fan_speed, water_level, passes, edge). Mirrors the backend |
|  | `src/renderers/rooms.js`:1193 | 1 | // escapeHtml'd at render below; this mirrors the room editor + standalone card, |
|  | `src/renderers/setup.js`:1046 | 1 | * Mirrors the old hardcoded two-step wizard: add_vacuum + import+save |
|  | `src/renderers/theme-preview.js`:8 | 1 | * rather than mirroring the full card on every keystroke. |
|  | `src/state/core.js`:107 | 1 | * Mirrors the dock_status / dock_status_label pair so card-side |
|  | `src/state/dialog.js`:26 | 1 | // The "cancelled / dismissed" value each kind resolves to — mirrors the |
|  | `src/state/map-compose-and-viewport.test.mjs`:26 | 1 | // Round helper mirroring the composer's 2dp corner rounding. |
|  | `src/state/map.js`:1153 | 1 | // first (mirrors the backend apply_live_pose_override) so a live anchor in a no-room |
|  | `src/state/order-engine.test.mjs`:4 | 1 | // tiny immutable adapter over {id, order} records so setOrder returns a NEW record (mirroring the |
|  | `src/state/room-editor.js`:34 | 1 | * the same rule without duplicating it. |
|  | `src/state/steps-manifest.js`:12 | 1 | // bundle styles them for the panel; the standalone card carries the same rules in |
|  | `src/state/steps-order.test.mjs`:3 | 1 | // never touch a room_group's internals (mode-agnostic). Mirrors the backend normalize for save. |
|  | `src/state/steps-queue-order.js`:63 | 1 | // (mirrors the backend get_queue_steps derivation). |
|  | `src/styles/saved-zones.js`:1 | 1 | // CSS for the Saved Zones sidebar panel (Wave 3b) — mirrors the run-profiles |

