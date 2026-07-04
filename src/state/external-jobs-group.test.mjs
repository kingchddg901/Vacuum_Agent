// Unit tests for the External-Jobs review wizard's pure state logic:
//   externalWizardGroups  — derive room groups from segments + split toggles
//                            (v2 resegmentable = one group/segment; v1 legacy = merge grouping)
//   openExternalWizard     — seed splits/assignments + normalize the v2 boundary fields
//   applyResegmentResult   — replace segmentation from a server re-segment record
//
// Coverage targets:
//   [EXJ-1]  externalWizardGroups: no wizard -> []
//   [EXJ-2]  externalWizardGroups v2 (resegmentable): one group per segment, no client grouping
//   [EXJ-3]  externalWizardGroups v1: order===0 leads; a split boundary leads; unsplit merges up
//   [EXJ-4]  externalWizardGroups v1: first segment always starts a group even if order!=0 (empty-guard)
//   [EXJ-5]  externalWizardGroups v1: only the split boundaries produce breaks (precedence)
//   [EXG-6]  openExternalWizard: splits only for order>0, keyed by confident_boundary
//   [EXG-7]  openExternalWizard: assignments seeded from shortlist[0].room_id (null when empty)
//   [EXG-8]  openExternalWizard: v2 fields normalized (activeBoundaries->Number, resegmentable, counts)
//   [EXG-9]  openExternalWizard: null/absent run -> empty, safe defaults
//   [EXR-10] applyResegmentResult: no wizard or no record -> no-op
//   [EXR-11] applyResegmentResult: replaces segments/assignments/activeBoundaries from record
//   [EXR-12] applyResegmentResult: resegmentMeta set only when capped||message, else null
//
// Run: node --test src/state/external-jobs-group.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyExternalJobsState } from "./external-jobs.js";

function makeCard() {
  const proto = {};
  applyExternalJobsState(proto);
  return Object.create(proto);
}

/* ---------------------------------------------------------------- groups */

test("[EXJ-1] externalWizardGroups: no open wizard -> []", () => {
  const c = makeCard();
  assert.deepEqual(c.externalWizardGroups(), []);          // _extWizard undefined
});

test("[EXJ-2] externalWizardGroups v2 (resegmentable): one group per segment, split toggles ignored", () => {
  const c = makeCard();
  const segments = [{ order: 0 }, { order: 1 }, { order: 2 }];
  // resegmentable true -> server owns segmentation; splits must have NO effect here.
  c._extWizard = { resegmentable: true, segments, splits: { 1: false, 2: false } };
  const g = c.externalWizardGroups();
  assert.equal(g.length, 3);                               // one per segment, no merging
  assert.deepEqual(g.map((x) => x.orders), [[0], [1], [2]]);
  assert.equal(g[1].lead, segments[1]);                    // lead is the segment itself
  assert.deepEqual(g[2].segments, [segments[2]]);
});

test("[EXJ-3] externalWizardGroups v1: order 0 leads, split boundary leads, unsplit merges up", () => {
  const c = makeCard();
  const segments = [{ order: 0 }, { order: 1 }, { order: 2 }, { order: 3 }];
  // split at 2 (starts a new group); 1 and 3 merged (off) -> groups: [0,1] and [2,3].
  c._extWizard = { resegmentable: false, segments, splits: { 1: false, 2: true, 3: false } };
  const g = c.externalWizardGroups();
  assert.equal(g.length, 2);
  assert.deepEqual(g[0].orders, [0, 1]);                   // 1 merged into the order-0 lead
  assert.deepEqual(g[1].orders, [2, 3]);                   // 2 split -> new group, 3 merged
  assert.equal(g[1].lead, segments[2]);                    // the split segment is the lead
  assert.deepEqual(g[0].segments, [segments[0], segments[1]]);
});

test("[EXJ-4] externalWizardGroups v1: first segment starts a group even if its order isn't 0", () => {
  const c = makeCard();
  // A run whose first segment is order 1 with no split entry: without the empty-guard the
  // first segment would try to merge into a non-existent group. It must lead a group instead.
  const segments = [{ order: 1 }, { order: 2 }];
  c._extWizard = { resegmentable: false, segments, splits: { 1: false, 2: false } };
  const g = c.externalWizardGroups();
  assert.equal(g.length, 1);                               // both in one group
  assert.deepEqual(g[0].orders, [1, 2]);
  assert.equal(g[0].lead, segments[0]);                    // first seg leads despite order!=0
});

test("[EXJ-5] externalWizardGroups v1: each split boundary produces exactly one break", () => {
  const c = makeCard();
  const segments = [{ order: 0 }, { order: 1 }, { order: 2 }, { order: 3 }, { order: 4 }];
  // splits at 1 and 3 -> three groups: [0], [1,2], [3,4].
  c._extWizard = {
    resegmentable: false, segments,
    splits: { 1: true, 2: false, 3: true, 4: false },
  };
  const g = c.externalWizardGroups();
  assert.deepEqual(g.map((x) => x.orders), [[0], [1, 2], [3, 4]]);
});

/* ------------------------------------------------------------ open wizard */

test("[EXG-6] openExternalWizard: splits only for order>0, value = !!confident_boundary", () => {
  const c = makeCard();
  c.openExternalWizard({
    segments: [
      { order: 0, confident_boundary: true },   // order 0 -> no split entry
      { order: 1, confident_boundary: true },    // confident -> split default on
      { order: 2, confident_boundary: false },   // uncertain -> merged (off)
      { order: 3 },                              // missing -> !!undefined = false
    ],
  });
  const w = c.externalWizard();
  assert.ok(!Object.prototype.hasOwnProperty.call(w.splits, 0)); // no key for order 0
  assert.equal(w.splits[1], true);
  assert.equal(w.splits[2], false);
  assert.equal(w.splits[3], false);
});

test("[EXG-7] openExternalWizard: assignments seed room_id from shortlist[0], null when empty", () => {
  const c = makeCard();
  c.openExternalWizard({
    segments: [
      { order: 0, shortlist: [{ room_id: 5 }, { room_id: 9 }] }, // top -> 5
      { order: 1, shortlist: [] },                                // empty -> null
      { order: 2 },                                              // absent -> null
    ],
  });
  const w = c.externalWizard();
  assert.equal(w.assignments[0].room_id, 5);                     // shortlist[0].room_id
  assert.equal(w.assignments[1].room_id, null);
  assert.equal(w.assignments[2].room_id, null);
  // default assignment shape
  assert.deepEqual(w.assignments[0], { room_id: 5, edge_mopping: false, override: false, overrides: {} });
});

test("[EXG-8] openExternalWizard: v2 boundary fields normalized to numbers + counts", () => {
  const c = makeCard();
  c.openExternalWizard({
    pending_job_id: "job-7",
    map_id: "map_6",
    segments: [{ order: 0 }, { order: 1 }],
    candidates: [{ order: 1 }],
    active_boundaries: ["1", "2", 3],       // strings must be coerced to numbers
    resegmentable: 1,                        // truthy -> boolean true
    suggested_room_count: "4",              // coerced via Number
    rooms: [{ room_id: 1 }],
  });
  const w = c.externalWizard();
  assert.equal(w.pendingJobId, "job-7");
  assert.equal(w.mapId, "map_6");
  assert.deepEqual(w.activeBoundaries, [1, 2, 3]);               // all Numbers
  assert.equal(w.resegmentable, true);
  assert.equal(w.suggestedRoomCount, 4);
  assert.equal(w.step, 1);
  assert.equal(w.busy, false);
  assert.equal(w.error, null);
  assert.equal(w.resegmentMeta, null);
});

test("[EXG-9] openExternalWizard: null/absent run -> empty segments + safe defaults", () => {
  const c = makeCard();
  c.openExternalWizard(null);                                    // run is null
  const w = c.externalWizard();
  assert.ok(c.isExternalWizardOpen());
  assert.deepEqual(w.segments, []);
  assert.deepEqual(w.splits, {});
  assert.deepEqual(w.assignments, {});
  assert.deepEqual(w.candidates, []);
  assert.deepEqual(w.activeBoundaries, []);
  assert.equal(w.resegmentable, false);
  assert.equal(w.pendingJobId, null);
  assert.equal(w.mapId, null);
  // suggestedRoomCount falls back to segments.length (0) since suggested_room_count absent
  assert.equal(w.suggestedRoomCount, 0);
});

/* ------------------------------------------------------- apply resegment */

test("[EXR-10] applyResegmentResult: no wizard OR no record -> no-op (no throw, no state)", () => {
  const c = makeCard();
  // no wizard open
  assert.doesNotThrow(() => c.applyResegmentResult({ segments: [{ order: 0 }] }));
  assert.equal(c.externalWizard(), null);
  // wizard open but record null -> segments untouched
  c._extWizard = { segments: [{ order: 0 }], assignments: {}, activeBoundaries: [7] };
  c.applyResegmentResult(null);
  assert.deepEqual(c._extWizard.segments, [{ order: 0 }]);
  assert.deepEqual(c._extWizard.activeBoundaries, [7]);         // unchanged
});

test("[EXR-11] applyResegmentResult: replaces segments/assignments/activeBoundaries from record", () => {
  const c = makeCard();
  c._extWizard = {
    segments: [{ order: 0 }], assignments: { 0: { room_id: 1 } },
    candidates: [], activeBoundaries: [9], suggestedRoomCount: 1, resegmentMeta: null,
  };
  c.applyResegmentResult({
    segments: [
      { order: 0, shortlist: [{ room_id: 3 }] },
      { order: 1, shortlist: [] },
    ],
    candidates: [{ order: 1 }],
    active_boundaries: ["1"],       // coerced to number
    suggested_room_count: 2,
  });
  const w = c.externalWizard();
  assert.equal(w.segments.length, 2);                           // replaced
  assert.equal(w.assignments[0].room_id, 3);                    // reseeded from new shortlist
  assert.equal(w.assignments[1].room_id, null);                // empty shortlist -> null
  assert.deepEqual(w.assignments[0], { room_id: 3, edge_mopping: false, override: false, overrides: {} });
  assert.deepEqual(w.activeBoundaries, [1]);                    // Number-coerced
  assert.deepEqual(w.candidates, [{ order: 1 }]);
  assert.equal(w.suggestedRoomCount, 2);
});

test("[EXR-12] applyResegmentResult: resegmentMeta set only when capped||message, null otherwise", () => {
  const c = makeCard();
  const seed = () => { c._extWizard = { segments: [], assignments: {}, activeBoundaries: [], candidates: [], resegmentMeta: "stale" }; };
  // capped -> meta object built with the cap fields
  seed();
  c.applyResegmentResult({ segments: [], active_boundaries: [], capped: true, capped_at: 8, reason: "max", message: "hit cap" });
  assert.deepEqual(c.externalWizard().resegmentMeta, { capped: true, capped_at: 8, reason: "max", message: "hit cap" });
  // message only (not capped) -> still built, capped false
  seed();
  c.applyResegmentResult({ segments: [], active_boundaries: [], message: "note" });
  assert.deepEqual(c.externalWizard().resegmentMeta, { capped: false, capped_at: undefined, reason: null, message: "note" });
  // neither -> meta cleared to null (defends against a stale prior meta)
  seed();
  c.applyResegmentResult({ segments: [], active_boundaries: [] });
  assert.equal(c.externalWizard().resegmentMeta, null);
});
