# Floor-texture map view — render, tokens, masks, tuning

A third map render mode that paints each room with its floor **material** (wood, tile,
marble, concrete, granite, carpet…) as **one continuous floor**, not a per-room patchwork.
Toggle: the **▨** button next to the VA-render (**▦**) toggle, once the VA raster canvas is
active — `isFloorRenderActive()` is literally `isVaRenderActive() && useFloorTexture()`, and
both buttons are suppressed when the map is embedded in a card (`embeddedInCard()`). The ▨
choice persists per vacuum in `localStorage`. Works on any brand with a room raster (Eufy CV
+ the Roborock raw-map decode).

This doc is the render + material side. For where the floor layer sits in the map paint
order see [map-render-layers.md](map-render-layers.md); for the theme editor groups that
expose these tokens see [theme-system.md](theme-system.md).

## How it renders (mechanism A — raster clip)

`bindings/map.js` `_drawVaFloorRender` clones the `_drawVaRender` per-pixel `room_pixels`
decode, but each room's pixels are painted from its floor **type's composited material**
instead of a flat colour. Continuous by construction: the material is sampled in map space,
so adjacent same-type rooms line up. The output ImageData is cached and re-stamped on
zoom/select (see [Caches](#caches)).

Two things happen before any material is touched:

- **rid → material.** The raster's per-pixel `rid` is bridged to a managed room through the
  same device-authoritative `rd.room_names` (`{rid: name}`) map `_drawVaRender` uses for
  colours; the room's `floor_type` / `carpet_type` go through `resolveFloorType()`
  (`src/textures/floor-texture-resolver.js`). A type only enters `presentTypes` if it is
  **not** `"default"` **and** `getPrimaryTextureUrl(ft)` returns a URL — every other room
  falls back to the flat palette fill, in the same pass. So "no floor type set" and "type
  with no assets" degrade identically and silently to the flat render.
- **Supersample.** The ~360 px raster is drawn at `S = clamp(round(1200 / max(W,H)), 1, 4)`,
  so the canvas is `CW×CH = W·S × H·S` and the mask detail survives. Every cache key below
  is in CW×CH, not W×H.

Each material is built by `compositeFloorTexture` (`src/textures/floor-texture-compositor.js`
— pure, unit-tested) from the `FLOOR_TEXTURE_REGISTRY` entry — layers composited
**bottom → top over an opaque base**:

```
layerAlpha(texel) = (mask luminance / 255) × layerOpacity   // white reveals
out = layerColour × layerAlpha + out × (1 − layerAlpha)     // alpha stays 255
```

The compositor itself takes only `(width, height, baseColor, layers[{lum, color, opacity}])`
and knows nothing about tokens: the **caller** (`_ensureFloorTextures`) folds the resolved
colour's own alpha into `opacity` before handing the layer over, which is what keeps the
canvas tones matching the card's CSS. A layer is skipped outright when its `lum` array is
missing or shorter than `W×H`, or its effective opacity is `≤ 0`.

The buffer is **seeded with the base-role layer's colour** (`resolved[baseIdx].color`, else
layer 0), then every layer composites over it. Keep that seed in mind — it drives the single
biggest gotcha below.

## The layer + colour model — and the "invisible on the map" gotcha

A material is an ordered list of layers in `FLOOR_TEXTURE_REGISTRY` (`src/textures/floor-texture-registry.js`).
Each layer is `{ url (mask PNG), role, colorToken, colorDefault, opacityToken, opacityDefault }`
(veins add `blurToken`/`blurDefault`, which **only the card path reads** — the canvas
compositor has no blur). The mask is a grayscale PNG: **white reveals the layer colour, black
hides it.** Layer order is bottom → top; `role` is free-form (`base` / `grout` / `grain` /
`accent` / `micro` / `vein-major` / `vein-minor`) and only `"base"` is load-bearing — it
picks the seed colour.

Alongside `layers[]` each entry also carries `opacityDefault` (the material's card-opacity
fallback), `masks[]` and `baseTexture`. Those last two are **not** the map path: they feed
`getPrimaryTextureUrl(floorType)` (preference order `baseTexture` → first layer → first mask
→ `null`), which the SVG polygon renderer uses and which the raster path calls only as the
"does this type have assets" gate described above.

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
(`_floorColorProbe` — an `aria-hidden`, zero-size `<span>` appended to the canvas's parent, so
it inherits the theme vars and colour resolution never mutates the render canvas). It reads
the token off that probe, applies the value — or the registry default when the token is unset
— as a real `color` property, and reads the *computed* rgb back. That element context is the
whole point: `_parseCssColor` (a cached 1×1 scratch canvas using the browser's own `fillStyle`
parser) handles hex 3/6/8, `rgb()`, `hsl()`, `oklch()` and named colours, but it cannot
resolve a `var()` or `oklch(from var(…) …)` — the marble minor-vein default — with no element
to inherit from, and those were painting black. Last resort after both is grey
`[128,128,128,1]`. The colour's own alpha is folded into the layer opacity by the caller.

`_resolveFloorOpacity` is the asymmetric twin: it reads its token off the **host canvas**, not
the probe, and `parseFloat`s the raw text (clamped `[0,1]`, default `1` on a non-number). It
never evaluates CSS. That matters for exactly one material — see the marble-vein note under
[Theme-editor tokens](#theme-editor-tokens--the-seed).

## Mask decode — reliability

`_decodeMaskLum(url, W, H, scale, rotate)` loads a mask and returns a per-texel luminance
array. Two hard-won robustness features:

- **`createImageBitmap(fetch → blob)`**, not `HTMLImageElement.decode()`. Under a burst of
  ~15–20 large (2048²) decodes (every present material × its layers, kicked at once), plain
  `img.decode()` rejects a **random** couple per load with *"The source image cannot be
  decoded"* — the file is valid and served 200; the decoder (or the static server under the
  burst) just drops some. `createImageBitmap` is the purpose-built off-DOM decode and is far
  less flaky; `Image`+`decode` is kept only as a fallback. The fetch is
  `{cache: "force-cache"}` — the `?v=` bust below is what makes a changed mask reload, so the
  request itself should never re-hit the network.
- **Concurrency cap + retry.** `_enqueueMaskDecode` / `_pumpMaskDecodeQueue` cap concurrent
  decodes at **3** so the burst can't overwhelm the decoder/server; each decode **retries up
  to 4×**, sleeping `70 × attempt` ms between tries, so a transient loss recovers instead of
  caching a blank. The bitmap is `close()`d in a `finally` on every attempt.

The mask is drawn as a `createPattern(src, "repeat")` fill at **native** resolution — never
downscaled to the canvas size, which averaged the 1–3 px grain/seam detail away to flat — and
luminance is Rec. 601 (`0.299 R + 0.587 G + 0.114 B`).

`_decodeMaskLum` itself *throws* after the last attempt; the **caller** is what guarantees a
cache write. `_ensureFloorTextures` holds a `_floorMaskPending` set so only one decode per key
is ever in flight, and both its `.then` and `.catch` write a **zero-luminance sentinel** on
failure (that layer reveals nothing → base shows through) rather than leaving the key
uncached — otherwise it re-kicks every render (infinite loop). Its `.finally` schedules the
re-render that stamps the finished texture. So a broken mask degrades to flat base colour, it
doesn't hang.

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

A fourth, non-cache guard sits alongside them: `_floorMaskPending`, a `Set` of in-flight mask
keys, so a re-render during a decode doesn't enqueue the same job twice.

Note the outer draw path is deliberately **unguarded**: `_bindMapRender` re-runs
`_drawVaFloorRender` on every render in floor mode (unlike the flat raster, which short-circuits
on a `version|mode` draw key), because a decode completing or a theme recolour changes what
should be on the canvas without changing the version. `_vaFloorImageCache` is what makes that
cheap — an unchanged key just re-stamps the cached ImageData.

**Asset cache-bust:** every registry URL (layer, mask, and `baseTexture` alike) gets `?v=<ver>`
appended once at module load. `ver` is `__ASSET_VER__`, an esbuild `--define` constant injected
by `scripts/build-card.mjs` as `hashDir("custom_components/eufy_vacuum/textures")` — a SHA-1
over every file's *name and bytes*, truncated to 10 hex chars. Change any mask's bytes → new
hash → new URL → the browser/service-worker refetch; change nothing → same URL → assets stay
cached. Re-running the build after `gen_floor_masks.py` does this automatically. Unbundled runs
(`build:dev`, `watch`, `node --test`) have no define and fall back to the literal `dev`, so
every unbundled session shares one URL — regenerate a mask there and you must hard-reload.

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
> `--evcc-floor-texture-opacity-card` master in the render's `var()` fallback chain
> (`var(--evcc-floor-<type>-opacity-card, var(--evcc-floor-texture-opacity-card, <entry
> opacityDefault>))`, `renderers/floor-texture-surface.js`), so seeding the per-material level
> would shadow (break) that global for anyone who set it. The layer color/opacity tokens have
> no such intermediate, so they're safe to seed.

> ### ⚠ Marble's two vein layers do not honour their opacity sliders **on the map**
> Both vein layers point `opacityToken` at a computed `…-opacity-eff` token that nothing
> defines in CSS, with a `clamp(0,calc(var(--evcc-floor-marble-vein-opacity,0.5) + var(…-major/
> minor-opacity,…)),1)` **string** as `opacityDefault`. The card path bakes that straight into
> `var(token, default)` and CSS evaluates it. The map path does not: `_resolveFloorOpacity`
> reads an empty token, `parseFloat`s the `clamp(…)` literal, gets `NaN`, and returns its `1`
> fallback. So on the map both veins composite at **full strength**, and the three editor
> controls that feed the clamp — *Marble Vein Opacity (master)* and the two ± offsets — move
> the card swatch and nothing else. The colour side of the same pair works, because
> `_resolveFloorColor` hands its value to the browser to evaluate. The vein **blur** tokens are
> card-only by design (the canvas compositor has no blur), but this opacity gap is not by
> design — tracked as `FTX-VEIN-1` in `.claude/notes/synthesis/DOC-PASS-TRIAGE.md`.

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

## Three surfaces read the registry (why they differ)

`FLOOR_TEXTURE_REGISTRY` feeds three renderers, not two. Edit the registry and all three move
— but they will never match pixel-for-pixel, by design:

| | Room card (`_renderFloorTextureLayer`) | VA raster map (`_drawVaFloorRender`) | SVG polygon map (`_buildFloorTextureDefs`) |
|---|---|---|---|
| Reads | every layer | every layer | `getPrimaryTextureUrl(ft)` only |
| Composite | CSS `mask-image` spans over the **card surface** | canvas `compositeFloorTexture` over the **base colour** | one `<pattern>` `<image>` as the polygon `fill` |
| Tiling | one swatch, `mask-size: cover` | mask tiled at the per-material scale | 8×8 userSpaceOnUse tile |
| Opacity | × `--evcc-floor-<type>-opacity-card` › `--evcc-floor-texture-opacity-card` › the entry's own `opacityDefault` | full strength (opaque floor) | pattern as-is |
| Blur | per-layer, veins only | none | none |
| Gaps show | card background | the base colour | — |
| Gate | `roomFloorTextureEnabled()` | `isFloorRenderActive()` | `mapFloorTextureEnabled()` |

The entry-level `opacityDefault` is per material (tile/concrete/granite `1`, wood `0.99`,
marble/carpet `0.9`) — `0.85` is only the `default` entry's, i.e. what an unrecognised floor
type gets. A card is a labelled tile with a texture *hint*; the raster map is a to-scale floor.
This is why a material can look bolder/softer on the card, and why same-as-base detail layers
vanish on the map but not the card.

## Tuning cheat-sheet

| Want | Lever |
|---|---|
| Bigger/smaller features on the map | `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE[<type>]` (or `--evcc-floor-<type>-map-scale`) |
| Rotate the grain/plank/grout direction | `--evcc-floor-texture-map-rotate` (editor) |
| Material colour(s) | the material's colour tokens (editor: Floor Textures — <Material>) |
| A detail layer stronger/fainter | that layer's `-opacity` token (editor) — **except marble's veins, card-only today** |
| Wider/narrower wood planks | `gen_wood_planks` `plank_w` param → regen → build |
| A flat material to actually read | re-author as multi-mask with a **distinct-colour** bold layer |

## See also

- [map-render-layers.md](map-render-layers.md) — the full map paint order + room-color cascade
- [theme-system.md](theme-system.md) — the theme editor + token groups
- [styles-system.md](styles-system.md) — where CSS lives (`src/styles/`)
- [../reference/THEME_TOKEN_MAP.md](../reference/THEME_TOKEN_MAP.md) — the generated token list
