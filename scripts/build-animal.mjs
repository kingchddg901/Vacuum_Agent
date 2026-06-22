/**
 * ============================================================
 * BUILD ANIMAL  (descriptor → gallery artifacts)
 * ============================================================
 *
 * The shared "compile a descriptor into what ships" step, used by BOTH intake
 * paths (the issue-form processor and the fork-PR check) and for authoring the
 * bundled/example animals. One descriptor in, two artifacts out:
 *
 *   gallery/animals/<id>.json   — the sanitised, source-stamped envelope
 *   …/animal-svg/animals/<id>.js — the generated module (codegen, never hand-edited)
 *
 * Pipeline: validateDescriptor (contract gate) → sanitiseParts (DOMPurify in
 * real Chromium) → codegenAnimalModule. Refuses to emit anything if validation
 * fails. The sanitised parts (not the raw input) are what get written + codegen'd.
 *
 * Usage: node scripts/build-animal.mjs <descriptor.json> [--no-write]
 *   (needs a Playwright browser for the sanitiser — run in the pinned image.)
 * ============================================================
 */
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { validateDescriptor, buildEnvelope, codegenAnimalModule } from "./animal-descriptor.mjs";
import { sanitizeParts, summariseRemovals } from "./sanitize-animal-svg.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
export const ANIMALS_DIR = resolve(REPO, "custom_components/eufy_vacuum/frontend/animal-svg/animals");
export const GALLERY_DIR = resolve(REPO, "gallery/animals");

/** Ids already present (bundled animals from index.json + any gallery descriptor). */
export function existingAnimalIds() {
  const ids = new Set();
  try {
    for (const f of JSON.parse(readFileSync(resolve(ANIMALS_DIR, "index.json"), "utf8"))) {
      ids.add(String(f).replace(/\.js$/, ""));
    }
  } catch {}
  try {
    for (const f of readdirSync(GALLERY_DIR)) {
      if (f.endsWith(".json")) ids.add(f.replace(/\.json$/, ""));
    }
  } catch {}
  return [...ids];
}

/**
 * Compile a descriptor (the `animal` object, or an envelope wrapping one) into
 * the sanitised envelope + generated module. Pure of disk writes.
 */
export async function buildAnimal(descriptorInput, { existingIds } = {}) {
  const animalIn = descriptorInput && descriptorInput.animal ? descriptorInput.animal : descriptorInput;
  const v = validateDescriptor(animalIn, { existingIds: existingIds ?? [] });
  if (!v.ok) return { ok: false, errors: v.errors };

  const san = await sanitizeParts(v.animal.parts);
  const animal = { ...v.animal, parts: san.parts };
  return {
    ok: true,
    animal,
    envelope: buildEnvelope(animal),
    moduleJs: codegenAnimalModule(animal),
    removed: san.removed,
    meta: v.meta,
  };
}

// --- CLI ---------------------------------------------------------------------
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const file = process.argv[2];
  const write = !process.argv.includes("--no-write");
  if (!file) {
    console.error("usage: node scripts/build-animal.mjs <descriptor.json> [--no-write]");
    process.exit(2);
  }
  const input = JSON.parse(readFileSync(file, "utf8"));
  // Rebuilding the SAME animal is always fine — only a collision with a
  // DIFFERENT existing id should block. So drop this descriptor's own id.
  const ownId = (input && input.animal ? input.animal.id : input && input.id) || "";
  const r = await buildAnimal(input, { existingIds: existingAnimalIds().filter((x) => x !== ownId) });
  if (!r.ok) {
    console.error("INVALID descriptor:\n" + r.errors.map((e) => "  - " + e).join("\n"));
    process.exit(1);
  }
  if (write) {
    mkdirSync(GALLERY_DIR, { recursive: true });
    writeFileSync(resolve(GALLERY_DIR, `${r.animal.id}.json`), JSON.stringify(r.envelope, null, 2) + "\n");
    writeFileSync(resolve(ANIMALS_DIR, `${r.animal.id}.js`), r.moduleJs);
  }
  console.log(`Built "${r.animal.id}" (${r.animal.name})${write ? "" : " [dry-run]"}`);
  const summary = summariseRemovals(r.removed);
  console.log(summary ? "Sanitiser removed:\n" + summary : "Sanitiser removed nothing.");
}
