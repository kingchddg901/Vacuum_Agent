# Adapter Config Reference

This is the canonical reference for the per-vacuum **adapter config** —
the single dict the framework reads to learn everything brand-specific
about a managed vacuum. The schema is defined in code at
`custom_components/eufy_vacuum/adapters/config_schema.py`; this doc
explains each section in human terms with examples and UI-builder notes.

Read [architecture-overview.md](architecture-overview.md) first for
context, and [porting-guide.md](../contributing/porting-guide.md) for the workflow of
adding a new brand.

---

## 1. What an adapter config is, and why it exists

The framework — lifecycle tracking, learning, water estimation, dock-event
recording, error tracking, room dispatch, upkeep guides — contains no
brand-specific knowledge. Every entity ID, vocabulary string, and
hardware constant it needs is read at runtime from the **adapter
registry**, a per-vacuum dict registered during integration setup.

There are two paths that populate the registry, and the framework
treats them identically:

| Path | When it runs | Stored where | Use case |
|------|--------------|--------------|----------|
| **Code adapter** | `async_setup_entry` calls `register_adapter_config(vacuum_entity_id, config)` | In-memory only | Reference brands shipped with the integration (Eufy today) |
| **Config adapter** | A future UI flow writes a dict to HA storage; `load_stored_adapter_configs()` loads it on setup | Persistent JSON | User-built configs for brands the integration doesn't ship with |

Both produce a dict matching the schema documented below. Both end up in
the same registry. Framework code never asks which path produced an
entry.

---

## 2. Two audiences for this document

This reference serves two readers:

- **Adapter authors** writing a Python module like
  `adapters/eufy/adapter.py` that calls `register_adapter_config()`
  with a hand-built dict. Look at the **Schema** and **Example** boxes
  in each section.
- **UI builder implementers** building the future config-flow card that
  lets users construct a config by filling in fields. Look at the
  **UI builder notes** at the end of each section for control types,
  validation, and which sections are conditional on others.

Both audiences produce the same shape, so the schema reference is
shared.

---

## 3. The full shape at a glance

```python
{
    # Identity
    "adapter_id": str,           # required
    "source": "code" | "config", # required
    "display_name": str,         # optional

    # Brand surface
    "entities": { ... },         # required — maps role keys → HA entity IDs
    "vocabulary": { ... },       # optional — raw and normalized state strings
    "completion": { ... },       # optional — what counts as job done
    "charging": { ... },         # optional — charging detection signals
    "error_tracking": { ... },   # optional — error tracker config
    "dock_events": { ... },      # optional — dock event triggers
    "post_job_wash_amendment": { ... },  # optional — post-job water amendment
    "discovery": { ... },        # optional — how room list is exposed
    "dispatch": { ... },         # required — how to send a clean job
    "mapping": { ... },          # optional — pluggable segmenter engine selection

    # Static catalogs (display + hardware constants)
    "capabilities": { ... },             # optional — explicit capability flags
    "maintenance_components": { ... },   # optional — replacement counter catalog
    "upkeep_catalog": { ... },           # optional — per-component guides
    "water_model_configs": { ... },      # optional — per-model tank measurements
}
```

Every section except `entities` and `dispatch` is optional. Absent
sections produce graceful degradation — the corresponding subsystem
disables itself rather than erroring. The degradation behavior is
called out in each section below.

---

## 4. Identity

### `adapter_id` *(required, str)*

Stable unique identifier for this adapter. Used in logs and to
disambiguate when multiple adapters exist in storage. Example:
`"eufy_x10_pro_omni"`.

### `source` *(required, str — `"code"` or `"config"`)*

How this entry was produced. Code adapters set `"code"` and overwrite
any stored config for the same vacuum at setup time (code wins). The
UI flow sets `"config"`.

### `display_name` *(optional, str)*

Human-readable label shown in the UI and logs. Example:
`"Eufy X10 Pro Omni"`.

**UI builder notes:** `adapter_id` is auto-generated (slug of
`display_name`) or hidden; `source` is hard-coded to `"config"` by the
form; `display_name` is the only visible field — a text input with
basic non-empty validation.

---

## 5. `entities` — the role-to-entity-ID map

Full HA entity IDs for every companion sensor or helper the framework
reads. Keys are **role names** the framework uses internally; values
are the **specific entity IDs** that fulfill the role for this brand.
Section 19 lists the framework modules that consume each role — useful
when sizing the impact of an absent entity. The two wash-frequency
keys are consumed by the timing estimator, documented in
[learning-system.md](learning-system.md).

Every key is optional. Missing entities degrade the feature that
depends on them — they never raise.

### Schema

| Key | Required by framework? | What the framework does without it |
|-----|------------------------|-------------------------------------|
| `task_status` | Strongly recommended | Lifecycle detection, job-completion signal, and learning all disabled. The integration becomes a passive room manager. |
| `dock_status` | Recommended | Dock event recording, mop-wash observation, post-job water amendment all disabled. |
| `active_map` | Recommended | Map mismatch check skipped — a job started on the wrong map will silently dispatch. |
| `active_cleaning_target` | Optional | Completion relies on `task_status` alone. |
| `cleaning_time` | Optional | Duration derived from job timestamps only (less precise). |
| `cleaning_area` | Optional | Area omitted from the job record. |
| `battery` | Optional | Falls back to the `battery_level` attribute on the vacuum entity. |
| `error_message` | Optional | Error tracker relies on secondary channels (vacuum state, `task_status`) only. |
| `charging` | Recommended | Charging detection falls back to substring matching on `task_status`/`dock_status` — known false-negative source. |
| `wash_frequency_mode` | Optional | Water estimator uses the default interval. |
| `wash_frequency_value_time` | Optional | Water estimator uses the default interval. |
| `dry_duration` | Optional | Dry-start dock events store no duration. |
| `water_level` | Optional | Water estimator can't track actual tank-level deltas, falls back to flow-rate-only. |
| `robot_position_x` | Optional | Mapping subsystem inactive — no trace recording, no derived room bounds. |
| `robot_position_y` | Optional | Same as above; both X and Y must be present. |
| `work_mode` | Optional | Work-mode block check in the start-blocker skipped. |
| `cleaning_intensity` | Optional | Path-control capability inferred from model family only. |

### Example (from Eufy adapter)

```python
"entities": {
    "task_status": "sensor.alfred_task_status",
    "dock_status": "sensor.alfred_dock_status",
    "active_map": "sensor.alfred_active_map",
    "active_cleaning_target": "sensor.alfred_active_cleaning_target",
    "cleaning_time": "sensor.alfred_cleaning_time",
    "cleaning_area": "sensor.alfred_cleaning_area",
    "battery": "sensor.alfred_battery",
    "error_message": "sensor.alfred_error_message",
    "charging": "binary_sensor.alfred_charging",
    "wash_frequency_mode": "select.alfred_wash_frequency_mode",
    "wash_frequency_value_time": "number.alfred_wash_frequency_value_time",
    "dry_duration": "select.alfred_dry_duration",
    "water_level": "sensor.alfred_water_level",
    "robot_position_x": "sensor.alfred_robot_position_x_raw",
    "robot_position_y": "sensor.alfred_robot_position_y_raw",
    "work_mode": "sensor.alfred_work_mode",
    "cleaning_intensity": "select.alfred_cleaning_intensity",
},
```

**UI builder notes:** Render each role as an entity-picker control
filtered to the relevant domain (`sensor.`, `binary_sensor.`,
`select.`, `number.`). Pre-fill candidates by scanning entities whose
`object_id` shares a prefix with the vacuum's `object_id`. Empty fields
are valid — store as omitted keys, not empty strings.

---

## 6. `vocabulary` — raw and normalized state strings

Brand-specific state strings the framework matches against runtime
sensor values. **Matching convention:** the framework compares
`.strip().lower()` of the live sensor state against the strings in
these lists, so entries should be lowercased.

The two exceptions are the `blocked_*_states` lists, which are matched
against **raw** (non-normalized) sensor values — those use the
title-cased firmware strings exactly as they appear in HA.

### Schema

| Field | Type | Purpose |
|-------|------|---------|
| `hard_service_states` | `list[str]` (normalized) | Dock/task states that **block** job start. The dock is performing an uninterruptible service action (washing, recycling waste water, emptying). |
| `drying_states` | `list[str]` (normalized) | Dock states that produce a **warning** but do not block job start. |
| `active_run_task_states` | `list[str]` (normalized) | `task_status` values indicating the vacuum is actively running a job. Used to detect `vacuum_busy` and set `has_observed_active_lifecycle`. |
| `not_error_sentinels` | `list[str]` (normalized) | `error_message` values that mean *no error*. Anything not in this set is treated as a real error. |
| `blocked_work_mode_states` | `list[str]` (**raw**) | `work_mode` values that block job start. Title-cased firmware strings. |
| `blocked_task_status_states` | `list[str]` (**raw**) | `task_status` values that block job start. Title-cased firmware strings. |
| `blocked_dock_status_states` | `list[str]` (**raw**) | `dock_status` values that block job start. Title-cased firmware strings. |
| `cancel_service_exclusion_states` | `list[str]` (normalized) | If any of these appear in the `task_status` transition history of a very short job, the cancel detector treats the early return as a service event (low-battery, mop wash, dust empty) rather than a manual cancel. |
| `water_level_aliases` | `dict[str, str]` | Maps lowercased water-level display strings to canonical keys (`low`/`medium`/`high`) for water-rate lookup. |
| `wash_frequency_mode_aliases` | `dict[str, str]` | Maps lowercased wash-frequency mode strings to canonical keys (`by_time`/`by_area`/`after_each_clean`). |
| `clean_mode_options` | `list[dict]` | User-facing dropdown options for clean mode. Each entry is `{value, label}`. Read by the card's room editor and rule editor to populate the cleaning-mode picker. Eufy: 3 entries (vacuum/mop/vacuum_mop). |
| `fan_speed_options` | `list[dict]` | User-facing dropdown options for fan speed. Each entry is `{value, label}`. Eufy: 4 entries (Quiet/Standard/Boost/Max). A Roborock adapter with Max+ would declare 5. |
| `water_level_options` | `list[dict]` | User-facing dropdown options for water level (mop-capable models only). Each entry is `{value, label}`. Eufy: 4 entries (Off/Low/Medium/High). |
| `clean_intensity_options` | `list[dict]` | User-facing dropdown options for cleaning intensity. Each entry is `{value, label}`. Brands without intensity/path-type concept omit this; the card hides the picker. Eufy: 3 entries (Quick/Narrow/Deep). |

### Example

```python
"vocabulary": {
    "hard_service_states": ["recycling waste water", "washing", "washing mop"],
    "drying_states": ["drying"],
    "active_run_task_states": ["cleaning", "returning", "paused", "going to wash mop"],
    "not_error_sentinels": ["", "unknown", "unavailable", "no error"],
    "blocked_work_mode_states": ["Smart Follow", "Auto", "Room"],
    "blocked_task_status_states": ["Cleaning", "Returning", "Washing Mop"],
    "blocked_dock_status_states": ["Washing", "Recycling waste water"],
    "cancel_service_exclusion_states": ["returning to charge", "going to wash mop"],
    "water_level_aliases": {"small": "low", "standard": "medium", "large": "high"},
    "wash_frequency_mode_aliases": {"by time": "by_time", "by area": "by_area"},
    "clean_mode_options": [
        {"value": "vacuum",     "label": "Vacuum"      },
        {"value": "mop",        "label": "Mop"         },
        {"value": "vacuum_mop", "label": "Vacuum & Mop"},
    ],
    "fan_speed_options": [
        {"value": "Quiet",    "label": "Quiet"   },
        {"value": "Standard", "label": "Standard"},
        {"value": "Boost",    "label": "Boost"   },
        {"value": "Max",      "label": "Max"     },
    ],
    "water_level_options": [
        {"value": "Off",    "label": "Off"   },
        {"value": "Low",    "label": "Low"   },
        {"value": "Medium", "label": "Medium"},
        {"value": "High",   "label": "High"  },
    ],
    "clean_intensity_options": [
        {"value": "Quick",  "label": "Quick" },
        {"value": "Narrow", "label": "Narrow"},
        {"value": "Deep",   "label": "Deep"  },
    ],
},
```

### How the four option lists flow to the card

The card never probes upstream brand-integration select entities to
discover what values are valid. Instead the adapter declares its
supported value set in these four lists and the card reads them
through two transport paths:

1. **Main card** — `get_dashboard_snapshot()` includes an
   `adapter_vocabulary` field that mirrors this whole `vocabulary`
   block. The card's state layer exposes
   `state.adapterOptionsFor(roleKey)` returning the matching
   `{value, label}[]` list.
2. **Standalone Eufy Room Card** — the room switch entity surfaces
   each option list as an attribute (`clean_mode_options`,
   `fan_speed_options`, etc.) so the standalone card can read from
   `switch.attributes.<role>_options` directly without going through
   the integration's service layer.

Both paths use the same `{value, label}` shape and the card stores
the `value` while displaying the `label`. A Roborock port whose
`fan_speed_options` includes a fifth `Max+` entry gets a 5-chip
fan-speed picker automatically — no card code changes needed.

**UI builder notes:** Use chip/tag inputs for each list field. For the
`blocked_*` fields the form should display a notice that values are
case-sensitive raw firmware strings; for everything else, the form can
auto-lowercase on submit. The alias dict fields are key-value pair
editors.

**How to discover the right strings:** the reliable way is to record
a real clean cycle and read the values directly off an HA recorder
trace. See [porting-guide.md §4](../contributing/porting-guide.md#recommended-capture-a-real-clean-cycle-with-the-timeline-card)
for the recommended workflow using the `ha-state-timeline-card`.

---

## 7. `completion` — what counts as job done

Defines the signal pair the lifecycle layer watches for to declare a
job complete.

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `task_status_value` | `str` | `"completed"` | Normalized `task_status` value that signals completion. |
| `secondary_clear_entity` | `str` | `"active_cleaning_target"` | Entity *key* (from the `entities` dict, not a full ID) whose cleared state must coincide. |
| `secondary_clear_sentinels` | `list[str]` | `["", "unknown", "unavailable", "none", "null"]` | Values that mean the secondary entity is cleared. |

### Example

```python
"completion": {
    "task_status_value": "completed",
    "secondary_clear_entity": "active_cleaning_target",
    "secondary_clear_sentinels": ["", "unknown", "unavailable", "none", "null"],
},
```

**UI builder notes:** This section is rarely customised — the form can
hide it behind an "Advanced" toggle and pre-fill the defaults. The
`secondary_clear_entity` field must be a dropdown populated from the
keys present in the `entities` section above it.

---

## 8. `charging` — charging detection signals

Configures how the framework detects whether the vacuum is currently
charging.

### Schema

| Field | Type | Purpose |
|-------|------|---------|
| `binary_sensor_entity` | `str` | Entity *key* (from `entities`) for the charging binary sensor. Primary signal. |
| `fallback_task_status_string` | `str` | `task_status` value indicating mid-job recharge resume (used when the binary sensor is absent). |
| `fallback_substrings` | `list[str]` | Substrings matched against `task_status`/`dock_status` as last-resort fallback. **Substring matching has known false negatives — only use as last resort.** |

### Example

```python
"charging": {
    "binary_sensor_entity": "charging",
    "fallback_task_status_string": "charging (resume)",
    "fallback_substrings": ["charg", "recharg"],
},
```

**UI builder notes:** If the user has selected a charging entity in
the `entities` section, the substring fallback is unnecessary — gray it
out or hide it. Show a one-line warning that substring matching is
unreliable.

---

## 9. `error_tracking` — error tracker configuration

Configures the active-run error tracker (`core/error_tracker.py`).

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `task_status_error_value` | `str` | `"error"` | Normalized `task_status` value indicating error state (secondary error channel). |
| `grace_window_seconds` | `int` | `5` | Wait window after the secondary signal fires before finalising as unknown error — some firmware emits the state DPS before the message DPS. |
| `error_code_attribute_names` | `list[str]` | – | Attribute names to check when reading an error code. Tried in order, first non-zero int wins. |
| `unknown_error_message` | `str` | `"Unknown error during run"` | Placeholder used when the grace window elapses without a real message. |

### Example

```python
"error_tracking": {
    "task_status_error_value": "error",
    "grace_window_seconds": 5,
    "error_code_attribute_names": ["error_code", "code", "errorCode"],
    "unknown_error_message": "Unknown error during run",
},
```

**UI builder notes:** Advanced section — collapse by default. The
`error_code_attribute_names` field is an ordered list editor (drag
to reorder).

---

## 10. `dock_events` — dock event recording

Configures the dock event recorder (`last_mop_wash`, `last_dust_empty`,
`last_dry_start`).

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `enabled` | `bool` | `False` | Whether to record dock events at all. Set `False` for brands with no dock actions. |
| `triggers` | `dict[str, list[str]]` | – | Maps framework event type keys to the normalized `dock_status` strings that trigger them. |

Framework event type keys: `last_mop_wash`, `last_dust_empty`,
`last_dry_start`. Absent keys produce no events of that type.

### Example

```python
"dock_events": {
    "enabled": True,
    "triggers": {
        "last_mop_wash": ["washing", "washing mop"],
        "last_dust_empty": ["emptying", "emptying dust"],
        "last_dry_start": ["drying"],
    },
},
```

**UI builder notes:** Toggle for `enabled`, then for each framework
event key a chip-input for the trigger strings. The form should hide
the triggers editor when `enabled` is `False`.

---

## 11. `post_job_wash_amendment` — post-job water amendment

For brands whose dock washes the mop *after* the robot docks and after
the framework has already finalized the job file. The amendment
watcher patches the completed job's water actuals once the wash cycle
ends.

See `core/water_amendment.py`.

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `enabled` | `bool` | `False` | Whether to register the watcher at all. |
| `trigger_states` | `list[str]` (normalized) | – | `dock_status` strings that increment the wash count. |
| `commit_state` | `str` (normalized) | – | `dock_status` string that signals the wash cycle is complete and triggers the amendment commit. |
| `debounce_seconds` | `float` | `60.0` | Minimum seconds between wash-count increments. Prevents double-counting multi-state wash sequences. Set to `0` for brands with single-state cycles. |
| `timeout_seconds` | `int` | `180` | Watcher timeout — closes regardless of `commit_state` after this many seconds. Safety valve. |

### Example

```python
"post_job_wash_amendment": {
    "enabled": True,
    "trigger_states": ["washing", "washing mop"],
    "commit_state": "drying",
    "debounce_seconds": 60.0,
    "timeout_seconds": 180,
},
```

**UI builder notes:** Hide entire section behind `enabled` toggle. The
`trigger_states` and `commit_state` fields should auto-populate
candidates by scanning recent values of the configured `dock_status`
entity if available.

---

## 12. `discovery` — how the room list is exposed

Tells the room discovery layer where to find the list of rooms the
vacuum has segmented.

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `room_list_entity` | `str` | `"vacuum_entity"` | Which entity exposes the list. Special value `"vacuum_entity"` means read from the vacuum entity itself; otherwise supply a full entity ID. |
| `room_list_attribute` | `str` | – | Attribute name on the entity that contains the list. Expected to be a `list[dict]`. |
| `room_id_key` | `str` | – | Key in each room dict that contains the room ID. Eufy: `"id"`. Roborock: `"segment_id"`. |
| `room_name_key` | `str` | – | Key in each room dict that contains the room name. Usually `"name"`. |
| `auto_refresh_on` | `list[str]` | `["vacuum_docked", "active_map_changed", "config_entry_reload"]` | Event triggers that automatically run discovery. Closed enum; see runtime notes below. |
| `auto_refresh_interval_seconds` | `int` | `21600` (6h) | Periodic safety-net discovery interval. `0` disables the floor. |
| `removal_confirmation_passes` | `int` | `3` | Consecutive discovery passes a configured room must be absent from before the framework flags it as removed. Prevents transient API glitches from producing spurious "room removed" notifications. |
| `new_room_confirmation_passes` | `int` | `1` | Consecutive passes a new room must appear in before being flagged for user review. Default `1` surfaces immediately. |

### Auto-discovery cadence and drift detection

Discovery isn't a one-time event — the framework runs it on each
declared trigger plus the safety-net interval. Each pass updates the
per-room missing/seen counters in
`manager.data["setup_progress"][vacuum_entity_id]["room_drift_history"]`.

Drift is computed at status-read time from those counters:

- **`new_rooms`** — discovered, not configured, not rejected, with
  `seen_passes ≥ new_room_confirmation_passes`
- **`removed_rooms`** — configured, missing for
  `≥ removal_confirmation_passes` consecutive passes
- **`transiently_missing`** — configured, missing 1..N-1 passes; not
  user-visible by default but available for debug views

A genuinely-removed room shows up in the setup tab within ~one day at
typical clean cadence (3 passes × 6-12h between events). A 5-minute
API glitch never surfaces.

### Example

```python
"discovery": {
    "room_list_entity": "vacuum_entity",
    "room_list_attribute": "segments",
    "room_id_key": "id",
    "room_name_key": "name",
    "auto_refresh_on": [
        "vacuum_docked",
        "active_map_changed",
        "config_entry_reload",
    ],
    "auto_refresh_interval_seconds": 21600,
    "removal_confirmation_passes": 3,
    "new_room_confirmation_passes": 1,
},
```

**UI builder notes:** Provide a "test discovery" button that calls the
configured path against the user's vacuum and shows the resolved
room list. Highest-value validation in the form.

---

## 12a. `setup` — adapter-declared setup steps

The setup flow is data-driven by an adapter-declared list of step IDs.
The framework iterates whatever steps the adapter requires; the card
renders one view per step in order.

### Schema

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `steps` | `list[str]` | yes | Ordered list of step IDs from the closed enum below. |

**Closed enum of step IDs:**

| ID | Service | Completes when | Universal? |
|----|---------|----------------|------------|
| `add_vacuum` | `setup_add_vacuum` | Vacuum present in `managed_vacuums` | Yes |
| `import_active_map` | `setup_import_active_map` | At least one map with rooms exists | Eufy + similar single-map-surfaced brands |
| `save_rooms` | `setup_save_rooms` | All discovered rooms are either `is_configured: True` or rejected | **Yes — universal floor-type + phantom-filter step** |
| `set_dock_position` (reserved) | `mapping.set_dock_anchor` | Dock anchor stored | Brand-specific future |

Adapters omitting `setup.steps` default to `["add_vacuum", "save_rooms"]`.
The Eufy adapter declares `["add_vacuum", "import_active_map", "save_rooms"]`
because robovac_mqtt surfaces only one map at a time and requires an
explicit import operation.

### Example

```python
"setup": {
    "steps": ["add_vacuum", "import_active_map", "save_rooms"],   # Eufy
},
# or, for brands with always-on map exposure:
"setup": {
    "steps": ["add_vacuum", "save_rooms"],
},
```

### Step completion semantics

Each `setup_*` service appends its step ID to
`manager.data["setup_progress"][vacuum_entity_id]["completed_steps"]`
on success. The `save_rooms` step is special: even after being marked
complete, drift detection can flip it back to "not completed" if
discovery later finds new rooms (the setup tab re-opens for review).

Two helper services support drift management:

- **`setup_reject_rooms`** — explicitly mark room IDs as phantoms.
  Rejected rooms never surface in `new_rooms` again, even if discovery
  re-reports them. Stored at `setup_progress.rejected_rooms`.
- **`setup_force_remove_room`** — bypass the missing-pass counter and
  immediately flag a room as removed, for the "I know this room is
  gone" path. Doesn't delete the room from `managed_rooms` (history
  preserved); only flips the drift signal.

**UI builder notes:** Render the step list as a progress indicator;
clicking an incomplete step opens the matching service-call form. The
`save_rooms` view should always be reachable even when "completed",
because drift can re-open it; expose room_drift.new_rooms,
room_drift.removed_rooms, and a manual "rescan" button there.

---

## 13. `dispatch` — how to send a clean job

The most brand-specific section. Configures the HA service call the
framework makes when starting a room-clean job. For the actual wire
shape and value vocabularies the framework produces from this
config, see [queue-engine.md](queue-engine.md); for worked dispatch
blocks for Eufy, Roborock, Dreame, and Narwal, see
[porting-guide.md §3](../contributing/porting-guide.md#3-brand-catalog).

### Schema

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `template` | `str` | yes | One of: `eufy_room_clean`, `roborock_segment_clean`, `dreame_room_clean`, `generic_room_ids`. Determines payload construction. |
| `service_domain` | `str` | yes | HA service domain. Usually `"vacuum"`. |
| `service_name` | `str` | yes | HA service name. Usually `"send_command"`. |
| `command` | `str` | conditional | Command string passed inside the service call. Required for templates with a `command` field (e.g. Eufy `room_clean`). |
| `map_id_field` | `str` | no | Field name for map_id in the payload. Default `"map_id"`. |
| `map_id_type` | `"int" \| "str"` | no | Type to cast map_id to. Default `"str"`. |
| `room_id_field` | `str` | no | Field name for room ID in each room entry. Eufy: `"id"`. Roborock: `"segment_id"`. |
| `clean_passes_field` | `str` | no | Field name for clean passes. Eufy: `"clean_times"`. Roborock: `"repeat"`. |
| `rooms_field` | `str` | no | Field name for the rooms list. Eufy: `"rooms"`. Roborock: `"segments"`. |

### Example: `eufy_room_clean`

Wraps a `room_clean` command inside `vacuum.send_command` with an
integer `map_id` and a `rooms` array of dicts keyed by `id` and
`clean_times`.

```python
"dispatch": {
    "template": "eufy_room_clean",
    "service_domain": "vacuum",
    "service_name": "send_command",
    "command": "room_clean",
    "map_id_field": "map_id",
    "map_id_type": "int",
    "room_id_field": "id",
    "clean_passes_field": "clean_times",
    "rooms_field": "rooms",
},
```

Generates a payload shaped like:

```python
{
    "command": "room_clean",
    "params": {
        "map_id": 6,
        "rooms": [
            {"id": 1, "clean_times": 2, "fan_speed": "Standard", ...},
            {"id": 3, "clean_times": 1, "fan_speed": "Boost", ...},
        ],
    },
}
```

### Example: `roborock_segment_clean`

Calls the Roborock integration's `vacuum.send_command` with the
`app_segment_clean` command and a list of segment IDs. Roborock uses
`segment_id` rather than `id`, and `repeat` rather than `clean_times`.

```python
"dispatch": {
    "template": "roborock_segment_clean",
    "service_domain": "vacuum",
    "service_name": "send_command",
    "command": "app_segment_clean",
    "map_id_field": "map_id",
    "map_id_type": "str",
    "room_id_field": "segment_id",
    "clean_passes_field": "repeat",
    "rooms_field": "segments",
},
```

### Example: `dreame_room_clean`

Dreame integrations vary; the most common shape calls a custom
service with a comma-separated room ID string. The dispatch template
flattens the `rooms` array to ID-only form.

```python
"dispatch": {
    "template": "dreame_room_clean",
    "service_domain": "dreame_vacuum",
    "service_name": "vacuum_clean_segment",
    "room_id_field": "segments",
    "clean_passes_field": "repeats",
    "rooms_field": "segments",
},
```

### Example: `generic_room_ids`

The fallback path for any integration that accepts a flat list of
room IDs. No payload metadata is forwarded — fan speed, water level,
clean mode, and passes are all dropped. Use this only when no
brand-specific template fits.

```python
"dispatch": {
    "template": "generic_room_ids",
    "service_domain": "vacuum",
    "service_name": "clean_segment",
    "room_id_field": "segments",
    "rooms_field": "segments",
},
```

Generates a minimal payload:

```python
{
    "entity_id": "vacuum.my_vacuum",
    "segments": [1, 3, 5],
}
```

### The per-room payload body

The outer-wrapper fields above (`map_id_field`, `room_id_field`,
`clean_passes_field`, `rooms_field`) control the keys around the
rooms array. The per-room dicts *inside* that array carry brand-
specific fields — clean mode, fan speed, water level, edge mopping,
path type, clean intensity — whose names and value vocabularies are
controlled by the **`dispatch.room_fields`** block.

A per-room dict for a mop-capable Eufy job looks like:

```python
{
    "id": 1,                       # ← name from dispatch.room_id_field
    "clean_times": 2,              # ← name from dispatch.clean_passes_field
    "fan_speed": "Standard",       # ← name + value via dispatch.room_fields.fan_speed
    "clean_mode": "vacuum_mop",    # ← name + value via dispatch.room_fields.clean_mode
    "clean_intensity": "Strong",   # ← name + value via dispatch.room_fields.clean_intensity
    "water_level": "Medium",       # ← conditional on supports_water_control + mop mode
    "edge_mopping": True,          # ← conditional on supports_edge_mopping + mop mode
    "path_type": "Standard",       # ← conditional on supports_path_control
}
```

The framework writes six canonical fields, each adapter-configurable:

| Canonical field | Renamed via | Value-mapped via |
|-----------------|-------------|------------------|
| `fan_speed` | `dispatch.room_fields.fan_speed.field_name` | `dispatch.room_fields.fan_speed.value_map` |
| `clean_mode` | `dispatch.room_fields.clean_mode.field_name` | `dispatch.room_fields.clean_mode.value_map` |
| `clean_intensity` | `dispatch.room_fields.clean_intensity.field_name` | `dispatch.room_fields.clean_intensity.value_map` |
| `water_level` | `dispatch.room_fields.water_level.field_name` | `dispatch.room_fields.water_level.value_map` |
| `edge_mopping` | `dispatch.room_fields.edge_mopping.field_name` | `dispatch.room_fields.edge_mopping.value_map` |
| `path_type` | `dispatch.room_fields.path_type.field_name` | `dispatch.room_fields.path_type.value_map` |

**Per-field semantics:**

- `field_name: str` — wire field name to use. Defaults to the
  canonical name when absent.
- `field_name: None` — **omits the field entirely**. Use for brands
  that don't expose this concept (e.g. Roborock has no `clean_intensity`
  surface, Dreame has no per-room `edge_mopping`).
- `value_map: dict[str, Any]` — maps the framework's canonical string
  values (`"Standard"`, `"vacuum_mop"`, etc.) to brand-specific wire
  values. Lookup is by `str(value)`, so booleans stringify cleanly.
  Values not in the map pass through unchanged.
- `value_map: None` (or absent) — identity passthrough; canonical
  value goes to the wire verbatim. Used by Eufy.

The framework reads canonical values from the room profile, then
`_write_room_field()` in `queue/queue_engine.py` applies the rename
+ value map per field. Capability gates (mop mode for water/edge,
`supports_path_control` for path_type) still apply *before* the
write so unsupported fields never reach the payload regardless of
the adapter's declarations.

A Roborock dispatch block illustrates the full feature:

```python
"dispatch": {
    # ...outer wrapper fields...
    "room_fields": {
        "fan_speed": {
            "field_name": "fan_power",
            "value_map": {
                "Quiet": 101, "Standard": 102,
                "Boost": 103, "Max": 104,
            },
        },
        "clean_mode": {
            "field_name": "mop_mode",
            "value_map": {"vacuum": 300, "vacuum_mop": 302, "mop": 304},
        },
        "water_level": {
            "field_name": "water_box_mode",
            "value_map": {"Low": 200, "Medium": 201, "High": 202},
        },
        # Fields Roborock doesn't expose:
        "edge_mopping":    {"field_name": None},
        "clean_intensity": {"field_name": None},
        "path_type":       {"field_name": None},
    },
}
```

The full Eufy reference adapter and brand catalog for Roborock,
Dreame, and Narwal live in
[porting-guide.md §3](../contributing/porting-guide.md#3-brand-catalog).

### Implementation status

The full dispatch path — outer wrapper, per-room body, and the
service-call envelope (`service_domain` / `service_name` / `command`)
— is **fully adapter-driven** as of the dispatch refactor.
`queue/queue_engine.py::build_room_clean_payload()` consumes every
declared knob; `core/manager.py::async_start_room_clean_job()` reads
`dispatch.service_domain` / `service_name` / `command` and constructs
either the wrapped (`{command, params: payload}`) or direct
(`{**payload}`) envelope based on whether `command` is set.

All four call sites of `build_room_clean_payload` in `core/manager.py`
thread the adapter's dispatch config through. Defaults preserve
byte-for-byte Eufy behavior when `dispatch` is absent or partial, so
existing installs are unaffected.

**What remains brand-aware in framework code** (and would be a PR
rather than a config change):

- A *structurally* different payload shape — e.g. an integration that
  wants nested arrays instead of a list of dicts, or parallel-list
  uniform-settings (the Dreame `repeats` / `suction_level` pattern
  that applies one value to all rooms). The current schema assumes
  per-room dicts.
- A new canonical field outside the six above (e.g. a per-room mop
  pressure setting). The rename map is bounded by that set.
- A third service-call envelope shape — e.g. `entity_id` nested
  inside `params` rather than alongside it.

None of these block ports for the four common brands; they're future
extensions called out for completeness.

**UI builder notes:** Render `template` as a dropdown that selects a
per-template default for the other fields; let the user override any
field via a "customise" toggle. A "dry-run" button that constructs
the payload for a sample room selection and prints the service call
(without executing) is the highest-value debugging affordance.
The `template` value is informational today — `build_room_clean_payload`
reads the explicit field-name knobs, not the template — but the UI
should still use it as a preset selector for sensible defaults.

---

## 13a. `mapping` — pluggable segmenter engine selection

Selects which segmenter engine drives image-segment analysis for this
adapter. The framework's `MapSegmenter` registry holds the engines; the
adapter declares which one to use by name. Engines vary in what kind
of input they consume (image bytes vs. structured wire data vs. nothing
at all) but produce the same canonical `SegmentationResult`, so the
rest of the framework doesn't have to know which engine is selected.

See [mapping-system.md §2.0](mapping-system.md#20-the-segmenter-engine-seam)
for the full protocol, the three engine variants, and the
`SegmentationResult` shape.

### Schema

```python
"mapping": {
    "segmenter_engine":  str,                  # required if `mapping` present
    "segmenter_tuning":  dict[str, Any],       # required if `mapping` present (may be empty)
}
```

If the whole `mapping` block is absent, the framework treats this
adapter as if it had declared `noop_fallback` — no image segmentation
runs, trace-based room bounds keep working off vacuum-space samples,
the card stops rendering polygonal overlays. This is the right
declaration for adapters whose vendor provides no usable map image.

### `segmenter_engine` *(required when `mapping` is present, str)*

One of the names registered in `mapping/segmenter_engines.py`:
`_SEGMENTER_ENGINES`. Currently:

| Name | What it does |
|---|---|
| `eufy_cv_v1` | Pillow + NumPy + SciPy CV pipeline. Reads the stored map PNG. Default for adapters that ship flat map images (Eufy, Dreame). |
| `noop_fallback` | Returns empty result. Use when the vendor provides no map image. Trace tracking still works. |
| `roborock_deterministic` *(reserved)* | Will read structured vector map data from the wire payload instead of an image. Not yet implemented. |

Unknown values fall back to `noop_fallback` with a logged warning,
and `_validate_adapter` flags the unknown name as a validation issue
at registration time. Add new engines by writing a class that
satisfies the `MapSegmenter` protocol and registering it under a
new name (see [mapping-system.md §2.0b](mapping-system.md#20b-adding-a-new-engine)).

### `segmenter_tuning` *(required when `mapping` is present, dict)*

Engine-specific knobs. **Each engine owns its own tuning schema**
and validates the dict in its `validate_tuning(tuning) -> list[str]`
method — unknown keys produce non-blocking warnings, malformed
values produce blocking errors. The framework's `_validate_adapter`
delegates to the engine's validator at registration time.

For `eufy_cv_v1`, the accepted keys mirror the kwargs of
`detect_room_segments(...)` (see [mapping-system.md §2.1.1](mapping-system.md#211-input)):

```python
"segmenter_tuning": {
    "min_area_pixels":     int,                # default 1200
    "simplify_epsilon":    float | None,       # default None
    "expected_room_count": int | None,         # default None
    "max_segments":        int | None,         # optional cap
    "image_variant":       str | None,         # optional metadata label
    "assist_variant":      str | None,         # optional metadata label
}
```

For `noop_fallback`, the dict must be empty — any keys are flagged
as misconfiguration (since noop ignores tuning by definition).

### Example (from the Eufy adapter)

```python
"mapping": {
    "segmenter_engine": "eufy_cv_v1",
    "segmenter_tuning": {
        "min_area_pixels":     1200,
        "simplify_epsilon":    None,
        "expected_room_count": None,
    },
}
```

### Where the framework reads it

- `mapping/manager.py:get_image_segment_suggestions` — selects engine, layers caller kwargs over the adapter's `segmenter_tuning`, dispatches.
- `mapping/mapping_services.py:_handle_analyze_map_image` — same pattern for the user-facing service call.

The two call sites consume the canonical `SegmentationResult` and cache it under `map_bucket["image_segments"]` in `.storage`. The `runtime` and `segmentation.*` blocks that were top-level in earlier versions are now under `engine_diagnostics`; consumers that need them read via that path.

---

## 14. `capabilities` — explicit capability flags

Explicit capability flag declarations that override or supplement the
entity-presence-based detection in `core/capabilities.py`. For code
adapters these are set from known hardware specs. For config adapters
the UI flow can set them based on user answers.

### Schema

All optional booleans:

```
supports_mop_features      supports_water_control     supports_path_control
supports_edge_mopping      supports_mop_wash          supports_mop_dry
supports_empty_dust        supports_robot_position    supports_station_water
```

### Example

```python
"capabilities": {
    "supports_mop_features": True,
    "supports_water_control": True,
    "supports_path_control": True,
    "supports_edge_mopping": True,
    "supports_mop_wash": True,
    "supports_mop_dry": True,
    "supports_empty_dust": True,
    "supports_robot_position": True,
    "supports_station_water": True,
},
```

**UI builder notes:** Render as a grid of toggle switches. Pre-fill
from entity-presence detection (the form already knows which entities
the user filled in) and let the user override if they know better.

---

## 15. `maintenance_components` — replacement counter catalog

Catalog of components the firmware exposes as replacement counters,
plus per-component display metadata and interval bounds.

### Schema

Top-level is `dict[component_id, ComponentEntry]`. Each entry:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `sensor_suffix` | `str \| None` | yes | Suffix appended to `{object_id}_` to form the counter sensor entity ID. `None` when the component uses `proxy_for`. |
| `proxy_for` | `str \| None` | no | Component ID to use as the sensor source. Used when firmware shares a counter between components (e.g. swivel_wheel proxies filter). |
| `default_interval_hours` | `float` | yes | Manufacturer guide recommendation. Reference anchor for the user's configured interval. |
| `max_interval_hours` | `float` | yes | Ceiling for user-configured interval override. |
| `label` | `str` | yes | Human-readable component name for display. |
| `icon` | `str` | yes | MDI icon string. |

### Example

```python
"maintenance_components": {
    "filter": {
        "sensor_suffix": "filter_lifetime",
        "proxy_for": None,
        "default_interval_hours": 130.0,
        "max_interval_hours": 260.0,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "side_brush": {
        "sensor_suffix": "side_brush_lifetime",
        "proxy_for": None,
        "default_interval_hours": 130.0,
        "max_interval_hours": 260.0,
        "label": "Side Brush",
        "icon": "mdi:rotate-3d-variant",
    },
    # ...
},
```

**UI builder notes:** This is verbose to author by hand. The UI flow
should ship a per-template seed (e.g. a default Roborock catalog) and
let the user add/edit/remove entries.

---

## 16. `upkeep_catalog` — per-component upkeep guides

Display data for the per-component upkeep guides shown in the
maintenance card. **Pure strings — no logic.** The framework uses
this only to render guide text; component identity comes from
`maintenance_components`.

### Schema

| Field | Type | Purpose |
|-------|------|---------|
| `model_names` | `dict[str, str]` | Maps device model code (from the vacuum entity's `detected_model` attribute) to a display name. Example: `{"T2351": "Robovac X10 Pro Omni"}`. |
| `model_guide_families` | `dict[str, str]` | Maps device model code to a guide family key. Multiple models can share one family. |
| `guide_family_names` | `dict[str, str]` | Maps guide family key to display name shown in the upkeep guide header. |
| `guide_library` | `dict[str, dict[str, dict]]` | Two-level dict: `family_key → component_key → guide_entry`. Component keys must match `maintenance_components` keys. |

Each `guide_entry`:

```python
{
    "clean_frequency": str,          # e.g. "weekly"
    "replace_frequency": str | None, # e.g. "every 3-6 months", or None
    "steps": list[str],
    "notes": list[str],
}
```

### Example

```python
"upkeep_catalog": {
    "model_names": {"T2351": "Robovac X10 Pro Omni"},
    "model_guide_families": {"T2351": "x10_pro_omni"},
    "guide_family_names": {"x10_pro_omni": "X10 Pro Omni"},
    "guide_library": {
        "x10_pro_omni": {
            "filter": {
                "clean_frequency": "weekly",
                "replace_frequency": "every 3-6 months",
                "steps": [
                    "Open the top cover and remove the dust box.",
                    "Tap dust off the filter and empty the dust box.",
                ],
                "notes": ["Do not use a brush, hot water, or detergent."],
            },
            # ...
        },
    },
},
```

**UI builder notes:** The largest piece of free-form content in the
schema. Ship per-template starter content. Provide a rich-text-lite
editor for `steps` and `notes` (numbered/bulleted lists). Make
`guide_library` editable per-component, not as one massive JSON blob.

---

## 17. `water_model_configs` — per-model tank measurements

Physical water-tank dimensions per model. **Pure measurements — no
logic.** The estimator reads these to convert tank-percent deltas
into ml.

### Schema

Top-level is `dict[model_code, TankConfig]`. Each `TankConfig`:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `robot_internal_tank_ml` | `float` | yes | Capacity of the robot's onboard water reservoir in ml. |
| `dock_clean_tank_capacity_ml` | `float` | no | Capacity of the dock's clean-water tank in ml. Omit for models with no dock clean tank. |
| `dock_wash_overhead_ml_per_cycle` | `float` | no | Measured water consumption per mop-wash cycle, in ml. Subtracted from total dock-water delta to isolate floor-mopping water. Omit for models with no dock wash cycle. |

These values **must be measured on real hardware**. They are not
calculated; the estimator's accuracy depends on the measurement.

### Example

```python
"water_model_configs": {
    "T2351": {
        "robot_internal_tank_ml": 80.0,
        "dock_clean_tank_capacity_ml": 4000.0,
        "dock_wash_overhead_ml_per_cycle": 110.0,
    },
},
```

**UI builder notes:** Three numeric inputs per model. Show the user a
methodology note: "These are physical measurements of your specific
hardware. Fill the dock tank to a known volume, run the cycle, and
record what the percentage sensor shows."

---

## 18. The runtime contract

A few rules the framework relies on, called out so adapter authors
don't accidentally violate them:

1. **String matching is case-insensitive after `.strip().lower()`.**
   Vocabulary strings should be lowercased except in the explicitly
   labeled `blocked_*_states` lists.
2. **Entity keys vs entity IDs.** Fields like
   `completion.secondary_clear_entity` and
   `charging.binary_sensor_entity` are **keys** that index into the
   `entities` dict — they are not full entity IDs.
3. **Absent keys = feature off, not error.** The framework never
   raises when an optional field is missing; it disables the
   corresponding subsystem. Tests should cover the "minimum viable
   adapter" path (only `adapter_id`, `source`, `entities.task_status`,
   `dispatch`).
4. **Code adapters win.** If a vacuum has both a stored config adapter
   and a code adapter registered for it, the code adapter wins. This
   is intentional — code adapters are the maintained reference, and
   stale storage shouldn't override them.

---

## 19. Where the framework reads each section

For adapter authors verifying their config flows through the system,
this table maps schema sections to the modules that consume them:

| Section | Primary consumers |
|---------|-------------------|
| `entities` | `core/manager.py`, `core/error_tracker.py`, `core/water_amendment.py`, `learning/estimator.py`, `learning/job_finalizer.py`, `__init__.py` (lifecycle listeners) |
| `vocabulary` | `core/manager.py` (`get_lifecycle_state`, `get_dock_action_status`), `learning/estimator.py` (alias maps) |
| `completion` | `__init__.py` (`_completed_finalize_signals`), `core/manager.py` |
| `charging` | `adapters/eufy/charging.py` (currently the only consumer; will move to `core/` when generalised) |
| `error_tracking` | `core/error_tracker.py` |
| `dock_events` | `__init__.py` (`_register_dock_event_listeners`) |
| `post_job_wash_amendment` | `core/water_amendment.py`, `__init__.py` (registration call site) |
| `discovery` | `setup/workflow.py` (`discover_rooms_for_vacuum`) |
| `dispatch` | `queue/queue_engine.py` (`build_room_clean_payload`), `core/manager.py` (`async_start_room_clean_job`) |
| `capabilities` | `core/capabilities.py` (`detect_capabilities`) |
| `maintenance_components` | `core/manager.py` (`get_upkeep_snapshot`) |
| `upkeep_catalog` | `core/manager.py` (`_get_upkeep_model_meta`, `_get_upkeep_item_guide`) |
| `water_model_configs` | `core/manager.py` (`_get_water_model_config`), `learning/estimator.py` |

If you grep for `get_adapter_config(` in `custom_components/eufy_vacuum/`
you'll find every read site — there is no other path by which the
framework learns brand-specific facts.

---

## 20. Minimum viable adapter

The smallest legal config that loads without errors and lets the
integration manage rooms (no learning, no lifecycle, no dock events —
just room dispatch):

```python
{
    "adapter_id": "my_brand_minimal",
    "source": "code",
    "display_name": "My Brand (minimal)",
    "entities": {},
    "dispatch": {
        "template": "generic_room_ids",
        "service_domain": "vacuum",
        "service_name": "send_command",
    },
}
```

---

## 21. Services that read and write adapter configs

The framework exposes five `eufy_vacuum.*` services for managing
adapter configs from the future UI flow and for diagnostic use today.
All are registered in `services.py`. The central index of every
integration service lives in
[advanced/03-services.md](../advanced/03-services.md).

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `save_adapter_config` | Persist a UI-submitted adapter config dict to storage. The framework reads it on next setup. | `vacuum_entity_id`, `config: dict` | (none) | no |
| `delete_adapter_config` | Remove a stored adapter config. The next setup falls back to the code adapter if one is registered for the same vacuum. | `vacuum_entity_id` | (none) | no |
| `get_adapter_config` | Return the currently active adapter config for one vacuum (code adapter if present, otherwise stored). | `vacuum_entity_id` | (none) | yes — full adapter config dict |
| `discover_adapter_entities` | Scan HA for entities matching the adapter schema's entity roles based on a `detected_model` hint. Used by the UI to pre-fill the entity picker. | `detected_model: str` | (none) | yes — `{role_key: [candidate_entity_id, ...]}` |
| `observe_entity_states` | Return current state snapshots for a list of entity IDs. Used by the UI to validate that selected entities are reading sane values. | `entity_ids: list[entity_id]` | (none) | yes — `{entity_id: state_snapshot}` |

There's also one closely-related service that resolves capabilities from an adapter config:

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `get_vacuum_capabilities` | Detect or refresh the capability flags for one vacuum (delegates to `core/capabilities.py::detect_capabilities`). Reads `entities` and `capability_hints` from the adapter config. | `vacuum_entity_id` | `detected_model: str`, `refresh: bool` | yes — `{model, docking_capable, mop_capable, entities, features, supports_*}` |

### Notes on the UI workflow

The five `*_adapter_config` services are designed to power a future
multi-step config flow:

1. UI calls `discover_adapter_entities(detected_model="<model>")` to
   suggest candidate entity IDs for each role.
2. UI calls `observe_entity_states(entity_ids=[...])` to validate the
   user's picks against live values.
3. UI builds the full adapter config dict client-side.
4. UI calls `save_adapter_config(vacuum_entity_id, config)` to persist.
5. UI calls `get_adapter_config(vacuum_entity_id)` to confirm the
   round trip succeeded.

Until that UI lands, these services are still usable from HA
Developer Tools or scripts — they're the supported programmatic path
for managing stored adapter configs.

Everything beyond this is a graceful-degradation knob.
