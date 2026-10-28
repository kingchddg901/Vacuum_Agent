// Run: node --test src/cards/shared-slider.test.mjs
//
// SLD — the Dreame wetness slider's BAND WORD, on the two standalone cards.
//
// The adapter ships the band as three ENGLISH labels (`water_level_range.labels` =
// "Slightly Dry" / "Moist" / "Wet"), and `sliderRow` printed them with no lookup — so the
// word read English in all 17 translated languages while the "Water level" caption right
// above it was translated.
//
// It is FOUR sinks, not one, and that is the whole reason this file exists: the initial
// word (`sliderWord`) plus the three `data-word-low/mid/high` attributes, which the slider
// bindings copy into the chip on every input event. Fixing the rendered word alone would
// have looked correct until the first drag and then flipped back to English. Localizing
// once, where `lbls` is built, is what covers both.
//
// The forwarders that READ those attrs (bindings/index.js, dashboard-card.js::syncWord,
// room-card.js::syncWord) are deliberately untouched — they are correct the moment their
// carrier is, which [SLD-2] is what pins.
//
// Coverage:
//   [SLD-1] the rendered word is the locale's, from the REAL shipped pack
//   [SLD-2] all three data-word-* attrs carry the same localized words (the drag path)
//   [SLD-3] a word with no catalog key keeps the adapter's own — a custom-declared range
//   [SLD-4] idPrefix still reaches data-scope (the argument-order bite)
//   [SLD-5] ablation — with no translator the output is the old English, so [SLD-1] can fail
//   [SLD-6] both real call sites actually PASS a translator (a correct helper, zero callers)

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { sliderRow, vocab } from "./_shared.js";
import { registerLocale, translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as enCatalog } from "../i18n/en.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const LOCALES = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales");

function loadPack(code) {
  const nested = JSON.parse(readFileSync(join(LOCALES, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(nested, enCatalog);
  registerLocale(code, flat, { status: "draft" });
  return flat;
}
const DE = loadPack("de");

/** Exactly what the cards pass: the shared vocab() bound to a resolved language. */
const tVocabFor = (lang) => (field, value, fallback) =>
  vocab((k, v) => translate(lang, k, v), field, value, fallback, "dreame");

/** The real Dreame declaration — adapters/dreame/vocabulary.py WATER_LEVEL_RANGE. */
const RANGE = {
  min: 1,
  max: 32,
  step: 1,
  labels: { min_label: "Slightly Dry", mid_label: "Moist", max_label: "Wet" },
};

/** The word inside the <span data-slider-word> chip. */
function renderedWord(html) {
  const m = html.match(/data-slider-word>([^<]*)</);
  return m ? m[1] : null;
}
function attr(html, name) {
  const m = html.match(new RegExp(`${name}="([^"]*)"`));
  return m ? m[1] : null;
}

test("[SLD-1] the rendered band word is the locale's, not the adapter's English", () => {
  // The three German words come from the pack itself, read here rather than restated, so
  // this assertion follows a retranslation instead of pinning one spelling.
  for (const [value, key] of [[1, "vocab.water_level.slightly_dry"],
                              [16, "vocab.water_level.moist"],
                              [32, "vocab.water_level.wet"]]) {
    const html = sliderRow("Wasserstand", "water_level", RANGE, value, tVocabFor("de"));
    assert.equal(renderedWord(html), DE[key], `value ${value} -> ${key}`);
  }
  // And the English the adapter sent is nowhere in the output.
  const html = sliderRow("Wasserstand", "water_level", RANGE, 16, tVocabFor("de"));
  for (const english of ["Slightly Dry", "Moist", "Wet"]) {
    assert.ok(!html.includes(english), `"${english}" must not survive into a de render`);
  }
});

test("[SLD-2] the three data-word-* attrs carry the localized words too", () => {
  // THE DRAG PATH. These attributes are the only thing the input handlers have; a fix that
  // localized the chip but not the carrier would be invisible until the user moved the
  // thumb, which is the normal way to use a slider.
  const html = sliderRow("Wasserstand", "water_level", RANGE, 16, tVocabFor("de"));
  assert.equal(attr(html, "data-word-low"), DE["vocab.water_level.slightly_dry"]);
  assert.equal(attr(html, "data-word-mid"), DE["vocab.water_level.moist"]);
  assert.equal(attr(html, "data-word-high"), DE["vocab.water_level.wet"]);
});

test("[SLD-3] an unkeyed word keeps the adapter's own — a custom-declared range", () => {
  // config_schema.py lets a stored adapter config declare ANY three words. Those are the
  // author's, and no catalog entry will ever exist for them, so the fallback must hold.
  const custom = { ...RANGE, labels: { min_label: "Barely damp", mid_label: "Damp", max_label: "Soaked" } };
  const html = sliderRow("Wasserstand", "water_level", custom, 1, tVocabFor("de"));
  assert.equal(renderedWord(html), "Barely damp");
  assert.equal(attr(html, "data-word-high"), "Soaked");
});

test("[SLD-4] idPrefix still reaches data-scope", () => {
  // The argument-order bite. `tVocabFn` was inserted BEFORE `idPrefix` to mirror chipRow,
  // so a caller that was not updated passes its room id into the translator slot. That is
  // silent in the word (a non-function falls back to esc) and visible only here: the scope
  // attribute disappears and every slider on a multi-room card commits to the wrong room.
  const html = sliderRow("Wasserstand", "water_level", RANGE, 16, tVocabFor("de"), "room-7");
  assert.equal(attr(html, "data-scope"), "room-7");
});

test("[SLD-5] ablation — with no translator the output is the pre-fix English", () => {
  // Proves the assertions above can distinguish fixed from broken. Remove the translator
  // and sliderRow reproduces exactly what shipped before: the adapter's English, escaped.
  const html = sliderRow("Water level", "water_level", RANGE, 1);
  assert.equal(renderedWord(html), "Slightly Dry");
  assert.equal(attr(html, "data-word-mid"), "Moist");
  assert.notEqual(renderedWord(html), DE["vocab.water_level.slightly_dry"]);
});

test("[SLD-6] both real call sites pass a translator", () => {
  // A correct helper with no caller passes every test about the helper. These are the only
  // two callers of sliderRow in the tree; a third must appear here or it ships English.
  const sites = [
    ["cards/dashboard-card.js", join(HERE, "dashboard-card.js")],
    ["room-card.js", join(HERE, "..", "room-card.js")],
  ];
  for (const [name, path] of sites) {
    const src = readFileSync(path, "utf8");
    const calls = src.split("\n").filter((l) => l.includes("sliderRow("));
    assert.equal(calls.length, 1, `${name}: expected exactly one sliderRow call`);
    assert.ok(
      /tVocab|,\s*tv\s*,/.test(calls[0]),
      `${name}: sliderRow must be handed a tVocab translator — got: ${calls[0].trim()}`,
    );
  }
});
