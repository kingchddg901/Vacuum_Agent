/**
 * ============================================================
 * HARNESS FIXTURE: README PANEL SHOTS
 * ============================================================
 *
 * The fifteen committed panel screenshots the README embeds, as one
 * declarative manifest: which view, at what width, driven by which stub
 * state, and — the part that makes the shot trustworthy — what has to be
 * ON SCREEN before the PNG is allowed to be written.
 *
 * WHY A GATE PER SHOT
 * -------------------
 * `renderTab` with the default stub state renders the EMPTY state, and an
 * empty panel screenshots perfectly: correct chrome, correct tab bar,
 * correct theme, nothing in it. `renderRoomsView` returns `.evcc-empty`
 * the moment `getRoomsForActiveMap()` is falsy; the metrics, maintenance
 * and review tabs each have their own "no data yet" branch. Every one of
 * those passes a check that the file exists and is a valid PNG.
 *
 * So each entry carries a `gate`: minimum counts for the selectors that
 * ARE the view, substrings that must appear in the rendered text, and a
 * height floor. The shooter measures the live shadow tree and refuses to
 * write anything that misses (harness/shoot-readme.mjs).
 *
 * NO REAL PEOPLE, PLACES OR NETWORKS
 * ----------------------------------
 * These are published on a public repo. Room names come from the neutral
 * vocabulary the rest of the harness already uses — Kitchen / Living Room
 * / Bedroom / Office / Bathroom / Hallway — never a household's own names
 * for its rooms; entity ids, file paths and map art are synthetic. The
 * gate asserts the expected synthetic names are present, so a fixture that
 * drifted to some other source of room names would fail rather than ship.
 *
 * DETERMINISM
 * -----------
 * Every shot renders with the clock frozen and animations zeroed, and
 * nothing here derives from wall-clock or randomness — so two consecutive
 * runs produce byte-identical PNGs.
 *
 * ============================================================
 */

import { VacuumCardState } from "../../src/state/index.js";

/* =========================================================
   SHARED VOCABULARY
   ========================================================= */

/** The only room names any shot may show. Neutral, synthetic, no household's. */
export const ROOM_NAMES = ["Kitchen", "Living Room", "Bedroom", "Office", "Bathroom", "Hallway"];

/** Header chrome. Sits in `overrides`, so it outranks a delegated real state. */
const HEADER = {
  vacuumDisplayName: () => "Alfred",
  vacuumObjectId: () => "alfred",
  vacuumState: () => "docked",
  vacuumStateLabel: () => "Docked",
  batteryLevel: () => 96,
  dockStatus: () => "charging",
  dockStatusLabel: () => "Charging",
  isMobileViewport: () => false,
  supportsBaseStation: () => true,
};

/** A room object with the fields the rooms renderer reads. */
function room(id, name, extra = {}) {
  return {
    id,
    // Both spellings on purpose: the rooms renderer reads `id`, the saved-zone
    // grouping and its re-file picker read `room_id`. With only `id`, every saved
    // zone's room select renders "Unassigned" while the zone sits under its room.
    room_id: id,
    mapId: "main",
    name,
    order: Number(id),
    enabled: true,
    clean_mode: "vacuum",
    ...extra,
  };
}

/* =========================================================
   SYNTHETIC FLOOR PLAN
   =========================================================
   The map views need a backdrop image. A real install serves one from
   Home Assistant (a camera frame or an uploaded plan) — headless there is
   no such route, and the one real-home plan in docs/screenshots is
   deliberately the ONLY one: it shows no names.

   So the backdrop is drawn here, as an inline SVG data URI: a square
   plan whose rooms are exactly the polygons below, at the same percent
   coordinates, so the overlay lands on the drawn floor instead of
   floating over an unrelated raster. Square because .evcc-map-container
   is aspect-ratio:1 and .evcc-map-image is object-fit:contain — any other
   ratio letterboxes and the polygons drift off the walls.
   ========================================================= */

/** Room polygons in percent of the map frame — shared by the plan art and the segments. */
const PLAN_ROOMS = [
  { id: 1, name: "Kitchen",     box: [8, 10, 38, 34] },
  { id: 2, name: "Living Room", box: [52, 10, 92, 50] },
  { id: 3, name: "Bedroom",     box: [8, 62, 38, 90] },
  { id: 4, name: "Office",      box: [52, 54, 92, 74] },
  { id: 5, name: "Bathroom",    box: [8, 38, 30, 58] },
  { id: 6, name: "Hallway",     box: [42, 10, 48, 90] },
];

const rect = ([x0, y0, x1, y1]) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];

/** A plain top-down plan: dark surround, pale floor per room, wall strokes. */
function floorPlanDataUri() {
  const floors = PLAN_ROOMS.map(({ box: [x0, y0, x1, y1] }) =>
    `<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" rx="0.6" ` +
    `fill="#e8eaee" stroke="#39424e" stroke-width="0.9"/>`,
  ).join("");
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="1000" height="1000">` +
    `<rect width="100" height="100" fill="#2b323b"/>` +
    floors +
    // A doorway gap drawn over each wall the hallway meets, so the plan reads
    // as one dwelling rather than six disconnected boxes.
    `<g fill="#e8eaee">` +
    `<rect x="37.6" y="18" width="1.2" height="6"/>` +
    `<rect x="41.4" y="18" width="1.2" height="6"/>` +
    `<rect x="47.4" y="24" width="5.2" height="1.2"/>` +
    `<rect x="47.4" y="60" width="5.2" height="1.2"/>` +
    `<rect x="37.6" y="70" width="1.2" height="6"/>` +
    `<rect x="41.4" y="70" width="1.2" height="6"/>` +
    `<rect x="29.4" y="45" width="1.2" height="6"/>` +
    `</g></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const PLAN_SEGMENTS = PLAN_ROOMS.map((r) => ({
  segment_id: r.id,
  name: r.name,
  polygon_pct: rect(r.box),
}));

const PLAN_ROOM_OBJECTS = [
  room("1", "Kitchen", { floor_type: "tile", clean_mode: "vacuum_mop", fan_speed: "max", water_level: "high" }),
  room("2", "Living Room", { floor_type: "carpet_low_pile", clean_mode: "vacuum", fan_speed: "high" }),
  room("3", "Bedroom", { floor_type: "hardwood", clean_mode: "vacuum_mop", water_level: "medium" }),
  room("4", "Office", { floor_type: "laminate", clean_mode: "vacuum" }),
  room("5", "Bathroom", { floor_type: "marble", clean_mode: "vacuum_mop", water_level: "high" }),
  room("6", "Hallway", { floor_type: "hardwood", clean_mode: "vacuum" }),
];

/** What renderMapRoomView + the rooms toolbar read to draw the plan above. */
const MAP_BASE = {
  mapImageUrl: () => floorPlanDataUri(),
  mapSegments: () => PLAN_SEGMENTS,
  mapSegmentsData: () => ({ available: true }),
  roomIdForSegment: (segmentId) => String(segmentId),
  segmentationMode: () => "cv",
  mapZoom: () => 1,
  mapTranslateX: () => 0,
  mapTranslateY: () => 0,
  effectiveMapRotation: () => 0,
  isFurnishedLayoutActive: () => false,
  liveMapImageEntity: () => null,
  // Floor textures are HA-served mask PNGs with no route headless; left on, every
  // room polygon paints from an empty <pattern> and reads as an unfilled outline.
  // The one texture shot in docs/screenshots is a real install and stays that way.
  mapFloorTextureEnabled: () => false,
  roomFloorTextureEnabled: () => false,
  mapRoomLabelsEnabled: () => true,
  roomNameAnchor: () => null,
  stallCaptureEnabled: () => false,
  overlaysAligned: () => false,
  isMapStale: () => false,
  canDrawZone: () => false,
  zoneDrawMode: () => false,
  hideDrawMode: () => false,
  canDrawHideArea: () => false,
  hiddenRegions: () => [],
  // Truthy by default under the null-object, which paints a full-width "Map
  // switched — zone drawing pauses until the robot re-localizes" banner across
  // the middle of the map. Nothing in this fixture switched maps.
  zoneDrawSuppressedBySwitch: () => false,
  useVaRender: () => false,
  supportsVaRender: () => false,
  isVaRenderActive: () => false,
  embeddedInCard: () => false,
  mapSwitcher: () => ({ available: false, options: [] }),
  // The mascot's sprites come from the HA-served animal pack; headless the harness
  // stubs it with empty SVGs, so an enabled mascot renders as a blank box.
  mapAnimalEnabled: () => false,
};

/* =========================================================
   ROOMS — the two README shots of the Rooms tab
   ========================================================= */

/**
 * Shared idle-rooms suppression. The null-object reads truthy for every
 * accessor it has not been given, so without these the confirmation flow, the
 * live-queue banner, the charge/wait banners and the zone picker all paint over
 * an idle tab at once — the "plausible but wrong" render the gate cannot see.
 */
const IDLE_ROOMS = {
  hasActiveRun: () => false,
  activeJobRooms: () => null,
  canStartCleaning: () => true,
  startBlockedReason: () => null,
  hasStartWarning: () => false,
  startMopCarpetWarning: () => null,
  startOrderAdvisory: () => null,
  startRequiresConfirmation: () => false,
  startConfirmation: () => null,
  startPreflight: () => null,
  cancelRunRequiresConfirmation: () => false,
  clearQueueRequiresConfirmation: () => false,
  shouldShowLiveQueue: () => false,
  liveChargeStatus: () => null,
  liveWaitStatus: () => null,
  liveZoneStatus: () => null,
  queueZonePickerOpen: () => false,
  dashboardLearningProcessing: () => null,
  hasLearningSummary: () => false,
  learningAllCompleted: () => false,
  learningBatteryWarning: () => false,
  hasIncompleteRunLog: () => false,
  orphanedRooms: () => [],
  isRunProfileEditorOpen: () => false,
  // Saved zones — populated, because the null-object's truthy defaults render the
  // panel with a "selected" badge over an empty list, which reads as a bug.
  savedZonesCollapsed: () => false,
  selectedSavedZoneCount: () => 0,
  isSavedZoneSelected: () => false,
  zoneCount: () => 0,
  zoneMax: () => 10,
  zoneDrawPurpose: () => null,
  settingEntities: () => ({}),
  vacuumEntityId: () => "vacuum.alfred",
  entity: () => null,
  savedZonesGrouped: () => [
    { room_id: "1", name: "Kitchen", zones: [{ id: "z1", name: "Under the table", area_m2: 2.4, room_number: "1" }] },
    {
      room_id: "2", name: "Living Room",
      zones: [
        { id: "z2", name: "By the sofa", area_m2: 3.1, room_number: "2" },
        { id: "z3", name: "Front door mat", area_m2: 1.2, room_number: "2" },
      ],
    },
  ],
};

/** Per-room learned estimate + confidence, so the cards show what the tab is FOR. */
const ROOM_ESTIMATES = {
  "1": { source: "learned", minutes: 14.2, confidence_breakpoint: { ui_variant: "success" } },
  "2": { source: "learned", minutes: 22.5, confidence_breakpoint: { ui_variant: "success" } },
  "3": { source: "learned", minutes: 11.8, confidence_breakpoint: { ui_variant: "warning" } },
  "4": { source: "learned", minutes: 9.4, confidence_breakpoint: { ui_variant: "success" } },
  "5": { source: "default", minutes: 7.0 },
  "6": { source: "learned", minutes: 5.6, confidence_breakpoint: { ui_variant: "warning" } },
};

const ROOMS_LIST_STATE = {
  ...HEADER,
  ...IDLE_ROOMS,
  ...MAP_BASE,
  getRoomsForActiveMap: () => PLAN_ROOM_OBJECTS,
  isMapViewActive: () => false,
  enabledRoomCount: () => 6,
  dashboardPlannedJobEstimate: () => ({
    total_minutes: 70.5,
    room_count: 6,
    confidence_breakpoint: { ui_variant: "success" },
  }),
  learningEstimate: () => null,
  roomEstimateForRoom: (id) => {
    const e = ROOM_ESTIMATES[String(id)];
    return e ? { ...e, error: null } : null;
  },
  troubleRoomForRoom: (id) =>
    String(id) === "6" ? { is_trouble: true, miss_count: 2, run_count: 9, miss_rate: 0.22 } : null,
  // Only the three MOP rooms project water. Left to the null-object every card
  // grows an "~0 ml water" chip — including the vacuum-only rooms, where the card
  // is asserting a water figure for a job that will not use any.
  dashboardPlannedWaterRoomForRoom: (id) =>
    ({
      1: { mop_active: true, effective_clean_mode: "vacuum_mop", effective_water_level: "high", estimated_robot_water_used_ml: 96 },
      3: { mop_active: true, effective_clean_mode: "vacuum_mop", effective_water_level: "medium", estimated_robot_water_used_ml: 58 },
      5: { mop_active: true, effective_clean_mode: "vacuum_mop", effective_water_level: "high", estimated_robot_water_used_ml: 34 },
    })[String(id)] ?? null,
  savedRunProfiles: () => [
    { key: "weeknight", name: "Weeknight Tidy", room_count: 3 },
    { key: "weekend", name: "Weekend Deep Clean", room_count: 6 },
  ],
  selectedRunProfile: () => null,
};

/** The map view is the same tab with the toggle flipped — same rooms, same job state. */
const ROOMS_MAP_STATE = {
  ...ROOMS_LIST_STATE,
  isMapViewActive: () => true,
  // A Set, not an array — the polygon renderer calls `.has()` on it (state/map.js
  // backs this with _getSegmentIds()).
  selectedSegmentIds: () => new Set(["2", "4"]),
  selectedSegments: () => [PLAN_SEGMENTS[1], PLAN_SEGMENTS[3]],
};

/* =========================================================
   BASE STATION
   ========================================================= */

const BASE_STATION_STATE = {
  ...HEADER,
  isDocked: () => true,
  dockLifecycleStateLabel: () => "Ready",
  dockTaskStatusLabel: () => "Completed",
  stationWaterLabel: () => null,
  pauseTimeoutMinutesDefault: () => 30,
  isDockActionPending: () => false,
  dockActionStatus: () => null,
  dashboardUpkeep: () => ({
    attention_summary: "2 items need attention soon",
    updated_at: "2026-06-07T07:30:00Z",
    station_water: 62,
    dock_events: {
      last_mop_wash: "2026-06-07T06:12:00Z",
      mop_wash_count: 57,
      last_dust_empty: "2026-06-06T21:40:00Z",
      dust_empty_count: 12,
      last_dry_start: "2026-06-07T06:20:00Z",
      dry_start_count: 76,
      last_dry_duration: 240,
    },
  }),
  dashboardPlannedWaterEstimate: () => ({
    available_clean_tank_ml: 2400,
    estimated_clean_tank_remaining_ml: 1690,
    estimated_clean_tank_remaining_percent: 70,
    estimated_total_dock_clean_water_used_ml: 710,
  }),
  // Each action's own gate: two ready, one blocked by a live precondition, one
  // blocked because the dock is not drying. A card where every tile says the
  // same thing hides the whole point of the gating.
  dockActionGate: (action) =>
    ({
      wash_mop: { supported: true, allowed: true, reason: "ready", reason_label: "Ready", message: "Ready." },
      dry_mop: { supported: true, allowed: true, reason: "ready", reason_label: "Ready", message: "Ready." },
      stop_dry_mop: {
        supported: true, allowed: false, reason: "not_drying",
        reason_label: "Unavailable", message: "Stop dry is only useful while the dock is actively drying.",
      },
      empty_dust: {
        supported: true, allowed: false, reason: "job_active",
        reason_label: "Unavailable", message: "Finish the current job first.",
      },
    })[action] ?? { supported: true, allowed: true, reason: "ready" },
};

/* =========================================================
   METRICS — Battery sub-tab
   ========================================================= */

const battery = (state, attrs = {}) => ({ state, attrs });

const METRICS_BATTERY_STATE = {
  ...HEADER,
  metricsSnapshot: () => ({
    available: true,
    message: "Usage, learning quality, water, and dock metrics across the learning dataset.",
    updated_at: "2026-06-07T08:30:00Z",
  }),
  metricsActiveTab: () => "battery",
  metricsTabOptions: () => [
    { value: "learning", label: "Learning" },
    { value: "rooms", label: "Rooms" },
    { value: "profiles", label: "Profiles" },
    { value: "water", label: "Water" },
    { value: "dock", label: "Dock" },
    { value: "battery", label: "Battery" },
  ],
  metricsOverview: () => ({
    metrics: { job_count: 128, learning_used_count: 96, excluded_count: 7 },
    metric_windows: {},
  }),
  metricsFilters: () => ({ room_slug: "", profile_key: "", status: "", used_for_learning: "" }),
  metricsFilterRoomOptions: () => [
    { value: "kitchen", label: "Kitchen" },
    { value: "living_room", label: "Living Room" },
  ],
  metricsFilterProfileOptions: () => [{ value: "vacuum_mop_deep", label: "Deep Mop" }],
  metricsFilterStatusOptions: () => [{ value: "completed", label: "Completed" }],
  metricsFilterUsedOptions: () => [{ value_key: "true", label: "Used" }],
  batteryMetrics: () => ({
    cycles: battery(128.5),
    health: battery(97, { baseline_session_count: 12 }),
    rate_overall: battery(1.24, { charging: true }),
    rate_low: battery(1.41),
    rate_high: battery(0.62),
    rate_mid_job: battery(1.08, { sample_count: 4 }),
    last_charge_duration: battery(74, { last_charge_delta_pct: 62 }),
    last_job_per_min: battery(0.41),
    last_job_per_hour: battery(24.6),
    last_job_per_m2: battery(0.372, {
      area_m2: 62.4,
      battery_used_pct: 23,
      recorded_at: "2026-06-06T19:42:00Z",
      job_id: "job_2026-06-06T18-55",
      duration_min: 56.5,
      single_clean_mode: "vacuum_mop",
      single_fan_speed: "max",
      single_water_level: "high",
      weighted_by: "area",
      // Exact attribute names the renderer reads. Guessed differently, every
      // bucket group falls through to "no single-bucket jobs yet" — three empty
      // rows in a table that otherwise looks fully populated.
      all_jobs_mean: 0.318,
      all_jobs_count: 44,
      by_clean_mode_mean: {
        "vacuum and mop": { mean: 0.372, count: 18 },
        vacuum: { mean: 0.244, count: 26 },
      },
      by_fan_speed_mean: { max: { mean: 0.401, count: 21 }, high: { mean: 0.288, count: 23 } },
      by_water_level_mean: { high: { mean: 0.386, count: 17 }, medium: { mean: 0.310, count: 12 } },
      post_job_charge: {
        duration_min: 74.0, start_battery: 38, end_battery: 100,
        avg_rate_per_min: 0.84, ended_reason: "full",
      },
    }),
  }),
};

/* =========================================================
   SETUP
   ========================================================= */

const SETUP_MAP_ROOMS = PLAN_ROOMS.map((r) => ({ room_id: String(r.id), name: r.name }));

const SETUP_STATE = {
  ...HEADER,
  setupLoading: () => false,
  setupError: () => null,
  setupLastResult: () => null,
  setupReconcileLoading: () => false,
  setupReconcileResolvedToken: () => null,
  setupReconcileResult: () => null,
  setupReconcileStaleNote: () => false,
  setupReconcileRefreshFailed: () => false,
  setupDeletePendingMapId: () => null,
  setupDeleteStage: () => null,
  setupDeleteTypedToken: () => "",
  setupDeleteDeleting: () => false,
  setupRoomEditorSaving: () => false,
  setupRoomEditorLoadingMapId: () => null,
  setupRoomEditorOpenMapId: () => "1",
  setupRoomEditorRooms: () => SETUP_MAP_ROOMS,
  setupRoomEditorEnabledIds: () => ["1", "2", "3", "4", "5", "6"],
  setupRoomEditorFloorTypesMap: () => ({
    1: "tile", 2: "carpet_low_pile", 3: "hardwood", 4: "laminate", 5: "marble", 6: "hardwood",
  }),
  isSetupMapConfigured: (mapId) => String(mapId) === "1",
  setupStatus: () => ({
    setup_complete: true,
    vacuums: [
      {
        vacuum_entity_id: "vacuum.alfred",
        panel_title: "Alfred",
        setup_steps: [
          { id: "add_vacuum", label: "Add Vacuum", completed: true },
          { id: "import_active_map", label: "Import Maps", completed: true },
          { id: "save_rooms", label: "Configure Rooms", completed: true },
        ],
        room_drift: { in_sync: true, new_rooms: [], removed_rooms: [], transiently_missing: [] },
        reconciliation: null,
        maps: [
          { map_id: "1", display_name: "Ground Floor", imported: true, protection: { requires_typed_confirmation: false } },
          { map_id: "2", display_name: "Upstairs", imported: true, protection: { requires_typed_confirmation: false } },
        ],
      },
    ],
  }),
};

/* =========================================================
   THEME — one view, three sub-states
   =========================================================
   Backed by a REAL VacuumCardState (see makeStubState's `real` layer):
   `_ensureThemeState()` and `resolvedTheme()` are an implementation, not
   data, and a hand-written stand-in for either would be a transcript that
   drifts. The library is loaded from gallery/themes Node-side and handed
   in as `data.themes`, so the presets grid shows the themes that ship.
   ========================================================= */

/** The group the Tokens shot filters to — 18 tokens, colors and scalars both. */
const TOKEN_GROUP = "Cards & Surfaces";

function themeState(subTab) {
  return (data = {}) => {
    const themes = Array.isArray(data.themes) ? data.themes : [];
    const state = new VacuumCardState({}, {});
    const library = {};
    for (const t of themes) library[t.id] = t;
    state.setThemeLibrary({
      library,
      themes: themes.map((t) => ({ id: t.id, name: t.name })),
      default_theme_id: themes[0]?.id ?? null,
    });
    state.applyThemeActivation(data.activeThemeId ?? themes[0]?.id ?? null, { clearDraft: true });
    state.setThemeSubTab(subTab);
    // Token groups default OPEN, so an unfiltered editor renders every one of the
    // ~400 tokens at once. Pick the group filter the way a user does — one chip —
    // so the shot shows the editor being used rather than the whole registry.
    if (subTab === "tokens") state.setThemeGroupFilter(TOKEN_GROUP);
    return { ...HEADER, __real: state };
  };
}

/* =========================================================
   THE MANIFEST
   ========================================================= */

/**
 * `file` is the committed basename in docs/screenshots — reused EXACTLY, so
 * the README keeps working without being edited.
 *
 * `gate.selectors` are per-shot minimum counts off the live shadow tree;
 * `gate.text` are substrings that must appear in the rendered text;
 * `gate.minHeight` is the rendered height floor in CSS px.
 */
export const README_SHOTS = [
  {
    id: "rooms-cards",
    file: "rooms-cards",
    view: "rooms",
    label: "Rooms — per-room cards with profile, learned ETA and floor type",
    state: ROOMS_LIST_STATE,
    gate: {
      selectors: { ".evcc-room-card": 6, ".evcc-rooms-view-toggle-btn": 4, ".evcc-nav-tab": 8 },
      text: ROOM_NAMES,
      minHeight: 500,
    },
  },
  {
    id: "rooms-map",
    file: "rooms-map",
    view: "rooms",
    label: "Rooms — interactive map view, rooms selectable on the floor plan",
    state: ROOMS_MAP_STATE,
    gate: {
      selectors: {
        ".evcc-map-container": 1,
        ".evcc-map-polygon": 6,
        ".evcc-map-label": 6,
        ".evcc-rooms-view-toggle-btn": 6,
      },
      text: ROOM_NAMES,
      minHeight: 500,
    },
  },
  {
    id: "maintenance",
    file: "maintenance",
    view: "maintenance",
    gallery: "maintenance",
    label: "Maintenance — consumables and station, across every wear state",
    gate: {
      selectors: { ".evcc-maintenance-card": 5, ".evcc-maintenance-item": 4, ".evcc-maintenance-stat": 8 },
      text: ["Rolling Brush", "Side Brush", "Dust Filter", "Cliff & Wall Sensors", "Dust Bag"],
      minHeight: 500,
    },
  },
  {
    id: "base-station",
    file: "base-station",
    view: "base_station",
    label: "Base Station — dock state, water projection and gated dock actions",
    state: BASE_STATION_STATE,
    gate: {
      selectors: {
        // 4, not 5: the pause-timeout panel left this tab. It is a job-lifecycle
        // setting and this tab is capability-gated on supports_base_station, so a
        // vacuum without a settable dock could not reach it — it renders in the
        // rooms sidebar now. This count dropping is the gate noticing that move,
        // which is what it is for; do not raise it back without checking the panel
        // really returned.
        ".evcc-base-station-panel": 4,
        ".evcc-base-station-stat": 8,
        ".evcc-base-station-activity-card": 3,
        ".evcc-base-station-action-card": 4,
      },
      text: ["Ready", "Completed", "Wash Mop", "Dry Mop", "Empty Dust", "ml"],
      minHeight: 500,
    },
  },
  {
    id: "metrics",
    file: "metrics",
    view: "metrics",
    gallery: "metrics-overview",
    label: "Metrics — learning overview, time windows and learned profiles",
    gate: {
      selectors: { ".evcc-metrics-panel": 2, ".evcc-metrics-tab": 6 },
      text: ["Deep Mop", "Vacuum Quick", "Kitchen", "Living Room"],
      minHeight: 500,
    },
  },
  {
    id: "metrics-battery",
    file: "metrics-battery",
    view: "metrics",
    label: "Metrics — Battery sub-tab: cycles, charge zones and per-job drain",
    state: METRICS_BATTERY_STATE,
    gate: {
      selectors: { ".evcc-metrics-table": 3, ".evcc-metrics-tab": 6, ".evcc-metrics-codeblock": 1 },
      text: ["%/min", "%/m", "sessions.csv", "samples.jsonl", "0.372", "Vacuum and mop"],
      notText: ["no single-bucket jobs yet", "Awaiting first job"],
      minHeight: 500,
    },
  },
  {
    id: "learning-review",
    file: "learning-review",
    view: "learning_review",
    gallery: "review-badges",
    label: "Learning Review — recorded runs with exclusion and outlier badges",
    // Overlay, not a gallery edit: the gallery entry is a committed visual
    // baseline. Unset, this accessor reads truthy off the null-object and every
    // Exclude / Restore button renders disabled and labelled "Working..." — a
    // screenshot claiming three actions are mid-flight.
    overlay: { isLearningHistoryJobActionPending: () => false },
    gate: {
      selectors: { ".evcc-review-job-card": 3 },
      text: ["Completed", "Cancelled", "Deep Mop", "Exclude", "Restore"],
      notText: ["Working..."],
      minHeight: 500,
    },
  },
  {
    id: "external-jobs",
    file: "external-jobs",
    view: "learning_review",
    gallery: "external-jobs",
    label: "External Jobs — app-started runs awaiting review",
    gate: {
      selectors: { ".evcc-external-card": 2, ".evcc-review-subtab": 2 },
      text: ["External Jobs", "segments"],
      minHeight: 300,
    },
  },
  {
    id: "external-wizard-step1",
    file: "external-wizard-step1",
    view: "learning_review",
    gallery: "external-wizard-step1",
    label: "External review wizard — step 1, confirm the room count",
    // Clipped to the modal, so the gate counts what is INSIDE it: the modal
    // element itself is the scope and can never match a selector run against it.
    gate: {
      selectors: { ".evcc-ext-seg": 3, ".evcc-ext-stepper": 1, ".evcc-ext-split-here": 2 },
      text: ["Step 1 of 2", "Merge up"],
      minHeight: 300,
    },
  },
  {
    id: "external-wizard-step2",
    file: "external-wizard-step2",
    view: "learning_review",
    gallery: "external-wizard-step2",
    label: "External review wizard — step 2, name each room and correct settings",
    gate: {
      selectors: { ".evcc-ext-room": 3, ".evcc-chip-row": 15 },
      text: ["Step 2 of 2", "Kitchen", "Living Room", "Bedroom"],
      minHeight: 400,
    },
  },
  {
    id: "room-rules",
    file: "room-rules",
    view: "room_rules",
    gallery: "room-rules",
    label: "Room Rules — per-room blocker and modifier rules driven by HA entities",
    gate: {
      selectors: { ".evcc-rule-card": 2, ".evcc-rule-kind-badge": 2, ".evcc-room-rules-subtab": 4 },
      text: ["Kitchen", "Living Room", "binary_sensor.front_door", "input_boolean.guest_mode"],
      minHeight: 400,
    },
  },
  {
    // The three Themes shots are ONE view in three sub-states. Height-bounded on
    // purpose: each sub-tab owns a scroll container, and an auto-height host lets
    // it grow to its content instead of scrolling — the Tokens editor would then
    // render the entire token registry in one image.
    id: "themes-presets",
    file: "themes-presets",
    view: "theme",
    height: 820,
    label: "Themes — the preset grid with search and facet filters",
    state: themeState("presets"),
    gate: {
      selectors: { ".evcc-theme-tabs .evcc-chip": 3, ".evcc-preset-card": 8, ".evcc-preset-search": 1 },
      text: ["Core Slate"],
      minHeight: 700,
    },
  },
  {
    id: "themes-palette",
    file: "themes-palette",
    view: "theme",
    height: 940,
    label: "Themes — the high-level palette editor",
    state: themeState("palette"),
    gate: {
      selectors: { ".evcc-theme-tabs .evcc-chip": 3, ".evcc-token-row": 4, ".hidden-color-input": 3 },
      text: ["Accent", "Text Primary", "Surface Base", "Radius Card"],
      minHeight: 700,
    },
  },
  {
    id: "themes-tokens",
    file: "themes-tokens",
    view: "theme",
    height: 1020,
    label: "Themes — full token-level control with live previews",
    state: themeState("tokens"),
    gate: {
      selectors: { ".evcc-theme-tabs .evcc-chip": 3, ".evcc-token-group": 1, ".evcc-token-row": 10 },
      text: [TOKEN_GROUP],
      minHeight: 700,
    },
  },
  {
    id: "setup",
    file: "setup",
    view: "setup",
    label: "Setup — register the vacuum, import maps, configure each room",
    state: SETUP_STATE,
    gate: {
      selectors: { ".evcc-setup-step": 3, ".evcc-setup-room-row": 6, ".evcc-setup-mapconfig-row": 2 },
      text: ["vacuum.alfred", "Ground Floor", "Upstairs", ...ROOM_NAMES],
      minHeight: 500,
    },
  },
];
