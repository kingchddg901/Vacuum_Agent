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
      // "" not "Quick": a brand may have no intensity axis at all (Roborock omits
       // it from every profile), and a Eufy word as the universal fallback is the
       // defect this whole seam exists to remove.
      clean_intensity:
        room.cleanIntensity ??
        room.selected_profile_details?.clean_intensity ??
        "",
      clean_passes: room.cleanPasses ?? 1,
      edge_mopping: room.edgeMopping ?? false,
      // Per-room map fill override ("#rrggbb" or null for the themeable palette). Not a profile
      // field — persisted straight through, no profile snapping.
      color: room.color ?? null,
      profile_name: room.profileName ?? "vacuum_quick",
    };

    this._syncEditorProfileFromFields();
  };

  proto.closeRoomEditor = function () {
    this._roomEditorRoomId = null;
    this._roomEditorMapId = null;
    this._roomEditorFields = null;
    this._skipRefreshOnClose = false;
    this._roomEditorSaveError = null;
  };

  // A6-AGX-2 Half B: a backend refusal has to survive long enough to be
  // rendered. update_room_fields can return {ok:false, reason:"invalid_access_graph"},
  // and both save bindings discarded it and closed the modal anyway — so the
  // edit silently reverted on the next snapshot with no banner and no toast.
  // Mirrors setRoomAccessSaveError/roomAccessSaveError in state/room-access.js.
  proto.setRoomEditorSaveError = function (error) {
    this._roomEditorSaveError = error ?? null;
  };

  proto.roomEditorSaveError = function () {
    return this._roomEditorSaveError ?? null;
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
   * NO PROFILE <-> EDITOR INTENSITY BRIDGE. There used to be one, mapping a
   * profile's Quick/Narrow/Deep onto Quick/Normal/Narrow, and removing it is the
   * fix for a real defect — leaving this note so it is not reintroduced.
   *
   * It was written when the editor drove upstream's `select.<vac>_cleaning_intensity`
   * entity, whose vocabulary really is Quick/Normal/Narrow. That probing was removed
   * (it was Eufy-only) and the editor now renders the ADAPTER's declared
   * `clean_intensity_options` — Quick / Narrow / Deep, matched by exact identity in
   * `_renderIntensityField`. That is the same vocabulary the profiles are written in,
   * so the bridge had stopped translating between two vocabularies and started
   * rewriting a value into a DIFFERENT valid value of one vocabulary.
   *
   * Applying the built-in "Vacuum Only Deep" wrote "Narrow" into the field: the
   * editor lit the Narrow chip while the profile chip still read Deep, and the wire
   * value went out as "normal" -> CleanExtent.NORMAL(0) -> the Eufy app's Medium.
   * The densest setting was unreachable from a profile, which is the same symptom
   * the wire-side map was fixed for.
   *
   * The wire half stays where it belongs, in the adapter's `dispatch.room_fields`
   * value_map {"Narrow": "normal", "Deep": "narrow"}, pinned by
   * tests/adapters/eufy/test_intensity_wire_mapping.py. Profile values are written
   * through unchanged; the adapter is the only thing that renames them.
   */

  /* =========================================================
     PROFILE MATCHING
     ========================================================= */

  proto._normalizeEditorComparisonValue = function (value, fieldName = "") {
    if (fieldName === "clean_mode") {
      return this._canonicalCleanModeCompare(value);
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
      clean_intensity: profile?.clean_intensity ?? null,
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
      clean_intensity: profile.clean_intensity ?? null,
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
    if (!room) return false;
    // Trust the pre-computed boolean first (set in state/rooms.js from
    // attrs.carpet or floor_type === "carpet"); then fall back to a string
    // match that catches every carpet variant the backend may emit:
    // "carpet", "carpet_low", "carpet_high", "carpet_low_pile",
    // "carpet_high_pile". Without this, low/high-pile carpet rooms slip
    // past the gate and the mop fields render.
    if (room.carpet === true) return true;
    const ft = String(room.floorType ?? "").toLowerCase();
    return ft === "carpet" || ft.startsWith("carpet_") || ft.startsWith("carpet-");
  };

  proto.showWaterLevel = function () {
    if (this.isEditorRoomCarpet()) return false;
    if (this.waterLevelOptions().length === 0) return false;
    // OBSERVE-ONLY tank brands (Roborock S6: a mop tank but no settable mode) report
    // mop_active from the water-box sensor and have no clean_mode — gate water on the
    // physical tank. A SETTABLE-mop brand (Roborock S7+, supports_water_control) has a
    // real per-room clean_mode, so it behaves like Eufy: show water when mopping.
    const mopActive = this.mopActive();
    if (mopActive !== null && !this.supportsSettableMop()) return mopActive;
    const fields = this.editorFields();
    if (!fields) return false;
    return this.isMopMode(fields.clean_mode);
  };

  /**
   * Whether the brand's mop is programmatically SETTABLE (supports_water_control):
   * a real per-room clean_mode + water intensity (Roborock S7+, Eufy), as opposed to
   * an observe-only tank (Roborock S6). Drives whether the editor shows the clean_mode
   * picker or a read-only tank indicator. Default false keeps observe-only brands as-is.
   */
  proto.supportsSettableMop = function () {
    return Boolean(this.dashboardSnapshot?.()?.supports_water_control);
  };

  /**
   * Whether the brand reports a tank-driven mop state (snapshot.mop_active is a
   * bool) and its current value; null when the adapter declares no tank sensor
   * (Eufy → the editor uses clean_mode instead).
   */
  proto.mopActive = function () {
    const v = this.dashboardSnapshot?.()?.mop_active;
    return (v === null || v === undefined) ? null : Boolean(v);
  };

  /**
   * Whether the brand exposes the reusable room-profiles section. False for
   * brands with a single editable per-room field (Roborock: fan only), where a
   * profile would be degenerate. Default true keeps the Eufy editor unchanged.
   */
  proto.supportsRoomProfiles = function () {
    const v = this.dashboardSnapshot?.()?.supports_room_profiles;
    return v === undefined || v === null ? true : Boolean(v);
  };

  /**
   * Upper bound for the Cleaning Passes chips, from the adapter's dispatch
   * passes_max (surfaced via the snapshot). Default 2 (historical Eufy editor).
   */
  proto.maxCleanPasses = function () {
    const n = Number(this.dashboardSnapshot?.()?.max_clean_passes);
    return (Number.isFinite(n) && n >= 1) ? Math.min(Math.trunc(n), 9) : 2;
  };

  /**
   * Whether passes is a single whole-run value (max-wins) rather than per-room
   * (Roborock). The editor keeps per-room chips but notes the strongest applies
   * to the whole run. Default false (per-room, Eufy).
   */
  proto.passesIsGlobal = function () {
    return Boolean(this.dashboardSnapshot?.()?.passes_is_global);
  };

  proto.showEdgeMopping = function () {
    if (this.isEditorRoomCarpet()) return false;
    const fields = this.editorFields();
    if (!fields) return false;
    return this.isMopMode(fields.clean_mode);
  };

  /* =========================================================
     ADAPTER-DRIVEN OPTION READERS
     =========================================================
     Each function returns an `Array<{value: string, label: string}>`
     of dropdown choices for the room editor. The primary source is
     the adapter's vocabulary (declared at adapter registration),
     surfaced to the card via dashboard_snapshot.adapter_vocabulary.
     A defensive merge with profile-derived legacy values keeps any
     saved profile selectable even if its value isn't in the current
     adapter declaration. UX rules (carpet excludes mop, etc.) are
     applied on top. Entity probing of upstream brand selects is
     gone — that was Eufy-only.
     ========================================================= */

  /**
   * Merge adapter-declared options with profile-derived legacy values
   * into a single `[{value, label}]` list, deduped by lowercase value.
   * Profile values that aren't in the adapter list get value-as-label.
   *
   * @param {string} roleKey - "clean_mode" / "fan_speed" / "water_level" / "clean_intensity"
   * @param {string} profileFieldName - matching key inside saved profiles
   * @returns {Array<{value: string, label: string}>}
   */
  /**
   * @param {string} roleKey
   * @param {string} profileFieldName
   * @param {(v: string) => string} [canonicalize] - how to decide two spellings
   *   are the SAME option. Defaults to lowercase. clean_mode passes
   *   _canonicalCleanModeCompare because the stored value is a DISPLAY label
   *   ("Vacuum and mop") while the adapter declares the token ("vacuum_mop") —
   *   without it the legacy-fallback below sees them as different and appends a
   *   duplicate chip (issue #48, visible in the Cleaning Mode row).
   */
  proto._buildOptionListForRole = function (roleKey, profileFieldName, canonicalize) {
    const adapterOptions = this.adapterOptionsFor?.(roleKey) ?? [];
    // When the adapter declares NO options for a role, the brand doesn't expose
    // that field at all — hide it (return []) rather than resurrecting it from
    // profile-derived legacy values. This is the "omit the option list -> hide
    // the picker" contract (e.g. Roborock has no per-room clean_mode / clean
    // intensity, so those rows must not appear).
    if (adapterOptions.length === 0) return [];
    const key_of = canonicalize || ((v) => String(v ?? "").trim().toLowerCase());
    const seen = new Set();
    const result = [];

    for (const opt of adapterOptions) {
      const value = String(opt?.value ?? "").trim();
      if (!value) continue;
      const key = key_of(value);
      if (seen.has(key)) continue;
      seen.add(key);
      result.push({
        value,
        label: String(opt?.label ?? value),
      });
    }
    // Keep ONLY the CURRENT room's saved value as a legacy fallback, so a value
    // the adapter doesn't declare stays visible + re-selectable for THIS room.
    // Previously this merged EVERY profile template's value, which bled foreign
    // values across adapters — e.g. a template's Eufy "Standard" fan speed
    // surfacing in a Roborock room's suction picker (which declares only
    // gentle/quiet/balanced/turbo/max and never "Standard").
    const currentValue = String(this.editorFields?.()?.[profileFieldName] ?? "").trim();
    if (currentValue && !seen.has(key_of(currentValue))) {
      result.push({ value: currentValue, label: currentValue });
    }
    return result;
  };

  proto.cleanModeOptions = function () {
    // issue #48: canonical comparison, so the stored display label and the
    // adapter's token are ONE option rather than two chips.
    const options = this._buildOptionListForRole(
      "clean_mode", "clean_mode", (v) => this._canonicalCleanModeCompare(v)
    );
    // UX rule: carpet rooms cannot use mop modes.
    if (this.isEditorRoomCarpet()) {
      return options.filter((o) => !this.isMopMode(o.value));
    }
    return options;
  };

  proto.suctionLevelOptions = function () {
    return this._buildOptionListForRole("fan_speed", "fan_speed");
  };

  proto.waterLevelOptions = function () {
    const options = this._buildOptionListForRole("water_level", "water_level");

    // "Off" is not a real choice while mopping, and offering it is dishonest:
    // the backend SUBSTITUTES the floor-type water default for an empty/off
    // value on a non-carpet mop room (room_profiles.resolve_room_profile_for_room
    // — "a mop room stayed dry-mopping instead of being corrected"). So a user
    // could pick Off, save, and get Low/Medium back with no explanation.
    //
    // Carpet is untouched: the row is hidden there entirely (showWaterLevel),
    // and carpet's own water default IS the brand's no-water value.
    const fields = this.editorFields();
    if (fields && !this.isEditorRoomCarpet() && this.isMopMode(fields.clean_mode)) {
      return options.filter(
        (o) => String(o?.value ?? "").trim().toLowerCase() !== "off"
      );
    }
    return options;
  };

  proto.cleanIntensityOptions = function () {
    return this._buildOptionListForRole("clean_intensity", "clean_intensity");
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
