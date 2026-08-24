# 42 — The Send Side

**Scope.** The last mile: turning a resolved payload into the adapter's wire envelope and pushing
it, the settings that must be pushed globally before an atomic dispatch, and the step vocabularies
that decide what a run's shape is. What produced the payload is
[05 — A Run, Live](05-run-live.md); what the brands declare is [23](23-eufy-adapter.md) and
[24](24-roborock-adapter.md).

Two failures documented here have the same shape and opposite fixes: one guard was inert because
nothing it wrapped could fail, and one duplication is correct because merging it would break a
feature. Both are worth reading past their own subsystem.

---

## 1. Room ids are re-resolved at the last possible moment

`dispatch/manager.py::_resolve_live_dispatch_payload` re-fetches the room source immediately before
dispatch, maps each target room's slug to its **current** id, and rewrites the wire id list.

It exists for brands whose segment ids renumber on a re-segment. A stored id that was correct when
the queue was built can address a different physical room after a map edit — so the stored id is
kept as identity and the wire id is derived fresh. **The room the user picked is named by slug; the
number is a detail resolved at send time.**

The stored payload is deliberately *not* rewritten. Identity stays slug-tagged in the record, so
rollover matches by name and completion keys off the job-active signal, neither of which needs the
live id ([23 §1](23-eufy-adapter.md)).

---

## 2. Some settings can only be pushed globally, and ordering matters

`dispatch/manager.py::_run_global_pre_calls` pushes fan and mop settings for brands that expose
them only as device-wide selects rather than per-room fields. Values are combined across the batch
by rank — the strongest wins — and a room whose value is not in the declared rank is ignored.

⚠ **The pre-calls run *after* live-id resolution, immediately before dispatch, and that ordering is
a fix.** Resolution can raise — it does when a map has been re-segmented and stored slugs no longer
resolve. Running pre-calls first meant the device's global settings were changed for a dispatch
that then failed, leaving the vacuum reconfigured with no clean to show for it.

The rule generalises: **push device state only after everything that can refuse has refused.**

---

## 3. A mixed batch takes the safest water, not the strongest

A device-global water select cannot be zeroed per room. So a batch containing both mop rooms and
vacuum-only rooms, combined by the usual strongest-wins rule, would **wet-mop the dry rooms**.

For an entry that opts in, a mixed batch flips to the **lowest** rank instead. The trade is stated
plainly: *under-mop is accepted over wet-mop.* A single-mode batch — all mop or all vacuum — keeps
strongest-wins, and the suction entry never carries the marker, so fan speed is unaffected.

One detail makes the difference between working and not: the rule targets the rank's **lowest
value directly**, rather than the minimum of the water levels the rooms declared. A vacuum-only
room carries no water level at all, so a minimum over declared values would never see it and never
lower anything. **The presence of a dry room is the signal — not its value.**

---

## 4. The safety abort that could never fire

This is the sharpest defect in the subsystem, and nothing about the code looked wrong.

The safest-water push was wrapped in `except Exception` with an abort, so a failure to apply it
would refuse the dispatch rather than wet-mop. But **Home Assistant does not raise when a service
call names an entity that does not exist.** It collects the missing ids and logs a warning.

So on an install where the target select resolved to nothing:

1. the call no-opped,
2. the `except` never ran,
3. the safety abort never happened, and
4. the run proceeded with whatever water the vendor app had last set —

the exact wet-mop the guard exists to prevent, **with no error anywhere.**

The fix is to check the entity exists *first*, which turns that silence into the same refusal a
genuine failure gets. Best-effort entries still degrade quietly, but now say so at warning level
rather than saying nothing at all.

**A guard is only as reachable as the failure it catches.** An `except` block around a call that
cannot raise is indistinguishable from a working guard by reading, by review, and by every test
that does not construct the missing-entity case.

### What "best effort" means here, precisely

The method's own summary says a failed pre-call never aborts the run, and that is true of the plain
entries — fan, and water on a single-mode batch. It is **not** true of the safest-water entry,
where both a missing target and a failed call raise and abort by design.

The two live in one loop and read alike. When quoting the best-effort line, check which entry it is
being applied to.

---

## 5. Two vocabularies that look identical and must not be merged

`step_types.py` exists because one same-looking tuple was hand-copied to **eleven call sites** and
drifted. On a single day the *same* missing `zone` entry was found and fixed twice, on opposite
sides of the stack — the backend's has-stops gate and the card's equivalent — because a
rooms-then-zone profile reported itself as a flat queue in both.

The obvious remedy is one shared set. The module says outright that this would be **worse than the
duplication it replaces**, because the two tuples answer different questions:

| set | question | contains `zone` |
|---|---|---|
| `step_types.py::STEPPED_STEP_TYPES` | does this step make the run **sequenced** rather than a flat queue | **yes** |
| `step_types.py::DOCK_POLLED_PHASE_TYPES` | is this phase driven by **polling the dock** | no |

A zone step makes a run sequenced; it is not a dock wait. Merging them either teaches the dock
poller to wait on a zone clean or tells the queue that a zone step is flat — and one of those two
breaks zone handling outright.

> Compare [37 §5](37-the-entity-surface.md), where merging six copies of a blank-state set made
> every call site **strictly stronger**. Same surface symptom — near-identical duplicated
> literals — opposite correct answer. What decides is whether the copies answer one question or
> several: unify the question, never the vocabulary.

What the module does instead of merging is name both sets, state the questions, and put them in one
file where the difference is visible — so the eleven call sites import a named answer rather than
retyping a tuple.

---

## 6. Common wrong assumptions

| assumption | reality |
|---|---|
| the wire ids are the stored ids | they are re-resolved by slug just before dispatch for brands that renumber — §1 |
| pre-calls can run any time before the send | they run after resolution, because resolution can refuse — §2 |
| a mixed batch takes the strongest setting | water takes the safest; suction still takes the strongest — §3 |
| the safe-water floor is the minimum declared level | a dry room declares none; the rule targets the rank's lowest value directly — §3 |
| a call wrapped in `except` is guarded | HA logs a missing target rather than raising, so the abort never ran — §4 |
| pre-calls never abort a run | true of the plain entries, false of the safest-water entry — §4 |
| two identical-looking tuples should be merged | these answer different questions and merging breaks zone handling — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
