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
| `battery-state` | `good`, `mid`, `warn`, `low`, `charging` | absent ≡ `good` | Pure CSS — re-targets `--animal-eye` to the matching framework default (`good`=green, `mid`=yellow, `warn`=orange, `low`=red, `charging`=blue). Themes can override via `--evcc-animal-eye-*` tokens. `charging` additionally drives a gentle brightness pulse on elements tagged `.animal-eyes`. |

`animal` and `pose` are observed and trigger a full re-render via
`attributeChangedCallback`. `width`, `height`, and `battery-state` work without
re-rendering — `battery-state` is implemented as five `:host([battery-state="X"])`
CSS rules plus a keyframe animation, so flipping through values is essentially
free.

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
| `battery-state` | `state.batteryState()` — resolved from battery % + charging into one of `good` / `mid` / `warn` / `low` / `charging` |

**Things the panel deliberately does NOT pass directly to the element:**

- No color attributes or inline color styles. Color customisation happens
  through the **theme token system** (see [Theme integration](#theme-integration)
  below) — the card sets `--evcc-animal-*` tokens on its host, the animal-svg
  shadow root picks them up via CSS custom-property inheritance, and the
  animal's per-definition defaults serve as fallbacks.
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

### `battery-state` semantics

The panel sets `battery-state` to one of five values resolved by
`state.batteryState()`:

| State      | Trigger | Framework default eye color |
|------------|---------|-----------------------------|
| `charging` | `binary_sensor.<vacuum>_charging` is `on` (overrides level-based bands) | blue, pulsing |
| `low`      | battery ≤ 15% | red |
| `warn`     | 15% < battery ≤ 25% | orange |
| `mid`      | 25% < battery ≤ 50% | yellow |
| `good`     | battery > 50% (or unavailable) | green |

It's **orthogonal to `pose`** — a docked vacuum gets `pose="curled"`
regardless of which `battery-state` band applies. A docked vacuum at full
battery gets `pose="curled"` + `battery-state="good"`. A docked vacuum
actively charging gets `pose="curled"` + `battery-state="charging"`.

Implementation: five `:host([battery-state="X"])` rules swap `--animal-eye`
to a state-specific color. The `charging` value additionally drives a
brightness pulse via the `evcc-animal-eye-pulse` keyframe on any element
tagged with the `.animal-eyes` class. The framework auto-tags the eye
group in `quadruped`/`parrot` types; `custom` animals add the class
themselves.

Themes override any of the five colors via the corresponding theme token:

| State       | Theme token                     |
|-------------|---------------------------------|
| `good`      | `--evcc-animal-eye-good`        |
| `mid`       | `--evcc-animal-eye-mid`         |
| `warn`      | `--evcc-animal-eye-warn`        |
| `low`       | `--evcc-animal-eye-low`         |
| `charging`  | `--evcc-animal-eye-charging`    |

Animals may also override these per-animal by including the matching
`--animal-eye-*` keys in their `colors` block (theme token still wins
over per-animal default).

### How creature-pack authors should think about this

When you write a new animal for the eufy_vacuum panel, the only state inputs
you can rely on are:

1. The six framework poses (the panel will only request these)
2. The five `battery-state` values (the panel will only set one of these)

If your animal needs more state than that — fan speed, dock activity, error
code, anything — you cannot get it. The contract is intentionally narrow.
This protects the panel from being coupled to creature internals, and
protects creatures from breaking when the panel's state model changes.

If you want to ship an animal that does more, it must be expressed entirely
through pose × battery-state combinations.

### Theme integration

Every color the animal-svg framework consumes is theme-overridable. The
shadow root wraps each per-animal default as a **two-level** fallback:

```css
--animal-X: var(--evcc-animal-<name>-X, var(--evcc-animal-X, <animal default>));
```

Override priority, highest first:

1. **Per-animal theme token** — `--evcc-animal-cat-fur`, `--evcc-animal-dog-eye-warn`, etc.
2. **Global animal token** — `--evcc-animal-fur`, `--evcc-animal-eye-warn`, etc.
3. **Animal's own default** — the value baked into the animal's `colors` block.

A theme that just wants "all forest dark" sets the global tokens once.
A theme that wants per-animal character (cat black, dog brown, parrot bright)
sets per-animal tokens. Both layers can coexist — per-animal wins where set,
global fills in everywhere else.

The theme editor surfaces these in six groups:

- **Animal Companion** — global tokens (5 eye-state colors + 9 palette
  fallbacks). Bulk-override every animal at once.
- **Animal Companion — Cat / Dog / Raccoon / Parrot / Snake** — per-animal
  overrides. Each sub-group has 14 tokens (5 eye-state + 9 palette). Each
  also has its own preview showing just that animal in all five battery
  states, so it's clear what each token controls before you save.

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
    battery-state="{% set b = states('sensor.alfred_battery') | int(0) -%}
      {% if is_state('binary_sensor.alfred_charging','on') -%}charging
      {%- elif b <= 15 -%}low
      {%- elif b <= 25 -%}warn
      {%- elif b <= 50 -%}mid
      {%- else -%}good
      {%- endif %}">
  </animal-svg>
```

(The exact card you use to inject HTML is up to you — `html-template-card`,
`config-template-card`, or any custom card that handles templating.)

## Adding / removing / editing an animal

Each animal is its own self-registering file in `animals/`. To add one:

1. Create `animals/myanimal.js` that calls `AnimalSVG.register('myanimal', { ... })`.
2. Add `loadScript('animals/myanimal.js')` to the array in `manifest.js`.

**That's it.** When the file's `register()` call fires, an
`animal-svg-registered` document event tells the integration's theme
system to rebuild its dynamic registry. Your animal appears automatically
in the map view's animal selector, in the theme editor with its own
sub-group of 14 tokens, and in the editor's per-animal preview pane.
There are no `src/` edits to make.

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
    '--animal-eye-good':       '142 71% 45%',  // optional; per-animal default for battery>50
    '--animal-eye-mid':        '50 100% 55%',  // optional; battery 25-50
    '--animal-eye-warn':       '30 100% 50%',  // optional; battery 15-25
    '--animal-eye-low':        '0 80% 50%',    // optional; battery ≤15
    '--animal-eye-charging':   '210 100% 55%', // optional; pulses while charging
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

The framework still honors `battery-state` for custom animals — the five
`:host([battery-state="X"])` rules that swap `--animal-eye` apply
regardless of type, so any element your render callback creates with
`fill="hsl(var(--animal-eye))"` responds automatically. To opt elements
into the charging pulse, tag them `class="animal-eyes"` (the snake does
this on its eye circles). For anything more elaborate, add your own CSS
scoped to `:host([battery-state="charging"]) .your-class` or read the
attribute inside your render callback.

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
pose. Pass `?battery-state=charging` (or `low` / `warn` / `mid` / `good`)
in the URL to test each band.

If you see "animal-svg: unknown animal" in the host element, the registration
file did not run — check the browser console for a load error in `manifest.js`.
