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
          this.tRaw("bind_setup.failed_add_vacuum", { error: err?.message ?? String(err) })
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       ADD ANOTHER VACUUM — register a different, unmanaged vacuum
       (data-vacuum-id from the row, not this panel's own vacuum).
       The backend reloads the entry to wire the new vacuum + its
       sidebar panel.
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-add-other-vacuum']", "click", async (e) => {
      const vacuumEntityId = e.currentTarget?.dataset?.vacuumId;
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
          this.tRaw("bind_setup.failed_add_vacuum", { error: err?.message ?? String(err) })
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       RENAME PANEL — set this vacuum's sidebar title. Reads the
       sibling input on click (uncontrolled, no per-keystroke
       state). Empty value reverts to the default name. The
       backend re-registers the panel; the sidebar repaints on
       a page refresh.
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-rename-panel-save']", "click", async (e) => {
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!vacuumEntityId) return;
      const input = e.currentTarget
        ?.closest(".evcc-setup-rename")
        ?.querySelector(".evcc-setup-rename-input");
      const title = input ? input.value : "";

      card._state.setSetupLoading?.(true);
      card._state.setSetupError?.(null);
      card._state.setSetupLastResult?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.renamePanel?.(vacuumEntityId, title);
        card._state.setSetupLastResult?.(result);
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);
        card.showToast?.(this.t("bind_setup.panel_renamed"), { kind: "success" });
      } catch (err) {
        card._state.setSetupError?.(
          this.tRaw("bind_setup.failed_rename_panel", { error: err?.message ?? String(err) })
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       LIVE MAP CAMERA — pick the camera/image entity used as
       this vacuum's map backdrop. Saves on change; blank clears
       the override (falls back to the adapter pattern). The next
       dashboard snapshot picks it up — no reload.
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-map-camera-select']", "change", async (e) => {
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!vacuumEntityId) return;
      const entityId = e.currentTarget?.value ?? "";

      card._state.setSetupLoading?.(true);
      card._state.setSetupError?.(null);
      card._state.setSetupLastResult?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.setMapCamera?.(vacuumEntityId, entityId);
        card._state.setSetupLastResult?.(result);
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);
        card.showToast?.(
          entityId
            ? this.t("bind_setup.map_camera_set")
            : this.t("bind_setup.map_camera_cleared"),
          { kind: "success" },
        );
      } catch (err) {
        card._state.setSetupError?.(
          this.tRaw("bind_setup.failed_set_map_camera", { error: err?.message ?? String(err) })
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
              this.tRaw("bind_setup.failed_load_rooms", { error: roomErr?.message ?? String(roomErr) }),
            );
            card._state.setSetupRoomEditorLoadingMapId?.(null);
          }
        }
      } catch (err) {
        card._state.setSetupError?.(
          this.tRaw("bind_setup.failed_import_map", { error: err?.message ?? String(err) })
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
          this.tRaw("bind_setup.failed_load_rooms", { error: err?.message ?? String(err) })
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
          this.tRaw("bind_setup.failed_save_rooms", { error: err?.message ?? String(err) })
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

          // Clear cached map segments / image variants. The deleted map's
          // image_variants would otherwise keep rendering in the Map
          // Configuration view's IMAGE VARIANTS section (Dark/Light/Default
          // sizes) until the next get_map_segments fetch. The setter
          // handles null by resetting overlays and zoom transform; the
          // next map-config nav will re-fetch fresh data.
          card._state.setMapSegmentsData?.(null);

          const statusResult = await card._actions.getSetupStatus?.();
          card._state.setSetupStatus?.(statusResult);
          card.showToast?.(this.t("bind_setup.map_deleted"), { kind: "success" });
        } else {
          card._state.setSetupError?.(
            result?.message ?? this.tRaw("bind_setup.failed_delete_map_plain")
          );
          card._state.setSetupDeleteDeleting?.(false);
        }
      } catch (err) {
        card._state.setSetupError?.(
          this.tRaw("bind_setup.failed_delete_map", { error: err?.message ?? String(err) })
        );
        card._state.setSetupDeleteDeleting?.(false);
        card.showToast?.(this.t("bind_setup.map_delete_failed"), { kind: "error" });
      } finally {
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       REJECT ROOM — mark a discovered room as a phantom
       Used on the room_drift.new_rooms entries to permanently
       suppress a room the user identifies as bogus.
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-reject-room']", "click", async (e) => {
      const roomId         = Number(e.currentTarget.dataset.roomId);
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!Number.isFinite(roomId) || !vacuumEntityId) return;

      card._state.setSetupLoading?.(true);
      card._state.setSetupError?.(null);
      card._state.setSetupLastResult?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.rejectSetupRooms?.(
          vacuumEntityId,
          [roomId],
        );
        card._state.setSetupLastResult?.(result);
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);
      } catch (err) {
        card._state.setSetupError?.(
          this.tRaw("bind_setup.failed_reject_room", { error: err?.message ?? String(err) }),
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });

    /* -------------------------------------------------------
       FORCE-REMOVE ROOM — bypass the missing-pass counter on
       a transiently_missing room when the user knows it's
       permanently gone.
       ------------------------------------------------------- */
    card._onAll("[data-action='setup-force-remove-room']", "click", async (e) => {
      const roomId         = Number(e.currentTarget.dataset.roomId);
      const vacuumEntityId = card._config?.vacuum_entity_id;
      if (!Number.isFinite(roomId) || !vacuumEntityId) return;

      card._state.setSetupLoading?.(true);
      card._state.setSetupError?.(null);
      card._state.setSetupLastResult?.(null);
      card._scheduleRender();

      try {
        const result = await card._actions.forceRemoveSetupRoom?.(
          vacuumEntityId,
          roomId,
        );
        card._state.setSetupLastResult?.(result);
        const statusResult = await card._actions.getSetupStatus?.();
        card._state.setSetupStatus?.(statusResult);
      } catch (err) {
        card._state.setSetupError?.(
          this.tRaw("bind_setup.failed_force_remove_room", { error: err?.message ?? String(err) }),
        );
      } finally {
        card._state.setSetupLoading?.(false);
        card._scheduleRender();
      }
    });
  };
}
