// Fault-label resolution (CARD-3 / RF-DOCK).
//
// The backend sends a KEY, never text. The point of the seam is the fallback: an
// unrecognised fault must show the raw vendor code, because "Error 6013" is honest and
// searchable while an invented label is not and a blank row tells the user their robot
// failed for no reason.
//
// Run: node --test src/state/fault-label.test.mjs
//
// Coverage (FL = Fault Label):
//   [FL-1] a known key translates
//   [FL-2] an unknown key falls back to the raw code, not the key
//   [FL-3] no key at all still falls back to the raw code
//   [FL-4] neither key nor code -> the generic unknown string
//   [FL-5] a translator echoing the key back counts as "no entry"
//   [FL-6] code 0 is a real code, not absence
//   [FL-7] faultRows preserves order and resolves each row
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyFaultState } from "./faults.js";

const LABELS = {
  "fault.eufy.roller_brush_stuck": "Roller brush stuck",
  "faults.unknown_code": "Error {code}",
  "faults.unknown": "Unknown error",
};

function makeCard(overrides = {}) {
  const proto = {};
  applyFaultState(proto);
  const card = Object.create(proto);
  card.t = (key, vars) => {
    const raw = overrides.t ? overrides.t(key) : LABELS[key];
    if (raw === undefined) return key;             // mirrors the real translator's echo
    return vars ? raw.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : raw;
  };
  return card;
}

test("[FL-1] a known key translates", () => {
  assert.equal(makeCard().faultLabel("fault.eufy.roller_brush_stuck", 4), "Roller brush stuck");
});

test("[FL-2] an unknown key falls back to the raw code, never the key", () => {
  const got = makeCard().faultLabel("fault.eufy.not_a_real_key", 6013);
  assert.equal(got, "Error 6013");
  assert.ok(!got.includes("fault."), "a dotted i18n key must never reach the user");
});

test("[FL-3] no key at all still falls back to the raw code", () => {
  assert.equal(makeCard().faultLabel(null, 7002), "Error 7002");
  assert.equal(makeCard().faultLabel(undefined, "6025"), "Error 6025");
});

test("[FL-4] neither key nor code gives the generic string", () => {
  assert.equal(makeCard().faultLabel(null, null), "Unknown error");
  assert.equal(makeCard().faultLabel("", "   "), "Unknown error");
});

test("[FL-5] a translator echoing the key back counts as no entry", () => {
  // The real translator returns the key when a locale has no value AND no en fallback.
  // Blank ONLY the fault key — the fallback strings must still resolve, or this would
  // assert on a broken translator rather than on a missing fault label.
  const card = makeCard({ t: (k) => (k.startsWith("fault.") ? undefined : LABELS[k]) });
  assert.equal(card.faultLabel("fault.eufy.roller_brush_stuck", 4), "Error 4");
});

test("[FL-6] code 0 is a real code, not absence", () => {
  // 0 is falsy in JS and is a real Eufy code (NONE). Treating it as absent would
  // silently swallow it — the exact class of bug the battery `-> int` default caused.
  assert.equal(makeCard().faultLabel(null, 0), "Error 0");
});

test("[FL-7] faultRows preserves order and resolves each row", () => {
  const rows = makeCard().faultRows([
    { code: 4, label_key: "fault.eufy.roller_brush_stuck", captured_at: "2026-08-02T06:24:47Z" },
    { code: 6013, label_key: "fault.eufy.nope" },
    "not an object",
    null,
  ]);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map((r) => r.label), ["Roller brush stuck", "Error 6013"]);
  assert.equal(rows[0].capturedAt, "2026-08-02T06:24:47Z");
  assert.equal(rows[1].capturedAt, null);
  assert.deepEqual(rows.map((r) => r.index), [0, 1]);
});
