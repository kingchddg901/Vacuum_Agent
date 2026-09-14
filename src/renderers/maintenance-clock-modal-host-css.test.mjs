// Run: node --test src/renderers/maintenance-clock-modal-host-css.test.mjs
//
// Coverage targets — src/renderers/maintenance.js :: renderMaintenanceClockModal
//   [MHC-1] every evcc-* class the counter picker emits is DEFINED in MODAL_HOST_STYLES
//   [MHC-2] the shadow cascade keeps them too (it interpolates the host export)
//   [MHC-3] the TRIGGER's class stays shadow-only — it never renders in the portal
//
// WHY. The picker renders into the body-portal modal host, whose stylesheet is a DIFFERENT
// string from the card's shadow cascade (styles/modal-host.js composes the former from
// `maintenanceModalHostStyles`; `maintenanceStyles` interpolates that same export, so the flow
// is one-way). The candidate rules shipped in the shadow-only half. On the live panel
// 2026-09-13 the modal opened with all six candidates fetched and correct, and rendered them as
// bare inline buttons — a working feature that read as a broken one. A green suite could not see
// it; only the rendered page could. This makes the declaration checkable.
//
// THE INPUT THAT MAKES [MHC-1] RED: move any `.evcc-clock-candidate*` rule back below the
// `maintenanceStyles` marker. The class is still emitted, still styled in the card — and
// undefined in the one cascade that renders it.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyMaintenanceRenderers } from "./maintenance.js";
import { MODAL_HOST_STYLES } from "../styles/modal-host.js";
import { maintenanceStyles } from "../styles/maintenance.js";

/** Render the picker with a candidate list exercising EVERY branch that emits a class. */
function renderPicker() {
  const proto = {};
  applyMaintenanceRenderers(proto);
  const ctx = Object.create(proto);
  ctx.t = (key) => `T(${key})`;
  ctx.tRaw = (key) => `T(${key})`;
  ctx.escapeHtml = (v) => String(v ?? "");

  const state = {
    isMaintenanceClockPickerOpen: () => true,
    maintenanceClockPicker: () => ({
      open: true,
      loading: false,
      error: "an error, so the error branch emits its class too",
      pending: "sensor.pending_one",
      candidates: [
        { entity_id: "sensor.plain", name: "Plain", state: "12", unit: "h" },
        { entity_id: "sensor.current_one", name: "Current", state: "414", unit: "min", is_current: true },
        { entity_id: "sensor.pending_one", name: "Pending", state: "5", unit: "min",
          caveat_key: "maintenance.clock_caveat_bound_part" },
      ],
    }),
  };
  return ctx.renderMaintenanceClockModal({ state, renderers: ctx });
}

/** Every distinct evcc-* class name appearing in a class="..." attribute. */
function emittedClasses(html) {
  const found = new Set();
  for (const m of html.matchAll(/class="([^"]*)"/g)) {
    for (const cls of m[1].split(/\s+/)) if (cls.startsWith("evcc-")) found.add(cls);
  }
  return [...found].sort();
}

test("[MHC-1] every class the picker emits is defined in the cascade that renders it", () => {
  const html = renderPicker();
  const classes = emittedClasses(html);

  // Guard the guard: an empty or tiny set would make this pass vacuously.
  assert.ok(
    classes.length >= 12,
    `expected the picker to emit a real class surface, got ${classes.length}: ${classes}`
  );
  assert.ok(classes.includes("evcc-clock-candidate-caveat"), "the caveat branch must have run");
  assert.ok(classes.includes("evcc-clock-candidate--current"), "the current branch must have run");

  const undefined_ = classes.filter((c) => !MODAL_HOST_STYLES.includes(`.${c}`));
  assert.deepEqual(
    undefined_,
    [],
    `emitted into the body portal but undefined in MODAL_HOST_STYLES: ${undefined_.join(", ")}`
  );
});

test("[MHC-2] the shadow cascade keeps them, via the one-way interpolation", () => {
  for (const cls of emittedClasses(renderPicker())) {
    assert.ok(
      maintenanceStyles.includes(`.${cls}`) || MODAL_HOST_STYLES.includes(`.${cls}`),
      `${cls} is defined in neither cascade`
    );
  }
  // The interpolation is what makes moving a rule INTO the host export lossless.
  assert.ok(
    maintenanceStyles.includes(".evcc-clock-candidate-list"),
    "maintenanceStyles must still carry the candidate rules through its interpolation"
  );
});

test("[MHC-3] the trigger stays shadow-only — it never renders in the portal", () => {
  // The link lives in the Maintenance Items panel header, inside the shadow root. Putting its
  // rule in the host export would say, falsely, that something in the portal wears it.
  assert.ok(maintenanceStyles.includes(".evcc-maintenance-clock-link"));
  assert.equal(
    renderPicker().includes("evcc-maintenance-clock-link"),
    false,
    "the picker must not emit the trigger's class"
  );
});
