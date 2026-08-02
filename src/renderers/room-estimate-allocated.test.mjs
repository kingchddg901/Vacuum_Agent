// Regression test — CARD-2 clause (2) (carried CF-6, "GUESS-1's display half"),
// the ALLOCATED half specifically. renderRoomEstimateModal (room-estimate.js:
// 24-200) already handles roomEstimate.source==="default" (line 47: pushes
// note_no_learned_data) -- that half is NOT re-tested here, it already works.
// What's missing is entry.allocated / entry.allocation_group_size (RP-013's
// additive schema fields, "allocated flags feed ACC-6's fix" per
// SYNTH-01b-families-remaining.md:233 -- not yet emitted by any landed
// backend code, confirmed by grep: zero matches for "allocated" anywhere
// under src/ or custom_components/). The minutes/etaAt values (line 38-39)
// render via _formatLearningMinutes/_formatLearningWallClock with NO check
// anywhere for whether the estimate is a genuinely single-room measurement
// or a multi-room total SPLIT evenly across an allocation_group_size -- the
// summaryRows and notes arrays never reference entry.allocated at all.
//
// This proof constructs a details fixture shaped exactly as RP-013's own
// spec describes (allocated:true, allocation_group_size:3) -- the same
// "prove the card's current behavior against a spec'd-but-not-yet-emitted
// shape" technique already used for CARD-1/CARD-9 this session, sanctioned
// because materialization does not require the blocking backend packet
// (here RP-013b) to have executed first.
//
// Run: node --test src/renderers/room-estimate-allocated.test.mjs
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs): RE-1 FAILS
// against current room-estimate.js (no "shared" qualifier anywhere in the
// rendered modal) and is expected to PASS once a note/row consumes
// entry.allocated. RE-2 is the control -- the ALREADY-working source=
// "default" note must keep firing, so a fix that touches this file can't
// silently break it.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyRoomEstimateRenderers } from "./room-estimate.js";

function makeCard() {
  const proto = {};
  applyRoomEstimateRenderers(proto);
  const card = Object.create(proto);
  card.t = (key, vars) => `T:${key}${vars ? `:${JSON.stringify(vars)}` : ""}`;
  card.tVocabRaw = (field, val, fallback) => fallback;
  card.escapeHtml = (s) => String(s);
  card._formatLearningMinutes = (m) => `${m} min`;
  card._formatLearningWallClock = (t) => String(t);
  card._learningConfidenceLabel = (label) => label;
  return card;
}

function makeCtx(card, { entryExtra = {}, roomEstimateExtra = {} } = {}) {
  return {
    state: {
      isRoomEstimateModalOpen: () => true,
      activeRoomEstimateDetails: () => ({
        room: { id: 5, name: "Kitchen" },
        entry: { minutes: 12, eta_at: null, ...entryExtra },
        roomEstimate: { source: "learned", sample_count: 4, ...roomEstimateExtra },
        plannedWaterRoom: null,
        confidenceBreakpoint: null,
      }),
    },
  };
}

test("[RE-1] an allocated (multi-room-split) estimate renders a 'shared across N rooms' qualifier", 
  { todo: "wave-7 CARD fix not yet executed - drop this flag as part of the fix" }, () => {
  const card = makeCard();
  const ctx = makeCtx(card, { entryExtra: { allocated: true, allocation_group_size: 3 } });

  const html = card.renderRoomEstimateModal(ctx);

  assert.match(
    html,
    /shared|allocat/i,
    "the modal shows 12 min as a plain, unqualified measurement even though it is " +
      "1/3 of a multi-room total split evenly across the group -- entry.allocated is never read"
  );
});

test("[RE-2] a source='default' estimate still shows its existing note (control, already-working)", () => {
  const card = makeCard();
  const ctx = makeCtx(card, { roomEstimateExtra: { source: "default" } });

  const html = card.renderRoomEstimateModal(ctx);

  assert.match(
    html,
    /note_no_learned_data/,
    "the already-landed source='default' note stopped firing -- this proof must not regress it"
  );
});
