# Porting Guide — Adding a Vacuum Brand

This guide is for developers adapting eufy_vacuum to a different vacuum brand
that has a Home Assistant integration exposing named-room cleaning (Roborock,
Ecovacs, Dreame, etc.).

Read [01-architecture-overview.md](../dev/01-architecture-overview.md),
[21-adapter-system.md](../dev/21-adapter-system.md), and
[22-adapter-config-reference.md](../dev/22-adapter-config-reference.md) first —
this guide is the workflow; those are the reference.

---

## 1. What you're actually doing

eufy_vacuum is not fundamentally a Eufy integration. It is a
**room-management, queue-orchestration, learning, and automation layer** that
sits on top of any HA vacuum entity capable of cleaning named rooms. Roughly
all of the framework and all of the frontend have zero brand knowledge.

Everything brand-specific lives in a **per-vacuum adapter config** — a single
dict the framework reads from the *adapter registry* at runtime. Porting a new
brand means **writing an adapter** (a config dict plus a few small brand
modules) and **registering it** at setup. You do **not** edit core files, and
you do **not** maintain a fork — the brand-adapter abstraction already exists.

The reference adapter lives at `custom_components/eufy_vacuum/adapters/eufy/`.
A new brand is a sibling package, `adapters/<brand>/`, that produces the same
config shape.

---

## 2. The adapter, end to end

An adapter is a small package mirroring `adapters/eufy/`:

| File (eufy) | Purpose |
|---|---|
| `adapter.py` | Builds the config dict and calls `register_adapter_config(...)`. Entry point: `register_eufy_adapter_for_vacuum(hass, vacuum_entity_id)`. |
| `entities.py` | Entity-ID naming convention (role → entity_id). |
| `vocabulary.py` | Brand state-string vocabulary sets. |
| `discovery.py` | How the room list is read from the integration. |
| `lifecycle.py` | Brand lifecycle signal helpers. |
| `charging.py` | Battery/charging reads. |
| `buttons.py` | Dock-action button candidate lists. |
| `maintenance_components.py`, `upkeep_catalog.py`, `water_config.py`, `model_catalog.py`, `constants.py` | Static per-model catalogs and tuned constants. |
| `segmentor.py` | (Optional) brand CV map segmentor. |

The config dict it builds must match the schema in
`adapters/config_schema.py`. Registration is one call:

```python
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
register_adapter_config(vacuum_entity_id, config)
```

`async_setup_entry` calls your adapter's `register_*_for_vacuum` per managed
vacuum. `registry._validate_adapter(config)` runs at registration and returns a
list of issue strings (logged as warnings); a declared `dispatch.template` that
doesn't resolve to a registered engine, or a bad `mapping.segmenter_engine`, is
flagged here.

---

## 3. The config blocks you fill in

These are the real "coupling points" — all data, no code in core. Every field
is documented in [22-adapter-config-reference.md](../dev/22-adapter-config-reference.md);
this is the orientation.

| Block | Required | What it carries |
|---|---|---|
| `adapter_id`, `source` | yes | identity (`source: "code"` for a shipped adapter) |
| `entities` | yes | role → HA entity-ID map (`task_status`, `dock_status`, `active_map`, `battery`, `charging`, `robot_position_x/y`, …). Absent entities degrade the dependent feature; they never raise. |
| `dispatch` | yes | how to send a clean job (§4) |
| `vocabulary` + `completion` | no (recommended) | the raw state strings your vacuum reports (§5) |
| `capabilities` | no | feature flags (§6) |
| `discovery` | no | how the room list is exposed (§7) |
| `mapping` | no | pluggable map segmenter (§8) |
| `dock_events`, `post_job_wash_amendment`, `error_tracking`, `maintenance_components`, `upkeep_catalog`, `water_model_configs` | no | dock/error/maintenance catalogs — graceful degradation when absent |

---

## 4. Dispatch — pick (or add) an engine

`dispatch.template` selects a **dispatch engine** in
`queue/dispatch_engines.py`. Each engine produces a different payload
**structure** (not just renamed fields); the per-room field vocabulary
(`room_fields`: rename + value_map) is shared across all of them.

| Template | Wire structure | Brands |
|---|---|---|
| `eufy_room_clean` | **rows** — list of per-room dicts | Eufy |
| `roborock_segment_clean` | **flat ids + batch scalar** — `{segments:[ints], repeat:n}` | Roborock |
| `generic_room_ids` | flat ids + batch scalar (e.g. Ecovacs `{rooms:[ints], cleanings:n}`) | Ecovacs / fallback |
| `dreame_room_clean` | **columns** — positional parallel arrays | Dreame |

**If your brand fits an existing shape**, just configure the field names /
value maps — no new code. Roborock (`app_segment_clean`):

```python
"dispatch": {
    "template": "roborock_segment_clean",
    "service_domain": "vacuum", "service_name": "send_command",
    "command": "app_segment_clean",
    "rooms_field": "segments", "clean_passes_field": "repeat",
},
# → {"command": "app_segment_clean", "params": {"segments": [16, 17], "repeat": 2}}
```

Dreame (`vacuum_clean_segment`, parallel arrays via a `room_fields` transpose):

```python
"dispatch": {
    "template": "dreame_room_clean",
    "service_domain": "dreame_vacuum", "service_name": "vacuum_clean_segment",
    "rooms_field": "segments", "clean_passes_field": "repeats",
    "room_fields": {
        "fan_speed":   {"field_name": "suction_level",
                        "value_map": {"Quiet": 0, "Standard": 1, "Turbo": 2, "Max": 3}},
        "water_level": {"field_name": "water_volume",
                        "value_map": {"Low": 1, "Medium": 2, "High": 3}},
        "clean_mode": {"field_name": None}, "clean_intensity": {"field_name": None},
        "edge_mopping": {"field_name": None}, "path_type": {"field_name": None},
    },
},
# → {"segments": [3, 2], "suction_level": [0, 3], "water_volume": [1, 3], "repeats": [1, 2]}
```

The send-site envelope is also config-driven: a `command` produces the wrapped
`{command, params}` shape (Eufy/Roborock); omitting it merges the payload into
the service data directly (Dreame).

**If your wire shape is genuinely new**, add an engine in
`queue/dispatch_engines.py` (subclass the closest one, override `build_payload`)
and register it under a new `template` name. `build_room_clean_payload` in
`queue/queue_engine.py` is the shared *resolver* (profile resolution +
capability gating + canonical `resolved_rooms`) that engines reuse — you do not
replace it.

**Job model.** Engines declare `job_model` (`atomic_batch` default, or
`sequenced` for sweep-all-then-mop-all style multi-dispatch jobs via
`build_phases`). See [07-queue-engine.md](../dev/07-queue-engine.md) and
[22 §13](../dev/22-adapter-config-reference.md#13-dispatch--how-to-send-a-clean-job).

---

## 5. Lifecycle vocabulary

The framework normalizes your vacuum's raw state strings into its internal
lifecycle vocabulary **from the adapter config** — you do not edit
`listeners/lifecycle.py` or `core/manager.py`.

- `entities.task_status` / `dock_status` / `active_cleaning_target` /
  `active_map` point at the companion sensors.
- `vocabulary` declares the raw strings: `active_run_task_states`,
  `hard_service_states` (wash/recycle/empty — hard block), `drying_states`
  (warning-only), `blocked_work_mode_states`, etc.
- `completion.task_status_value` is the normalized "done" value (default
  `"completed"`); `completion.secondary_clear_sentinels` are the values that
  count the secondary signal as cleared.

Completion fires when `task_status` reaches the completion value, the secondary
target is cleared, and the job was observed active at least once. If your brand
has no `active_cleaning_target` concept, point `completion.secondary_clear_entity`
elsewhere or rely on `task_status` alone (it degrades gracefully).

---

## 6. Capabilities

Declare feature flags in the `capabilities` block:
`supports_mop_features`, `supports_water_control`, `supports_path_control`,
`supports_edge_mopping`, `supports_mop_wash`, `supports_mop_dry`,
`supports_empty_dust`, `supports_robot_position`, `supports_station_water`.
They gate payload fields, dock actions, and card UI.

The Eufy adapter auto-populates these by calling
`core/capabilities.py::detect_capabilities()` (Eufy-specific: entity-presence
probes + product-code/name model families). For a new brand, the simplest path
is to **set the flags statically** in your config's `capabilities` block based
on the hardware; provide brand-specific detection only if you need it. Either
way the flags' *meaning* is brand-agnostic — only detection is brand-specific.

---

## 7. Discovery

The `discovery` block tells the framework how the room list is exposed:

- `room_list_entity` — `"vacuum_entity"` to read an attribute off the vacuum
  entity (Eufy `segments`, Ecovacs `rooms`), or a full entity ID.
- `room_list_attribute`, `room_id_key`, `room_name_key` — where the id/name live
  in each room dict.

Brands that expose rooms via a service (Roborock `vacuum.get_maps`) or via HA
Areas (the 2026.3 `vacuum.clean_area` integrations) read those instead — no CV
segmentation needed. The Eufy CV segmentor exists because Eufy exposes no
structured room geometry.

---

## 8. Map segmentor (optional)

`mapping.segmenter_engine` selects a map-image segmenter by name from
`mapping/segmenter_engines.py` (`eufy_cv_v1`, or `noop_fallback` to disable the
polygonal overlay while trace-based bounds keep working). The Eufy CV pipeline
lives in `adapters/eufy/segmentor.py` (`detect_room_segments`) and is built on
the brand-agnostic primitives in `mapping/segment_primitives.py`.

A new brand that ships structured room geometry (most lidar brands) does not
need a CV segmentor at all — declare `noop_fallback`. If you do want an
image-based overlay, write a new segmenter engine using `segment_primitives.py`
(polygon math, mask ops, HSV helpers, alignment) and register it; copy
`adapters/eufy/segmentor.py` as the reference and re-tune its HSV thresholds /
scoring heuristics for your brand's map palette.

---

## 9. What ports for free (zero changes)

These subsystems operate entirely on the internal data model / HA service calls
and need no brand work:

- **Learning** (`learning/`) — consumes canonical `resolved_rooms` + lifecycle
  events.
- **Queue engine** (`queue/queue_engine.py`) — ordering, enabled-room filtering,
  access graph, blocker/modifier rules, start protection.
- **Room rules** (`rooms/`, `queue/`) — blockers, modifiers, access graph,
  preflight. HA state reads only.
- **Mapping/bounds** (`mapping/`) — trace-based bounds from position sensors
  (coordinate units may need adjustment per brand).
- **HA entity platforms** — `button.py`, `switch.py`, `number.py`, `sensor/`
  (the integration registers **five** platforms: `binary_sensor`, `button`,
  `switch`, `number`, `sensor` — there is no `select` platform).
- **Listeners** (`listeners/` package) — lifecycle/finalize, job progress, dock
  events, path blockers, pause timeout. Driven by adapter config.
- **Card frontend, theme system, profile system** — fully brand-agnostic.

---

## 10. Validate with the contract harness

There is no fork to maintain. The brand-agnostic **adapter conformance suite**
(`tests/adapters/test_adapter_contract.py`) validates *any* adapter's config
against the documented schema and runtime expectations. Add your brand to the
`ADAPTER_BUILDERS` registry in `tests/adapters/conftest.py` and the entire
contract suite runs against it automatically — schema conformance, dispatch
shape, entity-ID format, registry validation. Brand-specific deep tests (your
CV segmentor, your model catalog) live under `tests/adapters/<brand>/`.

---

## 11. Port checklist

Each step is independently testable.

1. **Map the HA entities** your vacuum exposes to the `entities` role keys
   (`task_status`, `dock_status`, `active_map`, `battery`, position sensors, …).
   Document the IDs before writing code.
2. **Write the `vocabulary` + `completion` blocks** — every raw state string,
   sorted into `active_run_task_states` / `hard_service_states` / `drying_states`
   / blocked sets, and the completion value. Ensure at least one state marks the
   job "observed active."
3. **Choose a `dispatch.template`.** If an existing shape fits, configure field
   names + value maps. If not, add an engine in `dispatch_engines.py`.
4. **Set `capabilities`** flags for the hardware. Set `discovery` for how rooms
   are listed. Set `mapping` to `noop_fallback` unless you wrote a segmentor.
5. **Build the config dict** in `adapters/<brand>/adapter.py` and register it
   from `async_setup_entry`.
6. **Add the brand to `ADAPTER_BUILDERS`** and run `pytest tests/adapters` — the
   conformance suite must pass.
7. **Run a real job with learning disabled**: confirm the dispatch reaches the
   vacuum, the job is observed active, it auto-finalizes, and the active-job
   record clears. Then enable learning and confirm per-room timing accumulates.
8. **(Optional) Map overlay**: place a PNG at the maps path and use the card's
   bounds calibration, or rely on colour-coded bounds boxes with no image.

If the brand has a real user base, ship the adapter upstream as a new
`adapters/<brand>/` package rather than keeping it local — that is the whole
point of the adapter boundary.
