// Regression guard for RN6F7RW6 on the RENDERER instance.
//
// The renderer methods (tVocab / tVocabRaw) run on the VacuumCardRenderers INSTANCE,
// where only `this.card` is set — `this._snapshot` is undefined there (it lives on the
// dashboard-card element, a different object). A first fix read `this._snapshot?.adapter_id`
// directly, so the brand was always undefined and the room-editor MODAL showed the shared
// "Turbo" while the dashboard-card accordion (a real card, own `_snapshot`) showed "Max".
// It passed every existing test because none exercised brand resolution on the renderer.
//
// These pin the accessor: the brand comes from `card._state.dashboardSnapshot().adapter_id`
// (the way every other renderer reaches the snapshot). Revert `_vocabBrand` to
// `this._snapshot?.adapter_id` and [VB-1]/[VB-3] go red.

import { test } from "node:test";
import assert from "node:assert/strict";
import { applySharedRenderers } from "./shared.js";

const VOCAB = {
  "vocab.fan_speed.turbo": "Turbo",       // shared catalog (Eufy-origin wording)
  "vocab.dreame.fan_speed.turbo": "Max",  // brand-scoped: Dreame owns its value's word
};

// A minimal renderer host mirroring VacuumCardRenderers: only `card` on the instance,
// plus stub translators (the real proto.t/tRaw need the full i18n/locale load).
function makeRenderer({ snapshot = undefined, cardSnapshot = null } = {}) {
  class R {}
  applySharedRenderers(R.prototype);
  const r = new R();
  r.escapeHtml = (s) => String(s);
  r.t = (k) => (k in VOCAB ? VOCAB[k] : k);
  r.tRaw = (k) => (k in VOCAB ? VOCAB[k] : k);
  if (snapshot !== undefined) r._snapshot = snapshot;
  r.card = { _state: { dashboardSnapshot: () => cardSnapshot } };
  return r;
}

test("[VB-1] tVocab resolves the brand from card._state.dashboardSnapshot() — the renderer-instance path", () => {
  const r = makeRenderer({ cardSnapshot: { adapter_id: "dreame" } });
  assert.equal(r.tVocab("fan_speed", "turbo", "Max"), "Max");
});

test("[VB-2] no brand → the shared catalog word stands (Eufy unchanged)", () => {
  const r = makeRenderer({ cardSnapshot: { adapter_id: null } });
  assert.equal(r.tVocab("fan_speed", "turbo", "Turbo"), "Turbo");
});

test("[VB-3] tVocabRaw is the co-replica — same brand-first order on the same instance path", () => {
  const r = makeRenderer({ cardSnapshot: { adapter_id: "dreame" } });
  assert.equal(r.tVocabRaw("fan_speed", "turbo", "Max"), "Max");
});

test("[VB-4] a direct _snapshot (a real card host that carries the snapshot) also resolves the brand", () => {
  const r = makeRenderer({ snapshot: { adapter_id: "dreame" }, cardSnapshot: null });
  assert.equal(r._vocabBrand(), "dreame");
});

test("[VB-5] neither source present → undefined brand, no crash, shared word", () => {
  const r = makeRenderer({ cardSnapshot: null });
  assert.equal(r._vocabBrand(), undefined);
  assert.equal(r.tVocab("fan_speed", "turbo", "Turbo"), "Turbo");
});
