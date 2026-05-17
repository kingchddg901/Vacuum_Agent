# HA Integration Layer

This document covers the Home Assistant-specific plumbing of `eufy_vacuum`: config entry lifecycle, entity platforms, services, storage, event bus, and the background watchers that run while the integration is loaded. Read this when you want to add a new entity, service, or HA event.

---

## 1. Integration Entry Points

### `async_setup` (`__init__.py`)

Called once when the domain is first loaded — before any config entry exists. It:

- Creates the `eufy_vacuum/maps`, `eufy_vacuum/textures`, and `eufy_vacuum/frontend` directories under `hass.config.config_dir`.
- Registers three static HTTP paths via `hass.http.async_register_static_paths`:
  - `/eufy_vacuum/maps` → persisted map image files
  - `/eufy_vacuum/textures` → floor texture assets
  - `/eufy_vacuum/frontend` → the compiled card JS bundle

### `async_setup_entry` (`__init__.py`)

The main entry point. Called when the config entry is loaded (on HA start or after re-enable). In order, it:

1. Instantiates `EufyVacuumManager` and calls `manager.async_initialize()` to load persisted storage.
2. Stores the manager at `hass.data[DOMAIN][DATA_RUNTIME]`.
3. Instantiates `LearningManager` and stores it at `hass.data[DOMAIN][DATA_LEARNING]`.
4. Instantiates `MappingManager` and `MappingTracker`, stored at `hass.data[DOMAIN]["mapping_manager"]` and `hass.data[DOMAIN]["mapping_tracker"]`. Registers vacuum position entities with the tracker for any vacuum whose capability map includes `robot_position_x`/`robot_position_y`.
5. Calls the four service registration functions: `async_register_services`, `async_register_learning_services`, `async_register_theme_services`, `async_register_mapping_services`.
6. Registers four background listeners: `_register_lifecycle_listeners`, `_register_dock_event_listeners`, `_register_path_blocker_listeners`, `_register_pause_timeout_listener`.
7. Forwards setup to the five entity platforms: `button`, `switch`, `select`, `number`, `sensor`.
8. Registers one sidebar panel per managed vacuum via `panel_custom.async_register_panel`. The panel URL path is `eufy-vacuum-{object_id}`, the webcomponent name is `eufy-vacuum-command-center`, and the JS URL comes from `_frontend_url.panel_js_url()` — `/eufy_vacuum/frontend/eufy-vacuum-command-center.js?v=<bundle_mtime>`. The mtime-based query string is recomputed on every panel registration so a fresh bundle deploy busts the HA service-worker cache without a manual version bump. Panel URLs for the current entry are stored at `hass.data[DOMAIN][f"_panels_{entry.entry_id}"]`.

### `async_unload_entry` (`__init__.py`)

Called when the entry is being unloaded. In order, it:

1. Unloads all entity platforms.
2. Removes each registered sidebar panel via `frontend.async_remove_panel` (the `panel_custom` module doesn't expose an unregister API; the panel lives in HA's `frontend` component, which is where the remove helper is defined).
3. Removes all four background listeners.
4. Calls all four service unregistration functions.
5. Unregisters the mapping tracker and clears all runtime keys from `hass.data[DOMAIN]`.

### `async_remove_entry` (`__init__.py`)

Called when the entry is permanently deleted. Creates a bare `Store` instance for the integration's storage key and calls `async_remove()` to wipe persisted data.

### `hass.data` keys

| Key | Type | Description |
|---|---|---|
| `DATA_RUNTIME` (`"runtime"`) | `EufyVacuumManager` | Core manager. All services and entities resolve the manager through this key. |
| `DATA_LEARNING` (`"learning"`) | `LearningManager` | Learning subsystem manager. |
| `"mapping_manager"` | `MappingManager` | Map image/segment processing. |
| `"mapping_tracker"` | `MappingTracker` | Real-time robot position tracker. |
| `f"_panels_{entry.entry_id}"` | `list[str]` | Panel URL paths registered for this entry (used for cleanup). |

---

## 2. Config Flow

`EufyVacuumConfigFlow` in `config_flow.py` is intentionally minimal. It collects:

- `CONF_TESTED_MODEL` (`"tested_model"`) — defaults to `"Eufy X10 Pro Omni"`. Stored as a string for display only; not used for runtime capability detection.
- `CONF_NOTES` (`"notes"`) — optional free-text field. The default value instructs the user to open the sidebar panel to add their vacuum and import its map.

The flow calls `async_set_unique_id(DOMAIN)` and `_abort_if_unique_id_configured()`, which means only one config entry per HA instance is permitted.

On submit the entry is created with `title = DEFAULT_TITLE` (`"Eufy Vacuum Manager"`) and `data = user_input`.

**Options flow** (`EufyVacuumOptionsFlow`) exposes only the `CONF_NOTES` field for editing after initial setup. It reads the current value from `config_entry.options` first, falling back to `config_entry.data`.

`config_entry.data` contains `{"tested_model": str, "notes": str}`. No operational configuration (vacuum entity IDs, map IDs, room settings) lives in the config entry — all of that is in the storage layer.

---

## 3. Entity Platforms

Five platforms are registered: `button`, `switch`, `select`, `number`, and `sensor`. All platform `async_setup_entry` functions pull the manager from `hass.data[DOMAIN]["runtime"]`.

### Base pattern: `EufyVacuumRoomEntity`

`room_entities.py` defines `EufyVacuumRoomEntity(Entity)`, the base class for all per-room entities. It:

- Builds a stable `unique_id` using `make_room_unique_id(vacuum_entity_id, map_id, room_id, suffix)`.
- Builds a human-readable `name` using `make_room_entity_name(vacuum_entity_id, room_name, label)`.
- Attaches a `DeviceInfo` entry that groups all room entities under a device named `"{Vacuum Name} Rooms"` with `entry_type=DeviceEntryType.SERVICE`.
- Exposes a `manager` property that resolves the runtime manager at call time via `hass.data[DOMAIN]["runtime"]` — never cached.
- Provides `_get_room_data()` (reads from `manager.data["maps"][vacuum_entity_id][map_id]["rooms"][room_id]`) and `_async_update_room(updates)` (writes, persists, and notifies).
- Returns `available = False` if the room record no longer exists in storage (handles dynamic room removal).
- `extra_state_attributes` returns a standard attribute set: `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `slug`, `profile_name`, `floor_type`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping`, `carpet`, `order`, `enabled`, `is_dock_room`, `grants_access_to`, `rules`, and `integration`.

### entity_helpers.py utilities

| Function | Purpose |
|---|---|
| `build_entity_name(vacuum_entity_id, suffix)` | Derives a display name from the vacuum entity's object_id |
| `make_room_unique_id(...)` | Builds a stable `{vacuum_key}_{map_id}_{room_id}_{suffix}` unique ID |
| `make_room_entity_name(...)` | Builds a room entity name that stays unambiguous in multi-vacuum homes |
| `sort_room_items(rooms)` | Sorts room dict by `order` then `name` |
| `get_floor_type_label(floor_type)` | Maps a floor_type key to a human-readable label |
| `get_floor_water_guidance(floor_type)` | Returns mop water guidance for a given floor type |

### button platform

Exposes two entity kinds:

- **Maintenance reset buttons** — one per supported maintenance component (brush roll, filter, side brush, etc.) for each vacuum. Registered at startup and tied to capability detection (`sources.get(component)` must be non-`None`).
- **Saved run profile buttons** — dynamic; created when a run profile is saved with `expose_as_button = True`. A manager callback (`_on_run_profiles_updated`) syncs these dynamically, adding new ones and removing stale ones from the entity registry.

### switch platform

Exposes per-room enable/disable toggles. One `EufyVacuumRoomEnableSwitch` per room per map. State reflects `room_data["enabled"]`. Toggling calls `_async_update_room({"enabled": value})`.

### select platform

Exposes per-room profile selectors. One `EufyVacuumRoomProfileSelect` per room per map. Options are the available profile keys returned by `get_available_profiles(capabilities, stored_profiles)`. Changing selection calls `_async_update_room({"profile_name": value})`.

### number platform

Exposes per-room clean pass count sliders. One `EufyVacuumRoomCleanPassesNumber` per room per map. Range is 1–3. Changing the value calls `_async_update_room({"clean_passes": value})`.

### room_entities (shared base)

Switch, select, and number all inherit from `EufyVacuumRoomEntity`. Room add/remove is handled dynamically via manager callbacks registered in each platform's `async_setup_entry`. Stale entities are removed from both the platform and the entity registry.

---

## 4. Sensor Architecture

`sensor.py` sets up all sensor entities in `async_setup_entry`. It iterates `manager.data["maps"]` to enumerate vacuums and their maps.

### Per-vacuum sensors (static, created at startup)

One set of these is created per vacuum at startup and never torn down while the entry is loaded.

| Class | Entity ID pattern | `native_value` | Key attributes |
|---|---|---|---|
| `EufyVacuumProfileSensor` | `sensor.<object_id>_available_profiles` | String-cast count of available profiles (e.g. `"4"`) | `profile_count` (int), `profiles` (full dict), `profile_labels` (key→label dict), `supports_mop_features` (bool), `supports_water_control` (bool), `capability_filtered` (always `True`) |
| `EufyVacuumMaintenanceRemainingSensor` | `sensor.<object_id>_<component>_maintenance_remaining` | Remaining hours as a float (`native_unit_of_measurement = "h"`, `device_class = "duration"`, `state_class = "measurement"`) | `component` (str), `used_since_reset_hours` (float), `interval_hours` (float), `current_usage_hours` (float), `reset_at_usage_hours` (float), `reset_at` (ISO timestamp or `None`), `source_entity` (entity ID), `source_available` (bool) |
| `EufyVacuumDockEventSensor` | `sensor.<object_id>_dock_events` | ISO timestamp of the most recent dock event across all event types (`None` if no events recorded) | `last_mop_wash` (ISO str or `None`), `last_dust_empty` (ISO str or `None`), `last_dry_start` (ISO str or `None`), `last_dry_duration` (str or `None`), `vacuum_entity_id` |
| `EufyVacuumThemeStateSensor` | `sensor.<object_id>_theme_state` | Active theme name string, or `"none"` if no theme is selected or the active ID is not in the library | `active_theme_id` (str or `None`), `draft_dirty` (bool), `editor_mode` (str), `working_draft` (dict with `tokens`, `colors`, `alpha`), `library_count` (int), `library_summary` (list of `{id, theme_id, name}`), `default_theme_id` (str or `None`), `vacuum_entity_id` |
| `EufyVacuumOnboardingSensor` | `sensor.<object_id>_onboarding_state` | Worst-case status across all maps: `"rooms_needed"` > `"floor_type_needed"` > `"complete"` | `all_complete` (bool), `vacuum_entity_id`, `maps` (list of per-map status dicts) |

`EufyVacuumMaintenanceRemainingSensor` is created once per maintenance component per vacuum, conditioned on capability detection (`maintenance_sources[component]` must be non-`None`). It reads usage hours live from the HA entity referenced by the capabilities map. The `<component>` token in its entity ID is the component key from `MAINTENANCE_COMPONENTS` (e.g. `filter`, `rolling_brush`, `side_brush`, `mopping_cloth`, `cleaning_tray`, `swivel_wheel`, `sensor`).

`EufyVacuumThemeStateSensor` sets `_attr_should_poll = False` and is updated exclusively via the theme update callback.

### Per-room sensors (dynamic)

One pair of these is created per room per map. They are added and removed dynamically as rooms are added or deleted.

| Class | Entity ID pattern | `native_value` | Key attributes |
|---|---|---|---|
| `EufyVacuumRoomCleaningHistorySensor` | `sensor.<object_id>_<map_id>_<room_id>_cleaning_history` | ISO timestamp of the last completed cleaning for this room (`None` if never cleaned) | `last_cleaned_at`, `last_vacuumed_at`, `last_mopped_at` (ISO strs or `None`), `hours_since_last_vacuum`, `hours_since_last_mop` (floats or `None`), `last_job_mode` (str or `None`), plus all base `EufyVacuumRoomEntity` attributes |
| `EufyVacuumRoomRuleStatusSensor` | `sensor.<object_id>_<map_id>_<room_id>_rule_status` | Last rule evaluation result string (e.g. `"selected"`, `"blocked"`, `"never"`) | `last_evaluated_at` (ISO str or `None`), `last_result`, `last_selected` (bool), `last_included` (bool), `last_block_reason` (str or `None`), `last_block_source` (str or `None`), `last_blocked_by_room_id` (int or `None`), `last_blocked_by_room_name` (str or `None`), `last_triggered_rule_ids` (list), `last_modifier_changes` (dict or `None`), `last_requires_confirmation` (bool), `last_preflight_reason` (str or `None`), `last_warning_codes` (list), `last_evaluation_scope` (str or `None`), plus all base `EufyVacuumRoomEntity` attributes |

Both inherit from `EufyVacuumRoomEntity` and set `_attr_should_poll = False`.

### How sensors subscribe to manager notifications

All sensor update paths funnel through `_request_entity_state_write(entity)`, a module-level helper that schedules `async_write_ha_state()` onto the HA event loop using `hass.loop.call_soon_threadsafe`. This is required because manager callbacks can fire from worker threads.

Four manager callback types are registered in `async_setup_entry`:

| Callback type | What triggers it | Effect |
|---|---|---|
| `register_room_update_callback` | Room config added, removed, or changed | `_sync_room_history_entities` and `_sync_room_rule_status_entities` — adds/removes room sensors dynamically |
| `register_room_history_update_callback` | Learning job finalized, room history updated | `_refresh_room_history_entities` — calls `_request_entity_state_write` for the affected vacuum/map |
| `register_room_rule_status_update_callback` | Rule evaluation completed | `_refresh_room_rule_status_entities` — same pattern |
| `register_theme_update_callback` | Theme saved, applied, or draft changed | `_refresh_theme_entities` — writes state on `EufyVacuumThemeStateSensor` |

All callbacks are unregistered on entry unload via `entry.async_on_unload`.

Room sensors also refresh on the `eufy_vacuum_job_finished` event (registered via `hass.bus.async_listen`) and on a 1-hour timer (`async_track_time_interval`).

---

## 5. Service Registration Pattern

All integration services are registered in `async_register_services(hass)` in `services.py`. The pattern is:

1. Define a module-level `_handle_*` async function that takes `(hass, call)` and calls through to the manager.
2. Inside `async_register_services`, define a thin closure that calls the handler with the captured `hass` reference.
3. Call `hass.services.async_register(DOMAIN, SERVICE_NAME, closure, schema=SCHEMA, supports_response=True/False)`.

Services that return data to the caller (read-only snapshots, capability queries, job state) are registered with `supports_response=True`. Services that only write state (`discover_rooms`, `build_queue`, `start_selected_rooms`, etc.) omit `supports_response` or pass `False`.

After mutation, handlers call `await _get_manager(hass).async_save()` to persist. Read-only handlers skip the save.

### Service groups

| Group | Examples | Notes |
|---|---|---|
| Setup (panel-driven) | `setup_get_status`, `setup_add_vacuum`, `setup_import_active_map`, `setup_get_map_rooms`, `setup_save_rooms`, `setup_delete_map` | Invoked by the frontend panel during onboarding. All return data. |
| Queue / payload | `discover_rooms`, `save_managed_rooms`, `build_queue`, `build_room_payload`, `get_queue_state`, `get_payload_state`, `clear_queue` | Core room selection plumbing. |
| Job control | `get_start_status`, `start_selected_rooms`, `start_run_profile`, `pause_active_job`, `resume_active_job`, `cancel_active_job`, `get_active_job`, `get_job_progress_snapshot`, `get_job_control_state`, `clear_active_job`, `get_pause_timeout_settings`, `set_pause_timeout_settings` | Active job lifecycle. |
| Dock actions | `wash_mop`, `dry_mop`, `stop_dry_mop`, `empty_dust`, `get_dock_action_status` | Gated dock commands. All `supports_response=True`. |
| Snapshots | `get_lifecycle_state`, `get_dashboard_snapshot`, `get_upkeep_snapshot` | Unified card data snapshots. |
| Maintenance | `reset_maintenance`, `set_dock_event_count` | Upkeep counter management. |
| Room profiles | `get_room_profiles`, `save_user_room_profile`, `overwrite_room_profile`, `save_room_profile_from_room`, `overwrite_room_profile_from_room`, `rename_room_profile`, `delete_room_profile`, `apply_room_profile` | Named cleaning profile CRUD. |
| Run profiles | `get_saved_run_profiles`, `save_run_profile`, `apply_run_profile`, `overwrite_run_profile`, `rename_run_profile`, `delete_run_profile` | Saved run configuration CRUD. |
| Room fields / access | `update_room_fields`, `get_room_access_editor`, `get_access_graph_health` | Per-room field edits and access graph tooling. |
| Capabilities | `get_vacuum_capabilities` | Capability detection and refresh. |

### `async_unregister_services`

Called in `async_unload_entry`. Iterates over every registered service name and calls `hass.services.async_remove(DOMAIN, service_name)`. Learning, theme, and mapping services are unregistered by their own `async_unregister_*` functions.

### How to add a new service

1. Add the service name constant to `const.py` (e.g. `SERVICE_MY_NEW_SERVICE = "my_new_service"`).
2. Add the constant to the imports in `services.py`.
3. Define a voluptuous schema constant (e.g. `MY_NEW_SERVICE_SCHEMA`).
4. Write a `_handle_my_new_service(hass, call) -> dict | None` function. Call the manager. Call `async_save()` if state was mutated.
5. Inside `async_register_services`, define the closure and call `hass.services.async_register(DOMAIN, SERVICE_MY_NEW_SERVICE, closure, schema=MY_NEW_SERVICE_SCHEMA, supports_response=True)`.
6. Add the service name to the tuple in `async_unregister_services`.
7. If the service is called from the frontend card, add a corresponding handler in the card's service call module.

---

## 6. Storage Layer

`core/storage.py` defines `EufyVacuumStorage`.

### Wrapping HA's Store

```python
self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
```

- `STORAGE_VERSION = 1`
- `STORAGE_KEY = "eufy_vacuum.storage"`

HA's `Store` writes to `.storage/eufy_vacuum.storage` in the HA config directory. The `STORAGE_VERSION` is a schema version number — HA uses it for migration hooks (not yet implemented). **Do not edit the `.storage` file directly.** Use HA's UI or integration services.

### `async_load() -> dict`

Calls `self._store.async_load()`. Returns the stored dict if it exists, or the default empty structure:

```python
{
    "vacuums": {},
    "maps": {},
    "theme": {
        "library": {},
        "default_theme_id": None,
        "vacuums": {},
    },
    "analytics": {},
    "maintenance": {},
    "dock_events": {},
    "icons": {},
    "onboarding": {},
}
```

### `async_save(data: dict) -> None`

Calls `self._store.async_save(data)`. The manager calls this after any mutation. There is no debouncing at the storage layer — the manager has a `_async_save_logged()` helper for fire-and-forget saves.

### What is stored vs runtime-only

**Stored in `.storage`:**

| Key | Contents |
|---|---|
| `vacuums` | Vacuum registration metadata (capabilities snapshot, model info) |
| `maps` | Map definitions, per-map room configs, summaries, queue state, active job, run profiles |
| `theme` | Theme library, per-vacuum active theme, working drafts |
| `analytics` | Learning job records and derived stats |
| `maintenance` | Per-component reset snapshots and configured intervals |
| `dock_events` | Timestamps and counts for mop wash, dust empty, dry start events |
| `icons` | Custom room icon overrides |
| `onboarding` | Per-vacuum/map onboarding completion flags |

**Runtime-only (in `hass.data[DOMAIN]` or in-memory on the manager):**

- The manager object itself (`DATA_RUNTIME`)
- Learning manager (`DATA_LEARNING`)
- Mapping tracker state and active job tracking
- Background listener unsub handles
- Registered panel URL lists

---

## 7. Event System

The integration fires six events on `hass.bus`. All event type strings are constants in `const.py`.

| Event | Constant | Fired from | Payload |
|---|---|---|---|
| `eufy_vacuum_job_finished` | `EVENT_JOB_FINISHED` | `__init__.py` (auto-finalization and pause timeout), `services.py` (cancel_active_job), `learning/services.py` (finalize_learning_job) | `vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail`, `used_for_learning`, `finalized_at`, `room_count`, `job_path` |
| `eufy_vacuum_room_started` | `EVENT_ROOM_STARTED` | `core/manager.py` — on job start and on timing-based room rollover | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `started_at`, `source` |
| `eufy_vacuum_room_finished` | `EVENT_ROOM_FINISHED` | `core/manager.py` — on timing-based room rollover when the current room completes | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_at`, `source`, `actual_duration_minutes`, `confidence`, `completed_room_ids` |
| `eufy_vacuum_path_blocked` | `EVENT_PATH_BLOCKED` | `__init__.py` — path blocker listener when a blocker entity changes state during an active job | `vacuum_entity_id`, `map_id`, `trigger_entity_id`, `trigger_entity_state`, `affected_remaining_room_ids`, `path_block_action`, `action_taken`, (optional) `action_result` |
| `eufy_vacuum_stall_detected` | `EVENT_STALL_DETECTED` | `core/manager.py` — inside `get_job_progress_snapshot()` when elapsed time >= 2× timing threshold with bounds gate active | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` |
| `eufy_vacuum_run_incomplete` | `EVENT_RUN_INCOMPLETE` | `learning/services.py` — after job finalization when at least one queued room was not cleaned | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids` (list of int), `missed_rooms` (list of `{room_id, name}`) |

### Payload construction helpers

`__init__.py` defines `_job_finished_event_data(*, vacuum_entity_id, map_id, finalize_result)` to build the `eufy_vacuum_job_finished` payload. `services.py` defines a parallel `_job_finished_event_payload(...)` with slightly different argument structure. Both produce the same final dict shape.

### Subscribing in automations

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_job_finished
    event_data:
      vacuum_entity_id: vacuum.alfred
```

All events carry `vacuum_entity_id` in their payload, so automations can filter by specific device.

---

## 8. Auto-Finalization

`__init__.py` contains a state-change watcher that automatically finalizes a cleaning job when HA sensor states indicate the job is done, without requiring an explicit finalize call from the frontend. Auto-finalization is one of several end paths for an active job — see [job-lifecycle.md](job-lifecycle.md) for the full set.

### Watched entities

For each vacuum, `_get_lifecycle_watch_entities(vacuum_entity_id)` returns five entity IDs:

- `vacuum.{object_id}` — vacuum state (e.g. `docked`)
- `sensor.{object_id}_task_status`
- `sensor.{object_id}_dock_status`
- `sensor.{object_id}_active_cleaning_target`
- `sensor.{object_id}_active_map`

`async_track_state_change_event` watches all of these. One callback handles all vacuums.

### `_ACTIVE_LIFECYCLE_STATES`

```python
_ACTIVE_LIFECYCLE_STATES = {
    "active_job_running",
    "mid_job_service",
}
```

The job is not eligible for auto-finalization until the manager has reported at least one of these lifecycle states for the active job. This prevents stale pre-run dock states (e.g. `dock_drying`) from triggering finalization before the vacuum has actually started moving. The flag is written to the active job record via `manager.record_active_lifecycle_observed(...)`.

### Finalization condition

A job is finalized when all three of these are simultaneously true:

1. `task_status == "completed"`
2. `active_cleaning_target` is in `{"", "unknown", "unavailable", "none", "null"}`
3. `has_observed_active_lifecycle` is `True` on the active job record

`vacuum.state == "docked"` is intentionally not required — requiring it was stranding active job records when the vacuum was still returning to dock.

### What happens on finalization

1. `manager.finalize_learning_for_active_job(...)` is called.
2. `manager.mark_active_job_finalized(...)` clears the active job record (prevents stranded records even if finalization fails).
3. `eufy_vacuum_job_finished` is fired with the result payload.
4. For mop jobs: `_register_post_job_water_amendment(...)` registers a temporary dock status watcher to capture post-job mop wash water consumption and patch the job file once drying starts (or after a 180-second timeout).
5. `manager.async_save()` persists all changes.

### Pause timeout watchdog

`_register_pause_timeout_listener` sets up a `async_track_time_interval` callback that fires every minute. It calls `manager.get_paused_job_timeout_report(...)` for each active map. If the report indicates a timeout has been exceeded, it calls `manager.async_cancel_active_job(...)` and fires `eufy_vacuum_job_finished`.

---

## 9. Dock Event Listeners

`_register_dock_event_listeners` watches each vacuum's `sensor.{object_id}_dock_status` entity.

### `_DOCK_EVENT_TRIGGERS`

```python
_DOCK_EVENT_TRIGGERS = {
    "last_mop_wash":   {"washing", "washing mop"},
    "last_dust_empty": {"emptying dust", "emptying dust bin", "dust emptying"},
    "last_dry_start":  {"drying", "drying mop", "drying pads", "mop drying"},
}
```

When `dock_status` transitions to any value in a trigger set, `manager.record_dock_event(vacuum_entity_id, event_type, dry_duration)` is called and the manager is saved. For `last_dry_start` events, the current value of `select.{object_id}_dry_duration` is captured and stored as `dry_duration`.

These records are exposed through `EufyVacuumDockEventSensor`.

### Debounce / deduplication

There is no timer-based debounce on dock events. The listener fires on every state transition and records immediately. Deduplication relies on the dock_status not oscillating: it only records when the state is in the trigger set, and a transition from one non-trigger state to another does not fire. For mop wash counting in the post-job water amendment watcher, a minimum 60-second interval between wash counts is enforced via `_MIN_WASH_INTERVAL_SECONDS`.

---

## 10. Repairs

`repairs.py` defines `async_create_fix_flow` and `EufyVacuumSetupRedirectFlow`.

Any repair issue registered against the `eufy_vacuum` domain will open this flow when the user clicks "Fix" in the HA Repairs UI. The flow immediately presents a confirmation step and, when confirmed, dismisses the issue. The description text (defined in `strings.json`) directs the user to the sidebar panel.

Currently, repair issues are raised by the setup workflow when state is inconsistent (vacuum not found, map not imported). The repair flow itself does not fix the issue programmatically; it is a redirect to the panel.

---

## 11. Frontend Panel

The integration registers a custom sidebar panel per managed vacuum. This is a panel resource, not a Lovelace resource — it appears as a sidebar entry, not a card in a dashboard.

Registration happens in `async_setup_entry` using `panel_custom.async_register_panel`:

```python
await panel_custom.async_register_panel(
    hass,
    frontend_url_path=f"eufy-vacuum-{object_id}",   # e.g. "eufy-vacuum-alfred"
    webcomponent_name="eufy-vacuum-command-center",
    js_url="/eufy_vacuum/frontend/eufy-vacuum-command-center.js?v=3",
    sidebar_title="Eufy Vacuum",
    sidebar_icon="mdi:robot-vacuum",
    config={"vacuum_entity_id": vacuum_entity_id},
    require_admin=False,
    embed_iframe=False,
)
```

The JS URL points to the static path registered by `async_setup`. The `?v=` query parameter is now computed automatically via `_frontend_url.panel_js_url()`, which fingerprints the bundle's mtime — every time `dist/eufy-vacuum-command-center.js` is replaced, the panel re-registration on the next reload picks up the new mtime and the URL changes, busting the HA service-worker cache without manual intervention. The `config` dict is injected into the panel's web component as a property and is how the card learns which vacuum it is managing.

Panels are removed in `async_unload_entry` via `frontend.async_remove_panel` (`panel_custom` itself has no unregister API; the panel lives in HA's `frontend` component). The call is wrapped in `try/except` so a missing/renamed-in-future helper degrades to a debug log rather than blocking unload.

The card JS file at `/eufy_vacuum/frontend/eufy-vacuum-command-center.js` must be present in `custom_components/eufy_vacuum/frontend/` before the integration loads. It is not bundled with the Python package; it must be placed there as part of the installation or build process.
