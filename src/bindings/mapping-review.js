/**
 * ============================================================
 * BINDINGS: MAPPING REVIEW
 * ============================================================
 *
 * Wires DOM interactions in the Mapping Bounds Review view —
 * filter chips, per-room bounds clear, and bounds rebuild actions.
 *
 * ============================================================
 */

/**
 * Mix mapping bounds review binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyMappingReviewBindings(proto) {

  /**
   * Attach all Mapping Bounds Review view event handlers — filter chips, per-room bounds
   * clear, bounds rebuild, and job-level exclude/restore actions.
   */
  proto._bindMappingReview = function () {
    this.card._onAll("[data-mrev-filter]", "click", (e) => {
      const filter = e.currentTarget?.dataset?.mrevFilter;
      if (!filter) return;
      this.card._state.setMappingBoundsFilter?.(filter);
      this.card._scheduleRender();
    });

    this.card._onAll("[data-mrev-clear]", "click", async (e) => {
      const roomId = e.currentTarget?.dataset?.mrevClear;
      if (!roomId) return;

      this.card._state.beginMappingBoundsClear?.(roomId);
      this.card._scheduleRender();

      try {
        await this.card._actions.clearRoomBounds?.({ room_id: roomId });
        await this.card.refreshMappingBoundsSnapshot?.();
      } finally {
        this.card._state.endMappingBoundsClear?.();
        this.card._scheduleRender();
      }
    });

    this.card._onAll("[data-mrev-rebuild]", "click", async (e) => {
      const roomId = e.currentTarget?.dataset?.mrevRebuild;
      if (!roomId) return;

      this.card._state.beginMappingRebuild?.(roomId);
      this.card._scheduleRender();

      try {
        await this.card._actions.rebuildRoomBoundsFromArchive?.({ room_id: roomId });
        await this.card.refreshMappingBoundsSnapshot?.();
      } finally {
        this.card._state.endMappingRebuild?.();
        this.card._scheduleRender();
      }
    });

    this.card._onAll("[data-mrev-job-action]", "click", async (e) => {
      const btn      = e.currentTarget;
      const action   = btn?.dataset?.mrevJobAction;   // "exclude" or "restore"
      const roomId   = btn?.dataset?.mrevRoomId;
      const jobIndex = btn?.dataset?.mrevJobIndex;
      if (!action || !roomId || jobIndex == null) return;

      this.card._state.beginMappingJobAction?.(roomId, Number(jobIndex), action);
      this.card._scheduleRender();

      try {
        if (action === "exclude") {
          await this.card._actions.excludeRoomJobBounds?.({ room_id: roomId, job_index: Number(jobIndex) });
        } else {
          await this.card._actions.restoreRoomJobBounds?.({ room_id: roomId, job_index: Number(jobIndex) });
        }
        await this.card.refreshMappingBoundsSnapshot?.();
      } finally {
        this.card._state.endMappingJobAction?.();
        this.card._scheduleRender();
      }
    });
  };
}
