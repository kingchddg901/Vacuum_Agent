# REVIEW-04 — Packet readiness (Passes 5, 6)

Standard applied: Sonnet has never seen the corpus; every product/design decision must
already be made in the packet. The review's required field set differs from the
authored §K layout — fields present-under-other-names are counted, genuinely missing
ones listed.

```yaml
- packet_id: RP-001
  ready_for_sonnet: yes, after header amendment
  missing_fields: [problem/root_cause as explicit keys (content in goal/violated_invariant),
    exact_match_rules (implied by expected_* fragments — make explicit),
    escalation_target (add: main agent → Chris)]
  reproducer_status: SPEC ONLY — _proof_finalize_window.py must be materialized by the
    main agent and RUN AGAINST FROZEN SOURCE to prove it fails for the intended reason
    (Pass 6 rule 7) BEFORE assignment. Class: unit-safe (asyncio, in-memory).
  migration_status: none required — verified (per-job dict field, both directions tolerated)
  rollback_status: adequate (single revert)
  hardware_status: HC-0 defined; baseline exists
  blocked_by: [reproducer materialization]
- packet_id: RP-002
  ready_for_sonnet: NO until amended per D1 (already_finalized → mark slot with
    finalize_result=None; finalize_in_flight → leave). Amendment text in REVIEW-02.
  missing_fields: [escalation_target, exact_match_rules]
  reproducer_status: extension of _proof_finalize_window — same materialization gate
  blocked_by: [D1 amendment, RP-001]
- packet_id: RP-003
  ready_for_sonnet: yes with one addition — the ledger inventory step must emit the
    list of UNLEDGERED spawn sites it finds (stop condition already present)
  reproducer_status: SPEC ONLY (_proof_manager_reload.py); class unit-safe
  migration_status: none — additive seam, verified
  rollback_status: adequate
  blocked_by: [reproducer materialization]
- packet_id: RP-004
  ready_for_sonnet: yes
  reproducer_status: reproducer pattern PROVEN in the original record (executed);
    materialization trivial; class unit-safe
  blocked_by: []
- packet_id: RP-005
  ready_for_sonnet: yes
  reproducer_status: attaches EXISTING _proof_setup.py (verified present in
    .claude/notes per plan §7.1 artifact list) + new schema-null case; class unit-safe
  migration_status: none — schema tightening only; REJECTED "no migration" challenge:
    no persisted identifier changes
  rollback_status: adequate
  blocked_by: []
- packet_id: RP-006
  ready_for_sonnet: NO until amended per D4 (UNREADABLE cached with 60s backoff, not
    uncached). Amendment text in REVIEW-02.
  reproducer_status: SPEC ONLY (_proof_rmw_conflation.py); class integration-safe
    (touches temp files); step-8's live-snapshot clear needs a fixture-level test only
  blocked_by: [D4 amendment]
- packet_id: RP-007
  ready_for_sonnet: NO until amended per RF-08's wake-by-dispatch question (Q16) —
    the packet currently refuses a dispatch the shipped product may rely on to wake a
    sleeping Roborock. Chris answers Q16 first.
  reproducer_status: SPEC ONLY (_proof_stale_dispatch.py); class unit-safe
  hardware_status: HC-2 Ivy leg; BEFORE-capture for the dispatch path wanted
  blocked_by: [Q16, reproducer materialization]
- packet_id: RP-008
  ready_for_sonnet: yes (hold-previous semantics fully pinned)
  reproducer_status: SPEC ONLY (_proof_blocker_unavailable.py); class unit-safe
  blocked_by: [Chris check: no shipped automation matches unavailable deliberately
    (stop condition present — downgrade to execution-time check)]
- packet_id: RP-009
  ready_for_sonnet: NO until amended per D2 (public properties, not private attrs)
    and D3 (closed-set + report-residue semantics). Amendment text in REVIEW-02.
  reproducer_status: attaches EXISTING _proof_setup.py (DR-SETUP-1's proven harness)
    + EP-2 extension; class unit-safe/integration-safe
  migration_status: "no migration" UPHELD after Pass-9 challenge — every current
    identifier form accounted for; PRE-EXISTING orphans handled by report-not-delete
    (D3), which is precisely the Pass-9 rule against reconstructing overwritten data
    in reverse: never delete what you cannot re-derive.
  blocked_by: [D2+D3 amendments]
```

## Pass 6 — reproducer integrity notes
- The five NEW proofs are specifications, not artifacts. Per Pass-6 rule 7, each must
  be executed against frozen source and observed to fail FOR THE INTENDED REASON
  before its packet is assigned. This is the main agent's materialization step; the
  packets' validity_notes already encode the anti-simplification traps (notably
  RP-001's "task B must run after task A fully returns" — the trap that would
  otherwise make the proof pass pre-repair for the wrong reason).
- EXISTING artifacts attached (not recreated): `_proof_setup.py` (RP-005, RP-009).
  `_proof_battery.py` remains the cautionary example; nothing in tranche 1 touches it.
- Classes recorded above; none are destructive; none require live HA.

## Tranche-2 packets
Not yet authored (by design). RP-013 split into a..e per D14 before authoring.
RP-026 carries the fork-linkage verify-first gate (REVIEW-02/RF-09).
