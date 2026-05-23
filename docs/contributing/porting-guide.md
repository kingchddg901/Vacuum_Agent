# Porting Guide

This guide is for developers who want to use eufy_vacuum's framework
to manage a vacuum from a different brand — Roborock, Dreame, Narwal,
or anything else Home Assistant can talk to.

Read [architecture-overview.md](../dev/architecture-overview.md) first if you
haven't, and keep [adapter-config-reference.md](../dev/adapter-config-reference.md)
open in another tab — it's the canonical schema reference and this
guide will link to it constantly.

> If you're applying the same approach to a non-vacuum HA integration
> (thermostat, lock, EV charger, etc.), the underlying pattern is
> documented in its own repo: [ha-adapter-pattern](https://github.com/kingchddg901/ha-adapter-pattern).
> This porting guide stays focused on vacuum-specific concerns — the
> standalone guide covers the pattern itself, decoupled from the
> domain.

---

## 1. The porting story in one sentence

**A port is one adapter config dict. No framework code changes
required.**

That used to be aspirational. As of the dispatch refactor it is
literally true: every brand-specific fact the framework needs —
entity IDs, vocabulary, water tank measurements, upkeep guides, the
service call envelope, the per-room payload field names and value
vocabularies — is read at runtime from `get_adapter_config(vacuum_entity_id)`.

The Eufy adapter at `custom_components/eufy_vacuum/adapters/eufy/adapter.py`
is the reference implementation. A port produces an equivalent dict
for the target brand and calls `register_adapter_config()` with it.

---

## 2. The five-step workflow

1. **Identify the upstream HA integration** for your vacuum (the
   thing that exposes `vacuum.<your_vacuum>` as an HA entity) and
   read its service documentation. You need to know the service
   domain, service name, and parameter shape for "start cleaning
   specific rooms".
2. **Discover the entity IDs** the framework needs (task_status,
   dock_status, battery, charging, water_level, etc.) — see
   [adapter-config-reference.md §5](../dev/adapter-config-reference.md#5-entities--the-role-to-entity-id-map).
3. **Translate the brand vocabulary** to the framework's canonical
   states. Lifecycle uses `cleaning`/`returning`/`paused`/`error` from
   the HA standard; the rest (dock_status strings, task_status
   strings) flows through alias maps you supply. The most reliable way
   to discover what raw strings your brand actually emits — and in
   what order — is to **record a real clean cycle with
   [`ha-state-timeline-card`](https://github.com/kingchddg901/ha-state-timeline-card)**
   and read the transitions off the trace. See §4 below.
4. **Build the adapter config dict** by copying the Eufy reference and
   filling in your brand's values.
5. **Register it** at integration setup. Eufy does this via
   `register_eufy_adapter_for_vacuum()`; your brand follows the same
   pattern, ideally in its own module under
   `adapters/<your_brand>/adapter.py`.

That's the whole port. Sections 3-7 below are reference material for
the steps above.

---

## 3. Brand catalog

Worked dispatch examples for the four most common brands. Each section
shows just the `dispatch` block — see
[adapter-config-reference.md §13](../dev/adapter-config-reference.md#13-dispatch--how-to-send-a-clean-job)
for what the full adapter config looks like.

> **Caveat on these examples:** vacuum integrations vary across
> firmware revisions and integration versions. Treat the examples
> below as the *shape* of the config — verify the exact service name,
> command string, and field types against your installed integration
> before assuming the port will work end-to-end.

### 3.1 Eufy (reference implementation)

**Upstream integration:** `robovac_mqtt` exposes a `vacuum.send_command`
service with `command: "room_clean"` and a `params` dict containing
`map_id` (int) and a `rooms` array of per-room dicts.

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
    "room_fields": {
        "fan_speed":       {"field_name": "fan_speed",       "value_map": None},
        "clean_mode":      {"field_name": "clean_mode",      "value_map": None},
        "clean_intensity": {"field_name": "clean_intensity", "value_map": None},
        "water_level":     {"field_name": "water_level",     "value_map": None},
        "edge_mopping":    {"field_name": "edge_mopping",    "value_map": None},
        "path_type":       {"field_name": "path_type",       "value_map": None},
    },
},
```

**Resulting service call:**

```python
await hass.services.async_call(
    "vacuum",
    "send_command",
    {
        "entity_id": "vacuum.alfred",
        "command": "room_clean",
        "params": {
            "map_id": 6,
            "rooms": [
                {"id": 1, "clean_times": 2, "fan_speed": "Standard",
                 "clean_mode": "vacuum_mop", "water_level": "Medium",
                 "edge_mopping": True, "path_type": "Standard",
                 "clean_intensity": "Strong"},
                # ...
            ],
        },
    },
    blocking=True,
)
```

### 3.2 Roborock

**Upstream integration:** Home Assistant's first-party `roborock`
integration exposes `vacuum.send_command` with `command: "app_segment_clean"`.
The exact params shape varies across integration generations; the
modern dict-based form takes a `segments` list of per-room dicts with
integer-coded fan and water values.

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
    "room_fields": {
        "fan_speed": {
            "field_name": "fan_power",
            "value_map": {
                "Quiet":    101,
                "Standard": 102,
                "Boost":    103,
                "Max":      104,
                "Max+":     105,
            },
        },
        "clean_mode": {
            "field_name": "mop_mode",
            "value_map": {
                "vacuum":     300,
                "vacuum_mop": 302,
                "mop":        304,
            },
        },
        "water_level": {
            "field_name": "water_box_mode",
            "value_map": {
                "Low":    200,
                "Medium": 201,
                "High":   202,
            },
        },
        # Fields Roborock doesn't expose — omitted entirely.
        "edge_mopping":    {"field_name": None},
        "clean_intensity": {"field_name": None},
        "path_type":       {"field_name": None},
    },
},
```

**Verification points before shipping:**
- Confirm `app_segment_clean` (vs `app_zoned_clean`, `app_goto_target`)
  matches your vacuum's room-cleaning verb.
- Roborock's fan-power codes drifted between Gen 1 (101-104) and Gen
  2+ (101-105 with Max+, sometimes 106 for off). Verify against your
  model.
- Some Roborock vacuums don't accept per-room water settings — those
  need `water_level: {"field_name": None}` instead.

### 3.3 Dreame

**Upstream integration:** The community `dreame_vacuum` integration
exposes brand-specific services like `dreame_vacuum.vacuum_clean_segment`.
Unlike Eufy/Roborock there is **no `send_command` envelope** — the
service takes parameters directly, and (importantly) **applies one set
of settings to all selected rooms** rather than per-room.

```python
"dispatch": {
    "template": "dreame_room_clean",
    "service_domain": "dreame_vacuum",
    "service_name": "vacuum_clean_segment",
    # No "command" key → direct service envelope.
    "map_id_field": "map_id",
    "map_id_type": "str",
    "room_id_field": "segment_id",
    "clean_passes_field": "repeats",
    "rooms_field": "segments",
    "room_fields": {
        "fan_speed": {
            "field_name": "suction_level",
            "value_map": {"Quiet": 0, "Standard": 1, "Boost": 2, "Max": 3},
        },
        "water_level": {
            "field_name": "water_volume",
            "value_map": {"Low": 1, "Medium": 2, "High": 3},
        },
        # Dreame doesn't have these as per-room settings.
        "clean_mode":      {"field_name": None},
        "clean_intensity": {"field_name": None},
        "edge_mopping":    {"field_name": None},
        "path_type":       {"field_name": None},
    },
},
```

> **Known framework limitation for Dreame.** The Dreame service
> signature applies one `suction_level`, one `water_volume`, and one
> `repeats` value to the entire call — not per-room. The framework's
> current per-room payload shape doesn't elegantly match this.
> Practical options today:
>
> 1. **Pick the first room's settings** and accept that all rooms in
>    one dispatch get the same suction/water — fine if you tend to
>    queue rooms with similar profiles.
> 2. **Split into multiple dispatches** — one per distinct settings
>    profile — at the cost of multiple back-to-back service calls.
> 3. **Extend the framework** with a flat-list mode that emits a
>    single dict with parallel lists. A future schema knob like
>    `dispatch.uniform_settings: true` would be the right place.
>
> Option 1 is the cheapest path to a working Dreame port today.
> Options 2 and 3 are improvements that benefit upstream contributors.

### 3.4 Narwal

**Upstream integration:** Narwal has **no first-party HA integration**.
Several community integrations exist (covering the Freo / Freo X
Ultra) with different service signatures, and the picture changes as
new ones land. The example below is a **skeleton** showing what you'd
fill in once you've identified your installed integration — not a
verified working config.

Before writing the dispatch block, answer these questions about your
installed Narwal integration:

1. What is the service domain and service name for "clean specific
   rooms"? (Check `Developer Tools → Services` in HA.)
2. Does it use a `vacuum.send_command` + `command` envelope, or its
   own direct service?
3. Does it accept per-room settings, or uniform settings (like
   Dreame)?
4. What field name carries the room ID list? Is the list of dicts or
   flat ints?
5. What field names and value vocabularies are used for suction power
   and water level (if exposed)?

A skeleton answering those questions for a hypothetical direct-service
Narwal integration:

```python
"dispatch": {
    "template": "generic_room_ids",
    "service_domain": "narwal_freo",       # ← your integration's domain
    "service_name": "clean_segments",      # ← your integration's service
    # No "command" → direct envelope (typical for community integrations)
    "map_id_field": "map_id",
    "map_id_type": "str",
    "room_id_field": "segment_id",
    "clean_passes_field": None,            # ← null if not supported
    "rooms_field": "segments",
    "room_fields": {
        "fan_speed":       {"field_name": "suction", "value_map": {...}},
        # Most other canonical fields are likely None — Narwal exposes
        # fewer per-room settings than Eufy.
        "water_level":     {"field_name": None},
        "clean_mode":      {"field_name": None},
        "clean_intensity": {"field_name": None},
        "edge_mopping":    {"field_name": None},
        "path_type":       {"field_name": None},
    },
},
```

If your installed integration uses `vacuum.send_command` with a brand
command string, use the Roborock example (§3.2) as the structural
template instead.

The honest summary for Narwal: this is the brand most likely to need
**both** an adapter config *and* one or two upstream contributions
(maybe a new dispatch template, possibly the uniform-settings flag
discussed in §3.3). Start with the skeleton above, verify against your
installed integration, and file a framework issue if you hit a wall
the schema can't express.

---

## 4. Lifecycle vocabulary mapping

The framework operates on a canonical set of lifecycle states —
`mid_job_service`, `active_job_running`, `vacuum_busy`, `dock_drying`,
`ready` — that are independent of any brand's firmware strings. The
adapter is responsible for mapping each brand's raw `task_status` and
`dock_status` strings to the right canonical state.

This mapping is the `vocabulary` block in the adapter config — see
[adapter-config-reference.md §6](../dev/adapter-config-reference.md#6-vocabulary--raw-and-normalized-state-strings).

### Recommended: capture a real clean cycle with the timeline card

The hardest part of a port is **knowing what raw strings your brand
actually emits**. Firmware docs are usually incomplete or wrong;
substring-matching what *looks* right will produce silent
miscategorisations that surface days later as broken finalization or
phantom-running jobs. The reliable approach is to record a clean
cycle end-to-end and read the transitions off the trace.

The [`ha-state-timeline-card`](https://github.com/kingchddg901/ha-state-timeline-card)
was built specifically to support this kind of state-flow analysis —
it's a state *parser* rather than a history *viewer*, which is the
angle no other HA recorder UI takes. That's why it's the recommended
tool for porting vocabulary work, not a generic suggestion. Add it to
your dashboard, point it at the sensors that matter for your brand
(`vacuum.<your_vacuum>`, `sensor.<your_vacuum>_task_status`,
`sensor.<your_vacuum>_dock_status`,
`binary_sensor.<your_vacuum>_charging`, and any others the
integration exposes), then run a full job — start → cleaning →
returning → docked → wash/dry/empty service cycles → idle. The card
steps through HA's recorder and shows the exact string each sensor
held at each moment, side by side.

What to extract from the trace into the `vocabulary` block:

| Adapter config field | What to look for in the trace |
|----------------------|-------------------------------|
| `active_run_task_states` | Every distinct `task_status` value during the cleaning-and-returning portion of the run (typically: `Cleaning`, `Returning`, `Going to Wash Mop`, etc.). Add all of them. |
| `hard_service_states` | `dock_status` values during post-job dock activity that should *block* a new job start — recycling waste water, mid-wash, mid-empty. |
| `drying_states` | `dock_status` value during the dry cycle — typically blocks-with-warning, not hard-block. |
| `blocked_work_mode_states`, `blocked_task_status_states`, `blocked_dock_status_states` | The **raw** title-cased values (not lowercased) of states that should prevent a new job from starting. |
| `cancel_service_exclusion_states` | Transient `task_status` values that appear during normal mid-job services (low-battery return, mop wash, dust empty) — needed so the cancel detector doesn't misread these as a manual cancel. |
| `not_error_sentinels` | What `error_message` reads when there's no error. Often `""`, `"unknown"`, `"unavailable"`, sometimes a brand-specific `"No error"`. |
| `water_level_aliases`, `wash_frequency_mode_aliases` | The user-visible strings for each select option; map them to canonical keys (`low`/`medium`/`high`, `by_time`/`by_area`/`after_each_clean`). |

Also worth recording with the timeline card while you're there:

- **The completion signature.** What `task_status` value and which
  secondary sensor clears together at the moment of completion?
  That's `completion.task_status_value` plus
  `completion.secondary_clear_entity` and `secondary_clear_sentinels`.
- **The dock-event triggers.** Which `dock_status` values fire
  precisely once per wash cycle, dust empty, and dry-start? Those go
  into `dock_events.triggers`.
- **The post-job wash sequence.** Does the dock wash the mop *after*
  the robot docks (Eufy X10 pattern), and if so, what is the
  multi-state sequence and the final `commit_state`? Those drive
  `post_job_wash_amendment.trigger_states` and `commit_state`.

Spend an hour with the timeline card and you'll have 80% of the
vocabulary block filled in from observed reality rather than guessed
from docs.

### Dropdown vocabulary (don't forget the four option lists)

Beyond the state-string sets, the adapter's `vocabulary` block also
declares **four user-facing dropdown option lists** the card consumes
to populate the room editor and rule editor:

- `clean_mode_options` — valid clean modes (`vacuum` / `mop` /
  `vacuum_mop` for most brands)
- `fan_speed_options` — valid fan speed values for this brand
- `water_level_options` — valid water levels (mop-capable models only)
- `clean_intensity_options` — valid intensity values (omit entirely
  for brands without this concept; the card hides the picker)

Each entry is `{"value": "...", "label": "..."}` — the `value` is what
gets written to room records and dispatch payloads (the canonical
framework value), the `label` is what the user sees in the dropdown.
A Roborock adapter that declares a 5th fan-speed entry with Max+ gets
a 5-chip fan-speed picker automatically; a Dreame port that omits
`clean_intensity_options` hides the intensity row.

See [adapter-config-reference.md §6](../dev/adapter-config-reference.md#6-vocabulary--raw-and-normalized-state-strings)
for the full schema and worked examples. **Without these, the room
editor's dropdowns will be empty for your brand.**

For example, Eufy's `task_status` "Returning to Charge" maps to the
canonical `returning` HA standard state plus a low-battery semantic
gate handled in code; Eufy's `dock_status` "Recycling waste water"
maps to the `hard_service_states` set so the framework blocks new job
starts until it clears.

The four common brands' vocabulary differences:

| Concept | Eufy | Roborock | Dreame | Narwal |
|---------|------|----------|--------|--------|
| "Vacuum is running" task_status | `cleaning` | `cleaning` | `cleaning` | varies |
| "Returning home" task_status | `returning` | `returning to dock` | `returning home` | varies |
| Mop wash dock state | `Washing` | (often N/A on dock-equipped) | `Washing` | varies |
| Self-empty dock state | `Emptying dust` | `Emptying dust` | `Emptying dustbin` | varies |
| Drying dock state | `Drying` | (rare on Roborock) | `Drying` | varies |

The `vocabulary` block doesn't define mappings; it defines **sets** of
raw strings the framework matches against — what's blocking, what's
drying, what's a service event. The canonical state assignment is
implicit in which set the string lives in.

---

## 5. Capability declarations

The framework gates optional payload fields on per-vacuum capability
flags. Set these in the adapter config's `capabilities` block based on
known hardware support; the framework also probes entity presence as a
fallback. See
[adapter-config-reference.md §14](../dev/adapter-config-reference.md#14-capabilities--explicit-capability-flags).

For a port, the practical decisions:

| Flag | When to set `True` |
|------|--------------------|
| `supports_mop_features` | Robot has an attached mop pad (most modern hybrid vacuums) |
| `supports_water_control` | Robot exposes per-room water level (Eufy, Roborock S7+, Dreame L10s+) |
| `supports_path_control` | Robot exposes path_type / "deep" / "fast" mode (Eufy X-series) |
| `supports_edge_mopping` | Robot has an edge-extending mop (Eufy X10+, Roborock S8 Pro+) |
| `supports_mop_wash` | Dock washes the mop pad (X10 dock, Roborock G20S, Dreame L10s Pro Ultra) |
| `supports_mop_dry` | Dock dries the mop pad with hot air |
| `supports_empty_dust` | Dock auto-empties the dustbin |
| `supports_robot_position` | Integration exposes `robot_position_x`/`robot_position_y` raw coords |
| `supports_station_water` | Dock has a clean-water tank exposed via a percentage sensor |

`supports_passes` defaults to `True`; set to `False` if your brand
doesn't accept per-room repeat counts (Dreame uniformly applies one
`repeats` to the whole call — but `supports_passes=True` still works,
the framework just sends the same value for every room).

---

## 6. Maintenance components and upkeep guides

If you want the maintenance/upkeep view to work for your brand, fill
in the `maintenance_components` and `upkeep_catalog` blocks of the
adapter config. Both are pure data — see
[adapter-config-reference.md §§15-16](../dev/adapter-config-reference.md#15-maintenance_components--replacement-counter-catalog).

This is verbose to author by hand. The pragmatic order:

1. Get a minimal port working first — leave `maintenance_components`
   and `upkeep_catalog` absent. The maintenance view will be empty;
   nothing breaks.
2. Add `maintenance_components` once you've identified the brand's
   replacement counter sensors. The framework reads these to show
   "X% remaining" on each component.
3. Add `upkeep_catalog` last. This is the per-component guide text
   shown when the user expands a component — pure display copy. You
   can crib most of it from your brand's user manual.

---

## 7. Water model configs

If you want the water-usage estimator to track actual tank-level
deltas (not just flow-rate-based estimates), fill in
`water_model_configs` with **measured** values per model. See
[adapter-config-reference.md §17](../dev/adapter-config-reference.md#17-water_model_configs--per-model-tank-measurements).

This is optional. Without it, the estimator falls back to flow-rate
estimates only — the rest of the learning system still works.

---

## 8. Testing your port

### Smoke test (no live dispatch)

The framework exposes payload-building entry points that don't fire a
real service call. Add a debug service to your port that calls:

```python
runtime_manager.get_payload_state(
    vacuum_entity_id="vacuum.your_vacuum",
    map_id="1",
)
```

…and dumps the result. The `payload` key is exactly what would be
sent to your integration's clean service. Inspect it for:

- Correct outer wrapper field names (your integration's `segments`/
  `rooms`/`map_id` etc.)
- Correct per-room field renames (`fan_power` not `fan_speed` for
  Roborock, etc.)
- Correct value translations (integer codes for Roborock, level
  enums for Dreame)
- Absent fields where you set `field_name: None`

### Dry-run dispatch

Once the payload looks right, manually invoke the integration's
service via HA Developer Tools with the payload you just inspected.
This isolates "is my dispatch config right?" from "does the framework
build the right dict?".

### Live test

Last: kick off a real room-clean job through the framework. If the
vacuum starts cleaning the right rooms, the port is functionally
complete. Verify lifecycle progression (cleaning → returning →
docked → completed) by watching the manager's lifecycle sensors —
that's where vocabulary-mapping errors will surface.

The cleanest way to debug a misbehaving port is to keep the
[`ha-state-timeline-card`](https://github.com/kingchddg901/ha-state-timeline-card)
open in another panel during the live test. When the framework's
lifecycle sensor disagrees with what the brand's sensors are
showing, the timeline shows you exactly which raw string the
adapter's vocabulary failed to classify and at what moment. That
turns a "the port isn't quite right" debug session into a "add
`'recycling clean water'` to `hard_service_states`" fix.

---

## 9. What still might require framework work

Cases where the schema can't yet express what you need:

- **Uniform-settings dispatch** (Dreame-style). The per-room shape is
  hardcoded today. A schema knob like `dispatch.uniform_settings: true`
  with a "pick representative room" strategy would close this.
- **A new dispatch template** beyond the four enum values. The
  `template` field is informational today — `build_room_clean_payload`
  reads the explicit field-name knobs, not the template — so a new
  value mostly just changes documentation, but if your brand needs a
  *structurally* different payload shape (e.g. nested arrays instead
  of dicts), the function itself needs extending.
- **New canonical fields** beyond fan_speed/clean_mode/clean_intensity/
  water_level/edge_mopping/path_type. The `room_fields` rename map is
  bounded by the canonical set. If your brand exposes a per-room
  feature outside this list (e.g. a per-room mop pressure setting),
  it needs a framework PR.
- **Brand-specific service envelopes** beyond the wrap-vs-direct
  switch in `core/manager.py:async_start_room_clean_job`. If your
  integration wants e.g. `entity_id` nested inside `params`, that's
  a third envelope shape the dispatcher would need.
- **The card-level setup services** (`setup_get_status`,
  `setup_add_vacuum`, `setup_import_active_map`, `setup_get_map_rooms`,
  `setup_save_rooms`, `setup_delete_map`) live in `services.py` and
  drive the current onboarding card flow. They assume the Eufy
  integration's single-brand discovery pattern. Multi-brand support
  will need a parallel set of services (or a generalisation of these)
  that work against the adapter config rather than hardcoded entity
  patterns. See `docs/advanced/03-services.md` for the current
  signatures.

> **TODO — map image capture workflow.** The current user-facing
> setup guide describes capturing a map image from the Eufy app's
> floor-plan view as a PNG/screenshot upload. That workflow is
> Eufy-specific — Roborock's app exports map images differently,
> Dreame typically provides a built-in floor-plan export, Narwal's
> apps vary. Each brand port will need its own short capture-and-
> upload guide written by someone who actually has the hardware.
> This is a documentation gap, not a code one: the
> `save_map_image` / `upload_map_image` services accept any PNG and
> don't care about the source. See [mapping-system.md §2 + §11](../dev/mapping-system.md)
> for what happens once the image is in.

> **Image segmentation is now pluggable.** Earlier drafts of this
> guide flagged Eufy-biased segmentation as a hard porting problem.
> The framework's response is a pluggable engine seam in
> `mapping/segmenter_engines.py` — see
> [mapping-system.md §2.0](../dev/mapping-system.md#20-the-segmenter-engine-seam)
> for the full protocol. Adapters declare which engine they want via
> `adapter_config["mapping"]["segmenter_engine"]`; the framework
> dispatches uniformly and consumes the canonical `SegmentationResult`
> regardless of which engine produced it.
>
> Three strategies, pick whichever matches your brand:
>   1. **Fork `EufyCVSegmenter`** — register a new engine that runs
>      the same Pillow/NumPy/SciPy pipeline with parameters tuned
>      for the new brand's image style. Most relevant for brands
>      that ship flat PNG floor plans (Dreame, Narwal). The tunable
>      surface is `min_area_pixels`, `simplify_epsilon`, the HSV
>      mask thresholds, and the assist-variant alignment scoring.
>   2. **`noop_fallback`** — declare it as the adapter's
>      `segmenter_engine` if your vendor provides no usable map
>      image. The card stops rendering polygonal overlays; trace-
>      based room bounds keep working off vacuum-space coordinates
>      (see [mapping-system.md §3](../dev/mapping-system.md#3-room-bounds-from-traces)).
>      This is the safe degradation path — core automations, queue,
>      job lifecycle, and room presence detection are unaffected.
>   3. **A deterministic engine** — for vendors that stream structured
>      polygon data over the wire (Roborock's map protocol is the
>      canonical example), implement a new engine that reads
>      `context["wire_payload"]` and translates it into the canonical
>      `SegmentationResult` shape directly. `matched_room_id` comes
>      straight from the wire — no fuzzy image matching. A
>      `roborock_deterministic` slot is reserved in the registry for
>      when there's a Roborock adapter to drive it.
>
> Adding a new engine is one new class + one registry entry. The
> framework's two consumer call sites (`get_image_segment_suggestions`
> in `manager.py`, `_handle_analyze_map_image` in `mapping_services.py`)
> change nothing. See
> [mapping-system.md §2.0b](../dev/mapping-system.md#20b-adding-a-new-engine)
> for the recipe.

None of these are blocking for the four common brands at runtime —
existing setup_* services are still functional for Eufy installs.
Open an issue if you hit one — the fixes are isolated and small.

---

## 10. HA standard service contract

The framework assumes the upstream vacuum integration honors the
[HA vacuum platform service contract](https://www.home-assistant.io/integrations/vacuum/) —
specifically: `vacuum.pause`, `vacuum.start`, and `vacuum.return_to_base`
must work on the vacuum entity. The framework calls these directly for
pause/resume/cancel operations, independent of the adapter config's
`dispatch` block.

If your integration exposes a vacuum entity that responds to these
standard services, everything else is brand-agnostic and adapter-
config-driven. If it doesn't (rare for modern integrations), pause
and cancel operations will fail — file an upstream issue against the
integration rather than working around it in the adapter.

---

## 11. Where to put your adapter

The Eufy adapter lives at `custom_components/eufy_vacuum/adapters/eufy/`.
A new brand follows the same pattern:

```
adapters/
  eufy/              ← existing reference
  roborock/          ← your port
    __init__.py
    adapter.py       ← register_<brand>_adapter_for_vacuum()
    const.py         ← ADAPTER_ID, STORAGE_KEY
    constants.py     ← hardware measurements (water tank ml, etc.)
    entities.py      ← entity ID build helpers
    vocabulary.py    ← raw and normalized state string sets
    maintenance_components.py  ← optional, for upkeep
    upkeep_catalog.py          ← optional, for upkeep
    upkeep_guides.py           ← optional, for upkeep
    water_config.py            ← optional, for water estimation
    model_catalog.py           ← optional, for model-family detection
```

Then wire it into `__init__.py`'s setup flow alongside (or replacing)
`register_eufy_adapter_for_vacuum()`. For an integration that should
serve multiple brands, register all relevant adapters and let each
adapter decide whether it applies to a given vacuum entity by
inspecting the entity's `detected_model` attribute or domain.
