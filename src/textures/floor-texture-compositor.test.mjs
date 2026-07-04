// Unit tests for the floor-texture compositor — the pure mask×color×opacity math
// the map floor-texture view samples. White mask reveals the layer color over an
// opaque base; the result stays fully opaque (a floor is a solid surface).
// Run: node --test src/textures/floor-texture-compositor.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { compositeFloorTexture } from "./floor-texture-compositor.js";

const BASE = [10, 20, 30];
const RED = [200, 0, 0];
// A 2x2 tile => 4 texels.
const fill = (v) => [v, v, v, v];

function texel(res, i) {
  const o = i * 4;
  return [res.data[o], res.data[o + 1], res.data[o + 2], res.data[o + 3]];
}

test("[FTC-1] base-only (no layers) -> every texel is the opaque base", () => {
  const res = compositeFloorTexture(2, 2, BASE, []);
  assert.equal(res.width, 2);
  assert.equal(res.height, 2);
  for (let i = 0; i < 4; i++) assert.deepEqual(texel(res, i), [10, 20, 30, 255]);
});

test("[FTC-2] full-white mask, opacity 1 -> texel IS the layer color", () => {
  const res = compositeFloorTexture(2, 2, BASE, [{ lum: fill(255), color: RED, opacity: 1 }]);
  for (let i = 0; i < 4; i++) assert.deepEqual(texel(res, i), [200, 0, 0, 255]);
});

test("[FTC-3] black mask -> layer hidden, base shows through", () => {
  const res = compositeFloorTexture(2, 2, BASE, [{ lum: fill(0), color: RED, opacity: 1 }]);
  for (let i = 0; i < 4; i++) assert.deepEqual(texel(res, i), [10, 20, 30, 255]);
});

test("[FTC-4] mid-grey mask (128) -> ~halfway blend base<->layer", () => {
  const res = compositeFloorTexture(1, 1, BASE, [{ lum: [128], color: RED, opacity: 1 }]);
  const a = 128 / 255; // ~0.502
  const [r, g, b, al] = texel(res, 0);
  assert.ok(Math.abs(r - (200 * a + 10 * (1 - a))) <= 1);
  assert.ok(Math.abs(g - (0 * a + 20 * (1 - a))) <= 1);
  assert.ok(Math.abs(b - (0 * a + 30 * (1 - a))) <= 1);
  assert.equal(al, 255);
});

test("[FTC-5] opacity scales the reveal: white mask @ 0.5 -> halfway blend", () => {
  const res = compositeFloorTexture(1, 1, BASE, [{ lum: [255], color: RED, opacity: 0.5 }]);
  const [r, , , al] = texel(res, 0);
  assert.ok(Math.abs(r - (200 * 0.5 + 10 * 0.5)) <= 1);
  assert.equal(al, 255);
});

test("[FTC-6] layers stack bottom->top: a white top layer overrides a lower one", () => {
  const GREEN = [0, 180, 0];
  const res = compositeFloorTexture(1, 1, BASE, [
    { lum: [255], color: RED, opacity: 1 },   // bottom: paints red
    { lum: [255], color: GREEN, opacity: 1 }, // top: fully overrides -> green
  ]);
  assert.deepEqual(texel(res, 0), [0, 180, 0, 255]);
});

test("[FTC-7] degenerate inputs are skipped safely (short lum, opacity<=0, missing)", () => {
  const res = compositeFloorTexture(2, 2, BASE, [
    { lum: [255], color: RED, opacity: 1 },     // too short (len 1 < 4) -> skipped
    { lum: fill(255), color: RED, opacity: 0 }, // opacity 0 -> skipped
    { color: RED, opacity: 1 },                 // no lum -> skipped
  ]);
  for (let i = 0; i < 4; i++) assert.deepEqual(texel(res, i), [10, 20, 30, 255]);
});
