/**
 * ============================================================
 * BINDINGS: SAVED ZONES
 * ============================================================
 *
 * Wires the saved-zones side panel: collapse, per-row multi-select, the shared
 * clean-setting selects, "Clean N selected" (plural dispatch) and delete.
 * All handlers are DELEGATED (_onAll) so they survive the panel's re-renders.
 * (Wave 3b — Cut 2.)
 *
 * ============================================================
 */

export function applySavedZonesBindings(proto) {
  proto._bindSavedZones = function () {
    const card = this.card;

    // --- collapse / expand the whole section --------------------------------
    const toggleCollapse = () => {
      card._state.setSavedZonesCollapsed?.(!card._state.savedZonesCollapsed?.());
      card._scheduleRender?.();
    };
    card._onAll("[data-action='toggle-saved-zones-collapse']", "click", () => toggleCollapse());
    card._onAll("[data-action='toggle-saved-zones-collapse']", "keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleCollapse();
      }
    });

    // --- per-row multi-select (native checkbox) -----------------------------
    card._onAll("[data-action='toggle-saved-zone']", "change", (e) => {
      const id = e.target?.dataset?.zoneId;
      if (!id) return;
      card._state.toggleSavedZoneSelection?.(id);
      card._scheduleRender?.();
    });

    card._onAll("[data-action='clear-saved-zone-selection']", "click", () => {
      card._state.clearSavedZoneSelection?.();
      card._scheduleRender?.();
    });

    // --- shared clean-setting selects (device-level) ------------------------
    // Scoped to "sz-setting" so it never double-fires with the map panel's
    // "zone-setting" binding. The HA state push re-renders with the confirmed value.
    card._onAll("[data-action='sz-setting']", "change", (e) => {
      const sel = e.target;
      if (!sel?.dataset?.entityId) return;
      card._actions.setVacuumSetting?.(sel.dataset.entityId, sel.value);
    });

    // --- clean the selected set in one dispatch -----------------------------
    card._onAll("[data-action='clean-selected-saved-zones']", "click", async () => {
      const ids = card._state.selectedSavedZoneIds?.() ?? [];
      if (!ids.length) return;

      let result;
      try {
        result = await card._actions.cleanSavedZones({
          vacuum_entity_id: card._state.vacuumEntityId?.(),
          map_id: card._state.activeMapId?.(),
          zone_ids: ids,
        });
      } catch (err) {
        // dispatch_zone_clean raises on a cap breach (too many / a side out of range);
        // the count cap is already grey-out-guarded, so this is almost always side-length.
        card.showToast(this.t("bind_saved_zones.clean_failed"), { kind: "error" });
        return;
      }

      if (!result || result.cleaned === false) {
        const reason = result?.reason;
        let msg;
        if (reason === "map_not_active") msg = this.t("bind_saved_zones.map_not_active");
        else if (reason === "zone_not_found") msg = this.t("bind_saved_zones.zone_not_found");
        else if (reason === "bad_geometry") msg = this.t("bind_saved_zones.bad_geometry");
        else if (reason === "no_zones") msg = this.t("bind_saved_zones.no_zones");
        else msg = this.t("bind_saved_zones.clean_failed");
        card.showToast(msg, { kind: "error" });
        return;
      }

      card.showToast(
        this.t("bind_saved_zones.cleaning_selected", { count: ids.length }),
        { kind: "success" },
      );
      card._state.clearSavedZoneSelection?.();
      card._scheduleRender?.();
    });

    // --- delete a zone ------------------------------------------------------
    card._onAll("[data-action='delete-saved-zone']", "click", async (e) => {
      const zoneId = e.currentTarget.dataset.zoneId;
      if (!zoneId) return;

      const zone = (card._state.savedZones?.() ?? []).find(
        (z) => String(z.id) === String(zoneId)
      );
      if (!(await card._confirm(
        this.t("bind_saved_zones.confirm_delete", { name: zone?.name ?? "" }),
        { danger: true }
      ))) {
        return;
      }

      const result = await card._actions.deleteSavedZone({
        vacuum_entity_id: card._state.vacuumEntityId?.(),
        map_id: card._state.activeMapId?.(),
        zone_id: zoneId,
      });

      if (result?.saved === false) {
        card.showToast(this.t("bind_saved_zones.unable_delete"), { kind: "error" });
        return;
      }

      await card.refreshSavedZones?.();
      card._scheduleRender();
    });
  };
}
