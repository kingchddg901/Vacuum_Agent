# 06 — Cleaning Job Lifecycle

Traces every state, transition, side effect, and event across the full life of
a room-cleaning job — from queue build through finalization. A developer should
be able to follow the entire flow from source code using this document.

**Primary source files:**
- `custom_components/eufy_vacuum/core/manager.py`
- `custom_components/eufy_vacuum/jobs/active_job.py`
- `custom_components/eufy_vacuum/jobs/job_monitor.py`
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
`get_onboarding_state` and assembles a status dict. It returns early with
`blocked: True` and the following `reason` strings in priority order:

| `reason` | Condition |
|---|---|
| `"job_paused"` | `active_job["status"] == "paused"` |
| `"onboarding_required"` | One or more enabled rooms are missing a floor type |
| `"all_selected_rooms_blocked"` | All selected rooms were blocked by rules; none remain |
| `"no_target_map"` | `selected_map_id` is empty |
| `"map_mismatch"` | `selected_map_id` != vacuum's active map |
| `"no_rooms_selected"` | Queue is empty |
| `"invalid_payload"` | Payload room count is 0 |
| `"mid_job_service"` | Dock or task status is in a hard service state (washing, recycling, emptying) |
| `"active_job_running"` | A room-clean job is already active |
| `"vacuum_busy"` | Vacuum is busy and not dockable/idle |
| `"incomplete_access_graph"` | Room access graph is partially configured |
| `"access_graph_required_for_rules"` | Rules are present but no access graph exists |
| `"access_graph_required"` | Blocker rules exist without an access graph |

The lifecycle state `"dock_drying"` is a non-blocking warning — it sets
`blocked: False` with `warning: True` and `reason: "dock_drying"`.

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
`strict_order` boolean field — `services/job_control.py:84`) makes a
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
5. **Global pre-calls** — calls `_run_global_pre_calls` to push global device
   settings (fan/mop) for brands that expose them only globally (Roborock:
   per-room fan/water can't ride `app_segment_clean`), derived max-wins from
   the selected rooms. No-op when no adapter declares
   `dispatch.global_pre_calls` (e.g. Eufy, which carries fan/water per-room).
6. **Live-id resolution** — calls `_resolve_live_dispatch_payload` to map
   stored (slug-tagged) room ids to the current **live** segment ids before
   dispatch, for brands whose ids renumber on re-segment (Roborock). Wire-only:
   the active job below keeps the stored ids.
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
   active-job snapshot byte-identical to pre-sequencing.
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

### 2b. `start_run_profile`

`async EufyVacuumManager.start_run_profile(vacuum_entity_id, map_id,
profile_id, ...)` is the saved-run-profile alternative entry point.

1. Calls `apply_run_profile(profile_id)` — loads the saved room list from
   `data["run_profiles"]`, re-enables exactly those rooms, and overwrites their
   settings from the saved snapshot. Returns `applied: False` if the profile ID
   is not found.
2. Calls `build_queue` and `build_room_payload` to rebuild derived state from
   the new room configuration.
3. Delegates to `start_selected_rooms` (all confirmation/blocking logic applies
   identically). Adds `profile_id` and `profile` to the return dict.

---

## 3. Active Job Monitoring

### `get_job_progress_snapshot`

`EufyVacuumManager.get_job_progress_snapshot(vacuum_entity_id, map_id)` is the
main polling endpoint for the card. It does not mutate storage unless a timing
rollover occurs. Each call:

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
   accumulated `current_room_paused_seconds` and any ongoing pause.
7. **Timing rollover** — delegates to
   `active_job._maybe_roll_current_room_by_timing` (the manager's `active_job`
   attribute is the `ActiveJobTracker`; method defined at
   `jobs/active_job.py:814`, reached via the `manager.py:843` delegator). See §4.
8. **Bounds-exit detection** (`awaiting_bounds_exit`).
9. **Anomaly detection** — `stall` (hard), `running_long` (soft), and
   `skipped` (conservative). See below.

### `awaiting_bounds_exit` logic

After the timing rollover attempt, if the room did *not* roll (i.e.
`current_room_id` is unchanged), the snapshot checks whether elapsed time has
passed the timing completion threshold. If so, `awaiting_bounds_exit = True`.
This signals the card to switch to a short poll interval (~5 s) because the
robot is still physically inside the room and the rollover gate is blocked by
bounds.

### Anomaly detection

The three disjoint anomaly tiers (and the one-shot `EVENT_STALL_DETECTED` /
`EVENT_ROOM_SKIPPED` emission) are computed by
`ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py:628`), which
`get_job_progress_snapshot` calls (`manager.py:3202`) and whose returned fields
it merges into the snapshot. Both ratios are read from the adapter's `anomaly`
block (`running_long_ratio`, `stall_ratio`), each falling back to the Eufy
default if absent. The `_STALL_RATIO` / `_RUNNING_LONG_RATIO` locals live inside
`detect_run_anomalies` (`active_job.py:661-662`), not in the snapshot composer.

```
_STALL_RATIO        = anomaly.stall_ratio        or 2.0
_RUNNING_LONG_RATIO = anomaly.running_long_ratio  or 1.5
```

**Stall (hard).** A stall is detected when:
- `awaiting_bounds_exit` is already `True` (timing threshold exceeded), **and**
- `current_room_elapsed_minutes >= threshold * _STALL_RATIO` (≥2× by default)

`EVENT_STALL_DETECTED` fires at most once per room per job. Already-notified
rooms are tracked in `active_job["_stall_notified_room_ids"]` — owned and
written back to storage by the tracker (`active_job.py:687-691`). Subsequent
calls suppress the event for those rooms.

**Running-long (soft).** The tier *below* the stall band — set when the room is
genuinely overrunning but not yet stalled, and there is no pending live
transition (so it is overrunning *in* the room, not a missed roll). Conditions:
- not already stalled, status `started`, valid `current_room_id`, **and**
- no pending counter transition
  (`active_job._live_boundary_count(...) <= len(completed_room_ids)`), **and**
- `_RUNNING_LONG_RATIO * threshold <= current_room_elapsed_minutes < _STALL_RATIO * threshold`
  (1.5×–2× by default — a half-open band disjoint from stall).

Running-long is **snapshot-only — it fires no event.** It surfaces only on the
returned snapshot (`running_long`, `running_long_room_id`, `running_long_ratio`,
and per-room `running_long` on the current timeline entry) so the card can draw
a warning ring on the chip.

**Skipped (conservative).** `skipped_room_ids` = queued rooms strictly *before*
`current_room_id` in queue order that are not in `completed_room_ids`. Because
Eufy's sequential counter rollover keeps `completed_room_ids` a prefix of the
queue, this is **~always empty for Eufy** — a mid-run skip can't be attributed
from the counters, so the reliable "missed rooms" signal stays the post-run
`incomplete_run_log` (§8). The hook fires only on a genuinely non-sequential
advance (position-reliable brands / transition detection); there is no
false-positive heuristic. When new skips appear, `EVENT_ROOM_SKIPPED` fires once
per room (deduped via `active_job["_skipped_notified_room_ids"]`), and the
skipped rooms are flagged per-entry on the timeline (`skipped`) and excluded
from `remaining_room_ids`.

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
(`advance_active_job_phase`) and re-dispatches instead of finalizing —
each phase finalizes as its own job record.

No engine declares `job_model = "sequenced"` at the *class* level, but
sequenced runs are nonetheless produced **per-run** by the strict-order
opt-in. `GenericRoomIdsEngine.build_phases(strict_order=True)` (and its
`RoborockSegmentEngine` subclass) emits **one single-segment phase per
resolved room** in queue order instead of one batch the device would
re-route (`dispatch_engines.py:219-281`). This is gated on
`capabilities.honors_clean_order = False` — i.e. only path-optimizing
brands that ignore the dispatched order (Roborock, Ecovacs) take this
path; order-honoring brands (Eufy) never sequence. When the resulting plan
holds more than one phase, the framework attaches the sequence to the
active job and runs it as a sequenced job: `maybe_advance_phase` advances +
re-dispatches at each completion (`PhaseRunner.maybe_advance_phase`,
`jobs/phase_runner.py:67`, reached via the `manager.py:4206` delegator; the
advance step itself is `advance_active_job_phase` in
`queue/queue_engine.py:409`; the per-run phase build is
`planning/run_plan.py:778`; the completion-hook call is `lifecycle.py:307-312`),
and each phase finalizes
as its own job record. The advance/finalize machinery is wired into both
the start and completion paths (`maybe_advance_phase` runs in the
completion hook, see §6a; the start-side spawn and per-phase watchdog are
in §2a and §4a). See [07-queue-engine.md](07-queue-engine.md) and
[22-adapter-config-reference.md](22-adapter-config-reference.md) §13.

### 4a. Strict-order phase watchdog (`_run_advanced_phase`)

A sequenced strict-order run can't simply re-dispatch the next room at the
completion hook: a path-optimizing device (Roborock S6) returns to the dock
and starts charging at the end of each single-room phase, and **ignores an
`app_segment_clean` sent at that instant**. The per-phase watchdog lives on
the dedicated `PhaseRunner` subsystem
(`PhaseRunner._run_advanced_phase`, `jobs/phase_runner.py:287`) and wraps
each phase in a settle → dispatch → verify → retry loop. The manager keeps
only the initial-phase spawn (`self.phase_runner._run_advanced_phase`,
`manager.py:4403`) and a thin `maybe_advance_phase` delegator
(`manager.py:4206`).

- **Initial phase (`initial=True`).** Phase 0 was already dispatched by
  `start_selected_rooms`, so the watchdog skips the settle and the first
  send and only **verifies** that the device actually started — a retry
  re-dispatches only if the initial send was ignored.
- **Advanced phases.** The watchdog **settles** before dispatching. The
  settle is extended when the phase's target room *is* the dock room
  (`_phase_target_is_dock_room` → `dock_settle_seconds`), because a robot
  parked + charging on its target has the longest post-dock ignore-transient.
  It then **dispatches**, **verifies** via `PhaseRunner._await_phase_started`
  (`jobs/phase_runner.py:400`) that the device actually started *and sustained*
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
`_phase_timing` (`manager.py:4220-4244`, which stays on the manager): the
adapter's `dispatch.phase_timing` block merged over the `_PHASE_*` module
defaults (`manager.py:85-110`) — settle 10 s, dock-settle 45 s, verify 90 s, confirm
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
distinguishing the path. There are **four rollover sources**. The first is the
native-signal path (checked before everything else); the remaining three are the
counter/timing paths, checked in this order:

**Native-signal path (device's live current room, checked first):**
1. For adapters that declare `live_transition.native_transition_source=True`
   (Roborock), `_maybe_roll_current_room_by_timing` short-circuits to
   `_maybe_roll_current_room_by_native_signal` (`active_job.py:1107`) — checked
   **before** the `current_room_id is None` guard and the three counter/timing
   sources (`active_job.py:877-884`).
2. Rollover **follows** the device's native live current-room signal (filtered to
   job targets, matched by name slug, **order-agnostic**) rather than the
   sequential counter/timing heuristic.
3. It completes/advances rooms directly from the native signal and fires
   `EVENT_ROOM_FINISHED` / `EVENT_ROOM_STARTED` with `source="native_signal"`
   through `_set_native_current_room` (`active_job.py:1216`, `1227`, `1250`). The
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
  when truthy — Roborock, `adapters/roborock/adapter.py:399` — current-room
  rollover routes to `_maybe_roll_current_room_by_native_signal` and follows the
  brand's native live-room signal instead of this counter/timing path; Eufy
  leaves it `False`, `adapters/eufy/adapter.py:743`, keeping the path below
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

The stall threshold is `2 × _timing_completion_threshold_minutes`.

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

Fired when the vacuum's task status indicates a low-battery return. Two-stage
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

---

## 6. Job End Paths

### 6a. Normal completion

**Trigger:** The lifecycle listener observes `task_status == "completed"` AND
`active_cleaning_target` is cleared, while
`active_job["has_observed_active_lifecycle"] == True`.

**Code path:** the state-change handler → `_process()` in
`listeners/lifecycle.py` (registered via `lifecycle.register(hass)` from
`__init__.py`).

The base completion condition (`lifecycle.py:263-298`) is **adapter-driven,
not a hardcoded sentinel set**: it requires `task_status` to equal the
adapter's `completion.task_status_value`, the secondary signals to be
satisfied via `completion_secondary_satisfied` (which consults
`completion.secondary_clear_sentinels` and `completion.require_job_active_clear`),
and `has_observed_active_lifecycle == True`. Two further guards then run *on
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

When all three pass, it first calls `manager.maybe_advance_phase` — for a
**sequenced** job this advances to the next phase + re-dispatches instead of
finalizing (see §4). Otherwise: `finalize_learning_for_active_job` →
`mark_active_job_finalized` → `EVENT_JOB_FINISHED`.

### 6b. Manual cancel (service call)

**Trigger:** `eufy_vacuum.cancel_active_job` service.

**Code path:** `async_cancel_active_job` → `vacuum.return_to_base` (blocking)
→ polls every 2 s for up to 30 s (`_CANCEL_CONFIRM_TIMEOUT_S`) for
`vacuum_state in {"docked", "idle"}` or `task_status in {"completed", "complete"}`.
If not confirmed within 30 s, finalizes anyway with a warning. Calls
`finalize_learning_for_active_job` with `forced_outcome_status="cancelled"` and
`forced_lifecycle_state="job_cancelled"`, then `mark_active_job_finalized`.

### 6c. Pause timeout

**Trigger:** A paused job whose `pause_timeout_minutes > 0` has been paused
beyond the configured limit.

**Code path:** `listeners/pause_timeout.py` (`pause_timeout.register(hass)`)
sets a 1-minute `async_track_time_interval` tick. On each tick,
`get_paused_job_timeout_report` is called for each known job. If it returns a
report, `async_cancel_active_job` is called with
`forced_lifecycle_state="pause_timeout_cancelled"`.

### 6d. Path blocker cancel

**Trigger:** A watched entity whose state matches a blocker rule changes while
`path_block_action == "cancel_and_event"`.

**Code path:** `listeners/path_blockers.py` (`path_blockers.register(hass)`)
watches all rule entities. On state change, `get_runtime_path_block_report`
re-evaluates rules. Behaviour by
`path_block_action`:
- `"event_only"` — fires `EVENT_PATH_BLOCKED` only.
- `"pause_and_event"` — `async_pause_active_job` + `EVENT_PATH_BLOCKED`.
- `"cancel_and_event"` — `async_cancel_active_job` + `EVENT_JOB_FINISHED` +
  `EVENT_PATH_BLOCKED`.

### 6e. Cancel detection heuristic (automatic)

During finalization, `_detect_cancel_likely_run` is called when
`forced_outcome_status` is `None`. It examines `state_transitions`.

**Conditions for `cancel_likely=True`** (single-room jobs only):
1. Transition history contains `cleaning → returning` or `paused → returning`
   via `task_status`.
2. No stronger service state in transitions (e.g. `"returning to charge"`,
   `"washing mop"`, `"emptying dust"`).
3. `actual_cleaning_minutes < 1.5` (absolute floor), **or**
   `actual_cleaning_minutes < expected_room_minutes × 0.4` (relative threshold).

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
`is_stranded_started` (suppressed while `_phase_dispatch_pending` is set or the
status is a mid-run service state). On the first tick the strand holds it stamps
`active_job["stranded_since"]` and waits; a resume clears the stamp so a transient
dock never accrues grace. Once the strand has held past
`STRANDED_REAP_GRACE_MINUTES` (5 min), `poll_*` returns a reap report and the tick
calls `manager.async_finalize_stranded_job`, which finalizes the run as
`interrupted` (`forced_lifecycle_state="stranded_no_completion"`) **without**
`return_to_base` (the robot is already docked/over), using `stranded_since` as
`ended_at` so the duration reflects the real end, then fires `EVENT_JOB_FINISHED`.
As an interrupted run it is held from learning but lands in the same review flow,
**Restore-able** rather than lost.

---

## 7. Finalization

### `finalize_learning_for_active_job` (manager entry point)

`async EufyVacuumManager.finalize_learning_for_active_job(...)` reads
`started_at` and `battery_start` from the active job, reads current battery as
`battery_end`, then delegates to `learning.async_finalize_completed_job`. After
the result returns, calls `_ingest_completed_job_into_room_history` and fires
the room-history-updated notification if anything was ingested.

### `finalize_from_manager_state` / `finalize_from_inputs` (LearningJobFinalizer)

The finalizer separates event-loop work from file I/O:

**`_collect_finalization_inputs`** (event loop): loads the in-memory live
snapshot (falls back to disk), reads `queue_state`, `payload_state`, and
`active_job_state` from the manager. Determines `outcome_status` from the
caller-supplied forced lifecycle name or the cancel-detection heuristic (the
old live `get_lifecycle_state()` read was removed — its readiness values never
mapped to cancelled/failed/interrupted anyway). Reads `cleaning_time_seconds`
and `cleaning_area_m2` from `active_job` (written there by
`record_active_job_sensor_value` during the run). Returns a frozen inputs dict.

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
[eufy-native-transition.md](eufy-native-transition.md) for the shared attribution
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
| Rebuilt stats | `<config>/eufy_vacuum/learning/<vacuum_slug>/learned_stats.json` |

> **See also:** [10-learning-system](10-learning-system.md) §3 for learning eligibility rules and the full list of blocker strings; §8 for the stats rebuilder triggered at the end of `finalize_from_inputs`. [12-battery-system](12-battery-system.md) §14.3 for the battery metrics hook that runs inside the same finalizer call.

---

## 8. Incomplete Run

### When `EVENT_RUN_INCOMPLETE` fires

`EVENT_RUN_INCOMPLETE` is fired by the `handle_finalize_learning_job` service
handler in `learning/services.py` after finalization completes, **if**
`incomplete_run_log` is non-null and contains at least one `missed_room_id`.

The incomplete run log is only written when
`outcome_status in {"cancelled", "failed", "interrupted"}`. Normal completions
clear any stale log.

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
in-place (on `ActiveJobTracker`) rather than clearing it:

```python
active_job["status"]   = "completed"
active_job["finalized"] = True
active_job["paused_at"] = None
active_job["has_observed_active_lifecycle"] = False   # reset
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
| 5 | `EVENT_PATH_BLOCKED` | `eufy_vacuum_path_blocked` | When a blocker entity changes during a job (any `path_block_action`) | `vacuum_entity_id`, `map_id`, `path_block_action`, `action_taken`, `affected_remaining_room_ids` |
| 6 | `EVENT_ROOM_SKIPPED` | `eufy_vacuum_room_skipped` | Once per room, when the live queue advances *past* an uncompleted queued room (non-sequential advance — ~never for Eufy) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_room_ids` |
| 7 | `EVENT_JOB_FINISHED` | `eufy_vacuum_job_finished` | After finalization completes | `vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail`, `used_for_learning`, `finalized_at`, `room_count`, `job_path` |
| 8 | `EVENT_RUN_INCOMPLETE` | `eufy_vacuum_run_incomplete` | After `job_finished`, only when rooms were missed | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids`, `missed_rooms` |

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
- `EVENT_PATH_BLOCKED` and `EVENT_JOB_FINISHED` can both fire in the same job
  when `path_block_action == "cancel_and_event"`.
- `EVENT_JOB_PROGRESS_TICK` (`eufy_vacuum_job_progress_tick`) is fired
  periodically from `listeners/job_progress.py` (a 5-second
  `async_track_time_interval` ticker) as a lightweight polling signal for
  automations — it does not map to a lifecycle transition.
