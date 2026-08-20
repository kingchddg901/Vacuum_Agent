# 15 — Setup System

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
    "warnings": list[str],        # non-fatal notices (e.g. "This vacuum now has no imported maps.")
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

**On success (in order):**
1. Calls `manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)`.
2. Calls `manager.async_save()`.
3. Registers a per-vacuum sidebar panel at `/eufy-vacuum-{object_id}` via `panels.async_register_vacuum_panel(hass, vacuum_entity_id, title=effective_panel_title(record))`. The panel is registered with `config={"vacuum_entity_id": vacuum_entity_id}` and a per-vacuum sidebar title — `effective_panel_title(record)` returns the vacuum record's `panel_title` field when set, else the `"Vacuum Agent"` default — so two vacuums no longer show two identical sidebar entries once renamed. A `ValueError` (panel already registered) is caught and logged, and the url is still returned.
4. Appends the returned panel url to the config entry's teardown ledger via `panels.append_to_panel_ledger(hass, entry_id, panel_url)` (RP-039/RF-16 — the singleton domain's first/only entry is the owning entry). Without this, a panel registered mid-session (outside `async_setup_entry`'s own ledgering) was untracked and never cleanly removed by `async_unload_entry`.

The sidebar title is live-renamable via the `eufy_vacuum.setup_set_panel_title` service: it stores `panel_title` on the vacuum record (a blank title reverts to the default), persists it, then re-registers the panel with `replace=True` (which removes the existing panel first, since `panel_custom.async_register_panel` raises on a duplicate url) so the sidebar entry renames without a restart.

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
1. Calls `await async_refresh_room_source(hass, vacuum_entity_id)` **before** discovery. This is a no-op for attribute brands (Eufy, where rooms live in an entity attribute the sync discovery already reads), but for service-response brands (Roborock, where rooms come from the `get_maps` cloud response) it populates the `get_maps` cache that the sync discovery reads — without this step the Roborock import returns no rooms.
2. Calls `discover_rooms_for_vacuum()` — returns `"blocked"` if no rooms found.
3. Caches raw discovery in `data["discovery"][vacuum][str(map_id)]`.
4. Calls `manager.save_managed_rooms(vacuum_entity_id, map_id, enabled_room_ids=None, floor_types={})` — all rooms enabled by default, floor types assigned hardwood defaults.
5. Calls `manager.async_save()`.

Returns `"success"` with `next_actions=["configure_rooms"]`. Exact serialized shapes:

```python
# discovery cache — data["discovery"][vacuum][str(map_id)]:
{"vacuum_entity_id": str, "active_map_id": map_id, "room_count": int,
 "rooms": [ {"room_id": int, "map_id": str, "name": str, "slug": str}, ... ]}  # 4-field discovery dicts

# success ActionResult data:
{"vacuum_entity_id": str, "map_id": <as-detected>, "room_count": int,
 "rooms": [ {"room_id": int, "name": str}, ... ]}   # 2-field (NOT the 4-field discovery dict)

# already_done data (map already imported with rooms):
{"vacuum_entity_id": str, "map_id": str, "room_count": int}
```

**Upstream constraint:** Only the currently active map can be imported. This is a hard limitation of the upstream cloud API — there is no way to query alternate maps.

> **See also:** `save_managed_rooms()` (`rooms/room_crud.py`) is what import calls at step 4 — it runs `ensure_map_bucket()` ([17-map-manager](17-map-manager.md) §3) **+ `build_managed_rooms()` + `build_room_selection_summary()`** ([08-rooms-system](08-rooms-system.md) §5/§6). It does **not** call `rebuild_map_bucket()` — that runs only on the `rebuild_map` service/backfill path, never during import. `build_managed_rooms` is where every imported room is stamped `is_configured=True` / `configured_at` (§4.7).

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
    "completed_steps":       list[str],   # step IDs that have been marked complete
    "last_advanced_at":      str | None,  # ISO timestamp of last step completion
    "rejected_rooms":        list[int],   # LEGACY flat, vacuum-wide rejection list — read-only from now on (§4.6)
    "rejected_rooms_by_map": dict,        # {str(map_id): list[int]} — every rejection written from now on (§4.6)
    "room_drift_history":    dict,        # {str(room_id): entry} — entry schema in §4.5
}
```

`_get_progress_record` (`drift.py`) creates this record with the 4-key
literal above minus `rejected_rooms_by_map` on first touch, then
unconditionally `setdefault`s `room_drift_history`, `rejected_rooms`,
`rejected_rooms_by_map`, and `completed_steps` — so every record this helper
returns carries **5 keys** (`rejected_rooms_by_map` included), whether freshly
created or an older record being read back. **Divergent writer:**
`_migrate_setup_progress` (§4.7) writes directly (bypassing
`_get_progress_record`) a **6-key** variant that adds `"migrated_at": str`
(ISO) — present *only* on records backfilled for a legacy install.
(`migrated_at` is currently write-only — no reader — see code-flag CS-1.)

```python
record_step_completed(manager, vacuum_entity_id, step_id) -> None
is_step_completed(progress, step_id) -> bool
```

`record_step_completed` is idempotent — repeated calls do not duplicate the step in the list; it no-ops for a `step_id` not in `SETUP_STEP_IDS`, and stamps `last_advanced_at = _iso_now()`.

### 4.4 Adapter-declared steps

```python
get_adapter_setup_steps(vacuum_entity_id) -> list[str]
```

Reads `adapter_config["setup"]["steps"]`, filters out unknown step IDs (defence in depth — keeps only IDs in `SETUP_STEP_IDS`), and returns the filtered list. The `["add_vacuum", "save_rooms"]` fallback fires **only when `steps` is absent/empty** (`not declared`); a `steps` list containing *only* unknown IDs returns `[]`, not the default.

### 4.5 Room drift detection

Drift = difference between the rooms the adapter currently reports and the rooms the integration has **configured** — where "configured" means the room's `is_configured` flag is truthy (`_list_configured_room_ids`; the flag's provenance is §4.7). Rejected rooms (§4.6) are excluded from every set.

**Discovery cadence** — `get_discovery_cadence(vacuum_entity_id) -> dict` reads `adapter_config["discovery"]` with these defaults:

| Adapter key | Default | Coercion |
|---|---|---|
| `discovery.removal_confirmation_passes` | 3 | `max(1, int(...))` behind an `is not None` guard — an explicit low value is honored; `0`/negative clamps to **1** |
| `discovery.new_room_confirmation_passes` | 1 | same — `max(1, int(...))`, `is not None` guard |
| `discovery.auto_refresh_interval_seconds` | 21600 (6h) | `int(...)` behind an `is not None` guard — `0` is preserved |
| `discovery.auto_refresh_on` | `["vacuum_docked", "active_map_changed", "config_entry_reload"]` | `list(...)` behind an `is not None` guard (DR-SETUP-2, matching the other keys) — an adapter declaring `auto_refresh_on: []` to wire NO auto-discovery triggers is honored rather than silently reverted to the default |

The two pass-count keys are **floored at 1**: a literal `0` would make `missing_passes >= n_remove` a tautology (every configured room flagged removed, even present ones), so `0`/negative means "as aggressive as valid" = 1, not the surprising default. (This was code-flag CS-2 — the old `or` coercion silently reverted a configured `0` to the default; fixed + regression-tested DR-15.)

**Drift-history entry schema** — each `room_drift_history[str(room_id)]` value is a fixed **5-field** dict (created by `update_drift_history` / `force_remove_room`):

```python
{"missing_passes": int,        # consecutive discovery passes this room was absent
 "seen_passes":    int,        # consecutive passes it was present (resets to 0 on a miss)
 "last_seen_at":   str | None, # ISO of the most recent sighting
 "first_missed_at":str | None, # ISO when the current miss-streak began (cleared on sighting)
 "first_seen_at":  str | None} # ISO of the first-ever sighting (set once, never cleared)
```

**`update_drift_history(manager, vacuum_entity_id, discovered_room_ids: set[int], map_id: str | None = None)`** — called on every discovery pass. `map_id` is the map `discovered_room_ids` was read from — it selects which rejections apply (A4-SETUP-6, §4.6): the live room list always describes whichever map is currently loaded, so a real pass always has one; omitting it falls back to the union of every map's rejections (the pre-A4-SETUP-6 behaviour, and what a single-map install has always seen). For each room in `(configured_ids | discovered_ids) - rejected_ids` (`rejected_ids` resolved for that `map_id`):

- **Sighted** (in `discovered_room_ids`): set `first_seen_at` if `None`; `seen_passes += 1`; `missing_passes = 0`; `last_seen_at = now`; **`first_missed_at = None`** (clear the miss-streak).
- **Missed** (not in `discovered_room_ids`): `missing_passes += 1`; set `first_missed_at` if `None`; **`seen_passes = 0`** (the sighting streak restarts — load-bearing for the `seen_passes >= n_new` new-room gate).

Stale entries (rooms not in the relevant set) are then pruned to prevent unbounded growth.

**`compute_room_drift(manager, vacuum_entity_id, discovered_room_ids: set[int] | None = None, map_id: str | None = None) -> dict`** — `map_id` scopes which rejections apply (A4-SETUP-6, same contract as `update_drift_history` above); omitted, the snapshot unions every map's rejections, which is the right answer for a whole-vacuum status read not scoped to one map.

```python
{
    "in_sync":             bool,
    "new_rooms":           [{room_id, name, map_id}, ...],   # sorted by room_id
    "removed_rooms":       [{room_id, name, map_id}, ...],
    "transiently_missing": [{room_id, name, map_id}, ...],
    "rejected_rooms":      [room_id, ...],                   # sorted
}
```

**Removed rooms** (both branches): configured rooms whose `missing_passes >= removal_confirmation_passes` (default 3).

The `new_rooms` / `transiently_missing` derivation has **two branches** — and the panel status path (§5) always hits the **history-only** one because `status.py` calls this with `discovered_room_ids=None`:

- **Live branch** (`discovered_room_ids` provided): `new` = `(discovered - configured - rejected)` with `seen_passes >= n_new` **OR `n_new <= 1`** (the default `n_new=1` surfaces a candidate immediately, even at `seen_passes == 0`); `transiently_missing` = `configured - discovered - confirmed_removed`.
- **History-only branch** (`discovered_room_ids is None`): `new` = rooms in history with `seen_passes >= n_new` **and** `missing_passes == 0` **and** not configured **and** not rejected; `transiently_missing` = configured rooms with `missing_passes > 0` and not confirmed-removed.

`in_sync = True` when `new_rooms`, `removed_rooms`, and `transiently_missing` are all empty. Each enrichment falls back to `{room_id, name: "Room {id}", map_id: ""}` for an id missing from the room lookup.

### 4.6 Additional drift operations

**Rejection is MAP-SCOPED (A4-SETUP-6).** Eufy reissues room ids 1..N from
scratch on every map, so id 3 downstairs is a different physical room than id
3 upstairs. Rejecting a ghost id 3 on one map used to make the REAL id 3 on
another map unconfigurable — permanently and silently, since a rejected id
never surfaces in `new_rooms` for the user to notice. Two backings now exist,
deliberately:

- `rejected_rooms_by_map[str(map_id)]` — every rejection written from now on,
  scoped to its own map.
- `rejected_rooms` — the LEGACY flat list, applied to every map because the
  id genuinely carries no map and inventing one would be a guess. Read but
  never appended to again, so the ambiguity stops growing.

`rejected_room_ids(record, *, map_id=None, include_unscoped=True)` is the single
reader that resolves both backings together; `include_unscoped=False` (used
at the `save_managed_rooms` write boundary, §3.2) drops the legacy flat list —
an unattributable rejection may suppress a *suggestion*, but must never
*delete* a real, currently-configured room on a later map.

`_resolve_rejection_map(manager, vacuum_entity_id, map_id)` is what every
write path (`reject_rooms`, `unreject_rooms`) routes an omitted `map_id`
through — it never guesses "every map":

- **0 maps carrying rooms** → resolves to the single stored bucket if exactly
  one exists (still unambiguous), else `None` — nothing to scope to.
- **1 map carrying rooms** → resolves to that map, unambiguous.
- **2+ maps carrying rooms** → **refuses**, `{"status": "error", "reason":
  "map_ambiguous", "message": ..., "map_ids": [...]}`, naming the maps so the
  caller can re-issue with one. Writes nothing.

```python
reject_rooms(manager, vacuum_entity_id, room_ids: list[int], map_id: str | None = None) -> dict
# → {"rejected": [...], "removed_from_managed": [...], "affected_map_ids": [...], "map_id": str | None}
# or the map_ambiguous refusal above (writes nothing)
```
Moves room IDs into the rejected set for the resolved map. If they were
configured, also removes them from managed_rooms **on that map only** (their
HA entities get torn down by the platform-level room-update callbacks), and
drops their drift-history entries. `rejected` is the list of **newly-added**
ids from *this* call, not the cumulative rejected set. Callers should call
`manager._notify_rooms_updated` for each id in `affected_map_ids`.

```python
unreject_rooms(manager, vacuum_entity_id, room_ids: list[int], map_id: str | None = None) -> dict
# → {"unrejected": [...], "still_rejected_on": {map_id: [...]}, "map_id": str | None}
# or the map_ambiguous refusal (writes nothing)
```
Undoes a rejection so the room can be discovered and configured again — the
recovery path for a wrong `reject_rooms` call, previously impossible short of
hand-editing `.storage`. Clears the id from **both** backings: the per-map
list for the resolved `map_id`, and the legacy flat list (the flat entry is
the one that cannot say which map it meant, so it is the one blocking a real
room on a second floor — clearing it is the documented way out). The room
does not reappear instantly; it resurfaces on the next discovery pass through
the normal `new_rooms` confirmation cadence. `still_rejected_on` names any
*other* map that still rejects one of the given ids, so the caller doesn't
imply a clean sweep. `map_id` is subject to the same ambiguity refusal as
`reject_rooms` — an unqualified un-reject on a multi-map vacuum would clear
the vacuum-global legacy entry and un-hide the id on every floor at once, so
it refuses rather than guesses. No standalone service caller before
`setup_unreject_rooms` (§9) was added — undocumented until this audit.

```python
force_remove_room(manager, vacuum_entity_id, room_id: int) -> dict
# → {"room_id": int, "missing_passes": int, "threshold": int}
```
Bypasses the missing-pass counter — sets `missing_passes = max(existing, removal_confirmation_passes)` for the room (and `first_missed_at`/`seen_passes=0`), so the next `compute_room_drift` reports it removed without waiting. Does **not** delete the room from managed_rooms (learning data is retained). Used for the "I know this room is gone" manual action.

```python
run_discovery_pass(hass, manager, vacuum_entity_id) -> dict
# → {"vacuum_entity_id": str, "discovered_room_ids": list[int], "map_id": str | None, "updated_at": str}
```
Runs a live discovery probe, resolves the vacuum's active map id
(`manager.resolve_active_map_id`, best-effort — `None` if the adapter can't
name one), calls `update_drift_history(..., map_id=active_map_id)`, and
returns the result including `map_id` — the map this pass's ids belong to and
whose rejections applied.

### 4.7 Configured-room flags & legacy migration

Two per-room flags on the map-bucket room record — **not** in `setup_progress` — are the backbone of the setup state machine:

| Flag | Written by | Read by |
|---|---|---|
| `is_configured: bool` | `build_managed_rooms` stamps **`True`** for every room on any save (import + `setup_save_rooms`, `room_manager.py`); `_migrate_setup_progress` stamps `True` for legacy rooms lacking it | drift's "configured" set (`_list_configured_room_ids`, `active_map_configured`); the HA **entity-creation gate** `sort_room_items(..., configured_only=True)` — a room whose `is_configured` is not truthy gets **no entities** |
| `configured_at: str \| None` | `build_managed_rooms`: `existing_configured_at or _iso_now()` (preserved across re-saves); migration: `setdefault(now)` | display/audit only |

**Default-when-absent = unconfigured.** No writer other than `build_managed_rooms` and the migration ever `setdefault`s `is_configured`, so a room persisted by any other path reads unconfigured and is filtered out of entity creation — the same class as doc-08 **BUG-A** (`rebuild_map_bucket` carrying the flags forward) and code-flag CS-3.

**`_migrate_setup_progress(vacuum_entity_id)`** (`core/manager.py`, run once at load) backfills pre-state-machine installs: if a vacuum has **no** `setup_progress` entry but **has** map rooms, it writes the migrated 5-key record (§4.3: all three steps complete + `migrated_at`) and stamps `is_configured=True`/`configured_at` on every room that lacks `is_configured`. **Idempotent** via "skip if the vacuum is already in `setup_progress`." It is the *only* place legacy rooms become configured.

**`active_map_configured(manager, vacuum_entity_id) -> bool | None`** backs the **sticky `save_rooms` re-open** (§5): it returns whether the *active* map has ≥1 `is_configured` room. Tri-state — `None` when the active map can't be determined (adapter declares no `entities.active_map`, or the entity is unknown/unavailable), so callers leave the sticky flag alone; `False` when the active map has zero configured rooms (e.g. a factory reset / new map id against a stale completed flag); `True` otherwise.

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
            "panel_title":      str,          # current sidebar panel title (effective_panel_title) — user-set value or the "Vacuum Agent" default; pre-fills the Setup tab's rename field
            "live_map_image_entity": str | None,  # user's explicit live-map camera/image override, or None to use the adapter pattern; pre-selects the Setup-tab camera picker
            "setup_steps": [
                {"id", "label", "completed", "service"},
                ...
            ],
            "next_step":   str | None,   # first incomplete step ID
            "room_drift":  dict,         # compute_room_drift() result (no live probe)
            "reconciliation": {          # last-cached identity-shift reconciliation, or None
                "reviews":     list,     # review dicts (rooms/reconciliation.py) — id_changed /
                                          # renamed / renamed_and_renumbered shapes
                "has_changes": bool,
                "plan_token":  str,      # opaque; round-trips to reconcile_room, never parse
                "map_id":      str,      # the vacuum's active map this review was cached for
                "dismissed":   bool,     # optional, present only when a dismissal suppressed it
            } | None,
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

**`setup_complete`:** `True` only when there is **≥1 managed vacuum** AND all vacuums have all steps completed AND all maps are in_sync (`bool(managed) and …` — zero vacuums returns `False`, not vacuously `True`).

**`next_step` and the sticky `save_rooms` re-open.** `next_step` is the first incomplete step ID — but a *completed* `save_rooms` is flipped back to incomplete when `active_map_configured(...)` returns **`False`** (§4.7: the active map has no configured rooms, e.g. after a factory reset / new map id). `None` (active map indeterminate) leaves the sticky flag set. So `next_step` can point back at `save_rooms` even though it was completed earlier.

**Drift probe:** `compute_room_drift()` is called **without** a live discovery probe, scoped to the vacuum's currently-resolved active map (`resolve_active_map_id`, A4-SETUP-6 — leaving the map unset here would filter `new_rooms` by the union of every map's rejections, so a room rejected downstairs would never be offered upstairs) — reflects the latest stored history. Discovery passes update history out-of-band via listener triggers.

**Reconciliation (CARD-7/RP-019):** `reconciliation` is a **passive read only** — it never calls `discover_rooms` or recomputes anything itself. It reads whatever `RoomMapManager.discover_rooms` already cached at `data["discovery"][vacuum][map_id]["reconciliation"]` the last time discovery actually ran for the vacuum's currently-active map (`get_active_map_id`), same "as of the last pass" contract as `room_drift` above. Opening or polling Setup never itself triggers a new discovery pass. `None` when the active map can't be resolved or nothing has been cached yet.

**Maps list:** Each entry carries `map_id` (str), `display_name` (`str | None`), `room_count` (int), `imported` (bool), and a `protection` sub-dict from `evaluate_map_protection()` for imported maps. `display_name` is the raw stored name or **`None`** when the map is unnamed — `status.py` no longer fabricates an English `"Map {map_id}"`; the **card** renders the localized `setup.map_n` ("Map {id}") fallback.

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
    "requires_typed_confirmation": bool,        # True ONLY for a NAMED high map
    "requires_confirmation":       bool,        # one-click confirm (elevated, or an unnamed high map)
    "typed_confirmation_value":    str | None,  # the stored map name; None when the map is unnamed
}
```

**Reason codes checked (in order):**

| Code | Condition |
|---|---|
| `only_map` | This is the only imported map for this vacuum |
| `has_active_job` | `data["active_jobs"][vacuum][str(map_id)]["has_observed_active_lifecycle"]` is truthy (the flag lifecycle/`active_job` sets once a job has run) |
| `has_learning_data` | `data["room_history"][vacuum][map_id]` is non-empty |
| `has_rules` | Any room on the map has automation rules |
| `has_access_graph` | Any room has `grants_access_to` populated |

**Protection level derivation:**

```
if "has_active_job" in reason_codes: → "high"
elif len(reasons) >= 2:              → "high"
elif len(reasons) == 1:              → "elevated"
else:                                → "normal"

requires_typed_confirmation = (level == "high") and bool(stored_name)   # NAMED high maps only
requires_confirmation       = (level != "normal")                       # elevated, or an unnamed high map
typed_confirmation_value    = stored_name if requires_typed else None    # raw metadata.display_name
```

The backend **never fabricates** a `"Map {id}"` name. `stored_name` is `metadata.display_name` or `None`; an unnamed map keeps high-level friction via a one-click confirm rather than demanding a typed token it has no locale-invariant name for. The card renders the localized `setup.map_n` label when `display_name` is `None`.

---

## 7. Protected Map Delete (`delete.py`)

```python
async def delete_map(hass, *, vacuum_entity_id, map_id, confirmation_token=None) -> ActionResult
```

**Early guard:** manager unavailable → `status="error"`, `code="manager_unavailable"`. Bucket absent **or has no `rooms`** → `status="already_done"`, `code="map_not_found"` (nothing to delete).

The `code` field (delete's `ActionResult` extension, §2) takes one of: `manager_unavailable`, `map_not_found`, `typed_confirmation_required`, `confirmation_mismatch`, `confirmation_required`, `map_deleted`.

**Protection gate:**
- **NAMED `"high"` map** (`requires_typed_confirmation`): `confirmation_token` must be provided and match `typed_confirmation_value` (the stored map name — a locale-invariant token). The compare is **whitespace-stripped on both sides** (`token.strip() != (typed_value or "").strip()`), not byte-exact. Returns `"requires_confirmation"` (`code="typed_confirmation_required"`) if absent; `"blocked"` (`code="confirmation_mismatch"`) on mismatch.
- **UNNAMED `"high"` map, or any `"elevated"` map** (`requires_confirmation`, typed dropped): any truthy `confirmation_token` accepted (one-click confirm). Returns `"requires_confirmation"` if absent. An unnamed map has no locale-invariant name to type, so it drops to a one-click confirm rather than round-tripping a per-locale `"Map N"` token through the backend.
- `"normal"` protection: proceeds without confirmation.

`delete.py` uses a safe `display_label` (stored name or `"Map {id}"`) for response messages and log lines **only** — never as the wire token (which stays the raw stored name, non-`None` only when `requires_typed_confirmation`).

**On confirmed delete:**
1. The map's room ids are captured **before** the removal (needed to reconstruct ownership below, and the bucket is gone after step 2).
2. `manager.remove_map(vacuum_entity_id, map_id_str)` — removes all data for the map.
3. `manager._notify_rooms_updated(vacuum, map_id)` — triggers entity-platform cleanup.
4. `manager._notify_run_profiles_updated(vacuum, map_id)` — triggers run-profile cleanup.
5. **Entity registry sweep, by a CLOSED SET (RP-009/DR-SETUP-1)** — `unique_ids_for_map(vacuum_entity_id, map_id, room_ids)` forward-reconstructs the exact unique_ids this map's rooms would have owned, and only entities whose `unique_id` is in that set are removed. The registry is **never** swept by string prefix anymore: the old prefix scan (`{vacuum with '.'->'_'}_{map_id}_`) was proven to delete every entity of a *sibling* vacuum whose entity_id happened to be that prefix plus a suffix (e.g. deleting map "2" of `vacuum.alfred` swept all of `vacuum.alfred_2`'s entities). Entries the legacy prefix *would* have matched but the closed set does not are **enumerated and reported as `orphan_candidates`, never deleted** — pre-fix orphans (rooms removed before this repair) or an older id scheme cannot be safely re-derived, so what cannot be reconstructed is not destroyed.
6. `manager.async_save()`.

Returns `"success"` (`code="map_deleted"`) with:

```python
data = {
    "removed": <remove_map result>,
    "entities_removed": int,
    "orphan_candidates": [{"entity_id": str, "unique_id": str}, ...],  # matched the legacy
                                                                        # prefix but not the
                                                                        # closed set — left untouched
    "remaining_map_count": int,
}
next_actions = ["import_active_map"] if no maps remain else []
warnings = ["This vacuum now has no imported maps. Import a new map to resume cleaning."]  # only when none remain
```

---

## 8. Storage Path Reference

| Path | Description |
|---|---|
| `data["setup_progress"][vacuum_entity_id]["completed_steps"]` | List of completed step IDs |
| `data["setup_progress"][vacuum_entity_id]["last_advanced_at"]` | ISO of last step completion (or `None`) |
| `data["setup_progress"][vacuum_entity_id]["migrated_at"]` | ISO — **present only on migrated (legacy) records** (§4.3/§4.7); write-only (CS-1) |
| `data["setup_progress"][vacuum_entity_id]["room_drift_history"][str(room_id)]` | Per-room 5-field drift entry (`missing_passes`, `seen_passes`, `last_seen_at`, `first_missed_at`, `first_seen_at` — §4.5) |
| `data["setup_progress"][vacuum_entity_id]["rejected_rooms"]` | LEGACY flat, vacuum-wide rejected-room ids (read-only from now on) |
| `data["setup_progress"][vacuum_entity_id]["rejected_rooms_by_map"][str(map_id)]` | Room IDs rejected on that map (A4-SETUP-6, §4.6) — the current write target |
| `data["vacuums"][vacuum_entity_id]` | Vacuum record (created by `ensure_vacuum_record`); holds `panel_title`, `live_map_image_entity` |
| `data["maps"][vacuum_entity_id][str(map_id)]` | Map bucket (created by `import_active_map`) |
| `…[str(map_id)]["rooms"][str(room_id)]["is_configured"]` / `["configured_at"]` | Setup-approval flags (§4.7); gate entity creation + drift's "configured" set |
| `data["discovery"][vacuum_entity_id][str(map_id)]` | Raw discovery cache (`{vacuum_entity_id, active_map_id, room_count, rooms:[4-field]}` — §3.2) |
| `data["active_jobs"][vacuum_entity_id][str(map_id)]["has_observed_active_lifecycle"]` | Drives the `has_active_job` protection reason (§6) |

---

## 9. Service Wiring (`services/setup.py`)

The §4 state machine advances only through services — the workflow functions themselves never touch `setup_progress`. Each step-writer service calls its workflow action, then **conditionally** records the step:

- **The step-advance gate** — `_completed_step_result(result)` returns `True` when `result["status"] ∈ {"success", "already_done"}` (or the result isn't a dict). Only then does the handler call `record_step_completed(...)` followed by `manager.async_save()`. A `blocked`/`error`/`requires_confirmation` result does **not** advance the step.

| Service | Step recorded | Notes |
|---|---|---|
| `setup_add_vacuum` | `add_vacuum` | On `status=="success"` also schedules `hass.config_entries.async_reload(entry_id)` — required to wire a genuinely new vacuum's platforms |
| `setup_import_active_map` | `import_active_map` | — |
| `setup_save_rooms` | `save_rooms` | Returns `{"status": "success", "room_count": int}` |

Two more setup services write vacuum-record fields (no step):

- **`setup_set_panel_title`** — stores `panel_title` on the vacuum record (blank reverts to default), persists, re-registers the panel with `replace=True` (§3.1). The `title` field is `vol.Length(max=48)`.
- **`setup_set_map_camera`** — writes `live_map_image_entity` on the vacuum record (the §5 field); a **blank value clears it** (`record.pop`), falling back to the adapter's `live_map_image_entity_pattern`. Returns `{... "live_map_image_entity": raw_entity or None}`.

Two more services drive the map-scoped rejection state (§4.6, A4-SETUP-6) and record no setup step:

- **`setup_reject_rooms`** / **`setup_unreject_rooms`** — call `drift.reject_rooms` /
  `drift.unreject_rooms` with `map_id` resolved by `_rejection_map_id(manager,
  call)`: the caller's explicit `map_id` field if given, else the vacuum's
  currently **active** map (the card does not send `map_id` today, and the
  map the user was looking at when they clicked is the active one). `None`
  (no active-map resolver, or an adapter that can't say) falls through to the
  legacy every-map rejection rather than silently no-opping. `setup_reject_rooms`
  also fires `manager._notify_rooms_updated` for every entry in
  `affected_map_ids` so the platform-level entity teardown runs. Both `await
  manager.async_save()` and return `{"status": "success", **result}` — a
  `map_ambiguous` refusal (§4.6) is *not* re-wrapped, so its own `status:
  "error"` passes through unchanged.
