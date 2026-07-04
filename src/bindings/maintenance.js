/**
 * ============================================================
 * BINDINGS: MAINTENANCE
 * ============================================================
 *
 * Wires DOM interactions in the Maintenance view — inner tab
 * switching, maintenance item modal open/close, reset flow, and
 * the per-component interval editor (Save / Restore-default).
 *
 * The interval editor writes through eufy_vacuum.set_maintenance_interval,
 * which stores into the same data["maintenance"][vacuum][component]
 * slot as the EufyVacuumMaintenanceIntervalNumber HA entity — so any
 * value the user sets here is immediately reflected on number.*
 * entities and vice-versa.
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

    host.querySelectorAll("[data-action='save-maintenance-interval']").forEach((el) => {
      this.card._on(el, "click", async () => {
        const input = host.querySelector("[data-role='maintenance-interval-input']");
        if (!input) return;

        const raw = String(input.value ?? "").trim();
        const value = Number(raw);
        if (!Number.isFinite(value) || value <= 0) {
          console.warn("[eufy-vacuum-command-center] interval must be > 0", { raw });
          return;
        }

        const maxAttr = input.getAttribute("max");
        const maxVal = Number(maxAttr);
        if (Number.isFinite(maxVal) && maxVal > 0 && value > maxVal) {
          console.warn("[eufy-vacuum-command-center] interval exceeds max", { value, max: maxVal });
          return;
        }

        const vacuumEntityId = input.dataset?.vacuumEntityId;
        const component = input.dataset?.component;
        if (!vacuumEntityId || !component) return;

        const result = await this.card._actions.callNamedService?.(
          "eufy_vacuum.set_maintenance_interval",
          {
            vacuum_entity_id: vacuumEntityId,
            component,
            interval_hours: value,
          },
          true
        );

        if (result === null) {
          console.warn("[eufy-vacuum-command-center] set_maintenance_interval failed");
          this.card.showToast?.(this.t("bind_maintenance.could_not_save_interval"), { kind: "error" });
          return;
        }

        await this.card.refreshDashboardSnapshot?.();
        this.card.showToast?.(this.t("bind_maintenance.interval_saved", { value }), { kind: "success" });

        const active = this.card._state.activeMaintenanceModalItem?.();
        if (active) {
          const refreshed = this.card._state.findUpkeepItem?.(
            active.kind,
            active.component,
            active.entity_id
          );
          if (refreshed) this.card._state.openMaintenanceModal?.(refreshed);
        }
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='reset-maintenance-interval-default']").forEach((el) => {
      this.card._on(el, "click", () => {
        const input = host.querySelector("[data-role='maintenance-interval-input']");
        if (!input) return;
        const def = Number(input.dataset?.default);
        if (Number.isFinite(def) && def > 0) {
          input.value = String(def);
        }
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
          const label = item.label ?? item.component ?? "item";
          // The panel reset-error sink (renderers/maintenance.js) escapeHtml()s the whole message,
          // so it takes the RAW label; the toast sink trusts its message (trust model B), so the
          // backend-free-text label is escaped here before it reaches innerHTML.
          this.card._state.setMaintenanceResetError?.(this.t("bind_maintenance.could_not_reset", { label }));
          this.card.showToast?.(this.t("bind_maintenance.could_not_reset", { label: this.esc(label) }), { kind: "error" });
          this.card._scheduleRender();
          return;
        }

        await this.card.refreshDashboardSnapshot?.();

        const successMessage = String(item?.reset_kind ?? "").trim().toLowerCase() === "integration"
          ? this.t("bind_maintenance.maintenance_reset_saved")
          : this.t("bind_maintenance.replacement_reset_sent");
        this.card.showToast?.(successMessage, { kind: "success" });

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
