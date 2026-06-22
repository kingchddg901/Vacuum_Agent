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
  author: "Author",
  authorUrl: "Author URL",
  submittedBy: "Submitted by",
};

/**
 * Extract + merge the submission into a single `animal` input object.
 * @returns {{ok:true, animal:object} | {ok:false, reason:string, report:string}}
 */
export function parseAnimalIssue(issueBody) {
  const body = String(issueBody || "");

  const m = body.match(/```json\s*\n([\s\S]*?)\n```/);
  if (!m) {
    return {
      ok: false,
      reason: "no_descriptor",
      report:
        "Couldn't find the descriptor. Paste the full animal descriptor JSON into the **Animal descriptor JSON** box (inside the ```json fence), then close and reopen this issue to retry.",
    };
  }
  let parsed;
  try {
    parsed = JSON.parse(m[1]);
  } catch (e) {
    return {
      ok: false,
      reason: "bad_json",
      report: `That descriptor isn't valid JSON: \`${e.message}\`. Fix it, then close and reopen this issue to retry.`,
    };
  }

  // Accept an envelope { animal: {...} } or the bare animal object.
  const animal = parsed && typeof parsed === "object" && parsed.animal ? { ...parsed.animal } : { ...parsed };

  // Convenience metadata fields override the descriptor (so a submitter can
  // credit themselves without editing JSON). Empty fields are ignored.
  const author = getField(body, FIELD.author);
  const authorUrl = getField(body, FIELD.authorUrl);
  const submittedBy = getField(body, FIELD.submittedBy);
  if (author) animal.author = author;
  if (authorUrl) animal.author_url = authorUrl;
  if (submittedBy) animal.submitted_by = submittedBy;

  return { ok: true, animal };
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

function okReport(animal, removed, meta) {
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
  const built = await buildAnimal(parsed.animal, { existingIds });
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
    report: okReport(built.animal, built.removed, built.meta),
  };
}
