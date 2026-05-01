/**
 * ============================================================
 * BINDINGS: SETUP
 * ============================================================
 *
 * PURPOSE
 * -------
 * Wire click handlers for all Setup tab interactive elements.
 *
 * Step 1/2 actions:
 *   [data-action="setup-add-vacuum"]
 *   [data-action="setup-import-map"]
 *   [data-action="setup-refresh"]
 *
 * Step 3 room config actions:
 *   [data-action="setup-configure-map"]   data-map-id
 *   [data-action="setup-toggle-room"]     data-room-id
 *   [data-action="setup-set-floor-type"]  data-room-id  data-floor-type
 *   [data-action="setup-save-rooms"]      data-map-id
 *
 * ============================================================
 */

/**
 * Mix setup binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applySetupBindings(proto) {

  proto._bindSetup = function () {
    const card = this.card;

    /* -------------------------------------------------------
       ADD VACUUM
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-add-vacuum']", "click", async () => {
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!vacuumEntityId) return;

      card._state.setSetupLoading?.(true);
      card._state.setSetupError?.(null);
      card._state.setSetupLastResult?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.addVacuum?.(vacuumEntityId);
        card._state.setSetupLastResult?.(result);
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);
      } catch (err) {
        card._state.setSetupError?.(
          `Failed to add vacuum: ${err?.message ?? String(err)}`
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       IMPORT MAP
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-import-map']", "click", async () => {
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!vacuumEntityId) return;

      card._state.setSetupLoading?.(true);
      card._state.setSetupError?.(null);
      card._state.setSetupLastResult?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.importActiveMap?.(vacuumEntityId);
        card._state.setSetupLastResult?.(result);
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);

        // Auto-open room editor for the first unconfigured map so the user
        // configures rooms immediately — ghost rooms are never saved otherwise.
        const maps = statusResult?.vacuums
          ?.find((v) => v.vacuum_entity_id === vacuumEntityId)?.maps ?? [];
        const unconfigured = maps.find(
          (m) => m.imported && !card._state.isSetupMapConfigured?.(String(m.map_id)),
        );
        if (unconfigured) {
          const mapId = String(unconfigured.map_id);
          card._state.setSetupRoomEditorLoadingMapId?.(mapId);
          card._state.setSetupError?.(null);
          card._scheduleRender();
          try {
            const roomsResult = await card._actions.getSetupMapRooms?.(vacuumEntityId, mapId);
            card._state.openSetupRoomEditor?.(mapId, roomsResult?.rooms ?? []);
          } catch (roomErr) {
            card._state.setSetupError?.(
              `Failed to load rooms: ${roomErr?.message ?? String(roomErr)}`,
            );
            card._state.setSetupRoomEditorLoadingMapId?.(null);
          }
        }
      } catch (err) {
        card._state.setSetupError?.(
          `Failed to import map: ${err?.message ?? String(err)}`
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       REFRESH STATUS
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-refresh']", "click", async () => {
      await card.refreshSetupStatus?.();
    });

    /* -------------------------------------------------------
       CONFIGURE MAP — open/close room editor for a map
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-configure-map']", "click", async (e) => {
      const mapId          = e.currentTarget.dataset.mapId;
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!mapId || !vacuumEntityId) return;

      // Toggle: clicking again closes the editor.
      if (card._state.setupRoomEditorOpenMapId?.() === mapId) {
        card._state.closeSetupRoomEditor?.();
        card._scheduleRender();
        return;
      }

      card._state.setSetupRoomEditorLoadingMapId?.(mapId);
      card._state.setSetupError?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.getSetupMapRooms?.(vacuumEntityId, mapId);
        const rooms  = result?.rooms ?? [];
        card._state.openSetupRoomEditor?.(mapId, rooms);
      } catch (err) {
        card._state.setSetupError?.(
          `Failed to load rooms: ${err?.message ?? String(err)}`
        );
        card._state.setSetupRoomEditorLoadingMapId?.(null);
      }

      card._scheduleRender();
    });

    /* -------------------------------------------------------
       TOGGLE ROOM — include / exclude a room
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-toggle-room']", "click", (e) => {
      const roomId = e.currentTarget.dataset.roomId;
      if (!roomId) return;
      card._state.toggleSetupRoom?.(roomId);
      card._scheduleRender();
    });

    /* -------------------------------------------------------
       SET FLOOR TYPE — chip click per room
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-set-floor-type']", "click", (e) => {
      const roomId    = e.currentTarget.dataset.roomId;
      const floorType = e.currentTarget.dataset.floorType;
      if (!roomId || !floorType) return;
      card._state.setSetupRoomFloorType?.(roomId, floorType);
      card._scheduleRender();
    });

    /* -------------------------------------------------------
       SAVE ROOMS — persist enabled list + floor types
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-save-rooms']", "click", async (e) => {
      const mapId          = e.currentTarget.dataset.mapId;
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!mapId || !vacuumEntityId) return;

      card._state.setSetupRoomEditorSaving?.(true);
      card._state.setSetupError?.(null);
      card._scheduleRender();

      try {
        const enabledRoomIds = card._state.setupRoomEditorEnabledIds?.() ?? [];
        const floorTypes     = card._state.setupRoomEditorFloorTypesMap?.() ?? {};

        await card._actions.saveSetupRooms?.(
          vacuumEntityId,
          mapId,
          enabledRoomIds,
          floorTypes,
        );

        card._state.markSetupMapConfigured?.(mapId);
        card._state.closeSetupRoomEditor?.();

        // Refresh global status so map row updates.
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);
      } catch (err) {
        card._state.setSetupError?.(
          `Failed to save rooms: ${err?.message ?? String(err)}`
        );
      } finally {
        card._state.setSetupRoomEditorSaving?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       DELETE MAP — open confirmation panel for a map
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-delete-map-open']", "click", (e) => {
      const mapId      = e.currentTarget.dataset.mapId;
      const requiresTyped = e.currentTarget.dataset.requiresTyped === "true";
      if (!mapId) return;
      card._state.openSetupDeleteConfirm?.(mapId, requiresTyped);
      card._scheduleRender();
    });

    /* -------------------------------------------------------
       DELETE MAP — cancel confirmation
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-delete-map-cancel']", "click", () => {
      card._state.closeSetupDeleteConfirm?.();
      card._scheduleRender();
    });

    /* -------------------------------------------------------
       DELETE MAP — typed token input
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-delete-map-input']", "input", (e) => {
      card._state.setSetupDeleteTypedToken?.(e.currentTarget.value);
      card._scheduleRender();
    });

    /* -------------------------------------------------------
       DELETE MAP — confirm and execute
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-delete-map-confirm']", "click", async (e) => {
      const mapId          = e.currentTarget.dataset.mapId;
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!mapId || !vacuumEntityId) return;

      const stage = card._state.setupDeleteStage?.();
      const token = stage === "typing"
        ? card._state.setupDeleteTypedToken?.()
        : "confirmed";   // any truthy value for elevated (non-typed) confirmation

      card._state.setSetupDeleteDeleting?.(true);
      card._state.setSetupError?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.deleteSetupMap?.(vacuumEntityId, mapId, token);

        if (result?.status === "success") {
          card._state.closeSetupDeleteConfirm?.();
          const statusResult = await card._actions.getSetupStatus?.();
          card._state.setSetupStatus?.(statusResult);
        } else {
          card._state.setSetupError?.(
            result?.message ?? "Failed to delete map."
          );
          card._state.setSetupDeleteDeleting?.(false);
        }
      } catch (err) {
        card._state.setSetupError?.(
          `Failed to delete map: ${err?.message ?? String(err)}`
        );
        card._state.setSetupDeleteDeleting?.(false);
      } finally {
        card._scheduleRender();
      }
    });
  };
}
