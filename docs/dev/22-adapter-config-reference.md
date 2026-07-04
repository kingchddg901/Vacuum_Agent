# 22 — Adapter Config Reference

This is the canonical reference for the per-vacuum **adapter config** —
the single dict the framework reads to learn everything brand-specific
about a managed vacuum. The schema is defined in code at
`custom_components/eufy_vacuum/adapters/config_schema.py`; this doc
explains each section in human terms with examples and UI-builder notes.

Read [01-architecture-overview.md](01-architecture-overview.md) first for
context, and [porting-guide.md](../contributing/porting-guide.md) for the workflow of
adding a new brand. See [21-adapter-system.md](21-adapter-system.md) for the registry,
validation, and startup registration order that consumes this config.

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
    "brand": str,                # optional — short brand/app name for card copy

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
    "mapping": { ... },          # optional — pluggable MAP segmenter engine selection
    "map_state_source": { ... }, # optional — read the provider's OWN map segmentation (VA-owned room data)
    "map_render": { ... },       # optional — VA-owned client-side map raster render
    "job_segmenter": { ... },    # optional — pluggable JOB/run segmenter engine + threshold tuning
    "room_attribution": { ... }, # optional — pluggable ROOM-ATTRIBUTION engine (external-run room recovery)
    "live_transition": { ... },  # optional — live current-room rollover orchestration
    "room_profiles": { ... },    # optional — adapter-sourced room-profile vocabulary
    "anomaly": { ... },          # optional — live anomaly ratios (running-long / stall)
    "wash_frequency_bounds": { ... },    # optional — mop-wash interval clamp

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

### `brand` *(optional, str)*

Short brand/app name the card uses in copy — e.g. `"Eufy"`. The External Jobs
empty state renders `"Start a clean from the {brand} app"`; when absent the card
falls back to generic phrasing (`"your robot's app"`). Surfaced to the card via
the `get_external_pending_runs` service response, keeping brand names out of the
otherwise brand-agnostic card.

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
[10-learning-system.md](10-learning-system.md).

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
| `charging` | Recommended | Charging-dependent detection (battery-health charge sessions, mid-job recharge) is disabled — `is_charging()` returns `False`. There is **no** substring fallback (removed as a known false-negative source). |
| `wash_frequency_mode` | Optional | Water estimator uses the default interval. |
| `wash_frequency_value_time` | Optional | Water estimator uses the default interval. |
| `dry_duration` | Optional | Dry-start dock events store no duration. |
| `water_level` | Optional | Water estimator can't track actual tank-level deltas, falls back to flow-rate-only. |
| `robot_position_x` | Optional | Mapping subsystem inactive — no trace recording, no derived room bounds. |
| `robot_position_y` | Optional | Same as above; both X and Y must be present. |
| `work_mode` | Optional | Work-mode block check in the start-blocker skipped. |
| `cleaning_intensity` | Optional | Path-control capability inferred from model family only. |
| `total_cleaning_area` | Optional | Lifetime "Total cleaned" tile hidden in the Maintenance tab. |
| `total_cleaning_time` | Optional | Lifetime "Total time" tile hidden in the Maintenance tab. |
| `total_cleaning_count` | Optional | Lifetime "Cleans" tile hidden in the Maintenance tab. |
| `dock_firmware_version` | Optional | Dock firmware line hidden in the Maintenance overview. |
| `scene_select` | Optional | Vendor-app scenes select entity (e.g. eufy-clean `select.<object_id>_scene`). Its options are the app's saved scenes and selecting one **runs it immediately**, so the card only reads the options to build the "App scenes" run-launcher and fires `select_option` on Start. Absent (Roborock, or an eufy-clean build without scenes) → the App-scenes group is hidden. |

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
    "total_cleaning_area": "sensor.alfred_total_cleaning_area",
    "total_cleaning_time": "sensor.alfred_total_cleaning_time",
    "total_cleaning_count": "sensor.alfred_total_cleaning_count",
    "dock_firmware_version": "sensor.alfred_dock_firmware_version",
    "robot_position_x": "sensor.alfred_robot_position_x_raw",
    "robot_position_y": "sensor.alfred_robot_position_y_raw",
    "work_mode": "sensor.alfred_work_mode",
    "cleaning_intensity": "select.alfred_cleaning_intensity",
    "scene_select": "select.alfred_scene",
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
| `cancel_detection_states` | `dict[str, str]` (normalized) | Normalized `task_status` transition strings the cancel detector matches. Keys: `active`, `returning`, `paused`. A cancel-like transition is `active`→`returning` or `paused`→`returning`. Defaults to the HA-standard `cleaning`/`returning`/`paused`. |
| `water_level_aliases` | `dict[str, str]` | Maps lowercased water-level display strings to canonical keys (`low`/`medium`/`high`) for water-rate lookup. |
| `wash_frequency_mode_aliases` | `dict[str, str]` | Maps lowercased wash-frequency mode strings to canonical keys (`by_room`/`by_time`/`off`). |
| `clean_mode_aliases` | `dict[str, str]` | Maps clean-mode display strings (lowercased, non-alnum → one space) to the canonical codes the card vocab is keyed on (`vacuum`/`mop`/`vacuum_mop`). The learning manager normalizes observed room-profile settings through this so the card receives a code, not a raw display string (which would slug to a missing `vocab.clean_mode.*` key and leak English). |
| `clean_intensity_aliases` | `dict[str, str]` | Same, for clean intensity → `quick`/`narrow`/`deep`/`normal`/`standard`. May be empty when the brand's display values already slug to the canonical code. |
| `fan_speed_aliases` | `dict[str, str]` | Same, for suction/fan speed → `quiet`/`gentle`/`standard`/`boost`/`turbo`/`max`. E.g. `{"boostiq": "boost"}`. |
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
    "cancel_detection_states": {"active": "cleaning", "returning": "returning", "paused": "paused"},
    "water_level_aliases": {"quiet": "low", "automatic": "medium", "auto": "medium", "strong": "high"},
    "wash_frequency_mode_aliases": {"by room": "by_room", "room": "by_room", "by time": "by_time", "off": "off", "disabled": "off"},
    "clean_mode_aliases": {"vacuum and mop": "vacuum_mop", "vacuum & mop": "vacuum_mop"},
    "clean_intensity_aliases": {},
    "fan_speed_aliases": {"boostiq": "boost", "boost iq": "boost"},
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
trace. See [porting-guide.md §9](../contributing/porting-guide.md#9-jobrun-segmentor-optional)
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

## 8. `charging` — low-battery-return detection

The charging **state** itself is read from the dedicated `entities.charging`
binary sensor (`core/charging.py`, no substring fallback). This block only
configures the low-battery mid-job return classifier — how the framework
distinguishes "returned to dock because the battery ran low" from a
user-initiated `return_to_base` on a healthy battery.

### Schema

| Field | Type | Purpose |
|-------|------|---------|
| `low_battery_return_task_status` | `str` | Normalized `task_status` string the vacuum reports when it returns to dock specifically to recharge mid-job (Eufy: `"returning to charge"`). Authoritative — no battery gate needed when it matches. Absent: detected only via the generic `returning` vacuum state + threshold. |
| `low_battery_threshold_percent` | `int` | Battery percent at/below which a generic `returning` vacuum state is treated as a low-battery return. Default: `20`. |

### Example

```python
"charging": {
    "low_battery_return_task_status": "returning to charge",
    "low_battery_threshold_percent": 20,
},
```

**UI builder notes:** Charging detection requires a `entities.charging`
binary sensor — surface that requirement near this block. Both fields
here are optional; default `low_battery_threshold_percent` to `20` and
leave `low_battery_return_task_status` blank for brands that don't expose
a distinct return-to-charge `task_status` string.

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
| `debounce_seconds` | `dict[str, float]` | `{}` | Per-event-type cooldown collapsing noisy `dock_status` flips into one counted event. Keys match `triggers`. Also gates the active-job mop-wash observation via `last_mop_wash`. Absent key (or `0`) = no debounce. |
| `action_buttons` | `dict[str, dict]` | `{}` | Resolves the upstream button entity for each dock action (`wash_mop`, `dry_mop`, `stop_dry_mop`, `empty_dust`). Each value: `{"entity_suffixes": [str]}` appended to `button.{object_id}_` (tried first), `{"token_sets": [[str]]}` all-tokens-must-match registry fallbacks. Absent action = reported unavailable. |

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
    "debounce_seconds": {"last_mop_wash": 60},
    "action_buttons": {
        "wash_mop": {"entity_suffixes": ["wash_mop", "mop_wash"], "token_sets": [["wash", "mop"]]},
        "dry_mop": {"entity_suffixes": ["dry_mop", "mop_dry"], "token_sets": [["dry", "mop"]]},
        "stop_dry_mop": {"entity_suffixes": ["stop_dry_mop"], "token_sets": [["stop", "dry", "mop"]]},
        "empty_dust": {"entity_suffixes": ["empty_dust", "empty_dust_bin"], "token_sets": [["empty", "dust"]]},
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
| `source` | `str` | `"entity_attribute"` | Where the room list lives. `"entity_attribute"` (default, Eufy): a live attribute on an HA entity, read synchronously. `"service_response"` (Roborock): the room list exists only in a service-call RESPONSE (`get_maps`); the framework calls the service at the async discovery boundaries, flattens it, and caches it for the sync path (see `rooms/source_refresh.py`). |
| `room_list_entity` | `str` | `"vacuum_entity"` | Which entity exposes the list. Special value `"vacuum_entity"` means read from the vacuum entity itself; otherwise supply a full entity ID. |
| `room_list_attribute` | `str` | – | Attribute name on the entity that contains the list. Expected to be a `list[dict]`. |
| `room_id_key` | `str` | – | Key in each room dict that contains the room ID. Eufy: `"id"`. Roborock: `"segment_id"`. |
| `room_name_key` | `str` | – | Key in each room dict that contains the room name. Usually `"name"`. |
| `maps_service` | `dict` | – | For `source: "service_response"`: the response-returning service that lists maps + rooms, as `{"domain": str, "service": str}`, called with the vacuum entity as target and `return_response=True`. Roborock: `{"domain": "roborock", "service": "get_maps"}`. |
| `maps_rooms_key` | `str` | – | For `source: "service_response"`: key in each map entry of the service response that holds the rooms (may be a `{segment_id_str: name}` mapping, flattened to list-of-dicts). Roborock: `"rooms"`. |
| `map_name_key` | `str` | – | For `source: "service_response"`: key in each map entry that holds the map's identity; the flattened cache is keyed by this value, which must match what `entities.active_map` reports. Roborock: `"name"`. |
| `auto_refresh_on` | `list[str]` | `["vacuum_docked", "active_map_changed", "config_entry_reload"]` | Event triggers that automatically run discovery. Closed enum; see runtime notes below. |
| `auto_refresh_interval_seconds` | `int` | `21600` (6h) | Periodic safety-net discovery interval. `0` disables the floor. |
| `removal_confirmation_passes` | `int` | `3` | Consecutive discovery passes a configured room must be absent from before the framework flags it as removed. Prevents transient API glitches from producing spurious "room removed" notifications. |
| `new_room_confirmation_passes` | `int` | `1` | Consecutive passes a new room must appear in before being flagged for user review. Default `1` surfaces immediately. |

`room_list_entity` / `room_list_attribute` apply only when
`source: "entity_attribute"` (the default); `maps_service` /
`maps_rooms_key` / `map_name_key` apply only when
`source: "service_response"`.

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
| `calibrate_map` (reserved) | `mapping.calibrate_map` | Map calibration stored | Brand-specific future |
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
config, see [07-queue-engine.md](07-queue-engine.md); for worked dispatch
blocks for Eufy, Roborock, Dreame, and Narwal, see
[porting-guide.md §3](../contributing/porting-guide.md#3-the-config-blocks-you-fill-in).

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
| `rooms_field` | `str` | no | Field name for the rooms list / id array. Eufy: `"rooms"`. Roborock/Ecovacs: `"segments"` / `"rooms"`. |
| `passes_max` | `int` | no | Clamp ceiling for collapsed batch passes (flat-id engines). Default `3`. |

### Template selects a dispatch *engine* (and a payload *structure*)

`template` is **load-bearing**: it resolves to a dispatch engine in
`queue/dispatch_engines.py`, and each engine produces a genuinely
different payload **structure** — not just renamed fields. The
`room_fields` rename/value-map vocabulary is shared across all of them;
what differs is how the engine *emits* it:

| Template | Engine | Structure | Per-room fan/water? |
|----------|--------|-----------|---------------------|
| `eufy_room_clean` | `EufyRoomCleanEngine` | **rows** — a list of per-room dicts | yes (per dict) |
| `roborock_segment_clean` | `RoborockSegmentEngine` | **flat ids + batch scalar** — `{segments:[ints], repeat:n}` | no (fan is global) |
| `generic_room_ids` | `GenericRoomIdsEngine` | flat ids + batch scalar (Ecovacs `{rooms:[ints], cleanings:n}`) | no |
| `dreame_room_clean` | `DreameSegmentEngine` | **columns** — positional parallel arrays | yes (per array index) |

Engines also declare a **`job_model`** (see *Job model* below). An
unregistered `template` is rejected at adapter registration
(`registry._validate_adapter`); an absent one falls back to the Eufy
engine (the legacy no-adapter default).

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
`app_segment_clean` command. **Not a list of dicts** — a flat segment-id
list plus a single batch `repeat` scalar (Roborock takes no per-room
fan/water on the wire; fan is global). Per-room passes collapse to the
max requested, clamped to `[1, passes_max]`.

```python
"dispatch": {
    "template": "roborock_segment_clean",
    "service_domain": "vacuum",
    "service_name": "send_command",
    "command": "app_segment_clean",
    "rooms_field": "segments",
    "clean_passes_field": "repeat",
},
```

Generates:

```python
{"command": "app_segment_clean", "params": {"segments": [16, 17], "repeat": 2}}
```

Ecovacs is the same engine via `generic_room_ids` with
`rooms_field: "rooms"`, `clean_passes_field: "cleanings"`,
`command: "spot_area"`.

### Example: `dreame_room_clean`

The Tasshack `dreame_vacuum.vacuum_clean_segment` service takes
**positional parallel arrays** — one index per room — and is the only
shape that carries per-room fan/water *and* passes on the wire. The
engine is the **transpose** of Eufy: same `room_fields` vocabulary, but
emitted as columns (one array per field) instead of rows. `clean_mode`
is global on Dreame (a `select`, not in this payload) → `field_name:
null`; the global-mode pre-call is a send-side concern. Direct envelope
(no `command`).

```python
"dispatch": {
    "template": "dreame_room_clean",
    "service_domain": "dreame_vacuum",
    "service_name": "vacuum_clean_segment",
    "rooms_field": "segments",
    "clean_passes_field": "repeats",
    "room_fields": {
        "fan_speed":   {"field_name": "suction_level",
                        "value_map": {"Quiet": 0, "Standard": 1, "Turbo": 2, "Max": 3}},
        "water_level": {"field_name": "water_volume",
                        "value_map": {"Low": 1, "Medium": 2, "High": 3}},
        "clean_mode":      {"field_name": None},   # global select, off-wire
        "clean_intensity": {"field_name": None},
        "edge_mopping":    {"field_name": None},
        "path_type":       {"field_name": None},
    },
},
```

Generates (direct-merged into the service data):

```python
{"segments": [3, 2], "suction_level": [0, 3], "water_volume": [1, 3], "repeats": [1, 2]}
```

### Example: `generic_room_ids`

The flat-id engine (shared with `roborock_segment_clean`) for any
integration that accepts a list of room IDs plus an optional batch
passes scalar. Per-room **fan/water/mode are dropped** (no wire slot for
them); per-room **passes collapse to one batch value** (`clean_passes_field`,
omitted if set to `null`). Use when no richer brand template fits.

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

### The per-room field vocabulary (`room_fields`)

`room_fields` is the **shared** rename + value-map vocabulary every
engine consumes — what differs is *where* the values land: the Eufy
engine writes them into each per-room dict (rows); the Dreame engine
writes them into positional arrays (columns); the flat-id engines drop
the per-room ones and keep only the id list + batch passes. So the same
`room_fields` block describes fan speed, water level, clean mode, edge
mopping, path type, and clean intensity regardless of the wire shape.

For the Eufy (rows) engine, a per-room dict for a mop-capable job looks like:

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
[porting-guide.md §3](../contributing/porting-guide.md#3-the-config-blocks-you-fill-in).

### Job model (sequencing)

Each engine also declares a **`job_model`**:

- **`atomic_batch`** (every engine today) — one dispatch of a fixed room
  set; finalize when it completes. The entire existing lifecycle path.
- **`sequenced`** — a logical job is an ordered list of phases (e.g.
  Dreame sweep-all → mop-all), each its own dispatch. The engine returns
  the sequence from `build_phases()`; each phase runs as an atomic
  sub-job and **finalizes as its own job record** (one record per phase).
  At the completion hook, `manager.maybe_advance_phase` swaps to the next
  phase (`advance_active_job_phase`) and re-dispatches instead of
  finalizing; the last phase finalizes normally.

`job_model` is a property of the engine, not an adapter-config field —
an adapter selects it implicitly by choosing a `template`. No engine sets
`job_model = "sequenced"` as its *static* default today. But the flat-id
engines (`generic_room_ids` / `roborock_segment_clean`) produce a
**runtime** sequenced job via `build_phases(strict_order=True)`: instead
of one batch phase they emit one single-segment phase per resolved room
in queue order. This is the shipping Roborock **opt-in strict-order**
mode (see the `honors_clean_order` note in §14). Core doesn't read a
static flag to decide sequencing — it treats any phase list of length > 1
as sequenced: `core/manager.py` attaches the phase sequence to the active
job only when `len(_phases) > 1`, and at the completion hook
`maybe_advance_phase` advances to the next phase and re-dispatches instead
of finalizing (the final phase finalizes normally). A future
static-`job_model` adapter — a Dreame sweep-then-mop or always-away
phased-clean — would instead subclass its engine with
`job_model = "sequenced"` + a `build_phases` override, making the sequence
intrinsic to every run rather than a per-run opt-in.

### `dispatch.phase_timing` — strict-order phase watchdog timing

For a sequenced (strict-order) job, each room is a phase dispatched only
once the prior phase docks, and a watchdog settles + verifies + re-dispatches
each phase. `dispatch.phase_timing` lets a brand whose post-dock transient
differs override the per-phase watchdog timing; anything omitted falls back
to the in-core `_PHASE_*` defaults (so Eufy, which declares nothing here, is
byte-identical). Read by `core/manager.py::_phase_timing`.

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `settle_seconds` | `int` | `10` | Pause after a phase is queued before the watchdog first verifies it started. |
| `dock_settle_seconds` | `int` | `45` | Longer settle when the prior phase has just docked (the device ignores a clean dispatched the instant it docks). |
| `verify_seconds` | `int` | `90` | Window to confirm the phase actually started before re-dispatching. |
| `confirm_seconds` | `int` | `45` | Window to confirm the phase completed (docked) before advancing. |
| `poll_seconds` | `int` | `5` | Watchdog poll interval. |
| `max_attempts` | `int` | `3` | Re-dispatch attempts per phase before giving up. |

```python
"dispatch": {
    # ...outer wrapper fields...
    "phase_timing": {
        "settle_seconds": 10,
        "dock_settle_seconds": 45,
        "verify_seconds": 90,
        "confirm_seconds": 45,
        "poll_seconds": 5,
        "max_attempts": 3,
    },
},
```

### Implementation status

The full dispatch path — payload **structure**, per-room field
vocabulary, the service-call envelope, **and** the job model — is
adapter-driven via the dispatch-engine seam (`queue/dispatch_engines.py`).
`template` resolves to an engine; the engine's `build_payload` /
`build_phases` produce the structure; `queue/queue_engine.py::
build_room_clean_payload()` remains the shared *resolver* (profile
resolution + capability gating + canonical `resolved_rooms`) that the
non-Eufy engines reuse and reshape. The start path
(`planning/run_plan.py::_build_effective_start_plan` →
`_build_dispatch_phases`) and `core/manager.py::start_selected_rooms`
both go through the engine; the shared `manager._dispatch_clean_payload`
builds the wrapped (`{command, params}`) or direct (`{**payload}`)
envelope. Defaults preserve byte-for-byte Eufy behavior when `dispatch`
is absent or partial.

**Done as of the dispatch + sequencing refactor** (was previously listed
as future work): structurally-different payload shapes (flat-id+scalar,
parallel arrays), `template` being load-bearing, and the sequenced job
model.

**Also done — send-side pre-call hooks are now config-driven** (was
previously listed as brand-aware framework code). Two `dispatch` blocks
cover both timings:

- `dispatch.global_pre_calls` — one value per run, pushed **before** an
  atomic dispatch, for a setting the device exposes only globally
  (Roborock/Ecovacs global `set_fan_speed`, Dreame global
  `select.cleaning_mode`). Each entry picks the run value from the
  selected rooms' canonical field by **max-wins over `rank`**, maps it via
  optional `value_map`, and calls the declared `service`. Best-effort (a
  failed pre-call never aborts the run). Run by
  `core/manager.py::_run_global_pre_calls`.
- `dispatch.per_room_live_settings` — pushed **mid-run** as the robot
  enters each room (driven by the native current-room rollover, so the
  device keeps one path-optimized run — no per-room re-dispatch). Each
  entry names a canonical room field plus a side service call (with an
  optional `options_key` vocabulary guard). Applied by
  `jobs/active_job.py::ActiveJobTracker.apply_per_room_live_settings` (and
  `apply_per_room_live_settings_awaited` for the strict-order phase path).

**What still remains brand-aware in framework code** (a PR, not config):

- `vacuum.clean_area` (`ha_clean_area`) — a service **target**
  (`target: {area_id: [...]}`), not a data payload. Needs engines to own
  the *full* service call rather than just the payload dict.
- `live_queue` job model — mid-job room injection (dequeue already works).
- A new canonical field outside the six in `room_fields`.

**UI builder notes:** Render `template` as a dropdown that selects a
per-template default for the other fields; let the user override any
field via a "customise" toggle. A "dry-run" button that constructs the
payload for a sample room selection and prints the service call (without
executing) is the highest-value debugging affordance.

---

## 13a. `mapping` — pluggable MAP segmenter engine selection

Selects which **map** segmenter engine drives image-segment analysis for
this adapter — the subsystem that turns a stored map *image* into
polygonal room overlays. (The separate **job/run** segmenter that derives
per-room boundaries from a run's *counter signal* is configured by the
[§13a.1 `job_segmenter`](#13a1-job_segmenter--pluggable-jobrun-segmenter-engine--threshold-tuning)
block — don't conflate the two.) The framework's `MapSegmenter` registry
holds the engines; the adapter declares which one to use by name. Engines
vary in what kind of input they consume (image bytes vs. structured wire
data vs. nothing at all) but produce the same canonical
`SegmentationResult`, so the rest of the framework doesn't have to know
which engine is selected.

See [26-eufy-segmentor.md §2](26-eufy-segmentor.md#2-the-segmenter-engine-contract-the-pattern)
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
new name (see [26-eufy-segmentor.md §10](26-eufy-segmentor.md#10-writing-a-segmenter-for-a-new-brand)).

### `segmenter_tuning` *(required when `mapping` is present, dict)*

Engine-specific knobs. **Each engine owns its own tuning schema**
and validates the dict in its `validate_tuning(tuning) -> list[str]`
method — unknown keys produce non-blocking warnings, malformed
values produce blocking errors. The framework's `_validate_adapter`
delegates to the engine's validator at registration time.

For `eufy_cv_v1`, the accepted keys mirror the kwargs of
`detect_room_segments(...)` (see [11-mapping-system.md §2.1](11-mapping-system.md#21-input)):

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

## 13a.2 `map_state_source` — read the provider's own map segmentation

Where [§13a `mapping`](#13a-mapping--pluggable-map-segmenter-engine-selection)
turns a stored map *image* into overlays, `map_state_source` reads the
**provider's own** map segmentation — the device's authoritative room
data — into normalized, VA-owned room bboxes plus dock / robot anchors.
This makes room regions, current-room, and mascot anchors **auto-derived**
rather than hand-composed, and (for Eufy) immune to the per-session raw
coordinate-frame re-basing that makes absolute robot coordinates
non-comparable across sessions. The Eufy adapter declares it against
eufy-clean's decoded map; brands whose in-memory map is already
frame-fresh (Roborock) omit it.

The whole block is optional. Absent → no provider-map read; trace-based
room bounds and the CV image segmenter keep working unchanged.

### Schema

| Field | Type | Purpose |
|-------|------|---------|
| `backend` | `str` | Which read strategy to use. Eufy: `"storage"` (eufy-clean persists its decoded map to an HA `Store` file). |
| `identifier_domain` | `str` | Device-registry identifier domain used to resolve the device (Eufy: `"robovac_mqtt"`). |
| `store_key` | `str` | `Store` file key, with `{device_id}` filled from the `(identifier_domain, <serial>)` device-registry identifier (Eufy: `"robovac_mqtt.{device_id}"`). |
| `store_version` | `int` | Expected store wrapper version. A mismatch is treated as unavailable (re-point this number, don't rewrite, if the provider bumps it). |
| `present_requires_live_map_image` | `bool` | When `True`, presence is gated on the live-map camera artifact (the same gate as the live backdrop), so an older or plain install (no live-map camera) resolves to "not present" and the feature hides. |
| `live_pose` | `dict` | In-memory live-pose source — the fresh moving overlays (robot / dock / trail) read from the provider's live coordinator rather than the save-throttled `.storage` snapshot. Keys: `hass_data_domain`, `robot_pixel_attrs`, `dock_pixel_attrs`, `trail_pixel_attrs`, `heading_attrs` (each an ordered attr-name list tried in turn; absence → no override, stays on `.storage`). |
| `memory` | `dict` | In-memory `MapData` source — the same live coordinator also holds the full decoded map (fresher than `.storage`, loop-safe). Keys: `hass_data_domain`, `mapdata_attrs` (and optional per-field remap `field_attrs`). |

### Example (from the Eufy adapter)

```python
"map_state_source": {
    "backend": "storage",
    "identifier_domain": "robovac_mqtt",
    "store_key": "robovac_mqtt.{device_id}",
    "store_version": 1,
    "present_requires_live_map_image": True,
    "live_pose": {
        "hass_data_domain": "robovac_mqtt",
        "robot_pixel_attrs": ["_robot_pixel", "robot_pixel"],
        "dock_pixel_attrs":  ["_dock_pixel", "dock_pixel"],
        "trail_pixel_attrs": ["_robot_trail", "robot_trail"],
        "heading_attrs":     ["_robot_angle", "robot_angle", "_robot_heading"],
    },
    "memory": {
        "hass_data_domain": "robovac_mqtt",
        "mapdata_attrs": ["_map_data", "map_data"],
    },
},
```

### Where the framework reads it

- `mapping/map_source_coordinator.py::MapSourceCoordinator.async_refresh_map_state_source`
  — pre-warms the normalized read (storage / memory backends + the live-pose
  layer) into `manager._map_state_source_cache`. Constructed on the manager
  (`self.map_source = MapSourceCoordinator(manager=self)`); the manager exposes
  thin delegators (`async_refresh_map_state_source`, the live-pose poll, the
  compare probe). The on-loop dashboard snapshot composer reads the cached
  `result` back into `get_dashboard_snapshot`.

---

## 13a.3 `map_render` — VA-owned client-side map render

A small block declaring **how the card sources the raster** for its own
full-grid map backdrop (no server-side render dependency), so the overlays
align perfectly and the look stays themeable. `format` names the decode the
card applies; the source pointer (`store_key` / `identifier_domain` /
`store_version`) is **reused from
[`map_state_source`](#13a2-map_state_source--read-the-providers-own-map-segmentation)**
— no duplicate schema. Roborock omits this block (its HA-core image render is
already frame-matched); absence → the card's "VA-rendered map" backdrop source
is hidden for that brand, and `supports_va_render` is `False`.

### Schema

| Field | Type | Purpose |
|-------|------|---------|
| `format` | `str` | Names the raster decode the card applies (Eufy: `"eufy_room_pixels_v1"`). The source pointer is inherited from `map_state_source`. |

### Example (from the Eufy adapter)

```python
"map_render": {
    "format": "eufy_room_pixels_v1",
},
```

### Where the framework reads it

- `mapping/map_source_coordinator.py::MapSourceCoordinator.async_get_map_render_data`
  — fetches the card's own-render raster (delegated from
  `core/manager.py::async_get_map_render_data`).
- `core/manager.py::get_dashboard_snapshot` — reads the **presence** of this
  block to gate `supports_va_render` (`isinstance(adapter_cfg.get("map_render"), dict)`).

---

## 13a.1 `job_segmenter` — pluggable JOB/run segmenter engine + threshold tuning

Selects the **job/run** segmenter engine — the brand-specific detection
of per-room boundaries from a *run's progress signal* — and carries the
gap/area/cadence thresholds that detection uses. This is a **different
subsystem from [§13a `mapping`](#13a-mapping--pluggable-map-segmenter-engine-selection)**:
the map segmenter reads a map *image* and produces polygonal overlays;
the job segmenter reads the `cleaning_time` / `cleaning_area` *counters*
as a run progresses (Eufy has no native "current room" and its
coordinates drift, so the counter-plateau signal is the reliable
transition cue) and produces ordered per-room cleaning segments.

The seam mirrors [§13a `mapping`](#13a-mapping--pluggable-map-segmenter-engine-selection)
and the dispatch-engine seam: the framework's `JobSegmenter` registry
(`learning/job_segmenter_engines.py::_JOB_SEGMENTER_ENGINES`) holds the
engines; the adapter declares which one to use by name. All three
counter-segmentation consumers — **live rollover, external-run ingest,
and learned history** — resolve their engine *and* their thresholds from
this one block.

`job_segmenter.tuning` is the **single in-code source** of the five
gap/area/cadence thresholds. They previously lived inside
`live_transition`; they have moved here (see the note in
[§13b](#13b-live_transition--live-current-room-rollover-orchestration)).

### Schema

```python
"job_segmenter": {
    "engine":  str,                  # required when `job_segmenter` present
    "tuning":  dict[str, float],     # optional; validated by the engine (may be partial)
}
```

### `engine` *(required when `job_segmenter` is present, str)*

One of the names registered in `learning/job_segmenter_engines.py`
(`known_job_engine_names()`). Currently:

| Name | What it does |
|---|---|
| `eufy_counter_v1` | Counter-plateau detection over `cleaning_time` / `cleaning_area`. Delegates verbatim to the `counter_segmentation` primitives, so the Eufy path is byte-for-byte identical to the pre-engine code. Default for adapters with no native room-transition telemetry. |
| `noop_job_fallback` | Every stage returns `[]` — no boundaries. For a future brand that emits no segmentable signal. Registered for completeness; **not** the fallback. |

**Fallback is the Eufy engine, not noop** — unlike [§13a
`mapping`](#13a-mapping--pluggable-map-segmenter-engine-selection),
which falls back to `noop_fallback`. `get_job_segmenter_engine()` returns
`eufy_counter_v1` for an absent *or* unknown name (an unknown non-empty
name is logged as a warning), because the framework's historical default
(no adapter registered) is Eufy counter segmentation, and live rollover +
learned history must keep working byte-for-byte in that case. A noop
fallback would silently stop live rollover. A brand with native
per-room telemetry registers its own engine here (implementing
`find_candidates` / `build_segments` to return the same
`JobBoundaryCandidate` / `JobSegment` shape).

> **What the engine owns vs. what the framework owns.** The pipeline is
> three stages — `find_candidates → select_active → build_segments`. The
> engine owns the two brand-specific stages (`find_candidates`,
> `build_segments`) plus the legacy one-shot composition
> (`segment_legacy`). **`select_active` stays a framework function**
> (`counter_segmentation.select_active`) — it is pure ranking/filtering
> over the candidate *shape*, so the external-review wizard's count/toggle
> re-selection logic is uniform across brands. The Eufy *kind* literals
> (`wash_plateau` / `transit` / `area_jump` / `weak`) live at the
> Eufy-specific call sites, not in an indirection layer — a future brand
> with a different kind vocabulary supplies its own engine *and* its own
> kind literals there.

### `tuning` *(optional when `job_segmenter` is present, dict)*

The five gap/area/cadence thresholds. **The engine owns the schema** and
validates the dict in `validate_tuning(tuning) -> list[str]` (unknown
keys and non-positive values are flagged); the framework's
`_validate_adapter` delegates to it at registration time. The dict may be
partial — the engine merges it over its own `DEFAULT_TUNING` (for
`eufy_counter_v1`, defined *by reference* to the `counter_segmentation`
module constants, so it can't drift from the primitives).

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `gap_delayed_s` | `float` | `35.0` | Lower gap bound separating a `weak`/delayed blip from a real transition candidate. |
| `gap_transit_s` | `float` | `60.0` | Start of the `transit` band — a flat-area inter-room hop of 60-90 s. |
| `gap_plateau_s` | `float` | `90.0` | Gap at/above which a blip is a `wash_plateau` (the dock-wash dwell). |
| `area_jump_m2` | `float` | `2.0` | Forward cleaned-area rise (m²) that marks an `area_jump` candidate. |
| `cadence_s` | `float` | `30.0` | Expected counter-sample cadence; normalizes gap math against the polling interval. |

### Example (from the Eufy adapter)

```python
"job_segmenter": {
    "engine": "eufy_counter_v1",
    "tuning": {
        "gap_delayed_s": 35.0,
        "gap_transit_s": 60.0,
        "gap_plateau_s": 90.0,
        "area_jump_m2": 2.0,
        "cadence_s": 30.0,
    },
},
```

### Where the framework reads it

- `jobs/active_job.py::ActiveJobTracker._live_boundary_count` (live
  rollover) — resolves the engine + tuning from this block and calls
  `engine.find_candidates(...)` + the framework `select_active(...)`
  (enabled), or `engine.segment_legacy(...)` (the `live_transition.enabled`
  kill-switch).
- `learning/external_ingest.py` (`build_pending_record` /
  `resegment_pending_record` / `_mark_candidate_confidence`) — resolves
  the engine via `_resolve_engine_tuning(vacuum_entity_id)` and calls
  `engine.find_candidates` / `engine.build_segments`; `select_active`
  stays a direct framework import. (The persisted v2 record's
  `gap_transit_s` field is unchanged at `60.0`; only its *provenance*
  moved — from the module constant to the resolved engine tuning.)
- `learning/history_store.py::_build_transit_blocks` (learned history) —
  resolves the engine from the adapter (optional `vacuum_entity_id` param;
  absent → the Eufy fallback) and calls `engine.segment_legacy(...)`.

> **No `ADAPTER_CONFIG_SCHEMA` entry yet.** `job_segmenter` (like
> `live_transition` and `room_profiles`) has no entry in
> `adapters/config_schema.py`; the schema walker iterates *schema* keys,
> so extra blocks are simply ignored by it. Validation of this block lives
> in `registry._validate_adapter` (engine required when the block is
> present, must be a known engine, tuning validated by the engine). Schema
> entries are a deferred follow-up.

**UI builder notes:** Advanced section — collapse by default and pre-fill
the Eufy defaults. `engine` is a dropdown over `known_job_engine_names()`;
the five `tuning` values are timing thresholds in seconds (plus one area
delta in m²).

---

## 13a.4 `room_attribution` — pluggable room-attribution engine

The **4th pluggable engine seam** (alongside `mapping`, `job_segmenter`,
and the dispatch engines). It selects the engine that recovers **which
managed rooms an external (app-started, undispatched) run cleaned**, from
a per-tick pose time-series (current-room + anchor + cleaning-area). This
is a **different axis from [§13a.1 `job_segmenter`](#13a1-job_segmenter--pluggable-jobrun-segmenter-engine--threshold-tuning)**:
the job segmenter owns time/area *boundaries*; room attribution owns room
*identity*.

The whole block is optional and validated at registration. Its
**run-active consumers are still dormant** (the run-active pose sampler /
finalize wiring is pending), so it is declared now to make the engine
selection explicit and validated; the seam, engines, validation, and
tests already exist.

### Schema

```python
"room_attribution": {
    "engine":  str,                  # required when `room_attribution` present
    "tuning":  dict[str, float],     # optional; validated by the engine (may be partial)
}
```

### `engine` *(required when `room_attribution` is present, str)*

One of the names registered in `learning/room_attribution_engines.py`
(`known_room_attribution_names()`). Currently:

| Name | What it does |
|---|---|
| `eufy_anchor_winding_v1` | Segments by `current_room`, drops transit by path-winding, and separates cleaned vs. parked-dock rooms by the `cleaning_area` (swept m²) delta. Default for adapters with no native external-run room signal. |
| `noop_room_attribution` | Returns no attribution. Declare it to explicitly disable auto-attribution. |

**Fallback is the Eufy engine, not noop** — `get_room_attribution_engine()`
returns `eufy_anchor_winding_v1` for an absent *or* unknown name (an
unknown non-empty name is logged). `registry._validate_adapter` requires
`engine` when the block is present, rejects an unknown name, and validates
the tuning via the engine.

### `tuning` *(optional when `room_attribution` is present, dict)*

Engine-owned thresholds (`eufy_anchor_winding_v1`):
`wind_transit`, `dwell_min_s`, `swept_area_min_m2`, `interval_s`.

### Example (from the Eufy adapter)

```python
"room_attribution": {
    "engine": "eufy_anchor_winding_v1",
    "tuning": {
        "wind_transit": 1.5,
        "dwell_min_s": 25.0,
        "swept_area_min_m2": 0.5,
        "interval_s": 2.0,
    },
},
```

### Where the framework reads it

- `adapters/registry.py::_validate_adapter` — validates the block at
  registration (engine required + known, tuning validated by the engine).
- The run-active consumers (pose sampler + finalize attribution) are
  **pending wiring**; until they land, this block is validated and
  selectable but not yet read during a run.

> **No `ADAPTER_CONFIG_SCHEMA` entry yet.** Like `job_segmenter`,
> `live_transition`, and `room_profiles`, `room_attribution` has no entry
> in `adapters/config_schema.py` (the schema walker iterates schema keys,
> so extra blocks are ignored). Validation lives in
> `registry._validate_adapter`. Schema entries are a deferred follow-up.

**UI builder notes:** Advanced section — collapse by default and pre-fill
the Eufy defaults. `engine` is a dropdown over
`known_room_attribution_names()`; the four `tuning` values are detection
thresholds (winding ratio, dwell seconds, swept-area m², sample interval).

---

## 13b. `live_transition` — live current-room rollover orchestration

Configures the **orchestration** of the live current-room rollover that
runs on the 5-second job-progress tick while a job is in flight. The
vacuum reports no "current room" and its raw coordinates drift, so the
cleaning-counter plateau signal is the reliable transition cue.

This block carries **only the live-specific orchestration knobs** —
`{enabled, rollover_kinds, native_transition_source}`. The
gap/area/cadence **thresholds** that detection uses are **not here**: they
moved to [§13a.1 `job_segmenter.tuning`](#13a1-job_segmenter--pluggable-jobrun-segmenter-engine--threshold-tuning),
the single in-code source now read by live rollover, external ingest, and
learned history alike. The detection itself routes through the adapter's
pluggable job-segmenter engine (resolved in `_live_boundary_count`); this
block decides only *whether* rollover runs and *which boundary kinds*
advance the live queue.

This is **distinct from the finalize/history segmentation path**, which
is byte-identical and reaches the same engine via `segment_legacy`.
`live_transition` only governs the in-run rollover inside
`ActiveJobTracker._maybe_roll_current_room_by_timing`.

**Every default equals the prior hardcoded constant**, so Eufy is
byte-identical *except* it now also advances on a `transit` boundary —
a 60-90 s flat-area inter-room hop the legacy live path discarded (the
fix for live under-roll). `enabled: false` is a kill-switch back to the
legacy one-shot segmentation (`engine.segment_legacy`, the
wash/area_jump-only path).

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `enabled` | `bool` | `True` | Master switch. `False` reverts the live path to the legacy one-shot `engine.segment_legacy` (wash/area_jump-only) composition. |
| `rollover_kinds` | `list[str]` | `["wash_plateau", "transit", "area_jump"]` | Which candidate kinds count as a live rollover boundary. Eufy includes `transit`; the legacy set was `{wash_plateau, area_jump}`. |
| `native_transition_source` | `bool` | `False` | A brand that exposes a real per-room signal sets `True` to follow the device's native current-room directly (Eufy's counter-plateau inference is the fallback). **Consumed** by `jobs/active_job.py::_maybe_roll_current_room_by_native_signal` — **Roborock sets `True`** (its `_current_room` sensor); suppressed for sequenced/strict-order jobs so a parked dock room isn't phantom-completed. |

> **The five threshold keys are gone.** `gap_delayed_s`, `gap_transit_s`,
> `gap_plateau_s`, `area_jump_m2`, and `cadence_s` were **removed** from
> `live_transition` (and from the module-level `_LIVE_TRANSITION_DEFAULTS`
> in `jobs/active_job.py`). They now live in
> [`job_segmenter.tuning`](#13a1-job_segmenter--pluggable-jobrun-segmenter-engine--threshold-tuning).
> Any older doc or config that put them under `live_transition` is stale.

### Example (from the Eufy adapter)

```python
"live_transition": {
    "enabled": True,
    "rollover_kinds": ["wash_plateau", "transit", "area_jump"],
    "native_transition_source": False,
},
```

### Where the framework reads it

- `jobs/active_job.py::ActiveJobTracker._live_transition_config` — merges
  this block over the module-level `_LIVE_TRANSITION_DEFAULTS` (only
  `enabled` / `rollover_kinds` / `native_transition_source`; an absent
  block, or a non-Eufy adapter, behaves exactly as the defaults).
- `jobs/active_job.py::ActiveJobTracker._live_boundary_count` — reads
  `enabled` (kill-switch) and `rollover_kinds` (the `select_active` kind
  filter); the **thresholds** it feeds the engine come from
  `job_segmenter.tuning`, not from this block.

**UI builder notes:** Advanced section — collapse by default and pre-fill
the Eufy defaults. Render `rollover_kinds` as a multi-select over the
closed candidate-kind enum (`wash_plateau`, `transit`, `area_jump`,
`weak`). `native_transition_source` is a single toggle (Roborock `True`, Eufy
`False`). The detection *thresholds* are edited in the
[§13a.1 `job_segmenter`](#13a1-job_segmenter--pluggable-jobrun-segmenter-engine--threshold-tuning)
form, not here.

---

## 13c. `anomaly` — live anomaly ratios

Two ratio thresholds for the **live** job-progress anomaly signals.
Anomaly detection — reading these ratios, computing the stall /
running_long tiers, and emitting the `EVENT_STALL_DETECTED` /
`EVENT_ROOM_SKIPPED` events — lives in
`jobs/active_job.py::ActiveJobTracker.detect_run_anomalies` (the tracker
owns the active-job dict and the per-job event-dedup state). The
manager's `get_job_progress_snapshot` delegates to it and surfaces the
result in the snapshot. Both defaults match the tracker's hardcoded
fallbacks, so Eufy is unchanged.

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `running_long_ratio` | `float` | `1.5` | Soft tier. The current room is flagged `running_long` once its elapsed time reaches `running_long_ratio ×` its learned threshold (and below `stall_ratio ×`, with no pending transition). Surfaces a warning ring on the card chip; disjoint from the hard stall. |
| `stall_ratio` | `float` | `2.0` | Hard tier. The existing stall threshold — the current room has run `stall_ratio ×` its estimate. |

The snapshot returns `running_long`, `running_long_ratio`, and
`running_long_room_id` alongside the existing stall fields; the live
timeline entries gain a `running_long` flag (and a `skipped` flag, fired
once per skipped room as `EVENT_ROOM_SKIPPED`).

### Example (from the Eufy adapter)

```python
"anomaly": {
    "running_long_ratio": 1.5,
    "stall_ratio": 2.0,
},
```

### Where the framework reads it

- `jobs/active_job.py::ActiveJobTracker.detect_run_anomalies` — reads both
  ratios from the `anomaly` block with the defaults above as fallbacks;
  computes the `running_long` / stall tiers and fires the one-shot
  `EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED` events.
- `core/manager.py::get_job_progress_snapshot` — delegates to
  `detect_run_anomalies` and surfaces its fields in the snapshot.

**UI builder notes:** Advanced section. Two numeric inputs constrained to
`running_long_ratio < stall_ratio` (a softer tier below the hard stall);
pre-fill `1.5` / `2.0`.

---

## 13d. `room_profiles` — adapter-sourced room-profile vocabulary

The default room-profile catalog — the built-in profile presets, the
custom-profile template, legacy-name aliases, and the per-floor-type
fan/water defaults — that drive per-room dispatch settings. The in-code
constants in `profiles/room_profiles.py` remain the framework **default**
catalog (and the source of `_PROTECTED_ROOM_PROFILE_NAMES`, bound at
module load — untouched by this block); declaring `room_profiles` lets an
adapter **override any subset** of that vocabulary per-vacuum.

`resolve_profile_catalog(block)` (in `profiles/room_profiles.py`) merges
this block over the in-code constants **per key** — a `None`/empty block
returns the in-code defaults verbatim, so a vacuum without the block (and
Eufy, which declares it *by reference* to the in-code constants) resolves
byte-identically. The Eufy adapter declares it so room resolution is
adapter-sourced and a future brand can inline its own vocabulary.

### Schema

All keys optional; an absent key inherits the in-code default for that
key.

| Field | Type | In-code default | Purpose |
|-------|------|-----------------|---------|
| `default_profile` | `str` | `DEFAULT_ROOM_PROFILE_NAME` (`"vacuum_quick"`) | Profile name a newly-discovered room gets, and the fallback when a requested name is unknown. |
| `builtins` | `dict[str, dict]` | `BUILT_IN_ROOM_PROFILES` | The built-in profile presets (`vacuum_quick`, `vacuum_deep`, `vacuum_mop_quick`, `vacuum_mop_deep`), each a `ProfileRecord`. |
| `custom_template` | `dict` | `DEFAULT_CUSTOM_ROOM_PROFILE` | Template for the editable user profile slot (`user_1`). |
| `legacy_aliases` | `dict[str, str]` | `LEGACY_PROFILE_ALIASES` | Maps retired profile names to current ones (e.g. `vacuum_standard → vacuum_quick`). |
| `floor_type_water_defaults` | `dict[str, str]` | `FLOOR_TYPE_WATER_DEFAULTS` | Per-floor-type water level applied when a room has no explicit override. |
| `floor_type_fan_defaults` | `dict[str, str]` | `FLOOR_TYPE_FAN_DEFAULTS` | Per-floor-type fan speed (carpet pile heights). |
| `normalize_defaults` | `dict` | `DEFAULT_CUSTOM_ROOM_PROFILE` | Per-key fallbacks `normalize_room_profile()` uses to fill missing profile fields. |

### Example (from the Eufy adapter)

The Eufy adapter declares the block **by reference** to the in-code
constants (no duplication, byte-identical):

```python
from ...profiles.room_profiles import (
    BUILT_IN_ROOM_PROFILES, DEFAULT_CUSTOM_ROOM_PROFILE,
    DEFAULT_ROOM_PROFILE_NAME, FLOOR_TYPE_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS, LEGACY_PROFILE_ALIASES,
)

"room_profiles": {
    "default_profile": DEFAULT_ROOM_PROFILE_NAME,        # "vacuum_quick"
    "builtins": BUILT_IN_ROOM_PROFILES,
    "custom_template": DEFAULT_CUSTOM_ROOM_PROFILE,
    "legacy_aliases": LEGACY_PROFILE_ALIASES,
    "floor_type_water_defaults": FLOOR_TYPE_WATER_DEFAULTS,
    "floor_type_fan_defaults": FLOOR_TYPE_FAN_DEFAULTS,
    "normalize_defaults": DEFAULT_CUSTOM_ROOM_PROFILE,
},
```

### Where the framework reads it

- **Dispatch path** (wired) —
  `queue/queue_engine.py::build_room_clean_payload` resolves the catalog
  via `resolve_profile_catalog(get_adapter_config(...)["room_profiles"])`
  and threads it into `resolve_room_profile_for_room(...)` +
  `apply_capability_gate(...)`, so per-room dispatch settings are
  adapter-catalog-sourced. Every resolver in `profiles/room_profiles.py`
  takes an optional `catalog` param (default `None` → the in-code
  constants).

> **Deliberate boundary — documented honestly.** The **global/singleton
> profile editor** (`profiles/manager.py`: `get_room_profiles` /
> `_finalize_room_update` / `_match_profile_from_fields`) and the pure
> room-builder defaults (`rooms/room_manager.py::build_managed_rooms`;
> `room_entities` display fallback) lack per-vacuum context, so they call
> the resolvers with `catalog=None` and use the **framework default**
> catalog. This is byte-identical for Eufy; a second brand's editor UI
> would show framework defaults until threaded — a documented follow-up.

> **No `ADAPTER_CONFIG_SCHEMA` entry yet.** Like `job_segmenter` and
> `live_transition`, `room_profiles` has no entry in
> `adapters/config_schema.py` (the schema walker iterates schema keys, so
> extra blocks are ignored). `registry._validate_adapter` carries a light
> validation rule: the block must be a dict, `default_profile` a string,
> and each of `builtins` / `custom_template` / `legacy_aliases` /
> `floor_type_water_defaults` / `floor_type_fan_defaults` /
> `normalize_defaults` a dict when present. Schema entries are a deferred
> follow-up.

**UI builder notes:** Advanced section — most ports inherit the framework
defaults and declare nothing here. A `ProfileRecord` editor (the same one
the room editor uses) seeds `builtins` / `custom_template`; the two
floor-type maps are key-value editors keyed by the canonical floor types
(`hardwood`, `laminate`, `tile`, `marble`, `carpet_low_pile`,
`carpet_high_pile`).

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
position_lock_reliable     rooms_unique_per_job       honors_clean_order
supports_room_profiles
```

> `supports_base_station` and `supports_map_bounds` are **not** capability
> schema keys — no adapter declares them and they are absent from
> `adapters/config_schema.py`. They are **snapshot-derived** signals; see the
> note below.

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
    # Eufy re-bases the raw coordinate frame each session, so cross-session
    # bounds geometry is untrusted; the room detector only uses position/bounds
    # when this is True (Eufy = False). See 10-learning-system / 26-eufy-segmentor.
    "position_lock_reliable": False,
    # A room is cleaned at most once per job (no vacuum-then-mop whole-home mode),
    # so the external-run review card hard-blocks an already-picked room. A brand
    # whose vac-then-mop pass visits each room twice sets this False.
    "rooms_unique_per_job": True,
},
```

> **Roborock-introduced behavioral flags (Eufy omits → the defaults, so Eufy is
> unchanged).** Both describe firmware behavior an entity probe can't see:
>
> - `honors_clean_order` (default `True`) — `False` for a path-optimizing brand
>   (the S6). Gates the opt-in **strict-order** sequenced-clean mode and the
>   run-start "order is advisory" note. Read in `planning/run_plan.py`.
> - `supports_room_profiles` (default `True`) — `False` drops per-room profile
>   templates (the S6: mop unsettable, passes global).
>
> **`supports_base_station` / `supports_map_bounds` are not capability flags —
> they are snapshot-DERIVED** in `core/manager.py::get_dashboard_snapshot`
> (lines 3648-3661), not read from the `capabilities` block (no adapter declares
> them):
>
> - `supports_base_station` = `bool(dock_events.enabled)` OR any of
>   `supports_mop_wash` / `supports_mop_dry` / `supports_empty_dust` /
>   `supports_station_water`. Eufy (X10 dock) resolves `True`; the Roborock S6
>   (no dock caps) resolves `False`.
> - `supports_map_bounds` = the adapter's `mapping.segmenter_engine` is present
>   and not `"noop_fallback"`. Eufy (`"eufy_cv_v1"`) resolves `True`; the S6
>   (`"noop_fallback"`) resolves `False`.
>
> Both default to **shown** when the derivation is absent, and gate the card's
> Base Station / Map Bounds tabs — but via the derivation, not an
> adapter-declared boolean.
>
> The remaining Roborock-introduced keys live in their own blocks. Two are
> documented in §13 above: `dispatch.per_room_live_settings` (under
> [Implementation status](#implementation-status)) and
> [`dispatch.phase_timing`](#dispatchphase_timing--strict-order-phase-watchdog-timing).
> The rest are documented in context in
> [29-roborock-adapter](29-roborock-adapter.md):
> `completion.require_job_active_clear`; `dispatch.{resolve_live_ids_by_slug,
> params_as_list, passes_is_global}`; and
> `mapping.live_map_image_entity_pattern`. Threading each into its block table
> here is a deferred polish follow-up.

**UI builder notes:** Render as a grid of toggle switches. Pre-fill
from entity-presence detection (the form already knows which entities
the user filled in) and let the user override if they know better.

---

## 14b. `settings_selects` — external-run setting recovery

The global `select` entities that mirror the **current room's** per-room settings
while a job runs. We dispatch these for internal jobs but never read them back;
for an **app-started (external) run** they are the only window into what was set
per room (see [28-external-run-ingestion](28-external-run-ingestion.md)).

Optional. Maps a canonical setting key to `{entity_id, value_map}`:

```python
"settings_selects": {
    "clean_mode": {
        "entity_id": "select.alfred_cleaning_mode",
        "value_map": {"vacuum and mop": "vacuum_mop", "vacuum": "vacuum", "mop": "mop"},
    },
    "fan_speed":       {"entity_id": "select.alfred_suction_level",      "value_map": None},
    "water_level":     {"entity_id": "select.alfred_water_level",        "value_map": None},
    "clean_intensity": {"entity_id": "select.alfred_cleaning_intensity", "value_map": None},
},
```

- `value_map` (optional, lower-cased lookup) normalizes raw firmware strings to
  the canonical room-setting vocabulary; absent → the raw select state is kept.
- Entries with a `None`/absent `entity_id`, or an unavailable state, are skipped.
- `edge_mopping` is **not** listed — it is a dispatch-only payload field with no
  readback entity, so the user supplies it in the review card.

---

## 15. `maintenance_components` — replacement counter catalog

Catalog of components the firmware exposes as replacement counters,
plus per-component display metadata and interval bounds.

### Schema

Top-level is `dict[component_id, ComponentEntry]`. Each entry:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `sensor_suffix` | `str \| None` | yes | Full suffix appended to `sensor.{object_id}_` to form the counter sensor entity ID (e.g. `"filter_remaining"` → `sensor.{object_id}_filter_remaining`). `None` when the component has no own counter and sources only via `proxy_for`. |
| `proxy_for` | `str \| None` | no | Component ID whose sensor this component sources from when present, falling back to this component's own `sensor_suffix`. Used when firmware shares a counter between components (e.g. swivel_wheel proxies filter). |
| `reset_button` | `dict` | no | Resolves the upstream replacement-counter reset button. `{"entity_suffixes": [str]}` appended to `button.{object_id}_` (tried first), `{"token_sets": [[str]]}` all-tokens-must-match registry fallbacks. Absent = no reset button. |
| `default_interval_hours` | `float` | yes | Manufacturer guide recommendation. Reference anchor for the user's configured interval. |
| `max_interval_hours` | `float` | yes | Ceiling for user-configured interval override. |
| `label` | `str` | yes | Human-readable component name for display. |
| `icon` | `str` | yes | MDI icon string. |

### Example

```python
"maintenance_components": {
    "filter": {
        "sensor_suffix": "filter_remaining",
        "proxy_for": None,
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "side_brush": {
        "sensor_suffix": "side_brush_remaining",
        "proxy_for": None,
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Side Brush",
        "icon": "mdi:broom",
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

Physical water-tank dimensions per model, plus the optional flow-rate /
margin tuning the estimator reads. The tank dimensions are **pure
measurements — no logic**; the estimator reads them to convert
tank-percent deltas into ml. The tuning keys (added so a non-Eufy dock
can carry its own flow rates and warning margin) all **default to the
Eufy-measured values** when absent, so an adapter that omits them
behaves exactly as before.

### Schema

Top-level is `dict[model_code, TankConfig]`. Each `TankConfig`:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `robot_internal_tank_ml` | `float` | yes | Capacity of the robot's onboard water reservoir in ml. |
| `dock_clean_tank_capacity_ml` | `float` | no | Capacity of the dock's clean-water tank in ml. Omit for models with no dock clean tank. |
| `dock_wash_overhead_ml_per_cycle` | `float` | no | Measured water consumption per mop-wash cycle, in ml. Subtracted from total dock-water delta to isolate floor-mopping water. Omit for models with no dock wash cycle. |
| `water_rates` | `dict[str, float]` | no | First-pass floor-application flow rate in **ml/min, keyed by canonical water level** (`off`/`low`/`medium`/`high`). Replaces the default table wholesale when declared. Absent → the Eufy-measured default `{off: 0.0, low: 3.2, medium: 4.0, high: 5.3}` (unknown levels fall back to `4.0`). Read by `planning/run_plan.py::_water_rate_ml_per_minute` as `rate_override`. |
| `low_clean_water_margin_ml` | `float` | no | Dock clean-tank remaining (ml) at/below which the run plan raises the "low clean water" margin warning. Default `300.0` (Eufy dock tuning). Read in `planning/run_plan.py` (`_build_effective_start_plan` water block). |

The first three (tank dimensions) **must be measured on real hardware** —
they are not calculated, and the estimator's accuracy depends on the
measurement. `water_rates` likewise should be measured per dock; the
Eufy defaults are the bootstrap fallback.

> A closely-related fourth tuning knob — `wash_frequency_bounds`
> `{min, max, default}` — clamps the mop-wash interval but lives at the
> **top level** of the adapter config (not inside `water_model_configs`,
> because it's not per-model). See [§17a](#17a-wash_frequency_bounds--mop-wash-interval-clamp).

### Example

```python
"water_model_configs": {
    "T2351": {
        "robot_internal_tank_ml": 80.0,
        "dock_clean_tank_capacity_ml": 3080.0,
        "dock_wash_overhead_ml_per_cycle": 120.0,
        # Optional tuning — omit to inherit the Eufy defaults below:
        "water_rates": {"off": 0.0, "low": 3.2, "medium": 4.0, "high": 5.3},
        "low_clean_water_margin_ml": 300.0,
    },
},
```

The shipping Eufy adapter (`adapters/eufy/water_config.py`) declares only
the three tank measurements and **inherits both tuning defaults**, so its
behavior is byte-identical; the two optional keys are shown here as the
reference a brand port copies from.

**UI builder notes:** Three numeric inputs per model for the tank
measurements. Show the user a methodology note: "These are physical
measurements of your specific hardware. Fill the dock tank to a known
volume, run the cycle, and record what the percentage sensor shows." The
tuning keys (`water_rates`, `low_clean_water_margin_ml`) belong behind an
"Advanced" toggle pre-filled with the Eufy defaults.

---

## 17a. `wash_frequency_bounds` — mop-wash interval clamp

**Top-level** block (a sibling of `water_model_configs`, not nested
inside it — the bounds are per-brand, not per-model). Clamps the
mid-clean mop-wash interval the run plan derives from the
`wash_frequency_value_time` helper entity.

### Schema

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `min` | `float` | `15.0` | Lower clamp on the wash interval, in minutes. |
| `max` | `float` | `25.0` | Upper clamp on the wash interval, in minutes. |
| `default` | `float` | `20.0` | Fallback interval used when the helper entity is missing, non-numeric, or ≤ 0. |

Defaults are the Eufy X10 firmware range. Read by
`planning/run_plan.py::_derive_wash_frequency_config`; an absent block
uses the Eufy values, so Eufy is unchanged.

### Example

```python
"wash_frequency_bounds": {"min": 15.0, "max": 25.0, "default": 20.0},
```

**UI builder notes:** Advanced section — three numeric inputs in minutes
with `min ≤ default ≤ max` validation; pre-fill `15` / `20` / `25`.

---

## 18. The runtime contract

A few rules the framework relies on, called out so adapter authors
don't accidentally violate them:

1. **String matching is case-insensitive after `.strip().lower()`.**
   Vocabulary strings should be lowercased except in the explicitly
   labeled `blocked_*_states` lists.
2. **Entity keys vs entity IDs.** A field like
   `completion.secondary_clear_entity` is a **key** that indexes into the
   `entities` dict — not a full entity ID. (Charging detection reads the
   `entities.charging` key directly.)
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
| `vocabulary` | `core/manager.py` (`get_lifecycle_state`, `get_dock_action_status`), `learning/estimator.py` (water/wash alias maps), `learning/manager.py` (`_normalize_profile_setting` — `clean_mode`/`clean_intensity`/`fan_speed`/`water_level` alias maps, canonicalizing observed room-profile settings before they reach the card) |
| `completion` | `__init__.py` (`_completed_finalize_signals`), `core/manager.py` |
| `charging` | `core/charging.py` (`is_low_battery_return_state`), via `jobs/active_job.py` and `core/manager.py` |
| `error_tracking` | `core/error_tracker.py` |
| `dock_events` | `__init__.py` (`_register_dock_event_listeners`) |
| `post_job_wash_amendment` | `core/water_amendment.py`, `__init__.py` (registration call site) |
| `discovery` | `setup/workflow.py` (`discover_rooms_for_vacuum`) |
| `dispatch` | `queue/queue_engine.py` (`build_room_clean_payload`), `core/manager.py` (`async_start_room_clean_job`) |
| `mapping` | `mapping/manager.py` (`get_image_segment_suggestions`), `mapping/mapping_services.py` (`_handle_analyze_map_image`) |
| `map_state_source` | `mapping/map_source_coordinator.py` (`MapSourceCoordinator.async_refresh_map_state_source`); `core/manager.py` (delegators + `get_dashboard_snapshot` reads the cached result) |
| `map_render` | `mapping/map_source_coordinator.py` (`MapSourceCoordinator.async_get_map_render_data`); `core/manager.py` (`get_dashboard_snapshot` gates `supports_va_render` on its presence) |
| `job_segmenter` | `jobs/active_job.py` (`_live_boundary_count`), `learning/external_ingest.py` (`build_pending_record`, `resegment_pending_record`, `_resolve_engine_tuning`), `learning/history_store.py` (`_build_transit_blocks`) — engine + thresholds |
| `room_attribution` | `adapters/registry.py` (`_validate_adapter`) — validated + selectable; run-active consumers pending wiring |
| `live_transition` | `jobs/active_job.py` (`_live_transition_config`, `_live_boundary_count`) — orchestration knobs only (thresholds live in `job_segmenter`) |
| `room_profiles` | `queue/queue_engine.py` (`build_room_clean_payload` via `resolve_profile_catalog`), `profiles/room_profiles.py` (resolver `catalog` param) |
| `anomaly` | `jobs/active_job.py` (`ActiveJobTracker.detect_run_anomalies`); `core/manager.py` (`get_job_progress_snapshot`) delegates |
| `wash_frequency_bounds` | `planning/run_plan.py` (`_derive_wash_frequency_config`) |
| `capabilities` | `core/capabilities.py` (`detect_capabilities`) |
| `maintenance_components` | `core/manager.py` (`get_upkeep_snapshot`) |
| `upkeep_catalog` | `core/manager.py` (`_get_upkeep_model_meta`, `_get_upkeep_item_guide`) |
| `water_model_configs` | `planning/run_plan.py` (`_get_water_model_config`, `_water_rate_ml_per_minute`, water block), `learning/estimator.py` |

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
They are registered in the `services/` package (e.g.
`services/adapter_config.py`). The central index of every
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
