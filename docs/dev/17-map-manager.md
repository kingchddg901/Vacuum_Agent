# Map Manager — Developer Reference

> **Scope:** Complete implementation reference for `maps/map_manager.py`. Every function signature, storage path, and behavior is derived directly from the source. A developer should be able to re-implement the map manager from this document alone.

---

## 1. Overview

`maps/map_manager.py` is a collection of **pure functions** with no class, no state, and no async operations. Every function takes `data` (the integration's live storage dict) as its first argument and operates on `data["maps"]` directly.

All mutations are in-place on the `data` dict. The caller is responsible for calling `manager.async_save()` after mutating.

**Module:** `custom_components/eufy_vacuum/maps/map_manager.py`

---

## 2. Map Bucket Schema

The canonical unit is a **map bucket** — a dict stored at `data["maps"][vacuum_entity_id][str(map_id)]`:

```python
{
    "map_id":   int | str,          # the map ID
    "metadata": {
        "display_name":  str | None,   # human-readable map name (user-set or derived)
        "discovered_at": str | None,   # ISO timestamp of first discovery
        ...                            # arbitrary keys from discovery snapshot
    },
    "rooms":    dict[str, dict],    # room_id_str → managed room dict
    "summary":  dict,               # last-written summary snapshot
}
```

---

## 3. Functions

### 3.1 `ensure_map_bucket`

```python
ensure_map_bucket(
    data: dict,
    vacuum_entity_id: str,
    map_id: int | str,
) -> dict
```

Creates the map bucket at `data["maps"][vacuum_entity_id][str(map_id)]` if it does not already exist. Returns the (possibly newly created) bucket dict.

**Default shape on creation:**
```python
{
    "map_id":   map_id,
    "metadata": {},
    "rooms":    {},
    "summary":  {},
}
```

Idempotent — safe to call even if the bucket already exists.

### 3.2 `get_map_bucket`

```python
get_map_bucket(
    data: dict,
    vacuum_entity_id: str,
    map_id: int | str,
) -> dict
```

Returns the existing bucket at `data["maps"][vacuum_entity_id][str(map_id)]`, or an empty default-shape dict if not found. Does **not** create the bucket in storage — read-only.

### 3.3 `save_map_discovery_snapshot`

```python
save_map_discovery_snapshot(
    data: dict,
    vacuum_entity_id: str,
    map_id: int | str,
    discovery_payload: dict,
) -> None
```

Writes the raw discovery payload into the map bucket's `metadata` field:

```python
bucket["metadata"] = discovery_payload
```

Calls `ensure_map_bucket()` first to guarantee the bucket exists.

### 3.4 `rebuild_map_bucket`

```python
rebuild_map_bucket(
    data: dict,
    vacuum_entity_id: str,
    map_id: int | str,
    discovered_rooms: list[dict],
    preserve_existing_settings: bool = True,
) -> dict
```

Rebuilds the managed rooms in the bucket from a fresh discovery list:

1. Calls `ensure_map_bucket()`.
2. Reads existing rooms from the bucket.
3. Calls `room_manager.build_managed_rooms()` with `preserve_existing_settings` controlling whether existing room settings are carried over.
4. Writes the result back to `bucket["rooms"]`.

Returns the updated bucket dict.

When `preserve_existing_settings=True` (default), user settings (fan speed, clean mode, floor type, etc.) are preserved for rooms that still exist in the discovery list. New rooms get safe defaults.

When `preserve_existing_settings=False`, all rooms are re-initialized with defaults — used for full reset flows.

### 3.5 `get_vacuum_maps_summary`

```python
get_vacuum_maps_summary(
    data: dict,
    vacuum_entity_id: str,
) -> list[dict]
```

Returns a list of summary dicts, one per map bucket that has rooms:

```python
[
    {
        "map_id":       str,
        "display_name": str,   # from metadata.display_name or "Map {map_id}"
        "room_count":   int,
    },
    ...
]
```

Maps with empty `rooms` dicts are excluded from the summary.

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
