// Run: node --test src/cards/card-frame.test.mjs
//
// [CFR-*] THE CARD FRAME — replica set RNA0TM68, and the cycle that hid inside it.
//
// WHY THIS FILE EXISTS. check-styles.mjs does lint all three cards, but COLOR_PROP
// (check-styles.mjs:151) matches only colour properties AND requires a colour literal in
// the value. So `border: 1px solid var(--border)` passes, and border-width, box-shadow,
// padding, gap and font-size are invisible to it. That is the exact mechanism that let
// `--ha-card-border-width: 1px` and `--ha-card-box-shadow: none` sit hardcoded in
// room-card.js long enough for a user to file #83 about them — the cards' colours are
// fully tokenized and their geometry is not, because one half has a ratchet and the
// other has none. These tests are that ratchet for the frame.
//
// THE REPLICA. One rule, three copies, and they cannot be unified: room-card frames with
// Home Assistant's <ha-card> and so spells the rule as --ha-card-* custom properties,
// while the other two frame with a plain div and spell it as ordinary CSS. A green suite
// cannot see a missing copy, so [CFR-3] and [CFR-4] assert all three by construction
// rather than naming one.
//
// THE CYCLE. --evcc-radius-card -> --radius -> --ha-card-border-radius all landed on the
// room card's one host element, and CSS discards a cycle WHOLE: all three computed to the
// empty string. The card still looked correct because ha-card's own fallback is also
// 12px, so the documented ha-card-border-radius input reached nothing, silently, on one
// of three cards. Measured in Chromium: HA theme 24px -> painted 12px.
//
// Deleting the cyclic declaration is NOT the repair — it fixes the HA path and breaks the
// VA one. Measured, four paths, and only the third variant passes all four:
//
//                           HA 24px   VA 30px   neither   both (VA must win)
//   shipped                 12px  X   30px      12px      30px
//   delete the declaration  24px      12px  X   12px      24px  X
//   style the element       24px      30px      12px      30px
//
// [CFR-1] and [CFR-2] are the two halves of that third variant. Either one alone is
// satisfied by a broken state, which is why both exist.
//
// Coverage
// --------
// [CFR-1] room-card's :host does NOT declare --ha-card-border-radius (no cycle)
// [CFR-2] room-card's ha-card rule DOES own the radius as a property
// [CFR-3] all three cards read --evcc-card-frame-border-width
// [CFR-4] all three cards read --evcc-card-frame-shadow
// [CFR-5] both frame tokens are in the registry — required by two separate mechanisms
// [CFR-6] the border-width token declares an explicit range, not an inherited one
// [CFR-7] room-card registers idempotently and asks for a picker preview
// [CFR-8] room-card's :host does NOT declare --ha-card-border-width / -box-shadow
// [CFR-9] it declares them on the ha-card ELEMENT, from the :host intermediates
// [CFR-10] all three cards take an HA theme's value as the MIDDLE fallback

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { THEME_TOKEN_REGISTRY } from "../theme-tokens/index.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (...p) => readFileSync(join(REPO, ...p), "utf8");

/** Source with comments stripped. Load-bearing here: the comments at every one of these
 *  sites explain the cycle and name --ha-card-border-radius repeatedly, so an
 *  uncommented-source assertion would pass on the broken code it describes. */
function codeOnly(t) {
  return t.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

const ROOM = codeOnly(read("src", "room-card.js"));
const DASH = codeOnly(read("src", "cards", "dashboard-card.js"));
const PROF = codeOnly(read("src", "cards", "profile-card.js"));

/** The three frame copies of RNA0TM68. Named so a failure says which one drifted. */
const FRAMES = [
  ["room-card.js", ROOM],
  ["dashboard-card.js", DASH],
  ["profile-card.js", PROF],
];

test("[CFR-1] room-card declares --ha-card-border-radius nowhere", () => {
  // THE RED INPUT: re-add `--ha-card-border-radius: var(--radius);` to the card's :host.
  // That is the shipped-through-2.7.0 state, and it closes the three-property cycle, so
  // ha-card-border-radius from a Home Assistant theme reaches nothing.
  //
  // WHOLE FILE, not the :host block. The first version of this test scoped itself with
  // /:host \{([\s\S]*?)\n        \}/ — and room-card.js has TWO :host blocks. The first
  // belongs to the CONFIG EDITOR's shadow root (~line 95), which carries no --ha-card-*
  // at all, so the regex matched a block where the cycle can never appear and the test
  // passed on the fully ablated file. Caught by ablation, not by review: it was green
  // both ways. A file-wide assertion has no such anchor to miss.
  //
  // Safe against a legitimate READ: `var(--ha-card-border-radius, 12px)` has a comma
  // after the name, not a colon, so only a DECLARATION matches.
  assert.doesNotMatch(
    ROOM,
    /--ha-card-border-radius\s*:/,
    "declaring --ha-card-border-radius anywhere in room-card closes a cycle with " +
    "--evcc-radius-card and --radius; CSS discards a cycle whole, so all three compute " +
    "to the empty string and the documented theme input silently reaches nothing",
  );
});

test("[CFR-2] room-card's ha-card rule owns the frame radius", () => {
  // THE RED INPUT: drop `border-radius: var(--radius);` from the ha-card rule. The cycle
  // is gone, so HA's value works — but the VA theme's Radius Card token no longer moves
  // the frame, and when both are set HA wins where VA should. [CFR-1] alone passes on
  // that broken state, which is why this test is separate.
  const m = ROOM.match(/\bha-card \{([\s\S]*?)\}/);
  assert.ok(m, "could not find room-card's ha-card rule");
  assert.match(
    m[1],
    /border-radius\s*:\s*var\(\s*--radius\s*\)/,
    "the ha-card ELEMENT must own the radius as a property, so the one-way chain " +
    "--ha-card-border-radius -> --evcc-radius-card -> --radius -> frame stays intact " +
    "and an outer-tree rule still beats ha-card's inner :host",
  );
});

test("[CFR-3] all three cards read the frame border-width token", () => {
  // THE RED INPUT: revert any ONE card to a literal — `border: 1px solid var(--border)`
  // or `--ha-card-border-width: 1px`. Asserting all three is the point: this is a
  // three-copy replica and a green suite cannot see a missing copy.
  for (const [name, src] of FRAMES) {
    assert.match(
      src,
      /var\(\s*--evcc-card-frame-border-width\s*,/,
      `${name} must read var(--evcc-card-frame-border-width, <default>) for its frame ` +
      `border — replica RNA0TM68, all three copies or none`,
    );
  }
});

test("[CFR-4] all three cards read the frame shadow token", () => {
  // THE RED INPUT: drop the box-shadow read from any one card. Note this one was 1
  // declaration + 2 ABSENCES before the fix: only room-card declared `none`, and a div's
  // initial box-shadow is already none, so the three rendered identically while only one
  // was reachable. A fix that edited the declaration alone would have shipped a control
  // that moved one card of three, with every existing test still green.
  for (const [name, src] of FRAMES) {
    assert.match(
      src,
      /var\(\s*--evcc-card-frame-shadow\s*,/,
      `${name} must read var(--evcc-card-frame-shadow, <default>) — the two cards that ` +
      `previously declared NO box-shadow are the ones this catches`,
    );
  }
});

test("[CFR-5] both frame tokens are registered", () => {
  // THE RED INPUT: delete either entry from src/theme-tokens/cards.js, or rename a key
  // on one side only. Registry membership is required by TWO separate mechanisms:
  //   1. check-styles.mjs:288-301 fails the build on a var(--evcc-*) with no definition.
  //   2. apply-tokens.js:152 REMOVES only registry keys but WRITES every key, so a token
  //      in storage but not in the registry sticks on the host as an inline style across
  //      a theme switch and cannot be cleared.
  const keys = new Set(THEME_TOKEN_REGISTRY.map((t) => t.key));
  for (const k of ["--evcc-card-frame-border-width", "--evcc-card-frame-shadow"]) {
    assert.ok(keys.has(k), `${k} must be in THEME_TOKEN_REGISTRY`);
  }
});

test("[CFR-6] the border-width token declares its own range", () => {
  // THE RED INPUT: drop the { min, max, step } argument. A `size` token with no range
  // falls back to the per-group SLIDER_CONFIG, or to {min:0,max:64,step:1} when the group
  // is absent from that table — a 0-64px slider for a frame border, where every usable
  // value sits in the first 3% of travel. 40 of the 77 scalar tokens inherit a bound that
  // way today; --evcc-room-fill-opacity, a 0-1 opacity, currently gets 0-32 step 1.
  const t = THEME_TOKEN_REGISTRY.find((x) => x.key === "--evcc-card-frame-border-width");
  assert.ok(t, "--evcc-card-frame-border-width missing from the registry");
  assert.equal(t.type, "size");
  assert.equal(t.min, 0, "0 is a legitimate frame border and the one #83 asked for");
  assert.ok(Number.isFinite(t.max) && t.max <= 16,
    `max must be declared and in frame-border range, got ${t.max}`);
  assert.ok(Number.isFinite(t.step) && t.step <= 1,
    `step must be declared and sub-pixel-capable, got ${t.step}`);
});

/* =========================================================
   [CHP-*] THE CARD CHIP — replica set RNN1M4G1.
   =========================================================
   The Chips group holds 31 --evcc-chip-* tokens and the cards read ZERO of them until
   2026-11-16: measured, the three cards read 17 of 425 registry tokens and the Chips
   group's score was 0/31. A user moving "Chip Padding" in the theme editor changed the
   panel and nothing on their own dashboard, with no error and nothing to tell them why.

   TWO copies, not three — the profile card has no chips. A test that asserted "all three
   cards" here would be wrong, and would push someone to add chips to a card that has no
   use for them. docs/dev/00c-replicas.md records absence as load-bearing for this reason.
   ========================================================= */

/** The two cards that have chips. Profile card is deliberately absent. */
const CHIPPED = [["room-card.js", ROOM], ["dashboard-card.js", DASH]];

test("[CHP-1] both chipped cards read the chip tokens", () => {
  // THE RED INPUT: revert either card's .chip rule to its literals. Asserting the whole
  // token set, not one token, is the point: the old rule hardcoded SEVEN properties and
  // wiring six of them would look done and leave one surface unthemeable.
  const TOKENS = [
    "--evcc-chip-gap", "--evcc-chip-height", "--evcc-chip-padding", "--evcc-chip-radius",
    "--evcc-chip-border", "--evcc-chip-bg", "--evcc-chip-text",
    "--evcc-chip-font-size", "--evcc-chip-font-weight",
    "--evcc-chip-hover-bg", "--evcc-chip-hover-text", "--evcc-chip-hover-border",
    "--evcc-chip-active-bg", "--evcc-chip-active-text", "--evcc-chip-active-border",
  ];
  for (const [name, src] of CHIPPED) {
    for (const t of TOKENS) {
      assert.ok(
        new RegExp(`var\\(\\s*${t}\\s*[,)]`).test(src),
        `${name} must read ${t} — replica RNN1M4G1, both copies or neither`,
      );
    }
  }
});

test("[CHP-2] the old hardcoded chip geometry is gone from both", () => {
  // THE RED INPUT: leave a literal behind while adding the var() alongside it. [CHP-1]
  // passes on that — the token IS read — and the literal silently wins or loses
  // depending on declaration order. This is the half [CHP-1] cannot see.
  for (const [name, src] of CHIPPED) {
    const chipRule = src.match(/\.chip \{([\s\S]*?)\}/);
    assert.ok(chipRule, `${name}: could not find the .chip rule`);
    assert.doesNotMatch(chipRule[1], /padding:\s*5px\s+12px/,
      `${name}: .chip still hardcodes the old 5px 12px padding`);
    assert.doesNotMatch(chipRule[1], /font-size:\s*0\.80rem/,
      `${name}: .chip still hardcodes the old 0.80rem font-size`);
  }
});

test("[CHP-3] hover does not repaint a selected chip", () => {
  // THE RED INPUT: drop the :not(.active). A bare .chip:hover has the same specificity
  // as .chip.active and comes later in both files, so hovering a SELECTED chip repainted
  // it with the neutral hover background and it read as deselected under the cursor.
  // That was the shipped behaviour on both cards; the canonical .evcc-chip rule has
  // always guarded it.
  for (const [name, src] of CHIPPED) {
    assert.match(src, /\.chip:hover:not\(\.active\)/,
      `${name}: .chip:hover must be guarded with :not(.active), or hovering a selected ` +
      `chip paints it as if it were deselected`);
  }
});

test("[CHP-4] the active chip label keeps the card's lighter colour", () => {
  // THE RED INPUT: change either card's active-label fallback to a bare
  // var(--evcc-accent), which is the PANEL's token default and what this set took
  // everywhere else.
  //
  // Measured as swatches at the shipped accent #3b82f6 over the card surface #1c2127:
  //   bare accent                      3.49:1
  //   accent lightened 10% to white    4.02:1   <- what the cards shipped
  // Neither passes WCAG AA for normal text (4.5:1); that is an older problem and this
  // test does not claim to fix it. It stops the number moving the WRONG WAY as a side
  // effect of wiring chips to tokens — which is exactly what happened, and was invisible
  // because the before/after render that justified the change showed RESTING chips only.
  //
  // A theme setting --evcc-chip-active-text still wins outright on panel and cards, so
  // only the default differs. [CHP-1] passes either way: the token IS read.
  for (const [name, src] of CHIPPED) {
    const rule = src.match(/\.chip\.active \{([\s\S]*?)\}/);
    assert.ok(rule, `${name}: could not find the .chip.active rule`);
    assert.match(
      rule[1].replace(/\s+/g, " "),
      /color:\s*var\(\s*--evcc-chip-active-text,\s*color-mix\(in srgb, var\(--evcc-accent\) 90%, white\)\s*\)/,
      `${name}: the active label must fall back to the accent lightened toward white, ` +
      `not to a bare accent — the bare accent measures 3.49:1 against this background`,
    );
  }
});

test("[CFR-7] room-card registers idempotently and asks for a preview", () => {
  // THE RED INPUT: revert to `window.customCards.push({...})`, or drop `preview: true`.
  // This file ships in BOTH bundles — the panel bundle and the global one injected on
  // every page — so a bare push listed the card TWICE in Home Assistant's picker once
  // the panel had been opened. Its two siblings already used the guarded helper and both
  // already set preview: true; this was the odd one out on both counts.
  assert.doesNotMatch(
    ROOM,
    /window\.customCards\.push\s*\(/,
    "room-card must register via registerCard() from _shared.js, which guards against a " +
    "duplicate entry; a bare push has no such guard and this file loads from two bundles",
  );
  assert.match(ROOM, /registerCard\s*\(\s*\{/, "room-card must call registerCard({...})");
  const m = ROOM.match(/registerCard\s*\(\s*\{([\s\S]*?)\n\}\s*\)/);
  assert.ok(m, "could not find room-card's registerCard call");
  assert.match(m[1], /preview\s*:\s*true/,
    "preview: true asks HA to render the card in its own picker — the one card preview " +
    "that already ships, and it was switched off for this card alone");
});

/* ========================================================================== *
 * [CFR-8..10] THE HA NAMES REACH THE CARD TOO — issue #83, second pass
 * ========================================================================== *
 * THE FIRST PASS WAS A HALF FIX AND SHIPPED AS ONE. The reporter asked for
 * `ha-card-border-width: "0px"` and `ha-card-box-shadow: ...` in his Home Assistant
 * theme. He got VA-named tokens that do the same job, and his own two lines still did
 * nothing — on the room card because :host DECLARED those two names (a declared value
 * always beats an inherited one, so his was shadowed before it arrived), and on the
 * other two because they frame with a plain div that never read the HA name at all.
 *
 * The repair is the same shape as the radius one above, inverted: RESOLVE on :host,
 * where the two names are NOT declared and var() therefore sees what the theme set, and
 * APPLY on the ha-card element, where the intermediate has already computed to a plain
 * value so nothing refers to itself. Custom properties inherit their COMPUTED value,
 * which is what makes two steps legal where one is a cycle.
 *
 * MEASURED IN CHROMIUM against the built bundle, four paths x three cards:
 *
 *                       room card        dashboard / profile
 *   neither set         1px / none       1px / none
 *   HA theme only       0px / glow       0px / glow        <- was 1px / none, the defect
 *   VA token only       3px / VA         3px / VA
 *   both set            3px (VA wins)    3px (VA wins)
 *
 * VA winning when both are set is the deliberate precedence: a VA theme is opt-in and
 * more specific than the HA theme the card falls back to.
 */

test("[CFR-8] each --ha-card-* frame name is declared EXACTLY ONCE, at the apply site", () => {
  // THE RED INPUT, and it is exactly what shipped: add either declaration back onto
  // :host. The VA token keeps working and every other test here stays green, while the
  // reporter's theme silently stops reaching the card.
  //
  // THIS IS A FILE-WIDE COUNT, NOT A :host-BLOCK SCAN, and the first version of it was
  // the block scan. room-card.js has TWO :host blocks -- a one-line one at the top of
  // the chrome styles and the card's own -- and a lazy `:host\s*\{[\s\S]*?\}` matches
  // the one-liner, captures nothing, and passes whatever you do to the real block. An
  // ablation that re-declared the name on :host reddened NOTHING. That is the same trap
  // [CFR-1] records being caught by, in this same file, which is why both are now
  // file-wide: a count cannot be fooled by which block it found.
  for (const name of ["--ha-card-border-width", "--ha-card-box-shadow"]) {
    const decls = [...ROOM.matchAll(new RegExp(`${name}\s*:\s*([^;]+);`, "g"))]
      .map((m) => m[1].trim().replace(/\s+/g, " "));
    assert.equal(decls.length, 1,
      `${name} must be declared exactly once and only at the apply site. Found ` +
      `${decls.length}: ${JSON.stringify(decls)}. A second declaration on :host shadows ` +
      "the value an HA theme set, before the card can read it — the #83 defect.");
    assert.match(decls[0], /^var\(--frame-(border-width|shadow)\)$/,
      `${name} must be declared from the :host intermediate, not straight from the VA ` +
      `token — reading the token here loses the HA middle rung. Got: ${decls[0]}`);
  }
});

test("[CFR-9] it declares them on the ha-card ELEMENT, from the :host intermediates", () => {
  // The other half. [CFR-8] alone is satisfied by simply deleting the declarations,
  // which would hand the frame to the HA theme and break the VA token — so this pins
  // that the apply step exists and reads the resolved intermediate rather than
  // re-reading the --ha-card-* name (which on that element IS declared, i.e. a cycle).
  const rule = ROOM.match(/\n\s*ha-card\s*\{[\s\S]*?\n\s*\}/);
  assert.ok(rule, "could not find room-card's ha-card element rule");
  assert.match(rule[0], /--ha-card-border-width:\s*var\(--frame-border-width\)/);
  assert.match(rule[0], /--ha-card-box-shadow:\s*var\(--frame-shadow\)/);

  // And the intermediates must resolve VA-first, HA-second, literal-last.
  assert.match(ROOM,
    /--frame-border-width:\s*var\(--evcc-card-frame-border-width,\s*var\(--ha-card-border-width,\s*1px\)\)/,
    "the border-width intermediate must be VA token -> HA theme -> 1px, in that order");
  assert.match(ROOM,
    /--frame-shadow:\s*var\(--evcc-card-frame-shadow,\s*var\(--ha-card-box-shadow,\s*none\)\)/,
    "the shadow intermediate must be VA token -> HA theme -> none, in that order");
});

test("[CFR-10] all three cards take the HA theme value as the MIDDLE fallback", () => {
  // THE RED INPUT: fixing only the room card. It is the one with the interesting cycle,
  // so it is the one that gets the attention — and the other two would keep ignoring the
  // reporter's theme while the headline said the problem was solved. Same shape as
  // [CFR-3]/[CFR-4], which exist because a three-copy replica cannot be checked by
  // naming one copy.
  for (const [name, src] of FRAMES) {
    assert.match(src, /var\(--evcc-card-frame-border-width,\s*var\(--ha-card-border-width,/,
      `${name}: the border width must fall back to an HA theme's --ha-card-border-width`);
    assert.match(src, /var\(--evcc-card-frame-shadow,\s*var\(--ha-card-box-shadow,/,
      `${name}: the shadow must fall back to an HA theme's --ha-card-box-shadow`);
  }
});
