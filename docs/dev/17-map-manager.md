# 17 — Map Manager

> **Scope:** Complete implementation reference for `maps/map_manager.py`. Every function signature, storage path, and behavior is derived directly from the source. A developer should be able to re-implement the map manager from this document alone.

---

## 1. Overview

`maps/map_manager.py` is a collection of **pure functions** with no class, no state, and no async operations. Every function is **keyword-only** (all parameters after `*`) and takes `data` (the integration's live storage dict), operating on `data["maps"]` directly.

All mutations are in-place on the `data` dict. The caller is responsible for calling `manager.async_save()` after mutating.

**Module:** `custom_components/eufy_vacuum/maps/map_manager.py`

---

## 2. Map Bucket Schema

The canonical unit is a **map bucket** — a dict stored at `data["maps"][vacuum_entity_id][str(map_id)]`. The bucket is a **union of two concerns** that happen to share the same per-map key:

- **Map management** (owned by `maps/map_manager.py`) — `map_id`, `metadata`, `rooms`, `summary`.
- **Image analysis + map UI state** (written by external handlers, primarily `mapping/mapping_services.py`) — `image_segments`, `custom_segments`, `custom_layouts`, `active_custom_layout_id`, `segmentation_mode`, `image_segment_adjustments`, `image_variants`, `segment_room_links`, `companion_anchors`, `saved_zones`, `hidden_regions`, `area_label_anchors`, `live_map_rotation`, `overlay_visibility`.

`map_manager.py` only ever touches the first group; it never reads or initialises the image/UI-state keys. They are listed here because they live in the same bucket and any code that walks `data["maps"]` (delete protection, debug dumps) will encounter them.

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

    # --- image-analysis / map-UI-state keys (written by mapping/mapping_services.py;
    #     NOT managed by map_manager.py, NOT pre-initialised by ensure_map_bucket) ---
    "image_segments":  dict,        # canonical CV SegmentationResult cache (the
                                    #   base/"cv" segment store). Written by
                                    #   analyze_map_image; {available, analyzed_at,
                                    #   image, segments, summary, ...}.
    "custom_segments": dict,        # LEGACY single user-authored no-CV segment store
                                    #   (replace-all). Same shape as image_segments:
                                    #   {available, engine:"custom", analyzed_at,
                                    #   image:{width,height,variant:"custom"}, segments,
                                    #   summary}. Migrated lazily + non-destructively into a
                                    #   "Custom" entry under custom_layouts (kept, never
                                    #   deleted) — see §10 of 11-mapping-system.
    "custom_layouts": dict,         # {layout_id: layout}; the named multi-custom-layout
                                    #   collection. Each layout owns everything per-layout:
                                    #   {id, name, backdrop_variant, backdrop_source?,
                                    #   custom_segments, segment_room_links,
                                    #   companion_anchors, created_at, updated_at}.
                                    #   Optional backdrop_source:"live" pins the layout to
                                    #   the brand's live-map image entity as its backdrop
                                    #   (the card's "Live map" source) instead of an
                                    #   uploaded custom_<id> variant; absent for normal
                                    #   layouts. Set by create_custom_layout's
                                    #   backdrop_source param (_create_layout) and surfaced
                                    #   in the get_map_segments layout summary. CRUD + lazy
                                    #   legacy migration (_migrate_custom_layouts) live in
                                    #   mapping_services.py.
    "active_custom_layout_id": str, # id of the layout served in "custom" mode, or None.
    "segmentation_mode": str,       # "cv" | "custom"; pointer that selects which of the
                                    #   two segment stores get_map_segments serves.
                                    #   Defaults to "cv" when absent. set_segmentation_mode
                                    #   only flips this flag — it NEVER re-runs the segmenter.
    "image_segment_adjustments": {  # per-segment manual edits to CV segments, keyed by
                                    #   segment_id; applied to polygons at read time.
        "<segment_id>": {
            "offset_x":   int,      # whole-shape translation
            "offset_y":   int,
            "edge_left":  int,      # per-edge nudge (10% band each side)
            "edge_right": int,
            "edge_top":   int,
            "edge_bottom": int,
            "vertex_moves": [       # individual vertex deltas
                {"index": int, "delta_x": int, "delta_y": int},
            ],
        },
    },
    "image_variants": {             # uploaded backdrop images, keyed by variant name.
                                    #   Fixed variants ∈ {default, dark, light, custom}; dark/
                                    #   light/default feed the segmenter; "custom" is the
                                    #   no-CV authoring backdrop and is never segmented —
                                    #   its width/height are the px space set_custom_segments
                                    #   rasterises against. Per-layout backdrops (custom_<id>)
                                    #   and furnished-art keys (custom_<id>_home_art,
                                    #   custom_<id>_room_<rid>) ALSO live here — see
                                    #   11-mapping-system §6.
        "<variant>": {
            "variant":     str,     # echoes the key
            "path":        str,     # on-disk PNG path
            "browser_url": str,     # /eufy_vacuum/maps/<object_id>/map_<map_id><suffix>.png
            "width":       int,     # measured pixel dims (PIL), or declared fallback
            "height":      int,
        },
    },
    "segment_room_links": dict[str, str],   # {segment_id: room_id}; user-assigned 1:1
                                            #   segment→room mapping. Injected as a
                                            #   per-segment room_id field at read time.
    "companion_anchors": {          # {room_id | "dock": {pct_x, pct_y}} companion-sprite
                                    #   anchor positions, 0-100 % from the image top-left.
                                    #   The reserved "dock" key is a map-level spot the
                                    #   docked/idle mascot homes to (NOT a room).
        "<room_id|'dock'>": {"pct_x": float, "pct_y": float},
    },
    "saved_zones": {                # {zone_id: zone} named reusable clean regions
                                    #   (draw-a-box saved zones). Written by
                                    #   _create_saved_zone / _migrate_saved_zones.
        "<zone_id>": {
            "id":          str,
            "name":        str,     # user label; "Zone" when blank
            "geometry":    list,    # [[x, y], ...] normalized 0-1 point list (the
                                    #   zone shape; dispatch works off it directly).
                                    #   Sanitized per-point (finite, clamped 0-1) AND
                                    #   as a whole (bbox rejected if either side <
                                    #   0.01 -- matches dispatch's own degenerate
                                    #   check, so a saved zone can never be
                                    #   permanently unrepairable at clean time;
                                    #   RP-032/A1-SERVIC-4).
            "area_m2":     float,   # or None until computed (Wave 2)
            "room_number": int,     # filing bucket, or None until computed (Wave 2)
            "kind":        str,     # "clean" -- the only value the schema currently
                                    #   accepts (no dispatch path reads any other)
            "created_at":  str,     # iso
            "updated_at":  str,     # iso
        },
    },
    "hidden_regions": list,         # [[x0, y0, x1, y1], ...] normalized 0-1 top-left-
                                    #   origin mask rects the card draws to hide map
                                    #   noise. Replace-all; each entry sanitized (4
                                    #   finite numbers, clamped 0-1, ordered min<max,
                                    #   degenerate dropped). Written by
                                    #   _handle_set_hidden_regions.
    "area_label_anchors": {         # {room_id: {pct_x, pct_y}} dragged position of a
                                    #   room's m² label chip, 0-100 % of the map content
                                    #   box. Written by _handle_set_area_label_anchor
                                    #   (null both to reset to room centre).
        "<room_id>": {"pct_x": float, "pct_y": float},
    },
    "live_map_rotation": int,       # display-only live-map rotation ∈ {0, 90, 180, 270}.
                                    #   Never affects cleaning/dispatch. Written by
                                    #   _handle_set_live_map_rotation.
    "overlay_visibility": dict,     # {layer: bool} partial delta map — stores only the
                                    #   user's overrides, merged over defaults at read
                                    #   time via resolve_overlay_visibility; reset:true
                                    #   clears it. Written by
                                    #   _handle_set_map_overlay_visibility.

    # --- co-resident keys owned by OTHER subsystems (not mapping_services) ---
    "queue_breaks": list,           # ordered queue-break markers for the run in progress;
                                    #   written by the queue engine (core/manager.py), cleared
                                    #   at run end. See 07-queue-engine. NOT map-manager owned.
    "learned_zones": dict,          # per-map learned saved-zone store, persisted with the map;
                                    #   written by learning (learning/manager.py, zone_learning).
                                    #   See 10-learning-system. NOT map-manager owned.
}
```

Metadata keys are written by `save_map_discovery_snapshot()` (`last_discovery`, `discovered_rooms`) and `rebuild_map_bucket()` (`last_rebuild`). `rooms/room_crud.py::reconcile_room` additionally writes two ISO-timestamp `metadata` keys — `reconciled_at` and `reconciliation_dismissed_at` — which `map_manager.py` never touches. There is no `display_name` or `discovered_at` field.

> The image/UI-state keys are documented in full in [11-mapping-system](11-mapping-system.md); their derived read-time fields (`polygon_pct`, injected `room_id`, applied `adjustments`) are computed by `mapping/mapping_services.py::_handle_get_map_segments`, not stored.

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

> **Image/UI-state keys are not pre-initialised.** `ensure_map_bucket()` writes only `map_id`, `metadata`, `rooms`, and `summary`. The image-analysis / map-UI-state keys (`image_segments`, `custom_segments`, `custom_layouts`, `active_custom_layout_id`, `segmentation_mode`, `image_segment_adjustments`, `image_variants`, `segment_room_links`, `companion_anchors`, `saved_zones`, `hidden_regions`, `area_label_anchors`, `live_map_rotation`, `overlay_visibility` — see §2) are written **on demand** by the external handlers in `mapping/mapping_services.py`, each of which calls `ensure_map_bucket()` and then `setdefault()`s the key it owns. (`custom_layouts` / `active_custom_layout_id` are seeded by `_migrate_custom_layouts()`, which the layout-CRUD handlers run before mutating; legacy `custom_segments` is migrated lazily into a layout — see [Mapping system](11-mapping-system.md) §10.) Consumers must therefore read these via `bucket.get(key) or {}` rather than assuming presence.

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

When `preserve_existing_settings=True` (default), user settings (fan speed, clean mode, floor type, etc.) are preserved for rooms that still exist in the discovery list. New rooms get safe defaults. When `preserve_existing_settings=False`, `previous` is forced to `{}` for **every** room, so all rooms take the defaults below — used for full reset flows.

**Input contract (`discovered_rooms`).** Each element **must** carry `room_id` and `name`: `int(room["room_id"])` and `str(room["name"])` raise `KeyError` if absent (and `ValueError` if `room_id` is not int-coercible — `"3"` → `3` is fine). `slug` is optional (`room.get("slug")` → `None`). The element's own `map_id`, if any, is **ignored** — the function stamps the `map_id` **parameter** onto every room. (The caller `rooms/room_crud.py::rebuild_map` pre-filters `discovered_rooms` to the target map, so `rebuild_map_bucket` itself does not.)

**Rebuilt room-record schema** (the exact per-room dict written to `bucket["rooms"][<room_id_str>]`, `map_manager.py:140-172`). This is `map_manager.py`'s own writer; the canonical save-path record (`build_managed_rooms`) and the load-time backfill diverge from it — see [08-rooms-system](08-rooms-system.md) §6 for the full three-writers reconciliation.

| Field | Type | Default (when `previous` empty) | Notes |
|---|---|---|---|
| `room_id` | `int` | — (required) | `int(room["room_id"])` from discovery |
| `map_id` | `str` | `str(map_id)` | the **parameter**, never the element's own |
| `name` | `str` | — (required) | `str(room["name"])` |
| `slug` | `str \| None` | `None` | `room.get("slug")` (discovery, optional) |
| `enabled` | `bool` | `True` | |
| `order` | `int` | `index` | 1-based `enumerate` position |
| `profile_name` | `str` | `"vacuum_quick"` | |
| `floor_type` | `str` | `"hardwood"` | carpet pile encoded in the value (e.g. `"carpet_low_pile"`); **no** separate `carpet_type` field |
| `clean_mode` | `str` | `"vacuum"` | |
| `fan_speed` | `str` | `"Max"` | |
| `water_level` | `str` | `"Off"` | |
| `clean_intensity` | `str` | `"Quick"` | |
| `clean_passes` | `int` | `1` | |
| `edge_mopping` | `bool` | `False` | |
| `path_type` | `Any \| None` | `None` | `previous.get("path_type")` — **no coercion** |
| `is_dock_room` | `bool` | `False` | |
| `is_transition` | `bool` | `False` | **Not** a `RoomConfig` field — the save-path record omits it until a reload backfills it (08 §6, CS-3) |
| `is_configured` | `bool` | `True` | setup-approval flag; **gates HA entity creation** (`entity_helpers.py` `sort_room_items(..., configured_only=True)`) and the drift-tracker "removed" signal. Defaults `True` because a saved map-bucket room is an approved room — this carry-forward is the BUG-A fix (08 §6). |
| `configured_at` | `str \| None` | `None` | `previous.get("configured_at")`; new rooms stay `None` even when `is_configured` is `True` (the save-path stamps `_iso_now()` instead — CS-4) |
| `color` | `str \| None` | `None` | per-room map-fill override, preserved across rebuild |
| `grants_access_to` | `list` | `[]` | list-guarded (`list(previous.get(...))` iff already a list, else `[]`) |
| `rules` | `list` | `[]` | list-guarded, same pattern |

**Bucket summary shape** (written to `bucket["summary"]`, and echoed in the return's `summary`):

```python
{
    "enabled_count":  int,
    "disabled_count": int,
    "enabled_rooms":  [ {room_id: int, name, slug, order}, ... ],   # sorted by (int(order), str(name))
    "disabled_rooms": [ {room_id: int, name, slug, order}, ... ],   # sorted by str(name)
}
```

> **BUG-B (open, doc-critical divergence).** `rebuild_map_bucket` is the **only** summary writer that emits the **reduced 4-key** per-room entry above. Every other writer — save (`room_crud.py`), reconcile, queue-drain (`core/manager.py`), profiles apply, room entities — uses the canonical **9-key** builder `build_room_selection_summary` (`rooms/room_manager.py:99-131`), whose entry is `{room_id, name, slug, order, profile_name, floor_type, clean_passes, edge_mopping, carpet}` where `carpet = str(floor_type).startswith("carpet")`. So a map whose summary was **last written by a rebuild** silently loses `profile_name`/`floor_type`/`clean_passes`/`edge_mopping`/`carpet` for any card or service reading the summary, until a non-rebuild write repopulates it. The top-level keys and sort orders are identical between the two writers; only the per-entry field set differs. Fix candidate: have `rebuild_map_bucket` call `build_room_selection_summary(managed_rooms=rebuilt_rooms)` instead of its inline reducer, unifying all writers.

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
            "enabled_room_count":  int,   # int(summary.get("enabled_count", 0))
            "disabled_room_count": int,   # int(summary.get("disabled_count", 0))
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

The following keys live in the same bucket but are written by **other subsystems** (primarily `mapping/mapping_services.py`), **not** by `map_manager.py` (none are created by `ensure_map_bucket()` — see §3.1):

| Path | Type | Description |
|---|---|---|
| `…[str(map_id)]["image_segments"]` | dict | CV segmentation cache (base "cv" store). Written by `analyze_map_image` |
| `…[str(map_id)]["custom_segments"]` | dict | **Legacy** single user-authored no-CV segment store (replace-all). Migrated lazily + non-destructively into a `"Custom"` entry under `custom_layouts` — see [Mapping system](11-mapping-system.md) §10 |
| `…[str(map_id)]["custom_layouts"]` | dict | `{layout_id: {id, name, backdrop_variant, backdrop_source?, custom_segments, segment_room_links, companion_anchors, created_at, updated_at}}` named multi-custom-layout collection (each layout owns its own backdrop/segments/links/anchors). Optional `backdrop_source:"live"` pins the layout to the brand's live-map image entity (the card's "Live map" source) instead of an uploaded `custom_<id>` variant — absent for normal layouts; set by `create_custom_layout`'s `backdrop_source` param, surfaced in the `get_map_segments` layout summary. Seeded by `_migrate_custom_layouts`, CRUD by the layout handlers |
| `…[str(map_id)]["active_custom_layout_id"]` | str \| None | Id of the layout served in `"custom"` mode, or `None`. Seeded by `_migrate_custom_layouts` |
| `…[str(map_id)]["segmentation_mode"]` | str | `"cv"` \| `"custom"`; selects which segment store `get_map_segments` serves. Default `"cv"`. Written by `set_segmentation_mode` (flag flip only) |
| `…[str(map_id)]["image_segment_adjustments"]` | dict | `{segment_id: {offset_x, offset_y, edge_left/right/top/bottom, vertex_moves:[{index,delta_x,delta_y}]}}` manual CV-segment edits. Written by `adjust_map_segment` |
| `…[str(map_id)]["image_variants"]` | dict | `{variant: {variant, path, browser_url, width, height}}` uploaded backdrops, variant ∈ default/dark/light/custom. Written by `upload_map_image`, pruned by `delete_map_image` |
| `…[str(map_id)]["segment_room_links"]` | dict | `{segment_id: room_id}` 1:1 segment→room links. Written by `set_segment_room_link` |
| `…[str(map_id)]["companion_anchors"]` | dict | `{room_id\|"dock": {pct_x, pct_y}}` sprite anchors (0-100 %); reserved `"dock"` key is a map-level mascot spot. Written by `set_companion_anchor` |
| `…[str(map_id)]["saved_zones"]` | dict | `{zone_id: {id, name, geometry, area_m2, room_number, kind, created_at, updated_at}}` named reusable clean regions; `geometry` is a normalized 0-1 point list, sanitized per-point AND as a whole (bbox rejected if either side < 0.01, matching dispatch's own degenerate check), `kind` only accepts `"clean"` (no dispatch path reads any other value), `area_m2`/`room_number` are `None` until computed. Seeded by `_migrate_saved_zones`, written by `_create_saved_zone` |
| `…[str(map_id)]["hidden_regions"]` | list | `[[x0, y0, x1, y1], …]` normalized 0-1 top-left-origin mask rects that hide map noise (replace-all; sanitized — finite, clamped 0-1, ordered min<max, degenerate dropped). Written by `_handle_set_hidden_regions` |
| `…[str(map_id)]["area_label_anchors"]` | dict | `{room_id: {pct_x, pct_y}}` dragged m² label positions (0-100 % of the map content box); null both to reset to room centre. Written by `_handle_set_area_label_anchor` |
| `…[str(map_id)]["live_map_rotation"]` | int | Display-only live-map rotation ∈ `{0, 90, 180, 270}`; never affects cleaning/dispatch. Written by `_handle_set_live_map_rotation` |
| `…[str(map_id)]["overlay_visibility"]` | dict | `{layer: bool}` partial delta map storing only user overrides (merged over defaults at read time via `resolve_overlay_visibility`; `reset:true` clears it). Written by `_handle_set_map_overlay_visibility` |
| `…[str(map_id)]["queue_breaks"]` | list | Ordered queue-break markers for the run in progress; written by the queue engine (`core/manager.py`), cleared at run end. Owned by [07-queue-engine](07-queue-engine.md) |
| `…[str(map_id)]["learned_zones"]` | dict | Per-map learned saved-zone store, persisted with the map; written by `learning/manager.py` (`zone_learning`). Owned by [10-learning-system](10-learning-system.md) |

---

## 5. Integration Points

| Caller | Function | When |
|---|---|---|
| `rooms/room_crud.py` | `ensure_map_bucket()`, `rebuild_map_bucket()` | `save_managed_rooms()`, `rebuild_map()` |
| `rooms/room_crud.py` | `get_map_bucket()`, `get_vacuum_maps_summary()` | `get_managed_rooms()`, `get_vacuum_maps()` |
| `core/manager.py` | `get_map_bucket()`, **`ensure_map_bucket()`** (≈8 sites) | queue and room-clean payload builds; the queue-drain path also **mutates `rooms` and rewrites the 9-key `summary`** via `build_room_selection_summary` |
| `learning/manager.py` | `ensure_map_bucket()` | writes the per-map `learned_zones` store |
| `rooms/access_graph.py`, `profiles/manager.py` | `get_map_bucket()`, `ensure_map_bucket()` | automation-metadata reads, room/run-profile reads |
| `setup/delete.py` | reads `data["maps"]` directly | map-delete protection evaluation |

> The public read method is **`get_vacuum_maps()`** (`rooms/room_crud.py`, delegated by `core/manager.py`), which wraps `get_vacuum_maps_summary()`. There is no `get_managed_maps_summary()`.

> `save_map_discovery_snapshot()` has no current caller — it writes the `last_discovery` / `discovered_rooms` metadata keys (see §3.3) but the live discovery path (`rooms/room_crud.py::discover_rooms()`) caches into `data["discovery"]` directly instead.

> **See also:** [15-setup-system](15-setup-system.md) §3 for the `import_active_map` workflow that calls `ensure_map_bucket()` and `rebuild_map_bucket()`; [08-rooms-system](08-rooms-system.md) §5 for `RoomMapManager` (`rooms/room_crud.py`) which reads and writes the rooms dict inside each map bucket.
