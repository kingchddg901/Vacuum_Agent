import { test } from "node:test";
import assert from "node:assert/strict";
import { accumulateTrail } from "./live-trail.js";

const A = [0.1, 0.1], B = [0.2, 0.2], C = [0.3, 0.3];

test("[LT-1] accumulates anchors while cleaning", () => {
  let t = accumulateTrail(null, A, false);
  t = accumulateTrail(t, B, false);
  t = accumulateTrail(t, C, false);
  assert.deepEqual(t, [A, B, C]);
});

test("[LT-2] stationary repeats are de-duplicated", () => {
  let t = accumulateTrail(null, A, false);
  t = accumulateTrail(t, A, false);
  t = accumulateTrail(t, A, false);
  assert.deepEqual(t, [A]);
});

test("[LT-3] docked FREEZES, then the SAME trace CONTINUES on resume (recharge case, no split)", () => {
  let t = accumulateTrail(null, A, false);
  t = accumulateTrail(t, B, false);
  // A mid-clean recharge docks -> frozen, no new points added while docked.
  t = accumulateTrail(t, C, true);
  t = accumulateTrail(t, C, true);
  assert.deepEqual(t, [A, B]);            // unchanged across the dock
  // Robot resumes -> the SAME trace continues; a dock is NOT a new clean, so it is NOT reset.
  t = accumulateTrail(t, C, false);
  assert.deepEqual(t, [A, B, C]);
});

test("[LT-4] length is bounded (oldest points drop)", () => {
  let t = null;
  for (let i = 0; i < 5; i++) t = accumulateTrail(t, [i / 100, i / 100], false, { max: 3 });
  assert.equal(t.length, 3);
  assert.deepEqual(t[0], [0.02, 0.02]);   // the first two shifted out
});

test("[LT-5] a null/absent anchor HOLDS the trail (no extend)", () => {
  const t = accumulateTrail(null, A, false);
  assert.deepEqual(accumulateTrail(t, null, false), [A]);
  assert.deepEqual(accumulateTrail(t, undefined, false), [A]);
});

test("[LT-6] reset is EXTERNAL: a null trail starts fresh (what state.resetLiveTrail does on dispatch)", () => {
  let t = accumulateTrail(null, A, false);
  t = accumulateTrail(t, B, false);       // [A, B]
  // The card calls resetLiveTrail() (sets the trail to null) when it dispatches a new clean.
  t = accumulateTrail(null, C, false);
  assert.deepEqual(t, [C]);
});
