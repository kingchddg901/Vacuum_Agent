# Authoring a floor material

A **drop-in material** is a floor texture you make yourself and drop into your Home
Assistant config. The card treats it exactly like a shipped one: it appears as a chip in
room setup, gets its own group in the theme editor, and renders on the map, the room
cards and the theme preview.

Nothing is rebuilt and nothing is patched. You add a directory, restart Home Assistant,
and it is there.

*Using* floor types — picking one per room, what they change — is in the
[map configuration guide](../advanced/08-map-configuration.md). This page is about making
a new material.

## Two ways in

**[Material Author](https://kingchddg901.github.io/stone-author/app/stone-author.html) exports a complete pack.** Masks and `material.json`
together, in the layout below, ready to drop in. It runs in the browser — nothing to
install — and the source is at [kingchddg901/stone-author](https://github.com/kingchddg901/stone-author). That is the normal route now, and the rest of this page
is then reference rather than instructions — read it when you want to understand or
hand-edit what came out, not to produce one from nothing.

What its packs look like, measured from real exports:

| family | layers | suffixes |
|---|---|---|
| stone | 5 | `base` `major` `minor` `micro` `web` |
| wood | 6 | `ground` `early` `late` `heart` `mineral` `knot` |
| glass | 7 | `ground` + `cane-a` … `cane-f` (the cane count is capped at 6) |

All three are measured from real exports. Wood declares `early` primary, glass declares
`ground`, stone declares `base`.

A wood export's six layers are not six *working* layers: on the first one measured, only
`early` and `late` carried content. `ground` was a solid fill (legitimate — it is the
board colour at the bottom of the stack), but `heart` was **byte-identical to it** and
sat *above* both grain masks, so at luminance 255 and opacity 1 it was fully opaque and
painted over all the grain; `mineral` and `knot` were solid black and drew nothing. The
checker now warns on all of it — run it before you judge a material by eye.

**Writing one by hand** is still fully supported and nothing below assumes a generator.

Either way, check it before you restart Home Assistant:

```bash
python scripts/material_pack_contract.py config/eufy_vacuum/materials/<your-pack>
```

It runs the integration's own validator — the same code that decides at startup — so a
pack it accepts will load, and a pack it refuses prints the reason the log would have
given. It also warns about the two things that are legal but render badly.

## Where it goes

```
config/
  eufy_vacuum/
    materials/
      slate/
        material.json
        face.png  cleft.png  joint.png  cut-a.png  ...
```

The directory is created empty at startup, so it already exists. One subdirectory per
material, and the directory name may only contain letters, digits, underscore and hyphen
(max 64 characters).

**`catalog.json` appears beside your pack. Do not edit it.** It is generated: at every
Home Assistant start, `build_catalog()` walks every subdirectory here, validates each
one, and rewrites the file wholesale. Hand edits are lost on the next restart.

Three things follow from it being built only at startup:

- a newly added pack needs a **restart**, not a refresh;
- a pack **missing** from `catalog.json` was refused — the log says which rule;
- two packs claiming the same `id` means the second is **dropped with only a log line**
  (`id %r already used by another drop-in -- skipped`), so it simply never appears.

That location is deliberate: `config/` survives a HACS or Marketplace update. The
integration's own directory does **not** — it is replaced wholesale on every update, and
it is also the release payload, so anything put there is downloaded by every user of the
integration.

## The two halves

A material is **masks** (greyscale PNGs that say *where*) plus a **descriptor** (JSON that
says *what colour, how strong, in what order*). Colour never lives in the mask.

### What a mask actually is

Each mask is a greyscale image where the brightness of a pixel is how much of that
layer's colour shows through at that point:

```
layerAlpha(pixel) = (luminance / 255) × layerOpacity
```

So **white reveals, black hides, mid-grey blends halfway**. A joint mask is black almost
everywhere with thin white lines where the joints are. A broad mottle is a soft grey
cloud. Layers stack **bottom to top** in the order you list them, each one painting its
own colour through its own mask onto what is already there.

This is why the masks are greyscale and the colours are tokens: one set of masks can be
grey slate, autumn slate or something nobody has thought of yet, with no new files.

### Hard requirements, and why each exists

Every mask is checked against the file itself — not against what the descriptor claims —
and a material that fails any check is **refused whole** and logged.

| Requirement | Value | Why it is refused rather than coerced |
|---|---|---|
| Format | PNG | Read from the file's own header, no decoder needed |
| Canvas | exactly **2048 × 2048** | Feature scales are tuned to that canvas and the decode path never reads the bitmap's own width. Another size changes tile period and feature size together, so two layers from different canvases drift apart — **silently**, with no error and no obvious tell |
| Colour type | **0 (greyscale)** | The compositor reads luminance only. An RGB mask costs roughly 3× the bytes for no gain and nothing downstream would complain |
| Bit depth | **8** | — |
| Layers | 1 to 8 | Marble is the shipped maximum at 4; slate uses 7 |

Greyscale here means the PNG's own colour type, not "an RGB image that looks grey". If
your editor saved it as RGB it will be refused — export as 8-bit greyscale.

!!! tip "Masks must tile"
    They are tiled edge to edge across the whole map. If the left edge does not meet the
    right edge, you get a visible grid. Author them seamless, and check by tiling the
    image 2×2 in your editor before shipping it.

## The descriptor

`material.json`, beside the masks:

```json
{
  "schema": 1,
  "id": "slate",
  "name": "Slate",
  "layers": [
    { "suffix": "base",      "file": "face.png",      "color": "#555B60", "opacity": 0.95 },
    { "suffix": "cleft",     "file": "cleft.png",     "color": "#272C31", "opacity": 0.58, "primary": true },
    { "suffix": "highlight", "file": "highlight.png", "color": "#C8D0D7", "opacity": 0.55 },
    { "suffix": "joint",     "file": "joint.png",     "color": "#191C1F", "opacity": 0.90 }
  ]
}
```

### Top level

| Key | Required | Rule |
|---|---|---|
| `schema` | yes | Must be exactly `1` |
| `id` | yes | `^[a-z0-9][a-z0-9_-]{0,31}$` — see [The id is a namespace](#the-id-is-a-namespace) |
| `name` | no | Display name. Defaults to the id |
| `layers` | yes | 1–8 layer objects, bottom to top |
| `opacity` | no | 0–1, the material's overall card opacity. Defaults to `0.99` |
| `presets` | no | See [Presets](#presets) |
| `scale` | no | Feature scale on the map — how big the mask's detail is once tiled. Roughly 0.02–2; smaller is finer. Defaults to `0.05` |
| `family` | no | Descriptive metadata only — see [Known gaps](#known-gaps) |

### Each layer

| Key | Required | Rule |
|---|---|---|
| `suffix` | yes | `^[a-z][a-z0-9-]{0,23}$`, unique within the material. **This becomes the token name**, so choose it carefully |
| `color` | yes | `#rrggbb` or `#rrggbbaa` — the layer's default colour, overridable by theme token |
| `opacity` | yes | A number 0–1 |
| `file` | one of | A `.png` beside `material.json` |
| `from` | one of | `"<dir>/<file>.png"` — borrow a **shipped** mask instead of supplying your own |
| `primary` | no | At most one layer may set it. The primary layer is the single image the SVG polygon map draws, untinted. Defaults to the first layer |

`file` and `from` are alternatives: give one per layer.

### Borrowing a shipped mask

Rather than redrawing something that already exists, point `from` at a shipped mask:

```json
{ "suffix": "grout", "from": "tile/grout-mask.png", "color": "#2A2724", "opacity": 0.9 }
```

Available directories and files:

| Directory | Files |
|---|---|
| `carpet/` | `carpet-high-base-mask.png`, `carpet-high-detail-mask.png`, `carpet-low-base-mask.png`, `carpet-low-detail-mask.png` |
| `concrete/` | `concrete-broad-mask.png`, `concrete-micro-mask.png` |
| `granite/` | `granite-base-mask.png`, `granite-detail-mask.png` |
| `marble/` | `marble-base-mask.png`, `marble-micro-texture-mask.png`, `marble-vein-major.png`, `marble-vein-minor.png` |
| `tile/` | `grout-mask.png`, `pure-tile-grout.png`, `tile-mask.png` |
| `wood/` | `wood-directional-depth-mask.png`, `wood-grain-mask.png`, `wood-seam-mask.png` |

A borrowed layer still gets **your** colour, opacity and token — you are reusing the
geometry, not the look. Paths are resolved and contained: absolute paths, `..`,
backslashes, percent-encoded separators and symlinks are all refused.

## The id is a namespace

Token names are minted from the id by rule:

```
--evcc-floor-<id>-<suffix>            the layer's colour
--evcc-floor-<id>-<suffix>-opacity    the layer's opacity
```

So `id: "slate"` with `suffix: "cleft"` mints `--evcc-floor-slate-cleft` and
`--evcc-floor-slate-cleft-opacity`, which is what appears in the theme editor and what a
shared theme carries.

Because of that, an id is refused when it **is**, **is a prefix of**, or **is prefixed
by** a reserved floor-type name:

```
carpet-high  carpet-low  concrete  granite-light  marble  tile  wood  default
carpet_high_pile  carpet_low_pile  granite  hardwood  laminate
```

Equality would mint keys that already exist, which throws and takes the card down. The
prefix rules are subtler: a scoped theme import clears by raw prefix, so a material
called `carpet` would wipe `carpet-high`'s and `carpet-low`'s tokens, and a material
called `wood-dark` would be wiped by an import of `wood`.

Pick something distinctive. `slate`, `terrazzo`, `cork_dark` are all fine.

## Feature scale

`scale` sets how large the mask's detail is once it is tiled across the map. It is
the number that decides whether your stone reads as slabs or as gravel, and it is
independent of the mask itself — the same 2048² image at `0.05` and at `0.4` is
the same picture at two sizes.

Sensible range is about `0.02` to `2`; values outside that are clamped. The default
is `0.05`, which is what every shipped material except concrete and the carpets uses.

Precedence, in case you are fighting it:

1. A theme token `--evcc-floor-<id>-map-scale`, if set
2. Your `scale` in `material.json`
3. The global default

It affects the **map** only. Room cards and the theme preview stretch **every layer**
to fit the card (`mask-size: cover`, one element per layer) rather than tiling, so scale
does not apply there — judge it on the map.

Not to be confused with the single-mask surface: the **SVG map polygon** fill paints one
layer, untinted — the one marked `"primary": true`, else layer 0. That is the only place
a single mask stands in for the whole material.

**Leaving `scale` out is normal and correct.** An undeclared scale falls through to a
default that was tuned by eye, and a physically accurate number can easily look worse
than it. Set it only when you have looked at your material on the map and want it
different.

## Rotation

Rotation is **not** a property of the material, so it is not in this descriptor. It
is set **per room**, in the card: each room gets a rotation chip row beside its
material chips.

That is deliberate. The planks in a hallway and a living room routinely run different
ways, and a material-level angle could not express it — every room sharing the
material would turn together. The angle lives with the room because it describes the
house, not the stone.

The chips offer eighth turns — 0, 45, 90, 135, 180, 225, 270, 315 — because a diagonal
or herringbone floor is laid at 45 and the quarter turns had no chip for the one angle
it wants.

The stored value is a free angle in degrees regardless, and the backend schema is
unbounded, so a finer control can replace the chips later without a migration or a
schema change. A theme token `--evcc-floor-<id>-map-rotate` still applies to any room
that has not set its own.

Like scale, it affects the **map** only.

## Presets

A preset is a named set of token values shipped with the material — a starting point a
user can apply in one click:

```json
"presets": [
  {
    "id": "indian-autumn",
    "name": "Indian Autumn",
    "tokens": { "--evcc-floor-slate-cleft-opacity": 0.22 },
    "colors": { "--evcc-floor-slate-cut-a": "#A8641F" }
  }
]
```

A preset may only name tokens in **its own** `--evcc-floor-<id>-` namespace. Naming a
foreign token rejects the whole material rather than silently dropping the key: presets
are applied by writing into the theme, so a drop-in that could name foreign tokens could
recolour a shipped material.

## Installing it

1. Create `config/eufy_vacuum/materials/<yourname>/`.
2. Put `material.json` and the masks in it.
3. **Restart Home Assistant** — the catalogue is built at startup, so a reload is not
   enough.
4. Hard-refresh the dashboard (Ctrl+Shift+R).

Then, in the card:

- **Setup → rooms** — each room gains a material chip row. `Default` means "use this
  room's floor type's own look"; your material appears beside it.
- **Theme → Tokens** — your material gets its own facet and group, with a colour and an
  opacity control per layer, and a live preview card beside them.

Selecting a material is **appearance only**. It never changes how a room is cleaned —
that stays with the room's floor *type*, which is what carries the carpet water-off
behaviour. The two are deliberately separate fields so a material's name can never decide
whether a room gets mopped.

## When it does not appear

Every rejection is logged with the material's directory name and the reason, because a
material that half-loads renders as nothing and that reads like a theme problem rather
than a bad drop-in. Look in **Settings → System → Logs** for `user material <yourname>`.

Common ones, in the words the log uses:

| Log says | Means |
|---|---|
| `schema must be 1` | Missing or wrong `schema` key |
| `id must match ...` | Uppercase, too long, or starts with a hyphen |
| `"x" is a reserved floor-type name` | See [The id is a namespace](#the-id-is-a-namespace) |
| `is NNNxNNN, must be 2048x2048` | Wrong canvas |
| `has PNG colour type N, must be 0 (greyscale)` | Saved as RGB |
| `duplicate suffix "x"` | Two layers share a suffix |
| `N layers marked primary` | More than one `"primary": true` |
| `preset ... names tokens outside ...` | A preset reached outside its namespace |
| `id 'x' already used by another drop-in` | Two directories declare the same id |

A removed material degrades gracefully: rooms using it fall back to their floor type
rather than rendering flat, and the stored selection is left alone, so putting the
material back restores the look.

## Known gaps

Stated here rather than left to be discovered:

- **`family` does nothing.** It is accepted and stored as descriptive metadata, but no
  renderer reads it. Set it or omit it; nothing changes either way.
- **`scale` has no editor slider.** The descriptor value is honoured (see below), and
  a theme setting `--evcc-floor-<id>-map-scale` by hand overrides it, but that token is
  not minted as a control in the theme editor the way the per-layer colours are — so
  tuning tile size means editing the descriptor and restarting, rather than dragging a
  slider and watching it.
- **No per-material card-opacity token.** A material's own card opacity comes from the
  descriptor's `opacity`, deliberately: a per-material `-opacity-card` token would sit
  above the global master in the fallback chain and shadow it for anyone who set it.
  **Omitting `opacity` is fine** — it falls back to `0.99`. Until `78b4038b` it did not:
  an omitted value was written into the catalogue as an explicit `null`, `Number(null)`
  is `0` and `0` is finite, so it was read as a declared zero and every room card
  rendered untextured while the map looked right. If you are on an older build, declare
  `opacity` explicitly.

## Worked example

The slate material used while building this feature: seven layers, four of them cutouts
that exist purely so the parts can be coloured independently.

```json
{
  "schema": 1,
  "id": "slate",
  "name": "Slate",
  "opacity": 0.99,
  "layers": [
    { "suffix": "base",      "file": "face.png",      "color": "#555B60", "opacity": 0.95 },
    { "suffix": "cleft",     "file": "cleft.png",     "color": "#272C31", "opacity": 0.58, "primary": true },
    { "suffix": "cut-a",     "file": "cut-a.png",     "color": "#555B60", "opacity": 0.03 },
    { "suffix": "cut-b",     "file": "cut-b.png",     "color": "#555B60", "opacity": 0.03 },
    { "suffix": "cut-c",     "file": "cut-c.png",     "color": "#3F464C", "opacity": 0.10 },
    { "suffix": "highlight", "file": "highlight.png", "color": "#C8D0D7", "opacity": 0.55 },
    { "suffix": "joint",     "file": "joint.png",     "color": "#191C1F", "opacity": 0.90 }
  ],
  "presets": [
    {
      "id": "grey-slab",
      "name": "Basic grey, slab",
      "tokens": { "--evcc-floor-slate-joint-opacity": 0 },
      "colors": {}
    }
  ]
}
```

The three `cut-*` layers sit at very low opacity by default and do almost nothing in the
grey version. They are there so a preset can turn them up and recolour them — which is
how one set of masks becomes both plain grey slate and a mottled autumn one. **Cutout
layers are the main lever for a stone material**: the detail lives in which parts can be
coloured separately, not in how many masks there are.

A note on file size: masks are near-incompressible noise, so they are large. Slate's
seven layers total about 8.4 MB, and its `cleft.png` alone is 3.9 MB at a compression
ratio of barely 1.07:1 — PNG can do almost nothing with per-pixel variation. If size
matters, reduce the number of distinct grey levels or the spatial detail; the format is
not the lever.
