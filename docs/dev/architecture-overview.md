# Architecture Overview

This document describes the full system architecture of `eufy_vacuum` (the Home Assistant
custom integration) and `eufy-vacuum-command-center` (the companion Lovelace card).
It is written for developers who want to extend, contribute to, or port the system to a
different vacuum ecosystem.

---

## Table of Contents

1. [System Boundaries](#1-system-boundaries)
2. [Full Stack Layer Diagram](#2-full-stack-layer-diagram)
3. [Integration Internal Layers](#3-integration-internal-layers)
4. [Data Flows](#4-data-flows)
5. [State Persistence](#5-state-persistence)
6. [Key Design Decisions](#6-key-design-decisions)
7. [Concurrency & Thread Safety](#7-concurrency--thread-safety)
8. [Extension Points](#8-extension-points)

---

## 1. System Boundaries

### What the integration is

`eufy_vacuum` is a Home Assistant custom integration that sits **on top of** the
`robovac_mqtt` layer. Its purpose is to add a complete job-management, learning,
and configuration layer that the bare `robovac_mqtt` entities do not provide.

It owns:

- Managed room configuration (order, per-room clean settings, profiles, rules)
- A queue engine that assembles multi-room job payloads
- Active job lifecycle tracking (start → monitor → auto-finalize)
- A learning / ETA estimation system backed by per-job JSON files on disk
- A theme system for the companion card
- A mapping subsystem that tracks robot position during runs and learns room bounds
- All the HA entities (sensors, buttons, selects, switches, numbers) that surface
  integration state into the HA entity registry
- HA service endpoints consumed by the Lovelace card

### What the integration is not

`eufy_vacuum` does **not**:

- Communicate directly with the Eufy cloud or the vacuum hardware. All hardware
  interaction goes through the underlying `robovac_mqtt` vacuum entity and its
  companion sensor entities.
- Replace `robovac_mqtt`. It subscribes to state changes on entities that
  `robovac_mqtt` creates; it does not re-implement cloud or MQTT communication.
- Bundle the Lovelace card. The card is a separate JavaScript project
  (`eufy-vacuum-command-center`). The integration serves the compiled card JS
  as a static file at `/eufy_vacuum/frontend/`, but the two projects are
  independently versioned.

### External dependencies

| Dependency | Role |
|---|---|
| Home Assistant core | Config entry lifecycle, entity registry, service bus, storage helpers, static path serving |
| `robovac_mqtt` (or compatible) | Provides `vacuum.*` entity + companion sensor entities (task_status, dock_status, active_cleaning_target, active_map, robot_position_x/y, water_level, etc.) |
| Eufy cloud / robot hardware | Upstream of `robovac_mqtt`; invisible to this integration |
| `eufy-vacuum-command-center` | Frontend that calls integration services; served from the integration's static path |

---

## 2. Full Stack Layer Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HARDWARE                                                               │
│  Eufy vacuum robot (X10 Pro Omni or compatible)                         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ Wi-Fi / proprietary Eufy cloud protocol
┌───────────────────────────────▼─────────────────────────────────────────┐
│  EUFY CLOUD                                                             │
│  Eufy mobile app backend; relays commands and telemetry                 │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ MQTT / cloud API
┌───────────────────────────────▼─────────────────────────────────────────┐
│  robovac_mqtt  (third-party HA integration)                             │
│  Owns: vacuum.* entity, sensor.*_task_status, sensor.*_dock_status,     │
│        sensor.*_active_cleaning_target, sensor.*_active_map,            │
│        sensor.*_robot_position_x/y, sensor.*_water_level, ...          │
│  Exposes vacuum.send_command() for issuing clean payloads               │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HA entity state changes + service calls
┌───────────────────────────────▼─────────────────────────────────────────┐
│  eufy_vacuum  (this integration)                                        │
│  Owns: room config, queue, job lifecycle, learning, mapping, themes,    │
│        all eufy_vacuum.* HA services                                    │
│  Internal layers detailed in §3                                         │
└────────────┬────────────────────────────────────────┬────────────────────┘
             │ HA entity state                        │ HA service responses
             │ sensor.*_theme_state, etc.             │ (return payloads via
             │                                        │  hass.services.call)
┌────────────▼────────────────────────────────────────▼────────────────────┐
│  eufy-vacuum-command-center  (Lovelace card)                            │
│  Owns: all UI, view routing, theme rendering, user interactions          │
│  Communicates exclusively through the HA service bus (no direct Python  │
│  calls; no WebSocket subscriptions beyond standard hass object)         │
└─────────────────────────────────────────────────────────────────────────┘
```

### What each layer owns

**robovac_mqtt** owns the live vacuum state. It is the only layer that talks to the
hardware. `eufy_vacuum` never directly issues MQTT or cloud calls; it issues
`vacuum.send_command` service calls that `robovac_mqtt` translates.

**eufy_vacuum** owns all higher-level logic: it decides *what* to clean, *when* to
finalize, *how* to record history, and *how* to present configuration. It also serves
the card's compiled JS bundle as a static HTTP path.

**eufy-vacuum-command-center** owns all user-facing presentation. It is a completely
passive consumer: it reads HA entity states (via the standard `hass` object passed to
every Lovelace card) and calls `eufy_vacuum.*` services for everything else. This means
the card has no privileged channel into the integration — everything the card can do, an
automation script could also do using the same service calls.

---

## 3. Integration Internal Layers

Each layer has its own deep-dive doc; this section is the map. Detailed
references:

- [core-manager.md](core-manager.md) — `EufyVacuumManager` orchestrator
- [queue-engine.md](queue-engine.md) — queue / payload / snapshot builders
- [job-lifecycle.md](job-lifecycle.md) — lifecycle evaluation, finalization
- [learning-system.md](learning-system.md) — ETA math, file-backed job store
- [mapping-system.md](mapping-system.md) — calibration, boundaries, transforms
- [room-rules-system.md](room-rules-system.md) — blocker/modifier rule evaluation
- [battery-system.md](battery-system.md) — battery health subsystem
- [theme-system.md](theme-system.md) — token-based theme engine
- [ha-integration.md](ha-integration.md) — HA platforms, services, events
- [adapter-config-reference.md](adapter-config-reference.md) — per-vacuum brand schema
- [porting-guide.md](porting-guide.md) — workflow for non-Eufy brands
- [card-architecture.md](card-architecture.md) — frontend / Lovelace integration (incl. mobile shell, §7)
- [data-model.md](data-model.md) — canonical stored-data shapes

```
eufy_vacuum/
├── __init__.py             ← domain setup, config entry lifecycle,
│                             all runtime event listeners (lifecycle,
│                             dock events, path blockers, pause timeouts)
│
├── core/
│   ├── manager.py          ← EufyVacuumManager — central orchestrator
│   ├── storage.py          ← EufyVacuumStorage — HA Store wrapper
│   ├── water_amendment.py  ← generic post-job mop-wash water amendment watcher
│   ├── error_tracker.py    ← active-run error latching, falling-edge detection
│   └── capabilities.py     ← entity-presence-based capability detection
│
├── adapters/               ← brand-config layer (data-driven, no logic)
│   ├── registry.py         ← per-vacuum adapter config registry
│   ├── config_schema.py    ← canonical ADAPTER_CONFIG_SCHEMA (source of truth)
│   ├── config_loader.py    ← loads stored adapter configs at integration setup
│   └── eufy/               ← reference adapter (entity patterns, vocabulary,
│       ├── adapter.py          maintenance components, upkeep guides, water
│       ├── vocabulary.py       configs, model catalog). A port to a different
│       ├── entities.py         brand creates a parallel sub-folder; framework
│       ├── constants.py        code never imports from here. See
│       ├── model_catalog.py    docs/dev/adapter-config-reference.md and
│       ├── maintenance_components.py   docs/dev/porting-guide.md.
│       ├── upkeep_catalog.py
│       ├── upkeep_guides.py
│       └── water_config.py
│
├── queue/
│   └── queue_engine.py     ← pure queue/payload/snapshot builders (no IO);
│                             payload shape is adapter-driven via dispatch
│
├── jobs/
│   └── job_monitor.py      ← lifecycle evaluation, start-blocker logic
│
├── setup/                  ← onboarding, drift detection, lifecycle services
│   ├── workflow.py         ← initial discovery + room onboarding flow
│   ├── status.py           ← data-driven setup state machine (steps + drift)
│   ├── drift.py            ← per-room missing-pass history + run_discovery_pass
│   │                          + reject_rooms + force_remove_room helpers
│   ├── protection.py       ← guards against partial / mid-setup operations
│   └── delete.py           ← vacuum / map deletion services
│
├── learning/
│   ├── manager.py          ← LearningManager — orchestrates learning subsystem
│   ├── estimator.py        ← ETA math, confidence scoring
│   ├── history_store.py    ← file-backed job JSON store
│   ├── job_finalizer.py    ← per-job finalization, writes completed JSON
│   └── stats_rebuilder.py  ← rebuilds aggregate stats from job files
│
├── battery/
│   ├── manager.py          ← BatteryHealthManager — sampling, drain/charge zones, baseline
│   ├── job_metrics.py      ← per-job drain ingestion + per-mode aggregates
│   ├── sensors.py          ← battery health HA sensor entities
│   └── store.py            ← JSON-on-disk persistence (separate from HA Store)
│
├── mapping/
│   ├── manager.py          ← MappingManager — calibration, boundary, transform
│   ├── tracker.py          ← MappingTracker — live position tracking
│   ├── transform.py        ← affine transform (vacuum coords → pixel coords)
│   └── boundary.py         ← room boundary processing
│
├── rooms/
│   ├── room_manager.py     ← managed-room build / selection summary
│   └── room_discovery.py   ← discovers rooms from vacuum entity attributes
│
├── profiles/
│   └── room_profiles.py    ← built-in and user room profiles, capability gating
│
├── models/
│   └── models.py           ← VacuumRuntimeState dataclass
│
├── maps/
│   └── map_manager.py      ← per-map "bucket" management (maps stored in storage)
│
├── sensor.py               ← HA sensor entities (theme_state, etc.)
├── button.py               ← HA button entities
├── select.py               ← HA select entities
├── switch.py               ← HA switch entities
├── number.py               ← HA number entities
├── services.py             ← registers all core eufy_vacuum.* services
├── learning/services.py    ← registers learning-specific services
├── theme_services.py       ← registers theme-specific services
└── mapping/mapping_services.py ← registers mapping-specific services
```

### How the layers relate

```
                    ┌─────────────────────────┐
                    │   __init__.py            │
                    │  (entry point, listeners)│
                    └──────────┬──────────────┘
                               │ owns / coordinates
                    ┌──────────▼──────────────┐
                    │   EufyVacuumManager      │  ← single instance per entry
                    │   (core/manager.py)      │
                    └──┬──────┬──────┬─────┬──┘
                       │      │      │     │
              ┌────────▼─┐ ┌──▼───┐ ┌▼──┐ ┌▼──────────────┐
              │ Storage  │ │Queue │ │Job│ │ Learning       │
              │ (HA Store│ │Engine│ │Mon│ │ Manager        │
              │  wrapper)│ │(pure)│ │itor│ │(+ history,     │
              └──────────┘ └──────┘ └───┘ │  estimator,    │
                                          │  finalizer)    │
                                          └────────────────┘
                    ┌──────────────────────────┐
                    │  MappingManager          │
                    │  MappingTracker          │
                    └──────────────────────────┘
                    ┌──────────────────────────┐
                    │  HA Entity Layer         │
                    │  sensor / button /       │
                    │  select / switch /number │
                    └──────────────────────────┘
```

**EufyVacuumManager** is the single authoritative runtime object. It holds all
in-memory integration state (rooms, queues, active jobs, maps, themes, capabilities)
and exposes methods that every other subsystem calls. Services registered in
`services.py`, `theme_services.py`, etc. resolve the manager from
`hass.data[DOMAIN][DATA_RUNTIME]` and delegate to it.

**EufyVacuumStorage** (`core/storage.py`) is a thin wrapper around HA's built-in
`Store` helper. It serialises to `.storage/eufy_vacuum.storage` and owns the
top-level schema shape (see §5). The manager calls it on every mutation.

**Queue engine** (`queue/queue_engine.py`) is intentionally pure (no IO, no HA
imports). It takes managed-room dicts as input and returns `QueueEntry`,
`PayloadItem`, and `ActiveJobSnapshot` TypedDicts. Being pure makes it trivial to
unit-test and reason about independently.

**Job monitor** (`jobs/job_monitor.py`) evaluates the lifecycle state of an active
job from a snapshot of entity states. It does not subscribe to state changes itself —
`__init__.py` does the subscribing and calls `evaluate_job_lifecycle()` when relevant
entities change.

**LearningManager** orchestrates the optional learning system. It pulls payload state
from the core manager, delegates estimation to `LearningEstimator`, and delegates
persistence to `LearningHistoryStore` and `LearningJobFinalizer`. It never performs
ETA math itself; that is isolated in `estimator.py`.

**MappingManager** handles the transform pipeline for overlaying the robot's coordinate
space onto a map image: calibration corner collection, affine transform computation,
and room boundary learning from traced runs. **MappingTracker** holds the live
in-memory position trace during an active job and feeds it to the manager on
finalization.

**HA Entity Layer** (`sensor.py`, `button.py`, etc.) creates standard HA entities that
expose integration state. The `sensor.*_theme_state` entity is particularly important:
the card reads it on every `hass` update to stay in sync with backend theme state
without needing a separate service call.

---

## 4. Data Flows

### 4.1 Cleaning Job Flow

From the moment a user presses "Start" in the card to the moment learning data is
updated.

```
Card (browser)
  │
  │  1. User presses "Start" button in the Rooms view
  │     VacuumCardActions.startSelectedRooms()
  │     → calls hass.callService("eufy_vacuum", "start_selected_rooms", { vacuum_entity_id, map_id, room_ids })
  │
  ▼
HA service bus
  │
  │  2. services.py handles "start_selected_rooms"
  │     → resolves EufyVacuumManager from hass.data[DOMAIN][DATA_RUNTIME]
  │     → manager.async_start_selected_rooms(vacuum_entity_id, map_id, room_ids)
  │
  ▼
EufyVacuumManager.async_start_selected_rooms()
  │
  │  3. Retrieves managed rooms for (vacuum, map) from storage
  │  4. Applies blocker rules: removes rooms where a "blocker" rule entity
  │     is in its blocking state
  │  5. Calls build_queue_from_managed_rooms() [queue_engine.py]
  │     → returns QueueEntry list sorted by room order
  │  6. Calls build_room_clean_payload() once with all enabled rooms
  │     → applies capability gating (e.g. strips water_level if no mop)
  │     → consumes the adapter's dispatch config to rename fields and
  │       map values to the brand's wire vocabulary
  │       (see docs/dev/adapter-config-reference.md §13)
  │     → returns PayloadItem list (canonical, framework-internal names)
  │       plus a wire-shape "payload" dict (brand-specific names)
  │  7. Calls build_active_job_state() [queue_engine.py]
  │     → freezes queue + payload into an ActiveJobSnapshot (immutable after this)
  │     → assigns job_id (UUID), records started_at timestamp
  │  8. Stores the snapshot as the active_job record in memory + saves to storage
  │  9. Calls hass.services.async_call() with the service domain, name, and
  │     envelope shape resolved from the adapter's dispatch config
  │     (Eufy → vacuum.send_command with command=room_clean; other brands
  │     resolve to their own service signature — see porting-guide.md §3)
  │
  ▼
Upstream integration → vacuum hardware → robot starts moving
  │
  │  10. Robot state changes propagate back:
  │      sensor.*_task_status, sensor.*_dock_status,
  │      sensor.*_active_cleaning_target, vacuum.* all update in HA
  │
  ▼
__init__._handle_lifecycle_change()  [registered by _register_lifecycle_listeners()]
  │
  │  11. Fires on every relevant entity state change
  │  12. Calls manager.record_active_job_transition() to log state transition
  │  13. Calls manager.get_lifecycle_state() → evaluate_job_lifecycle() [job_monitor.py]
  │      → returns a lifecycle_state string:
  │        "active_job_running" | "mid_job_service" | "returning_to_dock" | etc.
  │  14. If lifecycle_state is in _ACTIVE_LIFECYCLE_STATES {"active_job_running",
  │      "mid_job_service"}, calls manager.record_active_lifecycle_observed()
  │      → sets has_observed_active_lifecycle = True on the active_job record
  │      This flag prevents a stale pre-run dock state (e.g. "drying") from
  │      immediately triggering finalization before the robot has moved.
  │  15. MappingTracker.start_job() is called on first active lifecycle state
  │      to begin collecting robot position samples
  │  16. Checks completion signals: task_status == "completed" AND
  │      active_cleaning_target is cleared AND has_observed_active_lifecycle
  │
  ▼  [on completion signals satisfied]
manager.finalize_learning_for_active_job()
  │
  │  17. LearningManager.finalize() is called
  │      → LearningJobFinalizer writes a completed-job JSON to:
  │         config/eufy_vacuum/learning/{vacuum_slug}/jobs/{job_id}.json
  │      → records outcome (status, rooms cleaned, duration, water usage, etc.)
  │  18. LearningStatsRebuilder.rebuild() recalculates aggregate stats from
  │      all job files for the vacuum (stats JSON written to disk)
  │  19. Returns finalize_result dict including job_path and outcome
  │
  │  20. manager.mark_active_job_finalized() clears the active_job record
  │  21. hass.bus.async_fire("eufy_vacuum_job_finished", payload)
  │      → any automations or scripts listening to this event are notified
  │  22. If the job had mop rooms: _register_post_job_water_amendment()
  │      watches dock_status for the post-dock wash cycle (~2s after finalization)
  │      and patches actual water usage into the completed-job JSON once the
  │      mop wash completes (dock transitions to "drying")
  │
  ▼
Learning data updated on disk; card will fetch updated metrics on next view
```

### 4.2 Theme Change Flow

From the moment a user edits a color token in the Theme view to the card re-rendering
with the new color.

```
Card (browser) — Theme view
  │
  │  1. User types a new hex value into a theme token input
  │     (data-theme-token="--evcc-accent", data-theme-color-input="...")
  │     VacuumCardBindings fires an "input" event handler
  │
  │  2. Handler reads all current token/color/alpha values from the DOM
  │     and calls VacuumCardActions.updateWorkingDraft({
  │       vacuum_entity_id, tokens: { "--evcc-accent": "#ff6b35", ... }
  │     })
  │     → calls hass.callService("eufy_vacuum", "update_working_draft", payload)
  │
  ▼
HA service bus
  │
  │  3. theme_services.py handles "update_working_draft"
  │     → resolves EufyVacuumManager
  │     → manager.update_theme_working_draft(vacuum_entity_id, tokens, colors, alpha)
  │
  ▼
EufyVacuumManager.update_theme_working_draft()
  │
  │  4. Merges the incoming token/color/alpha dicts into the "working_draft"
  │     sub-key of the vacuum's theme record in storage
  │  5. The working_draft is per-vacuum; it holds unsaved edits separately
  │     from the committed theme library entries so the user can revert
  │  6. Calls async_save() → EufyVacuumStorage.async_save()
  │     → HA Store writes the updated dict to .storage/eufy_vacuum.storage
  │  7. Triggers a write to the sensor.*_{objectId}_theme_state entity
  │     by calling async_write_ha_state() on the ThemeStateSensor
  │     → the sensor's state and attributes reflect the new working draft
  │
  ▼
HA entity registry — sensor.*_theme_state updated
  │
  │  8. HA pushes the updated hass object to all connected Lovelace cards
  │     (this is the standard HA hass update mechanism, not a special channel)
  │
  ▼
EufyVacuumCommandCenter.set hass(hass)   [main.js]
  │
  │  9. _findThemeSensor(hass) locates the sensor.*_{objectId}_theme_state entity
  │  10. state.setBackendThemeState(sensor.attributes)
  │      → VacuumCardState stores the new token values in its internal state tree
  │  11. _scheduleRender() queues a microtask render via Promise.resolve().then()
  │
  ▼
EufyVacuumCommandCenter._render()
  │
  │  12. applyThemeToCard(this) reads current token values from state and
  │      sets CSS custom properties on the shadow root host element:
  │        this.style.setProperty("--evcc-accent", "#ff6b35")  (conceptually)
  │  13. buildRenderContext(card) assembles the render context
  │  14. renderView(ctx) calls the active view renderer — because the Theme
  │      view is active, renderThemeView() re-renders the editor with the
  │      new values reflected in the color inputs and preview swatches
  │  15. The card compares the new HTML string against the previously rendered
  │      HTML (stored in dataset.renderedHtml) and only writes innerHTML if
  │      the content actually changed — preventing unnecessary DOM thrash
  │
  ▼
User sees the updated color applied immediately in the preview
```

Note the asymmetry: the draft update path goes **card → service → storage → sensor →
hass update → card**. The card never applies a theme change locally without going
through the backend first. This ensures the backend is always the source of truth,
meaning a page refresh or a second browser session will always see the same state.

---

## 5. State Persistence

Three distinct persistence tiers are used, each chosen for different access patterns
and failure-isolation reasons.

### 5.1 HA Storage (`eufy_vacuum.storage`)

**Location:** `config/.storage/eufy_vacuum.storage` (managed by HA's `Store` helper)

**Written by:** `EufyVacuumStorage.async_save()`, called by the manager after every
mutation.

**Schema root keys:**

| Key | Contents |
|---|---|
| `vacuums` | Per-vacuum config: managed rooms, active job snapshot, queue state, runtime transitions, maintenance counters, capabilities |
| `maps` | Per-map "bucket": map metadata, room definitions keyed by map_id |
| `theme` | Theme library (saved themes), per-vacuum working draft and active theme assignment |
| `analytics` | Aggregate runtime analytics |
| `maintenance` | Component wear counters and dock event timestamps |
| `dock_events` | Timestamped records of mop wash, dust empty, and dry start events |
| `icons` | User-assigned room icons |
| `onboarding` | Setup workflow state |

**Access pattern:** Read once on `async_initialize()`, then mutated in memory and
flushed to disk on every service call that changes state. HA's `Store` batches writes
automatically so rapid mutations do not hammer the filesystem.

**Do not edit directly.** HA creates a `.corrupt` backup if the write is interrupted
and will silently revert to that backup on next restart. Always use the HA UI or
service calls to mutate this file.

### 5.2 Flat Files on Disk — Learning System

**Location:** `config/eufy_vacuum/learning/{vacuum_slug}/`

**Written by:** `LearningHistoryStore`, `LearningJobFinalizer`, `LearningStatsRebuilder`

**Directory structure:**

```
config/eufy_vacuum/learning/
└── {vacuum_slug}/          e.g. alfred
    ├── jobs/               one JSON file per finalized job
    │   └── {job_id}.json
    ├── learned/            per-room learned timing/area stats
    │   └── stats.json
    ├── live/               in-progress job snapshot (written during job)
    └── exports/            optional CSV exports
```

**Why flat files instead of HA storage?** See §6.2.

**Access pattern:** Written once per job finalization; read on demand when the card
requests metrics or ETA estimates. The stats.json file is rebuilt from all job files
by `LearningStatsRebuilder` after each finalization.

### 5.3 Flat Files on Disk — Mapping System

**Location:** `config/eufy_vacuum/mapping/`

**Written by:** `MappingManager`

**Contents:** Affine transform calibration data, room boundary polygons, and archived
trace run JSON files. These are separate from learning data because they are spatial /
geometric rather than temporal.

**Location:** `config/eufy_vacuum/maps/` (served as static HTTP)

Map images (PNG) are also stored on disk and served as static paths at
`/eufy_vacuum/maps/`. This is registered in `async_setup()` so the card can reference
them by URL without needing HA authentication.

### 5.4 Runtime-Only (in-memory)

The following state is held only in `EufyVacuumManager`'s Python object. It is
lost if HA restarts, but it is either reconstructible or only meaningful for the
duration of a running process:

- `MappingTracker` position sample buffer (current-job trace in progress)
- Resolved capability detection cache (rebuilt from entity registry on restart)
- Event listener unsub handles
- Render scheduling timers in the card

---

## 6. Key Design Decisions

### 6.1 Single central manager rather than per-entity classes

A common HA integration pattern is to create one coordinator or entity class per
device. `eufy_vacuum` deliberately uses a single `EufyVacuumManager` object for all
vacuums registered in the same config entry.

**Why:**

A cleaning job touches many concerns simultaneously: the room config, the queue, the
active job record, the lifecycle tracker, the learning system, and the HA entity state.
If these were spread across per-entity classes, every cross-cutting operation (e.g.
"finalize the job and update the theme sensor and save storage") would require either
complex coordinator message-passing or shared mutable state anyway.

The manager acts as a facade: service handlers resolve it from `hass.data` and call
high-level methods like `async_start_selected_rooms()` or
`finalize_learning_for_active_job()`. The manager is then responsible for sequencing
all the sub-operations atomically from the caller's perspective.

The trade-off is that `core/manager.py` is large. The queue engine and job monitor
are extracted as separate pure modules precisely to keep the logic testable; the
manager orchestrates them rather than duplicating their logic.

### 6.2 Flat-file learning storage rather than HA storage

Learning job records (the per-job JSON files) are stored as flat files rather than
inside the HA `.storage` blob. The concrete file layout, schema versions, and
rebuild path are documented in [learning-system.md](learning-system.md).

**Why:**

HA storage is designed for small configuration blobs that are loaded entirely into
memory on startup. The learning system can accumulate hundreds of job records, each
containing detailed per-room timing, water usage, mop wash counts, and transition
history. Loading all of this into a single Store object on every HA restart would be
expensive and the Store API offers no partial-load or streaming capability.

Flat files also make the data directly inspectable and portable. A developer can open
any `{job_id}.json` in a text editor, write a script to analyze trends, or delete
individual records without touching the integration's configuration state. The learning
data is informational and advisory (it feeds ETA estimates), so the cost of losing it
on a filesystem failure is much lower than losing room configuration.

The `LearningStatsRebuilder` exists specifically because of this design: if job files
are deleted or corrupted, the stats can be rebuilt from whatever files remain by
replaying them.

### 6.3 Card uses a mixin/module pattern rather than a component framework

The card is a plain Web Components `HTMLElement` subclass with no framework (no
Lit, no React, no Vue). The behaviour is distributed across focused modules that are
composed into the card class at construction time:

- `VacuumCardState` — read-only HA state projection
- `VacuumCardRenderers` — pure HTML string generators keyed by view name
- `VacuumCardBindings` — event listener wiring (attaches after each render)
- `VacuumCardActions` — HA service call wrappers
- `LearningController` — learning-specific data fetch and presentation logic

**Why not a framework?**

Lovelace custom cards must be single-file bundles importable as ES modules without a
build system *or* bundled with their own dependencies. Framework overhead (even Lit's
~15 KB) adds to load time for something running inside the HA sidebar, and reactive
frameworks introduce complex reconciliation paths that are hard to reason about when
the data source (the `hass` object) is a single external push, not an internal signal
store.

The module pattern lets each concern be edited, tested, and reasoned about in
isolation. The render cycle (`render-cycle.js`) is the single orchestration point:
`buildRenderContext()` assembles a context object, `renderHeader()` and `renderView()`
produce HTML strings, and the card's `_render()` method diffs those strings against
the cached `dataset.renderedHtml` values before writing `innerHTML`. This is a
hand-rolled virtual-DOM approach with deliberately minimal scope.

**The trade-off:** Because there is no reactive framework, every path that changes
displayed state must explicitly call `_scheduleRender()`. This is why the `set hass()`
setter schedules multiple debounced refresh timers on every HA update — each one
fetches a different data payload from the backend and then re-renders.

---

## 7. Concurrency & Thread Safety

The integration is single-process Python. Most code runs on Home Assistant's
asyncio event loop, but a few intentional paths offload work to HA's
**executor thread pool** (`hass.async_add_executor_job`) — for CPU-bound
finalization, blocking file I/O, and anything that would otherwise stall
the loop. Crossing that thread boundary is where bugs live.

### 7.1 Rule

**Calls into Home Assistant APIs must originate on the event loop thread.**
Three calls are the most common offenders:

| API | What goes wrong off-loop |
|---|---|
| `hass.async_create_task(coro)` | Logs a `helpers.frame` warning; in some HA builds, raises or schedules onto the wrong loop. |
| `entity.async_write_ha_state()` | Silently no-ops or trips the same warning; the entity's state never updates from that call. |
| Any `@callback`-decorated handler invoked directly | Same class of failure as above — `@callback` is a marker that the body assumes loop context. |

If you must originate the call from a worker thread, route through one of the
three bridges below.

### 7.2 The three bridges

```python
# 1. Schedule a coroutine on the event loop, from any thread.
asyncio.run_coroutine_threadsafe(coro, hass.loop)

# 2. Run a sync @callback on the event loop, from any thread.
hass.loop.call_soon_threadsafe(my_callback)

# 3. Run a sync function on a worker thread, from the event loop.
await hass.async_add_executor_job(blocking_func, *args)
```

Bridges 1 and 2 push *into* the loop. Bridge 3 pulls work *out* of it.

### 7.3 Context detection pattern

Helpers that may be called from either context (e.g. a manager method that
fires from both a state-change listener on the loop *and* a finalizer running
in an executor) detect their context and dispatch accordingly:

```python
import asyncio

def _schedule(self, coro):
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is self._hass.loop:
        self._hass.async_create_task(coro)
    else:
        asyncio.run_coroutine_threadsafe(coro, self._hass.loop)
```

`asyncio.get_running_loop()` raises `RuntimeError` when called from a thread
with no running loop, which is exactly the worker-thread case.

### 7.4 Listener fan-out pattern

Manager classes that publish change notifications to many entities (the
battery health manager and the theme sensor both do this) keep the iteration
synchronous and let each listener handle its own dispatch. The publisher
makes no assumption about who's listening:

```python
def _notify(self, vacuum_entity_id):
    for cb in list(self._update_listeners):
        try:
            cb(vacuum_entity_id)
        except Exception:
            _LOGGER.exception("...")
```

Each listener wraps its own state write:

```python
def _on_manager_update(self, vacuum_entity_id):
    if vacuum_entity_id != self._vacuum_entity_id:
        return

    @callback
    def _write():
        self.async_write_ha_state()

    self.hass.loop.call_soon_threadsafe(_write)
```

This is more conservative than necessary when the publisher *always* runs on
the loop, but keeps publishers simple and listeners independently safe — even
new listeners added by other subsystems can't break the contract.

### 7.5 Where this applies in the codebase

| Subsystem | Off-loop entry point | Bridge used |
|---|---|---|
| Battery health (`battery/manager.py`) | `record_job_metrics` (called from `JobFinalizer.finalize_from_inputs` running in executor) | Context-detecting `_schedule_save`; `call_soon_threadsafe` in sensor listeners |
| Battery health (`battery/sensors.py`) | Same as above (notify fan-out) | `call_soon_threadsafe` around `async_write_ha_state` |
| Sensor platform (`sensor.py`) | Manager callbacks may fire from worker threads | `_request_entity_state_write()` helper at top of file — same pattern, integration-wide |
| Learning system (`learning/job_finalizer.py`) | The whole finalize body runs in an executor | All HA-API calls inside it are routed through `hass.async_add_executor_job` boundaries or use thread-safe variants |
| Mapping system (`mapping/`) | File I/O on disk (separate concern, not thread safety) | Tracked separately — see the issue tracker |

### 7.6 Detecting violations

HA's runtime will surface offenders as `homeassistant.helpers.frame`
warnings:

```
Detected that custom integration 'eufy_vacuum' calls
hass.async_create_task from a thread other than the event loop
```

These never crash on their own but indicate a real bug. Treat any new
warning of this shape as a regression even if the integration appears to
work.

There is **no static check** — the warning fires only when the offending
path actually executes. If you add code that runs in an executor and
touches HA APIs, exercise it locally before assuming it's safe.

---

## 8. Extension Points

### Adding a new HA service

1. Define a new `SERVICE_*` constant in `const.py`.
2. Add a Voluptuous schema and handler function in the appropriate `*_services.py` file
   (or create a new one following the existing pattern).
3. Register it in the module's `async_register_*_services()` function.
4. Add the corresponding unregister call in `async_unregister_*_services()`.
5. If the service needs to mutate manager state, add a method to
   `EufyVacuumManager` and call it from the handler.

### Adding a new HA entity type

1. Create or extend a platform file (`sensor.py`, `button.py`, etc.).
2. Add the platform name to `PLATFORMS` in `__init__.py` if it is new.
3. HA will call `async_setup_entry` on the platform automatically.

### Adding a new card view

1. Add the view key to the `VIEWS` constant object in `render-cycle.js`.
2. Add it to the `VIEW_ORDER` array (controls DOM order and tab order).
3. Add a nav tab `<button>` in `renderHeader()`.
4. Add a `case VIEWS.YOUR_VIEW:` branch in `renderView()` that delegates to
   `renderers.renderYourView?.(ctx)`.
5. Implement `renderYourView(ctx)` in an appropriate renderer module under
   `src/renderers/` and export it from `src/renderers/index.js`.
6. If the view needs backend data, add a `_scheduleYourDataRefresh()` method
   following the debounce timer pattern used by `_scheduleMetricsRefresh()` and
   call it from `set hass()` (or from `setView()` for on-demand fetches).

### Adding a new room rule kind

Room rules are evaluated in the manager's `_normalized_managed_rooms_with_automation()`
path. The existing kinds are `blocker` (prevents room from running when an entity is
in a specified state) and `modifier` (overrides a room setting based on entity state).

To add a new kind:

1. Define the kind string in `const.py` or the room profiles module.
2. Add evaluation logic in the manager's rule resolution path.
3. If the rule requires a runtime HA entity listener (like `blocker` does), register
   it in `_register_path_blocker_listeners()` or add a parallel registration function
   following the same pattern in `__init__.py`.
4. Add editor UI for the new rule kind in the Room Rules view renderer in the card.

### Porting to a different vacuum ecosystem

A port is one adapter config dict. **No framework code changes are
required** for any of the four most common brands (Eufy, Roborock,
Dreame, Narwal).

Every brand-specific fact — entity IDs, vocabulary, water tank
measurements, upkeep guides, the service call envelope, the per-room
payload field names and value vocabularies — is read at runtime from
`get_adapter_config(vacuum_entity_id)`. The Eufy adapter at
`adapters/eufy/adapter.py` is the reference implementation.

See:

- [porting-guide.md](porting-guide.md) — the workflow and a worked
  brand catalog (Eufy / Roborock / Dreame / Narwal) covering the
  dispatch shape, lifecycle vocabulary translation, capability
  declarations, and testing.
- [adapter-config-reference.md](adapter-config-reference.md) — the
  canonical schema reference. Every section in the adapter config
  is documented field-by-field with examples and UI-builder notes.

The queue engine, learning system, mapping subsystem, theme system,
error tracker, water amendment watcher, and card are all
vacuum-agnostic. The only remaining brand-specific surface (outside
the adapter folder) is the integration's name, HA domain string
(`eufy_vacuum`), and the frontend card filename — none of which are
porting blockers.
