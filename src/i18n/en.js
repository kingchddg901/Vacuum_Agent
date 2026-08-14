/**
 * ============================================================
 * I18N — English base catalog (source of truth)
 * ============================================================
 *
 * Every user-facing string key the card renders, in English. The reference for
 * translators and the fallback for all locales — a missing locale key falls back
 * to English; a missing English key renders the raw key (a visible miss).
 *
 * Conventions:
 *   - Keys are dot-namespaced by surface: `<view>.<name>`. Generic actions
 *     shared across surfaces live under `common.*` (one translation, reused).
 *   - Interpolation uses `{name}` placeholders, e.g. "{count} rooms selected".
 *   - `// plural` marks count-driven keys. Their VALUE is an OBJECT of CLDR
 *     forms ({ one, other }; English ships those two). At runtime translate()
 *     reads `vars.count` and picks the form via the language's Intl.PluralRules,
 *     so a locale supplies whatever its language needs (Russian one/few/many/
 *     other, etc.). `{count}` is the conventional count token. The one exception
 *     is `badge_runs_samples` (two independent counts) — a single-count selector
 *     can't inflect both nouns, so it stays a plain string (annotated inline).
 *   - A trailing `// <note>` after a key is a translator context note (the
 *     `// plural` flag may carry one too: `// plural; <note>`).
 *
 * Coverage: the whole card — every renderer, the standalone room-card, all
 * bindings, and the no-vacuum onboarding placeholder are localized, with the
 * plural mechanism live across all count-driven keys.
 *
 * ============================================================
 */

export const en = {
  // --- common ---
  // A5-AG-2. The glue between items when a backend ships a LIST param unjoined
  // (blocking rooms, cycle chains, inbound sources) so the CARD picks the
  // separator — joining server-side would bake an English list convention into
  // every locale. Include any trailing space the language needs; CJK typically
  // uses a full-width comma with no space.
  "common.list_separator": ", ",
  "common.cancel": "Cancel",
  "common.close": "Close",
  "common.percent_value": "{percent}%",  // A bare percentage. A KEY rather than string concat because the sign does not always trail the number — Turkish writes %42
  "common.seconds_short": "{seconds}s",  // A sub-minute duration. Only used below 30s, where the minutes formatter would round to '0 min' and read as 'no time at all'
  "common.service_failed": "Could not complete {service} — the vacuum may not have received it",  // Error toast when a card action fails to reach Home Assistant (network, unavailable
  // service, or a backend error). {service} is a raw "domain.service" identifier — do NOT
  // translate it. The second clause matters: the user must not assume the robot acted.
  "common.service_refused": "Could not complete this — {reason}",  // Error toast when a service call reaches Home Assistant and returns NORMALLY but
  // with a structured refusal ({success:false}/{started:false} + reason) — the backend understood
  // the request and declined it (e.g. a job already in progress). {reason} is the ALREADY-
  // TRANSLATED phrase from the service_reasons.* namespace below (showServiceRefusalToast
  // resolves the raw backend code to it before interpolating here) — a full sentence, not a
  // raw code. Distinct from common.service_failed (the call itself couldn't complete).
  "common.confirm": "Confirm",  // Confirm-button label on a card-native confirm dialog (proceed with the action)
  "common.delete": "Delete",
  "common.edit": "Edit",
  "common.no": "No",
  "common.ok": "OK",  // Acknowledge-button label on a card-native alert dialog
  "common.off": "Off",  // Toggle-button label = setting DISABLED (paired with common.on); not 'leave/away' or directional
  "common.on": "On",  // Toggle-button label = setting ENABLED (edge-mop/rules on); not 'turn on' verb or 'on' preposition
  "common.rename": "Rename",
  "common.reset": "Reset",
  "common.save": "Save",
  "common.saving": "Saving…",
  "common.yes": "Yes",

  // --- service_reasons (Q9 operational refusal codes — see core.js's showServiceRefusalToast,
  // which resolves a raw backend `reason` code to one of these before interpolating it into
  // common.service_refused above). One key per reason code job_control's start_selected_rooms /
  // start_zone_clean can actually return today; `unknown` is the forward-compat fallback for any
  // OTHER code the backend adds later without a matching frontend release — it still names the
  // raw code, in parens, so a refusal is never blank and never silently renders as success. ---
  "service_reasons.job_in_progress": "A cleaning job is already in progress.",
  "service_reasons.job_paused": "A tracked job is currently paused. Resume or cancel it before starting a new one.",
  "service_reasons.onboarding_required": "Some enabled rooms still need a floor type confirmed before cleaning can start.",
  "service_reasons.all_selected_rooms_blocked": "All selected rooms are currently blocked.",
  "service_reasons.vacuum_missing": "The vacuum entity is unavailable.",
  "service_reasons.map_mismatch": "This run was recorded on a different map. Switch to that map, then retry.",
  // A4-CUSTOM-2: custom segmentation mode is on but no layout is active, so there is
  // nowhere to store a room link or a companion anchor. The backend now refuses rather
  // than writing into a throwaway dict and reporting success.
  "service_reasons.no_active_custom_layout": "Pick or create a custom layout before saving this.",
  // A3-IMAGE--8: the uploaded image's dimensions could not be read, so the variant
  // is refused rather than stored with nulls that break every consumer downstream.
  "service_reasons.unreadable_image_dimensions": "That image's dimensions could not be read. Try re-exporting it as a PNG.",
  // --- theme service reason codes (CARD-9(2)/(3), RP-034's manager.py) — every {ok:false, reason}
  // code the theme library/draft/import services can return, resolved through the SAME
  // showServiceRefusalToast() path above (now centralized in _callThemeService, actions/theme.js). ---
  "service_reasons.theme_not_found": "That theme could not be found — it may have been deleted.",
  "service_reasons.empty_draft": "There are no unsaved changes to save.",
  "service_reasons.invalid_payload": "That import file isn't in a format this card understands.",
  "service_reasons.missing_theme": "That import file doesn't contain theme data.",
  "service_reasons.missing_name": "The imported theme needs a name.",
  "service_reasons.invalid_tokens": "The imported theme's token values aren't formatted correctly.",
  "service_reasons.invalid_colors": "The imported theme's color values aren't formatted correctly.",
  "service_reasons.invalid_alpha": "The imported theme's alpha values aren't formatted correctly.",
  "service_reasons.missing_vacuum": "No vacuum is selected for this card.",
  "service_reasons.empty_scope": "No floor types were selected to replace.",
  "service_reasons.no_active_theme": "This vacuum has no active theme to update.",
  "service_reasons.unknown": "This action was refused ({reason}).",  // {reason} is the RAW backend code — do NOT translate it (there is no sentence to translate; it's a forward-compat identifier, same convention as common.service_failed's {service}).

  // --- card_editor (Lovelace visual config editor: vacuum entity + per-card language override) ---
  "card_editor.vacuum_label": "Vacuum",  // editor field label: which vacuum entity this card controls
  "card_editor.pick_vacuum": "Select a vacuum…",  // editor placeholder prompting the user to choose the vacuum entity
  "card_editor.language_label": "Display language",  // editor field label: per-card UI language override (overrides the HA system language)
  "card_editor.language_auto": "Auto (follow Home Assistant)",  // language option: defer to the HA UI language (no override)
  "card_editor.language_hint": "Overrides the language for this card only.",  // editor hint: the override is scoped to this dashboard card

  // --- language (the header globe control: per-user display-language override, persisted across devices) ---
  "language.button_title": "Language",  // tooltip/aria-label on the header globe button that opens the language menu
  // ACCESSIBILITY typeface picker, inside the language menu. Translated at
  // creation even though the control is English-gated today — when a locale's
  // catalogue coverage is verified and enabled, the chrome must already be
  // there rather than appear in English on the day it is switched on.
  "font.heading": "Typeface",  // sub-heading over the font options in the language menu
  "font.default": "Default",   // font option: defer to the theme / Home Assistant font
  "font.opendyslexic": "OpenDyslexic",  // font option: PROPER NOUN — the typeface name, never translate it
  "language.heading": "Display language",  // heading at the top of the language dropdown menu
  "language.auto": "Auto (follow Home Assistant)",  // first menu row: defer to the HA system language (no override)
  "language.auto_draft_note": "{lang} is still a draft, so Auto shows English — pick it below to use it.",  // sub-note under the Auto row when the HA system language is a draft (gated to English); {lang} = that language's own name

  // --- vocab (adapter VOCABULARY values rendered via this.tVocab(field, value, label); keyed on the stable value, falls back to the backend English label for unkeyed values) ---
  "vocab.clean_mode.vacuum": "Vacuum",            // clean mode: suction only
  "vocab.clean_mode.mop": "Mop",                  // clean mode: mop only
  "vocab.clean_mode.vacuum_mop": "Vacuum and mop",// clean mode: both (code form)
  "vocab.clean_mode.vacuum_and_mop": "Vacuum and mop", // alias: stored profiles use the display-string form "Vacuum and mop" (slug vacuum_and_mop), not the vacuum_mop code
  "vocab.fan_speed.quiet": "Quiet",               // suction level (lowest)
  "vocab.fan_speed.gentle": "Gentle",             // suction level (Roborock app term)
  "vocab.fan_speed.balanced": "Balanced",         // suction level (Roborock app term)
  "vocab.fan_speed.standard": "Standard",         // suction level
  "vocab.fan_speed.boost": "Boost",               // suction level
  "vocab.fan_speed.turbo": "Turbo",               // suction level (Eufy app term; the value the device actually emits)
  "vocab.fan_speed.max": "Max",                   // suction level (highest)
  "vocab.water_level.off": "Off",                 // water level: no water
  "vocab.water_level.low": "Low",                 // water level
  "vocab.water_level.medium": "Medium",           // water level
  "vocab.water_level.high": "High",               // water level
  "vocab.clean_intensity.quick": "Quick",         // cleaning path / intensity
  "vocab.clean_intensity.narrow": "Narrow",       // cleaning path / intensity
  "vocab.clean_intensity.deep": "Deep",           // cleaning path / intensity
  "vocab.clean_intensity.normal": "Normal",       // cleaning path / intensity (manual-only)
  "vocab.clean_intensity.standard": "Standard",   // cleaning path / intensity (Eufy app term; the dominant stored value)

  // --- base_station (Base Station / dock: status, water, activity, controls) ---
  "base_station.action_available": "Action available",
  "base_station.action_dry_mop": "Dry Mop",  // dock button: start air-drying the mop pad (not 'dry-mopping' the floor)
  "base_station.action_empty_dust": "Empty Dust",  // dock button: empty the dust bin into the dock (Empty = verb)
  "base_station.action_stop_drying": "Stop Drying",  // dock button: stop the mop air-dry cycle
  "base_station.action_unavailable": "Action unavailable",
  "base_station.action_wash_mop": "Wash Mop",  // dock button: wash the mop pad at the dock (not 'mop with wash water')
  "base_station.activity_dry_start": "Dry Start",  // dock activity: mop air-drying cycle started, not a clean/run start
  "base_station.activity_dust_empty": "Dust Empty",  // dock activity event label: a dust-empty happened (noun pair, not 'dust is empty')
  "base_station.activity_mop_wash": "Mop Wash",  // dock activity event label: a mop-wash happened (reversed noun order)
  "base_station.activity_subtitle": "Last known dock service activity",
  "base_station.activity_title": "Recent Dock Activity",
  "base_station.dock_actions_subtitle": "Backend-gated dock controls",  // subtitle: dock controls shown/hidden per backend capability ('Backend-gated' = gated by support)
  "base_station.dock_actions_title": "Dock Actions",
  "pause_timeout.minutes_short": "{minutes} min",
  "base_station.no_activity_yet": "No activity yet",
  "pause_timeout.subtitle": "Default pause timeout used when a run is paused",
  "pause_timeout.title": "Pause Timeout",
  "base_station.recorded_count": { other: "{count} recorded" },  // plural; activity-card detail: count of recorded events of this kind, e.g. '5 recorded'
  "base_station.stat_after_job": "After Job",  // stat label: projected tank level remaining after the queued job
  "base_station.stat_dock_status": "Dock Status",
  "base_station.stat_docked": "Docked",  // stat label asking 'is the robot docked?' (value = Yes/No), not a status word
  "base_station.stat_job_use": "Job Use",  // stat label: clean-water this job is projected to use (ml)
  "base_station.stat_lifecycle": "Lifecycle",  // stat label: dock lifecycle state (drying/washing/idle), not product lifespan
  "base_station.stat_station_water": "Station Water",
  "base_station.stat_tank_now": "Tank Now",  // stat label: clean-water tank volume right now (water tank, in ml)
  "base_station.stat_task": "Task",  // stat label: robot's current task status string from the device
  "base_station.state_ready": "Ready",
  "base_station.state_running": "Running...",  // dock-action button state while the action is sending, not robot 'cleaning'
  "base_station.state_unavailable": "Unavailable",
  "base_station.station_status_subtitle": "Dock, lifecycle, and robot task state",
  "base_station.station_status_title": "Station Status",
  "base_station.unknown": "Unknown",
  "base_station.updated_prefix": "Updated {timestamp}",
  "base_station.water_subtitle": "Current dock water plus projected post-job tank level",
  "base_station.water_title": "Water",  // Water panel section heading (dock water tank levels), not a per-room water setting
  "bind_pause_timeout.auto_cancel_disabled": "Auto-cancel disabled",
  "bind_pause_timeout.could_not_save": "Could not save pause timeout",
  "bind_base_station.dock_action_failed": "Dock action failed ({action})",
  "bind_base_station.dock_action_sent": "Dock action sent",
  "bind_base_station.dust_empty_sent": "Dust empty sent",
  "bind_base_station.mop_dry_sent": "Mop dry sent",
  "bind_base_station.mop_wash_sent": "Mop wash sent",
  "bind_pause_timeout.set": "Pause timeout set to {minutes} min",
  "bind_base_station.stop_drying_sent": "Stop drying sent",
  "bind_external_jobs.confirm_failed_detail": "Confirm failed: {detail}",
  "bind_external_jobs.confirm_failed_retry": "Confirm failed — please try again.",
  "bind_external_jobs.pick_room_every_panel": "Pick a room for every panel before confirming.",  // 'panel' = each per-room assignment card in the review wizard; every one needs a room before Confirm
  "bind_external_jobs.resegment_failed_detail": "Re-segment failed: {detail}",  // 're-segment' = re-split the captured run into rooms; term of art, {detail}=error text
  "bind_external_jobs.resegment_failed_retry": "Re-segment failed — please try again.",
  "bind_maintenance.could_not_reset": "Could not reset {label}",
  "bind_maintenance.could_not_save_interval": "Could not save interval",
  "bind_maintenance.interval_saved": "Interval saved ({value}h)",  // {value} is a number of HOURS; the trailing 'h' is the hours unit (maintenance interval)
  "bind_maintenance.maintenance_reset_saved": "Maintenance reset saved",
  "bind_maintenance.replacement_reset_sent": "Replacement reset sent",
  "bind_map.analysis_failed": "Analysis failed",
  "bind_map.could_not_delete_variant_image": "Could not delete {variant} image",  // {variant}=capitalized map-image variant name (Dark/Light/Default); keep token
  "bind_map.could_not_prepare_image": "Could not prepare the image for upload",
  "bind_map.could_not_save_map_image": "Couldn't save the map image — try right-click → Save image on the map.",
  "bind_map.delete_failed": "Delete failed",
  "bind_map.map_image_still_loading": "Map image still loading — wait for the live map to appear, then save again (or upload a backdrop).",  // 'backdrop' = the uploaded base map image you draw rooms over; not a theme bg
  "bind_map.no_active_live_map_layout": "No active Live-map layout found",  // 'Live-map layout' = the custom layout drawn over the live camera map; term of art
  "bind_map.no_active_map": "No active map found",
  "bind_map.save_failed": "Save failed",
  "bind_map.save_failed_reason": "Save failed: {reason}",
  "bind_map.variant_image_deleted": "{variant} image deleted",  // {variant}=map-image variant name (Dark/Light/Default), capitalized at call site
  "bind_map.image_too_large": "Image too large even after resizing — please pick a smaller image.",  // map-image upload rejected: payload still over HA's 4 MiB WS-frame limit after client downscale. Feeds an escapeHtml sink → keyed via tRaw
  "bind_map.upload_failed_generic": "Upload failed",  // generic fallback when a map-image upload throws with no usable message
  // A6-AGX-2 Half B: shown IN the room-editor modal when update_room_fields refuses.
  // Generic fallback only — the backend normally returns a specific reason/issues list,
  // which the binding prefers over this.
  "bind_room_editor.save_rejected": "That change was rejected and has not been saved.",
  // Confirm shown when the user releases the dock room. Releasing it CLEARS the
  // whole access graph — the tree is rooted at the dock. {count} = how many rooms
  // currently hold access links.
  "bind_room_access.release_dock_clears_graph": {
    "one": "Releasing the dock room clears the access graph for this map, including the links on 1 room. Basic cleaning still works. Continue?",
    "other": "Releasing the dock room clears the access graph for this map, including the links on {count} rooms. Basic cleaning still works. Continue?"
  },
  "bind_room_access.backend_rejected_graph": "The backend rejected this room access graph.",  // 'graph' = the room-access dependency graph (which room unlocks which); not a chart
  "bind_room_access.failed_to_save": "Failed to save room access. Check Home Assistant logs for details.",
  "bind_room_editor.choose_custom_profile_key": "Choose a custom profile key:\n\n{choiceText}",  // window.prompt; user types a profile KEY (backend id), {choiceText}=newline list of 'name (label)'
  "bind_room_editor.confirm_delete_profile": "Delete {label}? This cannot be undone.",
  "bind_room_editor.confirm_overwrite_profile": "Overwrite {target} with this room's current settings?",
  "bind_room_editor.default_custom_profile_label": "Custom Room Profile",  // default display name suggested when saving a room's settings as a new reusable profile
  "bind_room_editor.failed_delete_profile": "Failed to delete room profile.",
  "bind_room_editor.profile_already_removed": "That profile was already removed.",  // info toast: the delete found the profile already gone from the backend; the card reconciled (refreshed) rather than erroring
  "bind_room_editor.failed_overwrite_profile": "Failed to overwrite room profile.",
  "bind_room_editor.failed_rename_profile": "Failed to rename room profile.",
  "bind_room_editor.failed_save_profile": "Failed to save room profile.",
  "bind_room_editor.label_required": "A room profile label is required.",
  "bind_room_editor.rename_key_prompt": "Optional: enter a new backend profile key.",  // prompt for the backend profile KEY (internal id), distinct from the display label; keep 'key' as identifier sense
  "bind_room_editor.rename_label_prompt": "Enter the new display label for this room profile:",  // prompt for the human-readable display LABEL of a saved room profile (vs its backend key)
  "bind_room_editor.save_new_profile_prompt": "Save current room settings as a new profile. Enter a display label:",
  "bind_room_rules.backend_rejected_rule": "The backend rejected this rule.",
  "bind_room_rules.failed_to_save_rule": "Failed to save rule. Check Home Assistant logs.",
  "bind_rooms.cancel_sent": "Cancel sent — returning to dock",
  "bind_rooms.chip_title": "Click for settings - Double-click for estimate - Hold to remove from queue",
  "bind_rooms.could_not_retry_missed": "Could not retry missed rooms",
  "bind_rooms.locate_sent": "Locate sent — listen for the chirp",
  "bind_rooms.queue_cleared": "Queue cleared",
  "bind_rooms.requeued_missed": { one: "Re-queued {count} missed room", other: "Re-queued {count} missed rooms" },  // plural
  "bind_run_profiles.break_needs_group": "Add a room group first — a charge or wait needs one before and after it.",
  "bind_run_profiles.capture_no_rooms": "Enable some rooms first, then add them as a group.",
  "bind_run_profiles.confirm_delete": "Delete run profile \"{name}\"?",
  "bind_run_profiles.enter_name": "Enter a name for the run profile.",
  "bind_run_profiles.steps_need_group": "A run needs at least one group of rooms to clean.",
  "bind_run_profiles.unable_apply": "Unable to apply run profile.",
  "bind_run_profiles.unable_delete": "Unable to delete run profile.",
  "bind_run_profiles.unable_overwrite": "Unable to overwrite run profile.",
  "bind_run_profiles.unable_run": "Unable to run run profile.",
  "bind_run_profiles.unable_save": "Unable to save run profile.",
  "bind_saved_zones.bad_geometry": "This zone has no valid area to clean.",
  "bind_saved_zones.clean_failed": "Couldn't clean the selected zones — check the count and size.",
  "bind_saved_zones.cleaning_selected": { one: "Cleaning {count} zone…", other: "Cleaning {count} zones…" },
  "bind_saved_zones.confirm_delete": "Delete saved zone \"{name}\"?",
  "bind_saved_zones.map_not_active": "That zone belongs to a different map — switch to its map first.",
  "bind_saved_zones.name_prompt": "Name this zone (e.g. \"the couch\"):",  // prompt after drawing a box to save
  "bind_saved_zones.no_zones": "No zones to clean.",
  "bind_saved_zones.nothing_drawn": "Draw a box on the map first.",  // save pressed with no box drawn
  "bind_saved_zones.refile_failed": "Couldn't move the zone.",  // set_saved_zone_room failed
  "bind_saved_zones.rename_failed": "Couldn't rename the zone.",  // rename_saved_zone failed
  "bind_saved_zones.rename_prompt": "New name for this zone:",  // prompt when renaming a zone
  "bind_saved_zones.renamed": "Renamed to \"{name}\".",  // rename succeeded
  "bind_saved_zones.save_failed": "Couldn't save the zone.",  // create_saved_zone failed
  "bind_saved_zones.saved": "Saved \"{name}\".",  // zone created successfully
  "bind_saved_zones.unable_delete": "Unable to delete the saved zone.",
  "bind_saved_zones.zone_not_found": "That saved zone no longer exists.",
  "bind_setup.failed_add_vacuum": "Failed to add vacuum: {error}",
  "bind_setup.failed_delete_map": "Failed to delete map: {error}",
  "bind_setup.failed_delete_map_plain": "Failed to delete map.",
  "bind_setup.failed_force_remove_room": "Failed to force-remove room: {error}",
  "bind_setup.failed_import_map": "Failed to import map: {error}",
  "bind_setup.failed_load_rooms": "Failed to load rooms: {error}",
  "bind_setup.failed_reconcile_dismiss": "Failed to dismiss reconciliation: {error}",
  "bind_setup.failed_reconcile_update": "Failed to update saved rooms: {error}",
  "bind_setup.failed_reject_room": "Failed to reject room: {error}",
  "bind_setup.failed_rename_panel": "Failed to rename panel: {error}",
  "bind_setup.failed_save_rooms": "Failed to save rooms: {error}",
  "bind_setup.failed_set_map_camera": "Failed to set live map camera: {error}",
  "bind_setup.map_camera_cleared": "Live map camera cleared",
  "bind_setup.map_camera_set": "Live map camera set",
  "bind_setup.map_delete_failed": "Map delete failed",
  "bind_setup.map_deleted": "Map deleted",
  "bind_setup.panel_renamed": "Panel renamed — refresh to update the sidebar",
  "bind_setup.reconciliation_dismissed": "Dismissed — the same review can resurface if the map changes again",
  "bind_theme.confirm_overwrite_theme": "Overwrite {target} with your unsaved changes? {target}'s other settings will stay as they are.",  // CARD-9(2)/Q7 (RP-034): overwrite merges the draft onto the TARGET's own stored palette — the target is state.activeThemeId itself, so this direction is correct even though target===active in the only call site (bindings/theme.js's save-theme handler).
  "bind_theme.copied": "Copied!",
  "bind_theme.copy": "Copy",
  "bind_theme.delete_theme_confirm": "Delete theme \"{themeId}\"?",
  "bind_theme.discard_draft_confirm": "Discard your unsaved theme edits?",
  "bind_theme.enter_new_theme_name": "Enter a name for your new theme:",
  "bind_theme.failed_export_theme": "Failed to export theme: {error}",
  "bind_theme.failed_import_file": "Failed to import \"{fileName}\": {error}",
  "bind_theme.import_failed": "Import failed: {reason}.",
  "bind_theme.import_rejected_keys": { one: "Imported, but {count} setting wasn't recognised and was skipped: {keys}", other: "Imported, but {count} settings weren't recognised and were skipped: {keys}" },  // plural; {keys}=joined, escaped list of rejected non-"--evcc-"-prefixed key names dropped from a partial import (both the paste-JSON and Upload full-import paths, RP-034's import_theme "rejected" field)
  "bind_theme.invalid_json": "That isn't valid JSON — check the pasted text.",
  "bind_theme.no_active_theme_download": "No active theme to download.",
  "bind_theme.no_active_theme_export": "No active theme to export.",
  "bind_theme.no_customised_floor_settings": "This theme has no customised \"{type}\" floor settings to export. Adjust and Save the {type} tokens first.",  // {type}=floor-material name (marble etc.); 'floor settings'=that material's theme tokens, not a storey
  "bind_theme.no_recognised_floor_types": "{sourceLabel} has no floor types this version recognises",  // 'floor types' = floor-MATERIAL theme scopes (marble/wood), not building storeys
  "bind_theme.paste_theme_first": "Paste a theme export first.",
  "bind_theme.pick_floor_type_export": "Pick a floor type to export.",  // 'floor type' = floor-material theme scope (marble/wood) to export, not a building storey
  "bind_theme.pick_preset_apply": "Pick a preset to apply.",
  "bind_theme.pasted_source_label": "the pasted theme",  // sourceLabel for a SCOPED import arriving via the paste-JSON modal (Upload passes the quoted file name instead); lowercase 'the' = embedded mid-sentence in another string
  "bind_theme.preset_source_label": "the {name} preset",  // {name}=marble preset name; lowercase 'the' = embedded mid-sentence in another string
  "bind_theme.replace_floor_types_confirm": "\n\nThis overwrites those types. Continue?",  // appended confirm fragment after the intro/skipped lines; 'those types'=floor materials
  "bind_theme.replace_floor_types_intro": "Replace these floor types on the active theme:\n  {known}",  // {known}=list of floor-MATERIAL theme scopes being overwritten; intro line, more text appended
  "bind_theme.replace_floor_types_skipped": "\n\nSkipped — unsupported in this version:\n  {unknown}",  // {unknown}=unsupported floor-material scope names; appended fragment, leading newlines matter
  "bind_theme.replaced_floor_types": "Replaced {known} from {sourceLabel}.",  // {known}=floor-material scopes applied; {sourceLabel}=file name or preset label
  "bind_theme.select_ctrl_c": "Select + Ctrl+C",  // copy-fallback hint; 'Ctrl+C' is a keyboard shortcut, do NOT translate it
  "bind_theme.send_failed_see_logs": "Failed — see logs",  // button state after a failed 'Send to HA'; HA=Home Assistant, keep verbatim
  "bind_theme.send_to_ha": "Send to HA",  // 'HA' = Home Assistant; product name, keep verbatim (sends theme export to HA)
  "bind_theme.sending": "Sending…",
  "bind_theme.sent_to_ha": "Sent to HA ✓",  // 'HA' = Home Assistant; keep verbatim. ✓ = success checkmark, keep
  "bind_theme.skipped_suffix": " Skipped: {unknown}.",  // appended fragment; {unknown}=skipped floor-material scope names; leading space intentional
  "bind_theme.theme_imported_from": "Theme imported from {fileName}.",
  "bind_theme.unsupported_suffix": " (unsupported: {unknown}).",  // appended fragment; {unknown}=unsupported floor-material scope names; leading space intentional
  "bind_theme.values_clamped_suffix": " {corrected} value(s) clamped to range.",  // appended fragment; {corrected}=count of out-of-range theme values forced into range; leading space intentional

  // --- external_jobs (External Jobs review: app-started run capture wizard) ---
  "external_jobs.back": "Back",
  "external_jobs.blocked": { one: "{count} room doesn't match the picked area — re-pick, or keep anyway.", other: "{count} rooms don't match the picked area — re-pick, or keep anyway." },  // plural
  "external_jobs.capped_message": "Capped to the detectable room count.",  // Shown when the room count was limited to the max number of rooms detectable.
  "external_jobs.card_rooms": { one: "~{count} room", other: "~{count} rooms" },  // plural
  "external_jobs.card_segments": { one: "{count} segment", other: "{count} segments" },  // plural
  "external_jobs.clean_mode_unknown": "?",  // '?' placeholder shown when a segment's clean mode wasn't captured
  "external_jobs.confirm": "Confirm",
  "external_jobs.count_hint": "set the room count, or split / merge below",
  "external_jobs.detected_rooms": { one: "Detected <strong>{count}</strong> room. Merge any over-split before continuing.", other: "Detected <strong>{count}</strong> rooms. Merge any over-split before continuing." },  // plural; 'over-split' = cut into more segments than real rooms; merge any extras. {count} bold.; 'over-split' = the run was cut into more segments than real rooms; user merges extras.
  "external_jobs.discard": "Discard",
  "external_jobs.edge_mop": "Edge mop?",  // field label asking whether the run used edge-mopping (Edge mop?)
  "external_jobs.edge_mop_hint": "not detected — please set",
  "external_jobs.empty": "No app-started runs awaiting review. Start a clean from {appPhrase} and the run will appear here to confirm which rooms it cleaned.",  // {appPhrase} is a sentence fragment ('the Eufy app' / 'your robot's app'), inserted mid-text.
  "external_jobs.empty_app_branded": "the {brand} app",  // Fragment inserted into 'empty' as {appPhrase}: 'the {brand} app' (e.g. the Eufy app).
  "external_jobs.empty_app_generic": "your robot's app",  // Fragment inserted into 'empty' as {appPhrase} when brand unknown: 'your robot's app'.
  "external_jobs.first_room": "First room",  // marks the first segment (no merge-up control); start of the run
  "external_jobs.keep_anyway": "Keep anyway",
  "external_jobs.merge_up": "Merge up",  // Button. Merges THIS room INTO the one above it (directional term of art).
  "external_jobs.merged_label": "merged",  // boundary toggle state = this cut is merged into the room above
  "external_jobs.merged_label_uncertain": "merged · uncertain",  // boundary state: merged, but the detected cut was low-confidence
  "external_jobs.mode": "Mode",  // field label above clean-mode chips (vacuum/mop/both); the cleaning mode, NOT theme appearance mode
  "external_jobs.mode_mop": "Mop",  // clean-mode chip value: mop-only
  "external_jobs.mode_vacuum": "Vacuum",  // clean-mode chip value: vacuum-only (no mopping)
  "external_jobs.mode_vacuum_mop": "Vac & Mop",  // clean-mode chip value: vacuum + mop together (short 'Vac & Mop')
  "external_jobs.next_name_rooms": "Next: name rooms",
  "external_jobs.passes": "Passes",  // field label for cleaning-pass count chips (1x / 2x)
  "external_jobs.pick_another_room": "… pick another room",
  "external_jobs.review": "Review",  // button on a pending app-started run that opens the review wizard
  "external_jobs.room_n": "Room {n}",
  "external_jobs.rooms_label": "Rooms",  // label for the room-COUNT stepper (how many rooms); a number, not a list of rooms
  "external_jobs.seg_n": "seg {n}",  // 'seg {n}' = abbreviated segment label (legacy step 1); n is the detected-segment order
  "external_jobs.segments_merged": { other: "{count} segments merged" },  // plural
  "external_jobs.setting_cleaning_path": "Cleaning Path",  // clean-intensity setting row (maps to clean_intensity), labelled 'Cleaning Path'
  "external_jobs.setting_suction": "Suction",  // per-room suction/fan-speed LEVEL setting row
  "external_jobs.setting_water": "Water",  // per-room mop water-LEVEL setting row (low/med/high), only shown for mop modes
  "external_jobs.split_here": "Split here",  // Button: reopens a detected cut, splitting this room into a new room at this point.
  "external_jobs.split_here_uncertain": "Split here · uncertain",  // Same as split_here but the detected cut was low-confidence; 'uncertain' = low confidence.
  "external_jobs.split_label": "split here",  // boundary toggle state = this cut is split into its own room
  "external_jobs.split_label_uncertain": "split here · uncertain",  // boundary state: split, but the detected cut was low-confidence
  "external_jobs.subtab_external": "External Jobs",
  "external_jobs.subtab_external_count": "External Jobs ({count})",
  "external_jobs.subtab_history": "Learning History",
  "external_jobs.unknown_time": "Unknown time",
  // REV-2. The shortlist's top entry is a GUESS the backend is not certain of —
  // it ships a shortlist precisely because it does not know. It is now SHOWN but
  // not pre-selected, so a wrong guess cannot be confirmed by reflex and then
  // learned from.
  "external_jobs.suggested_tag": "suggested",  // appended to the guessed room chip; lowercase, reads as an aside not a label
  "external_jobs.suggested_hint": "Our best guess from where the robot went. Tap to accept it, or pick another room.",
  "external_jobs.pick_required": "pick one",  // inline prompt beside the room label while nothing is chosen
  "external_jobs.rooms_unassigned": { one: "1 room still needs picking", other: "{count} rooms still need picking" },
  "external_jobs.which_room": "Which room?",
  "external_jobs.wizard_phase_count": "how many rooms?",
  "external_jobs.wizard_phase_name": "name each room",
  "external_jobs.wizard_step_of": "Step {step} of 2 — {phase}",
  "external_jobs.wizard_title": "Review app-started run",  // Modal title. 'app-started run' = a clean started from the vendor app, not from this card.

  // --- learning (Learning Review surface: live progress, estimates, completion, incomplete-run recovery) ---
  "learning.all_rooms_complete": "All rooms complete",
  "learning.battery_finish_rooms": "May need to recharge to finish remaining rooms",  // live warning: may recharge before finishing remaining rooms
  "learning.battery_mid_job": "May need to recharge mid-job",  // pre-job warning: battery may need a recharge partway through
  "learning.battery_recharged": "Recharge occurred during job",  // post-job note: a recharge actually happened during the run
  "learning.charging_delta": "{delta}% to go",  // live charge banner: percentage points still to charge (shrinks toward target)
  "learning.charging_from": "from {from}%",  // appended to the live charge banner: battery level when charging began
  "learning.charging_to": "Charging to {target}%",  // live charge-phase banner when no ETA is available yet
  "learning.charging_to_eta": "Charging to {target}% · ~{eta} left",  // live charge-phase banner with a learned ETA
  "learning.waiting": "Waiting · ~{remaining} left",  // live wait-phase countdown banner (time-based hold)
  "learning.cleaning_zone": "Cleaning zone: {names}",  // live zone-phase banner when no ETA is available yet
  "learning.cleaning_zone_eta": "Cleaning zone: {names} · ~{eta} left",  // live zone-phase banner with a learned/area ETA
  "learning.chip_mop_only": { one: "{count} mop-only room", other: "{count} mop-only rooms" },  // plural
  "learning.chip_vacuum_mop": { one: "{count} vacuum + mop room", other: "{count} vacuum + mop rooms" },  // plural
  "learning.chip_vacuum_only": { one: "{count} vacuum-only room", other: "{count} vacuum-only rooms" },  // plural
  "learning.chip_wash_cycle": { one: "{count} wash cycle", other: "{count} wash cycles" },  // plural
  "learning.chip_water": "~{ml} water",  // Chip '~{ml} water'; {ml} is a milliliter water-use string already incl. its unit, ~ = approx
  "learning.cleaning_complete": "Cleaning Complete",
  "learning.cleaning_room": "Cleaning {room}",
  "learning.confidence_high": "High",  // learning-confidence tier (High/Med/Low reliability), NOT water/suction High
  "learning.confidence_high_job": "High confidence",  // job-level confidence badge: 'High confidence' (whole-run estimate)
  "learning.confidence_job_suffix": "{label} confidence",  // job confidence badge for unknown tier: '{label} confidence'
  "learning.confidence_low": "Low",  // learning-confidence tier (estimate reliability), NOT water-level Low
  "learning.confidence_low_job": "Low confidence",  // job-level confidence badge: 'Low confidence' (whole-run estimate)
  "learning.confidence_medium": "Medium",  // learning-confidence tier (estimate reliability), NOT water-level Medium
  "learning.confidence_medium_job": "Medium confidence",  // job-level confidence badge: 'Medium confidence' (whole-run estimate)
  "learning.dismiss": "Dismiss",
  "learning.dismiss_aria": "Dismiss",
  "learning.done_at": "Done at {time}",  // projected per-room finish clock time: 'Done at {time}'
  "learning.done_by": "done by {time}",  // projected whole-job finish clock time: 'done by {time}'
  "learning.estimate_queue_first": "Queue rooms first to see an estimate",
  "learning.estimate_unavailable_message": "Estimate unavailable.",
  "learning.estimate_unavailable_title": "Estimate unavailable",
  "learning.estimated_job_time": "Estimated Job Time",
  // EST-PHASE-1: shown INSTEAD of "Queue rooms first" while a stepped run is in
  // flight — that copy tells the user to act on a run that is proceeding fine.
  // {step}/{total} count the LIVE-QUEUE CHIPS, which expand a room group into one
  // chip per room, so the numbers match the row directly above rather than the
  // backend's phase count.
  "learning.phase_context_title": "Currently on step {step} of {total}",
  "learning.phase_context_next": "Next: {step}",  // {step} is an already-rendered step description (room name, 'Wait 2 min', a zone name)
  "learning.finished_at": "Finished at {time}",
  "learning.hours_minutes": "{hours}h {minutes}m",  // Duration format '{hours}h {minutes}m'; h/m = hour/minute unit abbrevs, localize per language
  "learning.hours_only": "{hours}h",  // Duration '{hours}h'; h = hours unit abbreviation, localize if your language differs
  "learning.incomplete_title": { one: "Last run {outcome} — 1 room missed", other: "Last run {outcome} — {count} rooms missed" },  // plural
  "learning.run_incomplete_toast": { one: "Run incomplete — 1 room missed. Open Rooms to retry.", other: "Run incomplete — {count} rooms missed. Open Rooms to retry." },  // plural. Toast fired when a
  // run ends with rooms uncleaned. Was hardcoded English in the controller, so it was invisible to
  // check:i18n and untranslated in all 18 locales.
  "learning.job_will_use": "Job will use",  // water row: clean water this job is projected to consume
  "learning.learning_active": "Learning active",  // live banner title before first room update; system is recording data
  "learning.live_progress": "Live Progress",
  "learning.milliliters": "{ml} ml",
  "learning.minutes_left": "~{minutes} left",  // live ETA remainder on current room: '~{minutes} left'
  "learning.minutes_only": "{minutes} min",  // whole-minute duration '{minutes} min' (under 1h); distinct from minutes_short
  "learning.minutes_short": "{value} min",  // duration formatter, fractional min e.g. '3.5 min'; {value}, distinct from minutes_only
  "learning.mop_wash_label": { one: "{total} ({count} cycle × {per} every {interval})", other: "{total} ({count} cycles × {per} every {interval})" },  // plural
  "learning.mop_wash_label_none": "0 min (no cycles scheduled)",  // Overhead value when no mop-wash cycles scheduled; 'cycles' = dock mop-wash cycles
  "learning.next_room": "Next room",
  "learning.note_intensity_mismatch": "estimated from different intensity",  // per-room note: estimate learned at a different clean intensity/profile
  "learning.note_no_data": "No data yet",  // per-room note: no learned samples yet, using fallback estimate
  "learning.note_runs_to_reliable": { one: "{count} run to reliable", other: "{count} runs to reliable" },  // plural; per-room note: N more runs until estimate is 'reliable' (high confidence); per-room note: N more runs until estimate reaches 'reliable'
  "learning.outcome_cancelled": "cancelled",  // incomplete-run cause, lowercase mid-sentence: 'Last run cancelled — …'
  "learning.outcome_failed": "failed",
  "learning.outcome_interrupted": "interrupted",  // incomplete-run cause, lowercase mid-sentence (e.g. power/connection loss)
  "learning.overhead_breakdown": "Overhead breakdown",  // Expander heading. OVERHEAD = time or resources (e.g. water) spent on necessary SUPPORTING activity, not direct floor cleaning: transitions, docking, startup, recovery, mop washing, dust emptying, mid-job recharge, and dock water not applied to the floor. NOT financial overhead. Translate in that operational sense; keep as a loanword where idiomatic.
  "learning.overhead_dust_empty": "Dust empty",  // time-overhead segment: dock auto-empty minutes
  "learning.overhead_mop_wash": "Mop wash",  // time-overhead segment: dock mop-wash minutes
  "learning.overhead_recharge": "Recharge",  // time-overhead segment: mid-job recharge minutes
  "learning.overhead_return": "Return to dock",  // time-overhead segment: final return-to-dock minutes
  "learning.overhead_startup": "Startup",  // time-overhead segment: robot startup/spin-up minutes
  "learning.overhead_transitions": "Transitions",  // time-overhead segment: travel between rooms
  "learning.process_pending_runs": "Process pending runs",  // Button: reprocess the backlog of runs collected while processing was paused. Verb 'Process'
  "learning.processing_pending_fresh": { one: "Not computed yet · 1 run pending", other: "Not computed yet · {count} runs pending" },  // plural; status when processing is paused and NO estimate has ever been computed
  "learning.processing_pending_stale": { one: "1 new run pending", other: "{count} new runs pending" },  // plural; status when processing is paused but a prior estimate still stands; N runs await folding in
  "learning.processing_toggle": "Process runs automatically",  // Toggle label: on = fold each finished run into learning immediately; off = collect only (lower CPU on weak hardware)
  "learning.queue_missed_rooms": "Queue missed rooms",  // Imperative button: re-add the rooms a run skipped to the clean queue ('Queue' is the verb)
  "learning.returning_to_dock": "Returning to dock",
  "learning.robot_stuck": "Robot may be stuck in current room",  // stall warning: robot may be stuck in the room it's cleaning
  "learning.room_skipped": "Skipped",  // Live-progress marker for a room the robot passed over mid-run. Shown INSTEAD of
  // an ETA — a time for a room that will not be cleaned is a false promise.
  "learning.room_fallback": "Room {id}",
  "learning.stall_detail": "({elapsed} elapsed)",
  "learning.stall_detail_expected": "({elapsed} elapsed, expected {expected})",
  "learning.stat_actual": "Actual",  // post-job stat: actual elapsed run time (vs Predicted)
  "learning.stat_delta": "Delta",  // post-job stat: signed +/- diff between actual and predicted time
  "learning.stat_predicted": "Predicted",  // post-job stat: predicted run time (vs Actual)
  "learning.stat_rooms": "Rooms",  // post-job stat: count of rooms completed this run
  "learning.stats_stale": "Estimates may be outdated",  // warning: learned estimates may be outdated (stats not rebuilt recently)
  "learning.stats_stale_with_time": "Estimates may be outdated (last rebuilt {time})",
  "learning.tank_after_run": "Tank after run",  // water section: projected clean-water tank level AFTER the run
  "learning.tank_now": "Tank now",  // water section: clean-water tank level BEFORE the run starts
  "learning.unknown": "Unknown",
  "learning.waiting_next_room": "Waiting for next room update",
  "learning.water_estimate": "Water estimate",

  // --- maintenance (Upkeep tab: items, due dates, consumable status, reset) ---
  "maintenance.attention_empty": "Everything currently looks healthy.",
  "maintenance.attention_subtitle_none": "No maintenance or replacement items currently need attention",
  "maintenance.attention_subtitle_some": "Items currently flagged for service or replacement attention",
  "maintenance.attention_title": "Needs Attention",
  "maintenance.begin_reset_title_device": "Send the reset command to the device for this replacement item.",
  "maintenance.begin_reset_title_integration": "Reset this tracked maintenance interval and refresh the dashboard snapshot.",
  "maintenance.category_maintenance": "Maintenance",  // item-category label prefix in attention list: integration-tracked interval item
  "maintenance.category_replacement": "Replacement",  // item-category label prefix: upstream consumable/replacement part
  "maintenance.confirm_reset": "Confirm Reset",
  "maintenance.dock_fw": "Dock fw {version}",  // 'fw' = firmware abbreviation; {version} is the dock's firmware version string. Keep terse.
  "maintenance.due_in_days": { one: "Due in ~{count} day", other: "Due in ~{count} days" },  // plural
  "maintenance.due_in_months": { other: "Due in ~{count} months" },  // plural
  "maintenance.due_in_weeks": { other: "Due in ~{count} weeks" },  // plural
  "maintenance.due_overdue": "Overdue",
  "maintenance.due_today": "Due today",
  "maintenance.due_tomorrow": "Due tomorrow",
  "maintenance.hours": { one: "{value} hour", other: "{value} hours" },  // plural; run-hours label; {value} is preformatted, count drives one/other
  "maintenance.hours_remaining": "{hours} remaining",
  "maintenance.interval_default_button": "Default",  // button: restore manufacturer default interval value
  "maintenance.interval_default_hint": "Default {hours}h",  // 'Default {hours}h' — trailing 'h' = hours abbreviation; the manufacturer-default service interval.
  "maintenance.interval_default_title": "Restore manufacturer default ({hours}h)",
  "maintenance.interval_label": "Interval",  // Lone 'Interval' = the service-interval duration (in hours) before maintenance is due; not a generic time interval.
  "maintenance.interval_max_hint": "Max {hours}h",  // 'Max {hours}h' — 'h' = hours abbreviation; the maximum allowed service interval.
  "maintenance.interval_unit": "hours",  // unit suffix after a number-of-hours interval input
  "maintenance.items_empty_maintenance": "No maintenance items reported.",
  "maintenance.items_empty_replacements": "No replacement items reported.",
  "maintenance.items_subtitle": "Switch between maintenance intervals and replacement items",
  "maintenance.items_title": "Items",
  "maintenance.left_of": "{remaining} left of {total}",  // '{remaining} left of {total}' — both are formatted hour strings (life hours), e.g. '5 hours left of 150 hours'.
  "maintenance.ml_remaining": "~{ml} ml remaining",
  "maintenance.modal_fallback_name": "Item details",
  "maintenance.notes_label": "Notes",  // section heading for guide notes/cautions in the item modal
  "maintenance.overview_subtitle": "Backend maintenance snapshot",
  "maintenance.overview_title": "Maintenance Overview",
  "maintenance.percent_remaining": "{percent}% remaining",
  "maintenance.priority_normal": "Normal",  // highest-priority stat fallback = Normal (no item needs urgent attention)
  "maintenance.replacement_overview_subtitle": "Replacement inventory and lifecycle snapshot",
  "maintenance.replacement_overview_title": "Replacement Overview",
  "maintenance.reset_confirm_device": "This will send the reset command to the device for {name}.",
  "maintenance.reset_confirm_integration": "This will reset the tracked maintenance interval for {name}.",
  "maintenance.resetting": "Resetting...",
  "maintenance.stat_attention": "Attention",  // stat: count of items flagged needing attention
  "maintenance.stat_cleans": "Cleans",  // lifetime stat: total number of clean cycles run by the device
  "maintenance.stat_healthy": "Healthy",  // stat: count of replacement items currently in healthy state
  "maintenance.stat_items": "Items",
  "maintenance.stat_priority": "Priority",  // Stat cell label; value is the highest-priority item status (e.g. Normal/Warning), i.e. urgency, not sort order.
  "maintenance.stat_status": "Status",  // stat cell label whose value is Tracked/Empty (replacements group state)
  "maintenance.stat_total_cleaned": "Total cleaned",  // Lifetime stat label; value is total floor AREA cleaned in m² (not a count of cleans or 'cleaned' state).
  "maintenance.stat_total_time": "Total time",  // Lifetime stat label; value is total cleaning TIME in hours over the device's life.
  "maintenance.stat_water": "Water",  // overview stat cell: dock station water status value
  "maintenance.station_water_detail": "Base station water reservoir status",
  "maintenance.station_water_title": "Station Water",
  // CENSUS-6. Composed CARD-side from upkeep.attention_count. The backend also
  // ships an English `attention_summary` sentence ("3 upkeep item(s) need
  // attention.") which stays as the response-service surface and the card's
  // fallback — but "item(s)" is not a plural, it is a shrug, and it was rendered
  // verbatim in all 18 locales.
  "maintenance.attention_summary": { one: "1 upkeep item needs attention.", other: "{count} upkeep items need attention." },
  "maintenance.attention_summary_none": "No upkeep items need attention.",
  "maintenance.status_empty": "Empty",  // replacements group status: no replacement items tracked (empty list)
  "maintenance.status_good": "Good",  // consumable/water health status = Good (not 'Good' rating elsewhere)
  "maintenance.status_replace_now": "Replace Now",
  "maintenance.status_replace_soon": "Replace Soon",
  "maintenance.status_tracked": "Tracked",  // replacements group status: items are being tracked
  "maintenance.status_unknown": "Unknown",
  "maintenance.status_warning": "Warning",  // consumable health status = Warning
  "maintenance.steps_empty": "No model-aware steps were provided for this item.",
  "maintenance.steps_label": "Steps",  // section heading for the how-to maintenance steps list
  "maintenance.tab_maintenance_items": "Maintenance Items",
  "maintenance.tab_replacements": "Replacements",
  "maintenance.tab_subtitle_maintenance": "Integration-managed maintenance intervals",
  "maintenance.tab_subtitle_replacements": "Upstream replacement-style items",  // 'Upstream' = items sourced from the underlying robovac integration, not integration-tracked intervals.
  "maintenance.tab_title_maintenance": "Maintenance Items",
  "maintenance.tab_title_replacements": "Replacement Items",
  "maintenance.tabs_aria": "Maintenance item groups",
  "maintenance.unknown_remaining_life": "Unknown remaining life",
  "maintenance.unnamed_item": "Unnamed item",
  "maintenance.updated": "Updated {time}",
  "maintenance.used_of": "{used} used of {total}",
  "maintenance.used_since_reset": "{used} used since reset",
  "maintenance.value_unknown": "Unknown",  // fallback when station water value is missing
  "maintenance.water_empty": "Empty",  // station water reservoir FILL level: tank is empty
  "maintenance.water_high": "High",  // station water reservoir FILL level (High amount), not quality/priority
  "maintenance.water_low": "Low",  // station water reservoir FILL level (Low amount), not a low rating
  "maintenance.water_medium": "Medium",  // station water reservoir FILL level (Medium amount)

  // --- map (live map room + config: zoom, furnished, composer, segment editor, zone clean, layout, image variants) ---
  "map.adjusting": "Adjusting:",  // Section header 'Adjusting:' + segment name; user is nudging that room's offset, not editing settings
  "map.analyse_map": "Analyse map",
  "map.analysis_failed": "Analysis failed",
  "map.analyzing": "Analysing…",
  "map.analyzing_progress": "Analyzing… (10-30s)",  // Busy label 'Analyzing… (10-30s)'; keep the time hint, it sets the expected wait
  "map.assign_link_to": "Link to {name}",
  "map.assign_taken_segment": "Already linked to another segment",
  "map.assign_taken_shape": "Already linked to another shape",
  "map.assign_unlink": "Unlink",
  "map.assign_unlink_name": "Unlink {name}",
  "map.backdrop_image_hint": "any map picture — drawn on, never auto-segmented",
  "map.backdrop_image_label": "Backdrop image",
  "map.backdrop_none": "no backdrop yet",
  "map.backdrop_title": "Custom backdrop",
  "map.cancel_delete_title": "Cancel the pending delete",
  "map.compose_add_circle": "＋ Circle",
  "map.compose_add_rect": "＋ Rectangle",
  "map.compose_add_to_start": " · add a shape to start",
  "map.compose_clear_all": "Clear all",
  "map.compose_cutout_off": "Make cutout",
  "map.compose_cutout_off_title": "Carve this shape out of the room (cutout)",
  "map.compose_cutout_on": "⛏ Cutout (carving)",  // Cutout mode active: carve a hole out of the room shape (⛏ glyph)
  "map.compose_cutout_on_title": "Carving a hole — tap to fill instead",
  "map.compose_done": "Done",
  "map.compose_done_title": "Stop editing this shape",
  "map.compose_merge": "⛓ Merge",
  "map.compose_merge_cancel": "Cancel — tap a shape to merge",
  "map.compose_merge_start_title": "Combine another shape into this room",
  "map.compose_merge_stop_title": "Stop merging",
  "map.compose_move_prompt": "Move: the whole room, or just this piece",
  "map.compose_no_rooms": "No rooms discovered for this map yet — link a shape to a room here once they appear.",
  "map.compose_rooms": "Compose rooms",
  "map.compose_save": "Save rooms",
  "map.compose_scope_piece": "Piece",  // move-scope toggle: move just this one shape PIECE of the room
  "map.compose_scope_piece_title": "Move just this shape",
  "map.compose_scope_room": "Room",  // move-scope toggle: move the WHOLE room together (vs single piece)
  "map.compose_scope_room_title": "Move the whole room together",
  "map.compose_selected": "Selected:",
  "map.compose_shape_count": { one: "{count} shape", other: "{count} shapes" },  // plural
  "map.compose_split": "Split out",
  "map.compose_split_title": "Make this shape its own room again",
  "map.compose_step_coarse": "Coarse",  // Nudge-step size button (coarse = largest pixel step, 7px); pairs with Fine/Med
  "map.compose_step_fine": "Fine",  // Nudge-step size button (fine = smallest pixel step, 1px); pairs with Med/Coarse
  "map.compose_step_med": "Med",  // Nudge-step size button (medium step, 3px), short for Medium; pairs with Fine/Coarse
  "map.compose_tap_to_drop": "…or tap the map to drop the shape there.",
  "map.compose_tap_to_edit": " · tap one to edit",
  "map.config_back": "Rooms",
  "map.config_back_aria": "Back to rooms",
  "map.config_click_segment": "Click a segment on the map to adjust it.",
  "map.config_no_image": "No map image uploaded yet.",
  "map.config_title": "Map Configuration",
  "map.confirm_delete": "Confirm Delete",
  "map.delete_variant_confirm_title": "Click again to confirm — or click anywhere else to cancel",
  "map.delete_variant_title": "Delete this image (does not affect the map itself)",
  "map.deleting": "Deleting…",
  "map.dock": "Dock",  // Tooltip on the dock marker overlay; the charging dock's location on the map (noun)
  "map.draw_zone": "Draw a zone to clean",  // Button/tooltip 'Draw a zone to clean'; enters drag-a-box zone-clean mode
  "map.edge_bottom": "Bottom",  // BOTTOM edge of a room-shape box (expand/contract side)
  "map.edge_contract": "Contract {edge}",
  "map.edge_expand": "Expand {edge}",
  "map.edge_left": "Left",  // LEFT edge of a room-shape box (expand/contract side), not a direction
  "map.edge_right": "Right",  // RIGHT edge of a room-shape box (expand/contract side), not a direction
  "map.edge_top": "Top",  // TOP edge of a room-shape box (expand/contract side)
  "map.edges": "Edges",  // Section title over the room-box edge expand/contract controls (Top/Bottom/Left/Right sides)
  "map.empty_custom_hint": "Open Map Configuration to upload this layout's backdrop, then draw + save its rooms.",
  "map.empty_live_hint": "The live map appears once the robot has one — start a clean, or open the robot's app to build its map.",
  "map.empty_no_image_title": "No map image available.",
  "map.empty_rendering_hint": "Drawing the map from the device's room data — one moment.",
  "map.empty_rendering_title": "Rendering the map…",
  "map.empty_upload_hint": "Upload and analyze a map image to enable map view.",
  "map.floor_plan_alt": "Floor plan",  // alt text on the map <img>; describes the floor-plan image for screen readers
  "map.furnished_align": "Align art",
  "map.furnished_align_hint": "Drag the art on the map, or nudge it here. Scale + rotate to match.",
  "map.furnished_art_alt": "Furnished home render",
  "map.furnished_export": "⬇ Save map image",
  "map.furnished_export_failed": "Couldn't save the map image",
  "map.furnished_export_title": "Download the current live map image to trace your furniture over",
  "map.furnished_fine_trim": "Fine trim ±15°",
  "map.furnished_fine_trim_aria": "Fine rotation trim, plus or minus 15 degrees",
  "map.furnished_intro": "Upload a to-scale render of your home, then align it over the live map — the live robot, dock, and cleaning path ride on top.",
  "map.furnished_mode_art": "Art",  // render-mode toggle: show furnished art only (live map hidden)
  "map.furnished_mode_art_title": "Show your furnished art (live map hidden)",
  "map.furnished_mode_blend": "Blend",  // render-mode toggle: art over a faded live map (alignment aid)
  "map.furnished_mode_blend_title": "Art over a faded live map — best for aligning",
  "map.furnished_mode_live": "Live",  // render-mode toggle: show live map only (furniture art hidden)
  "map.furnished_mode_live_title": "Show the live map only (art hidden)",
  "map.furnished_no_size": "The live map has no image size yet — start a clean or open the robot's app so it publishes a map frame, then align.",
  "map.furnished_render_mode": "Render mode",
  "map.furnished_replace_art": "Replace art",
  "map.furnished_reset": "Reset placement",
  "map.furnished_reset_title": "Remove the placement (keeps the uploaded image)",
  "map.furnished_save_align": "Save alignment",
  "map.furnished_save_align_title": "Save this alignment",
  "map.furnished_tip": "Tip: save the current map image, draw your furniture over it, then upload that — it'll line up almost perfectly (the art is already registered to the map pixels). The live robot may show in the saved frame on some maps — just ignore it when tracing.",
  "map.furnished_title": "Furnished render",
  "map.furnished_upload_art": "Upload art",
  "map.hide_area": "Hide area…",
  "map.hide_clear": "Clear ({count})",
  "map.hide_done": "Done",
  "map.hide_draw_hint": "Drag a box over the map to hide it; × removes one.",
  "map.image_variants": "Image Variants",  // Section heading 'Image Variants'; the Dark/Light/Default map-image renders, not generic variants
  "map.layer_current_room": "Current room",
  "map.layer_dock": "Dock",
  "map.layer_hidden_areas": "Hidden areas",
  "map.layer_no_go": "No-go zones",
  "map.layer_no_mop": "No-mop zones",
  "map.layer_obstacles": "Obstacles",
  "map.layer_path": "Cleaning path",
  "map.layer_robot": "Robot + heading",
  "map.layer_room_area": "Room area (m²)",  // Map-layer toggle 'Room area (m²)'; shows each room's floor area in square metres, keep m² unit
  "map.layer_walls": "Virtual walls",  // 'Virtual walls' = app-drawn no-cross barriers (vacuum term of art)
  "map.layer_zones": "Device zones",  // the vacuum app's OWN saved zones from the device map (distinct from the card's Saved Zones panel)
  "map.layers_hint": "Overlays appear on the live-map backdrop.",
  "map.layers_title": "Map Layers",
  "map.layout_create": "Create",
  "map.layout_delete": "Delete layout",
  "map.layout_name_placeholder": "Layout name",
  "map.link_to_room": "Link to room",
  "map.mascot_dock_home": "Drag to set the mascot's docked home spot",
  "map.mascot_following": "Following the robot",
  "map.mascot_reposition": "Drag to reposition",
  "map.no_segments": "No segments analysed",
  "map.nudge_down": "Down",
  "map.nudge_left": "Left",  // move/nudge direction LEFT (arrow button), not a box edge
  "map.nudge_right": "Right",  // move/nudge direction RIGHT (arrow button), not a box edge
  "map.nudge_up": "Up",
  "map.nudge_vertex_down": "Nudge vertex down",
  "map.nudge_vertex_left": "Nudge vertex left",
  "map.nudge_vertex_right": "Nudge vertex right",
  "map.nudge_vertex_up": "Nudge vertex up",
  "map.obstacle": "obstacle",  // Fallback tooltip on an obstacle marker when the device gives no type; a detected floor obstacle
  "map.offset_label": "Offset: {x} px, {y} px",  // 'Offset: {x} px, {y} px' = the segment's translation nudge in pixels; px = pixels, keep unit
  "map.reanalyse": "Re-analyse",  // Button: re-run CV room segmentation on the map image (re-analyse, replaces 'Analyse map' once segments exist)
  "map.remove_hidden_area_aria": "Remove hidden area",
  "map.remove_hidden_area_title": "Remove this hidden area",
  "map.replace": "Replace",  // button to replace the uploaded map/backdrop image, not find-and-replace
  "map.reset_translation": "Reset translation",  // Button tooltip: reset a room segment's nudge offset back to 0 (translation = positional shift, not language)
  "map.reset_vertex": "Reset this vertex",  // Button tooltip: reset one moved polygon corner (vertex) to its original position
  "map.resize_h_minus": "－ H",  // Compose resize button: '－ H' shrinks shape Height; H = height, keep terse
  "map.resize_h_plus": "＋ H",  // Compose resize button: '＋ H' grows shape Height; H = height, keep terse
  "map.resize_w_minus": "－ W",  // Compose resize button: '－ W' shrinks shape Width; W = width, keep terse
  "map.resize_w_plus": "＋ W",  // Compose resize button: '＋ W' grows shape Width; W = width, keep terse
  "map.rotate": "Rotate map 90°",
  "map.switch_map": "Switch the active map",  // Map-toolbar dropdown to switch the active map (backed by the eufy-clean fork's "Switch Map" select)
  "map.frame_gate_notice": "Map switched — zone drawing pauses until the robot re-localizes (move it or start a clean). Running saved zones and room cleans still work.",  // Banner shown after a map switch: the coordinate frame is un-grounded so a drawn zone would land wrong
  "map.frame_gate_override": "Enable drawing anyway",  // Button on the post-switch banner: force-clear the pause (power-user override)
  "map.frame_gate_override_hint": "Only if you know the robot's position is correct — a zone drawn before the robot re-localizes can clean the wrong area.",  // Tooltip warning on the override button
  "map.rotate_aria": "Rotate map 90 degrees",
  "map.rotate_ccw": "↺ Rotate",
  "map.rotate_cw": "↻ Rotate",
  "map.rotate_left": "Rotate left",
  "map.rotate_left_01": "Rotate left 0.1°",
  "map.rotate_left_1": "Rotate left 1°",
  "map.rotate_left_90": "Rotate left 90°",
  "map.rotate_right": "Rotate right",
  "map.rotate_right_01": "Rotate right 0.1°",
  "map.rotate_right_1": "Rotate right 1°",
  "map.rotate_right_90": "Rotate right 90°",
  "map.save_failed": "Save failed",
  "map.scale_grow": "Grow",  // tooltip for the enlarge button when scaling placed art/shape (grow size)
  "map.scale_minus": "－ Scale",
  "map.scale_plus": "＋ Scale",
  "map.scale_shrink": "Shrink",  // tooltip for the reduce button when scaling placed art/shape (shrink size)
  "map.seg_adjusted": ", {count} adjusted",  // Appended fragment ', {count} adjusted'; count of segments manually nudged after auto-detect
  "map.seg_count": "{count} segments",
  "map.seg_custom_layout_title": "Custom layout: {name}",
  "map.seg_cv": "Auto (CV)",  // segmentation source: Auto (computer-vision) room detection; CV=computer vision
  "map.seg_cv_title": "Detect rooms automatically from the map image",
  "map.seg_cv_unavailable": "<strong>Auto (CV)</strong> map segmentation needs optional packages ({packages}) that aren't installed in this Home Assistant. Use <strong>Live map</strong>, a <strong>custom layout</strong>, or manual bounds instead — see the <a href=\"https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/16-making-your-own-maps/\" target=\"_blank\" rel=\"noopener\">map setup guide</a>.",
  "map.seg_live": "Live map",  // segmentation source: draw rooms over the vacuum's live map
  "map.seg_live_title": "Draw rooms over your vacuum's live map",
  "map.seg_new": "＋ New",
  "map.seg_new_title": "Add a custom layout (its own backdrop + rooms)",
  "map.seg_title": "Segmentation",
  "map.segment_fallback": "Segment {id}",
  "map.segment_hint_configurable": "Tap to queue · Double-tap to configure",
  "map.segment_hint_queue": "Tap to queue",
  "map.stale_badge_title": "The map couldn't be refreshed — showing the last known view.",  // Tooltip on the stale-map badge (RP-027's hold contract): explains WHY it's dimmed, not just that it is
  "map.stale_last_seen": "Last seen {value}",  // Stale-map badge text; {value} is an already-localized relative time like "3 hours ago"
  "map.toggle_floor_texture": "Toggle floor textures",  // Button toggling the floor-texture map view: paints each room with its floor-type material (wood/tile/carpet…) instead of flat colors
  "map.toggle_va_render": "Toggle VA-rendered map",  // Button toggling the VA-rendered (integration-drawn) map vs live image; VA=Vacuum Agent, expand or keep as-is
  "map.upload": "Upload",
  "map.upload_failed": "Upload failed",
  "map.uploading": "Uploading…",
  "map.variant_dark_hint": "primary — clearest room colours",  // Dark map-variant: the preferred / clearest-colour render (variant ranking hint)
  "map.variant_dark_label": "Dark",  // map image variant name (dark render), a label not a theme mode
  "map.variant_default_hint": "fallback",  // Default map-variant: the fallback render
  "map.variant_default_label": "Default",
  "map.variant_light_hint": "assist — wall detection",  // Light map-variant: aids CV wall-detection during segmentation
  "map.variant_light_label": "Light",  // map image variant name (light render), a label not a theme mode
  "map.variant_not_uploaded": "not uploaded",
  "map.vertices": "Vertices",  // Section title over the polygon-corner (vertex) nudge controls; geometry corners, not generic 'points'
  "map.zone_clean": "Zone clean",
  "map.zone_clean_n": "Clean {count} zones",
  "map.zone_clean_one": "Clean zone",
  "map.zone_clear": "Clear",
  "map.zone_empty": "Drag a box on the map to add a zone.",
  "map.zone_remove": "Remove zone {num}",
  "map.zone_setting_intensity": "Intensity",  // zone-clean strength setting (clean intensity), not screen brightness
  "map.zone_setting_mode": "Mode",  // zone-clean clean-mode select (vacuum/mop/both), not render/theme mode
  "map.zone_setting_suction": "Suction",  // zone-clean fan-speed select; short form of Suction Level
  "map.zone_setting_water": "Water",  // zone-clean water-level setting (Low/Med/High), not the dock water reservoir
  "map.zone_settings": "Settings",  // section title for the zone-clean settings panel (suction/mode/water)
  "map.zone_settings_note": "apply to the whole clean",  // Note under zone settings: these suction/mode/water values 'apply to the whole clean' (all zones, not per-zone)
  "map.zone_zones": "Zones",
  "map.zoom_controls_aria": "Map zoom controls",
  "map.zoom_fit": "Fit map to screen",
  "map.zoom_fit_aria": "Fit to screen",
  "map.zoom_in": "Zoom in",
  "map.zoom_level_aria": "Current zoom level",
  "map.zoom_out": "Zoom out",

  // --- metrics (Stats tab: usage/learning/water/dock/battery analytics) ---
  "metrics.battery_all_jobs": "All jobs (mixed + single)",  // Drain-table aggregate row label 'All jobs (mixed + single)'; the all-buckets total row
  "metrics.battery_area_used": "{area} m² | {pct} % used",  // Detail: '{area} m² | {pct} % used' = area cleaned and battery percent used; '|' divider
  "metrics.battery_awaiting_charge_session": "Awaiting next charge session",
  "metrics.battery_awaiting_first_job": "Awaiting first job",
  "metrics.battery_bucket_clean_mode": "Clean mode",  // Battery-drain table grouping dimension (jobs bucketed by clean mode); not a settable mode
  "metrics.battery_bucket_empty": "{label} — no single-bucket jobs yet",
  "metrics.battery_bucket_fan_speed": "Fan speed",  // Battery-drain table grouping dimension (jobs bucketed by fan speed); analytics label, not a control
  "metrics.battery_bucket_water_level": "Water level",  // Battery-drain table grouping dimension (jobs bucketed by water level); analytics, not a setting
  "metrics.battery_by_clean_mode": "By clean mode",  // Section sub-header in drain table: 'By clean mode' breakdown rows
  "metrics.battery_by_fan_speed": "By fan speed",  // Section sub-header in drain table: 'By fan speed' breakdown rows
  "metrics.battery_by_water_level": "By water level",  // Section sub-header in drain table: 'By water level' breakdown rows
  "metrics.battery_charge_cycles": "Charge cycles",  // 'Charge cycles' chip: estimated full-charge-equivalent cycles (cumulative drain ÷ 100)
  "metrics.battery_charge_cycles_detail": "Cumulative drain ÷ 100",  // Formula text: full-charge-equivalent cycles = cumulative drain divided by 100
  "metrics.battery_charge_rate": "Charge rate",  // Battery chip; value is a charge rate in %/min (percent per minute)
  "metrics.battery_charging_now": "Charging now",
  "metrics.battery_col_bucket": "Bucket",  // Drain-table column header for the stat grouping bucket (e.g. clean-mode/fan/water value)
  "metrics.battery_col_jobs": "Jobs",  // Drain-table column header: count of jobs in this bucket
  "metrics.battery_col_last_rate": "Last rate",  // Charge-rates table column: most recent charge rate (%/min) for the zone
  "metrics.battery_col_mean_per_m2": "Mean",  // Drain-table column header; the unit lives on the VALUE via metrics.unit_per_m2
  "metrics.unit_per_m2": "%/m²",  // battery drain unit, appended to a value. LOCALIZED — ar/he/ru do not use a Latin m
  "metrics.unit_per_min": "%/min",  // charge-rate unit, appended to a value. Composed from run_profiles.minutes_unit
  "metrics.battery_col_notes": "Notes",  // Charge-rates table column: explanatory note text per row, not user-entered notes
  "metrics.battery_col_zone": "Zone",  // Charge-rates table column: a battery charge-rate %-band zone (low/high/mid), not a clean zone/room
  "metrics.battery_drain_subtitle": "Only jobs where every room used the same setting feed these means. Mixed-mode runs still update the all-jobs row but skip per-bucket buckets.",  // 'single-bucket job' = a run where every room used the same setting
  "metrics.battery_drain_title": "Drain per m² by single-bucket job",
  "metrics.battery_health": "Health %",  // 'Health %' chip: battery state-of-health percent vs early full charges, not run health
  "metrics.battery_health_building": "Building baseline",  // Health placeholder: still building the baseline of early full charges
  "metrics.battery_health_vs_first": "vs first {count} full charges",  // Health detail: 'vs first {count} full charges' = baseline of earliest charges
  "metrics.battery_last_job_per_m2": "Last job %/m²",  // Chip label 'Last job %/m²' = battery percent drained per square metre last job
  "metrics.battery_last_job_title": "Most recent completed job",
  "metrics.battery_last_sample": "Last sample",  // Charge-rate sublabel: value is from the last recorded sample (robot not charging now)
  "metrics.battery_mixed": "(mixed)",  // Placeholder '(mixed)' shown when a job used multiple settings, not one single bucket value
  "metrics.battery_no_completed_job": "No completed job yet — sensors populate after the first finalized run.",
  "metrics.battery_post_job_recharge": "Post-job recharge",  // Section/row: the recharge that happens AFTER the cleaning job finishes
  "metrics.battery_rates_title": "Charge rates by zone",
  "metrics.battery_raw_files_subtitle": "Long-term review is best done from the raw files written by the integration. Chart any of the sensors above with HA's history-graph or apexcharts-card; for deeper analysis open the CSV in a spreadsheet.",
  "metrics.battery_raw_files_title": "Raw data files",
  "metrics.battery_row_area": "Area",  // Last-job table row: floor area covered (m²) in the most recent job
  "metrics.battery_row_avg_rate": "Avg rate",  // Recharge row; average charge rate in %/min during the post-job recharge
  "metrics.battery_row_battery_used": "Battery used",
  "metrics.battery_row_drain_per_hour": "Drain per hour",  // Last-job row; battery drain per hour (%/h)
  "metrics.battery_row_drain_per_m2": "Drain per m²",  // Last-job row; battery percent drained per square metre (%/m²)
  "metrics.battery_row_drain_rate": "Drain rate",  // Last-job row label; value is battery drain in %/min (percent per minute)
  "metrics.battery_row_duration": "Duration",
  "metrics.battery_row_ended": "Ended",
  "metrics.battery_row_job_id": "Job ID",
  "metrics.battery_row_recharge_delta": "Recharge delta",
  "metrics.battery_row_recharge_duration": "Recharge duration",
  "metrics.battery_row_recorded": "Recorded",
  "metrics.battery_row_single_clean_mode": "Single clean mode",
  "metrics.battery_row_single_fan_speed": "Single fan speed",
  "metrics.battery_row_single_water_level": "Single water level",
  "metrics.battery_row_weighted_by": "Weighted by",  // what the drain rate is weighted by: est-minutes / room-count / none
  "metrics.battery_zone_high": "High (≥ 80 %)",  // Battery charge-rate zone, high charge band (≥80%); a %-range, not a quality rating
  "metrics.battery_zone_high_note": "CV taper — earliest health drop indicator",  // Charge-rate note: 'CV taper' = constant-voltage charge taper; earliest health-drop sign
  "metrics.battery_zone_last_session": "Last full session",  // Charge-rates row for the last full charge session (its duration), not a %-band
  "metrics.battery_zone_last_session_note": "Charged {pct} %",
  "metrics.battery_zone_low": "Low (≤ 29 %)",  // Battery charge-rate zone, low charge band (≤29%); a %-range, not a quality rating
  "metrics.battery_zone_low_note": "Slow precharge / soft-cell signal",  // Charge-rate note: slow pre-charge or weak-cell ('soft-cell') signal at low battery
  "metrics.battery_zone_mid_job": "Mid-job (15→75)",  // Battery charge-rate zone, mid-job recharge band (15→75%); a %-range, not a rating
  "metrics.battery_zone_mid_job_note": "Rolling mean | {count} samples",
  "metrics.battery_zone_overall": "Overall",  // Battery charge-rate zone covering any active charge interval (aggregate row)
  "metrics.battery_zone_overall_note": "Any active charge interval",
  "metrics.chip_search_aria": "Search {label}",
  "metrics.chip_search_placeholder": "Search…",
  "metrics.detail_jobs_used": "{jobs} jobs | {used} used",  // Window-card detail: '|' divides two stats; '{used}' = jobs used for learning
  "metrics.detail_robot_overhead": "Robot {robot} | Overhead {overhead}",  // Water detail (ml): 'Robot' = water applied to the floor while cleaning; 'Overhead' = water used by dock services (wash/empty), not applied to the floor — the water facet of overhead.
  "metrics.detail_runs_used": "{runs} runs | {used} used",  // Card detail line: '|' is a divider; '{used}' = runs used for learning, not consumed
  "metrics.detail_trust_runs_to_trusted": "Trust {trust} | {runs} runs to trusted",  // Room detail: 'Trust'=tier label, 'runs to trusted'=runs until estimate is reliable
  "metrics.detail_water_recharge": "Water {water} | Recharge {recharge}",  // Window detail: 'Water'={ml} used, 'Recharge'=mid-job recharge count; '|' divider
  "metrics.detail_water_trust": "Water {water} | Trust {trust}",  // Card detail: 'Water'={ml}, 'Trust'=learning trust tier; '|' is a visual divider
  "metrics.dock_accuracy_updated": "Accuracy Updated",
  "metrics.dock_accuracy_updated_detail": "Latest accuracy update",
  "metrics.dock_avg_overhead_per_job": "Avg Overhead / Job",  // Stat: avg dock WATER overhead (ml) per job; 'Overhead' = water, not time
  "metrics.dock_avg_overhead_per_job_detail": "Average water overhead per job",
  "metrics.dock_dry_starts": "Dry Starts",
  "metrics.dock_dry_starts_detail": "Dock dry-start count",
  "metrics.dock_dust_empty": "Dust Empty",
  "metrics.dock_dust_empty_detail": "Dock dust-empty count",
  "metrics.dock_last_dry_duration": "Last Dry Duration",
  "metrics.dock_last_dry_duration_detail": "Latest dock dry duration",
  "metrics.dock_last_dry_start": "Last Dry Start",
  "metrics.dock_last_dry_start_detail": "Latest dock dry start",
  "metrics.dock_last_dust_empty": "Last Dust Empty",
  "metrics.dock_last_dust_empty_detail": "Latest dock dust empty",
  "metrics.dock_last_mop_wash": "Last Mop Wash",
  "metrics.dock_last_mop_wash_detail": "Latest dock mop wash",
  "metrics.dock_mop_wash": "Mop Wash",
  "metrics.dock_mop_wash_detail": "Dock mop wash count",
  "metrics.dock_room_stats_rebuilt": "Room Stats Rebuilt",
  "metrics.dock_room_stats_rebuilt_detail": "Latest room stat rebuild",
  "metrics.dock_wash_cycles": "Wash Cycles",
  "metrics.dock_wash_cycles_detail": "Wash cycles inferred from jobs",
  "metrics.dock_water_overhead": "Water Overhead",  // Dock stat: water used by dock services (wash/empty), not cleaning water
  "metrics.dock_water_overhead_detail": "Total dock water overhead",  // 'overhead' = non-cleaning dock/wash water; keep the overhead-vs-cleaning sense
  "metrics.empty_found_profiles": "No found profiles were returned for the current filters.",
  "metrics.empty_room_profiles": "No room-profile metrics matched the current filters.",
  "metrics.empty_rooms": "No room metrics matched the current filters.",
  "metrics.filter_all_learning_use": "All Learning Use",  // 'All' option for the learning-use filter (include used and excluded jobs)
  "metrics.filter_all_profiles": "All Profiles",
  "metrics.filter_all_rooms": "All Rooms",
  "metrics.filter_all_statuses": "All Statuses",
  "metrics.filter_learning_use": "Learning Use",  // Filter label: whether a job was USED for learning (used/excluded), not usage count
  "metrics.filter_profile": "Profile",
  "metrics.filter_room": "Room",
  "metrics.filter_status": "Status",
  "metrics.filters_subtitle": "Focus the metrics by room, profile, status, or learning use.",
  "metrics.filters_title": "Filters",
  "metrics.found_profiles_subtitle": "Detected profile families and trust state.",  // Subtitle for auto-detected profile families and their learning trust state
  "metrics.found_profiles_title": "Found Profiles",  // 'Found Profiles' = clean profiles auto-detected from run history (term of art)
  "metrics.loading": "Loading metrics...",
  "metrics.mini_accuracy_rows": "Accuracy Rows",  // Learning stat: count of predicted-vs-actual accuracy stat rows
  "metrics.mini_accuracy_rows_detail": "Accuracy stat rows",
  "metrics.mini_baselines": "Baselines",  // Learning stat: count of per-room baseline estimate groups (term of art)
  "metrics.mini_baselines_detail": "Room baseline groups",  // Detail: groups of baseline (fallback) per-room learning estimates
  "metrics.mini_exact_stats": "Exact Stats",  // Learning stat: count of exact-match per-room learning stat groups
  "metrics.mini_exact_stats_detail": "Exact room-learning stat groups",  // Detail: exact-match room+profile learning stat groups
  "metrics.mini_found_profiles": "Found Profiles",  // Mini-stat: count of profiles auto-DETECTED from run history (not user-created)
  "metrics.mini_found_profiles_detail": "Profiles with learning history attached",
  "metrics.mini_recharge_count": "Recharge Count",
  "metrics.mini_recharge_count_detail": "Observed mid-job recharges",
  "metrics.mini_wash_cycles": "Wash Cycles",
  "metrics.mini_wash_cycles_detail": "Wash cycles recorded from jobs",
  "metrics.panel_subtitle": "Usage, learning quality, water, and dock metrics across the learning dataset.",
  "metrics.panel_title": "Metrics",
  "metrics.profile_fallback": "Profile",  // Fallback label for an unnamed clean profile; keep short, same as profile noun
  "metrics.room_fallback": "Room",  // Fallback label for an unnamed room; the room noun, kept short
  "metrics.save_candidate": "Save Candidate",  // Badge on a learned profile suggested for saving as a reusable profile
  "metrics.save_candidate_title": "Suggested save candidate",  // Tooltip: this learned profile is a suggested save candidate
  "metrics.save_profile": "Save Profile",
  "metrics.save_profile_title": "Save this learned profile",
  "metrics.saving": "Saving...",
  "metrics.stat_excluded": "Excluded",
  "metrics.stat_jobs": "Jobs",
  "metrics.stat_updated": "Updated",
  "metrics.stat_used": "Used",  // Overview stat: count of jobs USED for learning (not 'used' as consumed/spent)
  "metrics.tabs_aria": "Metrics groups",
  "metrics.unavailable": "Metrics unavailable.",
  "metrics.unknown": "Unknown",
  "metrics.water_overhead": "Water Overhead",  // 'Water Overhead' chip: dock/wash water (not cleaning), distinct from Robot Water
  "metrics.water_overhead_detail": "Dock or wash overhead water",  // Detail for 'Water Overhead' chip: dock/wash water, not robot cleaning water
  "metrics.water_profiles_subtitle": "Average total water use per profile.",
  "metrics.water_profiles_title": "Highest Water Profiles",
  "metrics.water_robot": "Robot Water",  // 'Robot Water' chip: water the robot applied while cleaning, vs dock/overhead water
  "metrics.water_robot_detail": "Robot-applied cleaning water",
  "metrics.water_rooms_subtitle": "Average total water use per room.",
  "metrics.water_rooms_title": "Highest Water Rooms",
  "metrics.water_total": "Total Water",
  "metrics.water_total_detail": "Total water used across matching jobs",  // 'matching jobs' = jobs passing the active filters, not a match score
  "metrics.window_last_30_days": "Last 30 Days",
  "metrics.window_last_7_days": "Last 7 Days",
  "metrics.window_today": "Today",

  // --- mobile ---
  "mobile.dock_status_label": "Dock Status:",  // Status-line prefix before the dock's state value, e.g. 'Dock Status: Charging'; keep colon
  "mobile.more": "More",  // bottom-nav button opening the overflow sheet of extra tabs ('More views')
  "mobile.more_sheet_aria": "Additional views",
  "mobile.nav_primary_aria": "Primary",  // aria-label for the primary bottom tab bar; means 'primary navigation'
  "mobile.tab_dock": "Dock",  // mobile tab label for the Base Station view; NOT the dock map marker (cf. map.dock)
  "mobile.tab_learning_review": "Learning Review",
  "mobile.tab_map_config": "Map Config",
  "mobile.tab_room_rules": "Room Rules",
  "mobile.tab_rooms": "Rooms",
  "mobile.tab_setup": "Setup",
  "mobile.tab_stats": "Stats",  // mobile short tab label for the Metrics view (desktop calls it Metrics)
  "mobile.tab_theme": "Theme",
  "mobile.tab_upkeep": "Upkeep",  // mobile short tab label for the Maintenance view (desktop calls it Maintenance)
  "mobile.vacuum_status_label": "Vacuum Status:",  // Status-line prefix before the robot's state value; 'Vacuum'=the robot (noun); keep colon

  // --- nav (desktop shell: header + tab bar + view-router empty states) ---
  "nav.battery": "Battery",  // header label before the battery percent on the vacuum-status line, e.g. 'Battery 100%'
  "nav.dock_status": "Dock Status:",  // header status-line prefix shown before the dock's state value, e.g. 'Dock Status: Charging'
  "nav.tab_base_station": "Base Station",  // tab label for the dock/charging base station, not a cleaning zone or map area
  "nav.tab_learning_review": "Learning Review",  // Nav tab label. 'Learning' = the system's learned per-room timing data (a feature noun, not the act of learning); view reviews those estimates. Keep short.
  "nav.tab_maintenance": "Maintenance",
  "nav.tab_metrics": "Metrics",
  "nav.tab_room_rules": "Room Rules",
  "nav.tab_rooms": "Rooms",  // main nav tab opening the Rooms view (queue/clean), not a room count or list header
  "nav.tab_setup": "Setup",
  "nav.tab_theme": "Theme",
  "nav.unavailable_base_station": "Base station view unavailable",
  "nav.unavailable_learning_review": "Learning review view unavailable",
  "nav.unavailable_maintenance": "Maintenance view unavailable",
  "nav.unavailable_map_config": "Map config unavailable",
  "nav.unavailable_metrics": "Metrics view unavailable",
  "nav.unavailable_room_rules": "Room rules view unavailable",
  "nav.unavailable_rooms": "Rooms view unavailable",
  "nav.unavailable_setup": "Setup unavailable",
  "nav.unavailable_theme": "Theme view unavailable",
  "nav.unavailable_unknown": "Unknown view",
  "nav.vacuum_status": "Vacuum Status:",  // header status-line prefix shown before the robot's state value, e.g. 'Vacuum Status: Docked'

  // --- relative (shared "ago" timestamp formatter: formatRelativeAgo + map analyzed-at) ---
  "relative.days_ago": { other: "{count}d ago" },  // plural; Compact 'ago' pill; {count}=days, keep unit a short abbreviation
  "relative.hours_ago": { other: "{count}h ago" },  // plural; Compact 'ago' pill; {count}=hours, keep unit a short abbreviation
  "relative.just_now": "just now",
  "relative.minutes_ago": { other: "{count}m ago" },  // plural; 'm'=MINUTES (vs months_ago 'mo'); compact pill, keep unit short
  "relative.months_ago": { other: "{count}mo ago" },  // plural; 'mo'=MONTHS (distinct from minutes_ago 'm'); short suffix, keep distinct
  "relative.weeks_ago": { other: "{count}w ago" },  // plural; Compact 'ago' pill; {count}=weeks, keep unit a short abbreviation
  "relative.years_ago": { other: "{count}y ago" },  // plural; Compact 'ago' pill; {count}=years, keep unit a short abbreviation
  "relative.yesterday": "yesterday",

  // --- review (Learning History review: filters, profile matcher, run exclude/restore) ---
  "review.badge_attribution_disagreement": "Room Mismatch",  // Job badge: on a dispatched run the live room signal disagreed with the assigned (queue-order) room for a segment — flagged for review, not auto-changed
  "review.badge_attribution_disagreement_title": "The live room signal disagreed with the assigned room order for part of this run. The assignment was kept — open the run to check which room was cleaned.",  // Tooltip for the Room Mismatch badge
  "review.badge_excluded": "Excluded",
  "review.badge_external": "External",  // Job badge: run was captured externally (started outside HA / on the robot); its own flag, NOT a sanity or learning verdict
  "review.badge_multi_room": "Multi Room",  // Job badge: run covered multiple rooms ('Multi-room'); pairs with Single Room
  "review.badge_recharge": "Recharge",  // Job badge: robot recharged mid-run, not a battery level
  // Job badge: the run hit one or more device FAULTS while cleaning (bin full, brush
  // tangled, stuck…). Distinct from a cancel or a sanity failure — the run may still
  // have completed. Plural on the fault count.
  "review.badge_errors": "Errors",  // fallback when the count is unknown
  "review.badge_errors_count": { one: "1 error", other: "{count} errors" },
  // Tooltip, shown ONLY when the duration was actually measured. {seconds} = whole
  // seconds the run spent in a fault state.
  "review.badge_errors_seconds": "{seconds}s spent in an error state during this run",
  // Tooltip continuation — WHOSE hardware raised the faults (RF-DOCK clause 4). The
  // evidence axis already decides whether the seconds were deducted; this answers the
  // other question, "which box do I go and look at". Appended only for a source that
  // actually has seconds, so a purely robot-side run never mentions a dock.
  // {seconds} = whole seconds attributed to that source.
  "review.badge_errors_from_dock": "{seconds}s from the dock",
  "review.badge_errors_from_robot": "{seconds}s from the robot",
  // Shown when the brand does not classify a code, so the user is not told we know
  // which hardware it was. Silence would imply attribution we do not have.
  "review.badge_errors_unattributed": "{seconds}s not attributed to specific hardware",
  "review.badge_sanity_failed": "Sanity Failed",  // Job badge: run failed plausibility/sanity checks (suspect data)
  "review.badge_single_room": "Single Room",
  "review.badge_suggested_exclude": "Suggested Exclude",  // Job badge: system suggests excluding this run from learning
  "review.custom_reason_placeholder": "Enter a reason…",  // Placeholder for the free-text input shown when the 'Custom…' exclude reason is picked
  "review.detail_area_m2": "{value} m²",  // Job value: floor area cleaned this run, '{value}' = square metres (e.g. '15 m²')
  "review.detail_battery": "Battery {value}",  // Job stat: battery percent consumed by the run, '{value}' is a %
  "review.detail_minutes": "{value} min",  // Job-card stat: run duration; '{value}' = whole minutes (e.g. '12 min')
  "review.detail_outlier": "Outlier {value}",  // Job stat: statistical outlier score {value}, how anomalous the run is
  "review.detail_water": "Water {value} ml",
  "review.exclude": "Exclude",  // Action button: exclude this run from learning history (verb)
  "review.exclude_reason": "Exclude Reason",  // Label above chips picking WHY a run is excluded from learning
  "review.filter_all_learning_use": "All Learning Use",
  "review.filter_all_origins": "All Origins",  // Fallback chip for the Origin filter: no origin filter applied
  "review.filter_all_profiles": "All Profiles",
  "review.filter_all_rooms": "All Rooms",
  "review.filter_all_statuses": "All Statuses",
  "review.filter_learning_use": "Learning Use",  // Filter dimension: whether jobs are used for learning; verb 'use', not 'used'
  "review.filter_origin": "Origin",  // Filter dimension: how the run started — external (app-started) vs dispatched (by this integration)
  "review.filter_profile": "Profile",
  "review.filter_room": "Room",
  "review.filter_sort": "Sort",
  "review.filter_status": "Status",
  "review.filters_subtitle": "Narrow to room, profile, status, or learning use.",
  "review.filters_title": "Filters",
  "review.kv_area": "Area Cleaned",  // Job-card field: floor area cleaned this run (m²); aids the human include/exclude call
  "review.kv_primary_room": "Primary Room",  // Job-card field: the main/first room of a multi-room run
  "review.kv_profile": "Profile",
  "review.kv_rooms": "Rooms",
  "review.kv_zones": "Zones",  // review row: named zones cleaned in the run (shown only when it had a zone)
  "review.kv_scope": "Scope",  // Job-card field: job scope = single-room vs multi-room run extent
  "review.kv_used_for_learning": "Used For Learning",  // Job-card field: whether this run feeds time/water learning (Yes/No)
  "review.loading": "Loading learning history...",
  "review.matched_profiles_title": "Matched Profiles",
  "review.matcher_chip_title": "Filter learning jobs to this profile",
  "review.matcher_clean_mode": "Cleaning Mode",  // Profile-matcher field labeling clean mode: vacuum / mop / both (not appearance mode)
  "review.matcher_clean_passes": "Cleaning Passes",  // Matcher field: number of cleaning passes (1 or 2), not pass/fail or a corridor
  "review.matcher_clean_path": "Cleaning Path",  // Matcher label for clean_intensity (path density): quick vs deep coverage, not a file path
  "review.matcher_count": { one: "{count} exact match found.", other: "{count} exact matches found." },  // plural
  "review.matcher_edge_mopping": "Edge Mopping",  // Matcher field: edge-mopping on/off (mop along walls), a per-room setting
  "review.matcher_empty": "Adjust the matcher fields until they line up with a saved profile exactly.",
  "review.matcher_no_matches": "No exact profile matches for the current settings.",
  "review.matcher_reset": "Reset Matcher",
  "review.matcher_subtitle": "Try room-editor settings locally to find exact learned profile matches without editing a live room.",
  "review.matcher_suction_level": "Suction Level",  // Matcher field: vacuum suction strength (fan speed), not an audio/volume level
  "review.matcher_title": "Profile Matcher",  // Panel title: tool to find saved profiles matching chosen settings ('Profile Matcher')
  "review.matcher_water_level": "Water Level",  // Matcher field: mop water flow amount, not a tank fill gauge
  "review.panel_subtitle": "Review runs used for learning and exclude bad history when needed.",
  "review.panel_title": "Learning Review",
  "review.passes": { one: "{count} Pass", other: "{count} Passes" },  // plural; Chip value: N cleaning passes over the floor (re-clean count), not pass/fail
  "review.profile_fallback": "Profile",
  "review.restore": "Restore",  // Action button: restore a previously-excluded run into learning (verb)
  "review.room_fallback": "Room",
  "review.runs_empty": "No learning history jobs matched the current filters.",
  "review.runs_subtitle": "Newest first unless another sort is selected.",
  // REV-5. Shown ONLY when the run list was cut by the limit. {shown} = rows in this
  // payload, {total} = rows that matched the filters. A cap the user cannot see reads
  // as "there is nothing more", which is why the stat and the list disagreeing silently
  // was the bug.
  "review.runs_truncated": "Showing {shown} of {total} matching runs — narrow the filters to see the rest.",
  "review.runs_title": "Runs",  // Section title: list of cleaning runs/jobs (the noun 'Runs', not the verb)
  "review.search_aria": "Search {label}",
  "review.search_placeholder": "Search…",
  "review.sort_newest": "Newest",  // Sort option label: newest runs first (sort order, not a 'new' badge)
  "review.stat_jobs": "Jobs",
  "review.stat_profiles": "Profiles",
  "review.stat_rooms": "Rooms",
  "review.stat_updated": "Updated",
  "review.unavailable": "Learning history unavailable.",
  "review.unknown": "Unknown",
  "review.working": "Working...",  // Transient button label while an exclude/restore action is in flight
  "room_access.accessed_from_help": "The room that grants access to this room. Read-only — set from the other room's editor.",
  "room_access.accessed_from_here_help": "Select the rooms this room unlocks. A room already claimed by another room cannot be selected here.",
  "room_access.accessed_from_here_label": "Rooms Accessed From Here",  // Section label over editable list: rooms THIS room unlocks/grants access to (outbound).
  "room_access.accessed_from_label": "Accessed From",  // Section label over the read-only inbound list: rooms that grant access INTO this room.
  "room_access.claimed_by": "Already claimed by Room {room}",  // Tooltip on a disabled room chip. {room} = the claiming room's id/label. 'Claimed' = already has another room as its access-grantor; keep word 'Room'.
  "room_access.dock_room_help": "The dock room is the origin of the access tree. It has no inbound dependencies. Only one room can be the dock room. Releasing it clears the whole access graph for this map.",
  "room_access.dock_room_label": "Dock Room",  // Field label. 'Dock' = robot's charging dock; noun, NOT the verb 'to dock'. Root room of the access tree.
  "room_access.graph_issues_label": "Graph Issues",  // Label over validation errors. 'Graph' = the room-access dependency graph, not a chart/diagram.
  "room_access.invalid_graph": "Invalid room access graph.",
  // The dock is the root and there is exactly one, so the button is dead in every
  // other room. {room} = the room that currently holds it.
  "room_access.dock_held_by": "{room} is the dock room. Release it there first.",
  "room_access.issue.card.no_dock_room": "Set a dock room before linking rooms. The dock room is the origin of the access tree.",
  // A6-AGX-6. {id} = the raw stored room id for an access link whose room is gone.
  "room_access.missing_room": "Missing Room {id}",
  // Tooltip on an existing access link that points AT the dock room. The dock room is
  // never offered as a NEW target, but a stored edge into it stays visible and removable.
  "room_access.edge_into_dock": "This link points at the dock room. It can be removed, but not re-added.",

  // --- A6-AGX-4: access-graph issue codes -> translated sentences. The backend
  // emits {code, params} (params never pre-joined) and the card resolves them via
  // state/access-issue-label.js; the backend's English `message` remains the
  // fallback for a code this release has not heard of. Ten backend codes, then the
  // six the CARD's own validator raises (state/rooms.js validateRoomAccessUpdate).
  // {room}/{target}/{dock}/{missing_room}/{claimant} are room NAMES;
  // {rooms}/{sources} are already-joined lists (see list_separator). ---
  "room_access.issue.list_separator": ", ",  // Joins room names in {rooms}/{sources}. Include any trailing space the language needs; CJK typically uses a full-width comma with no space.
  "room_access.issue.self_reference": "{room} cannot grant access to itself.",
  "room_access.issue.missing_room": "{room} still references missing room {missing_room}.",
  "room_access.issue.duplicate_edge": "{room} has the same access target listed more than once for {target}.",
  "room_access.issue.cycle_detected": "Access links create a loop: {rooms}.",  // {rooms} = the loop chain, in order.
  "room_access.issue.multiple_inbound": "{room} is granted access by more than one room ({sources}). Each room can only have one inbound link.",
  "room_access.issue.missing_dock_room": "One room must be marked as the dock room before access links can be considered healthy.",  // 'Dock room' = the charging-dock room, the root of the access tree.
  "room_access.issue.multiple_dock_rooms": "Only one dock room is allowed. Current dock rooms: {rooms}.",
  "room_access.issue.missing_dependency": "{room} needs an inbound dependency so it can be reached from {dock}.",
  "room_access.issue.unreachable_from_dock": "{room} is not reachable from {dock} through the current access links.",
  "room_access.issue.unknown_issue": "The access graph contains an unknown issue.",
  "room_access.issue.duplicate_edges": "{room} lists the same access target more than once.",  // Card-side validator; plural 'edges' is a distinct code from the backend's duplicate_edge.
  "room_access.issue.missing_room_references": "{room} references a room that no longer exists.",
  "room_access.issue.cycle": "These access links would create a loop.",  // Card-side validator; it detects the loop but does not name the chain.
  // --- CARD-raised variants. Same code, different fault: the backend's
  // missing_room means "references a room that is gone", the card's means "the
  // room you are editing is gone"; the two multiple_inbound sentences also
  // interpolate different params. Scoped so neither renders the other's sentence. ---
  "room_access.issue.card.missing_room": "This room no longer exists on the active map.",
  "room_access.issue.card.self_reference": "A room cannot grant access to itself.",
  "room_access.issue.card.duplicate_edges": "Each access link can only appear once.",
  "room_access.issue.card.missing_room_references": "All access links must point to rooms on the current map.",
  "room_access.issue.card.multiple_inbound": "{target} already has an inbound link from {claimant}. Each room can only be reached from one room.",
  "room_access.issue.card.cycle": "This access setup would create a loop in the room graph.",


  "room_access.is_dock_room": "This is the Dock Room",  // Active-state chip label confirming this room IS the dock (charging-dock origin) room. 'Dock' = noun.
  "room_access.no_inbound": "No room grants access here yet.",
  "room_access.no_other_rooms": "No other rooms are available on this map.",
  "room_access.save": "Save Access",  // Save button in modal footer. 'Access' = noun (the room-access config); keep short.
  "room_access.set_dock_room": "Set as Dock Room",  // Chip button: make this the dock (charging-dock origin) room. Imperative; 'Dock' = noun, not verb.
  "room_access.title": "{name} Access",  // Modal header. {name} = the room name; reads '<RoomName> Access'. 'Access' = noun.

  // --- room_card (standalone per-room Lovelace card + its config editor) ---
  "room_card.carpet_notice": "Carpet room — mop fields hidden",  // banner shown when room is carpet: mop/water controls are hidden
  "room_card.cleaning_mode_label": "Cleaning Mode",
  "room_card.cleaning_path_label": "Cleaning Path",  // chip-row label for clean_intensity (path density: e.g. Standard/Deep), NOT a route/map path
  "room_card.edge_mopping_label": "Edge Mopping",  // Field label for the edge-mopping toggle (mop tight along walls/edges); term of art
  "room_card.editor_name_hint": "Overrides the label shown on the card.",
  "room_card.editor_name_override_label": "Name override",
  "room_card.editor_name_placeholder": "Leave blank to use room name",
  "room_card.editor_no_room_switches": "No room switches found for {vacuum}.",  // Error: no per-room HA switch.* entities for {vacuum}; 'switches'=entities, not light switches
  "room_card.editor_optional": "(optional)",
  "room_card.editor_pick_room": "— pick a room —",
  "room_card.editor_pick_vacuum": "— pick a vacuum —",
  "room_card.editor_room_label": "Room",
  "room_card.editor_select_vacuum_first": "Select a vacuum first.",
  "room_card.editor_vacuum_label": "Vacuum",  // Editor dropdown label for picking the vacuum device; noun (the robot), not the verb
  "room_card.passes_1": "1 Pass",  // chip value: one cleaning sweep over the room (passes count = 1)
  "room_card.passes_2": "2 Passes",  // chip value: two cleaning sweeps over the room (passes count = 2)
  "room_card.passes_label": "Passes",  // chip-row header for number of cleaning passes (1 or 2 sweeps), not a passcode/permit
  "room_card.room_fallback": "Room {room_id}",  // display name when a room has no name; {room_id} is the numeric id
  "room_card.select_hint": "Click the room name to select it for cleaning — this clears all other rooms in the queue.",  // hint under the header: clicking the room name does an EXCLUSIVE select (deselects every other room) before the run
  "room_card.start": "Start",  // button that starts cleaning this single room now (run action), not a generic begin
  "room_card.starting": "Starting…",  // transient label on the Start button while the clean is being dispatched
  "room_card.suction_level_label": "Suction Level",
  "room_card.unsaved_badge": "Unsaved",  // header badge: card has edited-but-unsaved chip changes (dirty state)
  "room_card.water_level_label": "Water Level",

  // --- vacuum_card (multi-room "Dashboard Mode" control card + its editor) ---
  "vacuum_card.dock": "Dock",  // button that sends the vacuum back to its charging dock (return_to_base), not a noun
  "vacuum_card.editor_sections_hint": "Hide a section to keep the card compact; sections also hide when the vacuum doesn't support them.",
  "vacuum_card.editor_sections_label": "Sections",  // editor group label for the show/hide toggles below it
  "vacuum_card.editor_show_dock": "Show dock button",
  "vacuum_card.editor_show_map": "Show map (draw zones)",  // toggle: show the live-map zone-draw section
  "vacuum_card.editor_show_profiles": "Show saved profiles",  // toggle: show the saved run-profiles dropdown
  "vacuum_card.editor_show_scenes": "Show app scenes",  // toggle: show the vendor-app scenes dropdown (Eufy only)
  "vacuum_card.editor_title_label": "Card title",
  "vacuum_card.editor_title_placeholder": "Leave blank to use the vacuum name",
  "vacuum_card.include_room": "Include this room in the run",  // tooltip on the per-room include checkbox
  "vacuum_card.map_label": "Map",  // section label above the live-map zone-draw surface
  "vacuum_card.map_loading": "Loading map…",  // placeholder while the full map bundle loads on first use
  "vacuum_card.zone_remove": "Tap to remove this zone",  // tooltip on a drawn zone rectangle
  "vacuum_card.zones_at_cap": "max zones",  // appended to the hint when the per-clean zone cap is reached
  "vacuum_card.zones_clean": { one: "Clean {count} zone", other: "Clean {count} zones" },  // button: start cleaning the drawn zones
  "vacuum_card.zones_clear": "Clear",  // button: discard all drawn zones
  "vacuum_card.zones_drawn": { one: "{count} zone drawn", other: "{count} zones drawn" },  // status: how many zones are drawn
  "vacuum_card.zones_failed": "Couldn't start the zone clean — try again.",  // toast when start_zone_clean fails
  "vacuum_card.zones_hint": "Drag on the map to draw a zone to clean",  // instruction shown before any zone is drawn
  "vacuum_card.no_rooms": "No rooms found for this vacuum — import a map and configure rooms first.",
  "vacuum_card.passes_n": { one: "{count} Pass", other: "{count} Passes" },  // chip: number of cleaning sweeps over the room
  "vacuum_card.profiles_label": "Your profiles",  // section label for the saved run-profiles launcher
  "vacuum_card.profiles_placeholder": "— run a saved profile —",  // dropdown placeholder before a profile is armed
  "vacuum_card.rooms_label": "Rooms",  // section label above the per-room selection rows
  "vacuum_card.rooms_selected": { one: "{count} selected", other: "{count} selected" },  // badge on the collapsed Rooms group showing how many rooms are armed
  "vacuum_card.scenes_hint": "Selecting a scene arms it; it runs when you press Start.",  // clarifies arm-only (scene fires on Start, not on pick)
  "vacuum_card.scenes_label": "App scenes",  // section label for the vendor-app (Eufy) scenes launcher
  "vacuum_card.scenes_placeholder": "— run an app scene —",  // dropdown placeholder before a scene is armed
  "vacuum_card.start": "Start",  // button that dispatches the armed run (rooms / profile / scene), not a generic begin
  "vacuum_card.start_failed": "Couldn't start the run — check the vacuum and try again.",  // toast when a service call fails mid-dispatch
  "vacuum_card.starting": "Starting…",  // transient Start-button label while the run is being dispatched
  "vacuum_card.status.cleaning": "Cleaning",  // live vacuum activity shown in the header
  "vacuum_card.status.docked": "Docked",
  "vacuum_card.status.error": "Error",
  "vacuum_card.status.idle": "Idle",
  "vacuum_card.status.paused": "Paused",
  "vacuum_card.status.returning": "Returning to dock",
  "vacuum_card.status.unavailable": "Unavailable",
  "vacuum_card.status.unknown": "Unknown",

  // --- room_editor ---
  "room_editor.access": "Access",  // button opening room access-graph editor (which room unlocks which); not generic 'access'
  "room_editor.carpet_notice": "Carpet room — locked to vacuum-only modes",
  "room_editor.cleaning_mode": "Cleaning Mode",  // Field label above vacuum/mop/both chips; the cleaning MODE, not theme/render mode
  "room_editor.cleaning_passes": "Cleaning Passes",  // Field label: how many cleaning sweeps over the room (noun 'Passes', not the verb)
  "room_editor.cleaning_path": "Cleaning Path",  // Field label for clean-INTENSITY chips (maps to clean_intensity), not the robot's route
  "room_editor.cleaning_profile": "Cleaning Profile",  // label for the saved-preset selector (a reusable bundle of room settings)
  "room_editor.color_default": "Default (palette)",  // shown next to the swatch when the room has NO custom color — it uses the themeable palette
  "room_editor.color_label": "Room Color",  // field label: this room's fill color on the map; a custom color overrides the shared palette
  "room_editor.color_pick_title": "Pick a custom color for this room",  // tooltip on the color swatch/picker
  "room_editor.color_reset": "Reset",  // button: clear the custom color, revert to the themeable palette default
  "room_editor.custom": "Custom",  // profile chip: settings are custom, not from a saved profile (a state, not 'Custom Profile')
  "room_editor.edge_mopping": "Edge Mopping",  // On/off toggle label: mop along room edges/walls (term of art 'edge mop')
  "room_editor.excluded": "Excluded",  // queue toggle state: room is OUT of this run's queue (not excluded from learning/bounds)
  "room_editor.included": "Included",  // queue toggle state: room IS in this run's queue (not learning/bounds 'included')
  "room_editor.meta_custom": "Current room settings are custom and not linked to a saved profile.",
  "room_editor.meta_profile_builtin": "{label} is built in and read-only.",
  "room_editor.meta_profile_custom": "{label} is a custom reusable profile.",
  "room_editor.meta_select": "Select a profile to apply reusable room settings.",
  "room_editor.mopstate_mopping": "Mopping — water tank attached",
  "room_editor.mopstate_vacuum": "Vacuum only — no water tank",
  "room_editor.pass": { one: "{count} Pass", other: "{count} Passes" },  // plural; Pass-count chip: N cleaning sweeps over the room; noun, not pass/fail
  "room_editor.passes_global_note": "Passes are controlled globally in the robot's own app — the per-room value here may be overridden.",
  "room_editor.queue_status_label": "Current queue status:",
  "room_editor.save_as_new": "Save as New",  // button: save current room settings as a new reusable profile (vs theme.save_as_new)
  "room_editor.save_over": "Save Over",  // button: overwrite the currently selected saved room profile
  "room_editor.suction_level": "Suction Level",
  "room_editor.transition_callout": "Shape analysis suggests this may be a hallway or connecting corridor.",
  "room_editor.transition_is": "Transition Space",  // toggle ON state for a hallway/corridor room; same 'Transition Space' meaning
  "room_editor.transition_mark": "Mark as Transition",  // verb: tag this room as a hallway/connecting corridor
  "room_editor.transition_space_label": "Transition Space",  // field label: room is a hallway/connecting corridor (pass-through space)
  "room_editor.water_level": "Water Level",

  // --- room_estimate ---
  "room_estimate.empty_notes": "No extra estimate notes for this room right now.",
  "room_estimate.label_battery": "Battery",  // battery % this room's clean is predicted to use
  "room_estimate.label_done_by": "Done by",  // predicted wall-clock finish time label (value is a clock time)
  "room_estimate.label_elapsed": "Elapsed",  // live time spent so far cleaning this room
  "room_estimate.label_estimated_time": "Estimated time",  // predicted clean duration for this room
  "room_estimate.label_mode": "Mode",  // per-room clean mode value: Mop / Vacuum / Vac & Mop (not a UI/theme mode)
  "room_estimate.label_progress": "Progress",  // live % cleaned of this room during an active run
  "room_estimate.label_projected_water": "Projected water",  // predicted water this room's clean will use (ml)
  "room_estimate.label_remaining": "Remaining",  // live time left to finish this room
  "room_estimate.label_samples": "Samples",  // count of learned past runs feeding this room's estimate
  "room_estimate.label_source": "Source",  // where this estimate came from: learned data vs default fallback
  "room_estimate.label_water_level": "Water level",  // per-room water-level setting value (Low/Medium/High), not a measured amount
  "room_estimate.modal_title": "{name} Estimate",  // modal title: '{room name} Estimate'
  "room_estimate.note_allocated_estimate": { one: "Shared across {count} room cleaned together", other: "Shared across {count} rooms cleaned together" },  // plural; caveat: this room's time is a multi-room total split evenly across the allocation group, not a standalone measurement
  "room_estimate.note_intensity_mismatch": "Estimated from different intensity",  // caveat: estimate derived from runs at a different suction/intensity
  "room_estimate.note_no_learned_data": "No learned data yet",  // caveat: no learned history yet, estimate is a default
  "room_estimate.note_runs_to_reliable": { one: "{count} run to reliable", other: "{count} runs to reliable" },  // plural; caveat: N more runs needed before estimate is reliable
  "room_estimate.section_live": "Live Progress",
  "room_estimate.section_notes": "Learning Notes",  // section heading over learning caveats for this estimate
  "room_estimate.section_summary": "Estimate Summary",  // section heading over the estimate facts (time/source/samples/battery)
  "room_estimate.section_water": "Water Projection",  // section heading over projected water + mode/level for this room
  "room_estimate.subtitle_done_by": "done by {time}",  // subtitle: predicted finish clock time, e.g. 'done by 3:40 PM'
  "room_estimate.water_ml": "~{ml} ml",  // approximate water volume in milliliters, e.g. '~120 ml'

  // --- room_rules ---
  "room_rules.add_rule": "Add Rule",
  "room_rules.also_affects": { one: "→ also affects {count} room", other: "→ also affects {count} rooms" },  // plural
  "room_rules.change_clean_intensity": "Clean Intensity",
  "room_rules.change_clean_mode": "Clean Mode",
  "room_rules.change_clean_passes": "Clean Passes",  // Setting-override row: number of cleaning passes/repeats (1x or 2x), not 'pass/fail'.
  "room_rules.change_edge_mopping": "Edge Mopping",  // Setting-override row: edge-mopping on/off (mop the room's wall edges); term of art.
  "room_rules.change_fan_speed": "Fan Speed",
  "room_rules.change_water_level": "Water Level",
  "room_rules.condition": "Condition",
  "room_rules.disabled": "Disabled",
  "room_rules.editor_title_edit": "Edit Rule - {name}",
  "room_rules.editor_title_new": "New Rule - {name}",
  "room_rules.empty": "No rooms yet — set up rooms first under Setup → Import Active Map (the highlighted button) → Configure Rooms, then add rules here.",
  "room_rules.enabled": "Enabled",
  "room_rules.entity_help_choose": "Choose a Home Assistant entity to drive this rule.",
  "room_rules.entity_help_current": "Current: {state}",
  "room_rules.entity_help_options": { one: "{count} option", other: "{count} options" },  // plural
  "room_rules.entity_help_type": "Type: {category}",
  "room_rules.entity_help_unavailable": "This entity is not currently available in Home Assistant.",
  "room_rules.entity_help_unit": "Unit: {unit}",
  "room_rules.entity_id": "Entity ID",
  "room_rules.entity_search_empty": "No matching Home Assistant entities found.",
  "room_rules.fan_out_help": "When this rule fires, also apply its settings to the rooms below. Each room's own rules still win for any fields they set; this fills in fields the room hasn't already overridden.",
  "room_rules.fan_out_label": "Also apply to",
  "room_rules.help_blocker": "Skip this room entirely when the condition is true.",
  "room_rules.help_max": "Max: {max}",
  "room_rules.help_min": "Min: {min}",
  "room_rules.help_modifier": "Override this room's cleaning settings when the condition is true.",
  "room_rules.kind_blocker": "Blocker",  // Rule-type chip 'Blocker' = skip this room entirely when the condition is true.
  "room_rules.kind_modifier": "Modifier",  // Rule-type chip 'Modifier' = override the room's clean settings when condition true.
  "room_rules.label_field": "Label",
  "room_rules.label_placeholder": "e.g. Skip when door is open",
  "room_rules.no_rules_for_room": "No rules configured for {name}.",
  "room_rules.op_is_on": "is ON",  // Rule-card condition summary for the is_on operator; reads as '<entity> is ON'
  "room_rules.op_is_off": "is OFF",  // Rule-card condition summary for the is_off operator
  "room_rules.op_exists": "exists",  // Rule-card condition summary: the entity/attribute exists
  "room_rules.op_missing": "is missing",  // Rule-card condition summary: the entity/attribute is absent
  "room_rules.effect_exclude": "Exclude room",  // Rule-card effect summary for a blocker rule with no reason text
  "room_rules.effect_exclude_reason": "Exclude - {reason}",  // Rule-card effect summary; {reason}=the user's free-text reason. Keep the dash separator.
  "room_rules.effect_modify": "Modify settings",  // Rule-card effect summary for a modifier rule with no specific changes
  "room_rules.optional": "(optional)",
  "room_rules.reason": "Reason",
  "room_rules.reason_placeholder_blocker": "e.g. Door open",
  "room_rules.reason_placeholder_modifier": "e.g. Reduce water near door",
  "room_rules.rule_type": "Rule Type",
  "room_rules.save_rule": "Save Rule",
  "room_rules.select_a_value": "Select a value",
  "room_rules.select_room_above": "Select a room above.",
  "room_rules.setting_overrides": "Setting Overrides",
  "room_rules.setting_overrides_help": "Select overrides to apply. \"-\" means keep the room's saved setting.",  // The literal '-' is a UI chip glyph (=keep saved setting); keep the dash as-is.
  "room_rules.unnamed_rule": "Unnamed rule",
  "room_rules.value": "Value",
  "room_rules.value_list_help": "Comma-separated list of values.",
  "room_rules.value_multi_help": "Choose one or more allowed values from the entity itself.",
  "room_rules.value_placeholder_list": "value1, value2, ...",
  "room_rules.value_placeholder_text": "e.g. home, 25, true",
  "rooms.access_not_set": "Access not set",
  "rooms.add_charge_break": "+ Charge break",  // chip: insert a charge-to-% break into the queue (makes the run stepped)
  "rooms.add_wait_break": "+ Wait break",  // chip: insert a timed wait break into the queue
  "rooms.another_room": "another room",
  "rooms.battery_label": "Battery: {value}",  // Estimate tooltip 'Battery: {value}'; {value} is the battery % the estimate assumed (a number)
  "rooms.block_reason.no_rooms_included": "No rooms included.",  // start blocked: no rooms enabled for this map. Reason CODE from state/rooms.js, localized in the renderer
  "rooms.block_reason.already_cleaning": "Already cleaning.",  // start blocked: a clean is already running
  "rooms.block_reason.returning_to_dock": "Returning to dock.",  // start blocked: vacuum is returning to its dock
  "rooms.block_reason.vacuum_error": "Vacuum has an error.",  // start blocked: vacuum is in an error state
  "rooms.block_reason.start_blocked": "Start is blocked.",  // start blocked: generic fallback when no more specific reason is available
  // --- A5-AG-2: BACKEND refusal codes. These reach the card as `reason` on the
  // start status / job-control payload and were previously rendered only as the
  // backend's English `message` — untranslatable in the 17 non-English packs.
  // {rooms} is a LIST joined card-side with common.list_separator.
  // live:AGX-CLEAR-1: the refusal named two exits and only one was findable.
  // "Clear all access settings" is a real, one-tap action — releasing the dock
  // room clears the graph — but nothing said WHERE, so a user could read this
  // sentence a dozen times and never locate the second door. Naming the room is
  // the difference between an instruction and a riddle.
  "rooms.block_reason.incomplete_access_graph": "Room access is incomplete for {rooms}. Complete their access links, or open the dock room's Access panel and release it — that clears the graph and lets basic runs work again.",  // start blocked: the room-access graph is half-configured. {rooms} = the rooms whose access links are missing or broken.
  "rooms.block_reason.access_graph_required_for_rules": "Room rules require a complete access graph. Configure the dock room and room connections before using rules.",  // start blocked: rules are set but no access graph exists to evaluate them against.
  "rooms.block_reason.access_graph_required": "Room blockers require a manual room access graph before they can be used.",  // start blocked: blocker rules exist with no access graph at all.
  "rooms.block_reason.rooms_blocked": "Some rooms are blocked by their rules and will be skipped.",  // preflight WARNING (not a block): a reduced run is offered for confirmation.
  "rooms.block_reason.confirmation_required": "Confirmation is required before starting this reduced run.",  // start warning: the reduced-run confirm flow.
  "rooms.block_reason.job_paused": "A tracked job is paused. Resume or cancel it before starting a new one.",  // start blocked: a paused job owns the vacuum.
  "rooms.block_reason.onboarding_required": "Finish setting up this map before starting a clean.",  // start blocked: onboarding (e.g. floor types) is incomplete.
  "rooms.block_reason.rule_blocked": "Blocked by a room rule.",  // per-room preflight reason CODE: a blocker rule matched but carries no user reason text
  "rooms.block_reason.access_blocked": "Blocked - the route to this room passes through a blocked room.",  // per-room preflight reason CODE: the room is unreachable because a room on its access path is blocked
  "rooms.blocked_fallback": "Blocked",
  "rooms.blocked_rooms": "Blocked Rooms",
  "rooms.cancel_run": "Cancel Run",
  "rooms.cancel_warning": "Tap \"Confirm Cancel\" again to send the vacuum back to the dock, or press <strong>Cancel</strong> to keep the job running.",
  "rooms.charge_time_varies": "Charge time varies with the battery level when it docks.",  // note under the stepped-run preview
  "rooms.chip_charge_label": "Charge to",  // prefix label on an editable charge chip (precedes a % input)
  "rooms.chip_charge_to": "Charge to {target}%",  // aria label for the editable charge chip
  "rooms.chip_wait": "Wait {minutes} min",  // aria label for the editable wait chip
  "rooms.chip_wait_label": "Wait",  // prefix label on an editable wait chip (precedes a minutes input)
  "rooms.clear_breaks": "Clear breaks",  // chip: remove all charge/wait breaks, back to a flat clean
  "rooms.clear_queue": "Clear Queue",
  "rooms.move_step": "Move step",  // aria/title on the queue-chip reorder grip (opens the move-to-position modal)
  "rooms.remove_break": "Remove break",  // aria/title on the queue-chip remove (X) control
  "rooms.add_zone": "+ Zone",  // chip: open the saved-zone picker to add a zone step to the queue
  "rooms.zone_fallback": "Zone",  // fallback name for a saved zone with no name / unresolved id
  "rooms.zone_time_learned": "Learned from {count} run(s)",  // title on a zone chip's time when it's a learned average
  "rooms.zone_time_estimated": "Estimated from zone size (no runs yet)",  // title on a zone chip's time when it's the area fallback (~)
  "rooms.zone_picker_title": "Add a zone step",  // header of the multi-select saved-zone picker
  "rooms.zone_picker_empty": "No saved zones on this map yet.",  // picker body when there are no saved zones
  "rooms.zone_picker_add": "Add to queue",  // picker confirm: inserts the selected zones as one step
  "rooms.companion_animal": "Companion animal",
  "rooms.configure": "Configure",
  "rooms.configure_map": "Configure map",
  "rooms.confirm_cancel": "Confirm Cancel",
  "rooms.confirm_clear": "Confirm Clear",
  "rooms.confirm_start": "Confirm Start",
  "rooms.count_rooms": { one: "1 room", other: "{count} rooms" },  // plural; room count label
  "rooms.count_zones": { one: "1 zone", other: "{count} zones" },  // plural; queued-zone count, appended to the room count
  "rooms.live_queue_label": "Live queue",  // header of the running-job chip sequence (rooms + breaks + zone, live)
  "rooms.derived_via": "(via {room}'s {rule})",  // Why a room was modified: '(via {room}'s {rule})'; {room}=other room name, {rule}=rule name
  "rooms.drag_to_reorder": "Drag to reorder",
  "rooms.duration_skipped": "~{duration} skipped",
  "rooms.edge_mop_on": "Edge Mop On",  // room chip: edge-mopping is enabled for this room (on/off state)
  "rooms.elapsed_label": "Elapsed: {value}",
  "rooms.empty": "No rooms yet — open the Setup tab and run Import Active Map (the highlighted button), then Configure Rooms to get started.",
  "rooms.estimate_label": "Estimate: {value}",
  "rooms.exclude_room_aria": "Exclude room {name}",
  "rooms.force_exact_order": "Force this exact order",  // Button enabling strict order: clean queued rooms one-by-one in the shown order (slower)
  "rooms.hide_companion": "Hide companion",
  "rooms.hide_map_textures": "Hide map textures",
  "rooms.hide_room_card_textures": "Hide room-card textures",
  "rooms.hide_room_labels": "Hide room labels",
  "rooms.icon_size": "Icon size",
  "rooms.include_room_aria": "Include room {name}",
  "rooms.included": "included",  // lowercase suffix after the queue count, e.g. '3 rooms included'
  "rooms.intensity_mismatch": "intensity mismatch",  // Warning chip: estimate was learned at a different clean intensity/profile than now set
  "rooms.last_cleaned_label": "Last cleaned: {value}",
  "rooms.list_view": "List view",  // view-toggle: show rooms as a list (vs map view)
  "rooms.locate": "Locate",  // button: make the vacuum chirp to find it (Locate command)
  "rooms.map_view": "Map view",  // view-toggle: show rooms on the map (vs list view)
  "rooms.mascot_follow_off": "Make the mascot ride the live robot position (replaces the dot)",
  "rooms.mascot_follow_on": "Mascot follows the live robot position — tap for room/dock mode",
  "rooms.mascot_follows_robot": "Mascot follows robot",
  "rooms.mascot_physics": "Mascot physics",  // aria-label for the Normal-universe / Moonwalk-mode toggle button
  "rooms.moonwalk_off": "Normal universe — the mascot faces the way it's heading. Tap for Moonwalk mode.",  // toggle title, direction-aware facing ON (default). "Moonwalk": a playful reference to Michael Jackson's moonwalk dance, not walking on the Moon. The mascot intentionally appears to move backward.
  "rooms.moonwalk_on": "🕺 Moonwalk mode — the mascot glides backward. Tap for Normal universe.",  // toggle title, Moonwalk mode ON. "Moonwalk": a playful reference to Michael Jackson's moonwalk dance, not walking on the Moon. The mascot intentionally appears to move backward.
  "rooms.mode_label": "Mode: {value}",
  "rooms.mode_mop": "Mop",  // per-room clean-MODE chip value (mop action), not the dock mop-wash
  "rooms.mode_vacuum": "Vacuum",  // per-room clean-MODE chip value (vacuum action), not the device/vacuum noun
  "rooms.mode_vacuum_mop": "Vacuum + Mop",  // per-room clean mode: vacuum and mop in one pass
  "rooms.modified_rooms": "Modified Rooms",
  "rooms.move": "Move",  // button to change a room's position in the clean order/queue
  "rooms.move_room": "Move room",
  "rooms.n_blocked": { other: "{count} blocked" },  // plural
  "rooms.n_included": { other: "{count} included" },  // plural
  "rooms.n_passes": "{count}× passes",  // Room chip: cleaning-pass count, e.g. '2× passes' = robot covers the room twice
  "rooms.no_rooms_queued": "No rooms queued — toggle rooms to include them",
  "rooms.note_intensity_mismatch_title": "Estimate was learned from a different cleaning intensity or profile.",
  "rooms.note_no_learned_data_title": "This room is using a fallback estimate until enough learned samples are collected.",
  "rooms.note_runs_to_reliable_title": "Estimated {count} more runs to reach high confidence.",
  "rooms.open_room_settings_aria": "Open room settings for {name}",
  "rooms.pause": "Pause",
  "rooms.percent_complete": "{pct}% complete",
  "rooms.profile_custom": "Custom",  // cleaning-profile name: user's own settings (not a saved preset)
  "rooms.profile_deep": "Deep",  // cleaning-profile name: thorough/deep clean preset
  "rooms.profile_quick": "Quick",  // cleaning-profile name: fast/light clean preset
  "rooms.profile_standard": "Standard",  // cleaning-PROFILE name (fallback), not a quality/size rating
  "rooms.profile_user_1": "User Profile 1",
  "rooms.profile_vacuum_only_deep": "Vacuum Only Deep",
  "rooms.profile_vacuum_only_quick": "Vacuum Only Quick",
  // plural — passes count in a composed profile name/subtitle (e.g. "2 Passes")
  "room_profile.passes": { one: "{count} Pass", other: "{count} Passes" },
  "rooms.progress_label": "Progress: {pct}%",
  "rooms.projected_water_use": "Projected water use: ~{ml} ml",
  "rooms.queue_chip_title": "Click for settings · Double-click for estimate · Hold to remove from queue",
  "rooms.queue_room_aria": "Queue room {name}",
  "rooms.rainbow_bridge": "Rainbow Bridge",  // Optgroup label for memorial (deceased-pet) companion animals; keep the 'rainbow bridge' idiom
  "rooms.reduced_run_detected": "Reduced Run Detected",  // Preflight header: some rooms are blocked so this run will clean fewer rooms than queued
  "rooms.remaining_label": "Remaining: {value}",
  "rooms.remaining_left": "~{value} left",
  "rooms.resume": "Resume",
  "rooms.room_fallback": "Room",
  "rooms.room_settings": "Room settings",
  "rooms.run_plan_title": "This Job",  // header of the pre-run stepped (room -> charge -> room) preview
  "rooms.running": "Running",  // active-job header label: a clean is in progress
  "rooms.select_all": "Select All",
  "rooms.settings_adjusted": "Settings adjusted",
  "rooms.show_companion": "Show companion",
  "rooms.show_map_textures": "Show map textures",
  "rooms.show_room_card_textures": "Show room-card textures",
  "rooms.stall_capture_enable": "Turn on stall capture",
  "rooms.stall_capture_disable": "Turn off stall capture",
  "rooms.show_room_labels": "Show room labels",
  "rooms.source_label": "Source: {value}",  // Estimate tooltip: data origin of the time estimate; {value} is 'learned' or 'default', not a URL
  "rooms.start_cleaning": "Start Cleaning",
  "rooms.strict_order_on_label": "Strict order: ON",
  "rooms.strict_order_on_text": "Strict order ON — rooms will clean one at a time in the order shown (slower: a dock trip between rooms).",
  "rooms.trouble_note_title": "This room was missed in {pct}% of recent runs. Consider checking for obstacles or map accuracy.",
  "rooms.trust_learning": "Learning",  // estimate-confidence badge: still learning, not the Learning feature/tab
  "rooms.trust_reliable": "Reliable",  // estimate-confidence badge: time estimate is trustworthy
  "rooms.trust_tooltip_with_samples": "{label} · {count} samples",  // confidence-chip tooltip: trust label plus how many learned runs it's based on
  "rooms.trust_uncertain": "Uncertain",  // estimate-confidence badge: estimate not yet trustworthy
  "rooms.trust_unlearned": "Unlearned",  // estimate-confidence badge: no learned data, using default estimate
  "rooms.warnings": "Warnings",
  "rooms.water_label": "Water: {value}",
  "rooms.water_ml": "~{ml} ml water",  // Room chip: projected clean-water this room will use, '~{ml} ml water'

  // --- run_profiles ---
  "run_profiles.create_profile": "Create Profile",
  "run_profiles.add_charge_step": "Add a charge step",  // reveals/adds a dock-and-recharge step between room groups
  "run_profiles.add_wait_step": "Add a wait",  // adds a timed dock-and-hold (wait X min) step between room groups
  "run_profiles.capture_group": "Add current rooms as a group",  // snapshot the current Rooms-view setup as the next step
  "run_profiles.editor_title_edit": "Edit Saved Profile",
  "run_profiles.editor_title_new": "Create Run Profile",
  "run_profiles.empty": "No saved profiles yet.",
  "run_profiles.expose_as_button": "Expose as Home Assistant Button",  // Checkbox; 'Expose'=surface this profile as a callable Home Assistant button entity
  "run_profiles.exposed_as_button": "· Exposed as button",  // Selected-profile meta tag; same 'Exposed'=surfaced-as-HA-button; keep leading '· ' separator
  "run_profiles.name_label": "Name",
  "run_profiles.name_placeholder": "Morning Clean",  // Input placeholder = example profile name, not a label; localize to a natural sample
  "run_profiles.room_count": { one: "{count} room", other: "{count} rooms" },  // plural
  "run_profiles.room_fallback": "Room {id}",  // fallback label when a step's room id has no known name
  "run_profiles.run": "Run",  // selected-profile button = apply + start the profile now (dispatches its steps)
  "run_profiles.runs_as": "Runs in this order",  // label above the read-only step sequence in the selected-profile card
  "run_profiles.save_over": "Save Over Profile",  // Editor button = overwrite the existing profile with current settings ('Save Over')
  "run_profiles.save_this_setup": "Save This Setup",  // Header button; 'Setup'=the current room-queue configuration, not install/wizard
  "run_profiles.step_charge_to": "Charge to",  // charge-step row label, precedes a percent input
  "run_profiles.step_clean": "Clean",  // room-group step row label, precedes the room names
  "run_profiles.step_group_empty": "(no rooms)",  // shown when a group step has no rooms
  "run_profiles.step_move_down": "Move down",  // step reorder control (title/aria)
  "run_profiles.step_move_up": "Move up",  // step reorder control (title/aria)
  "run_profiles.step_remove": "Remove step",  // step delete control (title/aria)
  "run_profiles.step_unsupported_position": "Will be skipped (unsupported position)",  // struck-through note on a legacy leading/trailing charge_wait/wait step (CARD-6 clause 1) -- it has nothing to bracket and will never actually run; sanitizeStepsForSave strips it on save
  "run_profiles.step_wait": "Wait",  // wait-step row label, precedes a minutes input
  "run_profiles.step_zone": "Zone",  // zone-step row label in the profile editor, precedes the saved-zone names
  "run_profiles.minutes_unit": "min",  // short unit after a minutes number (wait step)
  "run_profiles.steps_capture_hint": "Set up the rooms you want next in the Rooms view, then add them as a group.",
  "run_profiles.steps_hint": "Vacuum, dock to recharge, then keep cleaning — all in one run.",
  "run_profiles.steps_label": "Run steps",  // section label for the ordered room-group + charge-step editor
  "run_profiles.subtitle": "Save this room setup and reapply it later without rebuilding the queue by hand.",
  "run_profiles.title": "Run Profiles",  // Feature name = saved room-queue setups; 'Run'=a cleaning run, 'Profiles'=named setups

  // --- standalone profile card (inspect-and-run one saved profile on a dashboard) ---
  "profile_card.configure": "Select a vacuum, map, and profile in the card editor.",  // shown when the card has no profile picked yet
  "profile_card.loading": "Loading…",  // shown while the saved profiles are being fetched
  "profile_card.not_found": "Profile not found for this vacuum and map.",  // configured profile_id no longer exists
  "profile_card.untitled": "Untitled profile",  // fallback when a saved profile has no name
  "profile_card.editor_map_label": "Map",  // card-editor dropdown label for the map picker
  "profile_card.editor_pick_map": "— pick a map —",  // card-editor map dropdown placeholder
  "profile_card.editor_profile_label": "Profile",  // card-editor dropdown label for the profile picker
  "profile_card.editor_pick_profile": "— pick a profile —",  // card-editor profile dropdown placeholder
  "profile_card.editor_no_maps": "No maps found for this vacuum.",  // hint when the vacuum has no managed maps
  "profile_card.editor_no_profiles": "No saved profiles for this map.",  // hint when the map has no run profiles

  // --- saved zones ---
  "saved_zones.area_m2": "{area} m²",  // Zone size chip; {area}=one-decimal number, m²=square metres
  "saved_zones.cancel_draw": "Cancel",  // exit draw-to-save without saving
  "saved_zones.clean_selected": { one: "Clean {count} selected", other: "Clean {count} selected" },  // primary action; {count}=selected zone count
  "saved_zones.clean_selected_empty": "Clean selected",  // disabled label when nothing is selected
  "saved_zones.clear": "Clear",  // clear the zone multi-selection
  "saved_zones.draw": "+ Draw a zone",  // button: enter draw-a-box-to-save mode on the live map
  "saved_zones.draw_hint": "Drag a box on the map, then Save.",  // instruction shown while drawing a zone to save
  "saved_zones.empty": "No saved zones yet.",
  "saved_zones.over_cap": "Max {max} zones per clean",  // shown when more than the device limit are selected
  "saved_zones.rename": "Rename",  // per-zone rename button
  "saved_zones.room_select_aria": "File under room",  // aria-label on the per-zone room re-file select
  "saved_zones.save_drawn": "Save zone",  // commit the drawn box as a named saved zone
  "saved_zones.select_zone": "Select {name}",  // aria-label on a zone's select checkbox
  "saved_zones.selected_badge": { one: "{count} selected", other: "{count} selected" },  // collapsed-header count badge
  "saved_zones.subtitle": "Named spots you can re-clean any time — filed under the room they're in.",
  "saved_zones.title": "Saved Zones",
  "saved_zones.unassigned": "Unassigned",  // Section header for zones not filed under a room

  // --- setup ---
  "setup.add": "Add",
  "setup.add_another_vacuum": "Add another vacuum",
  "setup.add_vacuum": "Add Vacuum",
  // Setup STEP labels — keyed by step.id, rendered via t() (the backend/fallback
  // ships English labels; see setup/drift.py). Distinct from setup.add_vacuum
  // (the action BUTTON) vs setup.step_add_vacuum (the wizard step heading).
  "setup.step_add_vacuum": "Add vacuum",  // setup wizard step 1 heading
  "setup.step_import_active_map": "Import active map",  // setup wizard step 2 heading
  "setup.step_save_rooms": "Configure rooms",  // setup wizard step 3 heading (save/configure rooms)
  // Floor-type option labels (the room floor-type picker; FLOOR_TYPE_OPTIONS in
  // setup.js). Keyed by floor value, rendered via t().
  "setup.floor_hardwood": "Hardwood",  // floor type
  "setup.floor_laminate": "Laminate",  // floor type
  "setup.floor_tile": "Tile",  // floor type
  "setup.floor_marble": "Marble",  // floor type
  "setup.floor_granite": "Granite",  // floor type
  "setup.floor_concrete": "Concrete",  // floor type
  "setup.floor_carpet_low_pile": "Low-Pile Carpet",  // floor type: short/low carpet pile
  "setup.floor_carpet_high_pile": "High-Pile Carpet",  // floor type: deep/high carpet pile
  "setup.all_vacuums_managed": "All detected vacuums are already managed.",
  "setup.auto_adapter_default": "Auto (adapter default)",  // Live-map camera select default option; 'adapter'=brand integration shim (jargon)
  "setup.check_status": "Check Status",
  "setup.click_to_exclude": "Click to exclude",
  "setup.click_to_include": "Click to include",
  "setup.complete_add_vacuum_first": "Complete Add Vacuum first.",
  "setup.complete_map_import_first": "Complete map import first.",
  "setup.configure_each_map": "Configure each imported map — exclude ghost rooms and set floor types.",  // save_rooms intro; 'ghost rooms'=phantom/non-real rooms to exclude (term of art)
  "setup.configure_rooms": "Configure Rooms",
  "setup.configured_badge": "✓ Configured",
  "setup.delete_map": "Delete Map",
  "setup.delete_type_confirm": "Type <strong>{name}</strong> to confirm deletion.",
  "setup.delete_warning": "Delete <strong>{name}</strong>? This removes all rooms, history, and learning data for this map from the integration. The upstream cloud map is not affected.",
  "setup.deleting": "Deleting…",
  "setup.description": "Steps below are declared by your vacuum adapter. Each must complete in order. New rooms discovered after setup will surface here for review before they enter the room library.",
  "setup.drift_new_hint": "The vacuum reports rooms you haven't configured yet. Configure the matching map to include them, or reject as phantoms.",
  "setup.drift_new_title": "New rooms discovered ({count})",
  "setup.drift_removed_hint": "These rooms have been missing from discovery long enough to be confirmed removed. Reconfigure the matching map to drop them.",
  "setup.drift_removed_title": "Rooms no longer reported ({count})",
  "setup.drift_transient_hint": "Missing from recent discovery passes but not yet confirmed removed — likely a transient API glitch. Use \"Force remove\" only if you know the room is permanently gone.",
  "setup.drift_transient_title": "Temporarily missing ({count})",
  "setup.force_remove_now": "Force remove now",  // Drift button: permanently drop a room flagged as removed (force = override the wait)
  "setup.import_active_map": "Import Active Map",
  "setup.import_active_map_prompt": "Import the vacuum's currently active map. Make sure it has completed a mapping run first.",
  "setup.import_another_map": "Import Another Map",
  "setup.live_map_camera_hint": "Use a live map image/camera entity as this vacuum's map backdrop — for example the <code>camera.&lt;device&gt;_map</code> entity from the eufy-clean fork. Choose \"Auto\" to use the adapter default.",  // Keep code tokens literal: camera.<device>_map, 'eufy-clean fork', 'Auto' — do not translate
  "setup.live_map_camera_title": "Live map camera",
  "setup.loading_rooms": "Loading rooms…",
  "setup.map_label": "map {id}",  // Lowercase muted sub-label beside a room; {id}=the map's numeric id (cf. map_n capitalized)
  "setup.map_n": "Map {id}",
  "setup.maps_imported": "{count} maps imported.",
  "setup.no_rooms_discovered": "No rooms discovered yet. Run a clean cycle so the vacuum reports its room list, then refresh setup status.",
  "setup.no_rooms_for_map": "No rooms found for this map.",
  "setup.no_rooms_selected_hint": "Select at least one room to save. To remove this map entirely, use Delete Map instead.",
  "setup.no_step_handler": "No handler for step \"{id}\".",  // Internal error fallback; {id}=setup-step id; 'handler' is dev jargon, keep terse
  "setup.protection_reason.only_map": "This is the only imported map for this vacuum.",  // Map-delete protection badge; reason CODE only_map from the backend
  "setup.protection_reason.has_active_job": "A cleaning job is running or was recently active on this map.",  // Map-delete protection badge; reason CODE has_active_job
  "setup.protection_reason.has_learning_data": { one: "This map has cleaning history for {count} room.", other: "This map has cleaning history for {count} rooms." },
  "setup.protection_reason.has_rules": "One or more rooms have automation rules configured.",  // Map-delete protection badge; reason CODE has_rules
  "setup.protection_reason.has_access_graph": "One or more rooms are part of an access graph.",  // Map-delete protection badge; reason CODE has_access_graph
  "setup.panel_name_hint": "Rename this vacuum's entry in the Home Assistant sidebar. After saving, refresh the page to see the new name. Leave blank to reset to the default.",
  "setup.panel_name_title": "Panel name",  // Heading for renaming this vacuum's Home Assistant sidebar entry ('Panel'=HA sidebar item)
  "setup.ready_banner": "✓ Setup complete — switch to the Rooms tab to start cleaning.",
  "setup.reconcile_dismiss_button": "Dismiss",  // CARD-7/RP-019 reconciliation banner: reconcile_room(action=ignore) — NOT permanent, an identical review can resurface later (design: never say "Ignore forever")
  "setup.reconcile_dismissing": "Dismissing…",
  "setup.reconcile_dropped_sentence": { one: "<strong>{names}</strong> was removed from this map and its settings were discarded.", other: "<strong>{names}</strong> were removed from this map and their settings were discarded." },  // plural; State C (after Update) — rendered via tRaw, raw HTML bold (mirrors setup.delete_warning's pattern); {names}=comma-joined, already-escaped display names (prettified from the backend's slugs); {count}=names.length drives the form. Omitted entirely when dropped is empty.
  "setup.reconcile_formerly": "Formerly {name}",  // Secondary caption under a renamed room's NEW name in the reconciliation banner's "Renamed" group; {name}=the room's previous name (escaped by the caller). A separate translated unit from the name itself — never concatenated into one sentence.
  "setup.reconcile_rediscover_button": "Re-discover rooms",  // Manual retry button shown only when the silent plan_changed recovery itself failed
  "setup.reconcile_refresh_failed": "The map changed, but the refresh didn't go through automatically.",  // CARD-7/RP-019: shown when the silent plan_changed recovery (re-running discover_rooms) itself fails — design's literal fallback ("the map changed — re-discover" + a button)
  "setup.reconcile_renamed_hint": "Same room number, different name — either you renamed it in the app, or re-mapping reused this number for a different space. It can't be told apart automatically; review before updating.",
  "setup.reconcile_renamed_title": "Renamed rooms ({count})",
  "setup.reconcile_renumbered_hint": "The vacuum reassigned these room numbers after re-mapping. Saved settings will follow automatically — no action needed.",
  "setup.reconcile_renumbered_title": "Rooms renumbered ({count})",
  "setup.reconcile_stale_note": "The map changed while you were reviewing — this is the current state.",
  "setup.reconcile_update_button": "Update saved rooms",  // CARD-7/RP-019 reconciliation banner: reconcile_room(action=migrate) — the ONE whole-map decision (no per-row accept; reconcile_room has no per-room granularity)
  "setup.reconcile_updated_count": { one: "Updated {count} room.", other: "Updated {count} rooms." },  // plural; State C (after a successful Update) — reconcile_room's migrated_room_count
  "setup.reconcile_updating": "Updating…",
  "setup.reconfigure": "Reconfigure",
  "setup.refresh": "Refresh",
  "setup.register_vacuum_prompt": "Register this vacuum with the integration so it can be managed.",
  "setup.reject_as_phantom": "Reject as phantom",  // Drift button: mark a discovered room as not-real (phantom = ghost/non-existent room)
  "setup.room_editor_hint": "Deselect rooms you don't want managed (phantom rooms, closets, etc.). Set each real room's floor type — it drives the cleaning profile system.",
  "setup.room_n": "Room {id}",
  "setup.rooms_configured_drift": "Rooms configured. Drift detection watches for new or removed rooms below.",
  "setup.save_room_config": "Save Room Configuration",
  "setup.title": "Vacuum Setup",
  "setup.unmanaged_vacuums_hint": "These vacuums are available in Home Assistant but not yet managed. Adding one registers its adapter and a sidebar panel (the integration reloads).",
  "setup.vacuum_registered": "Vacuum registered.",
  "setup.working": "Working…",

  // --- shell (card-level render fallbacks + no-vacuum onboarding placeholder) ---
  "shell.setup_add_title": "Add your vacuum",
  "shell.setup_eufy_note": "Using a Eufy vacuum? The <a href=\"https://github.com/jeppesens/eufy-clean\" target=\"_blank\" rel=\"noopener\">eufy-clean</a> integration provides that entity.",
  "shell.setup_lede": "The integration is installed but no vacuum is configured yet, so the panel can't show your rooms, jobs, or controls until you point it at your vacuum.",
  "shell.setup_no_entity_body": "This integration works on top of whatever Home Assistant integration provides your vacuum — make sure your vacuum is set up and producing a working <code>vacuum.*</code> entity first, then come back here and choose it.",
  "shell.setup_no_entity_title": "If you don't see a vacuum entity in the dropdown",
  "shell.setup_reload_note": "The integration will reload and this page will turn into the full Vacuum Agent panel with your rooms, learning history, and controls.",
  "shell.setup_step_configure": "Click <strong>Configure</strong>",
  "shell.setup_step_find": "Find <strong>Vacuum Agent</strong>",  // Setup step. 'Vacuum Agent' is the product name (the integration) — keep it literal, do not translate.
  "shell.setup_step_open": "Open <strong>Settings → Devices &amp; Services</strong>",  // Setup step: HA menu path 'Settings -> Devices & Services' must match Home Assistant's own UI translation, not a literal re-translation.
  "shell.setup_step_pick": "Pick your <code>vacuum.*</code> entity from the dropdown and submit",
  "shell.setup_title": "Vacuum Agent — setup needed",  // No-vacuum onboarding heading. 'Vacuum Agent' = product name, keep literal; only 'setup needed' translates.
  "shell.view_error": "View error — check console ({view})",  // Render-error fallback. 'View error' = error rendering this view (noun), NOT imperative 'view the error'; {view} is an internal view/tab id.

  // --- theme (theme editor: token groups, swatches, import/export, presets, modes) ---
  "theme.alpha_aria_label": "{label} opacity",
  "theme.apply_preset": "Apply Preset",  // Button 'Apply Preset': applies a built-in marble FLOOR-TEXTURE preset to the theme; NOT the theme/preset cards on the Themes tab.
  "theme.apply_preset_title": "Apply this built-in marble preset to the active theme",
  "theme.browse_gallery": "Browse gallery",
  "theme.clear_filters": "Clear",  // button: clear the active preset filter chips (not delete data/zones)
  "theme.color_hint": "Drag for opacity · Double tap for color",
  "theme.colormix_hint": "Drag ratio · Edit color references",
  "theme.discard": "Discard",  // button: throw away unsaved theme token edits (the draft), not a captured run
  "theme.download": "Download",
  "theme.download_floor": "Download Floor",  // Button 'Download Floor': exports one FLOOR-TEXTURE type (tile/wood/marble/carpet) as a preset .json — NOT a building storey/level.
  "theme.download_floor_title": "Download just this floor type as a shareable preset .json",  // Tooltip: download just this floor-TEXTURE type (tile/wood/marble) as a shareable preset; 'floor type' = texture, not storey.
  "theme.download_title": "Download theme as a .json file",
  "theme.export": "Export",
  "theme.export_title": "Copy theme JSON to clipboard",
  "theme.filter_all": "All",
  "theme.filter_modified": "Modified",  // filter chip: show only tokens changed from default ('modified' = edited)
  "theme.filters": "Filters",
  "theme.filters_count": "Filters ({count})",
  "theme.floor_scope_title": "Floor type to export as a shareable preset",  // Tooltip on the floor-type picker: 'floor' = a floor-TEXTURE type (tile/wood/marble), not a building storey.
  "theme.gallery_link_title": "Browse the theme gallery (opens in a new tab)",
  "theme.group_no_match": "No tokens in {title} match \"{query}\".",
  "theme.group_search_placeholder": "Search {title}...",
  "theme.import": "Import",
  "theme.import_title": "Paste theme JSON from clipboard",
  "theme.json_modal_copy": "Copy",
  "theme.json_modal_hint_export": "Copy this JSON to share or back up the active theme. It's not saved anywhere — it's gone when you close this.",
  "theme.json_modal_hint_import": "Paste a theme export below, then Import. (Or use Upload for a file.)",
  "theme.json_modal_import": "Import",
  "theme.json_modal_notify_title": "Post this export to a Home Assistant persistent notification to grab later (useful for batch exports when clipboard/download are blocked)",
  "theme.json_modal_paste_placeholder": "Paste theme JSON here…",
  "theme.json_modal_send_to_ha": "Send to HA",
  "theme.json_modal_title_export": "Export theme",
  "theme.json_modal_title_import": "Import theme",
  "theme.marble_preset_title": "Built-in marble preset to apply to the active theme",
  "theme.mode_active_theme": "Active theme",
  "theme.mode_clear_device": "Clear device override",
  "theme.mode_follow_system": "Follow system",
  "theme.mode_label": "Theme mode",  // label for the theme appearance selector (follow system / this device only)
  "theme.mode_mode": "Mode",  // theme appearance scope label: 'this device only' vs follow-system; NOT clean mode
  "theme.mode_note": "Theme edits are shared. Only the <em>selected</em> theme is local to this browser.",
  "theme.mode_this_device": "This device only",
  "theme.mode_this_device_only": "this device only",  // theme appearance scope value: applies only on this browser/device
  "theme.mode_use_everywhere": "Use everywhere",
  "theme.modified_only": "Modified Only",
  "theme.no_tokens_match_filters": "No tokens match the current theme filters.",
  "theme.preset_active": "Active",  // badge on a theme card: this is the currently applied theme
  "theme.presets_empty": "No themes available.",
  "theme.presets_no_match": "No themes match these filters.",
  "theme.save_as_new": "Save as New",
  "theme.save_changes": "Save Changes",
  "theme.search_themes_placeholder": "Search themes...",
  "theme.search_toggle": "Search and filter",  // accessible name for the caret that collapses/expands the token search row; state is carried by aria-expanded, so this label stays constant in both directions
  "theme.search_tokens_placeholder": "Search tokens...",
  "theme.tab_palette": "Palette",
  "theme.tab_themes": "Themes",
  "theme.tab_tokens": "Tokens",  // sub-tab name: the CSS design-token editor list (jargon, keep as 'tokens')
  "theme.tag_add_placeholder": "add a tag…",
  "theme.tag_done_title": "Done editing tags",
  "theme.tag_edit_title": "Edit tags",
  "theme.tag_remove_title": "Remove tag",
  "theme.token_default_placeholder": "Default",  // Greyed placeholder in an empty token text input meaning 'uses the default value'; a hint, not a Default button/action.
  "theme.token_draft": "Draft",  // chip on a token row: this token value is an unsaved/draft edit
  "theme.upload": "Upload",
  "theme.upload_title": "Upload a theme .json file",

  // --- theme_preview (theme editor preview pane + group registry titles/descriptions) ---
  "theme_preview.animal.battery_charging_hint": "pulses",  // hint under the 'Charging' band: the animal's eye pulses while charging (verb, eye is subject)
  "theme_preview.animal.battery_charging_label": "Charging",  // battery-band label 'Charging' for the animal-companion preview row (sibling to Mid/Warn)
  "theme_preview.animal.battery_good_hint": "battery > 50%",
  "theme_preview.animal.battery_good_label": "Good",  // battery-band label 'Good' (>50%) for the animal-companion preview row
  "theme_preview.animal.battery_low_hint": "≤ 15%",
  "theme_preview.animal.battery_low_label": "Low",  // battery-band label 'Low' (<=15%) for the animal preview row; NOT water/suction Low
  "theme_preview.animal.battery_mid_hint": "25–50%",
  "theme_preview.animal.battery_mid_label": "Mid",  // battery-band label 'Mid' (25-50%) for the animal-companion preview row
  "theme_preview.animal.battery_warn_hint": "15–25%",
  "theme_preview.animal.battery_warn_label": "Warn",  // battery-band label 'Warn' (15-25%) for the animal-companion eye-color preview row
  "theme_preview.animal.parent_note": "Tokens in this <em>parent</em> group apply across <strong>every</strong> animal. The five eye-color tokens (<code>--evcc-animal-eye-*</code>) drive the rows; the global palette tokens (<code>--evcc-animal-fur</code>, <code>--evcc-animal-pupil</code>, etc.) drive every body. Use the per-animal sub-groups below to override for a single animal.",
  "theme_preview.animal.subgroup_note": "Tokens in this sub-group (prefixed <code>--evcc-animal-{animal}-…</code>) override the global Animal Companion tokens for just the {animal}. Leave any token unset to inherit the parent value (or the {animal}'s own built-in default if no theme value is set).",
  "theme_preview.borders.border_strength": "Border Strength",
  "theme_preview.borders.card_shadow": "Card shadow",
  "theme_preview.borders.default": "Default border",
  "theme_preview.borders.hover_shadow": "Hover shadow",
  "theme_preview.borders.shadow_depth": "Shadow Depth",
  "theme_preview.borders.strong": "Strong border",
  "theme_preview.borders.subtle": "Subtle border",
  "theme_preview.chips.active": "Active",  // theme-editor sample chip showing the 'active' visual state; demo label, not a real toggle
  "theme_preview.chips.default": "Default",  // theme-editor sample chip in default state; demo swatch label
  "theme_preview.chips.excluded": "Excluded",  // theme-editor sample chip in the 'excluded' state; demo swatch, not a real exclude action
  "theme_preview.chips.hover": "Hover",  // theme-editor sample chip in 'hover' state; demo swatch label
  "theme_preview.chips.included": "Included",  // theme-editor sample chip in the 'included' state; demo swatch, not the room include control
  "theme_preview.chips.matrix": "Chip Matrix",  // heading for the chip-swatch demo grid in the theme editor
  "theme_preview.chips.success": "Success",  // theme-editor sample chip showing 'success' color; demo swatch label
  "theme_preview.chips.warning": "Warning",  // theme-editor sample chip showing 'warning' color; demo swatch, not a real alert
  "theme_preview.confidence.building": "Building confidence",  // theme-editor demo badge: confidence still being built; preview only
  "theme_preview.confidence.high": "High confidence",  // theme-editor demo confidence badge (High); previews badge color, not a real confidence value
  "theme_preview.confidence.low": "Low confidence",  // theme-editor demo confidence badge (Low); previews badge color only
  "theme_preview.confidence.medium": "Medium confidence",  // theme-editor demo confidence badge (Medium); previews badge color only
  "theme_preview.eyebrow": "Contextual Preview",  // small overline 'Contextual Preview' above the theme preview pane
  "theme_preview.floor.carpet_high": "Carpet High",
  "theme_preview.floor.carpet_low": "Carpet Low",
  "theme_preview.floor.concrete": "Concrete",
  "theme_preview.floor.granite": "Granite",  // swatch label for the granite floor texture (maps to granite_light key)
  "theme_preview.floor.marble": "Marble",
  "theme_preview.floor.tile": "Tile",  // swatch label for the tile floor texture in the preview grid
  "theme_preview.floor.wood": "Wood",  // swatch label for the wood floor texture in the preview grid
  "theme_preview.foundations.chip": "Chip",  // plain sample chip labeled 'Chip' in the foundations preview; demo swatch
  "theme_preview.foundations.composite_desc": "Foundations touch multiple systems, so the preview intentionally mixes a few representative surfaces.",
  "theme_preview.foundations.composite_sample": "Composite Sample",
  "theme_preview.foundations.foundation_input": "Foundation input",
  "theme_preview.foundations.mixed_desc": "Shared gap, radius, font, hover lift, and transition values show up here together.",
  "theme_preview.foundations.mixed_surface": "Mixed Surface",
  "theme_preview.foundations.surface_stack": "Surface Stack",
  "theme_preview.group.animal.desc": "A single representative animal across all five battery-state bands. Eye-color and global palette tokens in this group apply across every animal.",
  "theme_preview.group.animal.title": "Animal Companion Preview",
  "theme_preview.group.animal_sub.desc": "The {animal} across all five battery-state bands. Tokens in this sub-group (prefixed --evcc-animal-{animal}-) override the global Animal Companion palette and eye-state colors for just the {animal}.",
  "theme_preview.group.animal_sub.title": "{animal} Preview",
  "theme_preview.group.borders.desc": "Border strength and elevation samples reveal separation, depth, and hover lift.",
  "theme_preview.group.borders.title": "Borders & Shadows Preview",
  "theme_preview.group.chips.desc": "A compact chip matrix highlights default, active, hover, success, warning, and excluded states.",
  "theme_preview.group.chips.title": "Chip Preview",
  "theme_preview.group.floor.desc": "Live swatches show each material's overlay on the card surface. Opacity, scale, and tint tokens update in real time.",
  "theme_preview.group.floor.title": "Floor Texture Preview",
  "theme_preview.group.floor_carpet_high.desc": "Base color tints the high-pile carpet texture layer on the card surface.",
  "theme_preview.group.floor_carpet_high.title": "Carpet High Pile Preview",
  "theme_preview.group.floor_carpet_low.desc": "Base color tints the low-pile carpet texture layer on the card surface.",
  "theme_preview.group.floor_carpet_low.title": "Carpet Low Pile Preview",
  "theme_preview.group.floor_concrete.desc": "Base color tints the concrete texture layer on the card surface.",
  "theme_preview.group.floor_concrete.title": "Concrete Floor Preview",
  "theme_preview.group.floor_granite.desc": "Base color tints the granite texture layer on the card surface.",
  "theme_preview.group.floor_granite.title": "Granite Floor Preview",
  "theme_preview.group.floor_marble.desc": "Base color tints the marble texture layer on the card surface.",
  "theme_preview.group.floor_marble.title": "Marble Floor Preview",
  "theme_preview.group.floor_tile.desc": "Base and accent colors control the grout lines and tile face on card and map surfaces.",
  "theme_preview.group.floor_tile.title": "Tile Floor Preview",
  "theme_preview.group.floor_wood.desc": "Base and accent colors control the wood grain, seam lines, and directional depth layers.",
  "theme_preview.group.floor_wood.title": "Wood Floor Preview",
  "theme_preview.group.foundations.desc": "A mixed control-surface preview shows spacing, radius, motion, and typography primitives together.",
  "theme_preview.group.foundations.title": "Shared Foundations Preview",
  "theme_preview.group.learning.desc": "Estimate badges and learning panels preview predictive and analytical surfaces.",
  "theme_preview.group.learning.title": "Learning & Metrics Preview",
  "theme_preview.group.modal.desc": "A modal shell sample isolates overlay surfaces, chips, warning states, and backdrop treatment.",
  "theme_preview.group.modal.title": "Modal & Overlay Preview",
  "theme_preview.group.queue.desc": "Queue strip, order chips, and drag feedback samples show sequencing and reorder states.",
  "theme_preview.group.queue.title": "Queue & Ordering Preview",
  "theme_preview.group.rooms.desc": "Mini room cards expose profile chips, room chips, and room-surface treatment together.",
  "theme_preview.group.rooms.title": "Room Card Preview",
  "theme_preview.group.shell.desc": "Accent, heading, and body text examples show the shell voice this group controls.",
  "theme_preview.group.shell.title": "Shell & Typography Preview",
  "theme_preview.group.status.desc": "Status dots, confidence badges, and alert surfaces show semantic state color relationships.",
  "theme_preview.group.status.title": "Status & Alerts Preview",
  "theme_preview.group.surfaces.desc": "Shared card, panel, and input surfaces show the base material language for the editor.",
  "theme_preview.group.surfaces.title": "Cards & Surfaces Preview",
  "theme_preview.learning.estimate_badges": "Estimate Badges",
  "theme_preview.learning.estimate_default": "~{min} min default",
  "theme_preview.learning.estimate_learned": "~{min} min learned",
  "theme_preview.learning.panel": "Learning Panel",
  "theme_preview.learning.reanchor_note": "Re-anchor suggested after a long interrupted run.",  // demo note; 're-anchor' = re-establish the learned-timing baseline after an odd run (term of art)
  "theme_preview.learning.tank_after": "Tank after run: {ml} ml ({pct}%)",
  "theme_preview.learning.water_use": "Estimated water use: {ml} ml",
  "theme_preview.modal.accent_chip": "Accent chip",
  "theme_preview.modal.cannot_undo": "This action cannot be undone.",
  "theme_preview.modal.confirm": "Confirm",  // demo 'Confirm' button inside the sample modal preview; inert, not a real confirm
  "theme_preview.modal.subtitle": "Overlay shell preview",
  "theme_preview.modal.title": "Maintenance Reset",
  "theme_preview.modal.type_note": "Type a note...",
  "theme_preview.queue.cat_room": "Cat Room",  // fictitious placeholder room name 'Cat Room' in the sample queue strip; demo, not a feature
  "theme_preview.queue.dragging": "Dragging",
  "theme_preview.queue.drop_target": "Drop target",
  "theme_preview.queue.entry": "Entry",  // placeholder room name 'Entry' (entryway) in the sample queue strip; fictitious
  "theme_preview.queue.office": "Office",
  "theme_preview.queue.strip": "Queue Strip",
  "theme_preview.rooms.area_rug": "Area Rug",
  "theme_preview.rooms.custom_profile": "Custom Profile",
  "theme_preview.rooms.daily_vacuum": "Daily Vacuum",
  "theme_preview.rooms.hallway": "Hallway",  // placeholder room name in the theme-preview sample card; fictitious example
  "theme_preview.rooms.hardwood": "Hardwood",  // placeholder floor-type chip in a sample room card; demo content
  "theme_preview.rooms.kitchen": "Kitchen",  // placeholder room name in the theme-preview sample card; fictitious example
  "theme_preview.rooms.profile_label": "Profile",  // demo field label 'Profile' inside a sample room card in the theme preview
  "theme_preview.rooms.room_label": "Room",  // demo field label 'Room' inside a sample room card in the theme preview
  "theme_preview.shell.accent": "Accent",
  "theme_preview.shell.copy": "Primary and secondary text plus accent styling define the card’s voice before any specific feature surface appears.",
  "theme_preview.shell.heading": "Premium vacuum control, calmly organized.",
  "theme_preview.shell.kicker": "EVCC Shell",  // 'EVCC Shell' overline label in the shell typography preview; product acronym, keep as-is
  "theme_preview.shell.open_metrics": "Open Metrics",
  "theme_preview.shell.text_muted": "Muted text handles metadata, helper copy, and low-priority hints.",
  "theme_preview.shell.text_primary": "Primary text anchors the main reading path.",
  "theme_preview.shell.text_secondary": "Secondary text supports controls and summaries without overpowering them.",
  "theme_preview.shell.text_stack": "Text Stack",
  "theme_preview.status.cleaning": "Cleaning",  // theme-editor demo status dot labeled 'Cleaning'; previews dot color, not live state
  "theme_preview.status.confidence_alerts": "Confidence & Alerts",
  "theme_preview.status.docked": "Docked",  // theme-editor demo status dot labeled 'Docked'; previews dot color, not live state
  "theme_preview.status.dots": "Status Dots",
  "theme_preview.status.error": "Error",  // theme-editor demo status dot labeled 'Error'; previews dot color, not a real error
  "theme_preview.status.error_surface": "Error surface",  // theme-editor demo alert box previewing the 'error' surface color
  "theme_preview.status.idle": "Idle",  // theme-editor demo status dot labeled 'Idle'; previews dot color, not live robot state
  "theme_preview.status.info_surface": "Information surface",  // theme-editor demo alert box previewing the 'info' surface color
  "theme_preview.status.warning_surface": "Warning surface",  // theme-editor demo alert box previewing the 'warning' surface color
  "theme_preview.surfaces.card_desc": "Shared card background, gap, padding, and surface treatment.",
  "theme_preview.surfaces.card_surface": "Card Surface",
  "theme_preview.surfaces.panel_desc": "Panel surfaces and nested inputs preview layered elevation.",
  "theme_preview.surfaces.panel_input": "Panel + Input",
  "theme_preview.surfaces.raised_card": "Raised Card",
  "theme_preview.surfaces.search_tokens": "Search tokens...",  // demo input placeholder 'Search tokens...'; tokens = theme/CSS tokens, not auth/security tokens

  // --- toast ---
  "toast.dismiss": "Dismiss",

  // --- Wave-1 vocabulary + bare/template additions (auto-applied from the leak audit) ---
  "vocab.metrics_tab.learning": "Learning",
  "vocab.metrics_tab.rooms": "Rooms",
  "vocab.metrics_tab.profiles": "Profiles",
  "vocab.metrics_tab.water": "Water",
  "vocab.metrics_tab.dock": "Dock",
  "vocab.metrics_tab.battery": "Battery",
  "vocab.battery_bucket_key.vacuum": "Vacuum",
  "vocab.battery_bucket_key.mop": "Mop",
  "vocab.battery_bucket_key.vacuum_mop": "Vacuum and mop",
  "vocab.battery_bucket_key.vacuum_and_mop": "Vacuum and mop", // alias: display-string form the stored profiles use
  "vocab.battery_bucket_key.quiet": "Quiet",
  "vocab.battery_bucket_key.gentle": "Gentle",
  "vocab.battery_bucket_key.balanced": "Balanced",
  "vocab.battery_bucket_key.standard": "Standard",
  "vocab.battery_bucket_key.boost": "Boost",
  "vocab.battery_bucket_key.turbo": "Turbo",
  "vocab.battery_bucket_key.max": "Max",
  "vocab.battery_bucket_key.off": "Off",
  "vocab.battery_bucket_key.low": "Low",
  "vocab.battery_bucket_key.medium": "Medium",
  "vocab.battery_bucket_key.high": "High",
  "vocab.battery_weighted_by.estimated_minutes": "Est. minutes",  // last-job %/m² weighting basis: the estimated per-room minutes
  "vocab.battery_weighted_by.actual_minutes": "Actual minutes",   // weighting basis: the actual measured minutes
  "vocab.battery_weighted_by.room_count": "Room count",
  "vocab.battery_weighted_by.none": "None",
  // RP-045: battery-health "unavailable" reason code -> sentence (tVocabRaw,
  // falls back to the backend's health_unavailable_reason_text for any code
  // not keyed here yet — see src/renderers/metrics.js).
  "vocab.health_unavailable_reason.insufficient_discharge_data": "No completed charge has started at 50% or lower and reached 90% or higher, so there's no baseline to compare against yet. A vacuum that docks frequently and rarely runs low may never produce one on its own.",
  "vocab.status.completed": "Completed",
  "vocab.status.canceled": "Canceled",
  "vocab.status.cancelled": "Cancelled",  // British spelling — the value the learning/metrics backend actually emits
  "vocab.status.failed": "Failed",
  "vocab.status.interrupted": "Interrupted",
  "vocab.job_scope.single_room": "Single Room",  // learning-review job coverage: one room cleaned
  "vocab.job_scope.multi_room": "Multi Room",     // learning-review job coverage: several rooms in one run
  // Origin filter chip VALUES (review history): external = app-started/captured; internal = dispatched by this integration.
  "vocab.origin.external": "External",
  "vocab.origin.internal": "Dispatched",
  // Device-status VALUES shown in the header next to "Vacuum status:" / "Dock status:".
  // Union of the HA vacuum-entity states + the Eufy dock_status sensor strings; tVocab
  // falls back to the backend label for any state not keyed here.
  "vocab.device_status.cleaning": "Cleaning",
  "vocab.device_status.docked": "Docked",
  "vocab.device_status.idle": "Idle",
  "vocab.device_status.paused": "Paused",
  "vocab.device_status.returning": "Returning",
  "vocab.device_status.error": "Error",
  "vocab.device_status.charging": "Charging",
  "vocab.device_status.standby": "Standby",
  "vocab.device_status.washing": "Washing",
  "vocab.device_status.washing_mop": "Washing Mop",
  "vocab.device_status.drying": "Drying",
  "vocab.device_status.drying_mop": "Drying Mop",
  "vocab.device_status.emptying": "Emptying",
  "vocab.device_status.emptying_dust": "Emptying Dust",
  "vocab.device_status.fault": "Fault",
  "vocab.device_status.offline": "Offline",
  "vocab.device_status.unavailable": "Unavailable",
  "vocab.device_status.unknown": "Unknown",
  "vocab.used_for_learning.true": "Used For Learning",
  "vocab.used_for_learning.false": "Excluded From Learning",  // matches the backend filter label
  "vocab.trust_level.none": "None",  // learning trust/confidence tier on a room/profile estimate
  "vocab.trust_level.building": "Building",
  "vocab.trust_level.low": "Low",
  "vocab.trust_level.medium": "Medium",
  "vocab.trust_level.good": "Good",
  "vocab.trust_level.high": "High",
  "vocab.trust_level.trusted": "Trusted",
  "vocab.maintenance_component.filter": "Filter",  // consumable/part names shown on the Maintenance cards
  "vocab.maintenance_component.sensor": "Sensor",
  "vocab.maintenance_component.side_brush": "Side Brush",
  "vocab.maintenance_component.rolling_brush": "Rolling Brush",
  "vocab.maintenance_component.mopping_cloth": "Mopping Cloth",
  "vocab.maintenance_component.cleaning_tray": "Cleaning Tray",
  "vocab.maintenance_component.swivel_wheel": "Swivel Wheel",
  "vocab.maintenance_kind.maintenance": "Maintenance",  // upkeep card kind: a cleanable item
  "vocab.maintenance_kind.replacement": "Replacement",  // upkeep card kind: a replaceable consumable
  // estimate trust-reason sentences (learning manager codes) — shown on metrics found-profile cards
  "vocab.estimate_reason.excluded_from_learning": "This run is currently excluded from learning.",
  "vocab.estimate_reason.cancel_like": "This run looks like a canceled run.",
  "vocab.estimate_reason.cancelled": "This run ended as a cancelled job.",
  "vocab.estimate_reason.failed": "This run ended as a failed job.",
  "vocab.estimate_reason.interrupted": "This run ended as an interrupted job.",
  "vocab.estimate_reason.completed": "This run completed normally.",
  "vocab.estimate_reason.test": "This run is marked as a test job.",
  "vocab.estimate_reason.no_learning_runs": "There are not enough learned runs yet.",
  "vocab.estimate_reason.building_samples": "The system is still building enough history to trust this estimate.",
  "vocab.estimate_reason.accuracy_observed": "Trust is supported by real estimate-versus-actual history.",
  "vocab.estimate_reason.not_enough_accuracy_data": "More estimate-versus-actual history is needed before trust can improve.",
  "vocab.estimate_reason.missing_timestamps": "The run did not have enough timestamp data to classify reliably.",
  "vocab.estimate_reason.not_single_room": "Cancel-likely detection currently only applies to single-room jobs.",
  "vocab.estimate_reason.no_transition_history": "No state-transition history was available for this run.",
  "vocab.estimate_reason.service_state_explains_return": "The return looked like a normal service cycle rather than a cancel.",
  "vocab.estimate_reason.no_cancel_like_transition": "No cancel-like transition pattern was observed.",
  // dock-action gate reasons (base-station cards) — keyed on the backend reason code
  "vocab.dock_reason.ready": "Ready.",
  "vocab.dock_reason.unsupported_feature": "This vacuum does not support that dock action.",
  "vocab.dock_reason.missing_action_entity": "The upstream dock control entity was not found.",
  "vocab.dock_reason.job_active": "Finish, pause, or cancel the tracked job before using dock actions.",
  "vocab.dock_reason.not_docked": "The vacuum must be docked before using that dock action.",
  "vocab.dock_reason.already_washing": "The dock is already washing the mop.",
  "vocab.dock_reason.already_drying": "The dock is already drying the mop.",
  "vocab.dock_reason.not_drying": "Stop dry is only useful while the dock is actively drying.",
  "vocab.dock_reason.already_emptying": "The dock is already emptying dust.",
  "vocab.dock_reason.dock_busy": "The dock is currently busy with another service action.",
  "vocab.resegment_reason.capped_to_detectable": "Capped to the rooms detectable from this run.",  // External-run review: shown when the requested room count exceeded the number of boundaries detectable from the captured run, so it was limited.
  "vocab.sort.newest": "Newest",
  "vocab.sort.outlier": "Highest Outlier",
  "vocab.sort.suggested": "Suggested Exclude",
  "vocab.sort.excluded": "Excluded Only",
  "vocab.exclude_reason.short_test_cancel": "Short Test Cancel",
  "vocab.exclude_reason.manual_test_run": "Manual Test Run",
  "vocab.exclude_reason.false_completion": "False Completion",
  "vocab.exclude_reason.bad_room_attribution": "Bad Room Attribution",
  "vocab.exclude_reason.interrupted_run": "Interrupted Run",
  "vocab.exclude_reason.custom": "Custom…",  // Exclude-reason chip that reveals a free-text input for a user-typed reason
  // Auto-exclude suggestion BADGE on Learning Review job cards — terse chip labels
  // keyed on the stable exclude_suggested_reason code (manager.py emits cancelled/
  // failed/interrupted/failed_sanity/cancel-detection reason/short_duration_vs_*).
  // tVocabRaw'd at review.js; falls back to the backend label for any unkeyed code.
  "vocab.exclude_suggested_reason.cancelled": "Cancelled run",
  "vocab.exclude_suggested_reason.failed": "Failed run",
  "vocab.exclude_suggested_reason.interrupted": "Interrupted run",
  "vocab.exclude_suggested_reason.failed_sanity": "Failed sanity check",
  "vocab.exclude_suggested_reason.floor_time_too_short": "Floor time too short",
  "vocab.exclude_suggested_reason.early_return_likely_cancelled": "Returned early",
  "vocab.exclude_suggested_reason.cancel_like": "Looks cancelled",
  "vocab.exclude_suggested_reason.short_duration_vs_profile": "Short vs profile",
  "vocab.exclude_suggested_reason.short_duration_vs_room": "Short vs room",
  // Per-job "This run …" explanatory NOTE on Learning Review job cards — full
  // sentences keyed on the stable reason code. One shared namespace because the
  // note sources overlap (status / learning blockers / sanity flags / cancel
  // reasons / exclude reasons reuse the same codes). Sourced verbatim from the
  // backend _reason_text() where present; fresh sentences for codes that only
  // title-cased before. tVocabRaw'd; falls back per-code to the backend sentence.
  "vocab.reason_code.completed": "This run completed normally.",
  "vocab.reason_code.cancelled": "This run ended as a cancelled job.",
  "vocab.reason_code.failed": "This run ended as a failed job.",
  "vocab.reason_code.interrupted": "This run ended as an interrupted job.",
  "vocab.reason_code.test": "This run is marked as a test job.",
  "vocab.reason_code.job_cancelled": "The job was cancelled before it finished.",
  "vocab.reason_code.job_failed": "The job failed before it finished.",
  "vocab.reason_code.job_interrupted": "The job was interrupted before it finished.",
  "vocab.reason_code.test_job": "This run is marked as a test job.",
  "vocab.reason_code.manually_excluded": "This run was manually excluded from learning.",
  "vocab.reason_code.excluded_from_learning": "This run is currently excluded from learning.",
  "vocab.reason_code.invalid_room_count": "This run did not record a valid number of rooms.",
  "vocab.reason_code.invalid_duration": "This run did not record a valid duration.",
  "vocab.reason_code.missing_resolved_rooms": "No rooms could be matched for this run.",
  "vocab.reason_code.failed_sanity": "This run failed the backend sanity checks.",
  "vocab.reason_code.short_duration_vs_profile": "Much shorter than this profile usually takes.",
  "vocab.reason_code.short_duration_vs_room": "Much shorter than this room usually takes.",
  "vocab.reason_code.cancel_like": "This run looks like a canceled run.",
  "vocab.reason_code.cancel_likely": "This run looks like it was canceled.",
  "vocab.reason_code.floor_time_too_short": "Floor-cleaning time was too short for a real run.",
  "vocab.reason_code.early_return_likely_cancelled": "The vacuum returned early, so this run was likely canceled.",
  "vocab.reason_code.short_test_cancel": "Looks like a short test run that was canceled early.",
  "vocab.reason_code.manual_test_run": "Marked as a manual test run.",
  "vocab.reason_code.false_completion": "This run appears to have ended before cleaning really completed.",
  "vocab.reason_code.bad_room_attribution": "Room attribution for this run looks unreliable.",
  "vocab.reason_code.interrupted_run": "This run appears to have been interrupted.",
  "vocab.reason_code.extreme_idle_wall": "Held from learning — an unusually long idle stretch off the dock, so it does not define a room baseline. Restore it if the run was legitimate.",
  "setup.panel_name_placeholder": "Vacuum Agent",
  "order_modal.move_item": "Move {label}",
  "order_modal.currently": "Currently",
  "order_modal.after_move": "After move",
  "order_modal.move_to_position": "Move to position",
  "rooms.trouble_missed": { one: "Missed {miss}× of {count} run", other: "Missed {miss}× of {count} runs" },

  // --- vocab: setting_field (per-room SETTING names — preflight "settings adjusted" list, rule-card effect summaries) ---
  "vocab.setting_field.clean_mode": "Clean Mode",
  "vocab.setting_field.fan_speed": "Fan Speed",
  "vocab.setting_field.water_level": "Water Level",
  "vocab.setting_field.clean_intensity": "Cleaning Path",  // Matches the established UI name for clean_intensity (path density), see external_jobs.setting_cleaning_path
  "vocab.setting_field.clean_passes": "Cleaning Passes",
  "vocab.setting_field.edge_mopping": "Edge Mopping",
  // --- vocab: snapshot_reason (metrics/review unavailable-state CODES from the backend) ---
  "vocab.snapshot_reason.no_learning_data": "No learned history is available yet.",
  // --- vocab: compose_shape (custom-segment composer shape types) ---
  "vocab.compose_shape.rect": "rectangle",
  "vocab.compose_shape.circle": "circle",
  // --- vocab: obstacle_type (Roborock AI obstacle markers; backend normalizes the parser's type ints to these slugs — unknown ints arrive as the number string and fall back raw) ---
  "vocab.obstacle_type.cable": "cable",
  "vocab.obstacle_type.pet_waste": "pet waste",
  "vocab.obstacle_type.shoes": "shoes",
  "vocab.obstacle_type.poop": "poop",
  "vocab.obstacle_type.pedestal": "pedestal",
  "vocab.obstacle_type.extension_cord": "extension cord",
  "vocab.obstacle_type.weighing_scale": "weighing scale",
  "vocab.obstacle_type.clothes": "clothes",
  "vocab.obstacle_type.dustpan": "dustpan",
  "vocab.obstacle_type.furniture_crossbar": "furniture with a crossbar",
  "vocab.obstacle_type.pet": "pet",
  "vocab.obstacle_type.fabric_paper_balls": "fabric or paper balls",
  // --- Wave-2 theme-editor vocabulary (token labels / groups / facets / tags) ---
  // --- vocab: token_type (the small type chip on every theme-editor token row) ---
  "vocab.token_type.color": "color",
  "vocab.token_type.text": "text",
  "vocab.token_type.shadow": "shadow",
  "vocab.token_type.size": "size",
  "vocab.token_type.number": "number",
  "vocab.token_type.duration": "duration",
  "vocab.token_type.motion": "motion",
  "vocab.token_type.typography": "typography",
  "vocab.token_type.easing": "easing",
  "vocab.theme_token.evcc_accent": "Accent",
  "vocab.theme_token.evcc_accent_soft": "Accent Soft",
  "vocab.theme_token.evcc_text_muted": "Text Muted",
  "vocab.theme_token.evcc_text_on_accent": "Text On Accent",
  "vocab.theme_token.evcc_text_primary": "Text Primary",
  "vocab.theme_token.evcc_text_secondary": "Text Secondary",
  "vocab.theme_token.evcc_text_strong": "Text Strong",
  "vocab.theme_token.evcc_bg_input": "BG Input",
  "vocab.theme_token.evcc_card_bg": "Card BG",
  "vocab.theme_token.evcc_card_gap": "Card Gap",
  "vocab.theme_token.evcc_card_min_height": "Card Min Height",
  "vocab.theme_token.evcc_card_padding": "Card Padding",
  "vocab.theme_token.evcc_panel_bg": "Panel BG",
  "vocab.theme_token.evcc_surface_action": "Surface Action",
  "vocab.theme_token.evcc_surface_action_hover": "Surface Action Hover",
  "vocab.theme_token.evcc_surface_base": "Surface Base",
  "vocab.theme_token.evcc_surface_card": "Surface Card",
  "vocab.theme_token.evcc_surface_chip": "Surface Chip",
  "vocab.theme_token.evcc_surface_input": "Surface Input",
  "vocab.theme_token.evcc_surface_overlay": "Surface Overlay",
  "vocab.theme_token.evcc_surface_panel": "Surface Panel",
  "vocab.theme_token.evcc_surface_raised": "Surface Raised",
  "vocab.theme_token.evcc_surface_subtle": "Surface Subtle",
  "vocab.theme_token.evcc_surface_sunken": "Surface Sunken",
  "vocab.theme_token.evcc_surface_warning": "Surface Warning",
  "vocab.theme_token.evcc_border_default": "Border Default",
  "vocab.theme_token.evcc_border_strong": "Border Strong",
  "vocab.theme_token.evcc_border_subtle": "Border Subtle",
  "vocab.theme_token.evcc_border_warning": "Border Warning",
  "vocab.theme_token.evcc_shadow_card": "Shadow Card",
  "vocab.theme_token.evcc_shadow_hover": "Shadow Hover",
  "vocab.theme_token.evcc_chip_active_bg": "Chip Active BG",
  "vocab.theme_token.evcc_chip_active_border": "Chip Active Border",
  "vocab.theme_token.evcc_chip_active_text": "Chip Active Text",
  "vocab.theme_token.evcc_chip_bg": "Chip BG",
  "vocab.theme_token.evcc_chip_border": "Chip Border",
  "vocab.theme_token.evcc_chip_excluded_bg": "Chip Excluded BG",
  "vocab.theme_token.evcc_chip_excluded_border": "Chip Excluded Border",
  "vocab.theme_token.evcc_chip_excluded_text": "Chip Excluded Text",
  "vocab.theme_token.evcc_chip_font_size": "Chip Font Size",
  "vocab.theme_token.evcc_chip_font_weight": "Chip Font Weight",
  "vocab.theme_token.evcc_chip_gap": "Chip Gap",
  "vocab.theme_token.evcc_chip_height": "Chip Height",
  "vocab.theme_token.evcc_chip_hover_bg": "Chip Hover BG",
  "vocab.theme_token.evcc_chip_hover_border": "Chip Hover Border",
  "vocab.theme_token.evcc_chip_hover_text": "Chip Hover Text",
  "vocab.theme_token.evcc_chip_icon_height": "Chip Icon Height",
  "vocab.theme_token.evcc_chip_icon_padding": "Chip Icon Padding",
  "vocab.theme_token.evcc_chip_icon_size": "Chip Icon Size",
  "vocab.theme_token.evcc_chip_included_bg": "Chip Included BG",
  "vocab.theme_token.evcc_chip_included_border": "Chip Included Border",
  "vocab.theme_token.evcc_chip_included_text": "Chip Included Text",
  "vocab.theme_token.evcc_chip_neutral_bg": "Chip Neutral BG",
  "vocab.theme_token.evcc_chip_padding": "Chip Padding",
  "vocab.theme_token.evcc_chip_radius": "Chip Radius",
  "vocab.theme_token.evcc_chip_success_bg": "Chip Success BG",
  "vocab.theme_token.evcc_chip_success_border": "Chip Success Border",
  "vocab.theme_token.evcc_chip_success_text": "Chip Success Text",
  "vocab.theme_token.evcc_chip_text": "Chip Text",
  "vocab.theme_token.evcc_chip_warning_bg": "Chip Warning BG",
  "vocab.theme_token.evcc_chip_warning_border": "Chip Warning Border",
  "vocab.theme_token.evcc_chip_warning_text": "Chip Warning Text",
  "vocab.theme_token.evcc_profile_chip_bg": "Profile Chip BG",
  "vocab.theme_token.evcc_profile_chip_border": "Profile Chip Border",
  "vocab.theme_token.evcc_profile_chip_custom_bg": "Profile Chip Custom BG",
  "vocab.theme_token.evcc_profile_chip_custom_border": "Profile Chip Custom Border",
  "vocab.theme_token.evcc_profile_chip_custom_text": "Profile Chip Custom Text",
  "vocab.theme_token.evcc_profile_chip_text": "Profile Chip Text",
  "vocab.theme_token.evcc_room_chip_bg": "Room Chip BG",
  "vocab.theme_token.evcc_room_chip_border": "Room Chip Border",
  "vocab.theme_token.evcc_room_chip_text": "Room Chip Text",
  "vocab.theme_token.evcc_room_fill_1": "Map Room Color 1",
  "vocab.theme_token.evcc_room_fill_2": "Map Room Color 2",
  "vocab.theme_token.evcc_room_fill_3": "Map Room Color 3",
  "vocab.theme_token.evcc_room_fill_4": "Map Room Color 4",
  "vocab.theme_token.evcc_room_fill_5": "Map Room Color 5",
  "vocab.theme_token.evcc_room_fill_6": "Map Room Color 6",
  "vocab.theme_token.evcc_room_fill_7": "Map Room Color 7",
  "vocab.theme_token.evcc_room_fill_8": "Map Room Color 8",
  "vocab.theme_token.evcc_room_fill_9": "Map Room Color 9",
  "vocab.theme_token.evcc_room_fill_10": "Map Room Color 10",
  "vocab.theme_token.evcc_room_fill_11": "Map Room Color 11",
  "vocab.theme_token.evcc_room_fill_12": "Map Room Color 12",
  "vocab.theme_token.evcc_room_fill_opacity": "Room Card Opacity",
  "vocab.theme_token.evcc_room_grid_columns": "Room Grid Columns",
  "vocab.theme_token.evcc_room_grid_gap": "Room Grid Gap",
  "vocab.theme_token.evcc_room_grid_min": "Room Grid Min",
  "vocab.theme_token.evcc_map_label_bg": "Map Label Background",
  "vocab.theme_token.evcc_map_label_text": "Map Label Text",
  "vocab.theme_token.evcc_map_label_text_selected": "Map Label Text (Selected)",
  "vocab.theme_token.evcc_map_label_order_text": "Map Order Badge Text",
  "vocab.theme_token.evcc_map_tooltip_bg": "Map Tooltip Background",
  "vocab.theme_token.evcc_map_tooltip_border": "Map Tooltip Border",
  "vocab.theme_token.evcc_map_tooltip_text": "Map Tooltip Text",
  "vocab.theme_token.evcc_map_tooltip_hint": "Map Tooltip Hint Text",
  "vocab.theme_token.evcc_map_compose_selected_stroke": "Composer Selected Outline",
  "vocab.theme_token.evcc_map_compose_cut_fill": "Composer Cutout Fill",
  "vocab.theme_token.evcc_map_compose_cut_selected_fill": "Composer Cutout Fill (Selected)",
  "vocab.theme_token.evcc_map_vertex_selected_glow": "Composer Selected Vertex Glow",
  "vocab.theme_token.evcc_map_ov_current": "Overlay: Current Room",
  "vocab.theme_token.evcc_map_ov_nogo": "Overlay: No-Go Zone",
  "vocab.theme_token.evcc_map_ov_nomop": "Overlay: No-Mop Zone",
  "vocab.theme_token.evcc_map_ov_wall": "Overlay: Virtual Wall",
  "vocab.theme_token.evcc_map_ov_zone": "Overlay: Saved Zone",
  "vocab.theme_token.evcc_map_ov_path": "Overlay: Cleaning Path",
  "vocab.theme_token.evcc_map_ov_robot": "Overlay: Robot Marker",
  "vocab.theme_token.evcc_map_ov_dock": "Overlay: Dock Marker",
  "vocab.theme_token.evcc_map_ov_obstacle": "Overlay: Obstacle Marker",
  "vocab.theme_token.evcc_map_ov_area_text": "Overlay: Area Label Text",
  "vocab.theme_token.evcc_floor_textures_card_enabled": "Card Textures Enabled (0/1)",
  "vocab.theme_token.evcc_floor_textures_map_enabled": "Map Textures Enabled (0/1)",
  "vocab.theme_token.evcc_floor_texture_opacity_card": "Card Texture Opacity (all)",
  "vocab.theme_token.evcc_floor_texture_opacity_map": "Map Texture Opacity (all)",
  "vocab.theme_token.evcc_floor_texture_map_rotate": "Map Texture Rotation (deg)",
  "vocab.theme_token.evcc_floor_tile_base": "Tile Base Color",
  "vocab.theme_token.evcc_floor_tile_grout": "Tile Grout Color",
  "vocab.theme_token.evcc_floor_tile_accent": "Tile Grout Line Color",
  "vocab.theme_token.evcc_floor_tile_opacity_card": "Tile Card Opacity",
  "vocab.theme_token.evcc_floor_tile_face_opacity": "Tile Base Layer Opacity",
  "vocab.theme_token.evcc_floor_tile_grout_opacity": "Tile Grout Layer Opacity",
  "vocab.theme_token.evcc_floor_tile_line_opacity": "Tile Grout Line Layer Opacity",
  "vocab.theme_token.evcc_floor_wood_base": "Wood Base Color",
  "vocab.theme_token.evcc_floor_wood_accent": "Wood Grain & Seam Color",
  "vocab.theme_token.evcc_floor_wood_opacity_card": "Wood Card Opacity",
  "vocab.theme_token.evcc_floor_wood_depth_opacity": "Wood Depth Layer Opacity",
  "vocab.theme_token.evcc_floor_wood_grain_opacity": "Wood Grain Layer Opacity",
  "vocab.theme_token.evcc_floor_wood_seam_opacity": "Wood Seam Layer Opacity",
  "vocab.theme_token.evcc_floor_marble_base": "Marble Base Color",
  "vocab.theme_token.evcc_floor_marble_micro": "Marble Micro Color",
  "vocab.theme_token.evcc_floor_marble_accent": "Marble Vein Color",
  "vocab.theme_token.evcc_floor_marble_opacity_card": "Marble Card Opacity",
  "vocab.theme_token.evcc_floor_marble_base_opacity": "Marble Base Layer Opacity",
  "vocab.theme_token.evcc_floor_marble_micro_opacity": "Marble Micro Layer Opacity",
  "vocab.theme_token.evcc_floor_marble_vein_opacity": "Marble Vein Opacity (master)",
  "vocab.theme_token.evcc_floor_marble_vein_blur": "Marble Vein Blur (master, px)",
  "vocab.theme_token.evcc_floor_marble_vein_major_opacity": "Marble Major Vein Opacity +/-",
  "vocab.theme_token.evcc_floor_marble_vein_minor_opacity": "Marble Minor Vein Opacity +/-",
  "vocab.theme_token.evcc_floor_marble_vein_major_blur": "Marble Major Vein Blur +/- (px)",
  "vocab.theme_token.evcc_floor_marble_vein_minor_blur": "Marble Minor Vein Blur +/- (px)",
  "vocab.theme_token.evcc_floor_marble_vein_minor_light": "Marble Minor Vein Lighten (L+)",
  "vocab.theme_token.evcc_floor_marble_vein_minor_chroma": "Marble Minor Vein Saturation (xC)",
  "vocab.theme_token.evcc_floor_marble_vein_minor_hue": "Marble Minor Vein Hue Shift (deg)",
  "vocab.theme_token.evcc_floor_concrete_base": "Concrete Base Color",
  "vocab.theme_token.evcc_floor_concrete_accent": "Concrete Micro Color",
  "vocab.theme_token.evcc_floor_concrete_opacity_card": "Concrete Card Opacity",
  "vocab.theme_token.evcc_floor_concrete_broad_opacity": "Concrete Base Layer Opacity",
  "vocab.theme_token.evcc_floor_concrete_micro_opacity": "Concrete Micro Layer Opacity",
  "vocab.theme_token.evcc_floor_carpet_low_base": "Carpet Low Base Color",
  "vocab.theme_token.evcc_floor_carpet_low_weave": "Carpet Low Weave Color",
  "vocab.theme_token.evcc_floor_carpet_low_opacity_card": "Carpet Low Card Opacity",
  "vocab.theme_token.evcc_floor_carpet_low_base_opacity": "Carpet Low Base Layer Opacity",
  "vocab.theme_token.evcc_floor_carpet_low_weave_opacity": "Carpet Low Weave Layer Opacity",
  "vocab.theme_token.evcc_floor_carpet_high_base": "Carpet High Base Color",
  "vocab.theme_token.evcc_floor_carpet_high_weave": "Carpet High Weave Color",
  "vocab.theme_token.evcc_floor_carpet_high_opacity_card": "Carpet High Card Opacity",
  "vocab.theme_token.evcc_floor_carpet_high_base_opacity": "Carpet High Base Layer Opacity",
  "vocab.theme_token.evcc_floor_carpet_high_weave_opacity": "Carpet High Weave Layer Opacity",
  "vocab.theme_token.evcc_floor_granite_light_base": "Granite Base Color",
  "vocab.theme_token.evcc_floor_granite_light_aggregate": "Granite Aggregate Color",
  "vocab.theme_token.evcc_floor_granite_light_opacity_card": "Granite Card Opacity",
  "vocab.theme_token.evcc_floor_granite_light_base_opacity": "Granite Base Layer Opacity",
  "vocab.theme_token.evcc_floor_granite_light_aggregate_opacity": "Granite Aggregate Layer Opacity",
  "vocab.theme_token.evcc_drag_opacity": "Drag Opacity",
  "vocab.theme_token.evcc_drag_scale": "Drag Scale",
  "vocab.theme_token.evcc_drag_shadow": "Drag Shadow",
  "vocab.theme_token.evcc_order_chip_bg": "Order Chip BG",
  "vocab.theme_token.evcc_order_chip_border": "Order Chip Border",
  "vocab.theme_token.evcc_order_chip_text": "Order Chip Text",
  "vocab.theme_token.evcc_order_feedback_border": "Order Feedback Border",
  "vocab.theme_token.evcc_order_target_outline": "Order Target Outline",
  "vocab.theme_token.evcc_progress_complete": "Progress Complete",
  "vocab.theme_token.evcc_progress_fill": "Progress Fill",
  "vocab.theme_token.evcc_queue_chip_bg": "Queue Chip BG",
  "vocab.theme_token.evcc_queue_chip_border": "Queue Chip Border",
  "vocab.theme_token.evcc_queue_chip_gap": "Queue Chip Gap",
  "vocab.theme_token.evcc_queue_chip_text": "Queue Chip Text",
  "vocab.theme_token.evcc_queue_completed_bg": "Queue Completed BG",
  "vocab.theme_token.evcc_queue_completed_border": "Queue Completed Border",
  "vocab.theme_token.evcc_queue_completed_opacity": "Queue Completed Opacity",
  "vocab.theme_token.evcc_queue_completed_text": "Queue Completed Text",
  "vocab.theme_token.evcc_queue_current_bg": "Queue Current BG",
  "vocab.theme_token.evcc_queue_current_border": "Queue Current Border",
  "vocab.theme_token.evcc_queue_current_glow": "Queue Current Glow",
  "vocab.theme_token.evcc_queue_current_text": "Queue Current Text",
  "vocab.theme_token.evcc_queue_hover_bg": "Queue Hover BG",
  "vocab.theme_token.evcc_queue_hover_border": "Queue Hover Border",
  "vocab.theme_token.evcc_queue_hover_text": "Queue Hover Text",
  "vocab.theme_token.evcc_queue_inferred_bg": "Queue Inferred BG",
  "vocab.theme_token.evcc_queue_inferred_border": "Queue Inferred Border",
  "vocab.theme_token.evcc_queue_inferred_glow": "Queue Inferred Glow",
  "vocab.theme_token.evcc_queue_inferred_text": "Queue Inferred Text",
  "vocab.theme_token.evcc_queue_order_bg": "Queue Order BG",
  "vocab.theme_token.evcc_queue_order_border": "Queue Order Border",
  "vocab.theme_token.evcc_queue_order_text": "Queue Order Text",
  "vocab.theme_token.evcc_queue_pending_bg": "Queue Pending BG",
  "vocab.theme_token.evcc_queue_pending_border": "Queue Pending Border",
  "vocab.theme_token.evcc_queue_pending_opacity": "Queue Pending Opacity",
  "vocab.theme_token.evcc_queue_pending_text": "Queue Pending Text",
  "vocab.theme_token.evcc_queue_skipped_bg": "Queue Skipped BG",
  "vocab.theme_token.evcc_queue_skipped_border": "Queue Skipped Border",
  "vocab.theme_token.evcc_queue_skipped_text": "Queue Skipped Text",
  "vocab.theme_token.evcc_reorder_feedback_duration": "Reorder Feedback Duration",
  "vocab.theme_token.evcc_reorder_flip_easing": "Reorder Flip Easing",
  "vocab.theme_token.evcc_color_cleaning": "Color Cleaning",
  "vocab.theme_token.evcc_color_docked": "Color Docked",
  "vocab.theme_token.evcc_color_error": "Color Error",
  "vocab.theme_token.evcc_color_idle": "Color Idle",
  "vocab.theme_token.evcc_confidence_high_bg": "Confidence High BG",
  "vocab.theme_token.evcc_confidence_high_border": "Confidence High Border",
  "vocab.theme_token.evcc_confidence_high_text": "Confidence High Text",
  "vocab.theme_token.evcc_confidence_low_bg": "Confidence Low BG",
  "vocab.theme_token.evcc_confidence_low_border": "Confidence Low Border",
  "vocab.theme_token.evcc_confidence_low_text": "Confidence Low Text",
  "vocab.theme_token.evcc_confidence_medium_bg": "Confidence Medium BG",
  "vocab.theme_token.evcc_confidence_medium_border": "Confidence Medium Border",
  "vocab.theme_token.evcc_confidence_medium_text": "Confidence Medium Text",
  "vocab.theme_token.evcc_sem_error": "Sem Error",
  "vocab.theme_token.evcc_sem_info": "Sem Info",
  "vocab.theme_token.evcc_sem_success": "Sem Success",
  "vocab.theme_token.evcc_sem_warning": "Sem Warning",
  "vocab.theme_token.evcc_status_cleaning_bg": "Status Cleaning BG",
  "vocab.theme_token.evcc_status_cleaning_border": "Status Cleaning Border",
  "vocab.theme_token.evcc_status_cleaning_text": "Status Cleaning Text",
  "vocab.theme_token.evcc_status_dot_charging": "Status Dot Charging",
  "vocab.theme_token.evcc_status_dot_cleaning": "Status Dot Cleaning",
  "vocab.theme_token.evcc_status_dot_docked": "Status Dot Docked",
  "vocab.theme_token.evcc_status_dot_error": "Status Dot Error",
  "vocab.theme_token.evcc_status_dot_idle": "Status Dot Idle",
  "vocab.theme_token.evcc_status_dot_offline": "Status Dot Offline",
  "vocab.theme_token.evcc_status_dot_paused": "Status Dot Paused",
  "vocab.theme_token.evcc_status_dot_returning": "Status Dot Returning",
  "vocab.theme_token.evcc_status_dot_shadow": "Status Dot Shadow",
  "vocab.theme_token.evcc_status_dot_unavailable": "Status Dot Unavailable",
  "vocab.theme_token.evcc_status_pulse_duration": "Status Pulse Duration",
  "vocab.theme_token.evcc_estimate_default_bg": "Estimate Default BG",
  "vocab.theme_token.evcc_estimate_default_border": "Estimate Default Border",
  "vocab.theme_token.evcc_estimate_default_text": "Estimate Default Text",
  "vocab.theme_token.evcc_estimate_learned_bg": "Estimate Learned BG",
  "vocab.theme_token.evcc_estimate_learned_border": "Estimate Learned Border",
  "vocab.theme_token.evcc_estimate_learned_text": "Estimate Learned Text",
  "vocab.theme_token.evcc_learning_anim_duration_fast": "Learning Anim Duration Fast",
  "vocab.theme_token.evcc_learning_anim_duration_normal": "Learning Anim Duration Normal",
  "vocab.theme_token.evcc_learning_anim_duration_slow": "Learning Anim Duration Slow",
  "vocab.theme_token.evcc_learning_anim_ease": "Learning Anim Ease",
  "vocab.theme_token.evcc_learning_chip_font_size": "Learning Chip Font Size",
  "vocab.theme_token.evcc_learning_chip_font_weight": "Learning Chip Font Weight",
  "vocab.theme_token.evcc_learning_chip_radius": "Learning Chip Radius",
  "vocab.theme_token.evcc_learning_confidence_high_bg": "Learning Confidence High BG",
  "vocab.theme_token.evcc_learning_confidence_high_border": "Learning Confidence High Border",
  "vocab.theme_token.evcc_learning_confidence_high_gradient": "Learning Confidence High Gradient",
  "vocab.theme_token.evcc_learning_confidence_high_text": "Learning Confidence High Text",
  "vocab.theme_token.evcc_learning_confidence_low_border": "Learning Confidence Low Border",
  "vocab.theme_token.evcc_learning_confidence_low_gradient": "Learning Confidence Low Gradient",
  "vocab.theme_token.evcc_learning_confidence_low_text": "Learning Confidence Low Text",
  "vocab.theme_token.evcc_learning_confidence_medium_bg": "Learning Confidence Medium BG",
  "vocab.theme_token.evcc_learning_confidence_medium_border": "Learning Confidence Medium Border",
  "vocab.theme_token.evcc_learning_confidence_medium_gradient": "Learning Confidence Medium Gradient",
  "vocab.theme_token.evcc_learning_confidence_medium_text": "Learning Confidence Medium Text",
  "vocab.theme_token.evcc_learning_confidence_neutral_border": "Learning Confidence Neutral Border",
  "vocab.theme_token.evcc_learning_confidence_neutral_gradient": "Learning Confidence Neutral Gradient",
  "vocab.theme_token.evcc_learning_confidence_neutral_text": "Learning Confidence Neutral Text",
  "vocab.theme_token.evcc_learning_note_text": "Learning Note Text",
  "vocab.theme_token.evcc_learning_panel_bg": "Learning Panel BG",
  "vocab.theme_token.evcc_learning_panel_border": "Learning Panel Border",
  "vocab.theme_token.evcc_learning_panel_shadow": "Learning Panel Shadow",
  "vocab.theme_token.evcc_learning_reanchor_border": "Learning Reanchor Border",
  "vocab.theme_token.evcc_learning_reanchor_highlight": "Learning Reanchor Highlight",
  "vocab.theme_token.evcc_learning_text_muted": "Learning Text Muted",
  "vocab.theme_token.evcc_learning_text_primary": "Learning Text Primary",
  "vocab.theme_token.evcc_learning_text_secondary": "Learning Text Secondary",
  "vocab.theme_token.evcc_learning_warning_text": "Learning Warning Text",
  "vocab.theme_token.evcc_modal_accent": "Modal Accent",
  "vocab.theme_token.evcc_modal_accent_bg": "Modal Accent BG",
  "vocab.theme_token.evcc_modal_accent_border": "Modal Accent Border",
  "vocab.theme_token.evcc_modal_accent_text": "Modal Accent Text",
  "vocab.theme_token.evcc_modal_backdrop_bg": "Modal Backdrop BG",
  "vocab.theme_token.evcc_modal_backdrop_blur": "Modal Backdrop Blur",
  "vocab.theme_token.evcc_modal_bg": "Modal BG",
  "vocab.theme_token.evcc_modal_border": "Modal Border",
  "vocab.theme_token.evcc_modal_border_default": "Modal Border Default",
  "vocab.theme_token.evcc_modal_border_strong": "Modal Border Strong",
  "vocab.theme_token.evcc_modal_border_subtle": "Modal Border Subtle",
  "vocab.theme_token.evcc_modal_chip_active_bg": "Modal Chip Active BG",
  "vocab.theme_token.evcc_modal_chip_active_border": "Modal Chip Active Border",
  "vocab.theme_token.evcc_modal_chip_active_text": "Modal Chip Active Text",
  "vocab.theme_token.evcc_modal_chip_bg": "Modal Chip BG",
  "vocab.theme_token.evcc_modal_chip_border": "Modal Chip Border",
  "vocab.theme_token.evcc_modal_chip_hover_bg": "Modal Chip Hover BG",
  "vocab.theme_token.evcc_modal_chip_hover_border": "Modal Chip Hover Border",
  "vocab.theme_token.evcc_modal_chip_hover_text": "Modal Chip Hover Text",
  "vocab.theme_token.evcc_modal_chip_text": "Modal Chip Text",
  "vocab.theme_token.evcc_modal_footer_bg": "Modal Footer BG",
  "vocab.theme_token.evcc_modal_header_bg": "Modal Header BG",
  "vocab.theme_token.evcc_modal_input_bg": "Modal Input BG",
  "vocab.theme_token.evcc_modal_padding": "Modal Padding",
  "vocab.theme_token.evcc_modal_radius": "Modal Radius",
  "vocab.theme_token.evcc_modal_section_gap": "Modal Section Gap",
  "vocab.theme_token.evcc_modal_shadow": "Modal Shadow",
  "vocab.theme_token.evcc_modal_surface_input": "Modal Surface Input",
  "vocab.theme_token.evcc_modal_surface_panel": "Modal Surface Panel",
  "vocab.theme_token.evcc_modal_surface_section": "Modal Surface Section",
  "vocab.theme_token.evcc_modal_text_muted": "Modal Text Muted",
  "vocab.theme_token.evcc_modal_text_primary": "Modal Text Primary",
  "vocab.theme_token.evcc_modal_text_secondary": "Modal Text Secondary",
  "vocab.theme_token.evcc_modal_warning_bg": "Modal Warning BG",
  "vocab.theme_token.evcc_modal_warning_border": "Modal Warning Border",
  "vocab.theme_token.evcc_modal_warning_text": "Modal Warning Text",
  "vocab.theme_token.evcc_animal_eye_good": "Eye — Good (>50% battery)",
  "vocab.theme_token.evcc_animal_eye_mid": "Eye — Mid (25–50%)",
  "vocab.theme_token.evcc_animal_eye_warn": "Eye — Warn (15–25%)",
  "vocab.theme_token.evcc_animal_eye_low": "Eye — Low (≤15%)",
  "vocab.theme_token.evcc_animal_eye_charging": "Eye — Charging (pulses)",
  "vocab.theme_token.evcc_animal_fur": "Fur (all animals)",
  "vocab.theme_token.evcc_animal_fur_shadow": "Fur Shadow (all)",
  "vocab.theme_token.evcc_animal_fur_highlight": "Fur Highlight (all)",
  "vocab.theme_token.evcc_animal_eye": "Eye Base (all)",
  "vocab.theme_token.evcc_animal_pupil": "Pupil (all)",
  "vocab.theme_token.evcc_animal_nose": "Nose (all)",
  "vocab.theme_token.evcc_animal_whisker": "Whisker (all)",
  "vocab.theme_token.evcc_animal_ear_inner": "Ear Inner (all)",
  "vocab.theme_token.evcc_animal_white_tip": "White Tip / Accent (all)",
  "vocab.theme_token.evcc_animal_cat_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_cat_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_cat_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_cat_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_cat_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_cat_fur": "Fur",
  "vocab.theme_token.evcc_animal_cat_fur_shadow": "Fur Shadow",
  "vocab.theme_token.evcc_animal_cat_fur_highlight": "Fur Highlight",
  "vocab.theme_token.evcc_animal_cat_eye": "Eye Base",
  "vocab.theme_token.evcc_animal_cat_pupil": "Pupil",
  "vocab.theme_token.evcc_animal_cat_nose": "Nose",
  "vocab.theme_token.evcc_animal_cat_whisker": "Whisker",
  "vocab.theme_token.evcc_animal_cat_ear_inner": "Ear Inner",
  "vocab.theme_token.evcc_animal_cat_white_tip": "White Tip / Accent",
  "vocab.theme_token.evcc_animal_dog_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_dog_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_dog_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_dog_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_dog_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_dog_fur": "Fur",
  "vocab.theme_token.evcc_animal_dog_fur_shadow": "Fur Shadow",
  "vocab.theme_token.evcc_animal_dog_fur_highlight": "Fur Highlight",
  "vocab.theme_token.evcc_animal_dog_eye": "Eye Base",
  "vocab.theme_token.evcc_animal_dog_pupil": "Pupil",
  "vocab.theme_token.evcc_animal_dog_nose": "Nose",
  "vocab.theme_token.evcc_animal_dog_whisker": "Whisker",
  "vocab.theme_token.evcc_animal_dog_ear_inner": "Ear Inner",
  "vocab.theme_token.evcc_animal_dog_white_tip": "White Tip / Accent",
  "vocab.theme_token.evcc_animal_raccoon_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_raccoon_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_raccoon_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_raccoon_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_raccoon_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_raccoon_fur": "Fur",
  "vocab.theme_token.evcc_animal_raccoon_fur_shadow": "Fur Shadow",
  "vocab.theme_token.evcc_animal_raccoon_fur_highlight": "Fur Highlight",
  "vocab.theme_token.evcc_animal_raccoon_eye": "Eye Base",
  "vocab.theme_token.evcc_animal_raccoon_pupil": "Pupil",
  "vocab.theme_token.evcc_animal_raccoon_nose": "Nose",
  "vocab.theme_token.evcc_animal_raccoon_whisker": "Whisker",
  "vocab.theme_token.evcc_animal_raccoon_ear_inner": "Ear Inner",
  "vocab.theme_token.evcc_animal_raccoon_white_tip": "White Tip / Accent",
  "vocab.theme_token.evcc_animal_parrot_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_parrot_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_parrot_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_parrot_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_parrot_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_parrot_fur": "Fur",
  "vocab.theme_token.evcc_animal_parrot_fur_shadow": "Fur Shadow",
  "vocab.theme_token.evcc_animal_parrot_fur_highlight": "Fur Highlight",
  "vocab.theme_token.evcc_animal_parrot_eye": "Eye Base",
  "vocab.theme_token.evcc_animal_parrot_pupil": "Pupil",
  "vocab.theme_token.evcc_animal_parrot_nose": "Nose",
  "vocab.theme_token.evcc_animal_parrot_whisker": "Whisker",
  "vocab.theme_token.evcc_animal_parrot_ear_inner": "Ear Inner",
  "vocab.theme_token.evcc_animal_parrot_white_tip": "White Tip / Accent",
  "vocab.theme_token.evcc_animal_snake_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_snake_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_snake_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_snake_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_snake_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_snake_fur": "Fur",
  "vocab.theme_token.evcc_animal_snake_fur_shadow": "Fur Shadow",
  "vocab.theme_token.evcc_animal_snake_fur_highlight": "Fur Highlight",
  "vocab.theme_token.evcc_animal_snake_eye": "Eye Base",
  "vocab.theme_token.evcc_animal_snake_pupil": "Pupil",
  "vocab.theme_token.evcc_animal_snake_nose": "Nose",
  "vocab.theme_token.evcc_animal_snake_whisker": "Whisker",
  "vocab.theme_token.evcc_animal_snake_ear_inner": "Ear Inner",
  "vocab.theme_token.evcc_animal_snake_white_tip": "White Tip / Accent",
  "vocab.theme_token.evcc_font_family": "Font Family",
  "vocab.theme_token.evcc_gap": "Gap",
  "vocab.theme_token.evcc_grid_gap": "Grid Gap",
  "vocab.theme_token.evcc_hover_lift": "Hover Lift",
  "vocab.theme_token.evcc_pad": "Pad",
  "vocab.theme_token.evcc_press_scale": "Press Scale",
  "vocab.theme_token.evcc_radius_card": "Radius Card",
  "vocab.theme_token.evcc_radius_chip": "Radius Chip",
  "vocab.theme_token.evcc_radius_inner": "Radius Inner",
  "vocab.theme_token.evcc_radius_panel": "Radius Panel",
  "vocab.theme_token.evcc_section_gap": "Section Gap",
  "vocab.theme_token.evcc_space_lg": "Space Lg",
  "vocab.theme_token.evcc_space_md": "Space Md",
  "vocab.theme_token.evcc_space_sm": "Space Sm",
  "vocab.theme_token.evcc_transition_normal": "Transition Normal",
  "vocab.theme_group.app_shell_typography": "App Shell & Typography",
  "vocab.theme_group.cards_surfaces": "Cards & Surfaces",
  "vocab.theme_group.borders_shadows": "Borders & Shadows",
  "vocab.theme_group.chips": "Chips",
  "vocab.theme_group.room_cards": "Room Cards",
  "vocab.theme_group.map": "Map",
  "vocab.theme_group.floor_textures": "Floor Textures",
  "vocab.theme_group.floor_textures_tile": "Tile",
  "vocab.theme_group.floor_textures_wood": "Wood",
  "vocab.theme_group.floor_textures_marble": "Marble",
  "vocab.theme_group.floor_textures_concrete": "Concrete",
  "vocab.theme_group.floor_textures_carpet_low": "Carpet Low",
  "vocab.theme_group.floor_textures_carpet_high": "Carpet High",
  "vocab.theme_group.floor_textures_granite": "Granite",
  "vocab.theme_group.queue_ordering": "Queue & Ordering",
  "vocab.theme_group.status_confidence_alerts": "Status, Confidence & Alerts",
  "vocab.theme_group.learning_metrics": "Learning & Metrics",
  "vocab.theme_group.modals_overlays": "Modals & Overlays",
  "vocab.theme_group.animal_companion": "Animal Companion",
  "vocab.theme_group.shared_foundations": "Shared Foundations",
  "vocab.theme_facet.mode": "Mode",
  "vocab.theme_facet.accent": "Accent",
  "vocab.theme_facet.temperature": "Temp",
  "vocab.theme_facet.surface": "Surface",
  "vocab.theme_facet.contrast": "Contrast",
  "vocab.theme_facet.a11y": "Access",
  "vocab.theme_facet.cvd": "Best for",
  "vocab.theme_facet.source": "Source",
  "vocab.theme_tag.dark": "dark",
  "vocab.theme_tag.light": "light",
  "vocab.theme_tag.red": "red",
  "vocab.theme_tag.orange": "orange",
  "vocab.theme_tag.gold": "gold",
  "vocab.theme_tag.green": "green",
  "vocab.theme_tag.teal": "teal",
  "vocab.theme_tag.cyan": "cyan",
  "vocab.theme_tag.blue": "blue",
  "vocab.theme_tag.purple": "purple",
  "vocab.theme_tag.pink": "pink",
  "vocab.theme_tag.mono": "mono",
  "vocab.theme_tag.warm": "warm",
  "vocab.theme_tag.cool": "cool",
  "vocab.theme_tag.neutral": "neutral",
  "vocab.theme_tag.deep": "deep",
  "vocab.theme_tag.vivid": "vivid",
  "vocab.theme_tag.muted": "muted",
  "vocab.theme_tag.soft": "soft",
  "vocab.theme_tag.high_contrast": "high-contrast",
  "vocab.theme_tag.colorblind_safe": "colorblind-safe",
  "vocab.theme_tag.red_green": "red-green",
  "vocab.theme_tag.blue_yellow": "blue-yellow",
  "vocab.theme_tag.core": "core",
  "vocab.theme_tag.community": "community",
  "vocab.theme_tag.generated": "generated",
  "vocab.theme_tag.manual": "manual",

  // --- Wave-3 animals: fox+mittens tokens, generic names + Rainbow Bridge (memorial names stay protected) ---
  "vocab.theme_token.evcc_animal_fox_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_fox_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_fox_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_fox_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_fox_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_fox_fur": "Fur",
  "vocab.theme_token.evcc_animal_fox_fur_shadow": "Fur Shadow",
  "vocab.theme_token.evcc_animal_fox_fur_highlight": "Fur Highlight",
  "vocab.theme_token.evcc_animal_fox_eye": "Eye Base",
  "vocab.theme_token.evcc_animal_fox_pupil": "Pupil",
  "vocab.theme_token.evcc_animal_fox_nose": "Nose",
  "vocab.theme_token.evcc_animal_fox_whisker": "Whisker",
  "vocab.theme_token.evcc_animal_fox_ear_inner": "Ear Inner",
  "vocab.theme_token.evcc_animal_fox_white_tip": "White Tip / Accent",
  "vocab.theme_token.evcc_animal_mittens_eye_good": "Eye — Good",
  "vocab.theme_token.evcc_animal_mittens_eye_mid": "Eye — Mid",
  "vocab.theme_token.evcc_animal_mittens_eye_warn": "Eye — Warn",
  "vocab.theme_token.evcc_animal_mittens_eye_low": "Eye — Low",
  "vocab.theme_token.evcc_animal_mittens_eye_charging": "Eye — Charging",
  "vocab.theme_token.evcc_animal_mittens_eye": "Eye Base",
  "vocab.theme_group.animal_companion_cat": "Cat",
  "vocab.theme_group.animal_companion_dog": "Dog",
  "vocab.theme_group.animal_companion_fox": "Fox",
  "vocab.theme_group.animal_companion_parrot": "Parrot",
  "vocab.theme_group.animal_companion_raccoon": "Raccoon",
  "vocab.theme_group.animal_companion_snake": "Snake",
  "vocab.theme_group.rainbow_bridge": "Rainbow Bridge",

  // === JOB SUMMARY MODAL =================================================
  // Opened from a Learning Review job card (row body OR its error badge — both
  // lead here, so there is one surface rather than a separate error dialog).
  // Most of what this modal shows reuses existing keys; only the labels that had
  // no equivalent are minted here.
  // REUSED rather than minted, after checking the catalog for equivalents:
  //   review.detail_area_m2   "{value} m²"   — the card's area value everywhere
  //   review.passes           plural, already { one, other }
  //   learning.stat_rooms     "Rooms"        — literally 'count of rooms this run'
  //   room_editor.edge_mopping, review.kv_rooms, review.unknown, common.close
  //
  // The two FORMATTER strings this modal needed had no equivalent, so they live in
  // common.* rather than here — they are units, not modal vocabulary, and the next
  // surface that needs a bare percent or a sub-minute duration should inherit them.
  "job_summary.title": "Run summary",  // Modal title. 'Run' not 'Job': the user thinks of it as one cleaning run
  "job_summary.open_aria": "Open run summary",  // Accessible name for the clickable job card. Deliberately does NOT interpolate the run id — a screen reader would read out 'job underscore 2026 dash 08...', which is unique but useless; the card's own text already identifies which run it is
  "job_summary.started": "Started",  // KV label: when the run began
  "job_summary.elapsed": "Elapsed",  // KV label: wall-clock start to finish, INCLUDING docking/washing overhead
  "job_summary.cleaning_time": "Cleaning time",  // KV label: time actually spent cleaning — deliberately distinct from Elapsed
  "job_summary.area": "Area cleaned",  // KV label: total floor area for the run
  "job_summary.battery": "Battery used",  // KV label: job-level battery consumption
  "job_summary.recharged": {
    one: "Recharged once mid-run",
    other: "Recharged {count}× mid-run",
  },  // plural; shown when the robot recharged but the charge duration is unknown. Without this line the battery figure silently understates what the run actually drew (start-minus-end cannot see the pack going back up)
  "job_summary.recharged_for": {
    one: "Recharged once mid-run · {duration}",
    other: "Recharged {count}× mid-run · {duration}",
  },  // plural; same as recharged, with total time spent charging
  "job_summary.room_cleaning": "Cleaning {duration}",  // Per-room result: time spent cleaning that room
  "job_summary.room_elapsed": "Elapsed {duration}",  // Per-room result: wall-clock in that room; shown only when it differs from cleaning time
  "job_summary.room_no_result": "Not reached",  // A room that was queued but the run never got to — normal, not an error
  "job_summary.errors_count": {
    one: "Errors — 1",
    other: "Errors — {count}",
  },  // plural; Errors section heading with the fault count
  "job_summary.source_dock": "Dock",  // Which hardware raised a fault. NOT map.dock (a map marker) or vacuum_card.dock (a button) — this is an attribution, and the distinction survives translation
  "job_summary.source_robot": "Robot",  // Which hardware raised a fault
  "job_summary.source_unknown": "Source unknown",  // Deliberately explicit: blaming the robot for an unclassified fault would send the user to hardware that is fine
  "job_summary.recovered": "Recovered",  // The fault cleared during the run
  "job_summary.not_recovered": "Not recovered",  // The fault was still latched when the run ended — NOT a claim that it ended the run, which the record cannot establish
  "job_summary.captured_from_app": "Captured from the app — some details are unavailable for runs this card did not start.",  // Explains why an app-started run's summary is thinner, so it reads as expected rather than broken

  // === EUFY FAULT LABELS (CARD-3 / RF-DOCK) ==============================
  // Plain-language labels for robovac_mqtt's 199 fault codes. The ADAPTER maps
  // code -> key (adapters/eufy/vocabulary.py EUFY_ERROR_LABEL_KEYS); core never
  // learns a brand's codes. Resolved at render time by faultLabel() in
  // src/i18n/faults.js, which is why these are reachable via template rather than
  // a literal t("…") call. CARD-3 shows the raw code alongside, so the vendor term
  // stays available. English signed off 2026-08-02; the 17-locale pass IS DONE —
  // verified 2026-08-05, all 189 keys translated in all 17 packs, 0 English
  // placeholders (the note here claimed it was still pending long after it landed).
  "fault.eufy.base_station_clean_water_pump_electrical_fault": "Base station clean-water pump electrical fault",  // Eufy code 6013
  "fault.eufy.base_station_clean_water_pump_not_responding": "Base station clean-water pump not responding",  // Eufy code 6012
  "fault.eufy.base_station_clean_water_tank_not_connected": "Base station clean water tank not connected",  // Eufy code 6010
  "fault.eufy.base_station_cleaning_tray_not_installed": "Base station cleaning tray not installed",  // Eufy code 6030
  "fault.eufy.base_station_dirty_tank_full": "Base station dirty tank full",  // Eufy code 6021
  "fault.eufy.base_station_dirty_tank_leak": "Base station dirty tank leak",  // Eufy code 6024
  "fault.eufy.base_station_dirty_tank_missing": "Base station dirty tank missing",  // Eufy code 6020
  "fault.eufy.base_station_dirty_water_pump_electrical_fault": "Base station dirty-water pump electrical fault",  // Eufy code 6023
  "fault.eufy.base_station_dirty_water_pump_not_responding": "Base station dirty-water pump not responding",  // Eufy code 6022
  "fault.eufy.base_station_dust_duct_blocked": "Base station dust duct blocked — clear it",  // Eufy code 6112
  "fault.eufy.base_station_dust_leak": "Base station dust leak",  // Eufy code 6111
  "fault.eufy.base_station_exploration_failed": "Base station exploration failed",  // Eufy code 7033
  "fault.eufy.base_station_fan_overheat": "Base station fan overheat",  // Eufy code 6114
  "fault.eufy.base_station_full_dirty_water_or_dirty_water_tank": "Base station full dirty water or dirty water tank not connected",  // Eufy code 6025
  "fault.eufy.base_station_heater_not_responding": "Base station heater not responding",  // Eufy code 6042
  "fault.eufy.base_station_low_clean_water": "Base station low clean water",  // Eufy code 6011
  "fault.eufy.base_station_mop_dryer_electrical_fault": "Base station mop dryer electrical fault",  // Eufy code 6041
  "fault.eufy.base_station_mop_dryer_heater_fault": "Base station mop dryer heater fault",  // Eufy code 41
  "fault.eufy.base_station_mop_dryer_not_responding": "Base station mop dryer not responding",  // Eufy code 6040
  "fault.eufy.base_station_no_dust_bag_installed": "Base station no dust bag installed",  // Eufy code 6113
  "fault.eufy.base_station_not_found": "Base station not found",  // Eufy code 7055
  "fault.eufy.base_station_power_fault": "Base station power fault",  // Eufy code 6110
  "fault.eufy.base_station_power_off": "Base station power off",  // Eufy code 5014
  "fault.eufy.base_station_pressure_sensor_fault": "Base station pressure sensor fault",  // Eufy code 6115
  "fault.eufy.base_station_temperature_sensor_not_responding": "Base station temperature sensor not responding",  // Eufy code 6043
  "fault.eufy.base_station_tray_full": "Base station tray full",  // Eufy code 6031
  "fault.eufy.base_station_tray_missing_or_full": "Base station tray missing or full",  // Eufy code 6032
  "fault.eufy.base_station_water_valve_electrical_fault": "Base station water valve electrical fault",  // Eufy code 6014
  "fault.eufy.battery_electrical_fault": "Battery electrical fault",  // Eufy code 5011
  "fault.eufy.battery_fault": "Battery fault",  // Eufy code 101
  "fault.eufy.battery_not_responding": "Battery not responding",  // Eufy code 5010
  "fault.eufy.battery_temperature_out_of_range": "Battery temperature out of range",  // Eufy code 5018
  "fault.eufy.bluetooth_error": "Bluetooth error",  // Eufy code 5111
  "fault.eufy.both_wheel_motors_electrical_fault": "Both wheel motors electrical fault",  // Eufy code 1031
  "fault.eufy.both_wheel_motors_not_responding": "Both wheel motors not responding",  // Eufy code 1030
  "fault.eufy.both_wheels_fault": "Both wheels fault",  // Eufy code 1032
  "fault.eufy.both_wheels_jammed_check_for_tangled_hair_or_debris": "Both wheels jammed — check for tangled hair or debris",  // Eufy code 1033
  "fault.eufy.bumper_stuck": "Bumper stuck",  // Eufy code 1
  "fault.eufy.camera_blocked": "Camera blocked",  // Eufy codes 51, 4041
  "fault.eufy.camera_fault": "Camera fault",  // Eufy code 76
  "fault.eufy.camera_sensor_error": "Camera sensor error",  // Eufy code 4040
  "fault.eufy.cannot_find_start_point": "Cannot find start point",  // Eufy code 7034
  "fault.eufy.charge_temp_high": "Charge temp high",  // Eufy code 5023
  "fault.eufy.charge_temp_low": "Charge temp low",  // Eufy code 5024
  "fault.eufy.charging_current_too_high": "Charging current too high",  // Eufy code 5016
  "fault.eufy.charging_current_too_low": "Charging current too low",  // Eufy code 5012
  "fault.eufy.charging_voltage_fault": "Charging voltage fault",  // Eufy code 5017
  "fault.eufy.clean_dust_collector": "Clean dust collector",  // Eufy code 70
  "fault.eufy.clean_tray_needs": "Clean tray needs clean",  // Eufy code 82
  "fault.eufy.clean_tray_not_installed": "Clean tray not installed",  // Eufy code 79
  "fault.eufy.clean_water_low": "Clean water low",  // Eufy code 74
  "fault.eufy.could_not_dock_something_reflective_is_confusing": "Could not dock — something reflective is confusing the dock sensor",  // Eufy code 7037
  "fault.eufy.could_not_find_the_base_station": "Could not find the base station",  // Eufy code 55
  "fault.eufy.could_not_leave_the_base_station": "Could not leave the base station",  // Eufy code 52
  "fault.eufy.could_not_return_to_the_base_station_clear_the_area": "Could not return to the base station — clear the area",  // Eufy code 7031
  "fault.eufy.depth_sensor_blocked": "Depth sensor blocked — wipe it clean",  // Eufy code 4031
  "fault.eufy.depth_sensor_fault": "Depth sensor fault",  // Eufy codes 77, 4030
  "fault.eufy.dirty_tank_full": "Dirty tank full",  // Eufy code 73
  "fault.eufy.discharge_current_too_high": "Discharge current too high",  // Eufy code 5013
  "fault.eufy.discharge_temp_high": "Discharge temp high",  // Eufy code 5021
  "fault.eufy.discharge_temp_low": "Discharge temp low",  // Eufy code 5022
  "fault.eufy.dock_failed": "Dock failed",  // Eufy code 21
  "fault.eufy.docking_failed_no_power": "Docking failed (no power)",  // Eufy code 7035
  "fault.eufy.docking_failed_wheel_stuck": "Docking failed (wheel stuck)",  // Eufy code 7036
  "fault.eufy.drop_sensor_triggered": "Drop sensor triggered",  // Eufy code 7003
  "fault.eufy.dust_bin_missing": "Dust bin missing",  // Eufy code 14
  "fault.eufy.dustbin_full_10h_reminder": "Dustbin full (10h reminder)",  // Eufy code 2311
  "fault.eufy.dustbin_or_filter_missing": "Dustbin or filter missing",  // Eufy code 2310
  "fault.eufy.entered_carpet": "Entered carpet",  // Eufy code 7011
  "fault.eufy.entered_no_go_zone": "Entered no-go zone",  // Eufy code 7010
  "fault.eufy.forbidden_area_detected": "Forbidden area detected",  // Eufy code 17
  "fault.eufy.front_roller_brush_jammed_check_for_tangled_hair": "Front roller brush jammed — check for tangled hair",  // Eufy code 2122
  "fault.eufy.front_roller_brush_motor_electrical_fault": "Front roller brush motor electrical fault",  // Eufy code 2121
  "fault.eufy.front_roller_brush_motor_not_responding": "Front roller brush motor not responding",  // Eufy code 2120
  "fault.eufy.global_positioning_failed": "Global positioning failed",  // Eufy code 7020
  "fault.eufy.gyroscope_fault": "Gyroscope fault",  // Eufy code 4020
  "fault.eufy.hair_cutting_in_progress": "Hair cutting in progress",  // Eufy code 6300
  "fault.eufy.hair_cutting_module_stuck": "Hair cutting module stuck",  // Eufy code 6311
  "fault.eufy.infrared_link_to_the_base_station_failed": "Infrared link to the base station failed",  // Eufy code 5112
  "fault.eufy.laser_blocked": "Laser blocked",  // Eufy code 20
  "fault.eufy.laser_cover_stuck": "Laser cover stuck",  // Eufy code 18
  "fault.eufy.laser_distance_sensor_fault": "Laser distance sensor fault",  // Eufy code 107
  "fault.eufy.laser_sensor_stuck": "Laser sensor stuck",  // Eufy code 19
  "fault.eufy.left_bumper_stuck": "Left bumper stuck",  // Eufy code 4111
  "fault.eufy.left_mop_missing": "Left mop missing",  // Eufy code 3110
  "fault.eufy.left_side_brush_fault": "Left side brush fault",  // Eufy code 2222
  "fault.eufy.left_side_brush_jammed_check_for_tangled_hair": "Left side brush jammed — check for tangled hair",  // Eufy code 2223
  "fault.eufy.left_side_brush_motor_electrical_fault": "Left side brush motor electrical fault",  // Eufy code 2221
  "fault.eufy.left_side_brush_motor_not_responding": "Left side brush motor not responding",  // Eufy code 2220
  "fault.eufy.left_suction_fan_electrical_fault": "Left suction fan electrical fault",  // Eufy code 2021
  "fault.eufy.left_suction_fan_fault": "Left suction fan fault",  // Eufy code 2022
  "fault.eufy.left_suction_fan_not_responding": "Left suction fan not responding",  // Eufy code 2020
  "fault.eufy.left_suction_fan_not_spinning_correctly": "Left suction fan not spinning correctly — check for a blockage",  // Eufy code 2023
  "fault.eufy.left_wheel_fault": "Left wheel fault",  // Eufy code 1012
  "fault.eufy.left_wheel_jammed_check_for_tangled_hair_or_debris": "Left wheel jammed — check for tangled hair or debris",  // Eufy code 1013
  "fault.eufy.left_wheel_motor_electrical_fault": "Left wheel motor electrical fault",  // Eufy code 1011
  "fault.eufy.left_wheel_motor_not_responding": "Left wheel motor not responding",  // Eufy code 1010
  "fault.eufy.lidar_cover_stuck": "Lidar cover stuck",  // Eufy code 4130
  "fault.eufy.lidar_not_spinning_correctly_check_for_a_blockage": "Lidar not spinning correctly — check for a blockage",  // Eufy code 4012
  "fault.eufy.lift_motor_stuck": "Lift motor stuck",  // Eufy code 3133
  "fault.eufy.lost_connection_to_the_robot": "Lost connection to the robot",  // Eufy code 80
  "fault.eufy.lost_position_cleaning_ended_early": "Lost position — cleaning ended early",  // Eufy code 39
  "fault.eufy.lost_the_target_it_was_following": "Lost the target it was following",  // Eufy code 7054
  "fault.eufy.low_battery_no_auto_empty": "Low battery (no auto empty)",  // Eufy code 6117
  "fault.eufy.low_battery_no_hair_cutting": "Low battery (no hair cutting)",  // Eufy code 6301
  "fault.eufy.low_battery_no_scheduled": "Low battery (no scheduled clean)",  // Eufy code 5015
  "fault.eufy.low_battery_no_self": "Low battery (no self clean)",  // Eufy code 6118
  "fault.eufy.mop_cloth_dislodged": "Mop cloth dislodged",  // Eufy code 40
  "fault.eufy.mop_lift_motor_electrical_fault": "Mop lift motor electrical fault",  // Eufy code 3131
  "fault.eufy.mop_lift_motor_fault": "Mop lift motor fault",  // Eufy codes 112, 3132
  "fault.eufy.mop_lift_motor_not_responding": "Mop lift motor not responding",  // Eufy code 3130
  "fault.eufy.mop_rotation_motor_electrical_fault": "Mop rotation motor electrical fault",  // Eufy code 3121
  "fault.eufy.mop_rotation_motor_fault": "Mop rotation motor fault",  // Eufy codes 111, 3122
  "fault.eufy.mop_rotation_motor_not_responding": "Mop rotation motor not responding",  // Eufy code 3120
  "fault.eufy.mop_water_spray_fault": "Mop water spray fault",  // Eufy code 113
  "fault.eufy.path_planning_failed": "Path planning failed",  // Eufy code 7052
  "fault.eufy.poor_charging_contact": "Poor charging contact",  // Eufy code 83
  "fault.eufy.positioning_failed": "Positioning failed",  // Eufy code 7021
  "fault.eufy.power_failure": "Power failure",  // Eufy code 6310
  "fault.eufy.power_low_shutdown": "Power low shutdown",  // Eufy code 8
  "fault.eufy.radar_blocked": "Radar blocked",  // Eufy code 4011
  "fault.eufy.radar_communication_error": "Radar communication error",  // Eufy code 4010
  "fault.eufy.rear_roller_brush_jammed_check_for_tangled_hair": "Rear roller brush jammed — check for tangled hair",  // Eufy code 2125
  "fault.eufy.rear_roller_brush_motor_electrical_fault": "Rear roller brush motor electrical fault",  // Eufy code 2124
  "fault.eufy.rear_roller_brush_motor_not_responding": "Rear roller brush motor not responding",  // Eufy code 2123
  "fault.eufy.right_bumper_stuck": "Right bumper stuck",  // Eufy code 4112
  "fault.eufy.right_mop_missing": "Right mop missing",  // Eufy code 3111
  "fault.eufy.right_side_brush_fault": "Right side brush fault",  // Eufy code 2226
  "fault.eufy.right_side_brush_jammed_check_for_tangled_hair": "Right side brush jammed — check for tangled hair",  // Eufy code 2227
  "fault.eufy.right_side_brush_motor_electrical_fault": "Right side brush motor electrical fault",  // Eufy code 2225
  "fault.eufy.right_side_brush_motor_not_responding": "Right side brush motor not responding",  // Eufy code 2224
  "fault.eufy.right_suction_fan_electrical_fault": "Right suction fan electrical fault",  // Eufy code 2025
  "fault.eufy.right_suction_fan_fault": "Right suction fan fault",  // Eufy code 2026
  "fault.eufy.right_suction_fan_not_responding": "Right suction fan not responding",  // Eufy code 2024
  "fault.eufy.right_suction_fan_not_spinning_correctly": "Right suction fan not spinning correctly — check for a blockage",  // Eufy code 2027
  "fault.eufy.right_wheel_fault": "Right wheel fault",  // Eufy code 1022
  "fault.eufy.right_wheel_jammed_check_for_tangled_hair_or_debris": "Right wheel jammed — check for tangled hair or debris",  // Eufy code 1023
  "fault.eufy.right_wheel_motor_electrical_fault": "Right wheel motor electrical fault",  // Eufy code 1021
  "fault.eufy.right_wheel_motor_not_responding": "Right wheel motor not responding",  // Eufy code 1020
  "fault.eufy.robot_is_trapped": "Robot is trapped",  // Eufy code 6
  "fault.eufy.robot_is_trapped_clear_the_obstacles_around": "Robot is trapped — clear the obstacles around it",  // Eufy code 5
  "fault.eufy.robot_low_water": "Robot low water",  // Eufy code 72
  "fault.eufy.robot_on_carpet": "Robot on carpet",  // Eufy code 50
  "fault.eufy.robot_picked_up": "Robot picked up",  // Eufy code 7002
  "fault.eufy.robot_stuck": "Robot stuck",  // Eufy code 7004
  "fault.eufy.robot_suspended": "Robot suspended",  // Eufy code 7001
  "fault.eufy.robot_tilted": "Robot tilted",  // Eufy codes 13, 7053
  "fault.eufy.robot_water_pump_electrical_fault": "Robot water pump electrical fault",  // Eufy code 3011
  "fault.eufy.robot_water_pump_fault": "Robot water pump fault",  // Eufy codes 106, 114, 3012
  "fault.eufy.robot_water_pump_not_responding": "Robot water pump not responding",  // Eufy code 3010
  "fault.eufy.roller_brush_fault": "Roller brush fault",  // Eufy code 2113
  "fault.eufy.roller_brush_jammed_check_for_tangled_hair": "Roller brush jammed — check for tangled hair",  // Eufy code 2112
  "fault.eufy.roller_brush_motor_electrical_fault": "Roller brush motor electrical fault",  // Eufy code 2111
  "fault.eufy.roller_brush_motor_fault": "Roller brush motor fault",  // Eufy code 105
  "fault.eufy.roller_brush_motor_not_responding": "Roller brush motor not responding",  // Eufy code 2110
  "fault.eufy.roller_brush_stuck": "Roller brush stuck",  // Eufy code 4
  "fault.eufy.rotation_motor_stuck": "Rotation motor stuck",  // Eufy code 3123
  "fault.eufy.schedule_failed": "Schedule failed",  // Eufy code 7051
  "fault.eufy.scheduled_clean_could_not_start": "Scheduled clean could not start",  // Eufy code 26
  "fault.eufy.sewage_tank_leak": "Sewage tank leak",  // Eufy code 81
  "fault.eufy.side_brush_fault": "Side brush fault",  // Eufy codes 103, 2212
  "fault.eufy.side_brush_jammed_check_for_tangled_hair": "Side brush jammed — check for tangled hair",  // Eufy code 2213
  "fault.eufy.side_brush_motor_electrical_fault": "Side brush motor electrical fault",  // Eufy code 2211
  "fault.eufy.side_brush_motor_not_responding": "Side brush motor not responding",  // Eufy code 2210
  "fault.eufy.side_brush_stuck": "Side brush stuck",  // Eufy code 3
  "fault.eufy.suction_fan_electrical_fault": "Suction fan electrical fault",  // Eufy code 2011
  "fault.eufy.suction_fan_fault": "Suction fan fault",  // Eufy codes 104, 2012
  "fault.eufy.suction_fan_not_responding": "Suction fan not responding",  // Eufy code 2010
  "fault.eufy.suction_fan_not_spinning_correctly": "Suction fan not spinning correctly — check for a blockage",  // Eufy code 2013
  "fault.eufy.suction_port_obstruction": "Suction port obstruction",  // Eufy code 31
  "fault.eufy.took_too_long_in_a_small_space": "Took too long in a small space",  // Eufy code 7000
  "fault.eufy.ultrasonic_error_cleaning": "Ultrasonic error (cleaning)",  // Eufy code 4120
  "fault.eufy.ultrasonic_error_idle": "Ultrasonic error (idle)",  // Eufy code 4121
  "fault.eufy.ultrasonic_sensor_fault": "Ultrasonic sensor fault",  // Eufy codes 78, 117
  "fault.eufy.undocking_failed": "Undocking failed",  // Eufy code 7040
  "fault.eufy.unreachable_target": "Unreachable target",  // Eufy code 7050
  "fault.eufy.wall_sensor_blocked": "Wall sensor blocked",  // Eufy code 4091
  "fault.eufy.wall_sensor_error": "Wall sensor error",  // Eufy code 4090
  "fault.eufy.wall_sensor_fault": "Wall sensor fault",  // Eufy code 71
  "fault.eufy.water_tank_absent": "Water tank absent",  // Eufy code 75
  "fault.eufy.water_tank_empty": "Water tank empty",  // Eufy code 3013
  "fault.eufy.water_tank_removed": "Water tank removed",  // Eufy code 3020
  "fault.eufy.wheel_module_fault": "Wheel module fault",  // Eufy code 102
  "fault.eufy.wheel_overhanging": "Wheel overhanging",  // Eufy code 7
  "fault.eufy.wheel_stuck": "Wheel stuck",  // Eufy code 2
  "fault.eufy.wi_fi_error": "Wi-Fi error",  // Eufy code 5110
  "fault.eufy.wi_fi_or_bluetooth_fault": "Wi-Fi or Bluetooth fault",  // Eufy code 119
  "fault.eufy.wipe_holder_motor_stuck": "Wipe holder motor stuck",  // Eufy code 32
  "fault.eufy.wiping_bracket_motor_stuck": "Wiping bracket motor stuck",  // Eufy code 33,

  // === ROBOROCK FAULT LABELS (CARD-3 / RF-DOCK) ==========================
  // Same seam as the Eufy block above, but the vendor's codes are ENUM STRINGS
  // rather than numbers — the adapter maps them (adapters/roborock/vocabulary.py
  // ROBOROCK_ERROR_LABEL_KEYS), core carries the key, these are the strings.
  //
  // WE SHIP OUR OWN RATHER THAN USING HA'S. Home Assistant does translate these 53
  // enum states, and the earlier plan was to call hass.localize and skip this table
  // entirely. Measured 2026-08-05, that fails twice: HA has only 11 of our 18
  // languages complete (Arabic 0/53, Polish 10/53, Indonesian 18/53), and
  // hass.localize keys off the HA PROFILE language while this card resolves its own
  // through the per-user globe override — so a user on a German card with an English
  // HA would get English fault names even where HA's German is complete.
  //
  // Register follows the Eufy block: sentence-case descriptive noun phrases, with
  // imperatives kept only where the state IS a maintenance prompt and the action is
  // the information (cf. "Clean dust collector" above).
  //
  // clear_brush_exception, clear_brush_exception_2 and light_touch are deliberately
  // ABSENT — HA's strings for those contradict their own enum names, and an unmapped
  // code falls through to the raw enum, which is honest. See vocabulary.py.
  "fault.roborock.audio_error": "Audio error",  // audio_error
  "fault.roborock.auto_empty_dock_voltage_error": "Auto-empty dock voltage error",  // collect_dust_error_4
  "fault.roborock.battery_error": "Battery error",  // battery_error
  "fault.roborock.bumper_stuck": "Bumper stuck",  // bumper_stuck
  "fault.roborock.camera_error": "Camera error",  // visual_sensor
  "fault.roborock.cannot_cross_carpet": "Cannot cross carpet",  // cannot_cross_carpet
  "fault.roborock.charging_error": "Charging error",  // charging_error
  "fault.roborock.check_clean_water_tank": "Check the clean water tank",  // clear_water_box_hoare
  "fault.roborock.check_cleaning_carousel": "Check the cleaning carousel",  // check_clean_carouse
  "fault.roborock.check_dirty_water_tank": "Check the dirty water tank",  // dirty_water_box_hoare
  "fault.roborock.clean_auto_empty_dock": "Clean the auto-empty dock",  // collect_dust_error_3
  "fault.roborock.clean_dock_water_filter": "Clean the dock water filter",  // filter_screen_exception
  "fault.roborock.clean_water_tank_empty": "Clean water tank empty",  // clear_water_box_exception
  "fault.roborock.cleaning_carousel_error": "Cleaning carousel error",  // clean_carousel_exception
  "fault.roborock.cleaning_carousel_water_full": "Cleaning carousel water full",  // clean_carousel_water_full
  "fault.roborock.cliff_sensor_error": "Cliff sensor error",  // cliff_sensor_error
  "fault.roborock.could_not_return_to_dock": "Could not return to dock",  // return_to_dock_fail
  "fault.roborock.dock_locator_error": "Dock locator error",  // dock_locator_error
  "fault.roborock.dock_not_powered": "Dock not connected to power",  // dock
  "fault.roborock.dustbin_missing": "Dustbin missing",  // no_dustbin
  "fault.roborock.fan_error": "Fan error",  // fan_error
  "fault.roborock.filter_blocked": "Filter blocked",  // filter_blocked
  "fault.roborock.filter_wet_or_blocked": "Filter is wet or blocked",  // strainer_error
  "fault.roborock.internal_error": "Internal error",  // internal_error
  "fault.roborock.invisible_wall_detected": "Invisible wall detected",  // invisible_wall_detected
  "fault.roborock.lidar_blocked": "Lidar blocked",  // lidar_blocked
  "fault.roborock.low_battery": "Low battery",  // low_battery
  "fault.roborock.main_brush_jammed": "Main brush jammed",  // main_brush_jammed
  "fault.roborock.nogo_zone_detected": "No-go zone detected",  // nogo_zone_detected
  "fault.roborock.optical_flow_sensor_dirty": "Optical flow sensor dirty",  // optical_flow_sensor_dirt
  "fault.roborock.reinstall_water_filter": "Reinstall the water filter",  // sink_strainer_hoare
  "fault.roborock.robot_on_carpet": "Robot on carpet",  // robot_on_carpet
  "fault.roborock.robot_tilted": "Robot tilted",  // robot_tilted
  "fault.roborock.robot_trapped": "Robot trapped",  // robot_trapped
  "fault.roborock.side_brush_error": "Side brush error",  // side_brush_error
  "fault.roborock.side_brush_jammed": "Side brush jammed",  // side_brush_jammed
  "fault.roborock.strong_magnetic_field": "Strong magnetic field detected",  // compass_error
  "fault.roborock.temperature_protection": "Temperature protection active",  // temperature_protection
  "fault.roborock.vertical_bumper_pressed": "Vertical bumper pressed",  // vertical_bumper_pressed
  "fault.roborock.vibrarise_jammed": "VibraRise jammed",  // vibrarise_jammed
  "fault.roborock.wall_sensor_dirty": "Wall sensor dirty",  // wall_sensor_dirty
  "fault.roborock.wash_roller_may_be_jammed": "Wash roller may be jammed",  // mopping_roller_1, mopping_roller_2
  "fault.roborock.wash_roller_not_lowered": "Wash roller not lowered properly",  // mopping_roller_error_2
  "fault.roborock.water_carriage_dropped": "Water carriage dropped",  // water_carriage_drop
  "fault.roborock.water_drainage_error": "Water drainage error",  // drain_water_exception
  "fault.roborock.water_supply_error": "Water supply error",  // up_water_exception
  "fault.roborock.wheels_jammed": "Wheels jammed",  // wheels_jammed
  "fault.roborock.wheels_suspended": "Wheels suspended",  // wheels_suspended

  "faults.unknown_code": "Error {code}",  // fallback when the adapter has no label for a fault code — the raw vendor number is honest and searchable
  "faults.unknown": "Unknown error",  // fallback when neither a label key nor a raw code is available
};
