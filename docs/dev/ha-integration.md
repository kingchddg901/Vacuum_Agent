# HA Integration Layer

Covers the Home Assistant-specific plumbing of `eufy_vacuum`: config entry
lifecycle, entity platforms, services, storage, event bus, and the background
watchers that run while the integration is loaded. Read this when you want to
add a new entity, service, or HA event.

---

## 1. Integration Entry Points

### `async_setup` (`__init__.py`)

Called once when the domain is first loaded. It:

- Creates the `eufy_vacuum/maps`, `eufy_vacuum/textures`, and
  `eufy_vacuum/frontend` directories under `hass.config.config_dir`.
- Registers three static HTTP paths via `hass.http.async_register_static_paths`:
  - `/eufy_vacuum/maps` → persisted map image files
  - `/eufy_vacuum/textures` → floor texture assets
  - `/eufy_vacuum/frontend` → the compiled card JS bundle

### `async_setup_entry` (`__init__.py`)

The main entry point. Called when the config entry is loaded. In order:

1. Instantiates `EufyVacuumManager` and calls `manager.async_initialize()` to
   load persisted storage.
2. Stores the manager at `hass.data[DOMAIN][DATA_RUNTIME]`.
3. Instantiates `LearningManager` and stores it at `hass.data[DOMAIN][DATA_LEARNING]`.
4. Instantiates `MappingManager` and `MappingTracker`; stores at
   `hass.data[DOMAIN]["mapping_manager"]` and
   `hass.data[DOMAIN]["mapping_tracker"]`. Registers position entities for
   vacuums whose capability map includes `robot_position_x`/`robot_position_y`.
5. Instantiates `ErrorTracker` and calls `error_tracker.start(known_vacuum_ids)`;
   stores at `hass.data[DOMAIN][DATA_ERROR_TRACKER]`.
6. Calls service registration functions: `async_register_services`,
   `async_register_learning_services`, `async_register_theme_services`,
   `async_register_mapping_services`.
7. Registers background listeners: `_register_lifecycle_listeners`,
   `_register_dock_event_listeners`, `_register_path_blocker_listeners`,
   `_register_pause_timeout_listener`.
8. Forwards setup to entity platforms: `button`, `switch`, `select`, `number`,
   `sensor`, `binary_sensor`.
9. Registers one sidebar panel per managed vacuum via
   `panel_custom.async_register_panel`. Panel URLs are stored at
   `hass.data[DOMAIN][f"_panels_{entry.entry_id}"]`.

### `async_unload_entry` (`__init__.py`)

1. Unloads all entity platforms.
2. Removes each registered sidebar panel.
3. Removes all background listeners.
4. Calls all service unregistration functions.
5. Calls `error_tracker.stop()`.
6. Clears all runtime keys from `hass.data[DOMAIN]`.

### `async_remove_entry` (`__init__.py`)

Creates a bare `Store` and calls `async_remove()` to wipe persisted data.

### `hass.data[DOMAIN]` keys

| Key constant | Type | Description |
|---|---|---|
| `DATA_RUNTIME` (`"runtime"`) | `EufyVacuumManager` | Core manager — all services and entities resolve through this key |
| `DATA_LEARNING` (`"learning"`) | `LearningManager` | Learning subsystem orchestrator |
| `DATA_ERROR_TRACKER` (`"error_tracker"`) | `ErrorTracker` | Active-run error latching and device error history |
| `"mapping_manager"` | `MappingManager` | Map image / segment processing |
| `"mapping_tracker"` | `MappingTracker` | Real-time robot position tracker |
| `f"_panels_{entry.entry_id}"` | `list[str]` | Panel URL paths registered for this entry (used for cleanup) |

---

## 2. Config Flow

`EufyVacuumConfigFlow` in `config_flow.py` is intentionally minimal:

- `CONF_TESTED_MODEL` — defaults to `"Eufy X10 Pro Omni"`. Display only.
- `CONF_NOTES` — optional free-text field.

`async_set_unique_id(DOMAIN)` + `_abort_if_unique_id_configured()` mean only
one config entry per HA instance is permitted.

**Options flow** (`EufyVacuumOptionsFlow`) exposes only `CONF_NOTES` for
editing after initial setup.

`config_entry.data` contains `{"tested_model": str, "notes": str}`. No
operational configuration (vacuum IDs, map IDs, room settings) lives in the
config entry — all of that is in the storage layer.

---

## 3. Entity Platforms

Eight platforms are registered: `button`, `switch`, `select`, `number`,
`sensor`, and `binary_sensor`. All platform `async_setup_entry` functions pull
the manager from `hass.data[DOMAIN]["runtime"]`.

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
| `get_floor_water_guidance(floor_type)` | Returns mop water guidance for a given floor type |

### button platform

- **Maintenance reset buttons** — one per supported maintenance component per
  vacuum (brush roll, filter, side brush, etc.), conditioned on capability
  detection.
- **Saved run profile buttons** — dynamic; created when a run profile is saved
  with `expose_as_button = True`. A manager callback
  (`_on_run_profiles_updated`) syncs these dynamically.

### switch platform

Per-room enable/disable toggles. One `EufyVacuumRoomEnableSwitch` per room per
map. State reflects `room_data["enabled"]`. Toggling calls
`_async_update_room({"enabled": value})`.

### select platform

Per-room profile selectors. One `EufyVacuumRoomProfileSelect` per room per
map. Options are available profile keys. Changing selection calls
`_async_update_room({"profile_name": value})`.

### number platform

Per-room clean pass count sliders. One `EufyVacuumRoomCleanPassesNumber` per
room per map. Range 1–3. Changing calls
`_async_update_room({"clean_passes": value})`.

All per-room entities (switch, select, number) inherit from
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

### Pattern

```python
# services/job_control.py
async def _handle_start_selected_rooms(hass, call):
    manager = _get_manager(hass)
    result = await manager.start_selected_rooms(...)
    await manager.async_save()
    return result

# services/__init__.py
def async_register_services(hass):
    hass.services.async_register(
        DOMAIN, SERVICE_START_SELECTED_ROOMS,
        lambda call: _handle_start_selected_rooms(hass, call),
        schema=START_SELECTED_ROOMS_SCHEMA,
        supports_response=True,
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
| Job control | `get_start_status`, `start_selected_rooms`, `start_run_profile`, `pause_active_job`, `resume_active_job`, `cancel_active_job`, `get_job_progress_snapshot`, `clear_active_job` |
| Dock actions | `wash_mop`, `dry_mop`, `stop_dry_mop`, `empty_dust`, `get_dock_action_status` |
| Snapshots | `get_lifecycle_state`, `get_dashboard_snapshot`, `get_upkeep_snapshot` |
| Room profiles | `get_room_profiles`, `save_user_room_profile`, `apply_room_profile`, `delete_room_profile` |
| Run profiles | `get_saved_run_profiles`, `save_run_profile`, `apply_run_profile`, `delete_run_profile` |
| Access graph | `get_room_access_editor`, `get_access_graph_health` |
| Capabilities | `get_vacuum_capabilities` |
| Errors | `acknowledge_error`, `get_recent_errors` |

### How to add a new service

1. Add the service name constant to `const.py`.
2. Pick the right `services/` sub-module for the domain, or create one.
3. Write `async _handle_<name>(hass, call) -> dict | None`. Call the manager.
   Call `async_save()` if state was mutated.
4. In `services/__init__.py`, register via `hass.services.async_register`.
5. Add the name to the unregister tuple in `async_unregister_services`.
6. If the service is called from the card, add a handler in the card's service
   call module.

---

## 6. Storage Layer

`core/storage.py` defines `EufyVacuumStorage`.

### Wrapping HA's Store

```python
self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
```

- `STORAGE_VERSION = 1`
- `STORAGE_KEY = "eufy_vacuum.storage"`

Written to `.storage/eufy_vacuum.storage`. **Never edit directly** — use HA UI
or integration services. Direct edits produce `.corrupt` backup files.

### Default empty structure (on first boot)

```python
{
    "vacuums": {},
    "maps": {},
    "capabilities": {},
    "active_jobs": {},
    "profiles": {},
    "run_profiles": {},
    "room_history": {},
    "room_rule_status": {},
    "setup_progress": {},
    "error_tracker": {},
    "theme": {"library": {}, "default_theme_id": None, "vacuums": {}},
    "maintenance": {},
    "dock_events": {},
    "onboarding": {},
    "discovery": {},
}
```

See `data-model.md` for the complete shape of each key.

### What is stored vs runtime-only

**Stored in `.storage`:** all keys above.

**Runtime-only (in `hass.data[DOMAIN]` or in-memory on the manager):**
- Manager object, LearningManager, ErrorTracker, MappingManager, MappingTracker
- Background listener unsub handles
- Registered panel URL lists
- `manager.runtime` — `VacuumRuntimeState` dict rebuilt from HA state on restart

---

## 7. Event System

The integration fires seven events on `hass.bus`. All type strings are
constants in `const.py`.

| Event constant | String value | Fired from | Key payload fields |
|---|---|---|---|
| `EVENT_ROOM_STARTED` | `eufy_vacuum_room_started` | `jobs/active_job.py` — job start and timing rollover | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `started_at`, `source` |
| `EVENT_ROOM_FINISHED` | `eufy_vacuum_room_finished` | `jobs/active_job.py` — timing rollover or bounds exit | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_at`, `source`, `actual_duration_minutes`, `confidence`, `completed_room_ids` |
| `EVENT_JOB_FINISHED` | `eufy_vacuum_job_finished` | `__init__.py`, `services/job_control.py`, `learning/services.py` | `vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail`, `used_for_learning`, `finalized_at`, `room_count`, `job_path` |
| `EVENT_PATH_BLOCKED` | `eufy_vacuum_path_blocked` | `__init__.py` path blocker listener | `vacuum_entity_id`, `map_id`, `trigger_entity_id`, `trigger_entity_state`, `affected_remaining_room_ids`, `path_block_action`, `action_taken` |
| `EVENT_STALL_DETECTED` | `eufy_vacuum_stall_detected` | `core/manager.py` inside `get_job_progress_snapshot` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` |
| `EVENT_RUN_INCOMPLETE` | `eufy_vacuum_run_incomplete` | `learning/services.py` after finalization | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids`, `missed_rooms` |
| `EVENT_JOB_PROGRESS_TICK` | `eufy_vacuum_job_progress_tick` | `jobs/job_monitor.py` periodic tick | `vacuum_entity_id`, `map_id` — lightweight polling signal for automations |

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

`__init__.py` contains a state-change watcher that automatically finalizes a
cleaning job when HA sensor states indicate the job is done.

### Watched entities

`_get_lifecycle_watch_entities(vacuum_entity_id)` returns:
- `vacuum.{object_id}`
- `sensor.{object_id}_task_status`
- `sensor.{object_id}_dock_status`
- `sensor.{object_id}_active_cleaning_target`
- `sensor.{object_id}_active_map`

### `has_observed_active_lifecycle` guard

The job is not eligible for auto-finalization until the manager has reported at
least one `"active_job_running"` or `"mid_job_service"` lifecycle state. This
prevents a stale pre-run dock state (e.g. `dock_drying`) from triggering
finalization before cleaning started.

### Finalization condition

All three must be simultaneously true:
1. `task_status == "completed"`
2. `active_cleaning_target` in `{"", "unknown", "unavailable", "none", "null"}`
3. `has_observed_active_lifecycle == True` on the active job record

`vacuum.state == "docked"` is intentionally not required — requiring it stranded
active job records when the vacuum was still returning.

### What happens on finalization

1. `manager.finalize_learning_for_active_job(...)`.
2. `manager.mark_active_job_finalized(...)`.
3. Fires `EVENT_JOB_FINISHED`.
4. For mop jobs: `_register_post_job_water_amendment(...)` registers a
   temporary dock status watcher to capture post-job mop wash water consumption
   and patch the job file after drying starts (or after a 180 s timeout).
5. `manager.async_save()`.

### Pause timeout watchdog

`_register_pause_timeout_listener` sets up a 1-minute
`async_track_time_interval`. On each tick it calls
`manager.get_paused_job_timeout_report(...)` for each active map. If a timeout
has been exceeded, it calls `manager.async_cancel_active_job(...)` and fires
`EVENT_JOB_FINISHED`.

---

## 9. Dock Event Listeners

`_register_dock_event_listeners` watches `sensor.{object_id}_dock_status`.

```python
_DOCK_EVENT_TRIGGERS = {
    "last_mop_wash":   {"washing", "washing mop"},
    "last_dust_empty": {"emptying dust", "emptying dust bin", "dust emptying"},
    "last_dry_start":  {"drying", "drying mop", "drying pads", "mop drying"},
}
```

When `dock_status` transitions to any trigger value:
`manager.record_dock_event(vacuum_entity_id, event_type, dry_duration)` is
called and the manager is saved. For `last_dry_start`, the current value of
`select.{object_id}_dry_duration` is captured.

Records are exposed through `EufyVacuumDockEventSensor`.

---

## 10. Repairs

`repairs.py` defines `EufyVacuumSetupRedirectFlow`. Any repair issue registered
against the `eufy_vacuum` domain opens this flow when the user clicks "Fix". It
presents a confirmation step and dismisses the issue. The description text
directs the user to the sidebar panel.

Currently raised by the setup workflow when state is inconsistent (vacuum not
found, map not imported). The repair flow does not fix programmatically — it is
a redirect.

---

## 11. Frontend Panel

The integration registers a custom sidebar panel per managed vacuum.

```python
await panel_custom.async_register_panel(
    hass,
    frontend_url_path=f"eufy-vacuum-{object_id}",
    webcomponent_name="eufy-vacuum-command-center",
    js_url=_frontend_url.panel_js_url(),   # "/eufy_vacuum/frontend/...js?v=<mtime>"
    sidebar_title="Eufy Vacuum",
    sidebar_icon="mdi:robot-vacuum",
    config={"vacuum_entity_id": vacuum_entity_id},
    require_admin=False,
    embed_iframe=False,
)
```

The `?v=<mtime>` fingerprint is computed from the bundle file's mtime — a fresh
deploy busts the HA service-worker cache automatically without a manual version
bump. The `config` dict is injected into the panel web component as a property.

Panels are removed in `async_unload_entry` via `frontend.async_remove_panel`
(the `panel_custom` module has no unregister API; the call is wrapped in
try/except so a future API change degrades gracefully).

The card JS file must be present at
`custom_components/eufy_vacuum/frontend/eufy-vacuum-command-center.js` before
the integration loads. It is not bundled with the Python package.
