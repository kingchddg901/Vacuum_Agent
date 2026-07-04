# Authoring a theme

So you want to make a card theme — to keep, or to share in the
[gallery](../user-guide/15-sharing-themes.md). There are three ways to build one,
they all produce the **same thing** (a theme export — `{ name, colors, alpha,
tokens }`), and this page is about choosing a path and making the result *good*.

*Using* themes — picking, per-device, import/export — is covered in the
[Theme system user guide](../user-guide/17-theme-system.md); the token mechanics
are in the [advanced theme reference](../advanced/05-theme-system.md). This page
assumes you've read enough of those to know what a token is.

## Three ways to build one

### In the card (recommended)

Open the **Theme** tab, use the **Palette** tab for the four headline tokens
(accent, base surface, text, corner radius) and the **Tokens** tab for everything
else, watch the live preview, and save. This is the most accessible path — you
see every change immediately and you *can't* produce an invalid theme. Start from
an existing theme (it becomes your editable draft) rather than a blank slate. The
editor, and the Save-Changes / Save-as-New distinction, are in the
[advanced theme reference](../advanced/05-theme-system.md#saving-overwriting-and-managing-themes).

### By hand

The export is plain JSON and the
[Theme Token Map](../dev/reference/THEME_TOKEN_MAP.md) is its spec, so you *can*
write one in a text editor — take keys from the catalog, give each a legal value,
import. It's mechanical and rarely worth it over the editor, but it's there. The
full envelope, the `colors`/`alpha`-vs-`tokens` distinction, and the
"export-then-edit" shortcut are in
[Authoring a theme JSON by hand](../dev/frontend/theme-system.md#authoring-a-theme-json-by-hand).

### With an AI

You can hand the whole job to an assistant: give it the
[Token Map](../dev/reference/THEME_TOKEN_MAP.md) (the spec) and a target — a
description, a photo, a few swatches — it emits the envelope, you render it
through the harness, critique the image, and fix by token. Two or three passes.
Because the catalog bounds the keys — every key it names is a real token —
whatever it returns loads. (Out-of-range scalar *values* aren't auto-corrected on
a full import, so a final pass against each token's **Range** is worth it.) The full loop, why it
works, and a worked example — the gallery's **Painted Hills**, authored from one
landscape photo — are in
[Authoring themes with an AI](../dev/reference/ai-theme-authoring.md).

## What a "good theme" looks like

A theme that's pleasant to *you* is the only hard requirement. But if you mean to
share it, here's what separates a theme that lands from one that feels
half-finished. The gallery doesn't enforce most of this — a human reviews each
submission — but hitting these makes that review a yes.

### Status stays readable

The card uses color to signal state — success, warning, error, info — across
chips, badges, and alerts. Whatever palette you pick, those four have to stay
tellable apart. Best case they stay apart *under color blindness* too, which
earns the verified **Colorblind Safe** badge (the check simulates the three
dichromacy types and fails any theme where a status pair collapses). You don't
*have* to be colorblind-safe — but a theme where warning and error look identical
is a bug, not a style. See [Accessibility](../user-guide/14-accessibility.md).

### Text stays legible

The most common real defect is **small-text contrast** — body text or secondary
labels that wash out on your new surfaces. Check the dense tabs (Metrics,
Maintenance), not just a single room card. Painted Hills took three harness
passes, and nearly all of them were sharpening small text.

### Cover the whole card

A theme is more than an accent color. Any token you *don't* set falls through to
the card's built-in default — so a theme that only recolors the accent leaves
default surfaces, chips, and modals behind, and they may clash with it. Walk the
[token groups](../dev/reference/THEME_TOKEN_MAP.md) — surfaces, borders, chips,
room cards, status, modals, the map overlays — and the **floor textures** (marble
veins, wood, tile…), which keep reading as "default" if you restyle everything
around them and leave them untouched. The card's contextual preview and the
render harness both show these surfaces, so you can catch the ones you missed.

### Be coherent

Pick a palette, not a pile of colors. Surfaces should relate to each other and to
the accent; the floor textures and map companion should feel like the same room.
A theme reads as *designed* when nothing on the card looks borrowed from a
different one.

### Name and credit it honestly

Give it a real name, not "theme 3." If you share it, add your author credit — a
direct profile or project link (the [submission
policy](../user-guide/15-sharing-themes.md) explains what's accepted). Add **vibe
tags** that describe the mood (aurora, cozy, retro), but don't bother re-typing
facet words like "dark" or "blue": those are derived from your palette
automatically, and a hand-typed copy is ignored.

### Keep it portable

A theme carries **no** reference to your rooms, entities, or vacuum brand — it's
pure visual styling plus a little metadata (name, tags, credit). That's exactly
why one loads cleanly on anyone's install, so don't try to bolt anything else
into the envelope; the importer keeps only the visual tokens and that metadata
anyway.

## Sharing it

When it's good, publish it: in the gallery, click **+ Submit a theme**, paste
your **Download** export, and a bot tags it, verifies colorblind-safety, renders
a preview of the real card in your theme, and opens a pull request for a
maintainer to merge. The full walkthrough — and the optional credit / tag /
colorblind-claim fields — is in [Sharing themes](../user-guide/15-sharing-themes.md).
