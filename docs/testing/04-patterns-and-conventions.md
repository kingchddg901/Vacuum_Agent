# 04 — Patterns and Conventions

Follow these so new tests read like the existing ones and stay easy to map back
to behavior.

## Coverage-target IDs

Every test file opens with a docstring that enumerates **coverage targets** —
short IDs, each naming one behavior, each owned by one test. The prefix is a
mnemonic for the file.

```python
"""Phase 4 integration tests — rooms service handlers.

Coverage targets
----------------
[SR-1]  save_managed_rooms service persists room config.
[SR-2]  get_vacuum_maps service returns map list for a vacuum.
[SR-3]  update_room_fields service updates a field and returns ok.
[SR-4]  update_room_fields service returns error for unknown room.
"""
```

Each test then references its target in its own docstring:

```python
async def test_save_managed_rooms_service_persists_rooms(hass, manager_with_services):
    """[SR-1] save_managed_rooms service writes rooms into manager data."""
```

Why it matters: the target list is the file's table of contents and its
contract. When you add a behavior, add a target ID and a test for it. When a
test fails, the ID tells you which behavior broke without reading the body.

Established prefixes include `LS` (learning services), `SR` (services-rooms),
`BE` (button entity), and so on — one per file. Pick a short prefix for a new
file, ideally one not already used elsewhere.

**IDs are file-scoped, not global.** `check_legend_drift.py` validates each
file's legend against *its own* tests only — it does **not** enforce global
uniqueness, and genuine cross-file references are handled inline (prose) plus the
checker's `CROSSREF_ALLOWLIST`. So a `[SP-1]` in one file is a different behavior
than a `[SP-1]` in another; resolve an ID by the file it lives in. Reusing a
prefix across **unrelated** files is tolerated but discouraged — it muddies a
global grep, so prefer a fresh prefix. A prefix deliberately **shared** by a set
of files covering one cross-file suite (e.g. `LC` for lifecycle across the
listener + sensor-status tests) is fine and intentional.

## Naming

| Thing | Convention | Example |
|-------|------------|---------|
| Test file | `test_<area>.py`, grouped by subsystem or platform | `test_services_queue.py`, `test_listeners_timers.py` |
| Test function | `test_<subject>_<expected>` | `test_get_vacuum_maps_service_returns_dict` |
| Module constants | `_VAC`, `_MAP` at top of file | `_VAC = "vacuum.alfred"` |
| Private helpers | leading underscore, module scope | `_seed_active_job`, `_make_manager` |

`vacuum.alfred` is the standard test vacuum across the suite. Reuse it.

## Calling a service

```python
result = await hass.services.async_call(
    DOMAIN,
    "service_name",
    {"vacuum_entity_id": _VAC, "map_id": _MAP},
    blocking=True,
    return_response=True,   # only for services that return data
)
```

- `blocking=True` — wait for completion before asserting.
- `return_response=True` — required for services that return a payload (the
  read/snapshot services). Omit it for fire-and-forget services, which return
  `None`.

After a service that schedules background work, drain the loop before
asserting:

```python
await hass.async_block_till_done()
```

## Sync manager methods: run them in the executor

Many manager methods are **synchronous** and do blocking file I/O through the
store (`finalize_completed_job`, the rebuilders, snapshot writes). HA forbids
blocking the event loop, so call them through the executor:

```python
result = await hass.async_add_executor_job(
    lambda: learning.finalize_completed_job(
        manager=core_manager,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        battery_start=85, battery_end=60,
        started_at="2026-01-01T09:00:00+00:00",
        ended_at="2026-01-01T09:30:00+00:00",
        used_for_learning=False,
        rebuild_stats=False,
    )
)
```

The async wrappers (e.g. `async_finalize_completed_job`) do this internally —
prefer them when one exists. Drop to the sync method + executor only when you
are specifically testing the sync path.

## Unit tests: mock the manager

Entity and platform unit tests do not need a real manager — they need an object
that records calls. Build a `MagicMock`, with `AsyncMock` for the async methods:

```python
from unittest.mock import AsyncMock, MagicMock

def _make_manager(*, run_profile_data=None):
    manager = MagicMock()
    manager.async_save = AsyncMock()          # awaited by the entity
    manager.reset_maintenance = MagicMock()   # sync
    manager.get_saved_run_profiles.return_value = {"library": run_profile_data or {}}
    return manager
```

Then assert on the recorded interaction:

```python
manager = _make_manager()
button = _make_reset_button(manager)
await button.async_press()
manager.reset_maintenance.assert_called_once()
manager.async_save.assert_awaited_once()
```

Use this for anything whose logic is "translate an HA call into a manager call"
— buttons, switches, numbers, sensors. It is faster and more precise than
standing up the full manager.

### …but use `spec_manager()` when the mock is handed to OUR code

The pattern above is right for driving a platform **entity** against a
deliberately partial stub. It is the wrong tool when the mock is passed *into*
our own code as a manager — `PhaseRunner(manager=mgr)`, `RoomMapManager(mgr)`,
`finalizer._collect_finalization_inputs(manager=mgr, …)` — because a bare
`MagicMock` **agrees with the caller, not the callee**:

- it answers to any attribute name, whether or not the real class has one.
  `mgr.learning` does not exist on `EufyVacuumManager` (it is
  `_get_learning_manager()`), and a mock inventing it made a dead path look
  exercised;
- it accepts any argument list. `_collect_finalization_inputs` was called
  without three **required** keyword-only args; the permissive stub swallowed
  the `TypeError` and two live runs wrote no child records while the suite
  stayed green.

```python
from tests._factories import spec_manager

mgr = spec_manager()                       # autospec'd against EufyVacuumManager
mgr.get_active_job.return_value = {...}    # stub what the test needs
runner = PhaseRunner(manager=mgr)
```

`spec_manager` builds `create_autospec(EufyVacuumManager, instance=True)`, so
call signatures are checked against the real functions and unknown names raise.
Instance attributes (`data`, `hass`, `active_job`, …) are invisible to autospec
because they are assigned at runtime, so they are **scraped from
`core/manager.py`** and attached — not hand-listed, because a hand list is a
second source of truth that goes stale silently (the first draft of the helper
proved it, failing 17 tests that had nothing wrong with them).

One consequence worth knowing: autospec makes the manager's `async def` methods
`AsyncMock`s, so `hass.async_create_task(mgr._async_save_logged())` now builds a
real coroutine. `spec_manager` closes it, or Python reports "coroutine … was
never awaited" against whichever test the GC happened to interrupt.

`tests/unit/test_factories_spec_surface.py` is the guard on the guard — it pins
that unknown attributes raise, that bad signatures raise, and (as a control) that
a bare `MagicMock` accepts both.

## Pin discipline: test the contract, not the shape

The mirror image of the mock rule above, discovered by the CAL-23 blind-reconstruction
calibration (2026-08-07). The two diseases:

| | what lies | failure mode | constrains |
|---|---|---|---|
| **Mock disease** | a fake collaborator agrees with the caller | test PASSES while the code is broken | under-constrains behavior |
| **Pin disease** | a real-code test asserts private internals by name | test FAILS while the code is correct | over-constrains implementation |

A test that drives `t._record_rising_edge(...)` or asserts `t._grace_cancels == {}` is
pinning the implementation's *shape*: any correct reimplementation that names or
structures its internals differently fails, while behaving identically. The acid
question for every new test: **would this test accept a correct reimplementation?**
If no, it asserts the wrong contract. Prefer the public surface — the constructor,
the public methods, the emitted state/attributes, the injected-closure seams — and
treat any direct `._name` access as a deliberate exception that needs a comment
saying why the public surface can't force the behavior.

Over-pinning also steers production: `core/error_tracker.py` keeps the deprecated
`harvest_active_run` alive solely because tests assert its semantic (its docstring
says so) — the suite driving the code instead of guarding it.

**Current, honestly stated:** `tests/integration/test_core_error_tracker.py` is the
known worst case — 35 of its 43 tests touch private names (census 2026-08-07).
They guard real behavior today and are NOT being rewritten opportunistically
(suite-freeze ruling); they are quarantined from blind-reconstruction verdicts and
queued as a hardening class. New tests follow this section from now on — the
ratchet direction is: white-box count may only shrink.

## Assertions: prefer presence over exact equality

Because the integration `hass` shares its `config_dir` across tests in a run
(see [05](05-gotchas-and-pitfalls.md)), seeded jobs and stats **accumulate**.
Assert on what your test added, not on totals:

```python
# Good — robust to accumulation
assert result.get("available") is True
assert result["overview"]["job_stats"]["total_jobs"] >= 1
assert any(j["job_id"] == "j-flt-001" for j in jobs)

# Fragile — breaks when another test seeds a job
assert result["overview"]["job_stats"]["total_jobs"] == 1
```

## What not to test

The suite deliberately skips:

- **Pure log-only / best-effort `except` blocks** — a block whose *only* effect
  is a log line (best-effort I/O writes, listener teardown). These carry
  `# pragma: no cover` instead (see below).
- **Inactive / dead code paths** — functions that currently always return early,
  or guards whose conditions are mutually exclusive (e.g. the documented dead
  branch in `core/manager.py`'s progress snapshot).
- **A real device or live HA entity setup** — e.g. the live-entity path of the
  `discover_rooms` service, which drives real adapter entities. The handler
  itself *is* covered with a mock manager (`test_services_rooms.py`
  `test_discover_handler_success` / `test_discover_handler_raises`, SR-5/SR-6);
  only the live-entity path is left to a full integration boot, the same place
  `async_setup_entry` boot wiring runs.
- **Defensive `continue` / `return []` normalization guards** — left as *honest
  misses* (real control flow, so not pragma'd), since a test that feeds garbage
  to assert it's skipped asserts plumbing, not behavior.

Coverage of those costs more than it protects. Spend the effort on real
behavior.

### But DO test an `except` that changes the surfaced result

The opposite of the first bullet: an `except` block is **behavior** — and worth
a test — when it does more than log. Test it when the failure path:

- **wraps the error** as `HomeAssistantError` / `ServiceValidationError` (the HA
  Silver action-exception contract) — `monkeypatch` the manager method to raise,
  then assert the wrapped type (see `test_services_run_profiles.py` `SRN-11`,
  `test_services_maintenance_reset.py` `MR-4/5`);
- **returns a degraded field** the caller sees (e.g. `start_selected_rooms`'
  `learning_snapshot: {saved: False, reason: snapshot_error}`, `SS-7`);
- **skips one item and continues** a fan-out loop (a failing update callback must
  not block the rest — `MD-7`).

The rule of thumb: *if removing the except would change what a caller observes,
it's behavior; if it would only change the logs, it's a `# pragma: no cover`.*

## Coverage exclusions (`# pragma: no cover`)

`.coveragerc` excludes `pragma: no cover` lines. Put it on the **`except` line
itself** (not the log line) so the whole branch drops, and append a short reason:

```python
except OSError as err:  # pragma: no cover - best-effort I/O, logs and swallows
    _LOGGER.debug("…failed to write %s: %s", path, err)
```

Use it surgically, one audited block at a time — never a blanket `_LOGGER.*`
regex, which would also silence the behavioral excepts above and leave
half-excluded branches under `--cov-branch`. The full convention is in
[subsystems/README](subsystems/README.md#coverage-conventions-apply-everywhere).

## The two ratchets (mock debt, doc coverage)

Two committed gates hold ground that the campaign is slowly reclaiming. Both are
SHRINK-ONLY: the numbers may fall freely, and raising one is meant to be harder
than fixing the thing it measures.

### Mock ratchet — `tests/test_mock_ratchet.py`

A bare `MagicMock()` / `AsyncMock()` **agrees with the caller, not the callee**:
every attribute exists, every method returns another mock, every shape assertion
passes. Audit 1 traced four live failures to exactly that, green all the way to
hardware. `spec_manager()` and `create_autospec` are the cure (see
[spec_manager](03-fixtures-and-helpers.md)); this gate measures where they are
not yet used.

`tests/mock_allowlist.json` records a per-file CEILING for the 40 files that
currently carry bare mocks. A file **not** on that list may have zero — that is
the half that matters, because the debt is concentrated and what must be
prevented is it reappearing in the ~145 files that are clean.

This is **not a ban**. Entity-driving partial stubs are correct and stay (above).
The doctrine's line is *a mock handed INTO production code must be spec'd*, which
needs per-site judgement; the gate only holds the total steady while that happens.

```bash
python scripts/mock_census.py                     # the current profile, worst first
python scripts/mock_census.py --write-allowlist   # bank progress AFTER converting
```

### Front-page link gate — `tests/unit/test_readme_links.py`

`mkdocs.yml` sets `docs_dir: docs` and builds `--strict`, so every link inside
`docs/` is validated on each Pages build. `README.md` sits at the repository ROOT,
which puts it outside that gate entirely — no CI job reads it at all.

The gap was not theoretical. The README pointed at `…/docs/dev/27-render-harness/`
after that file was renamed to `docs/dev/frontend/render-harness.md`. There is no
redirects plugin and the Pages deploy replaces the whole artifact, so it had been a
hard 404 since the rename, found eventually by a hand audit.

Four checks, all offline: every repo-relative path exists on disk; every published
docs-site URL maps to a real source file under `docs/` (including the section
landings, which are `README.md`, not `index.md`); every in-page anchor matches a
heading that still exists; and reference-style definitions and uses match in both
directions. External URLs are deliberately NOT checked — they need the network and
other people's repos are allowed to move.

Retiring a screenshot or renaming a docs page now fails here instead of on the
front page.

### Documentation ratchet — `tests/test_docs_ratchet.py`

A test file that appears nowhere in `docs/testing/` produces no findings and reads
exactly like a well-covered one — the same shape of lie as the mock, one level up.
`tests/undocumented_tests.json` lists the current backlog; **a new test file must
be mentioned in its subsystem page in the same commit that creates it.**

```bash
python scripts/mock_docs.py --undocumented   # what is still missing
```

### The generated `Mocking` column

Each subsystem coverage table carries a `Mocking` cell derived from the same
census that feeds the ratchet — so the docs and the gate cannot disagree. It
aggregates a row's test files and reports the risk (`bare xN`), not the pedigree:
`clean` means nothing in that row constructs an unspec'd mock. The `Layer` column
says unit-vs-integration, which is not the axis that bites.

Generated, so hand edits are overwritten:

```bash
python scripts/mock_docs.py            # rewrite the column
python scripts/mock_docs.py --check    # CI-style staleness check, writes nothing
```

Both ratchets and the column live in `tests/test_mock_ratchet.py`,
`tests/test_docs_ratchet.py`, `scripts/mock_census.py` and `scripts/mock_docs.py`.

## Generated documentation — the staleness gate

A generated document cannot drift the way prose does. It drifts by **not being
regenerated**, and that is indistinguishable from being correct: the file is
well-formed, the numbers are specific, and nothing about it looks old.

Both generated surfaces in this repo were stale when the gate was written, and
neither had ever failed anything:

| surface | state found | why nothing caught it |
|---|---|---|
| `docs/dev/reference/THEME_TOKEN_USAGE.md` | 651 lines out of date after 31 commits to `src/styles/`; **every `file:line` citation wrong** (`index.js:324` had become `:393`) | the generator was run by hand, last on 2026-08-11 |
| the `Mocking` column in `subsystems/15-adapters.md`, `17-services.md` | two rows stale | `mock_docs.py --check` existed, documented as *"CI: fail if stale"*, and was wired into nothing |

The second one is the sharper lesson: the check was already written and already
correct. Writing a checker is not the same as running one.

`scripts/check_generated_docs.py` holds a registry of every generator and compares
what is in the tree against what the generator emits **now**.

```bash
python scripts/check_generated_docs.py          # check
python scripts/check_generated_docs.py --fix    # regenerate everything, then re-check
```

Five findings, each ablated in `tests/unit/test_generated_doc_gate.py` (`GDG-1`..`GDG-16`)
— a clean run against a clean tree proves nothing about a detector that is silently
dead:

| | |
|---|---|
| `STALE` | the generator now emits something else |
| `MISSING` | a registered file is not in the tree |
| `SILENT` | the generator exited 0 and wrote nothing, or wrote the wrong name |
| `BROKEN` | it could not be run, timed out, or failed |
| `UNGATED` | a file carrying the `GENERATED FILE` banner that no registry entry claims — the omission failure, so adding a generator and forgetting to register it fails here rather than nowhere |

Entries come in two shapes. **Whole-file** generators write complete documents and
name an env var this gate sets to redirect them into a scratch tree, so the check
never touches the working copy — one that wrote over the tracked files and restored
them would leave the tree dirty on exactly the run that failed. **Region** generators
rewrite a block inside a hand-written page (the `Mocking` column), so there is
nothing to redirect; they bring their own `--check` and a non-zero exit means stale.
A command that cannot be run at all is `BROKEN`, never `STALE` — those are opposite
instructions, and reporting a missing `node` as "your docs are stale" sends the
reader to regenerate a document that was already current.

**This one IS a CI gate**, unlike [`check_docs_index.py`](../dev/README.md), and the
difference is not an inconsistency. That script is a doc-commit rule because a new
document legitimately lands before the index pass that files it, so gating on it
would fail pushes for work that is not yet due — the 2026-06-12 `check_legend_drift.py`
ruling. Staleness here is the opposite shape: it is caused by a **code** change, the
fix is one command with no editorial judgement in it, and there is no later pass
that is supposed to catch up. Same reason `check-styles.mjs` gates the build. It runs
as the `generated docs` job in `tests.yml`.

**Line-precise citations are what a generated doc is FOR**, and this gate is what
makes them safe. The standing rule that prose cites symbols rather than line numbers
exists because prose has no mechanism to stay current. A generator does — provided
something runs it.

### Testing a generator: assert on the DOCUMENT

`EVT-1`..`EVT-3` in the same file cover `scripts/gen_event_docs.py`, and they read
the emitted markdown rather than anything the generator printed about itself. That
distinction is the whole point. The bug they pin had reached the output: where two
fire sites built a payload key differently, only the first expression survived, so
17 slots printed one expression as though it were the only one — `source` and
`trigger` among them, the keys an automation actually branches on. Every count the
generator reported was correct while the document was wrong, so no stdout assertion
could have seen it.

They run against a synthetic three-file package via `EVCC_EVT_ROOT`, not the real
integration, so ordinary churn cannot fail them for an unrelated reason. `EVT-3`
asserts the blind-spot ledger is present **and non-empty**: a generated page that
declares no blind spots reads as one that has none, which is how
`THEME_TOKEN_USAGE.md` once reported 135 live theme tokens as dead.
