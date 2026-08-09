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
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mountHarness } from "../lib/mount-page.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));

// Semantic tokens with no distinct colored-state surface in the
// current tabs. Each MUST carry a reason. A new token is NOT
// auto-exempt — it fails until claimed by a gallery or listed here.
const ALLOWLIST = {
  "--evcc-status-cleaning-bg": "status pill variant not surfaced by the gallery tabs",
  "--evcc-status-cleaning-border": "status pill variant not surfaced by the gallery tabs",
  "--evcc-status-cleaning-text": "status pill variant not surfaced by the gallery tabs",
  "--evcc-learning-reanchor-border": "re-anchor learning UI state not exercised by the active-job fixture",
  "--evcc-learning-reanchor-highlight": "re-anchor learning UI state not exercised by the active-job fixture",
  // R2-DEAD-2. The mapping-badges entry was this token's ONLY claimant and its view
  // (mapping_review) no longer exists in the card. The token is still live — external
  // jobs' suggested-room chip, the room-access modal, setup, theme preview, the job
  // summary — but none of those surfaces is a gallery case, so nothing renders it today.
  // Deliberately allowlisted rather than re-claimed: the obvious candidate
  // (external-wizard-step2) is SKIPPED by the visual spec, so a claim there would assert
  // coverage that never renders in CI — the same "declaration reads as coverage" trap
  // this gate exists to catch. Claim it properly when a sem-info surface gets a real
  // gallery entry.
  "--evcc-sem-info": "sole claimant (mapping-badges) removed with the deleted mapping_review view; no current gallery case renders a sem-info surface",
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


/* =========================================================
   The harness's AnimalSVG stub must mirror what ships
   ========================================================= */

test("the AnimalSVG stub lists exactly the animals that ship", async ({ page }) => {
  // src/renderers/rooms.js reads window.AnimalSVG directly at render time, so the
  // harness stubs it. The stub is a HAND-KEPT MIRROR of a shipped list, which is the
  // shape that always drifts: it listed five while seven shipped, so every harness
  // render of the mascot picker under-represented the product and nothing said so.
  //
  // Compared against the shipped index rather than a second hardcoded list here —
  // a gate that mirrors the mirror would drift in exactly the same way.
  const shipped = JSON.parse(readFileSync(
    join(HERE, "../../custom_components/eufy_vacuum/frontend/animal-svg/animals/index.json"),
    "utf8",
  )).map((f) => f.replace(/\.js$/, "")).sort();

  await mountHarness(page);
  const stubbed = (await page.evaluate(() => window.AnimalSVG?.list?.() ?? [])).slice().sort();

  expect(stubbed.length, "the stub returned nothing — AnimalSVG is not installed").toBeGreaterThan(0);
  expect(stubbed).toEqual(shipped);
});
