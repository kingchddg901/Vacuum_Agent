# Tranche-2 authoring inputs — execution feedback from tranche 1

**For the Fable authoring session, 2026-08-01.** Tranche 1 (RP-001..RP-009) is
executed, gate-green (3056/1), CI-green, deployed, and hardware-validated
(HC-0..HC-2 satisfied by Chris; HW-FINAL-1 closed end-to-end). These are the
lessons the EXECUTION surfaced that should shape how tranche-2 packets are
WRITTEN. Everything else you need is in the existing registers.

## Read order (authoritative set)

1. `GATE4-application-register.md` — Q1..Q18 (Q18 added post-Gate-4: RP-008's
   unavailable escalation, discharged on facts with the fail-closed future-shape
   recorded)
2. `GATE4-decisions-q1-q17.md` — verbatim authority under the register
3. `SYNTH-01a` / `SYNTH-01b` + `closure-matrix.json` — the family catalogue and
   who closes what (RP-013 pre-split a..e per D14)
4. `REVIEW-02` (family verdicts + amendment texts) and `REVIEW-03` (the corrected
   dependency graph — supersedes SYNTH-02's edges)
5. `MATERIALIZATION-01-reproducers.md` — reproducer conventions + the
   PYTHONPATH invocation note
6. THIS file — execution feedback

## What execution taught (fold into packet authoring)

1. **files_allowed_to_change must include amendment-implied files.** RP-009's D2
   amendment placed properties on the shared base entity (`room_entities.py`) but
   files_allowed was never updated — the executor had to adjudicate the conflict
   mid-packet. When an amendment names a symbol location, list its file.
2. **Superseded tests are a first-class packet output.** Four existing tests
   asserted the OLD design (LID-4/LID-6 stored-id fallbacks, AG-12
   missing-matches-absent, SD-10 prefix sweep). Where a packet knowingly changes
   an asserted contract, NAME the test(s) it supersedes and require the decision
   be recorded in the updated docstring. Distinguish this from
   fixture-asserting-fiction (fix fixture, never weaken assertion) — different
   category, different treatment.
3. **Card halves are real halves.** RP-005's escalation produced a card guard +
   an i18n key in en.js + ALL 17 locale packs (per-locale Delete-Map term
   embedded). Any tranche-2 packet whose refusal/reason reaches the card should
   budget the card consumer + i18n work explicitly (or name the follow-on card
   packet), not discover it at escalation time. Locale mechanics: nested JSON in
   `custom_components/eufy_vacuum/frontend/locales/*.json`, insertion must be
   order-preserving, `npm run check:i18n` is the gate.
4. **Rollback-group staging is easy to fumble.** RP-007's pre-call fix rode into
   commit 2/3 because both edits touched dispatch/manager.py. When two rollback
   groups share a file, say so in the packet and order the groups so the split is
   mechanical.
5. **Proof scripts print state-dependent outcomes.** The flip convention worked
   perfectly (same command before/after; output diff = closure evidence). Keep
   requiring `expected_before`/`expected_after` with exact fragments; keep the
   UNEXPECTED-SHAPE exit-1 arm.
6. **The `_stored_job is None` else-branch is still open** (noted in HW-FINAL-1's
   corpus record) — RP-002's refusal covers the finalize entry, but the
   structural no-else hole at learning/manager.py's claim block was explicitly
   left for a later packet. Make sure a tranche-2 packet owns it (RF-01 family).
7. **Ledger closure marking is pending for tranche 1's ~40 findings** — a
   tranche-2-adjacent chore, not an authoring input, but the closure-matrix
   consumer should not double-assign those findings.

## Boundaries unchanged

Fable emits packet content only — no repo edits. Main agent materializes
reproducers and validates them failing on frozen source before assignment.
Executor runs packets in order with per-packet full gates. Chris adjudicates
escalations. Severity rubric (plan §5) remains frozen. Hardware tiers per
`TASK-synthesis-pass-design.md` §M2; the Eufy+Ivy baselines and the HC pattern
from tranche 1 are the template.
