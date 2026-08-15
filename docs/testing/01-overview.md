# 01 — Overview

## What this suite tests

`eufy_vacuum` is a Home Assistant custom integration built on an **adapter
pattern**: brand-specific entity wiring lives in `adapters/`, and a large
brand-agnostic core (the manager, the job pipeline, learning, mapping,
battery, rooms, themes, setup) sits on top. The test suite targets that core
plus the HA integration seams — config flow, services, platforms, listeners.

The goal is **regression safety for refactors**. The core is being split into
subsystem packages over time (see `docs/dev/`), and the suite exists so those
moves can happen without silently breaking behavior.

## The three layers

`pytest.ini`'s `testpaths` collects only two of these three — `tests/unit`
and `tests/integration`; `tests/adapters` is excluded there and must be
requested explicitly (see below). A fourth, separate harness — **replay** —
lives under `tests/replay/`; it is not one of the three layers pytest
defaults to, and is described in its own section below.

| Layer | Directory | Needs `hass`? | What it covers |
|-------|-----------|---------------|----------------|
| **Unit** | `tests/unit/` | No (mostly) | Pure functions and isolated class methods — timestamp parsing, battery metrics math, learning estimator/finalizer helpers, room-field resolution. Fast, no I/O. |
| **Integration** | `tests/integration/` | Yes | Anything that touches the manager, the HA service registry, platforms, or the persistent store. Uses the in-memory `hass` from `pytest-homeassistant-custom-component`. |
| **Adapter** | `tests/adapters/` | Mostly no | Brand-specific pure logic, now spanning **two brands** — Eufy (model catalog, lifecycle, segmentor, room attribution, error-source classification, upkeep guides) and Roborock (`roborock/test_adapter.py`) — plus the brand-agnostic conformance harness (`test_adapter_contract.py`) and the brand-selection table (`test_brand_selection.py`). Most files are pure logic, but registering a *real* adapter config needs a vacuum entity state: the `adapter` fixture (`tests/adapters/conftest.py`) takes `hass`, so the whole conformance suite plus 5 other files (`test_brand_selection.py`, `roborock/test_adapter.py`, `eufy/test_lifecycle.py`, `eufy/test_maintenance_config.py`, `eufy/test_job_segmenter_config.py`) do too. Kept on its own path; counted in the coverage number — we always test the adapters we ship. |

Rule of thumb: **if the thing under test is a pure function, write a unit
test** — it is faster, has no shared-state pitfalls, and reads more clearly.
Reach for an integration test only when you need the manager, a real service
call, or the store.

## Directory layout

```
tests/
  conftest.py                 # root fixtures: hass enablement, config entries
  _factories.py                # shared setup factories (VAC/MAP, spec_manager, ...)
  __init__.py
  fixtures/                   # committed data captures, loaded by path
    battery/  external_run/  learning/  replays/
  unit/                       # pure-function tests
    test_timestamp_utils.py
    test_battery_metrics.py
    test_learning_estimator.py
    test_learning_job_finalizer.py
    ...
  integration/
    conftest.py               # manager + manager_with_services + seeding helpers
    test_config_flow.py
    test_manager_setup.py
    test_services_rooms.py
    test_learning_services.py
    test_button_entity.py
    test_listeners_*.py
    test_setup_*.py
    test_themes_*.py
    ...
  adapters/
    conftest.py               # adapter-suite fixtures (ADAPTER_BUILDERS registry)
    test_adapter_contract.py  # brand-agnostic conformance harness
    test_brand_selection.py   # adapters/brands.py — which registrar runs per vacuum
    eufy/                     # concrete-adapter tests (counted in coverage %)
      test_model_catalog.py
      test_lifecycle.py
      test_buttons_entities.py
      test_segmentor.py
      test_segmentor_splitters.py
      test_job_segmenter_config.py
      test_room_attribution.py
      test_error_source.py
      test_maintenance_config.py
      test_upkeep_guides_i18n.py
    roborock/                 # second concrete adapter (S6-class)
      test_adapter.py
  replay/                     # recorder-replay harness — a separate track, see below
    bundle.py  harness.py     # bundle extract/load + the replay driver
    harvest.py  refocus.py    # corpus tooling (CLI, local-only output)
    reclassify.py  reverdict.py
    test_replay_smoke.py      # end-to-end: a real recorded run drives external capture
    test_harvest_units.py     # harvester unit handling (ft^2 / m^2 conversion)
    test_refocus.py           # lens sufficiency guards
```

(`eufy/test_discovery.py` is gone — model detection is no longer a separate
`discovery.py` module; see [15 — adapters](subsystems/15-adapters.md).)

## Toolchain

Declared in `requirements_test.txt`:

| Package | Why |
|---------|-----|
| `pytest>=9.0` | runner |
| `pytest-asyncio>=1.3` | async tests; `asyncio_mode = auto` means `async def test_*` just works, no decorator |
| `pytest-cov` | coverage + branch coverage |
| `pytest-homeassistant-custom-component>=0.13.332` | the in-memory HA harness — provides the `hass` and `enable_custom_integrations` fixtures |

Config lives in two files:

- **`pytest.ini`** — `asyncio_mode = auto`, `testpaths = tests/unit tests/integration`, and the coverage `addopts` (term-missing + branch). A default run does **not** write HTML; the canonical `htmlcov/` is produced only by an explicit `--cov-report=html:htmlcov`.
- **`.coveragerc`** — coverage `source` is `custom_components/eufy_vacuum` (no `omit` — the eufy adapter is counted too); `exclude_lines` drops `TYPE_CHECKING`, `__repr__`, `NotImplementedError`, `pragma: no cover`, bare `...` stub bodies (`^\s*\.\.\.\s*$`), and `@overload`-decorated signatures (`@(typing\.)?overload`).

Note that `testpaths` deliberately **excludes** `tests/adapters` and
`tests/replay` — run those paths explicitly when you want them (see
[02](02-running-tests.md)). CI's behavior gate passes `tests` explicitly
(`.github/workflows/tests.yml`), which walks the whole `tests/` tree, so both
excluded paths are still gated on every push.

## The replay harness

`tests/replay/` is a **separate track from the three layers above** — not a
fourth pytest layer, a different kind of test input. Where a unit/integration/
adapter test's stimulus is a fixture someone wrote to match their expectation,
replay's stimulus is a **recorder-save bundle**: the last-known state of every
upstream entity before a real run's window opens (`"initial"`) plus the
ordered in-window state changes (`"events"`), extracted from a recorder CSV
export (`tests/replay/bundle.py`).

The driver (`tests/replay/harness.py`) fires each event through
`hass.states.async_set` — the same public seam the production listeners
subscribe to via `async_track_state_change_event` — with a `freezer` jump +
`async_fire_time_changed` before each event, so time-scheduled callbacks
(pollers, reapers, debounces) fire exactly as wall-clock would have allowed.
Production code runs unmodified; the only fakery is the clock.

Rules the harness enforces by construction:

- **Replay is stimulus-only.** A recorder export also captures this
  integration's *own* output entities; those are `skip`ped (ask the entity
  registry after setup) so the system re-derives its outputs instead of being
  fed its recorded conclusions.
- **`supplement` states are explicit assumptions** — static context the
  states-only CSV export could not carry (entities that never changed in the
  window), passed per-test rather than hidden in a fixture.
- **Deterministic, not race evidence.** Sequences and gaps replay;
  await-interleavings do not.

`test_replay_smoke.py` (`RPL-1`) is the proof-of-life: a real recorded
phased-run window (2026-08-03, Kitchen phase → wait → group dispatch → dock)
replayed through a full-boot setup, asserting the lifecycle listener notices
the run as an external capture mid-replay (an active-job slot opens), buffers
real counter evidence from the recorded stream, and settles docked with no
stranded slot. Committed bundles live in `tests/fixtures/replays/`.

The other modules under `tests/replay/` are **corpus tooling**, not tests: CLI
scripts that harvest every retained run out of the live recorder DB
(`harvest.py`), cut focused recordings from that harvest (`refocus.py`), and
re-judge harvested runs with current code (`reverdict.py` for job records,
`reclassify.py` for tapes). Their output is one household's real device
telemetry. `harvest.py` and `refocus.py` require `--out` explicitly (no
argparse default) but both scripts' own docstrings model/recommend pointing it
at the git-ignored `.claude/notes/` tree, with an explicit warning against a
tracked destination; `reverdict.py` and `reclassify.py` take no `--out` at all
and only print findings to stdout. Each module's docstring is its manual.

## Coverage status

**Coverage: 93.9% statement** (92% combined with `--cov-branch`, which the
default `addopts` enables), across the brand-agnostic core **and** the shipped
brand adapters (Eufy + Roborock) — the adapters are counted in the number (see
[subsystems/15-adapters](subsystems/15-adapters.md)). Most subsystems sit in the
90–98% band; the most visible thin spots are the CV `segmentor` (91%) and
`rooms/reconciliation.py` (78%, see [04 — rooms](subsystems/04-rooms.md#known-gaps)).
The per-subsystem breakdown lives in
[subsystems/README](subsystems/README.md).

Coverage is a guide, not a target — the suite favors **precision** (each test
maps to a named behavior, see [04](04-patterns-and-conventions.md)) over chasing
the last few percent. The remaining misses are, by design, one of:

- **`# pragma: no cover`** — pure log-only / best-effort `except` blocks (I/O
  writes, listener teardown). Never used where the failure path escapes into a
  returned/persisted/user-visible value.
- **Honest misses** (not tested, not pragma'd) — defensive `continue` /
  `return []` guards (real control flow) and `async_setup_entry` boot wiring that
  only runs under a full integration boot.

See [subsystems/README](subsystems/README.md#coverage-conventions-apply-everywhere)
for the full convention. 95% is not pursued: reaching it on this codebase would
mean either pragma-bombing real control flow or writing tests that exist only to
move a number.
