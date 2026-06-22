/**
 * Tests for the .js -> descriptor converter. Pure (no browser) — runs the real
 * bundled raccoon.js through it. Run: node --test scripts/animal-js-to-descriptor.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { convertModule } from "./animal-js-to-descriptor.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const RACCOON = readFileSync(
  resolve(HERE, "../custom_components/eufy_vacuum/frontend/animal-svg/animals/raccoon.js"),
  "utf8",
);

test("[JS2D-1] resolves interpolations, single-quotes attrs, preserves colors/classes", () => {
  const r = convertModule(RACCOON, { id: "raccoon-x", license: "CC-BY-4.0" });
  assert.equal(r.ok, true, r.error);
  const a = r.envelope.animal;
  assert.equal(a.id, "raccoon-x");
  assert.equal(a.name, "Raccoon");
  assert.equal(a.type, "quadruped");
  assert.equal(a.license, "CC-BY-4.0");
  assert.equal(a.colors["--animal-fur"], "0 0% 40%");
  assert.match(a.parts.body, /hsl\(var\(--animal-fur\)\)/); // ${FUR} resolved
  assert.ok(!a.parts.body.includes("${"), "no unresolved interpolation");
  assert.ok(!a.parts.body.includes('"'), "double quotes converted to single");
  assert.match(a.parts.frontLeftLeg, /class='rac-fl-lower'/); // leg class preserved
  assert.equal(r.envelope.kind, "animal");
});

test("[JS2D-2] defaults id/name from the register call", () => {
  const r = convertModule(RACCOON);
  assert.equal(r.ok, true);
  assert.equal(r.envelope.animal.id, "raccoon");
  assert.equal(r.envelope.animal.license, "CC-BY-4.0"); // default
});

test("[JS2D-3] procedural (custom) modules are refused", () => {
  const r = convertModule("(function(){ AnimalSVG.register('x', { type:'custom', render: function(){} }); })()");
  assert.equal(r.ok, false);
  assert.match(r.error, /custom/i);
});

test("[JS2D-4] a non-animal source is refused", () => {
  assert.equal(convertModule("var x = 1;").ok, false);
  assert.equal(convertModule("this is not js (((").ok, false);
});
