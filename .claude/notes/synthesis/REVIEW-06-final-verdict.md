# REVIEW-06 — Final verdict

## Verdict: **APPROVE WITH NAMED AMENDMENTS**

The synthesis is structurally sound: reconciliation closes at 484/484 with single
owners; 30 of 33 families upheld unamended; the rejected-family register survived
re-attack; the anti-migration decision on RF-04 survived a targeted attempt to break
it and is now stronger (D3 makes the residual-orphan trade explicit instead of
implicit).

The review found **real defects** — none invalidates a family, five change packets or
dependencies:

| # | Severity for the program | Defect | Fix location |
|---|---|---|---|
| D1 | HIGH | RP-002 refusal handling loops the reaper forever on `already_finalized` | REVIEW-02/RF-01 amendment |
| D5 | HIGH | Stored duplicate slugs make RP-018's slug-led carry reintroduce REC-2; migration missing | RP-015 + new edge |
| D4 | MEDIUM | RP-006's uncached UNREADABLE hot-loops blocking reads during SMB outages | RP-006 amendment |
| D6 | MEDIUM | RF-35 trim removal presumes non-clean phase-0 support that does not exist | RP-021 restructure + Q17 |
| D14 | MEDIUM | RP-013 too large for one Sonnet packet | split a..e |
| D2/D3 | MEDIUM | RP-009 private-attr access; closed-set sweep leaks pre-fix orphans | RP-009 amendments + Q15 |
| D7 | LOW | DEF-2 deferral/ownership contradiction | matrix corrected |
| D8/D11 | LOW | RP-001 crash-window residual note; HC record template missing | notes + register template |

## Conditions required before implementation authorization (Gate 4)

1. Amendments D1, D2, D3, D4 applied to the four affected packet texts (REVIEW-02
   contains the exact amendment language; mechanical edit).
2. RP-013 split into a..e and RP-021 restructured per D6 during tranche-2 authoring.
3. The five new reproducers materialized by the main agent and observed to fail on
   frozen source for the intended reason (Pass-6 rule 7) before their packets are
   assigned.
4. Chris answers the consolidated question list — Q1–Q17 (SYNTH-05 + REVIEW-05).
   Blocking subset for Wave 0/1 only: **Q1 (stored-job None), Q16 (wake-by-dispatch)**;
   all others gate later waves.
5. The corrected dependency graph (REVIEW-03) supersedes SYNTH-02's edges.
6. HC captures adopt the Pass-8 record template (D11).

## What did NOT survive the review unchanged
- SYNTH-02's edge set (two edges added materially: D5 migration, RP-002→RP-011;
  one removed).
- The claim that all nine tranche-1 packets were execution-ready (four need
  amendment; two additionally gated on Chris answers).
- DEF-2 as a deferral.

## What survived hostile attack and is now higher-confidence
- RF-01's fix shape (the D1 interaction analysis shows RP-001+RP-002-amended is
  self-healing across the crash window).
- RF-04's no-migration disposition (attacked on legacy ids, offline entities,
  hidden consumers; held, with the orphan trade made explicit).
- The rejected-family register (all six re-attacked; none resurrected).
- The killed-lookalike boundaries on RF-18 (all 29 members re-checked against the
  RoomConfig rule; none rests on a dead premise).

This is not an endorsement of the synthesis because it was mine; it is an approval
because the reconciliation is machine-checked, the amendments are enumerated and
bounded, and every remaining unknown is routed to its authority (Chris for product,
reproduction for code behaviour, hardware gates for empirical claims).
