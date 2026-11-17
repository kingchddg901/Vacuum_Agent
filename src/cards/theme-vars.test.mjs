/**
 * ============================================================
 * PER-INSTANCE CARD STYLING FROM YAML  (`theme_vars`)
 * ============================================================
 *
 * HIS RULING 2026-11-16, verbatim: "YAML can be the winner its set directly after all",
 * with "per isntance cards yes and everything we exposed should be settable". So
 * `theme_vars` on a card's own config is the TOP rung of the styling ladder:
 *
 *   1. theme_vars on THIS card
 *   2. the Vacuum Agent theme            (va_theme: true)
 *   3. --evcc-card-<card>-<thing>        (themes.yaml, per card type)
 *   4. --evcc-card-<thing>               (themes.yaml, all cards)
 *   5. --ha-card-*                       (the Home Assistant theme)
 *   6. the shipped default
 *
 * MEASURED IN CHROMIUM against the built bundle, all three cards: theme_vars alone wins;
 * it beats a VA theme on the same token; it beats a themes.yaml value on the same token;
 * TWO instances of the same card type on one page take DIFFERENT values; deleting a key
 * releases it; and an --evcc-animal-* hex arrives converted ("32 100% 50%") rather than
 * raw. What those runs cannot pin is the WIRING, which is what this file is for -- and the
 * wiring is the whole ruling, because rung 1 beating rung 2 is purely a question of which
 * writer runs last.
 *
 * ============================================================
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  CARD_THEME_VARS_KEY, normaliseThemeVarName, readCardThemeVars, applyCardThemeVars,
} from "./_shared.js";
// The REAL producer of a drop-in material's token names. Imported rather than restated:
// a fixture that encodes my idea of the shape would agree with itself and prove nothing.
import { tokenFor } from "../textures/user-materials.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (...p) => readFileSync(join(REPO, ...p), "utf8");
const codeOnly = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

const CARDS = [
  ["room-card.js", codeOnly(read("src", "room-card.js"))],
  ["dashboard-card.js", codeOnly(read("src", "cards", "dashboard-card.js"))],
  ["profile-card.js", codeOnly(read("src", "cards", "profile-card.js"))],
];

/** A stand-in for the one thing this helper touches: an element's inline style.
 *  Deliberately only setProperty/removeProperty — the shape the caller actually uses, so
 *  the fake cannot drift into agreeing with an implementation detail instead of a
 *  contract. The real path is measured in Chromium; this pins the logic around it. */
function fakeHost() {
  const props = new Map();
  return {
    props,
    style: {
      setProperty: (k, v) => props.set(k, v),
      removeProperty: (k) => props.delete(k),
    },
  };
}

test("[TVR-1] every card applies theme_vars, to itself", () => {
  // THE RED INPUT: wire two cards and forget the third. Nothing else notices — the other
  // two work, the config key is accepted everywhere because nothing validates it, and the
  // forgotten card silently ignores a documented option.
  for (const [name, src] of CARDS) {
    assert.match(src, /applyCardThemeVars\(/,
      `${name}: must call applyCardThemeVars`);
    assert.match(src, /this\._appliedThemeVars = applyCardThemeVars\(\s*\n?\s*this,/,
      `${name}: must apply to ITSELF and keep the applied set, or deleting a key from ` +
      "the YAML leaves it painting until a reload");
  }
});

test("[TVR-2] it runs AFTER the theme writer — the ruling lives here", () => {
  // THIS IS THE RULING, as code. Both applyDynamicTheme and this write INLINE on the same
  // host, so whichever runs LAST wins. Worse than losing: applyDynamicTheme walks the whole
  // registry and removeProperty()s every token the theme does not carry, so running
  // theme_vars first does not merely lose — it is erased on the same tick.
  //
  // THE RED INPUT: move the call above applyVaThemeToCard. On a card with va_theme OFF
  // everything still looks right, because then the theme writer carries nothing to
  // overwrite with — so the bug only appears for users who ticked the box.
  for (const [name, src] of CARDS) {
    const theme = src.indexOf("applyVaThemeToCard(");
    const vars = src.indexOf("applyCardThemeVars(");
    assert.ok(theme > 0, `${name}: no applyVaThemeToCard call found`);
    assert.ok(vars > 0, `${name}: no applyCardThemeVars call found`);
    assert.ok(theme < vars,
      `${name}: applyCardThemeVars is called BEFORE applyVaThemeToCard (${vars} < ${theme}). ` +
      "The theme writer removes every registry token it does not carry, so theme_vars " +
      "would be erased on the same tick — and only on cards with va_theme ticked.");
  }
});

test("[TVR-3] the dashboard card reaches the nested map host too", () => {
  // THE RED INPUT: theme the card and forget the map inside it — exactly the defect
  // [MAP-THEME-*] exists for, arriving a second time by a different route. <eufy-vacuum-map>
  // injects foundationTokens into its OWN shadow root, so a value inherited from the card
  // loses to its own declaration.
  const [, dash] = CARDS.find(([n]) => n === "dashboard-card.js");
  assert.match(dash, /_appliedMapThemeVars = applyCardThemeVars\(\s*\n?\s*this\._mapEl,/,
    "dashboard-card must apply theme_vars to this._mapEl as well as to itself, tracked " +
    "in its own set — the map host re-declares every --evcc-* it inherits");
});

test("[TVR-4] only --evcc-* names are accepted, dashed or not", () => {
  // THE RED INPUT: accept any property name. `theme_vars` writes straight to inline style,
  // so an unrestricted name turns a card config into arbitrary CSS on that element.
  // Undashed is accepted because HA themes are written that way and people copy the habit.
  for (const good of ["evcc-accent", "--evcc-accent", "evcc-card-frame-background",
                      "evcc-map-background", "--evcc-animal-cat-eye-good"]) {
    assert.ok(normaliseThemeVarName(good)?.startsWith("--evcc-"),
      `${good} should be accepted`);
  }

  // A DROP-IN MATERIAL'S OWN CONTROLS, built by the REAL producer rather than by my idea
  // of its shape. The backend accepts a material id matching ^[a-z0-9][a-z0-9_-]{0,31}$
  // (user_materials.py ID_RE), so an id may contain an UNDERSCORE — and the first version
  // of the name check did not allow one, which made every control of such a pack
  // unreachable from theme_vars while the user guide promised the opposite. Silent, and
  // only for users who authored their own material. Found by the pre-release audit.
  for (const id of ["oak_wide", "carpet_low", "plain", "a1_b2-c3"]) {
    for (const kind of ["color", "opacity"]) {
      const minted = tokenFor(id, "base", kind);
      assert.equal(normaliseThemeVarName(minted), minted,
        `a drop-in material's minted token ${minted} must be settable from theme_vars — ` +
        "the editor shows it, so the documented promise covers it");
    }
  }
  for (const bad of ["color", "--color", "--ha-card-background", "background",
                     "--evcc-", "evcc_card_frame", "--evcc-Card-Frame", "", null, undefined]) {
    assert.equal(normaliseThemeVarName(bad), null, `${JSON.stringify(bad)} should be refused`);
  }
});

test("[TVR-5] values that could break out are refused, and refusals are reported", () => {
  // A custom property holds an arbitrary token stream, so `;` or `}` cannot escape the
  // element — it only makes the declarations that var() it invalid at computed-value time.
  // Refused anyway: that failure is invisible and lands far from its cause, and "the card
  // went blank" is a worse answer than "that value was ignored".
  //
  // THE RED INPUT: drop the value check. The probe for it is the `rejected` list — a
  // silent skip would leave nothing to show a user who mistyped.
  const { vars, rejected } = readCardThemeVars({
    [CARD_THEME_VARS_KEY]: {
      "evcc-accent": "#f60",
      "--evcc-ok": "blue",
      "--evcc-bad": "red; } body { display: none",
      "--evcc-brace": "red }",
      "not-a-token": "x",
      "--evcc-empty": "",
    },
  });
  assert.deepEqual(vars, [["--evcc-accent", "#f60"], ["--evcc-ok", "blue"]]);
  assert.deepEqual(rejected.sort(), ["--evcc-bad", "--evcc-brace", "not-a-token"]);

  // Absent, wrong-typed or array config is simply nothing — never a throw, because this
  // runs inside _render on every tick and a throw there takes the whole card down.
  for (const cfg of [undefined, null, {}, { theme_vars: null }, { theme_vars: "x" }, { theme_vars: [] }]) {
    assert.deepEqual(readCardThemeVars(cfg), { vars: [], rejected: [] },
      `${JSON.stringify(cfg)} must yield nothing rather than throw`);
  }
});

test("[TVR-6] deleting a key releases it, rather than leaving it painted", () => {
  // THE RED INPUT: drop the `previous` bookkeeping and just write what the config says.
  // Every test that checks "the value is applied" still passes; what breaks is REMOVING a
  // key, which keeps painting until a reload — so the card visibly disagrees with its own
  // config and the user's edit appears to do nothing.
  const host = fakeHost();
  let applied = applyCardThemeVars(host, { theme_vars: { "evcc-accent": "#f60", "evcc-ok": "blue" } });
  assert.deepEqual([...host.props.keys()].sort(), ["--evcc-accent", "--evcc-ok"]);
  assert.deepEqual([...applied].sort(), ["--evcc-accent", "--evcc-ok"]);

  applied = applyCardThemeVars(host, { theme_vars: { "evcc-accent": "#0f0" } }, applied);
  assert.deepEqual([...host.props.keys()], ["--evcc-accent"], "--evcc-ok must be released");
  assert.equal(host.props.get("--evcc-accent"), "#0f0", "and the kept one must update");

  applied = applyCardThemeVars(host, {}, applied);
  assert.deepEqual([...host.props.keys()], [], "removing theme_vars entirely releases all");
});

test("[TVR-7] animal tokens are converted, not written as a hex", () => {
  // THE RED INPUT: write the value straight through. --evcc-animal-* are consumed as BARE
  // hsl() components, so a hex renders the animal BLACK — and only on the YAML path, which
  // is the worst shape of bug: it works everywhere the author tested.
  const host = fakeHost();
  const toComponents = (hex) => (hex === "#ff8800" ? "32 100% 50%" : null);
  applyCardThemeVars(host, {
    theme_vars: { "evcc-animal-cat-eye-good": "#ff8800", "evcc-accent": "#ff8800" },
  }, undefined, toComponents);

  assert.equal(host.props.get("--evcc-animal-cat-eye-good"), "32 100% 50%",
    "an animal token must go through the hsl-components conversion");
  assert.equal(host.props.get("--evcc-accent"), "#ff8800",
    "a non-animal token must NOT be converted");

  // A value the converter cannot read falls back to the raw string rather than writing
  // null, which would blank the token and is worse than a wrong colour.
  const h2 = fakeHost();
  applyCardThemeVars(h2, { theme_vars: { "evcc-animal-cat-eye-good": "notacolour" } },
                     undefined, () => null);
  assert.equal(h2.props.get("--evcc-animal-cat-eye-good"), "notacolour");
});

test("[TVR-8] all three cards import the helper from the shared module", () => {
  // THE RED INPUT: a card that calls applyCardThemeVars without importing it. The bundler
  // fails loudly, so this is cheap — but it also pins that the three cards share ONE
  // implementation rather than growing three that drift, which is the replica problem this
  // repo keeps paying for.
  // BOTH ASSERTIONS MATCH AN `import` STATEMENT, not a bare mention. The first version of
  // the second one was `match(src, /animalHslComponents/)`, which the CALL SITE satisfies
  // on its own — so removing the import left this green while the card would throw a
  // ReferenceError on its first render. Ablation is what showed it, and it is the same
  // mistake that was actually made while writing this feature: the call went in first and
  // the import was missed.
  const imports = (src, what, file) => {
    const re = new RegExp(
      String.raw`import\s*\{[^}]*\b${what}\b[^}]*\}\s*from\s*"[^"]*${file}"`,
    );
    return re.test(src);
  };
  for (const [name, src] of CARDS) {
    assert.ok(imports(src, "applyCardThemeVars", "_shared\\.js"),
      `${name}: must IMPORT applyCardThemeVars from the shared module — three cards ` +
      "sharing one implementation is what keeps this out of the replica register");
    assert.ok(imports(src, "animalHslComponents", "apply-tokens\\.js"),
      `${name}: must IMPORT animalHslComponents — passing it at the call site without ` +
      "importing it throws a ReferenceError on the first render, and a test that only " +
      "greps for the name cannot see the difference");
  }
});
