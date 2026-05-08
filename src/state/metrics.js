// Card-local state for the Metrics view: snapshot, active tab, filters, and pending save tracking.

const METRIC_TABS = {
  LEARNING: "learning",
  ROOMS: "rooms",
  PROFILES: "profiles",
  WATER: "water",
  DOCK: "dock",
  BATTERY: "battery",
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
      { value: METRIC_TABS.BATTERY, label: "Battery" },
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

  /* =========================================================
     BATTERY SUB-TAB
     =========================================================
     Reads from the live HA sensors registered by the integration's
     BatteryHealthManager. Each sensor exposes its core value as state,
     plus richer breakdown data as attributes (last-job per-mode means,
     post-job recharge link, etc.). All helpers return null when a sensor
     hasn't reported yet so the renderer can show "—".
  */

  proto._batterySensor = function (suffix) {
    const objectId = this.vacuumObjectId();
    if (!objectId) return null;
    const entityId = `sensor.${objectId}_${suffix}`;
    const stateValue = this.stateOf(entityId);
    if (stateValue == null) return null;
    return {
      entity_id: entityId,
      state: stateValue,
      attrs: this.attrsOf(entityId) ?? {},
    };
  };

  proto.batteryMetrics = function () {
    // Note on the per_min entity ID:
    // The Python sensor is registered with label "Last Job Drain Rate", so HA
    // slugifies its entity_id to `sensor.<vac>_last_job_drain_rate` — NOT
    // `_last_job_drain_per_min`. The other two metrics (per_hour, per_m²)
    // happen to align with their suffixes by coincidence. Looking up the
    // wrong ID returns null and the row renders as "—".
    return {
      cycles:               this._batterySensor("charge_cycles"),
      health:               this._batterySensor("battery_health"),
      rate_overall:         this._batterySensor("charge_rate"),
      rate_low:             this._batterySensor("charge_rate_low_zone"),
      rate_high:            this._batterySensor("charge_rate_high_zone"),
      rate_mid_job:         this._batterySensor("mid_job_recharge_rate"),
      last_charge_duration: this._batterySensor("last_charge_duration"),
      last_job_per_min:     this._batterySensor("last_job_drain_rate")
                              || this._batterySensor("last_job_drain_per_min"),
      last_job_per_hour:    this._batterySensor("last_job_drain_per_hour"),
      last_job_per_m2:      this._batterySensor("last_job_drain_per_m2")
                              || this._batterySensor("last_job_drain_per_m_"),
    };
  };
}
