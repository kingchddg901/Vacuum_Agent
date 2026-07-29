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
| Setup System | [15](15-setup-system.md) | ✅ audited 2026-07-28 (17 findings + 4 code flags, docs-only) — the algorithm/rule surface (step ids, thresholds, protection-level derivation, delete steps) was DR-grade; the collapse was serialization + provenance + service wiring. Added the 5-field drift-history entry schema (§4.5/§8 — `first_seen_at` was entirely absent), `compute_room_drift`'s **history-only** branch (the one the panel actually runs, §4.5), the full `update_drift_history` mutations (`seen_passes` resets to 0 on a miss; `first_missed_at` clears on sighting), §4.7 the `is_configured`/`configured_at` provenance + `_migrate_setup_progress` + `active_map_configured` sticky save_rooms re-open, the `migrated_at` divergent record, §9 the service-layer step-advance gate (`status ∈ {success, already_done}` + the `async_reload` side-effect + `setup_set_map_camera`), the import/discovery/delete literal shapes + `code` enum, and the cadence coercion asymmetry (`or` loses a `0`, `is not None` keeps it). Fixed **confidently-wrong** §3.2: import calls `save_managed_rooms`→`build_managed_rooms`, **never `rebuild_map_bucket`**. Flagged (code, not fixed): CS-1 (`migrated_at` write-only/dead), CS-2 (cadence `or` blocks a legit `0` confirmation-passes), CS-3 (load-path `is_configured` setdefault gap — mitigated by the BUG-A fix), CS-4 (4-key vs 5-key divergent `setup_progress` writers). |
| Profile Manager | [16](16-profile-manager.md) | ✅ audited 2026-07-28 (9 findings + 6 code flags) — built-ins/ID/CRUD/capability-gate were DR-grade; the shaper + run-profile serialization had gaps. Added §6.2 the full 12-key `get_effective_room_details` output (with the **renamed** `default_clean_passes`/`default_edge_mopping` + `selected_`vs`resolved_profile_name` traps), §6.3 the resolution precedence ladder (carpet overrides room fan/water; "room always wins" is only true for unconstrained hard-floor fields), §3.1 the 9-key stored room-profile record (path_type/mop_required always-defaulted), §5.5 `apply_room_profile`, §7.7 the `start_run_profile` signature/returns, §7.2 snapshot coercions + the `-1` sentinel, and the `from_room` return shapes/reasons. Fixed confidently-wrong: "`steps` written **only** by `set_run_profile_steps`" (also written by `save_run_profile` when the queue `has_breaks`), and `_match_profile_from_fields` "exactly match" (it's a **normalized** match vs a bare-`{profile_name}` candidate). **FIXED B1 (HIGH, real bug):** a plain vacuum room **never matched its vacuum preset** → always `profile_name="custom"` (protected room forces water `Off`; candidate resolved to hardwood water default `Low`) — corroborated by the PM-10 test comment. Fix: `_match_profile_from_fields` now resolves + protects each candidate under the room's `floor_type` (symmetric pipeline); +regression test PM-10b, full suite 2889 green. **B2–B6 also resolved:** B2 (custom profiles now derive `path_type` Deep→narrow + `mop_required` from mode, +test PM-2b), B3 (`ProfileRecord` TypedDict corrected to the real 9 keys), B4 (`apply_room_profile_to_config` now threads `catalog` into alias resolution), B5 (`apply_room_profile` id filter cleaned via `_safe_int`; the `*_from_room` `int(room_id)` is service-`Coerce`d so unreachable), B6 (documented benign: dispatch reads the persisted `path_type`, no re-sync needed). Full suite 2890 green. |
| Map Manager | [17](17-map-manager.md) | ✅ audited 2026-07-28 (8 findings + 4 code flags) — the pure-function signatures/return shapes (§3.1–3.5) were DR-grade; the **persisted room-record + summary serialization collapsed**. Added the full 22-field rebuilt room-record schema to §3.4 (exact types/defaults/coercions: `profile_name="vacuum_quick"`, `fan_speed="Max"`, `floor_type="hardwood"`, `path_type` no-coercion, list-guarded `grants_access_to`/`rules`) + the `discovered_rooms` input contract (`room_id`/`name` required, per-element `map_id` ignored — param wins) + both summary entry shapes. Flagged **BUG-B** in-doc: `rebuild_map_bucket` is the lone writer of the **reduced 4-key** summary entry vs the canonical **9-key** `build_room_selection_summary` (drops `profile_name`/`floor_type`/`clean_passes`/`edge_mopping`/`carpet` until a non-rebuild write repopulates). Fixed confidently-wrong `get_managed_maps_summary()` → **`get_vacuum_maps()`** (§5). Added the `is_configured`/`configured_at` provenance (entity-creation gate, BUG-A carry-forward), the co-resident `queue_breaks`/`learned_zones` keys + the `reconciled_at`/`reconciliation_dismissed_at` metadata keys, and the stale `image_variants` set (per-layout `custom_<id>` + furnished-art). Code flags: CS-2 (BUG-B fix = call the 9-key builder), CS-3 (`is_transition` not in `RoomConfig`), CS-4 (`configured_at` None-vs-`_iso_now()` asymmetry), CS-5 (possibly-dead `core/manager.py` imports). |
| Mapping | [11](11-mapping-system.md) | ✅ audited 2026-07-28 (11 findings + 3 code flags) — algorithm (§2.2–2.9 masks/clustering/splitting) was pristine; the CV/custom **serialization** collapsed. Added §2.12: the full ~27-field per-segment dict (exact rounding, `segment_id`=`"segment_{N}"`, `area_percent` 0–1/4dp, value sets for `structural_role`/`segmentation_state`/`variant_support`/`edit_readiness` with thresholds) + the *stored* `image_segments` envelope (`_reshape` hoists `segmentation`/`runtime` under `engine_diagnostics`, adds `engine`/`analyzed_at`) + the keyword-only detector signature. Fixed confidently-wrong: custom segments are **not** the identical CV shape — `_build_custom_segment` is reduced (omits ~10 metrics, `area_percent` 0–100/2dp, `center_pixel` 1dp, adds `source`), and the stored `custom_segments` envelope is reduced too (§10.4). Pinned the `polygon_pct` divisor to the store's own dims (§2.10), the adjust-time `bbox`/`center_pixel` rewrites + the map-bucket-vs-active-scope scope caveat (§5.2), the dead `"primary"` path clause (§6.1), and the two extra coordinator readers (§11.2). Flagged 3 code smells: stale canonical `SegmentationState`/`EditReadiness` Literals (don't match runtime values), the `updated.get("id")` adjust-log that always reads `"unknown"`, and the latent cross-scope adjustment collision. |
| *(all others)* | — | ⬜ reference-grade — pending audit against this standard |

Harden one subsystem per pass: walk §4/§5, fix the collapse zones, update this row.
