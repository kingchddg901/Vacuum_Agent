# Map render — layer stack, room identity, and color resolution

The live map view (`renderers/map.js` → `renderMapRoomView`, used by BOTH the sidebar panel
and the embedded `vacuum-map-host` card) is a **stack of independently-authored layers** that
grew up over several waves. They do NOT share a single fill mechanism, and they touch **several
room-id spaces whose relationship is not fully settled — see §2**. This doc is the map — read it
before touching room fills, overlays, or per-room theming, so you don't re-derive it from code
(it has bitten us).

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
3. **Selection scrim** — `<canvas class="evcc-map-image evcc-map-selection-canvas">`
   (`_renderSelectionScrim` + `_bindSelectionScrim`; it shares `.evcc-map-image` purely for
   LAYOUT — width/height 100% + `object-fit:contain` letterbox parity with the backdrop, and
   "positioned like the backdrop; just needs to be click-through" (`styles/map.js:93-100,938-940`)).
   A subtractive **dark** dim over UN-selected rooms; only present on a *partial* selection. It
   dims, it does not recolor. This scrim keys its selection set directly by managed `room.id`
   against the raster's own `rid` (see §2's disagreement note) — `selected = new Set(
   rooms.filter(r => r.enabled).map(r => Number(r.id)))`, tested with `if (selected.has(rid))
   continue` (`bindings/map.js::_bindSelectionScrim`).
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

## 2. Room-id spaces — RESOLVED 2026-08-06 (was a live disagreement)

| id | Where | What it is |
|---|---|---|
| **raster `rid`** | `room_pixels` byte `>> 2` (`rid_shift`) in `_drawVaRender` | the raster's own per-pixel room id |
| **managed `room.id`** | `Number(attrs.room_id)`, from the device `segments[].id` | the device's declared segment id (`rooms/room_discovery.py:discover_rooms_for_vacuum`, keyed by the adapter's `room_id_key`) |
| **`room_names[rid]`** | render payload `{str(rid): name}` (`map_source.py`) | device's per-rid name |
| **CV `segment_id`** | `"segment_N"` (area-ranked) from the CV segmenter | a **separate** id space |

The codebase used to disagree with itself about whether raster `rid` and managed `room.id` are
the same number. Verified on Alfred all three (rid / `room.id` / `room_names` key) coincided
(Kitchen=5, Office=9, Dining=8, Entryway=6) — the one concrete dataset behind this doc. Two
different generations of code encoded two different beliefs about whether that's a *guarantee*:

- **Treats them as the SAME number, no bridging (older, load-bearing feature code):**
  - `_bindSelectionScrim` builds `selected = new Set(rooms.filter(r => r.enabled).map(r =>
    Number(r.id)))` and tests it directly against the decoded raster `rid`
    (`bindings/map.js::_bindSelectionScrim`) — if they ever diverge for a device, the scrim dims the wrong
    rooms.
  - `_renderRoomSelection`'s clean-order badges look up `order.get(Number(room.number))`, where
    `order` is keyed by `Number(r.id)` and `room.number` is the raw `rid` `rooms_from_room_pixels`
    emits (`map_source.py::rooms_from_room_pixels`, `"number": rid`); the function's own docstring says "Keyed by
    device room number (== managed room id)" (`renderers/map.js::_renderSelectionScrim`).
  - `current_room_for_pixel` returns the raw raster `rid` (`map_source.py::current_room_for_pixel`), and
    `learning/room_attribution_engines.py::PoseSample` documents that return value as **"the MANAGED
    room id"** outright.
- **Treats them as POSSIBLY DIFFERENT spaces, and bridges defensively (newer, Phase-2 palette
  code):** `_drawVaRender`'s per-room override resolves a raster pixel's `rid` → `rd.room_names[rid]`
  → our room *by matching name* (trimmed + lowercased) → `room.color` — it deliberately does NOT
  key by `room.id` directly. The comment at the point of the choice
  (`bindings/map.js#CNFJPTKD`) states this as an asserted, already-confirmed finding, not a
  hedge: *"Keying by room.id directly is WRONG — the raster rid and our stored room.id are
  DIFFERENT id spaces on real devices (empirically verified), so a room.id key lands on no
  pixels (or, worse, another room's)."* The name-bridge itself is at `bindings/map.js#CNZZT0GC`.
- **RESOLUTION (R2-BUG-5, 2026-08-06): the identity-assuming paths are the supported reading;
  the divergence claim has no dataset behind it.** Two facts settle it:
  1. **The raster `rid` space is Eufy-only.** `rooms_from_room_pixels` is the *"Eufy storage
     backend"* by its own docstring, and `map_source.py::zone_membership` states that Roborock has no
     per-pixel raster (`room_number` stays `None` there). So "DIFFERENT id spaces **on real
     devices**" cannot be describing Roborock — there is no Roborock `rid` to differ. The only
     brand with a raster is the one brand where all three ids were *observed* to coincide.
  2. **The claim contradicts its own commit.** `c4207b9`, which introduced both the name-bridge
     and the "empirically verified" comment, describes its own doc changes as
     *"map-render-layers.md (the layer stack, **rid==room.id==room_names identity**, …)"*.
     Identity in the message, divergence in the code comment, same commit.

  So this was never two findings in tension — it was one verified observation against one
  unsourced assertion. **No code changed.** The three identity paths (scrim, clean-order badges,
  current-room attribution) are consistent with all available evidence, and rewriting working
  code to satisfy an unsourced comment is the exact failure
  [00a §9](../history/documentation-epoch-lifecycle.md) warns about — docs are part of the
  measurement apparatus, and a wrong one makes an auditor "fix" correct code.

  The name-bridge is **kept**, relabelled defensive-not-required: it costs one lookup, it can
  never miscolor (a name miss falls through to the palette), and it is the safe side if some
  firmware we have never seen does diverge. What we cannot rule out is that the original author
  saw divergence on an Eufy firmware there is no record of and wrote the commit body carelessly —
  hence keeping the bridge rather than deleting it. Keying a raster override by the CV
  `segment_id` is WRONG regardless (different space, and it's a string → `NaN`).
- **CV `segment_id` ↔ room** is indirect: `state.roomIdForSegment(seg.segment_id)` → `seg.room_id`.
  The SVG polygons + labels use this; the raster does not (it has no segments, just rid pixels).

## 3. Room-color resolution (the one cascade)

Single source of truth: **`src/cards/map-room-color.js`**. Cascade, resolved the same everywhere:

> **per-room override (`room.color`) ▸ theme token (`--evcc-room-fill-N`) ▸ default palette**

- **SVG** consumes it via `roomFillCss(idx, override)` → a concrete hex (override) or
  `var(--evcc-room-fill-N, default)` (rides the live CSS cascade). Idx = render order.
- **Raster** can't take CSS vars, so `_drawVaRender` resolves RGBs: the palette once per slot
  (`roomFillRgb`, one `getComputedStyle` read), plus a per-rid override map
  (`roomOverrideRgb` via `rd.room_names`, bridged by name — see §2). An un-overridden pixel takes
  palette slot **`(rid − 1) mod N`** — rid-derived, NOT render order (render order is the SVG
  path's index rule instead; `bindings/map.js#CNYVDQ9S`, `ROOM_FILL_N` = 12,
  `cards/map-room-color.js::ROOM_FILL_PALETTE`). An `overrideSig` in the `_vaImageCache` key repaints on
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
[architecture-overview.md](architecture-overview.md) (the four-layer card + floor textures),
`docs/dev/frontend/furnished-render.md`, `docs/dev/frontend/themeable-map-palette.md` (the color feature design).
