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
 * may not change — with ONE exception, animals/index.json, the served roster: it
 * is tracked (it has to be in the release zip) so adding an animal necessarily
 * updates it, and a PR that cannot touch it cannot be made to pass. Allowing it
 * comes with two checks, because the card loads `animals/<entry>` for each entry:
 * every entry must be a bare `<id>.js` name, and every animal the PR adds must be
 * listed. A changed .js with no descriptor is an orphan. Whether a
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

// The served roster. It is TRACKED (it has to be in the release zip, or the card's
// fetch of it 404s until the next HA restart — see .gitignore's note), and adding an
// animal therefore means updating it. So a PR must be ALLOWED to touch this one file
// under animal-svg/, where everything else is framework and off-limits.
//
// Allowing it is only safe with the two checks below, because the card does
// `loadScript('animals/' + entry)` over whatever this file says: an entry containing a
// path separator would load an arbitrary served file. Entries must be bare `<id>.js`
// names, and every animal the PR adds must actually be listed.
const ANIMAL_INDEX = ANIMAL_SVG_DIR + "animals/index.json";
const INDEX_ENTRY_RE = /^[a-z0-9-]+\.js$/;

// Compare codegen against the committed module by CONTENT, not line endings:
// codegen emits LF, but a Windows checkout (no .gitattributes) may hold the
// committed .js as CRLF. Stripping CR keeps the tamper-check honest there —
// real tampering changes content, which survives this normalization.
const codeEq = (a, b) => a.replace(/\r/g, "").trim() === b.replace(/\r/g, "").trim();

/**
 * Problems with the served roster's CONTENT. Pure and exported so the hostile cases can
 * be tested directly — the caller reads the real file from disk, and a test that had to
 * mutate a tracked file to reach these branches would not get written.
 *
 * @param {unknown} listed     parsed animals/index.json
 * @param {string[]} requiredIds animal ids the PR adds, which the index must name
 * @returns {string[]}
 */
export function indexProblems(listed, requiredIds = []) {
  if (!Array.isArray(listed)) {
    return ["animals/index.json must be a JSON array of `<id>.js` filenames."];
  }
  const problems = [];
  const bad = listed.filter((e) => typeof e !== "string" || !INDEX_ENTRY_RE.test(e));
  if (bad.length) {
    problems.push(
      `animals/index.json has entries that are not bare \`<id>.js\` names: ` +
      `${bad.map((e) => JSON.stringify(e)).join(", ")} — the card loads each as ` +
      `\`animals/<entry>\`, so a path there would load an arbitrary served file.`);
  }
  for (const id of requiredIds) {
    if (!listed.includes(`${id}.js`)) {
      problems.push(
        `animals/${id}.js is not listed in animals/index.json — regenerate it (the sorted ` +
        `list of \`*.js\` in that directory) and commit it, or the card will not load this ` +
        `animal until Home Assistant restarts.`);
    }
  }
  return problems;
}

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
    if (GALLERY_RE.test(f) || SRC_RE.test(f) || f === ANIMAL_INDEX) continue;
    if (f.startsWith(ANIMAL_SVG_DIR)) {
      problems.push(`PR modifies the animal-svg framework (not allowed for an animal submission): ${f}`);
    }
  }

  // 1b. The served roster must stay loadable, and must list what the PR adds.
  //     Checked against the file ON DISK rather than the changed-file list, so it holds
  //     whether or not the PR touched it — a module added without the index being
  //     updated is the deadlock this exists to make actionable: the card would not load
  //     the new animal until the next HA restart, and `served-indexes.test.mjs` [IDX-1]
  //     would fail the PR with no hint of what to do about it.
  if (changedJsIds.size || files.includes(ANIMAL_INDEX)) {
    let listed = null;
    try {
      listed = JSON.parse(readFileSync(resolve(ANIMALS_DIR, "index.json"), "utf8"));
    } catch (e) {
      problems.push(`animals/index.json is missing or unreadable (${e.message}) — it is tracked and must stay valid JSON.`);
    }
    if (listed !== null) problems.push(...indexProblems(listed, [...changedJsIds]));
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
    } else if (!codeEq(readFileSync(jsPath, "utf8"), codegenAnimalModule(v.animal))) {
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
