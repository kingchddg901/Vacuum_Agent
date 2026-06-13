# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow semantic-ish versioning.

Releases before 0.9.10 are recorded as
[GitHub tags/releases](https://github.com/kingchddg901/Vacuum_Agent/releases)
only.

## [0.10.3] - 2026-06-13

Map-editor visibility fixes (custom-layout composer + CV vertex editing).

### Fixed
- **The composer's selection outline stays visible on light / photo map backdrops.**
  A selected shape's bright outline could wash out over a light custom-photo backdrop;
  it now carries a thin black halo on each side, so it reads on any backdrop.
- **Map-editor lines and vertex handles no longer balloon when you zoom in.** The
  CV-segment polygon stroke and the vertex grab dots were sized in map units, so they
  grew as you zoomed to align a room and hid the floor plan underneath. They are now a
  fixed thin size at any zoom level.

## [0.10.2] - 2026-06-13

Light-theme readability fixes — the card now renders light themes cleanly,
surfaced by adding the gallery's first light theme.

### Fixed
- **Room order numbers (#1–#5) are readable on light themes.** The room-card order
  label inherited a fixed near-white colour and disappeared on light surfaces; it
  now tracks the theme's secondary text colour (unchanged on dark themes).
- **The room-rules "Disabled" tag keeps its pill on light themes.** Its background
  and border were hard-coded white; they now use the surface/border tokens.

## [0.10.1] - 2026-06-13

A small theming fix.

### Fixed
- **Modals now follow the active theme.** A custom theme that set only the core
  colors — surfaces, text, and accent, as hand- and AI-authored themes typically
  do — left every modal (the room editor, the app-started-run review wizard, and
  the rest) on the default dark palette, because the modal/overlay token family
  didn't derive from those core colors. Modals now derive their surfaces, text,
  and accent from the active theme, so any theme themes its modals too. A
  light-mode default is preserved, and the built-in themes are unchanged.

## [0.10.0] - 2026-06-12

A UI-heavy release: hand-drawn custom map layouts, a real documentation site, and
a reworked profile filter — plus a batch of fixes.

### Added
- **Named custom map layouts.** Keep several hand-drawn layouts per vacuum
  alongside Auto/CV detection. Each layout can have its own backdrop, rooms, room
  links, and mascot dock spot. Build rooms from primitive shapes — rectangles and
  circles — then move, scale, resize, rotate, merge, or subtract cutouts. Link
  each custom room to a real vacuum room, then save and re-edit later. See
  [Making your own maps](https://kingchddg901.github.io/Vacuum_Agent/docs/user-guide/16-making-your-own-maps/).
- **Documentation site.** The docs now render as a searchable
  [MkDocs site on GitHub Pages](https://kingchddg901.github.io/Vacuum_Agent/docs/),
  cross-linked with the theme gallery.
- **Profile filters reworked.** The Metrics and Learning Review profile filters
  now have a search box, a height-capped scroll area, and settings-disambiguated
  chips. Duplicate-named profiles, such as several "Kitchen Vacuum Quick"
  variants, show their settings so you can tell them apart on both the chips and
  the result cards.
- **Independent floor-texture toggles.** Map polygons and room cards can now
  control floor textures separately.
- **Custom-map polish.** Added mascot dock spots and composer shape rotation.

### Fixed
- Large map backdrops no longer exceed Home Assistant's 4 MiB websocket limit and
  drop the connection. Uploads are resized/recompressed client-side while
  preserving transparency.
- Non-first custom layouts now render their room-control map correctly.
- Dashboard snapshots no longer block the event loop on a `room_stats` read.

### Internal
- Large test-coverage and documentation-reconciliation pass.

## [0.9.17] - 2026-06-08

> The external-run capture + review capability in this release was driven entirely by
> [@chubban-lgtm](https://github.com/chubban-lgtm)'s question in
> [#4](https://github.com/kingchddg901/Vacuum_Agent/issues/4) — *"does it not use the
> runs from the eufy app for learning review?"* I didn't think it was possible at first;
> a little digging proved otherwise. Thank you.

### Added
- **External-run review wizard: server-side re-segmentation.** The "review an
  external (app-driven) run" flow no longer only lets you merge rooms client-side
  — it now re-segments on the backend from the raw counter trace. Step 1 is a
  **room-count stepper** plus a per-boundary **Split here** / **Merge up** control
  (action-first labels — the button says what it *does*); step 2 is a **per-room
  settings editor** for `fan_speed` / `clean_intensity` / `water_level` drawn from
  the adapter vocabulary (it mirrors the live room editor). The card calls the new
  `eufy_vacuum.resegment_external_run` service (`src/actions/external-jobs.js`),
  which takes either an `expected_rooms` count *or* an explicit `active_boundaries`
  list (mutually exclusive) and returns the re-segmented record.
- **Pending external-run schema v2.** Finalizing an external run now persists the
  raw `counter_samples` + `settings_samples` and the full candidate-boundary pool
  alongside the segments (`learning/external_ingest.py`,
  `PENDING_SCHEMA_VERSION = 2`), so a run can be re-segmented after the fact
  without re-driving the robot. Records are flagged `resegmentable` when samples
  are present; v1 records (no samples) gracefully degrade to the legacy
  merge-only view. Samples are stripped from every served/returned record
  (`strip_samples`) so the API stays light.
- **Transit-aware boundary detection.** `counter_segmentation.py` is decomposed
  into `find_candidates` → `select_active` → `build_segments`. `find_candidates`
  now surfaces a **`transit`** boundary kind (a 60–90 s flat-area inter-room move)
  in addition to `wash_plateau` / `area_jump` — the real-transit case the old
  single-pass filter silently dropped. The legacy `segment_counters()` is kept as
  a **byte-identical back-compat wrapper** (transit disabled), so the
  finalize/history path is unchanged.
- **Live queue: running-long & skipped indicators.** `get_job_progress_snapshot`
  now reports a soft **`running_long`** anomaly (the current room is past
  `running_long_ratio` × its estimate but below the existing 2× stall) and a
  conservative **`skipped`** signal (a queued room strictly before the current one
  that never completed). The queue chips render these as a warning ring
  (running-long) and a dashed, struck-through chip (skipped); a new
  `eufy_vacuum_room_skipped` event (`EVENT_ROOM_SKIPPED`) fires once per skipped
  room.
- **Brand-agnostic JOB-segmenter engine seam.** The counter/run segmenter — the
  per-room boundary detector that reads the `cleaning_time` / `cleaning_area`
  counters — is now pluggable, mirroring the dispatch-engine pattern
  (`learning/job_segmenter_engines.py`, modelled on `queue/dispatch_engines.py`).
  An adapter selects an engine via a new `job_segmenter.engine` config key; the
  framework resolves it from `_JOB_SEGMENTER_ENGINES`. This is the COUNTER
  segmenter — distinct from the MAP segmenter (`mapping/segmenter_engines.py`,
  `eufy_cv_v1`), which is unchanged. The engine owns the brand-specific stages
  (`find_candidates`, `build_segments`) and the legacy one-shot composition
  (`segment_legacy`); `select_active` stays a brand-agnostic *framework* function
  (`counter_segmentation.select_active`) so the external-review wizard's
  count/toggle logic is uniform across brands. Canonical cross-engine
  `JobBoundaryCandidate` / `JobSegment` TypedDicts document the contract.
  `EufyCounterSegmenter` (`eufy_counter_v1`) delegates verbatim to the
  `counter_segmentation` primitives and defines its `DEFAULT_TUNING` *by
  reference* to that module's constants, so the Eufy path is byte-for-byte
  identical by construction. Unlike the map seam, an absent/unknown engine falls
  back to the **Eufy** engine (not a noop), so live rollover, external-run ingest,
  and learned history keep working with no adapter registered. All three counter
  consumers now route through the engine — learned history
  (`learning/history_store.py`), external-run ingest
  (`learning/external_ingest.py`), and live rollover (`jobs/active_job.py`).

### Changed
- **Live current-room tracking is now transit-aware.** The 5 s job-progress tick
  (`jobs/active_job.py`) advances the current room on a real 60–90 s inter-room
  transit, not only on a wash/area-jump boundary, via a new transit-aware
  boundary count — fixing rooms that the live queue under-counted mid-run. The
  finalize/history segmentation is untouched.
- **Brand-agnostic adapter hooks (Eufy is the default, byte-identical).** The
  Eufy adapter config gains a `live_transition` block (boundary gaps, cadence,
  `rollover_kinds`, `native_transition_source`) and an `anomaly` block
  (`running_long_ratio` 1.5, `stall_ratio` 2.0). The previously-hardcoded
  constants in `planning/run_plan.py` (per-level water rate, wash-interval bounds,
  low-water margin) are now read as *adapter-overridable hooks* —
  `_water_rate_ml_per_minute` takes a `rate_override` from
  `water_model_configs[model]["water_rates"]`, and the wash-interval bounds /
  low-water margin read `wash_frequency_bounds` (top-level adapter config) and
  `water_model_configs[model]["low_clean_water_margin_ml"]` respectively — each
  falling back to the prior Eufy value when the key is absent. (The Eufy adapter
  does not yet declare those override keys, so Eufy keeps the built-in defaults and
  behavior is unchanged; the seam is in place for a second brand.) The room-profile
  capability gate (`profiles/room_profiles.py`) now *derives* the mop→vacuum
  downgrade target from the vacuum-only built-in profile (`get_room_profile`)
  instead of hardcoding it.
- **Boundary thresholds de-duplicated to a single source.** The five gap/area/
  cadence thresholds (`gap_delayed_s`, `gap_transit_s`, `gap_plateau_s`,
  `area_jump_m2`, `cadence_s`) now live **only** in the adapter's
  `job_segmenter.tuning` block — live rollover, external-run ingest, *and* learned
  history all read them from the resolved engine tuning. The `live_transition`
  block was trimmed to just its orchestration knobs (`enabled`, `rollover_kinds`,
  `native_transition_source`); the five threshold keys were removed from it (and
  from `_LIVE_TRANSITION_DEFAULTS` in `jobs/active_job.py`). The persisted
  external-run record field `gap_transit_s` (60.0) is unchanged — only its
  provenance moved (module constant → resolved engine tuning). Values and behavior
  are unchanged for Eufy. *(This supersedes the 0.9.16-era note that
  `live_transition` carried the boundary gaps and cadence.)*
- **Adapter-sourced room-profile vocabulary.** Room profiles are now resolved from
  the adapter rather than read straight off the in-code constants. A new adapter
  `room_profiles` block + `resolve_profile_catalog()` (`profiles/room_profiles.py`)
  merges the block over the in-code defaults **per key** (`builtins`,
  `custom_template`, `legacy_aliases`, `default_profile`, the floor-type fan/water
  defaults, `normalize_defaults`); a None/empty block returns the in-code defaults
  verbatim. Every resolver gained an optional `catalog` param. The in-code
  `BUILT_IN_ROOM_PROFILES` stays the framework default and the
  `_PROTECTED_ROOM_PROFILE_NAMES` source (that module-load binding is untouched);
  the Eufy adapter declares the block *by reference* to those constants, so Eufy is
  byte-identical. Wired into the **dispatch** path (`queue/queue_engine.py`
  `build_room_clean_payload`), which resolves the catalog from the adapter and
  threads it into per-room resolution and the capability gate. The global/singleton
  profile editor and the pure room-builder defaults still use the framework default
  catalog (no per-vacuum context); a second brand's editor UI would show framework
  defaults until threaded — a documented follow-up.

### Fixed
- **Graduated external runs no longer falsely flagged "failed sanity checks."**
  The jobs index stored `sanity_passed` as `None`, so the history snapshot's
  `not item.get('sanity_passed', True)` test never hit its default and tagged
  *every* graduated external run as failing the backend sanity checks. The checks
  now use `item.get('sanity_passed') is False` (`learning/manager.py`), and
  graduation sets `sanity_passed=True` / `sanity_flags=[]` explicitly (external
  runs only graduate after passing the tier-1 identity gate, so they're sane by
  construction).
- **External-run room dropdown readability.** The "assign to room" `<select>`
  options now pin a dark background / light text, fixing washed-out unreadable
  options in Windows Chrome.

## [0.9.16] - 2026-06-06

### Fixed
- **Run Profiles panel no longer overlaps the room cards.** On narrow card
  widths the panel positioned itself with a viewport media query that ignored
  the card living in a container narrower than the window, so it overlapped the
  rooms. It now wraps below them via container-relative flex — the two never
  collide at any width.

### Added
- **Theme gallery + submission system.** A public
  [theme gallery](https://kingchddg901.github.io/Vacuum_Agent/) where you can
  browse community themes (each previewed as the real card), download one to load
  via **Upload**, and **submit your own** with a "+ Submit a theme" button. A
  submission flows through an issue form, a bot that validates the export and
  renders an inline preview, and a pull request a maintainer reviews and merges —
  nothing auto-publishes, and the validator reuses the card's own import safety.
  The gallery and bot are repo-hosted, so this doesn't change what HACS installs.

### Docs
- **Theme-sharing documentation pass.** New end-user guide
  (`user-guide/15-sharing-themes`), the full gallery + submission architecture in
  `dev/27-render-harness`, and cross-links from the theme-system, README, and
  testing docs.

## [0.9.15] - 2026-06-06

### Added
- **Colorblind Safe theme.** A new built-in theme with a CVD-validated palette —
  every status-color pair stays distinguishable under protanopia, deuteranopia,
  and tritanopia (CIEDE2000 ΔE ≥ 15). See the new Accessibility guide.
- **Always-on status shape marks.** Mapping-review badges now carry a distinct
  non-color shape per state in addition to color, so status is never conveyed by
  color alone — this applies to *every* theme, not just the colorblind one.

### Fixed
- **Mapping-review badges are now themeable.** They were colored by undefined CSS
  variables, so the hardcoded fallback always won and no theme could recolor
  them. Migrated to the registry `--evcc-sem-*` tokens (with a new
  `--evcc-sem-info`), so themes — including the colorblind palette — now drive the
  badge colors.

## [0.9.14] - 2026-06-05

### Added
- **Two-tier marble veins.** Marble now renders separate **major** and **minor**
  vein layers. A master opacity/blur rides both tiers at once; per-tier offsets
  nudge each tier while preserving the gap between them. The minor tier *recedes*
  — its color is a clamped lighten / desaturate / hue offset from the master
  (OKLCH relative color), so it reads as atmospheric depth rather than a flat
  second color. Per-tier blur is opt-in.
- **Per-floor-type theme export/import.** Move a single floor type's look in
  isolation: **Download Floor** exports just that type's tokens
  (`evcc-floor-{type}-…json`), and uploading a floor-scoped file **replaces only
  that floor's namespace** on your active theme (clear-then-apply, values
  clamped, unknown namespaces skipped) instead of swapping the whole theme.
- **Marble presets.** Carrara, Portoro, and Calacatta starter bundles for the
  two-tier vein system. They apply as a scoped replace on the marble namespace —
  they tune marble in place, they are not separate themes to switch to.

### Changed
- **Single-source token ranges.** Editor sliders and the import clamp now share
  one min/max/step definition per token, so a slider can never show a value its
  own importer would reject.
- **Floor masks regenerated at 2048×2048** (were 512) to match the tiling/shift
  the renderer uses — sharper textures without visible seams.

### Fixed
- **Floor-texture legibility.** Status chips, room controls, and the active-clean
  progress fill stay readable over a filled floor texture across a wide range of
  theme colors (opaque chip backing, halo text-shadow, and explicit z-layer
  pinning so the texture can no longer occlude the progress fill).

### Docs
- **Full documentation accuracy pass** across the developer and advanced guides:
  corrected the adapter-config schema (17 top-level keys; `mapping` is validated
  but is not a schema field), the config-flow and storage shapes, and the
  events/services references — removed three never-implemented "runtime
  management" services and corrected `map_id` to optional (auto-resolves to the
  active map). Testing-doc counts and coverage tables regenerated.

## [0.9.13] - 2026-06-03

### Fixed
- **Integration brand logo.** `logo.png` / `logo@2x.png` were ~2× over Home
  Assistant's brand-image size limit (1024×256 / 2048×512), so the new HA brands
  proxy (which serves the integration's local `brand/` folder by domain) rejected
  them and the logo failed to load. Downscaled to spec (512×128 / 1024×256); the
  icon was already correct.

## [0.9.12] - 2026-06-03

### Fixed
- **Completed the "Vacuum Agent" rename.** The sidebar **panel title** and the
  card's panel text still read "Eufy Vacuum" — a separate string from the product
  name renamed in 0.9.11 (`sidebar_title`, not "Eufy Vacuum Manager"). Both now
  read "Vacuum Agent".

## [0.9.11] - 2026-06-03

### Changed
- **Renamed the product display name to "Vacuum Agent"** (was "Eufy Vacuum
  Manager"); the GitHub repo moved to `Vacuum_Agent`. The Home Assistant
  **domain stays `eufy_vacuum`** — all `eufy_vacuum.*` services, `eufy_vacuum_*`
  events, and `/eufy_vacuum/` paths are unchanged, so existing installs and
  automations keep working. Eufy remains the only supported brand.

## [0.9.10] - 2026-06-03

Mostly a bug-fix release, with significant under-the-hood groundwork for
multi-brand support.

### Fixed
- **Learning stats no longer corrupt on disk.** Learning JSON is written
  atomically (temp file + atomic replace), and a malformed file (e.g. a
  half-written `accuracy_stats.json`) is tolerated and self-heals instead of
  erroring on every startup.
- **No more event-loop stalls.** Synchronous file I/O during setup, dashboard
  refresh, and the job-start snapshot now runs in the executor — resolves the
  "Detected blocking call … inside the event loop" warnings.
- **Mid-job restart recovery fixed.** A crash in the periodic trace-sample flush
  meant a job spanning a Home Assistant restart silently lost its trace (no
  boundary learning); the flush now works.
- **No spurious maintenance warnings at startup.** Maintenance sensors no longer
  log "source entity unavailable" during the normal cross-integration load race;
  they start unavailable and only warn on a genuine availability drop.
- **Dock/maintenance reset buttons resolve correctly** when firmware entity names
  drift (the token-fallback resolution path was unreachable and always returned
  nothing).

### Added
- **Pluggable dispatch engine** with payload shapes for Eufy, Roborock/Ecovacs
  (flat id-list), and Dreame (parallel-array), plus a sequenced job-model
  mechanism wired into start/finalize — groundwork for second-brand adapters.
- **Brand-agnostic adapter conformance test harness.**
- **Developer docs:** Eufy adapter worked-example + CV-segmentor references, and
  a rewritten porting guide for the adapter architecture.
- **`scripts/update_test_docs.py`** — regenerates the testing-doc counts and
  per-module/coverage tables so they don't drift.

### Changed
- **Brand-agnostic core:** charging reads and the last residual Eufy assumptions
  moved out of core into adapter config; duplicate button data de-duplicated.
- **Test coverage to 94.1%** statement (CV segmentor 22% → 70%); CI gate aligned
  with the local behavior gate; checkout@v5 + setup-python@v6.

### Removed
- Dead code: defunct map entry-gating ("System-A"), the vestigial
  `boundary_pixel` field, and an unreachable current-room induction branch in the
  job-progress snapshot.

[0.9.13]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.12...v0.9.13
[0.9.12]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.11...v0.9.12
[0.9.11]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.10...v0.9.11
[0.9.10]: https://github.com/kingchddg901/Vacuum_Agent/compare/v0.9.9.1...v0.9.10
