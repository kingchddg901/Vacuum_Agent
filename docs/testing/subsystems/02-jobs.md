# 02 — Jobs — Subsystem Test Map

The jobs subsystem owns active-job state and the start-time lifecycle gate:
`job_monitor.py` evaluates whether the vacuum is ready to start,
`active_job.py` tracks an in-flight job (room rollover, recharge/mop-wash
observations, transition-room detection, live run-anomaly detection), and
`phase_runner.py` runs strict-order (sequenced) per-room phase execution +
per-phase timing capture. Covered by **258 tests across 5 files**.

Source: `custom_components/eufy_vacuum/jobs/`
Architecture reference: [docs/dev/06-job-lifecycle.md](../../dev/06-job-lifecycle.md)

---

### `stuck_watch.py` — two triggers, because a robot gets stuck two ways (added 2026-08-09)

`test_stuck_watch.py` (12 tests) covers the area gate and the error edge as pure
logic. Both were designed against hardware, by deliberately trapping a Roborock S6
twice on 2026-08-09:

- **Corner trap** — the robot was MOVING, retrying, and freed itself after ~3 minutes.
  No error code ever fired; `vacuum.<id>` stayed `cleaning`. `cleaning_area` moved
  0.0 → 0.6 in the first seconds and then flat. Only the swept-area delta caught it,
  and a pose-based detector would have called it healthy because it *was* moving.
- **Box wedge** — `bumper_stuck` on every error surface within seconds.

So the tests are written against those two shapes rather than against the
implementation. The ones that carry the most weight are the refusals:

- [SW-2]/[SW-3] a working robot must not trip it. A detector that cries wolf is
  switched off, after which it catches nothing at all — the worst outcome available.
- [SW-4] leaving an exclusion must REBASE, not resume. Suppress-only fires on the
  first unmuted tick after every mid-run recharge.
- [SW-6] dither must not manufacture progress. Summing positive deltas over a
  15-minute window at a ~15s cadence turns ±0.1 m² of noise into ~3 m² of phantom
  movement, which would silently disable the gate on exactly the case it exists for.
- [SW-10] a `code=None` episode must FIRE — that is the Eufy stuck path, and a
  predicate written as `code in IMMOBILIZING` is blind to it.

**The interaction nothing tests, and the reason the numbers are what they are:** the
area window (15 min) must stay LONGER than `STRANDED_REAP_GRACE_MINUTES` (5). An
errored or docked run belongs to the reaper; the area gate's domain is a run that
still *looks* alive. Shorten one or lengthen the other and they fight over the same
run.

## Coverage map

| Source module | Stmts | Cov | Test file(s) | Layer | Mocking |
|---------------|------:|----:|--------------|-------|-------|
| `job_monitor.py` | 149 | 98% | `tests/unit/test_jobs_job_monitor.py` | unit (pure) | clean |
| `active_job.py` | 1106 | 93% | `tests/unit/test_jobs_active_job.py` + `tests/integration/test_jobs_active_job.py` + `tests/integration/test_jobs_active_job_spatial.py` | unit + integration | **bare x3** |
| `phase_runner.py` | 731 | 88% | `tests/integration/test_strict_order_phase_timing.py` | integration | clean |

---

## What's tested

### `job_monitor.py` — start-gate evaluation (prefix `JM`, 31 tests)
The whole module is pure, so coverage is near-total:
- **`_norm`** — sentinel collapsing (`unknown`/`unavailable`/`none` → `""`).
- **`build_job_metadata_from_payload`** — room id/slug/clean-mode extraction,
  `has_mop_mode` / `has_vacuum_only_mode` derivation, and defensive coercion of
  bad containers.
- **`evaluate_job_lifecycle`** — the full state-precedence ladder:
  `map_mismatch` → `mid_job_service` → `dock_drying` → `active_job_running` →
  `vacuum_busy` → `ready`, including the adapter-vocabulary sets
  (`hard_service_states`, `drying_states`, `active_run_task_states`).
- **`build_start_blocker_from_lifecycle`** — the blocker payload for each
  lifecycle state plus the pre-checks (no map, map mismatch, empty queue,
  invalid payload) and the canned-message fallback.

### `active_job.py` — active-job tracking (prefixes `AJ` unit, `AJI` integration)
`active_job.py` is a 3,211-line file that is mostly the `ActiveJobTracker` class
(starting line 231), bound to the manager and hass. Two layers:
- **`AJ` (unit, `MagicMock` manager)** — module helpers (`_safe_int`,
  `_normalize_path_block_action`, …) and the pure tracker methods:
  `_default_active_job_state`, `_derive_active_job_current_room_id`,
  `_normalize_active_job`, `_compute_current_room_elapsed_minutes`,
  `_room_name_from_active_job`, `_timing_completion_threshold_minutes`, and the
  current-room non-cleaning accumulator (`_accumulate_current_room_noncleaning`,
  `reopen_current_room_noncleaning` — the latter needs a hass whose vacuum state
  is *fixed*, not a bare `MagicMock`, or every "is it docked?" assertion passes
  for the wrong reason).
- **`AJI` (integration, real `manager` fixture + seeded active job)** —
  `get_active_job`, the mop-wash observation (count + 60s debounce),
  `record_active_job_transition` (append/ignore-noise/cap-12, plus driving the
  non-cleaning accumulator off the vacuum entity only),
  `record_active_lifecycle_observed`, `record_active_job_sensor_value`,
  `add_update_listener`/`_notify`, and `update_active_job_recharge_observation`.

`ActiveJobTracker` also owns **`detect_run_anomalies`** (`active_job.py::ActiveJobTracker._pose_says_still_in_room`) —
the live stall / running-long / skipped detection that emits
`EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED` (once per room per job) for the
progress snapshot, moved out of the manager snapshot composer because the tracker
holds the active-job dict and the per-job dedup state the one-shot emission keys
on. Its anomaly behavior is currently exercised from
`tests/integration/test_manager_progress.py` rather than the `AJ`/`AJI` suites.

`record_pose_sample` (the W5b pose buffer feeding external-run room attribution)
carries its own unit cases: the **stall-coalescing** guard (`_pose_sample_is_static`
+ `_POSE_STALL_COALESCE_TICKS`) collapses a frozen tail so a multi-hour freeze can't
flood the 3000-sample buffer and evict the run's real early cleaning data, while a
slow-but-cleaning robot (rising `cleaning_area`) is never coalesced — external-run
robustness Item 1 (see [28-external-run-ingestion](../../dev/28-external-run-ingestion.md)).

> The recharge test surfaced a real bug: the method called
> `hass.states.get(None)` when the adapter has no `task_status` entity. Fixed
> with the same `if entity_id else None` guard already applied in `core/manager`
> and `run_plan`.

The spatial pipeline is now covered (see the `AJS` integration suite below); the
remaining ~8% is defensive guards and edge branches — see **Known gaps**.

### `phase_runner.py` — strict-order phase execution (prefix `SOPT`, integration)
`PhaseRunner` (`phase_runner.py:59`) owns the two halves of strict-order
(sequenced, one-room-per-phase) cleaning, extracted from `core/manager.py`:
- **Per-phase timing capture** — `maybe_advance_phase` (the public entry point,
  called by the completion hook via the manager delegator) snapshots each
  finishing phase's room timing from *its own* counter slice
  (`_capture_finishing_phase_timing` → `_phase_room_timing` / `_wall_seconds` /
  `_learned_room_area_m2`) before `advance_active_job_phase` resets the queue, so
  finalization reconstructs per-phase timings instead of mis-attributing the whole
  run to the last phase's room.
- **Watchdog** — `_run_advanced_phase` (settle → dispatch → verify → retry) with
  `_await_phase_started` / `_dispatch_active_phase`, the per-phase re-dispatch that
  works around a path-optimizing brand ignoring a clean sent the instant it docks.

Covered by `tests/integration/test_strict_order_phase_timing.py` (`SOPT`, 6
tests): per-phase capture from its own slice (`SOPT-1`), capture idempotence on
retry/double-completion (`SOPT-2`), the learned-area fallback when a flat
`cleaning_area` sensor leaves no in-slice delta (`SOPT-3` / `SOPT-6`), atomic
(no-phase) jobs as a no-op (`SOPT-4`), and the per-phase battery/area/wall deltas
(`SOPT-7`). The watchdog timing defaults (`_PHASE_*` / the adapter
`dispatch.phase_timing` overrides) stay resolved on the core manager via
`_phase_timing`.

---

## How it's tested

Both files are **pure-import unit tests** (Recipe C):

```python
from custom_components.eufy_vacuum.jobs.job_monitor import evaluate_job_lifecycle
```

`job_monitor` needs nothing else. `active_job` instantiates the tracker with a
mock manager — the pure methods never touch `self._manager`:

```python
@pytest.fixture
def tracker():
    return ActiveJobTracker(MagicMock())
```

Time-dependent assertions (`_compute_current_room_elapsed_minutes`,
`_timing_completion_threshold_minutes`) use fixed ISO timestamps passed in via
the `now=` parameter or set on the state object directly, so they stay
deterministic without mocking the clock.

---

### `active_job.py` spatial pipeline (`AJS`, integration)
The transition-room/rollover surface is now covered with seeded capabilities +
a stubbed position read: `_get_robot_position` (sensor read + missing/non-numeric),
`_robot_outside_room_bounds` (inside/outside/no-manager), the access-graph walk
(`_access_graph_path` via `_detect_transition_room_from_position`), and the
`_maybe_roll_current_room_by_timing` slow- and fast-rollover paths (both firing
`EVENT_ROOM_FINISHED`). The suite also exercises the live counter-signal rollover
paths off `_live_boundary_count` / counter-plateau: AJS-9 (a transit hop rolls
live), AJS-10 (the `live_transition.enabled=False` kill-switch), AJS-11 (the
wash-plateau baseline), plus a multipass no-over-roll case — and the charging
delegates.

## Known gaps

`active_job.py` (93%) is considered **done** for this subsystem. The spatial
surface — `_get_robot_position`, `_robot_outside_room_bounds`, the access-graph
walk (`_access_graph_path` via `_detect_transition_room_from_position`), and the
`_maybe_roll_current_room_by_timing` slow / fast / counter-plateau / transit /
wash rollover paths (all firing `EVENT_ROOM_FINISHED`) — and the recharge state
machine (pending → start → in-progress→ended accumulation) are now covered.

What remains uncovered (~8%) is deliberately left and is almost
entirely defensive or edge-only:
- The `_safe_float` `except` branch and the `_position_lock_reliable` non-dict
  caps guard (defensive coercion).
- The `except` paths in `_robot_outside_room_bounds` /
  `_detect_transition_room_from_position` around the bounds-snapshot fetch (both
  marked `# pragma: no cover`) and their `None`-return edge guards.
- `_maybe_roll_current_room_by_timing` early-return edges (`current_room_id`
  None, current room not in the unresolved list, missing current room, stale
  `_pending_fast_rollover`).
- Guards/caps/`except` branches in `record_active_job_sensor_value`,
  `record_counter_sample`, and `_snapshot_settings_selects` (non-dict containers,
  unavailable entities, save-failure swallows, the sample-count cap), the
  `add_update_listener` `_unsub` `ValueError` branch, and the negative-room /
  non-dict guards in `record_completed_room` and `mark_active_job_finalized`.

(The adapter-override merge in `_live_transition_config` — the `enabled` /
`rollover_kinds` / `native_transition_source` reads, lines ~604-612) is now
covered directly by AJ-21/22/23 in `tests/unit/test_jobs_active_job.py`.)

Not worth chasing — see the project note on coverage vs. bug-find rate.

`job_monitor.py` (98%) has two misses: the `typing_extensions` `TypedDict`
import fallback (lines 19–20, a Python-version compatibility shim that never
runs under the supported interpreters), and line 384 in
`_phase_pending_still_live` — an unparseable
`phase_dispatch_pending_since` timestamp is treated as still-live (`return
True`), a real behavior arm (malformed persisted state fails open, presumed
alive) rather than defensive plumbing.

`phase_runner.py` (88%) nearly doubled in size this campaign (398→731
statements) and is now the subsystem's thinnest module — thinner than
`active_job.py`. Its 69 missing lines are spread mostly across the
lower-level timing/aggregation helpers, not concentrated in the watchdog
retry/re-dispatch path: `_segment_group_room_timing` (9),
`_finalize_phase_as_child` (7), `_phase_progress_samples` (6),
`_capture_finishing_phase_timing` (5), `_last_counter_value` and
`_record_phase_to_parent` (4 each) and several smaller helpers account for
49 of the 69 misses, all below line 1448. `_run_advanced_phase` itself has
11 of the remaining misses, `_await_phase_started` has 1, and
`_dispatch_active_phase` has none. Not yet broken down line-by-line the way
`active_job.py`'s gap is above — the natural next pass for this subsystem is
a `--cov-report=term-missing` sweep of this module specifically.

---

## Extending

1. **Start-gate behavior?** Add a `JM-n` target to `test_jobs_job_monitor.py`;
   it's pure, just import and assert.
2. **A new pure tracker method?** Add an `AJ-n` test with the mock-manager
   `tracker` fixture.
3. **The hass-dependent tracking pipeline?** That needs an integration fixture
   (real `hass`, seeded robot-position entities) — see
   [05 §1](../05-gotchas-and-pitfalls.md) for the active-job data layout
   (`data["active_jobs"][vac][map]`).
