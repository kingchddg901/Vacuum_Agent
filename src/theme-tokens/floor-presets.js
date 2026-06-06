/**
 * ============================================================
 * THEME TOKENS: BUILT-IN FLOOR PRESETS (MARBLE)
 * ============================================================
 *
 * PURPOSE
 * -------
 * Named, ready-to-apply MARBLE looks. Each preset is a SCOPED
 * theme envelope (scope:["marble"], same shape Download Floor
 * emits) that the card applies onto the ACTIVE theme via the
 * targeted-import path — it REPLACES the marble namespace, it is
 * NOT a standalone theme to switch to.
 *
 * AUTHORING NOTES
 * ---------------
 * - Colors are kept OPAQUE; vein subtlety is driven by the opacity
 *   tokens (vein-opacity master + per-tier offsets), so there is no
 *   alpha section to format and the look is fully token-controlled.
 * - Vein math is master + offset, clamped: effective tier opacity =
 *   clamp(0, vein-opacity + tier-offset, 1). The intents:
 *     Carrara   — minor-only  (major offset strongly negative)
 *     Portoro   — both tiers  (offsets near zero)
 *     Calacatta — major-forward (major up, minor down)
 * - These are STARTERS — refine in the editor, or Download Floor a
 *   tuned look to replace one.
 *
 * Imports clamp every value to the token ranges, so out-of-range
 * edits here can't invert behavior.
 *
 * ============================================================
 */

function _preset(id, name, tokens, colors) {
  return {
    id,
    name,
    envelope: {
      ok: true,
      version: 1,
      scope: ["marble"],
      name,
      theme: { name, tokens, colors, alpha: {} },
    },
  };
}

export const MARBLE_PRESETS = [

  // Carrara — soft white field, fine cool-grey MINOR veins; major nearly absent.
  _preset(
    "carrara",
    "Carrara",
    {
      "--evcc-floor-marble-opacity-card": 0.9,
      "--evcc-floor-marble-base-opacity": 0.97,
      "--evcc-floor-marble-micro-opacity": 0.45,
      "--evcc-floor-marble-vein-opacity": 0.5,
      "--evcc-floor-marble-vein-blur": 0.5,
      "--evcc-floor-marble-vein-major-opacity": -0.4,   // -> ~0.10 major (faint)
      "--evcc-floor-marble-vein-minor-opacity": 0.08,   // -> ~0.58 minor (prominent)
      "--evcc-floor-marble-vein-major-blur": 0,
      "--evcc-floor-marble-vein-minor-blur": 1.0,
      "--evcc-floor-marble-vein-minor-light": 0.05,
      "--evcc-floor-marble-vein-minor-chroma": 0.55,
      "--evcc-floor-marble-vein-minor-hue": 0,
    },
    {
      "--evcc-floor-marble-base": "#f4f3f0",
      "--evcc-floor-marble-micro": "#20201e",
      "--evcc-floor-marble-accent": "#9a9a98",
    },
  ),

  // Portoro — near-black field, bold GOLD veins, BOTH tiers present.
  _preset(
    "portoro",
    "Portoro",
    {
      "--evcc-floor-marble-opacity-card": 0.95,
      "--evcc-floor-marble-base-opacity": 1,
      "--evcc-floor-marble-micro-opacity": 0.4,
      "--evcc-floor-marble-vein-opacity": 0.85,
      "--evcc-floor-marble-vein-blur": 0.5,
      "--evcc-floor-marble-vein-major-opacity": 0,      // -> ~0.85 major
      "--evcc-floor-marble-vein-minor-opacity": -0.1,   // -> ~0.75 minor
      "--evcc-floor-marble-vein-major-blur": 0,
      "--evcc-floor-marble-vein-minor-blur": 1.0,
      "--evcc-floor-marble-vein-minor-light": 0.06,
      "--evcc-floor-marble-vein-minor-chroma": 0.7,
      "--evcc-floor-marble-vein-minor-hue": 4,
    },
    {
      "--evcc-floor-marble-base": "#14120e",
      "--evcc-floor-marble-micro": "#0a0908",
      "--evcc-floor-marble-accent": "#c9a24b",
    },
  ),

  // Calacatta — warm-white field, bold GOLD MAJOR veins, hazy subtle minor.
  _preset(
    "calacatta",
    "Calacatta",
    {
      "--evcc-floor-marble-opacity-card": 0.92,
      "--evcc-floor-marble-base-opacity": 0.97,
      "--evcc-floor-marble-micro-opacity": 0.4,
      "--evcc-floor-marble-vein-opacity": 0.7,
      "--evcc-floor-marble-vein-blur": 0.5,
      "--evcc-floor-marble-vein-major-opacity": 0.12,   // -> ~0.82 major (bold)
      "--evcc-floor-marble-vein-minor-opacity": -0.35,  // -> ~0.35 minor (subtle)
      "--evcc-floor-marble-vein-major-blur": 0,
      "--evcc-floor-marble-vein-minor-blur": 1.5,
      "--evcc-floor-marble-vein-minor-light": 0.08,
      "--evcc-floor-marble-vein-minor-chroma": 0.55,
      "--evcc-floor-marble-vein-minor-hue": 2,
    },
    {
      "--evcc-floor-marble-base": "#f3f1eb",
      "--evcc-floor-marble-micro": "#1c1a16",
      "--evcc-floor-marble-accent": "#c9a24b",
    },
  ),
];
