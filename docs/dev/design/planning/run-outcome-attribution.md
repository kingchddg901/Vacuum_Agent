# Run Outcome Attribution — evidence the integration computes, then discards

**Status:** design **DECIDED 2026-09-15, not built.** Two defects with one shape. The
mechanism and the traps are settled below; nothing here is scheduled.

> **Scope note.** A delta on the learning layer described in
> [19-event-ingress](../../19-event-ingress.md) and the job record in
> [03-data-model](../../03-data-model.md). No new subsystem, no new service, no adapter
> work — both changes are core and brand-neutral, and neither touches an adapter.

---

## 1. One thesis, two symptoms

The integration already computes the evidence it needs for both of these, and then
throws it away at the seam:

| Computed by | Consumed by | What happens |
|---|---|---|
| `jobs/active_job.py::detect_run_anomalies` — `skipped_room_ids` | `learning/job_finalizer.py::_update_trouble_rooms_log` | Ignored. The log re-derives a cruder answer by set subtraction. |
| `core/manager.py::_fire_stuck_event` — full stall payload | *nothing* | Fired on the bus. Never persisted. |

Neither is a missing capability. Both are a consumer declining a signal that already
exists, which is why the fixes are small and the reasoning is worth writing down — a
future reader will otherwise assume the evidence had to be invented.

---

## 2. Skipped is not missed

### 2a. The defect

`learning/job_finalizer.py::_update_trouble_rooms_log` decides what a room did by
subtraction:

```python
missed_ids = set(queued_room_ids) - set(active_completed)
```

There are exactly two outcomes, and every queued room pays into the denominator:

```python
entry["run_count"] = _safe_int(entry.get("run_count"), 0) + 1
if room_id in missed_ids:
    entry["miss_count"] += 1
    entry["last_missed_at"] = ended_at
else:
    entry["last_cleaned_at"] = ended_at
entry["miss_rate"] = round(entry["miss_count"] / run_count, 3)
entry["is_trouble"] = entry["miss_count"] >= 2 and entry["miss_rate"] >= 0.33
```

**A room the robot never reached is indistinguishable from a room it entered and failed
in.** Queue Kitchen → Bedroom → Office, have the run die in the Kitchen, and Bedroom and
Office each take a miss for a fault that was entirely the Kitchen's. They were not
tested. They were not even visited.

Two such runs is enough: `miss_count >= 2` and `miss_rate >= 0.33` both clear, and the
room is branded `is_trouble` having never once been the problem.

### 2b. The signal already exists, and it is already conservative

`jobs/active_job.py::detect_run_anomalies` computes exactly the missing distinction, and
its own docstring states the discipline:

> **skipped** (conservative): a queued room the live tracking has provably advanced past

*Provably advanced past* is the right bar and it is already met — this is not a
heuristic to be invented, it is an existing one being ignored. It is deduped against
`_skipped_notified_room_ids` so the same skip is not re-announced, and
`learning/estimator.py::reanchor_timeline` already persists the outcome per room
(`entry["skipped"] = True`), because the estimator needs a skipped room to be
**resolved rather than perpetually remaining**.

So the vocabulary exists in one subsystem and not in the other. Two parts of the
codebase answer *"did this room get its turn?"* differently, and the one driving the
user-visible badge has the weaker answer. Centralize the question, not the vocabulary.

### 2c. The fix, forward

Pass `skipped_room_ids` into `_update_trouble_rooms_log` and exclude those rooms from
**both** counters.

**Excluding from `miss_count` is obvious. Excluding from `run_count` is the one that
needs arguing, and it matters in the opposite direction.** The denominator means *runs
that actually tested this room*. Leave never-reached runs in it and a genuinely failing
room looks better than it is, because aborted runs pad its denominator with attempts
that never happened. The cascade inflates innocent rooms; the padded denominator
deflates guilty ones. Both are the same error.

A room that is skipped in every run of a job therefore moves neither counter and stays
exactly where it was — which is correct. Nothing was learned about it.

### 2d. This is an existing house rule, unapplied at room level

None of §2 is a new principle. [27 — What Counts As
Learnable](../../27-learning-eligibility.md) §1 already settles both halves of it for the
job-level record, in almost these words:

> The record's `outcome` block carries both, and **conflating them loses information** […]
> **A blocker is a reason, not just a veto.** The record keeps the specific list, so the
> review tab can say *why* a run was skipped rather than only that it was.

A job gets `sanity_flags` and `learning_blockers` — two vocabularies, deliberately not
collapsed, with the reason retained. A **room** gets `missed_ids`, a set subtraction with
no reason attached at all. The defect is that the discipline stops at the job boundary.

So the fix is not merely to exclude skipped rooms from the counters. **Record the reason,
the way the job record already does.** An excluded room with no stored reason recreates
the original problem one level down: a number that moved, with nothing to say why, and a
user with no way to tell a never-visited room from a clean one. `is_trouble` needs to be
explicable, not just correct.

---

## 3. TRAP: the retroactive half cannot be a patch

`trouble_rooms_log` persists only `run_count` and `miss_count` — **totals, with no
per-job detail.** There is no record of which runs contributed, so a corrected value
cannot be computed from the file. Editing it in place would be guessing.

The rebuild path is `learning/stats_rebuilder.py::build_jobs_index_payload`, which
already walks every completed job record. Recompute from `jobs/`, do not patch the
accumulator.

### 3a. TRAP inside the trap: exclusion moves the rate the wrong way

Jobs written before the `skipped` field existed cannot be classified. **They are
excluded, not guessed** — but excluding them shrinks the denominator, and a shrinking
denominator makes `miss_rate` *rise*.

A room with 2 misses across 10 recorded jobs reads 20%. Exclude 6 unclassifiable jobs
and the same 2 misses read 50% — over the `is_trouble` threshold, from a change that
added information. A rebuild that silently does this looks like a regression to the user
and is indistinguishable from one in a bug report.

Consequences, both required:

- The rebuild must report how many jobs were excluded as unclassifiable, not just the
  new numbers.
- `is_trouble` must not be evaluated at all below a floor of classifiable runs. A rate
  over a denominator of 3 is not a rate.

---

## 4. This is a sufficient cause for IN5ATBW9

`IN5ATBW9` records that the miss-rate badge can pin a room at *"chronically missed,
67%"* with no way back short of deleting a file by hand, and that the file cannot
self-heal because its only writer refuses on an unreadable read.

The cascade is a complete explanation of how a room gets there without ever being at
fault, and §2c is the way back down that does not require a hand edit. Whether it is the
*only* cause is not established here and should not be assumed — but a fix for this
defect should be checked against that record before that record is closed.

---

## 5. Stall events: fully built, then dropped

`core/manager.py::_fire_stuck_event` constructs a complete payload at two call sites in
the manager plus the timing branch in `jobs/active_job.py`, puts it on the event bus, and
nothing keys it, counts it, or keeps it.

The asymmetry is what makes it read as a defect rather than a choice:

| Origin | Retention |
|---|---|
| A fault the **device** announces | 50 durable slots, with a service to read them |
| A stall **we** detected ourselves | A notification, and a picture the next stall overwrites |

Same subsystem. Opposite retention. The evidence we worked harder for is the evidence we
keep least.

**Scope, and this is the load-bearing constraint: it ships as DIAGNOSTICS, never as
learning input.** A stall record is an observation about one run under conditions nobody
reconstructed. Feeding it into the estimator or into room scoring would let an unexamined
signal move numbers the user sees. [27 — What Counts As
Learnable](../../27-learning-eligibility.md) owns that judgement and lists every input
allowed to reach it; a stall record is not on that list and this design does not add it.
Persist it, expose it to diagnostics, and stop.

Shape: a capped per-vacuum ring in the existing store, written from the three sites that
already build the payload. Reuse the payload as-is — do not design a second schema for it.

---

## 6. What it would take

| Piece | Where | Note |
|---|---|---|
| Thread `skipped_room_ids` to the finalizer | `jobs/active_job.py` → `learning/job_finalizer.py::_update_trouble_rooms_log` | The value already exists at the source |
| Exclude skipped from both counters | `_update_trouble_rooms_log` | §2c — `run_count` too, not only `miss_count` |
| Record the **reason**, not just the exclusion | `_update_trouble_rooms_log` | §2d — the job record already does this; the room record does not |
| A classifiable-runs floor on `is_trouble` | same | §3a — a rate over 3 runs is not a rate |
| Rebuild from `jobs/` | `learning/stats_rebuilder.py::build_jobs_index_payload` | Recompute; never patch the accumulator |
| Report excluded-job count | rebuild output | §3a — otherwise a rise looks like a regression |
| Capped stall ring | existing store, written from `core/manager.py::_fire_stuck_event` + the `active_job` timing branch | Diagnostics only (§5) |
| A gate that bites | tests | See §7 |

---

## 7. The gate, because this is a claim that must be able to go red

A test asserting "skipped rooms are not counted" passes trivially against a fixture
where nothing is skipped. The input that makes it red must be named:

**A three-room queue, completion recorded for room 1 only, room 2 marked skipped, room 3
neither.** Correct behaviour: room 1 gains a clean, room 2 moves nothing at all, room 3
takes the miss. Today's code gives rooms 2 **and** 3 a miss and a `run_count`, so the
test fails before the change and passes after — and ablating the `skipped` argument
restores the failure.

The rebuild needs its own: a `jobs/` fixture mixing classifiable and pre-field records,
asserting the excluded count is reported and that `is_trouble` stays false below the
floor.

---

## 8. Open — decide before building, not during

1. **Where does the classifiable-runs floor sit?** 3 is a guess made while writing this.
   It wants a number from the real `jobs/` store, not from a design doc.
2. **Does a skipped room deserve its own visible state?** Today the card shows cleaned or
   missed. "Not reached" is honest and is a third badge, and a third badge is a real cost
   for an outcome most users will read as a miss anyway.
3. **Does the rebuild run automatically or on request?** Automatic means a user's numbers
   move without them asking, on an upgrade. On request means most installs never get the
   correction.
4. **Stall ring depth.** The device-fault side keeps 50. Matching it is defensible purely
   for symmetry, which is not the same as knowing 50 is right for stalls.

---

## 9. Why this is written down and not built

Nothing here is hard. It is written down because the reasoning is the expensive part and
it is not recoverable from the diff: the reason `run_count` must also exclude skipped
rooms, the reason the rebuild cannot be a patch, and the reason a correction makes the
number go **up** are all invisible in the finished code and all three are the kind of
thing a later reader reverses by accident.

It was found by mining [botts7/dreame-scheduler](https://github.com/botts7/dreame-scheduler),
whose run-history log uses *"runs that targeted this room"* as its denominator. The idea
transferred; the defect it exposed here was ours already.
