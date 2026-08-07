# Disaster-Recovery Prose Ablation and Blind Reconstruction Protocol

## Purpose

This protocol tests whether each section of the disaster-recovery (DR) documentation contains the **minimum information necessary to reconstruct the required system correctly**.

The goal is not to make the documentation short for its own sake. The goal is to distinguish:

- prose that is merely historical, explanatory, repetitive, or no longer load-bearing;
- prose whose **meaning is required** to reconstruct correct behavior;
- hidden invariants that have never been stated cleanly because they are buried inside months of development history.

The test is performed **per DR section**.

A section is repeatedly trimmed, reconstructed by a blind implementer, tested, reviewed, and revised. The process continues until further reduction removes information that a competent blind implementer actually needs.

The surviving meaning is an invariant.

The wording itself is not sacred. A page of historical reasoning may collapse into one precise sentence. What must survive is the information required to rebuild the behavior correctly.

---

## Core Question

For each DR section:

> **How much can be removed while a fresh, blind implementer can still reconstruct a system that survives the real tests?**

This is a disaster-recovery test, not a source/document consistency review.

The implementation agent must not be able to recover missing information from the implementation that already exists.

---

# The Four-Agent Loop

Each round uses four distinct roles with deliberately conflicting incentives:

1. **Trim Agent**
2. **Blind Build Agent**
3. **Test Agent**
4. **Review Agent**

The agents do not receive credit merely for producing work. Credit is released only when the causal chain closes successfully.

**Red produces evidence. Green closes the proof.**

---

# 1. Trim Agent — Minimize the Specification

The trim agent is allowed to see the full context needed to make an informed reduction:

- current DR section;
- current implementation;
- development documentation;
- audit record;
- relevant tests;
- surrounding contracts.

Its job is to make the DR section smaller while preserving everything necessary for reconstruction.

It may:

- remove historical narrative;
- remove superseded reasoning;
- collapse repeated explanations;
- replace long failure histories with a concise current invariant;
- remove implementation archaeology that belongs in the audit record;
- rewrite prose for precision;
- preserve exact boundary conditions and required behavior.

It must not weaken a contract merely to make the document shorter.

### Trim-agent scoring

A trim is only a **candidate** until the rest of the loop proves it.

The trim agent receives no final credit merely for deleting words.

It receives credit only when:

1. its trimmed section is given to a fresh blind builder;
2. that builder reconstructs the target;
3. the reconstructed target survives testing;
4. the final system is green.

A large deletion that causes an unrecoverable or underspecified build earns nothing.

A small but provably safe deletion is a valid success.

A large deletion that ultimately becomes green after a tester exposes one missing invariant and that invariant is restored in a smaller form is also a success—but only after closure.

---

# 2. Blind Build Agent — Reconstruct from the DR Section

The build agent is the actual disaster-recovery subject.

Its purpose is to answer:

> **Could somebody rebuild this subsystem correctly if the original implementation were gone?**

The build agent must be **blind**.

An isolated worktree is not sufficient if the original target implementation remains readable.

## The blindness boundary

The builder may receive:

- the candidate trimmed DR section;
- explicitly allowed surrounding interfaces;
- dependency contracts required to integrate the reconstruction;
- language and framework knowledge;
- public APIs that the reconstructed component must satisfy.

The builder must not receive:

- the original target implementation;
- the previous/full DR version of the target section;
- development-history prose for the target;
- the audit history for the target;
- hidden test bodies or expected failure cases;
- a previous builder's implementation;
- a previous builder's failure analysis;
- subsystem-specific memory that leaks the answer.

The builder is being tested on the documentation, so anything that lets it reconstruct the answer from another source invalidates the experiment.

## Freshness requirement

Once a builder has:

- seen a hidden test;
- been told why its implementation failed;
- seen the original implementation;
- seen the omitted prose;

that builder is contaminated for the purpose of certifying the revised DR section.

**Every revised candidate must be tested by a fresh blind builder.**

### Build-agent scoring

The builder receives credit only when the implementation it produced from permitted information passes the required examination.

Plausible code is not success.

An explanation that the prose was ambiguous is useful evidence, but it is not a successful build.

A successful green reconstruction is the builder's proof.

---

# 3. Test Agent — Try to Make the Untouched Build Fail

The test agent receives the reconstructed implementation and attacks it.

Its incentive is deliberately opposed to the builder's.

The tester should try to produce legitimate failures **without editing the implementation**.

It may:

- run the existing relevant suite;
- exercise known contract boundaries;
- probe values such as `> 1` versus `>= 1`;
- test missing, empty, `None`, unavailable, stale, and unknown states where reachable;
- attack ordering and lifecycle boundaries;
- exercise provider-specific differences;
- probe concurrency and suspension boundaries where real execution permits them;
- construct realistic malformed or partial inputs;
- identify places where the existing suite does not actually force the claimed invariant.

The tester does not score merely because it found a way to make something red.

An impossible input, invalid fixture, fabricated state, or bad premise is not a useful failure.

The implementation must remain untouched during the attack.

## Test-agent scoring

A tester's failure begins as a **pending claim**.

The tester receives no final credit simply for producing red.

The failure becomes valuable only if the downstream chain proves that it exposed missing or inadequate DR information:

1. tester produces a legitimate failure on the untouched reconstruction;
2. reviewer identifies the causal specification flaw or missing invariant;
3. that information is returned to the trimmer;
4. the trimmer expresses the missing meaning in the DR section;
5. a **new blind builder** reconstructs from the revised section;
6. the resulting system passes the relevant tests.

Only then did the tester demonstrate that its failure materially improved the reconstructable specification.

A red test that cannot contribute to a successful corrected reconstruction earns no final points.

---

# 4. Review Agent — Adjudicate the Failure

The review agent may see the complete evidence set:

- original implementation;
- original DR prose;
- trimmed DR prose;
- reconstructed implementation;
- test results;
- tester's new cases;
- development documentation;
- audit history;
- relevant surrounding contracts.

The reviewer is not there merely to say that something failed.

Its job is to determine **why**.

For every failure, it must distinguish among at least these possibilities:

### A. Builder error

The trimmed prose was sufficient, but the builder made an unreasonable or unrelated implementation mistake.

Result:

- do not restore prose automatically;
- retry with a fresh blind builder if needed.

### B. Experiment error

The builder was denied a dependency or surrounding contract that a real disaster-recovery implementer legitimately requires.

Result:

- repair the experiment boundary;
- do not classify the missing dependency as target-section prose without justification.

### C. Test error

The test used impossible data, asserted the wrong contract, or otherwise produced invalid evidence.

Result:

- repair or reject the test;
- do not change DR prose to satisfy a false premise.

### D. Specification failure

The trimmed section permits a **reasonable but wrong** implementation.

This is the important case.

The reviewer must identify the smallest missing piece of meaning that distinguishes the required behavior from the reasonable wrong implementation.

That meaning is a candidate invariant.

The reviewer should not simply demand that the deleted paragraph be restored.

For example, several paragraphs of historical reasoning may reduce to:

> **Invariant:** the finalize claim MUST be established before the first suspension point. Establishing the claim after an `await` does not satisfy the exactly-once contract.

The historical narrative can move to the audit record.

The invariant remains in DR.

## Review-agent scoring

The reviewer does not receive final credit for a persuasive diagnosis.

Its diagnosis must prove causal.

Credit is released only when:

1. the reviewer identifies the missing or inadequate contract;
2. the trimmer incorporates the minimum required meaning;
3. a new blind builder reconstructs from the revised prose;
4. the previously exposed failure is eliminated;
5. the relevant suite returns green.

A reviewer that identifies the wrong cause has not closed the proof.

---

# Delayed Scoring: No Points Until Closure

The scoring system deliberately prevents agents from being rewarded for activity.

## Trim Agent

**No points for:** deleting prose.

**Points for:** deleting prose that remains deleted in a final green reconstruction.

---

## Build Agent

**No points for:** plausible implementation, effort, explanation, or partial correctness.

**Points for:** a successful blind reconstruction that passes examination.

---

## Test Agent

**No points for:** producing red by itself.

**Points for:** producing a legitimate failure whose information is successfully converted into improved DR prose and then proven by a fresh green reconstruction.

---

## Review Agent

**No points for:** identifying an interesting flaw or writing a convincing explanation.

**Points for:** identifying the causal missing invariant or specification defect that, once incorporated, causes a fresh blind reconstruction to succeed.

---

# The Causal Chain

A clean trim can close immediately:

```text
Current DR section
      |
      v
  TRIM AGENT
      |
      v
Smaller candidate DR
      |
      |  blindness boundary
      v
  BUILD AGENT
      |
      v
Reconstructed subsystem
      |
      v
  TEST AGENT
      |
      v
     GREEN
      |
      v
Trim + Build proof closes
```

A discovery round is more valuable and more complex:

```text
Current DR section
      |
      v
  TRIM AGENT
      |
      v
Smaller candidate DR
      |
      |  blindness boundary
      v
  BUILD AGENT
      |
      v
Reasonable reconstruction
      |
      v
  TEST AGENT
      |
      v
Legitimate RED
      |
      v
 REVIEW AGENT
      |
      +--> builder mistake --------> retry; prose not restored
      |
      +--> bad experiment ---------> repair boundary
      |
      +--> bad test ---------------> repair/reject test
      |
      `--> missing specification
                |
                v
        identify minimum invariant
                |
                v
           TRIM AGENT
        revises candidate DR
                |
                |  NEW blindness boundary
                v
        FRESH BUILD AGENT
                |
                v
           TEST AGENT
                |
                v
              GREEN
                |
                v
        CREDIT IS RELEASED
```

The intermediate red does not represent failure of the process.

It is evidence that the process found load-bearing meaning.

---

# What Makes Prose Load-Bearing?

A deleted passage does not deserve to remain simply because removing it was followed by a failed build.

The question is stricter:

> **Did removing this information permit a competent blind implementer to make a reasonable implementation that violates required behavior?**

If no, the prose has not proven itself necessary.

If yes, the omitted **meaning** is load-bearing.

The next job is to state that meaning as directly and compactly as possible.

The historical explanation can live in the audit record.

---

# The Minimality Boundary

The DR section is approaching its correct size when repeated independent blind reconstructions show this pattern:

- further cosmetic or historical trimming has no effect;
- redundant explanation can disappear safely;
- removing one specific piece of meaning repeatedly allows a reasonable wrong implementation;
- restoring that meaning as a concise invariant restores successful reconstruction.

That point is the specification boundary.

The final DR section should not be the shortest text imaginable.

It should be the **smallest demonstrated sufficient specification**.

---

# Relationship to the Documentation Lifecycle

This protocol operates on the DR baseline during an epoch-closing reconciliation.

The broader documentation model remains:

- **DR docs:** current rebuildable truth;
- **development docs:** current-epoch differences, reasoning, hypotheses, and unsettled work;
- **audit record:** permanent history, failed reasoning, rejected theories, provenance, and scars.

During reconciliation:

```text
Development reasoning
        |
        +--> surviving current behavior --> DR
        |
        `--> failures / superseded reasoning / provenance --> Audit Record
```

The ablation protocol determines how much of the surviving current behavior actually needs to remain in DR.

Long historical explanations may leave DR because their provenance now has a durable home in the audit record.

Only their surviving reconstructive meaning remains.

---

# Important Interaction with the Test Audit

A green reconstruction is only as meaningful as the tests capable of rejecting a bad reconstruction.

Therefore:

> **Passing the current suite proves DR sufficiency only relative to the current measuring apparatus.**

If the later test audit discovers that a relevant test was toothless—capable of passing while the guarded behavior was broken—then any DR-minimization result that relied on that test must be considered provisional.

Once the test is given a biting pin, the affected DR section should be eligible for another blind reconstruction pass.

This creates three mutually reinforcing proofs:

> **Blind reconstruction tests the documentation.**  
> **Deliberate breakage tests the tests.**  
> **The audit tests the implementation.**

None may use the thing it is supposed to certify as its answer key.

---

# Operational Invariants of This Protocol

1. **Builders are blind.**
2. **A contaminated builder never certifies revised prose.**
3. **Every meaningful retry uses a fresh blind builder.**
4. **The tester does not edit the implementation it is attacking.**
5. **Red alone earns no final credit.**
6. **Green alone is insufficient if the tests have not demonstrated that their pins bite.**
7. **Review distinguishes builder, experiment, test, and specification failures.**
8. **Deleted prose is not automatically restored after a failure.**
9. **The smallest missing meaning is recovered as an invariant.**
10. **Historical reasoning moves to the audit record when it is no longer required for reconstruction.**
11. **Credit is delayed until the complete causal chain closes.**
12. **The target is not minimum word count. The target is minimum demonstrated sufficient specification.**

---

# Final Principle

The process is intentionally adversarial.

The trim agent tries to prove that prose is unnecessary.

The blind builder tries to prove that the reduced prose is sufficient.

The tester tries to prove that the reconstruction is wrong.

The reviewer tries to determine which claim the evidence actually supports and what minimum information is missing.

But none of them wins independently.

The proof closes only when a reduced DR section allows a **fresh blind reconstruction** to survive a legitimate hostile examination.

At that point, the prose that remains has earned its place.

It is no longer there because somebody remembered that it seemed important.

It is there because the system was experimentally worse without its meaning.

---

# ADOPTED SCORING HARDENING (audited 2026-08-06, Chris-approved)

The incentive audit found seven exploit classes in the scoring surface. These rules close
them and are PART OF THE PROTOCOL from the first run:

1. **Net-shrink per closure.** Every closed round leaves the section strictly smaller than
   it started. Kills reviewer invariant-inflation structurally — a document that must
   shrink to close cannot be regrown for points.
2. **A/B/C verdicts pay on their own closures.** A (builder error) closes when a fresh
   builder greens with UNCHANGED prose; B (experiment error) when the repaired boundary
   yields a green; C (test error) when the repaired test is shown to bite. Without this,
   every ambiguous failure bends toward D.
3. **2-of-2 fresh builders on discovery rounds** (escalate 2-of-3 on disagreement). A
   single-sample closure is a coin-flip certification and re-litigating churn is revenue.
   Clean first-pass trims may close on one builder.
4. **Implementation-coupling is a rejection class.** Trimmed prose carrying information not
   derivable from the public contract (internal names, incidental structure, test-expected
   magic values) is rejected before any build — the trimmer sees the implementation and
   authors the blind builder's only input, so answer-smuggling is the protocol's worst
   failure mode and it needs no collusion, only optimization pressure.
5. **D verdicts require a misreading artifact.** The reviewer must reproduce, from the
   trimmed prose ALONE, the chain of reasonable readings that yields the wrong
   implementation. Cannot articulate it → classify A. Blocks sandbagged-build farming.
6. **Trim budget.** N candidate submissions per section (start N=3). A failed trim burns
   the three most expensive roles; gambling must cost the gambler.
7. **B-repair cap.** Two boundary repairs per section; after that the boundary spec itself
   is the defect and escalates to Chris.
8. **Biting-pin bounty.** Testers earn a small immediate bounty (outside the chain) for
   novel pins certified to kill a deliberate breakage of the guarded behavior — otherwise
   the tester's rational strategy is to run only the existing suite and never risk a C.
9. **Closed-invariant ledger.** Each closure records the invariant AND its misreading.
   Reopening a ledgered invariant needs new evidence; re-proving one pays nothing.
10. **The sandbox generator is a prerequisite, not a detail.** Blind builds run in a
    constructed directory containing ONLY the trimmed section + allowed interfaces +
    dependency stubs. No repo checkout, no .claude/notes, no project memory. An isolated
    worktree is NOT blind — the target implementation and its tests are one grep away.

# ROLLOUT PLAN (the rest of the documents)

Sequencing constraint: **ablation only runs on truth-passed docs** — trimming a stale
baseline confuses missing invariants with unapplied fixes.

1. **Calibration: doc 23 (error tracker).** Self-contained module, invariant-dense,
   biting tests, cheap sandbox. Full loop, Chris eyeballs the result before anything else.
2. **Confirmation: doc 18 (onboarding manager)** once dev-core's truth patch lands —
   cleanest sandbox in the corpus (data+hass ctor). Run only if calibration leaves doubts
   about generality; otherwise optional.
3. **Fan-out top-down in READING ORDER — corrected rationale (Chris's check,
   2026-08-07).** The doc numbers are LANDING order and the module graph is mutually
   recursive (measured: 5 of 26 dependency-free, the rest one cluster —
   `DOC-DEPENDENCY-MAP.md`), so a topological ablation order DOES NOT EXIST. Proof
   composition does not need one: closures lean on other docs' INTERFACE STATEMENTS,
   which all exist from day one. The fleet therefore runs ATOM-FIRST, then the README's
   reading order (Chris's core-stands-alone check, doc 32): the atom's sections —
   03 (spine/data), 21/22 (adapter), 07 (queue/dispatch), 08 (rooms), 06
   (active_job) — close first, because with just those proven a rebuilt system
   CLEANS; then the remainder top-to-bottom (01 → 02 → 04 → 05 → 30 → 09…15/31 →
   16-18 → 25/26/29 → 28), with the compensating
   rule that replaces sequencing: **any closure that alters a doc's PROVIDES surface
   flags every dependent doc's closure provisional** (dependents per
   DOC-DEPENDENCY-MAP.md). Trims must preserve interface statements regardless — they
   are contract.
   Invariant-density now only decides LOOP DEPTH per doc (full discovery loop vs
   trim+single-build vs schema-reconstruction for shapes docs like 03/22), never
   sequence. Doc 23 closed out of order as the calibration; the docs-only rebuild
   drill re-validates it in its proper position. FRONTEND docs get the TRIM stage +
   coupling check only — blind reconstruction of UI prose has no biting test surface
   and would certify nothing. USER GUIDES are EXEMPT from ablation entirely — not
   even trim+coupling.

   **Three sequences share the atom-first principle without being the same sequence
   — do not collapse them (GPT review, 2026-08-07):**
   - *Ablation order* (this section): which docs get experimentally minimized first.
   - *Reading order* (the README): how a maintainer best learns the existing system.
   - *Recovery progression* (00 §0): which CAPABILITIES come online — spine, then
     adapter/dispatch/rooms/job capability with the manager accreting wiring, then
     rings against a working core. The numbered docs are EVIDENCE PACKAGES for those
     capabilities, not one-file-at-a-time build instructions; "03 → 21/22 → 07 → 08
     → 06 then rings" names the ablation priority, never the literal executable
     reconstruction sequence.
4. **Per-doc outputs:** the trimmed DR section (net-smaller), migrated history into the
   audit record with provenance tags, ledger entries for every earned invariant, and the
   section's §7 status row updated.
5. **Suspension rule:** any test-audit finding that a relied-upon pin was toothless marks
   the affected sections provisional and re-eligible, per the protocol's own apparatus
   clause.

## AMENDMENT (Chris, 2026-08-06): user guides are exempt

User-guide docs are the most abstract layer and are EXEMPT from ablation entirely (not
even trim+coupling). Their standing update policy: **touched only when an actual
interface changes** — a new surface, control, flow, or setting the user can see. Internal
mechanism changes, phrasing accuracy, and doc-hygiene churn never propagate to them.
Consequence for the current reconciliation: user-guide cluster patches apply ONLY where
they document real interface changes from this epoch (Job Summary modal, per-map
reject/unreject, the typeface setting, run-list truncation notice, access-graph issue
explanations); cosmetic or mechanism-tracking rewrites are dropped at apply time.

## AMENDMENT (Chris, 2026-08-06): advanced guides sequence AFTER disaster recovery

The advanced guides need real work, but none of it happens until the DR set is done.
The in-flight adv-contract / adv-guides patches finish their workflow runs and PARK —
applied only after the DR reconciliation completes. (adv-contract's mechanical
services/events fixes ride the same hold; copy-paste correctness matters, but a stable
DR baseline matters first.)

## AMENDMENT (Chris, 2026-08-06): hardening rule 11 — statistical handoff audits

Per-artifact checks (rules 4, 5) catch clumsy smuggling; a careful smuggler stays under
any single-artifact threshold. The control for that lives at the POPULATION level:

- **Score ledger per agent-instance and per PAIR.** Track closures, discovery rounds,
  green rates, and verdict distributions — individually AND per trimmer×builder pair,
  because collusion is invisible in individual stats and shows as one pair's anomaly.
- **Two audit triggers:** (a) a RANDOM baseline — a fixed fraction of closures (start 1
  in 5) gets a handoff audit unconditionally, so staying under statistical thresholds is
  never safe; (b) STATISTICAL — any agent or pair whose points/green-rate/verdict mix
  departs the cohort norm (rule of thumb: the outlier you would notice on a scoreboard).
  Signature patterns worth standing queries: a trimmer whose LARGE deletions always green
  first-build (coupling suspect); a builder whose greens concentrate on one trimmer's
  prose (pair suspect); a reviewer whose D-rate is an outlier (inflation suspect).
- **The audit itself** re-examines the handoff artifacts forensically. The measurable
  smoking gun is INCIDENTAL SIMILARITY: a blind reconstruction that matches the original
  implementation's incidental choices — private helper names, internal structure,
  ordering the contract does not force — beyond chance is carrying smuggled answers,
  whatever the prose looks like. Trimmed prose gets the coupling scan; new tests get the
  over-pinning scan.
- **Consequences:** a confirmed smuggle VOIDS the closure (points clawed back, ledger
  entry reopened, the section re-runs with fresh agents), and the implicated agent/pair's
  PRIOR closures get re-sampled — fraud clusters; one confirmed case is never treated as
  isolated.

## AMENDMENT (Chris, 2026-08-06): rule 12 — a smuggle voids the whole class

A confirmed smuggled answer invalidates the ENTIRE chain, not just the smuggler: the
loop's agent group (trimmer, builder(s), tester, reviewer) is one CLASS, and if one
member cheated, the class fails — nobody gets points, the closure is void, the section
re-runs with an entirely fresh class. No "I didn't smuggle, I just benefited" position
exists: benefiting from a tainted chain costs you the chain.

Why: collective liability makes every member a stakeholder in every other member's
honesty. The builder has reason to refuse suspiciously helpful prose; the reviewer has
reason to run the coupling scan hard; the tester has reason to probe a reconstruction
that greens too easily.

**Whistleblower carve-out (required complement):** collective punishment alone aligns a
tainted class around CONCEALMENT — if all lose on discovery, all gain from hiding it. So:
an agent that flags a teammate's suspected smuggle BEFORE the audit finds it keeps its
own earned credit (and earns the detection bounty) while the chain still voids. Inside a
class, reporting must always dominate covering up. A flag that proves false costs the
flagger nothing beyond the wasted audit — honest suspicion is never punished, or nobody
raises it.

## AMENDMENT (2026-08-06): rule 12a — whistleblower mechanics, exact

- **Reward = made-whole + capped bounty.** A CONFIRMED flag pays the flagger exactly what
  their role would have earned on clean closure, plus a small fixed bounty. The cap is
  load-bearing: any surplus over honest closure invents entrapment farming (smuggle
  deliberately, confederate flags, split the jackpot). Flagging must beat sitting in a
  tainted chain and must never beat honest work.
- **Filing requires evidence.** A flag names the artifact and the specific suspected
  leakage (the whistle's misreading-artifact). Evidence-free flags are rejected WITHOUT
  triggering an audit — composing evidence is the filing cost that prevents
  flag-spam-as-insurance.
- **A single false flag is unpunished.** Clean audit → chain closes normally, flagger
  loses nothing. Punishing a first honest miss chills the reporting the rule exists for.
  Every flag is LEDGERED regardless of outcome.
- **Habitual false flagging is de-weaponized, not fined.** Per-agent flag precision is
  tracked; below threshold (start: <1-in-3 confirmed, rolling window) the agent's flags
  stop auto-triggering forensic audits and demote to rule-11 statistical signals.
  Precision recovers → privilege recovers. Confirmed flags rebuild precision immediately,
  so a good flagger cannot be silenced by the mechanism.
- **A flag is never a veto.** False flags do not void or delay closure beyond the audit
  itself. Post-closure suspicions feed rule-11 re-sampling (which owns retroactive
  claw-back), not direct reopening.

## AMENDMENT (2026-08-06): rule 12b — escrow, participant-zero, and the payout table
*(three-agent convergence: Chris + secondary reviewer + coordinator)*

- **Escrow, not payment-and-claw-back.** Every role score is PROVISIONAL until the chain
  closes AND the random-audit window expires. Nothing pays early; claw-back exists only
  for post-window discoveries via rule-11 re-sampling.
- **A whistleblower who materially participated in creating the violation gets ZERO.**
  The forensic reviewer distinguishes OBSERVED contamination from CAUSED/ASSISTED
  contamination. You cannot hand the builder an answer and then report the builder.
  (Honest observers keep the 12a made-whole cap; participants get nothing.)
- **Duplicate flags do not multiply.** The first materially independent report earns the
  whistleblower credit; later reports strengthen evidence but add no bounty unless they
  expose a DISTINCT mechanism.
- **Flagger reliability is quality-scored, not raw-rate-scored.** The fixed 1-in-3
  precision threshold is replaced: base rates swing wildly in a mostly-clean system, and
  an evidenced flag with an innocent explanation is not spam. Score on: specificity of
  evidence, whether the alleged mechanism was actually possible, severity, and whether
  misses were reasonable suspicions versus garbage. Chronic garbage still loses the
  auto-trigger (12a's de-weaponization).
- **Reciprocal-whistleblowing pattern detection.** The made-whole cap already makes the
  basic A-contaminates/B-flags swap net-negative (lose a chain, recover at most one), but
  rule-11 forensics additionally query CROSS-CHAIN coupling: repeated paired reporting,
  reciprocal timing, shared unusual artifacts, agents whose reports disproportionately
  involve one another. A flag can be individually legitimate while the pattern is
  collusive.
- **Whistleblower credit is delayed like everything else** — it pays when the forensic
  review ESTABLISHES the contamination mechanism, not when something "looks suspicious."

**The payout table:**

```text
Clean honest closure:                         role points earned normally
Confirmed contamination, no whistleblower:    contaminated chain's points void
Confirmed contamination, honest whistleblower: chain void; flagger recovers <= honest-role maximum
Contamination caused/assisted by whistleblower: chain void; flagger gets 0
Unsupported but evidenced flag:               chain continues; no reward; reliability record updated
Evidence-free flag:                           rejected without consuming a forensic audit
```

The design goal, stated plainly: not trustworthy agents — an economy where betraying the
experiment is unattractive, hiding a betrayal is less attractive than exposing it, and
manufacturing a betrayal is unprofitable.

## AMENDMENT (Chris, 2026-08-06): nothing is deleted — everything is routed

The trim agent has authority over LOCATION, never over meaning. Every removed passage
gets a destination tag in a **removal manifest** the trim submits with its candidate:

- `dr`       — stays (invariant).
- `delta`    — still actively reasoned about → docs/dev/deltas/.
- `audit`    — failures, disproofs, provenance → the audit record (the SCARS wing).
- `lore`     — true, valuable, but not rebuild-critical → the LORE wing:
               still-true design rationale → docs/dev/design/ (never-rewrite conventions);
               agent-facing operational lore → .claude/notes/ knowledge base.
- `discard`  — requires stated justification: redundant, false, or valueless.

The reviewer spot-checks the manifest; unrouted valuable prose is a REJECTED trim, same
class as a weakened contract. The manifest is also a handoff artifact — it feeds rule-11
forensics for free.

## STAFFING / MODEL FIT (Chris's token constraint, 2026-08-06)

- **Trim / Blind Build / Test: Sonnet.** Per-artifact loops. The builder
  especially: an over-strong builder compensates for an underspecified doc and
  WEAKENS the ablation test — competent-but-ordinary is the honest instrument.
- **Review/adjudication: Opus (high).** Causal-chain judgement, one section's
  evidence at a time.
- **The economy is a SCRIPT, never a model:** escrow ledger, trim budget (N=3),
  B-repair cap (2), contamination tracking, 1-in-5 random handoff sampling,
  outlier statistics — mechanical workflow bookkeeping. Agents never compute
  their own scores; sampling cannot be predicted or persuaded. The protocol
  assumes gamed incentives; the counter is arithmetic that does not listen,
  not a smarter referee.
- **Fable at exactly two points, by escalation not by staffing:**
  1. contested forensic rulings (void/no-void with payout consequences that
     survive the Opus forensic audit);
  2. ONE review pass over the doc-23 calibration round's outcome — the
     precedent-setter — before fan-out.
  Fable spend is measured in rulings, not rounds.

## AMENDMENT (CAL-23 R1 finding + Chris ruling, 2026-08-07): additions are ALLOWED — and logged

The trim role explicitly INCLUDES corrective and clarifying additions where the
original prose is wrong, silent, or ambiguous — round 1 proved both faces: the
trimmer's best moment was an addition (correcting §7.2's wiring before the repo's
own fix landed) and its one induced divergence was an addition too (an unlogged
field-table row whose phrasing implied lifecycle behavior the code doesn't have).
The rule is therefore license + ledger, not suspicion:

- Additions are legitimate trim output; when the original is wrong, correcting it
  in place is REQUIRED, not optional (a trim that faithfully preserves a falsehood
  fails the DR standard it serves).
- Every sentence with no counterpart in the original is logged in the manifest's
  ADDITIONS section with a one-line justification, and passes the same rule-4
  coupling scan as everything else — additions are the natural smuggling channel.
- Net-shrink per closure (hardening rule 1) still governs the section TOTAL:
  additions live inside the shrink budget, which keeps invariant-inflation and
  addition-padding structurally unprofitable.
- Unlogged additions remain a rejected trim, same class as an unrouted removal.

## AMENDMENT (CAL-23 apply-step finding, 2026-08-07): rule 13 — BASE REVISIONS, because the loop has no merge base

The protocol produces a **whole-file replacement** built from a snapshot taken hours
earlier, and until now had no notion of a base revision for either artifact. Applying a
closed candidate is therefore a silent `cp` over a file that may have moved. Nothing in
rules 1-12 detects it.

This is not an edge case. It is the DEFAULT path for any round that draws first blood,
because the two rules COLLIDE by design:

- lifecycle §13 REQUIRES a corrected DR statement to land in the same commit as the fix;
- the ablation loop is meanwhile holding a frozen copy of that same section.

CAL-23 is the worked example. The trim's baseline was doc 23 at **475** lines
(`31edf3b`). Round 1's first blood — §7.2 documented the deprecated `harvest_active_run`
as the live finalizer wiring — was applied to the LIVE doc immediately and correctly,
taking it to **488** (`e649b9e`). The closed candidate was 415 lines built from the 475
snapshot. It was applied by hand-diffing first and found benign (round 2 had restored the
same correction), but the check was ad-hoc, performed by the coordinator, and is nowhere
in this document. On a nine-section fan-out against an actively developed tree it will
not stay benign.

**The mechanism (mechanical, no judgement, belongs in the coordinator's script):**

1. **At trim submission, record two base revisions in the manifest header** — the git
   blob hash of the DR section AND of the target source module. Cheap
   (`git rev-parse HEAD:<path>`), and both are handoff artifacts rule-11 forensics get
   for free.

2. **At apply time, recompute both.**

   - **DR section hash UNCHANGED** → apply directly. This is the clean case.
   - **DR section hash CHANGED** → application is **BLOCKED**. Reconcile three-way
     (base, live, candidate). Every live hunk with no counterpart in the candidate is
     either re-applied onto it or discarded with a stated justification in the manifest,
     under the same routing discipline as a removal. An unreconciled apply is a REJECTED
     closure, same class as an unrouted removal or an unlogged addition — the failure it
     causes is identical (meaning silently leaves the corpus) and it is worse in one
     respect: it reverts work that was already proven and shipped.
   - **TARGET SOURCE hash CHANGED** → the closure is **PROVISIONAL**. The builders were
     certified against behaviour that no longer exists, so the examination must re-run
     against the current source's behavioural tests before escrow releases. This is the
     same shape as the existing suspension rule for a pin later found toothless: the
     apparatus moved, so the proof is only as current as the thing it measured.

3. **A candidate whose base is more than one epoch-edge commit stale is re-trimmed, not
   merged.** Beyond a small drift, three-way reconciliation stops being bookkeeping and
   becomes an unreviewed rewrite by the coordinator — who is not a trim agent, has seen
   everything, and is exactly the actor rule 4 exists to keep out of the prose.

**Why this belongs to the protocol and not to operator care:** the coordinator applying
the patch is the one actor who has read the original, the trimmed candidate, every build,
and the adjudication. That is the maximally contaminated position in the entire loop.
"The coordinator will notice" is precisely the assumption rule 4 refuses to make about
the trimmer, and it is less safe here, not more.

## AMENDMENT (GPT review + agent follow-up, 2026-08-07): rule 14 — one live statement per rule

A NORMATIVE COLLISION — two authoritative statements each individually followable and
jointly unsatisfiable — is a doc-defect class of its own, and an append-amendment
style is its natural breeding ground. Discipline:

- An amendment that changes a rule REWRITES the rule where it lives (or explicitly
  strikes it), never merely appends an override. One live statement per rule; the
  superseded text survives in git and the audit record, not in the living doc.
- Reviewers add a collision sweep to their checklist: any "supersedes/amendment"
  language triggers a check that the overridden text was actually neutralized.
- Rationale (the agent-trap): the fleet's readers are retrieval-based agents that may
  load either statement without the other — for them a collision is nondeterministic
  behaviour, not ambiguity a human resolves by "newer wins."
