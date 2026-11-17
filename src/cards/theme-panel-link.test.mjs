// Run: node --test src/cards/theme-panel-link.test.mjs
//
// [PNL-*] THE LINK FROM A CARD'S EDITOR TO ITS THEME PANEL.
//
// His ask 2026-11-16: the tokens a card reads are edited in the panel's Theme tab, and
// nothing in the card's own config UI said where that was.
//
// IT CREATES TWO REPLICAS, and that is what this file is mostly about. Neither can be
// derived from the other at runtime, so both are pinned by reading the other side:
//
//   1. THE PANEL URL. panels.py builds `eufy-vacuum-<object_id>` in Python; the card
//      editor has to build the same string in JavaScript. [PNL-1] reads the Python.
//   2. THE VIEW ID. The hash names a view from src/render-cycle.js's VIEWS, which the
//      cards bundle deliberately does not import — render-cycle drags the whole panel
//      view machinery in behind it. [PNL-2] reads that file.
//
// A drift in either is SILENT and identical in shape: the button still renders, still
// navigates, and lands on Home Assistant's "panel not found" or on the wrong tab.
//
// Coverage
// --------
// [PNL-1] the url matches panels.py's panel_url_for, read from the Python
// [PNL-2] the hash matches VIEWS.THEME, read from render-cycle.js
// [PNL-3] the link is withheld unless a vacuum is chosen AND that panel is registered
// [PNL-4] all three editors render AND wire it — a rendered button nothing wired is dead

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { themePanelPath, THEME_VIEW_HASH, renderThemePanelLink } from "./_shared.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (...p) => readFileSync(join(REPO, ...p), "utf8");

test("[PNL-1] the panel url matches panels.py, read from the Python", () => {
  // THE RED INPUT: renaming the panel on either side. The Python owns the real url --
  // it is what HA registers -- so this reads the f-string out of panels.py rather than
  // restating it, and a rename there reddens here instead of shipping a dead button.
  const py = read("custom_components", "eufy_vacuum", "panels.py");
  const m = py.match(/return f"([^"]*\{object_id\}[^"]*)"/);
  assert.ok(m, "could not find panel_url_for's f-string in panels.py");
  const expected = m[1].replace("{object_id}", "alfred");
  assert.equal(themePanelPath("vacuum.alfred"), expected);
  assert.equal(themePanelPath("vacuum.alfred"), "eufy-vacuum-alfred");

  // The object id is the part after the dot, and a bare id is tolerated.
  assert.equal(themePanelPath("vacuum.robin"), "eufy-vacuum-robin");
  assert.equal(themePanelPath("alfred"), "eufy-vacuum-alfred");
});

test("[PNL-2] the hash matches VIEWS.THEME, read from render-cycle.js", () => {
  // THE RED INPUT: renaming the view id. The panel routes the hash through setView, which
  // only accepts a real VIEWS value -- so a drift here means the link reaches the panel
  // and silently lands on whatever tab was remembered, which looks like the link working.
  const rc = read("src", "render-cycle.js");
  const m = rc.match(/THEME:\s*"([^"]+)"/);
  assert.ok(m, "could not find VIEWS.THEME in render-cycle.js");
  assert.equal(THEME_VIEW_HASH, m[1]);
});

test("[PNL-3] the link is withheld unless the panel actually exists", () => {
  // THE RED INPUT: rendering it whenever a vacuum is set. A vacuum can be mid-setup, or
  // have had its panel removed, while its room switches are still there -- so inferring
  // the panel from the vacuum would navigate to Home Assistant's "panel not found".
  // hass.panels is HA's own map of what is registered: the direct truth.
  const t = (k) => k;
  const withPanel = { panels: { "eufy-vacuum-alfred": {} } };

  assert.equal(renderThemePanelLink({ t, hass: withPanel, vacuumEntityId: "" }), "",
    "no vacuum chosen yet");
  assert.equal(renderThemePanelLink({ t, hass: withPanel, vacuumEntityId: undefined }), "",
    "no vacuum at all");
  assert.equal(renderThemePanelLink({ t, hass: {}, vacuumEntityId: "vacuum.alfred" }), "",
    "hass with no panels map");
  assert.equal(renderThemePanelLink({ t, hass: { panels: {} }, vacuumEntityId: "vacuum.alfred" }), "",
    "panels map that does not hold THIS vacuum's panel");
  assert.equal(
    renderThemePanelLink({ t, hass: withPanel, vacuumEntityId: "vacuum.robin" }), "",
    "a DIFFERENT vacuum's panel being registered is not this one's");

  const ok = renderThemePanelLink({ t, hass: withPanel, vacuumEntityId: "vacuum.alfred" });
  assert.match(ok, /data-va-theme-panel="eufy-vacuum-alfred"/);
});

test("[PNL-4] all three editors render it AND wire it", () => {
  // THE RED INPUT, and it is the one that costs a release: adding the button to an editor
  // and not the handler. It renders, it looks right, and clicking it does nothing --
  // which no test about the helper can see, because the helper is correct.
  for (const [name, src] of [
    ["room-card.js", read("src", "room-card.js")],
    ["dashboard-card.js", read("src", "cards", "dashboard-card.js")],
    ["profile-card.js", read("src", "cards", "profile-card.js")],
  ]) {
    assert.match(src, /renderThemePanelLink\(\{/, `${name}: must RENDER the link`);
    assert.match(src, /wireThemePanelLink\(this\.shadowRoot\)/, `${name}: must WIRE it`);
    assert.match(src, /THEME_PANEL_LINK_CSS/, `${name}: must include its CSS`);
    assert.match(src, /renderThemePanelLink, wireThemePanelLink, THEME_PANEL_LINK_CSS,/,
      `${name}: must import all three from _shared.js`);
  }
});
