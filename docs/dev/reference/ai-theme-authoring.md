# Authoring themes with an AI

You don't have to understand the token system to make a theme for it — you need an
assistant, the three theme references, and the [render harness](../27-render-harness.md).
Writing a theme JSON by hand is a power-user move
([Authoring a theme JSON by hand](../20-theme-system.md#authoring-a-theme-json-by-hand));
handing that job to an AI is the general-purpose path, and it's surprisingly low-effort.

It works because the system is **constrained at every layer**: the catalog bounds what's
legal, the importer validates the values, and the usage trace turns visual feedback into a
targeted edit. No glue code is involved — the AI's output *is* the import format, and the
harness already eats the import format.

## The three inputs

| Doc | What it gives the AI |
|---|---|
| [Theme Token Map](THEME_TOKEN_MAP.md) | **the spec** — every legal `--evcc-*` key, its `Type`, and its `Range` |
| [Theme Token CSS-Usage Trace](THEME_TOKEN_USAGE.md) | **the targeting map** — the exact CSS property each token paints |
| [The import envelope](../20-theme-system.md#authoring-a-theme-json-by-hand) | **the output contract** — `{ name, colors, alpha, tokens }` |

## The loop

1. **Prompt with the spec.** Give the model a target — a description, a photo, a few hex
   swatches — plus the **Theme Token Map**. It can't invent a token, and `import_theme`
   clamps or rejects anything off-range, so whatever it returns is always loadable.
2. **It emits the envelope.** The `{ name, colors, alpha, tokens }` object *is* the import
   payload — no conversion step. (Use `colors` + `alpha` for picker-editable colors, or
   just put values straight in `tokens`; see the
   [hand-authoring rules](../20-theme-system.md#authoring-a-theme-json-by-hand).)
3. **Render it.** `node harness/preview.mjs path/to/theme.json` writes a contact sheet plus
   per-view PNGs to `harness/out/preview/<name>/`. That's the eval — and a multimodal model
   can read the PNG straight back.
4. **Critique the picture, fix by token.** This is where the usage trace earns its keep:
   "the completed room names are muddy" becomes a precise edit
   (`--evcc-queue-completed-text` + `--evcc-queue-completed-opacity`) instead of a guess.
   Change those keys, re-render.
5. **Repeat** until it reads right — usually by locking surfaces and accent and moving only
   the flagged controls. Two or three passes is typical.

## What it is (and isn't)

This is a **workflow, not a built-in feature**. Nothing wires an AI to the card; you drive
the loop. The pieces were each built for other reasons — self-documenting the token system,
catching dead/undefined tokens, visual-regression — and they happen to compose into a theme
generator. "A vibe in, a renderable theme out, self-correcting over a couple of passes" is a
real path, open to anyone with the harness and these docs.
