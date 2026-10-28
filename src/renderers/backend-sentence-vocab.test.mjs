// Run: node --test src/renderers/backend-sentence-vocab.test.mjs
//
// ATT / UPK / WAT / EST / REF / OA — the census's "backend English SENTENCE" bucket.
//
// THE BUCKET'S NAME WAS THE MISTAKE. These eight sinks were triaged as needing backend
// reason-codes — "the separate larger job" — because they were classified by what the sink
// PRINTED rather than by what was sitting next to it. Measured against the producers, seven
// are card-side and three need no key at all:
//
//   base-station subtitle   the Upkeep tab ALREADY composes it from attention_count
//   upkeep attention item   _maintenancePrimaryValue/_SecondaryValue already compose it
//   learning water notice   both codes were keyed by the previous wave
//   learning estimate       `estimate.error` is a code; one new key
//   rooms order advisory    one fixed sentence, so PRESENCE is the signal; one new key
//   rules save refusal      `result.reason` was in hand and ranked THIRD
//   setup step heading      3 of 5 ids keyed; the 2 unkeyed are shipped by no adapter
//   setup service error     a thrown exception string — correctly NOT localizable
//
// Classifying on the symptom put the codes, the helpers and the keys out of sight.
//
// Coverage:
//   [ATT-1] the Base Station subtitle composes from the count, in the reader's language
//   [ATT-2] the localized fallback is escaped ONCE — a live `it` defect, measured
//   [ATT-3] absent is not zero: a null count must not claim "nothing needs attention"
//   [UPK-1] the attention item's detail comes from the localized helpers
//   [WAT-1] the water notice resolves its code; the backend sentence is demoted
//   [EST-1] the estimate panel resolves `estimate_failed`, keeps `no_payload`'s own line
//   [EST-2] …and a payload with neither code nor message still says something
//   [REF-1] the three refusal codes resolve through the access-issue family
//   [REF-2] and the binding passes those prefixes
//   [OA-1] the rooms advisory renders the CARD's sentence, not the backend's

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { applySharedRenderers } from "./shared.js";
import { applyBaseStationRenderers } from "./base-station.js";
import { applyMaintenanceRenderers } from "./maintenance.js";
import { applyLearningRenderers } from "./learning.js";
import { resolveCodedLabel } from "../state/coded-label.js";
import { registerLocale, translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as enCatalog } from "../i18n/en.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOCALES = join(HERE, "..", "..", "custom_components", "eufy_vacuum", "frontend", "locales");

function loadPack(code) {
  const nested = JSON.parse(readFileSync(join(LOCALES, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(nested, enCatalog);
  registerLocale(code, flat, { status: "draft" });
  return flat;
}
const DE = loadPack("de");
const IT = loadPack("it");

function makeHost(lang = "de") {
  class H {}
  for (const apply of [applySharedRenderers, applyBaseStationRenderers,
                       applyMaintenanceRenderers, applyLearningRenderers]) {
    apply(H.prototype);
  }
  const h = new H();
  h.escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  h.t = (key, vars) => translate(lang, key, vars);
  h.tRaw = (key, vars) => translate(lang, key, vars, { raw: true });
  h.card = { _state: { dashboardSnapshot: () => ({ adapter_id: "eufy" }) } };
  return h;
}

/* ------------------------------------------------------- the attention summary */

test("[ATT-1] the Base Station subtitle composes from the count", () => {
  const h = makeHost();
  // The Upkeep tab has composed this from `attention_count` since CENSUS-6. The Base
  // Station panel printed `upkeep.attention_summary` — the backend's English — from the
  // SAME payload, one view across.
  const some = h._baseStationAttentionSubtitle({ attention_count: 3, attention_summary: "3 upkeep item(s) need attention." });
  assert.equal(some, translate("de", "maintenance.attention_summary", { count: 3 }));
  assert.ok(!some.includes("upkeep item(s)"), "the backend's English must not survive");

  const none = h._baseStationAttentionSubtitle({ attention_count: 0, attention_summary: "No upkeep items need attention." });
  assert.equal(none, DE["maintenance.attention_summary_none"]);
});

test("[ATT-2] the localized fallback is escaped exactly once", () => {
  // LIVE, AND MEASURED, not theoretical. The expression was
  // `escapeHtml(attention_summary || t("…subtitle"))` — one escape over both arms — and of
  // the 17 packs `it` is the one whose subtitle carries an apostrophe ("dell'attività"), so
  // that panel rendered `dell&#39;attività` on screen.
  const h = makeHost("it");
  assert.ok(IT["base_station.station_status_subtitle"].includes("'"),
    "the `it` subtitle must carry the apostrophe this test is about");
  const out = h._baseStationAttentionSubtitle({});
  assert.ok(out.includes("&#39;"), "escaped once");
  assert.ok(!out.includes("&amp;#39;"), "and never twice — that is the shipped bug");
});

test("[ATT-3] absent is not zero", () => {
  const h = makeHost();
  // Number(null) is 0 and 0 IS finite, so a `?? 0` here would render a confident "nothing
  // needs attention" on a payload that never said so. [C6-6] caught exactly this in the
  // Upkeep tab's copy; the rule is inherited, not rediscovered.
  const out = h._baseStationAttentionSubtitle({ attention_count: null, attention_summary: "Something needs attention." });
  assert.equal(out, "Something needs attention.", "a null count must defer to the backend");
  assert.notEqual(out, DE["maintenance.attention_summary_none"]);
  // And with nothing at all, the panel's own subtitle rather than a blank line.
  assert.equal(h._baseStationAttentionSubtitle({}), DE["base_station.station_status_subtitle"]);
});

test("[ATT-4] and the panel actually calls it", () => {
  // The CALL-SITE gate. [ATT-1..3] exercise the helper, and the helper was never the
  // broken part — ablating the panel back to its inline
  // `escapeHtml(attention_summary || t("…subtitle"))` left all three green. Fifth time in
  // this census that a correct helper with a wrong caller passed every test about the
  // helper, after sliderRow's translator slot, the floor select, the battery row and the
  // profile filter.
  const src = readFileSync(join(HERE, "base-station.js"), "utf8");
  assert.ok(src.includes("this._baseStationAttentionSubtitle(upkeep)"),
    "the Station Status panel must resolve its subtitle through the helper");
  const code = src.replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, "");
  assert.ok(
    !/escapeHtml\(\s*upkeep\.attention_summary/.test(code),
    "the panel is escaping the backend summary inline again — which also re-escapes the "
    + "localized fallback, the live `it` defect",
  );
});

test("[UPK-1] the attention item's detail comes from the localized helpers", () => {
  const h = makeHost();
  // `_maintenancePrimaryValue` composes "38% remaining" from `remaining_percent` through
  // `maintenance.percent_remaining`, which every pack already carries — twenty lines away
  // in the same file, used by the item CARDS, ignored by this row.
  const html = h._renderMaintenanceAttentionItem({
    component: "filter", label: "Filter", status: "warning", _category: "maintenance",
    remaining_percent: 38, interval_hours: 100,
    remaining_summary: "38% remaining", usage_summary: "62 hours used",
  });
  const expected = h.escapeHtml(translate("de", "maintenance.percent_remaining", { percent: 38 }, { raw: true }));
  assert.ok(html.includes(expected), `expected the localized remaining line, got: ${html.slice(0, 200)}`);
  assert.ok(!html.includes("38% remaining"), "the backend's English summary must not reach the row");
  // A payload with the prose but no numbers still reads — the backend line stays behind.
  const proseOnly = h._renderMaintenanceAttentionItem({
    component: "filter", status: "warning", summary: "Some backend sentence.",
  });
  assert.ok(proseOnly.includes("Some backend sentence."));
});

/* ------------------------------------------------------------------ learning */

test("[WAT-1] the water notice resolves its code", () => {
  const h = makeHost();
  // The CODE was already being used one line up, to pick the notice's colour, while the
  // SENTENCE beside it printed English. Both codes were keyed by the block-reason wave.
  for (const code of ["not_enough_clean_water", "low_clean_water_margin"]) {
    const resolved = resolveCodedLabel(
      { code, message: "Not enough clean water is estimated to complete the selected job." },
      (k, v) => h.tRaw(k, v),
      { prefixes: ["rooms.block_reason."] },
    );
    assert.equal(resolved, DE[`rooms.block_reason.${code}`], code);
  }
  // An unknown water reason still says the backend's sentence rather than going blank.
  assert.equal(
    resolveCodedLabel({ code: "tank_sensor_stale", message: "Backend prose." },
      (k, v) => h.tRaw(k, v), { prefixes: ["rooms.block_reason."] }),
    "Backend prose.",
  );
});

test("[EST-1] the estimate panel resolves its error code", () => {
  const h = makeHost();
  const resolve = (estimate) => resolveCodedLabel(
    { code: estimate.error, message: estimate.message || estimate.error_detail || "" },
    (k, v) => h.tRaw(k, v),
    { prefixes: ["learning.estimate_error."], genericKey: "learning.estimate_unavailable_message" },
  );
  assert.equal(
    resolve({ error: "estimate_failed", message: "Estimate failed for this run." }),
    DE["learning.estimate_error.estimate_failed"],
  );
  // `no_payload` keeps its own actionable line and is NOT in this family — it is handled by
  // the branch above the resolver, because "queue a run first" is something to do.
  assert.ok(!("learning.estimate_error.no_payload" in enCatalog));
  assert.ok(DE["learning.estimate_queue_first"]);
});

test("[EST-2] a payload with neither code nor message still says something", () => {
  const h = makeHost();
  const out = resolveCodedLabel({ code: "", message: "" }, (k, v) => h.tRaw(k, v),
    { prefixes: ["learning.estimate_error."], genericKey: "learning.estimate_unavailable_message" });
  assert.equal(out, DE["learning.estimate_unavailable_message"]);
  assert.ok(!out.includes("learning."), "never a bare key");
});

/* --------------------------------------------------------------- save refusal */

test("[REF-1] the three refusal codes resolve through the access-issue family", () => {
  const h = makeHost();
  // `update_room_fields` refuses with room_not_found / no_dock_room / invalid_access_graph.
  // They are access-graph vocabulary, and `no_dock_room` was ALREADY keyed there — which is
  // what made that family the right home rather than a new room-rules one.
  const resolve = (result) => resolveCodedLabel(
    { code: result.reason, message: result.reason_detail ?? result.message ?? "" },
    (k, v) => h.tRaw(k, v),
    {
      prefixes: ["room_access.issue.card.", "room_access.issue."],
      genericKey: "bind_room_rules.backend_rejected_rule",
    },
  );
  for (const code of ["room_not_found", "no_dock_room", "invalid_access_graph"]) {
    const out = resolve({ reason: code, reason_detail: "Some English detail from the backend." });
    assert.ok(out, `${code} resolved to nothing`);
    assert.notEqual(out, "Some English detail from the backend.", `${code} fell through to English`);
    assert.ok(!out.includes("room_access.issue"), `${code} leaked a bare key`);
  }
  // A code from a newer backend keeps the backend's detail; neither code nor detail gets
  // the card's own generic refusal rather than a blank editor.
  assert.equal(resolve({ reason: "quota_exceeded", reason_detail: "Backend detail." }), "Backend detail.");
  assert.equal(resolve({ reason: "", reason_detail: "" }), DE["bind_room_rules.backend_rejected_rule"]);
});

test("[REF-2] and the binding passes those prefixes", () => {
  // The composition lives in the BINDING, not the renderer the census pointed at — the
  // renderer only prints what the binding stored. So this is where the call-site gate goes.
  const src = readFileSync(join(HERE, "..", "bindings", "room-rules.js"), "utf8");
  assert.ok(src.includes("resolveCodedLabel("), "the refusal must go through the resolver");
  assert.ok(src.includes('"room_access.issue.card."'), "card-specific wording must be tried first");
  // Assert the PROPERTY, not one old shape. A first version matched the literal
  // `const message = result?.reason_detail` chain, which an ablation that merely wrapped
  // the detail in anything else slipped straight past — a negative check pinned to one
  // spelling is a check against that spelling, not against the defect.
  const assignment = src.match(/const message =([\s\S]{0,60})/);
  assert.ok(assignment, "`const message =` not found — did the handler move?");
  assert.ok(
    assignment[1].trimStart().startsWith("resolveCodedLabel("),
    `the resolver must be what message is assigned FROM, or the code is ranked below the `
    + `backend's English again — got: ${assignment[1].trim().slice(0, 48)}`,
  );
});

/* ------------------------------------------------------------ order advisory */

test("[OA-1] the rooms advisory renders the CARD's sentence", () => {
  // One fixed backend sentence with no parameters, so its PRESENCE is the signal and there
  // was never a code to add. [OA-1]/[OA-2] in tests/unit/test_card_sentence_contracts.py
  // are the other half: they fail if the backend ever returns a SECOND sentence, which is
  // the only thing that would make presence-keying unsound.
  assert.ok("rooms.order_advisory" in enCatalog, "the card needs its own sentence");
  assert.ok(DE["rooms.order_advisory"], "untranslated in de");
  assert.notEqual(DE["rooms.order_advisory"], enCatalog["rooms.order_advisory"]);
  const src = readFileSync(join(HERE, "rooms.js"), "utf8");
  assert.ok(src.includes('this.t("rooms.order_advisory")'), "the renderer must use the key");
  assert.ok(
    !/:\s*this\.escapeHtml\(orderAdvisory\)/.test(src),
    "the backend sentence is being printed again",
  );
});
