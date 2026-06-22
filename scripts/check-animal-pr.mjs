/**
 * ============================================================
 * CHECK ANIMAL PR  (fork-PR intake gate)
 * ============================================================
 *
 * A contributor opens a PR that adds/edits an animal. This gate runs in CI
 * (animal-pr-check.yml) and enforces the boundary for BOTH descriptor homes:
 *   gallery/animals/<id>.json — community submissions.
 *   …/animal-svg/src/<id>.json — first-party / bundled animals (reserved ids,
 *                                source:"core"); maintainer territory, but still
 *                                checked for consistency so a hand-written .js
 *                                can't sneak in beside a stub descriptor.
 *
 * For every changed descriptor: validate (community vs first-party), confirm the
 * committed SVG is already sanitised, and require the committed animals/<id>.js
 * to be its faithful codegen. Framework files (animal-svg.js, manifest.js, …)
 * may not change. A changed .js with no descriptor is an orphan. Whether a
 * first-party/reserved change is *legitimate* is the maintainer's call on merge;
 * this gate guarantees no arbitrary code (every .js is codegen of a sanitised
 * descriptor) + no framework edits.
 *
 * checkAnimalPr(changedFiles) -> { ok, problems, galleryIds }. CLI reads
 * CHANGED_FILES (newline-separated) and exits non-zero on any problem.
 * ============================================================
 */
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { validateDescriptor, codegenAnimalModule } from "./animal-descriptor.mjs";
import { sanitizeParts, summariseRemovals } from "./sanitize-animal-svg.mjs";
import { existingAnimalIds, ANIMALS_DIR } from "./build-animal.mjs";

const GALLERY_RE = /^gallery\/animals\/([a-z0-9-]+)\.json$/;
const SRC_RE = /^custom_components\/eufy_vacuum\/frontend\/animal-svg\/src\/([a-z0-9-]+)\.json$/;
const ANIMAL_JS_RE = /^custom_components\/eufy_vacuum\/frontend\/animal-svg\/animals\/([a-z0-9-]+)\.js$/;
const ANIMAL_SVG_DIR = "custom_components/eufy_vacuum/frontend/animal-svg/";

/**
 * @param {string[]} changed  file paths the PR changes (repo-relative, /-separated)
 * @returns {Promise<{ok:boolean, problems:string[], galleryIds:string[]}>}
 */
export async function checkAnimalPr(changed) {
  const files = (changed || []).map((s) => String(s).trim()).filter(Boolean);
  const problems = [];
  const descriptorIds = new Set(); // ids with a changed descriptor (gallery OR src)
  const changedJsIds = new Set();

  // 1. Classify + framework check. Allowed under animal-svg/: animals/<id>.js
  //    (generated modules) and src/<id>.json (first-party descriptors). Anything
  //    else there (the framework itself) is off-limits.
  for (const f of files) {
    if (ANIMAL_JS_RE.test(f)) {
      changedJsIds.add(f.match(ANIMAL_JS_RE)[1]);
      continue;
    }
    if (GALLERY_RE.test(f) || SRC_RE.test(f)) continue;
    if (f.startsWith(ANIMAL_SVG_DIR)) {
      problems.push(`PR modifies the animal-svg framework (not allowed for an animal submission): ${f}`);
    }
  }

  // 2. Validate + sanitise-check + tamper-check each changed descriptor.
  const checkDescriptor = async (f, id, firstParty) => {
    descriptorIds.add(id);
    let parsed;
    try {
      parsed = JSON.parse(readFileSync(f, "utf8"));
    } catch (e) {
      problems.push(`${f}: not valid JSON (${e.message})`);
      return;
    }
    const input = parsed && parsed.animal ? parsed.animal : parsed;
    const existing = existingAnimalIds().filter((x) => x !== id);
    const v = validateDescriptor(input, {
      existingIds: existing,
      allowReservedIds: firstParty,
      source: firstParty ? "core" : undefined,
    });
    if (!v.ok) {
      problems.push(`${f}: invalid descriptor:\n` + v.errors.map((e) => "      - " + e).join("\n"));
      return;
    }
    if (v.animal.id !== id) {
      problems.push(`${f}: descriptor id "${v.animal.id}" doesn't match the filename id "${id}".`);
      return;
    }
    const san = await sanitizeParts(v.animal.parts);
    if (Object.keys(san.removed).length) {
      problems.push(
        `${f}: the committed SVG isn't fully sanitised — rebuild with build-animal. Would strip:\n` +
          summariseRemovals(san.removed).replace(/^/gm, "      "),
      );
    }
    const jsPath = resolve(ANIMALS_DIR, `${id}.js`);
    if (!existsSync(jsPath)) {
      problems.push(`${f}: missing the generated module animals/${id}.js — run \`node scripts/build-animal.mjs ${f}${firstParty ? " --first-party" : ""}\`.`);
    } else if (readFileSync(jsPath, "utf8").trim() !== codegenAnimalModule(v.animal).trim()) {
      problems.push(`animals/${id}.js doesn't match its descriptor — regenerate with \`node scripts/build-animal.mjs ${f}${firstParty ? " --first-party" : ""}\`.`);
    }
  };

  for (const f of files) {
    const g = f.match(GALLERY_RE);
    if (g) {
      await checkDescriptor(f, g[1], false);
      continue;
    }
    const s = f.match(SRC_RE);
    if (s) {
      await checkDescriptor(f, s[1], true);
    }
  }

  // 3. No orphan modules (a changed .js with no descriptor in the PR).
  for (const id of changedJsIds) {
    if (!descriptorIds.has(id)) {
      problems.push(`animals/${id}.js changed without a descriptor (gallery/animals/${id}.json or src/${id}.json) — modules are generated from a descriptor, not hand-written.`);
    }
  }

  return { ok: problems.length === 0, problems, galleryIds: [...descriptorIds] };
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
