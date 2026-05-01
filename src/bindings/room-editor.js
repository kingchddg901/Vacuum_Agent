/**
 * ============================================================
 * BINDINGS: ROOM EDITOR
 * ============================================================
 *
 * Wires the room editor modal — open/close, field changes, profile
 * save/overwrite/rename/delete actions, and save-and-close flow.
 *
 * ============================================================
 */

/**
 * Mix room editor binding methods onto the given prototype.
 *
 * @param {object} proto - VacuumCardBindings prototype to extend.
 */
export function applyRoomEditorBindings(proto) {
  /**
   * Bind all room editor modal interactions.
   */
  proto._bindRoomEditor = function () {
    this._bindRoomEditorOpen();
    this._bindRoomEditorClose();
    this._bindRoomEditorFields();
    this._bindRoomEditorSave();
    this._bindRoomEditorTransition();
  };

  /** Reload learning estimates after a room settings change. */
  proto._refreshRoomEditorEstimates = async function () {
    try {
      await this.card._learningController?.loadRoomEstimates?.();
      await this.card.refreshDashboardSnapshot?.();
    } catch (err) {
      console.error(
        "[eufy-vacuum-command-center] Failed to refresh room estimates:",
        err
      );
    }
  };

  /** Reload the room profile library after a save/rename/delete. */
  proto._refreshRoomProfileLibrary = async function () {
    try {
      await this.card.refreshRoomProfiles?.();
    } catch (err) {
      console.error(
        "[eufy-vacuum-command-center] Failed to refresh room profile library:",
        err
      );
    }
  };

  /**
   * Build a newline-separated display string of custom profile choices for prompts.
   *
   * @returns {string} Formatted list of `name (label)` entries.
   */
  proto._roomProfileTargetChoices = function () {
    return (this.card._state.customRoomProfiles?.() ?? [])
      .map((profile) => `${profile.name} (${profile.label})`)
      .join("\n");
  };

  /**
   * Resolve which custom profile to target for overwrite/rename/delete.
   * Uses the editor's active profile if it is editable; otherwise prompts the user.
   *
   * @returns {string|null} Profile name key, or null if the user cancelled.
   */
  proto._resolveEditableRoomProfileTarget = function () {
    const selected = this.card._state.currentEditorManagedProfileName?.();
    if (selected && !this.card._state.isProtectedRoomProfile?.(selected)) {
      return selected;
    }

    const customProfiles = this.card._state.customRoomProfiles?.() ?? [];
    if (!customProfiles.length) return null;

    const choiceText = this._roomProfileTargetChoices();
    const entered = window.prompt(
      `Choose a custom profile key:\n\n${choiceText}`,
      customProfiles[0]?.name ?? ""
    );

    const target = String(entered ?? "").trim();
    if (!target) return null;

    const directMatch = customProfiles.find((profile) => profile.name === target);
    if (directMatch) return directMatch.name;

    const labelMatch = customProfiles.find(
      (profile) => String(profile.label).toLowerCase() === target.toLowerCase()
    );

    return labelMatch?.name ?? null;
  };

  /**
   * Surface a backend result message (or fallback) as a browser alert when non-empty.
   *
   * @param {object|null} result - Service response object.
   * @param {string} fallbackMessage - Shown when `result` has no message.
   */
  proto._alertRoomProfileResult = function (result, fallbackMessage) {
    const message = String(result?.message ?? result?.reason ?? fallbackMessage ?? "").trim();
    if (message) {
      window.alert(message);
    }
  };

  /**
   * Suggest a default display label for new profile prompts.
   * Falls back through active profile label → room name → generic string.
   *
   * @returns {string} Suggested label.
   */
  proto._defaultRoomProfileLabel = function () {
    const activeProfileName = this.card._state.currentEditorManagedProfileName?.();
    const activeProfile = activeProfileName
      ? this.card._state.roomProfileDefinition?.(activeProfileName)
      : null;
    const room = this.card._state.activeEditorRoom?.();

    return activeProfile?.label ?? room?.name ?? "Custom Room Profile";
  };

  /**
   * Open the room editor and pre-load the profile library in parallel.
   *
   * @param {number} roomId - Room ID to edit.
   * @param {string} mapId - Map ID for the room.
   */
  proto._openRoomEditorWithProfiles = async function (roomId, mapId) {
    this.card._state.openRoomEditor(roomId, mapId);
    this.card._scheduleRender();
    await this._refreshRoomProfileLibrary();
  };

  /**
   * Prompt for a label and save the current room settings as a new profile.
   */
  proto._handleSaveRoomProfileAsNew = async function () {
    const room = this.card._state.activeEditorRoom?.();
    if (!room) return;

    const label = window.prompt(
      "Save current room settings as a new profile. Enter a display label:",
      this._defaultRoomProfileLabel()
    );

    const trimmedLabel = String(label ?? "").trim();
    if (!trimmedLabel) return;

    const profileName = this.card._state.makeRoomProfileName?.(trimmedLabel);
    const response = await this.card._actions.saveRoomProfileFromRoom?.({
      vacuum_entity_id: this.card._state.vacuumEntityId?.(),
      map_id: String(room.mapId),
      room_id: room.id,
      label: trimmedLabel,
      profile_name: profileName,
    });

    if (!response?.saved) {
      this._alertRoomProfileResult(response, "Failed to save room profile.");
      return;
    }

    await this._refreshRoomProfileLibrary();

    const savedProfileName = String(response?.profile_name ?? profileName ?? "").trim();
    if (savedProfileName) {
      this.card._state.applyEditorProfile?.(savedProfileName);
    }

    this.card._scheduleRender();
  };

  /**
   * Confirm and overwrite an existing custom profile with the current room settings.
   */
  proto._handleOverwriteRoomProfile = async function () {
    const room = this.card._state.activeEditorRoom?.();
    if (!room) return;

    const targetProfileName = this._resolveEditableRoomProfileTarget();
    if (!targetProfileName) return;

    const targetProfile = this.card._state.roomProfileDefinition?.(targetProfileName);
    const confirmed = window.confirm(
      `Overwrite ${targetProfile?.label ?? targetProfileName} with this room's current settings?`
    );
    if (!confirmed) return;

    const response = await this.card._actions.overwriteRoomProfileFromRoom?.({
      vacuum_entity_id: this.card._state.vacuumEntityId?.(),
      map_id: String(room.mapId),
      room_id: room.id,
      profile_name: targetProfileName,
    });

    if (!response?.overwritten) {
      this._alertRoomProfileResult(response, "Failed to overwrite room profile.");
      return;
    }

    await this._refreshRoomProfileLibrary();
    this.card._state.applyEditorProfile?.(targetProfileName);
    this.card._scheduleRender();
  };

  /**
   * Prompt for a new label and optional key, then rename a custom profile.
   */
  proto._handleRenameRoomProfile = async function () {
    const targetProfileName = this._resolveEditableRoomProfileTarget();
    if (!targetProfileName) return;

    const targetProfile = this.card._state.roomProfileDefinition?.(targetProfileName);
    if (!targetProfile || this.card._state.isProtectedRoomProfile?.(targetProfileName)) {
      return;
    }

    const nextLabel = window.prompt(
      "Enter the new display label for this room profile:",
      targetProfile.label
    );
    if (nextLabel == null) return;

    const trimmedLabel = String(nextLabel).trim();
    if (!trimmedLabel) {
      window.alert("A room profile label is required.");
      return;
    }

    const suggestedKey = this.card._state.makeRoomProfileName?.(trimmedLabel, targetProfileName);
    const nextProfileName = window.prompt(
      "Optional: enter a new backend profile key.",
      suggestedKey ?? targetProfileName
    );
    if (nextProfileName == null) return;

    const trimmedProfileName = String(nextProfileName).trim();
    const response = await this.card._actions.renameRoomProfile?.({
      profile_name: targetProfileName,
      new_profile_name:
        trimmedProfileName && trimmedProfileName !== targetProfileName
          ? trimmedProfileName
          : undefined,
      label: trimmedLabel !== targetProfile.label ? trimmedLabel : undefined,
    });

    if (!response?.renamed) {
      this._alertRoomProfileResult(response, "Failed to rename room profile.");
      return;
    }

    await this._refreshRoomProfileLibrary();

    const currentProfileName = this.card._state.currentEditorManagedProfileName?.();
    const replacementProfileName = String(
      response?.profile_name ??
      response?.target_profile_name ??
      targetProfileName
    ).trim();

    if (currentProfileName === targetProfileName && replacementProfileName) {
      this.card._state.applyEditorProfile?.(replacementProfileName);
    }

    this.card._scheduleRender();
  };

  /**
   * Confirm and delete a custom room profile. Resets the editor to the default profile on success.
   */
  proto._handleDeleteRoomProfile = async function () {
    const targetProfileName = this._resolveEditableRoomProfileTarget();
    if (!targetProfileName) return;

    const targetProfile = this.card._state.roomProfileDefinition?.(targetProfileName);
    if (!targetProfile || this.card._state.isProtectedRoomProfile?.(targetProfileName)) {
      return;
    }

    const confirmed = window.confirm(
      `Delete ${targetProfile.label}? This cannot be undone.`
    );
    if (!confirmed) return;

    const response = await this.card._actions.deleteRoomProfile?.({
      profile_name: targetProfileName,
    });

    if (!response?.deleted) {
      this._alertRoomProfileResult(response, "Failed to delete room profile.");
      return;
    }

    await this._refreshRoomProfileLibrary();
    this.card._state._syncEditorProfileFromFields?.();
    this.card._scheduleRender();
  };

  proto._bindRoomEditorOpen = function () {
    this.card._onAll("[data-action='open-room-settings']", "click", async (e) => {
      e.stopPropagation();

      const btn = e.currentTarget;
      const roomId = btn.dataset.roomId;
      const mapId = btn.dataset.mapId;
      if (!roomId || !mapId) return;

      await this._openRoomEditorWithProfiles(roomId, mapId);
    });
  };

  proto._bindRoomEditorClose = function () {
    const modal = this.card.$("[data-stop-propagation]");
    if (modal) {
      modal.addEventListener("click", (e) => e.stopPropagation());
    }

    this.card._onAll("[data-action='close-room-editor']", "click", async () => {
      const shouldSkip = this.card._state.shouldSkipRefreshOnClose();

      if (shouldSkip) {
        this.card._state.setSkipRefreshOnClose(false);
      } else {
        await this._refreshRoomEditorEstimates();
      }

      this.card._state.closeRoomEditor();
      this.card._scheduleRender();
    });
  };

  proto._bindRoomEditorFields = function () {
    this.card._onAll("[data-field]", "click", (e) => {
      const btn = e.currentTarget;
      const field = btn.dataset.field;
      let value = btn.dataset.value;

      if (!field || value === undefined) return;

      if (btn.dataset.action === "apply-profile") {
        this.card._state.applyEditorProfile(value);
        this.card._scheduleRender();
        return;
      }

      if (field === "clean_passes") value = Number(value);
      if (field === "edge_mopping") value = value === "true";

      this.card._state.updateEditorField(field, value);
      this.card._scheduleRender();
    });
  };

  proto._bindRoomEditorTransition = function () {
    this.card._onAll("[data-action='toggle-room-transition']", "click", async (e) => {
      e.stopPropagation();
      const btn = e.currentTarget;
      const roomId = btn.dataset.roomId;
      const isTransition = btn.dataset.value === "true";
      if (!roomId) return;

      try {
        await this.card._actions.saveRoomTransition?.(roomId, isTransition);
        await this.card.refreshDashboardSnapshot?.();
        this.card._scheduleRender();
      } catch (err) {
        console.error(
          "[eufy-vacuum-command-center] Failed to save room transition flag:",
          err
        );
      }
    });
  };

  proto._bindRoomEditorSave = function () {
    this.card._on(
      this.card.$("[data-action='save-room-editor']"),
      "click",
      async () => {
        const room = this.card._state.activeEditorRoom();
        const fields = this.card._state.editorFields();
        if (!room || !fields) return;

        try {
          await this.card._actions.saveRoomEditor(
            room.mapId,
            room.id,
            fields
          );

          this.card._state.setSkipRefreshOnClose(true);

          await this._refreshRoomEditorEstimates();

          this.card._state.closeRoomEditor();
          this.card._scheduleRender();
        } catch (err) {
          console.error(
            "[eufy-vacuum-command-center] Failed to save room editor:",
            err
          );
        }
      }
    );
  };
}
