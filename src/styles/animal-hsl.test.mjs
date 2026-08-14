/**
 * ANIMAL TOKEN FORMAT — the contract that broke.
 *
 * The animal SVGs consume every variable as `hsl(var(--animal-X))`, so their
 * tokens must be BARE HSL COMPONENTS. The theme system stores colours as
 * 8-digit hex, so an untranslated value produced `hsl(#e8e800e0)` — invalid
 * CSS, and an invalid fill paints SVG black. Reported as "I've screwed up the
 * tokens for the animals"; it was the format, not the values.
 *
 * These pin the conversion. AC-1/2 are the black-cat case itself.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { animalHslComponents } from "./index.js";

test("[AC-1] the cat's own default round-trips to its authored triplet", () => {
  // cat.js declares "--animal-fur": "0 0% 7%" -> #121212 is that colour.
  assert.equal(animalHslComponents("#121212"), "0 0% 7.1%");
});

test("[AC-2] a hex with alpha keeps the alpha as hsl() slash syntax", () => {
  // Yellow at 88% — the value in the bug report. Must NOT drop the opacity:
  // the colour row's slider is half of what it edits.
  const out = animalHslComponents("#e8e800e0");
  assert.match(out, /^60 100% 45.5% \/ 0\.88$/);
});

test("[AC-3] fully opaque emits no alpha clause", () => {
  assert.equal(animalHslComponents("#ff0000ff"), "0 100% 50%");
  assert.equal(animalHslComponents("#ff0000"), "0 100% 50%");
});

test("[AC-4] greys report zero saturation rather than a stray hue", () => {
  assert.equal(animalHslComponents("#808080"), "0 0% 50.2%");
  assert.equal(animalHslComponents("#000000"), "0 0% 0%");
  assert.equal(animalHslComponents("#ffffff"), "0 0% 100%");
});

test("[AC-5] each primary lands on its own hue", () => {
  assert.match(animalHslComponents("#00ff00"), /^120 /);
  assert.match(animalHslComponents("#0000ff"), /^240 /);
});

test("[AC-6] a non-hex value is REFUSED, not mangled", () => {
  // The caller falls back to the raw value on null. A token already holding a
  // triplet, or a var() reference, must pass through untouched rather than be
  // parsed into nonsense.
  assert.equal(animalHslComponents("0 0% 7%"), null);
  assert.equal(animalHslComponents("var(--something)"), null);
  assert.equal(animalHslComponents("red"), null);
  assert.equal(animalHslComponents(""), null);
  assert.equal(animalHslComponents(null), null);
  assert.equal(animalHslComponents("#abc"), null);
});
