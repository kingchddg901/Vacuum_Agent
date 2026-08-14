/**
 * ============================================================
 * I18N ENTITY-LEAK GATE — the string reached the screen ESCAPED
 * ============================================================
 *
 * WHAT IT CATCHES. `translate()` HTML-escapes every catalog string by default
 * (Trust Model B — a contributed value must never reach an innerHTML sink raw).
 * A renderer that then calls `escapeHtml(this.t(...))` escapes it a SECOND
 * time, and the user reads the entity instead of the character:
 *
 *     d&#39;apprentissage        (should be d'apprentissage)
 *     Aujourd&#39;hui            (should be Aujourd'hui)
 *
 * Found on the maintainer's live panel in French, on the metrics view, five
 * occurrences on one screen.
 *
 * WHY A DOM SWEEP RATHER THAN A GREP. Grepping for `escapeHtml(this.t(` finds
 * the direct sites and MISSES the indirect ones, which is most of them: the
 * metrics window card takes a `title` argument and escapes it, and every caller
 * passes `this.t(...)`. The double escape happens one stack frame from anything
 * a grep can see. Reading the rendered text finds the leak wherever it came
 * from, and cannot be fooled by a new indirection.
 *
 * WHY FRENCH IS THE PRIMARY LOCALE HERE. The bug is invisible in English, which
 * has almost no apostrophes in UI copy. French has one in nearly every other
 * string ("d'apprentissage", "Aujourd'hui", "l'aspirateur"), so it is the
 * locale that makes an escaping regression obvious. Italian and Catalan share
 * the property; German and Russian mostly do not.
 *
 * SCOPE: the POPULATED fixtures, because an empty view renders no catalog
 * strings worth checking — the same hole the layout gate above had to close.
 */

import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { mountHarness } from "../lib/mount-page.mjs";

const LOCALE_DIR = new URL(
  "../../custom_components/eufy_vacuum/frontend/locales",
  import.meta.url,
).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const CATALOGUES = {};
function catalogue(code) {
  if (!CATALOGUES[code]) {
    CATALOGUES[code] = JSON.parse(readFileSync(`${LOCALE_DIR}/${code}.json`, "utf8"));
  }
  return CATALOGUES[code];
}

/** Entities that mean a string was escaped twice. */
const LEAK_RE = /&(#x?[0-9a-fA-F]+|amp|quot|apos|lt|gt|nbsp);/g;

// EVERY bundled locale. The bug is not French-specific — any catalog string
// containing an apostrophe, quote or ampersand leaks when escaped twice, and
// English UI copy has them too ("Today's", "vacuum's"). French merely makes it
// unmissable. Running the full set is cheap and tells us the real blast radius.
const LOCALES = [
  "en", "fr", "it", "es", "pt", "de", "nl", "pl", "cs", "tr",
  "id", "ru", "ja", "ko", "zh-Hans", "zh-Hant", "ar", "he",
];

/** Same fixture set the layout gate uses — real data, not the null-object stub. */
const POPULATED = [
  ["rooms", "rooms-active"],
  ["room_rules", "room-rules"],
  ["metrics", "metrics-overview"],
  ["learning_review", "review-badges"],
  ["maintenance", "maintenance"],
  ["rooms+profiles", "run-profiles-unsupported-break"],
];

// The catalogue must be FLATTENED before it is registered — the nested JSON is
// not the shape translate() reads. My first version registered it raw, the
// locale never landed, and all twelve assertions passed against English while
// also reading the stylesheet. Green for two independent wrong reasons.
async function seedLocale(page, code) {
  const keys = await page.evaluate(
    ([c, cat]) => {
      const { flat } = window.__evcc.flattenLocale(cat, window.__evcc.en);
      window.__evcc.registerLocale(c, flat);
      return Object.keys(flat || {}).length;
    },
    [code, catalogue(code)],
  );
  expect(keys, `${code} catalogue failed to flatten (gate would read English)`)
    .toBeGreaterThan(2000);
}

test.describe("i18n entity-leak gate", () => {
  for (const [view, fixture] of POPULATED) {
    for (const lang of LOCALES) {
      test(`${view} [${lang}] renders characters, not entities`, async ({ page }) => {
        await mountHarness(page);
        // English is the BASE catalogue (src/i18n/en.js) and has no locale
        // JSON to seed — it renders without registration.
        if (lang !== "en") await seedLocale(page, lang);

        const res = await page.evaluate(
          ([id, o]) => window.__evcc.renderGallery(id, o),
          [fixture, { width: 900, freeze: true, lang }],
        );
        expect(res.ok, res.error).toBe(true);

        // Exclude <style>: the stylesheet is ~390k chars of CSS whose COMMENTS
        // are English prose full of apostrophes ("theme's", "card's"). Reading
        // it made the first version of this gate pass on CSS instead of UI.
        const text = await page.evaluate(() => {
          const root = document.getElementById("evcc-host").shadowRoot;
          let out = "";
          root.querySelectorAll("*").forEach((el) => {
            const tag = el.tagName.toLowerCase();
            if (tag === "style" || tag === "script") return;
            el.childNodes.forEach((n) => {
              if (n.nodeType === Node.TEXT_NODE) out += n.nodeValue + " ";
            });
          });
          return out;
        });

        // Guard the fixture itself: a view that rendered nothing would pass
        // this gate while measuring nothing at all.
        expect(
          text.trim().length,
          `${fixture} [${lang}] rendered no text — this gate is measuring an empty box`,
        ).toBeGreaterThan(200);

        // Prove the TRANSLATION reached the screen. Registering a catalogue and
        // still rendering English is exactly how this gate first shipped green.
        // English is the base catalogue, so there is nothing to prove landed.
        if (lang !== "en") {
          const foreign = [...text].filter((c) => c.charCodeAt(0) > 127).length;
          expect(
            foreign,
            `${fixture} [${lang}]: only ASCII rendered — the locale did not reach ` +
              `the DOM, so an escaping regression would pass unnoticed`,
          ).toBeGreaterThan(0);
        }

        const hits = text.match(LEAK_RE) || [];
        const snippets = [];
        const ctx = /[^\s]{0,26}&(?:#x?[0-9a-fA-F]+|amp|quot|apos|lt|gt|nbsp);[^\s]{0,26}/g;
        let m;
        while ((m = ctx.exec(text)) && snippets.length < 6) snippets.push(m[0]);

        expect(
          hits.length,
          `${fixture} [${lang}]: ${hits.length} HTML entit(ies) reached the screen as text — ` +
            `a catalog string was escaped twice.\n      ` +
            snippets.join("\n      "),
        ).toBe(0);
      });
    }
  }
});
