# 14 — Live Room Tracking

**Scope.** The per-integration singleton that subscribes to the robot's raw X/Y position sensors
and does two unrelated things with the stream, selected by whether a job is held: during a job,
a dwell-and-movement debounce that decides when to publish room-completed; outside one, a
passive drift log of docked positions.

⚠ **It no longer asks position where the robot is.** Room identity comes entirely from the
device's own current-room signal. The coordinates survive only as a movement delta — a clock,
not a locator. Reading this module as a positioning system will mislead you about all of it.

---

## 1. Identity from the device, movement from position

Room identity is resolved from the brand's declared current-room entity and matched to a job
room by slug. The rejected design tested live coordinates against each room's learned bounding
box, accumulated across sessions.

What remains is a **debounce over someone else's answer.** The confidence machine consumes
coordinates for a Euclidean delta and nothing else — which is why it is unaffected by axis
direction, and why the absence of a scale conversion is not a defect.

> ⚠ **`MOVEMENT_DELTA_THRESHOLD` is a bare count of vacuum units with no scale anywhere in this
> unit, and that is correct** — a relative gate needs no absolute scale. But the tree's only
> mm-per-unit statement is **Roborock's**, and a reader who generalises it will believe this
> threshold means a specific distance on Eufy. It does not. (Recorded in
> `.claude/notes/SALVAGE-observations-for-code.md`.)

### A hold is not an exit, and the return sits above the update

An unresolvable signal — blank, sentinel, or matching no job room — is a **hold**: the room id is
retained for display continuity, and the handler returns *before* the confidence update, so
neither dwell nor movement is credited.

**The position of that return is the entire fix.** Move it below the update and a long hold
alone drives confidence to the firing threshold with no observation behind it — a robot parked
in an unresolvable state reports the room complete.

The earlier shape treated a blank signal as a room exit, which fired completion every time the
signal flickered.

**Rooms flagged as transitions are skipped by the resolver**, so crossing a hallway yields a hold
rather than a room switch. This is the only place in the backend where that flag changes
behaviour.

---

## 2. Two consumers, one flag, neither of them local

`_active_job` is the mode switch, and this unit is its **only** writer — `start_job` assigns it,
`end_job` and `unregister_vacuum` pop it, and nothing outside `tracker.py` touches it. What lives
elsewhere is the decision to flip it: `start_job` and `end_job` are *called* from the lifecycle
listener and `jobs/active_job.py::mark_active_job_finalized`.

That placement is the same decision recorded in [06 — How a Run Ends](06-run-end.md): the
release lives at the terminal chokepoint every path reaches, not in the happy path's `finally`,
which cancel and strand never traverse. **`end_job` flushes the currently-held room as completed
before clearing state — but only if its confidence already cleared the fire threshold.** A job
ended below it clears silently, emitting nothing. Either way the hold is released, which is the
point: a cancelled job used to leave the tracker holding a dead job, and the next run began
carrying the previous run's confidence.

`start_job` runs synchronously on the loop. The executor hop that preceded it was justified by a
comment naming two disk-I/O functions that no longer exist anywhere in the tree.

---

## 3. The drift log

Outside a job, docked positions are appended to a per-vacuum JSONL file. Three properties are
load-bearing:

**The baseline is committed only after the append succeeds.** A failed write leaves the baseline
stale, so the same position is re-detected as drift on the next reading rather than vanishing.

**A lock serialises the read-modify-write across executor threads.** The input that made it red
is on record: a CI run saw one record where two were expected, from two docked readings
scheduled back to back.

**Blank-state sentinels are derived from the shared set, not re-listed.** The old local copy
carried `"null"` but not `"None"` — so a backend that stringified a Python `None` would have
been accepted as a room name.

Room matching uses the same slug transform that room admission uses to derive identity. The
previous local normaliser was *coarser*, folding characters that admission deliberately keeps
distinct, so two separate rooms could both match one live signal.

---

## 4. Common wrong assumptions

| assumption | actually |
|---|---|
| the tracker runs on both brands | `register_vacuum` is never called for Roborock — its entity map declares no raw position sensors |
| `CONFIDENCE_THRESHOLD = 0.85` means 85% sure | it is a product of two saturating factors — a conjunctive gate near both ceilings, not a probability |
| a hold cannot inflate the room's recorded dwell | not during the hold; the hold's wall clock is credited in full the moment it ends |
| the dock-drift log records drift whenever the robot sits on the dock | it is the `else` of "is a job held" — a mid-run recharge dock logs nothing |
| the capability lookup is a cheap read-only call, safe on a per-event path | it is, in the steady state — but it escalates to full detection *and* a write in three cases: no stored snapshot, an empty `detected_model`, or an adapter `model_family` mismatch |
| the module has something to do with boundaries — the docstring says it feeds boundary traces | residue; that subsystem was deleted |
| room-completed drives something | nothing in Python subscribes to it; its only live consumer is the card |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
