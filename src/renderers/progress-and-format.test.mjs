// Regression tests — two renderers that showed the user a plainly wrong thing.
//
// [FE-LRN-1] The live-progress list dispatched on completed/current and then had an
//   all-flags-false CATCH-ALL that routed the entry into the CURRENT row. A backend-flagged
//   SKIPPED room has all three false, so it rendered as "▶ <Room>" in the actively-cleaning
//   style — several rows at once claiming to be the room under the robot. The sibling
//   queue-chip surface already read `entry.skipped`; this list never did.
//
// [FE-MET-1] numFmt trimmed trailing zeros with /\.?0+$/. The dot is OPTIONAL there, so on
//   a whole number it ate the number's own trailing zeros: 100 -> "1", 90 -> "9", 20 -> "2",
//   and 0 -> "" (a blank cell). Battery health rendered an order of magnitude wrong.
//
// Run: node --test src/renderers/progress-and-format.test.mjs
//
// Coverage (PF = Progress/Format):
//   [PF-1] a skipped entry does NOT render as the current row
//   [PF-2] a skipped entry is marked skipped and carries no ETA
//   [PF-3] an unclassifiable entry falls to REMAINING, not current
//   [PF-4] a genuinely current entry still renders as current
//   [PF-5] numFmt preserves whole numbers (100/90/20) and zero
//   [PF-6] numFmt still trims real fractional zeros
//   [PF-7] the SHIPPED numFmt still requires a dot before trimming zeros
//   [PF-8] the SHIPPED timeline dispatch still tests `skipped` before the catch-all
//   [PF-9]  formatTimestamp follows the CARD's language, not the browser's
//   [PF-10] a draft system language still gates to English, dates included
//   [PF-11] a malformed user-supplied locale tag does not take the card down
//   [PF-12] the identifier surfaces still print job_id verbatim

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySharedRenderers } from "./shared.js";

// The formatter under test, mirrored exactly from src/renderers/metrics.js.
const numFmt = (raw, digits = 2) => {
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
};

// Minimal harness for the row dispatch in src/renderers/learning.js.
function dispatch(entry) {
  if (entry.completed) return "completed";
  if (entry.current) return "current";
  if (entry.skipped) return "remaining:skipped";
  return "remaining";
}

test("[PF-1] a skipped entry does not render as the current row", () => {
  const row = dispatch({ completed: false, current: false, remaining: false, skipped: true });
  assert.notEqual(row, "current", "a skipped room was shown as currently cleaning");
});

test("[PF-2] a skipped entry is marked skipped", () => {
  assert.equal(
    dispatch({ completed: false, current: false, remaining: false, skipped: true }),
    "remaining:skipped"
  );
});

test("[PF-3] an unclassifiable entry falls to remaining, not current", () => {
  // All flags false and NOT skipped — the old catch-all sent this to the current row.
  assert.equal(dispatch({ completed: false, current: false, remaining: false }), "remaining");
});

test("[PF-4] a genuinely current entry still renders as current", () => {
  assert.equal(dispatch({ current: true }), "current");
});

test("[PF-5] numFmt preserves whole numbers and zero", () => {
  assert.equal(numFmt(100, 0), "100", "battery health rendered an order of magnitude wrong");
  assert.equal(numFmt(90, 0), "90");
  assert.equal(numFmt(20, 0), "20");
  assert.equal(numFmt(0, 0), "0", "zero rendered as an empty cell");
});

test("[PF-6] numFmt still trims real fractional zeros", () => {
  assert.equal(numFmt(12.5, 2), "12.5");
  assert.equal(numFmt(3.0, 2), "3");
  assert.equal(numFmt(3.14159, 2), "3.14");
  assert.equal(numFmt("nope", 2), "—");
});

// [PF-7]/[PF-8] SOURCE PINS — added 2026-08-07 by the W0 v2 census.
//
// Everything above asserts the `numFmt` and `dispatch` copies declared at the top
// of THIS file. Both are faithful transcriptions, and both prove nothing about the
// shipped renderers: the real numFmt is a closure inside _renderMetricsBatteryTab
// (renderers/metrics.js), the real dispatch is an inline if-chain in
// renderers/learning.js, and neither is exported or referenced by any assertion
// here. Measured: restoring the FE-MET-1 regex in metrics.js leaves this whole
// file green while battery health renders "1" for 100 and a BLANK cell for 0.
//
// Both defects are shape/ordering facts visible in source, so pin them the way
// [C6-4] does in maintenance-census6.test.mjs. Substring checks rather than
// regexes-matching-regexes: the pattern being pinned is itself full of
// metacharacters, and an over-escaped matcher fails for reasons that have nothing
// to do with the code — which is exactly what happened on the first attempt.
test("[PF-7] the SHIPPED numFmt still requires a dot before trimming zeros", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./metrics.js", import.meta.url), "utf-8");

  assert.ok(
    src.includes('.replace(/(\\.\\d*?)0+$/, "$1")'),
    "numFmt's fractional-zero trim changed shape. The dot must be MANDATORY and inside "
    + "the capture; if it becomes optional again the trim eats the trailing zero DIGITS "
    + "of whole numbers (FE-MET-1: 100 -> '1', 90 -> '9', 0 -> blank).",
  );
  // Anchored on `.replace(`, NOT on the bare pattern. metrics.js DOCUMENTS the old
  // regex in a comment ("The previous pattern was /\.?0+$/, whose optional dot…"),
  // so a bare substring check flags the prose that explains the fix and fails
  // identically before and after the mutation — measuring nothing, which is the
  // very defect class this pin was added to close. Same trap that forced
  // scripts/mock_census.py off regexes and onto an AST.
  assert.ok(
    !src.includes(".replace(/\\.?0+$/"),
    "the FE-MET-1 regex is back in a live .replace() call in metrics.js — its optional "
    + "dot eats the trailing zeros of WHOLE numbers",
  );
});

test("[PF-8] the SHIPPED timeline dispatch still tests `skipped` before the catch-all", async () => {
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./learning.js", import.meta.url), "utf-8");

  const iCurrent = src.indexOf("entry.current");
  const iSkipped = src.indexOf("entry.skipped");
  assert.ok(iCurrent > 0, "the `entry.current` branch is gone from learning.js");
  assert.ok(iSkipped > 0, "the `entry.skipped` branch is gone from learning.js");
  // ORDER is the contract. With `skipped` removed or moved below the catch-all, a
  // skipped room falls through to the CURRENT row, and during an out-of-order run
  // the list shows several rooms at once marked as actively cleaning.
  assert.ok(
    iSkipped > iCurrent,
    "`entry.skipped` no longer follows `entry.current` in the dispatch chain",
  );
  assert.ok(
    /_renderLearningRemainingRow\(\s*entry\s*,\s*\{\s*skipped:\s*true\s*\}\s*\)/.test(src),
    "a skipped entry no longer routes to the REMAINING row — the all-flags-false "
    + "catch-all will render it as the currently-cleaning room",
  );
});


// [PF-9]..[PF-12] — the timestamp-locale split, added 2026-08-24.
//
// renderers/shared.js::formatTimestamp called `date.toLocaleString([], options)`.
// `[]` is the BROWSER/OS locale: not HA's language, and not the card's own globe
// override. So every string on a card pinned to Arabic came out Arabic except the
// dates, which came out in whatever the browser was set to.
//
// These exercise the SHIPPED function (applySharedRenderers onto a bare object),
// not a transcription of it — the failure [PF-7]/[PF-8] were added to close.
//
// The paired half of the ruling is that IDENTIFIER timestamps must NOT localize:
// a job record is stored as `job_2026-08-05T02-52-05.json` and the user pastes
// that string back into exclude_learning_job / restore_learning_job, so a
// reordered or renumbered rendering of it is a job that can no longer be found.
// [PF-12] pins that those surfaces still bypass the formatter entirely.

/** A renderer instance with the shared mixin, bound to a fake card. */
function makeRenderer({ systemLang = "en", pinned = null, override = null } = {}) {
  const proto = {};
  applySharedRenderers(proto);
  const inst = Object.create(proto);
  // _i18nLanguage reads `this.card` — renderers run on the INSTANCE, where only
  // `card` is set (see the comment on _i18nLanguage in shared.js).
  inst.card = {
    _hass: { locale: { language: systemLang } },
    _config: pinned ? { i18n: { locale: pinned } } : {},
    _langOverride: override,
  };
  return inst;
}

const INSTANT = "2026-08-05T02:52:05Z";
const OPTS = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" };

test("[PF-9] formatTimestamp follows the card's language, not the browser's", () => {
  // Two DIFFERENT card languages, one instant, one machine. Asserting "ar looks
  // Arabic" would pass pre-fix on a machine whose browser locale IS Arabic;
  // asserting the two languages DISAGREE cannot, because pre-fix both ignore the
  // argument and return the same browser-locale string whatever that string is.
  const ar = makeRenderer({ override: "ar" }).formatTimestamp(INSTANT, OPTS);
  const ja = makeRenderer({ override: "ja" }).formatTimestamp(INSTANT, OPTS);

  assert.notEqual(
    ar, ja,
    "two cards pinned to different languages rendered the same timestamp text — "
    + "the locale argument is being ignored (the `[]` browser-locale bug)",
  );
  // And the resolved language is the one the card asked for, not a near miss.
  assert.match(ar, /أغسطس/, "a card pinned to Arabic did not render an Arabic month");
  assert.match(ja, /月/, "a card pinned to Japanese did not render a Japanese month");
});

test("[PF-10] a draft system language still gates to English, dates included", () => {
  // `ar` is a DRAFT locale: resolveLang refuses to auto-activate it from the HA
  // system language, so the card's strings stay English. The dates must make the
  // same call — reading hass.locale.language directly instead of going through
  // _i18nLanguage would give an Arabic date on an otherwise English card.
  const gated = makeRenderer({ systemLang: "ar" }).formatTimestamp(INSTANT, OPTS);
  const english = makeRenderer({ override: "en" }).formatTimestamp(INSTANT, OPTS);

  assert.equal(
    gated, english,
    "an unreviewed (draft) system language localized the dates while the rest of "
    + "the card stayed English — the date path skipped the draft-gate",
  );
});

test("[PF-11] a malformed user-supplied locale tag does not take the card down", () => {
  // config.i18n.locale is hand-written YAML. `pt_BR` (underscore, not hyphen) is
  // structurally invalid and toLocaleString throws RangeError on it. Renderers
  // build one HTML string, so an escaping throw blanks the whole card over a typo.
  const inst = makeRenderer({ pinned: "pt_BR" });
  let out;
  assert.doesNotThrow(() => { out = inst.formatTimestamp(INSTANT, OPTS); },
    "a typo'd locale tag threw out of the formatter and into the render");
  assert.ok(out && out.length > 0, "the fallback returned nothing renderable");

  // The absent/invalid-VALUE contract is unchanged by the locale work.
  assert.equal(inst.formatTimestamp(null, OPTS), "");
  assert.equal(inst.formatTimestamp("not-a-date", OPTS, "—"), "—");
});

test("[PF-12] the identifier surfaces still print job_id verbatim", async () => {
  const fs = await import("node:fs");
  const review = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");
  const summary = fs.readFileSync(new URL("./job-summary.js", import.meta.url), "utf-8");

  // job_id is a FILENAME the user retypes into a service call, not a date. Route
  // it through formatTimestamp and `job_2026-08-05T02-52-05` becomes "٥ أغسطس"
  // on an Arabic card — no longer matching anything on disk.
  assert.match(
    review,
    /evcc-review-job-title">\$\{this\.escapeHtml\(jobId\)\}/,
    "the review job-card title no longer prints job_id verbatim",
  );
  assert.match(
    summary,
    /evcc-job-summary-subtitle">\$\{this\.escapeHtml\(jobId\)\}/,
    "the job-summary subtitle no longer prints job_id verbatim",
  );
  for (const [name, src] of [["review.js", review], ["job-summary.js", summary]]) {
    assert.ok(
      !/Timestamp\??\.?\(?\s*job\??\.\s*job_id/.test(src),
      `${name} routes job_id through a timestamp formatter — a localized id cannot `
      + "be matched back to the stored job file",
    );
  }
});
