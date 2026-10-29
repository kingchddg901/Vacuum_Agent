/**
 * Tests for the fork-PR gate. Needs a Playwright browser (the descriptor checks
 * re-sanitise); run in the pinned image.
 *
 * APR-1 exercises the REAL committed Fox, proving the bundled animal is a clean,
 * faithful descriptor→module pair (a good regression guard on the fox itself).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { checkAnimalPr, indexProblems } from "./check-animal-pr.mjs";

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

/* ---------------------------------------------------- the served roster (index.json)
 *
 * animals/index.json is the one file under animal-svg/ a submission may touch. It is
 * TRACKED because it has to be in the release zip — ignored, it 404'd after every
 * card-only HACS update and the mascot stayed absent until the next restart — so adding
 * an animal necessarily updates it, and a PR that cannot touch it cannot be made to pass.
 * These pin both halves of the price of allowing it.
 */

test("[APR-8] the served roster may be touched — it is not framework", async () => {
  const r = await checkAnimalPr([
    FOX_JSON,
    FOX_JS,
    "custom_components/eufy_vacuum/frontend/animal-svg/animals/index.json",
  ]);
  assert.equal(r.ok, true, JSON.stringify(r.problems, null, 2));
  assert.doesNotMatch(r.problems.join("\n"), /framework/i,
    "index.json must not be classified as a framework edit, or an animal PR can never pass");
});

test("[APR-9] a module the roster does not list is rejected, actionably", async () => {
  const r = await checkAnimalPr(["custom_components/eufy_vacuum/frontend/animal-svg/animals/wolf.js"]);
  assert.equal(r.ok, false);
  // The orphan check fires too; this asserts the ROSTER problem specifically, and that
  // the message says what to do — the contributor cannot guess this one.
  assert.match(r.problems.join("\n"), /not listed in animals\/index\.json/);
  assert.match(r.problems.join("\n"), /regenerate it/);
});

test("[APR-10] roster entries must be bare <id>.js names", () => {
  // Pure, so the hostile shapes are reachable without mutating a tracked file.
  const traversal = indexProblems(["cat.js", "../../../etc/passwd.js"]);
  assert.equal(traversal.length, 1);
  assert.match(traversal[0], /not bare/);
  assert.match(indexProblems(["sub/dir.js"])[0], /not bare/, "a path separator is not a name");
  assert.match(indexProblems(["cat.json"])[0], /not bare/, "only .js modules are loadable");
  assert.match(indexProblems([42])[0], /not bare/, "a non-string entry is not a name");
  assert.match(indexProblems({ cat: "cat.js" })[0], /must be a JSON array/);
  assert.match(indexProblems(null)[0], /must be a JSON array/);
  // And the clean case really is clean, or the assertions above prove nothing.
  assert.deepEqual(indexProblems(["cat.js", "dog-two.js"]), []);
  assert.deepEqual(indexProblems(["cat.js"], ["cat"]), []);
});
