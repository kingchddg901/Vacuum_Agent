# 00 — Disaster-Recovery Doc Standard

> **Scope:** The bar every `docs/dev/` subsystem doc is measured against. A doc is
> *disaster-recovery grade* when someone with **only the doc — no source** — can
> rebuild the subsystem with correct behaviour, API, and data shapes. This file
> defines what that requires, why, and how to check it. It is grounded in two
> measured reconstruction runs, not vibes.

This standard governs the numbered dev docs; [12 — Battery](12-battery-system.md) and
[10 — Learning](10-learning-system.md) are the worked exemplars.

## 0. The availability contract (ruled 2026-08-07)

What "disaster" means, exactly — the scenario every DR doc is sized against:

- **The disaster is TOTAL loss of source code.** The DR corpus (all numbered docs,
  together) must suffice to rebuild the integration with no original source at all.
- **The target is FUNCTIONAL identity, never byte identity.** A rebuild is correct
  when it satisfies every documented contract and behaviour; private names, internal
  structure, and incidental choices are explicitly NOT part of the contract. (Corollary,
  proven by CAL-23: only behavioural tests can examine a rebuild — a test that asserts
  private internals demands byte identity the contract never promised.)
- **The corpus is SELF-HOSTING — neighbours are supplied as documentation, not code.**
  One section is sufficient when a competent blind implementer can rebuild its
  subsystem from that section plus the **interfaces the OTHER sections' docs state**
  (and public framework knowledge). No source appears anywhere in this contract — that
  is what gives the recovery a start point. Naive "rebuilt-neighbours" induction has no
  base case and the dependency graph is not even acyclic (`error_tracker → active_job →
  learning → error_tracker` is real); doc-stated interfaces dissolve both: mutual
  dependents each publish their surface on paper. The bootstrap is TWO-PHASE, not
  topological — measured reality: only 5 of 26 sections are dependency-free and the
  rest form one mutually-recursive cluster, so no topological order exists. Phase 1:
  declare every doc-stated interface as a skeleton, corpus-wide. Phase 2: implement
  each section against the skeletons, in any deterministic order. Composition rides
  the interface statements, not the sequence.
  Consequence for authors: every doc MUST state the interfaces it PROVIDES and the
  neighbour interfaces it CONSUMES (the rubric's integration-contract row is
  load-bearing for the whole corpus, not local hygiene).
- **Test-harness honesty:** blind-reconstruction experiments (the ablation loop) give
  builders the real surrounding source as a practical stand-in for rebuilt neighbours.
  That is an OVER-approximation — call-site bodies teach more than documented
  interfaces would — so a sandbox pass is **necessary but not sufficient** evidence of
  the corpus contract. The corpus-level acceptance test is the periodic full
  **docs-only rebuild drill** (the doc-as-spec cold run — measured ~90% at last
  execution; the ablation campaign exists to close that gap section by section).

A doc's scope line states this contract's per-section form; it never claims
document-alone sufficiency and never treats the *original* source as a legitimate
dependency — its dependencies are the corpus and the framework, full stop.

---

## 1. What "disaster-recovery grade" means

The test is literal: **a blind reader (or agent) rebuilds the module from the doc
alone; the rebuild is diffed against the real source; the diff measures the doc.**
Every behavioural/API/shape difference that traces to a doc omission is a doc defect
(`DOC_GAP`), separate from reader mistakes (`AGENT_MISS`). The goal is that if the
code vanished, the docs are enough to bring it back.

This is a stricter bar than "reference." A reference doc explains *what and why*. A
disaster-recovery doc is an **executable specification** — precise enough to re-derive
*the exact bytes on disk and the exact edge behaviour*, not just the idea.

## 2. What we measured (why the rubric is shaped this way)

Two runs, blind reconstruction → adversarial diff vs source:

- **Battery docs → ~90% cold.** Strong; the ~10% miss was underspecified edges.
- **Learning docs → ~55% (broke the 90% bar).** A sharp, informative split:
  - **Algorithm / math reconstructs well** — estimator ~75%, utils ~68%; most misses
    were reader errors (rounding, indexing), not doc faults.
  - **Persistence / serialization / HA-integration COLLAPSES** — `stats_rebuilder`
    ~35%, `history_store` ~35%. Whole surfaces were simply absent: exact CSV columns
    (19 of 27 missing), `job_stats` JSON nesting, `jobs_index` schema, `hass.data`
    cache keys, atomic writes, HA-bound constructors, the ~14-kwarg
    `build_completed_job_payload` signature, water metrics everywhere.
  - **7 statements were CONFIDENTLY WRONG** — worse than silence, because they
    actively misled the rebuild (0-vs-1 indexing, drift source, a formula weight that
    under-weighted area ~100×, a function's module-vs-method location, a default).

**Conclusion the standard encodes:** docs are naturally good at *algorithm* and weak
at *serialization + integration + edges*. So this rubric **front-loads the collapse
zones** (§2 data shapes, §3 edges, §4 integration) and **bans confident wrongness**
(§meta). Don't spend the effort where docs already succeed; spend it where they fail.

## 3. The grade scale

| Grade | Answers | Can you rebuild from it? |
|-------|---------|--------------------------|
| Reference | what & why | no |
| Interface | + API / signatures | partially |
| **Reconstruction (DR-grade)** | + exact shapes, edges, integration, provenance | **yes** |

DR-grade = Reconstruction. Everything below is what pushes a doc up to it.

## 4. The rubric — a DR-grade subsystem doc MUST specify

Grouped by the failure modes above; use as a checklist.

### 4.1 Algorithm & rules *(docs already do this — hold the line)*
- The exact computation: **every formula with all terms, coefficients, and weights** —
  not "weighted by area" but the actual weight (area was ~100× under-weighted once).
- Precedence / tie-breaking / ordering rules, stated explicitly.
- Behaviour at the boundaries of each input range.

### 4.2 Data shapes & serialization *(the #1 collapse zone — spell it out)*
- Every persisted structure's **exact schema**: field names, types, and **nesting**.
- Exact file formats: **CSV columns in order and count**; JSON key layout; store keys.
- In-memory layout that survives restarts (`hass.data` cache keys + shape).
- **Per-field rounding precision** (e.g. 2 dp vs 4 dp).
- What is **persisted vs computed-on-read**, and **when** each field is set
  (e.g. a value added by a *finalizer after* the main compute).

### 4.3 Edge behaviour — clamps, coercion, indexing *(silently glossed = silently wrong)*
- Every **clamp** with its exact condition → result ("negative → `None`"; ">0 gate";
  int/float coercion). "…and then it's clamped" is **not** enough — state the clamp.
- **Indexing conventions**: 0- vs 1-based, per structure (a confidently-wrong source).
- Null / empty / missing handling, per field.

### 4.4 Integration & host contract *(HA-bound = collapses)*
- **Entry-point / constructor signatures with all arguments** (the ~14-kwarg payload
  builder is a rebuild-blocker if absent).
- The **host contract**: what is *injected* vs *imported* — the seam a rebuild must
  reproduce. Write it as an explicit contract (cf. learning's `LearningHost` /
  `BrandFacts` Protocols).
- **Persistence mechanics**: atomic write (temp-file → rename), cache lifecycle.

### 4.5 Brand / variant dependence *(the leak that hides bugs)*
- Flag **explicitly** any behaviour that differs by brand / model / variant. The
  `clean_times` clamp (Eufy caps 2 passes, Roborock allows 1–3) was undocumented —
  and was a *real bug*, not just a doc gap.
- Mark which values are **observed-data passthrough** vs **capability-branched**.

### 4.6 Provenance & location
- Where each field originates and **when** it is set (post-compute additions).
- A function/method's **location** when it matters (module-level vs method — a
  confidently-wrong source once).

## 5. Meta-rules (as important as the checklist)

1. **Never be confidently wrong.** A precise-but-unverified statement is *worse than
   silence* — it misleads the rebuild. If you have not verified it against source,
   mark it *unverified* or omit it. Hedge, don't harden.
2. **A reconstruction that disagrees with the doc/code is a BUG SIGNAL.** When a
   *reasonable* rebuild contradicts what's written, the **code** may be wrong — the
   `clean_times` Eufy-ism surfaced exactly this way (the "no clamp" guess was closer
   to correct than the buggy clamp). Investigate the disagreement; don't just patch
   the doc.
3. **This depth is intentional — do not trim it as "over-documentation."** The clamps,
   exact columns, and kwarg lists are the load-bearing parts; a normal doc glosses
   precisely what reconstruction needs. Guard them against future cleanup passes.

## 6. Acceptance test

- **Full (measured):** a blind agent rebuilds the module from the doc alone; diff vs
  source; classify each miss `DOC_GAP` vs `AGENT_MISS`; the `DOC_GAP`s are the doc's
  failures. Re-verify each proposed doc fix *against source* before applying (an eval's
  "codeTruth" is ~90% reliable, not 100% — and the mismatch may be a code bug, per §5.2).
- **Pragmatic (per-doc walk):** run §4 against the doc. Audit §4.2–§4.4 hardest —
  that's where docs collapse; §4.1 usually survives. A doc passes when nothing in the
  collapse zones is missing, hand-wavy, or unverified.

## 7. Subsystem status

DR-grade is earned per subsystem, one at a time. Track it here.

| Subsystem | Doc | DR-grade? |
|-----------|-----|-----------|
| Battery | [12](12-battery-system.md) | ✅ ~90% (exemplar) |
| Learning | [10](10-learning-system.md) | ✅ re-audited 2026-07-28 against this rubric — 12 collapse-zone gaps closed (full `completed_job` schema §2.0, room-stats/baseline field sets, `jobs_index` fields, `hass.data` caches, idle-wall blocker §3.2b, finalizer/host-contract drift). The audit also surfaced a **real code bug** (cancel reason dropped from the persisted `learning_blockers`) — fixed + regression-tested, per §5.2. |
| Job Lifecycle | [06](06-job-lifecycle.md) | ✅ audited 2026-07-28 (2 waves, ~20 findings) — added the `active_job` + `incomplete_run.json` + phase-record schemas and the full lifecycle signatures / return shapes; fixed a confidently-wrong cancel threshold and the `last_*` live keys; stripped 25 stale line-refs. Also surfaced a behavior asymmetry (`EVENT_RUN_INCOMPLETE` fires only on the service finalize path) — documented + flagged for a product decision, per §5.2. |
| Queue Engine | [07](07-queue-engine.md) | ✅ audited 2026-07-28 (14 findings) — fixed confidently-wrong `clean_intensity` values (Quick/Narrow/Deep; `Standard` is dead) + profile-resolution precedence (per-room fields always win) + the zone-in-gate drift + zone-phase timing; added the exact wire-payload / `resolved_rooms` schemas, dispatch-engine registry + signatures, capability-gate mapping, and `map_id` cast/omission. Two code smells flagged for a decision (unclamped `clean_times` on the Eufy path; stale `queue_engine` TypedDicts). |
| External-Run Ingestion | [28](28-external-run-ingestion.md) | ✅ audited 2026-07-28 (9 findings + 2 code flags) — added the full external-ingestion adapter contract (§9: `external_mid_run_statuses`, `job_segmenter`, `room_attribution`, capture prereqs), corrected §10 file layout (`ExternalRunManager` in `learning/external_run.py`, not `core/manager.py`), documented the pose-only pending-record variant (§4), the sanitized filename chain, the `<4`-sample cold-start gate, and the exact service returns. §5b reconcile + §6 gate verified consistent with 10/06. Two low-confidence code smells flagged (resegment return lacks `resegmentable`; pose-only records lack `attribution_confidence`). |
| Phase Runner | [30](30-phase-runner.md) | ✅ audited 2026-07-28 (10 findings) — the room_group/stop machine was already solid; fixed the **zone-phase** cluster: the undocumented zone verify branch (§6.4 — sustained cleaning-state, else the phase locks ACTIVE forever), the zone dispatch early-return (§6.3), the `zones`-rects-at-**build**-time serialization (§3.1 — was "at dispatch time"), the `zone_timing` wall-start basis (§5.5 — prev phase, not job start), + zone-forces-strict-order and the queue-breaks step source. One code-behavior asymmetry documented + flagged (charge-timeout deadline restarts fresh on re-arm vs wait recomputes). |
| Room Rules | [09](09-room-rules-system.md) | ✅ audited 2026-07-28 (12 findings + 3 code flags) — operators/categories/fan-out/wire-format were solid; fixed the serialized-output collapse: full `preflight` schema + blocked/modified entry schemas, the `_build_effective_start_plan` return shape (`payload = phases[0]`, NOT `build_room_clean_payload`), the mid-job report schema + its `last_path_block_signature` mutation (doc said "does not mutate"), the §9 operator-allowlist step (a new op is coerced to `equals` without it), `protected_room_config` nullifying modifier water/edge, §6 rounding/guards/reason ladder. Flagged: stale TypedDicts, unguarded `int(room_id)`, backend `clean_passes` unclamped (mitigated by the 07 wire clamp). |
| Rooms | [08](08-rooms-system.md) | ✅ audited 2026-07-28 (10 findings + 3 code bugs) — the serialization collapse: documented the THREE divergent room-record writers (save / rebuild / load-time backfill) + the load-time normalization (setdefaults + `carpet`→`carpet_<pile>` migration) that reconciles them, the exact defaults, the reconciliation output shapes, the 9-key summary entry (vs rebuild's reduced 4-key), the `source_refresh` cache key/shape, the discovery cache key, and the discovery skip filters. Fixed confidently-wrong `clean_intensity`/`fan_speed` examples (Quick/Max, not Standard). Flagged **BUG-A** (HIGH): `rebuild_map` permanently strips `is_configured`/`configured_at` → rebuilt rooms read unconfigured and are filtered from entity creation. |
| Error Tracker | [23](23-error-tracker.md) | ✅ **ABLATION-CLOSED 2026-08-07 — the first section to earn its size experimentally** (CAL-23; the DR prose-ablation protocol and its ledger live in the repo-local audit record, not on this site). 475→415 lines (−13%) with one invariant ADDED, and the replacement is the doc a **2-of-2 fresh blind builders** rebuilt the module from — 8/8 behavioral tests + 9/9 certified pins, twice. This row's grade now means *demonstrated sufficient*, not *reviewed and believed*. Earned invariant #1 (`error_label_key` returns a label only for a non-empty **string** entry; any other stored value resolves to `None` exactly as an absent one does — ledger entry 1). Pre-build, the trim also caught a confidently-wrong claim that had survived two truth passes: §7.2 documented the **deprecated** `harvest_active_run` as the live finalizer wiring, when the real design is the peek/commit pair. Apparatus caveat, per the protocol's own suspension rule: the legacy suite was **81% white-box** (35/43 tests assert private names and reject any correct reimplementation), so certification rests on 8 behavioral tests + 9 tester-authored public-contract pins; the 35 are handed to test-hardening as over-pinned. Earlier: ✅ audited 2026-07-28 (12 findings + 1 code bug) — record shapes / extraction / API were solid; fixed confidently-wrong: the not-error sentinel set is **replaced** by the adapter's (not merged), the secondary predicate `strip().lower()`s (`"Error"`→`"error"`), the rising edge fires on **any** error value (not not_error→error). Added the harvest→finalizer injection + `extra_outcome`/`total_error_seconds` contract, `unregister_vacuum`, persistence mechanics. Flagged **Gap 7** (code bug): `_on_grace_expired` uses the generic sentinel set not the adapter's → a stuck event whose `error_message` reads a brand sentinel (Eufy `"none"`/`"normal"`) is silently dropped. |
| Setup System | [15](15-setup-system.md) | ✅ audited 2026-07-28 (17 findings + 4 code flags, docs-only) — the algorithm/rule surface (step ids, thresholds, protection-level derivation, delete steps) was DR-grade; the collapse was serialization + provenance + service wiring. Added the 5-field drift-history entry schema (§4.5/§8 — `first_seen_at` was entirely absent), `compute_room_drift`'s **history-only** branch (the one the panel actually runs, §4.5), the full `update_drift_history` mutations (`seen_passes` resets to 0 on a miss; `first_missed_at` clears on sighting), §4.7 the `is_configured`/`configured_at` provenance + `_migrate_setup_progress` + `active_map_configured` sticky save_rooms re-open, the `migrated_at` divergent record, §9 the service-layer step-advance gate (`status ∈ {success, already_done}` + the `async_reload` side-effect + `setup_set_map_camera`), the import/discovery/delete literal shapes + `code` enum, and the cadence coercion asymmetry (`or` loses a `0`, `is not None` keeps it). Fixed **confidently-wrong** §3.2: import calls `save_managed_rooms`→`build_managed_rooms`, **never `rebuild_map_bucket`**. **FIXED CS-2:** `get_discovery_cadence` now honors an explicit low confirmation-pass count (`is not None` guard, not `or`) and **floors `0`/negative to 1** — a literal `0` would make `missing_passes >= n_remove` a tautology (every configured room flagged removed); +regression test DR-15, full suite 2891 green. Still flagged (not fixed): CS-1 (`migrated_at` write-only/dead), CS-3 (load-path `is_configured` setdefault gap — mitigated by the BUG-A fix), CS-4 (4-key vs 5-key divergent `setup_progress` writers). |
| Architecture Overview | [01](01-architecture-overview.md) | ✅ audited 2026-07-29 (aggregator tier; SHAPE doc — lighter treatment) — the layer diagram, the 14-subsystem inventory with all post-extraction bundled-subsystem paths (`dispatch/`, `live_refresh/`, `external_run`, `phase_runner`, `map_source`), and the startup order were **verified current**. Fixed one HIGH confidently-wrong structural defect spanning §3/§4/§10 (**5 platforms → 6** — the live `select` debug-target platform, which §2's own diagram already listed → the doc self-contradicted; same defect as 02), added `debug.py` to the §9 services table, dropped a ~90-line-stale battery line-ref, and filled the `rooms/`/`setup/` package descriptions. No code flags. |
| Listeners | [04](04-listeners.md) | ✅ audited 2026-07-29 (aggregator tier; 5 HIGH + 7 MED + 4 LOW + 3 code flags, docs-only) — the ordering-plan bet **held for lifecycle/path-blockers/discovery/job-progress** but **broke for the two modules that absorbed real feature growth**: `pose_sampler` (dual-source attribution + dispatched-run sampling) and `pause_timeout` (the FN-1 stranded reaper). Fixed **confidently-wrong**: §6 was missing the **entire second reap** (stranded-`started` → `async_finalize_stranded_job`, fires `job_finished`+`run_incomplete` — the landed B1 "if it strands it is incomplete"); §10 "external runs only" (also samples `started`) and "single `live_pose` source" (also `native_current_room`/Roborock); §9 `vacuum_docked` watches the **vacuum entity's** literal `"docked"` (edge-guarded), not `dock_status` vocab; §7 progress-tick payload is `{ids}` only, **not** the snapshot (matches 02). Added the `run_incomplete_event_data` helper + 11-key `job_finished` shape, the path-blocker any-change trigger + report-dict payload (09), the dock dedup+save, the job-metrics unit conversions (60× guard, ft²→m²), the `completed_finalize_signals` 4-key subset, and cadence/vocab edge fixes. Flagged CS-1 (`job_metrics` stale 3-tuple comment), CS-2 (dead `"int"` branch), CS-3 (always-on 6h ticker). |
| HA Integration | [02](02-ha-integration.md) | ✅ audited 2026-07-29 (opens the AGGREGATOR tier; 10 findings + 3 code flags, docs-only + 1 comment fix) — the ordering-plan bet held: 8 of 10 gaps were in the §7 event table, 6 of them **02-vs-06 drifts where 06 (hardened this campaign) already had the source-correct payload** — so the fix was mostly "align §7 to 06 §10". Fixed **confidently-wrong**: 5 platforms → **6** (the live `select` debug-target platform was omitted), and "nine events / all in const.py" → **ten** (`EVENT_ROOM_COMPLETED`, defined in `mapping/tracker.py`, was undocumented). Aligned the event payloads to 06 (`EVENT_ROOM_STARTED` +`completed_room_ids`, `EVENT_ROOM_FINISHED` native-signal omits `confidence`, `EVENT_JOB_FINISHED` two shapes, `EVENT_RUN_INCOMPLETE` 5 fire sites, `EVENT_PATH_BLOCKED` = report-dict+augments), fixed `EVENT_EXTERNAL_RUN_PENDING`'s fire site (`learning/external_run.py` not `core/manager.py`), added the `async_remove_config_entry_device` host hook, and the `STORAGE_KEY` provenance. Fixed **CS-3** (the stale `__init__.py` "select platform was dropped" comment that *seeded* the doc error). Flagged CS-1 (`DATA_SERVICES_REGISTERED` dead const), CS-2 (`EVENT_JOB_FINISHED` payload asymmetry — same known 06 divergence). |
| Core Manager | [05](05-core-manager.md) | ✅ audited 2026-07-29 (aggregator tier; 1 HIGH + 3 MED + 4 LOW, docs-only, no code flags) — surfaced UNAUDITED during the docs/dev reorg. The **owns-vs-delegates map** (the #1 risk for an orchestrator doc) **verified fully current**: all six extraction delegators (`dispatch`/`phase_runner`/`run_plan`/`external_run`/`map_source`/`live_room_refresh`) correctly labeled delegators, every method the doc calls "owned" genuinely owned, §2 construction order + §3 constructor table byte-exact. The collapse was one manager-OWNED return shape + provenance rot. Fixed **confidently-wrong** §6 `get_dashboard_snapshot` "aggregates" list (claimed a managed-vacuums list + payload state + a top-level dock key — the first two are the SEPARATE `get_managed_vacuums`/`get_payload_state`; it is really a **per-vacuum ~36-key** read-model) and `update_room_fields` "and persists" (it's **sync + in-memory, no `async_save`** — the save is the service layer's, contradicting the doc's own §3). Added the §2 `_phase_dispatch_pending` guard-clear step, the `awaiting_bounds_exit` **path-optimizing-brand suppression** (`honors_clean_order is False` → Roborock), cross-refs to `frontend/backend-contract-and-data-shapes` for both snapshot shapes, fixed 3 stale color-sentinel line-refs (1233→1261 / 55→53 / 1291-1295→1319-1323) + the `resolve_active_map_id` typo, and qualified §7 "never reads disk" (the room-history cache still lazy-loads learning-history files). No code bugs — the code is correct, 05 was the stale party. |
| Data Model | [03](03-data-model.md) | ✅ audited 2026-07-29 (aggregator tier; 4 HIGH + 3 MED + 2 LOW, docs-only, no code flags) — the LAST backend doc; **closes the AGGREGATOR TIER + the whole backend.** The inlined OBJECT shapes were largely byte-faithful (hold-the-line: the default active-job state §5, the payload/ResolvedRoom capability-gating §4, the learning record §9), so the collapse was 03's #1 job as an INDEX. Added FOUR genuinely-persisted top-level keys the inventory omitted — `battery` (`{"vacuums":{…}}`, battery/manager.py:284), `adapters` (config_loader.py:78), `learning_processing_enabled` + `learning_pending_runs` (manager.py:319-320, also missing from the key-seeding prose) — plus `analytics` for completeness; THREE co-resident MapBucket keys (`saved_zones`/`learned_zones`/`queue_breaks`); and the `_pending_run_steps` transient staging key. Fixed **confidently-wrong**: §2a `clean_intensity` (`"Standard"/"Intense"` → **Quick/Narrow/Deep**, Standard dead — the same 07/08 fix reaching the data-model doc) and §1 `RoomSelectionSummary` (documented only `{enabled_count,disabled_count}` → the real 4-key shape with the 9-key `SummaryEntry` lists + the `rebuild_map_bucket` 4-key REDUCED divergence = doc-17 **BUG-B**). §6a room-profile record → 9 keys (added `mop_required`, `path_type` always-present str, cross-ref 16 §3.1); MapMetadata gained `reconciled_at`/`reconciliation_dismissed_at`/`last_rebuild`. No NEW code flags (surfaced smells — 17 BUG-B divergent summary writer, 15's write-only `migrated_at`, `_pending_run_steps` living in the durable dict — are all already tracked). Deferred: L3 `migrated_at` in §12 (LOW, owned by 15's CS). **BACKEND COMPLETE — only FRONTEND remains.** |
| Adapter Config Reference | [22](22-adapter-config-reference.md) | ✅ audited 2026-07-29 (2099-line schema diff; docs-only + 2 schema-desc fixes) — **all confidently-wrong fixed** (the worst category): §13a.2/§13a.3 "Roborock omits map_state_source/map_render" (it declares both — memory backend + `roborock_raw_map_v1`), `live_transition` "no schema entry" ×3 (it IS in the schema), §17 `water_rates` absent-behavior (flat `4.0`, not the Eufy table; Eufy *declares* it), §17a `wash_frequency_bounds` absent (`1.0/1440.0`, not Eufy `15/25`), §6 `cancel_detection_states` type (`str \| list`). Added `require_job_active_clear` + `job_active`/`mop_active`, `params_as_list`/`passes_is_global` + the `passes_max` 2-vs-3. **Fixed 2 SCHEMA bugs (config_schema.py, doc was right): CS-A** (charging desc claimed a substring fallback `core/charging.py` removed), **CS-B** (stale canonical wash-mode keys → `by_room/by_time/off`); 335 schema/adapter tests green. Additive fills also completed (§14c `external_mid_run_statuses`, §14d `cleaning_time_unit`, the §14 zone caps, the full Roborock dispatch field set, `guide_translations`, `maintenance_only`/`remaining_is_state`, `implicit_map_id`, `room_attribution.source`, §3 glance) + fixed a recurring stale `get_dashboard_snapshot` line-ref. **ADAPTERS TIER COMPLETE.** Still flagged: CS-C (`passes_max` split 2-vs-3 defaults), CS-D (schema-vs-runtime drift). |
| Eufy Adapter | [25](25-eufy-adapter.md) | ✅ audited 2026-07-29 (adapters swarm; docs-only) — value-level blocks were largely DR-grade; collapse in §3 provenance + unenumerated Eufy value-sets. Fixed confidently-wrong §3 model source (device-registry primary, `detected_model` attribute fallback — the scalar/Tuya fix, same as 21). Added the full `capability_hints` family-sets + `has_attribute_rooms`, the model-family catalog (7 hints + 22 T-codes), the 5 alias maps (incl. `standard/normal→quick`), the verbatim `blocked_*` sets, the Eufy per-side zone caps, `room_attribution.source`/tuning, `guide_translations`/`upkeep_guides_i18n`, and several scalar fills. Flagged CS-1 (`HA_ACTIVE_VACUUM_STATES` dead import + core hardcodes the value it should read from the adapter). |
| Eufy Segmentor | [26](26-eufy-segmentor.md) | ✅ audited 2026-07-29 (adapters swarm; docs-only) — companion to the DR-hardened 11 §2; its own scope (engine Protocol, degraded taxonomy, envelope, porting) was near-DR-grade. Added the undocumented **emit-time keep/drop gate cascade** (§5.1 — undocumented in *both* 26 and 11; the reject-reason list + `_component_should_keep` thresholds), fixed the raw-detector-vs-`SegmentationResult` conflation (§3, cross-ref 11 §2.12), the stale "trace-based tracking" → native current-room (§1/§10.5), the `no_image_path` degraded reason, and §8/§6 cross-refs. **Cross-doc:** corrected 11 §2.6 "7-level" → "8-level (0–7)" bins (the swarm caught 11 was the wrong one). Flagged CS-1 (`_split_suspicious_component` annotated 2-tuple but returns 3-tuple), CS-3 (`NoopSegmenter` docstring stale), CS-4 (dead `slices`). |
| Roborock Adapter | [29](29-roborock-adapter.md) | ✅ audited 2026-07-29 (adapters swarm; docs-only) — dispatch/map-render/completion/settable-mop were DR-grade. Fixed **confidently-wrong** §2 ("no upkeep modules" — they exist, fully wired with a 13-language guide library) and the `get_dashboard_snapshot` line ref (`3376-3389`→`3949-3963`) + stale Map-Bounds-tab framing (derived-but-unconsumed since the mapping split). Added the load-bearing **`cleaning_time_unit: "min"`** (a silent 60× learning-corruption fix), `rooms_unique_per_job: False` (the revisit guard), 4 missing entity keys, the `error_tracking`/`room_attribution`/`charging`/`map_state_source` blocks, the exact `discovery` keys, the 12-entry maintenance count, and the zone min. Flagged CS-1 (`remaining_is_state` unconsumed — confirms 13's finding), CS-2 (`guide_translations` "empty today" comment stale), CS-3 (`supports_map_bounds` unconsumed). |
| Adapter System | [21](21-adapter-system.md) | ✅ audited 2026-07-28 (opens the ADAPTERS tier; 10 findings + 2 code flags, docs-only) — the registry/seam/loader half was DR-grade; collapse in the **capability model** (§3.5) + **assembly provenance** (§5.2), plus subset-presented-as-complete claims. Fixed **confidently-wrong**: the 9 `supports_*` flags are **not** pure entity-probes — 5 are hint-OR-presence (model-family hints → True even with the entity absent), `supports_water_control` is never probed (= `supports_mop_features`), `supports_edge_mopping`/`passes`/`custom_room_config`/`room_clean` are hardcoded `True`; and the model source is the **device-registry** model (primary), the `detected_model` attribute only a fallback (the scalar/Tuya fix). Added: framework-read entity keys beyond the schema's 18 (esp. `job_active`, referenced by the completion schema), the 4 required blocks, the schema-absent `model_family`/`capability_hints`, `maintenance_only`, the 5 omitted Roborock dispatch fields + `map_id_type` default `"str"`, the per-side-vs-per-area zone caps, `build_entity_id`'s `strategy` kwarg, and fixed ~300-line-stale refs. Flagged CS-1 (validator enforces no required fields — doc already noted), CS-2 (schema entity-keyset drift = root of the `job_active` gap). Chris's "adapters won't be that bad" — borne out: lighter than the managers, docs-only, no code fixes needed. |
| Maintenance Manager | [13](13-maintenance-manager.md) | ✅ audited 2026-07-28 (parallel swarm; 4 HIGH + 5 MED + 5 LOW + 5 code flags, docs-only) — fixed **confidently-wrong** `replacement_status` (real signature `remaining_percent` not `state_value`, thresholds ≤5/≤10/≤15 not ≤5/≤15/≤30, input is derived %-of-life not raw state — the issue-#38 refactor the doc never absorbed), `max_interval_hours` "enforced at write" (it's **card-side only**; the service enforces `min=0` no max, the Number entity clamps to framework 1.0–500.0), and `sensor_suffix` "None when proxy_for" (they coexist). Added the `maintenance_only` + family-gate render rules (§4.3), the Eufy-vs-Roborock brand divergence (§4.4 — Roborock replacement rows read `"unknown"`, `remaining_is_state` declared-but-unconsumed), the full 24-key replacement-item / 26-key maintenance-item schemas + `model_meta`/`guide` shapes, `set_maintenance_interval` + Number/Sensor entry points, and the service-layer persistence. **FIXED CS-1** (reset now preserves the user's `interval_hours` override instead of wiping it; +regression MNT-7b, full suite 2892 green). Still flagged: CS-2 (`remaining_is_state` dormant), CS-3 (no backend max enforcement). |
| Dock Manager | [14](14-dock-manager.md) | ✅ audited 2026-07-28 (parallel swarm; 1 HIGH + 4 MED + 4 LOW + 3 code flags, docs-only) — the gating/storage core was DR-grade. Fixed **confidently-wrong** §5.2 token fallback (code scans `button.{object_id}_`-prefixed registry entities and matches by **substring**, not "all `button.*`" + split-on-`_` — the doc described safer behavior the code doesn't implement, CS-1). Added the 4 missing `*_label`/`lifecycle_message` return keys (§6.1), the exact 9-key blocked / 10-key success dispatch shapes (§7), the service-layer `map_id` auto-resolution + `ServiceValidationError` + `supports_response` (§7.1), the undocumented `get_dock_action_entities` (§5.3), the full capability→action map, and the `dock_event`/`learning`/`diagnostics` consumers. Correctly excludes the dock **anchor** (owned by 11/17). |
| Onboarding Manager | [18](18-onboarding-manager.md) | ✅ audited 2026-07-28 (parallel swarm; 2 HIGH + 2 MED + 2 LOW + 4 code flags, docs-only) — the storage/return/predicate surface was already DR-grade; the gaps were **confidently-wrong integration** claims. Fixed: `confirm_floor_type` has **no** panel/service path — it's a **bulk auto-confirm over every room on every `save_managed_rooms`** (not per-room, not initial-import-only); the §6 "Panel → get_onboarding_state" seam doesn't exist (real seams: the `get_start_status` embedding + the onboarding diagnostic sensor). Documented the start gate keys on `floor_types_complete` **alone** (not full `onboarding_complete`; zero-room maps pass vacuously). Flagged **CS-3**: the floor-type "review gate" is self-satisfying — the code never enforces a human floor-type review (product decision; ties to the deconstruction B3 onboarding-as-gate work). Plus CS-1/CS-2 (dead `*_notified` + write-only `room_count_at_last_check`), CS-4 (enabled-vs-`is_configured` cross-gate mismatch). |
| Profile Manager | [16](16-profile-manager.md) | ✅ audited 2026-07-28 (9 findings + 6 code flags) — built-ins/ID/CRUD/capability-gate were DR-grade; the shaper + run-profile serialization had gaps. Added §6.2 the full 12-key `get_effective_room_details` output (with the **renamed** `default_clean_passes`/`default_edge_mopping` + `selected_`vs`resolved_profile_name` traps), §6.3 the resolution precedence ladder (carpet overrides room fan/water; "room always wins" is only true for unconstrained hard-floor fields), §3.1 the 9-key stored room-profile record (path_type/mop_required always-defaulted), §5.5 `apply_room_profile`, §7.7 the `start_run_profile` signature/returns, §7.2 snapshot coercions + the `-1` sentinel, and the `from_room` return shapes/reasons. Fixed confidently-wrong: "`steps` written **only** by `set_run_profile_steps`" (also written by `save_run_profile` when the queue `has_breaks`), and `_match_profile_from_fields` "exactly match" (it's a **normalized** match vs a bare-`{profile_name}` candidate). **FIXED B1 (HIGH, real bug):** a plain vacuum room **never matched its vacuum preset** → always `profile_name="custom"` (protected room forces water `Off`; candidate resolved to hardwood water default `Low`) — corroborated by the PM-10 test comment. Fix: `_match_profile_from_fields` now resolves + protects each candidate under the room's `floor_type` (symmetric pipeline); +regression test PM-10b, full suite 2889 green. **B2–B6 also resolved:** B2 (custom profiles now derive `path_type` Deep→narrow + `mop_required` from mode, +test PM-2b), B3 (`ProfileRecord` TypedDict corrected to the real 9 keys), B4 (`apply_room_profile_to_config` now threads `catalog` into alias resolution), B5 (`apply_room_profile` id filter cleaned via `_safe_int`; the `*_from_room` `int(room_id)` is service-`Coerce`d so unreachable), B6 (documented benign: dispatch reads the persisted `path_type`, no re-sync needed). Full suite 2890 green. |
| Map Manager | [17](17-map-manager.md) | ✅ audited 2026-07-28 (8 findings + 4 code flags) — the pure-function signatures/return shapes (§3.1–3.5) were DR-grade; the **persisted room-record + summary serialization collapsed**. Added the full 22-field rebuilt room-record schema to §3.4 (exact types/defaults/coercions: `profile_name="vacuum_quick"`, `fan_speed="Max"`, `floor_type="hardwood"`, `path_type` no-coercion, list-guarded `grants_access_to`/`rules`) + the `discovered_rooms` input contract (`room_id`/`name` required, per-element `map_id` ignored — param wins) + both summary entry shapes. Flagged **BUG-B** in-doc: `rebuild_map_bucket` is the lone writer of the **reduced 4-key** summary entry vs the canonical **9-key** `build_room_selection_summary` (drops `profile_name`/`floor_type`/`clean_passes`/`edge_mopping`/`carpet` until a non-rebuild write repopulates). Fixed confidently-wrong `get_managed_maps_summary()` → **`get_vacuum_maps()`** (§5). Added the `is_configured`/`configured_at` provenance (entity-creation gate, BUG-A carry-forward), the co-resident `queue_breaks`/`learned_zones` keys + the `reconciled_at`/`reconciliation_dismissed_at` metadata keys, and the stale `image_variants` set (per-layout `custom_<id>` + furnished-art). Code flags: CS-2 (BUG-B fix = call the 9-key builder), CS-3 (`is_transition` not in `RoomConfig`), CS-4 (`configured_at` None-vs-`_iso_now()` asymmetry), CS-5 (possibly-dead `core/manager.py` imports). |
| Mapping | [11](11-mapping-system.md) | ✅ audited 2026-07-28 (11 findings + 3 code flags) — algorithm (§2.2–2.9 masks/clustering/splitting) was pristine; the CV/custom **serialization** collapsed. Added §2.12: the full ~27-field per-segment dict (exact rounding, `segment_id`=`"segment_{N}"`, `area_percent` 0–1/4dp, value sets for `structural_role`/`segmentation_state`/`variant_support`/`edit_readiness` with thresholds) + the *stored* `image_segments` envelope (`_reshape` hoists `segmentation`/`runtime` under `engine_diagnostics`, adds `engine`/`analyzed_at`) + the keyword-only detector signature. Fixed confidently-wrong: custom segments are **not** the identical CV shape — `_build_custom_segment` is reduced (omits ~10 metrics, `area_percent` 0–100/2dp, `center_pixel` 1dp, adds `source`), and the stored `custom_segments` envelope is reduced too (§10.4). Pinned the `polygon_pct` divisor to the store's own dims (§2.10), the adjust-time `bbox`/`center_pixel` rewrites + the map-bucket-vs-active-scope scope caveat (§5.2), the dead `"primary"` path clause (§6.1), and the two extra coordinator readers (§11.2). Flagged 3 code smells: stale canonical `SegmentationState`/`EditReadiness` Literals (don't match runtime values), the `updated.get("id")` adjust-log that always reads `"unknown"`, and the latent cross-scope adjustment collision. |
| *(all others)* | — | ⬜ reference-grade — pending audit against this standard |

Harden one subsystem per pass: walk §4/§5, fix the collapse zones, update this row.
