# 06 — How a Run Ends

**Scope.** Everything from "the run is over" to "the record is durable and the derived
stores agree with it." The first half of a run — queue build, start, live monitoring and
room transitions — is a separate document.

The end of a run has many authorities and one outcome. Almost every defect here has been an
ordering or an exclusion problem rather than a logic error.

---

## 1. RUN and RECORD

The folder names mislead here.

| | owns | lives in |
|---|---|---|
| **The RUN** | deciding the run ended, releasing runtime holds, firing the event, persisting `manager.data` | `core/`, `jobs/`, `listeners/` |
| **The RECORD** | the exactly-once claim, the completed-job archive, the derived stats | `learning/` |

**`learning/` is not a post-run tier.** No module in it is reachable only at end-of-run, and
`learning/job_finalizer.py` runs at job **start** — `LearningJobFinalizer.save_live_snapshot`
writes the dispatch-time planned estimate that finalization later compares against. Reading
`learning/` as "the part that happens afterwards" will mislead you about half of it.

The import arrow is one-way (`core` imports `learning`; `learning` imports `core` only for two
pure helpers plus one `TYPE_CHECKING` arrow), but the runtime arrow is two-way through
`hass.data`. That asymmetry is deliberate and §3 depends on it.

> **One anomaly.**
> `learning/external_run.py::ExternalRunManager` was extracted out of `core/manager.py` but is
> still constructed and owned by core as `self.external_run`, with twelve delegators left on the
> manager. It is the only one of core's fifteen sub-managers living outside core's own
> dependency tier. The delegators are **load-bearing, not cosmetic** — `learning/services.py`,
> `listeners/lifecycle.py` and the tests all reach it as `manager.<method>`. Deleting them to
> tidy the facade breaks the service layer.

---

## 2. One status machine, many authorities

A run has exactly one status machine — `idle → started ⇄ paused → completed` — plus a
separate `external` slot for app-started runs. Many independent authorities can drive it
to `completed`:

- normal completion (the lifecycle listener)
- manual cancel (service)
- pause timeout (reaper)
- path-blocker cancel (rule match)
- charge-wait timeout
- the cancel-likely reclassification (at finalize)
- the stranded dispatched-run reaper
- the phased-parent reaper
- external-run close

Every one of them converges on two functions:

| chokepoint | what it does |
|---|---|
| `learning/manager.py::LearningManager.async_finalize_completed_job` | holds the exactly-once claim, writes the record |
| `jobs/active_job.py::ActiveJobTracker.mark_active_job_finalized` | stamps the slot, releases every runtime hold |

The behaviour lives in the mutual-exclusion scheme that decides which authority owns a run, and
in the ordering of the guards that implements it. Three flags carry nearly all of that
weight — `has_observed_active_lifecycle`, `_phase_dispatch_pending` (with its liveness
pair), and `_cancel_in_flight` — and each is read by
more than one authority with *deliberately different strictness*. **The same flag is an
unconditional veto to one gate and a time-limited lease to another.** Making them symmetric is
the dominant failure mode in this area; most of the guards here exist because an earlier version
was symmetric.

---

## 3. The exactly-once claim

### Where the claim lives

The claim lives on `learning/manager.py::LearningManager.async_finalize_completed_job`, **not**
on `core/manager.py::EufyVacuumManager.finalize_learning_for_active_job` — which is the obvious
place, since it is the function every listener and reaper actually calls. A comment at the old
site forbids putting it back.

The obvious place fails because the `finalize_learning_job` service calls the learning
manager *directly*, with no core manager involved. A guard on the wrapper is simply walked past.
A second finalize then peeks an already-nulled error latch and `os.replace`s the record with
`had_errors: False` — destroying the run's fault history with no trace that it ever existed.

### Two gates, not one

`finalized` is permanent; `finalize_claimed_at` is transient. **`finalized` is written inside the
claimed window**, before the claim releases — not left to the caller's
`mark_active_job_finalized`.

That ordering is load-bearing. `mark_active_job_finalized` runs *after* an await — the
mapping-tracker hop in the lifecycle listener. A second listener task from the same physical
event interleaves in that gap, finds the claim released and `finalized` not yet set, and
finalizes again.

**The claim is written into the STORED dict** (`manager.data["active_jobs"][vac][map]`), never
into what `get_active_job` returns. `ActiveJobTracker._normalize_active_job` returns a *copy* — a
claim written there evaporates on return and the gate never engages at all, while looking
correct.

**A failed finalize releases the claim.** Success is defined narrowly as *the result carries a
`completed_job` dict* (`learning/manager.py::finalize_result_succeeded`, `IN5BRA39`). Treating
any non-`None` result as success would accept a refusal dict — firing completion events, marking
the slot, and feeding the derived stores from a run that was never written.

**Orphaned claims are cleared unconditionally at startup** — no age heuristic, no reaper. The
trade is explicit: `active_jobs` is persisted, so a claim orphaned mid-finalize returns on the
next boot and blocks that job from *ever* finalizing. A permanent block is strictly worse than
the duplicate finalize the claim exists to prevent.

### Phase children bypass it deliberately

`jobs/phase_runner.py` calls `finalize_from_inputs` directly with its own per-phase idempotency
key, and its docstring says **"Not through the chokepoint."** Routing a per-phase finalize through
the claim would set `finalized: True` on the stored active job at phase 0, so every later phase —
including the real final one — returns `already_finalized` and writes nothing.

---

## 4. Where ordering carries the behaviour

### The stranded-run predicate

`jobs/job_monitor.py::is_stranded_started` decides whether a run still marked `started` has ended
without reaching its brand's completion terminal. Two of its clauses are positioned, not
merely present.

**An errored robot is reapable, and the clause sits ABOVE the job-active and docked/idle gates.**
This reverses the predicate's original rule ("an error may recover; reaping a maybe-recovering
run is worse than a rare lingering record"). It was disproved on hardware: a robot wedged on a
box threw `bumper_stuck`, and both gates below refused to reap it — upstream keeps the cleaning
binary ON for an errored robot, and `error` is neither `docked` nor `idle`. Move the clause below
them and it becomes **unreachable dead code**: an errored robot fails both by construction, so
the trapped-robot strand returns permanently.

The recovery tolerance that the original rule wanted is not lost. It lives in the caller, which
stamps `stranded_since` on the first tick and only reaps after a grace window, clearing the stamp
if the condition stops holding. A transient error that clears inside the window costs nothing.

**The never-armed branch sits above everything and carries exactly one escape hatch** — a run
whose `task_status` already reached the brand's completion value. Without it, an install where
the brand's `job_active` role fails to resolve can never rescue an unarmed run by actually
completing.

### `_phase_dispatch_pending` is a lease, not a veto

It was converted from an unconditional reaper exclusion into a lease with liveness. When the
watchdog gives up, `PhaseRunner._mark_phase_watchdog_dead` **stamps the liveness fields rather
than clearing the pending flag.** Both simplifications were considered and rejected:

- keeping the exclusion unconditional wedges a run forever behind a guard nobody will release;
- clearing `pending` on a dead watchdog lets the completion gate advance a run whose phase never
  dispatched.

The liveness margin is **derived** from the same `_phase_timing` the watchdog uses
(`max_attempts × verify_seconds + 60`), not a constant — so a brand declaring longer retries
automatically gets a longer lease.

### The cancel interlock

`_cancel_in_flight` is a single-flight latch set on the *stored* record before `return_to_base`,
and it is **universal** — atomic and phased jobs alike. It replaced reuse of
`_phase_dispatch_pending`, which only ever covered phased jobs, leaving atomic jobs with no latch
at all.

It is read in four places, because a cancel's own `return_to_base` dock is **indistinguishable
from a phase completion** on a path-optimising brand — a robot sitting docked and charging
between phases is precisely that brand's completion signal.

Two details:

- **A cancel whose `return_to_base` raises clears the latch and re-raises.** Leaving it set turns
  a transient failure into a permanent single-flight lock: every later cancel returns
  `cancel_in_progress` for the life of that slot.
- **`maybe_advance_phase` refuses on `finalized or status != "started"` *in addition* to
  `_cancel_in_flight`.** `mark_active_job_finalized` deliberately clears `_cancel_in_flight` so a
  later run reusing the slot does not inherit a stale latch — which means that after a cancel
  completes, the flag is False again while the run is over. The second refusal is what covers
  that window.

`PhaseRunner._dispatch_active_phase` re-reads the stored job immediately before the wire send,
after the last await — not the parameter it was handed. Four sequential awaits sit between the
top-of-attempt check and the send.

---

## 5. Finalization

`LearningJobFinalizer.finalize_from_inputs` is split into a loop-bound collection half
(`_collect_finalization_inputs`, which reads HA states) and an executor-safe compute-and-I/O
half, with an explicit **commit point** in the middle: `store.save_completed_job`.

The error latch is **peeked before** it and **cleared after** it. This replaced a single
read-and-clear harvest (`ErrorTracker.harvest_active_run`, retained but deprecated — *"Do not add
new callers"*), because **a destructive read cannot be made safe against a save that fails
afterwards**: the run's error history is destroyed with no record carrying it, and the retry then
records `had_errors: False`.

`commit_active_run` clears the latch **by identity** — same `first_seen_at` and same
`error_count` — not by assigning `None`. Since the clear is no longer atomic with the read, a
rising edge can extend the latch in between; an unconditional clear would discard evidence
belonging to the *next* run.

Two orderings around the commit point:

- **The battery aggregate push is deferred past the commit**, while eligibility is still
  evaluated before it. The aggregate store is an incremental read-modify-write outside
  `rebuild_all`, so an aggregate counting a run whose record never landed can never be
  reconciled.
- **The idle-wall hold is applied before battery eligibility is read.** Move it after and a held
  anomaly enters the battery drain means silently.

The cold-start idle-wall guard **holds** rather than excludes — a `learning_blocker` plus
`used_for_learning: False` — because a hard exclusion is not Restore-able from the review tab. It
is always-on rather than gated on an existing baseline, since the danger case *is* a new room's
first sample.

---

## 6. Error seconds

Faults are latched live into one per-vacuum dict whose `errors[]` list is a chronological
sequence of rising edges, each optionally stamped `recovered_at`. At finalize, that list becomes
wall-clock intervals and **some** of them are subtracted from `cleaning_time_seconds`.

**Only evidence-invalidating seconds are deducted.** Safe and unclassified seconds are computed,
reported, and left alone. This replaced a flat `cleaning_time_seconds -= total_error_seconds`.
The live failure it fixed: five station water-pump faults deducted 455 s from a 360 s clean and
recorded it as zero. Undo it and a fault the robot worked straight through zeroes a productive
run, and the model learns the area takes no time.

**Two axes, deliberately independent:**

| axis | decides | drives arithmetic? |
|---|---|---|
| **evidence** — invalidating / safe / unclassified | what may be deducted | yes |
| **source** — dock / robot / unknown | which box to point the user at | **no** |

They genuinely diverge in both directions, which is why collapsing them fails: a
station-*named*, robot-*sourced* fault can be evidence-safe because it happens after the floor
work.

**UNCLASSIFIED is a real answer and is preserved, never deducted.** A brand declaring no tables,
or a vendor code newer than the table, keeps its full cleaning time. The asymmetry is deliberate:
*wrongly crediting adds noise that averages out; wrongly zeroing destroys the observation.* A
`.get(code, True)` default would reintroduce the exact incident this exists to fix.

**Two sets are declared**, invalidating and safe, rather than one list with an implicit
complement — so an unrecognised code is distinguishable from a deliberately-safe one.

Classification is a **static adapter-declared table**, chosen over a runtime timeline oracle that
asked "was the robot cleaning when this fault fired?". Rejected because the fault timestamp
records when the vendor *surfaced* the fault, not when it occurred.

---

## 7. The derived stores

> ⚠ **Destructive read-modify-write stores REFUSE on an unreadable read.** A tri-state read
> distinguishes ABSENT from UNREADABLE (`learning/history_store.py::read_json_outcome`,
> `IN2QDNB3`). This exists because a corrupt nine-room `trouble_rooms` store was once rewritten
> as a one-room store — years of chronic-miss history replaced by one job's rooms.
>
> **The consequence is that the file does not self-heal, and the code's own warning text says it
> does.** `_update_trouble_rooms_log` returns before writing on `READ_UNREADABLE`, and it is the
> only writer, so no successful write is reachable. Nothing else repairs it: the accumulator
> rebuild deliberately excludes trouble-rooms, and nothing anywhere deletes or recreates the
> file. The user sees the friendliest possible failure — every room reads as having no chronic
> misses, which is indistinguishable from a healthy house. The only signal is one warning per
> finalization.
>
> This is a known, accepted trade: refusing protects real history, and the alternative destroyed
> it. But *"retries on the next finalize"* is false and should not be believed.

**A cancelled run is skipped entirely by the trouble-rooms counter** — neither a miss nor a
success, while interrupted and failed still count. Counting cancels inverted the badge's meaning:
a day of cancel-testing flagged two rooms as chronic trouble with nothing having gone wrong. A
user cancel is not evidence in either direction.

**"Which rooms of this job are done" has exactly one answer** —
`learning/utils.py::known_completed_room_ids` (`INQ619A6`), biased toward *missed*. Separate ladders in the archived record and the
incomplete-run log once disagreed about the same job.

**A normal completion clears the incomplete-run log only when this run's queue overlaps the
logged missed rooms and the map matches.** Clearing on any completion — the prior rule, whose
docstring claimed a fullness it never checked — let a one-room clean silently erase a log about a
different run's stranded rooms, leaving `retry_missed_rooms` nothing to retry.

**The box-level learning toggle gates the stats rebuild only.** Collection always happens and the
run is marked pending, so turning the toggle back on runs a catch-up. Skipping collection would
have discarded those runs irrecoverably.

---

## 8. Common wrong assumptions

| assumption | actually |
|---|---|
| `clear_active_job` is a lightweight cancel | it does **not** end the run |
| a finalized job's `status` says how it ended | `mark_active_job_finalized` sets `status = "completed"` unconditionally — including on the cancel path, and even when finalize raised. The outcome is elsewhere on the record |
| any path that finalizes a run also ends it | the `finalize_learning_job` service writes the record and fires the event without calling `mark_active_job_finalized` |
| a finalize result that is not `None` means it ran | a refusal dict is not `None`. Use `finalize_result_succeeded` |
| `_phase_dispatch_pending` means one thing to everything reading it | it is a veto to one gate and a lease to another |
| `has_observed_active_lifecycle == False` is safe — an unarmed run just won't auto-finalize | it changes which reaper can rescue the run |
| `EVENT_JOB_FINISHED` has one payload shape | three builders exist, and the third is not equivalent to the other two |
| `manager.learning` is the learning manager | core never assigns it. `manager.learning_processing_enabled` and `manager.external_run` both exist, which makes the mistake easy |
| the learning system is optional, so it can be turned off | eight docstrings say "optional"; there is no config flag and it is constructed unconditionally |
| the cancel-detection heuristic is a general safety net | it is narrow by construction — see §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) — `IN` rules and their consequences.
[00c-replicas.md](00c-replicas.md) — `RN` sets, where one rule has more than one copy.
