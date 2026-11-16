/**
 * THE TOKEN WRITER, alone.
 *
 * Split out of styles/index.js 2026-11-16. That module imports every stylesheet in the
 * project, so importing the writer from there cost a measured +443,485 bytes of bundle --
 * irrelevant to the panel, which needs the stylesheets regardless, and fatal to a
 * dashboard card that only wants to paint CSS variables onto a host. From here the same
 * writer costs +18 bytes, because THEME_TOKEN_REGISTRY is already in that bundle.
 *
 * MOVED, NOT COPIED. A second implementation of the write loop is exactly the replica
 * shape this tree keeps paying for; styles/index.js re-exports these so nothing that
 * imported them before had to change.
 */

import { THEME_TOKEN_REGISTRY } from "../theme-tokens/index.js";

/**
 * ANIMAL TOKENS ARE HSL COMPONENTS, NOT COLOURS.
 *
 * The animal SVGs consume every one of their variables inside hsl():
 *
 *   default:   "--animal-fur": "0 0% 7%"
 *   consumed:  fill="hsl(var(--animal-fur))"          332 uses, 332 wrapped
 *
 * But the theme system stores every colour token as 8-digit hex
 * (theme-tokens/flatten.js:hexWithAlpha), so setting Fur to yellow at 88% produced
 * `fill="hsl(#e8e800e0)"` — invalid CSS. An invalid fill falls back to SVG's
 * initial value, which is BLACK. So ANY animal colour a user set turned that
 * part of the animal black, while untouched animals looked correct because
 * their built-in triplets were still in play. That reads as "I broke my
 * theme", which is how it was reported.
 *
 * Converted here, at the write to the DOM, rather than in resolvedTheme():
 * the editor's swatch reads the hex bucket, and the export envelope stores
 * hex, so both keep working unchanged. Nothing outside the animal-svg module
 * consumes --evcc-animal-*, so no other consumer can be surprised by the
 * different shape.
 *
 * Exported for the unit test — the conversion is pure and worth pinning.
 *
 * @param {string} hex "#rrggbb" or "#rrggbbaa"
 * @returns {string|null} "H S% L%" / "H S% L% / A", or null if not hex
 */
export function animalHslComponents(hex) {
  const m = /^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$/.exec(String(hex || "").trim());
  if (!m) return null;

  const int = parseInt(m[1], 16);
  const r = ((int >> 16) & 255) / 255;
  const g = ((int >> 8) & 255) / 255;
  const b = (int & 255) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;

  let h = 0;
  let s = 0;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }

  const round = (n) => Math.round(n * 10) / 10;
  const base = `${round(h)} ${round(s * 100)}% ${round(l * 100)}%`;

  // Alpha rides along as hsl()'s slash syntax rather than being dropped —
  // the opacity slider is half of what this editor's colour row does.
  if (m[2] === undefined) return base;
  const a = parseInt(m[2], 16) / 255;
  // Two decimals so the emitted alpha reads as the percentage the slider
  // showed (0xe0 -> 0.88, not 0.878) — round() above is one decimal and is
  // for the H/S/L components.
  return a >= 1 ? base : `${base} / ${Math.round(a * 100) / 100}`;
}

/**
 * Stamp `data-evcc-scheme="light"|"dark"` on a themed host from the RESOLVED base colour.
 *
 * ISSUE #65. Two different light signals shipped and they disagree:
 *   - the card had NONE, so every tint assumed a dark base;
 *   - modal-host/modals/room-rules branch on `@media (prefers-color-scheme: light)`,
 *     which is the OPERATING SYSTEM's preference, not Home Assistant's theme.
 * A user on an HA light theme with a dark OS gets dark-branch modals over a light card,
 * and the reporter's "follow HA theme" never triggers that branch at all. The OS cannot
 * know which HA theme is active, so it was never the right signal.
 *
 * The honest signal is the colour we actually render on. `--evcc-surface-base` already
 * resolves it (`var(--card-background-color, #1c2127)`), so measure THAT and let CSS key
 * off the answer.
 *
 * WHY A PROBE ELEMENT AND NOT A PARSER. Reading the custom property gives the DECLARED
 * string -- `#fff`, `rgb()`, `color(srgb …)`, or a var() chain -- and hand-parsing it is
 * how this work already produced two wrong answers: a `color(srgb 0.87 …)` read as 0-255
 * made every fixed panel measure as near-black, and a `#1c1c1c` with no parseable decimals
 * inflated the dark contrast figures. Painting the colour on a throwaway node and reading
 * `backgroundColor` back hands the parsing to the browser, which cannot get it wrong. The
 * 0-1 branch below is kept anyway, because `color()` serialisation is exactly the case
 * that already bit twice and a comment is not a guard.
 */
function syncColourScheme(host) {
  try {
    if (!host || typeof document === "undefined") return;
    const probe = document.createElement("span");
    probe.setAttribute("aria-hidden", "true");
    /* rtl-ignore — this is an off-screen parking spot for a 0x0 measurement node,
       not layout. There is no inline-start equivalent that is off-screen in BOTH
       directions, and a logical property here would park the probe ON SCREEN in RTL. */
    probe.style.cssText =
      "position:fixed;left:-9999px;top:0;width:0;height:0;pointer-events:none;" + /* rtl-ignore */
      "background-color:var(--evcc-surface-base, var(--card-background-color, #1c2127))";
    const mount = host.shadowRoot ?? host;
    mount.appendChild(probe);
    const raw = getComputedStyle(probe).backgroundColor;
    probe.remove();
    const n = String(raw).match(/[\d.]+/g);
    if (!n || n.length < 3) return;
    const scale = String(raw).startsWith("color(") ? 255 : 1;
    const [r, g, b] = n.slice(0, 3).map((v) => Number(v) * scale);
    if (![r, g, b].every(Number.isFinite)) return;
    const lin = (v) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    // Mid-grey splits it. A base at exactly 0.5 is a coin toss either way, and
    // `!(L > 0.5)` rather than `L <= 0.5` so a NaN that slipped the guard lands on
    // "dark" -- the value that ships today -- instead of flipping every install.
    // applyThemeToCard runs at the top of EVERY _render (main.js), which is what keeps
    // this tracking a live HA theme switch -- but it also means this runs constantly.
    // Writing the attribute unconditionally would invalidate style for the whole shadow
    // subtree on every render for a value that almost never changes, so only write on a
    // real transition.
    const next = !(L > 0.5) ? "dark" : "light";
    if (host.getAttribute("data-evcc-scheme") !== next) {
      host.setAttribute("data-evcc-scheme", next);
    }
  } catch (_) { /* a themed host that cannot be measured keeps whatever it has */ }
}

export function applyDynamicTheme(card, resolvedTheme) {
  if (!card || !resolvedTheme) return;

  const { tokens } = resolvedTheme;
  const host = card;

  // anchor: CN344YSE
  THEME_TOKEN_REGISTRY.forEach((token) => {
    if (!Object.prototype.hasOwnProperty.call(tokens, token.key) || tokens[token.key] === null || tokens[token.key] === undefined || tokens[token.key] === "") {
      host.style.removeProperty(token.key);
    }
  });

  Object.entries(tokens).forEach(([property, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      // See animalHslComponents: these are consumed as bare hsl() components,
      // so a hex value here renders the animal black.
      const asComponents = property.startsWith("--evcc-animal-")
        ? animalHslComponents(value)
        : null;
      host.style.setProperty(property, asComponents ?? value);
    }
  });

  // Re-measure AFTER the token layer lands: a theme may set --evcc-surface-base
  // itself, so the scheme has to be read from the post-apply state, not the pre.
  syncColourScheme(host);
}
