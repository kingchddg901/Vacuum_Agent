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

// Author-URL policy: a direct http(s) profile/project link only. new URL() parses
// the real scheme, so javascript:/data:/vbscript:/file:/blob:/about: are all
// rejected; URL shorteners are blocked so credits point at a real destination.
export const AUTHOR_URL_ERROR =
  "Author URL must be a direct http(s) profile or project link. URL shorteners are not accepted for gallery author credits.";

const URL_SHORTENERS = new Set([
  "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
  "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "t.ly", "lnkd.in", "tiny.cc",
  "bl.ink", "soo.gd", "clck.ru", "v.gd", "shrtco.de", "snip.ly", "adf.ly",
  "han.gl", "short.io", "tr.im", "x.co", "1url.com", "qr.ae", "shorte.st",
]);

/** True only for a direct http(s) link to a non-shortener host. */
export function isAcceptableAuthorUrl(url) {
  let u;
  try {
    u = new URL(String(url || "").trim());
  } catch {
    return false; // not a parseable URL (or a bare scheme like "javascript:foo")
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") return false;
  const host = u.hostname.toLowerCase().replace(/^www\./, "");
  return !URL_SHORTENERS.has(host);
}

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

function buildReport({ themeName, tags, colorblind, attr, cbClaim, authorUrlRejected }) {
  const lines = [`### ✅ Validated — ${themeName}`, ""];

  if (authorUrlRejected) {
    lines.push(`> ⚠ ${AUTHOR_URL_ERROR} Your credit will show without a link — fix it and reopen if you want one.`, "");
  }

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
  // author_url is untrusted + ends up in a gallery <a href>. Accept only a direct
  // http(s) non-shortener link (rejecting dangerous schemes is also XSS defense);
  // anything else is dropped and the submitter is told why (non-blocking).
  const rawUrl = getField(body, FIELD.authorUrl).slice(0, MAX_FIELD).trim();
  const authorUrl = isAcceptableAuthorUrl(rawUrl) ? rawUrl : "";
  const authorUrlRejected = rawUrl !== "" && authorUrl === "";
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
  const report = buildReport({ themeName, tags, colorblind, attr, cbClaim, authorUrlRejected });

  return { ok: true, slug, themeName, envelope, report, tags, colorblind };
}

// Exposed for the test + any CLI use.
export { getField, parseVibeTags, slugify, buildReport };
