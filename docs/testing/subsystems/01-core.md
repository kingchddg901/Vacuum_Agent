# 01 — Core — Subsystem Test Map

The core package is the orchestrator: `EufyVacuumManager` ties every subsystem
together and owns the live read surfaces the dashboard polls (lifecycle, job
progress, start-status), plus the storage layer, capability cache, error-tracker
latch, the post-job water amendment, and the brand-agnostic charging /
low-battery-return reads. Covered by **341 tests across 16 files**.

Source: `custom_components/eufy_vacuum/core/`
Architecture reference: [docs/dev/05-core-manager.md](../../dev/05-core-manager.md), [docs/dev/23-error-tracker.md](../../dev/23-error-tracker.md)


### `vacuum_identity.py` — per-vacuum state needs a real vacuum (added 2026-08-08)

Per-vacuum records are created by `setdefault(vacuum_entity_id, ...)` in a dozen
places, and none of them asked whether the id referred to anything. Two records
reached a live install as a result:

| record | how |
|---|---|
| `onboarding["vacuum.your_vacuum"]` | the CARD'S OWN PLACEHOLDER (`src/main.js`), persisted because a status QUERY created the record it was asking about — a read that writes |
| `setup_progress["vacuum.iv"]` | a truncated entity id, carrying a full `completed_steps` / `room_drift_history` record |

Neither corrupted anything, which is why they sat there. The defect is that the set
only ever grew: every typo, placeholder and renamed entity left a record nothing reaps.

Three parts: reads stopped creating (`OnboardingManager._get_map_onboarding(create=False)`),
creation is guarded by `is_real_vacuum`, and a one-shot sweep clears what is already
stored. `test_vacuum_identity.py` (12 tests) pins the shape:

| id | what it holds |
|---|---|
| `VI-1` | a vacuum HA knows is REAL even with no stored record — a NEW vacuum must be addable |
| `VI-2` | a vacuum with a stored record is REAL even if HA forgot it — a rename must not delete history |
| `VI-3` | a placeholder or typo is not real |
| `VI-4` | the sweep removes exactly the orphans, nothing else |
| `VI-5` | **the sweep can never empty `vacuums`** — presence there IS the proof of realness |
| `VI-6` | it runs once; a deliberate re-creation is not re-reaped |
| `VI-7` | planning is pure, so a deletion can be reviewed before it happens |
| `VI-8` | a malformed bucket is skipped rather than taking setup down on boot |

**VI-1 and VI-2 are the pair that matters.** The discriminator is deliberately not
"already known to the manager" — that would make adding a vacuum impossible — nor
"HA has the entity", which would delete a renamed vacuum's history. Either proof
suffices, and VI-5 guards the catastrophic case: if a stored record ever stopped
counting as proof, this sweep would delete every vacuum on the install.

---

### `pause_timeout_migration.py` — lifting a timeout nobody chose (added 2026-08-09)

`test_pause_timeout_migration.py` (7 tests) covers the one-shot repair that raises a
stored `pause_timeout_minutes_default` of 0 to 15.

The bug it repairs is two-part. The default was 0 — the timeout OFF — and no adapter
declared otherwise; and `get_pause_timeout_settings` PERSISTED that fallback on read,
so the first time anything asked, a hard 0 was stamped into the store and "never
configured" became indistinguishable from "deliberately disabled". The consequence is
a paused run that nothing ever closes: the pause reaper owns it, and the pause reaper
was off. Found on a live install on 2026-08-09.

The tests weight the REFUSALS as heavily as the repair, because this migration
knowingly overwrites a value a user could have set through Developer Tools:

- [PTM-2] a configured non-zero value survives — a repair that rewrote every vacuum to
  15 would satisfy the happy path and silently discard every real preference;
- [PTM-3] an ABSENT value stays absent, so the vacuum keeps inheriting the computed
  default. Stamping 15 here would recreate exactly the read-side write-back the repair
  exists to undo — the bug reintroduced by its own fix;
- [PTM-4] the latch holds, so a user who sets it back to 0 afterwards keeps 0;
- [PTM-7] malformed store buckets do not raise, since this runs at startup and a
  throw takes the integration down with it.

Unlike the room-vocabulary repair it needs no adapter declaration to judge a target,
so it cannot be deferred by a provider that has not finished setting up and latches
unconditionally.

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `manager.py` | 2225 | 91% | `test_manager_lifecycle_status.py`, `test_manager_progress.py`, `test_manager_delegation.py`, `test_manager_start_selected.py`, `test_manager_external_finalize.py`, `test_manager_init_migrations.py`, `test_core_manager_registry.py`, `test_manager_compare_sources.py`, `test_manager_live_pose.py`, `test_core_manager_helpers.py` (unit) | int + unit | **bare x10** |
| `error_tracker.py` | 458 | 87% | `test_core_error_tracker.py` | integration | **bare x1** |
| `capabilities.py` | 353 | 91% | `test_core_capabilities.py` | integration | clean |
| `charging.py` | 42 | 100% | `test_charging.py` (unit) | unit | clean |
| `run_state.py` | 15 | 100% | `test_core_run_state.py` (unit) | unit | clean |
| `water_amendment.py` | 123 | 92% | `test_core_water_amendment.py` | integration | clean |
| `storage.py` | 21 | 100% | `test_core_storage.py` | integration | clean |

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
- **Run-state predicate** (`RS`, unit) — `run_state.py`'s brand-agnostic "is
  the robot cleaning right now?" read, sibling of `charging.py`, feeding the
  current-room non-cleaning accumulator: HA-standard non-cleaning states
  recognized for any brand; **fails open** on unknown/unavailable/empty/None;
  paused/idle/error deliberately excluded; an adapter's declared vocabulary
  *extends* the standard set (never replaces it), matched
  case/whitespace-insensitively, with a malformed declaration falling back to
  the standard set.
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

`manager.py` (94%, 2113 total statements this campaign, up from a
1850-statement baseline — a ~14% growth) — the external-run
capture/review orchestration (`maybe_handle_external_run` /
`_external_grace_finalize` / `confirm` / `resegment` /
`get_external_pending_runs` / `discard`), the room-history ingest helpers, the
registry-model backfill, the init migrations, the job/dock delegations, and
the progress snapshot are covered (the EXT-*, CMR-*, init-migration,
delegation, and progress suites). What's left is 89 missed statements + 74
partial branches (`--cov-report=term-missing` for the current line list) —
still mostly the defensive tail (`# pragma: no cover` best-effort log-only
excepts, malformed-input guards, the recorder-dependent return-overhead
extraction skipped when no recorder is configured under test), but the file's
growth means this list has not been re-itemized line-by-line since the count
last stood at ~16 lines; treat the qualitative description as directional, not
exhaustive.

The remaining per-module gaps are within the held ceiling: `error_tracker.py`
(87%) and `water_amendment.py` (92%) are short of the others only on defensive
except/guard paths; `capabilities.py` (95%), `charging.py` (100%),
`run_state.py` (100%) and `storage.py` (100%) are effectively complete.
