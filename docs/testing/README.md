# Testing Docs — Reading Order

How the test suite is built, how to run it, and how to add to it without
rebuilding the scaffolding every time.

The suite's four layers hold **4,975 test functions** across **243 test files**
(99 unit, 115 integration, 27 adapter, 2 core), running on Python 3.14 inside a
Linux container.

**The CI behaviour gate is `pytest tests --no-cov`, and it is all green.** Prefer
that command when you need "is the suite green". Its scope is the whole `tests/`
tree, which is wider than those four layers — it also collects the
**recorder-replay harness** (`tests/replay/`, 28 cases: real recorded device runs
fired through the production listener layer, described in
[01 — overview](01-overview.md#the-replay-harness)) and the seven ratchet files
that sit directly under `tests/` (93 cases, the larger of the two additions — the
annotation, covers, docs, mock, pragma, replica and vocabulary gates). The gate
collects 6,206 cases after parametrization. `pytest.ini`'s default `testpaths`
names the four layers and no loose files, so the inner loop collects 6,081 of
those cases and cannot see the ratchets at all (6,081 + 28 + 93; measured
2026-11-11).

The gate's scope is also what the coverage figures are measured at, and what
`scripts/update_test_docs.py` regenerates them from. They exercise the
**206 source modules** under `custom_components/eufy_vacuum/` to
**97.8% coverage** (97% combined with branch coverage, adapters included); see
the [subsystems index](subsystems/README.md) for the per-subsystem breakdown.

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
  **904 cases across 91 `src/**/*.test.mjs` files** (coordinate math, validation
  engines, state accessors, theme/colour resolution, and the audit campaign's
  regression files); `npm run test:units`.
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

## Known test-suite issues

- **`tests/adapters/test_brand_selection.py::test_register_brand_adapter_refuses_loudly`**
  can fail with `AssertionError: assert 'not identified as any supported brand'
  in ''` when the suite is run as exactly `tests/unit tests/integration
  tests/adapters` (the path set `scripts/update_test_docs.py` used until
  2026-11-11) — the
  `caplog` fixture sees no records even though the code under test does log.
  It passes standalone and under the CI gate (`pytest tests`, which also
  collects `tests/replay`). Reproduced twice, with and without `--cov`. This
  reads as a cross-test **logger-state leak**: `debug_capture.py`'s
  `DebugCapture.start()`/`.stop()` save/restore the
  `custom_components.eufy_vacuum` package logger's `propagate` flag
  (`tests/unit/test_debug_capture.py`), and that is the only other place in
  the suite that mutates it — a run ordering where a capture is left active
  (or restored to the wrong prior value) would silently swallow this test's
  `caplog` records. Not confirmed as the exact mechanism; flagged as a
  **bug signal** per [00 §3](../dev/00-documentation-standard.md) rather than patched
  here. Consequence, since 2026-11-11: none for a doc regen.
  `scripts/update_test_docs.py` measures `MEASURE_PATHS = ["tests"]` — the gate's
  scope — so its own coverage run no longer uses that three-directory path set and
  no longer meets this failure. Do not narrow it back to reproduce the old
  command: that scope is what published `core/error_tracker.py` below the 95% bar
  when `pytest tests` puts it above it.

---

## TL;DR

- **Run everything:** `scripts\test.bat` (from a Windows shell; it spins up the container for you). The default run covers `tests/unit`, `tests/integration`, `tests/core` and `tests/adapters`; pass `tests` to also gate `tests/replay` and the top-level ratchet files the way CI does.
- **Never run pytest directly on Windows** — `pytest-homeassistant-custom-component` imports `fcntl`, which does not exist on Windows. See [02](02-running-tests.md).
- **Frontend / card tests are separate** — pure-JS logic units run with `npm run test:units` ([frontend/unit-tests](frontend/unit-tests.md)); the rendered card + visual baselines run with `npm run test:harness` ([frontend/render-harness](frontend/render-harness.md), Linux-only baselines, pinned Playwright image). Neither is pytest.
- **New integration test** → use the `manager_with_services` fixture and the seeding helpers in `tests/integration/conftest.py`. Start from a template in [06](06-recipes.md).
- **Managed rooms live at `data["maps"][vac][map]["rooms"]`**, not `data["rooms"]`. This one mistake invalidates more tests than any other — see [05](05-gotchas-and-pitfalls.md).
