"""
Adapter configuration schema for the ha_vacuum_manager framework.

Defines the canonical shape of the per-vacuum adapter config dict that
both the code adapter path and the config adapter path must produce.

The schema is the contract between:
  - Adapter authors (who produce it)
  - The framework runtime (which consumes it)
  - The UI config flow (which will generate it in a future pass)

Every field is documented with:
  - What it controls in the framework
  - Whether it is required or optional
  - What the framework does when it is absent (graceful degradation)

Two paths produce this schema:
  - Code adapter: registers at startup via register_adapter_config()
  - Config adapter: written by the UI config flow to storage

The framework reads from the adapter registry regardless of which path
populated it. See adapters/registry.py.
"""

from __future__ import annotations

ADAPTER_CONFIG_SCHEMA: dict[str, dict] = {

    # === IDENTITY =========================================================

    "adapter_id": {
        "type": "str",
        "required": True,
        "description": (
            "Unique identifier for this adapter. Used for logging and "
            "disambiguation when multiple adapters are registered. "
            "Example: 'eufy_x10_pro_omni'"
        ),
    },

    "source": {
        "type": "str",
        "required": True,
        "values": ["code", "config"],
        "description": (
            "How this adapter config was produced. 'code' = registered by "
            "a code adapter at startup. 'config' = written by the UI config "
            "flow. The framework treats both identically at runtime."
        ),
    },

    "display_name": {
        "type": "str",
        "required": False,
        "description": "Human-readable name shown in the UI and logs.",
    },

    # === ENTITIES =========================================================
    # Full entity IDs for each companion sensor/entity the framework reads.
    # All are optional — absent entities degrade the corresponding feature.

    "entities": {
        "type": "dict",
        "required": True,
        "description": "Full HA entity IDs for companion entities.",
        "fields": {
            "task_status": {
                "type": "str",
                "required": False,
                "description": (
                    "Task status sensor. Required for lifecycle detection, "
                    "job completion signal, and error tracking. "
                    "Degradation: lifecycle and learning disabled without it."
                ),
            },
            "dock_status": {
                "type": "str",
                "required": False,
                "description": (
                    "Dock status sensor. Required for dock event recording, "
                    "mop wash observation, and water amendment. "
                    "Degradation: dock events and water amendment disabled."
                ),
            },
            "active_map": {
                "type": "str",
                "required": False,
                "description": (
                    "Active map sensor. Required for map mismatch detection "
                    "and multi-floor support. "
                    "Degradation: map mismatch check skipped."
                ),
            },
            "active_cleaning_target": {
                "type": "str",
                "required": False,
                "description": (
                    "Active cleaning target sensor. Used as secondary "
                    "completion signal alongside task_status. "
                    "Degradation: completion relies on task_status alone."
                ),
            },
            "cleaning_time": {
                "type": "str",
                "required": False,
                "description": (
                    "Cleaning time sensor in seconds. Used by job finalizer "
                    "for actual duration. "
                    "Degradation: duration derived from job timestamps only."
                ),
            },
            "cleaning_area": {
                "type": "str",
                "required": False,
                "description": (
                    "Cleaning area sensor in m². Used by job finalizer. "
                    "Degradation: area omitted from job record."
                ),
            },
            "battery": {
                "type": "str",
                "required": False,
                "description": (
                    "Battery level sensor (0-100). Used by battery health "
                    "manager and low battery return detection. "
                    "Degradation: falls back to vacuum entity battery_level "
                    "attribute."
                ),
            },
            "error_message": {
                "type": "str",
                "required": False,
                "description": (
                    "Error message sensor. Primary signal for error tracking. "
                    "Degradation: error tracking relies on secondary channels "
                    "only (vacuum state, task_status)."
                ),
            },
            "charging": {
                "type": "str",
                "required": False,
                "description": (
                    "Charging binary sensor. Primary charging detection signal. "
                    "Degradation: charging detection falls back to substring "
                    "matching on task_status/dock_status."
                ),
            },
            "wash_frequency_mode": {
                "type": "str",
                "required": False,
                "description": (
                    "Wash frequency mode select entity. "
                    "Degradation: water estimation uses default interval."
                ),
            },
            "wash_frequency_value_time": {
                "type": "str",
                "required": False,
                "description": (
                    "Wash frequency interval number entity (minutes). "
                    "Degradation: water estimation uses default interval."
                ),
            },
            "dry_duration": {
                "type": "str",
                "required": False,
                "description": (
                    "Dry duration select entity. Read at dry_start dock "
                    "events and stored with the event record."
                ),
            },
            "water_level": {
                "type": "str",
                "required": False,
                "description": (
                    "Station clean water level sensor (0-100%). "
                    "Degradation: water estimation uses flow rates only, "
                    "no actual tank level tracking."
                ),
            },
            "robot_position_x": {
                "type": "str",
                "required": False,
                "description": (
                    "Robot X position sensor (raw vacuum coordinates). "
                    "Required for trace-based room bounds derivation. "
                    "Degradation: mapping subsystem inactive."
                ),
            },
            "robot_position_y": {
                "type": "str",
                "required": False,
                "description": (
                    "Robot Y position sensor (raw vacuum coordinates). "
                    "Required for trace-based room bounds derivation. "
                    "Degradation: mapping subsystem inactive."
                ),
            },
            "work_mode": {
                "type": "str",
                "required": False,
                "description": (
                    "Work mode sensor. Used by the start-blocker check "
                    "in core/manager.py to detect blocked work modes. "
                    "Degradation: work mode block check skipped."
                ),
            },
            "cleaning_intensity": {
                "type": "str",
                "required": False,
                "description": (
                    "Cleaning intensity select entity. Used as fallback for "
                    "path control capability detection. "
                    "Degradation: path control inferred from model family only."
                ),
            },
        },
    },

    # === VOCABULARY =======================================================
    # Brand-specific state strings matched after .strip().lower().

    "vocabulary": {
        "type": "dict",
        "required": False,
        "description": "Brand-specific state vocabulary sets.",
        "fields": {
            "hard_service_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Dock/task states that hard-block job start. The dock or "
                    "vacuum is performing a service action that cannot be "
                    "interrupted (washing, recycling, emptying). "
                    "Degradation: no hard service blocking."
                ),
            },
            "drying_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Dock states that produce a warning but do not block "
                    "job start. "
                    "Degradation: drying warning skipped."
                ),
            },
            "active_run_task_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Task status strings that indicate the vacuum is actively "
                    "running a job. Used to set has_observed_active_lifecycle "
                    "and detect vacuum_busy state."
                ),
            },
            "not_error_sentinels": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Error message values that mean no error is present. "
                    "Anything not in this set is treated as a real error. "
                    "Degradation: uses framework defaults."
                ),
            },
            "blocked_work_mode_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Work mode strings that block job start. These are "
                    "raw (non-normalized) values from the work_mode sensor. "
                    "Degradation: work mode block check skipped."
                ),
            },
            "blocked_task_status_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Task status strings that block job start. Raw "
                    "(non-normalized) values. "
                    "Degradation: task status block check skipped."
                ),
            },
            "blocked_dock_status_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Dock status strings that block job start. Raw "
                    "(non-normalized) values. "
                    "Degradation: dock status block check skipped."
                ),
            },
            "cancel_service_exclusion_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Normalized task_status strings that, if seen in the "
                    "transition history of a very short job, explain the "
                    "early return as a service event (low-battery return, "
                    "mop wash, dust empty) rather than a manual cancel. "
                    "When any of these strings appears the cancel detection "
                    "check returns cancel_likely=False. "
                    "Degradation: uses framework defaults."
                ),
            },
            "water_level_aliases": {
                "type": "dict[str, str]",
                "required": False,
                "description": (
                    "Maps brand-specific water-level display strings (lowercased) "
                    "to canonical keys the framework uses for water-rate lookup. "
                    "Canonical keys: 'low', 'medium', 'high'. "
                    "Example: {'small': 'low', 'standard': 'medium', 'large': 'high'}. "
                    "Degradation: unknown values pass through with spaces replaced "
                    "by underscores and the estimator uses default flow rate."
                ),
            },
            "wash_frequency_mode_aliases": {
                "type": "dict[str, str]",
                "required": False,
                "description": (
                    "Maps brand-specific wash-frequency-mode display strings "
                    "(lowercased) to canonical mode keys. "
                    "Canonical keys: 'by_time', 'by_area', 'after_each_clean'. "
                    "Example: {'by time': 'by_time', 'by area': 'by_area'}. "
                    "Degradation: unknown values pass through and the estimator "
                    "falls back to the default interval."
                ),
            },

            # --- User-facing dropdown vocabularies -----------------
            # The card's room editor and rule editor populate dropdowns
            # for clean_mode / fan_speed / water_level / clean_intensity
            # from these lists. Each entry is {value, label}:
            #   - `value` is what the adapter writes to room records and
            #     dispatch payloads (the canonical framework value).
            #   - `label` is the human-readable display text shown to
            #     the user.
            # Adapters declare which values are actually supported for
            # their brand. Eufy declares 4 fan speeds; Roborock with
            # Max+ would declare 5; etc.
            "clean_mode_options": {
                "type": "list[dict]",
                "required": False,
                "description": (
                    "Valid clean-mode values for this vacuum. List of "
                    "{value, label} dicts. Canonical values: 'vacuum', "
                    "'mop', 'vacuum_mop'. Example: "
                    "[{'value': 'vacuum', 'label': 'Vacuum'}, ...]. "
                    "Degradation: card falls back to a framework-canonical "
                    "default list with all three values."
                ),
                "entry_fields": {
                    "value": {"type": "str", "required": True},
                    "label": {"type": "str", "required": True},
                },
            },
            "fan_speed_options": {
                "type": "list[dict]",
                "required": False,
                "description": (
                    "Valid fan-speed values for this vacuum. List of "
                    "{value, label} dicts. Eufy: Quiet/Standard/Boost/Max. "
                    "Roborock with Max+: Quiet/Standard/Boost/Max/Max+. "
                    "Each brand declares what its hardware supports."
                ),
                "entry_fields": {
                    "value": {"type": "str", "required": True},
                    "label": {"type": "str", "required": True},
                },
            },
            "water_level_options": {
                "type": "list[dict]",
                "required": False,
                "description": (
                    "Valid water-level values for this vacuum (mop-capable "
                    "models only). List of {value, label} dicts. "
                    "Eufy: Off/Low/Medium/High."
                ),
                "entry_fields": {
                    "value": {"type": "str", "required": True},
                    "label": {"type": "str", "required": True},
                },
            },
            "clean_intensity_options": {
                "type": "list[dict]",
                "required": False,
                "description": (
                    "Valid clean-intensity values for this vacuum. List "
                    "of {value, label} dicts. Eufy: Quick/Narrow/Deep. "
                    "Most non-Eufy brands omit this — leave the field "
                    "absent and the card will hide the intensity picker."
                ),
                "entry_fields": {
                    "value": {"type": "str", "required": True},
                    "label": {"type": "str", "required": True},
                },
            },
        },
    },

    # === COMPLETION =======================================================

    "completion": {
        "type": "dict",
        "required": False,
        "description": "Job completion signal configuration.",
        "fields": {
            "task_status_value": {
                "type": "str",
                "required": False,
                "description": (
                    "Normalized task_status value that signals job completion. "
                    "Default: 'completed'."
                ),
            },
            "secondary_clear_entity": {
                "type": "str",
                "required": False,
                "description": (
                    "Entity key from entities dict whose cleared state "
                    "is required alongside task_status_value for completion. "
                    "Default: 'active_cleaning_target'."
                ),
            },
            "secondary_clear_sentinels": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Values that mean the secondary entity is cleared. "
                    "Default: ['', 'unknown', 'unavailable', 'none', 'null']."
                ),
            },
        },
    },

    # === CHARGING =========================================================

    "charging": {
        "type": "dict",
        "required": False,
        "description": "Charging detection configuration.",
        "fields": {
            "binary_sensor_entity": {
                "type": "str",
                "required": False,
                "description": (
                    "Entity key from entities dict for the charging binary "
                    "sensor. Primary charging detection signal. "
                    "Degradation: fallback substring matching used."
                ),
            },
            "fallback_task_status_string": {
                "type": "str",
                "required": False,
                "description": (
                    "task_status value that indicates charging resumed "
                    "mid-job. Used as fallback when binary sensor is absent."
                ),
            },
            "fallback_substrings": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Substrings matched against task_status/dock_status for "
                    "fallback charging detection."
                ),
            },
        },
    },

    # === ERROR TRACKING ===================================================

    "error_tracking": {
        "type": "dict",
        "required": False,
        "description": "Error tracker configuration.",
        "fields": {
            "task_status_error_value": {
                "type": "str",
                "required": False,
                "description": (
                    "Normalized task_status value that indicates an error "
                    "state. Used as secondary error channel alongside "
                    "vacuum entity state. Default: 'error'."
                ),
            },
            "grace_window_seconds": {
                "type": "int",
                "required": False,
                "description": (
                    "Seconds to wait after secondary error signal before "
                    "finalizing as unknown error. Some firmware emits the "
                    "state before the error message. Default: 5."
                ),
            },
            "error_code_attribute_names": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Attribute key names to check when reading the error "
                    "code from the vacuum or error_message entity attributes. "
                    "Tried in order — first non-zero int wins."
                ),
            },
            "unknown_error_message": {
                "type": "str",
                "required": False,
                "description": (
                    "Placeholder message used when the grace window elapses "
                    "without a real error message arriving. "
                    "Default: 'Unknown error during run'."
                ),
            },
        },
    },

    # === DOCK EVENTS ======================================================

    "dock_events": {
        "type": "dict",
        "required": False,
        "description": "Dock event recording configuration.",
        "fields": {
            "enabled": {
                "type": "bool",
                "required": False,
                "description": (
                    "Whether to record dock events (wash, empty, dry). "
                    "Set False for brands with no dock actions. Default: False."
                ),
            },
            "triggers": {
                "type": "dict[str, list[str]]",
                "required": False,
                "description": (
                    "Maps framework event type keys to the dock_status "
                    "strings that trigger them. Keys are framework vocabulary "
                    "('last_mop_wash', 'last_dust_empty', 'last_dry_start'). "
                    "Values are normalized dock_status strings. "
                    "Absent keys produce no events."
                ),
            },
        },
    },

    # === POST-JOB WASH AMENDMENT ==========================================

    "post_job_wash_amendment": {
        "type": "dict",
        "required": False,
        "description": (
            "Post-job mop wash water amendment configuration. "
            "Only needed for brands whose dock washes the mop after docking, "
            "after the job file has been finalized."
        ),
        "fields": {
            "enabled": {
                "type": "bool",
                "required": False,
                "description": (
                    "Whether to register the post-job wash watcher. "
                    "Set False for brands with no post-job wash behavior. "
                    "Default: False."
                ),
            },
            "trigger_states": {
                "type": "list[str]",
                "required": False,
                "description": (
                    "Normalized dock_status strings that increment the "
                    "post-job wash count."
                ),
            },
            "commit_state": {
                "type": "str",
                "required": False,
                "description": (
                    "Normalized dock_status string that signals the wash "
                    "cycle is complete and triggers the amendment commit."
                ),
            },
            "debounce_seconds": {
                "type": "float",
                "required": False,
                "description": (
                    "Minimum seconds between wash count increments. Prevents "
                    "double-counting multi-state wash sequences. "
                    "Set to 0 for brands with single-state wash cycles."
                ),
            },
            "timeout_seconds": {
                "type": "int",
                "required": False,
                "description": (
                    "Seconds after which the amendment watcher closes "
                    "regardless of commit_state. Safety valve."
                ),
            },
        },
    },

    # === ROOM DISCOVERY ===================================================

    "discovery": {
        "type": "dict",
        "required": False,
        "description": "Room discovery configuration.",
        "fields": {
            "room_list_entity": {
                "type": "str",
                "required": False,
                "description": (
                    "Which entity exposes the room list. Use 'vacuum_entity' "
                    "to read from the vacuum entity itself, or supply a full "
                    "entity ID. Default: 'vacuum_entity'."
                ),
            },
            "room_list_attribute": {
                "type": "str",
                "required": False,
                "description": (
                    "Attribute name on the entity that contains the room list. "
                    "Expected to be a list of dicts."
                ),
            },
            "room_id_key": {
                "type": "str",
                "required": False,
                "description": (
                    "Key in each room dict that contains the room ID. "
                    "Example: 'id' for Eufy, 'segment_id' for Roborock."
                ),
            },
            "room_name_key": {
                "type": "str",
                "required": False,
                "description": (
                    "Key in each room dict that contains the room name. "
                    "Example: 'name'."
                ),
            },
            "auto_refresh_on": {
                "type": "list[str]",
                "required": False,
                "values": [
                    "vacuum_docked",
                    "active_map_changed",
                    "config_entry_reload",
                ],
                "description": (
                    "Event triggers that automatically run room discovery. "
                    "'vacuum_docked' fires whenever the vacuum entity "
                    "transitions to 'docked'. 'active_map_changed' fires "
                    "when the active_map sensor value changes. "
                    "'config_entry_reload' fires once per integration setup. "
                    "Manual rescan via service call is always available "
                    "regardless of this list. "
                    "Default: ['vacuum_docked', 'active_map_changed', "
                    "'config_entry_reload']."
                ),
            },
            "auto_refresh_interval_seconds": {
                "type": "int",
                "required": False,
                "description": (
                    "Safety-net periodic discovery interval in seconds. "
                    "Runs in addition to event-driven triggers; covers idle "
                    "vacuums that never reach a triggering event. "
                    "Set to 0 to disable the periodic floor. "
                    "Default: 21600 (6 hours)."
                ),
            },
            "removal_confirmation_passes": {
                "type": "int",
                "required": False,
                "description": (
                    "Number of consecutive discovery passes a configured "
                    "room must be absent from before it is flagged as "
                    "removed in the setup-status response. Prevents "
                    "transient API glitches from producing spurious "
                    "removal notifications. Set higher for noisy "
                    "integrations, lower for stable ones. "
                    "Default: 3."
                ),
            },
            "new_room_confirmation_passes": {
                "type": "int",
                "required": False,
                "description": (
                    "Number of consecutive discovery passes a new room "
                    "must appear in before it is flagged for user review. "
                    "Default: 1 (surface immediately). Increase only for "
                    "integrations that frequently surface phantom rooms."
                ),
            },
        },
    },

    # === SETUP ============================================================
    # Adapter-declared setup steps. Drives the integration's onboarding
    # state machine and the card's setup tab.

    "setup": {
        "type": "dict",
        "required": False,
        "description": (
            "Setup-flow step declaration. Each step ID maps to a "
            "framework-defined service and card view. The framework "
            "iterates the adapter's declared list in order; unknown "
            "step IDs reject the adapter at registration. "
            "Absent = default to ['add_vacuum', 'save_rooms']."
        ),
        "fields": {
            "steps": {
                "type": "list[str]",
                "required": True,
                "values": [
                    "add_vacuum",
                    "import_active_map",
                    "save_rooms",
                    "calibrate_map",
                    "set_dock_position",
                ],
                "description": (
                    "Ordered list of setup step IDs. "
                    "'add_vacuum' is required for every adapter. "
                    "'save_rooms' is required for every adapter. "
                    "'import_active_map' is needed by brands whose "
                    "integration surfaces one map at a time and requires "
                    "an explicit import operation (Eufy). "
                    "'calibrate_map' and 'set_dock_position' are reserved "
                    "for future brand-specific extensions."
                ),
            },
        },
    },

    # === DISPATCH =========================================================

    "dispatch": {
        "type": "dict",
        "required": True,
        "description": "Job dispatch configuration.",
        "fields": {
            "template": {
                "type": "str",
                "required": True,
                "values": [
                    "eufy_room_clean",
                    "roborock_segment_clean",
                    "dreame_room_clean",
                    "generic_room_ids",
                ],
                "description": (
                    "Payload template to use. Determines how the framework "
                    "constructs the service call payload from the resolved "
                    "room list."
                ),
            },
            "service_domain": {
                "type": "str",
                "required": True,
                "description": "HA service domain. Example: 'vacuum'.",
            },
            "service_name": {
                "type": "str",
                "required": True,
                "description": "HA service name. Example: 'send_command'.",
            },
            "command": {
                "type": "str",
                "required": False,
                "description": (
                    "Command string passed to the service. Required for "
                    "templates that use a 'command' field (e.g. Eufy). "
                    "Omit for templates that call the service directly."
                ),
            },
            "map_id_field": {
                "type": "str",
                "required": False,
                "description": (
                    "Field name for map_id in the payload. "
                    "Default: 'map_id'."
                ),
            },
            "map_id_type": {
                "type": "str",
                "required": False,
                "values": ["int", "str"],
                "description": (
                    "Type to cast map_id to before dispatch. "
                    "Default: 'str'."
                ),
            },
            "room_id_field": {
                "type": "str",
                "required": False,
                "description": (
                    "Field name for room ID in each room payload entry. "
                    "Example: 'id' for Eufy, 'segment_id' for Roborock."
                ),
            },
            "clean_passes_field": {
                "type": "str",
                "required": False,
                "description": (
                    "Field name for clean passes in each room payload entry. "
                    "Example: 'clean_times' for Eufy, 'repeat' for Roborock."
                ),
            },
            "rooms_field": {
                "type": "str",
                "required": False,
                "description": (
                    "Field name for the rooms list in the payload. "
                    "Example: 'rooms' for Eufy, 'segments' for Roborock."
                ),
            },
            "room_fields": {
                "type": "dict[str, dict]",
                "required": False,
                "description": (
                    "Per-canonical-field rename + value mapping for the "
                    "per-room payload entries. Keys are canonical field "
                    "names the framework writes internally; values are "
                    "{field_name, value_map} dicts that control how each "
                    "field appears on the wire. Absent canonical keys "
                    "fall back to identity (canonical name, no value "
                    "transform). field_name=null omits the field entirely."
                ),
                "canonical_fields": [
                    "fan_speed",
                    "clean_mode",
                    "clean_intensity",
                    "water_level",
                    "edge_mopping",
                    "path_type",
                ],
                "entry_fields": {
                    "field_name": {
                        "type": "str | null",
                        "required": False,
                        "description": (
                            "Wire field name to use for this canonical field. "
                            "Set to null to omit the field from the payload "
                            "entirely (for brands that don't expose it)."
                        ),
                    },
                    "value_map": {
                        "type": "dict[str, Any] | null",
                        "required": False,
                        "description": (
                            "Maps canonical string values to the brand-"
                            "specific wire values. Lookup is by str(value) — "
                            "booleans and other non-string canonical values "
                            "are stringified before lookup. Values not in "
                            "the map pass through unchanged. Set to null or "
                            "omit for identity passthrough."
                        ),
                    },
                },
            },
        },
    },

    # === CAPABILITIES =====================================================

    "capabilities": {
        "type": "dict",
        "required": False,
        "description": (
            "Explicit capability flag declarations. Override or supplement "
            "the entity-presence-based capability detection in capabilities.py. "
            "For code adapters these are set from known hardware specs. "
            "For config adapters these are set by the user in the UI."
        ),
        "fields": {
            "supports_mop_features": {"type": "bool", "required": False},
            "supports_water_control": {"type": "bool", "required": False},
            "supports_path_control": {"type": "bool", "required": False},
            "supports_edge_mopping": {"type": "bool", "required": False},
            "supports_mop_wash": {"type": "bool", "required": False},
            "supports_mop_dry": {"type": "bool", "required": False},
            "supports_empty_dust": {"type": "bool", "required": False},
            "supports_robot_position": {"type": "bool", "required": False},
            "supports_station_water": {"type": "bool", "required": False},
        },
    },

    # === MAINTENANCE COMPONENTS ===========================================

    "maintenance_components": {
        "type": "dict[str, dict]",
        "required": False,
        "description": (
            "Maintenance component catalog. Keyed by component ID. "
            "Defines which components the firmware exposes as replacement "
            "counters and their display metadata and interval configuration. "
            "Absent = maintenance view empty, degrades gracefully."
        ),
        "entry_fields": {
            "sensor_suffix": {
                "type": "str | null",
                "required": True,
                "description": (
                    "Suffix appended to '{object_id}_' to form the "
                    "replacement counter sensor entity ID. "
                    "Null when the component uses proxy_for."
                ),
            },
            "proxy_for": {
                "type": "str | null",
                "required": False,
                "description": (
                    "Component ID to use as the sensor source for this "
                    "component. Used when the firmware shares a counter "
                    "between components (e.g. swivel_wheel proxies filter)."
                ),
            },
            "default_interval_hours": {
                "type": "float",
                "required": True,
                "description": (
                    "Manufacturer guide recommendation. Never changes. "
                    "Reference anchor for the user's configured interval."
                ),
            },
            "max_interval_hours": {
                "type": "float",
                "required": True,
                "description": (
                    "Ceiling for user-configured interval override. "
                    "Set above default to allow light-use extension."
                ),
            },
            "label": {
                "type": "str",
                "required": True,
                "description": "Human-readable component name for display.",
            },
            "icon": {
                "type": "str",
                "required": True,
                "description": "MDI icon string.",
            },
        },
    },

    # === UPKEEP CATALOG ===================================================
    # Display data for the per-component upkeep guides shown in the card.
    # Pure strings — no logic. Replaced wholesale for a brand port.

    "upkeep_catalog": {
        "type": "dict",
        "required": False,
        "description": (
            "Per-model upkeep guide catalog. Display data only — pure strings, "
            "no logic. The framework reads model_names to label the maintenance "
            "view, looks up the device's model code in model_guide_families to "
            "resolve which guide family to show, then renders the guide entries "
            "from guide_library for each component. "
            "Absent = upkeep view falls back to component labels only with no "
            "step-by-step instructions."
        ),
        "fields": {
            "model_names": {
                "type": "dict[str, str]",
                "required": False,
                "description": (
                    "Maps device model code (as reported by the vacuum entity's "
                    "'detected_model' attribute) to a human-readable display name. "
                    "Example: {'T2351': 'Robovac X10 Pro Omni'}."
                ),
            },
            "model_guide_families": {
                "type": "dict[str, str]",
                "required": False,
                "description": (
                    "Maps device model code to a guide family key. Multiple "
                    "models can share one family when their upkeep instructions "
                    "are identical, keeping guide_library compact. "
                    "Example: {'T2351': 'x10_pro_omni', 'T2261': 'x8_series'}."
                ),
            },
            "guide_family_names": {
                "type": "dict[str, str]",
                "required": False,
                "description": (
                    "Maps guide family key to display name shown in the "
                    "upkeep guide header. "
                    "Example: {'x10_pro_omni': 'X10 Pro Omni'}."
                ),
            },
            "guide_library": {
                "type": "dict[str, dict[str, dict]]",
                "required": False,
                "description": (
                    "Two-level dict: family_key → component_key → guide entry. "
                    "Component keys must match maintenance_components keys "
                    "(filter, side_brush, rolling_brush, dust_bag, mop_pad, "
                    "sensor, etc.). Each guide entry has fields: "
                    "clean_frequency (str), replace_frequency (str | null), "
                    "steps (list[str]), notes (list[str]). "
                    "Absent component keys produce no card in the upkeep view."
                ),
            },
        },
    },

    # === WATER MODEL CONFIGS ==============================================
    # Hardware water-tank constants per model. Pure measurements — no logic.

    "water_model_configs": {
        "type": "dict[str, dict]",
        "required": False,
        "description": (
            "Per-model physical water-tank dimensions. Each entry maps a "
            "device model code to the measured hardware capacities. These "
            "are not calculated values — they must be measured on real "
            "hardware. The estimator reads these to convert tank-percent "
            "deltas into ml. "
            "Absent = water estimation falls back to flow-rate-only and "
            "cannot report actual tank-level deltas."
        ),
        "entry_fields": {
            "robot_internal_tank_ml": {
                "type": "float",
                "required": True,
                "description": (
                    "Capacity of the robot's onboard water reservoir in ml. "
                    "Used to convert wash-frequency intervals into volume."
                ),
            },
            "dock_clean_tank_capacity_ml": {
                "type": "float",
                "required": False,
                "description": (
                    "Capacity of the dock's clean-water tank in ml. "
                    "Omit for models with no dock clean tank (no mop station). "
                    "Used to convert station_clean_water_percent deltas into ml."
                ),
            },
            "dock_wash_overhead_ml_per_cycle": {
                "type": "float",
                "required": False,
                "description": (
                    "Measured water consumption per mop-wash cycle, in ml. "
                    "Subtracted from the total dock-water delta to isolate "
                    "the floor-mopping water from the post-job wash water. "
                    "Omit for models with no dock wash cycle."
                ),
            },
        },
    },
}
