# 03 — Services Reference

All services are registered under the `eufy_vacuum` domain. Call them as `eufy_vacuum.<service_name>`.

Services that `supports_response` return a data payload you can capture with `response_variable` in a script or automation action. Services that do not support response run fire-and-forget.

Most services require at least `vacuum_entity_id`. Services that operate on a specific map also accept `map_id`, but it is optional — when omitted, it auto-resolves to the vacuum's currently active map (via the adapter's declared `active_map` entity). Pass it explicitly only when you need to target a stored secondary map. Both fields are noted in each section.

---

## Job Control

These services start, pause, resume, and cancel the integration-managed active job. All of them support response — pass `response_variable` to read the outcome rather than inferring it from entity state afterwards.

### `start_selected_rooms`

Sends the resolved cleaning payload to the vacuum and starts the job. Honors room blockers, access-graph dependencies, modifier rules, and reduced-run confirmation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `confirm_reduced_run` | No | Set `true` to allow a reduced run (some rooms blocked) to proceed without a separate confirmation step. |
| `confirm_token` | No | Retry token returned by a prior `confirmation_required` response. Alternative to `confirm_reduced_run`. |
| `path_block_action` | No | What to do if blocker rules change mid-run and remaining rooms become unreachable. Values: `event_only`, `pause_and_event`, `cancel_and_event`. |
| `pause_timeout_minutes_override` | No | Override the default pause timeout for this job only. Set to `0` to disable auto-cancel for this run. |
| `strict_order` | No | Boolean. Clean rooms strictly in queue order via sequenced one-room-at-a-time dispatch — the next room starts only after the previous one finishes. Only affects brands that otherwise path-optimize and ignore the dispatched order (Roborock); a no-op for order-honoring brands (Eufy). Slower, since it adds a dock trip between rooms. |

If blockers or access rules would reduce the room list, the service returns `confirmation_required: true` with a `confirm_token` unless you pass `confirm_reduced_run: true` or a valid token.

Supports response — pass `response_variable` in an automation to read `started`, `reason`, and `message` (and `confirmation_required`/`confirm_token`/`preflight` when a confirmation is needed). A refusal at this actual dispatch — distinct from `get_start_status`'s earlier readiness check above, which a concurrent job can race — is `started: false` with a `reason`, never an exception.

### `pause_active_job`

Pauses the vacuum and marks the integration-owned active job as paused.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `resume_active_job`

Resumes the vacuum and the paused job.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `cancel_active_job`

Returns the vacuum to base, finalizes the active job as cancelled, and emits the `eufy_vacuum_job_finished` event.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `start_zone_clean`

Dispatches an ad-hoc free-form zone clean — draw one or more boxes on the live map, clean only inside them. This is fire-and-forget: it carries no room IDs and does **not** touch the active job, queue, or learning store, so there is no job tracking, no completion event, and nothing is persisted.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Accepted and auto-resolved, but **not** forwarded to the device — the provider cleans on its current map. |
| `zones` | Yes | List of zone rectangles. Each is exactly four floats `[x0, y0, x1, y1]`, normalized `0–1` to the live-map image with a top-left origin. Minimum one zone. Values are not hard-clamped here — a drag to the image edge can land slightly outside and the provider clamps. |
| `clean_times` | No | Number of passes over the zones, `1`–`10`. Default `1`. |

Supports response.

### Saved Zones

Named, persisted clean regions stored per map. Unlike `start_zone_clean` (ad-hoc, nothing persisted), a saved zone keeps its geometry and can be re-cleaned by ID. These six services create, rename, delete, file, and clean saved zones. Every one requires `map_id` explicitly — it is **not** auto-resolved from the active map — and all support response.

Geometry is a list of at least three `[x, y]` points, each normalized `0–1` to the map image with a top-left origin (clamped server-side). The two clean services are **active-map-guarded** (a zone's geometry is only valid on its own map) — they return `{"cleaned": false, "reason": "map_not_active", "active_map_id": ...}` when a different map is loaded — and are fire-and-forget: like `start_zone_clean`, they touch no job, queue, or learning store. The clean geometry sent to the device is each zone's normalized bounding box, dispatched through the shared zone-clean path that enforces the per-brand zone count and size caps.

#### `create_saved_zone`

Creates and stores a named saved zone from drawn geometry.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `name` | Yes | Display name for the zone. |
| `geometry` | Yes | List of at least three `[x, y]` points, each normalized `0–1` to the map image (top-left origin). |
| `kind` | No | Zone kind. Only `clean` is currently accepted — no dispatch path reads any other value, so the schema rejects anything else rather than accept a value that would silently be dispatched as a clean anyway. Defaults to `clean`. |

Supports response.

#### `rename_saved_zone`

Updates a saved zone's display name.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `zone_id` | Yes | The zone to rename. |
| `name` | Yes | New display name. |

Supports response.

#### `delete_saved_zone`

Deletes a saved zone.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `zone_id` | Yes | The zone to delete. |

Supports response.

#### `set_saved_zone_room`

Files a saved zone under a room (or clears it to Unassigned). **Filing only** — this never affects the clean dispatch; it only buckets the zone in the panel.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `zone_id` | Yes | The zone to file. |
| `room_number` | No | Integer room number to file the zone under. Pass `null` or omit to clear it to Unassigned. |

Supports response.

#### `clean_saved_zone`

Cleans a single saved zone. Resolves the zone's geometry to its normalized bounding box and dispatches an ad-hoc zone clean over it. Active-map-guarded and fire-and-forget (same as `start_zone_clean`).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `zone_id` | Yes | The zone to clean. |
| `clean_times` | No | Number of passes. Minimum `1`. Default `1`. |

Supports response. Returns `{"cleaned": true, "zone_id", "dispatch": ...}`, or `{"cleaned": false, "reason": ...}` on `zone_not_found`, `bad_geometry`, `map_not_active`, or `active_map_indeterminate` (the active map could not be resolved).

#### `clean_saved_zones`

Cleans several saved zones together in **one** dispatch — the selected set is fired as a single zone-clean run. Same active-map guard as `clean_saved_zone`. The per-brand zone count and size caps are enforced inside the shared dispatch. **Atomic:** any missing or bad-geometry zone in the set refuses the whole batch.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `zone_ids` | Yes | List of zone IDs to clean together (minimum one). |
| `clean_times` | No | Number of passes. Minimum `1`. Default `1`. |

Supports response. Returns `{"cleaned": true, "zone_ids", "zone_count", "dispatch": ...}`, or `{"cleaned": false, "reason": ...}` on `zone_not_found`, `bad_geometry`, `no_zones`, `map_not_active`, or `active_map_indeterminate` (the active map could not be resolved).

---

## Queue Building

Use these services to configure which rooms are cleaned and in what order, then call `start_selected_rooms` to launch the job. All of them support response. The four break services and `add_queue_zone` merge the resulting queue state into their own result, so a read-modify-write round trip needs no separate read afterwards.

### `build_queue`

Builds the cleaning queue from all currently enabled rooms in their configured order.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Call this after changing room settings or enabling/disabling rooms, before calling `start_selected_rooms`.

### `build_room_payload`

Builds the resolved per-room cleaning payload — the exact per-room settings as they would be sent to the vacuum — without rebuilding the queue. This is the payload-side counterpart to `build_queue`; inspect the result with `get_payload_state`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_queue_steps`

Returns the live queue as an ordered **steps** list — room groups interleaved with the charge, wait, and zone steps inserted into it — in exactly the shape a saved run profile uses. This is the read side of the four break services below, and the read half of a read-modify-write round trip with `set_queue_breaks`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Supports response. Returns:

| Field | Description |
|---|---|
| `steps` | Ordered list. A room group is `{"type": "room_group", "rooms": [{room_id, name, slug, order, profile_name}, ...]}`; an inserted step is `{"type": "charge_wait", "target_battery_percent": ...}`, `{"type": "wait", "wait_minutes": ...}`, or `{"type": "zone", "zone_ids": [...]}`. |
| `breaks` | The raw ordered inserted steps as `{after_index, step}` — the write shape `set_queue_breaks` accepts back unchanged. |
| `has_breaks` | `true` when the queue is stepped rather than flat. A zone step counts. |

### `add_queue_break`

Inserts a **charge** or **wait** break into the live queue, turning a flat clean into a stepped one. The next `start_selected_rooms` runs the whole stepped sequence as one job.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `break_type` | Yes | `charge_wait` (dock and charge to a battery percentage) or `wait` (hold for a number of minutes). Zone steps have their own service, [`add_queue_zone`](#add_queue_zone). |
| `after_index` | Yes | The break sits after this many enabled rooms — `1` means after the first room. Clamped to `1`–(room count − 1): a charge or wait break must sit **between** two rooms, so it can neither lead nor trail. |
| `target_battery_percent` | For `charge_wait` | `1`–`100`. Required when `break_type` is `charge_wait`; passing a `charge_wait` without it is rejected by the schema rather than silently dropped. |
| `wait_minutes` | For `wait` | `1`–`1440`. Required when `break_type` is `wait`, on the same rule. |

Supports response. Requires at least two enabled rooms. Returns `{"added": true}` merged with the same payload `get_queue_steps` returns, or `{"added": false, "reason": ...}` on `needs_two_rooms` or `invalid_break`.

### `remove_queue_break`

Removes one inserted step from the live queue by its position in the `breaks` list.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `index` | Yes | Zero-based position in the `breaks` list returned by `get_queue_steps`. |

Supports response. Returns `{"removed": true}` merged with the live stepped-queue state, or `{"removed": false, "reason": "index_out_of_range"}`.

### `set_queue_breaks`

Replaces **all** inserted steps on the live queue in one call — the single primitive behind reordering steps and editing their charge percentage or wait minutes. Send the full desired list; the stored list is replaced wholesale, so there is no per-entry index shift to reason about.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `breaks` | Yes | Ordered list. Each entry is `{after_index, break_type, ...}` where `break_type` is `charge_wait`, `wait`, or `zone`, plus `target_battery_percent`, `wait_minutes`, or `zone_ids` to match. The read shape `get_queue_steps` returns (`{after_index, step: {type, ...}}`) is also accepted, so a get → edit → set round trip can send entries back unchanged. |

`after_index` is clamped per kind: a charge or wait step to `1`–(room count − 1), a zone step to `1`–room count (a zone may trail after the last room, since it is a real clean rather than a pause). Neither kind may lead — a run always opens with a room. Entries that fail validation are dropped; ties on `after_index` keep the order you sent.

Supports response. Returns `{"set": true}` merged with the live stepped-queue state, or `{"set": false, "reason": "needs_two_rooms"}` — in which case the stored steps are cleared, since breaks are meaningless on a queue of fewer than two rooms.

### `clear_queue_breaks`

Removes every inserted step — the queue drops back to a flat clean.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Supports response. Returns the live stepped-queue state (the same shape as `get_queue_steps`).

### `add_queue_zone`

Inserts a **zone step** into the live queue — the named [saved zones](#saved-zones) are cleaned together as one phase, positioned between rooms. Unlike `clean_saved_zones` (an immediate dispatch, not part of the queue), a queued zone step runs as part of the job the next `start_selected_rooms` launches.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `after_index` | Yes | Number of enabled rooms before the zone step. Clamped to `1`–room count: a zone may sit between rooms or trail after the last room (`after_index` = room count), but never leads — a run always opens with a room. |
| `zone_ids` | Yes | List of saved-zone IDs to clean together in this step. Zone existence and the per-brand zone count/size caps are enforced at dispatch time, not at insert time. |

Supports response. Requires at least two enabled rooms in the queue. Returns `{"added": true}` merged with the live stepped-queue state, or `{"added": false, "reason": ...}` on `invalid_zone` (empty or unusable `zone_ids`) or `needs_two_rooms` (fewer than two enabled rooms).

### `start_run_profile`

Applies a saved run profile, rebuilds the queue from it, and starts cleaning — all in one call. This is the recommended way to launch a named preset from an automation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `profile_id` | Yes | ID of the saved run profile to apply. |
| `strict_order` | No | Boolean. Clean the profile's rooms in its saved order on a brand that would otherwise optimize its own route. **Leave it out to use the profile's own saved setting**; set it here to override that profile for this run only, in either direction. A no-op for order-honoring brands (Eufy). |
| `confirm_reduced_run` | No | Allow a blocker-reduced run without interactive confirmation. |
| `confirm_token` | No | Retry token from a prior `confirmation_required` response. |
| `path_block_action` | No | `event_only`, `pause_and_event`, or `cancel_and_event`. |
| `pause_timeout_minutes_override` | No | Per-job pause timeout override in minutes. `0` disables auto-cancel. |

Returns the same shape as `start_selected_rooms`, including `confirmation_required` when blocker rules reduce the run and neither `confirm_reduced_run` nor a valid `confirm_token` is provided. When the profile carries charge or wait stops (see [`set_run_profile_steps`](#set_run_profile_steps)), this launches the whole stepped sequence — the run is forced into strict order so each group's rooms clean in the exact order shown.

### `update_room_fields`

Applies per-room field overrides without requiring a named profile. Only the fields you supply are changed; everything else stays as-is. Sets the room's `profile_name` to `custom` to signal divergence from a preset.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `room_id` | Yes | |
| `enabled` | No | Enable or disable the room for queue and payload generation. |
| `clean_mode` | No | |
| `fan_speed` | No | |
| `water_level` | No | |
| `clean_intensity` | No | |
| `clean_passes` | No | `1` or `2`. |
| `edge_mopping` | No | |
| `color` | No | Per-room map fill-color override. A `#rrggbb` (or `#rgb`, or bare hex without `#`) string, normalized to canonical `#rrggbb`. Pass `null` or an empty string to clear the override. Omitting `color` leaves any existing override intact. |
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
| `map_id` | No |

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
| `enabled_room_ids` | No | List of integer room IDs to save as managed rooms. **Omit the key to keep the current selection unchanged.** `null` and an empty list are rejected with a validation error rather than being treated as "delete every room" — removing rooms goes through per-room enabled flags or map deletion. |
| `floor_types` | No | Dict mapping room ID to floor type. Valid values: `hardwood`, `laminate`, `tile`, `marble`, `granite`, `concrete`, `carpet_low_pile`, `carpet_high_pile` — carpet pile is part of the compound value, not a separate field (legacy stored `carpet` values are migrated to `carpet_<pile>` at load). A room enabled in this call **without** a floor-type entry is saved but leaves the room record's own `is_configured` flag unset unless a prior save already set it. |

Every room passed here — regardless of whether it has a `floor_types` entry — also has the separate onboarding `floor_types_confirmed` flag stamped for it, so this call always clears the onboarding floor-type-confirmation gate for these rooms even when `is_configured` stays unset.

Room IDs rejected via `setup_reject_rooms` on this map are refused re-creation (skipped) unless the room is already configured.

### `get_vacuum_maps`

Returns all imported maps for a vacuum with room counts and display names.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Supports response.

### `reconcile_room`

The apply/dismiss control for the room-identity reconciliation reviews surfaced by `discover_rooms` — a known room whose segment ID changed (a brand re-segment renumbering, e.g. Roborock), a known ID whose name changed, or both at once. A re-segment renumbers many rooms together, so this is one per-map decision, not a per-room prompt. `migrate` atomically rebuilds the saved rooms onto the new IDs, carrying each room's durable settings by name slug and rewriting the access-graph grants; `ignore` dismisses the reviews without changing anything (the dismissal is fingerprinted, so a later genuinely-different review still surfaces).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `action` | No | One of `migrate` or `ignore`. Default `migrate`. |
| `plan_token` | For `migrate` | The opaque fingerprint of the reviews you are confirming — read it from the cached discovery's `reconciliation.plan_token`, surfaced per-vacuum by `setup_get_status`. Round-trip it, never parse it. Optional at the schema level (`ignore` needs none), but a `migrate` without it is refused. |
| `force` | No | Default `false`. Only meaningful with `migrate`: a migration is refused with `skipped: "partial_discovery_refused"` when the new discovery is both smaller than what is stored **and** would drop more than half the stored rooms — that usually means a stale or bad discovery, not a real re-map. Set `true` to proceed for a genuine re-map that really did shrink the room count. |

Supports response. A `migrate` whose token is missing or no longer matches the current discovery raises a `ServiceValidationError` (`plan_token_required` / `plan_changed`) — re-run `discover_rooms` and review again before retrying. A `migrate` against an empty cached discovery returns `skipped: "no_discovery"` without touching saved rooms.

---

## Map Services

These services manage map image uploads, segmentation (CV or manually authored), named custom layouts, custom segment authoring, and the map UI overlay state — segment-to-room links and the animated companion's anchor positions. The card calls them from the Map Configuration panel and the custom-segment composer; you can also call them from developer tools or scripts.

`map_id` is not uniform across this section, so read each service's table rather than assuming. The split is deliberate:

- **Services that address a map you name** — the image, segmentation, and custom-layout services (`upload_map_image`, `delete_map_image`, `analyze_map_image`, `get_map_segments`, `adjust_map_segment`, `set_segmentation_mode`, `set_custom_segments`, and the four `*_custom_layout` services) — **require `map_id`**. There is no auto-resolution: they replace or delete stored content, so an omitted map would have to be guessed.
- **Services that write display or overlay state** — `set_segment_room_link`, `set_companion_anchor`, `set_hidden_regions`, `set_live_map_rotation`, `set_furnished_art_placement`, `set_furnished_render_mode`, `set_room_viewport` — accept an **optional `map_id`**. Omitted, it resolves to the vacuum's active map, then to the first stored map; if neither exists the call refuses with `{"saved": false, "reason": "no_map"}` rather than inventing one. A `map_id` you *do* pass must name a map that exists — an unknown ID refuses with `{"saved": false, "reason": "map_not_found", "known_maps": [...]}` instead of silently creating an empty bucket for it. `set_map_overlay_visibility` resolves an omitted `map_id` the same way but reports its refusal as `{"saved": false, "error": "no_map"}`, and does not refuse an unknown ID.
- **Vacuum-scoped services** — `acknowledge_map_frame`, `get_map_render_data`, `get_map_live_pose`, `compare_map_sources` — take no `map_id` at all.

All of these services support response.

> **Calling these by hand:** `upload_map_image`, `delete_map_image`, `analyze_map_image`, and `get_map_segments` are registered in Python only (no `services.yaml` entry), so Developer Tools → Actions lists them but shows no field descriptions or autocomplete — call them in YAML mode. The parameter tables below come from the integration's schemas and are authoritative regardless.

The `segmentation_mode` flag (`cv` or `custom`) selects which segmentation a map serves on read. Switching modes is a pointer flip — it never re-runs the segmenter.

**CV** lives at the map-bucket level: a single `image_segments` store (the CV segmenter's output) plus its own `segment_room_links` and `companion_anchors`.

**Custom** is now a *named collection*. A map can hold many `custom_layouts` side by side — each a fully self-contained authoring surface keyed by `layout_id`, with its own backdrop image (variant `custom_<layout_id>`), authored `custom_segments`, `segment_room_links`, and `companion_anchors` (including the reserved `dock` mascot spot). A per-map `active_custom_layout_id` names which layout custom mode currently serves. Because room links are per-layout, two layouts can each carry a segment `living` linked to *different* rooms — impossible under the old single-store model.

Reads and writes in custom mode are scoped to the **active** custom layout; in CV mode they use the map-bucket stores. The integration resolves this once (`_resolve_active_scope`) so `get_map_segments`, `set_segment_room_link`, and `set_companion_anchor` all route to the right place and CV/custom never drift. `set_custom_segments` is the deliberate exception: as a destructive replace-all it names its target layout explicitly via a required `layout_id` instead of following the active pointer. The legacy single `custom_segments` key from before named layouts is folded **lazily and non-destructively** into a default `Custom` layout on first touch — the old key is kept, never deleted, and the migration is idempotent.

### Image Management

#### `upload_map_image`

Uploads a map background image variant. The `default`, `dark`, and `light` variants feed the CV segmenter (`dark` is the primary input; `light` assists with wall detection). The `custom` variant is the legacy single-store backdrop for the manual segment composer and is **never** auto-segmented — its recorded pixel dimensions become the canvas the custom-segment writer rasterises against. Each named custom layout owns its own per-layout backdrop under variant `custom_<layout_id>` — pass `layout_id` to target it. Non-PNG uploads are converted to PNG before storage.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `image_base64` | Yes | Base64-encoded image. Converted to PNG if not already. |
| `variant` | No | `default`, `dark`, `light`, `custom`, or a per-layout `custom_<layout_id>`. Default `default`. |
| `layout_id` | No | Targets a named custom layout's backdrop. When supplied, the server **forces** `variant` to `custom_<layout_id>` (ignoring any `variant` you pass) and repoints that layout's `backdrop_variant`. The layout must already exist — returns `{"saved": false, "reason": "layout_not_found"}` otherwise. |
| `art_scope` | No | `home` or `room`. Switches the upload from a **backdrop** to a **furnished-art** image: it writes variant `custom_<layout_id>_home_art` (scope `home`) or `custom_<layout_id>_room_<room_id>` (scope `room`) and points the active layout's `home_art.art_variant` / `rooms[<room_id>].art_variant` at it — the layout's `backdrop_variant` is **left untouched**. Requires `layout_id`; scope `room` also requires `room_id`. See [Furnished Render](#furnished-render). |
| `room_id` | When `art_scope=room` | The room the per-room furnished art belongs to. |
| `image_width` | No | Declared pixel width. The stored variant records the image's actual measured dimensions; for a custom/per-layout backdrop these define the rasterise canvas. |
| `image_height` | No | Declared pixel height. |

Supports response. Returns the saved variant's `path`, `browser_url`, measured `actual_width`/`actual_height`, and `size_bytes`. Returns `{"saved": false, "reason": ...}` on `invalid_base64` or `unsupported_format`.

#### `delete_map_image`

Deletes one stored image variant — both the PNG file and its entry in the map's `image_variants`. Backs the per-variant trash button so a bad upload can be dropped without deleting the whole map. Safe to call repeatedly.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `variant` | No | `default`, `dark`, `light`, `custom`, or a per-layout `custom_<layout_id>`. Default `default`. |

Supports response. Returns `{"deleted": true, "file_removed": bool, "remaining_variants": [...]}`, or `{"deleted": false, "reason": "not_found"}` when the variant is not recorded.

### Segmentation

#### `analyze_map_image`

Runs the CV segmenter on the map image and caches the result as `image_segments`. Probes the `dark` variant first, then falls back to `default`; the `light` variant is used as an assist when present. The `custom` variant is never read, so a custom-only map is never auto-segmented. Re-analysis preserves the user's `segment_room_links` and `companion_anchors`.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `expected_room_count` | No | Target room count hint (`>= 1`). |
| `max_segments` | No | Cap on the number of segments (`>= 1`). |
| `min_area_pixels` | No | Minimum segment area in pixels (`>= 1`). Default `1200`. |
| `simplify_epsilon` | No | Polygon simplification epsilon. |
| `force_reanalyze` | No | Re-run even when a cached result exists. Default `false`. |

Supports response. Returns the segments payload (the cached result enriched with `segment_room_links` and `companion_anchors`). With `force_reanalyze: false` and an existing cache, returns the cached payload without re-running. Returns `{"available": false, "reason": "image_not_found"}` when no `dark`/`default` image is stored.

#### `get_map_segments`

Returns the active segmentation for a map — whichever store `segmentation_mode` selects — plus room links, companion anchors, and image metadata. In CV mode this is the map-bucket `image_segments`; in custom mode it is the **active** custom layout's `custom_segments`, links, and anchors. Reading is pure and never invokes the segmenter. Per-segment `polygon_pct` (0–100 percentage coordinates), stored adjustments, and any `room_id` link are derived at read time.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |

Supports response. Returns `segmentation_mode` (`cv` or `custom`), `available`, `analyzed_at`, `image`, `image_variants`, a `summary` (with `segment_count` and `adjusted_count`), `segments` (each carrying `polygon_pct` and, when linked, `room_id`), `adjustments`, and `companion_anchors` (all scoped to the active store). It also returns `active_custom_layout_id`, `segment_room_links` (the active scope's link dict), and `custom_layouts` — a list of layout summaries, each `{id, name, backdrop_variant, backdrop_source, segment_count, created_at, updated_at, render_mode, home_art, rooms}` (the last three carry the per-layout **furnished-render** state — see [Furnished Render](#furnished-render)) — so the card can render the layout picker and the furnished panel without a second fetch.

#### `set_segmentation_mode`

Toggles a map between CV (auto-detected) and Custom (manually authored) segmentation.

> **Invariant:** this only flips the `segmentation_mode` flag. It never re-runs the segmenter in either direction, and both the `image_segments` and `custom_segments` stores are left untouched — so `cv → custom → cv` preserves each set with zero re-analysis.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `mode` | Yes | `cv` (auto-detected segments) or `custom` (authored polygons). |

Supports response. Returns `{"saved": true, "mode": ..., "segment_count": N}` where the count reflects the now-active store.

#### `set_custom_segments`

Authors no-CV map segments from primitive shapes — **replace-all** into **one named custom layout**. Rebuilds the `layout_id` layout's `custom_segments` store from the supplied list. The target layout must be named explicitly and must already exist — there is no active-layout fallback and no auto-create, precisely because a destructive replace-all must never land on whichever layout happened to be active. Each segment's primitives are rasterised server-side (via `rasterize_primitives` → `mask_to_polygon`, the same polygon tracer the CV path uses) onto a `1`-bit mask, scaled to the target layout's backdrop pixel dimensions, and wrapped in the same segment shape the CV segmenter produces — so room-linking and dispatch treat custom and CV segments identically. Requires the target layout's backdrop to be uploaded (for the canvas dimensions), **or** explicit `backdrop_width`/`backdrop_height` for a live-pinned layout that has no uploaded backdrop. Never runs the segmenter.

One segment is one room. Multiple primitives in a segment merge into a single room; a primitive with `op: subtract` carves material away (an edge cut yields a concave simple polygon; an interior hole cannot be represented by one polygon). Primitives are applied in list order. Degenerate segments (nothing drawn, or the result collapses) are dropped.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `layout_id` | Yes | The custom layout whose segments to replace. A blank value returns `{"saved": false, "reason": "layout_id_required"}`; an unknown ID returns `{"saved": false, "reason": "layout_not_found"}` — nothing is auto-created. |
| `segments` | Yes | List of `{id?, primitives: [...]}`. Extra keys are allowed and ignored. A stable `id` is preserved across re-saves (auto `custom_N` otherwise) so segment-room links survive. |
| `backdrop_width` | No | Rasterise-canvas width in pixels. For a live-pinned layout (no uploaded backdrop) the card sends the rendered live image's natural pixel size here so the writer has a canvas to rasterise against. |
| `backdrop_height` | No | Rasterise-canvas height in pixels. Same use as `backdrop_width`. |

Each primitive is `{type: rect|circle|polygon, op?: subtract, ...coords}` with coordinates as 0–100 percentages of the map:

- `rect` — `x`, `y`, `w`, `h`
- `circle` — `cx`, `cy`, `r`
- `polygon` — `points: [[x, y], ...]`

Primitives without `op` fill (union); `op: subtract` clears.

Supports response. Returns `{"saved": true, "segment_count": N, "skipped": N, "segment_ids": [...]}`, or `{"saved": false, "reason": ...}` on `layout_id_required`, `layout_not_found`, or `no_custom_backdrop` (the target layout has no uploaded backdrop and no `backdrop_width`/`backdrop_height` were supplied).

### Custom Layouts

A map's custom segmentation is a named collection of layouts. These four services create, rename, delete, and switch between them. The card surfaces them as the Auto (CV) / per-layout picker on the Map Configuration panel; you can also call them directly. All support response.

#### `create_custom_layout`

Creates a new named custom layout with empty segment, link, and anchor stores plus a fresh per-layout backdrop variant (`custom_<layout_id>`), activates it, and flips the map into custom mode so it goes live immediately.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `name` | No | Display name for the layout. Defaults to `Custom` when omitted or blank. |
| `backdrop_source` | No | Set to `"live"` to pin the layout to the brand's live-map image (stored as `backdrop_source: "live"` on the layout). A live-pinned layout always renders the live camera/image and ignores any uploaded backdrop, so you draw and link rooms straight over the live map. Omit for a normal layout backed by an uploaded backdrop. |

Supports response. Returns `{"saved": true, "layout_id": ..., "layout": {...}}` where `layout` is the new layout record (`id`, `name`, `backdrop_variant`, stores, `created_at`, `updated_at`). Upload its backdrop with `upload_map_image` passing the returned `layout_id` — except for a live-pinned layout, which needs no backdrop upload.

#### `rename_custom_layout`

Updates the display name of an existing custom layout. Does not touch its segments, links, anchors, or backdrop.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `layout_id` | Yes | The layout to rename. |
| `name` | Yes | New display name. |

Supports response. Returns `{"saved": true, "layout_id": ..., "layout": {...}}`, or `{"saved": false, "reason": "layout_not_found"}` when the ID is unknown (or `"missing_name"` when the name is blank).

#### `delete_custom_layout`

Deletes a custom layout along with its backdrop image (file and `image_variants` entry, best-effort). If the deleted layout was the active one, the active pointer is reassigned to the next remaining layout (ordered by name); if it was the last layout, `active_custom_layout_id` is cleared and the map flips back to `cv` mode so custom mode never has no store.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `layout_id` | Yes | The layout to delete. |

Supports response. Returns `{"saved": true, "deleted": true, "layout_id": ..., "active_custom_layout_id": ..., "segmentation_mode": ...}` so the card sees the new active layout and mode, or `{"saved": false, "reason": "layout_not_found"}` when the ID is unknown.

#### `set_active_custom_layout`

Activates a custom layout and flips the map into custom mode, so subsequent custom-scoped reads and writes resolve against it. Passing `null` or omitting `layout_id` (or an unknown ID) auto-creates and activates a default layout, guaranteeing custom mode always has a live store.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `layout_id` | No | The layout to activate. Omit, pass `null`, or pass an unknown ID to auto-create and activate a default layout. |

Supports response. Returns `{"saved": true, "active_custom_layout_id": ..., "mode": "custom"}`.

### Map UI Overlay State

#### `set_segment_room_link`

Persists or clears the link between a map segment and a managed room. Replaces the card's previous browser-localStorage storage, so links survive across browsers and devices. The mapping is enforced 1:1 — linking a room that is already attached to another segment drops the older link. The link is written to the **active store**: the map-bucket links in CV mode, or the active custom layout's own links in custom mode — so the same segment ID can map to different rooms in different layouts.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `segment_id` | Yes | e.g. `segment_4`. |
| `room_id` | No | Room to link. Pass `null` or omit to clear the link. |

Supports response. Returns `{"saved": true, "segment_id", "action": "set"|"cleared", "segment_room_links": {...}}` so the card can refresh in-memory state without a second fetch.

#### `set_companion_anchor`

Persists or clears the map position of the animated companion sprite for one room. When the vacuum is docked/idle the companion homes to the reserved `dock` key rather than a room; otherwise the anchor is keyed by room ID. With no anchor stored, the companion falls back to the linked segment's centroid. `pct_x`/`pct_y` are 0–100 percentages from the map image's top-left and are clamped to that range server-side. Like room links, anchors are written to the **active store** — the map-bucket anchors in CV mode, or the active custom layout's own anchors (including its own `dock` spot) in custom mode.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `room_id` | Yes | Target room ID, or the reserved string `dock` for the docked/idle home spot. |
| `pct_x` | No | X position (0–100%). Pass `null`/omit **both** `pct_x` and `pct_y` to clear the anchor. |
| `pct_y` | No | Y position (0–100%). |

Supports response. Returns `{"saved": true, "room_id", "action": "set"|"cleared", "companion_anchors": {...}}`.

#### `set_hidden_regions`

Replace-all the per-map hidden regions — normalized `[x0, y0, x1, y1]` rects (0–1 of the rendered image, top-left origin) drawn to mask map noise (e.g. porch noise off a room). Hidden regions are physical, so they are stored at the **map** level (not per CV/custom scope) and follow the map regardless of segmentation mode. Each entry is sanitised server-side — four finite numbers, clamped 0–1, ordered min < max, degenerate rects dropped. An empty or omitted `regions` clears them all.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `regions` | No | List of `[x0, y0, x1, y1]` rects (0–1). Omit or send an empty list to clear all hidden regions. |

Supports response. Returns `{"saved": true, "hidden_regions": [...]}` with the cleaned, stored list.

#### `adjust_map_segment`

Applies a per-segment geometry nudge to a CV segment — a whole-segment translate, per-edge grow/shrink, and/or individual vertex moves. Adjustments are stored against the map-bucket `image_segments` and are **cumulative**: each call's deltas add onto the segment's existing stored adjustment (a net-zero result drops that adjustment). Returns `{"saved": false, "reason": "segment_not_found"}` when the segment ID is unknown.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `segment_id` | Yes | The CV segment to adjust. |
| `delta_x` | No | Whole-segment translate in pixels. Default `0`. |
| `delta_y` | No | Whole-segment translate in pixels. Default `0`. |
| `edge_left` | No | Per-edge grow/shrink in pixels. Default `0`. |
| `edge_right` | No | Per-edge grow/shrink in pixels. Default `0`. |
| `edge_top` | No | Per-edge grow/shrink in pixels. Default `0`. |
| `edge_bottom` | No | Per-edge grow/shrink in pixels. Default `0`. |
| `vertex_moves` | No | List of `{index, delta_x?, delta_y?}` per-vertex nudges. |

Supports response.

#### `set_live_map_rotation`

Persists a display-only rotation for the live map — surfaced as `live_map_rotation` in the dashboard snapshot. The setting is backend-stored per map (so it follows the user across browsers and devices) and rotates the whole live-map layer together: the map image, room polygons, labels, and the animated companion. It does not affect segmentation or dispatch.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `rotation` | Yes | One of `0`, `90`, `180`, or `270` (degrees clockwise). |

Supports response.

#### `acknowledge_map_frame`

Force-clears the post-map-switch coordinate-frame gate for one vacuum — the backend behind the card's "Enable drawing anyway" control. After the active map switches, the map raster and room list update immediately but the robot's coordinate frame stays on the **old** map until the robot moves and re-localizes; while that gate is armed the card pauses zone drawing and map-tap room select, because any screen-to-device coordinate op would land in the wrong place. The gate clears itself once the robot's raw position moves past a movement threshold or the vacuum enters a `cleaning`/`returning` state; this service clears it immediately for a user who knows the robot is grounded (or accepts the risk). The override lasts until the **next** map switch re-arms the gate. Saved zones and the room list are never affected.

> Vacuum-scoped — takes only `vacuum_entity_id`, no `map_id`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Supports response. Returns `{"acknowledged": true, "vacuum_entity_id": ...}`.

#### `set_map_overlay_visibility`

Persists which overlay layers are shown on the map backdrop (display only — never affects segmentation or dispatch). Only the user's **deltas** are stored as `overlay_visibility` on the map bucket — a partial dict merged over the defaults at read time, so the shipped defaults can evolve without rewriting stored prefs. Visibility keys are validated against the known overlay layers, so a typo is rejected rather than silently stored. Pass `reset: true` to clear all deltas and fall back to the defaults.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `visibility` | No | Partial map of overlay-layer name to bool, merged over the stored deltas. Unknown layer keys are rejected. Omit on a reset. |
| `reset` | No | Clear all stored visibility deltas and fall back to the defaults. Default `false`. |

Supports response. Returns `{"saved": true, "map_id", "overlay_visibility": {...}}` with the fully-resolved visibility for the card.

### Live Map Source

These three read services back the card's own map render and its live moving overlays. They are served by the `MapSourceCoordinator` (`mapping/map_source_coordinator.py`, reached via the manager's `async_get_map_render_data` / `async_get_map_live_pose` / `async_compare_map_sources` delegators).

These three are **vacuum-scoped — they take only `vacuum_entity_id`, no `map_id`** (the coordinator resolves the live source itself). All support response.

#### `get_map_render_data`

Returns the raster plus decode parameters for the card's own map render — the on-demand fetch used when the brand's VA-rendered backdrop is selected. The card caches the result by the returned `version`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

#### `get_map_live_pose`

Returns only the live moving overlays — robot/dock anchors, current room, and heading — from the brand integration's fresh in-memory pose. This is the lightweight payload the card polls at the ~2-second live cadence, distinct from the full snapshot. Degrades gracefully when no live pose is available.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

#### `compare_map_sources`

Diagnostic verify probe: compares eufy-clean's in-memory `_map_data` against the `.storage` map data (rasters by length + SHA-1, per field) to confirm the in-memory bytes are byte-identical before repointing the map source to memory.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

### Furnished Render

These three write services back the **Furnished render** panel — a user-uploaded, to-scale home render aligned over the live map so the live robot/dock/path/room overlays ride on top (see the [Furnished render user guide](../user-guide/18-furnished-render.md)). They all operate on the map's **active custom layout** (returning `{"saved": false, "reason": "no_active_layout"}` when none is active) and all take an **optional `map_id`**, auto-resolved to the active map when omitted. The placement transform and viewport are resolution-independent percentage floats stored per-layout; each returns the resolved `furnished_render` so the card refreshes. All support response.

#### `set_furnished_art_placement`

Persists (or clears) the furnished-art placement transform `{tx, ty, scale, rotation}` on the active layout — the whole-home art (`scope: home`) or a per-room override (`scope: room`).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `scope` | Yes | `home` or `room`. |
| `room_id` | When `scope=room` | Returns `{"saved": false, "reason": "missing_room_id"}` if blank for a room scope. |
| `tx`, `ty` | No | Percentage offset of the art over the live frame. |
| `scale` | No | Multiplies the contain-fit size; clamped to `[0.05, 20]`. |
| `rotation` | No | Degrees. Stored in the natural (pre-live-rotation) frame so the art co-rotates with the overlays. |

Pass **all** of `tx`/`ty`/`scale`/`rotation` null (or omit them) to **clear** the placement (`{"action": "cleared"}`).

#### `set_furnished_render_mode`

Sets the render mode: `live` (art hidden, live map full), `art` (art full, live map faded to a ghost), or `blend` (art over a faded live map — the alignment view). Omit `room_id` (or pass it blank) for the **layout-level** default; pass it for a per-room override. An absent layout `render_mode` implies `live`.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `mode` | Yes | `live`, `art`, or `blend`. |
| `room_id` | No | Omit/blank = layout-level default; set = per-room override. |

#### `set_room_viewport`

Persists (or clears) a saved per-room viewport `{cx, cy, zoom}` (percentage floats) on the active layout, used to frame a single room.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `room_id` | Yes | Returns `{"saved": false, "reason": "missing_room_id"}` if blank. |
| `cx`, `cy`, `zoom` | No | Pass all three null (or omit) to clear the saved viewport. |

---

## State Inspection

Services that read current integration state, plus the few that reset it (`clear_queue`, `clear_active_job`) or write a setting (`set_pause_timeout_settings`). All support response except `clear_active_job`, which returns nothing.

### `get_queue_state`

Returns the current queue state including room order.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_payload_state`

Returns the current resolved cleaning payload including per-room settings as they would be sent to the vacuum. Reflects the output of the last `build_queue` or `build_room_payload` call, including carpet enforcement and capability guards.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Supports response. Use this to inspect exactly what the vacuum would receive before calling `start_selected_rooms`.

### `clear_queue`

Clears the current queue state. The vacuum is not affected — this only resets the integration-side queue record. Persists to storage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `clear_active_job`

Clears the active job record without sending any command to the vacuum. Persists to storage.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Use this to recover from a stuck or orphaned job state when `cancel_active_job` is not appropriate (for example, when the vacuum has already finished but the integration still shows an active job). This service does not finalize or archive the job — it only removes the in-memory record.

Does not support response — it is the one service in this section that returns nothing, so `response_variable` has nothing to capture.

### `get_active_job`

Returns the current active job state including start time and battery level at start.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_job_progress_snapshot`

Returns the canonical room-job progress state including current room, completed rooms, remaining rooms, and live completion percentage. During a stepped run it also surfaces mid-run stop state: `charge_phase_active` / `charge_target_percent` / `charge_eta_minutes` / `charge_eta_source` while docked charging, and `wait_phase_active` / `wait_minutes` during a wait stop.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_job_control_state`

Returns the backend-authored button availability and messages for the start, pause, resume, cancel, and clear actions. The card uses this to decide which buttons to enable and what label or tooltip to show. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

This service returns control state, not job progress. For current job progress use `get_job_progress_snapshot`. For the combined single-call dashboard payload, use `get_dashboard_snapshot`.

### `get_lifecycle_state`

Returns the current lifecycle state for a vacuum. Possible states are `ready`, `active_job_running`, `vacuum_busy`, `dock_drying`, `mid_job_service`, and `map_mismatch`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_dashboard_snapshot`

Returns one unified payload containing job progress, job control button state, start status, lifecycle, and upkeep data. Designed to power a full card render in a single call.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

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
| `pause_timeout_minutes_default` | Yes | Minutes before a paused job is auto-cancelled. `0` disables auto-cancel. Range: 0 or greater (no upper bound). |

### `get_upkeep_snapshot`

Returns replacement items, maintenance items, dock events, dock event counts, and upkeep attention summaries for one vacuum. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

This is a vacuum-level (not map-level) service — `map_id` is not required. The card uses it to populate the upkeep panel. You can call it from an automation to check whether any maintenance items are due.

---

## External Jobs (app-started runs)

Surface app-started (external) cleans for review and fold confirmed runs into the
learned baselines. See the [30 — External Runs](../dev/30-external-runs.md).
All of them support response, and the review flow depends on it: `get_external_pending_runs`
is the only source of the `pending_job_id` the other three require.

### `get_external_pending_runs`

Return the pending external records awaiting review (newest first). Response:
`{pending: [...], count}`; each record carries a `pending_job_id` used to confirm,
discard, or re-segment it.

| Field | Required | Description |
|---|---|---|
| `vacuum_entity_id` | yes | The vacuum. |

Each served record also carries `resegmentable` (bool): `true` when the record
embeds the raw counter samples needed to re-run segmentation (schema v2), `false`
for legacy v1 records that can only be merged. The bulky raw sample arrays are
stripped from the served payload — re-segmentation happens server-side via
`resegment_external_run`, so the card never needs them.

### `confirm_external_run`

Confirm a pending run's room identities and graduate it into learning. Returns
`{ok, job_id, job_path, rooms_learned}`, or `{ok: false, blocked: [...]}` when a
segment's area doesn't match the picked room (re-pick, or set `override` on that
assignment).

| Field | Required | Description |
|---|---|---|
| `vacuum_entity_id` | yes | The vacuum. |
| `map_id` | yes | The run's map. |
| `pending_job_id` | yes | From `get_external_pending_runs`. |
| `room_assignments` | yes | List of `{segment_orders, room_id, edge_mopping, override?, overrides?}` — one per room (merged segments share `segment_orders`). |
| `rebuild_stats` | no | Rebuild learned stats after graduating (default `true`). |

### `resegment_external_run`

Re-segment a pending external record server-side from its embedded raw samples,
then rewrite it in place. This backs the review wizard's step-1 room-count stepper
and per-boundary "Split here" / "Merge up" toggles: rather than the card splitting
segments client-side, it asks the backend to re-run the real segmenter for a target
room count or an explicit boundary set, keeping the result internally consistent
with the timing/area samples. Only v2 records (those with `resegmentable: true`)
can be re-segmented.

Pass **either** `expected_rooms` **or** `active_boundaries`, not both (they are
mutually exclusive). Omit both to reset to the confident-only default segmentation
(the pre-v2 view).

| Field | Required | Description |
|---|---|---|
| `vacuum_entity_id` | yes | The vacuum. |
| `map_id` | yes | The run's map. |
| `pending_job_id` | yes | From `get_external_pending_runs`. |
| `expected_rooms` | no | Target room count (integer `>= 1`). Picks the strongest boundaries to yield this many rooms, capped to the detectable pool. Exclusive with `active_boundaries`. |
| `active_boundaries` | no | Explicit list of boundary candidate IDs to activate (the per-boundary toggle set). Exclusive with `expected_rooms`. |

Supports response. On success returns `{ok: true, ...}` with the re-segmented,
sample-stripped pending record (its `pending_job_id`, updated `segments`,
`segment_count`, `suggested_room_count`, the full `candidates` pool, and the
resulting `active_boundaries`) merged with a selection `meta`:

| `meta` field | When | Description |
|---|---|---|
| `mode` | always | `count` (room-count request), `explicit` (boundary set), or `reset` (confident default). |
| `requested` | `count` mode | The room count you asked for. |
| `available` | `count` mode | Max rooms detectable from this run (boundaries + 1). |
| `capped` | `count` mode | `true` when `requested` exceeded `available`. |
| `capped_at` | `count` mode | The count actually applied after capping. |
| `message` | when capped | Human-readable note, e.g. `Only 3 room(s) detectable from this run.` |

Returns `{ok: false, error: ...}` **without** touching the stored record when the
record is missing (`pending_not_found`), is a v1 record with no embedded samples
(`not_resegmentable`), or the requested selection yields no usable segment
(`empty_segmentation`) — a usable record is never blanked.

### `discard_external_run`

Delete a pending external record (a junk or false-start run).

| Field | Required | Description |
|---|---|---|
| `vacuum_entity_id` | yes | The vacuum. |
| `pending_job_id` | yes | From `get_external_pending_runs`. |

---

## Profiles

### Run Profiles

Run profiles capture the full room selection, order, and per-room settings for a map so you can replay a cleaning configuration on demand. A profile can also carry an ordered **steps** list — room groups broken up by mid-run **charge** and **wait** stops (see [`set_run_profile_steps`](#set_run_profile_steps)). A profile without steps runs as a plain queue; a profile with steps runs as a sequence.

All of them support response. That matters more here than elsewhere: several of these refuse by RETURNING a reason rather than raising, so an automation that ignores the response cannot tell a completed write from a refused one. The per-service sections below give each returned shape.

#### `save_run_profile`

Saves the currently enabled rooms and their settings as a new named run profile.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `name` | Yes | Display name for the profile. |
| `expose_as_button` | No | Mark this profile for Home Assistant button exposure. |
| `strict_order` | No | Boolean. Save this profile to clean its rooms in the saved order on a brand that would otherwise path-optimize. The exposed button carries no service data, so this stored setting is how a button-driven run opts in. A no-op for order-honoring brands (Eufy). Absent on profiles saved before this field existed, and the stored default is `false`, so an older profile keeps path-optimized dispatch until you set it. |

#### `overwrite_run_profile`

Replaces the rooms snapshot in an existing run profile without creating a new one. Preserves the profile ID and label unless a new name is supplied.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `profile_id` | Yes | ID of the run profile to overwrite. |
| `name` | No | Updated display name. Omit to keep the existing label. |
| `expose_as_button` | No | |
| `strict_order` | No | Boolean. **Omit to keep the profile's current setting** — this field is tri-state, so an overwrite never clears a flag you did not mention. Set it to clean this profile's rooms in the saved order on a brand that would otherwise path-optimize. |

#### `rename_run_profile`

Updates the display label of an existing run profile.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |
| `profile_id` | Yes |
| `name` | Yes |

#### `delete_run_profile`

Deletes a saved run profile. This does not affect current room settings — it only removes the named preset from the library.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |
| `profile_id` | Yes |

#### `apply_run_profile`

Restores a saved run profile back onto room selection, order, and per-room settings without starting a job.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |
| `profile_id` | Yes |

#### `set_run_profile_steps`

Replaces a saved run profile's ordered **steps** list — the sequence of room groups and the mid-run stops between them. This is what turns a plain-queue profile into a stepped run: "vacuum this group, dock and charge to a target, then mop the next group" as one job. The profile must already exist and the resulting list must contain at least one `room_group` (a run has to clean something) — otherwise nothing is saved. Consecutive same-type stops are collapsed and leading/trailing stops are dropped during normalization.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `profile_id` | Yes | ID of the saved run profile whose steps to replace. |
| `steps` | Yes | Ordered list of step objects. See below. |

Each step is one of four types:

- `{"type": "room_group", "rooms": [...]}` — a batch of rooms cleaned together. `rooms` is a list of per-room setting objects (`room_id`, `clean_mode`, `fan_speed`, `water_level`, …); the group's fields overlay the global room view at dispatch, so the **same** room can appear in two groups with different settings (vacuum in one, mop in the next).
- `{"type": "charge_wait", "target_battery_percent": <1–100>}` — dock and poll the battery until it reaches the target, then continue. The percent is clamped to `1–100`.
- `{"type": "wait", "wait_minutes": <1–1440>}` — dock and hold for a fixed number of minutes (for example a mop-dry pause), then continue. The minutes are clamped to `1–1440`.
- `{"type": "zone", "zone_ids": ["…"]}` — clean one or more saved zones as their own phase. Unlike the two stops above this is a **clean** phase, not a dock, so it may sit at the tail of a profile.

**A malformed step is REFUSED, not dropped.** The call returns
`{"saved": false, "reason": "invalid_steps", "rejected_steps": [...]}` and the profile is
left untouched, with every rejected step named so you can see which line of your YAML was
wrong. Earlier behaviour dropped what it could not read and still reported success — which
returned `saved: true` for a profile that had quietly lost its charge stop, so the robot ran
the whole sequence in one go and could strand mid-run.

Two layers do this: the service schema validates each step's shape at the boundary, where the
error still points at your own YAML, and the manager reports what it rejected (it is also
reachable from the card and the websocket API). Out-of-range NUMBERS are the exception — they
are clamped and reported rather than schema-rejected, because "`target_battery_percent` was
120, clamped to 100" is a better error than a schema traceback.

A legacy profile with only a `rooms` snapshot and no `steps` is treated as a single implicit
`room_group` — **reads stay tolerant** so an old profile never fails to start. Only the write
path is strict.

Supports response. Returns `{"saved": true, "profile_id", "profile": {...}}` — the enriched profile now carries its normalized `steps` and a `has_charge_steps` flag (the backend signal the card uses to drive the stepped-run UI). Returns `{"saved": false, "reason": "profile_not_found"}` for an unknown profile ID, or `{"saved": false, "reason": "no_room_group"}` when the supplied steps contain no room group.

When a profile with charge or wait stops is started (via `start_run_profile`, the card's **Run** button, or an exposed profile button), the run is forced into strict order so each group's rooms clean in the exact sequence shown — a no-op for order-honoring brands (Eufy), enforced per-room for path-optimizing brands (Roborock). Charge and wait steps ride free on any brand whose adapter supports the phase machinery. Live charge/wait progress surfaces through [`get_job_progress_snapshot`](#get_job_progress_snapshot) (`charge_phase_active`, `charge_target_percent`, `charge_eta_minutes`, `charge_eta_source`, `wait_phase_active`, `wait_minutes`).

#### `start_run_profile`

See [Queue Building](#queue-building) — this is the one-shot apply-and-start shortcut. When the applied profile carries charge or wait stops, this runs the whole stepped sequence, not just the first room group.

#### `get_saved_run_profiles`

Returns all saved run profiles for a vacuum/map combination.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Supports response.

### Room Profiles

Room profiles define cleaning settings (fan speed, water level, clean mode, etc.) that can be applied to one or more rooms at once. All of them support response.

#### `apply_room_profile`

Applies a named profile to one or more rooms on a map.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `room_ids` | Yes | List of room IDs to apply the profile to. |
| `profile_name` | Yes | Built-in or custom profile key. |

#### `get_room_profiles`

Returns the user-saved room-profile library, plus one vacuum's built-in profiles when you name it.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | No | Whose built-in profiles to include. Omit to return the saved library alone. |

Built-in profiles belong to a **brand**, not to the integration: each adapter declares its own catalog, and there is no shared default vocabulary to fall back on. So a call with no `vacuum_entity_id` cannot answer the built-in half of the question, and does not guess — it returns only the saved library and says so.

Supports response. Returns `{profile_count, profiles, protected_profile_names, built_ins_included}`. `built_ins_included` is `false` exactly when `vacuum_entity_id` was omitted; treat a `false` there as "this list is incomplete", not as "this install has no built-ins".

> The profile **keys** (`vacuum_quick`, `vacuum_deep`, `vacuum_mop_quick`, `vacuum_mop_deep`, plus your saved ones) are shared across brands, so a stored room and the profile picker survive a brand switch. The **settings behind each key** are the adapter's own words — a fan speed named `Max` on one brand may be `max` or absent on another. Do not hard-code another brand's values into an automation.

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
| `map_id` | No | |
| `room_id` | Yes | |
| `label` | Yes | Display name for the new profile. |
| `profile_name` | No | Optional stable backend key. |

#### `overwrite_room_profile_from_room`

Replaces an existing custom room profile's settings from one room's current effective settings.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
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

Deletes a custom room profile from the library. Cannot target built-in profiles. Refused when rooms still reference the profile unless `force` is set.

| Parameter | Required | Notes |
|---|---|---|
| `profile_name` | Yes | |
| `force` | No | Default `false`. Without it, the delete is refused with `reason: "has_referrers"` and a `referring_rooms` list when any room still uses this profile. With `force: true` the profile is deleted anyway — the referring rooms keep pointing at the now-gone name and profile resolution falls back silently. |

Supports response. Returns `{"deleted": true, "profile_name", "referring_rooms"}` on success, or `{"deleted": false, "reason": ...}` on `protected_profile`, `profile_not_found`, or `has_referrers`.

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

## Stall Capture

When a run stalls, the integration can render a picture of the room the robot stopped in — the room's own shape, the robot's position, and the pose trail either side of the stall — write it beside that vacuum's learning data, raise a persistent notification, and fire [`eufy_vacuum_stall_captured`](02-events.md#eufy_vacuum_stall_captured) carrying the file path so an automation can forward it.

The feature is **off by default and armed per vacuum**. Arming changes nothing about detection: `eufy_vacuum_stall_detected` and the card's run-anomaly reporting fire either way, so turning capture off never quiets a subsystem you did not mean to touch.

### `set_stall_capture`

Arms or disarms stall capture for one vacuum.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | Must be a vacuum this install manages. An unmanaged entity ID raises an error rather than creating a record for it. |
| `enabled` | Yes | `true` to arm, `false` to disarm. |

Supports response (`supports_response: only` — it always returns a payload). Returns `{"vacuum_entity_id", "enabled"}`.

Absent means off, so an upgrade never silently starts writing pictures of your home. Where the image lands, and why it is deliberately not web-served, is covered under [`eufy_vacuum_stall_captured`](02-events.md#eufy_vacuum_stall_captured).

### `dev_inject_stall`

> **MAINTAINER TOOL — UNSUPPORTED. NOT PART OF THE SERVICE SURFACE YOU SHOULD BUILD ON.**
>
> This service **fabricates a stall that did not happen.** It exists so a maintainer can exercise the stall-capture chain without physically wedging a robot, and it is registered unconditionally only because a service nobody can find when they need it is worse than one that carries a warning.
>
> **It makes the run it is called on look anomalous when it was not.** The event it fires is the canonical `eufy_vacuum_stall_detected`, which is not private to stall capture — it also reaches run-anomaly detection, so the job will be reported as having stalled and the card's snapshot will say so. Do not call it on a run whose records you care about.
>
> It carries **no compatibility promise**: its name, arguments, response, and existence may change or disappear without notice. Nothing in an automation you intend to keep should call it.
>
> What it does **not** do: it never commands hardware. It fires an event. Nothing here pauses, cancels, or dispatches anything to a robot.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | Must be **currently cleaning a room**. |

Refuses with an error when the vacuum has no active map, or when it is not currently in a room — a stall with no current room has no room to render and no pose history to draw, so an injected one would exercise the empty path and look like a broken renderer. Start a run and let the robot move for roughly 30 seconds first.

Supports response (`supports_response: only`). Returns the payload it fired: `{"vacuum_entity_id", "map_id", "room_id", "room_name", "elapsed_minutes": null, "expected_minutes": null, "stall_ratio": null, "injected": true}`. The three timing fields are `null` because there is no real timing behind a fabricated stall, and `injected: true` is how a downstream consumer can tell one apart from a real detection.

---

## Diagnostic Capture

Four services that record this integration's own DEBUG logging into an in-memory ring
and write it out on demand. They exist for one job: producing a log to attach to a bug
report, without the usual cost of that.

The usual cost is why they are here. Raising this integration to DEBUG in
`configuration.yaml` floods `home-assistant.log` for everything else, needs a restart to
turn on, needs another to turn off, and by the time you have reproduced the problem the
interesting lines have scrolled past whatever your log rotation keeps. Capture attaches
to this integration's logger only, keeps a bounded ring in memory, and never touches the
main log file — so you can leave it running, reproduce the fault, and dump only the
window that matters.

All of them support response — that is how the captured log reaches you, since `debug_capture_dump`
returns the records rather than only writing a file.

> **Support tooling, not an automation surface.** These are for diagnosing a problem you
> are going to report. Nothing about their output shape is promised, and an automation
> built on it will break without notice.

> **This is scaffolding for something better.** The capture is a text ring — it records
> what the code happened to log, in the words each log line happens to use. The planned
> Semantic Trace System replaces it with structured, catalogued events that carry the
> decision rather than a sentence about it, and can be replayed. When that lands, these
> four go.

### `debug_capture_start`

Begins capturing. Nothing appears in `home-assistant.log`; records accumulate in memory
until you dump them.

| Parameter | Required | Notes |
|---|---|---|
| `areas` | No | Restrict to one or more of `map`, `rooms`, `dispatch`, `learning`, `setup`, `themes`, `decisions`. Omit to capture everything. Narrow this when you know roughly where the fault is — the ring holds a fixed number of records, so filtering buys you a longer window rather than a smaller file. |
| `services` | No | Per-service tracing: capture **only** while the named services run. Call `debug_capture_status` for the list of services flagged as traceable. Omit for a continuous capture. |
| `size` | No | Ring size in records; oldest are evicted. Default 3000. Raise it if a reproduction takes a long time, at the cost of memory. |
| `max_minutes` | No | Stop capturing automatically after this many minutes (1–1440). Worth setting: capture left running forever is the thing this feature exists to avoid, and a forgotten capture is a ring quietly holding your logs in memory. |
| `stop_when_full` | No | Freeze at the ring size — keep the FIRST `size` records instead of the last. Default `false`. Use it when the interesting moment is the **start** of something (a setup failure, the first dispatch after a restart); leave it off when the fault happens at an unknown time and you want the most recent window. Getting this backwards is the usual reason a capture contains everything except the part you needed. |

### `debug_capture_stop`

Stops capturing and restores normal logging. Captured records **survive** the stop, so
the order is: start, reproduce, stop, dump.

### `debug_capture_dump`

Returns the captured records, and by default also writes them to
`config/eufy_vacuum/debug/debug-<timestamp>.log`.

| Parameter | Required | Notes |
|---|---|---|
| `write_file` | No | Also write a timestamped file under `config/eufy_vacuum/debug/`. Default `true`. |
| `clear` | No | Empty the ring after dumping. Default `false`, so a dump is repeatable — you get a second copy rather than an empty one if the first went astray. |

Read the file before attaching it to a public issue. It is your own DEBUG log: it can
contain room names, map identifiers and entity IDs from your home.

### `debug_capture_status`

Reports whether capture is running and how much has accumulated, and lists the services
that support per-service tracing — which is where the `services` values for
`debug_capture_start` come from.

## Maintenance

These services write maintenance state. To read current maintenance status use `get_upkeep_snapshot` (State Inspection section).

### `reset_maintenance`

Records that a maintenance component has been cleaned or replaced, resetting its integration-tracked usage counter.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `component` | Yes | Component ID as declared in the adapter's `maintenance_components` block (e.g. `"side_brush"`, `"filter"`). Valid values: `filter`, `sensor`, `side_brush`, `rolling_brush`, `mopping_cloth`, `cleaning_tray`, `swivel_wheel`. |

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

## Battery

### `battery_rebaseline`

Clears the battery-health baseline anchor so the next qualifying recharge re-anchors it — call this after physically replacing the battery. Only the health comparison state is cleared: the charge-speed baseline, the health %, and the retained qualifying-session set it is compared against. Cycle count, per-job metrics, session history, and aggregates are untouched. A fresh baseline seeds itself automatically on the next qualifying recharge.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Fire-and-forget — no response payload. If no battery record exists for the vacuum yet, the call logs a warning and changes nothing.

> The service form in Developer Tools also shows a `pause_timeout_minutes_override` field for this service. That is a stray `services.yaml` entry: the registered schema accepts only `vacuum_entity_id`, so passing it fails validation. Do not use it.

---

## Access Graph

The access graph models rooms that can only be reached by passing through other rooms. These services drive the access graph editor in the panel.

### `get_room_access_editor`

Returns the editor payload for one room's access-graph configuration.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |
| `room_id` | Yes |

Supports response.

### `get_access_graph_health`

Validates the whole-map access graph and returns a health report identifying unreachable rooms, cycles, or misconfigured dock-room settings.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Supports response.

---

### `set_room_access_graph`

Replaces the **entire** access graph for one map in a single write: the dock room plus every access link. Call it with no `dock_room_id` and no `edges` to **clear** the graph, which is what unblocks basic runs on a map whose graph is only partly configured.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Defaults to the current active map. |
| `dock_room_id` | No | The room containing the charging dock — the root of the access tree. Omit to clear it. |
| `edges` | No | The complete link list as `{from, to}` pairs, where `from` grants access to `to`. Omit to remove all links. |

Supports response.

**Replace, not merge.** Any link absent from `edges` is removed. This is deliberate: the access graph is all-or-nothing — a map is either *blank* (no graph, basic runs allowed) or *complete* (valid graph, room rules usable), and the *partial* state in between refuses every run. Writing the graph room by room would walk the map through that blocked state on the way, and an interrupted sequence would leave it there. One call, one validation, one notification.

**What it touches.** Only `is_dock_room` and `grants_access_to`. Room rules, selection, order, colours, profiles and `is_transition` are left alone.

**Refusals.** A structurally illegal graph — a loop, a room reached from two rooms, a link to a room that is not on this map — is refused with `ok: false` and formatted `issues`, and **nothing is written**. An *incomplete* graph is not refused: completeness is enforced when the cleaning queue is built, and refusing it here would make a graph impossible to build in stages.

**Did it actually unlock anything?** The response carries `block_code_before` and `block_code_after`:

```yaml
ok: true
dock_room_id: "1"
edge_count: 3
block_code_before: incomplete_access_graph
block_code_after: null
blocked_before: true
blocked_after: false
blocking_rooms: []
```

Check `blocked_after` rather than `ok`. Clearing the graph on a map that has **blocker rules** moves you from `incomplete_access_graph` to `access_graph_required_for_rules` — the write succeeds and you are still blocked, because blocker rules need an access graph to evaluate against. `blocking_rooms` names the rooms responsible when `block_code_after` is `incomplete_access_graph`.

**Build a tree:**

```yaml
action: eufy_vacuum.set_room_access_graph
data:
  vacuum_entity_id: vacuum.alfred
  dock_room_id: 1
  edges:
    - {from: 1, to: 2}
    - {from: 1, to: 3}
    - {from: 3, to: 4}
```

**Clear it:**

```yaml
action: eufy_vacuum.set_room_access_graph
data:
  vacuum_entity_id: vacuum.alfred
```

---

## Learning Services

The learning system records completed job history to build per-room timing estimates. Most of these services run automatically — the ones below are the ones you would call explicitly from an automation or script.

Every service in this section supports response except `finalize_learning_job`, which returns nothing.

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
| `map_id` | No | |
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
| `charge_percent_per_minute` | No | Default `1.0`. Used in the remaining-rooms battery warning. |
| `reserve_battery_percent` | No | Minimum battery buffer to keep in reserve. Default `5.0`. |

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
| `map_id` | No | |
| `current_battery` | No | Optional. Informational only. |

**Returns:** Per-room estimate data keyed by room.

### `rebuild_learning_stats`

Forces a full rebuild of learned job and room statistics from all completed job history. Called automatically after `finalize_learning_job` — use this manually to correct stats after excluding or restoring archived jobs.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `rebuild_csv` | No | Also rebuild flat CSV exports. Default `false`. |

### `set_learning_processing`

Box-level toggle for learning's heavy per-run stats processing. It flips **all** vacuums at once, so it takes no `vacuum_entity_id`. When off, completed runs are still collected into history but the per-run stats rebuild is skipped (near-zero churn, useful on low-power hardware). Turning it back on reprocesses the whole collected backlog and resumes normal per-run processing.

| Parameter | Required | Notes |
|---|---|---|
| `enabled` | Yes | `true` resumes per-run processing (and catches up the backlog); `false` switches to collect-only. |

Supports response. Returns `{"enabled": bool, "was": bool, "caught_up": {...}}` — `caught_up` carries the backlog rebuild result when the call switched processing from off to on, otherwise `null`.

### `process_pending_runs`

Reprocesses every run collected while learning processing was off — a full stats rebuild from history — and clears the pending counters, **without** turning per-run processing back on. Like `set_learning_processing`, it is box-level and flips all vacuums, so it takes no parameters. Use it to catch up on demand while staying in collect-only mode.

Supports response. Returns `{"processed": [...], "count": N}` listing the vacuums rebuilt.

### `save_learning_snapshot`

Manually saves a learning snapshot for the current job state. Called automatically by `start_selected_rooms` — manual use is only needed for edge cases such as recording a job that was started outside the integration.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `started_at` | Yes | Job start timestamp in `YYYY-MM-DDTHH:MM:SS` format. |
| `battery_start` | Yes | Battery percent at job start (0–100). |
| `job_id` | No | Optional custom job ID. |

### `finalize_learning_job`

Manually finalizes a completed job and optionally rebuilds learned stats. Called automatically when the vacuum returns to dock — manual use is needed for edge cases or historical corrections.

Fires `eufy_vacuum_job_finished` on completion. Also fires `eufy_vacuum_run_incomplete` if the job ended with rooms unvisited.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `battery_start` | Yes | Battery at job start (0–100). |
| `battery_end` | Yes | Battery at job end (0–100). |
| `started_at` | Yes | Job start timestamp in `YYYY-MM-DDTHH:MM:SS` format. |
| `ended_at` | No | End timestamp. Defaults to now. |
| `used_for_learning` | No | Whether to include this job in learned stats. Default `true`. |
| `rebuild_stats` | No | Rebuild learned stats after finalizing. Default `true`. |
| `rebuild_csv` | No | Also rebuild CSV exports. Default `false`. |
| `forced_outcome_status` | No | Override the inferred outcome status (e.g. to force `completed`/`cancelled`) for internal or forced-status finalization. Omit to let the integration infer it. |

Does not support response — the one service in this section that returns nothing. Watch for the `eufy_vacuum_job_finished` event above instead of a `response_variable`.

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
| `profile_name` | No | Filter by the profile's display name (the Review panel's Profile chip sends this). |
| `status` | No | Filter by job status: `completed`, `cancelled`, `failed`, or `interrupted`. |
| `used_for_learning` | No | Filter to only jobs included in or excluded from learned stats. |
| `origin` | No | Filter by how the run started: `external` (app-started, captured by external-run ingestion) or `internal` (dispatched by this integration). |
| `limit` | No | Maximum recent jobs to return. Default `50`, floored to `1`. The `500` max in the Developer Tools form is UI-only — the schema itself sets no upper bound. |

**Returns:** History snapshot with recent jobs and aggregated room statistics.

### `record_estimate_accuracy`

Records estimated-vs-actual minutes per room after a job completes, feeding the estimator's accuracy tracking. Supports response.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_actuals` | Yes | List of per-room dicts, each with `slug`, `clean_mode`, `clean_passes`, `is_carpet`, `clean_intensity`, `estimated_minutes`, `actual_minutes`, and `map_id`. |

### `get_metrics_snapshot`

Returns a metrics-focused slice of learned history for the card, with the same optional filters as `get_learning_history_snapshot`. Supports response.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_slug` | No | Filter to a single room slug. |
| `profile_key` | No | Filter by room profile signature. |
| `profile_name` | No | Filter by the profile's display name (the Review panel's Profile chip sends this). |
| `status` | No | Filter by job status. |
| `used_for_learning` | No | Filter to jobs included in or excluded from learned stats. |

### `get_trouble_rooms_log`

Returns the chronic trouble-rooms log for a vacuum — per-room miss counts and miss rates. Rooms with `miss_count >= 2` and `miss_rate >= 0.33` are flagged `is_trouble: true` for the card. Returns an empty dict when no log exists. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

### `get_incomplete_run_log`

Returns the last incomplete-run log for a vacuum — the payload recorded when a previous job was cancelled, failed, or interrupted before all queued rooms were cleaned. This is the source `retry_missed_rooms` reads from. Returns an empty dict when no incomplete run log exists. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

---

## Dock Actions

These services gate on dock and vacuum state before issuing the upstream command. If the dock is not in a valid state the service raises a `ServiceValidationError` with a human-readable reason — it does **not** fail silently. The error surfaces in the HA service call UI and will propagate to automations that do not suppress errors. Use `get_dock_action_status` first to check availability before calling these from automations. All of them support response, so the dispatch result is readable with `response_variable` — the raised error covers the refused case, the response covers the accepted one.

### `wash_mop`

Runs the dock wash action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `dry_mop`

Runs the dock dry action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `stop_dry_mop`

Stops an active dock drying cycle. Only runs when the dock is actively drying.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `empty_dust`

Runs the dock dust-empty action when the dock state makes it valid to do so.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_dock_action_status`

Returns gated availability and blocked reasons for `wash_mop`, `dry_mop`, and `empty_dust`. Supports response.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `set_dock_event_count`

Overwrites a dock event counter to a specific value. This is a one-time correction service — use it when the stored event count is wrong due to an interrupted integration startup, missed dock event, or manual intervention at the dock.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `event_type` | Yes | One of `last_mop_wash`, `last_dust_empty`, `last_dry_start`. |
| `count` | Yes | The new integer count. Must be 0 or greater. |

Supports response. Returns `{"updated": true}` on success or `{"updated": false, "error": "..."}` if the `event_type` is unrecognised. Persists to storage when the update succeeds.

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
| `map_id` | No |

**Returns:** `{"vacuum_entity_id": ..., "map_id": ..., "rooms": [...]}`.

### `setup_save_rooms`

Saves a set of room IDs as managed rooms for a vacuum and map, optionally setting floor types. This is the commit step of the onboarding flow — rooms become managed and available for queue building after this call.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `enabled_room_ids` | No | List of integer room IDs to save as managed rooms. **Omit the key to keep the current selection unchanged.** `null` and an empty list are rejected with a validation error rather than being treated as "delete every room" — removing rooms goes through per-room enabled flags or map deletion. |
| `floor_types` | No | Dict mapping room ID to floor type. Valid values: `hardwood`, `laminate`, `tile`, `marble`, `granite`, `concrete`, `carpet_low_pile`, `carpet_high_pile` — carpet pile is part of the compound value, not a separate field (legacy stored `carpet` values are migrated to `carpet_<pile>` at load). |

**Returns:** `{"status": "success", "room_count": N}` on success.

### `setup_delete_map`

Deletes one imported map and all related integration data (rooms, queue, job records, learned history) for that map. This is an integration-only operation — it does not affect upstream cloud data.

Delete operations are protection-gated. Maps with significant data (active jobs, learning history, automation rules) require a `confirmation_token` matching the map display name exactly before the delete proceeds.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `confirmation_token` | No | Required for high-protection maps. Must match the map display name exactly. For elevated-protection maps any truthy string is accepted. |

**Returns:** An ActionResult dict. Returns `status: "requires_confirmation"` with a `code` of `"typed_confirmation_required"` or `"confirmation_required"` when the token is missing for a protected map. Returns `status: "blocked"` with code `"confirmation_mismatch"` when a typed token is provided but does not match.

> **Risk:** Irreversible. All learned history for the map is permanently deleted.

### `setup_reject_rooms`

Marks one or more discovered room IDs as rejected **on one map** — they never surface again in that map's new-rooms drift list even if the vacuum continues to report them. Rejected IDs that were configured are also removed from that map's managed rooms so their HA entities are torn down. Room IDs are reissued per map, so both the rejection and the managed-room strip are confined to the one map: an ID rejected downstairs must not block (or delete) a real room upstairs.

Use this for phantom rooms that your vacuum reports but that do not correspond to real cleaned spaces (firmware artifacts, stairwells, etc.).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_ids` | Yes | List of integer room IDs to reject. |
| `map_id` | No | The map the phantom was seen on. Defaults to the currently active map; if no active map can be resolved, a single-map vacuum uses its only map and a multi-map vacuum is **refused** with `reason: "map_ambiguous"` (naming the candidate `map_ids`) rather than guessing. |

**Returns:** `{"status": "success", "rejected": [...], "removed_from_managed": [...], "affected_map_ids": [...], "map_id": ...}`, or a `{"status": "error", "reason": "map_ambiguous", "map_ids": [...]}` refusal that writes nothing.

### `setup_unreject_rooms`

Undoes a room rejection so the room can be discovered and configured again — the escape hatch for a mistaken `setup_reject_rooms`. Clears the rejection on the given map **and** any legacy vacuum-global rejection recorded before rejections were per-map (those applied to every map, so an ID rejected on one floor could block a real room on another). The room does not reappear instantly: it resurfaces on the next discovery pass that sees it, through the normal new-rooms confirmation cadence.

Map resolution is the same as `setup_reject_rooms`, and an unresolvable multi-map call is refused with `reason: "map_ambiguous"` for the same cause pointed the other way — an unqualified un-reject would un-hide an ID on every floor at once.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `room_ids` | Yes | List of integer room IDs to un-reject. |
| `map_id` | No | Defaults to the currently active map; refused when ambiguous on a multi-map vacuum. |

**Returns:** `{"status": "success", "unrejected": [...], "still_rejected_on": {...}, "map_id": ...}` — `still_rejected_on` maps any **other** map ID that still rejects one of these room IDs to the affected IDs, so a clean sweep is never implied.

### `setup_force_remove_room`

Bypasses the missing-pass counter and immediately flags a room as removed in the drift signal. The room remains in managed rooms (history is preserved); only the drift status flips to confirm-removed.

Use this for the "I know this room is gone" manual action when you do not want to wait for the natural three-pass removal confirmation cycle.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `room_id` | Yes |

**Returns:** `{"status": "success", "room_id": int, "missing_passes": int, "threshold": int}`.

### `setup_set_panel_title`

Sets (or clears) the title of this vacuum's sidebar panel entry. The title is stored per-vacuum on the vacuum record as `panel_title` and the panel is re-registered live, so the sidebar updates without a restart (a browser refresh may be needed to repaint). The Setup tab exposes this as a panel-title field.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `title` | No | New sidebar title, max 48 characters. Pass blank or omit to revert to the default name. |

**Returns:** `{"status": "success", "message": ..., "vacuum_entity_id": ..., "panel_title": <the effective title>}`.

### `setup_set_map_camera`

Sets which camera or image entity supplies this vacuum's live-map backdrop, stored per-vacuum on the vacuum record as `live_map_image_entity`. The Setup tab's "Live map camera" picker calls this; the dashboard snapshot resolves the chosen entity **override-first** over the adapter's `live_map_image_entity_pattern`, so a default-named install auto-resolves the live map without picking and this service is only needed when the vacuum entity was renamed.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `entity_id` | No | The `camera.` or `image.` entity to use as the live-map backdrop. Pass blank to clear the override and fall back to the adapter pattern. |

**Returns:** `{"status": "success", "message": ..., "vacuum_entity_id": ..., "live_map_image_entity": <the chosen entity, or null when cleared>}`.

### `set_entity_override`

Pins one adapter **role** to a specific entity, for an install where automatic resolution picked the wrong entity or could not find one at all. This is not an onboarding step: it backs the entity picker on every row of the Setup tab's **System** sub-tab, and stays useful long after setup is done.

Resolution normally derives companion entity IDs from the vacuum's own name, then sweeps the vacuum's device and its config entry for siblings. On an install whose companions are named differently, or where two similarly-named entities collide, that can bind a role to the wrong entity — and a wrong binding never errors. A per-run `cleaning_area` role bound to a lifetime counter reads thousands of times too high and still looks like a working number, which is why the fix is a pin rather than a warning.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `role` | Yes | The role to pin, spelled as the System sub-tab lists it — for example `cleaning_area`, `task_status`, or `battery`. A blank role is refused with `{"status": "error", "reason": "missing_role"}`. |
| `entity_id` | No | The entity this role should read. **Blank clears the override** and hands the role back to automatic resolution; clearing the last override for a vacuum drops its entry entirely. |

Returns `{"status": "success", "role", "entity_id"}`, where `entity_id` is `null` when the override was cleared.

The overrides are stored per vacuum as `entity_overrides` — a `{role: entity_id}` dict — and the same key can also be written from the integration's options flow, which is the rescue path that still works when the card does not. **The call reloads the config entry**, because an override is consumed at adapter-registration time: without the reload you would save a choice and watch nothing change, which is the silent failure this whole surface exists to remove.

---

## Adapter Configuration

These services manage the brand-adapter config layer. Under normal operation the panel calls them automatically. Call them directly when building or debugging a custom adapter for a non-Eufy brand. All of them support response, which is the whole point of the discovery ones — `discover_adapter_entities` and `observe_entity_states` exist only to return what they found.

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

### `set_theme_tags`

Replaces a theme's free-text **vibe** tags (e.g. `aurora`, `cozy`, `retro`). Pass a `tags` list to set them; pass an empty list to clear them. Tags are normalised before storage — trimmed, lowercased, deduped, with empties dropped, capped at 16 tags of at most 32 characters each.

Only the user-owned vibe tags live here. Facet tags (`mode`, `accent`, …) and the colorblind-safe flag are **derived from the palette and verified by the card** — they are never stored on the theme, so they cannot be set or spoofed through this service.

| Parameter | Required | Notes |
|---|---|---|
| `theme_id` | Yes | The library theme to tag. |
| `tags` | Yes | List of free-text vibe tags. Send an empty list to clear all vibe tags. |

Supports response. Returns `{"ok": true, "theme_id": ...}`, and raises a `ServiceValidationError` when the theme ID is unknown (`theme_not_found`).

### Theme `source` (provenance)

Each library theme may carry a `source` field that drives the gallery and card's Source facet. Only four values are stored; any other or unknown value is dropped rather than persisted:

| Source | Where it comes from |
|---|---|
| `core` | Bundled (preloaded) themes. Reserved for the shipped library — `import_theme` never honours `core` on an imported payload, so a downloaded copy of a bundled theme is demoted to a user theme. |
| `community` | A submitted/imported theme whose payload declared `community`. |
| `generated` | A theme whose payload declared `generated`. |
| `manual` | A theme saved from a vacuum's working draft (`save_theme_as_new`), and the fallback provenance for any imported theme that did not declare a recognised source. |

`source` is read-only here — there is no service to set it directly. `save_theme_as_new` stamps `manual`; `import_theme` preserves a declared `community`/`generated`/`manual` and otherwise falls back to `manual`. A bundled theme that was seeded by an older version (before the field existed) is backfilled to `core` at load time; user themes are left untouched.

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
| `vacuum_entity_id` | No | Target vacuum for a **scoped** import: instead of adding a library theme, replace only the floor-type namespaces named in the payload's `scope` on that vacuum's active theme. Omit for a full import. |

---

## Events Reference

These events are fired by the integration. Use them as automation triggers.

| Event | Fired when |
|---|---|
| `eufy_vacuum_job_finished` | A job is finalized (completed, cancelled, or failed). Payload includes `job_id`, `status`, `vacuum_entity_id`, `map_id`. |
| `eufy_vacuum_run_incomplete` | A cancelled or interrupted job left at least one queued room uncleaned. Payload includes `missed_room_ids` and `missed_rooms`. Use with `retry_missed_rooms`. |
| `eufy_vacuum_room_started` | The vacuum begins cleaning a room (job lifecycle timing rollover). |
| `eufy_vacuum_room_finished` | The vacuum finishes cleaning a room (job lifecycle timing rollover). |
| `eufy_vacuum_room_completed` | The tracker confirmed a room exit, resolved from the device's native current-room signal and debounced by a confidence/dwell threshold. Informational per-room dwell only — distinct from the timing-rollover `eufy_vacuum_room_finished`. |
| `eufy_vacuum_room_skipped` | The live job queue advanced past a queued room that was never cleaned (a non-sequential advance). Conservative and live/mid-run — fires at most once per room per job; almost never seen on Eufy. See [Events Reference](02-events.md) §eufy_vacuum_room_skipped. |
| `eufy_vacuum_path_blocked` | Blocker rules changed mid-run and remaining rooms became inaccessible. |
| `eufy_vacuum_stall_detected` | The robot has been in a room for the stall ratio (default 2×) of its learned timing threshold. Payload includes `elapsed_minutes`, `expected_minutes`, and `stall_ratio`. Fires at most once per room per job. A synthetic one from `dev_inject_stall` carries `injected: true` and null timings. |
| `eufy_vacuum_stall_captured` | A stall picture was rendered and written — fires only when capture is armed for that vacuum via [`set_stall_capture`](#set_stall_capture). Payload includes `image_path` and the notification `message`. See [Events Reference](02-events.md) §eufy_vacuum_stall_captured. |
| `eufy_vacuum_job_progress_tick` | Fixed 5-second heartbeat while a run is in flight (active-job status `started`, `paused`, or `external`). Carries no job state — use it as a trigger to pull `get_job_progress_snapshot` or `get_dashboard_snapshot`. See [Events Reference](02-events.md) §eufy_vacuum_job_progress_tick. |
| `eufy_vacuum_external_run_pending` | An app-started (external) clean finished and was captured as a pending review record. Payload includes `record_path`, `segment_count`, and `detection_ts`. Use with `get_external_pending_runs`. See [Events Reference](02-events.md) §eufy_vacuum_external_run_pending. |
