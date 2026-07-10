# 07 — Queue Engine

The queue engine translates the user's room configuration into the exact JSON
payload the Eufy vacuum API accepts. It lives in
`custom_components/eufy_vacuum/queue/queue_engine.py` and is called from
`core/manager.py` (via `build_queue` and `build_room_payload`) and from
`planning/run_plan.py` (via `_build_effective_start_plan`).

---

## 1. What the Queue Engine Does

The engine takes three inputs and produces one output.

**Inputs**

- **Managed rooms** — the persisted `RoomRecord` dicts for one vacuum/map.
  Each room carries an `enabled` flag, an `order` number, a profile name, and
  per-room cleaning settings.
- **Capabilities** — a dict describing which hardware features the vacuum
  supports (`supports_mop_features`, `supports_water_control`,
  `supports_path_control`, `supports_edge_mopping`, `supports_passes`).
  Sourced from `get_vacuum_capabilities()`.
- **Stored profiles** — the custom room-profile library from
  `data["profiles"]["room_profiles"]`, merged with the built-in profiles via
  `merge_profile_dicts` in `profiles/room_profiles.py`. The built-in side of
  that merge comes from the adapter-resolved catalog (see §4), not directly
  from the in-code constants.

**What the engine does NOT do**

The queue engine is rule-agnostic. It processes whatever room states it
receives. Rule evaluation (blockers, modifiers, access-graph propagation)
happens in `RunPlanManager._build_effective_start_plan`
(`planning/run_plan.py`) before the engine is called at job-start time.

**Output**

```json
{
  "vacuum_entity_id": "vacuum.alfred",
  "map_id": "6",
  "payload": {
    "map_id": 6,
    "rooms": [ ... ]
  },
  "resolved_rooms": [ ... ],
  "room_count": 4
}
```

The `payload` sub-object is the exact body sent to the Eufy API via
`vacuum.send_command` with `command: "room_clean"`.

---

## 2. Payload Structure

### Wire format sent to the vacuum

```json
{
  "map_id": 6,
  "rooms": [
    {
      "id": 3,
      "clean_times": 1,
      "fan_speed": "Max",
      "clean_mode": "vacuum",
      "clean_intensity": "Standard"
    }
  ]
}
```

Capability-gated fields (`water_level`, `edge_mopping`, `path_type`) are
present only when the capabilities dict says the vacuum supports them *and* the
room's `clean_mode` requires them.

**Field reference**

| Field | Type | Condition |
|---|---|---|
| `map_id` | `int \| str` | Numeric when the ID is all-digits; raw string otherwise |
| `id` | `int` | Room ID from the vacuum firmware |
| `clean_times` | `int` | Number of cleaning passes (always ≥ 1) |
| `fan_speed` | `str` | `"Quiet"`, `"Standard"`, `"Boost"`, `"Max"` |
| `clean_mode` | `str` | `"vacuum"`, `"mop"`, `"vacuum_mop"` |
| `clean_intensity` | `str` | `"Quick"`, `"Standard"`, `"Deep"` (default `"Standard"`) |
| `water_level` | `str` | Only when `supports_water_control` AND `clean_mode` in `{"mop", "vacuum_mop"}` |
| `edge_mopping` | `bool` | Only when `supports_edge_mopping` AND `clean_mode` in `{"mop", "vacuum_mop"}` |
| `path_type` | `str` | `"wide"`, `"narrow"` (default `"wide"`); only when `supports_path_control` |

The vacuum processes rooms in the order they appear in the `rooms` array.

### The `resolved_rooms` sidecar

`resolved_rooms` is a parallel list used by the integration for display and job
tracking. It carries every field in the API payload plus:
- `name`, `slug`
- `selected_profile_name`, `resolved_profile_name`
- `carpet` (bool derived from `floor_type`)
- `capability_gated` dict

It is never sent to the vacuum.

---

## 3. Room Ordering

Rooms appear in the payload in the same order as the queue.

1. All rooms where `enabled == True` are collected from `managed_rooms`.
2. Sorted by `(int(room["order"]), str(room["name"]))`.
   - `order` is a user-assigned integer (set via number entity or card UI).
     Default fallback is `999`.
   - `name` is a stable tiebreaker when two rooms share the same order value.

The same sort key is applied by both `get_enabled_rooms_in_order` (queue state)
and inside `build_room_clean_payload` (payload build) — queue order and payload
order are always consistent.

**Changing room order** — the user assigns order values through number entities.
The card UI provides drag-and-drop reorder that writes these entities. The
engine reads stored values; it does not compute order from any other source.

---

## 4. Profile Resolution

Before resolving any room, `build_room_clean_payload` resolves the vacuum's
**room-profile catalog** from the adapter. It calls
`get_adapter_config(vacuum_entity_id)` (deferred import of `adapters/registry.py`),
reads the adapter's `room_profiles` block, and passes it through
`resolve_profile_catalog` (`profiles/room_profiles.py`). That returns a catalog
dict (`builtins`, `custom_template`, `legacy_aliases`, `default_profile`,
`floor_type_water_defaults`, `floor_type_fan_defaults`, `normalize_defaults`),
merging the adapter block over the in-code constants *per key*. A None/empty
block yields the in-code defaults verbatim — so for Eufy, whose `room_profiles`
block is declared by reference to those same constants, the catalog **is** the
in-code defaults and resolution is byte-identical to pre-refactor.

The resolved `_catalog` is then threaded into both
`resolve_room_profile_for_room` and `apply_capability_gate` (the `catalog=`
argument) so a brand's profile vocabulary — built-ins, legacy aliases, and
floor-type fan/water defaults — reaches the dispatched per-room settings.

For each room, the engine resolves which cleaning settings to use:

1. `room["profile_name"]` is looked up in the merged profile library
   (custom + built-in) via `resolve_room_profile_for_room`, using the
   adapter-resolved catalog.
2. If the profile name is `"custom"` or not found, the room's direct fields
   (`fan_speed`, `water_level`, etc.) are used as-is.
3. Carpet/mop invariants are enforced inside `resolve_room_profile_for_room`
   itself (carpet/floor-type defaults), not by a separate pass:
   - Carpet rooms: `fan_speed` set to the floor-type fan default;
     `water_level` forced to `"Off"`; `edge_mopping` forced to `False`.
   - Non-mop modes (and carpet): `edge_mopping` forced to `False`.
4. Capability gating is applied via `apply_capability_gate` (also passed the
   resolved catalog) — removes fields the vacuum hardware doesn't support and
   derives the mop→vacuum downgrade fallback from the catalog's built-ins.

The final `ResolvedRoom` records both the `selected_profile_name` (what the
room stored) and the `resolved_profile_name` (what was actually used).

---

## 5. Access Graph

### What it is

The access graph encodes which rooms the vacuum must physically traverse to
reach other rooms. It is a directed graph stored as adjacency data on each room
object, owned and evaluated by `AccessGraphManager` (`rooms/access_graph.py`).

**Why it matters** — if the path from room A to room B requires traversal
through room C, and room C is blocked by a rule, the vacuum cannot safely reach
room B. The access graph tells the rule evaluator about this dependency so it
can cascade the block.

### Storage format

Each room has a `grants_access_to` field — a list of room IDs accessible from
that room:

```json
{
  "room_id": 1,
  "name": "Hallway",
  "is_dock_room": true,
  "grants_access_to": [2, 3]
}
```

One room is marked `is_dock_room: true` — the root of the graph.

**Structural constraints enforced by `AccessGraphManager`:**
- Each non-dock room may have at most one inbound edge.
- No self-references.
- No duplicate edges.
- No cycles.
- The dock room must be reachable from every other room following
  `grants_access_to` edges in reverse.

### Graph states

`_access_graph_state()` (static method on `AccessGraphManager`) returns one of:

| State | Condition | Effect |
|---|---|---|
| `"blank"` | No dock room, no `grants_access_to` entries | Basic runs allowed; rule-requiring runs blocked |
| `"partial"` | Some config exists but validation fails | All runs blocked (basic and rule-based) until the graph is completed or all access settings are cleared |
| `"complete"` | Fully valid graph | All runs and rules allowed |

### How the graph is traversed for rule evaluation

`_build_room_access_views` (on `AccessGraphManager`) converts the
`grants_access_to` adjacency lists into two derived maps:

- `grants_map[room_id]` — room IDs this room grants access to (copy of
  `grants_access_to`).
- `requires_map[room_id]` — reverse: room IDs whose `grants_access_to`
  includes this room.

A room with an empty `requires_map` entry is directly accessible from the dock.

During `_build_effective_start_plan`, the engine computes `accessible_room_ids`
using an iterative propagation loop: a room becomes accessible only if at least
one of its parents is accessible and not blocked.

### BFS path finding

`_access_graph_path(managed_rooms, from_room_id, to_room_id)` (on
`ActiveJobTracker`, `jobs/active_job.py`) finds the intermediate rooms between
any two rooms. BFS over `grants_map` edges, tracks full paths, returns
`path[1:-1]` — intermediate rooms only, excluding both endpoints.

Used by the transition-detection subsystem to determine which room the robot is
currently traversing between queued rooms.

> **See also:** [09-room-rules-system](09-room-rules-system.md) §5 for how `_build_effective_start_plan` uses the access graph to cascade blocker rules to indirectly blocked rooms; [08-rooms-system](08-rooms-system.md) §6 for the `grants_access_to` field on room objects that populates this graph.

---

## 6. Reduced Run Detection

When blocker rules remove rooms from the queue, the resulting run may be
significantly shorter than intended. The planning engine calculates two ratios
and requires explicit confirmation if either threshold is exceeded.

### Formulas

```
blocked_ratio_time  = blocked_expected_minutes / selected_expected_minutes
blocked_ratio_rooms = len(blocked_room_ids) / len(selected_room_ids)
```

- `selected_expected_minutes` — sum of the learning estimate for every selected
  room.
- `blocked_expected_minutes` — sum of the estimate for only blocked rooms.

### Threshold

```python
requires_confirmation = bool(
    blocked_room_ids
    and (
        blocked_ratio_time  >= 0.20   # 20% of expected time would be removed
        or blocked_ratio_rooms >= 0.40   # 40% of rooms would be skipped
    )
)
```

When `requires_confirmation` is `True`, `_build_effective_start_plan` generates
a 12-character SHA-1 hex `confirm_token` (hash of
`vacuum_entity_id | map_id | selected_ids | included_ids | blocked_ids`). The
caller must pass this token back via `confirm_token`, or set
`confirm_reduced_run=True`, for `start_selected_rooms` to proceed.

If time estimates are unavailable (`selected_expected_minutes == 0.0`), only
the room-count ratio can trigger the confirmation gate.

---

## 7. `build_queue` vs `build_room_payload`

### `build_queue`

```python
manager.build_queue(vacuum_entity_id=..., map_id=...)
```

Calls `build_queue_from_managed_rooms`. Produces a lightweight queue summary
(see data model §4). The queue reflects only the `enabled` flag — blocker rules
have **not** been evaluated. This is the pre-rule queue used for display.

Stores the result in `self.data["queue"][vacuum_entity_id][map_id]` and updates
`runtime.queue_room_ids`.

### `build_room_payload`

```python
manager.build_room_payload(vacuum_entity_id=..., map_id=...)
```

Resolves the brand dispatch engine (`get_dispatch_engine(dispatch.template)`)
and calls its `build_payload(...)`; for the Eufy engine that delegates to
`build_room_clean_payload`, which reads current queue state, resolves profiles,
applies capability gating, and builds the full API payload. Stores the result in
`self.data["payloads"][vacuum_entity_id][map_id]`.

Called when the user changes a room setting or the queue is rebuilt. Does
**not** apply rules — that happens at job start.

### When `_build_effective_start_plan` supersedes both

At job start, `RunPlanManager._build_effective_start_plan`
(`planning/run_plan.py`) is called instead of `build_queue` +
`build_room_payload`. It re-evaluates all blocker and modifier rules against
live HA state, computes the effective room set with blocked rooms removed and
modifier changes applied, then calls `build_queue_from_managed_rooms` and the
resolved dispatch engine's `build_payload` / `build_phases` (which for the Eufy
engine delegate to `build_room_clean_payload`) on this effective room set. The
resulting `queue_state` and `payload_state` are what actually get stored and
sent to the vacuum.

> **See also:** [06-job-lifecycle](06-job-lifecycle.md) §1 for when `build_queue` and `build_room_payload` are called from the manager and §1 Preflight for the full `_build_effective_start_plan` call site; [16-profile-manager](16-profile-manager.md) §6 for the profile finalization pipeline that runs inside `build_room_clean_payload`.

### Dispatch engines & the job model

`build_room_clean_payload` is no longer the final dispatcher — it is the
shared **resolver** (profile resolution + capability gating + canonical
`resolved_rooms`). The brand-specific payload **shape** is produced by a
pluggable engine in `queue/dispatch_engines.py`, selected by
`dispatch.template`:

- `EufyRoomCleanEngine` — delegates verbatim to `build_room_clean_payload`
  (the list-of-dicts "rows" shape; byte-identical to pre-refactor).
- `GenericRoomIdsEngine` / `RoborockSegmentEngine` — flat id list + a
  single batch passes scalar (`{segments:[ints], repeat:n}`).
- `DreameSegmentEngine` — positional parallel arrays (the transpose of
  the Eufy rows). Non-Eufy engines reuse the resolver's `resolved_rooms`
  and reshape, so learning/history stay brand-independent.

The full author-facing reference (per-template shapes, `room_fields`,
value maps) is [22-adapter-config-reference §13](22-adapter-config-reference.md#13-dispatch--how-to-send-a-clean-job).

**Sequencing.** Engines declare a `job_model` at the class level, and today
every engine declares `atomic_batch` — a job is one dispatch of a fixed room
set, which `build_active_job_state` freezes and the lifecycle hook finalizes
when it completes. The generic `sequenced` machinery still exists: an engine's
`build_phases()` returns an ordered phase list; `build_active_job_state` stores
`phases` / `current_phase_index`, and `advance_active_job_phase(active_job)`
swaps to the next phase (resetting per-phase progress) or returns `None` on the
final/atomic case. The completion hook calls `manager.maybe_advance_phase` to
advance + re-dispatch instead of finalizing; each phase finalizes as its own
job record. See [06-job-lifecycle](06-job-lifecycle.md) for the completion path.

A phase list is no longer always all-room-groups: a **stepped run** (§9)
interleaves room-group phases with `charge_wait` / `wait` **break phases** that
have no rooms. `advance_active_job_phase` still swaps to the next phase the same
way, but `maybe_advance_phase` reads the next phase's `phase_type` and routes a
break phase to its own poller (charge / wait) instead of re-dispatching a clean.

**Strict order (per-run opt-in sequencing).** Sequencing does not require a
declared `sequenced` engine. `GenericRoomIdsEngine.build_phases(strict_order=True)`
emits **one single-segment phase per resolved room**, in queue order, each phase
carrying its own room's passes — turning a path-optimizing brand's single batch
into a sequenced job that cleans strictly in queue order (one room, wait for it
to finish, then the next). This is for brands whose wire command ignores the
dispatched order (Roborock `app_segment_clean`, Ecovacs `spot_area`): a batch is
re-routed by the device, but one room per phase is unambiguous. A bonus is that
each phase honors its own room's passes, where the batch path collapses passes to
one max-wins value.

`strict_order` is a per-run service flag on `start_selected_rooms`
(`core/manager.py`), threaded into `_build_effective_start_plan` →
`_build_dispatch_phases` (`planning/run_plan.py`). It is gated on
`capabilities.honors_clean_order` being `False` — `_build_dispatch_phases`
computes `effective_strict = strict_order and not honors_clean_order`, so it can
never alter an order-honoring brand (Eufy) even if requested. It is also a no-op
for atomic / order-honoring engines: `_SinglePhaseMixin.build_phases` ignores the
flag and returns the single batch phase. The class-level `job_model` stays
`atomic_batch` throughout — sequencing here is an opt-in property of the *run*,
not a declared engine model.

A **stepped run with stops** (§9) forces `strict_order=True` unconditionally:
`_build_effective_start_plan` passes `strict_order=True` into `_build_steps_phases`
whenever the run's steps contain a `charge_wait` / `wait` stop, so a
path-optimizing brand runs each group's rooms in the exact order shown rather than
silently re-ordering them inside one batch. The `honors_clean_order` gate still
folds it to a no-op for Eufy.

### Send-side dispatch (`DispatchManager`)

The dispatch engines above produce the payload **shape**; pushing that payload
onto the wire is the **send side**, owned by `DispatchManager`
(`dispatch/manager.py`, package `dispatch/`), constructed as
`self.dispatch = DispatchManager(manager=self)`. It owns
`_dispatch_clean_payload` (wraps a resolved payload in the adapter's on-wire
service envelope and calls it), `dispatch_zone_clean` (ad-hoc free-form zone
clean), `_resolve_live_dispatch_payload` (re-resolves segment ids to LIVE ids by
slug), and `_run_global_pre_calls`. The core manager keeps a thin delegator for
each of the four (`start_selected_rooms`, `jobs/phase_runner.py`, the mapping /
job-control services, and the dispatch tests all call `manager.<method>`), so
callers are unchanged.

`_run_global_pre_calls` pushes device-**global** fan/water settings before an
atomic dispatch for brands whose select-exposed settings aren't per-room payload
fields (Roborock `app_segment_clean` carries passes only). Each
`dispatch.global_pre_calls` entry picks the run value by its `rank` (max-wins).
**Mixed-batch safe water**: an entry that opts in with
`mixed_mode_water_policy: "safest"` flips to the SAFEST (lowest-rank) water for a
mixed mop + vacuum-only batch (≥1 mop room AND ≥1 vacuum-only room), so a device
that can't zero water per-room doesn't wet-mop the dry rooms — under-mop is
accepted over wet-mop. Single-mode batches (all-mop or all-vacuum) and the
fan-speed entry (which never carries the marker) stay max-wins.

---

## 8. `set_rooms_enabled_subset`

```python
manager.set_rooms_enabled_subset(
    vacuum_entity_id=...,
    map_id=...,
    room_ids=[3, 7],
)
```

Enables only rooms in `room_ids` and disables all others on the map. Does not
change any other room settings. After mutating room data:

1. Rebuilds the room selection summary.
2. Calls `_refresh_room_derived_state` to regenerate derived display state.
3. Fires the `rooms_updated` notification.

Returns:

```json
{
  "vacuum_entity_id": "vacuum.alfred",
  "map_id": "6",
  "enabled_count": 2,
  "total_count": 11,
  "wanted_room_ids": ["3", "7"]
}
```

### Use in `retry_missed_rooms`

```python
core_manager.set_rooms_enabled_subset(
    vacuum_entity_id=vacuum_entity_id,
    map_id=map_id,
    room_ids=missed_room_ids,
)
core_manager.build_queue(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
result = await core_manager.start_selected_rooms(
    vacuum_entity_id=vacuum_entity_id,
    map_id=map_id,
    confirm_reduced_run=True,   # retry is by definition a reduced run
)
```

`confirm_reduced_run=True` is always passed because a retry is by definition a
reduced run — the user already acknowledged the missed rooms.

---

## 9. Stepped Runs (charge / wait break phases)

A run profile can carry an ordered `steps` list — room **groups** broken up by
**stops** — so one learned job can vacuum some rooms, dock and charge to a target
battery, then continue (or dock and hold a fixed pause, e.g. a mop-dry wait). This
is built on the §7 sequencing machinery; the phase list gains non-room break
phases.

### Steps model

The profile's `steps` is a list of three step types:

```json
[
  {"type": "room_group", "rooms": [
     {"room_id": 3, "clean_mode": "vacuum", "fan_speed": "Max"},
     {"room_id": 4, "clean_mode": "vacuum"}
  ]},
  {"type": "charge_wait", "target_battery_percent": 80},
  {"type": "room_group", "rooms": [{"room_id": 3, "clean_mode": "mop"}]},
  {"type": "wait", "wait_minutes": 15}
]
```

- **`room_group`** — a group of rooms with per-room settings.
- **`charge_wait`** — dock and poll battery until `target_battery_percent`, then continue.
- **`wait`** — dock and hold for `wait_minutes`, then continue.

### Materialization → phases

`RunPlanManager._build_steps_phases` (`planning/run_plan.py`) turns `steps` into
the active-job `phases` list 1:1:

- Each `room_group` → its brand dispatch phase(s) (via `_build_dispatch_phases`),
  scoped to that group's **included** (enabled + not-blocked) room IDs.
- Each `charge_wait` / `wait` step → a break phase carrying only its
  `phase_type` + `target_battery_percent` / `wait_minutes` and empty room fields.
- **Break-phase cleanup**: leading and trailing breaks are dropped (a stop with
  no clean to bracket is pointless), and consecutive same-type breaks collapse to
  the last (two charges → last target). If no break survives, it falls back to one
  atomic clean over all included rooms.

**Per-group settings.** The SAME room can appear in two groups with different
settings (vacuum in one phase, mop the next). `_build_steps_phases` overlays each
group room's own fields over the global effective-room view before building that
group's dispatch phase — the group's fields win. Each group room's `room_id` is
coerced with a `_safe_int` (drop non-positive) before use — the same discipline
`build_room_clean_payload` uses — so a malformed `room_id` never reaches `int()`
and crashes the dispatch. `ProfileManager.normalize_run_profile_steps`
(`profiles/manager.py`) applies the same coercion when a `steps` list is stored,
dropping unparseable room ids and any group left with no valid room.

`_build_effective_start_plan` invokes `_build_steps_phases` only when the pending
run steps (stashed by `start_run_profile`, popped on the real dispatch) contain a
`charge_wait` / `wait` stop; otherwise it takes the normal single-phase
`_build_dispatch_phases` path. A stepped run with stops forces `strict_order=True`
(see §7).

### Running the break phases

Break phases have no rooms, so no room-finish event can advance them — the phase
runner owns their lifecycle. When `maybe_advance_phase` (`jobs/phase_runner.py`)
swaps to a break phase, it reads the next phase's `phase_type` and spawns:

- **`_run_charge_wait_phase`** — sends `vacuum.return_to_base`, polls battery
  every ~30 s, and advances via `maybe_advance_phase` once
  `target_battery_percent` is reached. Already at/above target on entry → advance
  immediately without charging. Timeout (`charge_wait_timeout_minutes`, default
  180) → finalize like a cancel, so the un-cleaned remaining rooms are reported
  missed. A genuine user Cancel / pause / advance bails.
- **`_run_wait_phase`** — the time-based twin: dock, hold `wait_minutes`, then
  advance.

Both keep `_phase_dispatch_pending` set for the duration, which the completion
gate honours — the same guard that stops a Roborock's between-phase dock from
finalizing — so the **intentional** charge/idle dock is never read as a
cancel/completion. Both phase types are also exempt from the mid-job recharge
observer (`ActiveJobTracker.update_active_job_recharge_observation`,
`jobs/active_job.py`, checks `phase_type in ("charge_wait", "wait")`): a `wait`
phase docks too and the device auto-charges while parked, so a low-battery
wait-dock would otherwise be logged as a phantom unplanned recharge.

**Poller re-arm (pause+resume / HA restart).** A break-phase poller is a purely
in-memory `asyncio` task — a pause+resume (status flips back to `started` but
re-arms nothing) or an HA restart (the task is gone and `async_initialize`
force-clears `_phase_dispatch_pending`) would leave the dock phase with no live
driver and the run would wedge in `started` forever.
`PhaseRunner.rearm_dock_phase_if_needed(vacuum_entity_id, map_id)`
(`jobs/phase_runner.py`) re-spawns the matching charge/wait poller when the active
job is `started` **and** its current phase is a dock phase (`charge_wait` / `wait`);
it re-asserts `_phase_dispatch_pending` and recomputes the wait deadline from the
persisted `wait_started_at`. It is a no-op for atomic / room-group / finalized jobs.
It is called on resume (`ActiveJobTracker.async_resume_active_job`, `jobs/active_job.py`)
and on load (`manager.async_initialize`, over every `started` active job), and is
double-spawn guarded by a `_dock_poller_active` set so a normal advance and a re-arm
can't both drive the same dock phase.

### Snapshot fields

`get_job_progress_snapshot` (`core/manager.py`) surfaces the current break phase:

| Field | Meaning |
|---|---|
| `charge_phase_active` | Current phase is a `charge_wait` |
| `charge_target_percent` | The phase's `target_battery_percent` |
| `charge_eta_minutes` | ETA from `battery/manager.py` `compute_time_to_target_pct` |
| `charge_eta_source` | ETA basis (`baseline` / `zone_rate` / `already_charged`; `None` on a cold start) |
| `wait_phase_active` | Current phase is a `wait` |
| `wait_minutes` | The phase's hold duration |
| `charge_from_battery` | Battery % recorded when the charge began (observability; `None` until the charge starts) |
| `charge_started_at` | ISO timestamp the charge phase began (`None` until started) |
| `wait_started_at` | ISO timestamp the wait phase began (`None` until started) |

`compute_time_to_target_pct` splits the CC/CV charge curve at 80 %; a cold start
(no learned rate) returns `minutes: None` (the card falls back to a wall-clock
display) rather than a fabricated estimate.

### Services & flag

- **`set_run_profile_steps`** (`services/run_profiles.py`, delegating to
  `profiles/manager.py`) writes a profile's `steps` list.
- **`start_run_profile`** applies + starts a saved profile, running its full
  stepped sequence. The orchestration (apply the profile, stash the charge/wait
  steps, dispatch) lives on **`ProfileManager.start_run_profile`**
  (`profiles/manager.py`, next to `apply_run_profile`); the core manager keeps a
  thin `start_run_profile` delegator for its service + button-entity callers, and
  `start_selected_rooms` / `build_queue` / `build_room_payload` stay on the core
  manager (reached via `self._manager`). It only stashes `_pending_run_steps` when
  the profile actually has a `charge_wait` / `wait` stop, and — because
  `start_selected_rooms` pops that stash only deep in `_build_effective_start_plan`,
  which an early return (blocked / confirmation-required without a token / vacuum
  missing) never reaches — it deletes the leftover stash on a **non-started**
  return, so the next plain Start on that map isn't silently turned into a
  charge/wait run.
- The enriched profile snapshot (`_enrich_saved_run_profile`, `profiles/manager.py`)
  carries two distinct flags. **`has_charge_steps`** is charge-only (any
  `charge_wait` step). **`has_stops`** means "this is a **sequenced** run, not a
  plain queue" — any break step (`charge_wait` / `wait`) **or** more than one
  `room_group` — and it is what the card's Start-routing gates on
  (`pendingStepRunProfileId`, `src/state/run-profiles.js`), routing an applied
  sequenced profile through the stepped dispatch instead of a plain Start.
  `_enrich_saved_run_profile` also derives `room_count` / `room_ids` / `room_names`
  from the effective `steps` (the flattened `room_group` rooms), not the stale
  top-level `rooms`.

Charge/wait steps are brand-agnostic — they ride free on Roborock as well as
Eufy. See [29-roborock-adapter](29-roborock-adapter.md) for the Roborock
per-phase dispatch (a stepped run can vacuum one group then mop the next).
