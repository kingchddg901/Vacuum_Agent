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
    "--evcc-learning-confidence-low-bg", "--evcc-learning-confidence-low-border", "--evcc-learning-confidence-low-text",
    "--evcc-learning-confidence-neutral-bg", "--evcc-learning-confidence-neutral-border", "--evcc-learning-confidence-neutral-text",
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
  { id: "returning", vs: "returning", vl: "Returning", tokens: ["--evcc-status-dot-returning", "--evcc-color-returning"] },
  { id: "paused", vs: "paused", vl: "Paused", tokens: ["--evcc-status-dot-paused", "--evcc-color-paused"] },
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
   EXPORT
   ========================================================= */

export const GALLERY = [
  ROOMS_ACTIVE,
  LEARNING_REVIEW,
  MAPPING_REVIEW,
  ...STATUS_DOTS,
];
