// Run: node --test src/theme-tokens/per-card-tokens.test.mjs
//
// [PCT-*] THE PER-CARD RUNG — one more step on the chain, and the three ways it can lie.
//
// WHY IT EXISTS. Chris's call 2026-11-16, and his reason is the shape of the whole
// feature: "yaml is fine for some but most of the reason i made the theme editor is to
// not need it for most people". So these are real registry tokens with real controls,
// not a var() a theme author could discover. That raises the stakes on three things a
// green suite would otherwise miss:
//
//   1. THE KEY LIST IS SPELLED OUT, because scripts/check-styles.mjs builds its
//      inventory by TEXT-SCANNING this directory — runtime-built keys are invisible to
//      it and every var() site reads as dangling (measured: the build failed with
//      exactly 51, the site count). Spelled-out keys and a derived shape are two halves
//      that can drift, so [PCT-1] pins them together.
//   2. A TOKEN WITH NO var() SITE IS A CONTROL THAT MOVES NOTHING. It renders in the
//      editor, it stores a value, it does nothing, and nothing anywhere reports it.
//      [PCT-3] is the reachability half.
//   3. THE RUNG ORDER IS THE WHOLE FEATURE. Per-card must be tried BEFORE the shared
//      token, or the per-card control can never win and the group is decorative.
//      [PCT-4] pins the direction, which [PCT-3] cannot see.
//
// Coverage
// --------
// [PCT-1] PER_CARD_KEYS is exactly what READS implies — no missing, no extra
// [PCT-2] each per-card token's SHAPE is its shared sibling's, differing only in key/group
// [PCT-3] every per-card key is actually read by that card's CSS
// [PCT-4] it is read as the OUTER rung, with the shared token as its fallback

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  PER_CARD_KEYS, PER_CARD_TOKENS, PER_CARD_GROUP, DASHBOARD_CARD_TOKENS,
} from "./cards.js";
import { THEME_GROUPS } from "./groups.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SRC = {
  room: readFileSync(join(REPO, "src", "room-card.js"), "utf8"),
  dashboard: readFileSync(join(REPO, "src", "cards", "dashboard-card.js"), "utf8"),
  profile: readFileSync(join(REPO, "src", "cards", "profile-card.js"), "utf8"),
};

/** Which of the eight each card reads — stated INDEPENDENTLY of cards.js on purpose.
 *  Importing READS from the module under test would make [PCT-1] compare a thing to
 *  itself and pass whatever either side said. This copy is the measurement. */
const EXPECTED = {
  room: ["frame-border-width", "frame-shadow", "action-glow", "font-scale",
         "header-padding", "field-gap"],
  dashboard: ["frame-border-width", "frame-shadow", "action-glow", "font-scale",
              "header-padding", "field-gap", "row-padding", "section-padding"],
  profile: ["frame-border-width", "frame-shadow", "action-glow", "font-scale"],
};

const split = (key) => {
  for (const id of Object.keys(EXPECTED)) {
    const p = `--evcc-card-${id}-`;
    if (key.startsWith(p)) return { id, thing: key.slice(p.length) };
  }
  throw new Error(`no card id in ${key}`);
};

test("[PCT-1] PER_CARD_KEYS is exactly what the cards read — no missing, no extra", () => {
  // THE RED INPUT: add a ninth thing to one card's CSS and forget its key, or leave a
  // key behind after dropping a control. Either way the two halves disagree and nothing
  // else notices: a missing key is a control that never appears, an extra one is a
  // control that moves nothing.
  const want = Object.entries(EXPECTED)
    .flatMap(([id, things]) => things.map((t) => `--evcc-card-${id}-${t}`))
    .sort();
  assert.deepEqual([...PER_CARD_KEYS].sort(), want);
  assert.equal(PER_CARD_KEYS.length, 18, "6 room + 8 dashboard + 4 profile");
  assert.equal(new Set(PER_CARD_KEYS).size, PER_CARD_KEYS.length, "no duplicate keys");
});

test("[PCT-2] each per-card token's shape is its shared sibling's", () => {
  // THE RED INPUT: restating {label, type, min, max, step} per card instead of deriving
  // it. This group carries TWO deliberately explicit ranges (0–8 step 0.5 for the border,
  // 0.5–2 step 0.05 for the text scale) with the reasoning written beside them, and a
  // parallel table is exactly how one gets retuned and the other does not.
  const shared = new Map(DASHBOARD_CARD_TOKENS.map((t) => [t.key.replace("--evcc-card-", ""), t]));
  for (const tok of PER_CARD_TOKENS) {
    const { id, thing } = split(tok.key);
    const base = shared.get(thing);
    assert.ok(base, `${tok.key} has no shared sibling`);
    const strip = (t) => { const { key, group, ...rest } = t; return rest; };
    assert.deepEqual(strip(tok), strip(base),
      `${tok.key} must match its sibling in label, type and range`);
    assert.equal(tok.group, PER_CARD_GROUP[id]);
    assert.ok(THEME_GROUPS.includes(tok.group), `${tok.group} must be a registered group`);
  }
});

test("[PCT-3] every per-card key is actually read by that card's CSS", () => {
  // THE RED INPUT: mint the token and forget the var() site. The control renders, stores
  // a value and moves nothing — a correct token with zero callers passes every test
  // about the token. This is the half that notices.
  const missing = PER_CARD_KEYS.filter((key) => !SRC[split(key).id].includes(`var(${key},`));
  assert.deepEqual(missing, [],
    "these per-card tokens have a control in the editor and no var() site in the card " +
    "they name, so moving them does nothing:\n  " + missing.join("\n  "));
});

test("[PCT-4] the per-card rung is OUTSIDE the shared one", () => {
  // THE RED INPUT: wrap them the other way round —
  //   var(--evcc-card-header-padding, var(--evcc-card-room-header-padding, ...))
  // The shared token then always wins and the per-card control can never take effect,
  // while [PCT-3] stays green because both names are still present in the file. Order
  // IS the feature; a chain that reads the wrong way is decorative.
  for (const key of PER_CARD_KEYS) {
    const { id, thing } = split(key);
    const at = SRC[id].indexOf(`var(${key},`);
    assert.notEqual(at, -1, `${key} is not read at all`);
    const after = SRC[id].slice(at + `var(${key},`.length, at + `var(${key},`.length + 80);
    assert.match(after, new RegExp(`^\\s*var\\(--evcc-card-${thing},`),
      `${key} must fall back to the SHARED --evcc-card-${thing}, so the per-card value ` +
      `wins and the shared one still carries every card that has no override. Got: ` +
      JSON.stringify(after.slice(0, 60)));
  }
});
