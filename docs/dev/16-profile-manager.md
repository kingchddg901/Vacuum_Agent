# Profile Manager — Developer Reference

> **Scope:** Complete implementation reference for `profiles/manager.py`. Every ID format, CRUD operation, protection rule, finalization pipeline, and storage path is derived directly from the source. A developer should be able to re-implement the profile manager from this document alone.

---

## 1. Overview

The profile manager handles two distinct but related concepts:

1. **Room profiles** — named presets for per-room cleaning settings (fan speed, clean mode, water level, etc.). Shared across all vacuums and maps. Built-in presets (Hardwood, Carpet, etc.) are protected and cannot be renamed or deleted.

2. **Run profiles** — snapshots of a complete room selection and its per-room settings for a specific (vacuum, map) pair. They let users save and restore multi-room job configurations with one tap.

**Module:** `custom_components/eufy_vacuum/profiles/manager.py`

**Built-in room profiles** defined in `profiles/room_profiles.py`:

| Profile name | clean_mode | floor type |
|---|---|---|
| Hardwood | vacuum | hard |
| Carpet | vacuum | carpet |
| Mop | mop | hard |
| Vacuum & Mop | vacuum_mop | hard |

---

## 2. ID Formats

| ID type | Format | Example |
|---|---|---|
| Room profile | `user_{YYYYMMDDTHHMMSS}` | `user_20260530T141522` |
| Run profile | `rp_{YYYYMMDDTHHMMSS}` | `rp_20260530T141522` |

Timestamps are UTC-formatted at creation time. IDs are not guaranteed globally unique — collision probability is low at human interaction rates.

---

## 3. Storage Layout

### 3.1 Room profiles

```
data["profiles"]["room_profiles"] = {
    "Hardwood":           { ...built-in fields... },
    "Carpet":             { ...built-in fields... },
    "user_20260530T...":  { ...user fields... },
}
```

Keys are the profile display names (used as both key and `profile_name` field). Built-in profiles are always present — they are seeded if missing.

### 3.2 Run profiles

```
data["run_profiles"][vacuum_entity_id][map_id_str][profile_id] = {
    "profile_id":   str,
    "label":        str,
    "rooms":        [ { ...room snapshot... } ],
    "created_at":   str,   # ISO timestamp
    "updated_at":   str,   # ISO timestamp
}
```

---

## 4. Protected Room Profiles

```python
_PROTECTED_ROOM_PROFILE_NAMES = frozenset(BUILT_IN_ROOM_PROFILES.keys())
# → frozenset({"Hardwood", "Carpet", "Mop", "Vacuum & Mop"})
```

Any operation that would rename, delete, or overwrite a protected profile raises `ValueError`. This check applies to:
- `delete_room_profile(profile_name)`
- `rename_room_profile(old_name, new_name)` — both old name (if protected) and new name (if it would collide with a protected name)
- `save_room_profile(profile_name, ...)` when `overwrite=False` and the name is protected

---

## 5. Room Profile Operations

### 5.1 `get_room_profiles`

```python
manager.get_room_profiles() -> dict[str, dict]
```

Returns all room profiles (built-ins + user-created) as a dict keyed by profile name. The built-ins are always present.

### 5.2 `save_room_profile`

```python
manager.save_room_profile(
    profile_name: str,
    fields: dict,
    *,
    overwrite: bool = False,
) -> str
```

Creates a new room profile. If `overwrite=True`, replaces an existing user profile with the same name. Protected names always block overwrite.

Returns the profile name (key).

### 5.3 `rename_room_profile`

```python
manager.rename_room_profile(old_name: str, new_name: str) -> None
```

Renames a user profile:
1. Rejects if `old_name` is protected.
2. Rejects if `new_name` would collide with any existing profile (protected or user).
3. Copies the dict to the new key, deletes the old key.
4. Updates the `profile_name` field inside the dict.

### 5.4 `delete_room_profile`

```python
manager.delete_room_profile(profile_name: str) -> None
```

Deletes a user room profile. Raises `ValueError` for protected names.

---

## 6. Room Profile Finalization Pipeline

When a room's settings are saved (via `update_room_settings()` or initial import), the settings pass through a two-stage pipeline:

### Stage 1 — `_protected_room_config(room: dict) -> dict`

Enforces carpet/mop invariants:

```
if room["floor_type"] == "carpet":
    if clean_mode in {"mop", "vacuum_mop"}:
        clean_mode = "vacuum"         # downgrade to vacuum-only
    water_level  = "Off"
    edge_mopping = False

else (hard floor):
    if clean_mode not in mop-capable modes:
        water_level  = "Off"
        edge_mopping = False
```

The rule is: carpet rooms can never mop. Non-mop modes on hard floors can never have water or edge mopping enabled.

### Stage 2 — `_finalize_room_update(room: dict) -> dict`

```
1. _protected_room_config(room)            # apply carpet/mop invariants
2. resolve_room_profile_for_room(room)     # match profile by floor_type
3. sync path_type from profile             # apply profile's path_type to room
4. _match_profile_from_fields(room)        # find matching named profile
5. set profile_name = matched name or "custom"
```

`_match_profile_from_fields` scans all room profiles looking for one whose fields exactly match the room's current `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, and `edge_mopping`. If found, `profile_name` is set to the matching profile name. If not found, `profile_name = "custom"`.

---

## 7. Run Profile Operations

### 7.1 `get_run_profiles`

```python
manager.get_run_profiles(
    vacuum_entity_id: str,
    map_id: str | int,
) -> dict[str, dict]
```

Returns all run profiles for the (vacuum, map) pair. Returns `{}` if none exist.

### 7.2 `save_run_profile`

```python
manager.save_run_profile(
    vacuum_entity_id: str,
    map_id: str | int,
    label: str,
    rooms: list[dict],   # list of room dicts from current room selection
) -> str
```

Creates a new run profile. Snapshots each selected room using `_snapshot_room_for_run_profile()`. Returns the new `profile_id`.

**Room snapshot fields:**

| Field | Source |
|---|---|
| `room_id` | room dict |
| `name` | room dict |
| `profile_name` | room dict |
| `clean_mode` | room dict |
| `fan_speed` | room dict |
| `water_level` | room dict |
| `clean_intensity` | room dict |
| `clean_passes` | room dict |
| `edge_mopping` | room dict |
| `order` | room dict (1-indexed) |

### 7.3 `overwrite_run_profile`

```python
manager.overwrite_run_profile(
    vacuum_entity_id: str,
    map_id: str | int,
    profile_id: str,
    rooms: list[dict],
) -> None
```

Replaces the rooms snapshot in an existing run profile. Preserves `label`, `profile_id`, and `created_at`. Updates `updated_at`.

### 7.4 `rename_run_profile`

```python
manager.rename_run_profile(
    vacuum_entity_id: str,
    map_id: str | int,
    profile_id: str,
    new_label: str,
) -> None
```

Updates the `label` field. Raises `KeyError` if `profile_id` not found.

### 7.5 `delete_run_profile`

```python
manager.delete_run_profile(
    vacuum_entity_id: str,
    map_id: str | int,
    profile_id: str,
) -> None
```

Removes the run profile from storage. No-ops if not found.

### 7.6 `apply_run_profile`

```python
manager.apply_run_profile(
    vacuum_entity_id: str,
    map_id: str | int,
    profile_id: str,
) -> dict
```

Restores a saved room selection to the live room data:

1. Disables **all** rooms for the (vacuum, map) pair.
2. For each room in the profile's `rooms` list:
   - Looks up the room by `room_id` in `data["maps"][vacuum][map_id]["rooms"]`.
   - Enables the room.
   - Restores saved settings: `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping`, `order`.
   - Runs `_finalize_room_update()` on the restored room.

Returns a summary with `applied_count`, `skipped_count` (rooms no longer on the map), and `map_id`.

---

## 8. Integration Points

| Caller | Method | When |
|---|---|---|
| Panel room editor | `get_room_profiles()`, `save_room_profile()`, `rename_room_profile()`, `delete_room_profile()` | Room settings save/edit |
| Panel run profile tab | `get_run_profiles()`, `save_run_profile()`, `apply_run_profile()`, `rename_run_profile()`, `delete_run_profile()` | Run profile CRUD |
| `rooms/room_crud.py` | `_finalize_room_update()` | Every room settings write |
| Panel initial map import | `_finalize_room_update()` (via save_managed_rooms) | Room creation on import |

> **See also:** [08-rooms-system](08-rooms-system.md) §6 for the room data model that profiles are merged into; [07-queue-engine](07-queue-engine.md) §4 for how run profiles are resolved at queue build time before the payload is sent to the vacuum.
