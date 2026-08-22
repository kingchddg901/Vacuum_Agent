# Documentation restructure — state of play

**As of 2026-08-16.** Read this before touching `docs/dev/`. Companion:
`FINDINGS-counterfactual-pass-06.md` (what the acceptance test turned up).

---

## 1. What changed, and why the old models died

**The Disaster Recovery standard and the epoch model are both retired**, in
`docs/dev/history/` with the reasons on the files. Two diagnoses, both Chris's, are
load-bearing:

- **Docs are SEDIMENT, not statements** (`00-documentation-standard.md` §5a). The
  characteristic defect is a *stack*: claims accreted over months, each true when written,
  nothing marking which layer is which. DR asked *"could you rebuild the module from
  this?"* — unanswerable against a stack. Epochs asked *"what changed since the
  baseline?"* — undiffable, because the layers are not dated. **Neither model was defeated
  by carelessness. Both assumed a document is a single coherent statement.**
- **Epochs are good for AUDITS, dangerous for DOCS.** An epoch licenses a doc to be out of
  date between reconciliations while it still *reads* as current — drift becomes
  compliance. Epochs remain in use for the audit campaign; they are gone from docs.

## 2. The three shelves

```
NOW      docs/dev/NN-*.md        31 files   what it does today. Code wins.
DESIGN   design/planning/         2 files   decided, not built
         design/shipped/          3 files   built — still answers "why is it like this"
HISTORY  docs/dev/history/        3 files   what we stopped doing. Never wrong.
```

*History is what we stopped doing; shipped design is why we do what we do.*

**History populates by EXCAVATION, not promotion.** Fixing a NOW doc displaces strata and
that is where they land. Do not go hunting private notes for things to promote.

Also present, deliberately outside the shelves: `frontend/` (20), `reference/` (4,
generated), `maintenance/` (1, a dated audit record).

## 3. The acceptance test — settled, after inverting twice

> **Does the document transform the information into a representation that makes something
> important substantially easier to reason about?**

It got this wrong twice before landing, and both wrong versions are instructive:

1. I carried DR's blind-rebuild drill into DR's own replacement — testing for omission when
   the source is in hand, which rewards restatement.
2. I replaced it with *"if nothing survives subtracting what the code says, it is
   restatement"* — which argues against the best docs there are.

Chris supplied the fix: `5 × 5`, `5+5+5+5+5`, and "five groups of five" encode the same
fact and make *different inferences* cheap. **Duplicate truth is not duplicate cognition.**
A naive "delete anything recoverable from source" rule optimises the corpus down to
*"read the source"* — technically complete, practically useless.

## 4. The two registries

Both indexed, both with declarations in **SOURCE only** — the docs are indexes over
anchors that live in code.

- **`00b-invariants.md`** — `IN` anchors, one sentence per rule plus a pointer to the
  explanation. First entry `INKR1TW7` (cold-start provider readiness) *indicts the gap it
  fills*: its own comment reads "a local comment is not a system property", and nothing
  indexed it.
- **`00c-replicas.md`** — `RN` anchors for rules deliberately implemented more than once.
  **A green suite cannot see a missing copy**: 4381 tests passed with 2 of 3 copies of the
  `translation_key` rescue fixed.
  - `RNF2RCXP` — translation_key rescue, **3 copies**
  - `RNZM4AYY` — most-specific-declaration ownership, **3 copies** as of #49. The third is
    the best argument for the whole class: it is the *same rule in a different vocabulary*
    (set containment for token sets, string containment for suffixes), so no single helper
    can serve all three. Coordination without unification is the point.

Anchor classes: `CN` code · `SN` semantic · `HN` historical · `PN` prose · `IN` invariant ·
`RN` replica. Mint with `python scripts/doc_anchor.py --mint <CLASS>`.

## 5. Gates — what actually enforces this

| Gate | Enforces | Note |
|---|---|---|
| `mkdocs build --strict` | links only | **NOT a truth gate** — passed clean through 11 false sentences |
| `check_doc_citations.py` | citation freshness | excludes `maintenance/` + `history/` |
| `check_generated_docs.py` | generated docs current | `--fix` regenerates |
| `doc_anchor.py --check` | anchor identity | DUPLICATE, BROKEN, MOVED, MALFORMED |
| `check_docs_index.py` | reachability from an index | excludes `maintenance/` + `history/` |

**`check_generated_docs` is the one that bites unrelated commits.** `EVENTS.md` still
carries **29 line-number citations** against 11 in the `::symbol` form, several pointing
into `core/manager.py` — so *any* edit there shifts them and fails the gate. It went red
twice today for exactly that. The `::symbol` migration in `gen_event_docs.py` is partial.

**A gate probe needs a positive control.** My first probe of `doc_anchor.py` reported a
clean pass and was itself the bug: it used `[x](file.md#TOKEN)`, but `CITE_RE` requires
backticks and a `.py`/`.js`/`.mjs` path, so nothing was scanned. The tell was the
**count** — `12 declared / 14 cited` before *and* after planting four defects — not the
exit code.

## 6. The counterfactual measurement — ✅ RUN 2026-08-22

Chris's framing: *"can an agent tell you the shape of the code from the docs, or what
would happen if you changed part of it, and be mostly right?"* The **"what breaks if you
change X"** half is the sharp one, because restatement cannot answer a counterfactual.

Three conditions, settled before building:

1. **An oracle** — two agents, one given only the doc, one only the source, same question.
   Divergence = doc gap. Avoids grading my own work.
2. **Miss attribution** — DOC_GAP vs AGENT_MISS; only the first counts.
3. **Questions where general competence gives the WRONG answer.** "What if you remove the
   debounce?" is answerable without reading anything.

`00b` and `00c` are pre-computed answers to this test — an invariant IS a counterfactual.

**Status: stages 1 and 2 done on `06-job-lifecycle.md` (1420 lines, the hardest file).**

- Authoring: 3 source-only agents → 9 counterfactuals.
- Verification: 9 skeptics → **3 CONFIRMED · 5 PARTLY_WRONG · 1 REFUTED.**

> **Verification is not optional here.** In this design the `true_answer` IS the oracle.
> Six bad ones would have graded the doc against a fiction — and a doc-agent answering
> CORRECTLY would have scored as a miss.

**The failure mode is QUANTIFIER CREEP, every time.** Mechanism right, scope wrong:
"every run", "never", "silently", "permanently". Prompt verifiers at the quantifiers
specifically.

**✅ RUN 2026-08-22 — full result in `FINDINGS-cf-measurement-2026-08-22.md`.**

> **The document answered 2 of 7. It failed 5. The source-only control scored 7/7, so
> AGENT_MISS is ZERO and every failure is attributable to the document.**

Shape matters more than the ratio: **zero WRONG** — the doc is either right or silent, never
confidently mistaken. Both successes are passages that record a DECISION AND ITS DEFEATED
ALTERNATIVE, not narration of what the code does. Quantifier creep appeared on the READING
side too (2 of 7), so it is not an artifact of the authoring agents.

⚠ **The oracle set was never written down and was recovered 2026-08-22 from the 2026-08-16
subagent transcripts** — see `ORACLES-counterfactual-06.md`. In this design the answer IS the
oracle and 6 of 9 as-authored answers were wrong, so re-authoring would have discarded the
verification stage and graded the doc against a fresh fiction.

⚠ **ONE ORACLE IN EIGHT ROTTED IN SIX DAYS.** CF-6 is excluded: `078ca634` fixed the very
defect it probed, so the doc was being graded against behaviour that no longer exists. That is
the adversarial review's thesis demonstrated by accident — identity without a dependency edge
decays measurably, and now we have a price for it.

## 7. Open, in order

1. ~~**Run the measurement** (§6).~~ ✅ **DONE 2026-08-22.** Next decision is Chris's: the
   revised plan in `PROPOSAL-docs-rewrite-tagged-corpus.md` is *three experiments, not a
   campaign*, and this was the first. **The missing half is the STALENESS EDGE** — a
   `code-at-this-anchor changed since the region last changed → ADJUDICATE` check. The
   measurement produced its own evidence for building it.
2. **59 line-number citations** in live docs. NOT 568 — that counted `maintenance/`, whose
   citations are as-of-2026-08-02 and must NOT be migrated; it holds 495 of them.
3. **Three `docs/dev/frontend/*` drift rows** from the 2026-08-06 note (6 of 8 done).
4. **`core-minimality.md` is unplaced** — sitting at `design/` root, in neither sub-shelf.
   It is a dated *measurement*: not a plan, not history. **Needs a ruling from Chris.**
5. **`14-dock-manager` §6 message defect** — `missing_action_entity` reads as a fault on
   the user's install; for Roborock it is the normal permanent state. Documented in 4.1,
   not fixed.
6. **Two labels wrong against the manuals** — "Dock Strainer" appears in NO Roborock manual
   (the Curv calls it the Cleaning Tray Filter); `cleaning_brush` is the *High-Speed
   Maintenance Brush*, 6–12 month replacement. Fix before stable.
7. **`EVENTS.md` line-citation migration** (§5) — optional, but it will keep failing CI on
   unrelated commits until done.

**CLOSED, do not re-open:** the "anchor cited but never declared is silent" tooling gap.
Probed 2026-08-16 — the explicit form fires `BROKEN` and `MOVED` correctly. Only the *bare*
form is unchecked, deliberately, because a bare token cannot be told from an English word
(`INSERTED`, `INSTANCE`, `INTENDED`, `INVERTED` are all valid `IN`-prefixed tokens).
