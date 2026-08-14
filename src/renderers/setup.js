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

import { resolveCodedLabel } from "../state/coded-label.js";

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

    /* Reconciliation review state (CARD-7/RP-019) — see state/setup.js's
       block comment for what's local UI state vs. backend-sourced. */
    const reconciliation       = vacuumEntry?.reconciliation ?? null;
    const reconcileLoading     = state.setupReconcileLoading?.()       ?? false;
    const reconcileResolvedTok = state.setupReconcileResolvedToken?.() ?? null;
    const reconcileResult      = state.setupReconcileResult?.()        ?? null;
    const reconcileStaleNote   = state.setupReconcileStaleNote?.()     ?? false;
    const reconcileRefreshFail = state.setupReconcileRefreshFailed?.() ?? false;

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

      const driftHtml      = renderDriftPanel(drift, vacuumEntry);
      const reconcileHtml  = renderReconciliationPanel(reconciliation);
      const mapRowsHtml = importedMaps.map((m) =>
        renderMapRow(m, /* showConfigureControls */ true)
      ).join("");

      const intro = step.completed
        ? `<div class="evcc-setup-step-body muted">${this.t("setup.rooms_configured_drift")}</div>`
        : `<div class="evcc-setup-step-body">${this.t("setup.configure_each_map")}</div>`;

      return `
        ${intro}
        ${driftHtml}
        ${reconcileHtml}
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
       Reconciliation review panel (CARD-7/RP-019) — shown inside
       save_rooms when a re-segment produced identity-shift reviews
       the user hasn't acted on. Structurally mirrors renderDriftPanel
       just above (same evcc-setup-drift-* naming pattern, adapted to
       evcc-setup-reconcile-*), but with only TWO groups (the design's
       "two review kinds, not four" correction) and ONE whole-map
       decision (Update/Dismiss) instead of per-row buttons — the
       backend (reconcile_room) has no per-room granularity.

       Three kinds fold into two groups:
         - id_changed              -> "Renumbered" (informational)
         - renamed                 -> "Renamed" (the real ambiguity)
         - renamed_and_renumbered  -> ALSO "Renamed" (same core question
           as a pure rename — did the user rename it, or is this a
           different room in disguise — just with an id-bookkeeping
           detail folded into the same row template).
       ------------------------------------------------------- */

    const renderReconcileIdChange = (oldId, newId) => `
      <span class="evcc-setup-reconcile-id-change">
        <span class="evcc-setup-reconcile-id-old">${this.escapeHtml(String(oldId ?? ""))}</span>
        <span class="evcc-setup-reconcile-id-arrow" aria-hidden="true">→</span>
        <span class="evcc-setup-reconcile-id-new">${this.escapeHtml(String(newId ?? ""))}</span>
      </span>
    `;

    const renderReconcileResult = (result) => {
      const count   = Number(result?.migrated_room_count ?? 0);
      const dropped = Array.isArray(result?.dropped) ? result.dropped : [];

      const updatedHtml = `
        <div class="evcc-setup-result success">${this.t("setup.reconcile_updated_count", { count })}</div>
      `;
      const droppedHtml = dropped.length === 0 ? "" : `
        <div class="evcc-setup-result info">
          ${this.tRaw("setup.reconcile_dropped_sentence", {
            count: dropped.length,
            names: dropped.map((slug) => this.escapeHtml(_prettifySlug(slug))).join(", "),
          })}
        </div>
      `;

      return `
        <div class="evcc-setup-reconcile-panel resolved">
          ${updatedHtml}
          ${droppedHtml}
        </div>
      `;
    };

    const renderReconciliationPanel = (reconciliation) => {
      if (!reconciliation) return "";

      // A review this card already resolved (Update or Dismiss) round-trips its
      // exact plan_token here — comparing against the CURRENT token (rather than
      // trusting has_changes, which only refreshes on the NEXT real discover_rooms
      // pass, same "last cached pass" contract room_drift already has) is what
      // stops the group banner from reappearing for a plan already acted on.
      const isResolved = Boolean(
        reconcileResolvedTok
        && reconciliation.plan_token
        && reconciliation.plan_token === reconcileResolvedTok
      );
      if (isResolved) {
        return reconcileResult?.action === "migrate" ? renderReconcileResult(reconcileResult) : "";
      }

      // State A: has_changes:false -> render nothing. No empty state, no badge.
      // Checked BEFORE reconcileRefreshFail: a fresh status poll (e.g. the
      // card's periodic _scheduleSetupStatusRefresh, independent of the
      // stuck recovery attempt) can report has_changes:false after a prior
      // silent-recovery failure left refreshFailed=true. That fresh "no
      // changes" read is authoritative and must win — otherwise the manual
      // re-discover prompt keeps showing a stale ask the backend already
      // resolved, violating State A's "no changes -> render nothing"
      // contract for as long as refreshFailed stays set.
      if (!reconciliation.has_changes) return "";

      // Design's literal fallback: the silent plan_changed recovery itself
      // failed — prompt a manual re-discover rather than render stale/guessed data.
      if (reconcileRefreshFail) {
        return `
          <div class="evcc-setup-reconcile-panel">
            <div class="evcc-setup-reconcile-note">${this.t("setup.reconcile_refresh_failed")}</div>
            <button class="evcc-setup-btn secondary small"
                    data-action="setup-reconcile-rediscover"
                    ${reconcileLoading ? "disabled" : ""}>
              ${this.t("setup.reconcile_rediscover_button")}
            </button>
          </div>
        `;
      }

      const reviews     = Array.isArray(reconciliation.reviews) ? reconciliation.reviews : [];
      const renumbered  = reviews.filter((r) => r.kind === "id_changed");
      const renamed     = reviews.filter((r) => r.kind === "renamed" || r.kind === "renamed_and_renumbered");
      if (renumbered.length === 0 && renamed.length === 0) return "";

      const renumberedSection = renumbered.length === 0 ? "" : `
        <div class="evcc-setup-reconcile-section renumbered">
          <div class="evcc-setup-reconcile-title">
            ${this.t("setup.reconcile_renumbered_title", { count: renumbered.length })}
          </div>
          <div class="evcc-setup-reconcile-hint">
            ${this.t("setup.reconcile_renumbered_hint")}
          </div>
          <div class="evcc-setup-reconcile-list">
            ${renumbered.map((r) => `
              <div class="evcc-setup-reconcile-row">
                <span class="evcc-setup-reconcile-room-name">${this.escapeHtml(r.name || this.t("setup.room_n", { id: r.new_id }))}</span>
                ${renderReconcileIdChange(r.old_id, r.new_id)}
              </div>
            `).join("")}
          </div>
        </div>
      `;

      const renamedSection = renamed.length === 0 ? "" : `
        <div class="evcc-setup-reconcile-section renamed">
          <div class="evcc-setup-reconcile-title">
            ${this.t("setup.reconcile_renamed_title", { count: renamed.length })}
          </div>
          <div class="evcc-setup-reconcile-hint">
            ${this.t("setup.reconcile_renamed_hint")}
          </div>
          <div class="evcc-setup-reconcile-list">
            ${renamed.map((r) => `
              <div class="evcc-setup-reconcile-row ${r.kind === "renamed_and_renumbered" ? "renamed-and-renumbered" : ""}">
                <span class="evcc-setup-reconcile-room-name">${this.escapeHtml(r.new_name || this.t("setup.room_n", { id: r.room_id ?? r.new_id }))}</span>
                <span class="evcc-setup-reconcile-was">${this.t("setup.reconcile_formerly", { name: this.escapeHtml(r.old_name || "") })}</span>
                ${r.kind === "renamed_and_renumbered" ? renderReconcileIdChange(r.old_id, r.new_id) : ""}
              </div>
            `).join("")}
          </div>
        </div>
      `;

      const staleNoteHtml = reconcileStaleNote
        ? `<div class="evcc-setup-reconcile-note">${this.t("setup.reconcile_stale_note")}</div>`
        : "";

      return `
        <div class="evcc-setup-reconcile-panel">
          ${staleNoteHtml}
          ${renumberedSection}
          ${renamedSection}
          <div class="evcc-setup-reconcile-actions">
            <button class="evcc-setup-btn secondary small"
                    data-action="setup-reconcile-dismiss"
                    ${reconcileLoading ? "disabled" : ""}>
              ${reconcileLoading ? this.t("setup.reconcile_dismissing") : this.t("setup.reconcile_dismiss_button")}
            </button>
            <button class="evcc-setup-btn small"
                    data-action="setup-reconcile-update"
                    ${reconcileLoading ? "disabled" : ""}>
              ${reconcileLoading ? this.t("setup.reconcile_updating") : this.t("setup.reconcile_update_button")}
            </button>
          </div>
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

      // RP-005/RF-02 (ROOMS-2, card half): an empty selection is not a savable
      // state — the backend now refuses enabled_room_ids: [] at the schema, so
      // surface the refusal HERE with a translated hint instead of letting the
      // call fail with a raw schema error. "I want no rooms" = Delete Map.
      const noneEnabled = rooms.length > 0
        && rooms.every((room) => !enabledIdSet.has(String(room.room_id)));

      return `
        <div class="evcc-setup-room-editor">
          <div class="evcc-setup-room-editor-hint">
            ${this.t("setup.room_editor_hint")}
          </div>
          <div class="evcc-setup-room-list">
            ${roomRowsHtml}
          </div>
          ${noneEnabled ? `<div class="evcc-setup-result info">${this.t("setup.no_rooms_selected_hint")}</div>` : ""}
          <button class="evcc-setup-btn"
                  data-action="setup-save-rooms"
                  data-map-id="${mapId}"
                  ${saving || noneEnabled ? "disabled" : ""}>
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
             ${reasons.map((r) => `<span class="evcc-setup-protection-badge">${this.escapeHtml(
               // Each reason is a backend {code, message} pair — resolve the
               // CODE through setup.protection_reason.* (the message is the
               // English fallback for codes this card build doesn't know).
               resolveCodedLabel(r, (k, v) => this.tRaw(k, v), {
                 prefixes: ["setup.protection_reason."],
               })
             )}</span>`).join("")}
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


  /* =========================================================
     SUB-TAB STRIP + THE "SYSTEM" BINDING TABLE (live:ENT-11)
     ========================================================= */

  proto._renderSetupSubtabStrip = function (state) {
    const sub = state.setupSubtab?.() ?? "steps";
    return `
      <div class="evcc-setup-subtabs">
        <button class="evcc-setup-subtab ${sub === "steps" ? "is-active" : ""}"
                data-action="set-setup-subtab" data-subtab="steps"
                aria-selected="${sub === "steps" ? "true" : "false"}"
        >${this.t("setup.subtab_steps")}</button>
        <button class="evcc-setup-subtab ${sub === "system" ? "is-active" : ""}"
                data-action="set-setup-subtab" data-subtab="system"
                aria-selected="${sub === "system" ? "true" : "false"}"
        >${this.t("setup.subtab_system")}</button>
      </div>
    `;
  };

  /**
   * WHAT WE ARE READING — every role, not only the broken ones.
   *
   * The default view is deliberately the FULL table. Every other surface shows
   * only roles that FAILED, and a failures-only view is structurally blind to
   * the defect this was built for: a name collision resolves SUCCESSFULLY, to a
   * real enabled entity, and is simply the wrong one — per-run cleaning area
   * reading a lifetime counter, off by ~4000x. That screen looks healthy.
   *
   * The current VALUE is on the row because it is the cheapest sanity check
   * there is and needs no engineering literacy: 0 min beside 166 min settles it
   * instantly. It also separates the two failure modes that look identical from
   * outside — an entity resolving correctly while the consumer is broken (issue
   * #49's battery) versus the resolver having picked the wrong entity.
   */
  proto._renderSystemSubtab = function (ctx) {
    const { state } = ctx;
    const rows = state.entityBindings?.() ?? [];

    if (!rows.length) {
      return `<div class="evcc-setup-empty">${this.t("system.empty")}</div>`;
    }

    const body = rows.map((row) => {
      const entityId = row?.entity_id ?? null;
      const value = entityId ? state.stateOf?.(entityId) : null;
      const shown = (value == null || value === "")
        ? this.t("system.no_value")
        : this.escapeHtml(String(value));

      // `chosen_by` is only set when the role was CONTESTED. Absent means it
      // was never contested — NOT that nothing decided it — so it must not
      // render as though a rung fired.
      const source = row?.chosen_by
        ? this.t(`system.source_${row.chosen_by}`)
        : this.t("system.source_derived");

      const reason = row?.reason && row.reason !== "resolved"
        ? `<span class="evcc-system-flag">${this.t(`system.reason_${row.reason}`)}</span>`
        : "";

      const rejected = Object.entries(row?.rejected ?? {});
      const alternatives = rejected.length
        ? `<div class="evcc-system-rejected">${this.t("system.rejected")}: ` +
          rejected.map(([id, why]) =>
            `<code>${this.escapeHtml(id)}</code> (${this.escapeHtml(String(why))})`
          ).join(", ") + `</div>`
        : "";

      return `
        <tr>
          <td class="evcc-system-role">${this.escapeHtml(String(row?.role ?? ""))}</td>
          <td class="evcc-system-entity">
            ${entityId ? `<code>${this.escapeHtml(entityId)}</code>` : `<em>${this.t("system.unresolved")}</em>`}
            ${alternatives}
          </td>
          <td class="evcc-system-value">${shown}</td>
          <td class="evcc-system-source">${source} ${reason}</td>
        </tr>
      `;
    }).join("");

    return `
      <div class="evcc-system-panel">
        <div class="evcc-system-intro">${this.t("system.subtitle")}</div>
        <div class="evcc-system-scroll">
          <table class="evcc-system-table">
            <thead>
              <tr>
                <th>${this.t("system.col_role")}</th>
                <th>${this.t("system.col_entity")}</th>
                <th>${this.t("system.col_value")}</th>
                <th>${this.t("system.col_source")}</th>
              </tr>
            </thead>
            <tbody>${body}</tbody>
          </table>
        </div>
      </div>
    `;
  };

  /* The steps list is the original renderSetupView; wrap rather than edit it so
     a 700-line renderer stays untouched by the addition of a sibling view. */
  const _renderSetupSteps = proto.renderSetupView;
  proto.renderSetupView = function (ctx) {
    const strip = this._renderSetupSubtabStrip(ctx.state);
    if ((ctx.state.setupSubtab?.() ?? "steps") === "system") {
      return strip + this._renderSystemSubtab(ctx);
    }
    return strip + _renderSetupSteps.call(this, ctx);
  };
}

/* -----------------------------------------------------------
   Helpers (module-private)
   ----------------------------------------------------------- */

/**
 * Reformat a room SLUG (e.g. "guest-bedroom") into a display-friendly label
 * ("Guest Bedroom") for State C's dropped-rooms report. `plan_migration`
 * (rooms/reconciliation.py) reports `dropped` as slugs, not display names —
 * the original room's name is gone along with the rest of its durable data,
 * so the slug is genuinely the best label left. Pure formatting, not i18n:
 * the slug itself is derived from whatever name the user gave the room.
 */
function _prettifySlug(slug) {
  const s = String(slug ?? "").trim();
  if (!s) return s;
  return s
    .split(/[-_]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

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
