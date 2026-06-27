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
  // Setup step heading, localized by step.id (setup.step_<id>). The backend
  // (setup/drift.py) and the legacy fallback both ship ENGLISH step.label, so
  // translate by the stable id and fall back to step.label for any unknown id.
  proto._setupStepLabel = function (step) {
    // Inline the template in the t() call so the check:i18n reachability scan
    // matches setup.step_* (a t(variable) form is invisible to it).
    const t = this.t(`setup.step_${step.id}`);
    return t === `setup.step_${step.id}` ? this.escapeHtml(String(step.label || step.id)) : t;
  };

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
      ? `<div class="evcc-setup-result info">${this.t("setup.working")}</div>`
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
            ${this.t("setup.vacuum_registered")}
            <div class="evcc-setup-entity-id">${this.escapeHtml(vacuumEntityId)}</div>
          </div>
        `;
      }
      return `
        <div class="evcc-setup-step-body">
          ${this.t("setup.register_vacuum_prompt")}
          <div class="evcc-setup-entity-id">${this.escapeHtml(vacuumEntityId)}</div>
        </div>
        <button class="evcc-setup-btn"
                data-action="setup-add-vacuum"
                ${loading ? "disabled" : ""}>
          ${this.t("setup.add_vacuum")}
        </button>
      `;
    };

    const renderImportActiveMapBody = (step) => {
      const addVacuumDone = _isStepCompleted(steps, "add_vacuum");
      const mapCount      = importedMaps.length;

      if (!addVacuumDone) {
        return `<div class="evcc-setup-step-body muted">${this.t("setup.complete_add_vacuum_first")}</div>`;
      }

      const summaryHtml = mapCount > 0
        ? `<div class="evcc-setup-step-body muted">${this.t("setup.maps_imported", { count: mapCount })}</div>`
        : `<div class="evcc-setup-step-body">${this.t("setup.import_active_map_prompt")}</div>`;

      const buttonLabel = mapCount > 0 ? this.t("setup.import_another_map") : this.t("setup.import_active_map");
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
        return `<div class="evcc-setup-step-body muted">${this.t("setup.complete_add_vacuum_first")}</div>`;
      }
      if (importNeeded && !importDone) {
        return `<div class="evcc-setup-step-body muted">${this.t("setup.complete_map_import_first")}</div>`;
      }
      if (importedMaps.length === 0 && !importNeeded) {
        return `
          <div class="evcc-setup-step-body">
            ${this.t("setup.no_rooms_discovered")}
          </div>
        `;
      }

      const driftHtml = renderDriftPanel(drift, vacuumEntry);
      const mapRowsHtml = importedMaps.map((m) =>
        renderMapRow(m, /* showConfigureControls */ true)
      ).join("");

      const intro = step.completed
        ? `<div class="evcc-setup-step-body muted">${this.t("setup.rooms_configured_drift")}</div>`
        : `<div class="evcc-setup-step-body">${this.t("setup.configure_each_map")}</div>`;

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
            ${this.t("setup.drift_new_title", { count: newRooms.length })}
          </div>
          <div class="evcc-setup-drift-hint">
            ${this.t("setup.drift_new_hint")}
          </div>
          <div class="evcc-setup-drift-list">
            ${newRooms.map((r) => `
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(r.name ?? this.t("setup.room_n", { id: r.room_id }))}</span>
                <span class="evcc-setup-drift-room-map muted">${this.t("setup.map_label", { id: this.escapeHtml(String(r.map_id ?? "")) })}</span>
                <button class="evcc-setup-btn secondary small"
                        data-action="setup-reject-room"
                        data-room-id="${r.room_id}"
                        ${loading ? "disabled" : ""}>
                  ${this.t("setup.reject_as_phantom")}
                </button>
              </div>
            `).join("")}
          </div>
        </div>
      `;

      const removedSection = removedRooms.length === 0 ? "" : `
        <div class="evcc-setup-drift-section removed">
          <div class="evcc-setup-drift-title">
            ${this.t("setup.drift_removed_title", { count: removedRooms.length })}
          </div>
          <div class="evcc-setup-drift-hint">
            ${this.t("setup.drift_removed_hint")}
          </div>
          <div class="evcc-setup-drift-list">
            ${removedRooms.map((r) => `
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(r.name ?? this.t("setup.room_n", { id: r.room_id }))}</span>
                <span class="evcc-setup-drift-room-map muted">${this.t("setup.map_label", { id: this.escapeHtml(String(r.map_id ?? "")) })}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;

      const transientSection = transientRooms.length === 0 ? "" : `
        <div class="evcc-setup-drift-section transient">
          <div class="evcc-setup-drift-title">
            ${this.t("setup.drift_transient_title", { count: transientRooms.length })}
          </div>
          <div class="evcc-setup-drift-hint">
            ${this.t("setup.drift_transient_hint")}
          </div>
          <div class="evcc-setup-drift-list">
            ${transientRooms.map((r) => `
              <div class="evcc-setup-drift-row">
                <span class="evcc-setup-drift-room-name">${this.escapeHtml(r.name ?? this.t("setup.room_n", { id: r.room_id }))}</span>
                <span class="evcc-setup-drift-room-map muted">${this.t("setup.map_label", { id: this.escapeHtml(String(r.map_id ?? "")) })}</span>
                <button class="evcc-setup-btn destructive-ghost small"
                        data-action="setup-force-remove-room"
                        data-room-id="${r.room_id}"
                        ${loading ? "disabled" : ""}>
                  ${this.t("setup.force_remove_now")}
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
          <div class="evcc-setup-result info">${this.t("setup.loading_rooms")}</div>
        </div>`;
      }
      if (openMapId !== mapId) return "";

      const roomRowsHtml = rooms.length === 0
        ? `<div class="evcc-setup-step-body muted">${this.t("setup.no_rooms_for_map")}</div>`
        : rooms.map((room) => {
            const roomId    = String(room.room_id);
            const roomName  = this.escapeHtml(room.name ?? this.t("setup.room_n", { id: roomId }));
            const enabled   = enabledIdSet.has(roomId);
            const floorType = floorTypesMap[roomId] ?? "hardwood";

            const chipsHtml = FLOOR_TYPE_OPTIONS.map((opt) => `
              <button class="evcc-setup-floor-chip ${floorType === opt.value ? "active" : ""}"
                      data-action="setup-set-floor-type"
                      data-room-id="${roomId}"
                      data-floor-type="${opt.value}"
                      ${saving ? "disabled" : ""}>
                ${this.t(`setup.floor_${opt.value}`)}
              </button>
            `).join("");

            return `
              <div class="evcc-setup-room-row ${enabled ? "" : "excluded"}">
                <div class="evcc-setup-room-row-top">
                  <button class="evcc-setup-room-toggle ${enabled ? "on" : "off"}"
                          data-action="setup-toggle-room"
                          data-room-id="${roomId}"
                          title="${enabled ? this.t("setup.click_to_exclude") : this.t("setup.click_to_include")}"
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
            ${this.t("setup.room_editor_hint")}
          </div>
          <div class="evcc-setup-room-list">
            ${roomRowsHtml}
          </div>
          <button class="evcc-setup-btn"
                  data-action="setup-save-rooms"
                  data-map-id="${mapId}"
                  ${saving ? "disabled" : ""}>
            ${saving ? this.t("common.saving") : this.t("setup.save_room_config")}
          </button>
        </div>
      `;
    };

    const renderDeletePanel = (mapId, protection) => {
      if (deletePendingMapId !== mapId) return "";
      const targetName      = this.escapeHtml(protection?.typed_confirmation_value ?? this.t("setup.map_n", { id: mapId }));
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
               ${this.tRaw("setup.delete_type_confirm", { name: targetName })}
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
            ${this.tRaw("setup.delete_warning", { name: targetName })}
          </div>
          ${typingInputHtml}
          <div class="evcc-setup-delete-actions">
            <button class="evcc-setup-btn destructive small"
                    data-action="setup-delete-map-confirm"
                    data-map-id="${mapId}"
                    ${(!tokenMatchesOrNotRequired || deleteDeleting) ? "disabled" : ""}>
              ${deleteDeleting ? this.t("setup.deleting") : this.t("setup.delete_map")}
            </button>
            <button class="evcc-setup-btn secondary small"
                    data-action="setup-delete-map-cancel"
                    ${deleteDeleting ? "disabled" : ""}>
              ${this.t("common.cancel")}
            </button>
          </div>
        </div>
      `;
    };

    const renderMapRow = (m, showConfigureControls) => {
      const mapId         = String(m.map_id);
      const mapLabel      = this.escapeHtml(m.display_name ?? this.t("setup.map_n", { id: mapId }));
      const configured    = state.isSetupMapConfigured?.(mapId);
      const isOpen        = openMapId === mapId || loadingMapId === mapId;
      const protection    = m.protection ?? null;
      const requiresTyped = protection?.requires_typed_confirmation ?? false;
      const isDeleteOpen  = deletePendingMapId === mapId;

      const badge = configured && !isOpen
        ? `<span class="evcc-setup-configured-badge">${this.t("setup.configured_badge")}</span>`
        : "";

      const configBtn = showConfigureControls ? `
        <button class="evcc-setup-btn ${configured ? "secondary" : ""} small"
                data-action="setup-configure-map"
                data-map-id="${mapId}"
                ${(loading || saving || deleteDeleting) ? "disabled" : ""}>
          ${isOpen ? this.t("common.close") : configured ? this.t("setup.reconfigure") : this.t("setup.configure_rooms")}
        </button>
      ` : "";

      const deleteBtn = !isDeleteOpen
        ? `<button class="evcc-setup-btn destructive-ghost small"
                   data-action="setup-delete-map-open"
                   data-map-id="${mapId}"
                   data-requires-typed="${requiresTyped}"
                   ${(loading || saving || deleteDeleting) ? "disabled" : ""}>
             ${this.t("common.delete")}
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
        : `<div class="evcc-setup-step-body muted">${this.t("setup.no_step_handler", { id: this.escapeHtml(step.id) })}</div>`;

      const badgeContents = step.completed ? "✓" : String(index + 1);

      return `
        <div class="evcc-setup-step">
          <div class="evcc-setup-step-header">
            <div class="evcc-setup-step-badge ${step.completed ? "done" : ""}">
              ${badgeContents}
            </div>
            <div class="evcc-setup-step-label">${this._setupStepLabel(step)}</div>
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
           ${this.t("setup.ready_banner")}
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
        <div class="evcc-setup-rename-title">${this.t("setup.panel_name_title")}</div>
        <div class="evcc-setup-step-body muted">
          ${this.t("setup.panel_name_hint")}
        </div>
        <div class="evcc-setup-rename-row">
          <input class="evcc-setup-rename-input"
                 type="text"
                 maxlength="48"
                 data-action="setup-rename-panel-input"
                 value="${this.escapeHtml(panelTitle)}"
                 placeholder="${this.t("setup.panel_name_placeholder")}"
                 autocomplete="off"
                 spellcheck="false"
                 ${loading ? "disabled" : ""} />
          <button class="evcc-setup-btn small"
                  data-action="setup-rename-panel-save"
                  ${loading ? "disabled" : ""}>
            ${this.t("common.rename")}
          </button>
        </div>
      </div>
    ` : "";

    /* -------------------------------------------------------
       Live map camera — pick a camera/image entity to use as
       this vacuum's live map backdrop (e.g. the eufy-clean
       fork's camera.<device>_map). Only shown when at least one
       camera/image entity exists (so non-fork installs see no
       clutter). Blank = adapter default. Saves on change.
       ------------------------------------------------------- */
    const liveMapCurrent = vacuumEntry?.live_map_image_entity ?? "";
    const mapCandidateIds = card?._hass?.states
      ? Object.keys(card._hass.states)
          .filter((id) => id.startsWith("camera.") || id.startsWith("image."))
          .sort()
      : [];
    // Keep a stored override selectable even if its entity isn't currently present.
    if (liveMapCurrent && !mapCandidateIds.includes(liveMapCurrent)) {
      mapCandidateIds.unshift(liveMapCurrent);
    }
    const mapCameraHtml = (vacuumEntry && mapCandidateIds.length) ? `
      <div class="evcc-setup-rename">
        <div class="evcc-setup-rename-title">${this.t("setup.live_map_camera_title")}</div>
        <div class="evcc-setup-step-body muted">
          ${this.tRaw("setup.live_map_camera_hint")}
        </div>
        <div class="evcc-setup-rename-row">
          <select class="evcc-setup-rename-input evcc-setup-map-camera-select"
                  data-action="setup-map-camera-select"
                  ${loading ? "disabled" : ""}>
            <option value=""${liveMapCurrent ? "" : " selected"}>${this.t("setup.auto_adapter_default")}</option>
            ${mapCandidateIds.map((id) => {
              const friendly = card._hass.states[id]?.attributes?.friendly_name ?? id;
              const sel = id === liveMapCurrent ? " selected" : "";
              return `<option value="${this.escapeHtml(id)}"${sel}>${this.escapeHtml(String(friendly))} (${this.escapeHtml(id)})</option>`;
            }).join("")}
          </select>
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
            ${this.t("setup.add")}
          </button>
        </div>
      `;
    }).join("");

    const addOtherHtml = `
      <div class="evcc-setup-add-other">
        <div class="evcc-setup-add-other-title">${this.t("setup.add_another_vacuum")}</div>
        ${unmanagedIds.length === 0
          ? `<div class="evcc-setup-step-body muted">${this.t("setup.all_vacuums_managed")}</div>`
          : `<div class="evcc-setup-step-body">${this.t("setup.unmanaged_vacuums_hint")}</div>
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
          ${status == null ? this.t("setup.check_status") : this.t("setup.refresh")}
        </button>
      </div>
    `;

    return `
      <div class="evcc-setup-view">
        <div class="evcc-setup-header">
          <div class="evcc-setup-title">${this.t("setup.title")}</div>
          <div class="evcc-setup-description">
            ${this.t("setup.description")}
          </div>
        </div>

        ${stepsHtml}
        ${readyHtml}
        ${lastResultHtml}
        ${errorHtml}
        ${loadingHtml}
        ${renamePanelHtml}
        ${mapCameraHtml}
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
