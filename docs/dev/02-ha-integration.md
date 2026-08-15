# 02 — HA Integration Layer

Covers the Home Assistant-specific plumbing of `eufy_vacuum`: config entry
lifecycle, entity platforms, services, storage, event bus, and the background
watchers that run while the integration is loaded. Read this when you want to
add a new entity, service, or HA event.

> **Naming.** The integration's **domain is `eufy_vacuum`** and is effectively
> permanent: it keys every entity ID, the storage file (`eufy_vacuum.storage`),
> the config entries, and the service names — changing it would break every
> existing install. The user-facing **product name is "Vacuum Agent"** (the
> sidebar panel title and the GitHub repo). So throughout the code and these
> docs, `eufy_vacuum` always means the domain/identifier while "Vacuum Agent" is
> the display name — they are not interchangeable.

---

## 1. Integration Entry Points

### `async_setup` (`__init__.py`)

Called once when the domain is first loaded. It:

- Ensures two directories exist under `hass.config.config_dir`:
  `eufy_vacuum/maps` (user-writable map images) and `eufy_vacuum/locales`
  (user-writable drop-in translation JSON that persists across HACS updates,
  like maps). The `locales` directory gets an auto-generated `index.json`
  listing its `*.json` files so the card can discover and load each at runtime.
  The `frontend` and `textures` directories are package-relative — they ship
  inside the installed integration and are not created under `config_dir` (the
  shipped/default `frontend/locales` directory is likewise package-relative).
  The `locales` index only lists real, regular `.json` files (never
  `index.json` itself and never a symlink) — the directory is served
  statically, so keeping the index that narrow means a stray symlink placed
  there is never advertised or auto-loaded by the card.
- Registers **six** static HTTP paths via `hass.http.async_register_static_paths`:
  - `/eufy_vacuum/maps` → persisted map image files (`cache_headers=False`)
  - `/eufy_vacuum/textures` → shipped floor-texture assets (`cache_headers=True`)
  - `/eufy_vacuum/frontend` → the compiled card JS bundle (`cache_headers=False`)
  - `/eufy_vacuum/fonts` → shipped webfonts (`frontend/fonts/`,
    `cache_headers=True`) — its own path purely for caching: the bundle path
    deliberately disables caching so a redeploy is picked up, while a woff2
    never changes between releases and must not be re-fetched on every page
    load
  - `/eufy_vacuum/user_fonts` → user drop-in webfonts (`cache_headers=False`) —
    cache OFF like the other drop-in directories, because a user iterating on a
    descriptor must see the edit on refresh; the woff2 files themselves ride
    heuristic caching, acceptable churn for a user-supplied asset that can
    change under the same name
  - `/eufy_vacuum/locales` → user-supplied drop-in translation JSON files (from
    `config/eufy_vacuum/locales/`, `cache_headers=False`)
- Registers the cards bundle as a **global frontend module**
  (`frontend.add_extra_js_url`, ES module) so the room card and dashboard card
  are defined on every HA page — including a cold dashboard that never opens
  the sidebar panel. Two guards: the bundle file must exist (an older deploy
  skips registration rather than advertise a 404) and the frontend component
  must be set up (absent in headless/test contexts). The full panel bundle
  also defines these cards; a `defineCard` guard makes the resulting double
  registration a no-op.

### `async_setup_entry` (`__init__.py`)

The main entry point. Called when the config entry is loaded. In order:

1. Constructs the `AdapterCoordinator` (the per-entry adapter registry) and
   stores it at `hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]`. It is built
   **before** the manager so that all subsequent adapter registration (stored
   adapter configs + per-vacuum code adapters) lands in the coordinator's
   registry rather than the fallback module-level dict.
2. Instantiates `EufyVacuumManager`, registers `manager.async_shutdown` via
   `entry.async_on_unload` (**before** `async_initialize()`, so a mid-setup
   failure still tears down — RP-003/INIT-1; `async_shutdown` is idempotent),
   then calls `manager.async_initialize()` to load persisted storage. An
   initialization failure raises `ConfigEntryNotReady` (HA retries). If the
   entry carries a `vacuum_entity_id` (config or options), `ensure_vacuum_record`
   makes it a managed vacuum; an options-update listener reloads the entry on
   change; a one-time registry pass removes orphaned icon-select entities.
3. Loads stored adapter configs (`load_stored_adapter_configs`, from
   `data["adapters"]`), then registers the brand code adapter for each known
   vacuum via `register_brand_adapter` (`adapters/brands.py` registrar table —
   override → detect → default arm; code adapters overwrite stored for the
   same vacuum). A local mid-setup unwind ledger (`_unwind_stack`,
   RP-039/RF-16) is created just before this step; adapter registration itself
   pushes nothing onto it (a failed attempt's coordinator is simply replaced
   by a fresh one next attempt). **From the next step on**, every newly
   registered resource IS pushed onto that ledger, walked in reverse if a
   later step raises — deliberately separate from `entry.async_on_unload`,
   which also fires on every normal unload and would run each undo twice.
4. Stores the manager at `hass.data[DOMAIN][DATA_RUNTIME]` and at
   `entry.runtime_data` (first ledger entries pushed here).
5. Instantiates `LearningManager`, stores it at
   `hass.data[DOMAIN][DATA_LEARNING]`, then warms the learning estimate
   read-caches per vacuum off-loop (`LearningHistoryStore.warm_estimate_caches`
   via executor — so the loop-bound dashboard-snapshot estimate never blocks on
   disk, not even on the first snapshot after restart).
6. Instantiates `BatteryHealthManager` and calls its `start(...)`; stores at
   `hass.data[DOMAIN][DATA_BATTERY]`.
7. Instantiates `ErrorTracker` and calls `error_tracker.start(known_vacuum_ids)`;
   stores at `hass.data[DOMAIN][DATA_ERROR_TRACKER]`.
8. Registers the inline `battery_rebaseline` service.
9. Instantiates `MappingTracker` (last of the subsystems); stores it at
   `hass.data[DOMAIN]["mapping_tracker"]`. Registers position entities for
   vacuums whose capability map includes `robot_position_x`/`robot_position_y` —
   in practice Eufy only, and NOT a pose source (see
   [Eufy adapter](25-eufy-adapter.md#4b-raw-robot-position-is-not-a-pose-source)).
10. Calls the remaining service registration functions: `async_register_services`,
   `async_register_learning_services`, `async_register_theme_services`,
   `async_register_mapping_services`.
11. Registers background listeners by calling each listener module's
   `register(hass)`: `lifecycle.register(hass)`, `job_metrics.register(hass)`,
   `dock_events.register(hass)`, `path_blockers.register(hass)`,
   `pause_timeout.register(hass)`, `stall_capture.register(hass)`,
   `job_progress.register(hass)`, `pose_sampler.register(hass)`,
   `discovery.register(hass)`. (`pose_sampler` samples external-run robot pose
   while a run is active, feeding room auto-attribution; `stall_capture` is an
   opt-in consumer of `EVENT_STALL_DETECTED` and does nothing until armed
   per-vacuum.) See the `listeners/` package for the per-group implementations.
12. Forwards setup to the **six** entity platforms: `binary_sensor`, `button`,
   `switch`, `select`, `number`, `sensor` (`PLATFORMS` in `__init__.py`).
13. Registers one sidebar panel per managed vacuum via
   `panels.async_register_vacuum_panel`. Panel URLs are stored at
   `hass.data[DOMAIN][f"_panels_{entry.entry_id}"]` — the entry's panel
   teardown ledger. Panels registered *after* startup (setup workflow's
   `add_vacuum`, the `setup_set_panel_title` rename) join the same ledger via
   `panels.append_to_panel_ledger` (RP-039/RF-16), so they are cleanly removed
   on unload too.

If no vacuum is managed yet, steps 4–13 still run, but step 13 registers a
single fallback panel at url `eufy-vacuum` (the shared `DEFAULT_PANEL_TITLE`
constant, `"Vacuum Agent"`, rather than a per-vacuum title; empty `config={}`)
instead of a per-vacuum panel.

### `async_unload_entry` (`__init__.py`)

1. Unloads all entity platforms. Everything below runs only if that succeeds.
2. Invalidates the room-source cache (`invalidate_room_source_cache`,
   RP-007/SRC-5) — a reloaded entry must not serve the previous life's cache
   as fresh.
3. Removes each registered sidebar panel (from the `_panels_{entry_id}` ledger).
4. Removes all background listeners by calling each listener module's
   `remove(hass)` (including `pose_sampler.remove(hass)`).
5. Calls all service unregistration functions, and removes the inline
   `battery_rebaseline` service.
6. Stops any active debug flight-recorder capture (`get_capture().stop()`) so a
   reload doesn't inherit a `propagate=False` / DEBUG logger.
7. Pops and stops `mapping_tracker` (`unregister_all()`), the battery manager
   (`stop()`), and the error tracker (`stop()`).
8. Unregisters adapter configs, then pops `DATA_ADAPTER_COORDINATOR` and calls
   `coordinator.shutdown()` (wrapped in `try/finally` so shutdown always runs).
9. Clears the remaining runtime keys from `hass.data[DOMAIN]` (dropping the
   whole domain dict when it is left empty).

Separately, HA runs the `entry.async_on_unload` callbacks — including
`manager.async_shutdown()`, which flushes any pending debounced save directly
via storage and cancels the manager's background tasks/timers (dock pollers,
external-run grace timers). See [05 §7](05-core-manager.md).

### `async_remove_entry` (`__init__.py`)

Creates a bare `Store` and calls `async_remove()` to wipe persisted data.

### `async_remove_config_entry_device` (`__init__.py`)

```python
async def async_remove_config_entry_device(hass, config_entry, device_entry) -> bool
```

The HA hook that turns the device page's "Delete" into a **per-vacuum** teardown (the domain is a singleton config entry, so this removes one vacuum *in place* — it does **not** reload the entry). It tears the vacuum down via `_teardown_vacuum`, and `_schedule_clear_configured_vacuum` clears `CONF_VACUUM_ENTITY_ID` on the entry so `async_setup_entry` doesn't **resurrect** the removed vacuum on the next load.

### `hass.data[DOMAIN]` keys

| Key constant | Type | Description |
|---|---|---|
| `DATA_ADAPTER_COORDINATOR` (`"adapter_coordinator"`) | `AdapterCoordinator` | Per-entry adapter registry; constructed first (before the manager) and popped + `shutdown()` on unload |
| `DATA_RUNTIME` (`"runtime"`) | `EufyVacuumManager` | Core manager — all services and entities resolve through this key (also mirrored at `entry.runtime_data`) |
| `DATA_LEARNING` (`"learning"`) | `LearningManager` | Learning subsystem orchestrator |
| `DATA_ERROR_TRACKER` (`"error_tracker"`) | `ErrorTracker` | Active-run error latching and device error history |
| `DATA_BATTERY` (`"battery"`) | `BatteryHealthManager` | Battery-health tracking and per-job battery metrics |
| `"mapping_tracker"` | `MappingTracker` | Real-time robot position tracker |
| `f"_panels_{entry.entry_id}"` | `list[str]` | Panel URL paths registered for this entry (used for cleanup) |

---

## 2. Config Flow

`EufyVacuumConfigFlow` in `config_flow.py` is intentionally minimal:

- `CONF_VACUUM_ENTITY_ID` — an optional vacuum-entity selector (HA
  `EntitySelector`), and the primary field. Naming a vacuum here lets
  `async_setup_entry` register the per-vacuum sidebar panel for it.
- `CONF_TESTED_MODEL` — defaults to the `SUPPORTED_TESTED_MODEL` constant (from
  `adapters/eufy/const.py`). Display only.
- `CONF_NOTES` — optional free-text field.

`async_set_unique_id(DOMAIN)` + `_abort_if_unique_id_configured()` mean only
one config entry per HA instance is permitted.

**Options flow** (`EufyVacuumOptionsFlow`) exposes `CONF_VACUUM_ENTITY_ID` and
`CONF_NOTES` for editing after initial setup.

`config_entry.data` can contain `{"vacuum_entity_id": str, "tested_model": str,
"notes": str}`. `__init__.py` reads `vacuum_entity_id` to register the panel. Bulk
operational state (map IDs, room settings) lives in the storage layer rather
than the config entry — with one deliberate exception: `entity_overrides` is
written to the entry's **options** by the options flow, because that flow is the
rescue path that still works when the panel does not. It is merged with the
storage copy at setup and **entry options win**; see
[03 — Data model](03-data-model.md).

---

## 3. Entity Platforms

**Six** platforms are registered: `binary_sensor`, `button`, `switch`, `select`,
`number`, and `sensor`. All platform `async_setup_entry` functions pull
the manager from `hass.data[DOMAIN]["runtime"]`.

### select platform

A single integration-level **diagnostic** select — the debug flight-recorder
target, built by `debug_capture.build_debug_target_select(hass, domain=DOMAIN)`
(`select.py`). Not a per-room entity. (The old per-room *icon*-picker selects were
removed; the platform was **repurposed**, not dropped — CS-3.)

### Base pattern: `EufyVacuumRoomEntity`

`room_entities.py` defines `EufyVacuumRoomEntity(Entity)` — base class for all
per-room entities. It:

- Builds a stable `unique_id` via `make_room_unique_id(...)`.
- Sets `_attr_has_entity_name = True` (device name prepended by HA).
- Attaches `DeviceInfo` grouping all room entities under the vacuum's device
  via `build_vacuum_device_info(vacuum_entity_id)`.
- Exposes a `manager` property that resolves `hass.data[DOMAIN]["runtime"]` at
  call time — never cached.
- `_get_room_data()` reads from
  `manager.data["maps"][vacuum_entity_id][map_id]["rooms"][room_id]`.
- `_async_update_room(updates)` writes, persists, and triggers notifications.
- `available` returns `False` if the room record no longer exists in storage.
- `extra_state_attributes` returns the full room attribute set including
  `last_cleaned_at`, `last_vacuumed_at`, `last_mopped_at`, and adapter
  vocabulary for the card's dropdowns (see `room_entities.py`).

### `entity_helpers.py` utilities

| Function | Purpose |
|---|---|
| `build_vacuum_device_info(vacuum_entity_id)` | Returns `DeviceInfo` tying entities to the vacuum's HA device |
| `make_room_unique_id(...)` | Builds a stable `{vacuum_key}_{map_id}_{room_id}_{suffix}` unique ID |
| `sort_room_items(rooms)` | Sorts room dict by `order` then `name`; filters to `is_configured=True` |
| `get_floor_type_label(floor_type)` | Maps a floor_type key to a human-readable label |

### button platform

- **Maintenance reset buttons** — one per supported maintenance component per
  vacuum (brush roll, filter, side brush, etc.), conditioned on capability
  detection.
- **Saved run profile buttons** — dynamic; created when a run profile is saved
  with `expose_as_button = True`. A manager callback
  (`_on_run_profiles_updated`) syncs these dynamically. `async_press` **awaits**
  `manager.start_run_profile(...)` (a coroutine) then `async_save()` — awaiting it
  is load-bearing: an un-awaited call silently no-ops (#42, fixed). Pressing the
  button runs the full profile, including any charge/wait steps, exactly like the
  card's "Start Cleaning".

### switch platform

Per-room enable/disable toggles. One `EufyVacuumRoomEnabledSwitch` per room per
map. State reflects `room_data["enabled"]`. Toggling calls
`_async_update_room({"enabled": value})`.

### number platform

Per-room cleaning-queue position inputs. One `EufyVacuumRoomOrderNumber` per
room per map. Range 0–999 (step 1, `box` mode). Changing calls
`_async_update_room({"order": value})`.

All per-room entities (switch, number) inherit from
`EufyVacuumRoomEntity`. Room add/remove is handled dynamically via manager
callbacks; stale entities are removed from both the platform and entity
registry.

---

## 4. Sensor Package (`sensor/`)

`sensor/__init__.py` sets up all sensor entities and coordinates dynamic entity
sync. Individual sensor types live in sub-modules.

### Per-vacuum sensors (static, created at startup)

| Module | Class | Entity ID pattern | `native_value` |
|---|---|---|---|
| `sensor/profile.py` | `EufyVacuumProfileSensor` | `sensor.<obj>_available_profiles` | String count of available profiles |
| `sensor/maintenance.py` | `EufyVacuumMaintenanceRemainingSensor` | `sensor.<obj>_<component>_maintenance_remaining` | Remaining hours (float, `h`, `duration`) |
| `sensor/dock_event.py` | `EufyVacuumDockEventSensor` | `sensor.<obj>_dock_events` | ISO timestamp of most recent dock event |
| `sensor/theme.py` | `EufyVacuumThemeStateSensor` | `sensor.<obj>_theme_state` | Active theme name, or `"none"` |
| `sensor/onboarding.py` | `EufyVacuumOnboardingSensor` | `sensor.<obj>_onboarding_state` | Worst-case onboarding status |
| `sensor/error.py` | `EufyVacuumActiveRunErrorSensor` | `sensor.<obj>_active_run_error` | Active-run error message or `"none"` |
| `sensor/error.py` | `EufyVacuumLastDeviceErrorSensor` | `sensor.<obj>_last_device_error` | Last device error message or `"none"` |
| `sensor/lifecycle.py` | `EufyVacuumActiveJobSensor` | `sensor.<obj>_active_job` (per map) | Active-job lifecycle + room-progress state |
| `sensor/map_overlays.py` | `EufyVacuumMapOverlaysSensor` | `sensor.<obj>_map_overlays` | Current room name; attributes mirror the normalized `map_state_source` layers + overlay visibility (`DIAGNOSTIC`) |

`EufyVacuumMaintenanceRemainingSensor` is created per maintenance component
(`filter`, `rolling_brush`, `side_brush`, `mopping_cloth`, `cleaning_tray`,
`swivel_wheel`, `sensor`) conditioned on capability detection.

`EufyVacuumThemeStateSensor` sets `_attr_should_poll = False`; updated
exclusively via the theme update callback.

`EufyVacuumActiveRunErrorSensor` / `EufyVacuumLastDeviceErrorSensor` subscribe
directly to `ErrorTracker` update notifications via
`tracker.register_update_listener`. Companion `binary_sensor.<obj>_active_run_has_error`
lives on the `binary_sensor` platform.

### Per-room sensors (dynamic)

| Module | Class | Entity ID pattern | `native_value` |
|---|---|---|---|
| `sensor/room_history.py` | `EufyVacuumRoomCleaningHistorySensor` | `sensor.<obj>_<map_id>_<room_id>_cleaning_history` | ISO timestamp of last completed cleaning, or `None` |
| `sensor/room_rule_status.py` | `EufyVacuumRoomRuleStatusSensor` | `sensor.<obj>_<map_id>_<room_id>_rule_status` | Last rule evaluation result string |

Both inherit from `EufyVacuumRoomEntity`. `EufyVacuumRoomCleaningHistorySensor`
reads via `manager.get_room_cleaning_history(...)`.
`EufyVacuumRoomRuleStatusSensor` reads via
`manager.get_room_rule_status(...)`. Both set `_attr_should_poll = False`.

### How sensors subscribe to manager notifications

All sensor update paths funnel through `_request_entity_state_write(entity)`,
which schedules `async_write_ha_state()` via `hass.loop.call_soon_threadsafe`.
Required because manager callbacks can fire from worker threads.

Four manager callback types are registered in `async_setup_entry`:

| Callback | Trigger | Effect |
|---|---|---|
| `register_room_update_callback` | Room config added/removed/changed | Syncs room sensor lists dynamically |
| `register_room_history_update_callback` | Job finalized, history updated | Refreshes room history sensor states |
| `register_room_rule_status_update_callback` | Rule evaluation completed | Refreshes rule status sensor states |
| `register_theme_update_callback` | Theme saved/applied/draft changed | Refreshes theme state sensor |

All callbacks are unregistered on entry unload via `entry.async_on_unload`.

Room sensors also refresh on the `eufy_vacuum_job_finished` event and on a
1-hour `async_track_time_interval` timer.

`EufyVacuumMapOverlaysSensor` is driven by its own dedicated **60-second**
`async_track_time_interval` timer (separate from the 1-hour room timer). Each
tick calls `manager.async_refresh_map_state_source(...)` to warm the
`_map_state_source_cache` (so automations/templates see fresh overlay attributes
even when no dashboard is open) and then pushes the sensor state. An initial warm
runs shortly after setup.

---

## 5. Services Package (`services/`)

Services were previously in a single `services.py` file; after the bundle-out
refactor they live in the `services/` package. Each file groups related
handlers:

| Module | Domain |
|---|---|
| `services/__init__.py` | Registration entry point; calls sub-registration functions |
| `services/setup.py` | Panel-driven onboarding (`setup_*`) |
| `services/queue.py` | Queue/payload build, room selection, queue state reads |
| `services/job_control.py` | Job start, pause, resume, cancel, progress, status |
| `services/rooms.py` | Room field updates, managed room CRUD |
| `services/room_profiles.py` | Room profile CRUD |
| `services/run_profiles.py` | Saved run profile CRUD |
| `services/dock.py` | Dock commands (wash, dry, empty) |
| `services/maintenance.py` | Maintenance reset, dock event counts |
| `services/snapshots.py` | `get_lifecycle_state`, `get_dashboard_snapshot`, `get_upkeep_snapshot` |
| `services/access_graph.py` | Access graph editor and health check |
| `services/adapter_config.py` | Capability / adapter config reads |
| `services/_common.py` | Shared helpers (`_get_manager`, schema fragments, etc.) |
| `services/errors.py` | Error acknowledgement services |
| `services/debug.py` | Debug flight-recorder capture (start/stop/status) — backs the `select` platform's capture target (§3) |
| `services/stall_capture.py` | `set_stall_capture` (per-vacuum arming of the stall-capture consumer, [04 §6a](04-listeners.md)) and the flagged maintainer injector `dev_inject_stall` |

### Pattern

Each submodule owns its own registration: it exposes a module-level `SERVICES`
tuple of the service names it registers, and a `register(hass)` function that
makes the `hass.services.async_register` calls. `services/__init__.py` just
iterates the `_DOMAINS` submodule tuple — `async_register_services` calls every
submodule's `register(hass)`, and `async_unregister_services` walks every
submodule's `SERVICES` tuple and removes each name. There is no central registry
or unregister tuple in `services/__init__.py`.

```python
# services/job_control.py
async def _handle_start_selected_rooms(hass, call):
    manager = get_manager(hass)
    result = await manager.start_selected_rooms(...)
    await manager.async_save()
    return result

SERVICES = (
    SERVICE_START_SELECTED_ROOMS,
    # ... every other name this module registers
)

def register(hass):
    async def start_selected_rooms(call):
        return await _handle_start_selected_rooms(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_START_SELECTED_ROOMS, start_selected_rooms,
        schema=_START_SELECTED_ROOMS_SCHEMA,
    )
```

Services that return data are registered with `supports_response=True`. After
mutations, handlers call `await manager.async_save()`. Read-only handlers skip
the save.

### Service catalogue (abbreviated)

| Group | Examples |
|---|---|
| Setup | `setup_get_status`, `setup_add_vacuum`, `setup_import_active_map`, `setup_save_rooms`, `setup_delete_map` |
| Queue/payload | `discover_rooms`, `save_managed_rooms`, `build_queue`, `build_room_payload`, `get_queue_state`, `clear_queue` |
| Job control | `get_start_status`, `start_selected_rooms`, `start_zone_clean`, `start_run_profile`, `pause_active_job`, `resume_active_job`, `cancel_active_job`, `get_job_progress_snapshot`, `clear_active_job` |
| Dock actions | `wash_mop`, `dry_mop`, `stop_dry_mop`, `empty_dust`, `get_dock_action_status` |
| Snapshots | `get_lifecycle_state`, `get_dashboard_snapshot`, `get_upkeep_snapshot` |
| Room profiles | `get_room_profiles`, `save_user_room_profile`, `apply_room_profile`, `delete_room_profile` |
| Run profiles | `get_saved_run_profiles`, `save_run_profile`, `set_run_profile_steps`, `apply_run_profile`, `delete_run_profile` |
| Access graph | `get_room_access_editor`, `get_access_graph_health` |
| Capabilities | `get_vacuum_capabilities` |
| Errors | `acknowledge_error`, `get_recent_errors` |

### How to add a new service

1. Add the service name constant to `const.py`.
2. Pick the right `services/` sub-module for the domain, or create one (and add
   it to the `_DOMAINS` tuple in `services/__init__.py`).
3. Write `async _handle_<name>(hass, call) -> dict | None`. Call the manager.
   Call `async_save()` if state was mutated.
4. Register the service inside that submodule's `register(hass)` via
   `hass.services.async_register`.
5. Add the name to that submodule's module-level `SERVICES` tuple
   (`async_unregister_services` walks every submodule's tuple to remove them).
6. If the service is called from the card, add a handler in the card's service
   call module.

---

## 6. Storage Layer

`core/storage.py` defines `EufyVacuumStorage`.

### Wrapping HA's Store

```python
self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
```

- `STORAGE_VERSION = 1` (defined in `core/storage.py`)
- `STORAGE_KEY = "eufy_vacuum.storage"` — originates in `adapters/eufy/const.py` (a porting seam), only **re-exported** by `core/storage.py`

Written to `.storage/eufy_vacuum.storage`. **Never edit directly** — use HA UI
or integration services. Direct edits produce `.corrupt` backup files.

### Default empty structure (on first boot)

```python
# core/storage.py async_load() returns this for an empty store:
{
    "vacuums": {},
    "maps": {},
    "theme": {"library": {}, "default_theme_id": None, "vacuums": {}},
    "analytics": {},
    "maintenance": {},
    "dock_events": {},
    "onboarding": {},
    "error_tracker": {},
}
```

On top of that, `async_initialize` (`core/manager.py`) `setdefault`s **six**
top-level keys it depends on — `vacuums` (already present), `capabilities`,
`room_history`, `room_rule_status`, `learning_processing_enabled` (default
`True`), and `learning_pending_runs`. Every other key is created lazily by its
owning subsystem the first time it writes. (`analytics` is present in the
default but currently unused.) Do not assume a key exists on a fresh boot unless
it is in the storage default above or one of the keys the manager seeds.

See [03-data-model.md](03-data-model.md) for the complete shape of each key.

### What is stored vs runtime-only

**Stored in `.storage`:** all keys above.

**Runtime-only (in `hass.data[DOMAIN]` or in-memory on the manager):**
- Manager object, LearningManager, ErrorTracker, MappingTracker
- Background listener unsub handles
- Registered panel URL lists
- `manager.runtime` — `VacuumRuntimeState` dict rebuilt from HA state on restart

---

## 7. Event System

The integration fires **eleven** events on `hass.bus`. **Most** type-string
constants live in `const.py`; the two exceptions are `EVENT_ROOM_COMPLETED`
(defined locally in `mapping/tracker.py`) and `EVENT_STALL_CAPTURED` (defined
locally in `listeners/stall_capture.py`).

| Event constant | String value | Fired from | Key payload fields |
|---|---|---|---|
| `EVENT_ROOM_STARTED` | `eufy_vacuum_room_started` | `core/manager.py` (job start, `source="job_start"`) + `ActiveJobTracker` (`jobs/active_job.py`, timing rollover **and** native-signal path) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `started_at`, `source`, **`completed_room_ids`** (all three fire sites include it — see 06 §10) |
| `EVENT_ROOM_FINISHED` | `eufy_vacuum_room_finished` | `jobs/active_job.py` — timing rollover / bounds exit, **and** the native-signal path (`source="native_signal"`) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_at`, `source`, `actual_duration_minutes`, `confidence` (rollover only, 4dp; **the native-signal variant omits `confidence`** — 06 §10), `completed_room_ids` |
| `EVENT_JOB_FINISHED` | `eufy_vacuum_job_finished` | `listeners/lifecycle.py`, `listeners/pause_timeout.py`, `listeners/path_blockers.py` (forced cancel on a path block), `services/job_control.py`, `learning/services.py` | **Two shapes (06 §10):** the 11-key form (`vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail`, `used_for_learning`, `finalized_at`, `room_count`, `duration_minutes`, `actual_cleaning_minutes`, `job_path`) from the `_common.py` builders; the `finalize_learning_job` **service** path fires an inline **9-key** payload that **omits `duration_minutes` / `actual_cleaning_minutes`** (CS-2). |
| `EVENT_PATH_BLOCKED` | `eufy_vacuum_path_blocked` | `listeners/path_blockers.py` | The full `get_runtime_path_block_report(...)` dict (`trigger_entity_id`, `trigger_entity_state`, `affected_remaining_room_ids`, …) **augmented** with `path_block_action`, `action_taken`, and — only when a pause/cancel action ran — `action_result`. |
| `EVENT_STALL_DETECTED` | `eufy_vacuum_stall_detected` | `jobs/active_job.py` — `ActiveJobTracker.detect_run_anomalies` (called by the manager's `get_job_progress_snapshot`; deduped once per room per job) | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` |
| `EVENT_STALL_CAPTURED` | `eufy_vacuum_stall_captured` | `listeners/stall_capture.py` — after a capture lands, only when capture is armed for that vacuum (`data["vacuums"][<vid>]["stall_capture_enabled"]`, absent = off). **Constant defined in `listeners/stall_capture.py`, not `const.py`.** | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `image_path`, `message` — the path is on the event because the persistent notification (markdown) cannot embed a local image |
| `EVENT_ROOM_SKIPPED` | `eufy_vacuum_room_skipped` | `jobs/active_job.py` — `ActiveJobTracker.detect_run_anomalies` (non-sequential advance, ~never for Eufy; the manager only delegates to it from the snapshot composer) | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_room_ids` |
| `EVENT_RUN_INCOMPLETE` | `eufy_vacuum_run_incomplete` | **Five** finalize paths (06 §10 / finding B1): `learning/services.py`, `services/job_control.py` (manual cancel), `listeners/path_blockers.py` (rule cancel), `listeners/pause_timeout.py` (paused reap **and** stranded reap) | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids`, `missed_rooms` (no `map_id`) |
| `EVENT_JOB_PROGRESS_TICK` | `eufy_vacuum_job_progress_tick` | `listeners/job_progress.py` periodic tick | `vacuum_entity_id`, `map_id` — lightweight polling signal for automations |
| `EVENT_EXTERNAL_RUN_PENDING` | `eufy_vacuum_external_run_pending` | `learning/external_run.py` — `ExternalRunManager` finalizes an external (app-started) run to a pending review record | `vacuum_entity_id`, `map_id`, `record_path`, `segment_count`, `detection_ts` |
| `EVENT_ROOM_COMPLETED` | `eufy_vacuum_room_completed` | `mapping/tracker.py` (`MappingTracker._fire_room_completed`) — informational dwell event on a confident native-current-room transition (vacuums with `robot_position_x/y`). **Constant defined in `tracker.py`, not `const.py`.** | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `confidence`, `duration_seconds` (1dp), `entered_at` (ISO or `None`) |

### Subscribing in automations

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_job_finished
    event_data:
      vacuum_entity_id: vacuum.alfred
```

All events carry `vacuum_entity_id` so automations can filter by device.

---

## 8. Auto-Finalization

`listeners/lifecycle.py` registers a state-change watcher that automatically
finalizes a cleaning job when HA sensor states indicate the job is done. (This
logic previously lived in `__init__.py`; it moved into the `listeners/` package
and is wired via `lifecycle.register(hass)`.)

### Watched entities

`get_lifecycle_watch_entities(vacuum_entity_id)` (in `listeners/_common.py`)
returns the vacuum entity plus the entity IDs the adapter declares for each watch
key (`entities.get(key)`) — the IDs are **adapter-config-sourced**, not a fixed
`sensor.{object_id}_<key>` naming convention:
- the vacuum entity itself (`vacuum.{object_id}`)
- `task_status`
- `dock_status`
- `active_cleaning_target`
- `active_map`
- `job_active` — the recharge-resume binary (a sensor that stays ON through a
  mid-job recharge dock); appended only when the adapter declares it (e.g.
  Roborock), so it is absent for brands like Eufy. Watching it ensures the job
  re-evaluates for finalization when it clears at the true finish.

### `has_observed_active_lifecycle` guard

The job is not eligible for auto-finalization until the manager has reported at
least one `"active_job_running"` or `"mid_job_service"` lifecycle state. This
prevents a stale pre-run dock state (e.g. `dock_drying`) from triggering
finalization before cleaning started.

### Finalization condition

The gate is adapter-configurable (multi-brand). All three must be simultaneously
true:
1. `task_status` equals the adapter's `completion.task_status_value` (default
   `"completed"`).
2. The **secondary** requirement is satisfied (`completion_secondary_satisfied`):
   - default (Eufy): `active_cleaning_target` reads a clear sentinel from
     `completion.secondary_clear_sentinels` (default `{"", "unknown",
     "unavailable", "none", "null"}`).
   - brands with `completion.require_job_active_clear` (Roborock): the sentinel
     check is **bypassed** (returns `True`) — Roborock's `active_cleaning_target`
     (`current_room`) reverts to the dock room's name at the end of a run and
     never sentinels, so the job-active binary clearing is the real completion
     signal, enforced by the recharge-resume guard below.
3. `has_observed_active_lifecycle == True` on the active job record.

`vacuum.state == "docked"` is intentionally not required — requiring it stranded
active job records when the vacuum was still returning.

Two suppression guards then run before finalizing:
- **Recharge-resume guard:** if `is_job_active(...)` is on (the `job_active`
  binary stays ON through a mid-job recharge dock), finalization is skipped so the
  resumed half stays the same job. No-op for brands without `entities.job_active`.
- **Strict-order `_phase_dispatch_pending` guard:** a just-advanced sequenced
  phase has not been confirmed cleaning yet, so the prior room's lingering
  completion signals must not finalize the new phase. No-op for non-sequenced
  (atomic) jobs.

### What happens on finalization

1. `manager.maybe_advance_phase(...)` — for **sequenced (strict-order)** jobs a
   completed phase advances (re-dispatch) and the handler returns instead of
   finalizing; only the last phase finalizes. Sequenced jobs arise from a run
   profile carrying ordered `steps` (room groups split by `charge_wait`/`wait`
   stops, materialized 1:1 into `active_job["phases"]`, any brand) or a Roborock
   strict-order run; a `charge_wait` phase routes to the charge poller and a `wait`
   phase to the hold timer rather than the clean-dispatch watchdog. Atomic jobs
   (a plain, unstepped run) return `False` here and fall through.
2. `manager.finalize_learning_for_active_job(...)`.
3. `mapping_tracker.end_job(...)` (run on the executor — it does disk I/O for
   bounds/raw-sample writes).
4. `manager.mark_active_job_finalized(...)`.
5. Fires `EVENT_JOB_FINISHED`.
6. For mop jobs: a post-job water amendment registers a temporary dock-status
   watcher to capture post-job mop wash water consumption and patch the job file
   after drying starts (or after a timeout).
7. `manager.async_save()`.

### Pause timeout watchdog

`listeners/pause_timeout.py` (`pause_timeout.register(hass)`) sets up a 1-minute
`async_track_time_interval`. On each tick it calls
`manager.get_paused_job_timeout_report(...)` for each active map. If a timeout
has been exceeded, it calls `manager.async_cancel_active_job(...)` and fires
`EVENT_JOB_FINISHED`.

---

## 9. Dock Event Listeners

`listeners/dock_events.py` (`dock_events.register(hass)`) watches a managed
vacuum's dock-status entity **only when both** hold: the adapter's
`dock_events.enabled` flag is truthy — `config_schema.py` declares the field
with no enforced default (its `description` documents the intent, "Default:
False", but the schema has no `"default"` key for it); the actual default is
the call-site `get_adapter_value(..., "dock_events", "enabled", fallback=False)`
(`listeners/dock_events.py:58`, REG-4), checked first, before anything else
runs for that vacuum — **and** the adapter declares `entities.dock_status`. Declaring
`entities.dock_status` alone is not sufficient — an adapter that declares the
entity but leaves `dock_events.enabled` unset gets no listener at all. The
watched entity ID itself is adapter-config-sourced
(`entities.dock_status`), not a fixed `sensor.{object_id}_dock_status` naming
convention. The trigger values are read from the adapter config at
`dock_events.triggers` rather than a module-level constant — by
default they map roughly as:

```python
{
    "last_mop_wash":   {"washing", "washing mop"},
    "last_dust_empty": {"emptying dust", "emptying dust bin", "dust emptying"},
    "last_dry_start":  {"drying", "drying mop", "drying pads", "mop drying"},
}
```

When `dock_status` transitions to any trigger value:
`manager.record_dock_event(vacuum_entity_id, event_type, dry_duration)` is
called and the manager is saved. For `last_dry_start`, the current value of the
dry-duration entity (adapter `entities.dry_duration`) is captured.

Records are exposed through `EufyVacuumDockEventSensor`.

---

## 10. Repairs

Removed (RP-040 closing batch, #10:INF-6). `repairs.py` defined
`EufyVacuumSetupRedirectFlow`, a repair-issue redirect to the sidebar panel,
but nothing in the codebase ever called `async_create_issue` /
`ir.create_issue` for the `eufy_vacuum` domain — a repo-wide grep confirmed
zero callers. The flow was reachable only by HA's own repairs UI, which never
had an issue to show it. Deleted along with the `issues.onboarding_required`
strings entries it existed to service.

---

## 11. Frontend Panel

The integration registers a custom sidebar panel per managed vacuum. All
registration is centralized in `panels.py` (`async_register_vacuum_panel`) so the
three call sites — startup (`__init__.async_setup_entry`), add-a-vacuum
(`setup/workflow.add_vacuum`), and the live rename service
(`services/setup.setup_set_panel_title`) — compute the title and register the
panel identically. The sidebar **title is per-vacuum and user-settable**: it is
stored on the managed-vacuum record (`panel_title`) and resolved via
`effective_panel_title(record)`, which falls back to `"Vacuum Agent"` when unset.

```python
# __init__.async_setup_entry — per managed vacuum
panel_url = await async_register_vacuum_panel(
    hass,
    vacuum_entity_id,
    title=effective_panel_title(record),   # stored panel_title, default "Vacuum Agent"
)

# panels.async_register_vacuum_panel — the single registration helper
await panel_custom.async_register_panel(
    hass,
    frontend_url_path=panel_url,            # f"eufy-vacuum-{object_id}"
    webcomponent_name="eufy-vacuum-command-center",
    js_url=panel_js_url(),                  # "/eufy_vacuum/frontend/...js?v=<mtime>"
    sidebar_title=title,
    sidebar_icon="mdi:robot-vacuum",
    config={"vacuum_entity_id": vacuum_entity_id},
    require_admin=False,
    embed_iframe=False,
)
```

The `?v=<mtime>` fingerprint is computed from the bundle file's mtime — a fresh
deploy busts the HA service-worker cache automatically without a manual version
bump. The `config` dict is injected into the panel web component as a property.

**Live rename.** The `setup_set_panel_title` service stores a new `panel_title`
and calls `async_register_vacuum_panel(..., replace=True)`, which removes the
existing panel first (`async_register_panel` raises `ValueError` on a duplicate
url) and re-registers it with the new `sidebar_title` — no restart needed.

**Fresh-install fallback.** When no vacuum is configured yet, no per-vacuum panel
is registered, so `async_setup_entry` registers a single fallback panel at url
`eufy-vacuum` with a hardcoded `sidebar_title="Vacuum Agent"` and an empty
`config={}` (the card detects the missing `vacuum_entity_id` and renders a setup
placeholder). This is the only place `"Vacuum Agent"` is hardcoded as a title.

Panels are removed in `async_unload_entry` via `frontend.async_remove_panel`
(the `panel_custom` module has no unregister API; the call is wrapped in
try/except so a future API change degrades gracefully).

The card JS file must be present at
`custom_components/eufy_vacuum/frontend/eufy-vacuum-command-center.js` before
the integration loads. It is not bundled with the Python package.
