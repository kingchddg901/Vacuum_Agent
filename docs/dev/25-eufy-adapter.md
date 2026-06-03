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
discovery, a rich dispatch payload, and a CV map segmenter. A minimal adapter
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
| `constants.py` | Tuning scalars: debounce/timeout seconds, low-battery threshold. |
| `entities.py` | `build_entity_id()` + every `SUFFIX_*` / `DOMAIN_*` constant — the entity-naming convention. |
| `vocabulary.py` | State-string sets and alias maps (hard-service, drying, active-run, not-error, cancel-exclusion, water-level/wash-frequency aliases, dock-event triggers). |
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
tracking keeps working off coordinates.

### `capabilities`
Every flag is sourced from `detect_capabilities()` (`caps.get(...)`), **not**
hardcoded — so the registered config matches the install's real entity surface.

### `maintenance_components`
Projected from `MAINTENANCE_COMPONENTS`: `sensor_suffix` (full suffix → counter
sensor), `proxy_for`, intervals, `label`, `icon`, and a `reset_button` block
built from `buttons.py` (§5). See [13-maintenance-manager](13-maintenance-manager.md).

### `upkeep_catalog` / `water_model_configs`
Per-model guide library + model→family maps, and tank/flow constants per model.
**Pattern:** model-keyed reference data is plain dict literals in their own
modules, projected verbatim into the config.

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
