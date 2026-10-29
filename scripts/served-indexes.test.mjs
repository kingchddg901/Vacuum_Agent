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

test("[IDX-3] neither served index is gitignored, and both are present", () => {
  const paths = [join(ANIMALS, "index.json"), join(LOCALES, "index.json")].map(rel);

  // NO `git` SUBPROCESS, and CI is what taught that. The first version shelled out to
  // `git check-ignore` / `git ls-files`; the node job runs in the pinned Playwright
  // container, where the checkout is owned by another user, so git refused outright:
  //   fatal: detected dubious ownership in repository at '/__w/Vacuum_Agent/Vacuum_Agent'
  // 127 of 128 passed and this was the one red. Making the guard depend on a usable git
  // made it depend on the environment, which a packaging guard must not.
  //
  // (It had already needed one correction: plain `git check-ignore` never reports a
  // TRACKED file, so with the index committed, putting the ignore line back left the
  // suite GREEN — a guard that read as a guard and tested nothing. `--no-index` fixed
  // that, and then CI rejected the subprocess entirely.)
  //
  // So read the ignore files directly. The defect WAS a line in .gitignore, so the line
  // is the thing to assert on. Walk the ancestor directories, because a nested
  // .gitignore ignores just as effectively as the root one.
  const offenders = [];
  let ignoreFilesRead = 0;
  for (const p of paths) {
    const parts = p.split("/");
    for (let i = 0; i < parts.length; i += 1) {
      const dir = parts.slice(0, i).join("/");
      const gi = join(REPO, dir, ".gitignore");
      let lines;
      try {
        lines = readFileSync(gi, "utf8").split("\n");
        ignoreFilesRead += 1;
      } catch {
        continue;                              // no .gitignore at this level
      }
      const tail = parts.slice(i).join("/");
      for (const raw of lines) {
        const line = raw.trim();
        if (!line || line.startsWith("#")) continue;
        const pat = line.replace(/^\/+/, "").replace(/\/+$/, "");
        // The realistic regressions: the exact path returns, a relative path from this
        // level returns, or someone ignores the basename everywhere.
        if (pat === p || pat === tail || pat === "index.json") {
          offenders.push(`${dir || "."}/.gitignore: ${line}   (would ignore ${p})`);
        }
      }
    }
  }
  assert.deepEqual(offenders, [],
    `a served index is gitignored again, so it will NOT be in the release zip and the card ` +
    `fetches a 404 until Home Assistant restarts:\n  ${offenders.join("\n  ")}\n` +
    `That is the defect this gate exists for — see the note in .gitignore.`);

  // Both must be on disk. In CI this is the committed-ness check and the strong form of
  // it: the runner checks out committed content only, and nothing in the node job
  // generates either file — so if these exist here, they are in the tag, which is what
  // the zip is built from. Locally it is weaker, because Home Assistant writes both at
  // startup; locally the assertion above is the one doing the work.
  for (const p of paths) {
    assert.ok(readFileSync(join(REPO, p), "utf8").length > 2,
      `${p} is missing or empty — in CI that means it is not committed, so it cannot be ` +
      `in the zip HACS installs`);
  }

  // Not vacuous: the walk really opened at least one ignore file (the root one). Without
  // this, a wrong REPO root or a typo in the paths would examine nothing and pass.
  assert.ok(ignoreFilesRead >= 2,
    `the walk read ${ignoreFilesRead} .gitignore file(s) — it should find the root one for ` +
    `each path, so it is not actually checking the ignore rules`);
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
