// <eufy-vacuum-map> — the embeddable FULL map host (W2b).
//
// Mounts the EXISTING map subsystem (the same VacuumCardState / Renderers / Bindings
// / Actions classes the panel uses) on a small, self-contained custom element, so the
// dashboard card can show the VA-rendered room-blob map with rotate / pan / zoom /
// overlays / zone-draw — reusing every line of the map code rather than rewriting it.
//
// This module statically imports that heavy class graph; the dashboard card loads it
// ONLY via dynamic import() when show_map is on, so esbuild code-splits it into a
// separate chunk and the always-loaded cards bundle stays lean.
//
// W2b-1 (next) wires the real render loop (renderMapRoomView + _bindMap) and the
// host shim (isMapViewActive→true, _scheduleRender, setSnapshot, the frame pollers).
// This file is the SHELL + the chunk boundary.

import { VacuumCardState } from "../state/index.js";
import { VacuumCardRenderers } from "../renderers/index.js";
import { VacuumCardBindings } from "../bindings/index.js";
import { VacuumCardActions } from "../actions/index.js";
import { applyCardDomHelpers } from "../bindings/core.js";
import { VIEWS } from "../render-cycle.js";
import { mapStyles } from "../styles/map.js";

// Hold the heavy graph in this chunk (W2b-1 instantiates these in the host shim).
const MAP_DEPS = {
  VacuumCardState, VacuumCardRenderers, VacuumCardBindings, VacuumCardActions,
  applyCardDomHelpers, VIEWS,
};

class EufyVacuumMap extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._deps = MAP_DEPS;   // retained for W2b-1 wiring (prevents tree-shake)
    this._hass = null;
    this._config = null;
    this._snapshot = null;
  }

  set hass(h) { this._hass = h; this._render(); }
  set config(c) { this._config = c; }
  setSnapshot(s) { this._snapshot = s; this._render(); }

  connectedCallback() { this._render(); }

  _render() {
    // STUB — W2b-1 replaces with: ctx = {card:this, state, renderers, vacuumStatus};
    // shadowRoot.innerHTML = `<style>${mapStyles}…</style>` + renderMapRoomView(ctx);
    // then this._bindings._bindMap().
    this.shadowRoot.innerHTML =
      `<style>${mapStyles}</style>` +
      `<div class="evcc-map-view" style="padding:14px;font:0.8rem sans-serif;color:var(--evcc-text-muted,#888)">Map host loaded — wiring in progress.</div>`;
  }
}

if (!customElements.get("eufy-vacuum-map")) {
  customElements.define("eufy-vacuum-map", EufyVacuumMap);
}

export { EufyVacuumMap };
