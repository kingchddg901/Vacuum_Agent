# Adapter configuration reference (generated)

Generated from `custom_components/eufy_vacuum/adapters/config_schema.py` (`ADAPTER_CONFIG_SCHEMA`, `validate_against_schema`), `custom_components/eufy_vacuum/adapters/registry.py` (`_validate_adapter`) and the two shipped adapters. Every fact below is derived from source; nothing is transcribed from the hand-written reference.

## What this contract is

Adapter configuration schema for the ha_vacuum_manager framework.

Defines the canonical shape of the per-vacuum adapter config dict that
both the code adapter path and the config adapter path must produce.

The schema is the contract between:
  - Adapter authors (who produce it)
  - The framework runtime (which consumes it)
  - The UI config flow (which will generate it in a future pass)

Every field is documented with:
  - What it controls in the framework
  - Whether it is required or optional
  - What the framework does when it is absent (graceful degradation)

Two paths produce this schema:
  - Code adapter: registers at startup via register_adapter_config()
  - Config adapter: written by the UI config flow to storage

The framework reads from the adapter registry regardless of which path
populated it. See adapters/registry.py.

## At a glance

| | |
|---|--:|
| Top-level keys | 33 |
| Required top-level keys | 5 |
| Documented entries (all depths) | 200 |
| ...carrying a prose `description` | 175 (88%) |
| Blocks declared as a bare dict (open-ended interior) | 10 |
| Blocks with an extra registration-time check | 7 |

**Required:** `adapter_id`, `source`, `entities`, `dispatch`, `room_profiles`. Everything else is optional; each optional block's own description states what the framework does when it is absent.

**Open-ended blocks** (declared `dict` with no enumerated interior, so the schema walker's unknown-key check does not apply inside them): `anomaly`, `capability_hints`, `device_clean_order`, `job_segmenter`, `map_render`, `map_state_source`, `mapping`, `room_attribution`, `room_profiles`, `settings_selects`.

## Full shape

```python
{
    # --- IDENTITY ---
    'adapter_id': str,                        # required
    'source': str,                            # required
    'display_name': str,                      # optional
    'brand': str,                             # optional
    # --- ENTITIES ---
    'entities': dict,                         # required
    # --- VOCABULARY ---
    'vocabulary': dict,                       # optional
    # --- COMPLETION ---
    'completion': dict,                       # optional
    # --- CHARGING ---
    'charging': dict,                         # optional
    # --- ERROR TRACKING ---
    'error_tracking': dict,                   # optional
    # --- DOCK EVENTS ---
    'dock_events': dict,                      # optional
    # --- POST-JOB WASH AMENDMENT ---
    'post_job_wash_amendment': dict,          # optional
    # --- ROOM DISCOVERY ---
    'discovery': dict,                        # optional
    # --- SETUP ---
    'setup': dict,                            # optional
    # --- DISPATCH ---
    'dispatch': dict,                         # required
    # --- CAPABILITIES ---
    'capabilities': dict,                     # optional
    'live_transition': dict,                  # optional
    'external_mid_run_statuses': list,        # optional
    # --- SETTINGS SELECTS (external-run capture) ---
    'settings_selects': dict,                 # optional
    # --- MAINTENANCE COMPONENTS ---
    'maintenance_components': dict[str, dict],# optional
    # --- UPKEEP CATALOG ---
    'upkeep_catalog': dict,                   # optional
    # --- WATER MODEL CONFIGS ---
    'water_model_configs': dict[str, dict],   # optional
    # --- PLUGGABLE ENGINES + LATE-ADDED BLOCKS ---
    'mapping': dict,                          # optional
    'map_state_source': dict,                 # optional
    'map_render': dict,                       # optional
    'device_clean_order': dict,               # optional
    'job_segmenter': dict,                    # optional
    'room_attribution': dict,                 # optional
    'room_profiles': dict,                    # required
    'anomaly': dict,                          # optional
    'wash_frequency_bounds': dict,            # optional
    'cleaning_time_unit': str,                # optional
    'model_family': str,                      # optional
    'capability_hints': dict,                 # optional
}
```

## Who declares what

| Block | eufy | roborock |
|---|---|---|
| `adapter_id` | yes | yes |
| `source` | yes | yes |
| `display_name` | yes | yes |
| `brand` | yes | yes |
| `entities` | yes | yes |
| `vocabulary` | yes | yes |
| `completion` | yes | yes |
| `charging` | yes | yes |
| `error_tracking` | yes | yes |
| `dock_events` | yes | - |
| `post_job_wash_amendment` | yes | - |
| `discovery` | yes | yes |
| `setup` | yes | yes |
| `dispatch` | yes | yes |
| `capabilities` | yes | yes |
| `live_transition` | yes | yes |
| `external_mid_run_statuses` | yes | - |
| `settings_selects` | yes | - |
| `maintenance_components` | yes | yes |
| `upkeep_catalog` | yes | yes |
| `water_model_configs` | yes | - |
| `mapping` | yes | yes |
| `map_state_source` | yes | yes |
| `map_render` | yes | yes |
| `device_clean_order` | - | yes |
| `job_segmenter` | yes | yes |
| `room_attribution` | yes | yes |
| `room_profiles` | yes | yes |
| `anomaly` | yes | - |
| `wash_frequency_bounds` | yes | - |
| `cleaning_time_unit` | - | yes |
| `model_family` | yes | - |
| `capability_hints` | yes | - |

## Validation

Recursively validate ``config`` against a schema node.

Returns a list of human-readable violation strings; empty == conformant.
Walks: required keys, type families, enum ``values`` membership, nested
``fields`` (fixed sub-schema), and ``entry_fields`` (per-entry required
sub-keys for catalog dicts/lists).

Generic over ``schema`` (not bound to ADAPTER_CONFIG_SCHEMA) so it can
recurse into a ``fields``/``entry_fields`` sub-schema, and so the test
suite's own validator-unit-tests can exercise it against small ad hoc
schemas. ``validate_adapter_config`` below is the production entry point
bound to the real schema.

A top-level-or-nested key whose name starts with "_" is exempt from the
"unknown key" check at every level: RP-033/VAC-3 stashes adapter-internal
bookkeeping (e.g. the code adapters' full entity_candidates) under such a
key on the registered config, deliberately NOT part of the user-facing
schema surface a stored/config adapter would ever declare.

Spec keys the walker enforces: `entry_fields`, `fields`, `required`, `type`, `values`. `description` is documentation only.

Spec keys present in the schema that the walker never reads: `canonical_fields` (1).

Type families recognised by `_type_ok`: `bool`, `dict`, `float`, `int`, `list`, `str`. Only the outer container is checked; a trailing `| null` permits `None`; an unrecognised type string passes unconditionally.

**Extra checks at registration** (`registry._validate_adapter`, beyond the schema walk):

| Block | `_validate_adapter` line(s) |
|---|---|
| `setup` | 604 |
| `dispatch` | 557 |
| `mapping` | 397 |
| `job_segmenter` | 429 |
| `room_attribution` | 459 |
| `room_profiles` | 506 |
| `capability_hints` | 532 |

## Identity

### `adapter_id`

type `str` - **required**

Unique identifier for this adapter. Used for logging and disambiguation when multiple adapters are registered. Example: 'eufy_x10_pro_omni'

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:33`.

*Read sites found by a conservative static scan (11; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/config_loader.py:81`, `custom_components/eufy_vacuum/adapters/registry.py:166`, `custom_components/eufy_vacuum/adapters/registry.py:191`, `custom_components/eufy_vacuum/adapters/registry.py:288`, `custom_components/eufy_vacuum/adapters/registry.py:655`, `custom_components/eufy_vacuum/adapters/registry.py:691`, `custom_components/eufy_vacuum/adapters/registry.py:718`, `custom_components/eufy_vacuum/services/adapter_config.py:142` ...

### `source`

type `str` - **required**

How this adapter config was produced. 'code' = registered by a code adapter at startup. 'config' = written to storage by the UI/service adapter-config path (save_adapter_config). ⚠ was: "The framework treats both identically at runtime." — false at the one boundary where `source` is the whole point. registry.py branches on this exact value at registration (RP-033/RF-32, anchor INYA5T84): when _validate_adapter returns any issue a 'config' config HARD-RAISES ServiceValidationError, while a 'code' config carrying the identical issues only logs warnings and registers. Everything DOWNSTREAM does treat them identically — nothing else in the tree branches on this key — so the asymmetry is registration severity and nothing more. Do not expect a stored config to get away with an omission the shipped code adapters do.

Allowed values: `code`, `config`

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:43`.

*Read sites found by a conservative static scan (5; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:179`, `custom_components/eufy_vacuum/adapters/registry.py:193`, `custom_components/eufy_vacuum/adapters/registry.py:706`, `custom_components/eufy_vacuum/adapters/registry.py:720`, `custom_components/eufy_vacuum/services/adapter_config.py:207`

### `display_name`

type `str` - optional

Human-readable name shown in the UI and logs.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:64`.

### `brand`

type `str` - optional

Short brand/app name the card uses in copy — e.g. "Eufy" renders "Clean from the Eufy app" in the External Jobs empty state. The card falls back to generic phrasing when absent.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:70`.

*Read sites found by a conservative static scan (5; a floor, not a complete set):* `custom_components/eufy_vacuum/diagnostics.py:152`, `custom_components/eufy_vacuum/diagnostics.py:694`, `custom_components/eufy_vacuum/diagnostics.py:695`, `custom_components/eufy_vacuum/learning/brand_facts.py:61`, `custom_components/eufy_vacuum/setup/workflow.py:157`

## Entities

### `entities`

type `dict` - **required**

Full HA entity IDs for companion entities.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `job_active` | `str` | no |  | Binary sensor that is on while a job runs. Roborock only. Drives completion.require_job_active_clear — the brand's terminal signal. |
| `mop_active` | `str` | no |  | Binary sensor reporting the mop is attached/active. Roborock only. |
| `mop_intensity` | `str` | no |  | Device-GLOBAL mop/water intensity select. Declared as a ROLE so the entity rescue can reach it and a user can override it; the mop global_pre_call names it via service.target_role rather than freezing an id, because pre-calls are built BEFORE the rescue runs and a frozen id stays wrong on a localized install (issue #51). Roborock only. |
| `dock_firmware_version` | `str` | no |  | Dock firmware version sensor. Diagnostic only. |
| `total_cleaning_area` | `str` | no |  | Lifetime cleaned-area counter. Diagnostic only. |
| `total_cleaning_count` | `str` | no |  | Lifetime completed-job counter. Diagnostic only. |
| `last_clean_end` | `str` | no |  | Timestamp the device stamps when it writes a clean-summary record. OBSERVABILITY ONLY — never gates completion. Read by the issue #46 observation trace (job_active_signal.py) and diagnostics; deliberately absent from the lifecycle watch list so a clean-summary edge cannot re-trigger the completion gate. |
| `total_cleaning_time` | `str` | no |  | Lifetime cleaning-time counter. Diagnostic only. |
| `task_status` | `str` | no |  | Task status sensor. Required for lifecycle detection, job completion signal, and error tracking. Degradation: lifecycle and learning disabled without it. |
| `dock_status` | `str` | no |  | Dock status sensor. Required for dock event recording, mop wash observation, and water amendment. Degradation: dock events and water amendment disabled. |
| `active_map` | `str` | no |  | Active map sensor. Required for map mismatch detection and multi-floor support. Degradation: map mismatch check skipped. |
| `active_cleaning_target` | `str` | no |  | Active cleaning target sensor. Used as secondary completion signal alongside task_status. Degradation: completion relies on task_status alone. |
| `cleaning_time` | `str` | no |  | Cleaning time sensor. Used by the job finalizer for actual duration. The framework reads the entity's own unit_of_measurement first; a BARE number with no unit falls back to this adapter's top-level `cleaning_time_unit` ("min" or "s", declared in this same schema), and only then is assumed to be seconds. ⚠ was: "Cleaning time sensor in seconds." — true of Eufy only. Roborock's counter is a bare number in MINUTES and declares cleaning_time_unit: "min". A porter who takes "in seconds" as the contract and ships a bare minutes sensor without declaring the unit stores every duration 60x low — listeners/job_metrics.py says exactly that at the ct_unit_hint read. The unit is a brand fact, not a framework requirement. Degradation: duration derived from job timestamps only. |
| `cleaning_area` | `str` | no |  | Cleaning area sensor. Used by the job finalizer. The framework normalizes whatever the sensor reports to canonical m² from its unit_of_measurement (learning/utils.py::cleaning_area_to_m2, whose _AREA_TO_M2 covers m²/ft²/in²/yd²/cm²); an absent or unknown unit is assumed to be m² already, never guessed. ⚠ was: "Cleaning area sensor in m²." — not a contract the adapter author can honour, because the unit follows the USER's HA unit system rather than the brand: an imperial HA exposes Eufy's cleaning_area in ft² while Roborock's stays m² (confirmed live on sensor.alfred_cleaning_area vs sensor.ivy_cleaning_area). A new consumer that reads `state` bare on the strength of that sentence reintroduces the ~10.76x inflation that breaks cross-brand comparison and mis-fires swept_area_min_m2. The real contract is: declare the entity, the framework reads its unit. Degradation: area omitted from job record. |
| `battery` | `str` | no |  | Battery level sensor (0-100). Used by battery health manager and low battery return detection. Degradation: falls back to vacuum entity battery_level attribute. |
| `error_message` | `str` | no |  | Error message sensor. Primary signal for error tracking. Degradation: error tracking relies on secondary channels only (vacuum state, task_status). |
| `charging` | `str` | no |  | Charging binary sensor — the sole charging detection signal. Absent/unknown -> is_charging() returns False; there is NO substring fallback on task_status/dock_status (removed as a false-negative source, see core/charging.py). |
| `wash_frequency_mode` | `str` | no |  | Wash frequency mode select entity. Degradation: water estimation uses default interval. |
| `wash_frequency_value_time` | `str` | no |  | Wash frequency interval number entity (minutes). Degradation: water estimation uses default interval. |
| `dry_duration` | `str` | no |  | Dry duration select entity. Read at dry_start dock events and stored with the event record. |
| `water_level` | `str` | no |  | Station clean water level sensor (0-100%). Degradation: water estimation uses flow rates only, no actual tank level tracking. |
| `robot_position_x` | `str` | no |  | Robot X position sensor (raw vacuum coordinates). Required for trace-based room bounds derivation. Degradation: mapping subsystem inactive. |
| `robot_position_y` | `str` | no |  | Robot Y position sensor (raw vacuum coordinates). Required for trace-based room bounds derivation. Degradation: mapping subsystem inactive. |
| `work_mode` | `str` | no |  | Work mode sensor. Read ONLY by core/capabilities.py, and only for PRESENCE — the entity (or its registry entry) existing sets supports_work_mode / work_mode_available for the card. The sensor's STATE is never consulted anywhere in the framework. ⚠ was: "Used by the start-blocker check in core/manager.py to detect blocked work modes. Degradation: work mode block check skipped." — false. No start-blocker reads work_mode: jobs/job_monitor.py::build_start_blocker_from_lifecycle has arms for vacuum_busy, mid_job_service, active_job_running, map_mismatch and friends, and no work-mode arm at all. The check was REAL once — see the vocabulary.blocked_work_mode_states note below and docs/dev/22-adapter-contract.md §5 for its four datable stages — but declaring this entity buys no start protection today, and someone debugging "why did a job start during Smart Follow?" will hunt a core/manager.py check that does not exist. Degradation: only the supports_work_mode capability flag is lost. |
| `cleaning_intensity` | `str` | no |  | Cleaning intensity select entity. Used as fallback for path control capability detection. Degradation: path control inferred from model family only. |
| `scene_select` | `str` | no |  | Vendor-app scenes select entity (e.g. eufy-clean select.<object_id>_scene). Its options are the app's saved scenes; selecting one RUNS it immediately. Surfaced on the dashboard snapshot for the card's 'App scenes' run-launcher. Degradation: absent (Roborock) -> the scenes group is hidden. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:84`.

*Read sites found by a conservative static scan (45; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:647`, `custom_components/eufy_vacuum/battery/manager.py:676`, `custom_components/eufy_vacuum/core/charging.py:56`, `custom_components/eufy_vacuum/core/charging.py:83`, `custom_components/eufy_vacuum/core/error_tracker.py:561`, `custom_components/eufy_vacuum/core/manager.py:1784`, `custom_components/eufy_vacuum/core/manager.py:3751`, `custom_components/eufy_vacuum/core/manager.py:3962` ...

## Vocabulary

### `vocabulary`

type `dict` - optional

Brand-specific state vocabulary sets.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `hard_service_states` | `list[str]` | no |  | Dock/task states that hard-block job start. The dock or vacuum is performing a service action that cannot be interrupted (washing, recycling, emptying). Degradation: no hard service blocking. |
| `drying_states` | `list[str]` | no |  | Dock states that produce a warning but do not block job start. Degradation: drying warning skipped. |
| `active_run_task_states` | `list[str]` | no |  | Task status strings that indicate the vacuum is actively running a job. Used to set has_observed_active_lifecycle and detect vacuum_busy state. |
| `not_error_sentinels` | `list[str]` | no |  | Error message values that mean no error is present. Anything not in this set is treated as a real error. Degradation: uses framework defaults. |
| `blocked_work_mode_states` | `list[str]` | no |  | NOT CONSUMED. Nothing reads this key. Historically: work mode strings that blocked job start, raw (non-normalized) values from the work_mode sensor. No start-blocker consults work_mode today — entities.work_mode is read only by core/capabilities.py, for capability detection. Declaring this changes nothing. |
| `blocked_task_status_states` | `list[str]` | no |  | NOT CONSUMED, and SUPERSEDED rather than lost — which is the difference that matters. The gate it named still exists; it is spelled with different vocabulary. jobs/job_monitor.py::evaluate_job_lifecycle refuses a start on active_run_task_states and on hard_service_states, and those two cover every value the reference brand declares here (verified 2026-08-23: Cleaning and Returning via active_run_task_states, Washing Mop via hard_service_states). Restoring a reader for this key would add a SECOND, shorter copy of a live rule with its own message — which is how the shorter copy becomes the bug. Declare the two sets above instead. |
| `blocked_dock_status_states` | `list[str]` | no |  | Dock status strings that block job start. Raw (non-normalized) values. Degradation: dock status block check skipped. |
| `cancel_service_exclusion_states` | `list[str]` | no |  | Normalized task_status strings that, if seen in the transition history of a very short job, explain the early return as a service event (low-battery return, mop wash, dust empty) rather than a manual cancel. When any of these strings appears the cancel detection check returns cancel_likely=False. Degradation: uses framework defaults. |
| `cancel_detection_states` | `dict[str, Any]` | no |  | Normalized task_status transition strings the cancel detector matches against. Keys: 'active' (the cleaning state — a single string, OR a list of strings for brands whose active status is mode-specific, e.g. Roborock's cleaning / segment_cleaning / zoned_cleaning), 'returning' (the return-to-dock state, e.g. 'returning' for Eufy, 'returning_home' for Roborock), 'paused'. A cancel-like transition is active->returning or paused->returning on the task_status entity. Degradation: defaults to the HA-standard cleaning/returning/paused strings. |
| `water_level_aliases` | `dict[str, str]` | no |  | Maps brand-specific water-level display strings (lowercased) to canonical keys the framework uses for water-rate lookup. Canonical keys: 'low', 'medium', 'high'. Example: {'small': 'low', 'standard': 'medium', 'large': 'high'}. Degradation: unknown values pass through with spaces replaced by underscores and the estimator uses default flow rate. |
| `wash_frequency_mode_aliases` | `dict[str, str]` | no |  | Maps brand-specific wash-frequency-mode display strings (lowercased) to canonical mode keys. Canonical keys: 'by_room', 'by_time', 'off'. Example: {'by room': 'by_room', 'by time': 'by_time'}. Degradation: unknown values pass through and the estimator falls back to the default interval. |
| `clean_mode_aliases` | `dict[str, str]` | no |  | Maps brand clean-mode display strings (lowercased, non-alnum collapsed to a single space) to the canonical codes the card vocab is keyed on. Canonical codes: 'vacuum', 'mop', 'vacuum_mop'. Example: {'vacuum and mop': 'vacuum_mop'}. The learning manager normalizes observed settings through this so the card receives a code, not a display string. Degradation: unknown values slug through (spaces -> underscores). |
| `clean_intensity_aliases` | `dict[str, str]` | no |  | Maps brand clean-intensity display strings to canonical codes. Canonical codes: 'quick', 'narrow', 'deep', 'normal', 'standard'. May be empty when the brand's display values already slug to the canonical code. Degradation: slug-through. |
| `fan_speed_aliases` | `dict[str, str]` | no |  | Maps brand suction/fan-speed display strings to canonical codes. Canonical codes: 'quiet', 'gentle', 'standard', 'boost', 'turbo', 'max'. Example: {'boostiq': 'boost'}. Degradation: slug-through. |
| `clean_mode_options` | `list[dict]` | no |  | Valid clean-mode values for this vacuum. List of {value, label} dicts. Canonical values: 'vacuum', 'mop', 'vacuum_mop'. Example: [{'value': 'vacuum', 'label': 'Vacuum'}, ...]. Degradation: card falls back to a framework-canonical default list with all three values. |
| `clean_mode_options.value` | `str` | yes |  |  |
| `clean_mode_options.label` | `str` | yes |  |  |
| `fan_speed_options` | `list[dict]` | no |  | Valid fan-speed values for this vacuum. List of {value, label} dicts. Eufy: Quiet/Standard/Boost/Max. Roborock with Max+: Quiet/Standard/Boost/Max/Max+. Each brand declares what its hardware supports. |
| `fan_speed_options.value` | `str` | yes |  |  |
| `fan_speed_options.label` | `str` | yes |  |  |
| `water_level_options` | `list[dict]` | no |  | Valid water-level values for this vacuum (mop-capable models only). List of {value, label} dicts. Eufy: Off/Low/Medium/High. |
| `water_level_options.value` | `str` | yes |  |  |
| `water_level_options.label` | `str` | yes |  |  |
| `clean_intensity_options` | `list[dict]` | no |  | Valid clean-intensity values for this vacuum. List of {value, label} dicts. Eufy: Quick/Narrow/Deep. A brand declares this OR path_type_options, never both — they are two names for the same pass-density axis, and declaring both puts one physical property on the wire twice. Omit and the card hides the picker. |
| `clean_intensity_options.value` | `str` | yes |  |  |
| `clean_intensity_options.label` | `str` | yes |  |  |
| `path_type_options` | `list[dict]` | no |  | Valid path/route values for this vacuum. List of {value, label} dicts. Roborock: wide/narrow. This is the same axis as clean_intensity_options under the other brand's name — declare exactly one of the two. Declaring the list is what makes a stored value judgeable by the store repair, and is required even when no current model exposes the axis: without it a bad value can be neither dropped (the field IS declared) nor reset (nothing to check against). |
| `path_type_options.value` | `str` | yes |  |  |
| `path_type_options.label` | `str` | yes |  |  |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:361`.

*Read sites found by a conservative static scan (12; a floor, not a complete set):* `custom_components/eufy_vacuum/core/error_tracker.py:135`, `custom_components/eufy_vacuum/core/manager.py:3734`, `custom_components/eufy_vacuum/core/manager.py:5841`, `custom_components/eufy_vacuum/core/run_state.py:65`, `custom_components/eufy_vacuum/dock/manager.py:231`, `custom_components/eufy_vacuum/jobs/active_job.py:1959`, `custom_components/eufy_vacuum/learning/brand_facts.py:57`, `custom_components/eufy_vacuum/listeners/pose_sampler.py:182` ...

## Completion

### `completion`

type `dict` - optional

Job completion signal configuration.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `task_status_value` | `str` | no |  | Normalized task_status value that signals job completion. Default: 'completed'. |
| `secondary_clear_entity` | `str` | no |  | ⚠ UNWIRED SEAM — DECLARED, VALIDATED, AND READ BY NOTHING (A9). Setting this has NO EFFECT today. The completion gate hardcodes the role: listeners/_common.py builds `'active_target': _state(entities.get('active_cleaning_target'))` and compares THAT against secondary_clear_sentinels. Verified by an AST sweep of every module, not a grep — zero readers. It was born orphaned: `git log -S` puts the declaration and the hardcode that ignores it in the SAME commit (2bfda655), so this is an aspirational declaration, not a consumer that was lost. INTENDED, once wired: entity key from the entities dict whose cleared state is required alongside task_status_value. Default: 'active_cleaning_target'. ⚠ THE DANGEROUS CASE IS NOT 'jobs never finalize'. A porter who sets this AND omits entities.active_cleaning_target gets `_state(None) == ''`, and '' IS in the default sentinel set — so the secondary is ALWAYS satisfied and the gate silently collapses to task_status alone. A premature finalize ends a running job and writes a wrong run record; a late one is recoverable. KEPT, NOT DELETED: a string naming ANY role is strictly more general than the shipped require_job_active_clear, which is a bool hardcoding ONE alternative role. Deleting it would also flip a stored config that sets it from silently-ignored to loudly-rejected. |
| `secondary_clear_sentinels` | `list[str]` | no |  | Values that mean the secondary entity is cleared. Default: ['', 'unknown', 'unavailable', 'none', 'null']. |
| `require_job_active_clear` | `bool` | no |  | When True, completion keys on the job-active (cleaning) binary clearing (entities.job_active, enforced by the recharge-resume guard) INSTEAD of the secondary_clear sentinel check. Needed for brands whose active_cleaning_target reverts to a non-sentinel at the end of a run (Roborock current_room -> the dock room's name), where the sentinel check would never pass. Pair with entities.job_active. Default: False (use secondary_clear). |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:629`.

*Read sites found by a conservative static scan (6; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:642`, `custom_components/eufy_vacuum/diagnostics.py:724`, `custom_components/eufy_vacuum/jobs/active_job.py:3234`, `custom_components/eufy_vacuum/listeners/_common.py:352`, `custom_components/eufy_vacuum/listeners/lifecycle.py:332`, `custom_components/eufy_vacuum/listeners/lifecycle.py:376`

## Charging

### `charging`

type `dict` - optional

Low-battery mid-job return detection. The charging *state* itself is read from the dedicated entities.charging binary sensor (core/charging.py); this block only configures the low-battery-return classifier.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `low_battery_return_task_status` | `str` | no |  | Normalized task_status string the vacuum reports when it returns to dock specifically to recharge mid-job (Eufy: 'returning to charge'). Authoritative — no battery gate needed when it matches. Absent: low-battery return is detected only via the generic 'returning' vacuum state + low_battery_threshold_percent gate. |
| `low_battery_threshold_percent` | `int` | no |  | Battery percent at/below which a generic 'returning' vacuum state is treated as a low-battery return (so a user-initiated return_to_base on a full battery isn't mis-classified). Default: 20. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:696`.

*Read sites found by a conservative static scan (2; a floor, not a complete set):* `custom_components/eufy_vacuum/core/charging.py:83`, `custom_components/eufy_vacuum/jobs/active_job.py:505`

## Error Tracking

### `error_tracking`

type `dict` - optional

Error tracker configuration.

CODE TYPE (R2-TYPE-1): the five classification tables below are keyed `int|str`, not `int`. A brand's error code is whatever its firmware reports — Eufy sends numbers, Roborock sends enum strings (`bumper_stuck`), and `core.error_tracker._code_key` normalises both into one comparable key. The annotations used to say `int`, describing what Eufy ships rather than what the seams accept, which read as a rule that string-keyed tables were malformed when they are the supported shape.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `message_is_code` | `bool` | no |  | TRUE when this brand's error_message entity STATE is itself the error code, rather than prose about it. Roborock's sensor.<id>_vacuum_error reports `bumper_stuck`; Eufy's reports 'Robot is stuck'. Declared, never sniffed: with it the tracker carries the message value into `code` when the attribute route yields nothing, and without it that same fallback would mint pseudo-codes like `robot is stuck` out of Eufy prose and pollute every classification table with garbage keys. Default: False — a brand that says nothing keeps the attribute-only behaviour. |
| `task_status_error_value` | `str` | no |  | Normalized task_status value that indicates an error state. Used as secondary error channel alongside vacuum entity state. Default: 'error'. |
| `grace_window_seconds` | `int` | no |  | Seconds to wait after secondary error signal before finalizing as unknown error. Some firmware emits the state before the error message. Default: 5. |
| `error_code_attribute_names` | `list[str]` | no |  | Attribute key names to check when reading the error code from the vacuum or error_message entity attributes. Tried in order — first non-zero int wins. |
| `unknown_error_message` | `str` | no |  | Placeholder message used when the grace window elapses without a real error message arriving. Default: 'Unknown error during run'. |
| `evidence_invalidating_error_codes` | `list[int\|str]` | no |  | Error codes after which the run's cleaning evidence cannot be trusted. ONLY these are deducted from cleaning_time_seconds. A brand that omits this deducts nothing — the failure mode degrades toward trusting the run rather than toward zeroing it. |
| `error_label_keys` | `dict[int\|str, str]` | no |  | Maps this brand's error codes to i18n keys for the card's fault labels. The strings live in the frontend locale packs; core only passes the key through, so it never learns a brand's codes. A code absent from this map has no label and the card falls back to the raw number. |
| `evidence_safe_error_codes` | `list[int\|str]` | no |  | Error codes that leave the floor work valid — station faults the robot cleaned straight through, and robot faults that bracket the clean (docking, undocking) rather than interrupt it. Declared SEPARATELY from the invalidating list so a code in neither is visibly unclassified: unknown must stay distinguishable from deliberately-safe, or a code the vendor ships after this table was written silently changes the arithmetic. |
| `dock_sourced_error_codes` | `list[int\|str]` | no |  | Error codes raised by the BASE STATION. A SECOND, independent axis from the two evidence lists above — not a finer grain of them. Evidence decides whether seconds may be deducted; source decides which box to point the user at, and a station fault the robot cleaned straight through is both evidence-safe and dock-sourced. Reported only, never subtracted. A brand that omits this reports every fault as unattributed rather than guessing a majority class. |
| `robot_sourced_error_codes` | `list[int\|str]` | no |  | Error codes raised by the ROBOT itself. Companion to dock_sourced_error_codes; a code in neither reports as 'unknown', which stays honest as the vendor adds codes. Defaulting an unrecognised fault to 'robot' would start blaming hardware that is fine. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:733`.

*Read sites found by a conservative static scan (3; a floor, not a complete set):* `custom_components/eufy_vacuum/core/error_tracker.py:153`, `custom_components/eufy_vacuum/core/error_tracker.py:786`, `custom_components/eufy_vacuum/core/manager.py:4972`

## Dock Events

### `dock_events`

type `dict` - optional

Dock event recording configuration.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `enabled` | `bool` | no |  | Whether to record dock events (wash, empty, dry). Set False for brands with no dock actions. Default: False. |
| `triggers` | `dict[str, list[str]]` | no |  | Maps framework event type keys to the dock_status strings that trigger them. Keys are framework vocabulary ('last_mop_wash', 'last_dust_empty', 'last_dry_start'). Values are normalized dock_status strings. Absent keys produce no events. |
| `debounce_seconds` | `dict[str, float]` | no |  | Per-event-type cooldown that collapses noisy dock_status flips into a single counted event. Keys are the same framework event type names as 'triggers'; values are minimum seconds between counted events. Also gates the active-job mop-wash observation via the 'last_mop_wash' key. Absent key (or 0) = no debounce, every flip counts. |
| `action_buttons` | `dict[str, dict]` | no |  | Resolves the upstream button entity for each dock action. Keyed by framework action name ('wash_mop', 'dry_mop', 'stop_dry_mop', 'empty_dust'). Each value: {'entity_suffixes': [str] appended to 'button.{object_id}_' tried in order; 'token_sets': [[str]] each an all-tokens-must-match registry fallback}. Absent action = no button resolved (the action is reported unavailable). |

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:864`.

*Read sites found by a conservative static scan (9; a floor, not a complete set):* `custom_components/eufy_vacuum/core/manager.py:5906`, `custom_components/eufy_vacuum/dock/manager.py:105`, `custom_components/eufy_vacuum/dock/manager.py:230`, `custom_components/eufy_vacuum/dock/manager.py:504`, `custom_components/eufy_vacuum/jobs/active_job.py:725`, `custom_components/eufy_vacuum/listeners/dock_events.py:122`, `custom_components/eufy_vacuum/listeners/dock_events.py:92`, `custom_components/eufy_vacuum/listeners/lifecycle.py:282` ...

## Post-Job Wash Amendment

### `post_job_wash_amendment`

type `dict` - optional

Post-job mop wash water amendment configuration. Only needed for brands whose dock washes the mop after docking, after the job file has been finalized.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `enabled` | `bool` | no |  | Whether to register the post-job wash watcher. Set False for brands with no post-job wash behavior. Default: False. |
| `trigger_states` | `list[str]` | no |  | Normalized dock_status strings that increment the post-job wash count. |
| `commit_state` | `str` | no |  | Normalized dock_status string that signals the wash cycle is complete and triggers the amendment commit. |
| `debounce_seconds` | `float` | no |  | Minimum seconds between wash count increments. Prevents double-counting multi-state wash sequences. Set to 0 for brands with single-state wash cycles. |
| `timeout_seconds` | `int` | no |  | Seconds after which the amendment watcher closes regardless of commit_state. Safety valve. |

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:918`.

*Read sites found by a conservative static scan (4; a floor, not a complete set):* `custom_components/eufy_vacuum/core/water_amendment.py:81`, `custom_components/eufy_vacuum/listeners/lifecycle.py:579`, `custom_components/eufy_vacuum/listeners/lifecycle.py:586`, `custom_components/eufy_vacuum/listeners/lifecycle.py:591`

## Room Discovery

### `discovery`

type `dict` - optional

Room discovery configuration.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `implicit_map_id` | `str` | no |  | Synthetic map id used when the transport exposes no real map (Eufy scalar/Tuya ships "main"). NOTE: it is non-numeric, which is why map-id handling must not assume an int — learned area bands are keyed by map id and become unreachable for such installs. |
| `source` | `str` | no | `entity_attribute`, `service_response` | Where the room list comes from. 'entity_attribute' (default, Eufy): a live attribute on an HA entity, read synchronously. 'service_response' (Roborock): the room list only exists in a service-call RESPONSE (get_maps). For service sources the framework calls the service at the async discovery boundaries, flattens it, and caches it for the sync discovery path — see rooms/source_refresh.py. Absent = 'entity_attribute'. |
| `room_list_shape` | `str` | no | `flat_list`, `per_map_mapping` | SHAPE of the room list, declared independently of the SOURCE it arrives through. 'flat_list' (default): the rooms for one map, as a list of dicts. 'per_map_mapping': a {map_name: [room, ...]} mapping covering every map, from which the active map's entry is selected. Source and shape were conflated until 2026-08-07 — 'entity_attribute' assumed a flat list and 'service_response' assumed per-map keying — which left the diagonal unexpressible: a brand serving a per-map MAPPING as a live ATTRIBUTE (Dreame's vacuum `rooms` attribute is {map_name: [{id, name, icon}, ...]}) read as 'missing or invalid' and discovered ZERO rooms. Declaring the shape is the extension point; branching on a brand name is not. Ignored for source='service_response', whose flattener always produces per-map keying. |
| `maps_service` | `dict` | no |  | For source='service_response': the response-returning service that lists maps + rooms. {'domain': str, 'service': str}, called with the vacuum entity as target and return_response=True. Example: {'domain': 'roborock', 'service': 'get_maps'}. |
| `maps_rooms_key` | `str` | no |  | For source='service_response': key in each map entry of the service response that holds the rooms. The value may be a {segment_id_str: name} mapping (flattened to list-of-dicts by the shim) or already a list of dicts. Default: 'rooms'. |
| `map_name_key` | `str` | no |  | For source='service_response': key in each map entry that holds the map's identity. The flattened cache is keyed by this value, which must match what entities.active_map reports (Roborock's select.{id}_selected_map reports the map NAME). Default: 'name'. |
| `room_list_entity` | `str` | no |  | For source='entity_attribute': which entity exposes the room list. Use 'vacuum_entity' to read from the vacuum entity itself, or supply a full entity ID. Default: 'vacuum_entity'. |
| `room_list_attribute` | `str` | no |  | For source='entity_attribute': attribute name on the entity that contains the room list. Expected to be a list of dicts. |
| `room_id_key` | `str` | no |  | Key in each room dict that contains the room ID. Example: 'id' for Eufy, 'segment_id' for Roborock. |
| `room_name_key` | `str` | no |  | Key in each room dict that contains the room name. Example: 'name'. |
| `auto_refresh_on` | `list[str]` | no | `vacuum_docked`, `active_map_changed`, `config_entry_reload` | Event triggers that automatically run room discovery. 'vacuum_docked' fires whenever the vacuum entity transitions to 'docked'. 'active_map_changed' fires when the active_map sensor value changes. 'config_entry_reload' fires once per integration setup. Manual rescan via service call is always available regardless of this list. Default: ['vacuum_docked', 'active_map_changed', 'config_entry_reload']. |
| `auto_refresh_interval_seconds` | `int` | no |  | Safety-net periodic discovery interval in seconds. Runs in addition to event-driven triggers; covers idle vacuums that never reach a triggering event. Set to 0 to disable the periodic floor. Default: 21600 (6 hours). |
| `removal_confirmation_passes` | `int` | no |  | Number of consecutive discovery passes a configured room must be absent from before it is flagged as removed in the setup-status response. Prevents transient API glitches from producing spurious removal notifications. Set higher for noisy integrations, lower for stable ones. Default: 3. |
| `new_room_confirmation_passes` | `int` | no |  | Number of consecutive discovery passes a new room must appear in before it is flagged for user review. Default: 1 (surface immediately). Increase only for integrations that frequently surface phantom rooms. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:974`.

*Read sites found by a conservative static scan (6; a floor, not a complete set):* `custom_components/eufy_vacuum/onboarding/manager.py:321`, `custom_components/eufy_vacuum/rooms/room_discovery.py:201`, `custom_components/eufy_vacuum/rooms/room_discovery.py:235`, `custom_components/eufy_vacuum/rooms/room_discovery.py:286`, `custom_components/eufy_vacuum/rooms/source_refresh.py:497`, `custom_components/eufy_vacuum/setup/drift.py:150`

## Setup

### `setup`

type `dict` - optional

Setup-flow step declaration. Each step ID maps to a framework-defined service and card view. The framework iterates the adapter's declared list in order; unknown step IDs reject the adapter at registration. Absent = default to ['add_vacuum', 'save_rooms'].

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `steps` | `list[str]` | yes | `add_vacuum`, `import_active_map`, `save_rooms`, `calibrate_map`, `set_dock_position` | Ordered list of setup step IDs. 'add_vacuum' is required for every adapter. 'save_rooms' is required for every adapter. 'import_active_map' is in practice required too: it is the brand-agnostic "discover + create the map bucket" op (it refreshes the map source first), and without it Configure Rooms has no bucket to show rooms from. BOTH shipped adapters declare it, for opposite reasons — Eufy because its integration surfaces one cloud map at a time and needs an explicit import, Roborock because the bucket still has to be built from the get_maps rooms (its own setup block says so). ⚠ was: "needed by brands whose integration surfaces one map at a time and requires an explicit import operation (Eufy)" — that reads as a test a porter applies to their own brand, so a brand exposing all maps at once correctly concludes it may drop the step, then ships a setup flow whose room step shows nothing. setup/drift.py's _DEFAULT_SETUP_STEPS ('add_vacuum', 'save_rooms') omits it, so an adapter that declares no setup block at all inherits exactly that broken shape. 'calibrate_map' and 'set_dock_position' are reserved for future brand-specific extensions. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1147`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:604`.

*Read sites found by a conservative static scan (3; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:604`, `custom_components/eufy_vacuum/adapters/registry.py:614`, `custom_components/eufy_vacuum/setup/drift.py:141`

## Dispatch

### `dispatch`

type `dict` - **required**

Job dispatch configuration.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `zone_passes_max` | `int` | no |  | Max repeat count the ZONE command accepts, per zone. Falls back to `passes_max`, then 3. Consulted on both coordinate branches — unlike capabilities.supports_zone_repeat, which is non-device_mm only (see its note). |
| `passes_max` | `int` | no |  | Maximum clean_passes the wire accepts. Load-bearing: the queue engine clamps to it before dispatch. Absent => the framework default, which may exceed what the brand tolerates. |
| `zone_command` | `str` | no |  | Service/command name used to dispatch a zone clean. |
| `zone_coords` | `str` | no |  | Coordinate space the zone command expects (e.g. "device_mm"). Zone rectangles are converted into this space before dispatch. |
| `phase_timing` | `dict` | no |  | Per-phase dispatch timing/settle tuning for stepped runs. |
| `live_room_refresh` | `dict` | no |  | Live current-room pulse config (Lever B) — nudges the provider to refresh its current-room signal faster than its own cache interval. |
| `template` | `str` | yes | `eufy_room_clean`, `roborock_segment_clean`, `dreame_room_clean`, `generic_room_ids` | Payload template to use. Determines how the framework constructs the service call payload from the resolved room list. |
| `service_domain` | `str` | yes |  | HA service domain. Example: 'vacuum'. |
| `service_name` | `str` | yes |  | HA service name. Example: 'send_command'. |
| `command` | `str` | no |  | Command string passed to the service. Required for templates that use a 'command' field (e.g. Eufy). Omit for templates that call the service directly. |
| `params_as_list` | `bool` | no |  | When True, the payload is wrapped in a single-element list on the wire: params=[payload] (Roborock app_segment_clean wants params=[{segments:[...],repeat:n}]). Default False = the bare payload dict (Eufy room_clean). Only applies to the command/params envelope (ignored for direct-merge templates). |
| `map_id_field` | `str` | no |  | Field name for map_id in the payload. Default: 'map_id'. |
| `map_id_type` | `str` | no | `int`, `str` | Type to cast map_id to before dispatch. Default: 'str'. |
| `room_id_field` | `str` | no |  | Field name for room ID in each room payload entry. Example: 'id' for Eufy, 'segment_id' for Roborock. |
| `clean_passes_field` | `str` | no |  | Field name for clean passes in each room payload entry. Example: 'clean_times' for Eufy, 'repeat' for Roborock. |
| `passes_is_global` | `bool` | no |  | True when clean passes is ONE batch scalar for the whole run (the flat-list engines collapse the selected rooms to the MAX requested passes) rather than per-room on the wire. The card keeps per-room passes chips but notes the strongest setting applies to the entire run. Default: False (per-room passes, Eufy/Dreame). |
| `rooms_field` | `str` | no |  | Field name for the rooms list in the payload. Example: 'rooms' for Eufy, 'segments' for Roborock. |
| `resolve_live_ids_by_slug` | `bool` | no |  | When True, the framework re-resolves each target room's name slug to its CURRENT segment id from a fresh discovery refresh (get_maps) right before sending, rewriting the wire id list. For brands whose segment ids renumber on re-segment (Roborock) so a stored id never cleans the wrong room. A target whose slug is absent from the current map is skipped; an unavailable source falls back to the stored ids. Default: False (use stored ids). |
| `per_room_live_settings` | `list[dict]` | no |  | Per-room device settings pushed LIVE as the robot enters each room (driven by the native current_room rollover —  live_transition.native_transition_source), for brands where a setting takes effect mid-run on the room being cleaned (Roborock: vacuum.set_fan_speed). True per-room control without per-room re-dispatch — the device keeps one path-optimized run. Each entry: {'field' (canonical room field, e.g. 'fan_speed'), 'service' ({'domain','service','value_key', optional 'target_entity_id'}), optional 'value_map', optional 'options_key' (a vocabulary list name — the value is pushed only when it's one of those options, skipping the framework's Eufy-shaped default on a brand whose vocabulary differs)}. The value is the entered room's resolved per-room value. Best-effort + fire-and-forget. Absent = no live per-room settings. Distinct from global_pre_calls (one value/run, pre-dispatch) — use this when the device honors mid-run per-room changes. |
| `global_pre_calls` | `list[dict]` | no |  | Global device settings pushed before a dispatch, for brands that expose a setting only globally. Each entry picks the value from the dispatched rooms' canonical field by max-wins over 'rank' (strongest request applies — mirrors the batch-passes max rule), maps it via optional 'value_map', and calls 'service'. Rooms whose value isn't in 'rank' are ignored; if none rank, the setting is left untouched. For a SEQUENCED job it re-runs PER PHASE from that phase's own rooms (phase_runner._dispatch_active_phase), so a vacuum group then a mop group each apply their own value; for an atomic job it fires once at start. Best-effort for ordinary entries: a failed pre-call logs and continues. NOT best-effort when mixed_mode_water_policy is 'safest' — that entry RAISES and aborts the dispatch on a missing target or a rejected select, because pushing safe water before a batch with dry rooms is what stops them being wet-mopped. Absent = no pre-call. Use per_room_live_settings instead when the device honors mid-run per-room changes. |
| `global_pre_calls.field` | `str` | yes |  | Canonical per-room field to read (e.g. 'fan_speed', 'water_level'). |
| `global_pre_calls.rank` | `list[str]` | yes |  | Allowed values in ASCENDING order; max-wins picks the highest present across the selected rooms. Doubles as the valid-value set (unrecognized room values are ignored). Example fan: ['gentle','quiet','balanced','turbo','max']. |
| `global_pre_calls.service` | `dict` | yes |  | {'domain', 'service', 'value_key', optional 'target_role' or 'target_entity_id'}. PREFER target_role: it names an entities-map role resolved at CALL time, so a rescued (localized or renamed) entity receives the push. A frozen target_entity_id is the PRE-RESCUE guess, because these blocks are built before resolve_declared_entities runs. The service is called with {entity_id: resolved target_role or target_entity_id or the vacuum, value_key: <wire value>}. Example: vacuum.set_fan_speed with value_key='fan_speed'; select.select_option targeting the mop-intensity select with value_key='option'. |
| `global_pre_calls.value_map` | `dict[str, Any] \| null` | no |  | Optional canonical->wire value map. Identity passthrough when absent (Roborock fan/water values already match the wire). |
| `global_pre_calls.mixed_mode_water_policy` | `str \| null` | no | `safest` | Mixed-batch safety for a device-GLOBAL water/mop-intensity select, which cannot be zeroed per room. Declare 'safest' so a batch containing BOTH mop rooms and vacuum-only rooms picks the lowest rung (off) instead of max-wins — otherwise the dry rooms get wet-mopped. Under-mop is accepted over wet-mop. A single-mode batch keeps max-wins. Omit on entries where max-wins is always right (a fan entry must NOT carry it, or suction drops to the weakest room's setting). Read by dispatch/manager.py. |
| `room_fields` | `dict[str, dict]` | no |  | Per-canonical-field rename + value mapping for the per-room payload entries. Keys are canonical field names the framework writes internally; values are {field_name, value_map} dicts that control how each field appears on the wire. Absent canonical keys fall back to identity (canonical name, no value transform). field_name=null omits the field entirely. |
| `room_fields.field_name` | `str \| null` | no |  | Wire field name to use for this canonical field. Set to null to omit the field from the payload entirely (for brands that don't expose it). |
| `room_fields.value_map` | `dict[str, Any] \| null` | no |  | Maps canonical string values to the brand-specific wire values. Lookup is by str(value) — booleans and other non-string canonical values are stringified before lookup. Values not in the map pass through unchanged. Set to null or omit for identity passthrough. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1197`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:557`.

*Read sites found by a conservative static scan (11; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:557`, `custom_components/eufy_vacuum/core/manager.py:3649`, `custom_components/eufy_vacuum/core/manager.py:5853`, `custom_components/eufy_vacuum/core/manager.py:6901`, `custom_components/eufy_vacuum/dispatch/manager.py:183`, `custom_components/eufy_vacuum/dispatch/manager.py:355`, `custom_components/eufy_vacuum/dispatch/manager.py:477`, `custom_components/eufy_vacuum/dispatch/manager.py:67` ...

## Capabilities

### `capabilities`

type `dict` - optional

Explicit capability flag declarations. Override or supplement the entity-presence-based capability detection in capabilities.py. For code adapters these are set from known hardware specs. For config adapters these are set by the user in the UI.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `supports_zone_clean` | `bool` | no |  |  |
| `supports_zone_repeat` | `bool` | no |  | Whether the zone-clean command accepts a repeat count. False (or omitted zone_passes_max/passes_max in dispatch) normalizes clean_times to 1 rather than shipping it verbatim. ⚠ BRANCH-SCOPED, AND DELIBERATELY SO (A6). This is read at exactly ONE site — dispatch/manager.py, inside the NON-device_mm branch. A `dispatch.zone_coords: device_mm` brand (Roborock app_zoned_clean) never consults it: that branch clamps with `min(clean_times, zone_passes_max or passes_max or 3)` regardless. THE SCOPING IS A STATED EDGE, NOT AN UNFINISHED WAVE: RP-022/RF-23 enumerated the hoist set as zone_max plus min/max area and side bounds, and closed with 'Roborock's device_mm clamp unchanged'; Q12 is likewise scoped to Eufy zones, verbatim, in the decision register and in the in-code comment. ⚠ DO NOT 'FINISH' IT BY CLAMPING repeat TO 1 ON device_mm. The two branches carry repeat differently: the else branch puts it in a NAMED field (`clean_times`), where 1 is a harmless no-op, while device_mm puts it as the 5th POSITIONAL element of every rect. A brand that genuinely accepts no repeat count needs a FOUR-element rect, so repeat=1 would still ship the element the declaration says does not exist — the hoist would not deliver the contract. |
| `zone_max` | `int` | no |  | Maximum number of zones accepted in a single dispatch. |
| `zone_max_side_m` | `float` | no |  | Max zone side length in metres (Eufy-style limit). |
| `zone_min_side_m` | `float` | no |  | Min zone side length in metres (Eufy-style limit). |
| `zone_max_area_m2` | `float` | no |  | Max zone area in m2 (Roborock-style limit). |
| `zone_min_area_m2` | `float` | no |  | Min zone area in m2 (Roborock-style limit). |
| `supports_mop_features` | `bool` | no |  |  |
| `supports_water_control` | `bool` | no |  |  |
| `supports_path_control` | `bool` | no |  |  |
| `supports_edge_mopping` | `bool` | no |  |  |
| `supports_mop_wash` | `bool` | no |  |  |
| `supports_mop_dry` | `bool` | no |  |  |
| `supports_empty_dust` | `bool` | no |  |  |
| `supports_robot_position` | `bool` | no |  |  |
| `supports_station_water` | `bool` | no |  |  |
| `position_lock_reliable` | `bool` | no |  |  |
| `rooms_unique_per_job` | `bool` | no |  |  |
| `supports_room_profiles` | `bool` | no |  | Whether the card shows the reusable room-PROFILES section. Default True. Set False for brands with a single editable per-room field (Roborock: fan only), where a profile would be degenerate — the editor hides the section. |
| `honors_clean_order` | `bool` | no |  | Whether the device cleans rooms in the dispatched queue order. Default True (Eufy send_command). Set False for brands that path-optimize and ignore the order (Roborock app_segment_clean, unless an order is set in the vacuum's app) — the card surfaces an 'order is advisory' note at run start. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1539`.

*Read sites found by a conservative static scan (5; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:832`, `custom_components/eufy_vacuum/core/manager.py:1803`, `custom_components/eufy_vacuum/core/manager.py:5873`, `custom_components/eufy_vacuum/dispatch/manager.py:193`, `custom_components/eufy_vacuum/jobs/active_job.py:1802`

### `live_transition`

type `dict` - optional

Live room-rollover orchestration. Controls how the framework advances the current room during a running job. Absent = the Eufy-style counter-plateau / timing heuristic over the job-segmenter engine.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `enabled` | `bool` | no |  | Whether live rollover runs at all. Default: True. False disables in-run room advancement (the job still finalizes). |
| `rollover_kinds` | `list[str]` | no |  | Which counter-boundary kinds advance the room for counter-driven brands (Eufy): subset of wash_plateau/transit/area_jump. Ignored when native_transition_source is set. |
| `native_transition_source` | `bool` | no |  | When True, rollover FOLLOWS the brand's native live-room signal (entities.active_cleaning_target — a room NAME, e.g. Roborock current_room) instead of the counter/timing heuristic: the signal is matched to a job TARGET room by name slug (transit rooms not in the job are ignored), the previous confirmed target is completed when the signal moves, and current is set directly to the new target (order-agnostic — the device path-optimizes). Assumes rooms_unique_per_job. Default: False (Eufy counter/timing path, untouched). |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1639`.

*Read sites found by a conservative static scan (1; a floor, not a complete set):* `custom_components/eufy_vacuum/jobs/active_job.py:1130`

### `external_mid_run_statuses`

type `list` - optional

task_status strings meaning the robot docked MID-run and will resume (mop wash / dust empty / recharge-resume). The external-run finalizer holds the run open while task_status is one of these instead of closing it at the dock, so a vacuum->mop run stays one multi-segment record.

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1683`.

*Read sites found by a conservative static scan (2; a floor, not a complete set):* `custom_components/eufy_vacuum/jobs/active_job.py:3189`, `custom_components/eufy_vacuum/learning/brand_facts.py:71`

## Settings Selects (External-Run Capture)

### `settings_selects`

type `dict` - optional

Global select entities that reflect the current room's per-room settings while a job runs. Used to recover per-room settings for app-started (external) jobs, which the integration did not dispatch. Maps a canonical setting key (clean_mode/fan_speed/water_level/clean_intensity/mop_intensity) to {entity_id, value_map}, where value_map (optional) normalizes raw firmware strings to canonical.

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1696`.

*Read sites found by a conservative static scan (2; a floor, not a complete set):* `custom_components/eufy_vacuum/core/manager.py:5963`, `custom_components/eufy_vacuum/jobs/active_job.py:2583`

## Maintenance Components

### `maintenance_components`

type `dict[str, dict]` - optional

Maintenance component catalog. Keyed by component ID. Defines which components the firmware exposes as replacement counters and their display metadata and interval configuration. Absent = maintenance view empty, degrades gracefully.

**Per-entry fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `sensor_suffix` | `str \| null` | yes |  | Full suffix appended to 'sensor.{object_id}_' to form the replacement counter sensor entity ID (e.g. 'filter_remaining' -> sensor.{object_id}_filter_remaining). Null when the component has no own counter and sources only via proxy_for. |
| `proxy_for` | `str \| null` | no |  | Component ID whose sensor this component sources from when present, falling back to this component's own sensor_suffix. Used when the firmware shares a counter between components (e.g. swivel_wheel proxies filter). |
| `reset_button` | `dict` | no |  | Resolves the upstream replacement-counter reset button. {'entity_suffixes': [str] appended to 'button.{object_id}_' tried in order; 'token_sets': [[str]] each an all-tokens-must-match registry fallback}. Absent = no reset button. |
| `default_interval_hours` | `float` | yes |  | Manufacturer guide recommendation. Never changes. Reference anchor for the user's configured interval. |
| `max_interval_hours` | `float` | yes |  | Ceiling for user-configured interval override. Set above default to allow light-use extension. |
| `label` | `str` | yes |  | Human-readable component name for display. |
| `icon` | `str` | yes |  | MDI icon string. |
| `maintenance_only` | `bool` | no |  | When True, surface the component only as a Maintenance item (integration-tracked interval), never as a Replacement row. For cleanables with no service-life replacement curve (e.g. the cleaning tray). Absent = False. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1711`.

*Read sites found by a conservative static scan (6; a floor, not a complete set):* `custom_components/eufy_vacuum/button.py:42`, `custom_components/eufy_vacuum/core/manager.py:1806`, `custom_components/eufy_vacuum/maintenance/manager.py:311`, `custom_components/eufy_vacuum/maintenance/manager.py:395`, `custom_components/eufy_vacuum/number.py:49`, `custom_components/eufy_vacuum/sensor/__init__.py:129`

## Upkeep Catalog

### `upkeep_catalog`

type `dict` - optional

Per-model upkeep guide catalog. Display data only — pure strings, no logic. The framework reads model_names to label the maintenance view, looks up the device's model code in model_guide_families to resolve which guide family to show, then renders the guide entries from guide_library for each component. Absent = upkeep view falls back to component labels only with no step-by-step instructions.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `guide_translations` | `dict` | no |  | Per-language upkeep guide bundles, keyed by language code. Both brands ship one; the set of languages is asserted by the adapter guide tests. |
| `model_names` | `dict[str, str]` | no |  | Maps device model code (as reported by the vacuum entity's 'detected_model' attribute) to a human-readable display name. Example: {'T2351': 'Robovac X10 Pro Omni'}. |
| `model_guide_families` | `dict[str, str]` | no |  | Maps device model code to a guide family key. Multiple models can share one family when their upkeep instructions are identical, keeping guide_library compact. Example: {'T2351': 'x10_pro_omni', 'T2261': 'x8_series'}. |
| `guide_family_names` | `dict[str, str]` | no |  | Maps guide family key to display name shown in the upkeep guide header. Example: {'x10_pro_omni': 'X10 Pro Omni'}. |
| `guide_library` | `dict[str, dict[str, dict]]` | no |  | Two-level dict: family_key → component_key → guide entry. Component keys must match maintenance_components keys (filter, side_brush, rolling_brush, dust_bag, mop_pad, sensor, etc.). Each guide entry has fields: clean_frequency (str), replace_frequency (str \| null), steps (list[str]), notes (list[str]). Absent component keys produce no card in the upkeep view. |

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1794`.

*Read sites found by a conservative static scan (3; a floor, not a complete set):* `custom_components/eufy_vacuum/maintenance/manager.py:204`, `custom_components/eufy_vacuum/maintenance/manager.py:241`, `custom_components/eufy_vacuum/maintenance/manager.py:398`

## Water Model Configs

### `water_model_configs`

type `dict[str, dict]` - optional

Per-model physical water-tank dimensions. Each entry maps a device model code to the measured hardware capacities. These are not calculated values — they must be measured on real hardware. The estimator reads these to convert tank-percent deltas into ml. Absent = water estimation falls back to flow-rate-only and cannot report actual tank-level deltas.

**Per-entry fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `robot_internal_tank_ml` | `float` | yes |  | Capacity of the robot's onboard water reservoir in ml, measured on real hardware. REPORTED ONLY: planning/run_plan.py::estimate_job_water_usage reads it once and echoes it straight into the returned estimate dict — no calculation consults it. ⚠ was: "Used to convert wash-frequency intervals into volume." — false; that arithmetic uses dock_wash_overhead_ml_per_cycle and the wash-cycle count, never this field. Still `required: True` on purpose (EST-CLAMP-1, stated at the read): every port measures it because folding it into the estimate — per-refill capping? overhead timing? — is a design question for a dedicated follow-up, not a one-line fix. Do not size or debug the water estimate against this number; it cannot move it. |
| `dock_clean_tank_capacity_ml` | `float` | no |  | Capacity of the dock's clean-water tank in ml. Omit for models with no dock clean tank (no mop station). Used to convert station_clean_water_percent deltas into ml. |
| `dock_wash_overhead_ml_per_cycle` | `float` | no |  | Measured water consumption per mop-wash cycle, in ml. Subtracted from the total dock-water delta to isolate the floor-mopping water from the post-job wash water. Omit for models with no dock wash cycle. |
| `water_rates` | `dict[str, float]` | no |  | Per-water-level flow rate in ml/min, keyed by the LOWERCASED canonical water level ('off'/'low'/'medium'/'high'). Overrides the framework's generic rate table when estimating a run's water use. Omit to use the generic table. Read by planning/run_plan.py. |
| `low_clean_water_margin_ml` | `float` | no |  | Dock clean-tank remaining, in ml, at or below which the run plan raises the 'low clean water' margin warning. Default 300.0 (Eufy dock tuning) -- the one water key that truly defaults rather than falling back to flow-rate-only. Read in planning/run_plan.py::estimate_job_water_usage (the water block). |

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1863`.

*Read sites found by a conservative static scan (1; a floor, not a complete set):* `custom_components/eufy_vacuum/planning/run_plan.py:334`

## Pluggable Engines + Late-Added Blocks

### `mapping`

type `dict` - optional

Pluggable MAP segmenter engine selection + tuning (doc 22 §13a). Engine name and tuning keys are validated at registration by registry._validate_adapter. Absent => the framework default engine.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1965`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:397`.

*Read sites found by a conservative static scan (5; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:397`, `custom_components/eufy_vacuum/core/manager.py:5917`, `custom_components/eufy_vacuum/core/manager.py:6334`, `custom_components/eufy_vacuum/diagnostics.py:384`, `custom_components/eufy_vacuum/mapping/mapping_services.py:1289`

### `map_state_source`

type `dict` - optional

Read the provider's own map segmentation instead of segmenting an image (doc 22 §13a.2). Absent => no provider-side room source.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1975`.

*Read sites found by a conservative static scan (10; a floor, not a complete set):* `custom_components/eufy_vacuum/diagnostics.py:897`, `custom_components/eufy_vacuum/listeners/pose_sampler.py:165`, `custom_components/eufy_vacuum/listeners/pose_sampler.py:294`, `custom_components/eufy_vacuum/listeners/stall_capture.py:102`, `custom_components/eufy_vacuum/mapping/map_source_coordinator.py:193`, `custom_components/eufy_vacuum/mapping/map_source_coordinator.py:405`, `custom_components/eufy_vacuum/mapping/map_source_coordinator.py:607`, `custom_components/eufy_vacuum/mapping/map_source_coordinator.py:649` ...

### `map_render`

type `dict` - optional

VA-owned client-side map render declaration (doc 22 §13a.3). Presence is the gate for supports_va_render — presence only; the interior is not validated. The gate is one line in core/manager.py::get_dashboard_snapshot (`supports_va_render = isinstance(_adapter_cfg.get("map_render"), dict)`), exported in that same snapshot dict. ⚠ was: "core/manager.py ~:4055", a line pointer that no longer lands on the gate. What :4055 held when that pointer was written is not recoverable without the sha it was written against, so this note does NOT say — an earlier draft of this correction guessed, and guessed wrong. Cite the function, not the line.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:1984`.

*Read sites found by a conservative static scan (2; a floor, not a complete set):* `custom_components/eufy_vacuum/core/manager.py:6040`, `custom_components/eufy_vacuum/mapping/map_source_coordinator.py:718`

### `device_clean_order`

type `dict` - optional

DEVICE-side clean order — the order the robot itself will clean rooms in, which on a path-optimising brand overrides its own optimisation. Absent (or enabled False) => the brand has no such concept: no read, and no clean-order sensor is created. `read.via` names the acquisition strategy and is the REPOINT SEAM (today only 'v1_debug_log'); an unimplemented via reads as unavailable, never as an empty order. Consumed by clean_order/manager.py.

*Declared by:* roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2001`.

*Read sites found by a conservative static scan (1; a floor, not a complete set):* `custom_components/eufy_vacuum/clean_order/manager.py:242`

### `job_segmenter`

type `dict` - optional

Pluggable JOB/run segmenter engine + threshold tuning (doc 22 §13a.1). NOTE: an absent block does NOT mean 'no segmentation' — the resolver falls back to the Eufy counter engine, not to noop. A brand that emits no counter signal must declare an explicit engine.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2014`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:429`.

*Read sites found by a conservative static scan (4; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:429`, `custom_components/eufy_vacuum/jobs/active_job.py:1428`, `custom_components/eufy_vacuum/jobs/phase_runner.py:1267`, `custom_components/eufy_vacuum/learning/brand_facts.py:93`

### `room_attribution`

type `dict` - optional

Pluggable room-attribution engine (doc 22 §13a.4) — decides which room a captured run segment belongs to. Absent => the Eufy anchor-winding engine, which a brand with no pose/anchor signal cannot satisfy.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2025`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:459`.

*Read sites found by a conservative static scan (4; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:459`, `custom_components/eufy_vacuum/learning/brand_facts.py:98`, `custom_components/eufy_vacuum/listeners/pose_sampler.py:132`, `custom_components/eufy_vacuum/listeners/pose_sampler.py:150`

### `room_profiles`

type `dict` - **required**

Adapter-declared room profile catalog / overrides (doc 22 §13d). REQUIRED: registration fails without it, and an empty dict fails too -- a brand with zero profile vocabulary can resolve nothing. Enforced in full by registry._validate_adapter.

*Declared by:* eufy, roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2035`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:506`.

*Read sites found by a conservative static scan (8; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:341`, `custom_components/eufy_vacuum/adapters/registry.py:506`, `custom_components/eufy_vacuum/profiles/manager.py:277`, `custom_components/eufy_vacuum/queue/queue_engine.py:264`, `custom_components/eufy_vacuum/rooms/room_defaults.py:113`, `custom_components/eufy_vacuum/rooms/vocabulary_migration.py:188`, `custom_components/eufy_vacuum/rooms/vocabulary_migration.py:210`, `custom_components/eufy_vacuum/sensor/profile.py:130`

### `anomaly`

type `dict` - optional

Anomaly-detection thresholds for run sanity checks (doc 22 §13c).

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2062`.

*Read sites found by a conservative static scan (1; a floor, not a complete set):* `custom_components/eufy_vacuum/jobs/active_job.py:1199`

### `wash_frequency_bounds`

type `dict` - optional

Bounds for the mop-wash cadence control, in minutes (doc 22 §17a). planning/run_plan.py reads these; the learning estimator historically hardcoded the Eufy X10 range instead.

**Fields**

| Key | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `default` | `float` | no |  |  |
| `min` | `float` | no |  |  |
| `max` | `float` | no |  |  |

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2070`.

*Read sites found by a conservative static scan (1; a floor, not a complete set):* `custom_components/eufy_vacuum/planning/run_plan.py:369`

### `cleaning_time_unit`

type `str` - optional

Unit of the vacuum's bare-number cleaning-time counter — "min" or "s" (doc 22 §14d). Roborock reports minutes; Eufy reports seconds. Omitted => the framework default. This is the ONE BrandFacts property only Roborock declares, so it is the seam most likely to be missed by an Eufy-anchored test.

*Declared by:* roborock. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2085`.

*Read sites found by a conservative static scan (3; a floor, not a complete set):* `custom_components/eufy_vacuum/jobs/active_job.py:2434`, `custom_components/eufy_vacuum/learning/brand_facts.py:77`, `custom_components/eufy_vacuum/listeners/job_metrics.py:127`

### `model_family`

type `str` - optional

Coarse hardware family (e.g. "x10", "s6") used to select model-specific behavior and maintenance catalogs. Shipped by the Eufy adapter and consumed by capability detection; previously undeclared in both the schema and doc 22.

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2096`.

*Read sites found by a conservative static scan (2; a floor, not a complete set):* `custom_components/eufy_vacuum/core/manager.py:1794`, `custom_components/eufy_vacuum/core/manager.py:1878`

### `capability_hints`

type `dict` - optional

Explicit capability declarations fed INTO runtime detection (core/capabilities.detect_capabilities). Distinct from the `capabilities` block above, which is the adapter's own declared capability set — the two share key names but are different dictionaries with different consumers. ⚠ A HINT IS NOT UNIFORMLY AUTHORITATIVE, AND THIS SAID IT WAS UNTIL 2026-08-24 (A4). detect_capabilities applies TWO rules, and which one a key gets is not visible from here. AUTHORITATIVE (`_hint_wins` — a declared False is binding): supports_water_control, supports_edge_mopping, supports_passes, supports_custom_room_config, supports_room_clean, supports_zone_clean. PERMISSIVE (hint OR live entity presence — a declared False is OVERRIDDEN when the entity resolves): supports_mop_features, supports_mop_wash, supports_mop_dry, supports_empty_dust, supports_path_control, has_attribute_rooms. So a porter declaring `supports_mop_wash: False` for a brand that categorically cannot wash a mop is silently overridden the moment a wash-mop button resolves by name-token match on any sibling entity. THE SPLIT IS BY DESIGN, not a defect: the code's own comment reserves `_hint_wins` for 'capabilities a brand can categorically NOT do'. What was wrong is only this description claiming the strong rule for all twelve. If a permissive key needs to become binding for your brand, move it into the `_hint_wins` set rather than declaring False and expecting it to hold.

*Declared by:* eufy. *Source:* `custom_components/eufy_vacuum/adapters/config_schema.py:2106`. *Registration check:* `custom_components/eufy_vacuum/adapters/registry.py:532`.

*Read sites found by a conservative static scan (2; a floor, not a complete set):* `custom_components/eufy_vacuum/adapters/registry.py:532`, `custom_components/eufy_vacuum/core/manager.py:1795`
