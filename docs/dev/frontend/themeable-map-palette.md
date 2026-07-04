# Themeable map room-fill palette — design

**Status:** SHIPPED 2026-07-03 (Phases 1 & 2). Per-room color override + theme-palette fallback
("2 with 1 as a fallback"). The palette tokens (`--evcc-room-fill-N`) + resolver
(`cards/map-room-color.js`) + per-room `room.color` override are live on both render paths.
**Learned the hard way:** the room's *visible* fill is the VA raster canvas, and anything opaque
above it (the **furnished-art** image in non-`live` mode, or a floor texture) hides a recolor — so
room colors are a **live-map** feature. The full layer stack + `rid == room.id == room_names`
identity is now documented in **[map-render-layers.md](map-render-layers.md)** — read that first.
Phase 3 (label ink by luminance) **DROPPED** 2026-07-03 — the label pills carry their own
contrast; validated readable at the `#ffffff` + `#000000` room-color extremes, so per-luminance
ink switching buys nothing.

## Problem

Almost every color surface in the card is themeable — map **overlay** colors (`--evcc-map-ov-*`, in `theme-tokens/map.js`), the room-**card** chips (`--evcc-room-chip-*`, `theme-tokens/room-cards.js`), shell/surfaces/status, etc. The one **forced** surface — and the biggest visual area — is the map **room fills**:

- **SVG segments** — `_SEGMENT_COLORS` (a hardcoded rainbow in `renderers/map.js`), consumed at `_renderMapSegmentPolygon` (`renderers/map.js:806`) and the furnished path (`:1147`) via an inline `--seg-color`.
- **VA raster** — `_vaRoomColor` (`bindings/map.js:304`, a separate hardcoded `_VA_ROOM_COLORS`), painting canvas pixels in `_drawVaRender`.

A user can't recolor their rooms, and (surfaced 2026-07-03) the fixed palette can collide with UI drawn over it. The zone-select collision is **already fixed** independently (color-independent casing on `.evcc-zone-rect` + drop-shadow on `.evcc-map-ov-savedzone`), so this doc is only about the *room fills*.

## Design — the cascade

Per room, resolve the fill color in this order (the same `override > theme > default` cascade the rest of the theme system uses):

1. **Per-room override** — a color the user assigned to *this specific room* (stable, keyed by `room_id`). If set → use it.
2. **Theme palette** — the theme's color for this room's **index** (`--evcc-room-fill-N`). If the theme sets it → use it.
3. **Default rainbow** — `_SEGMENT_COLORS[index]` (today's behavior).

Degrades gracefully: touch nothing → today's rainbow; set a theme palette → whole map recolors; override one room → just that room changes.

### One cascade, two consumption modes

The SVG path can ride the CSS cascade; the raster can't (canvas takes no CSS vars). Both consume **one** shared source of truth (`cards/map-room-color.js` — the default array, the index rule, the per-room lookup) so they can't drift:

- **SVG** — `roomFillCss(idx, override)` returns a CSS string: a concrete override hex if the room is overridden, else `var(--evcc-room-fill-<idx>, <default hex>)`. CSS resolves theme-token-or-default and picks up a live theme change with no re-render.
- **Raster** — `roomFillRgb(idx, host)` reads the *computed value* of `--evcc-room-fill-<idx>` off the host as `[r,g,b]` (one `getComputedStyle(host)` read per render, cached), and `roomOverrideRgb(value)` resolves a per-room override hex to `[r,g,b]` (or `null`) when set. A theme change busts the `_vaImageCache` so the canvas repaints.

### Index vs id (the split that makes it coherent)

- The **theme palette** is indexed by **render order** (`idx = segIndex % N`) — a base palette that "cycles by position," matching `_SEGMENT_COLORS[idx]` today. Not stable across a re-segment; that's fine — it's a *base look*, not a per-room promise.
- The **per-room override** is keyed by **`room_id`** — stable across re-segment/re-render, because it's a promise about a specific room.

## Contracts

- **Storage:** `room.color` — a `#rrggbb` string or `null`, on the per-map room bucket (alongside name/settings; `room_id` storage key per the locked room-identity model). New service `set_room_color(vacuum, map_id, room_id, color|null)`, or fold into the existing room-settings save.
- **Tokens:** `--evcc-room-fill-1` … `--evcc-room-fill-N` where **N = `_SEGMENT_COLORS.length`**, added to `MAP_TOKENS` (`theme-tokens/map.js`) — **defaults = the current `_SEGMENT_COLORS`**, so a themeless card is byte-for-byte today's render. They auto-surface in the theme editor (registry is array-driven) and resolve via `applyDynamicTheme`.
- **Resolver:** `cards/map-room-color.js` — the single definition of `perRoom ?? token ?? default`, exposed as three thin functions: `roomFillCss(idx, override)` → a CSS string (`"var(--evcc-room-fill-N, #default)"`, or a concrete override hex) for the SVG path; `roomFillRgb(idx, host)` → `[r,g,b]` reading the computed `--evcc-room-fill-N` token for the raster palette; and `roomOverrideRgb(value)` → `[r,g,b] | null` for the raster per-room override.
- **Label ink:** `labelInk(fillHex)` → `"#000" | "#fff"` by WCAG relative luminance, so a light user-chosen room color keeps its centroid room-name label + m² chip readable (replaces the fixed white).

## Phases (each shippable, gated `check:i18n`/`check:styles`/build/tests)

- **Phase 1 — resolver + theme palette (NET-ZERO visual):** add the `--evcc-room-fill-N` tokens (defaults = today's rainbow) + `mapping/map-room-color.js`; wire *both* render paths through it. Themeless render is unchanged; a theme can now recolor the whole map. Raster cache-busts on palette change.
- **Phase 2 — per-room override:** `room.color` storage + service + a color picker in the **room editor** (it already holds per-room name/settings) + cascade so per-room wins. (`map-tap → color` is a later nicety, not this phase.)
- ~~**Phase 3 — label contrast by luminance:**~~ **DROPPED** — the label pills already carry
  contrast (own background + light ink); validated at `#ffffff`/`#000000`, so `labelInk` is moot.
- **Phase 4 (optional):** per-room "reset to default", a few palette presets, an editor contrast hint.

## Reuse (this is a delta, not a rebuild)

- Room storage already holds per-map per-room data → add one `color` field.
- The theme registry is array-driven → the palette is N more `mapToken.color(...)` lines in an existing group; editor surfacing + resolution are automatic.
- `--evcc-room-fill-opacity` already exists (room-cards) — the palette is its natural sibling.
- The color-independent select/overlays (2026-07-03 casing fix) mean UI drawn over recolored rooms already survives.

## Design-care / open questions

- **Raster cache invalidation** — key `_vaImageCache` by a palette/override version (or the resolved-colors hash) so a theme or per-room change repaints. Cheapest: include a palette signature in the existing version key.
- **`getComputedStyle` cost** — read the N palette tokens once per raster render (they're few); cache within the render.
- **Editor grouping** — palette tokens under `MAP_TOKENS`, or a dedicated "Map Rooms" group for clarity? (Cosmetic; either surfaces.)
- **Color picker placement** — room editor (has room context) is the Phase-2 home; map-tap is deferred.
- **Contrast is advisory, not enforced** — we recolor and adapt the label ink, but don't block a low-contrast choice (match `feedback_map_render_aesthetics`: let the user see the LOOK; warn, don't nanny).

## Out of scope

Map **overlay** colors (already tokens), room-**card** chips (already tokens), the animal/mascot colors, and the CV/segmentor internals. The mapping/theme systems this rides on: `docs/dev/11-mapping-system.md`, `docs/dev/frontend/theme-system.md`, `docs/dev/map-state-source.md`.
