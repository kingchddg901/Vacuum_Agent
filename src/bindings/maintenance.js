/**
 * ============================================================
 * BINDINGS: MAINTENANCE
 * ============================================================
 *
 * Wires DOM interactions in the Maintenance view — inner tab
 * switching, maintenance item modal open/close, and reset flow.
 *
 * ============================================================
 */

/**
 * Mix maintenance binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyMaintenanceBindings(proto) {

  /**
   * Bind the Maintenance view — tab chips and item modal triggers.
   */
  proto._bindMaintenance = function () {
    this.card._onAll("[data-maintenance-tab]", "click", (e) => {
      const tab = e.currentTarget?.dataset?.maintenanceTab;
      if (!tab) return;

      this.card._state.setMaintenanceActiveTab?.(tab);
      this.card._scheduleRender();
    });

    this.card._onAll("[data-action='open-maintenance-modal']", "click", (e) => {
      const target = e.currentTarget;
      const kind = target?.dataset?.itemKind;
      const component = target?.dataset?.itemComponent;
      const entityId = target?.dataset?.itemEntityId;

      if (!kind || !component) return;

      const item = this.card._state.findUpkeepItem?.(kind, component, entityId);
      if (!item) return;

      this.card._state.openMaintenanceModal?.(item);
      this.card._scheduleRender();
    });
  };

  /**
   * Bind the maintenance item modal rendered in the external modal host.
   *
   * @param {Element|null} host - The modal host element, or null.
   */
  proto._bindMaintenanceModalHost = function (host) {
    if (!host) return;

    host.querySelectorAll("[data-action='close-maintenance-modal']").forEach((el) => {
      this.card._on(el, "click", () => {
        this.card._state.closeMaintenanceModal?.();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='begin-maintenance-reset']").forEach((el) => {
      this.card._on(el, "click", () => {
        this.card._state.beginMaintenanceResetConfirmation?.();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='cancel-maintenance-reset']").forEach((el) => {
      this.card._on(el, "click", () => {
        this.card._state.cancelMaintenanceResetConfirmation?.();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='confirm-maintenance-reset']").forEach((el) => {
      this.card._on(el, "click", async () => {
        const item = this.card._state.activeMaintenanceModalItem?.();
        if (!item || !this.card._state.canInvokeMaintenanceReset?.(item)) return;

        this.card._state.setMaintenanceResetPending?.(true);
        this.card._scheduleRender();

        const result = await this.card._actions.callNamedService?.(
          item.reset_service,
          item.reset_service_data
        );

        if (result === null) {
          this.card._state.setMaintenanceResetError?.(`Could not reset ${item.label ?? item.component ?? "item"}`);
          this.card._scheduleRender();
          return;
        }

        await this.card.refreshDashboardSnapshot?.();

        const successMessage = String(item?.reset_kind ?? "").trim().toLowerCase() === "integration"
          ? "Maintenance reset saved"
          : "Replacement reset sent";

        const refreshedItem = this.card._state.findUpkeepItem?.(
          item.kind,
          item.component,
          item.entity_id
        );

        if (refreshedItem) {
          this.card._state.openMaintenanceModal?.(refreshedItem);
        }

        this.card._state.setMaintenanceResetSuccess?.(successMessage);
        this.card._scheduleRender();
      });
    });
  };
}
