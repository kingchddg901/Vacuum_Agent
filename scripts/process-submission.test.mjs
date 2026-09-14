/**
 * Unit tests for the theme submission processor. Run: node --test scripts/
 * Uses real gallery themes as fixtures (some pass colorblind, some don't).
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  processSubmission, parseVibeTags, slugify, isAcceptableAuthorUrl,
  resolveThemeName, themeNameKey, existingGalleryThemes,
} from "./process-submission.mjs";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..");
const themeJson = (slug) => readFileSync(join(repo, "gallery", "themes", `${slug}.json`), "utf8");

/** Build a realistic GitHub issue-form body. */
function makeBody({ json, tags = "", author = "", authorUrl = "", submittedBy = "", cb = false }) {
  const f = (v) => (v ? v : "_No response_");
  return [
    "### Theme export JSON", "", "```json", json, "```", "",
    "### Vibe tags", "", f(tags), "",
    "### Author", "", f(author), "",
    "### Author URL", "", f(authorUrl), "",
    "### Submitted by", "", f(submittedBy), "",
    "### Colorblind-safe claim", "", `- [${cb ? "X" : " "}] I'm claiming this theme is colorblind-safe`, "",
    "### Before you submit", "", "- [X] This is a theme export and I'm OK sharing it.", "",
  ].join("\n");
}

test("valid submission stamps community + keeps metadata (system words stripped)", () => {
  const body = makeBody({ json: themeJson("jewel-spiral"), tags: "Aurora, cosmic, Dark", author: "Ada L.", authorUrl: "https://example.com" });
  const r = processSubmission(body, 42);
  assert.equal(r.ok, true);
  assert.equal(r.envelope.theme.source, "community");
  assert.deepEqual(r.envelope.theme.tags, ["aurora", "cosmic"]); // "Dark" is a system word -> stripped
  assert.equal(r.envelope.theme.author, "Ada L.");
  assert.equal(r.envelope.theme.author_url, "https://example.com");
  assert.equal(r.slug, "jewel-spiral-42");
});

test("colorblind claim that passes -> verified, earns badge", () => {
  const r = processSubmission(makeBody({ json: themeJson("colorblind-safe"), cb: true }), 7);
  assert.equal(r.colorblind.verified, true);
  assert.ok(r.tags.includes("colorblind-safe"));
  assert.match(r.report, /verified — earns the badge/);
});

test("colorblind claim that fails -> NON-blocking, explained, badge stripped", () => {
  const r = processSubmission(makeBody({ json: themeJson("green-airglow"), cb: true }), 8);
  assert.equal(r.ok, true); // does not block
  assert.equal(r.colorblind.verified, false);
  assert.ok(!r.tags.includes("colorblind-safe"));
  assert.match(r.report, /doesn't pass/);
  assert.match(r.report, /reopen if you want to earn it/);
});

test("no claim but passes -> bonus note", () => {
  const r = processSubmission(makeBody({ json: themeJson("colorblind-safe"), cb: false }), 9);
  assert.equal(r.colorblind.verified, true);
  assert.match(r.report, /bonus/);
});

test("colorblind breakdown exposes minDeltaE + weakest (with bucket + medical type) + bestBucket", () => {
  const r = processSubmission(makeBody({ json: themeJson("jewel-spiral") }), 1);
  assert.equal(r.colorblind.minDeltaE, 19.6);
  assert.deepEqual(r.colorblind.weakest.pair, ["warning", "error"]);
  assert.equal(r.colorblind.weakest.cvd, "deuteranopia"); // precise medical type
  assert.equal(r.colorblind.weakest.bucket, "red-green"); // layman bucket
  assert.equal(r.colorblind.bestBucket, "blue-yellow"); // most robust for blue-yellow
});

test("colorblind-safe theme carries its best-for bucket tag (filterable)", () => {
  const r = processSubmission(makeBody({ json: themeJson("jewel-spiral") }), 1);
  assert.ok(r.tags.includes("colorblind-safe"));
  assert.ok(r.tags.includes("blue-yellow")); // strongest for blue-yellow vision
  // a non-safe theme gets neither
  const fail = processSubmission(makeBody({ json: themeJson("green-airglow") }), 2);
  assert.ok(!fail.tags.includes("colorblind-safe"));
  assert.ok(!["red-green", "blue-yellow"].some((t) => fail.tags.includes(t)));
});

test("author_url policy: dangerous schemes + shorteners dropped (with warning); direct http(s) kept", () => {
  const reject = [
    "javascript:alert(1)", "data:text/html,x", "vbscript:msgbox(1)",
    "file:///etc/passwd", "blob:https://x/y", "about:blank", "ftp://x.example",
    "https://bit.ly/abc", "http://tinyurl.com/xyz", "https://t.co/abc", "not a url",
  ];
  for (const u of reject) {
    const r = processSubmission(makeBody({ json: themeJson("jewel-spiral"), author: "X", authorUrl: u }), 1);
    assert.equal(r.envelope.theme.author_url, undefined, `should drop ${u}`);
    assert.match(r.report, /Author URL must be a direct http\(s\)/, `should warn for ${u}`);
  }
  const good = processSubmission(makeBody({ json: themeJson("jewel-spiral"), author: "X", authorUrl: "https://github.com/me" }), 2);
  assert.equal(good.envelope.theme.author_url, "https://github.com/me");
  assert.doesNotMatch(good.report, /Author URL must be/);
});

test("isAcceptableAuthorUrl", () => {
  for (const ok of ["https://github.com/x", "http://example.org/y", "https://bit.ly.example.com/z"]) {
    assert.ok(isAcceptableAuthorUrl(ok), `accept ${ok}`);
  }
  for (const no of ["javascript:1", "data:x", "file:///x", "blob:x", "about:blank", "https://bit.ly/x", "x", ""]) {
    assert.ok(!isAcceptableAuthorUrl(no), `reject ${no}`);
  }
});

test("invalid JSON rejected", () => {
  const r = processSubmission(makeBody({ json: "{ not valid" }), 1);
  assert.equal(r.ok, false);
  assert.equal(r.reason, "bad_json");
});

test("not a theme export rejected", () => {
  const r = processSubmission(makeBody({ json: JSON.stringify({ ok: true, theme: { name: "x" } }) }), 1);
  assert.equal(r.ok, false);
  assert.equal(r.reason, "not_theme");
});

test("missing export rejected", () => {
  const r = processSubmission("nothing here", 1);
  assert.equal(r.ok, false);
  assert.equal(r.reason, "no_export");
});

test("parseVibeTags: lowercase, dedupe, strip system words, cap length", () => {
  assert.deepEqual(parseVibeTags("aurora, Aurora, dark, COSMIC, core"), ["aurora", "cosmic"]);
  assert.deepEqual(parseVibeTags("a".repeat(40)), []); // over 32 chars -> dropped
});

test("slugify", () => {
  assert.equal(slugify("Jewel Spiral!"), "jewel-spiral");
  assert.equal(slugify(""), "theme");
});

/* =========================================================
   NAME CLASH  ·  [PS-CLASH-1..5]
   ========================================================= */

// A minimal but REAL export envelope, so these exercise the same path a stranger's
// submission takes rather than a shape invented for the test.
const namedTheme = (name) => JSON.stringify({
  ok: true, version: 1,
  theme: { id: "theme_probe", name, tokens: {}, colors: { "--evcc-accent": "#c54a07" }, alpha: {} },
}, null, 2);

test("[PS-CLASH-1] a clashing name is SUFFIXED, not rejected, and the suffix LOOPS", () => {
  // Three taken variants PLUS two decoys, deliberately. The count of existing themes
  // must not equal the right answer: resolveThemeName has a runaway fallback of
  // `${base} (${existing.length + 1})`, and with a tidy fixture that fallback returns
  // the SAME string the loop would. This test passed against a single-shot suffix
  // until the decoys were added — it was agreeing with the bug, not catching it.
  const existing = [
    { stem: "nord-10", name: "Nord" },
    { stem: "nord-11", name: "Nord (2)" },
    { stem: "nord-12", name: "Nord (3)" },
    { stem: "signal-7", name: "Signal" },
    { stem: "voltage-8", name: "Voltage" },
  ];
  const r = processSubmission(makeBody({ json: namedTheme("Nord") }), 20, { existingThemes: existing });

  assert.equal(r.ok, true, "a name clash must never reject a submission");
  assert.equal(r.themeName, "Nord (4)", "the suffix must LOOP past every taken variant, not stop at the first");
  assert.equal(r.envelope.theme.name, "Nord (4)", "the published JSON must carry the resolved name");
  assert.equal(r.renamed, true);
  assert.equal(r.collidedWith, "Nord");
  assert.match(r.report, /already has a theme called \*\*Nord\*\*/, "the submitter must be told what happened");
  // The slug still comes from the SUBMITTED name, so a re-run recognises itself.
  assert.equal(r.slug, "nord-20");
});

test("[PS-CLASH-2] the comparison is case- and whitespace-insensitive", () => {
  assert.equal(themeNameKey("Black  One"), themeNameKey("black one"));
  assert.equal(themeNameKey("  Nord "), "nord");
  // Not slugified: a reader sees these as different titles, so they are.
  assert.notEqual(themeNameKey("Black-One"), themeNameKey("Black One"));

  const existing = [{ stem: "black-one-58", name: "Black One" }];
  const r = resolveThemeName("black   one", existing);
  assert.equal(r.renamed, true, "lowercase slips past a raw === compare — the card's importer does exactly that");
  assert.equal(r.name, "black   one (2)");
});

test("[PS-CLASH-3] a re-run on the SAME issue is a replace, not a clash", () => {
  // The bot re-runs on every issue edit and pushes to the same branch. Its own
  // previously-written file must not be read as somebody else holding the name.
  const existing = [{ stem: "nord-12", name: "Nord" }];
  const r = processSubmission(makeBody({ json: namedTheme("Nord") }), 12, { existingThemes: existing });
  assert.equal(r.renamed, false, "editing your own issue must not rename your theme each time");
  assert.equal(r.themeName, "Nord");

  // ...but the same name from a DIFFERENT issue is a genuine clash.
  const other = processSubmission(makeBody({ json: namedTheme("Nord") }), 13, { existingThemes: existing });
  assert.equal(other.renamed, true);
  assert.equal(other.themeName, "Nord (2)");
});

test("[PS-CLASH-4] the DEFAULT reads the real gallery — no opts needed", () => {
  // THE WIRING, not the algorithm. A guard that only fires when a caller remembers
  // to pass a list is one flag-flip from being silently off, and the workflow calls
  // processSubmission with two arguments. Change `?? existingGalleryThemes()` to
  // `?? []` and this is the only test that notices.
  const published = existingGalleryThemes();
  assert.ok(published.length > 0, "the gallery scan returned nothing — the default cannot be guarding anything");

  const taken = published.find((t) => t.name);
  const r = processSubmission(makeBody({ json: namedTheme(taken.name) }), 9999);
  assert.equal(r.renamed, true, `submitting the published name "${taken.name}" with no opts must still be caught`);
  assert.equal(r.themeName, `${taken.name} (2)`);
});

test("[PS-CLASH-5] no two PUBLISHED themes share a name", () => {
  // The invariant itself, over the real corpus — the gate that would have caught
  // two "Black One" cards before they reached the site. It holds however a
  // duplicate arrives: the intake bot, a hand-added file, or two submissions that
  // each validated clean and then merged one after the other.
  const byKey = new Map();
  for (const t of existingGalleryThemes()) {
    if (!t.name) continue;
    const k = themeNameKey(t.name);
    if (!byKey.has(k)) byKey.set(k, []);
    byKey.get(k).push(`${t.stem}.json ("${t.name}")`);
  }
  const dupes = [...byKey.values()].filter((v) => v.length > 1);
  assert.deepEqual(
    dupes, [],
    "two gallery themes share a display name. The site cards by FILENAME and dedupes " +
    "nothing, so these would publish as visually identical entries: " +
    dupes.map((v) => v.join("  ==  ")).join(" | "),
  );
});
