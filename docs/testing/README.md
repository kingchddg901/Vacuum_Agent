# Testing Docs — Reading Order

How the test suite is built, how to run it, and how to add to it without
rebuilding the scaffolding every time.

The suite currently has **759 test functions** across **47 files** (11 unit,
36 integration, plus the adapter suite), all green, running on Python 3.14
inside a Linux container.

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

## Subsystem test maps

Per-subsystem "what's tested and how" — start from the learning map (the template).

| Doc | What it covers |
|-----|----------------|
| [subsystems/](subsystems/README.md) | Index of per-subsystem test maps |
| [subsystems/learning](subsystems/learning.md) | The learning subsystem — coverage map, behaviors, setup patterns, gaps (**template**) |
| [subsystems/mapping](subsystems/mapping.md) | The mapping subsystem — trace pipeline, image stack, tracker, orchestrators |
| [subsystems/jobs](subsystems/jobs.md) | The jobs subsystem — start-gate evaluation + active-job tracking |

---

## TL;DR

- **Run everything:** `scripts\test.bat` (from a Windows shell; it spins up the container for you).
- **Never run pytest directly on Windows** — `pytest-homeassistant-custom-component` imports `fcntl`, which does not exist on Windows. See [02](02-running-tests.md).
- **New integration test** → use the `manager_with_services` fixture and the seeding helpers in `tests/integration/conftest.py`. Start from a template in [06](06-recipes.md).
- **Managed rooms live at `data["maps"][vac][map]["rooms"]`**, not `data["rooms"]`. This one mistake invalidates more tests than any other — see [05](05-gotchas-and-pitfalls.md).
