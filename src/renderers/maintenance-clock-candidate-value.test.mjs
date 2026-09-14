// Run: node --test src/renderers/maintenance-clock-candidate-value.test.mjs
//
// Coverage targets — src/renderers/maintenance.js :: renderMaintenanceClockModal
//   [MCV-1] a float state is rounded to one decimal
//   [MCV-2] a whole number keeps no decimal point
//   [MCV-3] a non-numeric state passes through untouched
//
// Measured on hardware 2026-09-13: the SAME picker read "414 min" on a Dreame and
// "206.618888888889 h" on a Roborock, because one firmware reports whole units and the other
// divides. The list is scanned, not computed from — the twelve decimals were noise that made
// the two machines look like different features.
//
// THE INPUT THAT MAKES [MCV-1] RED: go back to `String(c.state)`. ivy's real reading renders at
// full float width and the row wraps.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMaintenanceRenderers } from "./maintenance.js";

function render(candidates) {
  const proto = {};
  applyMaintenanceRenderers(proto);
  const ctx = Object.create(proto);
  ctx.t = (key) => `T(${key})`;
  ctx.tRaw = (key) => `T(${key})`;
  ctx.escapeHtml = (v) => String(v ?? "");
  return ctx.renderMaintenanceClockModal({
    state: {
      isMaintenanceClockPickerOpen: () => true,
      maintenanceClockPicker: () => ({ open: true, loading: false, error: "", pending: "", candidates }),
    },
  });
}

function values(html) {
  return [...html.matchAll(/class="evcc-clock-candidate-value">([^<]*)</g)].map((m) => m[1].trim());
}

test("[MCV-1] a Roborock float is rounded to one decimal", () => {
  // ivy's three real readings, verbatim off the live panel.
  const html = render([
    { entity_id: "sensor.a", name: "A", state: "206.618888888889", unit: "h" },
    { entity_id: "sensor.b", name: "B", state: "29.8688888888889", unit: "h" },
    { entity_id: "sensor.c", name: "C", state: "7.58333333333333", unit: "min" },
  ]);
  assert.deepEqual(values(html), ["206.6 h", "29.9 h", "7.6 min"]);
});

test("[MCV-2] a whole number gains no decimal point", () => {
  // robin's readings, which must not regress into "414.0 min".
  const html = render([
    { entity_id: "sensor.d", name: "D", state: "414", unit: "min" },
    { entity_id: "sensor.e", name: "E", state: "143", unit: "h" },
  ]);
  assert.deepEqual(values(html), ["414 min", "143 h"]);
});

test("[MCV-3] a non-numeric state passes through untouched", () => {
  // A candidate can go `unavailable` between the sweep and the render.
  const html = render([
    { entity_id: "sensor.f", name: "F", state: "unavailable", unit: "h" },
    { entity_id: "sensor.g", name: "G", state: null, unit: "h" },
  ]);
  assert.deepEqual(values(html), ["unavailable h", "h"]);
});
