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
discovery, a rich dispatch payload (room clean + ad-hoc zone clean), a CV map
segmenter, the device-map state source + VA-owned map render, a counter-based job
segmenter, a room-attribution engine, the room-profile vocabulary, and live
current-room transition + anomaly tuning. A minimal adapter
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

The block also declares `zone_command: "zone_clean"` — the ad-hoc free-form
zone-clean verb (draw a box on the live map, clean it) via the same
`vacuum.send_command` service with a bare `{zones:[[x0,y0,x1,y1],…], clean_times}`
payload, supported by the smcneece eufy-clean fork. `manager.dispatch_zone_clean`
reads this verb; an **absent** `zone_command` means zone cleaning is unsupported for
the brand (it raises rather than dispatching). It pairs with
`capabilities.supports_zone_clean` below.
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

### `map_state_source`
Where the framework reads the **device's own** map segmentation — normalized into
VA-owned room bboxes + dock/robot anchors — so room regions, current-room, and
mascot anchors are auto-derived (immune to the per-session raw coordinate drift).
Consumed by `mapping/map_source_coordinator.py`. Eufy declares a `storage` backend:
`identifier_domain: "robovac_mqtt"`, a `store_key: "robovac_mqtt.{device_id}"`
(filled from the `(robovac_mqtt, <serial>)` device-registry identifier), and a
`store_version` guarding the fork's stored-wrapper shape (re-point the number if the
fork bumps it). `present_requires_live_map_image: True` gates the whole block on the
`camera.<device>_map` artifact, so plain non-fork installs resolve to "not present"
and the segmentation features hide — same presence-gate idea as the model/CV gates.
Two sub-blocks override the static-storage source with the fork's **fresher
in-memory** state: `live_pose` (the `EufyCleanCoordinator`'s `_robot_pixel` /
`_dock_pixel` / `_robot_trail` for the moving overlays, ~2 s fresh vs the
save-throttled `.storage`) and `memory` (the in-memory `_map_data` MapData, fresher
and loop-safe vs a file read), each listing the attr names to try in order with
absence ⇒ stay on `.storage`. See [map-state-source](map-state-source.md).
**Pattern:** declare *where* the authoritative map state lives (a store key, a
presence gate) and *which* in-memory holders supersede it; core owns the read.

### `map_render`
The VA-owned client-side map render — declares **how** the card sources the raster
to draw its own full-grid backdrop (so overlays align with no fork-camera crop and
the look is themeable). One key, `format: "eufy_room_pixels_v1"`, naming the decode;
the card applies the explicit params `get_map_render_data` returns, so core/card stay
brand-agnostic. The **source pointer** (`store_key` / `identifier_domain` /
`store_version`) is reused from `map_state_source` above — no duplicate schema.
Roborock omits this block (its HA-core image render is already frame-matched);
absence ⇒ the card's "VA-rendered map" backdrop source is hidden for that brand.
**Pattern:** name the decode format and reuse the existing source pointer; absent ⇒
the feature degrades off.

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

### `room_attribution`
A **third** pluggable engine seam, on a different axis from `job_segmenter`: it
recovers **which managed rooms an external (undispatched) run cleaned**, from a
per-tick pose time-series (`current_room` + anchor + `cleaning_area`). Where
`job_segmenter` owns time/area *boundaries*, this owns room *identity*. `engine:
"eufy_anchor_winding_v1"` is looked up in
`learning/room_attribution_engines.py::_ROOM_ATTRIBUTION_ENGINES`; an absent or
unknown name falls back to `eufy_anchor_winding_v1` (not `noop`), mirroring the
job-segmenter default. The engine segments by `current_room`, drops transit by
path-winding, and separates a cleaned room from a parked dock by the swept-area
(`cleaning_area`) delta. `tuning` carries `wind_transit` / `dwell_min_s` /
`swept_area_min_m2` / `interval_s`. This block is **declared-but-dormant** — wired
and validated now, but inert until the run-active pose sampler (W5b) and finalize
wiring (W5c) land. See [eufy-native-transition](eufy-native-transition.md).
**Pattern:** room-identity recovery for external runs is its own pluggable engine,
declared up front so the selection is explicit even while the upstream sampler is
still pending.

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
Live anomaly-tuning ratios for the run-anomaly detector
(`jobs/active_job.py::ActiveJobTracker.detect_run_anomalies`, which the job-progress
snapshot composer `core/manager.py::get_job_progress_snapshot` now just delegates to).
`running_long_ratio: 1.5` (the **soft** tier — current room over 1.5× its estimate
with no pending transition) and `stall_ratio: 2.0` (the existing hard stall). Both
equal the `detect_run_anomalies` fallbacks, so Eufy is unchanged; both are
adapter-tunable.
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
Three flags are hardcoded literals instead, because they can't be settled by a
runtime entity probe: `position_lock_reliable = False` (Eufy re-bases the raw
coordinate frame each session) and `rooms_unique_per_job = True` (no vacuum-then-mop
whole-home mode, so a room is cleaned at most once per job) describe firmware
behaviour an entity probe can't see; `supports_zone_clean = True` is a literal
because no probe distinguishes the smcneece fork (which accepts `zone_clean` — see
`dispatch.zone_command`) from stock eufy-clean. It is gated **downstream** rather
than at the probe: the card only shows the zone-draw control when a live-map image
resolves, and the fork that adds `zone_clean` is the same one exposing
`camera.<device>_map`, so stock (no-live-map) installs never see it. See
[22-adapter-config-reference](22-adapter-config-reference.md).

### `settings_selects`
The global select entities (`cleaning_mode` / `suction_level` / `water_level` /
`cleaning_intensity` / `mop_intensity`) that mirror the current room's settings
while a job runs — the only window into an **app-started** run's per-room settings.
Consumed by external-run ingestion ([28](28-external-run-ingestion.md)); the
`clean_mode` entry carries a `value_map` to canonicalise the raw firmware strings.

### `external_mid_run_statuses`
A list of `task_status` values that mean "docked mid-run, will resume" — mop prewash
(`Returning to Wash` / `Washing Mop`), dust empty (`Returning to Empty` /
`Emptying Dust`), and recharge-resume (`Returning to Charge` / `Charging (Resume)`).
The external-run finalizer **holds the run open** while `task_status` is one of these
instead of closing it at the dock, so a vacuum→mop run stays one multi-segment
record. Source strings are extracted from `robovac_mqtt`'s `_map_task_status`; an
unrecognized value falls back to the time-based grace, so a string drift just loses
the long-wash hold rather than crashing. Consumed by external-run ingestion
([28](28-external-run-ingestion.md)).
**Pattern:** the "stay open across a dock return" vocabulary is brand firmware
strings in config, not a core constant.

### `maintenance_components`
Projected from `MAINTENANCE_COMPONENTS`: `sensor_suffix` (full suffix → counter
sensor), `proxy_for`, intervals, `label`, `icon`, and a `reset_button` block
built from `buttons.py` (§5). See [13-maintenance-manager](13-maintenance-manager.md).

### `upkeep_catalog` / `water_model_configs`
Per-model guide library + model→family maps, and tank/flow constants per model.
`water_model_configs` is projected verbatim from
`water_config.py::WATER_MODEL_CONFIGS` — today that's the physical tank trio
(`robot_internal_tank_ml` / `dock_clean_tank_capacity_ml` /
`dock_wash_overhead_ml_per_cycle`) **plus** a `water_rates` map: per-canonical-level
floor-application rate in ml/min (`off/low/medium/high = 0/3.2/4.0/5.3`, measured on
the X10 dock). Living it here (brand-owned) keeps the planning core neutral — it
reads `water_model_configs[<model>]["water_rates"]` and otherwise applies a generic
rate, so these Eufy numbers never leak onto an unconfigured brand.
**Pattern:** model-keyed reference data is plain dict literals in their own
modules, projected verbatim into the config.

> **Water-rate / wash-interval seam (`planning/run_plan.py`).** The planner reads
> three optional override hooks; absent ones fall back to the measured Eufy values.
> Two of the three are now **explicitly declared** by Eufy (no longer riding the
> absent-fallback) and one is still undeclared:
> - `water_model_configs[<model>]["water_rates"]` — per-canonical-level ml/min,
>   passed as `rate_override` to `_water_rate_ml_per_minute()`. **Declared** in
>   `water_config.py` (`off/low/medium/high = 0/3.2/4.0/5.3`); documented in the
>   `water_model_configs` body above.
> - **top-level** `wash_frequency_bounds` `{default, min, max}` — wash-cadence
>   interval clamp, read in `_derive_wash_frequency_config()`. **Declared** as a
>   real top-level adapter key (`{default: 20, min: 15, max: 25}`, sourced from the
>   `WASH_INTERVAL_*_MINUTES` constants); note it is *top-level*, **not** nested
>   under `water_model_configs`.
> - `water_model_configs[<model>]["low_clean_water_margin_ml"]` — low-water margin.
>   **Still undeclared** by Eufy; rides the framework default `300.0`. A second
>   brand with a different dock declares it to override.
>
> See [22-adapter-config-reference](22-adapter-config-reference.md).

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
