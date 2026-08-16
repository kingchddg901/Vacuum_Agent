# Testing Docs — Reading Order

How the test suite is built, how to run it, and how to add to it without
rebuilding the scaffolding every time.

The suite currently has **3,627 test functions** across **200 test files**
(78 unit, 104 integration, 18 adapter) — 4,259 cases after parametrization —
running on Python 3.14 inside a Linux container. The CI behavior gate
(`pytest tests --no-cov`, which also collects the fourth `tests/replay/`
directory below — **3,869 cases** total) is all green. Prefer that number and
that command when you need "is the suite green": running the doc-tool's
narrower `tests/unit tests/integration tests/adapters` path set on its own has
been observed to fail one adapter test
(`tests/adapters/test_brand_selection.py::test_register_brand_adapter_refuses_loudly`,
passes in isolation and under the full `tests` gate — see
[bug signals](#known-test-suite-issues)) via an apparent cross-test state leak,
not a real regression. Those 3,369/3,859 exercise the **217 source modules**
under `custom_components/eufy_vacuum/` to **93.9% coverage** (92% combined
with branch coverage, adapters included); see the
[subsystems index](subsystems/README.md) for the per-subsystem breakdown. A
separate fourth track, the **recorder-replay harness** (`tests/replay/` — real
recorded device runs fired through the production listener layer), is
described in [01 — overview](01-overview.md#the-replay-harness).

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
  tests/adapters` (the path set `scripts/update_test_docs.py` uses) — the
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
  **bug signal** per the disaster-recovery standard §5.2 rather than patched
  here. Consequence: `scripts/update_test_docs.py`'s own coverage run
  (`subprocess.run(..., check=True)`) raises on this path set, so a doc
  regen currently needs `--no-run` against a `coverage.json` produced by a
  manual `pytest tests/unit tests/integration tests/adapters --cov ...`
  (accepting the same one failure) or by widening `TEST_PATHS` to `tests` (not
  done here — out of this doc's scope).

---

## TL;DR

- **Run everything:** `scripts\test.bat` (from a Windows shell; it spins up the container for you). The default run covers `tests/unit` + `tests/integration`; pass `tests` to also gate `tests/adapters` and `tests/replay` the way CI does.
- **Never run pytest directly on Windows** — `pytest-homeassistant-custom-component` imports `fcntl`, which does not exist on Windows. See [02](02-running-tests.md).
- **Frontend / card tests are separate** — pure-JS logic units run with `npm run test:units` ([frontend/unit-tests](frontend/unit-tests.md)); the rendered card + visual baselines run with `npm run test:harness` ([frontend/render-harness](frontend/render-harness.md), Linux-only baselines, pinned Playwright image). Neither is pytest.
- **New integration test** → use the `manager_with_services` fixture and the seeding helpers in `tests/integration/conftest.py`. Start from a template in [06](06-recipes.md).
- **Managed rooms live at `data["maps"][vac][map]["rooms"]`**, not `data["rooms"]`. This one mistake invalidates more tests than any other — see [05](05-gotchas-and-pitfalls.md).
