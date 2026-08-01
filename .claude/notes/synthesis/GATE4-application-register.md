# GATE 4 — Decision Application Register

Maps each Q1–Q17 decision (GATE4-decisions-q1-q17.md — verbatim authority; do not
reinterpret) onto the synthesis artifacts. Product semantics stop at the decisions;
implementation agents consume THIS register plus the amended packets.

| Q | Decision (short) | Applied to | Status |
|---|---|---|---|
| Q1 | refuse on `_stored_job is None` (`no_active_job_record`) | RP-001 step 3 rewritten; regression added | **APPLIED** |
| Q2 | uniform precedence + explicit safety clamps | RP-024 (RF-19): variant (a) SELECTED — clamp-after-resolution; drop the (b) fork | governs authoring |
| Q3 | granite/concrete = brand hard-floor default (tile/marble value); never ""/None/forced-off | RP-024 value choice pinned | governs authoring |
| Q4 | `_r{room_id}` suffix, collisions only; migration writes a before/after MANIFEST; rollback restores from manifest (never strip-suffix inference) | RP-015 + its D5 dedupe migration — manifest requirement is STRONGER than the review spec'd; adopt verbatim (yaml fields per decision doc) | governs authoring |
| Q5 | first import: enable all; incremental: disabled+unconfirmed; never silently queue new rooms | RP-018/RF-25 semantics pinned (matches synthesis proposal) | governs authoring |
| Q6 | ADD a trouble_rooms rebuilder for stale markers (map-scoped), keep live path | RP-020/RF-22: STATE-5 disposition upgraded from "reopen question" to ACCEPTED — rebuilder from archived evidence joins async_rebuild_learning_accumulators' scope | governs authoring |
| Q7 | overwrite_theme = DRAFT-OVER-TARGET (full fix); refuse when draft/target unresolvable; never active-as-source; never empty overwrite; provenance preserved; draft state recomputed | RP-034/RF-17: the FULL variant is selected, minimal variant dropped | governs authoring |
| Q8 | delete repairs.py dead flow | DEAD-CODE batch (RP-040): INF-6 disposition = delete | governs authoring |
| Q9 | class-based failure convention: operational/automation-common → structured `success:false` responses; ServiceValidationError for caller error; HomeAssistantError for internal failure on admin/destructive; flags not reason-strings | RP-031/RF-14 convention table SETTLED — author packets directly against this taxonomy | governs authoring |
| Q10 | reject_rooms: map-scoped + protection/confirmation parity + un-reject service | RP-040 (A4-SETUP-6) scope confirmed | governs authoring |
| Q11 | CF-9 edge-mopping removal is Roborock-only, capability-declaration-driven; audit for scope creep | carried frontend item CF-9 (card packet) — reconstruction VERIFIED by decision | governs card work |
| Q12 | Eufy zone repeats UNSUPPORTED + unsurfaced: adapter omits/declares unsupported; card hides repeat control; backend rejects/normalizes clean_times>1 on Eufy zones | RP-022/RF-23 RESHAPED: DQ-ZONE-1's fix is normalize-to-1 + declaration, NOT clamp-to-2; DQ-PAY-4's "which default" question dissolves; card consumer named | governs authoring — **supersedes the packet sketch's clamp-to-2** |
| Q13 | **NO Omni E28 in fleet — inventory error.** RF-09 multi-Eufy: source + single-device regression; multi-device proof open; no fabricated closure | SYNTH-01a, SYNTH-05 HC-4, REVIEW-05 corrected; SESSION_HANDOFF §0 corrected | **APPLIED** |
| Q14 | mid-job recharge: deterministic simulation + production-listener parity; hardware optional unless parity fails | RP-012/RF-31 (A4-AJ-1/TRK-2) closure path pinned | governs authoring |
| Q15 | orphan registry entries: report-only; exact cleanup only when ownership reconstructible; unknowns untouched | RP-009 step 4 (already amended per D3) — CONFIRMED | **APPLIED** (matches amended text) |
| Q16 | refuse-until-awake; no stored-id wake dispatch; actionable user-visible reason; normal dispatch after live refresh succeeds | RP-007 step 7 rewritten to variant (a); packet UNBLOCKED | **APPLIED** |
| Q17 | leading charge_wait UNSUPPORTED — no non-clean phase-0 state machine; reject or explicitly normalize at plan VALIDATION; card must not display it as executable; zone-first proceeds | RP-021/RF-35 RESHAPED: replace the silent trim with validation-time rejection/normalization + card honesty (named card consumer); A5-PP-RP-5's disposition becomes "explicit refusal/normalization", not trim-removal | governs authoring — **supersedes the trim-removal sketch** |
| Q18 | *(2026-08-01, answered to the main agent)* RP-008 escalation DISCHARGED **on facts, not principle**: Chris has zero automations and no rule matches `unavailable`. He explicitly did NOT rule the semantics out — his counter-example: *"office occupied=true=block, false=allow, unavailable=block is a possible setting"* — i.e. **fail-closed on ignorance is a coherent authored policy** (and is accidentally expressible today: `not_equals` matches `unavailable` by side effect, which is exactly why this escalation question existed). Resolution: hold-previous ships as the DEFAULT because the bug is a dropout firing an irreversible ACTION (cancel); a conservative block differs from a cancel. Post-repair, sentinel-matching rules go dead — record this as a KNOWN LIMITATION, not a principle: if fail-closed is ever wanted, the shape is an explicit per-rule `when_unavailable: block/allow/hold` field (future feature, opt-in, NOT RP-008's scope — do not foreclose it, and do not reintroduce string-matching on sentinels to get it). | RP-008 `stop_and_escalate` DISCHARGED — Sonnet does not stop for it; the execution-time doc-grep remains as belt-and-braces | **APPLIED** |

| Q19 | *(2026-08-01, in-session)* **AG-2 semantics CONFIRMED: warning.** Unconfigured room (no inbound edge) = per-room warning + that room excluded from graph-gated runs; NOT a map-wide block. | RP-023's pre-assignment stop_condition DISCHARGED | **APPLIED** |
| Q20 | *(2026-08-01, in-session)* **PRE-1 CONFIRMED WITH REFINEMENT: an error state blocks start ONLY when the fault is relevant to the job being started** — Chris verbatim: "yes as long as that error is part of the job. no water for a vac job is invalid for instance." A water-class fault must not block a vacuum-only job; it blocks jobs that mop. Relevance defaults: unmapped/unclassifiable faults are relevant to ALL jobs (conservative — stuck/wheel/battery-class faults prevent any run); the IRRELEVANT set is the narrow, adapter-declared one. | PRE-1 EJECTED from RP-040 into new packet **RP-041** (design, not a one-liner — per RP-040's own ejection rule) | **APPLIED** |

## Packet-state after Gate 4

- **Waves 0–1 fully unblocked:** RP-001..RP-006, RP-008, RP-009 amended+decided;
  RP-007 unblocked by Q16. Remaining precondition: the five reproducers materialized
  and observed failing on frozen source (main agent), per REVIEW-04.
- **Tranche-2 authoring inputs complete:** every product fork that blocked packet
  authoring (Q2/Q3/Q4/Q5/Q6/Q7/Q9/Q12/Q17) is now decided. RP-013a..e split and the
  REVIEW-03 edge set apply.
- **Two packet sketches materially superseded** (Q12 zone-repeat, Q17 charge_wait) —
  tranche-2 authors MUST start from this register, not from the RF-23/RF-35
  catalogue sketches alone.
