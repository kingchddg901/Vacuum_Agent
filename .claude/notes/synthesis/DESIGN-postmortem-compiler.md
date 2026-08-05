# DESIGN — the postmortem compiler

**Status: DESIGN — awaiting Chris sign-off before any code.** Written 2026-08-04, from the
brief: do not summarize the audit; reconstruct it as an evidence-backed causal history.

> raw engineering exhaust → normalized evidence → causal graph → adversarial verification
> → human-readable narrative

**Supersession note:** `AUDIT-1-CLOSEOUT.md` (9d6d0dc) stays as the executive record, but the
postmortem this system compiles supersedes it as the campaign's history. The closeout doc
is itself a demonstration of the problem: it is prose written from ledgers and commit
subjects, and every causal claim in it is uncited. It becomes an input to attack, not a
source of truth.

**The design rule everything below serves: preserve failed reasoning, not merely failed
code.** "RAB-3 was fixed" is worthless. "The agent interpreted *unknown* as domain-wide
nullability, propagated `None`, four tests exposed that arithmetic depended on a total
numeric value, the model was revised so uncertainty stays at the display boundary, and
RAB-3 pinned measured-zero against future collapse" is engineering knowledge. A commit
summary destroys most of it; this system's schema makes it the primary object.

---

## 1. The base — what we compile FROM (CONFIRMED by Chris, 2026-08-04)

**The history is anchored at the calibration pass — the first multi-agent review run
against a subsystem** (2026-07-30, active-job lifecycle + exactly-once finalization,
8 agents). That run is the campaign's origin event and the compiler's timeline zero; its
findings and the era it opened (audits #1–#6, scoped by behavioural contract) are
first-class nodes, not preamble.

This is also exactly why the brief says **commit history supplies the fix-surfacing and
fix-landing events**: the calibration-era audits shipped fixes as they were found, with no
packet ledger — Corpus B records `finding_to_commit_mapping: not_recoverable` and derives
its completed half from git log alone. For the opening act of the campaign, **git history
is not a supplementary source; it is the only fix record that exists.** The later era
(#7–#18 → corpus → packets) adds the ledger layer on top; the extractors must handle both
eras and mark which regime each event was recovered under.

Concretely the base is: the calibration + early-audit prose artifacts (`_frozen/audits/`,
Corpus B inventory), the canonical corpus (`audit-findings-canonical.jsonl`) for the
structured era, the `_gen_*` machinery as extraction house style, and `git log` for every
surfaced/landed event across both eras. Nothing is re-derived that a ledger already
states; nothing is trusted that a harness can arbitrate.

Source inventory, mapped to the record types the brief demands:

| Brief's record | Where it actually lives today | Recoverability |
|---|---|---|
| Original hostile finding | `corpus/audit-findings-canonical.jsonl` — 516 records with `observed_behavior`, `reproduction`, `guards_checked`, per-lens `verification.verdicts`, `killed_by`, `severity_corrections` | FULL — this is the finding-node table, pre-normalized |
| Agent research & reasoning | `_frozen/journals/` (raw agent returns, upstream of post-processing) + audit prose artifacts + REVIEW-01..07 | PARTIAL — discovery-side reasoning is preserved; execution-side reasoning survives only where a commit message, BLOCKER-*, HANDOFF-*, or FINDING-* doc banked it |
| First proposed/attempted fix | SYNTH-03..12 packet texts (`required_behavior`, `findings_not_closed`, blocked_by clauses), REVIEW-02 amendments (D1–D14 are *pre-code* wrong-fix records), BLOCKER-* docs | PARTIAL — attempts that died inside a session without a commit or blocker doc are gone unless Chris or a transcript recalls them |
| Failing tests / harness output | 61 `_proof_*.py` + sweep buckets (BEFORE / AFTER / UNEXPECTED / NO_TALLY / QUARANTINED), REPRODUCER-STATUS, CI runs per push, `_crossmatch_replays.py` baseline | FULL for proof-backed packets; the sweep's staleness classes are themselves causal edges (see §3) |
| Corrected mental model | Adjudications (`_adjudicated_findings.json`), premise ledger (`_premises.json` — 8 premises, 4 retired with evidence), design docs, narrative commit bodies | GOOD — the premise ledger already implements `disproved_by`; it is the seed of the causal layer, not a new invention |
| Final commit | git history — 416 commits in-window, subjects carry packet/finding ids; landing proven by `git show --stat`, never subject (the RP-047 spec-only trap is *documented precedent* for why) | FULL |
| Disposition (fixed / rejected / narrowed / deferred / converted-to-feature) | OPEN-FIX-CHECKLIST reconciliation prose, closure-matrix, `_reopened_findings.json`, killed register (22), deferral register (5) | FULL — the ledgers already distinguish these; the compiler must not collapse them |
| Surviving invariant | SYNTH-05's eight structural invariants + per-family REVIEW verdicts | PARTIAL — exists at campaign level; per-chapter invariants are an *output* of the graph, adjudicated by Chris |
| Hardware arbitration | `_frozen/baseline/` captures, HC register, run ids (e.g. pj_2026-08-02T23-04-45) | FULL for the 5 validated packets; absence is itself recorded (open hardware gates) |

**Honesty rule inherited from Corpus B:** audits #1–#6's finding→commit mapping is
`not_recoverable` and stays that way. Where a record is gone, the graph carries an
`evidence_still_missing` edge to a named gap — the compiler *records* loss, it never
paves over it with plausible narrative. That is the whole point.

## 2. The core object — an event, not a paragraph

The unit is the **finding chain**: an ordered sequence of typed events per finding (or per
merged root cause), each event carrying provenance.

```jsonc
// postmortem/graph/events.jsonl — one event per line
{
  "event_id": "EV-RF36-004",
  "chain": "RF-36/RAB-3",
  "type": "test_result",           // see closed vocabulary below
  "at": "2026-08-02T23:04:45-07:00", // DERIVED from an artifact timestamp, never invented
  "claim": "Four unit tests failed: arithmetic in the ring accumulator assumed a total numeric battery value.",
  "provenance": [                   // ≥1 REQUIRED, or the event is 'asserted:uncited'
    {"kind": "commit",  "ref": "623372a", "quote": "…"},
    {"kind": "proof",   "ref": "_proof_battery.py", "bucket": "UNEXPECTED"},
    {"kind": "ledger",  "ref": "SYNTH-12-packets-battery.md#clause-2"}
  ],
  "asserted_by": "main-agent",     // main-agent | foreign-model | harness | chris
  "verified_by": []                 // filled by stages S2/S3
}
```

**Event types (closed vocabulary, matching the brief's spine):**
`finding_filed` · `premise_adopted` · `evidence_gathered` · `interpretation` ·
`fix_attempted` · `test_result` · `hardware_result` · `model_revised` ·
`ledger_event` (credit / reopen / reconcile) · `decision` (the terminal event).

**Terminal decision states (must match what the ledgers already distinguish):**
`fixed` · `rejected` · `narrowed` · `deferred` · `disproved` · `converted_to_feature`
(access graph, Phased Jobs, storage migrations are this state — findings that became
designs) · `superseded`.

Each chain ends with an **invariant field**: the one sentence that should survive after
everyone forgets the details. Machine-proposed, Chris-adjudicated, never auto-published.

**The time rule (Chris, 2026-08-04): never infer duration from work volume — reconstruct
it from timestamps in one declared timezone.** "This was a lot of work, so it took days"
and "one commit, so it was quick" are both forbidden inferences; the corpus itself proves
volume and duration decouple (an 8-agent audit = ~30 wall minutes; one two-line fix can
gate on a hardware run for days). Mechanically:

- **Declared timezone: America/Los_Angeles** (the commit log's own offset). Extractors
  store every timestamp as ISO-8601 with offset exactly as the artifact states it;
  rendering normalizes to the declared zone. Mixed-zone arithmetic is a lint failure.
- **The clock sources, in trust order:** git commits (committer date = when it LANDED;
  author date = when it was WRITTEN — they differ under amend/rebase, and landing events
  use committer date) · run/capture ids that embed timestamps (pj_2026-08-02T23-04-45)
  · frozen-artifact digests' recorded times · file mtimes (weakest — mtime moves on
  copy; admissible only when nothing better exists, and marked as such).
- **`at` is derived-only:** every event's time must be computable from one of its
  provenance entries. An event with no timestamped artifact gets `at: null` — visibly
  undated, never plausibly dated. Duration claims in rendered prose ("took three days",
  "later that night", "within 72 hours") are causal-connective-class statements: the
  S4 lint requires each to resolve to a timestamp pair from the graph.

## 3. The causal edges — the layer that currently lives only in heads

Edges connect events/chains/premises/commits across records that today live separately.
Closed vocabulary (the brief's list, plus three the corpus already demonstrates):

| edge | example already in the corpus |
|---|---|
| `caused_by` | reaper loop ← RP-002's refusal handling (REVIEW D1) |
| `disproved_by` | cv-ids-unstable premise ← 30 on-device re-analyses |
| `depends_on` | RP-017 ← RP-016's PER_MAP_STORES (clause text, not header) |
| `made_reachable_by` | `_proof_reachability.py` ERROR ← A6-AGX fix reaching deeper than fixture |
| `made_unreachable_by` | ROBORO-5 proof ← ROBORO-1's sibling guard (staleness class 2) |
| `same_wall_as` | distinguishability: DIAG-1's "wrong place vs absent" = battery's "unreadable vs zero" |
| `supersedes` | derived phase-index ← retired accumulated field (the tombstone comments) |
| `merged_into_root_cause` | closure-matrix family membership (4.5:1 fan-in) |
| `test_fabricated_impossible_state` | RP-016 case 3 — hand-simulated mutation, could never flip |
| `fix_overreached` | A3-REC-4's third site; the 17 verifier-killed consequence claims |
| `fix_underreached` | A3-REC-3 — half credited as whole; A7-ROBORO-4 preserved-not-applied |
| `evidence_still_missing` | Corpus B finding→commit; execution-session first attempts |
| `premise_retired_fells` | one retirement → N dependent findings flagged (delta-10 mechanism) |

Every edge carries the same provenance block as events. **An edge with no artifact behind
it is legal but marked `asserted:uncited`** — those route to the Chris-adjudication queue
(he supplies the distant causal edges no agent can find in artifacts) or convert to
`evidence_still_missing`. The renderer refuses to state uncited causality as fact.

**Chapters are emergent, not pre-assigned.** The postmortem's chapters will not align with
dates or packet numbers; they emerge as communities in the edge graph. The predicted themes
— reachability, distinguishability, wire-shape stability, evidence provenance, semantic
duplication, state ownership, uncertainty boundaries — are *hypotheses to test against the
clustering*, deliberately NOT seeded as categories. If the graph reproduces them, that is a
result; if it finds a different cut, that is a better result.

## 4. Pipeline — five stages, authority split by what each is good at

```
S0 EXTRACT     mechanical parsers per source → normalized nodes/events   (scripts, no model)
S1 RECONSTRUCT main agent proposes chains + edges w/ provenance          (institutional context)
S2 ATTACK      foreign model attacks causal claims & smooth narrative    (no repo access needed)
S3 ARBITRATE   harness + git settle facts; Chris adjudicates intent      (append-only rulings)
S4 RENDER      writer consumes ONLY the verified graph → cited prose     (lint enforces it)
```

- **S0 — extractors** (`postmortem/_extract_*.py`, house `_gen_*` style, deterministic,
  re-runnable): corpus JSONL → finding nodes; git log → commit nodes + surfaced/landed
  events (subject-parse for packet ids, `--stat` classification of authoring vs landing —
  the colon-anchor and spec-only traps are already documented, encode them); proof sweep →
  test_result events; premise/adjudication/reopen JSONs → their nodes verbatim; packet
  docs → fix_attempted events (clause-level, honoring 2b's x-of-y model); journals →
  evidence_gathered events keyed by finding id.
- **S1 — reconstruction** is where held context becomes explicit: the main agent walks one
  family at a time and writes the chain + edges, quoting artifacts. Anything it knows but
  cannot cite gets `asserted:uncited`, never silently woven in.
- **S2 — attack**: a model with *no stake in the reconstruction* receives self-contained
  attack packets (chain + its provenance quotes, nothing else) and is scored the way #1
  scored verifiers — on false causality killed. Two designated attacks: (a) causal claims
  whose provenance shows correlation only (commit B after commit A ≠ caused_by), (b)
  places where the narrative is cleaner than the evidence (a chain with no failed
  interpretation events is *suspicious by default* — this campaign's real chains have
  them). Delivery via the existing cross-agent review-block loop (claim / evidence /
  scope boundary / rejected), or a second in-fleet model tier — Chris's call, §7.
- **S3 — arbitration**: factual disputes go to instruments, never to debate — re-run the
  proof, `git show --stat`, replay concordance, the sweep. Intent disputes and distant
  edges go to Chris; rulings are append-only adjudication records (the premise-ledger
  pattern, reused verbatim).
- **S4 — render**: the writer receives the verified graph and produces chapters. Contract:
  every causal sentence carries an event/edge id; a lint pass rejects prose whose causal
  connectives ("because", "so", "which meant") cannot be mapped to a verified edge.
  Citations resolve to commits, test output, ledger entries, hardware packets, agent
  reports. The writer NEVER reads commit messages directly — that door is how smooth
  false stories get in.

## 5. Walking skeleton — validate the schema on two chains before any scale

Per the build-expansion-ready-ship-tiny rule: full schema + two hand-built chains, zero
mass extraction, then stop and review.

1. **RF-36 / battery (the brief's own exemplar).** Exercises: wrong interpretation
   (unknown → domain-wide nullability), propagated `None`, failing tests exposing the
   total-numeric assumption, model revision (uncertainty held at the display boundary),
   invariant (measured-zero pinned against future collapse), plus a live BLOCKER doc and
   an unparked-by-Chris decision event.
2. **#9:A3-REC-3 / RP-047 (the hardest provenance case).** Exercises: half-fix credited
   as whole (`fix_underreached`), spec-only landing trap, mechanism retirement with
   identical output shape (`supersedes` + tombstones), a reopen ledger event, a live
   hardware proof (pj_2026-08-02T23-04-45), conversion of the deep cause into a product
   design (Phased Jobs, `converted_to_feature`), and a still-open hardware gate.

If the schema survives both without bending, mass extraction proceeds; where it bends,
the schema changes *before* 484 findings are poured into it.

## 6. Build plan (post-approval), model fit by phase shape

| wave | work | shape / tier |
|---|---|---|
| 0 | schema files + S0 extractors + graph lint | mechanical; cheap window from this spec |
| 1 | two exemplar chains hand-built + schema revision | main agent (wide-read, institutional context) |
| 2 | mass reconstruction, one family per loop (33 families; clusters assigned to ONE reconstructor each, per the #1 dedup rule) | per-artifact loops from written spec; expensive tier only where a chain forces judgment |
| 3 | attack + arbitration rounds until edge-kill rate goes dry | foreign model + instruments + Chris queue |
| 4 | renderer + citation lint + chapter emergence pass | main agent writes; lint is mechanical |

Storage: `.claude/notes/postmortem/` — `graph/*.jsonl` (nodes, events, edges,
adjudications), `_extract_*.py`, `_lint_graph.py`, chapters rendered to markdown. All
git-tracked (force-added like synthesis/), because this is exactly the artifact class
that must survive a machine loss.

## 7. Decisions and open questions

**Decided (Chris, 2026-08-04):**
- **Anchor:** the calibration pass — the first multi-agent subsystem review — is the
  base; commit history recovers fix surfacing/landing (see §1).
- **Destination: INTERNAL ONLY.** The compiled postmortem lives in git-tracked
  `.claude/notes/postmortem/`, never on the public docs site. Tone may print internal
  process freely (model tiers, token spend, wrong turns, Chris rulings) — that candor is
  the document's value, and it is exactly what a public version would have to strip.

- **S2 foreign model: GPT, via the paste-ready attack-packet loop (Chris, 2026-08-04).**
  His testing: Gemini is not good at this; the others are tuned too hard for other
  things. Attack packets are self-contained (chain + provenance quotes, no repo
  access), which is exactly the ChatGPT loop's constraint — human in the loop,
  rulings come back through Chris and are recorded as adjudications.
- **Deliverable set (talked out 2026-08-04): one shared graph, four renderings.**
  PM-1 Findings & Fixes (compiler-driven — the only doc gated on the graph) ·
  PM-2 the audit's own architecture with reasoning (failure that forced it →
  alternatives rejected → mechanism adopted → trust boundary; absorbs the trap
  bestiary and discharges TASK-write-audit-methodology) · PM-3 instrument shop
  (tool catalog: what it answers, invocation, trust boundary) · PM-4 planning
  book (thin prose over regeneration commands — every number stated in prose is
  a future lie). Sequence: PM-3 → PM-2 → compiler+PM-1 → PM-4. PM-2/PM-3 are
  written from existing sources now and ingested later as S0 graph nodes.

**Still open:**
1. **Chapter grain (PM-1 only)** — the ~7 predicted themes suggest 6–10 chapters;
   acceptable range, or per-family appendices under the thematic chapters?

## 8. What this design rejects (so reviewers don't re-litigate)

- **Writing prose from commit messages** — the closeout doc already exists and is the
  cautionary example; the writer is downstream of the verified graph only.
- **Pre-seeding the chapter taxonomy** — the themes must emerge or the graph is a
  decoration on a foregone conclusion.
- **Reconstructing lost reasoning** — where the first bad attempt left no artifact, the
  chain says so (`evidence_still_missing`); the compiler is not licensed to invent
  plausible failed reasoning, which would be worse than losing it.
- **An open edge vocabulary** — free-text edge types would make the graph unqueryable and
  the attack stage unscoreable; additions go through this doc.
- **Summarization fallback** — if a chain cannot be evidenced, it renders as a stub with
  its gaps named, never as a smooth short paragraph.
