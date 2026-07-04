# 14 — Accessibility

A short guide to the card's accessibility features. The deeper theme mechanics
are in [Theme system](../advanced/05-theme-system.md); how the colorblind palette
is validated is in [dev/27-render-harness](../dev/frontend/render-harness.md).

## Colorblind mode

If you have color-vision deficiency, switch to the built-in **Colorblind Safe**
theme: open the **Theme** tab and click its preset card (it applies immediately,
like any other theme).

What it changes: the card leans on color to signal status — success (green),
warning (amber), error (red), reference (blue), and muted (grey). In a typical
palette several of those collapse together for protan / deutan / tritan vision —
red and green especially. The Colorblind Safe palette retunes those five so they
stay clearly distinct under all three types of color blindness (it's verified
with simulation, not eyeballed), while keeping the card legible for everyone.

## Shapes, not just colors

Color is never the only cue. On the **Map Bounds** tab, each status badge also
carries a distinct shape so you can tell them apart without relying on color at
all:

| Badge | Shape | Meaning |
|---|:--:|---|
| OK | ✓ | enough confident runs |
| Likely | ◐ | a few runs — bounds are forming |
| No bounds | ! | nothing learned yet |
| Outlier | ✕ | a run that disagrees with the others |
| Excluded | – | a run you've removed from the bounds |
| Baseline | ◆ | the protected reference run |

These marks are **always on**, in every theme — the Colorblind Safe theme just
adds the matching color tuning on top. They're chosen to stay distinguishable
even in pure grayscale, so they also cover full color blindness (monochromacy).

!!! info "Only on models with CV map bounds"

    The **Map Bounds** tab — and the shaped status badges above — is a learned-bounds
    feature that appears on Eufy. Brands that track the current room natively
    (Roborock S6) don't build CV map bounds, so the tab is hidden there and these
    badges won't appear. All the color and Colorblind Safe guidance on this page
    is brand-agnostic and applies everywhere.

## The badge is earned, not claimed

Any theme can carry the **Colorblind Safe** badge — it is not reserved for the
built-in preset. But the badge is *verified*, never just asserted. An author can
ask for it, yet the card runs a real check and withholds the badge (with a
reason) unless the theme actually passes.

The check works on the four status colors — success, warning, error, and info —
and asks a simple question: *if you couldn't see color the way most people do,
could you still tell these four apart?* To answer it without guessing, the card:

1. simulates each status color under the three dichromacy types —
   deuteranopia, protanopia, and tritanopia — using the standard Machado (2009)
   matrices;
2. measures how far apart each pair of colors lands (in CIELab, the ΔE
   distance);
3. fails the theme if *any* pair of statuses collapses too close together under
   *any* of the three — below a fixed separation floor (`CVD_DELTA_E`, currently
   19, roughly "clearly different at a glance").

If even one pair would be hard to distinguish, the badge is withheld and the
result tells you exactly which pair, which vision type, and how close they
landed — so a theme author knows what to fix.

## "Best for" your kind of color vision

The filter bar groups vision types into two plain-language buckets, because
those are the terms people actually recognize:

- **red-green** — covers both deuteranopia and protanopia (the common type,
  affecting around 8% of men);
- **blue-yellow** — tritanopia (rare).

The buckets live in the filter because they're the words you'd search for. The
precise medical term stays available in the per-theme detail, so nothing is
dumbed away — the simpler label is just the front door. A red-green bucket is
deliberately conservative: since someone with red-green deficiency can't tell
which of the two subtypes they have, the bucket reports the tighter (worse) of
the two simulations.

A theme that passes the check is also tagged with the bucket it handles
*best* — its strongest vision type. That shows up in the **Best for** filter, so
you can narrow the gallery or the card's theme picker to, say, "Best for
red-green" and see the themes tuned most strongly for your own vision. Only
themes that have earned the Colorblind Safe badge carry a "Best for" tag.

## Other niceties

- **Keyboard:** press **Esc** to close any open modal.
- **High Contrast** theme: if you want maximum contrast rather than colorblind
  tuning specifically, the **High Contrast** preset is also available in the
  Theme tab.
