# 16 — Listeners — Subsystem Test Map

The listeners subsystem wires HA state-change events to manager actions:
lifecycle (auto-finalize), job-progress ticks, job-metrics watch maps,
dock-events, path-blockers (mid-job rule re-evaluation), discovery passes, and
pause-timeout escalation — plus the registration/teardown plumbing. Covered by
**75 tests across 5 files**.

Source: `custom_components/eufy_vacuum/listeners/`
Architecture reference: [docs/dev/04-listeners.md](../../dev/04-listeners.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `lifecycle.py` | 113 | 85% | `test_listeners_state_driven.py`, `test_listeners_active.py` | integration |
| `path_blockers.py` | 103 | 86% | `test_listeners_state_driven.py` | integration |
| `job_metrics.py` | 65 | 86% | `test_listeners_active.py` | integration |
| `dock_events.py` | 64 | 82% | `test_listeners_active.py` | integration |
| `discovery.py` | 69 | 99% | `test_listeners_timers.py` | integration |
| `pause_timeout.py` | 48 | 94% | `test_listeners_timers.py` | integration |
| `_common.py` | 56 | 92% | `test_listeners_common.py` | integration |

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

`discovery.py` (79%) and `dock_events.py` (82%) leave the position-listener
wiring that needs live robot-position entities firing real state events — the
file docstrings defer that to a full integration boot — plus best-effort
teardown/guard branches.
