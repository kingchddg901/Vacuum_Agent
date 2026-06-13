/**
 * WAVE 2 — GALLERY COMPLETENESS
 * Every semantic-color token is represented by a gallery entry.
 *
 * The required set is the registry-derived semantic enum
 * (harness/semantic-tokens.js). A token counts as represented when a
 * gallery entry claims it in its `tokens` list. A token that is real
 * but has no colored-state surface to render is listed in ALLOWLIST
 * with a reason. Anything left over fails loudly — which is exactly
 * what happens when someone adds a colored state-token without a
 * fixture row.
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

// Semantic tokens with no distinct colored-state surface in the
// current tabs. Each MUST carry a reason. A new token is NOT
// auto-exempt — it fails until claimed by a gallery or listed here.
const ALLOWLIST = {
  "--evcc-status-cleaning-bg": "status pill variant not surfaced by the gallery tabs",
  "--evcc-status-cleaning-border": "status pill variant not surfaced by the gallery tabs",
  "--evcc-status-cleaning-text": "status pill variant not surfaced by the gallery tabs",
  "--evcc-learning-reanchor-border": "re-anchor learning UI state not exercised by the active-job fixture",
  "--evcc-learning-reanchor-highlight": "re-anchor learning UI state not exercised by the active-job fixture",
};

test("every semantic-color token is represented by a gallery entry", async ({ page }) => {
  await mountHarness(page);
  const { semanticTokens, gallery } = await page.evaluate(() => ({
    semanticTokens: window.__evcc.semanticTokens,
    gallery: window.__evcc.gallery,
  }));

  const claimed = new Set(gallery.flatMap((g) => g.tokens));
  const allow = new Set(Object.keys(ALLOWLIST));
  const uncovered = semanticTokens.filter((t) => !claimed.has(t) && !allow.has(t));

  expect(
    uncovered,
    `Semantic tokens with no gallery entry (claim them in harness/fixtures/gallery.js ` +
      `or add to ALLOWLIST with a reason):\n  ${uncovered.join("\n  ")}`,
  ).toEqual([]);

  // Hygiene: an allowlist entry that is no longer a semantic token
  // (renamed/removed) should be cleaned up.
  const enumSet = new Set(semanticTokens);
  const staleAllow = [...allow].filter((t) => !enumSet.has(t));
  expect(staleAllow, `stale ALLOWLIST entries (no longer semantic tokens):\n  ${staleAllow.join("\n  ")}`).toEqual([]);
});
