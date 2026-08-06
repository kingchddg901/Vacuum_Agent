// Run: node --test src/styles/typeface-wiring.test.mjs
//
// The accessibility typeface shipped 2026-08-04 and never applied anywhere. Not
// the font file (served 200, valid woff2) and not the @font-face (document.fonts
// .check('12px OpenDyslexic') === true on the live box). The token was set by a
// rule nothing read, and read by two rules that could not see it:
//
//   styles/fonts.js      :host([data-evcc-font]) { --evcc-font-family: … }
//   foundation.js        .evcc-card { font-family: var(--paper-font-…) }  <- ignored it
//   index.js  (x2)       .evcc-modal-host / .evcc-toast-host read the token —
//                        but both are document.body children and cannot inherit
//                        a custom property declared on the card's :host.
//
// Nothing caught it because every rule was individually valid. These assert the
// CONNECTIONS instead.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(p, import.meta.url), "utf-8");

test("[TF-1] the card shell reads --evcc-font-family", () => {
  // The one that was wrong. .evcc-card is what every surface inherits from, so
  // if it names a font directly the typeface setting is inert card-wide.
  const src = read("./foundation.js");
  const rule = src.slice(src.indexOf(".evcc-card {"), src.indexOf(".evcc-card {") + 900);
  assert.match(rule, /font-family:\s*var\(--evcc-font-family/,
    ".evcc-card no longer reads the typeface token — the setting is inert again");
  // The fallback chain must survive for the default typeface.
  assert.match(rule, /--paper-font-body1_-_font-family/);
});

test("[TF-2] the token is declared for BOTH the shadow host and the body hosts", () => {
  // Declared in fonts.js for the card, and re-declared in the body-host sheets
  // because those cannot inherit it. Losing either half breaks one surface.
  assert.match(read("./fonts.js"), /:host\(\[data-evcc-font="opendyslexic"\]\)/);

  const idx = read("./index.js");
  assert.match(idx, /\.evcc-modal-host\[data-evcc-font="opendyslexic"\]/,
    "modals will not follow the card's typeface");
  assert.match(idx, /\.evcc-toast-host\[data-evcc-font="opendyslexic"\]/,
    "toasts will not follow the card's typeface");
});

test("[TF-3] the attribute is stamped on the body hosts, not just the card", () => {
  // A rule keyed to [data-evcc-font] is dead unless something sets the attribute
  // on those hosts — they are created in document.body, outside the card.
  const main = read("../main.js");
  const stamps = main.match(/_applyFontAttributeTo\(/g) ?? [];
  assert.ok(stamps.length >= 4,
    `expected the stamp helper plus three call sites, found ${stamps.length}`);
  assert.match(main, /_applyFontAttributeTo\(this\._modalHost\)/);
  assert.match(main, /_applyFontAttributeTo\(this\._toastHost\)/);
});

test("[TF-4] @font-face still points at the served path, not a CDN", () => {
  const src = read("./fonts.js");
  // The path is composed from a constant, so assert the constant AND its use —
  // checking the resolved string would pass on a file that never interpolates it.
  assert.match(src, /const FONT_BASE = "\/eufy_vacuum\/fonts";/,
    "the served base path moved — __init__.py registers exactly this route");
  assert.match(src, /url\("\$\{FONT_BASE\}\/OpenDyslexic-Regular\.woff2"\)/);
  assert.match(src, /url\("\$\{FONT_BASE\}\/OpenDyslexic-Bold\.woff2"\)/);

  // Same-origin only: no external fetch, a stated design constraint. Strip the
  // block comment first — the OFL notice legitimately carries the author's URL,
  // and the licence text must travel with the font.
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "");
  assert.ok(!/https?:\/\//.test(code),
    "an external font URL appeared — the files ship inside the HACS package");
});

test("[TF-5] the picker's own sample renders in the font unconditionally", () => {
  // It must show the typeface BEFORE it is selected, so it cannot go through the
  // token — that would only resolve once the setting is already on.
  const src = read("./fonts.js");
  const i = src.indexOf(".evcc-font-sample-opendyslexic");
  assert.ok(i > -1, "the preview class vanished");
  const rule = src.slice(i, i + 200);
  assert.match(rule, /font-family:\s*"OpenDyslexic"/);
  assert.ok(!/var\(--evcc-font-family/.test(rule),
    "the sample went through the token — it would stop previewing when off");
});
