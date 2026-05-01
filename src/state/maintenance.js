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
