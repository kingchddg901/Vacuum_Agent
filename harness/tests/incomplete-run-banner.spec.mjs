/**
 * THE INCOMPLETE-RUN BANNER under a wide font and a long locale.
 *
 * ⚠ REPORTED FROM A PHONE, in two languages, as two symptoms of ONE defect:
 *
 *   EN + OpenDyslexic — "Last run cancelled — 1 room missed" collapsed into
 *     "Last / run / cancelled / — / 1 / room / missed", one word per line, in a
 *     sliver beside the button.
 *   FR + OpenDyslexic — the same banner pushed the page WIDER THAN THE VIEWPORT.
 *     Confirmed by scrolling sideways to reach content clipped off both edges.
 *
 * The mechanism is the CSS, and it only has one bug in it:
 *
 *     .evcc-incomplete-run-banner  { display:flex; gap:12px; }   // no flex-wrap
 *     .evcc-incomplete-run-body    { flex:1; min-width:0; }      // starves to zero
 *     .evcc-incomplete-run-actions { flex-shrink:0; }            // never shrinks
 *
 * The actions take whatever they need and the body absorbs the entire shortfall.
 * Which symptom you get depends only on whether the actions still fit: if they do,
 * the body starves; if they do not, the banner overflows. French decides that,
 * because `learning.queue_missed_rooms` is "Mettre en file les pièces manquées" —
 * 34 characters against English's 18 — and OpenDyslexic is roughly 1.66x Arial.
 *
 * WHY NEITHER EXISTING GATE CAUGHT IT:
 *   * `probeLayout` is blind to starvation BY CONSTRUCTION — a starved flex item
 *     plus overflow-wrap degrades vertically and overflows nothing. The i18n layout
 *     gate says so in its own comments, and added a line-count check for the
 *     maintenance CARDS for exactly this reason. This banner never got one.
 *   * The layout gate sweeps locales, but in the DEFAULT font. The hero shooter
 *     renders OpenDyslexic, but is a shooter, not a gate. Nothing crossed the two,
 *     and the defect lives precisely in the crossing.
 *
 * So this asserts BOTH symptoms, because fixing one and not the other is how this
 * bug survives: line count for the starve, probeLayout for the overflow.
 */
import { readFileSync } from "node:fs";

import { test, expect } from "@playwright/test";

import { mountHarness, probeLayout } from "../lib/mount-page.mjs";

const LOCALE_DIR = "custom_components/eufy_vacuum/frontend/locales";
const catalogue = (code) => JSON.parse(readFileSync(`${LOCALE_DIR}/${code}.json`, "utf8"));

/** Seed a real locale, and PROVE it landed — an empty catalogue renders English. */
async function seedLocale(page, code) {
  const keys = await page.evaluate(
    ([c, cat]) => {
      const { flat } = window.__evcc.flattenLocale(cat, window.__evcc.en);
      window.__evcc.registerLocale(c, flat);
      return Object.keys(flat || {}).length;
    },
    [code, catalogue(code)],
  );
  expect(keys, `${code} catalogue failed to flatten — the gate would render English`)
    .toBeGreaterThan(2000);
}

/**
 * Render the Rooms view with the banner present.
 *
 * The four accessors are built IN-PAGE: a function cannot survive page.evaluate's
 * structured clone, and without them `hasIncompleteRunLog()` returns the stub's
 * null-object, which is truthy — so the banner would render with an EMPTY title and
 * the line-count assertion would pass on nothing.
 */
function renderBanner(page, { lang, font, width }) {
  return page.evaluate(
    ([lg, ft, w]) => {
      const res = window.__evcc.render("rooms", {
        width: w,
        freeze: true,
        mobile: true,
        ...(lg ? { lang: lg } : {}),
        ...(ft ? { font: ft } : {}),
        overrides: {
          // Without rooms the Rooms view returns its EMPTY state and never reaches
          // the banner at all — the first cut of this spec asserted against a view
          // that had bailed 100 lines earlier.
          getRoomsForActiveMap: () => ([
            { room_id: 1, name: "KITCHEN", enabled: true, order: 1 },
            { room_id: 2, name: "LIVINGROOM", enabled: true, order: 2 },
          ]),
          hasIncompleteRunLog: () => true,
          learningJobActive: () => false,
          incompleteRunLog: () => ({ outcome_status: "cancelled" }),
          incompleteRunMissedRooms: () => [{ name: "KITCHEN" }],
        },
      });
      const root = document.getElementById("evcc-host")?.shadowRoot;
      const title = root?.querySelector(".evcc-incomplete-run-title") ?? null;
      if (!title) return { ok: res.ok, error: res.error, title: null };

      const cs = getComputedStyle(title);
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
      const r = title.getBoundingClientRect();
      return {
        ok: res.ok,
        error: res.error,
        title: {
          text: title.textContent.trim().slice(0, 60),
          width: Math.round(r.width),
          lines: Math.round(r.height / lh),
        },
      };
    },
    [lang, font, width],
  );
}

/* The reported combinations, plus the default font as a control. OpenDyslexic is
   the one that bites: it is ~1.66x Arial by rendered width, which is why the same
   markup survives in one font and fails in the other. */
const CASES = [
  { lang: null, font: null,           label: "en / default" },
  { lang: null, font: "opendyslexic", label: "en / OpenDyslexic" },
  { lang: "fr", font: "opendyslexic", label: "fr / OpenDyslexic" },
  { lang: "de", font: "opendyslexic", label: "de / OpenDyslexic" },
];

for (const VW of [360, 390]) {
test.describe(`incomplete-run banner @${VW}px`, () => {
  test.use({ viewport: { width: VW, height: 844 } });

  for (const c of CASES) {
    test(`${c.label}: neither starves nor overflows`, async ({ page }) => {
      await mountHarness(page);
      if (c.lang) await seedLocale(page, c.lang);
      const res = await renderBanner(page, { lang: c.lang, font: c.font, width: VW });

      expect(res.ok, res.error).toBe(true);
      expect(res.title, "the banner did not render — the accessor overrides stopped working").not.toBeNull();

      // SYMPTOM ONE — the starve. Line count, not a width threshold: a width
      // threshold restates whatever the CSS happens to say, while "seven lines for
      // a one-line sentence" is true independent of the implementation. The
      // reported English case was 7.
      expect(
        res.title.lines,
        `title starved into a word-per-line column (${res.title.lines} lines): "${res.title.text}"`,
      ).toBeLessThanOrEqual(3);

      // SYMPTOM TWO — the overflow. Same predicate the i18n layout gate uses,
      // pointed at the case that produced it.
      const { shellOverflow, culprits } = await probeLayout(page);
      const list = culprits.map((x) => `      +${x.ov}px  ${x.tag}.${x.cls}  "${x.text}"`).join("\n");
      expect(culprits.length, `${c.label}: ${culprits.length} element(s) overflow their box:\n${list}`).toBe(0);
      expect(shellOverflow, `${c.label}: card forces ${shellOverflow}px of horizontal scroll`).toBeLessThanOrEqual(2);
    });
  }
});
}
