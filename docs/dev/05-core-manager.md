# 05 — Core Manager — Central Orchestrator

`EufyVacuumManager` is the single integration-wide runtime object. Every
service call, every entity state read, and every card data request passes
through it. This document explains what the manager owns directly, what it
delegates, how the callback system works, and the rules for extending it.

---

## 1. Design Philosophy

### Orchestrator, not monolith

The manager was originally a monolithic file (~9 400 lines). The bundle-out
refactor extracted 10+ domain subsystems into their own packages while keeping
the manager as the single public API surface. The result is:

- **Callers** (service handlers, entities, listeners) always call
  `manager.<method>()` — they never import subsystem classes directly.
- **Subsystem managers** (e.g. `ProfileManager`, `RunPlanManager`) hold a
  `self._manager` back-reference and are trusted collaborators. They can read
  and write `self._manager.data` directly.
- **The manager** exposes shim methods that delegate to subsystems, plus owns
  a small number of responsibilities that genuinely span multiple subsystems.

### Why a single manager?

All integration data is interdependent. Starting a job requires reading the
queue *and* the payload *and* running preflight rule evaluation *and* writing
an active-job record — atomically from one call site. A per-entity or
per-subsystem design would fragment ownership and require synchronisation. One
writer, one in-memory dict, one save call.

### What stays in the manager vs what delegates

Things that stay in `core/manager.py`:
- `self.data` ownership and `async_save`
- Callback registration and notification firing
- `update_room_fields` (spans profiles, queue, payload, room state, and fires
  multiple notifications)
- `build_queue` / `build_room_payload` (derived-state refresh after room changes)
- `start_selected_rooms` (job start — orchestrates run_plan, active_job, HA
  service call, post-start state clear). `start_run_profile` is now a delegator
  to `ProfileManager` (see below); `build_queue`/`build_room_payload`/
  `start_selected_rooms` stay on the manager and are reached from there via
  `self._manager`.
- `get_job_progress_snapshot` / `get_lifecycle_state` / `get_dashboard_snapshot`
  (cross-cutting read aggregators)
- Room history ingestion methods (see §6)
- Schema migrations that run once at startup

Things that delegate to subsystems:
- Room/map CRUD → `room_map` (`rooms/room_crud.py`)
- Room profiles, run profiles, and run-profile **start** orchestration →
  `profiles` (`profiles/`) — `start_run_profile` (apply the profile, stash the
  charge/wait steps, build queue/payload, dispatch) lives next to
  `apply_run_profile` in `ProfileManager`
- Active job slot CRUD → `active_job` (`jobs/active_job.py`)
- Preflight planning and rule evaluation → `run_plan` (`planning/run_plan.py`)
- Send-side wire dispatch → `dispatch` (`dispatch/manager.py`,
  `DispatchManager`) — `_dispatch_clean_payload`, `dispatch_zone_clean`,
  `_resolve_live_dispatch_payload`, `_run_global_pre_calls`
- External (app-started) run capture / finalize / review →
  `external_run` (`learning/external_run.py`, `ExternalRunManager`) — see §7
- Theme library → `themes` (`themes/`)
- Maintenance / upkeep → `maintenance` (`maintenance/`)
- Dock actions → `dock` (`dock/`)
- Onboarding state machine → `onboarding` (`onboarding/`)
- Access graph → `access_graph` (`rooms/access_graph.py`)
- Strict-order phase execution → `phase_runner` (`jobs/phase_runner.py`)
- Live current-room refresh (Lever B) → `live_room_refresh` (`live_refresh/manager.py`)
- `map_state_source` dispatch and live-pose reads → `map_source`
  (`mapping/map_source_coordinator.py`)

---

## 2. Initialisation Sequence

`async_initialize()` is called once during `__init__.async_setup_entry()`.

```
async_initialize()
├── await self.storage.async_load()          → self.data populated from disk
├── self.data.setdefault(...)                → seed top-level keys
├── drop "icons" block                       → one-time cleanup (removed platform)
├── ThemeManager(self.data)                  → self.themes
├── MaintenanceManager(manager=self)         → self.maintenance
├── DockManager(manager=self)                → self.dock
├── OnboardingManager(data, hass)            → self.onboarding
├── ProfileManager(manager=self)             → self.profiles
├── AccessGraphManager(data, hass)           → self.access_graph
├── ActiveJobTracker(manager=self)           → self.active_job
├── PhaseRunner(manager=self)                → self.phase_runner (after ActiveJobTracker)
├── RunPlanManager(manager=self)             → self.run_plan
├── RoomMapManager(manager=self)             → self.room_map
├── LiveRoomRefreshManager(manager=self)     → self.live_room_refresh
├── MapSourceCoordinator(manager=self)       → self.map_source
├── DispatchManager(manager=self)            → self.dispatch
├── ExternalRunManager(manager=self)         → self.external_run
├── room field backfills (setdefault loop)   → existing rooms get new fields
├── discovery shape migration                → old flat → per-map-id dict
├── _migrate_setup_progress()                → stamps existing installs complete
├── callback lists + cache sets initialised
└── phase_runner.rearm_dock_phase_if_needed  → re-spawn a lost charge_wait/wait
                                               poller for any 'started' dock job
```

All subsystem managers are constructed with a reference to the manager and are
ready to receive calls immediately after `async_initialize()` returns.

### Schema migrations

Two migration classes run on every startup; both are idempotent.

**Room field backfill** — iterates every room in every map bucket and calls
`setdefault` on fields added after initial release: `path_type`,
`is_dock_room`, `is_transition`, `grants_access_to`, `rules`, `floor_type`,
`profile_name`. Also compacts the legacy `floor_type="carpet"` +
`carpet_type` pair into the canonical `"carpet_low_pile"` /
`"carpet_high_pile"` single value.

**`_migrate_setup_progress()`** — vacuums that already had managed rooms
before the setup state machine was introduced get all three legacy steps
(`add_vacuum`, `import_active_map`, `save_rooms`) stamped complete
automatically so they do not see an onboarding prompt on the next start.
Vacuums with no rooms are untouched.

**Future migrations** — the pattern is: `setdefault` for new fields on every
affected record, run on startup, idempotent. There is no migration version
number; migrations gate on data shape, not a stored version counter.

---

## 3. Subsystem Manager Contracts

Each subsystem receives the manager in its constructor and uses it as follows:

| Subsystem | Constructor | Accesses on manager |
|---|---|---|
| `ThemeManager` | `(data)` | `data["theme"]` directly (owns the sub-tree) |
| `MaintenanceManager` | `(manager)` | `self._manager.data`, adapter registry |
| `DockManager` | `(manager)` | `self._manager.hass`, adapter registry |
| `OnboardingManager` | `(data, hass)` | `data["onboarding"]`, `data["discovery"]` |
| `ProfileManager` | `(manager)` | `self._manager.data` |
| `AccessGraphManager` | `(data, hass)` | `data["maps"]` |
| `ActiveJobTracker` | `(manager)` | `self._manager.data`, hass, runtime state |
| `PhaseRunner` | `(manager)` | `self._manager.data["active_jobs"]`, hass, dispatch/save helpers, `_phase_timing` |
| `RunPlanManager` | `(manager)` | `self._manager.*` broadly |
| `RoomMapManager` | `(manager)` | `self._manager.data` |
| `LiveRoomRefreshManager` | `(manager)` | `self._manager.hass`, adapter config (fire-and-forget service pulse) |
| `MapSourceCoordinator` | `(manager)` | `self._manager.hass`, writes `_map_state_source_cache`, shares `_resolve_live_map_image_entity` |
| `DispatchManager` | `(manager)` | `self._manager.hass`, `async_get_map_data_dict`, `map_source`, adapter registry |
| `ExternalRunManager` | `(manager)` | `self._manager` active-job / map / save helpers; holds in-memory grace-timer + re-check state |

**The subsystem/manager write boundary**: subsystem managers write directly
to `self._manager.data[key]` for their own domain keys. They never call
`async_save()` themselves — saving is always the manager's (or the service
handler's) responsibility. The final `await manager.async_save()` call always
lives at the service layer.

**Delegators and shared state that stay on the manager.** For the
bundled-out subsystems the manager keeps thin delegators (called
from production listeners/lifecycle/services, so the entry points stay stable)
and the shared caches/helpers each subsystem reads back through `self._manager`:

- `PhaseRunner` — `maybe_advance_phase()` delegates; the `_PHASE_*` constants
  and `_phase_timing()` (adapter overrides merged over the defaults) stay on
  the manager. `rearm_dock_phase_if_needed()` re-spawns a lost
  `charge_wait`/`wait` poller when the current phase is a dock phase and
  `status=='started'` — called on resume (`active_job.async_resume_active_job`)
  and on load/`async_initialize`, guarded by a `_dock_poller_active` set — so a
  charge/wait run doesn't wedge in `'started'` after a pause+resume or HA restart.
- `LiveRoomRefreshManager` — `maybe_pulse_live_room_refresh()` delegates (the
  job-progress ticker calls it for contiguous runs only).
- `MapSourceCoordinator` — the four async readers `async_refresh_map_state_source`,
  `async_get_map_live_pose`, `async_compare_map_sources`, and
  `async_get_map_render_data` delegate; the `_map_state_source_cache` (read
  on-loop by the snapshot composer and the map-overlays sensor) and
  `_resolve_live_map_image_entity` stay on the manager.
- `DispatchManager` — `_dispatch_clean_payload`, `dispatch_zone_clean`,
  `_resolve_live_dispatch_payload`, and `_run_global_pre_calls` all delegate
  (production callers `start_selected_rooms`, `jobs/phase_runner.py`, the
  mapping/job-control services, and the tests reference `manager.<method>`
  unchanged). The subsystem reads `hass` + the map/room helpers back through
  `self._manager`.
- `ExternalRunManager` — every external-run entry point delegates (`§7`); the
  SHARED room-history ingestion helpers (`_ingest_*_into_room_history`, also
  driven by the normal completed-job finalize) and `_resolve_active_map_id` /
  `start_external_capture` stay in core and are reached via `self._manager`.
  `learning/__init__` exposes `ExternalRunManager` through a lazy `__getattr__`
  (its module imports two constants from `core.manager` at load time — deferring
  the import avoids the cycle during `core.manager`'s own module load).

---

## 4. The Shim Pattern

For every method that now lives in a subsystem, `core/manager.py` exposes a
shim that delegates with `**kwargs`. This keeps all ~80+ service handlers
unchanged — they call `manager.save_user_room_profile(...)` and do not need
to know that `ProfileManager` exists.

```python
# core/manager.py
def save_user_room_profile(self, **kwargs) -> dict[str, Any]:
    """Save one custom room profile — delegates to ProfileManager."""
    return self.profiles.save_user_room_profile(**kwargs)
```

Shims are intentionally thin. Any cross-cutting logic (e.g. firing a
notification after a profile save) stays in the manager method before or
after the subsystem call, not inside the subsystem.

---

## 5. Callback System

The manager is the central notification hub for HA entity refresh. Five
callback channels are maintained as plain Python lists.

| Channel | List name | `_notify_*` method | Subscribers |
|---|---|---|---|
| Room list changed | `_room_update_callbacks` | `_notify_rooms_updated` | switch, number, sensor platforms |
| Run profile changed | `_run_profile_update_callbacks` | `_notify_run_profiles_updated` | button platform |
| Room history updated | `_room_history_update_callbacks` | `_notify_room_history_updated` | sensor platform (room history sensors) |
| Rule status updated | `_room_rule_status_update_callbacks` | `_notify_room_rule_status_updated` | sensor platform (rule status sensors) |
| Theme updated | (owned by ThemeManager) | — | sensor platform (theme sensor) |

### Registration lifecycle

Platform `async_setup_entry` registers callbacks:

```python
manager.register_room_update_callback(_on_rooms_updated)
entry.async_on_unload(
    lambda: manager.unregister_room_update_callback(_on_rooms_updated)
)
```

`entry.async_on_unload` ensures cleanup on config entry reload or unload.

### Notification signature

All `_notify_*` methods pass `vacuum_entity_id` and `map_id` as keyword
arguments. Callbacks receive them and can filter to their relevant entities:

```python
def _on_rooms_updated(*, vacuum_entity_id: str, map_id: str) -> None:
    prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"
    # ... sync entity list for this vacuum/map
```

### Thread safety

Callbacks are called from the HA event loop. If a listener module fires
a notification from a background thread (rare but possible), it must
schedule the entity state write via `hass.loop.call_soon_threadsafe`. The
`_request_entity_state_write` helper in `sensor/__init__.py` handles this.
Callback lists are never mutated outside the event loop.

### `_refresh_room_derived_state`

When room configuration changes (enables, order, profile), this helper
rebuilds the queue and payload snapshots and is always called before
`_notify_rooms_updated`. The queue/payload in `manager.data` are derived
state — always reconstructed from room config, never edited directly.

---

## 6. Direct Responsibilities

These methods live in `core/manager.py` rather than a subsystem because they
orchestrate multiple subsystems or span too many data keys to belong to one.

### `update_room_fields`

The most cross-cutting write in the system. Accepts a room update, applies it
to `data["maps"]`, collapses the `floor_type` + `carpet_type` legacy shape,
applies the appropriate profile, enforces carpet/mop protection rules, updates
the summary, rebuilds derived queue/payload, fires room update callbacks, and
persists. All in one atomic call.

It also accepts a per-room `color` override. Unlike the `bool|None` /
`str|None`-defaulted params (where `None` means "not provided"), `color`
defaults to the module-level `_UNSET = object()` sentinel because `None` is
meaningful for this field: `_UNSET` leaves the existing override untouched,
`None` or an empty string clears the override (empty string coalesces to `None`
so a cleared field is never stored as `""`), and any other value stores the
schema-canonicalized hex. Ref: `manager.py:1233` (param), `manager.py:55`
(`_UNSET` sentinel), `manager.py:1291-1295` (three-way apply logic).

### `start_selected_rooms` (and the `start_run_profile` delegator)

`start_selected_rooms` orchestrates job start: build effective start plan
(run_plan), write active job state (active_job), call upstream vacuum service
(via the `DispatchManager` delegators — `_run_global_pre_calls` →
`_resolve_live_dispatch_payload` → `_dispatch_clean_payload`), clear room
selections post-start, persist. Returns a structured start summary. It stays on
the manager and is reached from `ProfileManager` via `self._manager`.

`start_run_profile` now lives in `ProfileManager` (next to `apply_run_profile`);
the manager keeps only a thin delegator for its service + button-entity callers.
It applies the profile, builds queue/payload, and calls `start_selected_rooms`.
It also stashes the profile's ordered `steps` sequence into
`data["_pending_run_steps"]` before starting, but only when the steps carry a
`charge_wait` or `wait` stop. The plan builder
(`run_plan._build_effective_start_plan`) consumes that stash and materializes a
multi-phase `[clean, charge_wait, clean, …]` job via `_build_steps_phases`
(which now `_safe_int`-coerces each `room_id`, so a bad id no longer crashes
dispatch); absent the stash it builds the single atomic phase as before. A
stepped run with stops is a deliberate sequence, so the plan builder forces
`strict_order=True` (a no-op for order-honoring brands like Eufy, which fold it
back to `False`; on a path-optimizing brand like Roborock it pins each group's
rooms to the shown order). Profiles with no stops (a plain room list) still start
atomically.

The stash is popped deep in `_build_effective_start_plan`, which an early return
(blocked / confirmation-required-without-token / vacuum missing) never reaches —
so `start_run_profile` deletes the leaked stash on any NON-started return, or the
next plain Start on that map would silently pop it and become a charge/wait run.

### `_run_global_pre_calls` (delegated to `DispatchManager`)

Pushes a brand's device-**global** run settings — settings the adapter exposes
only as whole-device state, not per-room payload fields — before an atomic
dispatch. For each adapter-declared `dispatch.global_pre_calls` entry it picks
the run value from the selected rooms' canonical field by the entry's `rank`
(max-wins), maps it to the wire value, and calls the entry's service.
Best-effort: a failed pre-call is logged, never aborts the run. It lives in
`DispatchManager` (`dispatch/manager.py`) with the rest of the send side; the
manager keeps a delegator because `start_selected_rooms` and
`PhaseRunner._dispatch_active_phase` call `manager._run_global_pre_calls`. It
runs **per phase**: `start_selected_rooms` fires it for the first phase, and
`PhaseRunner._dispatch_active_phase` re-runs it for every subsequent phase from
that phase's own rooms — so a stepped run can vacuum one group then mop the next,
each applying its own global setting (e.g. Roborock mop intensity via a
`select`). No-op for adapters that declare none (Eufy, the Roborock S6).

**Mixed-batch safe water.** A device-global water/mop-intensity `select` can't be
zeroed per-room, so a mixed mop + vacuum-only batch that max-wins to the
strongest water would wet-mop the dry rooms. An entry that opts in with
`mixed_mode_water_policy: "safest"` picks the SAFEST (lowest-rank) water for a
mixed batch (≥1 mop room AND ≥1 vacuum-only room) so a dry room is never
wet-mopped (under-mop accepted over wet-mop); a single-mode batch (all-mop or
all-vacuum) keeps max-wins, and the `fan_speed` entry never carries the marker so
suction stays max-wins. Detail:
[22-adapter-config-reference](22-adapter-config-reference.md),
[29-roborock-adapter](29-roborock-adapter.md).

### `get_job_progress_snapshot`

Reads active job state, computes elapsed/expected times per room (active_job),
and emits a timing-only bounds-exit signal (`awaiting_bounds_exit`) — computed
by the composer itself — when `current_room_elapsed_minutes` exceeds the
timing-completion threshold; `mapping_available` / `mapping_used` are always
`False`. Run-anomaly detection (stall / running-long / skipped) and the
one-shot `EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED` emission (deduped per
room per job) are delegated to `ActiveJobTracker.detect_run_anomalies`
(`jobs/active_job.py`), which owns the active-job dict and the dedup state; the
composer hands it the already-resolved locals and reads the anomaly fields back
into the snapshot. It then returns a complete card-ready progress payload.
Still too many concerns to belong to a single subsystem.

When the active phase is a `charge_wait` or `wait` stop (a stepped run docked
between room groups), the composer surfaces the stop so the card shows an
intentional "Charging to X% — ~N min" / "Waiting" state rather than a hung job:
`charge_phase_active` + `charge_target_percent` + `charge_eta_minutes` +
`charge_eta_source` (the ETA from `battery/manager.py`
`compute_time_to_target_pct`, which returns `None` — meaning the card falls back
to a live wall-clock — on a cold-start install rather than fabricating a number),
and `wait_phase_active` + `wait_minutes`.

### `get_dashboard_snapshot`

Aggregates: managed vacuums list, per-vacuum active job state, queue state,
payload state, maintenance state, dock event state, learning estimate, start
status. One call, complete card reload.

### Room history ingestion

`_ingest_completed_job_into_room_history` and
`_ingest_jobs_index_entry_into_room_history` merge completed job records
into `data["room_history"]`. Called from job finalization. The room history
cache (`_room_history_cache_ready`) is a set of vacuum keys that have been
loaded from learning history files via `async_preload_room_history_cache`.
For sensors reading history before the first job finishes, the cache is
populated from disk on sensor platform startup.

---

> **External-run methods** now live in `ExternalRunManager`
> (`learning/external_run.py`); the manager keeps a thin delegator for each so
> the service layer, the lifecycle listener, and the tests still call
> `manager.<method>`. Owned there: `maybe_handle_external_run` +
> `_finalize_external_run` (detect + capture an app-started run, then segment it
> into a pending review record), the `_external_grace_*` timers / checks / cb /
> finalize (defer the finalize until the robot stays docked) + the
> `_extract_return_overhead` helper, and the review-wizard surface
> `confirm_external_run` / `get_external_pending_runs` / `discard_external_run` /
> `resegment_external_run`. `start_external_capture` (active-job tracker) and the
> shared `_ingest_*_into_room_history` helpers stay in core. A confirmed run
> graduates into a normal `jobs/` record. See
> [28-external-run-ingestion](28-external-run-ingestion.md).

## 7. Storage

```python
# All writes:
await manager.async_save()

# All reads:
manager.data["maps"]["vacuum.alfred"]["6"]["rooms"]["1"]
```

`async_save()` delegates to `core/storage.py:EufyVacuumStorage`, which wraps
HA's `Store` helper. Writes are atomic (HA writes to a temp file and renames).

`_async_save_logged()` is a variant used in fire-and-forget contexts (e.g.
background callbacks) that logs exceptions instead of raising them.

The manager never reads from disk after `async_initialize()`. All reads are
against `self.data`. The storage file is the mirror of what was last saved.

---

## 8. `runtime` vs `data`

The manager holds two state containers:

| | `self.data` | `self.runtime` |
|---|---|---|
| Persisted | ✓ | ✗ |
| Loaded at startup | ✓ | Reconstructed from upstream |
| Type | `dict[str, Any]` | `dict[str, VacuumRuntimeState]` |
| Content | All integration config and history | Live vacuum state (HA state string, battery, dock sensors) |
| Written by | Manager + subsystems | `ensure_runtime()` + listener callbacks |

`ensure_runtime(vacuum_entity_id)` is called whenever a listener needs to
read or write live vacuum state. It creates the runtime slot if absent.
Runtime state is never saved to disk — it is rebuilt from upstream entity
state on every HA restart.

---

## 9. Adding a Subsystem

1. Create a package under `custom_components/eufy_vacuum/<name>/`.
2. Add a manager class: `class <Name>Manager: def __init__(self, manager): self._manager = manager`.
3. In `EufyVacuumManager.async_initialize()`, construct and assign:
   `self.<name> = <Name>Manager(manager=self)`.
4. Move the relevant methods from `core/manager.py` into the new class.
5. Add thin shims in `core/manager.py`:
   ```python
   def do_thing(self, **kwargs):
       """Delegate to <Name>Manager."""
       return self.<name>.do_thing(**kwargs)
   ```
6. Existing callers continue to call `manager.do_thing(...)` unchanged.

The key rule: shims are one-liners. Cross-cutting logic that touches multiple
subsystems stays in `core/manager.py`, not inside any subsystem.
