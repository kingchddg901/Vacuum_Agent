# The counterfactual oracle set — 06-job-lifecycle

**RECOVERED 2026-08-22 from the 2026-08-16 subagent transcripts. It was never written
down.** The findings note narrated about five of the nine; the other four, and every
skeptic's CORRECTED answer, existed only inside agent transcripts and would have died
with them.

> That matters more than it sounds. **In this test design the answer IS the oracle**, and
> 6 of 9 as-authored answers were wrong. Re-authoring would have thrown away the whole
> verification stage — the expensive half — and graded the doc against a fresh fiction.

Recovered from `wf_692e15dd-5e1` (3 authoring agents) and `wf_bab029bd-eca` (9 skeptics),
paired by headline token overlap, 9/9 matched. **The recovered verdict split is exactly
3 CONFIRMED / 5 PARTLY_WRONG / 1 REFUTED — the same figures the findings note recorded
independently**, which is what makes the pairing trustworthy rather than plausible.

## How to use it

| verdict | oracle is | n |
|---|---|---:|
| CONFIRMED | the authored answer, unchanged | 3 |
| PARTLY_WRONG | **the skeptic's correction**, never the authored one | 5 |
| REFUTED | dropped | 1 |

**8 usable oracles.**

⚠ **The failure mode was QUANTIFIER CREEP, every time.** Mechanism right, scope wrong —
*"every run"*, *"never"*, *"silently"*, *"permanently"*. When grading, a doc answer that
gets the mechanism right and the quantifier wrong is not the same as a miss, and the
authored answers show the same inflation, which is why they cannot be the oracle.

---

## CF-1 — CONFIRMED

**Question.** A predicate decides whether a dispatched run that is still marked `started` has become 'stranded' (ended without ever reaching its brand's completion terminal) and should be reaped. Its body, in order, is roughly: bail unless status is `started`; a never-really-started run is reapable purely on age; a phase dispatch whose watchdog is still live is excluded; `if vacuum_errored: return True`; then `if job_active_on or is_mid_run_status: return False`; then require `vacuum_state in ("docked", "idle")`; then require the brand's completion secondary to be satisfied; then confirm the completion status has NOT been reached. Suppose you moved the `if vacuum_errored: return True` line down to just above the final `return True`, so the other exclusions get to speak first. What changes?

**The naive answer** (what general competence says, and it is wrong): Very little, and what does change is more conservative. Errored runs would still be reaped once they settle, but a robot that errors while it is mid-mop-wash or mid-dust-empty would now be protected by the mid-run exclusion instead of reaped immediately — which is safer, since a dock service cycle can finish and the run can resume. At worst you delay the reap of a genuinely dead run by a few polls.

**ORACLE** *(source: as-authored (CONFIRMED))*

> The clause becomes unreachable dead code and the trapped-robot strand returns permanently. To get to the bottom of the function a job must pass `not (job_active_on or is_mid_run_status)` AND `vacuum_state in ("docked", "idle")`. An errored robot fails both by construction. Its `vacuum_state` IS `error` — that is exactly the value the caller derives `vacuum_errored` from — so it is never `docked`/`idle`. And, hardware-verified 2026-08-09 on a Roborock wedged on a box throwing `bumper_stuck`, upstream keeps `binary_sensor.<vac>_cleaning` ON while the robot is errored, so `job_active_on` stays True (the caller even passes `unavailable_is_active=True`). The observed run sat `started` eight minutes past a five-minute grace with `stranded_since` never even stamped, and would have stayed that way indefinitely. The clause has to sit ABOVE the two gates it is meant to override; below them it can never fire. The 'it may recover' protection the naive answer wants is not lost by keeping the clause high — it lives in the caller instead, which stamps `stranded_since` on the first tick and only reports a reap once the ~5-minute grace has elapsed, clearing the stamp if the condition stops holding. A transient error that clears inside the window costs nothing.

---

## CF-2 — CONFIRMED

**Question.** The per-vacuum chronic-trouble-rooms store is a single small JSON file of per-room `run_count` / `miss_count`, fully rewritten after every job finalization via an atomic temp-file + `os.replace` with `fsync`. Suppose that file ends up unreadable on disk — zero bytes, or trailing garbage from an interrupted write on a network-mounted config share. The vacuum keeps running jobs normally, several per day. After how many finalizations does the store recover, and what does the user see meanwhile?

**The naive answer** (what general competence says, and it is wrong): One. It is a single-overwrite file with no incremental history to preserve, and the very next finalization rewrites it wholesale and atomically — corruption self-heals immediately. At worst the counts restart from zero for one cycle, and in the meantime the trouble-room badges are stale or absent for a few minutes.

**ORACLE** *(source: as-authored (CONFIRMED))*

> Never, by any automatic path. The only writer of that file is `_update_trouble_rooms_log`, and it opens with a tri-state read that REFUSES on `READ_UNREADABLE` and returns before writing anything — precisely so a destructive read-modify-write cannot replace years of history with one job's rooms. That guard is unconditional, so every subsequent finalization takes the same early return: the store is permanently frozen and the only writer that could heal it is downstream of the read that refuses. The code's own warning text ("will retry on the next finalize; the file self-heals on the next successful atomic write") is false — no successful write is reachable. There is no repair path elsewhere either: `async_rebuild_learning_accumulators`, the seam that repairs incremental stores a rebuild cannot, deliberately EXCLUDES trouble_rooms on the reasoning that a bad sample decays on its own; and nothing anywhere deletes or recreates the file. The user sees the friendliest possible failure — every room reads as having no chronic misses (`load_trouble_rooms` → `read_json` → None → no badges), i.e. corruption is indistinguishable from a perfectly healthy house. The only signal is one WARNING per finalization.

---

## CF-3 — PARTLY_WRONG

**Question.** The live progress snapshot computes a per-room `current_room_overdue` flag: the room did not roll on this tick AND elapsed has passed the summed learned completion threshold for the rooms in the current dispatch. Now suppose you decide that flag is meaningless on a brand whose robot re-orders the dispatched rooms — "this room is late" says nothing if the robot chose a different order — and you hard-set `current_room_overdue = False` for those brands. What else changes?

**The naive answer** (what general competence says, and it is wrong): Only the overdue signal itself, plus whatever short-interval card polling it drives. The three run anomalies are independent detectors: stall is its own elapsed-vs-~2x-estimate ratio check, running_long is its own lower band, and skipped is queue-order arithmetic. Stall would keep firing on those brands, and running_long/skipped are untouched. Worst case you lose a UI polling hint.

**ORACLE** *(source: skeptic corrected_answer)*

> Hard-setting `current_room_overdue = False` for path-optimizing brands would silently disable the TIMING-trigger stall detector on those brands: `stall_detected`, `stall_elapsed_minutes`, `stall_expected_minutes`, `stall_ratio` and the once-per-room `EVENT_STALL_DETECTED` with `trigger: "timing"` are all computed inside `if current_room_overdue and current_room_id is not None:` in `active_job.py::detect_run_anomalies` (:1101), with no log line and no exception — the card's "Robot may be stuck" banner (`src/renderers/learning.js:469`, which reads only `progress.stall_detected`) would simply never appear. Because `running_long` (:1185) and `skipped_room_ids` (:1223) are gated on the OPPOSITE sense of the same capability (`adapter_honors_clean_order`; Roborock declares False, Eufy defaults True), all three `detect_run_anomalies` outputs would be dead at once on that brand. That much is real, and the code carries a comment recording that exactly this hard-zero used to sit in the snapshot composer and was removed for exactly this reason (commit `26c4b2d7`). Where the candidate overreaches: the run would NOT be left with "no anomaly detection at all", and not "every run anomaly" would be off. `core/manager.py::apply_stuck_watch_tick` is a separate detector — error edge plus area gate — that fires the same `EVENT_STALL_DETECTED` through `_fire_stuck_event` with `trigger: "error"`/`"ar

*Superseded authored answer, kept only to show the inflation:* It silently switches OFF every run anomaly on that brand. `stall_detected` is computed only inside `if current_room_overdue and current_room_id is not None:` — the ratio check and the group-combined threshold live entirely within that branch — so hard-zeroing overdue removes the hard-stall detector and its once-per-room EVENT_STALL_DETECTED completely, with no log line, no exception and no flag; t

---

## CF-4 — PARTLY_WRONG

**Question.** A run logs two faults into its error latch, in this order: a robot fault captured at 10:00 that never records a `recovered_at` (the firmware re-fired before it cleared), then a station/dock fault captured at 10:01 that the brand adapter classifies as harmless — i.e. it does not invalidate the run's cleaning evidence and must never be subtracted from cleaning time. The run ends at 10:30 with an upstream cleaning counter of ~1500 s. Now change one thing: the adapter stops surfacing that harmless dock fault, so it never enters the latch at all. Everything else is identical. What happens to the finalized record's `cleaning_time_seconds`?

**The naive answer** (what general competence says, and it is wrong): Nothing. The deducted total is computed over invalidating faults only — the harmless dock fault is filtered out of that bucket anyway, so deleting it removes an entry that was already contributing zero. Deduction stays ~60 s and cleaning_time_seconds stays ~1440 s. If anything the record gets marginally cleaner (one fewer noise entry, `error_seconds_by_evidence.safe` drops to 0).

**ORACLE** *(source: skeptic corrected_answer)*

> The load-bearing insight is correct: in `_compute_total_error_seconds`, `keep_entry` gates whether an interval OPENS (line 153) but the implicit CLOSE boundary is searched over the unfiltered `raw_entries[index+1:]` (line 161), so an entry excluded from a bucket still terminates that bucket's open windows. Given the stipulated latch contents, the deduction does go 60 s → 1800 s, `cleaning_time_seconds` clamps to 0, and `used_for_learning` stays True — the latter because `evaluate_idle_wall_hold` exempts runs with `had_errors`, which is the only thing preventing the 30-minute idle gap from tripping the 20-minute hold floor. Three corrections. (1) The `_LOGGER.debug` is not the only signal: the record deliberately preserves `cleaning_time_seconds_raw` (1500), `total_error_seconds` (1800), `error_seconds_deducted` (1800) and `error_seconds_by_evidence`, and the comment at job_finalizer.py:995-998 states that recording both values exists precisely so the discrepancy is visible in audit. (2) The stated trigger has no code path: nothing filters the latch by error code — `_record_rising_edge` latches any error-valued observation — and the one adapter mechanism that would suppress the message (`not_error_sentinels`) instead drives `_handle_error_message_change` into `_record_falling_edge`, stamping `recovered_at` = 10:01 on the robot fault and reproducing the 60 s figure. The 1800 s ou

*Superseded authored answer, kept only to show the inflation:* The deducted seconds jump from 60 s to 1800 s and `cleaning_time_seconds` clamps to 0 — the run records as a zero-second clean, still with `used_for_learning: True`. The bucket filter (`keep_entry`) is applied when deciding whether to OPEN an interval, but the implicit CLOSE boundary for an entry with no `recovered_at` is searched over the *unfiltered* `raw_entries[index+1:]`. So the harmless dock

---

## CF-5 — CONFIRMED

**Question.** The live room-rollover routine contains a guard `if active_job.get("phases"): return active_job` — a phased (sequenced) job is excluded from live rollover. That guard currently sits inside one branch of the function rather than at the top. Suppose you hoisted it to the first line of the function, so a phased job short-circuits before any rollover path runs. What breaks, and on which brands?

**The naive answer** (what general competence says, and it is wrong): Nothing. Hoisting a guard that already excludes phased jobs to the top of the same function is a pure clarity refactor — the branch it sits in is reached from the top anyway, so the only extra effect is that the timing and counter-based rollover paths also short-circuit for phased jobs. Those paths are redundant for a sequenced job, because the phase runner dispatches one room per phase and owns room advancement itself, so suppressing them removes a source of double-counting.

**ORACLE** *(source: as-authored (CONFIRMED))*

> It silently stops rooms from advancing *inside* a phase on every brand that has no native current-room signal (Eufy and any adapter leaving `live_transition.native_transition_source` at its `False` default). The premise that a phase is one room is false for those brands: the Eufy room-clean engine ignores `strict_order`, so a `room_group` phase dispatches N rooms in ONE command, and the counter-plateau / timing-rollover paths are the only thing that advances `current_room_id`, records completed rooms, and fires the room-finished/room-started events within that group. With the guard hoisted, a 4-room group records zero completed rooms until the whole phase ends. Nothing errors; the card just never strikes rooms out. The guard cannot be generalised because the defect it was written for is structurally unreachable on the other paths: the 0.55-minute phantom completion (seen live on a Roborock S6 — the dock sits in a target room, the native signal names that room while parked, the branch adopts it as current) requires the NATIVE branch. Counter-plateau needs counter samples, which a parked robot never produces; timing rollover needs at least ~1.75 minutes elapsed (~2.75 unlearned) against a 0.55-minute misread. Hoisting it also re-creates a second, quieter casualty: the phase-scoped sample slice becomes dead code, computed for anomaly gating and never reached by the rollover it exi

---

## CF-6 — PARTLY_WRONG

**Question.** A dispatched single-room clean that the user aborts ~30 s in from the vendor app — after which the robot reports its brand's normal completion status — is caught by the finalizer's cancel-likely heuristic and archived as `cancelled`, excluded from learning. Change exactly one thing: make it a THREE-room queue, aborted the same way at the same 30 s mark, robot again reporting its completion status. What does the finalized record say, and what does it do to the per-room miss statistics?

**The naive answer** (what general competence says, and it is wrong): It is caught at least as easily — three rooms in 30 s is a far more extreme deviation from the estimate than one room in 30 s, so the heuristic fires harder. Expect `status: cancelled`, `used_for_learning: False`, and the two-or-three untouched rooms logged as missed (feeding the incomplete-run log and the chronic-trouble-room counters).

**ORACLE** *(source: skeptic corrected_answer)*

> The heuristic never runs: `learning/job_finalizer.py::_detect_cancel_likely_run` returns `{"cancel_likely": False, "reason": "not_single_room"}` on its second guard, before any transition-pattern or estimate comparison, because it bails whenever `len(resolved_rooms) != 1`. The record is written `status: completed`, `used_for_learning: True`, `sanity_passed: True` — 3 rooms clears `invalid_room_count`, 0.5 min clears `invalid_duration`, and the 20-minute idle-wall floor cannot see a 30-second run. No incomplete-run log is written (and an existing one covering these rooms is CLEARED). `_update_trouble_rooms_log` takes `active_completed = queued_room_ids[:]` on a completed outcome, so all three rooms get `run_count += 1`, `last_cleaned_at` stamped and `miss_rate` improved, and `stats_rebuilder` allocates duration_minutes/3 into each room's learned average with `learning_run_count += 1`. The record carries `cancel_detection: {cancel_likely: False, reason: not_single_room}`, which reads as "evaluated and cleared" rather than "not evaluated". Correction on mechanism: `finalize_from_inputs` does NOT overwrite `completed_room_ids` with the full queue on a real run. That branch (job_finalizer.py 898-907) sources `_queued_ids` from the LIVE `manager.get_queue_state()` read taken at finalization, and `start_selected_rooms` empties that bucket at dispatch via `_clear_room_selections_after_

*Superseded authored answer, kept only to show the inflation:* The heuristic never runs. `_detect_cancel_likely_run` returns `{"cancel_likely": False, "reason": "not_single_room"}` on its second guard — before any duration, transition-pattern or estimate comparison — because it bails whenever `len(resolved_rooms) != 1`. The record is written `status: completed`, `used_for_learning: True`, `sanity_passed: True`; the only blockers that could fire are `invalid_r

---

## CF-7 — PARTLY_WRONG

**Question.** In this integration's start-blocker builder, the refusal ladder checks, in order: no target map → map mismatch → "queue is empty" → "payload has nothing to clean" → then the vacuum-lifecycle refusals (mid-job service / a job is already running / vacuum busy). Suppose you reordered it so the lifecycle refusals were evaluated FIRST and the empty-queue check last. How often would the refusal the user actually sees change, and in which situations?

**The naive answer** (what general competence says, and it is wrong): Rarely, and only in a genuine corner case. Normally when a job is running the queue still holds that job's rooms, so the empty-queue branch is skipped and 'a job is already running' is what gets reported anyway. Reordering would only matter if the user happened to clear the queue while a run was in flight — a cosmetic difference in a rare state, and arguably the reordered version is slightly more informative.

**ORACLE** *(source: skeptic corrected_answer)*

> Correct core: yes, this changes on essentially every run rather than in a corner case. `start_selected_rooms` clears the selection after dispatch (`_clear_room_selections_after_start`, manager.py:6824), and `get_start_status` re-derives `queue_room_ids` from live `enabled` flags each call (`_build_effective_start_plan` → `build_queue_from_managed_rooms`), never from `data["queue"]`. So a `started` run reports `reason="no_rooms_selected"`, and `active_job_running` is reachable only if rooms get re-enabled mid-run — confirmed by the fact that `build_active_job_state` has exactly one call site, inside the function that clears. Two scope corrections. First, not the entire duration: a paused segment short-circuits to `job_paused` at manager.py:3664, above the ladder, so the reorder is a no-op there. (Two further early returns, `onboarding_required` and `all_selected_rooms_blocked`, also sit above the ladder but cannot fire on an empty selection.) Second, the reorder would NOT flip the refusal to `active_job_running` universally: `evaluate_job_lifecycle` treats `docked`/`idle` as non-active, so during mid-run charge/wait breaks, inter-phase docks, and the pre-motion window after dispatch on a brand whose `active_cleaning_target` is a reliable idle sentinel (Eufy — see listeners/lifecycle.py:237-250), lifecycle reads `ready` and the reordered ladder falls through to the empty-queue ch

*Superseded authored answer, kept only to show the inflation:* It would change the refusal for the entire duration of EVERY run, on every install. The start path clears the selection as its last act: after dispatch, `start_selected_rooms` calls `_clear_room_selections_after_start`, which sets `enabled: False` on every enabled room and empties `queue_breaks`. The queue that `get_start_status` reports is not the stored `data["queue"]` bucket — it is re-derived 

---

## CF-9 — PARTLY_WRONG

**Question.** The per-phase timing capture walks the device's cumulative `cleaning_time` / `cleaning_area` series and accumulates progress-since-phase-start, treating a DECREASE as a per-phase counter reset. The decrease test is not `value < prev` but `value < prev - eps`, with eps = 0.5 seconds for time and 0.01 m² for area. If you dropped those epsilons and used a plain `value < prev`, what would happen — and on which installs would it happen?

**The naive answer** (what general competence says, and it is wrong): The epsilon is a noise tolerance on a monotonic counter. Remove it and occasional tiny decreases get misclassified as resets, so the accumulator restarts early and you LOSE a small amount of measured time or area — sub-second, sub-centimetre, well under the sensor's own precision. And it only matters on installs doing unit conversion (an imperial/US Home Assistant), where an m²→ft²→m² round trip introduces float error; a metric install gets whole m² straight from the device and never sees a decrease at all.

**ORACLE** *(source: skeptic corrected_answer)*

> Dropping the epsilons would indeed fail in the INFLATING direction, not the losing one, and the trigger is per-ENTITY rather than per-install — both halves of the candidate's core answer check out verbatim against `_phase_progress_samples` (`totals[key] += max(0.0, value)` on the reset branch, floors tracking the raw reading) and `cleaning_area_to_m2` (which keys off the entity's own `unit_of_measurement`). The error is the size of the counter at the jitter, it lands on the room through `_phase_room_timing`'s `cas[-1]`/`cts[-1]`, and nothing in the phase path intercepts it — the group segmenter's Gate 3 telescopes off the same inflated series. The third clause is overstated. The inflated AREA is not unflagged: `learning/utils.py::area_sanity` — written for exactly this cause ("attributed > sensor is double-counting (e.g. a non-monotonic counter)") — is applied in `stats_rebuilder.build_jobs_index_payload` as `area_over_attributed`, and on the run-level merged record it compares the inflated attributed sum against the device's untouched `cleaning_area_sensor_m2`, so a doubling exceeds the 10% tolerance and the index row is written True. What is true is that the alarm is invisible in practice: no frontend code reads `area_over_attributed`; it is structurally dead on the per-phase child records because `phase_runner.py:738` reads the wrong key (`cleaning_area_m2` instead of `area_

*Superseded authored answer, kept only to show the inflation:* Both halves are wrong. (1) DIRECTION: the reset branch does `totals[key] += max(0.0, value)` — after a reset the raw reading IS the progress since that reset. So a decrease of 6e-15 does not drop a hundredth, it RE-ADDS the entire current cumulative reading as fresh progress. A phase sitting at 3 m² that jitters 3.0 → 2.9999999999999942 books another 3 m² on top; the room's recorded area (and by t

---

## CF-8 — REFUTED, NOT USABLE

**Question.** A phased (sequenced) run accumulates cleaning-counter samples into one buffer for the whole run. The live "has the robot finished another room?" detector segments that buffer into bouts and compares the number of boundaries it finds against the number of rooms already recorded complete; when boundaries > completed, it rolls the current room forward. Today that detector is fed only the slice of sam

**Why it was refuted.** The supporting facts check out, but the headline direction ("comes back TOO LOW", "the rollover never fires at all") is provably backwards for the function under discussion. VERIFIED PREMISES - `jobs/active_job.py::_live_boundary_count` (line 1316) does feed `self._current_phase_samples(active_job)`, not `active_job["counter_samples"]`; the counter_plateau branch is `if self._live_boundary_count(...) > len(completed_room_ids)` (line 1462) and the same count gates `_pending_transition` in `detect_run_anomalies` (lines 1205-1208). - `queue/queue_engine.py::advance_active_job_phase` line 543 does `advanced["completed_room_ids"] = []` and never touches `counter_samples` (`advanced = dict(active_job)` shares the same list). The two-different-clocks fact is real. - `jobs/phase_runner.py` line 887 does say the whole-run stream "can't be segmented across the per-room dock trips (the segmenter's 
