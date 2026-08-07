# Subsystem Test Maps

Per-subsystem "what's tested and how" docs. Each maps a subsystem's source
modules to their test files, lists the behaviors under test, explains the setup
patterns specific to that subsystem, and records the deliberate gaps. Numbered
roughly by the start pipeline (core → queue → rooms → planning → learning →
mapping) then peripheral subsystems and the HA-facing layers.

| # | Subsystem | Map | Cov |
|---|-----------|-----|----:|
| 01 | Core (orchestrator, lifecycle, progress, errors, storage) | [01-core](01-core.md) | 93% |
| 02 | Jobs (start gate + active-job tracker) | [02-jobs](02-jobs.md) | 92% |
| 03 | Queue (ordered clean queue) | [03-queue](03-queue.md) | 95% |
| 04 | Rooms (discovery, CRUD, access graph) | [04-rooms](04-rooms.md) | 91% |
| 05 | Planning (rule eval, fan-out, path-block) | [05-planning](05-planning.md) | 93% |
| 06 | Learning (estimator, finalizer, history) | [06-learning](06-learning.md) | 93% |
| 07 | Mapping (trace pipeline, image stack, tracker) | [07-mapping](07-mapping.md) | 90% |
| 08 | Battery (wear/health, sensors, sessions) | [08-battery](08-battery.md) | 94% |
| 09 | Maintenance (wear tracking, care guides) | [09-maintenance](09-maintenance.md) | 91% |
| 10 | Dock (action gating + dispatch) | [10-dock](10-dock.md) | 98% |
| 11 | Setup (workflow, drift, delete, entry wiring) | [11-setup](11-setup.md) | 89% |
| 12 | Profiles (per-room cleaning profiles) | [12-profiles](12-profiles.md) | 96% |
| 13 | Onboarding (discovery + floor-type state) | [13-onboarding](13-onboarding.md) | 98% |
| 14 | Themes (card theme library) | [14-themes](14-themes.md) | 95% |
| 15 | Adapters (brand abstraction boundary) | [15-adapters](15-adapters.md) | 93%¹ |
| 16 | Listeners (HA event → manager wiring) | [16-listeners](16-listeners.md) | 94% |
| 17 | Services (HA service-call layer) | [17-services](17-services.md) | 93% |
| 18 | Platforms & entities (sensor/button/number/switch/…) | [18-platforms](18-platforms.md) | 95% |

¹ Includes both shipped brand adapters (`adapters/eufy/*` and
`adapters/roborock/*`), counted in the number. The framework adapter code
(registry/loader/schema/brands) sits in the low-90s to 100%, and the Roborock
adapter is ~96-100% across the board; the subsystem figure is pulled down
almost entirely by the CV `segmentor` (91%, 866 stmts) — see
[15-adapters](15-adapters.md).

The per-subsystem Cov column is **combined** (statement + branch) coverage —
the single number `pytest --cov-branch` prints per row — computed over exactly
the modules each subsystem's table lists. Package `__init__.py` files (boot /
re-export wiring) are deliberately not tabled, so they sit in the grand total
but not the per-subsystem figures. The grand total below breaks out the
statement-only figure too.

**Total: 94.4% statement coverage** (93% combined with `--cov-branch`, adapters
included) over the source modules, all tests green. These numbers and the
per-module tables are refreshed by `scripts/update_test_docs.py`.

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
