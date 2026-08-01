# Sonnet Application Packets — Wave 0 (RP-001..RP-004)

Executor rules: read ONLY this packet + linked source/docs. Confirm target commit.
Never close ledger findings. Stop at every `stop_and_escalate_when`.

---

## RP-001 — Write the finalize permanent gate inside the claimed window

```yaml
packet_id: RP-001
title: finalize claim released only after finalized=True on success
repair_family: RF-01
problem: the finalize body runs twice per job when two lifecycle tasks interleave
  (hardware-proven, ivy-run-BEFORE.log) — learning ingests every affected job twice
root_cause: the claim's finally releases finalize_claimed_at before the permanent
  gate (finalized=True) is written by the CALLER in another module after an await
goal: the finalize body can never run twice for one job
violated_invariant: success permanence written inside the claimed window
exact_match_rules: expected_* fragments are verbatim-match on the proof's stdout;
  asserted_values are exact equality; state mutations checked by direct dict reads
escalation_target: main agent → Chris
findings_addressed: ["hardware baseline:HW-FINAL-1"]
findings_not_closed: ["#12:A2-LIFE-1", "#16:A5-SVC-2", "#9:A5-STR-5" (RP-002),
  "#14:A3-SNAP-3" (later read-side packet)]
preconditions: clean master; pytest tests --no-cov green
target_commit: c61b3eb (or current master if unchanged in custom_components/)
files_allowed_to_change:
  - custom_components/eufy_vacuum/learning/manager.py
  - tests/ (new/modified tests only)
symbols_to_add: []
symbols_to_modify: [LearningManager.async_finalize_completed_job]
symbols_to_remove: []
ordered_edits:
  - step: 1
    what: >
      In async_finalize_completed_job (learning/manager.py:721-741 at target commit),
      replace the try/finally with explicit success/failure paths:
        try:
            result = await self._finalize_claimed(...)   # unchanged kwargs
        except BaseException:
            if _stored_job is not None:
                _stored_job.pop("finalize_claimed_at", None)   # failure -> retryable
            raise
        if _stored_job is not None:
            if isinstance(result, dict) and isinstance(result.get("completed_job"), dict):
                # SUCCESS: permanent gate written INSIDE the claimed window.
                _stored_job["finalized"] = True
            _stored_job.pop("finalize_claimed_at", None)
        return result
  - step: 2
    what: >
      Rewrite the comment at the (former) finally block: the old text ("After a
      successful finalize `finalized` is the gate, so releasing does not reopen it")
      is FALSE and is the documented cause of the hardware-proven double finalize
      (OBS-IVY-1). New comment states: the gate is written here, inside the claim,
      because the caller's mark_active_job_finalized runs after an await
      (listeners/lifecycle.py end_job executor hop) and a second listener task can
      interleave in that gap.
  - step: 3
    what: >
      (DECIDED per GATE4 Q1 — supersedes the earlier warn-and-proceed) When
      `_stored_job is None`, REFUSE: log a warning with vacuum/map context and
      return {"vacuum_entity_id": ..., "map_id": str(map_id), "finalized": False,
      "reason": "no_active_job_record"} WITHOUT calling _finalize_claimed. No
      events, no slot marking, no summary, no claim-less fallback. Consumers
      already handle refusal shapes via RP-002's finalize_result_succeeded.
source_of_truth: the chokepoint (same rationale as commit 71e089c — any future entry
  point is safe by construction)
required_api_or_helper_signatures: none (no signature changes)
call_sites_to_migrate: none — mark_active_job_finalized remains an idempotent second
  writer of finalized=True (jobs/active_job.py:2035); DO NOT remove or reorder it.
compatibility_behavior_to_preserve:
  - refusal dict shapes {"finalized": False, "reason": "already_finalized"|"finalize_in_flight"} unchanged
  - transient failure (raise) still releases the claim → retry possible
  - _clear_orphaned_finalize_claims startup reaper semantics unchanged
migration_steps: none
forbidden_simplifications:
  - do NOT move mark_active_job_finalized earlier in listeners/lifecycle.py (fixes one
    of three entry points only)
  - do NOT make _finalize_claimed write finalized (the claim owner at the chokepoint
    writes it; keep the write next to the release for auditability)
  - do NOT treat a dict result WITHOUT completed_job as success (missing_started_at /
    partial failures must stay retryable)

reproduction:
  reproducer_script: >
    NEW — main agent materializes as .claude/notes/_proof_finalize_window.py:
    an asyncio test double-invoking async_finalize_completed_job from two tasks where
    _finalize_claimed's body awaits an event between claim and return, simulating the
    executor yield; count body executions.
  reproducer_command: docker eufy-vacuum-test → python .claude/notes/_proof_finalize_window.py
  placement: .claude/notes/ (external proof; not part of the suite)
  environment: test image, no HA required
  destructive_or_safe: safe (in-memory)
  provenance: models the exact interleave proven on hardware (ivy-run-BEFORE.log,
    job_2026-07-31T20-14-28 double emission at 20:16:13.339/.342)
  validity_notes: >
    The proof MUST let task A fully return (claim released) before task B re-checks —
    i.e. B blocks on an event A sets AFTER its return, mirroring lifecycle.py's
    L334 executor hop. A simplified version where B runs during A's body only proves
    the in-flight refusal (already correct) and would falsely pass pre-repair.
  expected_before:
    exit_status: 0
    asserted_values: body_run_count == 2
    required_output_fragments: ["BODY RAN 2 TIMES"]
    forbidden_output_fragments: ["finalize_in_flight", "already_finalized"]
    required_state_mutations: two completed_job results returned
  expected_after:
    exit_status: 0
    asserted_values: body_run_count == 1
    required_output_fragments: ["BODY RAN 1 TIME", "second call refused: already_finalized"]
    forbidden_output_fragments: ["BODY RAN 2 TIMES"]
    required_state_mutations: stored job carries finalized=True after first return

regression:
  existing_tests: the Wave-0/1 exactly-once suite (grep tests/ for finalize_claimed_at)
  tests_to_add:
    - test: second finalize AFTER a successful first returns already_finalized even
      when invoked before the caller's mark_active_job_finalized runs
    - test: a raising _finalize_claimed releases the claim and a retry succeeds
    - test: a dict-but-not-success result (no completed_job) releases without setting finalized
  tests_to_modify: any fixture asserting the claim is released before finalized is set
    (fix the fixture, never weaken the assertion)
  closure_assertions: finalized=True is observable the moment async_finalize_completed_job
    returns a success shape
  broader_suites: pytest tests --no-cov

full_acceptance_gates: pytest tests --no-cov -p no:cacheprovider
hardware_validation: >
  tier 2 / HARDWARE_BASELINE_GATE (Chris approves): Ivy cancel-and-dock ×2 jobs;
  flight recorder unfiltered; expect exactly one finalize emission per job and exactly
  one 'Incomplete run log written' per job. Compare against ivy-run-BEFORE.log.
expected_behavior_before: finalize body runs twice per job on the interleave (hardware-proven)
expected_behavior_after: exactly once; second entrant refused with already_finalized
rollback_plan: git revert (single commit; no persisted-schema change)
ledger_closure_evidence: reproducer before/after + Ivy post-repair capture
residual_risk_note: >
  (REVIEW D8) finalized=True is in-memory until the next async_save; an HA crash in
  that window re-runs the body on restart. Pre-existing aperture, NOT widened by this
  packet — the caller's save path persists it. Executor verifies at implementation
  that a save is scheduled on the success path; if none is found, report (do not add
  one unprompted).
stop_and_escalate_when:
  - _finalize_claimed's success shape is not `completed_job`-keyed at target commit
  - an existing test exercises the `_stored_job is None` path EXPECTING a completed
    finalize — that test was asserting fiction per GATE4 Q1; fix the fixture, but
    REPORT which production caller it modeled (the caller inventory matters)
```
Additional regression (GATE4 Q1): `_stored_job is None` → returns
`no_active_job_record` refusal, `_finalize_claimed` never invoked, no event fired.

---

## RP-002 — Finalize refusals are not successes (three consumers)

```yaml
packet_id: RP-002
title: consumers branch on the finalize result before side effects
repair_family: RF-01
goal: no EVENT_JOB_FINISHED, no finalized-slot marking, no success report from a refusal
violated_invariant: refusal dict != success
findings_addressed: ["#12:A2-LIFE-1", "#16:A5-SVC-2", "#9:A5-STR-5"]
findings_not_closed: ["#14:A3-SNAP-3" (snapshot read-side, Wave 2)]
preconditions: RP-001 merged
target_commit: post-RP-001 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/learning/manager.py   # helper only
  - custom_components/eufy_vacuum/listeners/lifecycle.py
  - custom_components/eufy_vacuum/learning/services.py
  - custom_components/eufy_vacuum/jobs/active_job.py
  - tests/
symbols_to_add: [learning.manager.finalize_result_succeeded]
symbols_to_modify: [listeners.lifecycle._process finalize branch,
  learning.services finalize_learning_job handler,
  jobs.active_job.async_finalize_stranded_job]
ordered_edits:
  - step: 1
    what: >
      Add module-level `def finalize_result_succeeded(result) -> bool` in
      learning/manager.py (beside the producer): True iff isinstance(result, dict)
      and isinstance(result.get("completed_job"), dict). Docstring names the three
      open-coded siblings it replaces (manager.py:651, :793, :888) and repoints them.
  - step: 2
    what: >
      listeners/lifecycle.py (finalize branch, ~:316-355): after the await, branch on
      finalize_result_succeeded(result). On refusal: log at DEBUG with the reason,
      do NOT call mark_active_job_finalized, do NOT fire EVENT_JOB_FINISHED, do NOT
      run tracker.end_job (the successful pass owns those). A2-LIFE-1's all-null
      duplicate event disappears.
  - step: 3
    what: >
      learning/services.py finalize_learning_job handler (:409 region): on refusal,
      raise ServiceValidationError carrying result["reason"] (already_finalized /
      finalize_in_flight) instead of firing eufy_vacuum_job_finished with fabricated
      status "completed". On success, event fires with the REAL outcome status (no
      "completed" default: use the value from the completed_job outcome; if absent,
      omit the event and warn).
  - step: 4
    what: >
      (AMENDED per REVIEW D1) jobs/active_job.py async_finalize_stranded_job
      (:2447-2464): branch by refusal reason —
      (a) reason == "finalize_in_flight" or result is None: return
          {"finalized": False, "reason": ...} WITHOUT calling
          mark_active_job_finalized — the slot stays for the next reaper tick; log
          WARNING once per job_id (dedup key on the record).
      (b) reason == "already_finalized": the learning record exists but the slot was
          never marked (crash window between chokepoint and caller-mark). Call
          mark_active_job_finalized(finalize_result=None) — verified at source
          (active_job.py:2028-2078): sets status=completed + finalized=True and the
          isinstance guard writes NO fabricated finalize_summary. Return
          {"finalized": True, "reason": "already_finalized_slot_marked"}.
      Rationale: without (b) the reaper re-reaps and re-refuses the same slot EVERY
      MINUTE FOREVER; with it, the RP-001 crash window is self-healing.
compatibility_behavior_to_preserve:
  - successful-path event payloads unchanged
  - EVENT_JOB_FINISHED consumers (sensor latch gates on completed_job presence —
    corpus notes internal consumers are safe) — verify sensor/__init__.py:410 gate
forbidden_simplifications:
  - no reason-literal matching — branch on finalize_result_succeeded only
  - do not "fix" by making the producer raise on refusal (refusal is a normal outcome
    for the second entrant; the claim design is correct)
reproduction:
  reproducer_script: extend _proof_finalize_window.py — second entrant path asserts
    no event fired and slot not marked
  expected_before:
    required_output_fragments: ["EVENT fired on refusal", "stranded reported finalized:True on refusal"]
    forbidden_output_fragments: []
  expected_after:
    required_output_fragments: ["no event on refusal", "stranded left reapable"]
    forbidden_output_fragments: ["EVENT fired on refusal"]
regression:
  tests_to_add:
    - lifecycle refusal fires no event, marks nothing, skips tracker end_job
    - service refusal raises ServiceValidationError with the reason
    - stranded finalize_in_flight refusal leaves status untouched, reports finalized False
    - stranded already_finalized refusal MARKS the slot (status completed,
      finalized True, NO finalize_summary) and does not recur on the next tick
  closure_assertions: per finding (three sites verified independently — §L)
hardware_validation: rides HC-0 (the Ivy duplicate-path capture shows zero
  refusal-shaped EVENT_JOB_FINISHED)
rollback_plan: git revert per site (three commits, one per file)
exact_match_rules: verbatim fragment match on proof stdout; slot-state assertions by
  direct dict reads
escalation_target: main agent → Chris
downstream_note: RP-011 (reaper isolation) edits the SAME function — it rebases on
  this packet's amended version (REVIEW-03 edge; do not author RP-011 against c61b3eb).
stop_and_escalate_when:
  - any card/automation consumer is found relying on the duplicate event
  - sensor latch at sensor/__init__.py:410 does NOT gate on completed_job presence
```

---

## RP-003 — Manager shutdown seam + unload ledger (INIT-1)

```yaml
packet_id: RP-003
title: a reloaded entry's previous manager can neither run nor write
repair_family: RF-16
goal: reload produces exactly one live manager; stale managers stop persisting
violated_invariant: loop-lifetime work attached to a teardown ledger
findings_addressed: ["#14:A1-INIT-1"]
findings_not_closed: [panels ×3, learning services ×4, water-amendment ×2, debug timer
  ×3, LIFE-2 tasks, SRC-5 cache, REG-2/3, GUARD-6, VAC-4 — later RF-16 packets]
target_commit: post-RP-002 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/core/manager.py
  - custom_components/eufy_vacuum/jobs/phase_runner.py
  - custom_components/eufy_vacuum/learning/external_run.py
  - custom_components/eufy_vacuum/__init__.py
  - tests/
symbols_to_add: [EufyVacuumManager.async_shutdown, EufyVacuumManager._closed]
symbols_to_modify: [async_initialize (track spawned work), async_save (closed guard),
  __init__.async_setup_entry (register shutdown), phase_runner._spawn_dock_poller
  (track task), external_run timer arming (track cancel handles)]
ordered_edits:
  - step: 1
    what: manager gains self._closed = False and self._background_tasks/_timers
      ledgers; every hass.async_create_task / async_call_later spawned from
      async_initialize's re-arm loop and external_run's grace timers registers its
      handle (phase_runner exposes cancel_all(); external_run exposes cancel_timers()).
  - step: 2
    what: "async_shutdown(): sets _closed, cancels ledgered tasks/timers, awaits
      cancellation, logs residue at DEBUG."
  - step: 3
    what: "async_save(): if self._closed: log WARNING 'save after shutdown suppressed'
      and return (belt-and-braces against the stale-store clobber)."
  - step: 4
    what: "__init__.async_setup_entry: entry.async_on_unload(manager.async_shutdown)
      registered immediately after manager construction, BEFORE async_initialize
      (so a mid-setup failure after construction still tears down)."
forbidden_simplifications:
  - no blanket task-cancellation of hass-wide tasks; only ledgered handles
  - _still_ours() checks in pollers remain (defense in depth)
inventory_obligation: >
  (REVIEW-04 addition) while wiring the ledger, EMIT the list of every
  hass.async_create_task / async_call_later / async_track_* spawn site found in
  core/manager.py, jobs/phase_runner.py, learning/external_run.py that is NOT
  ledgered by this packet — in the completion report, for the later RF-16 packets.
reproduction:
  reproducer_script: NEW _proof_manager_reload.py — construct manager A, arm a fake
    ledgered timer, simulate unload (call shutdown), construct manager B, fire A's
    captured callbacks → assert A performs no save and B's data untouched.
  expected_before:
    required_output_fragments: ["stale manager saved after unload"]
  expected_after:
    required_output_fragments: ["stale save suppressed", "timers cancelled: "]
    forbidden_output_fragments: ["stale manager saved after unload"]
regression:
  tests_to_add: [shutdown cancels ledgered work, save-after-shutdown no-op,
    double-reload yields one live manager writing]
hardware_validation: tier 1 (HC-1) — reload entry twice on live HA; grep the log for
  'save after shutdown suppressed' absence in steady state; verify jobs still finalize.
rollback_plan: git revert (additive seam)
stop_and_escalate_when:
  - an unledgered spawn site is found outside the two named modules (report inventory,
    do not chase — later RF-16 packets own the rest)
```

---

## RP-004 — Flight recorder: redact and truncate exc_info (DR-DBG-1)

```yaml
packet_id: RP-004
title: tracebacks get the same masking + cap as messages
repair_family: RF-33
goal: dumps are safe to hand to a maintainer; multi-MB regression closed for tracebacks
findings_addressed: ["direct read:DR-DBG-1"]
findings_not_closed: [DBG-2/3/4/6/7 (RP-039)]
target_commit: post-RP-003 master
files_allowed_to_change: [custom_components/eufy_vacuum/debug_capture.py, tests/]
symbols_to_modify: [the record-store path at debug_capture.py:163-174, render_text]
ordered_edits:
  - step: 1
    what: apply the existing secret-masking function to the formatted exception text
      (both storage at :173-174 and render), then cap at the same ~2kB elision used
      for messages, with an explicit '… elided N chars' marker.
  - step: 2
    what: extend test_redaction_masks_secrets with an exc_info=True case asserting the
      token appears ZERO times in the dump and the 50kB payload is elided.
reproduction:
  reproducer_script: the record's own proven repro (log.debug with exc_info carrying
    token=SUPERSECRET123; a RuntimeError carrying 50kB)
  expected_before:
    required_output_fragments: ["SUPERSECRET123"]   # in the dump, twice
  expected_after:
    forbidden_output_fragments: ["SUPERSECRET123"]
    required_output_fragments: ["elided"]
regression:
  tests_to_add: [exc_info masking, exc_info elision]
hardware_validation: tier 0
rollback_plan: git revert
stop_and_escalate_when: [the gist/public copy needs a matching update — flag to Chris
  (he owns the published copy)]
```
