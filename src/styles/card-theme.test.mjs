// Run: node --test src/styles/card-theme.test.mjs
//
// [CVT-*] THE VA THEME ON A DASHBOARD CARD — opt-in, and reversible.
//
// Dashboard cards wear the HA theme because nothing ever applied a VA theme to them; the
// panel calls applyThemeToCard on every render and the cards never did. This is the opt-in
// half. Two properties carry the whole feature and neither is obvious from reading it:
//
//   The sensor is found by ATTRIBUTE. `sensor.${slug}_theme_state` is the construction that
//   produced issue #81 — Home Assistant slugs an entity id from the TRANSLATED name at
//   creation time, so a derived id is wrong on every localized install and wrong again for
//   anyone who renamed the entity. [CVT-3] is a German-slugged sensor, and it is the test
//   that goes red if someone "simplifies" the lookup back to a template string.
//
//   Turning it OFF must repaint, not skip. The writer removes every registry token it is
//   not handed, so the disabled call is what returns the card to the HA theme. An early
//   return leaves the old palette welded to the host until a reload. [CVT-5].
//
// Coverage
// --------
// [CVT-1] a card with the option off paints nothing, and still CLEARS a previous paint
// [CVT-2] a card with the option on resolves the sensor's raw triplet into tokens
// [CVT-3] the sensor is matched on vacuum_entity_id, NOT on a slugged entity id
// [CVT-4] two vacuums on one dashboard resolve independently
// [CVT-5] turning the option off removes the tokens the previous render set

import { test } from "node:test";
import assert from "node:assert/strict";

import { findThemeSensor, resolveVaTokens, applyVaThemeToCard } from "./card-theme.js";

/** A host that records what the writer does to it — the writer only ever uses
 *  style.setProperty / style.removeProperty, which is all this needs to stand in for. */
function fakeHost() {
  const props = new Map();
  return {
    props,
    style: {
      setProperty: (k, v) => props.set(k, v),
      removeProperty: (k) => props.delete(k),
      getPropertyValue: (k) => props.get(k) ?? "",
    },
  };
}

const themeSensor = (vacuumEntityId, { tokens = {}, colors = {}, alpha = {}, id = "t1" } = {}) => ({
  state: "Some Theme",
  attributes: {
    vacuum_entity_id: vacuumEntityId,
    card_theme: { theme_id: id, tokens, colors, alpha },
    working_draft: { tokens: {}, colors: {}, alpha: {} },
  },
});

const hassWith = (states) => ({ states });

test("[CVT-1] option off paints nothing", () => {
  const host = fakeHost();
  const hass = hassWith({
    "sensor.whatever": themeSensor("vacuum.alfred", { colors: { "--evcc-accent": "#ff0000" } }),
  });

  const painted = applyVaThemeToCard(host, hass, "vacuum.alfred", false);

  assert.equal(painted, false, "a card that did not opt in must not be themed");
  assert.equal(host.props.get("--evcc-accent"), undefined,
    "nothing from the VA theme may land on a card that did not ask for it");
});

test("[CVT-2] option on resolves the raw triplet into real tokens", () => {
  const hass = hassWith({
    "sensor.anything_at_all": themeSensor("vacuum.alfred", {
      colors: { "--evcc-accent": "#c9541e", "--evcc-surface-base": "#0a0a09" },
    }),
  });

  const tokens = resolveVaTokens(hass, "vacuum.alfred");
  assert.ok(tokens, "an active theme must resolve");
  assert.equal(tokens["--evcc-accent"], "#c9541e", "a colour set by the theme must survive the merge");

  const host = fakeHost();
  assert.equal(applyVaThemeToCard(host, hass, "vacuum.alfred", true), true);
  assert.equal(host.props.get("--evcc-accent"), "#c9541e", "...and reach the host");
});

test("[CVT-3] the sensor is found by ATTRIBUTE, not by a slugged entity id", () => {
  // THE RED INPUT, and the reason this file exists. The entity id here is German-slugged
  // and shares no substring with the vacuum's object id — exactly what HA produces on a
  // localized install, and exactly what defeats `sensor.${objectId}_theme_state`.
  const hass = hassWith({
    "sensor.saugwischroboter_designzustand": themeSensor("vacuum.saugwischroboter_s7_maxv", {
      colors: { "--evcc-accent": "#00ff00" },
    }),
    // A decoy on another vacuum, so "find any theme sensor" is not good enough either.
    "sensor.other_theme_state": themeSensor("vacuum.someone_else", {
      colors: { "--evcc-accent": "#0000ff" },
    }),
  });

  const found = findThemeSensor(hass, "vacuum.saugwischroboter_s7_maxv");
  assert.ok(found, "a localized entity id must still be found");
  assert.equal(found.attributes.card_theme.theme_id, "t1");

  const tokens = resolveVaTokens(hass, "vacuum.saugwischroboter_s7_maxv");
  assert.equal(tokens["--evcc-accent"], "#00ff00", "and must resolve to ITS theme, not the decoy's");

  // A vacuum with no sensor at all is a clean null, not the decoy.
  assert.equal(findThemeSensor(hass, "vacuum.nothing_here"), null);
  assert.equal(resolveVaTokens(hass, "vacuum.nothing_here"), null);
});

test("[CVT-4] two vacuums on one dashboard resolve independently", () => {
  const hass = hassWith({
    "sensor.a": themeSensor("vacuum.alfred", { id: "ta", colors: { "--evcc-accent": "#111111" } }),
    "sensor.b": themeSensor("vacuum.ivy", { id: "tb", colors: { "--evcc-accent": "#222222" } }),
  });

  assert.equal(resolveVaTokens(hass, "vacuum.alfred")["--evcc-accent"], "#111111");
  assert.equal(resolveVaTokens(hass, "vacuum.ivy")["--evcc-accent"], "#222222");
});

test("[CVT-5] turning the option OFF removes what a previous render painted", () => {
  // The property an early return would silently break: the writer clears by being CALLED
  // with nothing, so skipping the call leaves the old palette welded to the host.
  const host = fakeHost();
  const hass = hassWith({
    "sensor.x": themeSensor("vacuum.alfred", { colors: { "--evcc-accent": "#c9541e" } }),
  });

  applyVaThemeToCard(host, hass, "vacuum.alfred", true);
  assert.equal(host.props.get("--evcc-accent"), "#c9541e", "precondition: it is painted");

  const painted = applyVaThemeToCard(host, hass, "vacuum.alfred", false);

  assert.equal(painted, false);
  assert.equal(host.props.get("--evcc-accent"), undefined,
    "turning it off must hand the card back to the HA theme, not strand the last palette");
});


test("[CVT-6] a theme's font travels with everything else", () => {
  // FONTS NEEDED NO NEW CODE, and this test exists to record why rather than to add any.
  // Three facts, each measured on a live install 2026-11-16:
  //
  //   `--evcc-font-family` is a THEME-REGISTRY token (theme-tokens/foundations.js), so
  //   applyDynamicTheme already writes it inline alongside the colours.
  //
  //   The @font-face rules are already in document.head: the cards bundle calls
  //   `ensureFontFacesInDocument()` at MODULE LOAD (cards-standalone.js), and the
  //   integration loads that bundle on every HA page. Chromium ignores @font-face inside a
  //   shadow tree, which is the whole reason that document-level call exists.
  //
  //   A real theme ("Warm Light") sets a SYSTEM stack — "Segoe UI", "Aptos", system-ui —
  //   which needs no face registration at all.
  //
  // So the only link that was not directly observed is this one: that the resolver carries
  // the token into its output rather than dropping it with the non-colour keys. That is
  // what this pins, and it is the part a future refactor could silently break.
  //
  // ⚠ `document.fonts.check()` IS NOT EVIDENCE and must not be used as it. Measured on the
  // same install it returned FALSE for OpenDyslexic, which IS declared in the head, and
  // TRUE for Atkinson and Lexend, which are not — it answers true for a family with no
  // registered faces. fonts.js documents this; it is recorded here because this is the
  // test someone would reach for it in.
  const STACK = '"Segoe UI", "Aptos", system-ui, sans-serif';
  const hass = hassWith({
    "sensor.whatever": themeSensor("vacuum.alfred", {
      tokens: { "--evcc-font-family": STACK },
      colors: { "--evcc-accent": "#8C6A3C" },
    }),
  });

  const tokens = resolveVaTokens(hass, "vacuum.alfred");
  assert.equal(tokens["--evcc-font-family"], STACK,
    "the font is a theme token like any other; dropping it would make a themed card " +
    "wear the theme's colours in the HA theme's typeface");

  // And it reaches the host, which is where the card's CSS reads it from.
  const host = fakeHost();
  applyVaThemeToCard(host, hass, "vacuum.alfred", true);
  assert.equal(host.props.get("--evcc-font-family"), STACK);

  // The a11y override is a DIFFERENT token and must not be touched by theming: the
  // font-family read is var(--evcc-a11y-font-family, var(--evcc-font-family, ...)), so
  // accessibility wins over the theme by sitting earlier in the chain. A theme that set
  // the a11y token would override a user's accessibility choice.
  assert.equal(host.props.get("--evcc-a11y-font-family"), undefined,
    "theming must never write the accessibility font token");
});
