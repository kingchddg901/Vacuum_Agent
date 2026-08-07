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
- preserve exact boundary conditions and required behavior;
- make corrective or clarifying additions where the original prose is wrong, silent, or ambiguous — correcting a known falsehood in place is **required**, not optional, since a trim that faithfully preserves a falsehood fails the disaster-recovery standard it serves.

It must not weaken a contract merely to make the document shorter.

## The removal manifest

The trim agent has authority over **location**, never over meaning. Every removed passage — and every added sentence with no counterpart in the original — gets a destination tag in a **removal manifest** submitted with the candidate:

- `dr` — stays (invariant).
- `delta` — still actively reasoned about → docs/dev/deltas/.
- `audit` — failures, disproofs, provenance → the audit record (the scars wing).
- `lore` — true, valuable, but not rebuild-critical → the lore wing: still-true design rationale → docs/dev/design/ (never-rewrite conventions); agent-facing operational lore → .claude/notes/ knowledge base.
- `discard` — requires a stated justification: redundant, false, or valueless.

Additions are logged in the manifest's ADDITIONS section with a one-line justification and pass the same coupling scan (hardening rule 4) as everything else — additions are the natural smuggling channel, since the trimmer sees the implementation and authors the blind builder's only input. Unlogged additions are a rejected trim, the same class as an unrouted removal.

Both removals and additions are held inside the net-shrink budget (hardening rule 1): the section total must still shrink, so additions cannot be used to pad the specification back up for points.

The reviewer spot-checks the manifest; unrouted valuable prose is a rejected trim, the same class as a weakened contract. The manifest is also a handoff artifact — it feeds hardening-rule-11 forensics for free.

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

The build agent must be **blind**. A merely isolated worktree does not satisfy this boundary if the original target implementation remains reachable from it — the concrete sandbox construction that does satisfy it is hardening rule 10.

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

**Every revised candidate must be tested by a fresh blind builder.** Hardening rule 3 sets how many independent fresh builders a discovery-round closure requires.

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

Long historical explanations may leave DR because their provenance has a durable home in the audit record.

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

# Scoring Hardening Rules

The following rules close exploit and collusion classes in the scoring surface and are part of the protocol from the first run:

1. **Net-shrink per closure.** Every closed round leaves the section strictly smaller than it started. This kills reviewer invariant-inflation structurally — a document that must shrink to close cannot be regrown for points. Corrective or clarifying additions (see the removal manifest under Trim Agent) count against the same budget: they must fit inside the shrink, which keeps invariant-inflation and addition-padding equally unprofitable.
2. **A/B/C verdicts pay on their own closures.** Verdict A (builder error) closes when a fresh builder greens with unchanged prose; verdict B (experiment error) closes when the repaired boundary yields a green; verdict C (test error) closes when the repaired test is shown to bite. Without this, every ambiguous failure bends toward D.
3. **2-of-2 fresh builders on discovery rounds**, escalating to 2-of-3 on disagreement. A single-sample closure is a coin-flip certification, and re-litigating churn is revenue. Clean first-pass trims may still close on one builder.
4. **Implementation-coupling is a rejection class.** Trimmed prose carrying information not derivable from the public contract — internal names, incidental structure, test-expected magic values — is rejected before any build by the **coupling scan**. The trimmer sees the implementation and authors the blind builder's only input, so answer-smuggling is the protocol's worst failure mode, and it needs no collusion, only optimization pressure.
5. **D verdicts require a misreading artifact.** The reviewer must reproduce, from the trimmed prose alone, the chain of reasonable readings that yields the wrong implementation. If it cannot be articulated, the verdict is A instead. This blocks sandbagged-build farming.
6. **Trim budget.** N candidate submissions per section (start N=3). A failed trim burns the three most expensive roles; gambling must cost the gambler.
7. **B-repair cap.** Two boundary repairs per section; after that the boundary spec itself is the defect and escalates for a ruling.
8. **Biting-pin bounty.** Testers earn a small immediate bounty, outside the chain, for novel pins certified to kill a deliberate breakage of the guarded behavior — otherwise the tester's rational strategy is to run only the existing suite and never risk a C.
9. **Closed-invariant ledger.** Each closure records the invariant and its misreading. Reopening a ledgered invariant needs new evidence; re-proving one pays nothing.
10. **The sandbox generator is a prerequisite, not a detail.** Blind builds run in a constructed directory containing only the trimmed section, allowed interfaces, and dependency stubs — no repo checkout, no `.claude/notes`, no project memory. An isolated worktree is not blind: the target implementation and its tests are one grep away.
11. **Statistical handoff audits.** Per-artifact checks (rules 4 and 5) catch clumsy smuggling; a careful smuggler stays under any single-artifact threshold. The control for that lives at the population level:
    - **Score ledger per agent-instance and per pair.** Track closures, discovery rounds, green rates, and verdict distributions — individually and per trimmer×builder pair, because collusion is invisible in individual stats and shows up as one pair's anomaly.
    - **Two audit triggers:** a **random baseline** — a fixed fraction of closures (start 1 in 5) gets a handoff audit unconditionally, so staying under statistical thresholds is never safe — and a **statistical trigger** — any agent or pair whose points, green rate, or verdict mix departs the cohort norm (the outlier you would notice on a scoreboard). Signature patterns worth standing queries: a trimmer whose large deletions always green on the first build (coupling suspect); a builder whose greens concentrate on one trimmer's prose (pair suspect); a reviewer whose D-rate is an outlier (inflation suspect).
    - **The audit itself** re-examines the handoff artifacts forensically. The measurable smoking gun is **incidental similarity**: a blind reconstruction that matches the original implementation's incidental choices — private helper names, internal structure, ordering the contract does not force — beyond chance is carrying smuggled answers, whatever the prose looks like. Trimmed prose gets the coupling scan; new tests get the over-pinning scan.
    - **Consequences:** a confirmed smuggle voids the closure (points clawed back, ledger entry reopened, the section re-runs with fresh agents), and the implicated agent's or pair's prior closures get re-sampled — fraud clusters, and one confirmed case is never treated as isolated.
12. **A confirmed smuggle voids the whole class, with an escrowed whistleblower carve-out.** A confirmed smuggled answer invalidates the entire chain, not just the smuggler: the loop's agent group for that section (trimmer, builder(s), tester, reviewer) is one class, and if one member cheated, the class fails — nobody scores, the closure is void, and the section re-runs with an entirely fresh class. There is no "I didn't smuggle, I just benefited" position: benefiting from a tainted chain costs you the chain. Collective liability makes every member a stakeholder in every other member's honesty — the builder has reason to refuse suspiciously helpful prose, the reviewer has reason to run the coupling scan hard, the tester has reason to probe a reconstruction that greens too easily.

    Collective punishment alone would align a tainted class around concealment, so an agent that flags a teammate's suspected smuggle before the audit finds it keeps its own earned credit and earns a capped detection bounty, even though the chain still voids. Inside a class, reporting must always dominate covering up.

    **Whistleblower mechanics:**
    - **Escrow, not payment-and-clawback.** Every role score is provisional until the chain closes *and* the random-audit window (rule 11) expires; nothing pays early, and claw-back for post-window discoveries runs through rule-11 re-sampling.
    - **Reward = made-whole + capped bounty.** A confirmed flag pays the flagger exactly what their role would have earned on clean closure, plus a small fixed bounty. The cap is load-bearing: any surplus over honest closure invents entrapment farming (smuggle deliberately, confederate flags, split the take). Flagging must beat sitting in a tainted chain and must never beat honest work.
    - **A whistleblower who materially participated in creating the violation gets zero.** The forensic review distinguishes OBSERVED contamination from CAUSED/ASSISTED contamination — handing the builder an answer and then reporting the builder earns nothing; honest observers keep the made-whole cap.
    - **Filing requires evidence.** A flag names the artifact and the specific suspected leakage. Evidence-free flags are rejected without triggering an audit — composing evidence is the filing cost that prevents flag-spam-as-insurance.
    - **A single false flag is unpunished.** A clean audit lets the chain close normally and costs the flagger nothing; every flag is ledgered regardless of outcome, so honest suspicion is never chilled.
    - **Duplicate flags do not multiply.** The first materially independent report earns the whistleblower credit; later reports strengthen evidence but add no bounty unless they expose a distinct mechanism.
    - **Flagger reliability is quality-scored, not raw-rate-scored:** specificity of evidence, whether the alleged mechanism was actually possible, severity, and whether misses were reasonable suspicions versus noise — because base rates swing wildly in a mostly-clean system and an evidenced flag with an innocent explanation is not spam. Chronic low-quality flagging still loses the auto-trigger: below a quality threshold, an agent's flags stop auto-triggering forensic audits and demote to rule-11 statistical signals; confirmed flags rebuild the record immediately, so a good flagger cannot be silenced by the mechanism.
    - **Reciprocal-whistleblowing pattern detection.** Rule-11 forensics additionally query cross-chain coupling: repeated paired reporting, reciprocal timing, shared unusual artifacts, agents whose reports disproportionately involve one another. A flag can be individually legitimate while the pattern is collusive — the made-whole cap already makes the basic swap-flags-for-mutual-cover net-negative, but the pattern query catches subtler versions.
    - **A flag is never a veto.** False flags do not void or delay closure beyond the audit itself. Post-closure suspicions feed rule-11 re-sampling, which owns retroactive claw-back, not direct reopening.
    - **Whistleblower credit is delayed like everything else** — it pays when the forensic review establishes the contamination mechanism, not when something looks suspicious.

    **The payout table:**

    ```text
    Clean honest closure:                          role points earned normally
    Confirmed contamination, no whistleblower:      contaminated chain's points void
    Confirmed contamination, honest whistleblower:  chain void; flagger recovers <= honest-role maximum
    Contamination caused/assisted by whistleblower: chain void; flagger gets 0
    Unsupported but evidenced flag:                 chain continues; no reward; reliability record updated
    Evidence-free flag:                             rejected without consuming a forensic audit
    ```

    The design goal is not trustworthy agents — it is an economy where betraying the experiment is unattractive, hiding a betrayal is less attractive than exposing it, and manufacturing a betrayal is unprofitable.
13. **Base revisions.** The protocol produces a whole-file replacement built from a snapshot of the DR section and the target source, so applying a closed candidate needs an explicit base to compare against — without one, applying is a silent overwrite of a file that may have moved since the snapshot was taken.

    Mechanism:
    - At trim submission, record two base revisions in the manifest header: the git blob hash of the DR section and of the target source module (cheap via `git rev-parse HEAD:<path>`; both are handoff artifacts rule-11 forensics get for free).
    - At apply time, recompute both hashes.
      - **DR section hash unchanged** → apply directly.
      - **DR section hash changed** → the apply is **blocked** pending three-way reconciliation (base, live, candidate). Every live hunk with no counterpart in the candidate is either re-applied onto it or discarded with a stated justification in the manifest, under the same routing discipline as a removal. An unreconciled apply is a rejected closure, the same class as an unrouted removal or an unlogged addition — the failure it causes is identical (meaning silently leaves the corpus), and it is worse in one respect: it reverts work that was already proven and shipped.
      - **Target source hash changed** → the closure is **provisional**. The builders were certified against behavior that may no longer exist, so the examination re-runs against the current source's behavioral tests before escrow releases — the same shape as the suspension rule for a pin later found toothless (see Important Interaction with the Test Audit): the apparatus moved, so the proof is only as current as the thing it measured.
      - A candidate whose base is more than one epoch-edge commit stale is re-trimmed, not merged. Beyond a small drift, three-way reconciliation stops being bookkeeping and becomes an unreviewed rewrite by the coordinator, who is not a trim agent, has seen everything, and is exactly the actor rule 4 exists to keep out of the prose.
      - A stale base is never silently overwritten.

    This mechanism belongs to the protocol rather than to operator care: the coordinator applying a patch has read the original, the trimmed candidate, every build, and the adjudication — the most contaminated position in the entire loop. Assuming the coordinator will simply notice a drifted base is the same assumption rule 4 refuses to make about the trimmer, and it is less safe here, not more.
14. **One live statement per rule.** A normative collision — two authoritative statements each individually followable and jointly unsatisfiable — is a doc-defect class of its own. An amendment that changes a rule rewrites the rule where it lives, or explicitly strikes it — never merely appends an override. One live statement per rule; superseded text survives in git and the audit record, not in the living document. Reviewers include a collision sweep in their checklist: any "supersedes/amendment" language triggers a check that the overridden text was actually neutralized. This matters because the protocol's readers are retrieval-based agents that may load either statement without the other — for them a collision is nondeterministic behavior, not an ambiguity a human resolves by "newer wins."

---

# Rollout Plan

Sequencing constraint: **ablation only runs on truth-passed docs** — trimming a stale baseline confuses missing invariants with unapplied fixes.

1. **Calibration: doc 23 (error tracker).** Self-contained module, invariant-dense, biting tests, cheap sandbox. Runs the full loop before anything else.
2. **Confirmation: doc 18 (onboarding manager),** once its truth patch lands — the cleanest sandbox in the corpus (data + hass constructor). Run only if calibration leaves doubts about generality; otherwise optional.
3. **Fan-out order.** The doc numbers are landing order; the module graph is mutually recursive (5 of 26 dependency-free, the rest one cluster — see `DOC-DEPENDENCY-MAP.md`), so no topological ablation order exists. Proof composition does not need one: closures lean on other docs' interface statements, which all exist from day one. The fleet runs atom-first, then the README's reading order (doc 32): the atom's sections — 03 (spine/data), 21/22 (adapter), 07 (queue/dispatch), 08 (rooms), 06 (active_job) — close first, because with just those proven a rebuilt system CLEANS; then the remainder top-to-bottom (01 → 02 → 04 → 05 → 30 → 09…15/31 → 16-18 → 25/26/29 → 28). The compensating rule that replaces sequencing: **any closure that alters a doc's PROVIDES surface flags every dependent doc's closure provisional** (dependents per `DOC-DEPENDENCY-MAP.md`). Trims must preserve interface statements regardless — they are contract.

   Invariant-density decides LOOP DEPTH per doc only (full discovery loop vs trim+single-build vs schema-reconstruction for shapes docs like 03/22) — never sequence.

   FRONTEND docs get the TRIM stage + coupling scan only — blind reconstruction of UI prose has no biting test surface and would certify nothing.

   **User guides are exempt from ablation entirely — not even trim+coupling.** They are the most abstract layer, and their standing update policy is separate from ablation: touched only when an actual interface changes — a new surface, control, flow, or setting the user can see. Internal-mechanism changes, phrasing accuracy, and doc-hygiene churn never propagate to them.

   Three sequences share the atom-first principle without being the same sequence — do not collapse them:
   - *Ablation order* (this section): which docs get experimentally minimized first.
   - *Reading order* (the README): how a maintainer best learns the existing system.
   - *Recovery progression* (00 §0): which capabilities come online — spine, then adapter/dispatch/rooms/job capability with the manager accreting wiring, then rings against a working core. The numbered docs are evidence packages for those capabilities, not one-file-at-a-time build instructions; "03 → 21/22 → 07 → 08 → 06 then rings" names the ablation priority, never the literal executable reconstruction sequence.
4. **Per-doc outputs:** the trimmed DR section (net-smaller), migrated history into the audit record with provenance tags, ledger entries for every earned invariant, and the section's status row updated.
5. **Suspension rule:** any test-audit finding that a relied-upon pin was toothless marks the affected sections provisional and re-eligible, per the protocol's own apparatus clause (see Important Interaction with the Test Audit).
6. **Advanced guides sequence after disaster recovery.** Advanced-guide patches (adv-contract, adv-guides) do not apply until the DR reconciliation completes: in-flight workflow runs finish and then park, applied only once DR is done. Mechanical fixes (adv-contract's services/events corrections) ride the same hold — copy-paste correctness matters, but a stable DR baseline matters first.

---

# Staffing and Model Fit

- **Trim / Blind Build / Test: Sonnet.** Per-artifact loops. The builder especially: an over-strong builder compensates for an underspecified doc and weakens the ablation test — competent-but-ordinary is the honest instrument.
- **Review/adjudication: Opus (high).** Causal-chain judgement, one section's evidence at a time.
- **The economy is a script, never a model:** escrow ledger, trim budget (N=3), B-repair cap (2), contamination tracking, random handoff sampling, outlier statistics — mechanical workflow bookkeeping. Agents never compute their own scores; sampling cannot be predicted or persuaded. The protocol assumes gamed incentives; the counter is arithmetic that does not listen, not a smarter referee.
- **Fable is used at exactly two points, by escalation rather than by staffing:**
  1. contested forensic rulings (void/no-void decisions with payout consequences that survive the Opus forensic audit);
  2. one review pass over the doc-23 calibration round's outcome — the round every other closure calibrates against — before fan-out.

  Fable spend is measured in rulings, not rounds.
