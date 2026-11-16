// Run: node --test src/cards/va-theme-wiring.test.mjs
//
// [VTW-*] THE VA THEME REACHES ALL THREE CARDS.
//
// `applyVaThemeToCard` shipped correct, tested, and wired into ONE of the three cards a
// user can add. card-theme.test.mjs passed completely, because it tests the WRITER: hand
// it a host and a theme and it paints. What nothing tested was whether anybody called it.
// A correct function with one caller and three consumers is exactly the shape of
// `_roomProfileLabel` (zero callers, found by a census) and of the multi-vacuum filter
// behind #77 — a thing that passes every audit by being individually right.
//
// The three cards, each registered separately in window.customCards:
//   src/room-card.js            Eufy Room Card
//   src/cards/dashboard-card.js Vacuum Agent — Dashboard Mode
//   src/cards/profile-card.js   Vacuum Agent Profile Card
//
// [VTW-2] IS THE ONE THAT EARNS ITS PLACE, and it is not hypothetical — it reddens
// against the code as it shipped in 0a763b2a. The room card called the writer THIRTY
// LINES BELOW its own early return, under a comment explaining that returning early
// would "strand the last palette on the host". `innerHTML = ""` clears the card's
// CHILDREN; the tokens are inline style on the HOST and survive it. The editor's
// vacuum-change handler fires `{vacuum_entity_id, room_id: undefined}`, so changing
// vacuum takes the render down the empty branch — and below the return that is an empty
// card still wearing the palette, with no way to clear it short of a reload. The guard
// existed; the shoulder just above it did not.
//
// Coverage
// --------
// [VTW-1] all three cards import the writer and call it
// [VTW-2] each call sits ABOVE the first return in its own _render()  <- the guard
// [VTW-3] the option is read with `=== true`, never truthily
// [VTW-4] each editor DELETES the key when unticked rather than storing false
// [VTW-5] the dashboard card does not route va_theme through its default-ON bool() helper

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const CARDS = [
  ["room",      "src/room-card.js"],
  ["dashboard", "src/cards/dashboard-card.js"],
  ["profile",   "src/cards/profile-card.js"],
];

const src = (rel) => readFileSync(join(REPO, rel), "utf8");

test("[VTW-1] all three cards import the writer and call it", () => {
  for (const [name, rel] of CARDS) {
    const t = src(rel);
    assert.match(
      t,
      /import \{ applyVaThemeToCard \} from "[^"]*styles\/card-theme\.js";/,
      `${name}: must import applyVaThemeToCard — a card that does not wears the HA theme ` +
      "no matter what the user ticks",
    );
    // The CALL, not the import line: the import alone is what a dead wiring looks like.
    const calls = t.split("applyVaThemeToCard(").length - 1;
    assert.ok(calls >= 1, `${name}: imports the writer but never calls it (${calls} call sites)`);
  }
});

/**
 * Source with comments removed, so prose cannot move a textual anchor.
 *
 * The first cut of [VTW-2] searched for the word `return` and found it in the COMMENT
 * above the call — in two of the three files, the comment explaining this very invariant.
 * It reported all three red against code that was correct in all three. A probe that
 * fails on its first run is the probe, not the code.
 */
function codeOnly(t) {
  return t.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

test("[VTW-2] each call sits ABOVE any branch that clears the card's content", () => {
  // THE INVARIANT, stated precisely. It is NOT "before the first return" — the profile
  // card opens with `if (!this.shadowRoot) return;`, a readiness guard that neither
  // clears content nor strands anything, and demanding the theme call precede it would
  // be a rule about nothing. What strands a palette is the other shape: a branch that
  // assigns innerHTML and returns. `innerHTML` replaces the card's CHILDREN while the
  // tokens are inline style on the HOST, so a call below such a branch is skipped on
  // exactly the tick that needed it.
  //
  // THE RED INPUT: move the call below the `innerHTML`-clearing branch in any of the
  // three. That is where it shipped in the room card, and both orders read as correct.
  // EVERY call site, not just the first. The first version of this case indexed only
  // `indexOf(...)`, so an ablation that ADDED a second call below the clearing branch
  // left it green — the test was satisfied by the good call and blind to the bad one.
  // Ablation is what showed that; it looked identical to a passing test beforehand.
  for (const [name, rel] of CARDS) {
    const t = codeOnly(src(rel));
    const sites = [];
    for (let i = t.indexOf("applyVaThemeToCard("); i !== -1; i = t.indexOf("applyVaThemeToCard(", i + 1)) {
      sites.push(i);
    }
    assert.ok(sites.length > 0, `${name}: could not find a call site`);

    for (const call of sites) {
      // Walk back to the nearest enclosing `_render() {`. Each file holds TWO — the
      // card's and its editor's — so anchoring on the first would test the wrong one.
      const renderStart = t.lastIndexOf("_render() {", call);
      assert.ok(renderStart > 0, `${name}: a call at ${call} is not inside a _render()`);

      const clears = t.indexOf("innerHTML", renderStart);
      assert.ok(
        clears > 0,
        `${name}: no innerHTML write found in _render() — these cards all render by ` +
        "assigning innerHTML, so this test's anchor has gone stale rather than the card " +
        "having become safe. Do not relax it; re-aim it.",
      );
      assert.ok(
        call < clears,
        `${name}: applyVaThemeToCard is called AFTER _render() writes innerHTML ` +
        `(call at ${call}, innerHTML at ${clears}). A branch that clears content and ` +
        "returns then skips the theme call, and because the tokens live on the HOST they " +
        "survive the clear — an empty card still wearing the palette, until a reload.",
      );
    }
  }
});

test("[VTW-3] EVERY read of the option uses === true, never a truthy test", () => {
  // The first version asserted only that `va_theme === true` appeared SOMEWHERE in the
  // file. Ablating the profile card's render to `!!this._config?.va_theme` left it green,
  // because the editor's own `=== true` on the checkbox line still satisfied the match.
  // One strict read elsewhere in the file is not evidence about this read. So: classify
  // every occurrence, and let none through unexamined.
  //
  // `va_theme(?!_)` excludes the i18n key names `editor_va_theme_label` / `_hint`, which
  // contain the identifier as a substring and are not reads of it.
  for (const [name, rel] of CARDS) {
    const t = codeOnly(src(rel));
    const occurrences = [...t.matchAll(/va_theme(?!_)/g)];
    assert.ok(occurrences.length > 0, `${name}: no va_theme reference at all`);

    for (const m of occurrences) {
      const after = t.slice(m.index + "va_theme".length, m.index + "va_theme".length + 20);
      const before = t.slice(Math.max(0, m.index - 20), m.index);
      const isStrictRead = /^\s*===\s*true/.test(after);
      const isWrite = /^\s*=\s*true/.test(after);
      const isDelete = /delete\s+\w+\.$/.test(before);
      assert.ok(
        isStrictRead || isWrite || isDelete,
        `${name}: a va_theme reference at ${m.index} is neither \`=== true\`, \`= true\`, ` +
        `nor a delete — it reads as ...${JSON.stringify(before.slice(-28) + "va_theme" + after.slice(0, 16))}. ` +
        "The option defaults OFF and is written only when true, so a truthy test would " +
        "turn the VA theme on for any stored value that is merely not falsy.",
      );
    }
  }
});

test("[VTW-4] each editor deletes the key when unticked rather than storing false", () => {
  // The trap this pins is real and shaped like the dashboard card's own show_* loop,
  // which writes `[key]: e.target.checked`. Reused for va_theme that persists
  // `va_theme: false` onto every dashboard that merely OPENED the editor — turning a
  // no-op into a config change on cards the user never meant to touch.
  for (const [name, rel] of CARDS) {
    const t = src(rel);
    assert.match(
      t,
      /if \(e\.target\.checked\) next\.va_theme = true; else delete next\.va_theme;/,
      `${name}: the va_theme handler must write true or DELETE, so a card that never ` +
      "opted in carries no key and its stored config stays byte-identical to one from " +
      "before this option existed",
    );
  }
});

test("[VTW-5] the dashboard card does not route va_theme through its default-ON helper", () => {
  const t = src("src/cards/dashboard-card.js");
  // bool(k, dflt) is `(this._config[k] ?? dflt) !== false` — correct for the four show_*
  // options, which default ON. va_theme defaults OFF; through that helper it would be on
  // for everyone on upgrade, which is the one outcome the opt-in exists to prevent.
  assert.ok(
    !/bool\(\s*["']va_theme["']/.test(t),
    "va_theme must not go through bool(): that helper treats absent as the default, and " +
    "passing a true default would restyle every existing dashboard on upgrade",
  );
  assert.ok(
    !/\[key\]: e\.target\.checked[\s\S]{0,400}va_theme/.test(t) ||
      /else delete next\.va_theme/.test(t),
    "va_theme must not be folded into the show_* loop",
  );
});
