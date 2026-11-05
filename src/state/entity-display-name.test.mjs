// Run: node --test src/state/entity-display-name.test.mjs
//
// Coverage targets — src/state/entity-display-name.js :: entityDisplayName
//   [EDN-1] on a 2026.11 core the COMPOSED name wins over the friendly_name attribute
//   [EDN-2] on a pre-2026.4 core, where the helper does not exist, friendly_name still answers
//   [EDN-3] HA is called with the STATE OBJECT and NO name argument — its own default applies
//   [EDN-4] an empty compose does not blank a name we can still read the old way
//   [EDN-5] an unknown entity answers "" so each caller keeps its own last resort
//   [EDN-6] a supplied state object is used without a second lookup through hass.states
//   [EDN-7] no hass at all (first paint) degrades instead of throwing
//
// WHY. 2026.11 composes an entity's displayed name from its context instead of reading one
// attribute, so a card still reading `friendly_name` disagrees with every built-in card on
// the same dashboard. The composed answer comes from `hass.formatEntityName`, which arrived
// in 2026.4 — and `hacs.json` declares a 2025.6.0 floor, so for installs from the floor
// through 2026.3 the function is absent and the attribute is the only answer there is.
//
// THE ONE THAT MATTERS IS [EDN-2]. A fallback nobody exercises is indistinguishable from a
// fallback that does not work, and this one carries every install below 2026.4 — the
// majority of them on the day this shipped. It is written as an ABLATION: the helper is
// deleted from the hass object, which is exactly the shape of an old core.
//
// THE INPUTS THAT MAKE EACH ONE RED:
//   [EDN-1] drop the formatEntityName branch — the composed name is ignored and the test
//           reads the raw friendly_name instead.
//   [EDN-2] call hass.formatEntityName without the `typeof === "function"` guard — an old
//           core raises TypeError instead of falling back.
//   [EDN-3] pass a second argument, e.g. [{type:"device"},{type:"entity"}] — the arity
//           assertion fails. That spelling pins us to today's built-in composition and
//           drops the parent_device segment child devices rely on.
//   [EDN-4] return the composed value without the truthiness check — an entity HA cannot
//           compose renders blank instead of showing its old name.
//   [EDN-5] return `entityId` instead of "" — every caller's own fallback becomes dead code.

import { test } from "node:test";
import assert from "node:assert/strict";

import { entityDisplayName } from "./entity-display-name.js";

const ENTITY = "sensor.thermostat_temperature";

/** A state object carrying only what this helper reads. */
function makeState(friendlyName) {
  return {
    entity_id: ENTITY,
    state: "21.5",
    attributes: friendlyName == null ? {} : { friendly_name: friendlyName },
  };
}

/** A 2026.4+ hass whose formatEntityName records how it was called. */
function makeModernHass(composed, friendlyName = "Temperature") {
  const calls = [];
  const state = makeState(friendlyName);
  return {
    calls,
    state,
    hass: {
      states: { [ENTITY]: state },
      formatEntityName: (...args) => {
        calls.push(args);
        return composed;
      },
    },
  };
}

/** A pre-2026.4 hass: same shape, the helper simply does not exist. */
function makeOldHass(friendlyName = "Temperature") {
  const state = makeState(friendlyName);
  return { state, hass: { states: { [ENTITY]: state } } };
}

test("[EDN-1] the composed name wins over the friendly_name attribute", () => {
  const { hass } = makeModernHass("Thermostat Temperature", "Temperature");
  assert.equal(entityDisplayName(hass, ENTITY), "Thermostat Temperature");
});

test("[EDN-2] ABLATION: with no formatEntityName, friendly_name still answers", () => {
  const { hass } = makeOldHass("Thermostat Temperature");
  // Exactly the shape of every core from the 2025.6.0 floor through 2026.3.
  assert.equal(typeof hass.formatEntityName, "undefined", "the ablation must really be absent");
  assert.equal(entityDisplayName(hass, ENTITY), "Thermostat Temperature");
});

test("[EDN-3] HA is handed the state object and NO name argument", () => {
  const { hass, calls, state } = makeModernHass("Thermostat Temperature");
  entityDisplayName(hass, ENTITY);

  assert.equal(calls.length, 1, "called once");
  assert.equal(
    calls[0].length,
    1,
    "a second argument pins us to one composition and drops parent_device; " +
      "omitting it is what applies HA's own DEFAULT_ENTITY_NAME"
  );
  assert.equal(calls[0][0], state, "the STATE OBJECT, not its attributes");
});

test("[EDN-4] an empty or whitespace compose falls back instead of blanking", () => {
  for (const empty of ["", "   ", null, undefined]) {
    const { hass } = makeModernHass(empty, "Thermostat Temperature");
    assert.equal(
      entityDisplayName(hass, ENTITY),
      "Thermostat Temperature",
      `compose returning ${JSON.stringify(empty)} must not blank the name`
    );
  }
});

test("[EDN-5] an unknown entity answers \"\", not the id", () => {
  const { hass } = makeModernHass("Thermostat Temperature");
  assert.equal(entityDisplayName(hass, "sensor.does_not_exist"), "");
  assert.equal(entityDisplayName(hass, null), "");
  assert.equal(entityDisplayName(hass, undefined), "");
});

test("[EDN-6] a supplied state object is used without a hass.states lookup", () => {
  const { hass, calls } = makeModernHass("Thermostat Temperature");
  const orphan = makeState("Orphan Name");
  // The search loop already holds the state object for every entity in the house.
  hass.states = new Proxy({}, {
    get() {
      throw new Error("hass.states must not be read when a state object was supplied");
    },
  });

  assert.equal(entityDisplayName(hass, "sensor.anything", orphan), "Thermostat Temperature");
  assert.equal(calls[0][0], orphan, "the supplied object is what HA is asked about");
});

test("[EDN-7] no hass at all degrades rather than throwing", () => {
  assert.equal(entityDisplayName(null, ENTITY), "");
  assert.equal(entityDisplayName(undefined, ENTITY), "");
  // First paint: the card has a state object in hand before hass is wired.
  assert.equal(entityDisplayName(undefined, ENTITY, makeState("Thermostat Temperature")),
    "Thermostat Temperature");
});
