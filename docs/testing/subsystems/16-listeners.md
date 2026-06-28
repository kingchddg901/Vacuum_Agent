# 16 — Listeners — Subsystem Test Map

The listeners subsystem wires HA state-change events to manager actions:
lifecycle (auto-finalize), job-progress ticks, job-metrics watch maps,
dock-events, path-blockers (mid-job rule re-evaluation), discovery passes,
pause-timeout escalation, and pose sampling (external-run pose time-series
capture for room auto-attribution) — plus the registration/teardown plumbing.
Covered by **80 tests across 7 integration files**, with the pose sampler
covered separately by `tests/unit/test_pose_sampler.py` (14 tests).

Source: `custom_components/eufy_vacuum/listeners/`
Architecture reference: [docs/dev/04-listeners.md](../../dev/04-listeners.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `lifecycle.py` | 121 | 95% | `test_listeners_state_driven.py`, `test_listeners_active.py`, `test_listeners_registration.py` | integration |
| `path_blockers.py` | 103 | 99% | `test_listeners_state_driven.py`, `test_listeners_path_blockers.py` | integration |
| `job_metrics.py` | 82 | 92% | `test_listeners_active.py`, `test_listeners_job_metrics_negative.py` | integration |
| `dock_events.py` | 64 | 90% | `test_listeners_active.py`, `test_listeners_state_driven.py` | integration |
| `discovery.py` | 72 | 99% | `test_listeners_timers.py` | integration |
| `pause_timeout.py` | 48 | 94% | `test_listeners_timers.py` | integration |
| `_common.py` | 72 | 94% | `test_listeners_common.py` | integration |
| `job_progress.py` | 43 | 95% | `test_listeners_active.py` | integration |
| `pose_sampler.py` | 91 | 90% | `test_pose_sampler.py` (unit) | unit |

---

## What's tested

- **Registration / teardown** (`test_listeners_registration`) — each listener
  family registers its state-change subscriptions and unregisters cleanly.
- **State-driven actions** (`test_listeners_state_driven`) — a vacuum state
  change drives lifecycle auto-finalize and path-blocker re-evaluation.
- **Active watch maps** (`test_listeners_active`) — dock-event recording,
  job-metrics entity watch construction.
- **Timers** (`test_listeners_timers`) — the discovery pass and pause-timeout
  escalation fire on their timer callbacks.
- **Shared helpers** (`test_listeners_common`) — `_common.py` dispatch utilities.
- **Path-blocker actions** (`test_listeners_path_blockers`) — a matched
  mid-job blocker rule drives the pause / cancel / event action and the
  watcher-build filtering that drops malformed/disabled/non-blocker rules.
- **Job-metrics negative/guard paths** (`test_listeners_job_metrics_negative`)
  — the metrics-change handler's entry-miss / no-state / unavailable / manager-gone
  and value-parse (`ValueError`) guards.
- **Pose sampling** (`test_pose_sampler`, unit) — external-run pose time-series
  capture: parked/docked nulling of `current_room`/`anchor` via MQTT `task_status`
  (with the pose `robot_docked` flag as fallback), cadence resolution from the
  adapter's `room_attribution` block, and the external-only + live-pose-only gating.

---

## How it's tested

The `manager` / `manager_with_services` fixtures plus `hass.states.async_set`
to drive events and `hass.async_block_till_done()` to flush. The unsubscribe
teardown excepts are best-effort (`# pragma: no cover`).

---

## Known gaps

The uncovered lines are dominated by best-effort teardown/guard branches that
are intentionally left uncovered (`# pragma: no cover` on the unsubscribe
excepts), early-return guards on malformed/duplicate events, and a few
adapter-config sub-branches:

- **`lifecycle.py` (95%)** — the remaining misses are early-return guards
  (no manager / no matched vacuum) and the executor-job wrapper around the
  tracker's `end_job` (defensive). The mid-job `mapping_tracker.start_job`
  branch and the post-job mop-water amendment registration (gated on a
  finalized mop job) are now covered by `test_listeners_active.py`. The
  auto-finalize except is `# pragma: no cover - best-effort auto-finalize`.
- **`path_blockers.py` (99%)** — watcher-build filter branches that drop
  malformed/disabled/non-blocker rules (73, 76, 78, 81) and event-dedup guards
  (109, 111, 115, 131, 139: empty/unwatched entity, no new_state, unchanged
  state, non-dict report, already-paused). All defensive filtering.
- **`dock_events.py` (90%)** — event-dedup guards (69 no new_state, 75
  unchanged value, 79 unwatched entity, 83 manager gone). The `last_dry_start`
  dry-duration capture sub-branch (98-105) is now covered by
  `test_listeners_state_driven.py`; the remaining misses are the defensive
  dedup guards.
- **`job_metrics.py` (97%)** — the metrics-change handler's value-parse path
  (94-95 capability-read except, 106/110/113 entry-miss / no-state /
  unavailable guards, 118/122-123 manager-gone and `ValueError` guards). The
  happy-path record-and-counter-sample below is covered; the misses are guards.
- **`_common.py` (94%)** — the broad-except fallbacks in `get_adapter_vocab`
  (45-46) and `get_adapter_value` (72-73), plus the non-dict traversal guard
  (67). Defensive registry-lookup safety nets.
- **`pause_timeout.py` (94%)** — two guards inside the tick (56 manager gone,
  63 skip "unknown" map_id).
- **`discovery.py` (99%)** — only line 150, the body of the periodic
  safety-net `_on_tick` callback (`_run_pass()`); the timer fires it but no test
  advances the adapter-configured interval. Trivial.
- **`job_progress.py` (95%)** — only line 68, the `continue` that skips the
  "unknown" map_id during a tick.
- **`pose_sampler.py` (90%)** — the misses are the no-`task_status` /
  unreadable-state fallback to the pose `robot_docked` flag and the
  not-attribution / no-live-map vacuum skips (defensive gating). The
  external-only sampling and the parked/docked nulling happy paths are
  covered by `tests/unit/test_pose_sampler.py`.

These are deliberately uncovered at the ~90% meaningful-coverage ceiling: the
teardown/guard branches are defensive, and the sequenced-phase /
mapping-tracker branches in lifecycle exercise paths that require a full
integration boot with a live tracker rather than the per-unit fixtures used
here.
