# AB-07 pre-round finding — the ablation UNIT, and where the centre is

Two corrections to how this round was first scoped, plus one architectural
refinement from Chris. Written before any trim is spent.

## 1. The unit was inferred from file size — wrong basis, right answer

The first scoping said "doc 07 is 744 lines, comparable to CAL-23's 475, so
ablate the whole doc." CAL-23's size establishes nothing; its COHERENCE did.
The protocol says per DR SECTION. So: measured, as a finding about doc 07.

**Cross-section coupling** — 9 sections, 10 distinct cross-section edges:

| section | lines | out-edges |
|---|---|---|
| §1 what it does | 46 | →4 |
| §2 payload structure | 68 | →7 (+doc 13) |
| §3 room ordering | 20 | none |
| §4 profile resolution | 50 | none |
| §5 access graph | 83 | →6 |
| §6 reduced-run detection | 40 | none |
| **§7 build_queue vs build_room_payload** | **168** | **→1,4,6,9 (the hub)** |
| §8 set_rooms_enabled_subset | 50 | none |
| §9 stepped runs | 210 | →7 |

**Public-surface mapping** — the queue module exposes 6 public functions, and
`build_room_clean_payload` is specified across §2, §3, §4, §7 AND §9. §7 alone
names 4 of the 6. §1/§5/§6/§8 name no public function at all.

**Verdict: the sections are CHAPTERS OF ONE CONTRACT, not independently owned
questions.** Five sections co-specify one function; a blind builder cannot
reconstruct it from any one of them. The decomposition is by TOPIC (ordering,
profiles, access graph, reduced runs), not by operation. Whole-unit ablation is
therefore justified for doc 07 — as a measured finding, not by analogy to
CAL-23's line count.

## 2. The aggregator test generalizes — and fires INSIDE doc 07

The delegation-density test added to the protocol for doc 03 applies per
SECTION, not only per doc. Two of doc 07's sections are owned elsewhere:

- **§8 `set_rooms_enabled_subset`** → `core/manager.py:2079`, the accretive hub.
- **§5 access graph** → spans `core/manager.py`, `jobs/active_job.py`,
  `jobs/job_monitor.py`; the queue module does not own it.

Both are index-shaped sections inside a specification doc. They are excluded
from the trim's authority: the trim may compress their prose but may not
minimize the contracts, which belong to their owners' rounds.

So doc 03 was an index at DOCUMENT level; doc 07 has index-shaped SECTIONS. The
test is per-section. That is the generalization this round existed to test, and
it held.

## 3. A claim retracted before it became a finding

While tracing the centre, `dispatch/manager.py` (570 lines, `DispatchManager`)
looked undocumented: no DR doc is TITLED for dispatch, and it appears only 1-5
times across six docs. That reasoning was wrong — the same "no doc is titled for
it" shape as inferring a unit from file size. Dispatch IS specified: doc 07 §7
carries `### Send-side dispatch (DispatchManager)`, doc 05 §402-410 carries the
delegation and states DispatchManager owns the send side, doc 01:153 maps all
four entry points. NO GAP. Recorded because a confidently-wrong corpus claim is
the DR standard's own worst failure, and this one got within one step of being
reported.

## 4. Chris's refinement: the adapter is in the atom, but dispatch is its centre

Doc 32 measures the atom as adapter + dispatch + queue + rooms + spine +
active_job. That is a set, not a ranking. Chris's distinction:

> intent -> resolution -> **dispatch** -> adapter -> device

- **Conceptual core:** rooms / job / queue semantics — "the places", "how I want
  them cleaned", "the intended order".
- **Execution core: dispatch.** The deepest VA-OWNED boundary — the point where
  the system stops being a planner and becomes an actuator.
- **Provider edge: adapter.** Indispensable for a real run and deliberately
  SUBSTITUTABLE: Eufy falls out, Roborock takes its place. It teaches VA how to
  say it; dispatch is where VA decides to speak.
- **Accretive infrastructure:** manager / storage (already established).

Why it matters beyond taxonomy: **above dispatch, an error is informational;
through dispatch it becomes physical** — wrong room, wrong settings, wrong
vacuum, duplicate action, action at the wrong lifecycle point. That makes
dispatch the highest-consequence prose in the corpus, and it argues the recovery
skeleton should be derived causally outward from it — what minimum information
must dispatch receive, what upstream produces it, what minimum downstream
translation makes it real — rather than from imports or doc numbers.

Consequence for this round: §7 is both the doc's structural hub AND the section
carrying the send-side boundary. It is the highest-value prose here, and the
place a coupling leak or a lost invariant would cost the most.

## 5. Apparatus claim, corrected

Earlier wording: "~25 behavioural tests, so the examination can stand on its
own." That is a CLASSIFICATION asserted as a proof, and today gave two
counter-examples: 935/935 node tests stayed green after a production property
was renamed out from under them, and a visual gate rendered nine placeholder
cards while looking healthy.

Corrected: the examination surface appears substantially healthier than CAL-23's
(43% and 28% private-name contact vs 81%) and may need less supplemental
instrumentation. Whether it is SUFFICIENT is decided by mutation controls during
the round, not by the classification up front.
