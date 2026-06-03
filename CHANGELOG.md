# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow semantic-ish versioning.

Releases before 0.9.10 are recorded as
[GitHub tags/releases](https://github.com/kingchddg901/eufy-vacuum-manager/releases)
only.

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

[0.9.10]: https://github.com/kingchddg901/eufy-vacuum-manager/compare/v0.9.9.1...v0.9.10
