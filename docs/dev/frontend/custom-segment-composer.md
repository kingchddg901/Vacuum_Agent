# Custom Segment Composer

This doc covers the custom-segment composer: the in-map UI mode that lets a user author rooms by hand from primitive shapes (no CV), and the state/bindings/render machinery behind it. It is one panel in the frontend doc set — start at [architecture-overview.md](architecture-overview.md) for the hub, and see [map-render-layers.md](map-render-layers.md) for how the composer canvas sits in the map's render stack.

The composer is a UI mode **within the map view**, active when `get_map_segments` reports `segmentation_mode = "custom"`. It lets the user author rooms by hand from primitive shapes — no CV — and writes them back through `set_custom_segments`. The state lives in `src/state/map.js` (the `proto.compose*` methods), bindings in `src/bindings/map.js`, rendering in `src/renderers/map.js`. The composer canvas draws over the **active layout's** `custom_<layout_id>` backdrop variant (rendered `object-fit: fill`, so the authored pct-space lines up with the image the segment writer rasterises against).

A map holds **many named custom layouts**, not one — each with its own backdrop, authored rooms, room links, and mascot anchors. The composer always edits the *active* layout, so everything below is scoped to it.

The backend contract for the services referenced here (`set_custom_segments`, `create_custom_layout`, `get_map_segments`, etc.) is documented in [backend-contract-and-data-shapes.md](backend-contract-and-data-shapes.md).

## The layout picker

`_renderSegmentationToggle` (in `src/renderers/map.js`) replaces the old binary CV/Custom toggle with a **layout picker** that mirrors the run-profiles chip strip:

- An always-present **`Auto (CV)`** chip (`data-action="set-segmentation-mode"`, `data-mode="cv"`) selects the map-bucket CV store.
- One chip **per named layout** (`data-action="set-active-custom-layout"`, `data-layout-id`) — tapping it activates that layout and flips the map into `custom` mode. Switching a chip swaps the whole layout: backdrop, authored rooms, room links, and mascot home all change together.
- A **`＋ New`** chip (`data-action="open-new-layout"`) opens an inline name editor.
- When a custom layout is active, a **Rename** (`open-rename-layout`) and **Delete layout** (`delete-layout`) control row appears.
- The **inline name editor** (`isLayoutEditorOpen` / `layoutEditorMode` / `layoutDraftName`) is a text input plus Create/Save + Cancel; `data-layout-field="name"` feeds `setLayoutDraftName`.

The picker is backed by new actions in `src/actions/map.js`: `createCustomLayout(mapId, name)`, `renameCustomLayout(mapId, layoutId, name)`, `deleteCustomLayout(mapId, layoutId)`, and `setActiveCustomLayout(mapId, layoutId)` — thin wrappers over the four layout services in the [backend contract](backend-contract-and-data-shapes.md). After any of them resolves, the binding re-fetches `get_map_segments` so the picker and canvas reflect the new active layout.

The **per-layout backdrop upload** rides the shared `upload-map-variant` binding: when the variant starts with `custom`, the binding adds `layout_id = activeCustomLayoutId()` to the `upload_map_image` call, and the server forces the variant key to `custom_<layout_id>` and repoints that layout's `backdrop_variant`.

## The draft model

The draft is an in-memory array of **shapes** (not yet persisted). Each shape is one piece of geometry; all coordinates are 0–100 percentages of the map:

| Field | Meaning |
|---|---|
| `id` | Stable shape id (`draft_N` for new shapes; reloaded shapes keep their saved segment id) |
| `type` | `rect` \| `circle` \| `polygon` |
| geom | `rect`: `x, y, w, h` · `circle`: `cx, cy, r` · `polygon`: `points: [[x, y], …]` |
| `group?` | Groups merged pieces; **defaults to the shape's own `id`** — an un-merged shape is its own room |
| `op?` | `subtract` carves the piece out of its group (a cutout); absent = fill |
| `room_id?` | The room this shape's group is linked to |
| `angle?` | Rotation in degrees, **rect-only** (applied at render, baked to a polygon on save) |

Composer state on the `VacuumCardState` instance (all `proto.compose*`):

- `composeDraft` — the shape array (lazily `[]`).
- `composeSelectedId` — the currently selected shape.
- `composeMergeFrom` — the pending merge target during the two-tap merge flow.
- `composeMoveScope` — `room` (move the whole group, the default) or `piece` (move just the selected shape). Shaping is always per-piece.
- `composeStep` — nudge step in pct (Fine 1 / Med 3 / Coarse 7; default 3); scales both move and resize.
- `composeLoadedFor` — the `${map_id}:${active_custom_layout_id}` key (`_composeKey(data)`) the draft was last reloaded for (the once-per-active-layout guard; switching layouts reloads that layout's shapes).

## Operations

All operations are button-driven (mobile-friendly, no drag required), and geometry stays clamped to the 0–100 canvas:

- **Add** — `addComposeShape("rect" | "circle")` appends a cascaded shape and selects it.
- **Select** — `selectComposeShape(id)`.
- **Move** — `moveComposeScoped` / `placeComposeScoped` route by `composeMoveScope`: a merged room moves as a group (`moveComposeGroup` / `placeComposeGroup`, clamped on the group bbox) unless scope is `piece`. Standalone shapes ignore the scope.
- **Tap-to-place** — `placeComposeShape` jumps the selected shape's centre to a tapped point.
- **Scale** — `scaleComposeShape(id, factor)`, centred.
- **Resize (W/H)** — `resizeComposeShape(id, dim, delta)`, **rect-only**, centred.
- **Rotate** — `rotateComposeShape(id, ±15°)`: a rect accumulates `angle`; a polygon rotates its points about its bbox centre; a circle is a no-op.
- **Merge** — a two-tap flow: `startComposeMerge(targetId)` then `mergeComposeShapes(targetId, memberId)` moves the member's whole group into the target's group (so two pieces rasterise into **one** group-coloured segment) and unifies the room link.
- **Cut** — `toggleComposeOp(id)` flips a grouped shape to `op: "subtract"` (rendered dashed/red), carving a hole out of its room.
- **Split** — `splitComposeShape(id)` returns a piece to being its own standalone segment (clears `group`, `op`, and the duplicated `room_id`).
- **Link to room** — `assignComposeRoom(id, roomId)` sets `room_id` on every group-mate (a room links to a whole merged group, 1:1; re-tapping the linked room clears it).

## Save and re-edit

**Save** is a two-step reconcile, driven from the binding:

1. `composeToSegments()` maps the draft to the `set_custom_segments` payload. It buckets shapes by `group` (one bucket = one segment/room), **orders `subtract` primitives last** within each bucket (so cutouts are drawn after the fills they carve), bakes a rotated rect into a `polygon`, and carries the group's `room_id`.
2. The binding calls `setCustomSegments(mapId, segments)` (replace-all), then reconciles room links **per segment** via `setSegmentRoomLink(mapId, seg.id, seg.room_id ?? null)`, so the new segment ids match their linked rooms.

**Re-edit**: `maybeLoadComposeDraft(data)` runs once per active layout (guarded by `composeLoadedFor` against `_composeKey(data)` = `${map_id}:${active_custom_layout_id}`) and rebuilds the draft from the saved segments via `loadComposeDraftFromSegments`. Because the backend stores polygons (not the original primitives), reloaded shapes come back as editable `polygon` shapes, with their saved `segment_id` and `room_id` preserved. Switching to another layout re-keys the guard and reloads that layout's shapes; it will not clobber an in-progress draft or reload immediately after a save.

## Geometry boundaries

One segment = one room. Multiple primitives sharing a `group` merge into a single room. `op: subtract` carves from that room — an **edge cut** yields a concave but still simple polygon, while an **interior hole** cannot be represented by a single boundary polygon (the tracer, `mask_to_polygon`, returns one outer loop). Authors who need a true donut should instead bound the hole with edge cuts. The whole read → adjust → link → dispatch chain is shared with CV segments: `set_custom_segments` wraps each authored polygon in the same segment shape the segmenter produces, so room-linking and dispatch treat custom and CV segments identically. How these authored polygons sit in the map's draw order relative to the CV base and the live overlay is covered in [map-render-layers.md](map-render-layers.md).

## Map toolbar toggles

Two per-vacuum display toggles live in the Rooms-view map toolbar (`src/renderers/rooms.js`), independent of the composer:

- **Companion (paw button)** — `data-action="map-animal-toggle"` flips `mapAnimalEnabled` (localStorage `evcc_animal_on_<vac>`, default on). When off, `_renderMapAnimal` returns `""`. This is separate from animal *selection* — toggling off then on keeps the chosen animal. When docked/idle the companion homes to the reserved `dock` key in the active scope's `companion_anchors` (a spot, not a room); dragging it there writes that key, falling back to the resolved segment's centroid until set. Because `set_companion_anchor` routes through `_resolve_active_scope`, the `dock` spot (and every room anchor) is **per-layout** in custom mode and lives on the map-bucket dict for CV — so each custom layout can park its mascot in a different place.
- **Floor textures (two hatch buttons)** — `data-action="map-texture-toggle"` flips `mapFloorTextureEnabled` (localStorage `evcc_floor_tex_map_<vac>`) for the map texture surfaces (`_renderFloorTexturePolygon` / `_buildFloorTextureDefs`); `data-action="room-texture-toggle"` flips `roomFloorTextureEnabled` (`evcc_floor_tex_rooms_<vac>`) for the room-card layers (`_renderFloorTextureLayer`). Both default on (seeded from the legacy `evcc_floor_tex_<vac>` on first read); when off the respective renderer short-circuits to `""`.

---

The composer is one of the three standalone-map surfaces; how the map renderer mixin is hosted in the standalone dashboard card (`<eufy-vacuum-map>`) is covered in [card-topology-and-bundles.md](card-topology-and-bundles.md).
