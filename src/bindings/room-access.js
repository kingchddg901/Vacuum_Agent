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
import { accessIssueLabel } from "../state/access-issue-label.js";

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
      this.card._on(btn, "click", async (e) => {
        e.stopPropagation();

        // The button is disabled when another room holds the dock, but a
        // disabled button is a rendering fact and this handler is reachable
        // from a synthetic event — refuse here too rather than trusting it.
        if (this.card._state.accessDockHeldByOther?.()) return;

        const releasing = this.card._state.roomAccessFields?.().is_dock_room ?? false;
        const linked = this.card._state.accessGraphLinkedRoomCount?.() ?? 0;

        // RELEASING THE DOCK CLEARS THE GRAPH (Chris, 2026-08-04). The tree is
        // rooted at the dock, so a rootless tree is not worth keeping — and a
        // bare unset would leave grants with no root, which is `partial` and
        // refuses every run. Clearing lands on `blank`, where basic runs work.
        // Warn only when there is something to lose.
        if (releasing && linked > 0) {
          const proceed = await this.card._confirm(
            this.t("bind_room_access.release_dock_clears_graph", { count: linked }),
            { danger: true }
          );
          if (!proceed) return;
        }

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

        // Releasing the dock is not a per-room edit — it clears the map's graph,
        // so it goes through the replace-all service. Detected by comparing the
        // draft against STORED state: this room holds the dock on disk and the
        // draft has let it go.
        const releasingDock =
          Boolean(room.isDockRoom) && !(fields.is_dock_room ?? false);

        try {
          const result = releasingDock
            ? await this.card._actions.clearRoomAccessGraph?.()
            : await this.card._actions.saveRoomAccess?.(
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
                ? result.issues.map((issue) => accessIssueLabel(issue, (k, v) => this.t(k, v))).join(" ")
                : null) ??
              result?.reason_detail ??
              result?.message ??
              result?.reason ??
              this.tRaw("bind_room_access.backend_rejected_graph");

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
            this.tRaw("bind_room_access.failed_to_save")
          );
          this.card._scheduleRender();
        }
      });
  };
}
