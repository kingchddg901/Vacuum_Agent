/**
 * ============================================================
 * HARNESS FIXTURE: ALL-STATES GALLERIES
 * ============================================================
 *
 * Each gallery is a REAL tab render whose stub `state` (+ learning
 * controller) is shaped to force every colored branch onto one
 * screen at real size — the honest instrument for colorblind
 * validation (distinguishability is relative; states must be
 * co-present and adjacent in real layout, never a swatch strip).
 *
 * Entry shape:
 *   { id, view, label, tokens[], state{}, controller?{}, bundle?{}, clip? }
 *   - tokens : the semantic-color tokens this entry visibly exercises
 *              (the completeness test asserts the registry enum is
 *              covered by the union of these).
 *   - clip   : optional selector to screenshot instead of the whole
 *              card (used by the status-dot strip).
 *
 * Shapes were reverse-engineered from the renderers and verified by
 * screenshot — see harness/README.md.
 *
 * ============================================================
 */

/* =========================================================
   HELPERS
   ========================================================= */

/** A room object with the fields the rooms renderer reads. */
function room(id, name, extra = {}) {
  return {
    id,
    mapId: "main",
    name,
    order: Number(id),
    enabled: true,
    clean_mode: "vacuum",
    ...extra,
  };
}

/** A learning controller stub: per-room progress snapshots + job percent. */
function controllerFor(snapshots = {}, jobPercent = 50) {
  return {
    getJobProgressPercent: () => jobPercent,
    getRoomProgressPercent: (id) => snapshots[String(id)]?.percent ?? 0,
    getRoomProgressSnapshot: (id) => snapshots[String(id)] ?? null,
  };
}

/* =========================================================
   ROOMS — active job, every queue + confidence state
   ========================================================= */

const ROOMS_ACTIVE = {
  id: "rooms-active",
  view: "rooms",
  label: "Rooms — active job (current / completed / remaining / idle + confidence tiers)",
  // Floor textures need HA-served mask PNGs (absent headless), so suppress
  // them here to keep the colorblind read on the semantic states.
  bundle: { "--evcc-floor-textures-card-enabled": "0" },
  tokens: [
    "--evcc-color-cleaning",
    "--evcc-status-dot-cleaning",
    "--evcc-sem-success", "--evcc-sem-warning", "--evcc-sem-error",
    "--evcc-learning-confidence-high-bg", "--evcc-learning-confidence-high-border", "--evcc-learning-confidence-high-text",
    "--evcc-learning-confidence-medium-bg", "--evcc-learning-confidence-medium-border", "--evcc-learning-confidence-medium-text",
    "--evcc-learning-confidence-low-border", "--evcc-learning-confidence-low-text",
    "--evcc-learning-confidence-neutral-border", "--evcc-learning-confidence-neutral-text",
    "--evcc-estimate-learned-bg", "--evcc-estimate-learned-border", "--evcc-estimate-learned-text",
    "--evcc-estimate-default-bg", "--evcc-estimate-default-border", "--evcc-estimate-default-text",
    "--evcc-confidence-high-bg", "--evcc-confidence-high-border", "--evcc-confidence-high-text",
    "--evcc-confidence-medium-bg", "--evcc-confidence-medium-border", "--evcc-confidence-medium-text",
    "--evcc-confidence-low-bg", "--evcc-confidence-low-border", "--evcc-confidence-low-text",
    // Learning panels (summary / pre-job / live progress / notices) and the
    // room warning note all render in this active-job fixture — verified by
    // screenshot.
    "--evcc-learning-note-text", "--evcc-learning-warning-text",
    "--evcc-learning-panel-bg", "--evcc-learning-panel-border",
    "--evcc-learning-text-muted", "--evcc-learning-text-primary", "--evcc-learning-text-secondary",
  ],
  state: {
    vacuumState: () => "cleaning",
    vacuumStateLabel: () => "Cleaning",
    hasActiveRun: () => true,
    canStartCleaning: () => false,
    startBlockedReason: () => "Job in progress",
    hasStartWarning: () => false,
    enabledRoomCount: () => 4,
    // Suppress the confirmation-flow and contradictory post/pre-job panels the
    // null-object would otherwise read truthy, so the baseline shows ONLY the
    // active-job states we mean to exhibit.
    startRequiresConfirmation: () => false,
    startConfirmation: () => null,
    startPreflight: () => null,
    cancelRunRequiresConfirmation: () => false,
    clearQueueRequiresConfirmation: () => false,
    canPauseRun: () => true,
    canResumeRun: () => false,
    hasLearningSummary: () => false,
    learningAllCompleted: () => false,
    learningBatteryWarning: () => false,
    hasIncompleteRunLog: () => false,
    activeJobRooms: () => [
      { jobOrder: 1, id: "1", name: "Kitchen" },
      { jobOrder: 2, id: "2", name: "Living Room" },
      { jobOrder: 3, id: "3", name: "Bedroom" },
    ],
    learningCompletedRooms: () => [{ room_id: "2" }],
    learningRoomTimeline: () => [
      { room_id: "1", current: true, minutes: 14, confidence_breakpoint: { ui_variant: "success" } },
      { room_id: "2", completed: true, minutes: 20, confidence_breakpoint: { ui_variant: "warning" } },
      { room_id: "3", remaining: true, minutes: 9, confidence_breakpoint: { ui_variant: "error" } },
    ],
    roomEstimateForRoom: (id) => {
      const byId = {
        "1": { source: "learned", minutes: 14, confidence_breakpoint: { ui_variant: "success" } },
        "2": { source: "learned", minutes: 20, confidence_breakpoint: { ui_variant: "warning" } },
        "3": { source: "learned", minutes: 9, confidence_breakpoint: { ui_variant: "error" } },
        "4": { source: "default", minutes: 12 },
      };
      const e = byId[String(id)];
      return e ? { ...e, error: null } : null;
    },
    troubleRoomForRoom: (id) =>
      String(id) === "4"
        ? { is_trouble: true, miss_count: 2, run_count: 8, miss_rate: 0.25 }
        : null,
    getRoomsForActiveMap: () => [
      room("1", "Kitchen", { floor_type: "tile", clean_mode: "vacuum_mop", fan_speed: "max", water_level: "high", clean_intensity: "deep", clean_passes: 2, edge_mopping: true }),
      room("2", "Living Room", { floor_type: "carpet", clean_mode: "vacuum", fan_speed: "high" }),
      room("3", "Bedroom", { floor_type: "wood", clean_mode: "vacuum_mop", water_level: "medium" }),
      room("4", "Office", { floor_type: "marble", clean_mode: "vacuum" }),
      room("5", "Bathroom", { enabled: false, floor_type: "tile" }),
    ],
  },
  controller: controllerFor(
    {
      "1": { isCurrent: true, isCompleted: false, percent: 42, elapsedMinutes: 6, remainingMinutes: 8 },
      "2": { isCurrent: false, isCompleted: true, percent: 100 },
      "3": { isCurrent: false, isCompleted: false, percent: 0 },
    },
    42,
  ),
};

/* =========================================================
   LEARNING REVIEW — every job badge variant
   ========================================================= */

const LEARNING_REVIEW = {
  id: "review-badges",
  view: "learning_review",
  label: "Learning Review — excluded / suggested / warning / neutral job badges",
  tokens: ["--evcc-sem-error", "--evcc-sem-warning"],
  state: {
    learningHistorySnapshot: () => ({
      available: true,
      message: "Review runs used for learning and exclude bad history when needed.",
      updated_at: "2026-06-05T10:00:00Z",
      summary: { filtered_job_count: 3, filtered_room_count: 2, filtered_room_profile_count: 2 },
      jobs: [
        {
          job_id: "job_2026-06-05T08-45", started_at: "2026-06-05T08:45:00Z", duration_minutes: 45.5,
          outlier_score: 0.12, status: "completed", status_label: "Completed",
          used_for_learning: true, excluded_from_learning: false, exclude_allowed: true,
          is_multi_room: true, room_slugs: ["living_room", "kitchen"],
          primary_room_label: "Living Room", profile_label: "Deep Mop", profile_key: "vacuum_mop_deep",
        },
        {
          job_id: "job_2026-06-04T18-30", started_at: "2026-06-04T18:30:00Z", duration_minutes: 38.2,
          outlier_score: 0.81, status: "cancelled", status_label: "Cancelled",
          used_for_learning: false, excluded_from_learning: false, exclude_allowed: true,
          exclude_suggested: true, exclude_suggested_reason_label: "Incomplete Run",
          sanity_passed: false, is_single_room: true, room_slugs: ["kitchen"],
          primary_room_label: "Kitchen", profile_label: "Vacuum Quick", profile_key: "vacuum_quick",
        },
        {
          job_id: "job_2026-06-03T09-10", started_at: "2026-06-03T09:10:00Z", duration_minutes: 50.0,
          outlier_score: 0.40, status: "completed", status_label: "Completed",
          used_for_learning: false, excluded_from_learning: true, restore_allowed: true,
          exclude_suggested: true, exclude_suggested_reason_label: "Manual Test",
          mid_job_recharge_observed: true, is_multi_room: true, room_slugs: ["bedroom", "office"],
          primary_room_label: "Bedroom", profile_label: "Deep Mop", profile_key: "vacuum_mop_deep",
        },
      ],
    }),
    learningHistoryFilters: () => ({ room_slug: "", profile_key: "", status: "", used_for_learning: "" }),
    learningHistoryRooms: () => [
      { room_slug: "living_room", room_name: "Living Room" },
      { room_slug: "kitchen", room_name: "Kitchen" },
    ],
    learningHistoryProfiles: () => [
      { profile_key: "vacuum_mop_deep", label: "Deep Mop" },
      { profile_key: "vacuum_quick", label: "Vacuum Quick" },
    ],
    learningHistoryStatusOptions: () => [
      { value: "completed", label: "Completed" },
      { value: "cancelled", label: "Cancelled" },
    ],
    learningHistoryUsedOptions: () => [
      { value: "true", label: "Used" },
      { value: "false", label: "Not Used" },
    ],
    learningHistorySortOptions: () => [
      { value: "newest", label: "Newest" },
      { value: "outlier", label: "Outlier" },
    ],
    learningHistorySort: () => "newest",
    learningHistoryExcludeReasonOptions: () => [
      { value: "manual_test", label: "Manual Test" },
      { value: "incomplete", label: "Incomplete Run" },
    ],
    reviewProfileMatcherFields: () => ({
      clean_mode: "vacuum_mop", fan_speed: "high", water_level: "medium",
      clean_intensity: "deep", clean_passes: 2, edge_mopping: true,
    }),
    reviewProfileMatcherMatches: () => [{ profile_key: "vacuum_mop_deep", label: "Deep Mop" }],
    showReviewProfileMatcherWaterLevel: () => true,
    showReviewProfileMatcherEdgeMopping: () => true,
    cleanModeOptions: () => [{ value: "vacuum", label: "Vacuum" }, { value: "vacuum_mop", label: "Vacuum + Mop" }],
    suctionLevelOptions: () => [{ value: "high", label: "High" }, { value: "max", label: "Max" }],
    waterLevelOptions: () => [{ value: "medium", label: "Medium" }, { value: "high", label: "High" }],
    cleanIntensityOptions: () => [{ value: "standard", label: "Standard" }, { value: "deep", label: "Deep" }],
  },
};

/* =========================================================
   MAPPING REVIEW — all six bounds badges
   =========================================================
   Badge colors are registry-backed after the Wave-4 migration
   (src/styles/mapping-review.js): ok→sem-success, likely+warn→
   sem-warning, outlier→sem-error, baseline→sem-info, excluded→
   text-muted. likely/warn intentionally share warning (text-
   distinguished). A CVD bundle overriding --evcc-sem-* recolors
   these too.
   ========================================================= */

function boundsRun(jobId, recordedAt, box, extra = {}) {
  return { job_id: jobId, recorded_at: recordedAt, excluded: false, sample_count: 45, ...box, ...extra };
}

const MAPPING_REVIEW = {
  id: "mapping-badges",
  view: "mapping_review",
  label: "Mapping Review — ok / likely / warn / outlier / excluded / baseline badges",
  tokens: [
    "--evcc-sem-success", "--evcc-sem-warning", "--evcc-sem-error", "--evcc-sem-info",
    "--evcc-text-muted",
  ],
  state: {
    mappingBoundsFilter: () => "all",
    mappingBoundsFilterOptions: () => [
      { value: "all", label: "All Rooms" },
      { value: "has_bounds", label: "Has Bounds" },
      { value: "no_bounds", label: "No Bounds" },
    ],
    mappingBoundsSnapshot: () => ({
      available: true,
      rooms: {
        // 4 active runs (+1 excluded) => room badge OK; per-run shows
        // OK / Outlier / Excluded / Baseline.
        "1": {
          name: "Living Room",
          bounds: { min_x: 1000, max_x: 5000, min_y: 2000, max_y: 6000, sample_count: 48, updated_at: "2026-06-05T10:00:00Z" },
          has_archive: false,
          job_bounds_history: [
            boundsRun("job_2026-06-05T08-45", "2026-06-05T08:45:00Z", { min_x: 1000, max_x: 5000, min_y: 2000, max_y: 6000 }),
            boundsRun("job_2026-06-04T18-30", "2026-06-04T18:30:00Z", { min_x: 1000, max_x: 8200, min_y: 2000, max_y: 6000 }), // outlier (max X +60%)
            boundsRun("job_2026-06-03T09-10", "2026-06-03T09:10:00Z", { min_x: 980, max_x: 5050, min_y: 1980, max_y: 6010 }, { excluded: true }), // excluded
            boundsRun("job_2026-06-02T11-05", "2026-06-02T11:05:00Z", { min_x: 1010, max_x: 4990, min_y: 2010, max_y: 5990 }),
            boundsRun("job_2026-06-01T07-20", "2026-06-01T07:20:00Z", { min_x: 1000, max_x: 5000, min_y: 2000, max_y: 6000 }), // oldest => baseline
          ],
        },
        // 2 active runs => room badge LIKELY.
        "2": {
          name: "Kitchen",
          bounds: { min_x: 500, max_x: 3000, min_y: 1000, max_y: 4000, sample_count: 22, updated_at: "2026-06-04T19:00:00Z" },
          has_archive: false,
          job_bounds_history: [
            boundsRun("job_2026-06-04T19-00", "2026-06-04T19:00:00Z", { min_x: 500, max_x: 3000, min_y: 1000, max_y: 4000 }),
            boundsRun("job_2026-06-02T08-30", "2026-06-02T08:30:00Z", { min_x: 510, max_x: 2990, min_y: 1010, max_y: 3990 }),
          ],
        },
        // no bounds => room badge WARN.
        "3": { name: "Bedroom", bounds: null, has_archive: true, job_bounds_history: [] },
      },
    }),
  },
};

/* =========================================================
   STATUS DOTS — real header dot, one render per state
   =========================================================
   The card shows only one or two dots at a time, so each dot is
   rendered as a real header at real size; the gallery sheet
   juxtaposes them for the side-by-side distinguishability read.
   ========================================================= */

const DOT_STATES = [
  { id: "cleaning", vs: "cleaning", vl: "Cleaning", tokens: ["--evcc-status-dot-cleaning", "--evcc-color-cleaning"] },
  { id: "returning", vs: "returning", vl: "Returning", tokens: ["--evcc-status-dot-returning"] },
  { id: "paused", vs: "paused", vl: "Paused", tokens: ["--evcc-status-dot-paused"] },
  { id: "error", vs: "error", vl: "Error", ds: "error", dl: "Error", tokens: ["--evcc-status-dot-error", "--evcc-color-error"] },
  { id: "docked", vs: "docked", vl: "Docked", ds: "idle", dl: "Idle", tokens: ["--evcc-status-dot-docked", "--evcc-color-docked"] },
  { id: "charging", vs: "docked", vl: "Docked", ds: "charging", dl: "Charging", tokens: ["--evcc-status-dot-charging"] },
  { id: "offline", vs: "unknown", vl: "Offline", ds: "offline", dl: "Offline", tokens: ["--evcc-status-dot-offline"] },
  { id: "unavailable", vs: "unavailable", vl: "Unavailable", ds: "unavailable", dl: "Unavailable", tokens: ["--evcc-status-dot-unavailable"] },
  { id: "idle", vs: "idle", vl: "Idle", tokens: ["--evcc-status-dot-idle", "--evcc-color-idle"] },
];

const STATUS_DOTS = DOT_STATES.map((d) => ({
  id: `dot-${d.id}`,
  view: "rooms",
  label: `Status dot — ${d.vl}`,
  clip: "[data-evcc-header-root]",
  tokens: d.tokens,
  state: {
    vacuumState: () => d.vs,
    vacuumStateLabel: () => d.vl,
    dockStatus: () => d.ds ?? null,
    dockStatusLabel: () => d.dl ?? null,
  },
}));

/* =========================================================
   EXTERNAL JOBS — the "app-started runs" review subtab
   =========================================================
   The Learning Review view has two subtabs; the per-tab shooter
   only captures the default (History). This forces the External
   Jobs subtab (reviewSubtab -> "external") with a pending list so
   the app-started-run review surface gets its own baseline.
   ========================================================= */

const EXTERNAL_JOBS = {
  id: "external-jobs",
  view: "learning_review",
  label: "Learning Review — External Jobs subtab (app-started runs awaiting review)",
  tokens: [],
  state: {
    reviewSubtab: () => "external",
    externalBrand: () => "Eufy",
    externalPendingRuns: () => [
      {
        pending_job_id: "ext_2026-06-06T14-20",
        detection_ts: "2026-06-06T14:20:00Z",
        suggested_room_count: 3,
        segments: [{ area_m2: 18 }, { area_m2: 24 }, { area_m2: 11 }],
      },
      {
        pending_job_id: "ext_2026-06-05T09-05",
        detection_ts: "2026-06-05T09:05:00Z",
        suggested_room_count: 1,
        segments: [{ area_m2: 32 }],
      },
    ],
  },
};

/* =========================================================
   EXTERNAL REVIEW WIZARD — the two-step modal (body-level)
   =========================================================
   The wizard mounts to a body-level modal host (main.js
   _renderModals), NOT renderView — so it is captured via the
   harness `modal` opt (renders renderExternalWizardModal into the
   modal host) and clipped to the modal shell. One shared run's
   data drives both steps: step 1 = confirm room count (v2 re-
   segment: count stepper + split/merge), step 2 = name each room
   + correct settings. An uncertain inactive cut inside rooms 1 & 2
   exercises the "Split here · uncertain" affordance.
   ========================================================= */

const WIZARD_SEGMENTS = [
  { order: 0, boundary_id: 0,  area_m2: 18, time_wall_s: 840,  pass_count: 1, settings: { clean_mode: "vacuum" } },
  { order: 1, boundary_id: 30, area_m2: 24, time_wall_s: 1200, pass_count: 2, settings: { clean_mode: "vacuum_mop", fan_speed: "high", water_level: "high", clean_intensity: "deep" } },
  { order: 2, boundary_id: 66, area_m2: 11, time_wall_s: 540,  pass_count: 1, settings: { clean_mode: "vacuum" } },
];

// Full boundary menu; activeBoundaries (30, 66) are the cuts currently in play.
// The two inactive cuts (12, 66-internal 48) are uncertain — they surface as
// "Split here · uncertain" inside the room whose span contains them.
const WIZARD_CANDIDATES = [
  { id: 12, confident: false },
  { id: 30, confident: true },
  { id: 48, confident: false },
  { id: 66, confident: true },
];

const WIZARD_ROOMS = [
  { room_id: "1", name: "Kitchen" },
  { room_id: "2", name: "Living Room" },
  { room_id: "3", name: "Bedroom" },
  { room_id: "4", name: "Office" },
];

// Step-2 room groups (v2 = one group per segment), each lead carrying a
// shortlist + captured settings so the room panels render fully populated.
const WIZARD_GROUPS = [
  { orders: [0], segments: [WIZARD_SEGMENTS[0]], lead: { order: 0, pass_count: 1, settings: WIZARD_SEGMENTS[0].settings, shortlist: [{ room_id: "1", name: "Kitchen", learned_area_m2: 17 }, { room_id: "4", name: "Office", learned_area_m2: 21 }] } },
  { orders: [1], segments: [WIZARD_SEGMENTS[1]], lead: { order: 1, pass_count: 2, settings: WIZARD_SEGMENTS[1].settings, shortlist: [{ room_id: "2", name: "Living Room", learned_area_m2: 25 }] } },
  { orders: [2], segments: [WIZARD_SEGMENTS[2]], lead: { order: 2, pass_count: 1, settings: WIZARD_SEGMENTS[2].settings, shortlist: [{ room_id: "3", name: "Bedroom", learned_area_m2: 12 }] } },
];

function wizardState(step) {
  const w = {
    pendingJobId: "ext_2026-06-06T14-20",
    mapId: "main",
    step,
    resegmentable: true,
    segments: WIZARD_SEGMENTS,
    candidates: WIZARD_CANDIDATES,
    activeBoundaries: [30, 66],
    splits: {},
    assignments: {
      0: { room_id: "1", edge_mopping: false, override: false, overrides: {} },
      1: { room_id: "2", edge_mopping: true,  override: false, overrides: { clean_mode: "vacuum_mop", water_level: "high" } },
      2: { room_id: "3", edge_mopping: false, override: false, overrides: {} },
    },
    rooms: WIZARD_ROOMS,
    suggestedRoomCount: 3,
    resegmentMeta: null,
    blocked: null,
    busy: false,
    error: null,
  };
  return {
    isExternalWizardOpen: () => true,
    externalWizard: () => w,
    externalWizardGroups: () => WIZARD_GROUPS,
    // Step-2 setting chips read their options from the adapter vocabulary,
    // same accessors the room editor uses.
    suctionLevelOptions: () => [{ value: "standard", label: "Standard" }, { value: "high", label: "High" }, { value: "max", label: "Max" }],
    cleanIntensityOptions: () => [{ value: "standard", label: "Standard" }, { value: "deep", label: "Deep" }],
    waterLevelOptions: () => [{ value: "low", label: "Low" }, { value: "medium", label: "Medium" }, { value: "high", label: "High" }],
  };
}

const EXTERNAL_WIZARD_STEP1 = {
  id: "external-wizard-step1",
  view: "learning_review",
  label: "External review wizard — step 1 (confirm room count: stepper + split / merge)",
  tokens: [],
  modal: "renderExternalWizardModal",
  clip: ".evcc-external-wizard-modal",
  state: wizardState(1),
};

const EXTERNAL_WIZARD_STEP2 = {
  id: "external-wizard-step2",
  view: "learning_review",
  label: "External review wizard — step 2 (name each room + correct settings)",
  tokens: [],
  modal: "renderExternalWizardModal",
  clip: ".evcc-external-wizard-modal",
  state: wizardState(2),
};

/* =========================================================
   POPULATED TABS — theme-showcase fixtures
   =========================================================
   The per-tab shooter renders these tabs from the stub null-object,
   which leaves them EMPTY (zeros / "No data") — so a theme preview
   shows the theme recoloring blank panels. These fixtures populate
   the data-bearing accessors with realistic content so the theme
   gallery (and the docs shots) show each tab fully rendered. They are
   deliberately date-math-free so the visual baselines stay
   deterministic (e.g. maintenance omits `reset_at`, which would drive
   a now-relative "Due in N days" line).
   ========================================================= */

const METRICS_OVERVIEW = {
  id: "metrics-overview",
  view: "metrics",
  label: "Metrics — overview (learned profiles, time windows, learning quality)",
  tokens: [],
  state: {
    metricsSnapshot: () => ({
      available: true,
      message: "Usage, learning quality, water, and dock metrics across the learning dataset.",
      updated_at: "2026-06-07T08:30:00Z",
    }),
    metricsActiveTab: () => "learning",
    metricsTabOptions: () => [
      { value: "learning", label: "Learning" },
      { value: "rooms", label: "Rooms" },
      { value: "profiles", label: "Profiles" },
      { value: "water", label: "Water" },
      { value: "dock", label: "Dock" },
      { value: "battery", label: "Battery" },
    ],
    metricsOverview: () => ({
      metrics: {
        job_count: 128,
        learning_used_count: 96,
        excluded_count: 7,
        mid_job_recharge_count: 4,
        wash_cycle_count: 41,
      },
      metric_windows: {
        today: { total_duration_minutes: 78, job_count: 2, learning_used_count: 2, total_water_used_ml: 410, mid_job_recharge_count: 0 },
        last_7_days: { total_duration_minutes: 506, job_count: 11, learning_used_count: 9, total_water_used_ml: 2870, mid_job_recharge_count: 1 },
        last_30_days: { total_duration_minutes: 2184, job_count: 47, learning_used_count: 38, total_water_used_ml: 11540, mid_job_recharge_count: 3 },
      },
    }),
    metricsFilters: () => ({ room_slug: "", profile_key: "", status: "", used_for_learning: "" }),
    metricsFilterRoomOptions: () => [
      { value: "kitchen", label: "Kitchen" },
      { value: "living_room", label: "Living Room" },
      { value: "bedroom", label: "Bedroom" },
      { value: "office", label: "Office" },
    ],
    metricsFilterProfileOptions: () => [
      { value: "vacuum_mop_deep", label: "Deep Mop", subtitle: "vacuum + mop · deep" },
      { value: "vacuum_quick", label: "Vacuum Quick", subtitle: "vacuum · standard" },
    ],
    metricsFilterStatusOptions: () => [
      { value: "completed", label: "Completed" },
      { value: "cancelled", label: "Cancelled" },
    ],
    metricsFilterUsedOptions: () => [
      { value_key: "true", label: "Used" },
      { value_key: "false", label: "Not Used" },
    ],
    // Only `.length` of each array is read → drives the mini-card counts.
    metricsLearningStats: () => ({ exact: new Array(6).fill(0), baselines: new Array(4).fill(0), accuracy: new Array(9).fill(0) }),
    metricsFoundProfiles: () => [
      { profile_key: "vacuum_mop_deep", profile_label: "Deep Mop", profile_subtitle: "Kitchen", room_slug: "kitchen", room_label: "Kitchen", trust_level: "trusted", run_count: 24, learning_run_count: 21, trust_reason_text: "21 of 24 runs within tolerance" },
      { profile_key: "vacuum_quick", profile_label: "Vacuum Quick", profile_subtitle: "Living Room", room_slug: "living_room", room_label: "Living Room", trust_level: "building_trust", run_count: 9, learning_run_count: 5, trust_reason_text: "5 of 9 runs used — needs 3 more" },
      { profile_key: "vacuum_mop_standard", profile_label: "Standard Mop", profile_subtitle: "Bedroom", room_slug: "bedroom", room_label: "Bedroom", trust_level: "trusted", run_count: 17, learning_run_count: 16, trust_reason_text: "16 of 17 runs within tolerance" },
      { profile_key: "vacuum_eco", profile_label: "Eco Vacuum", profile_subtitle: "Office", room_slug: "office", room_label: "Office", trust_level: "low_confidence", run_count: 4, learning_run_count: 2, trust_reason_text: "Only 2 usable runs so far" },
    ],
  },
};

const MAINTENANCE = {
  id: "maintenance",
  view: "maintenance",
  label: "Maintenance — consumables + station (healthy / warning / replace states)",
  tokens: [],
  state: {
    // Everything hangs off this one accessor. `reset_at` is intentionally
    // omitted so the now-relative "Due in N days" projection never fires.
    dashboardUpkeep: () => ({
      attention_summary: "2 items need attention soon",
      updated_at: "2026-06-07T07:30:00Z",
      attention_count: 2,
      highest_priority_status_label: "Replace Soon",
      station_water: 28,
      station_water_label: null,
      model_meta: { name: "Eufy X10 Pro Omni", guide_family_name: "X-Series Omni" },
      maintenance_items: [
        { kind: "maintenance", component: "rolling_brush", entity_id: "sensor.alfred_rolling_brush_life", label: "Rolling Brush", status: "good", remaining_percent: 78, remaining_hours: 234, interval_hours: 300, used_since_reset_hours: 66, guide: { display: { frequency: "every_2_weeks" } } },
        { kind: "maintenance", component: "side_brush", entity_id: "sensor.alfred_side_brush_life", label: "Side Brush", status: "warning", remaining_percent: 18, remaining_hours: 36, interval_hours: 200, used_since_reset_hours: 164, guide: { display: { frequency: "monthly" } } },
        { kind: "maintenance", component: "filter", entity_id: "sensor.alfred_filter_life", label: "Dust Filter", status: "good", remaining_percent: 64, remaining_hours: 96, interval_hours: 150, used_since_reset_hours: 54, guide: { display: { frequency: "every_3_months" } } },
        { kind: "maintenance", component: "sensors", entity_id: "sensor.alfred_sensor_cleaning", label: "Cliff & Wall Sensors", status: "replace_soon", remaining_percent: 9, remaining_hours: 8, interval_hours: 90, used_since_reset_hours: 82, guide: { display: { frequency: "weekly" } } },
      ],
      replacement_items: [
        { kind: "replacement", component: "mop_pads", entity_id: "sensor.alfred_mop_pad_life", label: "Mop Pads", status: "good", remaining_percent: 72, usage_hours: 84, max_life_hours: 300, guide: { display: { frequency: "every_2_months" } } },
        { kind: "replacement", component: "dust_bag", entity_id: "sensor.alfred_dust_bag", label: "Dust Bag", status: "replace_now", remaining_percent: 3, usage_hours: 196, max_life_hours: 200, guide: { display: { frequency: "as_needed" } } },
      ],
    }),
    maintenanceActiveTab: () => "maintenance_items",
    dashboardPlannedWaterEstimate: () => ({ available_clean_tank_ml: 1280 }),
    dashboardAttentionSummary: () => "2 items need attention soon",
    dashboardStatusSummary: () => "Maintenance snapshot up to date",
    activeMaintenanceModalItem: () => null,
  },
};

const ROOM_RULES = {
  id: "room-rules",
  view: "room_rules",
  label: "Room Rules — per-room blocker + modifier rules (entity-driven)",
  tokens: [],
  state: {
    getRoomsForActiveMap: () => [
      { id: "1", mapId: "main", name: "Kitchen", order: 1, enabled: true, clean_mode: "vacuum", rules: [{}, {}] },
      { id: "2", mapId: "main", name: "Living Room", order: 2, enabled: true, clean_mode: "vacuum", rules: [{}] },
      { id: "3", mapId: "main", name: "Bedroom", order: 3, enabled: true, clean_mode: "vacuum", rules: [] },
      { id: "4", mapId: "main", name: "Office", order: 4, enabled: true, clean_mode: "vacuum", rules: [{}, {}, {}] },
    ],
    resolvedRoomRulesRoom: () => ({ id: "1", mapId: "main", name: "Kitchen", order: 1 }),
    // null => render the rule LIST, not the editor (stub null-object reads truthy).
    roomRulesDraft: () => null,
    roomRulesDraftMode: () => null,
    roomRulesSaveError: () => null,
    roomRulesForRoom: (roomId) =>
      String(roomId) === "1"
        ? [
            { id: "rule_door_open", kind: "blocker", label: "Skip when front door is open", entity_id: "binary_sensor.front_door", enabled: true },
            { id: "rule_guest_mode", kind: "modifier", label: "Quiet clean in guest mode", entity_id: "input_boolean.guest_mode", enabled: true, fan_out_room_ids: ["2"] },
          ]
        : [],
    ruleConditionSummary: (rule) =>
      rule.entity_id === "binary_sensor.front_door"
        ? "When binary_sensor.front_door is on"
        : "When input_boolean.guest_mode is on",
    ruleEffectSummary: (rule) =>
      rule.kind === "blocker" ? "Skip this room" : "Fan speed → Quiet, Clean passes → 1",
  },
};

/* =========================================================
   EXPORT
   ========================================================= */

export const GALLERY = [
  ROOMS_ACTIVE,
  LEARNING_REVIEW,
  MAPPING_REVIEW,
  EXTERNAL_JOBS,
  EXTERNAL_WIZARD_STEP1,
  EXTERNAL_WIZARD_STEP2,
  METRICS_OVERVIEW,
  MAINTENANCE,
  ROOM_RULES,
  ...STATUS_DOTS,
];
