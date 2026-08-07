# Provenance Record: DR Prose Ablation Protocol

This file holds everything stripped from `PROTOCOL-dr-prose-ablation.md` during the
2026-08-07 consolidation pass: attributions, dates, discovery narratives, and worked
examples. The living protocol states rules in present tense with no history; this file
is where that history lives. Entries are ordered to match the rule they belong to in the
consolidated document.

---

## Scoring Hardening Rules 1–10 (base list)

**Header, as it originally read:** "ADOPTED SCORING HARDENING (audited 2026-08-06,
Chris-approved)." Text claimed "The incentive audit found seven exploit classes in the
scoring surface" while the list that followed already had ten numbered rules — the count
was stale by the time of the 2026-08-07 pass (rules 8–10 had evidently been folded in
after the "seven" figure was written, without updating the sentence). The consolidated
document drops the specific-count claim entirely rather than perpetuate a number nobody
can verify.

---

## Rule 12 — smuggle voids the whole class

**Origin:** AMENDMENT (Chris, 2026-08-06): "rule 12 — a smuggle voids the whole class."
Ruled by Chris on 2026-08-06.

## Rule 12a — whistleblower mechanics

**Origin:** AMENDMENT (2026-08-06): "rule 12a — whistleblower mechanics, exact." No
individual attribution recorded beyond the date; follows directly from the rule-12
ruling above.

**Superseded provision, preserved here only:** rule 12a originally gated the
auto-audit-trigger demotion on a fixed numeric threshold — "Per-agent flag precision is
tracked; below threshold (start: <1-in-3 confirmed, rolling window) the agent's flags
stop auto-triggering forensic audits." Rule 12b (below) explicitly replaced this raw-rate
threshold with quality-scoring ("Flagger reliability is quality-scored, not raw-rate-scored
... The fixed 1-in-3 precision threshold is replaced"). The consolidated protocol
carries forward only the 12b version, per hardening rule 14 (one live statement per
rule). The 1-in-3 rolling-window figure is preserved here as the discarded first attempt,
in case the quality-scoring approach ever needs a fallback reference.

## Rule 12b — escrow, participant-zero, and the payout table

**Origin:** AMENDMENT (2026-08-06): "rule 12b — escrow, participant-zero, and the payout
table." Marked as a *"three-agent convergence: Chris + secondary reviewer +
coordinator"* — i.e., three independent review passes converged on this ruling rather
than one person deciding it. Dated 2026-08-06.

---

## Rule 11 — statistical handoff audits

**Origin:** AMENDMENT (Chris, 2026-08-06): "hardening rule 11 — statistical handoff
audits." Ruled by Chris on 2026-08-06.

---

## Trim Agent — removal manifest ("nothing is deleted — everything is routed")

**Origin:** AMENDMENT (Chris, 2026-08-06): "nothing is deleted — everything is routed."
Ruled by Chris on 2026-08-06. This amendment introduced the manifest concept
(`dr`/`delta`/`audit`/`lore`/`discard` destination tags) wholesale; it did not exist in
the original core protocol.

---

## Trim Agent — additions are licensed

**Origin:** AMENDMENT (CAL-23 R1 finding + Chris ruling, 2026-08-07): "additions are
ALLOWED — and logged."

**Worked example, stripped from operational text:** the rule was justified by round 1 of
the CAL-23 calibration run (doc 23, the error tracker), which "proved both faces" of the
addition-licensing question in a single round:
- The trimmer's best moment of that round was itself an addition: it corrected §7.2's
  wiring description — identifying that the deprecated `harvest_active_run` was
  documented as the live finalizer wiring — *before* the repository's own code fix for
  that same issue had landed.
- The same round's one induced divergence was also an addition: an unlogged field-table
  row whose phrasing implied lifecycle behavior that the code does not actually have.

The finding was that the rule needed to be "license + ledger, not suspicion" — additions
are legitimate and sometimes required, but every one has to be logged and scanned, because
the same mechanism that let the trimmer fix a real bug also let it introduce one.

---

## Rule 13 — base revisions

**Origin:** AMENDMENT (CAL-23 apply-step finding, 2026-08-07): "rule 13 — BASE
REVISIONS, because the loop has no merge base."

**Framing, stripped from operational text:** the amendment described itself as closing a
gap that "Nothing in rules 1-12" (the rule set as it stood at the time) detected, and
opened with "until now had no notion of a base revision for either artifact" — i.e., this
was a genuinely new mechanism, not a restatement.

**Worked example (CAL-23), moved here in full:**

> CAL-23 is the worked example. The trim's baseline was doc 23 at 475 lines
> (`31edf3b`). Round 1's first blood — §7.2 documented the deprecated
> `harvest_active_run` as the live finalizer wiring — was applied to the LIVE doc
> immediately and correctly, taking it to 488 lines (`e649b9e`). The closed candidate was
> 415 lines, built from the 475-line snapshot. It was applied by hand-diffing first and
> found benign (round 2 had independently restored the same correction), but the check
> was ad-hoc, performed by the coordinator, and was nowhere written down as a repeatable
> procedure. On a nine-section fan-out against an actively developed tree, the same
> shortcut would not stay benign — hence the mechanism being formalized as rule 13.

This example is the empirical basis for the rule's claim that base-revision drift "is not
an edge case" but "the DEFAULT path for any round that draws first blood" (i.e., any
round whose trim gets applied while a real fix is landing on the live doc concurrently) —
because lifecycle discipline requires a corrected DR statement to land in the same commit
as its fix, while the ablation loop is simultaneously holding a frozen snapshot of that
same section. The consolidated rule keeps this causal explanation in present tense but
drops the "rules 1-12" self-reference and the CAL-23 specifics (hashes, line counts,
round numbers).

---

## Rule 14 — one live statement per rule

**Origin:** AMENDMENT (GPT review + agent follow-up, 2026-08-07): "rule 14 — one live
statement per rule." Identified by an external GPT review pass, with follow-up
investigation by the working agent, on 2026-08-07.

---

## Staffing and Model Fit

**Origin header, as it originally read:** "STAFFING / MODEL FIT (Chris's token
constraint, 2026-08-06)." The section existed to manage token/cost budget across the
ablation fleet — Chris's constraint was the reason the staffing tiers (Sonnet for
per-artifact loops, Opus for adjudication, Fable reserved to two escalation points) were
set the way they were, rather than defaulting everything to the strongest available
model.

---

## Rollout Plan, step 3 — fan-out order

**Origin of the corrected rationale:** the original step 3 text was revised following
"Chris's check, 2026-08-07" — Chris identified that the doc numbers looked like a
topological build order but are not one (the module graph is mutually recursive), which
is why the rule now states the atom-first + PROVIDES-surface-provisional mechanism
instead. The README's reading order was independently verified as sound by "Chris's
core-stands-alone check" against doc 32.

**Narrative dropped entirely (not load-bearing for the rule):** "Doc 23 closed out of
order as the calibration; the docs-only rebuild drill re-validates it in its proper
position." This recorded the historical fact that doc 23 was ablated first (as the
calibration run) even though it does not sit first in the atom-first/reading-order
sequence, and that a later pass would re-validate it in its proper sequence position. It
is a status note about one specific run, not a rule.

**Three-sequences clarification, origin:** identified in a "GPT review, 2026-08-07"
pass, with agent follow-up confirming the distinction was real and not just terminological
— the ablation order, the README reading order, and the recovery-capability progression
are three genuinely different orderings that happen to share an atom-first starting
point, and conflating them was an active risk in the doc as it stood.

---

## Rollout Plan, step 3 — user guides are exempt

**Origin:** AMENDMENT (Chris, 2026-08-06): "user guides are exempt." Ruled by Chris on
2026-08-06. Originally a standalone amendment section; its full policy (exemption
rationale + the current-epoch consequence list of which user-guide patches actually
apply) has been merged into Rollout Plan step 3, which previously only carried a one-clause
mention ("USER GUIDES are EXEMPT from ablation entirely — not even trim+coupling").
This was one of two confirmed duplicate-normative-content cases found in the
consolidation sweep (see RULE-INVENTORY.md).

---

## Rollout Plan, step 6 — advanced guides sequence after DR

**Origin:** AMENDMENT (Chris, 2026-08-06): "advanced guides sequence AFTER disaster
recovery." Ruled by Chris on 2026-08-06.

---

## Blindness boundary — "isolated worktree" duplicate

The claim that an isolated worktree does not satisfy the blindness boundary originally
appeared twice: once as a bare assertion under Blind Build Agent → The blindness
boundary ("An isolated worktree is not sufficient if the original target implementation
remains readable"), and again with the full mechanism under hardening rule 10 ("An
isolated worktree is NOT blind — the target implementation and its tests are one grep
away," alongside the actual sandbox-construction requirement). This was the second
confirmed duplicate-normative-content case (see RULE-INVENTORY.md). Hardening rule 10 was
kept as the governing location because it carries the executable mechanism; the Blind
Build Agent section now cross-references it instead of restating the claim.

---

## Miscellaneous phrasing stripped as attention-of-the-author rather than rule content

These did not carry a named ruling or date, but read as evidence that someone was paying
attention to a specific moment in the project rather than as durable rule text. Recorded
here per the coordinator's mid-task filter, since none of them affect what the rule
requires:

- Rollout Plan step 3 originally said invariant-density "**now** only decides LOOP DEPTH
  per doc ... never sequence" — the "now" implicitly contrasted against an earlier
  (wrong) assumption that doc landing order was also ablation order. Consolidated text
  states the rule directly without the before/after framing.
- Rule 13's introduction said the protocol "**until now** had no notion of a base
  revision for either artifact" and that "**Nothing in rules 1-12** detects it" — both
  phrasings assert the gap by reference to the document's own prior state rather than
  describing the mechanism. Dropped; the consolidated rule just states what the base
  revision is and does.
- Rule 13's rationale originally said base-revision drift is "the DEFAULT path for any
  round that **draws first blood**" — vivid but narrative-flavored idiom for "the first
  round in a section that produces an actual correction." Consolidated text uses the
  plain phrasing.
- The Staffing section's description of the doc-23 calibration review called it "the
  **precedent-setter**" — technically accurate but framed as significance earned over
  time rather than a standing property. Consolidated text says "the round every other
  closure calibrates against," which states the same operational fact without the
  historical framing.

## User-guide exemption — campaign-state consequence (2026-08-07 sweep)

The exemption's original amendment carried an apply-time consequence for the Epoch-1
reconciliation, executed 2026-08-06: user-guide cluster patches applied only where they
documented real interface changes from that epoch (Job Summary modal, per-map
reject/unreject, the typeface setting, run-list truncation notice, access-graph issue
explanations); cosmetic or mechanism-tracking rewrites were dropped at apply time.
Removed from the living rule as time-bound campaign state.
