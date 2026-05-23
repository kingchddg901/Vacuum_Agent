# animal-svg

Standalone `<animal-svg>` web component for Home Assistant. No React, no build
step, no dependencies. Drop the folder into `/config/www/animal-svg/` and it is
served at `/local/animal-svg/`.

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

## Lovelace install

Settings → Dashboards → Resources → Add resource:

* URL: `/local/animal-svg/manifest.js`
* Type: **JavaScript Module**

Then anywhere in a card (e.g. inside an `html-template-card`, `markdown` raw
HTML, or any custom card):

```html
<animal-svg animal="cat" pose="walking"></animal-svg>
```

## Attributes

| Attribute | Values | Default |
|-----------|--------|---------|
| `animal`  | `cat`, `dog`, `raccoon`, `parrot`, `snake` (or any registered animal) | `cat` |
| `pose`    | `animating`, `standing`, `curled`, `alert`, `walking`, `warning` | `standing` |
| `width`   | any CSS length | `360px` |
| `height`  | any CSS length | `240px` |

Both `animal` and `pose` are observed — change them at runtime and the SVG
re-renders. From JS you can also use `el.setAnimal(name)` / `el.setPose(pose)`.

## Wiring to HA state

The element is fully attribute-driven, so you can drive it from a template:

```yaml
type: custom:html-template-card
content: |
  <animal-svg
    animal="cat"
    pose="{{ 'walking' if is_state('vacuum.alfred','cleaning')
            else 'curled'  if is_state('vacuum.alfred','docked')
            else 'warning' if is_state('vacuum.alfred','error')
            else 'standing' }}">
  </animal-svg>
```

(The exact card you use to inject HTML is up to you — `html-template-card`,
`config-template-card`, or a custom card that handles templating.)

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

### Lower-leg knee folding

For curling and walking knee-flex animations to fire on a quadruped, the lower
half of each leg must be wrapped in a group with one of these classes (pick the
namespace that does not collide with another animal):

* Front-left lower:  `xxx-fl-lower`
* Front-right lower: `xxx-fr-lower`
* Back-left lower:   `xxx-bl-lower`
* Back-right lower:  `xxx-br-lower`

Built-in namespaces are `cat-`, `dog-`, `rac-`. To add a new namespace, edit
the selector lists in `animal-svg.js` (`.pose-animating .xxx-fl-lower, ...`
and `.pose-walking .xxx-fl-lower, ...`).

### Custom (procedural) animals

For animals like the snake that need procedural geometry, use `type: 'custom'`
and supply a `render(svg, pose)` function. The host gives you the live `<svg>`
element. Build DOM into it however you want. Return a cleanup function that the
host will call on pose change or disconnect — at minimum, cancel any
`requestAnimationFrame` and remove your nodes.

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

## Debugging

Open `demo.html` in a browser (use the HA file editor or any static-file
viewer that can serve `/config/www/`). The page builds a grid of every
registered animal and lets you scrub through every pose.

If you see "animal-svg: unknown animal" in the host element, the registration
file did not run — check the browser console for a load error in `manifest.js`.
