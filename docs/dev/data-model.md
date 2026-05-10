# Data Model Reference

This document is the canonical shape reference for every major object in the eufy_vacuum integration. All field names, types, and constraints are derived directly from source. A developer reading this document should be able to reconstruct the full data model without reading source.

---

## Table of Contents

1. [HA Storage Schema](#1-ha-storage-schema)
2. [Room Object](#2-room-object)
3. [Map Object](#3-map-object)
4. [Queue Payload](#4-queue-payload)
5. [Active Job](#5-active-job)
6. [Learning Record (Completed Job)](#6-learning-record-completed-job)
7. [Learning Estimate](#7-learning-estimate)
8. [Room Bounds](#8-room-bounds)
9. [Theme Object](#9-theme-object)
10. [Incomplete Run Log](#10-incomplete-run-log)
11. [Trouble Rooms Log](#11-trouble-rooms-log)

---

## 1. HA Storage Schema

**File:** `.storage/eufy_vacuum.storage`  
**Storage key:** `eufy_vacuum.storage`  
**Schema version:** `1` (STORAGE_VERSION constant in `core/storage.py`)  
**Managed by:** `EufyVacuumStorage` (`core/storage.py`) via HA's `Store` helper.  
**Never edit this file directly** — use the HA UI. Direct edits produce `.corrupt` backup files.

### Top-level shape

```
{
  "vacuums":          dict[vacuum_entity_id, VacuumBucket]     # required; {} on first boot
  "maps":             dict[vacuum_entity_id, dict[map_id, MapBucket]]  # required; {} on first boot
  "theme":            ThemeRoot                                 # required; seeded by async_initialize
  "analytics":        dict                                      # reserved; always {}
  "maintenance":      dict                                      # reserved; always {}
  "dock_events":      dict                                      # reserved; always {}
  "icons":            dict                                      # reserved; always {}
  "onboarding":       dict                                      # reserved; always {}
  "capabilities":     dict[vacuum_entity_id, CapabilityBucket] # seeded by async_initialize
  "room_history":     dict                                      # seeded by async_initialize
  "room_rule_status": dict[vacuum_entity_id, dict[map_id, dict[room_id_str, LiveRuleState]]]
  "discovery":        dict[vacuum_entity_id, dict[map_id, DiscoveryPayload]]  # optional; legacy flat shape migrated on load
}
```

`map_id` keys inside `"maps"` and `"room_rule_status"` are always strings (e.g. `"6"`), even when the underlying value is numeric.

### VacuumBucket

Stored at `data["vacuums"][vacuum_entity_id]`.

```
{
  "pause_timeout_minutes_default": int   # optional; default 0; non-negative
}
```

### MapBucket

Stored at `data["maps"][vacuum_entity_id][map_id_str]`.

```
{
  "map_id":   str                        # required; string form of the numeric map ID
  "metadata": MapMetadata                # required; {} until first discovery
  "rooms":    dict[room_id_str, RoomRecord]  # required; {} until rooms are configured
  "summary":  RoomSelectionSummary       # required; rebuilt by build_room_selection_summary
}
```

`room_id_str` keys inside `"rooms"` are always strings (e.g. `"3"`), even though `room_id` values on the room dict itself are integers.

### MapMetadata

Stored at `data["maps"][vacuum_entity_id][map_id_str]["metadata"]`.

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

Stored at `data["maps"][vacuum_entity_id][map_id_str]["summary"]`. Rebuilt on every room change by `build_room_selection_summary`.

```
{
  "enabled_count":  int
  "disabled_count": int
}
```

### ThemeRoot

Stored at `data["theme"]`. Seeded on every boot by `_ensure_preloaded_theme_library`.

```
{
  "library":          dict[theme_id, ThemeEntry]     # built-in and user themes
  "default_theme_id": str | None                     # points into library; defaults to "theme_follow_ha"
  "vacuums":          dict[vacuum_entity_id, ThemeVacuumState]
}
```

---

## 2. Room Object

Rooms appear in three distinct contexts. The stored shape is authoritative; the other two are derived.

### 2a. Stored shape (`RoomRecord`)

TypedDict defined in `models/models.py`. Stored as a plain `dict` in `data["maps"][vacuum_entity_id][map_id_str]["rooms"][room_id_str]`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `room_id` | `int` | required | Numeric ID from the vacuum API. Key in parent dict is `str(room_id)`. |
| `map_id` | `str` | required | String form of the map ID. |
| `name` | `str` | required | Display name. |
| `slug` | `str \| None` | optional | URL-safe identifier; may be `None` if not yet assigned. |
| `enabled` | `bool` | required | Whether the room is included in the next job queue. |
| `order` | `int` | required | Zero-based sort position within the map. |
| `profile_name` | `str \| None` | optional | Active preset name; default `"vacuum_quick"`. |
| `floor_type` | `str` | required | One of: `"hardwood"`, `"laminate"`, `"tile"`, `"marble"`, `"carpet_low_pile"`, `"carpet_high_pile"`. Carpet pile is encoded in the value — use `floor_type.startswith("carpet")` rather than a separate flag. |
| `clean_mode` | `str` | required | `"vacuum"`, `"mop"`, or `"vacuum_mop"`. |
| `fan_speed` | `str` | required | e.g. `"Max"`, `"Boost"`, `"Standard"`, `"Quiet"`. |
| `water_level` | `str` | required | `"Off"`, `"Low"`, `"Medium"`, `"High"`. |
| `clean_intensity` | `str` | required | `"Standard"`, `"Intense"`, etc. |
| `clean_passes` | `int` | required | Number of cleaning passes; minimum 1. |
| `edge_mopping` | `bool` | required | Whether edge mopping is active. |
| `path_type` | `str \| None` | optional | `"wide"`, `"narrow"`, or `None`. |
| `is_dock_room` | `bool` | required | Marks the room that contains the dock. Backfilled to `False` on schema migration. |
| `grants_access_to` | `list[str]` | required | Room slugs this room grants traversal access to. Backfilled to `[]`. |
| `rules` | `list[dict]` | required | `RuleDefinition` dicts. Backfilled to `[]`. |

**Schema migration** (in `async_initialize`): `path_type`, `is_dock_room`, `grants_access_to`, `rules`, `floor_type`, and `profile_name` are backfilled with `setdefault`. The old `floor_type="carpet"` + `carpet_type` sub-field is collapsed into `"carpet_low_pile"` / `"carpet_high_pile"` in place. The derived `carpet` boolean is removed.

**`is_transition` field:** The backfill also seeds `_room.setdefault("is_transition", False)` but this field is not present on `RoomRecord` TypedDict — treat it as internal/legacy.

### 2b. As returned from `get_managed_rooms`

`get_managed_rooms` returns the same `dict[str, dict]` stored in `MapBucket["rooms"]` — the room dicts are the stored `RoomRecord` shapes directly, keyed by `room_id_str`.

### 2c. As it appears in queue payload items (`queue_rooms` list)

Built by `build_queue_from_managed_rooms` in `queue/queue_engine.py`. This is a compact summary, not the full record.

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
  "kind":      str      # "blocker" | "modifier"
  "operator":  str      # "equals" | "not_equals" | "in" | "not_in" | "gt" | "gte" | "lt" | "lte" | "is_on" | "is_off" | "exists" | "missing"
  "value":     Any      # RHS of comparison; None for boolean operators
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

A map is represented by its `MapBucket` in storage (see §1). There is no separate top-level map dataclass — maps are always accessed as buckets.

### As summarized by `get_vacuum_maps_summary`

Returns one entry per map in a list. Source: `maps/map_manager.py`.

```
{
  "map_id":               str
  "room_count":           int    # total rooms in the bucket
  "enabled_room_count":   int
  "disabled_room_count":  int
  "last_discovery": {
    "active_map_id": str | int | None
    "room_count":    int
  }
}
```

The full response from `get_vacuum_maps_summary` is:

```
{
  "vacuum_entity_id": str
  "map_count":        int
  "maps":             list[MapSummaryEntry]
}
```

### `MapConfig` dataclass

Defined in `models/models.py`. In-memory normalized form; not persisted directly.

```
MapConfig:
  map_id:  str                        # required
  name:    str | None                 # optional; default None
  rooms:   dict[int, RoomConfig]      # keyed by integer room_id; default {}
```

`as_dict()` serializes rooms as `dict[str(room_id), RoomConfig.as_dict()]`.

---

## 4. Queue Payload

Built by `build_room_clean_payload` in `queue/queue_engine.py`. This is the full object passed to the vacuum's room-clean API.

### Return shape of `build_room_clean_payload`

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

The object sent to the vacuum API per room. Capability-gated fields are conditionally present.

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

### `ResolvedRoom` (inside `resolved_rooms`)

Enriched room metadata after profile resolution and capability gating. Used for display, logging, and learning.

```
{
  "room_id":              int
  "name":                 str | None
  "slug":                 str | None
  "selected_profile_name": str
  "resolved_profile_name": str
  "clean_mode":           str
  "fan_speed":            str
  "water_level":          str
  "clean_intensity":      str
  "path_type":            str
  "clean_passes":         int
  "edge_mopping":         bool
  "carpet":               bool    # True when floor_type.startswith("carpet")
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

A lighter object built before the payload. Also stored in `active_job["queue_rooms"]`.

```
{
  "vacuum_entity_id": str
  "map_id":           str
  "room_count":       int
  "queue_room_ids":   list[int]
  "queue_rooms":      list[QueueRoomSummary]   # see §2c
}
```

### `PayloadItem` TypedDict (canonical shape for one room, `queue_engine.py`)

This TypedDict documents the canonical per-room payload shape post capability-gating. All fields are always present.

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

## 5. Active Job

The active job is an in-memory dict built by `build_active_job_state` in `queue/queue_engine.py` and frozen at job-start time. Only `status` and `ended_at` are written after the freeze point.

### Shape returned by `build_active_job_state`

```
{
  "vacuum_entity_id":        str
  "map_id":                  str
  "queue_room_ids":          list[int]          # frozen at job start
  "queue_stable_keys":       list[str]          # "{vacuum_entity_id}:{map_id}:{room_id}" per room
  "queue_rooms":             list[QueueRoomSummary]
  "payload":                 dict               # API payload dict ({"map_id": ..., "rooms": [...]})
  "resolved_rooms":          list[ResolvedRoom]
  "room_count":              int
  "status":                  str               # "started" on creation; later "running" | "paused" | "completed" | "cancelled"
  "paused_at":               None              # set to ISO timestamp if paused
  "paused_duration_seconds": int               # accumulated pause seconds; starts at 0
  "completed_room_ids":      list[int]         # rooms confirmed cleaned during the run
  "completed_rooms":         list[dict]        # room summary dicts for completed rooms
  "current_room_id":         int | None        # first room from resolved_rooms, or first from queue_room_ids
  "current_room_started_at": None              # set when a room starts
  "current_room_paused_seconds": int           # starts at 0
}
```

**Fields populated during the run** (not present in the initial snapshot but written to the active job by the job monitor):

```
  "started_at":                        str         # ISO timestamp
  "ended_at":                          float | None # unix timestamp; None until job ends
  "battery_start":                     int
  "state_transitions":                 list[dict]  # [{entity_id, from_state, to_state, changed_at}]
  "observed_mid_job_recharge":         bool
  "observed_mid_job_recharge_started_at": str | None
  "observed_mid_job_recharge_count":   int
  "recharge_seconds_accumulated":      int
  "observed_mop_wash_count":           int
  "observed_mop_wash_last_at":         str | None  # iso ts of most recent observed wash
  "observed_mop_wash_cycles":          list[dict]  # per-cycle log: [{"observed_at": iso ts}, ...] (capped at 50)
  "water_estimate":                    dict        # water usage estimate (see §7)
  "job_metadata":                      dict        # {map_id, room_count, room_slugs}
  "trace_run_id":                      str | None
```

**Invariants:**
- `queue_stable_keys` is always a composite of `"{vacuum_entity_id}:{map_id}:{room_id}"`. It is built at freeze time from `queue_room_ids` and does not change.
- `queue_room_ids` is preserved for backward compatibility with the learning subsystem even though `queue_stable_keys` is the canonical identity mechanism.

### `ActiveJobSnapshot` TypedDict (`queue_engine.py`)

Documents the intended frozen shape. All fields are present.

```
{
  "vacuum_entity_id":   str
  "job_id":             str
  "frozen_at":          float           # unix timestamp
  "queue_stable_keys":  list[str]
  "queue_entries":      dict            # dict[stable_key, QueueEntry]
  "payload_items":      dict            # dict[stable_key, PayloadItem]
  "status":             str            # "running" | "paused" | "completed" | "cancelled"
  "started_at":         float
  "ended_at":           float | None
}
```

### `QueueEntry` TypedDict (`queue_engine.py`)

```
{
  "stable_key":          str    # "{vacuum_entity_id}:{map_id}:{room_id}"
  "vacuum_entity_id":    str
  "map_id":              str
  "room_id":             int
  "name":                str | None
  "slug":                str | None
  "order":               int
  "effective_settings":  dict   # EffectiveRoomSettings snapshot at queue-build time
  "enabled":             bool
}
```

---

## 6. Learning Record (Completed Job)

Built by `LearningHistoryStore.build_completed_job_payload` in `learning/history_store.py`. Persisted to `eufy_vacuum/learning/{vacuum_slug}/jobs/{job_id}.json`.

For a job to be used for learning (`is_learning_job` returns True), it must have `record_type == "completed_job"`, `outcome.status == "completed"`, and `outcome.used_for_learning == True`.

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
  "water":          dict          # water estimate (see §7 water section); {} if unavailable
  "queue":          QueueSnapshot
  "payload":        dict          # API payload dict ({"map_id": ..., "rooms": [...]})
  "resolved_rooms": list[ResolvedRoom]  # enriched with estimate fields if snapshot was available
  "job_profile":    JobProfile
  "outcome":        OutcomeInfo
  "learning_context": LearningContext   # added by finalize_from_inputs
  "trace_run_id":   str | None          # present only if active_job had a trace_run_id
}
```

### `JobTimings`

```
{
  "started_at":                  str           # ISO timestamp
  "ended_at":                    str           # ISO timestamp
  "duration_minutes":            float         # active cleaning time (wall clock minus pauses minus recharge)
  "wall_clock_duration_minutes": float         # raw start→end duration
  "paused_duration_seconds":     int
  "room_count":                  int
  "actual_cleaning_minutes":     float | None  # single-room jobs only: duration until "returning" transition
  "return_to_dock_minutes":      float | None  # single-room only
  "room_cleaning_minutes":       float | None  # single-room only
  "cleaning_time_seconds":       int | None    # from HA sensor; present only if available at finalization
  "cleaning_area_m2":            float | None  # from HA sensor; present only if available
}
```

### `BatteryInfo`

```
{
  "start":                             int
  "end":                               int
  "used":                              int   # max(start - end, 0)
  "mid_job_recharge_observed":         bool
  "mid_job_recharge_started_at":       str | None
  "mid_job_recharge_count":            int
  "recharge_seconds_accumulated":      int
}
```

### `QueueSnapshot`

Mirrors the queue state at job start. Falls back to active job state if queue_state is empty.

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
  "rooms":       list[ResolvedRoom]   # same as top-level resolved_rooms
}
```

### `OutcomeInfo`

```
{
  "status":             str         # "completed" | "cancelled" | "failed" | "interrupted" | "test"
  "used_for_learning":  bool
  "sanity_passed":      bool
  "sanity_flags":       list[str]   # sorted; e.g. ["invalid_duration", "invalid_room_count"]
  "learning_blockers":  list[str]   # sorted; always non-empty when used_for_learning=False
  "was_cancelled":      bool
  "was_failed":         bool
  "was_interrupted":    bool
  "is_test_job":        bool
  "lifecycle_state":    str         # from job_finalizer inputs
  "lifecycle_message":  str
  "cancel_detection":   CancelDetection
}
```

**`learning_blockers` values:** `"invalid_room_count"`, `"invalid_duration"`, `"missing_resolved_rooms"`, `"job_cancelled"`, `"job_failed"`, `"job_interrupted"`, `"test_job"`, `"cancel_likely"` (or reason string from cancel detection).

### `CancelDetection`

```
{
  "cancel_likely":              bool
  "reason":                     str     # "missing_timestamps" | "not_single_room" | "no_transition_history" | "service_state_explains_return" | "no_cancel_like_transition" | "duration_not_short" | "floor_time_too_short" | "early_return_likely_cancelled"
  "source":                     str     # "physical_vacuum" | "app_or_manual_return" (when cancel_likely=True)
  "duration_minutes":           float   # present on most paths
  "actual_cleaning_minutes":    float   # present on floor_time_too_short path
  "floor_threshold_minutes":    float   # present on floor_time_too_short path (1.5 min)
  "expected_room_minutes":      float   # present on estimate-based paths
  "short_threshold_minutes":    float   # present on estimate-based paths
  "message":                    str     # present when cancel_likely=True
}
```

### `LearningContext`

Attached by `_build_learning_context` in `learning/job_finalizer.py`.

```
{
  "schema_version": int   # always 1
  "queue_shape": {
    "key":         str    # "map:{map_id}|count:{n}|rooms:{ids}|modes:{modes}"
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
    "total_minutes_delta":       float | None   # None if no estimate was available
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

When the live snapshot contained an estimate, each room in `resolved_rooms` gains additional fields beyond the standard `ResolvedRoom` shape (§4):

```
  "estimated_minutes":            float
  "estimated_battery":            float
  "estimate_confidence_score":    float
  "estimate_confidence_label":    str | None
  "estimate_source":              str | None   # "learned" | "default"
```

---

## 7. Learning Estimate

Returned by `LearningEstimator.estimate` in `learning/estimator.py`. This is the full job-level estimate object.

### Top-level shape

```
{
  "vacuum_entity_id":   str
  "map_id":             int
  "room_count":         int
  "estimated_at":       str           # ISO timestamp (UTC)
  "started_at":         str | None    # anchor for ETA math; None = pre-start
  "stats_stale":        bool          # True if last rebuild > 30 days ago
  "stats_rebuilt_at":   str | None
  # --- Timing ---
  "room_minutes_total": float
  "overhead_minutes":   float
  "overhead":           OverheadBreakdown
  "total_minutes":      float
  "job_eta_minutes":    float         # alias of total_minutes
  "job_eta_at":         str           # ISO timestamp
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
  "can_run_now":     bool              # False only on "no_payload" error; battery never blocks
  "battery_warning": bool
  # --- Job-level confidence (min of all room scores) ---
  "confidence_score":     float        # 0.0–1.0
  "confidence_label":     str          # "high" | "medium" | "low"
  "confidence_breakpoint": ConfidenceBreakpoint
  # --- Room-level breakdown ---
  "breakdown":     list[RoomTimelineEntry]   # alias of room_timeline
  "room_timeline": list[RoomTimelineEntry]
  # --- Debug ---
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
  "transition_minutes": float   # 0.75 min * (room_count - 1)
  "recharge_minutes":   float   # total_battery_estimate * 0.05
  "mop_wash_minutes":   float   # wash_cycle_count * 1.5 min
  "dust_empty_minutes": float   # (room_minutes_total / 10) * 0.3
  "return_minutes":     float   # fixed 1.0 min
  "mop_wash": {
    "mode":               str    # "by_time" | "by_room" | "off" | "unknown"
    "mode_entity_id":     str
    "interval_entity_id": str
    "interval_minutes":   float  # clamped to [15.0, 25.0]
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

One entry in `room_timeline`. The estimator produces a fixed shape; `reanchor_timeline` enriches it with actuals.

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
  "minutes":               float  # estimated room duration
  "battery":               float  # estimated battery usage
  "start_offset_minutes":  float
  "end_offset_minutes":    float
  "eta_minutes_from_start": float
  "eta_at":                str    # ISO timestamp
  "completed":             bool
  "current":               bool
  "remaining":             bool
  "skipped":               bool
  "progress_percent":      int    # 0 or 100
  "elapsed_minutes":       float
  "remaining_minutes":     float
  "learning_velocity": {
    "runs_to_medium": int
    "runs_to_high":   int
    "current_tier":   str   # "high" | "medium" | "low"
  }
  "confidence_score":      float
  "confidence_label":      str
  "confidence_breakpoint": ConfidenceBreakpoint
}
```

**After `reanchor_timeline` enrichment**, completed rooms gain:

```
  "actual_duration_minutes": float
  "reanchored":              bool
```

Remaining (not-yet-completed) rooms also get `"reanchored": True`.

### Confidence scoring model

| Component | Value |
|---|---|
| Base score (learned match) | 0.55 |
| Base score (default fallback) | 0.20 |
| Sample bonus (max) | +0.25 at 10 samples |
| Variance penalty (max) | -0.25 when CV ≥ 0.5 |
| Intensity mismatch penalty | -0.15 |
| Accuracy penalty (max) | -0.20 when mean abs % error ≥ 0.20 |

Job confidence = `min(all room scores)`. This is a hard architectural rule — the weakest room drives the job estimate.

---

## 8. Room Bounds

Room bounds are derived from completed single-room runs via `_auto_derive_room_boundary` in `learning/job_finalizer.py`. At the time of writing, boundary derivation is inactive (the method returns `None` unconditionally after logging a debug message). No stored shape is currently defined.

When derivation is active, eligibility gates are:
- `outcome_status == "completed"` and `was_cancelled == False`
- Exactly one resolved room with a valid `room_id`
- `trace_run_id` present

Boundary data, when implemented, will be written to the `eufy_vacuum/learning/mapping/{vacuum_slug}/` directory.

---

## 9. Theme Object

### `ThemeEntry` (library entry)

Stored at `data["theme"]["library"][theme_id]`. Defined in `models/models.py`.

```
{
  "id":     str
  "name":   str
  "tokens": dict    # str → Any; includes all color token aliases plus layout/motion tokens
  "colors": dict    # str → str; CSS custom property names (e.g. "--evcc-accent") → hex/rgba values
  "alpha":  dict    # str → float; named opacity values 0.0–1.0
}
```

**Invariant:** `tokens` is a superset of `colors` — it contains all color keys plus non-color design tokens (spacing, typography, animation, etc.). When building a theme entry via `_build_preloaded_theme_entry`, token values are merged as `{**colors, **tokens}`.

**Built-in theme IDs:** `"theme_follow_ha"`, `"theme_core_slate"`, `"theme_forest_night"`, `"theme_soft_carbon"`, `"theme_warm_light"`, `"theme_high_contrast"`, `"theme_signal"`. These are seeded on every boot and never replaced if already present.

### `ThemeDraft` (working draft)

Stored at `data["theme"]["vacuums"][vacuum_entity_id]["working_draft"]`. Defined in `models/models.py`.

```
{
  "tokens": dict    # str → Any; only overridden keys
  "colors": dict    # str → str; only overridden keys
  "alpha":  dict    # str → float; only overridden keys
}
```

At read time, the draft is merged on top of the active theme entry. Only keys explicitly overridden by the user are present — unset keys inherit from the active theme.

### `ThemeVacuumState` (per-vacuum)

Stored at `data["theme"]["vacuums"][vacuum_entity_id]`. Defined in `models/models.py`.

```
{
  "active_theme_id": str | None   # points into library; None = no theme selected
  "working_draft":   ThemeDraft
  "draft_dirty":     bool         # True when working_draft differs from the saved entry
  "editor_mode":     str          # always "live"
}
```

### Design token CSS custom properties

All theme token keys follow the `--evcc-*` naming convention. The full set is defined by `_build_release_theme_colors` and `_build_release_theme_tokens` in `core/manager.py`. Key groups:

| Group | Prefix | Examples |
|---|---|---|
| Semantic colors | `--evcc-sem-*` | `--evcc-sem-success`, `--evcc-sem-warning`, `--evcc-sem-error`, `--evcc-sem-info` |
| Surface layers | `--evcc-surface-*` | `--evcc-surface-base`, `--evcc-surface-panel`, `--evcc-surface-raised`, `--evcc-surface-input`, `--evcc-surface-overlay` |
| Text | `--evcc-text-*` | `--evcc-text-primary`, `--evcc-text-secondary`, `--evcc-text-muted` |
| Borders | `--evcc-border-*` | `--evcc-border-subtle`, `--evcc-border-default`, `--evcc-border-strong` |
| Chips | `--evcc-chip-*` | sizing, color states |
| Queue chips | `--evcc-queue-*` | completed, current, pending, skipped states |
| Confidence | `--evcc-confidence-*` / `--evcc-conf-*` | high, medium, low variants |
| Learning | `--evcc-learning-*` | confidence gradients, chip typography |
| Modal | `--evcc-modal-*` | backdrop, padding, radius |
| Layout | various | `--evcc-gap`, `--evcc-radius-card`, `--evcc-font-family`, etc. |

---

## 10. Incomplete Run Log

Written by `_write_incomplete_run_log` in `learning/job_finalizer.py`.  
Path: `eufy_vacuum/learning/{vacuum_slug}/live/incomplete_run.json`  
Single-overwrite file — only the most recent incomplete run is kept.  
Written only for `outcome_status` in `{"cancelled", "failed", "interrupted"}`.  
Cleared when a job completes normally or when `retry_missed_rooms` dispatches a retry.

```
{
  "schema_version":     int          # always 1
  "record_type":        str          # always "incomplete_run_log"
  "vacuum_entity_id":   str
  "job_id":             str
  "map_id":             str
  "outcome_status":     str          # "cancelled" | "failed" | "interrupted"
  "ended_at":           str          # ISO timestamp
  "queued_room_ids":    list[int]    # all rooms that were queued
  "completed_room_ids": list[int]    # rooms confirmed cleaned (from active_job.completed_room_ids)
  "missed_room_ids":    list[int]    # sorted; set difference of queued minus completed
  "missed_rooms": [
    {
      "room_id": int
      "name":    str    # from resolved_rooms; falls back to "Room {room_id}"
    }
  ]
  "logged_at":          str          # ISO timestamp of when the log was written
}
```

**Invariant:** `missed_room_ids` == `sorted(set(queued_room_ids) - set(completed_room_ids))`.

---

## 11. Trouble Rooms Log

Written and updated by `_update_trouble_rooms_log` in `learning/job_finalizer.py` after every job finalization.  
Path: `eufy_vacuum/learning/{vacuum_slug}/live/trouble_rooms.json`  
Single-overwrite file updated in place after every run.

A room is flagged `is_trouble` when `miss_count >= 2` AND `miss_rate >= 0.33`.

```
{
  "schema_version":   int    # always 1
  "record_type":      str    # always "trouble_rooms_log"
  "vacuum_entity_id": str
  "updated_at":       str    # ISO timestamp
  "rooms":            dict[room_id_str, TroubleRoomEntry]
}
```

### `TroubleRoomEntry`

Keyed by `str(room_id)` in the `rooms` dict.

```
{
  "room_id":         int
  "name":            str      # from resolved_rooms; updated on every run
  "run_count":       int      # total times queued across all runs
  "miss_count":      int      # total times missed
  "miss_rate":       float    # miss_count / run_count, rounded to 3 decimal places
  "is_trouble":      bool     # True when miss_count >= 2 AND miss_rate >= 0.33
  "last_cleaned_at": str      # ISO timestamp; present when last run included this room
  "last_missed_at":  str      # ISO timestamp; present when last run missed this room
}
```

**Note:** For a completed job (`outcome_status == "completed"`), all queued rooms are treated as completed — `active_completed` is set to `queued_room_ids` directly. For non-completed jobs, `active_completed` comes from `active_job_state["completed_room_ids"]`.
