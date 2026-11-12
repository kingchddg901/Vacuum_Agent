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

`pytest.ini`'s `testpaths` collects all three layers — `tests/unit`,
`tests/integration` and `tests/adapters` — plus `tests/core`. A fourth, separate
harness — **replay** — lives under `tests/replay/`; it is not one of the layers
pytest defaults to, and is described in its own section below.

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
    test_reverdict.py         # the re-judge harness derives verdicts, never restates them
    test_harness_replicas.py  # the harnesses' three registered replica sets must agree
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

- **`pytest.ini`** — `asyncio_mode = auto`, `testpaths = tests/unit tests/integration tests/core tests/adapters`, and the coverage `addopts` (term-missing + branch). A default run does **not** write HTML; the canonical `htmlcov/` is produced only by an explicit `--cov-report=html:htmlcov`.
- **`.coveragerc`** — coverage `source` is `custom_components/eufy_vacuum` (no `omit` — the eufy adapter is counted too); `exclude_lines` drops `TYPE_CHECKING`, `__repr__`, `NotImplementedError`, `pragma: no cover`, bare `...` stub bodies (`^\s*\.\.\.\s*$`), and `@overload`-decorated signatures (`@(typing\.)?overload`).

Note that `testpaths` deliberately **excludes** `tests/replay` — run it
explicitly when you want it (see [02](02-running-tests.md)). CI's behavior gate
passes `tests` explicitly (`.github/workflows/tests.yml`), which walks the whole
`tests/` tree, so the excluded path is still gated on every push.

⚠ **`tests/adapters` JOINED the default on 2026-11-11**, by Chris's call: the brand
adapters we ship are not an optional extra to test, and a default run that skipped
them meant the inner loop disagreed with the gate about what "the tests" are. A bare
`pytest` went from 5,386 to 5,990 collected. `tests/core` was added days earlier for
a different reason — it was never a decision at all, just a directory that postdated
the `testpaths` line, and its absence published two 100% modules as the worst in the
package (see [Coverage status](#coverage-status)).

> **`tests/core` was a THIRD exclusion that nobody decided.** It is not named
> above because it was never a choice: the directory postdates the `testpaths`
> line and holds the only tests for
> `core/maintenance_component_rename_migration.py` and
> `core/usage_accumulator.py`. Being outside `testpaths` it was also outside
> `scripts/update_test_docs.py`'s scope, so both modules published as the
> package's worst files while sitting at 100% (see
> [Coverage status](#coverage-status)). Added 2026-11-11 — 2 files, 40 tests,
> no measurable cost to the inner loop. The adapters and replay exclusions are
> unchanged, because those ARE decisions and CI still gates them.

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

One of those modules is gated, and the gate is about trust rather than coverage.
`test_reverdict.py` (`RPL-2`–`RPL-5`) holds `reverdict.py` to the rule its own
docstring states: a harness whose purpose is to report what the *current* build
concludes must import the shipped functions, never restate them. It restated one
— the attribution-shift threshold was written out as `run >= 2`, a hand copy of
`learning/external_ingest.py::_SHIFT_BLOCK_MIN_RUN`
— so the report printed "records the NEW rule blocks" while answering for a rule
of its own. `RPL-3` *moves* the shipped constant and asserts the report moves with
it; a test asserting "a run of 2 blocks" would merely have been a third copy of
the number.

**Why no existing gate could catch it — and what changed the same day.** The `RN`
replica register ([00c](../dev/00c-replicas.md)) only records a set whose every
member can be anchored at its own site, and `doc_anchor.py`'s declaration scan read
`custom_components`, `scripts`, `src` and `harness` but **not** `tests` — which was
in `REF_ROOTS` only. So a copy living in a test could be *cited* and never
*declared*: an `# anchor:` there was inert, and the checker called the token
"defined nowhere" the moment a document cited it. The register therefore could not
describe this pair at all, and coverage saw a line that ran.

`tests/` is a declaration root as of 2026-11-07, pinned by `ANC-5` in
`tests/unit/test_generated_doc_gate.py`: one test proves a `tests/` declaration
satisfies a citation of it, one proves the gate's own fixture strings stay data (it
writes `# anchor:` markers into throwaway files, which would otherwise have become
five declarations of one token), and one proves a *real* duplicate inside `tests/`
still fires, so the exclusion cannot quietly become a blindfold. The precedent was
already there on the frontend side: `harness/tests/i18n-rtl.spec.mjs` carries
`REPLICA RNF6XB1P` and has always resolved, because `harness/` is a source root.

**Two of these harnesses cannot follow the import-don't-restate rule at all**, and
`test_harness_replicas.py` (`RPL-6`–`RPL-8`) is what holds them to agreement
instead. `harvest.py` is deliberately stdlib-only — it opens a recorder SQLite
file, and importing the shipped converters pulls the whole Home Assistant
dependency tree in (measured: with `homeassistant` blocked, `learning/utils.py`,
`learning/job_finalizer.py` and `counter_segmentation.py` all die on
`voluptuous`), so its two unit tables are a replica set rather than a defect
waiting for a helper. `reclassify.py` does import shipped code, but a payload
SHAPE is not importable, so it reconstructs the counter sample by hand. All three
are registered in [00c](../dev/00c-replicas.md) as `RN0RGR1H`, `RN2ZQ5NG` and
`RNBTKYXY` — the first replica sets whose second member lives under `tests/`,
which is what the declaration-root change above made recordable. Each test
derives the shipped side mechanically (object identity, the function's own AST,
the producer's own dict literal) rather than retyping it, because a retyped
vocabulary would be a third copy that passes whenever it matches its author's
belief.

## Coverage status

**Coverage: 97.8% statement** (97% combined with `--cov-branch`, which the
default `addopts` enables), across the brand-agnostic core **and** the shipped
brand adapters (Eufy + Roborock) — the adapters are counted in the number (see
[subsystems/15-adapters](subsystems/15-adapters.md)).

**Nothing in the package sits below 95%.** Of the 141 modules carrying at least 30
units, zero are under the bar on combined coverage; the floor is
`sensor/__init__.py` at exactly **95.00%**.

> **A PARTIAL SCOPE DOES NOT READ AS PARTIAL — IT READS AS A GAP IN THE CODE.**
> This section has been wrong twice in one day, in the same way, and the second time
> was the instructive one.
>
> It first listed FOUR modules under 95%, naming
> `core/maintenance_component_rename_migration.py` at **79.65%** as "the one real
> outlier" with `core/usage_accumulator.py` at 91.67% behind it. Both are at
> **100%**. Their only tests live in `tests/core/`, which was in neither
> `pytest.ini`'s `testpaths` nor the generator's scope, so the package was measured
> with those two modules' tests switched off and the result published as their
> coverage. That one was at least loud: the excluded directory held EXACTLY the tests
> for the two files that then appeared worst, and the migration's uncovered lines were
> its most load-bearing branch — the "THE DESTINATION WINS" rule that stops a rename
> overwriting a user's newer setting. Covered the whole time, by `[MCR-3]`/`[MSK-2]`.
>
> It then listed TWO, `core/error_tracker.py` at 94.56% and `battery/manager.py` at
> 94.94%. Both are also above the bar — **95.52%** and **95.21%**. Adding `tests/core`
> had closed one layer of the gap and left `tests/replay` and the root ratchet files
> out, which cost `error_tracker.py` three statements and three branches: enough to
> invent a module below a bar it had never been below. The justification for leaving
> them out was that the residual was 0.02 pp — true of the PACKAGE TOTAL and
> irrelevant per file. **An aggregate that barely moves can still hide a module
> crossing the bar**, and that is the version of this mistake worth remembering,
> because the first was visible and this one was not.
>
> Fixed by separating what gets MEASURED from what gets LABELLED:
> `scripts/update_test_docs.py` now measures `MEASURE_PATHS = ["tests"]`, the scope
> CI's gate actually runs, and keeps `LAYER_PATHS` only for the per-layer counts.
> A figure in these docs should be reproducible by the documented command.

> **This section also once named the CV `segmentor` (91%) and
> `rooms/reconciliation.py` (78%) as the visible thin spots. Both had cleared.**
> The segmentor is at 95.43% ([15-adapters](subsystems/15-adapters.md)) and
> reconciliation.py was two revisions stale. A named thin spot rots quietly, because
> fixing the file never touches the sentence that names it.

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
for the full convention. **95% overall is still not pursued**: reaching it across
the whole package would mean either pragma-bombing real control flow or writing
tests that exist only to move a number.

> **NARROWED 2026-11-11, by events rather than by error.** This read "95% is not
> pursued" unqualified, and PER FILE that is no longer true: the last module under
> the bar, `adapters/eufy/segmentor.py`, went 92.38% to 95.43% with **no new
> pragmas**, 15 of 15 ablations reddening their test, and the two arms that could
> not be proven recorded as unproven rather than faked
> ([15-adapters](subsystems/15-adapters.md)).
>
> The original was CORRECT FOR THE CODEBASE IT DESCRIBED, which is why it is
> narrowed and not deleted. Measured over the 2389 commits since it was written
> (2026-06-01): shipped python grew 131 files / 44,945 lines to 205 / 105,013, while
> the suite grew 107 files / 22,817 lines to 273 / 130,587 -- a test-to-source line
> ratio of **0.51:1 to 1.24:1**. The code added since arrived far more densely
> tested than the code this sentence was written about, so the aggregate rose and
> the per-file bar became reachable on the newer material without the hard old code
> moving. A claim about what a codebase permits has a subject, and the subject
> changed.
