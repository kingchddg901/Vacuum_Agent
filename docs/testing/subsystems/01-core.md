# 01 — Core — Subsystem Test Map

The core package is the orchestrator: `EufyVacuumManager` ties every subsystem
together and owns the live read surfaces the dashboard polls (lifecycle, job
progress, start-status), plus the storage layer, capability cache, error-tracker
latch, and the post-job water amendment. Covered by **57 tests across 8 files**.

Source: `custom_components/eufy_vacuum/core/`
Architecture reference: [docs/dev/05-core-manager.md](../../dev/05-core-manager.md), [docs/dev/23-error-tracker.md](../../dev/23-error-tracker.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 1238 | 86% | `test_manager_lifecycle_status.py`, `test_manager_progress.py`, `test_manager_delegation.py`, `test_core_manager_helpers.py` (unit) | int + unit |
| `error_tracker.py` | 317 | 88% | `test_core_error_tracker.py` | integration |
| `capabilities.py` | 122 | 97% | `test_core_capabilities.py` | integration |
| `water_amendment.py` | 118 | 92% | `test_core_water_amendment.py` | integration |
| `storage.py` | 17 | 100% | `test_core_storage.py` | integration |

`manager.py` is the single largest module in the codebase; most of its public
surface delegates to a subsystem (see [the delegation seam](#delegation-seams)),
so its own tests target the logic that genuinely lives in the orchestrator.

---

## What's tested

- **Lifecycle + error overlay** (`LS`) — `get_lifecycle_state` folds the
  ErrorTracker active-run latch into the user-visible message: a live
  `current_message` wins; a blank current message with error history derives a
  "Run had N error(s); last: …" summary.
- **Start-status gates** (`LS`) — `get_start_status` blocks a new run on a paused
  job (`job_paused`), incomplete floor-type onboarding (`onboarding_required`),
  and every-selected-room-blocked (`all_selected_rooms_blocked`, reached by
  building a complete access graph so rule-bearing rooms clear the graph gate).
- **Live job progress** (`PR`) — `get_job_progress_snapshot`: idle terminal
  snapshot, started timeline (estimate / reanchored), completed-room reanchor,
  and **stall detection** (a single-room job stuck ≥ 2× its estimate fires
  `EVENT_STALL_DETECTED` exactly once, deduped per room).
- **Finalize bridge** (`PR`) — `finalize_learning_for_active_job`: no-learning →
  None, missing `started_at` → not finalized, full job → `completed_job`.
- **Room-history ingest** — `_ingest_jobs_index_entry_into_room_history`
  (newer-wins merge, bad-row skips).
- **Pure helpers** (`CMH`, unit) — `_safe_float`, `_hours_text`,
  `_settings_profile_display`.
- **Delegation seams** (`MD`) — every thin forwarder (`return self.<sub>.x(...)`)
  is smoke-tested through the manager so a delegation lost in a refactor fails
  loudly. This is the **#11 / #13 bug-class net** (a forwarder that went missing
  while a listener still called it).
- **ErrorTracker** (`ET`) — latch lifecycle, secondary-error detection.
- **Capabilities / storage / water amendment** — capability resolution + cache,
  the persistent store round-trip, and the post-job water patch.

---

## How it's tested

Driven against the real `manager` fixture (`tests/integration/conftest.py`). The
error overlay uses a recording `_FakeErrorTracker` registered at
`hass.data[DOMAIN][DATA_ERROR_TRACKER]`. Progress tests wire a real
`LearningManager` and seed an active job with `_seed_job(...)`. The delegation
smoke test calls each seam with minimal valid args and asserts it forwards
without `AttributeError`.

---

## Known gaps

`manager.py` (86%) — the remainder is `async_setup_entry`-class wiring reachable
only on a full integration boot, defensive `continue` / `return []` guards that
skip malformed input, and one confirmed **dead branch** (the current-room
backfill at `manager.py:2540-2546`: its `current_room_id is None` and
non-empty-`unresolved_room_ids` conditions are mutually exclusive). Pure
best-effort log-only excepts (`_async_save_logged`, `_refresh_room_derived_state`)
carry `# pragma: no cover`. Deliberately measured: the `_notify_*` fan-out
excepts (skip-one-continue resilience, `MD-7`) and the snapshot-degrade except
(`SS-7`) — both escape into behavior.
