/**
 * Tests for the full-SVG -> descriptor splitter. Needs a Playwright browser
 * (it parses + sanitises in real Chromium); run in the pinned image.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { svgToDescriptor } from "./svg-to-descriptor.mjs";

const SVG = `<svg viewBox="-10 -10 500 340">
  <g data-slot="body"><path d="M1,2 L3,4" fill="hsl(var(--animal-fur))"/></g>
  <g data-slot="frontLeftLeg">
    <line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/>
    <g class="cat-fl-lower" style="transform-origin:170px 236px"><line x1="1" y1="2" x2="3" y2="4" stroke="hsl(var(--animal-fur))"/></g>
  </g>
  <g data-slot="eyes"><circle cx="1" cy="2" r="3" fill="hsl(var(--animal-eye))" onload="evil()"/><script>steal()</script></g>
</svg>`;

test("[S2D-1] splits by data-slot + scaffolds colours from token refs", async () => {
  const r = await svgToDescriptor(SVG, { id: "t", name: "T", license: "CC0-1.0" });
  assert.equal(r.ok, true, r.error);
  const a = r.envelope.animal;
  assert.deepEqual(Object.keys(a.parts).sort(), ["body", "eyes", "frontLeftLeg"]);
  assert.equal(a.colors["--animal-eye"], "142 71% 45%");
  assert.ok("--animal-fur" in a.colors, "fur token scaffolded from the SVG");
  assert.equal(r.scaffoldedColors, true);
  assert.ok(r.missing.includes("head") && r.missing.includes("tail"), "flags missing required slots");
});

test("[S2D-2] sanitises each slot — the safe version (script/onload gone)", async () => {
  const r = await svgToDescriptor(SVG, { id: "t", name: "T" });
  assert.equal(r.ok, true);
  assert.ok(!/script|onload/i.test(r.envelope.animal.parts.eyes), r.envelope.animal.parts.eyes);
  assert.ok(/circle/i.test(r.envelope.animal.parts.eyes));
});

test("[S2D-3] preserves the author's leg-animation class", async () => {
  const r = await svgToDescriptor(SVG, { id: "t" });
  assert.match(r.envelope.animal.parts.frontLeftLeg, /cat-fl-lower/);
});

test("[S2D-4] no data-slot groups -> refused with guidance", async () => {
  const r = await svgToDescriptor('<svg><path d="M0 0"/></svg>', { id: "t" });
  assert.equal(r.ok, false);
  assert.match(r.error, /data-slot/);
});

test("[S2D-5] an unknown slot name -> refused", async () => {
  const r = await svgToDescriptor('<svg><g data-slot="wing"><path d="M0 0"/></g></svg>', { id: "t", type: "quadruped" });
  assert.equal(r.ok, false);
  assert.match(r.error, /wing/);
});

test("[S2D-6] provided colours are kept (not scaffolded)", async () => {
  const r = await svgToDescriptor(SVG, { id: "t", colors: { "--animal-eye": "10 20% 30%", "--animal-fur": "40 50% 60%" } });
  assert.equal(r.scaffoldedColors, false);
  assert.equal(r.envelope.animal.colors["--animal-fur"], "40 50% 60%");
});
