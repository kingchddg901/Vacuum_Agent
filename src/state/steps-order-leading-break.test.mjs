// Regression test — CARD-6 clause (1) (Q17, carried A5-PP-RP-5 display half),
// leading/trailing charge_wait/wait is UNSUPPORTED. insertChargeStep and
// insertWaitStep (state/steps-order.js:70-78, 104-109) splice a break step at
// ANY index with no positional check at all -- confirmed: the existing
// [STP-ins-2] test in steps-order.test.mjs explicitly PINS a TRAILING insert
// succeeding ("inserts at end when index >= length"), which is the packet's
// own superseded_tests target ("steps-editor tests permitting leading
// breaks") for the trailing case. This file adds the LEADING half (index 0)
// that no existing test covers, plus sanitizeStepsForSave's silent pass-
// through of an ALREADY-leading break (the "legacy profile carrying one"
// case, required to render struck-through rather than silently kept).
//
// Neither insertChargeStep/insertWaitStep nor sanitizeStepsForSave
// (steps-order.js:154-180) reference position at all -- grepped: zero
// matches for "leading"/"trailing" anywhere in this file.
//
// Run: node --test src/state/steps-order-leading-break.test.mjs
//
// ⚠ CI CONVENTION — READ BEFORE COPYING THIS FILE'S SHAPE.
// The Python reproducers live in .claude/notes/_proof_*.py: outside the test
// suite, run by hand, and therefore FREE to sit red until their fix lands. A
// frontend reproducer is NOT: anything matching *.test.mjs under src/ is run by
// `npm run test:units` and gates CI on every push. Committing one red turns the
// repo red for everyone until the fix ships, which is what happened here
// (d0be882 -> three failed CI runs).
//
// So LB-1 and LB-2 are marked `todo`. Node reports a todo test's failure without
// failing the run, which is exactly the semantic wanted: a known-failing
// reproducer awaiting its fix. REMOVING THE `todo` FLAG IS PART OF THE CARD-6
// CLAUSE (1) FIX — the flip is visible in that commit's diff, which is better
// evidence than a proof file changing verdict.
//
// The other six fail-until-fixed tests in this repo (core-refusal-shape,
// room-estimate-allocated, card4-untranslated-strings, ...) are green because
// each was committed WITH its fix. That is the frontend convention; this file is
// the exception that proves it needs stating.
//
// FLIP CONVENTION (mirrors src/actions/core-service-failure.test.mjs): LB-1 and LB-2
// FAIL against current steps-order.js (a leading break inserts/saves with
// no refusal or marking) and are expected to PASS once insertChargeStep/
// insertWaitStep refuse a leading/trailing position and sanitizeStepsForSave
// (or its caller) flags an already-leading legacy step. LB-3 is the
// control -- a MIDDLE insert (the ordinary, supported case) must keep
// working exactly as today.

import { test } from "node:test";
import assert from "node:assert/strict";

import { insertChargeStep, insertWaitStep, sanitizeStepsForSave } from "./steps-order.js";

const rg = (...ids) => ({ type: "room_group", rooms: ids.map((room_id) => ({ room_id })) });
const types = (arr) => arr.map((s) => s.type);

test("[LB-1] inserting a charge_wait at the LEADING position (index 0) is refused",
  { todo: "CARD-6 clause (1) not yet executed — drop this flag as part of the fix" }, () => {
  const before = [rg(1), rg(2)];
  const next = insertChargeStep(before, 0);

  assert.deepEqual(
    types(next),
    types(before),
    "a leading charge_wait was inserted (steps now start with a break) -- " +
      "no position check exists to refuse it, even though a leading break is unsupported"
  );
});

test("[LB-2] a legacy profile whose FIRST step is already charge_wait is not marked in any way",
  { todo: "CARD-6 clause (1) not yet executed — drop this flag as part of the fix" }, () => {
  const legacySteps = [{ type: "charge_wait", target_battery_percent: 80 }, rg(1)];
  const saved = sanitizeStepsForSave(legacySteps);

  // sanitizeStepsForSave is the save-time mirror of the backend normalize --
  // per Q17 it should strip/flag an unsupported-position break (a
  // normalized_steps note, matching the backend's own explicit normalization),
  // not carry it through byte-identical to a supported step.
  assert.notDeepEqual(
    saved,
    legacySteps.map((s) => ({ ...s })),
    "the leading charge_wait passed straight through unchanged, identical to " +
      "how a normal mid-sequence break would be saved -- nothing distinguishes " +
      "'this step will be silently skipped' from 'this step will run'"
  );
});

test("[LB-3] inserting a charge_wait in the MIDDLE still works (control, ordinary supported case)", () => {
  const next = insertChargeStep([rg(1), rg(2)], 1);
  assert.deepEqual(types(next), ["room_group", "charge_wait", "room_group"]);
});
