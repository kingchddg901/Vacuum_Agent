# core/manager.py — Central Orchestrator

`EufyVacuumManager` is the single integration-wide runtime object. Every service call, every sensor read, and every card data request passes through it. This document explains why it is designed as a singleton, what it owns, and how to extend it.

For the surrounding architecture, see [architecture-overview.md](architecture-overview.md). For the per-vacuum brand config the manager reads at every call site, see [adapter-config-reference.md](adapter-config-reference.md). For end-to-end job flow, see [job-lifecycle.md](job-lifecycle.md).

---

## 1. Role

### Why a single manager?

The integration manages multiple vacuums, each with multiple maps, each of which has rooms, a live job slot, a queue, a payload, history, rules, and theme state. All of this data is interdependent:

- Starting a job requires reading the queue _and_ the payload _and_ running preflight rule evaluation _and_ writing an active-job record — all atomically from one call site.
- Lifecycle callbacks from HA state changes (dock event, room finished, job cancelled) need to mutate storage and fire HA bus events from the same object that owns the storage.
- The learning system, the mapping tracker, and the room-history cache all need a central coordinator that won't create race conditions by holding separate copies of state.

A per-entity or per-vacuum design would fragment ownership and require complex synchronization. A single manager eliminates that problem: there is one writer, one in-memory dict, and one save call.

### Exclusive ownership

The manager is the only writer to:

- `self.data` — the in-memory dict that mirrors the persistent `.storage` file
- `self.runtime` — a `dict[str, VacuumRuntimeState]` that is pure in-process state (never persisted)
- All callback lists (`_room_update_callbacks`, `_theme_update_callbacks`, etc.)
- Active-job slots in `self.data["active_jobs"]`

No code outside `manager.py` writes directly to `self.data`. Helper modules (`queue_engine`, `room_manager`, `map_manager`, etc.) are stateless functions that receive data and return results; the manager decides whether to persist the result.

---

## 2. Initialisation Sequence

`async_initialize()` is called once during integration setup. The sequence is:

1. **Load storage** — `await self.storage.async_load()` pulls the `.storage` file from HA's `Store` helper. Returns a default-empty dict if the file does not exist.

2. **Seed top-level keys** — `setdefault` calls ensure `vacuums`, `capabilities`, `room_history`, `room_rule_status`, and `theme` (with sub-keys `library`, `default_theme_id`, `vacuums`) are always present, even on first run.

3. **Seed preloaded theme library** — `_ensure_preloaded_theme_library()` inserts all built-in themes (Core Slate, Forest Night, etc.) into `data["theme"]["library"]` exactly once. Subsequent reads go directly to the dict without iterating `PRELOADED_THEME_SPECS`.

4. **Backfill new room fields** — Iterates every room in every map bucket and calls `setdefault` on fields added after the initial release: `path_type`, `is_dock_room`, `is_transition`, `grants_access_to`, `rules`, `floor_type`, `profile_name`. Also compacts the legacy two-field `floor_type="carpet"` + `carpet_type` into the canonical single value `carpet_low_pile` / `carpet_high_pile`, and drops the derived `carpet` field.

5. **Flatten legacy discovery shape** — Discovery payloads that stored rooms directly under a vacuum key (old flat shape with top-level `"rooms"` key) are migrated to the current per-map-id dict shape.

6. **Initialise callback lists** — Five callback lists are created as empty lists: `_room_update_callbacks`, `_run_profile_update_callbacks`, `_room_history_update_callbacks`, `_room_rule_status_update_callbacks`, `_theme_update_callbacks`. Also initialises `_room_history_cache_loading` (a set tracking in-flight async cache loads).

After `async_initialize()` the manager is ready to service any call. There is no further migration path — backfills happen inline on every startup on affected records only, so old installs always come up clean.

---

## 3. Schema Migration

### Versioning system

Storage version is fixed at `STORAGE_VERSION = 1` in `storage.py`. HA's `Store` helper handles the version header in the `.storage` file. Because the integration uses additive migration (backfilling defaults rather than destructive transforms), the version has not needed to increment.

Backward-compatible changes (adding a new field with a safe default) are handled by adding a `setdefault` call inside the `async_initialize` room-backfill loop. Destructive changes that cannot be expressed as additive migrations would require incrementing `STORAGE_VERSION` and providing an explicit migration callable to `Store`.

### What the current backfill changed

The `async_initialize` backfill loop normalises the following fields on every room that is missing them:

| Field | Default | Notes |
|---|---|---|
| `path_type` | `None` | Derived from room profile at read time; stored as cache |
| `is_dock_room` | `False` | Required for access-graph logic |
| `is_transition` | `False` | Marks hallway / passthrough rooms |
| `grants_access_to` | `[]` | Access-graph edge list |
| `rules` | `[]` | Per-room automation rules |
| `floor_type` | `"hardwood"` | Canonical surface type |
| `profile_name` | `"vacuum_quick"` | Active clean-settings preset |

Additionally: rooms with `floor_type="carpet"` and a legacy `carpet_type` sub-field are compacted into `carpet_low_pile` or `carpet_high_pile`, and the old separate `carpet` boolean is removed entirely.

### Adding a new schema version

If you add a field to the room structure that cannot default to `None` or `False` safely, add a `setdefault` call inside the backfill loop in `async_initialize`:

```python
# In async_initialize, inside the _room loop:
_room.setdefault("my_new_field", "default_value")
```

If the migration is destructive (rename a key, change a type), increment `STORAGE_VERSION` in `storage.py` and add a migration function to `EufyVacuumStorage.async_load` using `Store`'s migration API.

---

## 4. State Structure

### `self.data` — persisted in-memory dict

All keys below are top-level keys of `self.data`.

| Key | Type | Description |
|---|---|---|
| `vacuums` | `dict[vacuum_entity_id, record]` | Per-vacuum identity records. Each record holds `vacuum_entity_id`, `detected_model`, `is_managed`, and `pause_timeout_minutes_default`. |
| `maps` | `dict[vacuum_entity_id, dict[map_id_str, map_bucket]]` | Core room configuration store. See map bucket structure below. |
| `capabilities` | `dict[vacuum_entity_id, capability_snapshot]` | Cached result of `detect_capabilities()`. Keys include `supports_rooms`, `supports_mop_features`, `supports_active_map`, `supports_robot_position`, `maintenance_sources`, and `entities`. |
| `discovery` | `dict[vacuum_entity_id, dict[map_id_str, payload]]` | Raw room discovery payloads. Written by `discover_rooms()`, consumed by `save_managed_rooms()`. Never shown directly to the card. |
| `active_jobs` | `dict[vacuum_entity_id, dict[map_id_str, active_job]]` | Live job tracking. Each slot is reset (not deleted) on job completion or map removal. |
| `queue` | `dict[vacuum_entity_id, dict[map_id_str, queue_state]]` | Output of `build_queue_from_managed_rooms()`. Rebuilt whenever rooms are updated. |
| `payloads` | `dict[vacuum_entity_id, dict[map_id_str, payload_state]]` | Output of `build_room_clean_payload()`. The `payload` sub-object's field names and value vocabulary are adapter-driven via the [`dispatch` config block](adapter-config-reference.md#13-dispatch--how-to-send-a-clean-job); the Eufy default produces the `room_clean` command params. |
| `profiles` | `{"room_profiles": dict[profile_name, profile]}` | Custom room clean-settings presets. Built-in presets are never stored here. |
| `run_profiles` | `dict[vacuum_entity_id, dict[map_id_str, dict[profile_id, profile]]]` | Saved multi-room run configurations. |
| `theme` | `{"library": dict, "default_theme_id": str\|None, "vacuums": dict}` | Full theme system state. Preloaded themes live in `library`. Per-vacuum active theme and working draft live in `vacuums`. |
| `room_history` | `dict[vacuum_entity_id, dict[map_id_str, dict[room_id_str, history_entry]]]` | Per-room last-cleaned timestamps. **Runtime cache** — rebuilt from learning history files on demand, not read from `.storage`. |
| `room_rule_status` | `dict[vacuum_entity_id, dict[map_id_str, dict[room_id_str, status_entry]]]` | Last preflight rule evaluation result per room. Written by `_update_room_rule_status_snapshot()`. |
| `onboarding` | `dict[vacuum_entity_id, dict[map_id_str, ob_state]]` | Floor-type confirmation and discovery state per map. |
| `maintenance` | `dict[vacuum_entity_id, dict[component, reset_record]]` | Manual maintenance reset snapshots. |
| `dock_events` | `dict[vacuum_entity_id, dict[event_type, timestamp_or_count]]` | Dock lifecycle event timestamps and debounced counters. |
| `icons` | `dict[category, dict[slot, value]]` | Custom icon selections. Keyed `[vacuum_entity_id][map_id_str]` for map-level icons. |
| `analytics` | `dict` | Reserved. Currently empty on fresh installs. |

### Map bucket structure (`data["maps"][vac_id][map_id_str]`)

| Key | Type | Description |
|---|---|---|
| `rooms` | `dict[room_id_str, room_config]` | Managed rooms keyed by string room ID. |
| `summary` | `dict` | Output of `build_room_selection_summary()`. Counts of enabled/total rooms. |
| `metadata` | `dict` | Optional map-level metadata. |

### Room config structure (one entry in `rooms`)

| Field | Type | Description |
|---|---|---|
| `room_id` | `int` | Upstream integer room ID. Always an integer in storage. |
| `map_id` | `str` | Map ID this room belongs to. Always a string. |
| `name` | `str` | Display name. |
| `slug` | `str` | URL-safe identifier derived from name. |
| `order` | `int` | Sort order within the queue. |
| `enabled` | `bool` | Whether this room is in the current run selection. |
| `floor_type` | `str` | Canonical surface type: `hardwood`, `tile`, `carpet_low_pile`, `carpet_high_pile`. |
| `profile_name` | `str` | Active clean-settings preset name, or `"custom"`. |
| `clean_mode` | `str` | `vacuum`, `mop`, or `vacuum_mop`. |
| `fan_speed` | `str` | Fan speed string (e.g. `"Max"`, `"Boost_IQ"`). |
| `water_level` | `str` | Water level string (e.g. `"Off"`, `"Low"`, `"Medium"`, `"High"`). |
| `clean_intensity` | `str` | Intensity string (e.g. `"Standard"`, `"Turbo"`). |
| `clean_passes` | `int` | Number of passes. Minimum 1. |
| `edge_mopping` | `bool` | Whether edge mopping is active. |
| `path_type` | `str\|None` | Derived from the resolved profile; cached here to avoid re-resolving on every read. |
| `is_dock_room` | `bool` | Whether this room contains the charging dock. |
| `is_transition` | `bool` | Whether this is a passthrough/hallway room. |
| `grants_access_to` | `list[int]` | Access-graph edges — room IDs this room leads to. |
| `rules` | `list[rule_dict]` | Per-room automation rules (blocker or modifier). |

### Active job structure (one slot in `data["active_jobs"]`)

Key fields:

| Field | Description |
|---|---|
| `status` | `"idle"`, `"started"`, `"paused"`, `"completed"`, `"cancelled"`, `"failed"`, `"interrupted"` |
| `job_id` | Stable string ID generated at start (`job_YYYY-MM-DDTHH-MM-SS`). |
| `started_at` | ISO-8601 UTC timestamp. |
| `battery_start` | Battery percent at job start. |
| `queue_room_ids` | Ordered list of integer room IDs in the job. |
| `queue_rooms` | Richer list of room dicts from the queue state. |
| `resolved_rooms` | Full list of rooms with resolved clean settings (what was actually sent to the vacuum). |
| `payload` | The raw `room_clean` command params dict that was sent. |
| `completed_room_ids` | List of integer room IDs marked done during the job. |
| `completed_rooms` | List of completion detail dicts (room_id, completed_at, actual_duration_minutes, source). |
| `current_room_id` | Integer ID of the room being cleaned now (derived, kept up to date). |
| `current_room_started_at` | ISO timestamp when the current room started. |
| `current_room_paused_seconds` | Accumulated paused time within the current room. |
| `paused_at` | ISO timestamp if currently paused; `None` otherwise. |
| `paused_duration_seconds` | Total wall-clock seconds spent paused across the whole job. |
| `path_block_action` | Policy for mid-job blocker events: `"event_only"`, `"pause_and_event"`, `"cancel_and_event"`. |
| `pause_timeout_minutes` | Auto-cancel timeout for paused jobs (0 = disabled). |
| `observed_mid_job_recharge` | `True` if the vacuum went back to dock mid-job to recharge. |
| `observed_mop_wash_count` | Debounced count of dock mop-wash cycles during the job. |
| `observed_mop_wash_last_at` | ISO timestamp of the most recent observed wash. |
| `observed_mop_wash_cycles` | Per-cycle log: list of `{"observed_at": <iso ts>}` entries appended on each observed wash event (after the 60s debounce). Capped at 50 entries. Use this for cadence analysis vs. the rollup count. |
| `state_transitions` | Rolling last-12 state transition records for debugging. |
| `water_estimate` | Snapshot of water usage estimate taken at job start. The estimate's "is this a mopping room?" gate is `"mop" in clean_mode` only — water_level is a knob within mop mode, not a gate on it. The dock washes the mop pad after a mop run regardless of water flow, so a `vacuum_mop` room with `water_level: "Off"` still counts as a wash cycle (and `_water_rate_ml_per_minute` returns 0 for off, so robot-water totals stay accurate). |
| `has_observed_active_lifecycle` | Pre-condition flag for auto-finalization. |
| `finalized` | `True` after `mark_active_job_finalized()` is called. |
| `finalize_summary` | Outcome metadata from the learning finalizer. |

### `self.runtime` — never persisted

`self.runtime` is a `dict[str, VacuumRuntimeState]`. Each `VacuumRuntimeState` instance holds fields that must survive within a HA session but must not survive a restart:

| Field | Description |
|---|---|
| `selected_map_id` | Map the card is currently showing. |
| `active_map_id` | Map ID reported by the vacuum sensor. |
| `queue_room_ids` | Copy of the queue for fast access without a dict lookup. |
| `active_job_room_ids` | Room IDs of the running job. |
| `start_block_reason` | Last computed reason for `get_start_status()`. |

The `room_history` bucket in `self.data` is also effectively runtime: it is populated by `async_preload_room_history_cache()` which reads the learning history files, not the `.storage` file. The `.storage` file never contains `room_history` data — it is rebuilt on demand each session.

---

## 5. Persistence Contract

### What `async_save` writes

`async_save()` serialises `self.data` in full to the HA `.storage` file at path `.storage/eufy_vacuum.storage`. The storage key is `"{DOMAIN}.storage"` and the version is `1`.

The full `self.data` dict is written, including all top-level keys listed in Section 4. HA's `Store` helper handles atomic writes via a temporary file + rename.

### What is runtime-only and why

The following are **never written to `.storage`** even though they live in `self.data` at runtime:

| Key | Why it is runtime-only |
|---|---|
| `room_history` | Rebuilt from the learning history files (individual job JSON files on disk) each session. Storing it in `.storage` would create stale duplicate state that diverges from the source of truth. |
| `queue` | Derived from `data["maps"]` on every room update. Storing it would create a stale snapshot that could disagree with actual room state after HA restart. |
| `payloads` | Same reason as `queue` — derived state. Rebuilt by `build_room_payload()`. |

These keys are populated during the session and written to `.storage` incidentally (they are part of `self.data`), but the correct initialisation path treats them as empty and rebuilds them. The `async_initialize` method does not seed `queue` or `payloads` keys — they appear in storage only if a job has already run.

### Calling `async_save`

`async_save()` is a public `async` method. Call it after any mutation that should survive a restart. Most service handlers call it after mutating state. For non-blocking fire-and-forget saves (e.g. within active-job update callbacks), use `_async_save_logged()` which catches and logs exceptions.

---

## 6. Notification System

The manager uses five callback lists for push-style notification of sensor and binary-sensor platform entities when state changes.

### Registration pattern

```python
manager.register_room_update_callback(my_callback)
# ...later, on platform unload:
manager.unregister_room_update_callback(my_callback)
```

Each callback is a plain callable. The notification methods call every registered callback inside a `try/except` and log exceptions without re-raising, so one bad callback cannot break others.

### Callback types and triggers

| Callback list | Notify method | Signature | What triggers it |
|---|---|---|---|
| `_room_update_callbacks` | `_notify_rooms_updated` | `(vacuum_entity_id, map_id)` | Any room field change: `update_room_fields`, `save_managed_rooms`, `apply_room_profile`, `apply_run_profile`, `set_rooms_enabled_subset`, `rebuild_map`, `_clear_room_selections_after_start` |
| `_run_profile_update_callbacks` | `_notify_run_profiles_updated` | `(vacuum_entity_id, map_id)` | `save_run_profile`, `overwrite_run_profile`, `rename_run_profile`, `delete_run_profile`, `apply_run_profile` |
| `_room_history_update_callbacks` | `_notify_room_history_updated` | `(vacuum_entity_id, map_id)` | `async_preload_room_history_cache` completion; `finalize_learning_for_active_job` when the completed job ingests into the cache |
| `_room_rule_status_update_callbacks` | `_notify_room_rule_status_updated` | `(vacuum_entity_id, map_id)` | `_update_room_rule_status_snapshot`, which is called as part of every `_build_effective_start_plan` invocation |
| `_theme_update_callbacks` | `_notify_theme_updated` | `(vacuum_entity_id=...)` | Any theme mutation: `save_theme_as_new`, `overwrite_theme`, `delete_theme`, `set_active_theme`, `update_working_draft`, `revert_draft`, `rename_theme`, `import_theme` |

`_notify_theme_updated` accepts `vacuum_entity_id=None` for global library changes (rename, delete, import) that affect all vacuums.

### `_refresh_room_derived_state`

A synchronous helper called after any room mutation. It rebuilds `build_queue` and `build_room_payload` for the affected map so the derived state is always consistent with the current room configuration. It does not fire callbacks — callers do that separately after calling this helper.

---

## 7. Section Map

The file is divided into clearly commented sections. This is the logical map:

| Section header | Key methods |
|---|---|
| Module-level helpers | `_safe_int`, `_safe_float`, `_display_label`, `_settings_profile_display`, `_room_surface_labels`, `_build_preloaded_theme_entry`, `_build_release_theme_colors`, `_build_release_theme_tokens` |
| Module-level constants | `PRELOADED_THEME_SPECS`, `BASE_PRELOADED_THEME_SPEC`, `_HA_ACTIVE_VACUUM_STATES`. Brand-specific catalogs (model names, upkeep guides, water tank configs) live in the adapter config — see [adapter-config-reference.md](adapter-config-reference.md). |
| Callback registration / notification | `register_*_callback`, `unregister_*_callback`, `_notify_*` |
| Vacuum / capability management | `ensure_vacuum_record`, `get_managed_vacuums`, `get_vacuum_capabilities`, `refresh_vacuum_capabilities`, `ensure_runtime` |
| Water usage estimation | `estimate_job_water_usage` |
| Active job tracking (state helpers) | `_default_active_job_state`, `_normalize_active_job`, `_derive_active_job_current_room_id`, `_compute_current_room_elapsed_minutes` |
| Active job tracking (observations) | `update_active_job_recharge_observation`, `update_active_job_mop_wash_observation`, `record_active_job_transition` |
| Transition-room position detection | `_access_graph_path`, `_get_robot_position`, `_detect_transition_room_from_position` |
| Dock actions | `get_dock_action_status`, `async_wash_mop`, `async_dry_mop`, `async_empty_dust`, `async_stop_dry_mop` |
| Room profiles (clean settings presets) | `get_room_profiles`, `save_user_room_profile`, `overwrite_room_profile`, `rename_room_profile`, `delete_room_profile`, `apply_room_profile` |
| Room field management | `update_room_fields`, `_finalize_room_update`, `_protected_room_config`, `_match_profile_from_fields`, `get_effective_room_details` |
| Room / map management | `discover_rooms`, `save_managed_rooms`, `get_managed_rooms`, `remove_map`, `get_vacuum_maps`, `rebuild_map` |
| Queue / payload building | `build_queue`, `build_room_payload`, `set_rooms_enabled_subset`, `get_queue_state`, `clear_queue` |
| Saved run profiles | `get_saved_run_profiles`, `save_run_profile`, `overwrite_run_profile`, `rename_run_profile`, `delete_run_profile`, `apply_run_profile` |
| Access graph / room rules | `_normalize_grants_access_to`, `_normalize_room_rules`, `_validate_room_access_graph`, `get_room_access_editor`, `get_access_graph_health`, `_build_effective_start_plan` |
| Lifecycle / start status | `build_room_payload`, `get_lifecycle_state`, `get_start_status` |
| Job control | `get_active_job`, `clear_active_job`, `pause_active_job`, `resume_active_job`, `record_completed_room`, `mark_active_job_finalized` |
| Job progress | `get_job_progress_snapshot`, `get_planned_job_estimate`, `get_job_control_state` |
| Job start | `start_selected_rooms`, `start_run_profile` |
| Job cancel / pause | `async_pause_active_job`, `async_resume_active_job`, `async_cancel_active_job` |
| Learning integration | `save_learning_snapshot_for_active_job`, `finalize_learning_for_active_job` |
| Upkeep / maintenance | `get_upkeep_snapshot`, `get_maintenance_remaining`, `reset_maintenance`, `get_dashboard_snapshot` |
| Onboarding | `get_onboarding_state`, `mark_rooms_discovered`, `confirm_floor_type`, `check_for_new_rooms`, `reset_onboarding` |
| Theme management | `get_theme_library`, `save_theme_as_new`, `overwrite_theme`, `rename_theme`, `delete_theme`, `set_active_theme`, `update_working_draft`, `revert_draft`, `export_theme`, `import_theme` |
| Room cleaning history | `get_room_cleaning_history`, `async_preload_room_history_cache`, `_ingest_completed_job_into_room_history` |
| Room rule status | `get_room_rule_status`, `get_runtime_path_block_report`, `_update_room_rule_status_snapshot` |
| Dock events | `record_dock_event`, `get_dock_events`, `set_dock_event_count` |
| Singleton helpers | `get_known_vacuum_ids`, `get_known_map_ids` |

---

## 8. Adding a New Service

Follow these steps in order. Each step is concrete and can be done independently before the next.

### Step 1 — Add the method to the manager

Add a synchronous or async method to `EufyVacuumManager`. Use keyword-only arguments. Return a plain `dict[str, Any]`. Always include `vacuum_entity_id` and `map_id` in the return value so the card knows which context the result belongs to.

```python
def get_my_new_thing(
    self,
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict[str, Any]:
    """Return ... for one vacuum/map."""
    # ... implementation ...
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        # ... result fields ...
    }
```

If the method mutates persistent state, call `await self.async_save()` before returning, or schedule `self._async_save_logged()` as a task.

### Step 2 — Add the service constant to `const.py`

```python
SERVICE_GET_MY_NEW_THING = "get_my_new_thing"
```

Add to both the declaration block and to `EUFY_SERVICES` (or whichever list is iterated by `async_unregister_services`).

### Step 3 — Add the Voluptuous schema and handler in `services.py`

Add a schema constant:

```python
GET_MY_NEW_THING_SCHEMA = vol.Schema({
    vol.Required("vacuum_entity_id"): cv.string,
    vol.Optional("map_id"): cv.string,   # auto-resolves via adapter
})
```

`map_id` is **always optional** on service schemas. The handler dispatches through `_resolved_call_data(hass, call)`, which fills in `map_id` from the adapter's declared `entities.active_map` entity when the caller omits it. Adapters that don't declare an active-map entity make the manager raise a clear error for the missing kwarg — no silent fallback.

Add the handler inside `async_register_services`:

```python
async def handle_get_my_new_thing(call: ServiceCall) -> None:
    manager = hass.data[DOMAIN][DATA_RUNTIME]
    result = manager.get_my_new_thing(**_resolved_call_data(hass, call))
    # Optionally fire a HA event or set call.return_value
    call.return_value = result

hass.services.async_register(
    DOMAIN,
    SERVICE_GET_MY_NEW_THING,
    handle_get_my_new_thing,
    schema=GET_MY_NEW_THING_SCHEMA,
    supports_response=SupportsResponse.OPTIONAL,
)
```

### Step 4 — Add the service descriptor to `services.yaml`

```yaml
get_my_new_thing:
  name: Get My New Thing
  description: Returns ... for one vacuum/map.
  fields:
    vacuum_entity_id:
      required: true
      example: "vacuum.alfred"
      selector:
        entity:
          domain: vacuum
    map_id:
      name: Map ID
      description: Leave blank to use the current active map.
      required: false
      example: "6"
      selector:
        text: {}
```

### Step 5 — Add to `async_unregister_services`

Find the list of service names iterated during teardown and add `SERVICE_GET_MY_NEW_THING` to it. This ensures the service is removed on integration unload, preventing ghost service entries if the integration is reloaded.

---

## 9. Key Invariants

These must always be true. Violating any of these produces subtle bugs that are hard to reproduce.

**`map_id` is always a string**
Map IDs are stored and passed as `str` throughout. Calls into `ensure_map_bucket`, `get_map_bucket`, and all `active_jobs` dict lookups use `str(map_id)`. Never pass a raw integer. The upstream HA sensor reports map IDs as strings; treat them as opaque string identifiers.

**`room_id` is always an integer in storage, a string key in dicts**
Room config dicts are keyed by `str(room_id)` inside `data["maps"]`. The `room_id` field inside each room dict is an `int`. Functions that receive a room ID from outside (service calls, events) must call `int(room_id)` before storage writes and `str(int(room_id))` before dict lookups. The `_safe_int` helper is the canonical way to parse untrusted room IDs.

**Active job slots are reset, not deleted**
`clear_active_job` and `remove_map` both reset an active job slot to `_default_active_job_state` rather than deleting the key. This means `get_active_job` can always find a key for any known vacuum/map pair and will never raise a `KeyError`.

**The active-job `status` field gates all mutation**
Methods like `pause_active_job`, `resume_active_job`, `record_completed_room`, and `update_active_job_recharge_observation` all check `status` before modifying the job. A job in `"completed"` or `"idle"` status will not be mutated. Respect this gate in any new job-related code.

**`_protected_room_config` is always applied before building a payload**
Carpet rooms must never send a mop-mode command. `_protected_room_config` enforces this: it downgrades `mop` and `vacuum_mop` modes on carpet rooms to `vacuum`, clears `water_level` to `"Off"`, and clears `edge_mopping`. Call `_protected_room_config` (or the higher-level `_finalize_room_update`) before persisting any room that has been modified by user input.

**Preloaded themes are never written by user operations**
The preloaded theme entries (all `theme_*` IDs) in `data["theme"]["library"]` are inserted by `_ensure_preloaded_theme_library` and must not be modified by `save_theme_as_new`, `import_theme`, or `delete_theme`. Protected theme IDs are the ones present in the library after `async_initialize` — they are identified by prefix (`theme_follow_ha`, `theme_core_slate`, etc.) and the delete/overwrite methods check for them explicitly by querying the preloaded spec list.

**`grants_access_to` stores integers, never strings**
The access-graph edge list (`room["grants_access_to"]`) stores integer room IDs. `_normalize_grants_access_to` enforces this and strips self-references, duplicates, and IDs that parse to `<= 0`. Never push raw strings into this list.

**The learning manager is accessed only through `_get_learning_manager()`**
The learning system is optional (it may not be loaded). All learning integration points check for `None` before calling any learning method. Do not assume the learning manager is present.

**`has_observed_active_lifecycle` must be set before auto-finalization can run**
The auto-finalization path in `services.py` (or wherever job completion is detected) guards on `active_job.get("has_observed_active_lifecycle")`. Call `manager.record_active_lifecycle_observed(...)` when the HA state machine transitions through an active cleaning state during a tracked job. Without this flag, a job started from outside the integration (e.g. directly from the Eufy app) will not be auto-finalized.
