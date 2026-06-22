# 08 — Rooms System

> **Scope:** Complete implementation reference for the rooms subsystem: `rooms/room_crud.py` (RoomMapManager), `rooms/room_manager.py` (pure functions), `rooms/room_discovery.py` (adapter-driven discovery), `rooms/reconciliation.py` (slug-based identity-shift detection + migration planning), `rooms/source_refresh.py` (the `service_response` room-source refresh/flatten cache), and `rooms/utils.py`. Every method, adapter dependency, storage path, and inter-module relationship is derived directly from the source.

---

## 1. Overview

The rooms system is responsible for the full lifecycle of room data within the integration: discovering rooms from the upstream vacuum API, building and persisting managed room records, and removing stale data when a map is deleted or rebuilt.

**Module roles:**

| Module | Role |
|---|---|
| `rooms/room_crud.py` | Orchestration class (`RoomMapManager`). Coordinates discover → save → remove → rebuild. Holds a back-reference to `EufyVacuumManager`. |
| `rooms/room_manager.py` | Pure functions for building managed room dicts from raw discovery data. No class, no side effects. |
| `rooms/room_discovery.py` | All brand-specific room discovery logic. Reads entity IDs, attribute names, and key mappings from the adapter registry. |
| `rooms/reconciliation.py` | Pure slug-based identity-shift detection (`compute_reconciliation`: `id_changed`/`renamed` reviews) and migration planning (`plan_migration`). No hass, no manager — the manager applies a confirmed plan. |
| `rooms/source_refresh.py` | `service_response` room-source refresh + flatten cache — the entire Roborock room-discovery mechanism. `async_refresh_room_source` calls the adapter's maps service at the async boundaries, `flatten_maps_response` normalizes it into the attribute-source list shape, and `get_cached_room_source` serves the sync discovery path. |
| `rooms/access_graph.py` | Room access-graph helpers (`grants_access_to` resolution / validation). See [09-room-rules-system.md](09-room-rules-system.md). |
| `rooms/utils.py` | `slugify_room_name()` helper. |

---

## 2. Room Discovery (`room_discovery.py`)

### 2.1 Adapter registry dependencies

All brand knowledge lives in the adapter config's `discovery` block:

| Adapter key | Description |
|---|---|
| `discovery.source` | Which discovery source to use: `"entity_attribute"` (the default, omitted → entity-attribute) reads a live attribute off an entity; `"service_response"` reads a cached flattened service-call response (see §2.3 and `rooms/source_refresh.py`). |
| `discovery.room_id_key` | Key for room ID within each room dict (e.g. `"id"`). Required by **both** sources. |
| `discovery.room_name_key` | Key for room name within each room dict (e.g. `"name"`). Required by **both** sources. |
| `discovery.room_list_entity` | (`entity_attribute` source) Which entity holds the room list. `"vacuum_entity"` means the vacuum entity itself. |
| `discovery.room_list_attribute` | (`entity_attribute` source) State attribute name on the room_list_entity that contains the room array |
| `discovery.maps_service` | (`service_response` source) `{domain, service}` of the maps service called with `return_response=True` (e.g. `roborock.get_maps`). |
| `discovery.maps_rooms_key` | (`service_response` source) Key on each map entry holding the `{segment_id: name}` room mapping. Defaults to `"rooms"`. |
| `discovery.map_name_key` | (`service_response` source) Key on each map entry holding the map name (the cache key, matching `entities.active_map`). Defaults to `"name"`. |

For Eufy (`entity_attribute` source): `room_list_entity = "vacuum_entity"`, `room_list_attribute = "segments"`, `room_id_key = "id"`, `room_name_key = "name"`.

### 2.2 `get_active_map_id`

```python
get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None
```

Reads the active map ID from the entity declared at `adapter_config["entities"]["active_map"]`. Returns the state value as a `str`, or `None` if the adapter is not registered, the entity is missing, or its state is an HA sentinel value (`"unknown"`, `"unavailable"`, `""`, `"none"`, `"None"`).

### 2.3 `discover_rooms_for_vacuum`

```python
discover_rooms_for_vacuum(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> list[dict]
```

Reads the room list according to `discovery.source`, then normalizes it identically for both:

- **`entity_attribute`** (default, Eufy) — reads the live attribute named by `room_list_attribute` off the entity named by `room_list_entity`.
- **`service_response`** (Roborock) — reads `get_cached_room_source(hass, vacuum_entity_id)` (the per-map flattened cache, refreshed at the async boundaries by `async_refresh_room_source` — see `rooms/source_refresh.py`) and selects the entry for the resolved active map name. There is no entity attribute to read; the service call is async and the sync discovery path cannot make one, so it consumes the cache instead.

For each raw room entry:

1. Extracts `room_id` (from `room_id_key`) and `name` (from `room_name_key`).
2. Generates `slug = slugify_room_name(name)`.
3. De-duplicates by `room_id` — if two entries share an ID, the first wins.

Returns a list of room dicts:

```python
[
    {
        "room_id": int,
        "map_id":  str,
        "name":    str,
        "slug":    str,
    },
    ...
]
```

Returns `[]` if the source yields nothing — the entity is unavailable / the attribute is missing (`entity_attribute`), or the cache holds no list for the resolved map (`service_response`).

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
    *,
    discovered_rooms: list[dict],
    existing_rooms: dict[str, dict] | None = None,
    enabled_room_ids: list[int] | list[str] | None = None,
    floor_types: dict[int, str] | None = None,
) -> dict[str, dict]
```

Builds the managed room dict from raw discovery data. Key is `str(room_id)`.

**For each discovered room:**

- If `enabled_room_ids` is supplied (not `None`) and the `room_id` is **not** in it, the room is **skipped** (`continue`) — it is not included in the result at all.
- If a matching room exists in `existing_rooms` (by room_id): preserves all existing user settings (fan speed, clean mode, etc.) and updates `name` and `slug` from discovery data.
- If the room is new: initializes with safe defaults — `clean_mode="vacuum"`, `fan_speed="Max"`, `water_level="Off"`, `profile_name="vacuum_quick"`, `clean_passes=1`, `edge_mopping=False`, etc.
- Sets `is_configured = True` for every room that makes it into the result — including a room in `enabled_room_ids` counts as the user's explicit approval. This flag is what the setup drift tracker uses to distinguish managed rooms from newly discovered ones.
- Sets `enabled = True` for new rooms (existing rooms keep their stored `enabled` value). Note: membership in `enabled_room_ids` gates *inclusion*, not the `enabled` flag.
- Sets `floor_type` from `floor_types` dict if present, otherwise defaults to `"hardwood"`.

When `enabled_room_ids` is `None`, returns the managed room dict for every room in `discovered_rooms`; when it is supplied, only those rooms are present. Rooms in `existing_rooms` that are **not** in `discovered_rooms` are **dropped** (they are stale).

### 3.2 `build_room_selection_summary`

```python
build_room_selection_summary(*, managed_rooms: dict[str, dict]) -> dict
```

`managed_rooms` is **keyword-only** — a positional call raises `TypeError`. The sole caller invokes it as `build_room_selection_summary(managed_rooms=managed_rooms)`.

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
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> dict
```

1. Calls `get_active_map_id()` if `map_id` is not supplied.
2. Calls `discover_rooms_for_vacuum()` (via `discover_rooms_payload()`).
3. Attaches a `"reconciliation"` block onto the payload — `compute_reconciliation()` (from `rooms/reconciliation.py`) compares the fresh discovery against the **saved** rooms for this map by slug, surfacing `id_changed` / `renamed` reviews. New/removed rooms are owned by drift, not reported here.
4. Caches the raw discovery result (with the reconciliation block) in `data["discovery"][vacuum][str(map_id)]`.
5. Updates `runtime.active_map_id` for the vacuum.

Returns the discovery payload dict.

### 5.2 `save_managed_rooms`

```python
manager.room_map.save_managed_rooms(
    *,
    vacuum_entity_id: str,
    map_id: str,
    enabled_room_ids: list[int] | list[str] | None = None,
    floor_types: dict[int, str] | None = None,
) -> dict   # summary {vacuum_entity_id, map_id, room_count, rooms, summary}
```

1. Ensures the vacuum record via `manager.ensure_vacuum_record()`.
2. Reads discovery cache from `data["discovery"][vacuum][str(map_id)]`, then filters it down to rooms whose `map_id` matches.
3. Ensures the map bucket exists via `ensure_map_bucket()` and reads existing rooms from it.
4. Calls `build_managed_rooms()` to merge.
5. Writes the merged rooms to `map_bucket["rooms"]`.
6. Builds the summary via `build_room_selection_summary(managed_rooms=...)` and writes it to `map_bucket["summary"]`.
7. Calls `manager._refresh_room_derived_state()` to re-run profile matching.
8. Invalidates the room-history cache via `manager._room_history_cache_ready.discard(vacuum)`.
9. Sets `runtime.selected_map_id = str(map_id)`.
10. **If** `managed_rooms` is non-empty: calls `manager.mark_rooms_discovered()`, then `manager.confirm_floor_type()` for each room. These two calls are skipped on an empty result.
11. Fires `_notify_rooms_updated(vacuum, map_id)` so entity-platform callbacks rebuild HA entities.

Returns `{vacuum_entity_id, map_id, room_count, rooms, summary}`.

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

Returns a summary of what was removed.

No cross-map access-graph cleanup is performed, and none is needed. `grants_access_to` targets are bare room IDs scoped to a single map — room identity is vacuum+map+room, and every consumer (`_build_room_access_views`, `_validate_room_access_graph`, `_normalized_managed_rooms_with_automation`) resolves them only against that same map's room set. A grant on a remaining map therefore can never reference a room on the map being removed (even if both maps happen to reuse the same numeric room ID, those IDs denote *different* rooms). There is nothing to strip, so `remove_map` leaves sibling maps' grants untouched.

### 5.4 `rebuild_map`

```python
manager.room_map.rebuild_map(
    *,
    vacuum_entity_id: str,
    map_id: str,
    preserve_existing_settings: bool = True,
) -> dict
```

Rebuilds the managed room set from the discovery cache, preserving existing room settings where possible:

1. Reads discovery cache from `data["discovery"][vacuum][map_id_str]`.
2. Reads existing rooms.
3. Calls `map_manager.rebuild_map_bucket()`, forwarding the `preserve_existing_settings` argument (defaults to `True`).
4. Calls `_refresh_room_derived_state()` to re-run profile matching on all rooms.
5. Calls `_notify_rooms_updated()` to rebuild HA entities.

Does **not** reset onboarding — use `onboarding.reset_onboarding()` explicitly before `rebuild_map()` if the intent is a full reset.

### 5.5 `reconcile_room`

```python
manager.room_map.reconcile_room(
    *,
    vacuum_entity_id: str,
    map_id: str,
    action: str = "migrate",   # "migrate" | "ignore"
) -> dict
```

Applies or dismisses the identity-shift reviews (`id_changed` / `renamed`) surfaced on the cached discovery payload by `discover_rooms` (§5.1). Because a re-segment renumbers many rooms at once, reconciliation is a single per-map decision rather than a per-room prompt. Requires a prior `discover_rooms` to have cached the discovery.

**`action="migrate"`** atomically rebuilds the saved room map from the cached discovery:

1. Reads the cached discovery and the saved rooms, then calls `plan_migration()` (from `rooms/reconciliation.py`) to build the new id-keyed room map, carrying each saved room's durable settings to its new (slug-matched) id.
2. Writes `plan["rooms"]` to the map bucket and rebuilds its `summary`; stamps `metadata["reconciled_at"]`.
3. Rewrites access-graph `grants_access_to` targets through the same `old->new` id remap (done inside `plan_migration`).
4. Drops the id-keyed rule-status snapshots for **both** the old and new ids (they rebuild on the next preflight) so a freed-then-reused id can't show a stale snapshot.
5. Calls `onboarding.remap_confirmed_floor_types()` so renumbered rooms keep their floor-type confirmation and the start gate does not block with `onboarding_required`.
6. Invalidates the room-history cache (`_room_history_cache_ready.discard(vacuum)`) — it re-ingests under the new ids from the slug-tagged job files.
7. Calls `_refresh_room_derived_state()` then `_notify_rooms_updated()`.

Guards an empty discovery: if the cached discovery has no rooms for this map, it returns early with `skipped="no_discovery"` (no rebuild) rather than wiping the saved rooms — re-run `discover_rooms` first.

**`action="ignore"`** leaves stored data untouched and stamps `metadata["reconciliation_dismissed_at"]` so the same reviews stop surfacing until the next real change.

Returns `{vacuum_entity_id, map_id, action, migrated_room_count, id_remap, dropped[, skipped]}`. Registered as the `reconcile_room` service (`supports_response=True`).

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
| `configured_at` | str | ISO-8601 timestamp stamped when the room was first configured (preserved across re-saves) |
| `floor_type` | str | One of: `"hardwood"`, `"laminate"`, `"tile"`, `"marble"`, `"carpet_low_pile"`, `"carpet_high_pile"`. Carpet pile is encoded in the value — use `floor_type.startswith("carpet")` rather than a separate flag. (The old `"carpet"` + `carpet_type` shape was migrated away.) |
| `profile_name` | str | Matched room profile name, or `"custom"` |
| `clean_mode` | str | `"vacuum"`, `"mop"`, or `"vacuum_mop"` |
| `fan_speed` | str | e.g. `"Standard"` |
| `water_level` | str | e.g. `"Off"`, `"Low"`, `"Medium"`, `"High"` |
| `clean_intensity` | str | e.g. `"Standard"` |
| `clean_passes` | int | Number of cleaning passes; minimum 1. (The "1 or 2" cap is a frontend modifier constraint, not a room-model rule.) |
| `edge_mopping` | bool | Whether edge mopping is enabled |
| `path_type` | str | From matched profile |
| `order` | int | Dispatch order (defaults to the room's 1-based position in discovery order) |
| `is_dock_room` | bool | Whether this room contains the dock (defaults `False`) |
| `is_transition` | bool | Whether this room is a transition/passage room (defaults `False`) |
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
