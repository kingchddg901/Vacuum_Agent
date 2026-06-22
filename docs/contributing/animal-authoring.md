# Authoring an animal

So you want to make a companion animal — one of the little creatures that lives
on your map and follows the robot — to keep, or to share in the
[animal gallery](https://kingchddg901.github.io/Vacuum_Agent/animals/). This page is about the **descriptor format**
and making the result *good*.

*Using* animals — picking a companion per vacuum, the Rainbow Bridge group, the
battery-state eyes — is covered in the user guide. This page is about building a
new one.

## Two rules to know up front

1. **It's declarative — never code.** An animal you submit is a JSON
   **descriptor**: colour tokens plus SVG path data. There is no JavaScript and
   no procedural renderer (`type: "custom"` is maintainer-only). The intake
   **sanitises** every SVG part, then *generates* the runtime module from your
   validated data — so a submission can never run code on anyone's dashboard.
2. **Baked colours ⟹ a tribute.** If you bake your colours in as literal
   `hsl(...)` values (so the animal always looks exactly like *one specific*
   creature — a real pet, say — and only the eye stays dynamic), it must set
   `"memorial": true` and it joins the **🌈 Rainbow Bridge** group. Otherwise,
   expose a themeable `--animal-*` colour block so it recolours in the theme
   editor like a regular companion. *(A baked animal with no memorial flag is
   rejected — "make it themeable, or tell us whose it is.")*

## The descriptor

A complete worked example is the Fox, at `gallery/animals/fox.json`. The shape:

```json
{
  "id": "fennec",
  "name": "Fennec Fox",
  "type": "quadruped",
  "license": "CC-BY-4.0",
  "colors": { "--animal-eye": "40 30% 20%", "--animal-fur": "30 60% 70%" },
  "parts": { "body": "<path .../>", "head": "...", "...": "..." },
  "memorial": false,
  "author": "Your name",
  "author_url": "https://...",
  "submitted_by": "Your name",
  "description": "A desert fox companion.",
  "tags": ["fox", "desert"]
}
```

- `id` — `^[a-z][a-z0-9-]{1,30}$`, unique, not one of the built-ins.
- `type` — `quadruped` or `parrot`.
- `license` — required: `CC0-1.0`, `CC-BY-4.0`, `MIT`, or `Apache-2.0`.
- `author_url` — optional, a direct `http(s)` link only (no shorteners).
- `description` — optional, ≤ 280 characters.

You can submit the bare `animal` object (above) or wrap it in an envelope
(`{ "version": 1, "kind": "animal", "animal": { ... } }`) — the intake accepts both.

### Already have a `.js` animal?

If you wrote one as a module (the old format — `const` colour aliases and
backtick `parts` with `${...}` interpolation, like the bundled
`raccoon.js`), **don't hand-translate it.** The converter runs your module to
capture the definition with every `${FUR}` interpolation already resolved,
tidies the SVG (and switches attributes to single quotes), and writes the
descriptor for you:

```sh
node scripts/animal-js-to-descriptor.mjs your-animal.js --license CC-BY-4.0 -o your-animal.json
```

Then add author/description if you like and validate it like any other
descriptor (below). Procedural (`type: "custom"`) modules can't be converted —
they're code, not data.

### Colours

Every key you declare in `colors` becomes a **themeable token**: the framework
wraps it so a theme can override it per-animal or globally, and the theme editor
lists exactly the tokens you declared. Values are **bare HSL triples** —
`"H S% L%"` (e.g. `"142 71% 45%"`), no `hsl(...)` wrapper, no `;`.

- In your `parts`, reference a token as `fill="hsl(var(--animal-fur))"`.
- **Always declare `--animal-eye`.** The eye is recoloured by battery state
  (green when full, red when low, blue while charging), so it must stay on the
  token. Tag the eye's group with `class="animal-eyes"` to get the charging pulse.
- A **baked** animal declares *only* `--animal-eye` and hard-codes the rest as
  literal `hsl(...)` in the parts (the Mittens pattern) — and so must be `memorial`.

### Parts (the anatomy)

`parts` is one SVG string per anatomical slot. The drawing space is a
`viewBox="-10 -10 500 340"` — the easiest start is to trace over an existing
quadruped (`cat.js` or the Fox), keeping the same coordinate anchors so the
poses line up.

**Quadruped** (cat / dog / fox): `body`, `frontLeftLeg`, `frontRightLeg`,
`backLeftLeg`, `backRightLeg`, `tail`, `head`, `eyes`, `face` — all required —
plus optional `warning` (a spooked overlay) and `extra`.

**Parrot**: `body`, `frontLeftLeg`, `frontRightLeg`, `tail`, `head`, `eyes`,
`face` (no hind legs) plus optional `warning` / `extra`.

#### From your drawing to the JSON

Once you have the SVG, turning it into the descriptor is mechanical:

1. **Split it into the slots.** Each anatomical group above becomes one entry in
   `parts` — just the markup that draws that piece (a `<g>`, some `<path>`s).
   Leave out the outer `<svg>` wrapper; the framework supplies it.
2. **Use single quotes for attributes.** JSON strings are double-quoted, and so
   is SVG by convention — so pasting `<path d="…" fill="…"/>` into JSON means
   escaping every quote as `\"`. Instead write your SVG with **single-quoted**
   attributes — `<path d='…' fill='…'/>` — and the JSON needs no escaping at all.
   SVG accepts single quotes, and the sanitiser normalises everything back to
   double quotes on the way out. *(The Fox's source is written exactly this way.)*
3. **Swap literal colours for tokens.** Replace each `fill='#e0742a'` with
   `fill='hsl(var(--animal-fur))'` and declare `--animal-fur` in `colors` — now
   it's themeable. (Or keep it a literal `hsl(...)` and make the animal a
   memorial — see the rule up top.)

So one slot ends up looking like:

```json
"body": "<path d='M145,160 C155,145 280,130 348,162 Z' fill='hsl(var(--animal-fur))'/>"
```

#### Check it before you submit

Compile your descriptor locally — it validates, sanitises, and generates the
module — then render every pose to eyeball it (both use a headless browser, so
run `npm ci` first):

```sh
node scripts/build-animal.mjs path/to/your-animal.json   # validate + sanitise + codegen
node scripts/preview-animal.mjs <id>                      # 6-pose contact sheet
```

`build-animal` refuses anything the contract gate or sanitiser rejects and tells
you exactly what to fix — the same checks the intake runs.

#### Make the legs animate

The framework's knee-bend animations (for the *curled*, *walking*, and
*animating* poses) are wired to a fixed set of class names. So wrap each
lower-leg group in the matching class and give it a `transform-origin` at the
knee:

```html
<g class="cat-fl-lower" style="transform-origin: 170px 236px"> ... </g>
```

Use `cat-fl-lower` / `cat-fr-lower` / `cat-bl-lower` / `cat-br-lower` (front/back,
left/right). Reusing the `cat-` namespace is correct and intentional — only one
animal renders per element, so there's no collision, and the knee-fold / walk
cycle fire for free with no framework change. (The Fox and Mittens both do this.)

### What the sanitiser allows

Your SVG is run through DOMPurify in a real browser at intake. **Allowed:**
geometry (`path`, `circle`, `ellipse`, `rect`, `line`, `polyline`, `polygon`,
`g`), gradients/clips (`defs`, `linearGradient`, `radialGradient`, `stop`,
`clipPath`, `use`), and presentation attributes (`fill`, `stroke`, `opacity`,
`transform`, etc.). `style` is clamped to `transform-origin` (plus a few). `href`
must be an internal `#fragment` (e.g. `fill="url(#grad)"`). **Stripped or
rejected:** `<script>`, `<foreignObject>`, `<image>`, event handlers
(`onload=...`), external references, `javascript:` / `data:` URIs, and any
non-allowlisted class. Keep your art to those primitives and nothing is removed.

### Licence

An SVG drawing is copyrightable art, so a `license` is **required**. Only submit
art you have the right to share under the licence you name.

## Submitting

Two paths, both end in a maintainer-reviewed pull request:

- **Issue form (easiest):** open a new animal submission
  (Issues, "Animal submission" template) and paste your descriptor. A bot
  validates it, sanitises the SVG, renders a 6-pose preview, and opens the PR
  for you.
- **Fork PR:** add `gallery/animals/<id>.json` and run
  `node scripts/build-animal.mjs gallery/animals/<id>.json` to generate the
  module, then open a PR. The `animal PR check` gate validates it the same way.

Either way, once merged your animal appears in the [gallery](https://kingchddg901.github.io/Vacuum_Agent/animals/) and
the in-card companion picker — themeable, in every pose, with no edit to the
framework.
