# 04 — Listeners Package

> **Scope:** Complete implementation reference for `listeners/`. Every module's register/remove surface, event triggers, vocabulary dependencies, timers, and side effects are derived directly from the source. A developer should be able to re-implement the listeners package from this document alone.

---

## 1. Overview

The `listeners/` package contains eight listener modules that register HA event and state-change subscriptions at integration load time: `lifecycle`, `dock_events`, `path_blockers`, `pause_timeout`, `job_progress`, `job_metrics`, `discovery`, and `pose_sampler`. (`_common.py` is a shared helper module, not a listener — see §2.) Each listener module has a consistent two-function public surface:

```python
register(hass: HomeAssistant) -> None
remove(hass: HomeAssistant) -> None
```

There is no `manager` parameter — each module resolves the manager from
`hass.data[DOMAIN][DATA_RUNTIME]` itself. Unsubscribe callables are stored under
a module-specific key in `hass.data[DOMAIN]` (or in module-level dicts).
`remove()` cancels all subscriptions registered by that module.

All listeners are wired from `__init__.py` `async_setup_entry` (each module's
`register(hass)`) and torn down from `async_unload_entry` (each module's
`remove(hass)`).

---

## 2. Shared Helpers (`_common.py`)

`listeners/_common.py` provides utilities used across multiple listener modules.

### 2.1 Adapter vocabulary helpers

```python
get_adapter_vocab(vacuum_entity_id, section, key, fallback) -> frozenset
```
Reads a list/set value from the adapter config and returns it as a `frozenset`. Returns the fallback frozenset only when the value is **missing or not a list/set/frozenset** — an explicitly **empty** list yields an empty frozenset (not the fallback).

```python
get_adapter_value(vacuum_entity_id, *path, fallback) -> Any
```
Traverses nested adapter config dicts by the given key path. Returns fallback on any missing key or type error. Delegates to `adapters/registry.py`'s own `get_adapter_value` (COMMON-5 — one lookup implementation, not two independently-drifting copies; a fix or semantic change there now reaches every listener that routes through this module).

```python
is_dock_trigger_edge(old_state_value, new_state_value, trigger_vocabulary) -> bool
```
The shared "is this a genuine dock-event edge" test (RP-038/LIFE-3 — one definition for both `dock_events.py`'s `_handle_dock_event` and `lifecycle.py`'s inline mop-wash detector). Three refusals, checked in order — any one means "not an edge": (1) `new_state_value` is `None`; (2) `old_state_value` is not a real, previously-known value — missing entirely (`None`, e.g. HA restart or first sighting) or currently `unavailable`/`unknown` (a fresh sighting after a restart must not count as a new dock cycle, REG-1/GUARD-3); (3) the normalized `old`/`new` values are equal (dedup). Otherwise: an edge iff the normalized `new_state_value` is in `trigger_vocabulary`. Values are compared case-insensitively after stripping.

### 2.2 Entity watch helpers

```python
get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]
```
Returns the full list of entities the lifecycle listener watches for one vacuum:
- `vacuum_entity_id` itself
- `entities.task_status`
- `entities.dock_status`
- `entities.active_cleaning_target`
- `entities.active_map`
- `entities.job_active`

Every declared-entity item (all but `vacuum_entity_id`) is only included when the adapter declares it. `entities.job_active` is the recharge-resume binary sensor (it stays on through a mid-job recharge dock); watching it ensures its clear at the true finish re-triggers finalization. It is absent for brands that don't declare it (e.g. Eufy).

```python
is_job_active(hass, vacuum_entity_id, *, unavailable_is_active=False) -> bool
```
The job-active binary probe. Returns `True` when the adapter declares `entities.job_active` and that binary sensor currently reads `"on"`; returns `False` for brands that don't declare it (e.g. Eufy), making every caller a no-op for them. When `unavailable_is_active=True`, an existing-but-`unavailable`/`unknown` entity counts as active (used by the recharge-resume guard so a transient cloud blip during a mid-job recharge dock doesn't finalize early). Used for the recharge-resume completion guard and strict-order completion gating (§3.4).

```python
completed_finalize_signals(hass, vacuum_entity_id) -> dict
```
Reads current state and returns a **4-key** snapshot used in completion checks: `vacuum_state`, `task_status`, `dock_status`, `active_target` (each `.strip().lower()`ed; `""` for absent/unavailable). Note it is a **subset** — `active_map` and `job_active` are watched but not in this dict.

```python
completion_secondary_satisfied(vacuum_entity_id, completion_signals, clear_sentinels) -> bool
```
The adapter-driven secondary-clear check used in the completion gate (§3.4). When the brand declares `completion.require_job_active_clear` (Roborock) **and actually declares `entities.job_active`** (RP-033/COMMON-2 — the flag names the entity supplying the real signal; a config that sets the flag without declaring the entity used to short-circuit to `True` unconditionally with nothing backing it, and registration now warns on this combination via `adapters/registry.py._warn_completion_gate_orphan`), the sentinel check is bypassed (returns `True`) — the job-active binary clearing is the completion signal instead, enforced separately by `is_job_active`. Without `entities.job_active` declared, it falls through to the default sentinel check below instead (behaves as if the flag were never set). Otherwise (default, Eufy) it requires the snapshot's `active_target` to read one of `clear_sentinels`.

### 2.3 Event payload builders

```python
job_finished_event_data(*, vacuum_entity_id, map_id, finalize_result: dict | None) -> dict
```
Builds the payload fired with every `eufy_vacuum_job_finished` event — **11 keys** (sourced from `finalize_result` → `completed_job.outcome` / `.job`): `vacuum_entity_id`, `map_id`, `job_id`, `status`, `reason_detail`, `used_for_learning`, `finalized_at`, `room_count`, `duration_minutes`, `actual_cleaning_minutes`, `job_path`.

```python
run_incomplete_event_data(*, vacuum_entity_id, finalize_result: dict | None) -> dict | None
```
Builds the `eufy_vacuum_run_incomplete` payload — but **returns `None` unless** `finalize_result`'s `incomplete_run_log.missed_room_ids` is non-empty (nothing was left uncleaned → no event). The 5-key payload (no `map_id`): `vacuum_entity_id`, `job_id`, `outcome_status`, `missed_room_ids`, `missed_rooms`. Fired from the `cancel_and_event` path (§5) and both reaps (§6).

---

## 3. Lifecycle Listener (`lifecycle.py`)

Watches all lifecycle-watch entities across all managed vacuums. Drives job start/completion detection.

**Module:** `listeners/lifecycle.py`

### 3.1 Constants

| Constant | Value | Description |
|---|---|---|
| `_ACTIVE_LIFECYCLE_STATES` | `{"active_job_running", "mid_job_service"}` | lifecycle_state values (from evaluate_job_lifecycle) that count as "active lifecycle observed" |
| `_DEFAULT_COMPLETION_TASK_STATUS` | `"completed"` | Default task_status string signalling job done |
| `_DEFAULT_CLEAR_SENTINELS` | `frozenset({"", "unknown", "unavailable", "none", "null"})` | Default active_cleaning_target values that indicate target cleared |

### 3.2 What it watches

`async_track_state_change_event` on every entity returned by `get_lifecycle_watch_entities()` for every managed vacuum. Every spawned `_process()` task is tracked in `hass.data[DOMAIN]["_job_lifecycle_tasks"]` and cancelled by `remove(hass)` (RP-039/RF-16 — unload used to cancel only the state-change-event subscription, leaving an in-flight `_process()` task free to keep running — and possibly finalize a job / write manager state — against a torn-down `hass`).

### 3.3 Processing pipeline

On each state change, the `_process()` coroutine first calls
`manager.maybe_handle_external_run(vacuum_entity_id=...)` **per matched
vacuum, before the per-map loop below** — an app-started run has no dispatched
job, so it would never be seen by the per-map loop, which only looks at maps
carrying a `started`/`paused` active job (see the External-run detection note
below). Then, for each map with a `started`/`paused` job, it runs:

1. `record_active_job_transition(vacuum_entity_id, new_state)` — records state machine transitions.
2. `resolve_mid_job_recharge_resumed(...)` **then** `update_active_job_recharge_observation(...)` (RP-012/RF-31, A4-AJ-1/TRK-2 — a recharge that has ENDED is resolved first, because this tick can observe a charging state that differs from the tick that set the observed flag; the resolver is where the recharge count increments and the sampler resumes — see [06 §5](06-job-lifecycle.md)).
3. If the adapter's `dock_status` entity changed: mop-wash edge detection via the shared `is_dock_trigger_edge` (§2.1) against `dock_events.triggers.last_mop_wash` (LIFE-3 — adapter-driven only, no hardcoded Eufy-literal fallback; an adapter that declares no trigger vocabulary gets no wash detection), then `update_active_job_mop_wash_observation()`.
4. `observe_job_active(...)` (`job_active_signal.py`) — the ISSUE #46 passive observation trace: emits a decision-log record of the raw "recharge dock or finish?" inputs beside the job-active binary's own reading. Strictly passive; no gate consults it. Placed above the arming gate so a run that never arms is still traced.
5. `record_active_lifecycle_observed(vacuum_entity_id)` — sets `has_observed_active_lifecycle = True` when task_status enters an active lifecycle state. For brands declaring `completion.require_job_active_clear`, arming additionally requires `is_job_active(hass, vacuum_entity_id)` (strict `"on"`, so an indeterminate binary at start can't arm the flag — without this a batch job created against a stale previous-run `charging` state would arm at t=0 and finalize in ~1 s).
6. Completion check.

### 3.4 Completion check

Job is considered complete when **all three** conditions hold simultaneously:

```
task_status   == completion_task_status_value  (from adapter "completion.task_status_value" or "completed")
active_target in clear_sentinels               (from adapter "completion.secondary_clear_sentinels")
has_observed_active_lifecycle == True          (set when task_status entered an active lifecycle state)
```

Even when all three hold, finalization is then suppressed by three guards:

- **Recharge-resume guard.** If `is_job_active(hass, vacuum_entity_id, unavailable_is_active=True)` is `True`, finalization is skipped. A brand may dock and report `task_status=charging` mid-job to recharge, then resume; while the job-active binary stays on (or transiently `unavailable`/`unknown`), the resumed half stays the same job. No-op for brands without `entities.job_active` (e.g. Eufy).
- **Strict-order dispatch guard.** If the active job has `_phase_dispatch_pending` set (a just-advanced sequenced phase whose watchdog hasn't yet confirmed the device started the new room), finalization is skipped so the prior room's lingering completion signals don't finalize the next phase before it starts. No-op for non-sequenced jobs.
- **Cancel-in-flight guard (RP-010/RF-06).** If `_cancel_in_flight` is set, the cancel path owns finalization — its own return-to-base dock reads as completion here and would otherwise race the cancel's finalize.

A sequenced (multi-phase) job that passes the guards does **not** finalize: `manager.maybe_advance_phase()` advances to the next phase (re-dispatch) and returns `True`, skipping finalization. Atomic jobs — and a sequenced job's final phase — return `False` and fall through to the finalization steps below.

On completion:
1. `finalize_learning_for_active_job(vacuum_entity_id)` — awaited directly (async), wrapped so a raise doesn't kill the pass.
2. **Branch on `finalize_result_succeeded(result)`** (RP-002/RF-01 — a refusal dict `{"finalized": False, "reason": ...}` is also not-`None`; re-running the terminal steps on it would fire an all-null duplicate event — see [06-job-lifecycle §6a](06-job-lifecycle.md)):
   - **Succeeded** → `mark_active_job_finalized(...)` (closes the slot; also releases the mapping tracker's hold — TRK-1) → fires `eufy_vacuum_job_finished` with `job_finished_event_data()` → if the completed job had a mop room and the adapter allows it (`post_job_wash_amendment.enabled`, default `True`): `register_post_job_water_amendment()` with the adapter's `debounce_seconds` (default 60) / `timeout_seconds` (default 180).
   - **Raised** → `mark_active_job_finalized(finalize_result=None)` — the slot and the tracker hold can never strand, but no event fires and no summary is fabricated.
   - **Refused** (`already_finalized` / `finalize_in_flight` / `no_active_job_record`) → nothing; the entrant that actually succeeded owns the terminal steps.

### 3.5 MappingTracker integration

- On first active lifecycle observation: `MappingTracker.start_job()` — a **plain synchronous call** (TRK-7: it is in-memory bookkeeping — a confidence-state reset + an `_active_job` entry — with no disk I/O, so the old executor hop was pure overhead), scoped to the job's own rooms (`queue_room_ids`-filtered; falls back to all rooms when the job has none, so a single-room job always takes the unconditional single-room path).
- On job finalization: the tracker's hold is released by `mark_active_job_finalized` itself (TRK-1 — the terminal chokepoint every path reaches: cancel, strand, success; this also may flush a confidence-cleared held room first — TRK-4 — which fires an HA event and so must run on the event loop, not from an executor thread). See [06-job-lifecycle §9](06-job-lifecycle.md).

---

> **External-run detection.** Before the per-map internal loop, the lifecycle
> listener calls `manager.maybe_handle_external_run()` — a vacuum cleaning with
> no dispatched job is an app-started run, opened as a `status="external"`
> capture slot and finalized to a pending review record when it docks. See
> [28-external-run-ingestion](28-external-run-ingestion.md).

## 4. Dock Events Listener (`dock_events.py`)

Watches dock status entities and records dock cycle events via `DockManager`.

**Module:** `listeners/dock_events.py`

Builds `watched: dict[str, str]` mapping dock_entity_id → vacuum_entity_id — only for vacuums whose adapter sets **`dock_events.enabled`** (REG-4; schema default `False` — a brand that declares `dock_status` but opts out gets no listener).

On dock_status state change:
1. Reads `dock_events.triggers` from adapter config.
2. For each `event_type` in the triggers dict: the shared **`is_dock_trigger_edge`** test (§2.1) decides — not an edge when `old_state` is missing/`unavailable`/`unknown` (REG-1/GUARD-3: a fresh sighting after an HA restart is not a new dock cycle), not an edge when old == new (dedup), else an edge iff the normalized new state is in that event type's trigger set. On an edge: `manager.record_dock_event(vacuum_entity_id, event_type, dry_duration)` — which **delegates** to `DockManager.record_dock_event` (§14) — then `manager._async_save_logged()` to persist.
3. For `last_dry_start` events: reads dry duration from the entity at `adapter_config["entities"]["dry_duration"]`.

---

## 5. Path Blockers Listener (`path_blockers.py`)

Watches binary sensors configured as path blockers for rooms and fires `eufy_vacuum_path_blocked` events.

**Module:** `listeners/path_blockers.py`

Builds `watch_map: dict[str, list[tuple[str, str]]]` mapping entity_id → [(vacuum_entity_id, map_id)]. Re-registers itself via `register_room_update_callback` whenever rooms change, so newly added blocker sensors are picked up without an integration restart.

On **any** watched-entity state change (dedup-guarded `old != new` — it does **not** gate on the literal `"on"`), with one refusal first (RP-008/GUARD-1): a transition **into or out of a dropout sentinel** (`unavailable` / `unknown` / `none` / `""` on either side) is logged and ignored for rule evaluation — a dying door-sensor battery once cancelled a live run. Whether a remaining change is actually a *block* is decided by `manager.get_runtime_path_block_report(..., trigger_entity_state=new_state)` returning a dict — that logic is owned by [09-room-rules](09-room-rules-system.md). On a block, the `path_block_action` for the active job drives:
- `"event_only"` (default): fires `eufy_vacuum_path_blocked` only.
- `"pause_and_event"`: pauses the job (`action_taken`: `paused` / `pause_failed`, or `already_paused` without re-pausing) and fires the event.
- `"cancel_and_event"`: **before the irreversible cancel, re-checks that the triggering rule still matches with a KNOWN state** (RP-008 step 4 — the report was computed from a snapshot; the sensor may have dropped out or cleared since). If not, the cancel is suppressed and the event fires with `action_taken: "cancel_suppressed_recheck"`. Otherwise cancels the job and — only when the cancel actually succeeded — fires `eufy_vacuum_job_finished`, then `eufy_vacuum_run_incomplete` (when rooms were missed), then `eufy_vacuum_path_blocked`.

**Single-flight (RP-008/GUARD-2).** A burst of blocker edges used to spawn one unbounded task per event; now one evaluation runs at a time, and later arrivals coalesce into a single queued re-check after it.

The `eufy_vacuum_path_blocked` payload is the **`get_runtime_path_block_report` dict augmented** with `path_block_action`, `action_taken`, and (only when a pause/cancel ran) `action_result` (consistent with [02 §7](02-ha-integration.md)).

---

## 6. Stale-Job Reaper (`pause_timeout.py`)

A **two-reap** stale-job reaper (not just a pause watchdog). **Module:** `listeners/pause_timeout.py`. **Timer:** `async_track_time_interval` fires every **1 minute**. Ticks never overlap (an `in_flight` box skips a tick while the previous one still runs). On each tick, for each managed (vacuum, map) pair (maps named `"unknown"` skipped) it runs `_reap_one_slot` — each slot isolated in its own try/except (RP-011/RF-07, STR-2/GUARD-4: one slot's exception must not kill the whole tick, or every later slot would go unprocessed this tick and every future one) — with two independent reaps:

**Reap 1 — paused-timeout.** `get_paused_job_timeout_report()` returns a report only once a job has been paused past the configured timeout (`None` otherwise — the common case). On a report: `async_cancel_active_job(...)` with the report's forced lifecycle state/message + `cancel_reason`; only when it reports `cancelled` does the tick fire `eufy_vacuum_job_finished` **and** — when rooms were left uncleaned — `eufy_vacuum_run_incomplete` (via `run_incomplete_event_data`).

**Reap 2 — stranded-`started` (FN-1).** Independent of the paused check (a stranded run is never paused). `poll_stranded_started_job(...)` stamps/clears a `stranded_since` marker and returns a report only once a dispatched `started` run has gone past its grace window without hitting its brand's completion terminal (power-loss / HA-restart / app-cancel-without-terminal; the verdict is `is_stranded_started`, [06 §6f](06-job-lifecycle.md)). On a report: `async_finalize_stranded_job(..., ended_at=stranded_since)` finalizes it as **`interrupted`** (making the run Restore-able instead of stranding), and only on `finalized: True` fires `eufy_vacuum_job_finished` **and** `eufy_vacuum_run_incomplete` (the "if it strands it is incomplete" case, so `retry_missed_rooms` can act). A refusal leaves the slot for the next tick. See [06-job-lifecycle](06-job-lifecycle.md) (`async_finalize_stranded_job`).

---

## 7. Job Progress Ticker (`job_progress.py`)

Pushes periodic progress snapshots for active jobs.

**Module:** `listeners/job_progress.py`

**Timer:** `async_track_time_interval` fires every **5 seconds**.

On each tick (maps named `"unknown"` skipped):
- Processes any run that is **in flight on the floor** — `run_is_in_flight(active_job)` (`jobs/active_job.py`): status in `{"started", "paused", "external"}`. RP-014/A5-METRICS-1: the old `{started, paused}` gate asked the *dispatched* question and excluded app-started (`external`) runs — the single case Lever B was built for (on Roborock an external run's `current_room` only advances at the device's slow native cadence, collapsing consecutive rooms — the EXT-1 shape).
- For **non-phased (contiguous) active jobs only**, calls `manager.maybe_pulse_live_room_refresh(vacuum_entity_id)` (Lever B) *before* the tick, keeping the brand's live current-room/map fresh so per-room rollover + live fan track the adapter's interval rather than the device's slower native map cadence. Strict-order phased runs (those carrying `phases`, which advance one room per dispatched phase and dock between rooms) are excluded — they already get a free refresh on each state flip. The pulse is a no-op unless the adapter declares `dispatch.live_room_refresh`; per-vacuum rate-limiting and local-gating live inside the `live_refresh` subsystem (`LiveRoomRefreshManager` in `live_refresh/manager.py`, reached via the `maybe_pulse_live_room_refresh` manager delegator).
- Calls **`manager.apply_job_progress_tick(...)`** — SNAP-2: this ticker is the ONE production caller of the side-effecting compose (`get_job_progress_snapshot(apply_side_effects=True)`, [06 §3](06-job-lifecycle.md)): the room rollover, `EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED` emission, and the anomaly dedup persistence all happen here, on the ticker's cadence. A card poll (`get_dashboard_snapshot` / `get_job_control_state`) only ever reads whatever this tick last persisted. The returned snapshot is **discarded**, not attached to the event.
- Fires `eufy_vacuum_job_progress_tick` with a payload of **`{vacuum_entity_id, map_id}` only** (a lightweight polling signal — consistent with [02 §7](02-ha-integration.md)), **not** the snapshot.

---

## 8. Job Metrics Listener (`job_metrics.py`)

Tracks cleaning time, cleaning area, battery, and station water during active jobs.

**Module:** `listeners/job_metrics.py`

Watches up to **four** entities per vacuum from two different sources: `cleaning_time`, `cleaning_area`, and `battery` come from the adapter `entities` block, while the station-water entity is resolved from the capabilities snapshot via `manager.get_vacuum_capabilities(vacuum_entity_id, refresh=False)` — and is wired **only when the snapshot declares `supports_station_water`** (METRICS-4; previously wired on an entity-key guess with any lookup failure silently swallowed; a failed capability lookup now logs a warning and leaves the watcher unwired for that vacuum).

| Entity key | Active-job field written |
|---|---|
| `cleaning_time` (adapter `entities`) | `last_cleaning_time_seconds` (int) |
| `cleaning_area` (adapter `entities`) | `last_cleaning_area_m2` (float) |
| `battery` (adapter `entities`) | `last_battery_percent` (int) — RP-013e/METRICS-2: previously **no writer existed** although both shipped adapters declare the entity, so every counter sample carried `battery=None` (the null per-room `battery_delta` at source) |
| `capabilities.entities.water_level` (fallback `capabilities.entities.station_water`), gated on `supports_station_water` | `last_station_water_percent` (float) |

On state change: validates the new value is numeric, **normalizes units**, and calls `record_active_job_sensor_value(vacuum_entity_id, key, value)`. The conversions are load-bearing (§4.1/§4.3):
- **cleaning_time → seconds** (`_duration_state_to_seconds`): ms/min/hr → seconds. The entity's `unit_of_measurement` wins; the adapter's `cleaning_time_unit` is the **fallback** for a bare-number sensor (Roborock reports minutes → `"min"`; absent → treated as seconds — the 60× learning-corruption guard, see [29](29-roborock-adapter.md)). An unrecognized unit is assumed seconds and **warned once per distinct unit** (METRICS-3), not once per event (a plateau-sampling counter can fire this path many times a minute).
- **cleaning_area → m²** (`cleaning_area_to_m2`): normalizes ft² → m² by the entity's unit. When the changed key is `last_cleaning_time_seconds` or `last_cleaning_area_m2`, the handler additionally calls `manager.record_counter_sample(vacuum_entity_id=...)`, appending one time-stamped counter sample (carrying the last-seen cleaning_time + cleaning_area + battery already pushed into the active-job state) to each in-flight job's `counter_samples` buffer, feeding `counter_segmentation.segment_counters()` for counter-plateau per-room segmentation at finalization.

---

## 9. Discovery Listener (`discovery.py`)

Triggers room discovery on lifecycle events and periodic intervals.

**Module:** `listeners/discovery.py`

**Why docked, not run-start (intended design, ruled 2026-08-07):** discovery reads the
map only when the map is SAFE — the run is over and the pose has settled. Mid-run the
map is being mutated (and on a multi-map vacuum may be mid-swap), so a run-start pass
would read churning or wrong-map data; this is the same protective stance as the
map-swap guards. The docked edge is therefore the primary trigger by design — an old
description of this as "first non-idle state" (run start) was wrong about intent, not
just detail.

**Trigger types** (from adapter config `discovery.auto_refresh_on`):

| Trigger | HA event / condition |
|---|---|
| `"vacuum_docked"` | the **vacuum entity** transitions to the literal state `"docked"` (edge-guarded `old != "docked"`) — **not** the `dock_status` entity, and not a vocabulary set |
| `"active_map_changed"` | active_map entity state changes |
| `"config_entry_reload"` | one-shot pass deferred via `async_at_started` — runs once HA has fully started (or immediately if HA is already running, e.g. a live config-entry reload). Deferred rather than run at `register()`/setup time so service-response room sources (e.g. Roborock `get_maps`) are registered before the pass reads them. |

**Periodic refresh:** `async_track_time_interval` fires every `discovery.auto_refresh_interval_seconds` seconds. `get_discovery_cadence` injects a **default of 6 hours (21,600 s)** when the adapter is silent, so the ticker is registered **by default**; it is skipped only when the adapter explicitly sets the interval to `0`.

On trigger: each pass runs three steps in order — (1) `await async_refresh_room_source(hass, vacuum_entity_id)` (from `rooms/source_refresh.py`), which refreshes the Roborock `get_maps` service-response source into the flattened cache before the sync pass reads it (a no-op for Eufy's entity-attribute source); (2) `run_discovery_pass(hass, manager, vacuum_entity_id)` from `setup/drift.py`; (3) `await manager.async_save()` to persist.

Uses `_make_run_pass(vid)` closure-binding pattern to avoid late-binding bugs in loop registration. Unsubs are keyed **per vacuum** and the module additionally exposes `remove_vacuum(hass, vacuum_entity_id)` (RP-039/RF-16) so deleting one managed vacuum tears down exactly its triggers without disturbing the others.

---

## 10. Pose Sampler (`pose_sampler.py`)

Records the per-tick robot pose time-series during an **active** run — both **external** (app-started, to recover its unknown room set) and **dispatched (`started`)** — for room auto-attribution (W5b). It is the production version of the throwaway `debug_log_live_room` probe.

**Module:** `listeners/pose_sampler.py`

**Timer:** `async_track_time_interval`. The period is the **smallest declared `room_attribution.tuning.interval_s` across all configured vacuums** (one ticker samples them all). The value is resolved from the adapter — never hardcoded: adapter `room_attribution.tuning.interval_s` → else the resolved engine's `DEFAULT_TUNING['interval_s']` → else a last-resort `_FALLBACK_INTERVAL_S` of 2 s. No adapter declaring `room_attribution` ⇒ no ticker is registered at all. On the shared ticker, each vacuum is still sampled only at its **own** declared interval (POSE-1 — a slower vacuum's samples would otherwise be over-weighted by the engine's dwell = n×interval_s math, measured 2.5× against a faster brand sharing the same ticker), a per-vacuum in-flight guard stops a slow live-pose await overlapping that same vacuum's next tick (POSE-2), and one vacuum's sampling failure doesn't stop the tick reaching the rest (POSE-5).

**Gating** (a vacuum is skipped this tick unless all hold):
- **Active runs only** — `status ∈ {external, started}` (`_SAMPLED_STATUSES`). An **external** run recovers its unknown cleaned-room set; a **dispatched (`started`)** run feeds the atomic-finalize positional-identity reconcile (strict-order phase jobs buffer samples but ignore them at finalize).
- **Capture-source-capable.** The adapter's `room_attribution.source` (default `"live_pose"`) selects one of two sources, each with its own prerequisite: **`live_pose`** (Eufy fork — a raster-lookup of the robot pixel via `async_get_map_live_pose`) needs `map_state_source.live_pose`; **`native_current_room`** (Roborock — the brand publishes the live room as a NAME entity, slugified + matched to a managed room id) needs `entities.active_cleaning_target`.
- **(`live_pose` source only) Live pose present this tick.** `async_get_map_live_pose()` must return `present`, else the tick is skipped rather than buffering a `None`. The `native_current_room` source has **no** such gate — it always records (a momentary unknown target is a genuine `None` current_room, not a skip).

On each qualifying tick it reads the declared `entities.cleaning_area` value and records one sample via `manager.record_pose_sample(...)` (`current_room`, `anchor`, `cleaning_area`, `heading`). While the robot is parked/docked — detected primarily from the MQTT `task_status` not being one of the adapter's `vocabulary.active_run_task_states` (more reliable than eufy-clean's pose `robot_docked` flag), with the pose flag as a fallback — `current_room` and `anchor` are nulled so a dock-sitting tick is not mis-attributed to the dock's room.

**Consumed — no longer inert.** The W5c engine wiring landed: the buffered `pose_samples` drive which rooms an external run is recorded as having cleaned (`learning/room_attribution_engines.py` → `external_ingest.build_pending_record`), the per-room durations on the learning record, and — via `reconcile_dispatched_identity`'s "rescued" branch — the room identity stamped on a **dispatched** atomic run's timings ([06-job-lifecycle](06-job-lifecycle.md)).

**24-hour pose ring.** Each sample is also appended (executor-offloaded via `hass.async_add_executor_job`, failures swallowed and only debug-logged) to a parallel on-disk ring (`pose_store.append_sample`, keyed by vacuum) that outlives the job — the live `pose_samples` buffer is job-scoped and never reaches the finalized record. The ring append is deliberately **not** gated on `record_pose_sample`'s return: the ring wants the sample regardless of whether a job slot accepted it.

---

## 11. Module Summary

| Module | Trigger type | Period | Primary side effect |
|---|---|---|---|
| `lifecycle.py` | State change (lifecycle entities) | — | Job start/finish detection, learning finalization, event fire |
| `dock_events.py` | State change (dock entities) | — | Dock cycle recording via DockManager |
| `path_blockers.py` | State change (binary sensors) | — | `eufy_vacuum_path_blocked` event, optional pause/cancel |
| `pause_timeout.py` | Time interval | 1 min | **Two reaps**: timed-out paused jobs + stranded-`started` jobs (FN-1) → both fire `job_finished` (+`run_incomplete` when rooms missed) |
| `job_progress.py` | Time interval | 5 sec | `apply_job_progress_tick` (SNAP-2: the sole side-effecting snapshot caller — rollover + stall/skip events) + `eufy_vacuum_job_progress_tick` event (+ Lever B live-room refresh pulse on contiguous runs); covers `external` runs too (`run_is_in_flight`) |
| `job_metrics.py` | State change (metric entities) | — | Record cleaning time/area/battery/water into active job (+ counter-sample append on time/area change) |
| `discovery.py` | State change + time interval | 6 hr | Run discovery pass, update drift history |
| `pose_sampler.py` | Time interval | min adapter `room_attribution.tuning.interval_s` (fallback 2 s); per-vacuum own-interval gating | Record per-tick pose sample (`record_pose_sample`) on **active** runs (`external`+`started`), dual-source (`live_pose` / `native_current_room`) + 24 h pose-ring append |
