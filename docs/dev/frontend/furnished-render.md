# Furnished Render

Furnished render overlays a user-supplied, to-scale image of the home **over the live map**, with the live robot/dock/path/room overlays composited on top. It is a **light path**: no georeference, no coordinate solve. The art is aligned by the user over the live frame once, and that placement *is* the registration — the overlays already ride the live frame (via `_overlayTransform`, keyed off `map_state_source.image_size`), so they land correctly regardless of what backdrop is painted underneath.

It is a cross-cutting feature — a per-layout data model, a pure resolver, three services, and a frontend art layer — and is brand-agnostic: it rides any live-map backdrop (Eufy via jeppesens eufy-clean's mainline live-map camera, Roborock, etc.) with a single build.

---

## 1. Data model (per custom layout)

The furnished state lives on each `custom_layouts[<id>]` record (see [data model](../03-data-model.md)), never at the map-bucket level (so it can't leak across layouts):

- `home_art: {art_variant, art_placement_transform: {tx, ty, scale, rotation}}` — the whole-home art.
- `rooms: {<room_id>: {art_variant?, art_placement_transform?, viewport?: {cx, cy, zoom}, render_mode?}}` — per-room overrides.
- `render_mode: "live" | "art" | "blend"` — the layout-level mode (absent ⇒ `live`).

Transforms and viewports are **resolution-independent percentage floats**, every field `round(…, 4)` on write, each with its own clamp:

| Field | Clamp | Value when the field is omitted |
|---|---|---|
| `tx`, `ty` | none (pct offset, may be negative) | `0.0` |
| `rotation` | none (degrees) | `0.0` |
| `scale`, `viewport.zoom` | `[0.05, 20]` | `1.0` |
| `viewport.cx`, `viewport.cy` | `[0, 100]` (pct, **not** a 0–1 fraction) | `0.0` |

The `scale`/`zoom` floor exists because the renderer coerces a `0` back to 1× (`Number(scale) || 1`) — an unclamped `0` would persist as `0.0` and render as `1.0`, so state and render would silently disagree.

The structure is schema-free and minted lazily — `rooms` starts `{}`; `home_art` / `render_mode` appear on first write. One deliberate asymmetry there (FURNIS-6): a *clear* at `scope: "home"` will not mint an empty `home_art` dict, because `resolve_furnished_render` treats a present-but-empty `home_art` as "this layout has furnished data" and a no-op clear would otherwise leave a phantom behind. Room scope has no such trap — the projection tests per-field presence there, so its `setdefault` is unconditional.

The art image itself is stored as an image variant — `custom_<layout_id>_home_art` or `custom_<layout_id>_room_<rid>` — distinct from the layout's `backdrop_variant`, which it never replaces.

---

## 2. Services

All three are map-scoped (operate on the **active** custom layout, returning `no_active_layout` when none is active), `supports_response`, bump the layout's `updated_at` and `async_save()`, and return the resolved `furnished_render` so the card refreshes without a second fetch. See the [services reference](../../advanced/03-services.md#furnished-render) for parameters.

| Service | Writes |
|---|---|
| `set_furnished_art_placement` | `home_art.art_placement_transform` (scope `home`) or `rooms[<id>].art_placement_transform` (scope `room`). All-null clears it. Scope `room` with a blank/absent `room_id` refuses `missing_room_id`. |
| `set_furnished_render_mode` | layout `render_mode` (no `room_id`) or `rooms[<id>].render_mode`. A blank `room_id` is treated as layout-level (never a junk `rooms[""]`) — the *only* one of the three that routes blank rather than refusing, because a mode legitimately has a layout-level default while a transform or viewport with no room is meaningless. |
| `set_room_viewport` | `rooms[<id>].viewport`. All-null clears it. Blank `room_id` refuses `missing_room_id`. |

Return envelope, uniform across all three: `{"saved": true, …, "furnished_render": <projection>}` on success, `{"saved": false, "reason": …}` on refusal — either the map-resolution refusal from `_resolve_write_map_bucket`, `no_active_layout`, or `missing_room_id`. The per-service extras are `scope` + `room_id` + `action` (`"set"` \| `"cleared"`) for placement, `mode` + `room_id` for render mode, `room_id` + `action` for viewport.

`upload_map_image` is extended with `art_scope` (`home` \| `room`) + `room_id`: it writes the furnished-art variant and points `home_art.art_variant` / `rooms[<id>].art_variant` at it, leaving `backdrop_variant` untouched. Unlike the three services above it is **not** active-layout-scoped — the variant key is derived from `layout_id`, so `layout_id` is required (`layout_id_required`) and must resolve (`layout_not_found`, re-checked *after* the file write in case a concurrent `delete_custom_layout` removed the layout mid-flight: the PNG is on disk but the linkage can't be written, and the call reports that rather than a silent "saved").

---

## 3. Surfacing

- **`resolve_furnished_render(map_bucket)`** (`mapping/map_source.py`) — a pure projection, never raises, tolerant of every missing/malformed key. Returns `None` unless `segmentation_mode == "custom"` **and** there is an active layout **and** that layout carries furnished data (`home_art` present, or at least one room with a non-`None` `art_variant` / `art_placement_transform` / `viewport` / `render_mode`). Otherwise:

    ```python
    {
      "active_layout_id": <id>,
      "render_mode": layout["render_mode"] or "live",
      "home_art": {"art_url": <browser_url|None>, "transform": <dict|None>} | None,
      "rooms": {"<rid>": {"art_url": …, "transform": …, "viewport": …, "render_mode": …}},
    }
    ```

    `art_url` is the variant resolved through `image_variants[…]["browser_url"]` (`None` if unresolvable); transforms and viewports pass through untouched. Added to the dashboard snapshot as the **`furnished_render`** key.
- **`get_map_segments`** — the per-layout summary projects `render_mode` / `home_art` / `rooms` through a **fixed whitelist**, so those three keys are the only way per-layout furnished state reaches the editor; a new field on the layout record needs adding here or it is invisible to the card.
- **`delete_custom_layout`** sweeps the layout's furnished-art image variants (whole-home + every per-room) alongside its backdrop, popping each from `image_variants` and unlinking the file best-effort. The reverse direction is covered too: deleting an image variant runs `_clear_layout_references_to_variant`, which nulls any `backdrop_variant` / `home_art.art_variant` / `rooms[*].art_variant` pointing at it, so no layout is left aiming at a missing file.

Two read paths feed the card: the **editor** (config view) uses the active layout's `get_map_segments` summary, authoritative while authoring (it resolves `home_art.art_variant` through `image_variants` itself, so a freshly-uploaded art shows before the next snapshot push); the **plain room view** uses the snapshot's `furnished_render`, where `art_url` is already resolved. Every reader tries the editor path first when `segmentationMode() === "custom"`, then falls back to the snapshot.

**Limitation (POSE-6, adjudicated no-behaviour-change):** the stored `transform` / `viewport` carry **no map-geometry version stamp**. They are pct floats placed against whatever floor plan was active when they were authored, so a re-map under the same `map_id` (new segmentation, different layout/aspect) silently misaligns the art. There is no map-geometry versioning mechanism in the codebase to compare against.

---

## 4. Frontend (the card)

The card gate is narrower than the backend projection. `isFurnishedLayoutActive()` requires all three of: `segmentationMode() === "custom"`, the active layout's **`backdrop_source === "live"`**, and a present live-map image URL. `resolve_furnished_render` has no `backdrop_source` check, so a layout with an uploaded backdrop can carry furnished data the card never paints.

The art renders as an `<img class="evcc-map-art">` — a **distinct class** from `.evcc-map-image`, so the zone-confirm `naturalWidth` selector, the selection scrim, and the room hit-test never grab it. It is emitted right after the base live `<img>` and before the overlay SVG, so paint order lands it **above the base, below** the robot/dock/path/room overlays. It sits inside `.evcc-map-content-rotator`, so it **co-rotates** with the overlays for free; the transform is stored in the **natural, pre-`live_map_rotation` frame** and the rotator applies the live rotation last. The element is `position:absolute; inset:0; object-fit:contain` — the same letterbox the overlays assume — so an untransformed art exactly fills the overlay frame; the placement transform, `translate(tx%, ty%) rotate(rot deg) scale(sc)` about a 50%/50% origin, is applied inline to the art element only. `_overlayTransform` is untouched.

Two modifier classes carry interaction state: `.evcc-map-art--editable` (config view only) attaches the `furnished-art-drag` handle, and `.evcc-map-art--passthrough` sets `pointer-events: none` while a compose shape is selected — without it the full-frame art swallows every tap and custom-segment placement is silently dead. Room-view art is click-through unconditionally.

The live base `<img>` **stays mounted** in every mode (only its opacity changes, via `.evcc-map-image--furnished-blend` = `0.45` / `--furnished-art` = `0.02`; `live` leaves it untouched at full) so it keeps anchoring the overlay frame and the camera poll alive. In `live` mode the art is not rendered at all. The fade classes ride the live `<img>` only — with the VA raster render active the backdrop is a `<canvas>` that takes no fade class, so art over a self-rendered map composites onto a full-strength raster.

Authoring (config view only) uses an **art-only draft transform** — separate from the segment composer, with no polygon bake — persisted via `set_furnished_art_placement` on save. Nudge / scale / rotate-step buttons mutate the draft directly; the fine rotation-trim slider (±15° around the current angle) applies **absolutely** (`base + value`, `base` captured at gesture start) so re-applying never compounds, and recenters to 0 on release. The pointer-drag and the slider suppress re-renders for the gesture's duration (a card-level `_furnishedGestureActive` flag short-circuits `_scheduleRender`) so the ~2 s live-map poll can't rebuild the element mid-gesture and lose the move; the finish handler clears the flag and renders once.

Upload downscales and recompresses client-side to `maxDim: 2048` before base64 (via `_imageFileToFittedBase64`, which enforces HA's ~4 MiB websocket frame cap — see [map configuration reference](../../advanced/08-map-configuration.md)), then, if the layout is still in `live` mode, auto-flips it to `blend` so a fresh upload is visibly there instead of reading as a no-op. A **Save map image** button downloads the live frame for the trace-over workflow — pure client-side, no service call: read the `src` off the displayed config-view `<img>`, `fetch` → blob → `<a download>`, with the extension taken from the served `Content-Type` and falling back to the URL path so a JPEG/WebP isn't mislabelled `.png`.

The card authors only the **home** scope today (it always uploads `art_scope: "home"`); the per-room `rooms[<id>]` art/viewport fields in the data model are backend scaffolding — wired through the services but not yet surfaced as card controls.

---

## 5. Why the light path works

The whole feature rests on one property: the live overlays are placed in the **device/image frame**, normalized off `map_state_source.image_size` — independent of the backdrop pixels. So compositing any image under the overlays doesn't move them. The art's only job is to *look* right under the overlays, which the user achieves by aligning it over the live frame. No affine solve, no landmark matching, no gate relaxation.

Concretely, `_overlayTransform` reads `mapImageSize()` (the `map_state_source.image_size` pair) and maps image-normalized 0–1 coords into the 0–100 container space, letterboxing a non-square image inside the square box exactly as the zone-clean path does — identity when the size is unknown. The art element uses that same `object-fit: contain` letterbox, which is why an untransformed art starts already registered.

The cost is that the art is pinned to the live map's current crop/scale: if the brand re-renders its map differently between sessions (Eufy re-localizes per session), the art can drift and needs a re-nudge — accepted as a known limitation, with the re-align controls always available. Zone-draw, which lives one z-layer above the art, therefore works over the furnished art on any brand that supports zone cleaning (Eufy and Roborock), at any map rotation, with no extra plumbing — `canDrawZone()` gates on the provider capability plus an overlay-aligned backdrop and never on rotation. Its one temporal gate is unrelated to the art: `frameUngrounded()` suppresses drawing after a map switch until the robot re-localizes, since a screen→device coordinate op would land on the previous map's frame.

See also: [map-state-source](../design/shipped/map-state-source.md) (the overlay frame the art rides), [map configuration reference](../../advanced/08-map-configuration.md#furnished-render), and the [user guide](../../user-guide/18-furnished-render.md).
