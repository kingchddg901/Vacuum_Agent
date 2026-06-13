/**
 * ============================================================
 * BINDINGS: METRICS
 * ============================================================
 *
 * Wires DOM interactions in the Metrics view — filter chip
 * selection, tab switching, and profile save buttons.
 *
 * ============================================================
 */

/**
 * Mix metrics binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyMetricsBindings(proto) {

  /**
   * Attach all Metrics view event handlers — filter chips, select filters, tab switcher,
   * and profile save buttons.
   */
  proto._bindMetrics = function () {
    this.card._onAll("[data-metrics-save-profile]", "click", async (e) => {
      const sourceType = e.currentTarget?.dataset?.metricsSaveProfile;
      const profileKey = e.currentTarget?.dataset?.profileKey;
      const roomSlug = e.currentTarget?.dataset?.roomSlug;
      if (!sourceType || !profileKey) return;

      const candidate = this.card._state.findMetricsSaveCandidate?.(sourceType, profileKey, roomSlug);
      const saveService = String(candidate?.save_service ?? "").trim();
      const saveData = candidate?.save_service_data;
      if (!candidate || candidate?.save_supported === false || !saveService || !saveData) return;

      const pendingKey = this.card._state.metricsProfileSaveKey?.(sourceType, candidate);
      this.card._state.beginMetricsProfileSave?.(pendingKey);
      this.card._scheduleRender();

      try {
        await this.card._actions.callNamedService?.(saveService, saveData, true);
        await this.card.refreshMetricsSnapshot?.();
        await this.card.refreshLearningHistorySnapshot?.();
      } finally {
        this.card._state.endMetricsProfileSave?.();
        this.card._scheduleRender();
      }
    });

    this.card._onAll("[data-metrics-filter-chip]", "click", async (e) => {
      const key = e.currentTarget?.dataset?.metricsFilterChip;
      const value = e.currentTarget?.dataset?.value;
      if (!key) return;

      this.card._state.setMetricsFilter?.(key, value);
      await this.card.refreshMetricsSnapshot?.();
      this.card._scheduleRender();
    });

    // Live chip search — filter the chips in a searchable group by text without a
    // re-render (keeps focus in the input). The "All" chip always stays visible.
    this.card._onAll("[data-chip-search]", "input", (e) => {
      const input = e.currentTarget;
      const q = String(input?.value ?? "").toLowerCase().trim();
      const group = input?.closest?.("[data-chip-filter-group]");
      if (!group) return;
      group.querySelectorAll(".evcc-chip").forEach((chip) => {
        if (chip.dataset.allChip === "true") { chip.style.display = ""; return; }
        chip.style.display = chip.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    });

    this.card._onAll("[data-metrics-filter]", "change", async (e) => {
      const key = e.currentTarget?.dataset?.metricsFilter;
      const value = e.currentTarget?.value;
      if (!key) return;

      this.card._state.setMetricsFilter?.(key, value);
      await this.card.refreshMetricsSnapshot?.();
      this.card._scheduleRender();
    });

    this.card._onAll("[data-metrics-tab]", "click", (e) => {
      const tab = e.currentTarget?.dataset?.metricsTab;
      if (!tab) return;

      this.card._state.setMetricsActiveTab?.(tab);
      this.card._scheduleRender();
    });
  };
}
