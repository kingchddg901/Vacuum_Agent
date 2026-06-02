# Map Manager — Developer Reference

> **Scope:** Complete implementation reference for `maps/map_manager.py`. Every function signature, storage path, and behavior is derived directly from the source. A developer should be able to re-implement the map manager from this document alone.

---

## 1. Overview

`maps/map_manager.py` is a collection of **pure functions** with no class, no state, and no async operations. Every function is **keyword-only** (all parameters after `*`) and takes `data` (the integration's live storage dict), operating on `data["maps"]` directly.

All mutations are in-place on the `data` dict. The caller is responsible for calling `manager.async_save()` after mutating.

**Module:** `custom_components/eufy_vacuum/maps/map_manager.py`

---

## 2. Map Bucket Schema

The canonical unit is a **map bucket** — a dict stored at `data["maps"][vacuum_entity_id][str(map_id)]`:

```python
{
    "map_id":   str,                # the map ID, always stored as str(map_id)
    "metadata": {
        "last_discovery":   dict,   # {active_map_id, room_count} from save_map_discovery_snapshot
        "discovered_rooms": list,   # raw discovered room list from the snapshot
        "last_rebuild":     dict,   # {map_id, room_count, preserve_existing_settings} from rebuild_map_bucket
    },
    "rooms":    dict[str, dict],    # room_id_str → managed room dict
    "summary":  dict,               # last-written summary snapshot
}
```

Metadata keys are written by `save_map_discovery_snapshot()` (`last_discovery`, `discovered_rooms`) and `rebuild_map_bucket()` (`last_rebuild`). There is no `display_name` or `discovered_at` field.

---

## 3. Functions

### 3.1 `ensure_map_bucket`

```python
ensure_map_bucket(
    *,
    data: dict,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Creates the map bucket at `data["maps"][vacuum_entity_id][str(map_id)]` if it does not already exist. Returns the (possibly newly created) bucket dict.

**Default shape on creation:**
```python
{
    "map_id":   str(map_id),
    "metadata": {},
    "rooms":    {},
    "summary":  {},
}
```

Idempotent — safe to call even if the bucket already exists.

### 3.2 `get_map_bucket`

```python
get_map_bucket(
    *,
    data: dict,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Returns the existing bucket at `data["maps"][vacuum_entity_id][str(map_id)]`, or an empty default-shape dict if not found. Does **not** create the bucket in storage — read-only.

### 3.3 `save_map_discovery_snapshot`

```python
save_map_discovery_snapshot(
    *,
    data: dict,
    vacuum_entity_id: str,
    map_id: str,
    discovery_payload: dict,
) -> dict
```

Calls `ensure_map_bucket()` first, then writes two metadata keys derived from `discovery_payload`:

```python
bucket["metadata"]["last_discovery"] = {
    "active_map_id": discovery_payload.get("active_map_id"),
    "room_count":    discovery_payload.get("room_count", 0),
}
bucket["metadata"]["discovered_rooms"] = discovery_payload.get("rooms", [])
```

Returns the map bucket. It does **not** assign `discovery_payload` directly to `metadata`.

### 3.4 `rebuild_map_bucket`

```python
rebuild_map_bucket(
    *,
    data: dict,
    vacuum_entity_id: str,
    map_id: str,
    discovered_rooms: list[dict],
    preserve_existing_settings: bool = True,
) -> dict
```

Rebuilds the managed rooms in the bucket from a fresh discovery list:

1. Calls `ensure_map_bucket()`.
2. Reads existing rooms from the bucket.
3. Builds each managed room **inline** (1-indexed `order`), carrying over prior settings when `preserve_existing_settings=True`. (It does **not** call `room_manager.build_managed_rooms()`.)
4. Writes the rebuilt rooms to `bucket["rooms"]`, sets `bucket["metadata"]["last_rebuild"]`, and writes `bucket["summary"]` (enabled/disabled counts + sorted enabled/disabled room lists).

Returns a **summary dict** (not the bucket):

```python
{
    "vacuum_entity_id": str,
    "map_id":           str,
    "room_count":       int,
    "rooms":            dict[str, dict],   # the rebuilt rooms
    "summary":          dict,              # the bucket summary
    "metadata":         dict,              # the bucket metadata
}
```

When `preserve_existing_settings=True` (default), user settings (fan speed, clean mode, floor type, etc.) are preserved for rooms that still exist in the discovery list. New rooms get safe defaults. `floor_type` encodes carpet pile height in the value itself (e.g. `"carpet_low_pile"`); there is no separate `carpet_type` field.

When `preserve_existing_settings=False`, all rooms are re-initialized with defaults — used for full reset flows.

### 3.5 `get_vacuum_maps_summary`

```python
get_vacuum_maps_summary(
    *,
    data: dict,
    vacuum_entity_id: str,
) -> dict
```

Returns a **dict** wrapping a list of per-map summaries (maps sorted by `str(map_id)`):

```python
{
    "vacuum_entity_id": str,
    "map_count":        int,
    "maps": [
        {
            "map_id":              str,
            "room_count":          int,
            "enabled_room_count":  int,   # from summary.enabled_count
            "disabled_room_count": int,   # from summary.disabled_count
            "last_discovery":      dict,  # from metadata.last_discovery
        },
        ...
    ],
}
```

There is no `display_name` field. Maps with empty `rooms` dicts are **not** excluded — every map bucket is reported.

---

## 4. Storage Path Reference

| Path | Type | Description |
|---|---|---|
| `data["maps"]` | dict | Top-level map storage, keyed by vacuum_entity_id |
| `data["maps"][vacuum_entity_id]` | dict | All maps for one vacuum, keyed by str(map_id) |
| `data["maps"][vacuum_entity_id][str(map_id)]` | dict | One map bucket |
| `data["maps"][vacuum_entity_id][str(map_id)]["rooms"]` | dict | Managed rooms, keyed by str(room_id) |
| `data["maps"][vacuum_entity_id][str(map_id)]["metadata"]` | dict | Discovery snapshot + display metadata |
| `data["maps"][vacuum_entity_id][str(map_id)]["summary"]` | dict | Last written summary snapshot |

---

## 5. Integration Points

| Caller | Function | When |
|---|---|---|
| `rooms/room_crud.py` | `ensure_map_bucket()`, `rebuild_map_bucket()` | `save_managed_rooms()`, `rebuild_map()` |
| `rooms/room_crud.py` | `save_map_discovery_snapshot()` | `discover_rooms()` |
| `setup/status.py` | `get_vacuum_maps_summary()` | `get_setup_status()` |
| `setup/workflow.py` | `get_map_bucket()` | `import_active_map()` existence check |
| `setup/delete.py` | reads `data["maps"]` directly | `delete_map()` protection evaluation |

> **See also:** [15-setup-system](15-setup-system.md) §3 for the `import_active_map` workflow that calls `ensure_map_bucket()` and `rebuild_map_bucket()`; [08-rooms-system](08-rooms-system.md) §5 for `RoomMapManager` (`rooms/room_crud.py`) which reads and writes the rooms dict inside each map bucket.
