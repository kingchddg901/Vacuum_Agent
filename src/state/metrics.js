// Card-local state for the Metrics view: snapshot, active tab, filters, and pending save tracking.

const METRIC_TABS = {
  LEARNING: "learning",
  ROOMS: "rooms",
  PROFILES: "profiles",
  WATER: "water",
  DOCK: "dock",
};

export function applyMetricsState(proto) {
  proto._ensureMetricsState = function () {
    if (!this._metricsState) {
      this._metricsState = {
        snapshot: null,
        filters: {
          room_slug: "",
          profile_key: "",
          status: "",
          used_for_learning: "",
        },
        activeTab: METRIC_TABS.LEARNING,
        pendingSaveKey: "",
      };
    }

    return this._metricsState;
  };

  proto.metricsSnapshot = function () {
    return this._ensureMetricsState().snapshot ?? null;
  };

  proto.setMetricsSnapshot = function (snapshot) {
    const metricsState = this._ensureMetricsState();
    metricsState.snapshot = snapshot ?? null;

    const incomingFilters = snapshot?.filters;
    if (incomingFilters && typeof incomingFilters === "object") {
      metricsState.filters = {
        room_slug: incomingFilters.room_slug == null ? "" : String(incomingFilters.room_slug),
        profile_key: incomingFilters.profile_key == null ? "" : String(incomingFilters.profile_key),
        status: incomingFilters.status == null ? "" : String(incomingFilters.status),
        used_for_learning:
          typeof incomingFilters.used_for_learning === "boolean"
            ? String(incomingFilters.used_for_learning)
            : "",
      };
    }
  };

  proto.metricsFilters = function () {
    return this._ensureMetricsState().filters;
  };

  proto.setMetricsFilter = function (key, value) {
    const filters = this.metricsFilters();
    if (!(key in filters)) return;
    filters[key] = value == null ? "" : String(value);
  };

  proto.metricsActiveTab = function () {
    return this._ensureMetricsState().activeTab ?? METRIC_TABS.LEARNING;
  };

  proto.setMetricsActiveTab = function (tab) {
    const normalized = String(tab ?? "").trim().toLowerCase();
    if (!Object.values(METRIC_TABS).includes(normalized)) return;
    this._ensureMetricsState().activeTab = normalized;
  };

  proto.metricsTabOptions = function () {
    return [
      { value: METRIC_TABS.LEARNING, label: "Learning" },
      { value: METRIC_TABS.ROOMS, label: "Rooms" },
      { value: METRIC_TABS.PROFILES, label: "Profiles" },
      { value: METRIC_TABS.WATER, label: "Water" },
      { value: METRIC_TABS.DOCK, label: "Dock" },
    ];
  };

  proto.metricsOverview = function () {
    return this.metricsSnapshot()?.overview ?? {};
  };

  proto.metricsSelection = function () {
    return this.metricsSnapshot()?.selection ?? {};
  };

  proto.metricsRooms = function () {
    return Array.isArray(this.metricsSnapshot()?.rooms) ? this.metricsSnapshot().rooms : [];
  };

  proto.metricsRoomProfiles = function () {
    return Array.isArray(this.metricsSnapshot()?.room_profiles) ? this.metricsSnapshot().room_profiles : [];
  };

  proto.metricsFoundProfiles = function () {
    return Array.isArray(this.metricsSnapshot()?.found_profiles) ? this.metricsSnapshot().found_profiles : [];
  };

  proto.metricsLearningStats = function () {
    return this.metricsSnapshot()?.room_learning_stats ?? {};
  };

  proto.metricsSources = function () {
    return this.metricsSnapshot()?.sources ?? {};
  };

  proto.beginMetricsProfileSave = function (key) {
    this._ensureMetricsState().pendingSaveKey = String(key ?? "");
  };

  proto.endMetricsProfileSave = function () {
    this._ensureMetricsState().pendingSaveKey = "";
  };

  proto.isMetricsProfileSavePending = function (key) {
    return this._ensureMetricsState().pendingSaveKey === String(key ?? "");
  };

  proto.metricsProfileSaveKey = function (sourceType, profile) {
    const source = String(sourceType ?? "profile");
    const roomSlug = String(profile?.room_slug ?? "");
    const profileKey = String(profile?.profile_key ?? "");
    return `${source}:${roomSlug}:${profileKey}`;
  };

  proto.findMetricsSaveCandidate = function (sourceType, profileKey, roomSlug = "") {
    const source = String(sourceType ?? "");
    const key = String(profileKey ?? "");
    const room = String(roomSlug ?? "");
    if (!key) return null;

    const list = source === "found"
      ? this.metricsFoundProfiles?.() ?? []
      : this.metricsRoomProfiles?.() ?? [];

    return list.find((item) =>
      String(item?.profile_key ?? "") === key &&
      String(item?.room_slug ?? "") === room
    ) ?? null;
  };

  proto.metricsFilterRoomOptions = function () {
    const options = this.metricsSnapshot()?.filter_options?.rooms;
    if (Array.isArray(options) && options.length) return options;
    return [];
  };

  proto.metricsFilterProfileOptions = function () {
    const options = this.metricsSnapshot()?.filter_options?.profiles;
    if (Array.isArray(options) && options.length) return options;
    return [];
  };

  proto.metricsFilterStatusOptions = function () {
    const options = this.metricsSnapshot()?.filter_options?.statuses;
    if (Array.isArray(options) && options.length) return options;
    return [];
  };

  proto.metricsFilterUsedOptions = function () {
    const options = this.metricsSnapshot()?.filter_options?.used_for_learning;
    if (Array.isArray(options) && options.length) return options;
    return [];
  };
}
