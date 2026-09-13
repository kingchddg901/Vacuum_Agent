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

    // THE TRIGGER IS IN THE SHADOW ROOT (Maintenance Items header), so `_onAll` is right for it
    // — unlike the modal's own controls below, which live in the body portal where `_onAll` can
    // never match. Same feature, two binding paths, for that one reason.
    this.card._onAll("[data-action='open-clock-picker']", "click", async () => {
      this.card._state.openMaintenanceClockPicker?.();
      this.card._scheduleRender();
      await this._fetchMaintenanceClockCandidates();
    });
  };

  /**
   * Fetch the counter candidates. A SERVICE CALL, not a snapshot field: the backend sweep walks
   * the entity registry and reads a state per sibling (300 entities on one live machine) for a
   * list wanted twice in a vacuum's life — and computing it now means the user sees what is true
   * NOW, since candidates come and go as integrations reload.
   */
  proto._fetchMaintenanceClockCandidates = async function () {
    const vacuumEntityId = this.card._state.vacuumEntityId?.();
    if (!vacuumEntityId) return;
    const result = await this.card._actions.callNamedService?.(
      "eufy_vacuum.get_maintenance_source_candidates",
      { vacuum_entity_id: vacuumEntityId },
      true
    );
    if (result === null || result === undefined) {
      this.card._state.setMaintenanceClockPickerError?.(
        this.t("common.service_failed", { service: "get_maintenance_source_candidates" })
      );
    } else {
      this.card._state.setMaintenanceClockCandidates?.(result?.candidates ?? []);
    }
    this.card._scheduleRender();
  };

  /**
   * Bind the maintenance item modal rendered in the external modal host.
   *
   * @param {Element|null} host - The modal host element, or null.
   */
  proto._bindMaintenanceModalHost = function (host) {
    if (!host) return;

    host.querySelectorAll("[data-action='close-maintenance-clock-picker']").forEach((el) => {
      this.card._on(el, "click", async () => {
        this.card._state.closeMaintenanceClockPicker?.();
        this.card._scheduleRender();
        // Re-read on close so the trigger's own state (warning vs faded, and the name it shows)
        // comes from fresh data rather than waiting for the next snapshot. Chris: "call on open,
        // call on save or close, then it reads the new set version and can drive the dimming."
        await this.card.refreshDashboardSnapshot?.();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='select-maintenance-clock']").forEach((el) => {
      this.card._on(el, "click", async () => {
        const entityId = el?.dataset?.entityId;
        const vacuumEntityId = this.card._state.vacuumEntityId?.();
        if (!entityId || !vacuumEntityId) return;

        this.card._state.setMaintenanceClockPending?.(entityId);
        this.card._scheduleRender();

        const result = await this.card._actions.callNamedService?.(
          "eufy_vacuum.set_entity_override",
          { vacuum_entity_id: vacuumEntityId, role: "maintenance_clock", entity_id: entityId },
          true
        );
        this.card._state.setMaintenanceClockPending?.("");

        if (result === null) {
          this.card._state.setMaintenanceClockPickerError?.(
            this.t("common.service_failed", { service: "set_entity_override" })
          );
          this.card._scheduleRender();
          return;
        }

        // Refresh BOTH: the candidate list so the current-selection marker moves, and the
        // dashboard so every maintenance row picks up its new source. The modal stays open —
        // seeing the marker move is the confirmation that the pick took.
        await this.card.refreshDashboardSnapshot?.();
        await this._fetchMaintenanceClockCandidates();
      });
    });

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
          // Both sinks now TRUST this message (trust model B): the panel (renderers/maintenance.js)
          // and the toast interpolate it raw, so the backend-free-text label is escaped here once.
          const resetErrorMsg = this.t("bind_maintenance.could_not_reset", { label: this.esc(label) });
          this.card._state.setMaintenanceResetError?.(resetErrorMsg);
          this.card.showToast?.(resetErrorMsg, { kind: "error" });
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
