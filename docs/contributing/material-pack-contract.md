# Drop-in material pack — the generator contract

**Audience: a program writing `material.json`,** not a person authoring one by hand.
For the human guide — what the masks mean, how to paint them, how to borrow a shipped
one — see [material-authoring.md](material-authoring.md). This file is the machine
contract: every constraint, what happens when you break it, and the parts that are not
expressible in a schema.

## The authority is the validator, not this file

There is exactly one place the rules live:
`custom_components/eufy_vacuum/user_materials.py`. This document and the schema beside
it are both **derived from it**, and the deriving is mechanical:

```bash
python scripts/material_pack_contract.py --schema > docs/contributing/material-pack.schema.json
```

```bash
python scripts/material_pack_contract.py --verify-schema docs/contributing/material-pack.schema.json
```

[`material-pack.schema.json`](material-pack.schema.json) is **generated — do not
hand-edit**. The second command fails if it has drifted from the validator, which is
what stops the schema quietly becoming a lie as the validator moves.

**Check a pack against the real validator** — this runs the shipped
`validate_material()`, not a copy of it:

```bash
python scripts/material_pack_contract.py path/to/mypack
```

It needs no Home Assistant, no venv and no test image; `user_materials.py` is pure
stdlib and the checker imports it directly.

## Layout

```
<pack-dir>/
  material.json        the descriptor
  *.png                greyscale masks, 2048x2048, 8-bit, colour type 0
```

The directory name must match `^[\w-]{1,64}$`. It is **not** the id — it is only where
the files live. The id is declared inside the descriptor.

## Descriptor fields

`schema`, `id` and `layers` are required. Everything else is optional. Unknown
top-level keys are rejected by the schema (the validator itself ignores them, so the
schema is the stricter of the two here, deliberately).

| field | type | constraint | if wrong |
|---|---|---|---|
| `schema` | number | exactly `1` | **REFUSED** |
| `id` | string | `^[a-z0-9][a-z0-9_-]{0,31}$`, plus the reserved rule below | **REFUSED** |
| `name` | string | display name; defaults to `id` | coerced with `str()` |
| `family` | string | free text (`stone`, `wood`, `glass`) | never validated, never used for behaviour |
| `scale` | **number** | feature scale, must be `> 0` | **SILENTLY DROPPED** — see below |
| `opacity` | **number** | `0..1`, the material's own card opacity | **SILENTLY DROPPED** |
| `layers` | array | 1 to 8 entries | **REFUSED** |
| `presets` | array | see Presets | **REFUSED** on a stray token |

### Layer fields

| field | type | constraint | if wrong |
|---|---|---|---|
| `suffix` | string | `^[a-z][a-z0-9-]{0,23}$`, unique in the pack | **REFUSED** |
| `file` | string | `^[\w][\w.-]*\.png$`, in this pack's dir | **REFUSED** |
| `from` | string | `^[a-z_]+/[\w][\w.-]*\.png$`, a **shipped** mask | **REFUSED** |
| `color` | string | `#rrggbb` or `#rrggbbaa` | **REFUSED** |
| `opacity` | number | `0 <= x <= 1` | **REFUSED** |
| `primary` | boolean | at most **one** layer in the pack | **REFUSED** if two |

`file` and `from` are mutually exclusive — exactly one per layer. A `from` layer still
takes **your** colour, opacity and token; you are borrowing geometry, not appearance.

Paths are resolved and contained. Absolute paths, `..`, backslashes, percent-encoded
separators and symlinks are all refused.

## The three requirements a schema cannot express

The validator reads these out of each PNG's IHDR rather than believing the descriptor,
because all three fail **silently** at render if wrong:

| property | required | why |
|---|---|---|
| canvas | **2048 × 2048** | the feature scales are tuned to that canvas and the decode path never reads the bitmap's own width, so another size misaligns with no error |
| PNG colour type | **0** (greyscale) | the compositor reads luminance only |
| bit depth | **8** | |

**A generator that validates against the schema alone has checked half the contract.**
Run the directory check.

### Colour type 0 is the one every generator trips on

A generator does not emit greyscale by accident. A browser canvas — which is what
[Material Author](https://kingchddg901.github.io/stone-author/app/stone-author.html) renders through — produces **RGBA (colour type 6)** from
`toDataURL()`/`toBlob()` always, and other export paths land on **RGB (type 2)**.
Neither is accepted. Measured on real MA output: the four exported masks came out type
6, and six other MA-produced PNGs in that repo are type 2. **Zero were type 0.**

So the transcode is not an optimisation a generator can skip — it is a required export
step. It is also **lossless for a real mask**: if the mask is genuinely greyscale then
R == G == B at every pixel, and dropping to one channel discards nothing. Assert that
equality during the transcode rather than assuming it; a channel that disagrees means
the "mask" is carrying colour, which the compositor would have thrown away silently.

It pays for itself immediately. Transcoding MA's four masks to type 0 took them from
2.18 MB to 0.69 MB — 65–92% smaller, `base` alone 88,729 → 6,987 bytes. The requirement
is a compositor constraint *and* a transfer win.

## Two kinds of silence

This is the part a generator gets wrong, because neither produces an error.

### 1. `scale` and `opacity` are coerced, never refused

```python
"scale": float(desc["scale"]) if isinstance(desc.get("scale"), (int, float)) else None
```

A **string** `"scale": "0.05"` is not a number, so it becomes `null` and the material
takes the global default. Nothing is logged. If your serialiser stringifies numbers —
and several do — your carefully chosen feature scale silently does nothing. This is
exactly how `scale` shipped inert from `1a183bb2` until it was wired.

Emit them as JSON numbers. The checker warns when a declared `scale` or `opacity` fails
to survive validation.

**But prefer omitting both.** `scale` is RULED fine as it stands (2026-11-14): an
undeclared scale falls through to a default tuned by eye, and a physically accurate
number — which only a generator that knows the mask's real-world size can compute — can
easily look worse than it. Declare `scale` only to override a look you have judged on the
map. `opacity` likewise defaults to `0.99`.

### The third silence: absent and `null` are not the same thing

`build_catalog` writes an **explicit `null`** for a top-level `scale`/`opacity` the
descriptor omits (`user_materials.py:347-348`) — a present key with a null value, not an
absent key. That distinction was live for a while and purely destructive:

```js
Number(null) === 0     // and 0 IS finite, so it read as a DECLARED ZERO
0 ?? 0.99              // 0 -- ?? only catches null/undefined
```

Every layer span then multiplied to opacity 0 and **the room card rendered untextured
while the map looked correct**, because the map reads per-layer opacity and never the
material's. Fixed in `78b4038b`; a pack omitting `opacity` is safe from that build on. It
is recorded here because the shape recurs: a value that EXISTS reading as a declaration.

### 2. `scale` is clamped at render

`src/bindings/map.js` clamps to `0.02 .. 2`. A declared `9.0` is accepted by the
backend and then becomes `2` on screen. The checker warns; the integration does not.

Precedence, highest first:

1. theme token `--evcc-floor-<id>-map-scale`
2. the pack's own `scale`
3. `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE` (shipped materials only)
4. the global default, `0.05`

## The id is a namespace, and it is the one irreversible commitment

The id mints every token name by rule:

```
--evcc-floor-<id>-<suffix>            the layer's colour
--evcc-floor-<id>-<suffix>-opacity    the layer's opacity
```

It is also the registry key, and it is what a room's stored `floor_material` references.
So changing a published pack's id dangles every room that uses it and invalidates every
theme anyone exported — and the failure is **silent**, because the renderer's fallback
to `floor_type` is correct behaviour and looks exactly like "pack not installed".

**Treat the id as permanent from the first time the pack leaves the generator.**

An id is refused when it **is**, **is a prefix of**, or **is prefixed by** (hyphen-
separated) any reserved floor-type name:

```
carpet-high  carpet-low  concrete  granite-light  marble  tile  wood  default
carpet_high_pile  carpet_low_pile  granite  hardwood  laminate
```

> **Schema limit.** The schema carries these as a `not/enum`, which catches **equality
> only**. `wood-x` passes the schema and is then refused by the validator. The prefix
> rules are checkable only by running the directory check.

## Presets

A preset may name tokens **only** in its own `--evcc-floor-<id>-` namespace. One stray
key rejects the **whole pack**, not just the preset — silently dropping it would mean
the preset does not do what it says, and presets are applied by writing into the theme,
so a drop-in could otherwise recolour a shipped material.

```json
{ "id": "grey-slab", "name": "Grey Slab",
  "tokens": { "--evcc-floor-slate-joint-opacity": 0.4 } }
```

## The primary layer — the one that bites a glass material

The **SVG map polygon** surface paints **one** layer, **untinted**, as a single pattern
fill. (Not the room card — the card emits one tinted `<span>` per layer and never reads
the primary. `getPrimaryTextureUrl()` is called only from the map paths.):
`getPrimaryTextureUrl()`. Everything else about the material — every colour, every
opacity, every other layer — applies to the **map**, not to that surface.

Selection order: the layer marked `"primary": true`, else **layer 0**.

So a pack whose first layer is a flat field renders as a **grey wash** on the room
cards while looking perfect on the map. Shipped slate is the case: its `face.png` is a
uniform 235 — measured contrast **0.00** — which is why slate marks `cleft` primary
instead of letting layer 0 win.

**This is the trap for glass.** Glass is the simplest material to describe — few layers,
little structure, mostly transmission — and that is precisely what makes its natural
layer 0 a near-constant field. Mark the layer that carries structure (an edge, a bevel,
a caustic, a smear) as `"primary": true`, even if it is faint and even if it is not
what you think of as the material's "base".

The checker measures it:

```
WARN: primary layer 'pane' (defaulted to layer 0) has contrast 0.0, below 1.5 ...
```

The threshold is measured, not chosen — `--calibrate` prints the contrast of all 18
shipped masks. The two populations are far apart: the only flat field is `0.00`, and
the lowest structural mask is `2.85` (`concrete-broad-mask.png`). It is a **warning,
never a refusal**, because a genuinely flat material is a legitimate choice.

## Mask luminance IS coverage — and it is not the same across layers

```
layerAlpha(pixel) = (luminance / 255) × layerOpacity
```

So a mask's **mean luminance is how much of the room that layer covers**, and the three
roles in a material want opposite means. This is the part that decides whether a pack
looks like the material or like a smear, and it is invisible in the schema.

A **field** layer wants a HIGH mean — it paints nearly everywhere, modulated slightly.
A **detail** layer wants a LOW mean — it paints only where the feature is, and the black
is doing as much work as the white.

### This is a law, not a per-family quirk

Measured across **all 18 shipped masks**, every material is built the same way: **one
bright, near-flat field layer plus one or more dark, sparse detail layers.** Nothing
shipped sits in the middle.

| family | mask | mean | contrast | `<32` | role |
|---|---|---|---|---|---|
| tile | `grout-mask.png` | 248.6 | 16.9 | 0.0% | field |
| tile | `tile-mask.png` | 247.0 | 38.7 | 1.6% | field |
| wood | `wood-directional-depth-mask.png` | 234.7 | 11.1 | 0.0% | field |
| marble | `marble-base-mask.png` | 232.6 | 71.3 | 8.5% | field |
| carpet | `carpet-low-base-mask.png` | 186.0 | 11.0 | 0.0% | field |
| granite | `granite-base-mask.png` | 182.8 | 15.3 | 0.0% | field |
| carpet | `carpet-high-base-mask.png` | 178.1 | 12.5 | 0.0% | field |
| concrete | `concrete-broad-mask.png` | 91.0 | **2.8** | 0.0% | field |
| carpet | `carpet-low-detail-mask.png` | 33.3 | 55.6 | 76.4% | detail |
| carpet | `carpet-high-detail-mask.png` | 28.9 | 51.2 | 79.7% | detail |
| marble | `marble-vein-minor.png` | 29.1 | 81.1 | 88.6% | detail |
| granite | `granite-detail-mask.png` | 27.1 | 49.8 | 77.6% | detail |
| wood | `wood-seam-mask.png` | 25.3 | 32.3 | 70.7% | detail |
| concrete | `concrete-micro-mask.png` | 16.6 | 47.3 | 87.8% | detail |
| wood | `wood-grain-mask.png` | 9.4 | 18.8 | 86.7% | detail |
| tile | `pure-tile-grout.png` | 8.0 | 38.7 | 95.6% | detail |
| marble | `marble-vein-major.png` | 5.2 | 36.1 | 98.0% | detail |
| marble | `marble-micro-texture-mask.png` | 0.8 | 6.1 | 99.3% | detail |

Two consequences for a generator:

1. **The field layer is always the near-flat one, and it is usually layer 0.** That is
   the structural reason the flat-primary trap exists — it is not an edge case, it is
   where every material's layer 0 lives. `concrete-broad-mask.png` is the extreme at
   contrast **2.8**, and it is why the warning threshold has to sit below that.
2. **A mask with a mid-range mean and mid-range contrast is probably wrong.** Nothing
   shipped occupies that space. If MA emits a layer at mean ~128 it is likely a value
   map being used where a coverage map belongs — the same mistake that produces a
   0.00 base.

`scale` per family, from `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE`: marble, tile, wood and
granite `0.05`; carpet `0.09`; concrete `0.16`. Anything not listed falls through to the
global `0.05`.

## What a wood pack needs

Measured from the shipped `wood` material, which is the reference MA has to land near:

| role | suffix | mean | contrast | median | `<32` | `>223` | reads as |
|---|---|---|---|---|---|---|---|
| plank tone / depth | `base` | **234.7** | 11.1 | 234 | 0.0% | 81.8% | bright field, small per-plank variation |
| along-plank fibre | `grain` | **9.4** | 18.8 | 0 | 86.7% | 0.0% | mostly black, sparse bright lines |
| plank boundaries | `seam` | **25.3** | 32.3 | 22 | 70.7% | 1.7% | dark, with a few fully-bright grooves |

Three layers, and the shipped values to start from:

| suffix | colour | opacity | borrowable shipped mask |
|---|---|---|---|
| `base` | `#7A4010cf` | 0.39 | `wood/wood-directional-depth-mask.png` |
| `grain` | `#3a2409` | 0.76 | `wood/wood-grain-mask.png` |
| `seam` | `#3a2409` | 0.70 | `wood/wood-seam-mask.png` |

`scale`: **0.05** — wood's entry in `FLOOR_TEXTURE_MASK_SCALE_BY_TYPE`.

Note the alpha on the base colour (`cf`): `#rrggbbaa` is accepted and shipped wood uses
it. Note also that shipped wood points `grain` and `seam` at the **same**
`--evcc-floor-wood-accent` token, because those literals are hand-authored. A drop-in
cannot do that and does not want to — tokens are minted per suffix, so **a drop-in gets
finer control than shipped wood has**, one colour and one opacity per layer.

### The precedent that already works

`bamboo` — a wood-family drop-in running on the live box — borrows the shipped depth and
seam masks and supplies only its own grain. Its grain measures mean **36.4**, contrast
39.8, 48.3% below 32: nearly 4× the shipped grain's mean and visibly denser. It renders
correctly. So the means above are a **centre, not a gate** — the contract does not police
them and there is real latitude.

### What this means for the primary pick

Wood's `base` is a bright near-flat field at contrast **11.1**. It clears the
flat-primary warning, but only by character, not by much — and it is the same *kind* of
mask as the ones that measure 0.00. If MA's wood base comes out flatter than the shipped
one (a single plank tone rather than per-plank variation), it will trip the warning, and
the fix is to mark `seam` or `grain` primary rather than to add noise to the base.

**How the masks are drawn is an art choice.** The numbers above are targets to land
near, not a recipe — the contract constrains the format and the semantics, never the
picture.

## What a glass pack needs — it already fits

**Glass fits today, at 7 layers, with no code change on either side.** That is measured
at both ends, and it retires the 12-colour framing this section was first written around.

**The name is free.** `glass` is not in `RESERVED_NAMES` — not as a registry key, not as
a persisted `floor_type`. A pack may be called exactly `glass`, with no prefix and no
suffix. (`glass-float` in the worked example below is a choice, not a requirement.)

**There is no 12-colour glass to carry.** Material Author clamps the cane count to
**6** — `CN: Math.max(2, Math.min(6, Math.round(GLASS.cordN)))` (`stone-author.html:9785`),
with the slider itself `min="2" max="6"` against exactly six colour tokens `glassA`–`glassF`.
Raising it means minting tokens, not changing a number.

Six canes plus the ground is **7 layers**, and `MAX_LAYERS` is **8** — one spare. Verified
by running the shipped validator over a real 7-layer pack built to that shape:

```
ACCEPTED glass-cane   id='glass-cane'  layers=7  presets=0
```

So the 8-layer ceiling, sized for stone (*"marble is the shipped maximum at 4; slate needs
7"*), is **more headroom than the generator can currently use.** Eight pure disjoint
colours is not a fallback for glass; it is room to spare.

### The one thing that does bite: glass defaults to the wrong primary

A glass pack's natural layer 0 is the ground — the body of the glass — and the **SVG map
polygon** surface paints the primary layer **untinted, as a single pattern fill**. Built as the generator
would emit it, the ground lands at mean 234.0, contrast 1.4, and the checker fires:

```
WARN: primary layer 'ground' (defaulted to layer 0) has contrast 1.4, below 1.5
```

**But do not trust that warning for glass.** It measures variance, and a glass ground's
problem is *brightness* — which the threshold does not look at. Ablated, by widening the
ground's dither while leaving it just as flat and just as white:

| ground | mean | contrast | checker |
|---|---|---|---|
| as emitted | 234.0 | 1.4 | **WARN** |
| dithered over 16 levels | 237.5 | 4.6 | passes — "OK" |
| dithered over 40 levels | 246.9 | 8.5 | passes — "OK" |

All three paint the same near-white wash on the card. The warning catching the first one
is a coincidence of where that ground's dither landed, **not a guard**.

**So for glass, declare `"primary": true` explicitly. Never let it default.** Two
declarations were tested and both clear the gate:

| declared primary | contrast | note |
|---|---|---|
| a single cane | 97.5 | one hard-edged sixth of the field |
| a `facets` layer (cane boundaries) | 44.7 | the 8th slot; draws cane *structure* |

Clearing the gate is not the same as reading as glass. **Which one looks right is an art
call, not a check** — the contract has no opinion, and the `facets` option is offered
because the spare layer exists, not because it is recommended.

### If the ceiling ever moves: why an index map does not work — twice over

> **This subsection is contingency, not a plan.** With the generator clamped at 6 and VA
> accepting 8, nothing today needs it. It is kept because the measurement is sound and
> because the arithmetic decides the question the moment anyone mints a 7th colour token
> — **not** as work to be priced or started. On today's code there is no 12-colour glass
> for an index mode to carry.


Encoding a palette index in the mask's greyscale value is the obvious way past the
ceiling, and it fails for two independent reasons. Both are mechanical, neither is taste.

**1. Both renderers read that value as coverage.** This is the law from the section
above, and it is not negotiable per-layer:

- canvas/map path — `layerAlpha = (luminance / 255) × layerOpacity`
- card/CSS path — `mask-mode: luminance` over a single `background-color`

So an index map handed to today's renderer paints **a 12-step opacity ramp of one
colour**, not 12 colours. Index 0 is alpha 0, i.e. invisible. The output is not a
degraded picture; the number means something else entirely.

**2. The sampler destroys the index before anything reads it.** `_decodeMaskLum` fills at
native resolution through `createPattern(..., "repeat")` and then minifies with the
pattern matrix by `1/scale` — **20× at the shipped `scale: 0.05`**. Interpolation averages
neighbouring source texels, and the average of two palette indices is a third index,
which is a *different colour*.

Measured in headless Chromium 148.0.7778.96 against that exact code path, 1024×1024
canvas, palette of 12 levels spread across 0..255 (spacing 23 — the most
resampling-tolerant encoding available, so this is the best case, not a worst case):

| layout | `scale` | smoothing | texels still on a palette index | distinct values |
|---|---|---|---|---|
| concentric rings | 0.05 *(shipped)* | on *(default)* | **5.10%** | 256 |
| concentric rings | 0.16 *(loosest shipped)* | on | 58.93% | 256 |
| vertical stripes | 0.05 *(shipped)* | on | 48.01% | 256 |
| vertical stripes | 0.16 | on | 72.34% | 256 |
| **either** | **0.05–1.0** | **off** | **100.00%** | **12** |

Concentric rings are the honest layout for glass, because that is what a cane looks like
in cross-section — curved boundaries, not axis-aligned ones. At the shipped scale
**94.9% of its texels land between two palette entries.** Stripes do better only because
their edges are vertical and sometimes fall on a sample.

### The fix is one line, and it is still his call

Smoothing off — nearest-neighbour point sampling — reads **100.00% intact with exactly 12
distinct values at every scale tested, the shipped 0.05 included.** So the idea is
mechanically sound. What it needs:

1. a per-layer mode saying *this mask is an index, not coverage*, plus the palette;
2. that mode to point-sample (`imageSmoothingEnabled = false`).

**Point 2 must be per-layer, never global.** Smoothing is what averages the 1–3px grain
and seam detail in every existing 2048² mask down to map scale; the native-resolution
fill exists to protect exactly that. Flipping it off globally would alias every shipped
material.

And one constraint that does not go away: **the CSS card path cannot do a palette lookup
at all.** It emits one `<span>` per layer with one `background-color` and
`mask-mode: luminance`; CSS has no way to select "pixels whose value is index 7". An
index-mode layer is therefore **canvas-only**, so it would render on the map and not in
the SVG map polygon surface. That fork is the part worth knowing before an
exporter commits to the encoding.

### The argument *for* the index approach

It is not merely more compact. `_decodeMaskLum` carries a 4-attempt retry loop whose
comment records why: `decode()` *"rejects intermittently when a burst of large (2048²)
masks decode at once"*. Slate already pushes that at 7 layers. Twelve masks would make a
known-flaky burst worse, while one index map is **one** decode. For glass specifically,
indexing is the better engineering, not just the smaller download.

**NOT BUILT, AND NOT NEEDED.** Glass fits in 7 of 8 layers today. A layer `mode` and a
`palette` would be new persisted keys in `material.json`, which is a stop-for-approval
change, and a new per-layer field has to cross both
validator dicts, both rebuild dicts in `user-materials.js`, the token minting, both
render paths, and the esbuild bundle boundary. Written down, not started.

## Worked example — glass

```json
{
  "schema": 1,
  "id": "glass-float",
  "name": "Float Glass",
  "family": "glass",
  "scale": 0.35,
  "opacity": 0.55,
  "layers": [
    { "suffix": "pane",  "file": "pane.png",  "color": "#AEC6CF", "opacity": 0.30 },
    { "suffix": "bevel", "file": "bevel.png", "color": "#E8F4F8", "opacity": 0.65,
      "primary": true },
    { "suffix": "smear", "file": "smear.png", "color": "#FFFFFF", "opacity": 0.18 }
  ]
}
```

Note `bevel` as primary rather than `pane`, and `scale` well above the `0.05` default —
glass reads as large panes, not as gravel.

## Checklist for the generator

1. **Omit `scale` and `opacity`** unless you are overriding a look you have judged on
   the map. If you do emit them, emit **JSON numbers**, never strings.
2. Keep any declared `scale` inside `0.02 .. 2` or accept the clamp.
3. Pick the id **once**, and never change it for a published pack.
4. Mark a **structural** layer `"primary": true` — do not rely on layer 0 — **unless
   the material is a partition**, where no single mask carries the structure. Glass is
   the measured case: six binary canes at 15.10–17.86% coverage summing to exactly
   100.00% with 0.00% bare, so any one cane is an arbitrary sixth and their union is the
   whole sheet. There `ground` is the honest primary and a low contrast figure is the
   checker reporting that truthfully, not a defect to design around.
5. Write every mask at **2048 × 2048, 8-bit, greyscale (colour type 0)**.
6. Keep every preset token inside `--evcc-floor-<id>-`.
7. Run `python scripts/material_pack_contract.py <dir>` and require exit 0 **with no
   WARN lines** before calling an export successful.
