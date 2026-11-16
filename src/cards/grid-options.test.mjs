// Run: node --test src/cards/grid-options.test.mjs
//
// [GRID-*] SECTIONS-VIEW SIZING.
//
// Home Assistant's sections view warns "This card does not fully support resizing yet and
// may not display correctly with custom sizes" for any custom card that does not declare
// `getGridOptions()`. All three of ours did not, so it showed on every card.
//
// WHAT IS MEASURED AND WHAT IS NOT, because the difference matters if these ever move.
// Read off a live dashboard 2026-11-16: the section grid is TWENTY-FOUR columns of 21.25px
// with 8px gaps (the developer docs say twelve and are out of date for this HA version),
// and all three cards render at 343px, which is exactly 12 columns. So `columns: 12`
// restates what the cards already do rather than choosing something new — declaring it is
// what stops HA guessing, and it means turning this on cannot move anybody's dashboard.
// `rows: "auto"` was confirmed valid by reading `hui-entities-card.getGridOptions()` on the
// same install, which returns {columns: 12, min_columns: 3, rows: "auto"}.
//
// `min_columns` is the one JUDGEMENT here. Nothing was measured about where each card stops
// being usable. [GRID-3] says so out loud rather than letting a guessed number read as a
// measured one.
//
// Coverage
// --------
// [GRID-1] every card declares the keys HA reads, with valid values
// [GRID-2] the default span is 12 — the width the cards already render at
// [GRID-3] the dashboard card's floor is wider than the other two, and is a judgement
// [GRID-4] the objects are copied, not shared — one card cannot mutate another's sizing

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  GRID_ROOM_CARD,
  GRID_PROFILE_CARD,
  GRID_DASHBOARD_CARD,
} from "./_shared.js";

const ALL = [
  ["room", GRID_ROOM_CARD],
  ["profile", GRID_PROFILE_CARD],
  ["dashboard", GRID_DASHBOARD_CARD],
];

test("[GRID-1] every card declares the keys HA reads, with valid values", () => {
  for (const [name, g] of ALL) {
    assert.equal(typeof g.columns, "number", `${name}: columns must be a number`);
    assert.ok(Number.isInteger(g.columns) && g.columns > 0 && g.columns <= 24,
      `${name}: columns must sit on the 24-column grid, got ${g.columns}`);
    assert.equal(typeof g.min_columns, "number", `${name}: min_columns must be a number`);
    assert.ok(g.min_columns > 0 && g.min_columns <= g.columns,
      `${name}: min_columns (${g.min_columns}) must be >0 and no wider than the default (${g.columns})`);
    // "auto" is the string HA's own hui-entities-card returns; a NUMBER here would pin
    // these cards to a fixed height, and all three are content-sized.
    assert.equal(g.rows, "auto", `${name}: rows must be "auto" — these cards size to content`);
  }
});

test("[GRID-2] the default span is the width the cards already render at", () => {
  // 343px measured = 12 columns exactly: 12 * 21.25 + 11 * 8 = 343.
  assert.equal(12 * 21.25 + 11 * 8, 343, "the arithmetic this default rests on");
  for (const [name, g] of ALL) {
    assert.equal(g.columns, 12,
      `${name}: declaring anything but 12 would RESIZE existing dashboards on upgrade`);
  }
});

test("[GRID-3] the floor is permissive, because the right floor is not ours to know", () => {
  // HIS RULING 2026-11-16: "min columns is going to vary based on names and other things
  // lets the users tune". The first version of this file floored these at 6/6/8 and
  // asserted the dashboard card's floor was the widest — a guess from English cards on one
  // dashboard, encoded as though it were a finding.
  //
  // It is unknowable in principle, not merely unmeasured: the narrowest usable width
  // depends on the ROOM NAMES and the LOCALE. The same card reading "Kitchen" and
  // "Vysávání a vytírání" needs different room, and a floor derived from English blocks
  // exactly the users who most need to tune it.
  //
  // THE INPUT THAT MAKES THIS RED is re-tightening any of them above HA's own most
  // permissive built-in. Raising a floor takes a dashboard the user had already arranged
  // and silently widens their card on upgrade.
  for (const [name, g] of ALL) {
    assert.ok(g.min_columns <= 3,
      `${name}: min_columns is ${g.min_columns}; HA's own hui-entities-card allows 3, and ` +
      "the card does not get to decide its user is wrong about their own dashboard");
  }

  // All three share the floor now. If that ever stops being true, the reason belongs here
  // — a card-specific floor is a claim about where THAT card breaks, which nobody has
  // measured for any of them.
  assert.equal(GRID_ROOM_CARD.min_columns, GRID_PROFILE_CARD.min_columns);
  assert.equal(GRID_ROOM_CARD.min_columns, GRID_DASHBOARD_CARD.min_columns);
});

test("[GRID-4] each card gets its own object, not a shared one", () => {
  // The cards spread these (`{ ...GRID_* }`), so a card that mutated what HA handed back
  // could not corrupt the next card's sizing. This pins the constants are distinct objects
  // to begin with — three aliases of one object would make that spread pointless.
  assert.notEqual(GRID_ROOM_CARD, GRID_PROFILE_CARD);
  assert.notEqual(GRID_ROOM_CARD, GRID_DASHBOARD_CARD);
  assert.notEqual(GRID_PROFILE_CARD, GRID_DASHBOARD_CARD);
});
