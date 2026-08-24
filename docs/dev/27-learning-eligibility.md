# 27 — What Counts As Learnable

**Scope.** How a finished run is judged before anything learns from it: the two vocabularies that
record the verdict, the three places that can veto, and the two side-logs written on the way past.
Where the record lives is [26](26-learning-record-store.md); what the surviving records become is
[28](28-learning-statistics.md). Error-second arithmetic belongs to
[06 — How a Run Ends §6](06-run-end.md) and is not repeated here.

Every rule below exists because the opposite shipped first. Read the alternatives as history, not
as hypotheticals.

---

## 1. Two vocabularies, and they answer different questions

The record's `outcome` block carries both, and conflating them loses information:

| field | asks | membership |
|---|---|---|
| `sanity_flags` | is this record **coherent** | two values: an impossible room count, an impossible duration |
| `learning_blockers` | should we **learn** from it | the two above, plus missing resolved rooms, cancelled, failed, interrupted, test, a detected cancel, an idle-wall hold, and manual exclusion |

Sanity is a strict subset. A cancelled run is a perfectly coherent record that must not train
anything; an impossible duration is both. `sanity_passed` is therefore not the inverse of
`used_for_learning`, and a reader who treats one as the other will mark good records bad.

**A blocker is a reason, not just a veto.** The record keeps the specific list, so the review tab
can say *why* a run was skipped rather than only that it was. That is the whole reason for a list
rather than a boolean.

---

## 2. Three places can veto, in order

`learning/history_store.py::build_completed_job_payload` computes the base verdict from the
record's own coherence and the run's terminal status. That is the only one that runs inside the
record builder. Two more run in the finalizer and reach back into the finished outcome:

1. **Cancel detection** — `learning/job_finalizer.py::_detect_cancel_likely_run` decides whether a
   very short return path *looks* like a manual stop even when nothing declared one. Its verdict is
   injected through the payload's extra-outcome channel.
2. **The idle-wall hold** — `learning/job_finalizer.py::_apply_idle_wall_hold` mutates the finished
   record in place afterwards.

⚠ **Ordering carries the behaviour here, and the code says so.** The outcome dict snapshots
`learning_blockers` before the cancel reason is appended, so both later vetoes must **re-publish**
the canonical list. Without that, a heuristically-detected cancel persists as
`used_for_learning: False` with an *empty* blockers list, and the reason survives only in the
cancel-detection sub-dict — a run marked unlearnable for no stated reason. Both later vetoes write
the list the same way, deliberately.

---

## 3. The cancel gate was scoped to the narrow case and missed the wide one

`learning/job_finalizer.py::_detect_cancel_likely_run` used to bail immediately on anything that
was not a single-room run. The reasoning was sound as far as it went — only the estimate comparison
is genuinely single-room, because it reads the first room's timeline entry and compares the whole
run against that one room's expected minutes, which means nothing for a multi-room queue.

The consequence of putting that gate at the top was that **a multi-room queue aborted from the
vendor app was never examined at all.** It archived as `completed` with `used_for_learning: True`,
and the trouble-rooms log then credited every queued room with a fresh clean.

> The more rooms the user aborted, the more confidently the system recorded them as cleaned.

The fix was not a new check but a **move**: the room-count gate now sits directly above the
estimate comparison it actually protects, so the absolute-floor test — which needs no estimate —
runs for every run regardless of room count.

This is the general shape worth carrying: the guard existed, was correct, and was scoped to the
case that mattered least. A guard that is present reads as complete.

---

## 4. Held is not excluded

`learning/job_finalizer.py::_apply_idle_wall_hold` catches an otherwise-eligible run that spent an
extreme, unexplained stretch off the dock — wall-clock far exceeding active cleaning, with no
charge or wait phase and no error to account for it. `learning/utils.py::evaluate_idle_wall_hold`
owns the decision.

Two properties are deliberate:

- **It holds rather than excludes.** The run keeps a blocker and loses `used_for_learning`, but
  stays visible and restorable in the review tab. The system is saying *this looks wrong, you
  decide* — not deleting the evidence.
- **It reads the device's cleaning counter, never the state-transition wall slice.** A stuck run's
  transition slice can be nearly full while the robot did almost nothing, which would mask exactly
  the case this exists to catch. Measuring the wrong quantity here does not weaken the guard, it
  inverts it.

The name is precise: the hold stops a run from **defining a room baseline**. It is a cold-start
guard, and its damage model is that one absurd run becomes the reference every later run is
compared against.

---

## 5. A user cancel is not evidence about a room

`learning/job_finalizer.py::_update_trouble_rooms_log` counts how often each room is missed across
runs and flags the chronic ones for the card. Cancelled runs are **skipped entirely**.

Counting them inverted the badge's meaning: a day of cancel-testing flagged two rooms as chronic
trouble rooms when nothing had ever gone wrong in either. Both were simply rooms the run had not
reached yet when it was stopped.

The subtler half is why they are not counted as successes either. A cancelled run is not evidence
in **either** direction, so it must not move the ratio at all — recording it as a clean would be
the same error with the opposite sign. Interrupted and failed runs still count, because there the
robot genuinely did fail to finish.

`learning/job_finalizer.py::_write_incomplete_run_log` fires only for those same non-clean
outcomes, and keeps only the most recent one — it is a "what got missed last time" prompt for the
card, not a history.

⚠ Both side-logs are keyed by raw room id and scoped per vacuum. The file's own invariant block
records that their counters can therefore reattach to the wrong physical room after a re-segment or
on a second map, and that the incomplete log's missed-room ids survive both. The block marks these
closed against a repair packet while also warning that a packet id there is an attribution rather
than a verification. Treat as unverified until read.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| `sanity_passed == used_for_learning` | sanity is two flags about record coherence; blockers are eight-plus reasons about evidence quality |
| an empty `learning_blockers` means the run was learned from | only if the list was re-published after the later vetoes — §2 |
| a cancelled run is a missed room | it is not evidence in either direction and is skipped — §5 |
| the idle-wall hold deletes the run | it holds it, visible and restorable — §4 |
| eligibility is decided in the finalizer | the base verdict is decided in the record builder; the finalizer adds two later vetoes — §2 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
