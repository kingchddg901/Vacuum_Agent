# DOC-PASS TRIAGE — findings + intent questions surfaced by the 2026-08-06 reconciliation

**Per Chris's rule: serious questions about how something is SUPPOSED to work get surfaced,
not guessed. This is the standing queue — bug signals become fix tickets, intent questions
get his answer, nothing rots silently. Updated as workflow clusters land.**

## OPEN — needs a fix ticket (code, not docs)

1. **live:FONT-1 remainder — fix landed, NOT confirmed effective.** `41a9735` registers the
   @font-face on the document (the shadow-tree gap was real and is closed; all three bundles
   verified carrying it on the live box). Chris's phone STILL does not render OpenDyslexic
   after force-close + earlier full cache nuke. Status: PARKED by Chris 2026-08-06 ("docs are
   more important"). The shadow-registration gap was necessary-but-not-sufficient, or a
   client layer (WebView font handling? remote-path fetch? something unfound) still
   interposes. Do NOT claim fixed. Next debugging lead when resumed: phone-browser direct
   fetch of /eufy_vacuum/fonts/OpenDyslexic-Regular.woff2 via his EXTERNAL access path, and
   whether the picker's own sample (class .evcc-font-sample-opendyslexic, setting-independent)
   renders the face. A last screenshot is attached in-session (unexamined at park time).
2. **live:RB-ERR-2** — Roborock error enum never enters the `code` field; all five declared
   Roborock tables unreachable at runtime. FINDING-roborock-error-code-carrier.md has the
   chain + fix shape. (Pre-existing, restated here so the queue is complete.)
3. **Config flow shows the Eufy tested model on Roborock installs** — `SUPPORTED_TESTED_MODEL`
   duplicated per-brand; `const.py` imports only Eufy's (orphan 01/02 report, bug signal 3).
4. **`_background_tasks` is a dead ledger** — never appended to anywhere; live phase watchdog
   tasks ride bare `async_create_task` with no shutdown coverage (orphan 30 report, signal 2).
5. **Collapse-path settings loss (UNVERIFIED reachable)** — `_build_steps_phases` collapsing
   adjacent room_group steps rebuilds from `effective_rooms`, discarding per-group settings
   overlays. Needs a reachability check before it becomes a ticket (orphan 30 report, signal 1).
6. **Dead SERVICE_* constants + local redefinition drift** — 4 dead constants in const.py;
   learning/services.py declares 17 service names locally, diverging from the stated
   convention (orphan 01/02 report, signal 2). Cheap hygiene fix.
7. **Stale in-source module docstrings** (queue.py "five services" for 11, etc.) — likely the
   root cause the dev docs drifted; fix the in-file docstrings with the doc pass or they
   re-poison the next transcription (orphan 01/02 report, signal 4).

## OPEN — needs a DOC ticket (the section above is code-only)

1. **`docs/dev/frontend/` was not in the batch-1 reconciliation** — three docs known-stale
   against the 2026-08-06 card work, and two subsystems (the accessibility typeface, the
   fault-label seam) have **no DR section at all**. Full table + rationale in
   `docs/dev/deltas/README.md` § "Epoch 1 coverage caveat". Treat that region as
   unreconciled baseline until a batch-2 pass closes it. The typeface omission is not
   academic: nothing in prose said a font token is subject to the shadow/body split, which
   is how `live:FONT-1` shipped inert for two days.

## QUESTIONS FOR CHRIS — intent, not defects

1. **`discovery.py` trigger semantics:** the doc said auto-discovery fires on "first non-idle
   state"; code fires on entering DOCKED (run-end), plus map-change/reload/timer. Which is the
   intended design? (If docked-on-purpose — rooms are freshest right after a run — say so and
   the doc gets the rationale; if the doc described the real intent, this is a regression.)
2. **Phased-Jobs doc depth:** both dev-jobs auditors and orphan reports left hedged pointers
   instead of documenting the parent/child finalize schema (your rebuild boundary honored).
   Stand pat until the rebuild is declared complete, or want a thin "current shape, subject
   to change" section sooner?
3. *(placeholder — user-guide cluster intent questions land here when the workflow returns;
   any patch section depending on an answer is HELD, not applied.)*

## RESOLVED THIS PASS (for the record)

- RP-047(b): shipped, then REVERTED on live evidence — surviving design now documented in 06.
- The 06/07/30 orphan patches + 5 orphan reports: quarantined in scratchpad/docpass as
  apply-time cross-checks; tree never accepted unverified edits after the reset.


---

# ROUND 2 — repair-round bug signals (2026-08-06, runs wf_c3085752-b7b + wf_16fa0e1a-3f3)

Doc-vs-code disagreements where the CODE side looks wrong, surfaced during the
repaired truth pass. Docs were NOT papered over these. Highest-priority first.

## Live bugs (code defects, users can hit)

- **R2-BUG-1 [fe-architecture]** `src/actions/rooms.js` clearRoomAccessGraph (~:553-563) reads `this.selectedVacuum()` / `this.activeMapId()` — neither exists on VacuumCardActions; throws TypeError when invoked. Every sibling uses `this.state.vacuumEntityId()` / `this.state.activeMapId()`.
- **R2-BUG-2 [ug-review]** `learning/manager.py` `_job_matches` (:1765-1784) never checks `profile_key_filter` — the Filters-row Profile chip and Profile Matcher chip set `profile_key` and refetch, but Jobs count + Runs list ignore it. (Carried from round 1, still live.)
- **R2-BUG-3 [ug-review]** `main.js` `_handleGlobalKeydown` closers (~:1668-1700) omit job-summary — Escape closes every other modal but not the Job Summary modal. Doc describes the buggy behavior accurately.
- **R2-BUG-4 [dev-rooms-maps]** `label_anchor` silently dropped by both room writers (rooms/room_manager.py build_managed_rooms, maps/map_manager.py rebuild_map_bucket) — neither builds through a RoomConfig carrying the field; only plan_migration's raw-dict carry preserves it.
- **R2-BUG-5 [fe-visual]** Two contradictory beliefs about raster `rid` == managed `room.id`: `_bindSelectionScrim` (bindings/map.js:269-288) vs clean-order badge lookup (renderers/map.js:626-668). Needs one canonical answer.
- **R2-BUG-6 [dev-core]** `async_shutdown` registered via entry.async_on_unload BEFORE async_initialize — first action awaits storage; on a never-initialized manager that path is not the documented no-op. Verify + guard.

## Stale source prose (docstrings/comments contradicting their own code)

- **R2-STALE-1 [dev-jobs]** phase_runner.py:539-541 — _record_phase_to_parent docstring claims no per-phase child exists; wave-1 body writes full child records with record_id + phase_key.
- **R2-STALE-2 [dev-jobs]** core/manager.py:6103-6107 — 'wave 0' comment repeats the same disproven claim.
- **R2-STALE-3 [dev-jobs]** queue_engine.py:443-444 — phased_job_id_for 'read by nothing yet'; read at core/manager.py:6109.
- **R2-STALE-4 [dev-adapters]** eufy/adapter.py:756 — room_attribution 'DORMANT until W5b/W5c land'; both shipped and wired.
- **R2-STALE-5 [dev-adapters]** roborock maintenance_components.py:22-24 + adapter.py:670 — 'Thirteen copies' comments for a field removed 2026-07-30 (and only 4/12 ever declared it).
- **R2-STALE-6 [dev-rooms-maps]** source_refresh.py:292-303 — docstring says five exits, lists six, implements SEVEN (superseded_by_newer_refresh uncounted).
- **R2-STALE-7 [ug-daily]** src/renderers/rooms.js:428-429 — comment claims no 'included' suffix; render always appends it.
- **R2-STALE-8 [testing-docs]** tests/adapters/conftest.py:78 — docstring says Yield, body returns.

## Contract / typing mismatches

- **R2-TYPE-1 [dev-adapters]** config_schema error_tracking blocks typed list[int]/dict[int,str] (eufy/config_schema.py:610-712) but shipping Roborock declares all five STRING-keyed (roborock/vocabulary.py:224+). Known from RB-ERR-2 family; the type annotations are the wrong side.

## Dead / unread / uncovered code

- **R2-DEAD-1 [dev-adapters]** external_run.py _extract_return_overhead (:272-322) stamps return_overhead_s/return_intervals (:425-426); NOTHING reads either field anywhere.
- **R2-DEAD-2 [ug-setup]** harness mapping-badges gallery fixture targets removed mapping_review view; every theme detail page renders a dead 'Unknown view' tile (harness/preview.mjs FULL_GALLERIES).
- **R2-DEAD-3 [ug-setup]** src/renderers/badge-marks.js — six shape marks, zero importers (retired Map Bounds tab leftover).
- **R2-COV-1 [testing-docs]** services/queue.py queue-break/step handlers (:202-244) + register closures (:266-281) have zero test coverage.
- **R2-TEST-1 [testing-docs]** tests/adapters/test_brand_selection.py::test_register_brand_adapter_falls_back_and_says_so reproducibly fails (empty caplog) under exactly `tests/unit tests/integration tests/adapters` — order-dependent test defect.
- **R2-DEAD-4 [live-debug 2026-08-06]** `src/styles/foundation.js:276` — the whole `.evcc-card` block is dead: no element carries the class (shell frame emits `.evcc-shell`). It hid the typeface read for two fix rounds (live:FONT-1 remainder, ecbe77f). Delete the block or retarget deliberately; TF-7 now guards the typeface read specifically but the rest of the block (background/radius/color) is still silently inert.

## live:FONT-1 — RESOLVED, USER-CONFIRMED 2026-08-06 (screenshot, OpenDyslexic rendering)

Three stacked bugs, each masking the next; all fixed + pinned (TF-1..TF-10):
1. @font-face never registered on the document (41a9735).
2. Token read on phantom selector .evcc-card + theme inline token overriding — a11y-token
   chain design, Chris's call (ecbe77f). Dead .evcc-card block = R2-DEAD-4.
3. Fallback-less var(--paper-font-body1_-_font-family) made the setter guaranteed-invalid
   on paper-var-less HA (d3f81e6) — found via headless-Chrome reproduction with the exact
   shipped CSS; probe lives in session scratchpad, technique worth reusing.
Deploy gotcha that cost two false deploys: npm run build writes dist/, NOT
custom_components/frontend/ — copy dist/ artifacts or use build:deploy.

Tail items (LOW, open):
- FONT-TAIL-1: form controls don't inherit font-family — "Search themes..." placeholder
  renders system font under OpenDyslexic; inputs/selects need font: inherit.
- HDR-BATT-1: header battery is a bare percent (no label/icon, since v0.9.0) and the
  .evcc-battery.low/.critical classes are never applied by the renderer (dead styling).
  Chris flagged the missing label; offer stands.
