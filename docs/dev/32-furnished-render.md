# 32 — Furnished Render

Furnished render overlays a user-supplied, to-scale image of the home **over the live map**, with the live robot/dock/path/room overlays composited on top. It is a **light path**: no georeference, no coordinate solve. The art is aligned by the user over the live frame once, and that placement *is* the registration — the overlays already ride the live frame (via `_overlayTransform`, keyed off `map_state_source.image_size`), so they land correctly regardless of what backdrop is painted underneath.

It is a cross-cutting feature — a per-layout data model, a pure resolver, three services, and a frontend art layer — and is brand-agnostic: it rides any live-map backdrop (Eufy via jeppesens eufy-clean's mainline live-map camera, Roborock, etc.) with a single build.

---

## 1. Data model (per custom layout)

The furnished state lives on each `custom_layouts[<id>]` record (see [data model](03-data-model.md)), never at the map-bucket level (so it can't leak across layouts):

- `home_art: {art_variant, art_placement_transform: {tx, ty, scale, rotation}}` — the whole-home art.
- `rooms: {<room_id>: {art_variant?, art_placement_transform?, viewport?: {cx, cy, zoom}, render_mode?}}` — per-room overrides.
- `render_mode: "live" | "art" | "blend"` — the layout-level mode (absent ⇒ `live`).

Transforms and viewports are **resolution-independent percentage floats** (`scale` clamped `[0.05, 20]`, rounded to 4 dp on write). The structure is schema-free and minted lazily — `rooms` starts `{}`; `home_art` / `render_mode` appear on first write. The art image itself is stored as an image variant — `custom_<id>_home_art` or `custom_<id>_room_<rid>` — distinct from the layout's `backdrop_variant`, which it never replaces.

---

## 2. Services

All three are map-scoped (operate on the **active** custom layout, returning `no_active_layout` when none is active), `supports_response`, and return the resolved `furnished_render`. See the [services reference](../advanced/03-services.md#furnished-render) for parameters.

| Service | Writes |
|---|---|
| `set_furnished_art_placement` | `home_art.art_placement_transform` (scope `home`) or `rooms[<id>].art_placement_transform` (scope `room`). All-null clears it; scale clamped `[0.05, 20]`. |
| `set_furnished_render_mode` | layout `render_mode` (no `room_id`) or `rooms[<id>].render_mode`. A blank `room_id` is treated as layout-level (never a junk `rooms[""]`). |
| `set_room_viewport` | `rooms[<id>].viewport`. All-null clears it. |

`upload_map_image` is extended with `art_scope` (`home` \| `room`) + `room_id`: it writes the furnished-art variant and points `home_art.art_variant` / `rooms[<id>].art_variant` at it, leaving `backdrop_variant` untouched.

---

## 3. Surfacing

- **`resolve_furnished_render(map_bucket)`** (`mapping/map_source.py`) — a pure projection: `None` unless the map is in custom mode and the active layout carries furnished data; otherwise it resolves each `art_variant` to a browser URL and returns the art + transform + mode. Added to the dashboard snapshot as the **`furnished_render`** key.
- **`get_map_segments`** — the per-layout summary now also projects `render_mode` / `home_art` / `rooms`, so the card can render the furnished panel without a second fetch.
- **`delete_custom_layout`** sweeps the layout's furnished-art image variants alongside its backdrop.

Two read paths feed the card: the **editor** (config view) uses the active layout's `get_map_segments` summary, authoritative while authoring; the **plain room view** uses the snapshot's `furnished_render`.

---

## 4. Frontend (the card)

The art renders as an `<img class="evcc-map-art">` — a **distinct class** from `.evcc-map-image`, so the zone-confirm `naturalWidth` selector, the selection scrim, and the room hit-test never grab it. It is emitted right after the base live `<img>` and before the overlay SVG, so paint order lands it **above the base, below** the robot/dock/path/room overlays. It sits inside `.evcc-map-content-rotator`, so it **co-rotates** with the overlays for free; the placement transform (`translate% rotate scale`) is applied inline to the art element only — `_overlayTransform` is untouched.

The live base `<img>` **stays mounted** in every mode (only its opacity changes: `live` 1, `blend` ~0.45, `art` ~0.02) so it keeps anchoring the overlay frame and the camera poll alive. In `live` mode the art is not rendered at all.

Authoring (config view only) uses an **art-only draft transform** — separate from the segment composer, with no polygon bake — persisted via `set_furnished_art_placement` on save. The pointer-drag and the fine-trim slider suppress re-renders for the gesture's duration (a card-level `_furnishedGestureActive` flag short-circuits `_scheduleRender`) so the ~2s live-map poll can't rebuild the element mid-gesture and lose the move; the finish handler clears the flag and renders once. A **Save map image** button downloads the live frame (client-side: fetch the displayed `<img>` src → blob → `<a download>`) for the trace-over workflow. The card authors only the **home** scope today (it always uploads `art_scope: "home"`); the per-room `rooms[<id>]` art/viewport fields in the data model are backend scaffolding — wired through the services but not yet surfaced as card controls.

---

## 5. Why the light path works

The whole feature rests on one property: the live overlays are placed in the **device/image frame**, normalized off `map_state_source.image_size` — independent of the backdrop pixels. So compositing any image under the overlays doesn't move them. The art's only job is to *look* right under the overlays, which the user achieves by aligning it over the live frame. No affine solve, no landmark matching, no gate relaxation.

The cost is that the art is pinned to the live map's current crop/scale: if the brand re-renders its map differently between sessions (Eufy re-localizes per session), the art can drift and needs a re-nudge — accepted as a known limitation, with the re-align controls always available. Zone-draw, which lives one z-layer above the art, therefore works over the furnished art on any brand that supports zone cleaning (Eufy and Roborock), at any map rotation, with no extra plumbing.

See also: [map-state-source](map-state-source.md) (the overlay frame the art rides), [map configuration reference](../advanced/08-map-configuration.md#furnished-render), and the [user guide](../user-guide/18-furnished-render.md).
