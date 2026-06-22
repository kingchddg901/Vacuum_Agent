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
- `start_selected_rooms` / `start_run_profile` (job start — orchestrates
  run_plan, active_job, HA service call, post-start state clear)
- `get_job_progress_snapshot` / `get_lifecycle_state` / `get_dashboard_snapshot`
  (cross-cutting read aggregators)
- Room history ingestion methods (see §6)
- Schema migrations that run once at startup

Things that delegate to subsystems:
- Room/map CRUD → `room_map` (`rooms/room_crud.py`)
- Room profiles and run profiles → `profiles` (`profiles/`)
- Active job slot CRUD → `active_job` (`jobs/active_job.py`)
- Preflight planning and rule evaluation → `run_plan` (`planning/run_plan.py`)
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
├── room field backfills (setdefault loop)   → existing rooms get new fields
├── discovery shape migration                → old flat → per-map-id dict
├── _migrate_setup_progress()                → stamps existing installs complete
└── callback lists + cache sets initialised
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

**The subsystem/manager write boundary**: subsystem managers write directly
to `self._manager.data[key]` for their own domain keys. They never call
`async_save()` themselves — saving is always the manager's (or the service
handler's) responsibility. The final `await manager.async_save()` call always
lives at the service layer.

**Delegators and shared state that stay on the manager.** For the three
most-recently bundled-out subsystems the manager keeps thin delegators (called
from production listeners/lifecycle, so the entry points stay stable) and the
shared caches/helpers each subsystem reads back through `self._manager`:

- `PhaseRunner` — `maybe_advance_phase()` delegates; the `_PHASE_*` constants
  and `_phase_timing()` (adapter overrides merged over the defaults) stay on
  the manager.
- `LiveRoomRefreshManager` — `maybe_pulse_live_room_refresh()` delegates (the
  job-progress ticker calls it for contiguous runs only).
- `MapSourceCoordinator` — the four async readers `async_refresh_map_state_source`,
  `async_get_map_live_pose`, `async_compare_map_sources`, and
  `async_get_map_render_data` delegate; the `_map_state_source_cache` (read
  on-loop by the snapshot composer and the map-overlays sensor) and
  `_resolve_live_map_image_entity` stay on the manager.

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

### `start_selected_rooms` / `start_run_profile`

Job start orchestrates: build effective start plan (run_plan), write active
job state (active_job), call upstream vacuum service, clear room selections
post-start, persist. Returns a structured start summary.

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

> **External-run methods.** `maybe_handle_external_run` / `_finalize_external_run`
> (detect + capture an app-started run), `confirm_external_run` /
> `get_external_pending_runs` / `discard_external_run` (the review-card service
> surface), and `start_external_capture` (delegated to the active-job tracker)
> graduate a confirmed external run into a normal `jobs/` record. See
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
