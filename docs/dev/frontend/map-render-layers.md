# Map render — layer stack, room identity, and color resolution

The live map view (`renderers/map.js` → `renderMapRoomView`, used by BOTH the sidebar panel
and the embedded `vacuum-map-host` card) is a **stack of independently-authored layers** that
grew up over several waves. They do NOT share a single fill mechanism, and they use **two
different room-id spaces**. This doc is the map — read it before touching room fills, overlays,
or per-room theming, so you don't re-derive it from code (it has bitten us).

## 1. The layer stack (bottom → top = DOM order = paint order)

Inside `.evcc-map-content-rotator`, in order (later paints ON TOP; most rely on DOM order, not
`z-index`):

1. **Backdrop** — EITHER `<canvas class="evcc-map-image evcc-map-render-canvas">` (the VA raster,
   `vaActive`) OR `<img class="evcc-map-image">` (the live camera map). Canvas **XOR** img, never
   both. The VA raster is the **visible room fill** and is where per-room color overrides land
   (`bindings/map.js` → `_drawVaRender`). Non-room pixels are transparent → the themed container
   background reads as floor.
2. **Furnished art** — `<img class="evcc-map-art">`, rendered only when a **furnished layout** is
   active AND render mode ≠ `live` (`_renderFurnishedArt`). A static, to-scale, user-aligned image
   at **full opacity, exactly over the backdrop**. ⚠️ **In furnished (blend/art) mode this covers
   the live map — including room colors.** That's by design: furnished replaces the live render.
   Room colors are a **live-map** feature; see the gotcha in §4.
3. **Selection scrim** — `<canvas class="evcc-map-selection-canvas">` (`_renderSelectionScrim` +
   `_bindSelectionScrim`). A subtractive **dark** dim over UN-selected rooms; only present on a
   *partial* selection. It dims, it does not recolor.
4. **`<svg class="evcc-map-svg">`** — contains, in order:
   - floor-texture `<defs>` (`_buildFloorTextureDefs`);
   - **room polygons** (`_renderMapSegmentPolygon`) — `fill: transparent` unless selected, so they
     only ever show the color as a **0.25 selection tint**, NOT the visible fill;
   - **floor-texture polygons** (`_renderFloorTexturePolygon`) — a per-room texture pattern that
     paints OVER the raster. **Suppressed for a room that has a color override** (the override is
     that room's fill), else it would cover the recolor and let it peek only at the edge;
   - device overlays (`_renderDeviceOverlaySvg` — current room / walls / path / robot / dock / …).
5. **Mascot** — `<div class="evcc-map-animal">`.
6. **Labels & chips** — room-name labels, area (m²) chips, clean-order badges, hidden regions.

**Key consequence:** the room's *visible* fill is the **VA raster canvas** (layer 1). Anything
opaque above it (furnished art, floor texture) will hide a raster recolor. The SVG room polygons
do NOT provide the fill — they're transparent except as a selection tint.

## 2. Two room-id spaces (do not conflate)

| id | Where | What it is |
|---|---|---|
| **raster `rid`** | `room_pixels` byte `>> 2` (`rid_shift`) in `_drawVaRender` | the device's native room id |
| **managed `room.id`** | `Number(attrs.room_id)`, from the device `segments[].id` | the device's native room id |
| **`room_names[rid]`** | render payload `{str(rid): name}` (`map_source.py`) | device's per-rid name |
| **CV `segment_id`** | `"segment_N"` (area-ranked) from the CV segmenter | a **separate** id space |

- **`rid == room.id == room_names` key** — all three derive from the same device segment id.
  Verified on Alfred (Kitchen=5, Office=9, Dining=8, Entryway=6). So the raster override map is
  keyed by rid, resolved rid → name (`rd.room_names`) → our room (by name) → `room.color`. Keying
  a raster override by the CV `segment_id` is WRONG (different space, and it's a string → `NaN`).
- **CV `segment_id` ↔ room** is indirect: `state.roomIdForSegment(seg.segment_id)` → `seg.room_id`.
  The SVG polygons + labels use this; the raster does not (it has no segments, just rid pixels).

## 3. Room-color resolution (the one cascade)

Single source of truth: **`src/cards/map-room-color.js`**. Cascade, resolved the same everywhere:

> **per-room override (`room.color`) ▸ theme token (`--evcc-room-fill-N`) ▸ default palette**

- **SVG** consumes it via `roomFillCss(idx, override)` → a concrete hex (override) or
  `var(--evcc-room-fill-N, default)` (rides the live CSS cascade). Idx = render order.
- **Raster** can't take CSS vars, so `_drawVaRender` resolves RGBs: the palette once per slot
  (`roomFillRgb`, one `getComputedStyle` read), plus a per-rid override map
  (`roomOverrideRgb` via `rd.room_names`). An `overrideSig` in the `_vaImageCache` key repaints on
  a recolor, like `paletteSig` does for a theme change.
- **Floor texture** is suppressed for an overridden room (see layer 4) so the override is the fill.
- `room.color` is a `#rrggbb` string or `null`, stored per-room (`update_room_fields`, models
  `RoomConfig.color`), surfaced on the room-switch entity → `_normalizeRoom` → `room.color`.

Themeless + no overrides ⇒ the default palette ⇒ byte-identical to the pre-feature render.

## 4. Gotcha: "my room color isn't showing"

Almost always a **layer covering the raster**, not a color/mapping bug:

- **Furnished (blend/art) mode** — the `evcc-map-art` image (layer 2) sits over the live map. Room
  colors only show in **`live`** render mode / a non-furnished layout. This is intended.
- **Floor texture** — if a textured floor covered an overridden room it'd peek only at the edge
  (~7% raster-vs-CV-polygon shape mismatch). Handled by the override-suppression in layer 4.
- To debug the stack, dump `canvas.parentElement.children` (tag/class/opacity/rect) from
  `_drawVaRender`; to debug identity, dump `rd.room_names` + the managed rooms + a rid histogram.

## See also

`docs/dev/map-state-source.md` (VA render payload + `room_names`), `docs/dev/11-mapping-system.md`,
`docs/dev/19-card-architecture.md` (the four-layer card + floor textures),
`docs/dev/32-furnished-render.md`, `docs/dev/themeable-map-palette.md` (the color feature design).
