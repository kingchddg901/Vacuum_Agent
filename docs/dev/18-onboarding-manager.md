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
rooms_discovered     = stored_flag AND len(rooms) > 0
floor_types_complete = len(enabled_rooms_needing_floor_type) == 0
onboarding_complete  = rooms_discovered AND floor_types_complete
```

Only **enabled** rooms are inspected for floor-type confirmation; disabled rooms are skipped. A room needs a floor type when it is enabled and `floor_types_confirmed[room_id]` is not `True`.

`rooms_discovered` requires both the stored `rooms_discovered` flag **and** `len(rooms) > 0` — the stored flag alone is not sufficient if the map currently has no rooms.

### 3.2 `get_onboarding_state`

```python
manager.get_onboarding_state(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Keyword-only. Returns:

```python
{
    "vacuum_entity_id":                  str,
    "map_id":                            str,
    "rooms_discovered":                  bool,
    "room_count":                        int,        # len(rooms) on the map
    "floor_types_complete":              bool,
    "onboarding_complete":               bool,
    "enabled_rooms_needing_floor_type":  list[str],  # enabled room IDs missing a confirmed floor type
    "status":                            str,        # see below
}
```

There is no `unconfirmed_room_ids` key — the field is `enabled_rooms_needing_floor_type`.

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
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> None
```

Sets `data["onboarding"][vacuum][map_id]["rooms_discovered"] = True` and stamps `room_count_at_last_check` with the current room count. Called by `RoomMapManager.save_managed_rooms()` after rooms are written.

### 4.2 `confirm_floor_type`

```python
manager.confirm_floor_type(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_id: str,
) -> None
```

Keyword-only. Always sets `floor_types_confirmed[str(room_id)] = True` — there is **no** `confirmed` parameter (the method can only confirm, not un-confirm). Called once per room by `save_managed_rooms()` during initial import.

The user can also call this via the panel's room editor to re-confirm after a floor type change.

### 4.3 `check_for_new_rooms`

```python
manager.check_for_new_rooms(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> bool
```

Reads the current room count from the adapter-declared discovery source (`adapter_config["discovery"]["room_list_entity"]` / `["room_list_attribute"]`, defaulting to the vacuum entity's `segments` attribute) and compares it to the stored `room_count_at_last_check`. Returns a plain **bool**: `True` when `current_count > last_count`. Returns `False` if the source state is missing or the attribute is not a list. It does **not** update the stored count.

It is exposed on `EufyVacuumManager` via a thin delegation wrapper (`EufyVacuumManager.check_for_new_rooms`). It has no live in-framework caller today — the auto-discovery path that keeps drift fresh (`listeners/discovery.py` → `setup/drift.py::run_discovery_pass`) uses the counter-based room-drift history (see [22-adapter-config-reference §12](22-adapter-config-reference.md)), not this single-shot count comparison. A caller would decide whether to show a notification.

### 4.4 `reset_onboarding`

```python
manager.reset_onboarding(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Clears all flags for the (vacuum, map) pair back to defaults and returns a result dict:

```python
# resets data["onboarding"][vacuum][map_id] to:
{
    "rooms_discovered":         False,
    "floor_types_confirmed":    {},
    "room_count_at_last_check": 0,
    "discovery_notified":       False,
    "rebuild_notified":         False,
}
# returns:
{"vacuum_entity_id": str, "map_id": str, "reset": True}
```

Exposed on `EufyVacuumManager` via a thin delegation wrapper (`EufyVacuumManager.reset_onboarding`); intended for the map-rebuild-from-scratch flow. It has no live in-framework caller today — `RoomMapManager.rebuild_map()` rebuilds the map bucket but does **not** currently reset onboarding state.

### 4.5 `get_rooms_onboarding_summary`

```python
manager.get_rooms_onboarding_summary(
    *,
    vacuum_entity_id: str,
) -> dict
```

Aggregates `get_onboarding_state()` across every known map for one vacuum:

```python
{
    "vacuum_entity_id": str,
    "all_complete":     bool,        # True only if every map is onboarding_complete
    "maps":             list[dict],  # one get_onboarding_state() result per map
}
```

(There are no `set_discovery_notified` / `set_rebuild_notified` methods. The `discovery_notified` / `rebuild_notified` flags exist in storage but are only written by `reset_onboarding` / defaults.)

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
| `EufyVacuumManager` delegation only (no live caller) | `reset_onboarding()` | Intended for map rebuild from scratch — not yet wired |
| `EufyVacuumManager` delegation only (no live caller) | `check_for_new_rooms()` | Predicate; the live drift path uses `setup/drift.py` instead |
| Panel setup tab | `get_onboarding_state()` | On render |
| Panel room editor | `confirm_floor_type()` | User saves floor type |
