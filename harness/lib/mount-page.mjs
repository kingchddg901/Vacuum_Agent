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
