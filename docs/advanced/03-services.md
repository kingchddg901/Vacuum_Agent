# Services Reference

All services are registered under the `eufy_vacuum` domain. Call them as `eufy_vacuum.<service_name>`.

Services that `supports_response` return a data payload you can capture with `response_variable` in a script or automation action. Services that do not support response run fire-and-forget.

Most services require at least `vacuum_entity_id`. Services that operate on a specific map also accept `map_id`, but it is optional — when omitted, it auto-resolves to the vacuum's currently active map (via the adapter's declared `active_map` entity). Pass it explicitly only when you need to target a stored secondary map. Both fields are noted in each section.

---

## Job Control

These services start, pause, resume, and cancel the integration-managed active job.

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

---

## Queue Building

Use these services to configure which rooms are cleaned and in what order, then call `start_selected_rooms` to launch the job.

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

### `start_run_profile`

Applies a saved run profile, rebuilds the queue from it, and starts cleaning — all in one call. This is the recommended way to launch a named preset from an automation.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
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
| `map_id` | No | |
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
| `enabled_room_ids` | No | List of integer room IDs to enable. Omit to keep all rooms enabled. |

### `get_vacuum_maps`

Returns all imported maps for a vacuum with room counts and display names.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

Supports response.

### `reconcile_room`

The apply/dismiss control for room-identity reconciliation reviews — id-reuse, renamed-room, and floor-type mismatches surfaced by `discover_rooms`. `migrate` carries the room's durable per-room settings onto the new IDs by name slug and rewrites the access-graph grants; `ignore` dismisses the review without changing anything.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `action` | No | One of `migrate` or `ignore`. Default `migrate`. |

Supports response.

---

## Map Services

These services manage map image uploads, segmentation (CV or manually authored), named custom layouts, custom segment authoring, and the map UI overlay state — segment-to-room links and the animated companion's anchor positions. The card calls them from the Map Configuration panel and the custom-segment composer; you can also call them from developer tools or scripts.

Unlike most map-scoped services in this document, every service in this section requires `map_id` explicitly — it is **not** auto-resolved from the active map. Pass the target map's ID on every call. All of these services support response.

> **Calling these by hand:** `upload_map_image`, `delete_map_image`, `analyze_map_image`, and `get_map_segments` are registered in Python only (no `services.yaml` entry), so Developer Tools → Actions lists them but shows no field descriptions or autocomplete — call them in YAML mode. The parameter tables below come from the integration's schemas and are authoritative regardless.

The `segmentation_mode` flag (`cv` or `custom`) selects which segmentation a map serves on read. Switching modes is a pointer flip — it never re-runs the segmenter.

**CV** lives at the map-bucket level: a single `image_segments` store (the CV segmenter's output) plus its own `segment_room_links` and `companion_anchors`.

**Custom** is now a *named collection*. A map can hold many `custom_layouts` side by side — each a fully self-contained authoring surface keyed by `layout_id`, with its own backdrop image (variant `custom_<layout_id>`), authored `custom_segments`, `segment_room_links`, and `companion_anchors` (including the reserved `dock` mascot spot). A per-map `active_custom_layout_id` names which layout custom mode currently serves. Because room links are per-layout, two layouts can each carry a segment `living` linked to *different* rooms — impossible under the old single-store model.

Reads and writes in custom mode are scoped to the **active** custom layout; in CV mode they use the map-bucket stores. The integration resolves this once (`_resolve_active_scope`) so `get_map_segments`, `set_segment_room_link`, `set_companion_anchor`, and `set_custom_segments` all route to the right place and CV/custom never drift. The legacy single `custom_segments` key from before named layouts is folded **lazily and non-destructively** into a default `Custom` layout on first touch — the old key is kept, never deleted, and the migration is idempotent.

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

Supports response. Returns `segmentation_mode` (`cv` or `custom`), `available`, `analyzed_at`, `image`, `image_variants`, a `summary` (with `segment_count` and `adjusted_count`), `segments` (each carrying `polygon_pct` and, when linked, `room_id`), `adjustments`, and `companion_anchors` (all scoped to the active store). It also returns `active_custom_layout_id`, `segment_room_links` (the active scope's link dict), and `custom_layouts` — a list of layout summaries, each `{id, name, backdrop_variant, backdrop_source, segment_count, created_at, updated_at}` — so the card can render the layout picker without a second fetch.

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

Authors no-CV map segments from primitive shapes — **replace-all**. Rebuilds the **active** custom layout's `custom_segments` store from the supplied list (auto-creating and activating a default layout first if the map has none). Each segment's primitives are rasterised server-side (via `rasterize_primitives` → `mask_to_polygon`, the same polygon tracer the CV path uses) onto a `1`-bit mask, scaled to the active layout's backdrop pixel dimensions, and wrapped in the same segment shape the CV segmenter produces — so room-linking and dispatch treat custom and CV segments identically. Requires the active layout's backdrop to be uploaded (for the canvas dimensions), **or** explicit `backdrop_width`/`backdrop_height` for a live-pinned layout that has no uploaded backdrop. Never runs the segmenter.

One segment is one room. Multiple primitives in a segment merge into a single room; a primitive with `op: subtract` carves material away (an edge cut yields a concave simple polygon; an interior hole cannot be represented by one polygon). Primitives are applied in list order. Degenerate segments (nothing drawn, or the result collapses) are dropped.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `segments` | Yes | List of `{id?, primitives: [...]}`. Extra keys are allowed and ignored. A stable `id` is preserved across re-saves (auto `custom_N` otherwise) so segment-room links survive. |
| `backdrop_width` | No | Rasterise-canvas width in pixels. For a live-pinned layout (no uploaded backdrop) the card sends the rendered live image's natural pixel size here so the writer has a canvas to rasterise against. |
| `backdrop_height` | No | Rasterise-canvas height in pixels. Same use as `backdrop_width`. |

Each primitive is `{type: rect|circle|polygon, op?: subtract, ...coords}` with coordinates as 0–100 percentages of the map:

- `rect` — `x`, `y`, `w`, `h`
- `circle` — `cx`, `cy`, `r`
- `polygon` — `points: [[x, y], ...]`

Primitives without `op` fill (union); `op: subtract` clears.

Supports response. Returns `{"saved": true, "segment_count": N, "skipped": N, "segment_ids": [...]}`, or `{"saved": false, "reason": "no_custom_backdrop"}` when the active layout's backdrop has not been uploaded.

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
| `map_id` | Yes | Required — not auto-resolved. |
| `segment_id` | Yes | e.g. `segment_4`. |
| `room_id` | No | Room to link. Pass `null` or omit to clear the link. |

Supports response. Returns `{"saved": true, "segment_id", "action": "set"|"cleared", "segment_room_links": {...}}` so the card can refresh in-memory state without a second fetch.

#### `set_companion_anchor`

Persists or clears the map position of the animated companion sprite for one room. When the vacuum is docked/idle the companion homes to the reserved `dock` key rather than a room; otherwise the anchor is keyed by room ID. With no anchor stored, the companion falls back to the linked segment's centroid. `pct_x`/`pct_y` are 0–100 percentages from the map image's top-left and are clamped to that range server-side. Like room links, anchors are written to the **active store** — the map-bucket anchors in CV mode, or the active custom layout's own anchors (including its own `dock` spot) in custom mode.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `room_id` | Yes | Target room ID, or the reserved string `dock` for the docked/idle home spot. |
| `pct_x` | No | X position (0–100%). Pass `null`/omit **both** `pct_x` and `pct_y` to clear the anchor. |
| `pct_y` | No | Y position (0–100%). |

Supports response. Returns `{"saved": true, "room_id", "action": "set"|"cleared", "companion_anchors": {...}}`.

#### `set_area_label_anchor`

Persists or clears the position of one room's m² area-label chip, so it can be dragged off the room-name label. Stored at the **map** level (rooms are segmentation-mode-independent), keyed by room ID, as `{pct_x, pct_y}` in the same 0–100 content-box frame the companion anchor uses. Pass `null`/omit **both** `pct_x` and `pct_y` to reset to the default (room centre).

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
| `room_id` | Yes | Target room ID. |
| `pct_x` | No | X position (0–100%). Clear both to reset. |
| `pct_y` | No | Y position (0–100%). |

Supports response. Returns `{"saved": true, "room_id", "action": "set"|"cleared", "area_label_anchors": {...}}`.

#### `set_hidden_regions`

Replace-all the per-map hidden regions — normalized `[x0, y0, x1, y1]` rects (0–1 of the rendered image, top-left origin) drawn to mask map noise (e.g. porch noise off a room). Hidden regions are physical, so they are stored at the **map** level (not per CV/custom scope) and follow the map regardless of segmentation mode. Each entry is sanitised server-side — four finite numbers, clamped 0–1, ordered min < max, degenerate rects dropped. An empty or omitted `regions` clears them all.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | Yes | Required — not auto-resolved. |
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
| `map_id` | Yes | Required — not auto-resolved. |
| `rotation` | Yes | One of `0`, `90`, `180`, or `270` (degrees clockwise). |

Supports response.

#### `set_map_overlay_visibility`

Persists which overlay layers are shown on the map backdrop (display only — never affects segmentation or dispatch). Only the user's **deltas** are stored as `overlay_visibility` on the map bucket — a partial dict merged over the defaults at read time, so the shipped defaults can evolve without rewriting stored prefs. Visibility keys are validated against the known overlay layers, so a typo is rejected rather than silently stored. Pass `reset: true` to clear all deltas and fall back to the defaults.

> **Exception to this section's `map_id`-required rule:** `set_map_overlay_visibility` accepts an **optional** `map_id`. When omitted it auto-resolves to the active map, then to the first stored map (returning `{"saved": false, "error": "no_map"}` when there is none) — like the dashboard-snapshot service.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | Auto-resolves to the active map (then the first stored map) when omitted. |
| `visibility` | No | Partial map of overlay-layer name to bool, merged over the stored deltas. Unknown layer keys are rejected. Omit on a reset. |
| `reset` | No | Clear all stored visibility deltas and fall back to the defaults. Default `false`. |

Supports response. Returns `{"saved": true, "map_id", "overlay_visibility": {...}}` with the fully-resolved visibility for the card.

### Live Map Source

These three read services back the card's own map render and its live moving overlays. They are served by the `MapSourceCoordinator` (`mapping/map_source_coordinator.py`, reached via the manager's `async_get_map_render_data` / `async_get_map_live_pose` / `async_compare_map_sources` delegators).

Unlike the rest of this section, these three are **vacuum-scoped — they take only `vacuum_entity_id`, no `map_id`** (the coordinator resolves the live source itself). The "every service in this section requires `map_id`" rule above does not apply to them. All support response.

#### `get_map_render_data`

Returns the raster plus decode parameters for the card's own map render — the on-demand fetch used when the brand's VA-rendered backdrop is selected. The card caches the result by the returned `version`.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

#### `get_map_live_pose`

Returns only the live moving overlays — robot/dock anchors, current room, and heading — from the brand fork's fresh in-memory pose. This is the lightweight payload the card polls at the ~2-second live cadence, distinct from the full snapshot. Degrades gracefully when no live pose is available.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

#### `compare_map_sources`

Diagnostic verify probe: compares the fork's in-memory `_map_data` against the `.storage` map data (rasters by length + SHA-1, per field) to confirm the in-memory bytes are byte-identical before repointing the map source to memory.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |

---

## State Inspection

Read-only services that return current integration state. All support response.

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

### `get_active_job`

Returns the current active job state including start time and battery level at start.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

### `get_job_progress_snapshot`

Returns the canonical room-job progress state including current room, completed rooms, remaining rooms, and live completion percentage.

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
learned baselines. See the [external-run ingestion dev doc](../dev/28-external-run-ingestion.md).

### `get_external_pending_runs`

Return the pending external records awaiting review (newest first). Response:
`{pending: [...], count}`; each record carries a `pending_job_id` used to confirm,
discard, or re-segment it. Only needs `vacuum_entity_id`.

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

Delete a pending external record (a junk or false-start run). Needs
`vacuum_entity_id` + `pending_job_id`.

---

## Profiles

### Run Profiles

Run profiles capture the full room selection, order, and per-room settings for a map so you can replay a cleaning configuration on demand.

#### `save_run_profile`

Saves the currently enabled rooms and their settings as a new named run profile.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `name` | Yes | Display name for the profile. |
| `expose_as_button` | No | Mark this profile for Home Assistant button exposure. |

#### `overwrite_run_profile`

Replaces the rooms snapshot in an existing run profile without creating a new one. Preserves the profile ID and label unless a new name is supplied.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
| `profile_id` | Yes | ID of the run profile to overwrite. |
| `name` | No | Updated display name. Omit to keep the existing label. |
| `expose_as_button` | No | |

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

#### `start_run_profile`

See [Queue Building](#queue-building) — this is the one-shot apply-and-start shortcut.

#### `get_saved_run_profiles`

Returns all saved run profiles for a vacuum/map combination.

| Parameter | Required |
|---|---|
| `vacuum_entity_id` | Yes |
| `map_id` | No |

Supports response.

### Room Profiles

Room profiles define cleaning settings (fan speed, water level, clean mode, etc.) that can be applied to one or more rooms at once.

#### `apply_room_profile`

Applies a named profile to one or more rooms on a map.

| Parameter | Required | Notes |
|---|---|---|
| `vacuum_entity_id` | Yes | |
| `map_id` | No | |
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

These services gate on dock and vacuum state before issuing the upstream command. If the dock is not in a valid state the service raises a `ServiceValidationError` with a human-readable reason — it does **not** fail silently. The error surfaces in the HA service call UI and will propagate to automations that do not suppress errors. Use `get_dock_action_status` first to check availability before calling these from automations.

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
| `enabled_room_ids` | No | List of integer room IDs to save. Omit to keep existing. |
| `floor_types` | No | Dict mapping room ID to floor type. Valid values: `hardwood`, `laminate`, `tile`, `marble`, `carpet`. |

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
| `eufy_vacuum_room_skipped` | The live job queue advanced past a queued room that was never cleaned (a non-sequential advance). Conservative and live/mid-run — fires at most once per room per job; almost never seen on Eufy. See [Events Reference](02-events.md) §eufy_vacuum_room_skipped. |
| `eufy_vacuum_path_blocked` | Blocker rules changed mid-run and remaining rooms became inaccessible. |
| `eufy_vacuum_stall_detected` | The robot has been in a room for 2× its learned timing threshold. Payload includes `elapsed_minutes`, `expected_minutes`, and `stall_ratio`. Fires at most once per room per job. |
| `eufy_vacuum_job_progress_tick` | Fixed 5-second heartbeat while an active job is `started` or `paused`. Carries no job state — use it as a trigger to pull `get_job_progress_snapshot` or `get_dashboard_snapshot`. See [Events Reference](02-events.md) §eufy_vacuum_job_progress_tick. |
| `eufy_vacuum_external_run_pending` | An app-started (external) clean finished and was captured as a pending review record. Payload includes `record_path`, `segment_count`, and `detection_ts`. Use with `get_external_pending_runs`. See [Events Reference](02-events.md) §eufy_vacuum_external_run_pending. |
