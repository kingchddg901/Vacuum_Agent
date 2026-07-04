# Animal Companion authoring (maintainer path)

!!! note "Two paths — pick the right one"
    **Want to *share* an animal? This isn't the page (and that's the good news).**
    Community companions are **declarative data**, not code: you write a JSON
    **descriptor**, and the intake sanitises the SVG and *generates* the runtime
    module for you — no JavaScript, no `register()`, nothing that can run on
    someone else's dashboard. → **[Authoring an animal](animal-authoring.md)** is
    the guide you want, and the only route the public gallery accepts.

    **This page is the maintainer / runtime path.** It covers adding an
    `animals/<id>.js` module *directly* — `AnimalSVG.register(...)`,
    framework-level behaviour, and procedural `type: 'custom'` renderers. Those
    ship **executable code** into the bundle, so they're reviewed *as code*, by
    maintainers — never accepted through the gallery intake.

    The **craft standards** below (what a *good* mascot looks like) apply to
    **both** paths: a descriptor animal is held to exactly the same bar.

Honest disclaimer up front: the bundled animals (cat, dog, raccoon, parrot,
snake, plus the Mittens memorial) started as **placeholder quality**. They were
built to validate the framework — to prove the parts pipeline, the pose system,
the registration model, and the custom-type escape hatch all work end-to-end.
Polish was not the goal.

If you have any visual-design instinct at all, you can probably make a
better one. This guide describes what "better" means here, so you have
something to aim at.

The technical contract (definition shape, coordinate space, allowed poses,
battery-state hook, theme tokens) lives in the integration's
[animal-svg dev doc](../dev/frontend/animal-svg.md). This file is about *making them
look good* (any animal) and the maintainer **runtime** path (raw-JS animals).

## What "good" means here

A good mascot has these properties. The bundled placeholders mostly don't.
This is craft guidance — it applies whether you're submitting a
[descriptor](animal-authoring.md) or a maintainer adding a runtime module.

### 1. Anatomically coherent across all six poses

The same animal should remain recognisably the same animal whether it's
curled, walking, alerting, or warning. Test it: render all six poses side
by side. Does the silhouette tell you "this is a cat" in every one? If two
poses look like different animals, the underlying anatomy isn't holding up.

Specifically watch for:

- **Leg position credibility.** Curled legs tucked under the body should
  match the body's compression. Walking legs should be roughly under the
  hips at all phases. Standing legs shouldn't disappear into the body.
- **Head-to-body proportion.** When the head rotates in curled or alert
  pose, it should still look attached. Watch the neck junction; placeholder
  animals often have visible seams.
- **Tail believability.** Tails in curled pose wrap or tuck; in alert pose
  they're up or flicked; in walking they sway. A stiff straight tail in
  all poses reads as unfinished.

### 2. Pose-distinguishing silhouette

The six poses should be visually distinct enough to read at the map's
actual render size: **64 × 44 pixels** by default (scaled by user setting).
That's tiny. Detail finer than ~2 pixels is wasted.

Squint test: at 64×44, can you tell `alert` from `standing`? `walking` from
`animating`? If not, the difference is in detail your user will never see.
The pose needs to be expressed in silhouette — posture, limb angles, tail
direction — not in face detail or texture.

The bundled cat does this poorly: `alert` and `standing` look nearly
identical at small sizes. A new cat that fixes this is a real upgrade.

### 3. Consistent line and stroke weight

Inside one animal, stroke widths should follow a system. The bundled
animals mix 13px and 8px and 4px strokes somewhat arbitrarily, which reads
as draft work. Pick a stroke hierarchy (e.g. body outlines = 4px, leg
strokes = 13px, whisker lines = 1.5px) and stick to it across every part.
Then carry that hierarchy across every pose.

This is the single biggest "looks finished vs. doesn't" lever.

### 4. Intentional color palette

The `colors` block isn't just "values that work" — it's an opportunity for
character. The bundled cat is a flat dark-grey with green eyes; that's
intentional but minimal. A more characterful palette might use:

- Two or three closely-related fur tones (highlight, midtone, shadow) for
  depth
- An accent color used sparingly in one element (collar, nose, inner ear)
- Eye colors that read well at the small render size — high contrast
  against the surrounding fur

The framework also drives a five-band eye color tied to battery state
(`good` / `mid` / `warn` / `low` / `charging`). Defaults are green /
yellow / orange / red / pulsing blue — sensible across most palettes,
but they may clash with very vivid animals. You can override any band
per-animal by adding the matching key to your `colors` block:

```js
colors: {
  '--animal-eye':           '142 71% 45%',  // base "good" eye color
  '--animal-eye-good':      '142 71% 45%',  // optional per-animal override
  '--animal-eye-mid':       '50 100% 55%',
  '--animal-eye-warn':      '30 100% 50%',
  '--animal-eye-low':       '0 80% 50%',
  '--animal-eye-charging':  '210 100% 55%',
  // ...rest of palette
}
```

(In a **descriptor**, the same block is JSON with bare `"H S% L%"` triples —
identical values, no `hsl(...)` wrapper.)

When picking colors, keep each band visually distinct at the 64×44 render
size — green vs yellow is easy, but yellow vs orange can muddle if both
are too saturated. The charging color should feel "active" (cool or
electric); the warn/low colors should feel "concerning" without becoming
indistinguishable.

### 5. Asymmetric motion

The walking pose has separate `kneeFlexA` / `kneeFlexB` animations on
alternating legs precisely so the animal doesn't move like a stiff toy.

The framework animates a **fixed set** of lower-leg class names — the `cat-`,
`dog-`, and `rac-` prefixes, each with `-fl-/-fr-/-bl-/-br-lower`. Wrap each
lower-leg subgroup in one of those (with a `transform-origin` at the knee) for
both the walking and animating poses:

```html
<g class="cat-fl-lower" style="transform-origin: 170px 236px"> ... </g>
```

Reusing the `cat-` namespace is correct and intentional — only one animal
renders per element, so there's no collision, and the knee-fold / walk cycle
fire for free. A *brand-new* namespace (`myanimal-fl-lower`) animates **only**
if you also add its keyframes to the framework's animation CSS — a framework
change — so unless you're doing that deliberately, **reuse `cat-*-lower`**. This
is the same rule the descriptor path follows (the sanitiser's class allowlist is
exactly these names plus `animal-eyes` and the parrot's `f-wing-l`/`f-wing-r`) —
see [Make the legs animate](animal-authoring.md#make-the-legs-animate).

Placeholder animals sometimes skip this and end up with all four legs
flexing in sync, which looks robotic.

### 6. Warning pose that actually warns

`warning` is the only pose with a `parts.warning` overlay slot — an
additive group rendered on top of everything in warning pose. The bundled
cat puts a tiny error symbol there; you could do much more (raised hackles,
arched back, alarm ears, exclamation glyph above the head).

A warning that just looks like an angrier alert isn't doing its job. The
user needs to be able to tell "the vacuum has a problem" at a glance from
across the room.

## What "good" doesn't mean

A few non-goals worth stating:

- **Photorealism is not a goal.** The framework is built around stylised,
  flat-shaded SVG with clear silhouettes. A photorealistic raccoon would
  fight the existing keyframes and probably read worse at 64×44.
- **Animation complexity isn't the win.** The keyframes the framework
  provides are deliberately gentle. Don't add 30 new keyframes — the
  existing six poses with a clear silhouette beat over-animated chaos.
- **You don't need every part.** `parts.warning`, `parts.extra`, and the
  parrot's `wingLeft`/`wingRight` are optional. Skip them if your animal
  doesn't need them — empty strings or absent keys are fine.
- **Don't fight the coordinate space.** ViewBox is `-10 -10 500 340` and
  anatomy anchors are documented in the
  [animal-svg dev doc](../dev/frontend/animal-svg.md) under "Coordinate space".
  You can deviate, but pose
  transforms pivot around those anchors regardless, so significant
  deviation produces strange motion.

## The runtime path (maintainer)

Everything below is the **trusted, code-level** route. For a *shared* animal,
none of this applies — submit a [descriptor](animal-authoring.md) and the intake
generates the module for you. Use the raw-JS route only when an animal needs
framework behaviour the declarative descriptor can't express, and expect it to
be reviewed as code.

### Improving a bundled animal

Most bundled animals are now **descriptor-backed**: cat, dog, raccoon, parrot,
and the Mittens memorial each have a source descriptor at
`custom_components/eufy_vacuum/frontend/animal-svg/src/<id>.json`, and the
committed `animals/<id>.js` is *generated* from it. (The exception is **snake** —
a procedural `type: 'custom'` module with no descriptor, edited directly as
code.) To improve a descriptor-backed animal, edit the descriptor and regenerate
the module:

```sh
node scripts/build-animal.mjs \
  custom_components/eufy_vacuum/frontend/animal-svg/src/<id>.json --first-party
```

That rebuilds only the `animals/<id>.js` module — a first-party rebuild leaves
`gallery/animals/` alone (that's the home of community submissions like the Fox).

The `bundled-animals` test guards that each committed `.js` is the faithful
codegen of its descriptor, so **don't hand-edit the `.js`** — change the
descriptor and rebuild. The cleanest submissions touch only one animal and
explain in the PR description:

- What looked wrong (the specific failure of the existing version)
- What changed (a before/after screenshot at 64×44 if at all possible)
- Whether the palette changed (and why)

For a change that needs **framework behaviour** the descriptor can't express (a
new pose hook, a procedural renderer), edit the framework / a hand-written `.js`
directly — see below.

### Adding a runtime animal directly

!!! warning "Maintainer / trusted path — not the public submission route"
    For a **shared** animal, submit a descriptor:
    **[Authoring an animal](animal-authoring.md)**. The raw-JS route here ships
    executable code, so it's for maintainers adding framework-level behaviour or
    a procedural renderer, reviewed as code — the gallery intake never accepts it.

1. Drop `animals/<id>.js` that calls `AnimalSVG.register('<id>', {...})`.
2. Restart Home Assistant.

The integration generates `animals/index.json` at startup from whatever `.js`
files are in that directory — no edit to `manifest.js` needed.

**The ID passed to `register()` must be unique.** Use the filename (minus `.js`)
as the ID. If two files register the same ID the second silently overwrites the
first.

**That is the entire change.** No edits to `src/`. The integration's theme
token registry and editor preview pane both auto-derive from the live
AnimalSVG list — once your file's `register()` call fires, an event
notifies the theme system, which rebuilds the registry and adds:

- An "Animal Companion — `<Id>`" editor sub-group listing the tokens
  your animal actually themes — derived from its `colors` block. A full
  palette is 9 palette + 5 battery-state = 14 tokens, all prefixed
  `--evcc-animal-<id>-`; declare fewer keys and only those appear.
- A single-animal preview pane in the editor showing your animal in all
  five battery-state bands

(Mark the definition `memorial: true` and it groups under a 🌈 **Rainbow
Bridge** tribute section instead — see [Memorial animals](#memorial-animals).)

PR description should include: a screenshot of all six poses (you can use
`demo.html` for this), what the animal expresses (cat → reserved, parrot
→ flighty, etc.), and the palette rationale.

### Procedural (`type: 'custom'`) animals — maintainer only

If an animal needs procedural rendering (snake-like), use `type: 'custom'`.
This **bypasses the parts pipeline and the sanitiser entirely** — you return a
render function, i.e. arbitrary JavaScript that draws into the host — so it is a
**maintainer-authored, code-reviewed** addition only. The public descriptor
intake rejects `type: "custom"` for exactly this reason: there's no safe way to
sanitise a renderer. See `animals/snake.js` for the pattern. You are entirely
responsible for the warning pose in custom animals — the framework hands you the
pose name and walks away.

### Memorial animals

A memorial mascot is a tribute to a real animal (e.g. `animals/mittens.js`,
modelled from photos of the author's cat). The "placeholder quality" disclaimer
at the top does **not** apply — a memorial is held to a *higher* bar than the
bundled animals: it should read as that specific animal, with its real markings,
not a generic shape. (Memorials work on the [descriptor](animal-authoring.md)
path too — the rule is the same; only the format differs.)

Two things set a memorial apart from a normal animal:

- **Bake the colors in.** Put the fur, markings, and white as literal `hsl()`
  values directly in the parts — *not* as `colors` keys. A tribute should stay
  true to the real animal regardless of the active theme, so its palette is
  deliberately **not** themeable. Leave only `--animal-eye` in the `colors` block
  (the battery-state system needs it dynamic), and the editor then lists just the
  eye tokens for it — no inert fur/nose/whisker entries.
- **Set `memorial: true`.** This groups the animal under a 🌈 **Rainbow Bridge**
  section in the theme editor and the map-view picker, set apart from the everyday
  companions. It's orthogonal to `type` — a memorial keeps its body plan (Mittens
  is a `quadruped`).

Everything else is the same as any animal: it still has to express all six poses
and obey the coordinate space — it just does so as a faithful portrait rather than
a placeholder. The technical specifics (the `memorial` flag, the colors-derived
token list) are in the [animal-svg dev doc](../dev/frontend/animal-svg.md#memorial-animals-rainbow-bridge).

### Sanity check before submitting

Open `demo.html` (served at `/eufy_vacuum/frontend/animal-svg/demo.html` if
the integration is installed, or open it directly from the file editor).
Walk through every pose for your animal. All six poses should look
intentional, not accidental.

If any pose looks broken at the default size *and* at 2× scale, fix it
before submitting. Map-view users will see one or the other; both should
work.

## Style: when in doubt, look at what works

The bundled animals aren't great, but the framework conventions they
established are sound:

- **cat.js** — reference quadruped. Read for: parts structure, lower-leg
  knee-fold namespacing, HSL color triplet convention, where the `parts.eyes`
  group sits inside `parts.head`.
- **parrot.js** — reference upright/perched animal with an extra wings
  feature only shown in walking (flight) pose. Read for: how `type:
  'parrot'` differs from quadruped, optional `wingLeft`/`wingRight`,
  `parts.extra` for the perch.
- **snake.js** — reference procedural (`type: 'custom'`) animal, **maintainer
  path only**. Read for: how to bypass the parts pipeline entirely, return a
  cleanup function, handle each framework pose by mapping to your own internal
  modes.

You don't need to study all three to add one new animal. Pick the one
closest to your concept and copy its structure. (For a descriptor animal, the
worked example is the **Fox** at `gallery/animals/fox.json`.)

## A note on creative range

The framework intentionally supports six poses that map to vacuum activity
states. That means anything you build is going to be expressing those
states in *some* form: rest, stand, walk, alert, warn, animate.

That doesn't constrain the *animal* — a frog, a fox, an octopus, an alien,
a mechanical dog all fit. It constrains the *vocabulary*: whatever animal
you pick has to express those six states convincingly. If your concept
doesn't have a believable "warning" expression (e.g. an inanimate object),
either find one (a shaking, an emanating glow, a colour shift) or pick a
different concept.
