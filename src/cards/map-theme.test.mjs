/**
 * ============================================================
 * THE NESTED MAP HOST GETS THE THEME TOO
 * ============================================================
 *
 * THE DEFECT, measured 2026-11-16 against the built bundles.
 *
 * <eufy-vacuum-map> (cards/vacuum-map-host.js) is a SEPARATE custom element with its own
 * shadow root, loaded as its own served module, and it injects `foundationTokens` into
 * that root. foundation DECLARES ~425 --evcc-* tokens there, and a declaration in an
 * element's own tree beats a value inherited from the card above it.
 *
 * So the dashboard card painted the Vacuum Agent theme onto ITSELF -- the frame followed
 * Warm Light -- while the map inside it re-derived every surface from the Home Assistant
 * theme. Measured: the card resolved --evcc-surface-panel to Warm Light's #E7E0D3, and a
 * host injecting the same foundationTokens text resolved it to
 * color-mix(in srgb, #1c2127 85%, #f0f2f5 15%). That is a dark map box inside a light
 * card, and it is visible in every screenshot taken from that dashboard.
 *
 * THIS IS THE THIRD INSTANCE OF ONE SHAPE. styles/apply-theme.js already bridges the same
 * layer onto the modal host (renders outside the shadow root) and onto the mounted theme
 * preview card (renders inside its own). Its comment records measuring exactly this:
 * "the preview tracked the editor only for tokens foundation does NOT declare". The card
 * already forwarded hass, config, language and the snapshot to the map host; the theme was
 * the one thing it did not.
 *
 * WHY THESE ARE SOURCE ASSERTIONS. The round trip needs a browser, the map module, and a
 * device snapshot before .evcc-map-container exists at all -- the Playwright harness is
 * where that is checked. What a unit test CAN pin is the wiring, and the wiring is what
 * was missing: the bridge existed in apply-theme.js for two other targets and simply was
 * never called for this one.
 *
 * ============================================================
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { MAP_TOKENS } from "../theme-tokens/map.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (...p) => readFileSync(join(REPO, ...p), "utf8");

// Comments are stripped so prose about a name never counts as the name being used --
// the same precaution card-frame.test.mjs takes, for the same reason.
const codeOnly = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

const DASH = codeOnly(read("src", "cards", "dashboard-card.js"));
const MAPCSS = codeOnly(read("src", "styles", "map.js"));
const MAPHOST = codeOnly(read("src", "cards", "vacuum-map-host.js"));

test("[MAP-THEME-1] the map host is a nested shadow root that injects foundationTokens", () => {
  // The PREMISE of everything below. If this stops being true -- the host stops injecting
  // foundation, or stops having its own root -- then the bridge is no longer needed and
  // these tests are enforcing dead weight. Stated so a future reader can tell the
  // difference between "still required" and "cargo".
  assert.match(MAPHOST, /attachShadow\(\s*\{\s*mode:\s*["']open["']\s*\}\s*\)/,
    "vacuum-map-host must still own a shadow root for the shadowing problem to exist");
  assert.match(MAPHOST, /\$\{foundationTokens\}/,
    "vacuum-map-host must still inject foundationTokens into that root — that injection " +
    "is what re-declares --evcc-* and discards the value inherited from the card");
});

test("[MAP-THEME-2] the dashboard card bridges the theme onto the map host", () => {
  // THE RED INPUT: delete _applyThemeToMapHost, or never call it. Nothing else notices:
  // the card still themes correctly, every existing test stays green, and only the map
  // inside it is wrong — which is precisely how this shipped.
  assert.match(DASH, /_applyThemeToMapHost\s*\(\s*\)\s*\{/,
    "dashboard-card must define _applyThemeToMapHost");
  assert.match(DASH, /applyVaThemeToCard\(\s*\n?\s*this\._mapEl\s*,/,
    "_applyThemeToMapHost must pass this._mapEl — passing `this` would re-theme the card " +
    "and leave the nested host exactly as broken as before");
});

test("[MAP-THEME-3] it is called on render AND at map creation", () => {
  // THE RED INPUT, and it is the subtle one: call it only where the map is created. The
  // map is created once and the theme changes on every editor keystroke, so the map would
  // be correct when it first appeared and then drift away from the card for the rest of
  // the session. Calling it only on render is the mirror failure: the map is created
  // AFTER that render, so it would paint unthemed until something else re-rendered.
  const calls = (DASH.match(/this\._applyThemeToMapHost\(\)/g) || []).length;
  assert.ok(calls >= 2,
    `_applyThemeToMapHost must be called at least twice — on render and at creation. ` +
    `Found ${calls}.`);

  const created = DASH.match(/this\._mapEl = document\.createElement\([\s\S]{0,600}/);
  assert.ok(created, "could not find where the map element is created");
  assert.match(created[0], /this\._applyThemeToMapHost\(\)/,
    "the creation path must theme the host before it is appended, so it never paints " +
    "one frame unthemed");
});

test("[MAP-THEME-4] the bridge is unconditional, so turning va_theme OFF strips the paint", () => {
  // THE RED INPUT: guard the call with `if (va_theme)`. applyVaThemeToCard called with
  // enabled=false is NOT a no-op — card-theme.js writes an EMPTY token map, and that empty
  // write is what REMOVES a previous paint. Skipping it would strand the last palette on
  // the map host with no way to clear it short of a reload, while the card around it
  // correctly reverted to the Home Assistant theme.
  const body = DASH.match(/_applyThemeToMapHost\s*\(\s*\)\s*\{[\s\S]*?\n  \}/);
  assert.ok(body, "could not read the body of _applyThemeToMapHost");
  assert.match(body[0], /this\._config\?\.va_theme === true/,
    "the enabled flag must be passed through to applyVaThemeToCard");
  assert.doesNotMatch(body[0], /if\s*\([^)]*va_theme[^)]*\)\s*(\{|return)/,
    "va_theme must be passed as the enabled ARGUMENT, never used to skip the call — " +
    "the disabled call is what undoes a previous paint");
});

test("[MAP-THEME-5] the map floor has its own token, falling through to Surface Panel", () => {
  // THE RED INPUT: point .evcc-map-container straight at --evcc-map-background with no
  // fallback. Every existing install has no value for it, so the floor would go
  // transparent and the card behind it would show through — a change for everyone, from a
  // token meant to change nothing until it is set.
  assert.match(MAPCSS,
    /background:\s*var\(--evcc-map-background,\s*var\(--evcc-surface-panel,\s*#1c2127\)\)/,
    ".evcc-map-container must read --evcc-map-background first and fall through to " +
    "--evcc-surface-panel, so an unset theme is byte-identical to before");

  assert.ok(MAP_TOKENS.some((t) => t.key === "--evcc-map-background"),
    "--evcc-map-background must be registered, or the floor is settable only from YAML");

  // It must be declared NOWHERE: a declaration would make the fallback unreachable, which
  // is the always-declared trap that made --ha-card-background dead on the card frame.
  for (const f of ["src/styles/foundation.js", "src/styles/index.js", "src/styles/map.js"]) {
    assert.doesNotMatch(codeOnly(read(f)), /--evcc-map-background\s*:/,
      `${f} must not DECLARE --evcc-map-background — declaring it kills the ` +
      "--evcc-surface-panel fallback and the token stops being a no-op when unset");
  }
});
