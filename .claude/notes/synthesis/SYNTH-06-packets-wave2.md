# Tranche-2 Packets — Wave 2: lifecycle correctness (RP-010..RP-014)

> **⚠ REVIEW-07 AMENDMENTS APPLY ACROSS ALL TRANCHE-2 WAVE FILES** — ownership
> pins (STATE-3→RP-020, DIAG-6→RP-028, JOB-5/6→RP-032), membership adds
> (SNAP-3→RP-037, A5-PP-RP-2→RP-021a, CUSTOM-2→RP-028, IMAGE--8→RP-029,
> ACT-6→RP-031 wontfix-ack, RF-13 remainder→RP-041), the T2-D7 edge
> (RP-021b→RP-031), and T2-D8's release-note item (sequential group dispatches).
> Substantive T2-D3/D4/D5/D6 amendments are folded into their packets inline.
> Consult REVIEW-07 alongside any packet.

**Conventions for ALL tranche-2 packets** (stated once, apply everywhere):
- `target_commit`: current post-tranche-1 master (`0ee7e07` or later). **Line numbers
  are corpus-era HINTS; symbols are authoritative** — tranche 1 shifted several files
  (history_store, dispatch/manager, path_blockers, sensor/__init__, room_crud).
  Executor re-anchors by symbol before editing.
- Reproducers: main agent materializes; each proof prints `expected_before` fragments
  on current master, flips to `expected_after` when repaired, exits 1 on any
  UNEXPECTED SHAPE. Invocation: docker test image with `-e PYTHONPATH=/workspace`.
- `superseded_tests`: where a packet changes an ASSERTED contract, the named tests are
  updated WITH the decision recorded in the docstring (distinct from
  fixture-asserting-fiction: fix fixture, never weaken assertion).
- Full gate per packet: `pytest tests --no-cov -p no:cacheprovider`; frontend gates
  when src/ touched (`npm run test:units`, `check:i18n`, `build:deploy`).
- escalation_target: main agent → Chris. Do not close ledger findings.
- Sequencing (REVIEW-03): RP-010 → RP-011 → RP-012 (shared files);
  RP-013a → RP-013c → {RP-013b, RP-013d, RP-013e}; RP-014 independent.

---

## RP-010 — Cancel/pause effective at the dispatch chokepoint (RF-06)

```yaml
packet_id: RP-010
family_id: RF-06
finding_ids: ["#7:DQ-ACT-2", "#9:A1-WD-1", "#9:A2-CAN-1", "#9:A2-CAN-3",
  "#9:A4-AJ-3", "#9:A2-CAN-5", "#9:A2-CAN-6", "#13:A2-JOB-2"]
files: [custom_components/eufy_vacuum/jobs/phase_runner.py,
  custom_components/eufy_vacuum/jobs/active_job.py,
  custom_components/eufy_vacuum/listeners/lifecycle.py,
  custom_components/eufy_vacuum/services/job_control.py,
  custom_components/eufy_vacuum/core/manager.py, tests/]
symbols: [_dispatch_active_phase, async_cancel_active_job, async_pause_active_job,
  maybe_advance_phase, lifecycle._process completion gate, _handle_start_zone_clean]
problem: cancel/pause set flags synchronously but _dispatch_active_phase performs 4
  sequential awaits (pre-calls, per-room settings, live resolve, wire send) without
  re-reading the job — the in-flight dispatch lands after cancel/pause; cancel clears
  _phase_dispatch_pending BEFORE return_to_base so its own dock reads as phase
  completion and the job advances mid-cancel; a second cancel in the 30s confirm
  window nulls finalize_summary; start_zone_clean bypasses every lifecycle gate.
root_cause: cancellation state is checked once per attempt at the top, never at the
  last suspension point; no cancel single-flight; the completion gate and
  maybe_advance_phase never consult _cancel_in_flight.
required_behavior: >
  (1) inside _dispatch_active_phase, IMMEDIATELY before _dispatch_clean_payload
  (after the last await), re-read the STORED job and abort (return without sending)
  when _cancel_in_flight is set OR status is not "started". This one check closes
  ACT-2/WD-1/CAN-1 and the pause window CAN-5 (pause flips status before its own
  service round-trip completes is NOT required — the status re-read at the chokepoint
  is the guard; pause needs no new flag).
  (2) async_cancel_active_job becomes single-flight: on entry, if _cancel_in_flight
  is already truthy return {"cancelled": False, "reason": "cancel_in_progress"}
  (CAN-6). The latch is CLEARED on every cancel failure/exception path
  (turn-transient-permanent hazard — REVIEW pin) and by mark_active_job_finalized.
  (3) DO NOT stop clearing _phase_dispatch_pending early (its clear order is part of
  the dock-completion design — REVIEW pin); instead the lifecycle completion gate and
  PhaseRunner.maybe_advance_phase both suppress when _cancel_in_flight is set
  (CAN-3/AJ-3): the cancel path owns finalization for a cancelling job.
  (4) _handle_start_zone_clean consults get_start_status's blocker evaluation first
  and refuses on an in-flight job (structured response per Q9:
  {"success": false, "reason": "job_in_progress"}); its documented
  no-tracking/fire-and-forget semantics otherwise unchanged (JOB-2).
allowed_changes: the four symbol groups above + tests
prohibited_changes: no redesign of the watchdog loop (RP-011's); no changes to the
  finalize claim; no reordering of the _phase_dispatch_pending clear
intentional_divergence: pause deliberately gains NO latch — the chokepoint status
  re-read covers it; recorded so a reviewer doesn't "complete the symmetry"
compatibility_constraints: cancel result shape gains reason "cancel_in_progress";
  EVENT flow for a cancelled job unchanged (single finalize via cancel path)
migration_plan: none (in-memory flags)
rollback_plan: 3 commits — (a) chokepoint re-check [phase_runner], (b) cancel
  single-flight + gate suppression [active_job + lifecycle], (c) zone-clean gate
  [job_control/core]. Groups (a) and (b) touch different files; no shared-file fumble.
reproducer_script: NEW _proof_cancel_chokepoint.py — fake manager where the live
  resolve await blocks on an event; cancel fires mid-dispatch; assert wire send count.
expected_before: ["dispatch landed after cancel", "second cancel nulled summary",
  "gate advanced during cancel window"]
expected_after: ["dispatch aborted at chokepoint", "second cancel refused:
  cancel_in_progress", "gate held during cancel"]
validity_notes: the proof must block INSIDE _dispatch_active_phase's await chain (not
  before entry) — mirrors the four-await window; a version blocking before entry
  passes pre-repair via the existing top-of-attempt check and is invalid.
tests_to_add_or_modify: chokepoint abort (cancel + pause flavours); single-flight;
  gate suppression during cancel; zone-clean refusal mid-job; cancel-failure clears
  the latch (retryable).
superseded_tests: any test asserting a second concurrent cancel proceeds, or that
  the completion gate advances during an active cancel — update with Q-register
  rationale in docstring (execution lesson 2).
broader_gates: full suite; HC-3 ride-along (Alfred cancel-during-dispatch was
  HC-2-validated for tranche 1 — REPEAT the same scenario post-RP-010, expect
  identical external behaviour with the new refusal logs).
hardware_gate: tier 2, rides the next Alfred/Ivy batch — no new baseline needed
  (tranche-1 HC captures are the before-state).
stop_conditions: [maybe_advance_phase suppression breaks the dock-phase advance for
  a NON-cancelling job in any test — stop, the gate condition is wrong;
  get_start_status refuses zone cleans when idle — stop, gate misapplied]
escalation_target: main agent → Chris
```

---

## RP-011 — Watchdog wedges resolved; the reaper reaches every dead state (RF-07)

```yaml
packet_id: RP-011
family_id: RF-07
finding_ids: ["#9:A1-WD-2", "#9:A5-STR-3", "#7:DQ-ACT-3", "#9:A1-WD-4",
  "#9:A2-CAN-4", "#9:A1-WD-5", "#9:A5-STR-4", "#9:A5-STR-1", "#9:A5-STR-2",
  "#12:A6-GUARD-4", "#9:A1-WD-3"]
files: [custom_components/eufy_vacuum/jobs/phase_runner.py,
  custom_components/eufy_vacuum/jobs/job_monitor.py,
  custom_components/eufy_vacuum/jobs/active_job.py,
  custom_components/eufy_vacuum/listeners/pause_timeout.py,
  custom_components/eufy_vacuum/core/manager.py, tests/]
symbols: [_run_advanced_phase, _await_phase_started, is_stranded_started,
  async_finalize_stranded_job, rearm_dock_phase_if_needed, _phase_timing,
  pause_timeout._handle_pause_timeout_tick]
problem: every abnormal watchdog exit leaves _phase_dispatch_pending set, which is
  ALSO an unconditional reaper exclusion — wedge and blinded recovery in one flag; a
  raising dispatch kills the task silently; restart/resume re-arm covers only dock
  phases; a dispatched-never-started run never arms has_observed_active_lifecycle so
  the NEXT run's signals finalize the stale slot; one raising finalize kills the
  whole reaper tick forever; reap ticks overlap.
root_cause: no try/finally on the attempt loop; pending has no liveness signal; the
  reaper cannot distinguish live-watchdog from dead-watchdog; per-slot isolation
  missing (the fix already applied to cancel at the active_job try/except comment was
  never mirrored).
required_behavior: >
  (1) _run_advanced_phase wraps the loop in try/except/finally: exceptions log ERROR
  with the phase context; on EVERY exit that did not confirm the start, pending is
  converted — set _phase_dispatch_pending_since (iso) and _phase_watchdog_dead=True
  on exhaustion/exception rather than clearing (the phase may still start late;
  clearing would let the completion gate advance on a half-dispatched phase).
  (2) is_stranded_started treats pending as an exclusion ONLY while the watchdog is
  live: dead-flag set, or pending_since older than (max_attempts × verify_seconds +
  60s margin computed from the resolved phase timing), makes the slot REAPABLE
  (WD-2/STR-3).
  (3) STR-4: arm a dispatch timestamp on job creation; a status="started" job with no
  observed lifecycle within 10 minutes of dispatch is reapable as
  "never_started" (constant documented operational).
  (4) STR-2: async_finalize_stranded_job's finalize await wrapped per-slot
  try/except (mirror the cancel-path fix verbatim in style); the reaper loop in
  pause_timeout isolates per (vacuum,map) and gains an in-flight guard (single
  concurrent _process; GUARD-4).
  (5) WD-4/CAN-4: restart re-arm and resume re-arm handle room_group and zone phases
  by spawning a fresh _run_advanced_phase attempt (initial=False so it dispatches);
  DOCK_POLLED re-arm unchanged.
  (6) WD-5: _phase_timing clamps merged values (poll_seconds ≥ 1.0, max_attempts ≥ 1,
  verify/settle ≥ 0) with a WARNING naming the adapter key.
  (7) STR-1: poll_stranded_started_job also consults dock_status against the
  adapter's blocked_dock_status_states (the vocabulary it fetches and discards) so a
  dock service cycle is mid-run, not interrupted.
  (8) WD-3: _await_phase_started gates has_native on live_transition.
  native_transition_source (the flag active_job.py:951 already trusts) instead of the
  always-truthy entity-id string; the coarse fallback becomes reachable for Eufy.
allowed_changes: listed symbols + tests. REBASE NOTE: async_finalize_stranded_job was
  amended by RP-002 (already-finalized marks the slot) — build on the landed version.
prohibited_changes: do not remove the pending exclusion outright; do not change the
  completion gate (RP-010 owns it); no reaper cadence change.
compatibility_constraints: "never_started"/"watchdog_dead" appear as new reap reasons
  in logs/events — additive.
migration_plan: none (new in-memory/per-record fields, absent-tolerated)
rollback_plan: 3 commits — (a) watchdog try/finally + liveness [phase_runner],
  (b) reaper arms + isolation [job_monitor/active_job/pause_timeout],
  (c) re-arm + clamps + vocabulary [phase_runner/core]. (a) and (c) share
  phase_runner.py — order (a) first, (c) rebases (execution lesson 4).
reproducer_script: NEW _proof_watchdog_wedge.py — raising dispatch; exhausted
  retries; never-started slot; assert reapability in each.
expected_before: ["wedged: pending set, reaper excluded", "reaper tick died on raise",
  "never-started slot unreapable"]
expected_after: ["dead watchdog reapable", "reaper survived raising slot",
  "never_started reaped"]
validity_notes: the never-started case must NOT arm has_observed_active_lifecycle —
  drive state via evaluate_job_lifecycle-visible entities staying docked/Standby.
tests_to_add_or_modify: per-behaviour tests (8 groups above); clamp warnings; WD-3
  fallback reachable on a no-native fixture.
superseded_tests: tests asserting pending is an unconditional strand exclusion, or
  that _phase_timing passes adapter values through unclamped — update with rationale.
broader_gates: full suite.
hardware_gate: tier 2 — rides the Wave-2 Alfred batch; the WD-3 change alters Eufy
  phase-confirm behaviour: watch one stepped run's confirm logs (HC-2b below).
stop_conditions: [the liveness margin computation cannot be derived from resolved
  phase timing at the reap site — stop, do not hardcode; any test shows the dead-flag
  reopening a HEALTHY phase to the reaper]
escalation_target: main agent → Chris
```

---

## RP-012 — Tracker lifecycle mirrors the job lifecycle (RF-31)

```yaml
packet_id: RP-012
family_id: RF-31
finding_ids: ["#11:A6-TRK-1", "#11:A6-TRK-2", "#9:A4-AJ-1", "#11:A6-TRK-3",
  "#11:A6-TRK-4", "#12:A4-POSE-1", "#12:A4-POSE-2", "#12:A4-POSE-5", "#7:DQ-PH-6"]
files: [custom_components/eufy_vacuum/mapping/tracker.py,
  custom_components/eufy_vacuum/jobs/active_job.py,
  custom_components/eufy_vacuum/listeners/pose_sampler.py,
  custom_components/eufy_vacuum/listeners/lifecycle.py,
  custom_components/eufy_vacuum/queue/queue_engine.py, tests/]
symbols: [MappingTracker.end_job, resume_sampling, _update_confidence,
  update_active_job_recharge_observation, pose_sampler.register,
  _handle_pose_tick, advance_active_job_phase]
problem: the tracker releases only on SUCCESSFUL finalize — cancel/strand leave it
  stuck on the dead job and the start gate blocks the next run's sampling; recharge
  never ends (same-tick double-check is structurally dead) so recharging runs are
  silently held from learning and sampling pauses forever; HOLD accrues dwell for a
  room the robot left, forcing confidence 1.0; the last room never fires
  room_completed; sampler cadence collapses to min() across vacuums while ticks are
  valued at each vacuum's own interval (Roborock over-weighted 2.5×); overlapping
  ticks double-record; one raising vacuum drops the rest of the tick.
root_cause: end_job called from exactly one path; recharge-end detection placed
  inside a synchronous block that re-asks an unchanged question; hold updates state
  instead of freezing it; one shared ticker at min interval.
required_behavior: >
  (1) TRK-1: mark_active_job_finalized (the terminal chokepoint every path reaches —
  cancel, strand, success) calls tracker release (executor-safe) when a tracker holds
  that vacuum's job. end_job itself: before reset, flush the currently-held room as
  room_completed IF its confidence cleared CONFIDENCE_THRESHOLD (TRK-4).
  (2) A4-AJ-1/TRK-2 (Q14 pinned): recharge-end becomes EVENT-DRIVEN — the lifecycle
  listener observes the charging→not-charging transition (via the existing watched
  entities) and calls a new explicit resume path (accumulate recharge_seconds from
  recharge_started_at, clear observed_mid_job_recharge, tracker.resume_sampling).
  The dead in-place branch is REMOVED with a comment naming why it could never fire.
  Closure per Q14: deterministic transition tests + verification that production
  listeners deliver equivalent transitions (parity check written as a test that
  drives the real listener wiring); hardware optional unless parity fails.
  (3) TRK-3: on HOLD (blank/transition/unknown room), do NOT call conf_state.update —
  freeze time_in_room accrual (hold the room id only). Confidence reflects observed
  presence, not wall time elsewhere.
  (4) POSE-1: per-vacuum cadence — keep ONE ticker at min(intervals) but sample each
  vacuum only when (now - last_sample_ts[vac]) >= its own interval_s; ticks are then
  valued correctly by the consumer's own interval.
  (5) POSE-2: per-vacuum in-flight guard (skip if previous sample still running);
  POSE-5: per-vacuum try/except in _handle_pose_tick.
  (6) DQ-PH-6: advance_active_job_phase also resets _native_current_room_id.
allowed_changes: listed symbols + tests
prohibited_changes: CF-2 preserved — pose-sampler PREDICATES untouched (no `paused`
  added to sampling); no attribution-engine math changes; no new sampling consumers.
intentional_divergence: the hold still KEEPS the room id (display continuity) — only
  accrual freezes.
compatibility_constraints: room_completed may now fire at end_job for the final room
  — consumers verified idempotent (fired_rooms set guards duplicates).
migration_plan: none
rollback_plan: 3 commits — (a) tracker release + flush [tracker/active_job],
  (b) recharge event path [lifecycle/active_job], (c) sampler cadence/isolation
  [pose_sampler] + PH-6 [queue_engine]. (a)+(b) share active_job.py — (a) first,
  (b) rebases.
reproducer_script: NEW _proof_tracker_lifecycle.py — cancel path leaves tracker
  stuck (before) / released (after); simulated charging→not-charging resumes
  sampling; hold does not accrue.
expected_before: ["tracker stuck after cancel", "recharge never ended",
  "hold accrued 300s"]
expected_after: ["tracker released on cancel", "recharge ended via transition",
  "hold accrued 0s"]
validity_notes: the recharge proof MUST drive the transition through the listener
  wiring (parity requirement Q14), not by calling the resume path directly.
tests_to_add_or_modify: release-on-every-terminal-path matrix; last-room flush;
  hold-freeze; per-vacuum cadence math; tick isolation; PH-6 reset.
superseded_tests: any test pinning end_job's single-caller assumption or the
  min()-cadence sampling of every vacuum per tick.
broader_gates: full suite.
hardware_gate: tier 2 ride-along on the Wave-2 batch (verify Ivy sampling density
  matches its declared 5s in a capture); Q14 makes the recharge run OPTIONAL.
stop_conditions: [parity test cannot drive the real listener path — STOP and report
  (Q14 says hardware becomes required); tracker release from executor context hits a
  loop-affinity error]
escalation_target: main agent → Chris
```

---

## RP-013a — Phase-type-aware capture validity (RF-11 part 1)

```yaml
packet_id: RP-013a
family_id: RF-11
finding_ids: ["#7:DQ-PH-1", "#16:A3-IO-1", "agent: infra (2-lens verified):INF-8"]
files: [custom_components/eufy_vacuum/learning/history_store.py,
  custom_components/eufy_vacuum/planning/run_plan.py,
  custom_components/eufy_vacuum/step_types.py, tests/]
symbols: [build_completed_job_payload (_every_phase_captured), run_plan._BREAKS,
  step_types (CLEANING/NON-CLEANING sets)]
problem: phase writers deliberately set room_timing=[] for break/zone phases; the
  reader treats [] as "capture failed" → transit_capture_valid=False → EVERY stepped
  run learns an even wall-time split including dock time.
root_cause: truthiness of room_timing conflates "no rooms by design" with "capture
  failed"; the phase-type vocabulary is hand-copied (INF-8).
required_behavior: >
  step_types exports the authoritative phase-type sets (extend the existing module —
  it exists for exactly this question); run_plan imports _BREAKS from it (INF-8);
  build_completed_job_payload computes validity per phase: a phase whose phase_type
  is non-cleaning (charge_wait/wait/zone) with room_timing=[] is VALID-EMPTY; a
  CLEANING phase with empty/missing room_timing is the capture failure. No stored
  record shape change (reader-side fix — schema compat by design).
allowed_changes: the three files + tests
prohibited_changes: no reset-detection logic (killed A3-REC-7 premise stays dead);
  no writer-side marker fields.
compatibility_constraints: historical records re-read under the new rule — a
  historical stepped run's transit_capture_valid recomputes TRUE on rebuild; that is
  the repair (poisoned even-splits stop being learned). Rebuild tolerance
  precondition: main agent verifies stats_rebuilder tolerates the recomputed flags
  (REVIEW-02 RF-11 precondition).
migration_plan: none; `rebuild_learning_stats` re-derives from archives.
rollback_plan: single commit.
reproducer_script: NEW _proof_phase_validity.py — stepped-run record fixture
  (charge_wait + 2 room phases with good timings): before → transit_capture_valid
  False / even split; after → True / real timings preserved.
expected_before: ["transit_capture_valid=False for stepped run", "even split"]
expected_after: ["transit_capture_valid=True", "per-room timings preserved"]
validity_notes: fixture must mirror phase_runner's REAL writer shape ([] with no
  marker) — not a synthetic marker the writer never emits.
tests_to_add_or_modify: validity matrix per phase_type; INF-8 import assertion
  (run_plan has no local _BREAKS literal).
superseded_tests: any test asserting []-means-failure for break phases.
broader_gates: full suite.
hardware_gate: >
  tier 2 — HC-2b: Alfred STEPPED run (charge_wait + 2-room group). PRECONDITION:
  verify a stepped-run BEFORE capture exists in the HC record
  (hc-results.md); if tranche-1's HC-2 batch did not include one, CAPTURE IT BEFORE
  this packet lands (the standing decaying item).
stop_conditions: [stats_rebuilder tolerance check fails]
escalation_target: main agent → Chris
```

---

## RP-013c — Job-cumulative completed evidence (RF-11 part 2; ordered before b/d/e)

```yaml
packet_id: RP-013c
family_id: RF-11
finding_ids: ["#9:A3-REC-3", "#7:DQ-PH-2", "#9:A2-CAN-2", "#16:A4-STATE-1",
  "#16:A4-STATE-2"]
files: [custom_components/eufy_vacuum/queue/queue_engine.py,
  custom_components/eufy_vacuum/jobs/active_job.py,
  custom_components/eufy_vacuum/learning/job_finalizer.py,
  custom_components/eufy_vacuum/learning/history_store.py, tests/]
symbols: [advance_active_job_phase, record_completed_room, _write_incomplete_run_log,
  clear_incomplete_run, build_completed_job_payload]
problem: completed_room_ids resets per phase and nothing refills it for phased jobs —
  cancel/strand reports wrong missed rooms; the final room of every non-completed run
  is "missed" by construction (retry automation loops); ANY completion erases an
  unrelated run's missed-room record; completed evidence is never persisted in the
  archive.
required_behavior: >
  (1) new job-level field completed_room_ids_cumulative: advance_active_job_phase
  appends the finished phase's completed evidence (its resolved room ids when the
  phase completed normally; its per-room completion evidence otherwise) BEFORE
  resetting the per-phase fields (which stay — phases remain fresh sub-jobs,
  intentional divergence preserved).
  (2) the finalizer's missed computation consumes cumulative ∪ current-phase
  evidence against the JOB's full queue (from RP-013d's frozen queue once landed;
  until then the existing source).
  (3) final-room honesty: at finalize, a room with timing evidence of completion
  (its captured room_timing covers it) counts completed even though the rollover
  never rolled it; an interrupted final room WITHOUT evidence stays missed — no
  synthesis of completion (REVIEW pin).
  (4) STATE-2: clear_incomplete_run only clears when the completing run's queue
  OVERLAPS the logged missed set's map+rooms (comparison, not any-completion);
  docstring's "(full clean)" claim replaced with the real rule.
  (5) build_completed_job_payload persists completed_room_ids (additive field) so
  the record is reconstructible.
allowed_changes: listed symbols + tests
prohibited_changes: per-phase reset semantics unchanged; no retroactive archive edit.
compatibility_constraints: additive archive field; readers tolerate absence.
migration_plan: none.
rollback_plan: 2 commits — (a) cumulative field + finalizer consumption,
  (b) clear-overlap rule + persisted field. Both touch history_store/job_finalizer —
  (a) first, (b) rebases (lesson 4).
reproducer_script: NEW _proof_completed_evidence.py — 3-phase job cancelled in phase
  2: before → all rooms missed incl. phase-1's completed; after → phase-1 rooms
  completed, phase-2 partial per evidence.
expected_before: ["missed = every room", "unrelated clear erased log"]
expected_after: ["missed = only unfinished", "log survives non-overlapping clear"]
tests_to_add_or_modify: cumulative append matrix; final-room evidence rule (both
  directions); STATE-2 overlap rule; persisted field round-trip.
superseded_tests: tests pinning missed=queue-minus-perphase for phased jobs.
broader_gates: full suite. hardware_gate: rides HC-2b stepped run + a cancelled
  stepped run (one extra Alfred cancel mid-phase-2 — cheap, same session).
stop_conditions: [any consumer reads completed_room_ids as per-phase]
escalation_target: main agent → Chris
```

---

## RP-013b — Allocated group timing (RF-11 part 3)

```yaml
packet_id: RP-013b
family_id: RF-11
finding_ids: ["#7:DQ-PH-3", "#9:A3-REC-1", "#9:A3-REC-2"]
files: [custom_components/eufy_vacuum/jobs/phase_runner.py,
  custom_components/eufy_vacuum/learning/history_store.py,
  custom_components/eufy_vacuum/learning/stats_rebuilder.py, tests/]
symbols: [_capture_finishing_phase_timing, _phase_room_timing]
problem: a multi-room group phase records queue_room_ids[0] only — the whole group's
  time/area/battery lands on one room, N-1 rooms vanish, and phase 0 reads the
  WHOLE-RUN queue so the credited room may not even belong to the phase.
required_behavior: >
  _capture_finishing_phase_timing sources ids from the PHASE's resolved_rooms (fixes
  REC-2 simultaneously) and emits ONE timing entry PER room: measured fields divided
  evenly across members with allocated=True and allocation_group_size=N on each
  entry; single-room phases keep allocated=False (exact). stats_rebuilder ingests
  allocated entries with the same math but records them for ACC-6's quality flag
  (single_room=False path — the flag exists, RP-036 consumes it). FABRICATED
  exactness is FORBIDDEN: no per-room boundary inference inside a group (REVIEW pin;
  killed-premise guard).
allowed_changes: listed + tests. prohibited_changes: no counter reset detection; no
  changes to the tracker (RP-012 owns attribution improvements).
compatibility_constraints: additive fields on room_timing entries.
migration_plan: none. rollback_plan: single commit.
reproducer_script: NEW _proof_group_allocation.py — 3-room group phase: before → one
  entry, room[0] credited 100%; after → three entries, allocated=True, sums equal.
expected_before: ["1 timing entry for 3-room group", "room[0] credited full"]
expected_after: ["3 allocated entries", "sum preserved", "phase-scoped ids"]
tests_to_add_or_modify: allocation math incl. rounding; phase-scoped id source;
  single-room exactness unchanged.
superseded_tests: the 'one strict-order phase = one room' docstring-pinned tests.
broader_gates: full suite. hardware_gate: HC-2b stepped run — OBS-B-1's
  three-inconsistent-durations cross-check happens HERE (compare the new record's
  cleaning_seconds vs wall vs derived).
stop_conditions: [stats_rebuilder double-counts allocated entries in any fixture]
escalation_target: main agent → Chris
```

---

## RP-013d — The job's own queue is the record of the run (RF-11 part 4)

```yaml
packet_id: RP-013d
family_id: RF-11
finding_ids: ["#16:A4-STATE-6"]
files: [custom_components/eufy_vacuum/learning/history_store.py, tests/]
symbols: [build_completed_job_payload queue block]
problem: >
  the payload's queue block prefers the LIVE queue over the job's own — a room
  switch flipped mid-run makes missed-rooms/trouble-rooms name a room never in
  the run (the exact incident already fixed for resolved_rooms, queue forgotten).

  AMENDED 2026-08-01 after stepped Run A (job_2026-08-01T13-49-21). There are
  TWO ways the queue block goes wrong and the original packet only named one.
  On that run the record came out queue_room_ids=[25] vs resolved_rooms=[27, 25]
  — the Kitchen, 255 seconds of it, absent from the queue half — and the
  originally-specified fix would NOT have changed it. On a PHASED job
  advance_active_job_phase overwrites the job's OWN top-level queue_room_ids
  with the phase it moved into, so the "job-frozen snapshot" is itself [25].
  Preferring it over the live queue is a no-op for every stepped run.
required_behavior: >
  Mirror the resolved_rooms ladder PROPERLY — that ladder is a UNION-OF-PHASES,
  not a preference between two flat lists, and its in-code comment
  (history_store.py:829-843) already explains why the top-level list cannot be
  trusted after an advance. The queue block needs the same four rungs:
    1. a PHASED job  -> the union of ALL phases' queue_room_ids, deduped, order
       preserved (this is the rung the original packet was missing);
    2. an ATOMIC job -> the job's top-level queue_room_ids launch snapshot;
    3. the LIVE queue_state only when the job carries none;
    4. empty.
  Derive it alongside resolved_rooms rather than as a second hand-written
  walk — one traversal answering both questions, per the centralize-the-QUESTION
  ladder. queue_rooms and room_count must follow the same source as the ids they
  describe, or the block becomes internally inconsistent in a new way.
rollback_plan: single commit (rebases on RP-013c's history_store edits — lesson 4).
reproducer_script: extend _proof_completed_evidence.py — TWO cases, not one.
  (a) atomic job + mid-run queue flip (already written, case 3);
  (b) PHASED job after an advance — the Run A shape. Case (b) is the one that
  fails against the original required_behavior, so it is the load-bearing one.
expected_before: ["queue block = live flipped queue",
  "phased: queue block = only the last phase's rooms"]
expected_after: ["queue block = job's frozen queue",
  "phased: queue block = union of all phases"]
hardware_evidence: >
  job_2026-08-01T13-49-21.json, frozen at
  .claude/notes/_frozen/baseline/job_2026-08-01T13-49-21-steppedA.json —
  queue_room_ids [25] vs resolved_rooms [27, 25] on a completed 2-room run.
tests_to_add_or_modify: precedence parity test with resolved_rooms, INCLUDING
  the phased-union rung; a regression asserting the two blocks name the same
  rooms for any job shape.
broader_gates: full suite. hardware_gate: none (SOURCE_DECIDABLE).
escalation_target: main agent → Chris
```

---

## RP-013f — A stepped run's cleaning time is the whole run (RF-11 part 6)

**Authored 2026-08-01 from stepped Run A. Not in the original synthesis — no
audit could see it, because none had a stepped-run record to look at.**

```yaml
packet_id: RP-013f
family_id: RF-11
finding_ids: ["live:REC-A", "live:REC-B"]
severity: HIGH
files: [custom_components/eufy_vacuum/learning/job_finalizer.py,
  custom_components/eufy_vacuum/learning/utils.py, tests/]
symbols: [cleaning_time_seconds derivation + its wall-clock fallback,
  build_overhead_observed]
problem: >
  REC-A (under-reports). cleaning_time_seconds is taken from
  last_cleaning_time_seconds — the last-seen DEVICE counter. Every dispatched
  phase RESETS that counter, so a stepped run records only its FINAL phase.
  Run A recorded 302 s against a measured 255 + 302 = 557 s: 46 % short.

  REC-B (over-reports, latent, and RP-012(d) just made it MORE reachable). When
  the sensor path yields None the function derives wall-clock minus
  paused_duration_seconds minus recharge_seconds_accumulated. It does NOT
  subtract COMMANDED break phases. On Run A that path would have produced
  1169 s against a true 557 s — 110 % over. It did not fire only because the
  sensor happened to be readable. Note the interaction: before RP-012(d) a
  commanded hold was (wrongly) accumulated into recharge_seconds_accumulated,
  which accidentally compensated here. Fixing that bug removed the only term
  that was masking this one — a repair making a latent defect reachable, the
  same shape as RP-012(d)'s own origin.

  THE CASCADE is what makes this HIGH rather than a cosmetic number.
  learning/utils.py:203 computes total_overhead_minutes = duration −
  cleaning_minutes, so Run A recorded 14.45 min of overhead against a true
  10.19. learning/stats_rebuilder.py:316 then AVERAGES total_overhead_minutes
  across jobs — every stepped run permanently inflates the learned overhead
  model, and the model is what the card's ETAs are built from. Run A carried
  used_for_learning: true, learning_blockers: [] — it is already in.
required_behavior: >
  Derive the job's cleaning time by SUMMING PHASE CONTRIBUTIONS, not by reading
  a device counter whose reset semantics are brand-specific and undocumented:
  room phases contribute their room_timing cleaning_seconds, zone phases their
  zone_timings, break phases contribute ZERO. An ATOMIC job keeps today's
  behaviour (one phase, one counter read — nothing to sum).

  Compose-safe with RP-013b: that packet re-splits a group phase's single timing
  entry into per-member allocated entries while PRESERVING the measured totals
  (its proof asserts exactly that), so a sum over room_timing is correct both
  before and after it lands. State this in the commit so the two are not seen to
  conflict.

  The wall-clock fallback must subtract commanded break-phase durations for the
  same reason it already subtracts paused and recharge seconds. A phase carries
  _timing_end_t and takes its start from the previous phase's, so the spans are
  available without new plumbing.
prohibited_changes: >
  Do NOT "fix" this by preferring cleaning_area's behaviour. Run A recorded
  cleaning_area_m2 5.8 against a per-room sum of 5.3 — area ACCUMULATED across
  phases while time did not. The same last_* read yields a cumulative answer for
  one counter and a per-phase answer for the other because the device resets
  them differently, and nothing documents that per brand. Neither counter is a
  trustworthy job total; only the phase sum is.
rollback_plan: 2 commits (phase-sum derivation; wall-clock fallback break-phase
  subtraction) — different failure modes, independently revertable.
reproducer_script: NEW _proof_job_cleaning_total.py — a 3-phase job whose room
  phases measured 255 s and 302 s with a charge_wait between them; assert the
  job total and the derived overhead. Second case drives the wall-clock fallback
  with the sensor absent.
expected_before: ["job cleaning_time_seconds = 302 (last phase only)",
  "overhead 14.45", "fallback counts the commanded hold as cleaning"]
expected_after: ["job cleaning_time_seconds = 557", "overhead 10.2",
  "fallback excludes the commanded hold"]
hardware_evidence: >
  job_2026-08-01T13-49-21.json, frozen at
  .claude/notes/_frozen/baseline/job_2026-08-01T13-49-21-steppedA.json.
tests_to_add_or_modify: phase-sum across room/zone/break phases; atomic job
  unchanged; fallback with and without break phases; an overhead-residual test
  pinning total_overhead to the summed cleaning time.
superseded_tests: any test pinning a stepped job's cleaning_time_seconds to the
  final phase's counter — that IS the defect; update with the decision recorded.
broader_gates: full suite.
hardware_gate: none to LAND (SOURCE_DECIDABLE — Run A is already the evidence).
  Ride-along on the next stepped run: expect the job total to equal the sum of
  its room timings, which Run A visibly violates.
escalation_target: main agent -> Chris
```

---

## RP-013e — Recorder predicates and scoped writes (RF-11 part 5)

```yaml
packet_id: RP-013e
family_id: RF-11
finding_ids: ["#9:A3-REC-4", "#9:A4-AJ-2", "#12:A5-METRICS-2", "#9:A3-REC-5"]
files: [custom_components/eufy_vacuum/jobs/active_job.py,
  custom_components/eufy_vacuum/listeners/job_metrics.py, tests/]
symbols: [record_counter_sample, record_active_job_sensor_value, job_metrics
  watch_map construction]
problem: both sample recorders use the permanently-true started_at-and-not-ended_at
  predicate and fan writes into EVERY map bucket (a finished/stranded job absorbs
  another run's counters); last_battery_percent has NO writer so per-room battery
  attribution is dead (OBS-B-3's null battery_delta).
required_behavior: >
  (1) both recorders adopt run_is_in_flight (the module docstring's own
  prescription — includes external; NOT dispatched_job_is_in_flight, per the
  recorded intent that recorders must match external) and write ONLY into buckets
  whose job is in flight (scoped, not fan-out). (AMENDED per REVIEW-07 T2-D6)
  When MORE THAN ONE bucket qualifies (stale slots exist until RP-011 beds in):
  write the bucket matching resolve_active_map_id; else the newest started_at;
  WARN once per job — never fan out to multiple.
  (2) job_metrics' watch_map subscribes the adapter-declared battery entity →
  last_battery_percent (both adapters declare it) — closes METRICS-2/REC-5 and
  OBS-B-3 in one edit.
prohibited_changes: pose-sampler predicates untouched (CF-2).
rollback_plan: 2 commits (recorder predicate/scope; battery watch) — different files.
reproducer_script: NEW _proof_recorder_scope.py — finished job absorbs a sample
  (before) / scoped (after); battery key populated after a watched change.
expected_before: ["finished bucket absorbed sample", "battery=None"]
expected_after: ["only in-flight bucket written", "battery=57"]
tests_to_add_or_modify: predicate matrix incl. external; scope; battery plumb-through
  to battery_delta.
superseded_tests: fixtures seeding last_battery_percent by hand — now production-fed;
  update docstrings.
broader_gates: full suite. hardware_gate: HC-2b ride-along — expect non-null
  per-room battery_delta in the new capture (closes OBS-B-3 observably).
escalation_target: main agent → Chris
```

---

## RP-014 — Every asker uses the owned in-flight helpers (RF-12)

```yaml
packet_id: RP-014
family_id: RF-12
finding_ids: ["#12:A5-METRICS-1", "#14:A6-VAC-1", "direct read:DR-SENS-1",
  "#12:A3-COMMON-6", "#12:A3-COMMON-4"]
files: [custom_components/eufy_vacuum/listeners/job_progress.py,
  custom_components/eufy_vacuum/dock/manager.py,
  custom_components/eufy_vacuum/sensor/lifecycle.py,
  custom_components/eufy_vacuum/listeners/_common.py,
  custom_components/eufy_vacuum/listeners/lifecycle.py,
  custom_components/eufy_vacuum/jobs/active_job.py, tests/]
symbols: [_handle_job_progress_tick, get_dock_action_status, active_job sensor
  native_value, listener status literals, completion vocabulary constants]
problem: five sites hand-inline {"started","paused"} answering ROBOT questions with
  the QUEUE set — external runs get no Lever B refresh; dock wash/dry actions fire
  mid-external-run (HIGH, actuating); the active_job sensor reads 'none' during a run
  the system itself considers in flight; completion vocabulary defaults are
  hand-copied in two modules.
required_behavior: >
  per the adjudication table (robot vs queue, pinned): job_progress → run_is_in_flight
  (external ticks are Lever B's purpose); dock gate → run_is_in_flight (docstring
  names it); active_job sensor → reports 'external' as a distinct state (additive —
  card half: verify the card's state enum renders 'external'; add the i18n label key
  to en.js + ALL 17 locale packs, `npm run check:i18n` — lesson 3); COMMON-6 listener
  sites → per-site table in-packet (sites asking queue questions KEEP
  dispatched_job_is_in_flight, listed explicitly); COMMON-4 → completion vocabulary
  defaults derived from ONE constant in _common (derived-constant rung — the two
  modules import it).
prohibited_changes: CF-2 pose-sampler predicates; no set merging (the questions stay
  distinct — no ACTIVE_STATUSES constant).
card_half: sensor 'external' label — src enum + 18-locale i18n key (budgeted here,
  not discovered at escalation; lesson 3).
rollback_plan: 4 commits by consumer (progress / dock / sensor+card / vocabulary).
reproducer_script: NEW _proof_inflight_askers.py — external-status job: progress tick
  fires, dock action refuses, sensor reads 'external'.
expected_before: ["no tick for external", "dock action allowed mid-external",
  "sensor: none"]
expected_after: ["tick fired for external", "dock action refused: run_in_flight",
  "sensor: external"]
tests_to_add_or_modify: per-site adjudication tests; vocabulary derivation test.
superseded_tests: tests pinning the literal sets at the five sites.
broader_gates: full suite + frontend gates (card half).
hardware_gate: tier 2 — app-started run ride-along on the Wave-2 batch (VAC-1/SENS-1
  observable); tranche-1 HC-2 external capture is the before-state.
stop_conditions: [the card's state enum cannot render an unknown state without error]
escalation_target: main agent → Chris
```

