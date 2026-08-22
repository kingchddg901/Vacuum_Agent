# 05 — While a Run Is Live

**Scope.** From "the user may start" to the moment a run ends: queue derivation, the refusal
ladder, dispatch, room advance, and the observers that run while the robot works. How a run ends
is [06 — How a Run Ends](06-run-end.md).

Nothing here decides a run's fate. Every value in this half is derived, observed or reported;
the authorities that can end a run all live in 06. That separation is enforced, not conventional
— the progress snapshot is a pure read by default, and the four mid-run observers write records
that only finalization consumes.

---

## 1. There are two queues

`data["queue"]` is a derived display and learning snapshot, maintained by `build_queue` and
`_refresh_room_derived_state`. **The start path never reads it.**

Every call to `get_start_status` re-derives a fresh plan from the live `enabled` flags on the map
(`planning/run_plan.py::RunPlanManager._build_effective_start_plan` →
`build_queue_from_managed_rooms`). Switching the start path to the stored snapshot would make
`start_selected_rooms` dispatch a stale room set.

This has a consequence that looks like a bug and is not. `start_selected_rooms`' last act is
`_clear_room_selections_after_start`, which turns every room off. So from the instant a run
begins the re-derived queue is **empty**, and the refusal ladder answers `no_rooms_selected`
from above every lifecycle branch. `active_job_running` is reachable from `get_start_status`
only if the user re-enables rooms mid-run.

## 2. The refusal ladder, and why its order is not the fix

`jobs/job_monitor.py::build_start_blocker_from_lifecycle` checks queue readiness — nothing
selected, wrong map, nothing to clean — **above** every lifecycle branch. During a run the user
therefore sees "select at least one room", not "a job is running."

Two ways to correct that were tried, and the shipped answer is neither:

- **Whitelisting the ladder's reason strings** as an in-flight test. This is what shipped first,
  and it meant a zone clean could stack a second dispatch on a moving robot: during a run the
  ladder returns `no_rooms_selected`, so a guard matching `active_job_running` never fires.
- **Reordering the ladder** so lifecycle speaks first. Worse in the other direction — during a
  mid-run `dock_drying` window the reordered ladder returns `blocked: False`, and Start reads as
  permitted mid-run.

The fix was a second function. `core/manager.py::EufyVacuumManager.get_job_inflight_state`
answers "is a job happening?" as a control signal; `get_start_status` answers "may the user
start?" as a sentence for a human. Its docstring states the rule outright: *reordering that
ladder is NOT the fix.* The pinning test asserts both that the new signal sees the started job
**and** that `start_status["reason"] != "active_job_running"` — deliberately, so nobody restores
the string match.

**Ask a question; do not parse a sentence written for a human.**

Two orderings inside the ladder are load-bearing:

`all_selected_rooms_blocked` is checked **above** the lifecycle call. Blocked rooms are rewritten
`enabled: False` in the effective plan, so the derived queue is empty when every selection is
blocked. Below the ladder, a user whose rooms were blocked by a window sensor is told to select a
room they already selected.

`build_start_blocker_from_lifecycle` **re-checks the map mismatch itself**, even though
`evaluate_job_lifecycle` already returns a `map_mismatch` state from the same two inputs. It
looks like duplication. It is not: the function has no branch for that lifecycle state, so
deleting the "redundant" check makes a map mismatch fall through to `blocked: False` and Start
dispatches against the wrong map.

**"Is there anything to clean?" counts clean phases across the whole plan**, not phase 0's room
count. A zone phase carries `room_count: 0` by construction, so any plan whose first surviving
phase is a zone was refused as an invalid payload while being perfectly runnable — reachable with
no user action, because a `room_group` whose rooms are all blocked is skipped during phase build.

---

## 3. Room advance is a brand-conditional choice, made once per tick

There is no single rollover mechanism. `ActiveJobTracker._maybe_roll_current_room_by_timing`
picks one per tick:

| brand declares | path |
|---|---|
| `live_transition.native_transition_source` (Roborock) | follows the device's own live current-room name entity, and takes no other path |
| default `False` (Eufy) | infers boundaries from the cleaning counters (`counter_plateau`), falling back to learned timing (`timing_rollover`) |

Two facts govern nearly every question in this area.

**"Elapsed" is not wall time.** Pause and docked/returning spans are subtracted by an
accumulator. A room that sat through a mid-run recharge is not overdue because of it.

**A phased run's clean phase is a fresh atomic sub-job.** Its rooms must still advance *inside*
it — which is why the phases guard sits where it does.

### The phases guard

`if active_job.get("phases"): return active_job` sits **inside the native-signal branch**, not at
the top of the function. It therefore suppresses rollover only for a phased job on a brand
declaring `native_transition_source` — Roborock. Eufy never reaches it.

It was at the top originally. Moving it back stops rooms advancing inside an Eufy `room_group`
phase: the Eufy room-clean engine ignores `strict_order`, so one phase holds N rooms in **one**
dispatch, and the queue freezes on room 1 for the phase's whole duration. A four-room group
records zero completed rooms until the phase ends. Nothing errors; the card simply never strikes
rooms out.

The defect the guard was written for is structurally unreachable on the other paths, which is why
it cannot be generalised: the phantom completion it prevents requires the native branch — a dock
sitting inside a target room, the native signal naming that room while parked. Counter-plateau
needs counter samples a parked robot never produces; timing rollover needs minutes of elapsed
against a sub-minute misread.

`advance_active_job_phase` resets `_native_current_room_id` alongside `current_room_id` at every
phase boundary. Today that is defence in depth — the phases guard means the native branch never
runs on a phased job — but without it the next native tick could re-complete the previous phase's
room into a freshly emptied `completed_room_ids`.

---

## 4. Two stuck detectors, kept apart on purpose

Both fire `EVENT_STALL_DETECTED`, distinguished only by a `trigger` key. Confusing them is the
most common error in this area.

| | TIMING detector | AREA / ERROR detector |
|---|---|---|
| lives in | `ActiveJobTracker.detect_run_anomalies` | `EufyVacuumManager.apply_stuck_watch_tick` over `jobs/stuck_watch.py` |
| gated on | `current_room_overdue` | neither `current_room_overdue` nor `honors_clean_order` |
| also produces | `running_long`, `skipped_room_ids` | nothing |
| reaches the card | yes — it is the only one in the snapshot | no. It puts an event on the bus and nothing else |

**`current_room_overdue` gates the timing detector only.** The `honors_clean_order` hard-zero
that used to sit at the end of its derivation was deleted. There had been two coupled gates — one
visible inside `detect_run_anomalies`, one hidden in the composer — and restoring either loses
Roborock timing-stall detection entirely, since Roborock declares `honors_clean_order: False`,
while the code still reads as though the detector works.

**The skipped-room branch keeps its `honors_clean_order` gate**, deliberately asymmetric with
stall. Ungate it and a path-optimising robot that starts at queue position 3 instantly reports
positions 0 and 1 as skipped: struck out in the card, dropped from `remaining_room_ids`.

### The area gate

Two triggers ship because each is blind where the other sees. A pose-delta detector and a
robot-state detector were both tested against hardware and **both call the corner-trap case
healthy** — the robot was moving the whole time.

- Drop the **area gate** and you miss every trap the robot never reports: swept area rising to
  0.6 m² in fifteen seconds, then flat, no error code.
- Drop the **error edge** and you wait the full window on a robot that announced its own fault.

**The window measures a high-water mark minus its baseline, not a sum of positive deltas.** At a
~15-second cadence a 15-minute window is ~60 samples, and dither on a *motionless* robot sums to
more than the progress bar — a delta sum silently disables the gate on exactly the case it exists
for.

**Leaving an exclusion rebases the window rather than un-muting it.** Suppress-only fires on the
first unmuted tick after every mid-run recharge: the robot docks, sits through a recharge
(a measured deep recharge ran 88 minutes), the mute lifts, and the baseline is over an hour
stale.

**The 15-minute window is constrained from both sides.** It must stay longer than the stranded
reaper's grace or the two fight over the same run.

**Neither trigger commands the robot.** A homing command is theatre on a robot that cannot obey
it — for a bumper fault the firmware will not release until the bumper is physically actuated —
and it would redirect app-started runs the integration does not own.

`_stuck_watch_excluded` refuses, by name, any exclusion requiring the pose to be still. **A
critique that only adds mutes is how you ship a detector that never fires.**

### The snapshot is a pure read

Room rollover, the one-shot event fires and the per-room dedup persistence are all gated behind
`apply_side_effects=True`, which only the 5-second ticker passes. Without that, the one-shot
contract is keyed to card-poll frequency, and a dashboard being open changes when rooms advance.

---

## 5. Four observers, three questions, no authority

Four observers run inside one synchronous block of the lifecycle listener and write into the same
active-job record. **None of them decides anything about the run**, and the completion gate reads
none of them — it is suppressed during a recharge dock by a separate signal.

**The recharge pair is a two-phase state machine split across ticks on purpose** — armed on the
dock, counted on the resume. "Docked and charging" cannot distinguish a mid-run recharge from the
end of the job, so counting on the dock would count every ending run as a recharge.

**The mop-wash observer is a debounced counter whose vocabulary is adapter-declared with no brand
fallback.** A brand that declares nothing observes nothing, rather than inheriting another
brand's words.

**State-transition and sensor-value recording exist to make finalization independent of live HA
reads.** The transitions are the segmenter's only window into a gap the counters cannot see; the
pushed sensor values dodge a packet-ordering race at job end, where a live read can return the
next run's zeroes.

---

## 6. Common wrong assumptions

| assumption | actually |
|---|---|
| `stall_detected` in the snapshot is the integration's stuck signal | it is one of two, and the other never reaches the snapshot |
| the two stuck triggers behave alike | different status filters, dedup and cadence |
| `running_long` is the band below stall, so it is scoped the same way | stall was un-gated from `honors_clean_order`; the others were not |
| the stuck-watch tunables are adapter-declarable extension points, as their docstrings say | the seam exists; **no shipped adapter declares them** |
| `data["queue"]` is what the start path dispatches | it is a display and learning snapshot; the plan is re-derived per call |
| a card poll advances the room | rollover requires `apply_side_effects=True`, passed only by the 5-second ticker |
| the map-mismatch re-check in the ladder is redundant | the lifecycle branch for it does not exist |
| `dev_inject_stall` makes the run report as anomalous | its docstring and `services.yaml` say so; it does not |

---

## Registries

[00b-invariants.md](00b-invariants.md) — `IN` rules and their consequences.
[00c-replicas.md](00c-replicas.md) — `RN` sets, where one rule has more than one copy.
