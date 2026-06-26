/**
 * ============================================================
 * BINDINGS: ROOM ACCESS MODAL
 * ============================================================
 *
 * PURPOSE
 * -------
 * Wires the dedicated room access modal interactions.
 *
 * ============================================================
 */

/**
 * Mix room access binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyRoomAccessBindings(proto) {
  proto._bindRoomAccess = function () {
    // Access modal lives in the external modal host, so there is
    // nothing to bind on the shadow root for now.
  };

  proto._bindRoomAccessHost = function (host) {
    if (!host) return;

    host.querySelectorAll("[data-action='open-room-access']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();

        const roomId = btn.dataset.roomId;
        const mapId = btn.dataset.mapId;
        if (!roomId || !mapId) return;

        this.card._state.closeRoomEditor?.();
        this.card._state.openRoomAccess?.(roomId, mapId);
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='close-room-access']").forEach((btn) => {
      this.card._on(btn, "click", () => {
        this.card._state.closeRoomAccess?.();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='toggle-is-dock-room']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();
        this.card._state.toggleIsDockRoomField?.();
        this.card._scheduleRender();
      });
    });

    host.querySelectorAll("[data-action='toggle-room-access-target']").forEach((btn) => {
      this.card._on(btn, "click", (e) => {
        e.stopPropagation();

        const roomId = btn.dataset.roomId;
        if (!roomId) return;

        this.card._state.toggleRoomAccessTarget?.(roomId);
        this.card._scheduleRender();
      });
    });

    const saveBtn = host.querySelector("[data-action='save-room-access']");
    this.card._on(saveBtn, "click", async () => {
        const room = this.card._state.activeAccessRoom?.();
        const fields = this.card._state.roomAccessFields?.();
        const validation = this.card._state.roomAccessValidation?.();
        if (!room || !fields || !validation?.valid) return;

        try {
          const result = await this.card._actions.saveRoomAccess?.(
            room.id,
            fields.grants_access_to ?? [],
            fields.is_dock_room ?? false
          );

          if (
            result?.ok === false ||
            result?.updated === false ||
            result?.error === "invalid_access_graph" ||
            result?.reason === "invalid_access_graph"
          ) {
            const message =
              (Array.isArray(result?.issues) && result.issues.length
                ? result.issues.map((issue) => issue?.message ?? String(issue)).join(" ")
                : null) ??
              result?.reason_detail ??
              result?.message ??
              result?.reason ??
              this.t("bind_room_access.backend_rejected_graph");

            this.card._state.setRoomAccessSaveError?.(message);
            this.card._scheduleRender();
            return;
          }

          this.card._state.closeRoomAccess?.();
          await this.card.refreshDashboardSnapshot?.();
          this.card._scheduleRender();
        } catch (err) {
          console.error(
            "[eufy-vacuum-command-center] Failed to save room access:",
            err
          );
          this.card._state.setRoomAccessSaveError?.(
            this.t("bind_room_access.failed_to_save")
          );
          this.card._scheduleRender();
        }
      });
  };
}
