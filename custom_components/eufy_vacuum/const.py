"""Constants for Vacuum Agent."""

from __future__ import annotations

# Adapter-specific identity constants — DOMAIN, NAME, VERSION, DEFAULT_TITLE,
# and SUPPORTED_TESTED_MODEL live in the adapter package so that porting to a
# different vacuum ecosystem only requires changing that one file.
# NOTE: STORAGE_KEY must also be explicitly declared in the adapter rather than
# derived from DOMAIN at runtime, to ensure storage isolation across adapters.
# This will be addressed in a later pass.
from .adapters.eufy.const import (
    DEFAULT_TITLE,
    DOMAIN,
    NAME,
    SUPPORTED_TESTED_MODEL,
    VERSION,
)

CONF_TESTED_MODEL = "tested_model"
CONF_NOTES = "notes"
CONF_VACUUM_ENTITY_ID = "vacuum_entity_id"

# ----------------------
# Service names
# ----------------------

SERVICE_REFRESH_BACKEND = "refresh_backend"
SERVICE_REBUILD_ACTIVE_MAP = "rebuild_active_map"
SERVICE_CLEAR_RUNTIME_STATE = "clear_runtime_state"

SERVICE_DISCOVER_ROOMS = "discover_rooms"
SERVICE_SAVE_MANAGED_ROOMS = "save_managed_rooms"
SERVICE_GET_VACUUM_MAPS = "get_vacuum_maps"
SERVICE_RECONCILE_ROOM = "reconcile_room"

SERVICE_BUILD_QUEUE = "build_queue"
SERVICE_BUILD_ROOM_PAYLOAD = "build_room_payload"
SERVICE_GET_START_STATUS = "get_start_status"
SERVICE_START_SELECTED_ROOMS = "start_selected_rooms"
SERVICE_START_ZONE_CLEAN = "start_zone_clean"
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
SERVICE_SET_MAINTENANCE_INTERVAL = "set_maintenance_interval"
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
# Adapter config services
# ----------------------

SERVICE_SAVE_ADAPTER_CONFIG = "save_adapter_config"
SERVICE_DELETE_ADAPTER_CONFIG = "delete_adapter_config"
SERVICE_GET_ADAPTER_CONFIG = "get_adapter_config"
SERVICE_DISCOVER_ADAPTER_ENTITIES = "discover_adapter_entities"
SERVICE_OBSERVE_ENTITY_STATES = "observe_entity_states"

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
SERVICE_SETUP_REJECT_ROOMS  = "setup_reject_rooms"
SERVICE_SETUP_FORCE_REMOVE_ROOM = "setup_force_remove_room"
SERVICE_SETUP_SET_PANEL_TITLE = "setup_set_panel_title"
# Per-vacuum live-map image/camera entity override. Stored on the vacuum record as
# `live_map_image_entity`; the dashboard snapshot's live-backdrop resolution prefers it
# over the adapter pattern (see manager.get_dashboard_snapshot). For installs whose
# live-map entity is device-named and doesn't match the adapter's {object_id} pattern.
SERVICE_SETUP_SET_MAP_CAMERA = "setup_set_map_camera"

# ----------------------
# Mapping services
# ----------------------

SERVICE_UPLOAD_MAP_IMAGE = "upload_map_image"
SERVICE_DELETE_MAP_IMAGE = "delete_map_image"
SERVICE_ANALYZE_MAP_IMAGE = "analyze_map_image"
SERVICE_GET_MAP_SEGMENTS = "get_map_segments"
SERVICE_ADJUST_MAP_SEGMENT = "adjust_map_segment"

# Map UI overlay state — segment↔room linkage and companion anchor
# positions. Both used to live in browser localStorage; moved to backend
# storage so a single configuration persists across browsers and devices.
# Stored on the per-map bucket as `segment_room_links` and
# `companion_anchors`; ride along on every analyze_map_image /
# get_map_segments response.
SERVICE_SET_SEGMENT_ROOM_LINK = "set_segment_room_link"
SERVICE_SET_COMPANION_ANCHOR = "set_companion_anchor"
# Live-map display rotation (0/90/180/270), stored on the per-map bucket as
# `live_map_rotation` and surfaced in the dashboard snapshot. Display only — never
# affects dispatch. Backend-stored so the orientation follows the user across devices.
SERVICE_SET_LIVE_MAP_ROTATION = "set_live_map_rotation"
# Per-map overlay-layer visibility (Wave 3b). Stores a partial `overlay_visibility`
# dict on the map bucket (user deltas over the defaults); surfaced in the snapshot as
# `map_overlay_visibility` and mirrored on sensor.<vac>_map_overlays. Display only.
SERVICE_SET_MAP_OVERLAY_VISIBILITY = "set_map_overlay_visibility"
# Card-render raster + decode params for the VA's OWN client-side map render (Wave 1).
# Adapter-driven (map_render.format); fetched on demand + cached by `version`.
SERVICE_GET_MAP_RENDER_DATA = "get_map_render_data"
# Lightweight live MOVING-overlay pose (robot/dock anchors + current-room + heading) from
# the fork's in-memory coordinator (~2s fresh). Polled by the card on the live cadence so
# the robot overlay isn't gated by the slower .storage write + full-snapshot fetch.
SERVICE_GET_MAP_LIVE_POSE = "get_map_live_pose"
# Verify probe (diagnostic): compare the fork's in-memory _map_data against the .storage
# map_data (byte-identical check) before repointing the map source to the fresher, loop-safe
# in-memory MapData. Returns a per-field comparison + a normalization_safe verdict.
SERVICE_COMPARE_MAP_SOURCES = "compare_map_sources"
# CV-or-Custom segmentation toggle. Only flips `segmentation_mode` on the map
# bucket; never re-runs the segmenter (see _handle_set_segmentation_mode).
SERVICE_SET_SEGMENTATION_MODE = "set_segmentation_mode"
# Author no-CV custom segments from primitives (rasterised server-side into the
# same polygon shape CV produces); replace-all into the custom_segments store.
SERVICE_SET_CUSTOM_SEGMENTS = "set_custom_segments"
# Named custom layouts — a map can hold many (each its own backdrop / segments /
# room links / mascot anchors); these CRUD them and pick the active one.
SERVICE_CREATE_CUSTOM_LAYOUT = "create_custom_layout"
SERVICE_RENAME_CUSTOM_LAYOUT = "rename_custom_layout"
SERVICE_DELETE_CUSTOM_LAYOUT = "delete_custom_layout"
SERVICE_SET_ACTIVE_CUSTOM_LAYOUT = "set_active_custom_layout"

# ----------------------
# Theme services
# ----------------------

SERVICE_GET_THEME_LIBRARY = "get_theme_library"
SERVICE_SAVE_THEME_AS_NEW = "save_theme_as_new"
SERVICE_OVERWRITE_THEME = "overwrite_theme"
SERVICE_RENAME_THEME = "rename_theme"
SERVICE_SET_THEME_TAGS = "set_theme_tags"
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

#: AdapterCoordinator instance — per-config-entry owner of the adapter
#: registry (vacuum_entity_id -> adapter_config). Replaces the previous
#: module-level _REGISTRY dict; bare-function lookups in
#: adapters/registry.py now route through this. See
#: adapters/registry.py:AdapterCoordinator.
DATA_ADAPTER_COORDINATOR = "adapter_coordinator"

# ----------------------
# Events
# ----------------------

EVENT_JOB_FINISHED       = f"{DOMAIN}_job_finished"
EVENT_ROOM_STARTED       = f"{DOMAIN}_room_started"
EVENT_ROOM_FINISHED      = f"{DOMAIN}_room_finished"
EVENT_PATH_BLOCKED       = f"{DOMAIN}_path_blocked"

# Fired when an app-started (external) run finishes and is captured as a PENDING
# record under learning/<slug>/external_jobs/. The review card subscribes and
# surfaces it so the user can confirm room identities + edge-mop. Payload:
# vacuum_entity_id, map_id, record_path, segment_count, detection_ts.
EVENT_EXTERNAL_RUN_PENDING = f"{DOMAIN}_external_run_pending"

# Fired every 5 s while at least one vacuum has an active job. The backend
# drives this — the dashboard card subscribes and refreshes its snapshot
# without having to poll. Carries vacuum_entity_id and map_id; consumers
# should treat the payload as a "refresh now" trigger and re-read the
# snapshot via the existing service. See _register_job_progress_listener
# in __init__.py for the rationale.
EVENT_JOB_PROGRESS_TICK  = f"{DOMAIN}_job_progress_tick"

# Fired from get_job_progress_snapshot() when the robot has been in a room for
# >= 2× its learned timing threshold and awaiting_bounds_exit is already true.
# Fires at most once per room per job (tracked via _stall_notified_room_ids in
# the active job dict).  Payload: vacuum_entity_id, map_id, room_id, room_name,
# elapsed_minutes, expected_minutes, stall_ratio.
EVENT_STALL_DETECTED     = f"{DOMAIN}_stall_detected"

# Fired from finalize_learning_job after a cancelled/failed/interrupted job
# when at least one queued room was not cleaned.  Payload: vacuum_entity_id,
# job_id, outcome_status, missed_room_ids (list of ints), missed_rooms
# (list of {room_id, name} dicts).  Use with the retry_missed_rooms service
# to automatically re-queue the skipped rooms.
EVENT_RUN_INCOMPLETE     = f"{DOMAIN}_run_incomplete"

# Fired once per room per job when the live queue advances PAST a queued room that was
# never cleaned (a non-sequential advance — position-reliable brands or transition
# detection; ~never for Eufy's sequential counter rollover, which can't attribute a
# mid-run skip). Payload: vacuum_entity_id, map_id, job_id, room_id, room_name,
# completed_room_ids. The reliable post-run "missed rooms" remains EVENT_RUN_INCOMPLETE.
EVENT_ROOM_SKIPPED       = f"{DOMAIN}_room_skipped"

# ----------------------
# Supported / tested
# ----------------------

# SUPPORTED_TESTED_MODEL is imported from adapters/eufy/const.py above.
