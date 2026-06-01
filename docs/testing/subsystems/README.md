# Subsystem Test Maps

Per-subsystem "what's tested and how" docs. Each maps a subsystem's source
modules to their test files, lists the behaviors under test, explains the setup
patterns specific to that subsystem, and records the deliberate gaps. Numbered
roughly by the start pipeline (core → queue → rooms → planning → learning →
mapping) then peripheral subsystems and the HA-facing layers.

| # | Subsystem | Map | Cov |
|---|-----------|-----|----:|
| 01 | Core (orchestrator, lifecycle, progress, errors, storage) | [01-core](01-core.md) | 92% |
| 02 | Jobs (start gate + active-job tracker) | [02-jobs](02-jobs.md) | 95% |
| 03 | Queue (ordered clean queue) | [03-queue](03-queue.md) | 93% |
| 04 | Rooms (discovery, CRUD, access graph) | [04-rooms](04-rooms.md) | 96% |
| 05 | Planning (rule eval, fan-out, path-block) | [05-planning](05-planning.md) | 93% |
| 06 | Learning (estimator, finalizer, history) | [06-learning](06-learning.md) | 95% |
| 07 | Mapping (trace pipeline, image stack, tracker) | [07-mapping](07-mapping.md) | 93% |
| 08 | Battery (wear/health, sensors, sessions) | [08-battery](08-battery.md) | 94% |
| 09 | Maintenance (wear tracking, care guides) | [09-maintenance](09-maintenance.md) | 90% |
| 10 | Dock (action gating + dispatch) | [10-dock](10-dock.md) | 98% |
| 11 | Setup (workflow, drift, delete, entry wiring) | [11-setup](11-setup.md) | 93% |
| 12 | Profiles (per-room cleaning profiles) | [12-profiles](12-profiles.md) | 93% |
| 13 | Onboarding (discovery + floor-type state) | [13-onboarding](13-onboarding.md) | 97% |
| 14 | Themes (card theme library) | [14-themes](14-themes.md) | 98% |
| 15 | Adapters (brand abstraction boundary) | [15-adapters](15-adapters.md) | 97%¹ |
| 16 | Listeners (HA event → manager wiring) | [16-listeners](16-listeners.md) | 90% |
| 17 | Services (HA service-call layer) | [17-services](17-services.md) | 94% |
| 18 | Platforms & entities (sensor/button/number/switch/…) | [18-platforms](18-platforms.md) | 94% |

¹ Framework adapter code only. The concrete Eufy adapter (`adapters/eufy/*`) is
**omitted** from the coverage number by `.coveragerc` and tested separately —
see [15-adapters](15-adapters.md).

**Framework total: 93.6% statement coverage** (90.8% with `--cov-branch`) over
the 131 source modules, driven by 1,448 test functions across 100 test files,
all green.

## Writing / updating a test map

Each map keeps five sections (see [10-dock](10-dock.md) as the compact template,
[06-learning](06-learning.md) as the detailed one):

1. **Coverage map** — table of source module → stmts → cov% → test file → layer.
2. **What's tested** — per module, the behaviors (reference target-ID ranges).
3. **How it's tested** — the setup patterns (which fixtures, `tmp_path` vs
   integration `hass`, seeding helpers).
4. **Known gaps** — what's deliberately untested and why.

Measure a subsystem's coverage by running **all** its test files together (see
[../02-running-tests.md](../02-running-tests.md#per-file-vs-combined-coverage)),
and link the matching `docs/dev/` architecture file at the top.

## Coverage conventions (apply everywhere)

- **`# pragma: no cover`** is used only on **pure log-only / best-effort** except
  blocks (I/O writes, listener teardown) — never on a block that escapes into a
  returned/persisted/user-visible value.
- **Deliberately measured** (not pragma'd, even though they only log): fan-out
  skip-one-continue resilience and degraded-return excepts — these are behavior.
- **Honest misses** (not tested, not pragma'd): defensive `continue` /
  `return []` guards (real control flow) and `async_setup_entry` boot wiring.
