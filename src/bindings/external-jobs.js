/**
 * ============================================================
 * BINDINGS: EXTERNAL JOBS
 * ============================================================
 *
 * Wires the External Jobs subtab (shadow root) and the review-wizard modal
 * (body-level modal host). Subtab events go through card._onAll (re-bound each
 * render); modal-host events are attached per-render in bindModalHostEvents via
 * _bindExternalWizardHost(host).
 * ============================================================
 */

export function applyExternalJobsBindings(proto) {

  /* --- subtab (shadow root) ------------------------------------------ */

  proto._bindExternalJobs = function () {
    const card = this.card;

    card._onAll("[data-action='set-review-subtab']", "click", (e) => {
      const sub = e.currentTarget?.dataset?.subtab;
      card._state.setReviewSubtab(sub);
      if (sub === "external") this._refreshExternalPending();
      card._scheduleRender();
    });

    card._onAll("[data-action='open-external-wizard']", "click", (e) => {
      const pid = e.currentTarget?.dataset?.pendingId;
      const run = (card._state.externalPendingRuns() || []).find(
        (r) => String(r.pending_job_id) === String(pid)
      );
      if (run) {
        card._state.openExternalWizard(run);
        card._scheduleRender();
      }
    });

    card._onAll("[data-action='discard-external-run']", "click", async (e) => {
      const pid = e.currentTarget?.dataset?.pendingId;
      if (!pid) return;
      try {
        await card._actions.discardExternalRun?.(pid);
      } catch (err) {
        console.error("[eufy-vacuum-command-center] discard external failed:", err);
      }
      await this._refreshExternalPending();
      card._scheduleRender();
    });

    // Populate the pending list + subtab badge once, proactively.
    if (!this._externalFetchedOnce) {
      this._externalFetchedOnce = true;
      this._refreshExternalPending();
    }
  };

  proto._refreshExternalPending = async function () {
    const card = this.card;
    try {
      const { pending, brand } = await card._actions.fetchExternalPendingRuns();
      card._state.setExternalPendingRuns(pending);
      card._state.setExternalBrand(brand);
      card._scheduleRender();
    } catch (err) {
      console.error("[eufy-vacuum-command-center] fetch external pending failed:", err);
    }
  };

  /* --- wizard modal (modal host) ------------------------------------ */

  proto._bindExternalWizardHost = function (host) {
    if (!host) return;
    const card = this.card;
    const render = () => card._scheduleRender();

    host.querySelectorAll("[data-action='close-external-wizard']").forEach((el) => {
      el.addEventListener("click", () => {
        card._state.closeExternalWizard();
        render();
      });
    });

    // v1 (legacy) merge-only toggle.
    host.querySelectorAll("[data-action='toggle-external-split']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        card._state.toggleExternalSplit(Number(btn.dataset.order));
        render();
      });
    });

    // v2 server-side re-segmentation: room count + per-boundary split/merge.
    host.querySelectorAll("[data-action='ext-count-inc']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const w = card._state.externalWizard();
        this._resegmentExternal({ expectedRooms: (w?.segments?.length || 1) + 1 });
      });
    });
    host.querySelectorAll("[data-action='ext-count-dec']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const w = card._state.externalWizard();
        this._resegmentExternal({ expectedRooms: Math.max(1, (w?.segments?.length || 1) - 1) });
      });
    });
    host.querySelectorAll("[data-action='ext-merge-up']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const w = card._state.externalWizard();
        const bid = Number(btn.dataset.boundaryId);
        const next = (w?.activeBoundaries || []).map(Number).filter((id) => id !== bid);
        this._resegmentExternal({ activeBoundaries: next });
      });
    });
    host.querySelectorAll("[data-action='ext-split-here']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const w = card._state.externalWizard();
        const bid = Number(btn.dataset.boundaryId);
        const next = Array.from(new Set([...(w?.activeBoundaries || []).map(Number), bid]));
        this._resegmentExternal({ activeBoundaries: next });
      });
    });

    host.querySelectorAll("[data-action='ext-pick-room']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        card._state.setExternalAssignment(Number(btn.dataset.order), {
          room_id: Number(btn.dataset.roomId),
        });
        render();
      });
    });

    host.querySelectorAll("[data-action='ext-pick-room-select']").forEach((sel) => {
      sel.addEventListener("change", (e) => {
        const value = e.target?.value;
        if (value) {
          card._state.setExternalAssignment(Number(sel.dataset.order), {
            room_id: Number(value),
          });
          render();
        }
      });
    });

    host.querySelectorAll("[data-action='ext-set-override']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const order = Number(btn.dataset.order);
        const key = btn.dataset.key;
        let value = btn.dataset.value;
        if (key === "clean_passes") value = Number(value);
        card._state.setExternalAssignmentOverride(order, key, value);
        render();
      });
    });

    host.querySelectorAll("[data-action='ext-set-edge']").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        card._state.setExternalAssignment(Number(btn.dataset.order), {
          edge_mopping: btn.dataset.value === "true",
        });
        render();
      });
    });

    host.querySelectorAll("[data-action='ext-wizard-next']").forEach((btn) => {
      btn.addEventListener("click", () => {
        card._state.setExternalWizardStep(2);
        render();
      });
    });

    host.querySelectorAll("[data-action='ext-wizard-back']").forEach((btn) => {
      btn.addEventListener("click", () => {
        card._state.setExternalWizardStep(1);
        render();
      });
    });

    host.querySelectorAll("[data-action='ext-wizard-confirm']").forEach((btn) => {
      btn.addEventListener("click", () => this._submitExternalWizard(false));
    });

    host.querySelectorAll("[data-action='ext-wizard-override']").forEach((btn) => {
      btn.addEventListener("click", () => this._submitExternalWizard(true));
    });
  };

  proto._resegmentExternal = async function (opts) {
    const card = this.card;
    const w = card._state.externalWizard();
    if (!w || !w.resegmentable || w.busy) return;
    card._state.setExternalWizardBusy(true);
    card._state.setExternalWizardError(null);
    card._scheduleRender();
    try {
      const res = await card._actions.resegmentExternalRun(w.pendingJobId, w.mapId, opts);
      if (res && res.ok) {
        card._state.applyResegmentResult(res);
      } else {
        card._state.setExternalWizardError(this.t("bind_external_jobs.resegment_failed_retry"));
      }
    } catch (err) {
      console.error("[eufy-vacuum-command-center] resegment external failed:", err);
      card._state.setExternalWizardError(this.t("bind_external_jobs.resegment_failed_detail", { detail: (err?.message || err) }));
    } finally {
      card._state.setExternalWizardBusy(false);
      card._scheduleRender();
    }
  };

  proto._submitExternalWizard = async function (override) {
    const card = this.card;
    const w = card._state.externalWizard();
    if (!w) return;

    const groups = card._state.externalWizardGroups();
    const assignments = groups.map((g) => {
      const lead = g.lead || {};
      const order = Number(lead.order ?? 0);
      const a = w.assignments[order] || {};
      return {
        segment_orders: g.orders,
        room_id: a.room_id,
        edge_mopping: !!a.edge_mopping,
        override: !!override || !!a.override,
        overrides: a.overrides || {},
      };
    });

    if (assignments.some((a) => !a.room_id)) {
      card._state.setExternalWizardError(this.t("bind_external_jobs.pick_room_every_panel"));
      card._scheduleRender();
      return;
    }

    card._state.setExternalWizardError(null);
    card._state.setExternalWizardBusy(true);
    card._scheduleRender();

    try {
      const res = await card._actions.confirmExternalRun(w.pendingJobId, w.mapId, assignments);
      if (res && res.ok) {
        card._state.closeExternalWizard();
        await this._refreshExternalPending();
        card._scheduleRender();
      } else if (res && Array.isArray(res.blocked) && res.blocked.length) {
        card._state.setExternalWizardBusy(false);
        card._state.setExternalWizardBlocked(res.blocked);
        card._scheduleRender();
      } else {
        card._state.setExternalWizardBusy(false);
        card._state.setExternalWizardError(this.t("bind_external_jobs.confirm_failed_retry"));
        card._scheduleRender();
      }
    } catch (err) {
      console.error("[eufy-vacuum-command-center] confirm external failed:", err);
      card._state.setExternalWizardBusy(false);
      card._state.setExternalWizardError(this.t("bind_external_jobs.confirm_failed_detail", { detail: (err?.message || err) }));
      card._scheduleRender();
    }
  };
}
