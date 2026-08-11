/**
 * THEME LIBRARY FIXTURE — a realistic, DERIVED token set for layout gating.
 *
 * WHY
 * ---
 * The theme editor was unmeasurable: `render()`'s stub state supplies no theme
 * data, so the editor body renders EMPTY and any layout probe reports a clean
 * shell having measured nothing (it did exactly that, greenly, before this
 * existed). The POPULATED @390 gate in i18n-layout.spec.mjs avoids that class of
 * hole by using real fixtures — theme had none.
 *
 * DERIVED, NOT AUTHORED
 * ---------------------
 * Every entry comes from THEME_TOKEN_REGISTRY, so this cannot drift from the real
 * token set: add a token to the registry and it appears here automatically. A
 * hand-copied dump would silently stop covering new groups.
 *
 * VALUES ARE DELIBERATELY UGLY
 * ----------------------------
 * Layout breaks on the LONGEST plausible value, not a tidy one. Live cards show
 * `color-mix(in srgb, var(--evcc-accent) 42%, transparent)` and
 * `var(--evcc-surface-raised)` inside the editor's value inputs — a fixture of
 * neat `#070808`s renders narrower than reality and UNDER-REPORTS overflow, which
 * is the failure mode this fixture exists to prevent. So colour tokens get a mix
 * of hex / var() / color-mix() by index, and text tokens get real font stacks.
 */
import { THEME_TOKEN_REGISTRY } from "../../src/theme-tokens/index.js";

/* Long-but-real value shapes, cycled by index so every group gets a spread of
   widths rather than one uniform (and uniformly narrow) case. */
const COLOR_SHAPES = [
  (i) => `#${((0x1a2b3c + i * 7919) & 0xffffff).toString(16).padStart(6, "0")}`,
  ()  => `var(--evcc-surface-raised)`,
  ()  => `color-mix(in srgb, var(--evcc-accent) 42%, transparent)`,
  ()  => `rgba(238, 243, 255, 0.62)`,
];
const TEXT_SHAPES = [
  () => `"Inter var", "SF Pro Text", system-ui, -apple-system, sans-serif`,
  () => `160ms cubic-bezier(0.22, 1, 0.36, 1)`,
  () => `0 2px 8px rgba(0, 0, 0, 0.35)`,
];

function valueFor(def, i) {
  const t = String(def?.type || "").toLowerCase();
  if (t === "number" || t === "size" || t === "motion" || t === "ratio") {
    // Numerics render in a 110-120px input; the slider row is the wide part.
    return String((i % 24) + 1);
  }
  if (t === "text") return TEXT_SHAPES[i % TEXT_SHAPES.length]();
  return COLOR_SHAPES[i % COLOR_SHAPES.length](i);
}

/**
 * One library theme carrying a value for EVERY registry token.
 * @param {{id?:string,name?:string}} [opts]
 */
export function makeThemeFixture({ id = "fixture_full", name = "Fixture Full" } = {}) {
  const tokens = {};
  const colors = {};
  const alpha = {};

  THEME_TOKEN_REGISTRY.forEach((def, i) => {
    const key = def?.key;
    if (!key) return;
    const v = valueFor(def, i);
    tokens[key] = v;
    // Mirror the export envelope's split: colours also land in colors/alpha so
    // the editor's swatch + opacity rail render populated rather than empty.
    if (typeof v === "string" && v.startsWith("#")) {
      colors[key] = v;
      alpha[key] = Number((0.4 + ((i % 6) * 0.1)).toFixed(2));
    }
  });

  return { id, name, tokens, colors, alpha };
}

/** The array shape `renderThemePresets` / `renderThemeEditor` expect. */
export function themeLibraryFixture() {
  return [
    makeThemeFixture({ id: "fixture_full", name: "Fixture Full" }),
    makeThemeFixture({ id: "fixture_alt", name: "Fixture Alt — a deliberately long theme name for the header" }),
  ];
}

/** Registry size at CALL time — the registry is populated lazily, so a
  * module-scope const would capture 0 on an early import. */
export function tokenCount() { return THEME_TOKEN_REGISTRY.length; }
