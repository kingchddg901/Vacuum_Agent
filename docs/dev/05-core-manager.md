# 05 — Core Manager — Central Orchestrator

`EufyVacuumManager` is the single integration-wide runtime object. Every
service call, every entity state read, and every card data request passes
through it. This document explains what the manager owns directly, what it
delegates, how the callback system works, and the rules for extending it.

---

## 1. Design Philosophy

### Orchestrator, not monolith

The manager was originally a monolithic file (~9 400 lines). The bundle-out
refactor extracted 10+ domain subsystems into their own packages while keeping
the manager as the single public API surface. The result is:

- **Callers** (service handlers, entities, listeners) always call
  `manager.<method>()` — they never import subsystem classes directly.
- **Subsystem managers** (e.g. `ProfileManager`, `RunPlanManager`) hold a
  `self._manager` back-reference and are trusted collaborators. They can read
  and write `self._manager.data` directly.
- **The manager** exposes shim methods that delegate to subsystems, plus owns
  a small number of responsibilities that genuinely span multiple subsystems.

### Why a single manager?

All integration data is interdependent. Starting a job requires reading the
queue *and* the payload *and* running preflight rule evaluation *and* writing
an active-job record — atomically from one call site. A per-entity or
per-subsystem design would fragment ownership and require synchronisation. One
writer, one in-memory dict, one save call.

### What stays in the manager vs what delegates

Things that stay in `core/manager.py`:
- `self.data` ownership and `async_save`
- Callback registration and notification firing
- `update_room_fields` (spans profiles, queue, payload, room state, and fires
  multiple notifications)
- `build_queue` / `build_room_payload` (derived-state refresh after room changes)
- `start_selected_rooms` (job start — orchestrates run_plan, active_job, HA
  service call, post-start state clear). `start_run_profile` is now a delegator
  to `ProfileManager` (see below); `build_queue`/`build_room_payload`/
  `start_selected_rooms` stay on the manager and are reached from there via
  `self._manager`.
- `get_job_progress_snapshot` / `get_lifecycle_state` / `get_dashboard_snapshot`
  (cross-cutting read aggregators)
- Room history ingestion methods (see §6)
- Schema migrations that run once at startup

Things that delegate to subsystems:
- Room/map CRUD → `room_map` (`rooms/room_crud.py`)
- Room profiles, run profiles, and run-profile **start** orchestration →
  `profiles` (`profiles/`) — `start_run_profile` (apply the profile, stash the
  charge/wait steps, build queue/payload, dispatch) lives next to
  `apply_run_profile` in `ProfileManager`
- Active job slot CRUD → `active_job` (`jobs/active_job.py`)
- Preflight planning and rule evaluation → `run_plan` (`planning/run_plan.py`)
- Send-side wire dispatch → `dispatch` (`dispatch/manager.py`,
  `DispatchManager`) — `_dispatch_clean_payload`, `dispatch_zone_clean`,
  `_resolve_live_dispatch_payload`, `_run_global_pre_calls`
- External (app-started) run capture / finalize / review →
  `external_run` (`learning/external_run.py`, `ExternalRunManager`) — see §7
- Theme library → `themes` (`themes/`)
- Maintenance / upkeep → `maintenance` (`maintenance/`)
- Dock actions → `dock` (`dock/`)
- Onboarding state machine → `onboarding` (`onboarding/`)
- Access graph → `access_graph` (`rooms/access_graph.py`)
- Strict-order phase execution → `phase_runner` (`jobs/phase_runner.py`)
- Live current-room refresh (Lever B) → `live_room_refresh` (`live_refresh/manager.py`)
- `map_state_source` dispatch and live-pose reads → `map_source`
  (`mapping/map_source_coordinator.py`)

---

## 2. Initialisation Sequence

`async_initialize()` is called once during `__init__.async_setup_entry()`.

```
async_initialize()
├── await self.storage.async_load()          → self.data populated from disk
├── self.data.setdefault(...)                → seed top-level keys (vacuums,
│                                              capabilities, room_history,
│                                              room_rule_status,
│                                              learning_processing_enabled=True,
│                                              learning_pending_runs) — 6 keys
├── release stale _phase_dispatch_pending    → clear the guard on loaded room-group
│                                              jobs (a restart lost the watchdog);
│                                              dock (charge_wait/wait) phases are
│                                              RE-ARMED at the end, not here
├── drop "icons" block                       → one-time cleanup (removed platform)
├── ThemeManager(self.data)                  → self.themes
├── MaintenanceManager(manager=self)         → self.maintenance
├── DockManager(manager=self)                → self.dock
├── OnboardingManager(data, hass)            → self.onboarding
├── ProfileManager(manager=self)             → self.profiles
├── AccessGraphManager(data, hass)           → self.access_graph
├── ActiveJobTracker(manager=self)           → self.active_job
├── PhaseRunner(manager=self)                → self.phase_runner (after ActiveJobTracker)
├── RunPlanManager(manager=self)             → self.run_plan
├── RoomMapManager(manager=self)             → self.room_map
├── LiveRoomRefreshManager(manager=self)     → self.live_room_refresh
├── MapSourceCoordinator(manager=self)       → self.map_source
├── DispatchManager(manager=self)            → self.dispatch
├── ExternalRunManager(manager=self)         → self.external_run
├── room field backfills (setdefault loop)   → existing rooms get new fields
├── discovery shape migration                → old flat → per-map-id dict
├── _migrate_setup_progress()                → stamps existing installs complete
├── callback lists + cache sets initialised  → incl. _vacuum_added_callbacks (§5)
│                                              and the _map_frame_gate dict (per-vacuum
│                                              post-map-switch coordinate-frame gate)
├── phase_runner.rearm_dock_phase_if_needed  → re-spawn a lost charge_wait/wait
│                                              poller for any 'started' dock job
├── _clear_orphaned_finalize_claims()        → release finalize claims a crash stranded
└── _reap_stranded_phased_jobs()             → close Phased-Job parents left "running"
                                               by a crash/restart (parents are written at
                                               run start, so an abnormal end must be reaped)
```

All subsystem managers are constructed with a reference to the manager and are
ready to receive calls immediately after `async_initialize()` returns.

### Schema migrations

Two migration classes run on every startup; both are idempotent.

**Room field backfill** — iterates every room in every map bucket and calls
`setdefault` on fields added after initial release: `path_type`,
`is_dock_room`, `is_transition`, `grants_access_to`, `rules`, `floor_type`,
`profile_name`. Also compacts the legacy `floor_type="carpet"` +
`carpet_type` pair into the canonical `"carpet_low_pile"` /
`"carpet_high_pile"` single value.

**`_migrate_setup_progress()`** — vacuums that already had managed rooms
before the setup state machine was introduced get all three legacy steps
(`add_vacuum`, `import_active_map`, `save_rooms`) stamped complete
automatically so they do not see an onboarding prompt on the next start.
Vacuums with no rooms are untouched.

**Future migrations** — the pattern is: `setdefault` for new fields on every
affected record, run on startup, idempotent. There is no migration version
number; migrations gate on data shape, not a stored version counter.

---

## 3. Subsystem Manager Contracts

Each subsystem receives the manager in its constructor and uses it as follows:

| Subsystem | Constructor | Accesses on manager |
|---|---|---|
| `ThemeManager` | `(data)` | `data["theme"]` directly (owns the sub-tree) |
| `MaintenanceManager` | `(manager)` | `self._manager.data`, adapter registry |
| `DockManager` | `(manager)` | `self._manager.hass`, adapter registry |
| `OnboardingManager` | `(data, hass)` | `data["onboarding"]`, `data["discovery"]` |
| `ProfileManager` | `(manager)` | `self._manager.data` |
| `AccessGraphManager` | `(data, hass)` | `data["maps"]` |
| `ActiveJobTracker` | `(manager)` | `self._manager.data`, hass, runtime state |
| `PhaseRunner` | `(manager)` | `self._manager.data["active_jobs"]`, hass, dispatch/save helpers, `_phase_timing` |
| `RunPlanManager` | `(manager)` | `self._manager.*` broadly |
| `RoomMapManager` | `(manager)` | `self._manager.data` |
| `LiveRoomRefreshManager` | `(manager)` | `self._manager.hass`, adapter config (fire-and-forget service pulse) |
| `MapSourceCoordinator` | `(manager)` | `self._manager.hass`, writes `_map_state_source_cache`, shares `_resolve_live_map_image_entity` |
| `DispatchManager` | `(manager)` | `self._manager.hass`, `async_get_map_data_dict`, `map_source`, adapter registry |
| `ExternalRunManager` | `(manager)` | `self._manager` active-job / map / save helpers; holds in-memory grace-timer + re-check state |

**The subsystem/manager write boundary**: subsystem managers write directly
to `self._manager.data[key]` for their own domain keys. They never call
`async_save()` themselves — saving is always the manager's (or the service
handler's) responsibility. The final `await manager.async_save()` call always
lives at the service layer.

**Delegators and shared state that stay on the manager.** For the
bundled-out subsystems the manager keeps thin delegators (called
from production listeners/lifecycle/services, so the entry points stay stable)
and the shared caches/helpers each subsystem reads back through `self._manager`:

- `PhaseRunner` — `maybe_advance_phase()` delegates; the `_PHASE_*` constants
  and `_phase_timing()` (adapter overrides merged over the defaults) stay on
  the manager. `rearm_dock_phase_if_needed()` re-spawns a lost
  `charge_wait`/`wait` poller when the current phase is a dock phase and
  `status=='started'` — called on resume (`active_job.async_resume_active_job`)
  and on load/`async_initialize`, guarded by a `_dock_poller_active` set — so a
  charge/wait run doesn't wedge in `'started'` after a pause+resume or HA restart.
- `LiveRoomRefreshManager` — `maybe_pulse_live_room_refresh()` delegates (the
  job-progress ticker calls it for contiguous runs only).
- `MapSourceCoordinator` — the four async readers `async_refresh_map_state_source`,
  `async_get_map_live_pose`, `async_compare_map_sources`, and
  `async_get_map_render_data` delegate; the `_map_state_source_cache` (read
  on-loop by the snapshot composer and the map-overlays sensor) and
  `_resolve_live_map_image_entity` stay on the manager.
- `DispatchManager` — `_dispatch_clean_payload`, `dispatch_zone_clean`,
  `_resolve_live_dispatch_payload`, and `_run_global_pre_calls` all delegate
  (production callers `start_selected_rooms`, `jobs/phase_runner.py`, the
  mapping/job-control services, and the tests reference `manager.<method>`
  unchanged). The subsystem reads `hass` + the map/room helpers back through
  `self._manager`.
- `ExternalRunManager` — every external-run entry point delegates (`§7`); the
  SHARED room-history ingestion helpers (`_ingest_*_into_room_history`, also
  driven by the normal completed-job finalize) and `resolve_active_map_id` /
  `start_external_capture` stay in core and are reached via `self._manager`.
  `learning/__init__` imports `ExternalRunManager` **directly** (no lazy
  `__getattr__`) — the old import cycle is gone: the grace-timer constants
  moved to `learning/constants.py`, and `external_run.py`'s only
  `core.manager` import is `TYPE_CHECKING`-guarded.

---

## 4. The Shim Pattern

For every method that now lives in a subsystem, `core/manager.py` exposes a
shim that delegates with `**kwargs`. This keeps all ~80+ service handlers
unchanged — they call `manager.save_user_room_profile(...)` and do not need
to know that `ProfileManager` exists.

```python
# core/manager.py
def save_user_room_profile(self, **kwargs) -> dict[str, Any]:
    """Save one custom room profile — delegates to ProfileManager."""
    return self.profiles.save_user_room_profile(**kwargs)
```

Shims are intentionally thin. Any cross-cutting logic (e.g. firing a
notification after a profile save) stays in the manager method before or
after the subsystem call, not inside the subsystem.

---

## 5. Callback System

The manager is the central notification hub for HA entity refresh. Six
callback channels are maintained as plain Python lists.

| Channel | List name | `_notify_*` method | Subscribers |
|---|---|---|---|
| Room list changed | `_room_update_callbacks` | `_notify_rooms_updated` | switch, number, sensor platforms |
| Run profile changed | `_run_profile_update_callbacks` | `_notify_run_profiles_updated` | button platform |
| Room history updated | `_room_history_update_callbacks` | `_notify_room_history_updated` | sensor platform (room history sensors) |
| Rule status updated | `_room_rule_status_update_callbacks` | `_notify_room_rule_status_updated` | sensor platform (rule status sensors) |
| Vacuum added | `_vacuum_added_callbacks` | `_notify_vacuum_added` | sensor platform (SN-1 — fires the first time `ensure_vacuum_record` creates a NEW managed-vacuum record, so per-vacuum sensors build immediately instead of waiting for a reload; `add_vacuum` / `discover_rooms` / config-entry setup all route through `ensure_vacuum_record`) |
| Theme updated | (owned by ThemeManager) | — | sensor platform (theme sensor) |

The vacuum-added notification passes only `vacuum_entity_id` (no `map_id`) —
unlike the four room/profile/history/rule channels above, which pass both; the
theme channel also passes only `vacuum_entity_id`.

### Registration lifecycle

Platform `async_setup_entry` registers callbacks:

```python
manager.register_room_update_callback(_on_rooms_updated)
entry.async_on_unload(
    lambda: manager.unregister_room_update_callback(_on_rooms_updated)
)
```

`entry.async_on_unload` ensures cleanup on config entry reload or unload.

### Notification signature

All `_notify_*` methods pass `vacuum_entity_id` and `map_id` as keyword
arguments. Callbacks receive them and can filter to their relevant entities:

```python
def _on_rooms_updated(*, vacuum_entity_id: str, map_id: str) -> None:
    prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"
    # ... sync entity list for this vacuum/map
```

### Thread safety

Callbacks are called from the HA event loop. If a listener module fires
a notification from a background thread (rare but possible), it must
schedule the entity state write via `hass.loop.call_soon_threadsafe`. The
`_request_entity_state_write` helper in `sensor/__init__.py` handles this.
Callback lists are never mutated outside the event loop.

### `_refresh_room_derived_state`

When room configuration changes (enables, order, profile), this helper
rebuilds the queue and payload snapshots and is always called before
`_notify_rooms_updated`. The queue/payload in `manager.data` are derived
state — always reconstructed from room config, never edited directly.

---

## 6. Direct Responsibilities

These methods live in `core/manager.py` rather than a subsystem because they
orchestrate multiple subsystems or span too many data keys to belong to one.

### `update_room_fields`

The most cross-cutting write in the system (`manager.py:1553`). Accepts a room
update (`enabled`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`,
`clean_passes`, `edge_mopping`, `color`, `is_dock_room`, `is_transition`,
`grants_access_to`, `rules` — keyword-only, all optional), applies it to
`data["maps"]`, applies the appropriate profile + carpet/mop protection rules
(via `_finalize_room_update`), updates the summary, rebuilds derived
queue/payload, and fires room update callbacks — all synchronously, in memory.
It does **not** save: like every subsystem write (§3), the
`await manager.async_save()` is the calling service handler's job.

It has **no `floor_type` / `carpet_type` parameters** — floor type is not
settable through this method (it changes via `save_managed_rooms`'
`floor_types` argument), and the legacy `floor_type="carpet"` + `carpet_type`
collapse happens only in the `async_initialize` room-field backfill (§2), not
here.

**Access-graph validation is half the method.** Two refusal gates run before
the write commits, both rolling `rooms[room_key]` back to the pre-edit record
and returning `ok=False`:

- **Delta-scoped structural validation (A6-AGX-2).** The post-edit graph is
  validated (`_validate_room_access_graph` → `_structural_access_graph_issues`),
  but the edit is refused (`error`/`reason = "invalid_access_graph"`, with a
  formatted `issues` list) only for issues **this edit introduced** — a
  baseline issue-key set is captured from the same validator *before* the
  mutation, and any issue whose key was already present is tolerated. A
  structural violation can genuinely pre-exist (reconciliation rewrites grants
  through an id remap without re-checking the cross-room single-inbound
  constraint), and it must not block an unrelated fan-speed / enable / colour
  edit.
- **`no_dock_room` (A5-DOCK-1).** A `grants_access_to` edit that *changes the
  links* on a map with **no** dock room is refused (`error`/`reason =
  "no_dock_room"`) — links without a root make every room trip
  `missing_dependency` at queue-build. Deliberately **not** delta-scoped ("no
  dock yet" is a baseline condition by definition); two escape hatches keep it
  workable: a save that *sets* the dock passes (dock + first children in one
  save), and a save that changes no links passes (so releasing the dock stays
  possible). Non-access edits are never gated by this rule.

On success returns `{ok: True, vacuum_entity_id, map_id, room_id, updated:
True, profile_name, room}`; a missing room returns `error`/`reason =
"room_not_found"`.

It also accepts a per-room `color` override. Unlike the `bool|None` /
`str|None`-defaulted params (where `None` means "not provided"), `color`
defaults to the module-level `_UNSET = object()` sentinel because `None` is
meaningful for this field: `_UNSET` leaves the existing override untouched,
`None` or an empty string clears the override (empty string coalesces to `None`
so a cleared field is never stored as `""`), and any other value stores the
schema-canonicalized hex. Ref: `manager.py:1566` (param), `manager.py:60`
(`_UNSET` sentinel), `manager.py:1627-1628` (three-way apply logic).

### `start_selected_rooms` (and the `start_run_profile` delegator)

`start_selected_rooms` orchestrates job start: build effective start plan
(run_plan), dispatch to the upstream vacuum (via the `DispatchManager`
delegators — **`_resolve_live_dispatch_payload` → `_run_global_pre_calls` →
`_dispatch_clean_payload`**; pre-calls deliberately run AFTER resolution,
immediately before the wire send — DQ-ACT-6: resolution can raise on a
re-segmented map, and firing the pre-calls first left the device's global mop
intensity rewritten by a start that then aborted), write active job state,
clear room selections post-start. It does **not** call `async_save()` — like
every other mutation, the save is the calling service handler's job. Returns a
structured start summary. It stays on the manager and is reached from
`ProfileManager` via `self._manager`.

`start_run_profile` now lives in `ProfileManager` (next to `apply_run_profile`);
the manager keeps only a thin delegator for its service + button-entity callers.
It applies the profile, builds queue/payload, and calls `start_selected_rooms`.
It also stashes the profile's ordered `steps` sequence into
`data["_pending_run_steps"]` before starting — gated on
`step_requires_stepped_execution` over `STEPPED_STEP_TYPES =
{"charge_wait", "wait", "zone"}` (`step_types.py:38`): a **zone** step counts
too, because a rooms→zone profile is a real multi-phase run (only
`charge_wait`/`wait` are *dock-polled*, a distinct vocabulary). The plan
builder (`run_plan._build_effective_start_plan`) consumes that stash and
materializes a multi-phase `[clean, charge_wait, clean, …]` / `[clean, zone]`
job via `_build_steps_phases` (which `_safe_int`-coerces each `room_id`,
resolves each zone step's saved-zone ids to dispatch rects at **build** time,
and trims leading/trailing *dock* breaks only — never a leading zone); absent
the stash it builds the single atomic phase as before. A stepped run with
stops is a deliberate sequence, so the plan builder forces `strict_order=True`
(a no-op for order-honoring brands like Eufy, which fold it back to `False`;
on a path-optimizing brand like Roborock it pins each group's rooms to the
shown order). Profiles with no stops (a plain room list) still start
atomically.

**Consume-vs-peek.** `_build_effective_start_plan` takes a
`consume_pending_steps` flag: only the real dispatch (`start_selected_rooms`)
passes `True` and **pops** the stash; preflight callers (`get_start_status`,
the path-block report) peek, so a preflight can never eat the stash before the
real dispatch builds its plan. The pop happens deep in
`_build_effective_start_plan`, so an early return (blocked /
confirmation-required-without-token / vacuum missing) never reaches it — hence
`start_run_profile` deletes the leaked stash on any NON-started return, or the
next plain Start on that map would silently pop it and become a charge/wait
run.

**Ad-hoc stepped fallback (plain Start).** When no profile stash exists, the
plan builder falls back to the LIVE QUEUE's own breaks (`get_queue_steps` —
derived, not consumed, so preflight and dispatch agree): if the queue's steps
carry a `charge_wait`/`wait`/`zone` entry, a plain Start also materializes a
stepped, strict-order multi-phase job. An explicit `start_run_profile` stash
takes precedence over the queue breaks.

### `_run_global_pre_calls` (delegated to `DispatchManager`)

Pushes a brand's device-**global** run settings — settings the adapter exposes
only as whole-device state, not per-room payload fields — before an atomic
dispatch. For each adapter-declared `dispatch.global_pre_calls` entry it picks
the run value from the selected rooms' canonical field by the entry's `rank`
(max-wins), maps it to the wire value, and calls the entry's service.
Best-effort: a failed pre-call is logged, never aborts the run. It lives in
`DispatchManager` (`dispatch/manager.py`) with the rest of the send side; the
manager keeps a delegator because `start_selected_rooms` and
`PhaseRunner._dispatch_active_phase` call `manager._run_global_pre_calls`. It
runs **per phase**: `start_selected_rooms` fires it for the first phase, and
`PhaseRunner._dispatch_active_phase` re-runs it for every subsequent phase from
that phase's own rooms — so a stepped run can vacuum one group then mop the next,
each applying its own global setting (e.g. Roborock mop intensity via a
`select`). No-op for adapters that declare none (Eufy, the Roborock S6).

**Mixed-batch safe water.** A device-global water/mop-intensity `select` can't be
zeroed per-room, so a mixed mop + vacuum-only batch that max-wins to the
strongest water would wet-mop the dry rooms. An entry that opts in with
`mixed_mode_water_policy: "safest"` picks the SAFEST (lowest-rank) water for a
mixed batch (≥1 mop room AND ≥1 vacuum-only room) so a dry room is never
wet-mopped (under-mop accepted over wet-mop); a single-mode batch (all-mop or
all-vacuum) keeps max-wins, and the `fan_speed` entry never carries the marker so
suction stays max-wins. Detail:
[22-adapter-config-reference](22-adapter-config-reference.md),
[29-roborock-adapter](29-roborock-adapter.md).

### `get_job_progress_snapshot`

Reads active job state, computes elapsed/expected times per room (active_job),
and emits a timing-only bounds-exit signal (`current_room_overdue`) — computed
by the composer itself — when `current_room_elapsed_minutes` exceeds the
timing-completion threshold, but **force-cleared to `False` for a
path-optimizing brand** (`capabilities.honors_clean_order is False`, e.g.
Roborock), where the dispatched room order carries no meaning to exit from;
`mapping_available` / `mapping_used` are always `False`. Run-anomaly detection (stall / running-long / skipped) and the
one-shot `EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED` emission (deduped per
room per job) are delegated to `ActiveJobTracker.detect_run_anomalies`
(`jobs/active_job.py`), which owns the active-job dict and the dedup state; the
composer hands it the already-resolved locals and reads the anomaly fields back
into the snapshot. It then returns a complete card-ready progress payload
(persisted field-by-field shape: [03 §5b](03-data-model.md); the client-facing
surface is aggregated in
[frontend/backend-contract-and-data-shapes](frontend/backend-contract-and-data-shapes.md#ha-services)).
Still too many concerns to belong to a single subsystem.

When the active phase is a `charge_wait` or `wait` stop (a stepped run docked
between room groups), the composer surfaces the stop so the card shows an
intentional "Charging to X% — ~N min" / "Waiting" state rather than a hung job:
`charge_phase_active` + `charge_target_percent` + `charge_eta_minutes` +
`charge_eta_source` (the ETA from `battery/manager.py`
`compute_time_to_target_pct`, which returns `None` — meaning the card falls back
to a live wall-clock — on a cold-start install rather than fabricating a number)
+ `charge_from_battery` / `charge_started_at` (read from the current phase
record), and `wait_phase_active` + `wait_minutes` + `wait_started_at`.

**Liveness gate.** charge/wait/zone used to be derived purely from
`current_phase_index` + the phase's `phase_type`, so a run cancelled during a
wait left the index pointing at that wait forever and the card kept counting
down a hold that had already been torn down. The fix is a liveness check —
`_phase_state_live = status == "started" and not finalized` — that nulls the
phase list out entirely before any of the charge/wait/zone branches run, so
none of them can activate once the job is no longer live.

The snapshot also carries `current_room_ids` + `current_phase` (RP-047): a
`room_group` phase is ONE dispatch, so no per-room rollover exists inside it
and `current_room_id` pins to the group's first room for the phase's whole
duration. `current_room_ids` lists every room of the current phase (falling
back to the single anchor room), and `current_phase` is a small block
`{index, phase_type, room_ids, is_group}` — `current_room_id` is unchanged and
stays the map's anchor; the card just stops treating it as the whole answer.

A **`zone` phase** is surfaced the same way (`zone_phase_active` +
`zone_phase_ids` / `zone_phase_names` + `zone_phase_eta_minutes`), but with one
difference: a zone is a *clean*, not a dock, and its roomless phase lingers on the
active job through the post-clean drying. So `zone_phase_active` is gated on
`_zone_is_actively_cleaning` — which reads `"zone" in active_cleaning_target` (the
device signal that stays truthy through mop-prep bounces and clears at dock-done),
with a "not docked/returning/idle" fallback for a brand that lacks it — so the
"Cleaning zone" banner clears cleanly instead of hanging through drying. The
zone's ETA is `_zone_ids_estimate_seconds` (learned avg else area fallback, see
[10-learning-system §2.5](10-learning-system.md#25-zone-learning-learned_zones)),
and the pre-run whole-job estimate folds queued zones in via
`_estimate_queued_zones` (exposed as `zone_estimate`).

**`live_queue` — the running-job composer twin.** The snapshot also carries
`live_queue = {active, steps[]}`, built by `_build_live_queue_steps`, which flattens
the running job's phase sequence into an ordered chip list —
`{seq, kind: room|charge|wait|zone, state: done|current|upcoming, + live detail on
the current one}`. Crucially it reads the **`active_job` clone** (its `phases`,
frozen at launch) and **never the live queue composer**, so re-queuing rooms mid-run
(building the *next* clean) can't disturb the chips of the *current* one — the "clone
principle." An atomic job (no `phases`) flattens its `resolved_rooms` as one group.
This is the monitor mirror of the [ad-hoc queue composer](07-queue-engine.md#the-ad-hoc-live-queue-queue_breaks).

### `get_dashboard_snapshot`

The card's whole read-model for **one** vacuum/map (`*, vacuum_entity_id,
map_id`) — one call, complete card reload. It composes the sub-snapshots
`lifecycle`, `start_status`, `job_progress`, `job_control`, `upkeep` (the
maintenance / attention state), `planned_job_estimate`, and `queue_steps`, then
layers on a large **adapter-capability hint block** the editor reads to shape
itself (`adapter_vocabulary`, `max_clean_passes`, `mop_active`,
`supports_room_profiles`, `passes_is_global`, `supports_base_station`,
`supports_map_bounds`, `supports_zone_clean`, `zone_max`, `zone_bounds`,
`supports_water_control`, `supports_edge_mopping`, `honors_clean_order`,
`supports_va_render`, `setting_entities`, `scene_select`, `cv_available` /
`cv_missing`) and a **live-map block** (`live_map_image_entity`, `map_switcher`,
`live_map_rotation`, `map_overlay_visibility`, `area_label_anchors`,
`hidden_regions`, `furnished_render`, `map_state_source`), plus `status_summary`
/ `attention_summary` / `learning_processing` / `updated_at`.

Because it is **per-vacuum**, it does NOT carry a managed-vacuums list (that is
the separate `get_managed_vacuums`) nor a `payload` block (the separate
`get_payload_state` service); "dock" state rides inside `job_control` /
`upkeep`, not a top-level key. **This section is the authoritative field-by-field
shape**; its client-facing surface (which services / entities / events a UI consumes
to render it) is aggregated in
[frontend/backend-contract-and-data-shapes](frontend/backend-contract-and-data-shapes.md#ha-services).

### Room history ingestion

`_ingest_completed_job_into_room_history` and
`_ingest_jobs_index_entry_into_room_history` merge completed job records
into `data["room_history"]`. Called from job finalization. The room history
cache (`_room_history_cache_ready`) is a set of vacuum keys that have been
loaded from learning history files via `async_preload_room_history_cache`.
For sensors reading history before the first job finishes, the cache is
populated from disk on sensor platform startup.

---

> **External-run methods** now live in `ExternalRunManager`
> (`learning/external_run.py`); the manager keeps a thin delegator for each so
> the service layer, the lifecycle listener, and the tests still call
> `manager.<method>`. Owned there: `maybe_handle_external_run` +
> `_finalize_external_run` (detect + capture an app-started run, then segment it
> into a pending review record), the `_external_grace_*` timers / checks / cb /
> finalize (defer the finalize until the robot stays docked) + the
> `_extract_return_overhead` helper, and the review-wizard surface
> `confirm_external_run` / `get_external_pending_runs` / `discard_external_run` /
> `resegment_external_run`. `start_external_capture` (active-job tracker) and the
> shared `_ingest_*_into_room_history` helpers stay in core. A confirmed run
> graduates into a normal `jobs/` record. See
> [28-external-run-ingestion](28-external-run-ingestion.md).

## 7. Storage

```python
# All writes:
await manager.async_save()

# All reads:
manager.data["maps"]["vacuum.alfred"]["6"]["rooms"]["1"]
```

`async_save()` delegates to `core/storage.py:EufyVacuumStorage`, which wraps
HA's `Store` helper. Writes are atomic (HA writes to a temp file and renames).

`_async_save_logged()` is a variant used in fire-and-forget contexts (e.g.
background callbacks) that logs exceptions instead of raising them.

**`async_save_delayed()` (DRAFT-5)** schedules a **coalesced** write via
`Store.async_delay_save` instead of writing immediately — for high-frequency,
low-stakes updates (theme draft edits / card slider drags), where the thing
being avoided is one full integration-data disk write per edit. The debounce
window is `DRAFT_SAVE_DELAY_SECONDS = 2.0` (`core/storage.py`); rapid callers
collapse into one write after the last call, and a crash mid-drag loses at
most that window. It is a callback, not a coroutine (mirroring HA's own
`Store.async_delay_save`), and the data getter (`lambda: self.data`) is
invoked at *write* time.

**Shutdown seam (RP-003/INIT-1).** A reloaded entry's previous manager must
neither run nor write:

- `async_shutdown()` — idempotent, registered via
  `entry.async_on_unload(manager.async_shutdown)` *before* `async_initialize`
  runs (so a mid-setup failure still tears down). It first **flushes any
  pending debounced write directly via storage** (`await
  self.storage.async_save(self.data)`, not `self.async_save()` — HA's `Store`
  only guards a full-hass final write, not an integration unload/reload, and
  routing the flush through the `_closed`-gated `async_save()` would drop an
  in-flight DRAFT-5 window right here), then sets `_closed = True` and cancels
  the phase runner's dock pollers (`phase_runner.cancel_all()`), the
  external-run grace timers (`external_run.cancel_timers()`), and everything
  in the generic `_background_tasks` / `_timers` ledgers. Returns
  `{timers_cancelled, tasks_cancelled}`.
- `_closed` gates both `async_save()` and `async_save_delayed()` —
  belt-and-braces: a stale, unloaded manager can never clobber the store a
  newer manager (from a reload) already owns; a post-shutdown save attempt
  logs a warning and no-ops.
- The subsystem-owned spawn sites (dock pollers, grace timers) are ledgered on
  their **owning subsystem** per the bundled-subsystem pattern and exposed via
  `cancel_all()`/`cancel_timers()`; `_background_tasks`/`_timers` are the
  generic reserved ledgers for future spawn sites.

The manager never reads the **storage file** after `async_initialize()` — every
`self.data` read is in-memory, and the storage file is just the mirror of what
was last saved. (One narrow exception, on a *different* file: the room-history
cache lazy-loads per-vacuum **learning-history** files off disk via
`async_preload_room_history_cache` → `_load_room_history_cache_sync`, run in an
executor for sensors that read history before the first job finishes — see §6.)

---

## 8. `runtime` vs `data`

The manager holds two state containers:

| | `self.data` | `self.runtime` |
|---|---|---|
| Persisted | ✓ | ✗ |
| Loaded at startup | ✓ | Reconstructed from upstream |
| Type | `dict[str, Any]` | `dict[str, VacuumRuntimeState]` |
| Content | All integration config and history | Live vacuum state (HA state string, battery, dock sensors) |
| Written by | Manager + subsystems | `ensure_runtime()` + listener callbacks |

`ensure_runtime(vacuum_entity_id)` is called whenever a listener needs to
read or write live vacuum state. It creates the runtime slot if absent.
Runtime state is never saved to disk — it is rebuilt from upstream entity
state on every HA restart.

---

## 9. Adding a Subsystem

1. Create a package under `custom_components/eufy_vacuum/<name>/`.
2. Add a manager class: `class <Name>Manager: def __init__(self, manager): self._manager = manager`.
3. In `EufyVacuumManager.async_initialize()`, construct and assign:
   `self.<name> = <Name>Manager(manager=self)`.
4. Move the relevant methods from `core/manager.py` into the new class.
5. Add thin shims in `core/manager.py`:
   ```python
   def do_thing(self, **kwargs):
       """Delegate to <Name>Manager."""
       return self.<name>.do_thing(**kwargs)
   ```
6. Existing callers continue to call `manager.do_thing(...)` unchanged.

The key rule: shims are one-liners. Cross-cutting logic that touches multiple
subsystems stays in `core/manager.py`, not inside any subsystem.
