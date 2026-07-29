# 00 — Disaster-Recovery Doc Standard

> **Scope:** The bar every `docs/dev/` subsystem doc is measured against. A doc is
> *disaster-recovery grade* when someone with **only the doc — no source** — can
> rebuild the subsystem with correct behaviour, API, and data shapes. This file
> defines what that requires, why, and how to check it. It is grounded in two
> measured reconstruction runs, not vibes.

This standard governs the numbered dev docs; [12 — Battery](12-battery-system.md) and
[10 — Learning](10-learning-system.md) are the worked exemplars.

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
| Error Tracker | [23](23-error-tracker.md) | ✅ audited 2026-07-28 (12 findings + 1 code bug) — record shapes / extraction / API were solid; fixed confidently-wrong: the not-error sentinel set is **replaced** by the adapter's (not merged), the secondary predicate `strip().lower()`s (`"Error"`→`"error"`), the rising edge fires on **any** error value (not not_error→error). Added the harvest→finalizer injection + `extra_outcome`/`total_error_seconds` contract, `unregister_vacuum`, persistence mechanics. Flagged **Gap 7** (code bug): `_on_grace_expired` uses the generic sentinel set not the adapter's → a stuck event whose `error_message` reads a brand sentinel (Eufy `"none"`/`"normal"`) is silently dropped. |
| Mapping | [11](11-mapping-system.md) | ✅ audited 2026-07-28 (11 findings + 3 code flags) — algorithm (§2.2–2.9 masks/clustering/splitting) was pristine; the CV/custom **serialization** collapsed. Added §2.12: the full ~27-field per-segment dict (exact rounding, `segment_id`=`"segment_{N}"`, `area_percent` 0–1/4dp, value sets for `structural_role`/`segmentation_state`/`variant_support`/`edit_readiness` with thresholds) + the *stored* `image_segments` envelope (`_reshape` hoists `segmentation`/`runtime` under `engine_diagnostics`, adds `engine`/`analyzed_at`) + the keyword-only detector signature. Fixed confidently-wrong: custom segments are **not** the identical CV shape — `_build_custom_segment` is reduced (omits ~10 metrics, `area_percent` 0–100/2dp, `center_pixel` 1dp, adds `source`), and the stored `custom_segments` envelope is reduced too (§10.4). Pinned the `polygon_pct` divisor to the store's own dims (§2.10), the adjust-time `bbox`/`center_pixel` rewrites + the map-bucket-vs-active-scope scope caveat (§5.2), the dead `"primary"` path clause (§6.1), and the two extra coordinator readers (§11.2). Flagged 3 code smells: stale canonical `SegmentationState`/`EditReadiness` Literals (don't match runtime values), the `updated.get("id")` adjust-log that always reads `"unknown"`, and the latent cross-scope adjustment collision. |
| *(all others)* | — | ⬜ reference-grade — pending audit against this standard |

Harden one subsystem per pass: walk §4/§5, fix the collapse zones, update this row.
