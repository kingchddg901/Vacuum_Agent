"""Constants for Eufy Vacuum Manager."""

from __future__ import annotations

DOMAIN = "eufy_vacuum"
NAME = "Eufy Vacuum Manager"
VERSION = "0.9.0"

CONF_TESTED_MODEL = "tested_model"
CONF_NOTES = "notes"

DEFAULT_TITLE = NAME

# ----------------------
# Service names
# ----------------------

SERVICE_REFRESH_BACKEND = "refresh_backend"
SERVICE_REBUILD_ACTIVE_MAP = "rebuild_active_map"
SERVICE_CLEAR_RUNTIME_STATE = "clear_runtime_state"

SERVICE_DISCOVER_ROOMS = "discover_rooms"
SERVICE_SAVE_MANAGED_ROOMS = "save_managed_rooms"
SERVICE_GET_VACUUM_MAPS = "get_vacuum_maps"

SERVICE_BUILD_QUEUE = "build_queue"
SERVICE_BUILD_ROOM_PAYLOAD = "build_room_payload"
SERVICE_GET_START_STATUS = "get_start_status"
SERVICE_START_SELECTED_ROOMS = "start_selected_rooms"
SERVICE_PAUSE_ACTIVE_JOB = "pause_active_job"
SERVICE_RESUME_ACTIVE_JOB = "resume_active_job"
SERVICE_CANCEL_ACTIVE_JOB = "cancel_active_job"

SERVICE_GET_QUEUE_STATE = "get_queue_state"
SERVICE_GET_PAYLOAD_STATE = "get_payload_state"
SERVICE_GET_ACTIVE_JOB = "get_active_job"
SERVICE_CLEAR_QUEUE = "clear_queue"
SERVICE_CLEAR_ACTIVE_JOB = "clear_active_job"

SERVICE_GET_LIFECYCLE_STATE = "get_lifecycle_state"
SERVICE_ACKNOWLEDGE_ERROR = "acknowledge_error"
SERVICE_GET_RECENT_ERRORS = "get_recent_errors"
SERVICE_GET_JOB_PROGRESS_SNAPSHOT = "get_job_progress_snapshot"
SERVICE_GET_JOB_CONTROL_STATE = "get_job_control_state"
SERVICE_GET_UPKEEP_SNAPSHOT = "get_upkeep_snapshot"
SERVICE_GET_DASHBOARD_SNAPSHOT = "get_dashboard_snapshot"
SERVICE_GET_DOCK_ACTION_STATUS = "get_dock_action_status"
SERVICE_GET_PAUSE_TIMEOUT_SETTINGS = "get_pause_timeout_settings"
SERVICE_SET_PAUSE_TIMEOUT_SETTINGS = "set_pause_timeout_settings"
SERVICE_WASH_MOP = "wash_mop"
SERVICE_DRY_MOP = "dry_mop"
SERVICE_STOP_DRY_MOP = "stop_dry_mop"
SERVICE_EMPTY_DUST = "empty_dust"
SERVICE_RESET_MAINTENANCE = "reset_maintenance"
SERVICE_SET_DOCK_EVENT_COUNT = "set_dock_event_count"

SERVICE_GET_ROOM_PROFILES = "get_room_profiles"
SERVICE_SAVE_USER_ROOM_PROFILE = "save_user_room_profile"
SERVICE_OVERWRITE_ROOM_PROFILE = "overwrite_room_profile"
SERVICE_RENAME_ROOM_PROFILE = "rename_room_profile"
SERVICE_DELETE_ROOM_PROFILE = "delete_room_profile"
SERVICE_APPLY_ROOM_PROFILE = "apply_room_profile"
SERVICE_SAVE_ROOM_PROFILE_FROM_ROOM = "save_room_profile_from_room"
SERVICE_OVERWRITE_ROOM_PROFILE_FROM_ROOM = "overwrite_room_profile_from_room"
SERVICE_UPDATE_ROOM_FIELDS = "update_room_fields"
SERVICE_GET_ROOM_ACCESS_EDITOR = "get_room_access_editor"
SERVICE_GET_ACCESS_GRAPH_HEALTH = "get_access_graph_health"
SERVICE_GET_SAVED_RUN_PROFILES = "get_saved_run_profiles"
SERVICE_SAVE_RUN_PROFILE = "save_run_profile"
SERVICE_APPLY_RUN_PROFILE = "apply_run_profile"
SERVICE_OVERWRITE_RUN_PROFILE = "overwrite_run_profile"
SERVICE_RENAME_RUN_PROFILE = "rename_run_profile"
SERVICE_DELETE_RUN_PROFILE = "delete_run_profile"
SERVICE_START_RUN_PROFILE = "start_run_profile"

# Capability service
SERVICE_GET_VACUUM_CAPABILITIES = "get_vacuum_capabilities"

# ----------------------
# Learning services
# ----------------------

SERVICE_SAVE_LEARNING_SNAPSHOT = "save_learning_snapshot"
SERVICE_FINALIZE_LEARNING_JOB = "finalize_learning_job"
SERVICE_REBUILD_LEARNING_STATS = "rebuild_learning_stats"
SERVICE_RUN_LEARNING_ESTIMATE = "run_learning_estimate"

# ----------------------
# Setup services (panel-driven)
# ----------------------

SERVICE_SETUP_GET_STATUS    = "setup_get_status"
SERVICE_SETUP_ADD_VACUUM    = "setup_add_vacuum"
SERVICE_SETUP_IMPORT_MAP    = "setup_import_active_map"
SERVICE_SETUP_GET_MAP_ROOMS = "setup_get_map_rooms"
SERVICE_SETUP_SAVE_ROOMS    = "setup_save_rooms"
SERVICE_SETUP_DELETE_MAP    = "setup_delete_map"

# ----------------------
# Mapping services
# ----------------------

SERVICE_UPLOAD_MAP_IMAGE = "upload_map_image"
SERVICE_ANALYZE_MAP_IMAGE = "analyze_map_image"
SERVICE_GET_MAP_SEGMENTS = "get_map_segments"
SERVICE_ADJUST_MAP_SEGMENT = "adjust_map_segment"

# ----------------------
# Theme services
# ----------------------

SERVICE_GET_THEME_LIBRARY = "get_theme_library"
SERVICE_SAVE_THEME_AS_NEW = "save_theme_as_new"
SERVICE_OVERWRITE_THEME = "overwrite_theme"
SERVICE_RENAME_THEME = "rename_theme"
SERVICE_DELETE_THEME = "delete_theme"
SERVICE_SET_ACTIVE_THEME = "set_active_theme"
SERVICE_UPDATE_WORKING_DRAFT = "update_working_draft"
SERVICE_REVERT_DRAFT = "revert_draft"
SERVICE_EXPORT_THEME = "export_theme"
SERVICE_IMPORT_THEME = "import_theme"

# ----------------------
# Internal data keys
# ----------------------

DATA_SERVICES_REGISTERED = "services_registered"
DATA_RUNTIME = "runtime"

DATA_LEARNING = "learning"

DATA_BATTERY = "battery"

#: ErrorTracker instance — captures upstream error_message + vacuum.state
#: transitions, latches them as active_run / last_device / recent_errors,
#: persists across restarts. See core/error_tracker.py.
DATA_ERROR_TRACKER = "error_tracker"

# ----------------------
# Events
# ----------------------

EVENT_JOB_FINISHED = "eufy_vacuum_job_finished"
EVENT_ROOM_STARTED = "eufy_vacuum_room_started"
EVENT_ROOM_FINISHED = "eufy_vacuum_room_finished"
EVENT_PATH_BLOCKED = "eufy_vacuum_path_blocked"

# Fired every 5 s while at least one vacuum has an active job. The backend
# drives this — the dashboard card subscribes and refreshes its snapshot
# without having to poll. Carries vacuum_entity_id and map_id; consumers
# should treat the payload as a "refresh now" trigger and re-read the
# snapshot via the existing service. See _register_job_progress_listener
# in __init__.py for the rationale.
EVENT_JOB_PROGRESS_TICK = "eufy_vacuum_job_progress_tick"

# Fired from get_job_progress_snapshot() when the robot has been in a room for
# >= 2× its learned timing threshold and awaiting_bounds_exit is already true.
# Fires at most once per room per job (tracked via _stall_notified_room_ids in
# the active job dict).  Payload: vacuum_entity_id, map_id, room_id, room_name,
# elapsed_minutes, expected_minutes, stall_ratio.
EVENT_STALL_DETECTED = "eufy_vacuum_stall_detected"

# Fired from finalize_learning_job after a cancelled/failed/interrupted job
# when at least one queued room was not cleaned.  Payload: vacuum_entity_id,
# job_id, outcome_status, missed_room_ids (list of ints), missed_rooms
# (list of {room_id, name} dicts).  Use with the retry_missed_rooms service
# to automatically re-queue the skipped rooms.
EVENT_RUN_INCOMPLETE = "eufy_vacuum_run_incomplete"

# ----------------------
# Supported / tested
# ----------------------

SUPPORTED_TESTED_MODEL = "Eufy X10 Pro Omni"
