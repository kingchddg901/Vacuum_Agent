/**
 * WAVE 4 — SHAPE-MARK GRAYSCALE DISTINGUISHABILITY
 * The six per-state marks must be distinct in FLAT GRAYSCALE at dot
 * size — that single property covers monochromacy AND every CVD type,
 * and it's what disambiguates warn from likely (which share a color).
 *
 * Each mark is rasterised grey-on-white at dot size, then every pair is
 * compared by the fraction of pixels whose luma differs. The worst pair
 * must clear the floor. We also require the safety-critical ok(✓)↔
 * outlier(✕) pair to clear a higher bar — it's the good-vs-bad cue.
 *
 * Marks come from the bundle (window.__evcc.badgeMarks), the same
 * src/renderers/badge-marks.js the card ships. Pure shape test (no card
 * render, no committed baseline) → runs everywhere, not gated to CI.
 */
import { test, expect } from "@playwright/test";
import { mountHarness } from "../lib/mount-page.mjs";

const SIZE = 20;             // px raster — near real badge/dot mark size
const LUMA_EPS = 32;         // per-pixel luma delta (of 255) to count as "different"
const FLOOR = 0.12;          // min fraction of pixels that must differ between any pair
const CRITICAL_FLOOR = 0.20; // ok↔outlier must clear more — it's the good/bad cue

test("the six state marks are distinguishable in flat grayscale at dot size", async ({ page }) => {
  await mountHarness(page);

  const matrix = await page.evaluate(
    async ({ size, eps }) => {
      const paths = window.__evcc.badgeMarks;
      const viewBox = window.__evcc.markViewBox;

      const raster = (inner) =>
        new Promise((resolve) => {
          const svg =
            `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" ` +
            `viewBox="${viewBox}">${inner.replaceAll("currentColor", "#808080")}</svg>`;
          const img = new Image();
          img.onload = () => {
            const cv = document.createElement("canvas");
            cv.width = size; cv.height = size;
            const ctx = cv.getContext("2d");
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, size, size);
            ctx.drawImage(img, 0, 0, size, size);
            const d = ctx.getImageData(0, 0, size, size).data;
            const luma = new Array(size * size);
            for (let i = 0; i < luma.length; i++) {
              luma[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
            }
            resolve(luma);
          };
          img.src = "data:image/svg+xml," + encodeURIComponent(svg);
        });

      const keys = Object.keys(paths);
      const lumas = {};
      for (const k of keys) lumas[k] = await raster(paths[k]);

      const out = {};
      for (let i = 0; i < keys.length; i++) {
        for (let j = i + 1; j < keys.length; j++) {
          const a = lumas[keys[i]], b = lumas[keys[j]];
          let diff = 0;
          for (let p = 0; p < a.length; p++) if (Math.abs(a[p] - b[p]) > eps) diff++;
          out[`${keys[i]}-${keys[j]}`] = diff / a.length;
        }
      }
      return out;
    },
    { size: SIZE, eps: LUMA_EPS },
  );

  // PIN THE SET, not just the pairs. The matrix is derived from
  // Object.keys(BADGE_MARK_PATHS), so without this the test asserts a property
  // of "every pair of whatever happens to exist" — a SMALLER set is a strictly
  // easier gate. Deleting `warn` and `likely` (the pair the header calls the
  // whole point, since they deliberately share the same orange) drops the matrix
  // from 15 pairs to 6, every survivor still clears FLOOR, "ok-outlier" still
  // exists so the critical assert passes, and the suite goes green while the card
  // renders no mark for two states.
  const MARKS = ["ok", "outlier", "warn", "likely", "excluded", "baseline"];
  const present = await page.evaluate(() => Object.keys(window.__evcc.badgeMarks).sort());
  expect(present, "the shipped mark set changed — update MARKS and re-verify every pair clears the floor")
    .toEqual([...MARKS].sort());
  // n*(n-1)/2 — pinned so a key that is present-but-unrasterised cannot shrink it.
  expect(Object.keys(matrix).length, "pair matrix is not the full 6-choose-2").toBe(15);

  const sorted = Object.entries(matrix).sort((a, b) => a[1] - b[1]);
  console.log(`\nflat-grayscale shape distinguishability @ ${SIZE}px (fraction of pixels differing):`);
  for (const [pair, frac] of sorted) {
    console.log(`  ${pair.padEnd(20)} ${(frac * 100).toFixed(1)}%${frac < FLOOR ? "  *" : ""}`);
  }
  const [worstPair, worstFrac] = sorted[0];
  console.log(`worst: ${worstPair} = ${(worstFrac * 100).toFixed(1)}%  (floor ${FLOOR * 100}%)`);

  expect(worstFrac, `marks too similar in grayscale: ${worstPair}`).toBeGreaterThanOrEqual(FLOOR);
  expect(
    matrix["ok-outlier"],
    "safety-critical ok(check)<->outlier(cross) must be strongly distinct in grayscale",
  ).toBeGreaterThanOrEqual(CRITICAL_FLOOR);
});
