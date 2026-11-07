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

### A re-send is suppressed only when we made it redundant ourselves

The method runs **twice over a phased job** — once at job start, once per phase — so a
strict-order run pushed an identical value at every room start. A robot that acknowledges the
write chimes each time, which is how it was reported (#78/#79).

What suppresses the re-send is **our own earlier push, not the reported state**, and that
difference is the design:

| | per-room suction skip | global pre-call skip |
|---|---|---|
| the question | does the target report this value? | did *we* put it there, this job? |
| the evidence | the entity's reported value | a blocking push of ours that did not raise |
| cost of being wrong | a redundant call | a wet mop on a dry floor |

The reported value cannot carry the second cost. Home Assistant's Roborock mop-intensity select
registers no push listener — unlike its vacuum — so its state moves only on a coordinator poll
(15–60s, and longer while a failing refresh is being suppressed, during which it still reports as
available). `off` is also the *modal* reading, precisely because this code puts it there. A
vendor-app change inside that window therefore reads as agreement, and suppressing on it would
withhold the one call protecting the dry floor — reproducing §4's incident exactly.

Three things to know before changing it:

- **The first push of every job is unconditional**, including when the device already reports the
  value. That is the chime a non-phased run still produces, and it stays: it is the one push whose
  redundancy cannot be established without trusting a reading that may be stale.
- **A disagreeing reading vetoes the skip**, so an external change the poll has since caught
  re-arms the push. An *absent* reading — missing entity, `unavailable`, `unknown`, blank — is no
  information: it cannot veto, and on its own it never creates a skip.
- **The skip sits after the missing/disabled refusal, deliberately.** A skip is not a failure and
  must never abort; placed earlier it would re-open §4's silence.

Two details that look cosmetic and are not. The comparison is **case-normalised on both sides**:
`rank` is lowercased when it is read while a select keeps its own option case, so a bare `==`
would be live on a lowercase-option device and dead on a capitalised one. And where the value is
read from follows the **service domain** — a select's value is its state, a vacuum's fan speed is
an attribute — because a select publishes no `option` attribute at all, so the per-room helper's
read, copied verbatim, would produce a guard that cannot fire. Both are pinned by tests that go
red under the opposite choice (`[GPC-19]`, `[GPC-22a/b]`).

The log is two-sided from here on: a skip logs and a send logs. One-sided, an empty debug log read
identically for "nothing happened" and "everything sent", which is what made the first report of
this hard to diagnose.

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

### The same guard, missed a second time: the zone restore

`_dispatch_zone_with_global_precall` flips a gate switch OFF so the device's globals become
settable, sets them, and restores the prior values at zone completion. The forward path is safe
because it **reads back** and refuses on a mismatch. The restore path had no read-back and two
`except Exception` handlers wrapped directly around `hass.services.async_call` -- so on an install
whose entities have been renamed or re-imported, the restore no-opped, nothing raised, and the
user's prior settings were dropped with no error. The gate half is worse: the globals stay
**un-regated** until someone flips the switch by hand, and nothing says so.

That is §4's defect exactly, found a second time in the same file, and found by following an
*uncovered log line* -- the only statement in each handler, which is what made the handlers
visible at all. Both now check the target exists first and warn, naming the entity and the
consequence. They stay best-effort: a missing target is reported and skipped, never raised,
because losing the restore must not also lose the run.

Covered by `[ZC-DR-7]` and `[ZC-DR-8]`, each red when its guard is removed.

**And the apply itself had never run.** `ZC-DR-7`/`8` prove a *vanished* target is reported;
`ZC-DR-6` proves the gate goes back. None of them reached the line that actually hands the
user's setting back, because it sits behind `if p.get("prior") is not None` and the three
existing cases miss it from both sides — `ZC-DR-6` snapshots no prior for the select, and
`ZC-DR-7` sets one and then *removes the entity*, so the vanished-guard fires first. The
ordinary case, a prior that still exists, was the gap. `[ZC-DR-9]`–`[ZC-DR-12]` close it:

- `ZC-DR-9` — a surviving prior **is** re-applied, and the *last* write is the prior rather
  than the zone's value. This is the whole point of the restore: a zone clean writes the
  device's **global** suction, so without it the device keeps the zone's value and every later
  room clean runs at it. The gate being back ON with the wrong suction behind it is still the
  user's setting lost.
- `ZC-DR-10` — a re-apply that *raises* is warned and the rest of the restore still runs. The
  restore fires from a state-change callback, so an escaping exception is invisible to the
  caller **and** able to abandon the gate, which is the un-regated failure above.
- `ZC-DR-11` — a gate re-enable that raises is warned. `ZC-DR-8` covers a gate that has
  vanished (HA warns rather than raising); this is the service that exists and fails, the only
  route to that `except`.
- `ZC-DR-12` — a non-`ValueError` during the bulk set restores the priors **and** re-raises,
  and asserts the zone service was never called. The readback-mismatch path already restores
  before raising its own `ValueError`; this is the other arm, and the robot must not be sent
  when the settings did not take.

Ablated five ways. Removing the `_apply` inside `_restore` reddens all four — stated up front,
because that line is what every one of them is ultimately about, so a test staying green under
it would be the suspicious result. The four narrow arms each redden exactly one.

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
| the zone restore puts the device back | only if the entities still exist; a missing one was silent until it was made to warn — §4 |
| pre-calls never abort a run | true of the plain entries, false of the safest-water entry — §4 |
| a value the device already reports is not re-sent | only when *we* sent it this job; a reported value alone never suppresses the push — §2 |
| two identical-looking tuples should be merged | these answer different questions and merging breaks zone handling — §5 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
