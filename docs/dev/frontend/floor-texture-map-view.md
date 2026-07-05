# Floor-texture map view — render, tokens, masks, tuning

A third map render mode that paints each room with its floor **material** (wood, tile,
marble, concrete, granite, carpet…) as **one continuous floor**, not a per-room patchwork.
Toggle: the **▨** button next to the VA-render (**▦**) toggle, once the VA raster canvas is
active. Works on any brand with a room raster (Eufy CV + the Roborock raw-map decode).

This doc is the render + material side. For where the floor layer sits in the map paint
order see [map-render-layers.md](map-render-layers.md); for the theme editor groups that
expose these tokens see [theme-system.md](theme-system.md).

## How it renders (mechanism A — raster clip)

`bindings/map.js` `_drawVaFloorRender` clones the `_drawVaRender` per-pixel `room_pixels`
decode, but each room's pixels are painted from its floor **type's composited material**
instead of a flat colour. Continuous by construction: the material is sampled in map space,
so adjacent same-type rooms line up. The output ImageData is cached and re-stamped on
zoom/select (see [Caches](#caches)).

Each material is built by `compositeFloorTexture` (`src/textures/floor-texture-compositor.js`
— pure, unit-tested) from the `FLOOR_TEXTURE_REGISTRY` entry — layers composited
**bottom → top over an opaque base**:

```
layerAlpha(texel) = (mask luminance / 255) × layerOpacity × colorAlpha   // white reveals
out = layerColour × layerAlpha + out × (1 − layerAlpha)                  // stays opaque
```

The buffer is **seeded with the base-role layer's colour** (`resolved[baseIdx].color`, else
layer 0), then every layer composites over it. Keep that seed in mind — it drives the single
biggest gotcha below.

## The layer + colour model — and the "invisible on the map" gotcha

A material is an ordered list of layers in `FLOOR_TEXTURE_REGISTRY` (`src/textures/floor-texture-registry.js`).
Each layer is `{ url (mask PNG), role, colorToken, colorDefault, opacityToken, opacityDefault }`
(veins add `blurToken`/`blurDefault`). The mask is a grayscale PNG: **white reveals the
layer colour, black hides it.**

> ### ⚠ A layer whose colour equals the base colour is INVISIBLE on the map
> The map seeds the buffer with the base-role layer's colour, then composites each layer
> **over** it. So a layer painted in that **same colour** is base-over-base — it contributes
> nothing visible on the map, no matter its mask or opacity. The **card does not hit this**:
> `renderers/floor-texture-surface.js` composites the layers (as CSS `mask-image` spans) over
> the **card's own surface** — a transparent container — not the material base. So the same
> layers show fine on room cards but can vanish on the map.
>
> This was the root cause of "map wood is flat / planks only in the centre": wood's depth and
> grain layers both used `--evcc-floor-wood-base`, so only the (accent-coloured) seam layer
> showed. **Rule: a material's definition/detail layers must use a colour DISTINCT from the
> base-role layer.** If a material reads detailed on the card but flat on the map, check for
> same-as-base layer colours FIRST.

### Colour resolution (matches the card's CSS)

`_resolveFloorColor` resolves each token **on a hidden probe element beside the map canvas**
(so it inherits the theme vars), by applying the value as a real `color` property and reading
the computed rgb. That's what lets `var()`, `oklch(from var(...) …)` (the marble minor-vein
default), and 8-digit hex all become real rgb — a bare hex parser returns grey for anything
but 3/6-digit hex. The colour's own alpha is folded into the layer opacity.

## Mask decode — reliability

`_decodeMaskLum(url, W, H, scale, rotate)` loads a mask and returns a per-texel luminance
array. Two hard-won robustness features:

- **`createImageBitmap(fetch → blob)`**, not `HTMLImageElement.decode()`. Under a burst of
  ~15–20 large (2048²) decodes (every present material × its layers, kicked at once), plain
  `img.decode()` rejects a **random** couple per load with *"The source image cannot be
  decoded"* — the file is valid and served 200; the decoder (or the static server under the
  burst) just drops some. `createImageBitmap` is the purpose-built off-DOM decode and is far
  less flaky; `Image`+`decode` is kept only as a fallback.
- **Concurrency cap + retry.** `_enqueueMaskDecode` / `_pumpMaskDecodeQueue` cap concurrent
  decodes at **3** so the burst can't overwhelm the decoder/server; each decode **retries up
  to 4×** with backoff so a transient loss recovers instead of caching a blank.

A decode that still fails caches a **zero-luminance sentinel** (that layer reveals nothing →
base shows through) rather than never caching — otherwise it re-kicks every render (infinite
loop). So a broken mask degrades to flat base colour, it doesn't hang.

> **Debugging a flat material:** temporary `[EVCC-FLOOR-DIAG]` console logs in
> `_decodeMaskLum` / `_ensureFloorTextures` report resolved colours + decoded `lumMean`/`lit%`.
> `curl`-ing the HA static path (`/eufy_vacuum/textures/<dir>/<mask>.png`) isolates
> server-vs-browser. If the **failing set is random per load**, it's the concurrency race, not
> the file — don't chase a re-encode.

## Caches

Three layers, all in `_ensureFloorTextures` / `_drawVaFloorRender`, keyed so a change busts
exactly what it should:

| Cache | Key | Busts on |
|---|---|---|
| `_floorMaskCache` (raw luminance) | `url \| W×H \| scale \| rotate` | mask/size/scale/rotation |
| `_floorTexCache` (composited RGBA) | `ft \| W×H \| scale \| rotate \| colorSig` | + resolved colours/opacities |
| `_vaFloorImageCache` (final map ImageData) | `version \| CW×CH \| paletteSig \| ridTypeMap \| texSig` | + any type's `texSig` |

`texSig` (the sorted join of each ready type's texKey) is what makes a **live theme edit to a
floor colour repaint the map** — `paletteSig` is the room-fill palette, and the ready list is
just type names, so without `texSig` a recolour left the outer image stale until a resize.

**Asset cache-bust:** every mask URL carries `?v=<hash>` where the hash is `hashDir(textures)`
(`scripts/build-card.mjs`). Change any mask's bytes → new hash → new URL → the browser/service-
worker refetch. Re-running the build after `gen_floor_masks.py` does this automatically.

## Per-material feature scale

`FLOOR_TEXTURE_MASK_SCALE_BY_TYPE` in `bindings/map.js` scales each material's mask pattern so
its features are the right apparent size on the map (1.0 = native = "zoomed in"; **lower =
finer/denser**). Map-only (the card shows one cover-fit swatch, no scale). Applied in the
pattern matrix; clamped to `[0.02, 2]`.

| Key | Scale |
|---|---|
| `marble` | 0.05 |
| `tile` | 0.05 |
| `wood` | 0.05 |
| `concrete` | 0.16 |
| `granite_light` | 0.05 |
| `carpet_low` | 0.09 |
| `carpet_high` | 0.09 |
| *(global fallback)* | 0.05 |

A theme token **`--evcc-floor-<type>-map-scale`** overrides the per-type default (per-type ›
global). `_resolveFloorScale` reads it; the token segment is **hyphenated** (`carpet-low`) to
match the `--evcc-floor-*` convention, so the underscored resolver key is normalised first.

> **Gotcha:** the JS keys MUST match `resolveFloorType()`'s output — `granite_light` (not
> `granite`), `carpet_low`/`carpet_high`. A wrong key **fails silently** to the global default.
> "A wide scale sweep changes nothing" almost always means the layer isn't rendering at all
> (bad key, or same-as-base colour, or a decode fail) — stop tuning and instrument.

## Rotation

**`--evcc-floor-texture-map-rotate`** (global, degrees, `Floor Textures` editor group) spins
the whole tiled grid relative to the map — so directional materials (wood planks, tile grout,
marble veins) can be made to run the way they do in the actual home. `_resolveFloorRotation`
reads a per-type **`--evcc-floor-<type>-map-rotate`** override then the global, quantises and
wraps to `[-180, 180)`. Folded into the pattern matrix as `[s·cos, s·sin, -s·sin, s·cos]`
(uniform scale commutes with rotation); `0` = as-authored = the prior `[s,0,0,s]`. Map-only.

## Theme-editor tokens + the seed

Floor colours and per-layer opacities are exposed as editor controls in
`src/theme-tokens/floor-textures.js` (grouped under **Floor Textures — <Material>**). The
editor reads a token's current value **only from `resolvedTheme()`** (`src/state/theme.js`) —
there is no CSS-computed-defaults backfill. Floor tokens keep their defaults in the **render
registry** (baked as the `var(token, default)` fallback at paint time), which the editor never
sees — so without help, every floor swatch resolves to `""` and renders an empty, un-openable
control.

`resolvedTheme()`'s **"0b" seed block** fixes this: it iterates `FLOOR_TEXTURE_REGISTRY`
layers and seeds each `colorToken` ← `colorDefault` and `opacityToken` ← `opacityDefault`
(source `"default"`, **before** the active-theme/draft merges so a theme still wins), plus the
global map-rotate = `0`. Gated on `THEME_TOKEN_MAP` membership so computed `-eff` marble-vein
layers (oklch/calc defaults) are skipped. Net-zero on render — the seed equals the render's own
`var()` fallback.

> **Do NOT seed the per-material `-opacity-card` token.** It sits *above* the global
> `--evcc-floor-texture-opacity-card` master in the render's `var()` fallback chain, so seeding
> the per-material level would shadow (break) that global for anyone who set it. The layer
> color/opacity tokens have no such intermediate, so they're safe to seed.

## Material authoring — the rule, and the procedural generator

**A material reads on the map only if it has a bold, medium-frequency, high-contrast layer**
whose colour is **distinct from the base** — veins, planks + grooves, grout, mottle. A single
full-colour photo used as one dark luminance-mask layer collapses to a flat/black field at map
scale; **no scale value fixes that** (blowing up fine speckle just gives bigger blurry speckle).
The fix is always to author it as **multiple grayscale masks** — a broad base plus at least one
bold detail layer in a contrasting colour — then wire the layers in the registry (no render
code change) and tune the scale.

`scripts/gen_floor_masks.py` (numpy + PIL) generates the masks that are derived by rule rather
than hand-authored. Run `python scripts/gen_floor_masks.py` (or `--check` for stats, writes
nothing), then `npm run build:deploy` (bumps the asset hash → cache-bust). Generators:

- `gen_tile_base` — inverts the grout grid → white tile faces + dark grout channels.
- `gen_concrete_micro` — black field + sparse aggregate specks.
- `gen_split_from_photo` — frequency-splits the carpet/granite **photos** into a broad **base**
  (heavy blur, mostly-white) + a bold **detail** (band-pass + darkening gamma → mostly-black
  with bold weave/aggregate). This is how carpet_low/high and granite_light were rescued from
  the flat single-photo trap.
- `gen_wood_planks` — **procedural seamless hardwood** (replaces the old photographic swatch
  whose baked plank-ends tiled into glitchy "stops"). Staggered running-bond planks that
  **edge-wrap**: `plank_w` divides `SIZE`, there are exactly `SIZE/plank_l` planks per column
  (tones indexed mod that count), per-column vertical offsets wrap `mod plank_l`, and the grain
  is modulated with an integer number of sine cycles. Writes three layers — faces (mostly
  white), fine grain streaks, grooves + staggered joint ends. Plank width = `plank_w` (a
  generator param; a bigger value = wider planks / fewer columns, since the column count is
  `SIZE/plank_w`). The grain + seam layers use the **dark accent** colour so they define the
  planks on the opaque map floor (per the invisible-on-map rule above).

## Card vs map — two render models (why they differ)

They will never match pixel-for-pixel, by design:

| | Card (`floor-texture-surface.js`) | Map (`_drawVaFloorRender`) |
|---|---|---|
| Composite | CSS `mask-image` spans over the **card surface** | canvas `compositeFloorTexture` over the **base colour** |
| Tiling | one swatch, `mask-size: cover` | mask tiled at the per-material scale |
| Opacity | × the per-material `-opacity-card` (~0.85) | full strength (opaque floor) |
| Gaps show | card background | the base colour |

A card is a labelled tile with a texture *hint*; the map is a to-scale floor. This is why a
material can look bolder/softer on the card, and why same-as-base detail layers vanish on the
map but not the card.

## Tuning cheat-sheet

| Want | Lever |
|---|---|
| Bigger/smaller features on the map | `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE[<type>]` (or `--evcc-floor-<type>-map-scale`) |
| Rotate the grain/plank/grout direction | `--evcc-floor-texture-map-rotate` (editor) |
| Material colour(s) | the material's colour tokens (editor: Floor Textures — <Material>) |
| A detail layer stronger/fainter | that layer's `-opacity` token (editor) |
| Wider/narrower wood planks | `gen_wood_planks` `plank_w` param → regen → build |
| A flat material to actually read | re-author as multi-mask with a **distinct-colour** bold layer |

## See also

- [map-render-layers.md](map-render-layers.md) — the full map paint order + room-color cascade
- [theme-system.md](theme-system.md) — the theme editor + token groups
- [styles-system.md](styles-system.md) — where CSS lives (`src/styles/`)
- [../reference/THEME_TOKEN_MAP.md](../reference/THEME_TOKEN_MAP.md) — the generated token list
