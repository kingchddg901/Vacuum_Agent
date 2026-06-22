/**
 * ============================================================
 * ANIMAL SVG SANITISER  (the authoritative allowlist pass)
 * ============================================================
 *
 * The SUSPENDERS to animal-descriptor.mjs's quickRejectSvg BELT. The contract
 * gate REJECTS the obvious attacks with clear feedback; this pass takes the
 * SVG that got past it and produces the clean, allowlisted markup that is then
 * codegen'd into animals/<id>.js.
 *
 * WHY A REAL BROWSER (Playwright Chromium), not jsdom:
 *   The framework injects parts.* via innerHTML in a real browser
 *   (animal-svg.js _render). A sanitiser must defend against the SAME parser
 *   that will later run the markup. jsdom's parser differs from a browser's —
 *   that gap is exactly where mutation-XSS hides. So we sanitise with
 *   DOMPurify INSIDE Chromium, against the real parser.
 *
 * Allowlist (tags / attrs / class namespaces) is the single source of truth in
 * animal-descriptor.mjs (SVG_ALLOWLIST). Two hooks tighten DOMPurify further:
 *   - href / xlink:href must be an internal #fragment (drops external refs).
 *   - class is clamped to the framework's animation namespaces (a bad/foreign
 *     class is harmless — shadow-DOM encapsulated — but dropped for tidiness).
 *
 * `DOMPurify.removed` is captured per part so the intake can tell a submitter
 * exactly what was stripped.
 *
 * Exports:
 *   sanitizePartsWithPage(page, parts) — reuse one Playwright page for many
 *     animals (the intake/PR-check path).
 *   sanitizeParts(parts) — standalone: launch + sanitise + close (tests, CLI).
 * ============================================================
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { SVG_ALLOWLIST } from "./animal-descriptor.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const PURIFY_PATH = resolve(HERE, "../node_modules/dompurify/dist/purify.min.js");

/** Inject DOMPurify into the page once. */
async function ensurePurify(page) {
  const present = await page.evaluate(() => typeof window.DOMPurify !== "undefined");
  if (!present) {
    await page.addScriptTag({ content: readFileSync(PURIFY_PATH, "utf8") });
  }
}

/**
 * Sanitise one SVG fragment in the page. Returns { clean, removed } where
 * `removed` is a list of {kind,name} describing what DOMPurify stripped.
 */
export async function sanitizePart(page, svg, allowlist = SVG_ALLOWLIST) {
  await ensurePurify(page);
  return page.evaluate(
    ({ svg, tags, attrs, classAllow }) => {
      const D = window.DOMPurify;
      const allowClasses = new Set(classAllow);
      D.removeAllHooks();
      D.addHook("uponSanitizeAttribute", (node, data) => {
        const n = (data.attrName || "").toLowerCase();
        if (n === "href" || n === "xlink:href") {
          if (!/^#/.test(String(data.attrValue || "").trim())) data.keepAttr = false;
        } else if (n === "class") {
          const kept = String(data.attrValue || "")
            .split(/\s+/)
            .filter((c) => c && allowClasses.has(c));
          data.attrValue = kept.join(" ");
          if (!kept.length) data.keepAttr = false;
        }
      });
      const clean = D.sanitize(svg, {
        ALLOWED_TAGS: tags,
        ALLOWED_ATTR: attrs,
        ALLOW_DATA_ATTR: false,
        ALLOW_ARIA_ATTR: false,
        ALLOW_UNKNOWN_PROTOCOLS: false,
        // Belt-and-suspenders: these are already absent from ALLOWED_TAGS, but
        // naming them makes intent explicit and survives an allowlist edit.
        FORBID_TAGS: ["script", "foreignObject", "image", "iframe", "a", "style", "animate", "animateTransform", "set", "audio", "video"],
        KEEP_CONTENT: false,
        // Parse + sanitise in the SVG namespace, matching how the framework
        // injects the fragment (inside <svg>…</svg>).
        NAMESPACE: "http://www.w3.org/2000/svg",
      });
      // DOMPurify reports its internal parse wrappers (template/body/…) in
      // `removed`; those aren't real content removals, so filter them out.
      const WRAPPERS = new Set(["template", "body", "html", "head", "#document-fragment"]);
      const removed = (D.removed || [])
        .map((r) => {
          if (r.element || r.node) {
            const el = r.element || r.node;
            return { kind: "element", name: (el.nodeName || String(el)).toLowerCase() };
          }
          if (r.attribute) {
            return { kind: "attribute", name: (r.attribute.name || "").toLowerCase(), on: ((r.from && r.from.nodeName) || "").toLowerCase() };
          }
          return { kind: "node", name: "?" };
        })
        .filter((r) => !(r.kind === "element" && WRAPPERS.has(r.name)));
      D.removeAllHooks();
      return { clean, removed };
    },
    {
      svg: String(svg || ""),
      tags: allowlist.tags,
      attrs: allowlist.attrs,
      classAllow: [...allowlist.classAllow],
    },
  );
}

/**
 * Sanitise every part of an animal using an existing page. Returns the cleaned
 * parts plus a per-slot removal report.
 *
 * @returns {Promise<{parts:object, removed:object, changed:boolean}>}
 */
export async function sanitizePartsWithPage(page, parts, allowlist = SVG_ALLOWLIST) {
  const cleanParts = {};
  const removed = {};
  let changed = false;
  for (const [slot, svg] of Object.entries(parts || {})) {
    const { clean, removed: rm } = await sanitizePart(page, svg, allowlist);
    cleanParts[slot] = clean;
    if (rm.length) {
      removed[slot] = rm;
      changed = true;
    }
  }
  return { parts: cleanParts, removed, changed };
}

/**
 * Standalone: launch a headless Chromium, sanitise, close. Convenient for tests
 * and one-off CLI use; the intake should prefer sanitizePartsWithPage to reuse
 * a single browser across many animals.
 */
export async function sanitizeParts(parts, allowlist = SVG_ALLOWLIST) {
  const { chromium } = await import("playwright");
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.setContent("<!doctype html><title>animal-svg sanitiser</title>");
    return await sanitizePartsWithPage(page, parts, allowlist);
  } finally {
    await browser.close();
  }
}

/** Summarise a removal report for an issue/PR comment. */
export function summariseRemovals(removed) {
  const lines = [];
  for (const [slot, items] of Object.entries(removed || {})) {
    const bits = items.map((r) => (r.kind === "attribute" ? `@${r.name}` : `<${r.name}>`));
    lines.push(`- \`parts.${slot}\`: removed ${bits.join(", ")}`);
  }
  return lines.join("\n");
}
