# PhaseRunner — Developer Reference

> **Scope:** Complete implementation reference for `jobs/phase_runner.py` — the
> **strict-order (sequenced) phase execution** subsystem. Every state-machine
> step, watchdog rule, and timing-capture path here is derived directly from the
> source. A developer should be able to re-implement the strict-order runner from
> this document alone.
>
> **Ownership note:** this subsystem was extracted from `core/manager.py` in the
> manager re-bundle. The orchestration now lives entirely in
> `jobs/phase_runner.py` (`class PhaseRunner`). What **stays** on the manager is a
> single 1-line delegator (`maybe_advance_phase`) plus the brand-tunable watchdog
> *timing* (`_phase_timing` + the `_PHASE_*` module constants). If you find a doc
> that attributes the phase machine to `core/manager.py`, this page is the
> correct owner.

---

## 1. Overview

A **path-optimizing brand** (the Roborock S6 is the live example) re-routes a
multi-room batch into whatever order its firmware thinks is fastest, ignoring the
order you dispatched. To honor a strict cleaning order on such a brand, the
framework switches to the **sequenced job model**: one room per *phase*,
dispatched in queue order, each waited on before the next is sent.

`PhaseRunner` owns the two halves of making that work reliably:

1. **The watchdog** — a per-phase state machine (`_run_advanced_phase`) that
   handles the device's nasty post-dock behavior: the S6 finishes a room, docks,
   starts charging, and **ignores** an `app_segment_clean` sent at that instant.
   So each next room is dispatched from a background task that *settles*,
   *dispatches*, *verifies the robot actually started THIS room*, and *retries*
   if not.
2. **Per-phase timing capture** — `_capture_finishing_phase_timing` snapshots
   each finishing phase's room timing from **its own counter slice** before
   advance resets the queue, so finalization can reconstruct per-phase timings
   instead of mis-attributing the whole run to the last phase's room.

**Module:** `custom_components/eufy_vacuum/jobs/phase_runner.py`
**Class:** `PhaseRunner` (constructed once with the core manager, the
bundled-subsystem pattern). The manager builds it as `self.phase_runner` and
reads/writes the same `manager.data["active_jobs"]` store.

> **Strict order is opt-in and brand-gated.** A run only becomes sequenced when
> `strict_order=True` is requested **and** the brand does not natively honor order
> (`honors_clean_order` is False). Eufy, which honors order, builds a single
> atomic phase and never enters this machine — the whole subsystem is inert for
> it. See [06-job-lifecycle](06-job-lifecycle.md) §2 and
> [29-roborock-adapter](29-roborock-adapter.md).

---

## 2. What it owns (and what it doesn't)

| Concern | Owner | Symbol |
|---|---|---|
| Public advance entry point | **PhaseRunner** (manager delegates) | `maybe_advance_phase` |
| Per-phase watchdog state machine | **PhaseRunner** | `_run_advanced_phase` |
| Dispatch a phase's segment + per-room fan | **PhaseRunner** | `_dispatch_active_phase` |
| Verify the device started THIS room | **PhaseRunner** | `_await_phase_started` |
| Release the dispatch-pending guard | **PhaseRunner** | `_clear_phase_dispatch_pending` |
| Coarse "is it cleaning at all" fallback | **PhaseRunner** | `_vacuum_started_cleaning` |
| Per-phase timing/area snapshot | **PhaseRunner** | `_capture_finishing_phase_timing` → `_phase_room_timing` / `_wall_seconds` / `_learned_room_area_m2` |
| Build the per-room phase list | queue engine | `GenericRoomIdsEngine.build_phases` |
| Advance the stored job to the next phase | queue engine | `advance_active_job_phase` |
| Concatenate per-phase timings at finalize | learning | `history_store` finalization |
| **Watchdog TIMING (defaults + brand overrides)** | **`core/manager.py`** | `_phase_timing` + `_PHASE_*` constants |

The timing split is deliberate: the orchestration is the subsystem's job, but the
**brand-tuned defaults** are a core-level surface so an adapter can override any
subset via `dispatch.phase_timing`. `_run_advanced_phase` /
`_await_phase_started` read the resolved timing back through
`self._manager._phase_timing(...)` — see §6.

---

## 3. The sequenced job model (upstream of PhaseRunner)

PhaseRunner consumes a job that was already built as *phased* by the queue
engine. The relevant upstream contract:

- `GenericRoomIdsEngine.build_phases(strict_order=True)` (in
  `queue/dispatch_engines.py`) emits **one single-segment phase per resolved
  room** in queue order instead of one batch phase. Each phase carries its own
  room's `passes`, so per-room passes is honored too. Without `strict_order` it
  returns a single batch phase (`[self.build_payload(...)]`). Atomic engines
  ignore the flag entirely. `RoborockSegmentEngine` is a naming subclass of
  `GenericRoomIdsEngine` and inherits this behavior.
- `build_active_job_state(..., phases=...)` (in `queue/queue_engine.py`) stores
  the ordered phase list plus `current_phase_index` / `phase_count`. When
  `phases is None` (atomic — every adapter today by default) those keys are
  **omitted**, so the stored job is byte-identical to pre-sequencing.
- `advance_active_job_phase(active_job)` returns a **new** job dict swapped to the
  next phase (next `resolved_rooms` / `payload` / `room_count` / `queue_*`,
  per-phase progress reset, `current_phase_index` incremented). It returns
  `None` for an atomic job (no `phases`, or `len(phases) < 2`) or when already on
  the final phase — in both cases the caller finalizes exactly as before.

Two job-record keys that `advance_active_job_phase` sets are central to the
watchdog handoff:

- **`has_observed_active_lifecycle = False`** — the next phase must be observed
  active again before it can finalize, so the just-ended phase's stale completion
  signal can't immediately re-finalize the new phase.
- **`_phase_dispatch_pending`** — set True until the watchdog confirms the device
  actually started THIS room. While pending, the completion listener must not
  finalize/advance on the previous room's lingering dock signals (see §7).

---

## 4. Entry point — `maybe_advance_phase`

```python
await manager.maybe_advance_phase(*, vacuum_entity_id: str, map_id: str) -> bool
```

The manager method is a **1-line delegator** to
`self.phase_runner.maybe_advance_phase(...)`. It is kept on the manager only
because production (`listeners/lifecycle.py`) and the listener tests reference
`manager.maybe_advance_phase`.

The completion hook in `listeners/lifecycle.py` calls it right before it would
finalize a completed phase. Behavior of `PhaseRunner.maybe_advance_phase`:

1. **Capture the finishing phase's timing FIRST** —
   `_capture_finishing_phase_timing(...)` snapshots the just-completed phase's
   room timing from its own counter slice (§5). This must run before
   `advance_active_job_phase` resets the queue, and it also runs for the **final**
   phase (advance returns `None` immediately after, but the capture already ran).
2. Call `advance_active_job_phase(active_job)`.
   - Returns `None` → an atomic job or the final phase → return **`False`** (the
     caller finalizes as today).
   - Returns the advanced dict → stamp `current_room_started_at`, persist it to
     `data["active_jobs"][vacuum_entity_id][map_id]`, then **spawn**
     `_run_advanced_phase(...)` for the new phase index as a background task (not
     awaited, so the completion listener returns promptly). Return **`True`** (the
     caller skips finalization).

**Return contract:** `True` = job advanced to a next phase, caller must skip
finalization; `False` = atomic job or final phase, caller finalizes normally.

---

## 5. Per-phase timing capture

Why this exists: the whole-run counter stream **cannot** be segmented across the
per-room dock trips. The CV/transit segmenter's transit capture breaks on the
intermediate dockings, so running the whole stream against the (single) last-phase
queue would either yield empty `room_timings` or credit the entire run's
battery/area to one room. Instead, **each phase is segmented alone** at the moment
it finishes, while its own counter slice is still intact.

### 5.1 `_capture_finishing_phase_timing`

```python
runner._capture_finishing_phase_timing(vacuum_entity_id, map_id, active_job) -> None
```

- **Atomic jobs (no `phases` list) → no-op.** Out-of-range / already-captured
  phases → no-op (idempotent; the `_timing_end_t` marker is set even for an empty
  capture so it can't re-run).
- **Slice selection:** the phase's slice is the `counter_samples` whose timestamp
  is strictly after the **previous phase's recorded `_timing_end_t`** (or from the
  run start for phase 0). All timestamps come from `_iso_now()` so a lexical
  string compare slices correctly.
- **One room per phase:** the target is `queue_room_ids[0]`; its slug comes from
  `resolved_rooms`.
- **Empty-phase guard:** a real per-room delta needs **≥ 2 samples carrying a
  counter** (`cleaning_time` or `cleaning_area` not `None`). A phase that never
  cleaned (the watchdog gave up, or a stale completion signal) records an
  **empty** timing rather than a phantom room — so finalize reads the run as
  *not-fully-captured* instead of fabricating a room with a learned area.
- **Result** is stashed on the phase as `phases[idx]["room_timing"]` plus
  `phases[idx]["_timing_end_t"]`.

### 5.2 `_phase_room_timing` — within-slice deltas

```python
runner._phase_room_timing(room_id, slug, slice_samples) -> dict
```

One strict-order phase = one room, so **no segmenter is needed**. `cleaning_time`
and `cleaning_area` are **cumulative across the run**, so the per-phase figure is
`last − first` *within the slice*. (Using the segmenter here would report a later
phase's cumulative total, not its own area.) The returned shape:

```python
{
    "room_id": room_id,
    "slug": slug,
    "cleaning_start": <first slice ts>,
    "cleaning_end":   <last slice ts>,
    "cleaning_seconds":      <cleaning_time delta, int>,
    "cleaning_wall_seconds": <wall-clock between first/last ts, or cleaning_seconds>,
    "area_m2":        <cleaning_area delta, rounded 3dp>,
    "battery_delta":  <first − last battery, or None>,
    "boundary": "phase",
}
```

`_wall_seconds(t0, t1)` is a static helper: whole seconds between two ISO
timestamps, best-effort `0` on parse failure.

### 5.3 Area fallback — `_learned_room_area_m2`

A within-phase `cleaning_area` delta of ≈ 0 (a stale/flat sensor through the
phase) is unusable. When `_phase_room_timing` produces `area_m2 <= 0`, the capture
substitutes the room's **learned area** from the map registry
(`maps[...][...][rooms][rid]`, keys `learned_area_m2` then `area_m2`) and tags it
`area_source: "learned_fallback"`. Returns `None` when no learned area is known.

### 5.4 Finalization concat (downstream, in learning)

At finalize, `learning/history_store.py` checks for `active_job_state["phases"]`.
If present, it **concatenates each phase's `room_timing` in phase order** rather
than running the whole counter stream through `_build_transit_blocks`:

- `transitions = []` — inter-phase gaps are dock overhead, not room-to-room
  transit.
- `transit_capture_valid` is True only when **every** phase contributed a
  non-empty timing (`_every_phase_captured`); a single empty phase marks the run
  as not-fully-captured (excluded from learning).
- Atomic jobs leave `phases` absent → the legacy `_build_transit_blocks` path.

See [10-learning-system](10-learning-system.md) for how finalized
`room_timings` feed per-room learned stats.

---

## 6. The watchdog state machine — `_run_advanced_phase`

```python
await runner._run_advanced_phase(
    *, vacuum_entity_id, map_id, phase_index, initial=False
) -> None
```

This is the heart of the subsystem. It runs as a background task — spawned by
`maybe_advance_phase` for an advanced phase, and by `start_selected_rooms` (in
`core/manager.py`) with `initial=True` for phase 0.

The state machine, per phase: **settle → (dispatch) → verify → retry**.

### 6.1 Settle

- Resolve timing via `pt = self._manager._phase_timing(vacuum_entity_id)`.
- **Advanced phase** (`initial=False`): `await asyncio.sleep(settle)`. If the
  phase's target room **is the dock room**
  (`_phase_target_is_dock_room` reads the map's per-room `is_dock_room` flag), the
  settle is extended to `dock_settle_seconds` — the robot is parked + charging
  right on the target, so its post-dock ignore-transient is the longest.
- **Initial phase** (`initial=True`): **skip the settle** — phase 0 was already
  dispatched by `start_selected_rooms`, so the first iteration is verify-only.

### 6.2 The attempt loop (1 .. `max_attempts`)

Each iteration first re-reads the live job and **bails** if the phase is no longer
ours — any of: job gone, `status != "started"`, `current_phase_index != phase_index`,
or `_cancel_in_flight` set. (`async_cancel` sets `_cancel_in_flight` *before* the
status flips, so the watchdog stops before it can re-dispatch during the
return-to-base window.)

Then:

- **Dispatch** via `_dispatch_active_phase(...)` — **except** on the initial
  phase's first attempt (its first send already happened at job start; attempt 1 is
  verify-only, and a re-dispatch only happens on a retry if the device ignored it).
- **Verify** via `await _await_phase_started(...)`:
  - **True** → the device started THIS room → call
    `_clear_phase_dispatch_pending(...)` and **return** (phase under way).
  - **False** → the device ignored the dispatch / is still docked / is still
    finishing the previous room → loop to the next attempt (re-dispatch).

After `max_attempts` with no start, the loop logs a warning and **leaves the run
stalled** — recoverable by the user via *Cancel Run*, rather than silently hung.
**`max_attempts` is the per-phase watchdog.**

### 6.3 `_dispatch_active_phase`

```python
await runner._dispatch_active_phase(*, vacuum_entity_id, map_id, job, attempt=1) -> None
```

1. Apply this phase's **per-room live settings (fan)** *before* the dispatch
   (`manager.active_job.apply_per_room_live_settings_awaited(...)`) so the room
   starts at its own fan value with no `current_room` poll lag.
2. Live-resolve the segment ids by slug per phase
   (`manager._resolve_live_dispatch_payload(...)`) so a re-segment between rooms
   can't clean the wrong room (no-op without `dispatch.resolve_live_ids_by_slug`).
3. Dispatch via `manager._dispatch_clean_payload(...)`.
4. Log at **INFO** (so a strict-order run is diagnosable without debug): the exact
   re-dispatched payload + attempt number. An empty segment list = the next room
   was skipped (e.g. a slug that didn't resolve to a live id).

### 6.4 `_await_phase_started` — the verification logic

```python
await runner._await_phase_started(*, vacuum_entity_id, map_id, phase_index) -> bool
```

This is where an earlier naive check (the job-active binary / "is it cleaning at
all") **false-passed**: the device's `inCleaning` flag stays on across the whole
job, so a clean it *ignored* at the dock looked like success and the watchdog
never retried (only ~1 room in 4 actually fired). The strong signal is the
brand's **native current-room** matching the phase's target *while actually
cleaning, sustained*.

- **Native path** (adapter declares `entities.active_cleaning_target`):
  - Accumulates `cleaning_in_target` seconds when **all** hold:
    `vacuum.state == "cleaning"` (rules out docked-in-the-target-room),
    the native signal (`manager.active_job.native_current_room_target_id(...)`) is
    present and `== job["current_room_id"]`.
  - Confirms (**True**) once `cleaning_in_target >= confirm_seconds`. The signal
    dips in and out, so a dip just doesn't add to the tally — we don't require
    strict continuity.
  - Bounds an attempt by **no-progress (idle) time**, not a fixed overall window:
    a long cross-room transit merely delays when the tally starts, so it can't
    falsely fail a device genuinely on its way; a device that never reaches the
    room accrues idle and retries promptly.
- **Idle-exit weak confirm:** once `idle >= verify_seconds`, return
  `cleaning_in_target > 0`. If we observed *genuine* cleaning of the target at any
  point (the tally only accrues while cleaning AND on-target), the device started
  the room and has since finished/docked — a small room that completed in under
  `confirm_seconds`. Treat that as **confirmed**, because re-dispatching an
  already-cleaned room is ignored by the device and would stall the phase forever.
  Only a true no-show (never cleaned the target) returns **False** to retry.
- **No-native fallback:** brands with no native current-room signal fall back to
  the coarse `_vacuum_started_cleaning(...)` (immediate, unchanged).
- **Early-out (True):** if the phase advanced / finalized / paused or
  `_cancel_in_flight` is set mid-poll, return True (nothing to retry).

### 6.5 `_vacuum_started_cleaning` (coarse fallback)

True when the vacuum entity reports `cleaning`, **or** the adapter's job-active
binary (`entities.job_active` — the device `inCleaning` flag) is on. Used only by
the no-native fallback in `_await_phase_started`.

### 6.6 `_clear_phase_dispatch_pending`

Once the watchdog confirms the phase's room actually started, this clears
`_phase_dispatch_pending` so the room's real completion can finalize/advance
normally. It only clears when the job is **still on this exact phase** (a later
advance owns its own pending flag), then best-effort persists via
`manager._async_save_logged()`.

---

## 7. The completion-gate handoff

The watchdog cooperates with the completion listener
(`listeners/lifecycle.py`) through `_phase_dispatch_pending`:

```text
phase completes
  → should_finalize_completed = True
  → if active_job["_phase_dispatch_pending"]:  should_finalize_completed = False   # (A)
  → if not should_finalize_completed: continue
  → if await manager.maybe_advance_phase(...):  continue   # (B) advanced — skip finalize
  → finalize_learning_for_active_job(...)                  # (C) atomic / final phase
```

- **(A)** A Roborock sits docked + charging *between* phases — precisely its
  completion signal. While the next phase's dispatch is still pending (the
  watchdog hasn't confirmed it started), the prior room's lingering dock signal
  must not finalize the next room before it ever starts. No-op for non-sequenced
  jobs (the flag is only set on a phase advance).
- **(B)** A completed non-final phase advances + re-dispatches instead of
  finalizing (this is `maybe_advance_phase` returning True).
- **(C)** Atomic jobs — every adapter today by default — and the final phase fall
  through to normal finalization.

See [06-job-lifecycle](06-job-lifecycle.md) §6–§7 for the full end-of-job flow.

---

## 8. Watchdog timing — the manager seam

The watchdog timing is **deliberately not owned by this subsystem**. It lives on
`core/manager.py` so it is a brand-tunable surface:

- **In-core defaults** are the `_PHASE_*` module constants in `core/manager.py`:

  | Constant | Default | Meaning |
  |---|---|---|
  | `_PHASE_SETTLE_SECONDS` | `10` | Post-dock settle before the first dispatch of an advanced phase. |
  | `_PHASE_DOCK_SETTLE_SECONDS` | `45` | Longer settle when the target room **is** the dock room (worst-case ignore-transient). |
  | `_PHASE_VERIFY_SECONDS` | `90` | No-progress (idle) budget before an attempt gives up and re-dispatches. |
  | `_PHASE_CONFIRM_SECONDS` | `45` | Cumulative cleaning-of-target seconds required to release the pending guard. |
  | `_PHASE_POLL_SECONDS` | `5` | How often the verify loop re-checks. |
  | `_PHASE_MAX_ATTEMPTS` | `3` | Per-phase watchdog cap; after this the run is left stalled. |

- **The resolver** is `core/manager.py::_phase_timing(vacuum_entity_id)`: it
  merges the adapter's `dispatch.phase_timing` overrides over the `_PHASE_*`
  defaults, casting each declared value to the default's type. A brand whose
  post-dock transient differs declares its own; anything omitted falls back to the
  default (byte-identical). Defaults are read **live** per call so the tests'
  module-constant monkeypatching still applies.

`PhaseRunner` reads this single resolver — never the constants directly — via
`self._manager._phase_timing(...)` inside `_run_advanced_phase` and
`_await_phase_started`.

The Roborock S6 declares its own `dispatch.phase_timing`
(`adapters/roborock/adapter.py`), lowering `confirm_seconds` to `15` (a sub-15s
room is rare on the S6; the idle-exit weak-confirm backstops anything faster) and
otherwise matching the defaults. Eufy declares nothing → fully default → inert.
See
[22-adapter-config-reference §dispatch.phase_timing](22-adapter-config-reference.md#dispatchphase_timing--strict-order-phase-watchdog-timing).

---

## 9. Integration points

| Caller | Method | When |
|---|---|---|
| `listeners/lifecycle.py` (completion hook) | `manager.maybe_advance_phase()` → `PhaseRunner.maybe_advance_phase()` | A phase's room set finished; decide advance vs finalize |
| `core/manager.py::start_selected_rooms` | `phase_runner._run_advanced_phase(..., initial=True)` | A sequenced job starts (verify phase 0) |
| `PhaseRunner.maybe_advance_phase` | `phase_runner._run_advanced_phase(...)` | An advanced phase is dispatched |
| `queue/dispatch_engines.py` | `build_phases(strict_order=True)` | Build the one-room-per-phase list (upstream) |
| `queue/queue_engine.py` | `advance_active_job_phase()` | Swap the stored job to the next phase |
| `learning/history_store.py` | concat `phases[*]["room_timing"]` | Finalize per-phase timings into the run record |
| `core/manager.py::_phase_timing` | (read by the watchdog) | Resolve brand timing overrides |

---

## 10. Edge cases & invariants

- **Atomic jobs are fully inert.** No `phases` key → `maybe_advance_phase` returns
  False, `_capture_finishing_phase_timing` no-ops, the watchdog is never spawned.
  Eufy (honors order) never enters this machine.
- **Cancellation is race-safe.** `async_cancel` sets `_cancel_in_flight` *before*
  the status flips; both `_run_advanced_phase` and `_await_phase_started` check it
  each iteration and bail, so the watchdog can't re-dispatch during return-to-base.
- **Idempotent capture.** `_capture_finishing_phase_timing` writes `_timing_end_t`
  even for an empty capture, so it never double-counts or re-runs a phase.
- **A stalled run is recoverable, never silently hung.** After `max_attempts` the
  watchdog stops and logs; the user recovers via Cancel Run.
- **The final phase's timing is still captured.** `maybe_advance_phase` captures
  before `advance_active_job_phase` returns `None`, so the last room is recorded.

---

## Cross-links

- [06-job-lifecycle](06-job-lifecycle.md) — full job start → finalize flow; the
  completion gate that calls `maybe_advance_phase`.
- [07-queue-engine](07-queue-engine.md) — `build_phases` / `build_active_job_state`
  / `advance_active_job_phase` and the dispatch engines.
- [29-roborock-adapter](29-roborock-adapter.md) — the live path-optimizing brand;
  `honors_clean_order`, native current-room signal, `per_room_live_settings`.
- [10-learning-system](10-learning-system.md) — how concatenated per-phase
  `room_timings` feed learned per-room stats.
- [22-adapter-config-reference §dispatch.phase_timing](22-adapter-config-reference.md#dispatchphase_timing--strict-order-phase-watchdog-timing)
  — the brand override block for the watchdog timing.
