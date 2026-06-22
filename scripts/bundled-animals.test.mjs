/**
 * The bundled core animals, expressed as descriptors (the new form), used as
 * system tests: each src/<id>.json must validate (first-party — reserved ids
 * allowed) AND the committed animals/<id>.js must be its faithful codegen.
 *
 * This dogfoods the whole contract on real, detailed animals, and keeps the
 * generated modules in sync with their descriptor source — edit a src/*.json,
 * regenerate with `build-animal.mjs --first-party`, and this test guards it.
 *
 * Pure (no browser). Run: node --test scripts/bundled-animals.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { validateDescriptor, codegenAnimalModule } from "./animal-descriptor.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const FW = resolve(HERE, "../custom_components/eufy_vacuum/frontend/animal-svg");
const SRC = resolve(FW, "src");
const ANIMALS = resolve(FW, "animals");

const ids = readdirSync(SRC)
  .filter((f) => f.endsWith(".json"))
  .map((f) => f.replace(/\.json$/, ""));

test("[BND-0] bundled descriptor sources exist", () => {
  assert.ok(ids.length >= 4, `expected the converted core animals, found: ${ids.join(", ") || "none"}`);
});

for (const id of ids) {
  test(`[BND] ${id}: validates (first-party) + animals/${id}.js is its faithful codegen`, () => {
    const env = JSON.parse(readFileSync(resolve(SRC, `${id}.json`), "utf8"));
    const input = env.animal || env;
    const v = validateDescriptor(input, { allowReservedIds: true, source: "core" });
    assert.equal(v.ok, true, JSON.stringify(v.errors));
    assert.equal(v.animal.id, id);
    assert.equal(v.animal.source, "core");

    // Compare by content, not line endings: codegen emits LF, but a Windows
    // checkout (no .gitattributes) may hold the committed .js as CRLF.
    const norm = (s) => s.replace(/\r/g, "").trim();
    const committed = readFileSync(resolve(ANIMALS, `${id}.js`), "utf8");
    assert.equal(
      norm(committed),
      norm(codegenAnimalModule(v.animal)),
      `animals/${id}.js is out of sync with src/${id}.json — regenerate: node scripts/build-animal.mjs custom_components/eufy_vacuum/frontend/animal-svg/src/${id}.json --first-party`,
    );
  });
}
