# Floor Texture Thermal Shimmer — make the material behave, not animate

**Status:** design **PARKED 2026-09-14**. Written up because the feasibility is settled,
**not because it is scheduled.** Nothing here is a commitment to build it; it is here so the
mechanism and the three traps are not re-derived from scratch later.

> **Scope note.** This is a delta on the floor-texture layer stack described in
> [render-harness](../../frontend/render-harness.md) and the registry in
> `src/textures/floor-texture-registry.js`. Every seam it needs already exists — no new
> renderer, no new service, no new token type.

---

## 1. The idea

Black One's marble reads as **scorched stone with partially molten inclusions**: a dark
matrix that has stayed solid, threaded by an irregular orange network that looks like
lower-melting-point material gone plastic inside fractures and grain boundaries.

The observation this design turns on: that read comes from the *irregularity*. The veins do
not glow evenly. Some of the network looks molten, some merely oxidised, some like a
heat-affected seam. It implies a thermal history the card never states.

**Extend that from appearance to behaviour.** Drift the two vein layers' opacity by 1–2% on
slow, mutually prime periods, so different parts of the fracture network appear to heat and
cool independently. Not a pulse — a shimmer.

**Why it would read as material rather than as animation:** the masks are fixed PNGs. The
fracture geometry cannot move. Only the apparent energy in the inclusions changes, so the
stone stays solid and the *inclusions* look unstable. That is the whole effect, and it is
also why the amplitude has to stay tiny. At 10–20% it becomes a glowing-lava GIF. At 1–2%,
with periods that do not divide into each other (7.3s against 11.1s beats at ~81s), it does
not resolve as a loop at all.

This extends the theme language from *what does this material look like* to *how does this
material behave over time*, which the card already does once — see the status pulse in §2.

---

## 2. What already supports it

| Fact | Where |
|---|---|
| The veins are genuinely separate compositing layers — marble is four spans (`base`, `micro`, `vein-major`, `vein-minor`), each with its own `data-role` | marble's `layers[]` in `src/textures/floor-texture-registry.js`, emitted by `renderers/floor-texture-surface.js::_renderFloorTextureLayer` |
| So each is independently targetable and can carry its own `animation-duration` | `.evcc-ftx-layer[data-role="vein-major"]` |
| Theme-defined motion is an established pattern, not a new concept | `src/styles/rooms.js` — `animation: evccPulse var(--evcc-status-pulse-duration, 1.6s) infinite` |
| `prefers-reduced-motion` is already handled in three stylesheets | `styles/learning.js`, `styles/mobile.js`, `styles/rooms.js` |
| Visual baselines are safe — the harness freezes animation | `harness/mount-entry.js` `FREEZE_STYLE` sets `animation-duration: 0s !important` under `freeze: true`, which every preview and visual spec passes |

Because freeze collapses an animation to its end state, a frozen capture lands on the
**100% keyframe** every time. Author the keyframes so 0% and 100% hold the same value and the
baseline is deterministic by construction.

---

## 3. TRAP: the obvious implementation does not work

**A CSS custom property cannot be animated in keyframes.**

An unregistered custom property is not interpolatable. A keyframe on
`--evcc-floor-marble-vein-major-opacity` flips **discretely at 50%**, so the result is a
two-state flicker, not a drift. Registering it
(`@property { syntax: "<number>"; inherits: true; initial-value: … }`) would make it
interpolate, but that adds a registration surface for every token involved and couples the
theme catalog to a second declaration mechanism.

**Do not animate the token. Animate a real CSS property and let tokens parameterize it** —
exactly what the status pulse does. The token supplies the duration; the keyframes are fixed
in the stylesheet.

### 3a. TRAP: the layer already owns `opacity`

`.evcc-ftx-layer` sets:

```css
opacity: calc(
  var(--evcc-floor-textures-card-enabled, 1) *
  var(--floor-opacity-card, 0.85) *
  var(--layer-opacity, 1)
);
```

An `animation` on `opacity` **overrides that normal declaration outright** for the duration
of the animation. Naively adding one snaps every vein to full strength the instant it starts.
The keyframes have to reproduce the product and scale it:

```css
@keyframes evccFtxThermalMajor {
  0%, 100% { opacity: calc(var(--evcc-floor-textures-card-enabled,1) * var(--floor-opacity-card,0.85) * var(--layer-opacity,1) * 0.99); }
  50%      { opacity: calc(var(--evcc-floor-textures-card-enabled,1) * var(--floor-opacity-card,0.85) * var(--layer-opacity,1) * 1.01); }
}
```

Verbose, but it keeps the whole token chain intact — including the card-textures kill switch,
which must still be able to turn the layer off.

### 3b. TRAP: opacity is cheap, blur is not

Opacity animates on the compositor. `filter: blur()` forces a **repaint every frame**, and
these are full-bleed masked layers on *every room card* — five to twelve on screen at once,
two vein layers each. An always-on blur oscillation is a permanent repaint load for an effect
nobody consciously registers.

**Ship opacity drift only.** If the blur breathing is wanted, confine it to the theme-preview
swatch (`renderers/theme-preview.js::_renderFloorPreviewCard`), where exactly one card renders
and the user is deliberately looking at the material.

---

## 4. Why it must animate the SPAN, not the token — a second, independent reason

The map renderer composites its own SVG version of each floor type, and reads the opacity
**once** through a hidden probe: `bindings/map.js::_resolveFloorOpacity` applies the token's
value to a real CSS property and reads back the computed result. It samples. It cannot follow
an animation.

Animate the span's `opacity` and the map is simply unaffected — it keeps using the base value.
Card shimmers, map stays still. Animate the *token* and the map silently disagrees with the
card about what the material looks like.

That disagreement has happened before, and the scar is worth reading: **FTX-VEIN-1**. Marble's
two vein layers point at computed `--…-opacity-eff` tokens that nothing defines in CSS, whose
registry default is a `clamp(0, calc(var(--evcc-floor-marble-vein-opacity,0.5) + …), 1)`
**string**. The map's `parseFloat("clamp(...)")` was `NaN`, fell back to `1`, and composited
both veins at full strength while the card rendered them at 0.5/0.38 — three editor sliders
moved the card swatch and nothing else. The probe exists because of that bug.

---

## 5. What it would take

| Piece | Where | Note |
|---|---|---|
| Two keyframe blocks | `src/styles/floor-texture-styles.js` | major and minor, each reproducing the opacity product (§3a) |
| Two `animation` declarations | same | on `[data-role="vein-major"]` / `[data-role="vein-minor"]` |
| Two period tokens | `src/theme-tokens/floor-textures.js` | kind `duration`. **Default `0s` = off**, so every existing theme is unchanged and this is opt-in per theme |
| An amplitude token, or a fixed 1% | — | open, see §6 |
| A `prefers-reduced-motion` arm | same stylesheet | non-optional: a shimmering floor under the whole UI is the case that media query exists for |
| A gate | `harness/tests/gallery-completeness.spec.mjs`, beside `[FLOOR-1]` | assert the animation is absent at the default period and present when one is set — otherwise this is a feature whose off-switch nothing checks |

Honest size: four layers, two surfaces (card and map), a reduced-motion path and an opt-in
default. It looks like three lines of CSS and is not.

---

## 6. Open — decide before building, not during

1. **Amplitude: token or constant?** A token is one more thing to tune and to get wrong (the
   whole effect dies above ~2%). A fixed 1% cannot be ruined by a submitter. Leaning constant,
   with the *period* tokenized — the period is what makes it feel bespoke.
2. **Per-material or marble-only?** The read is specific to marble's fracture network. Carpet
   weave and tile grout shimmering would be nonsense. Per-material tokens keep the shape
   generic and let only marble ship a non-zero default; marble-only grows a special case in
   the registry. Leaning per-material, zero everywhere.
3. **Does the map need a matching treatment?** Card shimmers, map does not (§4). Acceptable, or
   does the map need a static "hot" bias so the two surfaces do not visibly disagree?
4. **What does the theme editor show?** A period slider with no live preview is a control the
   author cannot evaluate. The floor-materials board (`harness/fixtures/gallery.js`) is frozen
   for capture, so it cannot demonstrate this at all.

---

## 7. Why it is parked

The feasibility is not the risk — that is settled above. The risk is that the effect is
**subliminal by design**: at the amplitude where it works, nobody can tell you whether it is
on. That makes it very hard to know when it is finished, and close to impossible to review.
That is the sort of thing to start rested and deliberately, not at the end of a session.
