# Option B implementation plan — one record per phase, one parent per run

**Written 2026-08-02. AWAITING APPROVAL — no code until Chris signs the wave plan.**

Design: `ARCH-phased-jobs-concept-vs-execution.md` (with the gpt review folded in).
This document is the HOW. It does not re-argue the WHY.

## The feasibility finding that makes this tractable

`finalize_completed_job` takes `battery_start / battery_end / started_at / ended_at`
explicitly and reads everything else from manager state. **At the advance point, manager
state IS the finishing phase's** — its queue block, its payload, its resolved_rooms. That
is precisely why `maybe_advance_phase` snapshots timing there.

So the core change is not new plumbing. It is calling a function that already exists, at a
point that already holds the right data, instead of hoarding a snapshot for a merged
record later.

> **CORRECTION 2026-08-02 — this finding is INCOMPLETE, and acting on it as written
> double-counts every phased run.**
>
> Manager state at the advance point is the finishing phase's *queue*, but NOT its
> *metrics*. `job_finalizer.py` derives `cleaning_time_seconds` by summing `room_timing`
> across **every** phase on the active job (RP-013f: a stepped run resets the device
> counter per phase, so the sum is the only correct total for a MERGED record). Split the
> children and that same code becomes wrong in a new way:
>
> | finalize point | phases with captured timing | what the sum yields |
> |---|---|---|
> | phase 0's advance | phase 0 only | phase 0 ✅ |
> | phase 1's advance | phases 0–1 | phases 0+1 ❌ |
> | final finalize | all | the WHOLE RUN ❌ |
>
> Every child after the first inherits its predecessors' seconds, and the parent then
> sums those children — so a 3-phase run reports roughly 3× its real cleaning time, with
> invariant 5 ("parent aggregation never double-counts") violated structurally rather
> than by a bug.
>
> Area is worse: `cleaning_area_m2` comes from `last_cleaning_area_m2`, and this file's
> own comment records that area **accumulates** across phases while time resets — so the
> final child would carry the whole run's area no matter what timing does.
>
> **Therefore wave 2 requires a metric SCOPE, not just a call site.** The finalizer needs
> to be told which phase it is recording, and sum only that phase. This is the real
> content of "this wave changes what a record MEANS".

```python
# today
snapshot_the_finishing_phase_timing()      # hoard it
advance_active_job_phase(job)              # swap
return True                                # -> caller SKIPS finalize

# Option B
finalize_the_finishing_phase()             # a real child record
advance_active_job_phase(job)              # swap
return True                                # -> caller still skips ITS finalize
```

## Invariant map — where each guarantee lives afterwards

The eight invariants from the arch note are binding. None may be dropped; each moves.

| # | invariant | new home | wave |
|---|---|---|---|
| 1 | a completed phase credits only its own rooms | structural — a child's queue block IS its phase | 1 |
| 2 | archived completed-room ids agree with the finalized child | structural — one child, one completion | 1 |
| 3 | one child cannot inherit another's counters | per-child battery/timestamps at finalize | 1 |
| 4 | allocation never consumed as observed per-room timing | `allocated` gains force in the rebuilder | 3 |
| 5 | parent aggregation never double-counts | parent sums children, never re-derives | 2 |
| 6 | a completed child survives a later child's cancellation | structural — children finalize independently | 1 |
| 7 | a wait/charge cannot contaminate cleaning overhead | break records are not cleaning records | 2 |
| 8 | flat 3-room ≠ `[room] → wait → [2 rooms]` | shape key gains phase structure | 3 |

Six of eight become **structural** rather than defended by code. That is the argument for
the change, and it is also the thing to be sceptical about — structural claims still need
reproducers.

## Waves

Each wave is independently landable and independently revertable. No wave leaves the
system in a state where a run produces no record.

> **STATUS 2026-08-02 — the order below was INVERTED on landing, deliberately.**
>
> | | plan | landed | commit |
> |---|---|---|---|
> | identity anchor | Wave 0 | ✅ | `ed46bc6` |
> | **the parent** | Wave 2 | ✅ **hardware-verified** | `3e7a36c` `b75d81a` `a3d3e61` `74ce10c` `7afd39f` |
> | **children finalize** | Wave 1 | ✅ **hardware-verified** | `b49818d` `6790952` `4adcac9` `e7c12db` `7bd1bb0` |
> | learning redirect | Wave 3 | ⬜ | — |
> | card | Wave 4 | ⬜ | — |
>
> **HARDWARE VERIFICATION 2026-08-02 — `job_2026-08-02T20-20-35`.** Both children record
> exactly their own phase and nothing else:
>
> ```
> phase0  recorded 120s  timings 120s  gap 0s
> phase2  recorded 390s  timings 390s  gap 0s      parent total 510s
> ```
>
> The run immediately before the metric-scope fix recorded 689s against 570s of truth —
> phase 0 counted twice. Also proven across five live runs: rooms disjoint between
> children, `phase_key` on every child, the planned hold separated from learnable transit
> (a 180s wait decomposing to 182 hold + 0 transit), and the whole structure surviving a
> physically disrupted run (bumped dock, robot lost on return) plus an HA restart without
> stranding the parent.
>
> Five defects reached hardware while the full suite stayed green; each is pinned as a
> regression test now. Four of the five were concealed by a permissive test double —
> see the mock-agrees-with-the-caller note.
>
> **Why the swap.** Open question 3 below asked whether Wave 1 and 2 had to land
> together, because Wave 1 alone fragments the review surface. Landing the PARENT first
> answers it without coupling them: when the children split there is already a parent to
> hold them, so the surface never fragments in the first place. It also puts the
> highest-risk change (what a record MEANS) last, behind a parent that is already proven
> on real runs.
>
> Parent-first has one honest cost: until the children split, every clean phase records
> `record_id: null` and the parent's aggregate covers only the break phases. That is
> named — `aggregate.unsplit_phases` lists them — so a reader can tell PARTIAL from
> EMPTY rather than reading `0 seconds` as a completed run. Removing that field is part
> of the child-split wave's definition of done.

### Wave 0 — identity, written but unread (no behaviour change)

- `phase_job_id`, `phase_index`, `phase_type`, `phase_count` onto the active job at plan
  time and carried through the advance.
- Same fields onto the finalized record's `queue` block (additive; absent on legacy).
- **Proves:** the plan already knows the structure; nothing needs inferring.
- **Risk:** none. Fields nothing reads.

### Wave 1 — children finalize

- `maybe_advance_phase` finalizes the OUTGOING phase before swapping, with that phase's
  own battery bounds and timestamps.
- A break phase writes a **phase record** (`type/planned/actual/outcome/reason/parent/
  ordinal`), NOT a `completed_job`.
- The last phase finalizes as today — the caller's path is unchanged.
- Delete the timing-snapshot hoard: its consumer is gone.
**Definition of done — three things the original wave text did not account for.** Each was
found by inspection before writing code, and each corrupts data if skipped:

1. **Metric scope.** See the correction above. Without it, children double-count.
2. **The child finalize must NOT go through the chokepoint.**
   `async_finalize_completed_job` sets `finalized: True` on the stored active job
   (`learning/manager.py:827`) under its exactly-once claim. A per-phase call through it
   would mark the RUN finalized at phase 0, and every later phase — including the real
   final one — would return `already_finalized` and write nothing. Children go through
   `finalizer.finalize_from_manager_state` directly, with their own per-phase
   idempotency; the run-level claim keeps guarding the run.
3. **Job-level stats must stop seeing children.** `stats_rebuilder.rebuild_all` computes
   `learning_jobs` ONCE (`:1230`) and feeds the same list to `build_job_stats_payload`
   and `build_room_stats_payload`. Children pass `is_learning_job`, so a 3-phase run
   would land as THREE jobs in job-level averages and shape learning. Room-level wants
   them (that is the Entryway fix); job-level must not see them — matching Chris's
   ruling that phased runs "populate in the Phased job list but [are] not learned unless
   directly called". One gate, two consumers: the gate has to split.

- **Proves:** invariants 1, 2, 3, 6 structurally.
- **Risk: HIGHEST.** This changes what a record MEANS for every consumer of `jobs/`.
  Review, metrics, accuracy, CSV export, the card's history all assume one record per run.
  **Wave 1 must land with Wave 2's parent, or the review surface fragments.**

### Wave 2 — the parent

- A parent record: wall-clock, battery delta, ordered structure, outcome, child ids,
  interruption/resume history. An AGGREGATE — sums children, never re-derives.
- Parent status from the child outcome LIST, never collapsed
  (`completed` / `partial` / `interrupted` + the list).
- Boundary transit = child[n].end → child[n+1].start MINUS the planned hold, recorded per
  boundary.
- **Proves:** invariants 5, 7.
- **Risk:** the parent's status vocabulary is user-visible and needs Chris's word.

> **DEFERRED, Chris 2026-08-02 ("not right now"): weight current_room + dwell higher in
> the room rollover.** Raised while watching `job_2026-08-02T19-53-07` sit on Entryway at
> 58% with the robot visibly in Home Office — `completed_room_ids` empty, `current_room_id`
> still 8, mid-phase.
>
> Four rollover sources already exist in `jobs/active_job.py`: `counter_plateau` (:1105),
> `timing_rollover` (:1020), `bounds_exit_early` (:1025) and `native_signal` (:1383, gated
> on `_native_current_room_id`). This is a REWEIGHTING of what exists, not a new mechanism.
>
> Why it matters: on that run neither firing path could. The counter slice was thin
> (20 samples for the whole run), and the timing threshold was waiting out a **6.9 min**
> Entryway estimate for a room that really takes ~1 min — inflated by the very allocated
> samples wave 3 removes. So today the stuck queue and the polluted learning are the SAME
> defect: allocations inflate the estimate, and the inflated estimate is what the rollover
> waits on.
>
> Sequencing: land wave 3 FIRST and re-measure. If the shortened threshold makes the
> timing path fire on time, the reweighting is a robustness improvement rather than a
> fix, and can be scoped calmly. Doing it first risks tuning weights against an estimate
> that is about to change underneath them.
>
> Care needed: `native_signal` is brand-dependent (Ivy reports live rooms reliably; the
> Eufy side is less proven — see `reference_roborock_ivy_signals`), so any reweighting
> belongs behind the adapter seam rather than in core.

> **CHRIS'S RULING 2026-08-02 — TWO POOLS, and FORWARD-ONLY.**
>
> *"the children stay in the general pool. the parents are a new pool for phased jobs."*
> *"migration right this is forward only thing. new feature new rules old is out of
> scope for it."*
>
> **The two pools are records, not key variants.**
>
> | pool | holds | learned as |
> |---|---|---|
> | general (`jobs/`) | atomic runs AND phased-run children | ordinary room + job learning; a child teaches what an AD-HOC run of its rooms costs |
> | phased (`phased_jobs/`) | parents only | orchestration cost — boundary transit — never room duration or queue shape |
>
> I first read "two pools" as a phased/flat discriminator ON the shape key. Wrong: it is
> a split of RECORDS between two stores, and the stores are already separate directories.
> `b49818d` had also excluded children from job-level stats, the exact inverse of this
> ruling; reverted in `8a3bada`.
>
> **Invariant 8 needs NO shape-key change.** It is satisfied structurally: a phased run no
> longer produces a 3-room record to collide with a flat 3-room run — it produces a 1-room
> and a 2-room record, each pooling with its own true shape. The collision was an artifact
> of the merged record, and the merged record is gone. This is the "six of eight become
> structural" claim actually paying out.
>
> **Forward-only. Do NOT re-key history.** No archived record persists `queue.phases`, so
> a historical run's phase structure is unrecoverable — re-keying would invent it. Old
> records stay where their existing key puts them and are out of scope.

### Wave 3 — learning redirect

> **RP-013c RETIRED — done early in `f88b53a`, not in this wave.** Its
> `completed_room_ids_cumulative` is deleted; `known_completed_room_ids` now DERIVES
> earlier phases' rooms from the phase index (reaching phase N proves 0..N-1 finished).
> Brought forward because the bridge in `e7c12db` — a child explicitly clearing the
> inherited list — only made sense until the list itself was gone.
>
> Still open here: `_write_incomplete_run_log` computes missed rooms from the ACTIVE JOB
> rather than from the parent's children. That is now correct via the derivation, so it
> is no longer a blocker — but reading the children directly would make the run-level
> answer survive an active job that is gone (a restart mid-run), which the derivation
> cannot.
>
> Note when rebuilding from history: no archived record persists `queue.phases`, so the
> archive cannot say which historical runs were phased. Only `phase_key` on the new
> children can, and only going forward.


- `allocated: true` becomes binding: the rebuilder skips those rows for per-room timing.
  (This alone fixes Entryway's 13.67-minute sample.)
- A group phase teaches a COMPOSITE key, not member rooms.
- The queue-shape key gains phase structure so a flat run and a phased run stop colliding.
- The parent teaches ORCHESTRATION cost only — boundary transit — never room duration,
  queue shape, or cleaning overhead.
- **Proves:** invariants 4, 8.
- **Risk:** changes learned values. Needs a rebuild and a before/after on real stats.

### Wave 4 — card

- Review groups by `phase_job_id`; one run reads as one entry with its phases.
- Live progress shows the whole group ("Entryway + Hallway") — RP-047.
- Stall detection is group-scoped when member attribution is unavailable — RP-047 (5).
- **Risk:** i18n for the joined label; `Intl.ListFormat`, not a `" + "` literal.

### Wave 5 — redirect, do not retire

- Map each of the six packets' reproducers onto the new model and re-run them.
- A reproducer that cannot be expressed against children/parent is a WARNING, not a
  licence to delete: it means an invariant has no home.
- **Proves:** that the architecture preserved what the patches guaranteed.

## Migration

Legacy records are marked legacy and left alone. Totals (battery, area, wall-clock) stay
trustworthy; ambiguous allocated per-room timings are excluded from room learning; no
modern phased shape key is assigned; no child records are manufactured. Inventing children
from insufficient history would repeat the error being repaired — converting allocation
into observation.

## Still needs Chris

1. **Parent status vocabulary** — user-visible words for a run whose children disagree.
2. **Group composite key shape** — `[8+4]` keyed how? Sorted ids, or the profile step's
   identity? The second survives a room rename; the first survives a profile edit.
3. ~~**Wave 1+2 land together?**~~ **RESOLVED 2026-08-02 by inverting them** — see the
   status block above. Landing the parent FIRST removes the coupling entirely, so the
   first landing got smaller rather than bigger.

## What this plan deliberately does NOT do

- Does not fix the three live bugs from `11-15-51` directly. Waves 3 and 4 subsume them;
  patching them first would be work thrown away.
- Does not revert any landed packet. Wave 5 decides that, with evidence.
- Does not touch the estimator's composition (`Σ children + Σ holds + Σ transit`). That is
  the payoff, and it is a wave of its own once the data exists.

---

## THE MENTAL MODEL, stated by Chris 2026-08-03 (supersedes RP-047's card half)

### Backend: a phased run is a SEQUENCE OF ATOMIC JOBS

*"phased dispatch for eufy at least is batched atomic jobs that get grouped at the
beginning for dispatch/queue planning and at the end."*

Grouping happens at exactly TWO moments — planning (deciding the phases) and aggregation
(the parent). In between, **each clean phase IS an atomic job and must behave like one.**
A break phase is not a job at all; it is the seam between two, which is why it earns its
own record type.

Checked against the code, the violations are exactly the places that treat a phase as
special:

| | code | verdict |
|---|---|---|
| rollover | `if active_job.get("phases"): return` (jobs/active_job.py:1070) | ✗ an atomic job rolls its rooms; a phase cannot |
| timing capture | `_distribute_int(seconds, n)`, `allocated: true` | ✗ an atomic job SEGMENTS; this one divides |
| capture window | slice from the previous phase's end | ✓ that slice IS the atomic job's stream |
| boundary count | phase-scoped samples (`3610b09`) | ✓ right, and now right for the right REASON |
| break records | own record type, not completed_job | ✓ a seam is not a job |
| parent | aggregates children, never re-derives | ✓ |

This is the same sentence from the original design — *"we stop losing good rooms because
we stop treating each phase as a special thing"* — and both open defects are literally
that.

### Card: a VISUAL MATCH TO THE HUMAN'S PLAN

*"in a perfect world the card would hold the full job for the live queue and just check
off each completed piece as it finishes — a visual match to the human's plan, while the
backend can do what's needed to make it work."*

**The card's granularity follows the PLAN, not the dispatch.** Live evidence
(2026-08-03): the queue was authored as FOUR items — Kitchen / Wait 20 min / Entryway /
Home Office — and the backend produced THREE phases by batching Entryway + Home Office
into one dispatch. The card renders the backend's three, so item 4 can never tick.

Batching exists to satisfy the brand. The human never authored it and must never see it.

**RP-047's card half is therefore the WRONG DIRECTION and is on hold.** "Render the group
as one entry" makes the card mirror the dispatch shape — merging items 3 and 4 into
"Entryway and Home Office" and calling the mismatch resolved by hiding it. The correct fix
keeps the four authored items and makes completion real, which requires the rollover.

RP-047's BACKEND half (`6831ccd`: current_room_ids + current_phase) stays — exposing what
the snapshot knows is right regardless, and a plan-shaped card still needs to know which
dispatch is in flight.

### Consequence: the ordering inverts

The rollover is not a nice-to-have behind the display fix. It is what MAKES the display
possible. Sequence:

1. Narrow the rollover guard (state-based, not phases-based) so rooms transition inside a
   group — the queue can then tick per authored item.
2. Segment the phase's counter slice instead of dividing it, so timings are OBSERVED
   (`allocated: false`) — wave 3's allocation gate then becomes a no-op for grouped
   phases, which is what it should always have been.
3. Only then revisit the card, against the plan shape rather than the dispatch shape.

---

## Steps 1 and 2 are LANDED (2026-08-03)

| Step | Commit | State |
|---|---|---|
| 1a. Guard moved off the whole function onto the native branch | `40cbaac` | landed, source-pinned |
| 1b. Non-cleaning accumulator (the follow-up 1a required) | `5ec6893` | landed |
| 2. Phase-slice segmentation | `def78af` | landed |
| 3. Card, against the PLAN shape | — | **OPEN — next** |

### 1b — why the guard move needed a follow-up

`current_room_started_at` is stamped at DISPATCH, so undock + transit + any mid-room mop
wash / recharge trip were all charged to the room. Re-enabling rollover made that number
load-bearing. Fixed with `current_room_noncleaning_seconds` + `..._since`, siblings of the
pause pair, closed/opened by `record_active_job_transition` off the vacuum entity and
re-seeded at every site that stamps a new room window.

**A state GATE would not have worked** — suppressing the tick does not stop the clock; it
defers the phantom to the instant the gate lifts. Only subtracting the span fixes it.

**Fails OPEN, deliberately.** Unreadable state ⇒ subtract nothing. A false "non-cleaning"
is UNBOUNDED (subtracts forever ⇒ room never advances ⇒ the exact stall 1a fixed); a false
"cleaning" is BOUNDED (one span stays charged, i.e. the old behaviour).

Measured margin that made 1a safe to land first: phase start → first cleaning was **3 s
and 13 s** across four live runs, against a ≥105 s threshold.

### 2 — the trap that would have shipped green

`build_segments` counts from **zero** while `cleaning_time`/`cleaning_area` are CUMULATIVE
across the run, and `_prepare_window` re-bases only at a counter reset — once per RUN, not
per phase. Fed a phase slice it credits the whole run's totals to the group's first member.
Measured (`_probe_phase_slice_seg.py`): a slice opening at `cleaning_time` 600 returns
`time_active_s` **660.0** and `area_delta_m2` **46.5** for a room that did 60 s / 4.5 m².

The existing SOPT battery could not have caught it — its synthetic streams carry no
plateau, so they always fall back to apportioning. New SOPT-11..14 force the observed path
with exact values.

Three gates, each falling back to the even split: **order**
(`capabilities.honors_clean_order` — Eufy True, Roborock False), **count** (exactly n
bouts), **reconciliation** (parts sum back to the group's whole).

`allocated` now means exactly *"arithmetic, not an observation"* — not *"came from a
group"*. A segmented group row is admitted to learning on the same signal, at the same
reliability, as an atomic multi-room job's row.

### Open judgment call to confirm with Chris

Segmentation maps segment *i* → `group_ids[i]` on the strength of the
`honors_clean_order` DECLARATION. There is no independent confirmation available: the live
rollover's own order is derived from the queue, so cross-checking it would be circular.
If Eufy ever reorders within a `selectRoomsClean` batch, learning would take confidently
wrong per-room rows where it previously took none. Reversible per-brand by declaring
`honors_clean_order: False`.
