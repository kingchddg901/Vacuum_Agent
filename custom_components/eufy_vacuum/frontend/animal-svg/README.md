# animal-svg

Standalone `<animal-svg>` web component for Home Assistant. No React, no build
step, no dependencies. Animals self-register via a small JS API; the element
re-renders on attribute change.

This folder is the contract document for two audiences:

- **Integration authors** who use `<animal-svg>` to express device state.
- **Creature-pack authors** who add new animals.

If you are using or extending the eufy_vacuum panel's map view, jump to
[Integration contract](#integration-contract) — it documents exactly what the
panel passes to `<animal-svg>` (and what it does *not* pass).

## Files

```
animal-svg/
├── animal-svg.js     custom element + registry + shared keyframes
├── manifest.js       loads animal-svg.js then each animal file
├── animals/
│   ├── cat.js
│   ├── dog.js
│   ├── raccoon.js
│   ├── parrot.js
│   └── snake.js
└── demo.html         open in a browser to verify everything works
```

## Install

When this folder is part of the eufy_vacuum integration, the integration
serves it at `/eufy_vacuum/frontend/animal-svg/` automatically — nothing else
to do. The panel card loads `manifest.js` from that path during its first
render.

To use the component standalone (outside the eufy_vacuum panel), drop the
folder into `<config>/www/animal-svg/`, then in **Settings → Dashboards →
Resources** add the resource:

* URL: `/local/animal-svg/manifest.js`
* Type: **JavaScript Module**

Then anywhere in a card:

```html
<animal-svg animal="cat" pose="walking"></animal-svg>
```

## Attributes

| Attribute  | Values | Default | Behaviour |
|------------|--------|---------|-----------|
| `animal`   | `cat`, `dog`, `raccoon`, `parrot`, `snake`, or any registered animal | `cat` | Triggers full re-render |
| `pose`     | `animating`, `standing`, `curled`, `alert`, `walking`, `warning` | `standing` | Triggers full re-render |
| `width`    | any CSS length | `360px` | Applied to host (`:host { width: ... }`) |
| `height`   | any CSS length | `240px` | Applied to host |
| `charging` | presence-only (boolean attribute) | absent | Pure CSS — re-targets `--animal-eye` to `--animal-eye-charging` (default yellow `50 100% 55%`) when present |

`animal` and `pose` are observed and trigger a full re-render via
`attributeChangedCallback`. `width`, `height`, and `charging` work without
re-rendering — `charging` in particular is implemented as a `:host([charging])`
CSS rule, so toggling it on/off is essentially free.

From JS you can also use `el.setAnimal(name)` / `el.setPose(pose)`.

## Integration contract

This is the specific contract the **eufy_vacuum panel's map view** honors —
the only place `<animal-svg>` is invoked from this integration. Creature-pack
authors targeting this panel can rely on every point below.

### What the panel passes

The panel renders **exactly one** `<animal-svg>` per map view, mounted in
`.evcc-map-animal` and positioned absolutely on the map by % coordinates
(driven by the same per-room anchor system that the legacy presence dot used).

It sets these attributes and nothing else:

| Attribute   | Source on the panel side |
|-------------|--------------------------|
| `animal`    | `state.mapAnimalSelection()` — user-configurable, default `"cat"` |
| `pose`      | Derived from the HA vacuum entity's state (see mapping below) |
| `width`     | `64 * state.mapAnimalScale()` (user-configurable, default 1.0×) |
| `height`    | `44 * state.mapAnimalScale()` |
| `charging`  | Present when `binary_sensor.<vacuum>_charging` is `on`; absent otherwise |

**Things the panel deliberately does NOT pass:**

- No color overrides. Animals own their palette via the `colors` block in
  their definition. The only color signal the panel injects is the binary
  `charging` attribute.
- No theme tokens. The card's wider theme system does not reach into the
  animal's shadow root. Animals stay visually consistent regardless of card
  theme.
- No event handlers. The wrapper div carries the click/drag handlers for
  repositioning the anchor; the `<animal-svg>` itself receives no click
  listeners from the panel. The component's built-in click-to-cycle-pose
  feature (if your custom animal implements one) is unused — pose is fully
  driven by vacuum state.

### State → pose mapping

The mapping is defined in `src/renderers/map.js::_vacuumStateToPose` and uses
the canonical HA vacuum-platform state vocabulary (brand-agnostic):

| HA vacuum state      | `pose` requested |
|----------------------|------------------|
| `cleaning`           | `alert`          |
| `returning`          | `walking`        |
| `paused`             | `standing`       |
| `error`              | `warning`        |
| `docked` / `idle`    | `curled` (+ a `--pulse` CSS modifier on the wrapper) |
| anything else / null | `curled`         |

**The panel only ever requests one of the six framework poses.** It never
makes up new pose names. Creature packs only need to implement the six poses
the framework defines.

### `charging` semantics

The panel attaches the `charging` attribute when the vacuum is actively
charging on the dock. It is **orthogonal to `pose`** — a docked vacuum
gets `pose="curled"` AND (usually) `charging`. A docked vacuum at full
battery gets `pose="curled"` but no `charging`.

The framework's default behaviour:

```css
:host([charging]) {
  --animal-eye: var(--animal-eye-charging, 50 100% 55%);
}
```

So out of the box, charging swaps the eye color to a warm yellow.
An animal can customise by setting `--animal-eye-charging` in its `colors`
block (e.g. an electric-blue charging look). The framework provides only
this single override hook for now; if you want to express charging more
elaborately (body pulse, tail twitch, particle effects), implement it
yourself via a CSS rule scoped to `:host([charging]) .your-class`.

### How creature-pack authors should think about this

When you write a new animal for the eufy_vacuum panel, the only state inputs
you can rely on are:

1. The six framework poses (the panel will only request these)
2. The presence/absence of the `charging` attribute (binary)

If your animal needs more state than that — battery percentage, dock activity,
fan speed, anything — you cannot get it. The contract is intentionally narrow.
This protects the panel from being coupled to creature internals, and
protects creatures from breaking when the panel's state model changes.

If you want to ship an animal that does more, it must be expressed entirely
through pose × charging-state combinations.

## Wiring to HA state (standalone usage)

When using the component outside the eufy_vacuum panel, drive it from any HA
template-capable card:

```yaml
type: custom:html-template-card
content: |
  <animal-svg
    animal="cat"
    pose="{{ 'walking' if is_state('vacuum.alfred','cleaning')
            else 'curled'  if is_state('vacuum.alfred','docked')
            else 'warning' if is_state('vacuum.alfred','error')
            else 'standing' }}"
    {% if is_state('binary_sensor.alfred_charging','on') %}charging{% endif %}>
  </animal-svg>
```

(The exact card you use to inject HTML is up to you — `html-template-card`,
`config-template-card`, or any custom card that handles templating.)

## Adding / removing / editing an animal

Each animal is its own self-registering file in `animals/`. To add one:

1. Create `animals/myanimal.js` that calls `AnimalSVG.register('myanimal', { ... })`.
2. Add `loadScript('animals/myanimal.js')` to the array in `manifest.js`.

To remove one, delete its line from `manifest.js` (and optionally its file).

To edit colors only, change the `colors` block in the relevant file — no other
files need to change.

## Definition shape

```js
AnimalSVG.register('myanimal', {
  label: 'My Animal',
  type:  'quadruped',  // or 'parrot' or 'custom'

  // CSS variables consumed by the SVG paths (HSL components, no `hsl()`).
  colors: {
    '--animal-fur':            '0 0% 7%',
    '--animal-fur-shadow':     '0 0% 5%',
    '--animal-fur-highlight':  '0 0% 10%',
    '--animal-eye':            '142 71% 45%',
    '--animal-eye-charging':   '50 100% 55%',  // optional; overrides the framework default
    '--animal-pupil':          '0 0% 7%',
    '--animal-nose':           '0 0% 33%',
    '--animal-whisker':        '0 0% 33%',
    '--animal-ear-inner':      '0 0% 10%',
    '--animal-white-tip':      '0 0% 100%',
  },

  // For `quadruped` and `parrot` types, supply SVG-fragment strings.
  // The host element wraps each in a transform group so pose animations apply.
  parts: {
    body:          '<path .../>',
    frontLeftLeg:  '<g>...</g>',
    frontRightLeg: '<g>...</g>',
    backLeftLeg:   '<g>...</g>',
    backRightLeg:  '<g>...</g>',
    tail:          '<g>...</g>',
    head:          '<g>...</g>',
    eyes:          '<g>...</g>',
    face:          '<g>...</g>',
    warning:       '<g>...</g>',  // additive overlay rendered only in warning pose
    extra:         '<g>...</g>',  // optional, drawn behind everything (e.g. perch)
  },

  // Parrot only: shown only in walking (flight) pose.
  wingLeft:  '<g class="f-wing-l">...</g>',
  wingRight: '<g class="f-wing-r">...</g>',
});
```

### Coordinate space

ViewBox is `-10 -10 500 340`. Quadruped anatomy is anchored around:

| Part | Approx. centre |
|------|----------------|
| Head | `(140, 140)` |
| Eyes | `(145, 117)` |
| Body | `(250, 200)` |
| Tail base | `(340, 180)` |
| Front-left leg | `(166, 198)` |
| Front-right leg | `(194, 198)` |
| Back-left leg | `(303, 198)` |
| Back-right leg | `(332, 195)` |

Parrot anatomy:

| Part | Approx. centre |
|------|----------------|
| Head | `(220, 140)` |
| Eyes | `(218, 108)` |
| Body | `(258, 244)` (perched) / `(258, 200)` (warning) |
| Tail base | `(320, 225)` |
| Wings | left `(210, 155)`, right `(310, 155)` |
| Perch | `y = 278` |

These are the `transform-origin` anchors used by the shared keyframes.
Following them keeps animations consistent. You can deviate, but pose
transforms (rotate/translate) will pivot around those points regardless.

### Warning-pose responsibility

For `quadruped` and `parrot` animals, the framework handles the warning pose
through the standard pipeline: it applies head/body/tail transforms and
toggles the `parts.warning` overlay group (if you supply one). You don't have
to do anything special — just author the warning paths into `parts.warning`
and they'll appear in `warning` pose, hidden in every other pose.

For `custom` animals (see next section), warning is the renderer's
responsibility entirely. The framework hands you the pose string and walks
away. The reference implementation is `animals/snake.js`, which maps the
framework's `warning` pose to its own internal `'warning'` mode and renders
a coiled-strike posture procedurally.

The rule: **declarative animals get the warning pipeline for free.
Procedural (`type: 'custom'`) animals own the warning rendering themselves.**

### Lower-leg knee folding

For curling and walking knee-flex animations to fire on a quadruped, the
lower half of each leg must be wrapped in a group with one of these classes
(pick the namespace that does not collide with another animal):

* Front-left lower:  `xxx-fl-lower`
* Front-right lower: `xxx-fr-lower`
* Back-left lower:   `xxx-bl-lower`
* Back-right lower:  `xxx-br-lower`

Built-in namespaces are `cat-`, `dog-`, `rac-`. To add a new namespace, edit
the selector lists in `animal-svg.js` (`.pose-animating .xxx-fl-lower, ...`
and `.pose-walking .xxx-fl-lower, ...`).

### Custom (procedural) animals

For animals like the snake that need procedural geometry — anything the
quadruped or parrot parts pipeline can't express — use `type: 'custom'` and
supply a `render(svg, pose)` function.

The host gives you the live `<svg>` element. Build DOM into it however you
want. Return a cleanup function that the host will call on pose change or
disconnect — at minimum, cancel any `requestAnimationFrame` and remove your
nodes.

```js
AnimalSVG.register('myproc', {
  label: 'Procedural', type: 'custom',
  colors: { ... },
  render(svg, pose) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    svg.appendChild(g);
    let raf = requestAnimationFrame(function tick(t) {
      // ...mutate g based on t and pose...
      raf = requestAnimationFrame(tick);
    });
    return () => { cancelAnimationFrame(raf); g.remove(); };
  },
});
```

The framework still honors `charging` for custom animals — the
`:host([charging])` rule that swaps `--animal-eye` applies regardless of
type, so if your custom animal uses `hsl(var(--animal-eye))` for any
element it'll respond automatically. To express charging more elaborately
in a custom animal, add your own CSS rule scoped to `:host([charging]) .your-class`
or read the `charging` attribute inside your render callback.

## Contributing or making your own

The five bundled animals are placeholder quality — built to validate the
framework, not to look polished. A separate guide,
[CONTRIBUTING.md](./CONTRIBUTING.md), covers what "good" means here (pose
silhouette, palette intent, stroke hierarchy, warning expression) and how
to submit improvements or new animals. Read it before opening a PR or
shipping a custom animal for your own install — the technical contract in
this README tells you what works; CONTRIBUTING.md tells you what looks
finished.

## Debugging

Open `demo.html` in a browser (use the HA file editor or any static-file
viewer that can serve `/config/www/` or `/eufy_vacuum/frontend/`). The page
builds a grid of every registered animal and lets you scrub through every
pose. Add `?charging` to the URL to test the charging state.

If you see "animal-svg: unknown animal" in the host element, the registration
file did not run — check the browser console for a load error in `manifest.js`.
