import { test } from "node:test";
import assert from "node:assert/strict";
import { canZoneRepeat } from "./zone-repeat.js";

/* ---- canZoneRepeat (CARD-6 clause 2) --------------------------------------- */

test("[ZR-1] no snapshot -> false", () => {
  assert.equal(canZoneRepeat(null), false);
  assert.equal(canZoneRepeat(undefined), false);
});

test("[ZR-2] snapshot without the capability key -> false (today's real payload shape)", () => {
  assert.equal(canZoneRepeat({ supports_zone_clean: true }), false);
});

test("[ZR-3] capability explicitly declared true -> true", () => {
  assert.equal(canZoneRepeat({ supports_zone_repeat: true }), true);
});

test("[ZR-4] capability explicitly declared false -> false", () => {
  assert.equal(canZoneRepeat({ supports_zone_repeat: false }), false);
});

test("[ZR-5] a truthy-but-not-boolean-true value does not pass (capability-DECLARED only, strict ===)", () => {
  assert.equal(canZoneRepeat({ supports_zone_repeat: 1 }), false);
  assert.equal(canZoneRepeat({ supports_zone_repeat: "true" }), false);
});
