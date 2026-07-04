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

import { rectToPolygon } from "../cards/zone-geometry.js";

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
      // Keep the selection so the map keeps drawing the zone(s) WHILE they clean (that's
      // the "where am I cleaning" the overlay is for). The user drops it with "Clear".
      card._scheduleRender?.();
    });

    // --- draw a new zone to save (Cut 3) ------------------------------------
    card._onAll("[data-action='draw-saved-zone']", "click", () => {
      card._state.setZoneDrawMode?.(true, "save");
      card._scheduleRender?.();
    });
    card._onAll("[data-action='cancel-draw-saved-zone']", "click", () => {
      card._state.setZoneDrawMode?.(false);
      card._scheduleRender?.();
    });
    card._onAll("[data-action='save-drawn-zone']", "click", async (e) => {
      // The live backdrop's natural px letterbox-corrects the drawn box into the image's 0-1
      // frame (same _liveMapDims the ad-hoc zone-clean uses — handles <img> AND <canvas>
      // backdrops). We save the FIRST drawn box as one named zone.
      const dims = this._liveMapDims?.(e.currentTarget.getRootNode?.());
      const rects = card._state.zoneDraftsToNormalizedRects?.(dims) ?? [];
      const geometry = rects.length ? rectToPolygon(rects[0]) : null;
      if (!geometry) {
        card.showToast(this.t("bind_saved_zones.nothing_drawn"), { kind: "error" });
        return;
      }
      const name = ((await card._prompt(this.t("bind_saved_zones.name_prompt"))) ?? "").trim();
      if (!name) return;  // cancelled / empty

      const result = await card._actions.createSavedZone({
        vacuum_entity_id: card._state.vacuumEntityId?.(),
        map_id: card._state.activeMapId?.(),
        name,
        geometry,
      });
      if (!result || result.saved === false) {
        card.showToast(this.t("bind_saved_zones.save_failed"), { kind: "error" });
        return;
      }
      card._state.setZoneDrawMode?.(false);          // exit draw + clear drafts
      await card.refreshSavedZones?.();
      card.showToast(this.t("bind_saved_zones.saved", { name: this.esc(name) }), { kind: "success" });
      card._scheduleRender?.();
    });

    // --- re-file a zone's room (Cut 4) --------------------------------------
    card._onAll("[data-action='set-saved-zone-room']", "change", async (e) => {
      const zoneId = e.target?.dataset?.zoneId;
      if (!zoneId) return;
      const val = e.target.value;
      const result = await card._actions.setSavedZoneRoom({
        vacuum_entity_id: card._state.vacuumEntityId?.(),
        map_id: card._state.activeMapId?.(),
        zone_id: zoneId,
        room_number: val === "" ? null : Number(val),
      });
      if (result?.saved === false) {
        card.showToast(this.t("bind_saved_zones.refile_failed"), { kind: "error" });
      }
      await card.refreshSavedZones?.();   // re-group under the new room
      card._scheduleRender?.();
    });

    // --- rename a zone (Cut 4) ----------------------------------------------
    card._onAll("[data-action='rename-saved-zone']", "click", async (e) => {
      const zoneId = e.currentTarget?.dataset?.zoneId;
      if (!zoneId) return;
      const zone = (card._state.savedZones?.() ?? []).find((z) => String(z.id) === String(zoneId));
      const next = ((await card._prompt(
        this.t("bind_saved_zones.rename_prompt"),
        { defaultValue: zone?.name ?? "" },
      )) ?? "").trim();
      if (!next || next === (zone?.name ?? "")) return;   // cancelled / unchanged / empty
      const result = await card._actions.renameSavedZone({
        vacuum_entity_id: card._state.vacuumEntityId?.(),
        map_id: card._state.activeMapId?.(),
        zone_id: zoneId,
        name: next,
      });
      if (!result || result.saved === false) {
        card.showToast(this.t("bind_saved_zones.rename_failed"), { kind: "error" });
        return;
      }
      await card.refreshSavedZones?.();
      card.showToast(this.t("bind_saved_zones.renamed", { name: this.esc(next) }), { kind: "success" });
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
        this.t("bind_saved_zones.confirm_delete", { name: this.esc(zone?.name ?? "") }),
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
