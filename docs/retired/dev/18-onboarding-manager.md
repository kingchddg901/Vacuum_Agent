# 18 — Onboarding Manager

> **Scope:** Complete implementation reference for `onboarding/manager.py`. Every state machine, storage path, predicate, and public method is derived directly from the source. A developer should be able to re-implement the onboarding manager from this document alone.

---

## 1. Overview

The onboarding manager tracks the per-vacuum, per-map setup state that determines whether a vacuum is ready to accept scheduled cleaning jobs. It answers two questions:

1. **Have all rooms been discovered?** — has the `save_rooms` setup step run at least once for this map?
2. **Have all room floor types been confirmed?** — has the user assigned a floor type (hardwood/carpet) to every room?

When both are true, onboarding is complete for that (vacuum, map) pair and the panel's job-scheduling UI unlocks.

The manager also detects **new rooms** (room count increased since last check) and **map rebuilds** (map bucket was replaced) so the panel can surface notifications prompting the user to re-confirm floor types.

**Module:** `custom_components/eufy_vacuum/onboarding/manager.py`

**Constructor:** `OnboardingManager(data: dict, hass: HomeAssistant)`

Note: Unlike most managers, `OnboardingManager` takes `data` and `hass` directly — it holds **no back-reference** to `EufyVacuumManager`. This keeps it testable in isolation.

---

## 2. Storage Layout

```
data["onboarding"][vacuum_entity_id][str(map_id)] = {
    "rooms_discovered":           bool,   # True after save_rooms step completes
    "floor_types_confirmed":      dict,   # {room_id_str: bool} — True when confirmed
    "room_count_at_last_check":   int,    # room count at last check_for_new_rooms call
    "discovery_notified":         bool,   # True after new-room notification fired
    "rebuild_notified":           bool,   # True after map-rebuild notification fired
}
```

**Default on first access:**
```python
{
    "rooms_discovered":         False,
    "floor_types_confirmed":    {},
    "room_count_at_last_check": 0,
    "discovery_notified":       False,
    "rebuild_notified":         False,
}
```

The storage is created lazily per vacuum per map. Missing keys default to their False/empty defaults via `setdefault`.

---

## 3. Onboarding State Machine

### 3.1 Completion predicate

```
rooms_discovered     = stored_flag AND len(rooms) > 0
floor_types_complete = len(enabled_rooms_needing_floor_type) == 0
onboarding_complete  = rooms_discovered AND floor_types_complete
```

Only **enabled** rooms are inspected for floor-type confirmation; disabled rooms are skipped. A room needs a floor type when it is enabled and `floor_types_confirmed[room_id]` is not `True`.

`rooms_discovered` requires both the stored `rooms_discovered` flag **and** `len(rooms) > 0` — the stored flag alone is not sufficient if the map currently has no rooms.

### 3.2 `get_onboarding_state`

```python
manager.get_onboarding_state(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Keyword-only. Returns:

```python
{
    "vacuum_entity_id":                  str,
    "map_id":                            str,
    "rooms_discovered":                  bool,
    "room_count":                        int,        # len(rooms) on the map
    "floor_types_complete":              bool,
    "onboarding_complete":               bool,
    "enabled_rooms_needing_floor_type":  list[str],  # enabled room IDs missing a confirmed floor type
    "status":                            str,        # see below
}
```

There is no `unconfirmed_room_ids` key — the field is `enabled_rooms_needing_floor_type`.

**Status values:**

| Status | Condition |
|---|---|
| `"complete"` | `rooms_discovered` AND `floor_types_complete` |
| `"floor_type_needed"` | `rooms_discovered` but one or more rooms lack a confirmed floor type |
| `"rooms_needed"` | `rooms_discovered` is False |

---

## 4. Manager Methods

### 4.1 `mark_rooms_discovered`

```python
manager.mark_rooms_discovered(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> None
```

Sets `data["onboarding"][vacuum][map_id]["rooms_discovered"] = True` and stamps `room_count_at_last_check` with the current room count. Called by `RoomMapManager.save_managed_rooms()` after rooms are written.

### 4.2 `confirm_floor_type`

```python
manager.confirm_floor_type(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_id: str,
) -> None
```

Keyword-only. Always sets `floor_types_confirmed[str(room_id)] = True` — there is **no** `confirmed` parameter (the method can only confirm, not un-confirm).

**It has no standalone / service caller.** The only runtime invoker is `save_managed_rooms` (`rooms/room_crud.py::save_managed_rooms`), which loops it over **every** entry in `managed_rooms`, gated on `if managed_rooms:` (non-empty). So it is a **bulk auto-confirm of all managed rooms**, fired on **every** `save_managed_rooms` call — initial import *and* every subsequent re-save/edit — **not** a per-room user decision and **not** limited to initial import. The panel "re-confirms" only by re-running the `save_rooms` step (`setup_save_rooms` → `save_managed_rooms`), which re-confirms everything; there is no per-room confirm service.

> **Design consequence (code-flag CS-3).** Because every save auto-confirms all rooms, the floor-type gate is **self-satisfying** in the normal flow — it can only ever fire when rooms enter `map_bucket["rooms"]` via a **non-save path** (a reconcile renumber before `remap_confirmed_floor_types` runs, or `rebuild_map` adding new room IDs). The §1 framing ("has the user assigned a floor type to every room?") describes an intended human review that the code does not actually enforce — flagged for a product decision.

### 4.3 `check_for_new_rooms`

```python
manager.check_for_new_rooms(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> bool
```

Reads the current room count from the adapter-declared discovery source (`adapter_config["discovery"]["room_list_entity"]` — the sentinel string `"vacuum_entity"` (also the default) resolves to `vacuum_entity_id` itself — and `["room_list_attribute"]`, defaulting to `"segments"`) and compares it to the stored `room_count_at_last_check` (read via `int(...)`). Returns a plain **bool**: `True` when `current_count > last_count`. Returns `False` if the source state is missing or the attribute is not a list. It does **not** update the stored count.

**Active-map guard (DR-ONB-2).** The stored side (`room_count_at_last_check`)
is scoped per map by `mark_rooms_discovered`. The live side — the vacuum
entity's room-list attribute — has no map dimension at all: it always
describes whichever map the robot currently has **loaded**. On a multi-map
vacuum, calling this for a map that is not the active one would compare one
map's stored count against a different map's live count, which is not a
stale answer, it is an answer about the wrong room set. So before comparing,
the method resolves the active map (`rooms.room_discovery.get_active_map_id`)
and returns `False` immediately — "I cannot tell" — whenever it can be
determined and does not match the requested `map_id`. This preserves every
single-map install byte-for-byte (the only shape reachable today) while
making a multi-map call honest instead of silently wrong.

It is exposed on `EufyVacuumManager` via a thin delegation wrapper (`EufyVacuumManager.check_for_new_rooms`). It has no live in-framework caller today — the auto-discovery path that keeps drift fresh (`listeners/discovery.py` → `setup/drift.py::run_discovery_pass`) uses the counter-based room-drift history (see [22-adapter-config-reference §12](22-adapter-config-reference.md)), not this single-shot count comparison. A caller would decide whether to show a notification.

### 4.4 `reset_onboarding`

```python
manager.reset_onboarding(
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict
```

Clears all flags for the (vacuum, map) pair back to defaults and returns a result dict:

```python
# resets data["onboarding"][vacuum][map_id] to:
{
    "rooms_discovered":         False,
    "floor_types_confirmed":    {},
    "room_count_at_last_check": 0,
    "discovery_notified":       False,
    "rebuild_notified":         False,
}
# returns:
{"vacuum_entity_id": str, "map_id": str, "reset": True}
```

Exposed on `EufyVacuumManager` via a thin delegation wrapper (`EufyVacuumManager.reset_onboarding`); intended for the map-rebuild-from-scratch flow. It has no live in-framework caller today — `RoomMapManager.rebuild_map()` rebuilds the map bucket but does **not** currently reset onboarding state.

### 4.5 `get_rooms_onboarding_summary`

```python
manager.get_rooms_onboarding_summary(
    *,
    vacuum_entity_id: str,
) -> dict
```

Aggregates `get_onboarding_state()` across every known map for one vacuum:

```python
{
    "vacuum_entity_id": str,
    "all_complete":     bool,        # True only if every map is onboarding_complete
    "maps":             list[dict],  # one get_onboarding_state() result per map
}
```

**DR-ONB-3 — no vacuous truth.** `all_complete = bool(maps) and not any_incomplete`
— a vacuum with **no maps** returns `all_complete=False`, `maps=[]`, **not**
vacuously `True`. This mirrors `setup/status.py`'s own `bool(managed) and …`
guard for the identical shape ([15 §5](15-setup-system.md)). The diagnostic
sensor (`sensor/onboarding.py`) applies the same non-empty-collection rule
independently at its own read: `native_value` short-circuits to
`"rooms_needed"` whenever `maps` is empty, before either of its scan loops
run — "no map imported yet" reads as rooms genuinely needing setup, not as
complete.

(There are no `set_discovery_notified` / `set_rebuild_notified` methods. The `discovery_notified` / `rebuild_notified` flags exist in storage but are only written by `reset_onboarding` / defaults — they are dead fields, never read and never set `True`, code-flag CS-1. `room_count_at_last_check` is likewise effectively write-only: only `check_for_new_rooms` reads it, and that has no live caller — CS-2.)

### 4.6 `remap_confirmed_floor_types`

```python
manager.remap_confirmed_floor_types(
    *,
    vacuum_entity_id: str,
    map_id: str,
    id_remap: dict[int, int],
) -> None
```

Keyword-only. Carries existing floor-type confirmations onto re-segmented room IDs after a reconcile migrate. Confirmations are keyed by room ID, so when a reconcile renumbers rooms it re-keys each entry through the old→new `id_remap`. **No-op when `id_remap` is empty** (no renumbering).

**DR-ONB-1 — rebuilt from a snapshot, never popped in place.** The
implementation takes an immutable snapshot of the confirmed dict
(`before = dict(confirmed)`) *before* touching anything, builds the new dict
purely from that snapshot (every key not named as an `old_id` in `id_remap`
survives verbatim; every `old_id → new_id` pair copies `before[old_id]`'s
value to `new_id` when it was `True`), and only then replaces the live dict's
contents via `confirmed.clear()` + `confirmed.update(rebuilt)` — never
reassignment, since `reset_onboarding` and `get_onboarding_state` both hold
the same dict object by reference. This matters because a **pop-and-write-in-place**
implementation (mutating `confirmed` while also reading from it in the same
pass) corrupts a remap whose `new_id` is itself a *later* `old_id` in the same
chain — e.g. a chain `{1:2, 2:3, 3:4}` with rooms 1–3 confirmed would collapse
to a single surviving `{'4': True}` instead of preserving all three, and a
swap `{1:2, 2:1}` can land a confirmation on the wrong room. The snapshot-based
rebuild is immune to iteration order for exactly this reason. One residual
ambiguity, resolved deliberately: if a target `new_id` is *also* a
pre-existing confirmed key that no remap entry names as an `old_id`, the
migrated room's confirmation wins (matching `rooms/room_crud.py`'s own
rule-status purge on the identical hazard).

Without this re-keying, every renumbered-but-already-confirmed room reads as needing confirmation (its confirmation is still keyed to the old ID), so `floor_types_complete` flips False and the core start gate blocks cleaning with `onboarding_required` until the user re-confirms each one.

Called by `RoomMapManager.reconcile_room()` (`rooms/room_crud.py`) as part of the reconcile migrate, right after the `id_remap` is applied to the room records. See §6.

---

## 5. Floor Type Semantics

Floor type confirmation is per-room, not per-map. The `floor_types_confirmed` dict maps room ID strings to booleans:

```python
{"1": True, "2": True, "3": False}
```

A room with `confirmed == False` or missing from the dict counts as unconfirmed. Unconfirmed **enabled** rooms block the `"complete"` status AND hard-block job start via the core start-status `onboarding_required` gate (`blocked`, not a warning); disabled rooms are excluded and never gate completion or starting.

> **The start gate keys on `floor_types_complete` alone.** `get_start_status` (`core/manager.py::get_start_status`; the gate itself at `:3481`) blocks only on `if not onboarding["floor_types_complete"]` — **not** the full `onboarding_complete` (it never consults `rooms_discovered`). Consequences: a map in `rooms_needed` status (stored flag `False` / zero rooms) is **not** blocked by the onboarding gate; and a **zero-room map** has `floor_types_complete` vacuously `True` (empty `enabled_rooms_needing_floor_type`), so onboarding never blocks it. Combined with the bulk auto-confirm (§4.2), the `onboarding_required` block effectively only fires for rooms that entered the bucket via a non-save path.

---

## 6. Integration Points

| Caller | Method | When |
|---|---|---|
| `RoomMapManager.save_managed_rooms()` | `mark_rooms_discovered()`, `confirm_floor_type()` (bulk loop over every room) | After rooms written to storage — the **only** caller of `confirm_floor_type` (§4.2) |
| `EufyVacuumManager` delegation only (no live caller) | `reset_onboarding()` | Intended for map rebuild from scratch — not yet wired |
| `EufyVacuumManager` delegation only (no live caller) | `check_for_new_rooms()` | Predicate; the live drift path uses `setup/drift.py` instead |
| `core/manager.py::get_start_status` | `get_onboarding_state()` | Embedded as the `onboarding_status` block of the start-status response (the start gate, §5) |
| `sensor/onboarding.py` (`EufyVacuumOnboardingSensor`) | `get_rooms_onboarding_summary()` | Diagnostic sensor state = worst-case status across maps (`rooms_needed` > `floor_type_needed` > `complete`) |
| `RoomMapManager.reconcile_room()` (`rooms/room_crud.py`) | `remap_confirmed_floor_types()` | After a reconcile migrate applies the `id_remap` — re-keys confirmations so renumbered rooms don't re-block start |

> There is **no** panel/service seam that calls `get_onboarding_state` or `confirm_floor_type` directly. The panel reads onboarding state via the `get_start_status` embedding and the diagnostic sensor above; it changes floor types only by re-running `setup_save_rooms` (which bulk-auto-confirms, §4.2).
