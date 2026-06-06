# Rooms System — Developer Reference

> **Scope:** Complete implementation reference for the rooms subsystem: `rooms/room_crud.py` (RoomMapManager), `rooms/room_manager.py` (pure functions), `rooms/room_discovery.py` (adapter-driven discovery), and `rooms/utils.py`. Every method, adapter dependency, storage path, and inter-module relationship is derived directly from the source.

---

## 1. Overview

The rooms system is responsible for the full lifecycle of room data within the integration: discovering rooms from the upstream vacuum API, building and persisting managed room records, and removing stale data when a map is deleted or rebuilt.

**Module roles:**

| Module | Role |
|---|---|
| `rooms/room_crud.py` | Orchestration class (`RoomMapManager`). Coordinates discover → save → remove → rebuild. Holds a back-reference to `EufyVacuumManager`. |
| `rooms/room_manager.py` | Pure functions for building managed room dicts from raw discovery data. No class, no side effects. |
| `rooms/room_discovery.py` | All brand-specific room discovery logic. Reads entity IDs, attribute names, and key mappings from the adapter registry. |
| `rooms/utils.py` | `slugify_room_name()` helper. |

---

## 2. Room Discovery (`room_discovery.py`)

### 2.1 Adapter registry dependencies

All brand knowledge lives in the adapter config's `discovery` block:

| Adapter key | Description |
|---|---|
| `discovery.room_list_entity` | Which entity holds the room list. `"vacuum_entity"` means the vacuum entity itself. |
| `discovery.room_list_attribute` | State attribute name on the room_list_entity that contains the room array |
| `discovery.room_id_key` | Key for room ID within each room dict (e.g. `"id"`) |
| `discovery.room_name_key` | Key for room name within each room dict (e.g. `"name"`) |

For Eufy: `room_list_entity = "vacuum_entity"`, `room_list_attribute = "segments"`, `room_id_key = "id"`, `room_name_key = "name"`.

### 2.2 `get_active_map_id`

```python
get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None
```

Reads the active map ID from the entity declared at `adapter_config["entities"]["active_map"]`. Returns the state value as a `str`, or `None` if the adapter is not registered, the entity is missing, or its state is an HA sentinel value (`"unknown"`, `"unavailable"`, `""`, `"none"`, `"None"`).

### 2.3 `discover_rooms_for_vacuum`

```python
discover_rooms_for_vacuum(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    map_id: int | None = None,
) -> list[dict]
```

Reads the room list from the upstream entity (via `room_list_entity` and `room_list_attribute`). For each raw room entry:

1. Extracts `room_id` (from `room_id_key`) and `name` (from `room_name_key`).
2. Generates `slug = slugify_room_name(name)`.
3. De-duplicates by `room_id` — if two entries share an ID, the first wins.

Returns a list of room dicts:

```python
[
    {
        "room_id": int,
        "name":    str,
        "slug":    str,
    },
    ...
]
```

Returns `[]` if the entity is unavailable or the attribute is missing.

### 2.4 `discover_rooms_payload`

```python
discover_rooms_payload(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict
```

Convenience wrapper that returns:

```python
{
    "vacuum_entity_id": str,
    "active_map_id":    str | None,
    "room_count":       int,
    "rooms":            list[dict],
}
```

---

## 3. Room Manager Pure Functions (`room_manager.py`)

### 3.1 `build_managed_rooms`

```python
build_managed_rooms(
    discovered_rooms: list[dict],
    existing_rooms: dict[str, dict],
    enabled_room_ids: list[int] | None,
    floor_types: dict[str, str],
) -> dict[str, dict]
```

Builds the managed room dict from raw discovery data. Key is `str(room_id)`.

**For each discovered room:**

- If `enabled_room_ids` is supplied (not `None`) and the `room_id` is **not** in it, the room is **skipped** (`continue`) — it is not included in the result at all.
- If a matching room exists in `existing_rooms` (by room_id): preserves all existing user settings (fan speed, clean mode, etc.) and updates `name` and `slug` from discovery data.
- If the room is new: initializes with safe defaults — `clean_mode="vacuum"`, `fan_speed="Max"`, `water_level="Off"`, `profile_name="vacuum_quick"`, `clean_passes=1`, `edge_mopping=False`, etc.
- Sets `is_configured = True` for every room that makes it into the result — including a room in `enabled_room_ids` is the user's explicit approval. This flag is what the setup drift tracker uses to distinguish managed rooms from newly discovered ones.
- Sets `enabled = True` for new rooms (existing rooms keep their stored `enabled` value). Note: membership in `enabled_room_ids` gates *inclusion*, not the `enabled` flag.
- Sets `floor_type` from `floor_types` dict if present, otherwise defaults to `"hardwood"`.

When `enabled_room_ids` is `None`, returns the managed room dict for every room in `discovered_rooms`; when it is supplied, only those rooms are present. Rooms in `existing_rooms` that are **not** in `discovered_rooms` are **dropped** (they are stale).

### 3.2 `build_room_selection_summary`

```python
build_room_selection_summary(managed_rooms: dict[str, dict]) -> dict
```

Returns:

```python
{
    "enabled_count":   int,
    "disabled_count":  int,
    "enabled_rooms":   list[dict],   # sorted by (order, name)
    "disabled_rooms":  list[dict],   # sorted by name
}
```

---

## 4. Room Slug — `utils.py`

```python
slugify_room_name(name: str) -> str
```

Converts a raw room name to a stable slug. There is **no** regex / punctuation strip — the transform is a fixed sequence of string operations:
1. `strip()` leading/trailing whitespace.
2. Lowercase.
3. Remove single quotes `'` and double quotes `"`.
4. Replace `&` with `and`.
5. Replace each space character with a single underscore.

All other punctuation is preserved verbatim, and internal multi-space runs become multiple underscores (each space → one `_`).

Examples: `"Living Room"` → `"living_room"`, `"Bedroom #2"` → `"bedroom_#2"`, `"Kids' & Guest"` → `"kids_and_guest"`.

---

## 5. RoomMapManager (`room_crud.py`)

`RoomMapManager` is instantiated by `EufyVacuumManager` and holds a back-reference via `self.manager`. All storage reads and writes go through `self.manager.data`.

### 5.1 `discover_rooms`

```python
manager.room_map.discover_rooms(
    vacuum_entity_id: str,
    map_id: int | str | None = None,
) -> dict
```

1. Calls `get_active_map_id()` if `map_id` is not supplied.
2. Calls `discover_rooms_for_vacuum()`.
3. Caches the raw discovery result in `data["discovery"][vacuum][str(map_id)]`.
4. Updates `runtime.active_map_id` for the vacuum.

Returns the discovery payload dict.

### 5.2 `save_managed_rooms`

```python
manager.room_map.save_managed_rooms(
    vacuum_entity_id: str,
    map_id: int | str,
    enabled_room_ids: list[int] | None = None,
    floor_types: dict[str, str] | None = None,
) -> None
```

1. Reads discovery cache from `data["discovery"][vacuum][str(map_id)]`.
2. Reads existing rooms from `data["maps"][vacuum][str(map_id)]["rooms"]`.
3. Calls `build_managed_rooms()` to merge.
4. Ensures the map bucket exists via `map_manager.ensure_map_bucket()`.
5. Writes the merged rooms to `data["maps"][vacuum][str(map_id)]["rooms"]`.
6. Calls `onboarding.mark_rooms_discovered()`.
7. Calls `onboarding.confirm_floor_type()` for each room.
8. Fires `_notify_rooms_updated(vacuum, map_id)` so entity-platform callbacks rebuild HA entities.

### 5.3 `remove_map`

```python
manager.room_map.remove_map(
    vacuum_entity_id: str,
    map_id: str | int,
) -> dict
```

Removes all integration data for the (vacuum, map) pair:

1. Removes map bucket from `data["maps"][vacuum]`.
2. Removes discovery cache from `data["discovery"][vacuum][map_id_str]`.
3. Removes learning history from `data["room_history"][vacuum][map_id_str]`.
4. Removes rule state from `data["room_rule_status"][vacuum][map_id_str]`.
5. Resets the active job slot for `data["active_jobs"][vacuum][map_id_str]`.
6. Drops stale access-graph references in remaining maps where `grants_access_to` pointed to rooms on the removed map.

Returns a summary of what was removed.

### 5.4 `rebuild_map`

```python
manager.room_map.rebuild_map(
    vacuum_entity_id: str,
    map_id: str | int,
) -> None
```

Rebuilds the managed room set from the discovery cache, preserving existing room settings where possible:

1. Reads discovery cache from `data["discovery"][vacuum][map_id_str]`.
2. Reads existing rooms.
3. Calls `map_manager.rebuild_map_bucket()` with `preserve_existing_settings=True`.
4. Calls `_refresh_room_derived_state()` to re-run profile matching on all rooms.
5. Calls `_notify_rooms_updated()` to rebuild HA entities.

Does **not** reset onboarding — use `onboarding.reset_onboarding()` explicitly before `rebuild_map()` if the intent is a full reset.

---

## 6. Room Data Model

A managed room dict (stored in `data["maps"][vacuum][map_id]["rooms"][room_id_str]`) contains:

| Field | Type | Description |
|---|---|---|
| `room_id` | int | Upstream vacuum room ID |
| `name` | str | Display name from discovery |
| `slug` | str | Slugified name for stable references |
| `enabled` | bool | Whether this room is selected for the next job |
| `is_configured` | bool | True after save_rooms step ran (used by drift tracker) |
| `floor_type` | str | One of: `"hardwood"`, `"laminate"`, `"tile"`, `"marble"`, `"carpet_low_pile"`, `"carpet_high_pile"`. Carpet pile is encoded in the value — use `floor_type.startswith("carpet")` rather than a separate flag. (The old `"carpet"` + `carpet_type` shape was migrated away.) |
| `profile_name` | str | Matched room profile name, or `"custom"` |
| `clean_mode` | str | `"vacuum"`, `"mop"`, or `"vacuum_mop"` |
| `fan_speed` | str | e.g. `"Standard"` |
| `water_level` | str | e.g. `"Off"`, `"Low"`, `"Medium"`, `"High"` |
| `clean_intensity` | str | e.g. `"Standard"` |
| `clean_passes` | int | Number of cleaning passes; minimum 1. (The "1 or 2" cap is a frontend modifier constraint, not a room-model rule.) |
| `edge_mopping` | bool | Whether edge mopping is enabled |
| `path_type` | str | From matched profile |
| `order` | int | Zero-based dispatch order (defaults to a zero-based index) |
| `rules` | list | Automation rules (see [09-room-rules-system.md](09-room-rules-system.md)) |
| `grants_access_to` | list | Access graph (room IDs this room grants access to) |

---

## 7. Integration Points

| Caller | Method | When |
|---|---|---|
| `setup/workflow.py` | `discover_rooms()`, `save_managed_rooms()` | Initial map import |
| `listeners/discovery.py` | `discover_rooms()`, `save_managed_rooms()` | Auto-discovery triggers |
| `setup/drift.py` | reads discovery cache via `run_discovery_pass()` | Drift tracking |
| `rooms/room_crud.py` | `remove_map()` | Map delete workflow |
| Panel room editor | `save_managed_rooms()` | Room settings save |

> **See also:** [09-room-rules-system](09-room-rules-system.md) for rule evaluation over the room data model; [16-profile-manager](16-profile-manager.md) §6 for the finalization pipeline applied to each room on every write; [07-queue-engine](07-queue-engine.md) §5 for the access graph stored on room objects and how it cascades blocks; [17-map-manager](17-map-manager.md) for the map bucket that rooms live inside.
