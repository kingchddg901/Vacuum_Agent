# 29 — The Roborock Adapter — The Second-Brand Proof

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
| `const.py` | Identity strings (`DOMAIN`, `NAME`, `SUPPORTED_TESTED_MODEL`), the brand-level `ADAPTER_ID`, and `LOW_BATTERY_THRESHOLD_PERCENT`. |
| `entities.py` | `build_entity_id()` + the Roborock-core entity suffixes (`_status`, `_current_room`, `_cleaning_time`, …). |
| `vocabulary.py` | Task-status / error / completion state sets + the fan-speed `*_options` (card vocab) and the per-room-live fan `options_key` vocabulary guard. A brand may also declare display→canonical alias maps (`clean_mode_aliases` / `clean_intensity_aliases` / `fan_speed_aliases`) so the learning manager hands the card a canonical code for observed settings; the S6's values already slug to canonical (`gentle`/`balanced`/…), so it declares none. |
| `model_catalog.py` | `profile_for_model()` — maps `roborock.vacuum.s6` → the s6 **capability profile** (a dict: `family`/`display_name`/`has_dock`/`has_mop`/`supports_segments`), not a family string like Eufy's `detect_model_family()`. |
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
`_current_room`, `_cleaning_time`, `_cleaning_area`, `binary_sensor.
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
- **Base Station and Map Bounds card tabs are hidden — but *not* via literal
  capability flags.** The S6 declares neither `supports_base_station` nor
  `supports_map_bounds` in its `capabilities` block; both card signals are
  *derived at snapshot time* in `core/manager.py::get_dashboard_snapshot`
  (lines 3648-3661). (a) `supports_base_station` resolves False because the
  adapter omits the `dock_events` block entirely and all of
  `supports_mop_wash` / `supports_mop_dry` / `supports_empty_dust` /
  `supports_station_water` are False. (b) `supports_map_bounds` resolves False
  because the adapter declares `mapping.segmenter_engine: "noop_fallback"` and
  the derivation is `bool(segmenter_engine and segmenter_engine != "noop_fallback")`.
  Both default to **shown** when the snapshot key is absent; only an adapter that
  resolves False hides the tab. Eufy shows both because its dock/station caps are
  True (X10 dock) and its `segmenter_engine` is a real CV engine (`eufy_cv_v1`).
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
  a **global** scalar on the run (the S6 can't vary passes per room). Because the S6
  has no provider fan-speed `select` (its fan power is the standard vacuum entity's
  `fan_speed` / `fan_speed_list`), the card's zone/clean **Settings** panel renders a
  **fallback suction row** backed by `vacuum.set_fan_speed` (renderer
  `_renderVacuumFanSpeedRow`, action `setVacuumFanSpeed`), shown only when no fan-speed
  `select` exists — so Eufy is unchanged. A zone clean runs at the device's CURRENT fan
  power (`app_zoned_clean` carries no fan field), the same "runs off current device
  settings" model as the Eufy select rows.
- **`phase_timing`** — the strict-order watchdog's settle/verify/confirm/poll
  seconds + retry cap, S6-tuned and **adapter-declared**. Core falls back to its own
  `_PHASE_*` defaults for any omitted key, and most S6 values match those defaults
  (settle 10, dock_settle 45, verify 90, poll 5, max 3) — but the S6 deliberately
  overrides `confirm_seconds` to **15**, well below the core default of 45, so a
  confirmed room releases the guard fast. A brand whose post-dock transient differs
  declares its own. See [22 §dispatch](22-adapter-config-reference.md).
- **`live_room_refresh`** (Lever B) — the S6's live `_current_room` + per-room fan
  ride the upstream coordinator's **map** cadence (`IMAGE_CACHE_INTERVAL` ~30 s), not
  the ~15 s status poll. During a **contiguous** run this block has the framework pulse
  `roborock.get_vacuum_current_position` (a `returns_response` service whose
  `map_content.refresh()` side effect runs off the 30 s gate) every `interval_s` (15)
  so the native rollover + per-room fan track at ~15 s. It is **LAN-gated** (`local_gate`
  keys off the *absence* of the upstream `cloud_api_used` repair issue — cloud ⇒ skip,
  re-checked each pulse) and **excluded for strict-order/phased runs** (each per-room
  dock already forces a free refresh). Eufy omits this block (it has a ~2 s eufy-clean pose) →
  no-op. Owner: `live_refresh/LiveRoomRefreshManager` (core delegates via
  `maybe_pulse_live_room_refresh`).

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
[11-mapping-system](11-mapping-system.md) and [frontend/architecture-overview](frontend/architecture-overview.md).

### `map_render` — re-decode the raw segment layer to a room raster
`mapping` above gives the card a *backdrop*; `map_render` gives it a **per-pixel
room-id raster** so Roborock rides the **same** raster render pipeline as Eufy —
per-room colour, floor textures, pixel-exact hit-test — instead of the overlapping
bounding boxes the parser exposes. The adapter declares `map_render.format:
"roborock_raw_map_v1"` (Eufy declares `eufy_room_pixels_v1`; those are the only two).

**Why re-decode.** `vacuum-map-parser-roborock` reads the raw blob's pixel layer to
colour the rooms, then **discards it** — the public `MapData` keeps only per-room
bboxes + a rendered RGB image. But the raw bytes survive on the v1
`MapContent.raw_api_response` (cached in HA memory, next to the `MapData` the
`map_state_source` `memory` backend already reaches). `mapping/roborock_raw_map.py`
re-decodes **just the segment layer** into a room-id raster equivalent to Eufy's
`room_pixels`, and `roborock_render_data()` wraps it in the **generic
`eufy_room_pixels_v1` render-data shape** — so the card decode is unchanged
(brand-agnostic); only the source path differs. `rid_shift` is 0 (ids already
resolved) and the raster IS the canvas (no separate outline frame → `ro_*` = the
canvas, `ro_dx/dy` = 0). See
[31 §3.4](31-map-source-coordinator.md#34-async_get_map_render_data) and
[frontend/floor-texture-map-view](frontend/floor-texture-map-view.md).

**v1 only** (S6 / Q-series-class). The byte walk is mirrored verbatim from the
reference parser (little-endian; header/block walk; IMAGE block `type == 2`; pixel
byte → `(type = byte & 0x07, room = byte >> 3)`, a room iff `type == 7` and the byte
is not `0x07`/`0xFF`; `0xFF` = the catch-all scanned floor, id 31; raw row 0 is the
image BOTTOM → `flip_y` True) so a firmware format change is a one-file fix. b01
(newer Qrevo-class) uses a different parser and is out of scope.

**Drift-check (`geometry_drift`).** The raw raster and the parser's own per-room
bboxes come from the **same** segment layer, so overlaying them validates the decode:
`raster_room_bboxes()` derives bboxes from the raster and `geometry_drift()` compares
them to the parser's (per-room IoU + centre delta + a soft `aligned` verdict). Aligned
boxes confirm rid-extraction + orientation + frame; a systematic delta IS a
calibration signal — a constant offset is the parser's trim, an **inverted axis is a
flip bug** (why `flip_y` matters: get it wrong and the two sit a whole Y-flip apart and
never overlap). The room raster is self-contained, but the **pose overlay's** coord
registration (`res` / origin / flip vs the live robot position) still needs calibrating
on a real device.

**Surfaced in diagnostics.** This drift-check runs automatically: for any
`map_state_source.backend == "memory"` (Roborock) vacuum, the config-entry diagnostics
download (`diagnostics.py` → `map_source_runtime.roborock_geometry_drift_from_candidates(...)`)
attaches a `roborock_geometry_drift` block — `{present: True, room_ids_parser/raster, common,
only_parser/raster, max_center_delta, min_iou, aligned, per_room{rid: {parser, raster,
center_delta, iou}}}` on a decodable device, or `{present: False, reason: "no_geometry"}`
otherwise (best-effort, never raises). So **Settings → Devices & Services → Vacuum Agent → ⋮ →
Download diagnostics** on a real run reports `aligned` (decode correct on this device) or the
per-room deltas (the pose/coord calibration signal) with no manual call.

**`self_check` reads native brands honestly.** The dump's interpreted summary (`_self_check`
in `diagnostics.py`, surfaced as the `self_check` block) is brand-agnostic. It reads the
adapter brand from `out["adapter"].brand`, then distinguishes three worlds instead of assuming
the Eufy transport: **Eufy full** (an `active_map` sensor), **Eufy reduced/scalar** (the
`segments` attribute), and **native integration** (rooms present with *neither* — e.g.
Roborock, whose rooms come from its own HA integration via `managed_rooms_by_map` / `maps`
room_count). Room availability keys off `supports_room_clean` (the true per-room capability),
not `supports_rooms` (the Eufy-shaped flag); map availability recognises a decoded raster via
`roborock_geometry_drift.present`. So a working Ivy reports `transport: native integration
(roborock)`, room control available, and map decoded — instead of the old Eufy-shaped
"unknown / unavailable / no". Diagnostics-only, data-driven, never raises. Pinned by
`[DIAG-9]`/`[DIAG-10]` in `tests/integration/test_diagnostics.py`.

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
  > **Per-phase recording (shipped):** because the per-room dock trips break the
  > whole-run transit segmenter, each phase is segmented **alone**: at phase
  > completion `PhaseRunner.maybe_advance_phase` calls `_capture_finishing_phase_timing`
  > (`jobs/phase_runner.py`), which snapshots the finishing phase's own
  > `room_timing` (cleaning-time rise + `cleaning_area` delta, with the room's learned
  > area as a fallback) onto `job["phases"][idx]` before the queue/timing resets.
  > Finalization then reconstructs per-phase `room_timings` from
  > `active_job["phases"][].room_timing` (`learning/history_store.py`), and only marks
  > the run valid (`transit_capture_valid`) when **every** phase captured. A multi-room
  > strict-order run is no longer mis-attributed to the last phase's room; a phase that
  > never cleaned records an empty timing so the run reads as not-fully-captured rather
  > than a phantom room.
- **Native current-room live rollover** — driven by `live_transition.
  native_transition_source` (§4), suppressed for sequenced jobs so a parked dock
  room is never phantom-completed.
- **Live-room refresh during a contiguous run (Lever B)** — driven by
  `dispatch.live_room_refresh` (§4): a ~15 s pulse of
  `roborock.get_vacuum_current_position` that refreshes the live room + per-room fan
  off the 30 s map gate, LAN-gated and excluded for phased (strict-order) runs. Owned
  by `live_refresh/LiveRoomRefreshManager` (core delegator
  `maybe_pulse_live_room_refresh`); Eufy is inert here.
- **Live-map card backdrop + rotation + dwell-follow mascot** — the live `image`
  entity as the Map view, backend-stored rotation, and a dwell-debounced mascot
  that follows the reported room. See [frontend/architecture-overview](frontend/architecture-overview.md).
- **Order-advisory note** — `honors_clean_order: False` surfaces a run-start note
  that order is advisory unless a Sequence is set in the app (or strict-order is on).
- **Ad-hoc zone clean (draw-a-box) over the rendered map** — the S6 declares
  `capabilities.supports_zone_clean: True` + `dispatch.zone_command: "app_zoned_clean"`
  (world-mm quads via stock `send_command`), so the card's **Draw a zone** control
  appears once the VA-render raster (`▦`) is the backdrop — the raster is the frame the
  brand-agnostic normalized→device conversion inverts, backstopped by a round-trip
  refuse-gate. Roborock caps: `zone_max: 5` zones, `zone_max_area_m2: 3.05` (~32.8 ft²)
  each; Eufy allows 10. See [saved-zones](frontend/saved-zones.md) for the persisted-zone
  layer on top of this, and [04 — running a clean](../user-guide/04-running-a-clean.md#zone-cleaning-draw-a-box).

---

## 6. What the S6 can't do (honest boundary)

The adapter declares these so the UI never offers a control the firmware ignores:

- **Mop is unsettable** — observe-only via a water-box sensor;
  `SET_WATER_BOX_CUSTOM_MODE` / `SET_MOP_MODE` raise `RoborockUnsupportedFeature`
  on the S6. The room editor hides mop controls for the S6.
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
