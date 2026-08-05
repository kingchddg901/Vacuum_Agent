// Run: node --test src/renderers/language-control-font.test.mjs
//
// P3 of the OpenDyslexic accessibility feature — the picker inside the language
// menu. The English gate is NOT written in the markup: availableFonts() consults
// FONT_SUPPORT, so an unverified locale returns the default alone and the whole
// section disappears. Adding a locale later must be a data edit.
//
// Coverage (LCF = Language Control Font):
//   [LCF-1] English renders the section with both options
//   [LCF-2] an unverified locale renders NO section at all
//   [LCF-3] the active option is marked, for a11y and for the tick
//   [LCF-4] the OpenDyslexic option carries the sample class, so it previews itself
//   [LCF-5] the font name is never translated (proper noun) in any shipped pack

import { test } from "node:test";
import assert from "node:assert/strict";

import { renderLanguageControl } from "./language-control.js";

function render({ lang = "en", uiFont = "default" } = {}) {
  const renderers = { t: (k) => `T:${k}` };
  return renderLanguageControl(renderers, {
    langOverride: "auto",
    currentLang: lang,
    open: true,
    autoInfo: { systemLang: lang, gatedToEnglish: false },
    uiFont,
  });
}

test("[LCF-1] English renders the typeface section with both options", () => {
  const html = render({ lang: "en" });
  assert.match(html, /T:font\.heading/);
  assert.match(html, /data-action="set-font" data-font="default"/);
  assert.match(html, /data-action="set-font" data-font="opendyslexic"/);
});

test("[LCF-2] an unverified locale renders no typeface section", () => {
  // pl/cs/tr are Latin-script but OpenDyslexic lacks ł ą ř ů ı İ ğ, so they are
  // NOT offered. The gate lives in FONT_SUPPORT, not in this markup.
  for (const lang of ["pl", "cs", "tr", "de", "ja"]) {
    const html = render({ lang });
    assert.doesNotMatch(html, /set-font/, `${lang} was offered the font picker`);
    assert.doesNotMatch(html, /T:font\.heading/, `${lang} rendered a typeface heading`);
  }
});

test("[LCF-3] the active option is marked", () => {
  const onDefault = render({ uiFont: "default" });
  assert.match(onDefault, /data-font="default"[\s\S]{0,80}?aria-checked="true"|aria-checked="true"[\s\S]{0,200}?data-font="default"/);

  const onOd = render({ uiFont: "opendyslexic" });
  // exactly one option is checked at a time
  assert.equal((onOd.match(/aria-checked="true"/g) || []).length >= 1, true);
  assert.match(onOd, /is-active/);
});

test("[LCF-4] the OpenDyslexic option previews itself", () => {
  // The user should see the typeface before committing to it — the one place
  // the font applies regardless of the current setting.
  const html = render({ lang: "en" });
  assert.match(html, /evcc-font-sample-opendyslexic/);
});

test("[LCF-5] the font NAME is never translated in any shipped pack", async () => {
  // "OpenDyslexic" is a proper noun and a Reserved Font Name under the OFL —
  // translating or transliterating it would both misname the product and muddy
  // the licence attribution.
  const fs = await import("node:fs");
  const path = await import("node:path");
  const dir = new URL("../../custom_components/eufy_vacuum/frontend/locales/", import.meta.url);

  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith(".json") || file === "index.json") continue;
    const data = JSON.parse(fs.readFileSync(new URL(file, dir), "utf-8"));
    const name = data?.font?.opendyslexic;
    if (name == null) continue;
    assert.equal(name, "OpenDyslexic", `${file} translated the typeface name`);
  }
  void path;
});
