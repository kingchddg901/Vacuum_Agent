# Accessibility

A short guide to the card's accessibility features. The deeper theme mechanics
are in [Theme system](../advanced/05-theme-system.md); how the colorblind palette
is validated is in [dev/27-render-harness](../dev/27-render-harness.md).

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

## Other niceties

- **Keyboard:** press **Esc** to close any open modal.
- **High Contrast** theme: if you want maximum contrast rather than colorblind
  tuning specifically, the **High Contrast** preset is also available in the
  Theme tab.
