# Frontend ↔ Backend Contract & Data Shapes

This is the **seam doc**: what a UI **reads** from the backend (services, events, entities) and what it **writes** back (service calls). Everything in the Backend Contract below is what *any* UI — the shipped card, a React app, a native client, a CLI — must consume to drive a eufy_vacuum installation; "Building a different UI" then distills the minimum a non-card client needs. For the overall frontend map and how the layers fit together, start at the hub, [architecture-overview.md](architecture-overview.md).

The **render-DATA shapes** — the map segment set, `room_names`, the live pose, and the dashboard snapshot the card draws its backdrop and overlays from — are **not owned here**. They are sourced and normalised by the [map source coordinator](../31-map-source-coordinator.md) and defined in [map-state-source](../map-state-source.md); this doc only records how a UI *fetches* them (the `get_map_segments` / `get_map_render_data` / `get_map_live_pose` / `get_dashboard_snapshot` services). See [Render-data shapes](#render-data-shapes) at the end for the pointer stub.

---

## The Backend Contract

### HA Services

All services live in the `eufy_vacuum` domain. Call them via `hass.callService(domain, service, data, target?, notifyOnError?, returnResponse?)`. Services marked **response** must be called with `returnResponse = true`; the result lives at `result.response`.

#### State queries (read-only, response)

| Service | Required fields | What it returns |
|---|---|---|
| `get_start_status` | `vacuum_entity_id`, `map_id` | Pre-flight eligibility, blocking flags, preflight payload |
| `get_dashboard_snapshot` | `vacuum_entity_id`, `map_id` | Full card read model: job control, queue, room list, learning state |
| `get_dock_action_status` | `vacuum_entity_id`, `map_id` | Dock action availability (wash/dry/empty), active action flags |
| `get_pause_timeout_settings` | `vacuum_entity_id` | Configured pause-timeout duration |
| `get_lifecycle_state` | `vacuum_entity_id` | Raw lifecycle state dict |
| `get_job_progress_snapshot` | `vacuum_entity_id` | In-progress job room/timing snapshot |
| `get_job_control_state` | `vacuum_entity_id` | Active job + queue combined state |
| `get_upkeep_snapshot` | `vacuum_entity_id` | Maintenance intervals and remaining hours |
| `get_queue_state` | `vacuum_entity_id`, `map_id` | Raw queue content |
| `get_payload_state` | `vacuum_entity_id`, `map_id` | Raw room payload |
| `get_active_job` | `vacuum_entity_id` | Active job dict |
| `get_vacuum_capabilities` | `vacuum_entity_id` | Hardware capability flags (water level, edge mopping, etc.) |
| `get_vacuum_maps` | `vacuum_entity_id` | Registered maps for the vacuum |

#### Job control (side-effecting)

| Service | Required fields | Notes |
|---|---|---|
| `start_selected_rooms` | `vacuum_entity_id`, `map_id` | Optional: `confirm_reduced_run`, `confirm_token`. Do **not** call with `returnResponse = true` |
| `start_zone_clean` | `vacuum_entity_id`, `zones` | Optional: `clean_times` (1–10, default 1), `map_id`. Ad-hoc free-form zone clean — `zones` is a list of `[x0, y0, x1, y1]` rectangles as 0–1 fractions of the live-map image (top-left origin). Fire-and-forget: no room ids, no job/queue/learning tracking. Requires a provider with the `supports_zone_clean` capability |
| `pause_active_job` | `vacuum_entity_id` | |
| `resume_active_job` | `vacuum_entity_id` | |
| `cancel_active_job` | `vacuum_entity_id` | |
| `vacuum.return_to_base` | `entity_id` (HA vacuum entity) | Standard HA vacuum service — not in eufy_vacuum domain |
| `clear_queue` | `vacuum_entity_id` | Optional: `map_id` (defaults to active map). Clears the pending run queue without stopping a running job |
| `clear_active_job` | `vacuum_entity_id` | |

#### Room management

| Service | Required fields | Notes |
|---|---|---|
| `update_room_fields` | `vacuum_entity_id`, `map_id`, `room_id` | Optional: `enabled`, `clean_mode`, `fan_speed`, `clean_intensity`, `clean_passes`, `water_level`, `edge_mopping`, `is_transition`, `grants_access_to`, `is_dock_room`, `rules`. Omit null optional fields — HA schema rejects them |
| `discover_rooms` | `vacuum_entity_id` | Interrogates the vacuum for the current room list |
| `save_managed_rooms` | `vacuum_entity_id` | Persists discovered rooms into integration storage |
| `get_room_access_editor` | `vacuum_entity_id`, `map_id` | Returns room access graph for editing |
| `get_access_graph_health` | `vacuum_entity_id`, `map_id` | Validates access graph integrity |

Room enabled/disabled state is stored in HA **switch entities** (one per room per map per vacuum). Toggle by calling `homeassistant.turn_on` / `homeassistant.turn_off` with the switch entity ID. Room ordering is stored in HA **number entities** (one per room per map per vacuum). Update by calling `number.set_value`.

#### Saved zones (response)

Named, reusable clean regions ("the couch", "the stove") drawn as normalised polygons on a map. All live in the `eufy_vacuum` domain and are **response** services. The card's JS wrappers live in `src/actions/saved-zones.js`. See also the [saved-zones](saved-zones.md) doc.

| Service | Required fields | Notes |
|---|---|---|
| `create_saved_zone` | `vacuum_entity_id`, `map_id`, `name`, `geometry` | `geometry` = normalised 0–1 polygon, a list of `[x, y]` points (≥ 3). Optional: `kind`. Returns `{saved, zone_id, zone}` |
| `rename_saved_zone` | `vacuum_entity_id`, `map_id`, `zone_id`, `name` | Renames an existing zone |
| `delete_saved_zone` | `vacuum_entity_id`, `map_id`, `zone_id` | |
| `set_saved_zone_room` | `vacuum_entity_id`, `map_id`, `zone_id` | Optional: `room_number` (which room the zone is **filed** under; omit/null = Unassigned). Filing only — never affects what the zone cleans |
| `clean_saved_zone` | `vacuum_entity_id`, `map_id`, `zone_id` | Optional: `clean_times` (number of passes, min 1). Fires one saved zone as an ad-hoc, fire-and-forget zone clean; requires the zone's map to be the active map. Returns `{cleaned, reason?}` (reason ∈ `map_not_active` \| `zone_not_found` \| `bad_geometry`) |
| `clean_saved_zones` | `vacuum_entity_id`, `map_id`, `zone_ids` | Optional: `clean_times`. Fires the whole selected set as one ad-hoc, fire-and-forget zone clean. Per-brand caps enforced service-side (Eufy: up to 10 zones, each side 0.5–10 m; Roborock: up to 5 zones, 1 ft²–3.05 m² each). Returns `{cleaned, reason?, zone_count?}` (reason ∈ `map_not_active` \| `zone_not_found` \| `bad_geometry` \| `no_zones`). JS wrapper `cleanSavedZones` |

The map's saved-zone list is **not** a separate query — it rides on the **`get_map_segments`** response as `saved_zones` (a list of the map's saved zones); the card fetches it via `getSavedZones` off the same `get_map_segments` call.

#### Queue

| Service | Required fields |
|---|---|
| `build_queue` | `vacuum_entity_id`, `map_id` |
| `build_room_payload` | `vacuum_entity_id`, `map_id` |

##### Live-queue composer (stepped ad-hoc runs)

The card builds a stepped run *ad hoc* — charge/wait stops and saved-zone cleans
inserted into the current queue without saving a profile. These persist on the map
bucket as `queue_breaks` (`[{after_index, step}]`); `get_dashboard_snapshot` exposes
the interleaved result as `queue_steps` (steps + raw breaks). All are **response**
services in the `eufy_vacuum` domain; JS wrappers in `src/actions/rooms.js`.

| Service | Required fields | Notes |
|---|---|---|
| `add_queue_break` | `vacuum_entity_id`, `map_id`, `after_index` | Insert a `charge_wait` (`target_battery_percent`) or `wait` (`wait_minutes`) stop between room groups |
| `add_queue_zone` | `vacuum_entity_id`, `map_id`, `after_index`, `zone_ids` | Insert a saved-zone **clean** step (one phase over the selected zones). May sit at the tail (`after_index == room_count`); stops may not |
| `remove_queue_break` | `vacuum_entity_id`, `map_id`, `index` | Remove one step by its position in the break list |
| `set_queue_breaks` | `vacuum_entity_id`, `map_id`, `breaks` | Wholesale replace — the primitive behind reorder + inline param-edit; the backend clamps `after_index` and re-sorts |
| `clear_queue_breaks` | `vacuum_entity_id`, `map_id` | Drop all steps — the queue reverts to a flat clean |
| `get_queue_steps` | `vacuum_entity_id`, `map_id` | Returns the interleaved `steps` (rooms + breaks/zones in order) and the raw `breaks` |

A queue with breaks/zones dispatches as a stepped run on the normal Start; saving the
setup snapshots `get_queue_steps().steps` into a run profile. The **running** job's
monitor twin is `live_queue` (see [`get_job_progress_snapshot`](#state-queries-read-only-response) and [05-core-manager](../05-core-manager.md)). Backend contract: [07-queue-engine §9](../07-queue-engine.md#the-ad-hoc-live-queue-queue_breaks).

#### Learning system

| Service | Required fields | Notes |
|---|---|---|
| `run_learning_estimate` | `vacuum_entity_id`, `map_id`, `current_battery` | Optional: `started_at` (omit for pre-start calls). Returns time estimates per room |
| `reanchor_learning_timeline` | `original_estimate`, `completed_rooms`, `reanchor_at` | Optional: `current_battery`. Recomputes remaining ETAs mid-job |
| `get_next_room` | `reanchored_estimate` | Resolves which room is next from the reanchored estimate |
| `get_room_learning_estimates` | `vacuum_entity_id`, `map_id` | Per-room estimates independent of queue state |
| `get_learning_history_snapshot` | `vacuum_entity_id` | Optional: `room_slug`, `profile_key`, `status`, `used_for_learning`, `origin` (`external` \| `internal`), `limit`. Each recent-jobs entry carries the [run-record attribution fields](#run-record-attribution-fields) the Review card reads |
| `get_metrics_snapshot` | `vacuum_entity_id` | Optional: `room_slug`, `profile_key`, `status`, `used_for_learning` |
| `get_incomplete_run_log` | `vacuum_entity_id` | Last cancelled/failed/interrupted job. Returns null-equivalent `{}` when no log exists |
| `get_trouble_rooms_log` | `vacuum_entity_id` | Chronic trouble rooms. Returns null-equivalent `{}` when no log exists |
| `save_learning_snapshot` | `vacuum_entity_id` | |
| `finalize_learning_job` | `vacuum_entity_id` | Called when a job ends; triggers `eufy_vacuum_run_incomplete` event when rooms were missed |
| `rebuild_learning_stats` | `vacuum_entity_id` | |
| `exclude_learning_job` | `vacuum_entity_id`, `job_id` | Optional: `reason`, `rebuild_csv` |
| `restore_learning_job` | `vacuum_entity_id`, `job_id` | Optional: `rebuild_csv` |

##### Run-record attribution fields

The `get_learning_history_snapshot` recent-jobs list carries per-run **attribution** fields the Review card reads. They ride the 1.8.0 native-current-room attribution path (see [eufy-native-transition](../eufy-native-transition.md)); an index built before these keys existed self-heals on the next snapshot.

- `origin` — `"external"` (app-started, captured) or `null`/absent (dispatched by this integration). The `origin` filter is binary `external` \| `internal`; a dispatched run with no `origin` key still matches `internal`. Drives the card's **Origin** filter chip and an "External" origin badge.
- `has_attribution_disagreement` — bool. A dispatched run whose native current-room named a *different* room than the positional (segment K → queue room K) assignment; surfaced as the card **"Room Mismatch"** badge (the assignment is kept, **never** silently overridden).
- `cleaning_area_m2` — the run's cleaned floor area in canonical m² (the card's **"Area Cleaned"**), shown on external runs (single and multi-room). External records fall back to summing per-room `room_timings[].area_m2` when no job-level sensor read exists.
- `cleaning_area_sensor_m2` — the device's own run-total area (m²), the sanity **upper bound**.
- `area_over_attributed` — bool; the per-room attributed sum exceeded `cleaning_area_sensor_m2` beyond tolerance (a double-counting alarm).

#### Dock (base station)

| Service | Required fields |
|---|---|
| `wash_mop` | `vacuum_entity_id`, `map_id` |
| `dry_mop` | `vacuum_entity_id`, `map_id` |
| `stop_dry_mop` | `vacuum_entity_id`, `map_id` |
| `empty_dust` | `vacuum_entity_id`, `map_id` |
| `reset_maintenance` | `vacuum_entity_id` |
| `set_maintenance_interval` | `vacuum_entity_id`, `component` (`brush` \| `side_brush` \| `filter` \| `mop` \| `sensor`), `interval_hours` (> 0) |
| `set_dock_event_count` | `vacuum_entity_id` |
| `set_pause_timeout_settings` | `vacuum_entity_id`, `pause_timeout_minutes_default` |

#### Profiles (room and run)

| Service | Required fields | Notes |
|---|---|---|
| `get_room_profiles` | _(none)_ | Global profile library |
| `save_user_room_profile` | _(payload)_ | |
| `save_room_profile_from_room` | `vacuum_entity_id`, `map_id`, `room_id`, `label` | Optional: `profile_name` |
| `overwrite_room_profile` | _(payload)_ | |
| `overwrite_room_profile_from_room` | `vacuum_entity_id`, `map_id`, `room_id`, `profile_name` | Optional: `label` |
| `rename_room_profile` | `profile_name` | Optional: `new_profile_name`, `label` |
| `delete_room_profile` | `profile_name` | |
| `apply_room_profile` | `vacuum_entity_id`, `map_id`, `room_ids`, `profile_name` | |
| `get_saved_run_profiles` | `vacuum_entity_id`, `map_id` | |
| `save_run_profile` | `vacuum_entity_id`, `map_id`, `name` | Optional: `expose_as_button` |
| `overwrite_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | Optional: `name`, `expose_as_button` |
| `apply_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | Restores saved room selection and settings |
| `rename_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id`, `name` | |
| `delete_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | |
| `start_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | |

#### Theme

| Service | Notes |
|---|---|
| `get_theme_library` | Returns full library of saved themes and working draft |
| `set_active_theme` | `theme_id`; optional `vacuum_entity_id` |
| `update_working_draft` | `vacuum_entity_id`; optional `tokens`, `colors`, `alpha` |
| `revert_draft` | `vacuum_entity_id` |
| `save_theme_as_new` | `vacuum_entity_id`, `name`; optional `set_as_default` |
| `overwrite_theme` | `vacuum_entity_id`, `theme_id` |
| `rename_theme` | `theme_id`, `name` |
| `set_theme_tags` | `theme_id`, `tags` (free-text "vibe" tag list; empty list clears them — facet/colorblind-safe tags are derived from the palette, never set here) |
| `delete_theme` | `theme_id` |
| `export_theme` | `theme_id` |
| `import_theme` | `payload` |

#### Setup

| Service | Notes |
|---|---|
| `setup_get_status` | Returns vacuum list and map import state |
| `setup_add_vacuum` | `vacuum_entity_id` |
| `setup_import_active_map` | `vacuum_entity_id` |
| `setup_get_map_rooms` | `vacuum_entity_id`, `map_id` |
| `setup_save_rooms` | `vacuum_entity_id`, `map_id`, `enabled_room_ids`, `floor_types` |
| `setup_delete_map` | `vacuum_entity_id`, `map_id`; optional `confirmation_token` — required for any protected map. A **named** high-protection map needs a typed token matching the map's stored name (`requires_typed_confirmation`); an **unnamed** high-protection map and any elevated map need only a one-click confirm, any non-empty token (`requires_confirmation`). The card reads those two protection fields to choose the prompt. |
| `setup_set_panel_title` | `vacuum_entity_id`; optional `title` (blank reverts to the default). Renames the vacuum's sidebar panel and re-registers it live (refresh the browser to repaint the sidebar) |
| `setup_set_map_camera` | `vacuum_entity_id`; optional `entity_id` (blank clears the override → falls back to the adapter's `live_map_image_entity_pattern`). Sets the per-vacuum live-map image/camera override the dashboard snapshot prefers over the pattern (see [Live-map backdrop read model](#live-map-backdrop-read-model)) |

#### Mapping / map image

| Service | Required fields | Notes |
|---|---|---|
| `upload_map_image` | `vacuum_entity_id`, `map_id`, `image_base64` | Optional: `variant`, `layout_id`, `image_width`, `image_height`. The `variant` validator accepts `default` \| `dark` \| `light` \| `custom` \| `custom_*` (default `default`). `dark`/`light`/`default` are segmenter inputs. `custom` and the per-layout `custom_<layout_id>` variants are manual-authoring backdrops and are **never auto-segmented** — `analyze_map_image` only probes `dark`/`default`/`light`. Passing `layout_id` forces `variant` to `custom_<layout_id>` and repoints that layout's `backdrop_variant` (returns `{saved: false, reason: "layout_not_found"}` if the layout doesn't exist). The stored variant's `image_width`/`image_height` are the pixel space `set_custom_segments` rasterises against. **response** |
| `delete_map_image` | `vacuum_entity_id`, `map_id` | Optional: `variant` (same enum). Removes one stored variant; safe to repeat. **response** |
| `analyze_map_image` | `vacuum_entity_id`, `map_id` | Runs the segmenter on the `dark`/`default` (and assist `light`) variants; caches `image_segments`. **response** |
| `get_map_segments` | `vacuum_entity_id`, `map_id` | Returns the active segment set plus overlays. Response carries `segmentation_mode`; in `custom` mode it serves the **active layout's** `custom_segments` over its `custom_<layout_id>` backdrop. Also returns `custom_layouts` (list) + `active_custom_layout_id` + `segment_room_links` (see [Map segments read model](#map-segments-read-model-get_map_segments-response) / [Minimum viable polling loop](#minimum-viable-polling-loop)), plus the map's `saved_zones` list (see [Saved zones](#saved-zones-response)). **response** |
| `set_segmentation_mode` | `vacuum_entity_id`, `map_id`, `mode` | `mode` ∈ {`cv`, `custom`}. **Flips a per-map flag only — never re-runs the segmenter.** Both the CV base (`image_segments`) and every custom layout persist; the toggle is a pointer flip, so `cv → custom → cv` is lossless. Flipping to `custom` with no active layout soft-selects the first existing layout. **response** |
| `set_custom_segments` | `vacuum_entity_id`, `map_id`, `segments` | **Replace-all** write of manually-authored segments **into the active custom layout** (auto-creating a default layout if none exists). `segments = [{id?, primitives: [...]}]` (extra keys allowed). A primitive is `{type: rect\|circle\|polygon, op?: subtract, ...pct geom 0-100}`. Each segment is rasterised server-side (`segment_primitives.rasterize_primitives` → `mask_to_polygon`, the same tracer CV uses) into one polygon, scaled to the active layout's backdrop pixel dims. Requires that backdrop (returns `{saved: false, reason: "no_custom_backdrop"}` without it). Degenerate segments are dropped. **response** |
| `create_custom_layout` | `vacuum_entity_id`, `map_id` | Optional: `name` (default `Custom`). Mints + **activates** a new named layout (its own `custom_<layout_id>` backdrop, segments, room links, mascot anchors) and flips the map into `custom` mode. Returns `{saved, layout_id, layout}`. **response** |
| `rename_custom_layout` | `vacuum_entity_id`, `map_id`, `layout_id`, `name` | Renames an existing layout. Returns `{saved: false, reason: "layout_not_found"}` for an unknown id, or `missing_name` for a blank name. **response** |
| `delete_custom_layout` | `vacuum_entity_id`, `map_id`, `layout_id` | Deletes the layout and best-effort removes its backdrop file/variant. If it was active, the next remaining layout (by name) is activated — or the map flips back to `cv` when none remain. Returns the resulting `active_custom_layout_id` + `segmentation_mode`. **response** |
| `set_active_custom_layout` | `vacuum_entity_id`, `map_id` | Optional: `layout_id`. Activates that layout and flips the map into `custom` mode; a `null`/omitted/unknown `layout_id` auto-creates + activates a default layout so `custom` mode always resolves a live store. **response** |
| `set_segment_room_link` | `vacuum_entity_id`, `map_id`, `segment_id` | Optional: `room_id` (omit/null to clear). Enforced 1:1 — assigning a room already linked elsewhere drops the older link. Returns the full updated `segment_room_links`. **response** |
| `set_companion_anchor` | `vacuum_entity_id`, `map_id`, `room_id` | Optional: `pct_x`, `pct_y` (0–100; omit both to clear). Stored as `{room_id: {pct_x, pct_y}}` in `companion_anchors`. The reserved key `dock` holds the docked-mascot home spot. Returns the full updated `companion_anchors`. **response** |
| `set_live_map_rotation` | `vacuum_entity_id`, `rotation` | Optional: `map_id` (defaults to the active map). `rotation` ∈ {`0`, `90`, `180`, `270`}. Stores the live-map display rotation per map; **display-only — never affects dispatch** (cleaning is by room), and follows the user across devices. **response** |
| `adjust_map_segment` | `vacuum_entity_id`, `map_id`, `segment_id` | Optional adjustment fields (`delta_x`/`delta_y`, `edge_*`, `vertex_moves`). Accumulates into `image_segment_adjustments`; applied at read time. **response** |
| `set_map_overlay_visibility` | `vacuum_entity_id` | Optional: `map_id`, `visibility` (partial map of overlay layer → bool: `room_labels`, `room_area`, `current_room`, `robot`, `dock`, `no_go`, `no_mop`, `walls`, `zones`, `path`, `obstacles`), `reset`. Show/hide individual Map-view overlay layers; stored per map, **display-only — never affects cleaning**. **response** |
| `set_hidden_regions` | `vacuum_entity_id` | Optional: `map_id`, `regions` (list of `[x0, y0, x1, y1]` normalised 0–1 rectangles; empty clears all). Per-map mask rectangles that hide render noise; normally driven by the card's "Hide area" draw tool. **response** |
| `set_area_label_anchor` | `vacuum_entity_id`, `room_id` | Optional: `map_id`, `pct_x`, `pct_y` (0–100; omit both to reset to the room centre). Moves a room's area (m²) chip off its name label; stored per map. **response** |
| `get_map_render_data` | `vacuum_entity_id` | Returns the raw room raster + decode params the card uses to draw its own backdrop (no server-side rendering); adapter-driven, cached by the returned version. Brands without a `map_render` config return `{present: false}`. **response** |
| `get_map_live_pose` | `vacuum_entity_id` | Returns the live moving-overlay pose (robot + dock anchors, current room, heading) from the provider's in-memory coordinator — fresher than the `.storage`-derived pose. Polled on the live cadence. Brands without a `live_pose` config return `{present: false}`. **response** |
| `compare_map_sources` | `vacuum_entity_id` | Diagnostic verify probe: compares the provider's in-memory map data against the `.storage` copy and reports whether raster + geometry are byte-identical (`normalization_safe`). **response** |

#### Live-map backdrop read model

For live-image brands (Roborock today), the Map view's backdrop is an HA `image` entity exposed by the brand's core integration — not a stored variant or CV/custom geometry. The contract for it is carried on the **`get_dashboard_snapshot`** response, which also emits two extra fields: `live_map_image_entity` (the resolved image entity ID, or `null`) and `live_map_rotation` (the per-map stored display rotation, normalised to one of `0`/`90`/`180`/`270` — surfaced even at `0` so the card always has a value).

The resolution is brand-owned at the seam: the adapter declares `mapping.live_map_image_entity_pattern` (e.g. Roborock's `image.{object_id}_{map_slug}`), core fills the `{object_id}` / `{map_slug}` placeholders, **existence-checks** the candidate against `hass.states`, and surfaces it only if it exists. Absent (Eufy / older backends) → `live_map_image_entity` is `null` and there is no live backdrop. The card renders the resolved image as the Map-view backdrop and applies `live_map_rotation` to the **whole content layer** (image, polygons, labels, and mascot together), so a 90° step never rotates the CV/custom polygons independently of their backdrop.

**Override-first resolution.** `get_dashboard_snapshot` now resolves the entity **override-first**: a per-vacuum override stored on the vacuum record (`data["vacuums"][vid]["live_map_image_entity"]`, written by the **`setup_set_map_camera`** service from the Setup tab's "Live map camera" picker) wins over the adapter pattern, and is itself existence-checked — a stale/renamed override that no longer resolves falls through to the pattern. The resolver is **domain-agnostic**: either branch may yield an `image.` or a `camera.` entity. The Eufy adapter now ships a best-effort `live_map_image_entity_pattern` of `camera.{object_id}_map`, so a default-named install running jeppesens eufy-clean (mainline v1.11.0+, where the vacuum entity and eufy-clean's `camera.<device>_map` share the device slug) auto-resolves **without** picking; the picker is the override for when the vacuum entity was renamed. Existence-gating keeps older or plain Eufy installs (no live-map camera) at `live_map_image_entity = null`.

**Cache-busting a `camera.` backdrop.** An `image.` entity rotates its `entity_picture` token every frame (it self-busts), but a `camera.` entity's token is stable — so a naïve `<img>` would never refetch. `src/state/map.js` `_liveMapImageUrl` appends the live entity's `last_updated` as a query param, forcing the browser to refetch each ~2 s frame. `mapImageUrl` (also in `state/map.js`) short-circuits to this live URL whenever `isLiveBackdropActive` reports the active scope is live-pinned (see below), so the live image always wins over any uploaded backdrop.

**"Live map" as a selectable source.** Beyond being the brand backdrop, the live image is selectable in Map Configuration: `_renderSegmentationToggle` (`src/renderers/map.js`) adds a **"Live map"** chip — shown only when a live entity is available — that selects/creates a custom layout marked `backdrop_source: "live"` (the new `backdrop_source` param on `create_custom_layout`). A live-pinned layout always renders the live image and ignores its `custom_<layout_id>` backdrop; you then **draw + link** rooms over the live map with the existing composer, and the same `segment_room_links` / tap-select machinery makes them selectable — unchanged from any other custom layout. **Caveat:** compose against a fully-mapped (stable) map — polygons store as 0-100% of the image, so if the map footprint changes (e.g. it grows during a first mapping run, shifting the aspect ratio) the drawn rooms drift.

**Room-label visibility toggle.** A per-vacuum map-toolbar toggle gates VA's own `.evcc-map-label` render (`mapRoomLabelsEnabled`, persisted to localStorage `evcc_map_labels_<vac>`, default **on**). eufy-clean's live map bakes in its own room labels, so VA's would stack into noise on top of them — flip the toggle off on the live map, leave it on for plain CV/custom maps.

---

### HA Events

Subscribe via `hass.connection.subscribeEvents(callback, eventType)`.

| Event type | Payload fields | When it fires |
|---|---|---|
| `eufy_vacuum_job_finished` | `vacuum_entity_id`, job summary fields | Job reaches a terminal state |
| `eufy_vacuum_room_started` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name` | Robot enters a room |
| `eufy_vacuum_room_finished` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, timing fields | Robot finishes a room |
| `eufy_vacuum_path_blocked` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name` | Blockage detected during cleaning |
| `eufy_vacuum_stall_detected` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` | Robot has been in a room >= 2x its learned threshold with `awaiting_bounds_exit = true`. Fires at most once per room per job |
| `eufy_vacuum_room_skipped` | `vacuum_entity_id`, `map_id`, `job_id`, `room_id`, `room_name`, `completed_room_ids` (list of int) | Live tracking advanced past a queued room that was never completed. Fired by `ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py`), deduped once per room per job via `_skipped_notified_room_ids`. Largely inert for Eufy's sequential counter; meaningful on brands whose live position can leapfrog the queue order |
| `eufy_vacuum_run_incomplete` | `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids` (list of int), `missed_rooms` (list of `{room_id, name}`) | Fired by `finalize_learning_job` when a cancelled/failed/interrupted job left uncleaned rooms |

---

### HA Entities the UI reads

Entity IDs are derived from the vacuum's `object_id` (the part after the dot in `vacuum.alfred` → `alfred`).

#### Vacuum entity

The primary vacuum entity (`vacuum.{object_id}`) is the core state source:

- `state` — `cleaning`, `docked`, `returning`, `paused`, `error`, `idle`
- `attributes.battery_level` — integer 0–100
- `attributes.friendly_name` — display name

#### Switch entities (room enabled/disabled)

The integration creates one switch per room per map: `switch.{object_id}_{map_slug}_{room_slug}`. The switch's `on`/`off` state is the room's enabled flag. Switch `extra_state_attributes` carry all room settings:

```
vacuum_entity_id, map_id, room_id, room_name, slug,
order, profile_name, clean_mode, fan_speed, water_level,
clean_intensity, clean_passes, edge_mopping, floor_type,
carpet, grants_access_to, is_dock_room, rules
```

The card discovers room switches by scanning `hass.states` for entities whose attributes contain `vacuum_entity_id` matching the configured vacuum. It does not rely on a fixed naming pattern.

#### Number entities (room order)

The integration creates one number entity per room per map: `number.{object_id}_{map_slug}_{room_slug}_order`. The integer state is the room's 1-based sort position. Write by calling `number.set_value`.

#### Sensor entities

| Entity ID pattern | `state` | Key `attributes` |
|---|---|---|
| `sensor.{object_id}_theme_state` | Theme ID string | `vacuum_entity_id`, active theme tokens + colors + alpha, working draft overrides, `draft_dirty` flag |
| `sensor.{object_id}_active_map` | Active map ID | Map metadata |
| `sensor.{object_id}_available_profiles` | Profile count | Available profile definitions |
| `sensor.{object_id}_dock_events` | Event count | Dock event history |
| `sensor.{object_id}_robot_position_x_raw` | X coordinate (int) | Raw robot X position |
| `sensor.{object_id}_robot_position_y_raw` | Y coordinate (int) | Raw robot Y position |
| `sensor.{object_id}_{component}_remaining` | Hours remaining | Per-component maintenance sensor (one per maintenance component) |

Per-room sensors are also registered at setup:
- `sensor.{object_id}_{map_slug}_{room_slug}_cleaning_history` — room-level cleaning history
- `sensor.{object_id}_{map_slug}_{room_slug}_rule_status` — room rule evaluation status

#### Theme sensor attributes (detailed)

The `sensor.{object_id}_theme_state` entity is the backend's source of truth for all theme state. On every HA update its attributes should be mirrored into your UI's theme state. Key attribute fields:

- `vacuum_entity_id` — confirms this sensor belongs to a specific vacuum
- `active_theme_id` — the currently applied theme
- `working_draft` — dict of token/color/alpha overrides being edited
- `draft_dirty` — boolean; true when the draft differs from the saved theme
- Token, color, and alpha maps for the active theme

#### Map segments read model (`get_map_segments` response)

Map geometry is **not** carried on an entity — it is fetched on demand via `get_map_segments` (response service) and lives in the per-map bucket `data["maps"][vacuum][map_id]`. The stored keys are:

- `image_segments` — the CV base: the canonical `SegmentationResult` from the segmenter engine. CV stays special at the **map-bucket level** — re-running CV re-segments and forces a relink.
- `custom_layouts` — `{layout_id: {id, name, backdrop_variant, custom_segments, segment_room_links, companion_anchors, created_at, updated_at}}`. A map can hold **many** named custom layouts (e.g. a "solar system" image and a "tree" image), each owning its **own** backdrop, authored segments, room links, and mascot anchors. Two layouts can each have a segment id `living` linked to *different* rooms — impossible in the old single-store model.
- `active_custom_layout_id` — which layout `custom` mode serves.
- `segmentation_mode` — `cv` or `custom`. `custom` serves the **active** layout.
- `image_segment_adjustments` — `{segment_id: {offset_x, offset_y, edge_left/right/top/bottom, vertex_moves: [{index, delta_x, delta_y}]}}`. Applied to CV polygons at read time.
- `image_variants` — `{name: {variant, path, browser_url, width, height}}`. Each layout's backdrop lives here under `custom_<layout_id>`; the legacy shared `custom` variant remains valid.
- `segment_room_links` — `{segment_id: room_id}` (enforced 1:1). At the map-bucket level this is **CV's** link store; each custom layout owns its **own** per-layout `segment_room_links`.
- `companion_anchors` — `{room_id | "dock": {pct_x, pct_y}}` — per-room sprite anchors; the reserved `dock` key holds the docked-mascot home spot. The map-bucket dict is **CV's**; each custom layout owns its **own** per-layout `companion_anchors` (including its own reserved `dock` spot).
- `custom_segments` (legacy) — the pre-layout single custom store. It is migrated **lazily and non-destructively** into a default `Custom` layout on first read (`_migrate_custom_layouts`): the legacy key is kept, never deleted, and the migration is idempotent.
- `rooms` — managed room metadata for the map.

**Scope resolution.** Every read/write routes through `_resolve_active_scope(map_bucket)`, which returns the live `{segments_store, links, anchors, backdrop_variant}`: the **CV branch** points at the map-bucket keys; the **custom branch** points at the active layout's keys. `get_map_segments`, `set_segment_room_link`, and `set_companion_anchor` all route through it; `set_custom_segments` targets the active layout (auto-creating a default if none).

The response is derived from these at read time: `polygon_pct`, the per-segment `room_id`, and the applied `adjustments` are all computed in `_handle_get_map_segments`, not stored. The response carries **`segmentation_mode`**, plus **`active_custom_layout_id`**, **`custom_layouts`** (a list of `{id, name, backdrop_variant, backdrop_source, segment_count, created_at, updated_at}` summaries), and the active scope's **`segment_room_links`**. When the mode is `custom` the endpoint serves the active layout's `custom_segments` over its `custom_<layout_id>` backdrop. Reading never invokes the segmenter, so a `cv ↔ custom` flip — or a switch between custom layouts — is a cheap, lossless pointer change.

---

## Building a Different UI — What You Need

This section specifies the minimum required for any UI (React app, Vue SPA, native app, CLI tool, etc.) that wants to drive a eufy_vacuum installation.

### Minimum viable polling loop

The backend does not push card-specific state over WebSockets. You must poll:

```
Every time hass.states updates (subscribe via HA WebSocket connection event):
  - Read vacuum entity state + battery from hass.states
  - Read all switch entities whose attributes.vacuum_entity_id == your vacuum
  - Read all number entities whose attributes.vacuum_entity_id == your vacuum
  - Read sensor.{object_id}_theme_state attributes
  - Read sensor.{object_id}_active_map state

Every 500 ms (debounced after HA state push):
  - Call get_dashboard_snapshot(vacuum_entity_id, map_id)

Every 800 ms (debounced after HA state push):
  - Call get_start_status(vacuum_entity_id, map_id)

On Base Station tab activation:
  - Call get_dock_action_status(vacuum_entity_id, map_id)
  - Call get_pause_timeout_settings(vacuum_entity_id)

On Metrics tab activation:
  - Call get_metrics_snapshot(vacuum_entity_id, filters...)

On Learning Review tab activation:
  - Call get_learning_history_snapshot(vacuum_entity_id, filters...)

Once per session (load-once):
  - Call get_theme_library()
  - Call get_incomplete_run_log(vacuum_entity_id)
  - Call get_trouble_rooms_log(vacuum_entity_id)

On Rooms tab when map_id or vacuum changes:
  - Call get_saved_run_profiles(vacuum_entity_id, map_id)
  - Call get_room_learning_estimates(vacuum_entity_id, map_id)

On map view open / when map_id or vacuum changes:
  - Call get_map_segments(vacuum_entity_id, map_id)
```

`get_map_segments` returns `segmentation_mode`, `active_custom_layout_id`, and the `custom_layouts` list. The card reads these to select the active segment store and backdrop variant: in `cv` mode it shows `image_segments` over the `dark`/`default`/`light` backdrop (rendered `object-fit: contain`); in `custom` mode it shows the **active layout's** `custom_segments` over that layout's `custom_<layout_id>` backdrop (rendered `object-fit: fill`), and renders the `custom_layouts` list as the layout-picker chips. The same response also rebuilds the composer draft once per `${map_id}:${active_custom_layout_id}` (see [custom-segment-composer.md](custom-segment-composer.md)).

### Event subscriptions needed for real-time updates

Subscribe to all seven events for any UI that tracks live jobs:

| Event | Why |
|---|---|
| `eufy_vacuum_room_started` | Update "currently cleaning" indicator |
| `eufy_vacuum_room_finished` | Update completed rooms list; trigger reanchor call |
| `eufy_vacuum_job_finished` | Clear active job UI; show summary |
| `eufy_vacuum_path_blocked` | Surface a blockage warning |
| `eufy_vacuum_stall_detected` | Show stall warning banner |
| `eufy_vacuum_room_skipped` | Flag a queued room the run advanced past without cleaning |
| `eufy_vacuum_run_incomplete` | Show missed rooms prompt; offer retry action |

### Entity reads needed for room state

For each room in the active map you need:

1. **Switch entity** for enabled/disabled state and all room settings (name, mode, fan speed, etc.). Discover by scanning `hass.states` for entities where `state.attributes.vacuum_entity_id === yourVacuumEntityId` and the entity ID starts with `switch.`.
2. **Number entity** for sort order. Discover by scanning `hass.states` for entities where `state.attributes.vacuum_entity_id === yourVacuumEntityId` and the entity ID starts with `number.` and ends with `_order`.

The active map ID comes from `sensor.{object_id}_active_map` state value.

### Service call safety notes

**Safe to call from any UI without side effects:**

- All `get_*` services (read-only query services)
- `get_theme_library` (read-only)
- `run_learning_estimate` (read-only compute, does not mutate stored state)
- `reanchor_learning_timeline`, `get_next_room` (pure compute)

**Has side effects — understand before calling:**

- `start_selected_rooms` — starts the vacuum. Do not call without confirming `get_start_status` returns non-blocked. Do not call with `returnResponse = true` (HA rejects it).
- `start_zone_clean` — dispatches an ad-hoc free-form zone clean (rectangles drawn on the live map) on `supports_zone_clean` providers. Fire-and-forget — it carries no room ids and never touches the job/queue/learning store, so there is no tracked active job to pause/resume/cancel afterward.
- `clear_queue` — empties the pending run queue only; does **not** disable rooms (the card UI disables rooms as a separate composite action before calling it).
- `finalize_learning_job` — fires `eufy_vacuum_run_incomplete` if rooms were missed. Call only when a job ends.
- `setup_delete_map` — destroys a map and all its room data. A protected map needs a `confirmation_token`: a **named** high-protection map needs a typed token matching the map name; an **unnamed** high-protection map and any elevated map need only a one-click confirm (any non-empty token).
- `wash_mop`, `dry_mop`, `empty_dust` — physically operate dock hardware.
- `update_room_fields` — null optional fields (e.g. `water_level`) must be omitted, not sent as null. HA schema validation will reject them.
- `apply_run_profile` — overwrites current room selection and settings with saved profile values.
- `revert_draft` — discards unsaved theme editor changes.

---

## Render-data shapes

The **render-DATA** a UI draws the map from — the segment geometry (`polygon_pct` per segment), the per-segment `room_id` links, `room_names`, the live robot/dock **pose**, and the **dashboard snapshot** read model — is **not defined in this doc**. This doc only records the *services* that fetch them (`get_map_segments`, `get_map_render_data`, `get_map_live_pose`, `get_dashboard_snapshot`, above). The authoritative shape definitions and how the sources are normalised live in:

- [map source coordinator](../31-map-source-coordinator.md) — how the map data sources are selected, coordinated, and cached per brand.
- [map-state-source](../map-state-source.md) — the canonical map-state shape (raster + geometry + `room_names` + pose) the coordinator produces.

This stub is the anchor for that topic from the frontend side; expand it here only if a frontend-specific view of the render-data shapes is later needed. For the card-side render path that *consumes* these, see [map-render-layers.md](map-render-layers.md).
