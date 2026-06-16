# The Roborock Adapter — The Second-Brand Proof

> **Scope:** A field-by-field walkthrough of the second shipping adapter,
> `adapters/roborock/`, written as the **foil to Eufy**. Where
> [25-eufy-adapter](25-eufy-adapter.md) shows what a full-feature adapter looks
> like, this doc shows what changes when the brand is fundamentally different:
> native maps instead of a CV image, a path-optimizing firmware that ignores
> dispatched order, segment ids that renumber on a re-map, and a "current room"
> the device reports directly.
>
> Read [21-adapter-system](21-adapter-system.md) for the registry/loader
> mechanics and [22-adapter-config-reference](22-adapter-config-reference.md) for
> the authoritative per-field schema. This doc is the *example*; those are the
> *contract*. The step-by-step porting workflow is the
> [porting guide](../contributing/porting-guide.md).

---

## 1. Why Roborock is the useful second example

Eufy proves the schema is *expressive*. Roborock proves the boundary is *real*:
the framework reads exactly the same config blocks, but almost every value is
different, and several blocks exercise seams Eufy never touches. It runs on top
of the HA **`roborock` core integration** (not robovac_mqtt), so:

| Dimension | Eufy | Roborock (S6) |
|---|---|---|
| Room discovery | `segments` attribute on the vacuum entity | `roborock.get_maps` **service call** |
| Segment ids | stable | **renumber on every re-map** → must re-resolve by name slug at dispatch |
| Dispatch | `room_clean`, bare dict payload | `app_segment_clean`, **list-wrapped** params |
| Clean order | honored | **ignored** (path-optimized) → opt-in strict-order sequencing |
| Current room | none (counters only) | **native** `_current_room` sensor → live rollover |
| Map image | CV segmenter over a static image | **live `image` entity** from core → card backdrop |
| Mop / passes | per-room settable | **mop unsettable; passes global** (firmware) |

The brand is **auto-detected** per vacuum in `__init__.py` (manufacturer
`Roborock` / model prefix `roborock.`); an explicit UI brand selector is a
follow-up. `adapter_id = "roborock"` is **brand-level** — per-model differences
(the S6 is the first profile) are capability-gated at registration from
`device.model` + live entity presence + `model_catalog`, exactly the Eufy
technique. `DOMAIN` stays `eufy_vacuum`: Roborock runs inside the same
integration, it is not a fork.

---

## 2. File layout

Same data/assembly split as Eufy (§2 there), but a **smaller surface** — the S6
has no CV map, no per-model water tanks, and no upkeep-guide library, so those
modules are simply absent (the blocks degrade gracefully).

| Module | Role |
|---|---|
| `adapter.py` | Assembly + `register_roborock_adapter_for_vacuum()`. Pure assembly, as in Eufy. |
| `const.py` | `ADAPTER_ID`, `STORAGE_KEY`. |
| `entities.py` | `build_entity_id()` + the Roborock-core entity suffixes (`_status`, `_current_room`, `_cleaning_time`, …). |
| `vocabulary.py` | Task-status / error / completion state sets + the fan-speed `*_options` (card vocab) and the per-room-live fan `options_key` vocabulary guard. |
| `model_catalog.py` | `detect_model_family()` — maps `roborock.vacuum.s6` → the `s6` profile. |
| `maintenance_components.py` | The 4 consumables (main/side brush, filter, sensor) as device-owned `*_time_left` countdowns. |

There is **no `segmentor.py`** (no CV pipeline — see `mapping` below), **no
`water_config.py`** (no dock water model), and **no `upkeep_*`** modules.

---

## 3. Assembly + auto-detection

`register_roborock_adapter_for_vacuum()` follows the same 7-step flow as Eufy
(§3 there): detect model → build entity candidates → capability hints → 
`detect_capabilities()` → assemble config → strip `None` → register. The one
addition is upstream of it: `__init__.py` picks Roborock vs Eufy per vacuum by
manufacturer/model before calling the brand's register function, so a mixed
household (a Eufy and a Roborock) wires each correctly with no user input.

---

## 4. Block by block — where Roborock diverges

Only the blocks that differ meaningfully from Eufy are called out; everything
else follows the Eufy pattern.

### `entities`
Roborock-core names are stable (`sensor.{object_id}_status`,
`_current_room`, `_cleaning_time`, `_total_cleaning_area`, `binary_sensor.
{object_id}_charging`, `binary_sensor.{object_id}_cleaning`). The two that drive
new framework behavior: **`active_cleaning_target` = `_current_room`** (a room
NAME the device reports live) and **`job_active` = `binary_sensor.{id}_cleaning`**
(the device's `inCleaning` flag — load-bearing for completion, below).

### `completion` — `require_job_active_clear`
`task_status_value: "charging"` (the S6 reports `charging` at the end of a run,
on the dock). But a **mid-job recharge** also hits `charging`, so the task value
alone is ambiguous. The disambiguator is `completion.require_job_active_clear:
True`: the completion gate additionally requires the `job_active` binary to have
cleared. The cleaning binary stays **ON** through a recharge dock and clears only
at the true finish (confirmed on an S6 trace: ON through a 19 % recharge + resume,
OFF only at completion). This is why `active_cleaning_target` can't be the
secondary signal the way it is for Eufy — Roborock's `_current_room` reverts to
the **dock room's name** when parked, never a clear sentinel. See
[06-job-lifecycle](06-job-lifecycle.md) for the gate.

### `capabilities` — the behavioral flags do the heavy lifting
Hardware flags come from `detect_capabilities()`; the **behavioral** flags are
literals describing firmware an entity probe can't see, and they gate real UI and
dispatch behavior:

- **`honors_clean_order: False`** — the S6 path-optimizes, so a dispatched
  room order is advisory. This flag (a) surfaces an "order is advisory" note at
  run start and (b) gates the opt-in **strict-order** sequencing (§5).
- **`supports_base_station: False` / `supports_map_bounds: False`** — hide the
  Base Station and Map Bounds card tabs (the S6 has neither). Eufy defaults both
  shown.
- **`supports_room_profiles: False`** — the S6 dropped per-room profile
  templates (mop/passes aren't per-room settable, below).
- **`position_lock_reliable: False`** — same as Eufy; reserved for a future
  stable-frame brand to flip True (re-enables the bounds-veto rollover gate).

### `dispatch` — `app_segment_clean`, renumbering ids, brand-tuned watchdog
`template: "roborock_segment_clean"`, `vacuum.send_command` with
`command: "app_segment_clean"`, `rooms_field: "segments"`,
`clean_passes_field: "repeat"`, and **`params_as_list: True`** (the wire payload
is `params=[{segments:[…], repeat:n}]`, a single-element list — Eufy passes the
bare dict). Roborock-specific keys with no Eufy equivalent:

- **`resolve_live_ids_by_slug: True`** — segment ids renumber on a re-map, so a
  stored id can clean the wrong room. Before each dispatch the framework fetches
  a fresh `get_maps`, maps each target room's name slug → current id, and rewrites
  the wire id list. Stored data is never touched; cleaning correctness is
  decoupled from the identity-reconciliation review.
- **`per_room_live_settings`** + **`passes_is_global: True`** — fan speed is set
  **per room, live** (`set_fan_speed` before each room's dispatch, guarded by an
  `options_key` vocabulary so an out-of-vocab value is skipped), while passes are
  a **global** scalar on the run (the S6 can't vary passes per room).
- **`phase_timing`** — the strict-order watchdog's settle/verify/confirm/poll
  seconds + retry cap, S6-tuned and **adapter-declared** (core keeps the same
  numbers as defaults; a brand whose post-dock transient differs declares its
  own). See [22 §dispatch](22-adapter-config-reference.md).

### `discovery` — `get_maps` + name-slug reconciliation
Rooms come from the `roborock.get_maps` **service** (`source: service_response`),
not an entity attribute. Because ids renumber, discovery feeds the
**name-slug identity reconciliation** in `rooms/reconciliation.py`: a room is
tracked by its name slug, settings/grants carry onto the new id, and the
reconciliation review surfaces ambiguous shifts. See
[08-rooms-system](08-rooms-system.md).

### `mapping` — no CV, a live image instead
There is **no CV segmenter** (`segmenter_engine` is the noop fallback — the S6
exposes no static map image to segment). Instead the Roborock core integration
publishes a **live map `image` entity**, and the adapter declares the entity-id
**pattern** `mapping.live_map_image_entity_pattern:
"image.{object_id}_{map_slug}"`. Core only `.format()`-fills the generic
`{object_id}` / `{map_slug}` placeholders and existence-checks the result, then
surfaces it in the dashboard snapshot as the card's Map-view backdrop. Room
polygons are hand-drawn over the live image via the custom-layout composer
(dispatch is by room id, so approximate polygons are fine). See
[11-mapping-system](11-mapping-system.md) and [19-card-architecture](19-card-architecture.md).

### `job_segmenter` — `noop_job_fallback`
The S6 reports native progress, so it registers `noop_job_fallback`, **not**
`eufy_counter_v1`: the Eufy counter-plateau heuristic would false-segment on the
S6's obstacle stalls. This is the one place Roborock deliberately opts out of the
historical default (see the Eufy doc's note that absent/unknown falls back to the
Eufy counter — Roborock declares the noop explicitly).

### `live_transition` — `native_transition_source: True`
Roborock is the brand that lights up the reserved `native_transition_source` flag.
Its `_current_room` sensor reports the live room directly, so the framework
follows that signal (filtered to the job's target rooms, matched by name slug,
order-agnostic) instead of Eufy's counter-plateau inference. See
[06-job-lifecycle](06-job-lifecycle.md).

### `setup`
`steps: [add_vacuum, import_active_map, save_rooms]` — `import_active_map` runs
the `get_maps` fetch (the S6 surfaces one map at a time). The Setup tab also
carries the add-another-vacuum control and the per-vacuum **panel rename**
(`setup_set_panel_title`), since a multi-vacuum household wants distinct sidebar
titles.

---

## 5. Framework features the Roborock adapter unlocked

These are not adapter config — they're **framework** capabilities the second
brand forced into existence, gated by Roborock's flags so Eufy is untouched:

- **Strict-order sequenced cleaning** — for `honors_clean_order: False` brands, an
  opt-in run-mode dispatches **one room per phase** (a sequenced job) so the queue
  order is enforced in-framework instead of being re-routed by the device. A
  per-phase watchdog (settle → dispatch → verify the device actually started THIS
  room → retry) handles the S6 ignoring a clean sent the instant it docks. See
  [06-job-lifecycle](06-job-lifecycle.md) / [07-queue-engine](07-queue-engine.md).
- **Native current-room live rollover** — driven by `live_transition.
  native_transition_source` (§4), suppressed for sequenced jobs so a parked dock
  room is never phantom-completed.
- **Live-map card backdrop + rotation + dwell-follow mascot** — the live `image`
  entity as the Map view, backend-stored rotation, and a dwell-debounced mascot
  that follows the reported room. See [19-card-architecture](19-card-architecture.md).
- **Order-advisory note** — `honors_clean_order: False` surfaces a run-start note
  that order is advisory unless a Sequence is set in the app (or strict-order is on).

---

## 6. What the S6 can't do (honest boundary)

The adapter declares these so the UI never offers a control the firmware ignores:

- **Mop is unsettable** — observe-only via a water-box sensor; `SET_WATER_BOX` /
  `MOP_MODE` raise `RoborockUnsupportedFeature`. The room editor hides mop
  controls for the S6.
- **Passes are global** (`passes_is_global`) — one passes value for the run, not
  per room.
- **No room profiles** (`supports_room_profiles: False`), **no Base Station / Map
  Bounds tabs** (capability-gated off).
- **Carpet + tank caution** — starting with the tank attached over carpet warrants
  a warning (`mop_carpet_warning`).

A future Roborock with a settable mop / per-room passes drops these flags and the
controls reappear — no core change.

---

## 7. Porting takeaway

Roborock is the proof that the litmus test in the Eufy doc (§7) holds: a brand
with **completely different** discovery, dispatch, ordering, and map behavior
needed **zero** brand special-cases in `core/`, `jobs/`, `dock/`, or
`onboarding/`. Every divergence above is a config value or an adapter-declared
pattern/threshold. Where the second brand needed genuinely new *framework*
behavior (strict order, native rollover, live map), that behavior is generic and
capability-gated — Eufy stays byte-identical. If your third brand needs something
none of these blocks express, add a block to the schema and a reader in core,
gate it, and document it here — don't special-case the brand.
