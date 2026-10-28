// Run: node --test src/renderers/stored-setting-vocab.test.mjs
//
// SSV — the panel sinks that printed a room or dock SETTING as the backend's English.
//
// One defect class, seven surfaces, and two distinct shapes of it:
//
//   PRECEDENCE — the renderer already had a correct `tVocabRaw(...)` arm and tested the
//   backend's `*_label` FIRST, so the localizing arm was only reachable when the label was
//   absent, which the backend does not do. Station Water, the room-estimate rows and the
//   planned-water tooltip were all this: a fix that was written, shipped, and unreachable.
//
//   MISSING CALL — the value was printed with no lookup at all: the map selection bar's
//   per-room summary, the rule editor's setting chips, the native zone-setting selects.
//
// Every assertion here reads the expected word OUT OF the shipped pack rather than
// restating a spelling, so a retranslation does not turn this file red; and each test
// names the input that makes it red, because a test whose assertion survives the revert is
// a preference, not a guard.
//
// Coverage:
//   [SSV-1] base-station Station Water localizes the CODE, label demoted to fallback
//   [SSV-2] ablation — label-first precedence restored, and [SSV-1] fails
//   [SSV-3] the maintenance water reading is one helper, shared by the stat row and card
//   [SSV-4] a WORD-valued water sensor derives its status from the code, not the word
//   [SSV-5] the room editor's wetness slider localizes the word AND its three carriers
//   [SSV-6] the map selection bar's per-room summary localizes both settings
//   [SSV-7] a numeric Dreame wetness ("16") passes through the summary unchanged
//   [SSV-8] native zone-setting rows bridge the adapter's axis names to vocab fields
//   [SSV-9] an UNMAPPED zone axis keeps the adapter's own caption and words
//   [SSV-10] the rule editor's setting chips localize the option value
//   [SSV-11] the room-estimate rows localize the code with the label demoted
//   [SSV-12] the planned-water tooltip localizes, and no longer double-escapes

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { applySharedRenderers } from "./shared.js";
import { applyBaseStationRenderers } from "./base-station.js";
import { applyMaintenanceRenderers } from "./maintenance.js";
import { applyRoomEditorRenderer } from "./room-editor.js";
import { applyMapRenderers } from "./map.js";
import { applyRoomRulesRenderers } from "./room-rules.js";
import { applyRoomEstimateRenderers } from "./room-estimate.js";
import { applyRoomsRenderers } from "./rooms.js";
import { registerLocale, translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as enCatalog } from "../i18n/en.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const LOCALES = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales");

function loadPack(code) {
  const nested = JSON.parse(readFileSync(join(LOCALES, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(nested, enCatalog);
  registerLocale(code, flat, { status: "draft" });
  return flat;
}
const DE = loadPack("de");

const APPLIERS = [
  applySharedRenderers, applyBaseStationRenderers, applyMaintenanceRenderers,
  applyRoomEditorRenderer, applyMapRenderers, applyRoomRulesRenderers,
  applyRoomEstimateRenderers, applyRoomsRenderers,
];

/** A host carrying the REAL renderer protos and the REAL translator over a shipped pack. */
function makeHost(lang = "de", brand = "dreame") {
  class H {}
  for (const apply of APPLIERS) apply(H.prototype);
  const h = new H();
  h.escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  h.t = (key, vars) => translate(lang, key, vars);
  h.tRaw = (key, vars) => translate(lang, key, vars, { raw: true });
  h.card = { _state: {
    dashboardSnapshot: () => ({ adapter_id: brand }),
    orderDragItemId: () => null,
    orderDragOverItemId: () => null,
    hasActiveRun: () => false,
  } };
  return h;
}

/* ------------------------------------------------------------------ station water */

test("[SSV-1] Station Water localizes the code; the English label is only the fallback", () => {
  const h = makeHost();
  // The payload the maintenance snapshot actually sends for a word-valued sensor:
  // the code, plus `_display_label` of it. The label used to win at the call site
  // (`stationWaterLabel() || _formatBaseStationWaterLevel(code)`), which short-circuited
  // the whole formatter.
  assert.equal(h._formatBaseStationWaterLevel("low", "Low"), DE["vocab.water_level.low"]);
  assert.equal(h._formatBaseStationWaterLevel("unknown", "Unknown"), DE["vocab.water_level.unknown"]);
  // A numeric reading goes through the card's own percent unit, not the backend's literal.
  assert.equal(h._formatBaseStationWaterLevel(74.6, "75%"), `75${DE["metrics.unit_percent"]}`);
  // No code at all: the label is all there is, and it must still be used.
  assert.equal(h._formatBaseStationWaterLevel(null, "Unavailable"), "Unavailable");
});

test("[SSV-2] ablation — with label-first precedence the row is English again", () => {
  const h = makeHost();
  // The exact expression that shipped. Kept here as the thing [SSV-1] distinguishes from,
  // so the test cannot pass against a revert.
  const asShipped = (code, label) => label || h._formatBaseStationWaterLevel(code);
  assert.equal(asShipped("low", "Low"), "Low");
  assert.notEqual(asShipped("low", "Low"), DE["vocab.water_level.low"]);
});

test("[SSV-3] the maintenance reading is ONE helper, shared by the stat row and the card", () => {
  const h = makeHost();
  // Two call sites, one answer — the stat row and the Station Water card cannot disagree.
  assert.equal(h._formatMaintenanceWaterReading("low", "Low"), DE["vocab.water_level.low"]);
  assert.equal(h._formatMaintenanceWaterReading(40, "40%"), `40${DE["metrics.unit_percent"]}`);
  assert.equal(h._formatMaintenanceWaterReading(null, ""), DE["maintenance.value_unknown"]);
  const card = h._renderStationWaterCard("low", "Low", null);
  assert.ok(card.includes(DE["vocab.water_level.low"]), "the card must show the localized reading");
  assert.ok(!card.includes(">Low<"), "the backend's English word must not reach the value slot");
});

test("[SSV-4] a WORD-valued sensor derives its status from the code, not the rendered word", () => {
  const h = makeHost();
  // The second half of the same bug. The status bucket was matched against the string the
  // card was about to display, so translating the display would have broken the bucket:
  // "Niedrig" matches none of ["low","empty","none"] and every reading fell to unknown.
  const low = h._renderStationWaterCard("low", "Low", null);
  assert.ok(low.includes("status-replace_soon"), "low water must still raise attention");
  const full = h._renderStationWaterCard("full", "Full", null);
  assert.ok(full.includes("status-good"), "full water must still read good");
});

test("[SSV-13] the enum tank cards localize the state, label demoted to the fallback", () => {
  // The status CHIP on these cards was always translated while the VALUE beside it printed
  // the backend's `_display_label(state)` — "Nicht verfügbar / Not Available" in one tile.
  const h = makeHost();
  const html = h._renderTankStatusCards({
    clean: { state: "low_water", label: "Low Water" },
    dirty: { state: "installed", label: "Installed" },
  });
  assert.ok(html.includes(DE["vocab.tank_status.low_water"]), "clean tank value must localize");
  assert.ok(html.includes(DE["vocab.tank_status.installed"]), "dirty tank value must localize");
  assert.ok(!html.includes(">Low Water<"), "the backend's English must not reach the value slot");
});

test("[SSV-14] an unkeyed tank state keeps the device's label, escaped exactly once", () => {
  // Two properties in one input. The tank set is DEVICE-defined, so a state we never keyed
  // must still read; and `fr`'s own word for low water carries an apostrophe ("Peu d'eau"),
  // which is the live check that the raw twin plus the sink's escape is a SINGLE escape.
  const h = makeHost("fr");
  const FR = loadPack("fr");
  assert.ok(FR["vocab.tank_status.low_water"].includes("'"), "fr must carry the apostrophe this tests");
  const html = h._renderTankStatusCards({
    clean: { state: "low_water", label: "Low Water" },
    dirty: { state: "rinsing", label: "Rinsing" },
  });
  assert.ok(html.includes("Peu d&#39;eau"), "escaped once");
  assert.ok(!html.includes("&amp;#39;"), "and never twice");
  assert.ok(html.includes("Rinsing"), "an unkeyed device state falls back to its own label");
});

/* ------------------------------------------------------------------ component names */

test("[SSV-15] the item NAME resolves through the same family as the modal TITLE", () => {
  const h = makeHost();
  // `_maintenanceItemName` only ever looked in `maintenance.component_label.*`, which has
  // no `swivel_wheel` and no `cleaning_tray` entry at all — so a Eufy caster_wheel (whose
  // label_key is "swivel_wheel") showed the backend's English name beside a modal title
  // that was translated, from the same item, on the same screen.
  assert.equal(
    h._maintenanceItemName({ component: "caster_wheel", label_key: "swivel_wheel", label: "Swivel Wheel" }),
    DE["vocab.maintenance_component.swivel_wheel"],
  );
  assert.equal(
    h._maintenanceItemName({ component: "cleaning_tray", label: "Cleaning Tray" }),
    DE["vocab.maintenance_component.cleaning_tray"],
  );
  // A component with no key in EITHER family keeps the backend's label — the forward-compat
  // leg, and the reason the deferred `component_label` gap does not become a blank screen.
  assert.equal(
    h._maintenanceItemName({ component: "washboard", label: "Washboard" }),
    "Washboard",
  );
  // Nothing at all still names the row rather than rendering empty.
  assert.equal(h._maintenanceItemName({}), DE["maintenance.unnamed_item"]);
});

test("[SSV-16] the item name is RAW, because every one of its sinks escapes", () => {
  // The latent half. `_maintenanceItemName` used `this.t()` for the component_label leg,
  // which escapes — and all four consumers escape again (the item-name row, the
  // reset-confirmation sentence, and the two modal titles that pass it as their fallback).
  // Measured across 27 keys x 17 packs, zero values carry & < > " ', so it never showed —
  // but only because the ten Latin packs still hold the raw ENGLISH for most of that group.
  // THE INPUT THAT MAKES IT RED is the first translation of it, so this supplies one:
  // French for the clean-water tank is "Réservoir d'eau propre".
  const translated = "Réservoir d'eau propre";
  registerLocale("xx-escape", { "maintenance.component_label.clean_water_tank": translated }, { status: "custom" });
  const h = makeHost("xx-escape");
  const name = h._maintenanceItemName({ component: "clean_water_tank", label: "Clean Water Tank" });
  assert.equal(name, translated, "the helper must return the apostrophe RAW — its callers escape");
  assert.ok(!name.includes("&#39;"), "a pre-escaped return double-escapes at every sink");
});

/* ------------------------------------------------------------------ wetness slider */

test("[SSV-5] the room editor's wetness slider localizes the word and its three carriers", () => {
  const h = makeHost();
  const range = { min: 1, max: 32, step: 1,
    labels: { min_label: "Slightly Dry", mid_label: "Moist", max_label: "Wet" } };
  const html = h._renderWetnessSlider(null, { water_level: "32" }, range);
  assert.ok(html.includes(DE["vocab.water_level.wet"]), "the thumb word must be localized");
  assert.ok(html.includes(`data-word-low="${DE["vocab.water_level.slightly_dry"]}"`));
  assert.ok(html.includes(`data-word-mid="${DE["vocab.water_level.moist"]}"`));
  assert.ok(html.includes(`data-word-high="${DE["vocab.water_level.wet"]}"`));
  for (const english of ["Slightly Dry", "Moist", "Wet"]) {
    assert.ok(!html.includes(english), `"${english}" must not survive into a de render`);
  }
});

/* ------------------------------------------------------------------ map summary */

test("[SSV-6] the map selection bar's per-room summary localizes both settings", () => {
  const h = makeHost();
  const summary = h._mapRoomSettingsSummary({ fanSpeed: "quiet", waterLevel: "high" });
  assert.ok(summary.includes(DE["vocab.fan_speed.quiet"]));
  assert.ok(summary.includes(DE["vocab.water_level.high"]));
  // A stored DISPLAY spelling resolves through its alias key rather than reverting.
  assert.equal(
    h._mapRoomSettingsSummary({ fanSpeed: "BoostIQ" }),
    DE["vocab.fan_speed.boostiq"],
  );
});

test("[SSV-7] a numeric Dreame wetness passes through the summary unchanged", () => {
  const h = makeHost();
  // The fine water axis stores an integer as a string. It is not a vocabulary word, no key
  // can match its slug, and the reading must survive the lookup untouched.
  assert.equal(h._mapRoomSettingsSummary({ waterLevel: "16" }), "16");
});

/* ------------------------------------------------------------------ zone settings */

const ZONE_NATIVE = [
  { key: "mode", label: "Mode", default: "vacuum",
    options: [{ value: "vacuum", label: "Vacuum" }, { value: "vacuum_mop", label: "Vacuum & Mop" }] },
  { key: "suction", label: "Suction", default: "standard",
    options: [{ value: "quiet", label: "Quiet" }, { value: "strong", label: "Intense" }] },
  { key: "route", label: "Route", default: "standard",
    options: [{ value: "standard", label: "Standard" }, { value: "intensive", label: "Intensive" }] },
  { key: "water", label: "Water", default: "moist",
    options: [{ value: "moist", label: "Moist" }, { value: "wet", label: "Wet" }] },
];

test("[SSV-8] native zone-setting rows bridge the adapter's axis names to vocab fields", () => {
  const h = makeHost();
  const state = { zoneSettingValue: (_k, d) => d };
  const html = h._renderNativeZoneSettingRows(state, ZONE_NATIVE);
  // Captions reuse the four keys the sibling entity-backed branch already uses — `route` is
  // the mop-route axis, which this card calls clean_intensity.
  for (const key of ["map.zone_setting_mode", "map.zone_setting_suction",
                     "map.zone_setting_intensity", "map.zone_setting_water"]) {
    assert.ok(html.includes(DE[key]), `caption ${key} must be localized`);
  }
  assert.ok(html.includes(DE["vocab.clean_mode.vacuum_mop"]));
  assert.ok(html.includes(DE["vocab.dreame.fan_speed.strong"]), "the brand's own word wins");
  assert.ok(html.includes(DE["vocab.clean_intensity.intensive"]));
  assert.ok(html.includes(DE["vocab.water_level.wet"]));
  for (const english of ["Route", "Suction", "Intensive", ">Wet<"]) {
    assert.ok(!html.includes(english), `"${english}" must not survive into a de render`);
  }
});

test("[SSV-9] an UNMAPPED zone axis keeps the adapter's own caption and words", () => {
  const h = makeHost();
  const state = { zoneSettingValue: (_k, d) => d };
  // An axis core has never seen. Inventing a vocab field for it would be a guess; the
  // adapter's declared label is the only honest answer.
  const html = h._renderNativeZoneSettingRows(state, [{
    key: "detergent", label: "Detergent", default: "auto",
    options: [{ value: "auto", label: "Auto dose" }],
  }]);
  assert.ok(html.includes("Detergent"));
  assert.ok(html.includes("Auto dose"));
});

/* ------------------------------------------------------------------ rule editor */

test("[SSV-10] the rule editor's setting chips localize the option value", () => {
  const h = makeHost();
  const state = {
    adapterOptionsFor: (field) => (field === "clean_intensity"
      ? [{ value: "standard", label: "Standard" }, { value: "intensive", label: "Intensive" }]
      : []),
  };
  const html = h._renderModifierChanges({ effect: { changes: {} } }, state);
  assert.ok(html.includes(DE["vocab.clean_intensity.intensive"]));
  assert.ok(!html.includes(">Intensive<"), "the adapter's English must not reach the chip");
});

/* ------------------------------------------------------------------ room estimate */

test("[SSV-11] the room-estimate rows localize the code with the label demoted", () => {
  const h = makeHost();
  const ctx = {
    state: {
      isRoomEstimateModalOpen: () => true,
      activeRoomEstimateDetails: () => ({
        room: { id: 1, name: "Küche", slug: "kueche" },
        entry: null,
        roomEstimate: null,
        plannedWaterRoom: {
          // Both arms present, which is what the backend sends — the label used to win.
          clean_mode_label: "Vacuum and mop", effective_clean_mode: "vacuum_mop",
          water_level_label: "High", effective_water_level: "high",
          estimated_robot_water_used_ml: 120,
        },
      }),
    },
  };
  const html = h.renderRoomEstimateModal(ctx);
  assert.ok(html.includes(DE["vocab.clean_mode.vacuum_mop"]), "mode row must be localized");
  assert.ok(html.includes(DE["vocab.water_level.high"]), "water row must be localized");
  assert.ok(!html.includes("Vacuum and mop"), "the English label must not reach the row");
});

/* ------------------------------------------------------------------ planned water */

test("[SSV-12] the planned-water tooltip localizes, and no longer double-escapes", () => {
  // TWO defects in one expression. The settings read English because the label won; and the
  // whole join was escapeHtml'd on top of t()'s own escape, so `fr`'s
  // "Consommation d'eau projetée" rendered its apostrophe as the literal `&#39;`.
  const h = makeHost("fr");
  const FR = loadPack("fr");
  h.renderConfidenceChip = () => "";
  h._formatLearningMinutes = (m) => String(m);
  const state = {
    dashboardPlannedWaterRoomForRoom: () => ({
      effective_clean_mode: "vacuum_mop", clean_mode_label: "Vacuum and mop",
      effective_water_level: "high", water_level_label: "High",
      mop_active: true, estimated_robot_water_used_ml: 120,
    }),
  };
  const html = h.renderRoomCard({ id: 1, name: "Cuisine", slug: "cuisine", enabled: true }, state);
  assert.ok(html.includes("&#39;"), "the apostrophe must be escaped exactly once");
  assert.ok(!html.includes("&amp;#39;"), "and never twice — that is the visible bug");
  assert.ok(html.includes(FR["vocab.clean_mode.vacuum_mop"]), "the mode must be localized");
});
