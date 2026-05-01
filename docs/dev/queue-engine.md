# Queue Engine

The queue engine translates the user's room configuration into the exact JSON payload the Eufy vacuum API accepts. It lives in `custom_components/eufy_vacuum/queue/queue_engine.py` and is called from `core/manager.py`.

---

## 1. What the queue engine does

The engine takes three inputs and produces one output.

**Inputs**

- **Managed rooms** — the persisted room objects for one vacuum/map, each carrying an `enabled` flag, an `order` number, a profile name, and per-room cleaning settings.
- **Capabilities** — a dict describing which hardware features the vacuum supports (`supports_mop_features`, `supports_water_control`, `supports_path_control`, `supports_edge_mopping`, `supports_passes`).
- **Rules** — blocker and modifier rules attached to rooms. These are evaluated separately, just before job start, in `_build_effective_start_plan`. The queue engine itself is rule-agnostic; it processes whatever room states it receives.

**Output**

A dict that contains:

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

The `payload` sub-object is the exact body sent to the Eufy API via `vacuum.send_command` with `command: room_clean`.

---

## 2. Payload structure

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
      "clean_intensity": "Standard",
      "water_level": "Low",
      "edge_mopping": false,
      "path_type": "bow_mode"
    }
  ]
}
```

**Field reference**

| Field | Type | Notes |
|---|---|---|
| `map_id` | int or str | Numeric when the ID is all-digits; raw string otherwise. |
| `id` | int | Room ID as assigned by the vacuum firmware. |
| `clean_times` | int | Number of cleaning passes. Always 1 or 2. |
| `fan_speed` | str | `"Quiet"`, `"Standard"`, `"Boost"`, or `"Max"`. |
| `clean_mode` | str | `"vacuum"`, `"mop"`, or `"vacuum_mop"`. |
| `clean_intensity` | str | `"Quick"`, `"Narrow"`, or `"Deep"`. |
| `water_level` | str | `"Off"`, `"Low"`, `"Medium"`, or `"High"`. Only included when `supports_water_control` is true and `clean_mode` is `"mop"` or `"vacuum_mop"`. |
| `edge_mopping` | bool | Only included when `supports_edge_mopping` is true and `clean_mode` is `"mop"` or `"vacuum_mop"`. |
| `path_type` | str | Only included when `supports_path_control` is true. |

The vacuum processes rooms in the order they appear in the `rooms` array.

### The `resolved_rooms` sidecar

`resolved_rooms` is a parallel list that the integration uses internally for display and job tracking. It carries every field in the API payload plus additional metadata: `name`, `slug`, `selected_profile_name`, `resolved_profile_name`, `carpet`, and a `capability_gated` dict. It is never sent to the vacuum.

---

## 3. Room ordering

Rooms appear in the payload in the same order they appear in the queue. Order is determined as follows.

1. All rooms where `enabled == True` are collected from `managed_rooms`.
2. They are sorted by a two-key tuple: `(int(room["order"]), str(room["name"]))`.
   - `order` is a user-assigned integer (set via the number entity or the card UI). The default fallback is `999`.
   - `name` is used as a stable tiebreaker when two rooms share the same order value.

The sort is applied identically in `get_enabled_rooms_in_order` (queue state) and inside `build_room_clean_payload` (payload build). Both functions use the same comparison key, so queue order and payload order are always consistent.

**Changing room order** — the user assigns order values through number entities exposed by the integration (one per room per map). The card UI provides a drag-and-drop reorder interface that writes these number entities. The engine reads the stored values; it does not compute order from any other source.

---

## 4. Access graph

### What it is

The access graph encodes which rooms the vacuum must physically pass through to reach other rooms. It is a directed graph stored as adjacency data on each room object.

**Why it matters for cleaning** — the vacuum's firmware cleans in queue order and navigates between rooms autonomously. If the path from room A to room B passes through room C, and room C is blocked by a rule, the vacuum cannot safely reach room B. The access graph tells the rule evaluator about this dependency so it can cascade the block.

### Storage format

Each room object has a `grants_access_to` field — a list of room IDs that are accessible from that room:

```json
{
  "room_id": 1,
  "name": "Hallway",
  "is_dock_room": true,
  "grants_access_to": [2, 3]
}
```

One room is marked `is_dock_room: true`. This is the room containing the dock. It is the root of the graph.

The integration enforces several structural constraints:

- Each non-dock room may have at most one inbound edge (single-inbound constraint).
- No self-references (`room_id` cannot appear in its own `grants_access_to`).
- No duplicate edges.
- No cycles.
- The dock room must be reachable from every other room following `grants_access_to` edges in reverse.

### How the graph is traversed

`_build_room_access_views` converts the `grants_access_to` adjacency lists into two derived maps:

- `grants_map[room_id]` — the list of room IDs this room grants access to (direct copy of `grants_access_to`).
- `requires_map[room_id]` — the reverse: the list of room IDs whose `grants_access_to` includes this room.

A room with an empty `requires_map` entry has no prerequisite rooms — it is directly accessible from the dock.

During queue build in `_build_effective_start_plan`, the engine computes the set of `accessible_room_ids` using an iterative propagation loop (described in section 5 of the rules system doc). A room becomes accessible if at least one of its parents in `requires_map` is accessible and not blocked.

### BFS path finding

`_access_graph_path(managed_rooms, from_room_id, to_room_id)` finds the intermediate rooms between any two rooms. It performs a BFS over `grants_map` edges, tracking full paths. When the target is reached, it returns `path[1:-1]` — the intermediate rooms only, excluding both endpoints.

This is used by the transition-detection subsystem to determine which room the robot is currently crossing between rooms.

### Graph states

The `_access_graph_state` method returns one of three states:

- `"blank"` — no dock room marked, no `grants_access_to` entries anywhere. Basic runs are allowed; rules requiring the graph are blocked.
- `"partial"` — some configuration exists but validation fails. All runs with rules are blocked.
- `"complete"` — graph is fully valid. All runs and rules are allowed.

---

## 5. Reduced run detection

When blocker rules remove rooms from the queue, the resulting run may be significantly shorter than what the user intended. The engine calculates two ratios and requires explicit confirmation if either threshold is exceeded.

### Formulas

```
blocked_ratio_time  = blocked_expected_minutes / selected_expected_minutes
blocked_ratio_rooms = len(blocked_room_ids) / len(selected_room_ids)
```

- `selected_expected_minutes` — sum of the learning system's time estimate for every selected room.
- `blocked_expected_minutes` — sum of the time estimate for only the blocked rooms.
- `included_expected_minutes` — `max(selected - blocked, 0)`.

### Threshold

```python
requires_confirmation = bool(
    blocked_room_ids
    and (
        blocked_ratio_time >= 0.20
        or blocked_ratio_rooms >= 0.40
    )
)
```

In plain terms: confirmation is required when at least 20% of the expected job time would be removed, **or** when at least 40% of the selected rooms would be skipped.

When `requires_confirmation` is true, `_build_effective_start_plan` generates a short confirmation token (a 12-character SHA-1 hex digest of `vacuum_entity_id | map_id | selected_ids | included_ids | blocked_ids`). The caller must pass this token back in `confirm_token`, or set `confirm_reduced_run=True`, for `start_selected_rooms` to proceed.

If time estimates are unavailable (the learning subsystem has not recorded data for these rooms), `selected_expected_minutes` is 0.0, which makes `blocked_ratio_time` evaluate to 0.0. In that case only the room-count ratio can trigger the confirmation gate.

---

## 6. `build_queue` vs `build_room_payload`

These are the two manager-level methods that call into the queue engine functions.

### `build_queue`

```python
manager.build_queue(vacuum_entity_id=..., map_id=...)
```

Calls `build_queue_from_managed_rooms`. Produces a lightweight queue summary:

```json
{
  "vacuum_entity_id": "vacuum.alfred",
  "map_id": "6",
  "room_count": 4,
  "queue_room_ids": [3, 1, 2, 4],
  "queue_rooms": [
    {"room_id": 3, "name": "Kitchen", "slug": "kitchen", "order": 1, "profile_name": "vacuum_quick"}
  ]
}
```

The queue summary reflects only the `enabled` flag — blocker rules have **not** been evaluated yet. This is the pre-rule queue used for display purposes.

`build_queue` also stores the result into `self.data["queue"][vacuum_entity_id][map_id]` and updates the runtime's `queue_room_ids`.

### `build_room_payload`

```python
manager.build_room_payload(vacuum_entity_id=..., map_id=...)
```

Calls `build_room_clean_payload`. Reads the current queue state (which room IDs are in it) from `self.data["queue"]`, resolves the cleaning profile for each room, applies capability gating, and builds the full API payload. Stores the result into `self.data["payloads"][vacuum_entity_id][map_id]`.

`build_room_payload` is called in the normal UI flow when the user changes a room setting or rebuilds the queue. It does **not** apply rules — that happens later.

### When `_build_effective_start_plan` supersedes both

At job start time, `_build_effective_start_plan` is called instead of `build_queue` + `build_room_payload`. It re-evaluates all blocker and modifier rules against live HA state, computes the effective `managed_rooms` with blocked rooms disabled and modifier changes applied, then calls `build_queue_from_managed_rooms` and `build_room_clean_payload` on this effective room set. The resulting `queue_state` and `payload_state` are what actually get stored and sent to the vacuum.

---

## 7. `set_rooms_enabled_subset`

```python
manager.set_rooms_enabled_subset(
    vacuum_entity_id=...,
    map_id=...,
    room_ids=[3, 7],
)
```

Enables only the rooms in `room_ids` and disables all others on the map. It does not change any other room settings. After mutating the room data it:

1. Rebuilds the room selection summary.
2. Calls `_refresh_room_derived_state` to regenerate derived display state.
3. Fires the `rooms_updated` notification so the card re-renders.

Returns a summary dict:

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

The `retry_missed_rooms` service (in `learning/services.py`) uses `set_rooms_enabled_subset` as its first step. After an incomplete run, the learning system records which rooms were missed. `retry_missed_rooms` calls `set_rooms_enabled_subset` with those missed room IDs, then calls `build_queue`, and finally calls `start_selected_rooms`. This is the complete retry sequence:

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
    confirm_reduced_run=True,
)
```

`confirm_reduced_run=True` is passed unconditionally because a retry is by definition a reduced run — the user already knows rooms will be skipped.
