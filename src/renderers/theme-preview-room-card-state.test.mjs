// Run: node --test src/renderers/theme-preview-room-card-state.test.mjs
//
// THE THEME PREVIEW RENDERS REAL ROOM CARDS WITH NO STATE. That is not an
// accident of the preview — it is the whole design: `.evcc-room-grid` and
// `renderRoomCard` are the real classes and the real renderer, so a token edited
// in the theme editor moves the specimen exactly as it moves the Rooms view.
// `_themePreviewRoomGrid(rooms, state = null)` has defaulted that state to null
// since 33ad5ef7 ("seven previews stop drawing pictures and render the product"),
// and six of its seven call sites pass one argument. The preview has been handing
// `renderRoomCard` no state for longer than that: `_renderFloorPreviewCard` has
// passed an explicit `null` since v0.9.0.
//
// d32aa092 then added three reads of a NEW accessor, `isBrandDefaultSetting`,
// and wrote them bare — `state.isBrandDefaultSetting(...)` — while every other
// read on that parameter in the same function is `state?.x?.()`. The result
// shipped in 2.4.0: the entire Theme view rendered as `shell.view_error`, every
// frame, on a real box.
//
// WHY NOTHING CAUGHT IT — and it is NOT that the assertions were too weak.
// `smoke.spec.mjs` already asserted `res.ok`, and the harness's own `render()`
// (harness/mount-entry.js — it calls `renderView(ctx)` inside its own try/catch,
// not main.js's `_render`) sets that false on a throw. That assertion was
// sufficient. THE CRASH WAS SIMPLY NEVER REACHED: under the plain stub the Theme
// view's body renders EMPTY, because the tab reads `_ensureThemeState()` and
// `resolvedTheme()` and stub-state.js deliberately does not hand-write those.
// Measured on the harness: `ok:true`, ~4.4k characters in the view-root, and no
// `.evcc-theme-preview-pane` in the tree at all — header and footer chrome,
// sailing past a `viewLen > 20` check.
//
// `renderThemeEditor` already existed to fix exactly this, after the same trap
// made the mobile-layout probe "report a clean shell having measured nothing".
// That lesson was applied there and never propagated to smoke.
//
// Coverage (TPS = Theme Preview State)
// ------------------------------------
// The absence has THREE distinct shapes and a signed test for one of them does
// not carry the others, so each is injected separately:
//   [TPS-1] state === null          — the grid default, 6 of 7 call sites
//   [TPS-2] state === {}            — an object with no such method
//   [TPS-3] state === _themePreviewState() — the real preview stub
// then the two directions of the predicate, to prove the guard did not neuter it:
//   [TPS-4] a live state answering TRUE  hides the chips
//   [TPS-5] a live state answering FALSE shows them
// and the gate that bites on the original mistake:
//   [TPS-6] every `state` accessor renderRoomCard reads is DECLARED by
//           _themePreviewState — the replica set, reconciled.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { applyRoomsRenderers } from "./rooms.js";
import { applyThemePreviewRenderers } from "./theme-preview.js";

/* ---- a renderer host with the deps renderRoomCard reads -------------------- */

function makeRenderers() {
  const proto = {};
  applyRoomsRenderers(proto);

  const r = Object.create(proto);
  r.t = (key, vars) => (vars ? `${key}:${JSON.stringify(vars)}` : key);
  r.tVocabRaw = (_family, _value, fallback) => String(fallback ?? "");
  r.escapeHtml = (v) => String(v ?? "");
  r.renderConfidenceChip = () => "";
  r._formatLearningMinutes = (m) => String(m);
  // The card-level state, a DIFFERENT object from the `state` parameter: the
  // drag/active-run reads go through `this.card._state`, which the preview host
  // always has. Kept non-null here so a failure can only come from `state`.
  r.card = { _state: {
    orderDragItemId: () => null,
    orderDragOverItemId: () => null,
    hasActiveRun: () => false,
  } };
  return r;
}

const ROOM = {
  id: 9001,
  name: "Kitchen",
  slug: "kitchen",
  enabled: true,
  order: 1,
  clean_mode: "vacuum_and_mop",
  fan_speed: "max",
  water_level: "high",
  clean_intensity: "deep",
  clean_passes: 2,
  edge_mopping: true,
  floor_type: "wood",
};

function previewState(over = {}) {
  const proto = {};
  applyThemePreviewRenderers(proto);
  return Object.create(proto)._themePreviewState(over);
}

/* ---- [TPS-1..3] the three shapes of absence -------------------------------- */

test("[TPS-1] state = null (the grid default, 6 of 7 call sites) renders a card", () => {
  const html = makeRenderers().renderRoomCard(ROOM, null);
  assert.match(html, /evcc-room-card/, "no card came back for the null state");
});

test("[TPS-2] state = {} (present, but no such method) renders a card", () => {
  const html = makeRenderers().renderRoomCard(ROOM, {});
  assert.match(html, /evcc-room-card/);
});

test("[TPS-3] state = the real _themePreviewState() renders a card", () => {
  const html = makeRenderers().renderRoomCard(ROOM, previewState());
  assert.match(html, /evcc-room-card/);
});

/* ---- [TPS-4..5] the predicate still decides, both ways --------------------- */
//
// Guarding a read is one keystroke from disabling it. These two pin the
// behaviour the guard must preserve: the chip set has to MOVE with the answer,
// so neither a dead predicate nor an always-on one passes.

// The chip text is the formatter's title-cased fallback ("Max", not "max").
// Asserting the lowercase token made TPS-4 pass against a chip that WAS there,
// which is the whole reason a doesNotMatch needs its positive twin below.
const CHIP = { suction: /Max/, route: /Deep/, water: /High/ };

test("[TPS-4] a state answering TRUE hides all three default-gated chips", () => {
  const html = makeRenderers().renderRoomCard(ROOM, {
    isBrandDefaultSetting: () => true,
  });
  assert.doesNotMatch(html, CHIP.suction, "suction chip rendered for a declared default");
  assert.doesNotMatch(html, CHIP.route,   "route chip rendered for a declared default");
  assert.doesNotMatch(html, CHIP.water,   "water chip rendered for a declared default");
});

test("[TPS-5] a state answering FALSE shows all three", () => {
  const html = makeRenderers().renderRoomCard(ROOM, {
    isBrandDefaultSetting: () => false,
  });
  assert.match(html, CHIP.suction);
  assert.match(html, CHIP.route);
  assert.match(html, CHIP.water);
});

test("[TPS-5b] absent predicate renders the same chips as one answering FALSE", () => {
  // The preview's contract, stated as an equality rather than a hope: a missing
  // accessor must degrade to "not a default", which is what the preview wants
  // AND what the card did before d32aa092.
  const r = makeRenderers();
  assert.equal(
    r.renderRoomCard(ROOM, null),
    r.renderRoomCard(ROOM, { isBrandDefaultSetting: () => false }),
    "null state and an explicit false disagree — the guard changed the picture",
  );
});

/* ---- [TPS-6] the replica set, reconciled ---------------------------------- */

test("[TPS-6] every `state` accessor renderRoomCard reads is declared by _themePreviewState", () => {
  const src = readFileSync(new URL("./rooms.js", import.meta.url), "utf8");

  const start = src.indexOf("proto.renderRoomCard = function");
  assert.ok(start > 0, "could not find renderRoomCard — this gate is not reading it");
  const end = src.indexOf("\n};", start);
  assert.ok(end > start, "could not find the end of renderRoomCard");
  // Comments out FIRST: this gate matched `state?.x?.()` out of a comment that
  // documents the very convention it enforces. A gate a comment can steer is
  // not a gate. The two assertions below prove the stripping did not eat
  // everything, so a stripping accident goes red instead of quiet.
  const body = src.slice(start, end)
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/\/\/.*/g, " ");

  // `\bstate` does not match inside `_state`, so the `this.card?._state?.x`
  // reads — a different object, always present — are correctly left out.
  const reads = new Set(
    [...body.matchAll(/\bstate\??\.\s*([A-Za-z_$][\w$]*)/g)].map((m) => m[1]),
  );
  assert.ok(reads.size > 0, "found no state reads at all — the pattern is broken");
  assert.ok(
    reads.has("isBrandDefaultSetting"),
    "the read this gate exists for is gone; if that is deliberate, retire the gate",
  );

  const declared = new Set(Object.keys(previewState()));
  const missing = [...reads].filter((k) => !declared.has(k));

  assert.deepEqual(
    missing, [],
    `renderRoomCard reads state accessors the theme preview does not declare: ` +
    `${missing.join(", ")}. Add them to _themePreviewState — an undeclared ` +
    `accessor is what took the Theme view down for all of 2.4.0.`,
  );
});
