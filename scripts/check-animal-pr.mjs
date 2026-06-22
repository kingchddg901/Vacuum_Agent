/**
 * ============================================================
 * CHECK ANIMAL PR  (fork-PR intake gate)
 * ============================================================
 *
 * The second intake path: a contributor opens a PR that adds/edits a community
 * animal (gallery/animals/<id>.json + the generated animals/<id>.js). This gate
 * runs in CI (animal-pr-check.yml) and enforces the same boundary the issue
 * intake does, plus PR-specific guards.
 *
 * Checks (per changed file set):
 *   1. No framework edits — only gallery/animals/<id>.json and
 *      …/animal-svg/animals/<id>.js may change, never the framework.
 *   2. Each changed descriptor passes the contract gate (validateDescriptor).
 *   3. Its committed SVG is already fully sanitised — re-running DOMPurify must
 *      strip nothing (catches raw/unsanitised parts smuggled into a PR).
 *   4. The committed animals/<id>.js is the FAITHFUL codegen of the descriptor
 *      (no hand-written / tampered module) — compared without re-sanitising, so
 *      DOMPurify idempotency can't cause a false mismatch.
 *   5. No orphan module (a changed .js without its descriptor).
 *
 * checkAnimalPr(changedFiles) -> { ok, problems, galleryIds }. The CLI wrapper
 * reads CHANGED_FILES (newline-separated) and exits non-zero on any problem.
 * ============================================================
 */
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { validateDescriptor, codegenAnimalModule } from "./animal-descriptor.mjs";
import { sanitizeParts, summariseRemovals } from "./sanitize-animal-svg.mjs";
import { existingAnimalIds, ANIMALS_DIR } from "./build-animal.mjs";

const GALLERY_RE = /^gallery\/animals\/([a-z0-9-]+)\.json$/;
const ANIMAL_JS_RE = /^custom_components\/eufy_vacuum\/frontend\/animal-svg\/animals\/([a-z0-9-]+)\.js$/;
const ANIMAL_SVG_DIR = "custom_components/eufy_vacuum/frontend/animal-svg/";

/**
 * @param {string[]} changed  file paths the PR changes (repo-relative, /-separated)
 * @returns {Promise<{ok:boolean, problems:string[], galleryIds:string[]}>}
 */
export async function checkAnimalPr(changed) {
  const files = (changed || []).map((s) => String(s).trim()).filter(Boolean);
  const problems = [];
  const galleryIds = [];
  const changedJsIds = new Set();

  // 1. No framework edits (anything under animal-svg/ that isn't a community module).
  for (const f of files) {
    const jm = f.match(ANIMAL_JS_RE);
    if (jm) {
      changedJsIds.add(jm[1]);
      continue;
    }
    if (f.startsWith(ANIMAL_SVG_DIR)) {
      problems.push(`PR modifies the animal-svg framework (not allowed for an animal submission): ${f}`);
    }
  }

  // 2–4. Validate + sanitise-check + tamper-check each changed descriptor.
  for (const f of files) {
    const m = f.match(GALLERY_RE);
    if (!m) continue;
    const id = m[1];
    galleryIds.push(id);

    let parsed;
    try {
      parsed = JSON.parse(readFileSync(f, "utf8"));
    } catch (e) {
      problems.push(`${f}: not valid JSON (${e.message})`);
      continue;
    }
    const input = parsed && parsed.animal ? parsed.animal : parsed;

    const existing = existingAnimalIds().filter((x) => x !== id); // updating an existing animal is fine
    const v = validateDescriptor(input, { existingIds: existing });
    if (!v.ok) {
      problems.push(`${f}: invalid descriptor:\n` + v.errors.map((e) => "      - " + e).join("\n"));
      continue;
    }
    if (v.animal.id !== id) {
      problems.push(`${f}: descriptor id "${v.animal.id}" doesn't match the filename id "${id}".`);
      continue;
    }

    const san = await sanitizeParts(v.animal.parts);
    if (Object.keys(san.removed).length) {
      problems.push(
        `${f}: the committed SVG isn't fully sanitised — rebuild with \`node scripts/build-animal.mjs\`. Would strip:\n` +
          summariseRemovals(san.removed).replace(/^/gm, "      "),
      );
    }

    const jsPath = resolve(ANIMALS_DIR, `${id}.js`);
    if (!existsSync(jsPath)) {
      problems.push(`${f}: missing the generated module animals/${id}.js — run \`node scripts/build-animal.mjs gallery/animals/${id}.json\`.`);
    } else if (readFileSync(jsPath, "utf8").trim() !== codegenAnimalModule(v.animal).trim()) {
      problems.push(`animals/${id}.js doesn't match its descriptor — don't hand-edit it; regenerate with \`node scripts/build-animal.mjs gallery/animals/${id}.json\`.`);
    }
  }

  // 5. No orphan modules (a changed .js with no matching descriptor in the PR).
  for (const id of changedJsIds) {
    if (!galleryIds.includes(id)) {
      problems.push(`animals/${id}.js changed without gallery/animals/${id}.json — community modules are generated from a descriptor, not hand-written.`);
    }
  }

  return { ok: problems.length === 0, problems, galleryIds };
}

// --- CLI ---------------------------------------------------------------------
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const changed = String(process.env.CHANGED_FILES || "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  const r = await checkAnimalPr(changed);
  if (!r.ok) {
    console.error("❌ Animal PR check failed:\n" + r.problems.map((p) => "  - " + p).join("\n"));
    process.exit(1);
  }
  console.log(`✅ Animal PR check passed (${r.galleryIds.length} animal(s): ${r.galleryIds.join(", ") || "none"}).`);
}
