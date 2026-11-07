# 03 — Queue — Subsystem Test Map

The queue subsystem turns the enabled-room set into an ordered clean queue: it
resolves room order, applies per-room overrides, and produces the
`queue_room_ids` / `queue_rooms` payload the job pipeline consumes -- and, for a
STEPPED queue, interleaves breaks into that order. Covered by **109 tests across
5 files** (counted 2026-11-07; the previous "78 across 3" predated both
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
