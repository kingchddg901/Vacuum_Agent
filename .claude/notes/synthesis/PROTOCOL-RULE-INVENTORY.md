# Rule Inventory: v1 → v2 mapping

Walks `PROTOCOL-dr-prose-ablation.md` v1 (888 lines, core doc + all appended amendments)
top to bottom. Every normative rule is mapped to its single v2 location. "Restated
elsewhere?" is "no" unless noted; "cross-ref only" marks locations where v2 deliberately
keeps a short pointer back to the governing statement rather than a second full
restatement. Two rows marked **cross-ref only — protected structure** are the
Delayed-Scoring and Operational-Invariants summary sections: instruction 5 explicitly
keeps these two sections intact as original core-doc structure, so they are treated as
sanctioned indexes back to the per-role/per-topic sections that state the full rule, not
as independent duplicate sources of truth.

| # | v1 rule (paraphrased) | v1 location(s) | v2 location | Restated elsewhere? |
|---|---|---|---|---|
| 1 | Ablation distinguishes historical/repetitive prose from load-bearing meaning; process repeats until reduction removes needed info | Purpose | Purpose | no |
| 2 | Core question: how much can be removed while a blind implementer still reconstructs a passing system; disaster-recovery test, not consistency review; builder can't recover missing info from existing implementation | Core Question | Core Question | no |
| 3 | Four roles, deliberately conflicting incentives; credit only on chain closure; "red produces evidence, green closes the proof" | The Four-Agent Loop | The Four-Agent Loop | no |
| 4 | Trim agent context access (DR section, implementation, dev docs, audit record, tests, contracts) | § Trim Agent | § 1. Trim Agent | no |
| 5 | Trim agent may: remove narrative/superseded reasoning/repeats, replace histories with invariant, remove archaeology, rewrite for precision, preserve boundary conditions | § Trim Agent | § 1. Trim Agent, "It may" list | no |
| 6 | Trim agent may also make corrective/clarifying additions where original is wrong/silent/ambiguous; required, not optional, to fix a known falsehood | AMENDMENT (CAL-23 R1 + Chris ruling, 2026-08-07) | § 1. Trim Agent, "It may" list (last bullet) | no |
| 7 | Must not weaken a contract merely to shorten | § Trim Agent | § 1. Trim Agent | no |
| 8 | Trim authority is over location, not meaning; removal manifest with dr/delta/audit/lore/discard tags; reviewer spot-checks; unrouted valuable prose = rejected trim; manifest is a handoff artifact for rule-11 | AMENDMENT (Chris, 2026-08-06): nothing is deleted — everything is routed | § 1. Trim Agent → "The removal manifest" | no |
| 9 | Additions logged in manifest ADDITIONS section w/ justification; pass coupling scan; unlogged addition = rejected trim, same class as unrouted removal | AMENDMENT (CAL-23 R1 + Chris ruling, 2026-08-07) | § 1. Trim Agent → "The removal manifest" | no |
| 10 | Net-shrink (hardening rule 1) still governs section total; additions live inside the shrink budget | AMENDMENT (CAL-23 R1 + Chris ruling, 2026-08-07) | § 1. Trim Agent → "The removal manifest" (full statement lives at Hardening rule 1) | cross-ref only |
| 11 | Trim-agent scoring: candidate until proven; credit only via 4-step closure chain; large-unsafe-deletion fails, small-safe succeeds, large-then-restored succeeds after closure | § Trim Agent | § 1. Trim Agent → "Trim-agent scoring" | no |
| 12 | Build agent purpose: could someone rebuild if original were gone; must be blind | § Blind Build Agent | § 2. Blind Build Agent | no |
| 13 | Isolated worktree insufficient if original implementation remains readable | § Blind Build Agent (intro) **and** Hardening rule 10 | § 2. Blind Build Agent (one-line cross-ref) — full mechanism at Hardening rule 10 | cross-ref only |
| 14 | Blindness boundary: what builder may receive | § Blind Build Agent | § 2. Blind Build Agent → "The blindness boundary" | no |
| 15 | Blindness boundary: what builder must not receive | § Blind Build Agent | § 2. Blind Build Agent → "The blindness boundary" | no |
| 16 | Builder is tested on the documentation; anything letting it reconstruct from another source invalidates the experiment | § Blind Build Agent | § 2. Blind Build Agent → "The blindness boundary" | no |
| 17 | Freshness requirement: contamination triggers; every revised candidate needs a fresh blind builder | § Blind Build Agent | § 2. Blind Build Agent → "Freshness requirement" | no |
| 18 | Sample-size requirement for fresh builders on discovery rounds (2-of-2, escalate 2-of-3; clean trims may close on one) | Hardening rule 3 | § Scoring Hardening Rules, rule 3 (cross-referenced from Freshness requirement) | no |
| 19 | Build-agent scoring: credit only on passing examination; plausible code / ambiguity-explanation is not success; green reconstruction is proof | § Blind Build Agent | § 2. Blind Build Agent → "Build-agent scoring" | no |
| 20 | Test agent attacks without editing; opposed incentive | § Test Agent | § 3. Test Agent | no |
| 21 | Test agent's permitted attack surface (suite, boundaries, `>` vs `>=`, missing/empty/None/stale/unknown states, ordering/lifecycle, provider differences, concurrency, malformed input, suite gaps) | § Test Agent | § 3. Test Agent | no |
| 22 | Red isn't automatically scored; impossible/invalid/fabricated/bad-premise inputs don't count; implementation stays untouched | § Test Agent | § 3. Test Agent | no |
| 23 | Test-agent scoring: pending claim until 6-step chain closes; red that can't contribute earns nothing | § Test Agent | § 3. Test Agent → "Test-agent scoring" | no |
| 24 | Review agent evidence access list | § Review Agent | § 4. Review Agent | no |
| 25 | Reviewer's job is to determine why; must distinguish A/B/C/D | § Review Agent | § 4. Review Agent | no |
| 26 | A. Builder error → don't restore prose, retry fresh | § Review Agent | § 4. Review Agent → A | no |
| 27 | B. Experiment error → repair boundary, don't misclassify as prose defect | § Review Agent | § 4. Review Agent → B | no |
| 28 | C. Test error → repair/reject test, don't change DR for a false premise | § Review Agent | § 4. Review Agent → C | no |
| 29 | D. Specification failure → find smallest missing meaning, don't just restore the deleted paragraph; worked example (finalize-claim invariant) | § Review Agent | § 4. Review Agent → D | no |
| 30 | Review-agent scoring: no credit for persuasive diagnosis alone; 5-step causal proof; wrong cause ≠ closed | § Review Agent | § 4. Review Agent → "Review-agent scoring" | no |
| 31 | Delayed-scoring summary: general principle + per-role no-points/points-for recap (trim/build/test/review) | § Delayed Scoring: No Points Until Closure | § Delayed Scoring: No Points Until Closure | cross-ref only — protected structure (full rules at rows 11, 19, 23, 30) |
| 32 | Causal chain diagrams: clean-trim path and discovery-round path | § The Causal Chain | § The Causal Chain | no |
| 33 | What makes prose load-bearing: stricter test (did removal permit a reasonable-but-wrong build); historical explanation → audit record | § What Makes Prose Load-Bearing? | § What Makes Prose Load-Bearing? | no |
| 34 | Minimality boundary: pattern signaling correct size; target is smallest demonstrated sufficient spec, not shortest text | § The Minimality Boundary | § The Minimality Boundary | no |
| 35 | Three-tier doc model (DR / dev docs / audit record) + reconciliation flow | § Relationship to the Documentation Lifecycle | § Relationship to the Documentation Lifecycle | no |
| 36 | Passing suite only proves sufficiency relative to current apparatus; toothless-test discovery makes DR result provisional; three mutually reinforcing proofs | § Important Interaction with the Test Audit | § Important Interaction with the Test Audit | no |
| 37 | Operational invariants 1–12 (blind builders, contamination, freshness, untouched implementation, red≠credit, green-needs-biting-pins, A/B/C/D review, no auto-restore, minimal-invariant recovery, historical-reasoning-to-audit, delayed credit, min-sufficient-spec-not-min-words) | § Operational Invariants of This Protocol | § Operational Invariants of This Protocol | cross-ref only — protected structure (full rules stated at their respective role/topic sections) |
| 38 | Final principle: adversarial roles, none wins independently, proof closes only on fresh blind reconstruction surviving hostile examination | § Final Principle | § Final Principle | no |
| 39 | Hardening rules 1–10 (net-shrink, A/B/C pay-on-own-closure, 2-of-2 builders, coupling rejection, D-needs-misreading-artifact, trim budget N=3, B-repair cap 2, biting-pin bounty, closed-invariant ledger, sandbox generator prerequisite) | ADOPTED SCORING HARDENING | § Scoring Hardening Rules 1–10 | no |
| 40 | Rollout step 1: doc 23 calibration | ROLLOUT PLAN | § Rollout Plan, step 1 | no |
| 41 | Rollout step 2: doc 18 confirmation | ROLLOUT PLAN | § Rollout Plan, step 2 | no |
| 42 | Rollout step 3: no topological order exists; atom-first then reading order; PROVIDES-surface-change flags dependents provisional; trims preserve interfaces | ROLLOUT PLAN | § Rollout Plan, step 3 | no |
| 43 | Rollout step 3: invariant-density decides loop depth, never sequence | ROLLOUT PLAN | § Rollout Plan, step 3 | no |
| 44 | Rollout step 3: frontend docs get trim + coupling scan only | ROLLOUT PLAN | § Rollout Plan, step 3 | no |
| 45 | User guides exempt from ablation entirely; standing update policy (interface-change-only); current-epoch consequence list | ROLLOUT PLAN step 3 (brief mention) **and** AMENDMENT (Chris, 2026-08-06): user guides are exempt (full policy) | § Rollout Plan, step 3 (single merged statement) | no — two v1 sources merged into one v2 location |
| 46 | Three distinct sequences (ablation order / reading order / recovery progression) — do not collapse | ROLLOUT PLAN step 3 (GPT review note) | § Rollout Plan, step 3 | no |
| 47 | Rollout step 4: per-doc outputs (trimmed section, migrated history, ledger entries, status row) | ROLLOUT PLAN | § Rollout Plan, step 4 | no |
| 48 | Rollout step 5: suspension rule for toothless pins | ROLLOUT PLAN | § Rollout Plan, step 5 | no |
| 49 | Advanced guides sequence after DR reconciliation; in-flight patches park; mechanical fixes ride the same hold | AMENDMENT (Chris, 2026-08-06): advanced guides sequence AFTER disaster recovery | § Rollout Plan, step 6 | no |
| 50 | Staffing tiers: Sonnet for trim/build/test, Opus for review, script-not-model economy, Fable at two escalation points | STAFFING / MODEL FIT | § Staffing and Model Fit | no |
| 51 | Hardening rule 11: statistical handoff audits (per-pair ledger, random + statistical triggers, incidental-similarity forensics, consequences) | AMENDMENT (Chris, 2026-08-06): hardening rule 11 | § Scoring Hardening Rules, rule 11 | no |
| 52 | Hardening rule 12: confirmed smuggle voids the whole class; collective liability rationale; whistleblower carve-out (keeps credit, earns bounty, false flag unpunished) | AMENDMENT (Chris, 2026-08-06): rule 12 | § Scoring Hardening Rules, rule 12 | no |
| 53 | Rule 12a whistleblower mechanics: made-whole+capped-bounty, evidence-required filing, single-false-flag unpunished, flag-precision-gated auto-trigger, flag-never-a-veto | AMENDMENT (2026-08-06): rule 12a | § Scoring Hardening Rules, rule 12 | no |
| 54 | Rule 12b: escrow not pay-then-clawback; participant-whistleblower gets zero; duplicate flags don't multiply; quality-scored reliability (supersedes 12a's raw 1-in-3 threshold); reciprocal-whistleblowing detection; delayed credit; payout table | AMENDMENT (2026-08-06): rule 12b | § Scoring Hardening Rules, rule 12 | no |
| 55 | Hardening rule 13: base-revision mechanism (record DR + source blob hashes at trim submission; unchanged → apply; DR drift → blocked pending 3-way reconciliation; source drift → provisional; stale base never silently overwritten; >1-epoch-edge-commit stale → re-trim not merge) | AMENDMENT (CAL-23 apply-step finding, 2026-08-07): rule 13 | § Scoring Hardening Rules, rule 13 | no |
| 56 | Hardening rule 14: one live statement per rule; amendments rewrite in place, never append-only; reviewer collision-sweep checklist item; rationale (retrieval-agent readers) | AMENDMENT (GPT review + agent follow-up, 2026-08-07): rule 14 | § Scoring Hardening Rules, rule 14 | no |

## Rows requiring explanation (not blank, not "no"/"cross-ref only" alone)

- **Row 45** (user-guide exemption): the two v1 sources are not left as full-statement +
  stub; both were merged into the single Rollout Plan step-3 statement, per the
  instruction that amendment sections disappear as sections. There is no residual second
  full statement anywhere else in v2 to point at, so there is nothing left to mark as a
  duplicate.

## Rules NOT cleanly placed

None. Every row above has exactly one governing v2 location, and both duplicate cases
found in the sweep (rows 10/13 partially, plus 45) were resolved either by cross-reference
(row 13, the isolated-worktree claim → Hardening rule 10) or full merge (row 45, user
guides).
