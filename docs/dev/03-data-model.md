# Data Model Reference

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
}
```

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

```
{
  "map_id":   str                                    # string form of the numeric map ID
  "metadata": MapMetadata
  "rooms":    dict[room_id_str, RoomRecord]          # {} until rooms are configured
  "summary":  RoomSelectionSummary                   # rebuilt by build_room_selection_summary
}
```

`room_id_str` keys inside `"rooms"` are always strings (e.g. `"3"`), even
though `room_id` values on the room dict itself are integers.

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
segmented into a **pending review record** under `learning/<slug>/external_jobs/`
(peer to `jobs/`); a confirmed run graduates to a normal `jobs/ext-<id>.json`
record tagged `origin: "external"`. See
[28-external-run-ingestion](28-external-run-ingestion.md).

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

---

## 6. Profiles

### 6a. Room profiles

Custom room profiles are stored at `data["profiles"]["room_profiles"]`.
Built-in profiles (e.g. `"vacuum_quick"`, `"mop_light"`) are compiled at
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
evaluation. One entry per room, per map, per vacuum.

```
{
  "last_result":        str          # see values below
  "blocked_by":         list[str]    # rule labels / IDs that triggered blockers
  "modifiers_applied":  list[dict]   # applied modifier effects (changes dicts)
  "reason":             str | None   # human-readable reason string for blocked rooms
  "evaluated_at":       str          # ISO timestamp
}
```

### `last_result` values

| Value | Meaning |
|---|---|
| `"pass"` | Room passed all rules; no changes |
| `"blocked"` | At least one blocker rule fired; room excluded from job |
| `"modified"` | At least one modifier rule fired; room settings changed |
| `"not_evaluated"` | Room was not in the evaluation set (disabled, not queued) |

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
  "completed":             bool
  "current":               bool
  "remaining":             bool
  "skipped":               bool
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
  "room_drift_history": dict[room_id_str, list[DriftHistoryEntry]]
}
```

**Step IDs** (constants in `setup/drift.py`): `"add_vacuum"`,
`"import_active_map"`, `"save_rooms"`.

**Migration:** `_migrate_setup_progress()` in `core/manager.py` stamps all
three legacy steps complete for any vacuum that already had managed rooms
before the state machine was introduced.

### `DriftHistoryEntry`

```
{
  "detected_at":   str    # ISO timestamp
  "drift_type":    str    # "new_room" | "missing_room" | "name_change"
  "room_id":       int
  "old_name":      str | None
  "new_name":      str | None
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
