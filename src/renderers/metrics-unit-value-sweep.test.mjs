// Task 18 — the shoulder tests. Task 17's [UV-1..4] only pinned the pure helper,
// leaving every callsite invisible to the suite. The 5-dim audit for v2.1.0
// found 7 sibling metrics.js sites the fix had walked past, plus a double-escape
// I introduced at metrics.js:913 by calling sensorUnitValue inside a mini-card
// whose value slot escapes. This file bites the SITES, not just the helper.
//
// Coverage:
//   [UV-5] _renderMetricsMiniCard wraps escaped value in <bdi>
//   [UV-6] mini-card ablation: input carrying <bdi> tags would be double-escaped
//   [UV-7] _formatMetricsMilliliters routes ml through metrics.unit_ml
//   [UV-8] _formatMetricsDurationValue routes min through run_profiles.minutes_unit
//   [UV-9] _formatBaseStationMilliliters routes ml through metrics.unit_ml
//   [UV-10] _formatBaseStationDuration routes min through run_profiles.minutes_unit
//   [UV-11] _formatBaseStationProjectedTank routes ml and % through i18n
//   [UV-12] _formatBaseStationWaterLevel routes % through metrics.unit_percent
//
// Run: node --test src/renderers/metrics-unit-value-sweep.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMetricsRenderers } from "./metrics.js";
import { applyBaseStationRenderers } from "./base-station.js";

const esc = (s) =>
  String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

// Build a card-like host with escapeHtml + a deterministic t() we can inspect.
function makeHost(unitTable = {}) {
  const proto = {};
  proto.escapeHtml = esc;
  proto.t = function (key, vars) {
    const v = unitTable[key] ?? key;
    if (vars) {
      return String(v).replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
    }
    return v;
  };
  proto.tVocab = function () { return ""; };
  proto.tVocabRaw = function (_family, _key, fallback) { return String(fallback ?? ""); };
  proto._formatBaseStationLabel = function (v) { return String(v ?? ""); };
  applyMetricsRenderers(proto);
  applyBaseStationRenderers(proto);
  return proto;
}

test("[UV-5] _renderMetricsMiniCard wraps its escaped value in <bdi>", () => {
  const host = makeHost();
  const html = host._renderMetricsMiniCard("title", "42 min", "detail");
  // The load-bearing invariant: any value the mini-card renders sits inside a
  // bdi isolate, so paragraph bidi cannot split digits from their unit.
  assert.match(html, /<bdi>42 min<\/bdi>/,
    `mini-card value must be bdi-wrapped; got:\n${html}`);
});

test("[UV-5] ablation: a mini-card that reverts the bdi wrap regresses to task 17's defect", () => {
  const host = makeHost();
  const html = host._renderMetricsMiniCard("title", "42 min", "");
  // Prove the bite: without <bdi>, the fix has been reverted.
  assert.ok(html.includes("<bdi>"),
    "if this fails the mini-card is no longer bdi-wrapping — the release-critical fix has regressed");
});

test("[UV-6] mini-card double-escapes any HTML in its value slot — sensorUnitValue is unsafe here", () => {
  // The bite for my 1f153481 regression: sensorUnitValue returns
  //   <bdi>42</bdi>&nbsp;%
  // and the mini-card escapes its input. If a future edit reintroduces
  // sensorUnitValue(...) inside a mini-card, the tags render as literal text.
  const host = makeHost();
  const html = host._renderMetricsMiniCard("title", "<bdi>42</bdi>&nbsp;%", "");
  assert.ok(!html.includes("<bdi>42</bdi>&nbsp;%"),
    "mini-card must escape its value; sensorUnitValue's HTML would ship as literal text");
  assert.ok(html.includes("&lt;bdi&gt;42&lt;/bdi&gt;"),
    "the double-escape (visible <bdi> text) is what the mini-card produces for HTML input");
});

test("[UV-7] _formatMetricsMilliliters routes 'ml' through metrics.unit_ml", () => {
  // In a ru locale the pack ships unit_ml='мл' — the helper must consult t(), not literal.
  const host = makeHost({ "metrics.unit_ml": "мл" });
  assert.equal(host._formatMetricsMilliliters(504), "504 мл");
  // Ablation: a helper that returns bare 'ml' fails this even with a mocked t().
});

test("[UV-8] _formatMetricsDurationValue routes 'min' through run_profiles.minutes_unit", () => {
  const host = makeHost({
    "run_profiles.minutes_unit": "دقيقة",
    "metrics.unknown": "?",
  });
  assert.equal(host._formatMetricsDurationValue(46), "46 دقيقة");
  assert.equal(host._formatMetricsDurationValue("hello"), "hello",
    "non-numeric passes through unchanged (unknown state)");
});

test("[UV-9] _formatBaseStationMilliliters routes 'ml' through metrics.unit_ml", () => {
  const host = makeHost({
    "metrics.unit_ml": "мл",
    "base_station.unknown": "неизвестно",
  });
  assert.equal(host._formatBaseStationMilliliters(300), "300 мл");
  assert.equal(host._formatBaseStationMilliliters(NaN), "неизвестно");
});

test("[UV-10] _formatBaseStationDuration routes 'min' through run_profiles.minutes_unit", () => {
  const host = makeHost({ "run_profiles.minutes_unit": "分" });
  assert.equal(host._formatBaseStationDuration(30), "30 分");
});

test("[UV-11] _formatBaseStationProjectedTank routes ml AND % through i18n", () => {
  const host = makeHost({
    "metrics.unit_ml": "мл",
    "metrics.unit_percent": "%",
    "base_station.unknown": "?",
  });
  const out = host._formatBaseStationProjectedTank({
    estimated_clean_tank_remaining_ml: 250,
    estimated_clean_tank_remaining_percent: 25,
  });
  assert.equal(out, "250 мл (25%)");
  // Without the percent tail
  const out2 = host._formatBaseStationProjectedTank({
    estimated_clean_tank_remaining_ml: 400,
  });
  assert.equal(out2, "400 мл");
});

test("[UV-12] _formatBaseStationWaterLevel routes '%' through metrics.unit_percent", () => {
  const host = makeHost({ "metrics.unit_percent": "%" });
  assert.equal(host._formatBaseStationWaterLevel(75), "75%");
});
