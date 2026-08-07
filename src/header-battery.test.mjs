// Run: node --test src/header-battery.test.mjs
// HDR-BATT-1 — the header battery rendered a bare "100%" (no label) since
// v0.9.0, and .evcc-battery.low/.critical shipped in the CSS with no renderer
// ever applying them. Same test shape as review-absent-battery.test.mjs: the
// threshold logic replicated here, plus source pins on the constructs.
//
// Coverage (HB = Header Battery):
//   [HB-1] thresholds: critical <= 10 < low <= 20 < plain; absent = no span
//   [HB-2] the label + class constructs are actually in renderHeader's source

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Mirror of render-cycle.js's batteryClass ternary.
function batteryClass(battery) {
  return battery == null ? "" : battery <= 10 ? " critical" : battery <= 20 ? " low" : "";
}

test("[HB-1] threshold bands", () => {
  assert.equal(batteryClass(null), "");
  assert.equal(batteryClass(undefined), "");
  assert.equal(batteryClass(100), "");
  assert.equal(batteryClass(21), "");
  assert.equal(batteryClass(20), " low");
  assert.equal(batteryClass(11), " low");
  assert.equal(batteryClass(10), " critical");
  assert.equal(batteryClass(0), " critical");
});

test("[HB-2] renderHeader labels the battery and applies the band class", () => {
  const src = readFileSync(new URL("./render-cycle.js", import.meta.url), "utf-8");
  assert.match(src, /battery == null \? "" : battery <= 10 \? " critical" : battery <= 20 \? " low" : ""/,
    "the threshold ternary changed — keep this replica in sync");
  assert.match(src, /class="evcc-battery\$\{batteryClass\}"/,
    "the band class is no longer applied — .low/.critical are dead styling again");
  assert.match(src, /renderers\.t\("nav\.battery"\)/,
    "the battery label vanished — the header shows a bare percent again");
});
