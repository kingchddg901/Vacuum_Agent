# Services Reference

All services are registered under the `eufy_vacuum` domain. Call them as `eufy_vacuum.<service_name>`.

Services that `supports_response` return a data payload you can capture with `response_variable` in a script or automation action. Services that do not support response run fire-and-forget.

Most services require at least `vacuum_entity_id`. Services that operate on a specific map also accept `map_id`, but it is **optional everywhere** — omit it and the integration auto-resolves to the vacuum's current active map by reading the adapter's declared `entities.active_map` entity. Pass `map_id` explicitly only when you need to target a non-active map (e.g. inspecting state on a stored secondary map).

Per-service tables below mark `map_id` as `No (auto)` to indicate this. Adapters that do not declare an active-map entity require the caller to pass `map_id` explicitly — the manager surfaces a clear error in that case rather than silently picking a wrong map.

---

## Service Index

Every `eufy_vacuum.*` service registered by the integration. Services
with full details in this doc link to their section below; services
whose deep reference lives in a subsystem doc link out.

### Core services (full reference below)

**Job control** — [Job Control](#job-control)
`start_selected_rooms` · `pause_active_job` · `resume_active_job` · `cancel_active_job` · `start_run_profile` · `get_start_status` · `clear_active_job` · `get_active_job` · `get_job_progress_snapshot` · `get_job_control_state`

**Queue and payload** — [Queue Management](#queue-management) (and similar sections)
`build_queue` · `build_room_payload` · `get_queue_state` · `get_payload_state` · `clear_queue`

**Lifecycle and dashboard**
`get_lifecycle_state` · `get_dashboard_snapshot` · `get_pause_timeout_settings` · `set_pause_timeout_settings` · `get_upkeep_snapshot`

**Room and profile management**
`get_room_profiles` · `save_user_room_profile` · `overwrite_room_profile` · `save_room_profile_from_room` · `overwrite_room_profile_from_room` · `rename_room_profile` · `delete_room_profile` · `apply_room_profile` · `update_room_fields` · `get_room_access_editor` · `get_access_graph_health` · `get_saved_run_profiles` · `save_run_profile` · `apply_run_profile` · `overwrite_run_profile` · `rename_run_profile` · `delete_run_profile`

**Room and map discovery**
`discover_rooms` · `save_managed_rooms` · `get_vacuum_maps`

**Dock actions** — [Dock Actions](#dock-actions)
`wash_mop` · `dry_mop` · `stop_dry_mop` · `empty_dust` · `get_dock_action_status` · `set_dock_event_count`

**Maintenance and errors**
`reset_maintenance` · `set_maintenance_interval` · `acknowledge_error` · `get_recent_errors`

**Setup (card-level Eufy onboarding — refactor candidate, see [porting-guide.md §9](../contributing/porting-guide.md#9-what-still-might-require-framework-work))**
`setup_get_status` · `setup_add_vacuum` · `setup_import_active_map` · `setup_get_map_rooms` · `setup_save_rooms` · `setup_delete_map` · `setup_reject_rooms` · `setup_force_remove_room`

**Backend, battery, and diagnostics**
`refresh_backend` · `rebuild_active_map` · `clear_runtime_state` · `battery_rebaseline`

### Subsystem services (full reference in subsystem docs)

**Learning** — full table in [learning-system.md §11](../dev/learning-system.md#11-services)
`save_learning_snapshot` · `finalize_learning_job` · `rebuild_learning_stats` · `run_learning_estimate` · `record_estimate_accuracy` · `reanchor_learning_timeline` · `get_next_room` · `get_room_learning_estimates` · `get_learning_history_snapshot` · `get_metrics_snapshot` · `get_incomplete_run_log` · `get_trouble_rooms_log` · `retry_missed_rooms` · `exclude_learning_job` · `restore_learning_job`

**Theme** — full table in [theme-system.md §10](../dev/theme-system.md#10-services)
`get_theme_library` · `save_theme_as_new` · `overwrite_theme` · `rename_theme` · `delete_theme` · `set_active_theme` · `update_working_draft` · `revert_draft` · `export_theme` · `import_theme`

**Mapping** — full table in [mapping-system.md §10](../dev/mapping-system.md#10-services)
`save_map_image` · `upload_map_image` · `analyze_map_image` · `set_companion_anchor` · `start_room_boundary_trace` · `close_room_boundary` · `cancel_room_boundary_trace` · `get_room_bounds_snapshot` · `clear_room_bounds` · `start_trace_capture` · `stop_trace_capture` · `cancel_trace_capture` · `review_trace_run` · `append_mapping_trace_evidence` · `exclude_room_job_bounds` · `restore_room_job_bounds` · `rebuild_room_bounds_from_archive` · `set_dock_anchor` · `set_dock_room` · `get_image_segment_suggestions` · `translate_image_segment` · `adjust_map_segment` · `set_segment_room_link` · `get_map_segments` · `get_mapping_state` · `get_mapping_package` · `save_mapping_package`

**Adapter config** — full table in [adapter-config-reference.md §21](../dev/adapter-config-reference.md#21-services-that-read-and-write-adapter-configs)
`save_adapter_config` · `delete_adapter_config` · `get_adapter_config` · `discover_adapter_entities` · `observe_entity_states` · `get_vacuum_capabilities`

---

## Job Control

These services start, pause, resume, and cancel the integration-managed active job.

### `start_selected_rooms`

Sends the resolved cleaning payload to the vacuum and starts the job. Honors room blockers, access-graph dependencies, modifier rules, and reduced-run confirmation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `confirm_reduced_run` | No | Set `true` to allow a reduced run (some rooms blocked) to proceed without a separate confirmation step. |
| `confirm_token` | No | Retry token returned by a prior `confirmation_required` response. Alternative to `confirm_reduced_run`. |
| `path_block_action` | No | What to do if blocker rules change mid-run and remaining rooms become unreachable. Values: `event_only`, `pause_and_event`, `cancel_and_event`. |
| `pause_timeout_minutes_override` | No | Override the default pause timeout for this job only. Set to `0` to disable auto-cancel for this run. |

If blockers or access rules would reduce the room list, the service returns `confirmation_required: true` with a `confirm_token` unless you pass `confirm_reduced_run: true` or a valid token.

### `pause_active_job`

Pauses the vacuum and marks the integration-owned active job as paused.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `resume_active_job`

Resumes the vacuum and the paused job.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `cancel_active_job`

Returns the vacuum to base, finalizes the active job as cancelled, and emits the `eufy_vacuum_job_finished` event.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

---

## Queue Building

Use these services to configure which rooms are cleaned and in what order, then call `start_selected_rooms` to launch the job.

### `build_queue`

Builds the cleaning queue from all currently enabled rooms in their configured order.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

Call this after changing room settings or enabling/disabling rooms, before calling `start_selected_rooms`.

### `start_run_profile`

Applies a saved run profile, rebuilds the queue from it, and starts cleaning — all in one call. This is the recommended way to launch a named preset from an automation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `profile_id` | Yes | ID of the saved run profile to apply. |
| `confirm_reduced_run` | No | Allow a blocker-reduced run without interactive confirmation. |
| `confirm_token` | No | Retry token from a prior `confirmation_required` response. |
| `path_block_action` | No | `event_only`, `pause_and_event`, or `cancel_and_event`. |
| `pause_timeout_minutes_override` | No | Per-job pause timeout override in minutes. `0` disables auto-cancel. |

Returns the same shape as `start_selected_rooms`, including `confirmation_required` when blocker rules reduce the run and neither `confirm_reduced_run` nor a valid `confirm_token` is provided.

### `update_room_fields`

Applies per-room field overrides without requiring a named profile. Only the fields you supply are changed; everything else stays as-is. Sets the room's `profile_name` to `custom` to signal divergence from a preset.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `room_id` | Yes | |
| `enabled` | No | Enable or disable the room for queue and payload generation. |
| `clean_mode` | No | |
| `fan_speed` | No | |
| `water_level` | No | |
| `clean_intensity` | No | |
| `clean_passes` | No | `1` or `2`. |
| `edge_mopping` | No | |
| `is_dock_room` | No | Mark this room as the dock/root room for the access graph. |
| `grants_access_to` | No | List of downstream room IDs this room leads to in the access graph. |
| `rules` | No | Dynamic blocker and modifier rule definitions. |

Water-on-carpet enforcement is applied at payload time regardless of what is stored here.

### `get_start_status`

Checks whether a cleaning job can be started and returns the current readiness state. Returns `onboarding_required` if any enabled room lacks a confirmed floor type.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

Supports response. Use this in an automation condition before calling `start_selected_rooms` if you need to gate on readiness.

---

## State Inspection

Read-only services that return current integration state. All support response.

### `get_queue_state`

Returns the current queue state including room order.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `get_payload_state`

Returns the current resolved cleaning payload including per-room settings as they would be sent to the vacuum. Reflects the output of the last `build_queue` or `build_room_payload` call, including carpet enforcement and capability guards.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

Supports response. Use this to inspect exactly what the vacuum would receive before calling `start_selected_rooms`.

### `clear_queue`

Clears the current queue state. The vacuum is not affected — this only resets the integration-side queue record. Persists to storage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `clear_active_job`

Clears the active job record without sending any command to the vacuum. Persists to storage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

Use this to recover from a stuck or orphaned job state when `cancel_active_job` is not appropriate (for example, when the vacuum has already finished but the integration still shows an active job). This service does not finalize or archive the job — it only removes the in-memory record.

### `get_active_job`

Returns the current active job state including start time and battery level at start.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `get_job_progress_snapshot`

Returns the canonical room-job progress state including current room, completed rooms, remaining rooms, and live completion percentage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `get_job_control_state`

Returns the backend-authored button availability and messages for the start, pause, resume, cancel, and clear actions. The card uses this to decide which buttons to enable and what label or tooltip to show. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

This service returns control state, not job progress. For current job progress use `get_job_progress_snapshot`. For the combined single-call dashboard payload, use `get_dashboard_snapshot`.

### `get_lifecycle_state`

Returns the current lifecycle state for a vacuum. Possible states include `ready`, `cleaning`, `dock_drying`, `cancelled`, and `failed`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `get_dashboard_snapshot`

Returns one unified payload containing job progress, job control button state, start status, lifecycle, and upkeep data. Designed to power a full card render in a single call.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `get_pause_timeout_settings`

Returns the persisted default paused-job timeout for a vacuum.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

### `set_pause_timeout_settings`

Persists the default paused-job auto-cancel timeout. Used when a start call does not supply `pause_timeout_minutes_override`.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `pause_timeout_minutes_default` | Yes | Minutes before a paused job is auto-cancelled. `0` disables auto-cancel. Range: 0–1440. |

### `get_upkeep_snapshot`

Returns replacement items, maintenance items, dock events, dock event counts, and upkeep attention summaries for one vacuum. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

This is a vacuum-level (not map-level) service — `map_id` is not required. The card uses it to populate the upkeep panel. You can call it from an automation to check whether any maintenance items are due.

---

## Profiles

### Run Profiles

Run profiles capture the full room selection, order, and per-room settings for a map so you can replay a cleaning configuration on demand.

#### `save_run_profile`

Saves the currently enabled rooms and their settings as a new named run profile.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `name` | Yes | Display name for the profile. |
| `expose_as_button` | No | Mark this profile for Home Assistant button exposure. |

#### `apply_run_profile`

Restores a saved run profile back onto room selection, order, and per-room settings without starting a job.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |
| `profile_id` | Yes |

#### `start_run_profile`

See [Queue Building](#queue-building) — this is the one-shot apply-and-start shortcut.

#### `get_saved_run_profiles`

Returns all saved run profiles for a vacuum/map combination.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

Supports response.

### Room Profiles

Room profiles define cleaning settings (fan speed, water level, clean mode, etc.) that can be applied to one or more rooms at once.

#### `apply_room_profile`

Applies a named profile to one or more rooms on a map.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `room_ids` | Yes | List of room IDs to apply the profile to. |
| `profile_name` | Yes | Built-in or custom profile key. |

#### `get_room_profiles`

Returns all available built-in and user-defined room profiles. Takes no parameters. Supports response.

#### `save_user_room_profile`

Saves a custom room profile to the profile library from explicit settings values.

| Parameter | Required | Notes |
|---|---|---|
| `label` | Yes | Display name. |
| `clean_mode` | Yes | |
| `fan_speed` | Yes | |
| `water_level` | Yes | |
| `clean_intensity` | Yes | |
| `clean_passes` | Yes | `1` or `2`. |
| `carpet` | Yes | Boolean — whether this profile targets carpet. |
| `edge_mopping` | Yes | |
| `profile_name` | No | Optional stable backend key. Omit to use the legacy user slot. |

#### `save_room_profile_from_room`

Creates a new custom room profile by copying one room's current effective settings.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `room_id` | Yes | |
| `label` | Yes | Display name for the new profile. |
| `profile_name` | No | Optional stable backend key. |

---

## Learning Services

The learning system records completed job history to build per-room timing estimates. Most of these services run automatically — the ones below are the ones you would call explicitly from an automation or script.

### `retry_missed_rooms`

Re-queues only the rooms that were skipped in the last incomplete run and starts cleaning immediately. Reads the stored incomplete run log to determine which rooms were missed, enables only those rooms, builds the queue, and fires `start_selected_rooms`.

This service is designed for automation use. Pair it with the `eufy_vacuum_run_incomplete` event trigger so the vacuum automatically retries missed rooms after a cancelled or interrupted run.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Defaults to the `map_id` stored in the incomplete run log. Omit when triggered by `eufy_vacuum_run_incomplete`. |
| `confirm_reduced_run` | No | Default `true`. Proceed even when blockers would normally require confirmation — appropriate for unattended automation. |
| `path_block_action` | No | `event_only`, `pause_and_event`, or `cancel_and_event`. |

**Returns:** The same shape as `start_selected_rooms` with an additional `missed_room_ids` list showing which rooms were re-queued. Returns `{"started": false, "reason": "no_missed_rooms"}` when the incomplete run log is absent or empty.

**Automation pattern:**

```yaml
trigger:
  - platform: event
    event_type: eufy_vacuum_run_incomplete
    event_data:
      vacuum_entity_id: "vacuum.alfred"
action:
  - service: eufy_vacuum.retry_missed_rooms
    data:
      vacuum_entity_id: "{{ trigger.event.data.vacuum_entity_id }}"
```

### `run_learning_estimate`

Computes a full job estimate from learned room history and the current queue state. Returns per-room ETAs, confidence scores, overhead breakdown, and battery information. Battery warnings are informational only — low battery never blocks the job because the vacuum recharges mid-job and resumes.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `current_battery` | No | Current battery %. Default `0.0`. Used for battery warning calculation. |
| `charge_percent_per_minute` | No | Default `1.0`. |
| `reserve_battery_percent` | No | Minimum battery buffer to keep in reserve. Default `5.0`. |
| `started_at` | No | ISO timestamp to anchor ETAs from. Defaults to now. |

**Returns:** Full estimate payload with per-room ETAs, confidence scores, and overhead breakdown.

### `reanchor_learning_timeline`

Recomputes room ETAs mid-job using actual completed room durations. Call this each time a room completes, passing all rooms completed so far (not just the latest one).

| Parameter | Required | Notes |
|---|---|---|
| `original_estimate` | Yes | The full payload from `run_learning_estimate`. |
| `completed_rooms` | Yes | List of dicts, each with `room_id` or `slug` and `actual_duration_minutes`. Pass all completed rooms, not just the latest. |
| `reanchor_at` | No | ISO timestamp to anchor remaining ETAs from. Defaults to now. |
| `current_battery` | No | Updates battery warning for remaining rooms if supplied. |

**Returns:** Updated estimate payload with revised ETAs for remaining rooms.

### `get_next_room`

Returns the next incomplete room from a reanchored timeline. Lightweight shortcut that returns only what a live job banner needs. Returns an empty dict when all rooms are complete.

| Parameter | Required | Notes |
|---|---|---|
| `reanchored_estimate` | Yes | The latest payload from `reanchor_learning_timeline`. |

**Returns:** Next room details or `{}` when all rooms are complete.

### `get_room_learning_estimates`

Returns per-room learning estimates for all rooms on a map based on each room's current effective persisted settings. Queue-independent — both queued and unqueued rooms receive estimates. Safe for frequent UI refreshes. Has no side effects.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `current_battery` | No | Optional. Informational only. |

**Returns:** Per-room estimate data keyed by room.

### `rebuild_learning_stats`

Forces a full rebuild of learned job and room statistics from all completed job history. Called automatically after `finalize_learning_job` — use this manually to correct stats after excluding or restoring archived jobs.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `rebuild_csv` | No | Also rebuild flat CSV exports. Default `false`. |

### `save_learning_snapshot`

Manually saves a learning snapshot for the current job state. Called automatically by `start_selected_rooms` — manual use is only needed for edge cases such as recording a job that was started outside the integration.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `started_at` | Yes | Job start timestamp in `YYYY-MM-DDTHH:MM:SS` format. |
| `battery_start` | Yes | Battery percent at job start (0–100). |
| `job_id` | No | Optional custom job ID. |

### `finalize_learning_job`

Manually finalizes a completed job and optionally rebuilds learned stats. Called automatically when the vacuum returns to dock — manual use is needed for edge cases or historical corrections.

Fires `eufy_vacuum_job_finished` on completion. Also fires `eufy_vacuum_run_incomplete` if the job ended with rooms unvisited.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `battery_start` | Yes | Battery at job start (0–100). |
| `battery_end` | Yes | Battery at job end (0–100). |
| `started_at` | Yes | Job start timestamp in `YYYY-MM-DDTHH:MM:SS` format. |
| `ended_at` | No | End timestamp. Defaults to now. |
| `used_for_learning` | No | Whether to include this job in learned stats. Default `true`. |
| `rebuild_stats` | No | Rebuild learned stats after finalizing. Default `true`. |
| `rebuild_csv` | No | Also rebuild CSV exports. Default `false`. |

### `exclude_learning_job`

Excludes one archived completed job from learned stats without deleting the JSON record. Rebuilds learned stats immediately so the bad run stops affecting future estimates.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `job_id` | Yes | Completed job ID, for example `job_2026-04-08T17-41-53`. |
| `reason` | No | Exclusion reason stored on the archived job. Default `manual_exclusion`. |
| `rebuild_csv` | No | Also rebuild CSV exports. Default `false`. |

**Returns:** Result payload confirming exclusion.

### `restore_learning_job`

Restores one archived completed job back into learned stats without deleting the archived file.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `job_id` | Yes | Archived completed job identifier. |
| `rebuild_csv` | No | Also rebuild CSV exports. Default `false`. |

**Returns:** Result payload confirming restoration.

### `get_learning_history_snapshot`

Returns a card-friendly snapshot of learned history including recent jobs, room aggregates, room profile aggregates, and learned room statistics. Supports optional filtering.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_slug` | No | Filter to a single room slug, e.g. `kitchen`. |
| `profile_key` | No | Filter by room profile signature. |
| `status` | No | Filter by job status: `completed`, `cancelled`, `failed`, or `interrupted`. |
| `used_for_learning` | No | Filter to only jobs included in or excluded from learned stats. |
| `limit` | No | Maximum recent jobs to return. Default `50`, max `500`. |

**Returns:** History snapshot with recent jobs and aggregated room statistics.

---

## Dock Actions

These services gate on dock and vacuum state before issuing the upstream command — they refuse silently when the dock is not in a valid state. Use `get_dock_action_status` first to check availability.

### `wash_mop`

Runs the dock wash action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `dry_mop`

Runs the dock dry action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `stop_dry_mop`

Stops an active dock drying cycle. Only runs when the dock is actively drying.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `empty_dust`

Runs the dock dust-empty action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `get_dock_action_status`

Returns gated availability and blocked reasons for `wash_mop`, `dry_mop`, and `empty_dust`. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

### `set_dock_event_count`

Overwrites a dock event counter to a specific value. This is a one-time correction service — use it when the stored event count is wrong due to an interrupted integration startup, missed dock event, or manual intervention at the dock.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `event_type` | Yes | One of `last_mop_wash`, `last_dust_empty`, `last_dry_start`. |
| `count` | Yes | The new integer count. Must be 0 or greater. |

Supports response. Returns `{"updated": true}` on success or `{"updated": false, "error": "..."}` if the `event_type` is unrecognised. Persists to storage when the update succeeds.

---

## Runtime Management

These are low-level diagnostic and recovery services. Under normal operation you should never need them. Use them only when directed by troubleshooting steps or when recovering from a corrupted or inconsistent integration state.

### `refresh_backend`

Forces the integration manager to re-read its persisted state from storage and rebuild all derived in-memory structures. Use this to recover after a storage file was manually corrected or after an unexpected HA restart left the integration in a partially-loaded state.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

> **Risk:** Any unsaved in-memory changes are discarded. This does not affect the vacuum hardware — only the integration's internal state.

### `rebuild_active_map`

Forces the integration to re-derive the active map record for a vacuum from the underlying map data. Use this when the active map is stale or the card is showing the wrong map after a map switch.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

> **Risk:** Low. This is a read-and-rebuild operation with no destructive side effects.

### `clear_runtime_state`

Clears all runtime state for a vacuum — queue, active job, lifecycle, and any pending in-memory mutations — without deleting persisted map or room configuration. Use this as a last resort when the integration is stuck and none of the more targeted recovery services (`clear_queue`, `clear_active_job`) resolve the issue.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

> **Risk:** Any active job tracking is lost. If a job is in progress, call `cancel_active_job` first so the job is finalized correctly before clearing runtime state.

---

## Battery Health

### `battery_rebaseline`

Clears the per-install health baseline anchor for the supplied vacuum so the next qualifying recharge re-anchors it. Use this after physically replacing the battery — the existing baseline describes the old cell's charge curve and produces meaningless health % readings against the new one.

**Parameters:**

| Parameter | Required | Description |
|---|---|---|
| `vacuum_entity_id` | Yes | The vacuum entity whose baseline should be cleared. |

**What it touches:**

- `baseline.min_per_pct` → `null`
- `baseline.session_count` → `0`
- `baseline.anchored_at` → `null`
- `stats.health_pct` → `null` (sensor reads "Building baseline" until re-anchored)

**What it leaves alone:**

- `cycles` and `cumulative_drain_pct` — total wear is still meaningful regardless of which battery is installed
- `job_aggregates` (per-mode / per-fan / per-water-level drain rates) — those describe the *vacuum's* power profile, not the battery's age
- `mid_job_recharge_stats` — rolling mean continues from where it left off
- `session_history_recent` — historical sessions still readable; only the baseline pointer is reset
- Sensors other than `_battery_health`

After the call, run a heavy-load job (max suction, max water, narrow path / 2 passes, edge clean, as many rooms as possible) to drain to ≤ 50 % then dock for an uninterrupted recharge to ≥ 90 %. The next session-close after that recharge anchors the new baseline.

The service has no return value (does not support response). Logs a warning if the battery manager is not loaded or no record exists for the supplied vacuum.

See [advanced/09-battery-health.md](09-battery-health.md#health-proxy) for the full health-proxy model and [user-guide/13-battery-health.md](../user-guide/13-battery-health.md#after-replacing-the-battery) for the user-facing replacement workflow.

---

## Setup Services

These services drive the setup panel's onboarding flow. Under normal operation the panel calls them for you. Power users and developers can call them directly from automations or scripts, but most of the time you will interact with them through the card's setup UI rather than the service developer tools.

All setup services support response.

### `setup_get_status`

Returns the current setup state that drives which panel view to render. Takes no parameters.

**Returns:**

| Field | Description |
|---|---|
| `setup_complete` | Boolean — `true` when at least one vacuum has an imported map. |
| `state` | `no_vacuums`, `no_map`, or `ready`. |
| `vacuums` | List of managed vacuum summaries, each including `vacuum_entity_id`, `display_name`, a `maps` list, and `has_imported_map`. |
| `next_actions` | Suggested next steps for the panel to render, e.g. `["add_vacuum"]`. |

### `setup_add_vacuum`

Registers a vacuum entity with the integration manager. Idempotent — returns `"already_done"` if the vacuum is already managed. Returns `"blocked"` if the entity does not exist in the HA state machine.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

**Returns:** An ActionResult dict with `status`, `message`, `data`, and `next_actions`.

### `setup_import_active_map`

Discovers rooms from the underlying `eufy-clean` integration for a vacuum's currently active map and imports them into the integration. This is the first step after adding a vacuum — it populates the room list the card will manage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

**Returns:** An ActionResult dict with `status`, `message`, `data`, and `next_actions`.

### `setup_get_map_rooms`

Returns the list of managed rooms for a specific vacuum and map. Used by the setup panel to show the current room state so the user can review before saving.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No (auto) |

**Returns:** `{"vacuum_entity_id": ..., "map_id": ..., "rooms": [...]}`.

### `setup_save_rooms`

Saves a set of room IDs as managed rooms for a vacuum and map, optionally setting floor types. This is the commit step of the onboarding flow — rooms become managed and available for queue building after this call.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `enabled_room_ids` | No | List of integer room IDs to save. Omit to keep existing. |
| `floor_types` | No | Dict mapping room ID to floor type. Valid values: `hardwood`, `laminate`, `tile`, `marble`, `carpet`. |

**Returns:** `{"status": "success", "room_count": N}` on success.

### `setup_delete_map`

Deletes one imported map and all related integration data (rooms, queue, job records, learned history) for that map. This is an integration-only operation — it does not affect Eufy cloud data.

Delete operations are protection-gated. High-protection maps (those with significant learned history) require a `confirmation_token` matching the map display name exactly before the delete proceeds.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No (auto) | |
| `confirmation_token` | No | Required for high-protection maps. Must match the map display name exactly. |

**Returns:** An ActionResult dict. Returns `"blocked"` with a `code` of `"confirmation_required"` when the token is missing or wrong for a protected map.

> **Risk:** Irreversible. All learned history for the map is permanently deleted.

### `setup_reject_rooms`

Marks one or more discovered rooms as phantoms. Rejected rooms never resurface in `room_drift.new_rooms` even if the vacuum re-reports them on a later discovery pass. If a rejected room was previously configured, it is removed from `managed_rooms` and its HA entities (switch, number, sensor) are torn down via the room-update callback chain.

Stored under `setup_progress[vacuum_entity_id].rejected_rooms` so the rejection persists across HA restarts.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_ids` | Yes | List of integer room IDs to reject. |

**Returns:** `{status, rejected: [room_id, ...], removed_from_managed: [room_id, ...], affected_map_ids: [map_id, ...]}`.

**Typical use:** A vacuum reports a phantom room (firmware glitch) which surfaces on the setup tab as a "new room". The user clicks **Reject as phantom** in the card to call this service. The room is permanently suppressed.

### `setup_force_remove_room`

Bypasses the missing-pass counter for one room — immediately flags it as removed in `room_drift.removed_rooms` without waiting for the normal `removal_confirmation_passes` window (default 3 missed discoveries).

The room **stays in `managed_rooms`** with `is_configured: True` and its HA entities continue to exist; only the drift signal flips. Pair with a separate explicit delete operation if you want to fully remove the room from learning history.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_id` | Yes | Integer room ID. |

**Returns:** `{status, room_id, missing_passes, threshold}`.

**Typical use:** The user knows a room has been permanently removed (renovation, vacuum reset) and doesn't want to wait several discovery passes for the framework to confirm it. Click **Force remove now** in the setup tab's drift panel.

---

## Theme Services

These services manage the integration's theme library — the named colour and token sets that drive the card's visual appearance. Primarily called by the card itself, but can be called from automations or developer tools for advanced workflows such as importing a shared theme or scripting a scheduled theme switch.

All read services support response. Write services are fire-and-forget unless noted.

### `get_theme_library`

Returns the full theme library including all named themes with their token, colour, and alpha values. Takes no parameters. Supports response.

### `save_theme_as_new`

Saves a vacuum's current working draft as a new named theme in the library. Clears `draft_dirty` on the vacuum after saving.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | The vacuum whose draft is being saved. |
| `name` | Yes | Display name for the new theme. |
| `set_as_default` | No | Set the new theme as the global default. Default `false`. |

### `overwrite_theme`

Replaces an existing library theme with a vacuum's current working draft. Clears `draft_dirty` on the vacuum.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `theme_id` | Yes |

### `rename_theme`

Updates the display name of a library theme.

| Parameter | Required |
|---|---|
| `theme_id` | Yes |
| `name` | Yes |

### `delete_theme`

Removes a theme from the library. Also clears `active_theme_id` on any vacuum that was using it, so those vacuums fall back to the global default.

| Parameter | Required |
|---|---|
| `theme_id` | Yes |

### `set_active_theme`

Points a vacuum at a specific library theme. The working draft is cleared so the preview resolves from the active theme plus any future draft overrides. Omit `vacuum_entity_id` to update the global default without changing any per-vacuum draft state.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | No | Leave blank to set the global default only. |
| `theme_id` | Yes | |

### `update_working_draft`

Patch-merges partial token, colour, and/or alpha overrides into a vacuum's working draft. Keys sent with `null` or an empty string are removed from the draft. The theme sensor updates automatically after the call.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `tokens` | No | Dict of token names to values. This is the canonical theme bucket. |
| `colors` | No | Dict of colour token names to values. Kept for compatibility. |
| `alpha` | No | Dict of alpha token names to opacity values (`0.0`–`1.0`). |

### `revert_draft`

Clears a vacuum's working draft overrides so the preview resolves back to the active theme. Clears `draft_dirty`. The theme sensor updates automatically.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

### `export_theme`

Returns a portable JSON-safe payload for a theme, including tokens, colours, and alpha values. Supports response. Use the output as the `payload` parameter for `import_theme`.

| Parameter | Required |
|---|---|
| `theme_id` | Yes |

### `import_theme`

Imports a theme from an exported payload. Handles name collisions by appending `(imported)` to the theme name.

| Parameter | Required | Notes |
|---|---|---|
| `payload` | Yes | The full dict returned by `export_theme`. |

---

## Room and Profile Management

Services for managing room cleaning profiles (factory + user-defined)
and saved multi-room "run profiles" (named selections of rooms). Most
of these are driven by the card; automation use is rare.

### Room cleaning profiles

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `get_room_profiles` | List every factory + user-saved room cleaning profile. | (none) | (none) | yes — `{profiles: [...]}` |
| `save_user_room_profile` | Save a new custom room profile from explicit clean parameters. | `label`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping` | `profile_name` | yes — `{ok, profile_name}` |
| `overwrite_room_profile` | Replace an existing custom profile with new clean parameters. | `profile_name`, `label`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping` | (none) | yes — `{ok}` |
| `save_room_profile_from_room` | Create a new profile by copying one room's current settings. | `vacuum_entity_id`, `room_id`, `label` | `map_id` (auto), `profile_name` | yes — `{ok, profile_name}` |
| `overwrite_room_profile_from_room` | Update an existing profile from one room's current settings. | `vacuum_entity_id`, `room_id`, `profile_name` | `map_id` (auto), `label` | yes — `{ok}` |
| `rename_room_profile` | Rename an existing custom profile. | `profile_name` | `new_profile_name`, `label` | yes — `{ok}` |
| `delete_room_profile` | Remove a custom profile from the library. Factory profiles cannot be deleted. | `profile_name` | (none) | yes — `{ok}` |
| `apply_room_profile` | Apply one profile's settings to one or more rooms. | `vacuum_entity_id`, `room_ids: list[int]`, `profile_name` | `map_id` (auto) | yes — `{ok, applied_count}` |

### Run profiles (saved room selections)

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `get_saved_run_profiles` | List saved run profiles for one vacuum/map. | `vacuum_entity_id` | `map_id` (auto) | yes — `{profiles: [...]}` |
| `save_run_profile` | Save the current enabled-room selection as a named run profile. | `vacuum_entity_id`, `name` | `map_id` (auto), `expose_as_button: bool` | yes — `{ok, profile_id}` |
| `apply_run_profile` | Activate a saved run profile (enables only its rooms; does not start). | `vacuum_entity_id`, `profile_id` | `map_id` (auto) | yes — `{ok}` |
| `overwrite_run_profile` | Replace a saved profile with the current enabled-room selection. | `vacuum_entity_id`, `profile_id` | `map_id` (auto), `name`, `expose_as_button` | yes — `{ok}` |
| `rename_run_profile` | Rename a saved run profile. | `vacuum_entity_id`, `profile_id`, `name` | `map_id` (auto) | yes — `{ok}` |
| `delete_run_profile` | Delete a saved run profile. | `vacuum_entity_id`, `profile_id` | `map_id` (auto) | yes — `{ok}` |

### Room field editing

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `get_room_access_editor` | Return the access-graph editor state for one room (incoming/outgoing edges, rules). | `vacuum_entity_id`, `room_id` | `map_id` (auto) | yes |
| `get_access_graph_health` | Validate the access graph for the whole map (orphan rooms, cycles, dock reachability). | `vacuum_entity_id` | `map_id` (auto) | yes — `{ok, issues: [...]}` |

---

## Room and Map Discovery

Services for adding rooms and maps to the integration's managed
inventory.

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `discover_rooms` | Read the room list from the vacuum entity's `segments` attribute (or wherever the adapter declares) and stage them for selection. | `vacuum_entity_id` | `map_id` | no |
| `save_managed_rooms` | Persist a subset of discovered rooms as managed. Drives the onboarding "pick the rooms you want to manage" step. | `vacuum_entity_id` | `map_id` (auto), `enabled_room_ids: list[int]` | no |
| `get_vacuum_maps` | List every map stored for one vacuum. | `vacuum_entity_id` | (none) | yes — `{maps: [{map_id, name, ...}, ...]}` |

---

## Maintenance and Errors

Per-component maintenance reset and the error-tracker surface.

| Service | Purpose | Required | Optional | Returns |
|---------|---------|----------|----------|---------|
| `reset_maintenance` | Reset the manual-reset counter for one consumable component (brush, filter, mop pad, etc.). The component key must match `adapter_config.maintenance_components`. | `vacuum_entity_id`, `component: str` | (none) | yes — `{ok, component, reset_at}` |
| `set_maintenance_interval` | Override the maintenance interval (in hours) for one component. Writes the same storage slot as the `number.*_maintenance_interval` entity, so the card editor and the entity stay in sync. The card's modal editor surfaces the adapter-declared default/max bounds and validates before submitting. | `vacuum_entity_id`, `component: str`, `interval_hours: float` | (none) | yes — `{saved, vacuum_entity_id, component, interval_hours}` |
| `acknowledge_error` | Clear an active-run error latch or the last-device error latch (or both). | `vacuum_entity_id` | `scope: "active_run" \| "last_device" \| "both"` (default `both`) | yes — `{ok, cleared: [...]}` |
| `get_recent_errors` | Return the most recent error entries from the per-device ring buffer. | `vacuum_entity_id` | `limit: int` (1-50, default 20) | yes — `{vacuum_entity_id, errors: [...], count}` |

---

## Mapping Services

The mapping subsystem covers map image upload, room boundary drawing,
trace capture, dock anchoring, and image-segment analysis. Most
services are called by the card during the map setup flow, not from
automations.

**Full reference: [mapping-system.md §10](../dev/mapping-system.md#10-services).**

Quick categories:

- **Image management** — `save_map_image`, `upload_map_image`, `analyze_map_image`
- **Room markers** — `set_companion_anchor` (per-room visual marker dot drawn on the map image)
- **Interactive boundaries** — `start_room_boundary_trace`, `close_room_boundary`, `cancel_room_boundary_trace`, `get_room_bounds_snapshot`, `clear_room_bounds`
- **Trace capture** (job-driven learning) — `start_trace_capture`, `stop_trace_capture`, `cancel_trace_capture`, `review_trace_run`, `append_mapping_trace_evidence`, `exclude_room_job_bounds`, `restore_room_job_bounds`, `rebuild_room_bounds_from_archive`
- **Dock and segments** — `set_dock_anchor`, `set_dock_room`, `get_image_segment_suggestions`, `translate_image_segment`, `adjust_map_segment`, `set_segment_room_link`, `get_map_segments`
- **State and packaging** — `get_mapping_state`, `get_mapping_package`, `save_mapping_package`

---

## Adapter Config Services

Services for the future multi-brand UI config flow. All operate on
the per-vacuum adapter registry that drives every brand-specific
behaviour in the framework.

**Full reference: [adapter-config-reference.md §21](../dev/adapter-config-reference.md#21-services-that-read-and-write-adapter-configs).**

| Service | Purpose | Required | Returns |
|---------|---------|----------|---------|
| `save_adapter_config` | Persist a UI-built adapter config dict. | `vacuum_entity_id`, `config: dict` | no |
| `delete_adapter_config` | Remove a stored adapter config; setup falls back to the code adapter if present. | `vacuum_entity_id` | no |
| `get_adapter_config` | Return the active adapter config (code or stored). | `vacuum_entity_id` | yes |
| `discover_adapter_entities` | Scan HA for entities matching adapter roles based on `detected_model`. | `detected_model: str` | yes |
| `observe_entity_states` | Return current state snapshots for a list of entity IDs (config-flow validation). | `entity_ids: list[entity_id]` | yes |
| `get_vacuum_capabilities` | Detect or refresh capability flags for one vacuum. | `vacuum_entity_id` | yes |

---

## Events Reference

These events are fired by the integration. Use them as automation triggers.

| Event | Fired when |
|---|---|
| `eufy_vacuum_job_finished` | A job is finalized (completed, cancelled, or failed). Payload includes `job_id`, `status`, `vacuum_entity_id`, `map_id`. |
| `eufy_vacuum_run_incomplete` | A cancelled or interrupted job left at least one queued room uncleaned. Payload includes `missed_room_ids` and `missed_rooms`. Use with `retry_missed_rooms`. |
| `eufy_vacuum_room_started` | The vacuum begins cleaning a room. |
| `eufy_vacuum_room_finished` | The vacuum finishes cleaning a room. |
| `eufy_vacuum_path_blocked` | Blocker rules changed mid-run and remaining rooms became inaccessible. |
| `eufy_vacuum_stall_detected` | The robot has been in a room for 2× its learned timing threshold. Payload includes `elapsed_minutes`, `expected_minutes`, and `stall_ratio`. Fires at most once per room per job. |
