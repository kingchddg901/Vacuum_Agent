# Profile Manager — Developer Reference

> **Scope:** Complete implementation reference for `profiles/manager.py`. Every ID format, CRUD operation, protection rule, finalization pipeline, and storage path is derived directly from the source. A developer should be able to re-implement the profile manager from this document alone.

---

## 1. Overview

The profile manager handles two distinct but related concepts:

1. **Room profiles** — named presets for per-room cleaning settings (fan speed, clean mode, water level, etc.). Shared across all vacuums and maps. The four built-in presets (`vacuum_quick`, `vacuum_deep`, `vacuum_mop_quick`, `vacuum_mop_deep`) are protected and cannot be renamed, deleted, or overwritten.

2. **Run profiles** — snapshots of a complete room selection and its per-room settings for a specific (vacuum, map) pair. They let users save and restore multi-room job configurations with one tap.

**Module:** `custom_components/eufy_vacuum/profiles/manager.py`

**Built-in room profiles** (`BUILT_IN_ROOM_PROFILES` in `profiles/room_profiles.py`):

| Profile key | label | clean_mode | fan_speed | water_level | clean_intensity | path_type | clean_passes | edge_mopping | mop_required |
|---|---|---|---|---|---|---|---|---|---|
| `vacuum_quick` | Vacuum Only Quick | vacuum | Standard | Off | Quick | wide | 1 | False | False |
| `vacuum_deep` | Vacuum Only Deep | vacuum | Max | Off | Deep | narrow | 2 | False | False |
| `vacuum_mop_quick` | Quick | vacuum_mop | Standard | Medium | Quick | wide | 1 | False | True |
| `vacuum_mop_deep` | Deep | vacuum_mop | Max | Medium | Deep | narrow | 2 | True | True |

`get_default_room_profiles()` also seeds a legacy user slot `user_1` (from `DEFAULT_CUSTOM_ROOM_PROFILE`). Legacy aliases `vacuum_standard`→`vacuum_quick` and `vacuum_mop_standard`→`vacuum_mop_quick` are resolved at lookup time. The default profile a newly-discovered room gets is `DEFAULT_ROOM_PROFILE_NAME = "vacuum_quick"`.

> **Framework default vs. adapter catalog.** The in-code constants (`BUILT_IN_ROOM_PROFILES`, `DEFAULT_CUSTOM_ROOM_PROFILE`, `LEGACY_PROFILE_ALIASES`, `FLOOR_TYPE_*_DEFAULTS`, `DEFAULT_ROOM_PROFILE_NAME`) are the **framework default catalog** AND remain the authoritative source of `_PROTECTED_ROOM_PROFILE_NAMES`. An adapter's optional `room_profiles` block can override any subset of them **per-vacuum** at *resolution* time via `resolve_profile_catalog()` — see §1.1. The Eufy adapter declares `room_profiles` *by reference* to these constants (no duplication), so Eufy output is byte-identical.

---

## 1.1 Adapter-Sourced Profile Catalog

`resolve_profile_catalog(block)` (in `profiles/room_profiles.py`) merges an adapter `room_profiles` block over the in-code defaults **per key**, returning a catalog dict:

| Catalog key | In-code default |
|---|---|
| `builtins` | `BUILT_IN_ROOM_PROFILES` |
| `custom_template` | `DEFAULT_CUSTOM_ROOM_PROFILE` |
| `legacy_aliases` | `LEGACY_PROFILE_ALIASES` |
| `default_profile` | `DEFAULT_ROOM_PROFILE_NAME` (`"vacuum_quick"`) |
| `floor_type_water_defaults` | `FLOOR_TYPE_WATER_DEFAULTS` |
| `floor_type_fan_defaults` | `FLOOR_TYPE_FAN_DEFAULTS` |
| `normalize_defaults` | `DEFAULT_CUSTOM_ROOM_PROFILE` |

A `None`/empty block returns the in-code defaults **verbatim**, so a vacuum without the block resolves byte-identically. The catalog is **resolution-only** — it does not touch the `_PROTECTED_ROOM_PROFILE_NAMES` binding (§4), which stays bound to the in-code `BUILT_IN_ROOM_PROFILES` at module load.

**Optional `catalog` param.** Every resolver function in `room_profiles.py` now takes an optional `catalog` (a resolved block); `None` falls back to the in-code constants. The functions: `get_default_room_profiles`, `normalize_room_profile`, `merge_profile_dicts`, `_normalize_profile_name`, `resolve_profile_name_for_constraints`, `get_room_profile`, `get_available_profiles`, `resolve_room_profile_for_room`, and `apply_capability_gate` (§6.1).

**Where it is wired (deliberate boundary).**

| Site | Catalog source | Rationale |
|---|---|---|
| Dispatch — `queue/queue_engine.py:build_room_clean_payload` | adapter (`get_adapter_config(vacuum_entity_id)` → `resolve_profile_catalog` → threaded into `resolve_room_profile_for_room` + `apply_capability_gate`) | has per-vacuum context; per-room dispatch settings must be adapter-catalog-sourced |
| Global profile editor — `manager.py` (`get_room_profiles`, `_finalize_room_update`, `_match_profile_from_fields`) | framework default (`catalog=None`) | the singleton editor lacks per-vacuum context |
| Pure room-builder — `rooms/room_manager.py` (`build_managed_rooms`), `room_entities` display fallback | framework default (`catalog=None`) | no per-vacuum context at build time |

Byte-identical for Eufy throughout. A second brand's dispatched per-room settings already honor its catalog; its *editor UI* would show framework defaults until those editor methods are threaded — a documented follow-up.

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
    "user_1":             { ...user fields... },
    "user_20260530T...":  { ...user fields... },
}
```

Only **user-created** profiles are stored here. The four built-ins are not persisted — `get_room_profiles()` merges them over the stored profiles at read time via `merge_profile_dicts()`. The store key is also the `profile_name`.

### 3.2 Run profiles

```
data["run_profiles"][vacuum_entity_id][map_id_str][profile_id] = {
    "id":                str,        # == profile_id (the store key)
    "name":              str,        # display name
    "vacuum_entity_id":  str,
    "map_id":            str,
    "room_count":        int,
    "room_ids":          list[int],
    "room_names":        list[str],
    "room_names_label":  str,        # ", "-joined room names
    "expose_as_button":  bool,
    "rooms":             [ { ...room snapshot... } ],
    "created_at":        str,        # ISO timestamp
    "updated_at":        str,        # ISO timestamp
}
```

---

## 4. Protected Room Profiles

```python
_PROTECTED_ROOM_PROFILE_NAMES = frozenset(BUILT_IN_ROOM_PROFILES.keys())
# → frozenset({"vacuum_quick", "vacuum_deep", "vacuum_mop_quick", "vacuum_mop_deep"})
```

This binds at **module load** to the in-code `BUILT_IN_ROOM_PROFILES` and is **untouched** by the adapter-catalog mechanism (§1.1) — `resolve_profile_catalog()` only affects *resolution*, never the protected-name set.

Any operation that would rename, delete, or overwrite a protected profile **returns a result dict** with `reason="protected_profile"` and the relevant action flag set `False` (e.g. `{"deleted": False, "reason": "protected_profile", ...}`). These methods do **not** raise `ValueError`. The check applies to:
- `delete_room_profile(*, profile_name)`
- `rename_room_profile(*, profile_name, ...)` — both the source name (if protected) and a target name that would collide with a protected name
- `save_user_room_profile(*, ..., profile_name=...)` and `overwrite_room_profile(*, profile_name, ...)` when the target name is protected

---

## 5. Room Profile Operations

All room-profile CRUD methods are **keyword-only** and return **result dicts** (never raise for protected/not-found cases).

### 5.1 `get_room_profiles`

```python
manager.get_room_profiles() -> dict
# → {
#     "profile_count": int,
#     "profiles": { profile_name: {label, clean_mode, fan_speed, ...}, ... },  # built-ins merged over stored
#     "protected_profile_names": sorted(list[str]),
#   }
```

Built-ins are merged over the stored user profiles via `merge_profile_dicts()`, so they are always present in `profiles`.

### 5.2 `save_user_room_profile` / `overwrite_room_profile`

```python
manager.save_user_room_profile(
    *,
    label: str,
    clean_mode: str,
    fan_speed: str,
    water_level: str,
    clean_intensity: str,
    clean_passes: int,
    edge_mopping: bool,
    profile_name: str | None = None,   # defaults to "user_1"
) -> dict
# → {"saved": True, "profile_name": str, "profile": dict}
#   or {"saved": False, "reason": "protected_profile", ...}
```

Writes a normalized profile into `data["profiles"]["room_profiles"]`. A protected `profile_name` is rejected with `reason="protected_profile"`.

```python
manager.overwrite_room_profile(
    *,
    profile_name: str,
    label: str, clean_mode: str, fan_speed: str, water_level: str,
    clean_intensity: str, clean_passes: int, edge_mopping: bool,
) -> dict
# → {"overwritten": bool, "profile_name": str, "profile": dict, "reason": ..., "message": ...}
```

Requires an existing editable profile — returns `reason="profile_not_found"` if absent, `reason="protected_profile"` if protected. Delegates the write to `save_user_room_profile()`.

There are also `save_room_profile_from_room(*, vacuum_entity_id, map_id, room_id, label, profile_name=None)` and `overwrite_room_profile_from_room(*, vacuum_entity_id, map_id, room_id, profile_name, label=None)`, which snapshot a room's current effective settings into a profile.

### 5.3 `rename_room_profile`

```python
manager.rename_room_profile(
    *,
    profile_name: str,
    new_profile_name: str | None = None,
    label: str | None = None,
) -> dict
# → {"renamed": True, "profile_name": str, "previous_profile_name": str, "profile": dict}
#   or {"renamed": False, "reason": ...}
```

Renames a user profile and/or updates its display label:
1. Rejects with `reason="protected_profile"` if `profile_name` is protected.
2. Rejects with `reason="profile_not_found"` if no such editable profile exists.
3. Rejects with `reason="protected_profile"` if `new_profile_name` collides with a protected name, or `reason="profile_name_exists"` if it collides with another stored profile.
4. Copies the dict to the new key, deletes the old key, and (if `label` is given and non-empty) updates the `label` field.

### 5.4 `delete_room_profile`

```python
manager.delete_room_profile(*, profile_name: str) -> dict
# → {"deleted": True, "profile_name": str}
#   or {"deleted": False, "reason": "protected_profile" | "profile_not_found", ...}
```

Deletes a user room profile. Returns `reason="protected_profile"` for built-ins, `reason="profile_not_found"` if absent.

---

## 6. Room Profile Finalization Pipeline

When a room's settings are saved (via `update_room_settings()` or initial import), the settings pass through a two-stage pipeline:

### Stage 1 — `_protected_room_config(room: dict) -> dict`

Enforces carpet/mop invariants. Carpet is detected with `floor_type.startswith("carpet")` (canonical values `carpet_low_pile` / `carpet_high_pile`; bare `"carpet"` is a legacy value migrated elsewhere). Mop mode is detected as `"mop" in clean_mode or "wash" in clean_mode`.

```
is_carpet  = floor_type.startswith("carpet")
is_mop_mode = ("mop" in clean_mode) or ("wash" in clean_mode)

if is_carpet:
    if clean_mode in {"mop", "vacuum_mop"}:
        clean_mode  = "vacuum"        # downgrade to vacuum-only
        is_mop_mode = False
    water_level  = "Off"
    edge_mopping = False

if not is_mop_mode:                   # applies on ANY floor type
    water_level  = "Off"
    edge_mopping = False
```

The rule is: carpet rooms can never mop (water/edge always cleared on carpet), and **any** non-mop mode — regardless of floor type — clears water and edge mopping.

### Stage 2 — `_finalize_room_update(room: dict) -> dict`

```
1. _protected_room_config(room)            # apply carpet/mop invariants
2. resolve_room_profile_for_room(room)     # match profile by floor_type
3. sync path_type from profile             # apply profile's path_type to room
4. _match_profile_from_fields(room)        # find matching named profile
5. set profile_name = matched name or "custom"
```

`_match_profile_from_fields` scans all room profiles looking for one whose fields exactly match the room's current `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, and `edge_mopping`. If found, `profile_name` is set to the matching profile name. If not found, `profile_name = "custom"`.

> The two-stage pipeline above produces **display/storage** values. A separate, capability-aware stage (`apply_capability_gate`) runs later at **payload-build time** — see §6.1.

### 6.1 — `apply_capability_gate(settings, capabilities, *, resolved_profile_name=None, catalog=None)`

`apply_capability_gate` lives in `profiles/room_profiles.py` (not the manager) and runs at **payload-build time, not during profile resolution** — the resolver produces display/storage values, gating is strictly a payload concern. It returns a new dict (input not mutated) and clamps every field to what the device actually supports, reading the `supports_*` flags from the adapter `capabilities`:

| Capability flag | Effect when `False` |
|---|---|
| `supports_water_control` | `water_level → "Off"` |
| `supports_edge_mopping` | `edge_mopping → False` |
| `supports_path_control` | `path_type → "wide"` |
| `supports_passes` (default `True`) | `clean_passes → 1` |

**Mop → vacuum downgrade.** When the device lacks `supports_mop_features` and the room is in a mop mode (`clean_mode in {"mop", "vacuum_mop"}`), the room is downgraded to vacuum-only. The downgrade **derives `path_type` and `clean_intensity` from the corresponding vacuum-only built-in profile** (via `get_room_profile`, passed the same `catalog`) rather than hardcoding values, so it follows whatever vocabulary the profile catalog declares:

```
if not supports_mop and clean_mode in {"mop", "vacuum_mop"}:
    fallback_name = "vacuum_deep" if resolved_profile_name == "vacuum_mop_deep" else "vacuum_quick"
    _, fallback = get_room_profile(profile_name=fallback_name, catalog=catalog)
    clean_mode      = "vacuum"
    water_level     = "Off"
    edge_mopping    = False
    path_type       = fallback.get("path_type", path_type)        # was hardcoded "narrow"/"wide"
    clean_intensity = fallback.get("clean_intensity", clean_intensity)  # was hardcoded "Deep"/"Quick"
```

The `resolved_profile_name` argument selects which vacuum profile to mirror: a deep mop profile (`vacuum_mop_deep`) maps to `vacuum_deep`, everything else maps to `vacuum_quick`. The optional `catalog` argument (§1.1) sources that fallback profile from the adapter's catalog when present (the dispatch path threads it in; `None` → in-code built-ins). With today's Eufy built-ins (§1) this yields the same `narrow`/`Deep` and `wide`/`Quick` values the code used to hardcode — so Eufy output is byte-identical — but a future brand whose catalog declares different `path_type`/`clean_intensity` vocabulary gets the right downgrade for free. After the downgrade (or for any room already in `clean_mode == "vacuum"`), `water_level` and `edge_mopping` are forced off. The returned dict carries `capability_gated: True`.

---

## 7. Run Profile Operations

All run-profile methods are **keyword-only** and return **result dicts**.

### 7.1 `get_saved_run_profiles`

```python
manager.get_saved_run_profiles(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
# → {
#     "vacuum_entity_id": str,
#     "map_id": str,
#     "profile_count": int,
#     "profiles": [ {id, name, room_count, room_ids, room_names,
#                    room_names_label, expose_as_button, created_at,
#                    updated_at, summary}, ... ],   # sorted by name
#     "library": { profile_id: {enriched profile}, ... },
#   }
```

### 7.2 `save_run_profile`

```python
manager.save_run_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    name: str,
    expose_as_button: bool = False,
) -> dict
# → {"saved": True, "profile_id": str, "profile": {enriched}}
#   or {"saved": False, "reason": "missing_name" | "no_rooms_selected"}
```

The caller does **not** pass rooms — `save_run_profile` snapshots the **current enabled rooms** (in queue order) itself via `_current_enabled_rooms_for_run_profile()` + `_snapshot_room_for_run_profile()`. Returns `reason="no_rooms_selected"` when no rooms are enabled.

**Room snapshot fields** (from `_snapshot_room_for_run_profile`):

| Field | Source |
|---|---|
| `room_id` | room dict (`room_id` or `id`) |
| `name` | room dict |
| `profile_name` | room dict (default `"vacuum_quick"`) |
| `clean_mode` | room dict |
| `fan_speed` | room dict |
| `water_level` | room dict |
| `clean_intensity` | room dict |
| `clean_passes` | room dict |
| `edge_mopping` | room dict |
| `order` | room dict (default 999) |

### 7.3 `overwrite_run_profile`

```python
manager.overwrite_run_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    profile_id: str,
    name: str | None = None,
    expose_as_button: bool | None = None,
) -> dict
# → {"overwritten": True, "profile_id": str, "profile": {enriched}}
#   or {"overwritten": False, "reason": "profile_not_found" | "no_rooms_selected"}
```

Re-snapshots the current enabled rooms into an existing run profile. Preserves `id` and `created_at`; updates `updated_at`. `name`/`expose_as_button` keep their existing value when passed `None`.

### 7.4 `rename_run_profile`

```python
manager.rename_run_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    profile_id: str,
    name: str,
) -> dict
# → {"renamed": True, "profile_id": str, "profile": {enriched}}
#   or {"renamed": False, "reason": "profile_not_found"}
```

Updates the `name` field (blank → `"Untitled"`) and `updated_at`. Returns `reason="profile_not_found"` if absent (does not raise).

### 7.5 `delete_run_profile`

```python
manager.delete_run_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    profile_id: str,
) -> dict
# → {"deleted": True, "profile_id": str}
#   or {"deleted": False, "reason": "profile_not_found"}
```

### 7.6 `apply_run_profile`

```python
manager.apply_run_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    profile_id: str,
) -> dict
# → {
#     "vacuum_entity_id": str,
#     "map_id": str,
#     "applied": bool,              # True if any room was applied
#     "profile_id": str,
#     "profile": dict,
#     "applied_room_ids": list[int],
#     "missing_room_ids": list[int],  # snapshot rooms no longer on the map
#   }
#   or {"applied": False, "reason": "profile_not_found", ...}
```

Restores a saved room selection to the live room data:

1. Disables **all** rooms for the (vacuum, map) pair.
2. For each room in the profile's `rooms` list (enumerated 1-indexed for `order`):
   - Looks up the room by `room_id` in `data["maps"][vacuum][map_id]["rooms"]`. If absent, the id is added to `missing_room_ids` and skipped.
   - Enables the room and restores saved settings: `profile_name`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping`, plus the enumeration `order`.
   - Runs `_finalize_room_update()` on the restored room.

---

## 8. Integration Points

| Caller | Method | When |
|---|---|---|
| Panel room editor | `get_room_profiles()`, `save_user_room_profile()`, `overwrite_room_profile()`, `rename_room_profile()`, `delete_room_profile()` | Room settings save/edit |
| Panel run profile tab | `get_saved_run_profiles()`, `save_run_profile()`, `apply_run_profile()`, `rename_run_profile()`, `delete_run_profile()` | Run profile CRUD |
| `rooms/room_crud.py` | `_finalize_room_update()` | Every room settings write |
| Panel initial map import | `_finalize_room_update()` (via save_managed_rooms) | Room creation on import |

> **See also:** [08-rooms-system](08-rooms-system.md) §6 for the room data model that profiles are merged into; [07-queue-engine](07-queue-engine.md) §4 for how run profiles are resolved at queue build time before the payload is sent to the vacuum.
