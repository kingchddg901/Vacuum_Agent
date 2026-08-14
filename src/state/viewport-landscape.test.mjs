/**
 * LANDSCAPE — narrow OR short is mobile.
 *
 * Rotating a 390x844 phone gives ~844x390. The old predicate looked only at
 * width, so 844 cleared the 600px gate and the card rendered the DESKTOP shell
 * with 390px of height — dropping the compact chrome exactly where vertical
 * room had just collapsed. Reported from a phone: "it reads the wider viewpoint
 * and tries to render in desktop mode. But it's not really that wide, and it
 * has no height at that point."
 *
 * VL-1/2 are that rotation, both ways.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyViewportState } from "./viewport.js";

function makeState() {
  const proto = {};
  applyViewportState(proto);
  return Object.create(proto);
}

test("[VL-1] a landscape phone is mobile despite clearing the width gate", () => {
  const s = makeState();
  s.setViewportFromSize(844, 390);
  assert.equal(s.viewport(), "mobile");
  assert.equal(s.isMobileViewport(), true);
});

test("[VL-2] rotating back to portrait stays mobile, and reports no churn", () => {
  const s = makeState();
  assert.equal(s.setViewportFromSize(844, 390), true, "desktop -> mobile is a change");
  // Same label either way round, so the card must NOT be told to re-render.
  assert.equal(s.setViewportFromSize(390, 844), false, "still mobile, no re-render");
  assert.equal(s.viewport(), "mobile");
});

test("[VL-3] a real desktop window is unaffected", () => {
  const s = makeState();
  assert.equal(s.setViewportFromSize(1280, 800), false, "already desktop");
  assert.equal(s.viewport(), "desktop");
});

test("[VL-4] a tablet keeps the desktop shell", () => {
  const s = makeState();
  s.setViewportFromSize(768, 1024);
  assert.equal(s.viewport(), "desktop");
});

test("[VL-5] a short desktop window gets the compact shell, deliberately", () => {
  // Not a side effect: a 450px-tall window has no vertical room either, which
  // is the whole thing the compact shell exists for.
  const s = makeState();
  s.setViewportFromSize(1400, 450);
  assert.equal(s.viewport(), "mobile");
});

test("[VL-6] the boundary is exclusive on both axes", () => {
  const a = makeState();
  a.setViewportFromSize(600, 500);
  assert.equal(a.viewport(), "desktop", "600x500 is exactly at both gates");

  const b = makeState();
  b.setViewportFromSize(600, 499);
  assert.equal(b.viewport(), "mobile", "one pixel shorter flips it");

  const c = makeState();
  c.setViewportFromSize(599, 500);
  assert.equal(c.viewport(), "mobile", "one pixel narrower flips it");
});

test("[VL-7] omitting height keeps width-only behaviour for callers with no window", () => {
  // Tests and SSR have no window; the predicate must not invent a height and
  // silently force the compact shell on them.
  const s = makeState();
  s.setViewportFromSize(1280);
  assert.equal(s.viewport(), "desktop");
});
