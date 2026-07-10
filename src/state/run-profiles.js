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

import {
  insertChargeStep,
  removeStep,
  setChargeTarget,
  moveStep,
  roomsToGroupStep,
  DEFAULT_CHARGE_TARGET,
  insertWaitStep,
  setWaitMinutes,
  DEFAULT_WAIT_MINUTES,
} from "./steps-order.js";

export function applyRunProfilesState(proto) {
  proto._emptyRunProfileDraft = function () {
    return {
      name: "",
      expose_as_button: false,
      steps: [],
      stepsExpanded: false,
    };
  };

  // Deep-ish clone of a steps list so editor mutations never touch the stored profile.
  proto._cloneRunProfileSteps = function (steps) {
    return JSON.parse(JSON.stringify(Array.isArray(steps) ? steps : []));
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

  // Local mirror of the backend has_stops rule (SHARED CONTRACT): a SEQUENCED run —
  // any wait/charge_wait boundary OR more than one room_group. Used only as a fallback
  // when the backend hasn't stamped has_stops on the payload; the backend flag wins.
  proto._deriveHasStops = function (steps) {
    if (!Array.isArray(steps)) return false;
    let roomGroups = 0;
    for (const step of steps) {
      const type = step?.type;
      if (type === "charge_wait" || type === "wait") return true;
      if (type === "room_group") roomGroups += 1;
    }
    return roomGroups > 1;
  };

  proto._normalizeRunProfile = function (profile) {
    const steps = Array.isArray(profile?.steps) ? profile.steps : [];
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
      steps,
      has_charge_steps: Boolean(profile?.has_charge_steps),
      // Sequenced-run flag: prefer the backend-derived value, fall back to deriving it
      // from steps so a WAIT-only or multi-group profile still gates correctly.
      has_stops:
        profile?.has_stops != null
          ? Boolean(profile.has_stops)
          : this._deriveHasStops(steps),
    };
  };

  proto._ensureRunProfilesState = function () {
    if (!this._runProfilesState) {
      this._runProfilesState = {
        profiles: [],
        selectedProfileId: null,
        appliedProfileId: null,
        steppedPreviewCollapsed: false,
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

  /* ---- applied-profile tracking (A: Start dispatches an applied stepped profile) ---- */

  proto.appliedRunProfileId = function () {
    return this._ensureRunProfilesState().appliedProfileId ?? null;
  };

  proto.setAppliedRunProfile = function (profileId) {
    this._ensureRunProfilesState().appliedProfileId = profileId ? String(profileId) : null;
  };

  proto.clearAppliedRunProfile = function () {
    this._ensureRunProfilesState().appliedProfileId = null;
  };

  // The applied profile's id IF it is a SEQUENCED run (has_stops — a wait/charge boundary
  // OR more than one room_group) still in the library — the signal that Start should dispatch
  // its steps (start_run_profile) instead of a flat start_selected_rooms, which would drop the
  // wait/charge + group ordering. Gates on has_stops (NOT charge-only has_charge_steps) so a
  // WAIT-only or multi-group profile still routes through the stepped path. Cleared when the
  // user diverges (hand-edits rooms) so a flat run stays flat. Returns null otherwise.
  proto.pendingStepRunProfileId = function () {
    const state = this._ensureRunProfilesState();
    const id = state.appliedProfileId;
    if (!id) return null;
    const profile = state.profiles.find((p) => p.id === id);
    return profile?.has_stops ? id : null;
  };

  proto.isSteppedPreviewCollapsed = function () {
    return Boolean(this._ensureRunProfilesState().steppedPreviewCollapsed);
  };

  proto.toggleSteppedPreviewCollapsed = function () {
    const state = this._ensureRunProfilesState();
    state.steppedPreviewCollapsed = !state.steppedPreviewCollapsed;
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
      steps: this._cloneRunProfileSteps(profile.steps),
      stepsExpanded: Boolean(profile.has_charge_steps),
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

  /* ---- steps editor draft (charge steps + room groups) ---- */

  proto.runProfileDraftSteps = function () {
    const draft = this._ensureRunProfilesState().draft;
    return Array.isArray(draft.steps) ? draft.steps : [];
  };

  proto.isDraftStepsExpanded = function () {
    return Boolean(this._ensureRunProfilesState().draft.stepsExpanded);
  };

  proto._setDraftSteps = function (steps) {
    const state = this._ensureRunProfilesState();
    state.draft = { ...state.draft, steps: Array.isArray(steps) ? steps : [] };
  };

  proto.expandDraftSteps = function () {
    const state = this._ensureRunProfilesState();
    state.draft = { ...state.draft, stepsExpanded: true };
  };

  proto.addDraftChargeStep = function (target = DEFAULT_CHARGE_TARGET) {
    const steps = this.runProfileDraftSteps();
    this._setDraftSteps(insertChargeStep(steps, steps.length, target));
    this.expandDraftSteps();
  };

  proto.addDraftWaitStep = function (minutes = DEFAULT_WAIT_MINUTES) {
    const steps = this.runProfileDraftSteps();
    this._setDraftSteps(insertWaitStep(steps, steps.length, minutes));
    this.expandDraftSteps();
  };

  proto.setDraftWaitMinutes = function (index, value) {
    this._setDraftSteps(setWaitMinutes(this.runProfileDraftSteps(), index, value));
  };

  proto.removeDraftStep = function (index) {
    this._setDraftSteps(removeStep(this.runProfileDraftSteps(), index));
  };

  proto.setDraftChargeTarget = function (index, value) {
    this._setDraftSteps(setChargeTarget(this.runProfileDraftSteps(), index, value));
  };

  proto.moveDraftStep = function (index, direction) {
    const from = Number(index);
    this._setDraftSteps(moveStep(this.runProfileDraftSteps(), from, from + Number(direction)));
  };

  // Snapshot the current Rooms-view enabled rooms + settings as a new room_group at the end.
  // Returns false (no-op) when nothing is enabled.
  proto.captureCurrentRoomsAsDraftGroup = function () {
    const rooms = this.getRoomsForActiveMap?.() ?? [];
    const group = roomsToGroupStep(rooms);
    if (!group.rooms.length) return false;
    this._setDraftSteps([...this.runProfileDraftSteps(), group]);
    this.expandDraftSteps();
    return true;
  };
}
