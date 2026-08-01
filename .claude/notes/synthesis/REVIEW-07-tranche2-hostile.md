# REVIEW-07 — Hostile review of the tranche-2 packet set (RP-010..RP-041)

Reviewer = author, adversarial stance. Method: scripted reconciliation against
closure-matrix.json + tranche-1's 40 closed findings, then design attack on the
high-risk packets. **Amendment language here is AUTHORITATIVE over the packet
texts** (as REVIEW-02 was for tranche 1) until folded in.

## Verdict: **APPROVE WITH NAMED AMENDMENTS** — 30/37 packets clean; 7 need
amendment; 0 need return-to-synthesis.

---

## Pass 1 — Reconciliation (scripted)

- 395 explicit finding assignments in tranche-2 packet lists; 0 overlap with
  tranche-1's 40 closed.
- **T2-D1 (ownership dups, 4):** pinned — `#16:A4-STATE-3` → **RP-020** (RP-017
  lists it findings_not_closed: walker half only); `#13:A6-DIAG-6` → **RP-028**
  (RP-031: response-class half, not_closed); `#13:A2-JOB-5` + `#13:A2-JOB-6` →
  **RP-032** (removed from RP-031's list — the round-trip/cross-field fixes ARE
  gate content).
- **T2-D2 (uncovered findings, 6 genuine after excluding parser artifacts*):**
  - `#14:A3-SNAP-3` (RF-01 read-side, promised "later packet" in RP-001/002 and
    never assigned) → **RP-037** (same function as SNAP-2's purity work: the
    snapshot reads the finalize claim / finalized flag and reports "finishing",
    withholding Pause/Cancel during the window).
  - `#12:A3-COMMON-1` (HIGH), `#14:A3-SNAP-1`, `SN-2`+`DR-MNT-1` (HIGH cluster),
    `#12:A3-COMMON-3`, `#12:A4-POSE-3`, `INF-4` — the RF-13 remainder was parked
    in RP-040's PROSE (two HIGHs in a closing batch, against my own rigor rule)
    → **all move into RP-041**, which becomes the full "RF-13 remainder:
    indeterminate semantics" packet (job_active missing→active when
    unavailable_is_active; mop_active tri-state; maintenance source_available
    honest on missing usage_hours + unreachable invalid_usage_hours; docstring
    truth for COMMON-3; _is_parked fallback; BLANK_STATE_VALUES consolidation).
  - `#7:DQ-ACT-6` → formally into **RP-031**'s finding_ids with disposition
    wontfix-pending-Chris-ack (was prose only).
  - `#8:A5-PP-RP-2` (same zone-first defect, audit-#8 flavour) → **RP-021a**.
  - `#18:A4-CUSTOM-2` (throwaway-dict writers) → **RP-028** (the
    _ensure_default_layout wiring belongs with addressing); `#18:A3-IMAGE--8` →
    **RP-029** (response-honesty group).
  *Parser artifacts (line-wrapped YAML strings, verified assigned): SN-4, SN-9,
  EP-4, EP-7 (RP-035); INF-5 (tranche-1 RP-009 document-only rider).

## Pass 2/3 — Design attack (defects found)

- **T2-D3 (HIGH — RP-026 would regress working single-device installs):** if the
  vacuum↔fork device linkage fails to resolve, the packet returns
  device_not_found ABSENT — but today's first-coordinator behaviour WORKS on
  single-device installs (Alfred). AMEND RP-026(1): when a root holds exactly ONE
  coordinator, select it (DEBUG note) regardless of linkage match; the
  no-match-absent rule applies only to MULTI-coordinator roots. Single-device
  regression risk eliminated; multi-device correctness kept.
- **T2-D4 (HIGH — RP-019's rename slug_remap is under-designed):** learning
  stores key on map_id::slug INSIDE files, and ARCHIVES carry the old slug — a
  rebuild regenerates old-slug keys, so a dict-walker "remap" cannot close REC-6.
  AMEND RP-019(2): adopt a persisted `slug_aliases` map (old→new per map),
  consulted by the stats rebuilder and the estimator's room-match lookups;
  archives are NOT rewritten (rejected: heavy, destructive); the walker/registry
  route is struck for slug-keyed stores. Reproducer gains a rename→rebuild→
  estimate round-trip case.
- **T2-D5 (MEDIUM — RP-035's SN-4 fix would stomp user customizations):**
  registry.async_update_entity(name=...) writes a USER-override name — future
  translation updates stop applying and we cannot distinguish our write from the
  user's. AMEND: on room rename, REMOVE+RE-ADD the entity object with fresh
  translation placeholders under the SAME unique_id (registry entry persists;
  a user's own name override then legitimately wins). The discarded-rebuilt-
  entity path in the sync helper becomes the mechanism.
- **T2-D6 (MEDIUM — RP-013e ambiguity):** "write only into in-flight buckets" is
  underspecified when MULTIPLE buckets qualify (stale slots exist until RP-011
  beds in). AMEND: when >1 bucket qualifies, write the one matching
  resolve_active_map_id, else newest started_at, and WARN once per job — never
  fan out.
- **T2-D7 (MEDIUM — missing edge):** RP-021b and RP-031 edit the same
  apply/start symbols (profiles/manager.py). ADD EDGE RP-021b → RP-031 (RP-031's
  05a reorder rebases on the landed RP-021b).
- **T2-D8 (LOW — release-note gap):** RP-021a's per-group phases mean a
  multi-group no-breaks plan now runs as SEQUENTIAL dispatches with
  dock-returns between groups (was one merged dispatch) — correct per the stepped
  design, but a visible duration/behaviour change; add to the release-notes
  register.
- **T2-D9 (LOW — RP-041 cross-ref):** the external_run_in_progress busy reason
  should cite audit #3's proven "Start during an external run destroys the
  capture" as its consequence anchor (strengthens closure evidence).

## Pass 4/5 sweeps
- Edges re-checked incl. new ones: no cycles (all forward-wave).
- Executability spot-check: RP-031's per-handler table and RP-040's generated
  per-file table are the two packets whose CONTENT is produced at execution time
  — both state the generation rule; acceptable (matrix/AST-driven, not judgment).
- Reproducer specs: 20 new proofs named across tranche 2; all follow the flip
  convention; RP-032's gate is self-proving. Materialization gate unchanged.

## Conditions before Wave-2 assignment
1. Fold T2-D1/D2 ownership+membership edits and T2-D3/D4/D5/D6 amendment text
   into the packet files (mechanical; language above is exact).
2. REVIEW-03 edge set + T2-D7's edge govern sequencing.
3. Chris ack at RP-031 review: DQ-ACT-6 wontfix (best-effort restore + log).
4. Materialize Wave-2 proofs against current master; verify each fails for the
   intended reason.

**What survived attack:** the wave partition, the Q-decision applications
(re-checked verbatim against the register), the 013/021 splits, RP-039's RF-16
recovery, and the no-double-assignment property. The uncovered-findings miss
(T2-D2) is the reviewer's honest catch: prose is not ownership — only a
finding_ids entry is.
