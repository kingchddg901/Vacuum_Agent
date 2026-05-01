// Card-local state for the room profile library: normalized profile list and lookup helpers.

export function applyRoomProfilesState(proto) {
  proto._ensureRoomProfilesState = function () {
    if (!this._roomProfilesState) {
      this._roomProfilesState = {
        profile_count: 0,
        protected_profile_names: [],
        profiles: {},
      };
    }

    return this._roomProfilesState;
  };

  proto._normalizeRoomProfile = function (profileName, profile = {}) {
    return {
      name: String(profileName ?? ""),
      label: String(profile?.label ?? profileName ?? "Unnamed Profile"),
      clean_mode: String(profile?.clean_mode ?? "vacuum"),
      fan_speed: String(profile?.fan_speed ?? ""),
      water_level: String(profile?.water_level ?? ""),
      clean_intensity: String(profile?.clean_intensity ?? "Quick"),
      clean_passes: Number(profile?.clean_passes ?? 1),
      carpet: Boolean(profile?.carpet),
      edge_mopping: Boolean(profile?.edge_mopping),
    };
  };

  proto.setRoomProfilesLibrary = function (payload) {
    const state = this._ensureRoomProfilesState();
    const rawProfiles =
      payload?.profiles && typeof payload.profiles === "object" && !Array.isArray(payload.profiles)
        ? payload.profiles
        : {};
    const protectedNames = Array.isArray(payload?.protected_profile_names)
      ? payload.protected_profile_names.map((name) => String(name))
      : [];

    state.profile_count = Number(payload?.profile_count ?? Object.keys(rawProfiles).length ?? 0);
    state.protected_profile_names = protectedNames;
    state.profiles = Object.fromEntries(
      Object.entries(rawProfiles)
        .map(([profileName, profile]) => [
          String(profileName),
          this._normalizeRoomProfile(profileName, profile),
        ])
        .filter(([profileName]) => profileName)
    );
  };

  proto.roomProfilesLibrary = function () {
    return this._ensureRoomProfilesState().profiles;
  };

  proto.roomProfilesCount = function () {
    return this._ensureRoomProfilesState().profile_count ?? 0;
  };

  proto.protectedRoomProfileNames = function () {
    return this._ensureRoomProfilesState().protected_profile_names ?? [];
  };

  proto.isProtectedRoomProfile = function (profileName) {
    const key = String(profileName ?? "").trim();
    if (!key) return false;

    return this.protectedRoomProfileNames().includes(key);
  };

  proto.roomProfileDefinition = function (profileName) {
    const key = String(profileName ?? "").trim();
    if (!key) return null;
    return this.roomProfilesLibrary()?.[key] ?? null;
  };

  proto.roomProfilesList = function () {
    const library = this.roomProfilesLibrary();

    return Object.values(library).sort((left, right) => {
      const leftProtected = this.isProtectedRoomProfile(left.name);
      const rightProtected = this.isProtectedRoomProfile(right.name);

      if (leftProtected !== rightProtected) {
        return leftProtected ? -1 : 1;
      }

      return String(left.label).localeCompare(String(right.label), undefined, {
        sensitivity: "base",
      });
    });
  };

  proto.customRoomProfiles = function () {
    return this.roomProfilesList().filter((profile) => !this.isProtectedRoomProfile(profile.name));
  };

  proto.makeRoomProfileName = function (label, currentProfileName = null) {
    const trimmed = String(label ?? "").trim().toLowerCase();
    const slug = trimmed
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/_+/g, "_");

    const baseName = slug ? `custom_${slug}` : "custom_profile";
    const current = String(currentProfileName ?? "").trim();

    if (current && current === baseName) {
      return current;
    }

    const existingNames = new Set(Object.keys(this.roomProfilesLibrary() ?? {}));
    if (!existingNames.has(baseName)) {
      return baseName;
    }

    let suffix = 2;
    while (existingNames.has(`${baseName}_${suffix}`)) {
      suffix += 1;
    }

    return `${baseName}_${suffix}`;
  };
}
