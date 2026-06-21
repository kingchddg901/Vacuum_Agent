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
