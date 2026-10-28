// Run: node --test src/theme-tokens/registry-display-names.test.mjs
//
// FTL / ANM — the two FRONTEND REGISTRIES whose names reached the user untranslated.
//
// Everything else in the census arrives from the backend. These two do not: the floor
// textures and the animal companions are declared in the card's own code and served
// assets, so no `*_label` field was ever involved and the surfaces simply printed the
// registry id. The theme editor's floor select showed "carpet-high"; the theme preview's
// animal column heading showed "cat" while the map view's picker beside it showed "Cat".
//
// The two completeness gates are the point of this file, because both display functions
// fall back rather than fail: a registry entry with no key renders a prettified id, which
// looks deliberate. A gate is the only thing that can tell "English by design" from
// "nobody added the key".
//
// Coverage:
//   [FTL-1] every floor type in the REGISTRY has a vocab.floor_type key in en.js
//   [FTL-2] the preview's curated ORDER covers the registry — a hand-written list cannot
//           be complete by construction, so completeness is gated instead
//   [FTL-3] both spellings of a floor name resolve to the same key
//   [FTL-4] an unkeyed floor type prettifies rather than echoing a dotted key
//   [ANM-1] the six SPECIES have keys; Mittens deliberately does not
//   [ANM-2] a memorial pet keeps its registry label — it is a name, not a word
//   [ANM-3] the registry label wins over a prettified id, and over nothing at all
//   [ANM-4] both renderers resolve one animal to ONE name (they used to disagree)

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { floorTypeNames, floorTypeLabelKey, floorTypeDisplayName } from "./floor-scope.js";
import { animalDisplayName } from "./animals.js";
import { registerLocale, translate } from "../i18n/index.js";
import { flattenLocale } from "../i18n/flatten.js";
import { en as enCatalog } from "../i18n/en.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const LOCALES = join(REPO, "custom_components", "eufy_vacuum", "frontend", "locales");
const ANIMALS = join(LOCALES, "..", "animal-svg", "animals");

function loadPack(code) {
  const nested = JSON.parse(readFileSync(join(LOCALES, `${code}.json`), "utf8"));
  const { flat } = flattenLocale(nested, enCatalog);
  registerLocale(code, flat, { status: "draft" });
  return flat;
}
const DE = loadPack("de");

/** The real vocab resolver, bound to a language — what both renderers hand in. */
const tVocabFor = (lang) => (field, value, fallback) => {
  const slug = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  const key = `vocab.${field}.${slug}`;
  const out = translate(lang, key, undefined, { raw: true });
  return out === key ? (fallback ?? String(value)) : out;
};

/* ------------------------------------------------------------------- floor textures */

test("[FTL-1] every floor type in the registry has a vocab.floor_type key", () => {
  // The gate the fallback makes necessary. floorTypeDisplayName prettifies an unkeyed
  // name, so a texture added to FLOOR_TEXTURE_REGISTRY without a key renders "Terrazzo"
  // in all 17 languages and looks exactly like a finished one.
  const missing = floorTypeNames().filter((name) => !(floorTypeLabelKey(name) in enCatalog));
  assert.deepEqual(missing, [], `floor types with no vocab key: ${missing.join(", ")}`);
  // Not vacuous: there are types to check, and the key really is derived from the name.
  assert.ok(floorTypeNames().length >= 7);
  assert.equal(floorTypeLabelKey("granite-light"), "vocab.floor_type.granite_light");
});

test("[FTL-2] the preview's curated order covers the registry", () => {
  // FLOOR_PREVIEW_ORDER is hand-written on purpose — the sequence is roughly hard to soft
  // and that is a look decision, not the registry's alphabetical sort. A hand-written list
  // cannot be complete by construction, so read it back out of the source and gate it.
  const src = readFileSync(join(HERE, "..", "renderers", "theme-preview.js"), "utf8");
  const block = src.match(/FLOOR_PREVIEW_ORDER\s*=\s*\[([^\]]*)\]/);
  assert.ok(block, "FLOOR_PREVIEW_ORDER not found — did it move or get renamed?");
  const listed = [...block[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]).sort();
  const registry = floorTypeNames().map((n) => n.replace(/-/g, "_")).sort();
  assert.deepEqual(listed, registry,
    "the preview grid and the registry disagree — a new floor type would be invisible there");
});

test("[FTL-3] both spellings of a floor name resolve to one key", () => {
  // The token namespace says `carpet-low`; a room's stored `floor_type` says `carpet_low`.
  // tVocab's slug rule folds both, which is what lets one key serve both surfaces.
  for (const [hyphen, underscore] of [["carpet-low", "carpet_low"], ["granite-light", "granite_light"]]) {
    assert.equal(floorTypeLabelKey(hyphen), floorTypeLabelKey(underscore));
    assert.equal(
      floorTypeDisplayName(hyphen, tVocabFor("de")),
      floorTypeDisplayName(underscore, tVocabFor("de")),
    );
  }
  assert.equal(floorTypeDisplayName("granite-light", tVocabFor("de")), DE["vocab.floor_type.granite_light"]);
  assert.notEqual(floorTypeDisplayName("carpet-high", tVocabFor("de")), "carpet-high");
});

test("[FTL-4] an unkeyed floor type prettifies rather than echoing a dotted key", () => {
  // The forward-compat leg. A dotted key on screen is worse than an English word.
  assert.equal(floorTypeDisplayName("terrazzo-dark", tVocabFor("de")), "Terrazzo Dark");
  assert.equal(floorTypeDisplayName("", tVocabFor("de")), "");
  assert.equal(floorTypeDisplayName(null, tVocabFor("de")), "");
  // With no translator at all it still answers — the preview renders before locales load.
  assert.equal(floorTypeDisplayName("carpet_high"), "Carpet High");
});

test("[FTL-5] every floor-name surface resolves through the helper", () => {
  // The call-site gate, and it was MISSING: ablating the theme editor's select back to
  // `<option value="${name}">${name}</option>` left [FTL-1..4] all green, because they test
  // the helper and the helper was still right. A correct helper with a wrong caller passes
  // every test about the helper — the same shape as sliderRow's translator slot.
  const sites = [
    ["renderers/theme.js", join(HERE, "..", "renderers", "theme.js")],
    ["renderers/theme-preview.js", join(HERE, "..", "renderers", "theme-preview.js")],
  ];
  for (const [name, path] of sites) {
    const src = readFileSync(path, "utf8");
    assert.ok(src.includes("floorTypeDisplayName("), `${name}: must resolve names through the helper`);
  }
  // And specifically: the select's option TEXT must not be the raw name again. That exact
  // expression is what shipped, and it is what the ablation restores.
  const themeSrc = readFileSync(join(HERE, "..", "renderers", "theme.js"), "utf8");
  assert.ok(
    !themeSrc.includes('<option value="${name}">${name}</option>'),
    "renderers/theme.js: the floor select is printing the raw registry name again",
  );
  assert.ok(
    /floorTypeNames\(\)[\s\S]{0,300}?floorTypeDisplayName\(/.test(themeSrc),
    "renderers/theme.js: the floor select must map its names through floorTypeDisplayName",
  );
});

/* ------------------------------------------------------------------------- animals */

/**
 * The shipped roster, read from the animals/ DIRECTORY.
 *
 * ⚠ NOT `animals/index.json`. That file is a RUNTIME ARTIFACT — `manifest.js` says the
 * integration "generates animals/index.json at startup from whatever .js files exist", and
 * `.gitignore:58` ignores it. So it exists on a box that has booted Home Assistant and
 * nowhere else: a first version of this read it, passed here, and failed CI with ENOENT.
 *
 * `harness/tests/gallery-completeness.spec.mjs` had already hit this and written the reason
 * down. Reading that note first would have saved the red build — which is what
 * "scan the docs before scoping" is for.
 *
 * The directory is not a workaround for the missing file, it is the better read: the
 * generator at `__init__.py:201-203` is `sorted(f for f in os.listdir(animals_dir) if
 * f.endswith(".js"))`, so this applies the same rule to the same directory and agrees with
 * it by construction — including on a species added since the last HA restart, which a
 * stale index.json would miss. And it is tracked, so CI can see it.
 */
function registryAnimals() {
  return readdirSync(ANIMALS)
    .filter((f) => f.endsWith(".js"))
    .map((f) => f.replace(/\.js$/, ""))
    .sort();
}
/**
 * One animal's declared label, read from the SERVED roster file.
 *
 * Not JSON.parse: these are JS modules that call `AnimalSVG.register(...)`, the generated
 * ones wrapping a JSON-ish block and `snake.js` being hand-written procedural code with no
 * label at all. And not the `src/*.json` descriptors either — only five of the seven have
 * one, and none of those carries a `label`. The served file IS the roster the browser
 * reads, so it is the thing to read.
 */
function registryLabel(id) {
  const src = readFileSync(join(ANIMALS, `${id}.js`), "utf8");
  const m = src.match(/"label":\s*"([^"]*)"/);
  return m ? m[1] : null;
}

test("[ANM-1] the six species have keys; Mittens deliberately does not", () => {
  const ids = registryAnimals();
  assert.ok(ids.length >= 7, `roster looks wrong: ${ids.join(", ")}`);
  const keyed = ids.filter((a) => `vocab.animal.${a}` in enCatalog);
  const unkeyed = ids.filter((a) => !(`vocab.animal.${a}` in enCatalog));
  assert.deepEqual(unkeyed, ["mittens"],
    "only the memorial pet may be unkeyed; a species with no key reads English everywhere");
  assert.deepEqual(keyed.sort(), ["cat", "dog", "fox", "parrot", "raccoon", "snake"]);
});

test("[ANM-2] a memorial pet keeps its registry label in every language", () => {
  // She is a proper noun, which is the whole reason the 🌈 Rainbow Bridge group exists.
  // Same exemption font.opendyslexic holds: a name is not a word.
  const label = registryLabel("mittens");
  assert.equal(label, "Mittens", "the registry label is what carries her name");
  for (const lang of ["de", "ja", "ar"]) {
    loadPack(lang);
    assert.equal(animalDisplayName("mittens", label, tVocabFor(lang)), "Mittens");
  }
});

test("[ANM-3] the registry label wins over a prettified id, and over nothing", () => {
  // A user-dropped animal rides this leg, which is why the label must stay reachable.
  assert.equal(animalDisplayName("sea_otter", "Sea Otter", tVocabFor("de")), "Sea Otter");
  // No label on record: the id is prettified rather than printed bare.
  assert.equal(animalDisplayName("sea_otter", null, tVocabFor("de")), "Sea Otter");
  // `snake` declares no label in its own registry entry, so the key is its only name.
  assert.equal(registryLabel("snake"), null);
  assert.equal(animalDisplayName("snake", null, tVocabFor("de")), DE["vocab.animal.snake"]);
  assert.equal(animalDisplayName("", null, tVocabFor("de")), "");
});

test("[ANM-4] neither renderer keeps its own copy of the name logic", () => {
  // They used to disagree — the map picker read the registry label and prettified a missing
  // one, the theme preview printed the bare lowercase id — and the only thing that keeps
  // them agreeing is that there is one function. So this asserts THAT, not that the
  // function equals itself: an earlier draft called animalDisplayName twice and compared
  // the results, which is true of any function and proves nothing.
  const sites = [
    ["renderers/map.js", join(HERE, "..", "renderers", "map.js")],
    ["renderers/theme-preview.js", join(HERE, "..", "renderers", "theme-preview.js")],
  ];
  for (const [name, path] of sites) {
    const src = readFileSync(path, "utf8");
    assert.ok(src.includes("animalDisplayName("), `${name}: must resolve names through the helper`);
    // The shape of the old local copy: uppercase the first character of the id and spread
    // underscores. If it comes back, the two surfaces can drift again.
    assert.ok(
      !/charAt\(0\)\.toUpperCase\(\)/.test(src.replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, "")),
      `${name}: a local prettifier is back — that is how the two drifted apart`,
    );
  }
  // And the roster really does exercise both legs, or the assertions above are about nothing.
  const ids = registryAnimals();
  assert.ok(ids.some((a) => registryLabel(a)), "some animal must declare a label");
  assert.ok(ids.some((a) => !registryLabel(a)), "and some must not, or the fallback is untested");
});

test("[ANM-5] a registry label cannot break out of the map picker's option", () => {
  // The map picker interpolated the registry label into innerHTML RAW. Animals are
  // user-droppable, so that label is untrusted; routing it through tVocab closed it,
  // because vocab() escapes the FALLBACK arm as well as a catalog hit. This pins the
  // property rather than the route, so an equivalent fix elsewhere still passes.
  const escaping = (field, value, fallback) => {
    const out = tVocabFor("de")(field, value, fallback);
    return out === fallback
      ? String(fallback).replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
      : out;
  };
  const hostile = '"><script>x</script>';
  const out = animalDisplayName("sea_otter", hostile, escaping);
  assert.ok(!out.includes("<script"), "a dropped label must not reach innerHTML as markup");
  assert.ok(!out.includes('">'), "and must not close the attribute it sits in");
});
