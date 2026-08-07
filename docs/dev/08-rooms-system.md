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
| `rooms/access_graph.py` | `AccessGraphManager` — access-graph normalization/validation/health + rule evaluation, plus the module-level `structural_issue_key()` used for delta-scoped edit gating. See [09-room-rules-system.md](09-room-rules-system.md). |
| `rooms/room_defaults.py` | THE single answer to "what does a fresh room look like?": `resolve_new_room_defaults_for_vacuum()` resolves the brand's `room_profiles.default_profile` into the setting fields a new room starts with (see §3.1). Consumed by both room writers (`build_managed_rooms` and `maps/map_manager.py::rebuild_map_bucket`). |
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

Reads the active map ID from the entity declared at `adapter_config["entities"]["active_map"]`. The adapter declares `entities.active_map` from a naming pattern for every device, so "declared" does not mean "exists" — resolution is a **four-rung fallback ladder**:

1. **Entity present in the state machine** → return its state as a `str`, or `None` if the state is blank per `entity_helpers.is_blank_state` (the shared `BLANK_STATE_VALUES` vocabulary: `""`, `"unknown"`, `"unavailable"`, `"none"`, `"null"` — case- and whitespace-insensitive, so `"None"` is covered too).
2. **Entity absent from the state machine but present in the entity registry** → a novel device whose sensor has not materialised yet (a boot/restart window) → return `None` and wait (must not fork a phantom implicit map).
3. **Entity absent from BOTH the state machine and the entity registry** (or not declared at all) → try `_implicit_attribute_map_id`, which returns `discovery.implicit_map_id` (e.g. `"main"` for Eufy) when `discovery.room_list_entity == "vacuum_entity"` and the room-list attribute currently holds at least one **dict** row.
4. **Single-map service-response fallback** (`_single_cached_map_id`, issue #46) — HA 2026.7 can stop creating the Roborock map-selector entity entirely, leaving every rung above `None` while the rooms decode fine. When `discovery.source == "service_response"` **and** the cached room source (§2.3) holds **exactly one** map **and** that map's segment list contains at least one dict row, return that one cache key. Two or more cached maps, an attribute-source brand, or a room-less map → `None` (guessing would serve one map's rooms under another's id).

Returns `None` when no rung yields an id (including when the adapter is not registered).

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

  The cache lives at `hass.data[DOMAIN]["room_source_cache"][vacuum_entity_id]`
  (`DATA_ROOM_SOURCE_CACHE`); the entry is **freshness-stamped** (RP-007):
  `{"per_map": {map_name: [{<room_id_key>: id_str, <room_name_key>: name}, ...]},
  "refreshed_at": iso, "refreshed_mono": float}` — a legacy raw `per_map` dict is still
  readable (age reads as unknown = not fresh; dispatch's freshness gate uses
  `REFRESH_TTL_SECONDS = 15 min`). The refresher (`async_refresh_room_source`) returns
  `{"ok", "reason", "refreshed_at"}` with **seven** distinct `reason` values (`not_service_source` /
  `no_maps_service` / `entity_unavailable` / `service_call_failed` / `empty_response_kept_cache` /
  `superseded_by_newer_refresh` / `None` on success), coalesces concurrent refreshes onto one
  in-flight task, guards a stale slow response with a commit generation (SRC-4, the
  `superseded_by_newer_refresh` exit), and **keeps the previous cache** when a response flattens
  to nothing (RP-006/SRC-2). Entry unload invalidates via `invalidate_room_source_cache` (SRC-5).
  `flatten_maps_response` keys each map by **name** (`map_name_key`, default `"name"`), with
  fallbacks when the name is blank: single-map → `active_map_id`, else `f"Map {flag}"`, else
  `f"Map {index}"`; `room_id_key` defaults to `"segment_id"`, `maps_rooms_key` to `"rooms"`.
  Duplicate map names in one response are keyed collision-safely (`#flag<N>` / `#idx<N>` suffix,
  RP-007/SRC-3) rather than last-writer-wins. The single-map cache fallback is **narrow**
  (RP-019/ID-2): only when the resolved map id is the `"unknown"` sentinel (i.e. no explicit
  `map_id` and `get_active_map_id` came back empty) **and** exactly one map is cached does
  discovery fall back to that one map. An explicit, resolved map id that misses the cache
  returns `[]` — serving another map's rooms relabeled with the requested id is exactly the bug
  this guards.

For each raw room entry:

1. Extracts `room_id` (from `room_id_key`) and `name` (from `room_name_key`).
2. Generates `slug = slugify_room_name(name)`.
3. De-duplicates by `room_id` — if two entries share an ID, the first wins.

An entry is **skipped** entirely when: the segment is not a dict, its id **or** name is `None`,
its id is not int-coercible, its name is empty after `str(name).strip()`, or its name
**slugifies to an empty string** (RP-015/A1-ID-3 — an all-punctuation name can never be a
stable identity key; skipped with a warning). (`resolved_map_id` falls back to `"unknown"`
when both `map_id` and the active map are `None`.)

**Slug uniqueness is enforced at the admission boundary** (RP-015/Q4): `slugify_room_name` has
no cross-room uniqueness guarantee, so after the per-entry loop, colliding slugs are
disambiguated deterministically — the **lowest** `room_id` keeps the bare slug and every
colliding sibling becomes `{slug}_r{room_id}`, so re-discovery of the same physical rooms
always converges on the same suffixed identities.

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
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> dict
```

When `map_id` is `None` it defaults to the active map via `get_active_map_id`. Convenience wrapper that returns:

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
    new_room_defaults: dict,                                # REQUIRED — no default
    existing_rooms: dict[str, dict] | None = None,
    enabled_room_ids: list[int] | list[str] | None = None,
    floor_types: dict[int, str] | None = None,
    rejected_rooms: set[int] | list[int] | None = None,
) -> dict[str, dict]
```

Builds the managed room dict from raw discovery data. Key is `str(room_id)`. Each record is
built through the **`RoomConfig` dataclass** (`models/models.py`) — the same dataclass the
rebuild path (`maps/map_manager.py::rebuild_map_bucket`) uses — so the two writers cannot drift
on the field list.

`new_room_defaults` is **required with no default value** — it comes from
`rooms/room_defaults.py::resolve_new_room_defaults_for_vacuum(vacuum_entity_id)`, which resolves
the **brand's `room_profiles.default_profile`** (framework catalog: `vacuum_quick`) and returns
`{"profile_name": <name>}` plus whichever of `clean_mode` / `fan_speed` / `water_level` /
`clean_intensity` / `path_type` / `clean_passes` / `edge_mopping` that profile declares. A field
the brand's profile omits falls back to the `RoomConfig` field default (`fan_speed` /
`water_level` / `clean_intensity` default to `""` — visibly unset, not Eufy vocabulary).

**Carry-over is SLUG-LED with id fallback** (RP-018/RF-25b): an existing room whose slug is
**unique** among `existing_rooms` is matched by slug first; only then does the id fallback apply,
and an id already "consumed" by a slug match is excluded from id fallback (a renumber that frees
Kitchen's id 16 for a new Bedroom must not transplant Kitchen's settings onto Bedroom). An
ambiguous (duplicate) stored slug is excluded from slug matching entirely — that room falls back
to id-led carry, never a guess.

**For each discovered room:**

- If the `room_id` is in `rejected_rooms` **and** the room is not already configured
  (`existing.is_configured` falsy), it is **skipped** — a rejection refuses a room's *creation*,
  it never deletes a configured room (SETUP-REJ-2 / A4-SETUP-6). The production caller
  (`save_managed_rooms`) passes the **map-scoped** rejection set
  (`setup/drift.py::rejected_room_ids_for(..., include_unscoped=False)`).
- If `enabled_room_ids` is supplied (not `None`) and the `room_id` is **not** in it, the room is **skipped** (`continue`) — it is not included in the result at all.
- A matched existing room preserves all existing user settings (fan speed, clean mode, etc.); `name` and `slug` come from discovery data.
- A **new** room takes the brand's default-profile settings via `new_room_defaults` (Eufy: `profile_name="vacuum_quick"`, `clean_mode="vacuum"`, `fan_speed="Standard"`, `water_level="Off"`, `clean_intensity="Quick"`, `path_type="wide"`, `clean_passes=1`, `edge_mopping=False`).
- `is_configured` (CRUD-3): when `enabled_room_ids` is supplied, `is_configured = existing.is_configured OR a floor_types entry was supplied for this room THIS call` — approval without a floor type is a real gap in the wizard flow. When `enabled_room_ids` is `None` (a re-sync, not an approval question), `is_configured` is unconditionally `True`. `configured_at` = existing value or `_iso_now()`.
- `enabled` (DQ-Q-5/CRUD-6): an existing room keeps its stored value. A **new** room is enabled only on a **first import** (`existing_rooms` was empty before this call); on an incremental discovery a new room arrives **disabled** — it never silently joins an already-active queue. Membership in `enabled_room_ids` gates *inclusion*, not the `enabled` flag.
- Sets `floor_type` with a **3-tier precedence**: the wizard `floor_types` value (looked up by
  **both** int and str key) → the room's **existing stored** `floor_type` → `"hardwood"`. So an
  existing room with no wizard override keeps its stored floor type.
- `is_transition` **is** a `RoomConfig` field (preserved across a re-save, default `False`) —
  the old "save path omits it until a reload backfills it" gap is closed.

When `enabled_room_ids` is `None`, returns the managed room dict for every room in `discovered_rooms`; when it is supplied, only those rooms are present. Rooms in `existing_rooms` that are **not** in `discovered_rooms` are **dropped** (they are stale). The function can legitimately return `{}` — it does **not** itself guard a destructive replace; the persisting callers do (§5.2/§5.4, `room_crud._refuse_destructive_replace`).

### 3.2 `build_room_selection_summary`

```python
build_room_selection_summary(*, managed_rooms: dict[str, dict]) -> dict
```

`managed_rooms` is **keyword-only** — a positional call raises `TypeError`. There are 10 call sites: `rooms/room_crud.py` (`save_managed_rooms`, `reconcile_room`, `get_managed_rooms`'s read-path default), `core/manager.py` (`_clear_room_selections_after_start`, `update_room_fields`, `set_room_access_graph`, `set_rooms_enabled_subset`), `profiles/manager.py` (`apply_room_profile`, `apply_run_profile`), and `room_entities.py` (`_async_update_room`). Every one invokes it as `build_room_selection_summary(managed_rooms=...)`.

Returns:

```python
{
    "enabled_count":   int,
    "disabled_count":  int,
    "enabled_rooms":   list[dict],   # sorted by (order, name)
    "disabled_rooms":  list[dict],   # sorted by name
}
```

Each `enabled_rooms` / `disabled_rooms` entry is **9 keys**: `{room_id: int, name, slug, order,
profile_name, floor_type, clean_passes, edge_mopping, carpet}` where `carpet =
floor_type.startswith("carpet")`. (A `rebuild_map` writes a *reduced* 4-key entry instead — §5.4.)

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
6. Unicode-normalize the result to NFC (so a name arriving as NFD on one firmware and NFC on another derives the same slug; NFC is a no-op for ASCII).

All other punctuation is preserved verbatim, and internal multi-space runs become multiple underscores (each space → one `_`). The transform is intentionally script-agnostic: non-ASCII characters are preserved (never ASCII-folded/stripped), so Cyrillic/Greek/CJK/emoji names keep distinct, non-empty slugs rather than collapsing to empty and colliding.

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

1. Calls `get_active_map_id()` if `map_id` is not supplied (via `discover_rooms_payload()`).
2. Calls `discover_rooms_for_vacuum()` (via `discover_rooms_payload()`).
3. **Empty-discovery cache-keep** (RP-005/RF-02, FACADE-2): if the fresh payload has no rooms but
   a previously-cached payload for this map does, the old cache is **kept** — the returned payload
   is the cached one plus `cache_kept: True` and `reason: "empty_discovery_kept"`. A glitched
   discovery must not blank the cache that `save_managed_rooms` reads from. A genuinely-empty
   *first* discovery (no prior cache) still writes normally.
4. Attaches a `"reconciliation"` block onto the payload — `compute_reconciliation()` (from
   `rooms/reconciliation.py`) compares the fresh discovery against the **saved** rooms for this
   map by slug, surfacing `id_changed` / `renamed` / `renamed_and_renumbered` reviews. The saved
   map metadata's `reconciliation_dismissed_at` / `reconciliation_dismissed_token` are passed in
   so a previously-dismissed identical review set is suppressed (§5.5). New/removed rooms are
   owned by drift, not reported here.
5. Stamps `payload["reconciliation"]["plan_token"]` — `compute_plan_token(reviews,
   discovered_rooms)`, a 16-hex-char sha256 fingerprint of the exact review set + discovery the
   user is being shown. The card round-trips it back on `reconcile_room` migrate (REC-5/RP-019).
6. Caches the raw discovery result (with the reconciliation block) under the **resolved active-map
   id**: `data["discovery"][vacuum][str(payload["active_map_id"] or map_id or "")]` — so an omitted
   `map_id` keys under the active map, never the literal `"None"`. (`save`/`rebuild`/`reconcile`
   read back under `str(map_id)`, which lines up because callers pass the resolved active map.)
7. Updates `runtime.active_map_id` for the vacuum.

`discover_rooms` itself never **creates** a map bucket: step 4 reads the existing bucket via
`get_map_bucket`, which since DR-MAP-1 always returns a detached `copy.deepcopy` (or an
empty default-shape dict on a miss) and never writes to storage. A bucket is created the
first time something calls `ensure_map_bucket` for this (vacuum, map) pair — in practice that
happens well before a save, e.g. `reconcile_room` (both the `ignore` and `migrate` arms, §5.5)
and `rebuild_map` (via `rebuild_map_bucket`, [17](17-map-manager.md) §3.4) also call it. Returns
the discovery payload dict.

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
4. Calls `build_managed_rooms()` to merge — passing the brand's
   `new_room_defaults=resolve_new_room_defaults_for_vacuum(vacuum)` and the **map-scoped**
   `rejected_rooms=rejected_room_ids_for(manager, vacuum, map_id=..., include_unscoped=False)`
   (SETUP-REJ-2; see §3.1).
5. **Destructive-replace guard** (RP-005/RF-02): if the merge produced an **empty** room map while
   the stored one is non-empty, returns
   `{"saved": False, "reason": "empty_replacement_refused", "source": "save_managed_rooms",
   "stored_room_count": int}` **without writing anything**.
6. Writes the merged rooms to `map_bucket["rooms"]`.
7. Builds the summary via `build_room_selection_summary(managed_rooms=...)` and writes it to `map_bucket["summary"]`.
8. Calls `manager._refresh_room_derived_state()` to re-run profile matching.
9. Invalidates the room-history cache via `manager._room_history_cache_ready.discard(vacuum)`.
10. Sets `runtime.selected_map_id = str(map_id)`.
11. **If** `managed_rooms` is non-empty: calls `manager.mark_rooms_discovered()`, then `manager.confirm_floor_type()` for each room. These two calls are skipped on an empty result.
12. Fires `_notify_rooms_updated(vacuum, map_id)` so entity-platform callbacks rebuild HA entities.

Returns `{vacuum_entity_id, map_id, room_count, rooms, summary}` (or the refusal dict from step 5).

### 5.3 `remove_map`

```python
manager.room_map.remove_map(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Removes all integration data for the (vacuum, map) pair. The bucket list is **driven by the
`PER_MAP_STORES` registry** (`maps/map_manager.py`, RP-016/RF-20) — the single list of every
per-`(vacuum, map_id)` bucket in the root data dict, so a bucket added there is reachable here
without a second hand-maintained sequence (the defect this closed: `run_profiles` / `queue` /
`onboarding` survived `remove_map` for as long as they existed):

1. Removes the map bucket from `data["maps"][vacuum]` (counted as `rooms_removed`).
2. Pops this map's entry from `setup_progress.rejected_rooms_by_map` (rejections are per-map but
   live inside the per-**vacuum** setup record, so the registry can't reach them; reported as
   `rejected_rooms_removed: [int, ...]` when present). Eufy only rolls map ids forward, but a
   future map can eventually reach a freed number and must not inherit its rejections.
3. Walks `PER_MAP_STORES` for the rest: `discovery`, `room_history`, `room_rule_status`,
   `run_profiles`, `queue`, `onboarding` are **deleted** (`mode="delete"`); `active_jobs` is
   **reset** to `manager._default_active_job_state(...)` (`mode="reset"` — callers index the slot
   without a presence check).

Returns `{vacuum_entity_id, map_id, rooms_removed: int, discovery_removed, history_removed,
rule_status_removed, run_profiles_removed, queue_removed, onboarding_removed,
active_job_cleared: bool[, rejected_rooms_removed: list[int]]}` — each flag `True` only when
that bucket actually held an entry for this map. Unlike `save`/`rebuild`/`reconcile` (which
notify internally), `remove_map` does **not** call `_notify_rooms_updated` — its caller must.

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

1. Reads discovery cache from `data["discovery"][vacuum][map_id_str]`, filtered to rooms whose `map_id` matches.
2. **Destructive-replace guard** (RP-005/RF-02): if the filtered discovery is **empty** while the
   stored room map is not, returns `{"saved": False, "reason": "empty_replacement_refused",
   "source": "rebuild_map", "stored_room_count": int}` **before** calling `rebuild_map_bucket`
   (which would deterministically produce an empty room map from an empty list).
3. Calls `map_manager.rebuild_map_bucket()`, forwarding the `preserve_existing_settings` argument (defaults to `True`). See [17](17-map-manager.md) §3.4 for its slug-led carry + brand-default semantics.
4. Sets `runtime.selected_map_id = str(map_id)` (same as `save`).
5. Calls `_refresh_room_derived_state()` to re-run profile matching on all rooms.
6. Calls `_notify_rooms_updated()` to rebuild HA entities.

`rebuild_map` returns `rebuild_map_bucket`'s dict: `{vacuum_entity_id, map_id, room_count, rooms,
summary, metadata}`. Note its `summary` entries are a **reduced 4-key** shape
(`{room_id, name, slug, order}`) — **not** `build_room_selection_summary`'s 9-key entry — so a
consumer reading `summary.enabled_rooms[].floor_type` / `profile_name` / `clean_passes` /
`edge_mopping` / `carpet` gets nothing after a rebuild until the next save.

Does **not** reset onboarding — use `onboarding.reset_onboarding()` explicitly before `rebuild_map()` if the intent is a full reset.

### 5.5 `reconcile_room`

```python
manager.room_map.reconcile_room(
    *,
    vacuum_entity_id: str,
    map_id: str,
    action: str = "migrate",   # "migrate" | "ignore"
    force: bool = False,
    plan_token: str | None = None,
) -> dict
```

Applies or dismisses the identity-shift reviews (`id_changed` / `renamed` / `renamed_and_renumbered`) surfaced on the cached discovery payload by `discover_rooms` (§5.1). Because a re-segment renumbers many rooms at once, reconciliation is a single per-map decision rather than a per-room prompt. Requires a prior `discover_rooms` to have cached the discovery. An unknown `action` raises `ValueError`.

**`action="migrate"`** atomically rebuilds the saved room map from the cached discovery:

1. Guards an empty discovery: if the cached discovery has no rooms for this map, returns early with `skipped="no_discovery"` (no rebuild) rather than wiping the saved rooms — re-run `discover_rooms` first.
2. **Plan-token gate** (REC-5/RP-019): recomputes the reviews + `compute_plan_token` **fresh** from
   the current discovery/existing rooms (never trusting a cached token). A missing `plan_token`
   returns `skipped="plan_token_required"`; a token that no longer matches returns
   `skipped="plan_changed"` — the plan on screen is not necessarily the plan that would apply.
3. Calls `plan_migration()` (from `rooms/reconciliation.py`) to build the new id-keyed room map, carrying each saved room's durable settings to its new (slug-matched) id.
4. **Minimum-evidence guard** (RP-005/RF-02): when the discovery is smaller than the stored set
   **and** the migration would keep fewer than half the stored rooms, returns
   `skipped="partial_discovery_refused"` (+ `stored_room_count`, `discovered_room_count`) —
   "this discovery looks wrong", deliberately looser than the empty guard because discovery
   legitimately skips unnamed segments. Overridable with `force=True` for a genuine shrinking
   re-map.
5. Writes `plan["rooms"]` to the map bucket and rebuilds its `summary`; stamps `metadata["reconciled_at"]`.
6. Rewrites access-graph `grants_access_to` targets through the same `old->new` id remap (done inside `plan_migration`).
7. Drops the id-keyed rule-status snapshots for **both** the old and new ids (they rebuild on the next preflight) so a freed-then-reused id can't show a stale snapshot.
8. Calls `onboarding.remap_confirmed_floor_types()` so renumbered rooms keep their floor-type confirmation and the start gate does not block with `onboarding_required`.
9. Invalidates the room-history cache (`_room_history_cache_ready.discard(vacuum)`) — it re-ingests under the new ids from the slug-tagged job files.
10. Calls `_refresh_room_derived_state()` then `_notify_rooms_updated()`.

**`action="ignore"`** leaves stored data untouched and stamps
`metadata["reconciliation_dismissed_at"]` **and** `metadata["reconciliation_dismissed_token"]`
(the plan token of the reviews being dismissed, recomputed from the currently-cached discovery).
REC-7/RP-019: a dismissal suppresses only while the fresh reviews fingerprint the **same** as
what was dismissed — a genuinely new shift still surfaces. No `plan_token` is needed to ignore.

Returns `{vacuum_entity_id, map_id, action, migrated_room_count, id_remap, dropped[, skipped[,
stored_room_count, discovered_room_count]]}`. Registered as the `reconcile_room` service
(`supports_response=True`).

**Reconciliation shapes.** `compute_reconciliation(*, discovered_rooms, existing_rooms,
dismissed_at=None, dismissed_plan_token=None)` (§5.1, cached on the discovery payload as
`payload["reconciliation"]`) returns `{"reviews": [...], "has_changes": bool}` (plus
`"dismissed": True` when a dismissal suppressed an identical set) where each review is one of:
- `{"kind": "id_changed", "slug", "name", "old_id": int, "new_id": int}` — same slug, new id;
- `{"kind": "renamed", "room_id": int, "old_slug", "new_slug", "old_name", "new_name"}` — same
  id, new name. A `renamed` review is **suppressed** when the old slug is still present in
  discovery (that's a renumber — already surfaced as an `id_changed` for the other room; firing
  both would contradict).
- `{"kind": "renamed_and_renumbered", "old_id", "new_id", "old_slug", "new_slug", "old_name",
  "new_name"}` (REC-3/RP-019) — a room renamed AND renumbered in one re-map matches neither
  branch; when **exactly one** existing room and **exactly one** discovered room are left
  unclaimed, they can only be each other. Anything more than one on either side is ambiguous
  and deliberately left unpaired.

`plan_migration` returns `{"rooms": {id_str: cfg}, "id_remap": {old_id: new_id}, "dropped":
[slug, ...]}` (dropped is sorted). Carry is slug-led with an **id fallback** (a saved room whose
slug vanished but whose id survives is still carried), guarded by a `consumed_old_ids` set
(freed-then-reused ids never transplant settings), plus the same REC-3 singleton pairing as the
reviews (the one-left-on-each-side room is carried, not dropped). It rewrites each room's
`grants_access_to` through the remap, dropping targets that don't resolve. (`reconcile_room`
migrate **stringifies** the remap keys — `{str(old): new}` — and the `ignore` return has
`id_remap={}`, `dropped=[]`.)

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
| `floor_type` | str | One of: `"hardwood"`, `"laminate"`, `"tile"`, `"marble"`, `"granite"`, `"concrete"`, `"carpet_low_pile"`, `"carpet_high_pile"`. Carpet pile is encoded in the value — use `floor_type.startswith("carpet")` rather than a separate flag. (The old `"carpet"` + `carpet_type` shape was migrated away.) |
| `profile_name` | str | Matched room profile name, or `"custom"` |
| `clean_mode` | str | `"vacuum"`, `"mop"`, or `"vacuum_mop"` |
| `fan_speed` | str | `"Quiet"` / `"Standard"` / `"Boost"` / `"Max"` (Eufy vocabulary); a new room's value comes from the brand's default profile (Eufy: `"Standard"` via `vacuum_quick`), not a hardcoded literal — a brand whose profile omits the axis leaves it `""` (§3.1) |
| `water_level` | str | e.g. `"Off"`, `"Low"`, `"Medium"`, `"High"` |
| `clean_intensity` | str | `"Quick"` / `"Narrow"` / `"Deep"`; default `"Quick"` (legacy `"Standard"`/`"Normal"` are dead — folded to `"Quick"`) |
| `clean_passes` | int | Number of cleaning passes; minimum 1. (The "1 or 2" cap is a frontend modifier constraint, not a room-model rule.) |
| `edge_mopping` | bool | Whether edge mopping is enabled |
| `path_type` | str | From matched profile |
| `order` | int | Dispatch order (defaults to the room's 1-based position in discovery order) |
| `is_dock_room` | bool | Whether this room contains the dock (defaults `False`) |
| `is_transition` | bool | Whether this room is a transition/passage room (defaults `False`) |
| `rules` | list | Automation rules (see [09-room-rules-system.md](09-room-rules-system.md)) |
| `grants_access_to` | list | Access graph (room IDs this room grants access to) |
| `color` | str \| None | Per-room map fill override, a canonical `"#rrggbb"` (lowercased), or `None`/absent to use the themeable room-fill palette. Purely presentational; preserved across re-save (`room_manager.py`) and rebuild (`map_manager.py`). See [themeable-map-palette.md](frontend/themeable-map-palette.md). |
| `label_anchor` | dict | Optional `{pct_x, pct_y}` (0-100, 4 dp) — the dragged position of the room's m² label chip. Lives **on the room record** (A5-FURNIS-4) so it rides a re-import through reconciliation's slug matching (`plan_migration`'s `carried = dict(source)` preserves it); written by `mapping_services.py::_handle_set_area_label_anchor`, absent until first dragged, `null` both `pct_x`/`pct_y` to clear. The legacy map-level `area_label_anchors` side-table is migrated onto rooms lazily on the write path only (never on read) via `_migrate_area_label_anchors`, and stays as a fallback for rooms with no managed record (e.g. a discovered-but-unmanaged room the card renders from the live map source). **Not a `RoomConfig` field** — see the note below. |

**Defaults** (new room, from `RoomConfig` + the brand's default profile via
`rooms/room_defaults.py` — see §3.1): `enabled=<True on first import, False on incremental
discovery>`, `order=<1-based discovery index>`, `profile_name=<brand default_profile;
framework "vacuum_quick">`, `floor_type="hardwood"`, and the setting fields from that profile —
for Eufy/framework `vacuum_quick`: `clean_mode="vacuum"`, `fan_speed="Standard"`,
`water_level="Off"`, `clean_intensity="Quick"`, `path_type="wide"`, `clean_passes=1`,
`edge_mopping=False`. A brand whose profile omits an axis leaves the `RoomConfig` field default
(`""` for `fan_speed`/`water_level`/`clean_intensity` — visibly unset; Roborock declares no
`clean_intensity`). Plus `is_dock_room=False`, `is_transition=False`, `grants_access_to=[]`,
`rules=[]`, `color=None`, `is_configured=<see §3.1 CRUD-3 gate>`,
`configured_at=<existing or now on the save path; carried-forward or None on rebuild>`.

**Two writers, one dataclass, plus a load-time backfill.** Both room writers —
`build_managed_rooms` (save path) and `rebuild_map_bucket` ([17](17-map-manager.md) §3.4,
rebuild path) — now build every record through the **same `RoomConfig` dataclass**, so the
field list cannot drift between them (`is_transition` had drifted exactly this way before; it
is now a `RoomConfig` field carried by both). The approval flags deliberately differ per
writer: the save path is an explicit user approval (`is_configured` per the CRUD-3 gate,
`configured_at` stamped `_iso_now()` when new); the rebuild path **preserves** whatever
approval already existed (`True` for pre-field data or a carried-forward room, `False` for a
genuinely new room — a rebuild must neither un-approve nor silently auto-approve). Neither
writer emits `label_anchor` — it is not a `RoomConfig` field, so a re-save or rebuild **drops**
it unless the room came from `plan_migration`'s carry (which copies the raw dict, not through
`RoomConfig`).

- A **load-time backfill** in `EufyVacuumManager.__init__` (`core/manager.py`) still runs on
  every construction: `setdefault` for `path_type=None`, `is_dock_room=False`,
  `is_transition=False`, `grants_access_to=[]`, `rules=[]`, `floor_type="hardwood"`,
  `profile_name="vacuum_quick"`; and it **migrates** `floor_type=="carpet"` + `carpet_type` →
  `carpet_<pile>` and pops the legacy `carpet` / `carpet_type` keys. This is what makes old
  on-disk records uniform after a reload — a reconstruction must reproduce it or the record
  won't match. (The backfill does **not** `setdefault("is_configured", …)`; that flag is now
  owned by the two writers above, both of which always set it.)

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
