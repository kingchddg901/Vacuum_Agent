/**
 * ============================================================
 * RENDERERS: SETUP
 * ============================================================
 *
 * PURPOSE
 * -------
 * Renders the Setup tab — a two-step wizard:
 *   1. Add the card's vacuum to the integration
 *   2. Import maps + immediately configure each map's rooms
 *      (exclude ghost rooms, set floor type per room)
 *
 * Room config is part of step 2 so ghost rooms are never
 * persisted — setup_save_rooms is what actually writes them.
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

/**
 * Mix setup renderer methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardRenderers prototype to extend.
 */
export function applySetupRenderers(proto) {

  /**
   * Render the two-step setup wizard (add vacuum, import maps + configure rooms).
   *
   * @param {{ state: object, card: object }} ctx - Render context.
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
       Derive per-vacuum state
       ------------------------------------------------------- */
    const vacuums      = Array.isArray(status?.vacuums) ? status.vacuums : [];
    const vacuumEntry  = vacuums.find((v) => v.vacuum_entity_id === vacuumEntityId) ?? null;
    const step1Done    = vacuumEntry != null;
    const importedMaps = (vacuumEntry?.maps ?? []).filter((m) => m.imported);
    const hasAnyMap    = importedMaps.length > 0;

    const allMapsConfigured =
      hasAnyMap && importedMaps.every((m) => state.isSetupMapConfigured?.(String(m.map_id)));

    /* Room editor state */
    const openMapId    = state.setupRoomEditorOpenMapId?.()    ?? null;
    const loadingMapId = state.setupRoomEditorLoadingMapId?.() ?? null;
    const rooms        = state.setupRoomEditorRooms?.()        ?? [];
    const saving       = state.setupRoomEditorSaving?.()       ?? false;

    /* Delete state */
    const deletePendingMapId = state.setupDeletePendingMapId?.() ?? null;
    const deleteStage        = state.setupDeleteStage?.()        ?? null;
    const deleteTypedToken   = state.setupDeleteTypedToken?.()   ?? "";
    const deleteDeleting     = state.setupDeleteDeleting?.()     ?? false;

    const enabledIdSet  = new Set(
      (state.setupRoomEditorEnabledIds?.() ?? []).map(String),
    );
    const floorTypesMap = state.setupRoomEditorFloorTypesMap?.() ?? {};

    /* -------------------------------------------------------
       Transient feedback
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
      return `<div class="evcc-setup-result success">${this.escapeHtml(msg)}</div>`;
    })();

    /* -------------------------------------------------------
       Step 1 — Add Vacuum
       ------------------------------------------------------- */
    const step1Html = `
      <div class="evcc-setup-step">
        <div class="evcc-setup-step-header">
          <div class="evcc-setup-step-badge ${step1Done ? "done" : ""}">
            ${step1Done ? "✓" : "1"}
          </div>
          <div class="evcc-setup-step-label">Add Vacuum</div>
        </div>

        <div class="evcc-setup-step-body">
          Register this vacuum with the integration so it can be managed.
          <div class="evcc-setup-entity-id">${this.escapeHtml(vacuumEntityId)}</div>
        </div>

        ${step1Done
          ? `<div class="evcc-setup-result success">Vacuum registered.</div>`
          : `<button class="evcc-setup-btn"
                     data-action="setup-add-vacuum"
                     ${loading ? "disabled" : ""}>
               Add Vacuum
             </button>`
        }
      </div>
    `;

    /* -------------------------------------------------------
       Step 2 — Import Maps + Configure Rooms

       Import and room config are one step so the user configures
       each map (excludes ghost rooms, sets floor types) before
       the rooms are ever saved to the integration.

       Flow:
         1. Click "Import Active Map" → map discovered
         2. Room editor auto-opens for the new map
         3. Toggle off ghost rooms, pick floor types, Save
         4. Repeat for additional maps
       ------------------------------------------------------- */

    /* Inline room editor for a specific map */
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
            Deselect ghost rooms (Eufy sometimes reports phantom rooms).
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

    /* Render delete confirmation panel for a map */
    const renderDeletePanel = (mapId, protection) => {
      if (deletePendingMapId !== mapId) return "";
      const targetName     = this.escapeHtml(protection?.typed_confirmation_value ?? `Map ${mapId}`);
      const requiresTyped  = protection?.requires_typed_confirmation ?? false;
      const protectionLevel = protection?.protection_level ?? "normal";
      const reasons        = protection?.reasons ?? [];

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
            Eufy's upstream map is not affected.
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

    /* Configured / unconfigured map rows */
    const mapRowsHtml = importedMaps.map((m) => {
      const mapId      = String(m.map_id);
      const mapLabel   = this.escapeHtml(m.display_name ?? `Map ${mapId}`);
      const configured = state.isSetupMapConfigured?.(mapId);
      const isOpen     = openMapId === mapId || loadingMapId === mapId;
      const protection = m.protection ?? null;
      const requiresTyped = protection?.requires_typed_confirmation ?? false;
      const isDeleteOpen = deletePendingMapId === mapId;

      const badge = configured && !isOpen
        ? `<span class="evcc-setup-configured-badge">✓ Configured</span>`
        : "";

      const configBtn = `
        <button class="evcc-setup-btn ${configured ? "secondary" : ""} small"
                data-action="setup-configure-map"
                data-map-id="${mapId}"
                ${(loading || saving || deleteDeleting) ? "disabled" : ""}>
          ${isOpen ? "Close" : configured ? "Reconfigure" : "Configure Rooms"}
        </button>
      `;

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
          ${renderRoomEditor(mapId)}
        </div>
      `;
    }).join("");

    const step2Done = allMapsConfigured;

    const step2Html = `
      <div class="evcc-setup-step">
        <div class="evcc-setup-step-header">
          <div class="evcc-setup-step-badge ${step2Done ? "done" : ""}">
            ${step2Done ? "✓" : "2"}
          </div>
          <div class="evcc-setup-step-label">Import Maps &amp; Configure Rooms</div>
        </div>

        <div class="evcc-setup-step-body">
          ${hasAnyMap
            ? "Configure each imported map — exclude ghost rooms and set floor types. Then import additional maps as needed."
            : "Import the vacuum's currently active map. Make sure it has completed a mapping run first."
          }
        </div>

        ${hasAnyMap ? `<div class="evcc-setup-mapconfig-list">${mapRowsHtml}</div>` : ""}

        ${step1Done
          ? `<button class="evcc-setup-btn ${hasAnyMap ? "secondary" : ""}"
                     data-action="setup-import-map"
                     ${loading ? "disabled" : ""}>
               ${hasAnyMap ? "Import Another Map" : "Import Active Map"}
             </button>`
          : `<div class="evcc-setup-step-body muted">Complete step 1 first.</div>`
        }
      </div>
    `;

    /* -------------------------------------------------------
       Ready banner
       ------------------------------------------------------- */
    const readyHtml = allMapsConfigured
      ? `<div class="evcc-setup-result success">
           ✓ Setup complete — switch to the Rooms tab to start cleaning.
         </div>`
      : hasAnyMap
      ? `<div class="evcc-setup-result info">
           Configure rooms for each imported map to complete setup.
         </div>`
      : "";

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
            Add your vacuum, import each of its maps, then configure rooms
            per map — this is where you exclude ghost rooms and set floor types.
          </div>
        </div>

        ${step1Html}
        ${step2Html}
        ${readyHtml}
        ${lastResultHtml}
        ${errorHtml}
        ${loadingHtml}
        ${refreshHtml}


      </div>
    `;
  };
}
