/**
 * ============================================================
 * RENDERERS: SETUP
 * ============================================================
 *
 * PURPOSE
 * -------
 * Renders the Setup tab as a data-driven step list. The backend
 * declares each vacuum's setup.steps in its adapter config; the
 * card iterates that list and renders the appropriate view per
 * step ID. There is no longer a hardcoded "step 1 / step 2"
 * structure — the adapter owns the truth, the card displays.
 *
 * Step IDs handled today (closed enum from backend):
 *   - "add_vacuum"         → register the vacuum entity
 *   - "import_active_map"  → import a map from upstream cloud
 *                            (Eufy-conditional; brands with always-on
 *                            map exposure omit this step)
 *   - "save_rooms"         → configure rooms (floor types, phantom
 *                            filtering, drift review)
 *
 * The save_rooms step is special: even after being marked complete,
 * room drift (new rooms discovered, configured rooms missing) can
 * re-open it. The drift display surfaces these as actionable items
 * with Configure / Reject / Force-Remove buttons.
 *
 * ============================================================
 */

const FLOOR_TYPE_OPTIONS = [
  { value: "hardwood",         label: "Hardwood"         },
  { value: "laminate",         label: "Laminate"         },
  { value: "tile",             label: "Tile"             },
  { value: "marble",           label: "Marble"           },
  { value: "granite",          label: "Granite"          },
  { value: "concrete",         label: "Concrete"         },
  { value: "carpet_low_pile",  label: "Low-Pile Carpet"  },
  { value: "carpet_high_pile", label: "High-Pile Carpet" },
];

export function applySetupRenderers(proto) {

  /**
   * Render the Setup tab.
   *
   * Iterates vacuumEntry.setup_steps and dispatches per-step rendering
   * based on each step's `id`. The badge number reflects the step's
   * position in the adapter-declared list, not a hardcoded sequence —
   * a brand with two steps shows "1, 2"; a brand with three shows
   * "1, 2, 3".
   *
   * @param {{ state: object, card: object }} ctx
   * @returns {string} HTML string.
   */
  proto.renderSetupView = function (ctx) {
    const { state, card } = ctx;

    const vacuumEntityId = card._config?.vacuum_entity_id ?? "";
    const status         = state.setupStatus?.()     ?? null;
    const loading        = state.setupLoading?.()    ?? false;
    const error          = state.setupError?.()      ?? null;
    const lastResult     = state.setupLastResult?.() ?? null;

    /* -------------------------------------------------------
       Resolve this card's vacuum entry from the status response
       ------------------------------------------------------- */
    const vacuums     = Array.isArray(status?.vacuums) ? status.vacuums : [];
    const vacuumEntry = vacuums.find((v) => v.vacuum_entity_id === vacuumEntityId) ?? null;

    /* Adapter-declared step list (new contract). Falls back to a
       legacy two-step list when the response predates the contract;
       this keeps the card functional during a partial backend
       rollout and against older snapshots of state. */
    const steps = (Array.isArray(vacuumEntry?.setup_steps) && vacuumEntry.setup_steps.length)
      ? vacuumEntry.setup_steps
      : _legacyStepsFallback(vacuumEntry);

    const drift = vacuumEntry?.room_drift ?? null;

    /* Room editor state — same as before; the save_rooms step
       drives this. */
    const openMapId    = state.setupRoomEditorOpenMapId?.()    ?? null;
    const loadingMapId = state.setupRoomEditorLoadingMapId?.() ?? null;
    const rooms        = state.setupRoomEditorRooms?.()        ?? [];
    const saving       = state.setupRoomEditorSaving?.()       ?? false;

    const deletePendingMapId = state.setupDeletePendingMapId?.() ?? null;
    const deleteStage        = state.setupDeleteStage?.()        ?? null;
    const deleteTypedToken   = state.setupDeleteTypedToken?.()   ?? "";
    const deleteDeleting     = state.setupDeleteDeleting?.()     ?? false;

    const enabledIdSet  = new Set(
      (state.setupRoomEditorEnabledIds?.() ?? []).map(String),
    );
    const floorTypesMap = state.setupRoomEditorFloorTypesMap?.() ?? {};

    const importedMaps = (vacuumEntry?.maps ?? []).filter((m) => m.imported);

    /* -------------------------------------------------------
       Transient feedback (loading / error / last action)
       ------------------------------------------------------- */
    const loadingHtml = loading
      ? `<div class="evcc-setup-result info">Working…</div>`
      : "";

    const errorHtml = error && !loading
      ? `<div class="evcc-setup-result error">${this.escapeHtml(String(error))}</div>`
      : "";

    const lastResultHtml = (() => {
      if (!lastResult || loading) return "";
      const s   = lastResult.status  ?? "";
      const msg = lastResult.message ?? "";
      if (s === "error" || s === "blocked") {
        return `<div class="evcc-setup-result error">${this.escapeHtml(msg)}</div>`;
      }
      if (msg) {
        return `<div class="evcc-setup-result success">${this.escapeHtml(msg)}</div>`;
      }
      return "";
    })();

    /* -------------------------------------------------------
       Per-step body renderers
       -------------------------------------------------------
       Each function returns the HTML for the step's body
       region. The outer step container (badge + label) is
       added by renderStep().
       ------------------------------------------------------- */

    const renderAddVacuumBody = (step) => {
      if (step.completed) {
        return `
          <div class="evcc-setup-step-body">
            Vacuum registered.
            <div class="evcc-setup-entity-id">${this.escapeHtml(vacuumEntityId)}</div>
          </div>
        `;
      }
      return `
        <div class="evcc-setup-step-body">
          Register this vacuum with the integration so it can be managed.
          <div class="evcc-setup-entity-id">${this.escapeHtml(vacuumEntityId)}</div>
        </div>
        <button class="evcc-setup-btn"
                data-action="setup-add-vacuum"
                ${loading ? "disabled" : ""}>
          Add Vacuum
        </button>
      `;
    };

    const renderImportActiveMapBody = (step) => {
      const addVacuumDone = _isStepCompleted(steps, "add_vacuum");
      const mapCount      = importedMaps.length;

      if (!addVacuumDone) {
        return `<div class="evcc-setup-step-body muted">Complete Add Vacuum first.</div>`;
      }

      const summaryHtml = mapCount > 0
        ? `<div class="evcc-setup-step-body muted">${mapCount} map${mapCount === 1 ? "" : "s"} imported.</div>`
        : `<div class="evcc-setup-step-body">Import the vacuum's currently active map. Make sure it has completed a mapping run first.</div>`;

      const buttonLabel = mapCount > 0 ? "Import Another Map" : "Import Active Map";
      const buttonClass = mapCount > 0 ? "secondary" : "";

      return `
        ${summaryHtml}
        <button class="evcc-setup-btn ${buttonClass}"
                data-action="setup-import-map"
                ${loading ? "disabled" : ""}>
          ${buttonLabel}
        </button>
      `;
    };

    const renderSaveRoomsBody = (step) => {
      const importStep      = steps.find((s) => s.id === "import_active_map");
      const importNeeded    = Boolean(importStep);
      const importDone      = !importStep || importStep.completed;
      const addVacuumDone   = _isStepCompleted(steps, "add_vacuum");

      if (!addVacuumDone) {
        return `<div class="evcc-setup-step-body muted">Complete Add Vacuum first.</div>`;
      }
      if (importNeeded && !importDone) {
        return `<div class="evcc-setup-step-body muted">Complete map import first.</div>`;
      }
      if (importedMaps.length === 0 && !importNeeded) {
        return `
          <div class="evcc-setup-step-body">
            No rooms discovered yet. Run a clean cycle so the vacuum reports
            its room list, then refresh setup status.
          </div>
        `;
      }

      const driftHtml = renderDriftPanel(drift, vacuumEntry);
      const mapRowsHtml = importedMaps.map((m) =>
        renderMapRow(m, /* showConfigureControls */ true)
      ).join("");

      const intro = step.completed
        ? `<div class="evcc-setup-step-body muted">Rooms configured. Drift detection watches for new or removed rooms below.</div>`
        : `<div class="evcc-setup-step-body">Configure each imported map — exclude ghost rooms and set floor types.</div>`;

      return `
        ${intro}
        ${driftHtml}
        <div class="evcc-setup-mapconfig-list">${mapRowsHtml}</div>
      `;
    };

    const STEP_BODY_RENDERERS = {
      "add_vacuum":         renderAddVacuumBody,
      "import_active_map":  renderImportActiveMapBody,
      "save_rooms":         renderSaveRoomsBody,
    };

    /* -------------------------------------------------------
       Drift panel — shown inside save_rooms when not in_sync
       ------------------------------------------------------- */

    const renderDriftPanel = (drift, vacuumEntry) => {
      if (!drift || drift.in_sync) return "";

      const newRooms       = Array.isArray(drift.new_rooms)       ? drift.new_rooms       : [];
      const removedRooms   = Array.isArray(drift.removed_rooms)   ? drift.removed_rooms   : [];
      const transientRooms = Array.isArray(drift.transiently_missing) ? drift.transiently_missing : [];

      if (newRooms.length === 0 && removedRooms.length === 0 && transientRooms.length === 0) {
        return "";
      }

      const newSection = newRooms.length === 0 ? "" : `
        <div class="evcc-setup-drift-section new">
          <div class="evcc-setup-drift-title">
            New rooms discovered (${newRooms.length})
          </div>
          <div class="evcc-setup-drift-hint">
            The vacuum reports rooms you haven't configured yet. Configure
            the matching map to include them, or reject as phantoms.
          </div>
          <div class="evcc-setup-drift-list">
            ${newRooms.map((r) => `
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(r.name ?? `Room ${r.room_id}`)}</span>
                <span class="evcc-setup-drift-room-map muted">map ${this.escapeHtml(String(r.map_id ?? ""))}</span>
                <button class="evcc-setup-btn secondary small"
                        data-action="setup-reject-room"
                        data-room-id="${r.room_id}"
                        ${loading ? "disabled" : ""}>
                  Reject as phantom
                </button>
              </div>
            `).join("")}
          </div>
        </div>
      `;

      const removedSection = removedRooms.length === 0 ? "" : `
        <div class="evcc-setup-drift-section removed">
          <div class="evcc-setup-drift-title">
            Rooms no longer reported (${removedRooms.length})
          </div>
          <div class="evcc-setup-drift-hint">
            These rooms have been missing from discovery long enough to be
            confirmed removed. Reconfigure the matching map to drop them.
          </div>
          <div class="evcc-setup-drift-list">
            ${removedRooms.map((r) => `
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(r.name ?? `Room ${r.room_id}`)}</span>
                <span class="evcc-setup-drift-room-map muted">map ${this.escapeHtml(String(r.map_id ?? ""))}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;

      const transientSection = transientRooms.length === 0 ? "" : `
        <div class="evcc-setup-drift-section transient">
          <div class="evcc-setup-drift-title">
            Temporarily missing (${transientRooms.length})
          </div>
          <div class="evcc-setup-drift-hint">
            Missing from recent discovery passes but not yet confirmed
            removed — likely a transient API glitch. Use "Force remove"
            only if you know the room is permanently gone.
          </div>
          <div class="evcc-setup-drift-list">
            ${transientRooms.map((r) => `
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(r.name ?? `Room ${r.room_id}`)}</span>
                <span class="evcc-setup-drift-room-map muted">map ${this.escapeHtml(String(r.map_id ?? ""))}</span>
                <button class="evcc-setup-btn destructive-ghost small"
                        data-action="setup-force-remove-room"
                        data-room-id="${r.room_id}"
                        ${loading ? "disabled" : ""}>
                  Force remove now
                </button>
              </div>
            `).join("")}
          </div>
        </div>
      `;

      return `
        <div class="evcc-setup-drift-panel">
          ${newSection}
          ${removedSection}
          ${transientSection}
        </div>
      `;
    };

    /* -------------------------------------------------------
       Per-map row (with inline editor + delete panel)
       Same UI as before; only its placement moved into the
       save_rooms step.
       ------------------------------------------------------- */

    const renderRoomEditor = (mapId) => {
      if (loadingMapId === mapId) {
        return `<div class="evcc-setup-room-editor">
          <div class="evcc-setup-result info">Loading rooms…</div>
        </div>`;
      }
      if (openMapId !== mapId) return "";

      const roomRowsHtml = rooms.length === 0
        ? `<div class="evcc-setup-step-body muted">No rooms found for this map.</div>`
        : rooms.map((room) => {
            const roomId    = String(room.room_id);
            const roomName  = this.escapeHtml(room.name ?? `Room ${roomId}`);
            const enabled   = enabledIdSet.has(roomId);
            const floorType = floorTypesMap[roomId] ?? "hardwood";

            const chipsHtml = FLOOR_TYPE_OPTIONS.map((opt) => `
              <button class="evcc-setup-floor-chip ${floorType === opt.value ? "active" : ""}"
                      data-action="setup-set-floor-type"
                      data-room-id="${roomId}"
                      data-floor-type="${opt.value}"
                      ${saving ? "disabled" : ""}>
                ${opt.label}
              </button>
            `).join("");

            return `
              <div class="evcc-setup-room-row ${enabled ? "" : "excluded"}">
                <div class="evcc-setup-room-row-top">
                  <button class="evcc-setup-room-toggle ${enabled ? "on" : "off"}"
                          data-action="setup-toggle-room"
                          data-room-id="${roomId}"
                          title="${enabled ? "Click to exclude" : "Click to include"}"
                          ${saving ? "disabled" : ""}>
                    ${enabled ? "✓" : "✕"}
                  </button>
                  <span class="evcc-setup-room-name">${roomName}</span>
                </div>
                ${enabled ? `<div class="evcc-setup-floor-chips">${chipsHtml}</div>` : ""}
              </div>
            `;
          }).join("");

      return `
        <div class="evcc-setup-room-editor">
          <div class="evcc-setup-room-editor-hint">
            Deselect rooms you don't want managed (phantom rooms, closets, etc.).
            Set each real room's floor type — it drives the cleaning profile system.
          </div>
          <div class="evcc-setup-room-list">
            ${roomRowsHtml}
          </div>
          <button class="evcc-setup-btn"
                  data-action="setup-save-rooms"
                  data-map-id="${mapId}"
                  ${saving ? "disabled" : ""}>
            ${saving ? "Saving…" : "Save Room Configuration"}
          </button>
        </div>
      `;
    };

    const renderDeletePanel = (mapId, protection) => {
      if (deletePendingMapId !== mapId) return "";
      const targetName      = this.escapeHtml(protection?.typed_confirmation_value ?? `Map ${mapId}`);
      const requiresTyped   = protection?.requires_typed_confirmation ?? false;
      const reasons         = protection?.reasons ?? [];

      const reasonBadgesHtml = reasons.length
        ? `<div class="evcc-setup-delete-badges">
             ${reasons.map((r) => `<span class="evcc-setup-protection-badge">${this.escapeHtml(r.message)}</span>`).join("")}
           </div>`
        : "";

      const typingInputHtml = requiresTyped
        ? `<div class="evcc-setup-delete-typed">
             <div class="evcc-setup-delete-typed-hint">
               Type <strong>${targetName}</strong> to confirm deletion.
             </div>
             <input class="evcc-setup-delete-input"
                    data-action="setup-delete-map-input"
                    type="text"
                    placeholder="${targetName}"
                    value="${this.escapeHtml(deleteTypedToken)}"
                    autocomplete="off"
                    spellcheck="false" />
           </div>`
        : "";

      const tokenMatchesOrNotRequired = requiresTyped
        ? deleteTypedToken.trim() === (protection?.typed_confirmation_value ?? "").trim()
        : true;

      return `
        <div class="evcc-setup-delete-panel">
          ${reasonBadgesHtml}
          <div class="evcc-setup-delete-warning">
            Delete <strong>${targetName}</strong>? This removes all rooms, history,
            and learning data for this map from the integration.
            The upstream cloud map is not affected.
          </div>
          ${typingInputHtml}
          <div class="evcc-setup-delete-actions">
            <button class="evcc-setup-btn destructive small"
                    data-action="setup-delete-map-confirm"
                    data-map-id="${mapId}"
                    ${(!tokenMatchesOrNotRequired || deleteDeleting) ? "disabled" : ""}>
              ${deleteDeleting ? "Deleting…" : "Delete Map"}
            </button>
            <button class="evcc-setup-btn secondary small"
                    data-action="setup-delete-map-cancel"
                    ${deleteDeleting ? "disabled" : ""}>
              Cancel
            </button>
          </div>
        </div>
      `;
    };

    const renderMapRow = (m, showConfigureControls) => {
      const mapId         = String(m.map_id);
      const mapLabel      = this.escapeHtml(m.display_name ?? `Map ${mapId}`);
      const configured    = state.isSetupMapConfigured?.(mapId);
      const isOpen        = openMapId === mapId || loadingMapId === mapId;
      const protection    = m.protection ?? null;
      const requiresTyped = protection?.requires_typed_confirmation ?? false;
      const isDeleteOpen  = deletePendingMapId === mapId;

      const badge = configured && !isOpen
        ? `<span class="evcc-setup-configured-badge">✓ Configured</span>`
        : "";

      const configBtn = showConfigureControls ? `
        <button class="evcc-setup-btn ${configured ? "secondary" : ""} small"
                data-action="setup-configure-map"
                data-map-id="${mapId}"
                ${(loading || saving || deleteDeleting) ? "disabled" : ""}>
          ${isOpen ? "Close" : configured ? "Reconfigure" : "Configure Rooms"}
        </button>
      ` : "";

      const deleteBtn = !isDeleteOpen
        ? `<button class="evcc-setup-btn destructive-ghost small"
                   data-action="setup-delete-map-open"
                   data-map-id="${mapId}"
                   data-requires-typed="${requiresTyped}"
                   ${(loading || saving || deleteDeleting) ? "disabled" : ""}>
             Delete
           </button>`
        : "";

      return `
        <div class="evcc-setup-mapconfig-row">
          <div class="evcc-setup-mapconfig-header">
            <div class="evcc-setup-mapconfig-name">${mapLabel}</div>
            <div class="evcc-setup-mapconfig-actions">
              ${badge}
              ${deleteBtn}
              ${configBtn}
            </div>
          </div>
          ${renderDeletePanel(mapId, protection)}
          ${showConfigureControls ? renderRoomEditor(mapId) : ""}
        </div>
      `;
    };

    /* -------------------------------------------------------
       Build the step list
       ------------------------------------------------------- */

    const renderStep = (step, index) => {
      const bodyRenderer = STEP_BODY_RENDERERS[step.id];
      const body = bodyRenderer
        ? bodyRenderer(step)
        : `<div class="evcc-setup-step-body muted">No handler for step "${this.escapeHtml(step.id)}".</div>`;

      const badgeContents = step.completed ? "✓" : String(index + 1);

      return `
        <div class="evcc-setup-step">
          <div class="evcc-setup-step-header">
            <div class="evcc-setup-step-badge ${step.completed ? "done" : ""}">
              ${badgeContents}
            </div>
            <div class="evcc-setup-step-label">${this.escapeHtml(step.label)}</div>
          </div>
          ${body}
        </div>
      `;
    };

    const stepsHtml = steps.map(renderStep).join("");

    /* -------------------------------------------------------
       Ready banner
       ------------------------------------------------------- */
    const setupComplete   = Boolean(status?.setup_complete);
    const allInSync       = drift ? drift.in_sync !== false : true;
    const readyHtml = setupComplete && allInSync
      ? `<div class="evcc-setup-result success">
           ✓ Setup complete — switch to the Rooms tab to start cleaning.
         </div>`
      : "";

    /* -------------------------------------------------------
       Panel name — rename this vacuum's sidebar entry. Only
       shown for a managed vacuum (the panel must exist). The
       backend re-registers the panel live; the sidebar repaints
       after a page refresh. Empty = revert to the default name.
       ------------------------------------------------------- */
    const panelTitle = vacuumEntry?.panel_title ?? "";
    const renamePanelHtml = vacuumEntry ? `
      <div class="evcc-setup-rename">
        <div class="evcc-setup-rename-title">Panel name</div>
        <div class="evcc-setup-step-body muted">
          Rename this vacuum's entry in the Home Assistant sidebar. After saving,
          refresh the page to see the new name. Leave blank to reset to the default.
        </div>
        <div class="evcc-setup-rename-row">
          <input class="evcc-setup-rename-input"
                 type="text"
                 maxlength="48"
                 data-action="setup-rename-panel-input"
                 value="${this.escapeHtml(panelTitle)}"
                 placeholder="Vacuum Agent"
                 autocomplete="off"
                 spellcheck="false"
                 ${loading ? "disabled" : ""} />
          <button class="evcc-setup-btn small"
                  data-action="setup-rename-panel-save"
                  ${loading ? "disabled" : ""}>
            Rename
          </button>
        </div>
      </div>
    ` : "";

    /* -------------------------------------------------------
       Add another vacuum — any vacuum.* entity not yet managed.
       This panel's setup steps only manage its own vacuum; this
       section is the cross-vacuum affordance to register a NEW
       one. Adding wires its adapter + panel (the backend reloads
       the entry — see setup_add_vacuum).
       ------------------------------------------------------- */
    const managedIds   = new Set(vacuums.map((v) => v.vacuum_entity_id));
    // Always exclude this panel's own vacuum, even before the status loads.
    if (vacuumEntityId) managedIds.add(vacuumEntityId);
    const allVacuumIds = card?._hass?.states
      ? Object.keys(card._hass.states).filter((id) => id.startsWith("vacuum."))
      : [];
    const unmanagedIds = allVacuumIds.filter((id) => !managedIds.has(id)).sort();

    const addOtherRowsHtml = unmanagedIds.map((id) => {
      const friendly = card._hass.states[id]?.attributes?.friendly_name ?? id;
      return `
        <div class="evcc-setup-add-other-row">
          <div class="evcc-setup-add-other-info">
            <span class="evcc-setup-add-other-name">${this.escapeHtml(String(friendly))}</span>
            <span class="evcc-setup-entity-id">${this.escapeHtml(id)}</span>
          </div>
          <button class="evcc-setup-btn small"
                  data-action="setup-add-other-vacuum"
                  data-vacuum-id="${this.escapeHtml(id)}"
                  ${loading ? "disabled" : ""}>
            Add
          </button>
        </div>
      `;
    }).join("");

    const addOtherHtml = `
      <div class="evcc-setup-add-other">
        <div class="evcc-setup-add-other-title">Add another vacuum</div>
        ${unmanagedIds.length === 0
          ? `<div class="evcc-setup-step-body muted">All detected vacuums are already managed.</div>`
          : `<div class="evcc-setup-step-body">These vacuums are available in Home Assistant but not yet managed. Adding one registers its adapter and a sidebar panel (the integration reloads).</div>
             <div class="evcc-setup-add-other-list">${addOtherRowsHtml}</div>`}
      </div>
    `;

    /* -------------------------------------------------------
       Refresh button
       ------------------------------------------------------- */
    const refreshHtml = `
      <div class="evcc-setup-footer">
        <button class="evcc-setup-btn secondary"
                data-action="setup-refresh"
                ${loading ? "disabled" : ""}>
          ${status == null ? "Check Status" : "Refresh"}
        </button>
      </div>
    `;

    return `
      <div class="evcc-setup-view">
        <div class="evcc-setup-header">
          <div class="evcc-setup-title">Vacuum Setup</div>
          <div class="evcc-setup-description">
            Steps below are declared by your vacuum adapter. Each must complete
            in order. New rooms discovered after setup will surface here for
            review before they enter the room library.
          </div>
        </div>

        ${stepsHtml}
        ${readyHtml}
        ${lastResultHtml}
        ${errorHtml}
        ${loadingHtml}
        ${renamePanelHtml}
        ${addOtherHtml}
        ${refreshHtml}
      </div>
    `;
  };

}

/* -----------------------------------------------------------
   Helpers (module-private)
   ----------------------------------------------------------- */

/**
 * Check whether the named step is marked completed in a steps array.
 */
function _isStepCompleted(steps, stepId) {
  if (!Array.isArray(steps)) return false;
  const entry = steps.find((s) => s.id === stepId);
  return Boolean(entry?.completed);
}

/**
 * Build a fallback steps array from legacy status fields when the
 * backend response predates the data-driven contract.
 *
 * Mirrors the old hardcoded two-step wizard: add_vacuum + import+save
 * combined under the legacy "no_map"→"ready" transition. This lets the
 * card render against an older snapshot of state without crashing;
 * once the backend ships, this branch is rarely hit.
 */
function _legacyStepsFallback(vacuumEntry) {
  if (!vacuumEntry) {
    return [
      { id: "add_vacuum",        label: "Add vacuum",       completed: false, service: "" },
      { id: "import_active_map", label: "Import active map", completed: false, service: "" },
      { id: "save_rooms",        label: "Configure rooms",  completed: false, service: "" },
    ];
  }
  const hasImported = Boolean(vacuumEntry.has_imported_map);
  return [
    { id: "add_vacuum",        label: "Add vacuum",        completed: true,        service: "" },
    { id: "import_active_map", label: "Import active map", completed: hasImported, service: "" },
    { id: "save_rooms",        label: "Configure rooms",   completed: hasImported, service: "" },
  ];
}
