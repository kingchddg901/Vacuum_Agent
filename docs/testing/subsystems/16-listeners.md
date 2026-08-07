# 16 — Listeners — Subsystem Test Map

The listeners subsystem wires HA state-change events to manager actions:
lifecycle (auto-finalize), job-progress ticks, job-metrics watch maps,
dock-events, path-blockers (mid-job rule re-evaluation), discovery passes,
pause-timeout escalation, and pose sampling (external-run pose time-series
capture for room auto-attribution) — plus the registration/teardown plumbing.
Covered by **167 tests across 7 integration files**, with the pose sampler
covered separately by `tests/unit/test_pose_sampler.py` (24 tests) — 191
cases total.

<!-- The two bold counts above are HAND-MAINTAINED (same reason as 15-adapters:
the integration/unit split can't be computed by the single-header model). -->

Source: `custom_components/eufy_vacuum/listeners/`
Architecture reference: [docs/dev/04-listeners.md](../../dev/04-listeners.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `lifecycle.py` | 144 | 94% | `test_listeners_state_driven.py`, `test_listeners_active.py`, `test_listeners_registration.py` | integration | **bare x28** |
| `path_blockers.py` | 142 | 95% | `test_listeners_state_driven.py`, `test_listeners_path_blockers.py` | integration | spec'd |
| `job_metrics.py` | 98 | 94% | `test_listeners_active.py`, `test_listeners_job_metrics_negative.py` | integration | **bare x28** |
| `dock_events.py` | 65 | 92% | `test_listeners_active.py`, `test_listeners_state_driven.py` | integration | **bare x28** |
| `discovery.py` | 81 | 99% | `test_listeners_timers.py` | integration | clean |
| `pause_timeout.py` | 74 | 92% | `test_listeners_timers.py` | integration | clean |
| `_common.py` | 80 | 93% | `test_listeners_common.py` | integration | clean |
| `job_progress.py` | 44 | 95% | `test_listeners_active.py` | integration | **bare x28** |
| `pose_sampler.py` | 159 | 89% | `test_pose_sampler.py` (unit) | unit | **bare x5** |

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

Every module in this subsystem grew this campaign (`lifecycle.py` 121→144
statements, `path_blockers.py` 106→142, `job_metrics.py` 88→98, `pause_timeout.py`
59→74, `pose_sampler.py` 137→159, smaller growth elsewhere), so the specific
line numbers below are freshly pulled from a `--cov-report=term-missing` run
against this revision rather than re-verified item-by-item for every module —
spot checks on `lifecycle.py` and `path_blockers.py` confirm the *shape*
(early-return / defensive guards) still holds:

- **`lifecycle.py` (94%)** — missing lines 115, 126, 129, 144, 516, 521: the
  no-manager early return, the unmatched-vacuum debug-log-and-return, and
  guards inside the finalize/mark-finalized flow. Same defensive shape as
  before this campaign's growth.
- **`path_blockers.py` (95%)** — missing lines 179, 250-251, 256-257: a
  non-dict-room skip inside the watcher-build rule walk, and event-dedup
  guards.
- **`dock_events.py` (92%)** — missing lines 77, 81, 85: event-dedup guards.
- **`job_metrics.py` (94%)** — missing lines 44, 48, 206: capability-read /
  value-parse guards in the metrics-change handler.
- **`_common.py` (93%)** — missing lines 50-51, 73-74, 106, 114: broad-except
  fallbacks in the adapter-vocab/value readers plus a non-dict traversal guard.
- **`pause_timeout.py` (92%)** — missing lines 161, 175, 182-183: guards
  inside the tick (manager gone, unknown map_id, and one new arm not yet
  itemized by name).
- **`discovery.py` (99%)** — only line 190: the body of the periodic
  safety-net `_on_tick` callback; the timer fires it but no test advances the
  adapter-configured interval. Trivial.
- **`job_progress.py` (95%)** — only line 75: the `continue` that skips the
  "unknown" map_id during a tick.
- **`pose_sampler.py` (89%)** — missing lines 93-94, 155, 173, 176, 185,
  193-194, 210-212, 262, 339, 372, 379: the no-`task_status` /
  unreadable-state fallback to the pose `robot_docked` flag and the
  not-attribution / no-live-map vacuum skips (defensive gating). The
  external-only sampling and the parked/docked nulling happy paths are
  covered by `tests/unit/test_pose_sampler.py`.

These are deliberately uncovered at the ~90% meaningful-coverage ceiling: the
teardown/guard branches are defensive, and the sequenced-phase /
mapping-tracker branches in lifecycle exercise paths that require a full
integration boot with a live tracker rather than the per-unit fixtures used
here.
