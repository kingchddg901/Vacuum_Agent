// Run: node --test src/theme-tokens/per-card-tokens.test.mjs
//
// [PCT-*] THE PER-CARD RUNG — one more step on the chain, and the three ways it can lie.
//
// WHY IT EXISTS. Chris's call 2026-11-16, and his reason is the shape of the whole
// feature: "yaml is fine for some but most of the reason i made the theme editor is to
// not need it for most people". So these are real registry tokens with real controls,
// not a var() a theme author could discover. That raises the stakes on three things a
// green suite would otherwise miss:
//
//   1. THE KEY LIST IS SPELLED OUT, because scripts/check-styles.mjs builds its
//      inventory by TEXT-SCANNING this directory — runtime-built keys are invisible to
//      it and every var() site reads as dangling (measured: the build failed with
//      exactly 51, the site count). Spelled-out keys and a derived shape are two halves
//      that can drift, so [PCT-1] pins them together.
//   2. A TOKEN WITH NO var() SITE IS A CONTROL THAT MOVES NOTHING. It renders in the
//      editor, it stores a value, it does nothing, and nothing anywhere reports it.
//      [PCT-3] is the reachability half.
//   3. THE RUNG ORDER IS THE WHOLE FEATURE. Per-card must be tried BEFORE the shared
//      token, or the per-card control can never win and the group is decorative.
//      [PCT-4] pins the direction, which [PCT-3] cannot see.
//
// Coverage
// --------
// [PCT-1] PER_CARD_KEYS is exactly what READS implies — no missing, no extra
// [PCT-2] each per-card token's SHAPE is its shared sibling's, differing only in key/group
// [PCT-3] every per-card key is actually read by that card's CSS
// [PCT-4] it is read as the OUTER rung, with the shared token as its fallback

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  PER_CARD_KEYS, PER_CARD_TOKENS, PER_CARD_GROUP, DASHBOARD_CARD_TOKENS,
} from "./cards.js";
import { THEME_GROUPS } from "./groups.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SRC = {
  room: readFileSync(join(REPO, "src", "room-card.js"), "utf8"),
  dashboard: readFileSync(join(REPO, "src", "cards", "dashboard-card.js"), "utf8"),
  profile: readFileSync(join(REPO, "src", "cards", "profile-card.js"), "utf8"),
};

/** Which of the ten each card reads — stated INDEPENDENTLY of cards.js on purpose.
 *  Importing READS from the module under test would make [PCT-1] compare a thing to
 *  itself and pass whatever either side said. This copy is the measurement.
 *  frame-background and frame-border-color were added by reading the three card files:
 *  room-card.js resolves them on :host and applies them on the ha-card element, while
 *  dashboard-card.js (.card) and profile-card.js (.evcc-pcard) spell them as ordinary
 *  properties on a plain div. */
const EXPECTED = {
  room: ["frame-background", "frame-border-color", "frame-border-width", "frame-shadow",
         "action-glow", "font-scale", "header-padding", "field-gap"],
  dashboard: ["frame-background", "frame-border-color", "frame-border-width", "frame-shadow",
              "action-glow", "font-scale", "header-padding", "field-gap",
              "row-padding", "section-padding"],
  profile: ["frame-background", "frame-border-color", "frame-border-width", "frame-shadow",
            "action-glow", "font-scale"],
};

const split = (key) => {
  for (const id of Object.keys(EXPECTED)) {
    const p = `--evcc-card-${id}-`;
    if (key.startsWith(p)) return { id, thing: key.slice(p.length) };
  }
  throw new Error(`no card id in ${key}`);
};

test("[PCT-1] PER_CARD_KEYS is exactly what the cards read — no missing, no extra", () => {
  // THE RED INPUT: add an eleventh thing to one card's CSS and forget its key, or leave a
  // key behind after dropping a control. Either way the two halves disagree and nothing
  // else notices: a missing key is a control that never appears, an extra one is a
  // control that moves nothing.
  const want = Object.entries(EXPECTED)
    .flatMap(([id, things]) => things.map((t) => `--evcc-card-${id}-${t}`))
    .sort();
  assert.deepEqual([...PER_CARD_KEYS].sort(), want);
  assert.equal(PER_CARD_KEYS.length, 24, "8 room + 10 dashboard + 6 profile");
  assert.equal(new Set(PER_CARD_KEYS).size, PER_CARD_KEYS.length, "no duplicate keys");
});

test("[PCT-2] each per-card token's shape is its shared sibling's", () => {
  // THE RED INPUT: restating {label, type, min, max, step} per card instead of deriving
  // it. This group carries TWO deliberately explicit ranges (0–8 step 0.5 for the border,
  // 0.5–2 step 0.05 for the text scale) with the reasoning written beside them, and a
  // parallel table is exactly how one gets retuned and the other does not.
  const shared = new Map(DASHBOARD_CARD_TOKENS.map((t) => [t.key.replace("--evcc-card-", ""), t]));
  for (const tok of PER_CARD_TOKENS) {
    const { id, thing } = split(tok.key);
    const base = shared.get(thing);
    assert.ok(base, `${tok.key} has no shared sibling`);
    const strip = (t) => { const { key, group, ...rest } = t; return rest; };
    assert.deepEqual(strip(tok), strip(base),
      `${tok.key} must match its sibling in label, type and range`);
    assert.equal(tok.group, PER_CARD_GROUP[id]);
    assert.ok(THEME_GROUPS.includes(tok.group), `${tok.group} must be a registered group`);
  }
});

test("[PCT-3] every per-card key is actually read by that card's CSS", () => {
  // THE RED INPUT: mint the token and forget the var() site. The control renders, stores
  // a value and moves nothing — a correct token with zero callers passes every test
  // about the token. This is the half that notices.
  const missing = PER_CARD_KEYS.filter((key) => !SRC[split(key).id].includes(`var(${key},`));
  assert.deepEqual(missing, [],
    "these per-card tokens have a control in the editor and no var() site in the card " +
    "they name, so moving them does nothing:\n  " + missing.join("\n  "));
});

test("[PCT-4] the per-card rung is OUTSIDE the shared one", () => {
  // THE RED INPUT: wrap them the other way round —
  //   var(--evcc-card-header-padding, var(--evcc-card-room-header-padding, ...))
  // The shared token then always wins and the per-card control can never take effect,
  // while [PCT-3] stays green because both names are still present in the file. Order
  // IS the feature; a chain that reads the wrong way is decorative.
  for (const key of PER_CARD_KEYS) {
    const { id, thing } = split(key);
    const at = SRC[id].indexOf(`var(${key},`);
    assert.notEqual(at, -1, `${key} is not read at all`);
    const after = SRC[id].slice(at + `var(${key},`.length, at + `var(${key},`.length + 80);
    assert.match(after, new RegExp(`^\\s*var\\(--evcc-card-${thing},`),
      `${key} must fall back to the SHARED --evcc-card-${thing}, so the per-card value ` +
      `wins and the shared one still carries every card that has no override. Got: ` +
      JSON.stringify(after.slice(0, 60)));
  }
});

test("[PCT-5] no card token is DECLARED anywhere — that absence is the YAML path", () => {
  // THE RED INPUT: declare any one of the 34 in a :host block, with any value at all.
  // A declaration in the card's own tree beats a value inherited from the document, so
  // that token stops responding to a themes.yaml entry while the theme editor keeps
  // working perfectly — and the user's report would be "my YAML does nothing", which
  // looks exactly like a mistyped key.
  //
  // MEASURED 2026-11-16 against the built bundle, all three cards: a token set on <html>
  // reaches the frame; the per-card key beats the shared key; a VA theme (written inline
  // on the host) beats both. That is his stated precedence, and it holds only while these
  // stay undeclared. Same mechanism-is-the-absence shape as [SCO-2].
  const NAMES = [...PER_CARD_KEYS, ...DASHBOARD_CARD_TOKENS.map((t) => t.key)];
  assert.ok(NAMES.length >= 34, `expected at least 34 card tokens, got ${NAMES.length}`);

  const offenders = [];
  // EVERY non-test .js under src/, not just the three cards: a declaration anywhere in
  // the cascade above a card shadows the inherited value just as effectively, and the
  // three-file version of this would not have seen it. [SCO-2] sweeps the same way.
  const walk = (dir, out = []) => {
    for (const e of readdirSync(dir)) {
      const p = join(dir, e);
      if (statSync(p).isDirectory()) walk(p, out);
      else if (e.endsWith(".js") && !e.includes(".test.")) out.push(p);
    }
    return out;
  };
  const FILES = walk(join(REPO, "src"));
  assert.ok(FILES.length > 50, `expected a real sweep of src/, got ${FILES.length} files`);

  for (const p of FILES) {
    const id = p.slice(p.indexOf("src"));
    const text = readFileSync(p, "utf8");
    const code = text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
    for (const name of NAMES) {
      // A DECLARATION is `--name:` NOT inside a var(). Every legitimate use here is
      // `var(--name, …)`, so anything else is the thing this case exists to catch.
      const re = new RegExp(String.raw`(^|[^(\w-])${name}\s*:`, "gm");
      for (const m of code.matchAll(re)) {
        const before = code.slice(Math.max(0, m.index - 4), m.index + 1);
        if (before.includes("var(")) continue;
        offenders.push(`${id}: ${name}`);
      }
    }
  }
  assert.deepEqual(offenders, [],
    "these card tokens are DECLARED, which shadows any themes.yaml value a user sets " +
    "for them — the token keeps working in the theme editor and silently stops working " +
    "from YAML: " + JSON.stringify(offenders));
});

test("[YDOC-1] the user guide's YAML table matches the registry — names, labels and readership", () => {
  // THE RED INPUT: add an eleventh Dashboard Cards control, or change which cards read one,
  // and leave the guide alone. The guide is where someone who chose YAML goes INSTEAD of
  // opening the editor, so a missing row is a control they will never find, and a wrong
  // tick is a value they will set and watch do nothing.
  //
  // Both counts in the 2.7.1 changelog rotted exactly this way within one release.
  const guide = readFileSync(
    join(REPO, "docs", "user-guide", "20-dashboard-and-room-cards.md"), "utf8");
  const en = readFileSync(join(REPO, "src", "i18n", "en.js"), "utf8");

  // The table rows look like: | `evcc-card-x` | Label | value | tick | tick | tick |
  const rows = [...guide.matchAll(
    /^\|\s*`(evcc-card-[a-z-]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|/gm)]
    .map((m) => ({
      key: `--${m[1]}`,
      label: m[2].trim(),
      reads: { room: m[4].includes("\u2705"), dashboard: m[5].includes("\u2705"), profile: m[6].includes("\u2705") },
    }));
  assert.ok(rows.length > 0, "found no YAML reference rows in the user guide — the table's " +
    "shape changed, so this gate has gone blind rather than the guide having become right");

  // 1. exactly the shared tokens, no more and no fewer
  assert.deepEqual(
    rows.map((r) => r.key).sort(),
    DASHBOARD_CARD_TOKENS.map((t) => t.key).sort(),
    "the guide's YAML table and the Dashboard Cards registry disagree about which controls exist");

  // 2. the label is the SHIPPED English one, not the registry's internal label.
  //    --evcc-card-font-scale is "Font Scale" in the registry and "Text Scale" on screen.
  for (const r of rows) {
    const vocabKey = `vocab.theme_token.${r.key.replace(/^--/, "").replace(/-/g, "_")}`;
    const m = en.match(new RegExp(`"${vocabKey.replace(/\./g, "\\.")}":\\s*"([^"]+)"`));
    const shipped = m ? m[1] : null;
    assert.ok(shipped, `${r.key} has no ${vocabKey} in en.js, so the guide cannot be checked ` +
      "against what the editor actually shows");
    assert.equal(r.label, shipped,
      `the guide calls ${r.key} "${r.label}" but the editor shows "${shipped}" — a reader ` +
      "following the guide would look for a control that is not on the screen");
  }

  // 3. the ticks match which cards actually read each control
  const readsFromRegistry = {};
  for (const k of PER_CARD_KEYS) {
    const m = k.match(/^--evcc-card-(room|dashboard|profile)-(.+)$/);
    (readsFromRegistry[`--evcc-card-${m[2]}`] ??= new Set()).add(m[1]);
  }
  for (const r of rows) {
    const actual = readsFromRegistry[r.key] ?? new Set();
    for (const card of ["room", "dashboard", "profile"]) {
      assert.equal(r.reads[card], actual.has(card),
        `${r.key}: the guide says ${card} ${r.reads[card] ? "does" : "does not"} read it, ` +
        `the registry says it ${actual.has(card) ? "does" : "does not"}`);
    }
  }
});
