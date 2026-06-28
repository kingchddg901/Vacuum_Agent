# 01 — Core — Subsystem Test Map

The core package is the orchestrator: `EufyVacuumManager` ties every subsystem
together and owns the live read surfaces the dashboard polls (lifecycle, job
progress, start-status), plus the storage layer, capability cache, error-tracker
latch, the post-job water amendment, and the brand-agnostic charging /
low-battery-return reads. Covered by **243 tests across 15 files**.

Source: `custom_components/eufy_vacuum/core/`
Architecture reference: [docs/dev/05-core-manager.md](../../dev/05-core-manager.md), [docs/dev/23-error-tracker.md](../../dev/23-error-tracker.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 1690 | 97% | `test_manager_lifecycle_status.py`, `test_manager_progress.py`, `test_manager_delegation.py`, `test_manager_start_selected.py`, `test_manager_external_finalize.py`, `test_manager_init_migrations.py`, `test_core_manager_registry.py`, `test_manager_compare_sources.py`, `test_manager_live_pose.py`, `test_core_manager_helpers.py` (unit) | int + unit |
| `error_tracker.py` | 316 | 89% | `test_core_error_tracker.py` | integration |
| `capabilities.py` | 118 | 97% | `test_core_capabilities.py` | integration |
| `charging.py` | 39 | 100% | `test_charging.py` (unit) | unit |
| `water_amendment.py` | 120 | 92% | `test_core_water_amendment.py` | integration |
| `storage.py` | 17 | 100% | `test_core_storage.py` | integration |

`manager.py` is the single largest module in the codebase; most of its public
surface delegates to a subsystem (see [the delegation seam](#whats-tested)),
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
  and **run-anomaly detection**. The anomaly logic + event emission live in
  `ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py`); the snapshot
  composer calls it (`self.active_job.detect_run_anomalies(...)`) and folds the
  returned fields in. Three anomalies are covered: **stall** (bounds gate blocking
  and the room stuck ≥ 2× its estimate — fires `EVENT_STALL_DETECTED` once per
  room per job), **running_long** (the soft band 1.5×–2× below stall, no event),
  and **skipped** (a queued room advanced past but not completed — fires
  `EVENT_ROOM_SKIPPED` once per room per job). `test_manager_progress.py`
  exercises all three through the manager.
- **Finalize bridge** (`PR`) — `finalize_learning_for_active_job`: no-learning →
  None, missing `started_at` → not finalized, full job → `completed_job`.
- **Room-history ingest** — `_ingest_jobs_index_entry_into_room_history`
  (newer-wins merge, bad-row skips).
- **Pure helpers** (`CMH`, unit) — `_safe_float`, `_safe_int`,
  `_normalize_path_block_action`, `_hours_text`, `_display_label`,
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

`manager.py` (97%) — the external-run capture/review orchestration
(`maybe_handle_external_run` / `_external_grace_finalize` / `confirm` /
`resegment` / `get_external_pending_runs` / `discard`), the room-history ingest
helpers, the registry-model backfill, the init migrations, the job/dock
delegations, and the progress snapshot are now all covered (the EXT-*, CMR-*,
init-migration, delegation, and progress suites). What's left (~2%, ~16 lines) is
the defensive tail: `# pragma: no cover` best-effort log-only excepts
(`_async_save_logged`, `_refresh_room_derived_state`, a defensive read inside
`get_lifecycle_state`), a few malformed-input guards, the
recorder-dependent return-overhead extraction (skipped when no recorder is
configured under test), and a handful of not-taken partial branches. The
`_notify_*` fan-out excepts (`MD-7`) and the snapshot-degrade except (`SS-7`) are
covered because they escape into behavior.

The remaining per-module gaps are within the held ceiling: `error_tracker.py`
(89%) and `water_amendment.py` (92%) are short of the others only on defensive
except/guard paths; `capabilities.py` (97%), `charging.py` (100%) and
`storage.py` (100%) are effectively complete.
