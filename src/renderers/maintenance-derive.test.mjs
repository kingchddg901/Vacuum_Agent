// Unit tests for the pure derivation logic in the maintenance renderer. Covers the
// extracted, deterministic due-in projection (maintenanceDueInBucket — now + i18n
// injected), plus the two already-pure predicates reached through the mixin instance:
// the needs-attention verdict (backend flags OR status allowlist OR remaining_percent
// <= 20) and the remaining-percent derivation (explicit percent, else the
// replacement-vs-maintenance max-hours branch). All are pure over fixed inputs.
// Run: node --test src/renderers/maintenance-derive.test.mjs
//
// Coverage targets:
//   [DUE-*]  maintenanceDueInBucket        — projection math, 3-day / 0.1-h-per-day /
//                                             replacement guards, overdue, bucket thresholds
//   [ATT-*]  _maintenanceItemNeedsAttention — flag precedence, status allowlist,
//                                             remaining_percent <= 20 boundary
//   [PCT-*]  _maintenanceRemainingPercent   — explicit percent wins; replacement uses
//                                             max_life/total_life, maintenance uses interval
import { test } from "node:test";
import assert from "node:assert/strict";
import { maintenanceDueInBucket, applyMaintenanceRenderers } from "./maintenance.js";

// A fixed "now" and a reset 10 days earlier: chosen so daysSinceReset (10) clears the
// >=3-day guard, and hours_per_day is a clean divisor of remaining_hours in each case.
const NOW = Date.parse("2026-07-04T00:00:00Z");
const RESET_10D = "2026-06-24T00:00:00Z"; // exactly 10 days before NOW

// Echo resolver: return a compact string encoding key + count so bucket selection and
// the interpolated count are both assertable without a real i18n bundle.
const t = (key, vars) => (vars && "count" in vars ? `${key}:${vars.count}` : key);

// Build a mixin instance (like learning-derive.test.mjs) to reach the pure predicates
// that take no `this` and no injected now.
function makeRenderers() {
  const proto = {};
  applyMaintenanceRenderers(proto);
  return Object.create(proto);
}

/* ============================================================
   maintenanceDueInBucket — [DUE-*]
   ============================================================ */

test("[DUE-1] projects days_remaining at the observed daily rate -> ~N days bucket", () => {
  // 10 days since reset, 20 h used -> 2 h/day. remaining 12 h -> 6 days remaining.
  const item = { kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 20, remaining_hours: 12 };
  assert.equal(maintenanceDueInBucket(item, NOW, t), "maintenance.due_in_days:6");
});

test("[DUE-2] replacement items are skipped (interval lives in firmware, not reset_at)", () => {
  const item = { kind: "replacement", reset_at: RESET_10D, used_since_reset_hours: 20, remaining_hours: 12 };
  assert.equal(maintenanceDueInBucket(item, NOW, t), null);
});

test("[DUE-3] missing required fields -> null (each guarded independently)", () => {
  const base = { kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 20, remaining_hours: 12 };
  assert.equal(maintenanceDueInBucket({ ...base, remaining_hours: undefined }, NOW, t), null);
  assert.equal(maintenanceDueInBucket({ ...base, used_since_reset_hours: "not-a-number" }, NOW, t), null);
  assert.equal(maintenanceDueInBucket({ ...base, reset_at: null }, NOW, t), null);
  assert.equal(maintenanceDueInBucket(null, NOW, t), null);
});

test("[DUE-4] unparseable reset_at -> null", () => {
  const item = { kind: "maintenance", reset_at: "definitely-not-a-date", used_since_reset_hours: 20, remaining_hours: 12 };
  assert.equal(maintenanceDueInBucket(item, NOW, t), null);
});

test("[DUE-5] <3 days of history -> null (rate is noise below the guard)", () => {
  const item = { kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 20, remaining_hours: 12 };
  // now only ~2 days after reset: daysSinceReset < 3 -> guard trips.
  const now2d = Date.parse("2026-06-26T00:00:00Z");
  assert.equal(maintenanceDueInBucket(item, now2d, t), null);
  // exactly 3.0 days clears the guard (>= 3), so it returns a real bucket.
  const now3d = Date.parse("2026-06-27T00:00:00Z");
  assert.notEqual(maintenanceDueInBucket(item, now3d, t), null);
});

test("[DUE-6] <0.1 h/day of usage -> null (projection would overflow to meaningless)", () => {
  // 10 days, 0.5 h used -> 0.05 h/day (< 0.1) -> guard trips.
  const item = { kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 0.5, remaining_hours: 12 };
  assert.equal(maintenanceDueInBucket(item, NOW, t), null);
  // 1.0 h used -> 0.1 h/day exactly clears the guard (>= 0.1).
  const item2 = { ...item, used_since_reset_hours: 1.0 };
  assert.notEqual(maintenanceDueInBucket(item2, NOW, t), null);
});

test("[DUE-7] remaining_hours <= 0 -> overdue, short-circuiting the projection", () => {
  const item = { kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 20, remaining_hours: 0 };
  assert.equal(maintenanceDueInBucket(item, NOW, t), "maintenance.due_overdue");
  assert.equal(maintenanceDueInBucket({ ...item, remaining_hours: -5 }, NOW, t), "maintenance.due_overdue");
});

test("[DUE-8] bucket thresholds: today / tomorrow / days / weeks / months", () => {
  // 10 days, 10 h used -> 1 h/day, so remaining_hours == daysRemaining. Pick values to
  // land in each bucket boundary. Rate = 1 h/day.
  const mk = (remaining_hours) =>
    ({ kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 10, remaining_hours });

  assert.equal(maintenanceDueInBucket(mk(0.5), NOW, t), "maintenance.due_today");      // 0.5 < 1
  assert.equal(maintenanceDueInBucket(mk(1.5), NOW, t), "maintenance.due_tomorrow");   // 1 <= x < 2
  assert.equal(maintenanceDueInBucket(mk(6), NOW, t), "maintenance.due_in_days:6");    // 2 <= x < 14
  // 21 days -> weeks bucket, round(21/7) = 3
  assert.equal(maintenanceDueInBucket(mk(21), NOW, t), "maintenance.due_in_weeks:3");  // 14 <= x < 60
  // 90 days -> months bucket, round(90/30) = 3
  assert.equal(maintenanceDueInBucket(mk(90), NOW, t), "maintenance.due_in_months:3"); // x >= 60
});

test("[DUE-9] bucket boundaries are half-open at 1, 2, 14, 60 days", () => {
  const mk = (remaining_hours) =>
    ({ kind: "maintenance", reset_at: RESET_10D, used_since_reset_hours: 10, remaining_hours }); // 1 h/day

  // exactly 1 day -> NOT today (1 < 1 is false), falls to tomorrow
  assert.equal(maintenanceDueInBucket(mk(1), NOW, t), "maintenance.due_tomorrow");
  // exactly 2 days -> NOT tomorrow, falls to days bucket, round(2) = 2
  assert.equal(maintenanceDueInBucket(mk(2), NOW, t), "maintenance.due_in_days:2");
  // exactly 14 days -> NOT days, weeks bucket, round(14/7) = 2
  assert.equal(maintenanceDueInBucket(mk(14), NOW, t), "maintenance.due_in_weeks:2");
  // exactly 60 days -> NOT weeks, months bucket, round(60/30) = 2
  assert.equal(maintenanceDueInBucket(mk(60), NOW, t), "maintenance.due_in_months:2");
});

test("[DUE-10] the proto method delegates: identical output via the mixin (uses real Date.now)", () => {
  // Reach the delegating wrapper. reset_at is 10 days before a live now, so the guards
  // clear regardless of the exact wall clock. t is stubbed so the label is assertable.
  const r = makeRenderers();
  r.t = (key, vars) => (vars && "count" in vars ? `${key}:${vars.count}` : key);
  const tenDaysAgo = new Date(Date.now() - 10 * 86_400_000).toISOString();
  // 10 days, 20 h used -> 2 h/day; remaining 12 h -> 6 days.
  const item = { kind: "maintenance", reset_at: tenDaysAgo, used_since_reset_hours: 20, remaining_hours: 12 };
  assert.equal(r._maintenanceDueInLabel(item), "maintenance.due_in_days:6");
  // replacement short-circuits the same way through the wrapper
  assert.equal(r._maintenanceDueInLabel({ ...item, kind: "replacement" }), null);
});

/* ============================================================
   _maintenanceItemNeedsAttention — [ATT-*]
   ============================================================ */

test("[ATT-1] any explicit backend flag forces attention", () => {
  const r = makeRenderers();
  for (const flag of ["needs_attention", "attention_required", "warning", "overdue", "due"]) {
    assert.equal(r._maintenanceItemNeedsAttention({ [flag]: true }), true, `flag ${flag}`);
  }
  // strictly === true: a truthy-but-not-true value does NOT trip the flag path
  assert.equal(r._maintenanceItemNeedsAttention({ needs_attention: 1 }), false);
  assert.equal(r._maintenanceItemNeedsAttention({ overdue: "yes" }), false);
});

test("[ATT-2] status allowlist (warning/replace_soon/replace_now), case/space-insensitive", () => {
  const r = makeRenderers();
  assert.equal(r._maintenanceItemNeedsAttention({ status: "warning" }), true);
  assert.equal(r._maintenanceItemNeedsAttention({ status: "replace_soon" }), true);
  assert.equal(r._maintenanceItemNeedsAttention({ status: "  REPLACE_NOW  " }), true); // trimmed + lowered
  // a status NOT on the allowlist and no other trigger -> false
  assert.equal(r._maintenanceItemNeedsAttention({ status: "good" }), false);
  assert.equal(r._maintenanceItemNeedsAttention({ status: "unknown" }), false);
});

test("[ATT-3] remaining_percent <= 20 qualifies; > 20 does not; boundary at 20", () => {
  const r = makeRenderers();
  assert.equal(r._maintenanceItemNeedsAttention({ remaining_percent: 20 }), true);   // <= 20 inclusive
  assert.equal(r._maintenanceItemNeedsAttention({ remaining_percent: 5 }), true);
  assert.equal(r._maintenanceItemNeedsAttention({ remaining_percent: 0 }), true);
  assert.equal(r._maintenanceItemNeedsAttention({ remaining_percent: 20.01 }), false); // just over
  assert.equal(r._maintenanceItemNeedsAttention({ remaining_percent: 80 }), false);
  // non-numeric remaining_percent is ignored (Number.isFinite guard), not treated as 0
  assert.equal(r._maintenanceItemNeedsAttention({ remaining_percent: "n/a" }), false);
});

test("[ATT-4] no trigger anywhere / non-object -> false", () => {
  const r = makeRenderers();
  assert.equal(r._maintenanceItemNeedsAttention({}), false);
  assert.equal(r._maintenanceItemNeedsAttention({ status: "good", remaining_percent: 50 }), false);
  assert.equal(r._maintenanceItemNeedsAttention(null), false);
  assert.equal(r._maintenanceItemNeedsAttention(undefined), false);
  assert.equal(r._maintenanceItemNeedsAttention("not-an-object"), false);
});

/* ============================================================
   _maintenanceRemainingPercent — [PCT-*]
   ============================================================ */

test("[PCT-1] explicit remaining_percent wins verbatim (even out-of-range / <=0)", () => {
  const r = makeRenderers();
  assert.equal(r._maintenanceRemainingPercent({ remaining_percent: 42 }), 42);
  // finite is returned as-is; the caller (not this fn) clamps to 0..100.
  assert.equal(r._maintenanceRemainingPercent({ remaining_percent: 130 }), 130);
  assert.equal(r._maintenanceRemainingPercent({ remaining_percent: 0 }), 0);
  assert.equal(r._maintenanceRemainingPercent({ remaining_percent: -10 }), -10);
});

test("[PCT-2] maintenance branch: remaining_hours / interval_hours * 100", () => {
  const r = makeRenderers();
  // kind defaults toward maintenance (not "replacement") -> interval_hours is the denom.
  assert.equal(r._maintenanceRemainingPercent({ kind: "maintenance", remaining_hours: 15, interval_hours: 60 }), 25);
  // absent kind is also NOT "replacement" -> maintenance denom (interval_hours)
  assert.equal(r._maintenanceRemainingPercent({ remaining_hours: 30, interval_hours: 60 }), 50);
});

test("[PCT-3] replacement branch: max_life_hours preferred, else total_life_hours", () => {
  const r = makeRenderers();
  assert.equal(
    r._maintenanceRemainingPercent({ kind: "replacement", remaining_hours: 50, max_life_hours: 200 }),
    25
  );
  // max_life_hours absent -> total_life_hours is the fallback denom
  assert.equal(
    r._maintenanceRemainingPercent({ kind: "replacement", remaining_hours: 50, total_life_hours: 100 }),
    50
  );
  // a replacement item must NOT read interval_hours: with only interval_hours the denom
  // is undefined -> null (proves the branch really switched on kind).
  assert.equal(
    r._maintenanceRemainingPercent({ kind: "replacement", remaining_hours: 50, interval_hours: 100 }),
    null
  );
});

test("[PCT-4] indeterminate -> null: missing denom, non-finite, or non-positive max", () => {
  const r = makeRenderers();
  assert.equal(r._maintenanceRemainingPercent({ remaining_hours: 10 }), null);            // no interval
  assert.equal(r._maintenanceRemainingPercent({ interval_hours: 60 }), null);             // no remaining
  assert.equal(r._maintenanceRemainingPercent({ remaining_hours: 10, interval_hours: 0 }), null);   // max <= 0
  assert.equal(r._maintenanceRemainingPercent({ remaining_hours: 10, interval_hours: -5 }), null);  // max < 0
  assert.equal(r._maintenanceRemainingPercent({}), null);
  assert.equal(r._maintenanceRemainingPercent(null), null);
});
