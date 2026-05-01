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
        alert(result.reason || "Unable to apply run profile.");
        return;
      }

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
          alert("Enter a name for the run profile.");
          return;
        }

        const result = await this.card._actions.saveRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          name,
          expose_as_button: Boolean(draft?.expose_as_button),
        });

        if (result?.ok === false) {
          alert(result.reason || "Unable to save run profile.");
          return;
        }

        await this.card.refreshRunProfiles?.();
        this.card._state.selectRunProfile?.(result?.profile_id ?? null);
        this.card._state.closeRunProfileEditor?.();
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
          alert("Enter a name for the run profile.");
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
          alert(result.reason || "Unable to overwrite run profile.");
          return;
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

        if (!confirm(`Delete run profile "${profile.name}"?`)) return;

        const result = await this.card._actions.deleteRunProfile({
          vacuum_entity_id: this.card._state.vacuumEntityId?.(),
          map_id: this.card._state.activeMapId?.(),
          profile_id: profileId,
        });

        if (result?.ok === false) {
          alert(result.reason || "Unable to delete run profile.");
          return;
        }

        await this.card.refreshRunProfiles?.();
        this.card._state.selectRunProfile?.(null);
        this.card._state.closeRunProfileEditor?.();
        this.card._scheduleRender();
      }
    );
  };
}
