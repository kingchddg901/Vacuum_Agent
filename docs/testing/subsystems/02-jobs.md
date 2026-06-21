# Jobs — Subsystem Test Map

The jobs subsystem owns active-job state and the start-time lifecycle gate:
`job_monitor.py` evaluates whether the vacuum is ready to start, and
`active_job.py` tracks an in-flight job (room rollover, recharge/mop-wash
observations, transition-room detection). Covered by **116 tests across 3 files**.

Source: `custom_components/eufy_vacuum/jobs/`
Architecture reference: [docs/dev/06-job-lifecycle.md](../../dev/06-job-lifecycle.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file(s) | Layer |
|---------------|------:|----:|--------------|-------|
| `job_monitor.py` | 115 | 99% | `tests/unit/test_jobs_job_monitor.py` | unit (pure) |
| `active_job.py` | 867 | 93% | `test_jobs_active_job.py` (unit) + `test_jobs_active_job.py` + `test_jobs_active_job_spatial.py` (integration) | unit + integration |

---

## What's tested

### `job_monitor.py` — start-gate evaluation (prefix `JM`, 36 tests)
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
`active_job.py` is a 1,673-line file that is mostly the `ActiveJobTracker` class
(lines 104-1673), bound to the manager and hass. Two layers:
- **`AJ` (unit, `MagicMock` manager)** — module helpers (`_safe_int`,
  `_normalize_path_block_action`, …) and the pure tracker methods:
  `_default_active_job_state`, `_derive_active_job_current_room_id`,
  `_normalize_active_job`, `_compute_current_room_elapsed_minutes`,
  `_room_name_from_active_job`, `_timing_completion_threshold_minutes`.
- **`AJI` (integration, real `manager` fixture + seeded active job)** —
  `get_active_job`, the mop-wash observation (count + 60s debounce),
  `record_active_job_transition` (append/ignore-noise/cap-12),
  `record_active_lifecycle_observed`, `record_active_job_sensor_value`,
  `add_update_listener`/`_notify`, and `update_active_job_recharge_observation`.

> The recharge test surfaced a real bug: the method called
> `hass.states.get(None)` when the adapter has no `task_status` entity. Fixed
> with the same `if entity_id else None` guard already applied in `core/manager`
> and `run_plan`.

The spatial pipeline is now covered (see the `AJS` integration suite below); the
remaining ~8% is defensive guards and edge branches — see **Known gaps**.

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

`active_job.py` (92%) is considered **done** for this subsystem. The spatial
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

`job_monitor.py` (99%) — the only miss is the `typing_extensions` `TypedDict`
import fallback (lines 19–20), a Python-version compatibility shim that never
runs under the supported interpreters.

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
