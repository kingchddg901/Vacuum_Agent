# 17 — Services — Subsystem Test Map

The services subsystem is the HA service-call layer: thin async handlers that
resolve call data, delegate to the manager, and wrap failures as
`HomeAssistantError` / `ServiceValidationError` (the HA Silver action-exception
contract). Covered by **264 tests across 17 files**.

Source: `custom_components/eufy_vacuum/services/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md)

**Scope.** This doc covers only the `services/` package — the handlers wired by
`async_register_services`. The integration registers many more `eufy_vacuum.*`
services from sibling packages, and those are tested under their own subsystem
docs, not here:

- Map/segment/layout/live-pose services in `mapping/mapping_services.py`
  (registered via `async_register_mapping_services`) — see
  [07-mapping.md](07-mapping.md).
- Learning + external-run services in `learning/services.py` — see
  [06-learning.md](06-learning.md).
- Theme services in `themes/services.py` — see [14-themes.md](14-themes.md).

---

## Rename repair (`RS`) — the manual half of D4

`setup_repair_renamed_vacuum` exists because the automatic migration is driven by a listener that
only records renames it was running to see. A rename from before that shipped left no record, and
Home Assistant does not keep the old entity id anywhere — so only the user can supply it.

Covered by `tests/unit/test_services_repair_renamed_vacuum.py`. Two targets carry the reasoning:

- **`RS-4`** — a collision changes **nothing** by default and names what is in the way. This is the
  expected first call, not an edge case: the new id normally holds the empty record
  `ensure_vacuum_record` created on the first restart after the rename. Reporting has to precede
  destruction, because a user cannot consent to discarding something nobody told them about.
  Ablating the default to always-overwrite turns `RS-4` red on its own.
- **`RS-6`** — the response carries `sections_moved` and `tree_moved`, which are written by
  `core/manager.py::_apply_pending_entity_renames` and not by the service. Their presence is the
  evidence that the service **delegated** rather than growing a second, divergent migration.


## Coverage map

| Source module | Stmts | Cov | Test file | Mocking |
|---------------|------:|----:|-----------|-------|
| `job_control.py` | 154 | 93% | `test_services_job_control_read.py`, `test_services_job_control_write.py` | **bare x10** |
| `run_profiles.py` | 104 | 100% | `test_services_run_profiles.py` | **bare x1** |
| `adapter_config.py` | 107 | 96% | `test_services_adapter_config.py` | clean |
| `setup.py` | 219 | 84% | `test_services_errors_setup.py` | **bare x2** |
| `dock.py` | 80 | 100% | `test_services_dock.py` | **bare x5** |
| `room_profiles.py` | 81 | 100% | `test_services_room_profiles.py` | clean |
| `rooms.py` | 108 | 98% | `test_services_rooms.py` | **bare x1** |
| `maintenance.py` | 47 | 100% | `test_services_maintenance_reset.py` | clean |
| `queue.py` | 135 | 96% | `test_services_queue.py`, `test_services_unmanaged_vacuum.py` | **bare x1** |
| `snapshots.py` | 71 | 100% | `test_services_snapshots.py`, `test_services_unmanaged_vacuum.py` | clean |
| `errors.py` | 40 | 96% | `test_services_errors_setup.py`, `test_services_unmanaged_vacuum.py` | **bare x2** |
| `access_graph.py` | 34 | 100% | `test_services_access_graph.py` | clean |
| `clean_order.py` | 42 | 96% | `test_services_clean_order.py` | spec'd |
| `_common.py` | 54 | 94% | `test_services_common.py`, `test_services_misc.py`, `test_services_unmanaged_vacuum.py` | clean |
| `stall_capture.py` | 43 | 100% | `test_services_stall_capture.py` | spec'd |
| `debug.py` | 8 | 100% | `test_services_misc.py` | clean |

---

## What's tested

- **Two services, two audiences, and every refusal was an unexercised `raise` (`SSC-1..8`)** —
  `test_services_stall_capture.py`. `stall_capture.py` shipped registered and documented with
  **25 of 43 statements and 0 of 6 branches** reached: the managed-vacuum gate, the no-active-map
  refusal and the not-currently-cleaning refusal had never run, which is the same shape as the
  abort that could never fire in issue #51. The handlers are closures inside `register()`, so the
  tests pull them off the registration list rather than importing a callable — which exercises the
  real registration path as a side effect (`SSC-8` asserts both carry `supports_response="only"`,
  since a caller that cannot read the response cannot use either). `SSC-3` deliberately **pins a
  known divergence** rather than asserting it is correct: `setdefault` mutates `manager.data`
  before the authorization decision, so a refused call leaves `data["vacuums"] = {}` behind (C12,
  still open). It is pinned so the repair lands with a red test instead of silently. **Ablated:**
  seven substitutions — dropping each guard, the flag write, the room-name fallback, the canonical
  event name and `supports_response` — each reddened exactly its own test, restores byte-identical.


- **A service exists because something CALLS it (`SNP-5`)** — `test_services_snapshots.py`.
  `get_maintenance_source_candidates` sat on the manager for a day with **zero callers**: no
  service, no snapshot field, nothing. It was written as "the picker's read half" and the picker
  could not have read it, while the suite stayed green throughout — `f/audit_callsite_reachability`
  exactly, a correct function whose absence of a call site no test could see. `SNP-5` therefore
  asserts the **service answers**, not the payload shape: `has_service(...)` first, then a real
  call. `SNP-5b` carries the `INKV8ZQD` read guard so asking about an unmanaged vacuum cannot mint
  a record for it. **Ablated:** deleting the `async_register` block reddens both, which is
  precisely the state the function shipped in.

  *Why the response is a dict wrapping a list:* a HA service response must be a mapping, and
  `candidates` stays a list even when empty — the card distinguishes "the fetch has not landed"
  (`null`) from "there is nothing to offer" (`[]`), and returning the wrong one shows an
  empty-state to somebody whose request is still in flight.

- **Unmanaged vacuums (`INKV8ZQD`)** — `test_services_unmanaged_vacuum.py`.
  `cv.entity_id` validates the SHAPE `domain.object_id` and nothing more, so every
  per-vacuum store keyed off an unchecked id used to mint a durable bucket for
  whatever string an automation passed. A **write** now refuses
  (`ServiceValidationError`); a **read** returns the empty shape with
  `reason: "unmanaged_vacuum"` rather than raising, because a read is how the card
  discovers state. `[UV-5]` asserts the managed case still works — without it the
  whole file would pass against a guard that refused everything.
  Each guard was **ablated** and confirmed to turn a test red; that pass caught two
  of these tests being decorative, one because the ErrorTracker was never loaded so
  the guarded path was unreachable, and one because a second guard at the service
  layer masked the manager-level fix it was meant to prove.


- **Read services** — snapshots, job-control read, access-graph, saved profiles,
  dashboard snapshot: returned-shape assertions through the registry.
- **Write services** — job-control write, run-profile + room-profile + maintenance
  CRUD, queue build/clear, adapter-config set: side effects + persistence.
- **Input validation** — the `update_room_fields` color validator normalizes raw
  frontend input to canonical `#rrggbb` (`#rgb` expansion, hash-prepend, lowercase,
  empty → clear) and rejects non-hex values at the service-schema boundary.
- **Error contract** — a manager-layer failure surfaces as `HomeAssistantError`
  (run-profile save/apply/rename/overwrite/delete, maintenance reset, set-interval
  save path), and not-found conditions raise `ServiceValidationError`.
- **Call-data resolution + job-finished payload** (`_common`) — `resolved_call_data`
  map-id defaulting (incl. the no-active-map pass-through), and
  `job_finished_event_payload` built from a `finalize_result`-wrapped result.

### `snapshots.py` — 84.81% → 100% (`SNP-4`, `SNP-6`–`SNP-8`, 2026-11-08)

Its twelve uncovered units were **two whole behaviours**, not a scattered tail: both
READ handlers' unmanaged arms, and `_handle_set_vacuum_capability` in its entirety
including its registered delegator. The manager method behind that handler is well
covered by `test_user_capability.py`; the **service** that reaches it had no test at
all — the forgotten-sibling shape again.

| id | what it holds |
|---|---|
| `SNP-4` | both reads answer empty-**with-a-reason** for an unmanaged vacuum, and mint no record |
| `SNP-6` | the WRITE **refuses** with `ServiceValidationError` instead |
| `SNP-7` | the capability service records the user's answer **and persists it** |
| `SNP-8` | an omitted `supported` **clears** the override rather than storing `False` |

**`SNP-4` and `SNP-6` are one claim in two halves.** The split is a ruling
(`INT62M7A`, 2026-08-18): a write refuses so HA shows a toast rather than a traceback,
a read returns its empty shape carrying `reason` "because a read is how a card
discovers state and turning discovery into an error trades a blank panel for a red
toast". Ablation separates them: converting the write's refusal into a read-style
answer — the plausible "make it consistent" edit — reddens `SNP-6` **and leaves
`SNP-4` green**, which is what shows the two tests establish a split rather than a
preference.

**`SNP-8` is the one with real user consequence.** The schema says absent means clear
— "a user who answers wrongly must not be stuck with it" — and the handler passes
`data.get("supported")`, so absent arrives as `None`. Defaulting that to `False` would
pin the wrong answer permanently, which is the exact failure the feature exists to
undo. The test sets the override first, because "no override present" is also what a
service that never stored anything produces.

**`SNP-7` pins the save with a wrapping spy, and had to.** Asserting on `manager.data`
cannot see a missing `async_save` — the handler mutates the dict and *then* persists,
so the read-back passes either way. Measured: dropping the save reddened nothing until
the spy was added, and an earlier draft of that docstring claimed otherwise. The spy
`wraps` the real method, so the save still happens.

Two things about the existing ids, both left alone rather than changed in passing:
`SNP-5` was already taken, which is why `SNP-4` carries both reads as parametrize rows;
and `SNP-5b` — the third read's equivalent — is **named** `refuses_an_unmanaged_vacuum`
while its body asserts the service *answers*, and it checks only `isinstance(result,
dict)`, so a bare `{}` would satisfy it.

### `setup.py` — 83.74% → 94.46% (`SVS-11`–`SVS-20`, 2026-11-08)

It was the lowest-covered file in the package. These close **every** uncovered unit
outside the `manager is None` ruling in Known gaps below — 30 of its 47.

| id | what it holds |
|---|---|
| `SVS-11` | `_completed_step_result` treats a non-dict as COMPLETED, so a step cannot wedge the panel |
| `SVS-12` | the `enabled_room_ids` validator's ACCEPT path, and that it coerces to **ints** |
| `SVS-13` | a `pending_entity_renames` value read back as a non-list is repaired **in storage** |
| `SVS-14` | an explicitly supplied `map_id` wins over the resolved active map |
| `SVS-15` | a manager carrying no `resolve_active_map_id` still rejects (legacy every-map) |
| `SVS-16` | a **blocked** add does not stamp the setup step as done |
| `SVS-17` | an entity override with no config entry plants no panel-survival marker (ISSUE #63) |
| `SVS-18` | `setup_unreject_rooms` — A4-SETUP-6's escape hatch, which had **no test at all** |
| `SVS-19` | the map-camera override's **per-map** branch, [SVS-10]'s untested sibling |
| `SVS-20` | clearing one map's camera leaves the other maps' overrides intact |

**Three of these were vacuous before the ablation caught them**, which is the part
worth carrying:

- `SVS-18` asserted `'"2"' not in json.dumps(...)`. The ids are stored as **ints**, so
  the quoted form never appears and the assertion held whatever the handler did —
  stubbing the handler's call out entirely reddened nothing. It now reads the stored
  set through `drift.rejected_room_ids_for`, the module's own accessor, which also
  deliberately does not materialise the record it reads.
- `SVS-16` first used a never-seen vacuum id. Nothing stamps a step for one —
  `drift._get_progress_record` refuses to create a record for a vacuum the install
  does not have — so the assertion passed for the wrong reason. It now uses a
  **stored-but-offline** vacuum: `add_vacuum` checks the state machine *before* the
  already-managed check, so a stored record with no live state returns `blocked` while
  still being real enough for a step record to exist.
- `SVS-15` could not reach its arm at all at first: `EufyVacuumManager` **does** define
  `resolve_active_map_id`, which is why that line was uncovered. `delattr` on the
  instance raises for a class attribute and `hasattr` still answers True, so a draft
  concluded the method was absent when it is always present. It now shadows the method
  on the instance, which is the faithful stand-in for the duck-typed manager the
  `getattr(..., None)` guard exists for.

Eleven ablations, eleven at the predicted verdict after those fixes. Two are worth
noting: ablating `_completed_step_result` reddens the pre-existing `SVS-8b` as well,
because both `setup_add_vacuum` and `setup_import_active_map` consult that one
predicate; and the per-map cleanup's two ablations redden `SVS-19` and `SVS-20`
*separately*, which is what says `SVS-20` is not redundant.

---

## How it's tested

The `manager_with_services` fixture registers the full service set (same path as
`async_setup_entry`). Tests call `hass.services.async_call(DOMAIN, name, data,
blocking=True, return_response=True)`. Error-contract tests `monkeypatch` a
manager method to raise and assert the wrapped exception type.

---

## Known gaps

`queue.py` (77%) is now the real gap in this subsystem, not a defensive tail —
this campaign added the queue **breaks/steps** service handlers
(`_handle_get_queue_steps`, `_handle_add_queue_break`,
`_handle_remove_queue_break`, `_handle_clear_queue_breaks`,
`_handle_set_queue_breaks`, `_handle_add_queue_zone`, missing lines 202-244)
and their `register()` closures (missing lines 266-281) — none of them are
exercised by `test_services_queue.py`. The handler bodies are thin delegators
to the manager (`get_manager(hass).<method>(**resolved_call_data(...))` +
`async_save()`), so this is closer to an untested wrapper than untested logic,
but it is a real gap, not a documented-defensive one — flagged here rather
than characterized as intentional. (Line 62 is a genuinely defensive
`isinstance` guard in a payload-normalization helper, unrelated to the above.)

The remaining misses elsewhere are still almost all defensive, not untested
behavior, though line numbers have shifted with the campaign's growth:

- **`manager is None` early-returns (defensive)** — the runtime-not-available
  guards at the top of several `setup.py` handlers, plus `adapter_config.py`'s
  missing lines 67, 116. Unreachable in the fixture-registered service set,
  intentionally uncovered.

  > ⚠ **THE LINE NUMBERS THIS USED TO NAME WERE ALL STALE** (64, 114, 187, 190,
  > 237, 264, 303, 335-338, 344-345, 356, 375, 425). Re-measured 2026-11-08: every
  > one of those sixteen is **covered**. Eight uncovered lines and eight arms of the
  > same SHAPE remain, at entirely different numbers (377, 439, 466, 518, 552, 571,
  > 590, 640). The ruling's *shape* is what still applies; its *list* described
  > nothing. Numbers are deliberately not re-listed here — the shape is the durable
  > fact, and a replacement list would rot the same way.
  >
  > **This is now the only thing standing between `setup.py` and 95%, and it is a
  > decision rather than work.** Everything outside the ruling is closed (83.74% →
  > 94.46%); the file needs **2** more units and the 16 that remain are all inside
  > it. Worth knowing before deciding: the ruling's own wording is about the
  > FIXTURE — "unreachable in the fixture-registered *service set*" — not about
  > reachability in principle. In production `hass.data[DOMAIN][DATA_RUNTIME]` is
  > genuinely absent during a reload or after a failed setup, and one test that
  > calls a handler with the runtime cleared would close all 16 at once. Against
  > that: this campaign has found the "defensive, intentionally uncovered" label
  > wrong more often than right — three of four such claims in `18-platforms.md`
  > carried real failures, and `13-onboarding.md`'s turned out to be the per-map
  > dict bug that returned `False` forever for Dreame. Left to Chris either way.
- **`access_graph.py` (88%)** — missing lines 89-91, 104: defensive guards,
  not yet re-itemized by name this pass.
- **Registered-wrapper closures (trivial)** — `rooms.py` missing line 270 (a
  wrapper/`vol.Required` false-arm the registered service can't reach).
- **`_common.py` (96%)** — missing line 138, a single defensive guard.

Module coverage: `queue.py` 77% (see above), `setup.py` 94%,
`access_graph.py` 88%, `adapter_config.py` 96%, `_common.py` 96%,
`errors.py` 95%, `rooms.py` 98%; `dock.py`, `room_profiles.py`,
`maintenance.py`, and `snapshots.py` are at 100%.

> ⚠ **This list claimed `snapshots.py` was at 100% while the Coverage map above said
> 85%** — the two halves of this document contradicted each other, and the prose half
> was the wrong one. It is 100% as of 2026-11-08 (`SNP-4`, `SNP-6`–`SNP-8`), so the
> sentence is now true, but it was not when it was written. A figure that appears in
> two places in one file is a figure that will disagree with itself; prefer the table.
