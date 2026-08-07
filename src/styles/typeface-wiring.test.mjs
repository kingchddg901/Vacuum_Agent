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
import { readFileSync, readdirSync } from "node:fs";

const read = (p) => readFileSync(new URL(p, import.meta.url), "utf-8");

test("[TF-1] the card shell reads --evcc-font-family — on a selector that EXISTS", () => {
  // Twice wrong now. First the rule named a font directly (never read the token).
  // Then the token-read was put on .evcc-card — a class NO element carries; the
  // shell frame emits .evcc-shell (main.js). A source-regex test on the rule text
  // passed while the selector matched nothing, so the faces stayed "unloaded"
  // forever: no rendered text ever asked for the family. The read lives on
  // .evcc-shell now; TF-7 asserts the selector is actually emitted.
  const src = read("./shell.js");
  const rule = src.slice(src.indexOf(".evcc-shell {"), src.indexOf(".evcc-shell {") + 900);
  assert.match(rule, /font-family:\s*var\(--evcc-a11y-font-family,\s*var\(--evcc-font-family/,
    ".evcc-shell no longer reads the typeface chain a11y-first — the setting is inert or theme-overridable again");
  // The fallback chain must survive for the default typeface.
  assert.match(rule, /--paper-font-body1_-_font-family/);
});

test("[TF-8] accessibility rides its OWN token, read ahead of the theme's", () => {
  // --evcc-font-family is a THEME_TOKEN_REGISTRY entry ("Font Family") that
  // applyDynamicTheme writes as an INLINE style — inline beats any sheet rule,
  // so a setter targeting the same token loses to the theme no matter where it
  // sits in the STYLES array (found on-device 2026-08-06: a theme carrying
  // Segoe UI/Inter kept OpenDyslexic inert after every other link was fixed).
  // The design: setters write --evcc-a11y-font-family, and every read chains
  // a11y-first — precedence lives in the var() fallback order, no !important.
  const fonts = read("./fonts.js");
  const setter = fonts.slice(fonts.indexOf('[data-evcc-font="opendyslexic"]'));
  assert.match(setter, /--evcc-a11y-font-family:\s*"OpenDyslexic"/,
    "the card-host setter no longer writes the a11y token");
  assert.ok(!/--evcc-font-family:\s*"OpenDyslexic"/.test(fonts),
    "a setter writes the THEME token — inline theme values will override it");

  const idx = read("./index.js");
  for (const host of ["evcc-modal-host", "evcc-toast-host"]) {
    const i = idx.indexOf(`.${host}[data-evcc-font="opendyslexic"]`);
    assert.ok(i > -1, `${host} setter vanished`);
    assert.match(idx.slice(i, i + 500), /--evcc-a11y-font-family:\s*"OpenDyslexic"/,
      `${host} setter no longer writes the a11y token`);
  }
  // Every read that consults the theme token must consult the a11y token FIRST.
  for (const file of ["./index.js", "./foundation.js", "./shell.js", "./theme-preview.js"]) {
    const src = read(file);
    const bare = src.match(/font-family:\s*var\(--evcc-font-family/g) ?? [];
    assert.equal(bare.length, 0,
      `${file}: a font-family read consults the theme token without the a11y token first`);
  }
});

test("[TF-10] no fallback-less var() inside typeface values", () => {
  // The guaranteed-invalid trap (found by local reproduction 2026-08-06):
  // var(--paper-font-body1_-_font-family) with NO fallback, on a setup where
  // the legacy paper var is unset, makes the ENTIRE declaration guaranteed-
  // invalid — the a11y token computes to unset and the whole chain silently
  // falls through to the theme. The rule parses, the selector matches, and
  // nothing anywhere reports an error. Every inner var() in a typeface value
  // must carry a fallback (a comma after the name).
  for (const file of ["./fonts.js", "./index.js", "./shell.js", "./foundation.js", "./theme-preview.js"]) {
    const src = read(file);
    const bare = src.match(/var\(--paper-font-body1_-_font-family\)/g) ?? [];
    assert.equal(bare.length, 0,
      `${file}: var(--paper-font-body1_-_font-family) without a fallback — on a paper-var-less HA this poisons the whole declaration to guaranteed-invalid`);
  }
});

test("[TF-9] the a11y token is NOT a theme token", () => {
  // THEME_TOKEN_REGISTRY is exactly the set applyDynamicTheme writes INLINE
  // from a theme. Registering --evcc-a11y-font-family would hand themes the
  // same inline-override channel TF-8 exists to close — a theme could set the
  // a11y token and beat the accessibility rule again. It must stay a CSS-only
  // token, set solely by the [data-evcc-font] rules, invisible to the editor.
  const dir = new URL("../theme-tokens/", import.meta.url);
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".js") || f.endsWith(".test.mjs")) continue;
    const src = readFileSync(new URL(f, dir), "utf-8");
    assert.ok(!src.includes("--evcc-a11y-font-family"),
      `theme-tokens/${f} registers the a11y font token — themes can now override the accessibility choice inline`);
  }
});

test("[TF-7] the reading selector matches an element the shell frame emits", () => {
  // The reachability half TF-1 was missing: a rule can read the token perfectly
  // and be dead because nothing carries its class. Assert the markup side.
  const main = read("../main.js");
  assert.match(main, /class="evcc-shell"/,
    "the shell frame no longer emits .evcc-shell — the typeface read (and the shell styling) is dead");
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

test("[TF-6] the faces are registered on the DOCUMENT, from every bundle entry", () => {
  // live:FONT-1 — the connection TF-1..TF-5 never asserted. Chromium ignores
  // @font-face inside shadow trees, so a shadow-sheet copy registers nothing;
  // document.fonts.check() cannot catch the gap (it returns true for a family
  // with no registered faces). The face must be injected into document.head,
  // and every bundle entry must perform the (idempotent) injection.
  const fonts = read("./fonts.js");
  assert.match(fonts, /export function ensureFontFacesInDocument/,
    "the document-level registration function vanished");
  assert.match(fonts, /doc\.getElementById\(FONT_FACE_STYLE_ID\)/,
    "the injection lost its idempotence guard");
  assert.match(fonts, /doc\.head\.appendChild\(style\)/,
    "the injection no longer reaches document.head");

  for (const entry of ["../all-cards.js", "../cards-standalone.js", "../cards/vacuum-map-host.js"]) {
    const src = read(entry);
    assert.match(src, /ensureFontFacesInDocument\(\)/,
      `${entry} no longer registers the faces — any surface loaded via that bundle alone renders the fallback forever`);
  }
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
