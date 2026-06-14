/**
 * Unit tests for the theme submission processor. Run: node --test scripts/
 * Uses real gallery themes as fixtures (some pass colorblind, some don't).
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { processSubmission, parseVibeTags, slugify } from "./process-submission.mjs";

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
