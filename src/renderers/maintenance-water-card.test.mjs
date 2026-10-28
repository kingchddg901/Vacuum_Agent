// Unit tests for the water/tank cards in the maintenance renderer.
// Run: node --test src/renderers/maintenance-water-card.test.mjs
//
// These exist because a device with NO water-level sensor rendered a confident
// "Empty · ~0 ml remaining" card. Root cause was JS coercion, not missing data:
// `Number(null)` is 0, so `Number.isFinite(Number(stationWater))` was TRUE for a
// null reading -> numericValue 0 -> status "replace_now" -> the "Empty" label, and
// `Number.isFinite(Number(availableCleanTankMl))` did the same for "~0 ml".
// A fabricated reading is worse than a missing one: the user acts on it.
//
// Coverage targets:
//   [WTR-1] null station water renders NOTHING (not an "Empty" card)
//   [WTR-2] a real numeric reading still renders, with its value
//   [WTR-3] ~0 ml secondary line never appears from a null tank capacity
//   [TNK-1] enum tank status renders the DEVICE's own words
//   [TNK-2] absent tank status renders nothing
//   [TNK-3] low_water maps to an attention status, not "good"
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMaintenanceRenderers } from "./maintenance.js";
import { applySharedRenderers } from "./shared.js";

function makeInstance() {
  const proto = {};
  // The REAL tVocab/tVocabRaw pair, not a stub of it. The tank value and the station-water
  // reading both resolve through it now, and a hand-written stand-in would be transcribing
  // the resolution this file is supposed to be downstream of.
  //
  // With echo-keys below, every `vocab.*` lookup MISSES by construction (translate returns
  // the key, tVocabRaw sees key === key and hands back the fallback) — so what this file
  // pins is the FALLBACK leg, which is the load-bearing one here: the tank-state set is the
  // DEVICE's, not ours, so a state we have never keyed must still reach the user as its own
  // label. The keyed leg is covered against the real shipped packs in
  // stored-setting-vocab.test.mjs [SSV-13], where a catalogue exists to hit.
  applySharedRenderers(proto);
  applyMaintenanceRenderers(proto);
  const inst = Object.create(proto);
  inst.t = (key) => key;                      // echo keys: assert the BRANCH, not wording
  inst.tRaw = (key) => key;
  inst.escapeHtml = (s) => String(s);
  inst._formatMaintenanceStatus = (k) => `status:${k}`;
  return inst;
}

test("[WTR-1] a null water level renders NO card at all", () => {
  const inst = makeInstance();
  const html = inst._renderStationWaterCard(null, null, null);
  assert.equal(html, "", "a device with no water sensor must render no water card");
});

test("[WTR-1b] the null reading never claims Empty", () => {
  const inst = makeInstance();
  const html = inst._renderStationWaterCard(null, null, null);
  assert.ok(!html.includes("water_empty"), "null must not render the Empty label");
  assert.ok(!html.includes("replace_now"), "null must not become a replace_now status");
});

test("[WTR-2] a real numeric reading still renders with its value", () => {
  const inst = makeInstance();
  const html = inst._renderStationWaterCard(80, null, null);
  assert.ok(html.includes("station_water_title"), "a real reading must still render");
  assert.ok(html.includes("80"), "the numeric value must appear");
});

test("[WTR-3] a null tank capacity never renders the ml line", () => {
  const inst = makeInstance();
  const html = inst._renderStationWaterCard(80, null, null);
  assert.ok(!html.includes("ml_remaining"), "Number(null)===0 must not surface as ~0 ml");
});

test("[TNK-1] an UNKEYED tank state still reaches the user as its own label", () => {
  const inst = makeInstance();
  // The set is the device's: `tank_status` is a raw sensor state, and config_schema.py
  // declares four values we key. Anything else — a firmware that adds a fifth, a model we
  // have not seen — must keep the backend's label rather than going blank or showing a
  // dotted key. Under echo-keys every vocab lookup misses, so this is that leg.
  const html = inst._renderTankStatusCards({
    clean: { state: "rinsing", label: "Rinsing" },
    dirty: { state: "installed", label: "Installed" },
  });
  assert.ok(html.includes("clean_water_tank_title"), "clean tank card must render");
  assert.ok(html.includes("dirty_water_tank_title"), "dirty tank card must render");
  assert.ok(html.includes("Rinsing"), "an unkeyed state must fall back to the device's label");
  assert.ok(html.includes("Installed"), "and so must a keyed one when no catalogue is loaded");
});

test("[TNK-2] absent tank status renders nothing", () => {
  const inst = makeInstance();
  assert.equal(inst._renderTankStatusCards(null), "");
  assert.equal(inst._renderTankStatusCards({ clean: null, dirty: null }), "");
});

test("[TNK-3] low_water is an attention status, not good", () => {
  const inst = makeInstance();
  const html = inst._renderTankStatusCards({ clean: { state: "low_water", label: "Low water" }, dirty: null });
  assert.ok(html.includes("replace_soon"), "low_water must raise attention");
  assert.ok(!html.includes("status--status-good"), "low_water must not read as good");
});
