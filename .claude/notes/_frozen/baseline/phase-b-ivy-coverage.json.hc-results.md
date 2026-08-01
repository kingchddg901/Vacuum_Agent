# Hardware checkpoints HC-0..HC-2 — SATISFIED (Chris, 2026-08-01)

Deployed tree: wave-1 markers verified present (all 9 packets) at commit 6ab1b20,
deploy-live.ps1 -SkipBuild, HA restarted.

- **HC-0 (RP-001/RP-002, Ivy cancel×2, unfiltered recorder): "perfect"** — exactly
  ONE Auto-finalized and ONE Incomplete-run-log write per job. The before-capture
  (ivy-run-BEFORE.log) showed TWO of each for the same shape. HW-FINAL-1 /
  the reopened campaign CRIT is closed END-TO-END: hardware-proven broken →
  mechanism traced → repaired → hardware-proven fixed.
- **HC-1 (RP-003/RP-009): clean** — double reload, jobs finalize, entities survive
  a room edit (maintenance numbers intact — EP-2 closed on hardware).
- **HC-2 (RP-007, Ivy): clean** — normal dispatch unchanged; re-segment shape
  produces the refusal, not a wrong-room clean.

Post-repair dump: not yet attached (capture lives on the HA box; attach to
_frozen/baseline/ as ivy-run-AFTER.log when convenient — the before/after diff is
RP-001's ledger_closure_evidence).
