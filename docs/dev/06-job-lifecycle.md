# 06 — Cleaning Job Lifecycle

Traces every state, transition, side effect, and event across the full life of
a room-cleaning job — from queue build through finalization. A developer should
be able to follow the entire flow from source code using this document.

**Primary source files:**
- `custom_components/eufy_vacuum/core/manager.py`
- `custom_components/eufy_vacuum/jobs/active_job.py`
- `custom_components/eufy_vacuum/jobs/job_monitor.py` — `evaluate_job_lifecycle`,
  `build_start_blocker_from_lifecycle`, `is_stranded_started` + the reaper constants
- `custom_components/eufy_vacuum/jobs/phase_runner.py`
- `custom_components/eufy_vacuum/__init__.py`
- `custom_components/eufy_vacuum/learning/job_finalizer.py`
- `custom_components/eufy_vacuum/learning/history_store.py`
- `custom_components/eufy_vacuum/learning/external_ingest.py`
- `custom_components/eufy_vacuum/learning/services.py`
- `custom_components/eufy_vacuum/listeners/pause_timeout.py`
- `custom_components/eufy_vacuum/const.py`

---

## 1. Pre-job: Queue Build

### `build_queue`

`EufyVacuumManager.build_queue(vacuum_entity_id, map_id)` reads the managed
room records from the map bucket, passes them to
`build_queue_from_managed_rooms` (`queue/queue_engine.py`), and writes the
result to `self.data["queue"][vacuum_entity_id][map_id]`. Also updates the
runtime object: `runtime.selected_map_id` and `runtime.queue_room_ids`.

Only rooms whose `enabled` flag is `True` are included. Output shape:

```
{
  "vacuum_entity_id": str
  "map_id":           str
  "room_count":       int
  "queue_room_ids":   list[int]
  "queue_rooms":      list[QueueRoomSummary]
}
```

where each `QueueRoomSummary` is `{room_id: int, name: str, slug: str, order: int
(default 999), profile_name: str (default "vacuum_quick")}` (`queue/queue_engine.py`).

### `build_room_payload`

`EufyVacuumManager.build_room_payload(vacuum_entity_id, map_id)` builds the
`room_clean` command payload. Before building, it applies carpet/mop invariants
via `_protected_room_config` on every room and fetches:

- the current queue state for `queue_room_ids`
- stored room profiles from `self.data["profiles"]["room_profiles"]`
- vacuum capabilities via `get_vacuum_capabilities`

Result stored at `self.data["payloads"][vacuum_entity_id][map_id]`. Contains
the raw `payload` dict plus a `resolved_rooms` list with full per-room settings.

### `get_start_status` — blocker reasons

`get_start_status` calls `_build_effective_start_plan` (which evaluates all
room rules against live HA states), `get_lifecycle_state`, and
`get_onboarding_state` and assembles a status dict. **Every return carries:**
`vacuum_entity_id`, `map_id`, `selected_map_id`, `active_map_id`, `queue_room_ids`,
`payload_room_count`, `lifecycle_state`, `lifecycle_state_label`, `lifecycle_message`,
`reason`, `reason_label`, `message`, `blocked`, `warning`, `onboarding_status`,
`preflight`. Three further keys are present only on SOME of the six return
branches (`core/manager.py::get_start_status`) — do not assume any of them:

| Branch | `reason_params` | `requires_confirmation` / `confirm_token` |
|---|---|---|
| `job_paused` | `{}` | **absent** |
| `onboarding_required` | **absent** | **absent** |
| `all_selected_rooms_blocked` | **absent** | present |
| lifecycle-blocked (the `reason` table below) | `{}` | present |
| preflight-blocked | present (the preflight's own `reason_params`) | present |
| ready (not blocked) | present (empty unless a preflight reason won) | present |

It returns with `blocked: True` and the following `reason` strings in priority order:

| `reason` | Condition |
|---|---|
| `"job_paused"` | `active_job["status"] == "paused"` |
| `"onboarding_required"` | One or more enabled rooms are missing a floor type |
| `"all_selected_rooms_blocked"` | All selected rooms were blocked by rules; none remain |
| `"no_target_map"` | `selected_map_id` is empty |
| `"map_mismatch"` | `selected_map_id` != vacuum's active map |
| `"no_rooms_selected"` | Queue is empty |
| `"invalid_payload"` | **No phase in the whole plan actually cleans anything** (A5-PP-RP-2): `get_start_status` counts `clean_phase_count` = phases with `room_count > 0` OR a `zone` phase with resolved `zones`, and `build_start_blocker_from_lifecycle` blocks when it is 0. (The old first-phase-only `payload_room_count <= 0` check refused a runnable rooms-then-zone plan whose first surviving phase was a zone; it remains the fallback only for callers that pass no `clean_phase_count`.) |
| `"mid_job_service"` | Dock or task status is in a hard service state (washing, recycling, emptying) |
| `"active_job_running"` | A room-clean job is already active |
| `"vacuum_busy"` | Vacuum is busy and not dockable/idle |
| `"incomplete_access_graph"` | Room access graph is partially configured |
| `"access_graph_required_for_rules"` | Rules are present but no access graph exists |
| `"access_graph_required"` | Blocker rules exist without an access graph |

The lifecycle state `"dock_drying"` is a non-blocking warning — it sets
`blocked: False` with `warning: True` and `reason: "dock_drying"`.

The lifecycle evaluation (`evaluate_job_lifecycle`) and the blocker assembly
(`build_start_blocker_from_lifecycle`) live in `jobs/job_monitor.py`, along with
the `PreflightResult` / `BlockedRoomEntry` TypedDicts (a blocked room's `source`
is `"direct_rule"` or `"access_dependency"` — PRE-4).

#### Preflight rule evaluation (`_build_effective_start_plan`)

This is the authoritative rule-evaluation site for job start (the only other
site is `get_runtime_path_block_report` for mid-job path changes). Steps:

1. All managed rooms with automation rules are loaded.
2. Blocker rules are evaluated against live HA entity states. Matching rooms go
   into `direct_blocked`.
3. Modifier rules are evaluated; matching changes are accumulated in
   `modifier_matches`.
4. Access-graph propagation: rooms that require traversal through a
   directly-blocked room are also marked blocked.
5. `included_room_ids` = selected minus blocked.
6. `requires_confirmation` becomes `True` when `blocked_ratio_time >= 0.20` or
   `blocked_ratio_rooms >= 0.40`. When confirmation is required, a
   `confirm_token` (opaque hash of the preflight parameters) is generated.

> **See also:** [09-room-rules-system](09-room-rules-system.md) §5 for the full rule evaluation pipeline and operator reference; [07-queue-engine](07-queue-engine.md) §5 for the access graph data structure `_build_effective_start_plan` traverses to propagate indirect blocks.

---

## 2. Job Start

### 2a. `start_selected_rooms`

`async EufyVacuumManager.start_selected_rooms(vacuum_entity_id, map_id,
confirm_reduced_run, confirm_token, path_block_action,
pause_timeout_minutes_override, strict_order)`

`strict_order` (opt-in, exposed on the start service as the
`strict_order` boolean field — `services/job_control.py`) makes a
path-optimizing brand clean rooms in queue order by producing one phase per
room (sequenced job model, see §4); it is a no-op for order-honoring brands.

**Step-by-step flow:**

1. **Blocker check** — calls `get_start_status`. If `blocked`, returns
   immediately with `started: False`.
2. **Confirmation handshake** — if `requires_confirmation` is set, start is
   blocked unless:
   - `confirm_reduced_run=True` (bypass flag for automations), **or**
   - the caller supplies a `confirm_token` matching the preflight token.
   If neither, returns `{"started": False, "reason": "confirmation_required", "confirm_token": <token>}`.
3. **Rebuild plan** — calls `_build_effective_start_plan` again (rules may have
   changed since `get_start_status`) and writes the final queue/payload.
4. **Vacuum entity check** — if the HA state object is missing, returns
   `{"started": False, "reason": "vacuum_missing"}`.
5. **Live-id resolution** — calls `_resolve_live_dispatch_payload` to map
   stored (slug-tagged) room ids to the current **live** segment ids before
   dispatch, for brands whose ids renumber on re-segment (Roborock). Wire-only:
   the active job below keeps the stored ids.
6. **Global pre-calls** — calls `_run_global_pre_calls` to push global device
   settings (fan/mop) for brands that expose them only globally (Roborock:
   per-room fan/water can't ride `app_segment_clean`), derived max-wins from
   the selected rooms. No-op when no adapter declares
   `dispatch.global_pre_calls` (e.g. Eufy, which carries fan/water per-room).
   **Order is deliberate (DQ-ACT-6):** the pre-calls run *after* live-id
   resolution, immediately before dispatch — resolution is a real failure path
   (it raises when the map has been re-segmented and the stored slugs no
   longer resolve), and running the pre-calls first once left the device's
   global mop intensity rewritten by a start that then aborted, with nothing
   to put it back (a settings change that outlived the job it was made for).
   Reordering closes that window; it does not make the start transactional —
   a failure inside the dispatch call itself still leaves the pre-call applied.
7. **Command dispatch** — calls `_dispatch_clean_payload` with the resolved
   wire payload (`vacuum.send_command`, `command="room_clean"`, blocking).
8. **Active job initialisation** — calls `build_active_job_state` then enriches.
   Note that `started_at`, `battery_start`, and `job_id` are captured *before*
   dispatch (i.e. ahead of step 7) and only attached onto the active job here
   during this enrichment:
   - `job_metadata` from `build_job_metadata_from_payload`
   - `job_id` (generated as `"job_{YYYY-MM-DDTHH-MM-SS}"`)
   - `started_at` (UTC ISO timestamp)
   - `battery_start`
   - `current_room_started_at` = `started_at`
   - `path_block_action` (normalised; default `"event_only"`)
   - `pause_timeout_minutes` (from config or override)
   - `water_estimate` from `get_planned_job_estimate`

   The start plan's phase sequence is attached to the active job (`phases=`)
   **only when it holds more than one phase** — i.e. a genuine sequenced
   strict-order run. An atomic job leaves the phase keys absent, keeping the
   active-job snapshot byte-identical to pre-sequencing. A phased run
   additionally gets **`phased_job_id`** (`phased_job_id_for(job_id)`,
   `queue/queue_engine.py` — `job_2026-…` → `pj_2026-…`; the key's presence *is*
   the "this run is phased" signal, there is deliberately no separate boolean),
   and its Phased Job parent record is opened right here
   (`_open_phased_job_parent` → `LearningHistoryStore.open_phased_job`,
   best-effort — a failed write never blocks the dispatch). Opening the parent
   at *start* rather than at close is what makes an abnormal end leave a
   *reapable* parent: `async_initialize` runs `_reap_stranded_phased_jobs` at
   startup, sealing any parent still `"running"` with no live active job as
   `interrupted`. See §4's "Phased Jobs recording" note for what gets written
   onto this parent as each phase finishes.

   Two more start-time seeds run here **for every job, phased or not**:
   `self.active_job.reopen_current_room_noncleaning(...)` opens room one's
   non-cleaning interval (the robot is on the dock right now — undock + transit
   must not be charged to the room), and `self.active_job.seed_counter_baseline(...)`
   records the run's counter floor (`live:PHASE-ATTR-1` — a counter sample only
   lands on a *change*, so without this seed the opening phase/room's first
   increment would be credited to nothing).
9. **Storage write** — saves to `self.data["active_jobs"][vacuum_entity_id][map_id]`.
10. **Phase-watchdog spawn (sequenced runs only)** — if the active job has
    `phases`, sets `_phase_dispatch_pending = True` and spawns
    `_run_advanced_phase(..., phase_index=0, initial=True)` (see §4a). Phase 0
    was already dispatched in step 7, so this initial pass is verify-only — it
    confirms the device actually started room 0 (and releases the guard) before
    the completion gate may finalize. No watchdog for atomic jobs.
11. **Room-started event** — if `current_room_id` is set, fires
    `eufy_vacuum_room_started` (see §9 event table).
12. **Runtime update** — `runtime.active_job_room_ids` is set; room selections
    are cleared via `_clear_room_selections_after_start`.
13. **Learning snapshot** — `save_learning_snapshot_for_active_job` is called.
    The snapshot freezes the queue/payload/active_job state to disk
    non-blockingly (via executor). Failures are caught and logged; they do not
    abort the job.

**Return shapes** (all carry `vacuum_entity_id` + `map_id`):

| Outcome | Shape |
|---|---|
| success | `{started: True, reason: "started", message, warning, warning_message, active_job, learning_snapshot}` |
| blocked (from `get_start_status`) | `{started: False, reason, message, warning}` |
| confirmation required | `{started: False, reason: "confirmation_required", message, warning: True, preflight, confirm_token}` |
| vacuum missing | `{started: False, reason: "vacuum_missing", message}` |

### 2b. `start_run_profile`

`async EufyVacuumManager.start_run_profile(vacuum_entity_id, map_id,
profile_id, ...)` is the saved-run-profile alternative entry point. It is a **thin
delegator** — `manager.start_run_profile(**kwargs)` forwards to
`self.profiles.start_run_profile` (ProfileManager), where the orchestration below
lives. Both the service handler (`services/job_control.py`) and the exposed
run-profile button (`button.py`) call the manager delegator.

1. Calls `apply_run_profile(profile_id)` — loads the saved room list from
   `data["run_profiles"]`, re-enables exactly those rooms, and overwrites their
   settings from the saved snapshot. Returns `applied: False` if the profile ID
   is not found.
2. Calls `build_queue` and `build_room_payload` to rebuild derived state from
   the new room configuration.
3. Delegates to `start_selected_rooms` (all confirmation/blocking logic applies
   identically). Adds `profile_id` and `profile` to the return dict.

### 2c. The `active_job` record (persisted shape)

The `active_job` dict (one per `data["active_jobs"][vacuum][map_id]`) is the
central lifecycle record — written at start, mutated throughout monitoring, and
frozen into the learning snapshot at finalize. `_default_active_job_state`
(`jobs/active_job.py`) seeds it:

```json
{
  "vacuum_entity_id": "vacuum.alfred", "map_id": "6",
  "queue_room_ids": [], "queue_stable_keys": [], "queue_rooms": [ /* QueueRoomSummary */ ],
  "payload": { "map_id": "6", "rooms": [] }, "resolved_rooms": [], "room_count": 0,
  "status": "idle",                          // idle | started | paused | external | completed
  "paused_at": null, "paused_duration_seconds": 0,
  "completed_room_ids": [], "completed_rooms": [],
  "current_room_id": null, "current_room_started_at": null, "current_room_paused_seconds": 0,
  "current_room_noncleaning_seconds": 0,     // wall time the robot spent off the floor
  "current_room_noncleaning_since": null,    // open interval start, null while cleaning
  "observed_mid_job_recharge": false, "observed_mid_job_recharge_started_at": null,
  "observed_mid_job_recharge_count": 0, "recharge_seconds_accumulated": 0,
  "pending_mid_job_recharge_return": false, "pending_mid_job_recharge_return_at": null,
  "observed_mop_wash_count": 0, "observed_mop_wash_last_at": null,
  "observed_mop_wash_cycles": [],            // [{observed_at}]
  "state_transitions": [],                   // cap 12
  "counter_samples": [],                     // cap 2000 (shape in §5)
  "settings_samples": [],                    // external runs only
  "water_estimate": null, "path_block_action": "event_only",
  "pause_timeout_minutes": 0, "has_observed_active_lifecycle": false
}
```

**Enrichment fields** — added *after* the default seed, by their source (§4.6 provenance):

| Added by | Fields |
|---|---|
| Job start (§2a step 8) | `job_id`, `started_at`, `battery_start`, `job_metadata`; **sequenced runs only:** `phases`, `current_phase_index`, `phase_count`, `phased_job_id`, `_phase_dispatch_pending` |
| Job-metrics listener (§5) | `last_cleaning_time_seconds`, `last_cleaning_area_m2`, `last_station_water_percent`, `last_battery_percent` |
| Pose sampler (`started` / `external` runs) | `pose_samples` (cap 3000; shape in §5) |
| Rollover / anomaly | `_native_current_room_id`, `_pending_fast_rollover` (dormant), `_stall_notified_room_ids` / `_skipped_notified_room_ids` (both capped at `max(len(queue_room_ids) + 1, 20)`) |
| Cancel / stranded reaper | `_cancel_in_flight` (also the cancel single-flight latch), `stranded_since` |
| Finalize (§9) | `finalize_claimed_at` (transient exactly-once claim — popped on success/failure, force-cleared at startup by `_clear_orphaned_finalize_claims`), `finalized`, `finalized_at`, `finalize_summary` |

The whole record is persisted to `.storage` on `async_save()`; nothing here is runtime-only.

---

## 3. Active Job Monitoring

### `get_job_progress_snapshot`

`EufyVacuumManager.get_job_progress_snapshot(vacuum_entity_id, map_id,
apply_side_effects=False)` is the main polling endpoint for the card.

**SNAP-2 — a card poll is a pure read by default.** With `apply_side_effects=False`
(every card/dashboard path — direct polls, `get_dashboard_snapshot`,
`get_job_control_state`) step 7 (timing rollover) is skipped and the anomaly
detector's one-shot event firing + dedup-set persistence (step 10) are suppressed —
the anomaly *fields* are still computed fresh so the card can display them, but
calling the snapshot any number of times returns identical output with zero side
effects. The **only** caller that passes `apply_side_effects=True` is
`apply_job_progress_tick` (a thin wrapper), whose only production caller is the
5-second ticker in `listeners/job_progress.py` ([04-listeners §7](04-listeners.md)) —
so the room rollover and the one-shot anomaly events fire on the ticker's cadence,
not on however often a card happens to be polling. Each call:

1. Loads and normalises `active_job` via `_normalize_active_job`.
2. Calls `get_lifecycle_state` for the current lifecycle context.
3. Reads current battery level.
4. **Timeline construction** — if the learning system is available and
   `resolved_rooms` is set:
   - First call: `learning.estimate_from_manager` produces a full
     `room_timeline` (`timeline_source = "estimate"`).
   - After any room completes: `learning.reanchor_timeline` replaces estimates
     with actual completed-room durations (`timeline_source = "reanchored"`).
   - No learning system: `timeline_source = "none"`.
5. **Current room resolution** — reads `active_job["current_room_id"]`. Falls
   back to the first unresolved room if the stored ID is not in
   `unresolved_room_ids`.
6. **Elapsed time** — calls `_compute_current_room_elapsed_minutes` on
   `ActiveJobTracker`: wall-clock elapsed since `current_room_started_at` minus
   two spans that were wall time but not cleaning time —

   - accumulated `current_room_paused_seconds` plus any ongoing pause, and
   - accumulated `current_room_noncleaning_seconds` plus any open
     `current_room_noncleaning_since` interval.

   The second matters because `current_room_started_at` is stamped at
   **dispatch**: without it the undock, the drive out, and any mid-room mop wash
   or recharge trip are all charged to the room, inflating elapsed against the
   timing-rollover threshold until a room that was never finished gets completed.
   The interval is opened and closed by `record_active_job_transition` off the
   vacuum entity's own state, and reopened at every site that stamps a new
   `current_room_started_at` (`reopen_current_room_noncleaning`). The predicate
   is `core/run_state.is_non_cleaning_vacuum_state`, which **fails open**: an
   unreadable state subtracts nothing rather than subtracting unboundedly and
   stalling the room.
7. **Timing rollover** — **only when `apply_side_effects=True`** (a plain read
   reflects whatever the last tick already persisted) — delegates to
   `active_job._maybe_roll_current_room_by_timing` (the manager's `active_job`
   attribute is the `ActiveJobTracker`; method defined at
   `jobs/active_job.py`, reached via the `manager.py` delegator). See §4.
8. **Current-phase derivation (RP-047a)** — resolves the current phase
   (`phases[current_phase_index]`) and derives **`current_room_ids`**: every
   room id in that phase's own `resolved_rooms` (the same source
   `advance_active_job_phase` swaps), deduped, in encounter order. An atomic
   run, or a phase with no resolved rooms (a break), falls back to
   `[current_room_id]` (or `[]` with none). This is **not** a "the phase has no
   per-room rollover" workaround — §4 below shows a `room_group` phase's rooms
   *do* roll individually via the counter/timing paths — `current_room_ids` exists
   so the group-level anomaly and bounds-exit math (steps 9–10) can sum a
   threshold over the whole dispatched group rather than judging it against a
   single room's estimate. Also exposed as **`current_phase`** =
   `{index, phase_type, room_ids, is_group}` (`is_group` = `len(current_room_ids) > 1`;
   `None` for an atomic run). A follow-up (RP-047b) tried marking *every* room in
   `current_room_ids` as the card's "current" room, on the premise that a group
   phase never rolls per-room — a live run disproved that premise (completions
   were firing inside the group) and the change was reverted; the card still
   reads the single `current_room_id`/`current` flag per room, `current_room_ids`
   is consumed only for the threshold sums below.
9. **Bounds-exit detection** (`awaiting_bounds_exit`) — the threshold is the
   **sum over `current_room_ids`** of each member's timing-completion threshold
   (a single-room threshold would engage almost immediately on a multi-room group
   and hold for the whole phase), and the flag is **forced `False` for
   path-optimizing brands** (`adapter_honors_clean_order(...)` is `False` — timing
   order is meaningless there).
10. **Anomaly detection** — `stall` (hard), `running_long` (soft), and
    `skipped` (conservative). See below.

### `awaiting_bounds_exit` logic

After the timing rollover attempt, if the room did *not* roll (i.e.
`current_room_id` is unchanged), the snapshot checks whether elapsed time has
passed the timing completion threshold summed over `current_room_ids` (step 9
above — a single-room member sum reduces to the plain per-room threshold, so an
atomic run is unaffected). If so, `awaiting_bounds_exit = True`. This signals the
card to switch to a short poll interval (~5 s) because the robot is still
physically inside the room/group and the rollover gate is blocked by bounds.
Forced `False` outright for a path-optimizing brand (`adapter_honors_clean_order`
is `False`), since timing order is meaningless there.

### Anomaly detection

The three disjoint anomaly tiers (and the one-shot `EVENT_STALL_DETECTED` /
`EVENT_ROOM_SKIPPED` emission) are computed by
`ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py`), which
`get_job_progress_snapshot` calls with `emit=apply_side_effects` (`manager.py`)
and whose returned fields it merges into the snapshot — the fields are always
computed; the event fire + dedup-set persistence happen only when `emit=True`
(the 5s ticker, SNAP-2 above). **All three tiers are additionally gated on
`adapter_honors_clean_order`** — a path-optimizing brand (Roborock) reports no
anomalies from this heuristic at all; `detect_run_anomalies` receives
`current_room_ids` and uses it the same way the bounds-exit check does: the stall
threshold sums `_timing_completion_threshold_minutes` over every id in
`current_room_ids` (members with no timeline entry contribute nothing, which
keeps the sum conservative rather than inventing a default). Both ratios are read
from the adapter's `anomaly` block (`running_long_ratio`, `stall_ratio`), each
falling back to the Eufy default if absent. The `_STALL_RATIO` /
`_RUNNING_LONG_RATIO` locals live inside `detect_run_anomalies` (`active_job.py`),
not in the snapshot composer.

```
_STALL_RATIO        = anomaly.stall_ratio        or 2.0
_RUNNING_LONG_RATIO = anomaly.running_long_ratio  or 1.5
```

**Stall (hard).** Gated on `_honors_clean_order` (no-op for a path-optimizing
brand). A stall is detected when:
- `awaiting_bounds_exit` is already `True` (timing threshold exceeded), **and**
- `current_room_elapsed_minutes >= threshold * _STALL_RATIO` (≥2× by default),
  where `threshold` is the **sum of `_timing_completion_threshold_minutes` over
  `current_room_ids`** (step 8 above) — on a single-room dispatch this is just
  that room's own threshold; on a multi-room `room_group` phase it is the
  group's combined estimate, so the bar reflects the work actually dispatched
  rather than firing at ~1× on the group's first member alone. A member with no
  timeline entry contributes nothing (conservative: an under-counted threshold
  can still stall, an invented one cannot be reasoned about).

`EVENT_STALL_DETECTED` fires at most once per room per job (only from the
tick, `emit=True` — SNAP-2). Already-notified rooms are tracked in
`active_job["_stall_notified_room_ids"]` (capped at
`max(len(queue_room_ids) + 1, 20)`, oldest dropped) — owned and written back
to storage by the tracker (`active_job.py`). Subsequent calls suppress the
event for those rooms.

**Running-long (soft).** The tier *below* the stall band — set when the room is
genuinely overrunning but not yet stalled, and there is no pending live
transition (so it is overrunning *in* the room, not a missed roll). Unlike
stall/bounds-exit, this tier's threshold is **per the single `current_room_id`
only** (`_rl_entry`/`_rl_threshold`), not summed over `current_room_ids`.
Conditions:
- not already stalled, status `started`, valid `current_room_id`, **and**
- the room is not **unlearned** (issue #40): a timeline entry with
  `source == "default"` and `sample_count <= 0` is excluded — an unlearned
  room falls back to the ~6-minute default estimate, so any normal new-setup
  room would trip the 1.5× band on its very first run with no real baseline to
  judge against (stall needs no such gate — it is already bounds-gated), **and**
- no pending counter transition
  (`active_job._live_boundary_count(...) <= len(completed_room_ids)`), **and**
- `_RUNNING_LONG_RATIO * threshold <= current_room_elapsed_minutes < _STALL_RATIO * threshold`
  (1.5×–2× by default — a half-open band disjoint from stall).

Running-long is **snapshot-only — it fires no event, and is always computed**
regardless of `apply_side_effects` (SNAP-2 only gates stall/skipped's one-shot
emission, not this tier). It surfaces only on the returned snapshot
(`running_long`, `running_long_room_id`, `running_long_ratio`, and per-room
`running_long` on the current timeline entry) so the card can draw a warning
ring on the chip.

**Skipped (conservative).** `skipped_room_ids` = queued rooms strictly *before*
`current_room_id` in queue order that are not in `completed_room_ids`. Because
Eufy's sequential counter rollover keeps `completed_room_ids` a prefix of the
queue, this is **~always empty for Eufy** — a mid-run skip can't be attributed
from the counters, so the reliable "missed rooms" signal stays the post-run
`incomplete_run_log` (§8). The hook fires only on a genuinely non-sequential
advance (position-reliable brands / transition detection); there is no
false-positive heuristic. When new skips appear, `EVENT_ROOM_SKIPPED` fires once
per room (only from the tick, `emit=True`; deduped via
`active_job["_skipped_notified_room_ids"]`, same `max(len(queue_room_ids) + 1, 20)`
cap as the stall set), and the skipped rooms are flagged per-entry on the
timeline (`skipped`) and excluded from `remaining_room_ids`.

### `has_observed_active_lifecycle`

Set to `True` the first time the lifecycle listener observes a state that
indicates the robot is actively cleaning (not at the dock). This flag is the
mandatory pre-condition for auto-finalization. Without it, a stale pre-run dock
state (e.g. `dock_drying`) could complete the job before it actually started.

---

## 4. Room Transitions

### What triggers `room_started` / `room_finished`

`EVENT_ROOM_STARTED` fires in two situations:
- At job start (`source: "job_start"`), when `current_room_id` is non-null.
- After each rollover, for the *next* room. The `source` carries the rollover
  path: `"counter_plateau"`, `"timing_rollover"`, `"bounds_exit_early"` (dormant —
  producer removed with the mapping split), or
  `"native_signal"` (brands on the native current-room path, e.g. Roborock).

`EVENT_ROOM_FINISHED` fires from `_maybe_roll_current_room_by_timing` (via
`_apply_room_rollover`, or via `_set_native_current_room` on the native path)
after rollover, carrying the same `source` values.
Within a single dispatch there is no HA-entity-state-driven *room* transition
mechanism — room rollover is driven by the live counter signal and timing, or
by the device's native live current-room signal for brands that declare it.

**Job model / phase transitions.** The above describes an `atomic_batch`
job — one dispatch over a fixed room set, the model a job uses by default.
The dispatch engine (`queue/dispatch_engines.py`) may instead declare
`job_model = "sequenced"`, where one logical job is an ordered list of
phases (e.g. sweep-all → mop-all), each its own dispatch.
`engine.build_phases()` produces the sequence; at the completion hook
`manager.maybe_advance_phase` swaps to the next phase
(`advance_active_job_phase`) and re-dispatches instead of finalizing — each
**clean** phase finalizes as its own child `completed_job` record (Phased Jobs
wave 1, below), separately from the whole-run lifecycle finalize
(`mark_active_job_finalized` / `EVENT_JOB_FINISHED`), which fires once, on the
atomic job or the sequenced run's *final* phase (§6a).

No engine declares `job_model = "sequenced"` at the *class* level, but
sequenced runs are nonetheless produced **per-run** by the strict-order
opt-in. `GenericRoomIdsEngine.build_phases(strict_order=True)` (and its
`RoborockSegmentEngine` subclass) emits **one single-segment phase per
resolved room** in queue order instead of one batch the device would
re-route (`dispatch_engines.py`). This is gated on
`capabilities.honors_clean_order = False` — i.e. only path-optimizing
brands that ignore the dispatched order (Roborock, Ecovacs) take this
path; order-honoring brands (Eufy) never sequence. When the resulting plan
holds more than one phase, the framework attaches the sequence to the
active job and runs it as a sequenced job: `maybe_advance_phase` advances +
re-dispatches at each completion (`PhaseRunner.maybe_advance_phase`,
`jobs/phase_runner.py`, reached via the `manager.py` delegator; the
advance step itself is `advance_active_job_phase` in
`queue/queue_engine.py`; the per-run phase build is
`planning/run_plan.py`; the completion-hook call is `lifecycle.py`), and each
clean phase finalizes as its own child record the same way. The advance/finalize
machinery is wired into both the start and completion paths (`maybe_advance_phase`
runs in the completion hook, see §6a; the start-side spawn and per-phase watchdog
are in §2a and §4a). See [07-queue-engine.md](07-queue-engine.md) and
[22-adapter-config-reference.md](22-adapter-config-reference.md) §13.

**Phased Jobs recording (wave 1).** A phased run's parent record (opened at
start, §2a) is what makes the per-phase child records below addressable.
Immediately before each advance — inside `PhaseRunner.maybe_advance_phase`,
*after* `_capture_finishing_phase_timing` (it reads the `_timing_end_t` the
capture just stamped) and *before* `advance_active_job_phase` (which moves
`current_phase_index`) — `_record_phase_to_parent` (`jobs/phase_runner.py`)
attaches the finishing phase to the parent, best-effort (a failed write never
blocks the next phase's dispatch):
- A **clean** phase (`room_group` or `zone`) is finalized as its own child
  `completed_job` record under `{job_id}.phase{N}` via `_finalize_phase_as_child`
  — a copy of the active-job state narrowed to that one phase (so the finalizer's
  cross-phase sums don't leak an earlier phase's seconds into this child), run
  through the same `LearningJobFinalizer` the whole-run finalize uses but
  **outside** the run-level exactly-once claim (that claim guards the *run*;
  a per-phase call through it would mark the whole run finalized at phase 0).
  Idempotent via the phase's own `_child_record_id`. The saved child is stamped
  with `phase_key = {phased_job_id, phase_index, phase_type}`.
- A **break** phase (`charge_wait` / `wait`) gets a `phase_break` record instead
  (planned hold/target-battery vs. actual elapsed) via `_break_record_payload` —
  never the `completed_job` schema, so a planned dock is never taught as
  cleaning time.
- Either way, `record_phase_outcome` (`learning/history_store.py`) appends the
  phase's outcome + record id onto the parent (a read-modify-write; the parent
  is a cache over its children, never a recomputed number).

See [30-phase-runner §4a](30-phase-runner.md#4a-phased-jobs-recording--attaching-finishing-phases-to-the-parent-wave-1)
for the full per-phase recording mechanics, and §2a above for where the parent
itself is opened / reaped.

**Phase record + non-room phase types.** A `phases` entry is a dict tagged by
`phase_type`; a clean phase also carries the same room fields an atomic job has.
The four types:

| `phase_type` | Driver | Key fields |
|---|---|---|
| `room_group` (clean) | dispatch watchdog `_run_advanced_phase` (§4a) | `resolved_rooms`, `payload`, `room_count`, `queue_room_ids`, `queue_rooms`; runtime: `room_timing`, `_timing_end_t` |
| `charge_wait` | `_run_charge_wait_phase` — dock, poll battery to target | `target_battery_percent` (default 100); runtime: `charge_from_battery`, `charge_started_at`, `charge_to_battery`, `charge_ended_at` |
| `wait` | `_run_wait_phase` — dock, hold | `wait_minutes` (default 5); runtime: `wait_started_at`, `wait_ended_at` |
| `zone` | zone dispatch | `zone_timing` |

The job carries `phases`, `current_phase_index`, and `phase_count`.
`advance_active_job_phase` (`queue/queue_engine.py`) swaps
`resolved_rooms` / `payload` / `room_count` / `queue_*` to the next phase and resets
per-phase progress (`completed_room_ids`, `current_room_id`, timing); it returns
`None` for an atomic job or the final phase (the caller then finalizes). The
`charge_wait` / `wait` phases run an **in-memory asyncio poller** guarded against a
double-spawn by `_dock_poller_active` (keyed `(vacuum, map, phase_index)`) and
**re-armed** after a pause/resume or HA restart via `rearm_dock_phase_if_needed`.
See [30-phase-runner.md](30-phase-runner.md) for the full driver internals.

### 4a. Strict-order phase watchdog (`_run_advanced_phase`)

A sequenced strict-order run can't simply re-dispatch the next room at the
completion hook: a path-optimizing device (Roborock S6) returns to the dock
and starts charging at the end of each single-room phase, and **ignores an
`app_segment_clean` sent at that instant**. The per-phase watchdog lives on
the dedicated `PhaseRunner` subsystem
(`PhaseRunner._run_advanced_phase`, `jobs/phase_runner.py`) and wraps
each phase in a settle → dispatch → verify → retry loop. The manager keeps
only the initial-phase spawn (`self.phase_runner._run_advanced_phase`,
`manager.py`) and a thin `maybe_advance_phase` delegator
(`manager.py`).

- **Initial phase (`initial=True`).** Phase 0 was already dispatched by
  `start_selected_rooms`, so the watchdog skips the settle and the first
  send and only **verifies** that the device actually started — a retry
  re-dispatches only if the initial send was ignored.
- **Advanced phases.** The watchdog **settles** before dispatching. The
  settle is extended when the phase's target room *is* the dock room
  (`_phase_target_is_dock_room` → `dock_settle_seconds`), because a robot
  parked + charging on its target has the longest post-dock ignore-transient.
  It then **dispatches**, **verifies** via `PhaseRunner._await_phase_started`
  (`jobs/phase_runner.py`) that the device actually started *and sustained*
  this room — polling `confirm_seconds` of cumulative cleaning-the-target
  (a brief dip just doesn't add to the tally; a small room that finishes
  under `confirm_seconds` is weak-confirmed on idle-exit rather than
  re-dispatched), and **retries** up to `max_attempts`. After the cap the
  run is left stalled (recoverable via Cancel Run) rather than silently
  re-dispatched forever.

**Dispatch-pending guard.** While the watchdog is in its settle/dispatch/
verify window, `active_job["_phase_dispatch_pending"]` is `True`; it clears
(`_clear_phase_dispatch_pending`) only once the device is confirmed cleaning
the phase's room. This blocks the completion gate from finalizing a
just-advanced phase on the lingering dock/charging signal of the room that
just finished (see §6a).

**Timing (adapter-declarable).** The watchdog timing is resolved by
`_phase_timing` (`manager.py`, which stays on the manager): the
adapter's `dispatch.phase_timing` block merged over the `_PHASE_*` module
defaults (`manager.py`) — settle 10 s, dock-settle 45 s, verify 90 s, confirm
45 s, poll 5 s, max-attempts 3. Any key a brand omits falls back to the
default. The Roborock adapter overrides **`confirm_seconds` to 15 s**
(`adapters/roborock/adapter.py`); all other keys match the defaults.

**Cancel.** `async_cancel_active_job` sets `active_job["_cancel_in_flight"]`
up front — *before* the status flips — so the watchdog bails before it can
re-dispatch during the return-to-base window.

### Timing rollover (`_maybe_roll_current_room_by_timing`)

Defined in `ActiveJobTracker` (`jobs/active_job.py`). Called from
`get_job_progress_snapshot`. Every counter/timing rollover funnels through the
shared `_apply_room_rollover(...)` helper, which records the completed room and
fires the `EVENT_ROOM_FINISHED` / `EVENT_ROOM_STARTED` pair with a `source` tag
distinguishing the path. There are **four rollover sources**.

**A phased job is NOT categorically excluded from rollover.** An earlier build
opened this method with a blanket `if active_job.get("phases"): return active_job`,
which disabled all four sources for every phased job. That guard's own premise —
"a sequenced job advances one room per dispatched *phase*" — is true for a
native-signal brand (Roborock, one room per phase by construction) but **false**
for Eufy: `EufyRoomCleanEngine` ignores `strict_order` and a `room_group` phase can
hold **N** rooms in one dispatch, so the guard was the sole reason rooms never
advanced inside an Eufy group (fixed by commit `40cbaac`, "rooms must advance
inside a group"). The guard now lives **only inside the native-signal branch**
below — it blocks rollover for a phased job **only when
`live_transition.native_transition_source` is truthy** (Roborock); it does not
run at all for Eufy. For an **atomic** job, or a **phased job on a
non-native-transition-source brand**, the native-signal path is skipped and the
remaining three counter/timing paths apply *scoped to the current phase's own
`resolved_rooms` / counter slice* exactly as they would for a single-room atomic
job — a room_group phase's rooms roll one at a time as their own
`completed_room` events fire. Checked in this order:

**Native-signal path (device's live current room, checked first):**
1. For adapters that declare `live_transition.native_transition_source=True`
   (Roborock), `_maybe_roll_current_room_by_timing` short-circuits to
   `_maybe_roll_current_room_by_native_signal` (`active_job.py`) — checked
   **before** the `current_room_id is None` guard and the three counter/timing
   sources (`active_job.py`). Inside this branch only, a phased job
   (`active_job.get("phases")` truthy) returns immediately without rolling —
   this is where the phases guard now lives (the 0.55-minute phantom
   completion it exists to prevent — a Roborock docked in the target room's
   name, adopted as current before it was ever cleaned — is a native-branch-only
   failure; counter/timing rollover can't reproduce it).
2. Rollover **follows** the device's native live current-room signal (filtered to
   job targets, matched by name slug, **order-agnostic**) rather than the
   sequential counter/timing heuristic.
3. It completes/advances rooms directly from the native signal and fires
   `EVENT_ROOM_FINISHED` / `EVENT_ROOM_STARTED` with `source="native_signal"`
   through `_set_native_current_room` (`active_job.py`, `1227`, `1250`). The
   native `EVENT_ROOM_FINISHED` payload does **not** carry `confidence`.
4. The three counter/timing sources below apply only when
   `native_transition_source` is `False` (Eufy default).

**Counter-plateau path (live boundary, checked first):**
1. Before any timing math, the tracker asks `_live_boundary_count(...)` how many
   *completed* room transitions the live cleaning-counter stream currently
   shows. If that exceeds `len(completed_room_ids)`, roll **now** — ahead of the
   timing threshold (`source="counter_plateau"`).
2. This signal is high-confidence and frame-invariant (counters, no geometry).
   The in-progress room is never counted — `expected_rooms` caps detected
   boundaries at N-1 — so this can never roll the *final* room.
3. `_live_boundary_count` is transit-aware and adapter-tunable (see below).

**Slow-room path (timing has expired):**
1. Requires `active_job["status"] == "started"` and a valid `current_room_id`.
2. Elapsed >= `_timing_completion_threshold_minutes(current_room)`.
3. Rollover is **timing-only** — when the threshold is reached, the room advances.
   (The old learned-bounds veto, which held rollover until the robot left the room's
   bounding box, was removed with the mapping split: it rode the device's per-session
   coordinate frame and drifted, and both adapters shipped `position_lock_reliable=False`,
   so it was gated off in production anyway.)
5. On rollover: `source="timing_rollover"`.

**Fast-room path (early bounds exit) — dormant.** The finalize reader below is
retained, but its **producer was removed with the mapping split**: the mapping
tracker no longer sets `_pending_fast_rollover` (`MappingTracker._signal_fast_rollover`
is gone), so `source="bounds_exit_early"` no longer fires in current builds. Kept
here as the dormant design — the reader is a no-op until a producer is restored.
1. Elapsed < `_timing_completion_threshold_minutes` but >=
   `_MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER` (1.5 min / 90 s).
2. The mapping tracker's confidence model *would* signal via
   `_pending_fast_rollover` on the active job that the robot finished and left
   (producer removed — see above).
3. Signal is consumed (popped from `active_job`) on use so it cannot trigger twice.
4. Fires `EVENT_ROOM_FINISHED` with `source="bounds_exit_early"`.

The 90-second floor on the fast path prevents doorway transits from triggering
a false rollover on the next snapshot poll.

### Live boundary count (`_live_boundary_count`) — the counter-plateau source

`_live_boundary_count(vacuum_entity_id, active_job, raw_timeline)` returns how
many *completed* room transitions the live counter-sample stream
(`active_job["counter_samples"]`, buffered by `record_counter_sample` on every
`cleaning_time` / `cleaning_area` change) currently exposes. It is the same
counter-segmentation machinery the finalizer uses, run live each tick — but
**transit-aware**, where the legacy live path was not.

Detection routes through the **pluggable job-segmenter engine**
(`learning/job_segmenter_engines.py` — the *counter/run* segmenter, distinct
from the *map* segmenter in `mapping/segmenter_engines.py`). It resolves the
engine from the adapter's `job_segmenter.engine` (`get_job_segmenter_engine`);
an absent/unknown name falls back to the Eufy engine (`eufy_counter_v1`), so
the legacy no-adapter path stays byte-identical — this is a *dispatch-style*
fallback, **not** the map seam's noop. `select_active` stays a direct framework
import (`counter_segmentation.select_active`) — it is brand-agnostic ranking
over the candidate shape and is not on the engine.

Two adapter blocks shape the result, and they are now **separate concerns**:

- **`job_segmenter.tuning`** is the single source of the gap/area/cadence
  thresholds (`gap_delayed_s`, `gap_transit_s`, `gap_plateau_s`, `area_jump_m2`,
  `cadence_s`). `_live_boundary_count` reads them from `job_segmenter` and
  passes them as the engine's `tuning`; the Eufy engine merges a partial/`None`
  tuning over its own `DEFAULT_TUNING` (defined *by reference* to the
  `counter_segmentation` module constants, so it can't drift).
- **`live_transition`** is now **orchestration-only**: `enabled`,
  `rollover_kinds`, and `native_transition_source` (an active orchestration flag:
  when truthy — Roborock, `adapters/roborock/adapter.py` — current-room
  rollover routes to `_maybe_roll_current_room_by_native_signal` and follows the
  brand's native live-room signal instead of this counter/timing path; Eufy
  leaves it `False`, `adapters/eufy/adapter.py`, keeping the path below
  unchanged — see §4). `_live_transition_config(vacuum_entity_id)` merges this block
  over `_LIVE_TRANSITION_DEFAULTS`, which **no longer carries the five
  threshold keys** — they moved to `job_segmenter.tuning`. An adapter with no
  `live_transition` block behaves as before — **except** it now also rolls on a
  `transit` boundary:

- **`enabled: False`** is a kill-switch — it falls back to the engine's
  legacy one-shot composition `engine.segment_legacy(...)` (wash/area_jump only;
  delegates verbatim to the byte-identical `segment_counters` wrapper) and
  returns `len(segments) - 1`.
- **`enabled: True`** (the default) calls `engine.find_candidates(...)` →
  framework `select_active(...)` with the tuned thresholds and `rollover_kinds`,
  and returns `len(active)`.

The key change is the `transit` kind: a **60–90 s flat-area inter-room hop** —
the robot crossing into the next room without a wash-station detour or a forward
area jump. The legacy live path discarded this case, so on a back-to-back room
pair with no wash between them the live tracker under-rolled and only caught up
at the timing threshold. The default `rollover_kinds` is therefore
`("wash_plateau", "transit", "area_jump")`. Brands tune the gap bands
per-firmware via `job_segmenter.tuning` and the matched kinds via
`live_transition.rollover_kinds`.

> The finalize/history segmentation path is **byte-identical** — it now also
> routes through the engine (`engine.segment_legacy`, which delegates verbatim
> to the `segment_counters` back-compat wrapper). Only the *live* current-room
> rollover gained transit-awareness. See
> [22-adapter-config-reference.md](22-adapter-config-reference.md) for the
> `job_segmenter`, `live_transition`, and `anomaly` adapter blocks.

### Timing completion threshold formula

`_timing_completion_threshold_minutes(room)` in `ActiveJobTracker`:

```
threshold = estimated_minutes + slack_minutes

overrun_ratio:
  0.06  if confidence_score >= 0.85
  0.10  if confidence_score >= 0.65
  0.15  if confidence_score >= 0.45
  0.22  otherwise

slack_minutes = max(0.75, estimated_minutes * overrun_ratio)
              + 1.0  if sample_count <= 1
              + 0.5  if sample_count <= 3
              + min(estimated_minutes * drift_ratio * 0.25, 1.5) if drift_ratio > 0

slack_minutes is capped at max(4.0, estimated_minutes * 0.35)
```

The stall threshold is `_STALL_RATIO × _timing_completion_threshold_minutes`
(adapter-tunable via `anomaly.stall_ratio`, default `2.0` — see Anomaly
detection above), summed over `current_room_ids` on a multi-room phase.

### `reanchor_learning_timeline`

`learning.reanchor_timeline(original_estimate, completed_rooms, ...)` takes the
original pre-job estimate and a list of `{room_id, actual_duration_minutes}`
entries for completed rooms, replaces estimated durations with actuals, then
recalculates all downstream ETAs and battery projections from the reanchor
point. Called from `get_job_progress_snapshot` on every snapshot call after any
room completes.

---

## 5. Mid-job Observations

The lifecycle listener in `__init__.py` fires callbacks on state changes during
a job. `ActiveJobTracker` mutates `data["active_jobs"]` directly for these
observations:

### Recharge observation (`update_active_job_recharge_observation`)

Fired when the vacuum's task status indicates a low-battery return. **Skipped
entirely when the current phase is a commanded `charge_wait` / `wait` break** — a
planned dock must not be logged as an unplanned battery recharge (that would also
pause the mapping sampler and double-count the dock). Otherwise, two-stage
detection:
1. `pending_mid_job_recharge_return = True` when `_is_low_battery_return_state`
   fires.
2. On the next observation where `_is_charging()` is `True`:
   `observed_mid_job_recharge = True`, `observed_mid_job_recharge_count` incremented,
   `pending` flags cleared. Mapping tracker `pause_sampling` is called.
3. When charging ends (not charging while `observed_mid_job_recharge = True`):
   accumulate `recharge_seconds_accumulated`, clear flag, call
   `tracker.resume_sampling`.

### Mop wash observation (`update_active_job_mop_wash_observation`)

Debounced by the adapter's `dock_events.debounce_seconds["last_mop_wash"]`
(60 s for Eufy; `0`/absent = no debounce). Each confirmed wash event
increments `observed_mop_wash_count`, appends to `observed_mop_wash_cycles`
(capped at 50), and updates `observed_mop_wash_last_at`.

### State transition recording (`record_active_job_transition`)

The listener appends every relevant entity state change to
`active_job["state_transitions"]` (capped at 12 entries). Used by the
finalization cancel-detection heuristic.

### Sensor value recording (`record_active_job_sensor_value`)

Called from the job-metrics listener whenever tracked sensors
(`cleaning_time_seconds`, `cleaning_area_m2`, etc.) change. Each reading is
**normalized to canonical units at capture** by the listener before it is
recorded: `cleaning_area` → m² by the sensor's own `unit_of_measurement`
(`learning/utils.cleaning_area_to_m2`; an imperial HA presents Eufy's sensor in
ft² and Roborock's in m², so a bare read would silently mix units and inflate
Eufy area ~10.76×), and `cleaning_time` → seconds by unit (Roborock reports bare
minutes — previously stored 60× too low). The unit is re-read live, so a unit
toggle in the app or HA is handled per-tick. Writes directly to all in-flight
active jobs for the vacuum. Finalization reads from `active_job` instead of
issuing a live HA state read at job-end, avoiding the DPS timing race.

The listener writes the last-seen values onto each active job under **`last_*`-prefixed
keys**: `last_cleaning_time_seconds` (int), `last_cleaning_area_m2` (float),
`last_station_water_percent` (float), and `last_battery_percent` (int). On a
`cleaning_time` / `cleaning_area` change it also appends one **counter sample** —
`{t, cleaning_time, cleaning_area, battery}` — to `active_job["counter_samples"]`
(cap `_MAX_COUNTER_SAMPLES = 2000`, oldest dropped on overflow), feeding
counter-plateau segmentation. Separately, the pose sampler ([04-listeners](04-listeners.md) §10)
appends **pose samples** — `{t, current_room, anchor, cleaning_area, heading}` — to
`active_job["pose_samples"]` (cap `_MAX_POSE_SAMPLES = 3000`) on `started` and
`external` runs, for room attribution (§7 reconcile).

---

## 6. Job End Paths

### 6a. Normal completion

**Trigger:** The lifecycle listener observes `task_status == "completed"` AND
`active_cleaning_target` is cleared, while
`active_job["has_observed_active_lifecycle"] == True`.

**Code path:** the state-change handler → `_process()` in
`listeners/lifecycle.py` (registered via `lifecycle.register(hass)` from
`__init__.py`).

The base completion condition (`lifecycle.py`) is **adapter-driven,
not a hardcoded sentinel set**: it requires `task_status` to equal the
adapter's `completion.task_status_value`, the secondary signals to be
satisfied via `completion_secondary_satisfied` (which consults
`completion.secondary_clear_sentinels` and `completion.require_job_active_clear`),
and `has_observed_active_lifecycle == True`. Three further guards then run *on
top of* that base condition before finalization can proceed:

- **Recharge-resume guard.** A brand may dock and report
  `task_status=charging` *mid*-job to recharge, then resume. When the adapter
  declares a job-active signal (`entities.job_active` — a binary sensor that
  stays on through the recharge dock and clears only at the true finish),
  `is_job_active(..., unavailable_is_active=True)` suppresses finalization
  while it is on, so the resumed half stays the same job. No-op for brands
  without `entities.job_active` (e.g. Eufy).
- **Strict-order dispatch guard.** A just-advanced sequenced phase has not
  been confirmed cleaning yet — the watchdog (`_run_advanced_phase`, §4a) is
  still in its settle/dispatch/verify window. While
  `active_job["_phase_dispatch_pending"]` is set, the lingering completion
  signals from the room that *just* finished (a Roborock sits docked +
  charging between phases — precisely its completion signal) must not finalize
  the new phase. No-op for non-sequenced jobs (the flag is only set on a phase
  advance / the initial sequenced spawn).
- **Cancel-in-flight guard.** If `active_job["_cancel_in_flight"]` is set, the
  cancel path (§6b) owns finalization for this job — its own return-to-base
  dock can otherwise read as completion here, which would race the cancel's
  own finalize. `_cancel_in_flight` is released before the cancel's terminal
  confirm poll completes, by design, so this guard is what keeps the two paths
  from colliding in that window.

When all four pass, it first calls `manager.maybe_advance_phase` — for a
**sequenced** job this advances to the next phase + re-dispatches instead of
finalizing (see §4). Otherwise it calls `finalize_learning_for_active_job` and
branches on `finalize_result_succeeded(finalize_result)` (RP-002/RF-01 — a
refusal dict `{"finalized": False, "reason": ...}` is also not `None`, so the
branch cannot be `finalize_result is not None`):
- **Succeeded** → `mark_active_job_finalized` → fires `EVENT_JOB_FINISHED` with
  `job_finished_event_data()` → if the completed job had a mop room and the
  adapter allows it (`post_job_wash_amendment.enabled`, default `True`):
  `register_post_job_water_amendment()` with the adapter's `debounce_seconds`
  (default 60) / `timeout_seconds` (default 180).
- **Raised** (the finalize call itself threw) → `mark_active_job_finalized(...,
  finalize_result=None)` still runs, so the active-job slot and the mapping
  tracker's hold can never strand — but no event fires and no summary is
  fabricated.
- **Refused** (`missing_started_at` from `finalize_learning_for_active_job`
  itself, §7; or `already_finalized` / `finalize_in_flight` / `no_active_job_record`
  from the exactly-once claim inside `async_finalize_completed_job`, §7) →
  nothing further runs here; the entrant that actually succeeded (earlier, or
  concurrently) owns the terminal steps.

### 6b. Manual cancel (service call)

**Trigger:** `eufy_vacuum.cancel_active_job` service.

**Code path:** `async_cancel_active_job` → `vacuum.return_to_base` (blocking)
→ polls every 2 s for up to 30 s (`_CANCEL_CONFIRM_TIMEOUT_S`) for
`vacuum_state in {"docked", "idle"}` or `task_status in {"completed", "complete"}`.
If not confirmed within 30 s, finalizes anyway with a warning. Calls
`finalize_learning_for_active_job` with `forced_outcome_status="cancelled"` and
`forced_lifecycle_state="job_cancelled"`, then `mark_active_job_finalized`. The
service handler (`services/job_control.py`) fires `EVENT_JOB_FINISHED`, plus
`EVENT_RUN_INCOMPLETE` when the cancel stranded rooms (§8).

### 6c. Pause timeout

**Trigger:** A paused job whose `pause_timeout_minutes > 0` has been paused
beyond the configured limit.

**Code path:** `listeners/pause_timeout.py` (`pause_timeout.register(hass)`)
sets a 1-minute `async_track_time_interval` tick (ticks never overlap; this is
one of the reaper's **two** independent per-slot reaps, the other being §6f —
see [04-listeners §6](04-listeners.md)). On each tick,
`get_paused_job_timeout_report` is called for each known job. If it returns a
report (`forced_lifecycle_state="pause_timeout_cancelled"`,
`cancel_reason="pause_timeout"`), `async_cancel_active_job` is called with
those values; only when it reports `cancelled` does the tick fire
`EVENT_JOB_FINISHED`, plus `EVENT_RUN_INCOMPLETE` when the auto-cancel stranded
rooms (§8).

### 6d. Path blocker cancel

**Trigger:** A watched entity whose state matches a blocker rule changes while
`path_block_action == "cancel_and_event"`.

**Code path:** `listeners/path_blockers.py` (`path_blockers.register(hass)`)
watches all rule entities (dropout-sentinel transitions ignored, single-flight
per burst — see [04-listeners §5](04-listeners.md) for both). On state change,
`get_runtime_path_block_report` re-evaluates rules. Behaviour by
`path_block_action`:
- `"event_only"` — fires `EVENT_PATH_BLOCKED` only.
- `"pause_and_event"` — `async_pause_active_job` + `EVENT_PATH_BLOCKED`.
- `"cancel_and_event"` — re-checks the triggering rule still matches with a
  known state immediately before the irreversible cancel ([04-listeners §5](04-listeners.md));
  if it no longer does, the cancel is suppressed
  (`action_taken: "cancel_suppressed_recheck"`) and only `EVENT_PATH_BLOCKED`
  fires. Otherwise `async_cancel_active_job` + `EVENT_JOB_FINISHED` +
  `EVENT_PATH_BLOCKED`, **plus `EVENT_RUN_INCOMPLETE` when the cancel stranded
  rooms** (a rule-driven cancel is involuntary; §8).

### 6e. Cancel detection heuristic (automatic)

During finalization, `_detect_cancel_likely_run` is called when
`forced_outcome_status` is `None`. It examines `state_transitions`.

**Conditions for `cancel_likely=True`** (single-room jobs only):
1. Transition history contains `cleaning → returning` or `paused → returning`
   via `task_status`.
2. No stronger service state in transitions (e.g. `"returning to charge"`,
   `"washing mop"`, `"emptying dust"`).
3. **Either** the absolute floor — `actual_cleaning_minutes < 1.5`
   (`_MIN_FLOOR_MINUTES`; `actual_cleaning_minutes` is the time to the `returning`
   transition, pause-adjusted) — **or** the relative gate — the whole-job
   `duration_minutes < short_threshold`, where
   `short_threshold = max(min(expected_room_minutes × 0.4, expected_room_minutes), 0.75)`,
   forced to `1.0` when there is no estimate (`expected_room_minutes <= 0`). The
   relative gate compares **job `duration_minutes`**, not `actual_cleaning_minutes`,
   and never drops below the `0.75` floor (`1.0` with no estimate).

When detected, `outcome_status` is overridden to `"cancelled"` with
`lifecycle_name = "cancel_likely"`.

### 6f. Stranded dispatched-run reaper (automatic)

**Trigger:** A dispatched run left at `status == "started"` that ended *without*
ever hitting its brand's completion terminal — power loss, an HA restart mid-run,
a stuck-then-docked run, or an app-cancel that never emitted the terminal status.
Left alone it strands as `started`: no record, it masks a later external run, and
a later terminal signal can be mis-attributed to it.

**Code path:** the same 1-minute `listeners/pause_timeout.py` tick that drives the
pause-timeout reaper also calls `manager.poll_stranded_started_job`
(`ActiveJobTracker`, independent of the paused check — a stranded run is never
paused). The verdict is brand-agnostic: it reads the same completion signals +
secondary + job-active as the completion gate (§6a) and defers to
`is_stranded_started` (`jobs/job_monitor.py`). Two cases bypass the normal
ended-looking checks entirely:
- **STR-4 — never armed.** A run that never observed an active lifecycle at all
  (`has_observed_active_lifecycle` still `False`) can't be judged by the
  docked/idle + secondary-satisfied checks below (they all assume a real run
  happened) — it's reapable once `dispatched_seconds_ago >= NEVER_STARTED_SECONDS`
  (600s / 10 min), independent of vacuum_state or docked signals.
- **A sequenced phase mid-dispatch.** `_phase_dispatch_pending` set is **no
  longer an unconditional exclusion** (RP-011/RF-07 WD-2/STR-3) — it only
  excludes the reaper while the per-phase watchdog is presumed live; a watchdog
  explicitly marked dead (`phase_watchdog_dead`), or one whose
  `phase_dispatch_pending_since` stamp has aged past its liveness margin with no
  dead-flag update, is reapable like any other stranded phase.

For a run that observed an active lifecycle and isn't excluded by either of
those, `is_stranded_started` also refuses while the job-active binary is on or
`task_status` is a mid-run service state, unless the vacuum reads
docked/idle with its completion secondary satisfied and `task_status` has not
yet reached the brand's completion value. On the first tick the strand holds it stamps
`active_job["stranded_since"]` and waits; a resume clears the stamp so a transient
dock never accrues grace. Once the strand has held past
`STRANDED_REAP_GRACE_MINUTES` (5 min), `poll_*` returns a reap report and the tick
calls `manager.async_finalize_stranded_job`, which finalizes the run as
`interrupted` (`forced_lifecycle_state="stranded_no_completion"`) **without**
`return_to_base` (the robot is already docked/over), using `stranded_since` as
`ended_at` so the duration reflects the real end, then fires `EVENT_JOB_FINISHED`
— **plus `EVENT_RUN_INCOMPLETE` when the strand left rooms uncleaned** (the user's
"if it strands it is incomplete" case; §8), so `retry_missed_rooms` can act.
As an interrupted run it is held from learning but lands in the same review flow,
**Restore-able** rather than lost.

---

## 7. Finalization

### `finalize_learning_for_active_job` (manager entry point)

```python
async def finalize_learning_for_active_job(
    self, *, vacuum_entity_id: str, map_id: str,
    battery_end: int | None = None, ended_at: str | None = None,
    rebuild_stats: bool = True, rebuild_csv: bool = False,
    forced_outcome_status: str | None = None,
    forced_lifecycle_state: str | None = None,
    forced_lifecycle_message: str | None = None,
) -> dict[str, Any] | None
```

Reads `started_at` and `battery_start` from the active job. **Returns
`{"finalized": False, "reason": "missing_started_at"}` early** when `started_at` is
empty (nothing to finalize); returns `None` when no learning manager is present.
Fills `battery_end` from a live read when not supplied. The box-level processing
toggle gates **only the rebuild** — `effective_rebuild = rebuild_stats and
self.learning_processing_enabled`; collection (the per-job save) always happens.
Delegates to `learning.async_finalize_completed_job`, then calls
`_ingest_completed_job_into_room_history` and fires the room-history-updated
notification if anything was ingested.

### The exactly-once claim (`async_finalize_completed_job`)

Multiple entry points can race to finalize the same (vacuum, map) slot — the
lifecycle listener's completion check (§6a), a manual cancel (§6b), the
pause-timeout / stranded reapers (§6c/§6f), and the `finalize_learning_job`
service can all reach `learning.async_finalize_completed_job`
(`learning/manager.py`) for the same job around the same tick. It guards itself
with a synchronous claim written into the **stored** active-job dict (not the
normalized copy `get_active_job()` returns) before the first `await`, which is
atomic on HA's single event loop:

1. No stored record at all → refuse: `{"finalized": False, "reason": "no_active_job_record"}`.
2. `finalized` already `True` → refuse: `{"finalized": False, "reason": "already_finalized"}`.
3. `finalize_claimed_at` already set (a claim is in flight) → refuse:
   `{"finalized": False, "reason": "finalize_in_flight"}`.
4. Otherwise, stamp `finalize_claimed_at = <now>` and proceed.

On a raised exception the claim is popped so a retry stays possible. On success,
`finalized = True` is written **inside the still-claimed window, before
release** — not left to the caller's own `mark_active_job_finalized` — because
two concurrent listener tasks (from two physical HA state-change events
arriving close together) can each be awaiting their own call into this
function; an older release-then-let-the-caller-set-`finalized` ordering left a
gap where a second entrant could find the claim already released and
`finalized` not yet written, and run the whole finalize body again
(hardware-proven, `OBS-IVY-1`/`HW-FINAL-1`). Writing the gate here closes that
window; the caller's `mark_active_job_finalized` remains a safe idempotent
second writer for its own bookkeeping (§9).
`finalize_claimed_at` cannot legitimately survive a process restart — if the
process is starting, nothing is mid-finalize — so `core/manager.py`'s
`_clear_orphaned_finalize_claims` pops it unconditionally from every stored
active job at startup (`async_initialize`); no age heuristic needed. Callers
branch on `finalize_result_succeeded(result)` (`isinstance(result, dict) and
isinstance(result.get("completed_job"), dict)`) rather than "is the result not
`None`", since every refusal above is also a non-`None` dict — see §6a.

### `finalize_from_manager_state` / `finalize_from_inputs` (LearningJobFinalizer)

The finalizer separates event-loop work from file I/O:

**`_collect_finalization_inputs`** (event loop): loads the in-memory live
snapshot (falls back to disk), reads `queue_state`, `payload_state`, and
`active_job_state` from the manager. Determines `outcome_status` from the
caller-supplied forced lifecycle name or the cancel-detection heuristic (the
old live `get_lifecycle_state()` read was removed — its readiness values never
mapped to cancelled/failed/interrupted anyway). Reads `last_cleaning_time_seconds`,
`last_cleaning_area_m2`, and `last_station_water_percent` from `active_job` — the
`last_*`-prefixed live keys the job-metrics listener wrote during the run (§5),
falling back to a live sensor read only on the first run after a cold start. (The
un-prefixed `cleaning_time_seconds` / `cleaning_area_m2` names exist **only** on the
*completed_job* `job` dict, stamped later at finalize — a rebuild reading
`active_job["cleaning_time_seconds"]` would get `None`.) Returns a frozen inputs dict.

**`finalize_from_inputs`** (executor thread — pure computation and file I/O):
- Builds a `completed_job` payload via `store.build_completed_job_payload`. For
  an **atomic dispatched** run this also runs the dispatched-identity reconcile
  (see below) before returning the payload.
- Calls `_apply_snapshot_estimates_to_completed_job` — attaches pre-run
  estimated minutes, battery, and confidence onto each resolved room.
- Calls `_apply_water_actuals` — computes actual water-used breakdown.
- Stamps the normalized `cleaning_area_m2` onto the job dict and mirrors it as
  `cleaning_area_sensor_m2` (the device's own run total, used downstream as the
  area-attribution sanity bound — `utils.area_sanity`), then derives
  `overhead_observed`.
- Calls `_apply_idle_wall_hold` — the cold-start idle-wall guard (see below), run
  *before* the battery sink so a held run also stays out of the battery-drain means.
- Writes `learning_context` (queue shape key, estimate delta, access graph
  metadata).
- Saves `completed_job.json` via `store.save_completed_job`.
- Calls `_write_incomplete_run_log` (for cancelled/failed/interrupted only).
- Calls `_update_trouble_rooms_log`.
- Optionally rebuilds learned stats (`rebuilder.rebuild_all`).

### Dispatched-identity reconcile (atomic runs)

Inside `store.build_completed_job_payload`, an **atomic** dispatched run (not a
strict-order/phased one) reconciles its *positional* room identity — segment K →
queue room K — against the device's native current-room that the pose sampler
buffered during the run (`learning/external_ingest.reconcile_dispatched_identity`).
The counter still owns each segment's time/area; the reconcile only decides *which
room* it was. ROBUST (swept-area) mode only — an anchor-only pose stream is left
untouched, so a weak signal never rewrites a dispatched assignment. Per segment,
on the room the vacuum physically dwelt in most (dock ticks are already nulled):

- **CONFIRM** — the pose agrees with the positional room → stamp
  `pose_confidence="confirmed"`, no change.
- **RESCUE** — the positional K→K map is already known-unreliable (`positional_valid`
  is `False`: segment count ≠ queue count) → overwrite `room_id`/`slug` with the
  pose room and stamp `pose_correction="rescued"` / `pose_prior_room_id`. The run
  is already excluded from the learned aggregate, so this only sharpens the record.
- **FLAG** — a valid positional run where the pose names a *different* room → keep
  the positional `room_id`, annotate `attribution_disagreement={positional, pose}`.
  **Never silently overridden**; learning inclusion is unchanged. Rolled up to the
  job-level `has_attribution_disagreement`, surfaced as the card's "Room Mismatch"
  badge.

No pose / anchor-only / a window the pose can't name → that timing is byte-identical
to the positional path. Strict-order (phased) jobs never reach this — they already
capture accurate per-phase timings. The app-started (external) sibling of this path
is `_apply_pose_identity` / `build_attributed_job` (§9 note); see
[eufy-native-transition.md](design/eufy-native-transition.md) for the shared attribution
model and [28-external-run-ingestion](28-external-run-ingestion.md) for the external flow.

### Cold-start idle-wall guard (`_apply_idle_wall_hold`)

An otherwise-eligible completed run that spent an extreme, *unexplained* stretch off
the dock — wall time far exceeding the device's own `cleaning_time_seconds`, with no
commanded charge/wait break phase and no error window — is **held from learning**
rather than allowed to skew baselines. The decision lives in
`utils.evaluate_idle_wall_hold` (floor `IDLE_WALL_HOLD_FLOOR_MINUTES` = 20 min); when
it holds, the `extreme_idle_wall` blocker is appended to `outcome["learning_blockers"]`,
`used_for_learning` is cleared, and `idle_wall_minutes` is stamped. The run stays
visible and **Restore-able** in the review tab — a soft hold, not a hard exclusion. It
uses the device cleaning counter (never the state-transition wall slice) so a stuck
run's near-full slice can't mask the idle.

### Learning eligibility

A job is **not** used for learning if `outcome_status` is any of:
`"cancelled"`, `"failed"`, `"interrupted"`, `is_test_job = True`.

Normal completions (`outcome_status = "completed"`) are eligible — **unless** the
cold-start idle-wall guard held the run (`extreme_idle_wall` learning blocker,
`used_for_learning` cleared; see above), which stays a `completed` record but is
kept out of the corpus and Restore-able.

### What gets written where

| Data | Location |
|---|---|
| Live snapshot (job start) | `<config>/eufy_vacuum/learning/<vacuum_slug>/live/last_job_snapshot.json` |
| Completed job record | `<config>/eufy_vacuum/learning/<vacuum_slug>/jobs/<job_id>.json` |
| Incomplete run log | `<config>/eufy_vacuum/learning/<vacuum_slug>/live/incomplete_run.json` |
| Trouble rooms log | `<config>/eufy_vacuum/learning/<vacuum_slug>/live/trouble_rooms.json` |
| Rebuilt stats | `<config>/eufy_vacuum/learning/<vacuum_slug>/learned/` — `job_stats.json`, `room_stats.json`, `jobs_index.json`, `accuracy_stats.json` (see [10](10-learning-system.md) §9) |

> **See also:** [10-learning-system](10-learning-system.md) §3 for learning eligibility rules and the full list of blocker strings; §8 for the stats rebuilder triggered at the end of `finalize_from_inputs`. [12-battery-system](12-battery-system.md) §14.3 for the battery metrics hook that runs inside the same finalizer call.

---

## 8. Incomplete Run

### When `EVENT_RUN_INCOMPLETE` fires

`EVENT_RUN_INCOMPLETE` fires after finalization completes whenever the returned
`incomplete_run_log` is non-null and carries at least one `missed_room_id` —
i.e. an involuntarily- or deliberately-ended run left rooms uncleaned. It is
fired by **every** path whose finalize can strand rooms:

| Firing site | Code path | Payload builder |
|---|---|---|
| `finalize_learning_job` service | `handle_finalize_learning_job` (`learning/services.py`) | inline (reference shape) |
| Pause-timeout auto-cancel | `listeners/pause_timeout.py` (via `async_cancel_active_job`) | `run_incomplete_event_data` (`listeners/_common.py`) |
| Stranded-run reaper | `listeners/pause_timeout.py` (via `async_finalize_stranded_job`) | `run_incomplete_event_data` (`listeners/_common.py`) |
| Path-block cancel (`cancel_and_event`) | `listeners/path_blockers.py` (via `async_cancel_active_job`) | `run_incomplete_event_data` (`listeners/_common.py`) |
| Manual `cancel_active_job` service | `services/job_control.py` (via `async_cancel_active_job`) | `run_incomplete_event_payload` (`services/_common.py`) |

Each site fires `EVENT_JOB_FINISHED` first, then `EVENT_RUN_INCOMPLETE` when the
finalize result's `incomplete_run_log` names missed rooms (a completed run carries
no log, so the second event is simply skipped). The payload is byte-identical
across all sites — `{vacuum_entity_id, job_id, outcome_status, missed_room_ids,
missed_rooms}` (no `map_id`) — so an automation's event-driven `retry_missed_rooms`
trigger fires the same regardless of how the run ended. The two payload builders
mirror the `job_finished_event_data` / `job_finished_event_payload` split
(listener vs. service package; kept in sync, live separately).

> **Historical note (finding B1):** through the job-lifecycle DR hardening this
> event was *service-path-only* — the internal reapers wrote `incomplete_run.json`
> but emitted just `EVENT_JOB_FINISHED`, so `retry_missed_rooms` never fired after
> an internal cancel/strand. A run that stranded rooms was therefore "finished"
> but not "incomplete", and the retry never triggered. The reapers now fire it too.

The incomplete run log is written only when
`outcome_status in {"cancelled", "failed", "interrupted"}`; a normal completion
clears any stale log (`store.clear_incomplete_run`). It is a single-overwrite file —
only the most recent incomplete run is kept.

**`incomplete_run.json` schema** (`_write_incomplete_run_log`, `learning/job_finalizer.py`):

```json
{
  "schema_version": 1,
  "record_type": "incomplete_run_log",
  "vacuum_entity_id": "vacuum.alfred",
  "job_id": "job_2026-06-06T16-11-34",
  "map_id": "6",
  "outcome_status": "cancelled",           // cancelled | failed | interrupted
  "ended_at": "<ISO>",
  "queued_room_ids": [1, 2, 3],
  "completed_room_ids": [1],
  "missed_room_ids": [2, 3],               // sorted(set(queued) - set(completed))
  "missed_rooms": [ { "room_id": 2, "name": "Kitchen" } ],
  "logged_at": "<ISO>"
}
```

### `retry_missed_rooms` flow

`handle_retry_missed_rooms` in `learning/services.py`:

1. Reads the incomplete run log from disk via `learning.get_incomplete_run_log`.
   Returns `{"started": False, "reason": "no_missed_rooms"}` if empty.
2. Resolves `map_id` from the log (overridable via call data).
3. Calls `set_rooms_enabled_subset` — enables only missed rooms, disables all
   others.
4. Calls `build_queue` to rebuild the queue with those rooms.
5. Calls `start_selected_rooms` with `confirm_reduced_run=True` so automations
   bypass confirmation.
6. Persists via `async_save`.
7. If started successfully, clears the incomplete run log.
8. Returns the `start_selected_rooms` result plus `missed_room_ids` and
   `map_id`.

---

## 9. State Cleanup

After finalization, `mark_active_job_finalized` updates the active job record
in-place (on `ActiveJobTracker`) rather than clearing it. Before touching the
active-job fields it also releases the `MappingTracker`'s hold on this job
(`tracker.end_job(...)`, if a tracker is registered) — this is the terminal
chokepoint every path reaches (success, cancel, strand), unlike the lifecycle
finalize path's own `finally`, which a cancel/strand never goes through (see
[04-listeners §3.5](04-listeners.md)):

```python
active_job["status"]   = "completed"
active_job["finalized"] = True
active_job["paused_at"] = None
active_job["has_observed_active_lifecycle"] = False   # reset
active_job["_phase_dispatch_pending"] = False          # clear strict-order guard
active_job["_cancel_in_flight"] = False                # clear the cancel single-flight latch
active_job["finalized_at"] = <from completed_job>
active_job["finalize_summary"] = {
    "job_id", "job_path", "used_for_learning",
    "sanity_passed", "sanity_flags", "learning_blockers", "status"
}
```

`runtime.active_job_room_ids` is reset to `[]`.

The `data["queue"]` and `data["payloads"]` snapshots are **not** cleared
automatically after finalization — they persist until the next `build_queue` /
`build_room_payload` call (e.g., when the user selects rooms for the next job).
The active job record stays at `status: "completed"` until overwritten by the
next job start.

---

> **External (app-started) runs** follow a parallel lifecycle: detected by the
> lifecycle listener (cleaning + no dispatched job), captured into a
> `status="external"` slot, and finalized — when the robot docks — into a *pending
> review record* rather than a learned job. The user confirms room identities in
> the card, which graduates the run into a normal `jobs/` record. See
> [28-external-run-ingestion](28-external-run-ingestion.md).
>
> A graduated external job's `outcome` is written with **`sanity_passed: True`**
> and `sanity_flags: []` by `build_graduated_job` (`learning/external_ingest.py`):
> a run only graduates after clearing the tier-1 identity gate with a valid
> duration and room set, so it is sane by construction. The flag is set
> explicitly because the jobs index stores `sanity_passed` as `None` for such
> records, and the history-view outlier check now treats only an explicit
> `item.get("sanity_passed") is False` as a sanity failure
> (`learning/manager.py`) — a missing/`None` value no longer counts as failed.
> (Previously a `.get("sanity_passed", True)` default never fired against the
> stored `None`, so every graduated external run was wrongly tagged "failed the
> backend sanity checks".)

## 10. Event Timeline

Chronological table of every HA event fired during a complete job (single
successful run, no cancellations or stalls).

| # | Event constant | String value | When | Key payload fields |
|---|---|---|---|---|
| 1 | `EVENT_ROOM_STARTED` | `eufy_vacuum_room_started` | Immediately after `vacuum.send_command`, if `current_room_id` is non-null | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `started_at`, `source: "job_start"`, `completed_room_ids: []` |
| 2 | `EVENT_ROOM_FINISHED` | `eufy_vacuum_room_finished` | Each rollover (room N complete) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_at`, `source` (`"counter_plateau"` / `"timing_rollover"` / `"bounds_exit_early"` / `"native_signal"`), `actual_duration_minutes`, `confidence`, `completed_room_ids`. The `"native_signal"` variant (native current-room rollover, e.g. Roborock, `_set_native_current_room`) omits `confidence`. The `"bounds_exit_early"` source is **dormant** — its producer was removed with the mapping split. |
| 3 | `EVENT_ROOM_STARTED` | `eufy_vacuum_room_started` | Immediately after each `room_finished`, for the next room | `source: "counter_plateau"`, `"timing_rollover"`, `"bounds_exit_early"` (dormant), or `"native_signal"` |
| 4 | `EVENT_STALL_DETECTED` | `eufy_vacuum_stall_detected` | Once per room per job, when elapsed >= `stall_ratio`× timing threshold (2× default) | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` |
| 5 | `EVENT_PATH_BLOCKED` | `eufy_vacuum_path_blocked` | When a blocker entity changes during a job (any `path_block_action`) | The full `get_runtime_path_block_report` dict **plus** `path_block_action`, `action_taken`, and `action_result` (present only when a cancel/pause action ran). Includes `affected_remaining_room_ids` among the report fields. |
| 6 | `EVENT_ROOM_SKIPPED` | `eufy_vacuum_room_skipped` | Once per room, when the live queue advances *past* an uncompleted queued room (non-sequential advance — ~never for Eufy) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_room_ids` |
| 7 | `EVENT_JOB_FINISHED` | `eufy_vacuum_job_finished` | After finalization completes | **Two shapes.** *Lifecycle / reaper path* (`job_finished_event_data`, `listeners/_common.py` — normal completion + pause-timeout + stranded + path-block cancel) = 11 fields: the 9 below **plus `duration_minutes` and `actual_cleaning_minutes`**, with `reason_detail = lifecycle_message or status`. *Service path* (`finalize_learning_job` handler) = 9 fields: `vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail` (= `lifecycle_message`, no status fallback), `used_for_learning`, `finalized_at`, `room_count`, `job_path` |
| 8 | `EVENT_RUN_INCOMPLETE` | `eufy_vacuum_run_incomplete` | After `job_finished`, when the finalize's `incomplete_run_log` names missed rooms — from **every** finalize path that can strand rooms (service finalize, pause-timeout, stranded reaper, path-block cancel, manual cancel); see §8 | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids`, `missed_rooms` (no `map_id`) |

**Notes:**
- Events 2 and 3 repeat for each room beyond the first. A 4-room job produces 3
  pairs of `room_finished` / `room_started` plus the initial `room_started`.
- Event 4 fires at most once per room even on repeated polls. `running_long`
  (the soft 1.5×–2× tier below the stall) fires **no event** — it appears only
  on the progress snapshot.
- Event 6 (`EVENT_ROOM_SKIPPED`) fires at most once per room and is
  effectively never seen on Eufy (sequential counter rollover); the reliable
  post-run "missed rooms" signal remains `EVENT_RUN_INCOMPLETE`.
- Events 5, 6, and 8 are conditional and may not appear in every job.
- `EVENT_RUN_INCOMPLETE` (event 8) fires from **every** finalize path that can strand rooms — the `finalize_learning_job` service, the pause-timeout auto-cancel, the stranded-run reaper, a path-block `cancel_and_event`, and the manual `cancel_active_job` service — each after its `EVENT_JOB_FINISHED`, whenever the finalize's `incomplete_run_log` names missed rooms. So event-driven `retry_missed_rooms` fires after an internal cancel/strand just as it does after a service finalize. (Finding B1: previously service-path-only — see §8.)
- `EVENT_PATH_BLOCKED` and `EVENT_JOB_FINISHED` can both fire in the same job
  when `path_block_action == "cancel_and_event"`.
- Event `room_id` is a **string** in `EVENT_ROOM_STARTED` / `EVENT_ROOM_FINISHED` (job start + rollover) but an **int** in `EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED`. On `EVENT_ROOM_FINISHED`, `actual_duration_minutes` rounds to 2 dp and `confidence` to 4 dp (`None` when ≤ 0).
- `EVENT_JOB_PROGRESS_TICK` (`eufy_vacuum_job_progress_tick`) is fired
  periodically from `listeners/job_progress.py` (a 5-second
  `async_track_time_interval` ticker) as a lightweight polling signal for
  automations — it does not map to a lifecycle transition.
