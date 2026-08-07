// Run: node --test src/styles/typeface-wiring.test.mjs
//
// The accessibility typeface shipped 2026-08-04 and never applied anywhere —
// then survived TWO more fix rounds (live:FONT-1, closed 2026-08-06) because
// every rule involved was individually valid and nothing asserted the
// CONNECTIONS. The four failure classes, each with its pin below:
//   - faces registered only in a shadow tree (Chromium ignores them)  -> TF-6
//   - the token READ on a selector no element carries                  -> TF-7
//   - the theme's inline Font Family token outranking the sheet rule   -> TF-8/9
//   - a fallback-less var() poisoning the setter to guaranteed-invalid -> TF-10
//
// Since the CSS is now GENERATED from FONT_DEFS, these tests assert on the
// BUILT strings (imported), not source regexes — a source regex can pass while
// the built CSS is wrong, and the built CSS is what ships.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { FONT_DEFS, FONT_FACE_CSS, FONT_STACK_PRESETS, fontStyles, fontTokenRules } from "./fonts.js";
import { MODAL_HOST_STYLES, TOAST_HOST_STYLES } from "./index.js";
import { FONT_SUPPORT } from "../i18n/font-store.js";

const read = (p) => readFileSync(new URL(p, import.meta.url), "utf-8");

test("[TF-1] the card shell reads the typeface chain — on a selector that EXISTS", () => {
  // Twice wrong historically: first the rule named a font directly; then the
  // token-read sat on .evcc-card — a class NO element carries (the shell frame
  // emits .evcc-shell). TF-7 asserts the markup side of this.
  const src = read("./shell.js");
  const rule = src.slice(src.indexOf(".evcc-shell {"), src.indexOf(".evcc-shell {") + 900);
  assert.match(rule, /font-family:\s*var\(--evcc-a11y-font-family,\s*var\(--evcc-font-family/,
    ".evcc-shell no longer reads the typeface chain a11y-first — the setting is inert or theme-overridable again");
  assert.match(rule, /--paper-font-body1_-_font-family/);
});

test("[TF-2] every font's token is declared for the shadow host AND both body hosts", () => {
  // Body hosts live on document.body and cannot inherit a token declared on
  // the card's :host — each surface needs its own generated setter rule.
  for (const def of FONT_DEFS) {
    assert.match(fontStyles, new RegExp(`:host\\(\\[data-evcc-font="${def.id}"\\]\\)`),
      `${def.id}: no shadow-host setter in fontStyles`);
    assert.ok(MODAL_HOST_STYLES.includes(`.evcc-modal-host[data-evcc-font="${def.id}"]`),
      `${def.id}: modals will not follow the card's typeface`);
    assert.ok(TOAST_HOST_STYLES.includes(`.evcc-toast-host[data-evcc-font="${def.id}"]`),
      `${def.id}: toasts will not follow the card's typeface`);
  }
});

test("[TF-3] the attribute is stamped on the body hosts, not just the card", () => {
  const main = read("../main.js");
  const stamps = main.match(/_applyFontAttributeTo\(/g) ?? [];
  assert.ok(stamps.length >= 4,
    `expected the stamp helper plus three call sites, found ${stamps.length}`);
  assert.match(main, /_applyFontAttributeTo\(this\._modalHost\)/);
  assert.match(main, /_applyFontAttributeTo\(this\._toastHost\)/);
});

test("[TF-4] every declared face resolves to the served path, no CDN anywhere", () => {
  for (const def of FONT_DEFS) {
    for (const face of def.faces) {
      assert.ok(FONT_FACE_CSS.includes(`url("/eufy_vacuum/fonts/${face.file}")`),
        `${def.id}/${face.file}: face does not point at the served path __init__.py registers`);
    }
  }
  // Same-origin only: the files ship inside the HACS package.
  assert.ok(!/https?:\/\//.test(FONT_FACE_CSS),
    "an external font URL appeared in the generated faces");
});

test("[TF-5] every font's picker sample renders in that font unconditionally", () => {
  // The sample must show the typeface BEFORE it is selected, so it cannot go
  // through the a11y token — that only resolves once the setting is on.
  for (const def of FONT_DEFS) {
    const i = fontStyles.indexOf(`.evcc-font-sample-${def.id}`);
    assert.ok(i > -1, `${def.id}: preview class missing from generated styles`);
    const rule = fontStyles.slice(i, i + 250);
    assert.match(rule, new RegExp(`font-family:\\s*"${def.family}"`),
      `${def.id}: sample does not lead with its own family`);
    assert.ok(!/var\(--evcc-a11y-font-family/.test(rule),
      `${def.id}: sample went through the a11y token — it would stop previewing when off`);
  }
});

test("[TF-6] the faces are registered on the DOCUMENT, from every bundle entry", () => {
  const fonts = read("./fonts.js");
  assert.match(fonts, /export function ensureFontFacesInDocument/);
  assert.match(fonts, /doc\.getElementById\(FONT_FACE_STYLE_ID\)/,
    "the injection lost its idempotence guard");
  assert.match(fonts, /doc\.head\.appendChild\(style\)/,
    "the injection no longer reaches document.head");
  for (const entry of ["../all-cards.js", "../cards-standalone.js", "../cards/vacuum-map-host.js"]) {
    assert.match(read(entry), /ensureFontFacesInDocument\(\)/,
      `${entry} no longer registers the faces — any surface loaded via that bundle alone renders the fallback forever`);
  }
  // The HARNESS entry is listed here deliberately, even though it ships nothing.
  // This assertion covered only the three ship entries, so when mount-entry.js
  // stamped data-evcc-font WITHOUT registering the faces, nothing complained —
  // and gallery-rooms-opendyslexic.png was byte-identical to the default-font
  // baseline (both sha256 16f6440f…), a typeface gate that could never fail.
  // A measuring instrument that cannot render the thing it measures is the same
  // defect class as an unregistered face, one level up.
  assert.match(read("../../harness/mount-entry.js"), /ensureFontFacesInDocument\(\)/,
    "the render harness no longer registers the faces — every typeface baseline silently becomes a default-font baseline");
});

test("[TF-7] the reading selector matches an element the shell frame emits", () => {
  // The reachability half: a rule can read the token perfectly and be dead
  // because nothing carries its class. Assert the markup side.
  assert.match(read("../main.js"), /class="evcc-shell"/,
    "the shell frame no longer emits .evcc-shell — the typeface read (and the shell styling) is dead");
});

test("[TF-8] accessibility rides its OWN token, read ahead of the theme's", () => {
  // --evcc-font-family is a THEME_TOKEN_REGISTRY entry that applyDynamicTheme
  // writes INLINE — inline beats any sheet rule, so a setter targeting the
  // theme token loses to the theme regardless of STYLES-array position.
  // Setters write ONLY the a11y token; reads chain a11y-first; no !important.
  const setterBlock = fontTokenRules((id) => `.probe-${id}`);
  for (const def of FONT_DEFS) {
    assert.ok(setterBlock.includes(`.probe-${def.id}`), `${def.id}: no generated setter`);
  }
  assert.match(setterBlock, /--evcc-a11y-font-family:/);
  assert.ok(!setterBlock.includes("--evcc-font-family:"),
    "a generated setter writes the THEME token — inline theme values will override it");
  // Every read that consults the theme token must consult the a11y token FIRST.
  for (const file of ["./index.js", "./foundation.js", "./shell.js", "./theme-preview.js"]) {
    const bare = read(file).match(/font-family:\s*var\(--evcc-font-family/g) ?? [];
    assert.equal(bare.length, 0,
      `${file}: a font-family read consults the theme token without the a11y token first`);
  }
});

test("[TF-9] the a11y token is NOT a theme token", async () => {
  // THEME_TOKEN_REGISTRY is exactly the set applyDynamicTheme writes INLINE
  // from a theme. Registering --evcc-a11y-font-family would hand themes the
  // same override channel TF-8 closes. CSS-only, editor-invisible, forever.
  const { readdirSync } = await import("node:fs");
  const dir = new URL("../theme-tokens/", import.meta.url);
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".js") || f.endsWith(".test.mjs")) continue;
    const src = readFileSync(new URL(f, dir), "utf-8");
    assert.ok(!src.includes("--evcc-a11y-font-family"),
      `theme-tokens/${f} registers the a11y font token — themes can override the accessibility choice inline`);
  }
});

test("[TF-10] no fallback-less var() inside any font stack", () => {
  // The guaranteed-invalid trap: var(--x) with NO fallback, where --x is
  // unset, makes the ENTIRE declaration guaranteed-invalid — the rule parses,
  // the selector matches, the token computes to unset, and nothing reports an
  // error. Every inner var() in every stack must carry a fallback.
  for (const def of FONT_DEFS) {
    const bare = def.stack.match(/var\((--[\w-]+)\)/g) ?? [];
    assert.deepEqual(bare, [],
      `${def.id}: fallback-less var() in stack (${bare.join(", ")}) — poisons the declaration to guaranteed-invalid where unset`);
  }
  for (const preset of FONT_STACK_PRESETS) {
    const bare = preset.stack.match(/var\((--[\w-]+)\)/g) ?? [];
    assert.deepEqual(bare, [],
      `preset ${preset.id}: fallback-less var() in stack — a theme applying this chip breaks where the var is unset`);
  }
  for (const file of ["./fonts.js", "./index.js", "./shell.js", "./foundation.js", "./theme-preview.js"]) {
    const bare = read(file).match(/var\(--paper-font-body1_-_font-family\)/g) ?? [];
    assert.equal(bare.length, 0,
      `${file}: var(--paper-font-body1_-_font-family) without a fallback`);
  }
});

test("[TF-11] FONT_DEFS and FONT_SUPPORT agree on the font ids", () => {
  // fonts.js owns the CSS half, font-store.js owns the offering/persistence
  // half. An id in one but not the other is a font that either renders but
  // can't be chosen, or can be chosen but never renders.
  const cssIds = FONT_DEFS.map((d) => d.id).sort();
  const storeIds = Object.keys(FONT_SUPPORT).sort();
  assert.deepEqual(cssIds, storeIds,
    "FONT_DEFS (CSS side) and FONT_SUPPORT (store side) list different fonts");
});

test("[TF-13] every shipped card font is offered as a theme Font Family chip", () => {
  // FONT_STACK_PRESETS appends FONT_DEFS automatically — a new card font must
  // surface in the theme editor with zero extra wiring. If this fails, the
  // spread was removed and new fonts silently stop appearing as chips.
  for (const def of FONT_DEFS) {
    const preset = FONT_STACK_PRESETS.find((p) => p.id === def.id);
    assert.ok(preset, `${def.id}: not offered as a theme font chip`);
    assert.equal(preset.stack, def.stack, `${def.id}: chip stack drifted from FONT_DEFS`);
    assert.equal(preset.label, def.family, `${def.id}: chip label is not the verbatim family name`);
  }
});

test("[TF-12] form controls inherit the typeface on every surface", () => {
  // input/select/textarea/button default to the UA font — without an inherit
  // rule every text box ignores the selected typeface AND the theme font
  // (found live: the theme-search placeholder rendered the system font).
  assert.match(fontStyles, /input,\s*textarea,\s*select,\s*button\s*\{\s*font-family:\s*inherit/,
    "the shadow-side form-control inherit rule vanished");
  assert.match(MODAL_HOST_STYLES, /input,\s*textarea,\s*select\s*\{\s*font-family:\s*inherit/,
    "the modal-host form-control inherit rule vanished");
});
