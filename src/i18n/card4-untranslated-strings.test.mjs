// Regression test — CARD-4 (carried CF-4), "the three untranslated strings".
// common.service_failed, learning.room_skipped, and learning.run_incomplete_toast
// are defined in the English base (src/i18n/en.js:35,371,338) but were never
// added to any of the 17 shipped locale packs under
// custom_components/eufy_vacuum/frontend/locales/*.json. check-i18n.mjs's own
// "C. shipped locale validation" section treats this as a silent, PASSING
// fallback (coverage.untranslated just grows -- "3 -> en" on every locale
// line, confirmed by running the script directly), not a build failure, so a
// non-English user sees English for these three strings with nothing in CI
// flagging it. This test asserts the gap directly against the shipped JSON,
// mirroring exactly what check-i18n.mjs's own flattenLocale(...).coverage
// call does.
//
// Run: node --test src/i18n/card4-untranslated-strings.test.mjs
//
// FLIP CONVENTION (mirrors core-service-failure.test.mjs / core-refusal-shape
// .test.mjs): CARD4-1 FAILS against the current locale packs (the three keys
// are untranslated in all 17) and is expected to PASS once the packet's
// translation pass lands (AI-draft tier, per feedback_guide_source_ai_default).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { flattenLocale } from "./flatten.js";
import { en as enCatalog } from "./en.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const LOCALES_DIR = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales");

const TARGET_KEYS = [
  "common.service_failed",
  "learning.room_skipped",
  "learning.run_incomplete_toast",
];

test("[CARD4-1] the three carried-CF-4 strings are translated in every shipped locale", () => {
  const files = readdirSync(LOCALES_DIR).filter((f) => f.endsWith(".json") && f !== "index.json");
  assert.ok(files.length > 0, "no shipped locale files found -- check LOCALES_DIR");

  const stillUntranslated = [];
  for (const f of files) {
    const nested = JSON.parse(readFileSync(join(LOCALES_DIR, f), "utf8"));
    const { coverage } = flattenLocale(nested, enCatalog);
    for (const key of TARGET_KEYS) {
      if (coverage.untranslated.includes(key)) stillUntranslated.push(`${f}:${key}`);
    }
  }

  assert.deepEqual(
    stillUntranslated,
    [],
    `${stillUntranslated.length} locale/key pairs still silently fall back to English ` +
      `(every non-English user sees English for these): ${stillUntranslated.slice(0, 6).join(", ")}` +
      (stillUntranslated.length > 6 ? ", ..." : "")
  );
});
