// Run: node --test src/renderers/review-error-badge.test.mjs
//
// Backlog item "Card: surface captured run errors (run_errors)". The backend has
// carried error evidence end to end for both origins — the dispatched finalizer
// and the app-started ingest write the SAME keys onto `outcome` on purpose — and
// nothing displayed it. A run that hit a fault looked identical in the review
// list to one that ran clean.
//
// Coverage (REB = REview error Badge):
//   [REB-1] had_errors with a count -> a warning badge naming the count
//   [REB-2] had_errors with no usable count -> the countless fallback badge
//   [REB-3] a measured duration rides the TOOLTIP, not the badge text
//   [REB-4] an UNMEASURED duration produces no tooltip — never "0s"
//   [REB-5] a clean run gets no badge at all (control)
//   [REB-7] the SOURCE split rides the tooltip — dock vs robot vs unattributed
//   [REB-8] unattributed is named explicitly; silence would imply attribution
//   [REB-9] a source with no seconds is never mentioned
//   [REB-10] a record with no source block still gets the plain duration tooltip
//   [REB-11] the badge requests the warning glyph
//   [REB-12] the glyph is inline SVG — never U+26A0 (absent from OpenDyslexic,
//            and its emoji presentation ignores CSS color)
//   [REB-13] only the ERROR badge takes it, not every --warning chip
//   [REB-14] an unknown or PROTOTYPE-INHERITED icon name resolves to nothing

import { test } from "node:test";
import assert from "node:assert/strict";

/** Minimal renderer host: only what the badge block touches. */
function badgesFor(job) {
  const pushed = [];
  const host = {
    t: (key, vars = {}) =>
      `${key}${Object.keys(vars).length ? `(${JSON.stringify(vars)})` : ""}`,
  };

  // The block under test, transcribed from renderers/review.js. Kept in step by
  // [REB-6] below, which asserts the source still contains it.
  if (job?.had_errors === true) {
    const errorCount = Number(job?.error_count);
    const errorSeconds = Number(job?.total_error_seconds);
    const bySource = job?.error_seconds_by_source;
    const sourceParts = [];
    if (bySource && typeof bySource === "object") {
      const dock = Math.round(Number(bySource.dock));
      const robot = Math.round(Number(bySource.robot));
      const unknown = Math.round(Number(bySource.unknown));
      if (Number.isFinite(dock) && dock > 0) sourceParts.push(host.t("review.badge_errors_from_dock", { seconds: dock }));
      if (Number.isFinite(robot) && robot > 0) sourceParts.push(host.t("review.badge_errors_from_robot", { seconds: robot }));
      if (Number.isFinite(unknown) && unknown > 0) sourceParts.push(host.t("review.badge_errors_unattributed", { seconds: unknown }));
    }
    const titleParts = [];
    if (Number.isFinite(errorSeconds) && errorSeconds > 0) {
      titleParts.push(host.t("review.badge_errors_seconds", { seconds: Math.round(errorSeconds) }));
    }
    titleParts.push(...sourceParts);
    pushed.push({
      text: Number.isFinite(errorCount) && errorCount > 0
        ? host.t("review.badge_errors_count", { count: errorCount })
        : host.t("review.badge_errors"),
      cls: "evcc-review-badge--warning",
      icon: "warning",
      title: titleParts.length ? titleParts.join(" · ") : null,
    });
  }
  return pushed;
}

/** The renderer's icon lookup, transcribed. Pinned by [REB-6] / [REB-13]. */
function iconFor(badge) {
  const BADGE_ICONS = Object.freeze({ warning: "<svg class=\"evcc-chip-icon\"></svg>" });
  return badge.icon && Object.hasOwn(BADGE_ICONS, badge.icon) ? BADGE_ICONS[badge.icon] : "";
}

test("[REB-1] a run with errors gets a warning badge naming the count", () => {
  const [badge] = badgesFor({ had_errors: true, error_count: 3 });
  assert.ok(badge, "a run that hit faults rendered identically to a clean one");
  assert.equal(badge.cls, "evcc-review-badge--warning");
  assert.match(badge.text, /badge_errors_count/);
  assert.match(badge.text, /"count":3/);
});

test("[REB-2] errors with no usable count fall back to the countless badge", () => {
  for (const job of [
    { had_errors: true },
    { had_errors: true, error_count: 0 },
    { had_errors: true, error_count: null },
  ]) {
    const [badge] = badgesFor(job);
    assert.ok(badge, `no badge for ${JSON.stringify(job)}`);
    assert.equal(badge.text, "review.badge_errors");
  }
});

test("[REB-3] a measured duration rides the tooltip, not the badge text", () => {
  const [badge] = badgesFor({ had_errors: true, error_count: 2, total_error_seconds: 41.6 });
  assert.match(badge.text, /badge_errors_count/, "the duration leaked into the badge label");
  assert.match(badge.title, /badge_errors_seconds/);
  assert.match(badge.title, /"seconds":42/, "seconds should be rounded for display");
});

test("[REB-4] an UNMEASURED duration produces no tooltip, never 0s", () => {
  // The app-started ingest omits total_error_seconds deliberately — it has no
  // per-phase timings to derive it from. Rendering "0s" would assert the run
  // spent no time in error, a stronger claim than "we did not measure it".
  for (const job of [
    { had_errors: true, error_count: 1 },
    { had_errors: true, error_count: 1, total_error_seconds: null },
    { had_errors: true, error_count: 1, total_error_seconds: 0 },
  ]) {
    const [badge] = badgesFor(job);
    assert.equal(badge.title, null, `unmeasured duration rendered: ${JSON.stringify(job)}`);
  }
});

test("[REB-5] a clean run gets no badge (control)", () => {
  for (const job of [
    { had_errors: false, error_count: 0 },
    {},
    { had_errors: "false" },      // string, not the boolean the backend sends
  ]) {
    assert.deepEqual(badgesFor(job), [], `spurious badge for ${JSON.stringify(job)}`);
  }
});

test("[REB-6] the renderer still contains the block this file transcribes", async () => {
  // A transcribed block can drift from its original silently. This is the cheap
  // guard: the real source must still push the badge on had_errors, and must
  // still gate the tooltip on a finite positive duration.
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");

  assert.match(src, /job\?\.had_errors === true/);
  assert.match(src, /review\.badge_errors_count/);
  assert.match(src, /Number\.isFinite\(errorSeconds\) && errorSeconds > 0/);
  // and the source split this file now transcribes
  assert.match(src, /error_seconds_by_source/);
  assert.match(src, /review\.badge_errors_unattributed/);
  // and the icon: the badge must still REQUEST it, and the renderer must still
  // resolve it through an own-property check rather than a bare index.
  assert.match(src, /icon:\s*"warning"/);
  assert.match(src, /Object\.hasOwn\(BADGE_ICONS,\s*badge\.icon\)/);
});


test("[REB-11] the error badge requests the warning glyph", () => {
  const [badge] = badgesFor({ had_errors: true, error_count: 3 });
  assert.equal(badge.icon, "warning");
  assert.notEqual(iconFor(badge), "", "the badge asked for an icon and got nothing");
});

test("[REB-12] the glyph is inline SVG, never a unicode warning sign", async () => {
  // U+26A0 is absent from BOTH shipped OpenDyslexic faces (measured: 1586
  // codepoints, no U+26A0), and its emoji presentation ignores CSS color — it
  // would sit in a --evcc-sem-warning row refusing the theme. check-styles lints
  // CSS declarations and cannot see a glyph that bypasses CSS, so this is the
  // only place that failure can be caught.
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./review.js", import.meta.url), "utf-8");

  assert.ok(!src.includes("⚠"), "a raw U+26A0 WARNING SIGN reached the renderer");
  assert.ok(!src.includes("⚡"), "a raw U+26A1 reached the renderer");
  assert.match(src, /<svg class="evcc-chip-icon"/);
  // currentColor, so the glyph inherits whichever semantic token the chip set.
  assert.match(src, /fill="currentColor"/);
  // The badge text is the accessible name; the glyph must not be announced too.
  assert.match(src, /aria-hidden="true"/);
});

test("[REB-13] only the ERROR badge takes the glyph, not every warning chip", () => {
  // sanity-failed and non-completed runs share evcc-review-badge--warning and are
  // a DIFFERENT claim. A triangle on those would say a fault occurred when none did.
  for (const badge of [
    { cls: "evcc-review-badge--warning" },              // sanity failed / status
    { cls: "evcc-review-badge--neutral" },
    { cls: "evcc-review-badge--excluded" },
  ]) {
    assert.equal(iconFor(badge), "", `an unrelated badge rendered a glyph: ${badge.cls}`);
  }
});

test("[REB-14] an unknown or inherited icon name resolves to nothing", () => {
  // A bare `BADGE_ICONS[badge.icon]` would resolve these to prototype junk and
  // splice it straight into the DOM the day this field takes an outside value.
  for (const name of ["constructor", "toString", "__proto__", "hasOwnProperty", "nope"]) {
    assert.equal(iconFor({ icon: name }), "", `"${name}" resolved to something`);
  }
  assert.equal(iconFor({}), "", "a badge with no icon field rendered one");
});


test("[REB-7] the source split rides the tooltip (RF-DOCK clause 4)", () => {
  // The DOCK-1 shape: five station faults, correctly NOT deducted, and the card
  // used to say only "errors" — the user was told their run was fine and never
  // told their dock's water pump was failing.
  const [badge] = badgesFor({
    had_errors: true, error_count: 5, total_error_seconds: 455,
    error_seconds_by_source: { dock: 455, robot: 0, unknown: 0 },
  });
  assert.match(badge.title, /badge_errors_seconds/);
  assert.match(badge.title, /badge_errors_from_dock/);
  assert.match(badge.title, /"seconds":455/);
  assert.doesNotMatch(badge.title, /from_robot/, "a dock-only run must not mention the robot");
});

test("[REB-8] unattributed seconds are named, not silently omitted", () => {
  // A brand that classifies nothing (Roborock before RB-ERR-1, or any code added
  // after a table was written) must not read as "we know it was the robot".
  const [badge] = badgesFor({
    had_errors: true, error_count: 2, total_error_seconds: 30,
    error_seconds_by_source: { dock: 0, robot: 0, unknown: 30 },
  });
  assert.match(badge.title, /badge_errors_unattributed/);
  assert.doesNotMatch(badge.title, /from_dock|from_robot/);
});

test("[REB-9] a mixed run names both sources, and omits the empty one", () => {
  const [badge] = badgesFor({
    had_errors: true, error_count: 4, total_error_seconds: 100,
    error_seconds_by_source: { dock: 60, robot: 40, unknown: 0 },
  });
  assert.match(badge.title, /from_dock/);
  assert.match(badge.title, /from_robot/);
  assert.doesNotMatch(badge.title, /unattributed/);
});

test("[REB-10] no source block still yields the plain duration tooltip (back-compat)", () => {
  // Records written before the finalizer carried error_seconds_by_source, and any
  // path that omits it, must keep behaving exactly as before.
  const [badge] = badgesFor({ had_errors: true, error_count: 1, total_error_seconds: 12 });
  assert.match(badge.title, /badge_errors_seconds/);
  assert.doesNotMatch(badge.title, /from_dock|from_robot|unattributed/);
});
