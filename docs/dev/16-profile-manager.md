# 16 — Profile Manager

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

`get_default_room_profiles()` returns **only** the built-in catalog (`BUILT_IN_ROOM_PROFILES`, or the resolved catalog's `builtins`); it does **not** seed a legacy user slot `user_1`. A pristine framework-default `user_1` was deliberately removed because it surfaced as an undeletable "User Profile 1" chip in the room editor — it lived in no user store, so a delete found nothing (`profile_not_found`) and it reappeared on every fetch. A `user_1` exists only when a user has explicitly saved over it, in which case it lives in the stored profiles and is returned by `merge_profile_dicts()` as real, deletable data. The starting-settings template `DEFAULT_CUSTOM_ROOM_PROFILE` remains available as the resolved catalog's `custom_template` for callers that want it explicitly. Legacy aliases `vacuum_standard`→`vacuum_quick` and `vacuum_mop_standard`→`vacuum_mop_quick` are resolved at lookup time. The framework's default profile name is `DEFAULT_ROOM_PROFILE_NAME = "vacuum_quick"` — a brand can override which profile a newly-discovered room actually gets via `room_profiles.default_profile` (§1.1); see [08-rooms-system](08-rooms-system.md) §3.1 for how the new-room defaulting seam (`rooms/room_defaults.py`) consumes it.

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
| Bulk apply — `manager.py:apply_room_profile` (→ `apply_room_profile_to_config`) | **adapter** (`get_adapter_config(vacuum_entity_id)` → `resolve_profile_catalog`) | it has a `vacuum_entity_id`, so a non-Eufy brand fills omitted fields from ITS `normalize_defaults` (§5.5) |
| Global profile editor — `manager.py` (`get_room_profiles`, `_finalize_room_update`, `_match_profile_from_fields`) | framework default (`catalog=None`) | the singleton editor lacks per-vacuum context |

Byte-identical for Eufy throughout. A second brand's dispatched per-room settings already honor its catalog; its *editor UI* would show framework defaults until those editor methods are threaded — a documented follow-up.

**Note — new-room defaulting no longer goes through this table.** `rooms/room_manager.py::build_managed_rooms` (and `maps/map_manager.py::rebuild_map_bucket`) do **not** call any of the catalog-aware resolver functions above with `catalog=None`; "what does a fresh room look like?" is answered by a separate, newer, brand-aware seam — `rooms/room_defaults.py::resolve_new_room_defaults_for_vacuum(vacuum_entity_id)`, which resolves the SAME `resolve_profile_catalog` but is invoked by the (vacuum-scoped) caller (`save_managed_rooms` / `rebuild_map`) rather than by the room-builder itself, and returns setting values directly rather than being threaded through as a `catalog` kwarg. See [08-rooms-system](08-rooms-system.md) §3.1. `build_managed_rooms` still imports the bare `DEFAULT_ROOM_PROFILE_NAME` constant (not `resolve_profile_catalog`) as the last-resort `profile_name` fallback when neither the existing room nor `new_room_defaults` supplies one.

---

## 2. ID Formats

| ID type | Format | Example |
|---|---|---|
| Room profile | `user_{YYYYMMDDTHHMMSS}` | `user_20260530T141522` |
| Run profile | `rp_{YYYYMMDDTHHMMSS}` | `rp_20260530T141522` |

ID timestamps use naive local time (`datetime.now()`) at creation time. IDs are not guaranteed globally unique — collision probability is low at human interaction rates.

---

## 3. Storage Layout

### 3.1 Room profiles

```
data["profiles"]["room_profiles"] = {
    "user_1":             { ...9-key record... },
    "user_20260530T...":  { ...9-key record... },
}
```

Each stored record is the `normalize_room_profile()` output — exactly **9 keys**, no `id`/`name`/`is_builtin` (the store key **is** the `profile_name`):

| Field | Type | Default |
|---|---|---|
| `label` | `str` | `"User Profile 1"` |
| `clean_mode` | `str` | `"vacuum"` |
| `fan_speed` | `str` | `"Max"` |
| `water_level` | `str` | `"Off"` |
| `clean_intensity` | `str` | `"Quick"` (dead `Standard`/`Normal` folded via `normalize_clean_intensity`) |
| `path_type` | `str` | `"wide"` |
| `clean_passes` | `int` | `1` |
| `edge_mopping` | `bool` | `False` |
| `mop_required` | `bool` | `False` |

> **`path_type`/`mop_required` are derived for custom profiles.** The editor/service exposes 7 fields (`label`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping`) — not `path_type` or `mop_required`. `save_user_room_profile` **derives** the missing two to mirror the built-ins rather than letting `normalize_room_profile` default both: `mop_required = "mop" in clean_mode or "wash" in clean_mode`, and `path_type = "narrow"` when `clean_intensity` normalizes to `Deep` else `"wide"`. (Was code-flag B2: previously both were left to default `"wide"`/`False`, mis-storing a deep-mop custom profile — fixed.)

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
    "steps":             [ { ...step... } ],  # OPTIONAL — ordered run steps (§7.7); absent on legacy/flat profiles
    "created_at":        str,        # ISO timestamp
    "updated_at":        str,        # ISO timestamp
}
```

`steps` is written by **`set_run_profile_steps()`** (§7.7) **and** by **`save_run_profile()` when the live queue has breaks** — `save_run_profile` calls `get_queue_steps()` and, when the result's `has_breaks` is `True` (an ad-hoc charge_wait/wait/zone-sequenced queue), persists `library[profile_id]["steps"] = queue["steps"]` at creation (§7.2). So a run profile can carry `steps` without `set_run_profile_steps` ever being called. `overwrite_run_profile()` **resets** `steps` to `[]` (§7.3). A profile saved from a flat queue is a legacy rooms-only profile (no `steps`); `run_profile_steps()` back-fills such a profile as a single `room_group` step at read time, so everything downstream is byte-identical.

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

There are also `save_room_profile_from_room(*, vacuum_entity_id, map_id, room_id, label, profile_name=None)` and `overwrite_room_profile_from_room(*, vacuum_entity_id, map_id, room_id, profile_name, label=None)`, which snapshot a room's current **effective** settings (via `get_effective_room_details`, §6.2) into a profile. Both return:

```python
# → {"vacuum_entity_id", "map_id", "room_id": int(room_id), "saved"|"overwritten": bool,
#    "profile_name": str, "profile": dict}
#   or {..., "saved"|"overwritten": False, "reason": ..., ["message": ...]}
```

Reason codes: `missing_label`, `room_not_found`, `room_details_unavailable`, `protected_profile` (both); `profile_not_found` (overwrite-only). `room_id` is echoed as `int(room_id)`; the two `*_from_room` service schemas already `Coerce(int)` the `room_id`, so that coercion cannot fail via the service path (only a direct non-int caller would raise).

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

### 5.5 `apply_room_profile` — bulk apply to rooms

```python
manager.apply_room_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_ids: list[int] | list[str],
    profile_name: str,
) -> dict
# → {"vacuum_entity_id", "map_id", "profile_name",
#    "updated_room_ids": sorted(list[int]), "room_count": int}
#   or {"vacuum_entity_id", "map_id", "profile_name",
#    "updated_room_ids": [], "error": "profile_not_found"}
```

Applies one profile's settings to each listed room: for each id it runs `apply_room_profile_to_config(room, profile_name, profile, catalog)` then `_finalize_room_update` (§6), rewrites `bucket["rooms"]`, and re-derives the **9-key** `build_room_selection_summary`. It resolves the **adapter** catalog (§1.1) — a per-vacuum method, unlike the singleton editor. `room_ids` are coerced with `_safe_int(r, -1)` and any non-positive/unparseable id is dropped (`[rid for rid in (...) if rid >= 0]`); rooms not on the map are skipped. Exposed as the `apply_room_profile` service (whose schema already `Coerce(int)`s each id). Note the failure key is **`error`** (not `reason`).

---

## 6. Room Profile Finalization Pipeline

When a room's settings are saved via `update_room_fields()`, the settings pass through a two-stage pipeline:

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

`_match_profile_from_fields` scans all room profiles looking for one that matches the room on six fields — `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping` (**not** `path_type` or `label`). The match is **not literal**: both sides pass through `_normalize_profile_match_value` (case-fold; `"off"`; `"true"`/`"false"` → bool; numeric strings → float), so `"Off" == "off"` and `2 == 2.0`. Crucially the two sides are **not symmetric**:

- **Room side:** the room is run through `_protected_room_config` first (so a vacuum room already has `water_level="Off"`, `edge_mopping=False`).
- **Candidate side:** each preset is resolved via `resolve_room_profile_for_room` **under the room's `floor_type`** and then run through the **same** `_protected_room_config` — so both sides reflect identical floor-driven invariants (vacuum → water `"Off"`; carpet → water `"Off"` + fan default). A room with no `floor_type` leaves the candidate at the resolver's `hardwood` default.

If a match is found `profile_name` is set to it; otherwise `profile_name = "custom"`.

> **Why the candidate is protected too (was code-flag B1, now FIXED).** The candidate **must** be resolved with the room's `floor_type` and protected on the same pipeline. Historically it was resolved from a bare `{"profile_name": name}` (no `floor_type`), so it carried the hardwood water default `"Low"` while a vacuum room's protected water is forced `"Off"` → `"low" != "off"` → **every plain vacuum room fell to `profile_name="custom"`** (only mop presets, which keep their water, could ever match — the PM-10 test comment notes it deliberately used a mop preset for exactly this reason). Resolving + protecting the candidate under the room's floor closes the asymmetry; regression test `PM-10b` (a hardwood vacuum room now matches `vacuum_quick`).

> The two-stage pipeline above produces **display/storage** values. A separate, capability-aware stage (`apply_capability_gate`) runs later at **payload-build time** — see §6.1.

> **Two callers of the matcher (B6, benign).** The **editor** path (`update_room_fields` → `_finalize_room_update`) runs the full protect → resolve → **path_type sync** → match pipeline and persists the result. The **dispatch** path (`planning/run_plan.py`) runs only `protected_room_config` + `_match_profile_from_fields` (no `path_type` sync) — but it reads the room's **already-persisted** `path_type` for the payload (synced when the room was last saved), so it doesn't need to re-sync. Both now set `profile_name` consistently (the B1 fix applies to the dispatch matcher too).

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

### 6.2 `get_effective_room_details` — the public resolved-room read

```python
manager.get_effective_room_details(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_id: int | str,
) -> dict | None   # None when the room is absent on that map
```

The B2 shaper's **public output contract**: resolve the stored room (`resolve_room_profile_for_room`), then re-run the resolved values through `_protected_room_config`, and return a **12-key** dict. **Two keys are renamed** — a blind rebuild that emitted `clean_passes`/`edge_mopping` here would silently break every consumer (`room_entities.py`, `save_room_profile_from_room`, and the card's `src/renderers/rooms.js`):

| Key | Type | Source |
|---|---|---|
| `clean_mode` | `str` | protected(resolved) |
| `fan_speed` | `str` | protected(resolved) |
| `water_level` | `str` | protected(resolved) |
| `clean_intensity` | `str` | protected(resolved) |
| `path_type` | `str` | **resolved** (not protected) |
| **`default_clean_passes`** | `int` | protected `clean_passes` — **renamed** (not `clean_passes`) |
| **`default_edge_mopping`** | `bool` | protected `edge_mopping` — **renamed** (not `edge_mopping`) |
| `mop_required` | `bool` | `"mop" in clean_mode or "wash" in clean_mode` |
| `selected_profile_name` | `str` | resolved |
| `resolved_profile_name` | `str` | resolved (may differ from `selected` — floor-type match) |
| `floor_type` | `str` | raw `room.floor_type` (un-normalized) |
| `floor_type_label` | `str` | `get_floor_type_label(floor_type, default "hardwood")` |

Returns `None` (not a result dict) when the room id is not on the map.

### 6.3 Room-profile resolution precedence (`resolve_room_profile_for_room`)

The field-by-field precedence lives in `profiles/room_profiles.py`; because doc 16 is the profiles subsystem's home, the ladder is stated here authoritatively. Base rule: **the room's own field wins over the profile default** for `clean_mode`, `clean_intensity`, `path_type`, `fan_speed`, `clean_passes`, and `edge_mopping` — but with **floor-type overrides** that are *not* "room always wins":

1. **Carpet overrides the room** — even an explicit value loses: `fan_speed → FLOOR_TYPE_FAN_DEFAULTS[floor_type]` (`carpet_low_pile="Max"`, `carpet_high_pile="Standard"`, else `"Max"`) and `water_level → "Off"`.
2. **Hard floors fill water only when absent** — `water_level → FLOOR_TYPE_WATER_DEFAULTS[floor_type]` (default `"Low"`) **only when `"water_level" not in room_config`**; an explicit room `water_level` on a hard floor is kept.
3. **Mop-mode + `Off` + non-carpet** → `water_level → FLOOR_TYPE_WATER_DEFAULTS[floor_type]` (mop with water Off is invalid).
4. **`edge_mopping` forced `False`** for any non-mop mode **or** carpet.

So the doc-07 shorthand "the room field always wins" holds only for the *unconstrained hard-floor* fields; carpet fan/water and the water-fill-when-absent rule are the exceptions. (Because these floor overrides are asymmetric, §6 Stage 2's profile matcher resolves + protects its candidate under the room's `floor_type` — an earlier version dropped the candidate's floor and mislabeled every vacuum room `"custom"`.)

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

Each `library` entry is passed through `_enrich_saved_run_profile()`, which derives its room metadata (`room_count` / `room_ids` / `room_names` / `room_names_label`) from the **effective steps** (the flattened `room_group` rooms, same flattening `apply_run_profile` uses) rather than the stored top-level `rooms` — a stepped edit only rewrites `steps`, leaving `profile["rooms"]` holding the stale pre-steps set. It also adds three derived fields on top of the stored profile:

- `steps` — the normalized ordered steps via `run_profile_steps()`, back-filling a legacy rooms-only profile as one `room_group`.
- `has_charge_steps` — `True` if any step is a `charge_wait`.
- `has_stops` — `True` if the profile is a **sequenced** run rather than a plain queue: any break step (`charge_wait` **or** `wait`) **OR** more than one `room_group`. This is **distinct** from the charge-only `has_charge_steps`. The frontend gates the stepped preview/chips, the "Runs as" summary, and Start-routing (`pendingStepRunProfileId`) on `has_stops` (a shared contract with the card lane) — **not** on `has_charge_steps`.

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

| Field | Type / coercion | Default |
|---|---|---|
| `room_id` | `_safe_int(room["room_id"] or room["id"])` | `-1` (unparseable → `-1`) |
| `name` | `str` | `""` |
| `profile_name` | `str` | `"vacuum_quick"` |
| `clean_mode` | `str` | `"vacuum"` |
| `fan_speed` | `str` | `"Max"` |
| `water_level` | `str` | `"Off"` |
| `clean_intensity` | `normalize_clean_intensity(...)` | `"Quick"` |
| `clean_passes` | `int` | `1` |
| `edge_mopping` | `bool` | `False` |
| `order` | `int` | `999` |

> A `-1` `room_id` sentinel **survives in the stored `rooms` list** but is dropped from the summary: `_run_profile_summary` filters `room_ids >= 0`, so a snapshot with an unparseable id is counted in `rooms` yet absent from `room_ids`/`room_count`.

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

Re-snapshots the current enabled rooms into an existing run profile. Preserves `id` and `created_at`; updates `updated_at`. `name`/`expose_as_button` keep their existing value when passed `None`. **Resets `steps` to `[]`** — an overwrite replaces the whole run with the current enabled-room queue, so any prior sequencing is intentionally discarded. (Without the reset, the `{**existing}` spread would carry the stale `steps` list forward, and since `run_profile_steps()` prefers a non-empty `steps` list, apply/start would clean the *old* rooms and ignore the new selection. The empty list lets `run_profile_steps()` back-fill a single `room_group` of the new rooms.)

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
2. For each room across the profile's `room_group` **steps**, in step order (via `run_profile_steps()`, so a legacy rooms-only profile back-fills to a single group; `charge_wait`/`wait` steps carry no rooms and are skipped here), enumerated 1-indexed for `order`:
   - Looks up the room by `room_id` in `data["maps"][vacuum][map_id]["rooms"]`. If absent, the id is added to `missing_room_ids` and skipped.
   - Enables the room and restores saved settings: `profile_name`, `clean_mode`, `fan_speed`, `water_level`, `clean_intensity`, `clean_passes`, `edge_mopping`, plus the enumeration `order`.
   - Runs `_finalize_room_update()` on the restored room.

`apply_run_profile` only restores the room **selection/settings** onto the map; it does not itself execute the ordered stops. The `charge_wait`/`wait` boundaries and their per-group settings are materialized into job phases at start time — see §7.7.

### 7.7 Ordered Steps — `set_run_profile_steps` (native charge/wait stops)

A run profile can carry an ordered **`steps`** list that breaks its rooms into groups separated by **stops** (and, optionally, saved-zone cleans). This is what powers a "vacuum, then dock and charge to 60%, then mop, then hit the stove zone" sequence as one saved run. Four step types:

| `type` | Fields | Meaning |
|---|---|---|
| `room_group` | `rooms: [ {room_id, clean_mode, fan_speed, water_level, ...}, ... ]` | A group of rooms cleaned back-to-back. The **same** room may appear in two groups with different settings (vacuum in one, mop in the next); the group's fields overlay the room view at dispatch. |
| `charge_wait` | `target_battery_percent: int` (clamped 1–100) | Dock and poll the battery until the target %, then continue. |
| `wait` | `wait_minutes: int` (clamped 1–1440) | Dock and hold for N minutes, then continue (e.g. a mop-dry pause). |
| `zone` | `zone_ids: [ ... ]` (saved-zone ids) | Clean one or more saved zones as a single **clean** phase (not a dock). Dispatched via `dispatch_zone_clean`; unlike a stop it may sit at the tail after the last room group. See [07-queue-engine](07-queue-engine.md#steps-model). |

```python
manager.set_run_profile_steps(
    *,
    vacuum_entity_id: str,
    map_id: str,
    profile_id: str,
    steps: list,
) -> dict
# → {"saved": True, "profile_id": str, "profile": {enriched}}
#   or {"saved": False, "reason": "profile_not_found" | "no_room_group"}
```

Replaces the profile's stored `steps`. Requires at least one `room_group` (a run must clean something) — otherwise `reason="no_room_group"`. The list is passed through `normalize_run_profile_steps()`, a static method that coerces/validates each entry and **drops** invalid or empty ones (a `room_group` with no rooms, a `charge_wait`/`wait` whose numeric field won't parse). Each `room_group` room is coerced to a well-formed `{room_id: int, ...}` dict via a safe-int (a bare int is wrapped; a room whose `room_id` doesn't parse to a positive int is dropped; a group left with no valid room is dropped entirely), so dispatch never sees an unparseable `room_id`. Phase materialization (`planning/run_plan.py:_build_steps_phases`) also reads each `room_id` through the same safe-int, so a bad id no longer crashes dispatch. The service wrapper is `set_run_profile_steps` in `services/run_profiles.py` (schema requires `steps: list`); it raises `ServiceValidationError` when `saved` is `False`.

**Read helper — `run_profile_steps(profile)`** (static): returns a profile's ordered steps, back-filling a legacy rooms-only profile as a single `room_group` of its `rooms`. This is the single read path — `apply_run_profile` (§7.6), `_enrich_saved_run_profile` (`steps` / `has_charge_steps` / `has_stops`, §7.1), and phase materialization all go through it, so legacy profiles stay byte-identical.

> **Where the stops actually run.** This manager only *stores* and *normalizes* the steps and *restores* the room selection. Materializing `steps` 1:1 into `active_job["phases"]` (leading/trailing stops dropped, consecutive same-type stops collapsed), executing the dock-and-poll `charge_wait` / dock-and-hold `wait` phases, and running per-phase pre-calls so a stepped run can vacuum one group then mop the next all live in the job/phase machinery — see [30-phase-runner](30-phase-runner.md) and [07-queue-engine](07-queue-engine.md) §4. A dock (`charge_wait` / `wait`) phase is driven **only** by an in-memory poller task, which a pause+resume or an HA restart loses — `PhaseRunner.rearm_dock_phase_if_needed` re-spawns it when the current phase is a dock phase and `status == "started"` (called from resume in `active_job.async_resume_active_job` and on load from `manager.async_initialize`), guarded by a `_dock_poller_active` set so an advance and a re-arm can't both spawn. Without it a charge/wait run would wedge in `started` forever after a pause+resume or restart. The `wait` phase is also exempt from the mid-job recharge observer (`active_job.update_active_job_recharge_observation` treats both `charge_wait` and `wait` as commanded docks that own their own dock).

```python
async manager.start_run_profile(
    *,
    vacuum_entity_id: str,
    map_id: str,
    profile_id: str,
    confirm_reduced_run: bool = False,
    confirm_token: str | None = None,
    path_block_action: str | None = None,
    pause_timeout_minutes_override: int | None = None,
) -> dict
# started → the start_selected_rooms result dict with profile_id + profile injected
# not applied → {vacuum_entity_id, map_id, profile_id, "started": False, reason,
#                message, profile, applied_room_ids, missing_room_ids}
```

> **Apply + start in one shot.** Kicking off a saved profile's full stepped sequence is `start_run_profile`, exposed as the `start_run_profile` service and as each profile's HA button. The START orchestration — apply the profile (§7.6), stash its `charge_wait`/`wait`/`zone` steps under `data["_pending_run_steps"]`, then dispatch — now lives on **`ProfileManager.start_run_profile`** (next to `apply_run_profile`); the stash gate mirrors the run-plan step-source gate and includes **`zone`** as well as the two stops — without it, a saved rooms→zone profile started from an automation (where `apply_run_profile` never writes the live `queue_breaks`) would dispatch flat and silently **drop the zone** (fixed in `bbc1030`); `core/manager.py` keeps a thin `start_run_profile` delegator so service/button/test callers of `manager.start_run_profile` are unchanged. It reaches back to the core manager (via `self._manager`) for `build_queue` / `build_room_payload` / `start_selected_rooms`, which stay on the core manager. On a **non-started** return (blocked / confirmation-required without a token / vacuum missing), it deletes the leaked `_pending_run_steps` entry for that (vacuum, map) so the next plain Start on the map isn't silently turned into a charge/wait run. See [06-job-lifecycle](06-job-lifecycle.md).

---

## 8. Integration Points

| Caller | Method | When |
|---|---|---|
| Panel room editor | `get_room_profiles()`, `save_user_room_profile()`, `overwrite_room_profile()`, `rename_room_profile()`, `delete_room_profile()` | Room settings save/edit |
| Panel run profile tab | `get_saved_run_profiles()`, `save_run_profile()`, `apply_run_profile()`, `rename_run_profile()`, `delete_run_profile()`, `set_run_profile_steps()` | Run profile CRUD + step editing (§7.7) |
| `core/manager.py` (`update_room_fields`) | `_finalize_room_update()` | Every per-room settings write (service `services/rooms.py`) |
| Exposed profile button (`button.py`) / `start_run_profile` service | `apply_run_profile()` via `manager.start_run_profile` (thin delegator → `ProfileManager.start_run_profile`) | Apply + start a saved profile's full stepped sequence in one tap |

> **See also:** [08-rooms-system](08-rooms-system.md) §6 for the room data model that profiles are merged into; [07-queue-engine](07-queue-engine.md) §4 for how run profiles are resolved at queue build time before the payload is sent to the vacuum.
