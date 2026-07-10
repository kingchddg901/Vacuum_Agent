# Testing Docs — Reading Order

How the test suite is built, how to run it, and how to add to it without
rebuilding the scaffolding every time.

The suite currently has **2,629 test functions** across **154 test files**
(50 unit, 92 integration, 12 adapter) — 2,925 cases after parametrization — all
green, running on Python 3.14 inside a Linux container. Those exercise the
**161 source modules** under
`custom_components/eufy_vacuum/` to **95.6% coverage** (94% combined with
branch coverage, adapters included); see the [subsystems index](subsystems/README.md) for the
per-subsystem breakdown.

---

## Start here

| # | File | What it covers |
|---|------|----------------|
| 01 | [overview](01-overview.md) | Test philosophy, the three layers (unit / integration / adapter), directory layout, coverage status |
| 02 | [running-tests](02-running-tests.md) | `scripts\test.bat`, why tests must run in Docker, running subsets, reading coverage |

## Reference

| # | File | What it covers |
|---|------|----------------|
| 03 | [fixtures-and-helpers](03-fixtures-and-helpers.md) | Every fixture (`hass`, `manager`, `manager_with_services`, config entries) and the seeding helpers |
| 04 | [patterns-and-conventions](04-patterns-and-conventions.md) | Coverage-target IDs, file/test naming, calling services, sync-via-executor, the unit-mock pattern |
| 05 | [gotchas-and-pitfalls](05-gotchas-and-pitfalls.md) | The traps that cost the most time: shared `config_dir`, the real data layout, learning blockers, adapter registry wiring |

## Do the thing

| # | File | What it covers |
|---|------|----------------|
| 06 | [recipes](06-recipes.md) | Copy-paste templates: a service test, an entity test, a unit test, a finalize test, an adapter-config test |

## Frontend (JS) — its own set

The card is a separate JS track (not part of the Python count above), documented
as its own set under **[frontend/](frontend/unit-tests.md)**:

- **[frontend/unit-tests](frontend/unit-tests.md)** — the pure-JS logic units:
  **505 cases across 36 `src/**/*.test.mjs` files** (coordinate math, validation
  engines, state accessors, theme/colour resolution); `npm run test:units`.
- **[frontend/render-harness](frontend/render-harness.md)** — the headless
  render-harness gates (smoke, visual regression, CVD, shape marks, intake) and
  the Docker baseline workflow; `npm run test:harness`.

## Subsystem test maps

Per-subsystem "what's tested and how" — start from the learning map (the template).

**All 18 subsystems are mapped** (core + every package + the HA-facing layers),
numbered by the start pipeline then peripherals — see the
[subsystems index](subsystems/README.md) for the full table and per-subsystem
coverage. Highlights:

| Doc | What it covers |
|-----|----------------|
| [subsystems/](subsystems/README.md) | Index of all per-subsystem test maps + coverage conventions |
| [subsystems/01-core](subsystems/01-core.md) | The orchestrator — lifecycle, job progress, start-status, delegation seams, errors, storage |
| [subsystems/06-learning](subsystems/06-learning.md) | The learning subsystem — coverage map, behaviors, setup patterns, gaps (**detailed template**) |
| [subsystems/10-dock](subsystems/10-dock.md) | The dock subsystem — action gating, dispatch, event recording (**compact template**) |

---

## TL;DR

- **Run everything:** `scripts\test.bat` (from a Windows shell; it spins up the container for you).
- **Never run pytest directly on Windows** — `pytest-homeassistant-custom-component` imports `fcntl`, which does not exist on Windows. See [02](02-running-tests.md).
- **Frontend / card tests are separate** — pure-JS logic units run with `npm run test:units` ([frontend/unit-tests](frontend/unit-tests.md)); the rendered card + visual baselines run with `npm run test:harness` ([frontend/render-harness](frontend/render-harness.md), Linux-only baselines, pinned Playwright image). Neither is pytest.
- **New integration test** → use the `manager_with_services` fixture and the seeding helpers in `tests/integration/conftest.py`. Start from a template in [06](06-recipes.md).
- **Managed rooms live at `data["maps"][vac][map]["rooms"]`**, not `data["rooms"]`. This one mistake invalidates more tests than any other — see [05](05-gotchas-and-pitfalls.md).
