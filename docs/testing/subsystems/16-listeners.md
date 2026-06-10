# 16 — Listeners — Subsystem Test Map

The listeners subsystem wires HA state-change events to manager actions:
lifecycle (auto-finalize), job-progress ticks, job-metrics watch maps,
dock-events, path-blockers (mid-job rule re-evaluation), discovery passes, and
pause-timeout escalation — plus the registration/teardown plumbing. Covered by
**61 tests across 4 files**.

Source: `custom_components/eufy_vacuum/listeners/`
Architecture reference: [docs/dev/04-listeners.md](../../dev/04-listeners.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `lifecycle.py` | 116 | 88% | `test_listeners_state_driven.py`, `test_listeners_active.py` | integration |
| `path_blockers.py` | 103 | 86% | `test_listeners_state_driven.py` | integration |
| `job_metrics.py` | 67 | 86% | `test_listeners_active.py` | integration |
| `dock_events.py` | 64 | 90% | `test_listeners_active.py` | integration |
| `discovery.py` | 69 | 99% | `test_listeners_timers.py` | integration |
| `pause_timeout.py` | 48 | 94% | `test_listeners_timers.py` | integration |
| `_common.py` | 56 | 92% | `test_listeners_common.py` | integration |
| `job_progress.py` | 40 | 96% | `test_listeners_active.py` | integration |

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

- **`lifecycle.py` (88%)** — the largest real gap. Missing the mid-job
  `mapping_tracker.start_job` branch (187-211, fires only when active-lifecycle
  is first observed and no tracker job exists yet). The post-job mop-water
  amendment registration (319-331, gated on a finalized mop job) is now covered
  by `test_listeners_active.py`. The remaining misses (100, 108, 123,
  187/193/196/204, 251-252, 280) are early-return guards (no manager / no
  matched vacuum), the executor-job wrappers around the tracker's start/end
  (defensive), and the `maybe_advance_phase` sequenced-job branch (251-252, no
  adapter ships sequenced jobs today). The auto-finalize except (268) is
  `# pragma: no cover`.
- **`path_blockers.py` (86%)** — watcher-build filter branches that drop
  malformed/disabled/non-blocker rules (73, 76, 78, 81) and event-dedup guards
  (109, 111, 115, 131, 139: empty/unwatched entity, no new_state, unchanged
  state, non-dict report, already-paused). All defensive filtering.
- **`dock_events.py` (90%)** — event-dedup guards (69 no new_state, 75
  unchanged value, 79 unwatched entity, 83 manager gone). The `last_dry_start`
  dry-duration capture sub-branch (98-105) is now covered by
  `test_listeners_state_driven.py`; the remaining misses are the defensive
  dedup guards.
- **`job_metrics.py` (86%)** — the metrics-change handler's value-parse path
  (94-95 capability-read except, 106/110/113 entry-miss / no-state /
  unavailable guards, 118/122-123 manager-gone and `ValueError` guards). The
  happy-path record-and-counter-sample below is covered; the misses are guards.
- **`_common.py` (92%)** — the broad-except fallbacks in `get_adapter_vocab`
  (45-46) and `get_adapter_value` (72-73), plus the non-dict traversal guard
  (67). Defensive registry-lookup safety nets.
- **`pause_timeout.py` (94%)** — two guards inside the tick (56 manager gone,
  63 skip "unknown" map_id).
- **`discovery.py` (99%)** — only line 150, the body of the periodic
  safety-net `_on_tick` callback (`_run_pass()`); the timer fires it but no test
  advances the adapter-configured interval. Trivial.
- **`job_progress.py` (96%)** — only line 68, the `continue` that skips the
  "unknown" map_id during a tick.

These are deliberately uncovered at the ~90% meaningful-coverage ceiling: the
teardown/guard branches are defensive, and the sequenced-phase /
mapping-tracker branches in lifecycle exercise paths that require a full
integration boot with a live tracker rather than the per-unit fixtures used
here.
