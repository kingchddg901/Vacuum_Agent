# Repair Dependency Graph & Implementation Sequence (§J)

> **⚠ SUPERSEDED IN PART BY REVIEW-03 (hostile self-review, 2026-08-01).** Execute
> against REVIEW-03's corrected edge set. Deltas: RP-008 ∥ RP-009 (ordering edge
> removed); **RP-013 → RP-013a..e** (split, order a→c→b/d/e); **RP-015 gains a
> stored-slug dedupe MIGRATION and RP-018 is blocked on it** (D5); RP-011 rebases on
> RP-002-as-amended; RP-013a → RP-021 (shared run_plan.py edits); RP-013c → RP-020;
> RP-026 has a fork-linkage verify-first gate. RP-007 additionally blocked on Q16.
> DEF-2 dissolved into RP-030.

Target commit `c61b3eb`. Waves are commit-ordered; packets within a wave are independent
unless noted. **Commits that must not be combined** are called out. Tier-2 hardware
checkpoints are batched **per device path** (§M2), not per family.

## Foundation ordering (why HW-FINAL-1 reorders the plan)

RF-01 (finalize window) is the root: every tier-2 validation run that reads learning
output is uninterpretable while the finalize body can run twice — a doubled ingest is
indistinguishable from a family's own regression. RF-16's INIT-1 (stale manager writes
over the live store after reload) is the second contaminant: any hardware pass that
reloads the entry mid-campaign can silently corrupt the store being measured. These two
land before ANY other packet is hardware-verified.

## Wave 0 — instrument + contaminant fixes (no behaviour change beyond the defects)

| Packet | Family | Content | Blocks |
|---|---|---|---|
| RP-001 | RF-01 | finalize claim window: gate written inside claim; release-on-failure-only | everything tier-2 |
| RP-002 | RF-01 | refusal-consumption at 3 sites (lifecycle, finalize service, stranded reaper) + `finalize_result_succeeded` | RP-010, RF-11 verif |
| RP-003 | RF-16 | manager.async_shutdown + entry.async_on_unload ledger + closed-flag on async_save (INIT-1) | all tier-1/2 passes |
| RP-004 | RF-33 | DR-DBG-1: redact+truncate exc_info in the flight recorder (the campaign instrument) | all capture-based evidence |

RP-001 and RP-002 are separate commits (chokepoint vs consumers). RP-003 must not be
combined with RP-001 (both touch finalize-adjacent paths; bisectability).

**Hardware checkpoint HC-0 (tier 2, Ivy + Alfred, lifecycle path):** reproduce the
cancel-and-dock flip on Ivy → finalize body exactly once; Alfred normal run → unchanged
single finalize. BASELINE: exists (ivy-run-BEFORE.log / alfred-run-BEFORE.log).

## Wave 1 — CRITICAL data-loss guards (source-decidable, tier 0)

| Packet | Family | Content |
|---|---|---|
| RP-005 | RF-02 | room-store wipe guard at room_crud chokepoints + enabled_room_ids null/absent distinction |
| RP-006 | RF-03 | read_json tri-state + RMW refusals (trouble_rooms, accuracy, caches, preload, segmenter store) |
| RP-007 | RF-08 | total-miss dispatch refusal + refresh result/freshness stamp (Roborock wrong-room CRITs) |
| RP-008 | RF-13 | path_blockers unavailable semantics (GUARD-1 CRIT) + edge dedup |
| RP-009 | RF-04 | entity-ownership classification (prefix → attribute/closed-set); registry sweep exactness |

Each its own commit. RP-005/RP-006 touch different layers of the same stores — do not combine.

**Hardware checkpoint HC-1 (tier 1):** deploy-live + reload ×2; entity list intact after
a room edit + a map delete (RP-009); no duplicate panels/services (RP-003).

## Wave 2 — lifecycle correctness (jobs/, listeners/, tracker)

Order inside wave: RP-010 → RP-011 → RP-012 (same files, sequential).

| Packet | Family | Content |
|---|---|---|
| RP-010 | RF-06 | cancel/pause chokepoint re-check; cancel single-flight; completion-gate _cancel_in_flight; start_zone_clean lifecycle gate |
| RP-011 | RF-07 | watchdog try/finally + pending_since reapability; reaper isolation; never-started reap arm |
| RP-012 | RF-31 | tracker release on every terminal path; recharge-end event-driven detection; sampler cadence/isolation |
| RP-013 | RF-11 | phased-run recording: phase-type validity, allocated group timing, cumulative completed set, frozen queue block, run_is_in_flight recorders |
| RP-014 | RF-12 | in-flight helper adoption (dock gate, job_progress, active_job sensor, listener sites) |

**Hardware checkpoint HC-2 (tier 2, one batch per device):**
- Alfred: stepped run (charge_wait + 2-room group) — **REQUIRES A NEW BEFORE-CAPTURE
  prior to RP-013 landing** (existing baseline is single-room; this is the one decaying
  item this synthesis adds). Cancel-during-dispatch run. App-started (external) run.
- Ivy: cancel + stepped run; needs wake + integration reload first
  (reference_roborock_idle_disconnect).

## Wave 3 — identity & stores

| Packet | Family | Content |
|---|---|---|
| RP-015 | RF-24 | slug uniqueness at discovery + tracker adopts slugify |
| RP-016 | RF-20 | per-map store registry; remove_map completeness; rename referrer scans; zone-id reuse |
| RP-017 | RF-25a | id-remap walker coverage over the registry (trouble_rooms, anchors, adjustments) + DR-ONB-1 two-dict remap |
| RP-018 | RF-25b | slug-led carry in build_managed_rooms + first-import vs incremental enable semantics (**Chris-flagged**) |
| RP-019 | RF-25c | reconciliation reachability: plan echo/token service contract (card wiring = downstream product work) |
| RP-020 | RF-22 | exclude/restore reach accumulators; cache invalidation parity; STATE-3/4 map scoping |

RP-015 → RP-018 strictly ordered. RP-016 before RP-017 (registry first).

## Wave 4 — dispatch/planning correctness

| Packet | Family | Content |
|---|---|---|
| RP-021 | RF-35 | engine envelope queue identity; collapse preserves groups; zone-first whole-plan validation + phase-0 type branch; trim removal (sequenced WITH validation fix); RP-2 overwrite preserves steps; apply/start step round-trip |
| RP-022 | RF-23 | cap resolution hoisted above coordinate branches; author-time zone checks; snapshot/dispatch/card single declaration |
| RP-023 | RF-26 + RF-27 | one reachability function; graph verdict; delta-scoped gate; issue codes (i18n) |
| RP-024 | RF-19 | precedence clamp reframe + match-candidate water key (custom-snap); granite/concrete defaults (**Chris value choice**); path_type None |
| RP-025 | RF-18 | catalog threading (after RP-024); literal purge; declared-empty honored; ROOMS-6/9 vocabulary validation |

**Hardware checkpoint HC-3 (tier 2):** Alfred zone clean (cap clamp); Ivy stepped order
run + profile apply → stored-room inspection (no "Quick"/"Off" acquisition).

## Wave 5 — mapping subsystem

| Packet | Family | Content |
|---|---|---|
| RP-026 | RF-09 | device+map binding (Eufy coordinator selection, Roborock scoping); version covers served content |
| RP-027 | RF-10 | stale-hold consumer split; live-pose geometry repoint (memory-primary) |
| RP-028 | RF-15 | require_map_bucket adoption; resolved_call_data in mapping_services; managed-vacuum checks; CUSTOM-1 layout_id |
| RP-029 | zone-safety batch | ZONE-C-1/C-3/C-4 + CUSTOM-3/4 (map_version stamp, indeterminate refuses); POLYGO-1 growth; POLYGO-3 by-reference |
| RP-030 | mapping small batch | GEO-3/4/5/6, EXT-3/4, RB-7/8, POSE-7, ROBORO-1/5/6/7, FURNIS-3/5/6 |

RP-026 before RP-027 (identity before freshness; same files).

**Hardware checkpoint HC-4 (tier 2, both devices):** live-map runs; two-Eufy case
(Alfred + Omni E28) for RF-09 if Chris runs both — otherwise RF-09 multi-device closure
stays `HARDWARE_BASELINE_GATE unsatisfied` and closes on the single-device regression +
source review.

## Wave 6 — service surface & platform

| Packet | Family | Content |
|---|---|---|
| RP-031 | RF-14 + RF-05 | per-module refusal/ordering pass (job_control, rooms, run_profiles, setup, maintenance/dock, learning services, themes services) — one packet per module, commits per concern |
| RP-032 | RF-28 | the declaration-parity gate test + content fixes to green |
| RP-033 | RF-32 | adapter-config full-contract validation; delete restores code adapter; engine-template required |
| RP-034 | RF-17 | themes packets (overwrite source, provenance/tombstones, draft lifecycle, notify parity, import key validation) |
| RP-035 | RF-34 | SN-1 sensor creation path; platform batch; options-flow replace semantics |
| RP-036 | RF-21 | estimator batch |
| RP-037 | RF-29 | loop-hygiene batch (SNAP-2 memoize+hoist rides RP-013's progress-path knowledge) |
| RP-038 | RF-30 | dock-events edge semantics |
| RP-039 | RF-33 rest | debug/diagnostics remainder |
| RP-040 | batches | SMALL-CORRECTNESS (+-2), DEAD-CODE, DOC-ONLY |

**Hardware checkpoint HC-5 (tier 1):** card walk-through (profiles, themes, graph
editor, zones) after deploy-live; **tier 2 ride-along:** mop-wash cycle (RF-30),
ETA observation (RF-21) on the HC-2/HC-3 runs' captures.

## Frontend consumer nodes (§J requirement — NOT closed by backend packets)

| Carried item | Unblocked by |
|---|---|
| CF-5 two failure-renders-as-success paths | RP-031 (supports_response/raise on the named services) |
| CF-7 surface captured run errors | independent — schedulable any time |
| CF-6 qualification gap (stale/provenance display) | RP-027 (stale contract), RP-013 (allocated flags) |
| CF-4 three untranslated card strings | independent |
| STATE-4 card map-scoping (retryMissedRooms) | RP-020 (backend scoping) — card must check log.map_id |
| AGX-6 dock-room "Missing Room N" | RP-023 |
| CF-9 Roborock edge-mopping control removal | independent (verify intent with Chris — reconstructed note) |
| CF-8 OpenDyslexic | independent (own plan) |

## Obsolescence notes (findings later packets may find pre-closed)
- RP-013's cumulative-completed set may partially resolve A4-STATE-1/STATE-2 before
  RP-020 lands — closure evidence still per finding (§L).
- RP-032's gate will re-detect any RP-031 schema drift — run gate after RP-031, fix, freeze.

## Commit discipline
- One packet = one or more commits; NEVER combine packets across families in a commit.
- Gate per commit: `pytest tests --no-cov` + frontend gates when src/ touched; mkdocs
  --strict when docs touched.
- Deploy-live only at hardware checkpoints (release⇒deploy coupling applies at tags).
