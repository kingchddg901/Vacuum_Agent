/**
 * ============================================================
 * BINDINGS: LEARNING REVIEW
 * ============================================================
 *
 * Wires DOM interactions in the Learning Review view — filter
 * chips, sort chips, profile matcher fields, and job exclusion
 * toggles.
 *
 * ============================================================
 */

/**
 * Mix learning review binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyReviewBindings(proto) {

  /**
   * Attach all Learning Review view event handlers — filter chips, profile matcher fields,
   * matcher profile selection, sort chips, reason chips, and job exclude/restore actions.
   */
  proto._bindReview = function () {
    this.card._onAll("[data-review-filter-chip]", "click", async (e) => {
      const key = e.currentTarget?.dataset?.reviewFilterChip;
      const value = e.currentTarget?.dataset?.value;
      if (!key) return;

      if (key === "sort") {
        this.card._state.setLearningHistorySort?.(value);
        this.card._scheduleRender();
        return;
      }

      this.card._state.setLearningHistoryFilter?.(key, value);
      await this.card.refreshLearningHistorySnapshot?.();
      this.card._scheduleRender();
    });

    this.card._onAll("[data-review-matcher-field]", "click", (e) => {
      const key = e.currentTarget?.dataset?.reviewMatcherField;
      const value = e.currentTarget?.dataset?.value;
      if (!key) return;

      this.card._state.setReviewProfileMatcherField?.(key, value);
      this.card._scheduleRender();
    });

    this.card._onAll("[data-review-matcher-action]", "click", (e) => {
      const action = e.currentTarget?.dataset?.reviewMatcherAction;
      if (action !== "reset") return;

      this.card._state.resetReviewProfileMatcher?.();
      this.card._scheduleRender();
    });

    this.card._onAll("[data-review-matcher-profile]", "click", async (e) => {
      const profileKey = e.currentTarget?.dataset?.reviewMatcherProfile;
      if (!profileKey) return;

      this.card._state.setLearningHistoryFilter?.("profile_key", profileKey);
      await this.card.refreshLearningHistorySnapshot?.();
      this.card._scheduleRender();
    });

    this.card._onAll("[data-review-filter]", "change", async (e) => {
      const key = e.currentTarget?.dataset?.reviewFilter;
      const value = e.currentTarget?.value;
      if (!key) return;

      if (key === "sort") {
        this.card._state.setLearningHistorySort?.(value);
        this.card._scheduleRender();
        return;
      }

      this.card._state.setLearningHistoryFilter?.(key, value);
      await this.card.refreshLearningHistorySnapshot?.();
      this.card._scheduleRender();
    });

    this.card._onAll("[data-review-reason-chip]", "click", (e) => {
      const jobId = e.currentTarget?.dataset?.reviewReasonChip;
      const value = e.currentTarget?.dataset?.value;
      if (!jobId) return;

      this.card._state.setLearningHistoryExcludeReason?.(jobId, value);
      this.card._scheduleRender();
    });

    this.card._onAll("[data-review-action]", "click", async (e) => {
      const action = e.currentTarget?.dataset?.reviewAction;
      const jobId = e.currentTarget?.dataset?.jobId;
      if (!action || !jobId) return;

      this.card._state.beginLearningHistoryJobAction?.(jobId);
      this.card._scheduleRender();

      try {
        if (action === "exclude") {
          await this.card._actions.excludeLearningJob?.({
            job_id: jobId,
            reason: this.card._state.learningHistoryExcludeReason?.(jobId),
          });
        }

        if (action === "restore") {
          await this.card._actions.restoreLearningJob?.({
            job_id: jobId,
          });
        }

        await this.card.refreshLearningHistorySnapshot?.();
      } finally {
        this.card._state.endLearningHistoryJobAction?.();
        this.card._scheduleRender();
      }
    });
  };
}
