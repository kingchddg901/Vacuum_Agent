# Porting Guide

This guide is for developers who want to adapt eufy_vacuum to work with a
different vacuum brand. It covers both a generic port (any vacuum that has a
Home Assistant entity) and a specific port to Roborock or Dreame, which already
have mature HA integrations with a similar room-cleaning pattern.

Read [architecture-overview.md](architecture-overview.md) and
[queue-engine.md](queue-engine.md) before continuing here.

---

## 1. What this system actually is

eufy_vacuum is not fundamentally a Eufy integration. It is a
**room-management, queue-orchestration, learning, and automation layer** that
sits on top of any HA vacuum entity capable of cleaning named rooms.

The vacuum brand is almost incidental to the vast majority of the codebase.
Roughly 95% of the Python and all of the frontend JavaScript have no Eufy
knowledge whatsoever. Only two narrow seams connect the generic layer to
the specific hardware:

1. **The queue payload format** — the data structure the vacuum's clean service
   expects to receive when a room-clean job is dispatched.
2. **The lifecycle state names** — the raw strings the vacuum entity and its
   companion sensors report, which the system normalises into its own internal
   lifecycle vocabulary.

Everything else — learning, rules, profiles, the card, the map trace engine —
operates entirely on the internal vocabulary produced by those two seams.

---

## 2. The two coupling points in detail

### 2.1 The queue payload format

The actual HA service call that dispatches a room-clean job is in
`core/manager.py` at `async_start_room_clean_job()`:

```python
await self.hass.services.async_call(
    "vacuum",
    "send_command",
    {
        "entity_id": vacuum_entity_id,
        "command": "room_clean",
        "params": payload,
    },
    blocking=True,
)
```

`payload` is the `dict` produced by `queue/queue_engine.py ::
build_room_clean_payload()`. Its structure is:

```python
{
    "map_id": int | str,   # e.g. 6  (Eufy uses an integer map ID)
    "rooms": [
        {
            "id": int,                 # Eufy room ID (1–11 for this installation)
            "clean_times": int,        # number of passes
            "fan_speed": str,          # "Standard", "Boost", etc.
            "clean_mode": str,         # "vacuum", "mop", "vacuum_mop"
            "clean_intensity": str,
            # conditionally present:
            "water_level": str,        # only for mop/vacuum_mop + supports_water_control
            "edge_mopping": bool,      # only for mop/vacuum_mop + supports_edge_mopping
            "path_type": str,          # only when supports_path_control
        },
        ...
    ]
}
```

This is a Eufy-specific format. `robovac_mqtt` (the underlying Eufy cloud
integration) interprets `room_clean` with this schema and translates it into
the Eufy protocol. No other part of the eufy_vacuum codebase reads or produces
this structure — `build_room_clean_payload()` is the single place it is
assembled, and `async_start_room_clean_job()` is the single place it is sent.

### 2.2 The lifecycle state names

The lifecycle watcher in `__init__.py` reads five HA entities derived from the
vacuum's `object_id`:

| Role | Entity |
|---|---|
| Vacuum state | `vacuum.<object_id>` |
| Task status | `sensor.<object_id>_task_status` |
| Dock status | `sensor.<object_id>_dock_status` |
| Active cleaning target | `sensor.<object_id>_active_cleaning_target` |
| Active map | `sensor.<object_id>_active_map` |

These are Eufy/robovac-mqtt sensor names. The raw state strings that the system
responds to (matched case-insensitively after `.strip().lower()`) are:

**Vacuum entity states consumed:**
- `docked`, `idle`, `paused` — treated as "ready to accept a job"
- `cleaning`, `returning`, `error` — treated as "active or faulted"

**task_status strings consumed** (in `job_monitor.py :: evaluate_job_lifecycle`):
- `completed` — the primary signal that a job finished successfully
- `cleaning`, `room cleaning`, `spot cleaning`, `returning`, `resuming`,
  `navigating` — treated as active_run_states
- `washing`, `washing mop`, `recycling waste water`, `recycling wastewater`,
  `emptying dust`, `emptying dust bin`, `dust emptying` — hard blockers
- `drying`, `drying mop`, `drying pads`, `mop drying` — warning-only (drying)

**dock_status strings consumed:**
- Same washing/drying/emptying sets as above, but sourced from the dock sensor
- Additionally, transitions to `washing` or `washing mop` trigger the
  post-job mop-wash water amendment in `__init__.py`

**active_cleaning_target:**
- Any non-empty, non-sentinel value means cleaning is in progress
- Sentinel values: `""`, `"unknown"`, `"unavailable"`, `"none"`, `"null"`

**Completion condition** (all three must be true simultaneously):
1. `task_status == "completed"`
2. `active_cleaning_target` is cleared (sentinel value)
3. `has_observed_active_lifecycle` flag set (confirms the job actually moved)

The `_ACTIVE_LIFECYCLE_STATES` constant in `__init__.py` lists the two
internal states that set this flag:
```python
_ACTIVE_LIFECYCLE_STATES = {
    "active_job_running",   # vacuum is actively cleaning
    "mid_job_service",      # dock is servicing mid-job
}
```

These are *internal* names produced by `evaluate_job_lifecycle()` in
`job_monitor.py`, not raw sensor values.

### 2.3 Capability detection

`core/capabilities.py :: detect_capabilities()` is also Eufy-specific. It
derives entity names by appending well-known suffixes to `object_id`, detects
model family from Eufy product codes (T2351, T2320, etc.) and name hints
(x10, x8, l60, …), and sets capability flags.

Flags use one of two detection strategies:

- **Entity presence** — check whether the upstream integration registered the
  entity (state machine or registry). No model knowledge required.
- **Model family** — infer from the product code or name hint. Used when the
  capability corresponds to a payload field or behaviour that has no
  representative entity to probe.

Where model family is the primary signal, an entity-based fallback is applied
wherever a corresponding button entity can be probed. This prevents a legitimate
device from losing capabilities solely because its product code was not in
`MODEL_CODE_FAMILIES`.

#### MODEL_CODE_FAMILIES mapping

Product code → family name. A product code is the raw string from the vacuum's
`detected_model` attribute (e.g. `"T2351"`). Unrecognised codes fall back to
`"generic"`.

| Product code | Family |
|---|---|
| T2351 | x10 |
| T2320 | x10 |
| T2261 | x8 |
| T2262 | x8 |
| T2266 | x8 |
| T2276 | x8 |
| T2267 | l60 |
| T2268 | l60 |
| T2277 | l60 |
| T2278 | l60 |
| T2280 | c20 |
| T2080 | s1 |
| T2071 | s1 |
| T2210 | g50 |
| T2255 | g40 |
| T2256 | g40 |
| T2192 | lr30 |
| T2193 | lr30 |
| T2181 | lr30 |
| T2194 | lr30 |
| T2182 | lr30 |

If the raw code is not in this table, `_detect_model_family` falls back to
`MODEL_FAMILY_HINTS`, which matches substrings (case-insensitive) in the full
model string: `"x10"`, `"x8"`, `"l60"`, `"l50"`, `"g50"`, `"g40"`, `"lr30"`.
If neither matches, the family is `"generic"`.

#### Capability flags

Each flag is a `bool` in the returned capabilities dict. The table below shows
how each flag is set and what it controls downstream.

Flags marked **model + entity fallback** use model family as the primary check
and additionally probe for the presence of the corresponding upstream button
entity in the HA registry. If the model resolves to `"generic"` but the button
exists, the capability is still `True`.

Flags marked **model only** have no representative entity to probe — they gate
payload fields sent to the vacuum, not HA entities. An unrecognised model that
needs these features must be added to `MODEL_CODE_FAMILIES`.

| Flag | Detection | What it controls |
|---|---|---|
| `supports_mop_features` | Model family (`x10`, `x8`, `l60`, `l50`) **or** `water_level` entity present | Enables mop-related clean modes (`"mop"`, `"vacuum_mop"`) in the profile system and card UI |
| `supports_water_control` | Alias for `supports_mop_features` | Gates the `water_level` field in the queue payload (added only for mop/vacuum_mop modes) |
| `supports_path_control` | Model + entity fallback — `x10`/`x8` or `select.*_cleaning_intensity` present (eufy-clean exposes this with options `Normal`, `Narrow`, `Quick` on path-capable hardware) | Gates the `path_type` field in the queue payload (added regardless of clean mode) |
| `supports_edge_mopping` | Model only — `x10` or `x8` | Gates the `edge_mopping` field in the queue payload (added only for mop/vacuum_mop modes) |
| `supports_passes` | Always `True` | Enables the `clean_times` field in the payload; reserved for future per-model restriction |
| `supports_mop_wash` | Model + entity fallback — `x10`/`x8` or `button.*_wash_mop` / `button.*_mop_wash` present | Enables dock mop-wash service calls and dock event recording for `last_mop_wash` |
| `supports_mop_dry` | Model + entity fallback — `x10`/`x8` or `button.*_dry_mop` / `button.*_mop_dry` present | Enables dock mop-dry service calls |
| `supports_empty_dust` | Model + entity fallback — `x10`/`x8`/`l60`/`l50` or `button.*_empty_dust` / `button.*_empty_dust_bin` present | Enables dock dust-empty service calls |
| `supports_robot_position` | Entity presence — both position entities registered | Enables trace-based room bounds derivation in the mapping subsystem |
| `supports_station_water` | Entity presence — `water_level` entity registered | Used by the card to display station water level |
| `supports_dock_status` | Entity presence — dock status entity registered | Used by lifecycle watcher to monitor dock state |
| `supports_task_status` | Entity presence — task status entity registered | Required for the completion detection logic in `__init__.py` |
| `supports_cleaning_stats` | Entity presence — `cleaning_area` or `cleaning_time` registered | Enables area/time display in the card |

#### How capability flags gate the queue payload

`build_room_clean_payload()` in `queue/queue_engine.py` reads the flags and
conditionally adds fields to each room's payload entry:

| Payload field | Always present | Condition for inclusion |
|---|---|---|
| `id` | Yes | — |
| `clean_times` | Yes | — (always included; `supports_passes` is currently always `True`) |
| `fan_speed` | Yes | — |
| `clean_mode` | Yes | — |
| `clean_intensity` | Yes | — |
| `water_level` | No | `supports_water_control` is `True` **and** `clean_mode` is `"mop"` or `"vacuum_mop"` |
| `edge_mopping` | No | `supports_edge_mopping` is `True` **and** `clean_mode` is `"mop"` or `"vacuum_mop"` |
| `path_type` | No | `supports_path_control` is `True` (added regardless of clean mode) |

The capability flags themselves (`supports_mop_features`,
`supports_water_control`, `supports_path_control`, `supports_edge_mopping`,
`supports_passes`) are used by `build_room_clean_payload()` to gate optional
payload fields. These flags are brand-agnostic in meaning; only the detection
logic is Eufy-specific.

### 2.4 Position tracking

The mapping tracker (`mapping/tracker.py`) reads two position sensors:
- `sensor.<object_id>_robot_position_x_raw`
- `sensor.<object_id>_robot_position_y_raw`

These are robovac-mqtt-specific entity names. The coordinate space and units
are also Eufy-specific (see [mapping-system.md](mapping-system.md)).

---

## 3. Generic port — what to replace

### 3.1 The queue payload builder

`queue/queue_engine.py :: build_room_clean_payload()` must be replaced (or
made brand-aware via a strategy object). The function's contract with the rest
of the system is:

**Inputs** (all keyword arguments):
- `vacuum_entity_id: str`
- `map_id: str`
- `managed_rooms: dict[str, dict]` — the rooms config from storage
- `queue_room_ids: list[int] | None` — the subset of room IDs to include
- `stored_profiles: dict[str, dict] | None` — named room profiles
- `capabilities: dict[str, Any] | None` — capability flags dict

**Required output shape:**
```python
{
    "vacuum_entity_id": str,
    "map_id": str,
    "payload": dict,       # the brand-specific service call data
    "resolved_rooms": list[dict],  # one entry per room, for job tracking
    "room_count": int,
}
```

`resolved_rooms` is consumed by the learning system and job tracking. Each
entry must contain at minimum: `room_id`, `name`, `slug`, `clean_mode`,
`fan_speed`, `clean_passes`. The other fields (`water_level`, `path_type`,
etc.) can be omitted if the target vacuum does not support them.

`payload` is opaque to the rest of the system — only the single service call
site in `manager.py` reads it.

### 3.2 The service call itself

In `core/manager.py`, the service call:

```python
await self.hass.services.async_call(
    "vacuum",
    "send_command",
    {"entity_id": vacuum_entity_id, "command": "room_clean", "params": payload},
    blocking=True,
)
```

must be replaced with whatever service and data structure the target vacuum
integration expects. This is a single call site. No other code dispatches to
the vacuum hardware.

### 3.3 The lifecycle state mapping

Replace the raw state strings in `job_monitor.py :: evaluate_job_lifecycle()`
with the strings your target vacuum reports. The function must continue to
produce the same output dictionary shape with the same `lifecycle_state` keys:
`"ready"`, `"active_job_running"`, `"mid_job_service"`, `"dock_drying"`,
`"vacuum_busy"`, `"map_mismatch"`.

The completion detection logic in `__init__.py` looks for:
- `task_status == "completed"` (exact normalised string)
- `active_cleaning_target` cleared

If your target vacuum does not have an `active_cleaning_target` concept,
clear the sentinel artificially when the vacuum entity returns to `docked`
and `task_status` reaches its equivalent of "completed".

### 3.4 Capability detection

Replace `core/capabilities.py :: detect_capabilities()` with a version that:
1. Discovers the correct companion sensor entity IDs for your vacuum.
2. Sets capability flags based on your vacuum's actual hardware.
3. Returns a dict with the same keys — particularly `supports_mop_features`,
   `supports_water_control`, `supports_path_control`, `supports_edge_mopping`,
   `supports_passes`, and the `entities` sub-dict.

For flags that correspond to dock action buttons (`supports_mop_wash`,
`supports_mop_dry`, `supports_empty_dust`), prefer probing entity registry
presence over a hardcoded model name. If entity presence is the primary check,
an unrecognised model that actually has the button still gets the capability
set correctly rather than silently disabled. Use `_state_exists` or
`_registry_entry_exists` from `capabilities.py` for this.

For `supports_path_control`, eufy-clean exposes `select.*_cleaning_intensity`
on path-capable hardware — probe that entity as a fallback. For
`supports_edge_mopping` there is no representative eufy-clean entity (the
edge_mop input_booleans belong to this integration, not the upstream one) — set
it based on whatever model or feature identifier your target integration exposes.

The `entities` sub-dict keys consumed elsewhere are: `task_status`,
`dock_status`, `active_map`, `active_cleaning_target`, `robot_position_x`,
`robot_position_y`.

### 3.5 The watched entity list

`__init__.py :: _get_lifecycle_watch_entities()` constructs entity IDs from
`object_id` using Eufy/robovac-mqtt naming conventions. Replace with your
target entity IDs.

### 3.6 robovac_mqtt dependency

The robovac-mqtt HACS integration provides:
- The `vacuum.<object_id>` entity with `send_command` support and the
  `room_clean` command
- All the companion sensors (`_task_status`, `_dock_status`, `_active_map`,
  `_active_cleaning_target`, `_robot_position_x_raw`,
  `_robot_position_y_raw`, etc.)
- The Eufy cloud connection and protocol translation

A port to another brand replaces the entire robovac-mqtt layer with whatever
HA integration the target brand uses. eufy_vacuum itself has no direct
dependency on robovac-mqtt's Python package — it only depends on HA entities
being present with the right names and states.

### 3.7 Map image format

The card can display a map image behind the room bounds overlay. eufy_vacuum
does not process the map image itself — it serves whatever image file is placed
at `<config_dir>/eufy_vacuum/maps/<map_id>.png`. The image is sourced manually
or by a robovac-mqtt helper script. For a Roborock/Dreame port, see section
4.5 below.

---

## 4. Roborock and Dreame specific port

Roborock and Dreame both have maintained HA integrations and a similar
room-cleaning model. The mapping below applies to the official `roborock`
integration (available in HA core since 2023.3) and to Dreame via
`hacs/dreame-vacuum`.

### 4.1 HA entities exposed

**Roborock (official integration):**
| Entity | Role |
|---|---|
| `vacuum.<name>` | Main vacuum entity |
| `sensor.<name>_status` | Equivalent to task_status |
| `sensor.<name>_dock_status` | Dock status (S7 MaxV Ultra, Q Revo, etc.) |
| Various `sensor.*` | Battery, area, time |

**Dreame (dreame-vacuum):**
| Entity | Role |
|---|---|
| `vacuum.<name>` | Main vacuum entity |
| `sensor.<name>_task_status` or `sensor.<name>_status` | Task status |
| `sensor.<name>_dock_status` | Present on stations with mop wash |

Neither integration exposes an `active_cleaning_target` sensor. For the
completion logic, the most reliable substitute is to treat
`active_cleaning_target` as cleared when the vacuum state returns to
`docked` and status reaches the "completed" equivalent.

### 4.2 Room-cleaning service call — Roborock

The official Roborock integration exposes rooms as segments. The service to
clean specific segments is:

```yaml
service: vacuum.send_command
data:
  entity_id: vacuum.<name>
  command: app_segment_clean
  params:
    segments: [3, 5, 7]   # list of segment IDs
    repeat: 1              # number of passes
```

For a Roborock port, `build_room_clean_payload()` must produce a `payload`
containing a segment list and repeat count. Per-room fan speed overrides
are supported on some models via:

```yaml
params:
  segments:
    - id: 3
      fan_power: 102    # Roborock fan speed integer values
    - id: 5
      fan_power: 102
  repeat: 1
```

The map concept in Roborock is a "floor" — `map_id` can be mapped to the
Roborock floor/map index. Multi-floor support requires selecting the active
floor before cleaning, which Roborock exposes as a select entity.

### 4.3 Room-cleaning service call — Dreame

The dreame-vacuum integration uses a different command:

```yaml
service: vacuum.send_command
data:
  entity_id: vacuum.<name>
  command: start_sweep_with_room_id
  params:
    rooms: [3, 5, 7]
```

Some Dreame models support per-room settings via the
`vacuum.set_room_settings` service. For a Dreame port, `build_room_clean_payload()`
produces a rooms list (integer segment IDs) plus an optional settings block.

### 4.4 Lifecycle state mapping

**Roborock vacuum entity states:** `cleaning`, `returning`, `docked`, `idle`,
`paused`, `error`. These match the eufy_vacuum internal expectations almost
exactly — `evaluate_job_lifecycle()` already handles `docked` and `idle` as
"ready" and `cleaning`/`returning` as active.

**Roborock task status equivalents:**
| eufy_vacuum internal state | Roborock sensor value |
|---|---|
| `completed` | `"Idle"` when vacuum returns to dock after segment clean |
| active_run_states | `"Segment cleaning"`, `"Returning home"` |
| hard_service_states | `"Washing"`, `"Drying"` (S7/Q Revo dock sensors) |

For Roborock, completion detection cannot rely on a
`task_status == "completed"` string. Instead, monitor the vacuum entity state
transitioning to `docked` while `active_cleaning_target` is cleared (or
there is no such concept and the job count is satisfied).

**Dreame:** Similar to Roborock. The dreame-vacuum integration does expose a
`task_status` sensor with values like `"idle"`, `"cleaning"`, `"returning"`.
Map to `completed` when `task_status` is `"idle"` and `vacuum` is `docked`.

### 4.5 Map handling

Both Roborock and Dreame use cloud-hosted map images, served as camera entities
by their HA integrations. These are rendered SVG or PNG overlays generated from
the vacuum's own map data.

eufy_vacuum's map display uses static PNG files placed in
`<config_dir>/eufy_vacuum/maps/`. For Roborock/Dreame, the simplest approach
is:

1. Capture a screenshot of the camera entity's current map image using an HA
   automation or script.
2. Save it to the maps directory at the correct path for the map_id.
3. Use the bounds calibration tool in the card (see
   [map-bounds-review.md](../advanced/07-map-bounds-review.md)) to align the
   overlay with the saved image.

The `image_segments` pipeline (trace-based room boundary derivation) runs
entirely on the saved PNG and does not require an active camera feed. It
operates on pixel coordinates and produces room polygon bounds — these bounds
are brand-agnostic.

Alternatively, skip the map image entirely. The card renders room bounds
boxes even without a background image, using colour-coded overlays only.

---

## 5. What ports for free

The following subsystems require zero changes to port to a different vacuum
brand. They operate entirely on the internal data model and HA service calls
that are not vacuum-specific.

**Learning system** (`learning/`) — records per-room timing observations,
computes confidence scores, detects trouble rooms, estimates future job
duration. Consumes the `resolved_rooms` list from the payload builder and
job lifecycle events from the watcher. Brand-agnostic.

**Queue engine logic** (`queue/queue_engine.py`) — room ordering, enabled-room
filtering, access graph evaluation, blocker/modifier rule processing, start
protection checks. Has no vacuum knowledge beyond the capability flags passed
to it.

**Room rules system** (`rooms/`, `queue/`) — blocker rules, modifier rules,
the access graph, preflight evaluation. Operates entirely on HA entity state
reads and room configuration. No vacuum calls.

**Mapping/bounds system** (`mapping/`) — trace-based room boundary derivation
from position sensor coordinates, the bounds editor, the calibration overlay.
Reads `robot_position_x` and `robot_position_y` entities (entity IDs are
configurable). The coordinate normalisation assumes a specific coordinate space
(see [mapping-system.md](mapping-system.md)) — this is the only part that
may need adjustment if the target vacuum uses a different unit or origin.

**HA entity layer** (`button.py`, `switch.py`, `number.py`, `sensor.py`,
`select.py`) — all HA platform entities. These call internal manager methods;
they have no vacuum brand knowledge.

**Card frontend** (`frontend/`) — the entire Lit-based card. It calls
`eufy_vacuum.*` HA services and reads `eufy_vacuum.*` sensor/switch entities.
It has no knowledge of the underlying vacuum brand. No changes required for
any port.

**Theme system** — CSS custom property injection, theme profiles, colour
tokens. Entirely UI-layer, brand-agnostic.

**Profile system** (`profiles/`) — named room profiles (`vacuum_quick`,
`vacuum_deep`, etc.), capability gating, floor-type overrides. The profile
names and settings map to payload fields — these will need to match whatever
settings the target vacuum accepts, but the profile resolution logic itself
is brand-agnostic.

---

## 6. Port checklist

Follow these steps in order. Each step is independently testable before
proceeding to the next.

### Step 1 — Map the vacuum's HA entities

Identify the equivalent of each entity that eufy_vacuum watches:

- `vacuum.<object_id>` — must support `send_command` or an equivalent service
- `sensor.*_task_status` — reports task phase; must eventually reach a
  "completed" or "idle" state when a clean finishes
- `sensor.*_dock_status` — reports dock activity (wash, dry, empty); may be
  absent on simpler stations
- `sensor.*_active_cleaning_target` — optional; the current room/segment
  being cleaned; cleared on finish
- `sensor.*_active_map` — the currently loaded floor map; required for
  multi-floor setups
- `sensor.*_robot_position_x_raw` and `*_y_raw` — position coordinates for
  trace-based bounds; optional (skip if not available)

Document these entity IDs before writing any code.

### Step 2 — Map lifecycle states

For each raw state string your vacuum reports across all five entities, decide
which internal lifecycle category it belongs to:

| Internal state | Meaning | Sets `has_observed_active_lifecycle` |
|---|---|---|
| `ready` | Vacuum is docked/idle, safe to start | No |
| `active_job_running` | Vacuum is actively cleaning | **Yes** |
| `mid_job_service` | Dock is washing/emptying mid-job | **Yes** |
| `dock_drying` | Dock is drying; start still allowed | No |
| `vacuum_busy` | Vacuum is busy for an unrelated reason | No |
| `map_mismatch` | Selected floor ≠ active floor | No |

Produce a table mapping every raw sensor value you observe to one of these.
The completion signal requires `has_observed_active_lifecycle` to have been
set at least once during the job — ensure at least one of your vacuum's states
maps to `active_job_running` or `mid_job_service`.

### Step 3 — Write a new queue payload builder

Create a new `build_room_clean_payload()` implementation that:

1. Accepts the same input signature as the existing function.
2. Iterates over `managed_rooms`, filters by `queue_room_ids`, resolves
   profiles, applies capability gating.
3. Produces a `payload` dict in the format your vacuum's service expects.
4. Returns the full output shape (`payload`, `resolved_rooms`, `room_count`).

The `resolved_rooms` list must contain each room's `room_id`, `name`, `slug`,
`clean_mode`, and `fan_speed` at minimum — these are read by the learning
system and job tracking.

### Step 4 — Update the service call and watched entities

In `core/manager.py`, replace the `vacuum.send_command` / `room_clean` call
with your target service.

In `__init__.py`, replace `_get_lifecycle_watch_entities()` to return the
entity IDs you documented in step 1.

In `core/capabilities.py`, replace `detect_capabilities()` to discover your
vacuum's entities and set appropriate capability flags.

### Step 5 — Verify with learning disabled

Set `learning_enabled: false` in the integration config and run a complete job:

1. Confirm the service call reaches the vacuum and cleaning starts.
2. Confirm `has_observed_active_lifecycle` gets set (check via the job sensor
   or logs).
3. Confirm the job auto-finalizes when cleaning completes.
4. Confirm the active job record clears correctly.

Resolve any entity naming or state-string mismatches before enabling learning.

### Step 6 — Enable learning and verify timing data

Enable learning and run several complete jobs. Verify:

1. Job files are written to `<config_dir>/eufy_vacuum/jobs/`.
2. Per-room timing observations accumulate in the stats file.
3. Expected duration estimates appear in the card.

If timing data is absent, check that `resolved_rooms` in the payload output
contains valid `room_id` values matching the room IDs in storage.

### Step 7 — Map image calibration (optional)

If you want the map image overlay:

1. Obtain a PNG of your vacuum's floor map at a known, stable zoom level.
2. Place it at `<config_dir>/eufy_vacuum/maps/<map_id>.png`.
3. Use the bounds calibration tool in the card to set the pixel-to-coordinate
   transform for each corner of the map.
4. Verify room bounds overlay correctly on the image.

If position sensors are not available, you can draw room bounds manually
using the bounds editor — the image still displays correctly.

---

## 7. Maintaining a fork

### Upstream sync strategy

The two coupling-point files are the most likely to diverge from upstream:
- `core/manager.py` (the service call site and job start logic)
- `__init__.py` (entity watch list and completion signals)
- `core/capabilities.py` (entity discovery and capability flags)

Keep your modifications in clearly marked sections or extract them into a
`core/brand_adapter.py` module that the above files import from. This makes
rebasing onto upstream straightforward — your changes are isolated to the
adapter module.

### What is safe to customise locally without conflict risk

- `core/capabilities.py` — this file has no upstream PR activity that would
  affect a brand other than Eufy
- Additional sensor entity IDs in `_get_lifecycle_watch_entities()` — additive
  changes that don't remove the existing sensor set
- Post-job water amendment logic in `__init__.py` — this is X10-specific and
  can be stubbed out with a no-op for vacuums that don't have mop stations
- `MODEL_CODE_FAMILIES` and `MODEL_FAMILY_HINTS` in `capabilities.py` — adding
  your brand's model codes is safe and non-conflicting

### What will conflict on upstream updates

- The `payload` dict format in `build_room_clean_payload()` — upstream may
  add new optional fields (e.g. if Eufy adds a new capability); your override
  will not receive these changes automatically. Run the test suite after each
  rebase to catch shape mismatches.
- `_ACTIVE_LIFECYCLE_STATES` in `__init__.py` — if upstream adds a new
  lifecycle state here, your fork needs to evaluate whether your vacuum can
  produce the equivalent.
- `evaluate_job_lifecycle()` in `job_monitor.py` — the normalised state string
  sets in this function may grow. Review diffs here after each rebase.

### Forking vs contributing

If the target brand has a significant user base, consider contributing a
brand-adapter protocol upstream (a `BrandAdapter` abstract base or similar)
rather than maintaining a fork. The existing structure strongly suggests this
abstraction would be clean — the seams are already narrow and well-defined.
