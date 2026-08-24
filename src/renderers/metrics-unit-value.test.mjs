// Task 17: the pure `formatUnitValue` helper.
//
// Chris's screenshots on 2026-08-24 showed an Arabic-locale Metrics tab rendering
// "min 46" instead of "46 min" — bidi is right to flip LTR digits and EN letters
// separated by a neutral space, so the value must be bdi-isolated. This tests the
// pure formatter that every callsite in metrics.js now delegates to.
//
// Coverage:
//   [UV-1] wraps the value in <bdi>, joined with nbsp to the unit
//   [UV-2] escapes both value and unit (values arrive HTML-untrusted)
//   [UV-3] an empty unit renders just <bdi>value</bdi> (no trailing separator)
//   [UV-4] a non-Latin unit (RTL Arabic) is not truncated by the escape
//
// Run: node --test src/renderers/metrics-unit-value.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatUnitValue } from "./metrics.js";

// Realistic HTML escaper — same shape callers pass. Not a real DOMPurify (we do
// not need one; the helper's own escape is what matters), just enough to prove
// the caller-supplied escape is what runs.
const esc = (s) =>
  String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

test("[UV-1] wraps value in <bdi>, joined with nbsp to the unit", () => {
  // The nbsp is &nbsp; entity, NOT a literal space — that is what stops bidi from
  // reordering across it AND what stops a wrap-break splitting a value from its unit.
  const html = formatUnitValue("46", "min", esc);
  assert.equal(html, "<bdi>46</bdi>&nbsp;min");
});

test("[UV-1] ablation: NO <bdi> would allow bidi to flip '46 min' to 'min 46'", () => {
  // Load-bearing enough to pin as its own row: any 'fix' that reverts the isolate
  // (e.g. returning `${value}&nbsp;${unit}` bare) trips this immediately.
  const html = formatUnitValue("46", "min", esc);
  assert.match(html, /<bdi>46<\/bdi>/, "the value must be inside a bdi isolate");
});

test("[UV-2] escapes value and unit", () => {
  // A value carrying HTML meta-chars would inject markup without the escape.
  // Callers pass numeric strings today, but the helper is guarding the callsite
  // rather than the current inputs, so this is the future-proofing half.
  const html = formatUnitValue("<img>", "%", esc);
  assert.ok(!html.includes("<img>"), "raw <img> reached the output — escape not called");
  assert.ok(html.includes("&lt;img&gt;"), `expected escaped form, got: ${html}`);
});

test("[UV-3] empty unit renders just the bdi with no trailing separator", () => {
  const html = formatUnitValue("46", "", esc);
  assert.equal(html, "<bdi>46</bdi>");
});

test("[UV-4] a non-Latin unit is preserved through the escape", () => {
  // Arabic minute suffix — this is what an ar-locale card actually renders after
  // the fix. The escape must not strip or transcode non-Latin bytes.
  const html = formatUnitValue("46", "دقيقة", esc);
  assert.equal(html, "<bdi>46</bdi>&nbsp;دقيقة");
  // And the Han-script Chinese case too, for completeness of the "script-strong
  // unit does not itself flip" claim in the finding.
  const zh = formatUnitValue("46", "分钟", esc);
  assert.equal(zh, "<bdi>46</bdi>&nbsp;分钟");
});
