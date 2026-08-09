/**
 * ============================================================
 * HARNESS FIXTURE: THE STANDALONE LOVELACE CARDS
 * ============================================================
 *
 * The gallery fixture (./gallery.js) drives the PANEL's pure renderers through a
 * stub `state` accessor. The three standalone cards cannot be driven that way:
 * they are plain custom elements that read Home Assistant directly — `hass.states`
 * for the room switches, and two response-capable service calls for the dashboard
 * snapshot / saved run profiles. So their fixture is a stub HASS, not a stub state.
 *
 * WHAT THE CARDS ACTUALLY READ (cards/_shared.js is the contract):
 *   roomSwitchesFor(hass, vacuumEntityId)
 *       every `switch.*` whose attributes carry a matching `vacuum_entity_id`
 *       AND a non-null `room_id`. Miss either and the card renders zero rooms.
 *   adapterOptions(attrs, "<field>_options")
 *       the adapter-declared `[{value,label},…]` lists, carried ON THE SWITCH.
 *       Omit them and every chip row collapses to nothing — the card renders,
 *       but as an empty box. This is the single most load-bearing part below.
 *   committedRoomFields(attrs)
 *       clean_mode / fan_speed / water_level / clean_intensity / clean_passes /
 *       edge_mopping.
 *
 * The option lists mirror the Eufy adapter's `vocabulary` block verbatim
 * (adapters/eufy/adapter.py) so a chip row here shows the chips a real install
 * shows, in the real order.
 *
 * TWO SPELLINGS OF ONE MODE, ON PURPOSE. The room editor persists the DISPLAY
 * LABEL ("Vacuum and mop") while the adapter option value, the profile catalog
 * and the framework use the TOKEN ("vacuum_mop"). Both spellings appear below —
 * Kitchen holds the label, Office holds the token — so the rendered shot passes
 * through canonicalCleanMode() rather than the trivially-equal path. A fixture
 * built only from tokens would light the chip either way and prove nothing.
 *
 * Entry shape (CARD_FIXTURES):
 *   { id, element, label, file, width, config, expand?, dark? }
 *     - element : the custom-element tag name, as the card itself registers it.
 *     - file    : output basename, stable — it names a committed screenshot.
 *     - expand  : room ids to open (dashboard only; a fresh card has every row
 *                 collapsed, so without this the settings chips never render).
 *
 * ============================================================
 */

const VACUUM_ID = "vacuum.alfred";
const MAP_ID = "6";

/* =========================================================
   ADAPTER VOCABULARY — mirrors adapters/eufy/adapter.py
   ========================================================= */

const CLEAN_MODE_OPTIONS = [
  { value: "vacuum", label: "Vacuum" },
  { value: "mop", label: "Mop" },
  { value: "vacuum_mop", label: "Vacuum & Mop" },
];

const FAN_SPEED_OPTIONS = [
  { value: "Quiet", label: "Quiet" },
  { value: "Standard", label: "Standard" },
  { value: "Turbo", label: "Turbo" },
  { value: "Max", label: "Max" },
];

const WATER_LEVEL_OPTIONS = [
  { value: "Off", label: "Off" },
  { value: "Low", label: "Low" },
  { value: "Medium", label: "Medium" },
  { value: "High", label: "High" },
];

const CLEAN_INTENSITY_OPTIONS = [
  { value: "Quick", label: "Quick" },
  { value: "Narrow", label: "Narrow" },
  { value: "Deep", label: "Deep" },
];

/* =========================================================
   ROOMS — one plausible home, one map
   ========================================================= */

/**
 * The per-room rows the backend's room entity publishes. `carpet` is derived
 * there from floor_type (`startswith("carpet")`); it is spelled out here so the
 * fixture reads the way the attribute set does, and it is what suppresses the
 * water-level + edge-mopping rows on a carpeted room.
 */
const ROOMS = [
  {
    room_id: 1, name: "Kitchen", slug: "kitchen", floor_type: "tile", order: 1,
    // The DISPLAY spelling the room editor writes — folded by canonicalCleanMode.
    clean_mode: "Vacuum and mop", fan_speed: "Max", water_level: "Medium",
    clean_intensity: "Deep", clean_passes: 2, edge_mopping: true, on: true,
  },
  {
    room_id: 2, name: "Living Room", slug: "living_room", floor_type: "carpet_medium", order: 2,
    clean_mode: "vacuum", fan_speed: "Turbo", water_level: null,
    clean_intensity: "Narrow", clean_passes: 2, edge_mopping: false, on: true,
  },
  {
    room_id: 3, name: "Hallway", slug: "hallway", floor_type: "hardwood", order: 3,
    clean_mode: "vacuum", fan_speed: "Standard", water_level: null,
    clean_intensity: "Quick", clean_passes: 1, edge_mopping: false, on: false,
  },
  {
    room_id: 4, name: "Bathroom", slug: "bathroom", floor_type: "tile", order: 4,
    clean_mode: "mop", fan_speed: "Quiet", water_level: "High",
    clean_intensity: "Narrow", clean_passes: 2, edge_mopping: true, on: false,
  },
  {
    room_id: 5, name: "Bedroom", slug: "bedroom", floor_type: "carpet_low", order: 5,
    clean_mode: "vacuum", fan_speed: "Quiet", water_level: null,
    clean_intensity: "Quick", clean_passes: 1, edge_mopping: false, on: false,
  },
  {
    room_id: 6, name: "Office", slug: "office", floor_type: "laminate", order: 6,
    // The TOKEN spelling — the same mode as Kitchen, stored the other way.
    clean_mode: "vacuum_mop", fan_speed: "Standard", water_level: "Low",
    clean_intensity: "Quick", clean_passes: 1, edge_mopping: false, on: false,
  },
];

/** One room switch, shaped as EufyVacuumRoomEntity publishes it. */
function roomSwitchState(room) {
  return {
    entity_id: `switch.alfred_${room.slug}_selected_for_cleaning`,
    state: room.on ? "on" : "off",
    attributes: {
      friendly_name: `Alfred ${room.name} Selected for Cleaning`,
      vacuum_entity_id: VACUUM_ID,
      map_id: MAP_ID,
      room_id: room.room_id,
      room_name: room.name,
      slug: room.slug,
      floor_type: room.floor_type,
      carpet: String(room.floor_type).startsWith("carpet"),
      order: room.order,
      enabled: room.on,
      profile_name: "vacuum_quick",
      clean_mode: room.clean_mode,
      fan_speed: room.fan_speed,
      water_level: room.water_level,
      clean_intensity: room.clean_intensity,
      clean_passes: room.clean_passes,
      edge_mopping: room.edge_mopping,
      // Adapter-declared option lists. Without these every chip row is empty.
      clean_mode_options: CLEAN_MODE_OPTIONS,
      fan_speed_options: FAN_SPEED_OPTIONS,
      water_level_options: WATER_LEVEL_OPTIONS,
      clean_intensity_options: CLEAN_INTENSITY_OPTIONS,
    },
  };
}

/* =========================================================
   hass.states
   ========================================================= */

export const CARD_STATES = {
  [VACUUM_ID]: {
    entity_id: VACUUM_ID,
    state: "docked",
    attributes: {
      friendly_name: "Alfred",
      battery_level: 96,
      fan_speed: "Standard",
      supported_features: 12333,
    },
  },
  // The vendor-app scene select the dashboard card's launcher offers. The card
  // drops the seeded "None" entry itself, so it is present here.
  "select.alfred_scene": {
    entity_id: "select.alfred_scene",
    state: "None",
    attributes: {
      friendly_name: "Alfred Scene",
      options: ["None", "Quick Tidy", "After Dinner", "Deep Clean Downstairs"],
    },
  },
  ...Object.fromEntries(ROOMS.map((r) => [roomSwitchState(r).entity_id, roomSwitchState(r)])),
};

/* =========================================================
   SERVICE RESPONSES — the two response-capable reads
   ========================================================= */

/**
 * get_dashboard_snapshot, trimmed to the keys the dashboard card reads. The map
 * section is deliberately absent from the shot via the card's own `show_map`
 * config toggle, not by lying about capability: this device DOES support a
 * VA-rendered map, but the map host is a separately-served bundle the harness
 * has no route for.
 */
export const DASHBOARD_SNAPSHOT = {
  vacuum_entity_id: VACUUM_ID,
  map_id: MAP_ID,
  max_clean_passes: 2,
  supports_room_profiles: true,
  supports_zone_clean: false,
  zone_max: 10,
  honors_clean_order: true,
  supports_water_control: true,
  supports_edge_mopping: true,
  supports_va_render: true,
  live_map_image_entity: null,
  live_map_rotation: 0,
  scene_select: "select.alfred_scene",
};

/** A room_group step, shaped as the profile store holds one. */
function group(rooms) {
  return { type: "room_group", rooms };
}

function stepRoom(room_id, name, clean_mode, extra = {}) {
  return {
    room_id, name, clean_mode,
    profile_name: "vacuum_quick",
    fan_speed: "Standard", water_level: "", clean_intensity: "Quick",
    clean_passes: 1, edge_mopping: false, order: room_id,
    ...extra,
  };
}

/**
 * One saved run profile, enriched exactly as `_enrich_saved_run_profile` returns
 * it: `steps` is the ordered routine; `room_ids`/`room_names` are the parallel
 * arrays the card's manifest reads its labels from.
 *
 * The routine is a sequenced one (two room groups either side of a charge stop,
 * plus a wait) because that is the case the card exists for — a flat single-group
 * profile renders one manifest row and shows nothing a profile NAME wouldn't.
 */
const WEEKEND_PROFILE = {
  id: "rp_weekend_deep",
  name: "Weekend Deep Clean",
  vacuum_entity_id: VACUUM_ID,
  map_id: MAP_ID,
  expose_as_button: true,
  room_count: 5,
  room_ids: [1, 6, 2, 5, 4],
  room_names: ["Kitchen", "Office", "Living Room", "Bedroom", "Bathroom"],
  room_names_label: "Kitchen, Office, Living Room, Bedroom, Bathroom",
  has_charge_steps: true,
  has_stops: true,
  created_at: "2026-02-14T09:00:00+00:00",
  updated_at: "2026-02-14T09:00:00+00:00",
  steps: [
    // Both rooms are the combined mode, stored in the two different spellings —
    // so the group's single mode chip only appears if the fold is applied.
    group([
      stepRoom(1, "Kitchen", "Vacuum and mop", { fan_speed: "Max", water_level: "Medium", clean_intensity: "Deep", clean_passes: 2, edge_mopping: true }),
      stepRoom(6, "Office", "vacuum_mop", { water_level: "Low" }),
    ]),
    { type: "charge_wait", target_battery_percent: 80 },
    group([
      stepRoom(2, "Living Room", "vacuum", { fan_speed: "Turbo", clean_intensity: "Narrow", clean_passes: 2 }),
      stepRoom(5, "Bedroom", "vacuum", { fan_speed: "Quiet" }),
    ]),
    { type: "wait", wait_minutes: 15 },
    group([
      stepRoom(4, "Bathroom", "mop", { fan_speed: "Quiet", water_level: "High", clean_intensity: "Narrow", clean_passes: 2, edge_mopping: true }),
    ]),
  ],
};

const NIGHTLY_PROFILE = {
  id: "rp_nightly_tidy",
  name: "Nightly Tidy",
  vacuum_entity_id: VACUUM_ID,
  map_id: MAP_ID,
  expose_as_button: false,
  room_count: 2,
  room_ids: [1, 3],
  room_names: ["Kitchen", "Hallway"],
  room_names_label: "Kitchen, Hallway",
  has_charge_steps: false,
  has_stops: false,
  created_at: "2026-02-02T21:30:00+00:00",
  updated_at: "2026-02-02T21:30:00+00:00",
  steps: [
    group([
      stepRoom(1, "Kitchen", "vacuum", { fan_speed: "Max" }),
      stepRoom(3, "Hallway", "vacuum"),
    ]),
  ],
};

const PROFILE_LIBRARY = {
  [WEEKEND_PROFILE.id]: WEEKEND_PROFILE,
  [NIGHTLY_PROFILE.id]: NIGHTLY_PROFILE,
};

/** get_saved_run_profiles — `profiles` feeds the dashboard, `library` the profile card. */
export const SAVED_RUN_PROFILES = {
  vacuum_entity_id: VACUUM_ID,
  map_id: MAP_ID,
  profile_count: 2,
  profiles: Object.values(PROFILE_LIBRARY)
    .map((p) => ({
      id: p.id,
      name: p.name,
      room_count: p.room_count,
      room_ids: p.room_ids,
      room_names: p.room_names,
      room_names_label: p.room_names_label,
      expose_as_button: p.expose_as_button,
      created_at: p.created_at,
      updated_at: p.updated_at,
      summary: p.room_names_label,
    }))
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())),
  library: PROFILE_LIBRARY,
};

/** domain.service -> the payload a returnResponse call resolves to. */
export const CARD_SERVICE_RESPONSES = {
  "eufy_vacuum.get_dashboard_snapshot": DASHBOARD_SNAPSHOT,
  "eufy_vacuum.get_saved_run_profiles": SAVED_RUN_PROFILES,
};

/* =========================================================
   THE FIXTURE ENTRIES
   ========================================================= */

export const CARD_FIXTURES = [
  {
    id: "room",
    element: "eufy-room-card",
    file: "card-room",
    label: "Room card — one room's settings chips + Start",
    // Roughly the width one column of a three-column HA dashboard gives a card.
    width: 400,
    // Kitchen: a hard-floor MOP room, so the water-level and edge-mopping rows
    // both render. A vacuum-only room hides two of the six rows.
    config: { vacuum_entity_id: VACUUM_ID, room_id: 1 },
  },
  {
    id: "dashboard",
    element: "vacuum-agent-dashboard",
    file: "card-dashboard",
    label: "Dashboard card — every room, one expanded, profile + scene launcher",
    // The card's own `.card` is max-width:480px, so this is its natural size.
    width: 480,
    // show_map off: the map body is a separately-served bundle the harness has
    // no route for, and it is a real per-card toggle in the visual editor.
    config: { vacuum_entity_id: VACUUM_ID, show_map: false },
    // A fresh card has every room row collapsed. Open the mop room so the shot
    // shows what the rows contain.
    expand: ["1"],
  },
  {
    id: "profile",
    element: "vacuum-agent-profile-card",
    file: "card-profile",
    label: "Profile card — a sequenced routine's step manifest + Run",
    width: 480,
    config: {
      vacuum_entity_id: VACUUM_ID,
      map_id: MAP_ID,
      profile_id: WEEKEND_PROFILE.id,
    },
  },
];
