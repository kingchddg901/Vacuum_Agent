# Phased jobs — a concept/execution mismatch, not a bug

**Written 2026-08-02. Nothing decided; nothing to execute yet.**

This is not a defect report. Every individual bug below is real and several are already
repaired. The point is that they are **symptoms of one architectural divergence**: the
phased-job model was designed, documented as chosen, and then not built — and everything
since has been patching the consequences.

## 1. What was chosen

`c1fb647` (2026-06-02), *"feat(dispatch): wire sequenced job model into start + finalize"*:

> **"Each phase finalizes as its own job record (Option B), reusing the whole
> learning/finalizer path."**

Chris's own description of the intent, independently, 2026-08-02:

> *"a phased job is multiple jobs merged. each should be treated like a job as normal
> then merged for its aggregate numbers"* — and concretely, a `room → pause → 2-room`
> run should have produced **1. a 1-room job finalized, 2. a lost phase for the charge or
> timer, 3. a two-room job finalized.**

The design and the owner's mental model agree exactly.

## 2. What was built

The **same commit** contradicts itself. Its added code:

```python
if await manager_local.maybe_advance_phase(...):
    any_changes = True
    continue            # <- jumps PAST the finalizer
finalize_result = None  # <- only reached on the LAST phase
```

and its own added comment:

> `# every adapter today — return False here and finalize as before.`
> `# Each phase finalizes only when it is the LAST.`

Option B was never implemented. A non-final phase produces **no record**. One run = one
merged record, from the first day sequencing shipped.

This is the same failure class as A3-REC-3 being marked closed while half of it was open
(see `_reopened_findings.json`) — a claim recorded as done, with nothing mechanical able
to notice. Here it sat for two months at architecture scale.

## 3. What was built on top of the mismatch

Every one of these exists to patch a consequence of merging. **None is wrong, and none is
discardable** — see §7: the architecture may supersede their implementations, never their
guarantees.

| packet | patches |
|---|---|
| RP-013a | phase-type-aware capture validity |
| RP-013b | fabricated per-room allocation inside a group |
| RP-013c | completed evidence surviving a phase reset |
| RP-013d | the `queue` block clobbered to the last phase |
| RP-013f | `cleaning_time_seconds` re-derived from phase sums |
| RP-047 | live progress pinned to `room[0]` of a group |

The phase-timing snapshot's own docstring names the cause:

> *"Snapshot the FINISHING phase's room_timing from its OWN counter slice BEFORE advance
> resets the queue/timing. Without this, strict-order finalization segments the whole
> accumulated counter stream against only the LAST phase's queue."*

That is a workaround for having one record where there should be several.

## 4. Live evidence — alfred `job_2026-08-02T11-15-51`

Shape run: `[kitchen] → wait 2 min → [entryway + hallway]`.

**(a) The group's per-room numbers are fabricated, and learning eats them.**
`allocated: true` / `allocation_group_size: 2` mark them as apportioned, not observed.
That flag is **written in two places and read in none**. `stats_rebuilder` consumes
`cleaning_wall_seconds` — a field its own capture docstring says is *"shared verbatim
across members"* — as if it were per-room. Both group rooms carry `820`, so each learned
**13.67 minutes**; summed that is 27.3 minutes of room time inside a 21-minute job.
Entryway historically runs ~30–60 s.

**(b) The planned wait is invisible.** `_run_had_break_phase()` is computed at
`job_finalizer.py:805`, used to exempt the idle-wall guard, and **discarded**. The system
demonstrably knows the run had a break; nothing persists it. `overhead_observed` has slots
for entry / inter_room / return / recharge / wash — a planned `wait` is none of those.

**(c) The wait contaminates a different shape.** The learning key is

```
map:12|count:3|rooms:5,8,4|modes:vacuum,vacuum,vacuum
```

with no phase structure, so a FLAT three-room run of the same rooms shares it — and has
now been taught that it takes two minutes longer, because Chris chose to pause. Add a
20-minute charge step and the flat run inherits that too.

**(d) Live progress freezes.** `current_room_id` pins to the group's first room for the
phase's duration, because `record_completed_room` never fires inside one dispatch. The
card showed Entryway for 13m40s and never reached Hallway.

## 5. The proposed model

**A phased run becomes N+1 things.**

- **One record per CLEAN phase.** A job in the full sense — own queue block, own
  segmentation, own completion evidence, own `used_for_learning`. A single-room phase
  learns that room exactly. A multi-room group phase learns what a standalone multi-room
  job learns, which is *not* per-room — correct, and it stops the fabrication.
- **Break phases produce no `completed_job`** — Chris's "lost phase" — but they DO get a
  durable phase record of their own shape. See §8; this is what closes §4(b).
- **A parent bucket for the sequence.** An AGGREGATE, not a second learner — see §8, which
  narrows this considerably from the first draft.

Identity on every phase record: `phase_job_id`, `phase_index`, `phase_type`,
`phase_count`. Siblings reassemblable; each independently valid.

### The parent's three gap kinds

Today all three are summed into one `overhead_observed.total_overhead_minutes`.

| | source | learnable? |
|---|---|---|
| planned hold (`wait` / `charge_wait`) | the PLAN — known before the run | **no** — it is a constant the user chose |
| boundary transit (undock, travel, re-acquire) | observed per phase gap | **yes** — the real cost of phasing |
| entry / return | observed once per run | yes, already partly modelled |

Only the middle should ever reach an estimate as a learned quantity. The first is
arithmetic. In `11-15-51`: 205 s of boundary, of which **120 s was the planned wait** and
~85 s was genuine transit (kitchen sits ~30 s from the dock).

### Planned holds are known, not inferred

The parent does not reconstruct gaps from timestamps — the plan already says where they
fall. But the two break types differ:

```
wait         {type:"wait",        wait_minutes:int}            <- duration planned
charge_wait  {type:"charge_wait", target_battery_percent:int}  <- TARGET planned, duration NOT
```

So a slot carries **planned + actual + outcome** (held / skipped / truncated). A
`charge_wait` to 80 % on a robot already at 85 % is a planned slot that cost nothing;
recording it as "charging to 80 % takes zero minutes" would be the same class of lie as
the 50/50 allocation.

### What it makes possible

```
estimated_total = Σ phase estimates           (children — each a normal job)
                + Σ planned break durations   (arithmetic, from the plan)
                + Σ learned boundary transit  (parent's own bucket)
```

No current bucket can produce this. `11-15-51` estimated **3.61 minutes** and took **21**.

## 6. Open questions

1. **Cancellation semantics.** Phase 1 finalizes and should teach; phase 2 is cancelled
   and should not. Per-phase records make that natural — but what is the PARENT's status
   when one child completed and one was cancelled?
2. **The review surface.** One user action becomes several rows unless the UI groups by
   `phase_job_id`. Card work, and the visible cost of the change.
3. **Existing archives.** No record carries a parent id. Are they read as single-phase
   runs, or excluded from the parent bucket?
4. **Does the group phase teach anything?** Under the model it cannot teach per-room.
   Either those rooms keep their existing estimates untouched, or a `[8+4]` composite key
   learns — which only helps if the same grouping recurs.
5. **Was the merge deliberate?** Chris suspects he may have introduced it to get "pure
   job findings". No commit doing so has been found — the merge appears to date from
   `c1fb647` itself — but if per-phase records make job-level analysis harder, that trade
   should be named before it is reopened.

## 7. The six packets — CORRECTED (gpt review, 2026-08-02)

An earlier draft said "six landed packets become unnecessary rather than wrong." **That
was overstated and is withdrawn.** The replacement, verbatim from the review:

> *"The phase-record architecture may supersede the IMPLEMENTATIONS of six landed
> packets. Their guarantees and reproducers remain BINDING until each is mapped to, and
> proven under, the replacement model."*

The test is not *"does the new model make these implementations obsolete?"* It is
**"does the new model preserve every guarantee those packets added, through a cleaner
path?"** A repair that removes six fixes is plausible. A repair that removes six
**invariants** is almost certainly wrong.

### The invariants that must survive, whatever the architecture

Each of these was discovered the hard way. Implementations may be deleted; these may not.

1. A completed phase credits only its own rooms.
2. Archived completed-room ids agree with the finalized child.
3. One child cannot inherit another child's counters.
4. Grouped-room allocation is never consumed as observed per-room timing.
5. Parent aggregation does not double-count child minutes, area, or battery.
6. A completed child survives cancellation or failure of a later child.
7. A wait or charge phase cannot contaminate cleaning overhead.
8. A flat three-room job cannot share a learning identity with `[room] → wait → [two rooms]`.

Every existing reproducer should be **redirected** at the child-record / parent-aggregation
model, not retired with the implementation it was written against.

## 8. Corrections from review — the parent is an AGGREGATE, not a second learner

The draft called the parent "a different learning subject". Too loose, and it invites the
exact pollution the model exists to prevent: **teaching both children and parent
double-teaches the same work.**

**The parent OWNS:** total wall-clock, total battery delta, ordered phase structure,
overall outcome, child record ids, the user-facing summary, interruption/resume history.

**The parent DOES NOT teach:** ordinary room duration, queue shape, or cleaning overhead.

The one thing it may legitimately learn is **orchestration cost** — boundary transit, the
price of *having* phases — and only as a deliberately separate model, never folded into
cleaning overhead. That is the narrow reading of §5's middle gap kind; the broader reading
in the first draft was wrong.

### Non-cleaning phases DO get a record — just not a `completed_job`

The draft said break phases "produce no record", following the "lost phase" phrasing. The
review's correction is better and closes §4(b) directly: a break needs a durable **phase
record**, of its own shape —

```
type: wait | charge | wash | other blocker
planned: duration (wait) or target (charge)
actual: start, end
outcome: held | skipped | truncated
reason
parent_run_id, ordinal
```

— which contributes to the parent's wall-clock but **not** to cleaning time or learned
cleaning overhead. That preserves "one record per phase" without pretending a two-minute
timer cleaned zero rooms.

### Mixed child outcomes must not collapse

```
Kitchen             completed, learning-eligible
Wait                completed
Entryway + Hallway  cancelled
```

Child truth stays authoritative. The parent exposes an aggregate (partial / interrupted)
**plus the full child outcome list** — never one lossy status. This is among the largest
benefits of the architecture and the draft undersold it: **cancelling phase 3 stops
retroactively poisoning phase 1.**

### A group phase teaches the GROUP, not invented rooms

For `[8, 4]` the system genuinely observed one two-room cleaning job. It may learn a
composite: duration, battery, settings, area, phase overhead, dispatch success. It did
**not** observe 375 s in Entryway and 375 s in Hallway.

So: keep the allocated rows for presentation and accounting; never feed allocated wall
time into per-room learning as observed duration; teach individual rooms only where
authoritative boundaries exist; otherwise teach the composite or skip room-level timing.
`allocated: true` finally acquires semantic force.

### Migration must not manufacture children

Legacy monolithic records are marked legacy and kept for display and aggregate metrics.
Trustworthy totals (battery, area, wall-clock) survive; ambiguous allocated per-room
timings are excluded from room learning; no modern phased shape key is assigned. Migrate
only where phase boundaries are independently recoverable.

Inventing child records from insufficient history would repeat the precise error being
repaired — **converting allocation into observation.**

## 9. An unverified prediction from review — NOT observed

The review states that during the group phase Entryway *"stayed at 99%, acquired the
entire phase clock, and triggered a false stuck warning."* **Chris reported only that the
card never advanced to Hallway.** The 99 %, the clock, and the stall event are the
reviewer's inference, not observation, and are recorded here as such.

They are, however, a sound prediction worth testing. `detect_run_anomalies` fires a stall
when the bounds gate blocks rollover and elapsed >= `stall_ratio` (2.0) x the room's
timing threshold. Entryway pinned for 13m40s against a ~1-minute estimate clears that bar
by an order of magnitude, so a **false stall event on every grouped phase** is likely.
Not confirmable from the record — stalls fire as bus events, not record fields.

**Consequence for RP-047:** the stall detector must be group-scoped when member
attribution is unavailable, not merely the label. Added to that packet.
