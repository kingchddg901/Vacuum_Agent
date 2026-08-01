# REVIEW-03 — Dependency graph corrections (Pass 4)

## Edge classification of the existing graph

| Edge | Class | Verdict |
|---|---|---|
| RP-001/003/004 → all tier-2 | test-interpretability prerequisite | REAL (double-finalize + stale-manager writes + unredacted dumps contaminate evidence) |
| RP-001 → RP-002 | semantic (helper + contract) | REAL |
| RP-002 before RP-010 | semantic (refusal contract consumed by cancel paths) | REAL |
| RP-005 vs RP-006 same-wave independence | claimed independent | **CONFIRMED** — disjoint files after re-check (room_crud/services vs learning stores/core preload) |
| RP-007 → RP-003 (cache invalidation via ledger) | semantic | REAL, correctly ordered (Wave 0 before Wave 1) |
| RP-009 ← RP-008 ordering within wave | administrative only | **REMOVED** — no shared files; RP-008 and RP-009 may run in parallel |
| RP-010 → RP-011 → RP-012 | source-conflict ordering (same files) | REAL |
| RP-013 → RP-001 | test-interpretability | REAL |
| RP-015 → RP-018 | semantic | REAL, **STRENGTHENED by D5**: RP-018 now `blocked_by: RP-015 INCLUDING its new stored-slug dedupe migration` |
| RP-016 → RP-017 | semantic (registry first) | REAL |
| RP-024 → RP-025 | source-conflict + semantic | REAL |
| RP-026 → RP-027 | source-conflict (same files) | REAL |
| RP-031 → RP-032 | generated-artifact ordering (gate after content) | REAL |
| RP-033 → RF-16 (RP-003) | semantic (registration lifecycle) | REAL |
| RP-037 (SNAP-2) → RP-013 | semantic (progress-path knowledge) | REAL — now specifically → RP-013c (rollover hoist) |

## Added edges (missing dependencies found)

1. **RP-015(migration) → RP-018** (D5) — migration prerequisite, new.
2. **RP-013c → RP-020** (STATE-3/4 map-scoping consumes the cumulative set's
   semantics) — semantic, new.
3. **RP-002(amended D1) → RP-011** (reaper refusal branching is consumed by the
   reaper-isolation packet; avoid conflicting edits to
   async_finalize_stranded_job) — source-conflict, new: RP-011 must rebase on
   RP-002's amended version of that function.
4. **RP-026(verify-first step) → RP-026 body** — internal gate (fork linkage
   verification precedes Sonnet assignment; failure returns the Eufy half to
   synthesis).
5. **RP-021(zone-first fix) ↔ RP-013a** share `step_types` import work — same-file
   touch in run_plan.py; ordered RP-013a → RP-021 (source-conflict).

## Removed edges
- RP-008 → RP-009 wave-internal ordering (administrative; parallelizable).
- DEF-2 as a scheduling node (dissolved per REVIEW-01 D7; ROBORO-1/5/6/7 → RP-030).

## Cycles
None found after corrections (spot-verified the new edges do not close a loop:
RP-013a→RP-021, RP-013c→RP-020, RP-015→RP-018 are all forward-wave).

## Packet-before-source-of-truth check
- RP-013b (allocated timing) consumes ACC-6's `single_room` accuracy semantics —
  source of truth (the flag) already exists; RP-036 (estimator consumption) correctly
  AFTER RP-013b. ✔
- RP-030's zone-safety batch stamps `map_version` (ZONE-C-3) — consumed by nothing
  earlier. ✔

## Revised wave impact
Waves unchanged except: RP-013 → RP-013a..e (Wave 2 grows by four packet slots,
wall-clock roughly unchanged — they were always sequential edits); RP-008 ∥ RP-009
recovers parallelism in Wave 1.
