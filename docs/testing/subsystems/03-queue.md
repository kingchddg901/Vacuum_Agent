# 03 — Queue — Subsystem Test Map

The queue subsystem turns the enabled-room set into an ordered clean queue: it
resolves room order, applies per-room overrides, and produces the
`queue_room_ids` / `queue_rooms` payload the job pipeline consumes -- and, for a
STEPPED queue, interleaves breaks into that order. Covered by **78 tests across 3 files** (counted 2026-11-07; the previous "78 across 3" predated both
`test_dispatch_settings_write.py` and `test_manager_queue_breaks.py`, which the
body already described and listed respectively).

Source: `custom_components/eufy_vacuum/queue/`
Architecture reference: [05 — While a Run Is Live](../../dev/05-run-live.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `queue_engine.py` | 175 | 95% | `test_queue_engine.py` (unit), `test_manager_queue.py` | unit + int | clean |
| `dispatch_engines.py` | 98 | 95% | `test_dispatch_engines.py` (unit) | unit | clean |
| `core/manager.py` (breaks only) | -- | -- | `test_manager_queue_breaks.py` | int | clean |

(The `build_queue` / `clear_queue` service surface is in
[17 — services](17-services.md) via `test_services_queue.py`.)

---

## What's tested

- **Pure ordering** (unit) — the queue-engine builder: ordering by `order`,
  enabled-only inclusion, override merge, and the empty-input fallback.
- **Manager integration** — `build_queue` / `get_queue_state` / `clear_queue`
  against the real manager with seeded managed rooms; the queue payload shape and
  the round-trip through `data["queue"]`.

- **Bulk per-room settings write** (integration) — `test_dispatch_settings_write.py`
  covers the third pre-dispatch shape (`dispatch/manager.py::_run_settings_write`),
  distinct from `global_pre_calls` and `per_room_live_settings`: a brand whose
  per-room settings are persistent device state (Dreame) fires ONE
  `vacuum_set_custom_cleaning` with index-aligned INT arrays over the queued rooms
  while parked, just before a bare segment dispatch (the saved store wins over the
  clean payload). Asserts array alignment, `value_maps` application, the filler for
  empty/unmapped fields, gate-entity gating, the `[1,3]`/`[1,32]` clamps, ordering
  before the global pre-calls, and best-effort-loud failure (logs, never raises).
  No-op for every brand that does not declare `dispatch.settings_write`.

- **Slug to live segment ids** (integration) — `test_dispatch_live_ids.py` (`LID-1`..`LID-10`).
  For brands whose segment ids renumber on re-segment, the framework re-resolves each
  target room's slug to its CURRENT id just before sending, so a stored id never cleans
  the wrong room. `LID-10` closes the no-rooms-field early return: an adapter can set
  `resolve_live_ids_by_slug` and still build a payload with nothing to remap (a zone or
  whole-house command), and the guard returns before any service call.

- **Global fan/water pre-calls** (integration) — `test_dispatch_global_precall.py`
  (`GPC-1`..`GPC-24`). `GPC-23` and `GPC-24` were added 2026-11-07 with the last two
  reachable uncovered statements in `dispatch/manager.py`. Both DROP a pre-call rather
  than emit a wrong one, which is the safety polarity of the whole path: these calls set
  DEVICE-GLOBAL fan and water before a run, so a guessed value reaches every room in the
  batch including the dry ones. `GPC-23` is parametrised over all five terms of the
  declaration guard's conjunction — a partial guard reads as complete, and losing one
  term leaves four of five shapes passing. `GPC-24` is the case where the safest-water
  policy has nothing rankable to choose from: it pushes NOTHING, which only an assertion
  can distinguish from `GPC-6b`'s "chose off", since both batches are all-vacuum.

#### The three statements that stay uncovered, and why they were not chased

`dispatch/manager.py` sits at **98%** with three uncovered statements (705-706, 709-710),
all inside the slug→live-id loop, plus five partial branches in the zone-restore path.
The three are **double-guards over a contract `rooms/room_discovery.py` already
enforces**: it coerces `room_id = int(raw_id)` under its own `except/continue`, skips a
row whose name is blank or slugifies to empty, dedupes room ids, and runs a
disambiguation pass that suffixes any colliding slug with `_r{room_id}`. So a blank slug,
a duplicate slug and a non-coercible id cannot arrive.

> **Two tests for them were written, PASSED, and were deleted.** The producer's
> disambiguation renamed the duplicate slug and its own `int()` dropped the unusable id,
> so both tests asserted a true thing for a reason other than the one they named —
> coverage is what exposed it, because the lines stayed missed while the tests went
> green. Reaching those guards needs a fabricated producer, which tests the fake. The
> guards are kept (this function rewrites the wire payload moments before dispatch, and
> its failure mode is a plausible segment list rather than an exception) and the
> reasoning now sits at the site.

#### The zone converter — `zone_dispatch.py` at 100%

`tests/unit/test_zone_dispatch.py` (`ZDM-*`, `ZPT-*`, `DGT-*`) covers the
normalized→device-mm affine: pure maths, no HA. `ZDM-10`..`ZDM-14` and `ZPT-4`/`ZPT-5`
closed the last twelve statements on 2026-11-07, taking the module to **100% statements
and branches**.

**Eleven of those twelve cannot be reached through either production caller**, measured
before they were written: `services/job_control.py::_ZONE_RECT_SCHEMA` is
`vol.All([vol.Coerce(float)], vol.Length(min=4, max=4))`, `_GOTO_SCHEMA` coerces each
element to float *and* range-checks 0..1 at length 2, and
`map_source_runtime.correspondences_from_mapdata` returns clean 4-tuples, skipping a
corner that projects out of grid. They are tested anyway because this module is a
standalone converter whose docstrings state a return contract four times over ("or
`None`", "caller MUST refuse to dispatch"), and the schema that currently excludes the
bad shapes is a separate layer a new caller would not pass through. That is a different
case from the same sweep's slug/id guards above, which were one internal stage
re-validating the previous one — those stayed uncovered.

`ZPT-4` is the exception and the one that matters: the round-trip residual check is not
an input-shape guard but the module's whole safety contract, and it fires on real,
well-formed geometry that simply is not the affine assumed. `ZDM-5` pinned it for rects;
go-to had no equivalent, and the consequence there is worse — a wrong rect cleans the
wrong area, a wrong point drives the robot to the wrong place.

#### The zone restore path, and the two arcs left

`test_dispatch_zone_clean.py` (`ZC-*`, `ZC-DR-*`, `GOTO-DR-*`) drives the real
gate-flip → set → readback → execute → restore sequence. `ZC-DR-13` closed both arms of
`gate_prior == "on"`: the suite had only ever driven an install whose
customized-cleaning switch was ON, so neither the no-flip nor the no-restore path ran.
A user who leaves that switch off is an ordinary install, and the negative assertions
are the test — re-enabling a gate the user deliberately left off would change their
device configuration as a side effect of one zone clean.

`GPC-25` closed the last branch arc, the off-fallback walk finding no candidate. It
**pins today's behaviour and names a gap** rather than changing it: with no rank member
among the select's options, the call still goes out carrying `"off"` to a select that
has just reported it has no `"off"`, and HA logs rather than raises — so the fallback
built to avoid a silent no-op degrades into one. Changing that is a safety-posture
decision on a hardware-facing path, not a test fix.

Two arcs remain in `dispatch/manager.py` (`314->exit`, `315->318`), both idempotency on
the completion callback, classified at the site. `315->318` is not reachable through
`async_track_state_change_event` at all — the unsub removes the listener, so the
callback cannot fire twice; it guards a re-entrant invocation this subscription does not
produce.

  **The malformed-declaration guards (`SW-14..SW-18`)** cover the other half: a
  mistake in an adapter's own `settings_write` block rather than bad device data.
  They earn tests rather than pragmas because the block is hand-authored (ours today,
  a contributor's tomorrow) and the damage is not local — the call carries
  index-aligned arrays into an object selector that rejects the **whole call** if one
  column is the wrong type or length, so a guard that let a bad column through would
  not degrade one field, it would lose the entire per-room write for the run. Each
  guard therefore drops exactly one column or refuses the call outright:

  | | guard | on a bad declaration |
  |---|---|---|
  | `SW-14` | no `domain`/`service` | refuse before building anything |
  | `SW-15` | a non-numeric `room_id` | abort + ERROR — the segment column *is* the alignment, so there is no per-room degradation available |
  | `SW-16` | a field with no `wire` | skip it, and keep emitting the ones after it |
  | `SW-17` | a `wire` with no `canonical` and no `constant` | omit the column; a filler is a real value the device would store |
  | `SW-18` | a clamped value that will not coerce | filler for *that room only*, so one typo cannot cost the others their write |

> **`SW-14` cannot be written as `calls == []`**, and the first draft was exactly
> that. Delete the `domain`/`service` guard and `async_call(None, None, ...)` raises,
> which the function's own best-effort-loud `except` swallows into an ERROR log — so
> no call is recorded either way and the assertion passes with the guard gone. It also
> asserts that log is **absent**, which is the only thing separating "refused cleanly"
> from "attempted it and swallowed the failure". Ablation is what surfaced this.

> **The `SW-` prefix is shared by three unrelated files** — this one (`SW-1..SW-9b`),
> `test_setup_workflow.py` (`SW-10..SW-13`) and `test_stuck_watch.py`
> (`SW-10..SW-11`), the latter two already colliding with each other. The new ids
> start at `SW-14`, the lowest free repo-wide, rather than adding a third claim on
> `SW-10`; that is why the numbering here jumps.

---

## How it's tested

The pure builder is exercised in isolation in `test_queue_engine.py` (no `hass`).
The manager-level path uses the `manager` fixture + `setup_map(...)` to seed
rooms, then asserts the resolved queue.

---

## Known gaps

`queue_engine.py` (95%) — the remaining uncovered lines are defensive:

- the `typing_extensions` `TypedDict` import fallback (lines 9-10), unreachable on
  the shipped Python (3.14 has `typing.TypedDict`);
- the `room_id <= 0` skip guard in `build_room_clean_payload` (line 264);
- the `elif queue_room_ids:` `current_room_id` fallback in `build_active_job_state`
  (lines 397-398), reached only when `resolved_rooms` is empty but the queue ids
  are present.

The two **capability-gated per-room write branches** in `build_room_clean_payload`
— `edge_mopping` (line 296, under `supports_edge` + mop mode) and `path_type`
(line 299, under `supports_path`) — are now covered by `test_dispatch_engines.py`'s
DE-11b (`test_edge_and_path_per_room_writes_when_caps_enabled`), which declares
edge/path as real wire fields and asserts both per-room writes land on the wire.
No shipped adapter declares these fields, so DE-11b is the only path that drives
them.

### Queue breaks -- the stepped queue (`test_manager_queue_breaks.py`, QB-1..16)

A break (`wait`, `charge_wait`) or an inserted `zone` turns the flat queue into a
STEPPED one. `core/manager.py::get_queue_steps` derives that plan on every read by
interleaving `_map_queue_breaks` into the enabled-room order -- a break with
`after_index` K sits after the K-th room -- and returns it in the same shape as a
stored run-profile steps list, which is what lets the card preview a plan it has not
run. QB-1..14 cover add / remove / clear / set, the interleave, the `after_index`
clamp to an interior slot, trailing zones, and the raw `breaks` passthrough.

**QB-15 / QB-16 cover the self-heal, and they exist because the plan is derived on
READ while the breaks are stored on WRITE.** `profiles.normalize_run_profile_steps`
is not total: it raises `ServiceValidationError` when the first or last of 2+ steps
is a break. Both write paths clamp `after_index` to an interior slot, so the only way
to reach that raise is state that became invalid AFTER it was written -- disable a
room and the break in front of it is stranded at the edge. Without the catch in
`get_queue_steps` the symptom is not a lost break but a queue that refuses to load
at all, which is the failure the normaliser's own docstring describes.

- **QB-15** -- two rooms with an interior wait, then the first room disabled: the
  derived plan heals to a single `room_group`, the stored break SURVIVES, and
  re-enabling the room restores the original three-step plan. The non-destructive
  half is the part worth pinning -- a heal that deleted the break would also pass the
  first assertion.
- **QB-16** -- every room disabled, so the room loop never runs and the drain emits
  the breaks alone: the plan heals to `[]` rather than raising.

Two measurements recorded with them, both from the ablation rather than from reading
the code:

1. **The heal has two arms and they are not separable.** Deleting the LEADING
   while-loop reddens nothing. `steps[0]` can only be a break when there are no
   enabled rooms at all -- a break with `after_index >= 1` always emits after at
   least one `room_group`, and `_map_queue_breaks` filters `after_index: 0` out
   entirely -- and in that case every entry is a break, which the TRAILING loop
   drains from the right. The leading arm is therefore executed and covered, but no
   input can prove it; deleting the trailing loop reddens QB-15 alone, for the
   mirror-image reason. Only removing the catch reddens both tests. Left in place
   and documented rather than deleted: it is what makes the dropped breaks log as
   "leading" rather than "trailing", and whether to drop it is a behaviour call.
2. **`after_index: 0` is not a route to the leading arm**, which is what the coverage
   triage proposed. `_map_queue_breaks` filters on `after >= 1`, so a stored 0 never
   reaches the steps loop.

---

`dispatch_engines.py` (95%) leaves line 377 — the `if cfg is None: continue` skip
in `DreameSegmentEngine`'s array transpose, the path where a canonical field is
simply not declared in `room_fields` (Dreame omits most). Defensive; the declared
and `field_name: None` cases are both covered.
