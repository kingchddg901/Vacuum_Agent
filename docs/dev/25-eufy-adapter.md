# The Eufy Adapter — Worked Example & Pattern Guide

> **Scope:** A field-by-field walkthrough of the one shipping concrete adapter,
> `adapters/eufy/` (everything except the CV segmentor, which has its own doc).
> This doc is **dual-purpose**: it documents what the Eufy adapter actually
> declares and why, and it doubles as the **pattern guide** for what a complete,
> full-feature adapter looks like — the thing a new brand copies from.
>
> Read [21-adapter-system](21-adapter-system.md) first for the registry/loader
> mechanics and [22-adapter-config-reference](22-adapter-config-reference.md) for
> the authoritative per-field schema. This doc is the *example*, those are the
> *contract*. The CV segmentor is [26-eufy-segmentor](26-eufy-segmentor.md). The
> step-by-step porting workflow is the [porting guide](../contributing/porting-guide.md).

---

## 1. What "full-feature" means

Eufy (the X10 Pro Omni) is the reference adapter because it exercises **every**
schema block the framework can read: mop/water control, dock wash/dry/empty
events, post-job water amendment, per-model maintenance + upkeep guides, room
discovery, a rich dispatch payload, a CV map segmenter, a counter-based job
segmenter, the room-profile vocabulary, and live current-room transition +
anomaly tuning. A minimal adapter
can omit most of these (absent blocks degrade gracefully — see the
"if absent" column in [22 §consumers](22-adapter-config-reference.md)). Eufy is
the upper bound, so it's the best thing to read when you want to see how a block
is *meant* to be filled.

One principle runs through the whole adapter and is worth internalizing before
the rest of this doc:

> **The framework hard-codes no brand knowledge.** Entity names, state strings,
> completion signals, dispatch shape, discovery source — all of it lives in the
> config dict. If you find yourself wanting to special-case a brand in core,
> the value belongs in the adapter instead.

---

## 2. File layout

The adapter is split so that **data lives in small focused modules** and
`adapter.py` is pure assembly — it imports the data and arranges it into the
schema. This is the pattern to copy: don't write one 1500-line adapter module;
factor the brand facts into named files.

| Module | Role |
|---|---|
| `adapter.py` | Assembly + registration. `register_eufy_adapter_for_vacuum()`. No brand *data* of its own beyond literals that only make sense here (card option lists, completion sentinels). |
| `const.py` | `ADAPTER_ID`, `STORAGE_KEY`. |
| `constants.py` | Tuning scalars: debounce/timeout seconds, low-battery threshold, water flow rates (`WATER_RATE_*_ML_PER_MIN`), and wash-interval bounds (`WASH_INTERVAL_{MIN,MAX,DEFAULT}_MINUTES`). |
| `entities.py` | `build_entity_id()` + every `SUFFIX_*` / `DOMAIN_*` constant — the entity-naming convention. |
| `vocabulary.py` | State-string sets and alias maps (hard-service, drying, active-run, not-error, cancel-exclusion, water-level/wash-frequency aliases, dock-event triggers). |
| `discovery.py` | Brand room discovery: `discover_rooms_for_vacuum()` reads the vacuum's `segments` attribute and normalizes it into the framework room shape; `get_active_map_id()` reads the active-map sensor. |
| `lifecycle.py` | Lifecycle-signal helpers: `_get_lifecycle_watch_entities()`, `_completed_finalize_signals()`, `_active_cleaning_target_cleared()` — translate Eufy entity naming + state vocab into the signals the framework lifecycle listener consumes. |
| `buttons.py` | The single source for button discovery: `*_CANDIDATES` (entity suffixes) and `*_TOKENS` (token-set fallbacks) for dock actions and maintenance resets. |
| `model_catalog.py` | `detect_model_family()` — maps a `detected_model` string to a family key (`x10`/`x8`/`l60`/`l50`/…). |
| `maintenance_components.py` | `MAINTENANCE_COMPONENTS` — the consumable catalog (sensor suffix, intervals, label, icon, proxy links). |
| `upkeep_catalog.py` + `upkeep_guides.py` | Per-model upkeep guide library and the model→family mapping. |
| `water_config.py` | `WATER_MODEL_CONFIGS` — tank capacity + flow-rate constants per model. |
| `segmentor.py` | The CV room segmenter — see [26](26-eufy-segmentor.md). |

---

## 3. The assembly flow

`register_eufy_adapter_for_vacuum(hass, vacuum_entity_id)` runs once per managed
vacuum at startup (after stored configs load, so code wins — see
[21 §6](21-adapter-system.md)). It is idempotent. The shape of this function is
the porting template:

1. **Detect the model.** Read `vacuum.attributes["detected_model"]`, resolve a
   `model_family` via `detect_model_family()`. Everything model-specific keys off
   the family, not the raw string.
2. **Build `entity_candidates`.** A dict of `{entity_key: [candidate_id, …]}`.
   This is where the **two-naming-variant trick** lives: robovac_mqtt exposes
   different suffixes across firmware/integration versions, so each list holds
   the known variants and the prober picks whichever is actually present:
   ```python
   "wash_mop_button":   [f"button.{object_id}_wash_mop",   f"button.{object_id}_mop_wash"],
   "empty_dust_button": [f"button.{object_id}_empty_dust", f"button.{object_id}_empty_dust_bin"],
   ```
3. **Build `capability_hints`.** Model-family booleans for hardware you *know*
   exists even if the entity isn't live right now (e.g. `supports_mop_wash =
   model_family in {"x10","x8"}`). Hints are the confident path; entity-presence
   detection is the fallback for unrecognized models.
4. **Call `detect_capabilities(...)`** (`core/capabilities.py`) — probes the HA
   entity registry + state machine against the candidates and hints, returning
   resolved entity IDs and capability flags. **Capabilities reflect the actual
   install, not the spec sheet.**
5. **Assemble the `config` dict** from the sub-modules (§4).
6. **Strip `None` entities** — absent entities degrade gracefully, so they're
   removed rather than stored as `None`.
7. **`register_adapter_config(vacuum_entity_id, config)`.**

---

## 4. Block by block

Each block below shows what Eufy declares and a **Pattern** line — the
transferable takeaway for your own adapter.

### `entities`
Built with `build_entity_id(vacuum_entity_id, suffix, domain)`, which applies the
`object_id_suffix` strategy (`sensor.{object_id}_{suffix}`). Position / work-mode
/ cleaning-intensity IDs come from `detect_capabilities()` (resolved candidates),
not constructed directly, because their suffixes vary by version.
**Pattern:** derive IDs from one naming helper; source version-variant entities
from the capability prober so the config records what was actually found.

### `vocabulary`
State sets (`hard_service_states`, `drying_states`, `active_run_task_states`,
`not_error_sentinels`, `cancel_service_exclusion_states`) come from
`vocabulary.py` and are stored **normalized (lowercase)**. The `blocked_*` sets
are stored **raw** (title-cased firmware strings) because the queue engine
matches them verbatim. Alias maps (`water_level_aliases`,
`wash_frequency_mode_aliases`) normalize brand display strings to canonical keys.
`cancel_detection_states` maps the HA-standard activity terms.
The four `*_options` lists (`clean_mode`/`fan_speed`/`water_level`/
`clean_intensity`) are **card-only** — the framework never reads them.
**Pattern:** keep framework-matched vocab normalized; only the queue-engine
`blocked_*` sets and the card `*_options` are exceptions, and the doc says so.

### `completion`
`task_status_value: "completed"` is the primary signal; the secondary check
requires `active_cleaning_target` to land in a sentinel set
(`"", unknown, unavailable, none, null`) simultaneously.
**Pattern:** a single authoritative completion string plus an optional
"target cleared" co-signal is the robust shape.

### `charging`
This block does **not** turn charging detection on — `core/charging.py` reads the
dedicated `entities.charging` binary sensor with **no substring fallback**. The
block only configures the *low-battery mid-job return* classifier:
`low_battery_return_task_status` + `low_battery_threshold_percent`.
**Pattern:** prefer a dedicated upstream signal (a binary_sensor) over string
sniffing; only the genuinely brand-specific scalars live in config.

### `error_tracking`
Secondary error channel (`task_status_error_value: "error"`), a
`grace_window_seconds` (firmware emits the state DP before the message DP), and
an ordered `error_code_attribute_names` list (first non-zero int wins).
**Pattern:** model the firmware's *timing* (grace window) and *attribute
variance* (name list) in config, not in core.

### `dock_events`
`enabled: True`, a `triggers` map (event-type → normalized dock_status strings,
from `vocabulary.DOCK_EVENT_TRIGGERS`), a `debounce_seconds` map (noisy states
flip 1–2× per real cycle), and `action_buttons` — built from `buttons.py` via the
button-block helper (§5).

### `post_job_wash_amendment`
The dock washes the mop ~2 s after docking; the amendment watcher
(`core/water_amendment.py`) patches water actuals after finalization.
`trigger_states` / `commit_state` / `debounce_seconds` / `timeout_seconds` model
that cycle. **Pattern:** post-job corrections that depend on dock behavior are
configured, with a timeout safety valve.

### `discovery`
Eufy exposes rooms as the `segments` attribute on the vacuum entity, so
`room_list_entity: "vacuum_entity"`, `room_list_attribute: "segments"`, with
`id`/`name` keys. `auto_refresh_on` events + a 6 h interval safety net, plus
drift confirmation windows (`removal_confirmation_passes: 3`,
`new_room_confirmation_passes: 1`). **Pattern:** declare the discovery *source*
and the drift hysteresis; the framework owns the cadence loop.

### `setup`
`steps: [add_vacuum, import_active_map, save_rooms]`. The `import_active_map` step
exists because robovac_mqtt surfaces one map at a time and needs a fetch.
**Pattern:** brands with always-on map exposure drop that step; the list drives
which wizard screens appear (see `setup/drift.py`).

### `dispatch`
`template: "eufy_room_clean"`, `vacuum.send_command` with `command=room_clean`,
payload `{map_id:int, rooms:[{id, clean_times, …}]}`. Eufy uses the canonical
framework field names and values verbatim, so every `room_fields` entry is an
**identity rename with `value_map: None`**. This block is technically optional
for Eufy (defaults match) but is kept as the **copy template** a port edits.
**Pattern:** the dispatch block is where brand payload shape is expressed; pick a
built-in template or add one to the dispatch engine.

### `mapping`
`segmenter_engine: "eufy_cv_v1"` + `segmenter_tuning`. See
[26-eufy-segmentor](26-eufy-segmentor.md). Adapters with no usable map image
declare `"noop_fallback"` so the card stops drawing polygon overlays while trace
tracking keeps working off coordinates. **This is the *map* segmenter** (room
polygons from the map image) — not to be confused with `job_segmenter` below,
which is a separate subsystem.

The block also declares a best-effort live-map pattern,
`"live_map_image_entity_pattern": "camera.{object_id}_map"`, targeting the
community eufy-clean fork's `camera.<device>_map` live-map entity. Core fills
`{object_id}` from the vacuum entity's object_id and **existence-checks** the
result, so a default-named fork install auto-resolves without picking, while
plain (non-fork) Eufy installs resolve to `None` and are unaffected. When the
vacuum entity was renamed and the guess misses, the per-vacuum override (Setup
tab "Live map camera", set via `setup_set_map_camera`) wins.
**Pattern:** the live-map pattern is a brand-default guess, existence-gated, with
the per-vacuum override as the escape hatch — never hard-code a camera name in
core.

### `job_segmenter`
`engine: "eufy_counter_v1"` + `tuning`. This is the **run/counter** segmenter — a
*different* subsystem from the `mapping` map segmenter above. It detects per-room
boundaries from a run's progress signal; for Eufy that's the `cleaning_time` /
`cleaning_area` counters (no geometry — coordinates drift, so the counters are the
reliable transition signal). The engine seam mirrors `mapping` and `dispatch`: the
framework looks the name up in
`learning/job_segmenter_engines.py::_JOB_SEGMENTER_ENGINES` and `eufy_counter_v1`
(`EufyCounterSegmenter`) delegates verbatim to the `counter_segmentation`
primitives, so the Eufy path is byte-identical. One deliberate non-mirror of the
map seam: an **absent or unknown** engine name falls back to `eufy_counter_v1`
(*not* `noop`), like `dispatch_engines` — because the historical no-adapter default
is Eufy counter segmentation, and live rollover + external ingest + learned history
must keep working. `noop_job_fallback` stays registered for a future brand that
emits no segmentable signal, but it is **not** the fallback.

`tuning` is the **single in-code source** of the gap/area/cadence thresholds —
`gap_delayed_s: 35.0` / `gap_transit_s: 60.0` / `gap_plateau_s: 90.0` /
`area_jump_m2: 2.0` / `cadence_s: 30.0`. All three consumers read it: live rollover
(`jobs/active_job.py::_live_boundary_count`), external-run ingest
([28](28-external-run-ingestion.md)), and learned history
(`learning/history_store.py`). The engine's `DEFAULT_TUNING` is defined *by
reference* to the `counter_segmentation` module constants, so it can't drift; the
declared Eufy values equal those defaults, so declaring the block changes nothing.
**Pattern:** the segmenter the framework uses to split a run into rooms is a
pluggable engine; the inference thresholds are config (one source), so a port
re-tunes them without touching `learning/` or `jobs/`. A brand with native
per-room telemetry registers its own engine here that emits the same
`JobBoundaryCandidate` / `JobSegment` shape. See
[22 §job_segmenter](22-adapter-config-reference.md).

### `live_transition`
The **orchestration** half of live current-room rollover (the detection thresholds
live in `job_segmenter.tuning`, above — this block was trimmed to the knobs that
are live-specific). Eufy's rollover runs off the counter signal because it reports
no "current room" and its coordinates drift. The block carries exactly three keys:
`enabled: True` (a kill-switch — `False` routes back to the legacy `segment_legacy`
wrapper); `rollover_kinds: ["wash_plateau", "transit", "area_jump"]` (which
candidate kinds advance the live queue); and `native_transition_source: False`
(reserved for a brand with native per-room telemetry — parsed but no reader yet).
Every value equals the `_LIVE_TRANSITION_DEFAULTS` module fallback in
`jobs/active_job.py`, so declaring the block changes nothing for Eufy — it's the
**documented, adapter-tunable copy** of those defaults. The one behavioural change
vs the legacy live path is the `"transit"` band — a 60-90 s flat-area inter-room
hop the old live filter discarded — so the job now advances on a real transit, not
only on wash/area_jump. The finalize/history segmentation path is untouched.
Consumed by `ActiveJobTracker._live_transition_config()` (orchestration) /
`_live_boundary_count()` (which reads the thresholds from the resolved
`job_segmenter` engine, not from here).
**Pattern:** keep the inference's *thresholds* in one place
(`job_segmenter.tuning`) and the *live orchestration* (kill-switch, which kinds
roll the queue) here, so a port re-tunes either without touching `jobs/`. See
[22 §live_transition](22-adapter-config-reference.md).

### `anomaly`
Live anomaly-tuning ratios for the job-progress snapshot
(`core/manager.py::get_job_progress_snapshot`). `running_long_ratio: 1.5`
(the **soft** tier — current room over 1.5× its estimate with no pending
transition) and `stall_ratio: 2.0` (the existing hard stall). Both equal the
manager fallbacks, so Eufy is unchanged; both are adapter-tunable.
**Pattern:** thresholds for "this is taking too long" are firmware/brand-paced,
so they're config scalars, not core constants. See
[22 §anomaly](22-adapter-config-reference.md).

### `room_profiles`
The room-profile vocabulary — the built-in profiles, the custom-profile template,
legacy aliases, the default profile name, and the floor-type fan/water default
maps. Eufy declares the whole block **by reference** to the in-code constants in
`profiles/room_profiles.py` (`BUILT_IN_ROOM_PROFILES`, `DEFAULT_CUSTOM_ROOM_PROFILE`,
`LEGACY_PROFILE_ALIASES`, `DEFAULT_ROOM_PROFILE_NAME`, `FLOOR_TYPE_*_DEFAULTS`) — no
duplication, byte-identical. Those in-code constants stay the framework **default**
catalog *and* the source of `_PROTECTED_ROOM_PROFILE_NAMES` (bound at module load in
`profiles/manager.py`); this block is **resolution-only**.
`resolve_profile_catalog()` merges the block over the constants **per key**, so a
port can override any subset (just its `builtins`, say) and inherit the rest; a
None/empty block returns the in-code defaults verbatim. The catalog is threaded
through the per-room resolvers (`resolve_room_profile_for_room`,
`apply_capability_gate`, …) on the **dispatch** path
(`queue/queue_engine.py::build_room_clean_payload`), so per-room dispatch settings
are adapter-catalog-sourced.
> **Honest boundary.** The *global* profile-editor (`profiles/manager.py`) and the
> pure room-builder defaults (`rooms/room_manager.py`) have no per-vacuum context,
> so they resolve against the framework **default** catalog (`catalog=None`).
> Byte-identical for Eufy; a second brand's editor UI would show framework defaults
> until those call sites are threaded — a documented follow-up.

**Pattern:** ship the room vocabulary as adapter config (by reference to the
framework defaults, so there's nothing to maintain twice); a future brand inlines
its own profiles/aliases without forking the resolver. See
[22 §room_profiles](22-adapter-config-reference.md).

### `capabilities`
Hardware/entity-surface flags are sourced from `detect_capabilities()`
(`caps.get(...)`) so the registered config matches the install's real entities.
Two **behavioural** flags are hardcoded literals instead, because they describe
firmware behaviour an entity probe can't see: `position_lock_reliable = False`
(Eufy re-bases the raw coordinate frame each session) and
`rooms_unique_per_job = True` (no vacuum-then-mop whole-home mode, so a room is
cleaned at most once per job). See [22-adapter-config-reference](22-adapter-config-reference.md).

### `settings_selects`
The global select entities (`cleaning_mode` / `suction_level` / `water_level` /
`cleaning_intensity` / `mop_intensity`) that mirror the current room's settings
while a job runs — the only window into an **app-started** run's per-room settings.
Consumed by external-run ingestion ([28](28-external-run-ingestion.md)); the
`clean_mode` entry carries a `value_map` to canonicalise the raw firmware strings.

### `maintenance_components`
Projected from `MAINTENANCE_COMPONENTS`: `sensor_suffix` (full suffix → counter
sensor), `proxy_for`, intervals, `label`, `icon`, and a `reset_button` block
built from `buttons.py` (§5). See [13-maintenance-manager](13-maintenance-manager.md).

### `upkeep_catalog` / `water_model_configs`
Per-model guide library + model→family maps, and tank/flow constants per model.
`water_model_configs` is projected verbatim from
`water_config.py::WATER_MODEL_CONFIGS` — today that's the physical tank trio only
(`robot_internal_tank_ml` / `dock_clean_tank_capacity_ml` /
`dock_wash_overhead_ml_per_cycle`).
**Pattern:** model-keyed reference data is plain dict literals in their own
modules, projected verbatim into the config.

> **Water-rate / wash-interval seam (read by the framework, not yet declared by
> Eufy).** `planning/run_plan.py` now reads three optional override hooks and
> falls back to the measured Eufy values when they're absent — which is exactly
> what Eufy does, so Eufy is byte-identical:
> - `water_model_configs[<model>]["water_rates"]` — per-canonical-level ml/min,
>   passed as `rate_override` to `_water_rate_ml_per_minute()`. Eufy rides the
>   built-in table (`off/low/medium/high = 0/3.2/4.0/5.3`, the
>   `WATER_RATE_*_ML_PER_MIN` constants).
> - `water_model_configs[<model>]["low_clean_water_margin_ml"]` — low-water
>   margin (default `300.0`).
> - **top-level** `wash_frequency_bounds` `{min, max, default}` — wash-cadence
>   interval clamp, read in `_derive_wash_frequency_config()` (default
>   `15/25/20`, the `WASH_INTERVAL_*_MINUTES` constants). Note this is a
>   *top-level* adapter key, **not** nested under `water_model_configs`.
>
> The constants back these defaults in `constants.py` but are **not** wired into
> the Eufy config dict — a second brand with a different dock declares them to
> override. See [22-adapter-config-reference](22-adapter-config-reference.md).

---

## 5. Button resolution pattern

Buttons (dock actions, maintenance resets) are the one place a brand can't rely
on a clean suffix, so the resolver takes **two ordered strategies**, both sourced
from `buttons.py` (the single source of truth):

```python
{
  "entity_suffixes": ["wash_mop", "mop_wash"],   # tried first: button.{object_id}_{suffix}
  "token_sets":      [["wash", "mop"]],           # fallback: all-tokens-must-match registry scan
}
```

`_build_button_block()` assembles one such block (returning `None` when a key has
no button), and `_build_button_blocks()` builds the full action map.
`_strip_button_suffix()` reconciles `buttons.py`'s leading-underscore convention
(`"_wash_mop"`) with the resolver's `button.{object_id}_` convention.
**Pattern:** named suffixes first, all-tokens-must-match registry fallback second;
keep both lists in one module so resets and dock actions can't drift apart.

---

## 6. Capability detection vs hints

`detect_capabilities()` reconciles two inputs: **hints** (model-family booleans
you're confident about) and **entity presence** (what's actually registered).
Hints win for known models; presence is the safety net for unrecognized model
codes that still expose the entities. The result is authoritative for the rest of
the config (`capabilities` block + resolved position/work-mode entity IDs).

---

## 7. Building your own full-feature adapter

Use Eufy as the template and the [porting guide](../contributing/porting-guide.md)
as the procedure. The short version:

1. Make `adapters/{brand}/` with the same data/assembly split (§2). Put brand
   facts in small modules; keep `{brand}/adapter.py` as pure assembly.
2. Write `register_{brand}_adapter_for_vacuum()` following the 7-step flow (§3).
3. Fill each schema block ([22](22-adapter-config-reference.md)) with real,
   provenance-noted values — copy Eufy's block, change the facts. Mandatory:
   `entities`, `completion`, `dispatch`. Card-only / optional blocks degrade if
   omitted.
4. Pick a `dispatch.template` (or add one to `queue/dispatch_engines.py`).
5. Declare a `mapping.segmenter_engine` — `"noop_fallback"` if you have no CV
   pipeline, or implement one ([26](26-eufy-segmentor.md)).
6. Set `setup.steps` to the screens your brand needs.
7. Register at startup; verify with the adapter validator (`_validate_adapter`).

The litmus test: if any brand fact ended up in `core/`, `jobs/`, `dock/`,
`battery/`, or `onboarding/`, it's in the wrong place — it belongs in your
adapter config.
