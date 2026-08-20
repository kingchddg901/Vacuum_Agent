# 01 — Architecture Overview

This document describes the full system architecture of `eufy_vacuum` (the Home
Assistant custom integration) and `eufy-vacuum-command-center` (the companion
Lovelace card). It is written for developers who want to extend, contribute to,
or port the system to a different vacuum ecosystem.

---

## Table of Contents

1. [System Boundaries](#1-system-boundaries)
2. [Integration Internal Layers](#2-integration-internal-layers)
3. [Subsystem Package Map](#3-subsystem-package-map)
4. [Startup Sequence](#4-startup-sequence)
5. [Data Flow — Job Start to Finish](#5-data-flow--job-start-to-finish)
6. [State Persistence](#6-state-persistence)
7. [The Adapter Pattern](#7-the-adapter-pattern)
8. [Listener Architecture](#8-listener-architecture)
9. [Service Layer](#9-service-layer)
10. [Entity Layer](#10-entity-layer)
11. [Concurrency & Thread Safety](#11-concurrency--thread-safety)
12. [Extension Points](#12-extension-points)

---

## 1. System Boundaries

### What the integration is

`eufy_vacuum` is a Home Assistant custom integration that sits **on top of** an
upstream vacuum integration (currently Eufy via `robovac_mqtt`). Its purpose is
to add a complete job-management, learning, and configuration layer that the bare
upstream entities do not provide.

It owns:

- Managed room configuration (order, per-room clean settings, profiles, rules)
- A queue engine that assembles multi-room job payloads
- Active job lifecycle tracking (start → monitor → auto-finalize)
- A learning / ETA estimation system backed by per-job JSON files on disk
- A theme system for the companion card
- A mapping subsystem (image-based room segmentation, custom named layouts, the
  live map source, and point-in-polygon zone membership)
- Native current-room tracking (per-room completion + dwell fired off the device's
  current-room signal, not learned coordinates)
- Battery health tracking (cycle counts, charge rates, degradation metrics)
- All HA entities that surface integration state into the entity registry
- HA service endpoints consumed by the Lovelace card

### What the integration is not

`eufy_vacuum` does **not**:

- Communicate directly with Eufy cloud or vacuum hardware. All hardware
  interaction goes through the upstream vacuum entity and its companion sensors.
- Replace the upstream integration. It subscribes to state-change events on
  entities that the upstream integration creates.
- Bundle the Lovelace card. The card is a separate JS project
  (`eufy-vacuum-command-center`). The integration serves the compiled card JS
  as a static file at `/eufy_vacuum/frontend/`, but the two projects are
  independently versioned.

### External dependencies

| Dependency | Role |
|---|---|
| Upstream vacuum integration | Hardware control, raw position sensors, battery level |
| HA `Store` helper | Persistent JSON storage at `.storage/eufy_vacuum` |
| HA `async_add_executor_job` | Off-loop disk I/O for learning history files |
| HA event bus | Inbound state changes; outbound job/room events |
| HA service registry | All ~80+ service endpoints |

No third-party Python packages are required (`requirements` is empty).

---

## 2. Integration Internal Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  Lovelace Card  (eufy-vacuum-command-center)                        │
│  JavaScript — actions / state / renderers / bindings / styles       │
└────────────────────────┬────────────────────────────────────────────┘
                         │  HA WebSocket service calls
┌────────────────────────▼────────────────────────────────────────────┐
│  Service Layer  (services/, learning/services.py,                   │
│                  themes/services.py, mapping/mapping_services.py)   │
│  ~100+ named services — validate input, call manager, return payload│
└────────────────────────┬────────────────────────────────────────────┘
                         │  method calls
┌────────────────────────▼────────────────────────────────────────────┐
│  core/manager.py — EufyVacuumManager (orchestrator)                │
│  Owns self.data (in-memory mirror of .storage), self.runtime        │
│  Delegates deep logic to subsystem manager objects                  │
│                                                                     │
│  Subsystems (each a manager class, holds a back-reference):         │
│  themes · maintenance · dock · onboarding · profiles                │
│  access_graph · active_job · phase_runner · run_plan · room_map     │
│  live_room_refresh · map_source · dispatch · external_run           │
└──┬───────────┬──────────┬────────────────────┬───────────────────┬──┘
   │           │          │                    │                   │
   ▼           ▼          ▼                    ▼                   ▼
battery/   mapping/  learning/            listeners/         HA entities
manager    manager   manager              (9 modules)        (sensor/,
BatteryH   Mapping   LearningM            each owns          switch/,
ealthMgr   Manager   anager               its listener       button/,
                                          lifecycle)         number/,
                                                             select/,
                                                             binary_sensor)
```

The key insight: **`EufyVacuumManager` owns `self.data`, and `async_save()` is the
only way anything reaches disk** — but it is not the only thing that writes the dict.
Subsystem managers hold a `self._manager` back-reference and write
`self._manager.data[key]` directly. They are trusted collaborators rather than external
consumers, and treating every write as a manager method would be ceremony.

The boundary is looser than that description implies, and it is worth knowing before
you go looking for where a value is set. **Two entity classes write the store
directly:** `MaintenanceIntervalNumber.async_set_native_value` (`number.py`) builds the
`maintenance` path and assigns `interval_hours` without going through
`maintenance/manager.py`, and `EufyVacuumRoomEntity._async_update_room`
(`room_entities.py`) merges room fields into `data["maps"]`. Three service modules do
the same. So "who writes this key?" has more answers than the layer diagram suggests,
and the maintenance bucket in particular has a second writer sitting outside the
subsystem that owns it.

---

## 3. Subsystem Package Map

Every directory under `custom_components/eufy_vacuum/` is either a HA platform
module (flat file) or a subsystem package. Here is the full map:

### Core orchestration

| Package / file | Role |
|---|---|
| `core/manager.py` | `EufyVacuumManager` — singleton orchestrator, storage owner, callback hub |
| `core/storage.py` | HA `Store` wrapper (`async_load` / `async_save`) |
| `core/capabilities.py` | Reads upstream entities to populate `data["capabilities"]` |
| `core/error_tracker.py` | `ErrorTracker` — latches vacuum errors, persists across restarts |
| `core/water_amendment.py` | Mopping water-level protection rules |
| `core/charging.py` | Brand-agnostic battery-level / charging-state / low-battery-return reads from adapter-declared entities |

### Subsystem managers (all constructed in `manager.async_initialize()`)

| Object | Package | Owns |
|---|---|---|
| `manager.themes` | `themes/` | `data["theme"]` — library, working draft, active theme |
| `manager.maintenance` | `maintenance/` | Upkeep metadata, replacement discovery, reset snapshots |
| `manager.dock` | `dock/` | Dock action dispatch and dock event recording |
| `manager.onboarding` | `onboarding/` | `data["onboarding"]`, setup progress state machine |
| `manager.profiles` | `profiles/` | Room profiles and run profiles CRUD; also owns the run-profile START orchestration (`start_run_profile` — apply the profile, stash charge/wait steps, dispatch), next to `apply_run_profile` (core keeps a `start_run_profile` delegator; `start_selected_rooms` + `build_queue`/`build_room_payload` stay on the core manager) |
| `manager.access_graph` | `rooms/access_graph.py` | Room-to-room access graph (grants_access_to) |
| `manager.active_job` | `jobs/active_job.py` | Active job slot CRUD and finalization handoff |
| `manager.phase_runner` | `jobs/phase_runner.py` | Sequenced phase execution — per-phase watchdog (settle/dispatch/verify/retry) + per-phase timing + per-phase global-pre-call dispatch; also runs the `charge_wait` (`_run_charge_wait_phase` — dock, poll battery to `target_battery_percent`) and `wait` (`_run_wait_phase` — dock, hold `wait_minutes`) break phases via `maybe_advance_phase`, guarding the intentional dock with `_phase_dispatch_pending` |
| `manager.run_plan` | `planning/run_plan.py` | Preflight rule evaluation, effective start plan; materializes a run profile's ordered `steps` (room groups + charge/wait stops) into `active_job["phases"]` via `_build_steps_phases`, forcing `strict_order` when the run carries stops |
| `manager.room_map` | `rooms/room_crud.py` | Room and map CRUD operations |
| `manager.live_room_refresh` | `live_refresh/manager.py` | Lever B contiguous-run live current-room refresh (rate-limit + sticky-disable + local-connection pulse) |
| `manager.map_source` | `mapping/map_source_coordinator.py` | `map_state_source` backend dispatch (provider segmentation + live-pose reads) |
| `manager.dispatch` | `dispatch/manager.py` | Send-side wire dispatch: `_dispatch_clean_payload`, `dispatch_zone_clean`, `_resolve_live_dispatch_payload`, `_run_global_pre_calls` (all four moved out of core; the manager keeps a thin delegator for each) |
| `manager.external_run` | `learning/external_run.py` | External (app-started) run capture/finalize: `maybe_handle_external_run`, `_finalize_external_run`, `confirm_external_run`, `get_external_pending_runs`, `discard_external_run`, `resegment_external_run`, the `_external_grace_*` timers/checks/finalize, `_extract_return_overhead` (the manager keeps a thin delegator for each). The `_ingest_*_into_room_history` helpers STAY in core — they are shared with the normal finalize path. `learning/__init__` imports `ExternalRunManager` **directly** — the old import-cycle-driven lazy `__getattr__` is gone: the grace-timer constants moved to `learning/constants.py`, and `external_run.py`'s only `core.manager` import is `TYPE_CHECKING`-guarded |

### Entry-point singletons (constructed in `__init__.async_setup_entry()`)

| Object | Key in `hass.data[DOMAIN]` | Role |
|---|---|---|
| `EufyVacuumManager` | `"runtime"` | Main orchestrator |
| `LearningManager` | `"learning"` | Per-job finalization and ETA estimation |
| `BatteryHealthManager` | `"battery"` | Cycle counting and charge rate tracking |
| `ErrorTracker` | `"error_tracker"` | Active-run and last-device error state |
| `AdapterCoordinator` | `"adapter_coordinator"` | Per-entry adapter config registry |
| `MappingTracker` | `"mapping_tracker"` | Position listener; fires `eufy_vacuum_room_completed` off the device's native current-room signal, plus a passive dock-coordinate drift diagnostic log |

### Stateless helper packages

| Package | Role |
|---|---|
| `adapters/` | Adapter config schema, `AdapterCoordinator`, Eufy-specific constants |
| `queue/` | `build_queue_from_managed_rooms`, `build_room_clean_payload` |
| `maps/` | `get_map_bucket`, `ensure_map_bucket`, `get_vacuum_maps_summary`, `rebuild_map_bucket`, `save_map_discovery_snapshot` — pure dict helpers |
| `rooms/` | `room_manager.py` (incl. `build_managed_rooms`), `room_discovery.py`, `reconciliation.py` (name-slug identity reconcile), `source_refresh.py` (service-response room cache), `rooms/utils.py` — stateless |
| `models/` | `TypedDict` definitions (`VacuumRuntimeState`, `LiveRuleState`, etc.) |
| `mapping/` | Image-based room segmentation, custom named layouts, the live map source, `point_in_polygon` zone membership, and the native current-room tracker |
| `learning/` | Job finalization pipeline, history store, ETA estimator; also `external_run.py` — the `ExternalRunManager` subsystem (a stateful bundled subsystem, not stateless; see the subsystem-managers table above) — and `constants.py` (grace-timer constants) |
| `setup/` | Setup workflow, drift detection, protection rules, protected map delete, status response |
| `jobs/job_monitor.py` | Lifecycle state machine (pure function) |
| `timestamp_utils.py` | `parse_timestamp`, `utc_now_iso` |

### Observability — how a run explains itself afterwards

A separate concern from the job pipeline, and the reason the integration can be debugged
from a user's dump rather than from a reproduction. These are what turn "it did something
odd" into evidence.

| Package / file | Role |
|---|---|
| `debug_capture.py` | The silent **flight recorder**. HA's own DEBUG toggle floods the log and is useless in a report; this captures a bounded ring of structured events with no log noise, so a user can hand over what actually happened |
| `decision_log.py` | A machine-readable record at each **decision point** — a run makes dozens of choices and normally records none, so a wrong fallback is invisible after the fact |
| `pose_store.py` | 24-hour rolling chunked JSONL of **where the robot was**. The pose sampler's live buffer is for attribution during a run; this outlives it |
| `receipts/` | Semantic receipts — radio-discipline logging for the stall-capture pilot |
| `counter_segmentation.py` | Brand-agnostic room segmentation from the cumulative `cleaning_time` / `cleaning_area` counters — the fallback for brands with no native per-room signal |
| `job_active_signal.py` | Presence probe + passive observation trace for `binary_sensor.<vac>_cleaning`, which HA 2026.7 stopped creating on some devices (issue #46) |
| `contract_versions.py` | Mechanism-contract versions for mechanism-sensitive reproducers. ⚠ **Currently has zero importers** — either wire it or drop it |

### HA platform modules

`binary_sensor.py`, `button.py`, `number.py`, `sensor/`,
`switch.py`, `select.py` (the debug flight-recorder target — §10) — each owns its
`async_setup_entry` and entity classes. Room entities share the base class in
`room_entities.py`.

> **See also — subsystem deep dives:** [05-core-manager](05-core-manager.md) · [06-job-lifecycle](06-job-lifecycle.md) · [07-queue-engine](07-queue-engine.md) · [08-rooms-system](08-rooms-system.md) · [09-room-rules-system](09-room-rules-system.md) · [10-learning-system](10-learning-system.md) · [11-mapping-system](11-mapping-system.md) · [12-battery-system](12-battery-system.md) · [13-maintenance-manager](13-maintenance-manager.md) · [14-dock-manager](14-dock-manager.md) · [15-setup-system](15-setup-system.md) · [16-profile-manager](16-profile-manager.md) · [17-map-manager](17-map-manager.md) · [18-onboarding-manager](18-onboarding-manager.md) · [frontend/architecture-overview](frontend/architecture-overview.md) · [frontend/theme-system](frontend/theme-system.md) · [23-error-tracker](23-error-tracker.md)

---

## 4. Startup Sequence

`async_setup_entry` in `__init__.py` runs the following in order:

1. **`AdapterCoordinator` construction** — must happen before any adapter
   registration so `get_adapter_config` lookups route through the coordinator,
   not the fallback module-level dict.

2. **`EufyVacuumManager` construction + `async_initialize()`** — the manager's
   `async_shutdown` is registered via `entry.async_on_unload` *immediately
   after construction, before* `async_initialize()` runs (RP-003/INIT-1), so a
   mid-setup failure after this point still tears down (`async_shutdown` is
   idempotent — a never-initialized manager has empty ledgers and cancels
   nothing). `async_initialize()` loads `.storage`, seeds top-level keys, runs
   schema migrations, constructs all subsystem manager objects (themes through
   `external_run` — in construction order: themes, maintenance, dock,
   onboarding, profiles, access_graph, active_job, phase_runner, run_plan,
   room_map, live_room_refresh, map_source, dispatch, external_run),
   initialises callback lists. It then re-arms any `charge_wait` / `wait` dock
   phase whose in-memory poller the restart lost
   (`phase_runner.rearm_dock_phase_if_needed`, called for every `status=='started'`
   active job), and releases orphaned finalize claims / reaps stranded
   phased-job parents left `running` by a crash (see [05 §2](05-core-manager.md)).
   An `async_initialize()` failure raises `ConfigEntryNotReady` (HA retries).

   > **All subsystems are constructed unconditionally here — but only a few are
   > load-bearing to actually fire a room clean.** The architecture is **atom +
   > rings**:
   >
   > - The **atom** — `adapters` + `dispatch` + `rooms` + the spine (`hass`,
   >   `storage`, `data`) + `active_job` — is what fires a clean. It is
   >   structurally unchanged since the integration's origin as a ~118-line HA
   >   script: assemble rooms, gate, `room_clean`, reset. The wire send is still
   >   one `hass.services.async_call`.
   > - Everything else is a **ring**, added for *fit* rather than for the call.
   >   `themes`, `maintenance`, `dock`, `room_map`, `map_source` and
   >   `live_room_refresh` are never touched on the room-clean path at all.
   > - A ring should attach through an **absence-tolerant seam** — `learning` is
   >   the model to copy, guarded `if learning is None: …` at every reach-in, so
   >   the core tolerates its *nonexistence* rather than merely its stubbing. The
   >   test that property has to pass is stated in
   >   [design/core-minimality](design/core-minimality.md): a manager with
   >   `access_graph`, `profiles`, `onboarding`, `learning`, `maps` and
   >   `maintenance` **absent** still fires one `room_clean`.
   >
   > Three rings do **not** yet meet that bar: `access_graph` and `profiles` hold
   > room-definition primitives the core reaches in for, and `onboarding` gates the
   > start on VA-owned state. Those are mis-homed mechanism, not features the core
   > depends on — the measured map, the reach-in counts, and the refactor that would
   > close them are in
   > [design/core-minimality](design/core-minimality.md).

3. **Orphaned entity cleanup** — removes legacy `eufy_vacuum_icon_*` entities
   from the entity registry if found (silent no-op on clean installs).

4. **Adapter registration** — `load_stored_adapter_configs` reads
   `data["adapters"]` (user-built stored configs); then `register_brand_adapter`
   (the ordered `BRAND_REGISTRARS` table in `adapters/brands.py`) registers the
   matching brand's code adapter for each known vacuum — resolution order:
   **platform match** (the vacuum's entity-registry `platform` against each
   adapter's declared `UPSTREAM_PLATFORMS`) → **unsupported** (no adapter, and a
   warning naming the providing integration). Code adapters always win over
   stored.

   > **From immediately before this step onward** (the ledger is created just
   > before it, in `__init__.async_setup_entry`), every resource this and the
   > following steps register is pushed onto a local mid-setup unwind ledger
   > (`_unwind_stack`, RP-039/RF-16), walked in reverse (LIFO) if a later step
   > raises. Adapter registration itself pushes nothing to the ledger (a failed
   > attempt's `AdapterCoordinator` is simply replaced by a fresh one on the
   > next attempt) — the first entries appear once the manager is stored at
   > `DATA_RUNTIME`, at the start of the next step. See
   > [02-ha-integration §1](02-ha-integration.md#1-integration-entry-points).

5. **Singletons construction** — `LearningManager` constructed, then the
   learning read-caches (`room_stats.json` / `accuracy_stats.json` /
   `job_stats.json`) are warmed off-loop per vacuum
   (`LearningHistoryStore.warm_estimate_caches` via executor) so the
   loop-bound dashboard-snapshot estimate never blocks on disk — not even on
   the first snapshot after a restart. Then `BatteryHealthManager`,
   `ErrorTracker` constructed and started. `BatteryHealthManager` is built in
   `__init__.py` and stored at `hass.data[DOMAIN][DATA_BATTERY]`
   (`DATA_BATTERY = "battery"`, `const.py`); it is torn down on unload.
   `MappingTracker` constructed; position listeners
   registered for known vacuums.

6. **Service registration** — four service groups registered:
   `async_register_services`, `async_register_learning_services`,
   `async_register_theme_services`, `async_register_mapping_services`. One
   service — `battery_rebaseline` — is registered inline in `__init__.py`
   rather than through a group function (it drives `BatteryHealthManager`).

7. **Listener registration** — nine listener modules registered:
   `lifecycle`, `job_metrics`, `dock_events`, `path_blockers`,
   `pause_timeout`, `stall_capture`, `job_progress`, `pose_sampler`,
   `discovery`.

8. **Platform forward** — `async_forward_entry_setups` triggers
   `async_setup_entry` in all **six** platform modules (`binary_sensor`, `button`,
   `switch`, `select`, `number`, `sensor`), creating and registering all HA entities.

9. **Panel registration** — one sidebar panel registered per managed vacuum
   (`eufy-vacuum-{object_id}`), serving the compiled card JS.

On unload, platforms unload first (everything else runs only if that
succeeds), then panels are removed, listeners removed, services unregistered,
singletons shut down, coordinator torn down — and, separately, HA runs the
`entry.async_on_unload` callbacks registered in step 2, including
`manager.async_shutdown()`, which flushes any pending debounced save and
cancels the manager's background tasks/timers. See
[02-ha-integration](02-ha-integration.md) for the exact order.

> **See also:** [02-ha-integration](02-ha-integration.md) for the full config-entry lifecycle, platform setup, and entity registration detail; [04-listeners](04-listeners.md) for the listener registration and unsubscription pattern.

---

## 5. Data Flow — Job Start to Finish

This traces the complete path of a card-initiated "Start Selected Rooms" action:

```
Card → eufy_vacuum.start_selected_rooms service call
  │
  ▼
services/job_control.py
  Validates vacuum_entity_id, map_id, room_ids
  Calls manager.start_selected_rooms(...)
  │
  ▼
core/manager.py — start_selected_rooms()
  1. Builds managed_rooms from data["maps"]
  2. Delegates to run_plan._build_effective_start_plan()
     ├── Runs preflight rule evaluation (per-room blockers/modifiers)
     ├── Calls manager._update_room_rule_status_snapshot() → data["room_rule_status"]
     └── Returns queue, payload, preflight summary
  3. Dispatches via the DispatchManager delegators, in order:
     ├── _resolve_live_dispatch_payload (slug → live segment id, wire-only)
     ├── _run_global_pre_calls (device-global settings; runs AFTER resolution
     │    — DQ-ACT-6: resolution can raise on a re-segmented map, and firing
     │    the pre-calls first left a failed start with the device's global
     │    setting already rewritten)
     └── _dispatch_clean_payload → hass.services.async_call(domain, service, data)
         (dispatch/manager.py — the adapter's wire envelope, command default "room_clean")
  4. Builds the active-job record (build_active_job_state + job_metadata/job_id)
     └── Writes data["active_jobs"][vacuum][map_id]
  5. Returns start summary to service caller → card displays result
     (the calling service handler saves; start_selected_rooms itself never
     calls async_save)
  │
  ▼  (vacuum hardware begins cleaning)
  │
  ▼
listeners/lifecycle.py  (state-change listener on vacuum entity)
  Inlines state handling (no single entry-point method); on completion
  calls manager.finalize_learning_for_active_job(...) then
  manager.mark_active_job_finalized(...)
  → Updates data["active_jobs"] lifecycle fields
  │
  ▼
listeners/job_progress.py  (5s time-interval ticker)
  Calls manager.get_job_progress_snapshot()
  → Fires EVENT_JOB_PROGRESS_TICK (every 5s while running)
  → Card receives tick, re-fetches snapshot, updates progress display
  │
  ▼  (vacuum returns to dock)
  │
  ▼
listeners/dock_events.py  (state-change listener on dock sensors)
  Calls manager.record_dock_event(...)
  → Records dock event in data["dock_events"]
  → Triggers finalization
  │
  ▼
listeners/lifecycle.py  (charging state detected)
  Calls manager.async_finalize_completed_job(...)
  │
  ▼
learning/manager.py — LearningManager.async_finalize_completed_job()
  (drives the LearningJobFinalizer in learning/job_finalizer.py)
  1. Reads active job, calculates duration
  2. Writes completed_job record to disk (per-job JSON)
  3. Updates learning stats
  4. Returns completed_job dict
  │
  ▼
core/manager.py — _ingest_completed_job_into_room_history()
  Updates data["room_history"][vacuum][map_id][room_id]
  Fires _notify_room_history_updated()
  → Room history sensors refresh
  │
  ▼
listeners/lifecycle.py — fires EVENT_JOB_FINISHED on HA event bus
  → Card receives event, refreshes dashboard
```

> **See also:** [06-job-lifecycle](06-job-lifecycle.md) for the complete per-step breakdown of this flow including all paths to job end; [07-queue-engine](07-queue-engine.md) for the payload construction at step 2; [09-room-rules-system](09-room-rules-system.md) §5 for `_build_effective_start_plan` at step 2; [10-learning-system](10-learning-system.md) and [12-battery-system](12-battery-system.md) for the two finalization hooks in the last step.

---

## 6. State Persistence

### `.storage/eufy_vacuum`

The single source of truth for all persistent integration state. Managed by
`core/storage.py` using HA's `Store` helper (atomic JSON writes, automatic
backup). Loaded into `manager.data` on startup; all writes go through
`manager.async_save()`.

Top-level keys in `manager.data`:

| Key | Content |
|---|---|
| `"vacuums"` | Per-vacuum record — `vacuum_entity_id`, `detected_model`, `is_managed` (set by `ensure_vacuum_record`); `pause_timeout_minutes_default` (get/set_pause_timeout_settings — **absent until set**, the getter computes 15 without writing); `stall_capture_enabled` (set_stall_capture — absent means off); optional `panel_title` / `live_map_image_entity` when the user has overridden them via the setup services |
| `"capabilities"` | Discovered entity IDs and feature flags per vacuum |
| `"maps"` | Per-vacuum, per-map bucket: rooms, summary, metadata, segment links |
| `"queue"` / `"payloads"` | Per-vacuum, per-map derived queue / payload snapshots |
| `"active_jobs"` | Per-vacuum, per-map active job state (status, queue, progress) |
| `"room_history"` | Per-vacuum, per-map, per-room last clean timestamps |
| `"room_rule_status"` | Per-vacuum, per-map, per-room last rule evaluation result |
| `"profiles"` | Room profiles library (`profiles.room_profiles`) |
| `"run_profiles"` | Saved run profiles, per vacuum per map |
| `"theme"` | Theme library (built-in + user), active theme ID, working draft |
| `"maintenance"` | Per-vacuum, per-component reset snapshots and intervals |
| `"onboarding"` | Per-vacuum, per-map onboarding flags (`rooms_discovered`, floor-type confirmations) |
| `"discovery"` | Raw discovery cache per vacuum per map |
| `"setup_progress"` | Per-vacuum setup state machine (completed steps, rejections, drift history) |
| `"adapters"` | User-built adapter overrides (stored adapter configs) |
| `"battery"` | Battery-health records, nested one level down per vacuum under `battery.vacuums` (written by `battery/manager.py`) |
| `"dock_events"` | Recent dock event log per vacuum |
| `"error_tracker"` | Per-vacuum error state (`active_run_error`, `last_device_error`, `recent_errors`); in the storage default, backfilled unconditionally on load (`core/storage.py`) |
| `"learning_processing_enabled"` / `"learning_pending_runs"` | Box-level learning toggle + per-vacuum pending-run counters |
| `"migrations"` | One-shot store-repair latches (`{key: True}`) — `room_vocabulary_v1`, `pause_timeout_default_v1`, `orphaned_vacuum_keys_v1`. See [03 §1](03-data-model.md) |

(This is the working inventory; [03-data-model](03-data-model.md) is the
authoritative schema for whatever it documents, but as of this audit that doc
covers only a subset of the keys above.)

### Learning history files

Completed job records and derived stats live in
`<config>/eufy_vacuum/<vacuum_key>/` as individual JSON files. Not part of
`.storage` — written and read by `learning/history_store.py` via
`async_add_executor_job`. This keeps large per-job payloads off the storage
file while the `.storage` file stays fast to load.

### Runtime state

`manager.runtime` holds `VacuumRuntimeState` dicts keyed by `vacuum_entity_id`.
Runtime state is never persisted; it is reconstructed from upstream entity states
on each HA start. It includes: raw HA state string, battery level, charging
flag, dock sensor values.

> **See also:** [03-data-model](03-data-model.md) for the complete schema of every key in `manager.data` including per-key ownership and storage path references.

---

## 7. The Adapter Pattern

The adapter pattern is the key seam that makes `eufy_vacuum` portable across
vacuum brands. Every brand-specific piece of knowledge is encapsulated in an
adapter config dict rather than hard-coded.

### What an adapter config contains

```python
{
    "entities": {
        "vacuum": "vacuum.alfred",
        "task_status": "sensor.alfred_status",
        "cleaning_area": "sensor.alfred_cleaning_area",
        "battery_level": "sensor.alfred_battery",
        "error_message": "sensor.alfred_error_message",
        # ... all upstream entity IDs
    },
    "maintenance_components": {
        "brush": {"label": "Main Brush", "icon": "mdi:...", "default_interval_hours": 300},
        # ...
    },
    "vocabulary": {
        "clean_mode_options": [{"value": "vacuum", "label": "Vacuum"}, ...],
        "fan_speed_options": [...],
        "water_level_options": [...],
        "clean_intensity_options": [...],
    },
    "charging_states": ["docked", "charging"],
    "active_states": ["cleaning", "returning"],
    # ...
}
```

### How adapters are resolved

`adapters/registry.py` exposes `get_adapter_config(vacuum_entity_id)`. The
lookup chain is:

1. `AdapterCoordinator` (per-config-entry; constructed in `async_setup_entry`)
2. Module-level `_REGISTRY` fallback (legacy shim; stays empty in normal operation)

The coordinator's registry is populated in two ways:
- **Code adapters** — `register_brand_adapter` (`adapters/brands.py`) resolves
  and runs one brand's registrar for each known vacuum, per the ordered
  `BRAND_REGISTRARS` table: the first registrar whose declared `platforms`
  contains the vacuum's entity-registry `platform` → otherwise **unsupported**,
  meaning no adapter and a warning naming the providing integration.
  `resolve_brand` reports which route was taken. Identity is DATA: each brand
  names the integration that provides it in its own `const.py`, and there is no
  `detect` callable and no per-user brand override — core compares, and never
  asks a brand to judge itself. See
  [21-adapter-system §6.1](21-adapter-system.md).
- **Stored adapters** — `adapters/config_loader.py` reads `data["adapters"]`
  and registers user-built configs. Code adapters always win if both exist for
  the same vacuum.

### Adding a new brand

Roborock is already shipped as a worked second-brand adapter
(`adapters/roborock/`, a `BrandRegistrar` row pairing
`register_roborock_adapter_for_vacuum` with the `UPSTREAM_PLATFORMS` it declares
in `const.py`) — see
[29-roborock-adapter](29-roborock-adapter.md) for that walkthrough.

To add a *third* brand (e.g. Dreame), you would:

1. Create `adapters/dreame/` with `adapter.py`, `const.py`, and vocabulary
   files mirroring the Eufy / Roborock structure.
2. Declare `UPSTREAM_PLATFORMS` in `adapters/dreame/const.py` — the HA
   integration domain that provides that brand's vacuum entity (for Dreame,
   `dreame_vacuum`). This is the adapter's identity claim about itself.
3. Add one `BrandRegistrar` row to `BRAND_REGISTRARS` in `adapters/brands.py`
   (`register_dreame_adapter_for_vacuum` + that tuple). Integration core
   (`__init__.py`) is untouched — this is the whole point of the registrar
   table, and why identity is data rather than a per-brand callable.
4. The rest of the codebase calls `get_adapter_config(vacuum_entity_id)` — no
   other files change.

See the [porting guide](../contributing/porting-guide.md) for the complete porting checklist.

> **See also:** [21-adapter-system](21-adapter-system.md) for the registry, validation, and startup registration order; [22-adapter-config-reference](22-adapter-config-reference.md) for the complete field-by-field schema of every block in the adapter config dict.

---

## 8. Listener Architecture

All upstream HA state changes are handled by the nine listener modules in
`listeners/`. Each module owns its listener registration, unsubscription, and
any private constants. None of them hold persistent state — they read from
`manager.data` and call manager methods to mutate it.

| Module | Listens to | Purpose |
|---|---|---|
| `lifecycle.py` | Vacuum entity state | Job start/stop/cancel detection, finalization trigger |
| `job_metrics.py` | Battery + vacuum state | Battery readings during jobs |
| `dock_events.py` | Dock sensor entities | Dock event recording (empty, wash, etc.) |
| `path_blockers.py` | Rule trigger entities | Mid-job blocker rule evaluation |
| `pause_timeout.py` | HA time + vacuum state | **Two reaps** on one 1-minute tick: auto-cancel on overlong pause, and finalize a stranded `started` run (including a robot trapped in `error`) |
| `stall_capture.py` | `EVENT_STALL_DETECTED` | Opt-in per vacuum: render the stalled room to disk, notify, fire `eufy_vacuum_stall_captured` |
| `job_progress.py` | HA time (5 s) | Takes a progress snapshot, then **fires** `EVENT_JOB_PROGRESS_TICK` for the card. It produces that event; it does not subscribe to one |
| `pose_sampler.py` | HA time + vacuum state | Buffers the per-tick pose time-series (`pose_samples`) during an external (app-started) or dispatched run for room auto-attribution, via the adapter-declared `room_attribution.source`; attribution-capable vacuums only |
| `discovery.py` | Vacuum entity state | Auto-discovery once **docked** (map-safe: run over, pose settled) + map-change/reload/6h timer — see [04 §discovery](04-listeners.md) |

Registration pattern (all nine are identical):

```python
# In __init__.py
lifecycle.register(hass)  # subscribes, stores unsub callable in hass.data
# ...
# On unload:
lifecycle.remove(hass)    # calls unsub and cleans up
```

> **See also:** [04-listeners](04-listeners.md) for the complete listener module breakdown — what each module subscribes to, what it calls, and how the unsubscription chain is managed.

---

## 9. Service Layer

Services are the card's primary API surface. `const.py` defines 100+ `SERVICE_*`
constants, plus the inline `battery_rebaseline` service registered directly in
`__init__.py` — roughly 100+ services in total. They are registered in four
groups (the inline `battery_rebaseline` registration is the one exception to the
group pattern):

| Registration function | Module(s) | Domain |
|---|---|---|
| `async_register_services` | `services/*.py` | All core room/job/queue/setup services |
| `async_register_learning_services` | `learning/services.py` | Finalization, stats, estimates |
| `async_register_theme_services` | `themes/services.py` | Theme library CRUD |
| `async_register_mapping_services` | `mapping/mapping_services.py` | Map image / segment services |

Service modules in `services/` are split by domain:

| File | Services |
|---|---|
| `job_control.py` | start, pause, resume, cancel, get lifecycle state |
| `queue.py` | build queue, get queue/payload/active-job state |
| `rooms.py` | discover, save, update room fields |
| `room_profiles.py` | room profile CRUD + apply |
| `run_profiles.py` | run profile CRUD + start + `set_run_profile_steps` (ordered room-group / charge-wait / wait steps) |
| `setup.py` | setup workflow (add vacuum, import map, save rooms, drift) |
| `maintenance.py` | reset, set interval, get upkeep snapshot |
| `dock.py` | wash mop, dry mop, empty dust, dock action status |
| `access_graph.py` | room access graph editor |
| `adapter_config.py` | save/delete/get adapter config, entity discovery |
| `errors.py` | acknowledge error, get recent errors |
| `snapshots.py` | dashboard snapshot, progress snapshot, job control state |
| `debug.py` | debug flight-recorder capture (start/stop/status) — backs the `select.py` capture target (§10) |
| `stall_capture.py` | `set_stall_capture` — the rooms-card switch; the consumer treats absent as off, so without this the feature is correct and unreachable. Plus `dev_inject_stall`, the one maintainer-only service: it fires the canonical `EVENT_STALL_DETECTED` from the vacuum's real state so every downstream consumer runs for real |

All service handlers follow a three-step pattern:
1. Extract and validate `call.data` fields
2. Call one or more `manager.*` methods
3. Fire `call.async_set_result(payload)` with a structured response dict

> **See also:** [advanced/03-services.md](../advanced/03-services.md) for the user-facing service reference (call shapes, parameters, and return payloads).

---

## 10. Entity Layer

**Six** HA platforms create entities:

| Platform | Entity classes |
|---|---|
| `sensor/` | ActiveJob, Profile, MaintenanceRemaining, DockEvent, ThemeState, Onboarding, RoomCleaningHistory, RoomRuleStatus, BatteryHealth (×12), ActiveRunError, LastDeviceError, MapOverlays |
| `switch.py` | RoomEnabledSwitch (one per configured room) |
| `select.py` | DebugTargetSelect (a single integration-level debug flight-recorder capture target) |
| `number.py` | RoomOrderNumber (one per room), MaintenanceIntervalNumber (one per component) |
| `button.py` | MaintenanceResetButton (one per component), SavedRunProfileButton (one per exposed profile) |
| `binary_sensor.py` | ActiveRunHasErrorBinarySensor |

All entity classes set `_attr_has_entity_name = True` and use
`build_vacuum_device_info(vacuum_entity_id)` from `entity_helpers.py`. This
groups all entities under a single HA device per vacuum ("Alfred" not "Alfred
Rooms").

`EufyVacuumActiveJobSensor` (one per vacuum/map) is defined in
`sensor/lifecycle.py` and instantiated in `sensor/__init__.py`. The 12
`BatteryHealth` sensors are the exception to the "one class per file under
`sensor/`" rule: they are defined in `battery/sensors.py` and injected into the
sensor platform via `build_battery_sensors`, not as classes under `sensor/`.

`DebugTargetSelect` is the same arrangement one platform over — defined in
`debug_capture.py` and built by `build_debug_target_select`, so `select.py`
declares no entity class at all. The rule both follow: **an entity whose state
belongs to a subsystem is defined with that subsystem**, and the platform module
only publishes it. Reading `select.py` or `sensor/` alone will not find them.

Room entities inherit from `EufyVacuumRoomEntity` (`room_entities.py`), which
provides `_get_room_data()`, `_async_update_room()`, `available`, and
`extra_state_attributes`.

Dynamic entities (room-based sensors/switches/numbers) are added and removed at
runtime via `register_room_update_callback`. When `_notify_rooms_updated` fires,
each platform's callback adds new entities and removes stale ones.

> **See also:** [02-ha-integration](02-ha-integration.md) for entity registration detail and the platform `async_setup_entry` pattern; [frontend/architecture-overview](frontend/architecture-overview.md) for how the panel card reads entity state.

---

## 11. Concurrency & Thread Safety

HA's event loop is single-threaded. All manager methods run on the event loop
and do not need locking.

Blocking I/O is pushed to executor threads via `async_add_executor_job`, and
that is **not rare** — learning history and stats, map rendering and the
map-source coordinator, debug capture, stall capture, battery, diagnostics and
pose sampling all use it. Safety therefore cannot rest on it being exceptional.
It rests on a rule:

> **The function that runs off-loop takes its inputs as arguments, returns a
> value, and mutates nothing shared. The caller writes the result into
> `self.data` back on the event loop.**

`_load_room_history_cache_sync` (`core/manager.py`) is the shape to copy: it
builds a local dict and hands it back. An executor function that read or wrote
`self.data` directly would be a genuine data race — and one that almost never
reproduces under test, because the loop is usually idle while it runs.

Callback lists (`_room_update_callbacks`, etc.) are mutated only from the event
loop. Manager methods called from `hass.loop.call_soon_threadsafe` (the
`_request_entity_state_write` pattern in sensor setup) are safe because
`async_write_ha_state` is event-loop-safe.

> **See also:** [12-battery-system](12-battery-system.md) §14.3 for the primary real-world example of the `call_soon_threadsafe` pattern — the battery hook fires from the learning finalizer's executor thread.

---

## 12. Extension Points

### Adding a room entity type

1. Create a class in `sensor/` (or another platform) inheriting from
   `EufyVacuumRoomEntity`.
2. Add it to the platform's `async_setup_entry` loop.
3. Add a stale/new sync callback in the platform's `_on_rooms_updated` handler.

### Adding a service

1. Add a constant to `const.py`.
2. Add a handler to the appropriate `services/*.py` file.
3. Register it in `async_register_services` (or the relevant group function).
4. Declare it in `services.yaml` — or add it to the documented exception list in
   `tests/unit/test_service_declaration_parity.py`. That gate asserts both
   directions (every registered service is declared; every declared field exists
   in the schema with a matching type), so skipping this step fails the suite
   rather than shipping an undeclared service. An inline schema built by hand
   rather than through the group pattern is how one service escaped the gate for
   twelve days — see the note above `_BATTERY_REBASELINE_SCHEMA` in `__init__.py`.

### Adding a subsystem manager

1. Create a new package under `custom_components/eufy_vacuum/`.
2. Expose a manager class with `__init__(self, manager)`.
3. Instantiate it in `EufyVacuumManager.async_initialize()` and assign to
   `self.<name>`.
4. Add shim methods in `core/manager.py` that delegate to the subsystem.

### Porting to a new brand

The adapter pattern means the only brand-specific files are:
- `adapters/<brand>/` — entity IDs, vocabulary, maintenance components, and the
  `UPSTREAM_PLATFORMS` identity claim in its own `const.py`
- `adapters/brands.py` — one `BrandRegistrar` row in `BRAND_REGISTRARS`

**Integration core (`__init__.py`) is not touched.** It used to hold a
`register_<brand>_adapter_for_vacuum` call per brand; moving that into the
registrar table is exactly what turned adding a brand from an edit to core into
an addition beside it (§7). If a port makes you reach for `__init__.py`, the
thing you are adding is not brand knowledge.

See the [porting guide](../contributing/porting-guide.md) for the detailed walkthrough.
