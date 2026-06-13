// Card-local state for the Learning Review view: history snapshot, filters, sort order,
// exclude reasons, pending action tracking, and profile matcher.

import { ENTITY } from "../constants.js";

const REVIEW_SORTS = {
  NEWEST: "newest",
  OUTLIER: "outlier",
  SUGGESTED: "suggested",
  EXCLUDED: "excluded",
};

const DEFAULT_EXCLUDE_REASON = "manual_test_run";
const DEFAULT_MATCHER_FIELDS = Object.freeze({
  clean_mode: "Vacuum",
  fan_speed: "Standard",
  water_level: null,
  clean_intensity: "Quick",
  clean_passes: 1,
  edge_mopping: false,
});

export function applyReviewState(proto) {
  proto._ensureReviewState = function () {
    if (!this._reviewState) {
      this._reviewState = {
        snapshot: null,
        filters: {
          room_slug: "",
          profile_key: "",
          status: "",
          used_for_learning: "",
          limit: 50,
        },
        sort: REVIEW_SORTS.NEWEST,
        excludeReasons: {},
        pendingJobActionId: "",
        matcherFields: { ...DEFAULT_MATCHER_FIELDS },
      };
    }

    return this._reviewState;
  };

  proto.learningHistorySnapshot = function () {
    return this._ensureReviewState().snapshot ?? null;
  };

  proto.setLearningHistorySnapshot = function (snapshot) {
    const reviewState = this._ensureReviewState();
    reviewState.snapshot = snapshot ?? null;

    const incomingFilters = snapshot?.filters;
    if (incomingFilters && typeof incomingFilters === "object") {
      reviewState.filters = {
        room_slug: incomingFilters.room_slug == null ? "" : String(incomingFilters.room_slug),
        profile_key: incomingFilters.profile_key == null ? "" : String(incomingFilters.profile_key),
        status: incomingFilters.status == null ? "" : String(incomingFilters.status),
        used_for_learning:
          typeof incomingFilters.used_for_learning === "boolean"
            ? String(incomingFilters.used_for_learning)
            : "",
        limit: Number.isFinite(Number(incomingFilters.limit)) && Number(incomingFilters.limit) > 0
          ? Number(incomingFilters.limit)
          : reviewState.filters?.limit ?? 50,
      };
    }
  };

  proto.learningHistoryFilters = function () {
    return this._ensureReviewState().filters;
  };

  proto.setLearningHistoryFilter = function (key, value) {
    const filters = this.learningHistoryFilters();
    if (!(key in filters)) return;

    if (key === "limit") {
      const numeric = Number(value);
      filters[key] = Number.isFinite(numeric) && numeric > 0 ? numeric : 50;
      return;
    }

    filters[key] = value == null ? "" : String(value);
  };

  proto.learningHistorySort = function () {
    return this._ensureReviewState().sort ?? REVIEW_SORTS.NEWEST;
  };

  proto.setLearningHistorySort = function (value) {
    const normalized = String(value ?? "").trim().toLowerCase();
    if (!Object.values(REVIEW_SORTS).includes(normalized)) return;
    this._ensureReviewState().sort = normalized;
  };

  proto.learningHistoryJobs = function () {
    const jobs = this.learningHistorySnapshot()?.jobs;
    return Array.isArray(jobs) ? jobs : [];
  };

  proto.learningHistoryRooms = function () {
    const filterOptions = this.learningHistorySnapshot?.()?.filter_options?.rooms;
    if (Array.isArray(filterOptions) && filterOptions.length) {
      return filterOptions
        .filter((option) => String(option?.value ?? "").trim() !== "")
        .map((option) => ({
          room_slug: String(option?.value ?? ""),
          room_name: String(option?.label ?? option?.value ?? ""),
        }));
    }

    const snapshot = this.learningHistorySnapshot?.();
    const rooms = Array.isArray(snapshot?.rooms) ? snapshot.rooms : [];
    const fromJobs = Array.isArray(snapshot?.jobs)
      ? snapshot.jobs.flatMap((job) =>
          Array.isArray(job?.room_slugs)
            ? job.room_slugs.map((slug) => ({
                room_slug: slug,
                room_name: this._formatReviewRoomLabel?.(slug) ?? slug,
              }))
            : []
        )
      : [];

    const merged = new Map();
    for (const room of [...rooms, ...fromJobs]) {
      const slug = String(room?.room_slug ?? room?.slug ?? "").trim();
      if (!slug) continue;
      if (!merged.has(slug)) {
        merged.set(slug, {
          room_slug: slug,
          room_name: room?.room_name ?? room?.label ?? this._formatReviewRoomLabel?.(slug) ?? slug,
        });
      }
    }

    return Array.from(merged.values()).sort((a, b) =>
      String(a.room_name ?? a.room_slug).localeCompare(String(b.room_name ?? b.room_slug))
    );
  };

  proto.learningHistoryProfiles = function () {
    const filterOptions = this.learningHistorySnapshot?.()?.filter_options?.profiles;
    if (Array.isArray(filterOptions) && filterOptions.length) {
      return this._disambiguateProfileOptions(
        filterOptions
          .filter((option) => String(option?.value ?? "").trim() !== "")
          .map((option) => ({
            profile_key: String(option?.value ?? ""),
            label: String(option?.label ?? option?.value ?? ""),
            subtitle: option?.subtitle == null ? null : String(option.subtitle),
            room_slug: option?.room_slug == null ? null : String(option.room_slug),
            room_label: option?.room_label == null ? null : String(option.room_label),
          }))
      );
    }

    const snapshot = this.learningHistorySnapshot?.();
    const foundProfiles = Array.isArray(snapshot?.found_profiles) ? snapshot.found_profiles : [];
    const roomProfiles = Array.isArray(snapshot?.room_profiles) ? snapshot.room_profiles : [];

    const merged = new Map();

    for (const profile of [...foundProfiles, ...roomProfiles]) {
      const key = String(profile?.profile_key ?? "").trim();
      if (!key) continue;

      if (!merged.has(key)) {
        merged.set(key, {
          profile_key: key,
          label:
            profile?.profile_label ??
            profile?.label ??
            profile?.selected_profile_label ??
            key,
          subtitle:
            profile?.profile_subtitle ??
            profile?.resolved_profile_label ??
            null,
        });
      }
    }

    return this._disambiguateProfileOptions(
      Array.from(merged.values()).sort((a, b) =>
        String(a.label ?? a.profile_key).localeCompare(String(b.label ?? b.profile_key))
      )
    );
  };

  proto.learningHistoryExcludeReason = function (jobId) {
    const stored = this._ensureReviewState().excludeReasons[String(jobId ?? "")];
    return stored || DEFAULT_EXCLUDE_REASON;
  };

  proto.setLearningHistoryExcludeReason = function (jobId, reason) {
    this._ensureReviewState().excludeReasons[String(jobId ?? "")] = String(reason ?? DEFAULT_EXCLUDE_REASON);
  };

  proto.beginLearningHistoryJobAction = function (jobId) {
    this._ensureReviewState().pendingJobActionId = String(jobId ?? "");
  };

  proto.endLearningHistoryJobAction = function () {
    this._ensureReviewState().pendingJobActionId = "";
  };

  proto.isLearningHistoryJobActionPending = function (jobId) {
    return this._ensureReviewState().pendingJobActionId === String(jobId ?? "");
  };

  proto.learningHistorySortOptions = function () {
    return [
      { value: REVIEW_SORTS.NEWEST, label: "Newest" },
      { value: REVIEW_SORTS.OUTLIER, label: "Highest Outlier" },
      { value: REVIEW_SORTS.SUGGESTED, label: "Suggested Exclude" },
      { value: REVIEW_SORTS.EXCLUDED, label: "Excluded Only" },
    ];
  };

  proto.learningHistoryStatusOptions = function () {
    const filterOptions = this.learningHistorySnapshot?.()?.filter_options?.statuses;
    if (Array.isArray(filterOptions) && filterOptions.length) {
      return filterOptions.map((option) => ({
        value: String(option?.value ?? ""),
        label: String(option?.label ?? option?.value ?? ""),
      }));
    }

    return [
      { value: "", label: "All Statuses" },
      { value: "completed", label: "Completed" },
      { value: "canceled", label: "Canceled" },
      { value: "failed", label: "Failed" },
      { value: "interrupted", label: "Interrupted" },
    ];
  };

  proto.learningHistoryUsedOptions = function () {
    const filterOptions = this.learningHistorySnapshot?.()?.filter_options?.used_for_learning;
    if (Array.isArray(filterOptions) && filterOptions.length) {
      return filterOptions.map((option) => ({
        value: String(option?.value_key ?? option?.value ?? ""),
        label: String(option?.label ?? option?.value_key ?? option?.value ?? ""),
      }));
    }

    return [
      { value: "", label: "All Learning Use" },
      { value: "true", label: "Used For Learning" },
      { value: "false", label: "Not Used For Learning" },
    ];
  };

  proto.learningHistoryExcludeReasonOptions = function () {
    return [
      { value: "short_test_cancel", label: "Short Test Cancel" },
      { value: "manual_test_run", label: "Manual Test Run" },
      { value: "false_completion", label: "False Completion" },
      { value: "bad_room_attribution", label: "Bad Room Attribution" },
      { value: "interrupted_run", label: "Interrupted Run" },
    ];
  };

  proto._formatReviewRoomLabel = function (slug) {
    return String(slug ?? "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  proto.reviewProfileMatcherFields = function () {
    return this._ensureReviewState().matcherFields;
  };

  proto.resetReviewProfileMatcher = function () {
    this._ensureReviewState().matcherFields = { ...DEFAULT_MATCHER_FIELDS };
  };

  proto.setReviewProfileMatcherField = function (key, value) {
    const fields = this.reviewProfileMatcherFields();
    if (!fields || !(key in fields)) return;

    let nextValue = value;

    if (key === "clean_mode") {
      nextValue = this._canonicalCleanModeDisplay?.(value) ?? value;
    }

    if (key === "clean_passes") {
      const numeric = Number(value);
      nextValue = Number.isFinite(numeric) && numeric > 0 ? numeric : 1;
    }

    if (key === "edge_mopping") {
      nextValue = value === true || String(value ?? "").trim().toLowerCase() === "true";
    }

    fields[key] = nextValue;

    if (key === "clean_mode" && !this.isMopMode?.(nextValue)) {
      fields.water_level = null;
      fields.edge_mopping = false;
    }
  };

  proto.showReviewProfileMatcherWaterLevel = function () {
    const fields = this.reviewProfileMatcherFields();
    if (!fields) return false;
    return this.isMopMode?.(fields.clean_mode) ?? false;
  };

  proto.showReviewProfileMatcherEdgeMopping = function () {
    const fields = this.reviewProfileMatcherFields();
    if (!fields) return false;
    return this.isMopMode?.(fields.clean_mode) ?? false;
  };

  proto.reviewProfileMatcherCatalog = function () {
    const sensorAttrs = this.attrsOf?.(ENTITY.profileSensor(this.vacuumEntityId())) ?? {};
    const profiles    = sensorAttrs.profiles       ?? {};
    const labels      = sensorAttrs.profile_labels ?? {};

    const foundProfiles = this.learningHistoryProfiles?.() ?? [];
    const foundProfileLabels = new Map(
      foundProfiles.map((profile) => [
        String(profile?.profile_key ?? ""),
        String(profile?.label ?? profile?.profile_key ?? ""),
      ]).filter(([key]) => key)
    );

    const catalog = new Map();

    for (const [profileKey, definition] of Object.entries(profiles)) {
      const key = String(profileKey ?? "").trim();
      if (!key) continue;

      if (!catalog.has(key)) {
        catalog.set(key, {
          profile_key: key,
          label: foundProfileLabels.get(key) || labels[key] || key,
          definition,
        });
      }
    }

    for (const profile of foundProfiles) {
      const key = String(profile?.profile_key ?? "").trim();
      if (!key || catalog.has(key)) continue;

      catalog.set(key, {
        profile_key: key,
        label: String(profile?.label ?? key),
        definition: null,
      });
    }

    return Array.from(catalog.values()).sort((a, b) =>
      String(a.label ?? a.profile_key).localeCompare(String(b.label ?? b.profile_key))
    );
  };

  proto.reviewProfileMatcherMatches = function () {
    const fields = this.reviewProfileMatcherFields();
    const catalog = this.reviewProfileMatcherCatalog();
    if (!fields || !catalog.length) return [];

    return catalog.filter((entry) => {
      if (!entry?.definition) return false;
      return this._editorFieldsMatchProfile?.(fields, entry.definition) === true;
    });
  };
}
