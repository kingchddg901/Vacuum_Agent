# Map Manager — Developer Reference

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
- **Image analysis + map UI state** (written by external handlers, primarily `mapping/mapping_services.py`) — `image_segments`, `custom_segments`, `segmentation_mode`, `image_segment_adjustments`, `image_variants`, `segment_room_links`, `companion_anchors`.

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
    "custom_segments": dict,        # user-authored no-CV segment store (replace-all,
                                    #   written by set_custom_segments). Same shape as
                                    #   image_segments: {available, engine:"custom",
                                    #   analyzed_at, image:{width,height,variant:"custom"},
                                    #   segments, summary}. Coexists with image_segments —
                                    #   both persist independently.
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
                                    #   Variant ∈ {default, dark, light, custom}. dark/
                                    #   light/default feed the segmenter; "custom" is the
                                    #   no-CV authoring backdrop and is never segmented —
                                    #   its width/height are the px space set_custom_segments
                                    #   rasterises against.
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
}
```

Metadata keys are written by `save_map_discovery_snapshot()` (`last_discovery`, `discovered_rooms`) and `rebuild_map_bucket()` (`last_rebuild`). There is no `display_name` or `discovered_at` field.

> The image/UI-state keys are documented in full in [16-mapping-system](16-mapping-system.md); their derived read-time fields (`polygon_pct`, injected `room_id`, applied `adjustments`) are computed by `mapping/mapping_services.py::_handle_get_map_segments`, not stored.

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

> **Image/UI-state keys are not pre-initialised.** `ensure_map_bucket()` writes only `map_id`, `metadata`, `rooms`, and `summary`. The image-analysis / map-UI-state keys (`image_segments`, `custom_segments`, `segmentation_mode`, `image_segment_adjustments`, `image_variants`, `segment_room_links`, `companion_anchors` — see §2) are written **on demand** by the external handlers in `mapping/mapping_services.py`, each of which calls `ensure_map_bucket()` and then `setdefault()`s the key it owns. Consumers must therefore read these via `bucket.get(key) or {}` rather than assuming presence.

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

The following keys live in the same bucket but are written by `mapping/mapping_services.py`, **not** by `map_manager.py` (none are created by `ensure_map_bucket()` — see §3.1):

| Path | Type | Description |
|---|---|---|
| `…[str(map_id)]["image_segments"]` | dict | CV segmentation cache (base "cv" store). Written by `analyze_map_image` |
| `…[str(map_id)]["custom_segments"]` | dict | User-authored no-CV segment store (replace-all). Written by `set_custom_segments`; coexists with `image_segments` |
| `…[str(map_id)]["segmentation_mode"]` | str | `"cv"` \| `"custom"`; selects which segment store `get_map_segments` serves. Default `"cv"`. Written by `set_segmentation_mode` (flag flip only) |
| `…[str(map_id)]["image_segment_adjustments"]` | dict | `{segment_id: {offset_x, offset_y, edge_left/right/top/bottom, vertex_moves:[{index,delta_x,delta_y}]}}` manual CV-segment edits. Written by `adjust_map_segment` |
| `…[str(map_id)]["image_variants"]` | dict | `{variant: {variant, path, browser_url, width, height}}` uploaded backdrops, variant ∈ default/dark/light/custom. Written by `upload_map_image`, pruned by `delete_map_image` |
| `…[str(map_id)]["segment_room_links"]` | dict | `{segment_id: room_id}` 1:1 segment→room links. Written by `set_segment_room_link` |
| `…[str(map_id)]["companion_anchors"]` | dict | `{room_id\|"dock": {pct_x, pct_y}}` sprite anchors (0-100 %); reserved `"dock"` key is a map-level mascot spot. Written by `set_companion_anchor` |

---

## 5. Integration Points

| Caller | Function | When |
|---|---|---|
| `rooms/room_crud.py` | `ensure_map_bucket()`, `rebuild_map_bucket()` | `save_managed_rooms()`, `rebuild_map()` |
| `rooms/room_crud.py` | `get_map_bucket()`, `get_vacuum_maps_summary()` | `get_managed_rooms()`, `get_managed_maps_summary()` |
| `core/manager.py` | `get_map_bucket()` | queue and room-clean payload builds |
| `rooms/access_graph.py`, `profiles/manager.py` | `get_map_bucket()`, `ensure_map_bucket()` | automation-metadata reads, room/run-profile reads |
| `setup/delete.py` | reads `data["maps"]` directly | map-delete protection evaluation |

> `save_map_discovery_snapshot()` has no current caller — it writes the `last_discovery` / `discovered_rooms` metadata keys (see §3.3) but the live discovery path (`rooms/room_crud.py::discover_rooms()`) caches into `data["discovery"]` directly instead.

> **See also:** [15-setup-system](15-setup-system.md) §3 for the `import_active_map` workflow that calls `ensure_map_bucket()` and `rebuild_map_bucket()`; [08-rooms-system](08-rooms-system.md) §5 for `RoomMapManager` (`rooms/room_crud.py`) which reads and writes the rooms dict inside each map bucket.
