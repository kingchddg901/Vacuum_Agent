# Jobs — Subsystem Test Map

The jobs subsystem owns active-job state and the start-time lifecycle gate:
`job_monitor.py` evaluates whether the vacuum is ready to start, and
`active_job.py` tracks an in-flight job (room rollover, recharge/mop-wash
observations, transition-room detection). Covered by **86 tests across 3 files**.

Source: `custom_components/eufy_vacuum/jobs/`
Architecture reference: [docs/dev/06-job-lifecycle.md](../../dev/06-job-lifecycle.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file(s) | Layer |
|---------------|------:|----:|--------------|-------|
| `job_monitor.py` | 115 | 99% | `tests/unit/test_jobs_job_monitor.py` | unit (pure) |
| `active_job.py` | 577 | 41% | `test_jobs_active_job.py` (unit) + `tests/integration/test_jobs_active_job.py` | unit + integration |

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
`active_job.py` is mostly a 1,400-line `ActiveJobTracker` bound to the manager
and hass. Two layers:
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

The remaining ~59% is the spatial pipeline — see **Known gaps**.

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

## Known gaps

What remains in `active_job.py` is the **spatial transition-room pipeline**,
which needs robot-position sensor entities + a wired mapping manager and adapter
charging vocabulary:
- `_maybe_roll_current_room_by_timing`, `_robot_outside_room_bounds`,
  `_get_robot_position`, `_detect_transition_room_from_position`
- the charging/low-battery branches inside
  `update_active_job_recharge_observation` (delegate to adapter `is_charging` /
  `is_low_battery_return_state`)

These are reachable with a fuller fixture (seeded `robot_position_x/y` entities +
an adapter config exposing them) — a natural next increment.

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
