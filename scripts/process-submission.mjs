/**
 * ============================================================
 * THEME SUBMISSION PROCESSOR  (gallery intake bot core)
 * ============================================================
 *
 * Pure transform from a "theme-submission" issue body to a gallery-ready theme
 * envelope + a human report. Factored out of the workflow YAML so it's unit
 * testable (scripts/process-submission.test.mjs) and reuses the SAME theme-tags
 * core the card and gallery use — so a submission is tagged/verified identically.
 *
 * Contract: processSubmission(issueBody, issueNumber) -> {
 *   ok, reason?, slug?, themeName?, envelope?, report, tags?, colorblind?
 * }
 *   - ok:false  -> structure invalid; `report` explains what to fix (no PR).
 *   - ok:true   -> `envelope` is the final JSON to write; `report` is the
 *                  issue comment (preview is added by the workflow).
 *
 * Provenance: every accepted submission is stamped source:"community". The
 * submitter's free-text VIBE tags are kept (system words stripped); the facet
 * tags + colorblind-safe are DERIVED/VERIFIED live, never stored. A colorblind
 * claim that fails is NON-BLOCKING: the badge is simply not earned and the
 * report says why.
 * ============================================================
 */
import {
  effectiveThemeTags,
  themeAttribution,
  orderTags,
  facetOf,
  SYSTEM_VOCAB,
  CVD_DELTA_E,
} from "../src/theme-tags/index.mjs";

// Issue-form field labels — these are the contract with theme-submission.yml's
// `label:` values (GitHub renders each as a `### <label>` section in the body).
export const FIELD = {
  export: "Theme export JSON",
  tags: "Vibe tags",
  author: "Author",
  authorUrl: "Author URL",
  submittedBy: "Submitted by",
  colorblind: "Colorblind-safe claim",
};

const MAX_TAGS = 16;
const MAX_FIELD = 200;
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Extract a "### Label\n\n<value>" section; "" for missing or "_No response_". */
function getField(body, label) {
  const re = new RegExp(`###\\s*${escapeRe(label)}\\s*\\n([\\s\\S]*?)(?=\\n###\\s|$)`, "i");
  const m = String(body || "").match(re);
  if (!m) return "";
  const v = m[1].trim();
  return /^_no response_$/i.test(v) ? "" : v;
}

/** Split free-text tags on commas / newlines; clean, dedupe, drop system words. */
function parseVibeTags(raw) {
  const seen = new Set();
  const out = [];
  for (const piece of String(raw || "").split(/[,\n]/)) {
    const tag = piece.trim().toLowerCase();
    // System words (dark/core/colorblind-safe…) are derived/verified, never
    // free-text — strip them so a submission can't spoof a facet.
    if (!tag || tag.length > 32 || seen.has(tag) || SYSTEM_VOCAB.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
    if (out.length >= MAX_TAGS) break;
  }
  return out;
}

const slugify = (name) =>
  String(name || "theme")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "theme";

function buildReport({ themeName, tags, colorblind, attr, cbClaim }) {
  const lines = [`### ✅ Validated — ${themeName}`, ""];

  const tagList = orderTags(tags).map((t) => `\`${t}\``).join(" ");
  lines.push(`**Tags:** ${tagList || "_none_"}`);

  const credit = [];
  if (attr.author) credit.push(attr.authorUrl ? `[${attr.author}](${attr.authorUrl})` : attr.author);
  if (attr.submittedBy && attr.submittedBy !== attr.author) credit.push(`submitted by ${attr.submittedBy}`);
  lines.push(`**Source:** community${credit.length ? ` · ${credit.join(" · ")}` : ""}`);

  // Colorblind-safe is verified, never asserted. The claim only drives the
  // explanation; a pass earns the badge regardless of the claim.
  if (cbClaim && colorblind.verified) {
    lines.push("", "**Colorblind-safe:** ✓ verified — earns the badge.");
  } else if (cbClaim && !colorblind.verified) {
    const why = (colorblind.reasons || [])
      .slice(0, 2)
      .map((r) => `\`${r.pair.join("/")}\` under ${r.cvd} (ΔE ${r.deltaE})`)
      .join("; ");
    lines.push(
      "",
      `**Colorblind-safe:** ✗ claimed, but it doesn't pass (min ΔE ${colorblind.minDeltaE} < ${CVD_DELTA_E}${why ? `: ${why}` : ""}).`,
      "Published **without** the badge — that's fine; fix the palette and reopen if you want to earn it.",
    );
  } else if (!cbClaim && colorblind.verified) {
    lines.push("", "**Colorblind-safe:** 🎉 bonus — this theme qualifies for the badge (you didn't even claim it).");
  }

  return lines.join("\n");
}

/**
 * @param {string} issueBody  the rendered issue-form body.
 * @param {number|string} issueNumber  used to make the slug unique per issue.
 */
export function processSubmission(issueBody, issueNumber) {
  const body = String(issueBody || "");

  // 1. Extract the export JSON (the only ```json fence in the form).
  const m = body.match(/```json\s*\n([\s\S]*?)\n```/);
  if (!m) {
    return {
      ok: false,
      reason: "no_export",
      report:
        "Couldn't find the export. Paste the full JSON into the **Theme export JSON** box, then close and reopen this issue to retry.",
    };
  }
  let env;
  try {
    env = JSON.parse(m[1]);
  } catch (e) {
    return {
      ok: false,
      reason: "bad_json",
      report: `That export isn't valid JSON: \`${e.message}\`. Re-copy it from the card's **Download** / **Export** button, then close and reopen this issue to retry.`,
    };
  }
  const t = env && typeof env === "object" ? env.theme : null;
  if (!t || typeof t !== "object" || !(t.tokens || t.colors || t.alpha)) {
    return {
      ok: false,
      reason: "not_theme",
      report:
        "That doesn't look like a theme export (no `theme.tokens` / `colors` / `alpha`). Use the card's **Download** / **Export** button.",
    };
  }

  // 2. Parse the submitter's metadata fields.
  const vibe = parseVibeTags(getField(body, FIELD.tags));
  const author = getField(body, FIELD.author).slice(0, MAX_FIELD);
  // author_url is untrusted + ends up in a gallery <a href> — only http(s) is kept
  // (a javascript:/data: URL would be a stored-XSS sink). Anything else is dropped.
  const rawUrl = getField(body, FIELD.authorUrl).slice(0, MAX_FIELD).trim();
  const authorUrl = /^https?:\/\//i.test(rawUrl) ? rawUrl : "";
  const submittedBy = getField(body, FIELD.submittedBy).slice(0, MAX_FIELD);
  const cbClaim = /\[x\]/i.test(getField(body, FIELD.colorblind));

  // 3. Build the final theme: stamp community provenance + carry metadata.
  const theme = { ...t, source: "community" };
  if (vibe.length) theme.tags = vibe;
  else delete theme.tags;
  for (const [key, value] of [["author", author], ["author_url", authorUrl], ["submitted_by", submittedBy]]) {
    if (value) theme[key] = value;
    else delete theme[key];
  }
  const envelope = { ...env, theme };

  // 4. Tags + colorblind verdict from the shared core (same as card/gallery).
  const { tags, colorblind } = effectiveThemeTags(theme);
  const attr = themeAttribution(theme);

  const themeName = String(t.name || slugify(t.name)) || "Theme";
  const slug = `${slugify(t.name)}-${issueNumber}`;
  const report = buildReport({ themeName, tags, colorblind, attr, cbClaim });

  return { ok: true, slug, themeName, envelope, report, tags, colorblind };
}

// Exposed for the test + any CLI use.
export { getField, parseVibeTags, slugify, buildReport };
