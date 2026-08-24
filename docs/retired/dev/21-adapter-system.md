# 21 — Adapter System

> **Scope:** Complete implementation reference for the adapter subsystem: `adapters/registry.py` (AdapterCoordinator + shim functions), `adapters/config_schema.py` (ADAPTER_CONFIG_SCHEMA), `adapters/config_loader.py` (stored adapter loading), and `adapters/eufy/adapter.py` (Eufy reference implementation). Every registry pattern, schema block, and config-loading path is derived directly from the source.

---

## 1. Overview

The adapter system is the **brand abstraction layer**. Every piece of brand-specific knowledge — entity naming, vocabulary, completion signals, dispatch templates, discovery config, maintenance component definitions — lives in an adapter config dict registered with the adapter registry. The framework never hard-codes brand names or entity ID patterns.

**Module roles:**

| Module | Role |
|---|---|
| `adapters/registry.py` | Stores registered configs; provides both class-based (new) and shim (legacy) access surfaces |
| `adapters/config_schema.py` | `ADAPTER_CONFIG_SCHEMA` — the authoritative definition of every valid adapter field |
| `adapters/config_loader.py` | Loads stored adapter configs from integration storage at startup |
| `adapters/eufy/adapter.py` | Assembles and registers the Eufy X10 Pro Omni adapter — the reference implementation |
| `adapters/roborock/adapter.py` | Assembles and registers the Roborock adapter (S6 first profile) — the second shipping brand |

**Two brands ship today.** Eufy is the full-feature reference; Roborock is the
second concrete adapter, **auto-detected** per vacuum in `__init__.py` by
manufacturer/model (manufacturer `Roborock` / model prefix `roborock.`) so a
mixed household wires each correctly with no user input. Roborock fills the same
schema out completely differently (native `get_maps` discovery, renumbering
segment ids, path-optimized order, a live map image, a native current-room
signal) — it's the [Eufy worked example](25-eufy-adapter.md)'s foil, documented
in [29-roborock-adapter](29-roborock-adapter.md).

---

## 2. Registry (`registry.py`)

### 2.1 AdapterCoordinator

`AdapterCoordinator` is instantiated once per config entry in `__init__.py::async_setup_entry`. It sets itself as the module-level `_active_coordinator` pointer on creation, enabling the legacy shim functions to route through it.

```python
coordinator = AdapterCoordinator(hass, entry)   # sets _active_coordinator
coordinator.register_adapter_config(vacuum_entity_id, config)
coordinator.get_adapter_config(vacuum_entity_id) -> dict | None
coordinator.get_all_adapter_configs() -> dict[str, dict]
coordinator.unregister_adapter_config(vacuum_entity_id) -> None
coordinator.clear_registry()               # empties this coordinator's _registry
coordinator.get_adapter_value(vacuum_entity_id, *path, fallback=None) -> Any
coordinator.shutdown()               # clears _active_coordinator
```

The coordinator owns its own `_registry: dict[str, dict]` dict, separate from the module-level `_REGISTRY` fallback. `get_active_coordinator()` (module level, `registry.py::get_active_coordinator`) returns the active coordinator or `None`, for code paths that prefer the coordinator API but must handle the pre-setup / test-fixture case.

### 2.2 Validation

`register_adapter_config()` calls `_validate_adapter()` before storing:

```python
_validate_adapter(config: dict) -> list[str]   # returns a list of issue strings
```

`_validate_adapter()` returns a list of human-readable issue strings (empty = valid); it does **not** raise itself. What `register_adapter_config()` does with a non-empty issues list is **source-dependent** (RP-033/RF-32, `registry.py::register_adapter_config` on the coordinator method, mirrored at `:570-592` on the bare-function fallback shim):

- **`source == "config"`** (a stored, UI/service-authored config): hard-raises `ServiceValidationError`. A broken stored config used to register cleanly and shadow the live adapter, with every block it omitted silently falling through to that block's own absent-default (Eufy-shaped) behaviour.
- **`source == "code"`** (the two shipped brand adapters, registered at startup): every issue is logged as a `warning` and the config is stored anyway — both pass validation cleanly today, but a future code-adapter regression must degrade to a warning rather than take every install's startup down with it.
- A non-dict `config` raises `TypeError` regardless of source (and `_validate_adapter()` returns the single issue `"adapter config must be a dict"`) — always was structurally unusable.

Both the coordinator method and the bare-function fallback shim implement the same source-based behavior. **Only on the non-raising paths** — no issues at all, or issues on a `source == "code"` config — registration goes on to run two standalone **advisories** (warn-only, never raise, both source types): `_warn_eufy_fallbacks` (names each engine block the adapter did not declare and the Eufy default that takes over — see §7.1) and `_warn_completion_gate_orphan` (`registry.py::_warn_completion_gate_orphan`, RP-033/COMMON-2: `completion.require_job_active_clear` set without `entities.job_active` declared — the flag has no runtime effect and completion falls back to the sentinel check). On the `source == "config"` hard-raise path, the raise happens before either advisory call — a rejected stored config never gets an advisory, only the raised error.

Current checks:

- **`mapping` block** (when present): must be a dict; `mapping.segmenter_engine` is required and must resolve to a known engine (`known_engine_names()` in `mapping/segmenter_engines.py`); `mapping.segmenter_tuning` must pass the resolved engine's own `validate_tuning()`.
- **`job_segmenter` block** (when present): must be a dict; `job_segmenter.engine` is required and must resolve to a known job/run segmenter engine (`known_job_engine_names()` in `learning/job_segmenter_engines.py`); `job_segmenter.tuning` must pass the resolved engine's own `validate_tuning()`. This mirrors the `mapping` check (deferred import). Note this is the **counter/run** segmenter seam, distinct from the **map** segmenter `mapping` block above (see §2.4).
- **`room_attribution` block** (when present): must be a dict; `room_attribution.engine` is required and must resolve to a known room-attribution engine (`known_room_attribution_names()` in `learning/room_attribution_engines.py`); `room_attribution.tuning` must pass the resolved engine's own `validate_tuning()`. This mirrors the `job_segmenter` check (deferred import). An absent block falls back to the Eufy engine (`eufy_anchor_winding_v1`); declare `noop_room_attribution` to disable external-run auto-attribution. This is the external-run room-attribution seam (see §2.4).
- **`room_profiles` block** — **REQUIRED**, unlike every other block on this list. An adapter that declares none, or declares an empty one, fails registration: core carries no profile catalog, so such an adapter cannot resolve a single room. The message names the keys. Within the block, `default_profile` (when set) must be a string and each of `builtins`, `custom_template`, `legacy_aliases`, `floor_type_water_defaults`, `floor_type_fan_defaults`, `normalize_defaults` (when set) must be a dict.

  **The gate is the block, not each key.** A porter who declared `builtins` and stopped has engaged with the contract, and their undeclared keys resolve EMPTY — a defined answer, not an inherited one. Only declaring NOTHING means "not written yet", which is the one state worth failing on. Declaring a key empty (`legacy_aliases: {}`, as Roborock does) is a legitimate statement that this brand supplies none, and is deliberately distinguishable from omitting it.
- **`dispatch.template`** (when present): must resolve to a registered dispatch engine (`known_dispatch_templates()` in `queue/dispatch_engines.py`). A schema-valid template with no registered engine yet is flagged rather than silently falling back to the Eufy shape.
- **`capability_hints` block** (when present, `registry.py::_validate_adapter`): must be a dict; every key must be in `core/capabilities.py::KNOWN_CAPABILITY_HINTS` — an unrecognised hint key is a silent no-op at read time (`_hints.get(name)` misses), so a typo is caught here instead of at "why is this control showing?".
- **`dispatch.phase_timing`** (when present, `registry.py::_validate_adapter`, RP-033/WD-5): must be a dict; every numeric value must be **positive** (a 0 poll interval busy-loops; 0 `max_attempts` means the watchdog never tries). This is an earlier check on the same values `core/manager.py::_phase_timing`'s own `_minimums` clamp guards at runtime — the runtime clamp stays as defense-in-depth.
- **`setup.steps`** (when present, `registry.py::_validate_adapter`, RP-033/SETUP-9): every step id must be in the allowed set, which is read from `ADAPTER_CONFIG_SCHEMA["setup"]["fields"]["steps"]["values"]` itself (not re-declared) so the two cannot drift. This makes the schema description's "unknown step IDs reject the adapter at registration" (`config_schema.py::ADAPTER_CONFIG_SCHEMA`) actually true for a stored config; still warn-only for a code config, per the source-based behavior above.

### 2.3 Legacy shim functions (module level)

For backward compatibility, module-level functions route to `_active_coordinator` if set, otherwise fall back to the module-level `_REGISTRY` dict (used in tests and pre-coordinator paths):

```python
register_adapter_config(vacuum_entity_id, config)
get_adapter_config(vacuum_entity_id) -> dict | None
get_all_adapter_configs() -> dict[str, dict]
unregister_adapter_config(vacuum_entity_id) -> None
clear_registry() -> None
get_adapter_value(vacuum_entity_id, *path, fallback=None) -> Any
```

`get_adapter_value(*path)` does nested dict traversal: each path segment indexes one level deeper. Returns `fallback` on any `KeyError` or `TypeError`.

**`adapter_honors_clean_order(vacuum_entity_id) -> bool`** (module level, `registry.py::adapter_honors_clean_order`) is **the one read** of `capabilities.honors_clean_order`. Four modules ask the question, six call sites total: `core/manager.py` (bounds-exit gate, `:4078`; snapshot export, `:5029`), `jobs/active_job.py` (anomaly gates, `:1058`), `jobs/phase_runner.py` (segmented-vs-apportioned per-room timings, `:1234`), `planning/run_plan.py` (advisory-order note, `:756`; strict-order split, `:811`) — one of them used to answer it differently. Contract: **only a literal `False` means "does not honor order"** — absent / `None` / a non-dict `capabilities` block all resolve to the default `True`, because a false "does not honor order" sends confidently-wrong evenly-apportioned per-room baselines into learning.

### 2.4 Pluggable engine seams

Four brand-specific subsystems are pluggable behind the **same seam shape**: a `Protocol`, a module-level registry dict, a `get_*()` resolver with a fallback, a `known_*()` enumerator for the validator, an adapter config block that names the engine, and a `_validate_adapter` rule. The adapter declares *which* engine; the framework owns *resolution and the cross-engine contract*. This is how a second brand swaps brand-specific behavior without touching the framework call sites.

| Seam | Module | Protocol | Registry / resolver | Adapter block | Fallback | `select`-style framework function |
|---|---|---|---|---|---|---|
| **Map segmenter** | `mapping/segmenter_engines.py` | `MapSegmenter` | `_SEGMENTER_ENGINES` / `get_segmenter_engine()` | `mapping` (`segmenter_engine` + `segmenter_tuning`) | `noop_fallback` (empty result) | — |
| **Dispatch engine** | `queue/dispatch_engines.py` | `DispatchEngine` | `_DISPATCH_ENGINES` / `get_dispatch_engine()` | `dispatch` (`template` + field map; see "Dispatch-engine specifics" below) | `eufy_room_clean` | — |
| **Job/run segmenter** | `learning/job_segmenter_engines.py` | `JobSegmenter` | `_JOB_SEGMENTER_ENGINES` / `get_job_segmenter_engine()` | `job_segmenter` (`engine` + `tuning`) | `eufy_counter_v1` | `counter_segmentation.select_active` |
| **Room attribution** | `learning/room_attribution_engines.py` | `RoomAttributionEngine` | `_ROOM_ATTRIBUTION_ENGINES` / `get_room_attribution_engine()` | `room_attribution` (`engine` + `tuning`) | `eufy_anchor_winding_v1` | — |

**Two segmenters, different jobs — do not conflate them.** The **map** segmenter (`eufy_cv_v1`, the Eufy CV pipeline in `adapters/eufy/segmentor.py`) turns a *map image* into polygonal room overlays. The **job/run** segmenter (`eufy_counter_v1`) turns a *counter-sample stream* (`cleaning_time` / `cleaning_area`) into ordered per-room boundaries within a single run — no geometry. They are independent seams with independent registries.

**Job-segmenter specifics** (`learning/job_segmenter_engines.py`):

- **Eufy fallback, not noop.** Unlike the map seam (whose `get_segmenter_engine()` falls back to `noop_fallback`), `get_job_segmenter_engine()` falls back to the **Eufy** engine (`_FALLBACK_JOB_ENGINE = "eufy_counter_v1"`) for an absent/unknown name — same policy as the dispatch seam. The framework's historical no-adapter default is Eufy counter segmentation, and live rollover + learned history must keep working byte-for-byte; a noop fallback would silently stop live rollover. `NoopJobSegmenter` (`"noop_job_fallback"`) stays registered for a future brand with no segmentable signal, but it is **not** the fallback.
- **`select_active` stays a framework function, not on the engine.** The job pipeline is three stages — `find_candidates → select_active → build_segments`. The engine owns the two *brand-specific* stages (`find_candidates`, `build_segments`) plus the legacy one-shot composition `segment_legacy`. `select_active` is pure ranking/filtering over the candidate *shape* (`kind`/`confident`/`strength`/`id`), so it is brand-agnostic and stays a direct framework import (`counter_segmentation.select_active`) — the external-review wizard's count/toggle re-selection logic is then uniform across brands.
- **Cross-engine contract.** The `JobBoundaryCandidate` and `JobSegment` `TypedDict`s are the canonical shape every engine emits (the exact field union the counter primitives already produce). `EufyCounterSegmenter` delegates verbatim to the `counter_segmentation` primitives, and its `DEFAULT_TUNING` (`gap_delayed_s` 35, `gap_transit_s` 60, `gap_plateau_s` 90, `area_jump_m2` 2.0, `cadence_s` 30, `stall_wall_s` 600) is defined *by reference* to that module's constants, so the Eufy path can't drift.
- **The Eufy `kind` vocabulary** (`"wash_plateau"` / `"transit"` / `"area_jump"` / `"weak"`) is produced by `find_candidates` and referenced at the Eufy-specific call sites (live `rollover_kinds`, the legacy `{"wash_plateau","area_jump"}` filter). A future brand supplies its own engine *and* its own kind literals at those sites — the documented extension point; no kind indirection is built into the seam.

**Dispatch-engine specifics** (`queue/dispatch_engines.py`):

- **Beyond `template` + field map, a dispatch engine also declares its job model.** `DispatchEngine.job_model` is `"atomic_batch"` (one dispatch of a fixed room set — the default, mixed in by `_SinglePhaseMixin`) or `"sequenced"` (a logical job is an ordered list of phases, each its own dispatch that finalizes like a one-room atomic sub-job). `build_phases()` returns the ordered per-phase payload envelopes; the default is a single phase == `build_payload()` output, so an atomic engine is exactly a one-phase sequenced engine and the framework treats both uniformly.
- **`build_phases(strict_order=True)` turns a flat-id engine into a per-room sequenced job.** A flat-id batch shape (`generic_room_ids` / its `roborock_segment_clean` naming subclass) path-optimizes and *ignores* the dispatched order for a multi-room batch. With `strict_order` set, `GenericRoomIdsEngine.build_phases()` instead emits one single-segment phase per resolved room in queue order — the sequenced job model then cleans them strictly in order, and each phase carries its own room's passes (the batch path otherwise collapses passes to one max-wins value). This is the shipping Roborock opt-in (`dispatch_engines.py:79-98, 219-281, 284`).
- **Per-phase watchdog timing is adapter-declarable.** The framework re-dispatches each strict-order phase from a background task (the device just docked after the previous room and ignores a clean sent at that instant) and verifies it actually started, retrying if not — the retry loop doubling as the per-phase watchdog. The timing knobs live under `dispatch.phase_timing`: `settle_seconds` / `dock_settle_seconds` / `verify_seconds` / `confirm_seconds` / `poll_seconds` + `max_attempts`. `core/manager.py::_phase_timing` merges the adapter's declared overrides over the in-core `_PHASE_*` defaults *per key*, so a brand whose post-dock transient differs declares only what it needs and anything omitted stays byte-identical to the defaults. The whole mode is gated on `capabilities.honors_clean_order` being `False` (a path-optimizing brand); an order-honoring brand like Eufy never enters it.
- **The strict-order phase logic lives in `jobs/phase_runner.py::PhaseRunner` (bundled subsystem), not the manager.** The phase advance/finalize decision at the completion hook is `PhaseRunner.maybe_advance_phase`; `EufyVacuumManager.maybe_advance_phase` is a one-line delegator that calls it. The watchdog itself — the background re-dispatch + settle/verify/retry loop and per-phase timing capture (`_run_advanced_phase`, `_await_phase_started`, `_dispatch_active_phase`, `_vacuum_started_cleaning`) — is also on `PhaseRunner` (constructed as `self.phase_runner`). What stays on `core/manager.py` is only the timing config: the `_PHASE_*` module constants and the `_phase_timing` resolver `PhaseRunner` reads.

For the per-field documentation of `dispatch` (including `phase_timing` and the strict-order keys) see [Adapter config reference](22-adapter-config-reference.md) §13.

---

## 3. Config Schema (`config_schema.py`)

`ADAPTER_CONFIG_SCHEMA` is a single dict defining all valid top-level blocks. It has **32** top-level keys. The 21 originally-declared blocks:

| Block | Description |
|---|---|
| `adapter_id` | str — unique brand identifier |
| `source` | `"code"` or `"config"` |
| `display_name` | Human-readable adapter name |
| `brand` | Short brand/app name the card uses in copy (generic phrasing when absent) |
| `entities` | Entity ID map (25 entity keys) |
| `vocabulary` | State string sets and card dropdown options |
| `completion` | Completion signal configuration |
| `charging` | Charging detection configuration |
| `error_tracking` | Error channel configuration |
| `dock_events` | Dock event recording configuration |
| `post_job_wash_amendment` | Post-job mop-wash amendment configuration |
| `discovery` | Room discovery source and cadence |
| `setup` | Adapter-specific setup step list |
| `dispatch` | Room-clean command template and field mapping |
| `capabilities` | Detected capability flags |
| `live_transition` | Live room-rollover orchestration (`enabled` / `rollover_kinds` / `native_transition_source`) |
| `external_mid_run_statuses` | `task_status` strings = robot docked mid-run and will resume (holds the external run open instead of closing at the dock) |
| `settings_selects` | Global select entities for the device's live per-room settings — canonical key → `{entity_id, value_map}`. TWO consumers: external (app-started) run recovery, and the zone-clean panel's live controls via `get_dashboard_snapshot.setting_entities` ([22 §14b](22-adapter-config-reference.md)) |
| `maintenance_components` | Consumable component definitions |
| `upkeep_catalog` | Per-model upkeep guide library |
| `water_model_configs` | Tank capacity and water usage constants |

— plus **11 late-declared blocks** (RP-033/RF-32 closed the "shipped before declared" gap; `test_no_undeclared_top_level_keys` now asserts a future block cannot ship undeclared):

| Block | Description |
|---|---|
| `mapping` | Pluggable **map** segmenter engine + tuning (interior validated at registration, §2.2) |
| `map_state_source` | Read the provider's own map segmentation instead of segmenting an image |
| `map_render` | VA-owned client-side map render; **presence** gates `supports_va_render` (`core/manager.py::get_dashboard_snapshot`) |
| `job_segmenter` | Pluggable job/run segmenter engine + tuning (absent ≠ noop — Eufy fallback, §2.4) |
| `room_attribution` | Pluggable external-run room-attribution engine (absent → Eufy anchor-winding fallback) |
| `room_profiles` | Adapter-declared room-profile catalog / overrides |
| `anomaly` | Run-anomaly detection thresholds |
| `wash_frequency_bounds` | Mop-wash cadence bounds in minutes (`default`/`min`/`max` fields) |
| `cleaning_time_unit` | str — unit of the bare-number cleaning-time counter (`"min"` Roborock, `"s"` Eufy default) |
| `model_family` | str — coarse hardware family, stored so a capability refresh reproduces startup inputs |
| `capability_hints` | Hints fed INTO `detect_capabilities` — distinct from `capabilities` (same key names, different dicts/consumers); a hint is authoritative over the derived default |

The nine engine/open-ended blocks (`settings_selects`, `mapping`, `map_state_source`, `map_render`, `job_segmenter`, `room_attribution`, `room_profiles`, `anomaly`, `capability_hints`) are declared as bare `dict`s with no nested `fields` — their interiors are validated at registration by `_validate_adapter` where a rule exists (§2.2), and enumerating them wrongly in the schema would produce false conformance failures. `discovery.implicit_map_id` and `dispatch.zone_command`/`dispatch.zone_coords` are also schema-declared now (they were once schema-absent).

**Required blocks:** only `adapter_id`, `source`, `entities`, and `dispatch` are `required: True` in the schema. Enforcement is split: `_validate_adapter()` at registration still does **not** check required fields (code-flag CS-1, narrowed), but the **schema walker** now runs at runtime on the stored-config save path — see below.

> **The schema walker is production code now (RP-033/RF-32).** `validate_against_schema(config, schema, path="")` + the bound entry point `validate_adapter_config(config)` live in `config_schema.py` itself (`config_schema.py::validate_against_schema`; extracted from the test suite's pytest-only `_validate`), and `services/adapter_config.py::_handle_save_adapter_config` calls `validate_adapter_config()` **before** persisting/registering a stored config (`services/adapter_config.py::_handle_save_adapter_config`) — one implementation backs both the tests and the save path. The walk checks required keys, type families, enum `values` membership, nested `fields`, per-entry `entry_fields`, **and unknown keys** (RC-1) at every level where the schema enumerates a shape — the nine bare-`dict` blocks above are legitimately open-ended and skip the unknown-key check there. Keys whose name starts with `_` are exempt everywhere (RP-033/VAC-3): the code adapters stash adapter-internal bookkeeping there (e.g. Eufy's full `_entity_candidates` probe dict, kept so a capability refresh can re-probe multi-candidate keys).

### 3.1 `entities` block (25 keys)

| Key | Domain | Description |
|---|---|---|
| `task_status` | sensor | Vacuum task/operation state |
| `dock_status` | sensor | Dock station state |
| `active_map` | sensor | Currently active map ID |
| `active_cleaning_target` | sensor | Room(s) currently being cleaned |
| `cleaning_time` | sensor | Total cleaning duration in seconds |
| `cleaning_area` | sensor | Total area cleaned in m² |
| `battery` | sensor | Battery percentage |
| `error_message` | sensor | Current error message |
| `charging` | binary_sensor | Is the vacuum currently charging? |
| `wash_frequency_mode` | select | Mop wash frequency mode |
| `wash_frequency_value_time` | number | Mop wash frequency value (minutes) |
| `dry_duration` | select | Mop dry duration setting |
| `water_level` | sensor or select | Station water level |
| `robot_position_x` | sensor | X coordinate (vacuum space) |
| `robot_position_y` | sensor | Y coordinate (vacuum space) |
| `work_mode` | sensor | Current work/drive mode |
| `cleaning_intensity` | select | Suction/cleaning intensity |
| `scene_select` | select | Vendor-app scenes select (eufy-clean `select.<object_id>_scene`); options are saved app scenes and selecting one runs it immediately; surfaced on the dashboard snapshot for the card's App-scenes run-launcher; absent (Roborock) hides the group. |
| `job_active` | binary_sensor | On while a job runs (Roborock only). Drives `completion.require_job_active_clear` — the brand's terminal signal |
| `mop_active` | binary_sensor | Mop is attached/active (Roborock only) |
| `last_clean_end` | sensor | Timestamp the device stamps on a clean-summary write. **Observability only** — never gates completion; read by the issue-#46 observation trace + diagnostics, deliberately absent from the lifecycle watch list |
| `total_cleaning_area` | sensor | Lifetime cleaned-area counter (diagnostic only) |
| `total_cleaning_time` | sensor | Lifetime cleaning-time counter (diagnostic only) |
| `total_cleaning_count` | sensor | Lifetime completed-job counter (diagnostic only) |
| `dock_firmware_version` | sensor | Dock firmware version (diagnostic only) |

> The seven keys at the bottom shipped in the adapters before the schema declared them (former code-flag CS-2, now closed): the schema carries all 25, all optional (neither brand ships the full set), with types read from the adapters. `entities.job_active` in particular is the key `completion.require_job_active_clear` needs — registering that flag without it now triggers the `_warn_completion_gate_orphan` advisory (§2.2).

### 3.2 `vocabulary` block

State string sets (all normalized to lowercase before matching unless noted):

| Key | Type | Description |
|---|---|---|
| `hard_service_states` | list[str] | Dock states that block manual actions |
| `drying_states` | list[str] | Dock states that indicate active drying |
| `active_run_task_states` | list[str] | Task states that count as "active run" |
| `not_error_sentinels` | list[str] | error_message values that mean "no error" |
| `blocked_work_mode_states` | list[str] | Work modes that block queue-engine jobs |
| `blocked_task_status_states` | list[str] | Task status values that block queue-engine jobs |
| `blocked_dock_status_states` | list[str] | Dock status values that block queue-engine jobs |
| `cancel_service_exclusion_states` | list[str] | Task status values that explain early return as service (not cancel) |
| `cancel_detection_states` | dict[str, Any] | Normalized task_status transition strings the cancel detector matches: `active` (cleaning state — string or list), `returning` (return-to-dock state), `paused`; a cancel is active→returning or paused→returning |
| `water_level_aliases` | dict[str, str] | Brand display strings → canonical water level keys |
| `wash_frequency_mode_aliases` | dict[str, str] | Brand display strings → canonical frequency keys |
| `clean_mode_aliases` | dict[str, str] | Brand clean-mode display strings → canonical codes (e.g. `"vacuum and mop"` → `vacuum_mop`) the card vocab is keyed on |
| `clean_intensity_aliases` | dict[str, str] | Brand clean-intensity display strings → canonical codes (may be empty when values already slug to the code) |
| `fan_speed_aliases` | dict[str, str] | Brand suction/fan-speed display strings → canonical codes (e.g. `"boostiq"` → `boost`) |
| `clean_mode_options` | list[{value, label}] | Card dropdown options for clean mode |
| `fan_speed_options` | list[{value, label}] | Card dropdown options for fan speed |
| `water_level_options` | list[{value, label}] | Card dropdown options for water level |
| `clean_intensity_options` | list[{value, label}] | Card dropdown options for clean intensity |

### 3.3 `dispatch` block

Controls how room-clean commands are assembled:

| Field | Eufy value | Description |
|---|---|---|
| `template` | `"eufy_room_clean"` | Which payload template to use |
| `service_domain` | `"vacuum"` | HA service domain |
| `service_name` | `"send_command"` | HA service name |
| `command` | `"room_clean"` | Command string within the service call |
| `map_id_field` | `"map_id"` | Top-level payload field for map ID |
| `map_id_type` | `"int"` | Cast map_id to this type before sending |
| `room_id_field` | `"id"` | Per-room field for room ID |
| `clean_passes_field` | `"clean_times"` | Per-room field for clean passes |
| `rooms_field` | `"rooms"` | Top-level payload field for rooms array |
| `room_fields` | dict | Per-room field renames and value_map transforms |

> **Not exhaustive** — the schema declares **20** `dispatch` fields; the 10 omitted here are the Roborock/sequenced dispatch model plus the zone/live knobs: `params_as_list`, `passes_is_global`, `resolve_live_ids_by_slug`, `per_room_live_settings`, `global_pre_calls`, `passes_max`, `zone_command`, `zone_coords`, `phase_timing` (validated positive at registration, §2.2), `live_room_refresh`. Also note `map_id_type`'s **schema default is `"str"`** — Eufy's `"int"` above is its own value, not the default. Full field-by-field spec: [22-adapter-config-reference §13](22-adapter-config-reference.md).

**`room_fields` entry:**
```python
{
    "fan_speed": {
        "field_name": "fan_speed",   # target field name in the API payload
        "value_map":  None,          # None = pass-through; dict = rename values
    }
}
```

**Built-in dispatch templates:**

| Template | Brand | Payload shape |
|---|---|---|
| `eufy_room_clean` | Eufy | `{map_id, rooms: [{id, clean_times, fan_speed, ...}]}` |
| `roborock_segment_clean` | Roborock | Segment-ID based |
| `dreame_room_clean` | Dreame | Dreame-specific |
| `generic_room_ids` | Any | Room ID list only |

### 3.4 `maintenance_components` block

Dict keyed by component_id. Each entry:

| Field | Type | Description |
|---|---|---|
| `sensor_suffix` | str \| None | Suffix used to build the upstream sensor entity ID |
| `proxy_for` | str \| None | If set, this component aliases another component's sensor |
| `default_interval_hours` | float | Factory replacement interval |
| `max_interval_hours` | float | Maximum allowed user-override interval |
| `label` | str | Display name |
| `icon` | str | MDI icon |
| `reset_button` | dict \| None | Upstream replacement-counter reset button resolution (`entity_suffixes` + `token_sets`); absent = no reset button |
| `maintenance_only` | bool | (absent → False) Suppresses the Replacement row + attention roll-up; subject to the family gate (see [13-maintenance §4.3](13-maintenance-manager.md)) |

(Roborock coerces `default_interval_hours`/`max_interval_hours` to `0.0` when absent, and omits `reset_button` entirely for guide-only cleanables. Its former non-schema `remaining_is_state` flag was **removed** 2026-07-30 — it was declared `True` on only 4 of the 12 components, projected (with a `False` default) onto all 12 in the registered config, with zero readers; re-add it *with* its consumer if the "Wave 1b" device-countdown model ever ships.)

### 3.5 `capabilities` block

Boolean flags set by `detect_capabilities()` at adapter registration time:

| Flag | Description |
|---|---|
| `supports_mop_features` | Vacuum has mop hardware |
| `supports_water_control` | Water level can be programmatically set |
| `supports_path_control` | Cleaning path type can be set |
| `supports_edge_mopping` | Edge mopping setting is available |
| `supports_mop_wash` | Dock can auto-wash the mop |
| `supports_mop_dry` | Dock can auto-dry the mop |
| `supports_empty_dust` | Dock can auto-empty the dustbin |
| `supports_robot_position` | Position X/Y sensors are present |
| `supports_station_water` | Station water level sensor is present |

**Derivation** (`detect_capabilities`, `core/capabilities.py::detect_capabilities`). Only **two** of the nine are pure entity-presence; the rest are hint-OR-presence or hint-overridable defaults:

- **hint OR entity present** (True from *either* source): `supports_mop_features` (water-level entity), `supports_mop_wash`, `supports_mop_dry`, `supports_empty_dust`, `supports_path_control` (cleaning-intensity entity). The hint comes from the adapter's `capability_hints` (model-family driven, §5.2 step 3) — so on a **model-known** device these read `True` **even when the entity is absent**.
- **pure entity presence**: `supports_robot_position` (position X/Y sensors), `supports_station_water` (station water sensor).
- **hint wins, else derived** (`_hint_wins`, `capabilities.py::_hint_wins` — an explicit `capability_hints` entry **overrides** the derived/default value, so a brand can categorically declare `False`; a name absent from the hints dict falls through to the derived value): `supports_water_control` (derived value = `supports_mop_features`; never entity-probed), and the default-`True` group `supports_edge_mopping`, `supports_passes`, `supports_custom_room_config`, `supports_room_clean`, `supports_zone_clean` (the latter four aren't in the table above but are in the return). These were formerly hardcoded `True` — unreachable by any adapter, which is exactly how `supports_edge_mopping` stayed True for a brand declaring it False.
- **`supports_water_control` is NOT how the Roborock S6 ends up `False`.** Roborock's `capability_hints` dict (`adapters/roborock/adapter.py#CN1R6FC7`) declares six flags (`supports_mop_features`, `supports_mop_wash`, `supports_mop_dry`, `supports_empty_dust`, `supports_path_control: False`, `supports_edge_mopping: False`) and none of them is `supports_water_control`. `supports_edge_mopping: False` is hinted there *in addition to* the config-block declaration below, because the room-payload gate reads the runtime-detected capabilities payload, not the config block. The S6's `False` is set directly in the adapter's own shipped `capabilities` config block (`adapters/roborock/adapter.py#CN0QXDWS`, `"supports_water_control": mop_settable`), which is a separate dict from `detect_capabilities()`'s return and can diverge from it field-by-field.
- **attribute-mode rooms**: `supports_rooms`/`supports_segments` are True from an `active_map` entity **or** the `has_attribute_rooms` hint (scalar/Tuya devices expose rooms as a vacuum attribute with no map sensor); `supports_active_map` stays strictly entity-gated.

**Entity resolution appends sibling candidates (live:ENT-1).** Before probing, `detect_capabilities` runs `augment_candidates_from_device(hass, vacuum_entity_id, entity_candidates)` (`capabilities.py::augment_candidates_from_device`): for each role, siblings whose domain matches and whose object_id ends with the same suffix are appended **behind** the derived candidates.

> ⚠ The name says `_from_device` and it is no longer only the device. `_sweep_siblings` (`capabilities.py::_sweep_siblings`) sweeps **two** scopes — the vacuum's device-registry device FIRST, then its whole CONFIG ENTRY — and reports which scope each winner came from (`device_sibling` / `config_entry_sibling`). Issue #49 is exactly the install where the device scope finds nothing and the config-entry scope finds everything: 65 companions named for an area, one vacuum named for the model. §5.2 states this correctly; this paragraph described the pre-#49 behaviour. Derived names stay first and `_find` takes the first match, so an install where name-derivation works resolves byte-identically — only a role that would have resolved to **nothing** can now find something (proven on the maintainer's own install, where companions carry an area prefix; GitHub issue #48). Best-effort: an unreadable registry returns the candidates unchanged.

The companion diagnostic is `diagnostics.py`'s `entity_resolution_summary` (`diagnostics.py::_vacuum_diagnostics`): `{declared, unresolved, device_entity_count, likely_naming_mismatch}`. `likely_naming_mismatch` is `True` only when at least one role is unresolved **and** the vacuum's device has ≥1 sibling entity at all — the shape that means "derivation failed but there was something to find," distinguishing a naming-mismatch install from one that simply has no companion entities registered. `unresolved` folds in pattern-resolved roles too (live:ENT-2, e.g. `mapping.live_map_image_entity_pattern`) — roles that aren't declared `entity_candidates` keys, so without this fold-in an install whose only broken role is a pattern one would read as "no mismatch."

The full `detect_capabilities()` return is **larger** than the nine flags the Eufy config copies out: ~20 `supports_*` flags plus `entities` (resolved ids), `maintenance_sources`, `sources`, `robot_position_status`/`_message`, and `model_family` (defaults to `"generic"` for an unknown model). Its signature is keyword-only after `hass` (§5.2 step 4).

> **Note — the flags above are not the whole block.** They are the framework's derived `supports_*` set (per the derivation above — **not** pure entity probes). The same `capabilities` block also carries **adapter-literal behavioral
> flags** that no entity probe can see — they describe firmware behavior and are set
> directly in the adapter config (e.g. the Roborock S6 adapter at
> `adapters/roborock/adapter.py`): `honors_clean_order`, `supports_room_profiles`,
> `position_lock_reliable`, and `rooms_unique_per_job`. **Both** brands declare zone
> caps, with **different units**: Eufy `supports_zone_clean=True`, `zone_max=10`, and
> per-**side** bounds `zone_min_side_m=0.5` / `zone_max_side_m=10.0`; Roborock `zone_max=5`
> with per-**area** bounds `zone_min_area_m2` / `zone_max_area_m2`. See
> [Adapter config reference](22-adapter-config-reference.md)
> §14 for the full set and each flag's default and effect.
>
> Do **not** treat `supports_base_station` and `supports_map_bounds` as
> adapter-literal capability flags — no adapter config sets them. They are computed
> at snapshot time in `core/manager.py::get_dashboard_snapshot`:
> `supports_base_station` (`core/manager.py#CN585YGW`) from `dock_events.enabled` OR the mop-wash /
> mop-dry / empty-dust / station-water caps, and `supports_map_bounds`
> (`core/manager.py#CN5APNA9`) from `mapping.segmenter_engine` being **set at all**
> AND not `"noop_fallback"` — an absent or empty `segmenter_engine` is False too,
> not only the fallback one. The same snapshot also computes `supports_va_render`
> (`core/manager.py::get_dashboard_snapshot`; no anchor is minted at that line) from
> a `map_render` block that is a `dict` — `isinstance(..., dict)`, so a
> present-but-non-dict `map_render` does not count.
>
> ⚠ **Those last two used to be cited as bare line numbers — `` (`:4993`) `` and
> `` (`:5113`) `` against `core/manager.py` — and both were dead.** A bare line
> citation records no sha, so there is no way to say what they once resolved to, and
> `core/manager.py` has moved a long way since they were written; do not try to
> reconstruct it. The anchor and the symbol above are the forms that survive the
> file moving. Note the sentence's other citation, `#CN585YGW`, was already in
> anchor form and stayed correct throughout — that contrast is the whole argument.

> **See also:** [22-adapter-config-reference](22-adapter-config-reference.md) for the complete field-by-field documentation of every block (`entities`, `vocabulary`, `dispatch`, `maintenance_components`, `capabilities`, and all sub-schemas).

---

## 4. Config Loader (`config_loader.py`)

### 4.1 Startup loading

```python
load_stored_adapter_configs(hass, data) -> int
```

Called from `async_setup_entry` **before** code adapter registration. Reads `data["adapters"]` — a dict of `{vacuum_entity_id: config_dict}` stored by the UI wizard — and calls `register_adapter_config()` for each. Returns the count of successfully registered configs.

Code adapters registered afterward **overwrite** stored configs for the same vacuum entity ID. This means code adapters always take precedence.

### 4.2 Save / delete / read

```python
save_adapter_config(data, vacuum_entity_id, config) -> None
```
Writes to `data["adapters"][vacuum_entity_id]`. Caller must call `manager.async_save()` and `register_adapter_config()` separately.

```python
delete_adapter_config(data, vacuum_entity_id) -> bool
```
Removes from `data["adapters"]`. Returns `True` if removed, `False` if not present. Caller handles save.

```python
get_stored_adapter_config(data, vacuum_entity_id) -> dict | None
```
Read-only. Returns stored config or `None`.

---

## 5. Eufy Adapter (`adapters/eufy/adapter.py`)

The Eufy adapter is the **reference implementation** of `ADAPTER_CONFIG_SCHEMA`. Every field maps to a measured or observed value.

### 5.1 Entry point

```python
register_eufy_adapter_for_vacuum(hass, vacuum_entity_id) -> None
```

Called once per managed vacuum at startup from `async_setup_entry`. Idempotent — re-calling overwrites the previous registration.

### 5.2 Assembly steps

1. Resolve the model code — the **device-registry** model is the primary source (`_registry_model_code`, reads `device_entry.model`); the `vacuum.attributes.detected_model` attribute is only the **fallback** when the registry has none. This matters: scalar/Tuya-transport Eufy devices don't set the attribute, so reading *only* the attribute pinned them to `model_family="generic"` — the registry carries the code either way. Then compute `model_family` via `_detect_model_family()`.
2. Build `entity_candidates` dict (two naming-variant candidates per entity where robovac_mqtt uses different suffixes between versions).
3. Build `capability_hints` dict — model-based boolean hints for `detect_capabilities()`.
4. Call `detect_capabilities(hass, *, vacuum_entity_id, detected_model, entity_candidates, model_family, capability_hints, maintenance_components, reserved_suffixes, entity_overrides)` (all args after `hass` are keyword-only) — augments each candidate list with device-registry siblings (live:ENT-1, §3.5), then probes the HA entity registry and state machine; returns capability flags and resolved entity IDs.

   `reserved_suffixes` is the adapter's **full** suffix vocabulary (`ALL_SUFFIXES`, derived from `entities.py`'s own `SUFFIX_*` constants so it cannot drift), and it exists because sibling matching is otherwise unsafe. `endswith` cannot tell that `_cleaning_area` is a substring of `_total_cleaning_area`, so a per-run role can claim the **lifetime counter** and resolve to it depending on entity-registry order — wrong data, not missing data. The colliding halves are declared in *different* places (`entities` vs `entity_candidates`), so neither map can see the conflict alone; passing the whole vocabulary lets the longest declared suffix claim its own sibling exclusively (**live:ENT-4**). Omitting the argument degrades to candidate-vs-candidate exclusivity rather than failing.

   It is passed to **both** resolvers, because the ownership test exists in two copies: `detect_capabilities` forwards it to `augment_candidates_from_device`, and `adapters/entity_resolve.resolve_declared_entities` takes it directly and applies the same longest-suffix `_claimed_by` rule to the declared entity map. **Both brands now pass it in both places** — `adapters/eufy/adapter.py#CN2X0DN6` and `:330`, `adapters/roborock/adapter.py#CNXD5V8Q` and `:255`. Roborock shipped without it and ran the guard UNARMED: replaying `_claimed_by` against that adapter's real map returned `_claimed_by("ivy_total_cleaning_area") == "_cleaning_area"`, the lifetime counter accepted as the per-run sensor, because Roborock binds no lifetime role for the `entities` map to learn the longer suffix from. It is the argument rather than a longer `entities` map for exactly that reason — a brand should not have to BIND a role merely to be protected from it, and Roborock now declares `SUFFIX_TOTAL_CLEANING_AREA` / `SUFFIX_TOTAL_CLEANING_TIME` as constants that reach `ALL_SUFFIXES` without being bound anywhere.

   **Two scopes are searched, device first (live:ENT-5).** Companion lookup used to consult only the vacuum's DEVICE, while `adapters/entity_resolve.resolve_declared_entities` consulted its CONFIG ENTRY. On issue #49 the config-entry search rescued battery and the dock counters on the same install at the same instant that the device search rescued nothing — so config-entry scope is the half with field evidence, and device scope is where the failure lives. Both are now searched, device first because it is the tighter scope and order is priority. A vacuum with **no `device_id` at all** is no longer an instant give-up.

   **A LOCALIZED entity id is rescued by the provider's own word (live:ENT-14).** HA slugs
   an entity id from the **translated** name at creation and then never revisits it
   (`async_get_or_create` looks the entity up by `unique_id` and takes the update path), so
   the id is a fossil of whatever language was active when the entity was first seen.
   Switching HA's language afterwards renames **nothing** — which also means an affected
   user cannot self-heal. On a German install the Roborock map select is
   `select.<obj>_ausgewahlte_karte`, and every derived name and every `endswith` suffix
   test misses it, so `active_map` resolves to nothing and `supports_rooms` /
   `supports_segments` come back False — an install where the integration does essentially
   nothing (GitHub issue #51).

   `rescue_by_translation_key` (`adapters/entity_resolve.py::rescue_by_translation_key`)
   closes it. `translation_key` is the **upstream integration's own untranslated word** for
   the concept: set in code, never localized, and it survives both a rename and a move to
   another device — so one mechanism covers localized ids *and* Roborock's split dock,
   whose consumables live on a second device entirely.

   Ordering is the safety property. It runs only **after** the derived id and the suffix
   match have both failed, so an install where naming already works resolves
   byte-identically and only a role heading for **nothing** can newly bind. It is
   exactly-one-or-nothing for the same reason the contest ladder is: Dreame publishes five
   keys (`wetness_level`, `suction_level`, `cleaning_mode`, `mop_pad_humidity`,
   `cleaning_route`) **eleven times each** — global plus one per room — so a key is not
   unique per entity on every brand, and an ambiguous key must decline rather than pick.

   **The wanted key is the declared suffix, unless the brand says otherwise.** For every
   provider that sets one, the key IS the English slug the declaration was written from, so
   the default needs no brand vocabulary. Where it differs, the adapter declares it:
   `resolve_declared_entities(..., translation_keys={role: key})`. Exactly one role needs
   this today, and it earned the seam — Roborock's `job_active` is declared `_cleaning`,
   deriving `cleaning`, while upstream publishes **`in_cleaning`**. A miss by one word, and
   because that entity is the sole arming signal under
   `completion.require_job_active_clear`, it meant **every run on a localized install was
   reaped as `interrupted` ten minutes after dispatch** — see
   [06 — job lifecycle](06-job-lifecycle.md).

   **The ACT path is a caller, not a copy — `INR2F03P`.** Everything above serves READING.
   Anything we intend to PRESS resolves through
   `entity_resolve.py::resolve_action_entity`, which walks the same ladder and returns
   **resolved / disabled / missing**. It was added because the rescue reached only readers:
   on a localized install every maintenance sensor bound correctly while all four dock
   buttons, all four consumable reset buttons, and the mop-intensity dispatch target were
   dead — silently, because HA logs rather than raises when a service names a missing
   entity. Disabled is reported separately since
   `er.async_entries_for_config_entry` returns disabled entries, and pressing one is a
   no-op.

   ⚠ **THE PREDICATE EXISTS IN THREE PLACES AND TWO IS NOT ENOUGH — `RNF2RCXP`.**
   `resolve_declared_entities` (the declared `entities` map),
   `capabilities._rescue_maintenance_source` (maintenance sources) and
   `capabilities.augment_candidates_from_device` (the roles `detect_capabilities` probes)
   each perform this rescue. The first fix landed in two of them and a full green suite said
   nothing — the third was only caught by renaming a live vacuum's entities to German and
   watching the counts fail to match. Count the copies before believing a fix.

   Blast radius, for anyone weighing whether this is niche: HA localizes entity ids for
   **41** languages (`generated/languages.py` `NATIVE_ENTITY_IDS`); Roborock ships **48**
   translation packs, **32** of them in that set. Non-Latin scripts are unaffected only
   because they are absent from the native set, not by design.

   **Competing candidates are refused, not ranked by luck (live:ENT-6).** When more than one sibling matches a role, appending them all and taking the first that exists makes entity-registry INSERTION ORDER the tiebreaker — which nobody chose, and which can bind a card to the wrong machine when two vacuums share a config entry. The colliding pair is almost always per-run against lifetime — `cleaning_area` against `total_cleaning_area` — and those are not two spellings of one quantity: on live hardware the per-run figure reads 2.9 m² while the lifetime counter reads 11,814.2 m². Binding the wrong one never throws, because a cumulative counter simply looks like a vacuum making no progress, so a ~4000x error goes quietly into the learning store, counter segmentation and battery metrics.

   **The contest ladder decides it, or nobody does (live:ENT-9).** `_narrow_competing` (`capabilities.py::_narrow_competing`) walks four rungs, strongest evidence first, and each rung must be DECISIVE — exactly one survivor — or the next is tried. The rung that decided is recorded under `entity_augmentation.decisions[role]["by"]` (`decided_by` is only the local name inside `_narrow_competing`) and surfaced to the card as `chosen_by`. **`object_id`**: the only competitor whose entity ID still carries the vacuum's own object_id (Eufy's dock entities are named `<area>_<vacuum>_<suffix>`, so they survive it). **`translation_key`**: the only competitor whose registry `translation_key` equals the role name — the upstream integration's own word for the concept, independent of what anyone named the entity. **`state_class`**: drop every competitor declaring a cumulative one. The test EXCLUDES `total` and `total_increasing` rather than REQUIRING `measurement`, because Dreame marks its lifetime sensor `total_increasing` and leaves the per-run one unset, so a rule demanding `measurement` finds zero survivors on the very hardware it was written for. **`magnitude`**: the smallest reading wins, and only when the runner-up is non-zero and at least `_MAGNITUDE_RATIO` (`10.0`) times larger — a brand-new vacuum reads 0 for both, and 0 against 0 is not evidence.

   The first three rungs read the **entity registry** (`_sibling_traits`, `capabilities.py::_sibling_traits`), which persists `translation_key`, `state_class`, `device_class` and the unit and can be read before the upstream integration has produced a single state — so they are safe during setup, where `hass.states` is still empty. Only `magnitude` needs runtime, and it needs a numeric state on *every* competitor.

   **The ladder SHORT-CIRCUITS on the first decisive rung, and no consumer may pretend otherwise.** A role decided at `translation_key` never evaluated `state_class` or `magnitude`: those rungs were NOT EVALUATED and must never be rendered as agreeing. Presenting a rung that never ran as corroboration manufactures confidence, which is the exact failure this surface exists to catch. What the decision does carry is `rejected` — each losing candidate mapped to the trait that ruled it out, e.g. `translation_key=total_cleaning_area` — recorded alongside the winner under `entity_augmentation.decisions`.

   **An undecidable contest leaves the role UNRESOLVED rather than guessing.** No rung deciding returns `None`, which is a real answer and not a failure: the role resolves to nothing and the competitors are recorded under `entity_augmentation.ambiguous`, which the OPTIONS FLOW reads (`config_flow.py#CNAYBZY3`) to decide which pickers to show. The System tab does not read it — `_entity_bindings` builds its rows from `entities` and `entity_resolution_reasons`, so an ambiguous role appears there as unresolved rather than as a listed contest. The user's version of the question — "which of these resets after each clean?" — is answerable, where a heuristic can only pick. This matches the discipline `resolve_declared_entities` already applied.

   **A user override sits ahead of the ladder and outranks it (live:ENT-7).** `entity_overrides` (`{role: entity_id}`, written by the System tab and the options flow) is applied by `augment_candidates_from_device` BEFORE anything can fail — ahead of every early return, because the installs an override rescues are exactly the ones where the registry search dies — and the chosen id goes FIRST in that role's candidate list. `_find` returns the first candidate that has a state, so a resolvable override beats every derived and sibling candidate and no contest below can overturn it; a role carrying an override is also not reported as ambiguous, because the user already decided that one. An override that does NOT resolve — renamed or deleted since — falls through to the normal candidates rather than pinning a dead id, and the role's reason is reported as `override_unresolved` rather than `resolved`, so a user choice that has quietly stopped working stays visible instead of being silently replaced by our guess.

   Three reporting keys come back beside the capability flags — `entity_sources`, `entity_resolution_reasons` and `entity_augmentation`. They were introduced as diagnostics, but they are now LOAD-BEARING: `_resolution_gaps` (`config_flow.py::_resolution_gaps`) computes the options form's field list from `entity_resolution_reasons` + `entity_augmentation.ambiguous`, and `_entity_bindings` derives every System row from them. Changing their shape changes two user-facing surfaces. `entity_resolution_reasons` (per role: `resolved` / `disabled` / `registered_no_state` / `absent` / `override_unresolved` — **live:ENT-2**, because a bare `null` cannot distinguish "no such entity" from "present but switched off", and those need opposite fixes) and `entity_augmentation` (`ran`, `siblings_seen`, `merged`, `reason`, `error` — **live:ENT-3**, because every failure path in the sibling rescue used to return silently, making "it died" and "it found nothing" identical in a dump).
5. Build the full `config` dict from all sub-modules: `entities.py`, `buttons.py`, `vocabulary.py`, `maintenance_components.py`, `upkeep_catalog.py`, `<brand>_upkeep_guides.py`, `water_config.py`, `constants.py`. The config also stores `model_family` + `capability_hints` (`adapters/eufy/adapter.py#CNAFKHEP`, so `refresh_vacuum_capabilities` reproduces the startup `detect_capabilities` inputs) and the full probe dict under `_entity_candidates` (`adapters/eufy/adapter.py#running_long_ratio`, RP-033/VAC-3 — a refresh used to rebuild candidates from the resolved `entities` alone, silently losing every probe-only, multi-candidate key).
6. Strip `None` values from the entities dict (absent entities degrade gracefully per the schema).
7. Call `register_adapter_config(vacuum_entity_id, config)`.

### 5.3 Eufy-specific sub-modules

| Module | Exported symbols |
|---|---|
| `adapters/eufy/const.py` | `ADAPTER_ID`, `STORAGE_KEY` |
| `adapters/eufy/constants.py` | `POST_JOB_AMENDMENT_MIN_WASH_INTERVAL_SECONDS`, `POST_JOB_AMENDMENT_TIMEOUT_SECONDS` |
| `adapters/eufy/entities.py` | `build_entity_id()`, all `SUFFIX_*` and `DOMAIN_*` constants |
| `adapters/eufy/vocabulary.py` | `HARD_SERVICE_STATES`, `DRYING_STATES`, `ACTIVE_RUN_TASK_STATES`, `HA_ACTIVE_VACUUM_STATES`, `DOCK_EVENT_TRIGGERS`, `WATER_LEVEL_ALIASES`, `WASH_FREQUENCY_MODE_ALIASES`, `CLEAN_MODE_ALIASES`, `CLEAN_INTENSITY_ALIASES`, `FAN_SPEED_ALIASES`, `NOT_ERROR_SENTINELS`, `CANCEL_SERVICE_EXCLUSION_STATES` |
| `adapters/eufy/maintenance_components.py` | `MAINTENANCE_COMPONENTS` |
| `adapters/eufy/model_catalog.py` | `detect_model_family()` |
| `adapters/eufy/upkeep_catalog.py` | `UPKEEP_GUIDE_FAMILY_NAMES`, `UPKEEP_MODEL_GUIDE_FAMILIES`, `UPKEEP_MODEL_NAMES` |
| `adapters/eufy/eufy_upkeep_guides.py` | `UPKEEP_GUIDE_LIBRARY` |
| `adapters/eufy/water_config.py` | `WATER_MODEL_CONFIGS` |
| `adapters/eufy/buttons.py` | `DOCK_ACTION_CANDIDATES`, `DOCK_ACTION_TOKENS`, `RESET_CANDIDATES`, `RESET_TOKENS` — dock-action and maintenance-reset button entity-resolution candidates / token-sets |
| `adapters/eufy/lifecycle.py` | `_get_lifecycle_watch_entities()`, `_completed_finalize_signals()`, `_active_cleaning_target_cleared()` — translate Eufy entity naming + state vocabulary into the framework lifecycle listener's signals |
| `adapters/eufy/segmentor.py` | `detect_room_segments()` — Eufy CV map-segmentation pipeline (the brand's *map* segmenter, `eufy_cv_v1`; distinct from the counter/run segmenter `eufy_counter_v1` in `learning/job_segmenter_engines.py` — see §2.4) |

### 5.4 Entity ID construction

`build_entity_id(vacuum_entity_id, suffix, domain="sensor", *, strategy=STRATEGY_OBJECT_ID_SUFFIX)` derives an entity ID. The default (and only shipping) strategy `object_id_suffix`:

```
object_id = vacuum_entity_id.split(".", 1)[1]   # e.g. "alfred"
entity_id = f"{domain}.{object_id}_{suffix}"    # e.g. "sensor.alfred_task_status"
```

---

## 6. Startup Registration Order

The two-phase registration order at `async_setup_entry` time:

```
1. load_stored_adapter_configs(hass, data)
   → registers any UI-wizard-built configs first

2. register_brand_adapter(hass, vacuum_entity_id, data=data)  [for each managed vacuum]
   → resolves the brand, runs that brand's registrar
   → overwrites stored configs; code adapters always win
```

This order means: if a user built a custom adapter config via the UI wizard and then the
code adapter is also registered, the code adapter takes precedence. The stored config is
not deleted — it persists for reference and is used if the code adapter is removed.

### 6.1 Brand selection (`adapters/brands.py`)

Which registrar runs is decided by an ordered table, **not** by a branch in
`__init__.py`. `BRAND_REGISTRARS` holds one `BrandRegistrar` per brand
(`brand_id`, `register`, `platforms`, `is_default`), and `resolve_brand` returns both the
registrar and **how** it was chosen:

| `source` | Meaning |
|---|---|
| `"platform"` | The vacuum's **entity-registry `platform`** appears in a registrar's declared `platforms`, first match in table order. |
| `"default"` | No override and no platform match — the terminal `is_default` arm. Exactly one entry declares it. |

**Identity is DATA, declared by the adapter about itself.** Each brand package names the
HA integration domain(s) that provide its vacuum entity in its own `const.py`
(`UPSTREAM_PLATFORMS`), and core does nothing but compare strings — see
`adapters/roborock/const.py::UPSTREAM_PLATFORMS`.

There is deliberately **no `detect` callable and no `is_X_brand` function**. An earlier
version had one per brand and core called each in turn; that is `if brand:` wearing a
function pointer, and putting brand knowledge back inside core's control flow is the
arrangement this whole seam exists to remove. A brand cannot express "probably me",
because core no longer asks.

The platform is also strictly better evidence than what it replaced. The previous
detector read `manufacturer` and a model prefix — vendor-controlled free text that is
routinely blank on real installs, which is why Eufy never had a detector at all.
`platform` is set by HA from the providing integration's domain and is never blank, so
Eufy is now positively identified (`robovac_mqtt`) rather than assumed.

**There is no default arm and no per-user brand override.** An unmatched vacuum is
UNSUPPORTED: it stays managed, gets no adapter config (which every consumer of
`get_adapter_config` already tolerates), and a warning names the providing integration.

What is supported is a **tested upstream integration**, not a brand in the abstract —
"Vacuum Agent supports `robovac_mqtt`" is the precise claim. So a rename is **ours to
follow** and ships as a one-line data change, and an unsupported system wants an
**adapter**, not a switch pointing an existing brand's vocabulary at hardware it was
never written for.

> ⚠ This guard activates over existing installs and the only recovery is a release from
> us. The refusal is therefore written as a **diagnosis**: it carries the providing
> integration's name, which is exactly what an issue needs. Before this, a Dreame
> (`vacuum.robin`) was silently registered as a Eufy and bound 2 of ~10 roles by
> coincidence of naming — configured-looking, and wrong.

What changed is that reaching it is no longer silent: `register_brand_adapter` logs at INFO
when the default was reached by *no-match* rather than by detection. "This is a Eufy" and
"we could not tell, so we assumed Eufy" are different facts and now read differently in the
log.

Eufy declares no `detect` at all, deliberately — the Eufy adapter never reads the device
registry for manufacturer or model, so there is no positive test to write, and inventing
one would dress an assumption up as an identification.

Every failure mode degrades rather than raising, because this runs for every managed vacuum
during setup: an unknown override id falls through to detection (with a warning), a
malformed stored value is ignored, and a `detect` that throws is skipped so later brands
still get their turn.

---

## 7. Porting to a New Brand

> **Read ROBOROCK as the template, not Eufy.** Eufy was the first brand, so parts
> of the system were built around it before "core" and "brand" were distinct
> ideas. Measured by import graph, an adapter package reaches outside itself in
> exactly three ways, and they are not the same kind of thing:
>
> | reach | status |
> |---|---|
> | `core.capabilities.detect_capabilities` | **Allowed.** Both brands use it. It is adapter-facing API that happens to live in `core/` — entity-presence detection you are expected to call, not a private core internal. |
> | `mapping.segment_primitives` | **Allowed for CV brands.** Brand-neutral geometry (`rdp`, `polygon_area`, `mask_to_polygon`, `mask_iou`…) with no Eufy semantics. Eufy needs it because Eufy ships a map IMAGE; Roborock supplies segments directly and needs none of it. |
> | `profiles.room_profiles` | **Nothing to import.** This was the one real weld: the framework's in-code catalog *was* Eufy's, and the Eufy adapter imported it to declare its own vocabulary. Cut on 2026-08-07 — those values now live in `adapters/eufy/room_profiles.py`, alongside Roborock's in its own package, and core holds only the four profile KEYS. The `KNOWN_LEAKS` ledger in `tests/adapters/test_adapter_isolation.py` is empty as a result. Declare your own values; the `ProfileRecord` shape is published in [22 §13d](22-adapter-config-reference.md). |
>
> Both brands now show the correct shape: each declares `FLOOR_TYPE_WATER_DEFAULTS`
> and its profile vocabulary in its OWN package and imports nothing from `profiles/`.
> The trap that made this necessary is gone with it — a brand that omits the block no
> longer inherits Eufy's `"Max"`/`"Off"`/`"Quick"`, it fails registration.
>
> The check when porting: if your adapter imports from `profiles/`, `queue/`,
> `jobs/` or `learning/`, you are reaching for something that should be yours or
> should be passed to you. Compare against Roborock before concluding you need it.
> The only legitimate edit outside your brand package is the `BRAND_REGISTRARS`
> row in step 1b.

To add a new brand adapter:

1. Create `adapters/{brand}/adapter.py` with a `register_{brand}_adapter_for_vacuum(hass, vacuum_entity_id)` function, plus an `is_{brand}_vacuum(hass, vacuum_entity_id)` predicate for positive identification.
1b. **Add one row to `BRAND_REGISTRARS` in `adapters/brands.py`** pairing the two (see §6.1). Place it before the default arm; detection runs in table order. This is a REGISTRATION at a declared extension point, not a core edit — and so are the three engine registries below (`queue/dispatch_engines.py` §3, `mapping/segmenter_engines.py` and `learning/job_segmenter_engines.py` §4) if your brand needs its own engine rather than a built-in. What "core is not touched" means precisely: **no existing behaviour changes when your brand arrives.** Nothing above the adapter learns your brand's name, vocabulary or limits. Adding a registry entry does not violate that; changing a shared default so your brand fits does.
2. Build the config dict using `ADAPTER_CONFIG_SCHEMA` as the reference. Every framework-read field must be present; card-only fields (`vocabulary.clean_mode_options`, etc.) are optional.
3. Set `dispatch.template` to one of the four built-in templates, or add a new template to the dispatch engine.
4. Pick the two segmenter engines (see §2.4). Declare `mapping.segmenter_engine` (or `noop_fallback` if the brand yields no map image) and `job_segmenter.engine` (or `noop_job_fallback` if the brand emits no per-room run signal). For Eufy these are `eufy_cv_v1` and `eufy_counter_v1`; a brand whose boundary detection differs registers its own engine in the relevant registry and names it here. **Declare `room_profiles`. It is required, and registration fails without it.** That is
a deliberate change from "optional": core carries no catalog, so an adapter declaring none
cannot resolve a room at all. Before the rule existed, an absent block silently gave your
rooms Eufy display vocabulary — `"Max"`, `"Off"`, `"Quick"`. Roborock shipped without it
and every Roborock room was created with settings the brand does not recognise: the card's
chip rows compare option values strictly so nothing rendered as selected, and
`per_room_live_settings` filters on `fan_speed_options`, so `jobs/active_job.py` skipped
the `set_fan_speed` call entirely and the room ran on whatever fan was last set.

Declare `builtins` + `default_profile` in your own vocabulary, using the same four profile
KEYS every brand declares so stored rooms and the card's profile picker survive a brand
switch, and declare `floor_type_water_defaults` / `floor_type_fan_defaults` too — those are
applied to *every* room, not just new ones, and the resolver reads the carpet entry of the
water map as your brand's no-water value. Omit an axis your brand does not have (Roborock
omits `clean_intensity` from every profile) so nothing inert is written onto rooms.

`tests/adapters/test_adapter_contract.py` asserts all of this for every brand in
`ADAPTER_BUILDERS`, so a missing or mis-cased declaration is a red test rather than a
silent wrong default.
5. Register via `register_adapter_config(vacuum_entity_id, config)` at startup.
6. The adapter's `setup.steps` declaration controls which setup-wizard screens the user sees (see `setup/drift.py`).

### 7.1 What the framework checks, and what it will not tell you

Four layers, deliberately different in strictness (see §2.2 for the full source-based breakdown):

| Layer | When | On failure |
|---|---|---|
| `registry._validate_adapter` | Every registration | A stored (`source == "config"`) config **hard-raises** `ServiceValidationError`; a code (`source == "code"`) config just logs a warning; a non-dict config always raises `TypeError`. Gates the four engine blocks (`mapping`, `job_segmenter`, `room_attribution`, `room_profiles`), `dispatch.template`, `capability_hints` key names, `dispatch.phase_timing` positivity, and `setup.steps` ids. |
| `registry._warn_eufy_fallbacks` + `registry._warn_completion_gate_orphan` | Every registration **except** a hard-raised stored config | Advisory warning only, both source types. `_warn_eufy_fallbacks` names each engine block you did **not** declare, the Eufy default that takes over, and how to opt out. `_warn_completion_gate_orphan` fires when `completion.require_job_active_clear` is set without `entities.job_active` declared. |
| `config_schema.validate_adapter_config` (via `services/adapter_config.py::_handle_save_adapter_config`) | Every UI/service **save** of a stored config | Raises `ServiceValidationError` before the config is persisted or registered — required keys, types, enum membership, and any key the schema does not declare, at every level the schema enumerates a shape (§3). |
| `tests/adapters/test_adapter_contract.py` | CI | Red. Calls the **same** `validate_adapter_config` against every code adapter in `ADAPTER_BUILDERS`, plus `test_no_undeclared_top_level_keys` asserting no adapter ships a block the schema doesn't know. |

**Every permissive default in this framework resolves to a concrete *Eufy* answer, not to
a refusal.** An absent `job_segmenter` runs Eufy's counter-plateau segmenter; an absent
`room_attribution` runs Eufy's anchor-winding attributor. Against a brand that emits
neither signal that is not a crash — it is wrong learned boundaries, quietly. That is why
the advisory exists, and why the opt-out engines (`noop_job_fallback`,
`noop_room_attribution`, `noop_fallback`) are worth declaring explicitly even when you
mean "this brand has nothing here".

**`capability_hints` keys are checked against `KNOWN_CAPABILITY_HINTS`.** A hint the
reader does not know is a silent no-op — `_hints.get(name)` misses and the default stands
— so a typo is indistinguishable from declaring nothing, and a brand saying "I
categorically cannot do this" gets ignored as thoroughly as one saying nothing.

See the [porting guide](../contributing/porting-guide.md) for the complete porting walkthrough.
