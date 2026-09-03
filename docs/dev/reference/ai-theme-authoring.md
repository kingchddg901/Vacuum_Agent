# Authoring themes with an AI

You don't need to understand the token system to theme it — an assistant, the three
references below, and the [render harness](../frontend/render-harness.md) are enough. Writing the
JSON [by hand](../frontend/theme-system.md#authoring-a-theme-json-by-hand) is the power-user move;
handing it to an AI is the accessible one.

It works because every layer is **constrained**: the catalog bounds what's legal, the
importer checks the shape, and the usage trace turns a visual complaint into a precise
edit. No glue code — the model's output *is* the import format, and the harness already
renders the import format.

## The three references

| Doc | Role |
|---|---|
| [Theme Token Map](THEME_TOKEN_MAP.md) | **the spec** — every legal `--evcc-*` key, its type and range |
| [Theme Token CSS-Usage Trace](THEME_TOKEN_USAGE.md) | **the targeting map** — which CSS property each token paints |
| [The import envelope](../frontend/theme-system.md#authoring-a-theme-json-by-hand) | **the output contract** — `{ name, colors, alpha, tokens }`; `alpha` composes onto `colors`, it does not replace it |

## The loop

1. **Prompt with the spec.** Hand the model a target — a description, a photo, a few hex
   swatches — plus the Token Map. It can't name a token that doesn't exist, so whatever it
   returns always loads — though a full import stores scalar values as-is (no range clamp),
   so a final check against each token's **Range** is worth it.
2. **It emits the envelope** — `{ name, colors, alpha, tokens }`, which *is* the import
   payload. No conversion step. The three buckets are **recombined, not concatenated**:
   `alpha["--evcc-x"]` is a 0–1 multiplier baked onto `colors["--evcc-x"]`, so a key in
   both buckets is normal and correct (it is what the editor's own opacity rail writes).
   Either form is fine — `colors` + `alpha`, or the composed 8-char hex in `tokens` — but
   an alpha on a key with **no** color in the same envelope, or on a non-hex base such as
   `rgb()` / `color-mix()`, has nothing to bake into and is dropped; the harness lists
   those keys as `unappliedAlpha` in its ingest report, so check it rather than reading
   `0 skipped` as an all-clear.
3. **Render it.** Run the export through the [render harness](../frontend/render-harness.md) (that
   doc covers how) — it recolors the real card and writes preview images. That's the eval,
   and a multimodal model can read the image back.
4. **Critique the image, fix by token.** This is where the usage trace pays off: look up the
   element that reads wrong, get the token that paints it, change that key — a precise edit
   instead of a guess. Re-render.
5. **Repeat** — usually locking surfaces and accent and moving only the flagged controls.
   Two or three passes.

## What it is (and isn't)

A workflow, not a feature. Nothing wires an AI to the card; you drive the loop. The pieces
were built for other reasons — self-documenting the tokens, catching drift, visual
regression — and happen to compose into a theme generator.

## A worked example

The gallery's **Painted Hills** theme was authored exactly this way: one landscape photo as
the prompt, three passes through the harness (mostly sharpening small-text contrast), then
submitted. Those passes are also the cautionary half of the story: the harness ingest used
to concatenate the buckets, so all twelve of that theme's `colors` + `alpha` pairs — every
text token included — rendered as the card's built-in defaults. The small-text contrast
was being tuned against a preview that was not showing the theme. Trust the loop, but read
the ingest report's `composed` / `unappliedAlpha` counts before trusting a pass. The provenance — the source image and the pass notes — is recorded in its
[merge commit](https://github.com/kingchddg901/Vacuum_Agent/commit/4026454b47664f70db955d38fec61d21442622c2),
and the result is live in the [theme gallery](https://kingchddg901.github.io/Vacuum_Agent/).
