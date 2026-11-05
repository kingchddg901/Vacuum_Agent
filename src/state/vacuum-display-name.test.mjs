// Run: node --test src/state/vacuum-display-name.test.mjs
//
// Coverage targets — src/state/core.js :: vacuumDisplayName
//   [VDN-1] the user's own panel title wins over the upstream friendly_name
//   [VDN-2] an UNSET title falls through to friendly_name — it must not read "Vacuum Agent"
//   [VDN-3] a blank/whitespace title falls through too
//   [VDN-4] no snapshot yet (first paint) still renders friendly_name
//   [VDN-5] nothing at all degrades to the formatted object id
//   [VDN-6] a title is trimmed, not passed through with its padding
//   [VDN-7] HA's COMPOSED name (2026.11) beats the attribute — and the title still beats both
//
// WHY. `panel_title` is settable per vacuum via `setup_set_panel_title`, and the SIDEBAR has
// always honoured it — but the dashboard snapshot never carried it, so this header showed the
// upstream integration's `friendly_name` and nothing else. Renaming a vacuum moved its sidebar
// entry and left the card unchanged: a setting that could be written and never read, the same
// shape as `saveRoomRules` having no action behind it.
//
// THE TRAP [VDN-2] GUARDS. The backend has `effective_panel_title()`, which answers the
// SIDEBAR's question and falls back to "Vacuum Agent". Shipping THAT into the snapshot would
// replace a perfectly good friendly_name with a generic label on every vacuum nobody renamed.
// The snapshot ships the raw value, null when unset, and this test is what keeps it raw.
//
// THE INPUT THAT MAKES [VDN-1] RED: delete the panelTitle branch from vacuumDisplayName. The
// header goes back to friendly_name and the user's own name is ignored again.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyCoreState } from "./core.js";

/**
 * A card with just the surfaces vacuumDisplayName reads.
 *
 * The name no longer comes from a stubbed `vacuumAttrs()` — it is resolved through
 * `entityDisplayName`, which reads the real `hass.states` entry. So the fixture builds a
 * real state object: stubbing the accessor would have tested a path production no longer
 * takes, which is the whole failure mode this file is meant to catch.
 */
function makeState({ panelTitle, friendlyName, objectId = "alfred", formatEntityName } = {}) {
  const proto = {};
  applyCoreState(proto);
  const s = Object.create(proto);
  const entityId = `vacuum.${objectId}`;

  s.config = { vacuum_entity_id: entityId };
  s.hass = {
    states:
      friendlyName == null
        ? {}
        : {
            [entityId]: {
              entity_id: entityId,
              state: "docked",
              attributes: { friendly_name: friendlyName },
            },
          },
  };
  if (formatEntityName) s.hass.formatEntityName = formatEntityName;

  s.dashboardSnapshot = () =>
    panelTitle === undefined ? null : { panel_title: panelTitle };
  s.vacuumObjectId = () => objectId;
  return s;
}

test("[VDN-1] the user's own title wins over the upstream name", () => {
  const s = makeState({ panelTitle: "Downstairs", friendlyName: "Robin  Robin" });
  assert.equal(s.vacuumDisplayName(), "Downstairs");
});

test("[VDN-2] an UNSET title falls through — never the sidebar's generic fallback", () => {
  for (const unset of [null, undefined]) {
    const s = makeState({ panelTitle: unset, friendlyName: "Eufy Alfred" });
    assert.equal(
      s.vacuumDisplayName(),
      "Eufy Alfred",
      `panel_title ${unset} must not suppress the friendly name`
    );
    assert.notEqual(s.vacuumDisplayName(), "Vacuum Agent");
  }
});

test("[VDN-3] a blank or whitespace title falls through as unset", () => {
  for (const blank of ["", "   ", "\t"]) {
    const s = makeState({ panelTitle: blank, friendlyName: "Eufy Alfred" });
    assert.equal(s.vacuumDisplayName(), "Eufy Alfred", `${JSON.stringify(blank)} is not a name`);
  }
});

test("[VDN-4] no snapshot yet still renders the friendly name", () => {
  // First paint: the card renders before the snapshot service has answered.
  const s = makeState({ friendlyName: "Robo Rock Ivy" });
  s.dashboardSnapshot = () => null;
  assert.equal(s.vacuumDisplayName(), "Robo Rock Ivy");
});

test("[VDN-5] with neither, the object id is formatted rather than shown raw", () => {
  const s = makeState({ panelTitle: null, friendlyName: null, objectId: "robin_dreame" });
  assert.equal(s.vacuumDisplayName(), "Robin Dreame");
});

test("[VDN-6] a title is trimmed, not passed through with its padding", () => {
  const s = makeState({ panelTitle: "  Upstairs  ", friendlyName: "Eufy Alfred" });
  assert.equal(s.vacuumDisplayName(), "Upstairs");
});

test("[VDN-7] HA's composed name beats the attribute, and the title beats the composed name", () => {
  // 2026.11: the built-in cards show device-then-entity, so an untitled vacuum must follow.
  const composed = () => "Hallway Alfred";

  const untitled = makeState({
    panelTitle: null,
    friendlyName: "Alfred",
    formatEntityName: composed,
  });
  assert.equal(untitled.vacuumDisplayName(), "Hallway Alfred");

  // THE INPUT THAT MAKES THIS RED: route vacuumDisplayName back to `friendly_name` and the
  // header reads "Alfred" while every built-in card beside it reads "Hallway Alfred".
  const titled = makeState({
    panelTitle: "Downstairs",
    friendlyName: "Alfred",
    formatEntityName: composed,
  });
  assert.equal(
    titled.vacuumDisplayName(),
    "Downstairs",
    "the one name the user chose still outranks anything HA composes"
  );
});
