/**
 * Tests for the fork-PR gate. Needs a Playwright browser (the descriptor checks
 * re-sanitise); run in the pinned image.
 *
 * APR-1 exercises the REAL committed Fox, proving the bundled animal is a clean,
 * faithful descriptor→module pair (a good regression guard on the fox itself).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { checkAnimalPr } from "./check-animal-pr.mjs";

const FOX_JSON = "gallery/animals/fox.json";
const FOX_JS = "custom_components/eufy_vacuum/frontend/animal-svg/animals/fox.js";

test("[APR-1] the committed Fox passes the gate", async () => {
  const r = await checkAnimalPr([FOX_JSON, FOX_JS]);
  assert.equal(r.ok, true, JSON.stringify(r.problems, null, 2));
  assert.deepEqual(r.galleryIds, ["fox"]);
});

test("[APR-2] a framework edit is rejected", async () => {
  const r = await checkAnimalPr([
    FOX_JSON,
    FOX_JS,
    "custom_components/eufy_vacuum/frontend/animal-svg/animal-svg.js",
  ]);
  assert.equal(r.ok, false);
  assert.match(r.problems.join("\n"), /framework/i);
});

test("[APR-3] manifest.js edit is rejected too", async () => {
  const r = await checkAnimalPr(["custom_components/eufy_vacuum/frontend/animal-svg/manifest.js"]);
  assert.equal(r.ok, false);
  assert.match(r.problems.join("\n"), /framework/i);
});

test("[APR-4] an orphan generated module (no descriptor) is rejected", async () => {
  const r = await checkAnimalPr(["custom_components/eufy_vacuum/frontend/animal-svg/animals/wolf.js"]);
  assert.equal(r.ok, false);
  assert.match(r.problems.join("\n"), /without a descriptor/i);
});

test("[APR-5] a PR touching no animal files passes (nothing to check)", async () => {
  const r = await checkAnimalPr(["README.md", "src/state/map.js"]);
  assert.equal(r.ok, true);
  assert.deepEqual(r.galleryIds, []);
});

test("[APR-6] a first-party (src/) bundled animal + its .js passes the gate", async () => {
  const r = await checkAnimalPr([
    "custom_components/eufy_vacuum/frontend/animal-svg/src/cat.json",
    "custom_components/eufy_vacuum/frontend/animal-svg/animals/cat.js",
  ]);
  assert.equal(r.ok, true, JSON.stringify(r.problems, null, 2));
  assert.ok(r.galleryIds.includes("cat"));
});

test("[APR-7] the actual PR-14 shape (all bundled src + .js) passes", async () => {
  const changed = [];
  for (const id of ["cat", "dog", "raccoon", "mittens", "parrot"]) {
    changed.push(`custom_components/eufy_vacuum/frontend/animal-svg/src/${id}.json`);
    changed.push(`custom_components/eufy_vacuum/frontend/animal-svg/animals/${id}.js`);
  }
  const r = await checkAnimalPr(changed);
  assert.equal(r.ok, true, JSON.stringify(r.problems, null, 2));
});
