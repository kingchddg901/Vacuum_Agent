# Onboarding Manager — Developer Reference

> **Scope:** Complete implementation reference for `onboarding/manager.py`. Every state machine, storage path, predicate, and public method is derived directly from the source. A developer should be able to re-implement the onboarding manager from this document alone.

---

## 1. Overview

The onboarding manager tracks the per-vacuum, per-map setup state that determines whether a vacuum is ready to accept scheduled cleaning jobs. It answers two questions:

1. **Have all rooms been discovered?** — has the `save_rooms` setup step run at least once for this map?
2. **Have all room floor types been confirmed?** — has the user assigned a floor type (hardwood/carpet) to every room?

When both are true, onboarding is complete for that (vacuum, map) pair and the panel's job-scheduling UI unlocks.

The manager also detects **new rooms** (room count increased since last check) and **map rebuilds** (map bucket was replaced) so the panel can surface notifications prompting the user to re-confirm floor types.

**Module:** `custom_components/eufy_vacuum/onboarding/manager.py`

**Constructor:** `OnboardingManager(data: dict, hass: HomeAssistant)`

Note: Unlike most managers, `OnboardingManager` takes `data` and `hass` directly — it holds **no back-reference** to `EufyVacuumManager`. This keeps it testable in isolation.

---

## 2. Storage Layout

```
data["onboarding"][vacuum_entity_id][str(map_id)] = {
    "rooms_discovered":           bool,   # True after save_rooms step completes
    "floor_types_confirmed":      dict,   # {room_id_str: bool} — True when confirmed
    "room_count_at_last_check":   int,    # room count at last check_for_new_rooms call
    "discovery_notified":         bool,   # True after new-room notification fired
    "rebuild_notified":           bool,   # True after map-rebuild notification fired
}
```

**Default on first access:**
```python
{
    "rooms_discovered":         False,
    "floor_types_confirmed":    {},
    "room_count_at_last_check": 0,
    "discovery_notified":       False,
    "rebuild_notified":         False,
}
```

The storage is created lazily per vacuum per map. Missing keys default to their False/empty defaults via `setdefault`.

---

## 3. Onboarding State Machine

### 3.1 Completion predicate

```
onboarding_complete = rooms_discovered AND floor_types_complete

floor_types_complete = all(
    floor_types_confirmed[room_id] == True
    for room_id in managed_rooms[vacuum][map_id]
)
```

If no rooms exist, `floor_types_complete` is False (no rooms → not complete).

### 3.2 `get_onboarding_state`

```python
manager.get_onboarding_state(
    vacuum_entity_id: str,
    map_id: int | str,
) -> dict
```

Returns:

```python
{
    "status":                  str,    # see below
    "rooms_discovered":        bool,
    "floor_types_complete":    bool,
    "unconfirmed_room_ids":    list[str],   # room IDs missing floor type
    "onboarding_complete":     bool,
}
```

**Status values:**

| Status | Condition |
|---|---|
| `"complete"` | `rooms_discovered` AND `floor_types_complete` |
| `"floor_type_needed"` | `rooms_discovered` but one or more rooms lack a confirmed floor type |
| `"rooms_needed"` | `rooms_discovered` is False |

---

## 4. Manager Methods

### 4.1 `mark_rooms_discovered`

```python
manager.mark_rooms_discovered(
    vacuum_entity_id: str,
    map_id: int | str,
) -> None
```

Sets `data["onboarding"][vacuum][map_id]["rooms_discovered"] = True`. Called by `RoomMapManager.save_managed_rooms()` after rooms are written.

### 4.2 `confirm_floor_type`

```python
manager.confirm_floor_type(
    vacuum_entity_id: str,
    map_id: int | str,
    room_id: str | int,
    confirmed: bool = True,
) -> None
```

Sets `floor_types_confirmed[str(room_id)] = confirmed`. Called once per room by `save_managed_rooms()` during initial import.

The user can also call this via the panel's room editor to re-confirm after a floor type change.

### 4.3 `check_for_new_rooms`

```python
manager.check_for_new_rooms(
    vacuum_entity_id: str,
    map_id: int | str,
) -> dict
```

Reads the current room count from `vacuum.attributes.segments` and compares it to `room_count_at_last_check`. Updates the stored count on every call.

Returns:

```python
{
    "new_rooms_detected": bool,
    "previous_count":     int,
    "current_count":      int,
    "delta":              int,     # current_count - previous_count
}
```

**New rooms detected** when `current_count > previous_count`. The caller (typically `listeners/discovery.py`) decides whether to show a notification.

### 4.4 `reset_onboarding`

```python
manager.reset_onboarding(
    vacuum_entity_id: str,
    map_id: int | str,
) -> None
```

Clears all flags for the (vacuum, map) pair back to defaults:

```python
data["onboarding"][vacuum][map_id] = {
    "rooms_discovered":         False,
    "floor_types_confirmed":    {},
    "room_count_at_last_check": 0,
    "discovery_notified":       False,
    "rebuild_notified":         False,
}
```

Called by `RoomMapManager.rebuild_map()` when a map is rebuilt from scratch.

### 4.5 `set_discovery_notified` / `set_rebuild_notified`

```python
manager.set_discovery_notified(vacuum_entity_id: str, map_id: str, value: bool = True) -> None
manager.set_rebuild_notified(vacuum_entity_id: str, map_id: str, value: bool = True) -> None
```

Sets the respective notification-sent flag. Used to avoid sending the same notification repeatedly on consecutive discovery passes.

---

## 5. Floor Type Semantics

Floor type confirmation is per-room, not per-map. The `floor_types_confirmed` dict maps room ID strings to booleans:

```python
{"1": True, "2": True, "3": False}
```

A room with `confirmed == False` or missing from the dict counts as unconfirmed. Unconfirmed rooms block the `"complete"` status but do **not** block jobs from running — they surface as warnings in the panel.

---

## 6. Integration Points

| Caller | Method | When |
|---|---|---|
| `RoomMapManager.save_managed_rooms()` | `mark_rooms_discovered()`, `confirm_floor_type()` | After rooms written to storage |
| `RoomMapManager.rebuild_map()` | `reset_onboarding()` | Map rebuild from scratch |
| `listeners/discovery.py` | `check_for_new_rooms()` | After each discovery pass |
| Panel setup tab | `get_onboarding_state()` | On render |
| Panel room editor | `confirm_floor_type()` | User saves floor type |
