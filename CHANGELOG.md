# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow semantic-ish versioning.

Releases before 0.9.10 are recorded as
[GitHub tags/releases](https://github.com/kingchddg901/Vacuum_Agent/releases)
only.

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
