// Unit tests for the item-agnostic ordering ENGINE in src/state/order.js — the pure reorder
// primitives that every feature (room order, custom-segment order, ...) rides on. These take a
// caller-supplied adapter {getItems,getId,getOrder,setOrder} and own no feature data. We stub a
// tiny immutable adapter over {id, order} records so setOrder returns a NEW record (mirroring the
// real feature adapters, which persist a fresh object). Covers: numeric-order sort with the
// 999999 non-finite fallback + id localeCompare tiebreak, the Math.max(1,Math.min(target,len))
// clamp + splice in _moveOrderedItemToPosition, the drag-swap in _swapOrderedItemsById, 1-based
// _reindexOrderedItems, and the scope-adapter preview/position wrappers.
// Run: node --test src/state/order-engine.test.mjs
//
// Coverage targets (src/state/order.js):
//   [ORD] _sortOrderedItems        — numeric order, 999999 non-finite fallback, id localeCompare tiebreak, copy-not-mutate
//   [MOV] _moveOrderedItemToPosition — clamp [1,len], target||1 fallback, splice to first/last/mid, unknown id, empty
//   [SWP] _swapOrderedItemsById     — drag reorder, missing/equal id short-circuit, forward/backward moves
//   [RE]  _reindexOrderedItems      — 1-based contiguous order via setOrder
//   [PRV] previewMovedItemsForScope / previewDraggedItemsForScope — adapter resolution + delegation, null-adapter -> []
//   [POS] getOrderedItemPosition    — 1-based position, unknown -> null, null adapter -> null
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyOrderState } from "./order.js";

function makeState() {
  const proto = {};
  applyOrderState(proto);
  return Object.create(proto);
}

// Immutable {id, order} adapter — setOrder returns a FRESH record (as real feature adapters do),
// so the engine's map()-with-setOrder is what carries the new order out. Records are plain objects.
const rec = (id, order) => ({ id, order });
const ADP = {
  getId: (it) => it.id,
  getOrder: (it) => it.order,
  setOrder: (it, order) => ({ ...it, order }),
};

// Convenience: [id, order] pairs -> array of records.
const recs = (...pairs) => pairs.map(([id, order]) => rec(id, order));
// Read the id/order shape out for terse assertions.
const shape = (arr) => arr.map((it) => [it.id, it.order]);

/* ============================ _sortOrderedItems ============================ */

test("[ORD-1] _sortOrderedItems: ascending numeric order, returns a copy (no mutate)", () => {
  const s = makeState();
  const input = recs(["c", 3], ["a", 1], ["b", 2]);
  const out = s._sortOrderedItems(input, ADP);
  assert.deepEqual(out.map((it) => it.id), ["a", "b", "c"]);
  // input array order is unchanged: a copy was sorted, not the original.
  assert.deepEqual(input.map((it) => it.id), ["c", "a", "b"]);
});

test("[ORD-2] _sortOrderedItems: only NaN-coercing orders hit the 999999 fallback (null->0 trap)", () => {
  const s = makeState();
  // _normalizeNumericOrder does Number(value); Number.isFinite ? value : 999999.
  //   Number(null)      = 0        (FINITE -> kept as 0, NOT the fallback!)
  //   Number(undefined) = NaN      -> 999999
  //   Number(NaN)       = NaN      -> 999999
  //   Number("xyz")     = NaN      -> 999999
  // So null sorts to the FRONT (order 0), ahead of a real 5, while undefined/NaN/str sink.
  const input = recs(["real", 5], ["z-nan", NaN], ["a-null", null], ["m-str", "xyz"], ["k-undef", undefined]);
  const out = s._sortOrderedItems(input, ADP);
  assert.equal(out[0].id, "a-null");                      // null -> 0 leads (documented coercion trap)
  assert.equal(out[1].id, "real");                        // finite 5 next
  // the three 999999-fallback items are tie-broken by id localeCompare: k-undef, m-str, z-nan
  assert.deepEqual(out.slice(2).map((it) => it.id), ["k-undef", "m-str", "z-nan"]);
});

test("[ORD-3] _sortOrderedItems: equal order -> id localeCompare tiebreak (stringified)", () => {
  const s = makeState();
  // all order 2 -> pure id tiebreak. Numeric-looking ids are compared as STRINGS via localeCompare.
  const input = recs(["10", 2], ["2", 2], ["1", 2]);
  const out = s._sortOrderedItems(input, ADP);
  // String(id).localeCompare: "1" < "10" < "2"
  assert.deepEqual(out.map((it) => it.id), ["1", "10", "2"]);
});

test("[ORD-4] _sortOrderedItems: non-array input -> [] (defensive)", () => {
  const s = makeState();
  assert.deepEqual(s._sortOrderedItems(null, ADP), []);
  assert.deepEqual(s._sortOrderedItems(undefined, ADP), []);
  assert.deepEqual(s._sortOrderedItems("nope", ADP), []);
  assert.deepEqual(s._sortOrderedItems({}, ADP), []);
});

/* ============================ _reindexOrderedItems ============================ */

test("[RE-1] _reindexOrderedItems: assigns contiguous 1-based order via setOrder", () => {
  const s = makeState();
  // pre-existing orders are ignored — position drives the new 1-based order.
  const input = recs(["a", 40], ["b", 7], ["c", 999]);
  const out = s._reindexOrderedItems(input, ADP);
  assert.deepEqual(shape(out), [["a", 1], ["b", 2], ["c", 3]]);
});

test("[RE-2] _reindexOrderedItems: empty in -> empty out", () => {
  const s = makeState();
  assert.deepEqual(s._reindexOrderedItems([], ADP), []);
});

/* ============================ _moveOrderedItemToPosition ============================ */
// Every move first sort+reindexes, so input orders need not be normalized.

test("[MOV-1] move to first: item hops to position 1, others shift down", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2], ["c", 3]);
  const out = s._moveOrderedItemToPosition(input, ADP, "c", 1);
  assert.deepEqual(shape(out), [["c", 1], ["a", 2], ["b", 3]]);
});

test("[MOV-2] move to last: target beyond len clamps to len (Math.min)", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2], ["c", 3]);
  // target 99 clamps to 3 (len) -> a goes to the end.
  const out = s._moveOrderedItemToPosition(input, ADP, "a", 99);
  assert.deepEqual(shape(out), [["b", 1], ["c", 2], ["a", 3]]);
});

test("[MOV-3] move to middle: splice inserts at the 1-based target index", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2], ["c", 3], ["d", 4]);
  // move d to position 2: remove d, list is [a,b,c], insert at idx 1 -> [a,d,b,c]
  const out = s._moveOrderedItemToPosition(input, ADP, "d", 2);
  assert.deepEqual(shape(out), [["a", 1], ["d", 2], ["b", 3], ["c", 4]]);
});

test("[MOV-4] target < 1 clamps to 1 (Math.max); 0/NaN/negative all -> position 1", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2], ["c", 3]);
  // Number(0)||1 = 1 ; then Math.max(1, Math.min(1,3)) = 1
  assert.deepEqual(shape(s._moveOrderedItemToPosition(input, ADP, "c", 0)),
    [["c", 1], ["a", 2], ["b", 3]]);
  // Number(-5)||1 -> -5, then Math.min(-5,3) = -5, Math.max(1,-5) = 1
  assert.deepEqual(shape(s._moveOrderedItemToPosition(input, ADP, "c", -5)),
    [["c", 1], ["a", 2], ["b", 3]]);
  // Number("abc")||1 -> NaN||1 -> 1
  assert.deepEqual(shape(s._moveOrderedItemToPosition(input, ADP, "c", "abc")),
    [["c", 1], ["a", 2], ["b", 3]]);
});

test("[MOV-5] unknown itemId -> the sorted+reindexed list is returned unchanged (sourceIndex -1)", () => {
  const s = makeState();
  const input = recs(["b", 2], ["a", 1]);           // unsorted on purpose
  const out = s._moveOrderedItemToPosition(input, ADP, "ghost", 1);
  // no move, but the return is still normalized (sorted a,b + reindexed 1,2)
  assert.deepEqual(shape(out), [["a", 1], ["b", 2]]);
});

test("[MOV-6] empty items -> empty (clamp uses len 0, findIndex -1)", () => {
  const s = makeState();
  assert.deepEqual(s._moveOrderedItemToPosition([], ADP, "a", 1), []);
});

test("[MOV-7] move by string id matches numeric getId via String() coercion", () => {
  const s = makeState();
  const numAdp = { ...ADP, getId: (it) => it.id };   // ids are numbers here
  const input = [rec(1, 1), rec(2, 2), rec(3, 3)];
  // pass target id as the STRING "3" — engine compares String(getId)===String(itemId)
  const out = s._moveOrderedItemToPosition(input, numAdp, "3", 1);
  assert.deepEqual(out.map((it) => it.id), [3, 1, 2]);
});

/* ============================ _swapOrderedItemsById ============================ */

test("[SWP-1] drag forward: source removed then re-inserted at target's index", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2], ["c", 3], ["d", 4]);
  // drag a onto c: remove a -> [b,c,d]; targetIndex of c in the ORIGINAL ordered list is 2;
  // splice a in at idx 2 -> [b,c,a,d]
  const out = s._swapOrderedItemsById(input, ADP, "a", "c");
  assert.deepEqual(shape(out), [["b", 1], ["c", 2], ["a", 3], ["d", 4]]);
});

test("[SWP-2] drag backward: last onto first lands at position 1", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2], ["c", 3]);
  const out = s._swapOrderedItemsById(input, ADP, "c", "a");
  assert.deepEqual(shape(out), [["c", 1], ["a", 2], ["b", 3]]);
});

test("[SWP-3] source == target -> unchanged (normalized) list, no-op short-circuit", () => {
  const s = makeState();
  const input = recs(["b", 2], ["a", 1]);
  const out = s._swapOrderedItemsById(input, ADP, "a", "a");
  assert.deepEqual(shape(out), [["a", 1], ["b", 2]]);   // still sorted+reindexed
});

test("[SWP-4] missing source OR target -> unchanged normalized list", () => {
  const s = makeState();
  const input = recs(["a", 1], ["b", 2]);
  assert.deepEqual(shape(s._swapOrderedItemsById(input, ADP, "ghost", "b")),
    [["a", 1], ["b", 2]]);
  assert.deepEqual(shape(s._swapOrderedItemsById(input, ADP, "a", "ghost")),
    [["a", 1], ["b", 2]]);
});

/* ============================ previewMovedItemsForScope / previewDraggedItemsForScope ============================ */
// These resolve an adapter via getOrderAdapter(scope) then delegate to the move/swap engine.
// getOrderAdapter is a null-returning stub on the base proto — override per test.

function withAdapter(items) {
  const s = makeState();
  s.getOrderAdapter = () => ({
    ...ADP,
    getItems: () => items,   // engine calls adapter.getItems.call(this)
  });
  return s;
}

test("[PRV-1] previewMovedItemsForScope: null adapter -> [] (no crash)", () => {
  const s = makeState();               // base getOrderAdapter returns null
  assert.deepEqual(s.previewMovedItemsForScope("rooms", "a", 1), []);
});

test("[PRV-2] previewMovedItemsForScope: pulls items from the adapter and moves", () => {
  const s = withAdapter(recs(["a", 1], ["b", 2], ["c", 3]));
  const out = s.previewMovedItemsForScope("rooms", "c", 1);
  assert.deepEqual(shape(out), [["c", 1], ["a", 2], ["b", 3]]);
});

test("[PRV-3] previewDraggedItemsForScope: null adapter -> []", () => {
  const s = makeState();
  assert.deepEqual(s.previewDraggedItemsForScope("rooms", "a", "b"), []);
});

test("[PRV-4] previewDraggedItemsForScope: pulls items and swaps via drag", () => {
  const s = withAdapter(recs(["a", 1], ["b", 2], ["c", 3]));
  const out = s.previewDraggedItemsForScope("rooms", "c", "a");
  assert.deepEqual(shape(out), [["c", 1], ["a", 2], ["b", 3]]);
});

test("[PRV-5] previewDraggedItemsForScope: getItems is called with `this` bound (adapter.getItems.call)", () => {
  // getItems reads off `this` -> proves the engine binds the card as the receiver.
  const s = makeState();
  s._backing = recs(["x", 2], ["y", 1]);
  s.getOrderAdapter = () => ({
    ...ADP,
    getItems() { return this._backing; },   // `this` must be the card
  });
  const out = s.previewDraggedItemsForScope("rooms", "y", "x");
  // sorted first: y(1),x(2) -> drag y onto x -> [x,y]
  assert.deepEqual(shape(out), [["x", 1], ["y", 2]]);
});

/* ============================ getOrderedItemPosition ============================ */

test("[POS-1] getOrderedItemPosition: 1-based position of an item in the sorted scope", () => {
  const s = withAdapter(recs(["c", 3], ["a", 1], ["b", 2]));
  assert.equal(s.getOrderedItemPosition("rooms", "a"), 1);
  assert.equal(s.getOrderedItemPosition("rooms", "b"), 2);
  assert.equal(s.getOrderedItemPosition("rooms", "c"), 3);
});

test("[POS-2] getOrderedItemPosition: unknown id -> null; null adapter -> null", () => {
  const s = withAdapter(recs(["a", 1], ["b", 2]));
  assert.equal(s.getOrderedItemPosition("rooms", "ghost"), null);
  const base = makeState();            // getOrderAdapter -> null
  assert.equal(base.getOrderedItemPosition("rooms", "a"), null);
});
