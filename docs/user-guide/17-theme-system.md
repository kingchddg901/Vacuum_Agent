# Theme system

The card has a built-in **theme system** — per-card visual styling (colors,
typography, surfaces, floor textures, even the map companion) driven by design
tokens. It's separate from Home Assistant's own theme: a card theme changes only
this card, and HA global themes don't override it.

Everything lives in the card's **Theme** tab. This page is the tour; the deep,
token-by-token reference is [Theme system (advanced)](../advanced/05-theme-system.md),
and making your own is [Authoring a theme](../contributing/theme-authoring.md).

## Picking a theme

The Theme tab opens on the **Themes** grid — your saved theme library, each shown
as a small preview card. Click one to apply it; the active theme gets an
**Active** chip. That's the whole interaction — themes apply live, with no save
step needed just to *switch*.

The card ships with several built-in themes (including **Colorblind Safe** and
**High Contrast**), and you grow the library by importing themes or building your
own.

## This device, or everywhere

By default a theme is **shared**: the library, your edits, and which theme is
*active* all live in the integration, so every device that views this vacuum's
card sees the same one. Switch the active theme on your laptop and the wall
tablet follows.

Sometimes you don't want that. A **Theme mode** row at the top of the Themes tab
lets each browser opt out:

- **Follow system** *(default)* — show whatever theme is active in the backend.
- **This device only** — pin a theme just for this browser and ignore later
  changes to the active one.

That's how one kiosk can sit on **High Contrast** while your phone stays on
something compact, all viewing the same vacuum. Once you've pinned a theme, two
buttons manage it: **Use everywhere** promotes your pick to the shared active
theme (and drops the local pin, so this device goes back to following), and
**Clear device override** returns this browser to *Follow system*.

The line to remember: **theme edits are shared; only the selection is local.**
Editing, saving, or importing while pinned still changes the shared library —
only *which theme this browser displays* stays on this device. The full behavior,
including how a pin to a since-deleted theme safely falls back, is in
[Per-device theme selection](../advanced/05-theme-system.md#per-device-theme-selection).

## Finding a theme

Once your library grows, the Themes tab has a **filter bar** and a **search box**
above the grid:

- **Search** matches a theme's name and its tags.
- **Filters** opens facet rows — Mode (dark / light), Accent, Contrast, Access,
  **Best for**, Source, and more. Click chips to narrow; it's *OR within a row*
  and *AND across rows*. Only chips that match a theme actually in your library
  appear, so the bar never offers a dead end.

The same facets power the public gallery, so a filter you learn here works there
too. A **Browse gallery ↗** link in the bar opens the gallery to see what others
have made — see [Sharing themes](15-sharing-themes.md).

## Colorblind basics

If color-vision deficiency makes statuses hard to tell apart, switch to the
built-in **Colorblind Safe** theme — it keeps the four status colors (success,
warning, error, info) distinct, and that separation is *verified* by simulation,
not eyeballed. (The theme also restyles the muted color, but the verification
gate covers the four status semantics.)

Two things worth knowing when you're choosing one:

- The **Colorblind Safe badge is earned, not claimed.** Any theme can carry it,
  but only if it actually passes the check — so filtering for it is meaningful.
- The **Best for** filter narrows the grid to safe themes tuned for the vision
  type they handle best — **red-green** or **blue-yellow** — so you can find one
  tuned for yours.

And color is never the only cue: status badges also carry distinct shapes that
read in pure grayscale. The full accessibility guide is
[Accessibility](14-accessibility.md).

## Import, export, and sharing

The Theme tab's footer has four transport buttons:

- **Export** / **Import** — open a small JSON window to copy a theme out of, or
  paste one into (quick and one-session).
- **Download** / **Upload** — save a theme to, or load one from, a `.json` file
  (backups, sharing as a file attachment, moving between Home Assistant installs).

A downloaded theme is a plain file with no reference to your rooms or vacuum, so
it loads cleanly anywhere. The mechanics — and the floor-only "just my marble"
option — are in [Import and export](../advanced/05-theme-system.md#import-and-export).

To pull a theme from, or publish one to, the **public gallery**, see
[Sharing themes](15-sharing-themes.md).

## Making your own

Two tabs beside Themes — **Palette** (four headline tokens) and **Tokens**
(everything else) — let you build a theme from any starting point and save it.
The token editor itself is documented in the
[advanced theme reference](../advanced/05-theme-system.md).

When you want to make something to keep or share,
[Authoring a theme](../contributing/theme-authoring.md) walks through the
build-in-card, by-hand, and AI paths — and what separates a good theme from a
half-finished one.
