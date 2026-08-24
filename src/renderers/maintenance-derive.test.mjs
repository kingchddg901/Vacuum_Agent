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
  const inst = Object.create(proto);
  // Echo resolver, same idea as `t` above: _maintenancePrimaryValue composes its
  // answer from i18n KEYS, so returning the key makes "which branch fired" the
  // thing under assertion rather than any particular English wording.
  inst.tRaw = (key) => key;
  inst._formatMaintenanceHours = (h) => String(h);
  return inst;
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

test("[ATT-4] an UNKNOWN item is not attention, even at 0% (issue #51)", () => {
  const r = makeRenderers();
  // A Roborock exposes five consumables; dustbin/wheels/tanks have no telemetry to
  // give, so they arrive 0 hours of 0 hours and score 0%. The percent fallback used
  // to flag all eight, while the backend's own attention_count -- which counts only
  // {warning, replace_soon, replace_now} -- said zero. The same screen therefore read
  // "ATTENTION 0 / No upkeep items need attention" above a full Needs Attention list.
  assert.equal(
    r._maintenanceItemNeedsAttention({ status: "unknown", remaining_percent: 0 }), false);
  assert.equal(
    r._maintenanceItemNeedsAttention({
      status: "unknown", remaining_percent: 0, remaining_hours: 0, interval_hours: 0,
    }), false);

  // The status allowlist still wins over the unknown short-circuit ordering, and an
  // explicit backend flag still wins over everything -- an unknown STATUS must not
  // become a way to silence a real signal.
  assert.equal(
    r._maintenanceItemNeedsAttention({ status: "replace_now", remaining_percent: 0 }), true);
  assert.equal(
    r._maintenanceItemNeedsAttention({ status: "unknown", needs_attention: true }), true);

  // A KNOWN item at 0% is still attention -- that is a worn part, not a missing one.
  assert.equal(
    r._maintenanceItemNeedsAttention({ status: "good", remaining_percent: 0 }), true);
});

test("[PV-1] no data renders UNKNOWN, not '0% remaining' (issue #51)", () => {
  const r = makeRenderers();
  // Untracked maintenance item: unknown status AND no interval to measure against.
  assert.equal(
    r._maintenancePrimaryValue({
      kind: "maintenance", status: "unknown",
      remaining_percent: 0, remaining_hours: 0, interval_hours: 0,
    }),
    "maintenance.unknown_remaining_life");

  // Untracked replacement: same, via max_life_hours.
  assert.equal(
    r._maintenancePrimaryValue({
      kind: "replacement", status: "unknown",
      remaining_percent: 0, remaining_hours: 0, max_life_hours: 0,
    }),
    "maintenance.unknown_remaining_life");

  // NARROW: unknown status but a real life to measure against still reports its
  // percentage. Suppressing that would throw away information we actually have.
  assert.equal(
    r._maintenancePrimaryValue({
      kind: "replacement", status: "unknown",
      remaining_percent: 77, remaining_hours: 232.3, max_life_hours: 300,
    }),
    "maintenance.percent_remaining");

  // A known item at 0% still says 0% -- worn, not missing.
  assert.equal(
    r._maintenancePrimaryValue({
      kind: "maintenance", status: "replace_now",
      remaining_percent: 0, remaining_hours: 0, interval_hours: 300,
    }),
    "maintenance.percent_remaining");
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

/* ============================================================
   _formatMaintenanceFrequency — [FREQ-*]
   ============================================================
   Ran on nothing until 2026-08-07: the single call site was
   `guide?.frequency || _formatMaintenanceFrequency(guide?.frequency)`, so it
   was only ever invoked with a value it had already established was falsy, and
   it returns "" for falsy input. Dead by construction, while the live branch
   printed the value raw — English cards read lowercase "weekly"/"monthly"
   while de/pl/ru read properly-cased prose from the guide catalogue.
   These pin the real function, not a transcription of it.
*/

// The `lang` the formatter reads. A hass stand-in that is TRUTHY but stringifies
// to "" is the shape that crashed the render, so it is a first-class case here.
const freqHost = (lang) => {
  const r = makeRenderers();
  r._i18nLanguage = () => lang;
  return r;
};

test("[FREQ-1] a lowercase English fragment is raised to sentence case", () => {
  const r = freqHost("en");
  assert.equal(r._formatMaintenanceFrequency("weekly"), "Weekly");
  assert.equal(r._formatMaintenanceFrequency("monthly"), "Monthly");
});

test("[FREQ-2] already-cased prose is returned unchanged — NOT title-cased", () => {
  // Title-casing every word is wrong in the target language: "Раз В Неделю" and
  // "Einmal Pro Woche" are both incorrect. Only char 0 may be raised.
  assert.equal(freqHost("de")._formatMaintenanceFrequency("Einmal pro Woche"), "Einmal pro Woche");
  assert.equal(freqHost("ru")._formatMaintenanceFrequency("Раз в неделю"), "Раз в неделю");
  assert.equal(freqHost("pl")._formatMaintenanceFrequency("Co tydzień"), "Co tydzień");
});

test("[FREQ-3] hyphens survive; only underscores collapse", () => {
  const r = freqHost("en");
  // The real bundled value. The old `[_-]+` class would have produced
  // "Every 3 6 months" — latent only because nothing called the function.
  assert.equal(r._formatMaintenanceFrequency("every 3-6 months"), "Every 3-6 months");
  // A backend that sends a CODE instead of prose still reads correctly.
  assert.equal(r._formatMaintenanceFrequency("every_3_months"), "Every 3 months");
});

test("[FREQ-4] blank input stays blank (the card omits the line entirely)", () => {
  const r = freqHost("en");
  for (const v of ["", "   ", null, undefined]) {
    assert.equal(r._formatMaintenanceFrequency(v), "");
  }
});

test("[FREQ-5] a truthy language that stringifies to \"\" must not throw", () => {
  // REGRESSION PIN. `String(_i18nLanguage() || "en")` looks correct and is not:
  // the harness hass null-object is truthy, so `||` never fires, String() gives
  // "", and toLocaleUpperCase("") throws RangeError — which took out the whole
  // maintenance render for the default locale. Defaulting must happen AFTER
  // stringifying.
  // The load-bearing shape is exactly "truthy, but String() gives empty" —
  // which is what the harness hass null-object does at the end of a miss chain.
  const emptyish = { toString: () => "", valueOf: () => "" };
  assert.ok(emptyish, "the fake must be TRUTHY or it does not reproduce the bug");
  assert.equal(String(emptyish), "");
  assert.equal(freqHost(emptyish)._formatMaintenanceFrequency("weekly"), "Weekly");
  assert.equal(freqHost("")._formatMaintenanceFrequency("weekly"), "Weekly");
  assert.equal(freqHost(undefined)._formatMaintenanceFrequency("weekly"), "Weekly");
});

test("[FREQ-6] Turkish raises dotless i correctly", () => {
  // tr ships. toUpperCase() would give "Iki"; the locale-aware form gives "İki".
  assert.equal(freqHost("tr")._formatMaintenanceFrequency("iki haftada bir"), "İki haftada bir");
  // and a regional tag still resolves to the base language
  assert.equal(freqHost("tr-TR")._formatMaintenanceFrequency("iki haftada bir"), "İki haftada bir");
});

/* ============================================================
   [LG-*] _localizedGuide — script/region locales (zh-Hans, zh-Hant)
   ============================================================ */

// Task 15: the pre-fix code did `String(this._i18nLanguage() || "en").split("-")[0]`,
// so `zh-Hans` collapsed to `zh` and the GUIDE_TRANSLATIONS lookup missed for both
// Chinese variants — a whole-locale regression silently falling back to English
// steps/notes/frequency. These tests would have caught it.
//
// Uses the REAL GUIDE_TRANSLATIONS bundle rather than a stub, because that is where
// the shape lives (roborock.upkeep_guides_i18n.zh_hans keys the map by "zh-Hans").
// A stub might have hidden the collapse.

function guideHost(lang) {
  const proto = {};
  applyMaintenanceRenderers(proto);
  const inst = Object.create(proto);
  inst._i18nLanguage = () => lang;
  return inst;
}

const _ITEM = {
  kind: "maintenance",
  component: "main_brush",
  guide: {
    display: { steps: ["EN step 1"], notes: [], frequency: "weekly" },
    source_guide_family: "standard",
  },
};

// A cheap language-identity check that beats "not equal to my English fixture":
// the previous version of this test only checked step0 !== "EN step 1", which is
// satisfied by the English translation from the bundle when the split-bug is back
// and the lookup falls all the way through to `byEn`. Han-script detection is
// robust to future edits of the translation strings themselves.
const HAN = /\p{Script=Han}/u;

test("[LG-1] zh-Hans picks up the zh_hans upkeep guide (roborock 'standard' family)", () => {
  const inst = guideHost("zh-Hans");
  const g = inst._localizedGuide(_ITEM);
  assert.ok(g, "guide should resolve");
  const step0 = String(g.steps?.[0] ?? "");
  assert.ok(HAN.test(step0),
    `zh-Hans steps did not contain Han script -- the split("-")[0] bug is back: ${JSON.stringify(step0)}`);
});

test("[LG-2] zh-Hant picks up the zh_hant upkeep guide", () => {
  const inst = guideHost("zh-Hant");
  const g = inst._localizedGuide(_ITEM);
  const step0 = String(g?.steps?.[0] ?? "");
  assert.ok(HAN.test(step0),
    `zh-Hant steps did not contain Han script: ${JSON.stringify(step0)}`);
});

test("[LG-3] a region-only variant still resolves via the base language", () => {
  // pt-BR should still find pt-branch guide translations via the base fallback.
  // (pt has translations shipped for the standard family.)
  const inst = guideHost("pt-BR");
  const g = inst._localizedGuide(_ITEM);
  assert.ok(g, "guide should resolve via base fallback");
  // We don't compare to English here — pt may or may not translate 'main_brush' —
  // but the lookup MUST have run without raising or returning null.
});

test("[LG-4] an unknown language falls all the way to English (never null, never raise)", () => {
  const inst = guideHost("xx-ZZ");
  const g = inst._localizedGuide(_ITEM);
  assert.ok(g, "unknown language should still get an English-fallback guide, not null");
});

/* ============================================================
   [MIN-*] _maintenanceItemName — task 16: i18n'd component labels
   ============================================================ */

function nameHost(componentKey_translation_map) {
  const proto = {};
  applyMaintenanceRenderers(proto);
  const inst = Object.create(proto);
  // `t` echoes the key when no translation is provided — the real translate
  // contract does this too (`key.for.missing` -> "key.for.missing"). The
  // helper is expected to treat that round-trip as "no translation", NOT as
  // a real label — otherwise a bare i18n key would leak into the modal title
  // whenever a component grew without a matching pack entry.
  inst.t = (key) => componentKey_translation_map[key] ?? key;
  return inst;
}

test("[MIN-1] a translated component key wins over the backend label", () => {
  const inst = nameHost({
    "maintenance.component_label.main_brush": "主刷",
  });
  const item = { component: "main_brush", label: "Main Brush" };
  assert.equal(inst._maintenanceItemName(item), "主刷");
});

test("[MIN-2] a MISSING translation falls through to the backend label — never a bare key", () => {
  // The bug the helper prevents: `this.t("maintenance.component_label.xyz")` when
  // xyz has no pack entry returns the bare KEY. Rendering that in the modal title
  // would be worse than a plain English label, so the helper detects the key-echo
  // and falls back.
  const inst = nameHost({});  // no keys at all
  const item = { component: "main_brush", label: "Main Brush" };
  const name = inst._maintenanceItemName(item);
  assert.equal(name, "Main Brush",
    `expected the backend label; got bare key: ${JSON.stringify(name)}`);
});

test("[MIN-3] no component key at all -> backend label chain, no throw", () => {
  const inst = nameHost({});
  const item = { label: "Custom Thing" };
  assert.equal(inst._maintenanceItemName(item), "Custom Thing");
});

test("[MIN-4] nothing to fall back on -> final i18n fallback (translated or the key)", () => {
  const inst = nameHost({
    "maintenance.unnamed_item": "Unnamed item",
  });
  assert.equal(inst._maintenanceItemName(null), "Unnamed item");
});
