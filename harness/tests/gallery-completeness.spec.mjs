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
import { readdirSync } from "node:fs";
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
  // Compared against what SHIPS rather than a second hardcoded list here — a gate
  // that mirrors the mirror would drift in exactly the same way.
  //
  // Read from the animals/ DIRECTORY, not animals/index.json. That index is a runtime
  // artifact: manifest.js says the integration "generates animals/index.json at
  // startup from whatever .js files exist", and .gitignore:58 ignores it. So the file
  // exists on a box that has booted HA and nowhere else — this test could never pass
  // on a runner, and nothing noticed because gallery-completeness was not wired into
  // CI at all. The directory is the same source of truth the startup scan uses, and
  // it is tracked.
  const shipped = readdirSync(
    join(HERE, "../../custom_components/eufy_vacuum/frontend/animal-svg/animals"),
  ).filter((f) => f.endsWith(".js")).map((f) => f.replace(/\.js$/, "")).sort();

  await mountHarness(page);
  const stubbed = (await page.evaluate(() => window.AnimalSVG?.list?.() ?? [])).slice().sort();

  expect(stubbed.length, "the stub returned nothing — AnimalSVG is not installed").toBeGreaterThan(0);
  expect(stubbed).toEqual(shipped);
});


/**
 * [FLOOR-1] Every floor material in the registry actually RENDERS in the gallery.
 *
 * The expectation is read from the registry node-side; the observation is read off
 * the DOM. That split is deliberate and is the lesson the --evcc-sem-info allowlist
 * entry above records: a fixture that merely DECLARES a material would assert
 * coverage that never renders. Here a material only counts when its texture layer
 * exists in the rendered tree with at least one composited mask span.
 *
 * Goes red when someone adds an eighth material to FLOOR_TEXTURE_REGISTRY without a
 * card, and when the mask route stops serving images. Both arms were verified by
 * ablation; the span-count arm alone was NOT enough -- see the response-watch note
 * inside the test for why markup cannot see an unroutable mask.
 */
test("[FLOOR-1] every registry floor material renders a textured card", async ({ page }) => {
  // Watch the mask responses BEFORE mounting. A layer's <span> is emitted whether or
  // not its mask URL resolves, so the markup alone cannot tell a composited material
  // from an untextured one -- ablating the texture route leaves this test green if it
  // only counts spans. The harness catch-all answers an unrouted request with the page
  // HTML, so the tell is the CONTENT TYPE, not the status code.
  const maskResponses = [];
  page.on("response", (res) => {
    if (!res.url().includes("/eufy_vacuum/textures/")) return;
    maskResponses.push({ url: res.url(), type: res.headers()["content-type"] || "" });
  });

  await mountHarness(page);

  const rendered = await page.evaluate(() => {
    const res = window.__evcc.renderGallery("floor-materials", { freeze: true, width: 520 });
    return {
      ok: Boolean(res && res.ok),
      error: res && res.error,
      // The EXPECTATION side, read from the registry. The observation below is read
      // off the rendered tree, so the two come from different places -- which is what
      // makes this a gate rather than a fixture restating itself.
      registryTypes: window.__evcc.floorTypes,
    };
  });

  expect(rendered.ok, `floor-materials gallery failed to render: ${rendered.error}`).toBe(true);

  // Locators, NOT document.querySelectorAll: the card renders into a shadow root, and
  // a raw querySelectorAll silently returns nothing across that boundary -- an empty
  // result that reads exactly like "no materials rendered".
  const layers = page.locator(".evcc-room-texture-layer");
  const painted = new Set();
  const unpainted = [];
  for (let i = 0; i < (await layers.count()); i += 1) {
    const el = layers.nth(i);
    const floor = await el.getAttribute("data-floor");
    // A layer with zero mask spans is a card that rendered but painted NOTHING -- the
    // shape the unroutable-mask era produced. It must not count as coverage.
    if (await el.locator(".evcc-ftx-layer").count()) painted.add(floor);
    else unpainted.push(floor);
  }

  const missing = rendered.registryTypes
    .map((n) => n.replace(/-/g, "_"))
    .filter((type) => !painted.has(type));

  expect(
    missing,
    `Floor materials in FLOOR_TEXTURE_REGISTRY with no rendered texture layer in the ` +
      `floor-materials gallery (add a card in harness/fixtures/gallery.js, or check that ` +
      `serveFloorTextures can reach its mask PNGs): ${missing.join(", ")}`,
  ).toEqual([]);

  expect(unpainted, `floor cards rendered with no mask spans: ${unpainted.join(", ")}`).toEqual([]);

  // Every material must have actually FETCHED a mask image. Zero requests means the
  // layers never asked; a non-image content type means something answered that was
  // not a mask (the unrouted case). Either way the board is showing flat colour.
  expect(maskResponses.length, "no floor mask images were requested at all").toBeGreaterThan(0);
  const notImages = maskResponses.filter((r) => !r.type.startsWith("image/"));
  expect(
    notImages.map((r) => `${r.url} -> ${r.type}`),
    "floor masks answered with a non-image content type (serveFloorTextures not routing?)",
  ).toEqual([]);
});
