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

### Wave 3 — learning redirect

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
3. **Wave 1+2 land together?** My read is yes — Wave 1 alone fragments the review surface.
   Confirm, because it makes the first landing bigger.

## What this plan deliberately does NOT do

- Does not fix the three live bugs from `11-15-51` directly. Waves 3 and 4 subsume them;
  patching them first would be work thrown away.
- Does not revert any landed packet. Wave 5 decides that, with evidence.
- Does not touch the estimator's composition (`Σ children + Σ holds + Σ transit`). That is
  the payoff, and it is a wave of its own once the data exists.
