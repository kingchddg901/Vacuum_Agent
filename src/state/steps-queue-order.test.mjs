// Unit tests for the steps-queue order adapter (src/state/steps-queue-order.js) — the pure
// logic behind reordering the live ad-hoc queue (rooms + charge/wait breaks) as one list.
// This is the "here be dragons" translation: a reordered combined list -> room-order writes +
// a recomputed after_index per break. Run: node --test src/state/steps-queue-order.test.mjs
//
// Coverage:
//   [SQO-items]  getItems interleaves enabled rooms (by order) with breaks (by after_index)
//   [SQO-filter] getItems drops disabled rooms and sorts by order
//   [SQO-label]  break labels use the compact, translator-free format
//   [SQO-chain]  getOrderAdapter falls through to the prior adapter for non-"steps" scopes
//   [SQO-bmove]  persist on a BREAK move: no room-order write, breaks recomputed
//   [SQO-rmove]  persist on a ROOM move: rooms reindexed + persisted, breaks recomputed
//   [SQO-after]  persist recomputes after_index from the NEW order (break dragged earlier)
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyStepsQueueOrderState } from "./steps-queue-order.js";
import { registerLocale } from "../i18n/index.js";

function makeState({ rooms = [], breaks = [], prev, savedZones = [] } = {}) {
  const proto = {};
  proto.getOrderAdapter = prev ?? (() => null);
  applyStepsQueueOrderState(proto);
  const state = Object.create(proto);
  state.getRoomsForActiveMap = () => rooms;
  state.dashboardSnapshot = () => ({ queue_steps: { breaks } });
  state.savedZones = () => savedZones;
  return state;
}

const room = (id, order, extra = {}) => ({ id, order, enabled: true, name: `R${id}`, ...extra });
const chargeBreak = (after, pct) => ({ after_index: after, step: { type: "charge_wait", target_battery_percent: pct } });
const waitBreak = (after, min) => ({ after_index: after, step: { type: "wait", wait_minutes: min } });

// Build the persist context and capture what the adapter writes to each backing.
function persistCtx() {
  const calls = { room: undefined, breaks: undefined };
  const ctx = {
    _actions: {
      persistRoomOrdering: async (r) => { calls.room = r; },
      persistQueueBreaks: async (b) => { calls.breaks = b; },
    },
  };
  return { ctx, calls };
}

test("[SQO-items] interleaves rooms (by order) with breaks (by after_index)", () => {
  const state = makeState({
    rooms: [room("1", 1), room("2", 2), room("3", 3)],
    breaks: [chargeBreak(1, 90), waitBreak(2, 20)],
  });
  const adapter = state.getOrderAdapter("steps");
  const items = adapter.getItems.call(state);

  assert.deepEqual(items.map((i) => i._id), [
    "room:1", "break:0", "room:2", "break:1", "room:3",
  ]);
  assert.deepEqual(items.map((i) => i._seq), [1, 2, 3, 4, 5]);
  // breakIndex tracks the raw breaks-list index (== the after_index-sorted index the card uses).
  assert.equal(items[1].breakIndex, 0);
  assert.equal(items[3].breakIndex, 1);
});

test("[SQO-filter] drops disabled rooms and sorts by order", () => {
  const state = makeState({
    rooms: [room("3", 3), room("1", 1), room("2", 2, { enabled: false })],
    breaks: [],
  });
  const items = state.getOrderAdapter("steps").getItems.call(state);
  assert.deepEqual(items.map((i) => i._id), ["room:1", "room:3"]);
});

test("[SQO-label] break labels compose the compact format with the resolved unit strings", () => {
  const state = makeState({
    rooms: [room("1", 1), room("2", 2)],
    breaks: [chargeBreak(1, 85), waitBreak(1, 15)],
  });
  const items = state.getOrderAdapter("steps").getItems.call(state);
  const labels = items.filter((i) => i.kind === "break").map((i) => i._label);
  // Default hass = undefined → resolveLang → "en" → % and min.
  assert.deepEqual(labels, ["⚡ 85%", "⏱ 15 min"]);
});

test("[SQO-label-i18n] break labels use the ACTUAL translated unit — the bite prior fix missed", () => {
  // Bite: the prior fix used `this.t?.(...) ?? "%"` — state has NO t() method,
  // so the optional chain always yielded undefined and the ?? fallback silently
  // kept the English literal. Set the state's hass to an ar locale and prove the
  // Arabic unit is actually threaded through.
  //
  // Node test env has only en registered at import time (no loadLocale runs);
  // register a minimal ar catalog inline so the assertion actually bites.
  registerLocale("ar", { "run_profiles.minutes_unit": "دقيقة",
                         "metrics.unit_percent": "%" });
  const state = makeState({
    rooms: [room("1", 1)],
    breaks: [chargeBreak(1, 85), waitBreak(1, 15)],
  });
  // ar is draft in LOCALE_STATUS, so resolveLang would fall back to en on the
  // system-language path. A per-dashboard PIN bypasses the draft-gate — use
  // that so the test proves the ar path.
  state.hass = { locale: { language: "en" } };
  state.config = { i18n: { locale: "ar" } };
  const items = state.getOrderAdapter("steps").getItems.call(state);
  const labels = items.filter((i) => i.kind === "break").map((i) => i._label);
  // If the fix regresses to `this.t?.(...)`, this ALWAYS reads "⏱ 15 min".
  assert.equal(labels[0], "⚡ 85%", "% unit still % in ar (pack value)");
  assert.equal(labels[1], "⏱ 15 دقيقة", "minutes_unit MUST be the ar 'دقيقة', not English 'min'");
});

test("[SQO-zone] a zone break resolves its ids to saved-zone names in the label", () => {
  const state = makeState({
    rooms: [room("1", 1), room("2", 2)],
    breaks: [{ after_index: 1, step: { type: "zone", zone_ids: ["z1", "z2"] } }],
    savedZones: [{ id: "z1", name: "Kennel" }, { id: "z2", name: "Entry" }],
  });
  const items = state.getOrderAdapter("steps").getItems.call(state);
  const zone = items.find((i) => i.kind === "break");
  assert.equal(zone._label, "🎯 Kennel, Entry");
  assert.equal(zone._id, "break:0");
});

test("[SQO-chain] non-steps scopes fall through to the prior adapter", () => {
  const prev = (scope) => (scope === "rooms" ? { scope: "rooms" } : null);
  const state = makeState({ prev });
  assert.deepEqual(state.getOrderAdapter("rooms"), { scope: "rooms" });
  assert.equal(state.getOrderAdapter("nope"), null);
  assert.equal(state.getOrderAdapter("steps").scope, "steps");
});

test("[SQO-bmove] a break move recomputes breaks but does NOT rewrite room order", async () => {
  const state = makeState({ rooms: [room("1", 1), room("2", 2), room("3", 3)] });
  const adapter = state.getOrderAdapter("steps");
  // Break dragged from after room 1 to after room 2.
  const nextItems = [
    { kind: "room", room: { id: "1", order: 1 } },
    { kind: "room", room: { id: "2", order: 2 } },
    { kind: "break", breakIndex: 0, step: { type: "charge_wait", target_battery_percent: 90 } },
    { kind: "room", room: { id: "3", order: 3 } },
  ];
  const { ctx, calls } = persistCtx();
  await adapter.persist.call(ctx, nextItems, { itemId: "break:0" });

  assert.equal(calls.room, undefined, "room order must NOT be rewritten on a break move");
  assert.deepEqual(calls.breaks, [
    { after_index: 2, break_type: "charge_wait", target_battery_percent: 90 },
  ]);
});

test("[SQO-rmove] a room move reindexes rooms AND recomputes break after_index", async () => {
  const state = makeState({ rooms: [room("1", 1), room("2", 2), room("3", 3)] });
  const adapter = state.getOrderAdapter("steps");
  // Room 3 dragged to the front; the charge break stays visually after what is now the 2nd room.
  const nextItems = [
    { kind: "room", room: { id: "3", order: 3 } },
    { kind: "room", room: { id: "1", order: 1 } },
    { kind: "break", breakIndex: 0, step: { type: "charge_wait", target_battery_percent: 90 } },
    { kind: "room", room: { id: "2", order: 2 } },
  ];
  const { ctx, calls } = persistCtx();
  await adapter.persist.call(ctx, nextItems, { itemId: "room:3" });

  assert.deepEqual(calls.room.map((r) => [r.id, r.order]), [["3", 1], ["1", 2], ["2", 3]]);
  assert.deepEqual(calls.breaks, [
    { after_index: 2, break_type: "charge_wait", target_battery_percent: 90 },
  ]);
});

test("[SQO-zpersist] moving a zone preserves its zone_ids through persist (else it drops)", async () => {
  const state = makeState({ rooms: [room("1", 1), room("2", 2), room("3", 3)] });
  const adapter = state.getOrderAdapter("steps");
  // Zone dragged to sit after room 2.
  const nextItems = [
    { kind: "room", room: { id: "1", order: 1 } },
    { kind: "room", room: { id: "2", order: 2 } },
    { kind: "break", breakIndex: 0, step: { type: "zone", zone_ids: ["z1", "z2"] } },
    { kind: "room", room: { id: "3", order: 3 } },
  ];
  const { ctx, calls } = persistCtx();
  await adapter.persist.call(ctx, nextItems, { itemId: "break:0" });
  assert.deepEqual(calls.breaks, [
    { after_index: 2, break_type: "zone", zone_ids: ["z1", "z2"] },
  ]);
});

test("[SQO-after] after_index is derived from the NEW order (break dragged before all rooms clamps to 1)", async () => {
  const state = makeState({ rooms: [room("1", 1), room("2", 2)] });
  const adapter = state.getOrderAdapter("steps");
  // Wait break dragged ahead of every room -> 0 rooms before it -> clamp to 1.
  const nextItems = [
    { kind: "break", breakIndex: 0, step: { type: "wait", wait_minutes: 20 } },
    { kind: "room", room: { id: "1", order: 1 } },
    { kind: "room", room: { id: "2", order: 2 } },
  ];
  const { ctx, calls } = persistCtx();
  await adapter.persist.call(ctx, nextItems, { itemId: "break:0" });
  assert.deepEqual(calls.breaks, [{ after_index: 1, break_type: "wait", wait_minutes: 20 }]);
});

/* =========================================================
   THE GLOBE CHANNEL — state has no _langOverride of its own
   ========================================================= */

test("[SQO-globe] the break label follows the CARD's globe language, not just HA/pin", () => {
  // Round-2 adversary finding. resolveLang(hass, config) resolves the HA
  // language or the dashboard pin — it cannot see the per-user globe, which
  // lives on the card element. A user whose HA runs English but who picks
  // Arabic on the globe got an Arabic modal with English chips inside it.
  // VacuumCardState.i18nLanguage() is the channel; this proves the adapter
  // reads it in preference to hass/config.
  registerLocale("ar", { "run_profiles.minutes_unit": "دقيقة",
                         "metrics.unit_percent": "%" });
  const state = makeState({
    rooms: [room("1", 1)],
    breaks: [waitBreak(1, 15)],
  });
  state.hass = { locale: { language: "en" } };   // HA is English
  state.config = {};                             // no dashboard pin
  state.i18nLanguage = () => "ar";               // ...but the globe says Arabic
  const items = state.getOrderAdapter("steps").getItems.call(state);
  const label = items.find((i) => i.kind === "break")._label;
  assert.equal(label, "⏱ 15 دقيقة",
    "the chip must follow the globe; reading hass/config alone yields English 'min'");
});

test("[SQO-globe-wired] VacuumCardState exposes the channel AND main.js installs it", async () => {
  // A seam nobody wires is decorative. The fallback inside i18nLanguage() is
  // the OLD hass/config behaviour, so a missing installation degrades silently
  // to exactly the defect this fixes — which is why the wiring itself is pinned
  // here rather than left to inspection.
  const { VacuumCardState } = await import("./index.js");
  const s = new VacuumCardState({ locale: { language: "en" } }, {});
  assert.equal(typeof s.setLangResolver, "function", "state must expose setLangResolver");
  assert.equal(typeof s.i18nLanguage, "function", "state must expose i18nLanguage");

  // Resolver wins when installed...
  s.setLangResolver(() => "ar");
  assert.equal(s.i18nLanguage(), "ar");
  // ...and an empty/absent answer falls back to hass+config rather than throwing.
  s.setLangResolver(() => "");
  assert.equal(s.i18nLanguage(), "en");
  s.setLangResolver(null);
  assert.equal(s.i18nLanguage(), "en");

  const fs = await import("node:fs");
  const main = fs.readFileSync(new URL("../main.js", import.meta.url), "utf-8");
  assert.match(main, /setLangResolver\?\.\(\s*\(\)\s*=>\s*this\._i18nLanguage\(\)\s*\)/,
    "main.js must install the resolver — without it every state-level renderer silently ignores the globe");
});
