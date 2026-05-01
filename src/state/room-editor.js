/**
 * ============================================================
 * STATE: ROOM EDITOR MODAL
 * ============================================================
 *
 * PURPOSE
 * -------
 * Tracks which room editor modal is open and the current
 * working state of the fields being edited.
 *
 * This file owns:
 * - modal open/close state
 * - active room reference for the open modal
 * - live field values (working copy before save)
 * - field visibility rules (carpet lock, mop-only fields)
 * - "Custom" detection (has any field diverged from profile)
 * - reading clean mode / suction / water options from vacuum entities
 * - fallback option derivation from integration profile metadata
 * - applying valid room profiles into the working editor state
 * - auto-detecting when manual edits match a preset profile again
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - service calls (lives in actions/rooms.js)
 * - rendering (lives in renderers/room-editor.js)
 * - event binding (lives in bindings/room-editor.js)
 *
 * CARPET LOCK RULE
 * ----------------
 * When floor_type === "carpet", only vacuum-only clean modes
 * are allowed. Mop and vacuum+mop modes are filtered out.
 * Water level and edge mopping are hidden entirely.
 * This is enforced here so renderers and actions both use
 * the same rule without duplicating it.
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * Mixed onto VacuumCardState via applyRoomEditorState(proto).
 * Applied after rooms.js in the state combiner.
 *
 * PROFILE MATCHING RULE
 * ---------------------
 * The editor should not stay "custom" if the current working
 * fields exactly match a known preset profile.
 *
 * This means:
 * - clicking a preset applies that preset directly
 * - manual edits that diverge from presets become custom
 * - manual edits that land exactly on a preset snap back to
 *   that preset automatically
 *
 * This keeps the room editor feeling polished instead of
 * exposing the technical distinction too aggressively.
 *
 * ============================================================
 */

export function applyRoomEditorState(proto) {

  /* =========================================================
     MODAL OPEN / CLOSE
     ========================================================= */

  proto.openRoomEditor = function (roomId, mapId) {
    const rooms = this.getRoomsForActiveMap();
    const room = rooms.find(
      (r) => String(r.id) === String(roomId) && String(r.mapId) === String(mapId)
    );

    if (!room) return;

    this._roomEditorRoomId = room.id;
    this._roomEditorMapId = room.mapId;

    this._roomEditorFields = {
      clean_mode: this._canonicalCleanModeDisplay(room.cleanMode ?? "vacuum"),
      fan_speed: room.fanSpeed ?? null,
      water_level: (() => {
        const value = room.waterLevel ?? null;
        if (String(value ?? "").trim().toLowerCase() === "off") return null;
        return value;
      })(),
      clean_intensity:
        room.cleanIntensity ??
        room.selected_profile_details?.clean_intensity ??
        "Quick",
      clean_passes: room.cleanPasses ?? 1,
      edge_mopping: room.edgeMopping ?? false,
      profile_name: room.profileName ?? "vacuum_quick",
    };

    this._syncEditorProfileFromFields();
  };

  proto.closeRoomEditor = function () {
    this._roomEditorRoomId = null;
    this._roomEditorMapId = null;
    this._roomEditorFields = null;
    this._skipRefreshOnClose = false;
  };

  proto.setSkipRefreshOnClose = function (skip) {
    this._skipRefreshOnClose = !!skip;
  };

  proto.shouldSkipRefreshOnClose = function () {
    return !!this._skipRefreshOnClose;
  };

  proto.isRoomEditorOpen = function () {
    return this._roomEditorRoomId != null;
  };

  proto.activeEditorRoom = function () {
    if (!this._roomEditorRoomId) return null;

    const rooms = this.getRoomsForActiveMap();
    return rooms.find(
      (r) =>
        String(r.id) === String(this._roomEditorRoomId) &&
        String(r.mapId) === String(this._roomEditorMapId)
    ) ?? null;
  };

  proto.editorFields = function () {
    return this._roomEditorFields ?? null;
  };

  proto.availableEditorProfiles = function () {
    return this.roomProfilesLibrary?.() ?? {};
  };

  proto.editorProfileLabels = function () {
    return Object.fromEntries(
      this.roomProfilesList?.().map((profile) => [profile.name, profile.label]) ?? []
    );
  };

  proto.getEditorProfileDefinition = function (profileName) {
    return this.roomProfileDefinition?.(profileName) ?? null;
  };

  /* =========================================================
     SHARED OPTION HELPERS
     ========================================================= */

  proto._profileDerivedOptions = function (fieldName) {
    const profiles = this.availableEditorProfiles();
    const values = new Set();

    Object.values(profiles).forEach((profile) => {
      const value = profile?.[fieldName];
      if (value != null && String(value).trim() !== "") {
        values.add(String(value));
      }
    });

    return Array.from(values);
  };

  proto._normalizeOptionList = function (values) {
    const seen = new Set();
    const result = [];

    for (const value of values ?? []) {
      const text = String(value ?? "").trim();
      if (!text) continue;

      const key = text.toLowerCase();
      if (seen.has(key)) continue;

      seen.add(key);
      result.push(text);
    }

    return result;
  };

  /**
   * Canonical display value for clean mode options shown in the modal.
   * This removes duplicate UI entries like:
   * - vacuum_mop
   * - Vacuum and mop
   *
   * by collapsing them to one user-facing label.
   */
  proto._canonicalCleanModeDisplay = function (value) {
    const raw = String(value ?? "").trim();
    const lowered = raw.toLowerCase().replace(/[\s+_-]+/g, "");

    if (lowered === "vacuummop" || lowered === "vacuumandmop") {
      return "Vacuum and mop";
    }

    if (lowered === "vacuum") {
      return "Vacuum";
    }

    if (lowered === "mop") {
      return "Mop";
    }

    return raw;
  };

  /**
   * Canonical internal comparison value for clean modes so profile
   * matching treats all vacuum+mop spellings as the same mode.
   */
  proto._canonicalCleanModeCompare = function (value) {
    const raw = String(value ?? "").trim().toLowerCase().replace(/[\s+_-]+/g, "");

    if (raw === "vacuummop" || raw === "vacuumandmop") return "vacuum_mop";
    if (raw === "vacuum") return "vacuum";
    if (raw === "mop") return "mop";

    return raw;
  };

  /**
   * Profile vocabulary uses:
   * - Quick
   * - Deep
   *
   * Real room editor entity uses:
   * - Quick
   * - Normal
   * - Narrow
   *
   * Mapping:
   * - Quick -> Quick
   * - Deep  -> Narrow
   *
   * Normal is intentionally a custom/manual-only value and
   * does not correspond to a preset profile.
   */
  proto._profileIntensityToEditorIntensity = function (value) {
    const raw = String(value ?? "").trim().toLowerCase();

    if (raw === "quick") return "Quick";
    if (raw === "deep") return "Narrow";

    return value ?? null;
  };

  proto._editorIntensityToComparableProfileIntensity = function (value) {
    const raw = String(value ?? "").trim().toLowerCase();

    if (raw === "quick") return "quick";
    if (raw === "narrow") return "deep";

    return raw;
  };

  /* =========================================================
     PROFILE MATCHING
     ========================================================= */

  proto._normalizeEditorComparisonValue = function (value, fieldName = "") {
    if (fieldName === "clean_mode") {
      return this._canonicalCleanModeCompare(value);
    }

    if (fieldName === "clean_intensity") {
      return this._editorIntensityToComparableProfileIntensity(value);
    }

    if (value == null) return null;
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return Number(value);

    const text = String(value).trim();
    const lowered = text.toLowerCase();

    if (lowered === "true") return true;
    if (lowered === "false") return false;

    const numeric = Number(text);
    if (!Number.isNaN(numeric) && text !== "") return numeric;

    return lowered;
  };

  proto._buildComparableProfileFields = function (profile) {
    const roomIsCarpet = this.isEditorRoomCarpet();
    const cleanMode = this._canonicalCleanModeDisplay(profile?.clean_mode ?? "vacuum");
    const mopActive = this.isMopMode(cleanMode) && !roomIsCarpet;

    return {
      clean_mode: cleanMode,
      fan_speed: profile?.fan_speed ?? null,
      water_level: mopActive ? (profile?.water_level ?? null) : null,
      clean_intensity: this._profileIntensityToEditorIntensity(profile?.clean_intensity ?? null),
      clean_passes: Number(profile?.clean_passes ?? 1),
      edge_mopping: mopActive ? Boolean(profile?.edge_mopping) : false,
    };
  };

  proto._editorFieldsMatchProfile = function (fields, profile) {
    if (!fields || !profile) return false;

    const comparableProfile = this._buildComparableProfileFields(profile);

    return (
      this._normalizeEditorComparisonValue(fields.clean_mode, "clean_mode") === this._normalizeEditorComparisonValue(comparableProfile.clean_mode, "clean_mode") &&
      this._normalizeEditorComparisonValue(fields.fan_speed) === this._normalizeEditorComparisonValue(comparableProfile.fan_speed) &&
      this._normalizeEditorComparisonValue(fields.water_level) === this._normalizeEditorComparisonValue(comparableProfile.water_level) &&
      this._normalizeEditorComparisonValue(fields.clean_intensity, "clean_intensity") === this._normalizeEditorComparisonValue(comparableProfile.clean_intensity, "clean_intensity") &&
      this._normalizeEditorComparisonValue(fields.clean_passes) === this._normalizeEditorComparisonValue(comparableProfile.clean_passes) &&
      this._normalizeEditorComparisonValue(fields.edge_mopping) === this._normalizeEditorComparisonValue(comparableProfile.edge_mopping)
    );
  };

  proto.matchingEditorProfileName = function (fields = null) {
    const activeFields = fields ?? this.editorFields();
    if (!activeFields) return null;

    const profiles = this.availableEditorProfiles();

    for (const [profileName, profileDefinition] of Object.entries(profiles)) {
      if (this._editorFieldsMatchProfile(activeFields, profileDefinition)) {
        return profileName;
      }
    }

    return null;
  };

  proto._syncEditorProfileFromFields = function () {
    if (!this._roomEditorFields) return;

    const matchedProfile = this.matchingEditorProfileName(this._roomEditorFields);

    this._roomEditorFields = {
      ...this._roomEditorFields,
      profile_name: matchedProfile ?? "custom",
    };
  };

  /* =========================================================
     FIELD MUTATION
     ========================================================= */

  proto.applyEditorProfile = function (profileName) {
    if (!this._roomEditorFields) return;

    const profile = this.getEditorProfileDefinition(profileName);
    if (!profile) return;

    const resolvedCleanMode = this._canonicalCleanModeDisplay(
      profile.clean_mode ?? this._roomEditorFields.clean_mode ?? "vacuum"
    );
    const roomIsCarpet = this.isEditorRoomCarpet();
    const mopActive = this.isMopMode(resolvedCleanMode) && !roomIsCarpet;

    this._roomEditorFields = {
      ...this._roomEditorFields,
      profile_name: String(profileName),
      clean_mode: resolvedCleanMode,
      fan_speed: profile.fan_speed ?? null,
      water_level: mopActive ? (profile.water_level ?? null) : null,
      clean_intensity: this._profileIntensityToEditorIntensity(profile.clean_intensity ?? null),
      clean_passes: Number(profile.clean_passes ?? 1),
      edge_mopping: mopActive ? Boolean(profile.edge_mopping) : false,
    };
  };

  proto.updateEditorField = function (key, value) {
    if (!this._roomEditorFields) return;

    if (key === "profile_name") {
      if (value === "custom") {
        this._roomEditorFields = {
          ...this._roomEditorFields,
          profile_name: "custom",
        };
      } else {
        this.applyEditorProfile(value);
      }
      return;
    }

    const nextValue = key === "clean_mode"
      ? this._canonicalCleanModeDisplay(value)
      : value;

    this._roomEditorFields = {
      ...this._roomEditorFields,
      [key]: nextValue,
    };

    if (key === "clean_mode" && !this.isMopMode(nextValue)) {
      this._roomEditorFields.water_level = null;
      this._roomEditorFields.edge_mopping = false;
    }

    if (key === "clean_mode" && this.isEditorRoomCarpet()) {
      this._roomEditorFields.water_level = null;
      this._roomEditorFields.edge_mopping = false;
    }

    this._syncEditorProfileFromFields();
  };

  /* =========================================================
     FIELD VISIBILITY RULES
     ========================================================= */

  proto.isMopMode = function (cleanMode) {
    const mode = this._canonicalCleanModeCompare(cleanMode);
    return mode.includes("mop") || mode.includes("wash");
  };

  proto.isEditorRoomCarpet = function () {
    const room = this.activeEditorRoom();
    return room?.floorType === "carpet";
  };

  proto.showWaterLevel = function () {
    if (this.isEditorRoomCarpet()) return false;
    const fields = this.editorFields();
    if (!fields) return false;
    return this.isMopMode(fields.clean_mode);
  };

  proto.showEdgeMopping = function () {
    if (this.isEditorRoomCarpet()) return false;
    const fields = this.editorFields();
    if (!fields) return false;
    return this.isMopMode(fields.clean_mode);
  };

  /* =========================================================
     ENTITY OPTION READERS
     ========================================================= */

  proto.cleanModeOptions = function () {
    const objectId = this.vacuumObjectId();
    const entityId = `select.${objectId}_cleaning_mode`;
    const entityOptions = this.attrsOf(entityId)?.options ?? [];
    const profileOptions = this._profileDerivedOptions("clean_mode");

    const canonicalized = [
      ...entityOptions,
      ...profileOptions,
      "vacuum",
      "vacuum_mop",
    ].map((option) => this._canonicalCleanModeDisplay(option));

    const options = this._normalizeOptionList(canonicalized);

    return options.filter((o) => {
      const lower = String(o).toLowerCase().replace(/[\s_-]/g, "");

      if (lower.includes("mopaftersweep") || lower.includes("afterswee")) return false;
      if (this.isEditorRoomCarpet() && this.isMopMode(o)) return false;

      return true;
    });
  };

  proto.suctionLevelOptions = function () {
    const objectId = this.vacuumObjectId();
    const entityId = `select.${objectId}_suction_level`;
    const entityOptions = this.attrsOf(entityId)?.options ?? [];
    const profileOptions = this._profileDerivedOptions("fan_speed");

    return this._normalizeOptionList([
      ...entityOptions,
      ...profileOptions,
      "Quiet",
      "Standard",
      "Turbo",
      "Max",
    ]).filter(
      (o) => String(o).toLowerCase().replace(/[\s_-]/g, "") !== "boostiq"
    );
  };

  proto.waterLevelOptions = function () {
    const objectId = this.vacuumObjectId();
    const entityId = `select.${objectId}_water_level`;
    const entityOptions = this.attrsOf(entityId)?.options ?? [];
    const profileOptions = this._profileDerivedOptions("water_level");

    return this._normalizeOptionList([
      ...entityOptions,
      ...profileOptions,
      "Low",
      "Medium",
      "High",
    ]).filter((o) => {
      const normalized = String(o ?? "").trim().toLowerCase().replace(/[\s_-]/g, "");
      return normalized !== "off";
    });
  };

  proto.cleanIntensityOptions = function () {
    const room = this.activeEditorRoom();

    // Primary source of truth: per-room entity options
    if (room?.slug) {
      const objectId = this.vacuumObjectId();
      const entityId = `input_select.${objectId}_map_${room.mapId}_cleaning_speed_${room.slug}`;
      const entityOptions = this.attrsOf(entityId)?.options ?? [];

      const normalizedEntityOptions = this._normalizeOptionList(entityOptions);
      if (normalizedEntityOptions.length) return normalizedEntityOptions;
    }

    // Fallback only when the entity is missing.
    // Do NOT merge profile labels here because profile intensity
    // vocabulary is not the same as the real room entity vocabulary.
    return this._normalizeOptionList([
      "Quick",
      "Normal",
      "Narrow",
    ]);
  };

  /* =========================================================
     CUSTOM DETECTION
     ========================================================= */

  proto.isCustomProfile = function () {
    const fields = this.editorFields();
    if (!fields) return false;
    return String(fields.profile_name ?? "").toLowerCase() === "custom";
  };

  proto.currentEditorManagedProfileName = function () {
    const fields = this.editorFields();
    if (!fields) return null;

    const profileName = String(fields.profile_name ?? "").trim();
    if (!profileName || profileName.toLowerCase() === "custom") {
      return null;
    }

    return profileName;
  };
}
