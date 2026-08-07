# Frontend ↔ Backend Contract & Data Shapes

This is the **seam doc**: what a UI **reads** from the backend (services, events, entities) and what it **writes** back (service calls). Everything in the Backend Contract below is what *any* UI — the shipped card, a React app, a native client, a CLI — must consume to drive a eufy_vacuum installation; "Building a different UI" then distills the minimum a non-card client needs. For the overall frontend map and how the layers fit together, start at the hub, [architecture-overview.md](architecture-overview.md).

The **map render-DATA shapes** — the map segment geometry, `room_names`, and the live pose the card draws its backdrop and overlays from — are **not owned here**. They are sourced and normalised by the [map source coordinator](../31-map-source-coordinator.md) and defined in [map-state-source](../design/map-state-source.md); this doc only records how a UI *fetches* them (`get_map_segments` / `get_map_render_data` / `get_map_live_pose`). The **dashboard / job-progress snapshots** the card renders from, by contrast, ARE aggregated here — with the field-by-field shape linked to the DR-grade backend docs ([05 §6](../05-core-manager.md#6-direct-responsibilities) / [03](../03-data-model.md) / [06](../06-job-lifecycle.md)).

---

## The Backend Contract

### HA Services

All services live in the `eufy_vacuum` domain. Call them via `hass.callService(domain, service, data, target?, notifyOnError?, returnResponse?)`. Services marked **response** must be called with `returnResponse = true`; the result lives at `result.response`.

> **`map_id` is usually optional even where a table lists it as required** — most services auto-resolve it to the active map (`resolved_call_data`), so passing it explicitly always works but omitting it is fine. The over-strict direction is safe. Separately, `debug_capture_*` / `debug_log_live_room` are internal diagnostics, **not** part of the client contract.

#### State queries (read-only, response)

| Service | Required fields | What it returns |
|---|---|---|
| `get_start_status` | `vacuum_entity_id`, `map_id` | Pre-flight eligibility: fixed field set + a priority-ordered `reason` enum + `requires_confirmation`/`confirm_token` (the reduced-run handshake source). Full shape: [06 §1](../06-job-lifecycle.md) |
| `get_dashboard_snapshot` | `vacuum_entity_id`, `map_id` | The per-vacuum **39-key card read model** — sub-snapshots (`job_progress`, `job_control`, `start_status`, `lifecycle`, `upkeep`, `planned_job_estimate`, `queue_steps`) + a **capability-hint block** (now incl. `zone_bounds` / `supports_water_control` / `supports_edge_mopping`) + a **live-map block** + `status_summary`/`attention_summary`/`learning_processing`/`updated_at`. There is **no** "room list" key (rooms come from switch entities). Full field-by-field shape: [05 §6 `get_dashboard_snapshot`](../05-core-manager.md#6-direct-responsibilities); see [Capability flags → behavior](#capability-flags--behavior) for the hint block |
| `get_dock_action_status` | `vacuum_entity_id`, `map_id` | Dock action availability (wash/dry/empty), active action flags |
| `get_pause_timeout_settings` | `vacuum_entity_id` | Configured pause-timeout duration |
| `get_lifecycle_state` | `vacuum_entity_id` | Raw lifecycle state dict |
| `get_job_progress_snapshot` | `vacuum_entity_id` | Live in-progress job snapshot: `current_room_id`, **`current_room_ids`** (list of int — everything the CURRENT phase covers: a single-room phase yields one id identical to `current_room_id`; a `room_group` phase yields every room of the dispatch from the phase's own `resolved_rooms`, falling back to `[current_room_id]` for atomic runs/breaks — RP-047: a group is ONE dispatch, so `current_room_id` pins to the group's first room and must not be read as the whole answer), **`current_phase`** (`{index, phase_type, room_ids, is_group}`, or `null` when no phase is resolvable), `completed_room_ids`, `remaining_room_ids`, `skipped_room_ids`, `progress_percent`, the per-room `timeline`, `awaiting_bounds_exit` (group-phase-aware: the threshold sums the whole dispatch), the `charge_*`/`wait_*`/`zone_*` phase surfacing, and the `live_queue` monitor twin. Full shape: [03 §5b](../03-data-model.md) + [05 §6](../05-core-manager.md#6-direct-responsibilities). The intended refresh trigger is the `eufy_vacuum_job_progress_tick` event (see [Events](#ha-events)) |
| `get_job_control_state` | `vacuum_entity_id` | Card **action-affordance** state (NOT queue content — that's `get_queue_state`): `status`, `status_label`, `terminal`, `can_start`/`can_pause`/`can_resume`/`can_cancel`/`can_clear`, `reason`/`reason_label`/`reason_detail`, `message`, `pause_timeout_minutes_default`/`_effective`, `warning`, `status_summary`, `job_id`, `current_room_id` |
| `get_upkeep_snapshot` | `vacuum_entity_id` | Maintenance: `replacement_items`, `maintenance_items`, `attention_count`, `attention_summary`, priority rollup. See [13-maintenance-manager](../13-maintenance-manager.md) |
| `get_queue_state` | `vacuum_entity_id`, `map_id` | Raw queue content; shape [03 §4](../03-data-model.md) |
| `get_payload_state` | `vacuum_entity_id`, `map_id` | Raw room-clean payload; shape [03 §4](../03-data-model.md) |
| `get_active_job` | `vacuum_entity_id` | Active job dict; shape [03 §5](../03-data-model.md) / [06 §2c](../06-job-lifecycle.md) |
| `get_vacuum_capabilities` | `vacuum_entity_id` | Optional: `detected_model`, `refresh` (default true). The **5 payload-gating hardware flags** (`supports_mop_features`, `supports_water_control`, `supports_path_control`, `supports_edge_mopping`, `supports_passes`) — see [03 §1 CapabilityBucket](../03-data-model.md) and [Capability flags → behavior](#capability-flags--behavior) |
| `get_vacuum_maps` | `vacuum_entity_id` | Registered maps for the vacuum |

#### Job control (side-effecting)

| Service | Required fields | Notes |
|---|---|---|
| `start_selected_rooms` | `vacuum_entity_id`, `map_id` | **response** (since FE-ERR-1 — call with `returnResponse = true`). Optional: `confirm_reduced_run`, `confirm_token`, `strict_order`, `path_block_action` (`event_only` \| `pause_and_event` \| `cancel_and_event`), `pause_timeout_minutes_override`. Every blocked path returns a structured `{started: false, reason, message, …}` payload (a TOCTOU refusal at the actual dispatch can differ from `get_start_status`'s earlier pre-check), so a refused start is distinguishable from a started one. The reduced-run `confirm_token` comes from `get_start_status` (which returns `requires_confirmation` + `confirm_token`); `strict_order` / `path_block_action` materially change run behavior |
| `start_zone_clean` | `vacuum_entity_id`, `zones` | **response.** Optional: `clean_times` (int ≥ 1, default 1 — **no fixed schema ceiling**; the per-brand ceiling is enforced against the adapter's zone-repeat capability at dispatch), `map_id`. Ad-hoc free-form zone clean — `zones` is a list of `[x0, y0, x1, y1]` rectangles as 0–1 fractions of the live-map image (top-left origin). Untracked: no room ids, no job/queue/learning store — but **no longer unconditionally fire-and-forget**: since RP-010/RF-06 it first checks `get_start_status`'s blocker evaluation and, if blocked for one of `job_paused` \| `active_job_running` \| `mid_job_service` \| `vacuum_busy`, **refuses without dispatching**: `{success: false, reason: "job_in_progress", start_status_reason: <the get_start_status reason>, message}` — **no `started` key**, a different shape from `start_selected_rooms`'s refusal. On any other reason it falls through and dispatches normally. Requires a provider with the `supports_zone_clean` capability |
| `pause_active_job` | `vacuum_entity_id` | **response** |
| `resume_active_job` | `vacuum_entity_id` | **response** |
| `cancel_active_job` | `vacuum_entity_id` | **response.** Performs the return-to-base itself and finalizes the run through the cancel chokepoint; fires `eufy_vacuum_run_incomplete` when the finalize reports missed rooms. This — not `vacuum.return_to_base` — is how a client cancels a tracked run (the stock dock command leaves the tracker believing the run is live, and the finalizer then records a truncated run as completed + learned) |
| `vacuum.return_to_base` | `entity_id` (HA vacuum entity) | Standard HA vacuum service — not in eufy_vacuum domain |
| `clear_queue` | `vacuum_entity_id` | Optional: `map_id` (defaults to active map). Clears the pending run queue without stopping a running job |
| `clear_active_job` | `vacuum_entity_id` | |

#### Room management

| Service | Required fields | Notes |
|---|---|---|
| `update_room_fields` | `vacuum_entity_id`, `map_id`, `room_id` | **response** (`{updated, ...}`). Optional: `enabled`, `clean_mode`, `fan_speed`, `clean_intensity`, `clean_passes`, `water_level`, `edge_mopping`, `color` (per-room fill `#rrggbb`/`#rgb`/null), `is_transition`, `grants_access_to`, `is_dock_room`, `rules`. Omit null optional fields — HA schema rejects them |
| `discover_rooms` | `vacuum_entity_id` | Interrogates the vacuum for the current room list |
| `save_managed_rooms` | `vacuum_entity_id` | Persists discovered rooms into integration storage |
| `get_room_access_editor` | `vacuum_entity_id`, `map_id` | Returns room access graph for editing |
| `get_access_graph_health` | `vacuum_entity_id`, `map_id` | Validates access graph integrity |
| `reconcile_room` | `vacuum_entity_id`, `map_id`, `room_id` | Re-segment room-identity migration (native-segment brands, e.g. Roborock) |
| `set_room_access_graph` | `vacuum_entity_id` | **response.** REPLACE one map's whole access graph in a single atomic write (N per-room writes would leave the map observably half-built). Optional: `map_id`, `dock_room_id`, `edges` (a list of `{from, to}` int pairs — pairs, not a parent→children map, so a caller can't express the same graph two ways). **Both `dock_room_id` and `edges` omitted = the CLEAR operation**, not a no-op — clearing lands on the permissive `blank` state (basic runs allowed), which is why there is no separate clear service |

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
| `add_queue_break` | `vacuum_entity_id`, `map_id`, `after_index`, `break_type` | `break_type` ∈ {`charge_wait`, `wait`} (**required**). Insert a `charge_wait` (with `target_battery_percent` 1–100) or `wait` (with `wait_minutes` 1–1440) stop between room groups |
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
| `run_learning_estimate` | `vacuum_entity_id`, `map_id` | Optional: `current_battery` (default 0), `started_at` (omit for pre-start calls), `charge_percent_per_minute` (default 1.0), `reserve_battery_percent` (default 5.0). Read-only compute. Returns time estimates per room |
| `reanchor_learning_timeline` | `original_estimate`, `completed_rooms`, `reanchor_at` | Optional: `current_battery`. Recomputes remaining ETAs mid-job |
| `get_next_room` | `reanchored_estimate` | Resolves which room is next from the reanchored estimate |
| `get_room_learning_estimates` | `vacuum_entity_id`, `map_id` | Per-room estimates independent of queue state |
| `get_learning_history_snapshot` | `vacuum_entity_id` | Optional: `room_slug`, `profile_key`, `status`, `used_for_learning`, `origin` (`external` \| `internal`), `limit`. Each recent-jobs entry carries the [run-record attribution fields](#run-record-attribution-fields) and the [job-summary detail fields](#job-summary-detail-fields) (`run_errors` / `recharge` / `room_detail`, all derived at read time) the Review card reads |
| `get_metrics_snapshot` | `vacuum_entity_id` | Optional: `room_slug`, `profile_key`, `status`, `used_for_learning` |
| `get_incomplete_run_log` | `vacuum_entity_id` | Last cancelled/failed/interrupted job. Returns null-equivalent `{}` when no log exists |
| `get_trouble_rooms_log` | `vacuum_entity_id` | Chronic trouble rooms. Returns null-equivalent `{}` when no log exists |
| `save_learning_snapshot` | `vacuum_entity_id`, `started_at`, `battery_start` | Auto-invoked at job end; not normally called directly by a client |
| `finalize_learning_job` | `vacuum_entity_id`, `battery_start`, `battery_end`, `started_at` | Auto-invoked when a job ends; fires `eufy_vacuum_run_incomplete` when rooms were missed. Not normally called directly (see the safety notes) |
| `rebuild_learning_stats` | `vacuum_entity_id` | |
| `exclude_learning_job` | `vacuum_entity_id`, `job_id` | Optional: `reason`, `rebuild_csv` |
| `restore_learning_job` | `vacuum_entity_id`, `job_id` | Optional: `rebuild_csv` |
| `set_learning_processing` | `vacuum_entity_id`, `enabled` | Box-level toggle for automatic learning processing |
| `process_pending_runs` | `vacuum_entity_id` | Process collected-but-unprocessed runs now |
| `record_estimate_accuracy` | `vacuum_entity_id` | Records an estimate-vs-actual accuracy sample |
| `retry_missed_rooms` | `vacuum_entity_id` | **response** `{started, reason}`. Starts a clean of the last run's missed rooms — the "retry" the `eufy_vacuum_run_incomplete` event offers |
| `get_external_pending_runs` | `vacuum_entity_id` | **response.** Pending app-started (external) runs awaiting attribution review |
| `confirm_external_run` | `vacuum_entity_id`, `pending_job_id` | **response.** Confirms an external run's room attribution → graduates it into the learned baselines |
| `discard_external_run` | `vacuum_entity_id`, `pending_job_id` | **response.** Discards a pending external run |

The external-run review flow (`get_external_pending_runs` / `confirm_external_run` / `discard_external_run` / `resegment_external_run`) is documented end-to-end in [28-external-run-ingestion](../28-external-run-ingestion.md).

##### Run-record attribution fields

The `get_learning_history_snapshot` recent-jobs list carries per-run **attribution** fields the Review card reads. They ride the 1.8.0 native-current-room attribution path (see [eufy-native-transition](../design/eufy-native-transition.md)); an index built before these keys existed self-heals on the next snapshot.

- `origin` — `"external"` (app-started, captured) or `null`/absent (dispatched by this integration). The `origin` filter is binary `external` \| `internal`; a dispatched run with no `origin` key still matches `internal`. Drives the card's **Origin** filter chip and an "External" origin badge.
- `has_attribution_disagreement` — bool. A dispatched run whose native current-room named a *different* room than the positional (segment K → queue room K) assignment; surfaced as the card **"Room Mismatch"** badge (the assignment is kept, **never** silently overridden).
- `cleaning_area_m2` — the run's cleaned floor area in canonical m² (the card's **"Area Cleaned"**), shown on external runs (single and multi-room). External records fall back to summing per-room `room_timings[].area_m2` when no job-level sensor read exists.
- `cleaning_area_sensor_m2` — the device's own run-total area (m²), the sanity **upper bound**.
- `area_over_attributed` — bool; the per-room attributed sum exceeded `cleaning_area_sensor_m2` beyond tolerance (a double-counting alarm).

##### Job-summary detail fields

Each recent-jobs entry also carries the error evidence and per-room detail the job-summary modal renders (CARD-3 / RF-DOCK). The `run_errors` / `recharge` / `room_detail` blocks are **derived from the archived record at read time, never stored** — so every historical job gets fault labels the moment an adapter's mapping ships or is fixed, and a record written before a rule change heals instead of staying frozen at the verdict it shipped with.

- `had_errors` (bool) + `error_count` (int) — the run hit N faults.
- `total_error_seconds` — passed through, **not defaulted**: the app-started ingest path deliberately omits it (no per-phase timings to derive it from). `None` means *unmeasured*; a client must not render it as 0.
- `run_errors` — the faults **named** (capped at 12 rows): `[{code, label_key, source, recovered, captured_at, room_id}]`. `code` is the raw vendor code (always present on every record ever written); `label_key` is the adapter-resolved i18n key (`fault.<brand>.<slug>`, `None` when the adapter has no label for that code — the client falls back to showing the raw code, honest and searchable); `source` ∈ `"dock"` \| `"robot"` \| `"unknown"` (unknown is a real answer, not a fallback to the majority class); `recovered` is true iff `recovered_at` was stamped — **recovery state only, never evidence that the fault ended the run**.
- `recharge` — `null` when no mid-job recharge is indicated (so a client can omit the row rather than render a confident 0), else `{observed: true, count, seconds, started_at, recovered_from_stale_record}`. Re-derived from the accumulators (`mid_job_recharge_count` / `recharge_seconds_accumulated`, OR-ed with the stored flag for the finalize-while-still-charging edge); `recovered_from_stale_record` marks a pre-RECHARGE-FLAG-1 record being corrected on read.
- `room_detail` — per-room rows joining the settings **as dispatched** (from the record's `resolved_rooms`, never the room's *current* profile) to what happened: `{room_id, slug, name, profile_key, settings: {clean_mode, fan_speed, clean_intensity, water_level, path_type, clean_passes, edge_mopping — only keys the run carried}, cleaning_seconds, cleaning_wall_seconds, area_m2, boundary, has_result}`. `cleaning_seconds` and `cleaning_wall_seconds` are BOTH carried (they disagree on 110 of 113 real timing entries — collapsing them silently picks a side); timing joins by `room_id` first, slug only for id-less legacy entries (slugs repeat across maps). A row with settings and `has_result: false` is normal — a queued room the run never reached leaves nothing to measure. Per-room battery deliberately does **not** ride these rows (it doesn't reconcile with the job total).

#### Errors

Both **response** services in the `eufy_vacuum` domain. Full error model: [23-error-tracker](../23-error-tracker.md); prefer the `binary_sensor.{object_id}_active_run_has_error` signal over parsing state strings.

| Service | Required fields | Notes |
|---|---|---|
| `get_recent_errors` | `vacuum_entity_id` | **response.** The recent-error ring for the vacuum |
| `acknowledge_error` | `vacuum_entity_id` | **response.** Clears the active-run error latch |

#### Dock (base station)

| Service | Required fields |
|---|---|
| `wash_mop` | `vacuum_entity_id`, `map_id` |
| `dry_mop` | `vacuum_entity_id`, `map_id` |
| `stop_dry_mop` | `vacuum_entity_id`, `map_id` |
| `empty_dust` | `vacuum_entity_id`, `map_id` |
| `reset_maintenance` | `vacuum_entity_id`, `component` (an adapter-declared maintenance-component id — Eufy: `filter` \| `side_brush` \| `rolling_brush` \| `mopping_cloth` \| `cleaning_tray` \| `swivel_wheel` \| `sensor`) |
| `set_maintenance_interval` | `vacuum_entity_id`, `component` (an adapter-declared maintenance-component id — Eufy: `filter` \| `side_brush` \| `rolling_brush` \| `mopping_cloth` \| `cleaning_tray` \| `swivel_wheel` \| `sensor`), `interval_hours` (> 0) |
| `set_dock_event_count` | `vacuum_entity_id`, `event_type` (`last_mop_wash` \| `last_dust_empty` \| `last_dry_start`), `count` (int ≥ 0) |
| `set_pause_timeout_settings` | `vacuum_entity_id`, `pause_timeout_minutes_default` |
| `battery_rebaseline` | `vacuum_entity_id` — rebaselines the battery-health proxy (see [12-battery-system](../12-battery-system.md)) |

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
| `set_run_profile_steps` | `vacuum_entity_id`, `map_id`, `profile_id`, `steps` | The run-profile step-editor primitive (rooms + charge/wait/zone stops in order) |
| `start_run_profile` | `vacuum_entity_id`, `map_id`, `profile_id` | **response.** Optional: `confirm_reduced_run`, `confirm_token`, `path_block_action` (`event_only` \| `pause_and_event` \| `cancel_and_event`), `pause_timeout_minutes_override`. Applies the profile, rebuilds the queue, and starts it through the protected start flow. Returns `{started, reason, message, confirm_token?, requires_confirmation?, profile_id, profile, applied_room_ids, missing_room_ids}` — same reduced-run confirmation handshake as `start_selected_rooms` (retry with `confirm_reduced_run: true` or the returned `confirm_token`) |

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

All `setup_*` services are **response** services (returning an `ActionResult` `{status, code, message, warnings, data, next_actions}` where relevant). See [15-setup-system](../15-setup-system.md).

| Service | Notes |
|---|---|
| `setup_get_status` | Returns vacuum list and map import state |
| `setup_add_vacuum` | `vacuum_entity_id` |
| `setup_import_active_map` | `vacuum_entity_id` |
| `setup_get_map_rooms` | `vacuum_entity_id`, `map_id` |
| `setup_save_rooms` | `vacuum_entity_id`, `map_id`, `enabled_room_ids`, `floor_types` |
| `setup_delete_map` | `vacuum_entity_id`, `map_id`; optional `confirmation_token` — required for any protected map. A **named** high-protection map needs a typed token matching the map's stored name (`requires_typed_confirmation`); an **unnamed** high-protection map and any elevated map need only a one-click confirm, any non-empty token (`requires_confirmation`). The card reads those two protection fields to choose the prompt. Returns an ActionResult `{status, code, message, warnings, data, next_actions}` — `status` ∈ `error` \| `already_done` \| `requires_confirmation` \| `blocked` \| `success`; `code` ∈ `typed_confirmation_required` \| `confirmation_mismatch` \| `confirmation_required` \| `map_deleted` \| `map_not_found`; the `requires_typed_confirmation`/`requires_confirmation` protection fields ride inside `data.protection`. |
| `setup_set_panel_title` | `vacuum_entity_id`; optional `title` (blank reverts to the default). Renames the vacuum's sidebar panel and re-registers it live (refresh the browser to repaint the sidebar) |
| `setup_set_map_camera` | `vacuum_entity_id`; optional `entity_id` (blank clears the override → falls back to the adapter's `live_map_image_entity_pattern`). Sets the per-vacuum live-map image/camera override the dashboard snapshot prefers over the pattern (see [Live-map backdrop read model](#live-map-backdrop-read-model)) |
| `setup_reject_rooms` | `vacuum_entity_id`, `room_ids`; optional `map_id`. Omitted resolves server-side to the vacuum's **active** map (`_rejection_map_id` calls `manager.resolve_active_map_id()`), so the ordinary multi-map case — an active map that resolves — succeeds against it, not a refusal. The "2+ maps, refuse rather than guess" path (`setup/drift.py` `_resolve_rejection_map`) only fires when that resolution itself comes back empty (no resolver, or it can't say) — suppress phantom/rejected rooms from the discovered set |
| `setup_unreject_rooms` | `vacuum_entity_id`, `room_ids`; optional `map_id` (same active-map-resolves / refuse-only-when-unresolvable rule as `setup_reject_rooms`) — undo a rejection so the room can be discovered and configured again (A4-SETUP-6's escape hatch; without it a rejection was one-way short of hand-editing `.storage`). Clears both the per-map rejection list and the legacy flat (vacuum-global) one. The room does **not** reappear immediately — it resurfaces on the next discovery pass that sees it, through the normal confirmation cadence |
| `setup_force_remove_room` | `vacuum_entity_id`, `map_id`, `room_id` — force-remove a stuck room from the managed set |

#### Adapter config (adapter-authoring surface)

Five services drive the UI-based adapter-config flow for future multi-brand setups — an **authoring/diagnostic surface**, not something a normal client needs (the shipped card has no call sites for any of them): `save_adapter_config` (`vacuum_entity_id`, `config` — validated in full against `ADAPTER_CONFIG_SCHEMA`, the same walk the adapter contract tests run; the `source` field is always forced to `"config"` server-side, before validation, never trusted from the caller), `delete_adapter_config`, `get_adapter_config`, `discover_adapter_entities` (scan for entities matching adapter roles), and `observe_entity_states` (read entity states for vocabulary mapping). `get_vacuum_capabilities` (above) is registered alongside them but is part of the normal client contract.

#### Mapping / map image

| Service | Required fields | Notes |
|---|---|---|
| `upload_map_image` | `vacuum_entity_id`, `map_id`, `image_base64` | Optional: `variant`, `layout_id`, `image_width`, `image_height`. The `variant` validator accepts `default` \| `dark` \| `light` \| `custom` \| `custom_*` (default `default`). `dark`/`light`/`default` are segmenter inputs. `custom` and the per-layout `custom_<layout_id>` variants are manual-authoring backdrops and are **never auto-segmented** — `analyze_map_image` only probes `dark`/`default`/`light`. Passing `layout_id` forces `variant` to `custom_<layout_id>` and repoints that layout's `backdrop_variant` (returns `{saved: false, reason: "layout_not_found"}` if the layout doesn't exist). The stored variant's `image_width`/`image_height` are the pixel space `set_custom_segments` rasterises against. **response** |
| `delete_map_image` | `vacuum_entity_id`, `map_id` | Optional: `variant` (same enum). Removes one stored variant; safe to repeat. **response** |
| `analyze_map_image` | `vacuum_entity_id`, `map_id` | Runs the segmenter on the `dark`/`default` (and assist `light`) variants; caches `image_segments`. **response** |
| `get_map_segments` | `vacuum_entity_id`, `map_id` | Returns the active segment set plus overlays. Response carries `segmentation_mode`; in `custom` mode it serves the **active layout's** `custom_segments` over its `custom_<layout_id>` backdrop. Also returns `custom_layouts` (list) + `active_custom_layout_id` + `segment_room_links` (see [Map segments read model](#map-segments-read-model-get_map_segments-response) / [Minimum viable polling loop](#minimum-viable-polling-loop)), plus the map's `saved_zones` list (see [Saved zones](#saved-zones-response)). **response** |
| `set_segmentation_mode` | `vacuum_entity_id`, `map_id`, `mode` | `mode` ∈ {`cv`, `custom`}. **Flips a per-map flag only — never re-runs the segmenter.** Both the CV base (`image_segments`) and every custom layout persist; the toggle is a pointer flip, so `cv → custom → cv` is lossless. Flipping to `custom` with no active layout soft-selects the first existing layout. **response** |
| `set_custom_segments` | `vacuum_entity_id`, `map_id`, `segments` | **Replace-all** write of manually-authored segments **into the active custom layout** (auto-creating a default layout if none exists). `segments = [{id?, primitives: [...]}]` (extra keys allowed). A primitive is `{type: rect\|circle\|polygon, op?: add\|subtract, ...pct geom 0-100}`. Optional `backdrop_width`/`backdrop_height` set the pixel space when authoring over a live-image-backed layout (no uploaded backdrop). Each segment is rasterised server-side (`segment_primitives.rasterize_primitives` → `mask_to_polygon`, the same tracer CV uses) into one polygon, scaled to the active layout's backdrop pixel dims. Requires that backdrop (returns `{saved: false, reason: "no_custom_backdrop"}` without it). Degenerate segments are dropped. **response** |
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
| `acknowledge_map_frame` | `vacuum_entity_id` | Re-enables map drawing after a map switch (clears the post-switch coordinate-frame gate). **response** |
| `set_furnished_art_placement` | `vacuum_entity_id`, `map_id` | Furnished digital-twin art placement — see [furnished-render](furnished-render.md). **response** |
| `set_furnished_render_mode` | `vacuum_entity_id`, `map_id` | Toggle furnished-render mode for a custom layout. **response** |
| `set_room_viewport` | `vacuum_entity_id`, `map_id`, `room_id` | Per-room viewport for the furnished render. **response** |

#### Live-map backdrop read model

For live-image brands (Roborock today), the Map view's backdrop is an HA `image` entity exposed by the brand's core integration — not a stored variant or CV/custom geometry. The contract for it is carried on the **`get_dashboard_snapshot`** response, which also emits two extra fields: `live_map_image_entity` (the resolved image entity ID, or `null`) and `live_map_rotation` (the per-map stored display rotation, normalised to one of `0`/`90`/`180`/`270` — surfaced even at `0` so the card always has a value).

The resolution is brand-owned at the seam: the adapter declares `mapping.live_map_image_entity_pattern` (e.g. Roborock's `image.{object_id}_{map_slug}`), core fills the `{object_id}` / `{map_slug}` placeholders, **existence-checks** the candidate against `hass.states`, and surfaces it only if it exists. Absent (Eufy / older backends) → `live_map_image_entity` is `null` and there is no live backdrop. The card renders the resolved image as the Map-view backdrop and applies `live_map_rotation` to the **whole content layer** (image, polygons, labels, and mascot together), so a 90° step never rotates the CV/custom polygons independently of their backdrop.

**Override-first resolution.** `get_dashboard_snapshot` now resolves the entity **override-first**: a per-vacuum override stored on the vacuum record (`data["vacuums"][vid]["live_map_image_entity"]`, written by the **`setup_set_map_camera`** service from the Setup tab's "Live map camera" picker) wins over the adapter pattern, and is itself existence-checked — a stale/renamed override that no longer resolves falls through to the pattern. The resolver is **domain-agnostic**: either branch may yield an `image.` or a `camera.` entity. The Eufy adapter now ships a best-effort `live_map_image_entity_pattern` of `camera.{object_id}_map`, so a default-named install running jeppesens eufy-clean (mainline v1.11.0+, where the vacuum entity and eufy-clean's `camera.<device>_map` share the device slug) auto-resolves **without** picking; the picker is the override for when the vacuum entity was renamed. Existence-gating keeps older or plain Eufy installs (no live-map camera) at `live_map_image_entity = null`.

**Cache-busting a `camera.` backdrop.** An `image.` entity rotates its `entity_picture` token every frame (it self-busts), but a `camera.` entity's token is stable — so a naïve `<img>` would never refetch. `src/state/map.js` `_liveMapImageUrl` appends the live entity's `last_updated` as a query param, forcing the browser to refetch each ~2 s frame. `mapImageUrl` (also in `state/map.js`) short-circuits to this live URL whenever `isLiveBackdropActive` reports the active scope is live-pinned (see below), so the live image always wins over any uploaded backdrop.

**"Live map" as a selectable source.** Beyond being the brand backdrop, the live image is selectable in Map Configuration: `_renderSegmentationToggle` (`src/renderers/map.js`) adds a **"Live map"** chip — shown only when a live entity is available — that selects/creates a custom layout marked `backdrop_source: "live"` (the new `backdrop_source` param on `create_custom_layout`). A live-pinned layout always renders the live image and ignores its `custom_<layout_id>` backdrop; you then **draw + link** rooms over the live map with the existing composer, and the same `segment_room_links` / tap-select machinery makes them selectable — unchanged from any other custom layout. **Caveat:** compose against a fully-mapped (stable) map — polygons store as 0-100% of the image, so if the map footprint changes (e.g. it grows during a first mapping run, shifting the aspect ratio) the drawn rooms drift.

**Room-label visibility toggle.** A per-vacuum map-toolbar toggle gates VA's own `.evcc-map-label` render (`mapRoomLabelsEnabled`, persisted to localStorage `evcc_map_labels_<vac>`, default **on**). eufy-clean's live map bakes in its own room labels, so VA's would stack into noise on top of them — flip the toggle off on the live map, leave it on for plain CV/custom maps.

---

### HA Events

Subscribe via `hass.connection.subscribeEvents(callback, eventType)`. All ten `eufy_vacuum_*` events fire on the HA event bus. The exact payloads + fire conditions are owned by [02-ha-integration §7](../02-ha-integration.md) and [06-job-lifecycle §10](../06-job-lifecycle.md) — the field lists below are the client-facing summary.

| Event type | Payload fields | When it fires |
|---|---|---|
| `eufy_vacuum_job_progress_tick` | `vacuum_entity_id`, `map_id` | **Fixed 5-second backend heartbeat while any job is `started`/`paused`.** The intended live-job refresh trigger: on each tick re-read `get_job_progress_snapshot` (the backend already ran it server-side this tick — see [Building a Different UI](#minimum-viable-polling-loop)) |
| `eufy_vacuum_job_finished` | **Two shapes** (see 06 §10): the lifecycle/reaper form adds `duration_minutes` + `actual_cleaning_minutes`; the `finalize_learning_job` form omits both (`reason_detail = lifecycle_message`). Common: `vacuum_entity_id`, `map_id`, `job_id`, `outcome_status`, room counts | Job reaches a terminal state |
| `eufy_vacuum_room_started` | `vacuum_entity_id`, `map_id`, `room_id` (**str**), `room_name`, `job_id`, `started_at`, `source` (`job_start`\|`counter_plateau`\|`timing_rollover`\|`native_signal`), `completed_room_ids` | Robot enters a room |
| `eufy_vacuum_room_finished` | `vacuum_entity_id`, `map_id`, `room_id` (**str**), `room_name`, `job_id`, `completed_at`, `source`, `actual_duration_minutes` (2 dp, or `None`), `confidence` (4 dp) — **the `native_signal` variant omits `confidence` entirely**, `completed_room_ids` | Robot finishes a room |
| `eufy_vacuum_room_completed` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name`, `confidence`, `duration_seconds`, `entered_at` | **Informational** dwell event on native-position brands (`mapping/tracker.py`); not a queue driver |
| `eufy_vacuum_path_blocked` | `vacuum_entity_id`, `map_id`, `room_id`, `room_name` (+ the block report fields) | Blockage detected during cleaning |
| `eufy_vacuum_stall_detected` | `vacuum_entity_id`, `map_id`, `room_id` (**int**), `room_name`, `elapsed_minutes`, `expected_minutes`, `stall_ratio` | Robot has been in a room >= 2x its learned threshold with `awaiting_bounds_exit = true`. Fires at most once per room per job |
| `eufy_vacuum_room_skipped` | `vacuum_entity_id`, `map_id`, `job_id`, `room_id` (**int**), `room_name`, `completed_room_ids` (list of int) | Live tracking advanced past a queued room that was never completed. Deduped once per room per job. Largely inert for Eufy's sequential counter; meaningful on brands whose live position can leapfrog the queue order |
| `eufy_vacuum_run_incomplete` | `vacuum_entity_id`, `job_id`, `outcome_status` (`completed`\|`cancelled`\|`failed`\|`interrupted`), `missed_room_ids` (list of int), `missed_rooms` (list of `{room_id, name}`) | Fired by `finalize_learning_job` when a cancelled/failed/interrupted job left uncleaned rooms |
| `eufy_vacuum_external_run_pending` | `vacuum_entity_id`, `map_id`, `record_path`, `segment_count`, `detection_ts` | An app-started (external) run was detected + captured — the Learning Review / external-run-confirm UI keys off this to prompt attribution ([28](../28-external-run-ingestion.md)) |

> **`room_id` type is inconsistent across events**: a **string** in `room_started`/`room_finished`, an **int** in `stall_detected`/`room_skipped` (per 06 §10). A client matching rooms by strict equality across events must coerce.

---

### HA Entities the UI reads

Entity IDs are derived from the vacuum's `object_id` (the part after the dot in `vacuum.alfred` → `alfred`).

#### Vacuum entity

The primary vacuum entity (`vacuum.{object_id}`) is the core state source. It is **provided by the brand integration** (jeppesens eufy-clean / roborock), not this one — so `state` values are brand / HA-`VacuumActivity`-defined and `battery_level` may be deprecated on newer HA vacuum entities:

- `state` — `cleaning`, `docked`, `returning`, `paused`, `error`, `idle`
- `attributes.battery_level` — integer 0–100
- `attributes.friendly_name` — display name

#### Switch entities (room enabled/disabled)

The integration creates one switch per room per map: `switch.{object_id}_{map_slug}_{room_slug}`. The switch's `on`/`off` state is the room's enabled flag. The **29** `extra_state_attributes` are the room's full transport (the same base rides the room **number** entity too):

```
vacuum_entity_id, map_id, room_id, room_name, slug, order, enabled,
profile_name, floor_type, carpet, color, is_dock_room, grants_access_to, rules, integration,
clean_mode, fan_speed, water_level, clean_intensity, clean_passes, edge_mopping,   # profile-RESOLVED effective values
last_cleaned_at, last_vacuumed_at, last_mopped_at, last_job_mode,
clean_mode_options, fan_speed_options, water_level_options, clean_intensity_options  # each [{value, label}]
```

`clean_mode` / `fan_speed` / `water_level` / `clean_intensity` / `clean_passes` / `edge_mopping` are **profile-resolved effective** settings (from `get_effective_room_details`), not the raw stored room fields. The four `*_options` lists are the picker vocab (canonical `value` + English `label` — see [Canonical values vs localized display](#canonical-values-vs-localized-display)); they ride the entity precisely so a client with no service access (the standalone room card) can build the mode/speed/water/intensity dropdowns.

The card discovers room switches by scanning `hass.states` for entities whose attributes contain `vacuum_entity_id` matching the configured vacuum. It does **not** rely on a fixed naming pattern — recommended for all this integration's entities, since entity_id derivation is not guaranteed stable.

#### Number entities (room order)

The integration creates one number entity per room per map: `number.{object_id}_{map_slug}_{room_slug}_order`. The integer state is the room's 1-based sort position. Write by calling `number.set_value`.

#### Sensor entities

| Entity ID pattern | `state` | Key `attributes` |
|---|---|---|
| `sensor.{object_id}_theme_state` | active theme **name** (or `none`) | `active_theme_id`, `draft_dirty`, `editor_mode`, `working_draft`, `library_count`, `library_summary` (`[{id, theme_id, name}]`), `default_theme_id`, `vacuum_entity_id` — **no** active-theme token map (fetch full tokens via `get_theme_library`) |
| `sensor.{object_id}_available_profiles` | Profile count | Available profile definitions |
| `sensor.{object_id}_dock_events` | Event count | Dock event history |
| `sensor.{object_id}_map_overlays` | current-room name | per-room bbox/area, `robot_anchor` / `dock_anchor` / `robot_heading` (**the first-party robot-position source**), `no_go`/`no_mop`/`walls`/`zones`/`obstacles`, `visibility` |
| `sensor.{object_id}_{component}_remaining` | Hours remaining | Per-component maintenance sensor (one per maintenance component) |
| `binary_sensor.{object_id}_active_run_has_error` | `on`/`off` | The dedicated error signal — prefer over parsing vacuum state strings |

There is **no first-party `active_map` sensor and no `robot_position_*_raw` sensor** (contrary to older guidance). The active-map id is resolved server-side from the adapter's brand entity (role `active_map`) — read it via `get_dashboard_snapshot` / `get_vacuum_maps`, not a fixed `sensor.{object_id}_active_map`. Robot position is the `map_overlays` sensor's `robot_anchor`/`robot_heading` above. The integration also registers onboarding, active-job (lifecycle), error, and six battery-health sensors — see [12-battery-system](../12-battery-system.md) / [23-error-tracker](../23-error-tracker.md).

Per-room sensors are also registered at setup:
- `sensor.{object_id}_{map_slug}_{room_slug}_cleaning_history` — room-level cleaning history
- `sensor.{object_id}_{map_slug}_{room_slug}_rule_status` — room rule evaluation status

#### Theme sensor attributes (detailed)

The `sensor.{object_id}_theme_state` entity carries the theme *draft + library index* — its `state` is the active theme **name** (or `none`). The **full** active-theme token/color/alpha maps are NOT on the sensor; fetch them via `get_theme_library()`. Attributes:

- `active_theme_id` — the currently applied theme id
- `draft_dirty` — boolean; true when the working draft differs from the saved theme
- `editor_mode` — the editor state (`live` / …)
- `working_draft` — the `{tokens, colors, alpha}` overrides being edited (this IS on the sensor)
- `library_count` + `library_summary` — `[{id, theme_id, name}]` (names only, no tokens)
- `default_theme_id`
- `vacuum_entity_id` — confirms this sensor belongs to a specific vacuum

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

### Canonical values vs localized display

The backend is the source of **canonical values**; the frontend owns **display text**. A replacement client must round-trip the canonical tokens unchanged and localize them itself.

- **Canonical wire enums** (send back verbatim; localize on the client): `clean_mode` ∈ `vacuum` / `mop` / `vacuum_mop`; `clean_intensity` ∈ `Quick` / `Narrow` / `Deep` (legacy `Standard` / `Normal` are dead → normalized to `Quick`); `fan_speed` ∈ `Max` / `Boost` / `Standard` / `Quiet`; `water_level` ∈ `Off` / `Low` / `Medium` / `High`; `floor_type` ∈ `hardwood` / `laminate` / `tile` / `marble` / `granite` / `concrete` / `carpet_low_pile` / `carpet_high_pile`; `room_id` (int); active-job `status` ∈ `idle` / `started` / `paused` / `completed`; the `get_start_status` `reason` enum ([06 §1](../06-job-lifecycle.md)); `outcome_status` ∈ `completed` / `cancelled` / `failed` / `interrupted`. The exact per-brand option lists ride the **switch entity** as `clean_mode_options` / `fan_speed_options` / `water_level_options` / `clean_intensity_options`, each `[{value, label}]` (canonical `value` + English `label`).
- **Server-baked ENGLISH convenience strings** (NOT localized — do not render as-is in a non-English UI): every `*_label` (`status_label`, `reason_label`) and `*_summary` (`status_summary`, `attention_summary`) — the backend title-cases English via `_display_label`. Localize from the canonical token, not from these.
- **User free-text** (pass through as-is): `room_name`, theme `name`, saved-zone `name`.

Ownership: the backend does **not** localize. The frontend owns all display text and fallback labels; the shipped card resolves via `tVocab(field, value)`, which falls back to the backend's English label for unkeyed values — see [i18n-system.md](i18n-system.md).

### Capability flags → behavior

There are **two distinct capability surfaces** — keep them separate.

**1. Payload-gating hardware flags** — from `get_vacuum_capabilities` (persisted in `data["capabilities"]`, [03 §1](../03-data-model.md)). They gate which per-room fields are sent in a clean payload ([03 §4](../03-data-model.md)):

| Flag | Gates |
|---|---|
| `supports_mop_features` | mop-mode availability per room |
| `supports_water_control` | the `water_level` field |
| `supports_path_control` | the `path_type` field |
| `supports_edge_mopping` | the `edge_mopping` field |
| `supports_passes` | the `clean_passes` field |

**2. Editor / UI-shaping hints** — ride the **`get_dashboard_snapshot`** response; they show/hide/shape UI:

| Flag | Enables / disables |
|---|---|
| `supports_base_station` | the Base Station tab (hidden when false) |
| `supports_zone_clean` + `zone_max` | the ad-hoc zone-draw control + per-clean zone cap |
| `zone_bounds` | per-**zone** size limits, so the draw can stop at the brand limit instead of the clean silently refusing at dispatch (which is still where they're enforced). The two brands express the limit in different units, so the dict carries whichever keys the brand declares (floats): `min_side_m`/`max_side_m` (Eufy — side length in metres) or `min_area_m2`/`max_area_m2` (Roborock — area in m²); an absent key = no declared limit |
| `supports_water_control` | whether the brand's mop is programmatically settable — gates the room editor's water-level picker + `clean_mode` picker vs the read-only observe-only-tank indicator. **Not a fixed per-brand fact**: Roborock is genuinely per-model (S6 `mop_settable=False`, S7+ `True`, from the model profile); the Eufy value is **install-dependent** — derived from `detect_capabilities()`'s live entity-surface probe (an adapter `capability_hint` can override it, but nothing does today), so it can read either way depending on what's actually installed. Declared per-adapter (`_caps_cfg`), default true when absent (older-backend safe) |
| `supports_edge_mopping` | **Narrower than it sounds — does NOT hide the edge-mopping toggle.** The room editor's ON/OFF chips (`state/room-editor.js` `showEdgeMopping()`) gate only on carpet + mop-mode and never read this flag, so it still renders even on a brand declaring `false`. Its one real consumer is the **profile-summary subtitle** in the Metrics view (`renderers/metrics.js`, via `state/learning.js supportsEdgeMopping()`): it suppresses the "edge mopping" note on a profile chip when false. Roborock declares this `false` brand-wide **by deliberate design** (a hardcoded per-brand literal, not per-model) and the codebase explicitly rejected gating the card on it — see `adapters/roborock/vocabulary.py`'s "WHAT WAS DELIBERATELY NOT DONE" note: doing so would hide the control on every Roborock, including models that can edge-mop. Default true when absent |
| `honors_clean_order` | the strict-order toggle (no-op on path-optimizing brands) |
| `passes_is_global` | per-run vs per-room passes note |
| `max_clean_passes` | the passes-chip ceiling (Eufy 2, Roborock 3) |
| `supports_room_profiles` | the per-room profiles section (hidden when false) |
| `supports_map_bounds` | derived brand signal (no live consumer today) |
| `supports_va_render` | the "VA-rendered map" backdrop-source option |
| `cv_available` / `cv_missing` | the Auto (CV) segmentation chip (disabled + explained when libs absent) |
| `mop_active` | live tank-driven mop state (`null` on brands without a tank sensor) |
| `scene_select` | the vendor-app "Scenes" run-launcher (`null` → hidden) |
| `adapter_vocabulary` | the room-editor dropdown option lists |

A client hides a feature whose flag is false/absent rather than dead-ending on it.

---

## Building a Different UI — What You Need

This section specifies the minimum required for any UI (React app, Vue SPA, native app, CLI tool, etc.) that wants to drive a eufy_vacuum installation.

### Minimum viable polling loop

The backend **does push** a live-job heartbeat: `eufy_vacuum_job_progress_tick` fires every 5 s while a job runs, and the backend runs `get_job_progress_snapshot` server-side on the same tick (which is also what fires the room-rollover / stall / skip events — so they work even when nobody has the panel open). Subscribe to the tick and re-read the snapshot; everything else is read on HA state pushes / tab activation. The 500/800 ms figures below are the **shipped card's** debounce choices, not a contract requirement.

```
On eufy_vacuum_job_progress_tick (5 s, while a job runs) — the live-job refresh signal:
  - Call get_job_progress_snapshot(vacuum_entity_id)
  - When it returns awaiting_bounds_exit == true, keep short-polling (~5 s) until the room rolls over

Every time hass.states updates (subscribe via HA WebSocket connection event):
  - Read vacuum entity state + battery from hass.states
  - Read all switch entities whose attributes.vacuum_entity_id == your vacuum
  - Read all number entities whose attributes.vacuum_entity_id == your vacuum
  - Read sensor.{object_id}_theme_state attributes

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
  - (live-image brands) Call get_map_render_data(vacuum_entity_id) once — cached by its returned version; {present:false} => no VA render
  - (live-pose brands) Poll get_map_live_pose(vacuum_entity_id) on the live cadence for the moving robot/dock overlay; {present:false} => no live pose
```

`get_map_segments` returns `segmentation_mode`, `active_custom_layout_id`, and the `custom_layouts` list. The card reads these to select the active segment store and backdrop variant: in `cv` mode it shows `image_segments` over the `dark`/`default`/`light` backdrop (rendered `object-fit: contain`); in `custom` mode it shows the **active layout's** `custom_segments` over that layout's `custom_<layout_id>` backdrop (rendered `object-fit: fill`), and renders the `custom_layouts` list as the layout-picker chips. The same response also rebuilds the composer draft once per `${map_id}:${active_custom_layout_id}` (see [custom-segment-composer.md](custom-segment-composer.md)).

### Event subscriptions needed for real-time updates

Subscribe to these for any UI that tracks live jobs:

| Event | Why |
|---|---|
| `eufy_vacuum_job_progress_tick` | **The refresh heartbeat** — re-read `get_job_progress_snapshot` on each tick |
| `eufy_vacuum_room_started` | Update "currently cleaning" indicator |
| `eufy_vacuum_room_finished` | Update completed rooms list; trigger reanchor call |
| `eufy_vacuum_job_finished` | Clear active job UI; show summary |
| `eufy_vacuum_path_blocked` | Surface a blockage warning |
| `eufy_vacuum_stall_detected` | Show stall warning banner |
| `eufy_vacuum_room_skipped` | Flag a queued room the run advanced past without cleaning |
| `eufy_vacuum_run_incomplete` | Show missed rooms prompt; offer retry action |
| `eufy_vacuum_external_run_pending` | Prompt attribution for a detected app-started run (Review card) |

### Entity reads needed for room state

For each room in the active map you need:

1. **Switch entity** for enabled/disabled state and all room settings (name, mode, fan speed, etc.). Discover by scanning `hass.states` for entities where `state.attributes.vacuum_entity_id === yourVacuumEntityId` and the entity ID starts with `switch.`.
2. **Number entity** for sort order. Discover by scanning `hass.states` for entities where `state.attributes.vacuum_entity_id === yourVacuumEntityId` and the entity ID starts with `number.` and ends with `_order`.

The active map ID comes from `get_dashboard_snapshot` / `get_vacuum_maps` — there is **no** first-party `sensor.{object_id}_active_map` (the adapter resolves it from the brand's own entity).

### Cache invalidation & degrading gracefully

- **Refetch `get_map_segments` after any mutating map-config call** (`set_custom_segments`, `set_segment_room_link`, `create_custom_layout`, `set_segmentation_mode`, `adjust_map_segment`, …). The response is derived at read time, so edits aren't visible until you re-pull.
- A **`camera.` live backdrop** has a stable `entity_picture` token — append the entity's `last_updated` as a query param to force each frame to refetch (an `image.` entity self-busts).
- **Degrade on absent data**: `get_map_render_data` / `get_map_live_pose` return `{present: false}`; `live_map_image_entity` is `null` when no live backdrop resolves; a false/absent capability flag means hide that feature; `get_*_log` services return `{}` when empty. Hide or fall back — never dead-end.

### Service call safety notes

**Safe to call from any UI without side effects:**

- All `get_*` services (read-only query services)
- `get_theme_library` (read-only)
- `run_learning_estimate` (read-only compute, does not mutate stored state)
- `reanchor_learning_timeline`, `get_next_room` (pure compute)

**Has side effects — understand before calling:**

- `start_selected_rooms` — starts the vacuum. Do not call without confirming `get_start_status` returns non-blocked, and call with `returnResponse = true` (it is a response service): a refused start returns `{started: false, reason, message}`; WITHOUT the response payload a refused start is indistinguishable from a started one.
- `start_zone_clean` — dispatches an ad-hoc free-form zone clean (rectangles drawn on the live map) on `supports_zone_clean` providers. Untracked — it carries no room ids and never touches the job/queue/learning store, so there is no tracked active job to pause/resume/cancel afterward — but it **refuses** (`{success: false, reason: "job_in_progress", start_status_reason}` — note: no `started` key, a different shape from `start_selected_rooms`'s refusal) while a job is already in flight rather than stacking a second dispatch.
- `clear_queue` — empties the pending run queue only; does **not** disable rooms (the card UI disables rooms as a separate composite action before calling it).
- `finalize_learning_job` — fires `eufy_vacuum_run_incomplete` if rooms were missed. Call only when a job ends.
- `setup_delete_map` — destroys a map and all its room data. A protected map needs a `confirmation_token`: a **named** high-protection map needs a typed token matching the map name; an **unnamed** high-protection map and any elevated map need only a one-click confirm (any non-empty token).
- `wash_mop`, `dry_mop`, `empty_dust` — physically operate dock hardware.
- `update_room_fields` — null optional fields (e.g. `water_level`) must be omitted, not sent as null. HA schema validation will reject them.
- `apply_run_profile` — overwrites current room selection and settings with saved profile values.
- `revert_draft` — discards unsaved theme editor changes.

---

## Render-data shapes

The **map render-DATA** a UI draws the map from — the segment geometry (`polygon_pct` per segment), the per-segment `room_id` links, `room_names`, and the live robot/dock **pose** — is **not defined in this doc**; it is normalised by the backend map source. (The **dashboard snapshot** read model, by contrast, IS a frontend read model — its shape is the `get_dashboard_snapshot` row above plus [05 §6](../05-core-manager.md#6-direct-responsibilities), not deferred to the map docs.) This doc records the *services* that fetch the map data (`get_map_segments`, `get_map_render_data`, `get_map_live_pose`); the authoritative map-shape definitions live in:

- [map source coordinator](../31-map-source-coordinator.md) — how the map data sources are selected, coordinated, and cached per brand.
- [map-state-source](../design/map-state-source.md) — the canonical map-state shape (raster + geometry + `room_names` + pose) the coordinator produces.

This stub is the anchor for that topic from the frontend side; expand it here only if a frontend-specific view of the render-data shapes is later needed. For the card-side render path that *consumes* these, see [map-render-layers.md](map-render-layers.md).
