# Floor-texture map view — render + material authoring

A third map render mode that paints each room with its floor **material** — one
continuous floor, not a per-room patchwork. Toggle: the **▨** button next to the
VA-render (**▦**) toggle, once the VA raster canvas is active. Works on any brand with
a room raster (Eufy CV + the Roborock raw-map decode).

## How it renders (mechanism A — raster clip)

`bindings/map.js` `_drawVaFloorRender` clones the `_drawVaRender` per-pixel `room_pixels`
decode, but each room's pixels are painted from its floor **type's composited material**
instead of a flat colour. Continuous by construction: the material is sampled in map
space, so adjacent same-type rooms line up.

Each material is built by `compositeFloorTexture` (pure, unit-tested) from the
`FLOOR_TEXTURE_REGISTRY` entry — layers composited **bottom → top over an opaque base**:

```
layerAlpha(texel) = (mask luminance / 255) × layerOpacity × colorAlpha   // white reveals
out = layerColour × layerAlpha + out × (1 − layerAlpha)                  // opaque result
```

- **Masks** are decoded at **native resolution** (a repeat-pattern, NOT downscaled to map
  size — downscaling averages fine detail to mush) and then **scaled per material** (below).
- **Colours** resolve like the card's CSS — applied on the canvas + read computed — so
  `var()`, `oklch()`, and 8-digit hex all become real rgb (a plain hex parser can't).

## Per-material feature scale

`FLOOR_TEXTURE_MASK_SCALE_BY_TYPE` in `bindings/map.js` scales each material's mask pattern
down so its features are the right apparent size on the map (1.0 = native = "zoomed in";
lower = finer/denser). It's a **map-only** concept (the card shows the whole mask, no
scale), so it's a baked constant, not a theme token.

| Key | Scale | Notes |
|---|---|---|
| `marble` | 0.05 | broad veins ✓ |
| `wood` | 0.05 | planks + grain ✓ |
| `tile` | 0.05 | grid + fleck ✓ (fleck noise is tunable/intentional) |
| `concrete` | 0.7 | broad mottle + micro ✓ (two-layer — reads) |
| `granite_light` | 0.05 | ⏸ parked — single fine speckle, needs a bold mask |
| `carpet_low` / `carpet_high` | 0.65 | ⏸ parked — needs a split (multi-mask) re-author |

> **Gotcha:** the keys MUST match `resolveFloorType()`'s output. Granite resolves to
> `granite_light` (not `granite`); carpet to `carpet_low`/`carpet_high`. A wrong key
> **fails silently** to the global default — so if a material "won't respond to scale,"
> check the key first.

## The material-authoring rule (why some materials work and some don't)

**A material reads on the map only if it has a BOLD, medium-frequency, high-contrast
layer** — something the eye can catch from across a room:

- ✅ **Works** — authored as several **grayscale masks**, each its own layer with a
  contrasting colour token: marble (base + micro + two vein tiers), wood (depth + grain +
  seams), tile (face + grout + line), concrete (broad + micro). The bold layer (veins,
  planks, grout, mottle) carries it.
- ❌ **Fails (black/flat)** — authored as a **single full-colour photo** used as one
  luminance-mask layer × a near-black colour: `carpet_low/high`, `granite_light`
  (`texture-floor-carpet-*.png`, ~6.6 MB). Luminance-of-a-dark-photo × dark colour = a
  dark, low-contrast field → it collapses to black at map scale, and **no scale value can
  fix it** (blowing up fine speckle just gives bigger blurry speckle).

**Fix a failing material by re-authoring it as multi-mask**, the way marble is — a broad
base plus at least one bold detail layer. The render composites as many layers as you give
it; it's purely a texture-authoring task (drop grayscale PNGs in a subdir, wire the layers
in the registry entry — no render code change), then tune its scale down like the others.

### Suggested splits

Author these as grayscale masks (white reveals the layer colour). Either **derive from the
current full-colour file** — heavily blur it for the base (low frequency), high-pass it
(photo − blur) + boost contrast for the bold layer (medium frequency), matching the
high-pass radius to the feature size you want visible across a room — or **generate fresh**.

**Carpet (low & high pile)** — 2–3 layers:
1. `base` — broad low-frequency tone (overall carpet colour field, gentle mottle). Fills flat.
2. `pile` **(bold)** — medium-frequency pile clumps / directional weave, high contrast, at a
   few-cm scale so it reads across a room. Contrasting tone (lighter sheen for high-pile,
   tighter weave lines for low-pile). *This is the layer that makes it read.*
3. `fleck` *(optional, fine, low opacity)* — fine fibre speckle for close-up richness; mostly
   vanishes at map scale, so keep subtle.
   Low vs high pile: high-pile = larger, softer clumps + more sheen contrast; low-pile =
   tighter weave grid.

**Granite (light)** — 2–3 layers:
1. `base` — broad stone tone.
2. `aggregate` **(bold)** — the *larger* aggregate grains plus faint cracks/veins (marble-lite),
   high contrast, medium frequency. *The bold layer.* Granite's trap is that real granite is
   mostly uniform fine speckle with no bold structure — so lean on the biggest grains + a hint
   of veining to give the eye something to catch.
3. `speckle` *(optional, fine, subtle)* — the fine mineral speckle.

Once a re-authored material has a real bold layer, drop its per-material scale back down
near the others (~0.05–0.1) rather than the large "parked" values.
