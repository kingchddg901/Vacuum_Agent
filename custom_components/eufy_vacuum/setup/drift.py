"""
Room-drift detection and setup-step bookkeeping.

The setup state machine is data-driven by the adapter's `setup.steps`
declaration. Each step ID has a completion predicate and may correspond
to a service the user (or card) calls to advance the step.

Drift between the vacuum's reported room list and the integration's
configured rooms is the key signal that the `save_rooms` step has
re-opened — discovered rooms with no `is_configured` flag, or
configured rooms no longer visible to the vacuum, both flip the
overall setup state out of "ready".

To prevent transient API glitches from producing spurious removal
notifications, removed rooms must be missing for
`removal_confirmation_passes` consecutive discovery passes before
they are flagged. New rooms surface on first sighting by default.

This module is framework-only — every brand-specific input
(adapter config, room list source, step list) is read from the
adapter registry. The Eufy adapter is the reference declaration.

Public entry points:

    compute_room_drift(manager, vacuum_entity_id) -> dict
        Live drift snapshot — new/removed/transient/in_sync.

    update_drift_history(manager, vacuum_entity_id, discovered_ids)
        Called by every discovery pass. Increments missing-pass
        counters and resets last_seen timestamps.

    record_step_completed(manager, vacuum_entity_id, step_id)
        Mark a setup step as complete in setup_progress.

    is_step_completed(progress, step_id) -> bool
        Predicate for "has this step been marked complete?"

    SETUP_STEP_IDS
        Closed enum of legal step IDs the framework understands.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..learning.utils import _iso_now

# Closed enum of setup step IDs. Adapters must declare a subset of these
# values; the registry rejects unknown IDs at adapter registration time.
SETUP_STEP_IDS: frozenset[str] = frozenset({
    "add_vacuum",
    "import_active_map",
    "save_rooms",
    # Future:
    "calibrate_map",
    "set_dock_position",
})

# Display labels for each step ID. Adapters do not override these —
# the framework controls step semantics, the adapter only declares
# which steps apply.
SETUP_STEP_LABELS: dict[str, str] = {
    "add_vacuum": "Add vacuum",
    "import_active_map": "Import active map",
    "save_rooms": "Configure rooms",
    "calibrate_map": "Calibrate map",
    "set_dock_position": "Set dock position",
}

# Service each step ID maps to. The card calls these via
# eufy_vacuum.<service_name>.
SETUP_STEP_SERVICES: dict[str, str] = {
    "add_vacuum": "setup_add_vacuum",
    "import_active_map": "setup_import_active_map",
    "save_rooms": "setup_save_rooms",
    "calibrate_map": "calibrate_map",         # mapping_services
    "set_dock_position": "set_dock_anchor",   # mapping_services
}

# Default discovery cadence values when the adapter omits them.
_DEFAULT_REMOVAL_CONFIRM_PASSES = 3
_DEFAULT_NEW_ROOM_CONFIRM_PASSES = 1
_DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS = 21_600  # 6 hours
_DEFAULT_AUTO_REFRESH_TRIGGERS: tuple[str, ...] = (
    "vacuum_docked",
    "active_map_changed",
    "config_entry_reload",
)

# Default setup.steps when the adapter omits the section. Brand-new
# adapters get the minimum viable setup flow.
_DEFAULT_SETUP_STEPS: tuple[str, ...] = ("add_vacuum", "save_rooms")


def get_adapter_setup_steps(vacuum_entity_id: str) -> list[str]:
    """Return the adapter-declared list of setup steps for one vacuum.

    Filters out unknown step IDs (defence in depth — registration should
    have rejected them, but if they slipped through, ignore rather than
    crash). Falls back to the default minimal step list when absent.
    """
    cfg = (get_adapter_config(vacuum_entity_id) or {}).get("setup", {}) or {}
    declared = cfg.get("steps")
    if not declared:
        return list(_DEFAULT_SETUP_STEPS)
    return [s for s in declared if s in SETUP_STEP_IDS]


def get_discovery_cadence(vacuum_entity_id: str) -> dict[str, Any]:
    """Read auto-discovery cadence config with safe defaults."""
    disc = (get_adapter_config(vacuum_entity_id) or {}).get("discovery", {}) or {}
    return {
        "auto_refresh_on": list(
            disc.get("auto_refresh_on") or _DEFAULT_AUTO_REFRESH_TRIGGERS
        ),
        "auto_refresh_interval_seconds": int(
            disc.get("auto_refresh_interval_seconds")
            if disc.get("auto_refresh_interval_seconds") is not None
            else _DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS
        ),
        "removal_confirmation_passes": int(
            disc.get("removal_confirmation_passes")
            or _DEFAULT_REMOVAL_CONFIRM_PASSES
        ),
        "new_room_confirmation_passes": int(
            disc.get("new_room_confirmation_passes")
            or _DEFAULT_NEW_ROOM_CONFIRM_PASSES
        ),
    }


def _get_progress_record(
    manager: Any, vacuum_entity_id: str
) -> dict[str, Any]:
    """Return the setup_progress record for one vacuum, creating it if absent.

    Always returns the live mutable dict on manager.data — callers can
    write directly and changes persist on the next manager.async_save().
    """
    root = manager.data.setdefault("setup_progress", {})
    record = root.setdefault(
        vacuum_entity_id,
        {
            "completed_steps": [],
            "last_advanced_at": None,
            "rejected_rooms": [],
            "room_drift_history": {},
        },
    )
    # Defence in depth — older records may be missing the history field.
    record.setdefault("room_drift_history", {})
    record.setdefault("rejected_rooms", [])
    record.setdefault("completed_steps", [])
    return record


def is_step_completed(progress: dict[str, Any], step_id: str) -> bool:
    """Has this setup step been marked complete?"""
    return step_id in (progress.get("completed_steps") or [])


def record_step_completed(
    manager: Any, vacuum_entity_id: str, step_id: str
) -> None:
    """Mark one setup step as complete in setup_progress.

    Idempotent — repeated calls don't duplicate the step. Updates
    last_advanced_at to the current ISO timestamp.
    """
    if step_id not in SETUP_STEP_IDS:
        return
    record = _get_progress_record(manager, vacuum_entity_id)
    completed = record["completed_steps"]
    if step_id not in completed:
        completed.append(step_id)
    record["last_advanced_at"] = _iso_now()


def active_map_configured(manager: Any, vacuum_entity_id: str) -> bool | None:
    """Whether the ACTIVE map currently has >= 1 configured room.

    Returns ``None`` when the active map can't be determined — the adapter declares no
    ``entities.active_map`` (brand without an active-map concept) or the entity is
    unknown/unavailable — so callers leave sticky step completion untouched.

    This backs the "re-open save_rooms" guard: the save_rooms completion flag is sticky,
    but a factory reset / switch to a fresh map id can leave it set against a now-dead
    map while the ACTIVE map has no configured rooms. Scoping the check to the active map
    (not "any map ever configured") is what distinguishes a genuinely-configured setup
    from a stale flag pointing at a map that no longer matters.
    """
    entities = (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}) or {}
    am_entity = entities.get("active_map")
    if not am_entity:
        return None
    state = manager.hass.states.get(am_entity)
    if state is None or state.state in ("unknown", "unavailable", "", None):
        return None
    bucket = (
        manager.data.get("maps", {})
        .get(vacuum_entity_id, {})
        .get(str(state.state))
    )
    if not isinstance(bucket, dict):
        return False
    return any(
        isinstance(room, dict) and room.get("is_configured")
        for room in (bucket.get("rooms") or {}).values()
    )


def _list_configured_room_ids(
    manager: Any, vacuum_entity_id: str
) -> set[int]:
    """Every configured room ID across all maps for one vacuum.

    A room is "configured" iff `is_configured` is True. The migration
    shim stamps existing rooms True; new rooms enter False and require
    the save_rooms step to flip them.
    """
    out: set[int] = set()
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    for bucket in vac_maps.values():
        if not isinstance(bucket, dict):
            continue
        for room_id_key, room in (bucket.get("rooms") or {}).items():
            if not isinstance(room, dict):
                continue
            if not room.get("is_configured"):
                continue
            try:
                out.add(int(room.get("room_id", room_id_key)))
            except (TypeError, ValueError):
                continue
    return out


def _room_lookup(
    manager: Any, vacuum_entity_id: str
) -> dict[int, dict[str, Any]]:
    """Return {room_id: {name, map_id}} for every room on every map.

    Used to enrich the new/removed lists in compute_room_drift with
    display-friendly metadata.
    """
    out: dict[int, dict[str, Any]] = {}
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    for map_id, bucket in vac_maps.items():
        if not isinstance(bucket, dict):
            continue
        for room_id_key, room in (bucket.get("rooms") or {}).items():
            if not isinstance(room, dict):
                continue
            try:
                rid = int(room.get("room_id", room_id_key))
            except (TypeError, ValueError):
                continue
            out[rid] = {
                "room_id": rid,
                "name": str(room.get("name", f"Room {rid}")),
                "map_id": str(map_id),
            }
    return out


def update_drift_history(
    manager: Any,
    vacuum_entity_id: str,
    discovered_room_ids: set[int],
) -> None:
    """Update per-room missing-pass counters from one discovery pass.

    Called every time a discovery pass runs (auto-trigger or manual).
    Increments `missing_passes` for configured rooms not in the
    discovered set; resets counters for rooms that reappear.

    The history dict lives on the manager's setup_progress storage and
    is persisted on the next manager.async_save().
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    history: dict[str, dict[str, Any]] = record["room_drift_history"]
    now = _iso_now()

    configured_ids = _list_configured_room_ids(manager, vacuum_entity_id)
    rejected_ids = {int(r) for r in record.get("rejected_rooms", []) if r is not None}

    # Update history for every room the framework cares about — both
    # configured and newly-discovered. Rejected rooms never enter the
    # history (they're explicitly out of scope).
    relevant_ids = (configured_ids | discovered_room_ids) - rejected_ids

    for rid in relevant_ids:
        key = str(rid)
        entry = history.setdefault(
            key,
            {
                "missing_passes": 0,
                "seen_passes": 0,
                "last_seen_at": None,
                "first_missed_at": None,
                "first_seen_at": None,
            },
        )
        if rid in discovered_room_ids:
            if entry.get("first_seen_at") is None:
                entry["first_seen_at"] = now
            entry["seen_passes"] = int(entry.get("seen_passes", 0)) + 1
            entry["missing_passes"] = 0
            entry["last_seen_at"] = now
            entry["first_missed_at"] = None
        else:
            entry["missing_passes"] = int(entry.get("missing_passes", 0)) + 1
            if entry.get("first_missed_at") is None:
                entry["first_missed_at"] = now
            # Reset seen_passes — a new sighting streak starts when the
            # room reappears.
            entry["seen_passes"] = 0

    # Clean up stale entries for rooms that no longer exist anywhere
    # (configured AND not currently discovered AND not in history-relevant
    # set). This prevents history from growing unboundedly across years.
    stale_keys = [
        key for key in list(history.keys())
        if int(key) not in relevant_ids
    ]
    for key in stale_keys:
        history.pop(key, None)


def compute_room_drift(
    manager: Any,
    vacuum_entity_id: str,
    discovered_room_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Compute the current room drift snapshot for one vacuum.

    ``discovered_room_ids`` is the live set of room IDs the adapter's
    discovery source currently reports. When None, returns drift based
    only on stored history (no live read) — useful for status responses
    that don't want to re-probe the vacuum.

    Returns:
        {
            "in_sync": bool,
            "new_rooms":           [{room_id, name, map_id}, ...],
            "removed_rooms":       [{room_id, name, map_id}, ...],
            "transiently_missing": [{room_id, name, map_id}, ...],
            "rejected_rooms":      [room_id, ...],
        }

    New rooms surface after `new_room_confirmation_passes` consecutive
    sightings (default 1 — immediate). Removed rooms surface after
    `removal_confirmation_passes` consecutive misses (default 3).
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    cadence = get_discovery_cadence(vacuum_entity_id)
    history: dict[str, dict[str, Any]] = record["room_drift_history"]
    rejected_ids = {int(r) for r in record.get("rejected_rooms", []) if r is not None}
    configured_ids = _list_configured_room_ids(manager, vacuum_entity_id)
    lookup = _room_lookup(manager, vacuum_entity_id)

    n_remove = cadence["removal_confirmation_passes"]
    n_new = cadence["new_room_confirmation_passes"]

    # Confirmed removals: configured rooms whose missing-pass counter
    # has met the threshold.
    confirmed_removed_ids: set[int] = {
        rid for rid in configured_ids
        if int(history.get(str(rid), {}).get("missing_passes", 0)) >= n_remove
    }

    # New rooms: discovered but not configured and not rejected, with
    # seen_passes >= threshold. When discovered_room_ids is None we
    # derive "new" from history alone — any room in history with
    # missing_passes == 0 and seen_passes >= n_new and not configured.
    if discovered_room_ids is not None:
        new_candidate_ids = (
            discovered_room_ids - configured_ids - rejected_ids
        )
        new_confirmed_ids: set[int] = {
            rid for rid in new_candidate_ids
            if int(history.get(str(rid), {}).get("seen_passes", 0)) >= n_new
            or n_new <= 1  # immediate-surface mode: don't wait
        }
        # Transiently-missing: configured rooms not currently discovered
        # but below the removal threshold.
        transiently_missing_ids: set[int] = (
            configured_ids - discovered_room_ids - confirmed_removed_ids
        )
    else:
        new_confirmed_ids = {
            int(key) for key, entry in history.items()
            if int(entry.get("seen_passes", 0)) >= n_new
            and int(entry.get("missing_passes", 0)) == 0
            and int(key) not in configured_ids
            and int(key) not in rejected_ids
        }
        transiently_missing_ids = {
            rid for rid in configured_ids
            if int(history.get(str(rid), {}).get("missing_passes", 0)) > 0
            and rid not in confirmed_removed_ids
        }

    def _enrich(ids: set[int]) -> list[dict[str, Any]]:
        return sorted(
            (lookup.get(rid) or {"room_id": rid, "name": f"Room {rid}", "map_id": ""}
             for rid in ids),
            key=lambda r: r.get("room_id", 0),
        )

    in_sync = (
        not new_confirmed_ids
        and not confirmed_removed_ids
        and not transiently_missing_ids
    )

    return {
        "in_sync": in_sync,
        "new_rooms": _enrich(new_confirmed_ids),
        "removed_rooms": _enrich(confirmed_removed_ids),
        "transiently_missing": _enrich(transiently_missing_ids),
        "rejected_rooms": sorted(rejected_ids),
    }


def reject_rooms(
    manager: Any, vacuum_entity_id: str, room_ids: list[int]
) -> dict[str, Any]:
    """Move room IDs into the rejected_rooms set.

    Rejected rooms never appear in `new_rooms` even when discovery
    re-reports them. If they were configured, they are also removed
    from managed_rooms across every map for this vacuum so their
    HA entities (switches, numbers, sensors) get torn down by the
    platform-level room-update callbacks.

    Returns:
        {
            "rejected": [room_id, ...],
            "removed_from_managed": [room_id, ...],
            "affected_map_ids": [map_id, ...],
        }

    Callers should call ``manager._notify_rooms_updated`` for each
    map ID in ``affected_map_ids`` so the entity-platform cleanup
    fires for every map a rejected room used to live on.
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    rejected: list[int] = list(record.get("rejected_rooms") or [])
    rejected_set = set(rejected)

    added: list[int] = []
    for rid in room_ids:
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            continue
        if rid_int not in rejected_set:
            rejected.append(rid_int)
            rejected_set.add(rid_int)
            added.append(rid_int)

    record["rejected_rooms"] = rejected

    # Strip rejected rooms from managed_rooms. Track which maps were
    # touched so the service handler can fire room-update callbacks
    # for those maps — entity-platform cleanup keys off (vacuum, map).
    removed_from_managed: list[int] = []
    affected_map_ids: list[str] = []
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    for map_id, bucket in vac_maps.items():
        if not isinstance(bucket, dict):
            continue
        rooms = bucket.get("rooms") or {}
        map_touched = False
        for key in list(rooms.keys()):
            room = rooms.get(key)
            if not isinstance(room, dict):
                continue
            try:
                rid_int = int(room.get("room_id", key))
            except (TypeError, ValueError):
                continue
            if rid_int in rejected_set:
                rooms.pop(key, None)
                removed_from_managed.append(rid_int)
                map_touched = True
        if map_touched:
            affected_map_ids.append(str(map_id))

    # Drop any stale history entries for the rejected rooms.
    history = record["room_drift_history"]
    for rid_int in added:
        history.pop(str(rid_int), None)

    return {
        "rejected": added,
        "removed_from_managed": removed_from_managed,
        "affected_map_ids": affected_map_ids,
    }


def run_discovery_pass(
    hass: HomeAssistant,
    manager: Any,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Run one discovery pass and update drift history.

    Reads the adapter's declared room-list source (via
    ``rooms.room_discovery.discover_rooms_for_vacuum``) and updates the
    per-vacuum drift history counters so subsequent
    ``compute_room_drift`` reads reflect what the vacuum currently sees.

    Cheap to call — pure state read + counter update. Safe to invoke on
    any trigger (state change, periodic timer, manual rescan) without
    debouncing.

    Returns:
        {
            "vacuum_entity_id": str,
            "discovered_room_ids": list[int],
            "updated_at": str (ISO),
        }
    """
    from ..rooms.room_discovery import discover_rooms_for_vacuum

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=vacuum_entity_id)
    discovered_ids: set[int] = set()
    for room in rooms:
        if not isinstance(room, dict):
            continue
        try:
            discovered_ids.add(int(room.get("room_id")))
        except (TypeError, ValueError):
            continue

    update_drift_history(manager, vacuum_entity_id, discovered_ids)

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "discovered_room_ids": sorted(discovered_ids),
        "updated_at": _iso_now(),
    }


def force_remove_room(
    manager: Any, vacuum_entity_id: str, room_id: int
) -> dict[str, Any]:
    """Bypass the missing-pass counter and immediately mark a room removed.

    Used by the "I know this room is gone" manual action in the setup
    tab. Sets missing_passes to the configured threshold so the next
    drift computation reports it as removed without waiting for natural
    discovery passes.

    Note: This does NOT delete the room from managed_rooms — that is
    a separate, more destructive action. The user can choose to keep
    historical learning data for the room even after marking it removed.
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    cadence = get_discovery_cadence(vacuum_entity_id)
    n_remove = cadence["removal_confirmation_passes"]
    history = record["room_drift_history"]
    key = str(int(room_id))
    entry = history.setdefault(
        key,
        {
            "missing_passes": 0,
            "seen_passes": 0,
            "last_seen_at": None,
            "first_missed_at": None,
            "first_seen_at": None,
        },
    )
    entry["missing_passes"] = max(int(entry.get("missing_passes", 0)), n_remove)
    if entry.get("first_missed_at") is None:
        entry["first_missed_at"] = _iso_now()
    entry["seen_passes"] = 0
    return {
        "room_id": int(room_id),
        "missing_passes": entry["missing_passes"],
        "threshold": n_remove,
    }
