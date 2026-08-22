# 00 — How These Docs Work

> **Scope:** the shape of the documentation corpus and the rules for writing in it.
> This replaces the Disaster-Recovery standard and the documentation-epoch model, both
> of which are retired to [`history/`](history/disaster-recovery-standard.md) with the reasons recorded.

---

## 1. Three shelves

Every document in `docs/dev/` sits on exactly one of three shelves. If you cannot say
which, it is on the wrong one.

| Shelf | Answers | Where | When it is wrong |
|---|---|---|---|
| **NOW** | *What does the system do today?* | `docs/dev/NN-*.md` | The **doc** is wrong. Code wins, always. |
| **DESIGN** | *How do we want it to work — how would we change it next?* | `docs/dev/design/` | **Either side may be wrong.** See §3. |
| **HISTORY** | *What did we try, how did we find it, and what failed?* | `docs/dev/history/` | Never. It is a record of what was true then. |

Cross-link freely between them. A NOW doc explaining a non-obvious rule should point at
the HISTORY entry that explains how the rule was earned, rather than telling the story
inline.

### 1.1 NOW — the subsystem guides

The numbered guides describe the system **as it is**. They are complete references, not
diffs against anything: a competent reader should be able to work on the subsystem from
the guide plus the source.

Code is authoritative. A NOW doc that disagrees with the code is simply stale, and the
fix is to correct the doc.

> This is a change. The previous model declared these docs to be a *diff* against a
> canonical Disaster-Recovery baseline, and said explicitly that they were "not another
> canonical specification". In practice they were never written that way — most open with
> "Complete implementation reference" — so the declaration was the part that was wrong.
> The deeper reason it could not hold is §5a: these docs are sediment, and a diff needs
> two coherent states to sit between.

### 1.2 Invariants — *"do this, or this happens"*

An invariant is not a preference and not a style note. It states a rule **and the
consequence of breaking it**, because a rule without a consequence gets optimised away by
the next person who finds it inconvenient.

> ✅ *Never edit `.storage` directly — HA rewrites it on shutdown and your change becomes
> a `.corrupt` backup.*
> ❌ *Avoid editing `.storage`.*

If you cannot name what goes wrong, you have a convention, not an invariant. Say so.

### 1.3 DESIGN — how we want it to work

`docs/dev/design/` holds intent: how a thing should work, or how we would change it next.

**A design doc must be a PLAN to live here.** If it is exploratory — options being weighed,
nothing decided — it is *pre-design* and stays out of the repo. The test is whether a
reader could act on it.

**Two sub-shelves, because a design does not stop being useful when it is built:**

| | |
|---|---|
| `design/planning/` | Decided, not built. A reader could pick it up and implement it. |
| `design/shipped/` | Built. Kept because it still answers *"why is it like this?"* — a question that stays live long after the work lands. |

**A shipped design is NOT maintained against the code**, and that is load-bearing rather
than lax. It is a touchstone: what was decided, as it was decided. §3 asks a reader to
adjudicate when a design and the code disagree — and that question only exists while the
design still says what it originally said. Edit it to track the implementation and it agrees
with the code forever, which deletes the evidence of exactly the drift it was meant to catch.

It can still evolve, but only in one direction: when the DESIGN is revisited, not when the
code moves. That is the difference from `history/`, which never changes at all.

So a shipped design does not go to `history/`, and the reason is the question each shelf
answers rather than how either is maintained — neither is. **History is what we stopped
doing; shipped design is why we do what we do.** A design abandoned rather than built belongs
in `history/`.

NOW docs cite these as rationale — one calls `map-state-source` "the design rationale",
another defers to it as the authoritative reference — which is why a live doc may point at a
shelf nobody updates. It is being pointed at a decision, not at a description.

### 1.4 HISTORY — what we tried, and what failed

`docs/dev/history/` holds the record: how a rule was discovered, what was attempted, what
was ruled out and why. **Failures belong here explicitly.** A retired approach with no
recorded reason gets proposed again in six months, confidently.

Nothing here is maintained against the code. It is dated and left alone.

**This shelf fills as a by-product of fixing NOW docs — it is not stocked deliberately.**
Resolving a stack (§5a) leaves displaced strata: a paragraph that was true, is no longer,
and is worth keeping. That is history, and this is where it lands. So the shelf grows in
step with the corpus being repaired, which is the right rate — an empty history shelf
means nothing has been excavated yet, not that nothing was ever tried.

It was already happening before the shelf existed. `room-bounds-from-traces.md` was cut
out of [11 — Mapping system](11-mapping-system.md) on 2026-08-14 because it was four
pages of present-tense algorithm describing deleted code; with no history shelf to put it
on it went to `design/`, where it sat declaring "This is HISTORY" in its own first line
until 2026-08-16. The excavation was right; only the destination was missing.

> **Corollary:** do not go hunting through private notes for things to promote here. If a
> fact never surfaces while repairing a doc, it was not load-bearing for a reader of that
> doc.

---

## 2. The corpus is read by AGENTS as well as people

This is not decoration; several rules below only make sense in that light. A human
resolves a contradiction with common sense ("the newer one wins"). A retrieval-based
reader may load either statement **without its sibling** and follow it faithfully. So a
contradiction is not ambiguity here — it is nondeterministic behaviour.

---

## 3. When a DESIGN doc and the code disagree, ADJUDICATE — do not assume the doc is stale

For NOW docs the rule is simple: code wins. For DESIGN docs it is not, and this is the
part most easily got wrong.

A design doc says how we *want* it to work. If the code differs, **either** the design was
never implemented, **or** the implementation drifted from a decision that still stands.
Those need opposite fixes, and you cannot tell which by reading the doc.

**Establish which way the drift went before changing anything.** Check when each side was
written and what landed in between. A design describing a deliberate decision, with code
that quietly does something else, is a *code* defect wearing a doc's clothes.

> This generalises a rule earned the hard way: a reconstruction that disagrees with the
> code is a **bug signal**, not a documentation error. The `clean_times` Eufy-ism surfaced
> exactly that way — the "wrong" guess was closer to correct than the buggy clamp.

### 3a. Drift is not the problem. SEMANTIC drift is.

The two sides own different things, and they are allowed to move independently:

| | owns | says |
|---|---|---|
| **design** | intent and shape | we are doing this thing · these responsibilities are separated this way · this behaviour must exist · these tradeoffs were chosen |
| **code** | mechanism | here is the class · the call path · the guard · the exact structure that implements it |

A refactor can change *how* something is implemented beyond recognition while the design
stays perfectly true. A design can evolve at its own level without prescribing every
detail beneath it. Neither is drift.

**The warning sign is when the code stops being a plausible implementation of the design.**
If the design says *there is one authority for X* and the implementation moves that
authority between modules, nothing is wrong. If the code now has **three** independent
authorities, the two are no longer describing the same system.

That is what makes a shipped design a useful comparator: it does not chase every code
change. It answers *what are we doing*, while the code answers *how are we doing it right
now*.

> **The test, before adjudicating anything:**
>
> **Could I change this implementation detail completely and still truthfully say we are
> implementing the same design?**
>
> **Yes** — the design needs no update, however far the code has moved.
> **No** — either the code has drifted from the design, or the design itself changed and
> that change was never recorded. Establish which before touching either.

---

## 4. What a NOW doc must specify

Retained from the retired standard, but **re-weighted by §8**: these are the areas where
a reader most often goes wrong, so they are where the doc earns its place. State the part
a reader would misjudge — not the part they can read. "Clamped `>= 0`" restates; "clamped
`>= 0` because a negative here silently zeroes a productive run" is the doc's job.

1. **Algorithm and rules** — the actual logic, not a summary of its purpose.
2. **Data shapes and serialization** — *the number-one collapse zone.* Spell out keys,
   types, nesting and what is persisted.
3. **Edge behaviour** — clamps, coercion, indexing, empty and None handling. Silently
   glossed is silently wrong.
4. **Integration and host contract** — anything HA-bound: when it runs, what it assumes
   exists, what happens during setup and teardown.
5. **Brand / variant dependence** — which parts are brand-specific and which are core.
   This is the leak that hides bugs.
6. **Provenance** — where the behaviour is implemented, cited per §6.

---

## 5. Meta-rules

Carried forward from the retired standard. These outlived the concept they were written
for.

1. **Never be confidently wrong.** A precise but unverified statement is *worse than
   silence* — it misleads with authority. If you have not checked it against source, mark
   it unverified or leave it out. Hedge, don't harden.
2. **Depth where the code cannot speak CLEARLY — not restatement.** The reader has the
   source, so spelling out what is plainly readable buys nothing and costs a great deal:
   every restated clamp, column and kwarg list is an independent claim that can rot on its
   own, which is where the sediment in §5a came from. The retired standard said the
   opposite ("depth is intentional — do not trim it"), and it was right *for a corpus that
   had to survive losing the source*. That premise is gone.

   ⚠ **But "the source contains it" is the wrong test — see §8.** Duplicate truth is not
   duplicate cognition. Go deep wherever a second representation makes an important
   inference cheap; go shallow on anything a reader can already see for themselves.
3. **No normative collisions. Amendments edit the superseded text in place — never merely
   append an override.** Two authoritative statements, each individually followable and
   jointly unsatisfiable, are a defect class of their own (see §2). One live statement per
   rule; history goes to `history/` and git.
4. **Canonical text is never evidence that the author paid attention.** Names, dates,
   "as discussed", and discovery stories are metadata about the author, not information
   about the system. The filter: *would this still serve a competent reader who has never
   seen the project's conversations?* If not, it belongs in HISTORY or the commit message.
5. **Explain the code, never the document.** "This document exists because…", "what is worth
   understanding here is…", "called out so it is not mistaken for…" — all of it is the author
   present in the text, and it reads as padding because it is. A section that has to announce
   its own significance has not demonstrated it. State the case; the reader can see where it
   sits.

   The calibration passage is `docs/retired/dev/06-job-lifecycle.md` §6f, on the errored-robot
   clause in the stranded reaper. It is one of only two passages in that document that answered
   a counterfactual correctly under measurement, and it never once says what it is doing. It
   also shows the right way to carry a rejected alternative — inside the sentence ("reverses the
   predicate's original *an error may recover, leave it alone* stance"), not announced from a
   labelled slot.

6. **If a sentence is there because the paragraph looked short, cut it.** Padding is not
   neutral: every filler sentence is another claim that can rot, and a reader who finds one
   stops trusting the density of the rest. This is the sibling of §5.2 — restatement pads with
   the code's own content, this pads with nothing at all.

7. **A doc no index reaches is a doc the corpus does not have.** Omission is invisible in
   prose — a missing table row leaves a visible hole, a missing clause reads as a complete
   sentence. Run `python scripts/check_docs_index.py`; naming a file in backticks does
   **not** count as reaching it.

---

## 5a. Do not stack strata

The characteristic defect of this corpus is not a wrong sentence. It is a **stack**: two
or three claims accreted into one line over months, each true when it was added, with
nothing marking which layer is which.

A real example, found 2026-08-16 in `05-core-manager.md`:

> Ref: `core/manager.py` line 1566 (param), `core/manager.py` line 60 (`_UNSET`
> sentinel), `core/manager.py` lines 1627-1628 (three-way apply logic).

Three citations. **All three wrong.** `_UNSET` had moved to 73; the other two now landed
inside `refresh_vacuum_capabilities` and `get_vacuum_capabilities`, neither of which has
anything to do with the field being described. Every one pointed confidently at real code
that was not the code. The whole thing collapses to one honest citation:
`core/manager.py::update_room_fields`.

**This is why the two previous models could not hold**, and it is worth understanding
before writing anything here:

- **DR asked "could someone rebuild this from the doc alone?"** — unanswerable against a
  stack, because the reader cannot tell which stratum is current. The doc is not wrong
  enough to fail and not right enough to follow.
- **Epochs asked "what changed since the baseline?"** — undiffable against a stack,
  because the layers are not dated. Accretion has no epoch boundary; it is deposited
  continuously by people adding a true thing next to an older true thing.

Neither model was defeated by carelessness. Both assumed a document is a single coherent
statement, and these documents are **sediment**.

**So: when you touch a line, resolve it to one claim.** If an older layer still matters, it
belongs in `history/` or in git — not stacked beside the live one. This is §5.3 (no
normative collisions) applied at the line rather than the document, and it is the more
common form by far.

---

## 6. Citations — symbols, never line numbers

A line-number citation rots on the next unrelated edit above it, silently, and then points
confidently at the wrong thing.

| Form | Use |
|---|---|
| `‹path›/‹file›.py::symbol` | **Preferred.** Survives every edit that does not rename the symbol. |
| `‹path›/‹file›.py#ANCHOR` | For a place with no symbol — see [design/shipped/notation-anchors.md](design/shipped/notation-anchors.md). |
| `‹path›/‹file›.py:123` | **Banned.** |

Gated by `python scripts/check_doc_citations.py`, which also catches a `::symbol` that no
longer exists — the failure a line number cannot report.

**This is what makes §5a tractable.** A stale line number is silent: it resolves to
*something*, and the something looks plausible. A stale `::symbol` is loud — it fails the
gate by name. Migrating a citation therefore does not merely future-proof it; it converts
every buried stratum from invisible to reported. That is the point of the migration, not
tidiness.

> Not theoretical: adding five comment lines to `const.py` once invalidated **nine**
> citations at a stroke and reported an entire generated document as drifted.

---

## 7. Generated content

Facts that can be derived from source should be **generated**, not typed. A generated doc
cannot drift — but it can be wrong in bulk, and it carries numbers, which read as more
authoritative than prose.

- Each generator declares its blind spots, with a test guarding them.
- Staleness is gated: `python scripts/check_generated_docs.py` (`--fix` regenerates).
- Generators emit `::symbol` citations, per §6.

> `THEME_TOKEN_USAGE.md` once reported "135 tokens with no consumer". It was false — the
> tracer could not see three dynamically-built families — and acting on it would have
> deleted live theming.

---

## 8. Acceptance test — what does this doc ADD?

The retired standard tested for **omission**: a blind agent rebuilt the module from the doc
alone, and every miss was a doc failure. That was the right test when the premise was total
source loss. With the source in hand it measures the wrong thing — it rewards restatement,
which §5.2 now says is the defect.

**The test is not "does the source already contain this?" — it is:**

> **Does the document transform that information into a representation that makes something
> important substantially easier to understand or reason about?**

That distinction matters more than it first appears. `5 × 5`, `5+5+5+5+5`, and "five groups
of five" encode the same fact and expose different relationships: compact notation, repeated
addition, the conceptual model. **Duplicate truth is not duplicate cognition.** A naive
"delete anything recoverable from source" rule optimises the corpus down to *"read the
source"* — technically complete, practically useless.

So, three criteria:

1. **Everything it claims must be TRUE.** A wrong statement is worse than a missing one,
   because the reader has no reason to doubt it (§5.1). Check every claim against source.
2. **It must pay for its length in comprehension.** Ask what a reader gets here that they
   would not get *clearly, cheaply, and at the right level of abstraction* from the code.
3. **Where the answer is "nothing", cut it.** Where the answer is "a mental model of
   something the implementation scatters", keep it — that is the doc's real content.

The line, concretely:

| Code | Doc | Verdict |
|---|---|---|
| `if A and B: finalize()` | "If A and B, finalize is called." | **Restatement.** Contributes nothing; rots independently. |
| Completion spread across six functions and three guards | "Completion requires two independent claims because either signal alone can be stale. Once accepted, it is irreversible for that run." | **Keep.** The code contains it; the prose compresses a distributed implementation into a model. |

**Examples survive under the same rule.** A concrete example may add zero derivable
information and still reveal what a rule *means* in thirty seconds rather than twenty
minutes. That is a real reduction in cost, and cost is what this test measures.

A doc can therefore FAIL by being too long — an accurate, exhaustive restatement scores
zero on (2) — and can equally fail by being too terse to be understood. Neither is a
paradox; both follow from measuring comprehension rather than completeness.

**Where a disagreement appears, remember §3: the mismatch may be a code bug.** Investigate
which side is wrong before patching the doc.

---

## 9. Release gate

Docs are a **release** gate, not a per-push one. Tests land in bunches and docs follow;
gating every push on doc freshness is friction that buys nothing.

Before a release: §6 citations, §7 generated docs, `check_docs_index`, and
`mkdocs --strict`.

> ⚠ `mkdocs --strict` is a **link** gate and nothing more. It has passed clean through
> eleven false sentences. It can never be the freshness gate.

> **QUOTING A CITATION — the convention.** When you need to show a citation (an example, a
> defect being described, a rule being illustrated), write the line number **in prose**:
> `` `core/manager.py` line 1566 ``, never `` `‹file›.py:1566` `` with the number inside
> the code span. The checker
> cannot tell an illustration from a claim, so an example written in the live form is
> counted as a live citation — it inflates the migration backlog with instances of the
> thing being argued against. This bit three times in one session before the convention
> was written down.
>
> **Why the placeholders above use `‹ ›`:** a realistic-looking filename in a code span,
> followed by `::` and a symbol, is indistinguishable from a real citation —
> `check_doc_citations.py` duly reports it as pointing at a file that does not exist. The
> checker cannot tell an illustration from a claim, so illustrations must not look like
> claims. This paragraph tripped the gate twice while being written, which is the most
> convincing argument for the rule that could be made.
