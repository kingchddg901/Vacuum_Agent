/**
 * Node-side helpers shared by the smoke test and the screenshot CLI.
 * Loads the bundled mount entry into a Playwright page and drives it.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { basename, dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const BUNDLE = join(here, "..", "dist", "mount.js");

const PAGE_HTML =
  `<!doctype html><html><head><meta charset="utf-8"></head>` +
  `<body style="margin:0;background:#0b0d10"><div id="root"></div></body></html>`;

/**
 * The card's @font-face points at /eufy_vacuum/fonts/*.woff2, which Home
 * Assistant serves (registered in __init__.py). The harness is a bare page with
 * no such route, so the request 404s, the face never loads, and everything
 * renders in the fallback.
 *
 * That silently gutted the accessibility case: gallery `rooms-opendyslexic`
 * exists precisely because "OpenDyslexic is wider and heavier than the default,
 * so this is where chip wrapping, queue-row truncation and header fit get to
 * fail visibly" — and its screenshot came out BYTE-IDENTICAL to `rooms-active`
 * (same sha256, same 245099 bytes). A case that cannot differ cannot catch the
 * thing it was written for.
 *
 * Fulfil the request from the shipped woff2 files instead, so the harness
 * renders the same face a real install does.
 */
const FONT_DIR = join(here, "..", "..", "custom_components", "eufy_vacuum",
                      "frontend", "fonts");

async function serveCardFonts(page) {
  await page.route("**/eufy_vacuum/fonts/*", (route) => {
    const name = basename(new URL(route.request().url()).pathname);
    try {
      route.fulfill({
        status: 200,
        contentType: name.endsWith(".woff2") ? "font/woff2" : "text/plain",
        body: readFileSync(join(FONT_DIR, name)),
      });
    } catch {
      // Missing file is a real failure worth SEEING as a fallback render rather
      // than a hang: abort so the page proceeds without the face.
      route.abort();
    }
  });
}

/** Mount a fresh page with #root and the harness bundle loaded. */
export async function mountHarness(page) {
  // A REAL ORIGIN, not setContent's opaque one. This was mountRealCard's fix and
  // it belongs here: with an opaque origin a RELATIVE asset URL like
  // `/eufy_vacuum/fonts/X.woff2` cannot be resolved to a routable request at all
  // — document.fonts.load() rejects with NetworkError — so serveCardFonts above
  // has never once fired for a mountHarness spec. That is why the OpenDyslexic
  // visual baseline was byte-identical to the default-font one: the face was
  // unreachable, so every "typeface" shot rendered the fallback.
  // Routed, not served: no port, no teardown, stable per run.
  await page.route("https://evcc.harness.test/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: PAGE_HTML }));
  // AFTER the catch-all on purpose: Playwright matches the most recently
  // registered route first, so registering the font route second is what lets it
  // win. Registered first, the catch-all above answers the .woff2 with HTML and
  // the face fails to parse — the same NetworkError, one layer along.
  await serveCardFonts(page);
  await page.goto("https://evcc.harness.test/", { waitUntil: "domcontentloaded" });
  await page.addScriptTag({ content: readFileSync(BUNDLE, "utf8") });
  await page.waitForFunction(() => Boolean(window.__evcc));
}

/** Render one tab in-page and return the serialisable result object. */
export function renderTab(page, view, opts = {}) {
  return page.evaluate(([v, o]) => window.__evcc.render(v, o), [view, opts]);
}

/**
 * Mount one STANDALONE Lovelace card (room / dashboard / profile) and return
 * what it rendered. Requires mountHarness first, like renderTab.
 *
 * Not the same path as renderTab: those are the panel's pure renderers driven by
 * a stub state accessor, these are real custom elements driven by a stub hass —
 * see the CARD MOUNT block in mount-entry.js. The returned report carries live
 * counts off the shadow tree (chips / rooms / steps) so a caller can refuse to
 * screenshot a card that mounted empty.
 */
export function mountCard(page, id, opts = {}) {
  return page.evaluate(([i, o]) => window.__evcc.mountCard(i, o), [id, opts]);
}

/** The standalone-card fixture list (id / element / file / label / width). */
export function cardFixtures(page) {
  return page.evaluate(() => window.__evcc.cards);
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
 * are skipped (raster/vector boxes, not text layout).
 *
 * Also excluded: DELIBERATE negative-margin bleeds. An enlarged tap target or a
 * full-bleed row uses a negative L/R margin so its border-box extends past the
 * content edge BY DESIGN — that inflates scrollWidth without clipping any
 * visible content (and an ancestor contains it). When a child's negative margin
 * magnitude ≥ the overflow, the overflow is that bleed, not real content
 * overflow (whose children's positive widths exceed the box), so it is skipped.
 *
 * Only the DEEPEST element in any overflow chain is kept (ancestors that
 * overflow only because a descendant does are dropped) so each culprit points
 * at the real fix site.
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
      const ov = el.scrollWidth - cw;
      if (cw <= 0 || ov <= t) continue;
      if (getComputedStyle(el).overflowX !== "visible") continue; // clips/scrolls → intentional
      // VISUALLY HIDDEN content cannot visually overflow — it is never painted.
      // The visually-hidden idiom (a 1x1 clipped box that keeps its text in the
      // accessibility tree) makes every descendant report a huge scrollWidth
      // against a 1px clientWidth, which is the idiom working, not a defect: no
      // sighted user can see anything cut off, because nothing is shown at all.
      // Detected from LAYOUT rather than a class list, per this probe's own rule
      // that the allowlist is computed from CSS — an ancestor that both clips and
      // has collapsed to <=1px in either axis is hiding, not laying out.
      let hidden = false;
      for (let p = el.parentElement; p; p = p.parentElement) {
        const pcs = getComputedStyle(p);
        if (pcs.overflow !== "visible" && (p.clientWidth <= 1 || p.clientHeight <= 1)) {
          hidden = true;
          break;
        }
      }
      if (hidden) continue;
      // A DESCENDANT whose negative margin ≥ the overflow is a deliberate bleed,
      // not content overflow — skip (see doc above). Scans descendants, not just
      // direct children: the bleed extends past every ancestor up to the one that
      // contains it (e.g. a tap-target's -4px bleeds past both its control row
      // AND the room row), so each of those would otherwise be flagged in turn.
      let bleed = false;
      for (const c of el.querySelectorAll("*")) {
        const ccs = getComputedStyle(c);
        const neg = Math.max(-(parseFloat(ccs.marginLeft) || 0), -(parseFloat(ccs.marginRight) || 0), 0);
        if (neg >= ov - 0.5) { bleed = true; break; }
      }
      if (bleed) continue;
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
 * Elements whose RIGHT EDGE lands past the shell's right edge.
 *
 * probeLayout above asks "does any box hold more than it can show". This asks
 * a different question, and the theme view proved they are not the same one:
 * .evcc-shell is overflow:hidden, so content wider than the card is CLIPPED
 * rather than overflowing anything. The card was visibly cut off at 390px
 * while shellOverflow read 0 and every per-element culprit was a deliberate
 * overhang — a gate can be fully green on a view a user can see is broken.
 *
 * Measured across four states of that view (390 broken, 500 working, and both
 * after the fix) this read 30 / 0 / 0 / 0 while shellOverflow read 0 in all
 * four and the culprit count read 454 in all four. It is the only one of the
 * three that separates broken from working, which is why it is the signal the
 * gate fails on.
 *
 * Only bleed ORIGINS are returned: a box that sticks out while its parent does
 * not. Everything beneath an origin has merely inherited the width and would
 * bury the one line that names the cause.
 *
 * Form controls are excluded — an <input> reports an intrinsic scrollWidth
 * regardless of its container, which is noise for this question.
 */
export function probeBleed(page) {
  return page.evaluate(() => {
    const host = document.getElementById("evcc-host");
    const root = host && host.shadowRoot;
    const shell = root && root.querySelector(".evcc-shell");
    if (!shell) return { shellWidth: 0, total: 0, origins: [] };
    const sr = shell.getBoundingClientRect();
    const past = [];
    for (const el of root.querySelectorAll("*")) {
      if (/^(INPUT|TEXTAREA|SELECT|OPTION)$/.test(el.tagName) || el.closest("svg")) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || r.right <= sr.right + 0.5) continue;
      past.push(el);
    }
    const origins = past
      .filter((el) => !(el.parentElement && past.includes(el.parentElement)))
      .map((el) => {
        const raw = el.className && el.className.baseVal !== undefined
          ? el.className.baseVal : String(el.className || "");
        const r = el.getBoundingClientRect();
        return {
          tag: el.tagName.toLowerCase(),
          cls: raw.split(/\s+/).filter(Boolean).slice(0, 3).join("."),
          past: Math.round((r.right - sr.right) * 10) / 10,
          width: Math.round(r.width),
          text: (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40),
        };
      })
      .sort((a, b) => b.past - a.past);
    return { shellWidth: Math.round(sr.width), total: past.length, origins };
  });
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
  "setup",
];


/**
 * Mount the REAL custom element instead of the synthetic frame. OPT-IN.
 *
 * Use when the thing under test IS the frame — viewport detection, sticky mobile
 * chrome, shell construction, the body-level hosts. For everything else keep using
 * mountHarness + render(): that path can inject arbitrary stub state, this one
 * needs a hass and cannot.
 *
 * `width` drives the ResizeObserver, so it is the knob a mobile-layout test turns.
 */
export async function mountRealCard(page, {
  config = {}, hass = {}, width = null, viewport = null,
  // How the HOST sizes the card. HA panel mode gives a definite height; a normal
  // dashboard card gives none, and the difference decides whether the mobile shell
  // can fill and pin its nav. Default models panel mode; pass "auto" to model a
  // height-less host deliberately.
  hostHeight = "100dvh",
} = {}) {
  if (viewport) await page.setViewportSize(viewport);

  // A REAL ORIGIN first. setContent() alone leaves the page on an opaque origin,
  // where localStorage throws SecurityError — and the card reads it during mount
  // (map view state, label anchors, floor textures). The synthetic path never
  // noticed because it drives the renderers directly and never mounts the element.
  // Routed, not served: no port, no teardown, and the origin is stable per run so
  // localStorage persists across mounts within one test the way it does in HA.
  await page.route("https://evcc.harness.test/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><html><body></body></html>" }));
  await page.goto("https://evcc.harness.test/", { waitUntil: "domcontentloaded" });

  await mountHarness(page);
  return page.evaluate(
    (o) => window.__evcc.mountRealCard(o),
    { config, hass, width, hostHeight },
  );
}
