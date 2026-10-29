/**
 * The two SERVED indexes must ship, and must match the directories they index.
 *
 * `custom_components/eufy_vacuum/__init__.py`'s `_prepare_static_dirs` writes an
 * index.json beside the animal modules and another beside the shipped locale packs,
 * at every Home Assistant startup, from whatever files are in each directory. The
 * card fetches both at runtime to discover what to load.
 *
 * WHY THIS FILE EXISTS. `animals/index.json` was gitignored and `locales/index.json`
 * was not, although the same function writes both on the same startup with the same
 * rule. hacs.json sets `zip_release`, so HACS installs the release ASSET — a zip of
 * the tag — and replaces the integration folder with it. An ignored file is not in
 * the tag, so after a card-only update the animals index was absent, the card's
 * fetch got a 404, and the map's mascot did not appear until the next HA restart.
 * The locale packs arrived immediately, from the tracked twin. Nothing was red.
 *
 *   [IDX-1] the animals index matches its directory, by the generator's own rule
 *   [IDX-2] the shipped-locales index matches its directory, same
 *   [IDX-3] NEITHER index is gitignored and both are tracked — the regression itself
 *   [IDX-4] manifest.js survives an index that is missing, or that names a file
 *           which is not served
 *
 * Pure (no browser). Run: node --test scripts/served-indexes.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const FRONTEND = join(REPO, "custom_components", "eufy_vacuum", "frontend");
const ANIMALS = join(FRONTEND, "animal-svg", "animals");
const LOCALES = join(FRONTEND, "locales");

const rel = (p) => p.slice(REPO.length + 1).split("\\").join("/");

/** The generator's rule for the animals index, __init__.py:
 *    sorted(f for f in os.listdir(animals_dir) if f.endswith(".js"))
 * Mirrored rather than imported, because it lives in a closure inside async_setup.
 * If that rule changes, change this one — and [IDX-3] is what keeps the FILE honest
 * meanwhile, since it compares the committed index against the real directory. */
const animalRule = () => readdirSync(ANIMALS).filter((f) => f.endsWith(".js")).sort();

/** And for the shipped-locales index, __init__.py:
 *    f.endswith(".json") and f != "index.json"
 * Note `en.reference.jsonc` is excluded by the extension test, not by a name test —
 * ".jsonc" does not end with ".json". */
const localeRule = () =>
  readdirSync(LOCALES).filter((f) => f.endsWith(".json") && f !== "index.json").sort();

const readIndex = (dir) => JSON.parse(readFileSync(join(dir, "index.json"), "utf8"));

test("[IDX-1] the animals index matches its directory", () => {
  const expected = animalRule();
  // Not vacuous: there are animals to index, and the rule really does select them.
  assert.ok(expected.length >= 6, `roster looks wrong: ${expected.join(", ")}`);
  assert.ok(expected.includes("cat.js"), "the rule stopped selecting .js modules");
  assert.deepEqual(readIndex(ANIMALS), expected,
    "animals/index.json is stale — it is committed, so regenerate it (start HA, or write " +
    "the sorted .js listing) and commit the result");
});

test("[IDX-2] the shipped-locales index matches its directory", () => {
  const expected = localeRule();
  assert.ok(expected.length >= 15, `pack list looks wrong: ${expected.length} entries`);
  assert.ok(!expected.includes("index.json"), "the index must not list itself");
  assert.ok(!expected.some((f) => f.endsWith(".jsonc")),
    "en.reference.jsonc is not a pack and must not be indexed");
  assert.deepEqual(readIndex(LOCALES), expected, "locales/index.json is stale");
});

test("[IDX-3] both indexes are tracked, and neither is gitignored", () => {
  const paths = [join(ANIMALS, "index.json"), join(LOCALES, "index.json")].map(rel);

  // `--no-index` IS LOAD-BEARING, and the ablation is what proved it. Plain
  // `git check-ignore` never reports a TRACKED file, so with the index committed this
  // assertion could not fire: putting the ignore line back left the suite green. That
  // made it a guard that reads as a guard and tests nothing — the exact shape it was
  // written to catch. `--no-index` evaluates the ignore rules on their own, so the
  // pattern coming back is caught while the file is still tracked, which is the only
  // useful moment: by the time anything causes a re-add, the file is already out of the
  // release zip and the mascot is already gone.
  //
  // check-ignore exits 1 when NOTHING matches, which is the state we want, so a non-zero
  // exit is the pass here and only a match is a failure.
  let ignored = [];
  try {
    ignored = execFileSync("git", ["-C", REPO, "check-ignore", "--no-index", ...paths],
      { encoding: "utf8" })
      .split("\n").map((s) => s.trim()).filter(Boolean);
  } catch (err) {
    if (err.status !== 1) throw err;          // 1 = no path ignored; anything else is real
  }
  assert.deepEqual(ignored, [],
    `these served indexes are gitignored, so they are NOT in the release zip and the card ` +
    `fetches a 404 until Home Assistant restarts: ${ignored.join(", ")}. ` +
    `That is the defect this gate exists for — see the note in .gitignore.`);

  const tracked = execFileSync("git", ["-C", REPO, "ls-files", "--", ...paths], { encoding: "utf8" })
    .split("\n").map((s) => s.trim()).filter(Boolean);
  assert.deepEqual(tracked.sort(), paths.slice().sort(),
    "both served indexes must be committed, or they cannot be in the zip HACS installs");
});

test("[IDX-4] manifest.js survives a missing index and an unserved animal", () => {
  const src = readFileSync(join(FRONTEND, "animal-svg", "manifest.js"), "utf8");
  const code = src.replace(/\/\*[\s\S]*?\*\/|^\s*\/\/.*$/gm, "");

  // The 404 was served as HTML, so the original `.then(r => r.json())` threw on the
  // body rather than on the status. Parse only an OK response.
  assert.match(code, /r\.ok\s*\?/,
    "manifest.js must check response.ok before parsing the index — a 404 body is not JSON");

  // The index is a startup snapshot, so it can name a file that is no longer served.
  // Promise.all turned that one rejection into zero animals.
  assert.match(code, /Promise\.allSettled\(/,
    "load the animals with allSettled — one unserved file must not take down the rest");
  assert.doesNotMatch(code, /await\s+Promise\.all\(/,
    "a bare Promise.all over the animal loads is the failure mode [IDX-4] exists to prevent");

  // And it must still say something when it gives up, rather than failing silently:
  // the original rejection was swallowed by the caller and left no trace at all.
  assert.match(code, /console\.warn\(/, "a roster that does not load must say so");
});
