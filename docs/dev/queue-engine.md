# Queue Engine

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
  `data["profiles"]["room_profiles"]`, merged with built-in profiles via
  `merge_profile_dicts` in `profiles/room_profiles.py`.

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
| `clean_intensity` | `str` | `"Quick"`, `"Standard"`, `"Intense"`, `"Deep"`, etc. |
| `water_level` | `str` | Only when `supports_water_control` AND `clean_mode` in `{"mop", "vacuum_mop"}` |
| `edge_mopping` | `bool` | Only when `supports_edge_mopping` AND `clean_mode` in `{"mop", "vacuum_mop"}` |
| `path_type` | `str` | Only when `supports_path_control` |

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

For each room, the engine resolves which cleaning settings to use:

1. `room["profile_name"]` is looked up in the merged profile library
   (custom + built-in) via `resolve_room_profile_for_room`.
2. If the profile name is `"custom"` or not found, the room's direct fields
   (`fan_speed`, `water_level`, etc.) are used as-is.
3. The resolved settings are passed through `_protected_room_config` in
   `ProfileManager` — this enforces carpet/mop invariants:
   - Carpet rooms: `clean_mode` downgraded from mop/vacuum_mop to `"vacuum"`;
     `water_level` forced to `"Off"`; `edge_mopping` forced to `False`.
   - Non-mop modes: `water_level` forced to `"Off"`; `edge_mopping` to `False`.
4. Capability gating is applied via `apply_capability_gate` — removes fields
   the vacuum hardware doesn't support.

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
| `"partial"` | Some config exists but validation fails | All rule-based runs blocked |
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

Calls `build_room_clean_payload`. Reads current queue state, resolves profiles,
applies capability gating, builds the full API payload. Stores the result in
`self.data["payloads"][vacuum_entity_id][map_id]`.

Called when the user changes a room setting or the queue is rebuilt. Does
**not** apply rules — that happens at job start.

### When `_build_effective_start_plan` supersedes both

At job start, `RunPlanManager._build_effective_start_plan`
(`planning/run_plan.py`) is called instead of `build_queue` +
`build_room_payload`. It re-evaluates all blocker and modifier rules against
live HA state, computes the effective room set with blocked rooms removed and
modifier changes applied, then calls `build_queue_from_managed_rooms` and
`build_room_clean_payload` on this effective room set. The resulting
`queue_state` and `payload_state` are what actually get stored and sent to the
vacuum.

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
