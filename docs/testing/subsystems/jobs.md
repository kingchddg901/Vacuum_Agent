# Jobs — Subsystem Test Map

The jobs subsystem owns active-job state and the start-time lifecycle gate:
`job_monitor.py` evaluates whether the vacuum is ready to start, and
`active_job.py` tracks an in-flight job (room rollover, recharge/mop-wash
observations, transition-room detection). Covered by **76 tests across 2 files**.

Source: `custom_components/eufy_vacuum/jobs/`
Architecture reference: [docs/dev/06-job-lifecycle.md](../../dev/06-job-lifecycle.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `job_monitor.py` | 115 | 99% | `tests/unit/test_jobs_job_monitor.py` | unit (pure) |
| `active_job.py` | 576 | 25% | `tests/unit/test_jobs_active_job.py` | unit (pure helpers + mock-manager methods) |

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

### `active_job.py` — active-job tracking (prefix `AJ`, 40 tests)
`active_job.py` is mostly a 1,400-line `ActiveJobTracker` bound to the manager
and hass. The tests cover the **deterministic, hass-free** surface:
- Module helpers: `_safe_int`, `_safe_float`, `_normalize_path_block_action`,
  `_normalize_pause_timeout_minutes`.
- Pure tracker methods (constructed with a `MagicMock` manager):
  `_default_active_job_state`, `_derive_active_job_current_room_id`,
  `_normalize_active_job`, `_compute_current_room_elapsed_minutes`
  (including live-pause subtraction), `_room_name_from_active_job`, and the
  `_timing_completion_threshold_minutes` slack model.

The 25% module number reflects that the rest — recharge/mop-wash observation,
spatial transition-room detection, robot-position reads, and the job-lifecycle
event emission — depends on a live hass with adapter entities and robot-position
sensors. See **Known gaps**.

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

## Known gaps (deferred to a later integration pass)

`active_job.py`'s hass-dependent core is not yet covered:
- `update_active_job_recharge_observation`, `update_active_job_mop_wash_observation`
- `record_active_job_transition`, `_maybe_roll_current_room_by_timing`
- `_robot_outside_room_bounds`, `_get_robot_position`,
  `_detect_transition_room_from_position`
- `_is_charging` / `_is_low_battery_return_state` (delegate to adapter charging)
- listener registration + `_notify`

These need a real `hass` with robot-position sensors and a wired mapping manager
— an integration fixture, not the pure-method approach used here.

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
