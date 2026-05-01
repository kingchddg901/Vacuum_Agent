/**
 * ============================================================
 * STATE: RUN PROFILES
 * ============================================================
 *
 * PURPOSE
 * -------
 * Card-side state for saved run profile management.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * The backend remains the source of truth for the persisted
 * profile library. This module owns only:
 * - normalized in-card profile list
 * - selected profile
 * - save/edit form state
 *
 * ============================================================
 */

export function applyRunProfilesState(proto) {
  proto._emptyRunProfileDraft = function () {
    return {
      name: "",
      expose_as_button: false,
    };
  };

  proto._normalizeRunProfilesPayload = function (payload) {
    if (Array.isArray(payload)) {
      return {
        profiles: payload,
        library: {},
      };
    }

    if (payload && typeof payload === "object") {
      return {
        profiles: Array.isArray(payload.profiles)
          ? payload.profiles
          : Array.isArray(payload.saved_run_profiles)
            ? payload.saved_run_profiles
            : [],
        library:
          payload.library && typeof payload.library === "object" && !Array.isArray(payload.library)
            ? payload.library
            : {},
      };
    }

    return {
      profiles: [],
      library: {},
    };
  };

  proto._normalizeRunProfile = function (profile) {
    return {
      id: String(profile?.id ?? profile?.profile_id ?? ""),
      name: String(profile?.name ?? "Unnamed Profile"),
      vacuum_entity_id: String(profile?.vacuum_entity_id ?? ""),
      map_id: String(profile?.map_id ?? ""),
      room_count: Number(profile?.room_count ?? 0),
      room_ids: Array.isArray(profile?.room_ids) ? profile.room_ids : [],
      room_names: Array.isArray(profile?.room_names) ? profile.room_names : [],
      room_names_label: String(profile?.room_names_label ?? ""),
      expose_as_button: Boolean(profile?.expose_as_button),
      summary: String(profile?.summary ?? ""),
      created_at: String(profile?.created_at ?? ""),
      updated_at: String(profile?.updated_at ?? ""),
      rooms: Array.isArray(profile?.rooms) ? profile.rooms : [],
    };
  };

  proto._ensureRunProfilesState = function () {
    if (!this._runProfilesState) {
      this._runProfilesState = {
        profiles: [],
        selectedProfileId: null,
        editorOpen: false,
        editorMode: "new",
        editorProfileId: null,
        draft: this._emptyRunProfileDraft(),
      };
    }

    return this._runProfilesState;
  };

  proto.setRunProfilesLibrary = function (payload) {
    const state = this._ensureRunProfilesState();
    const normalizedPayload = this._normalizeRunProfilesPayload(payload);

    const profiles = normalizedPayload.profiles
      .map((profile) => {
        const profileId = String(profile?.id ?? profile?.profile_id ?? "");
        const detailedProfile =
          profileId && normalizedPayload.library?.[profileId]
            ? normalizedPayload.library[profileId]
            : null;

        return this._normalizeRunProfile({
          ...profile,
          ...(detailedProfile ?? {}),
        });
      })
      .filter((profile) => profile.id);

    state.profiles = profiles;

    if (
      state.selectedProfileId &&
      !profiles.some((profile) => profile.id === state.selectedProfileId)
    ) {
      state.selectedProfileId = null;
    }

    if (
      state.editorProfileId &&
      !profiles.some((profile) => profile.id === state.editorProfileId)
    ) {
      state.editorOpen = false;
      state.editorMode = "new";
      state.editorProfileId = null;
      state.draft = this._emptyRunProfileDraft();
    }
  };

  proto.savedRunProfiles = function () {
    return this._ensureRunProfilesState().profiles;
  };

  proto.savedRunProfilesCount = function () {
    return this.savedRunProfiles().length;
  };

  proto.selectedRunProfileId = function () {
    return this._ensureRunProfilesState().selectedProfileId ?? null;
  };

  proto.selectedRunProfile = function () {
    const state = this._ensureRunProfilesState();
    return state.profiles.find((profile) => profile.id === state.selectedProfileId) ?? null;
  };

  proto.selectRunProfile = function (profileId) {
    const state = this._ensureRunProfilesState();
    state.selectedProfileId = profileId ? String(profileId) : null;
  };

  proto.openNewRunProfileEditor = function () {
    const state = this._ensureRunProfilesState();
    state.editorOpen = true;
    state.editorMode = "new";
    state.editorProfileId = null;
    state.draft = this._emptyRunProfileDraft();
  };

  proto.openSelectedRunProfileEditor = function () {
    const state = this._ensureRunProfilesState();
    const profile = this.selectedRunProfile();
    if (!profile) return;

    state.editorOpen = true;
    state.editorMode = "edit";
    state.editorProfileId = profile.id;
    state.draft = {
      name: profile.name,
      expose_as_button: Boolean(profile.expose_as_button),
    };
  };

  proto.closeRunProfileEditor = function () {
    const state = this._ensureRunProfilesState();
    state.editorOpen = false;
    state.editorMode = "new";
    state.editorProfileId = null;
    state.draft = this._emptyRunProfileDraft();
  };

  proto.isRunProfileEditorOpen = function () {
    return this._ensureRunProfilesState().editorOpen === true;
  };

  proto.runProfileEditorMode = function () {
    return this._ensureRunProfilesState().editorMode ?? "new";
  };

  proto.runProfileDraft = function () {
    return this._ensureRunProfilesState().draft;
  };

  proto.updateRunProfileDraft = function (field, value) {
    const state = this._ensureRunProfilesState();

    if (field === "expose_as_button") {
      state.draft = {
        ...state.draft,
        expose_as_button: Boolean(value),
      };
      return;
    }

    state.draft = {
      ...state.draft,
      [field]: value,
    };
  };
}
