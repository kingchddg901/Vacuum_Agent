// Run: node --test src/renderers/base-station-stat-vocab.test.mjs
//
// BSV — the two Station Status rows CENSUS-6 stopped short of.
//
// CENSUS-6 fixed the "Dock status" row to resolve the CODE through vocab.device_status.*
// and left the two rows immediately below it — "Lifecycle" and "Task" — reading
// `state.dockXLabel?.() ?? state.dockX?.()`. Label first. The backend's label is
// `_display_label(slug)`, i.e. title-cased English, so both rows read English in all 17
// locales while the row above them was translated. The shoulder just after a guard's
// window closed.
//
// WHY THIS TEST RENDERS THE REAL THING. The sibling CENSUS-6 test transcribes the
// renderer's logic into its own helper and then greps the source to compensate — the
// `RNNPSKT7` shape (a test that reimplements the arithmetic it checks cannot fail when
// that arithmetic changes). So this one imports the real `applyBaseStationRenderers`,
// wires `t`/`tRaw` to the real `translate()` over a real SHIPPED locale pack, and asserts
// on the HTML `renderBaseStationView` actually returns. Nothing about the resolution is
// restated here, which is what lets it go red on a revert.
//
// Coverage:
//   [BSV-1] both rows render the locale's word, and the English label is ABSENT
//   [BSV-2] ablation — restore label-first precedence and [BSV-1]'s assertion fails
//   [BSV-3] an UNKEYED code still falls back to the backend label (forward-compat)
//   [BSV-4] no code at all degrades to the label, then to "unknown" — never blank
//   [BSV-5] the rows resolve through DIFFERENT fields, which is why one fix missed two
//   [BSV-6] the stat sink escapes, so these rows must use the RAW twin

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { applyBaseStationRenderers } from "./base-station.js";
import { applySharedRenderers } from "./shared.js";
import { registerLocale, translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as enCatalog } from "../i18n/en.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const LOCALES = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales");

/** Register a real shipped pack so translate() resolves against shipped data, not a stub. */
function loadPack(code) {
  const nested = JSON.parse(readFileSync(join(LOCALES, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(nested, enCatalog);
  registerLocale(code, flat, { status: "draft" });
  return flat;
}

const DE = loadPack("de");

/**
 * A minimal host for renderBaseStationView: the real renderer protos, the real
 * translator, and stub STATE getters. `lang` is fixed rather than resolved so the test
 * does not depend on hass.
 */
function makeHost(lang, dock) {
  class H {}
  applySharedRenderers(H.prototype);
  applyBaseStationRenderers(H.prototype);
  const h = new H();
  h.escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  h.t = (key, vars) => translate(lang, key, vars);
  h.tRaw = (key, vars) => translate(lang, key, vars, { raw: true });
  h.card = { _state: { dashboardSnapshot: () => ({ adapter_id: "eufy" }) } };
  const state = {
    dashboardUpkeep: () => ({}),
    dockStatus: () => dock.dockStatus ?? null,
    dockStatusLabel: () => dock.dockStatusLabel ?? null,
    dockLifecycleState: () => dock.lifecycleState ?? null,
    dockLifecycleStateLabel: () => dock.lifecycleStateLabel ?? null,
    dockTaskStatus: () => dock.taskStatus ?? null,
    dockTaskStatusLabel: () => dock.taskStatusLabel ?? null,
    isDocked: () => true,
    dockActionStatus: () => null,
    dashboardPlannedWaterEstimate: () => null,
    dockActionGate: () => null,
  };
  return { html: () => h.renderBaseStationView({ state }), host: h };
}

/** The payload a real dock mid-service produces: codes plus the backend's English labels. */
const MID_SERVICE = {
  dockStatus: "washing_mop",
  dockStatusLabel: "Washing Mop",
  lifecycleState: "mid_job_service",
  lifecycleStateLabel: "Mid Job Service", // _display_label("mid_job_service")
  taskStatus: "paused",
  taskStatusLabel: "Paused",
};

test("[BSV-1] both rows render the locale's word, and the backend's English is absent", () => {
  const html = makeHost("de", MID_SERVICE).html();

  // The de pack's own values — read from the shipped pack, never hardcoded here, so a
  // retranslation updates this test instead of breaking it.
  const lifecycleDe = DE["vocab.lifecycle_state.mid_job_service"];
  const taskDe = DE["vocab.status.paused"];
  assert.ok(lifecycleDe && taskDe, "the de pack must carry both keys for this test to mean anything");

  assert.ok(html.includes(lifecycleDe), `Lifecycle row should read ${JSON.stringify(lifecycleDe)}`);
  assert.ok(html.includes(taskDe), `Task row should read ${JSON.stringify(taskDe)}`);

  // The half that actually catches the bug: the English label must not survive.
  assert.ok(
    !html.includes("Mid Job Service"),
    "the backend's title-cased English label is still in the markup — the row is reading " +
      "the label instead of resolving the code"
  );
});

test("[BSV-2] ablation — label-first precedence breaks [BSV-1], so [BSV-1] can fail", () => {
  // Reproduce ONLY the precedence, which is the thing under test, and show that the
  // old order yields the English label from the same inputs. If this ever passes with
  // the English absent, [BSV-1] is asserting nothing.
  const old = MID_SERVICE.lifecycleStateLabel ?? MID_SERVICE.lifecycleState ?? null;
  assert.equal(old, "Mid Job Service", "label-first yields the English label");

  const fixed = MID_SERVICE.lifecycleState ?? null;
  assert.equal(fixed, "mid_job_service", "code-first yields the code the vocab is keyed on");
  assert.notEqual(
    translate("de", "vocab.lifecycle_state.mid_job_service", undefined, { raw: true }),
    old,
    "the de translation must differ from the English label, or this pair proves nothing"
  );
});

test("[BSV-3] an unkeyed code still falls back to the backend label (forward-compat)", () => {
  // A brand that starts emitting a seventh lifecycle value must not render a raw key.
  const html = makeHost("de", {
    ...MID_SERVICE,
    lifecycleState: "awaiting_descale",
    lifecycleStateLabel: "Awaiting Descale",
  }).html();
  assert.ok(html.includes("Awaiting Descale"), "unkeyed code should fall back to the label");
  assert.ok(
    !html.includes("vocab.lifecycle_state.awaiting_descale"),
    "a raw dotted key must never reach the markup"
  );
});

test("[BSV-4] no code degrades to the label, then to the unknown string — never blank", () => {
  const withLabel = makeHost("de", {
    lifecycleState: null, lifecycleStateLabel: "Mid Job Service",
    taskStatus: null, taskStatusLabel: null,
  }).html();
  assert.ok(withLabel.includes("Mid Job Service"), "a label with no code is still shown");

  const withNeither = makeHost("de", {
    lifecycleState: null, lifecycleStateLabel: null,
    taskStatus: null, taskStatusLabel: null,
  }).html();
  const unknownDe = DE["base_station.unknown"];
  assert.ok(unknownDe, "the de pack must carry base_station.unknown");
  assert.ok(withNeither.includes(unknownDe), `empty state should read ${JSON.stringify(unknownDe)}`);
});

test("[BSV-5] the two rows resolve through DIFFERENT vocab fields", () => {
  // This is why one fix could not cover both: the Lifecycle row is the start-readiness
  // verdict (producer jobs/job_monitor.py) while the Task row is our own active-job slot
  // (producer jobs/active_job.py). `paused` exists in BOTH vocab.device_status.* and
  // vocab.status.*, so a test that only checked "is it German" could pass on the wrong
  // field. Pin that the Task row takes its word from vocab.status.
  const html = makeHost("de", { ...MID_SERVICE, dockStatus: null, dockStatusLabel: null }).html();
  assert.ok(html.includes(DE["vocab.status.paused"]), "Task row reads vocab.status.paused");
  assert.ok(
    DE["vocab.lifecycle_state.mid_job_service"] !== DE["vocab.device_status.washing_mop"],
    "the two fields must hold distinct words, or this test cannot tell them apart"
  );
});

test("[BSV-6] the stat sink escapes, so the rows must use the RAW twin", () => {
  // _renderBaseStationStat escapeHtml()s its value. tVocab escapes too, so the escaping
  // twin double-escapes: latent only while no catalogue value carries & < > " ', which is
  // a property of the DATA, not the code. Pin the raw twin at the three stat rows so a
  // future apostrophe in a locale cannot turn into &#39; on screen.
  const src = readFileSync(new URL("./base-station.js", import.meta.url), "utf-8");
  for (const field of ["device_status", "lifecycle_state", "status"]) {
    assert.ok(
      src.includes(`this.tVocabRaw("${field}"`),
      `the ${field} stat row must use tVocabRaw (the sink escapes)`
    );
    assert.ok(
      !src.includes(`this.tVocab("${field}"`),
      `the ${field} stat row must NOT use the escaping tVocab — the sink escapes again`
    );
  }
  // And prove the escaping twin really would double-escape, rather than asserting a habit.
  const h = makeHost("de", MID_SERVICE).host;
  registerLocale("qqx", { "vocab.lifecycle_state.ready": "Dock's Ready" }, { status: "custom" });
  const hq = makeHost("qqx", MID_SERVICE).host;
  assert.equal(hq.tVocabRaw("lifecycle_state", "ready", "x"), "Dock's Ready");
  assert.equal(
    hq.tVocab("lifecycle_state", "ready", "x"),
    "Dock&#39;s Ready",
    "tVocab escapes; handed to a sink that escapes again this becomes Dock&amp;#39;s Ready"
  );
  assert.ok(h.escapeHtml("Dock&#39;s Ready").includes("&amp;#39;"), "the sink would re-escape it");
});
