# 03 — Data Model Reference

Canonical shape reference for every major object in `eufy_vacuum`. All field
names, types, and constraints are derived directly from source. A developer
reading this document should be able to reconstruct the full data model without
reading source.

---

## Table of Contents

1. [HA Storage Schema](#1-ha-storage-schema)
2. [Room Record](#2-room-record)
3. [Map Object](#3-map-object)
4. [Queue Payload](#4-queue-payload)
5. [Active Job State](#5-active-job-state)
6. [Profiles](#6-profiles)
7. [Room History](#7-room-history)
8. [Room Rule Status](#8-room-rule-status)
9. [Learning Record (Completed Job)](#9-learning-record-completed-job)
10. [Learning Estimate](#10-learning-estimate)
11. [Theme Object](#11-theme-object)
12. [Setup Progress](#12-setup-progress)
13. [Error Tracker](#13-error-tracker)
14. [Incomplete Run Log](#14-incomplete-run-log)
15. [Trouble Rooms Log](#15-trouble-rooms-log)
16. [Key Constraints](#16-key-constraints)

---

## 1. HA Storage Schema

**File:** `.storage/eufy_vacuum.storage`  
**Storage key:** `eufy_vacuum.storage`  
**Schema version:** `1` (constant in `core/storage.py`)  
**Managed by:** `EufyVacuumStorage` (`core/storage.py`) via HA's `Store` helper.  
**Never edit this file directly** — use the HA UI or service calls. Direct edits
produce `.corrupt` backup files.

### Top-level shape

```
{
  "vacuums":          dict[vacuum_entity_id, VacuumBucket]
  "maps":             dict[vacuum_entity_id, dict[map_id_str, MapBucket]]
  "capabilities":     dict[vacuum_entity_id, CapabilityBucket]
  "active_jobs":      dict[vacuum_entity_id, dict[map_id_str, ActiveJobState]]
  "profiles":         dict["room_profiles", dict[profile_name, RoomProfileEntry]]
  "run_profiles":     dict[vacuum_entity_id, dict[map_id_str, dict[profile_id, RunProfileEntry]]]
  "room_history":     dict[vacuum_entity_id, dict[map_id_str, dict[room_id_str, RoomHistoryEntry]]]
  "room_rule_status": dict[vacuum_entity_id, dict[map_id_str, dict[room_id_str, RuleStatusEntry]]]
  "setup_progress":   dict[vacuum_entity_id, SetupProgressRecord]
  "error_tracker":    dict[vacuum_entity_id, ErrorTrackerBucket]
  "theme":            ThemeRoot
  "maintenance":      dict                             # domain bucket; see maintenance/
  "dock_events":      dict                             # domain bucket; see dock/
  "onboarding":       dict                             # domain bucket; see onboarding/
  "discovery":        dict[vacuum_entity_id, dict[map_id, DiscoveryPayload]]
  "queue":            dict[vacuum_entity_id, dict[map_id_str, QueueState]]    # derived snapshot; see §4
  "payloads":         dict[vacuum_entity_id, dict[map_id_str, PayloadState]]  # derived room-clean payload snapshot; see §4
}
```

`queue` and `payloads` are **derived-state** snapshots: `core/manager.py` lazily
`setdefault`s each (`data["queue"][vacuum][map]` = the queue state,
`data["payloads"][vacuum][map]` = the resolved room-clean payload) when the queue
or a run is built, and they persist alongside the rest of `self.data`. Like the
other lazily-created keys, a reader must tolerate their absence (see §16's
derived-state note).

**Key seeding:** `core/storage.py async_load()` returns a default dict with
`vacuums`, `maps`, `theme`, `analytics`, `maintenance`, `dock_events`,
`onboarding`, and `error_tracker` already present on an empty store.
`async_initialize()` (`core/manager.py`) then `setdefault`s the keys it depends
on — `vacuums` (already present), `capabilities`, `room_history`, and
`room_rule_status`. The remaining keys above (`active_jobs`, `profiles`,
`run_profiles`, `setup_progress`, `discovery`) are created lazily by their
owning subsystems on first write, so they may be absent until that subsystem
first runs. Code that reads any other key must tolerate its absence.

**Legacy cleanup:** The `icons` block, if present, is deleted unconditionally
during `async_initialize()`. It was written by a removed platform and serves no
purpose. `analytics` is part of the storage default but is currently unused
(always `{}`).

### VacuumBucket

`data["vacuums"][vacuum_entity_id]`

```
{
  "pause_timeout_minutes_default": int   # default 0; non-negative
}
```

### MapBucket

`data["maps"][vacuum_entity_id][map_id_str]`

The per-map bucket is the union of map-management data (`metadata`, `rooms`,
`summary`) and the image-analysis + map-UI-overlay state written by the mapping
subsystem (`mapping/mapping_services.py`). Every key below is created lazily by
its owning handler via `ensure_map_bucket`, so any reader must tolerate absence.

```
{
  "map_id":                    str                            # string form of the numeric map ID
  "metadata":                  MapMetadata
  "rooms":                     dict[room_id_str, RoomRecord]  # {} until rooms are configured
  "summary":                   RoomSelectionSummary           # rebuilt by build_room_selection_summary
  "segmentation_mode":         str                            # "cv" | "custom"; default "cv" (custom serves the ACTIVE layout)
  "image_segments":            SegmentationResult             # CV auto-detected store (map-bucket level)
  "custom_layouts":            dict[layout_id_str, CustomLayout]   # named custom segmentations; {} until first author/migration
  "active_custom_layout_id":   str | None                     # which layout custom mode serves; None until set
  "custom_segments":           SegmentationResult             # LEGACY single store — migrated lazily into a default layout, never deleted
  "image_segment_adjustments": dict[segment_id_str, AdjustmentRecord]
  "image_variants":            dict[variant_name, VariantRecord]
  "segment_room_links":        dict[segment_id_str, room_id_str]   # 1:1; CV scope only (custom links live per-layout)
  "companion_anchors":         dict[anchor_key, AnchorRecord]      # CV scope only (custom anchors live per-layout)
}
```

`room_id_str` keys inside `"rooms"` are always strings (e.g. `"3"`), even
though `room_id` values on the room dict itself are integers.

The image-analysis and overlay keys are documented in full below; the
dual-store architecture and the read-time derivation (`get_map_segments`,
`segmentation_mode`) are covered in §3a.

#### Segment stores: CV base + named custom layouts

A map carries one CV base plus a **collection** of named custom layouts; the two
sides coexist and persist independently:

- **`image_segments`** — the CV base, and the *only* CV store. A
  `SegmentationResult` produced by the adapter's `MapSegmenter` engine
  (`eufy_cv_v1`), cached on the first `analyze_map_image` and treated as
  immutable from the UI (the card never rewrites it; only
  `image_segment_adjustments` tweak it at read time). Re-running CV re-segments
  and forces a relink (accepted). CV stays at the **map-bucket level** — including
  its `segment_room_links` and `companion_anchors`.
- **`custom_layouts`** — a `dict[layout_id, CustomLayout]`. A map can hold **many**
  named custom segmentations (e.g. a "solar system" image and a "tree" image), not
  one. Each layout owns its own backdrop, authored segments, room links and mascot
  anchors. Layouts sit **alongside** CV (CV is *not* "layout 0").
- **`custom_segments`** *(legacy)* — the old single user-authored store. It is
  migrated **lazily and non-destructively** into a default `"Custom"` layout by
  `_migrate_custom_layouts`: the migration runs the first time any read/write
  handler touches the bucket, copies the store (plus the resolving subset of the
  shared links / the `"dock"` + linked-room anchors) into a new layout, activates
  it, and **keeps** the legacy key in place. It is idempotent — once
  `custom_layouts` exists, migration returns immediately.

`segmentation_mode` is a per-map pointer (`"cv"` | `"custom"`, default `"cv"`).
In `custom` mode it serves the **active** layout (`active_custom_layout_id`); in
`cv` mode it serves the map-bucket CV store. `set_segmentation_mode` **only flips
this flag** (soft-selecting the first layout if custom is chosen with none active)
— it never re-runs the segmenter in either direction, so a `cv → custom → cv`
round-trip preserves every store untouched.

#### The active-scope seam (`_resolve_active_scope`)

`_resolve_active_scope(map_bucket)` (`mapping/mapping_services.py`) returns the
**live** `{segments_store, links, anchors, backdrop_variant}` for the current
mode. The segment-read (`get_map_segments`), room-link, companion-anchor, and
custom-author (`set_custom_segments`) handlers all route through it; segment
*adjustments* (`adjust_map_segment`) apply to the CV `image_segments` store only:

- **CV branch** — the map-bucket keys: `image_segments`, the map-bucket
  `segment_room_links` / `companion_anchors`, no backdrop variant override.
- **custom branch** — the active layout's own keys:
  `custom_segments` / `segment_room_links` / `companion_anchors` /
  `backdrop_variant`.

`get_map_segments` reads through it; `set_segment_room_link` and
`set_companion_anchor` write the resolved (live, mutable) `links` / `anchors`
dict, so their 1:1-enforcement and clamp logic is unchanged but now lands in the
right scope. `set_custom_segments` targets the **active layout**, auto-creating a
default one (`_ensure_default_layout`) when none exists.

#### `CustomLayout` (inside `custom_layouts`)

`data["maps"][v][m]["custom_layouts"][layout_id_str]`. `layout_id` is generated as
`"cl_{YYYYMMDDTHHMMSS}"` (with a same-second collision guard). Each layout is a
fully self-contained custom segmentation.

```
{
  "id":                 str                  # == the dict key
  "name":               str                  # user label; default "Custom"
  "backdrop_variant":   str                  # this layout's image variant; "custom_<id>" for new layouts
  "backdrop_source":    str                  # "custom" (uploaded backdrop) | "live" (rides the live map frame)
  "custom_segments":    SegmentationResult   # authored store (replace-all by set_custom_segments)
  "segment_room_links": dict[segment_id_str, room_id_str]   # 1:1, PER-LAYOUT
  "companion_anchors":  dict[anchor_key, AnchorRecord]       # PER-LAYOUT (incl. the reserved "dock" key)
  "render_mode":        str                  # furnished render: "live"|"art"|"blend" (absent ⇒ "live")
  "home_art":           dict                 # furnished whole-home art: {art_variant, art_placement_transform:{tx,ty,scale,rotation}}
  "rooms":              dict[room_id_str, dict]   # per-room furnished overrides: {art_variant?, art_placement_transform?, viewport?:{cx,cy,zoom}, render_mode?}
  "created_at":         str                  # ISO timestamp
  "updated_at":         str                  # ISO timestamp; bumped on author/upload/rename/furnished write
}
```

Because the links and anchors are **per-layout**, two layouts can each hold a
segment id `"living"` linked to **different** rooms — impossible in the old
single-store model where the links lived once at the map-bucket level. The
`"dock"` mascot-home anchor (see `AnchorRecord` below) is likewise owned by each
custom layout in custom mode, while CV keeps the map-bucket dicts.

The furnished-render members (`render_mode`, `home_art`, `rooms`) are written by
`set_furnished_art_placement` / `set_furnished_render_mode` / `set_room_viewport`
and `upload_map_image(art_scope=…)`, all scoped to the active layout. Their
transforms/viewports are resolution-independent percentage floats (`scale`
clamped `[0.05, 20]`). They are schema-free and minted lazily — `rooms` starts
`{}`; `home_art`/`render_mode` appear on first write. See
[Furnished render](../advanced/08-map-configuration.md#furnished-render).

#### SegmentationResult

The shape held by `image_segments` and by each layout's `custom_segments`. The CV
store is the engine's output verbatim; a layout's custom store is assembled by
`_handle_set_custom_segments` against the active layout's backdrop.

```
{
  "available":   bool
  "engine":      str                # "custom" for the custom store
  "analyzed_at": str                # ISO timestamp
  "image":       dict               # {width, height, variant}
  "segments":    list[Segment]
  "summary":     dict               # {segment_count, ...}
}
```

Each `Segment` carries `segment_id`, `source` (`"custom"` for authored
segments), `polygon_pixel`, `bbox`, `area_pixels`, `area_percent`,
`center_pixel`, `confidence`, and CV-quality metadata. `polygon_pct`, `room_id`,
and applied adjustments are **derived at read time** (§3a), not stored on the
segment.

#### VariantRecord

`data["maps"][v][m]["image_variants"][variant_name]`. Written by
`upload_map_image`; one entry per uploaded backdrop. Variant names are the four
fixed values `"default"`, `"dark"`, `"light"`, `"custom"`, **plus** one
`"custom_<layout_id>"` key per named custom layout (the per-layout backdrop). The
upload `variant` field is no longer a fixed enum but a validator accepting
`default | dark | light | custom | custom_*` (§3b).

```
{
  "variant":     str
  "path":        str                # on-disk PNG path
  "browser_url": str                # /eufy_vacuum/maps/{object_id}/map_{map_id}{suffix}.png
  "width":       int | None         # measured on write; None when PIL is unavailable
  "height":      int | None
}
```

`"dark"`/`"default"`/`"light"` are segmenter inputs. `"custom"` is the
manual-authoring backdrop for the no-CV path: the segmenter never reads it
(`analyze_map_image` only probes dark/default), so a custom-only map is never
auto-segmented, and its recorded `width`/`height` are the pixel space
`set_custom_segments` rasterises against.

#### AdjustmentRecord

`data["maps"][v][m]["image_segment_adjustments"][segment_id_str]`. CV-segment
edits only — written by `adjust_map_segment`, applied to `image_segments` at
read time. Authored custom segments are edited by re-saving, not adjusted.

```
{
  "offset_x":     int               # whole-shape translation, px
  "offset_y":     int
  "edge_left":    int               # per-edge nudge (applied to vertices in the edge band), px
  "edge_right":   int
  "edge_top":     int
  "edge_bottom":  int
  "vertex_moves": list[{ "index": int, "delta_x": int, "delta_y": int }]
}
```

Deltas accumulate across calls; an entry is dropped when every component nets to
zero.

#### segment_room_links

User-assigned segment→room mapping, written by `set_segment_room_link`. Enforced
**1:1** — assigning a room already linked to another segment removes the older
link. Both keys are strings; pass a `null`/empty `room_id` to clear.

`set_segment_room_link` writes through `_resolve_active_scope`, so the dict it
mutates depends on the mode: in `cv` mode it is the map-bucket
`data["maps"][v][m]["segment_room_links"]`; in `custom` mode it is the **active
layout's** `segment_room_links`. The 1:1 rule applies within the resolved scope —
different layouts can therefore link the same segment id to different rooms.

```
dict[segment_id_str, room_id_str]
```

#### AnchorRecord

Per-anchor position for the animated companion sprite, written by
`set_companion_anchor` (or by the card's drag handler). `anchor_key` is a
`room_id` string **or** the reserved literal `"dock"` — the dock anchor is **not**
a room; the mascot homes there when idle/docked (falling back to the resolved
segment centroid until the spot is placed).

Like the links, the anchor dict is resolved through `_resolve_active_scope`: in
`cv` mode it is the map-bucket `data["maps"][v][m]["companion_anchors"]`; in
`custom` mode it is the **active layout's** `companion_anchors`, so each custom
layout owns its own mascot positions including its own `"dock"` spot.

```
{
  "pct_x": float                    # 0–100, % from the map image top-left; clamped + rounded 4dp
  "pct_y": float                    # 0–100
}
```

### MapMetadata

`data["maps"][vacuum_entity_id][map_id_str]["metadata"]`

```
{
  "last_discovery": {
    "active_map_id": str | int | None
    "room_count":    int
  }
  "discovered_rooms": list[dict]   # raw room discovery payloads from the vacuum API
}
```

### RoomSelectionSummary

`data["maps"][vacuum_entity_id][map_id_str]["summary"]`

Rebuilt on every room change by `build_room_selection_summary`.

```
{
  "enabled_count":  int
  "disabled_count": int
}
```

### CapabilityBucket

`data["capabilities"][vacuum_entity_id]`

Populated from the adapter config. Read by `get_vacuum_capabilities()`.

```
{
  "supports_mop_features":  bool
  "supports_water_control": bool
  "supports_path_control":  bool
  "supports_edge_mopping":  bool
  "supports_passes":        bool
  "entities":               dict[role_key, entity_id_str]
}
```

Capability keys gate which payload fields are included per room (see §4).
`entities` maps adapter role keys (e.g. `"task_status"`, `"robot_position_x"`)
to live HA entity IDs.

---

## 2. Room Record

### 2a. Stored shape (`RoomRecord`)

TypedDict defined in `models/models.py`. Stored as a plain `dict` in
`data["maps"][vacuum_entity_id][map_id_str]["rooms"][room_id_str]`.

| Field | Type | Notes |
|---|---|---|
| `room_id` | `int` | Numeric ID from the vacuum API. Parent dict key is `str(room_id)`. |
| `map_id` | `str` | String form of the map ID. |
| `name` | `str` | Display name. |
| `slug` | `str \| None` | URL-safe identifier. May be `None` if not yet assigned. |
| `enabled` | `bool` | Whether the room is included in the next job queue. |
| `order` | `int` | Zero-based sort position within the map. |
| `is_configured` | `bool` | Gating flag: only rooms with `True` become HA entities. Backfilled `True` for pre-existing rooms; new rooms enter `False` and advance through the setup wizard. |
| `configured_at` | `str \| None` | ISO timestamp the room was approved/backfilled — stamped (`setdefault`) when `is_configured` first flips `True`. Defined on `RoomConfig`; like `is_transition`, not in the `RoomRecord` TypedDict. |
| `profile_name` | `str \| None` | Active preset name; default `"vacuum_quick"`. |
| `floor_type` | `str` | One of: `"hardwood"`, `"laminate"`, `"tile"`, `"marble"`, `"carpet_low_pile"`, `"carpet_high_pile"`. Carpet pile is encoded in the value — use `floor_type.startswith("carpet")` rather than a separate flag. |
| `clean_mode` | `str` | `"vacuum"`, `"mop"`, or `"vacuum_mop"`. |
| `fan_speed` | `str` | e.g. `"Max"`, `"Boost"`, `"Standard"`, `"Quiet"`. |
| `water_level` | `str` | `"Off"`, `"Low"`, `"Medium"`, `"High"`. |
| `clean_intensity` | `str` | `"Standard"`, `"Intense"`, etc. |
| `clean_passes` | `int` | Number of cleaning passes; minimum 1. |
| `edge_mopping` | `bool` | Whether edge mopping is active. |
| `path_type` | `str \| None` | `"wide"`, `"narrow"`, or `None`. |
| `is_dock_room` | `bool` | Marks the room that contains the dock. Backfilled `False`. |
| `is_transition` | `bool` | Internal / legacy; seeded `False` by backfill. Not in TypedDict. |
| `grants_access_to` | `list[str]` | Room slugs this room grants traversal access to. Backfilled `[]`. |
| `rules` | `list[RuleDefinition]` | Backfilled `[]`. |

**Schema migration** in `async_initialize`: `path_type`, `is_dock_room`,
`is_transition`, `grants_access_to`, `rules`, `floor_type`, `profile_name`, and
`is_configured` are backfilled with `setdefault`. The old `floor_type="carpet"` +
`carpet_type` sub-field is collapsed into `"carpet_low_pile"` / `"carpet_high_pile"`
in place. The derived `carpet` boolean field is removed.

### 2b. `is_configured` gate

`sort_room_items()` in `entity_helpers.py` filters to `is_configured=True`
before returning the room list used to create HA entities. Rooms that fail
this gate exist in storage but have no corresponding switch, number, or sensor
entities. The setup wizard advances new rooms to `True` after name
confirmation.

### 2c. As queue summary item (inside `queue_rooms` list)

Built by `build_queue_from_managed_rooms` in `queue/queue_engine.py`.

```
{
  "room_id":      int
  "name":         str | None
  "slug":         str | None
  "order":        int
  "profile_name": str    # default "vacuum_quick"
}
```

### `RuleDefinition` (nested in `rules`)

```
{
  "id":        str
  "label":     str | None
  "entity_id": str
  "kind":      str   # "blocker" | "modifier"
  "operator":  str   # "equals" | "not_equals" | "in" | "not_in"
                     # | "gt" | "gte" | "lt" | "lte"
                     # | "is_on" | "is_off" | "exists" | "missing"
  "value":     Any   # RHS of comparison; None for boolean operators
  "enabled":   bool
  "effect":    RuleEffect
}
```

### `RuleEffect` (nested in `RuleDefinition`)

```
{
  "action":  str          # "exclude" | "mutate"
  "reason":  str | None
  "changes": dict         # partial RoomRecord fields; empty for blockers
}
```

---

## 3. Map Object

A map is represented by its `MapBucket` in storage (§1). There is no separate
top-level map dataclass.

### As returned by `get_vacuum_maps_summary`

```
{
  "vacuum_entity_id": str
  "map_count":        int
  "maps":             list[MapSummaryEntry]
}
```

Each `MapSummaryEntry`:

```
{
  "map_id":               str
  "room_count":           int
  "enabled_room_count":   int
  "disabled_room_count":  int
  "last_discovery": {
    "active_map_id": str | int | None
    "room_count":    int
  }
}
```

### `MapConfig` dataclass (`models/models.py`)

In-memory normalized form; not persisted directly.

```
MapConfig:
  map_id:  str
  name:    str | None
  rooms:   dict[int, RoomConfig]   # keyed by integer room_id
```

`as_dict()` serializes rooms as `dict[str(room_id), RoomConfig.as_dict()]`.

### 3a. Read-time segment view (`get_map_segments`)

Returned by `_handle_get_map_segments` (`mapping/mapping_services.py`). This is
the card-facing union of the **active scope** (resolved by `_resolve_active_scope`)
plus the layout catalog — **derived, never stored**. Reading is pure: it serves
whichever store `segmentation_mode` selects — in `custom` mode the **active
layout's** segments / links / anchors / backdrop, else the map-bucket CV store —
so the segmenter is never invoked and every store survives a mode or layout flip
untouched. The lazy `_migrate_custom_layouts` runs first.

```
{
  "vacuum_entity_id":        str
  "map_id":                  str
  "segmentation_mode":       str                 # the active store: "cv" | "custom"
  "active_custom_layout_id": str | None          # which layout custom mode is serving
  "custom_layouts":          list[CustomLayoutSummary]   # the whole catalog (summary; see below)
  "segment_room_links":      dict[segment_id_str, room_id_str]   # the ACTIVE scope's links, verbatim
  "available":               bool                 # from the served store
  "analyzed_at":             str | None
  "image":                   dict | None          # served store's {width, height, variant}
  "image_variants":          dict[name, VariantRecord]   # all variants, verbatim
  "summary":                 dict                 # store summary + {segment_count, adjusted_count}
  "segments":                list[Segment]        # see below — enriched per read
  "adjustments":             dict[segment_id_str, AdjustmentRecord]
  "companion_anchors":       dict[anchor_key, AnchorRecord]   # the ACTIVE scope's anchors
}
```

Each `CustomLayoutSummary` in `custom_layouts` is the layout shorn of its heavy
stores — `{id, name, backdrop_variant, backdrop_source, segment_count, created_at, updated_at, render_mode, home_art, rooms}`
(`segment_count` is `len(custom_segments.segments)`; the last three carry the
per-layout **furnished-render** state so the card renders the furnished panel
without a second fetch). The card renders one picker chip per entry.

Each served `Segment` is the stored segment enriched at read time:

- **`polygon_pct`** — `polygon_pixel` scaled to 0–100 % against the served
  image's `width`/`height`. The served image is the active scope's
  `backdrop_variant` (a layout's `"custom_<id>"` in custom mode) with a fallback
  chain of `dark` → `default` → `light`.
- **`room_id`** — injected as a string when the active scope's
  `segment_room_links` holds a link for the segment (otherwise absent).
- **adjustments applied** — for CV segments, `image_segment_adjustments` are
  folded into `polygon_pixel`/`bbox`/`center_pixel` before scaling, and the
  segment's `issues` gains `translated_manual` / `edge_adjusted_manual` /
  `vertex_adjusted_manual` markers.

Note: the per-segment `room_id` is the served representation of the links; the
response **also** carries the active scope's full `segment_room_links` dict at the
top level (so the card can refresh its in-memory link state without a second
fetch).

### 3b. Map image variants (`upload_map_image`)

`upload_map_image` writes one backdrop PNG and records a `VariantRecord` (§1)
under `image_variants[variant]`. The `variant` field is validated (not a fixed
enum) by `_image_variant`, which accepts the four fixed values **plus** any
`custom_*` per-layout key:

| Variant | Role |
|---|---|
| `default` | Segmenter input (no filename suffix). |
| `dark` | Segmenter **primary** — clearest room colours. |
| `light` | Segmenter **assist** — wall detection. |
| `custom` | Manual-authoring backdrop for the legacy/default no-CV path. |
| `custom_<layout_id>` | Per-layout authoring backdrop (one per named custom layout). |

**Per-layout upload:** `upload_map_image` takes an optional `layout_id`. When
present, the server **forces** the variant to `custom_<layout_id>` (ignoring any
`variant` field), validates the layout exists (returns
`{"saved": False, "reason": "layout_not_found"}` otherwise), writes the PNG, and
repoints that layout's `backdrop_variant` to the new variant (bumping its
`updated_at`).

The active custom backdrop is the **only** image used to rasterise authored
primitives: its recorded `width`/`height` are the pixel space `set_custom_segments`
writes against (resolved via the active layout's `backdrop_variant`, defaulting to
`"custom"`), and a `no_custom_backdrop` failure is returned if it's absent. The
segmenter never reads `custom` / `custom_*` variants (`analyze_map_image` only
probes `dark`/`default`), so a map that only has a custom backdrop is never
auto-segmented.

---

## 4. Queue Payload

`build_room_clean_payload` in `queue/queue_engine.py` is the shared resolver
for this object — the per-brand payload *shape* is produced by the dispatch
engine. The start path obtains `payload_state` as `phases[0]` from
`get_dispatch_engine(...).build_phases(...)` (via `run_plan._build_dispatch_phases`);
atomic engines return a single phase that is byte-identical to the direct
`build_room_clean_payload` result. This is the full object passed to the
vacuum's room-clean API.

### Return shape

```
{
  "vacuum_entity_id": str
  "map_id":           str
  "payload": {
    "map_id": int | str     # int when map_id.isdigit(), else str
    "rooms":  list[PayloadRoom]
  }
  "resolved_rooms": list[ResolvedRoom]
  "room_count":     int
}
```

### `PayloadRoom` (inside `payload["rooms"]`)

Capability-gated fields are conditionally present.

| Field | Type | Condition |
|---|---|---|
| `id` | `int` | always |
| `clean_times` | `int` | always |
| `fan_speed` | `str` | always |
| `clean_mode` | `str` | always |
| `clean_intensity` | `str` | always |
| `water_level` | `str` | only if `supports_water_control` AND `clean_mode` in `{"mop", "vacuum_mop"}` |
| `edge_mopping` | `bool` | only if `supports_edge_mopping` AND `clean_mode` in `{"mop", "vacuum_mop"}` |
| `path_type` | `str` | only if `supports_path_control` |

### `ResolvedRoom`

Enriched room metadata after profile resolution and capability gating. Used
for display, logging, and learning.

```
{
  "room_id":               int
  "name":                  str | None
  "slug":                  str | None
  "selected_profile_name": str
  "resolved_profile_name": str
  "clean_mode":            str
  "fan_speed":             str
  "water_level":           str
  "clean_intensity":       str
  "path_type":             str
  "clean_passes":          int
  "edge_mopping":          bool
  "carpet":                bool    # True when floor_type.startswith("carpet")
  "capability_gated": {
    "supports_mop_features":  bool
    "supports_water_control": bool
    "supports_path_control":  bool
    "supports_edge_mopping":  bool
    "supports_passes":        bool
  }
}
```

### Queue state (from `build_queue_from_managed_rooms`)

```
{
  "vacuum_entity_id": str
  "map_id":           str
  "room_count":       int
  "queue_room_ids":   list[int]
  "queue_rooms":      list[QueueRoomSummary]   # see §2c
}
```

### `PayloadItem` TypedDict (`queue_engine.py`)

Canonical per-room payload shape post capability-gating. All fields always present.

```
{
  "stable_key":      str    # "{vacuum_entity_id}:{map_id}:{room_id}"
  "room_id":         int
  "map_id":          str
  "clean_mode":      str
  "fan_speed":       str
  "water_level":     str
  "clean_intensity": str
  "clean_passes":    int
  "edge_mopping":    bool
  "path_type":       str
}
```

---

## 5. Active Job State

Stored at `data["active_jobs"][vacuum_entity_id][map_id_str]`.

Owned and normalized by `ActiveJobTracker` (`jobs/active_job.py`).
`get_active_job()` always returns a normalized copy — it never returns a raw
reference. All mutations write back through
`data["active_jobs"][vacuum_entity_id][map_id_str]`.

### Default / idle shape

Returned by `_default_active_job_state` and by `get_active_job` when no record
exists for the vacuum/map pair.

```
{
  "vacuum_entity_id":                      str
  "map_id":                                str
  "queue_room_ids":                        list[int]       # []
  "queue_stable_keys":                     list[str]       # []
  "queue_rooms":                           list            # []
  "payload":                               dict            # {"map_id": ..., "rooms": []}
  "resolved_rooms":                        list            # []
  "room_count":                            int             # 0
  "status":                                str             # "idle"
  "paused_at":                             None
  "paused_duration_seconds":               int             # 0
  "completed_room_ids":                    list[int]       # []
  "completed_rooms":                       list            # []
  "current_room_id":                       None
  "current_room_started_at":               None
  "current_room_paused_seconds":           int             # 0
  "observed_mid_job_recharge":             bool            # False
  "observed_mid_job_recharge_started_at":  None
  "observed_mid_job_recharge_count":       int             # 0
  "recharge_seconds_accumulated":          int             # 0
  "pending_mid_job_recharge_return":       bool            # False
  "pending_mid_job_recharge_return_at":    None
  "observed_mop_wash_count":               int             # 0
  "observed_mop_wash_last_at":             None
  "observed_mop_wash_cycles":              list            # []  max 50 entries
  "state_transitions":                     list            # []  max 12 entries
  "counter_samples":                       list            # []  [{t, cleaning_time, cleaning_area, battery}] — per-room segmentation input
  "settings_samples":                      list            # []  external runs only: deduped [{t, settings:{...}}] setting-flip timeline
  "water_estimate":                        None
  "path_block_action":                     str             # "event_only"
  "pause_timeout_minutes":                 int             # 0
  "has_observed_active_lifecycle":         bool            # False
}
```

### External-run capture (`status == "external"`)

App-started runs the integration did **not** dispatch reuse this slot with
`status="external"` and no queue/payload — counters buffer into `counter_samples`
and the per-room setting selects into `settings_samples`. On finalize the slot is
segmented into a **pending review record** (schema v2 — see §5a) under
`learning/<slug>/external_jobs/` (peer to `jobs/`); a confirmed run graduates to a
normal completed-job record (§9b) tagged `origin: "external"`. See
[28-external-run-ingestion](28-external-run-ingestion.md).

### 5a. Pending External Review Record (schema v2)

Built by `build_pending_record` in `learning/external_ingest.py` on external-run
finalize. Persisted to `learning/{vacuum_slug}/external_jobs/job_{...}.json`.
`PENDING_SCHEMA_VERSION = 2`. The record embeds the **raw samples** so the run can
be re-segmented entirely server-side (`resegment_pending_record`) when the user
sets a room count or toggles a boundary in the review card — a client-side regroup
could not reproduce the exact area attribution (a wash plateau forward-reads its
lagged area; every other boundary stays same-instant).

```
{
  "schema_version":      int           # 2
  "status":              str           # "pending"
  "origin":              str           # "external"
  "detection_ts":        str | None    # when the external run was first detected
  "map_id":              str
  "segment_count":       int           # len(segments) after the trailing-drop
  "suggested_room_count": int          # default room count = the confident-only view
  "gap_transit_s":       float         # the transit-band threshold used (Eufy: 60.0)
  "candidates":          list[BoundaryCandidate]   # the FULL boundary pool (no discards)
  "active_boundaries":   list[int]     # candidate ids that started a kept segment
  "counter_samples":     list          # [{t, cleaning_time, cleaning_area, battery}] — stripped before serving
  "settings_samples":    list          # [{t, settings:{...}}] — stripped before serving
  "segments":            list[PendingSegment]
}
```

`segment_count == suggested_room_count` on the default (confident-only) view —
uncertain / transit / weak cuts ship in `candidates` with `confident: false` and
surface as inactive "split here" candidates the user can activate.

#### `BoundaryCandidate` (inside `candidates`)

The job-segmenter engine's `JobBoundaryCandidate` contract (§5c), serialized
as-is. Emitted by `find_candidates` (`counter_segmentation.py`, behind the
`eufy_counter_v1` engine); `confident` is upgraded in place by
`_mark_candidate_confidence` where a per-room settings flip corroborates the cut.

```
{
  "id":            int     # == position; stable handle for the frozen samples (card toggles by id)
  "position":      int     # increment-tick index of the blip
  "gap_s":         float   # seconds between cleaning_time ticks at the blip
  "area_after_m2": float   # new floor covered AFTER the blip (read forward to the next blip)
  "kind":          str     # "wash_plateau" | "transit" | "area_jump" | "weak"
  "strength":      float   # count-ranking score (kind band + area + gap fraction)
  "confident":    bool    # geometric base (wash_plateau) OR a corroborating settings flip
  "t":             str     # ISO timestamp of the blip tick
}
```

**Boundary kinds** (`_classify`): `wash_plateau` (gap > `gap_plateau_s` = 90 s —
a mop wash / long transit; always confident), `transit` (`gap_transit_s` 60 s <
gap ≤ 90 s AND area stays flat — a real inter-room hop the legacy filter dropped),
`area_jump` (`cleaning_area` rose ≥ `area_jump_m2` = 2.0 after the blip — new floor),
`weak` (a short delayed step with flat area — most likely a multi-pass turn).

#### `PendingSegment` (inside `segments`)

The engine's raw `JobSegment` (§5c) **after** the ingest enrichment
(`_enrich_segments`) — it renames/derives fields (`area_delta_m2` → `area_m2`,
adds `order`/`pass_count`/`settings`/`confident_boundary`/`shortlist`, drops the
raw counter fields), so its shape differs from the cross-engine contract. Built by
`build_segments` then enriched. One per kept room bout, re-indexed `0..N-1` over the
KEPT segments after trailing sub-room stretches (area < `_MIN_ROOM_AREA_M2` =
0.5 m²) are dropped.

```
{
  "order":               int          # 0-based, contiguous over kept segments
  "boundary_id":         int | None   # candidate id that started this segment; None for the first
  "t_start":             str          # ISO timestamp (UTC)
  "t_end":               str          # ISO timestamp (UTC)
  "area_m2":             float        # new floor covered in this segment
  "time_wall_s":         int          # wall-clock seconds in the segment
  "time_active_s":       int          # cleaning_time seconds (active clock) in the segment
  "pass_count":          int          # estimated passes from the area-plateau pattern
  "settings":            dict         # per-room selects in effect (clean_mode, fan_speed, ...)
  "boundary":            str          # the boundary kind that opened it ("job_start" for order 0)
  "confident_boundary":  bool | None  # None for order 0; else whether boundary_id is a confident cut
  "shortlist":           list[ShortlistEntry]   # top-3 candidate rooms, settings-first ranked
}
```

#### `ShortlistEntry` (inside `segments[].shortlist`)

The map-scoped, carpet-filtered (for mopped segments) top-3 room guesses, ranked
SETTINGS-first (area distance is only a tiebreak — `cleaning_area` is
path/pass-cumulative, a poor identity signal).

```
{
  "room_id":         int
  "slug":            str
  "name":            str | None
  "is_carpet":       bool
  "learned_area_m2": float | None   # avg_area_m2 from the room's learned band; None when cold
  "settings_score":  float          # weighted settings-match (mode 4 / passes 3 / intensity 2 / fan 1 / water 1)
  "score":           float          # area-distance tiebreak (negative abs delta; cold rooms rank last)
}
```

#### Served record (what the card receives)

`handle_get_external_pending_runs` (`learning/services.py`) loads each record,
attaches a `rooms` list + `pending_job_id` (filename stem), sets
`resegmentable = bool(counter_samples)`, then calls `strip_samples` to drop the
two embedded sample lists. So the served record is the v2 shape **minus**
`counter_samples` / `settings_samples` **plus**:

```
  "resegmentable":  bool                 # True when the run can be re-segmented (v2 only; v1 = False)
  "pending_job_id": str                  # filename stem, for the confirm/resegment services
  "rooms":          list[{room_id, slug, name}]   # the map's room list for the assignment UI
```

`resegment_external_run` (`core/manager.py`, via the `resegment_external_run`
service) loads the on-disk record **with** samples, re-runs the segmentation at a
new room count (`expected_rooms`) XOR boundary set (`active_boundaries`) XOR the
confident-only default, rewrites the file in place, and returns the freshly
`strip_samples`'d record plus a `meta` block (`mode` /
`requested` / `available` / `capped` / `capped_at`). v1 records (no samples) are
`not_resegmentable` and degrade the card to legacy merge-only.

### Fields written at job-start

```
  "job_id":                                str    # "job_{YYYY-MM-DDTHH-MM-SS}"
  "started_at":                            str    # ISO timestamp (UTC)
  "battery_start":                         int
  "job_metadata": {
    "map_id":      str
    "room_count":  int
    "room_slugs":  list[str]
  }
  "trace_run_id":                          str | None
```

### Sequenced job model (optional keys)

Present only when the run has more than one phase (a `sequenced` dispatch
engine). Set by `build_active_job_state` when `phases` is passed, and
mutated by `advance_active_job_phase` at each completion hook. Absent for
atomic (single-phase) jobs.

```
  "phases":              list   # ordered per-phase payload envelopes
  "current_phase_index": int    # 0-based; incremented on phase advance
  "phase_count":         int    # len(phases)
```

Two further keys are written to the active job to drive the strict-order
watchdog. They are **internal/transient** runtime control flags — not part of the
persisted job contract — so a reader should never depend on their presence:

The strict-order watchdog itself lives in `jobs/phase_runner.py` (`PhaseRunner`);
`core/manager.py` keeps only the `maybe_advance_phase` delegator and the
initial-phase spawn (`active_job["_phase_dispatch_pending"] = True` then
`phase_runner._run_advanced_phase(...)`).

- `_phase_dispatch_pending` (`bool`) — completion suppression. Set `True` when a
  phase is dispatched — the sequenced/initial start in `core/manager.py` (just
  before spawning `_run_advanced_phase`) and on each phase advance — and cleared
  `False` by `PhaseRunner._clear_phase_dispatch_pending` once the per-phase
  watchdog (`_await_phase_started`) confirms the device actually started the
  dispatched phase's target room. While set, the completion gate refuses to
  finalize (`listeners/lifecycle.py`), so the just-finished room's
  docked/charging completion signal cannot finalize the next phase before it
  begins.
- `_cancel_in_flight` (`bool`) — set `True` (alongside clearing
  `_phase_dispatch_pending`) at the top of `async_cancel` in
  `jobs/active_job.py` to halt the watchdog and block re-dispatch during the
  return-to-base window. The `PhaseRunner` watchdog reads it and bails (in
  `_run_advanced_phase` and `_await_phase_started`) so a cancel cannot be undone
  by a re-sent clean.

### Fields written during the run (by listener / sensor callbacks)

```
  "ended_at":                              float | None    # unix timestamp
  "state_transitions":                     list[StateTransition]
  "cleaning_time_seconds":                 int | None      # from HA sensor; record_active_job_sensor_value
  "cleaning_area_m2":                      float | None    # from HA sensor
  "water_estimate":                        dict | None
```

### Fields written at finalization

```
  "status":           str             # "completed"
  "finalized":        bool            # True
  "finalized_at":     str | None      # ISO timestamp from completed job record
  "has_observed_active_lifecycle": bool  # False (reset)
  "finalize_summary": {
    "job_id":             str
    "job_path":           str
    "used_for_learning":  bool
    "sanity_passed":      bool
    "sanity_flags":       list[str]
    "learning_blockers":  list[str]
    "status":             str   # outcome status from completed job
  }
```

### `StateTransition` (inside `state_transitions`, max 12 kept)

```
{
  "entity_id":  str
  "from_state": str
  "to_state":   str
  "changed_at": str    # ISO timestamp
}
```

### `CompletedRoomEntry` (inside `completed_rooms`)

One entry appended per room confirmed cleaned. Capped to
`max(queue_room_count + 1, 20)`.

```
{
  "room_id":                int
  "slug":                   None
  "room_name":              str | None
  "completed_at":           str     # ISO timestamp
  "source":                 str     # "event" | "timing_rollover" | "bounds_exit_early"
  "actual_duration_minutes": float  # present if duration was computed
  "confidence":             float   # present if confidence score was available
}
```

### `valid_status` values

| Status | Meaning |
|---|---|
| `"idle"` | No active job |
| `"started"` | Job running |
| `"paused"` | Job paused by service call |
| `"completed"` | Job finalized |

### 5b. Live Progress Snapshot

Returned by `get_job_progress_snapshot` in `core/manager.py` — the canonical
card-facing view of a running job. **Derived, never stored**: rebuilt on every call
from the active-job state plus a fresh learning estimate (the `timeline` here is the
estimator's `room_timeline`, §10, re-enriched per room). Selected keys (recharge /
stall / lifecycle fields omitted for brevity):

```
{
  "vacuum_entity_id":      str
  "map_id":                str
  "job_id":                str | None
  "status":                str           # active-job status
  "terminal":              bool          # status NOT in {started, paused}
  "current_room_id":       int | None    # next unfinished QUEUED room
  "position_room_id":      int | None    # what the icon tracks; may be a transition room
  "awaiting_bounds_exit":  bool
  "completed_room_ids":    list[int]
  "remaining_room_ids":    list[int]     # excludes current + skipped
  "skipped_room_ids":      list[int]     # conservative; ~empty live for Eufy (see below)
  "running_long":          bool          # soft anomaly tier below the 2x stall
  "running_long_room_id":  int | None
  "running_long_ratio":    float | None  # elapsed / threshold (running_long_ratio..stall band)
  "stall_detected":        bool          # hard anomaly (>= stall_ratio x threshold)
  "stall_ratio":           float | None
  "progress_percent":      int
  "timeline":              list[TimelineRoom]   # alias: "room_timeline"
  ...
}
```

**`running_long`** is the soft anomaly band: the current room has run
`running_long_ratio` (Eufy default 1.5) up to `stall_ratio` (2.0) × its timing
threshold with **no pending counter transition** — genuinely stuck, not a missed
roll. Disjoint from `stall_detected` by band. Both ratios come from the adapter's
`anomaly` block (falling back to the Eufy constants).

**`skipped_room_ids`** is CONSERVATIVE — a queued room strictly before
`current_room_id` in queue order that is not completed. Eufy's sequential counter
rollover keeps `completed_room_ids` a queue prefix, so this is ~empty live for Eufy
(the reliable "missed rooms" signal is the post-run incomplete-run log, §14); it
fires only on a non-sequential advance (position-reliable brands). New skips fire
`EVENT_ROOM_SKIPPED` (`const.py`) once per room per job.

The stall / running_long / skipped detection — and the deduped one-shot
`EVENT_STALL_DETECTED` / `EVENT_ROOM_SKIPPED` emission — lives in
`ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py`), not in the
snapshot composer; `get_job_progress_snapshot` calls it and just reads back the
returned anomaly fields (it owns the active-job dict and the per-job dedup state
the once-per-room emission keys on). The output shape above is unchanged.

#### `TimelineRoom` (inside `timeline`)

Each `RoomTimelineEntry` (§10) re-enriched for the live job with run-state flags:

```
  "completed":     bool
  "current":       bool
  "skipped":       bool    # room_id in skipped_room_ids
  "remaining":     bool    # not completed, not current, not skipped
  "running_long":  bool    # running_long AND this is the current room
  "progress_percent":  int
  "elapsed_minutes":   float
  "remaining_minutes": float
```

### 5c. Job-Segmentation Engine Contract

The **counter/run** segmenter turns a run's `counter_samples` stream (§5) into
ordered per-room boundaries and segments. It is pluggable behind the
`JobSegmenter` Protocol in `learning/job_segmenter_engines.py` (mirroring the
dispatch-engine seam), selected via the adapter's `job_segmenter.engine`. The
Eufy engine (`eufy_counter_v1`, `EufyCounterSegmenter`) delegates verbatim to the
`counter_segmentation.py` primitives. This is a **distinct subsystem** from the
*map* segmenter (`mapping/segmenter_engines.py`, `eufy_cv_v1`), which segments the
map image — do not conflate them.

The two TypedDicts below are the **canonical cross-engine contract**: the exact
field union every engine's `find_candidates` / `build_segments` returns (verified
field-identical to the dicts produced in `counter_segmentation.py`). They are the
shape the three consumers read unchanged — live rollover
(`jobs/active_job.py` `_live_boundary_count`), external-run ingest
(`learning/external_ingest.py`), and learned history (`learning/history_store.py`
`_build_transit_blocks`). A future brand supplies its own engine that produces the
same two shapes, and no consumer changes.

#### `JobBoundaryCandidate`

One detected room boundary in a run, **before** selection (`find_candidates`
returns all of them, no discards, in cleaning order). The framework selector
`counter_segmentation.select_active` ranks/filters on `id` / `kind` / `strength` /
`confident` only — that subset is the brand-agnostic part of the contract. This is
the raw shape serialized as `BoundaryCandidate` in the pending external record
(§5a).

```
{
  "id":            int     # == position; stable handle for the frozen samples
  "position":      int     # increment-tick index of the blip
  "gap_s":         float   # seconds between cleaning_time ticks at the blip
  "area_after_m2": float   # new floor covered AFTER the blip (read forward to the next blip)
  "kind":          str     # "wash_plateau" | "transit" | "area_jump" | "weak"
  "strength":      float   # count-ranking score (kind band + area + gap fraction)
  "confident":     bool    # geometric base (wash_plateau); ingest may upgrade it
  "t":             str     # ISO timestamp (UTC) of the blip tick
}
```

#### `JobSegment`

One ordered per-room cleaning bout, the **raw** output of `build_segments` (and of
the `segment_legacy` one-shot composition). The external-ingest `PendingSegment`
(§5a) is this shape **after** the `_enrich_segments` pass (which renames
`area_delta_m2` → `area_m2`, re-indexes `index` → `order`, and adds
`pass_count` / `settings` / `confident_boundary` / `shortlist`).

```
{
  "index":          int          # 0-based position in cleaning order
  "boundary_id":    int | None    # active candidate id that started it; None for the first
  "t_start":        str           # ISO timestamp (UTC)
  "t_end":          str           # ISO timestamp (UTC)
  "ct_start":       float         # cleaning_time at segment start
  "ct_end":         float         # cleaning_time at segment end
  "area_start_m2":  float         # cleaning_area at segment start
  "area_end_m2":    float         # cleaning_area at segment end (forward-read across a wash_plateau)
  "area_delta_m2":  float         # new floor covered in this segment (floored at 0; never negative)
  "time_active_s":  float         # cleaning_time seconds (active clock) in the segment
  "time_wall_s":    float         # wall-clock seconds in the segment
  "gap_before_s":   float         # idle seconds before this segment opened
  "battery_delta":  float | None  # battery drop across the segment; None when battery samples are absent
  "boundary":       str           # boundary kind that opened it ("job_start" for index 0)
  "increment_count": int          # cleaning_time ticks rolled into this segment
}
```

**Tuning** is the engine's `DEFAULT_TUNING` merged under the adapter
`job_segmenter.tuning` block — the five gap/area/cadence thresholds
(`gap_delayed_s` 35, `gap_transit_s` 60, `gap_plateau_s` 90, `area_jump_m2` 2.0,
`cadence_s` 30). The Eufy engine defines them *by reference* to the
`counter_segmentation` module constants, so the Eufy path can never drift from the
primitives.

---

## 6. Profiles

### 6a. Room profiles

Custom room profiles are stored at `data["profiles"]["room_profiles"]`.
Built-in profiles (e.g. `"vacuum_quick"`, `"vacuum_mop_quick"`) are compiled at
runtime from `profiles/room_profiles.py` and never written to storage — only
user-created profiles appear in storage.

`data["profiles"]["room_profiles"][profile_name]`

```
{
  "label":          str
  "clean_mode":     str    # "vacuum" | "mop" | "vacuum_mop"
  "fan_speed":      str
  "water_level":    str
  "clean_intensity": str
  "clean_passes":   int
  "edge_mopping":   bool
  "path_type":      str | None
}
```

Profile names that match built-in IDs are protected and cannot be overwritten
or deleted via service calls (`_PROTECTED_ROOM_PROFILE_NAMES` frozenset in
`profiles/manager.py`).

**Profile resolution order:** `room["profile_name"]` → stored custom profiles
→ built-in defaults. `profile_name = "custom"` means the room's direct fields
don't match any named preset; the room fields are authoritative.

### 6b. Run profiles

Saved multi-room job configurations. Stored at
`data["run_profiles"][vacuum_entity_id][map_id_str][profile_id]`.

`profile_id` is generated as `"rp_{YYYYMMDDTHHMMSS}"`.

```
{
  "id":              str    # same as the dict key
  "name":            str    # user-facing label
  "rooms":           list[RunProfileRoomSnapshot]
  "expose_as_button": bool  # True → creates a HA button entity
  "created_at":      str    # ISO timestamp
  "updated_at":      str    # ISO timestamp
}
```

### `RunProfileRoomSnapshot` (inside `rooms`)

```
{
  "room_id":        int
  "name":           str
  "profile_name":   str    # room profile active at save time
  "clean_mode":     str
  "fan_speed":      str
  "water_level":    str
  "clean_intensity": str
  "clean_passes":   int
  "edge_mopping":   bool
  "order":          int
}
```

---

## 7. Room History

`data["room_history"][vacuum_entity_id][map_id_str][room_id_str]`

Written by `_ingest_completed_job_into_room_history` and
`_ingest_jobs_index_entry_into_room_history` on job finalization. Also
pre-populated from learning store files via `async_preload_room_history_cache`
on sensor platform startup.

```
{
  "last_cleaned_at":  str | None    # ISO timestamp of last job that included this room
  "last_vacuumed_at": str | None    # ISO timestamp of last vacuum-mode run
  "last_mopped_at":   str | None    # ISO timestamp of last mop-mode run
  "last_job_mode":    str | None    # clean_mode of the most recent completed run
}
```

Both `map_id_str` and `room_id_str` keys are always strings. Missing keys
evaluate to `None` — never `KeyError` when using `.get()` with a default.

These fields are surfaced on every room entity's `extra_state_attributes` so
the Eufy Room Card can render "last cleaned N days ago" without a service
round-trip.

---

## 8. Room Rule Status

`data["room_rule_status"][vacuum_entity_id][map_id_str][room_id_str]`

Written by `_update_room_rule_status_snapshot` on every preflight plan
evaluation (`last_evaluation_scope == "start_preflight"`). One entry per room,
per map, per vacuum. The shape is the `LiveRuleState` TypedDict (`models/models.py`,
`total=False`) — every field is `last_*`-prefixed.

```
{
  "room_id":                    int          # numeric room ID
  "map_id":                     str          # string form of the map ID
  "room_name":                  str          # display name (falls back to "Room {id}")
  "last_evaluated_at":          str          # ISO timestamp of this evaluation
  "last_result":                str          # see values below
  "last_selected":              bool         # room was in the selected/queued set
  "last_included":              bool         # room survived to the dispatched set
  "last_block_reason":          str | None   # human-readable reason a blocker fired
  "last_block_source":          str | None   # "direct_rule" | "access_graph"
  "last_blocked_by_room_id":    str | None   # upstream room that blocked this one (access graph)
  "last_blocked_by_room_name":  str | None
  "last_triggered_rule_ids":    list[str]    # sorted IDs of the blocker/modifier rules that fired
  "last_modifier_changes":      dict         # applied modifier effects (partial RoomRecord fields); {} when none
  "last_requires_confirmation": bool         # the preflight flagged a confirm-required gate
  "last_preflight_reason":      str          # preflight reason string; "ready" when clear
  "last_warning_codes":         list         # preflight warning codes
  "last_evaluation_scope":      str          # always "start_preflight"
}
```

`last_warning_codes` and `last_evaluation_scope` are written by the snapshot but
are not declared on the `LiveRuleState` TypedDict; since it is `total=False`,
readers must tolerate any subset of these keys.

### `last_result` values

| Value | Meaning |
|---|---|
| `"not_selected"` | Room was not in the selected/queued set for this run |
| `"allowed"` | Room was selected; no blocker or modifier fired (the no-change default) |
| `"blocked"` | At least one blocker rule fired; room excluded from job |
| `"modified"` | At least one modifier rule fired; room settings changed |
| `"blocked_and_modified"` | A blocker AND a modifier both fired for this room |

Both `map_id_str` and `room_id_str` keys are always strings. The sensor
`EufyVacuumRoomRuleStatusSensor` reads via
`manager.get_room_rule_status(vacuum_entity_id, map_id, room_id)`.

---

## 9. Learning Record (Completed Job)

Built by `LearningHistoryStore.build_completed_job_payload` in
`learning/history_store.py`. Persisted to
`eufy_vacuum/learning/{vacuum_slug}/jobs/{job_id}.json`.

For a job to be used for learning (`is_learning_job` returns True), it must
have `record_type == "completed_job"`, `outcome.status == "completed"`, and
`outcome.used_for_learning == True`.

### Top-level shape

```
{
  "schema_version": int           # always 1
  "record_type":    str           # always "completed_job"
  "job_id":         str
  "finalized_at":   str           # ISO timestamp (UTC)
  "vacuum": {
    "entity_id": str
    "name":      str              # vacuum slug (entity_id after the ".")
  }
  "job":            JobTimings
  "battery":        BatteryInfo
  "water":          dict          # water estimate; {} if unavailable
  "queue":          QueueSnapshot
  "payload":        dict          # API payload dict ({"map_id": ..., "rooms": [...]})
  "resolved_rooms": list[ResolvedRoom]
  "job_profile":    JobProfile
  "outcome":        OutcomeInfo
  "learning_context": LearningContext
  "trace_run_id":   str | None
}
```

### `JobTimings`

```
{
  "started_at":                  str
  "ended_at":                    str
  "duration_minutes":            float    # active cleaning time (wall clock minus pauses minus recharge)
  "wall_clock_duration_minutes": float
  "paused_duration_seconds":     int
  "room_count":                  int
  "actual_cleaning_minutes":     float | None   # single-room jobs only
  "return_to_dock_minutes":      float | None   # single-room only
  "room_cleaning_minutes":       float | None   # single-room only
  "cleaning_time_seconds":       int | None     # from HA sensor; if available at finalization
  "cleaning_area_m2":            float | None   # from HA sensor; if available
}
```

### `BatteryInfo`

```
{
  "start":                             int
  "end":                               int
  "used":                              int    # max(start - end, 0)
  "mid_job_recharge_observed":         bool
  "mid_job_recharge_started_at":       str | None
  "mid_job_recharge_count":            int
  "recharge_seconds_accumulated":      int
}
```

### `QueueSnapshot`

```
{
  "vacuum_entity_id": str
  "map_id":           str
  "room_count":       int
  "queue_room_ids":   list[int]
  "queue_rooms":      list[QueueRoomSummary]
}
```

### `JobProfile`

```
{
  "map_id":      int
  "room_count":  int
  "room_slugs":  list[str]
  "rooms":       list[ResolvedRoom]
}
```

### `OutcomeInfo`

```
{
  "status":             str        # "completed" | "cancelled" | "failed" | "interrupted" | "test"
  "used_for_learning":  bool
  "sanity_passed":      bool
  "sanity_flags":       list[str]
  "learning_blockers":  list[str]
  "was_cancelled":      bool
  "was_failed":         bool
  "was_interrupted":    bool
  "is_test_job":        bool
  "lifecycle_state":    str
  "lifecycle_message":  str
  "cancel_detection":   CancelDetection
}
```

`sanity_passed` / `sanity_flags` are the backend sanity verdict. A missing/`None`
`sanity_passed` is **not** treated as a failure — the history view checks
`item.get('sanity_passed') is False` (the jobs index stored the key as `None`, so a
naive `.get(..., True)` default never fired). Graduated **external** runs (§9b) set
`sanity_passed=True` / `sanity_flags=[]` explicitly — they are sane by construction.

**`learning_blockers` values:** `"invalid_room_count"`, `"invalid_duration"`,
`"missing_resolved_rooms"`, `"job_cancelled"`, `"job_failed"`,
`"job_interrupted"`, `"test_job"`, `"cancel_likely"` (or reason string from
cancel detection).

### `CancelDetection`

```
{
  "cancel_likely":              bool
  "reason":                     str
  "source":                     str    # "physical_vacuum" | "app_or_manual_return"
  "duration_minutes":           float
  "actual_cleaning_minutes":    float  # floor_time_too_short path
  "floor_threshold_minutes":    float  # floor_time_too_short path (1.5 min)
  "expected_room_minutes":      float  # estimate-based paths
  "short_threshold_minutes":    float  # estimate-based paths
  "message":                    str    # present when cancel_likely=True
}
```

### `LearningContext`

```
{
  "schema_version": int   # always 1
  "queue_shape": {
    "key":         str
    "room_ids":    list[int]
    "room_slugs":  list[str]
    "room_modes":  list[str]
    "room_count":  int
  }
  "estimate_snapshot": {
    "available":                      bool
    "estimated_room_minutes_total":   float
    "estimated_overhead_minutes":     float
    "estimated_total_minutes":        float
    "estimated_total_battery_used":   float
    "job_confidence_score":           float
    "job_confidence_label":           str | None
  }
  "actuals": {
    "actual_job_minutes":   float
    "actual_battery_used":  float
  }
  "estimate_delta": {
    "total_minutes_delta":       float | None
    "total_minutes_delta_ratio": float | None
  }
  "access_graph": {
    "present":                  bool
    "edge_count":               int
    "pair_count":               int
    "graph_transition_count":   int
    "graph_jump_count":         int
    "graph_coherence_score":    float | None
  }
}
```

### `ResolvedRoom` as enriched in a completed job

When the live snapshot contained an estimate, each room in `resolved_rooms`
gains additional fields beyond the standard `ResolvedRoom` shape (§4):

```
  "estimated_minutes":            float
  "estimated_battery":            float
  "estimate_confidence_score":    float
  "estimate_confidence_label":    str | None
  "estimate_source":              str | None   # "learned" | "default"
```

### 9b. Graduated External Completed-Job Record

Built by `build_graduated_job` in `learning/external_ingest.py` when a pending
external record (§5a) is confirmed in review. It is a **leaner variant** of the §9
record — the stats rebuilder ingests it, but external capture has no dispatched
queue/payload, no battery-start, and no transit edges, so those sections are absent
or stubbed. Persisted under the same `jobs/` directory, tagged `origin: "external"`.

Graduation is **atomic**: every confirmed assignment must pass the tier-1 identity
gate (`gate_segment_identity` — a wide area-band plausibility check, bypassable per
assignment with `override`), or the build returns `(None, blocked)` and nothing is
written.

```
{
  "record_type":    str           # "completed_job"
  "schema_version": int           # 1
  "job_id":         str
  "origin":         str           # "external"
  "vacuum":         {entity_id, name}
  "job": {
    "started_at":           str | None   # = pending detection_ts
    "ended_at":             str | None
    "duration_minutes":     float        # summed segment wall-time / 60
    "room_count":           int
    "room_timings":         list[ExtRoomTiming]
    "transitions":          list         # [] — external runs emit no transit edges
    "transit_capture_valid": bool        # True (gates the rebuilder's use of room_timings)
  }
  "job_profile":    {map_id, room_count, rooms: list[ExtProfileRoom]}
  "resolved_rooms": list[ExtProfileRoom]   # same list as job_profile.rooms
  "outcome": {
    "status":            str    # "completed"
    "used_for_learning": bool   # True
    "origin":            str    # "external"
    "sanity_passed":     bool   # True  — sane by construction (passed the identity gate)
    "sanity_flags":      list   # []
  }
  "finalized_at":   str | None
}
```

`ExtRoomTiming` carries `{room_id, slug, cleaning_start, cleaning_end,
cleaning_seconds, cleaning_wall_seconds, area_m2}` (one or more merged segments per
room). `ExtProfileRoom` carries `{room_id, slug, name, clean_mode, clean_intensity,
fan_speed, water_level, clean_passes, is_carpet, edge_mopping}` — settings resolved
as explicit override → the segment's recovered selects → the room config.

---

## 10. Learning Estimate

Returned by `LearningEstimator.estimate` in `learning/estimator.py`.

### Top-level shape

```
{
  "vacuum_entity_id":   str
  "map_id":             int
  "room_count":         int
  "estimated_at":       str
  "started_at":         str | None
  "stats_stale":        bool
  "stats_rebuilt_at":   str | None
  # --- Timing ---
  "room_minutes_total": float
  "overhead_minutes":   float
  "overhead":           OverheadBreakdown
  "total_minutes":      float
  "job_eta_minutes":    float
  "job_eta_at":         str
  # --- Battery ---
  "total_battery_used":                        float
  "required_start_battery":                    float
  "battery_shortfall":                         float
  "estimated_charge_minutes":                  float
  "remaining_battery_after_job":               float
  "mid_job_recharge_risk":                     bool
  "mid_job_recharge_needed_battery":           float
  "mid_job_recharge_estimated_charge_minutes": float
  "projected_recharge_overhead_minutes":       float
  "can_run_now":     bool
  "battery_warning": bool
  # --- Confidence ---
  "confidence_score":      float
  "confidence_label":      str      # "high" | "medium" | "low"
  "confidence_breakpoint": ConfidenceBreakpoint
  # --- Room breakdown ---
  "breakdown":     list[RoomTimelineEntry]
  "room_timeline": list[RoomTimelineEntry]
  "_debug": {
    "weighted_avg_confidence_score": float
  }
}
```

**Error shape** (returned when `ordered_rooms` is empty):

```
{
  "vacuum_entity_id": str
  "map_id":           int
  "room_count":       0
  "estimated_at":     str
  "started_at":       str | None
  "error":            "no_payload"
  "error_detail":     str
  "stats_stale":      bool
  "stats_rebuilt_at": str | None
  "can_run_now":      False
}
```

### `OverheadBreakdown`

```
{
  "startup_minutes":    float   # fixed 1.0 min
  "transition_minutes": float   # 0.75 min × (room_count - 1)
  "recharge_minutes":   float
  "mop_wash_minutes":   float
  "dust_empty_minutes": float
  "return_minutes":     float   # fixed 1.0 min
  "mop_wash": {
    "mode":               str    # "by_time" | "by_room" | "off" | "unknown"
    "mode_entity_id":     str
    "interval_entity_id": str
    "interval_minutes":   float  # clamped [15.0, 25.0]
    "projected_mop_minutes": float
    "cycle_count":        int
    "minutes_per_cycle":  float  # 1.5
    "mode_available":     bool
    "interval_available": bool
  }
}
```

### `ConfidenceBreakpoint`

```
{
  "key":        str    # "high" | "medium" | "low"
  "min_score":  float  # 0.80 | 0.50 | 0.00
  "max_score":  float  # 1.00 | 0.79 | 0.49
  "ui_rank":    int    # 3 | 2 | 1
  "ui_variant": str    # "success" | "warning" | "error"
}
```

### `RoomTimelineEntry`

```
{
  "position":              int
  "room_id":               int
  "room_name":             str
  "slug":                  str
  "clean_mode":            str
  "clean_passes":          int
  "clean_intensity":       str
  "is_carpet":             bool
  "source":                str    # "learned" | "default"
  "intensity_mismatch":    bool
  "sample_count":          int
  "accuracy_drift_ratio":  float
  "minutes":               float
  "battery":               float
  "start_offset_minutes":  float
  "end_offset_minutes":    float
  "eta_minutes_from_start": float
  "eta_at":                str
  "completed":             bool   # run-state flags (see note) — stamped by the live snapshot
  "current":               bool
  "remaining":             bool
  "skipped":               bool
  "running_long":          bool
  "progress_percent":      int
  "elapsed_minutes":       float
  "remaining_minutes":     float
  "learning_velocity": {
    "runs_to_medium": int
    "runs_to_high":   int
    "current_tier":   str
  }
  "confidence_score":      float
  "confidence_label":      str
  "confidence_breakpoint": ConfidenceBreakpoint
}
```

The run-state flags (`completed` / `current` / `remaining` / `skipped` /
`running_long`) are **not** set by the estimator — they are stamped per room by
`get_job_progress_snapshot` (§5b) when this timeline is reused as the live job view.

After `reanchor_timeline` enrichment, completed rooms gain:

```
  "actual_duration_minutes": float
  "reanchored":              bool
```

### Confidence scoring model

| Component | Value |
|---|---|
| Base score (learned match) | 0.55 |
| Base score (default fallback) | 0.20 |
| Sample bonus (max) | +0.25 at 10 samples |
| Variance penalty (max) | -0.25 when CV ≥ 0.5 |
| Intensity mismatch penalty | -0.15 |
| Accuracy penalty (max) | -0.20 when mean abs % error ≥ 0.20 |

Job confidence = `min(all room scores)`. The weakest room drives the job
estimate — this is a hard architectural rule.

---

## 11. Theme Object

### `ThemeEntry` (library entry)

`data["theme"]["library"][theme_id]`. Defined in `models/models.py`.

```
{
  "id":     str
  "name":   str
  "tokens": dict    # str → Any; color token aliases plus layout/motion tokens
  "colors": dict    # str → str; CSS custom property names → hex/rgba
  "alpha":  dict    # str → float; named opacity values 0.0–1.0
}
```

**Invariant:** `tokens` is a superset of `colors`. When building a theme entry
via `_build_preloaded_theme_entry`, token values are merged as
`{**colors, **tokens}`.

**Built-in theme IDs:** `"theme_follow_ha"`, `"theme_core_slate"`,
`"theme_forest_night"`, `"theme_soft_carbon"`, `"theme_warm_light"`,
`"theme_high_contrast"`, `"theme_signal"`. Seeded on every boot; never
replaced if already present.

### `ThemeDraft` (working draft)

`data["theme"]["vacuums"][vacuum_entity_id]["working_draft"]`.

```
{
  "tokens": dict    # str → Any; only overridden keys
  "colors": dict    # str → str; only overridden keys
  "alpha":  dict    # str → float; only overridden keys
}
```

Only keys explicitly overridden by the user are present — unset keys inherit
from the active theme at read time.

### `ThemeVacuumState` (per-vacuum)

`data["theme"]["vacuums"][vacuum_entity_id]`.

```
{
  "active_theme_id": str | None
  "working_draft":   ThemeDraft
  "draft_dirty":     bool
  "editor_mode":     str    # always "live"
}
```

### Design token CSS custom properties

All token keys follow the `--evcc-*` naming convention.

| Group | Prefix | Examples |
|---|---|---|
| Semantic | `--evcc-sem-*` | `success`, `warning`, `error`, `info` |
| Surfaces | `--evcc-surface-*` | `base`, `panel`, `raised`, `input`, `overlay` |
| Text | `--evcc-text-*` | `primary`, `secondary`, `muted` |
| Borders | `--evcc-border-*` | `subtle`, `default`, `strong` |
| Chips | `--evcc-chip-*` | sizing, color states |
| Queue chips | `--evcc-queue-*` | completed, current, pending, skipped |
| Confidence | `--evcc-confidence-*` / `--evcc-conf-*` | high/medium/low variants |
| Learning | `--evcc-learning-*` | confidence gradients, chip typography |
| Modal | `--evcc-modal-*` | backdrop, padding, radius |
| Layout | various | `--evcc-gap`, `--evcc-radius-card`, `--evcc-font-family` |

---

## 12. Setup Progress

`data["setup_progress"][vacuum_entity_id]`

Written and read by `setup/drift.py`. Tracks which wizard steps have been
completed for each vacuum.

```
{
  "completed_steps":    list[str]             # ordered list of completed step IDs
  "last_advanced_at":   str | None            # ISO timestamp of last step completion
  "rejected_rooms":     list[int]             # room IDs the user dismissed during setup
  "room_drift_history": dict[room_id_str, DriftHistoryEntry]   # one entry per room_id
}
```

**Step IDs** (constants in `setup/drift.py`): `"add_vacuum"`,
`"import_active_map"`, `"save_rooms"`.

**Migration:** `_migrate_setup_progress()` in `core/manager.py` stamps all
three legacy steps complete for any vacuum that already had managed rooms
before the state machine was introduced.

### `DriftHistoryEntry`

A single dict per `room_id` (not a list), written by `setup/drift.py`.

```
{
  "missing_passes":   int           # consecutive drift passes the room was absent
  "seen_passes":      int           # consecutive drift passes the room was present
  "last_seen_at":     str | None    # ISO timestamp the room was last discovered
  "first_missed_at":  str | None    # ISO timestamp the current missing streak began
  "first_seen_at":    str | None    # ISO timestamp the room was first discovered
}
```

---

## 13. Error Tracker

`data["error_tracker"][vacuum_entity_id]`

Maintained by `ErrorTracker` (`core/error_tracker.py`). Three buffers per
device:

```
{
  "active_run_error":  ActiveRunError | None   # sticky during a job; nulled at harvest
  "last_device_error": DeviceError | None      # persistent until acknowledged
  "recent_errors":     list[RecentErrorEntry]  # ring buffer; max 50
}
```

### `ActiveRunError`

Set on first rising edge (non-empty error message) while a job is active.

```
{
  "job_id":         str | None
  "first_seen_at":  str           # ISO timestamp
  "last_seen_at":   str
  "message":        str
  "code":           str | None
  "rising_edges":   int           # count of distinct rising edges in this run
  "recovered":      bool          # True when error message cleared mid-run
}
```

### `DeviceError`

```
{
  "seen_at":  str      # ISO timestamp of most recent rising edge
  "message":  str
  "code":     str | None
}
```

### `RecentErrorEntry`

```
{
  "seen_at":    str
  "message":    str
  "code":       str | None
  "in_active_run": bool
  "job_id":     str | None
}
```

**Edge detection:** the core fallback "not-error" set is
`{"", "unknown", "unavailable"}` (the `_NOT_ERROR` frozenset in
`core/error_tracker.py`, used only when no adapter is registered). When an
adapter is present, its `vocabulary.not_error_sentinels` is used — the Eufy
adapter adds the firmware sentinels `"none"` and `"normal"` (from robovac_mqtt's
`"NONE"` / `"Normal"`), so the effective Eufy set is
`{"", "unknown", "unavailable", "none", "normal"}`. Matching is case-normalized
to lowercase. Any other value is an error string; a rising edge is a transition
*into* an error value, a falling edge is the reverse.

**Late-arrival grace window:** when the vacuum state transitions to `"error"`
but the error message sensor is still empty, a 5-second one-shot callback
upgrades the latch. If the message doesn't arrive in time, the latch is
finalized as `"Unknown error during run"`.

---

## 14. Incomplete Run Log

Written by `_write_incomplete_run_log` in `learning/job_finalizer.py`.  
Path: `eufy_vacuum/learning/{vacuum_slug}/live/incomplete_run.json`  
Single-overwrite — only the most recent incomplete run is kept.  
Written for `outcome_status` in `{"cancelled", "failed", "interrupted"}`.  
Cleared when a job completes or when `retry_missed_rooms` fires.

```
{
  "schema_version":     int          # always 1
  "record_type":        str          # always "incomplete_run_log"
  "vacuum_entity_id":   str
  "job_id":             str
  "map_id":             str
  "outcome_status":     str
  "ended_at":           str
  "queued_room_ids":    list[int]
  "completed_room_ids": list[int]
  "missed_room_ids":    list[int]    # sorted; set difference of queued minus completed
  "missed_rooms": [
    {
      "room_id": int
      "name":    str
    }
  ]
  "logged_at":          str
}
```

**Invariant:** `missed_room_ids == sorted(set(queued_room_ids) - set(completed_room_ids))`.

---

## 15. Trouble Rooms Log

Written and updated by `_update_trouble_rooms_log` in `learning/job_finalizer.py`
after every job finalization.  
Path: `eufy_vacuum/learning/{vacuum_slug}/live/trouble_rooms.json`  
Single-overwrite updated in place.

A room is flagged `is_trouble` when `miss_count >= 2` AND `miss_rate >= 0.33`.

```
{
  "schema_version":   int
  "record_type":      str    # always "trouble_rooms_log"
  "vacuum_entity_id": str
  "updated_at":       str
  "rooms":            dict[room_id_str, TroubleRoomEntry]
}
```

### `TroubleRoomEntry`

```
{
  "room_id":         int
  "name":            str
  "run_count":       int
  "miss_count":      int
  "miss_rate":       float    # miss_count / run_count; 3 decimal places
  "is_trouble":      bool
  "last_cleaned_at": str      # present when last run included this room
  "last_missed_at":  str      # present when last run missed this room
}
```

---

## 16. Key Constraints

These constraints apply across the entire data model. Violating them produces
silent bugs — they are not enforced at write time.

### String keys for dict lookups

- `map_id` keys in `data["maps"]`, `data["active_jobs"]`, `data["room_history"]`,
  `data["room_rule_status"]`, and `data["run_profiles"]` are always `str`.
- `room_id` keys in `data["maps"][v][m]["rooms"]`, `data["room_history"]`,
  and `data["room_rule_status"]` are always `str`.
- `room_id` *values* inside room dicts (the `room_id` field) are always `int`.
- To look up a room: `rooms.get(str(room_id))`, never `rooms.get(room_id)`.

### Timestamps

All stored timestamps are ISO 8601 UTC strings (e.g. `"2026-05-30T14:22:01+00:00"`).
The `utc_now_iso()` helper in `timestamp_utils.py` is the canonical source.
Parse with `parse_timestamp()` from the same module rather than
`datetime.fromisoformat()` directly — it handles the `Z` suffix variant.

### Derived fields are not stored

`data["maps"][v][m]["summary"]`, queue snapshots, and payload snapshots are
derived state. They are always rebuilt from room configuration — never edited
in place. `_refresh_room_derived_state()` rebuilds both before any
`_notify_rooms_updated()` call.

Likewise on the segment side (§3a): a served segment's `polygon_pct`, `room_id`,
and applied `image_segment_adjustments` are derived at read time by
`get_map_segments` — the stored `image_segments` cache and each layout's
`custom_segments` store are never mutated in place. `segmentation_mode` (plus
`active_custom_layout_id`) is a pointer, not a copy: the CV store and every named
custom layout persist independently, and `set_segmentation_mode` only flips the
pointer (never re-runs the segmenter), so toggling modes — and switching layouts —
is lossless.

### `is_configured` gate

Only rooms with `is_configured=True` are returned by `sort_room_items()` and
thus become HA entities. Rooms with `is_configured=False` exist in storage and
in the manager's room data, but have no corresponding switch, number, or sensor
entity. This is the correct path for new rooms discovered mid-use before the
user confirms them through the setup wizard.

### `async_save` is always the service layer's responsibility

Subsystem managers write directly to `self._manager.data[key]` for their own
domain keys but never call `async_save()`. The final `await manager.async_save()`
always lives at the service layer (service handler or entity `_async_update_room`).

### Room history cache

`data["room_history"]` is populated either:
1. Eagerly at sensor platform startup via `async_preload_room_history_cache`
   (reads learning store files in an executor thread), or
2. Lazily on job finalization via `_ingest_completed_job_into_room_history`.

The `_room_history_cache_ready` set on the manager tracks which vacuums have
been pre-loaded. Sensors reading history before the first job completes get
their data from this disk-backed preload.
