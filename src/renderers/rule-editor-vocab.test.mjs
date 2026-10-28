// Run: node --test src/renderers/rule-editor-vocab.test.mjs
//
// RUL — the rule editor's 22 CARD-LOCAL words.
//
// Every other sink in the i18n census had a backend `*_label` field beside it, which is
// what made each one findable: a label arriving in English is a thing you can look for.
// These 22 had nothing. `ruleOperatorGroups` and `ruleEntityDescriptor` composed their own
// English in the STATE layer — `{label: "State"}`, `{label: "Is ON"}`, `category: "boolean"`
// — and the renderer printed it. No field to notice, no vocabulary to miss, no key to be
// absent from. They were the last English strings in the editor.
//
// The fix follows the pattern `state/rooms.js`'s block reasons already set: the state layer
// returns a CODE and stays i18n-free, the renderer localizes, and the state's English rides
// along as `resolveCodedLabel`'s message — so an operator added without a key reads as
// English rather than as a dotted key.
//
// Coverage:
//   [RUL-1] the operator GROUP headings localize
//   [RUL-2] the twelve operator chips localize
//   [RUL-3] the entity TYPE in the help line localizes — "Type: boolean" was the string
//   [RUL-4] a code with no key falls back to the state layer's English, never a key
//   [RUL-5] the state layer still carries both the code and the English
//   [RUL-6] RTL packs get WORDS for the comparison operators, LTR packs keep the symbol
//   [RUL-7] the help line escapes exactly once — the bits are joined raw
//   [RUL-8] every operator the DESCRIPTOR can offer has a key (the completeness gate)

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { applySharedRenderers } from "./shared.js";
import { applyRoomRulesRenderers } from "./room-rules.js";
import { applyRoomRulesState } from "../state/room-rules.js";
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
const HE = loadPack("he");

function makeHost(lang = "de") {
  class H {}
  applySharedRenderers(H.prototype);
  applyRoomRulesRenderers(H.prototype);
  const h = new H();
  h.escapeHtml = (s) =>
    String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  h.t = (key, vars) => translate(lang, key, vars);
  h.tRaw = (key, vars) => translate(lang, key, vars, { raw: true });
  h.card = { _state: { dashboardSnapshot: () => ({ adapter_id: "eufy" }) } };
  return h;
}

/**
 * The REAL state layer over one stub entity.
 *
 * `entity(id)` is the dependency, NOT `hass.states` — `ruleEntityDescriptor` reads
 * `this.entity?.(id)`. A first version of this fixture populated `hass.states` and the
 * descriptor came back with `entityExists: false`, which silently routed every render to
 * the "entity unavailable" branch and made four assertions about a string that was never
 * produced. Fixtures agree with the CALLER's actual reads, not with the shape you expect.
 */
function makeState(entityId, attrs = {}, stateValue = "on") {
  const proto = {};
  applyRoomRulesState(proto);
  const s = Object.create(proto);
  const entity = { entity_id: entityId, state: stateValue, attributes: attrs };
  s.hass = { states: { [entityId]: entity } };
  s.entity = (id) => (id === entityId ? entity : null);
  s._roomRulesDraft = { entity_id: entityId };
  return s;
}

/* ------------------------------------------------------------------- the three sinks */

/** The real editor block, rendered through the real state layer. */
function renderEditor(host, state, entityId) {
  const draft = { kind: "condition", entity_id: entityId, operator: "" };
  const html = host._renderRuleEditor(state, { name: "Küche" }, draft, "new", null);
  assert.ok(html.includes("evcc-rule-operator-group"), "the operator block did not render");
  return html;
}

test("[RUL-1] the operator GROUP headings localize", () => {
  const h = makeHost();
  const s = makeState("binary_sensor.door", { friendly_name: "Door" });
  const groups = s.ruleOperatorGroups(s._roomRulesDraft);
  assert.ok(groups.length, "the state layer must offer groups for a binary_sensor");
  // Rendered through `_renderRuleEditor` — the REAL block, so the call site counts. An
  // earlier draft guessed a function name, found nothing, and guarded the render assertion
  // behind `if (html)`, which skipped it silently: a vacuous branch dressed as coverage.
  const html = renderEditor(h, s, "binary_sensor.door");
  for (const group of groups) {
    const key = `room_rules.operator_group.${group.code}`;
    assert.ok(key in enCatalog, `${group.code} has no key`);
    assert.ok(DE[key], `${key} is untranslated in de`);
    assert.notEqual(DE[key], group.label, `${key}: de holds the state layer's English`);
    assert.ok(html.includes(DE[key]), `${group.code} did not reach the render`);
    assert.ok(!html.includes(`>${group.label}<`), `the English "${group.label}" still renders`);
  }
});

test("[RUL-2] the twelve operator chips localize", () => {
  const h = makeHost();
  // A numeric sensor offers the comparison group; a binary_sensor offers state/existence.
  // Between them the two cover every operator a real entity can present.
  const seen = new Set();
  for (const [entityId, attrs, value] of [
    ["sensor.temp", { friendly_name: "Temp", unit_of_measurement: "°C" }, "21.5"],
    ["binary_sensor.door", { friendly_name: "Door" }, "on"],
    ["select.mode", { friendly_name: "Mode", options: ["a", "b"] }, "a"],
  ]) {
    const s = makeState(entityId, attrs, value);
    const html = renderEditor(h, s, entityId);
    for (const op of s.ruleOperatorGroups(s._roomRulesDraft).flatMap((g) => g.operators)) {
      const key = `room_rules.operator.${op.value}`;
      assert.ok(key in enCatalog, `${op.value} has no key`);
      assert.ok(DE[key], `${key} is untranslated in de`);
      assert.ok(html.includes(h.escapeHtml(DE[key])), `${op.value} did not reach the chip`);
      seen.add(op.value);
    }
  }
  assert.ok(seen.size >= 10, `only ${seen.size} operators were exercised: ${[...seen]}`);
});

test("[RUL-3] the entity TYPE in the help line localizes", () => {
  const h = makeHost();
  // "Type: boolean" was the literal string, beside a "Type:" that was translated.
  for (const [entityId, attrs, value, category] of [
    ["binary_sensor.door", { friendly_name: "Door" }, "on", "boolean"],
    ["select.mode", { friendly_name: "Mode", options: ["a", "b"] }, "a", "enum"],
    ["number.level", { friendly_name: "Level" }, "3", "numeric"],
    ["sensor.name", { friendly_name: "Name" }, "kitchen", "text"],
  ]) {
    const s = makeState(entityId, attrs, value);
    const descriptor = s.ruleEntityDescriptor(entityId);
    assert.equal(descriptor.category, category, `${entityId} should be ${category}`);
    const html = h._renderRuleEntityHelp(descriptor);
    const expected = DE[`room_rules.entity_category.${category}`];
    assert.ok(expected, `no de translation for ${category}`);
    assert.ok(html.includes(expected), `${category} did not reach the help line`);
    assert.ok(!html.includes(`: ${category}`), `the raw code "${category}" still renders`);
  }
});

/* ------------------------------------------------------------------------- contract */

test("[RUL-4] a code with no key falls back to the state layer's English", () => {
  const h = makeHost();
  // The reason the state layer KEEPS its English rather than returning bare codes: an
  // operator or category added here before its key exists must read, not show a dotted key.
  // `entityId` is load-bearing in this literal: _renderRuleEntityHelp returns the
  // "choose an entity" line without it, which would pass the assertions below for the
  // wrong reason.
  const html = h._renderRuleEntityHelp({
    entityId: "sensor.thing", entityExists: true, entityLabel: "Thing",
    category: "quaternion", options: [],
  });
  assert.ok(html.includes("quaternion"), "an unkeyed category must still say something");
  assert.ok(!html.includes("room_rules.entity_category"), "and never a bare key");
});

test("[RUL-5] EVERY group in the state layer's table has a code and a key", () => {
  // THE COMPLETENESS GATE FOR GROUPS, and it reads the whole table rather than one
  // entity's. `ruleOperatorGroups` FILTERS by what the descriptor allows, so a
  // binary_sensor never offers the numeric group — which is why an earlier version of this
  // file could not see `code: "numeric"` being deleted from the state layer at all. Same
  // reason [RUL-8] reads ALL_OPERATORS instead of walking one entity's chips.
  const src = readFileSync(join(HERE, "..", "state", "room-rules.js"), "utf8");
  const table = src.slice(src.indexOf("const groups = ["), src.indexOf("return groups"));
  const codes = [...table.matchAll(/code:\s*"([a-z_]+)"/g)].map((m) => m[1]);
  const labels = [...table.matchAll(/^\s*label:\s*"([^"]+)"/gm)].map((m) => m[1]);
  assert.ok(codes.length >= 5, `only ${codes.length} group code(s) found: ${codes}`);
  assert.equal(codes.length, labels.length,
    `${codes.length} codes but ${labels.length} group labels — a group is missing one`);
  for (const code of codes) {
    const key = `room_rules.operator_group.${code}`;
    assert.ok(key in enCatalog, `${code} has no key`);
    assert.ok(DE[key], `${key} is untranslated in de`);
  }

  // And the runtime shape, for the groups one entity does offer.
  const s = makeState("binary_sensor.door", { friendly_name: "Door" });
  const offered = s.ruleOperatorGroups(s._roomRulesDraft);
  assert.ok(offered.length, "a binary_sensor must offer at least one group");
  for (const group of offered) {
    assert.ok(group.code, "every group needs a code for the renderer to key on");
    assert.ok(group.label, "and its English, which is the renderer's fallback");
    for (const op of group.operators) {
      assert.ok(op.value && op.label, `${group.code}: an operator is missing value or label`);
    }
  }
});

test("[RUL-6] RTL packs get WORDS for the comparison operators", () => {
  // This is what earns those four their keys. English keeps the symbol — correct in most
  // scripts — but a bare ">" is ambiguous in a right-to-left layout, so ar and he carry
  // words. Without that difference the keys would be 68 identical values and a ratchet
  // entry, i.e. a preference.
  for (const op of ["gt", "gte", "lt", "lte"]) {
    const key = `room_rules.operator.${op}`;
    assert.equal(DE[key], enCatalog[key], `de should keep the symbol for ${op}`);
    assert.notEqual(HE[key], enCatalog[key], `he must NOT be the bare symbol for ${op}`);
    assert.ok(/[֐-׿]/.test(HE[key]), `he ${op} should be Hebrew words, got ${HE[key]}`);
  }
  // And the non-symbol operators differ in de too, or the family would be pointless.
  for (const op of ["is_on", "exists", "equals", "in"]) {
    const key = `room_rules.operator.${op}`;
    assert.notEqual(DE[key], enCatalog[key], `de holds the English for ${op}`);
  }
});

test("[RUL-7] the help line escapes exactly once", () => {
  // `bits.join(" • ")` is interpolated RAW, so each bit must arrive already escaped once.
  // tRaw inside, escapeHtml at the call site. A translated category carrying an apostrophe
  // is the input that tells a single escape from a double one.
  registerLocale("xx-rule", { "room_rules.entity_category.enum": "Choix d'options" }, { status: "custom" });
  const h = makeHost("xx-rule");
  const html = h._renderRuleEntityHelp({
    entityId: "select.mode", entityExists: true, entityLabel: "Mode",
    category: "enum", options: ["a", "b"],
  });
  assert.ok(html.includes("Choix d&#39;options"), "escaped once");
  assert.ok(!html.includes("&amp;#39;"), "and never twice");
});

test("[RUL-8] every operator the descriptor can offer has a key", () => {
  // THE COMPLETENESS GATE, and it reads the state layer's own tables rather than a list
  // here. `ruleOperatorGroups` filters by what the descriptor allows, so walking one
  // entity's groups only proves that entity's operators — ALL_OPERATORS is the union.
  const src = readFileSync(join(HERE, "..", "state", "room-rules.js"), "utf8");
  const block = src.match(/const ALL_OPERATORS\s*=\s*\[([\s\S]*?)\]/);
  assert.ok(block, "ALL_OPERATORS not found — did it move or get renamed?");
  const all = [...block[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.ok(all.length >= 10, `only ${all.length} operators found — the scan is wrong`);
  const missing = all.filter((op) => !(`room_rules.operator.${op}` in enCatalog));
  assert.deepEqual(missing, [], `operators with no key: ${missing.join(", ")}`);
  // Categories likewise: the five `ruleEntityDescriptor` can assign.
  for (const category of ["boolean", "enum", "numeric", "text", "unknown"]) {
    assert.ok(`room_rules.entity_category.${category}` in enCatalog, `${category} has no key`);
  }
});
