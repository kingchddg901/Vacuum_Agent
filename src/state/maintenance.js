/**
 * ============================================================
 * STATE: MAINTENANCE
 * ============================================================
 *
 * PURPOSE
 * -------
 * Card-local UI state for the Maintenance tab.
 *
 * This file owns:
 * - maintenance subtab selection
 * - the maintenance-item modal
 * - the maintenance-COUNTER picker modal (which entity backs the components the
 *   device does not count itself)
 *
 * ============================================================
 */

const MAINTENANCE_TABS = {
  MAINTENANCE: "maintenance_items",
  REPLACEMENTS: "replacements",
};

export function applyMaintenanceState(proto) {

  proto._ensureMaintenanceState = function () {
    if (!this._maintenanceState) {
      this._maintenanceState = {
        activeTab: MAINTENANCE_TABS.MAINTENANCE,
        modalItem: null,
        resetUi: {
          confirming: false,
          pending: false,
          success: "",
          error: "",
        },
        /* The counter picker. `candidates` is null until the open-time fetch lands, which is
           what the renderer distinguishes from an empty LIST — "still asking" and "nothing to
           offer" are different screens, and collapsing them shows an empty-state to someone
           whose data is still in flight. */
        clockPicker: {
          open: false,
          loading: false,
          candidates: null,
          error: "",
          pending: "",
        },
      };
    }

    return this._maintenanceState;
  };

  proto.maintenanceActiveTab = function () {
    return this._ensureMaintenanceState().activeTab;
  };

  proto.setMaintenanceActiveTab = function (tab) {
    const state = this._ensureMaintenanceState();
    const normalized = String(tab ?? "").trim().toLowerCase();

    if (
      normalized !== MAINTENANCE_TABS.MAINTENANCE &&
      normalized !== MAINTENANCE_TABS.REPLACEMENTS
    ) {
      return;
    }

    state.activeTab = normalized;
  };

  proto.isMaintenanceTabActive = function (tab) {
    return this.maintenanceActiveTab() === String(tab ?? "").trim().toLowerCase();
  };

  proto.openMaintenanceModal = function (item) {
    if (!item || typeof item !== "object") return;
    const state = this._ensureMaintenanceState();
    state.modalItem = { ...item };
    state.resetUi = {
      confirming: false,
      pending: false,
      success: "",
      error: "",
    };
  };

  proto.closeMaintenanceModal = function () {
    const state = this._ensureMaintenanceState();
    state.modalItem = null;
    state.resetUi = {
      confirming: false,
      pending: false,
      success: "",
      error: "",
    };
  };

  proto.activeMaintenanceModalItem = function () {
    return this._ensureMaintenanceState().modalItem ?? null;
  };

  proto.isMaintenanceModalOpen = function () {
    return Boolean(this.activeMaintenanceModalItem());
  };

  /* ---- the maintenance-counter picker -------------------------------------------------
     WHY A MODAL AND NOT A SETUP SCREEN (Chris, 2026-09-14): the fix belongs where the problem
     is noticed. The trigger sits in the Maintenance Items header, warning-coloured when nothing
     is picked and faded when something is.

     WHY THE LIST IS FETCHED, NOT RENDERED FROM THE SNAPSHOT: the backend sweep walks the entity
     registry and reads a state per sibling -- 300 entities on one live machine -- for a list
     wanted twice in a vacuum's life. It is a service call on OPEN, and again on save/close so
     the trigger's own state re-reads from fresh data rather than waiting for the next snapshot.
  */

  proto.openMaintenanceClockPicker = function () {
    const picker = this._ensureMaintenanceState().clockPicker;
    picker.open = true;
    picker.loading = true;
    picker.error = "";
    picker.pending = "";
    // candidates deliberately NOT cleared: on a re-open the previous list is a better first
    // paint than an empty one, and the fetch replaces it a moment later.
  };

  proto.closeMaintenanceClockPicker = function () {
    const picker = this._ensureMaintenanceState().clockPicker;
    picker.open = false;
    picker.loading = false;
    picker.error = "";
    picker.pending = "";
  };

  proto.isMaintenanceClockPickerOpen = function () {
    return Boolean(this._ensureMaintenanceState().clockPicker.open);
  };

  proto.maintenanceClockPicker = function () {
    return this._ensureMaintenanceState().clockPicker;
  };

  proto.setMaintenanceClockCandidates = function (list) {
    const picker = this.maintenanceClockPicker();
    picker.candidates = Array.isArray(list) ? list : [];
    picker.loading = false;
    picker.error = "";
  };

  proto.setMaintenanceClockPickerError = function (message) {
    const picker = this.maintenanceClockPicker();
    picker.error = String(message ?? "");
    picker.loading = false;
    picker.pending = "";
  };

  proto.setMaintenanceClockPending = function (entityId) {
    this.maintenanceClockPicker().pending = String(entityId ?? "");
  };

  proto.maintenanceResetUi = function () {
    return this._ensureMaintenanceState().resetUi;
  };

  proto.beginMaintenanceResetConfirmation = function () {
    const resetUi = this.maintenanceResetUi();
    resetUi.confirming = true;
    resetUi.error = "";
    resetUi.success = "";
  };

  proto.cancelMaintenanceResetConfirmation = function () {
    const resetUi = this.maintenanceResetUi();
    resetUi.confirming = false;
    resetUi.pending = false;
    resetUi.error = "";
  };

  proto.setMaintenanceResetPending = function (pending) {
    this.maintenanceResetUi().pending = Boolean(pending);
  };

  proto.setMaintenanceResetSuccess = function (message) {
    const resetUi = this.maintenanceResetUi();
    resetUi.success = String(message ?? "");
    resetUi.error = "";
    resetUi.pending = false;
    resetUi.confirming = false;
  };

  proto.setMaintenanceResetError = function (message) {
    const resetUi = this.maintenanceResetUi();
    resetUi.error = String(message ?? "");
    resetUi.success = "";
    resetUi.pending = false;
  };

  proto.canInvokeMaintenanceReset = function (item) {
    return Boolean(
      item?.can_reset === true &&
      typeof item?.reset_service === "string" &&
      item.reset_service.length > 0 &&
      item?.reset_service_data != null
    );
  };

  proto.findUpkeepItem = function (kind, component, entityId = null) {
    const upkeep = this.dashboardUpkeep?.() ?? {};
    const normalizedKind = String(kind ?? "").trim().toLowerCase();
    const normalizedComponent = String(component ?? "").trim().toLowerCase();
    const normalizedEntityId = entityId == null ? null : String(entityId).trim().toLowerCase();

    const groups = [
      ...(Array.isArray(upkeep.maintenance_items) ? upkeep.maintenance_items : []),
      ...(Array.isArray(upkeep.replacement_items) ? upkeep.replacement_items : []),
    ];

    return groups.find((item) => {
      const itemKind = String(item?.kind ?? "").trim().toLowerCase();
      const itemComponent = String(item?.component ?? "").trim().toLowerCase();
      const itemEntityId = item?.entity_id == null ? null : String(item.entity_id).trim().toLowerCase();

      if (itemKind !== normalizedKind) return false;
      if (itemComponent !== normalizedComponent) return false;
      if (normalizedEntityId && itemEntityId && itemEntityId !== normalizedEntityId) return false;
      return true;
    }) ?? null;
  };
}
