# Documentation Epoch and Reconciliation Model

**Status:** Working documentation doctrine  
**Scope:** Vacuum Agent engineering documentation  
**Purpose:** Separate present-tense rebuild truth, active engineering change, and permanent historical evidence without losing any of them.

---

## 1. Core premise

Before the audit system existed, the developer documentation had to do too many jobs at once.

It was simultaneously:

- the **disaster-recovery specification** needed to reconstruct a subsystem correctly;
- the **working engineering memory** for current development;
- and the **historical record** of failures, rejected interpretations, odd guards, false assumptions, and the reasoning that produced the current implementation.

That was necessary because there was nowhere else for the history to live. Removing old reasoning from the developer documentation would have meant actually losing it.

The audit record changes that.

Vacuum Agent can now maintain three distinct bodies of documentation, each optimized for a different question:

1. **Disaster-Recovery documentation:** What is true now?
2. **Development documentation:** What differs from the last reconciled truth, and what are we currently learning or changing?
3. **Audit record:** What happened, what failed, what was disproved, and why did the surviving design win?

The goal is not to make the documentation less honest. The goal is to put each kind of truth in the place where it is most useful.

---

## 2. Disaster-Recovery documentation: the reconciled baseline

The Disaster-Recovery (DR) set is the authoritative description of the system at the most recently closed documentation epoch.

It is a **present-tense rebuild specification**.

A reader or agent with no other context should be able to reconstruct the subsystem's correct behavior, interfaces, persistence, lifecycle, algorithms, and important refusal conditions from the DR documentation alone.

### 2.1 Precision standard

DR documentation does not become less rigorous when historical narrative is removed.

It becomes more purely rigorous.

Exact distinctions remain part of the contract:

- `> 1` is not `>= 1`;
- `None` is not `0`;
- missing is not empty;
- `unavailable` is not `false`;
- before an `await` is not after an `await`;
- once per room is not once per phase;
- current map is not requested map;
- historical unit metadata is not today's configured unit;
- an inferred value is not an observed value.

If one character, ordering rule, sentinel, ownership boundary, or timing condition can change behavior, the DR documentation must preserve it exactly.

### 2.2 What belongs in DR

DR documentation contains the current surviving truth, including:

- exact algorithms and formulas;
- schemas and persisted record shapes;
- API, service, event, and entity contracts;
- ownership boundaries;
- lifecycle and teardown behavior;
- state-transition rules;
- capability and adapter semantics;
- exact boundary conditions and sentinels;
- required guards and refusal behavior;
- ordering requirements;
- reconstruction-critical assumptions;
- invariants that must survive a rewrite;
- enough rationale to prevent a future maintainer or agent from "simplifying" an essential invariant away.

### 2.3 What does not need to remain in DR

DR does not need to retain the complete path by which the current rule was discovered.

It should not require a reader to sort through:

- the first broken implementation;
- the second attempted fix;
- the test that falsely passed;
- the theory that hardware later disproved;
- the agent disagreement that preceded the final explanation;
- or every commit involved in arriving at the present rule.

The final DR rule may instead say, for example:

> Establish the claim before the `await`. State may change while the coroutine is suspended, so establishing the claim afterward does not provide the required exactly-once guarantee.

That preserves both the current rule and the reason the rule must remain true, without forcing the reader to reconstruct the entire failure history.

The full history belongs in the audit record.

---

## 3. Development documentation: the current-epoch diff

Development documentation is the **working engineering memory for the current epoch**.

After a DR baseline has been reconciled, the development set should not need to repeat the entire subsystem description. It can instead behave as an overlay or diff against the authoritative DR baseline.

The DR set says what was true at the last reconciliation boundary.

The development set says what has changed, what is changing, and what is still being reasoned about since then.

### 3.1 Diff-oriented structure

A development document may point directly at a DR section and describe only its current differences.

For example:

> **Subsystem 08 — Current-epoch differences from DR**  
> **§53 — Room-source refresh**
>
> DR §53 remains authoritative except for the following current-epoch differences:
>
> 1. Refresh now returns a tri-state result instead of `None`.
> 2. Dispatch refuses stale segment IDs after an explicit refresh failure.
> 3. Concurrent refresh requests are coalesced.
> 4. ...
> 8. ...

The development section can then carry the full active reasoning behind those differences.

If a DR section has no development delta, there is no need to duplicate it. **No dev delta means the DR baseline remains authoritative for that section.**

### 3.2 What belongs in development docs

Development documentation is allowed to be painfully honest.

It may contain:

- active hypotheses;
- open questions;
- implementation experiments;
- competing interpretations;
- failed approaches;
- tests that passed when they should have failed;
- hardware observations;
- newly discovered edge cases;
- model or agent disagreements;
- temporary constraints;
- why a change currently appears necessary;
- evidence that is not yet fully adjudicated;
- current test and replay evidence;
- behavior that differs from the last DR baseline;
- known gaps awaiting the next audit.

Development documentation is not required to present a clean historical story. Its job is to preserve the reasoning of active engineering accurately enough that the next audit has the evidence necessary to adjudicate it.

### 3.3 Development docs are not another canonical specification

The dev set should not quietly become a second full copy of DR.

Its relationship should be explicit:

> **DR = reconciled baseline.**  
> **Dev = current-epoch delta against that baseline.**

This reduces both human and agent ambiguity. A new investigator should not have to compare two enormous present-tense descriptions and guess which statement is newer.

The reading rule can be simple:

> Read the relevant DR section first. Then read the matching development delta. The delta overrides the baseline only where it explicitly says it differs.

---

## 4. Audit record: permanent engineering provenance

The audit record is the **permanent historical ledger**.

It preserves the evidence and reasoning that no longer belongs in the present-tense DR specification but must not be forgotten.

### 4.1 What belongs in the audit record

The audit record preserves, where relevant:

- defects that actually shipped;
- false positives and why they were killed;
- incorrect assumptions;
- failed fixes;
- tests that produced false confidence;
- hardware evidence that changed the theory;
- code/doc divergences;
- source-versus-fixture disagreements;
- impossible test states;
- causal chains;
- finding → premise → evidence → interpretation → correction;
- why an apparently reasonable implementation was rejected;
- provenance for important architectural scars;
- superseded behavior that is still useful for understanding why the current invariant exists;
- audit decisions, confidence, and unresolved items carried forward.

The point is not to preserve embarrassment or trivia.

The point is to make old mistakes expensive to repeat.

### 4.2 The audit record is where the blood stays on the walls

The DR set may say:

> Use the commanded-dock guard when resolving a recharge transition. Ordinary commanded returns can be observationally indistinguishable at this layer, so dock state alone is insufficient evidence.

The audit record can preserve:

- the earlier interpretation;
- the reproducer;
- the fix attempt;
- the hardware run that disproved the first mechanism;
- the corrected mechanism;
- the regression proof;
- and the final invariant.

That history remains available without forcing every future DR reader through it.

---

## 5. An epoch is not a release

A documentation epoch is **not** a version number and is **not** a release boundary.

An epoch is the period between two authoritative audit/reconciliation boundaries.

Several releases may occur inside one epoch.

An epoch may contain:

- feature releases;
- bug-fix releases;
- hotfixes;
- refactors;
- documentation changes;
- adapter work;
- test changes;
- and substantial behavioral evolution.

The important property is that all of those changes are still being described relative to the same reconciled DR baseline.

A useful definition is:

> **An epoch is the lifetime of a set of development deltas against one reconciled DR baseline.**

A release answers:

> What did users receive in this version?

An epoch answers:

> What body of engineering change and reasoning has accumulated since the last time the system's truth was comprehensively reconciled?

The two boundaries may sometimes coincide, but they do not have to.

---

## 6. The epoch-closing audit is the reconciliation operation

The audit is not only a code review. It is the operation that closes one documentation epoch and establishes the baseline for the next.

During the epoch, the working model is:

```text
Last reconciled DR baseline
        +
Current-epoch development deltas
        +
Source / tests / replay / hardware evidence
        |
        v
   Epoch-closing audit
```

The audit then sorts the accumulated knowledge by destination:

```text
Development reasoning and deltas
        |
        +---- surviving current truth ----> Disaster-Recovery docs
        |
        +---- failures / rejected theories
        |     / superseded behavior
        |     / provenance ----------------> Audit record
        |
        +---- unresolved work -------------> Next epoch's dev docs
```

### 6.1 What happens to DR at epoch close

The DR set is reconciled to the surviving current system.

It receives:

- the final behavior;
- exact contracts;
- exact algorithms;
- exact boundary conditions;
- final ownership and lifecycle;
- required guards;
- and the minimal durable explanation of why a non-obvious invariant must remain that way.

It does not inherit every failed path that led there.

### 6.2 What happens to the audit record

The audit record receives the historical evidence worth preserving:

- failures;
- disproved interpretations;
- rejected fixes;
- false-green tests;
- hardware contradictions;
- adjudication notes;
- provenance;
- and the reasoning chain behind important scars.

### 6.3 What happens to development docs

Once the surviving dev delta has been folded into DR and the historical reasoning has been preserved in the audit record, that old delta no longer needs to remain active development context.

The next epoch can begin with a clean relationship:

> DR describes the newly reconciled system.  
> Dev begins accumulating only the differences that arise after that point.

The dev diff can therefore collapse toward empty at an epoch boundary instead of growing forever.

---

## 7. Core post-audit invariant

After an epoch-closing audit:

> **Nothing important from that epoch should exist only in the development documentation.**

Every meaningful piece of knowledge should have been classified.

Use these questions:

### 7.1 Does losing this cause the present system to be rebuilt incorrectly?

Put it in **Disaster-Recovery documentation**.

### 7.2 Does losing this make us likely to repeat an old mistake, lose the provenance of a decision, or forget why a conclusion changed?

Put it in the **audit record**.

### 7.3 Is this reasoning still active, unsettled, or part of work that continues beyond the audit boundary?

Carry it into the **next epoch's development docs**.

Some information may legitimately appear in more than one place, but the purpose of each copy must remain different.

DR preserves the invariant.

The audit record preserves how the invariant was earned.

Development preserves what has not yet been reconciled.

---

## 8. Authority and reading order

At any point inside an epoch, the authority order should be explicit.

For a subsystem section:

1. Read the last reconciled **DR section**.
2. Read the matching **development delta**, if one exists.
3. Treat the delta as overriding DR only where the difference is explicit.
4. Use the **audit record** for provenance, failure history, and rationale beyond what is necessary to reconstruct the current behavior.

This prevents an agent or maintainer from treating historical narrative as current behavior or treating a working hypothesis as settled truth.

At the next epoch-closing audit, all three are reconciled against implementation and evidence again.

---

## 9. Relationship to testing and audit rigor

This documentation model exists partly because documentation is an input to the audit, not decoration around it.

The audit must be able to distinguish:

- a code defect;
- a documentation defect;
- an intentional documented design choice;
- a current-epoch change that has not yet been folded into DR;
- and a historical failure that is no longer part of the current contract.

A clean DR baseline plus explicit dev deltas gives the auditor a tractable statement of current intent.

The precision requirement therefore remains severe. A wrong equality sign, sentinel, ordering rule, scope, unit source, or ownership statement can cause an auditor or test author to construct the wrong expected behavior and then "fix" correct code to match incorrect documentation.

The documentation is part of the measurement apparatus.

---

## 10. Why this model is possible now

Before the hostile audit process existed, the development docs were the only durable place to preserve the reasoning behind the system.

They therefore had to serve as both:

- rebuild specification;
- and audit history.

That was not bad documentation. It was a necessary consequence of having only one durable memory store.

Now the audit itself produces a durable evidence ledger.

That allows historical reasoning to migrate out of DR without being destroyed.

The result is not less honesty. It is **better separation of honest information by purpose**:

- DR answers: **What exactly must be true now?**
- Dev answers: **What has changed or remains unsettled since the last reconciliation?**
- Audit answers: **How did we learn this, what failed, and why did this answer survive?**

---

## 11. Compact doctrine

The entire model can be reduced to the following rules:

> **DR is the last reconciled truth.**
>
> **Development docs are the current epoch's diff against that truth.**
>
> **The audit record is permanent provenance: failures, rejected theories, evidence, and the reasoning that produced the surviving design.**
>
> **An epoch is not a release. It is the lifetime of a set of deltas against one reconciled DR baseline, and it may contain several releases.**
>
> **An epoch-closing audit folds surviving behavior into DR, moves historical reasoning into the audit record, and carries only genuinely unresolved work into the next epoch.**
>
> **After that reconciliation, nothing important from the closed epoch should exist only in development documentation.**

That gives Vacuum Agent a documentation lifecycle instead of an ever-growing document that must simultaneously represent present truth, active thought, and historical scar tissue.

---

## 12. The plain-language key

> **Design — this is why.**
> **DR — this is how.**
> **Dev deltas — this is what I'm changing right now.**
> **Audit record — this is what happened, and what it cost to learn.**

Every document answers exactly one of these questions. If a passage answers a different
question than the document it lives in, it belongs somewhere else — that is the entire
routing rule, compressed.

---

## 13. Epoch-edge fixes: the fix and its DR statement move together

The truth pass documents what the code DOES — including its bugs (a bug is flagged as a
bug signal, never papered over in prose). But when a fix for a pass-found bug lands at the
epoch edge, the DR statement it disproves is corrected **in the same commit**, verified
against source like any reconciled statement. Do not bless a description you already know
is false and queue its correction as a next-epoch delta: that manufactures drift out of
process.

The delta ledger is a **deferral buffer, not a mandatory queue**. It exists for work whose
doc-side cannot ride the change — mid-feature churn, no verification capacity, meaning not
yet settled. If you can update the DR statement with the fix, you must; a delta entry for
a change whose documentation was ready is a process failure, not compliance.

(Ruled by Chris 2026-08-06, during the epoch-1-edge fix wave; the same-commit pattern was
already the practice for every fix that wave landed.)
