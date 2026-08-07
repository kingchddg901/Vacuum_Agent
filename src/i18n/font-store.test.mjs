// Run: node --test src/i18n/font-store.test.mjs
//
// Coverage (FS = Font Store):
//   [FS-1]  the coverage GATE reads FONT_SUPPORT, never a hardcoded "en"
//   [FS-2]  a region tag resolves against its base ("en-GB" -> "en")
//   [FS-3]  an unverified locale is REFUSED even when it is Latin-script
//   [FS-4]  availableFonts always includes the default
//   [FS-5]  a stored font is validated on READ, not just on write
//   [FS-6]  writing merges — ui_language survives
//   [FS-7]  choosing the default DELETES the field rather than storing "default"
//   [FS-8]  an unknown font is refused, and a dead connection never throws

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  FONT_DEFAULT,
  FONT_SUPPORT,
  availableFonts,
  fontSupportsLang,
  getStoredFont,
  setStoredFont,
} from "./font-store.js";

function fakeHass(stored) {
  const calls = [];
  return {
    calls,
    callWS: async (msg) => {
      calls.push(msg);
      if (msg.type === "frontend/get_user_data") return { value: stored };
      return true;
    },
  };
}

test("[FS-1] the gate reads FONT_SUPPORT rather than a hardcoded locale", () => {
  assert.equal(fontSupportsLang("opendyslexic", "en"), true);
  assert.ok(FONT_SUPPORT.opendyslexic instanceof Set, "the generic shape is the contract");
  assert.equal(fontSupportsLang("not_a_font", "en"), false);
});

test("[FS-2] a region tag resolves against its base", () => {
  assert.equal(fontSupportsLang("opendyslexic", "en-GB"), true);
  assert.equal(fontSupportsLang("opendyslexic", "EN"), true);
});

test("[FS-3] an unverified locale is refused even when it is Latin-script", () => {
  // The whole point of the gate: FONT_SUPPORT is a WHITELIST of locales whose
  // shipped catalogue has been PROVEN covered, never an inference from script
  // family.
  //
  // This test used to make that point with pl/cs/tr on the premise that
  // OpenDyslexic lacked ł ą ř ů ı İ ğ. That premise was measured against the
  // wrong release and is false — the shipped Regular/Bold carry all of them
  // (1586 codepoints), so those three are now proven and supported.
  //
  // The doctrine outlived its example. These locales make the same point more
  // sharply: sv/hu/vi are Latin-script AND the font would render them fine (the
  // cmap carries å ä ö, ő ű, ơ ư ạ) — they are refused purely because nobody has
  // proven them against a shipped catalogue. Coverage is not the criterion;
  // proof is. ja/ar are the easy case: absent from the cmap outright.
  for (const lang of ["sv", "hu", "vi", "ja", "ar"]) {
    assert.equal(fontSupportsLang("opendyslexic", lang), false, `${lang} was offered unverified`);
  }
});

test("[FS-4] availableFonts always includes the default", () => {
  // pl is on the proven list as of the 2026-08-06 cmap verification — it takes
  // the both-options branch now. he is the genuinely-absent case (zero Hebrew
  // codepoints in the shipped font), so it must fall back to default-only.
  assert.deepEqual(availableFonts("en"), [FONT_DEFAULT, "opendyslexic"]);
  assert.deepEqual(availableFonts("pl"), [FONT_DEFAULT, "opendyslexic"]);
  assert.deepEqual(availableFonts("he"), [FONT_DEFAULT]);
  assert.deepEqual(availableFonts(""), [FONT_DEFAULT]);
});

test("[FS-5] a stored font is validated on READ", async () => {
  // A value edited directly in storage, or left by a release that offered a font
  // this one does not, must not reach the DOM as an attribute nothing styles.
  assert.equal(await getStoredFont(fakeHass({ ui_font: "opendyslexic" })), "opendyslexic");
  assert.equal(await getStoredFont(fakeHass({ ui_font: "comic_sans" })), FONT_DEFAULT);
  assert.equal(await getStoredFont(fakeHass({})), FONT_DEFAULT);
  assert.equal(await getStoredFont(fakeHass(null)), FONT_DEFAULT);
});

test("[FS-6] writing merges — the language preference survives", async () => {
  const hass = fakeHass({ ui_language: "de" });
  assert.equal(await setStoredFont(hass, "opendyslexic"), true);

  const write = hass.calls.find((c) => c.type === "frontend/set_user_data");
  assert.deepEqual(write.value, { ui_language: "de", ui_font: "opendyslexic" });
});

test("[FS-7] choosing the default DELETES the field", async () => {
  // Absence already means "use the theme font". Storing "default" as well would
  // be two representations of one state, which is how they drift apart.
  const hass = fakeHass({ ui_language: "de", ui_font: "opendyslexic" });
  assert.equal(await setStoredFont(hass, FONT_DEFAULT), true);

  const write = hass.calls.find((c) => c.type === "frontend/set_user_data");
  assert.deepEqual(write.value, { ui_language: "de" });
  assert.ok(!("ui_font" in write.value));
});

test("[FS-8] an unknown font is refused, and a dead connection never throws", async () => {
  const hass = fakeHass({});
  assert.equal(await setStoredFont(hass, "comic_sans"), false);
  assert.equal(hass.calls.filter((c) => c.type === "frontend/set_user_data").length, 0);

  assert.equal(await setStoredFont({}, "opendyslexic"), false);
  assert.equal(await getStoredFont({}), FONT_DEFAULT);
  assert.equal(await getStoredFont(undefined), FONT_DEFAULT);
});
