# Setup System — Developer Reference

> **Scope:** Complete implementation reference for the `setup/` package: `workflow.py` (add_vacuum / import_active_map), `drift.py` (step tracking + room drift), `status.py` (setup status response), `protection.py` (delete protection evaluation), and `delete.py` (protected map delete). Every ActionResult shape, protection level rule, drift predicate, and storage path is derived directly from the source.

---

## 1. Overview

The setup system manages the multi-step onboarding flow for adding new vacuums and importing their maps. It is **data-driven** — each adapter declares which setup steps apply to it. The framework iterates those steps and tracks completion state, rather than hard-coding an Eufy-specific flow.

**Module roles:**

| Module | Role |
|---|---|
| `setup/workflow.py` | `add_vacuum()` and `import_active_map()` — the two atomic setup actions |
| `setup/drift.py` | Setup step tracking, room drift detection, discovery-history counters |
| `setup/status.py` | `get_setup_status()` — composite status response for panel rendering |
| `setup/protection.py` | `evaluate_map_protection()` — protection level for destructive operations |
| `setup/delete.py` | `delete_map()` — protected map delete workflow |

---

## 2. ActionResult Schema

Every public function in `workflow.py` and `delete.py` returns an `ActionResult` dict:

```python
{
    "status":       str,          # "success" | "already_done" | "blocked" | "error" | "requires_confirmation"
    "message":      str,          # human-readable description
    "data":         dict,         # operation-specific payload
    "next_actions": list[str],    # suggested follow-up actions (e.g. ["import_active_map"])
}
```

`delete.py` extends this with:
```python
{
    ...base fields...
    "code":     str,              # machine-readable reason code
    "warnings": list[str],        # non-fatal notices (e.g. "no maps remain")
}
```

---

## 3. Setup Workflow (`workflow.py`)

### 3.1 `add_vacuum`

```python
async def add_vacuum(hass, vacuum_entity_id) -> ActionResult
```

**Pre-conditions checked:**
1. Manager is available — returns `"error"` if not.
2. Vacuum entity exists in HA state machine — returns `"blocked"` if not.
3. Vacuum is not already managed — returns `"already_done"` with `next_actions=["import_active_map"]` if it is.

**On success:**
1. Calls `manager.ensure_vacuum_record(vacuum_entity_id)`.
2. Registers a per-vacuum sidebar panel at `/eufy-vacuum-{object_id}` via `panel_custom.async_register_panel()`. The panel is registered with `config={"vacuum_entity_id": vacuum_entity_id}`.
3. Calls `manager.async_save()`.

Returns `"success"` with `next_actions=["import_active_map"]`.

### 3.2 `import_active_map`

```python
async def import_active_map(hass, vacuum_entity_id) -> ActionResult
```

**Pre-conditions checked:**
1. Manager is available.
2. Vacuum is already managed — returns `"blocked"` with `next_actions=["add_vacuum"]` if not.
3. Active map ID is detectable — returns `"blocked"` if `get_active_map_id()` returns `None`.
4. Map is not already imported with rooms — returns `"already_done"` if `data["maps"][vacuum][map_id]["rooms"]` is non-empty.

**On success:**
1. Calls `discover_rooms_for_vacuum()` — returns `"blocked"` if no rooms found.
2. Caches raw discovery in `data["discovery"][vacuum][str(map_id)]`.
3. Calls `manager.save_managed_rooms(vacuum_entity_id, map_id, enabled_room_ids=None, floor_types={})` — all rooms enabled by default, floor types assigned hardwood defaults.
4. Calls `manager.async_save()`.

Returns `"success"` with room list in `data` and `next_actions=["configure_rooms"]`.

**Upstream constraint:** Only the currently active map can be imported. This is a hard limitation of the upstream cloud API — there is no way to query alternate maps.

---

## 4. Setup Step Tracking (`drift.py`)

### 4.1 Setup step IDs

```python
SETUP_STEP_IDS: frozenset = frozenset({
    "add_vacuum",
    "import_active_map",
    "save_rooms",
    "calibrate_map",        # future
    "set_dock_position",    # future
})
```

### 4.2 Step labels and services

| Step ID | Label | Service called |
|---|---|---|
| `add_vacuum` | Add vacuum | `eufy_vacuum.setup_add_vacuum` |
| `import_active_map` | Import active map | `eufy_vacuum.setup_import_active_map` |
| `save_rooms` | Configure rooms | `eufy_vacuum.setup_save_rooms` |
| `calibrate_map` | Calibrate map | `eufy_vacuum.calibrate_map` |
| `set_dock_position` | Set dock position | `eufy_vacuum.set_dock_anchor` |

### 4.3 Step completion storage

```
data["setup_progress"][vacuum_entity_id] = {
    "completed_steps":    list[str],   # step IDs that have been marked complete
    "last_advanced_at":   str | None,  # ISO timestamp of last step completion
    "rejected_rooms":     list[int],   # room IDs explicitly rejected by user
    "room_drift_history": dict,        # per-room discovery-pass counters
}
```

```python
record_step_completed(manager, vacuum_entity_id, step_id) -> None
is_step_completed(progress, step_id) -> bool
```

`record_step_completed` is idempotent — repeated calls do not duplicate the step in the list.

### 4.4 Adapter-declared steps

```python
get_adapter_setup_steps(vacuum_entity_id) -> list[str]
```

Reads `adapter_config["setup"]["steps"]`, filters out unknown step IDs (defence in depth), and returns the filtered list. Falls back to `["add_vacuum", "save_rooms"]` if the adapter omits the `setup` block.

### 4.5 Room drift detection

Drift = difference between the rooms the adapter currently reports and the rooms the integration has configured.

**Discovery cadence** (with defaults):

| Adapter key | Default |
|---|---|
| `discovery.removal_confirmation_passes` | 3 |
| `discovery.new_room_confirmation_passes` | 1 |
| `discovery.auto_refresh_interval_seconds` | 21600 (6 hours) |
| `discovery.auto_refresh_on` | `["vacuum_docked", "active_map_changed", "config_entry_reload"]` |

**`update_drift_history(manager, vacuum_entity_id, discovered_room_ids)`**

Called on every discovery pass. For each room in `(configured_ids | discovered_ids) - rejected_ids`:

- If room is in `discovered_room_ids`: increment `seen_passes`, reset `missing_passes` to 0, update `last_seen_at`.
- If room is NOT in `discovered_room_ids`: increment `missing_passes`, set `first_missed_at` if first miss.

Stale history entries (rooms neither configured nor currently discovered) are cleaned up to prevent unbounded growth.

**`compute_room_drift(manager, vacuum_entity_id, discovered_room_ids=None) -> dict`**

```python
{
    "in_sync":             bool,
    "new_rooms":           [{room_id, name, map_id}, ...],
    "removed_rooms":       [{room_id, name, map_id}, ...],
    "transiently_missing": [{room_id, name, map_id}, ...],
    "rejected_rooms":      [room_id, ...],
}
```

**New rooms:** discovered but not configured, `seen_passes >= new_room_confirmation_passes` (default 1 = immediate).

**Removed rooms:** configured but `missing_passes >= removal_confirmation_passes` (default 3).

**Transiently missing:** configured and currently absent but below removal threshold.

`in_sync = True` when new_rooms, removed_rooms, and transiently_missing are all empty.

### 4.6 Additional drift operations

```python
reject_rooms(manager, vacuum_entity_id, room_ids: list[int]) -> dict
```
Moves room IDs into `rejected_rooms`. Removes them from managed_rooms across all maps. Drops their drift history entries. Returns `{rejected, removed_from_managed, affected_map_ids}`.

```python
force_remove_room(manager, vacuum_entity_id, room_id: int) -> dict
```
Bypasses the missing-pass counter — immediately sets `missing_passes = removal_confirmation_passes` for the room. Used for the "I know this room is gone" manual action.

```python
run_discovery_pass(hass, manager, vacuum_entity_id) -> dict
```
Runs a live discovery probe, calls `update_drift_history()`, and returns `{vacuum_entity_id, discovered_room_ids, updated_at}`.

---

## 5. Setup Status (`status.py`)

```python
get_setup_status(hass) -> dict
```

Called by the panel on load. Returns:

```python
{
    # New data-driven fields
    "setup_complete": bool,
    "vacuums": [
        {
            "vacuum_entity_id": str,
            "display_name":     str,
            "setup_steps": [
                {"id", "label", "completed", "service"},
                ...
            ],
            "next_step":   str | None,   # first incomplete step ID
            "room_drift":  dict,         # compute_room_drift() result (no live probe)
            "maps":        list[dict],   # per-map summaries with protection info
            # Legacy backward-compat:
            "has_imported_map": bool,
        },
        ...
    ],
    # Legacy backward-compat:
    "state":        "no_vacuums" | "no_map" | "ready",
    "next_actions": list[str],
}
```

**`setup_complete`:** `True` only when all vacuums have all steps completed AND all maps are in_sync.

**Drift probe:** `compute_room_drift()` is called **without** a live discovery probe — reflects the latest stored history. Discovery passes update history out-of-band via listener triggers.

**Maps list:** Each entry includes a `protection` sub-dict from `evaluate_map_protection()` for imported maps.

---

## 6. Delete Protection (`protection.py`)

```python
evaluate_map_protection(manager, *, vacuum_entity_id, map_id) -> dict
```

Returns:

```python
{
    "protection_level":            "normal" | "elevated" | "high",
    "reasons": [{"code": str, "message": str}, ...],
    "requires_typed_confirmation": bool,
    "typed_confirmation_value":    str,   # map display name
}
```

**Reason codes checked (in order):**

| Code | Condition |
|---|---|
| `only_map` | This is the only imported map for this vacuum |
| `has_active_job` | An active job has been observed on this map |
| `has_learning_data` | `data["room_history"][vacuum][map_id]` is non-empty |
| `has_rules` | Any room on the map has automation rules |
| `has_access_graph` | Any room has `grants_access_to` populated |

**Protection level derivation:**

```
if "has_active_job" in reason_codes: → "high"
elif len(reasons) >= 2:              → "high"
elif len(reasons) == 1:              → "elevated"
else:                                → "normal"

requires_typed_confirmation = (level == "high")
typed_confirmation_value    = map display name (from metadata.display_name or "Map {map_id}")
```

---

## 7. Protected Map Delete (`delete.py`)

```python
async def delete_map(hass, *, vacuum_entity_id, map_id, confirmation_token=None) -> ActionResult
```

**Protection gate:**
- `"high"` protection: `confirmation_token` must be provided and must exactly match `typed_confirmation_value` (map display name). Returns `"requires_confirmation"` if token absent; `"blocked"` if token mismatches.
- `"elevated"` protection: any truthy `confirmation_token` accepted (one-click confirm). Returns `"requires_confirmation"` if token absent.
- `"normal"` protection: proceeds without confirmation.

**On confirmed delete:**
1. `manager.remove_map(vacuum_entity_id, map_id_str)` — removes all data for the map.
2. `manager._notify_rooms_updated(vacuum, map_id)` — triggers entity-platform cleanup.
3. `manager._notify_run_profiles_updated(vacuum, map_id)` — triggers run-profile cleanup.
4. Entity registry sweep: removes any `eufy_vacuum`-platform entities whose `unique_id` starts with `{vacuum_object_id}_{map_id}_` to catch stragglers missed by platform teardown callbacks.
5. `manager.async_save()`.

Returns `"success"` with `warnings=["no maps remain"]` if the vacuum now has no imported maps.

---

## 8. Storage Path Reference

| Path | Description |
|---|---|
| `data["setup_progress"][vacuum_entity_id]["completed_steps"]` | List of completed step IDs |
| `data["setup_progress"][vacuum_entity_id]["room_drift_history"][str(room_id)]` | Per-room discovery-pass counters |
| `data["setup_progress"][vacuum_entity_id]["rejected_rooms"]` | Room IDs the user has explicitly rejected |
| `data["vacuums"][vacuum_entity_id]` | Vacuum record (created by `ensure_vacuum_record`) |
| `data["maps"][vacuum_entity_id][str(map_id)]` | Map bucket (created by `import_active_map`) |
| `data["discovery"][vacuum_entity_id][str(map_id)]` | Raw discovery cache |
