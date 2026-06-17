/**
 * ============================================================
 * CONSTANTS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Single source of truth for all fixed values used across the card:
 * - integration domain
 * - service names
 * - card identity
 * - entity ID patterns
 *
 *
 * WHAT THIS FILE SHOULD NOT CONTAIN
 * ----------------------------------
 * - runtime state
 * - computed values
 * - DOM references
 * - CSS
 *
 *
 * HOW THIS FILE FITS INTO THE SYSTEM
 * -----------------------------------
 * Imported by any file that needs a service name, entity pattern,
 * or card identity string. Nothing hardcodes these values inline.
 *
 * Theme editor note:
 * The integration is the source of truth for theme state. The card
 * must only reference service names that the backend actually exposes.
 * This file therefore defines the real theme service contract used by
 * the integration's theme_services.py rather than the earlier
 * card-invented service names.
 *
 * ============================================================
 */

/* =========================================================
   CARD IDENTITY
   ========================================================= */

export const CARD_NAME    = "eufy-vacuum-command-center";
export const CARD_VERSION = "1.0.6";

/* =========================================================
   INTEGRATION DOMAIN
   ========================================================= */

export const DOMAIN = "eufy_vacuum";

/* =========================================================
   SERVICE NAMES
   =========================================================
   All service calls go through hass.callService(DOMAIN, SERVICE_*, data).
   Names must exactly match what the integration registers.
   ========================================================= */

// --- Room / map management ---
export const SERVICE_DISCOVER_ROOMS         = "discover_rooms";
export const SERVICE_SAVE_MANAGED_ROOMS     = "save_managed_rooms";
export const SERVICE_GET_VACUUM_MAPS        = "get_vacuum_maps";

// --- Queue ---
export const SERVICE_BUILD_QUEUE            = "build_queue";
export const SERVICE_BUILD_ROOM_PAYLOAD     = "build_room_payload";
export const SERVICE_GET_QUEUE_STATE        = "get_queue_state";
export const SERVICE_GET_PAYLOAD_STATE      = "get_payload_state";
export const SERVICE_CLEAR_QUEUE            = "clear_queue";
export const SERVICE_GET_ACTIVE_JOB         = "get_active_job";
export const SERVICE_CLEAR_ACTIVE_JOB       = "clear_active_job";
export const SERVICE_GET_LIFECYCLE_STATE    = "get_lifecycle_state";
export const SERVICE_GET_START_STATUS       = "get_start_status";
export const SERVICE_START_SELECTED_ROOMS   = "start_selected_rooms";
export const SERVICE_START_ZONE_CLEAN       = "start_zone_clean";
export const SERVICE_GET_DASHBOARD_SNAPSHOT = "get_dashboard_snapshot";
export const SERVICE_GET_PAUSE_TIMEOUT_SETTINGS = "get_pause_timeout_settings";
export const SERVICE_SET_PAUSE_TIMEOUT_SETTINGS = "set_pause_timeout_settings";

// --- Profiles ---
export const SERVICE_GET_ROOM_PROFILES       = "get_room_profiles";
export const SERVICE_SAVE_USER_ROOM_PROFILE  = "save_user_room_profile";
export const SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM = "save_room_profile_from_room";
export const SERVICE_OVERWRITE_ROOM_PROFILE = "overwrite_room_profile";
export const SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM = "overwrite_room_profile_from_room";
export const SERVICE_RENAME_ROOM_PROFILE = "rename_room_profile";
export const SERVICE_DELETE_ROOM_PROFILE = "delete_room_profile";
export const SERVICE_APPLY_ROOM_PROFILE      = "apply_room_profile";
export const SERVICE_UPDATE_ROOM_FIELDS      = "update_room_fields";
export const SERVICE_GET_SAVED_RUN_PROFILES  = "get_saved_run_profiles";
export const SERVICE_SAVE_RUN_PROFILE        = "save_run_profile";
export const SERVICE_OVERWRITE_RUN_PROFILE   = "overwrite_run_profile";
export const SERVICE_APPLY_RUN_PROFILE       = "apply_run_profile";
export const SERVICE_RENAME_RUN_PROFILE      = "rename_run_profile";
export const SERVICE_DELETE_RUN_PROFILE      = "delete_run_profile";

// --- Capabilities ---
export const SERVICE_GET_VACUUM_CAPABILITIES = "get_vacuum_capabilities";

// --- Theme ---
export const SERVICE_GET_THEME_LIBRARY      = "get_theme_library";
export const SERVICE_SAVE_THEME_AS_NEW      = "save_theme_as_new";
export const SERVICE_OVERWRITE_THEME        = "overwrite_theme";
export const SERVICE_RENAME_THEME           = "rename_theme";
export const SERVICE_SET_THEME_TAGS         = "set_theme_tags";
export const SERVICE_DELETE_THEME           = "delete_theme";
export const SERVICE_SET_ACTIVE_THEME       = "set_active_theme";
export const SERVICE_UPDATE_WORKING_DRAFT   = "update_working_draft";
export const SERVICE_REVERT_DRAFT           = "revert_draft";
export const SERVICE_EXPORT_THEME           = "export_theme";
export const SERVICE_IMPORT_THEME           = "import_theme";

// --- Map image ---
export const SERVICE_UPLOAD_MAP_IMAGE       = "upload_map_image";
export const SERVICE_DELETE_MAP_IMAGE       = "delete_map_image";
export const SERVICE_ANALYZE_MAP_IMAGE      = "analyze_map_image";
export const SERVICE_GET_MAP_SEGMENTS       = "get_map_segments";
export const SERVICE_ADJUST_MAP_SEGMENT     = "adjust_map_segment";
export const SERVICE_SET_SEGMENTATION_MODE  = "set_segmentation_mode";
export const SERVICE_SET_CUSTOM_SEGMENTS    = "set_custom_segments";
export const SERVICE_CREATE_CUSTOM_LAYOUT     = "create_custom_layout";
export const SERVICE_RENAME_CUSTOM_LAYOUT     = "rename_custom_layout";
export const SERVICE_DELETE_CUSTOM_LAYOUT     = "delete_custom_layout";
export const SERVICE_SET_ACTIVE_CUSTOM_LAYOUT = "set_active_custom_layout";

// --- Map UI overlays (segment↔room links, companion anchors) ---
// Backend-persisted equivalents of what used to live in browser
// localStorage. Card writes through the service; reads ride along on
// every analyze_map_image / get_map_segments response.
export const SERVICE_SET_SEGMENT_ROOM_LINK  = "set_segment_room_link";
export const SERVICE_SET_COMPANION_ANCHOR   = "set_companion_anchor";
export const SERVICE_SET_LIVE_MAP_ROTATION  = "set_live_map_rotation";

// --- Setup ---
export const SERVICE_SETUP_GET_STATUS       = "setup_get_status";
export const SERVICE_SETUP_ADD_VACUUM       = "setup_add_vacuum";
export const SERVICE_SETUP_IMPORT_MAP       = "setup_import_active_map";
export const SERVICE_SETUP_GET_MAP_ROOMS    = "setup_get_map_rooms";
export const SERVICE_SETUP_SAVE_ROOMS       = "setup_save_rooms";
export const SERVICE_SETUP_DELETE_MAP       = "setup_delete_map";
export const SERVICE_SETUP_REJECT_ROOMS     = "setup_reject_rooms";
export const SERVICE_SETUP_FORCE_REMOVE_ROOM = "setup_force_remove_room";
export const SERVICE_SETUP_SET_PANEL_TITLE  = "setup_set_panel_title";
export const SERVICE_SETUP_SET_MAP_CAMERA   = "setup_set_map_camera";

// --- Learning ---
export const SERVICE_FINALIZE_LEARNING_JOB  = "finalize_learning_job";
export const SERVICE_REBUILD_LEARNING_STATS = "rebuild_learning_stats";
export const SERVICE_RUN_LEARNING_ESTIMATE  = "run_learning_estimate";

// --- Tracking ---
export const SERVICE_GET_TRACKING_STATUS    = "get_tracking_status";
export const SERVICE_REFRESH_TRACKING_STATE = "refresh_tracking_state";
export const SERVICE_GET_TRACKING_HISTORY   = "get_tracking_history";
export const SERVICE_CLEAR_TRACKING_HISTORY = "clear_tracking_history";

/* =========================================================
   ENTITY ID PATTERNS
   =========================================================
   These are functions, not strings, because entity IDs include
   the vacuum object_id which varies per installation.

   vacuum_entity_id is always the full HA entity ID,
   e.g. "vacuum.alfred".

   object_id is the part after the dot, e.g. "alfred".
   ========================================================= */

/**
 * Extract the object_id portion from a vacuum entity ID.
 * e.g. "vacuum.alfred" → "alfred"
 */
export function vacuumObjectId(vacuumEntityId) {
  const parts = String(vacuumEntityId || "").split(".");
  return parts.length > 1 ? parts[1] : parts[0];
}

/**
 * Sensor entity IDs exposed by the integration per vacuum.
 */
export const ENTITY = {
  dockEvents:        (id) => `sensor.${vacuumObjectId(id)}_dock_events`,
  themeState:        (id) => `sensor.${vacuumObjectId(id)}_theme_state`,
  profileSensor:     (id) => `sensor.${vacuumObjectId(id)}_available_profiles`,
  activeMap:         (id) => `sensor.${vacuumObjectId(id)}_active_map`,
  robotPositionXRaw: (id) => `sensor.${vacuumObjectId(id)}_robot_position_x_raw`,
  robotPositionYRaw: (id) => `sensor.${vacuumObjectId(id)}_robot_position_y_raw`,
};

/* =========================================================
   INVALID STATE VALUES
   =========================================================
   Entity states that should be treated as "no value".
   ========================================================= */

export const INVALID_STATES = new Set([
  "unknown",
  "unavailable",
  "",
]);
