/**
 * WAVE 4 — LIVE CVD GATE
 * Applies the shipped cvd-safe bundle to the REAL rendered card, reads
 * the colors the browser resolves for each semantic group (proving the
 * 5-override cascade actually resolves on the card, not just the
 * canonical hexes), and asserts all 10 group pairs separate by
 * ΔE2000 ≥ 15 under Machado protan/deutan + Brettel tritan. The full
 * matrix is printed for the CI artifact.
 *
 * Deterministic (computed styles + color math, no pixels) → runs
 * everywhere, not gated to CI.
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";
import cvdSafe from "../bundles/cvd-safe.mjs";
import { separationMatrix, printReport, GROUP_KEYS } from "../cvd/report.mjs";
import { parseColor, composite } from "../cvd/color.mjs";

const GROUP_TOKEN = {
  success: "--evcc-sem-success",
  warning: "--evcc-sem-warning",
  error: "--evcc-sem-error",
  info: "--evcc-sem-info",
  muted: "--evcc-text-muted",
};

test("cvd-safe theme separates every semantic group under protan/deutan/tritan", async ({ page }) => {
  await mountHarness(page);

  const probe = await page.evaluate(({ bundle, groupToken }) => {
    // Apply the bundle to the real card (sets --evcc-* inline on the host).
    window.__evcc.render("mapping_review", { bundle });
    const host = document.getElementById("evcc-host");
    const el = document.createElement("span");
    host.shadowRoot.appendChild(el); // inherits the host's custom properties
    const resolve = (tok) => {
      el.style.color = `var(${tok})`;
      return getComputedStyle(el).color;
    };
    const groups = {};
    for (const [g, t] of Object.entries(groupToken)) groups[g] = resolve(t);
    const surface = resolve("--evcc-surface-panel");
    // Cascade proof: derived tokens must follow the sem-* overrides.
    const cascade = {
      colorError: resolve("--evcc-color-error"),
      semError: resolve("--evcc-sem-error"),
      confHigh: resolve("--evcc-conf-high"),
      semSuccess: resolve("--evcc-sem-success"),
    };
    el.remove();
    return { groups, surface, cascade };
  }, { bundle: cvdSafe, groupToken: GROUP_TOKEN });

  // Resolve each group to an opaque rgb (composite alpha over the panel).
  const bg = parseColor(probe.surface);
  const rgb = {};
  for (const g of GROUP_KEYS) {
    const c = parseColor(probe.groups[g]);
    rgb[g] = c[3] < 1 ? composite(c, bg) : [c[0], c[1], c[2]];
  }

  // The 5-override cascade resolves on the rendered card.
  expect(probe.cascade.colorError, "--evcc-color-error should cascade from --evcc-sem-error")
    .toBe(probe.cascade.semError);
  expect(probe.cascade.confHigh, "--evcc-conf-high should cascade from --evcc-sem-success")
    .toBe(probe.cascade.semSuccess);

  // 30-pair separation matrix (printed for the CI artifact), then the gate.
  const pass = printReport("cvd-safe (live, as rendered)", rgb);
  const { worst } = separationMatrix(rgb);
  expect(
    pass,
    `cvd-safe below ΔE floor — worst per sim: ` +
      Object.entries(worst).map(([s, w]) => `${s} ${w.pair}=${w.dE.toFixed(1)}`).join(", "),
  ).toBe(true);
});
