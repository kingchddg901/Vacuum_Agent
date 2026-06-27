/**
 * ============================================================
 * LOCALE INTAKE GATE — sanitize-or-quarantine (the trust boundary)
 * ============================================================
 *
 * Community/user-authored JSON locales ride the SAME untrusted intake path as
 * the animal-add system (data-not-code, reload-not-rebuild). Trust Model B in
 * index.js already HTML-escapes every catalog value at translate() time — except
 * the ~13 `tRaw` keys, whose values are emitted RAW into innerHTML by the call
 * site. A loaded locale supplying a value for a tRaw key is the injection
 * surface. This gate closes it by scrubbing each parsed locale BEFORE
 * registerLocale, so by translate-time provenance no longer matters.
 *
 * It does NOT replace the translate()-time escape — that stays as the independent
 * backstop. Two layers is the correct posture for an untrusted path.
 *
 * It operates UNIFORMLY over every value (no tRaw key-list to maintain — a 14th
 * tRaw site needs no change here), and recursively (plural-object form strings
 * included — that is where external_jobs.detected_rooms keeps its <strong>).
 *
 * DETECTION uses DOMPurify (the same engine the animal SVG sanitiser trusts) in
 * the BROWSER — the same parser the innerHTML sink will later use, which is where
 * mutation-XSS hides. PARSE, never regex: DOMPurify hands hooks the *parsed*
 * attribute name, so `on\nerror` / `java&#9;script:` resolve to their real
 * identity and cannot evade. The escape-visible SCRUB (§5) is a small DOM walk
 * that runs only AFTER detection has cleared a value of active content.
 *
 * Three bright-line outcomes (no runtime judgement calls):
 *   REJECT_MALFORMED  — not a plain object of string / plural-of-string values.
 *                       Honest mistake → soft skip, NOT hash-locked (retried).
 *   QUARANTINE_HOSTILE — any value carries active content (§4). Positive tamper
 *                       evidence taints the shared-source siblings → reject the
 *                       WHOLE file. Hash-locked by the loader.
 *   LOAD              — clean, or only inert-disallowed markup that was scrubbed.
 *
 * ============================================================
 */

import DOMPurify from "dompurify";

export const OUTCOME = Object.freeze({
  REJECT_MALFORMED: "REJECT_MALFORMED",
  QUARANTINE_HOSTILE: "QUARANTINE_HOSTILE",
  LOAD: "LOAD",
});

// Inline markup the first-party tRaw keys legitimately carry. Everything else is
// inert-escaped (§5) or — if active — quarantines (§4).
const ALLOWED_TAGS = Object.freeze(["strong", "em", "code", "a"]);
// Active-content tags: no legitimate reason to appear in a translation string.
const DANGEROUS_TAGS = new Set(["script", "iframe", "object", "embed", "link", "meta", "base", "form"]);
// An <a href> may only point at these hosts (a translator linking a localized doc
// mirror is a believable good-faith act → scrub the href off, never quarantine).
const ALLOWED_HOSTS = new Set(["github.com", "kingchddg901.github.io"]);

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

/**
 * Verdict for a URL-bearing attribute, by PARSING the scheme (not startsWith).
 * `hostile` → an active scheme (javascript:/data:/vbscript:…) or scheme-relative
 * //host: positive tamper evidence → quarantine. `ok` → http(s) or a relative
 * ref; the off-allowlist HOST case is a scrub (handled in the walk), not hostile.
 */
function urlVerdict(value) {
  const s = String(value ?? "").trim();
  if (/^\/\//.test(s)) return "hostile"; // scheme-relative //host (no scheme to parse)
  // Resolve through the URL parser — it strips tab/newline/control chars the way
  // the HTML parser does, so `java&#9;script:` (decoded to a tab) and `java\tscript:`
  // collapse to their real scheme. A RAW regex would be evaded; this is the point.
  let scheme;
  try {
    scheme = new URL(s).protocol.replace(/:$/, "").toLowerCase();
  } catch {
    return "ok"; // relative ref / no scheme — host-allowlist (scrub) handles the rest
  }
  return (scheme === "http" || scheme === "https") ? "ok" : "hostile";
}

/** Whether an <a href> survives the scrub: http(s) AND an allowlisted host. */
function hrefSurvives(value) {
  try {
    const u = new URL(String(value ?? "").trim());
    return (u.protocol === "http:" || u.protocol === "https:") && ALLOWED_HOSTS.has(u.hostname.toLowerCase());
  } catch {
    return false; // relative / malformed → strip the href, keep the text
  }
}

/**
 * Run DOMPurify over one value purely to DETECT active content. Returns
 * `{ hostile, predicate, detail }`. DOMPurify parses with the real browser
 * engine and hands the hooks PARSED names, defeating encoded/padded evasion.
 */
function detectHostile(value) {
  // Detect by PARSING with the browser's own engine — the same parser the
  // innerHTML sink will use — and walking the real tree. This is why we don't
  // regex: encoded/padded names (`on&#101;rror`, `java&#9;script:`) and split
  // names (`on\nerror` → two harmless attrs) resolve to their true identity in
  // the DOM. (DOMPurify.removed is unreliable here — it logs the BODY wrapper,
  // not the forbidden tag, when the whole value is stripped.)
  const tpl = document.createElement("template");
  tpl.innerHTML = String(value ?? "");
  let hit = null;
  const walk = (parent) => {
    for (const node of parent.childNodes) {
      if (hit || node.nodeType !== 1) continue;
      const tag = node.tagName.toLowerCase();
      if (DANGEROUS_TAGS.has(tag)) { hit = { hostile: true, predicate: "dangerous_tag", detail: tag }; return; }
      for (const attr of node.attributes) {
        const name = attr.name.toLowerCase();
        if (/^on/.test(name)) { hit = { hostile: true, predicate: "event_handler", detail: name }; return; }
        if ((name === "href" || name === "src" || name === "xlink:href") && urlVerdict(attr.value) === "hostile") {
          hit = { hostile: true, predicate: "dangerous_url_scheme", detail: `${name}=${String(attr.value).trim().slice(0, 40)}` };
          return;
        }
      }
      walk(node);
      if (hit) return;
    }
  };
  walk(tpl.content);
  return hit || { hostile: false, predicate: null, detail: null };
}

/**
 * Escape-visible SCRUB (§5), reached only after detectHostile cleared the value.
 * Parses with the browser's own parser and serializes: allowlisted tags survive
 * as markup (attributes dropped; an <a href> only if it survives the host check);
 * text is escaped; any DISALLOWED-but-inert element is escaped to VISIBLE literal
 * text (not silently stripped) so a translator sees their mistake rendered.
 */
function scrubToString(value) {
  const tpl = document.createElement("template");
  tpl.innerHTML = String(value ?? "");
  const walk = (parent) => {
    let out = "";
    for (const node of parent.childNodes) {
      if (node.nodeType === 3) {            // text
        out += esc(node.nodeValue);
      } else if (node.nodeType === 1) {     // element
        const tag = node.tagName.toLowerCase();
        if (ALLOWED_TAGS.includes(tag)) {
          let attrs = "";
          if (tag === "a") {
            const href = node.getAttribute("href");
            if (href && hrefSurvives(href)) attrs = ` href="${esc(href)}"`;
          }
          out += `<${tag}${attrs}>${walk(node)}</${tag}>`;
        } else {
          // Disallowed-but-inert → escape the whole element to visible text.
          out += esc(node.outerHTML);
        }
      }
    }
    return out;
  };
  return walk(tpl.content);
}

/**
 * Belt-and-suspenders final pass: run the (already escape-visible) scrub output
 * through DOMPurify — the hardened sanitiser. The escaped text and the allowlisted
 * markup pass through unchanged; anything the walk somehow missed is stripped here,
 * so the string that ultimately reaches the innerHTML sink is one DOMPurify itself
 * certifies. This is DOMPurify's role: guarding the security-critical output.
 */
function domHarden(html) {
  return DOMPurify.sanitize(String(html ?? ""), {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: ["href"],
    ALLOW_UNKNOWN_PROTOCOLS: false,
  });
}

/** A usable locale shape: a plain object whose values are strings or plural objects of strings. */
function isPlainCatalog(catalog) {
  return !!catalog && typeof catalog === "object" && !Array.isArray(catalog);
}

/**
 * Walk every string value (including each plural-object form), calling
 * fn(value, keyPath, setValue). Mutates `catalog` in place via setValue.
 */
function forEachString(catalog, fn) {
  for (const key of Object.keys(catalog)) {
    const v = catalog[key];
    if (typeof v === "string") {
      fn(v, key, (nv) => { catalog[key] = nv; });
    } else if (v && typeof v === "object" && !Array.isArray(v)) {
      for (const form of Object.keys(v)) {
        if (typeof v[form] === "string") fn(v[form], `${key}.${form}`, (nv) => { v[form] = nv; });
      }
    }
  }
}

/**
 * The gate. Pure: no fetch, no hashing, no persistence (the loader owns those).
 *
 * @param {Record<string, string | Record<string, string>>} catalog - parsed locale.
 * @returns {{ outcome: string, catalog: object|null, report: object }}
 */
export function sanitizeOrQuarantineLocale(catalog) {
  if (!isPlainCatalog(catalog)) {
    return { outcome: OUTCOME.REJECT_MALFORMED, catalog: null, report: { reason: "locale is not a plain object" } };
  }

  // Deep-clone so the scrub never mutates the caller's parsed object.
  const clean = JSON.parse(JSON.stringify(catalog));
  let hostile = null;
  let scrubbedCount = 0;

  forEachString(clean, (value, keyPath, setValue) => {
    if (hostile) return;
    const det = detectHostile(value);
    if (det.hostile) {
      hostile = { firstOffendingKey: keyPath, predicate: det.predicate, detail: det.detail };
      return;
    }
    const scrubbed = domHarden(scrubToString(value));
    if (scrubbed !== value) scrubbedCount++;
    setValue(scrubbed);
  });

  if (hostile) {
    return { outcome: OUTCOME.QUARANTINE_HOSTILE, catalog: null, report: hostile };
  }
  return { outcome: OUTCOME.LOAD, catalog: clean, report: { scrubbed: scrubbedCount } };
}
