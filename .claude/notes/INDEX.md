# eufy-vacuum-manager — engineering notes (migrated from central memory)

Local, **git-ignored** knowledge base for this repo — the deep technical detail
that used to live in Claude's central memory index. Read these when working the
corresponding subsystem; the central `MEMORY.md` keeps only a pointer here.

Same format as the central index: one tight hook line per file, detail in the
file. Grow freely — this is not size-capped.

## Audits
- ⏳ [**TASK — DR-doc drift from 2026-08-06**](TASK-doc-drift-2026-08-06.md) — OPEN, piecemeal one subsystem per pass. 154 commits landed inside DR-graded subsystems; `23-error-tracker.md` is PROVEN confidently-wrong (says codes are NUMERIC ×4, core carries enum strings since `1b3155c`) and would teach a rebuild to reproduce the exact bug fixed that day. **⚠ READ THE BANNER FIRST — under the Documentation Epoch model the fix is a DEV DELTA, not a DR edit; only the epoch-closing audit promotes dev → DR.** Wide-read authoring → Fable
- ⏳ [**TASK — write the audit methodology doc**](TASK-write-audit-methodology.md) — PENDING; includes the **CV/segmentor EXCLUSION** and the generalised rule (if correctness is EMPIRICAL not textual, this method produces unfalsifiable noise the verifiers cannot kill). PENDING, fires after the FINAL subsystem audit. Distil the method that works, NOT a diary; raw material captured in the file so the write-up isn't reconstructed from a lossy summary
- [**OPEN FIX CHECKLIST**](OPEN-FIX-CHECKLIST.md) — every unapplied finding; regenerate with `python .claude/notes/_gen_audit_doc.py` after each audit (manifest: `_audit_runs.json`)
- [Lifecycle hostile audit — 2026-07-30 CALIBRATION](audit-lifecycle-calibration-2026-07-30.md) — active-job lifecycle + exactly-once finalization; 8 agents, 1.9M tok, 41min; **RC-1 = no pre-await finalize claim (5-agent confirm)**, RC-1b cancel race poisons battery aggregates PERMANENTLY, `ended_at` never written (battery post_job dead), dead recharge-end branch, multi-room phase credits room[0] into learned baselines; 1 CRIT + 5 HIGH; 17 over-reaches killed in verification; repair order §9 = ~15 lines for the top 4

## eufy_vacuum — architecture & decisions
- ⏳ [**Stall capture — cropped map + position (issue #47)**](DESIGN-stall-capture-issue47.md) — SCOPED, not started; **position comes from the POSE (`robot_anchor`, pre-normalized), NEVER `robot_position_x/y` which are raw uint32 ZUPT-clamped** (Chris's ruling); only missing piece is fetching the map image backend-side (2 platforms, both brands already declare the entity); ±30s pose-ring capture on stall distinguishes wedged from slow
- [Map-source lifecycle + sticky](reference_map_source_lifecycle.md) — Roborock map HA-mem-only; Eufy .storage-backed; sticky-hold 6h TTL
- [Overview/architecture/deploy](project_eufy_vacuum.md) — state 2026-04-29; docs phase, legacy onboarding removed
- [Locked architecture decisions](project_eufy_architecture_decisions.md) — Option C singleton-domain; room identity TWO-LAYER (room_id + name-slug)
- [Origin lineage](project_eufy_origin_lineage.md) — ~7-stage pre-integration evolution; explains no-helpers/no-CV/timing-first
- [HA quality scale stance](project_eufy_quality_stance.md) — Bronze done; Silver WIP; Gold+ incompatible with adapter pattern
- [Manager split - re-bundled x2](project_manager_split.md) — bundled-subsystem=THE pattern (delegator for prod-callers, repoint white-box)
- [Dispatch-engine seam - phases 1&2](project_dispatch_engine.md) — payload SHAPE + job model adapter-owned; clean_area + pre-calls + live_queue
- [Room seg + job-segmenter seam - v0.9.17](project_room_segmentation_unified.md) — counter-plateau seg + external-run capture + pluggable JobSegmenter
- [Custom segment path - v0.10.0](project_custom_segment_path.md) — many named custom layouts per map + composer; CV stays special
- [Eufy clean_area is global-only](reference_eufy_clean_area_global.md) — rich send_command room_clean = only per-room route; mqtt drops read-back
- [Two-path dispatch concept](project_two_path_dispatch.md) — full-power send_command vs HA-native clean_area (ordered); not built
- [HA native segment/area clean = voice](reference_ha_vacuum_clean_area_segments.md) — CLEAN_AREA + Segment + clean_segments via Assist; -> proxy or PR
- [HA voice WIZARD - multi-turn, no LLM](reference_ha_conversation_agent_multiturn.md) — continue_conversation force-routes follow-ups; hassil CAN'T slot-fill
- [Eufy inter-session coord drift](reference_eufy_intersession_coord_drift.md) — re-localizes origin every session; absolute coords NOT cross-session comparable
- [Boundary derivation DEAD](project_boundary_derivation_dead.md) — trace→room-boundary removed (494c6f6); revive ONLY w/ proven stable-origin
- [Mapping shelve + bounds-off-map](project_mapping_shelve.md) — mapping-inference + RoomBoundsStore DELETED; room tracking 100% off native
- [HA CAN switch Eufy maps - PROVEN](reference_eufy_biz_map_switch.md) — MAP_LOAD over DPS 172; fork PR #150 OPEN; VA switcher PARKED
- [Room ID -> name (vacuum.alfred map_6)](project_room_ids.md) — IDs 1-11 (no ID 10)
- [P2P full-local odds - RESEARCHED](reference_eufy_p2p_full_local_assessment.md) — zero-cloud ~3-10%; p2p_info DORMANT; PIVOT = de-cloud AWS-IoT
- [Roborock adapter - v1.0.0](project_roborock_adapter_planned.md) — per-room clean + native live rollover + per-room fan; S6 mop unsettable

## Frontend / card / themes
- [Card input focus-restore](reference_card_input_focus.md) — refocuses inputs across re-renders; #37 FIXED v1.6.4
- [Card entity-suggestions - SHIPPED](project_card_entity_suggestions.md) — HA 2026.6 getEntitySuggestion; room+dashboard auto-suggest MANAGED vacuums
- [Card bundle is a build artifact](reference_frontend_build.md) — edit src/, run npm run build:deploy; never hand-edit the minified bundle
- [i18n: never esc() t() output](reference_i18n_double_escape.md) — translate() escapes by default; esc() on t() -> literal &#39
- [Upkeep-guide i18n pipeline](reference_guide_translation_pipeline.md) — guides own py->js sync; empty notes:[] silently shows English
- [Profile-label localization = FRONTEND](reference_profile_label_localization.md) — per-globe via _builtInProfileI18nKey + _localizedProfile; backend English=fallback
- [Theme-token analysis gotchas](reference_theme_token_usage_analysis.md) — scan src CSS + animal-svg + preloaded.py; handle wrapped var(
- [Modal token derivation gotcha](reference_modal_token_derivation.md) — --evcc-modal-* on body-level host, derived from canonical
- [Theme tag/search system - v1.0.0](project_theme_tag_system.md) — auto-facets + colorblind-safe + provenance + vibe-tags; core extracted→theme-kit
- [Render harness + theme gallery](project_render_harness.md) — headless Playwright (visual-reg/CVD/intake) + Pages gallery + theme bot; NOT extracted (niche)
- [Community animal submission](project_animal_submission.md) — declarative descriptor + sanitise + codegen .js (never accept JS); Wave 1 shipped
- [Mittens - memorial mascot](project_mittens_mascot.md) — baked grey-brown tabby; markings literal/non-themeable, only eye dynamic
- [Run-profile break-insert fix - FIXED 2026-08-02](reference_run_profile_break_insert_fix.md) — CARD-6 clause(1) made Add Charge/Wait a silent no-op + STRANDED new-profile creation entirely (collapsed view's only reveal button); insert-before-last + always-expand + toast

## Testing
- [Don't CI-guard blocking I/O](reference_blocking_io_test_guard.md) — block_async_io unreliable in pytest-homeassistant; rely on runtime detection
- [Testing-doc drift + gap-close](project_testing_drift_gap_pattern.md) — update_test_docs.py owns table cells; digest->audit->apply->gated
- [Eufy adapter test harness - DONE](project_eufy_adapter_harness_planned.md) — brand-agnostic contract suite + Eufy deep tests; segmentor 91%
- [Pre-baked eufy-vacuum-test image](reference_eufy_test_image.md) — deps baked, skips ~78s pip; rebuild on requirements_test.txt change
- [Canonical htmlcov is explicit-only](reference_htmlcov_explicit_only.md) — written ONLY by --cov-report=html:htmlcov; agents use htmlcov_scratch/
- [CI + release gotchas](project_eufy_ci_actions_planned.md) — tests/validate/card-visual; visual change = commit-local→repin→push

## Eufy device/firmware references
- [Factory reset wipes everything](reference_eufy_factory_reset.md) — maps + cloud config gone → new-user; per-map VA data orphaned; check entity_id survival
- [Eufy map editor = geometry not semantics](reference_eufy_map_editor_geometry.md) — refuses wall-less/irregular splits; saved-zone "draw a box" IS the escape
- [Omni E28 (T2352)](project_eufy_e28_support.md) — flagship->'generic'; #38 FIXED v1.6.7; C2 SHIPPED v1.7.0
- [Eufy map outline-offset sign](reference_eufy_map_outline_offset.md) — render offset = (outline_origin-origin)/res (sign INVERTED, fixed 2026-07-02)
- [Alfred error_message always empty](reference_alfred_error_message_firmware.md) — firmware; use binary_sensor.alfred_active_run_has_error; faults ride error[]
- [Alfred clean-completion pattern](reference_alfred_clean_completion_pattern.md) — 5-event signature ~2s after dock; active_run_has_error->off + dock+charging
- [Eufy task_status lifecycle strings](reference_eufy_task_status_lifecycle.md) — mid-run-return vs terminal "Completed"; gates external-run grace
- [Saved-zone run signals SHIPPED](reference_eufy_zone_run_signals.md) — target="N zone"/work_mode=Zone; zone-learning W0-3 done (wall-clock per zone_id+mode)
- [eufy-clean scene select FIRES](reference_eufy_scene_select_fires.md) — select.<obj>_scene FIRES on select_option; arm locally + fire only on explicit
- [datetime-local format varies](reference_datetime_local_parsing.md) — Chrome includes seconds, Firefox doesn't; parse with tolerant regex
- [HA history compact-format rows](reference_ha_history_compact_format.md) — keys s/a/lu/lc not state/attributes; lu/lc float seconds
- [Eufy MQTT push-only staleness](reference_eufy_mqtt_transport_staleness.md) — Alfred update_interval None; push can go silently stale (#160), transport-inherent; reaper backstops
