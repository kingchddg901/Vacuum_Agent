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

> **CENSUS COMPLETE 2026-08-18 — all 71 rows classified.** 34 `OBLIGED`, 32 `COUSIN`,
> plus the 5 pre-existing rulings. The pile is reduced; what remains is minting `RN`
> anchors for the 34, which is a separate pass.
>
> **The ratio is the headline: roughly half.** `00c` predicted it ("roughly half the
> divergence in this repo is deliberate") and the census landed at 32/66 cousins. A
> detector tuned to flag duplication would have been wrong about half of these.
>
> **Where the obligations actually live: 23 of the 34 are in `src/` or `harness/`** —
> card-mirrors-backend, or fixture-mirrors-production. That is the class no structural
> similarity pass can see, because the two halves are in different languages. The three
> sets found by machine that day (`RNJ9YQF7`, `RNRVXK51`, and `_display_label`'s third
> copy) were all Python-to-Python. **The two methods barely overlap**, and neither is
> optional.
>
> **A `COUSIN` here is usually not a near-miss — it is the opposite.** The commonest
> shape by far is a *refusal to replicate*: a comment that exists precisely to say "we
> did NOT copy this, and here is why". Reading only the quoted fragment inverts its
> meaning, which is what the header below warns about.
>
> **Line numbers in this table have drifted** — `profiles/manager.py:398` is now `:426`,
> and two rows resolved only by searching the notice text. The notices are intact; the
> coordinates are not. Same rot as the audit corpus's `file:line`, and the same argument
> for anchors.

**71 files** carry a replica notice and no `RN` anchor; **14** hold a STRONG one.

## Strong notices first

| STATUS | File | S/total | Notice |
|---|---|---|---|
| **OBLIGED** -> `RNWQ82XZ` | `src/bindings/room-editor.js`:405 | 4/4 | * The room editor's Save button is bound in TWO places, on two different |
| **STALE** | `custom_components/eufy_vacuum/themes/preloaded.py`:470 | 1/1 | Cites `harness/bundles/cvd-safe.mjs` + `harness/tests/cvd.spec.mjs`, neither of which exists -- but the CVD gate is REAL and lives at `src/theme-tags/colorblind.mjs` (Machado 2009 matrices) with `derive.mjs` computing `cvdMin` into `themeMetrics`. Right mechanism, wrong path. One nuance the comment still gets wrong: it reads as though a gate re-validates automatically, whereas `colorblind-safe` is a DELIBERATELY manual verified tag -- derive.mjs:175, "a crude palette metric over-claims ... a false safety claim is worse than none." So nothing auto-re-checks the palette, BY DESIGN. |
| **OBLIGED** -> `RNWQ82XZ` | `src/bindings/index.js`:323 | 1/1 | // the SHARED helper in bindings/room-editor.js — not a second copy. |
| **OBLIGED** -> `RNXX8X11` | `src/theme-tokens/map.js`:56 | 1/1 | // lands in Phase 2. Count = ROOM_FILL_N in cards/map-room-color.js — keep them in sync. |
| **COUSIN** | `src/bindings/map.js`:1803 | 1/7 | NOT a family -- the opposite. The staleness guard was deliberately placed in the ONE fetch helper both hosts already call, explicitly so a second copy would not exist ("rather than adding a second copy of the panel's guard for the next host to forget"). A refusal to replicate reads like a replica notice when quoted in fragment. Read the WHOLE block. |
| **COUSIN** | `custom_components/eufy_vacuum/core/manager.py`:1604 | 1/3 | # deriving either in core would be a second copy of a brand's or a flow's — **Refusal: core deliberately does NOT derive a brand's or a flow's value -- 'would be a second copy'. An anti-replica notice.** |
| **COUSIN** | `custom_components/eufy_vacuum/jobs/active_job.py`:2286 | 1/2 | # imports in turn. Reusing their conversions rather than writing a third copy — **Refusal: 'Reusing their conversions rather than writing a third copy'.** |
| **COUSIN** | `harness/mount-entry.js`:404 | 1/2 | * rather than a second copy that could drift from it. — **Refusal: the gallery fixture is reused 'rather than a second copy that could drift'.** |
| **COUSIN** | `custom_components/eufy_vacuum/adapters/roborock/entities.py`:68 | 1/1 | #: where the same predicate on Eufy correctly returns ``_total_cleaning_area``. — **Each adapter DERIVES its own ALL_SUFFIXES from its own SUFFIX_* constants. Parallel structure, not shared content -- a suffix added here obliges nothing in the Eufy adapter. The reserved_suffixes CONTRACT is an adapter-config relation (IN), not a replica.** |
| **COUSIN** | `custom_components/eufy_vacuum/mapping/map_source_runtime.py`:901 | 1/1 | # fields, and two copies is how the card had a robot position the stall capture did not. — **Refusal: uses the shared extractor -- 'two copies is how the card had a robot position the stall capture did not'.** |
| **COUSIN** | `src/bindings/map-segments-staleness.test.mjs`:12 | 1/1 | //   — and any future one — are covered, rather than adding a second copy of the guard. — **Refusal: fix lives in the shared fetch helper so both hosts are covered.** |
| **COUSIN** | `src/state/access-graph-model.js`:29 | 1/1 | * two copies. — **Refusal: shared pure functions -- 'a bug in one function rather than drift between two copies'.** |
| **COUSIN** | `src/state/coded-label.js`:10 | 1/1 | * the code, never showing a bare key, never showing blank." Two copies of that — **Refusal: 'it lives here once and the callers supply only their namespace'.** |
| **OBLIGED** | `src/styles/fonts.js`:56 | 1/1 | * forget (live:FONT-1 was three copies of exactly that class of miss). — **Adding a font requires an entry HERE and in i18n/font-store.js FONT_SUPPORT, ids matching. Already pinned by TF-11 -- note a TEST does not discharge the obligation, it DETECTS breach, which is exactly the ratchet 00c wants.** |

## Weak notices only — likely prose, review cheaply

| STATUS | File | Notices | Notice |
|---|---|---|---|
| **COUSIN** | `custom_components/eufy_vacuum/learning/services.py`:262 | 1 | # leaked on every unload/reload). Mirrors the pattern services/__init__.py and — **Mirrors the unregister PATTERN services/__init__.py uses. Bound by INT79PB7, which obliges each registration site INDEPENDENTLY -- an IN relation.** |
| **OBLIGED** | `harness/cvd/report.mjs`:81 | 1 | // panel surface). These mirror the foundation.js defaults. — **A hand-copied semantic palette that 'mirrors the foundation.js defaults'. If foundation.js changes, the CVD contrast report validates colours the product no longer ships -- a green report about the wrong palette.** |
| **COUSIN** | `src/bindings/setup-reconciliation.test.mjs`:2 | 1 | // Scaffold mirrors theme-overwrite-confirm.test.mjs's pattern: a bare proto — **Test scaffold mirrors another test's PATTERN. Changing one scaffold obliges nothing.** |
| **COUSIN** | `src/bindings/theme-overwrite-confirm.test.mjs`:12 | 1 | // Scaffold mirrors theme-preset-confirm.test.mjs (CARD-9(1)'s own tests): — **Same: scaffold pattern shared with theme-preset-confirm.test.mjs.** |
| **OBLIGED** | `src/renderers/run-profiles.js`:303 | 1 | // ISSUE #48, twin of the same line in state/steps-manifest.js: fold the — **Explicitly named: 'ISSUE #48, twin of the same line in state/steps-manifest.js'. Fold spellings before the Set or a mixed group's chip vanishes.** |
| **OBLIGED** | `src/renderers/map.js`:530 | 4 | // mirroring the room-name label. Always the default, never the dragged position. — **Three label families share one drag-anchor convention -- area label 'mirroring the room-name label', and saved-zone labels at :540 'mirrors the boxes above'. data-cx/cy is ALWAYS the auto placement, never the dragged position; one label type diverging breaks snap-back for that type only.** |
| **OBLIGED** | `src/state/steps-order.js`:9 | 4 | // sanitizeStepsForSave mirrors the backend normalize (profiles/manager.normalize_run_profile_steps) — **CROSS-LANGUAGE: sanitizeStepsForSave mirrors profiles/manager.normalize_run_profile_steps. Backend normalize changes and the card ships data the service then re-normalizes differently.** |
| **COUSIN** | `custom_components/eufy_vacuum/battery/manager.py`:249 | 3 | # mirroring the learning manager's trust_reason/trust_reason_text — **Mirrors the learning manager's trust_reason/trust_reason_text CONVENTION. Changing one subsystem's reason codes obliges nothing in the other.** |
| **COUSIN** | `custom_components/eufy_vacuum/adapters/eufy/adapter.py`:789 | 2 | # a docked robot resolves its anchor to the dock (mirrors the fork's render). — **Mirrors the FORK's render behaviour -- an external project we cannot oblige and which cannot oblige us.** |
| **OBLIGED** | `custom_components/eufy_vacuum/adapters/registry.py`:399 | 2 | # Job-segmenter engine check — mirrors the mapping check (deferred import). A — **The engine-block validation is written once per engine family (mapping / job_segmenter / room_attribution). A change to the validation contract obliges all copies; a new engine family adds one.** |
| **COUSIN** | `custom_components/eufy_vacuum/learning/estimator.py`:849 | 2 | # above for the read-side twin of this guard). rooms_data is mutated — **Cites the RP-006/ACC-1 destructive-RMW rule -- that is an INVARIANT relation (IN2QDNB3), obliging each site independently, not a replica.** |
| **COUSIN** | `custom_components/eufy_vacuum/learning/history_store.py`:1560 | 2 | # rung 2 (atomic) and rung 3 (live) mirror the ladder's own precedence: — **Refusal: the queue block is DERIVED alongside resolved_rooms 'rather than as a second hand-written walk, per the centralize-the-QUESTION rule'.** |
| **OBLIGED** | `custom_components/eufy_vacuum/profiles/manager.py`:398 | 2 | # _protected_room_config expresses it — same file, same question, and the — **Line drifted to :426. 'ISSUE #48: the LAST private copy of the predicate. Expressed exactly as _protected_room_config expresses it -- same file, same question, read off the same `protected` dict a few lines apart, so a disagreement between them is the original #48 shape in miniature.' Names itself as the last copy.** |
| **OBLIGED** | `custom_components/eufy_vacuum/step_types.py`:9 | 2 | **There are TWO vocabularies here, and they are NOT the same question.** Collapsing them — **CROSS-LANGUAGE: profiles.manager._enrich_saved_run_profile's has_stops gate (backend) and _deriveHasStops (card) -- 'a rooms->zone profile reported itself as a flat queue in BOTH'. Note the block ALSO warns the two vocabularies inside step_types must NOT be collapsed; the set is the backend/card pair, not the two vocabularies.** |
| **OBLIGED** | `src/renderers/shared.js`:127 | 2 | * render its entities literally. The CALLER must escape (these do). Mirrors the — **tVocab/tVocabRaw mirror the t/tRaw escaped-vs-raw pairing. A change to the escaping contract on one pair obliges the other, or a translated "l'eau" double-escapes.** |
| **COUSIN** | `custom_components/eufy_vacuum/adapters/brands.py`:247 | 1 | # words" is the same rule stated from the other side. The brand receives — **'core owns the KEYS, never a brand's words is the same rule stated from the other side' -- one INVARIANT (ISO-1 / IN40W49E) expressed from two directions, not two implementations.** |
| **COUSIN** | `custom_components/eufy_vacuum/adapters/eufy/room_profiles.py`:80 | 1 | # "Quick" — by the same rule it applies to every out-of-vocabulary setting on every — **States a RULE applied uniformly (declaring real options IS the declaration of what is retired) -- an invariant relation, not a copy.** |
| **COUSIN** | `custom_components/eufy_vacuum/adapters/roborock/adapter.py`:835 | 1 | # frequencies, mirroring the Eufy adapter's upkeep_catalog. The manager — **Each adapter declares its OWN upkeep_catalog. Same schema, different content -- the shape is an adapter-config contract (IN), not a replica.** |
| **COUSIN** | `custom_components/eufy_vacuum/adapters/roborock/roborock_upkeep_guides.py`:167 | 1 | # twin mounts) with the same remove-wash-airdry care — the true ROTATING roller mop — **Refusal: 'the base-9 dicts are SHARED, not duplicated' -- composition is shallow and callers deep-copy.** |
| **OBLIGED** | `custom_components/eufy_vacuum/adapters/roborock/upkeep_catalog.py`:73 | 1 | # These carry TWO flat mop cloths on twin mounts — same remove-wash-airdry care — **The dual_pad RESERVATION is stated in two files (here and roborock_upkeep_guides.py:167) with the same rationale. When a rotating roller-mop model is covered, both must change or the tier table and its guide library disagree.** |
| **OBLIGED** | `custom_components/eufy_vacuum/dispatch/manager.py`:514 | 1 | # (mirrors the max-wins "nothing rankable -> leave untouched" contract); a — **The safest-water policy mirrors the max-wins 'nothing rankable -> leave untouched' contract. One contract, two policy branches.** |
| **OBLIGED** | `custom_components/eufy_vacuum/jobs/phase_runner.py`:415 | 1 | # Mirrors the pollers' `_still_ours` predicate — a job is advanceable only while it — **Mirrors the pollers' _still_ours predicate -- the same ownership test written in two modules.** |
| **OBLIGED** | `custom_components/eufy_vacuum/learning/job_finalizer.py`:724 | 1 | # mirrors the cleaning_time unit handling right above. — **cleaning_area unit normalization mirrors the cleaning_time handling directly above. Eufy ft2 vs m2 -- if the unit convention changes, both.** |
| **OBLIGED** | `custom_components/eufy_vacuum/learning/manager.py`:2257 | 1 | # mirrors the profile_filter_options passthrough. — **Flattened settings codes mirror the profile_filter_options passthrough; the card's _localizedProfile consumes both. A new field needs adding twice.** |
| **OBLIGED** | `custom_components/eufy_vacuum/learning/stats_rebuilder.py`:347 | 1 | # contributes a sample — mirrors the area_sample_count pattern — **battery_sample_count mirrors the area_sample_count pattern -- 'only a real measurement increments'. RP-036/EST-2 is what the missing half cost.** |
| **COUSIN** | `custom_components/eufy_vacuum/mapping/map_source.py`:388 | 1 | # AREA — mirror the fork's de-normalization exactly; OFFSET-INDEPENDENT of the raster. — **Mirrors the FORK's de-normalization -- an EXTERNAL project. One-way conformance we cannot oblige and cannot detect breaking. Worth its own hazard note, but not a set.** |
| **OBLIGED** | `custom_components/eufy_vacuum/mapping/mapping_services.py`:2709 | 1 | # (mirrors the dispatch-path map_mismatch guard). Indeterminate active map -> compute. — **Mirrors the dispatch-path map_mismatch guard.** |
| **COUSIN** | `custom_components/eufy_vacuum/planning/run_plan.py`:1073 | 1 | # get_access_graph_health diagnostic can answer the same question this — **The one-reachability-answer rule is already INSJM6KC; this is an invariant relation.** |
| **OBLIGED** | `custom_components/eufy_vacuum/receipts/__init__.py`:99 | 1 | #: So a station MIRRORS ITS MODULE PATH, and the gate checks that — a copy-pasted receipt — **A station name must mirror its module path, and a gate checks it. The GATE does not discharge the obligation -- it detects breach, which is the ratchet 00c wants.** |
| **OBLIGED** | `harness/fixtures/cards.js`:24 | 1 | * The option lists mirror the Eufy adapter's `vocabulary` block verbatim — **CROSS-LANGUAGE + FIXTURE: option lists mirror the Eufy adapter's vocabulary block VERBATIM so harness chips match a real install. feedback_test_discipline: a fixture agrees with the CALLER, not the callee -- adapter vocabulary drifts and the harness silently renders a product that does not exist.** |
| **OBLIGED** | `harness/fixtures/theme-library.mjs`:67 | 1 | // Mirror the export envelope's split: colours also land in colors/alpha so — **Fixture mirrors the export envelope's colors/alpha split so the editor renders populated rather than empty.** |
| **COUSIN** | `harness/tests/gallery-completeness.spec.mjs`:78 | 1 | // a gate that mirrors the mirror would drift in exactly the same way. — **Refusal: compares against the shipped index, because 'a gate that mirrors the mirror would drift in exactly the same way'.** |
| **OBLIGED** | `harness/tests/i18n-rtl.spec.mjs`:31 | 1 | // typeless .js as CJS and rejects their ESM `export const`). Mirrors the runtime — **The spec mirrors the runtime locale load path (harness/shoot-locales.mjs); if that path changes the spec validates a model nothing uses.** |
| **COUSIN** | `harness/tests/real-frame.spec.mjs`:7 | 1 | * that blind spot: a gallery case byte-identical to its plain twin, a semantic-token — **Describes a BUG found (a gallery case byte-identical to its twin), not a maintained set.** |
| **COUSIN** | `src/actions/core-refusal-shape.test.mjs`:1 | 1 | // Regression test — CARD-1 (CF-5 root, RF-14's card-side twin), the structured- — **Two test files cover two DIFFERENT refusal shapes (throwing vs structured); complementary, not copies. The contract itself is INT62M7A.** |
| **OBLIGED** | `src/actions/index.js`:52 | 1 | * Translate a UI string for an action (toast text). Mirrors the identical — **The action prototype's t() delegation is identical to VacuumCardBindings'; both route to renderers/shared.js under trust model B.** |
| **OBLIGED** | `src/cards/_shared.js`:118 | 1 | * Response-capable service call (snapshot / saved-profile reads). Mirrors the — **Mirrors the panel's actions/core.js response-capable call helper, argument for argument (target undefined, notifyOnError false, returnResponse true).** |
| **OBLIGED** | `src/cards/card-suggestions.js`:33 | 1 | * The first per-room switch's room_id for a vacuum, or null. Mirrors the filter in — **LOAD-BEARING and says so: mirrors _shared.roomSwitchesFor's filter, 'kept local so this module stays dependency-free'. Dissolving it would add the dependency the duplication exists to avoid.** |
| **COUSIN** | `src/cards/dashboard-card.js`:879 | 1 | // Wrapped in a collapsible group (mirrors the Rooms group) so the card stays compact; — **UI PATTERN (collapsible group mirrors the Rooms group). No shared content.** |
| **OBLIGED** | `src/clean-mode.js`:12 | 1 | // This mirrors the BACKEND owner, `canonical_clean_mode` in — **TEXTBOOK, load-bearing: 'mirrors the BACKEND owner canonical_clean_mode in profiles/room_profiles.py, alias for alias. The two are separate languages and CANNOT share code, so they are pinned to each other by test instead: if you add an alias to one, add it to the other.' Names the obligation, the reason it cannot dissolve, and its guard.** |
| **COUSIN** | `src/i18n/flatten.js`:7 | 1 | * per-subtab sections with staged fallback, mirroring the theme-token chain). — **The nested/flat locale shape is conceptually like the theme-token fallback chain. An analogy, not a copy.** |
| **COUSIN** | `src/i18n/index.js`:248 | 1 | * Trust model: locales may be community-contributed (mirroring the theme/animal — **Shares the community-contribution TRUST MODEL with the theme/animal intake. A policy applied independently at each intake.** |
| **COUSIN** | `src/renderers/language-control.js`:18 | 1 | * closes the menu on outside click, mirroring the card's modal pattern. — **UI pattern (backdrop closes on outside click).** |
| **OBLIGED** | `src/renderers/metrics.js`:521 | 1 | * clean_intensity, fan_speed, water_level, passes, edge). Mirrors the backend — **_localizedProfile 'mirrors the backend _settings_profile_label so the result matches, but localized'. NOTE: this is a THIRD expression of the logic RNJ9YQF7 already covers in two Python files -- the set spans languages and the register currently records only its Python half.** |
| **OBLIGED** | `src/renderers/rooms.js`:1193 | 1 | // escapeHtml'd at render below; this mirrors the room editor + standalone card, — **Chip localization mirrors the room editor + standalone card -- the compact cards were the copy that got missed and showed English.** |
| **COUSIN** | `src/renderers/setup.js`:1046 | 1 | * Mirrors the old hardcoded two-step wizard: add_vacuum + import+save — **Mirrors the RETIRED hardcoded wizard as a legacy fallback -- mirrors something dead, which cannot oblige.** |
| **COUSIN** | `src/renderers/theme-preview.js`:8 | 1 | * rather than mirroring the full card on every keystroke. — **Refusal: mounts only affected surfaces 'rather than mirroring the full card on every keystroke'.** |
| **OBLIGED** | `src/state/core.js`:107 | 1 | * Mirrors the dock_status / dock_status_label pair so card-side — **Mirrors the dock_status / dock_status_label value+label pairing so card-side vocabulary normalization stays unnecessary.** |
| **COUSIN** | `src/state/dialog.js`:26 | 1 | // The "cancelled / dismissed" value each kind resolves to — mirrors the — **Mirrors the BROWSER-NATIVE confirm/prompt/alert return values -- an external, frozen contract.** |
| **OBLIGED** | `src/state/map-compose-and-viewport.test.mjs`:26 | 1 | // Round helper mirroring the composer's 2dp corner rounding. — **Test helper mirrors the composer's 2dp corner rounding; a precision change makes the test assert against its own stale arithmetic.** |
| **OBLIGED** | `src/state/map.js`:1153 | 1 | // first (mirrors the backend apply_live_pose_override) so a live anchor in a no-room — **Mirrors the backend apply_live_pose_override -- the live pose OWNS current_room + path, and the card must clear the stale snapshot values in the same order or the 'stale in the kitchen' ghost returns.** |
| **OBLIGED** | `src/state/order-engine.test.mjs`:4 | 1 | // tiny immutable adapter over {id, order} records so setOrder returns a NEW record (mirroring the — **Stub adapter mirrors the real feature adapters' immutable setOrder.** |
| **COUSIN** | `src/state/room-editor.js`:34 | 1 | * the same rule without duplicating it. — **Refusal: the rule is enforced once 'so renderers and actions both use the same rule without duplicating it'.** |
| **OBLIGED** | `src/state/steps-manifest.js`:12 | 1 | // bundle styles them for the panel; the standalone card carries the same rules in — **Class names must match src/styles/run-profiles.js, AND the standalone card carries the same rules in its own shadow root. This is the renderers<->styles coupling git co-change surfaced independently.** |
| **OBLIGED** | `src/state/steps-order.test.mjs`:3 | 1 | // never touch a room_group's internals (mode-agnostic). Mirrors the backend normalize for save. — **Second member of the steps-order set -- the test also mirrors the backend normalize.** |
| **OBLIGED** | `src/state/steps-queue-order.js`:63 | 1 | // (mirrors the backend get_queue_steps derivation). — **Mirrors the backend get_queue_steps derivation (break with after_index K sits after the K-th room).** |
| **OBLIGED** | `src/styles/saved-zones.js`:1 | 1 | // CSS for the Saved Zones sidebar panel (Wave 3b) — mirrors the run-profiles — **Mirrors the run-profiles panel tokens 'so the two sidecol panels read as a set' -- observational, low severity, but a real obligation.** |

