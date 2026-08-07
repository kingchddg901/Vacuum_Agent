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
- ~~**R2-BUG-5 [fe-visual]** Two contradictory beliefs about raster `rid` == managed `room.id`~~
  **RESOLVED 2026-08-06 — NOT a code defect. No code changed.** It was one verified observation
  against one unsourced assertion, not two findings in tension. (a) The raster `rid` space is
  **Eufy-only** — `rooms_from_room_pixels` is the "Eufy storage backend" per its own docstring and
  `map_source.py:373` says Roborock has no per-pixel raster — so the comment's "DIFFERENT id spaces
  on real devices" cannot mean Roborock, and the only brand with a raster is the one where all
  three ids were observed to coincide. (b) `c4207b9`, the commit that wrote both the name-bridge
  and the "empirically verified" claim, describes its own doc change as "rid==room.id==room_names
  identity" — identity in the message, divergence in the comment, same commit.
  Fix was to the CLAIM, not the code: comment downgraded to defensive-not-required, doc §2
  rewritten as RESOLVED. The three identity paths were left alone deliberately — rewriting working
  code to satisfy an unsourced comment is the 00a §9 failure. Name-bridge kept (costs one lookup,
  cannot miscolor, safe side if unseen firmware ever diverges).
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

## ROUND 2 ADJUDICATION (2026-08-06, Opus) — every remaining item has a verdict

Each was checked against source before acting. Three of the eight were wrong as filed;
saying so is the point of the pass.

| id | verdict |
|---|---|
| R2-BUG-1/3, R2-DEAD-4 | **FIXED** `c9e0526` |
| R2-BUG-5 | **RESOLVED, no code change** `3531e02` — unsourced claim vs verified observation |
| R2-BUG-7 | **FIXED** `54707f8` — ticket named 1 of 5 blocking ops |
| R2-STALE-1..6, 8 | **FIXED** `54707f8` (+ an unreported Roborock sibling of S4) |
| R2-STALE-7 | **NOT REPRODUCIBLE** — cited lines are a zone-counting comment; no "included suffix" claim exists anywhere in `src/renderers/rooms.js`. Not touched. |
| R2-BUG-6 | **REAL, but MISDIAGNOSED — and far worse than filed.** Filed as "first action awaits storage; on a never-initialized manager that path is not the documented no-op", implying an AttributeError. There is none: `__init__` seeds `self.data = {}` at :312. The actual bug is that the seed is *flushable* — `async_initialize` only swaps in the real store at :405, and `__init__.py:277` registers the unload callback BEFORE awaiting init, so a failure at/before `async_load` makes `async_shutdown` write `{}` over the ENTIRE store: every managed room, map, learned profile, theme. Silent total data loss triggered by an unrelated setup failure. Fixed with a `_loaded` flag (NOT `hasattr`, which guards nothing since the attribute always exists; NOT truthiness, since a fresh install's empty store is legitimately flushable). Pinned both ways — MS-4 no-flush-before-load, MS-5 still-flushes-after. |
| R2-BUG-2 | **NOT a mechanical fix — needs a semantics call.** `profile_key` exists only on ROOM-PROFILE index entries (`stats_rebuilder.py:1098-1107`); job entries have none, because a job spans many rooms which may each use a different profile. So "add the filter to `_job_matches`" would filter on a field that does not exist and return zero jobs. Real options: (a) match a job if ANY of its rooms used that profile, (b) disable the Profile chip for the Jobs count + Runs list. Chris's call. |
| R2-DEAD-1 | **FALSE as filed.** "NOTHING reads either field anywhere" — `tests/integration/test_manager_external_finalize.py` asserts on both at :245-247, :408, :440-441. Production-dead but test-covered, and the fields are PERSISTED into external-run records, so deleting them is a stored-data shape change, not dead-code removal. Not touched. |
| R2-DEAD-3 | **FALSE.** `src/renderers/badge-marks.js` has importers — `harness/mount-entry.js:46` imports `BADGE_MARK_PATHS`/`MARK_VIEWBOX`, and `harness/tests/shape-marks.spec.mjs` exists to test it. The finding appears to have grepped only `src/`. Not touched. |
| R2-DEAD-2 | **REAL, not yet done.** `mapping_review` is gone from the card (`src/` has only an i18n comment) but the harness still registers it — `harness/lib/mount-page.mjs:150`, `harness/preview.mjs:52` — and `harness/tests/cvd.spec.mjs:32` actively renders it, so that spec asserts against a dead view. Touches visual baselines, so it wants its own pass. |
| R2-TYPE-1 | **DEFER to Epoch 2** — same family as `live:RB-ERR-2`. Making the annotations honest about tables nothing can reach at runtime is half a fix; it should land with the capture change. |
| R2-COV-1, R2-TEST-1 | Open. |

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

### Typeface mechanism FINISHED (ec30b11, 2026-08-06) — FONT-TAIL-1 CLOSED
All per-font CSS generates from FONT_DEFS (faces/setters/sample/theme chip); form controls
inherit on both surfaces; theme Font Family = preset chips (names verbatim, no i18n) + text
escape hatch; wiring tests assert BUILT CSS, 13 pins; 911 logic tests green; deployed live.
HDR-BATT-1 (header battery label + dead low/critical classes) remains the only font-adjacent
open item.

### HDR-BATT-1 CLOSED (d93a971, 2026-08-06)
Header battery: nav.battery label (18 locales) + low/critical bands wired (<=20/<=10);
HB-1/2 pins. Ratchet repinned same push (684b605): 57 accepted-class pairs from the
job-summary + typeface features, all within Chris's adjudicated categories.

### Drop-in fonts SHIPPED (cefc688 + 12e3b63, 2026-08-06) + one new bug signal
Backend-verified user fonts: config/eufy_vacuum/fonts/<id>/ + user_fonts.py (fontTools cmap
-> catalog.json); manifest now REQUIRES fonttools[woff2] (install verified live). OpenDyslexic
FONT_SUPPORT widened en->12 locales by cmap evidence (the missing-l/r/i judgement was false).
testdrop demo font live on Chris's box (delete config/eufy_vacuum/fonts/testdrop + restart to
remove).
- **Test reconciliation (2026-08-06, Opus): FS-3 / FS-4 / LCF-2 were left RED by the widening.**
  They encoded the disproven premise (pl/cs/tr unsupported). Re-verified the widening
  independently before touching them — read the cmap out of both shipped woff2 directly: 1586
  codepoints, all 12 claimed locales fully covered incl. ł ą ř ů ı İ ğ, all 6 excluded locales at
  ZERO glyphs. The widening is correct; the tests were stale. Repaired to keep the DOCTRINE rather
  than to go green: FS-3 now uses sv/hu/vi — Latin-script locales the font *would* render fine
  (cmap carries å ä ö, ő ű, ơ ư ạ) but nobody has proven, which states "proof, not coverage" more
  sharply than the original ever did. JS suite 919/919.
- **R2-BUG-7 [live log]** history_store.py:411 read_json does a BLOCKING file read in the event
  loop via _reap_stranded_phased_jobs (core/manager.py:602) at startup — HA flags it and asks
  for a bug report. ~~Wrap in async_add_executor_job.~~

  **FIX SHAPE CORRECTED 2026-08-06 — the flagged read is 1 of 5 blocking ops, and not the
  slowest.** Verified at source, current tree. `_reap_stranded_phased_jobs`
  (core/manager.py:572) blocks on all of:
  1. `store.get_paths()` → two `mkdir(parents=True, exist_ok=True)` (history_store.py:385-386);
  2. `paths.phased_jobs_dir.exists()` (:598);
  3. `paths.phased_jobs_dir.glob("*.json")` (:600) — full directory scan;
  4. `store.read_json(path)` → `exists` + `is_file` + `read_text` (:411) ← **the one HA caught**;
  5. `store.close_phased_job()` → `load_phased_job()` read (:884) **plus `write_json()`** —
     atomic temp-write + `os.replace` (history_store.py:1006).

  Wrapping only the read therefore leaves the **write** — the slowest of the five — in the
  event loop, and HA keeps warning. The ticket as written would read as fixed and not be.

  Correct fix: the call site is inside `async def async_initialize` (core/manager.py:570), so
  `await self.hass.async_add_executor_job(...)` is available and idiomatic here (61 existing
  uses). Hand the **whole sync method** to the executor, not the read.

  **Caveat that must not be skipped:** snapshot `live` and the vac_id list in the event loop
  and pass them in, rather than letting the executor thread walk `self.data["active_jobs"]`.
  `rearm_dock_phase_if_needed` runs four lines earlier (:566) and re-spawns dock pollers that
  can mutate `active_jobs`; iterating it from another thread is a "dictionary changed size
  during iteration" race. The method's blanket `except Exception` (:621, "startup housekeeping
  must never block setup") would swallow that into a **silent no-reap** — parents accumulate
  forever, which is the exact failure the reaper was written to prevent.

## D-6 RULINGS (Chris, 2026-08-07)

**Q2 RULED — FULL DEPTH.** The phased-job parent/child finalize schema becomes a real DR
section (docs 06/30), and the queue-break services get real documentation in
docs/advanced/03-services.md — retiring their entries from _check_advanced_doc_drift.py's
by-design exempt list (document, then unexempt; the list may only shrink).
WORK ORDER (SONNET-TIER — do not run on Fable): document get_queue_steps,
add_queue_break, remove_queue_break, clear_queue_breaks, set_queue_breaks,
add_queue_zone from services/queue.py:202-281 source (params, clamps, step_types
STEPPED_STEP_TYPES vocabulary); author the phased-job record schema section in doc 06
(parent/child completed_job records, phase_key stamping, phased_job_id, merge/reap
lifecycle — sources jobs/phase_runner.py _finalize_phase_as_child + _record_phase_to_parent,
learning/history_store, core/manager reapers) + doc 30 cross-ref; verify every field
against source per DR standard 4-5; run the drift checker to 0/0 with the queue-break
exempts REMOVED; mkdocs --strict; private-index commit to master. NOTE: R2-COV-1 (queue
handler test coverage) is SEPARATE and stays in the held test queue — docs only here.

**Q1 RULED (Chris, 2026-08-07): DOCKED-ON-PURPOSE — map-swap-protection semantics.**
Intended design: discovery fires once the pose has updated and the map is SAFE (run over;
mid-run maps churn / may be mid-swap). Docs updated same-commit: 01-arch:523 corrected,
04-listeners sec 9 carries the rationale. "first non-idle" was wrong about intent, not
just detail — NOT a code regression. Held sections unfrozen. Original question text: code fires discovery on transition-INTO-docked
(+ map-change/reload/6h timer, adapter-declared via discovery.auto_refresh_on, default set
drift.py:98); old doc said "first non-idle state" (run start). Choice: (a) docked-on-purpose
(fresh-data rationale — the edge filtering reads deliberate) -> doc gets the rationale;
(b) run-start was the intent -> regression ticket. Dependent doc sections stay HELD.
