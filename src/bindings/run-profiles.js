/**
 * ============================================================
 * BINDINGS: RUN PROFILES
 * ============================================================
 *
 * Wires the saved run profile side panel — create, apply, edit,
 * and delete profile actions.
 *
 * ============================================================
 */

import { sanitizeStepsForSave, stepsHaveRoomGroup } from "../state/steps-order.js";

/**
 * Mix run profiles binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyRunProfilesBindings(proto) {
  /**
   * Bind all run profile panel interactions.
   */
  proto._bindRunProfiles = function () {
    this.card._on(
      this.card.$("[data-action='open-new-run-profile']"),
      "click",
      () => {
        this.card._state.openNewRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );

    this.card._on(
      this.card.$("[data-action='cancel-run-profile-editor']"),
      "click",
      () => {
        this.card._state.closeRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );

    this.card._onAll("[data-run-profile-field='name']", "input", (e) => {
      this.card._state.updateRunProfileDraft?.("name", e.currentTarget.value);
    });

    this.card._onAll("[data-run-profile-field='expose_as_button']", "change", (e) => {
      this.card._state.updateRunProfileDraft?.("expose_as_button", e.currentTarget.checked);
      this.card._scheduleRender();
    });

    this.card._onAll("[data-action='apply-run-profile']", "click", async (e) => {
      const profileId = e.currentTarget.dataset.profileId;
      if (!profileId) return;

      this.card._state.selectRunProfile?.(profileId);

      const result = await this.card._actions.applyRunProfile({
        vacuum_entity_id: this.card._state.vacuumEntityId?.(),
        map_id: this.card._state.activeMapId?.(),
        profile_id: profileId,
      });

      if (result?.ok === false) {
        this.card.showToast((result.reason ? this.esc(result.reason) : this.t("bind_run_profiles.unable_apply")), { kind: "error" });
        return;
      }

      // Remember the applied profile so a plain Start dispatches its steps (A).
      this.card._state.setAppliedRunProfile?.(profileId);
      this.card._state.clearStartConfirmation?.();
      this.card._state.clearCancelRunConfirmation?.();
      this.card._state.closeRunProfileEditor?.();

      await this.card.refreshDashboardSnapshot?.();
      this.card._scheduleRender();
    });

    this.card._on(
      this.card.$("[data-action='save-new-run-profile']"),
      "click",
      async () => {
        const draft = this.card._state.runProfileDraft?.();
        const name = String(draft?.name ?? "").trim();
        if (!name) {
          this.card.showToast(this.t("bind_run_profiles.enter_name"), { kind: "error" });
          return;
        }

        const result = await this.card._actions.saveRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          name,
          expose_as_button: Boolean(draft?.expose_as_button),
        });

        if (result?.ok === false) {
          this.card.showToast((result.reason ? this.esc(result.reason) : this.t("bind_run_profiles.unable_save")), { kind: "error" });
          return;
        }

        await this.card.refreshRunProfiles?.();
        this.card._state.selectRunProfile?.(result?.profile_id ?? null);
        this.card._state.closeRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );

    this.card._on(
      this.card.$("[data-action='run-run-profile']"),
      "click",
      async (e) => {
        const profileId = e.currentTarget.dataset.profileId;
        if (!profileId) return;

        this.card._state.selectRunProfile?.(profileId);
        this.card._state.setAppliedRunProfile?.(profileId);

        const result = await this.card._actions.startRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          profile_id: profileId,
        });

        if (result?.ok === false) {
          this.card.showToast((result.reason ? this.esc(result.reason) : this.t("bind_run_profiles.unable_run")), { kind: "error" });
          return;
        }

        this.card._state.clearStartConfirmation?.();
        this.card._state.closeRunProfileEditor?.();
        await this.card.refreshDashboardSnapshot?.();
        this.card._scheduleRender();
      }
    );

    this.card._on(
      this.card.$("[data-action='edit-run-profile']"),
      "click",
      (e) => {
        const profileId = e.currentTarget.dataset.profileId;
        if (!profileId) return;

        this.card._state.selectRunProfile?.(profileId);
        this.card._state.openSelectedRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );

    this.card._on(
      this.card.$("[data-action='overwrite-run-profile']"),
      "click",
      async () => {
        const profile = this.card._state.selectedRunProfile?.();
        const draft = this.card._state.runProfileDraft?.();
        if (!profile) return;

        const name = String(draft?.name ?? "").trim();
        if (!name) {
          this.card.showToast(this.t("bind_run_profiles.enter_name"), { kind: "error" });
          return;
        }

        const result = await this.card._actions.overwriteRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          profile_id: profile.id,
          name,
          expose_as_button: Boolean(draft?.expose_as_button),
        });

        if (result?.ok === false) {
          this.card.showToast((result.reason ? this.esc(result.reason) : this.t("bind_run_profiles.unable_overwrite")), { kind: "error" });
          return;
        }

        // Persist the ordered steps too, when the user has engaged the steps editor.
        if (this.card._state.isDraftStepsExpanded?.()) {
          const clean = sanitizeStepsForSave(this.card._state.runProfileDraftSteps?.() ?? []);
          if (!stepsHaveRoomGroup(clean)) {
            this.card.showToast(this.t("bind_run_profiles.steps_need_group"), { kind: "error" });
            return;
          }
          await this.card._actions.setRunProfileSteps({
            vacuum_entity_id: this.card._state.vacuumEntityId?.(),
            map_id: this.card._state.activeMapId?.(),
            profile_id: profile.id,
            steps: clean,
          });
        }

        await this.card.refreshRunProfiles?.();
        this.card._state.selectRunProfile?.(profile.id);
        this.card._state.closeRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );

    this.card._on(
      this.card.$("[data-action='delete-run-profile']"),
      "click",
      async (e) => {
        const profileId = e.currentTarget.dataset.profileId;
        const profile = this.card._state.selectedRunProfile?.();
        if (!profileId || !profile) return;

        if (!(await this.card._confirm(this.t("bind_run_profiles.confirm_delete", { name: this.esc(profile.name) }), { danger: true }))) return;

        const result = await this.card._actions.deleteRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          profile_id: profileId,
        });

        if (result?.ok === false) {
          this.card.showToast((result.reason ? this.esc(result.reason) : this.t("bind_run_profiles.unable_delete")), { kind: "error" });
          return;
        }

        await this.card.refreshRunProfiles?.();
        this.card._state.selectRunProfile?.(null);
        this.card._state.closeRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );

    /* ---- steps editor (charge steps + room groups) ---- */

    this.card._onAll("[data-action='add-run-profile-charge']", "click", () => {
      this.card._state.addDraftChargeStep?.();
      this.card._scheduleRender();
    });

    this.card._onAll("[data-action='capture-run-profile-group']", "click", () => {
      const ok = this.card._state.captureCurrentRoomsAsDraftGroup?.();
      if (ok === false) {
        this.card.showToast(this.t("bind_run_profiles.capture_no_rooms"), { kind: "error" });
        return;
      }
      this.card._scheduleRender();
    });

    this.card._onAll("[data-action='remove-run-profile-step']", "click", (e) => {
      this.card._state.removeDraftStep?.(Number(e.currentTarget.dataset.stepIndex));
      this.card._scheduleRender();
    });

    this.card._onAll("[data-action='move-run-profile-step']", "click", (e) => {
      this.card._state.moveDraftStep?.(
        Number(e.currentTarget.dataset.stepIndex),
        Number(e.currentTarget.dataset.stepDir),
      );
      this.card._scheduleRender();
    });

    this.card._onAll("[data-run-profile-charge-index]", "change", (e) => {
      this.card._state.setDraftChargeTarget?.(
        Number(e.currentTarget.dataset.runProfileChargeIndex),
        e.currentTarget.value,
      );
      this.card._scheduleRender();
    });
  };
}
