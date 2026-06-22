/**
 * ============================================================
 * ANIMAL SUBMISSION PROCESSOR  (gallery intake bot core)
 * ============================================================
 *
 * The animal counterpart to process-submission.mjs. Turns an "animal-submission"
 * issue body into the gallery artifacts + a human report, reusing the SAME
 * validate→sanitise→codegen core (build-animal.mjs) that the fork-PR check uses,
 * so both intake paths are identical.
 *
 * Two layers:
 *   parseAnimalIssue(body) — SYNC. Pulls the descriptor JSON out of the ```json
 *     fence + the convenience metadata fields, returns the merged `animal`
 *     input (or a fix-it report). Unit-testable with no browser.
 *   processAnimalSubmission(body, issueNumber) — ASYNC. Runs the descriptor
 *     through buildAnimal (which sanitises in real Chromium), returns the
 *     envelope + generated module + a validated/invalid report. Runs in the
 *     intake workflow's Playwright container.
 *
 * Security: nothing here trusts the input. The contract gate + the DOMPurify
 * sanitiser inside buildAnimal are the boundary; this layer only parses + merges
 * + formats. source:"community" is stamped in the core.
 * ============================================================
 */
import { getField } from "./process-submission.mjs";
import { buildAnimal, existingAnimalIds } from "./build-animal.mjs";

// Issue-form field labels — the contract with animal-submission.yml's `label:`s.
export const FIELD = {
  descriptor: "Animal descriptor JSON",
  // Full-SVG path: the drawing + the metadata the SVG can't carry itself.
  fullSvg: "Full SVG",
  id: "Animal id",
  name: "Animal name",
  type: "Body plan",
  license: "Licence",
  memorial: "Memorial (Rainbow Bridge)",
  colors: "Colour defaults (JSON)",
  author: "Author",
  authorUrl: "Author URL",
  submittedBy: "Submitted by",
};

/**
 * Detect the submission MODE + extract its inputs. Two paths share one form:
 *   descriptor — a ```json fence (the animal object / envelope).
 *   svg        — a pasted full <svg> + the id/name/type/licence/memorial fields.
 * @returns {{ok:true, mode:"descriptor", animal}|{ok:true, mode:"svg", svg, meta}|{ok:false, reason, report}}
 */
export function parseAnimalIssue(issueBody) {
  const body = String(issueBody || "");

  // Shared credit fields (apply to both paths).
  const author = getField(body, FIELD.author);
  const authorUrl = getField(body, FIELD.authorUrl);
  const submittedBy = getField(body, FIELD.submittedBy);
  const applyCredit = (obj) => {
    if (author) obj.author = author;
    if (authorUrl) obj.author_url = authorUrl;
    if (submittedBy) obj.submitted_by = submittedBy;
    return obj;
  };

  // Descriptor mode — a ```json fence wins if present.
  const m = body.match(/```json\s*\n([\s\S]*?)\n```/);
  if (m) {
    let parsed;
    try {
      parsed = JSON.parse(m[1]);
    } catch (e) {
      return { ok: false, reason: "bad_json", report: `That descriptor isn't valid JSON: \`${e.message}\`. Fix it, then close and reopen this issue to retry.` };
    }
    const animal = parsed && typeof parsed === "object" && parsed.animal ? { ...parsed.animal } : { ...parsed };
    return { ok: true, mode: "descriptor", animal: applyCredit(animal) };
  }

  // Full-SVG mode — a pasted drawing + the metadata fields.
  const svg = getField(body, FIELD.fullSvg);
  if (svg && /<svg[\s>]/i.test(svg)) {
    let colors;
    const rawColors = getField(body, FIELD.colors);
    if (rawColors) {
      try {
        colors = JSON.parse(rawColors);
      } catch {
        /* leave undefined → the tool scaffolds + the report flags it */
      }
    }
    const meta = applyCredit({
      id: getField(body, FIELD.id) || undefined,
      name: getField(body, FIELD.name) || undefined,
      type: /parrot/i.test(getField(body, FIELD.type)) ? "parrot" : "quadruped",
      license: getField(body, FIELD.license) || undefined,
      memorial: /\[x\]/i.test(getField(body, FIELD.memorial)),
      ...(colors ? { colors } : {}),
    });
    return { ok: true, mode: "svg", svg, meta };
  }

  return {
    ok: false,
    reason: "no_input",
    report:
      "Couldn't find a submission. Either paste a descriptor into **Animal descriptor JSON** (inside the ```json fence), or paste a drawing into **Full SVG** and fill the id / name / licence fields. Then close and reopen this issue to retry.",
  };
}

function invalidReport(errors) {
  return [
    "### ❌ Couldn't accept this animal",
    "",
    "Fix the points below, then **close and reopen** this issue to retry:",
    "",
    ...errors.map((e) => `- ${e}`),
  ].join("\n");
}

function okReport(animal, removed, meta, extra = {}) {
  const lines = [`### ✅ Validated — ${animal.name}`, ""];
  lines.push(`**Type:** ${animal.type}${animal.memorial ? " · 🌈 Rainbow Bridge (memorial)" : ""}`);

  const themeable = Object.keys(animal.colors).filter((k) => k !== "--animal-eye");
  lines.push(`**Themeable:** ${themeable.length ? `${themeable.length} colour token${themeable.length === 1 ? "" : "s"}` : "baked (eye only)"}`);
  lines.push(`**Licence:** ${animal.license}`);

  const credit = [];
  if (animal.author) credit.push(animal.author_url ? `[${animal.author}](${animal.author_url})` : animal.author);
  if (animal.submitted_by && animal.submitted_by !== animal.author) credit.push(`submitted by ${animal.submitted_by}`);
  lines.push(`**Source:** community${credit.length ? ` · ${credit.join(" · ")}` : ""}`);

  if (meta && meta.authorUrlRejected) {
    lines.push("", "> ⚠ The author URL must be a direct http(s) link (no shorteners) — your credit will show without a link.");
  }

  const removedSlots = Object.keys(removed || {});
  if (removedSlots.length) {
    lines.push("", "**The sanitiser cleaned a few things** (kept the art, dropped the rest):");
    for (const [slot, items] of Object.entries(removed)) {
      const bits = items.map((r) => (r.kind === "attribute" ? `@${r.name}` : `<${r.name}>`));
      lines.push(`- \`parts.${slot}\`: ${bits.join(", ")}`);
    }
  }

  if (extra.svg) {
    lines.push("", "**Built from your SVG** — here's the safe descriptor we generated (review it):");
    if (extra.scaffoldedColors) {
      lines.push("> ⚠ Colours were scaffolded with placeholders — set your real `--animal-*` default values (a maintainer can do this on the PR).");
    }
    lines.push("", "```json", JSON.stringify(extra.envelope, null, 2), "```");
  }

  return lines.join("\n");
}

/**
 * @param {string} issueBody
 * @param {number|string} issueNumber  (kept for parity / future use)
 * @param {object} [opts] {existingIds}
 */
export async function processAnimalSubmission(issueBody, issueNumber, opts = {}) {
  const parsed = parseAnimalIssue(issueBody);
  if (!parsed.ok) return parsed;

  const existingIds = opts.existingIds ?? existingAnimalIds();

  // Full-SVG path: split + sanitise the drawing into a descriptor first.
  let animalInput = parsed.animal;
  let scaffoldedColors = false;
  if (parsed.mode === "svg") {
    const { svgToDescriptor } = await import("./svg-to-descriptor.mjs");
    const r = await svgToDescriptor(parsed.svg, parsed.meta);
    if (!r.ok) {
      return { ok: false, reason: "svg", report: `### ❌ Couldn't read your SVG\n\n${r.error}` };
    }
    animalInput = r.envelope.animal;
    scaffoldedColors = r.scaffoldedColors;
  }

  // build-animal is the authoritative gate for BOTH paths (validate + sanitise
  // + codegen) — so the svg path re-sanitises (idempotent) and is held to the
  // exact same contract as a hand-written descriptor.
  const built = await buildAnimal(animalInput, { existingIds });
  if (!built.ok) {
    return { ok: false, reason: "invalid", report: invalidReport(built.errors), errors: built.errors };
  }

  const slug = built.animal.id; // the id IS the unique gallery key + register name
  return {
    ok: true,
    slug,
    name: built.animal.name,
    envelope: built.envelope,
    moduleJs: built.moduleJs,
    removed: built.removed,
    report: okReport(built.animal, built.removed, built.meta, {
      svg: parsed.mode === "svg",
      scaffoldedColors,
      envelope: built.envelope,
    }),
  };
}
