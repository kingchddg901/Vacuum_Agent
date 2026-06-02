# Services Reference

All services are registered under the `eufy_vacuum` domain. Call them as `eufy_vacuum.<service_name>`.

Services that `supports_response` return a data payload you can capture with `response_variable` in a script or automation action. Services that do not support response run fire-and-forget.

Most services require at least `vacuum_entity_id`. Services that operate on a specific map also require `map_id`. Both fields are noted in each section.

---

## Job Control

These services start, pause, resume, and cancel the integration-managed active job.

### `start_selected_rooms`

Sends the resolved cleaning payload to the vacuum and starts the job. Honors room blockers, access-graph dependencies, modifier rules, and reduced-run confirmation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
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
| `map_id` | Yes |

### `resume_active_job`

Resumes the vacuum and the paused job.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `cancel_active_job`

Returns the vacuum to base, finalizes the active job as cancelled, and emits the `eufy_vacuum_job_finished` event.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

---

## Queue Building

Use these services to configure which rooms are cleaned and in what order, then call `start_selected_rooms` to launch the job.

### `build_queue`

Builds the cleaning queue from all currently enabled rooms in their configured order.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

Call this after changing room settings or enabling/disabling rooms, before calling `start_selected_rooms`.

### `start_run_profile`

Applies a saved run profile, rebuilds the queue from it, and starts cleaning — all in one call. This is the recommended way to launch a named preset from an automation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
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
| `map_id` | Yes | |
| `room_id` | Yes | |
| `enabled` | No | Enable or disable the room for queue and payload generation. |
| `clean_mode` | No | |
| `fan_speed` | No | |
| `water_level` | No | |
| `clean_intensity` | No | |
| `clean_passes` | No | `1` or `2`. |
| `edge_mopping` | No | |
| `is_dock_room` | No | Mark this room as the dock/root room for the access graph. |
| `is_transition` | No | Mark this room as a transition corridor (pass-through only, not cleaned). |
| `grants_access_to` | No | List of downstream room IDs this room leads to in the access graph. |
| `rules` | No | Dynamic blocker and modifier rule definitions. |

Water-on-carpet enforcement is applied at payload time regardless of what is stored here.

### `get_start_status`

Checks whether a cleaning job can be started and returns the current readiness state. Returns `onboarding_required` if any enabled room lacks a confirmed floor type.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

Supports response. Use this in an automation condition before calling `start_selected_rooms` if you need to gate on readiness.

---

## Rooms

These services manage room discovery and map data outside of the onboarding wizard. They are also called automatically by the discovery listener.

### `discover_rooms`

Triggers a live room discovery pass from the upstream vacuum integration and updates the room drift history. Safe to call at any time — does not modify managed room settings.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Defaults to the currently active map. |

### `save_managed_rooms`

Persists the current room discovery result as the managed room configuration. Equivalent to the `setup_save_rooms` onboarding step but callable outside the setup wizard.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Defaults to the currently active map. |
| `enabled_room_ids` | No | List of integer room IDs to enable. Omit to keep all rooms enabled. |

### `get_vacuum_maps`

Returns all imported maps for a vacuum with room counts and display names.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Supports response.

---

## State Inspection

Read-only services that return current integration state. All support response.

### `get_queue_state`

Returns the current queue state including room order.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `get_payload_state`

Returns the current resolved cleaning payload including per-room settings as they would be sent to the vacuum. Reflects the output of the last `build_queue` or `build_room_payload` call, including carpet enforcement and capability guards.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

Supports response. Use this to inspect exactly what the vacuum would receive before calling `start_selected_rooms`.

### `clear_queue`

Clears the current queue state. The vacuum is not affected — this only resets the integration-side queue record. Persists to storage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `clear_active_job`

Clears the active job record without sending any command to the vacuum. Persists to storage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

Use this to recover from a stuck or orphaned job state when `cancel_active_job` is not appropriate (for example, when the vacuum has already finished but the integration still shows an active job). This service does not finalize or archive the job — it only removes the in-memory record.

### `get_active_job`

Returns the current active job state including start time and battery level at start.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `get_job_progress_snapshot`

Returns the canonical room-job progress state including current room, completed rooms, remaining rooms, and live completion percentage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `get_job_control_state`

Returns the backend-authored button availability and messages for the start, pause, resume, cancel, and clear actions. The card uses this to decide which buttons to enable and what label or tooltip to show. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

This service returns control state, not job progress. For current job progress use `get_job_progress_snapshot`. For the combined single-call dashboard payload, use `get_dashboard_snapshot`.

### `get_lifecycle_state`

Returns the current lifecycle state for a vacuum. Possible states include `ready`, `cleaning`, `dock_drying`, `cancelled`, and `failed`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `get_dashboard_snapshot`

Returns one unified payload containing job progress, job control button state, start status, lifecycle, and upkeep data. Designed to power a full card render in a single call.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

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
| `map_id` | Yes | |
| `name` | Yes | Display name for the profile. |
| `expose_as_button` | No | Mark this profile for Home Assistant button exposure. |

#### `overwrite_run_profile`

Replaces the rooms snapshot in an existing run profile without creating a new one. Preserves the profile ID and label unless a new name is supplied.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
| `profile_id` | Yes | ID of the run profile to overwrite. |
| `name` | No | Updated display name. Omit to keep the existing label. |
| `expose_as_button` | No | |

#### `rename_run_profile`

Updates the display label of an existing run profile.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |
| `profile_id` | Yes |
| `name` | Yes |

#### `delete_run_profile`

Deletes a saved run profile. This does not affect current room settings — it only removes the named preset from the library.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |
| `profile_id` | Yes |

#### `apply_run_profile`

Restores a saved run profile back onto room selection, order, and per-room settings without starting a job.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |
| `profile_id` | Yes |

#### `start_run_profile`

See [Queue Building](#queue-building) — this is the one-shot apply-and-start shortcut.

#### `get_saved_run_profiles`

Returns all saved run profiles for a vacuum/map combination.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

Supports response.

### Room Profiles

Room profiles define cleaning settings (fan speed, water level, clean mode, etc.) that can be applied to one or more rooms at once.

#### `apply_room_profile`

Applies a named profile to one or more rooms on a map.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
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
| `edge_mopping` | Yes | |
| `profile_name` | No | Optional stable backend key. Omit to use the legacy user slot. |

#### `overwrite_room_profile`

Replaces the settings in an existing custom room profile. Cannot target built-in profiles.

| Parameter | Required | Notes |
|---|---|---|
| `profile_name` | Yes | Key of the profile to overwrite. |
| `label` | Yes | Updated display name. |
| `clean_mode` | Yes | |
| `fan_speed` | Yes | |
| `water_level` | Yes | |
| `clean_intensity` | Yes | |
| `clean_passes` | Yes | `1` or `2`. |
| `edge_mopping` | Yes | |

#### `save_room_profile_from_room`

Creates a new custom room profile by copying one room's current effective settings.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
| `room_id` | Yes | |
| `label` | Yes | Display name for the new profile. |
| `profile_name` | No | Optional stable backend key. |

#### `overwrite_room_profile_from_room`

Replaces an existing custom room profile's settings from one room's current effective settings.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
| `room_id` | Yes | Source room to copy settings from. |
| `profile_name` | Yes | Key of the profile to overwrite. |
| `label` | No | Updated display name. Omit to keep the existing label. |

#### `rename_room_profile`

Updates the display name and/or backend key of a custom room profile. Cannot target built-in profiles.

| Parameter | Required | Notes |
|---|---|---|
| `profile_name` | Yes | Existing profile key. |
| `new_profile_name` | No | New backend key. Omit to keep the key and change only the label. |
| `label` | No | New display name. |

#### `delete_room_profile`

Deletes a custom room profile from the library. Cannot target built-in profiles.

| Parameter | Required |
|---|---|
| `profile_name` | Yes |

---

## Error Tracking

These services interact with the per-vacuum error tracker. The tracker monitors error signals from the vacuum and retains a rolling history independent of job records.

### `acknowledge_error`

Clears the active-run error latch, the last-device error latch, or both.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `scope` | No | `"active_run"`, `"last_device"`, or `"both"` (default). |

Supports response. Returns `{"acknowledged": bool, "vacuum_entity_id", "scope"}`.

Does not affect the upstream device — the next error event re-populates whichever latch was cleared.

### `get_recent_errors`

Returns the last N entries from the per-device recent-error ring buffer (max 50).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `limit` | No | Number of entries to return. Default `20`, max `50`. |

Supports response. Returns `{"vacuum_entity_id", "errors": [...], "count": int}`.

---

## Maintenance

These services write maintenance state. To read current maintenance status use `get_upkeep_snapshot` (State Inspection section).

### `reset_maintenance`

Records that a maintenance component has been cleaned or replaced, resetting its integration-tracked usage counter.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `component` | Yes | Component ID as declared in the adapter's `maintenance_components` block (e.g. `"side_brush"`, `"filter"`). Valid values: `brush`, `side_brush`, `filter`, `mop`, `sensor`. |

Supports response.

### `set_maintenance_interval`

Persists a custom maintenance interval for one component, overriding the adapter's factory default. The same value is written to the backing `EufyVacuumMaintenanceIntervalNumber` entity so the card editor and the HA number entity stay in sync.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `component` | Yes | Component ID. |
| `interval_hours` | Yes | Replacement interval in hours. The backend handler trusts its caller and does **not** clamp this against any declared maximum — range validation against the adapter's default/max is done card-side in the UI before the service is called. (The backing number entity does clamp to its own min/max.) |

Supports response.

---

## Access Graph

The access graph models rooms that can only be reached by passing through other rooms. These services drive the access graph editor in the panel.

### `get_room_access_editor`

Returns the editor payload for one room's access-graph configuration.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |
| `room_id` | Yes |

Supports response.

### `get_access_graph_health`

Validates the whole-map access graph and returns a health report identifying unreachable rooms, cycles, or misconfigured dock-room settings.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

Supports response.

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
| `map_id` | Yes | |
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
| `map_id` | Yes | |
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
| `map_id` | Yes | |
| `started_at` | Yes | Job start timestamp in `YYYY-MM-DDTHH:MM:SS` format. |
| `battery_start` | Yes | Battery percent at job start (0–100). |
| `job_id` | No | Optional custom job ID. |

### `finalize_learning_job`

Manually finalizes a completed job and optionally rebuilds learned stats. Called automatically when the vacuum returns to dock — manual use is needed for edge cases or historical corrections.

Fires `eufy_vacuum_job_finished` on completion. Also fires `eufy_vacuum_run_incomplete` if the job ended with rooms unvisited.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
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

These services gate on dock and vacuum state before issuing the upstream command. If the dock is not in a valid state the service raises a `ServiceValidationError` with a human-readable reason — it does **not** fail silently. The error surfaces in the HA service call UI and will propagate to automations that do not suppress errors. Use `get_dock_action_status` first to check availability before calling these from automations.

### `wash_mop`

Runs the dock wash action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `dry_mop`

Runs the dock dry action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `stop_dry_mop`

Stops an active dock drying cycle. Only runs when the dock is actively drying.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `empty_dust`

Runs the dock dust-empty action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

### `get_dock_action_status`

Returns gated availability and blocked reasons for `wash_mop`, `dry_mop`, and `empty_dust`. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

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

## Setup Services

These services drive the setup panel's onboarding flow. Under normal operation the panel calls them for you. Power users and developers can call them directly from automations or scripts, but most of the time you will interact with them through the card's setup UI rather than the service developer tools.

All setup services support response.

### `setup_get_status`

Returns the current setup state that drives which panel view to render. Takes no parameters.

**Returns:**

| Field | Description |
|---|---|
| `setup_complete` | Boolean — `true` only when all managed vacuums have completed all adapter-declared setup steps and all room maps are in sync (no new or removed rooms pending). |
| `vacuums` | List of per-vacuum status objects. See below. |
| `state` | Legacy field: `no_vacuums`, `no_map`, or `ready`. |
| `next_actions` | Legacy field: suggested next steps for the panel. |

Each entry in `vacuums` contains:

| Field | Description |
|---|---|
| `vacuum_entity_id` | |
| `display_name` | |
| `setup_steps` | List of `{id, label, completed, service}` for each step the adapter declared. |
| `next_step` | Step ID of the first incomplete step, or `null` when all done. |
| `room_drift` | `{in_sync, new_rooms, removed_rooms, transiently_missing, rejected_rooms}` — reflects stored drift history, not a live probe. |
| `maps` | Per-map summary list including room count, protection level, and import status. |
| `has_imported_map` | Legacy field. |

### `setup_add_vacuum`

Registers a vacuum entity with the integration manager. Idempotent — returns `"already_done"` if the vacuum is already managed. Returns `"blocked"` if the entity does not exist in the HA state machine.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

**Returns:** An ActionResult dict with `status`, `message`, `data`, and `next_actions`.

### `setup_import_active_map`

Discovers rooms from the upstream vacuum integration for a vacuum's currently active map and imports them into the integration. This is the first step after adding a vacuum — it populates the room list the card will manage.

Only the currently active map can be imported. This is a hard limitation of the upstream cloud API — there is no way to query alternate or historical maps.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

**Returns:** An ActionResult dict with `status`, `message`, `data`, and `next_actions`.

### `setup_get_map_rooms`

Returns the list of managed rooms for a specific vacuum and map. Used by the setup panel to show the current room state so the user can review before saving.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | Yes |

**Returns:** `{"vacuum_entity_id": ..., "map_id": ..., "rooms": [...]}`.

### `setup_save_rooms`

Saves a set of room IDs as managed rooms for a vacuum and map, optionally setting floor types. This is the commit step of the onboarding flow — rooms become managed and available for queue building after this call.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
| `enabled_room_ids` | No | List of integer room IDs to save. Omit to keep existing. |
| `floor_types` | No | Dict mapping room ID to floor type. Valid values: `hardwood`, `laminate`, `tile`, `marble`, `carpet`. |

**Returns:** `{"status": "success", "room_count": N}` on success.

### `setup_delete_map`

Deletes one imported map and all related integration data (rooms, queue, job records, learned history) for that map. This is an integration-only operation — it does not affect upstream cloud data.

Delete operations are protection-gated. Maps with significant data (active jobs, learning history, automation rules) require a `confirmation_token` matching the map display name exactly before the delete proceeds.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | |
| `confirmation_token` | No | Required for high-protection maps. Must match the map display name exactly. For elevated-protection maps any truthy string is accepted. |

**Returns:** An ActionResult dict. Returns `status: "requires_confirmation"` with a `code` of `"typed_confirmation_required"` or `"confirmation_required"` when the token is missing for a protected map. Returns `status: "blocked"` with code `"confirmation_mismatch"` when a typed token is provided but does not match.

> **Risk:** Irreversible. All learned history for the map is permanently deleted.

### `setup_reject_rooms`

Marks one or more discovered room IDs as rejected — they will never surface again in the new-rooms drift list even if the vacuum continues to report them. Also removes them from managed rooms across all maps so their HA entities are torn down.

Use this for phantom rooms that your vacuum reports but that do not correspond to real cleaned spaces (firmware artifacts, stairwells, etc.).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_ids` | Yes | List of integer room IDs to reject. |

**Returns:** `{"status": "success", "rejected": [...], "removed_from_managed": [...], "affected_map_ids": [...]}`.

### `setup_force_remove_room`

Bypasses the missing-pass counter and immediately flags a room as removed in the drift signal. The room remains in managed rooms (history is preserved); only the drift status flips to confirm-removed.

Use this for the "I know this room is gone" manual action when you do not want to wait for the natural three-pass removal confirmation cycle.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `room_id` | Yes |

**Returns:** `{"status": "success", "room_id": int, "missing_passes": int, "threshold": int}`.

---

## Adapter Configuration

These services manage the brand-adapter config layer. Under normal operation the panel calls them automatically. Call them directly when building or debugging a custom adapter for a non-Eufy brand.

### `get_adapter_config`

Returns the currently registered adapter config for one vacuum.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Supports response. Returns `{"vacuum_entity_id", "config", "source", "adapter_id"}`.

### `save_adapter_config`

Persists a UI-built adapter config for one vacuum and registers it immediately. Overwrites any previously stored config for the same vacuum. The code adapter (if applicable) will overwrite this again on the next integration reload.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `config` | Yes | Full adapter config dict matching `ADAPTER_CONFIG_SCHEMA`. Must include `adapter_id` and `dispatch.template`. |

### `delete_adapter_config`

Removes a stored adapter config for one vacuum and unregisters it from the active registry.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

### `discover_adapter_entities`

Scans the HA entity registry for all entities whose entity ID contains the vacuum's object ID. Returns them grouped by domain to help identify which entities to map to adapter roles.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Supports response. Returns `{"vacuum_entity_id", "entity_count", "entities": [...], "by_domain": {...}}`.

### `observe_entity_states`

Returns the current states and attributes for a list of entity IDs. Used when building vocabulary mappings (e.g. observing all possible dock_status values while the dock runs through a cycle).

| Parameter | Required |
|---|---|
| `entity_ids` | Yes |

Supports response. Returns `{"observations": [{entity_id, state, attributes}], "entity_count"}`.

### `get_vacuum_capabilities`

Detects and returns capability flags for one vacuum by probing the HA entity registry. Optionally re-registers the capability detection result with the adapter registry.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `detected_model` | No | Model code to hint model-family detection. |
| `refresh` | No | Re-register detected caps with the adapter. Default `true`. |

Supports response.

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

## Events Reference

These events are fired by the integration. Use them as automation triggers.

| Event | Fired when |
|---|---|
| `eufy_vacuum_job_finished` | A job is finalized (completed, cancelled, or failed). Payload includes `job_id`, `status`, `vacuum_entity_id`, `map_id`. |
| `eufy_vacuum_run_incomplete` | A cancelled or interrupted job left at least one queued room uncleaned. Payload includes `missed_room_ids` and `missed_rooms`. Use with `retry_missed_rooms`. |
| `eufy_vacuum_room_started` | The vacuum begins cleaning a room (job lifecycle timing rollover). |
| `eufy_vacuum_room_finished` | The vacuum finishes cleaning a room (job lifecycle timing rollover). |
| `eufy_vacuum_room_completed` | Position-based room exit detected by the mapping tracker. Fired when the robot's coordinates leave a room's boundary. |
| `eufy_vacuum_path_blocked` | Blocker rules changed mid-run and remaining rooms became inaccessible. |
| `eufy_vacuum_stall_detected` | The robot has been in a room for 2× its learned timing threshold. Payload includes `elapsed_minutes`, `expected_minutes`, and `stall_ratio`. Fires at most once per room per job. |
