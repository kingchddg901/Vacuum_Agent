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

---

## 4. What a NOW doc must specify

Retained from the retired standard, because the collapse zones are the same whatever the
shelf is called. Audit §4.2–§4.4 hardest; §4.1 usually survives on its own.

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
2. **Depth is intentional — do not trim it as "over-documentation".** The clamps, exact
   columns and kwarg lists are the load-bearing parts. A normal doc glosses precisely what
   a reader most needs.
3. **No normative collisions. Amendments edit the superseded text in place — never merely
   append an override.** Two authoritative statements, each individually followable and
   jointly unsatisfiable, are a defect class of their own (see §2). One live statement per
   rule; history goes to `history/` and git.
4. **Canonical text is never evidence that the author paid attention.** Names, dates,
   "as discussed", and discovery stories are metadata about the author, not information
   about the system. The filter: *would this still serve a competent reader who has never
   seen the project's conversations?* If not, it belongs in HISTORY or the commit message.
5. **A doc no index reaches is a doc the corpus does not have.** Omission is invisible in
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
| `‹path›/‹file›.py#ANCHOR` | For a place with no symbol — see [design/notation-anchors.md](design/notation-anchors.md). |
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

## 8. Acceptance test

**Pragmatic (per-doc):** run §4 against the doc. It passes when nothing in the collapse
zones is missing, hand-wavy, or unverified.

**Full (measured):** a blind agent rebuilds the module from the doc alone; diff against
source; classify each miss as `DOC_GAP` or `AGENT_MISS`. The `DOC_GAP`s are the doc's
failures. Re-verify each proposed fix against source before applying — and remember §3: the
mismatch may be a code bug.

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
