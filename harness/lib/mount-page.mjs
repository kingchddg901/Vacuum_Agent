/**
 * Node-side helpers shared by the smoke test and the screenshot CLI.
 * Loads the bundled mount entry into a Playwright page and drives it.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const BUNDLE = join(here, "..", "dist", "mount.js");

const PAGE_HTML =
  `<!doctype html><html><head><meta charset="utf-8"></head>` +
  `<body style="margin:0;background:#0b0d10"><div id="root"></div></body></html>`;

/** Mount a fresh page with #root and the harness bundle loaded. */
export async function mountHarness(page) {
  await page.setContent(PAGE_HTML, { waitUntil: "domcontentloaded" });
  await page.addScriptTag({ content: readFileSync(BUNDLE, "utf8") });
  await page.waitForFunction(() => Boolean(window.__evcc));
}

/** Render one tab in-page and return the serialisable result object. */
export function renderTab(page, view, opts = {}) {
  return page.evaluate(([v, o]) => window.__evcc.render(v, o), [view, opts]);
}

/**
 * Probe #evcc-host's shadow tree for REAL horizontal overflow under the current
 * render — the property gate's measurement.
 *
 * A "culprit" overflows its own box (scrollWidth - clientWidth > tol) AND has a
 * computed `overflow-x: visible` — i.e. it does NOT clip/scroll its own excess,
 * so the overflow escapes upward and forces the card wide. Elements that
 * ellipsize/scroll (overflow-x: hidden/auto/scroll/clip) are INTENTIONAL clips
 * and excluded: that's the allowlist, COMPUTED FROM CSS rather than a
 * hand-maintained class list (the audit's crux — too-broad allowlists never
 * fail, too-narrow ones flag the ~86 deliberate clips). svg/img/canvas/video
 * are skipped (raster/vector boxes, not text layout). Only the DEEPEST element
 * in any overflow chain is kept (ancestors that overflow only because a
 * descendant does are dropped) so each culprit points at the real fix site.
 *
 * @returns {Promise<{shellOverflow:number, culprits:Array<{tag:string,cls:string,ov:number,text:string}>}>}
 */
export function probeLayout(page, { tol = 2 } = {}) {
  return page.evaluate((t) => {
    const host = document.getElementById("evcc-host");
    const root = host && host.shadowRoot;
    if (!root) return { shellOverflow: 0, culprits: [] };
    const SKIP = new Set(["svg", "img", "canvas", "video"]);
    const over = [];
    for (const el of root.querySelectorAll("*")) {
      if (SKIP.has(el.tagName.toLowerCase()) || el.closest("svg")) continue;
      const cw = el.clientWidth;
      if (cw <= 0 || el.scrollWidth - cw <= t) continue;
      if (getComputedStyle(el).overflowX !== "visible") continue; // clips/scrolls → intentional
      over.push(el);
    }
    // Deepest-only: drop any culprit that contains another culprit.
    const leaves = over.filter((el) => !over.some((o) => o !== el && el.contains(o)));
    const culprits = leaves
      .map((el) => {
        const raw = el.className && el.className.baseVal !== undefined
          ? el.className.baseVal : String(el.className || "");
        return {
          tag: el.tagName.toLowerCase(),
          cls: raw.split(/\s+/).filter(Boolean).slice(0, 3).join("."),
          ov: el.scrollWidth - el.clientWidth,
          text: (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 48),
        };
      })
      .sort((a, b) => b.ov - a.ov);
    const shell = root.querySelector(".evcc-shell");
    return { shellOverflow: shell ? shell.scrollWidth - host.clientWidth : 0, culprits };
  }, tol);
}

/**
 * The card's tab set, mirrored from VIEW_ORDER in src/render-cycle.js.
 * (Hardcoded so Node-side tooling needn't import the browser bundle.)
 */
export const VIEW_ORDER = [
  "rooms",
  "maintenance",
  "base_station",
  "metrics",
  "learning_review",
  "room_rules",
  "theme",
  "map_config",
  "mapping_review",
  "setup",
];
