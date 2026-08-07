# 05 — Gotchas and Pitfalls

The traps that have actually cost time on this suite. Read this before debugging
a confusing failure — the answer is probably here.

## 1. Managed rooms live under `data["maps"]`, not `data["rooms"]`

This is the single most expensive mistake. Managed rooms are stored at:

```
manager.data["maps"][vacuum_entity_id][map_id]["rooms"]
```

accessed through `ensure_map_bucket` / `get_map_bucket` and read by
`get_managed_rooms`. There is a `data["rooms"]` key in some contexts, but it is
**not** where managed rooms are read from — seeding it does nothing and your
test silently exercises the empty-state path instead of the one you meant.

Other internal locations worth knowing:

| Data | Location |
|------|----------|
| Managed rooms | `data["maps"][vac][map]["rooms"]` |
| Active job state | `data["active_jobs"][vac][map]` |
| Discovery (pre-save) | `data["discovery"][vac][map]` |
| Error tracker | `hass.data[DOMAIN][DATA_ERROR_TRACKER]` |

When in doubt, find the **reader** in the source and seed exactly what it reads.
Do not guess the layout from the key name.

## 2. The integration `hass` shares `config_dir` across tests

Within a single pytest run, the phac `hass` reuses one `config_dir`, so
**anything written to the store persists between tests** — completed jobs,
stats files, learning history, snapshots. Two consequences:

- **Totals accumulate.** Assert with `>=` / presence checks, never exact counts
  (see [04](04-patterns-and-conventions.md)).
- **A malformed file you write can break a later test.** If you seed a store
  file in a non-canonical shape, the next test that reads it through the real
  code path can crash. If you must write an unusual shape, capture the original
  and restore it in a `finally`:

  ```python
  store = LearningHistoryStore(hass)
  original = store.load_accuracy_stats(vacuum_entity_id=_VAC)
  try:
      store.save_accuracy_stats(vacuum_entity_id=_VAC, payload={...unusual...})
      # ... assert ...
  finally:
      store.save_accuracy_stats(
          vacuum_entity_id=_VAC,
          payload=original if isinstance(original, dict) else {"rooms": {}},
      )
  ```

  Better still: seed through the **real writer** (a service call or the recorder
  method) so the shape is canonical by construction and never poisons anything.

## 3. Seed the canonical shape — readers and writers can disagree

A persisted structure is only as good as the agreement between the code that
writes it and the code that reads it. The accuracy-stats file is the cautionary
tale: it is written as a **dict keyed by room_key** with a fractional error, but
one reader expected a **list** of percent entries — so recorded data silently
never reached that reader.

When you seed a file directly, match the shape the **production writer**
produces, not the shape a single reader happens to want. If you cannot tell, run
the real writer once and inspect the file.

## 4. `used_for_learning` is computed, not just passed through

`build_completed_job_payload` flips `used_for_learning` to `False` when the job
has learning blockers: `invalid_room_count` (room_count <= 0), `invalid_duration`
(duration <= 0), `missing_resolved_rooms`, or a cancelled/failed/interrupted/test
status. A downstream effect: the battery-metrics handoff is skipped for
non-learning runs.

So a finalize test that wants the "happy" learning path must give the job real
shape — seed an active job with `resolved_rooms` and use a positive duration:

```python
_seed_active_job(manager, _VAC, _MAP, resolved_rooms=[
    {"room_id": 1, "slug": "kitchen", "name": "Kitchen",
     "clean_mode": "vacuum", "clean_intensity": "standard",
     "clean_times": 1, "is_carpet": False},
])
```

Pass `used_for_learning=True` **and** give it a room, or the blocker logic
overrides you.

## 5. Adapter config must be registered for entity-dependent paths

Code that reads adapter entities (`task_status`, `dock_status`, wash-frequency,
etc.) goes through `get_adapter_config(vacuum_entity_id)`. In tests, register a
config first:

```python
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

register_adapter_config(_VAC, {
    "adapter_id": "test",
    "source": "test",
    "entities": {"task_status": "sensor.alfred_task_status"},
    "vocabulary": {"cancel_service_exclusion_states": ["mop_washing"]},
})
```

The `manager` fixture wires an `AdapterCoordinator` as the active coordinator, so
`register_adapter_config` routes into it and is isolated per test (each test gets
a fresh coordinator). Omit a `mapping` block to skip the segmenter-engine
validation. Leaving `task_status` unset is itself a valid test case — the cancel
detector returns `no_task_status_entity`.

## 6. Schedule loop work threadsafely from the executor

A sync method running in the executor (via `async_add_executor_job`) is **not**
on the event-loop thread. Calling `hass.async_create_task(...)` there raises
"no running event loop". The fix used in the codebase:

```python
self.hass.loop.call_soon_threadsafe(self.hass.async_create_task, _coro())
```

If you write or test a sync path that needs to kick off async work, use this
pattern — do not call `async_create_task` directly from executor code.

## 7. Coverage percentage depends on which files you run

A module's number changes with the set of test files in the run, because
different files cover different parts of it. To get a module's true coverage,
run **every** file that exercises it (unit + integration). See
[02](02-running-tests.md#per-file-vs-combined-coverage).

## 8. Do not edit `.storage` files to set up state

This is a project-wide rule, and it applies to tests too: drive state through
the manager, the services, or the store API — never by hand-editing serialized
HA storage. Direct edits produce hard-to-find `.corrupt` backups.

## 9. `setup_map` / `save_managed_rooms` auto-confirms floor types

To exercise the **onboarding-incomplete** path (e.g. the `get_start_status`
`onboarding_required` gate), it is not enough to seed rooms and enable them —
`save_managed_rooms` marks their floor types confirmed, so onboarding reads as
complete. Clear the confirmations after seeding:

```python
setup_map(manager, _VAC, _MAP, count=2)
for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
    room["enabled"] = True
# undo the auto-confirm so enabled rooms still need a floor type
manager.data["onboarding"][_VAC][_MAP]["floor_types_confirmed"] = {}
```

## 10. Start gates fire in order — clear earlier gates to reach a later one

`get_start_status` / `_build_effective_start_plan` evaluate gates in sequence
(paused job → onboarding → access-graph-required → all-blocked → lifecycle).
A rule-bearing room trips `access_graph_required_for_rules` **before** the
all-selected-blocked branch is reached, so to test the later gate you must
satisfy the earlier one — e.g. build a **complete** access graph (a dock room
granting access to the others) so the rule-bearing rooms clear the graph gate,
*then* assert `all_selected_rooms_blocked`. If a gate test returns an unexpected
reason, it's usually an earlier gate firing first — check the order.

## 11. Fire-and-forget executor file writes — drain, clean-slate, and watch for read-modify-write races

`test_dock_drift_log` cost a red CI run after a clean local pass. It's the
cautionary tale for three traps that compound:

- **The write is fire-and-forget on the executor.** `_handle_position_update`
  schedules `_append_dock_drift` via `hass.async_add_executor_job(...)` *without*
  awaiting it. A test that fires two updates back-to-back must
  `await hass.async_block_till_done()` **between** them — not just at the end — or
  the two executor jobs run concurrently: non-deterministic order, and (next
  point) a lost write.

- **It read-modify-writes the whole file.** `_append_dock_drift` reads the JSONL,
  appends, rolls off old lines, and rewrites atomically. Two concurrent appends
  both read the old contents and one overwrites the other → lost update. CI's
  thread scheduling dropped the second record (`len == 1` instead of `2`);
  locally the two happened to serialize, so it passed. The fix is a
  `threading.Lock` around the read-modify-write. Writes that **append**
  (`open(path, "a")`, e.g. `battery/store.py`) or write a **full snapshot**
  (e.g. `_flush_samples_to_disk`) are race-free and need no lock — the trap is
  *read-modify-rewrite reached by a rapid fire-and-forget path*.

- **The file persists across runs** (gotcha 2). The dock-drift JSONL lives under
  the shared `config_dir`, so on a *re-run* it already exists and the count climbs
  (`2 → 4 → …`). When you must assert an **exact** count on a file the test
  writes, clear it first:

  ```python
  drift_path = tracker._dock_drift_path(_VAC)
  if drift_path.exists():
      drift_path.unlink()
  ```

  Otherwise prefer `>=` / presence checks (gotcha 2). `pytest tests; pytest tests`
  in one container is the cheap check for this whole class of re-run flake.

## 12. `Number.isFinite` does NOT prove a value was present — `Number("")` is `0`

JavaScript coerces several *absent-ish* values to `0`, and `0` is finite. So the
common shape

```js
const n = Number(raw);
return Number.isFinite(n) ? n : null;   // WRONG for null / "" / [] / false
```

silently turns **missing data into a real reading of zero**. The coercion table is
the trap, because it is not consistent:

| input        | `Number(input)` | passes `isFinite`? |
|--------------|-----------------|--------------------|
| `null`       | `0`             | **yes** ← absent becomes zero |
| `""`         | `0`             | **yes** ← absent becomes zero |
| `"   "`      | `0`             | **yes** |
| `[]`         | `0`             | **yes** |
| `false`      | `0`             | **yes** |
| `undefined`  | `NaN`           | no  |
| `"unknown"`  | `NaN`           | no  |

`undefined` and `"unavailable"` are caught; `null` and `""` are not. Code that
looks tested because it handles `"unavailable"` still lets `null` through.

**Why it matters more than a wrong number.** Zero is rarely a neutral value in
this domain — it is usually an *alarming* one. A battery of `null` means unknown;
a battery of `0` means flat. An `attention_count` of `null` means "not computed";
`0` means "all clear". The bug does not produce nonsense you would notice, it
produces a confident, plausible, wrong answer.

**The rule: check for the non-value BEFORE coercing.**

```js
if (raw == null || raw === "" || raw === "unavailable" || raw === "unknown") {
  return null;
}
const n = Number(raw);
return Number.isFinite(n) ? n : null;
```

(`raw == null` with `==` is deliberate — it catches `null` and `undefined` both.)

**Testing it.** A test that only feeds `"unavailable"` and a good value will pass
against the broken form. The case that bites must be in the table:

```js
for (const bad of [null, "", "   ", "unavailable", "unknown"]) {
  assert.equal(readValue(bad), null, `input ${JSON.stringify(bad)}`);
}
```

**This has happened three times in one session** (REV-6, an absent battery
rendered as "Battery 0"; CENSUS-6, `Number(attention_count)` with `null`;
BAT-6, an empty `sensor.<vacuum>_battery` state reading as a flat battery). Two
were caught by tests written for the *same* fix minutes earlier, which is the
argument for the loop above rather than a single happy-path case.

The Python equivalent is milder but real: `float(None)` raises, but
`_safe_float(value, 0.0)` returns the default and is indistinguishable from a
genuine `0.0`. Prefer a `None` default and let the caller decide.

## Assigning over a spec'd method throws its protection away

`spec_manager()` / `spec_of()` give every method an autospec child that checks the
call signature. **Assigning a fresh mock over one silently removes that check** —
and the assignment usually happens in exactly the tests that most need it.

```python
mgr = spec_manager()
mgr.get_start_status(bogus_kwarg=1)          # TypeError — protected

mgr.get_start_status = MagicMock(return_value={"ok": True})
mgr.get_start_status(bogus_kwarg=1)          # ACCEPTED — protection gone

mgr2 = spec_manager()
mgr2.get_start_status.return_value = {"ok": True}
mgr2.get_start_status(bogus_kwarg=1)         # TypeError — protection KEPT
```

So: **`x.method.return_value = …`, not `x.method = Mock(return_value=…)`.** Same
stub, same test, signature checking retained.

Two caveats worth knowing rather than guessing at:

**It only matters for methods that HAVE a signature.** Roughly half of
`EufyVacuumManager`'s public surface (77 of 158) is thin `**kwargs` delegators, where
autospec has nothing to check and the two forms are equivalent. The conversion is
worth doing on the strict half, not mechanically everywhere.

**Attribute protection is bypassable by assignment.** Reading `mgr.learning` raises
`AttributeError` — that is [spec_manager](03-fixtures-and-helpers.md) refusing to
invent one of audit 1's four defects. But *assigning* `mgr.learning = MagicMock()`
succeeds, and every later read then works. `create_autospec` is not `spec_set=True`,
and cannot be here: `spec_manager` legitimately assigns the runtime `self.<name>`
attributes it scrapes from `core/manager.py`, which a class-derived spec does not
know about. If a test needs `mgr.learning`, that is the signal it is testing against
a shape production does not have.

## The mock-failure ledger

Every defect below **reached running hardware with the suite green**. Each is here
because a test double answered a question the real object would have refused.

This is the audit record's test wing: it exists to make old mistakes expensive to
repeat, not to catalogue every mock we dislike. **Only incidents that actually bit are
listed.** A hardening we applied pre-emptively is not an incident and does not belong
here — that distinction is the ledger's whole value, because a list padded with
near-misses stops being evidence of anything.

Append when the next one bites. Do not append hypotheticals.

### ML-1 · A mock invented an attribute production does not have

**What lied.** `mgr.learning`. The core manager reaches the learning manager through
`_get_learning_manager()` (via `hass.data`), and genuinely never assigns `.learning`.
A `MagicMock` manufactured it on demand.

**What it cost.** The first real phased run — kitchen → 2 min wait → Entryway + Home
Office — produced a correct parent, a correct break record, and **not one child**. The
`AttributeError` was swallowed by a best-effort handler, so every clean phase recorded
`record_id: null`.

**Why the test could not catch it.** The fixture written to make wave 2 execute did
`mgr.learning.finalizer = …` on a bare mock. *The fixture built the illusion it was
written to dispel.*

**Guarded by.** `spec_manager()` — autospec cannot invent an attribute the class does
not declare, so reading `mgr.learning` now raises. Reintroducing the bug fails 6 tests
instead of 0. (`6790952`, `e665db7`)

### ML-2 · A bare mock silently disabled the code path under test

**What lied.** `finalize_from_inputs` returned a `MagicMock`, so
`isinstance(result, dict)` was `False` and `_finalize_phase_as_child` bailed returning
`None`.

**What it cost.** Every "a clean phase has no child" assertion passed **for the wrong
reason**, and wave 2 went completely unexercised while appearing tested.

**Guarded by.** The fixture now stubs the finalizer with **real dicts**, so the child
path actually runs. (`b49818d`)

### ML-3 · A permissive stub swallowed a required-argument mismatch

**What lied.** `def _collect(**kw)` accepts anything.
`_collect_finalization_inputs` requires three keyword-only args with no defaults
(`forced_outcome_status`, `forced_lifecycle_state`, `forced_lifecycle_message`); the
call omitted all three.

**What it cost.** Every child raised `TypeError` immediately. **Two live runs wrote no
child records; three deploy cycles to find.**

**Guarded by.** The stub is now derived from the function it stands in for —
`inspect.signature(...).bind()` — so it rejects exactly what production rejects.
(`4adcac9`)

### ML-4 · A fake agreed with the caller about where a value lives

**What lied.** `finalize_from_inputs` reads `inputs["job_id"]`; only
`active_job_state["job_id"]` was being set. The fake finalizer read from the same wrong
key the caller wrote to, so the two agreed with each other and not with production.

**What it cost.** Past the ML-3 `TypeError`, every child would have been written under
the **run's own id** — overwriting the run's record instead of landing beside it, and
silently, because the write itself succeeds.

**Guarded by.** The stub reads `inputs`, as production does. (`4adcac9`)

### ML-5 · A sync mock hid a missing `await` — and shipped to a user

The only one here that escaped to someone else's house.

**What lied.** A shared manager mock stubbed `start_run_profile` as a **sync**
`MagicMock`. `EufyVacuumSavedRunProfileButton.async_press` called the coroutine without
awaiting it, so its body never ran — but the un-awaited call still *recorded*, and
`assert_called_once` passed.

**What it cost.** Every exposed profile button silently no-oped, on every brand.
Reported from the outside on an Omni E28 (issue #42). The only runtime signal was a
`coroutine was never awaited` RuntimeWarning, invisible in `home-assistant.log`. The UI
"Start Cleaning" worked, because the service handler awaits the same call — so the
failure looked like a button problem rather than a missing `await`.

**Guarded by.** `AsyncMock` + `assert_awaited_once_with`, and the fix **measured the
break**: the test was verified to FAIL when the `await` is removed. (`9ff783d`)

### What the five have in common

Four of the five are the same sentence: *the double agreed with the caller.* Not one
was a wrong assertion — every test asserted the right thing about an object that was
not behaving like the real one.

Two structural lessons, both cheap:

**A green test proves nothing until you have seen it fail.** ML-5's fix measured the
break; ML-1's records that reintroducing the bug now costs 6 failures. The other three
were found by hardware.

**Suspect the fixture that makes a new path "work".** ML-1 and ML-2 were both
introduced by fixtures written to exercise wave 2. A stub authored to make code run
will make it *appear* to run.
